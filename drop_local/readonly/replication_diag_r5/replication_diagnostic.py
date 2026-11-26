"""Why the replication lane disagrees with the engine: a READ-ONLY diagnostic (2026-11-26).

The box dry run of 2026-11-26 judged 11,261 of 13,452 certificates MISMATCH, with rebuilt/recorded
ratios of 0.01-0.43 and groups of 25 identical sign flips. Audit ruled MISMATCH is
UNMEASURED-equivalent until the lane is shown to reproduce what it judges, and asked for three
things this module measures:

  1. certificates whose forward clocks hold fills: the lane's verdict against those ledgers;
  2. the sign-flip groups (many certificates, one identical recorded/rebuilt pair) dumped with
     window, cost basis, direction and timeframe;
  3. the verdicts broken down by family, timeframe and cost basis.

For every sampled certificate it reports, side by side:
  * the recorded in-sample screen Sharpe;
  * the lane's Sharpe under the OLD session rule (selector read as a session) and the NEW one
    (``params["session"]`` only), full history and development window (first 80% of days);
  * the ENGINE's own Sharpe (``external_gauntlet.build_cell`` + ``daily_series``), full and
    development window, with its trade count and cost basis.

The engine is imported HERE ONLY: the lane itself must never import it (FORBIDDEN_IMPORTS), since a
second implementation that reads the first one replicates nothing. This module writes ONE report
file and touches no certificate, registry, verdict book, quarantine or clock.

    python desks/mt5/research/replication_diagnostic.py --per-cell 3 --budget-s 3000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
BASE = DESK.parents[1]
for _p in (str(BASE), str(DESK), str(DESK / "scripts"), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402

OUT = DESK / "reports" / "replication" / "REPLICATION_DIAGNOSTIC.json"
DEV_FRAC = 0.80  # research.gate_policy.LOCKBOX_FRAC = 0.20 held out


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def _dev_sharpe_from_days(days: Mapping[Any, float]) -> tuple[float | None, int]:
    keys = sorted(days)
    if len(keys) < 2:
        return None, len(keys)
    keep = keys[:max(2, int(len(keys) * DEV_FRAC))]
    x = np.asarray([days[k] for k in keep], dtype="float64")
    sd = float(np.std(x, ddof=1))
    return (0.0 if sd == 0 else float(np.mean(x) / sd)), len(keep)


def _lane_days(fills: Sequence[rc.Fill]) -> dict[int, float]:
    days: dict[int, float] = {}
    for f in fills:
        d = int(f.entry_t // 86_400_000_000_000)
        days[d] = days.get(d, 0.0) + f.r
    return days


def lane_side(row: Mapping[str, Any], bars: rc.Bars | None, meta: Mapping[str, Any],
              old_rule: bool) -> dict[str, Any]:
    spec = dict(row.get("shadow_spec") or {})
    fam, sym = str(spec.get("family") or ""), str(spec.get("symbol") or row.get("sym") or "")
    p, why = rc.resolve_spec(fam, spec.get("params"), spec.get("selector"), spec.get("side"),
                             symbol=sym, condition=spec.get("condition"))
    if (old_rule and p is not None and not rc.SPEC_BOOK[fam].selector_params
            and fam not in rc.HUNT16_FAMILIES):
        # r3's rule, reproduced here only so the report shows before and after
        p["_session"] = rc.SESSIONS.get(str(spec.get("selector") or "").lower())
    if p is None or bars is None:
        return {"error": why if p is None else "no bars"}
    cost = rc.cost_spec(meta)
    try:
        _o, fills = rc.rebuild(fam, bars, p, cost.price_units)
    except rc.Unrebuildable as exc:
        return {"error": str(exc)[:200]}
    full, n_days = rc.sharpe(fills)
    dev, n_dev = _dev_sharpe_from_days(_lane_days(fills))
    return {"sharpe_full": _r(full), "sharpe_dev": _r(dev), "n_fills": len(fills),
            "n_days": n_days, "n_dev_days": n_dev, "session": p.get("_session"),
            "cost_price_units": cost.price_units, "cost_basis": cost.basis,
            "mean_r": _r(float(np.mean([f.r for f in fills])) if fills else None)}


def engine_side(row: Mapping[str, Any], eg: Any, meta_all: Mapping[str, Any]) -> dict[str, Any]:
    spec = dict(row.get("shadow_spec") or {})
    fam, sym = str(spec.get("family") or ""), str(spec.get("symbol") or row.get("sym") or "")
    try:
        cell = eg.build_cell(sym, fam, dict(spec.get("params") or {}), dict(meta_all))
    except Exception as exc:  # a diagnostic records the failure, it never stops on one
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    if not cell:
        return {"error": str(getattr(eg, "LAST_BUILD_FAILURE", None) or "build_cell None")[:200]}
    try:
        daily = eg.daily_series(cell["df"], cell["sigs"], cell["costs"])
    except Exception as exc:
        return {"error": f"daily_series {type(exc).__name__}: {str(exc)[:200]}"}
    days = {k: float(v) for k, v in daily.items()}
    x = np.asarray(list(days.values()), dtype="float64")
    full = None if x.size < 2 else (0.0 if float(np.std(x, ddof=1)) == 0
                                    else float(np.mean(x) / np.std(x, ddof=1)))
    dev, n_dev = _dev_sharpe_from_days(days)
    costs = cell.get("costs")
    return {"sharpe_full": _r(full), "sharpe_dev": _r(dev), "n_days": int(x.size),
            "n_dev_days": n_dev, "n_signals": len(cell.get("sigs") or []),
            "cost_basis": cell.get("_cost_basis"), "fill_hour": cell.get("_fill_hour"),
            "spread_pts": getattr(costs, "spread_pts", None)}


def agree(a: float | None, b: float | None) -> bool:
    """The lane's own MISMATCH rule, read as agreement: same sign and ratio in [0.5, 2]."""
    if a is None or b is None:
        return False
    if abs(a) < rc.SHARPE_NOISE and abs(b) < rc.SHARPE_NOISE:
        return True
    if a == 0 or np.sign(a) != np.sign(b):
        return False
    return bool(rc.SHARPE_RATIO[0] <= b / a <= rc.SHARPE_RATIO[1])


def sign_flip_groups(certs: Sequence[Mapping[str, Any]], verdict_book: Mapping[str, Any]
                     ) -> list[list[int]]:
    """Indexes of certificates sharing one identical (recorded, rebuilt) Sharpe pair, 5+."""
    groups: dict[tuple[Any, Any], list[int]] = defaultdict(list)
    for i, r in enumerate(certs):
        v = verdict_book.get(rc.certificate_id(r)) or {}
        if v.get("verdict") != rc.MISMATCH:
            continue
        ours = (v.get("ours") or {}).get("sharpe") if isinstance(v.get("ours"), dict) else None
        theirs = (v.get("theirs") or {}).get("sharpe") if isinstance(v.get("theirs"),
                                                                     dict) else None
        if ours is not None and theirs is not None:
            groups[(round(float(ours), 4), round(float(theirs), 4))].append(i)
    return sorted((g for g in groups.values() if len(g) >= 5), key=len, reverse=True)


def sample(certs: Sequence[Mapping[str, Any]], per_cell: int) -> list[int]:
    seen: Counter[tuple[str, str]] = Counter()
    out: list[int] = []
    for i, r in enumerate(certs):
        spec = r.get("shadow_spec") or {}
        key = (str(spec.get("family") or ""),
               str((spec.get("params") or {}).get("timeframe") or "H1"))
        if seen[key] < per_cell:
            seen[key] += 1
            out.append(i)
    return out


def run(*, per_cell: int, budget_s: float, flip_groups: int, forward_n: int,
        out: Path = OUT) -> dict[str, Any]:
    t0 = time.monotonic()
    import external_gauntlet as eg  # type: ignore[import-not-found]

    meta_all = rc._read_json(rc.UNIVERSE_JSON, {}) or {}
    certs = rc.certificate_rows()
    book_doc = rc._read_json(rc.CURSOR.parent / rc.VERDICTS_NAME, {}) or {}
    book = dict(book_doc.get("certificates") or {}) if isinstance(book_doc, dict) else {}
    groups = sign_flip_groups(certs, book)
    flip_idx = [i for g in groups[:flip_groups] for i in g[:3]]
    order = list(dict.fromkeys(flip_idx + sample(certs, per_cell)))
    loader = rc._cached_loader(rc.load_bars)
    rows: list[dict[str, Any]] = []
    for i in order:
        if time.monotonic() - t0 > budget_s:
            break
        r = certs[i]
        spec = dict(r.get("shadow_spec") or {})
        sym = str(spec.get("symbol") or r.get("sym") or "")
        params = dict(spec.get("params") or {})
        tf = str(params.get("timeframe") or "H1")
        gates = r.get("gates")
        gates = gates if isinstance(gates, dict) else {}
        iss = gates.get("in_sample_screen")
        iss = iss if isinstance(iss, dict) else {}
        bars = loader(sym, tf)
        meta = dict(meta_all.get(sym) or {})
        new = lane_side(r, bars, meta, old_rule=False)
        rows.append({
            "certificate": rc.certificate_id(r), "symbol": sym,
            "family": spec.get("family"), "timeframe": tf, "selector": spec.get("selector"),
            "side": spec.get("side"), "params_session": params.get("session"),
            "in_flip_group": i in set(flip_idx), "recorded_is_sharpe": rc._num(iss.get("sharpe")),
            "recorded_days": r.get("days"),
            "book_verdict": (book.get(rc.certificate_id(r)) or {}).get("verdict"),
            "lane_old_rule": lane_side(r, bars, meta, old_rule=True), "lane_new_rule": new,
            "lane_new_verdict": rc.judge_certificate(rc._num(iss.get("sharpe")),
                                                     new.get("sharpe_full"),
                                                     int(new.get("n_fills") or 0))[0],
            "engine": engine_side(r, eg, meta_all)})
    fwd_rows: list[dict[str, Any]] = []
    for row in rc.forward_rows():
        if len(fwd_rows) >= forward_n or time.monotonic() - t0 > budget_s:
            break
        ident = dict(row.get("identity") or {})
        ledger = rc.ledger_for(str(row.get("key") or ""), ident)
        if not ledger:
            continue
        sym = str(ident.get("symbol") or "")
        res = rc.replicate_forward(row, meta=dict(meta_all.get(sym) or {}),
                                   bars=loader(sym, str(ident.get("timeframe") or "H1")),
                                   ledger=ledger)
        fwd_rows.append({"key": res.get("key"), "family": res.get("family"),
                         "verdict": res.get("verdict"), "why": res.get("why"),
                         "ledger_rows": len(ledger), "divergence": res.get("divergence")})
    breakdown: dict[str, Counter[str]] = defaultdict(Counter)
    for r in certs:
        spec = r.get("shadow_spec") or {}
        v = (book.get(rc.certificate_id(r)) or {})
        basis = ((v.get("ours") or {}).get("cost_basis") if isinstance(v.get("ours"), dict)
                 else None)
        key = (f"{spec.get('family')}|{(spec.get('params') or {}).get('timeframe') or 'H1'}"
               f"|{basis}")
        breakdown[key][str(v.get("verdict") or "UNJUDGED")] += 1

    summary: Counter[str] = Counter()
    for x in rows:
        e, n, o = x["engine"], x["lane_new_rule"], x["lane_old_rule"]
        rec = x["recorded_is_sharpe"]
        summary["sampled"] += 1
        summary["engine_dev_reproduces_recorded"] += int(agree(rec, e.get("sharpe_dev")))
        summary["engine_full_reproduces_recorded"] += int(agree(rec, e.get("sharpe_full")))
        summary["lane_new_dev_matches_engine_dev"] += int(agree(e.get("sharpe_dev"),
                                                                n.get("sharpe_dev")))
        summary["lane_old_dev_matches_engine_dev"] += int(agree(e.get("sharpe_dev"),
                                                                o.get("sharpe_dev")))
        summary["lane_new_verdict_" + str(x["lane_new_verdict"])] += 1
    doc = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "read_only": True, "elapsed_s": round(time.monotonic() - t0, 1),
           "certificates_total": len(certs), "flip_groups_found": len(groups),
           "flip_group_sizes": [len(g) for g in groups[:20]], "summary": dict(summary),
           "rows": rows, "forward": fwd_rows,
           "breakdown_family_timeframe_costbasis": {k: dict(v) for k, v in
                                                     sorted(breakdown.items())}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--per-cell", type=int, default=3, help="certificates per family x timeframe")
    ap.add_argument("--flip-groups", type=int, default=5)
    ap.add_argument("--forward", type=int, default=20, help="forward clocks with ledgers")
    ap.add_argument("--budget-s", type=float, default=3000.0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = run(per_cell=a.per_cell, budget_s=a.budget_s, flip_groups=a.flip_groups,
              forward_n=a.forward, out=a.out)
    print(json.dumps({"out": str(a.out), "elapsed_s": doc["elapsed_s"],
                      "summary": doc["summary"], "flip_group_sizes": doc["flip_group_sizes"],
                      "forward": Counter(str(f["verdict"]) for f in doc["forward"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
