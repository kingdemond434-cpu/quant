"""THE PRE-JUDGE SCREEN: where Tier S's adopted defenders and ratified tests act (layers 9, 21).

The Red Queen (layer 9) finds attack kinds that fool the certifier; test invention (layer 21)
finds checks that stop traps on one suite and are confirmed on another. Until this module both
ended in a report: nothing a candidate passed through changed. The sealed judge
(`external_gauntlet.py`, `universal_gate.py`, everything `check_immutable_evaluator` signs) may
not be edited by an agent, so the rules act on the RESEARCH side, one step before judging:

    rules file      desks/mt5/data/tier_s/PREJUDGE_RULES.json   (written by tier_s.py only)
    screen          side_channels/run_external_backtest.run_cell computes each backtested
                    candidate's features with the SAME function the rules were learned on
                    (`libs.tiers.meta_benchmark.features`, per-bar positions x log returns) and
                    tags the result row `prejudge = {flags, rules_hash}`; the verdicts are
                    indexed by executable identity in data/hypotheses/prejudge_verdicts.json
    consequence     research/merge_hypotheses (the docket writer) moves every FLAGGED row behind
                    the unflagged rows of its OWN family, in that family's own slots -- so the
                    judge's family-balanced prefix is unchanged and the flagged cell is reached
                    after its clean siblings. Nothing is removed, nothing is refused: a demotion
                    withholds no candidate from judging, so it bills no missed growth, and the
                    count of demoted rows is published beside the docket (merge_report.json).

ADOPTION IS EARNED, NEVER ASSERTED. A rule enters the file only when its challenger -- the
incumbent reference validator plus the rule -- SURVIVES THE SEALED TRAP SUITE: on a suite neither
proposal nor confirmation saw, it rejects at least as many traps as the incumbent and accepts
every genuine planted signal the incumbent accepts (`sealed_survival`). A rule whose feature a
candidate's backtest cannot produce is never adopted (`SCREEN_FEATURES`).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.tiers import meta_benchmark as mb
from libs.tiers import traps

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "desks" / "mt5" / "data" / "tier_s" / "PREJUDGE_RULES.json"
VERDICTS = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "prejudge_verdicts.json"

#: features a real backtested candidate yields exactly as a synthetic case does. `variants` (the
#: trials a case declares) is absent on purpose: a docket row declares none, so a rule on it
#: would read a constant.
SCREEN_FEATURES: tuple[str, ...] = ("sr", "t", "n", "zero_share", "ac1", "sr_first_half",
                                    "sr_second_half", "decay", "turnover")
#: a rule that flags more than this share of the candidates it screened in one pass is not
#: separating anything; it is published as UNINFORMATIVE (and still only demotes)
UNINFORMATIVE_SHARE = 0.9


# ------------------------------------------------------------------------------------------------
# features of a real candidate, on the same definition the rules were learned on
# ------------------------------------------------------------------------------------------------

def positions_from_trades(index: Sequence[Any], trades: Iterable[Any]) -> np.ndarray:
    """Per-bar position (+1/-1/0) held from bar t to t+1, from the engine's trades
    (`entry_time`, `exit_time`, `side`). A trade entered at bar i's open is exposed to bar i's
    return, which meta_benchmark books as held from bar i-1 to i."""
    import pandas as pd
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx), dtype=float)
    for tr in trades:
        try:
            a = int(idx.searchsorted(pd.Timestamp(tr.entry_time)))
            b = int(idx.searchsorted(pd.Timestamp(tr.exit_time)))
        except (TypeError, ValueError, AttributeError):
            continue
        a, b = max(a - 1, 0), min(max(b - 1, a), len(idx) - 1)
        if b > a:
            pos[a:b] = float(np.sign(getattr(tr, "side", 0) or 0))
    return pos


def candidate_features(closes: Sequence[float], pos: Sequence[float], *,
                       cost_per_trade: float = 0.0) -> dict[str, float] | None:
    """`meta_benchmark.features` on a real price path and position series. None when the path
    is too short or not positive (UNMEASURED, never a clean pass)."""
    px = np.asarray(closes, dtype=float)
    p = np.asarray(pos, dtype=float)
    if len(px) < 40 or len(p) != len(px) or not np.all(np.isfinite(px)) or np.any(px <= 0):
        return None
    n = len(px)
    case = traps.Case(case_id="candidate", prices=px, signal_fn=lambda _p, t: float(p[t]),
                      fills=px.copy(), lows=px.copy(), highs=px.copy(),
                      cost_per_trade=float(cost_per_trade), n_variants_tried=1,
                      factor_returns=np.zeros(n + 1), universe_returns=np.zeros((n, 1)),
                      universe_alive=np.ones(1, dtype=bool))
    feats = mb.features(case, p)
    out = {k: float(v) for k, v in feats.items() if k in SCREEN_FEATURES}
    return out if all(math.isfinite(v) for v in out.values()) else None


# ------------------------------------------------------------------------------------------------
# the rules
# ------------------------------------------------------------------------------------------------

def rule_id(source: str, check: Sequence[Any], kind: str = "") -> str:
    f, op, thr = str(check[0]), str(check[1]), float(check[2])
    return f"{source}:{kind + ':' if kind else ''}{f}{op}{thr:.6g}"


def load_rules(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads((path or RULES).read_text("utf-8"))
    except (OSError, ValueError):
        return {"rules": []}
    return doc if isinstance(doc, dict) and isinstance(doc.get("rules"), list) else {"rules": []}


def active(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in doc.get("rules") or [] if isinstance(r, Mapping)
            and r.get("status") == "ADOPTED" and isinstance(r.get("check"), list)
            and len(r["check"]) == 3 and str(r["check"][0]) in SCREEN_FEATURES]


def rules_hash(rules: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(sorted(str(r.get("id")) for r in rules)).encode()
                          ).hexdigest()[:16]


def adopt(doc: Mapping[str, Any], rule: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Add `rule` (idempotent by id). Returns (new doc, added)."""
    rules = [dict(r) for r in doc.get("rules") or [] if isinstance(r, Mapping)]
    if any(r.get("id") == rule.get("id") for r in rules):
        return {**doc, "rules": rules}, False
    rules.append({**rule, "status": "ADOPTED"})
    return {**doc, "rules": rules}, True


def save_rules(doc: Mapping[str, Any], path: Path | None = None) -> None:
    p = path or RULES
    p.parent.mkdir(parents=True, exist_ok=True)
    rules = list(doc.get("rules") or [])
    body = {**doc, "updated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "rules_hash": rules_hash(active({"rules": rules})),
            "consumers": ["desks/mt5/side_channels/run_external_backtest.py run_cell (tags)",
                          "desks/mt5/research/merge_hypotheses.py (demotes within family)"],
            "rule": "demote, never remove: a flagged candidate is judged after its clean "
                    "siblings of the same family and is never withheld from judging"}
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(body, indent=1, default=str), "utf-8")
    os.replace(tmp, p)


def fires(check: Sequence[Any], feats: Mapping[str, float]) -> bool | None:
    """True/False, or None when the candidate lacks the feature (UNMEASURED)."""
    v = feats.get(str(check[0]))
    if v is None:
        return None
    thr = float(check[2])
    return (check[1] == ">" and v > thr) or (check[1] == "<" and v < thr)


def screen(feats: Mapping[str, float] | None, rules: Sequence[Mapping[str, Any]]
           ) -> dict[str, Any]:
    """The verdict one candidate carries: the rules it trips, the ones it could not be judged
    on, and the rule set's hash (a verdict under an older rule set is recognisable as such)."""
    h = rules_hash(rules)
    if feats is None:
        return {"status": "UNMEASURED", "flags": [], "rules_hash": h}
    flags, unmeasured = [], []
    for r in rules:
        f = fires(r["check"], feats)
        if f is None:
            unmeasured.append(str(r["id"]))
        elif f:
            flags.append(str(r["id"]))
    return {"status": "SCREENED", "flags": flags, "unmeasured": unmeasured, "rules_hash": h}


# ------------------------------------------------------------------------------------------------
# the consequence: demotion inside the family, published
# ------------------------------------------------------------------------------------------------

def identity(row: Mapping[str, Any]) -> str:
    """merge_hypotheses._identity, spelled once more: what would actually be EXECUTED."""
    params = row.get("params") or {}
    params = params if isinstance(params, Mapping) else {}
    return json.dumps({"symbol": str(row.get("symbol") or row.get("sym") or ""),
                       "family": str(row.get("family") or ""),
                       "params": {k: params[k] for k in sorted(params)}},
                      sort_keys=True, default=str)


def load_verdicts(path: Path | None = None) -> dict[str, Any]:
    try:
        doc = json.loads((path or VERDICTS).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    v = doc.get("verdicts") if isinstance(doc, dict) else None
    return v if isinstance(v, dict) else {}


def demote_flagged(rows: list[dict[str, Any]], verdicts: Mapping[str, Any]
                   ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Stable, family-preserving demotion. Each family keeps the SAME positions in the docket;
    within them its unflagged rows come first and its flagged rows after, each group in its
    original order. The docket's length, membership and family interleave are unchanged."""
    flagged_of: list[bool] = []
    by_rule: dict[str, int] = {}
    for r in rows:
        v = r.get("prejudge") if isinstance(r.get("prejudge"), Mapping) else None
        v = v or verdicts.get(identity(r))
        flags = list((v or {}).get("flags") or []) if isinstance(v, Mapping) else []
        if flags:
            r["prejudge"] = dict(v) if isinstance(v, Mapping) else {"flags": flags}
            for f in flags:
                by_rule[str(f)] = by_rule.get(str(f), 0) + 1
        flagged_of.append(bool(flags))
    slots: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        slots.setdefault(str(r.get("family") or ""), []).append(i)
    out: list[dict[str, Any]] = list(rows)
    moved = 0
    for idxs in slots.values():
        order = [i for i in idxs if not flagged_of[i]] + [i for i in idxs if flagged_of[i]]
        for slot, src in zip(idxs, order, strict=True):
            out[slot] = rows[src]
            moved += int(slot != src)
    return out, {"rows": len(rows), "flagged": sum(flagged_of), "moved": moved,
                 "by_rule": dict(sorted(by_rule.items())),
                 "withheld": 0,
                 "rule": "flagged rows follow their clean siblings inside their own family's "
                         "slots; no row is removed, so no missed growth is billed"}


# ------------------------------------------------------------------------------------------------
# adoption: the challenger must survive the sealed trap suite
# ------------------------------------------------------------------------------------------------

def sealed_survival(incumbent: mb.ValidatorConfig, check: Sequence[Any],
                    sealed: list[tuple[traps.Case, traps.Truth]]) -> dict[str, Any]:
    """Incumbent vs incumbent+check on the sealed suite. SURVIVES when the challenger's power is
    not lower and its immune score not lower (it may only make the desk harder to fool without
    costing a genuine edge)."""
    chk = (str(check[0]), str(check[1]), float(check[2]))
    base = mb.score(mb.reference_validator(incumbent), cases=sealed)
    chal = mb.score(mb.reference_validator(mb.with_extra(incumbent, chk)), cases=sealed)
    bi, bp = float(base["immune_score"] or 0.0), float(base["power"] or 0.0)
    ci, cp = float(chal["immune_score"] or 0.0), float(chal["power"] or 0.0)
    return {"survives": cp >= bp - 1e-12 and ci >= bi - 1e-12,
            "incumbent": {"immune": round(bi, 4), "power": round(bp, 4)},
            "challenger": {"immune": round(ci, 4), "power": round(cp, 4)},
            "n_cases": len(sealed)}


def verdict_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """identity -> prejudge verdict, over every backtest result row that carries one."""
    return {identity(r): dict(r["prejudge"]) for r in rows
            if isinstance(r, Mapping) and isinstance(r.get("prejudge"), Mapping)}


def pass_summary(verdicts: Iterable[Mapping[str, Any]], rules: Sequence[Mapping[str, Any]]
                 ) -> dict[str, Any]:
    """What one screening pass did, per rule: flagged / screened, and UNINFORMATIVE rules."""
    vs = [v for v in verdicts if isinstance(v, Mapping)]
    screened = sum(1 for v in vs if v.get("status") == "SCREENED")
    per: dict[str, int] = {str(r["id"]): 0 for r in rules}
    for v in vs:
        for f in v.get("flags") or []:
            per[str(f)] = per.get(str(f), 0) + 1
    return {"screened": screened, "unmeasured": sum(1 for v in vs
                                                    if v.get("status") == "UNMEASURED"),
            "flagged": sum(1 for v in vs if v.get("flags")), "rules": len(rules),
            "per_rule": per, "rules_hash": rules_hash(rules),
            "uninformative": sorted(k for k, n in per.items()
                                    if screened and n / screened > UNINFORMATIVE_SHARE)}
