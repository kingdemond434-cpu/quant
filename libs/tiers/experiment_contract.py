"""THE EXPERIMENT CONTRACT: every research leg declares what it is testing, how it is measured,
what would prove it wrong, what it may spend and who answers for it.

It EXTENDS the subsystem admission rule (`libs.tiers.contracts`) rather than duplicating it. The
admission rule already fixes the METRIC half -- one of eight gains, a dotted path into the leg's
own report, the direction that counts as better -- and evaluates it into ADMITTED / REJECTED /
UNMEASURED from the metric's history. What the desk never had is the rest of an experiment:

    hypothesis   what the leg claims its hour of compute buys, in one sentence
    metric       a `libs.tiers.contracts.Contract` (gain, metric, better, organ=report:<FILE>)
    falsifier    {metric, op, threshold, after}: the reading that would prove the hypothesis
                 wrong, judged against the leg's own report every hour
    budget       seconds per pass -- DERIVED from `hourly_cycle.LEG_BUDGET_SEC` when not declared
    owner        who answers for it -- DERIVED from `hourly_cycle.LEG_DEPARTMENT` when not declared

The declarations live in `docs/research/experiment_contracts.json`. Budget and owner are derived
because the cycle already declares them and a second copy would drift; hypothesis, metric and
falsifier cannot be derived and must be written by the leg's author. A Tier S `leg_contracts` row
supplies the metric half for the legs that programme contracted, so nothing is declared twice.

A FALSIFIER IS NEVER A VETO. A falsified experiment is published as FALSIFIED so its owner has to
answer it; nothing here stops a leg, cuts its budget or removes a producer (the principal's
standing order: research generation is never reduced).
"""
from __future__ import annotations

import json
import operator
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from libs.tiers import contracts

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "research" / "experiment_contracts.json"
TIER_S = ROOT / "docs" / "research" / "tier_s_program.json"
REPORTS = ROOT / "desks" / "mt5" / "reports"

REQUIRED: tuple[str, ...] = ("hypothesis", "metric", "falsifier", "budget", "owner")
FALSIFIED, HOLDS, UNMEASURED = "FALSIFIED", "HOLDS", "UNMEASURED"
#: A hypothesis shorter than this is a label, not a claim anyone could test.
MIN_HYPOTHESIS_CHARS = 24
_OPS: dict[str, Callable[[float, float], bool]] = {
    "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge,
    "==": operator.eq, "!=": operator.ne}


def _num(x: Any) -> float:
    """float(x), raising TypeError/ValueError on anything that is not a number (None included)."""
    if x is None or isinstance(x, bool):
        raise TypeError("not a number")
    return float(x)


def load_registry(path: Path | None = None) -> dict[str, Any]:
    try:
        d = json.loads((path or REGISTRY).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def tier_s_metrics(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """leg -> its Tier S admission contract (the metric half), where that programme wrote one."""
    try:
        d = json.loads((path or TIER_S).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for r in d.get("leg_contracts") or []:
        if isinstance(r, dict) and r.get("leg") and isinstance(r.get("contract"), dict):
            out[str(r["leg"])] = dict(r["contract"])
    return out


def resolve(leg: str, declared: Mapping[str, Any] | None, *,
            budget_s: int | None = None, department: str | None = None,
            tier_s_metric: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The leg's full contract: its declaration, with budget/owner/metric filled from the places
    the desk already declares them. Each derived field says where it came from."""
    c: dict[str, Any] = dict(declared or {})
    derived: dict[str, str] = {}
    if not c.get("budget") and budget_s:
        c["budget"] = {"seconds": int(budget_s)}
        derived["budget"] = "hourly_cycle.LEG_BUDGET_SEC"
    if not c.get("owner") and department:
        c["owner"] = f"department:{department}"
        derived["owner"] = "hourly_cycle.LEG_DEPARTMENT"
    if not c.get("metric") and tier_s_metric:
        c["metric"] = dict(tier_s_metric)
        derived["metric"] = "tier_s_program.leg_contracts"
    if derived:
        c["derived"] = derived
    c["leg"] = leg
    return c


def problems(c: Mapping[str, Any]) -> list[str]:
    """Static validation: every field present and well formed. Empty list means a valid contract."""
    out: list[str] = []
    for f in REQUIRED:
        if not c.get(f):
            out.append(f"missing {f}")
    hyp = str(c.get("hypothesis") or "")
    if hyp and len(hyp.strip()) < MIN_HYPOTHESIS_CHARS:
        out.append(f"hypothesis under {MIN_HYPOTHESIS_CHARS} chars: a label, not a claim")
    m = c.get("metric")
    if m:
        out.extend(f"metric: {p}" for p in contracts.problems(m))
        if isinstance(m, Mapping) and not str(m.get("organ") or "").startswith("report:"):
            out.append("metric: organ must be report:<FILE> (the leg's own report)")
    fz = c.get("falsifier")
    if fz:
        if not isinstance(fz, Mapping):
            out.append("falsifier must be an object {metric, op, threshold}")
        else:
            if not str(fz.get("metric") or ""):
                out.append("falsifier: metric is required")
            if str(fz.get("op")) not in _OPS:
                out.append(f"falsifier: op must be one of {sorted(_OPS)}")
            try:
                _num(fz.get("threshold"))
            except (TypeError, ValueError):
                out.append("falsifier: threshold must be a number")
    b = c.get("budget")
    if b:
        try:
            if _num((b or {}).get("seconds")) <= 0:
                out.append("budget: seconds must be positive")
        except (TypeError, ValueError, AttributeError):
            out.append("budget must be {seconds: <positive number>}")
    return out


def report_for(c: Mapping[str, Any], reports: Path | None = None) -> tuple[dict[str, Any], str]:
    organ = str((c.get("metric") or {}).get("organ") or "")
    if not organ.startswith("report:"):
        return {}, "UNMEASURED: no report organ"
    p = (reports or REPORTS) / organ.split(":", 1)[1]
    try:
        d = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}, f"UNMEASURED: {p.name} absent or unreadable on this host"
    return (d if isinstance(d, dict) else {}), "read"


def judge_falsifier(c: Mapping[str, Any], doc: Mapping[str, Any]) -> dict[str, Any]:
    fz = c.get("falsifier") or {}
    if not isinstance(fz, Mapping):
        return {"verdict": UNMEASURED, "why": "no falsifier"}
    val = contracts.read_metric(doc, str(fz.get("metric") or ""))
    if val is None:
        return {"verdict": UNMEASURED, "why": f"{fz.get('metric')} not a number in the report"}
    try:
        tripped = _OPS[str(fz.get("op"))](val, _num(fz.get("threshold")))
    except (KeyError, TypeError, ValueError):
        return {"verdict": UNMEASURED, "why": "falsifier malformed"}
    return {"verdict": FALSIFIED if tripped else HOLDS, "value": val,
            "rule": f"{fz.get('metric')} {fz.get('op')} {fz.get('threshold')}",
            "after": fz.get("after")}
