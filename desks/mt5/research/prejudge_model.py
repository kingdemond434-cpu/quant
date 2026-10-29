"""THE LEARNED PRE-JUDGE: P(survive) for a never-judged cell, spent on QUEUE ORDER, nothing else.

    python research/prejudge_model.py --train   # hourly leg `prejudge_model`: refit (<= hourly)
    python research/prejudge_model.py --train --force

WHAT IT IS (principal, 2026-10-13). "Train a model on P(passes each gate | cell metadata + cheap
diagnostics). Use something boring and fast ... The surrogate does NOT permanently reject
hypotheses. It controls queue priority. Keep a random exploration quota so weird cells can still
surprise you." So: a scikit-learn HistGradientBoostingClassifier over the gate verdict ledger
(`data/hypotheses/gate_verdict_ledger.jsonl`, one row per judged cell), a pure-Python rate-table
fallback when sklearn or the evidence is missing, and one effect on the docket:

    priority = P(survive) x ExpectedValue x Novelty x Orthogonality x InformationGain / ComputeCost

and, inside each family, the NEVER-JUDGED rows strictly below the family's `PERCENTILE` of
priority get `prejudge.flags += ["surrogate_low_priority"]` -- except a seeded random
`EXPLORATION_QUOTA` of them, which keep no flag.

WHY A FLAG IS THE WHOLE LEVER, AND WHY IT CAN ONLY REORDER. The sealed judge
(`scripts/external_gauntlet.py`) folds `bool(prejudge.flags)` into `prejudge_flagged` and uses it
as the FOURTH key of its stable sort -- after never-judged-first, chart rank and the CEO's
families -- and nowhere else; `allocate_by_yield` then trims each family's TAIL, so a flagged
row is reached after its family's unflagged rows of the same tier. `libs/tiers/prejudge_screen.
demote_flagged` (reused below, never restated) moves flagged rows behind their clean siblings
inside the family's own docket slots. No consumer of `prejudge.flags` rejects, drops, charges a
trial or touches a gate (`tests/test_prejudge_model.py` pins the docket permutation). A row
flagged this hour is un-flagged next hour if the model changes its mind: `strip_stale` removes
this module's flag from every row before anything reads the docket's order.

WHAT IS MEASURED AND WHAT IS NOT (L1.28a: an unmeasured term is 1.0 and NAMED, never faked).
Training must use features a never-judged row can also produce, so every feature is derived from
the judge's own cell identity (`<sym>[@TF].<family>.p=<digest>`) plus the broker registry:
family, symbol, asset class (`universe_policy.asset_class_of`), chart, the out-of-fold pass
rates of those keys and their crosses (family x chart, family x asset class, family x symbol --
the "similarity to past failures"), the evidence depth of each, and the stored family posterior
(`libs/research/research_priors`). Session, source, mechanism and the cheap backtest diagnostics
are NOT on the ledger row, so they are not features; `FEATURE_TERMS` says so in the report.

FAIL OPEN, NEVER CLOSED. No model, no ledger, no sklearn, an unreadable seen-cell index, a
corrupt pickle: each degrades to the rate tables, then to the family prior, then to NO FLAG AT
ALL -- the docket keeps the order it already had. Equal priorities are never split by this
module (only rows strictly below the cutoff are flagged), so a model with nothing to say says
nothing.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import pickle
import random
import sys
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HYP = DESK / "data" / "hypotheses"
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
SEEN_CELLS = HYP / "gauntlet_seen_cells.json"
MODEL_DIR = DESK / "data" / "prejudge_model"          # gitignored: box-local learned state
MODEL_PATH = MODEL_DIR / "model.pkl"
SCHEMA_PATH = MODEL_DIR / "model.json"
REPORT = DESK / "reports" / "PREJUDGE.json"

FLAG = "surrogate_low_priority"
SCHEMA = "prejudge_model/1"
UNMEASURED = "UNMEASURED"

#: Within each family, never-judged rows strictly below this percentile of priority are flagged.
PERCENTILE = float(os.environ.get("PREJUDGE_PERCENTILE", "50"))
#: Share of the would-be-flagged rows (per family, per data-day) left unflagged at random.
EXPLORATION_QUOTA = float(os.environ.get("PREJUDGE_EXPLORATION_QUOTA", "0.10"))
#: A family with fewer never-judged rows than this is left alone -- a median of three is noise.
MIN_FAMILY_ROWS = 4
#: NO FLAG OUTLIVES THIS (audit of #330). A flagged row sorts behind every clean row of its
#: family, so under a backlog that never empties it would never be reached: the audit's sim at
#: 100/h inflow against 60/h capacity left two symbols with cells waiting the whole 336h while
#: FIFO kept every symbol under 135h. A row first seen longer ago than this is never flagged, so it
#: sorts with its family's clean rows -- in the judge's own order, which has NO age key (audit S1:
#: a 500 h row sorted behind 26 rows 1 h old), so the bound is on how long a flag can delay a row,
#: not a promise of oldest-first. Unknown age is treated as old.
FLAG_MAX_AGE_H = float(os.environ.get("PREJUDGE_FLAG_MAX_AGE_H", "72"))
#: Training sample cap (stratified by family x label, inverse-inclusion weighted).
MAX_TRAIN_ROWS = int(os.environ.get("PREJUDGE_MAX_TRAIN_ROWS", "200000"))
PER_KEY_CAP = max(500, MAX_TRAIN_ROWS // 50)
#: Below these the boosted model is not fitted and the rate tables answer alone.
MIN_TRAIN, MIN_CLASS = 200, 10
#: Refit at most this often (audit S5 of 680f2856e). The model persists and a flag lives at most
#: FLAG_MAX_AGE_H, so an hourly refit bought nothing; 3000 s sat below the hourly cadence and refit
#: every pass. A pass inside the window reuses the persisted model and reads nothing.
REFIT_MIN_S = 6 * 3600
#: Pseudo-counts of the parent rate mixed into every table rate.
SMOOTH = 20.0
#: Out-of-fold folds for the rate features the booster is trained on.
N_FOLDS = 5
TF_ORDER = {"M1": 0, "M5": 1, "M15": 2, "M30": 3, "H1": 4, "H4": 5, "D1": 6}
FEATURES = ("family_rate", "symbol_rate", "asset_rate", "tf_rate", "fam_tf_rate",
            "fam_asset_rate", "fam_sym_rate", "log_n_family", "log_n_fam_sym", "tf_ordinal",
            "family_prior")

#: The principal's input list, and what this module can honestly feed the model today.
FEATURE_TERMS: dict[str, str] = {
    "family": "MEASURED (cell id; out-of-fold family pass rate)",
    "asset_class": "MEASURED (universe_policy.asset_class_of)",
    "timeframe": "MEASURED (cell id @TF)",
    "historical_family_pass_rate": "MEASURED (ledger rates + research_priors family posterior)",
    "novelty": "MEASURED (judged depth of the family x symbol neighbourhood)",
    "similarity_to_past_failures": "MEASURED (out-of-fold family x symbol / chart / class rates)",
    "session": UNMEASURED + " (ledger rows carry only a params digest)",
    "source": UNMEASURED + " (not on the gate ledger row)",
    "mechanism": UNMEASURED + " (not on the gate ledger row)",
    "source_prior": UNMEASURED + " (not on the gate ledger row)",
    "trade_count": UNMEASURED + " (no pre-judge diagnostic on never-judged rows)",
    "cheap_expectancy": UNMEASURED + " (no pre-judge diagnostic on never-judged rows)",
    "cheap_t_stat": UNMEASURED + " (no pre-judge diagnostic on never-judged rows)",
    "turnover": UNMEASURED + " (no pre-judge diagnostic on never-judged rows)",
    "rough_costs": UNMEASURED + " (no pre-judge diagnostic on never-judged rows)",
    "parameter_stability": UNMEASURED + " (no pre-judge diagnostic on never-judged rows)",
}


# ------------------------------------------------------------------------------------------------
# identity and cheap per-cell keys
# ------------------------------------------------------------------------------------------------

def _tf_of(cell: str) -> str:
    head = str(cell or "").split(".", 1)[0]
    return head.split("@", 1)[1].upper() if "@" in head else "H1"


def _sym_of(cell: str) -> str:
    return str(cell or "").split(".", 1)[0].split("@", 1)[0]


def _fam_of(cell: str) -> str:
    parts = str(cell or "").split(".")
    return parts[1] if len(parts) >= 2 else ""


@lru_cache(maxsize=4096)
def _asset(sym: str) -> str:
    try:
        from research.universe_policy import asset_class_of
        return asset_class_of(sym) or "?"
    except Exception:
        return "?"


def row_cell(row: Mapping[str, Any]) -> str | None:
    """The judge's own identity for a docket row (`frontier_identity.docket_cell_id`)."""
    try:
        from research.frontier_identity import docket_cell_id
        return str(docket_cell_id(dict(row)))
    except Exception:
        return None


def _keys(fam: str, sym: str, tf: str, ac: str) -> dict[str, str]:
    return {"f": fam, "s": sym, "a": ac, "t": tf, "ft": f"{fam}|{tf}", "fa": f"{fam}|{ac}",
            "fs": f"{fam}|{sym}"}


# ------------------------------------------------------------------------------------------------
# rate tables (also the pure-Python fallback)
# ------------------------------------------------------------------------------------------------

class Tables:
    """[n, passes] per key family; rates smoothed toward their parent rate."""

    def __init__(self, counts: dict[str, list[int]] | None = None) -> None:
        self.c: dict[str, list[int]] = counts or {}

    def add(self, keys: Mapping[str, str], y: int, sign: int = 1) -> None:
        g = self.c.setdefault("g:", [0, 0])
        g[0] += sign
        g[1] += sign * y
        for kind, k in keys.items():
            v = self.c.setdefault(f"{kind}:{k}", [0, 0])
            v[0] += sign
            v[1] += sign * y

    def n_k(self, kind: str, key: str) -> tuple[int, int]:
        n, k = self.c.get(f"{kind}:{key}", (0, 0))
        return max(n, 0), max(k, 0)

    def rate(self, kind: str, key: str, parent: float) -> float:
        n, k = self.n_k(kind, key)
        return (k + SMOOTH * parent) / (n + SMOOTH)

    def global_rate(self) -> float | None:
        n, k = self.n_k("g", "")
        return (k + 1.0) / (n + 2.0) if n > 0 else None

    def copy(self) -> Tables:
        return Tables({k: list(v) for k, v in self.c.items()})

    def features(self, keys: Mapping[str, str], family_prior: float) -> list[float]:
        g = self.global_rate()
        g = family_prior if g is None else g
        fr = self.rate("f", keys["f"], g)
        return [fr,
                self.rate("s", keys["s"], g),
                self.rate("a", keys["a"], g),
                self.rate("t", keys["t"], g),
                self.rate("ft", keys["ft"], fr),
                self.rate("fa", keys["fa"], fr),
                self.rate("fs", keys["fs"], fr),
                math.log1p(self.n_k("f", keys["f"])[0]),
                math.log1p(self.n_k("fs", keys["fs"])[0]),
                float(TF_ORDER.get(keys["t"], 4)),
                family_prior]

    def fallback_p(self, keys: Mapping[str, str], family_prior: float) -> float:
        """No model: the family x symbol and family x chart rates, each shrunk to the family."""
        f = self.features(keys, family_prior)
        return 0.5 * (f[4] + f[6]) if self.c else family_prior


@lru_cache(maxsize=1024)
def family_prior(fam: str) -> float:
    """The stored family posterior mean (`research_priors`), Beta(1,1)=0.5 when unknown."""
    try:
        from libs.research.research_priors import prior_for
        return float(prior_for("family", fam).mean)
    except Exception:
        return 0.5


# ------------------------------------------------------------------------------------------------
# training
# ------------------------------------------------------------------------------------------------

#: Gates read on the HELD-OUT window (audit S4 of 680f2856e). A label that knew their outcome would
#: make which cells get judged first a selection on the holdout, uncharged in DSR. The label is
#: therefore the PRE-holdout outcome: a cell that failed only these is labelled as passing.
HOLDOUT_GATES = frozenset({"lockbox"})


def _label(row: Mapping[str, Any]) -> int | None:
    """1 passed every development gate, 0 failed one; None for UNKNOWN / NOT_RUN (not a failure)
    or when the row cannot say whether anything but a holdout gate failed."""
    if str(row.get("downstream_status") or "").startswith("NOT_RUN"):
        return None
    if row.get("passed") is True or str(row.get("passed")).lower() == "true":
        return 1
    term = str(row.get("terminal_gate") or "")
    if term in ("", "UNKNOWN"):
        return None
    failed = row.get("failed_gates")
    if isinstance(failed, list) and failed:
        return 0 if any(str(g) not in HOLDOUT_GATES for g in failed) else 1
    # No failed-gate list: the terminal gate is the FIRST failure, so a holdout gate there says
    # nothing about the development gates after it.
    return None if term in HOLDOUT_GATES else 0


#: THE STREAM RESUMES (audit MF1 of 680f2856e). The refit used to stream the whole verdict ledger
#: every time, with no budget and nothing saved until the end; on the box that is the same file
#: whose full read made JUDGING_RATE overrun, and a leg killed at its cap would start from byte 0
#: every hour, forever. The tables, the reservoir, its RNG and the byte offset are saved here, so a
#: pass reads only what was appended (whole lines only) and a pass cut by its deadline resumes.
#: A ledger whose head or last-read bytes changed, or that shrank, is read again from the start.
STREAM_STATE = MODEL_DIR / "stream_state.pkl"
STREAM_STATE_V = 1
STREAM_HEAD_BYTES = 4096
_STREAM_CHECK_EVERY = 4096
#: Share of the leg's cap (`QUANT_LEG_BUDGET_S`) the stream may take; the fit needs the rest.
STREAM_BUDGET_SHARE = 0.5
#: The fit runs only when the time left covers this multiple of the last measured fit.
FIT_MARGIN = 1.25


def _bytes_hash(path: Path, start: int, n: int) -> str:
    with path.open("rb") as fh:
        fh.seek(max(0, start))
        return hashlib.blake2b(fh.read(max(0, n)), digest_size=16).hexdigest()


def _load_stream_state(path: Path, ledger: Path, size: int) -> dict[str, Any] | None:
    """The saved stream, or None when the ledger is not the one it read (head or last-read bytes
    changed, or it shrank) or the state cannot be read."""
    try:
        with path.open("rb") as fh:
            st = pickle.load(fh)  # noqa: S301 -- written only by this module, box-local
        if not isinstance(st, dict) or st.get("v") != STREAM_STATE_V:
            return None
        off, hl = int(st["offset"]), int(st["head_len"])
        tl = min(off, STREAM_HEAD_BYTES)
        if (off > size or st.get("ledger") != str(ledger)
                or _bytes_hash(ledger, 0, hl) != st["head"]
                or _bytes_hash(ledger, off - tl, tl) != st["tail"]):
            return None
        return st
    except Exception:
        return None


def stream_ledger(path: Path, seed: int = 0, *, state_path: Path | None = None,
                  deadline: float | None = None) -> dict[str, Any]:
    """One pass over the ledger, bounded memory: full-population tables plus a stratified
    reservoir (family x label, `PER_KEY_CAP` each) with its inclusion weights.

    With `state_path` the pass resumes from the saved state and saves it again (whole lines
    only); `deadline` (a `time.monotonic()` instant) stops it early with `complete` False and
    its progress kept. Resumed or not, the tables and the reservoir are those of one pass over
    every line, in file order."""
    tables = Tables()
    res: dict[tuple[str, int], list[tuple[str, str, str, str, int]]] = {}
    seen: dict[tuple[str, int], int] = {}
    gates: dict[str, dict[str, int]] = {}
    rng = random.Random(seed)  # noqa: S311 -- sampling, never a secret
    read = used = 0
    offset = 0
    try:
        size = path.stat().st_size
        fh = path.open("rb")
    except OSError:
        return {"tables": tables, "sample": [], "read": 0, "used": 0, "gates": {},
                "complete": True, "resumed": False}
    st = _load_stream_state(state_path, path, size) if state_path is not None else None
    if st is not None:
        tables = Tables(st["tables"])
        res, seen, gates = st["res"], st["seen"], st["gates"]
        rng.setstate(st["rng"])
        read, used, offset = int(st["read"]), int(st["used"]), int(st["offset"])
    complete = True
    with fh:
        fh.seek(offset)
        n_line = 0
        while True:
            if (deadline is not None and n_line % _STREAM_CHECK_EVERY == 0
                    and time.monotonic() > deadline):
                complete = False
                break
            raw = fh.readline()
            if not raw or not raw.endswith(b"\n"):
                break                       # EOF, or a row the writer is still appending
            n_line += 1
            offset += len(raw)
            read += 1
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            y = _label(row)
            cell = str(row.get("cell") or "")
            if y is None or not cell:
                continue
            fam = str(row.get("family") or _fam_of(cell))
            sym = str(row.get("sym") or _sym_of(cell))
            tf = _tf_of(cell)
            ac = _asset(sym)
            tables.add(_keys(fam, sym, tf, ac), y)
            gh = gates.setdefault(fam, {})
            gate = "PASSED" if y else str(row.get("terminal_gate"))
            gh[gate] = gh.get(gate, 0) + 1
            used += 1
            key = (fam, y)
            seen[key] = seen.get(key, 0) + 1
            bucket = res.setdefault(key, [])
            item = (cell, fam, sym, tf, y)
            if len(bucket) < PER_KEY_CAP:
                bucket.append(item)
            else:
                j = rng.randrange(seen[key])
                if j < PER_KEY_CAP:
                    bucket[j] = item
    if state_path is not None:
        try:
            hl = min(offset, STREAM_HEAD_BYTES)
            snap = {"v": STREAM_STATE_V, "ledger": str(path), "offset": offset,
                    "head_len": hl, "head": _bytes_hash(path, 0, hl),
                    "tail": _bytes_hash(path, offset - hl, hl),
                    "tables": tables.c, "res": res, "seen": seen, "gates": gates,
                    "rng": rng.getstate(), "read": read, "used": used}
            state_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_bytes(state_path, pickle.dumps(snap))
        except OSError:
            pass                            # the next pass reads from the last saved offset
    # The state was saved BEFORE the shuffle below draws from `rng`, so a resumed pass and an
    # uninterrupted one make the same draws.
    sample: list[tuple[str, str, str, str, int, float]] = []
    for key, items in res.items():
        w = seen[key] / max(len(items), 1)
        sample.extend((*it, w) for it in items)
    if len(sample) > MAX_TRAIN_ROWS:
        rng.shuffle(sample)
        scale = len(sample) / MAX_TRAIN_ROWS
        sample = [(*s[:5], s[5] * scale) for s in sample[:MAX_TRAIN_ROWS]]
    sample.sort(key=lambda s: s[0])
    return {"tables": tables, "sample": sample, "read": read, "used": used, "gates": gates,
            "complete": complete, "resumed": st is not None, "offset": offset, "size": size}


def _holdout(cell: str) -> bool:
    return int(hashlib.sha256(cell.encode("utf-8")).hexdigest()[:8], 16) % 5 == 0


def _fold(cell: str) -> int:
    return int(hashlib.sha256(cell.encode("utf-8")).hexdigest()[8:16], 16) % N_FOLDS


def _matrix(sample: list[tuple[str, str, str, str, int, float]], tables: Tables
            ) -> tuple[list[list[float]], list[int], list[float]]:
    """OUT-OF-FOLD rate features: a row is encoded by tables its own fold's labels have left.

    Leave-one-out encoding was tried first and is a known trap: removing a row's own label shifts
    its rate in the direction opposite to that label, so a booster learns the shift and inverts
    on rows that were never in the tables (measured on the synthetic ledger: holdout AUC 0.50).
    Fold-level removal moves every row of a fold together, so no row can see its own label."""
    xs, ys, ws = [], [], []
    for f in range(N_FOLDS):
        part = [s for s in sample if _fold(s[0]) == f]
        if not part:
            continue
        t = tables.copy()
        for _cell, fam, sym, tf, y, _w in part:
            t.add(_keys(fam, sym, tf, _asset(sym)), y, sign=-1)
        for _cell, fam, sym, tf, y, w in part:
            xs.append(t.features(_keys(fam, sym, tf, _asset(sym)), family_prior(fam)))
            ys.append(y)
            ws.append(w)
    return xs, ys, ws


def _one_thread() -> Any:
    """ONE OpenMP THREAD (audit of #330): unpinned, the booster took 170.5s on 50k rows against
    5.5s pinned, and 536s on 300k against the 600s leg budget with the box at 98.7% CPU -- the
    judge never takes CPU from the miners."""
    try:
        from threadpoolctl import threadpool_limits
        return threadpool_limits(limits=1)
    except Exception:
        return contextlib.nullcontext()


def _fit(xs: list[list[float]], ys: list[int], ws: list[float]) -> Any:
    from sklearn.ensemble import HistGradientBoostingClassifier
    clf = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.1, max_leaf_nodes=31,
                                         l2_regularization=1.0, random_state=0)
    with _one_thread():
        clf.fit(xs, ys, sample_weight=ws)
    return clf


def leg_cap_s(env: Mapping[str, str] | None = None) -> float | None:
    """The hourly cycle's SIGKILL for this leg (`QUANT_LEG_BUDGET_S`), or None run by hand."""
    try:
        cap = float((os.environ if env is None else env).get("QUANT_LEG_BUDGET_S") or 0.0)
    except (TypeError, ValueError):
        return None
    return cap if cap > 0 else None


def train(*, ledger: Path | None = None, model_dir: Path | None = None, force: bool = False,
          now: float | None = None) -> dict[str, Any]:
    """Refit (at most every `REFIT_MIN_S`) and persist model + schema. Never raises."""
    mdir = model_dir or MODEL_DIR
    schema_path, model_path = mdir / SCHEMA_PATH.name, mdir / MODEL_PATH.name
    t0 = time.time() if now is None else now
    prev = _read_json(schema_path)
    fresh = isinstance(prev, dict) and t0 - float(prev.get("trained_ts") or 0) < REFIT_MIN_S
    if not force and fresh and isinstance(prev, dict):
        return {**prev, "refit": False}
    m0 = time.monotonic()
    cap = leg_cap_s()
    st = stream_ledger(ledger or GATE_LEDGER, state_path=mdir / STREAM_STATE.name,
                       deadline=None if cap is None else m0 + STREAM_BUDGET_SHARE * cap)
    keep = {**prev, "refit": False} if isinstance(prev, dict) else {"schema": SCHEMA,
                                                                     "refit": False}
    if not st["complete"]:
        # PROGRESS SAVED, NOTHING FITTED: the model in hand keeps answering, and the next pass
        # resumes the stream where this one stopped.
        return {**keep, "status": keep.get("status") or "NO_EVIDENCE",
                "stream": f"CATCHING_UP: byte {st['offset']:,} of {st['size']:,}"}
    fit_s = float(prev.get("fit_seconds") or 0.0) if isinstance(prev, dict) else 0.0
    if cap is not None and fit_s and cap - (time.monotonic() - m0) < FIT_MARGIN * fit_s:
        return {**keep, "status": keep.get("status") or "NO_EVIDENCE",
                "stream": (f"FIT_DEFERRED: {cap - (time.monotonic() - m0):.0f} s left against a "
                           f"last fit of {fit_s:.0f} s; the stream is current, so the next "
                           "pass has the time")}
    tables: Tables = st["tables"]
    sample = st["sample"]
    ys_all = [s[4] for s in sample]
    n_pos, n_neg = sum(ys_all), len(ys_all) - sum(ys_all)
    doc: dict[str, Any] = {
        "schema": SCHEMA, "trained_ts": t0,
        "trained_at": datetime.fromtimestamp(t0, tz=UTC).isoformat(timespec="seconds"),
        "ledger": str(ledger or GATE_LEDGER), "ledger_rows_read": st["read"],
        "ledger_rows_labelled": st["used"], "n_train": len(sample), "n_pos": n_pos,
        "n_neg": n_neg, "features": list(FEATURES), "tables": tables.c,
        "terminal_gates_by_family": {f: dict(sorted(g.items(), key=lambda kv: -kv[1])[:6])
                                     for f, g in st["gates"].items()},
        "auc_holdout": UNMEASURED, "model_sha256": None, "refit": True,
    }
    if len(sample) < MIN_TRAIN or n_pos < MIN_CLASS or n_neg < MIN_CLASS:
        doc["status"] = "PRIOR_FALLBACK" if st["used"] else "NO_EVIDENCE"
        doc["why"] = (f"{len(sample)} labelled rows, {n_pos} passes, {n_neg} failures -- below "
                      f"{MIN_TRAIN}/{MIN_CLASS}/{MIN_CLASS}; rate tables answer alone")
    else:
        try:
            hold = [s for s in sample if _holdout(s[0])]
            fit_rows = [s for s in sample if not _holdout(s[0])]
            if hold and fit_rows and 0 < sum(s[4] for s in hold) < len(hold):
                t_fit = tables.copy()
                for _cell, fam, sym, tf, y, _w in hold:      # holdout labels leave the tables
                    t_fit.add(_keys(fam, sym, tf, _asset(sym)), y, sign=-1)
                xf, yf, wf = _matrix(fit_rows, t_fit)
                if 0 < sum(yf) < len(yf):
                    from sklearn.metrics import roc_auc_score
                    clf = _fit(xf, yf, wf)
                    xh = [t_fit.features(_keys(f, s, t, _asset(s)), family_prior(f))
                          for _c, f, s, t, _y, _w in hold]
                    ph = clf.predict_proba(xh)[:, 1]
                    doc["auc_holdout"] = round(float(roc_auc_score(
                        [h[4] for h in hold], ph, sample_weight=[h[5] for h in hold])), 4)
                    doc["n_holdout"] = len(hold)
            f0 = time.monotonic()
            xs, ys, ws = _matrix(sample, tables)
            clf = _fit(xs, ys, ws)
            doc["fit_seconds"] = round(time.monotonic() - f0, 1)
            blob = pickle.dumps(clf)
            mdir.mkdir(parents=True, exist_ok=True)
            _atomic_bytes(model_path, blob)
            doc["model_sha256"] = hashlib.sha256(blob).hexdigest()
            doc["status"] = "MODEL"
        except Exception as exc:
            doc["status"] = "PRIOR_FALLBACK"
            doc["why"] = f"model fit failed ({type(exc).__name__}: {exc}); rate tables answer"
    try:
        mdir.mkdir(parents=True, exist_ok=True)
        _atomic_bytes(schema_path, json.dumps(doc, default=str).encode("utf-8"))
    except OSError as exc:
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


# ------------------------------------------------------------------------------------------------
# scoring
# ------------------------------------------------------------------------------------------------

class Scorer:
    """P(survive) from the persisted model, else the rate tables, else the family prior."""

    def __init__(self, schema: Mapping[str, Any] | None, model: Any = None) -> None:
        self.schema = dict(schema or {})
        self.tables = Tables(self.schema.get("tables") or {})
        self.model = model
        self.status = ("MODEL" if model is not None
                       else ("PRIOR_FALLBACK" if self.tables.c else "FAMILY_PRIOR"))

    @classmethod
    def load(cls, model_dir: Path | None = None) -> Scorer:
        mdir = model_dir or MODEL_DIR
        schema = _read_json(mdir / SCHEMA_PATH.name)
        if not isinstance(schema, dict) or schema.get("schema") != SCHEMA:
            return cls(None)
        model = None
        want = schema.get("model_sha256")
        if want:
            try:
                blob = (mdir / MODEL_PATH.name).read_bytes()
                auc = schema.get("auc_holdout")
                # A MODEL THAT NEVER BEAT A COIN ON HELD-OUT CELLS ORDERS NOTHING (audit of #330):
                # UNMEASURED or <= 0.5 holdout AUC leaves the rate tables to answer.
                if not isinstance(auc, (int, float)) or float(auc) <= 0.5:
                    return cls(schema, None)
                if hashlib.sha256(blob).hexdigest() == want:
                    import sklearn  # noqa: F401 -- unpickling needs it; absent -> tables
                    model = pickle.loads(blob)  # noqa: S301 -- our artifact, hash-verified
            except Exception:
                model = None
        return cls(schema, model)

    def p_many(self, cells: list[str]) -> list[float]:
        keys = [_keys(_fam_of(c), _sym_of(c), _tf_of(c), _asset(_sym_of(c))) for c in cells]
        priors = [family_prior(k["f"]) for k in keys]
        if self.model is not None and cells:
            try:
                xs = [self.tables.features(k, fp) for k, fp in zip(keys, priors, strict=True)]
                with _one_thread():
                    probs = self.model.predict_proba(xs)[:, 1]
                return [float(v) for v in probs]
            except Exception:
                self.status = "PRIOR_FALLBACK (model predict failed)"
        return [self.tables.fallback_p(k, fp) for k, fp in zip(keys, priors, strict=True)]


def value_terms(tables: Tables) -> tuple[dict[str, Any], dict[str, str]]:
    """Per-family multipliers that exist on the desk today, and which ones do not."""
    status: dict[str, str] = {}
    ev: dict[str, float] = {}
    occ: dict[str, float] = {}
    try:
        from research.judge_coverage import family_breadth, family_value
        best, median = family_value()
        if best and median > 0:
            ev = {f: min(4.0, max(0.25, v / median)) for f, v in best.items()}
            status["expected_value"] = "MEASURED (reports/NET_EDGE.json, family / median, 0.25..4)"
        occ = family_breadth()
        if occ:
            status["orthogonality"] = "MEASURED (reports/EFFECTIVE_BREADTH.json, 1/(1+occupancy))"
    except Exception:
        pass
    status.setdefault("expected_value", UNMEASURED + " (NET_EDGE.json absent/empty) -> 1.0")
    status.setdefault("orthogonality", UNMEASURED + " (EFFECTIVE_BREADTH.json absent) -> 1.0")
    status["novelty"] = ("MEASURED (1 + 1/sqrt(1 + judged cells of this family x symbol))"
                         if tables.c else UNMEASURED + " (no ledger) -> 1.0")
    status["information_gain"] = ("MEASURED (1 + family Beta posterior sd / sd of Beta(1,1))"
                                  if tables.c else UNMEASURED + " (no ledger) -> 1.0")
    status["compute_cost"] = (UNMEASURED + " (no per-family build seconds are published) -> 1.0")
    return {"ev": ev, "occ": occ}, status


def priority(p: float, cell: str, tables: Tables, vt: Mapping[str, Any]) -> float:
    fam, sym = _fam_of(cell), _sym_of(cell)
    ev = float((vt.get("ev") or {}).get(fam, 1.0)) if vt.get("ev") else 1.0
    orth = 1.0 / (1.0 + float((vt.get("occ") or {}).get(fam, 0.0))) if vt.get("occ") else 1.0
    nov = ig = 1.0
    if tables.c:
        nov = 1.0 + 1.0 / math.sqrt(1.0 + tables.n_k("fs", f"{fam}|{sym}")[0])
        n, k = tables.n_k("f", fam)
        a, b = 1.0 + k, 1.0 + (n - k)
        sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1.0)))
        ig = 1.0 + sd / math.sqrt(1.0 / 12.0)
    cost = 1.0
    return max(p, 0.0) * ev * nov * orth * ig / cost


# ------------------------------------------------------------------------------------------------
# the docket effect
# ------------------------------------------------------------------------------------------------

def strip_stale(rows: list[dict[str, Any]]) -> int:
    """Remove this module's flag from every row (last hour's verdict never carries over)."""
    n = 0
    for r in rows:
        pj = r.get("prejudge")
        if not isinstance(pj, dict) or FLAG not in (pj.get("flags") or []):
            continue
        new = {k: v for k, v in pj.items() if k != "surrogate_p"}
        new["flags"] = [f for f in (pj.get("flags") or []) if f != FLAG]
        if not new["flags"] and set(new) <= {"flags", "by"}:
            del r["prejudge"]          # this module created the dict; leave no trace of it
        else:
            r["prejudge"] = new
        n += 1
    return n


def _seen_cells(path: Path) -> set[str] | None:
    doc = _read_json(path)
    return set(doc) if isinstance(doc, dict) else None


def _age_h(first_seen: Any, now: datetime) -> float:
    """Hours since the row was first seen; unknown or unparseable age is infinitely old."""
    try:
        seen = datetime.fromisoformat(str(first_seen).replace("Z", "+00:00"))
    except ValueError:
        return math.inf
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    return max(0.0, (now - seen).total_seconds() / 3600.0)


def _flag(r: dict[str, Any], p: float) -> None:
    pj = r.get("prejudge")
    if isinstance(pj, dict):
        new = dict(pj)
        new["flags"] = [*list(pj.get("flags") or []), FLAG]
    else:
        new = {"flags": [FLAG], "by": "prejudge_model"}
    new["surrogate_p"] = round(p, 6)
    r["prejudge"] = new


def _reorder(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Flagged rows behind their family's clean rows, in the family's own slots (reused)."""
    try:
        from libs.tiers import prejudge_screen as pj
        out, info = pj.demote_flagged(rows, {})
        return out, int(info.get("moved") or 0)
    except Exception:
        return rows, 0


def apply(rows: list[dict[str, Any]], *, now: datetime | None = None,
          scorer: Scorer | None = None, seen: set[str] | None = None,
          seen_path: Path | None = None, percentile: float | None = None,
          quota: float | None = None, report: Path | None = REPORT
          ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Flag the low-priority tail of each family's NEVER-JUDGED rows; return a permutation."""
    when = now or datetime.now(tz=UTC)
    pct = PERCENTILE if percentile is None else float(percentile)
    q = EXPLORATION_QUOTA if quota is None else float(quota)
    stale = strip_stale(rows)
    sc = scorer if scorer is not None else Scorer.load()
    judged = seen if seen is not None else _seen_cells(seen_path or SEEN_CELLS)
    summary: dict[str, Any] = {
        "at": when.isoformat(timespec="seconds"), "data_day": when.strftime("%Y-%m-%d"),
        "rows": len(rows), "stale_flags_removed": stale, "scorer": sc.status,
        "percentile": pct, "exploration_quota": q, "flagged": 0, "explored": 0,
        "candidates": 0, "judged_skipped": 0, "moved": 0, "families": {},
        "flag_max_age_h": FLAG_MAX_AGE_H, "aged_unflaggable": 0,
    }
    if judged is None:
        summary["status"] = "NOT_APPLIED: seen-cell index unreadable, never-judged unknown"
        _write_report(report, summary, sc)
        return rows, summary
    by_fam: dict[str, list[tuple[int, str]]] = {}
    for i, r in enumerate(rows):
        # AGE FIRST (audit S3): it is a string parse, and it rules out ~97% of the docket before
        # the cell id is hashed at all.
        if _age_h(r.get("first_seen"), when) > FLAG_MAX_AGE_H:
            summary["aged_unflaggable"] += 1          # waits as a clean row: no starvation
            continue
        cid = row_cell(r)
        if not cid:
            continue
        if cid in judged:
            summary["judged_skipped"] += 1
            continue
        by_fam.setdefault(str(r.get("family") or ""), []).append((i, cid))
    vt, term_status = value_terms(sc.tables)
    summary["terms"] = {"p_survive": f"MEASURED ({sc.status})", **term_status}
    for fam, members in sorted(by_fam.items()):
        summary["candidates"] += len(members)
        fam_doc = {"candidates": len(members), "flagged": 0, "explored": 0}
        summary["families"][fam] = fam_doc
        if len(members) < MIN_FAMILY_ROWS:
            continue
        ps = sc.p_many([c for _i, c in members])
        pr = [priority(p, c, sc.tables, vt) for p, (_i, c) in zip(ps, members, strict=True)]
        srt = sorted(pr)
        cut = srt[min(len(srt) - 1, max(0, math.floor(pct / 100.0 * len(srt))))]
        low = sorted((c, i, p) for p, v, (i, c) in zip(ps, pr, members, strict=True) if v < cut)
        if not low:
            continue
        # CEIL, never round (audit of #330): a family with four flagged rows still explores one.
        n_explore = min(len(low), math.ceil(len(low) * q)) if q > 0 else 0
        seed = int(hashlib.sha256(f"{summary['data_day']}|{fam}".encode()).hexdigest()[:16], 16)
        rng = random.Random(seed)  # noqa: S311 -- reproducible exploration, never a secret
        explore = set(rng.sample(range(len(low)), n_explore))
        for j, (_c, i, p) in enumerate(low):
            if j in explore:
                continue
            _flag(rows[i], p)
            fam_doc["flagged"] += 1
        fam_doc["explored"] = len(explore)
        summary["flagged"] += fam_doc["flagged"]
        summary["explored"] += len(explore)
    for fam_doc in summary["families"].values():
        fam_doc["flag_rate"] = round(fam_doc["flagged"] / max(fam_doc["candidates"], 1), 4)
    out, summary["moved"] = _reorder(rows)
    summary["status"] = "APPLIED"
    _write_report(report, summary, sc)
    return out, summary


# ------------------------------------------------------------------------------------------------
# io
# ------------------------------------------------------------------------------------------------

def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _model_section(schema: Mapping[str, Any]) -> dict[str, Any]:
    keep = ("status", "why", "trained_at", "ledger_rows_read", "ledger_rows_labelled", "n_train",
            "n_pos", "n_neg", "n_holdout", "auc_holdout", "model_sha256", "features",
            "terminal_gates_by_family", "refit")
    return {k: schema.get(k) for k in keep if k in schema}


def _write_report(path: Path | None, apply_doc: Mapping[str, Any] | None,
                  sc: Scorer | None = None, model_doc: Mapping[str, Any] | None = None) -> None:
    if path is None:
        return
    prev = _read_json(path)
    doc: dict[str, Any] = prev if isinstance(prev, dict) else {}
    doc.update({
        "schema": "prejudge_report/1",
        "rule": ("queue priority only: never-judged rows strictly below the family's "
                 f"{PERCENTILE:g}th priority percentile get prejudge.flags += [{FLAG!r}], "
                 f"minus a seeded {EXPLORATION_QUOTA:.0%} exploration quota; the sealed judge "
                 "sorts flagged rows behind unflagged ones of the same tier; nothing is dropped, "
                 "rejected or charged"),
        "priority": "P(survive) x EV x Novelty x Orthogonality x InformationGain / ComputeCost",
        "feature_terms": FEATURE_TERMS,
    })
    if model_doc is not None:
        doc["model"] = _model_section(model_doc)
        doc["model"]["auc_holdout"] = model_doc.get("auc_holdout", UNMEASURED)
    elif sc is not None and sc.schema:
        doc["model"] = {**_model_section(sc.schema), "loaded_as": sc.status}
    elif sc is not None:
        doc["model"] = {"status": sc.status, "auc_holdout": UNMEASURED, "n_train": 0}
    if apply_doc is not None:
        doc["apply"] = dict(apply_doc)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_bytes(path, json.dumps(doc, indent=1, default=str).encode("utf-8"))
    except OSError:
        pass


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--train", action="store_true", help="refit the model (at most hourly)")
    ap.add_argument("--force", action="store_true", help="refit even inside the refit window")
    a = ap.parse_args(list(argv) if argv is not None else None)
    if not a.train:
        ap.print_help()
        return 0
    doc = train(force=a.force)
    _write_report(REPORT, None, model_doc=doc)
    print(f"prejudge_model: {doc.get('status')} n_train={doc.get('n_train')} "
          f"pos={doc.get('n_pos')} auc_holdout={doc.get('auc_holdout')} "
          f"refit={doc.get('refit')} -> {REPORT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
