"""TRADE VERDICTS: EVERY LIVE TRADE IS A DEFECT, SUB-OPTIMAL, A DECAYING EDGE, OR THE MARKET.

Principal 2026-10-13, widened the same minute to "or unoptimalities": winners are judged too, a
trade that made money but was sized timidly, exited early at a tightened stop, sent slowly,
filled late or paid more spread or slippage than its stop can carry is SUBOPTIMAL, and a
certified signal whose send the venue refused is a MISSED trade. SUBOPTIMAL findings queue fix
rows exactly as defects do. Run inside the hourly `trade_autopsy` leg, which publishes the
verdicts in reports/TRADE_AUTOPSY.json.


The principal's words: "it fixes its own losses if theyre bottlenecks flaws defects etc". The
night of 2026-10-12 the desk lost 74.58 EUR on one AUDCHF gap-decay trade and nobody could say,
without an afternoon of reading, whether that was the certified -1R or a fault. It was both: the
geometry was the certificate's, and the size was 13.0% of equity against the 10% envelope,
because a macro multiplier ran after the cap (fixed 441071a47). This organ asks the same
questions of every losing close, every hour, and answers each with one of three verdicts:

    DEFECT      something on this side made the loss bigger or made it happen at all -- fixable:
                  oversize          risk / equity at entry above MAX_RISK_FRAC (sizing.py)
                  over_allocation   risk / equity above 1.25x the fraction the book funds
                  entry_slippage    filled worse than the intent's price by > SLIP_R of risk
                  stale_quote       the send took longer than STALE_MS from decision to ack
                  stop_widened      the closing stop sits further from entry than the intent's
                  exit_beyond_stop  gross loss beyond EXIT_R: the stop did not hold
                  cost              commission + swap above COST_R of risk
                  clock             the ledger's broker entry stamp is not the intent's UTC
                                    time shifted by the broker's +2h/+3h
                  untraced          no order intent joins the close by ticket
                  unattributed      the close carries no sleeve, or a stem two roster names share
    EDGE_DECAY  no defect, and the sleeve's edge is going: drift_monitor's own hazard calls it
                AT_RISK or BREAKING, or its live mean R sits more than DECAY_Z standard errors
                under its certified expectancy. The allocator already prices that hazard as the
                sleeve's own decay probability (`pf_allocator.hazard_by_sleeve`); this names
                which losses it explains.
    NATURAL     a clean loss inside the certified distribution: the -1R the certificate pays.

A DEFECT FAILS LOUDLY until it is resolved: exit 1, and a named fix row appended once to
data/loss_fix_queue.jsonl, which the cloud's fix routine reads from origin, enters in the
OWNERSHIP ledger and builds. A fix is recorded in data/loss_defects_resolved.json by deal and
defect with the commit that fixed it; resolution is never inferred from silence.

UNMEASURED IS A VERDICT (L1.28a): a check whose input is absent says so and is never read as
clean. E8's losses come from data/e8_ledger.jsonl (prop/e8_close_ledger.py, written on every E8
pass); until that file exists on the box the E8 half is UNMEASURED and that is a standing fix row.

Published by research/trade_autopsy.py into reports/TRADE_AUTOPSY.json (`verdicts`); that leg
exits 1 while any DEFECT or SUBOPTIMAL finding is unresolved.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.ops.live_ledger_view import ledger_path as _audited_ledger_path  # noqa: E402

LEDGER = _audited_ledger_path(BASE / "data" / "live_ledger.jsonl")
INTENTS = BASE / "data" / "order_intents.jsonl"
E8_LEDGER = BASE / "data" / "e8_ledger.jsonl"
BLOCKED = BASE / "data" / "blocked_entries.jsonl"
#: Blocked-entry stages that are the desk DECIDING (the allocator's zero, the certified state
#: filter, the risk envelope, a venue minimum above the target, a spread guard): listed, never
#: queued. Every other stage is a fault between a fired signal and the venue, and is queued.
DECISION_STAGES = frozenset({"no_heat", "state_gate", "risk_envelope", "symbol_side_cap",
                             "below_min", "quote_spread"})
SLEEVES = BASE / "data" / "sleeves.json"
CERT_BOOK = BASE / "data" / "CERT_BOOK_LIVE.json"
ACCOUNT = BASE / "data" / "account_state.json"
DRIFT = BASE / "reports" / "DRIFT.json"
RESOLVED = BASE / "data" / "loss_defects_resolved.json"
FIX_QUEUE = BASE / "data" / "loss_fix_queue.jsonl"
SHADOW_STATE = BASE / "reports" / "shadow" / "shadow_state.json"
#: How far either side of the clock's entry a live send still counts as the same trade.
CLOCK_MATCH_S = 5400.0
#: How long after the clock's entry a live send may still arrive before the miss is called.
CLOCK_GRACE_S = 7200.0

DEFECT, EDGE_DECAY, NATURAL, UNMEASURED = "DEFECT", "EDGE_DECAY", "NATURAL", "UNMEASURED"
WINDOW_DAYS = 30
#: THE ORGAN'S BIRTH. Closes before it are classified and reported (`historical`), never queued:
#: they belong to lanes and code that have since been stopped or rewritten (the 09-16 forex
#: stand-down, the 0.02-lot gold floor, the pre-trace journal), and a fix queue that opens with
#: forty rows nobody can act on is a queue nobody reads. Every close from here on is queued.
FIX_SINCE = datetime(2026, 10, 12, tzinfo=UTC)
LOSS_R = -0.10            # a close below this R is a loss; above it is a scratch or a win
CAP_TOL = 1.05            # 5% over MAX_RISK_FRAC is lot rounding; beyond it is a sizing fault
ALLOC_TOL = 1.25
SLIP_R = 0.15
STALE_MS = 2000.0
EXIT_R = -1.25
COST_R = 0.20
CLOCK_TOL_S = 900.0
BROKER_OFFSETS_H = (2, 3)  # the venue's clock: UTC+2 winter, UTC+3 summer (NY+7)
DECAY_Z = 2.0
SUBOPTIMAL = "SUBOPTIMAL"
UNDERSIZE = 0.75           # charged under 75% of the fraction the book funds: timid sizing
SLOW_MS = 500.0            # send-to-ack over this is slow; over STALE_MS it is a defect
LATE_FILL_S = 60.0         # a market fill this long after its intent is a late entry
COST_SLIP_R = 0.05         # slippage between this and SLIP_R is a cost, not yet a fault
SPREAD_R = 0.10            # a spread over a tenth of the stop is a costly entry
DECAY_MIN_N = 8
STEM = 27                  # the ledger's sleeve stem (`gateway.COMMENT_MAX` - len("DW"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        pass
    return out


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def max_risk_frac() -> float:
    try:
        from mt5desk.sizing import MAX_RISK_FRAC
        return float(MAX_RISK_FRAC)
    except Exception:                                   # pragma: no cover - import guard
        return 0.10


def risk_account(deal: Mapping[str, Any]) -> float | None:
    """The trade's risk in ACCOUNT currency. `pl_quote` is the venue's deal profit (account
    currency) and `r_multiple` is that profit over the risk the gateway charged, so their ratio
    is the risk itself; a scratch is too small to divide by and reads None."""
    pl, r = _f(deal.get("pl_quote")), _f(deal.get("r_multiple"))
    if pl is None or r is None or abs(r) < 0.05:
        return None
    return abs(pl / r)


def equity_before(deals: list[dict[str, Any]], balance_now: float | None) -> dict[str, float]:
    """Equity just before each close, walked back from today's balance through the closes after
    it. A deposit or withdrawal in between would bias it, so it is labelled `derived` wherever it
    is used and only the ledger's own account is walked."""
    if balance_now is None:
        return {}
    out: dict[str, float] = {}
    running = balance_now
    for d in sorted(deals, key=lambda r: str(r.get("time") or ""), reverse=True):
        pl = _f(d.get("pl_quote")) or 0.0
        running -= pl
        out[str(d.get("deal"))] = running
    return out


def join_intent(deal: Mapping[str, Any], by_ticket: Mapping[int, dict[str, Any]]
                ) -> dict[str, Any] | None:
    for k in ("position_id", "entry_order", "order"):
        try:
            v = int(deal.get(k) or 0)
        except (TypeError, ValueError):
            continue
        if v and v in by_ticket:
            return by_ticket[v]
    return None


def roster_names(sleeves_doc: Any) -> list[str]:
    rows = (sleeves_doc or {}).get("sleeves") if isinstance(sleeves_doc, dict) else None
    return [str(s.get("name")) for s in rows or [] if isinstance(s, dict) and s.get("name")]


def resolve_sleeve(deal: Mapping[str, Any], intent: Mapping[str, Any] | None,
                   names: list[str]) -> tuple[str | None, str | None]:
    """(full sleeve name, why it is unresolved). The intent's own name wins; then the ledger's
    exact `sleeve_full`; then a stem only one roster name carries."""
    if intent and intent.get("sleeve"):
        return str(intent["sleeve"]), None
    if deal.get("sleeve_full"):
        return str(deal["sleeve_full"]), None
    stem = str(deal.get("sleeve") or "")
    if not stem or stem == "UNATTRIBUTED" or stem.startswith("["):
        return None, f"close carries no sleeve ({stem or 'empty'!r})"
    hits = [n for n in names if n == stem or n[:STEM] == stem]
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return stem, None                      # a retired sleeve: named, just not on the roster
    return None, f"stem {stem!r} is carried by {len(hits)} roster names"


def defects(deal: Mapping[str, Any], intent: Mapping[str, Any] | None, *,
            equity: float | None, funded: float | None, cap: float,
            unresolved: str | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Every defect this close shows, and the checks that could not be measured."""
    out: list[dict[str, Any]] = []
    unmeasured: list[str] = []

    def hit(kind: str, why: str, **m: Any) -> None:
        out.append({"defect": kind, "why": why, **m})

    risk = risk_account(deal)
    if risk is None or equity is None or equity <= 0:
        unmeasured.append("oversize")
    else:
        frac = risk / equity
        if frac > cap * CAP_TOL:
            hit("oversize", f"risked {frac:.1%} of equity against the {cap:.0%} envelope",
                risk_frac=round(frac, 4), cap=cap, equity_derived=round(equity, 2))
        if funded and funded > 0 and frac > funded * ALLOC_TOL:
            hit("over_allocation", f"risked {frac:.1%} against the book's {funded:.1%}",
                risk_frac=round(frac, 4), funded=funded)
    if unresolved:
        hit("unattributed", unresolved)
    if intent is None:
        hit("untraced", "no order intent joins this close by ticket")
        unmeasured += ["entry_slippage", "stale_quote", "stop_widened", "clock"]
    else:
        side = 1.0 if int(_f(deal.get("side")) or 0) == 1 else -1.0   # closing sell = long
        # A MARKET ORDER IS JUDGED AGAINST THE QUOTE IT WAS SENT ON (the ask for a buy, the bid
        # for a sell), not the signal's bar price: `intended` is where the signal fired, and the
        # gap from there to the quote is the market moving, not the venue filling badly.
        quote = _f(intent.get("decision_ask") if side > 0 else intent.get("decision_bid"))
        entry, isl = _f(deal.get("entry_price")), _f(intent.get("sl"))
        want = quote if quote is not None else _f(intent.get("intended"))
        pending = str(intent.get("order_type") or "").startswith("pending")
        if entry is None or want is None or isl is None or abs(want - isl) < 1e-12:
            unmeasured.append("entry_slippage")
        elif not pending:
            slip = side * (want - entry) / abs(want - isl)
            if slip < -SLIP_R:
                hit("entry_slippage", f"filled {abs(slip):.2f}R worse than the intent",
                    slip_r=round(slip, 4))
        lat = _f(intent.get("latency_send_to_ack_ms") or intent.get("latency_ms"))
        if lat is None:
            unmeasured.append("stale_quote")
        elif lat > STALE_MS:
            hit("stale_quote", f"{lat:.0f} ms from send to acknowledgement", latency_ms=lat)
        dsl = _f(deal.get("sl"))
        if dsl is None or isl is None or want is None:
            unmeasured.append("stop_widened")
        elif side * (isl - dsl) > 0.02 * abs(want - isl) + 1e-9:
            hit("stop_widened", f"closing stop {dsl} is further from entry than the intent's "
                                f"{isl}", intent_sl=isl, closing_sl=dsl)
        it, et = _ts(intent.get("time")), _ts(deal.get("entry_time"))
        if pending:
            pass                      # a pending order fills when price reaches it, not at send
        elif it is None or et is None:
            unmeasured.append("clock")
        else:
            gap = min(abs((et - it).total_seconds() - h * 3600) for h in BROKER_OFFSETS_H)
            if gap > CLOCK_TOL_S:
                hit("clock", f"broker entry stamp {et.isoformat()} is not the intent's UTC "
                             f"{it.isoformat()} shifted by +2h/+3h ({gap:.0f}s off)")
    risk_q = abs(_f(deal.get("risk_quote")) or 0.0)
    pl = _f(deal.get("pl_quote"))
    costs = (_f(deal.get("commission")) or 0.0) + (_f(deal.get("swap")) or 0.0)
    r = _f(deal.get("r_multiple"))
    if risk is None or pl is None or r is None:
        unmeasured += ["exit_beyond_stop", "cost"]
    else:
        gross_r = r - costs / risk if risk else r
        if gross_r < EXIT_R:
            hit("exit_beyond_stop", f"gross {gross_r:.2f}R: the stop did not hold",
                gross_r=round(gross_r, 4))
        if costs < 0 and abs(costs) / risk > COST_R:
            hit("cost", f"commission + swap {abs(costs) / risk:.2f}R of risk",
                cost_r=round(costs / risk, 4))
    del risk_q
    return out, sorted(set(unmeasured))


def suboptimal(deal: Mapping[str, Any], intent: Mapping[str, Any] | None, *, sleeve: str,
               equity: float | None, funded: float | None) -> list[dict[str, Any]]:
    """What made a trade -- winner or loser -- worse than the certificate's own rules allowed,
    short of a fault: sized timidly, exited early at a tightened stop, sent slowly, filled late,
    paid more slippage or spread than the stop can carry."""
    out: list[dict[str, Any]] = []
    risk = risk_account(deal)
    if risk is not None and equity and funded and funded > 0:
        frac = risk / equity
        if frac < funded * UNDERSIZE:
            out.append({"finding": "undersize", "why": f"risked {frac:.2%} where the book funds "
                        f"{funded:.2%}: growth left unclaimed", "risk_frac": round(frac, 4)})
    if intent is None:
        return out
    side = 1.0 if int(_f(deal.get("side")) or 0) == 1 else -1.0
    quote = _f(intent.get("decision_ask") if side > 0 else intent.get("decision_bid"))
    want = quote if quote is not None else _f(intent.get("intended"))
    isl, dsl = _f(intent.get("sl")), _f(deal.get("sl"))
    entry, fill = _f(deal.get("entry_price")), _f(deal.get("fill_price"))
    pending = str(intent.get("order_type") or "").startswith("pending")
    dist = abs(want - isl) if want is not None and isl is not None else 0.0
    if dist > 0 and not pending and entry is not None and want is not None:
        slip = side * (want - entry) / dist
        if -SLIP_R <= slip < -COST_SLIP_R:
            out.append({"finding": "slippage_cost", "why": f"filled {abs(slip):.2f}R worse "
                        f"than the quote", "slip_r": round(slip, 4)})
    spread = _f(intent.get("spread_at_decision"))
    if dist > 0 and spread is not None and spread / dist > SPREAD_R:
        out.append({"finding": "wide_spread", "why": f"spread {spread / dist:.2f}R of the stop "
                    f"at the decision", "spread_r": round(spread / dist, 4)})
    lat = _f(intent.get("latency_send_to_ack_ms") or intent.get("latency_ms"))
    if lat is not None and SLOW_MS < lat <= STALE_MS:
        out.append({"finding": "slow_send", "why": f"{lat:.0f} ms send to acknowledgement",
                    "latency_ms": lat})
    it, et = _ts(intent.get("time")), _ts(deal.get("entry_time"))
    if not pending and it is not None and et is not None:
        gap = min(abs((et - it).total_seconds() - h * 3600) for h in BROKER_OFFSETS_H)
        if LATE_FILL_S < gap <= CLOCK_TOL_S:
            out.append({"finding": "late_fill", "why": f"filled {gap:.0f}s after its intent",
                        "late_s": round(gap, 1)})
    # A fixed-bracket sleeve's certificate holds its opening stop to target or time exit; a
    # close AT a stop tightened from the sent one is a lookalike exit that left money behind.
    # The gold windows' ratchet is their certified behaviour and is not judged here.
    if (dist > 0 and isl is not None and dsl is not None and fill is not None
            and not sleeve.startswith("gold_") and side * (dsl - isl) > 0.02 * dist
            and abs(fill - dsl) <= 0.05 * dist):
        out.append({"finding": "stop_tightened", "why": f"closed at {dsl}, tightened from the "
                    f"sent stop {isl}", "left_r": round(side * (dsl - isl) / dist, 4)})
    return out


def missed_sends(intents: list[dict[str, Any]], e8_journals: list[dict[str, Any]],
                 since: datetime, blocked: list[dict[str, Any]] | None = None
                 ) -> list[dict[str, Any]]:
    """A certified signal the desk decided to trade and the venue never took: a Fusion intent
    whose send came back without TRADE_RETCODE_DONE, or an E8 send journalled REJECTED."""
    out: list[dict[str, Any]] = []
    for i in intents:
        t, rc = _ts(i.get("time")), int(_f(i.get("retcode")) or 0)
        if t is None or t < since or rc in (0, 10008, 10009):
            continue
        out.append({"venue": "fusion", "time": i.get("time"), "sleeve": i.get("sleeve"),
                    "symbol": i.get("symbol"), "id": i.get("intent_id") or f"{t.isoformat()}:"
                    f"{i.get('sleeve')}", "why": f"send refused, retcode {rc}"})
    for j in e8_journals:
        t = _ts(j.get("at"))
        if t is None or t < since or j.get("status") != "REJECTED":
            continue
        out.append({"venue": "e8", "time": j.get("at"), "sleeve": j.get("sleeve"),
                    "symbol": j.get("symbol"), "id": f"{j.get('at')}:{j.get('sleeve')}",
                    "why": str(j.get("why") or "E8 send rejected")[:200]})
    for b in blocked or []:
        t, stage = _ts(b.get("time")), str(b.get("stage") or "")
        if t is None or t < since or stage in DECISION_STAGES:
            continue
        out.append({"venue": "fusion", "time": b.get("time"), "sleeve": b.get("sleeve"),
                    "symbol": b.get("symbol"), "id": f"{b.get('sleeve')}|{stage}|"
                    f"{b.get('bar') or str(b.get('time'))[:13]}",
                    "why": f"blocked at {stage}: {str(b.get('why') or '')[:200]}"})
    return out


def edge_decay(sleeve: str, history: list[dict[str, Any]], cert_exp: float | None,
               drift: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Drift's own hazard first (the one the allocator prices); the live-vs-certificate test
    when drift has nothing for this sleeve."""
    rows = (drift or {}).get("hazard_by_sleeve") or {}
    row = rows.get(sleeve) or rows.get(sleeve[:STEM])
    if isinstance(row, Mapping) and str(row.get("verdict") or "") in ("AT_RISK", "BREAKING"):
        return {"source": "drift_monitor", "verdict": row.get("verdict"),
                "hazard": row.get("hazard"), "leading_channel": row.get("leading_channel")}
    rs = [r for r in (_f(h.get("r_multiple")) for h in history) if r is not None]
    if cert_exp is None or len(rs) < DECAY_MIN_N:
        return None
    mean = sum(rs) / len(rs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in rs) / (len(rs) - 1)) or 1e-9
    z = (mean - cert_exp) / (sd / math.sqrt(len(rs)))
    if z < -DECAY_Z:
        return {"source": "live_vs_certificate", "n": len(rs), "live_mean_r": round(mean, 4),
                "cert_exp": cert_exp, "z": round(z, 3)}
    return None


def e8_autopsy(ledger: list[dict[str, Any]] | None, *, cert: Mapping[str, Any],
               since: datetime, res_map: Mapping[str, Any]
               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The E8 half: every losing close in data/e8_ledger.jsonl. Every row there is one of this
    desk's own sends (the ledger writes nothing else), so `untraced` cannot arise; the sizing,
    stop and quote checks can."""
    if ledger is None:
        return [], {"status": UNMEASURED,
                    "why": ("data/e8_ledger.jsonl absent: no E8 pass has recorded what came "
                            "back from the venue, so an E8 loss cannot be autopsied")}
    book = (cert.get("e8") or {}) if cert.get("enabled") is True else {}
    rows: list[dict[str, Any]] = []
    for d in ledger:
        t, r = _ts(d.get("time")), _f(d.get("r_multiple"))
        if t is None or t < since or r is None or r >= LOSS_R:
            continue
        sleeve = str(d.get("sleeve") or "")
        found: list[dict[str, Any]] = []
        frac = _f(d.get("risk_frac"))
        funded = next((float(v) for k, v in book.items() if isinstance(v, (int, float))
                       and (k == sleeve or k.lower().startswith(
                           f"{str(d.get('symbol') or '').lower()}_"))), None)
        if frac is not None and funded and frac > funded * ALLOC_TOL:
            found.append({"defect": "over_allocation",
                          "why": f"charged {frac:.2%} against the E8 book's {funded:.2%}"})
        if r < EXIT_R:
            found.append({"defect": "exit_beyond_stop",
                          "why": f"{r:.2f}R: the stop did not hold"})
        lat = _f(d.get("latency_send_to_ack_ms"))
        if lat is not None and lat > STALE_MS:
            found.append({"defect": "stale_quote", "why": f"{lat:.0f} ms send to ack"})
        deal = f"e8:{d.get('position_id')}"
        res = res_map.get(deal) or {}
        for f in found:
            f["resolved_by"] = res.get(f["defect"]) if isinstance(res, dict) else None
        open_ = t >= FIX_SINCE and any(not f.get("resolved_by") for f in found)
        rows.append({"venue": "e8", "deal": deal, "position_id": d.get("position_id"),
                     "time": d.get("time"), "sleeve": sleeve, "symbol": d.get("symbol"),
                     "r": r, "pl": _f(d.get("pl_usd_est")),
                     "verdict": DEFECT if found else NATURAL, "open": open_,
                     "historical": t < FIX_SINCE, "defects": found, "edge_decay": None,
                     "unmeasured": ["oversize", "entry_slippage", "clock"],
                     "intent_id": None})
    return rows, {"status": "MEASURED", "closes": len(ledger), "losses": len(rows)}


def clock_misses(sleeves_doc: Any, shadow: Any, intents: list[dict[str, Any]],
                 blocked: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """A LIVE family sleeve whose own forward clock ENTERED and whose live lane sent nothing.

    Measured 2026-10-13: AUDCHF, EURZAR and USDZAR overnight_gap_decay all run the same family
    with the same parameters, and all three clocks entered on the 01:00 broker bar of 10-13.
    AUDCHF sent at 01:41 broker; EURZAR and USDZAR, LIVE since 10-07, have never sent at all,
    and nothing anywhere said so: a block at a quiet or decision stage is not a refused send,
    so `missed_sends` could not see it. The clock is the replay of the certified trade, so a
    clock entry with no live send in the same window is a missed trade whatever stopped it, and
    the blocked-entry ledger, when it holds a row for that sleeve, names the stage.

    Clock bars are labelled in broker time (`broker_offset_h` 0); a send matches when it falls
    within CLOCK_MATCH_S of the entry at either of the venue's offsets. A LIVE family sleeve
    with no ACTIVE clock is a missed measurement and is listed too.
    """
    out: list[dict[str, Any]] = []
    if not isinstance(shadow, Mapping):
        return out
    for s in ((sleeves_doc or {}).get("sleeves") or []) if isinstance(sleeves_doc, Mapping) \
            else []:
        if not isinstance(s, dict) or str(s.get("status") or "").upper() != "LIVE" \
                or s.get("exec") != "family_market":
            continue
        name, sym = str(s.get("name") or ""), str(s.get("symbol") or "")
        key = f"{sym}.{s.get('family')}.{s.get('selector')}"
        clock = shadow.get(key)
        if not isinstance(clock, Mapping) or str(clock.get("status") or "") != "ACTIVE":
            out.append({"sleeve": name, "symbol": sym, "clock": key, "kind": "unclocked",
                        "id": f"unclocked:{name}",
                        "why": f"LIVE with no ACTIVE forward clock {key}: its edge is unmeasured"})
            continue
        label, live_since = _ts(clock.get("last_entry")), _ts(s.get("promoted_at"))
        if label is None or (live_since and label - timedelta(hours=max(BROKER_OFFSETS_H))
                             < live_since):
            continue
        entries = [label - timedelta(hours=h) for h in BROKER_OFFSETS_H]
        if (now - min(entries)).total_seconds() < CLOCK_GRACE_S:
            continue                                  # the live lane may still be sending
        sent = any(str(i.get("sleeve") or "") == name and (t := _ts(i.get("time")))
                   and any(abs((t - e).total_seconds()) <= CLOCK_MATCH_S for e in entries)
                   for i in intents)
        if sent:
            continue
        stages = sorted({str(b.get("stage")) for b in blocked
                         if str(b.get("sleeve") or "") == name and (t := _ts(b.get("time")))
                         and any(abs((t - e).total_seconds()) <= CLOCK_MATCH_S
                                 for e in entries)})
        out.append({"sleeve": name, "symbol": sym, "clock": key, "kind": "clock_fired",
                    "id": f"{name}|{clock.get('last_entry')}", "entry": clock.get("last_entry"),
                    "blocked_at": stages or UNMEASURED,
                    "why": (f"forward clock {key} entered on bar {clock.get('last_entry')} "
                            f"(broker) and the live sleeve sent no order; blocked at "
                            f"{', '.join(stages) if stages else 'an UNRECORDED stage'}")})
    return out


def build(now: datetime | None = None, *, deals: list[dict[str, Any]] | None = None,
          intents: list[dict[str, Any]] | None = None, sleeves_doc: Any = None,
          cert: Any = None, account: Any = None, drift: Any = None,
          resolved: Any = None, e8_ledger: list[dict[str, Any]] | None = None,
          e8_journals: list[dict[str, Any]] | None = None,
          blocked: list[dict[str, Any]] | None = None,
          shadow: Any = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    deals = [d for d in (deals if deals is not None else _jsonl(LEDGER))
             if d.get("account_kind", "live") == "live"]
    intents = intents if intents is not None else _jsonl(INTENTS)
    sleeves_doc = sleeves_doc if sleeves_doc is not None else _json(SLEEVES)
    cert = cert if cert is not None else (_json(CERT_BOOK) or {})
    account = account if account is not None else (_json(ACCOUNT) or {})
    drift = drift if drift is not None else _json(DRIFT)
    resolved = resolved if resolved is not None else (_json(RESOLVED) or {})
    if e8_ledger is None:
        e8_ledger = _jsonl(E8_LEDGER) if E8_LEDGER.exists() else None
    cap = max_risk_frac()
    names = roster_names(sleeves_doc)
    exp = {str(s.get("name")): _f(s.get("shadow_exp"))
           for s in ((sleeves_doc or {}).get("sleeves") or []) if isinstance(s, dict)}
    by_ticket: dict[int, dict[str, Any]] = {}
    for i in intents:
        try:
            ticket = int(i.get("ticket") or 0)
        except (TypeError, ValueError):
            continue
        if ticket and int(_f(i.get("retcode")) or 0) == 10009:
            by_ticket[ticket] = i
    eq = equity_before(deals, _f(account.get("balance")))
    fusion_book = (cert.get("fusion") or {}) if cert.get("enabled") is True else {}
    since = now - timedelta(days=WINDOW_DAYS)
    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in deals:
        history[str(d.get("sleeve") or "")].append(d)
    res_map = resolved.get("resolved") if isinstance(resolved, dict) else None
    res_map = res_map if isinstance(res_map, dict) else {}
    rows: list[dict[str, Any]] = []
    for d in deals:
        t = _ts(d.get("time"))
        r = _f(d.get("r_multiple"))
        if t is None or t < since or r is None:
            continue
        intent = join_intent(d, by_ticket)
        sleeve, why = resolve_sleeve(d, intent, names)
        key = f"{str(d.get('symbol') or '').upper()}_" \
              f"{'_'.join((sleeve or '').split('_')[1:5])}" if sleeve else ""
        funded = next((float(v) for k, v in fusion_book.items()
                       if sleeve and (k == sleeve or key.startswith(k))
                       and isinstance(v, (int, float))), None)
        found, unmeasured = defects(d, intent, equity=eq.get(str(d.get("deal"))),
                                    funded=funded, cap=cap, unresolved=why)
        deal_res = res_map.get(str(d.get("deal"))) or {}
        for f in found:
            fix = deal_res.get(f["defect"]) if isinstance(deal_res, dict) else None
            f["resolved_by"] = fix
        sub = suboptimal(d, intent, sleeve=sleeve or "", equity=eq.get(str(d.get("deal"))),
                         funded=funded)
        for f in sub:
            fix = deal_res.get(f["finding"]) if isinstance(deal_res, dict) else None
            f["resolved_by"] = fix
        historical = t < FIX_SINCE
        open_defects = [] if historical else [f for f in found + sub
                                              if not f.get("resolved_by")]
        decay = None if found or sub or r >= LOSS_R else edge_decay(
            sleeve or "", history.get(str(d.get("sleeve") or ""), []), exp.get(sleeve or ""),
            drift)
        verdict = (DEFECT if found else SUBOPTIMAL if sub else EDGE_DECAY if decay
                   else NATURAL)
        rows.append({"venue": "fusion", "deal": str(d.get("deal")),
                     "position_id": d.get("position_id"), "time": d.get("time"),
                     "sleeve": sleeve, "symbol": d.get("symbol"), "r": r,
                     "pl": _f(d.get("pl_quote")), "verdict": verdict,
                     "open": bool(open_defects), "historical": historical,
                     "outcome": "loss" if r < LOSS_R else "win" if r > -LOSS_R else "scratch",
                     "defects": found, "suboptimal": sub, "edge_decay": decay,
                     "unmeasured": unmeasured,
                     "intent_id": (intent or {}).get("intent_id")})
    fix_rows = [{"fix_id": f"loss:{r['deal']}:{f['defect']}", "venue": r["venue"],
                 "class": DEFECT, "deal": r["deal"], "sleeve": r["sleeve"],
                 "symbol": r["symbol"], "defect": f["defect"], "why": f["why"], "pl": r["pl"],
                 "time": r["time"]}
                for r in rows if r["open"] for f in r["defects"] if not f.get("resolved_by")]
    fix_rows += [{"fix_id": f"trade:{r['deal']}:{f['finding']}", "venue": r["venue"],
                  "class": SUBOPTIMAL, "deal": r["deal"], "sleeve": r["sleeve"],
                  "symbol": r["symbol"], "defect": f["finding"], "why": f["why"],
                  "pl": r["pl"], "time": r["time"]}
                 for r in rows if r["open"] for f in r["suboptimal"]
                 if not f.get("resolved_by")]
    from prop.e8_close_ledger import JOURNALS as _E8_JOURNALS
    e8_journal_rows = e8_journals if e8_journals is not None else \
        [r for p in _E8_JOURNALS for r in _jsonl(p)]
    blocked = blocked if blocked is not None else _jsonl(BLOCKED)
    missed = missed_sends(intents, e8_journal_rows, max(since, FIX_SINCE), blocked)
    _missed = res_map.get("missed")
    missed_res: dict[str, Any] = _missed if isinstance(_missed, dict) else {}
    fix_rows += [{"fix_id": f"missed:{m['venue']}:{m['id']}", "venue": m["venue"],
                  "class": SUBOPTIMAL, "deal": None, "sleeve": m["sleeve"],
                  "symbol": m["symbol"], "defect": "missed_send", "why": m["why"],
                  "pl": None, "time": m["time"]}
                 for m in missed if not missed_res.get(str(m["id"]))]
    shadow = shadow if shadow is not None else _json(SHADOW_STATE)
    clock_missed = clock_misses(sleeves_doc, shadow, intents, blocked, now)
    fix_rows += [{"fix_id": f"clock:{m['id']}", "venue": "fusion", "class": DEFECT,
                  "deal": None, "sleeve": m["sleeve"], "symbol": m["symbol"],
                  "defect": m["kind"], "why": m["why"], "pl": None, "time": m.get("entry")}
                 for m in clock_missed if not missed_res.get(str(m["id"]))]
    e8_rows, e8 = e8_autopsy(e8_ledger, cert=cert, since=since, res_map=res_map)
    rows += e8_rows
    fix_rows += [{"fix_id": f"loss:e8:{r['deal']}:{f['defect']}", "venue": "e8",
                  "deal": r["deal"], "sleeve": r["sleeve"], "symbol": r["symbol"],
                  "defect": f["defect"], "why": f["why"], "pl": r["pl"], "time": r["time"]}
                 for r in e8_rows if r["open"] for f in r["defects"]
                 if not f.get("resolved_by")]
    if e8["status"] == UNMEASURED:
        fix_rows.append({"fix_id": "loss:e8:no_close_ledger", "venue": "e8", "deal": None,
                         "sleeve": None, "symbol": None, "defect": "untraced",
                         "why": e8["why"], "pl": None, "time": None})
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["verdict"]] += 1
    open_n = sum(1 for row in rows if row["open"])
    return {"at": now.isoformat(timespec="seconds"), "window_days": WINDOW_DAYS,
            "verdict": "FAIL" if fix_rows else "PASS",
            "trades": len(rows), "losses": sum(1 for r in rows if r["r"] < LOSS_R),
            "by_verdict": dict(counts), "open_trades": open_n, "missed_sends": missed,
            "clock_misses": clock_missed,
            "blocked_decisions": [b for b in blocked if str(b.get("stage")) in DECISION_STAGES
                                  and (_ts(b.get("time")) or since) >= since],
            "fix_queue": fix_rows, "e8": e8, "cap": cap, "rows": rows,
            "edge_decay_by_sleeve": {r["sleeve"]: r["edge_decay"] for r in rows
                                     if r["edge_decay"]},
            "consumer": ("data/loss_fix_queue.jsonl -> the cloud fix routine -> OWNERSHIP ledger "
                         "and a built fix; EDGE_DECAY is the hazard pf_allocator already prices "
                         "through drift_monitor.hazard_by_sleeve"),
            "rule": ("every live close, winners included, is DEFECT, SUBOPTIMAL, EDGE_DECAY or "
                     "NATURAL, and every refused send is a missed trade; an unresolved DEFECT "
                     "or SUBOPTIMAL finding fails the leg until data/loss_defects_resolved.json "
                     "names the commit that fixed it. Principal 2026-10-13.")}


def queue_fixes(doc: dict[str, Any], queue: Path = FIX_QUEUE) -> int:
    """Append each NEW fix row once (idempotent on fix_id); the count appended."""
    seen = {str(r.get("fix_id")) for r in _jsonl(queue)}
    new = [r for r in doc["fix_queue"] if r["fix_id"] not in seen]
    if new:
        queue.parent.mkdir(parents=True, exist_ok=True)
        with queue.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps({**r, "queued_at": doc["at"]}, default=str,
                                    separators=(",", ":")) + "\n")
    return len(new)
