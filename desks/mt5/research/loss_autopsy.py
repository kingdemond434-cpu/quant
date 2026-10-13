"""LOSS AUTOPSY: EVERY LIVE LOSS IS A DEFECT, A DECAYING EDGE, OR THE MARKET (principal 2026-10-13).

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

Artifact: desks/mt5/reports/LOSS_AUTOPSY.json. Exit 1 while any DEFECT is unresolved.
"""
from __future__ import annotations

import argparse
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
SLEEVES = BASE / "data" / "sleeves.json"
CERT_BOOK = BASE / "data" / "CERT_BOOK_LIVE.json"
ACCOUNT = BASE / "data" / "account_state.json"
DRIFT = BASE / "reports" / "DRIFT.json"
RESOLVED = BASE / "data" / "loss_defects_resolved.json"
FIX_QUEUE = BASE / "data" / "loss_fix_queue.jsonl"
OUT = BASE / "reports" / "LOSS_AUTOPSY.json"

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


def build(now: datetime | None = None, *, deals: list[dict[str, Any]] | None = None,
          intents: list[dict[str, Any]] | None = None, sleeves_doc: Any = None,
          cert: Any = None, account: Any = None, drift: Any = None,
          resolved: Any = None, e8_ledger: list[dict[str, Any]] | None = None
          ) -> dict[str, Any]:
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
            t = int(i.get("ticket") or 0)
        except (TypeError, ValueError):
            continue
        if t and int(_f(i.get("retcode")) or 0) == 10009:
            by_ticket[t] = i
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
        if t is None or t < since or r is None or r >= LOSS_R:
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
        historical = t < FIX_SINCE
        open_defects = [] if historical else [f for f in found if not f.get("resolved_by")]
        decay = None if found else edge_decay(sleeve or "", history.get(
            str(d.get("sleeve") or ""), []), exp.get(sleeve or ""), drift)
        verdict = DEFECT if found else EDGE_DECAY if decay else NATURAL
        rows.append({"venue": "fusion", "deal": str(d.get("deal")),
                     "position_id": d.get("position_id"), "time": d.get("time"),
                     "sleeve": sleeve, "symbol": d.get("symbol"), "r": r,
                     "pl": _f(d.get("pl_quote")), "verdict": verdict,
                     "open": bool(open_defects), "historical": historical,
                     "defects": found, "edge_decay": decay,
                     "unmeasured": unmeasured,
                     "intent_id": (intent or {}).get("intent_id")})
    fix_rows = [{"fix_id": f"loss:{r['deal']}:{f['defect']}", "venue": r["venue"],
                 "deal": r["deal"], "sleeve": r["sleeve"], "symbol": r["symbol"],
                 "defect": f["defect"], "why": f["why"], "pl": r["pl"], "time": r["time"]}
                for r in rows if r["open"] for f in r["defects"] if not f.get("resolved_by")]
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
    counts = defaultdict(int)
    for r in rows:
        counts[r["verdict"]] += 1
    open_n = sum(1 for r in rows if r["open"])
    return {"at": now.isoformat(timespec="seconds"), "window_days": WINDOW_DAYS,
            "verdict": "FAIL" if fix_rows else "PASS",
            "losses": len(rows), "by_verdict": dict(counts), "open_defect_losses": open_n,
            "fix_queue": fix_rows, "e8": e8, "cap": cap, "rows": rows,
            "edge_decay_by_sleeve": {r["sleeve"]: r["edge_decay"] for r in rows
                                     if r["edge_decay"]},
            "consumer": ("data/loss_fix_queue.jsonl -> the cloud fix routine -> OWNERSHIP ledger "
                         "and a built fix; EDGE_DECAY is the hazard pf_allocator already prices "
                         "through drift_monitor.hazard_by_sleeve"),
            "rule": ("every live losing close is DEFECT, EDGE_DECAY or NATURAL; an unresolved "
                     "DEFECT fails this leg until data/loss_defects_resolved.json names the "
                     "commit that fixed it. Principal 2026-10-13.")}


def publish(doc: dict[str, Any], out: Path = OUT, queue: Path = FIX_QUEUE) -> int:
    """Write the report and append each NEW fix row once (idempotent on fix_id)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    seen = {str(r.get("fix_id")) for r in _jsonl(queue)}
    new = [r for r in doc["fix_queue"] if r["fix_id"] not in seen]
    if new:
        queue.parent.mkdir(parents=True, exist_ok=True)
        with queue.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps({**r, "queued_at": doc["at"]}, default=str,
                                    separators=(",", ":")) + "\n")
    return len(new)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--queue", type=Path, default=FIX_QUEUE)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    queued = 0 if a.no_write else publish(doc, a.out, a.queue)
    print(f"loss autopsy: {doc['verdict']} -- {doc['losses']} loss(es) in {WINDOW_DAYS}d "
          f"{doc['by_verdict']}; {len(doc['fix_queue'])} open fix row(s), {queued} newly queued")
    for r in doc["rows"]:
        if r["open"]:
            print(f"  DEFECT {r['time']} {r['sleeve']} {r['pl']}: "
                  f"{[f['defect'] for f in r['defects'] if not f.get('resolved_by')]}")
    return 1 if doc["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
