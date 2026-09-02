"""Shadow-forward validation for hunt6 survivors (10 sleeves).

Deterministic replay on real live H1 bars from SHADOW_START forward. Same
families/engine code as the backtest -> identical signals given identical bars.
No capital: fills simulated at actual bar opens with the account cost model.

Ledger: reports/shadow/ledger_<sym>_<window>.json (full trade list, idempotent).
State:  reports/shadow/shadow_state.json (per sleeve n / cumR / exp / maxDD /
days / status; runs once per UTC day).

Verdict at n>=50 or 14 days active: exp>0.05R and maxDD>-25R -> PROMOTION
CANDIDATE (portfolio study + sizing before any live lot), else KILL.
XAUUSD sleeves here are challengers (hunt6 generic params) vs the armed
hunt5-param gold book.
"""

import json
import sys
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families

BASE = Path(__file__).resolve().parent.parent
# This engine is called both as ``research.shadow_forward`` and as a script on the desk box.
# Keep sibling desk modules ahead of the repository's unrelated ``libs/research`` package, whose
# presence otherwise makes ``import sleeve_registry`` depend on the entry point's path order.
sys.path.insert(0, str(BASE / "research"))
UNI = BASE / "data" / "universe"
SHADOW_DIR = BASE / "reports" / "shadow"
SHADOW_DIR.mkdir(parents=True, exist_ok=True)
LOG = open(BASE / "logs" / "shadow.log", "a", encoding="utf-8")  # noqa: SIM115

SHADOW_START = datetime(2026, 8, 16, tzinfo=UTC)

#: Verdicts that END a row. A blocked evaluation must never overwrite one of these: a KILL that
#: turns back into an unevaluated row would re-enter the book, and a PROMOTION CANDIDATE that
#: loses its verdict to a transient cost-map miss loses a decision the desk already made.
_TERMINAL_STATUSES = ("KILL", "PROMOTED", "DEAD", "REJECTED", "RETIRED", "QUARANTINED",
                      "PROMOTION CANDIDATE", "IDENTITY_BROKEN")


def _is_terminal(status: object) -> bool:
    text = str(status or "").upper()
    return any(text == name or text.startswith(name + "_") for name in _TERMINAL_STATUSES)

WINDOWS = {
    "asia": {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
    "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13, "wait_bars": 8,
                  "rr": 2.0, "ttl_bars": 12},
    "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14, "wait_bars": 12,
                "rr": 2.0, "ttl_bars": 12},
    "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17, "wait_bars": 8,
                  "rr": 2.0, "ttl_bars": 12},
}

#: Grandfathered enrolment only -- hunt6 sleeves already on clocks when enrolment became
#: data-driven. NEVER extend this list by hand: a certificate IS enrolment (RESEARCH §6d, the
#: one-pipeline law), and `certified_sleeves()` below turns every ten-gate pass into a clock on
#: the next daily run with no code edit. Editing this literal instead is the exact defect the
#: same-day fence exists to catch (a certificate sat un-enrolled until a human typed).
#: GRANDFATHERING IS OVER (principal 2026-08-26: "shouldn't all be tested for certification and
#: retired if the 10 gates don't work"). This list held ten hunt6 sleeves that ran WITHOUT a
#: ten-gate certificate. On 2026-08-26 `forward_reconcile` put all ten through the canonical
#: gauntlet: the five `asia` cells hold certificates and now enrol through `certified_sleeves()`
#: like everything else, and the five london_am/afternoon cells FAILED on PBO 0.5961 (threshold
#: 0.50 -- a 60% probability of being backtest-overfit) and are retired RETIRED_GATE_FAIL.
#: The list stays empty: enrolment is a CERTIFICATE, never a literal a human typed.
SLEEVES: list[tuple[str, str]] = []


def certified_sleeves() -> list[tuple[str, str, dict]]:
    """Every runnable certificate as (symbol, window, EXACT certified params).

    Authority AND parameters come from `shadow_admission.authorized_runs` -- the same fail-closed
    door, now carrying the parameterization that actually passed the gauntlet. One clock per
    parameterization: rr=1.5 and rr=2.5 on the same symbol and session are two different
    strategies and each owes its own forward evidence. Before this, all variants shared one clock
    running the WINDOWS default (rr=2.0), so four certified XAUUSD variants were never tested.

    A certificate whose selector this engine has no window for, or which carries no params, is
    reported and skipped -- a visible wiring gap for the gap-wirer, never a silent guess.
    """
    rows: list[tuple[str, str, dict, str]] = []
    try:
        from shadow_admission import authorized_runs
        for run in sorted(authorized_runs(BASE), key=lambda r: (r["symbol"], r["selector"])):
            fam = run["family"]
            if fam == "session_range_breakout":
                if run["selector"] not in WINDOWS:
                    slog(f"ENROL-GAP: certified {run['symbol']}.{run['selector']} has no window "
                         f"mapping; certificate exists but cannot be run -- wire the selector")
                    continue
                # The window supplies the SESSION hours; the certificate supplies everything it
                # was gauntleted with. Certificate wins on overlap: it is the thing that passed.
                params = dict(WINDOWS[run["selector"]])
                params.update(run["params"])
                rows.append((run["symbol"], run["selector"], params, fam))
                continue
            # EVERY certified family owes a clock (one-pipeline law; the same-day fence carried
            # CERTIFIED-NOT-ENROLLED on two overnight_gap_decay certificates while this branch
            # was a bare `continue`). A price-only family replays here exactly as the gauntlet
            # ran it; a family needing runtime inputs beyond bars is skipped BY NAME, because a
            # silent skip is indistinguishable from enrolment that works.
            fn = _family_fn(fam)
            if fn is None:
                slog(f"ENROL-GAP: certified {run['symbol']}.{fam} cannot enrol here -- no "
                     f"constructor found; certificate stands, forward evidence is NOT accruing")
                continue
            # A FAMILY NEEDING RUNTIME INPUTS IS NO LONGER A DEAD END. The gauntlet rebuilds swap
            # terms, peer bars, factor bars, macro and COT series from the candidate's own params;
            # `mt5desk.family_inputs` is that same reconstruction, shared so the two cannot drift.
            # Measured 2026-08-29: this branch was blocking 344 of 615 validity-passing candidates
            # -- cross_asset_residual 140, relative_value 73, carry 72, correlation_regime 30 --
            # every one of them failing ONLY deflated_sharpe, a gate the policy marks curable by
            # forward evidence they were structurally unable to gather. Carry mattered most: it is
            # the desk's only non-directional mechanism and the book's constraint is orthogonality.
            # Whether the inputs actually rebuild is decided per pass, at signal time, where the
            # bars exist -- not guessed here.
            rows.append((run["symbol"], run["selector"], dict(run["params"] or {}), fam))
    except Exception as exc:
        slog(f"certified_sleeves FAILED ({type(exc).__name__}: {exc}); "
             f"running grandfathered sleeves only this pass")
    return rows


def _family_fn(fam: str):
    """The one constructor for `fam`, wherever it lives -- same resolution as the gauntlet."""
    fn = getattr(families, f"family_{fam}", None)
    if fn is None:
        try:
            from mt5desk import families_orthogonal as _fo
            fn = _fo.ORTHOGONAL_FAMILIES.get(fam)
        except ImportError:
            fn = None
    return fn


def _family_needs(fam: str) -> str | None:
    """Runtime input `fam` needs beyond bars, or None when price-only (replayable here)."""
    try:
        from mt5desk.families_orthogonal import FAMILY_INPUTS
    except ImportError:
        return "families_orthogonal unavailable"
    desc = FAMILY_INPUTS.get(fam)
    if desc is None:
        return None  # a families.py native -- bars in, signals out
    return None if desc[1] is None else str(desc[0])


def sleeve_key(sym: str, win: str, params: dict, family: str = "session_range_breakout") -> str:
    """One clock per parameterization -- the key carries what makes them different.

    Breakout keys keep their historical `SYM.window` shape (running clocks must not be renamed);
    every other family carries its family name, because `EURZAR.asia` alone cannot say WHICH
    certified strategy's forward evidence this is.
    """
    extra = {k: v for k, v in sorted(params.items()) if WINDOWS.get(win, {}).get(k) != v}
    sig = "_".join(f"{k}={v}" for k, v in extra.items())
    stem = f"{sym}.{win}" if family == "session_range_breakout" else f"{sym}.{family}.{win}"
    return stem + (f"#{sig}" if sig else "")


FETCH_DAYS = 45
VERDICT_MIN_TRADES = 50
VERDICT_MIN_DAYS = 14
PROMOTE_MIN_EXP = 0.05
PROMOTE_MIN_DD = -25.0
#: SEQUENTIAL SUFFICIENCY (principal 2026-08-26: discovery -> gates -> forward -> live, same day
#: at the front, and the forward leg must actually be reachable). A flat n>=50 is a PROXY for
#: "enough forward evidence to overturn the power-gate doubt". At this desk's measured rate --
#: 5-7 trades per sleeve in 8 days, ~0.75/day -- that proxy costs ~66 days, so the 14-day clause
#: it is AND'd with was dead letter and nothing could ever promote. The fix is not to lower the
#: bar but to MEASURE THE THING THE BAR STANDS FOR: a t-statistic on forward R is valid at any n,
#: so a large true edge clears it early and a weak one still fails at n=200. Strictly more
#: aggressive when the edge is real, strictly stricter when it is marginal.
SEQ_MIN_TRADES = 20      # never a verdict on a handful of trades, however pretty
SEQ_MIN_T = 2.5          # forward mean R significantly > 0, one-sided


def slog(*a) -> None:
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def per_symbol_costs(meta: dict, sym: str):
    """Costs for `sym` from the registry, via the ONE sanctioned constructor.

    THIS FUNCTION HAND-ROLLED THE ARITHMETIC AND CARRIED BOTH DOCUMENTED UNIT BUGS (2026-08-26).

      * `spread = 0.48 if sym == "XAUUSD"` is the hardcode `Costs` warns about in its own
        docstring: 0.48 is dollars PER OUNCE written into a field that wants currency PER LOT, so
        the engine divided it by 100 and charged gold 0.0048/oz -- three percent of a real spread
        the registry itself puts at 0.10/oz and the desk's own fills put at 0.05-0.08. Every gold
        forward R on this desk was accrued very nearly spread-free.
      * `commission_per_lot=3.50` went in unconverted, so on a EUR account the JPY crosses were
        charged 1/184th of their real commission.

    `Costs.from_symbol` is where both fixes live. Hand-rolling here is what kept the money path
    from ever receiving them, which is why this now calls it and a test forbids the hand-roll.

    The commission stays at 3.50 rather than the class default 2.25: it is the higher number and
    nothing here may lower a cost.
    """
    from mt5desk.engine import Costs
    return Costs.from_symbol(meta[sym], commission_per_lot=3.50)


def frozen_costs(key: str):
    """Return the cost basis frozen with ``key``, or ``None`` if it is unavailable.

    The shadow engine cannot substitute current costs when its catalogue has lost a symbol:
    doing so either stops a certified clock or silently reprices it.  A frozen identity already
    contains the complete, cost-aware basis the clock was admitted on, so it is the only safe
    fallback.  Missing or malformed frozen fields remain an explicit evaluation failure.
    """
    import sleeve_registry as registry
    from mt5desk.engine import Costs

    fields = registry.frozen_cost_fields(key)
    required = {"spread_per_lot", "commission_per_lot", "contract_oz", "quote_per_account"}
    if not isinstance(fields, dict) or not required.issubset(fields):
        return None
    try:
        return Costs(**{name: float(fields[name]) for name in required})
    except (TypeError, ValueError):
        return None


def fetch_h1(sym: str):
    """Bars from whatever source is available, with the provenance attached.

    THIS IMPORTED MetaTrader5 DIRECTLY, which made the entire shadow record
    hostage to a Windows box with a logged-in terminal -- on this Linux box the
    daily cycle died on ModuleNotFoundError, and a day of bars not evaluated is
    a day of forward evidence no later run can recover. Shadow needs bars and
    nothing else: no terminal, no login, no funded account, no accepted order.
    See research/h1_source.py. (Re-applied 2026-08-26 after a sync trample
    reverted a0c3de04; the guard tests in tests/test_h1_source.py are the
    fence.)

    Returns a `Bars` (not a DataFrame) so the source travels with the data.
    """
    from datetime import timedelta

    from research.h1_source import fetch_h1 as _fetch
    start = max(SHADOW_START - timedelta(days=FETCH_DAYS),
                datetime(2018, 1, 1, tzinfo=UTC))
    bars = _fetch(sym, start)
    if bars is None:
        slog(f"{sym}: NO DATA from any source. That is an absence of bars, not "
             f"an empty market, and no verdict may be drawn from it.")
        return None
    ok, why = bars.covers(SHADOW_START)
    slog(f"{sym}: {bars.n} bars from {bars.source} -- {why}")
    if not ok:
        # NOT a silent continue: replaying a window the source does not cover
        # would record "no trades" for days that are actually NO DATA, and the
        # promoter would divide by a denominator that includes them.
        return None
    return bars


def clock_breaches() -> dict[str, str]:
    """Keys whose forward clock was SILENTLY REBASED, from the ratchet fence's own report.

    `scripts/check_forward_clock_ratchet.py` has detected these since 2026-08-27 and NOTHING READ
    IT. A silent rebase means a pre-registered forward window was served and then discarded, so
    the desk cannot tell a clock at day 13 from one restarted at day 0 -- and `days >= 14` (L1.58)
    is the single number the whole path to live capital turns on. Detection without consequence
    left the breached sleeve accruing evidence toward that bar as though its window were intact.

    Absence of the report is UNMEASURED, not clean: it returns empty, and the fence's own exit
    code is what reports that it did not run.
    """
    try:
        doc = json.loads((BASE.parent.parent / "data" / "forward_clock_ratchet.json")
                         .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, str] = {}
    for row in doc.get("silent_rebases") or []:
        if isinstance(row, dict) and row.get("key"):
            out[str(row["key"])] = (
                f"forward clock silently rebased {row.get('was')} -> {row.get('now')}; "
                f"{row.get('forward_days_destroyed', '?')} pre-registered days destroyed")
    return out


def main() -> None:
    from mt5desk.engine import run_backtest

    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    state_path = SHADOW_DIR / "shadow_state.json"
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    today = datetime.now(UTC).date().isoformat()

    h1_cache = {}
    # ONE PIPELINE: grandfathered rows plus every certificate, deduped. Certificates enrol
    # here automatically -- the same day they are written -- with their clock stamped below.
    enrolled = ([(s, w, dict(WINDOWS.get(w, {})), "session_range_breakout") for s, w in SLEEVES]
                + certified_sleeves())
    # Keep variants of one symbol adjacent so their bars are loaded once, while never retaining
    # the full multi-symbol history set. The old unbounded h1_cache crossed the service's 400 MB
    # safety ceiling as soon as all certified families became genuinely enrollable.
    enrolled.sort(key=lambda row: (row[0], row[1], row[3], repr(sorted(row[2].items()))))
    cached_symbol: str | None = None
    breached = clock_breaches()
    if breached:
        slog(f"forward-clock ratchet: {len(breached)} breached key(s) will be quarantined")
    seen: set[str] = set()
    for sym, win, params, fam in enrolled:
        key = sleeve_key(sym, win, params, fam)
        if key in seen:
            continue
        seen.add(key)
        st = state.get(key, {"n": 0, "cum_r": 0.0, "max_dd_r": 0.0,
                             "first_entry": None, "last_entry": None,
                             "status": "ACTIVE"})
        if key in breached and not st.get("quarantine_reason"):
            st["quarantine_reason"] = breached[key]

        # A RATCHET BREACH IS TERMINAL, NOT ADVISORY, and it must be applied BEFORE the sleeve is
        # evaluated -- evaluating it first would add another day of evidence to a window whose
        # length is exactly what is in doubt. The clock fence has detected silent rebases since
        # 2026-08-27 and nothing acted on one; a breached sleeve kept counting toward the
        # `days >= 14` bar it had already lost the right to claim.
        #
        # BOTH AUTHORITIES ARE REVOKED, not just promotion. `order_authority` is what tells the
        # engine this row may place a real order rather than replay one, and leaving it while
        # revoking promotion would quarantine a sleeve that can still trade.
        if st.get("quarantine_reason"):
            st["status"] = "QUARANTINED_FORWARD_CLOCK_BREACH"
            st["promotion_authority"] = False
            st["order_authority"] = False
            state[key] = st
            slog(f"QUARANTINED {key}: {st['quarantine_reason']}")
            continue

        # BLAST RADIUS: ONE SLEEVE, NEVER THE BOOK (gap-wirer 2026-08-27). This loop had no
        # per-sleeve guard and `state_path.write_text` sits AFTER it, so ANY exception raised for
        # ANY single sleeve discarded the whole pass -- every row already evaluated in that run
        # included. Measured live on contabo-mt5: `per_symbol_costs` raised `KeyError: 'EURZAR'`
        # (a certified symbol absent from that box's 23-row cost map) and the entire forward book
        # stopped accruing for 5.5h across every 15-minute run, with CADJPY and EURJPY evaluated
        # and thrown away each time. The desk's readiness blocker is forward evidence, so a pass
        # that computes evidence and drops it is the most expensive silence available here.
        # THE FAILURE IS RECORDED, NEVER SWALLOWED: the row takes an explicit blocked status that
        # shadow_cycle counts into `evidence_blocked_sleeves` and the watchdog reports as a
        # defect, so an unevaluable sleeve reads as UNMEASURED and never as a clean zero (WS-005).
        # Counters are left untouched -- a failed evaluation produces no new evidence, so it must
        # not overwrite the evidence the row already holds.
        try:
            if cached_symbol != sym:
                h1_cache.clear()
                cached_symbol = sym
            if sym not in h1_cache:
                h1_cache[sym] = fetch_h1(sym)
            bars = h1_cache[sym]
            if bars is None:
                continue
            h1 = bars.df
            fam_fn = _family_fn(fam)
            if fam_fn is None:
                slog(f"{key}: constructor for family {fam} vanished; skipping this pass")
                continue
            # Rebuild whatever this family needs beyond bars, from its own stored params. A
            # family that needs nothing gets an empty dict and is unaffected.
            from mt5desk.family_inputs import resolve, strip_identity_keys

            call_params = strip_identity_keys(fam, params)
            extra, why = resolve(sym, fam, params, h1)
            if extra is None:
                # SKIP LOUDLY, NEVER RUN SHORT. `family_carry` returns [] without its swap terms,
                # which reads as "this mechanism never fires" rather than "nobody gave it what it
                # needs" -- the exact misreading that hid carry for the life of this desk.
                slog(f"{key}: runtime inputs unavailable ({why}); no signals this pass, forward "
                     f"evidence NOT accruing -- this is a wiring gap, not a null result")
                # RECORD THE ATTEMPT, OR THE ROW LIES FOREVER. This branch used to log and
                # `continue` without touching `st`, so `last_attempt_at` stayed null and whatever
                # `last_error` the row happened to carry survived every subsequent pass.
                #
                # Measured 2026-08-29T20:42: seven EURCHF.discovered rows still advertised
                # `ModuleNotFoundError: mt5desk.family_inputs` stamped 13:46:59, hours after that
                # module was shipped and verified importable on the box. The dashboard showed them
                # BLOCKED, the healer re-shipped a correct module on every run and reported HEALED,
                # and the actual cause -- this skip -- was invisible because a skip that writes
                # nothing is indistinguishable from a pass that never happened.
                #
                # A row the engine reached must say so, and must say what it found NOW.
                st["last_attempt_at"] = datetime.now(UTC).isoformat(timespec="seconds")
                st["last_error"] = f"runtime inputs unavailable: {why}"
                st["last_error_at"] = st["last_attempt_at"]
                # NEVER OVERWRITE A VERDICT. A transient input gap must not turn a KILL back into
                # an unevaluated row (it would re-enter the book) or cost a PROMOTION CANDIDATE a
                # decision the desk already made -- the rule stated at _TERMINAL_STATUSES. The
                # attempt and the reason are still recorded above, so the gap stays visible on a
                # row whose verdict stands.
                if st.get("status") not in _TERMINAL_STATUSES:
                    st["status"] = "BLOCKED_INPUTS_UNAVAILABLE"
                state[key] = st
                continue
            call_params.update(extra)
            try:
                sigs = fam_fn(h1, **call_params)
            except TypeError:
                sigs = fam_fn(h1, side=1, **call_params)
            # THE WINDOW RUNS ON THE COST BASIS IT FROZE WITH. Rebuilding costs from live universe
            # metadata every cycle meant the spread re-measure (~2x/day) changed cost_hash and
            # terminally broke every clock mid-window -- 15 clocks in one afternoon, none of them
            # about a real strategy change. A re-measured cost is a NEW identity at the NEXT window.
            try:
                costs = per_symbol_costs(meta, sym)
            except KeyError as exc:
                # The desk box can temporarily carry a narrower pulled catalogue than the
                # certificate's Fusion snapshot.  A live lookup would then turn an existing,
                # certified clock into a KeyError and forward_reconcile would keep reviving and
                # retiring it.  Reuse only its immutable frozen basis; never invent or downgrade
                # a cost because today's remote catalogue is incomplete.
                costs = frozen_costs(key)
                if costs is None:
                    # Preserve the missing-catalogue identity in the blocked-evidence record.
                    # Operations consumes this as a cost-map repair target; relabelling it as a
                    # generic RuntimeError makes the 2026-08-27 failure indistinguishable from
                    # unrelated replay faults.
                    raise KeyError(sym) from exc
                slog(f"{key}: current universe lacks {sym}; using its frozen cost basis")
            try:
                import dataclasses as _dc

                import sleeve_registry as _reg
                _ff = _reg.frozen_cost_fields(key)
                if _ff:
                    _known = {f.name for f in _dc.fields(costs)}
                    costs = _dc.replace(costs, **{k: float(v) for k, v in _ff.items()
                                                  if k in _known})
            except Exception as exc:
                slog(f"{key}: frozen-cost lookup failed ({type(exc).__name__}: {exc}); "
                     f"running on live costs this pass")
            res = run_backtest(h1, sigs, costs)
            # HISTORY IS KEPT, BUT IT IS NOT FORWARD EVIDENCE. `res.trades` runs from SHADOW_START
            # (2026-08-16); this parameterization's clock was frozen at `forward_start`.
            # Trades before that boundary were available while the cell was being SELECTED,
            # so counting them toward
            # a forward threshold is the leakage the two-stage law forbids -- measured 2026-08-26:
            # XAUUSD.asia had forward_start=Aug 25 23:25 and n=7 whose first entry was Aug 17 17:00.
            # Both sets are written: `all_trades` to the ledger tagged by phase (deleting history
            # would destroy the audit trail), `trades` -- the only set feeding
            # n/exp_r/max_dd/verdicts -- starts at the boundary. The boundary is CONVERTED,
            # not assumed: bar stamps are on the
            # broker clock (+3h at Fusion) while forward_start is true UTC.
            all_trades = [t for t in res.trades if t.entry_time >= SHADOW_START]
            _fs = st.get("forward_start")
            _boundary = None
            if _fs:
                try:
                    _boundary = (pd.Timestamp(_fs).to_pydatetime().replace(tzinfo=UTC)
                                 + timedelta(hours=float(st.get("broker_offset_h") or 0.0)))
                except (ValueError, TypeError):
                    _boundary = None
            trades = ([t for t in all_trades if t.entry_time >= _boundary]
                      if _boundary is not None else [])
            st["n_historical"] = len(all_trades) - len(trades)
            st["evidence_note"] = (
                f"{len(trades)} forward observation(s) since the clock froze; "
                f"{len(all_trades) - len(trades)} earlier observation(s) retained as "
                f"HISTORICAL and "
                f"excluded from every threshold (they predate pre-registration)")
            ledger = (SHADOW_DIR / f"ledger_{sym}_{win}.json" if fam == "session_range_breakout"
                      else SHADOW_DIR / f"ledger_{sym}_{fam}_{win}.json")
            # A trade replayed on the broker's own feed and one replayed on cached
            # or free bars are not the same evidence -- OHLC differ at the tick and
            # spreads differ materially -- so an expectancy averaged across them is
            # an average over two different games. Stamped per row so the promoter
            # can split them.
            _stamp = bars.stamp()
            ledger.write_text(json.dumps(
                [{"entry_time": str(t.entry_time), "exit_time": str(t.exit_time),
                  "side": t.side, "entry": t.entry, "exit": t.exit,
                  "r_multiple": t.r_multiple, "reason": t.reason,
                  "phase": ("forward" if (_boundary is not None and t.entry_time >= _boundary)
                            else "historical"),
                  **_stamp}
                 for t in all_trades],
                indent=2), encoding="utf-8")
            try:
                import MetaTrader5 as _mt5
                from h1_source import broker_utc_offset_hours
                st["broker_offset_h"] = broker_utc_offset_hours(_mt5)
            except Exception:
                st.setdefault("broker_offset_h", 0.0)
            # STAMP THE CLOCK BEFORE FREEZING IT. `freeze()` below passes `st["forward_start"]` into
            # the registry, and this stamp used to be written ~50 lines LATER -- so on a row's first
            # pass the registry froze `forward_start: null`, and because freeze() is idempotent by
            # design that null was permanent. The stamp is unconditional-if-absent and uses the same
            # `now` the later block would, so moving it earlier changes the value by nothing
            # and only
            # makes it visible to the freeze. The later block remains as the fallback for rows that
            # never reach the registry branch (import failure), where it is still the only stamper.
            if not st.get("forward_start"):
                st["forward_start"] = datetime.now(UTC).isoformat()
            # CANONICAL IDENTITY, frozen at the clock and verified every cycle. Params alone do not
            # identify a sleeve: the signal function's SOURCE and the COST MODEL change what it does
            # while leaving every name and number intact, and a forward series that splices two of
            # those together is not a smaller sample but a wrong one.
            try:
                import sleeve_registry as _reg
                _ident = _reg.identity(
                    family=fam, symbol=sym, direction="LONG", timeframe="H1",
                    selector=win, condition=None, params=params,
                    code=_reg.code_hash(fam_fn),
                    cost=_reg.cost_hash(costs),
                    # THE VENUE, NOT THE ROUTE. `bars.source` is how the bars reached this process
                    # (live terminal vs the parquet cache OF THAT SAME BROKER), so freezing it made
                    # every clock break on every run the Windows box was down -- terminally, and the
                    # 14-day window therefore never survived one day. `evidence_venue` names whose
                    # prints these are, so a real venue change still breaks the clock and an outage
                    # does not. See h1_source.Bars.evidence_venue.
                    data_venue=str(bars.evidence_venue))
                _drift = _reg.verify(key, _ident)
                # A COST CORRECTION IS NOT A STRATEGY CHANGE, and treating it as one kills the
                # clock permanently. Measured 2026-09-02: all twelve IDENTITY_BROKEN rows had
                # frozen `commission_per_lot: 3.5` -- the round-turn figure that sat in a per-SIDE
                # field -- and the desk's own correction to 2.25 changed every cost_hash. Twelve
                # pre-registered clocks stopped accruing toward `days >= 14` because the desk
                # fixed a known error. `rebase_cost` re-freezes the cost and NOTHING else, fires
                # only when cost_hash is the SOLE drift, and never touches forward_start.
                if _drift == ["cost_hash"]:
                    _why = _reg.rebase_cost(key, _ident, {
                        "spread_per_lot": getattr(costs, "spread_per_lot", None),
                        "commission_per_lot": getattr(costs, "commission_per_lot", None),
                        "contract_oz": getattr(costs, "contract_oz", None),
                        "quote_per_account": getattr(costs, "quote_per_account", None),
                    })
                    if _why:
                        _drift = []
                        st.pop("identity_drift", None)
                        st["cost_rebased_why"] = _why
                        slog(f"{key}: COST REBASED -- {_why}")
                if _drift:
                    _reason = f"{', '.join(_drift)} changed after the clock froze"
                    _reg.mark(key, "IDENTITY_BROKEN", _reason)
                    st["status"] = "IDENTITY_BROKEN"
                    st["identity_drift"] = _drift
                    # THE REASON BELONGS IN THE STATE TOO. It was recorded only in the registry,
                    # so `shadow_state.json` carried twelve terminal rows with no why -- a status
                    # nobody downstream could act on, and the registry disagreed with it anyway
                    # (all twelve still read LIVE there).
                    st["identity_reason"] = _reason
                    slog(f"{key}: IDENTITY BROKEN -- {_reason}; evidence preserved, clock "
                         f"stopped. Restarting requires a NEW frozen identity and a NEW window.")
                    state[key] = st
                    continue
                # THE DRIFT VERDICT MUST CLEAR ITSELF WHEN THE IDENTITY COMES BACK. Reaching this
                # line means `verify()` found NO drifted field, so a stop left by an earlier pass
                # is describing a code state that no longer exists. Six clocks sat dead this way
                # for a day (2026-08-27 15:31 -> 2026-08-28) after a stale `families.py` was
                # synced in and restored, blocking readiness rung 0 the whole time. Resumption is
                # gated on this engine being a REPLAY -- `order_authority` false means no real
                # fill was ever produced under the foreign code, and every number in `st` is
                # recomputed from bars on this pass. See sleeve_registry.reconcile.
                _resumed = _reg.reconcile(
                    key, _ident, replayed=not st.get("order_authority"))
                if _resumed:
                    st["status"] = "ACTIVE"
                    st.pop("identity_drift", None)
                    slog(f"{key}: IDENTITY RESTORED -- {_resumed}; clock resumes on its "
                         f"original forward_start ({st.get('forward_start')}), window unbroken.")
                _reg.freeze(key, _ident, forward_start=st.get("forward_start"),
                            cost_fields=vars(costs))
                st["sleeve_id"] = _ident["sleeve_id"]
            except Exception as exc:
                slog(f"{key}: registry unavailable ({type(exc).__name__}: {exc})")
            # EVERY EVALUATION STAMPS ITSELF. The idle-clock fence judges freshness by
            # `last_attempt_at`, and this engine was evaluating rows every 15 minutes without
            # updating it -- so the four pre-params rows kept a 13-hour-old stamp from the previous
            # engine and were flagged IDLE while demonstrably accruing (XAUUSD.asia took its first
            # forward trade under the stale stamp). An organ that does the work but does not sign it
            # is indistinguishable from one that stopped.
            # A BLOCK MUST CLEAR ITSELF WHEN THE CAUSE IS REPAIRED. Reaching this line means the
            # sleeve evaluated end to end, so a `BLOCKED_SLEEVE_ERROR` left by an earlier pass is
            # now stale -- and a status that only ever goes one way would leave
            # `evidence_blocked_sleeves` permanently non-zero, which is the always-red detector
            # this desk retires on sight (L1.37). MEASURED 2026-08-27: EURZAR and USDZAR blocked
            # at 21:45:10 on a 23-row cost map, evaluated successfully at 21:47:07 on the
            # repaired 251-row map, and still reported blocked. The error text is dropped WITH
            # the status -- keeping it would leave the row reading as failing while it accrues --
            # and `last_error_seen_at` preserves that it once did, so the history is not erased.
            if st.get("status") == "BLOCKED_SLEEVE_ERROR":
                st["status"] = "ACTIVE"
                st["last_error_seen_at"] = st.pop("last_error_at", None)
                st["last_error_cleared"] = st.pop("last_error", None)
                slog(f"{key}: block CLEARED -- evaluated end to end; previous error was "
                     f"{st['last_error_cleared']}")
            st["last_attempt_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            st["bar_source"] = bars.source
            st["evidence_venue"] = bars.evidence_venue
            st["bar_source_stale"] = bars.stale
            st["promotion_authority"] = bars.promotion_authority
            st["order_authority"] = False
            st["gate_admission"] = "ORIGINAL_UNIVERSAL_10_PASS"
            if trades:
                rs = [t.r_multiple for t in trades]
                cum = [sum(rs[:i + 1]) for i in range(len(rs))]
                max_dd = min(cum[i] - max(cum[:i + 1]) for i in range(len(cum)))
                st.update({
                    "n": len(trades), "cum_r": float(sum(rs)),
                    "exp_r": float(sum(rs) / len(rs)),
                    "max_dd_r": float(max_dd),
                    "first_entry": str(trades[0].entry_time),
                    "last_entry": str(trades[-1].entry_time),
                })
            else:
                # ZERO FORWARD OBSERVATIONS IS A MEASUREMENT, NOT A REASON TO KEEP THE OLD NUMBER.
                # This branch used to `setdefault` and leave n/cum_r/exp_r/max_dd untouched, so a
                # clock whose forward set became empty -- exactly what happens the moment the
                # boundary is corrected -- kept displaying the CONTAMINATED pre-registration counts
                # and would have carried them into a promotion decision. Counters are reset to the
                # honest zero and the historical arm is reported separately (L1.28a: unmeasured is
                # never a verdict, and neither is inherited).
                st.update({"n": 0, "cum_r": 0.0, "exp_r": 0.0, "max_dd_r": 0.0,
                           "first_entry": None, "last_entry": None})
            # THE CLOCK STARTS AT PRE-REGISTRATION, NOT AT THE FIRST TRADE EVER TAKEN. This read
            # `first_entry` -- trades[0].entry_time -- so a sleeve that had been trading for 8 days
            # before its hypothesis was frozen arrived at the gate already 8/14 of the way through
            # its "forward" window, on evidence gathered while it was still being SELECTED. That is
            # the precise leakage the two-stage law exists to stop (LAWS L1.28a; RESEARCH §6a: the
            # gauntlet screens, only pre-registered forward evidence promotes). `forward_start` is
            # stamped once, the first time a row is seen, and never moved.
            now = datetime.now(UTC)
            if not st.get("forward_start"):
                st["forward_start"] = now.isoformat()
            days_active = (now - pd.Timestamp(st["forward_start"]).to_pydatetime()
                           .replace(tzinfo=UTC)).days
            st["days_active"] = days_active
            # SUFFICIENT EVIDENCE = the flat count OR a significant forward t-stat at a floor of
            # trades. Whichever arrives first; both are honest, one is merely faster when the edge
            # is large. Quality bars (exp_r, maxDD) still apply to every promotion below.
            t_stat = 0.0
            if len(trades) >= 2:
                _rs = [t.r_multiple for t in trades]
                _mean = sum(_rs) / len(_rs)
                _var = sum((x - _mean) ** 2 for x in _rs) / (len(_rs) - 1)
                if _var > 0:
                    t_stat = _mean / ((_var / len(_rs)) ** 0.5)
            st["forward_t"] = round(t_stat, 3)
            enough = (st["n"] >= VERDICT_MIN_TRADES
                      or (st["n"] >= SEQ_MIN_TRADES and t_stat >= SEQ_MIN_T))
            # AND, never OR: gate_spec.yaml has always said `n >= 50, days >= 14` together, but this
            # line said `or`, so a sleeve holding ONE trade would take a verdict on day 14 -- and
            # `EURJPY.asia.NORMAL_DAY` (n=1) and three MACRO_FAV rows (n=1) were on course to do
            # exactly that. A one-trade promotion is not a fast promotion, it is a coin flip wearing
            # a certificate.
            if st["status"] == "ACTIVE" and enough and days_active >= VERDICT_MIN_DAYS:
                if st["exp_r"] > PROMOTE_MIN_EXP and st["max_dd_r"] > PROMOTE_MIN_DD:
                    st["status"] = "PROMOTION CANDIDATE"
                    slog(f"{key}: VERDICT PROMOTE n={st['n']} exp={st['exp_r']:.3f}R "
                         f"maxDD={st['max_dd_r']:.1f}R")
                else:
                    st["status"] = "KILL"
                    slog(f"{key}: VERDICT KILL n={st['n']} exp={st['exp_r']:.3f}R "
                         f"maxDD={st['max_dd_r']:.1f}R")
            state[key] = st
            slog(f"{key}: shadow n={st['n']} cumR={st['cum_r']:+.2f} "
                 f"exp={st['exp_r']:+.3f}R maxDD={st['max_dd_r']:.1f}R "
                 f"days={days_active} [{st['status']}]")
        except Exception as exc:  # deliberate: isolate ONE sleeve, never the book
            detail = f"{type(exc).__name__}: {exc}"
            st["last_error"] = detail
            st["last_error_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            if not _is_terminal(st.get("status")):
                st["status"] = "BLOCKED_SLEEVE_ERROR"
            state[key] = st
            slog(f"{key}: SLEEVE BLOCKED -- {detail}; this row is not evaluated this pass and "
                 f"every other sleeve continues")
            slog(traceback.format_exc())
    state["last_run"] = today
    state["configured_sleeves"] = len(enrolled)
    state["gate_blocked_sleeves"] = 0
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    slog(f"shadow state saved ({len(enrolled)} sleeves, "
         f"{len(enrolled) - len(SLEEVES)} certificate-enrolled)")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        slog("shadow error:", traceback.format_exc())
