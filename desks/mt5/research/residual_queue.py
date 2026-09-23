"""Q11 -- THE ONE QUEUE OF EVERYTHING THE DESK CANNOT EXPLAIN.

THE PRINCIPAL, 2026-09-16: *Residual = Reality - ExistingModels, at every level. The machine
researches its own ignorance.*

SIX PRODUCERS ALREADY MEASURE A RESIDUAL AND NOT ONE OF THEM IS READ BY THE NEXT: the standing
questions (residual correlates, a drift census, the live losses no factor explains),
`factor_residual` (13,554 instrument-by-driver cells), `unknown_unknowns` (an anomaly queue that
-- measured 2026-09-16 -- IS CONSUMED BY NOTHING), the counterfactual world, the opportunity gap,
and the fill funnel beside the execution tape. Each is a report somebody reads once. None is a
QUEUE, and a residual that is never queued is never worked.

THIS IS THE QUEUE. One row shape, one stable id, so the same ignorance seen in two producers is
one item and the same ignorance seen in ten passes is one item with a recurrence of ten, ordered
the only way that makes sense -- how big it is, how often it returns, and how much of it the
desk's models still fail to account for:

    priority = magnitude x recurrence x unexplained_fraction

An item a later producer explains below 0.2 is EXPLAINED and leaves the front; one nobody has
seen for fourteen days is STALE. Neither is deleted: the record is how the desk knows what it
used to not know. UNMEASURED IS A VERDICT, NOT A ZERO (L1.28a) -- a producer stating no explained
share gets 0.5 with `unexplained_measured: false`, never a confident 1.0, never a silent drop.

WHAT LEAVES, AND WHAT ONLY SITS. The top OPEN items whose level maps to a REGISTERED family are
donated through the shared proposer contract and the ten gates take over. Levels no family
expresses -- slippage, a strategy loss the posterior did not predict -- stay research tasks and
are never given an invented family. A single-name equity may SIT here (its residual is real) and
may never leave in a donation: the two-lane mandate is enforced at the door.

    python desks/mt5/research/residual_queue.py [--dry-run] [--max-donations N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STANDING = DESK / "reports" / "STANDING_QUESTIONS.json"
FACTOR = DESK / "reports" / "factor_residual.json"
UNKNOWN = DESK / "data" / "unknown_unknowns_queue.jsonl"
COUNTERFACTUAL = DESK / "reports" / "COUNTERFACTUAL_WORLD.json"
GAP = DESK / "reports" / "OPPORTUNITY_GAP.json"
MISSED = DESK / "data" / "missed_growth.jsonl"
FILLS = DESK / "reports" / "FILL_ATTRIBUTION.json"
EXECQ = DESK / "reports" / "execution_quality.json"
LEDGER = DESK / "data" / "live_ledger.jsonl"
POSTERIOR = DESK / "reports" / "POSTERIOR_ALPHA.json"
QUEUE = DESK / "data" / "residual_queue.jsonl"
REPORT = DESK / "reports" / "RESIDUAL_QUEUE.json"

SOURCE = "residual_queue"
#: Days unseen before an item is STALE. Two weeks is two hundred-odd hourly passes: an anomaly
#: not seen once in that many looks is no longer the desk's live ignorance.
STALE_DAYS = 14
EXPLAINED_BELOW = 0.2
#: What an UNSTATED explained share is worth. Not 1.0 -- calling a thing wholly unexplained
#: because nobody measured it is the cry-wolf shape this desk keeps paying for.
UNMEASURED_SHARE = 0.5
#: Items one producer may add per pass: `factor_residual` alone publishes 13,554 cells, and a
#: queue nobody can read is a queue nobody reads.
MAX_PER_SOURCE = 120
MAX_DONATIONS = 15
LEVELS = ("returns", "volatility", "spread", "correlation", "slippage", "strategy_loss",
          "macro_reaction")
RULE = ("priority = magnitude x recurrence x unexplained fraction; "
        "the desk researches its ignorance")
UNITS = ("magnitude keeps the PRODUCER's own unit (R, bp, a correlation delta, a vol multiple, "
         "an order count): re-scaling somebody else's measurement invents a number nobody "
         "measured. `priority` therefore ranks comparably WITHIN a level, `by_level` is the "
         "comparable view, and `top` is the raw ordering the rule states.")


# --------------------------------------------------------------------------------- plumbing
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _f(value: Any) -> float | None:
    """A finite float, or None. NaN and inf are absences, not magnitudes."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if x == x and x not in (float("inf"), float("-inf")) else None


def _read_json(path: Path) -> Any:
    """Tolerant: a BOM, a missing file and a half-written one are all 'that source is absent'."""
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _read_rows(path: Path, limit: int = 50_000) -> list[dict]:
    try:
        lines = path.read_text("utf-8-sig", "replace").splitlines()[:limit]
    except OSError:
        return []
    out: list[dict] = []
    for line in lines:
        try:
            row = json.loads(line) if line.strip() else None
        except ValueError:
            row = None
        if isinstance(row, dict):
            out.append(row)
    return out


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def residual_id(level: str, symbol: str, key: str) -> str:
    """Stable across runs, machines and producers: the same ignorance is the same row."""
    return hashlib.sha1(f"{level}|{str(symbol).upper()}|{key}".encode()).hexdigest()[:16]


def _asset_class(symbol: str) -> str:
    try:
        from research.universe_policy import asset_class_of
        return str(asset_class_of(symbol) or "") if symbol else ""
    except Exception:                                                   # pragma: no cover
        return ""


def may_hypothesise(symbol: str) -> bool:
    """FAILS CLOSED. An unreadable registry hunts nothing: absence is not a permission."""
    try:
        from research.universe_policy import may_hypothesise as _may
        return bool(symbol) and bool(_may(symbol))
    except Exception:                                                   # pragma: no cover
        return False


def registered_families() -> set[str]:
    """Every family the desk can call, minus the banned -- read off the registries the way
    `research/breadth_sweep.default_families` reads them, never from a list kept here."""
    try:
        from mt5desk import families as fam_mod
        from mt5desk import families_orthogonal as fo
        names = {str(k) for k in getattr(fam_mod, "FAMILY_REGISTRY", {})}
        names |= {str(k) for k in getattr(fo, "ORTHOGONAL_FAMILIES", {})}
    except Exception:                                                   # pragma: no cover
        return set()
    try:
        from research.family_policy import family_banned
        return {n for n in names if not family_banned(n)}
    except Exception:                                                   # pragma: no cover
        return names


def item(level: str, symbol: Any, key: str, magnitude: Any, unit: str, share: Any,
         source: str, why: str, *, family: str | None = None,
         params: dict | None = None, measured: bool = True) -> dict | None:
    """One normalised residual. None when the producer's own number is not a number."""
    mag = _f(magnitude)
    if mag is None or level not in LEVELS or not key:
        return None
    sym = str(symbol or "").strip()
    frac = _f(share)
    frac = UNMEASURED_SHARE if frac is None else min(max(frac, 0.0), 1.0)
    return {"residual_id": residual_id(level, sym, key), "level": level, "symbol": sym,
            "asset_class": _asset_class(sym), "key": str(key),
            "magnitude": round(abs(mag), 6), "magnitude_unit": unit,
            "unexplained_fraction": round(frac, 4), "unexplained_measured": bool(measured),
            "source": source, "why": why, "family": family, "params": dict(params or {})}


# ------------------------------------------------------------------------------- producers
# HOW EACH PRODUCER'S OWN NUMBER BECOMES "the share still unexplained", stated once so a reader
# can argue with the mapping instead of reverse-engineering it out of nine call sites:
#   Q1 lift / factor_residual / the fill funnel   UNMEASURED -> 0.5 (no variance share is stated)
#   Q2, Q3 correlation                            1 - r**2 (the lead, or the axis, explains r^2)
#   Q4 drift, Q6 uncovered flow, missed growth    1.0 (no registered family reads it at all)
#   counterfactual, posterior shortfall           1.0 (the gap IS what the model did not predict)
#   unknown_unknowns                              1.0, except `unexplained_move` -> 0.5, which is
#       the PRODUCER's own caveat: with no readable event ledger, "unexplained" is by construction
#   execution quality                             1.0 where no markout exists at any horizon
def _anchor(session: Any) -> dict:
    """`{"anchor_hour": h}` when the desk's own session table names one, else nothing. A
    parameter restated here is right the day it is written and forks when the family changes."""
    try:
        from mt5desk.family_call import SESSIONS
        return {"anchor_hour": int(SESSIONS[str(session)][0])}
    except Exception:
        return {}


def _standing() -> list[dict]:
    qs = (_read_json(STANDING) or {}).get("questions")
    if not isinstance(qs, dict):
        return []
    out: list[dict | None] = []
    for f in (qs.get("Q1") or {}).get("findings") or []:
        out.append(item("volatility", f.get("target"), f"precursor:{f.get('feature')}",
                        f.get("lift"), "lift", None, "standing_questions:Q1",
                        f"{f.get('feature')} leads this volatility at lift {f.get('lift')} "
                        f"(perm p {f.get('p_perm')}); no registered family reads that feature",
                        family="vol_transition", measured=False))
    # Q2 CARRIES NO FAMILY, DELIBERATELY. The tradable form of "X leads the dollar basket" is a
    # cell on each basket member, and `standing_questions` already donates exactly that. The
    # queue records the ignorance; it does not charge one trial budget twice.
    for f in (qs.get("Q2") or {}).get("findings") or []:
        r = _f(f.get("corr")) or 0.0
        out.append(item("returns", f.get("symbol"), f"leads_usd_basket@{f.get('lead_bars')}",
                        r * 1e4, "1e-4 corr", 1.0 - r ** 2, "standing_questions:Q2",
                        f"leads the dollar basket by {f.get('lead_bars')} bar(s), r={r:+.3f}"))
    for f in (qs.get("Q3") or {}).get("findings") or []:
        r = _f(f.get("corr")) or 0.0
        out.append(item("returns", f.get("symbol"), f"axis:{f.get('axis')}", r * 1e4,
                        "1e-4 corr", 1.0 - r ** 2, "standing_questions:Q3",
                        f"after the dollar/gold/equity factors the daily residual still "
                        f"correlates {r:+.3f} with {f.get('axis')}", family="cross_asset_residual"))
    for f in (qs.get("Q4") or {}).get("findings") or []:
        drift = f.get("measure") == "close_to_open"
        out.append(item("returns", f.get("symbol"),
                        f"drift:{f.get('session')}:{f.get('measure')}", f.get("mean_bp"), "bp",
                        1.0, "standing_questions:Q4",
                        f"{f.get('session')} {f.get('measure')} averages {f.get('mean_bp')} bp "
                        f"over {f.get('n_days')} day(s) at t={f.get('t')}",
                        family="overnight_drift" if drift else None,
                        params=_anchor(f.get("session")) if drift else None))
    for f in (qs.get("Q5") or {}).get("findings") or []:
        out.append(item("strategy_loss", f.get("symbol"), f"unexplained_loss:{f.get('sleeve')}",
                        f.get("mean_r") or f.get("loss_r") or f.get("residual_r"), "R", 1.0,
                        "standing_questions:Q5",
                        "a live loss no factor the desk regresses R on accounts for"))
    for f in (qs.get("Q6") or {}).get("findings") or []:
        if not f.get("covered"):
            out.append(item("macro_reaction", (f.get("symbols") or [""])[0],
                            f"forced_flow:{f.get('kind')}", f.get("events_per_quarter"),
                            "events/quarter", 1.0, "standing_questions:Q6",
                            f"{f.get('events')} forced-flow event(s), actor: "
                            f"{str(f.get('forced_actor') or '')[:120]}",
                            family=str(f.get("family") or "") if f.get("registered") else None))
    return [r for r in out if r]


def _factor() -> list[dict]:
    doc = _read_json(FACTOR) or {}
    rows = doc.get("all") if isinstance(doc.get("all"), list) else (doc.get("proposals") or [])
    ranked = sorted((r for r in rows if isinstance(r, dict)),
                    key=lambda r: -abs(_f(r.get("t_gross")) or 0.0))[:MAX_PER_SOURCE]
    out: list[dict | None] = []
    for r in ranked:
        drivers = [str(d) for d in (r.get("drivers") or []) if d]
        # A CELL THE PRODUCER ITSELF REFUSED IS NOT RE-DONATED. `factor_residual` writes
        # `not_proposed_why` (a cost basis it does not trust, a t below its bar) precisely so the
        # cell is charged as a trial and never traded; handing it back to the intake re-charges
        # the budget for a decision already taken. It stays queued, with no family.
        refused = bool(r.get("not_proposed_why"))
        fam = None if refused else ("lead_lag" if len(drivers) == 1 else "cross_asset_residual")
        params = {"driver_symbol": drivers[0]} if fam == "lead_lag" else {
            dst: r[src] for src, dst in (("entry_z", "entry_z"), ("horizon_bars", "ttl_bars"),
                                         ("side_mode", "side_mode"))
            if fam and r.get(src) is not None}
        out.append(item("returns", r.get("target"), f"driver_set:{r.get('driver_set')}",
                        (_f(r.get("gross_per_trade")) or 0.0) * 1e4, "bp", None,
                        "factor_residual",
                        f"{r.get('cell')}: residual against {', '.join(drivers) or 'its drivers'}"
                        f" at t={r.get('t_gross')} over {r.get('n_independent')} trade(s)"
                        + (f"; producer refused it: {str(r.get('not_proposed_why'))[:80]}"
                           if refused else ""),
                        family=fam, params=params, measured=False))
    return [r for r in out if r]


#: The anomaly kinds `unknown_unknowns` appends, and the level each is a residual AT.
_UNKNOWN_LEVEL = {"unexplained_move": "returns", "decoupling": "correlation",
                  "dispersion_break": "volatility", "cost_shock": "spread"}


def _unknown() -> list[dict]:
    out: list[dict | None] = []
    for r in _read_rows(UNKNOWN):
        kind = str(r.get("kind") or "")
        level = _UNKNOWN_LEVEL.get(kind)
        if not level:
            continue
        sym, peer = str(r.get("symbol") or ""), ""
        if "|" in sym:                                  # a decoupling names the pair as "A|B"
            sym, peer = (p.strip() for p in sym.split("|", 1))
        why = str(r.get("question") or "")[:240]
        if kind == "unexplained_move":
            out.append(item(level, sym, f"move:{r.get('at')}", (_f(r.get("return")) or 0.0) * 1e4,
                            "bp", UNMEASURED_SHARE, "unknown_unknowns", why,
                            family="cross_asset_residual", measured=False))
        elif kind == "decoupling":
            out.append(item(level, sym, f"decoupled:{sym}|{peer}", r.get("delta"), "corr delta",
                            1.0, "unknown_unknowns", why, family="relative_value",
                            params={"peer_symbol": peer} if peer else None))
        elif kind == "dispersion_break":
            out.append(item(level, sym, "vol_regime_break", r.get("multiple"), "x band", 1.0,
                            "unknown_unknowns", why, family="vol_transition"))
        else:
            out.append(item(level, sym, f"cost_shock:{r.get('at') or r.get('hour')}",
                            r.get("multiple") or r.get("spread_multiple"), "x median", 1.0,
                            "unknown_unknowns", why))
    return [r for r in out if r]


def _counterfactual() -> list[dict]:
    doc = _read_json(COUNTERFACTUAL) or {}
    out: list[dict | None] = [
        item("strategy_loss", d.get("symbol"),
             f"counterfactual:{d.get('best_class')}:{d.get('sleeve')}",
             d.get("abs_d_elog_max"), "dElogW", 1.0, "counterfactual_world",
             f"the desk chose {d.get('chosen')} on {d.get('sleeve')}; {d.get('best_arm')} was "
             f"worth {d.get('best_d_elog')} in E[log W]")
        for d in doc.get("top_decisions") or [] if isinstance(d, dict)]
    for name, blk in (doc.get("headline_by_class") or {}).items():
        if isinstance(blk, dict) and _f(blk.get("alpha")) is not None:
            ok = blk.get("status") == "MEASURED"
            out.append(item("strategy_loss", "", f"counterfactual_class:{name}", blk.get("alpha"),
                            "dElogW", 1.0 if ok else UNMEASURED_SHARE, "counterfactual_world",
                            str(blk.get("reads") or name)[:200], measured=ok))
    return [r for r in out if r]


def _gap() -> list[dict]:
    out: list[dict | None] = []
    # ONLY THE BINDING CAUSES. The gap report's own argument is that the EARLIEST broken link is
    # the one to fix; queuing the five that are not binding buries the two that are.
    for c in (_read_json(GAP) or {}).get("components") or []:
        if not isinstance(c, dict) or not c.get("binding"):
            continue
        cause, ok = str(c.get("cause") or ""), c.get("status") == "MEASURED"
        out.append(item("slippage" if cause == "EXECUTION" else "strategy_loss", "",
                        f"gap:{cause}", c.get("measured"), "gap units",
                        1.0 if ok else UNMEASURED_SHARE, "opportunity_gap",
                        str(c.get("why") or "")[:240], measured=ok))
    return [r for r in out if r]


def _missed() -> list[dict]:
    return [r for r in (item("strategy_loss", "", f"rail:{x.get('rail')}", x.get("value"), "R",
                             1.0, "missed_growth",
                             f"growth the {x.get('rail')} rail refused on {x.get('day')}; "
                             f"Growth Rule 1 asks it to prove forward E[log W] rose")
                        for x in _read_rows(MISSED)) if r]


def _fills() -> list[dict]:
    doc = _read_json(FILLS) or {}
    out: list[dict | None] = [
        item("slippage", "", f"reject:{code}", n, "orders", UNMEASURED_SHARE, "fill_attribution",
             f"{n} order(s) refused with '{code}'. The funnel counts the refusal; nothing prices "
             f"what it cost", measured=False)
        for code, n in ((doc.get("why_rejected") or {}).get("by_code") or {}).items()]
    u = doc.get("why_unfilled") or {}
    out.append(item("slippage", "", f"unfilled:{u.get('cause')}", u.get("count"), "orders",
                    UNMEASURED_SHARE, "fill_attribution",
                    f"{u.get('count')} accepted order(s) never filled: "
                    f"{str(u.get('cause'))[:160]}", measured=False))
    return [r for r in out if r]


def _execq() -> list[dict]:
    out: list[dict | None] = []
    for cell, blk in ((_read_json(EXECQ) or {}).get("by_symbol_session") or {}).items():
        if not isinstance(blk, dict):
            continue
        sym, _, sleeve = str(cell).partition(".")
        # NO MARKOUT AT ANY HORIZON MEANS NOTHING ATTRIBUTES THE FILL'S COST, so the whole of the
        # slippage is unexplained -- a measurement, not an assumption. Where markouts exist the
        # attribution exists somewhere and the SHARE of it is what nobody states.
        seen = any(_f((m or {}).get("n")) for m in (blk.get("markouts_R") or {}).values()
                   if isinstance(m, dict))
        out.append(item("slippage", sym, f"slippage:{sleeve or cell}",
                        (blk.get("slippage_R") or {}).get("mean"), "R",
                        UNMEASURED_SHARE if seen else 1.0, "execution_quality",
                        f"{blk.get('fills')} fill(s) on {cell}; markout "
                        f"{'measured' if seen else 'ABSENT at every horizon'}", measured=not seen))
    return [r for r in out if r]


def _losses() -> list[dict]:
    """Sleeves whose realised R is below the posterior the desk holds for them.

    THE BROKER TRUNCATES THE COMMENT AT 27 CHARACTERS, which is why this matches on a prefix and
    not only on equality: the ledger carries `chfnok_carry_asia_p_98d776f` for a sleeve the
    posterior calls `chfnok_carry_asia_p_98d776f3e210d3e2`. A prefix matching TWO posterior
    sleeves (`gold_asia` -> `gold_asia_v2`, `gold_asia_v3`) is ambiguous and resolves to nothing:
    guessing which sleeve lost the money is worse than recording that the desk cannot say.
    """
    post = {str(r.get("name")): r for r in (_read_json(POSTERIOR) or {}).get("sleeves") or []
            if isinstance(r, dict) and r.get("name")}
    if not post:
        return []
    agg: dict[str, dict[str, Any]] = {}
    for r in _read_rows(LEDGER):
        name, rv = str(r.get("sleeve") or "").strip(), _f(r.get("r_multiple"))
        if not name or name.startswith("[") or rv is None:   # "[sl 4443.90]" is a bracket, not a
            continue                                         # sleeve: the broker's own comment
        cell = agg.setdefault(name, {"n": 0, "sum": 0.0, "symbols": {}})
        cell["n"] += 1
        cell["sum"] += rv
        sym = str(r.get("symbol") or "")
        cell["symbols"][sym] = cell["symbols"].get(sym, 0) + 1
    out: list[dict | None] = []
    for name, cell in agg.items():
        hits = [k for k in post if k == name] or [k for k in post if k.startswith(name)]
        mu = _f(post[hits[0]].get("mu_mean")) if len(hits) == 1 else None
        got = cell["sum"] / cell["n"] if cell["n"] else None
        if mu is None or got is None or mu - got <= 0:
            continue
        sym = max(cell["symbols"], key=lambda s: cell["symbols"][s]) if cell["symbols"] else ""
        out.append(item("strategy_loss", sym, f"sleeve_shortfall:{name}", mu - got, "R", 1.0,
                        "live_ledger",
                        f"{name} realised {got:+.3f} R over {cell['n']} trade(s) against a "
                        f"posterior of {mu:+.3f} R; the gap is what the desk's model of this "
                        f"sleeve did not predict"))
    return [r for r in out if r]


def collect() -> tuple[list[dict], dict[str, dict]]:
    """Every producer, normalised. An absent artifact is `absent` with n=0 -- never an error."""
    plan = (("standing_questions", STANDING, _standing), ("factor_residual", FACTOR, _factor),
            ("unknown_unknowns", UNKNOWN, _unknown),
            ("counterfactual_world", COUNTERFACTUAL, _counterfactual),
            ("opportunity_gap", GAP, _gap), ("missed_growth", MISSED, _missed),
            ("fill_attribution", FILLS, _fills), ("execution_quality", EXECQ, _execq),
            ("live_ledger", LEDGER, _losses), ("posterior_alpha", POSTERIOR, None))
    items: list[dict] = []
    sources: dict[str, dict] = {}
    for name, path, fn in plan:
        rows = (fn() if (fn and path.exists()) else [])[:MAX_PER_SOURCE]
        sources[name] = {"status": "present" if path.exists() else "absent",
                         "n": len(rows), "path": str(path)}
        items.extend(rows)
    # The posterior is not a producer of its own: it is the model `live_ledger` is differenced
    # against, so its count is that join's, reported here so an absent posterior is visible.
    sources["posterior_alpha"]["n"] = sources["live_ledger"]["n"]
    return items, sources


# ----------------------------------------------------------------------------------- queue
def _age_days(stamp: Any, now: datetime) -> float:
    try:
        seen = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return 0.0
    seen = seen.replace(tzinfo=UTC) if seen.tzinfo is None else seen
    return max((now - seen).total_seconds() / 86400.0, 0.0)


def _status(row: dict, now: datetime) -> str:
    if float(row.get("unexplained_fraction") or 0.0) < EXPLAINED_BELOW:
        return "EXPLAINED"
    if _age_days(row.get("last_seen"), now) >= STALE_DAYS:
        return "STALE"
    return "DONATED" if row.get("donated_at") else "OPEN"


def merge(prior: list[dict], fresh: list[dict], now: datetime | None = None) -> list[dict]:
    """The queue after this pass. Merge by `residual_id`; recurrence counts PASSES, not rows.

    A producer emitting the same residual twice in one pass is ONE sighting -- recurrence is the
    number of passes that saw it, which is what makes it evidence of a persistent ignorance
    rather than of a chatty producer. MEASURED on the live artifacts: 304 sightings collapse to
    207 items, almost all of them `factor_residual` grid variants of ONE (target, driver_set)
    cell. The residual is the cell, not the grid point, and the first representation wins --
    each producer hands its rows over already ranked, so that is its own strongest one.
    """
    now = now or _now()
    stamp = now.isoformat(timespec="seconds")
    by_id = {str(r["residual_id"]): dict(r) for r in prior if r.get("residual_id")}
    seen: dict[str, dict] = {}
    for it in fresh:
        seen.setdefault(str(it["residual_id"]), it)
    for rid, it in seen.items():
        old = by_id.get(rid)
        by_id[rid] = {**it, "recurrence": 1, "first_seen": stamp, "last_seen": stamp,
                      "status": "OPEN", "donated_at": None} if old is None else {
            **old, **it, "recurrence": int(_f(old.get("recurrence")) or 0) + 1,
            "first_seen": old.get("first_seen") or stamp, "last_seen": stamp,
            "donated_at": old.get("donated_at")}
    for row in by_id.values():
        row["priority"] = round(float(row.get("magnitude") or 0.0)
                                * float(_f(row.get("recurrence")) or 1.0)
                                * float(row.get("unexplained_fraction") or 0.0), 6)
        row["status"] = _status(row, now)
    return sorted(by_id.values(),
                  key=lambda r: (-float(r.get("priority") or 0.0), str(r.get("residual_id"))))


def _donate(candidates: list[dict], tests_run: int) -> Any:
    """The seam. One import, one call, so a test can watch what leaves without a live intake."""
    from research.proposer_common import donate
    return donate(SOURCE, candidates, tests_run)


#: What a donated row carries back about the residual that proposed it, so the gauntlet's verdict
#: can be read against the ignorance it came from rather than against a title.
_EVIDENCE = ("level", "key", "magnitude", "magnitude_unit", "recurrence",
             "unexplained_fraction", "unexplained_measured", "priority")


def donation_candidates(rows: list[dict], limit: int) -> tuple[list[dict], list[dict]]:
    """(candidates, refusals) for the top OPEN items. Every refusal is counted, never silent."""
    known = registered_families()
    out: list[dict] = []
    refused: list[dict] = []
    for row in rows:
        if len(out) >= max(int(limit), 0):
            break
        if row.get("status") != "OPEN":
            continue
        fam, sym = str(row.get("family") or ""), str(row.get("symbol") or "")
        if not fam:
            refused.append({"residual_id": row["residual_id"], "level": row["level"],
                            "why": "no registered family expresses this level; it stays a "
                                   "research task rather than take an invented one"})
        elif fam not in known:
            refused.append({"residual_id": row["residual_id"], "family": fam,
                            "why": "not in the family registry, or banned"})
        elif not may_hypothesise(sym):
            refused.append({"residual_id": row["residual_id"], "symbol": sym,
                            "asset_class": row.get("asset_class"),
                            "why": "the two-lane mandate: this instrument is traded on news and "
                                   "earnings reaction, never hunted for statistical hypotheses"})
        else:
            out.append({"source": SOURCE, "kind": "hypothesis", "symbol": sym, "symbols": [sym],
                        "family": fam, "params": dict(row.get("params") or {}), "url": "",
                        "title": f"residual {row['level']} {sym} {row['key']}"[:120],
                        "mechanism": str(row.get("why") or "")[:400],
                        "residual_id": row["residual_id"],
                        "evidence": {k: row.get(k) for k in _EVIDENCE}
                        | {"producer": row.get("source"), "screen": RULE}})
    return out, refused


def build(max_donations: int = MAX_DONATIONS, *, apply: bool = True) -> dict:
    now = _now()
    fresh, sources = collect()
    rows = merge(_read_rows(QUEUE), fresh, now)
    cands, refusals = donation_candidates(rows, max_donations)
    path = _donate(cands, len(fresh)) if (apply and cands) else None
    if path is not None:
        ids = {c["residual_id"] for c in cands}
        for row in rows:
            if row["residual_id"] in ids:
                row["donated_at"] = now.isoformat(timespec="seconds")
                row["status"] = _status(row, now)
    n = {s: sum(1 for r in rows if r.get("status") == s)
         for s in ("OPEN", "DONATED", "EXPLAINED", "STALE")}
    by_level = {lv: {"n": sum(1 for r in rows if r["level"] == lv),
                     "open": sum(1 for r in rows if r["level"] == lv and r["status"] == "OPEN"),
                     "priority": round(sum(float(r.get("priority") or 0.0)
                                           for r in rows if r["level"] == lv), 4)}
                for lv in LEVELS}
    return {"rows": rows, "report": {
        "at": now.isoformat(timespec="seconds"), "sources": sources, "n_items": len(rows),
        "n_open": n["OPEN"], "n_donated": n["DONATED"], "n_explained": n["EXPLAINED"],
        "n_stale": n["STALE"], "n_sightings_this_pass": len(fresh),
        "n_candidates": len(cands), "donated_this_pass": len(cands) if path else 0,
        "donation_file": str(path) if path else None,
        "n_refused": len(refusals), "refused": refusals[:30],
        "top": [{k: v for k, v in r.items() if k != "params"} for r in rows[:30]],
        "by_level": by_level, "units": UNITS, "rule": RULE,
        "stale_days": STALE_DAYS, "explained_below": EXPLAINED_BELOW}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the one queue of what the desk cannot explain")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no queue, no report, no donation")
    ap.add_argument("--max-donations", type=int, default=MAX_DONATIONS)
    a = ap.parse_args(argv)
    built = build(a.max_donations, apply=not a.dry_run)
    rep, rows = built["report"], built["rows"]
    live = sum(1 for s in rep["sources"].values() if s["status"] == "present")
    top = rep["top"][0] if rep["top"] else {}
    print(f"residual-queue: {rep['n_items']} item(s) from {live}/{len(rep['sources'])} "
          f"producer(s); {rep['n_sightings_this_pass']} sighting(s) this pass")
    print(f"  OPEN {rep['n_open']}  DONATED {rep['n_donated']}  "
          f"EXPLAINED {rep['n_explained']}  STALE {rep['n_stale']}")
    print("  by level  " + "  ".join(f"{k}:{v['open']}/{v['n']}"
                                     for k, v in rep["by_level"].items()))
    print(f"  top       {top.get('level', '-')} {top.get('symbol') or '(desk)'} "
          f"{str(top.get('key', '-'))[:44]} priority {top.get('priority', 0)}")
    verb = "would donate" if a.dry_run else "donated"
    print(f"  {verb:<9} {rep['n_candidates'] if a.dry_run else rep['donated_this_pass']} of "
          f"{a.max_donations} allowed; {rep['n_refused']} refused (no family, unregistered, or "
          f"wrong lane)")
    print(f"  rule      {RULE}")
    if a.dry_run:
        print("  --dry-run: nothing written, nothing donated")
        print(f"  would have written {QUEUE.name} and {REPORT.name}")
        return 0
    _atomic(QUEUE, "".join(json.dumps(r, default=str) + "\n" for r in rows))
    _atomic(REPORT, json.dumps(rep, indent=1, default=str))
    print(f"  -> {QUEUE}")
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
