"""MT5 gateway for the research desk: multi-sleeve breakout engine, kill switches.

Modes:
  SHADOW (default): computes signals, NEVER sends orders.
  ARMED  (manual):  sends real bracket orders to the logged-in MT5 account.

Sleeves:
  - Gold book (armed, hunt5-validated, lot = auto_lot(equity), q=5.5%).
  - Promoted sleeves (data/sleeves.json, written ONLY by research/promoter.py):
    auto-promoted from shadow-forward verdicts at fixed 0.01 lot, auto-retired
    by the same promoter when forward evidence decays. The machine manages
    promoted sleeves; only the human arms the account (armed=true).

Housekeeping: cancel unfilled brackets 20:30 UTC, force-close positions 19:30
UTC (Friday too), never trade a closed market (stale-tick guard).

Deal ledger: every closed trade tagged with its sleeve (order comment) is
appended to data/live_ledger.jsonl for retire/champion logic.

THIS FILE IS THE VENUE ADAPTER (split 2026-09-05). It imports MetaTrader5, which exists only on
the Windows box, so nothing in it can run or be measured anywhere else -- and for as long as the
sizing, heat and admission decisions lived here, the capital-moving code had 0.6% branch coverage
on the runner: the import prelude. Every decision now lives in `mt5desk/decision_core.py`, pure
over its arguments and branch-covered on any host; what stays here reads the terminal, keeps the
pass state and the ledgers, and sends what the core decided.
"""

from __future__ import annotations

import contextlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import MetaTrader5 as mt5
import pandas as pd
from mt5desk import decision_core as _core
from mt5desk import position_manager as _pm
from mt5desk import provenance as _prov
from mt5desk.config import desk_root, gateway_paused, terminal_path
from mt5desk.decision_core import (
    ATR_N,
    BRACKET_TTL_HOURS,
    CANCEL_HOUR,
    CLOSE_HOUR,
    GOLD_SYMBOL,
    MAX_TOTAL_REJECTIONS,
    MIN_RATCHET_IMPROVEMENT_R,
    PROMOTED_MIN_EQUITY,
    addon_desc,
    addon_entries,
    allocator_rank,
    atr_last,
    basket_lots,
    basket_record,
    book_from_allocation,
    bracket_deadline,
    bracket_from_bars,
    closed_trade_r,
    diagnose,
    entry_is_legal,
    exec_context,
    family_bar_due,
    family_entry,
    family_order_desc,
    family_signal_hour,
    family_signal_step,
    family_ttl_until,
    h1_frame,
    hibernated,
    placement_verdict,
    ramped_fraction,
    release_gate,
    roster,
    scalp_order_desc,
    scalp_recipe,
    sleeve_from_comment,
    state_allows,
    stop_distance,
    ttl_expired,
)
from mt5desk.independence import measure_from_ledger
from mt5desk.sizing import decay_factor

BASE = desk_root()
STATE = BASE / "data" / "gateway_state.json"
SLEEVES_FILE = BASE / "data" / "sleeves.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
LOG = BASE / "logs" / "gateway.log"
#: The pause flag `gateway_paused()` reads. Named here so the desk can set the
#: SAME file it already honours -- a second, private pause mechanism would be a
#: kill switch the operator does not know about.
PAUSED = BASE / "data" / "GATEWAY_PAUSED"

TERMINAL = terminal_path()
MAGIC = 341953

#: How far back record_trades looks for closed deals it has not yet written. Deals are deduped
#: by the venue's own ticket, so a wider window costs a list scan and cannot double-count. It
#: exists because the previous day-wide window silently lost every fill the gateway did not see
#: on the same calendar day: a skipped pass, an OOM kill or a restart after midnight left those
#: closes unrecorded permanently, since nothing ever looked backwards.
LEDGER_LOOKBACK_DAYS = 30

LOT = 0.02              # gold book lot; see Q_OPT below for the sizing policy
# RISK FRACTION OF EQUITY PER TRADE. Was 0.055, and that was not an arbitrary number: measured
# full Kelly on the 3-leg gold book (E[ln(1+qR)] maximised over the daily portfolio series,
# 5,728 trades, 2018-2026) is q* = 6.00%, so 5.5% was ~92% of Kelly, chosen deliberately.
#
# IT IS STILL WRONG, AND THE REASON IS NOT THE DRAWDOWN -- IT IS ESTIMATION FRAGILITY.
# Kelly is computed FROM the measured edge. That edge is in-sample, on one path, with params
# selected on this same gold data in hunt5. If the true expectancy is even half of the measured
# +0.159R/trade, then sizing at Kelly-on-measured is 2x over-levered, and past 2x Kelly the
# geometric growth rate turns NEGATIVE while every backtest number still looks excellent. Full
# Kelly is the point of maximum growth AND the point of maximum sensitivity to being wrong about
# the input; the whole margin of safety lives below it.
#
# The visible symptom is the drawdown ladder, in-sample, on the 3-leg book (worst -33.7R):
#     0.75% -> +118%/yr, -23.0% DD      <- here
#     1.04% -> +190%/yr, -30.7% DD      (what the 0.01 min lot forces at EUR1,684 -- see auto_lot)
#     3.00% -> +1,479%/yr, -68.4% DD    (half Kelly)
#     5.50% -> +7,660%/yr, -90.7% DD    (the old setting)
#     6.00% -> +9,816%/yr, -93.0% DD    (full Kelly)
# Those growth figures are in-sample and assume the edge is exactly as measured; they are the
# reason the ladder is shown, not a forecast. A -90% drawdown is also not survivable in practice
# regardless of what the geometric mean says about the path that produced it.
#
# THIS NUMBER MAY RISE, BUT ONLY ON FORWARD EVIDENCE. Fixed-fractional sizing already compounds
# -- auto_lot scales the lot with equity every run, so the book grows geometrically at a CONSTANT
# q without anyone touching this constant. Raising q is a separate claim: that the edge is better
# known than it is today. That claim is settled by live trades, not by backtest cells.

#: RE-EXPORTS, NOT RESTATEMENTS. Nothing below is defined here: the risk budget lives in
#: gateway_config_fallback and the arithmetic that uses it lives in `decision_core` since the
#: 2026-09-05 split. Both are imported into this namespace because the desk's research code and
#: tests have always read these names FROM THE GATEWAY -- `from mt5desk.gateway import Q_OPT` in
#: research/allocation.py is a fenced marker, and `GOLD_WINDOWS`, `bracket_spec` and `heat_budget`
#: are read the same way -- so the split may move a definition but may not move a name off this
#: module. The redundant `X as X` alias is the explicit re-export form, not a typo, and it is why
#: the block carries `noqa: I001`: isort wants every explicit re-export in a statement of its own,
#: which would turn one readable list of fourteen re-exported names into fourteen import lines.
from mt5desk.decision_core import (  # noqa: E402, I001
    CONTRACT_OZ as CONTRACT_OZ,
    DIST_USD as DIST_USD,
    FX_EUR as FX_EUR,
    GOLD_WINDOWS as GOLD_WINDOWS,
    HEAT_SLIDE as HEAT_SLIDE,
    MAX_HEAT_CEILING as MAX_HEAT_CEILING,
    MIN_LOT_RISK_EUR as MIN_LOT_RISK_EUR,
    RETCODE_MEANING as RETCODE_MEANING,
    RR as RR,
    allocator_order as allocator_order,
    bracket_spec as bracket_spec,
    day_range as day_range,
    heat_budget as heat_budget,
    min_lot_risk_eur as min_lot_risk_eur,
)
from mt5desk.gateway_config_fallback import (  # noqa: E402
    HEAT_HARD_CEILING as HEAT_HARD_CEILING,
    HEAT_TARGET as HEAT_TARGET,
    Q_OPT as Q_OPT,
)

# ---------------------------------------------------------------------------------------------
# THE DECISIONS LIVE IN `mt5desk.decision_core` (split 2026-09-05, principal's audit: "the most
# important capital-moving code must have the strongest proof"). This file imports MetaTrader5
# and therefore cannot be imported -- or measured -- anywhere but the Windows box; the sizing
# laws, the heat cap, the allocator readers, roster admission, the state gate, the bracket
# arithmetic, the retcode diagnosis, the session deadline, the execution context, the release
# gate and both lanes' decision steps now live in a module that imports on any host and is
# branch-covered there. What follows binds them to this desk's paths and the terminal's readings.
# ---------------------------------------------------------------------------------------------


def promoted_lot(equity: float, live_n: int, dist_usd: float | None = None,
                 symbol: str = GOLD_SYMBOL, info: object | None = None,
                 risk_frac: float | None = None,
                 decay_faded: object = None, from_book: bool = False) -> float:
    """Dynamic lot for a promoted sleeve -- `decision_core.promoted_lot`, bound here by name.

    A `def` AND NOT A BARE RE-EXPORT, for one reason: scripts/check_risk_units.py (L1.67)
    audits THIS file's sizing FunctionDefs by name -- it walks `auto_lot`, `realised_q` and
    `promoted_lot` for gold's constants and counts their call sites' arity -- and that fence is
    not editable from the gateway lane. The law itself, and its proof, live in the core: the
    allocator's fraction reaches the venue un-re-shrunk (`from_book`), the 3% base ramps with
    live authority otherwise, the L1.59 fade is reduce-only, and no heat is no lot.
    """
    return _core.promoted_lot(equity, live_n, dist_usd, symbol, info, risk_frac, decay_faded,
                              from_book=from_book)


def auto_lot(equity: float, dist_usd: float | None = None,
             symbol: str = GOLD_SYMBOL, info: object | None = None,
             q: float | None = None) -> float:
    """Fixed-fractional sizing -- `decision_core.auto_lot`, bound here by name (see
    `promoted_lot` for why a `def` rather than a re-export)."""
    return _core.auto_lot(equity, dist_usd, symbol, info, q=q)


def realised_q(equity: float, dist_usd: float | None = None,
               symbol: str = GOLD_SYMBOL, info: object | None = None,
               lot: float | None = None) -> float:
    """The risk fraction the account WILL actually run -- `decision_core.realised_q`, bound
    here by name (see `promoted_lot` for why a `def` rather than a re-export)."""
    return _core.realised_q(equity, dist_usd, symbol, info, lot=lot)


def sleeve_live_n(name: str) -> int:
    """Closed-trade count for a sleeve from this desk's live ledger."""
    return _core.sleeve_live_n(name, LEDGER)


def load_sleeves() -> list[dict]:
    """Promoted sleeves from data/sleeves.json (writer: research/promoter.py)."""
    return _core.load_sleeves(SLEEVES_FILE)


def allocator_heat() -> tuple[float | None, str]:
    """Total heat the E[log W] allocator resolved under this desk root, or None with the
    reason -- `decision_core.allocator_heat` over the artifacts this desk actually reads."""
    return _core.allocator_heat(BASE)


def allocator_book() -> tuple[dict[str, float] | None, str]:
    """The optimiser's PER-SLEEVE target risk fractions, or None with the reason.

    THE GATEWAY READS, THE CORE DECIDES. Three inputs come off disk here -- the certified total
    from `allocator_heat`, the proof certificate (`libs.portfolio.allocator_proof`), and the
    allocation artifact itself -- and each read fails closed with its own reason, because a book
    the desk cannot fully read is not a book it may size from. What those inputs MEAN (the
    dynamic book when the proof is fresh, the best baseline `book_fallback` at the same heat when
    it is not, the drift and empty-book refusals) is `decision_core.book_from_allocation`, which
    takes the parsed pieces and nothing else.

    A*_t: THE ALLOCATOR THAT WON HERE, NOT THE ONE THAT WON THE AVERAGE (2026-09-05). The
    certificate now carries a per-state verdict, and `select` answers which book may size in the
    state the desk is actually in: the state's own winner, else the same winner matched on the
    regime suffix, else the global verdict -- which is exactly what this did before per-state
    scoring existed, so an artifact without `by_state` is unchanged. A challenger that beat the
    dynamic allocator in this state is sized as a FALLBACK book (`certified=False`): it is a
    real book with real evidence behind it, and it is not the thing the global proof certified.
    """
    total, why = allocator_heat()
    if total is None:
        return None, f"no allocator book: {why}"
    try:
        from libs.portfolio.allocator_proof import read_certificate, select
        cert, cwhy = read_certificate(BASE.parent.parent)
    except Exception as exc:
        return None, f"proof unreadable ({type(exc).__name__}: {exc})"
    try:
        art = json.loads((BASE / "reports" / "pf_allocation.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"pf_allocation unreadable ({type(exc).__name__})"
    # `heat.state` is the id pf_allocator solved under and the certificate's `by_state` is keyed
    # the same way; a state with no bucket falls back to the global verdict INSIDE `select`.
    state = str((art.get("heat") or {}).get("state") or "")
    src, swhy = select(cert, state) if cert is not None else ("", cwhy)
    if src and src != "dynamic":
        # The certificate's books are at the contest's equalised heat, which is `heat.total`
        # (`contest` runs on `funded` AFTER `bind_verdict`), so the core's sum check still holds.
        by_name = {str(k): float(v) for k, v in
                   (((cert or {}).get("books") or {}).get(src) or {}).items() if float(v) > 0.0}
        if by_name:
            return book_from_allocation(total, art.get("book"),
                                        {"name": src, "book": by_name},
                                        certified=False, why=f"state-conditioned: {swhy}")
    return book_from_allocation(total, art.get("book"), art.get("book_fallback"),
                                certified=(cert is not None and src == "dynamic"),
                                why=(f"{cwhy}; {swhy}" if cert is not None else cwhy))


def cap_by_heat(sleeves: list[dict], equity: float,
                per_sleeve_q: float | None = None,
                k_eff: float | None = None) -> tuple[list[dict], str | None]:
    """Trim `sleeves` to the heat budget: `decision_core.cap_by_heat`, fed the allocator verdict.

    THE ALLOCATOR'S BOOK IS THE BUDGET WHEN THERE IS ONE. `heat_budget` is the derivation the
    desk falls back to; `allocator_heat` is a number something actually solved for. Both the
    solved total and the marginal ranking are read HERE, from this desk's artifacts, and handed
    to the core, which fails closed to the derivation on any doubt -- so this cannot raise heat
    by accident, and the cap's arithmetic is proven without a terminal.
    """
    solved, why = allocator_heat()
    return _core.cap_by_heat(sleeves, equity, per_sleeve_q, k_eff,
                             allocation=(solved, why), rank=allocator_rank(BASE))


def regime_hibernate(sleeves: list[dict]) -> set[str]:
    """Gateway names of sleeves flagged 'hibernate' in data/regime_state.json (writer:
    research/regime_monitor.py). Auto-kill: no new brackets until a human re-admits the sleeve
    (flag cleared or removed). An absent or unreadable file hibernates nothing; the key mapping
    is `decision_core.hibernated`."""
    p = BASE / "data" / "regime_state.json"
    if not p.exists():
        return set()
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return hibernated(sleeves, state)


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"{now()} {msg}"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def load_state() -> dict:
    defaults = {"armed": False, "brackets": {}, "position": None,
                "last_bracket_date": None, "last_reconcile": None}
    if STATE.exists():
        st = json.loads(STATE.read_text(encoding="utf-8"))
        for k, v in defaults.items():
            st.setdefault(k, v)
        return st
    return defaults


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")


def connect() -> bool:
    if mt5.terminal_info() is not None:
        return True
    if not mt5.initialize(path=TERMINAL):
        log(f"mt5 initialize failed: {mt5.last_error()}")
        return False
    return True


def note_placement(st: dict, sleeve: str, orders: list) -> bool:
    """Record whether a placement pass succeeded, and PAUSE THE DESK if none do.

    THE DEFECT THIS EXISTS TO END. `place_bracket` logged each rejection and
    returned; nothing counted them, nothing escalated, nothing stopped. The
    gateway ran for four days with 100% of its orders refused -- every sleeve,
    both sides, 10015 and 10017 -- writing retcodes into a state file and trying
    again tomorrow. Total failure and a quiet market produced the same silence,
    which is the absence-read-as-permission pattern in its purest form: nothing
    checked for SUCCESS, so nothing could tell them apart.

    Returns True while the desk is still healthy enough to keep going.
    """
    # UNAVAILABLE IS NOT REJECTED (see `decision_core.placement_verdict`): a bracket the desk
    # declined to send because price sat inside the broker's freeze band is the strategy having
    # nothing to do today, not the venue refusing us.
    attempted, ok, diags = placement_verdict(orders)
    hist = st.setdefault("placement_health", {"consecutive_total_rejections": 0,
                                              "last_ok": None, "last_error": None})
    if not attempted:
        return True
    if ok:
        hist["consecutive_total_rejections"] = 0
        hist["last_ok"] = now()
        return True

    hist["consecutive_total_rejections"] += 1
    hist["last_error"] = {"time": now(), "sleeve": sleeve, "diagnoses": diags}
    n = hist["consecutive_total_rejections"]
    log(f"PLACEMENT FAILED ENTIRELY [{sleeve}] -- {n} consecutive pass(es) with no "
        f"accepted order")
    for d in diags:
        log(f"    {d}")
    if n < MAX_TOTAL_REJECTIONS:
        return True

    # PAUSE, not just shout. A desk nobody is watching that logs an error and
    # keeps going is a desk that discovers the problem when someone happens to
    # read a file. The pause is the same file the operator uses by hand, so
    # clearing it is one command and the reason is written where they will look.
    PAUSED.parent.mkdir(parents=True, exist_ok=True)
    PAUSED.write_text(
        f"AUTO-PAUSED {now()}: {n} consecutive placement passes with ZERO accepted "
        f"orders.\n\n" + "\n".join(f"  {d}" for d in diags) +
        "\n\nNothing has traded. Fix the cause, then delete this file to re-arm.\n",
        encoding="utf-8")
    log("GATEWAY AUTO-PAUSED: no order has been accepted in "
        f"{n} consecutive passes. Nothing is trading; the reason is in "
        f"{PAUSED}. This is deliberate -- a desk whose orders are all refused is "
        "not a desk with a quiet market.")
    return False


def margin_ok(symbol: str, lot: float, price: float) -> bool:
    """Skip a sleeve if margin would be tight (machine kill switch)."""
    acc = mt5.account_info()
    if acc is None or acc.margin_free <= 0:
        return False
    need = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, lot, price)
    if need is None:
        return True  # cannot compute; let broker decide
    return need <= acc.margin_free * 0.9


#: Placement intents, one line per pending order sent. Separate from the deal ledger because the
#: two are written at different moments by different events -- an intent exists the instant an
#: order is sent, a deal only when it closes, and most intents never become deals at all (the
#: 20:30 cancel). Keeping them apart means an unfilled bracket is recorded as what it is rather
#: than inferred from an absence.
INTENTS = BASE / "data" / "order_intents.jsonl"

_SV_CACHE: tuple[float, str] = (0.0, "")


def _state_vector_id() -> str:
    """The id of the world description current at this placement, or "" if none is fresh.

    WHY AN ID ON AN ORDER. Slippage is not a constant; it is a function of the conditions the
    order was sent into -- session, event phase, liquidity state, volatility regime. Recording
    the price paid without recording the world it was paid in gives an average that describes no
    situation the desk will ever be in again. Stamping the state vector's id makes execution cost
    a learnable function of a state that can be reconstructed exactly, months later, from the
    artifact rather than re-derived from a timestamp and a guess.

    Cached on mtime and NEVER raises: this is on the money path, and an unreadable telemetry file
    must cost an empty string rather than an order.
    """
    global _SV_CACHE
    try:
        p = BASE / "data" / "state_vector.json"
        mtime = p.stat().st_mtime
        if mtime == _SV_CACHE[0]:
            return _SV_CACHE[1]
        sid = str(json.loads(p.read_text("utf-8")).get("id") or "")
        _SV_CACHE = (mtime, sid)
        return sid
    except Exception:
        return ""


DECISIONS = BASE / "data" / "decision_ledger.jsonl"


def _release_id() -> str:
    """The canonical live release this process runs under (libs.ops.release). One SHA, named on
    every intent and every decision, so a fill weeks later is attributable to one code state."""
    try:
        from libs.ops.release import release_id
        return release_id()
    except Exception:                                           # noqa: BLE001
        return "unreleased"


def _record_decision(**row) -> None:
    """Append one CONSIDERED signal -- taken or not -- with why, the size, the execution, the
    exit rule and the book it was decided inside. NEVER raises.

    THE DATASET NOBODY ELSE HAS. The intent ledger records what was sent to the broker. This
    records everything the desk LOOKED AT: the bracket it would have placed, whether it placed
    it, and if not, which filter said no. Joined later to what the market did, that is the P&L of
    every veto the desk runs, which is the number that decides whether a filter earns its place.

    THE FULL RECORD (2026-09-05, the counterfactual-world order). This wrote a hand-rolled dict
    -- sleeve, side, price, stop, target, taken, reason -- and nothing could price the
    alternatives from it. `libs.research.decision_ledger.write_decision` is now the one writer:
    it normalises this keyword dict through `Decision` (every new field defaulted, so a row
    written today is a superset of one written last month), keeps `time`, `state_vector_id` and
    `taken` on the line verbatim so `counterfactual_markout`'s join is untouched, and never
    raises -- on the money path a ledger fault must cost a row, and a row is cheaper than an
    order.
    """
    from libs.research.decision_ledger import write_decision

    row["time"] = now()
    row.setdefault("state_vector_id", _state_vector_id())
    try:
        row.setdefault("release_id", _release_id())
    except Exception:                                       # noqa: BLE001
        row.setdefault("release_id", "unreleased")
    row.setdefault("size_mult", 1.0)
    row.setdefault("execution",
                   "pending_stop" if str(row.get("side") or "").endswith("_stop") else "market")
    row.setdefault("exit_rule", "fixed_tp")
    row.setdefault("veto_reason", "" if row.get("taken") else str(row.get("reason") or ""))
    row.setdefault("portfolio_context", _decision_portfolio_context(row.get("sleeve")))
    write_decision(DECISIONS, row, log=log)


#: The book at the moment of a decision, memoised for one pass. `allocator_book()` is three disk
#: reads and a decision pass records many rows; a stale-by-one-pass book is the right trade,
#: and a failure costs an empty context and never an order.
_PF_CTX: dict[str, object] = {"at": "", "book": None, "why": ""}


def _decision_portfolio_context(sleeve) -> dict:
    """The portfolio the decision was made inside: the sleeve's target fraction and the book's
    size, or the reason there is no book. Never raises."""
    try:
        stamp = now()[:16]                                  # one refresh per minute at most
        if _PF_CTX["at"] != stamp:
            book, why = allocator_book()
            _PF_CTX.update({"at": stamp, "book": book, "why": why})
        book, why = _PF_CTX["book"], _PF_CTX["why"]
        if not isinstance(book, dict):
            return {"book": None, "why": why}
        return {"h": book.get(str(sleeve or "")), "n_book": len(book),
                "total_heat": round(sum(float(v) for v in book.values()), 6), "why": why}
    except Exception as exc:                                # noqa: BLE001
        return {"book": None, "why": f"{type(exc).__name__}: {exc}"}


def _record_vetoed_bracket(s: dict, df: pd.DataFrame, sym, reason: str,
                           detail: str = "") -> bool:
    """Record the bracket a VETOED sleeve would have placed today, both sides. NEVER raises.

    A veto that fires before the bracket is computed (regime hibernate, the state gate) leaves
    no trace of what it refused, and a filter with no trace cannot be valued. This computes the
    same range and the same spec the bracket loop would have -- the identical `day_range` and
    `bracket_spec` calls, on the identical bars -- and writes the two pending-stop levels with
    the veto reason, so `counterfactual_markout` can replay them exactly as it replays a margin
    veto. Nothing is sent to the broker; the sleeve is not sized; state is not touched.

    Returns True when a record was written (range ready), False when the sleeve's range was not
    yet formed at this hour -- in which case the next pass tries again, exactly as the live loop
    would have.
    """
    try:
        built = bracket_from_bars(df, s.get("rng"), s["sig_hour"], sym.trade_tick_size,
                                  int(getattr(sym, "trade_stops_level", 0) or 20))
        if built is None:
            return False
        _hi, _lo, spec = built
        for side in ("buy_stop", "sell_stop"):
            leg = spec.get(side) or {}
            _record_decision(sleeve=s["name"], symbol=s["symbol"], side=side, lot=None,
                             price=leg.get("price"), sl=leg.get("sl"), tp=leg.get("tp"),
                             taken=False, reason=reason, detail=detail)
        return True
    except Exception as exc:
        log(f"vetoed-bracket record failed (non-fatal) [{s.get('name')}]: "
            f"{type(exc).__name__}: {exc}")
        return False


def _record_intent(**row) -> None:
    """Append one placement intent. NEVER raises -- telemetry must not break the money path."""
    try:
        row["time"] = now()
        row.setdefault("state_vector_id", _state_vector_id())
        try:
            row.setdefault("release_id", _release_id())
        except Exception:                                   # noqa: BLE001
            row.setdefault("release_id", "unreleased")
        INTENTS.parent.mkdir(parents=True, exist_ok=True)
        with INTENTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except Exception as exc:
        log(f"intent record failed (non-fatal): {type(exc).__name__}: {exc}")


def place_bracket(st: dict, spec: dict, sleeve: str, symbol: str, lot: float) -> dict:
    if not st["armed"]:
        log(f"SHADOW [{sleeve}] would place bracket: {json.dumps(spec, default=str)}")
        for side in ("buy_stop", "sell_stop"):
            s = spec.get(side) or {}
            _record_decision(sleeve=sleeve, symbol=symbol, side=side, lot=lot,
                             price=s.get("price"), sl=s.get("sl"), tp=s.get("tp"),
                             taken=False, reason="shadow_not_armed")
        return {"shadow": True, "orders": []}
    sent = []
    # Current market, read ONCE for the legality check below. A pending order
    # whose entry sits inside the broker's freeze band is refused with 10015,
    # and finding that out from the broker costs a rejection that then looks
    # like a failing desk rather than an unavailable setup.
    _t = mt5.symbol_info_tick(symbol)
    _si = mt5.symbol_info(symbol)
    _point = float(getattr(_si, "point", 0.01) or 0.01)
    _lvl = int(getattr(_si, "trade_stops_level", 0) or 0)

    for side in ("buy_stop", "sell_stop"):
        s = spec[side]
        if _t is not None and _lvl > 0:
            legal, why_illegal = entry_is_legal(
                float(s["price"]), side, float(_t.bid), float(_t.ask), _point, _lvl)
            if not legal:
                log(f"NOT AVAILABLE [{sleeve}] {side}: {why_illegal}")
                # Recorded as UNAVAILABLE, which is a different fact from a
                # rejected order and must not count toward the rejection
                # escalation -- a desk pausing itself because the market sat on
                # the range edge would be a desk that stops working on exactly
                # the days its strategy has nothing to do.
                sent.append({"side": side, "retcode": None, "unavailable": True,
                             "comment": why_illegal})
                _record_decision(sleeve=sleeve, symbol=symbol, side=side, lot=lot,
                                 price=s.get("price"), sl=s.get("sl"), tp=s.get("tp"),
                                 taken=False, reason="entry_inside_freeze_band",
                                 detail=why_illegal)
                continue
        req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY_STOP if side == "buy_stop" else mt5.ORDER_TYPE_SELL_STOP,
            "price": s["price"],
            "sl": s["sl"],
            "tp": s["tp"],
            # BROKER-SIDE EXPIRY, so the TTL survives this process dying. A gateway-side sweep
            # only runs while the gateway runs, and an OOM kill or a box restart would leave a
            # stale bracket resting at the broker indefinitely -- exposure nothing is managing.
            # `_expiry_request` falls back to GTC when the symbol refuses timed orders, and the
            # sweep below is what covers that case.
            **_expiry_request(symbol, sleeve, spec.get("window")),
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "deviation": 20,
            "magic": MAGIC,
            "comment": f"DW{sleeve}",
        }
        res = mt5.order_send(req)
        code = res.retcode if res else None
        why = diagnose(code, getattr(res, "comment", "") or "")
        if why:
            log(f"ORDER FAILED [{sleeve}] {side}: {why}")
        # THE INTENT, RECORDED AT PLACEMENT. Without this line slippage is unknowable: once the
        # order fills, MT5 reports only the price it GOT, and the price the desk ASKED for is
        # gone. Every backtest number on this desk assumes fills at exactly `s["price"]`, and
        # nothing has ever checked that assumption -- the crypto desk made the same omission and
        # discovered its real execution cost was 50x its modelled one, on trades that needed
        # twelve days of funding to repay a single entry. Written at send time, joined by ticket
        # in `markout.py` when the deal closes.
        # THE CONDITIONS AT DECISION, not just the price asked. Slippage measured without the
        # market it was paid into averages over every situation at once and describes none of
        # them; with the quote and spread recorded here, execution cost becomes a function of
        # symbol, hour, spread and state rather than one scalar per symbol. `_t` was already read
        # above for the legality check, so this costs nothing and cannot fail separately.
        _record_intent(sleeve=sleeve, symbol=symbol, side=side, lot=lot,
                       intended=float(s["price"]), sl=float(s["sl"]), tp=float(s["tp"]),
                       ticket=(getattr(res, "order", None) if res else None), retcode=code,
                       decision_bid=(float(_t.bid) if _t is not None else None),
                       decision_ask=(float(_t.ask) if _t is not None else None),
                       spread_at_decision=(float(_t.ask) - float(_t.bid)
                                           if _t is not None else None),
                       point=_point, stops_level=_lvl, order_type="pending_stop")
        sent.append({"side": side, "retcode": code,
                     "comment": res.comment if res else None})
        _record_decision(sleeve=sleeve, symbol=symbol, side=side, lot=lot,
                         price=s.get("price"), sl=s.get("sl"), tp=s.get("tp"),
                         taken=(not why), reason=("placed" if not why else "broker_rejected"),
                         detail=(why or ""), ticket=(getattr(res, "order", None) if res else None))
        log(f"ORDER [{sleeve}] {side} -> retcode={code} "
            f"{res.comment if res else ''}")
    # THE SUCCESS CHECK. Without it a pass where every order was refused is
    # indistinguishable from a quiet day, which is how four days of total
    # rejection passed unnoticed.
    note_placement(st, sleeve, sent)
    return {"shadow": False, "orders": sent}


def _expiry_request(symbol: str, sleeve: str = "", window: str | None = None) -> dict:
    """`type_time`/`expiration` fields for a bracket, or GTC when the symbol refuses timed orders.

    MT5 exposes what a symbol accepts through `symbol_info().expiration_mode`; a symbol without
    the SPECIFIED bit rejects the whole order if one is sent, so this asks first rather than
    losing the bracket. Absence of the information falls back to GTC and the gateway-side sweep,
    never to an unbounded order the desk believes is bounded.
    """
    try:
        info = mt5.symbol_info(symbol)
        mode = int(getattr(info, "expiration_mode", 0) or 0)
        if info is not None and (mode & mt5.SYMBOL_EXPIRATION_SPECIFIED):
            until = bracket_deadline(sleeve, window)
            return {"type_time": mt5.ORDER_TIME_SPECIFIED,
                    "expiration": int(until.timestamp())}
    except Exception as exc:
        log(f"{symbol}: expiration mode unreadable ({type(exc).__name__}); bracket is GTC "
            f"and relies on the {BRACKET_TTL_HOURS:.0f}h sweep")
    return {"type_time": mt5.ORDER_TIME_GTC}


def expire_stale_brackets(st: dict) -> int:
    """Cancel this desk's pending orders whose SESSION has ended. Returns how many.

    THE SWEEP IS NOT REDUNDANT WITH THE BROKER EXPIRY. It covers the symbols whose expiration
    mode refuses a timed order, brackets placed before this TTL existed, and anything left
    resting by a gateway that died between placing and cancelling. It is keyed on MAGIC, so it
    can only ever touch orders this desk placed.
    """
    try:
        orders = mt5.orders_get() or ()
    except Exception as exc:
        log(f"TTL sweep skipped: orders_get failed ({type(exc).__name__})")
        return 0
    killed = 0
    now_utc = datetime.now(tz=UTC)
    for o in orders:
        if int(getattr(o, "magic", 0) or 0) != MAGIC:
            continue
        setup = getattr(o, "time_setup", None)
        if not setup:
            continue
        placed = datetime.fromtimestamp(int(setup), tz=UTC)
        # THE SAME PER-SESSION RULE THE ORDER WAS PLACED UNDER, recovered from its own label, so
        # the sweep and the broker expiry can never disagree. A flat cutoff here would defeat the
        # point: it would keep an afternoon bracket alive hours past the force-close the broker
        # had already been told to kill it at.
        sleeve = sleeve_from_comment(str(getattr(o, "comment", "") or ""))
        if bracket_deadline(sleeve) > now_utc and placed.date() == now_utc.date():
            continue
        res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})
        gone = not any(getattr(x, "ticket", None) == o.ticket
                       for x in (mt5.orders_get(symbol=o.symbol) or ()))
        if gone:
            killed += 1
            log(f"TTL: cancelled {o.symbol} order {o.ticket} placed {placed:%H:%M} "
                f"({(datetime.now(tz=UTC) - placed).total_seconds() / 3600:.1f}h old, "
                f"limit {BRACKET_TTL_HOURS:.0f}h)")
        else:
            log(f"TTL: {o.symbol} order {o.ticket} SURVIVED cancellation "
                f"(retcode {getattr(res, 'retcode', None)}); it is still resting")
    return killed


def cancel_pending(st: dict, symbol: str) -> None:
    """Remove unfilled pending orders, and PROVE each one is gone.

    THIS NEVER WORKED ONCE. It called `mt5.order_delete(ticket)`, and the MetaTrader5 Python
    package HAS NO SUCH FUNCTION -- verified against the live terminal 2026-09-01:
    `hasattr(mt5, "order_delete")` is False. Removal is documented as order_send() with
    TRADE_ACTION_REMOVE (=8). So every call raised AttributeError while the very next line
    logged "cancelled pending ticket <n>", and unfilled buy/sell stops were left standing on a
    live account with the desk reporting them cancelled.

    IT ALSO TOOK THE REST OF THE PASS WITH IT. Neither this function nor its caller caught the
    exception, and the housekeeping block runs at hour >= CANCEL_HOUR (20:30 UTC) BEFORE
    close_positions, record_trades and reconcile. From 20:30 onward, every one of those was
    skipped -- which is the shape of `last_reconcile` standing at 2026-08-17 and of a live
    ledger that never appeared.

    SO CANCELLATION IS NOW IDEMPOTENT AND VERIFIED, not hopeful: send the documented removal,
    read the retcode, then re-read orders_get and confirm the ticket is ABSENT. A ticket that
    survives is reported as still live rather than logged as cancelled, because a cancellation
    the desk believes in but the venue did not perform is worse than a loud failure. One
    ticket's failure never aborts the others, and never the pass.
    """
    if not st["armed"]:
        log("SHADOW would cancel unfilled brackets")
        return
    pending = list(mt5.orders_get(symbol=symbol) or [])
    if not pending:
        return
    for o in pending:
        ticket = getattr(o, "ticket", None)
        try:
            res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        # Broad on purpose: one bad ticket must not strand the others, nor abort the pass.
        except Exception as exc:
            log(f"CANCEL FAILED ticket {ticket} ({symbol}): "
                f"{type(exc).__name__}: {exc}; order may still be live")
            continue
        retcode = getattr(res, "retcode", None)
        # THE VENUE IS THE STATE, not the return value. A retcode can be optimistic, a result can
        # be None on a dropped connection, and either way the only fact that matters is whether
        # the ticket is still accepting a fill.
        still = any(getattr(x, "ticket", None) == ticket
                    for x in (mt5.orders_get(symbol=symbol) or []))
        if still:
            log(f"CANCEL NOT CONFIRMED ticket {ticket} ({symbol}): retcode={retcode}, "
                f"order STILL PRESENT after remove -- treat as live")
            continue
        log(f"cancelled pending ticket {ticket} ({symbol}) retcode={retcode}, "
            f"confirmed absent from orders_get")


def close_positions(st: dict, symbol: str) -> None:
    if not st["armed"]:
        log("SHADOW would force-close open positions")
        return
    for p in mt5.positions_get(symbol=symbol) or []:
        tick = mt5.symbol_info_tick(symbol)
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": p.ticket,
            "price": tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "deviation": 20,
            "magic": MAGIC,
        }
        res = mt5.order_send(req)
        log(f"CLOSE ticket {p.ticket} ({symbol}) -> retcode={res.retcode if res else None} "
            f"{res.comment if res else ''}")


def _original_stop_distance(st: dict, ticket: int, price_open: float, sl: float) -> float | None:
    """The stop distance this position was OPENED with, captured once and then remembered.

    R is defined against the INITIAL risk. Once management starts moving the stop, the live
    `sl` no longer encodes it, so the distance has to be captured while it still does -- the
    first time this ticket is seen -- and reused thereafter.

    THE RESTART HAZARD IS REAL AND IS LOGGED RATHER THAN HIDDEN. If `data/gateway_state.json`
    is lost while a managed position is open, first sight after the restart captures the ALREADY
    MOVED stop and every subsequent R for that ticket is computed against a smaller denominator,
    overstating the multiple. The capture is therefore logged loudly on the pass it happens, so
    a capture appearing for a position that is not brand new is visible as the anomaly it is.
    A position with no stop at all returns None and is left alone: there is no initial risk to
    ratchet against, and inventing one would be inventing the denominator of every number that
    follows.
    """
    if not sl:
        return None
    store = st.setdefault("orig_stop_dist", {})
    key = str(ticket)
    if key not in store:
        dist = abs(price_open - sl)
        if dist <= 0:
            return None
        store[key] = dist
        log(f"MANAGE capture: ticket {ticket} initial stop distance {dist:.5f} "
            f"(open {price_open:.5f} sl {sl:.5f}) -- expected only on a position's first pass")
    return float(store[key])


def manage_open_positions(st: dict, sleeves: list[dict]) -> None:
    """Ratchet the stop on every open position. SHADOW UNLESS `st["armed"]`.

    THE GAP THIS CLOSES. `engine.py` models a trailing, banking runner and every backtest
    expectancy on this desk is computed with it applied; this gateway placed a stop at entry and
    never touched it again. The two were different strategies and the difference was the whole
    right tail -- a live winner could round-trip to its opening stop, an outcome the backtest
    would never have shown because there the stop had moved.

    THE BROKER IS THE STATE. `p.sl` is re-read from `positions_get` on every pass and fed in as
    the current stop, so a rejected modify simply leaves the next pass re-proposing against the
    unchanged level. Nothing is cached that could disagree with the account, which is what makes
    this idempotent and acknowledgement-driven rather than merely hopeful.
    """
    symbols = list({s["symbol"] for s in sleeves} | {"XAUUSD"})
    for symbol in symbols:
        positions = mt5.positions_get(symbol=symbol) or []
        if not positions:
            continue
        info = mt5.symbol_info(symbol)
        if info is None:
            log(f"MANAGE {symbol}: no symbol_info; skipped")
            continue
        for p in positions:
            side = 1 if p.type == mt5.POSITION_TYPE_BUY else -1
            dist = _original_stop_distance(st, p.ticket, p.price_open, p.sl)
            if dist is None:
                log(f"MANAGE ticket {p.ticket} ({symbol}): no stop on the position; "
                    f"nothing to ratchet against and none invented")
                continue

            # Bars SINCE ENTRY only. A pre-entry extreme is a level the thesis never reached.
            since = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1,
                                         datetime.fromtimestamp(p.time, tz=UTC),
                                         datetime.now(tz=UTC))
            if since is None or len(since) < 2:
                log(f"MANAGE ticket {p.ticket} ({symbol}): fewer than 2 bars since entry; "
                    f"too early to locate an extreme")
                continue
            bars = pd.DataFrame(since)

            # ATR on a longer window than the holding period, because a young position has too
            # few bars of its own to characterise volatility with.
            h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 400)
            if h1 is None or len(h1) < ATR_N + 1:
                log(f"MANAGE ticket {p.ticket} ({symbol}): ATR unavailable; skipped")
                continue
            atr = atr_last(pd.DataFrame(h1))
            if not (atr > 0):
                log(f"MANAGE ticket {p.ticket} ({symbol}): ATR non-positive; skipped")
                continue

            extreme, stall = _pm.extreme_and_stall(
                highs=[float(x) for x in bars["high"]],
                lows=[float(x) for x in bars["low"]], side=side)
            decision = _pm.ratchet(
                entry=float(p.price_open), current_stop=float(p.sl), stop_distance=dist,
                extreme=extreme, atr=atr, side=side, bars_since_extreme=stall)

            tag = f"MANAGE ticket {p.ticket} ({symbol})"
            if not decision.moves:
                log(f"{tag}: {decision.reason}")
                continue
            if decision.improvement_r < MIN_RATCHET_IMPROVEMENT_R:
                log(f"{tag}: improvement {decision.improvement_r:+.3f}R below the "
                    f"{MIN_RATCHET_IMPROVEMENT_R:.2f}R floor; not worth a modify")
                continue

            # THE VENUE'S OWN MINIMUM DISTANCE. A stop inside stops_level is rejected, and a
            # rejection every pass is a management loop that looks busy and protects nothing.
            stops_level = int(getattr(info, "trade_stops_level", 0) or 0)
            tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
            tick_now = mt5.symbol_info_tick(symbol)
            if stops_level and tick_size and tick_now is not None:
                ref = tick_now.bid if side == 1 else tick_now.ask
                if abs(ref - decision.new_stop) < stops_level * tick_size:
                    log(f"{tag}: proposed stop {decision.new_stop:.5f} is inside the venue's "
                        f"{stops_level}-point stops level; held")
                    continue

            if not st["armed"]:
                log(f"SHADOW would modify {tag}: sl {p.sl:.5f} -> {decision.new_stop:.5f} "
                    f"| {decision.reason}")
                continue

            res = mt5.order_send({
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": p.ticket,
                "sl": decision.new_stop,
                "tp": p.tp,
                "magic": MAGIC,
            })
            rc = res.retcode if res else None
            log(f"{tag}: MODIFY sl {p.sl:.5f} -> {decision.new_stop:.5f} "
                f"(protected {decision.protected_r_before:+.3f}R -> "
                f"{decision.protected_r_after:+.3f}R) retcode={rc} "
                f"{diagnose(rc, res.comment if res else '')}")

            # CONFIRM FROM THE BROKER, not from the return code. A retcode is an answer about
            # the request; the position is the answer about the account.
            after = mt5.positions_get(ticket=p.ticket) or []
            if after:
                got = float(after[0].sl)
                if abs(got - decision.new_stop) > (tick_size or 1e-9):
                    log(f"{tag}: WARNING requested sl {decision.new_stop:.5f} but the broker "
                        f"reports {got:.5f} -- next pass re-proposes against what it reports")


def reconcile(st: dict) -> dict:
    pos = []
    pend = []
    for symbol in list({s["symbol"] for s in load_sleeves()}) + ["XAUUSD"]:
        pos += mt5.positions_get(symbol=symbol) or []
        pend += mt5.orders_get(symbol=symbol) or []
    st["position"] = [
        {"ticket": p.ticket, "type": p.type, "volume": p.volume,
         "price_open": p.price_open, "sl": p.sl, "tp": p.tp,
         "profit": p.profit, "symbol": p.symbol} for p in pos
    ] if pos else None
    st["pending"] = [{"ticket": o.ticket, "type": o.type, "price": o.price_open,
                      "symbol": o.symbol} for o in pend] if pend else None
    st["last_reconcile"] = now()
    return st


def _position_context(deal: object) -> tuple[float, float, float, str]:
    """(entry price, stop, take-profit, comment) for the position a closing deal belongs to.

    MT5 splits what this desk needs across two record types and joins them only on
    `position_id`: the DEAL holds the executed price and P&L, the ORDER holds the stop and
    target. A closing deal therefore knows what it made and not what it risked, and R is the
    ratio of the two -- so both must be fetched.

    RETURNS ZEROS RATHER THAN RAISING. A single unreadable position must not abort the loop that
    records every other fill: that is exactly how one AttributeError kept the entire live ledger
    empty while the account carried real P&L.
    """
    pid = getattr(deal, "position_id", None)
    if not pid:
        return 0.0, 0.0, 0.0, ""
    entry = sl = tp = 0.0
    comment = ""
    try:
        for o in (mt5.history_orders_get(position=pid) or ()):
            if not comment:
                comment = str(getattr(o, "comment", "") or "")
            if float(getattr(o, "sl", 0.0) or 0.0) > 0:
                sl = float(o.sl)
                tp = float(getattr(o, "tp", 0.0) or 0.0)
        for x in (mt5.history_deals_get(position=pid) or ()):
            if getattr(x, "entry", None) == mt5.DEAL_ENTRY_IN:
                entry = float(getattr(x, "price", 0.0) or 0.0)
                break
    except Exception as exc:
        log(f"position {pid}: context unreadable ({type(exc).__name__}); R left unmeasured")
        return 0.0, 0.0, 0.0, comment
    return entry, sl, tp, comment


def record_trades(st: dict, sleeves: list[dict]) -> None:
    """Append closed trades (deal OUT with DW comment) to the live ledger.

    r_multiple: quote-currency P&L per lot / entry-risk distance per lot
    (entry risk = bracket SL distance x contract size in quote units).
    """
    if not st["armed"]:
        return

    # ALREADY-RECORDED DEALS, so the window below can be widened without duplicating rows.
    # The ledger is append-only JSONL and `deal` is the venue's own ticket, unique per fill.
    seen_deals: set = set()
    if LEDGER.exists():
        try:
            for line in LEDGER.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                with contextlib.suppress(ValueError):
                    tid = json.loads(line).get("deal")
                    if tid is not None:
                        seen_deals.add(tid)
        except OSError:
            seen_deals = set()

    try:
        # A DAY-WIDE WINDOW LOSES EVERY FILL THE GATEWAY DID NOT SEE THE SAME DAY. Any pass that
        # is skipped, OOM-killed or started after midnight left that day's closes unrecorded
        # forever, because nothing ever looked backwards. Dedupe by deal ticket makes a wider
        # window free, so the lookback is bounded by history rather than by uptime.
        since = datetime.now(tz=UTC) - timedelta(days=LEDGER_LOOKBACK_DAYS)
        deals = mt5.history_deals_get(since, datetime.now(tz=UTC), magic=MAGIC) or []
    except Exception:
        return
    written = 0
    for d in deals:
        if d.entry != mt5.DEAL_ENTRY_OUT:
            continue
        if getattr(d, "ticket", None) in seen_deals:
            continue
        # A DEAL CARRIES NO STOP, NO TAKE-PROFIT AND NO ENTRY PRICE, and this function read all
        # three off it. MEASURED 2026-09-02 on the live box: every pass raised
        # `AttributeError("'TradeDeal' object has no attribute 'price_open'")` and the whole
        # trade loop aborted, so `live_ledger.jsonl` was never written -- the file whose absence
        # was diagnosed on 2026-09-01 as a comment-prefix problem and fixed there. That fix was
        # necessary and not sufficient: the function could not run at all.
        #
        # MT5's own shapes: TradeDeal has {price, position_id, order, entry, profit, commission,
        # swap, volume}; TradeOrder has {price_open, sl, tp}. So the risk this trade actually
        # took is reconstructed from the position's OPENING deal (entry price) and its ORDER
        # (stop), joined on position_id -- the only join MT5 offers between the two.
        entry_price, sl_price, tp_price, order_comment = _position_context(d)
        comment = (d.comment or order_comment or "")
        # MAGIC IS THE IDENTITY, NOT THE COMMENT. history_deals_get already filtered to
        # magic=MAGIC, so every deal here is this gateway's own; requiring the comment to ALSO
        # start with "DW" made a broker-side rewrite silently discard the entire ledger. Brokers
        # do rewrite comments -- it is the same lesson the EA learned when it stopped trusting
        # them for idempotency and moved to a persistent journal. Measured 2026-09-01:
        # live_ledger.jsonl did not exist on either box while the account carried real P&L and
        # open margin, so matched_fills read 0 and execution was UNMEASURED. A fill this desk
        # placed is now recorded whether or not its label survived the round trip; the sleeve
        # name is taken from the comment when it is there and marked unattributed when it is not,
        # which is a recoverable gap, unlike never recording the fill at all.
        sleeve = sleeve_from_comment(comment, "UNATTRIBUTED")
        sym_info = mt5.symbol_info(d.symbol)
        if sym_info is None:
            continue
        # risk per lot at entry: SL distance x contract (quote units)
        pl_quote = float(d.profit) + float(d.commission or 0.0) + float(d.swap or 0.0)
        # UNRECONSTRUCTIBLE IS RECORDED, NEVER GUESSED -- `decision_core.closed_trade_r` returns
        # zeros without both the entry and the stop, and the row below says so.
        risk_quote, r = closed_trade_r(entry_price, sl_price, d.type == mt5.POSITION_TYPE_BUY,
                                       sym_info.trade_contract_size, pl_quote)
        rec = {"time": now(), "sleeve": sleeve, "symbol": d.symbol,
               "side": d.type, "pl_quote": round(pl_quote, 2),
               "r_multiple": round(r, 4), "volume": d.volume,
               "commission": d.commission, "swap": d.swap, "deal": d.ticket,
               # THE FILL, so it can be compared with the intent. price_open was already read
               # here to size `risk_quote` and then thrown away, which is why no markout was
               # possible: the one number that reveals execution quality was computed and
               # discarded on every single trade. contract_size travels with it so slippage can
               # be converted to account currency without a second lookup at analysis time.
               "fill_price": float(d.price), "entry_price": float(entry_price),
               "sl": float(sl_price), "tp": float(tp_price),
               "r_unreconstructible": bool(entry_price <= 0 or sl_price <= 0),
               "order": getattr(d, "order", None),
               "contract_size": float(sym_info.trade_contract_size),
               "risk_quote": round(float(risk_quote), 6),
               # WHICH ACCOUNT TRADED. The broker is switched by editing one line of
               # data/terminal_path.txt, so the account under this gateway can change between two
               # runs. Without these fields a Fusion DEMO fill lands in the same ledger the
               # promoter reads to RETIRE a live sleeve, indistinguishable forever after -- and a
               # newly funded live account would be judged partly on demo history sitting above it
               # in the same file. Demo fills are not a conservative approximation of live ones:
               # a demo server fills stops at the trigger with no slippage, which is exactly the
               # assumption markout exists to test.
               **_prov.stamp(_prov.current_account(mt5.account_info()))}
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        written += 1
    if written:
        log(f"ledger: recorded {written} closed trade(s)")


def ledger_rows() -> list[dict]:
    """Closed trades recorded by this desk. Torn final lines are skipped, never fatal."""
    return _core.ledger_rows(LEDGER)


#: Written by research/promoter.py when a gold window trips a retire rule. Read on every pass so
#: a retirement takes effect within one gateway cycle rather than waiting for a restart.
GOLD_RETIRED_FILE = BASE / "data" / "GOLD_RETIRED.json"


def _load_retired_gold() -> dict:
    """Retired gold windows, or {} when the file is absent/unreadable -- fails OPEN, for the
    reason `decision_core.load_retired_gold` states: an unreadable file must not silently stop a
    live book that is otherwise trading correctly."""
    return _core.load_retired_gold(GOLD_RETIRED_FILE)


def sleeve_set() -> list[dict]:
    """All active sleeves: gold book + promoted, with window metadata.

    The admission rules -- which gold windows the promoter has retired, which promoted rows
    carry validated semantics, the `auto_ramp` rewrite that keeps the promoter's literal lot
    from ever reaching the venue -- are `decision_core.roster`; this reads the two files it
    decides over and logs what it declined.
    """
    sleeves, notes = roster(_load_retired_gold(), load_sleeves())
    for note in notes:
        log(note)
    return sleeves


#: The one-file arm switch for generic family execution. ABSENT = every family sleeve logs the
#: exact order it would place and places nothing; the operator watches it be right, then
#: `type nul > data\GENERIC_EXEC_ENABLED` is the deliberate human act that arms the lane.
GENERIC_EXEC_ENABLED = BASE / "data" / "GENERIC_EXEC_ENABLED"

#: RELEASE IDENTITY (2026-09-05). The code this box runs must be the code that was sealed,
#: tested and merged -- one SHA. When it is not (a stale checkout, a trampled module, a seal that
#: never landed, an identity that cannot be measured), the gateway keeps managing what is open
#: and opens NOTHING new: stops still ratchet, TTLs still close, reconciliation still runs. Set
#: once per pass in `main()` from `mt5desk.release_identity.verdict()`; the three placement
#: sites read it. Unmeasured is not a licence, so the default before the first measurement
#: is a refusal.
NEW_RISK_OK: bool = False


def _policy_advice(symbol: str, side: int, entry_ref: float, tick, sym, dist: float, g,
                   lot: float = 0.0) -> dict:
    """The execution policy's shadow choice for one order. NEVER raises, never routes.

    THE LOT IS THE REAL LOT, NOT 0.0. The algorithm registry (`execution_registry.compete`)
    splits a parent order into children -- a TWAP slices it, an iceberg displays part of it --
    and a zero-lot intent gives the schedulers nothing to split, so every algorithm priced
    identically and the competition on the intent row was vacuous. Called after `promoted_lot`
    so the row carries the competition on the order that is actually about to be placed.
    """
    try:
        from mt5desk.execution_policy import choose
        return choose(exec_context(symbol, side, entry_ref, tick, dist, g, lot),
                      _fill_surface())
    except Exception as exc:                                    # noqa: BLE001
        return {"policy": "MARKET", "why": f"advice unavailable: {type(exc).__name__}"}


_SURFACE: object = None


def _fill_surface():
    """The box's own fill/slip surface, fitted once per process from the intent ledger.

    `fill_surface.FillSurface` has no loader for its report, so the surface is refitted here
    from the rows the gateway itself recorded; a cheap ridge on a few hundred fills. None when
    there is nothing to fit -- the policy and the registry then price on the spread prior, which
    is the honest state of a box that has not filled enough to know its own slippage.
    """
    global _SURFACE
    if _SURFACE is None:
        try:
            from mt5desk import fill_surface
            rows = [json.loads(ln) for ln in INTENTS.read_text("utf-8").splitlines()
                    if ln.strip()] if INTENTS.exists() else []
            fs = fill_surface.FillSurface().fit(rows) if rows else None
            _SURFACE = fs if fs is not None else False
        except Exception as exc:                                # noqa: BLE001
            log(f"fill surface unavailable ({type(exc).__name__}: {exc}); spread prior only")
            _SURFACE = False
    return _SURFACE or None


_BOOK: object = None


def _netting_book():
    """The theoretical-position ledger, one per process. A ledger fault never stops a pass.

    WHY A LEDGER BESIDE THE TERMINAL. The terminal knows the account's net position per
    symbol; it does not know which sleeve wants what. Two sleeves long and short the same
    symbol net to nothing at the venue, and without a per-sleeve book the desk could neither
    attribute the P&L of each nor measure the spread the netting saved. `netting.TheoreticalBook`
    keeps every sleeve whole and lets `netting.route` compute the ONE order the venue should see.
    Today that order is MEASURED and logged, never sent (see `_net_routes`).
    """
    global _BOOK
    if _BOOK is None:
        try:
            from mt5desk import netting
            _BOOK = netting.TheoreticalBook()
        except Exception as exc:                                # noqa: BLE001
            log(f"netting book unavailable ({type(exc).__name__}: {exc}); pass runs without it")
            _BOOK = False
    return _BOOK or None


def _book_target(name: str, symbol: str, lots_signed: float, reason: str,
                 price: float | None = None) -> None:
    """A sleeve's desired signed position, asserted every pass (idempotent). Shadow included."""
    book = _netting_book()
    if book is None:
        return
    try:
        book.set_target(name, symbol, float(lots_signed), reason=reason,
                        at=datetime.now(tz=UTC), price=price)
    except Exception as exc:                                    # noqa: BLE001
        log(f"[{name}] netting target not recorded ({type(exc).__name__}: {exc})")


def _book_fill(name: str, symbol: str, lots_signed: float, price: float) -> None:
    """What the venue actually gave a sleeve. Exits the broker performs (stop, target) are not
    seen here; `_net_routes` reports the resulting ledger-vs-terminal gap as a finding."""
    book = _netting_book()
    if book is None:
        return
    try:
        book.fill(name, symbol, float(lots_signed), float(price), at=datetime.now(tz=UTC))
    except Exception as exc:                                    # noqa: BLE001
        log(f"[{name}] netting fill not recorded ({type(exc).__name__}: {exc})")


def _record_exec_outcome(symbol: str, side: int, lot: float, entry_ref: float, tick,
                         dist: float, g, fill_price: float) -> None:
    """What the market algorithm expected against what the venue did -- the learning loop
    behind algorithm choice. Market is what is actually sent today; once an algorithm is
    routed, the plan recorded here is the one that ran."""
    try:
        from mt5desk import execution_registry
        from mt5desk.execution_policy import intent_of
        ctx = exec_context(symbol, side, entry_ref, tick, dist, g, lot)
        plan = execution_registry.market(intent_of(ctx), surface=_fill_surface())
        execution_registry.record_outcome(plan, [(float(lot), float(fill_price))],
                                          at=datetime.now(tz=UTC))
    except Exception as exc:                                    # noqa: BLE001
        log(f"execution outcome not recorded for {symbol} ({type(exc).__name__}: {exc})")


def _net_routes(symbols: set[str]) -> None:
    """The ONE order per symbol the venue would see if the sleeves were netted -- measured and
    logged as NET WOULD SEND, never placed. Also reconciles the ledger's account position
    against the terminal's: a disagreement is a finding to log (exits the broker performed,
    fills from before the ledger existed), never something to auto-correct."""
    book = _netting_book()
    if book is None or not symbols:
        return
    from mt5desk import netting
    for symbol in sorted(symbols):
        try:
            tick = mt5.symbol_info_tick(symbol)
            sym = mt5.symbol_info(symbol)
            if tick is None or sym is None:
                continue
            mid = 0.5 * (float(tick.bid) + float(tick.ask))
            r = netting.route(book, symbol, mid,
                              lot_step=float(getattr(sym, "volume_step", 0.01) or 0.01),
                              lot_min=float(getattr(sym, "volume_min", 0.01) or 0.01))
            log(f"[netting] {symbol} NET WOULD SEND {r.get('side')} {r.get('lots')} "
                f"(delta {r.get('delta')}, netted {r.get('netted_lots')} lots across "
                f"{len(r.get('sleeves') or [])} sleeves){' -- ' + str(r['why']) if r.get('why') else ''}")
            terminal = 0.0
            for p in mt5.positions_get(symbol=symbol) or []:
                sgn = 1.0 if int(getattr(p, "type", 0)) == 0 else -1.0
                terminal += sgn * float(getattr(p, "volume", 0.0) or 0.0)
            ledger = float(book.account_position(symbol))
            if abs(terminal - ledger) > 1e-9:
                log(f"[netting] {symbol} ledger {ledger:+.2f} vs terminal {terminal:+.2f} lots"
                    f" -- broker-side exits or pre-ledger fills; reported, not corrected")
        except Exception as exc:                                # noqa: BLE001
            log(f"[netting] {symbol} route unmeasured ({type(exc).__name__}: {exc})")

def run_family_sleeves(st: dict, sleeves: list[dict], equity: float) -> None:
    """Execute hunt-certified family sleeves with replay-faithful semantics (GAP 124).

    FAITHFUL TO THE REPLAY OR NOT AT ALL: signals come from the SAME
    `run_hunt16.FAMILIES[family]` code the forward clock replays, filtered to the same
    selector hour and day-state condition; entry is market at the open following the signal
    bar (the engine's fill rule); sl/tp are the Signal's own absolute levels; TTL closes the
    position `ttl_bars` hours after entry. Anything this function cannot compute exactly is a
    loud skip, never an approximation -- trading a lookalike strategy under a certified
    sleeve's name is the defect class `state_allows` documents.

    The decision steps -- which closed bar is the signal bar, whether it was already
    considered, the state gate, the signal itself, the entry and its stop, the time exit -- are
    `decision_core.family_*`; this function reads the terminal, records what the core decided
    in the pass state, and sends the order.
    """
    fam_sleeves = [s for s in sleeves if s.get("exec") == "family_market"]
    if not fam_sleeves:
        return
    try:
        from research.run_hunt12 import day_states
        from research.run_hunt16 import FAMILIES, WINDOWS
    except Exception as exc:
        log(f"FAMILY-EXEC unavailable ({type(exc).__name__}: {exc}); "
            f"{len(fam_sleeves)} certified sleeve(s) NOT traded this pass")
        return
    armed = bool(st.get("armed")) and GENERIC_EXEC_ENABLED.exists() and NEW_RISK_OK
    gstate = st.setdefault("generic", {})
    now_utc = datetime.now(tz=UTC)
    for s in fam_sleeves:
        name, family, selector = s["name"], s.get("family"), s.get("selector")
        side = 1 if str(s.get("side", "LONG")).upper() == "LONG" else -1
        if family not in FAMILIES or selector not in WINDOWS:
            log(f"[{name}] FAMILY-EXEC refused: family/selector has no exact executable")
            continue
        sig_hour = family_signal_hour(WINDOWS[selector])
        h1 = mt5.copy_rates_from_pos(s["symbol"], mt5.TIMEFRAME_H1, 0, 400)
        if h1 is None or len(h1) < 60:
            log(f"[{name}] FAMILY-EXEC: bars unavailable; skipped")
            continue
        # The last CLOSED bar: current in-progress bar is excluded, exactly as replay sees it.
        closed = h1_frame(h1).iloc[:-1]
        last_bar = family_bar_due(closed, sig_hour)
        if last_bar is None:
            continue
        srec = gstate.setdefault(name, {})
        step = family_signal_step(closed, last_bar, last_signal_bar=srec.get("last_signal_bar"),
                                  want_state=s.get("state"), side=side,
                                  family_fn=FAMILIES[family], day_states_fn=day_states)
        if step.mark:
            srec["last_signal_bar"] = str(last_bar)
        if step.note:
            log(f"[{name}] {step.note}")
        if step.signal is None:
            continue
        g = step.signal
        tick = mt5.symbol_info_tick(s["symbol"])
        sym = mt5.symbol_info(s["symbol"])
        if tick is None or sym is None:
            log(f"[{name}] FAMILY-EXEC: no tick/symbol_info; skipped")
            continue
        entry_ref, dist = family_entry(g, side, tick.bid, tick.ask)
        if not (dist > 0):
            log(f"[{name}] FAMILY-EXEC: degenerate stop distance; skipped")
            continue
        # EXECUTION POLICY, IN SHADOW: what the utility-maximising plan would have been for this
        # order (market / passive / pullback / split / skip), recorded on the intent so the
        # counterfactual ledger can score the road not taken. Routing stays MARKET until the
        # fill surface is fitted on enough of the box's own fills to make the choice measured.
        try:
            lot = promoted_lot(equity, sleeve_live_n(name), dist, s["symbol"], sym,
                               s.get("risk_frac"), s.get("decay_faded"),
                               from_book=(s.get("sized_by") == "allocator_book"))
        except Exception as exc:
            log(f"[{name}] FAMILY-EXEC: cannot price risk ({exc}); skipped")
            continue
        if not (lot > 0):
            log(f"[{name}] FAMILY-EXEC: allocator gave this sleeve no heat; skipped")
            continue
        policy_advice = _policy_advice(s["symbol"], side, entry_ref, tick, sym, dist, g, lot)
        # The theoretical book sees every intent, armed or not, so netting is measured in shadow.
        _book_target(name, s["symbol"], side * lot, f"family_market/{family}/{selector}",
                     price=entry_ref)
        ttl_until = family_ttl_until(last_bar, g.ttl_bars)
        order_desc = family_order_desc(side, lot, s["symbol"], g, ttl_until)
        if not armed:
            log(f"[{name}] WOULD PLACE (generic exec "
                f"{'not armed' if st.get('armed') else 'account unarmed'}; "
                f"enable={GENERIC_EXEC_ENABLED.name}): {order_desc}")
            continue
        if not margin_ok(s["symbol"], lot, entry_ref):
            log(f"[{name}] FAMILY-EXEC SKIPPED: margin tight (lot={lot})")
            continue
        res = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": s["symbol"], "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if side == 1 else mt5.ORDER_TYPE_SELL,
            "price": entry_ref, "sl": float(g.stop), "tp": float(g.target),
            "deviation": 20, "magic": MAGIC, "comment": f"DW{name}"[:31],
        })
        rc = res.retcode if res else None
        _record_intent(sleeve=name, symbol=s["symbol"],
                       side=("buy" if side == 1 else "sell"), lot=lot,
                       intended=entry_ref, sl=float(g.stop), tp=float(g.target),
                       ticket=(getattr(res, "order", None) if res else None), retcode=rc,
                       policy_advice=policy_advice)
        log(f"[{name}] FAMILY-EXEC ORDER -> retcode={rc} {diagnose(rc, getattr(res, 'comment', '') or '')} "
            f"| {order_desc}")
        if rc in (10008, 10009):
            srec["open_ttl_until"] = ttl_until
            fill_px = float(getattr(res, "price", 0.0) or entry_ref)
            _book_fill(name, s["symbol"], side * lot, fill_px)
            _record_exec_outcome(s["symbol"], side, lot, entry_ref, tick, dist, g, fill_px)
    # TTL housekeeping: positions past their deadline are closed regardless of P&L -- the
    # replay's ttl exit is part of the certified strategy, not an optional tidy-up.
    for s in fam_sleeves:
        srec = gstate.get(s["name"]) or {}
        if ttl_expired(srec.get("open_ttl_until"), now_utc.isoformat()):
            _book_target(s["name"], s["symbol"], 0.0, "ttl")
            if st.get("armed") and GENERIC_EXEC_ENABLED.exists():
                close_positions(st, s["symbol"])
            else:
                log(f"[{s['name']}] SHADOW would TTL-close open position(s)")
            srec.pop("open_ttl_until", None)


def _sleeve_positions(symbol: str, name: str) -> list:
    """Open positions this sleeve owns: the order comment is the sleeve's tag."""
    tag = f"DW{name}"[:31]
    return [p for p in (mt5.positions_get(symbol=symbol) or [])
            if str(getattr(p, "comment", "") or "") == tag]


def close_sleeve_positions(st: dict, symbol: str, name: str) -> None:
    """Close ONE sleeve's positions on a symbol, never the symbol's whole book.

    `close_positions` closes every position on the symbol, which on XAUUSD would take the armed
    gold windows down with a scalp basket's time exit. Scoped by the order comment instead.
    """
    if not st.get("armed"):
        log(f"[{name}] SHADOW would close its open position(s)")
        return
    for p in _sleeve_positions(symbol, name):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            continue
        res = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": p.volume,
            "type": (mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY
                     else mt5.ORDER_TYPE_BUY),
            "position": p.ticket,
            "price": tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "deviation": 20, "magic": MAGIC, "comment": f"DW{name}"[:31],
        })
        log(f"[{name}] CLOSE ticket {p.ticket} -> retcode={res.retcode if res else None}")


def _retarget_sleeve_positions(symbol: str, name: str, sl: float, tp: float) -> None:
    """Move every slice's target to the basket's new average-entry target (stop unchanged)."""
    for p in _sleeve_positions(symbol, name):
        res = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket,
                              "symbol": symbol, "sl": float(sl), "tp": float(tp),
                              "magic": MAGIC})
        log(f"[{name}] RETARGET ticket {p.ticket} tp={tp:.5f} -> "
            f"retcode={res.retcode if res else None}")


def run_scalp_sleeves(st: dict, sleeves: list[dict], equity: float) -> None:
    """Execute promoted scalp sleeves with replay-faithful semantics (principal 2026-09-04).

    FAITHFUL TO THE REPLAY OR NOT AT ALL, as for the family lane: the signal, the ATR geometry,
    the four-slice structural basket and the time exit are `mt5desk/scalp_exec.py`'s reading
    of `scalp_reverse_engineering.simulate`, computed on the broker's own M5/M15 bars. The one
    stated deviation is the stop's ATR (last closed bar, since the replay's bar-i ATR cannot be
    known at the open). Sized by `promoted_lot` like every other sleeve, so the allocator book's
    fraction reaches the venue unshrunk; LOG-ONLY under the same arm switch as the family lane.
    The recipe, the time exit, the basket arithmetic and the order lines are
    `decision_core`'s; this function reads the bars and the tick, keeps the pass state, and
    sends.
    """
    sc_sleeves = [s for s in sleeves if s.get("exec") == "scalp_market"]
    if not sc_sleeves:
        return
    try:
        from mt5desk import scalp_exec as sx
    except Exception as exc:
        log(f"SCALP-EXEC unavailable ({type(exc).__name__}: {exc}); "
            f"{len(sc_sleeves)} sleeve(s) NOT traded this pass")
        return
    armed = bool(st.get("armed")) and GENERIC_EXEC_ENABLED.exists() and NEW_RISK_OK
    gstate = st.setdefault("scalp", {})
    now_iso = datetime.now(tz=UTC).isoformat()
    for s in sc_sleeves:
        name, tf = s["name"], str(s.get("timeframe") or "")
        tf_attr = sx.MT5_TIMEFRAME_ATTR.get(tf)
        if tf_attr is None or not hasattr(mt5, tf_attr):
            log(f"[{name}] SCALP-EXEC refused: timeframe {tf!r} has no exact executable")
            continue
        try:
            family, session, stop_atr, target_atr, max_hold = scalp_recipe(s)
        except (KeyError, TypeError, ValueError) as exc:
            log(f"[{name}] SCALP-EXEC refused: recipe incomplete ({exc})")
            continue
        rates = mt5.copy_rates_from_pos(s["symbol"], getattr(mt5, tf_attr), 0, sx.BARS_NEEDED)
        if rates is None or len(rates) < sx.MIN_BARS + 1:
            log(f"[{name}] SCALP-EXEC: bars unavailable; skipped")
            continue
        try:
            df = sx.frame_from_rates(rates)
        except ValueError as exc:
            log(f"[{name}] SCALP-EXEC: bars unreadable ({exc}); skipped")
            continue
        closed, forming = df.iloc[:-1], df.index[-1]
        srec = gstate.setdefault(name, {})
        basket = srec.get("basket")
        # THE BASKET ENDS WHEN THE BROKER SAYS SO: stop, target or the day's force-close leave no
        # position, and a basket with no position must not accept an add-on slice.
        if basket and armed and not _sleeve_positions(s["symbol"], name):
            srec.pop("basket", None)
            srec.pop("open_ttl_until", None)
            basket = None
            _book_target(name, s["symbol"], 0.0, "bracket_exit")
        # THE TIME EXIT is part of the certified strategy, not an optional tidy-up.
        if ttl_expired(srec.get("open_ttl_until"), now_iso):
            _book_target(name, s["symbol"], 0.0, "ttl")
            close_sleeve_positions(st, s["symbol"], name)
            srec.pop("open_ttl_until", None)
            srec.pop("basket", None)
            basket = None
        if srec.get("last_signal_bar") == str(forming):
            continue                                   # this bar's open already considered
        srec["last_signal_bar"] = str(forming)
        tick = mt5.symbol_info_tick(s["symbol"])
        sym = mt5.symbol_info(s["symbol"])
        if tick is None or sym is None:
            log(f"[{name}] SCALP-EXEC: no tick/symbol_info; skipped")
            continue
        from_book = (s.get("sized_by") == "allocator_book")
        if basket:
            # AN ADD-ON SLICE, at this bar's open, on the replay's own conditions.
            side = int(basket["side"])
            price = float(tick.ask if side == 1 else tick.bid)
            try:
                ok = sx.addon_allowed(closed, tf=tf, family=family, session=session, side=side,
                                      stop=float(basket["stop"]), depth=len(basket["entries"]),
                                      price=price, forming_time=forming)
            except Exception as exc:
                log(f"[{name}] SCALP-EXEC add-on signal failed ({exc}); skipped")
                continue
            if not ok or basket.get("mode") != "bounded_structural":
                continue
            dist = abs(price - float(basket["stop"]))
            try:
                lot = promoted_lot(equity, sleeve_live_n(name), dist, s["symbol"], sym,
                                   s.get("risk_frac"), s.get("decay_faded"),
                                   from_book=(s.get("sized_by") == "allocator_book"))
            except Exception as exc:
                log(f"[{name}] SCALP-EXEC: cannot price add-on risk ({exc}); skipped")
                continue
            per, mode = sx.slice_lot(lot, float(getattr(sym, "volume_min", 0.01) or 0.01),
                                     float(getattr(sym, "volume_step", 0.01) or 0.01))
            if mode != "bounded_structural" or not (per > 0):
                continue
            entries = addon_entries(basket["entries"], price, per)
            new_tp = sx.basket_target(entries, side, float(basket["target_atr"]),
                                      float(basket["atr"]))
            desc = addon_desc(side, per, s["symbol"], float(basket["stop"]), new_tp,
                              len(entries))
            if not armed:
                log(f"[{name}] WOULD PLACE (scalp exec not armed): {desc}")
                continue
            if not margin_ok(s["symbol"], per, price):
                log(f"[{name}] SCALP-EXEC add-on SKIPPED: margin tight (lot={per})")
                continue
            res = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL, "symbol": s["symbol"], "volume": per,
                "type": mt5.ORDER_TYPE_BUY if side == 1 else mt5.ORDER_TYPE_SELL,
                "price": price, "sl": float(basket["stop"]), "tp": float(new_tp),
                "deviation": 20, "magic": MAGIC, "comment": f"DW{name}"[:31],
            })
            rc = res.retcode if res else None
            _record_intent(sleeve=name, symbol=s["symbol"],
                           side=("buy" if side == 1 else "sell"), lot=per, intended=price,
                           sl=float(basket["stop"]), tp=float(new_tp),
                           ticket=(getattr(res, "order", None) if res else None), retcode=rc,
                           slice_depth=len(entries))
            log(f"[{name}] SCALP-EXEC ADD-ON -> retcode={rc} "
                f"{diagnose(rc, getattr(res, 'comment', '') or '')} | {desc}")
            if rc in (10008, 10009):
                basket["entries"] = [[p, u] for p, u in entries]
                basket["target"] = float(new_tp)
                _book_fill(name, s["symbol"], side * per,
                           float(getattr(res, "price", 0.0) or price))
                _book_target(name, s["symbol"], side * basket_lots(entries),
                             "scalp_market/add-on", price=price)
                _retarget_sleeve_positions(s["symbol"], name, float(basket["stop"]),
                                           float(new_tp))
            continue
        try:
            plan = sx.plan_entry(closed, tf=tf, family=family, session=session,
                                 stop_atr=stop_atr, target_atr=target_atr, max_hold=max_hold,
                                 bid=float(tick.bid), ask=float(tick.ask), forming_time=forming)
        except Exception as exc:
            log(f"[{name}] SCALP-EXEC signal computation failed ({exc}); skipped")
            continue
        if plan is None:
            continue
        try:
            lot = promoted_lot(equity, sleeve_live_n(name), plan.stop_dist, s["symbol"], sym,
                               s.get("risk_frac"), s.get("decay_faded"), from_book=from_book)
        except Exception as exc:
            log(f"[{name}] SCALP-EXEC: cannot price risk ({exc}); skipped")
            continue
        if not (lot > 0):
            log(f"[{name}] SCALP-EXEC: allocator gave this sleeve no heat; skipped")
            continue
        per, mode = sx.slice_lot(lot, float(getattr(sym, "volume_min", 0.01) or 0.01),
                                 float(getattr(sym, "volume_step", 0.01) or 0.01))
        if not (per > 0):
            log(f"[{name}] SCALP-EXEC: lot {lot} below the symbol's minimum; skipped")
            continue
        policy_advice = _policy_advice(s["symbol"], plan.side, plan.entry_ref, tick, sym,
                                       plan.stop_dist, plan, per)
        _book_target(name, s["symbol"], plan.side * per, f"scalp_market/{family}",
                     price=plan.entry_ref)
        desc = scalp_order_desc(plan, per, s["symbol"], mode)
        if not armed:
            log(f"[{name}] WOULD PLACE (scalp exec "
                f"{'not armed' if st.get('armed') else 'account unarmed'}; "
                f"enable={GENERIC_EXEC_ENABLED.name}): {desc}")
            continue
        if not margin_ok(s["symbol"], per, plan.entry_ref):
            log(f"[{name}] SCALP-EXEC SKIPPED: margin tight (lot={per})")
            continue
        res = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": s["symbol"], "volume": per,
            "type": mt5.ORDER_TYPE_BUY if plan.side == 1 else mt5.ORDER_TYPE_SELL,
            "price": plan.entry_ref, "sl": float(plan.stop), "tp": float(plan.target),
            "deviation": 20, "magic": MAGIC, "comment": f"DW{name}"[:31],
        })
        rc = res.retcode if res else None
        _record_intent(sleeve=name, symbol=s["symbol"],
                       side=("buy" if plan.side == 1 else "sell"), lot=per,
                       intended=plan.entry_ref, sl=float(plan.stop), tp=float(plan.target),
                       ticket=(getattr(res, "order", None) if res else None), retcode=rc,
                       policy_advice=policy_advice, slice_depth=1)
        log(f"[{name}] SCALP-EXEC ORDER -> retcode={rc} "
            f"{diagnose(rc, getattr(res, 'comment', '') or '')} | {desc}")
        if rc in (10008, 10009):
            srec["open_ttl_until"] = plan.ttl_until
            fill_px = float(getattr(res, "price", 0.0) or plan.entry_ref)
            _book_fill(name, s["symbol"], plan.side * per, fill_px)
            _record_exec_outcome(s["symbol"], plan.side, per, plan.entry_ref, tick,
                                 plan.stop_dist, plan, fill_px)
            srec["basket"] = basket_record(plan, per, mode, target_atr)


def main() -> None:
    if gateway_paused():
        log("gateway paused (data/GATEWAY_PAUSED present); no trading this pass")
        return
    if not connect():
        return
    st = load_state()
    tick = mt5.symbol_info_tick("XAUUSD")
    if tick is None:
        log("no tick; market likely closed")
        mt5.shutdown()
        return
    equity = float(mt5.account_info().equity)
    st["equity"] = round(equity, 2)

    tnow = pd.Timestamp(tick.time, unit="s", tz="UTC")
    today = tnow.date()
    hour = tnow.hour + tnow.minute / 60.0
    day_key = str(today)

    # stale tick (weekend/holiday/terminal dead): never trade a closed market
    age_sec = (datetime.now(tz=UTC) - tnow).total_seconds()
    if age_sec > 1800:
        st = reconcile(st)
        save_state(st)
        log(f"idle: tick stale {age_sec/60:.0f} min (last {tnow}); market closed")
        mt5.shutdown()
        return

    if st["last_bracket_date"] != day_key:
        st["brackets"] = {}
        st["last_bracket_date"] = day_key
        save_state(st)

    sleeves = sleeve_set()

    # MANAGE WHAT IS ALREADY OPEN BEFORE CONSIDERING ANYTHING NEW, and run it on EVERY pass --
    # before the regime filter, before the equity floor, before heat. Those gates decide whether
    # to OPEN a position; a position that is already on carries risk regardless of whether the
    # desk would enter it again today, and hibernating a sleeve must not orphan its open trade.
    # Shadow unless st["armed"]: unarmed passes log the modification they would have sent.
    try:
        manage_open_positions(st, sleeves)
    except Exception as exc:
        # Never let management take the gateway down. A desk that cannot ratchet a stop is
        # degraded; a desk that cannot place or reconcile anything because management raised is
        # broken, and the second is strictly worse than the first.
        log(f"MANAGE FAILED (positions left untouched): {type(exc).__name__}: {exc}")
    save_state(st)

    # RELEASE IDENTITY: measured after management and before anything that could open a
    # position, so a refusal costs new entries only. The verdict file travels with the box's
    # git sync; the reason is logged every pass it refuses so it never reads as a quiet day.
    global NEW_RISK_OK
    NEW_RISK_OK, _ident_why = release_gate()
    if not NEW_RISK_OK:
        log(f"RELEASE IDENTITY refuses NEW risk: {_ident_why} -- managing open positions only")

    reg_killed = regime_hibernate(sleeves)
    # THE VETOED SLEEVES ARE KEPT ASIDE, NOT FORGOTTEN. They are removed from `sleeves` so nothing
    # downstream sizes or places them, and walked once more below -- after the bracket loop, on
    # the same bars -- purely to write what they would have placed into the decision ledger.
    _hibernated = [s for s in sleeves if s["name"] in reg_killed] if reg_killed else []
    if reg_killed:
        log(f"REGIME: auto-hibernate, no new brackets: {reg_killed}")
        sleeves = [s for s in sleeves if s["name"] not in reg_killed]
    if equity < PROMOTED_MIN_EQUITY:
        sleeves = [s for s in sleeves if s["name"].startswith("gold_")]
        if load_sleeves():
            log(f"equity {equity:.0f} < {PROMOTED_MIN_EQUITY:.0f}: promoted sleeves dormant")
    # AGGREGATE HEAT, applied after every other filter so it sees the sleeves that would really
    # trade. Deferred sleeves are named in the log rather than dropped quietly.
    #
    # k_eff IS MEASURED AND PASSED, and until now it was neither. `cap_by_heat(sleeves, equity)`
    # supplied no breadth term, so `heat_budget` returned its base 3.81% on every call and the
    # whole sqrt(k_eff) ladder was dead code -- the book pinned to a three-leg budget however many
    # independent edges it went on to earn. That is a permanent cap on compounding, which is the
    # opposite of what the budget was written to do: breadth is meant to be PAID FOR with measured
    # orthogonality and then spent.
    #
    # The estimate is deliberately conservative in three ways, because an overstated k_eff feeds
    # straight into leverage: correlations are computed on overlapping days only (never zero
    # filled), the 95% UPPER bound on mean correlation is used rather than the point estimate, and
    # an unmeasurable book returns None, which routes back to the base budget rather than to the
    # ceiling.
    # CURRENCY CONCENTRATION BINDS THE BUDGET TOO, from the positions actually open.
    #
    # Return correlation is backward-looking and estimated on the quiet sample: four sleeves each
    # secretly SHORT USD measure as four independent bets for as long as the dollar does not move,
    # and then move together on the day it does. `libs/risk/fx_factors` decomposes a book into its
    # currency legs and reported `n_effective 1.019 across 17 sleeves` on the live survivor set --
    # seventeen positions behaving as one bet. It had ZERO non-test callers.
    #
    # EXPOSURES COME FROM OPEN POSITIONS, NOT FROM THE SLEEVE ROSTER, and the distinction is not
    # pedantry: a session bracket places a buy stop AND a sell stop, so its direction does not
    # exist until one of them fills. Reading intent off the roster would assume a sign the desk
    # has not taken, and could tighten the budget against a book that is genuinely two-sided.
    # A flat book has nothing to concentrate and so correctly constrains nothing.
    _exposure: dict[str, float] = {}
    try:
        for _p in mt5.positions_get() or []:
            _sgn = 1.0 if int(getattr(_p, "type", 0)) == 0 else -1.0
            _exposure[str(_p.symbol)] = _exposure.get(str(_p.symbol), 0.0) + _sgn * float(
                getattr(_p, "volume", 0.0) or 0.0)
    except Exception as _exc:
        # A breadth MEASUREMENT must never stop the trading loop. An unreadable position list
        # leaves exposures empty, which leaves the budget exactly as the return series set it.
        log(f"factor breadth: positions unreadable ({type(_exc).__name__}: {_exc}); "
            f"return breadth alone")
    k_eff, k_why = measure_from_ledger(
        ledger_rows(), _prov.current_account(mt5.account_info()),
        exposures=_exposure or None)
    log(k_why)
    # Read ONCE per pass: the book is an artifact, and re-reading it per sleeve could size two
    # legs of the same pass from two different solves if the allocator rewrote it mid-loop.
    _book, _book_why = allocator_book()
    log(f"sizing: {_book_why}")
    # EACH SLEEVE'S LAST REAL STOP, so the cap prices legs on what they actually traded rather
    # than on a house average. The gateway already records every bracket it places; not reading
    # them back meant the one number that decides how much heat a leg costs was the only number
    # the cap did not have.
    for _s in sleeves:
        _spec = (st.get("brackets", {}).get(_s["name"]) or {}).get("spec")
        _d = stop_distance(_spec) if _spec else None
        if _d:
            _s["dist"] = _d
        # A risk_frac sleeve is BILLED its own effective fraction (base x ramp), not the house
        # Q_OPT -- undercharging heat for the very sleeves running above Q_OPT would recreate
        # the 2.94%-believed/22.2%-true defect documented on cap_by_heat.
        # THE OPTIMISER'S OWN FRACTION, WHEN IT HAS EARNED THE RIGHT TO SET IT. h_i is what
        # maximised E[log W] jointly with every other sleeve; Q_OPT and the ramp are what the
        # desk falls back to when nothing solved for it. Only reachable behind a fresh proof
        # certificate (see `allocator_book`), so an unproven allocator cannot resize the book.
        from_book = _book is not None and _s["name"] in _book
        if from_book:
            _s["risk_frac"] = float(_book[_s["name"]])
            _s["sized_by"] = "allocator_book"
            # BILLED AT EXACTLY THE FRACTION IT IS SIZED AT (see promoted_lot from_book): the
            # heat cap and the sizer must price the same leg at the same number.
            _s["q_charge"] = float(_book[_s["name"]]) * decay_factor(_s.get("decay_faded"))
        elif _s.get("lot") == "auto_ramp":
            # THE SAME LADDER THE SIZER USES (`decision_core.ramped_fraction`): base clamp x
            # authority ramp x fade. A second copy of it here, beside promoted_lot's, was how the
            # heat ledger and the order path could come to disagree about the same leg.
            _s["q_charge"] = ramped_fraction(_s.get("risk_frac"), sleeve_live_n(_s["name"]),
                                             _s.get("decay_faded"))
    sleeves, heat_note = cap_by_heat(sleeves, equity, k_eff=k_eff)
    if heat_note:
        log(heat_note)
    # Hunt-certified family sleeves run their own replay-faithful executor -- AFTER the heat
    # cap, so an inadmissible sleeve never reaches it, and OUTSIDE the bracket loop, whose
    # session-window semantics they do not share.
    try:
        run_family_sleeves(st, sleeves, equity)
    except Exception as exc:
        log(f"FAMILY-EXEC FAILED (bracket path unaffected): {type(exc).__name__}: {exc}")
    try:
        run_scalp_sleeves(st, sleeves, equity)
    except Exception as exc:
        log(f"SCALP-EXEC FAILED (bracket path unaffected): {type(exc).__name__}: {exc}")
    # The net order per symbol across every sleeve's theoretical position -- measured, never
    # sent: the ledger's answer to "what would the venue see if the sleeves were netted".
    try:
        _net_routes({s["symbol"] for s in sleeves
                     if s.get("exec") in ("family_market", "scalp_market")})
    except Exception as exc:
        log(f"netting measurement FAILED (trading unaffected): {type(exc).__name__}: {exc}")
    save_state(st)
    if st["last_bracket_date"] == day_key:
        for s in sleeves:
            if s.get("exec") in ("family_market", "scalp_market"):
                continue
            if st["brackets"].get(s["name"]):
                continue
            if hour < s["sig_hour"]:
                continue
            sym = mt5.symbol_info(s["symbol"])
            if sym is None:
                continue
            h1 = mt5.copy_rates_from_pos(s["symbol"], mt5.TIMEFRAME_H1, 0, 400)
            if h1 is None:
                log(f"copy_rates failed {s['symbol']}: {mt5.last_error()}")
                continue
            df = h1_frame(h1)
            # THE STATE GATE, applied before any bracket is computed. A conditioned sleeve that
            # cannot confirm its state does not trade -- see `state_allows`.
            ok_state, why_state = state_allows(s, df, datetime.now(tz=UTC).date())
            if not ok_state:
                log(f"[{s['name']}] no trade today: {why_state}")
                # The gate's refusal is a decision with a P&L; write what it refused, once.
                _vetoed = st.setdefault("vetoed_today", {})
                if _vetoed.get(s["name"]) != day_key and _record_vetoed_bracket(
                        s, df, sym, "state_gate", why_state):
                    _vetoed[s["name"]] = day_key
                    save_state(st)
                continue
            # THE RANGE, THE ATR AND THE BRACKET are one computation in the core, shared with
            # the veto record so the ledger's "would have placed" is exactly this.
            built = bracket_from_bars(df, s["rng"], s["sig_hour"], sym.trade_tick_size,
                                      int(getattr(sym, "trade_stops_level", 0) or 20))
            if built is None:
                log(f"[{s['name']}] range not ready at {hour:.1f}")
                continue
            hi, lo, spec = built
            # SIZE AGAINST THIS SLEEVE'S OWN STOP, which `spec` holds one line above.
            # Sizing from the house DIST_USD while the real bracket was in hand made every
            # wide-session sleeve trade 2.5-2.8x its budget -- see `auto_lot`.
            dist = stop_distance(spec)
            if dist is None:
                log(f"[{s['name']}] SKIPPED: bracket spec has no usable stop distance; "
                    f"refusing to size from the house average")
                continue
            # SIZE IN THIS SLEEVE'S OWN INSTRUMENT, from the LIVE symbol_info already in hand.
            # `sym` carries trade_tick_value, which is what the venue will actually credit for
            # one tick in the account currency at today's FX -- the quantity `CONTRACT_OZ *
            # FX_EUR` was a frozen stand-in for. A sleeve whose risk cannot be priced does not
            # trade, for the same reason a sleeve with no usable stop does not.
            try:
                lot = auto_lot(equity, dist, s["symbol"], sym) if s["lot"] == "auto" else (
                    promoted_lot(equity, sleeve_live_n(s["name"]), dist, s["symbol"], sym,
                                 s.get("risk_frac"), s.get("decay_faded"),
                                 from_book=(s.get("sized_by") == "allocator_book"))
                    if s["lot"] == "auto_ramp" else float(s["lot"]))
                q_real = realised_q(equity, dist, s["symbol"], sym, lot=lot)
            except Exception as exc:
                log(f"[{s['name']}] SKIPPED: cannot price {s['symbol']} risk in account "
                    f"currency ({exc}); refusing to size from the house average")
                continue
            if not (lot > 0):
                log(f"[{s['name']}] SKIPPED: allocator gave this sleeve no heat")
                continue
            log(f"[{s['name']}] stop {dist:.5g} -> lot {lot:.2f} "
                f"(realised q {q_real:.2%})")
            # margin guard (machine kill switch): skip sleeve if tight
            if not margin_ok(s["symbol"], lot, max(hi, lo)):
                log(f"[{s['name']}] SKIPPED: margin tight (lot={lot})")
                for _side, _px in (("buy_stop", hi), ("sell_stop", lo)):
                    _record_decision(sleeve=s["name"], symbol=s["symbol"], side=_side, lot=lot,
                                     price=_px, sl=None, tp=None, taken=False,
                                     reason="margin_guard")
                st["brackets"][s["name"]] = {"date": day_key, "hi": hi, "lo": lo,
                                             "spec": spec, "result": {"margin": False}}
                save_state(st)
                continue
            pend = mt5.orders_get(symbol=s["symbol"]) or []
            matches = [
                o for o in pend
                if abs(o.price_open - spec["buy_stop"]["price"]) < 0.5
                or abs(o.price_open - spec["sell_stop"]["price"]) < 0.5
            ]
            if matches:
                st["brackets"][s["name"]] = {"date": day_key, "recovered": True,
                                             "hi": hi, "lo": lo, "spec": spec}
                log(f"recovered [{s['name']}] bracket for {day_key}")
                save_state(st)
                continue
            if not NEW_RISK_OK:
                # The bracket is computed and written as a not-taken decision, so the ledger
                # shows what the sealed code would have placed while the running code could not.
                log(f"[{s['name']}] bracket NOT placed: release identity refuses new risk")
                try:
                    _record_decision(sleeve=s["name"], symbol=s["symbol"], side=None, lot=lot,
                                     price=None, sl=None, tp=None, taken=False,
                                     reason="release_identity_refused", detail=spec)
                except Exception as exc:                        # noqa: BLE001
                    log(f"release-refusal record failed (non-fatal) [{s['name']}]: "
                        f"{type(exc).__name__}: {exc}")
                continue
            res = place_bracket(st, spec, s["name"], s["symbol"], lot)
            st["brackets"][s["name"]] = {"date": day_key, "hi": hi, "lo": lo,
                                         "spec": spec, "placed_at": now(), "result": res}
            save_state(st)
        # THE HIBERNATE VETO'S LEDGER LINE. Each sleeve the regime monitor silenced today has its
        # would-be bracket computed on the same bars the live loop reads and written as a not-taken
        # decision, once per day. This is the only path by which a hibernated sleeve touches the
        # broker API, and it is read-only: symbol_info and copy_rates, never an order.
        _vetoed = st.setdefault("vetoed_today", {})
        for s in _hibernated:
            if s.get("exec") in ("family_market", "scalp_market") \
                    or _vetoed.get(s["name"]) == day_key:
                continue
            if hour < s.get("sig_hour", 0):
                continue
            try:
                sym = mt5.symbol_info(s["symbol"])
                h1 = mt5.copy_rates_from_pos(s["symbol"], mt5.TIMEFRAME_H1, 0, 400)
                if sym is None or h1 is None:
                    continue
                df = h1_frame(h1)
                if _record_vetoed_bracket(s, df, sym, "regime_hibernate",
                                          f"hibernated by regime monitor: {s['name']}"):
                    _vetoed[s["name"]] = day_key
                    save_state(st)
            except Exception as exc:
                log(f"hibernate ledger [{s['name']}] skipped: {type(exc).__name__}: {exc}")

    # housekeeping: expire stale brackets FIRST (every pass, not just at CANCEL_HOUR), then the
    # end-of-day backstop and the force-close.
    expire_stale_brackets(st)
    if hour >= CANCEL_HOUR:
        for s in sleeves:
            cancel_pending(st, s["symbol"])
    if hour >= CLOSE_HOUR:
        for s in sleeves:
            close_positions(st, s["symbol"])
    if tnow.dayofweek == 4 and hour >= CLOSE_HOUR:  # Friday: weekend close
        for s in sleeves:
            close_positions(st, s["symbol"])

    record_trades(st, sleeves)
    st = reconcile(st)
    save_state(st)
    log(f"state: armed={st['armed']} pos={len(st['position'] or [])} "
        f"pending={len(st['pending'] or [])} brackets={list(st['brackets'])} "
        f"sleeves={len(sleeves)}")
    mt5.shutdown()


if __name__ == "__main__":
    main()
