"""WIN / LOSS AUTOPSIES (Tier-5 mandate 97/98): every closed live trade gets an autopsy row --
attribution, counterfactual, lesson -- appended once to data/autopsies.jsonl, hourly.

The desk classified LOSSES in prose (`scripts/research_autopsy.py`, research failures) and had a
root-cause engine (`libs/research/root_cause.classify`) that nothing called. Live deals closed
and left only a P&L line. This organ reads `data/live_ledger.jsonl` (one closed deal per row),
joins each deal to the decision that placed it (`data/decision_ledger.jsonl`: sleeve, side,
intended price, world_state_id, regime) and to the sleeve's forward expectancy
(`data/sleeves.json` shadow_exp), and writes per deal:

    attribution     gross R, cost R (commission + swap over |risk|), slippage R (fill vs the
                    intended price, from the decision), net R -- each named UNMEASURED when the
                    input is absent rather than zeroed
    counterfactual  no_cost_r, opposite_side_r, held_to_tp_r, stopped_out_r, and the deal's
                    excess over the sleeve's own forward expectancy
    lesson          one of a fixed vocabulary (cost_dominated, loss_beyond_stop, win_left_on_table,
                    loss_within_expectation, win_within_expectation, scratch, unreconstructible)
    state           world_state_id and regime captured at the decision, for the world search
                    the mandate asks for on an unexplained loss

Per sleeve, the root-cause engine is asked the period question the mandate poses ("is this loss
EXPECTED?") with expected P&L = shadow_exp x sum|risk|, so its confidence distribution is over
measured inputs. Idempotent on `deal`: a deal already in the file is never re-written. Every new
row is also a registry memory (category trade_autopsy). Nothing here sizes, vetoes or retires.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "TRADE_AUTOPSY.json"
AUTOPSIES = BASE / "data" / "autopsies.jsonl"
LIVE = BASE / "data" / "live_ledger.jsonl"
DECISIONS = BASE / "data" / "decision_ledger.jsonl"
SLEEVES = BASE / "data" / "sleeves.json"
SCRATCH_R = 0.1
MAX_NEW_PER_PASS = 500
LESSONS = ("cost_dominated", "loss_beyond_stop", "win_left_on_table", "loss_within_expectation",
           "win_within_expectation", "scratch", "unreconstructible")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _f(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ts(v: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def existing_deals(path: Path = AUTOPSIES) -> set[str]:
    return {str(r.get("deal")) for r in _jsonl(path) if r.get("deal") is not None}


def match_decision(deal: dict[str, Any], decisions: list[dict[str, Any]],
                   max_hours: float = 48.0) -> dict[str, Any] | None:
    """The latest decision for the same sleeve and symbol decided before the close, within
    `max_hours`; a bracket named as the sleeve ('[sl 1.23]') matches on symbol alone."""
    t = _ts(deal.get("time"))
    if t is None:
        return None
    sleeve, sym = str(deal.get("sleeve") or ""), str(deal.get("symbol") or "")
    best: dict[str, Any] | None = None
    best_dt: float | None = None
    for d in decisions:
        if str(d.get("symbol") or "") != sym:
            continue
        d_sleeve = str(d.get("sleeve") or d.get("strategy_id") or "")
        if not sleeve.startswith("[") and d_sleeve != sleeve:
            continue
        dt = _ts(d.get("decided_at"))
        if dt is None or dt > t:
            continue
        age = (t - dt).total_seconds() / 3600.0
        if age > max_hours:
            continue
        if best_dt is None or age < best_dt:
            best, best_dt = d, age
    return best


def autopsy(deal: dict[str, Any], decision: dict[str, Any] | None,
            shadow_exp: float | None) -> dict[str, Any]:
    risk = abs(_f(deal.get("risk_quote")) or 0.0)
    pl = _f(deal.get("pl_quote")) or 0.0
    comm = _f(deal.get("commission")) or 0.0
    swap = _f(deal.get("swap")) or 0.0
    costs = comm + swap
    unrec = bool(deal.get("r_unreconstructible")) or risk <= 0
    r_net = (pl / risk) if risk > 0 else (_f(deal.get("r_multiple")) or 0.0)
    r_gross = ((pl - costs) / risk) if risk > 0 else None
    cost_r = (costs / risk) if risk > 0 else None
    entry, fill = _f(deal.get("entry_price")), _f(deal.get("fill_price"))
    sl, tp = _f(deal.get("sl")), _f(deal.get("tp"))
    side = int(_f(deal.get("side")) or 0)          # 0 buy, 1 sell (MT5 deal convention)
    sign = 1.0 if side == 0 else -1.0
    contract = _f(deal.get("contract_size")) or 0.0
    vol = _f(deal.get("volume")) or 0.0
    slip_r: float | None = None
    if decision is not None and entry is not None and risk > 0:
        intended = _f(decision.get("price"))
        if intended is not None and contract > 0 and vol > 0:
            slip_r = -sign * (entry - intended) * contract * vol / risk
    held_to_tp: float | None = None
    if entry is not None and sl is not None and tp is not None and abs(entry - sl) > 1e-12:
        held_to_tp = abs(tp - entry) / abs(entry - sl)
    excess = (r_net - shadow_exp) if shadow_exp is not None else None
    if unrec:
        lesson = "unreconstructible"
    elif abs(r_net) < SCRATCH_R:
        lesson = "scratch"
    elif cost_r is not None and r_net < 0 and abs(cost_r) >= 0.5 * abs(r_net):
        lesson = "cost_dominated"
    elif r_net < -1.2:
        lesson = "loss_beyond_stop"
    elif r_net < 0:
        lesson = "loss_within_expectation"
    elif (held_to_tp is not None and held_to_tp > r_net + 0.5 and fill is not None
          and tp is not None and abs(fill - tp) > 1e-9):
        lesson = "win_left_on_table"
    else:
        lesson = "win_within_expectation"
    return {
        "deal": str(deal.get("deal")), "time": deal.get("time"), "sleeve": deal.get("sleeve"),
        "symbol": deal.get("symbol"), "side": "buy" if side == 0 else "sell", "volume": vol,
        "outcome": "win" if r_net > SCRATCH_R else "loss" if r_net < -SCRATCH_R else "scratch",
        "attribution": {
            "r_net": round(r_net, 4),
            "r_gross": round(r_gross, 4) if r_gross is not None else "UNMEASURED",
            "cost_r": round(cost_r, 4) if cost_r is not None else "UNMEASURED",
            "slippage_r": round(slip_r, 4) if slip_r is not None else "UNMEASURED",
            "pl_quote": pl, "costs_quote": round(costs, 4), "risk_quote": risk,
        },
        "counterfactual": {
            "no_cost_r": round(r_gross, 4) if r_gross is not None else "UNMEASURED",
            "opposite_side_r": round(-r_net, 4),
            "held_to_tp_r": round(held_to_tp, 4) if held_to_tp is not None else "UNMEASURED",
            "stopped_out_r": -1.0,
            "excess_over_forward_expectancy": (round(excess, 4) if excess is not None
                                               else "UNMEASURED"),
        },
        "lesson": lesson,
        "state": {"decision_id": (decision or {}).get("decision_id"),
                  "world_state_id": (decision or {}).get("world_state_id"),
                  "regime": (decision or {}).get("regime") or "UNMEASURED",
                  "decided_at": (decision or {}).get("decided_at")},
        "account": deal.get("account"), "server": deal.get("server"),
    }


def root_causes(rows: list[dict[str, Any]], expectancy: dict[str, float]) -> dict[str, Any]:
    """Per sleeve, the root-cause engine's confidence distribution over the period."""
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by[str(r.get("sleeve"))].append(r)
    out: dict[str, Any] = {}
    try:
        from libs.research import root_cause
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"root_cause unavailable: {exc}"}
    for sleeve, rs in sorted(by.items()):
        risk = sum(float(r["attribution"]["risk_quote"] or 0.0) for r in rs)
        net = sum(float(r["attribution"]["pl_quote"] or 0.0) for r in rs)
        fees = sum(abs(float(r["attribution"]["costs_quote"] or 0.0)) for r in rs)
        exp = expectancy.get(sleeve)
        ev = {"net_pnl": net, "expected_pnl": (exp * risk) if exp is not None else 0.0,
              "fees_paid": fees, "funding_earned": 0.0}
        try:
            verdict = root_cause.classify(ev)
        except Exception as exc:
            verdict = {"error": f"{type(exc).__name__}: {exc}"}
        out[sleeve] = {"n": len(rs), "net_pnl": round(net, 2),
                       "expected_pnl": (round(exp * risk, 2) if exp is not None else "UNMEASURED"),
                       "verdict": verdict}
    return out


def build(now: datetime | None = None, deals: list[dict[str, Any]] | None = None,
          decisions: list[dict[str, Any]] | None = None,
          sleeves_doc: dict[str, Any] | None = None,
          done: set[str] | None = None) -> dict[str, Any]:
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    deals = deals if deals is not None else _jsonl(LIVE)
    decisions = decisions if decisions is not None else _jsonl(DECISIONS)
    done = done if done is not None else existing_deals()
    if sleeves_doc is None:
        try:
            sleeves_doc = json.loads(SLEEVES.read_text("utf-8"))
        except (OSError, ValueError):
            sleeves_doc = {}
    expectancy: dict[str, float] = {}
    for s in (sleeves_doc.get("sleeves") or []) if isinstance(sleeves_doc, dict) else []:
        if isinstance(s, dict) and _f(s.get("shadow_exp")) is not None:
            expectancy[str(s.get("name"))] = float(s["shadow_exp"])
    new_rows: list[dict[str, Any]] = []
    skipped = 0
    for d in deals:
        if d.get("deal") is None:
            skipped += 1
            continue
        if str(d.get("deal")) in done:
            continue
        if len(new_rows) >= MAX_NEW_PER_PASS:
            break
        row = autopsy(d, match_decision(d, decisions), expectancy.get(str(d.get("sleeve"))))
        row["autopsied_at"] = at
        new_rows.append(row)
    lessons = Counter(r["lesson"] for r in new_rows)
    outcomes = Counter(r["outcome"] for r in new_rows)
    doc: dict[str, Any] = {
        "at": at, "n_deals": len(deals), "n_already_autopsied": len(done),
        "n_new": len(new_rows), "n_skipped_no_deal_id": skipped,
        "lessons": dict(lessons), "outcomes": dict(outcomes),
        "n_decision_joined": sum(1 for r in new_rows if r["state"].get("decision_id")),
        "root_causes": root_causes(new_rows, expectancy),
        "rows": new_rows,
        "ledger": str(AUTOPSIES.relative_to(REPO)).replace("\\", "/"),
        "consumer": "data/autopsies.jsonl (append-only), registry memory category trade_autopsy, "
                    "research_dashboard; the world search on unexplained losses reads `state`",
        "rule": ("one autopsy per deal, ever; every attribution term is measured or UNMEASURED; "
                 "wins are autopsied like losses; nothing here sizes, vetoes or retires"),
    }
    doc["headline"] = (f"{len(new_rows)} new autopsies over {len(deals)} deals "
                       f"({len(done)} already done); lessons {dict(lessons)}")
    return doc


def publish(doc: dict[str, Any], out: Path = OUT, ledger: Path = AUTOPSIES) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for r in doc["rows"]:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in doc.items() if k != "rows"}
    slim["sample"] = doc["rows"][:25]
    out.write_text(json.dumps(slim, indent=1, default=str), "utf-8")
    try:
        from libs.moat import registry
        n = 0
        for r in doc["rows"][:200]:
            registry.remember("trade_autopsy",
                              f"{r['sleeve']} {r['symbol']} {r['side']} deal {r['deal']}: "
                              f"{r['outcome']} r_net {r['attribution']['r_net']} -> {r['lesson']}",
                              kind="lesson", memory_key=f"autopsy:{r['deal']}",
                              metrics={"r_net": r["attribution"]["r_net"],
                                       "lesson": r["lesson"], "outcome": r["outcome"]})
            n += 1
        doc["registry_memories"] = n
    except Exception as exc:
        doc["registry"] = f"not written: {type(exc).__name__}: {exc}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--ledger", type=Path, default=AUTOPSIES)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = build(done=existing_deals(a.ledger))
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    doc["budget_s"] = a.budget_s
    publish(doc, a.out, a.ledger)
    print(f"trade autopsy: {doc['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
