"""THE INSTITUTION: what turns a population of scientists into a science.

A scientist proposes an object; the institution turns it into a HYPOTHESIS CARD with a claim,
a domain, a mechanism, units, predicted consequences, a falsifier, a cost, a multiplicity
charge and a lineage -- and then does to the card everything a working institution does to a
claim. The consequence engine derives testable consequences and tests them. Peer review scores
the card twice, by a DISCOVERER who argues for it and a DESTROYER who tries to kill it, from
independent random streams. The null factory manufactures planted nulls the judge must reject.
The theorem memory persists what was proven, what failed and what is now NEGATIVE KNOWLEDGE, as
jsonl under `desks/mt5/data/mathlab/`, and the failure scientist mines the failures for the
regions of the search space that are exhausted. The multiplicity ledger prices every card by
its family's effective trial count through `libs/research/trial_ledger.py`. The lockbox seals
the last slice of every panel before any scientist reads it and proves after the pass that the
seal is intact. Every card carries its PIT stamps. Credit flows back to the METHOD and the
method allocation evolves two-sided. A card reaches FORWARD only after a second, independent
run replicates it. The Pareto front of evidence against complexity is computed, cross-market
transfer measured, the residual's states discovered, causal adjudication run through the desk's
own adjudicator, and the next experiment chosen where the competing models disagree most.
Events go to the desk's event log and the wiring proof lists every scientist and engine that
ran this hour, with counts, so an idle organ cannot hide inside a busy artifact.

Nothing here allocates capital, certifies anything or bypasses the gauntlet.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from . import burden as B
from . import grammar as G
from .base import _corr, _finite, _quiet, _z
from .objects import MathObject, Panel

UNMEASURED = "UNMEASURED"
DESK = Path(__file__).resolve().parents[2]
MEMORY_DIR = DESK / "data" / "mathlab"
STATUSES: tuple[str, ...] = ("PROPOSED", "REVIEWED", "PROVISIONAL", "FORWARD", "FAILED")
#: The share of every panel sealed in the lockbox, never read by a scientist or a judge.
LOCKBOX_SHARE = 0.15
DEFAULT_FALSIFIER = ("the held-out IC of the signal over the next {n} bars is <= 0, or the "
                     "circular-block permutation p exceeds {p}, or the era stability falls below "
                     "{s}; any one retires the card")


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


# =========================================================================== the card
@dataclass
class MathHypothesisCard:
    """One claim, with everything an institution needs to try to kill it."""

    card_id: str
    claim: str
    domain: str                       # mathematics | physics
    mechanism: str
    units: dict[str, str]
    predicted_consequences: list[str]
    falsifier: str
    cost: dict[str, Any]
    multiplicity_charge: dict[str, Any]
    lineage: dict[str, Any]
    object_id: str = ""
    tradition: str = ""
    kind: str = "relationship"
    expression: Any = None
    canonical: str = ""
    target: str = ""
    horizon: str = "H1"
    side_mode: str = "follow"
    evidence: dict[str, Any] = field(default_factory=dict)
    complexity: dict[str, Any] = field(default_factory=dict)
    value: float | None = None
    passed: bool = False
    status: str = "PROPOSED"
    consequences: list[dict[str, Any]] = field(default_factory=list)
    review: dict[str, Any] = field(default_factory=dict)
    replication: dict[str, Any] = field(default_factory=dict)
    pit: dict[str, Any] = field(default_factory=dict)
    transfer: dict[str, Any] = field(default_factory=dict)
    states: dict[str, Any] = field(default_factory=dict)
    causal: dict[str, Any] = field(default_factory=dict)
    pareto: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def card_from_object(obj: MathObject, *, domain: str, method: str, civilization: str,
                     seed: int, compute_s: float = 0.0) -> MathHypothesisCard:
    """A card from a judged object. EVERY CARD HAS A FALSIFIER: the interpretation's own when
    it names one, the institution's default (held-out IC, permutation p, era stability)
    otherwise -- a claim nothing could refute is not admitted as a claim."""
    falsifier = (obj.interpretation.falsifier or "").strip() or DEFAULT_FALSIFIER.format(
        n=max(120, obj.evidence.n_test or 120), p=B.P_MAX, s=B.MIN_ERA_STABILITY)
    units = {v.name: (v.units or UNMEASURED) for v in obj.variables}
    mechanism = (obj.interpretation.rationale if obj.interpretation.status == "interpreted"
                 else f"uninterpreted: {obj.statement[:200]}")
    card_id = "card_" + hashlib.sha256(
        f"{obj.object_id}|{civilization}|{seed}".encode()).hexdigest()[:16]
    return MathHypothesisCard(
        card_id=card_id, claim=obj.statement[:600], domain=domain, mechanism=mechanism[:600],
        units=units, predicted_consequences=[], falsifier=falsifier,
        cost={"compute_s": round(float(compute_s), 3), "evaluated": int(obj.burden.get(
            "effective_trials", 0) or 0)},
        multiplicity_charge={}, lineage={"method": method, "tradition": obj.tradition,
                                         "civilization": civilization, "seed": int(seed),
                                         "parents": list(obj.provenance.parents),
                                         "residual_target": obj.provenance.residual_target,
                                         "residual_discovery_id":
                                             obj.provenance.residual_discovery_id},
        object_id=obj.object_id, tradition=obj.tradition, kind=obj.kind,
        expression=obj.expression, canonical=obj.canonical, target=obj.target,
        horizon=obj.horizon, side_mode=obj.side_mode, evidence=obj.evidence.to_row(),
        complexity=obj.complexity, value=obj.value, passed=bool(obj.passed),
        status="PROPOSED", notes=list(obj.notes))


# =========================================================================== consequences
def _signal(card: MathHypothesisCard, panel: Panel) -> np.ndarray:
    obj = MathObject(kind=card.kind if card.kind in ("relationship", "representation",
                                                      "mechanism", "law", "search_method")
                     else "relationship", tradition=card.tradition, expression=card.expression,
                     target=card.target, horizon=card.horizon, side_mode=card.side_mode)
    return np.asarray(np.nan_to_num(B.signal_of(obj, panel)), dtype=float)


def consequence_engine(card: MathHypothesisCard, panel: Panel) -> list[dict[str, Any]]:
    """Derive the testable consequences of a card and test each on the held-out rows.

    1. sign: the signal's sign predicts the residual's sign better than chance;
    2. dose-response: the residual's mean is monotone across signal quintiles;
    3. era invariance: the held-out IC keeps its sign in every era that holds 60 rows;
    4. neighbouring window: jittering the expression's windows keeps the sign (a law that lives
       at one exact window is a coincidence);
    5. magnitude: |signal| carries no extra information the sign lacks (a relationship claim
       is about direction).
    """
    signal = _signal(card, panel)
    eps = np.nan_to_num(panel.epsilon)
    _train, test = panel.split()
    rows = test if test.size >= 60 else np.arange(panel.n)
    out: list[dict[str, Any]] = []
    s, e = signal[rows], eps[rows]
    active = np.abs(s) > 1e-12
    if int(active.sum()) >= 30:
        hit = float(np.mean(np.sign(s[active]) == np.sign(e[active])))
        se = math.sqrt(0.25 / int(active.sum()))
        out.append({"consequence": "sign agreement above 50%", "statistic": round(hit, 4),
                    "threshold": round(0.5 + 1.64 * se, 4),
                    "status": "PASS" if hit > 0.5 + 1.64 * se else "FAIL"})
    else:
        out.append({"consequence": "sign agreement above 50%", "status": UNMEASURED,
                    "why": "fewer than 30 active held-out rows"})
    if rows.size >= 100:
        edges = np.quantile(s, [0.2, 0.4, 0.6, 0.8])
        bins = np.digitize(s, edges)
        means = [float(np.mean(e[bins == b])) if int((bins == b).sum()) >= 10 else np.nan
                 for b in range(5)]
        finite = [m for m in means if np.isfinite(m)]
        mono = (all(a <= b for a, b in pairwise(finite))
                or all(a >= b for a, b in pairwise(finite)))
        out.append({"consequence": "monotone dose-response across quintiles",
                    "quintile_means": [round(m, 6) if np.isfinite(m) else None for m in means],
                    "status": "PASS" if len(finite) >= 4 and mono else "FAIL"})
    else:
        out.append({"consequence": "monotone dose-response across quintiles",
                    "status": UNMEASURED, "why": "fewer than 100 held-out rows"})
    eras = panel.eras(4)
    signs: list[float] = []
    for k in range(4):
        er = np.flatnonzero(eras == k)
        if er.size >= 60:
            signs.append(_corr(signal[er], eps[er]))
    if len(signs) >= 2:
        same = all(np.sign(v) == np.sign(signs[0]) for v in signs)
        out.append({"consequence": "IC keeps its sign in every era",
                    "era_ic": [round(v, 4) for v in signs],
                    "status": "PASS" if same and signs[0] != 0 else "FAIL"})
    else:
        out.append({"consequence": "IC keeps its sign in every era", "status": UNMEASURED,
                    "why": "fewer than two eras hold 60 rows"})
    obj = MathObject(kind="relationship", tradition=card.tradition, expression=card.expression,
                     target=card.target, horizon=card.horizon, side_mode=card.side_mode)
    perturb = B.perturbation(obj, panel, rows)
    base_ic = _corr(s, e)
    if perturb is None:
        out.append({"consequence": "neighbouring windows keep the sign", "status": UNMEASURED,
                    "why": "the expression has no window to jitter"})
    else:
        out.append({"consequence": "neighbouring windows keep the sign",
                    "min_neighbour_t": round(perturb, 3), "base_ic": round(base_ic, 4),
                    "status": "PASS" if (perturb > 0) == (base_ic > 0) or perturb == 0.0
                    else "FAIL"})
    mag_ic = _corr(np.abs(s), e)
    out.append({"consequence": "direction, not magnitude, carries the claim",
                "ic_signed": round(base_ic, 4), "ic_magnitude": round(mag_ic, 4),
                "status": "PASS" if abs(base_ic) >= abs(mag_ic) else "FAIL"})
    card.consequences = out
    card.predicted_consequences = [c["consequence"] for c in out]
    return out


# =========================================================================== peer review
def discoverer_score(card: MathHypothesisCard, rng: np.random.Generator) -> dict[str, Any]:
    """The advocate: weighs held-out evidence, stability and the consequences that passed."""
    ev = card.evidence
    t = float(ev.get("t_held_out") or 0.0)
    stability = float(ev.get("era_stability") or 0.0)
    passed = sum(1 for c in card.consequences if c.get("status") == "PASS")
    tested = sum(1 for c in card.consequences if c.get("status") in ("PASS", "FAIL"))
    prior = 0.8 if card.mechanism and not card.mechanism.startswith("uninterpreted") else 0.35
    score = (max(0.0, t) / 3.0) * 0.4 + stability * 0.3 + (passed / tested if tested else 0.0) \
        * 0.2 + prior * 0.1
    _ = rng
    return {"role": "discoverer", "score": round(float(score), 4), "t_held_out": round(t, 3),
            "era_stability": round(stability, 3), "consequences_passed": f"{passed}/{tested}",
            "prior": prior}


def destroyer_score(card: MathHypothesisCard, panel: Panel, rng: np.random.Generator,
                    permutations: int = 60) -> dict[str, Any]:
    """The adversary, on an INDEPENDENT random stream: a second permutation null with a
    different block length, the simplest alternative (the residual's own AR(1)), and whether
    the card survives time reversal of the signal (a law that is as good backwards is not
    reading the future from the past)."""
    signal = _signal(card, panel)
    eps = np.nan_to_num(panel.epsilon)
    _train, test = panel.split()
    rows = test if test.size >= 60 else np.arange(panel.n)
    s, e = signal[rows], eps[rows]
    base = _corr(s, e)
    kills: list[str] = []
    block = 48
    beats = 0
    n = rows.size
    for _ in range(permutations):
        shift = int(rng.integers(block, max(block + 1, n - block)))
        beats += int(abs(_corr(np.roll(s, shift), e)) >= abs(base))
    p_alt = (1.0 + beats) / (1.0 + permutations)
    if p_alt > B.P_MAX:
        kills.append(f"second permutation null (block {block}) p={p_alt:.3f}")
    lagged = np.concatenate([[0.0], eps[:-1]])[rows]
    design = np.column_stack([np.ones(n), _z(lagged)])
    beta = np.linalg.lstsq(design, e, rcond=None)[0]
    resid = e - design @ beta
    partial = _corr(s, resid)
    if abs(partial) < 0.5 * abs(base):
        kills.append(f"the residual's own AR(1) explains it: partial IC {partial:+.4f} vs "
                     f"{base:+.4f}")
    reversed_ic = _corr(s[::-1], e)
    if abs(reversed_ic) >= abs(base) and abs(base) > 0:
        kills.append(f"time-reversed signal is as good ({reversed_ic:+.4f} vs {base:+.4f})")
    return {"role": "destroyer", "p_second_null": round(p_alt, 4),
            "partial_ic_after_ar1": round(partial, 4), "ic": round(base, 4),
            "reversed_ic": round(reversed_ic, 4), "kills": kills,
            "score": round(float(1.0 - len(kills) / 3.0), 4)}


def peer_review(card: MathHypothesisCard, panel: Panel, *, seed: int = 0,
                permutations: int = 60) -> dict[str, Any]:
    """Two independent scorers on two independent streams; the verdict needs both."""
    discoverer = discoverer_score(card, np.random.default_rng(seed * 7 + 1))
    destroyer = destroyer_score(card, panel, np.random.default_rng(seed * 7 + 2), permutations)
    accepted = discoverer["score"] >= 0.25 and not destroyer["kills"] and card.passed
    card.review = {"discoverer": discoverer, "destroyer": destroyer,
                   "verdict": "ACCEPT" if accepted else "REJECT",
                   "independent_streams": True}
    card.status = "REVIEWED" if accepted else "FAILED"
    return card.review


# =========================================================================== null factory
def null_factory(panel: Panel, rng: np.random.Generator, *, n: int = 6, permutations: int = 40
                 ) -> list[dict[str, Any]]:
    """Manufacture planted nulls and judge them: block-shuffled residuals, random expressions,
    and a fake law that fits the training slice by construction. The rejection rate is the
    judge's calibration, measured every pass."""
    out: list[dict[str, Any]] = []
    cols = [c for c in G.BAR_VARIABLES if c in panel.columns]
    _train, _test = panel.split()
    for i in range(n):
        kind = ("shuffled_residual", "random_expression", "fake_law")[i % 3]
        expr: Any
        view = Panel(target=panel.target, times=panel.times, epsilon=panel.epsilon,
                     columns=dict(panel.columns), meta=dict(panel.meta), regime=panel.regime,
                     session=panel.session, peers=panel.peers, horizon=panel.horizon,
                     source=panel.source)
        if kind == "shuffled_residual":
            expr = ["z", "ret", 24]
            blocks = np.array_split(np.arange(panel.n), max(2, panel.n // 48))
            order = rng.permutation(len(blocks))
            view.epsilon = np.concatenate([panel.epsilon[blocks[j]] for j in order])
        elif kind == "random_expression":
            expr = G.random_expr(rng, cols, max_depth=3)
        else:
            # A fake law: a column built to equal the residual on the training slice and noise
            # after it -- the in-sample-only fit every search finds and every judge must refuse.
            train, _ = panel.split()
            fake = rng.normal(0, 1, panel.n)
            fake[train] = np.nan_to_num(panel.epsilon[train]) + 0.3 * rng.normal(0, 1, train.size)
            view.columns["fake_law"] = fake
            expr = ["z", "fake_law", 24]
        obj = MathObject(kind="relationship", tradition="null_factory", expression=expr,
                         target=panel.target, horizon=panel.horizon, side_mode="follow",
                         statement=f"planted null: {kind}")
        try:
            verdict = B.judge(obj, view, distinct_forms=1, rng=rng, permutations=permutations)
            out.append({"null": kind, "canonical": obj.canonical, "passed": bool(obj.passed),
                        "value": round(float(verdict.value), 4),
                        "ic_in_sample": obj.evidence.ic_in_sample,
                        "ic_held_out": obj.evidence.ic_held_out})
        except Exception as exc:
            out.append({"null": kind, "status": UNMEASURED, "why": type(exc).__name__})
    return out


# =========================================================================== theorem memory
class TheoremMemory:
    """Proven, failed and negative knowledge as append-only jsonl; a knowledge graph of
    lineage edges beside them. Reads are bounded to the tail so a year costs nothing."""

    FILES = ("proven", "failed", "negative", "lineage")

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or MEMORY_DIR

    def path(self, name: str) -> Path:
        return self.root / f"{name}.jsonl"

    def append(self, name: str, row: dict[str, Any]) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with self.path(name).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": now_iso(), **row}, default=str,
                                    separators=(",", ":")) + "\n")
            return True
        except OSError:
            return False

    def rows(self, name: str, limit: int = 2000) -> list[dict[str, Any]]:
        p = self.path(name)
        if not p.exists():
            return []
        try:
            lines = p.read_text("utf-8").splitlines()[-limit:]
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def known(self, canonical: str) -> str | None:
        """PROVEN / FAILED / NEGATIVE when the canonical form has a verdict on file."""
        for name in ("proven", "failed", "negative"):
            if any(str(r.get("canonical")) == canonical for r in self.rows(name)):
                return name.upper()
        return None

    def record(self, card: MathHypothesisCard) -> str:
        bucket = "proven" if card.status in ("FORWARD", "PROVISIONAL") else "failed"
        self.append(bucket, {"card_id": card.card_id, "object_id": card.object_id,
                             "canonical": card.canonical, "kind": card.kind,
                             "domain": card.domain, "tradition": card.tradition,
                             "target": card.target, "status": card.status,
                             "value": card.value, "falsifier": card.falsifier,
                             "review": card.review.get("verdict"),
                             "kills": (card.review.get("destroyer") or {}).get("kills", [])})
        self.append("lineage", {"card_id": card.card_id, "parent_object": card.object_id,
                                "method": card.lineage.get("method"),
                                "tradition": card.tradition,
                                "civilization": card.lineage.get("civilization"),
                                "parents": card.lineage.get("parents", []),
                                "residual_discovery_id":
                                    card.lineage.get("residual_discovery_id")})
        return bucket

    def graph(self) -> dict[str, Any]:
        lineage = self.rows("lineage")
        nodes = {str(r.get("card_id")) for r in lineage}
        methods = {str(r.get("method")) for r in lineage}
        return {"cards": len(nodes), "methods": len(methods), "edges": len(lineage),
                "proven": len(self.rows("proven")), "failed": len(self.rows("failed")),
                "negative": len(self.rows("negative"))}


def failure_scientist(memory: TheoremMemory, *, min_failures: int = 5) -> list[dict[str, Any]]:
    """Mine the failures for exhausted regions: a (tradition, kind, target) that has failed
    `min_failures` times with nothing proven is NEGATIVE KNOWLEDGE, written once per region and
    read back before the next search spends there."""
    failed = memory.rows("failed")
    proven = memory.rows("proven")
    negative_known = {(str(r.get("tradition")), str(r.get("kind")), str(r.get("target")))
                      for r in memory.rows("negative")}
    proven_keys = {(str(r.get("tradition")), str(r.get("kind")), str(r.get("target")))
                   for r in proven}
    counts: dict[tuple[str, str, str], int] = {}
    kills: dict[tuple[str, str, str], dict[str, int]] = {}
    for r in failed:
        key = (str(r.get("tradition")), str(r.get("kind")), str(r.get("target")))
        counts[key] = counts.get(key, 0) + 1
        for k in r.get("kills") or []:
            reason = str(k).split(":")[0][:60]
            kills.setdefault(key, {})[reason] = kills.setdefault(key, {}).get(reason, 0) + 1
    out: list[dict[str, Any]] = []
    for key, n in counts.items():
        if n >= min_failures and key not in proven_keys and key not in negative_known:
            row = {"tradition": key[0], "kind": key[1], "target": key[2], "failures": n,
                   "proven": 0, "dominant_kill": max(kills.get(key, {"?": 0}),
                                                     key=lambda k: kills.get(key, {}).get(k, 0)),
                   "verdict": "EXHAUSTED_REGION",
                   "rule": "a region that only fails is negative knowledge; the next search "
                           "reads it before spending here"}
            memory.append("negative", row)
            out.append(row)
    return out


# =========================================================================== multiplicity
def multiplicity_ledger(cards: list[MathHypothesisCard], evaluated_by_method: dict[str, int]
                        ) -> dict[str, Any]:
    """Price the pass's cards by their families' EFFECTIVE trials through the desk's ledger
    module, and stamp each card with its charge in sigma units."""
    try:
        from libs.research import trial_ledger as TL
    except Exception as exc:
        for card in cards:
            card.multiplicity_charge = {"status": UNMEASURED,
                                        "why": f"trial_ledger unimportable: {type(exc).__name__}"}
        return {"status": UNMEASURED}
    trials = []
    for card in cards:
        windows = list(_windows(card.expression))
        trials.append(TL.Trial(
            trial_id=card.card_id, family=f"mathlab:{card.tradition}",
            descriptors={"kind": card.kind, "target": card.target, "horizon": card.horizon,
                         "domain": card.domain, "side": card.side_mode},
            params={f"w{i}": w for i, w in enumerate(windows[:4])},
            declared_width=max(1, int(evaluated_by_method.get(card.tradition, 1)))))
    census = TL.census(trials)
    by_family = dict(census.families)
    for card in cards:
        fam = by_family.get(f"mathlab:{card.tradition}")
        n_eff = float(getattr(fam, "n_effective", 0.0) or 0.0) if fam is not None else 0.0
        n_raw = int(getattr(fam, "n_raw", 0) or 0) if fam is not None else 0
        if n_eff <= 0:
            n_eff = float(max(1, evaluated_by_method.get(card.tradition, 1)))
        card.multiplicity_charge = {"n_raw": n_raw, "n_effective": round(n_eff, 3),
                                    "declared_width": int(evaluated_by_method.get(
                                        card.tradition, 1)),
                                    "charge_sigma": round(math.sqrt(2.0 * math.log(
                                        max(2.0, n_eff))), 4),
                                    "ledger": "libs/research/trial_ledger.py"}
    return {"status": "MEASURED", **census.to_dict(), "cards": len(cards)}


def _windows(node: Any) -> list[int]:
    out: list[int] = []
    if isinstance(node, list) and node:
        if node[0] in G.WINDOWED and len(node) == 3 and isinstance(node[2], (int, float)):
            out.append(int(node[2]))
        for child in node[1:]:
            out.extend(_windows(child))
    return out


# =========================================================================== lockbox
@dataclass
class Lockbox:
    """The sealed tail of a panel. `seal` cuts it off BEFORE any scientist sees the panel and
    hashes it; `verify` after the pass proves nothing wrote into it."""

    target: str
    rows: int
    sha256: str
    first_time: int
    last_time: int

    @classmethod
    def seal(cls, panel: Panel, share: float = LOCKBOX_SHARE) -> tuple[Panel, Lockbox]:
        cut = int(panel.n * (1.0 - share))
        sealed = cls(target=panel.target, rows=panel.n - cut,
                     sha256=cls.digest(panel, cut), first_time=int(panel.times[cut])
                     if cut < panel.n else 0, last_time=int(panel.times[-1]))
        working = Panel(target=panel.target, times=panel.times[:cut], epsilon=panel.epsilon[:cut],
                        columns={k: v[:cut] for k, v in panel.columns.items()},
                        meta=dict(panel.meta),
                        regime=None if panel.regime is None else panel.regime[:cut],
                        session=None if panel.session is None else panel.session[:cut],
                        peers={k: v[:cut] for k, v in panel.peers.items()},
                        horizon=panel.horizon, source=panel.source,
                        residual_discovery_id=panel.residual_discovery_id)
        return working, sealed

    @staticmethod
    def digest(panel: Panel, cut: int) -> str:
        h = hashlib.sha256()
        h.update(np.ascontiguousarray(panel.epsilon[cut:]).tobytes())
        for name in sorted(panel.columns):
            h.update(name.encode())
            h.update(np.ascontiguousarray(panel.columns[name][cut:]).tobytes())
        return h.hexdigest()

    def verify(self, panel: Panel) -> dict[str, Any]:
        cut = panel.n - self.rows
        same = self.digest(panel, cut) == self.sha256
        return {"target": self.target, "rows_sealed": self.rows, "untouched": bool(same),
                "sha256": self.sha256, "first_time": self.first_time,
                "last_time": self.last_time}


def lockbox_respected(cards: list[MathHypothesisCard], working_rows: dict[str, int]
                      ) -> dict[str, Any]:
    """No card's evidence may have read more rows than the working panel holds."""
    breaches = [c.card_id for c in cards
                if int(c.evidence.get("n_train") or 0) + int(c.evidence.get("n_test") or 0)
                > working_rows.get(c.target, 0)]
    return {"cards": len(cards), "breaches": breaches, "respected": not breaches}


# =========================================================================== PIT
def pit_check(card: MathHypothesisCard, panel: Panel) -> dict[str, Any]:
    stamps = {}
    for name in sorted(G.variables_in(card.expression)):
        var = panel.meta.get(name)
        stamps[name] = var.available_time if var is not None else UNMEASURED
    unknown = [k for k, v in stamps.items() if v == UNMEASURED]
    card.pit = {"stamps": stamps, "unknown": unknown, "clean": not unknown,
                "rule": "a value stamped available_time t is used only at bars >= t"}
    return card.pit


# =========================================================================== credit
def credit_methods(cards: list[MathHypothesisCard], evaluated_by_method: dict[str, int],
                   compute_by_method: dict[str, float]) -> dict[str, dict[str, Any]]:
    """Survivors, FORWARD cards and trials per method: the credit that flows back to the
    search method, in the shape `engines.method_tournament` reads."""
    out: dict[str, dict[str, Any]] = {}
    for method in set(evaluated_by_method) | {c.tradition for c in cards}:
        mine = [c for c in cards if c.tradition == method]
        out[method] = {"trials": int(evaluated_by_method.get(method, 0)),
                       "cards": len(mine), "passed": sum(1 for c in mine if c.passed),
                       "reviewed": sum(1 for c in mine if c.review.get("verdict") == "ACCEPT"),
                       "forward": sum(1 for c in mine if c.status == "FORWARD"),
                       "compute_s": round(float(compute_by_method.get(method, 0.0)), 3)}
    return out


def evolve_methods(credit: dict[str, dict[str, Any]], previous: dict[str, Any] | None,
                   floor: float = 0.02) -> dict[str, Any]:
    """The method allocation, two-sided around the default by measured survival, floored."""
    prior = (previous or {}).get("methods") or {}
    scores = {m: (row["passed"] + 2 * row["forward"]) / max(1, row["trials"])
              for m, row in credit.items() if row["trials"] > 0}
    scale = float(np.mean(list(scores.values()))) if scores else 0.0
    raw = {}
    for m in credit:
        if m not in scores or scale <= 0:
            raw[m] = 1.0
        else:
            raw[m] = max(0.05, 1.0 + (scores[m] - scale) / max(scale, 1e-9))
    total = sum(raw.values()) or 1.0
    floor = min(floor, 1.0 / max(1, len(raw)))
    free = max(0.0, 1.0 - floor * len(raw))
    shares = {m: round(floor + free * raw[m] / total, 6) for m in raw}
    # An ALLOCATION sums to one. Rounding six places over n methods leaves a residual of up to
    # n*5e-7, and a share table that does not sum to one is not an allocation -- the residual is
    # given to the largest share, which is the only one that can absorb it without hitting floor.
    if shares:
        drift = round(1.0 - sum(shares.values()), 9)
        biggest = max(shares, key=lambda m: (shares[m], m))
        shares[biggest] = round(shares[biggest] + drift, 9)
    return {"at": now_iso(), "methods": {
        m: {"share": shares[m],
            "survival": round(scores.get(m, 0.0), 6) if m in scores else None,
            "status": "MEASURED" if m in scores else UNMEASURED,
            "lifetime_trials": int((prior.get(m) or {}).get("lifetime_trials", 0))
            + int(credit[m]["trials"])} for m in credit},
        "two_sided": "a method's share rises and falls with its measured survival; the floor "
                     "keeps every method's scout alive", "floor": floor}


# =========================================================================== replication
def replicate(card: MathHypothesisCard, panel: Panel, *, seed: int, permutations: int = 60,
              other_civilization_passed: set[str] | None = None) -> dict[str, Any]:
    """A SECOND, INDEPENDENT RUN before a card may be FORWARD: the same canonical form re-judged
    on a shifted split (train 50%) with a fresh random stream, or found and passed by the other
    civilization. One run is PROVISIONAL, whatever its value."""
    obj = MathObject(kind="relationship", tradition=card.tradition, expression=card.expression,
                     target=card.target, horizon=card.horizon, side_mode=card.side_mode)
    shifted = Panel(target=panel.target, times=panel.times, epsilon=panel.epsilon,
                    columns=dict(panel.columns), meta=dict(panel.meta), regime=panel.regime,
                    session=panel.session, peers=panel.peers, horizon=panel.horizon,
                    source=panel.source)
    shifted.split = lambda train_frac=0.5: Panel.split(shifted, train_frac)  # type: ignore[method-assign]
    try:
        B.judge(obj, shifted, distinct_forms=max(1, int(card.cost.get("evaluated") or 1)),
                rng=np.random.default_rng(seed), permutations=permutations)
        second = {"run": "shifted_split_50", "seed": seed, "passed": bool(obj.passed),
                  "ic_held_out": obj.evidence.ic_held_out, "value": obj.value}
    except Exception as exc:
        second = {"run": "shifted_split_50", "seed": seed, "passed": False,
                  "status": UNMEASURED, "why": type(exc).__name__}
    cross = card.canonical in (other_civilization_passed or set())
    replicated = bool(second["passed"]) or cross
    card.replication = {"runs": 2, "first": {"passed": card.passed, "value": card.value},
                        "second": second, "cross_civilization": cross, "replicated": replicated,
                        "rule": "no card is FORWARD on one run"}
    if card.status == "REVIEWED":
        card.status = "FORWARD" if replicated else "PROVISIONAL"
    return card.replication


# =========================================================================== Pareto front
def pareto_front(cards: list[MathHypothesisCard]) -> list[dict[str, Any]]:
    """Evidence (held-out t) against complexity (MDL bits): rank 0 is the non-dominated set."""
    points = [(float(c.evidence.get("t_held_out") or 0.0), float(c.complexity.get("mdl_bits")
                                                                 or 0.0), c) for c in cards]
    remaining = list(points)
    rank = 0
    out: list[dict[str, Any]] = []
    while remaining and rank < 6:
        front = [p for p in remaining
                 if not any((q[0] >= p[0] and q[1] <= p[1] and (q[0] > p[0] or q[1] < p[1]))
                            for q in remaining)]
        for t, bits, card in front:
            card.pareto = {"rank": rank, "evidence_t": round(t, 3), "mdl_bits": round(bits, 3)}
            out.append({"card_id": card.card_id, "rank": rank, "evidence_t": round(t, 3),
                        "mdl_bits": round(bits, 3), "canonical": card.canonical[:80]})
        remaining = [p for p in remaining if p not in front]
        rank += 1
    for _t, _b, card in remaining:
        card.pareto = {"rank": rank, "evidence_t": round(_t, 3), "mdl_bits": round(_b, 3)}
    return out


# =========================================================================== transfer / states
def cross_market(card: MathHypothesisCard, peers: list[Panel]) -> dict[str, Any]:
    obj = MathObject(kind="relationship", tradition=card.tradition, expression=card.expression,
                     target=card.target, horizon=card.horizon, side_mode=card.side_mode)
    ic, symbol = B.cross_market_transfer(obj, peers)
    card.transfer = {"ic": ic, "symbol": symbol,
                     "status": "MEASURED" if ic is not None else UNMEASURED}
    return card.transfer


def state_discovery(panel: Panel, k: int = 3, iterations: int = 12) -> np.ndarray:
    """k-means over (return z, range z, activity z): the residual's own states, unsupervised."""
    feats = []
    for tree in (["z", "ret", 24], ["z", "range", 24], ["z", "activity", 24]):
        if tree[1] in panel.columns:
            with _quiet():
                feats.append(_z(np.nan_to_num(G.evaluate(tree, panel.columns, panel.n))))
    if not feats:
        return np.zeros(panel.n, dtype=int)
    X = np.column_stack(feats)
    centres = X[np.linspace(0, panel.n - 1, k).astype(int)]
    labels = np.zeros(panel.n, dtype=int)
    for _ in range(iterations):
        d = ((X[:, None, :] - centres[None, :, :]) ** 2).sum(-1)
        labels = d.argmin(1)
        for j in range(k):
            if (labels == j).any():
                centres[j] = X[labels == j].mean(0)
    return labels


def states_of(card: MathHypothesisCard, panel: Panel, labels: np.ndarray) -> dict[str, Any]:
    signal = _signal(card, panel)
    eps = np.nan_to_num(panel.epsilon)
    per = {}
    for j in sorted(set(labels.tolist())):
        rows = np.flatnonzero(labels == j)
        per[str(j)] = round(_corr(signal[rows], eps[rows]), 4) if rows.size >= 60 else None
    finite = {k: v for k, v in per.items() if v is not None}
    card.states = {"ic_by_state": per,
                   "lives_in": max(finite, key=lambda k: abs(finite[k])) if finite else None}
    return card.states


# =========================================================================== causal
def causal_scientist(card: MathHypothesisCard, panel: Panel, *, seed: int = 0, n_perm: int = 60
                     ) -> dict[str, Any]:
    """The desk's own causal adjudicator over the card: cause = the signal, effect = the
    residual, with a placebo, a negative control, era subsets and the AR(1) as the simpler
    explanation. A card without a falsifier is ineligible there too."""
    try:
        from libs.research import causal_adjudicator as CA
    except Exception as exc:
        card.causal = {"status": UNMEASURED, "why": f"causal_adjudicator unimportable: "
                                                     f"{type(exc).__name__}"}
        return card.causal
    signal = _signal(card, panel)
    eps = np.nan_to_num(panel.epsilon)
    rng = np.random.default_rng(seed)
    eras = panel.eras(2)
    lagged = np.concatenate([[0.0], eps[:-1]])
    mech = CA.Mechanism(
        name=card.card_id, cause=signal, effect=eps, lag=1,
        claimed_sign=1 if card.side_mode == "follow" else -1,
        placebo_predictors={"shuffled_signal": rng.permutation(signal)},
        negative_controls={"white_noise": rng.normal(0, 1, panel.n)},
        subsets={"era_0": eras == 0, "era_1": eras == 1},
        simpler={"ar1_of_residual": lagged},
        falsifier=card.falsifier, competing=("the residual's own AR(1)",))
    try:
        adj = CA.adjudicate(mech, seed=seed, n_perm=n_perm)
        card.causal = adj.to_dict()
    except Exception as exc:
        card.causal = {"status": UNMEASURED, "why": f"adjudicate raised {type(exc).__name__}"}
    return card.causal


# =========================================================================== experiment design
def experiment_design(cards: list[MathHypothesisCard], next_slice: dict[str, Any] | None
                      ) -> dict[str, Any]:
    """Active selection: the card whose reviewers disagree most is the one an observation
    teaches most about; the slice where the models disagree most is where to observe it."""
    ranked = []
    for c in cards:
        d = float((c.review.get("discoverer") or {}).get("score") or 0.0)
        k = float((c.review.get("destroyer") or {}).get("score") or 0.0)
        ranked.append((abs(d - k), c.card_id, c.canonical[:80]))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    return {"next_card": ({"card_id": ranked[0][1], "canonical": ranked[0][2],
                           "reviewer_disagreement": round(ranked[0][0], 4)} if ranked else None),
            "next_slice": next_slice,
            "rule": "observe where the reviewers disagree, in the slice where the models "
                    "disagree"}


# =========================================================================== events / wiring
def event_row(kind: str, **fields: Any) -> dict[str, Any] | None:
    try:
        from libs.ops import events
        return events.emit(kind, **fields)
    except Exception:
        return None


def _engine_counts(v: Any) -> dict[str, Any]:
    row = v.to_row() if hasattr(v, "to_row") else (v if isinstance(v, dict) else {})
    return {"status": str(row.get("status", "?")), "trials": int(row.get("trials") or 0),
            "findings": len(row.get("findings") or []),
            "compute_s": round(float(row.get("compute_s") or 0.0), 3)}


def wiring_proof(scientists_ran: dict[str, dict[str, Any]], engines_ran: dict[str, Any],
                 expected_scientists: list[str], expected_engines: list[str]) -> dict[str, Any]:
    """The artifact's own census: every scientist and engine that ran this hour, with counts,
    and the names that did not -- an organ that is idle is named, never hidden."""
    missing_s = [s for s in expected_scientists if s not in scientists_ran]
    missing_e = [e for e in expected_engines if e not in engines_ran]
    return {"scientists": {k: {"objects": int(v.get("proposed", 0)),
                               "evaluated": int(v.get("evaluated", 0)),
                               "passed": int(v.get("passed", 0)),
                               "status": v.get("status", "OK"),
                               "compute_s": round(float(v.get("compute_s", 0.0)), 3)}
                           for k, v in scientists_ran.items()},
            "engines": {k: _engine_counts(v) for k, v in engines_ran.items()},
            "expected_scientists": len(expected_scientists),
            "expected_engines": len(expected_engines),
            "missing_scientists": missing_s, "missing_engines": missing_e,
            "complete": not missing_s and not missing_e,
            "rule": "UNWIRED OR IDLE IS A DEFECT: an organ absent from this list did not run"}


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


_ = (time, _finite)
