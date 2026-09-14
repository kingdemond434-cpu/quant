"""Why every order this desk has sent did or did not become a fill. The binding stage, named.

`conversion_ledger` picks the binding constraint by its own rule -- the lowest rate on the
critical path, tie-broken by the work it destroys -- and the answer is not in research. It is
order -> fill at 1.9%: 52 attempts, 34 unfilled, 10 rejected, 1 filled. Breadth multiplied by a
1.9% fill rate is still 1.9%, so every certificate, clock and allocation upstream is worth
whatever this number is worth.

AND NOTHING READ THE REASON CODES. `order_intents.jsonl` records a broker retcode per attempt and
no artifact has ever parsed them, so every statement about why orders do not fill -- including
mine, earlier tonight -- was a guess standing next to a file that had the answer.

WHAT THE RECORDS ACTUALLY SAY, measured 2026-09-14 over 39 intents:

    10009 DONE              31    accepted by the broker
    10015 Invalid price      4    entry on the WRONG SIDE of the market
    10027 AutoTrading off    4    the terminal's button, not the desk

Every 10015 was a buy_stop below the ask -- 0.28, 0.24 and 13.78 below -- which is not a stop
order at all. Price had run past the range high between the range completing and the order going
out, the ordinary behaviour of a breakout. `entry_is_legal` exists to refuse exactly that and was
gated on `stops_level > 0`; Fusion reports 0 on every symbol, so it never ran.

ACCEPTED IS NOT FILLED, and conflating them is how a 60% fill rate and a 2% one look alike. A
pending stop that the market never reaches is the strategy DECLINING to enter -- for a breakout
book most brackets expiring untouched is the expected shape, not a failure. This separates the
three states rather than scoring them together:

    REJECTED    the broker refused it            a defect, always
    EXPIRED     accepted, never triggered        usually correct; a rate, not a fault
    FILLED      became a position                the only one that earns

    python desks/mt5/research/fill_attribution.py
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
INTENTS = BASE / "data" / "order_intents.jsonl"
FILLS = BASE / "data" / "fill_corpus.jsonl"
OUT = BASE / "reports" / "FILL_ATTRIBUTION.json"

#: Broker retcode -> (short name, whose fault, what to do). Imported from decision_core when it
#: is importable so the two can never disagree; this fallback keeps the report runnable anywhere.
_FALLBACK_MEANING = {
    10009: ("DONE", "none", "accepted by the broker"),
    10015: ("Invalid price", "desk",
            "the pending entry is on the wrong side of the market or inside the stops band"),
    10016: ("Invalid stops", "desk", "SL or TP inside the stops/freeze distance"),
    10014: ("Invalid volume", "desk", "lot below the venue minimum or off its step"),
    10019: ("No money", "desk", "insufficient free margin for the requested volume"),
    10018: ("Market closed", "venue", "the venue is shut for this symbol"),
    10017: ("Trade disabled", "operator", "account or terminal will not accept orders"),
    10027: ("AutoTrading disabled", "operator", "the terminal's AutoTrading button is off"),
}

#: Retcodes that mean the broker ACCEPTED the order. Everything else is a rejection.
ACCEPTED = (10009,)


def _meaning() -> dict[int, tuple[str, str, str]]:
    try:
        import sys
        sys.path.insert(0, str(BASE))
        from mt5desk.decision_core import RETCODE_MEANING
        merged = dict(_FALLBACK_MEANING)
        for code, val in RETCODE_MEANING.items():
            short = val[0] if isinstance(val, (list, tuple)) and val else str(val)
            prev = merged.get(int(code))
            merged[int(code)] = (short, prev[1] if prev else "desk",
                                 val[1] if isinstance(val, (list, tuple)) and len(val) > 1
                                 else (prev[2] if prev else ""))
        return merged
    except Exception:
        return dict(_FALLBACK_MEANING)


def _rows(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _side_verdict(r: dict[str, Any]) -> str:
    """For a rejected pending order: was its price on the legal side of the market?

    This is the difference between "the broker was unhappy" and "we sent a buy_stop below the
    ask", and only the second is actionable.
    """
    side = str(r.get("side") or "")
    px, bid, ask = r.get("intended"), r.get("decision_bid"), r.get("decision_ask")
    if None in (px, bid, ask):
        return "UNMEASURED: no decision prices recorded on this intent"
    px, bid, ask = float(px), float(bid), float(ask)
    if side == "buy_stop" and px <= ask:
        return f"WRONG SIDE: buy_stop {px:.5f} at or below ask {ask:.5f} ({px - ask:+.5f})"
    if side == "sell_stop" and px >= bid:
        return f"WRONG SIDE: sell_stop {px:.5f} at or above bid {bid:.5f} ({px - bid:+.5f})"
    if side == "buy_limit" and px >= ask:
        return f"WRONG SIDE: buy_limit {px:.5f} at or above ask {ask:.5f}"
    if side == "sell_limit" and px <= bid:
        return f"WRONG SIDE: sell_limit {px:.5f} at or below bid {bid:.5f}"
    return "side legal at decision time"


def attribute() -> dict[str, Any]:
    """The funnel from the CORPUS, the causes from the INTENTS, and the gap between them named.

    THE TWO LEDGERS CANNOT BE ROW-JOINED, and that is a finding rather than an inconvenience.
    `fill_corpus.jsonl` carries `intent_id` and an authoritative `status`; `order_intents.jsonl`
    carries the broker `retcode` and no `intent_id` at all. The only shared field is `ticket`, and
    a rejected order has ticket 0 -- so the rows that most need explaining are exactly the rows
    that cannot be joined.

    So this reports both censuses side by side and does not pretend to a per-row marriage it
    cannot make. An earlier version DID pretend: it joined on ticket, called 31 orders FILLED and
    published a 100% fill rate against a corpus holding exactly one fill.
    """
    meaning = _meaning()
    intents = _rows(INTENTS)
    fills = _rows(FILLS)

    # THE FUNNEL. The corpus is the only ledger that knows what became of an order after the
    # broker answered, so it owns the states and nothing here overrides them.
    corpus = Counter(str(f.get("status") or "UNKNOWN").upper() for f in fills)
    n_corpus = len(fills) or 1
    filled = corpus.get("FILLED", 0)
    rejected_n = corpus.get("REJECTED", 0)
    unfilled = corpus.get("UNFILLED", 0)
    accepted_n = filled + unfilled

    # THE CAUSES. Retcodes explain the rejections; nothing else can.
    codes = Counter()
    blame = Counter()
    diagnoses: list[dict[str, Any]] = []
    for r in intents:
        rc = r.get("retcode")
        rc = int(rc) if isinstance(rc, (int, float)) else None
        if rc in ACCEPTED or rc is None:
            continue
        short, who, remedy = meaning.get(rc, ("UNKNOWN", "unmeasured",
                                              "no standing meaning for this code"))
        codes[f"{rc} {short}"] += 1
        blame[who] += 1
        diagnoses.append({
            "symbol": r.get("symbol"), "sleeve": r.get("sleeve"), "side": r.get("side"),
            "retcode": rc, "retcode_name": short, "attributable_to": who, "remedy": remedy,
            "diagnosis": _side_verdict(r),
        })

    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("ACCEPTED is not FILLED. A pending stop the market never reaches is the strategy "
                 "DECLINING to enter -- for a breakout book most brackets expiring untouched is "
                 "the expected shape, not a failure. Only REJECTED is always a defect."),
        "funnel": {
            "orders": len(fills),
            "rejected": rejected_n,
            "accepted": accepted_n,
            "unfilled": unfilled,
            "filled": filled,
            "unresolved": corpus.get("UNRESOLVED", 0),
        },
        "rates": {
            "rejection_rate": round(rejected_n / n_corpus, 4),
            "fill_rate_of_all_orders": round(filled / n_corpus, 4),
            "fill_rate_of_accepted": round(filled / max(accepted_n, 1), 4),
        },
        "why_rejected": {
            "by_code": dict(codes),
            "attributable_to": dict(blame),
            "records": diagnoses,
        },
        "why_unfilled": {
            "count": unfilled,
            "cause": ("accepted and never triggered: price did not reach the entry before the "
                      "bracket expired. For a session-range breakout this is the range NOT "
                      "breaking, which is the common case and not a defect"),
            "is_defect": False,
        },
        # THE JOIN GAP, NAMED. Fixing it means stamping intent_id onto order_intents at write
        # time; until then no per-order cause can be attached to an UNFILLED row.
        "ledger_join": {
            "joinable": False,
            "why": ("order_intents.jsonl carries no intent_id and fill_corpus.jsonl carries no "
                    "retcode; the only shared field is ticket, which is 0 on every rejection"),
            "n_intents": len(intents),
            "n_corpus_rows": len(fills),
            "remedy": "stamp intent_id onto order_intents at write time",
        },
        "corpus_status_census": dict(corpus),
    }


def main() -> int:
    doc = attribute()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    f = doc["funnel"]
    print(f"fill attribution: {f['orders']} order(s)")
    print(f"  REJECTED   {f['rejected']:3}   (a defect, always)")
    print(f"  UNFILLED   {f['unfilled']:3}   (accepted, never triggered -- not a defect)")
    print(f"  FILLED     {f['filled']:3}")
    print(f"  UNRESOLVED {f['unresolved']:3}")
    r = doc["rates"]
    print(f"  rejection {r['rejection_rate']:.1%} | fill of all {r['fill_rate_of_all_orders']:.1%}"
          f" | fill of accepted {r['fill_rate_of_accepted']:.1%}")
    if doc["why_rejected"]["by_code"]:
        print("  why rejected:")
        for k2, v in doc["why_rejected"]["by_code"].items():
            print(f"    {k2:36} {v}")
        print(f"    attributable to: {doc['why_rejected']['attributable_to']}")
    if not doc["ledger_join"]["joinable"]:
        print(f"  NOTE: {doc['ledger_join']['why']}")
    print(f"  -> {OUT}")
    return 1 if f["rejected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
