"""THE ALPHA THEORY COMPILER AND THE THEORY <-> EVIDENCE GRAPH (Tier S layers 17 and 18).

A mechanism the machine can reason over has seven slots:

    cause -> observable -> transmission -> condition -> trade -> horizon -> falsifier

The desk already holds three partial schemas for this (`libs/research/mechanism_genome.py`'s
eleven slots, `mechanism_ontology.py`'s falsifiers, `mechanism_claims.py`'s quantity/direction/
horizon grammar). `compile_mechanism()` reads any of them through one slot map, reports which
slots it could fill, and hashes the filled record so the same mechanism has the same id wherever
it came from. A record missing its falsifier is INCOMPLETE and says so: a theory nobody can
falsify is not yet a theory.

`compose(a, condition=b, execution=c)` builds mechanism A under state condition B with execution
mechanism C as a NEW record whose parents are all three -- composition is lineage, and the
ancestry discount in `libs/tiers/topology.py` charges it accordingly.

THE GRAPH. Every theory keeps the experiments that support and contradict it, weighted by where
the evidence came from (live 3, forward 2, backtest 1 -- reality outranks simulation), as a Beta
posterior. Confidence FALLS automatically when contradicting evidence accumulates; status is
UNTESTED, SUPPORTED, CONTESTED or REFUTED from the posterior, never set by hand. Competing
explanations are theories that predict the same observable and trade.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from libs.tiers.truth_kernel import canon, sha256

SLOTS: tuple[str, ...] = ("cause", "observable", "transmission", "condition", "trade", "horizon",
                          "falsifier")

#: every alias the desk's existing schemas use for a slot
SLOT_ALIASES: dict[str, tuple[str, ...]] = {
    "cause": ("cause", "actor", "catalyst", "trigger", "driver", "mechanism"),
    "observable": ("observable", "quantity", "feature", "signal", "input_source"),
    "transmission": ("transmission", "channel", "constraint", "pathway"),
    "condition": ("condition", "state", "regime", "selector", "session"),
    "trade": ("trade", "entry", "direction", "side", "exit"),
    "horizon": ("horizon", "holding", "timeframe", "hold"),
    "falsifier": ("falsifier", "falsifiers", "kill", "refutation"),
}

EVIDENCE_WEIGHT = {"live": 3.0, "forward": 2.0, "backtest": 1.0, "replication": 1.5}


@dataclass(frozen=True)
class Mechanism:
    cause: str = ""
    observable: str = ""
    transmission: str = ""
    condition: str = ""
    trade: str = ""
    horizon: str = ""
    falsifier: str = ""
    parents: tuple[str, ...] = field(default_factory=tuple)
    family: str = ""

    @property
    def mid(self) -> str:
        body = {s: getattr(self, s).strip().lower() for s in SLOTS}
        return "m" + sha256(canon({"slots": body, "parents": sorted(self.parents)}))[:16]

    @property
    def filled(self) -> list[str]:
        return [s for s in SLOTS if getattr(self, s).strip()]

    @property
    def complete(self) -> bool:
        return len(self.filled) == len(SLOTS)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["parents"] = list(self.parents)
        d["id"] = self.mid
        d["complete"] = self.complete
        d["missing"] = [s for s in SLOTS if s not in self.filled]
        return d


def _text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "; ".join(_text(x) for x in v if _text(x))
    if isinstance(v, Mapping):
        return "; ".join(f"{k}={_text(x)}" for k, x in sorted(v.items()) if _text(x))
    return str(v).strip()


def compile_mechanism(raw: Mapping[str, Any], *, family: str = "",
                      parents: Iterable[str] = ()) -> Mechanism:
    vals: dict[str, str] = {}
    lower = {str(k).lower(): v for k, v in raw.items()}
    for slot, aliases in SLOT_ALIASES.items():
        parts = [_text(lower[a]) for a in aliases if a in lower and _text(lower[a])]
        vals[slot] = " | ".join(dict.fromkeys(parts))
    return Mechanism(**vals, parents=tuple(parents), family=family or _text(raw.get("family")))


def compose(a: Mechanism, *, condition: Mechanism | None = None,
            execution: Mechanism | None = None) -> Mechanism:
    parents = [a.mid] + [m.mid for m in (condition, execution) if m is not None]
    cond = a.condition
    if condition is not None:
        cond = " AND ".join(x for x in (a.condition, condition.condition or condition.observable)
                            if x)
    trade = a.trade
    if execution is not None:
        trade = f"{a.trade} VIA {execution.trade or execution.transmission}".strip()
    fals = " OR ".join(x for x in (a.falsifier, condition.falsifier if condition else "") if x)
    return Mechanism(a.cause, a.observable, a.transmission, cond, trade, a.horizon, fals,
                     parents=tuple(parents), family=a.family)


@dataclass
class Theory:
    mechanism: Mechanism
    support: float = 0.0
    contra: float = 0.0
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def add(self, *, experiment: str, supports: bool, source: str, context: str = "") -> None:
        w = EVIDENCE_WEIGHT.get(source, 1.0)
        if supports:
            self.support += w
        else:
            self.contra += w
        self.evidence.append({"experiment": experiment, "supports": supports, "source": source,
                              "weight": w, "context": context})

    def posterior(self) -> dict[str, Any]:
        a, b = 1.0 + self.support, 1.0 + self.contra
        mean = a / (a + b)
        var = a * b / ((a + b) ** 2 * (a + b + 1))
        sd = math.sqrt(var)
        n = len(self.evidence)
        if n == 0:
            status = "UNTESTED"
        elif mean - 2 * sd > 0.5:
            status = "SUPPORTED"
        elif mean + 2 * sd < 0.35:
            status = "REFUTED"
        else:
            status = "CONTESTED"
        return {"confidence": round(mean, 4), "sd": round(sd, 4), "n_evidence": n,
                "support_weight": self.support, "contra_weight": self.contra, "status": status}


class TheoryGraph:
    def __init__(self) -> None:
        self.theories: dict[str, Theory] = {}

    def theory(self, m: Mechanism) -> Theory:
        t = self.theories.get(m.mid)
        if t is None:
            t = Theory(m)
            self.theories[m.mid] = t
        return t

    def competitors(self, mid: str) -> list[str]:
        me = self.theories[mid].mechanism
        key = (me.observable.lower(), me.trade.lower())
        return [k for k, t in self.theories.items() if k != mid and key[0]
                and (t.mechanism.observable.lower(), t.mechanism.trade.lower()) == key]

    def report(self, top: int = 50) -> dict[str, Any]:
        rows = []
        for mid, t in self.theories.items():
            post = t.posterior()
            rows.append({"id": mid, "family": t.mechanism.family, **post,
                         "complete": t.mechanism.complete,
                         "missing": [s for s in SLOTS if s not in t.mechanism.filled],
                         "competitors": self.competitors(mid)[:5],
                         "contradictions": [e for e in t.evidence if not e["supports"]][-5:]})
        rows.sort(key=lambda r: (-r["n_evidence"], r["id"]))
        by_status: dict[str, int] = {}
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        complete = sum(1 for r in rows if r["complete"])
        return {"n_theories": len(rows), "by_status": by_status,
                "complete_share": (complete / len(rows)) if rows else None,
                "theories": rows[:top]}
