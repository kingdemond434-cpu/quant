"""Decision replay -- freeze a solve's inputs, reproduce it, and prove what moves it.

WHY THIS EXISTS (principal, 2026-10-06: ARCH-04, ARCH-13, ARCH-19, ALLOC-19). Every allocation
pass solved a book and threw its inputs away. The artifact said what the desk decided and never
what it decided ON, so three questions the principal asked had no answer anyone could compute:

  1. CAN THE DECISION BE REPRODUCED? A book nobody can re-derive is an assertion, not a
     decision. `freeze` writes the solver's COMPLETE input -- every `SleeveEvidence` field, the
     `WorldConfig`, the drawn `Worlds` tensor itself, the held book and the solve kwargs -- and
     `replay` re-runs `robust_elog.optimise` on exactly those bytes and says whether the answer
     is the same one, within a tolerance stated below and not chosen after looking.
  2. WAS MOVING BETTER THAN STAYING? `replay` scores the HELD book on the SAME worlds
     (`robust_elog.score_book`), so "the solve beats holding" is one subtraction on one
     population -- not two numbers drawn on two different days (ARCH-04).
  3. DOES EACH INPUT REACH THE DECISION, AND IN THE RIGHT DIRECTION? `perturb` moves ONE channel
     -- posterior mean, volatility, decay, cost, regime, dependence, crisis share, or pure noise
     -- re-draws the worlds with the SAME seed (common random numbers, so the only difference
     between the two populations is the channel), re-solves, and returns the delta. A channel
     that does not move the book is not connected; one that moves it the wrong way is wired
     backwards; tiny noise that moves it materially is gratuitous turnover (ALLOC-19).
     `missing_is_not_zero` does the same for MISSING inputs: a NaN where a critical number
     should be must never buy a sleeve more heat than the frozen decision gave it (ARCH-19).

WHAT IS NOT IN HERE. No desk paths, no policy, no gate. `pf_allocator` calls `freeze` with the
directory it owns; everything else is a pure function of a snapshot, so a harness, a test or an
auditor on another machine can run it on a copied file and get the same answer.

THE SNAPSHOT FORMAT. One `.npz` per decision, written atomically (temp + fsync + os.replace), no
pickle anywhere (`allow_pickle=False` on load, so a snapshot cannot execute code). Arrays are
stored as arrays with their own dtype; every scalar, tuple and mapping goes into one canonical
JSON document stored as uint8 bytes. A sha256 covers the JSON and every array's name, dtype,
shape and bytes, and `thaw` REFUSES a file whose digest does not match -- a corrupt snapshot is
an error, never a slightly different decision replayed as if it were the recorded one.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import math
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.portfolio import robust_elog
from libs.portfolio.robust_elog import (
    AllocationResult,
    SleeveEvidence,
    WorldConfig,
    Worlds,
    decay_prob_of,
    sample_worlds,
    score_book,
)

__all__ = [
    "CHANNELS",
    "HEAT_L1_TOL",
    "KEEP_SNAPSHOTS",
    "MATERIAL_TURNOVER",
    "MAX_SNAPSHOT_BYTES",
    "Snapshot",
    "SnapshotCorrupt",
    "freeze",
    "missing_is_not_zero",
    "perturb",
    "replay",
    "thaw",
]

#: THE DISK BOUND, STATED. At most this many snapshots are kept per directory, newest first by
#: modification time, AND their total size is held under `MAX_SNAPSHOT_BYTES` -- whichever binds
#: first. The newest snapshot is ALWAYS kept, whatever its size: a bound that could delete the
#: decision just made would make the replay record empty on exactly the pass that was too big.
#: One snapshot is dominated by the worlds tensor, which `WorldConfig.max_elements` caps at 12M
#: float32 = 48 MB, plus the sleeve histories; so the worst case is about 6 x 60 MB. The build box
#: has run with ~1 GB of free disk (CLAUDE.md, measured 2026-09-24), hence a bound in bytes and
#: not only a count.
KEEP_SNAPSHOTS = 6
MAX_SNAPSHOT_BYTES = 384 * 1024 * 1024

#: EQUIVALENCE, STATED BEFORE ANY REPLAY WAS RUN. Two books are the SAME DECISION when
#:   heat L1 distance <= HEAT_L1_TOL                (one hundredth of a percent of account risk,
#:                                                  summed over every sleeve), AND
#:   |robust score difference| <= score band        (the recorded certificate's own gap: the
#:                                                  solver already said it cannot tell books
#:                                                  apart inside that band, so replay may not
#:                                                  demand more of it than it certified).
#: On one machine the solve is deterministic and replay is bit-identical (`identical`); the
#: tolerance is for another machine's BLAS summing a float32 einsum in another order.
HEAT_L1_TOL = 1e-4
#: The floor of the score band, so a book certified at a zero gap is not held to rounding.
SCORE_BAND_FLOOR = 1e-10
#: GRATUITOUS TURNOVER, STATED. A perturbation at the noise level (1e-6 relative) that moves the
#: book by more than this heat L1 is churn the inputs did not ask for (ALLOC-19). The same number
#: is the "did not raise heat" tolerance of `missing_is_not_zero`.
MATERIAL_TURNOVER = 1e-4

#: The solve kwargs a snapshot carries. `deadline` is deliberately NOT one of them: it is a
#: wall-clock instant, so replaying it would replay the clock, not the decision. A frozen solve
#: that hit its deadline says so in the recorded `budget_hit`, and replay runs to completion.
SOLVE_KEYS = ("hard_cap", "target", "max_per_sleeve", "warm_start", "iterations", "step")

_SNAP_PREFIX = "decision-"
_JSON_KEY = "__json__"
_SHA_KEY = "__sha256__"
_STAMP_KEY = "__frozen_utc__"


class SnapshotCorrupt(ValueError):
    """The file's digest does not match its contents, or a required entry is missing."""


@dataclass(frozen=True)
class Snapshot:
    """A thawed decision: everything `optimise` read, plus what it answered and what was held."""

    ev: tuple[SleeveEvidence, ...]
    cfg: WorldConfig
    worlds: Worlds
    held_book: dict[str, float]
    solve_kwargs: dict[str, Any]
    decision_id: str
    meta: dict[str, Any] = field(default_factory=dict)
    #: The recorded result (`AllocationResult` fields as a dict), or None when none was frozen.
    recorded: dict[str, Any] | None = None
    sha256: str = ""
    frozen_utc: str = ""
    path: str = ""


# ------------------------------------------------------------------------------------ encoding

def _jsonable(v: Any) -> Any:
    """A field value as canonical JSON. Unknown types RAISE: a new field kind must be taught to
    the snapshot, never silently stringified into something replay would read back differently."""
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, (tuple, list)):
        return [_jsonable(x) for x in v]
    if isinstance(v, Mapping):
        return {str(k): _jsonable(x) for k, x in v.items()}
    raise TypeError(f"decision_replay cannot freeze a value of type {type(v).__name__}")


def _tuplify(v: Any) -> Any:
    return tuple(_tuplify(x) for x in v) if isinstance(v, list) else v


def _encode_dataclass(obj: Any, prefix: str, arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    """Every field of a frozen dataclass, by `dataclasses.fields` -- so a field added to
    `SleeveEvidence` or `WorldConfig` tomorrow is frozen tomorrow without editing this file, or
    refused loudly by `_jsonable` if it is a kind this format does not know."""
    doc: dict[str, Any] = {}
    for f in dataclasses.fields(obj):
        v = getattr(obj, f.name)
        if isinstance(v, np.ndarray):
            arrays[f"{prefix}{f.name}"] = np.ascontiguousarray(v)
            doc[f.name] = {"kind": "array"}
        elif isinstance(v, tuple):
            doc[f.name] = {"kind": "tuple", "v": _jsonable(v)}
        else:
            doc[f.name] = {"kind": "scalar", "v": _jsonable(v)}
    return doc


def _decode_dataclass(cls: Any, doc: Mapping[str, Any], prefix: str,
                      arrays: Mapping[str, np.ndarray]) -> Any:
    kw: dict[str, Any] = {}
    for name, spec in doc.items():
        kind = spec.get("kind")
        if kind == "array":
            key = f"{prefix}{name}"
            if key not in arrays:
                raise SnapshotCorrupt(f"snapshot lacks array {key}")
            kw[name] = arrays[key]
        elif kind == "tuple":
            kw[name] = _tuplify(spec.get("v"))
        else:
            kw[name] = spec.get("v")
    return cls(**kw)


def _result_doc(result: AllocationResult | Mapping[str, Any] | None) -> dict[str, Any] | None:
    if result is None:
        return None
    if isinstance(result, AllocationResult):
        return dict(_jsonable(dataclasses.asdict(result)))
    return dict(_jsonable(dict(result)))


def _solve_doc(solve_kwargs: Mapping[str, Any] | None) -> dict[str, Any]:
    kw = dict(solve_kwargs or {})
    kw.pop("deadline", None)                       # a wall-clock instant is not a solver input
    unknown = sorted(set(kw) - set(SOLVE_KEYS))
    if unknown:
        raise ValueError(f"unknown solve kwargs {unknown}; a snapshot carries {SOLVE_KEYS}")
    if "hard_cap" not in kw:
        raise ValueError("solve_kwargs must carry hard_cap: optimise cannot run without it")
    return dict(_jsonable(kw))


def _digest(doc_bytes: bytes, arrays: Mapping[str, np.ndarray]) -> str:
    h = hashlib.sha256()
    h.update(doc_bytes)
    for k in sorted(arrays):
        a = np.ascontiguousarray(arrays[k])
        h.update(k.encode("utf-8"))
        h.update(a.dtype.str.encode("ascii"))
        h.update(repr(tuple(a.shape)).encode("ascii"))
        h.update(a.tobytes())
    return h.hexdigest()


def _canonical(doc: Mapping[str, Any]) -> bytes:
    # allow_nan: an inf `max_per_sleeve` or a -inf score is a real value and must round-trip.
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=True,
                      ensure_ascii=True).encode("ascii")


def _safe_id(decision_id: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]", "_", str(decision_id or "")).strip("._")
    return (s or "unnamed")[:120]


# ------------------------------------------------------------------------------- freeze / thaw

def freeze(path: str | Path, *, ev: Sequence[SleeveEvidence], cfg: WorldConfig, worlds: Worlds,
           held_book: Mapping[str, float] | None, solve_kwargs: Mapping[str, Any],
           decision_id: str, meta: Mapping[str, Any] | None = None,
           result: AllocationResult | Mapping[str, Any] | None = None,
           keep: int = KEEP_SNAPSHOTS, max_bytes: int = MAX_SNAPSHOT_BYTES) -> Path:
    """Persist one decision's complete solver input into directory `path`; return the file.

    `result` is the book the solve returned. Without it `replay` can still prove the solve is
    deterministic (two re-runs), but not that it reproduces what was PUBLISHED -- so the
    allocator passes it. `meta` is free JSON (fingerprints, mode, the binding verdict); values
    JSON cannot carry are stringified there, and only there.

    The digest covers the decision's inputs, never the wall-clock it was written at: the same
    inputs frozen twice carry the same sha256, which is what lets an auditor say two passes
    decided on identical state.
    """
    if not ev:
        raise ValueError("no sleeves to freeze")
    arrays: dict[str, np.ndarray] = {}
    sleeves = [_encode_dataclass(e, f"ev{i}__", arrays) for i, e in enumerate(ev)]
    cfg_doc = _encode_dataclass(cfg, "cfg__", arrays)
    arrays["worlds__r"] = np.ascontiguousarray(worlds.r)
    arrays["worlds__crisis"] = np.ascontiguousarray(worlds.crisis)
    arrays["worlds__mu_draws"] = np.ascontiguousarray(worlds.mu_draws)
    doc = {
        "format": 1,
        "decision_id": str(decision_id),
        "sleeves": sleeves,
        "cfg": cfg_doc,
        "worlds": {"names": list(worlds.names), "regimes": list(worlds.regimes),
                   "note": str(worlds.note)},
        "held_book": {str(k): float(v) for k, v in (held_book or {}).items()},
        "solve_kwargs": _solve_doc(solve_kwargs),
        "recorded": _result_doc(result),
        "meta": json.loads(json.dumps(dict(meta or {}), default=str, allow_nan=True)),
    }
    doc_bytes = _canonical(doc)
    sha = _digest(doc_bytes, arrays)

    out_dir = Path(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{_SNAP_PREFIX}{_safe_id(decision_id)}.npz"
    payload = dict(arrays)
    payload[_JSON_KEY] = np.frombuffer(doc_bytes, dtype=np.uint8)
    payload[_SHA_KEY] = np.frombuffer(sha.encode("ascii"), dtype=np.uint8)
    payload[_STAMP_KEY] = np.frombuffer(
        datetime.now(UTC).isoformat().encode("ascii"), dtype=np.uint8)
    tmp = out_dir / f".{target.name}.{os.getpid()}.tmp"
    with tmp.open("wb") as fh:
        np.savez(fh, **payload)                      # type: ignore[arg-type]
        fh.flush()
        os.fsync(fh.fileno())
    for i in range(5):
        try:
            os.replace(tmp, target)
            break
        except PermissionError:                     # a Windows reader holding the old file
            if i == 4:
                raise
            time.sleep(0.05 * (i + 1))
    _prune(out_dir, keep=keep, max_bytes=max_bytes, protect=target)
    return target


def _prune(out_dir: Path, *, keep: int, max_bytes: int, protect: Path) -> None:
    """Newest first; drop everything past `keep` files or `max_bytes`, never the newest one."""
    snaps = sorted(out_dir.glob(f"{_SNAP_PREFIX}*.npz"),
                   key=lambda p: (p != protect, -p.stat().st_mtime))
    total = 0
    for i, p in enumerate(snaps):
        size = p.stat().st_size
        total += size
        if i == 0:
            continue
        if i >= max(1, keep) or total > max_bytes:
            with contextlib.suppress(OSError):       # a reader holds it; next freeze retries
                p.unlink()


def thaw(path: str | Path) -> Snapshot:
    """Load a snapshot back EXACTLY, refusing any file whose digest does not match."""
    p = Path(path)
    with np.load(p, allow_pickle=False) as z:
        raw = {k: np.array(z[k]) for k in z.files}      # copy out, then close (Windows locks)
    for k in (_JSON_KEY, _SHA_KEY):
        if k not in raw:
            raise SnapshotCorrupt(f"{p.name}: missing {k}")
    doc_bytes = raw.pop(_JSON_KEY).tobytes()
    sha = raw.pop(_SHA_KEY).tobytes().decode("ascii")
    stamp = raw.pop(_STAMP_KEY).tobytes().decode("ascii") if _STAMP_KEY in raw else ""
    if _digest(doc_bytes, raw) != sha:
        raise SnapshotCorrupt(f"{p.name}: sha256 mismatch -- the snapshot is not what was frozen")
    doc = json.loads(doc_bytes.decode("ascii"))
    ev = tuple(_decode_dataclass(SleeveEvidence, s, f"ev{i}__", raw)
               for i, s in enumerate(doc["sleeves"]))
    cfg = _decode_dataclass(WorldConfig, doc["cfg"], "cfg__", raw)
    wd = doc["worlds"]
    worlds = Worlds(r=raw["worlds__r"], names=tuple(wd["names"]), crisis=raw["worlds__crisis"],
                    mu_draws=raw["worlds__mu_draws"], regimes=tuple(wd["regimes"]),
                    note=str(wd["note"]))
    return Snapshot(ev=ev, cfg=cfg, worlds=worlds, held_book=dict(doc["held_book"]),
                    solve_kwargs=dict(doc["solve_kwargs"]), decision_id=str(doc["decision_id"]),
                    meta=dict(doc.get("meta") or {}), recorded=doc.get("recorded"),
                    sha256=sha, frozen_utc=stamp, path=str(p))


# -------------------------------------------------------------------------------------- replay

def _solve(ev: Sequence[SleeveEvidence], cfg: WorldConfig, worlds: Worlds,
           kw: Mapping[str, Any]) -> AllocationResult:
    return robust_elog.optimise(ev, cfg=cfg, worlds=worlds, **dict(kw))


def _l1(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    keys = set(a) | set(b)
    return float(sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys))


def _score_band(rec: Mapping[str, Any]) -> float:
    """The recorded certificate's own resolution: the widest finite of its tolerance and gaps."""
    vals = [float(rec.get(k, float("nan"))) for k in ("gap_tolerance", "global_gap",
                                                       "optimality_gap")]
    fin = [v for v in vals if math.isfinite(v)]
    return max([SCORE_BAND_FLOOR, *fin])


def replay(snapshot: Snapshot) -> dict[str, Any]:
    """Re-solve on the frozen inputs, compare to the recorded book, and score holding (ARCH-04).

    `equivalent` is the stated rule (`HEAT_L1_TOL` and the certificate's score band), `identical`
    is bit-for-bit. `hold` is the HELD book scored on the same frozen worlds, and
    `decision_minus_hold` is how much robust E[log W] per day the decision buys over standing
    still -- the only comparison in which turnover can be said to have paid for itself.
    """
    s = snapshot
    new = _solve(s.ev, s.cfg, s.worlds, s.solve_kwargs)
    basis = "recorded"
    rec = s.recorded
    if rec is None:
        # No published book to compare with: prove at least that the solve is a function of
        # its inputs, by solving twice. Weaker, and named as such.
        basis = "rerun"
        rec = dataclasses.asdict(_solve(s.ev, s.cfg, s.worlds, s.solve_kwargs))
    rec_heat = {k: float(v) for k, v in (rec.get("heat") or {}).items()}
    l1 = _l1(rec_heat, new.heat)
    r_score = float(rec.get("robust_score", float("nan")))
    both_finite = math.isfinite(r_score) and math.isfinite(new.robust_score)
    score_diff = abs(new.robust_score - r_score) if both_finite else (
        0.0 if r_score == new.robust_score else float("inf"))
    band = _score_band(rec)
    hold = score_book(s.ev, s.held_book, cfg=s.cfg, worlds=s.worlds)
    hold_score = float(hold["robust_score"])

    def _minus(a: float) -> float:
        if math.isfinite(a) and math.isfinite(hold_score):
            return a - hold_score
        return float("inf") if a > hold_score else float("-inf") if a < hold_score else 0.0

    return {
        "decision_id": s.decision_id,
        "sha256": s.sha256,
        "basis": basis,
        "identical": bool(l1 == 0.0 and score_diff == 0.0),
        "equivalent": bool(l1 <= HEAT_L1_TOL and score_diff <= band),
        "heat_l1": l1,
        "heat_l1_tol": HEAT_L1_TOL,
        "score_recorded": r_score,
        "score_replayed": float(new.robust_score),
        "score_diff": float(score_diff),
        "score_band": band,
        "total_heat_recorded": float(sum(rec_heat.values())),
        "total_heat_replayed": float(new.total_heat),
        "recorded_budget_hit": bool(rec.get("budget_hit", False)),
        "replayed_heat": dict(new.heat),
        "certificate": new.certificate,
        "hold": {k: float(v) for k, v in hold.items()},
        "decision_minus_hold": _minus(r_score),
        "replay_minus_hold": _minus(float(new.robust_score)),
        "decision_beats_hold": bool(_minus(r_score) > 0.0),
    }


# ------------------------------------------------------------------------------------- perturb

#: Each channel, the input it moves, the UNIT of `size`, and the economically expected sign of
#: the change in heat (on the named sleeve when one is given, else on total heat). None means
#: the direction depends on the data and the harness must state its own expectation.
CHANNELS: dict[str, tuple[str, str, int | None]] = {
    "mean":       ("daily_r level (posterior mean)", "own std of daily R", +1),
    "volatility": ("daily_r dispersion about its active mean (GARCH)", "relative scale", -1),
    "decay":      ("decay_prob_i", "probability points", -1),
    "cost":       ("cost_bias_r", "R per trade", -1),
    "regime":     ("WorldConfig.regime_probs", "probability mass moved to `regime`", None),
    "dependence": ("factor_load common factor (correlation target)", "common variance share",
                   -1),
    "crisis":     ("WorldConfig.crisis_common_share", "share points", -1),
    "noise":      ("daily_r multiplicative noise", "relative std", 0),
}

_BASE_CACHE: dict[tuple[str, str], tuple[Worlds, AllocationResult]] = {}


def _redrawn_base(s: Snapshot) -> tuple[Worlds, AllocationResult]:
    """The frozen evidence re-drawn with its own seed and solved: the common-random-numbers
    baseline every perturbation is measured against, so the ONLY difference between the two
    populations is the channel that was moved."""
    key = (s.sha256 or s.decision_id, s.path)
    hit = _BASE_CACHE.get(key)
    if hit is not None:
        return hit
    w = sample_worlds(s.ev, s.cfg)
    out = (w, _solve(s.ev, s.cfg, w, s.solve_kwargs))
    if len(_BASE_CACHE) >= 4:
        _BASE_CACHE.pop(next(iter(_BASE_CACHE)))
    _BASE_CACHE[key] = out
    return out


def _active(a: np.ndarray) -> np.ndarray:
    out: np.ndarray = np.isfinite(a) & (a != 0.0)
    return out


def _shift_mean(e: SleeveEvidence, size: float) -> SleeveEvidence:
    # Shift ONLY the days the sleeve traded, by size*sd/activity, so its own mean moves by exactly
    # size*sd while its activity (which prices cost) and its flat days stay what they were.
    a = np.array(e.daily_r, dtype=float)
    own = e.own_r
    act = _active(a)
    if own.size < 2 or not act.any():
        return e
    frac = float(act.sum()) / float(own.size)
    a[act] = a[act] + size * float(own.std(ddof=1)) / frac
    return dataclasses.replace(e, daily_r=a)


def _scale_vol(e: SleeveEvidence, size: float) -> SleeveEvidence:
    a = np.array(e.daily_r, dtype=float)
    act = _active(a)
    if int(act.sum()) < 2:
        return e
    m = float(a[act].mean())
    a[act] = m + (a[act] - m) * (1.0 + size)
    return dataclasses.replace(e, daily_r=a)


def _add_noise(e: SleeveEvidence, size: float, rng: np.random.Generator) -> SleeveEvidence:
    a = np.array(e.daily_r, dtype=float)
    z = rng.standard_normal(a.size)
    act = _active(a)
    a[act] = a[act] * (1.0 + size * z[act])
    return dataclasses.replace(e, daily_r=a)


def _add_common_factor(e: SleeveEvidence, share: float) -> SleeveEvidence:
    # A common factor carrying `share` of the sleeve's factor-model variance, appended as one
    # more whitened loading: pairwise it adds ~share of correlation to the structured target.
    share = min(max(share, 0.0), 0.999)
    load = np.asarray(e.factor_load, dtype=float)
    rv = max(0.0, float(e.factor_resid_var or 0.0))
    base = float(load @ load) + rv
    if base <= 0.0:
        return dataclasses.replace(e, factor_load=(math.sqrt(share),),
                                   factor_resid_var=1.0 - share)
    c = math.sqrt(share * base / (1.0 - share))
    return dataclasses.replace(e, factor_load=(*map(float, load), c))


def _perturbed_inputs(s: Snapshot, channel: str, size: float, sleeve: str | None,
                      regime: str | None, seed: int
                      ) -> tuple[list[SleeveEvidence], WorldConfig]:
    ev = list(s.ev)
    cfg = s.cfg
    targets = [i for i, e in enumerate(ev) if sleeve is None or e.name == sleeve]
    if sleeve is not None and not targets:
        raise KeyError(f"no sleeve named {sleeve!r} in the snapshot")
    rng = np.random.default_rng(seed)
    for i in targets:
        e = ev[i]
        if channel == "mean":
            ev[i] = _shift_mean(e, size)
        elif channel == "volatility":
            ev[i] = _scale_vol(e, size)
        elif channel == "noise":
            ev[i] = _add_noise(e, size, rng)
        elif channel == "decay":
            ev[i] = dataclasses.replace(
                e, decay_prob_i=min(1.0, max(0.0, decay_prob_of(e, cfg) + size)))
        elif channel == "cost":
            ev[i] = dataclasses.replace(
                e, cost_bias_r=max(0.0, float(e.cost_bias_r or 0.0) + size))
        elif channel == "dependence":
            ev[i] = _add_common_factor(e, size)
    if channel == "regime":
        probs = dict(cfg.regime_probs)
        if not probs:
            raise ValueError("snapshot carries no regime_probs to perturb")
        reg = regime if regime is not None else next(iter(probs))
        if reg not in probs:
            raise KeyError(f"regime {reg!r} not in {sorted(probs)}")
        tot = sum(max(0.0, float(v)) for v in probs.values()) or 1.0
        frac = min(max(size, 0.0), 1.0)
        cfg = dataclasses.replace(cfg, regime_probs=tuple(
            (k, (1.0 - frac) * max(0.0, float(v)) / tot + (frac if k == reg else 0.0))
            for k, v in cfg.regime_probs))
    elif channel == "crisis":
        cfg = dataclasses.replace(
            cfg, crisis_common_share=min(1.0, max(0.0, cfg.crisis_common_share + size)),
            crisis_common_share_by_sleeve=tuple(
                (k, min(1.0, max(0.0, float(v) + size)))
                for k, v in cfg.crisis_common_share_by_sleeve))
    return ev, cfg


def perturb(snapshot: Snapshot, channel: str, size: float, *, sleeve: str | None = None,
            regime: str | None = None, seed: int = 20261006) -> dict[str, Any]:
    """Move ONE input channel by `size` (units in `CHANNELS`) and return the decision delta.

    Both books are solved on worlds re-drawn from `cfg.seed`, so they share random numbers and
    differ only by the channel. `sleeve` restricts a per-sleeve channel to one sleeve (None: all
    of them). `direction_ok` checks the economically expected sign on that sleeve's heat (or on
    total heat for a book-wide move) to within `MATERIAL_TURNOVER`; `moved` says the decision
    actually changed by more than that. `frozen_worlds_reproduce` says whether the frozen worlds
    are what the frozen evidence draws -- False when the pass reused a cached population, which
    is legitimate but means the deltas are measured against a re-drawn baseline.
    """
    if channel not in CHANNELS:
        raise KeyError(f"unknown channel {channel!r}; known: {sorted(CHANNELS)}")
    w0, base = _redrawn_base(snapshot)
    ev1, cfg1 = _perturbed_inputs(snapshot, channel, float(size), sleeve, regime, seed)
    w1 = sample_worlds(ev1, cfg1)
    new = _solve(ev1, cfg1, w1, snapshot.solve_kwargs)
    names = [e.name for e in snapshot.ev]
    per = {n: float(new.heat.get(n, 0.0)) - float(base.heat.get(n, 0.0)) for n in names}
    expected = CHANNELS[channel][2]
    total_delta = float(new.total_heat) - float(base.total_heat)
    focus = per[sleeve] if sleeve is not None else total_delta
    l1 = _l1(base.heat, new.heat)
    direction_ok: bool | None
    if expected is None:
        direction_ok = None
    elif expected == 0:
        direction_ok = bool(l1 <= MATERIAL_TURNOVER)
    else:
        direction_ok = bool(expected * focus >= -MATERIAL_TURNOVER)
    return {
        "channel": channel,
        "input": CHANNELS[channel][0],
        "unit": CHANNELS[channel][1],
        "size": float(size),
        "sleeve": sleeve,
        "regime": regime,
        "expected_sign": expected,
        "heat_l1": l1,
        "total_heat_before": float(base.total_heat),
        "total_heat_after": float(new.total_heat),
        "total_heat_delta": total_delta,
        "per_sleeve_delta": per,
        "focus_delta": float(focus),
        "moved": bool(l1 > MATERIAL_TURNOVER),
        "direction_ok": direction_ok,
        "score_before": float(base.robust_score),
        "score_after": float(new.robust_score),
        #: A move inside the base solve's own certificate band is a move the solver could not
        #: tell from staying put: turnover there is churn, whatever its size.
        "score_band": _score_band(dataclasses.asdict(base)),
        "frozen_worlds_reproduce": bool(
            w0.r.shape == snapshot.worlds.r.shape
            and np.array_equal(w0.r, snapshot.worlds.r)),
    }


# --------------------------------------------------------------------------------- missingness

#: The fraction of a sleeve's most recent days blanked by the STALE case: its feed stopped.
STALE_FRACTION = 0.25


def _missing_variants(s: Snapshot, i: int) -> list[tuple[str, list[SleeveEvidence], WorldConfig,
                                                         bool]]:
    """(input, evidence, cfg, applicable) for each critical input made missing on sleeve `i`.

    `applicable` is False when the frozen value was already absent, so the case is vacuous and
    is reported as such rather than counted as a pass.
    """
    e = s.ev[i]
    out: list[tuple[str, list[SleeveEvidence], WorldConfig, bool]] = []

    def _with(e2: SleeveEvidence) -> list[SleeveEvidence]:
        ev = list(s.ev)
        ev[i] = e2
        return ev

    a = np.array(e.daily_r, dtype=float)
    fin = np.flatnonzero(np.isfinite(a))
    stale = a.copy()
    k = max(1, round(STALE_FRACTION * fin.size))
    stale[fin[-k:]] = np.nan
    out.append(("daily_r_stale", _with(dataclasses.replace(e, daily_r=stale)), s.cfg,
                fin.size > 0))
    out.append(("daily_r_missing", _with(dataclasses.replace(e, daily_r=np.full_like(a, np.nan))),
                s.cfg, fin.size > 0))
    out.append(("cost_r", _with(dataclasses.replace(e, cost_r=float("nan"))), s.cfg, True))
    out.append(("cost_bias_r", _with(dataclasses.replace(e, cost_bias_r=float("nan"))), s.cfg,
                float(e.cost_bias_r or 0.0) > 0.0))
    out.append(("decay_prob_i", _with(dataclasses.replace(e, decay_prob_i=float("nan"))), s.cfg,
                e.decay_prob_i is not None))
    mw = np.asarray(e.macro_w, dtype=float)
    out.append(("macro_w", _with(dataclasses.replace(e, macro_w=np.full_like(mw, np.nan))),
                s.cfg, mw.size > 0))
    fl = tuple(e.factor_load)
    out.append(("factor_load", _with(dataclasses.replace(
        e, factor_load=tuple(float("nan") for _ in fl))), s.cfg, len(fl) > 0))
    rp = s.cfg.regime_probs
    out.append(("regime_probs", list(s.ev), dataclasses.replace(
        s.cfg, regime_probs=tuple((k2, float("nan")) for k2, _ in rp)), len(rp) > 0))
    return out


def missing_is_not_zero(snapshot: Snapshot, *, sleeve: str | None = None) -> dict[str, Any]:
    """Make each critical input missing (NaN, or a stale tail) and check heat does not RISE.

    MISSING IS NOT A FAVOURABLE ZERO (ARCH-13, ARCH-19). A cost nobody measured is not a free
    fill, a decay probability that failed to parse is not "this edge cannot break", and a feed
    that stopped is not a quiet market. For each case the sleeve's heat and the book's total heat
    are compared with the re-drawn frozen decision; either rising by more than
    `MATERIAL_TURNOVER` is a violation. A solve that RAISES on the missing input is safe -- loud
    refusal is the opposite of silent authorisation -- and is reported with its error.

    `sleeve` defaults to the sleeve the frozen decision funded most, which is where a favourable
    zero would buy the most risk. Book-wide inputs (`regime_probs`) are judged on total heat.
    """
    _w0, base = _redrawn_base(snapshot)
    names = [e.name for e in snapshot.ev]
    if sleeve is None:
        sleeve = max(names, key=lambda n: float(base.heat.get(n, 0.0)))
    if sleeve not in names:
        raise KeyError(f"no sleeve named {sleeve!r} in the snapshot")
    i = names.index(sleeve)
    rows: list[dict[str, Any]] = []
    for inp, ev1, cfg1, applicable in _missing_variants(snapshot, i):
        row: dict[str, Any] = {"input": inp, "sleeve": sleeve, "applicable": applicable,
                               "heat_before": float(base.heat.get(sleeve, 0.0)),
                               "total_before": float(base.total_heat)}
        try:
            with np.errstate(all="ignore"):
                w1 = sample_worlds(ev1, cfg1)
                new = _solve(ev1, cfg1, w1, snapshot.solve_kwargs)
        except (ValueError, FloatingPointError, ZeroDivisionError) as exc:
            row.update(refused=f"{type(exc).__name__}: {exc}", raised_heat=False)
            rows.append(row)
            continue
        h_after = float(new.heat.get(sleeve, 0.0))
        book_wide = inp == "regime_probs"
        raised = (not book_wide and h_after > row["heat_before"] + MATERIAL_TURNOVER) or \
            float(new.total_heat) > row["total_before"] + MATERIAL_TURNOVER
        row.update(heat_after=h_after, total_after=float(new.total_heat), refused=None,
                   raised_heat=bool(raised))
        rows.append(row)
    violations = [r["input"] for r in rows if r["applicable"] and r["raised_heat"]]
    return {"sleeve": sleeve, "rows": rows, "violations": violations,
            "ok": not violations, "tolerance": MATERIAL_TURNOVER}
