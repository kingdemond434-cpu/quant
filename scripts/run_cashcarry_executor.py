"""RETIRED, GENUINELY VENUE-SPECIFIC (2026-08-23): no MT5 translation exists. This trade needs a
dual spot+perpetual-futures listing on the SAME instrument to arb the convergence; Fusion's MT5
catalogue is CFDs, with no second, independently-priced futures leg to hedge against. Kept in the
repo per standing instruction, but never wire this into any live schedule again.

Cash-and-carry EXECUTOR -- the delta-neutral funding-harvest book, executed on the testnets.

Long spot (spot testnet) + short perp (futures testnet) on the top POSITIVE-funding perps that trade
on BOTH venues. Persistent loop with a BANDED rebalance (carry compounds -> hold, don't churn): it
only opens new carries and closes names that leave the positive-funding set, so turnover (and fees)
stay minimal. Tracks a real position state + marks the book, writes a heartbeat + kill-switch. This
is now the PROFIT-LEAD book; the perp L/S book drops to shadow. PAPER (testnet) -- it builds the
forward track record the edge-gate sizes leverage on. dry-run DEFAULT; --live to send paper orders.

    python scripts/run_cashcarry_executor.py --live --top 5 --capital 2000 --interval 600
"""

from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import os
import random
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.data.crypto_source import current_funding
from libs.execution import binance_spot_testnet as spot
from libs.execution import binance_testnet as fut
from libs.execution import excitation, execution_tape
from libs.execution.carry_accounting import (
    attribute_non_funding,
    carry_bleed_report,
    dedup_basis,
    derive_spot_realized,
    read_income,
    reconcile_futures_leg,
)
from libs.ops.fresh import read_fresh  # L1.44: decision-path reads carry freshness contracts
from libs.ops.lawful import guard as _law_guard  # L1.42: no act exempt
from libs.ops.production_contract import (
    deterministic_hot_path,
    preflight_contract,
    strategy_manifest,
)
from libs.risk import capital_events, risk_controls

_STATE = Path("data/cashcarry_positions.json")
_TRADES = Path("data/cashcarry_trades.json")     # real open/close log -> winrate + trade history
_LEV_TGT = Path("data/leverage_target.json")     # dynamic-leverage sizing (honoured when validated)
_CONFIG = Path("data/cashcarry_config.json")     # LIVE-tunable params (top/hold_top/capital)
_WEB = Path("web/cashcarry_live.json")
_HB = Path("data/cashcarry_exec_heartbeat")
_KILL = Path("data/CASHCARRY_KILL")
# PERMANENTLY RETIRED (principal 2026-08-19: "Kill cash carry executor I say we don't ever
# need it anymore"; the desk is MT5-only from that date, per CLAUDE.md). This is stronger than
# _KILL.exists(): that path is a REVERSIBLE pause that auto-resumes trading the moment the
# file clears (by design, for transient risk events). This flag is a permanent, code-level
# shutdown -- the executor closes every open carry (idempotent, retried while any leg remains)
# and then idles forever, exactly the same well-tested close+idle path _KILL already used
# (never a hard process exit -- that caused a 14k-respawn storm on 2026-07-13). Flipping this
# back to False is a deliberate, reviewed, principal-authorised decision, never a default.
_PERMANENTLY_RETIRED = True
_ERR = Path("data/cashcarry_error.log")          # visible cycle-error log (not swallowed to null)
# RESTORED 2026-08-13. Added by 0d31469 -- an ANCESTOR of HEAD -- and dropped by a later merge
# together with the two functions below, so the executor lost its FAIL-CLOSED PREFLIGHT and its
# frozen replay path while every test naming them stayed in the tree. Nothing broke loudly: the
# names simply stopped existing, which is how a safety gate leaves the money path in silence.
_PREFLIGHT = Path("data/preflight_checks.json")
_HOT_REPLAY = Path("data/hot_path_replay.json")
_VENUE_CAPABILITIES = Path("data/venue_capabilities.json")
_MANIFEST = strategy_manifest(
    {
        "strategy_id": "cashcarry",
        "signal": "positive-funding-net-of-realised-round-trip-cost",
        "allocator": "free-capital-funding-weighted-concentration-capped",
        "risk_policy": "risk_controls.evaluate-ruin-boundary-v1",
        "execution_policy": "paired-maker-first-verified-fills-v1",
    },
    version="1",
)
_LAST_ARCHIVE = Path("data/.last_metrics_archive")  # once-per-day data-flywheel marker
_HB_TICK = 60                                    # heartbeat cadence (decoupled from rebalance work)
_MAKER = True                                     # maker-first execution (set via --no-maker)
_RSP_TOL = 5.0                                    # $ drift before realized_spot_pnl self-heals
_FLAT_EPS = 1e-9                                  # |qty| at or below this counts as flat
_DEPTH_MULT = 5.0                                # book depth within 1% of touch must cover an open
# ORPHAN-COVER BOUNDS (gap #37, panel consensus 8+/12 on the 2026-07-19 audit): the
# orphan cover is a live-ammo market-order path that previously fired on FIRST sight of
# any untracked position, unbounded. A transient REST desync or partial-fill lag then
# market-covers into a thin book, and repeated covers during a venue outage could
# themselves breach the ruin constraint. Two bounds, both safe-direction only:
_ORPHAN_CONFIRM = 2        # reconcile passes an orphan must PERSIST before live ammo
_ORPHAN_MAX_USD = 1500.0   # max notional force-covered per symbol per pass
# CASCADE GUARD (gap #37): the confirm-window and per-pass cap bound a SINGLE cover, but
# `seen.pop()` reset the symbol immediately, so a persistent desync (exactly what a venue
# outage looks like) could re-fire live ammo every pass with no rate limit. A cooldown
# bounds repeats per symbol; the hourly circuit stops the whole path when MANY symbols go
# orphan at once -- that pattern means "the venue is sick", not "we have N real orphans".
_ORPHAN_COOLDOWN_S = 1800.0   # per-symbol quiet period after a cover
_ORPHAN_MAX_PER_HOUR = 3      # covers/hour across all symbols before the path halts
                                                 # this many times, on BOTH legs, or the name is
                                                 # skipped (2026-07-13 thin-book incident)


def _daily_data_tasks() -> None:
    """Keep the DATA FLYWHEEL turning once per UTC day off the always-on cash-carry loop.

    Archives OI/LS/taker metrics, market breadth, and Deribit surface -- these grow the 40-day
    forward clocks that gate the derivative alpha column. Spawns the heavy research chain detached
    so a slow research run can never block trading. Process-isolated so any data hiccup is safe."""
    today = datetime.now(tz=UTC).date().isoformat()
    if _LAST_ARCHIVE.exists() and _LAST_ARCHIVE.read_text("utf-8").strip() == today:
        return
    root = Path(__file__).resolve().parent.parent
    for script in ("scripts/collect_binance_metrics.py", "scripts/collect_market_breadth.py",
                   "scripts/collect_deribit_surface.py", "scripts/classify_regime.py",
                   "scripts/run_regime_engine.py"):
        try:
            subprocess.run([sys.executable, script], cwd=root, timeout=600,
                           capture_output=True, text=True, check=False)
        except Exception as e:
            print(f"[daily-task] {script}: {e!r}"[:140])
    try:
        subprocess.Popen([sys.executable, "scripts/run_daily_research.py"], cwd=root,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[daily-task] run_daily_research spawn: {e!r}"[:140])
    _LAST_ARCHIVE.write_text(today, "utf-8")


def _book_snapshot() -> dict[str, Any]:
    """Current book (state positions + live prices), NO orders -- for frequent marking."""
    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    return {"state": state, "pos": state.get("positions", {}), "actions": [], "cands": [],
            "spot_px": spot.prices(), "fut_px": fut.mark_prices()}


def _round(qty: float, step: float, prec: int) -> float:
    return round(round(qty / step) * step, prec) if step > 0 else round(qty, prec)


def _log_trade(rec: dict[str, Any]) -> None:
    """Append a real open/close event -> cashcarry_trades.json (source of winrate + history).

    The rolling file stays capped at 500 (every existing consumer depends on its shape), but the
    same record ALSO goes to the append-only execution tape -- the cap was destroying ~27 fills/day
    of own-fill history, which is both the data moat and the evidence Gate 0's ">=4 weeks of live
    fills" is measured against. The tape append is exception-safe and never blocks the executor.
    """
    try:
        log = json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []
    except (OSError, json.JSONDecodeError):
        log = []
    log.append(rec)
    _TRADES.parent.mkdir(parents=True, exist_ok=True)
    _TRADES.write_text(json.dumps(log[-500:], indent=2, default=str), "utf-8")
    execution_tape.append(rec)


def _held_hours(opened: object) -> float:
    try:
        dt = datetime.fromisoformat(str(opened))
        return round((datetime.now(tz=UTC) - dt).total_seconds() / 3600, 2)
    except (ValueError, TypeError):
        return 0.0


def _check_dynamic_leverage_gate() -> tuple[bool, dict[str, Any]]:
    """
    Check if the dynamic leverage optimizer may drive sizing.

    Re-enable gate (GAP #14):
    1. >=30 uncontaminated live days (clean_since in leverage_target.json)
    2. Plausibility rail fired (plausibility_rail_fired: true, Sharpe <= 4.0)
    3. Principal sign-off (stage S1+ proven via stage_state.json)
    4. Optimizer active with confidence > 0

    Returns (gate_passed, details_dict) where details contains the leverage
    recommendation if gate passed, or reason for failure.
    """
    from libs.ops.fresh import read_fresh

    _LEV_TGT = Path("data/leverage_target.json")
    _STAGE = Path("data/stage_state.json")

    details: dict[str, Any] = {"gate": "dynamic_leverage_re_enable", "checks": {}}

    # 1. Read leverage target
    try:
        if not _LEV_TGT.exists():
            details["checks"]["leverage_target_exists"] = False
            details["reason"] = "leverage_target.json missing"
            return False, details

        with open(_LEV_TGT) as f:
            tgt = json.load(f)
        details["checks"]["leverage_target_exists"] = True
        details["leverage_target"] = tgt
    except Exception as e:
        details["checks"]["leverage_target_exists"] = False
        details["reason"] = f"leverage_target.json unreadable: {e}"
        return False, details

    # 2. Check optimizer active and confidence > 0
    active = bool(tgt.get("active", False))
    confidence = float(tgt.get("confidence", 0.0))
    details["checks"]["optimizer_active"] = active
    details["checks"]["confidence_gt_zero"] = confidence > 0.0
    if not active or confidence <= 0.0:
        details["reason"] = "optimizer not active or confidence zero"
        return False, details

    # 3. Plausibility rail fired (Sharpe <= 4.0)
    plausibility = bool(tgt.get("plausibility_rail_fired", False))
    details["checks"]["plausibility_rail_fired"] = plausibility
    if not plausibility:
        details["reason"] = "plausibility rail not fired (Sharpe implausible)"
        return False, details

    # 4. Clean days >= 30
    clean_since_str = tgt.get("clean_since")
    if not clean_since_str:
        details["checks"]["clean_since_30d"] = False
        details["reason"] = "clean_since missing"
        return False, details
    try:
        clean_since = datetime.fromisoformat(clean_since_str.replace("Z", "+00:00"))
        if clean_since.tzinfo is None:
            clean_since = clean_since.replace(tzinfo=UTC)
        days_clean = (datetime.now(UTC) - clean_since).total_seconds() / 86400.0
        details["checks"]["clean_since_30d"] = days_clean >= 30.0
        details["days_clean"] = round(days_clean, 1)
        if days_clean < 30.0:
            details["reason"] = f"only {days_clean:.1f} clean days (< 30 required)"
            return False, details
    except Exception as e:
        details["checks"]["clean_since_30d"] = False
        details["reason"] = f"clean_since parse error: {e}"
        return False, details

    # 5. Principal sign-off: stage S1+ (Gate 0 passed)
    try:
        fr = read_fresh(_STAGE, max_age_h=1.0, kind="state",
                        guardian="data/live_guard.json",
                        caller="run_cashcarry_executor._check_dynamic_leverage_gate")
        stage = str((fr.data or {}).get("stage", "S0")).upper()
        principal_ok = stage in ("S1", "S2")
        details["checks"]["principal_signoff_s1_plus"] = principal_ok
        details["stage"] = stage
        if not principal_ok:
            details["reason"] = f"stage {stage} not S1+ (Gate 0 not passed)"
            return False, details
    except Exception as e:
        details["checks"]["principal_signoff_s1_plus"] = False
        details["reason"] = f"stage check failed: {e}"
        return False, details

    # All checks passed - return the leverage recommendation
    leverage = float(tgt.get("leverage", 0.25))
    gated_leverage = float(tgt.get("gated_leverage", leverage))
    notional_per_leg = float(tgt.get("notional_per_leg", 1250.0))
    growth_optimal = float(tgt.get("growth_optimal", 0.0))
    ruin_cap = float(tgt.get("ruin_cap", 6.3))

    details["recommendation"] = {
        "leverage": leverage,
        "gated_leverage": gated_leverage,
        "notional_per_leg": notional_per_leg,
        "growth_optimal": growth_optimal,
        "ruin_cap": ruin_cap,
        "status": tgt.get("status", "DYNAMIC"),
    }
    details["gate_passed"] = True
    return True, details


# Log for observability
_DYN_LEV_LOG: list[dict[str, Any]] = []


def _dynamic_capital(default: float) -> float:
    """
    Deployed notional from the dynamic-leverage optimizer -- but ONLY once the
    re-enable gate passes (GAP #14).

    Gate: >=30 uncontaminated live days + plausibility rail + principal sign-off
    + optimizer active with confidence > 0.

    Until gate passes, returns operator capital (compounded).
    When gate passes, returns optimizer's notional scaled by compounded capital,
    clamped to [0.5x, 4.0x] operator capital.
    """
    # Check the re-enable gate
    gate_passed, details = _check_dynamic_leverage_gate()

    if not gate_passed:
        # Gate not passed: use operator capital (compounded), log the reason
        _DYN_LEV_LOG.append({
            "ts": datetime.now(UTC).isoformat(),
            "gate_passed": False,
            "reason": details.get("reason", "unknown"),
            "details": details,
        })
        # Keep last 100 log entries
        if len(_DYN_LEV_LOG) > 100:
            _DYN_LEV_LOG.pop(0)
        return _compounded_capital(default)

    # Gate passed: use optimizer's recommendation
    rec = details["recommendation"]
    gated_leverage = rec["gated_leverage"]

    # Compute deployed notional from optimizer's leverage * compounded capital
    base_capital = default
    compounded = _compounded_capital(base_capital)

    # Optimizer's leverage applied to compounded capital
    optimizer_notional = compounded * gated_leverage

    # Clamp to [0.5x, 4.0x] operator capital (same as _compounded_capital)
    min_notional = base_capital * _COMPOUND_MIN_FACTOR
    max_notional = base_capital * _COMPOUND_MAX_FACTOR
    final_notional = max(min_notional, min(max_notional, optimizer_notional))

    # Log the decision
    _DYN_LEV_LOG.append({
        "ts": datetime.now(UTC).isoformat(),
        "gate_passed": True,
        "operator_capital": base_capital,
        "compounded_capital": compounded,
        "optimizer_leverage": gated_leverage,
        "final_notional": final_notional,
        "clamp": {"min": min_notional, "max": max_notional},
    })
    if len(_DYN_LEV_LOG) > 100:
        _DYN_LEV_LOG.pop(0)

    return float(final_notional)


# --- COMPOUNDING RE-ANCHOR (principal 2026-07-23; Gate-0 lever, built early on purpose) ------
# DEFECT IT FIXES: the executor deployed a FROZEN notional, so realised gains never enlarged the
# base. That is ARITHMETIC growth -- the same dollar profit on a growing account is a shrinking
# percentage, so measured CAGR decays toward zero. For a desk whose supreme objective is max
# E[log(wealth)], a frozen base disconnects the objective's own transmission mechanism.
#
# WHY THIS IS SAFE (each hazard named and closed):
#  * The QUARANTINED OPTIMIZER is never consulted (gap #14 stands). This reads only REALISED,
#    hash-chain-attested PnL -- never a confidence score. Incident #2 was optimizer confidence
#    sizing the book to $40k; that path stays dead.
#  * NEVER raw equity. Testnet equity marks ~$10.8k because of faucet bags, so anchoring to it
#    would balloon the book. Only realized_spot_pnl from the NAV attestation is used.
#  * FAIL-SAFE INERT: if the stage machine cannot PROVE S1+ (live), the operator capital is
#    returned unchanged. Missing/unreadable/S0 all read as NOT live. So this is fully built and
#    testable today and begins compounding on day 1 of Gate 0 -- ready since the beginning.
#  * CLAMPED BOTH WAYS: never below 0.5x nor above 4.0x authorised capital, so a corrupt
#    realised figure cannot run the book away in either direction.
_COMPOUND_FRACTION = 1.0      # redeploy 100% of realised gains into the base (log-optimal)
_COMPOUND_MAX_FACTOR = 4.0    # never exceed 4x authorised capital without a new authorisation
_COMPOUND_MIN_FACTOR = 0.5    # de-risk floor: losses shrink the base, but only to half
_STAGE = Path("data/stage_state.json")
_NAV = Path("data/nav_attestation.jsonl")


def _is_live() -> bool:
    """True ONLY when the stage machine proves S1+ (Gate 0 passed). Any error, missing file or
    S0/paper reads as NOT live, so compounding stays off. Fail-safe by construction.

    L1.44 state-kind contract: stage_state.json is valid-until-changed, so its own age proves
    nothing -- the read is trustworthy iff its GUARDIAN (run_live_guard, the tripwire/demotion
    evaluator) is alive. The decision below is unchanged either way (fail-safe already); the
    contract makes a dead guardian visible as a consumed-state event instead of silence."""
    try:
        fr = read_fresh(_STAGE, max_age_h=1.0, kind="state",
                        guardian="data/live_guard.json",
                        caller="run_cashcarry_executor._is_live")
        return str((fr.data or {}).get("stage", "S0")).upper() in ("S1", "S2")
    except Exception:
        return False


def _realised_pnl() -> float:
    """Cumulative REALISED PnL from the hash-chained NAV attestation (never marks or equity)."""
    try:
        lines = [ln for ln in _NAV.read_text("utf-8").splitlines() if ln.strip()]
        return float(json.loads(lines[-1]).get("realized_spot_pnl", 0.0))
    except Exception:
        return 0.0


#: Where the live epoch baseline is recorded. See _live_epoch_pnl.
_LIVE_EPOCH = Path("data/live_compound_epoch.json")


def _live_epoch_pnl() -> float:
    """Realised PnL already on the books when this desk FIRST went live.

    R0235: the NAV chain does not distinguish testnet from live, and at the S0->S1 flip it carried
    2,930.43 of TESTNET profit. Compounding a real deposit by that figure sized a 200 USD deposit
    as 800 -- 4x, on money that does not exist at the venue -- and Gate 0's capital_fraction cap is
    evaluated on the pre-multiplied number, so it never saw the size actually traded.

    The first live read stamps the then-current realised figure as an EPOCH, and all later growth
    counts only PnL ABOVE it. Live compounding therefore begins at exactly 1.0x, which is the
    truth: no live PnL has been earned yet. The testnet record stays intact and the hash-chained
    NAV file is never rewritten.
    """
    try:
        if _LIVE_EPOCH.exists():
            return float(json.loads(_LIVE_EPOCH.read_text("utf-8")).get("epoch_realised", 0.0))
    except Exception:
        return _realised_pnl()        # unreadable epoch -> subtract everything => 1.0x, fail-safe
    stamp = _realised_pnl()
    # best-effort persist: if it fails we still RETURN the stamp, so this tick computes 1.0x and
    # the next tick re-stamps. Failing to write can never widen the size.
    with contextlib.suppress(Exception):
        _LIVE_EPOCH.write_text(json.dumps(
            {"epoch_realised": stamp, "stamped_at": datetime.now(tz=UTC).isoformat(),
             "why": "R0235: realised PnL on the books at the first live read. Growth counts only "
                    "PnL above this, so live compounding starts at 1.0x instead of inheriting "
                    "testnet profit as live size."}), "utf-8")
    return stamp


def _compounded_capital(default: float) -> float:
    """Operator capital grown by REALISED PnL earned LIVE, hard-clamped, inert until live."""
    if not _is_live():
        return default                                   # pre-Gate-0: frozen base, unchanged
    live_pnl = _realised_pnl() - _live_epoch_pnl()        # R0235: exclude pre-live (testnet) PnL
    grown = default + live_pnl * _COMPOUND_FRACTION
    lo, hi = default * _COMPOUND_MIN_FACTOR, default * _COMPOUND_MAX_FACTOR
    return float(min(max(grown, lo), hi))


def _alloc(cands: list[tuple[str, float]], capital: float,
           *, cap_frac: float = 0.35) -> dict[str, float]:
    """Per-name notional weighted by funding rate (harvest more where it pays), capped so no single
    carry dominates (capacity / concentration guard). The cap is HARD: when it cannot be met
    (n * cap_frac < 1, i.e. fewer than 3 names) the remainder stays in cash rather than piling
    into one name -- relaxing it is how 2026-07-13 put $4.3k of a $4.5k book into a single
    micro-cap (NOMUSDT) and fired the dead-man rail."""
    n = len(cands)
    if n == 0:
        return {}
    fs = [max(0.0, f) for _, f in cands]
    tot = sum(fs)
    w = [x / tot for x in fs] if tot > 0 else [1.0 / n] * n
    # WATER-FILL: cap each weight at cap_frac and redistribute the excess to the uncapped names,
    # iterating to a fixed point. A plain min()+renormalise does NOT hold the cap (excess leaks
    # back into the max name); this does. When no under-cap name can absorb the excess, the
    # excess is simply NOT deployed (never scaled back up -- see docstring).
    for _ in range(n):
        over = [i for i, x in enumerate(w) if x > cap_frac + 1e-12]
        if not over:
            break
        excess = sum(w[i] - cap_frac for i in over)
        for i in over:
            w[i] = cap_frac
        pool = sum(w[i] for i in range(n) if w[i] < cap_frac - 1e-12)
        if pool <= 0:
            break                                        # nowhere to redistribute -> stays in cash
        for i in range(n):
            if w[i] < cap_frac - 1e-12:
                w[i] += excess * w[i] / pool
    s = sum(w)
    if s > 1.0 + 1e-9:                                   # defensive: weights may only scale DOWN
        w = [x / s for x in w]
    return {cands[i][0]: capital * w[i] for i in range(n)}


def _topup_plan(pos: dict[str, dict[str, Any]], capital: float, *, cap_frac: float = 0.35,
                min_frac: float = 0.02, min_usd: float = 20.0) -> dict[str, float]:
    """Extra notional to bring each HELD carry UP toward its funding-weighted share of the FULL
    capital -- never DOWN (closes are the target-set's job; this only fills idle authorized
    capital that held carries would otherwise leave frozen from a low-free-capital open window).

    Pure (no venue calls) so the risk-path sizing is unit-testable. Invariants that keep this in
    the SAFE direction only (operator-directed 2026-07-19, gap #32):
      * aggregate adds never exceed the free headroom (capital - deployed) -> the book can never
        lever past the operator's --capital (the quarantined leverage optimizer stays ignored);
      * each name is held under cap_frac*capital -> the 2026-07-13 single-name concentration rail;
      * only MATERIAL shortfalls (>= max(min_frac*capital, min_usd)) top up -> a book already near
        target does not churn on rounding noise.
    """
    if not pos:
        return {}
    funded = [(sym, max(float(p.get("funding", 0.0)), 0.0)) for sym, p in pos.items()]
    tgt = _alloc(funded, capital, cap_frac=cap_frac)
    deployed = sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())
    room = max(0.0, capital - deployed)
    floor = max(min_frac * capital, min_usd)
    plan: dict[str, float] = {}
    for sym in sorted(pos, key=lambda k: max(float(pos[k].get("funding", 0.0)), 0.0), reverse=True):
        if room <= 0.0:
            break
        cur = float(pos[sym]["spot_qty"]) * float(pos[sym]["spot_cost"])
        add = min(min(tgt.get(sym, 0.0), cap_frac * capital) - cur, room)
        if add < floor:
            continue
        plan[sym] = add
        room -= add
    return plan


# --- CHURN GUARD (gap #42, 2026-07-22) -----------------------------------------------------
# Trade audit over 250 closes: carries held <8h (38% of all trades) LOSE money as a class
# (<2h -5.0 bps, 2-8h -4.1 bps) while 8-24h earns +6.5 and >24h earns +16.9. 42% of closes
# re-opened the SAME symbol within 24h -- a provably wasted round-trip. Realized drag -8.1%/yr.
# Cause is funding-sign flicker, not bad entries (funding at open is identical fast vs slow).
# ECONOMICS: adverse funding costs ~1 bp per 8h; a round-trip costs ~4.5 bps (measured by
# run_cost_model.py). So holding up to 24h risks <=3 bps to save 4.5 -- strictly dominant.
# Beyond ~32h the accumulated adverse funding would exceed the saved round-trip, so 24h is the
# profit-maximising floor, not an arbitrary constant.
_MIN_HOLD_H = 24.0        # rotation-driven closes blocked below this age
_FUNDING_PANIC = -0.0005  # per-8h rate: worse than this, holding costs more than the round-trip


def _churn_guard(held_h: float, funding: float, rail_forced: bool) -> bool:
    """True => HOLD the carry (block a rotation-driven close).

    Rails ALWAYS win (basis-stop / ADL / cooldown / risk-flatten / reconcile close instantly);
    strongly-negative funding escapes the floor; otherwise a carry younger than the minimum
    hold is kept so it can earn back the round-trip it already paid."""
    if rail_forced:
        return False
    if funding <= _FUNDING_PANIC:
        return False
    return held_h < _MIN_HOLD_H


# --- ENTRY GATE (gap #43, 2026-07-22) ------------------------------------------------------
# Trade audit over 250 closes, bucketed by funding rate AT OPEN:
#   0.000100 (Binance BASELINE, no real premium): n=50  net -$176.24  (-92.7 bps)  <-- disaster
#   0.000100-0.000144                           : n=50  net  +$14.71  (+12.8 bps)
#   0.000100-0.000144                           : n=50  net  +$60.87  (+42.7 bps)
#   0.000144-0.000219                           : n=50  net  -$22.43   (-7.5 bps)
#   0.000219-0.001517                           : n=50  net +$179.31  (+45.9 bps)
# `_ranked()` accepted ANY funding > 0, so the desk opened carries on symbols sitting at the
# exchange DEFAULT rate -- i.e. names with no funding premium whatsoever -- and paid a full
# round-trip for them. Those 50 trades ate ~80% of the desk's gross profit.
#
# _MIN_FUNDING DELETED 2026-07-31 (R0057). The absolute per-8h floor (0.00015, derived from the
# desk-MEDIAN round-trip when the cost gate still used the median default) became redundant the
# day the cost gate went per-symbol with a p90 fail-closed default: unmeasured names now need
# funding > 39.5/3e4 = 0.00132 anyway, and thin proven losers are on the bleed denylist. The
# ARITHMETIC CORRECTED 2026-08-13 (R0442) -- this line read 0.000132, ten times too small, and the
# error inverted what the record CLAIMED about the change. 39.5/3e4 = 0.0013167: 13.2 bps per 8h,
# ~144%/yr funding. At 0.000132 the per-symbol bar would sit BELOW the 0.00015 floor being
# deleted, i.e. the deletion would read as a LOOSENING that was waved through; the true bar is
# 8.78x ABOVE it. The conclusion survives and is strengthened -- the per-symbol check is far
# stricter for unmeasured names than the floor it replaced -- but a future reader arriving at the
# wrong number could reinstate a floor, or loosen this gate, on a premise that was never true.
# floor's only remaining effect, measured 2026-07-30: vetoing the 4 net-positive MAJORS (tight
# measured books whose funding capture beats their own round-trip below 0.00015) -- 245/245
# candidates rejected with the floor on. Protection lives in the per-symbol check below.
# FAIL CLOSED (2026-07-27). Default was 4.5 = the desk MEDIAN, which sits at only the 43rd
# percentile of measured round-trips (median 5.7, p75 21.3, p90 39.5, max 130.5 across 30
# symbols). 'Unmeasured' is NOT a random subset: a symbol is missing from the cost model
# BECAUSE it is too illiquid to measure -- i.e. it is the expensive tail. Assigning it the
# median was a fail-open on exactly the worst books (this file already records NOM -149bps,
# KNC -211bps). p90 makes the unmeasured case pessimistic: a symbol must prove it is cheap
# (by being measured) before it can clear the bar. Raising it can only REFUSE NEW OPENS --
# _entry_gate is never applied to the hold/target set, so this cannot force-close anything.
_DEFAULT_RT_BPS = 39.5          # p90 of measured pair round-trip; pessimistic when unmeasured
_COST_MODEL = Path("data/cost_model.json")
_FORENSICS = Path("web/trade_forensics.json")
_PRINT_IMPACT = Path("data/print_impact.json")   # L1.11b third basis (R0483): third-party prints
# STRUCTURAL-BLEED DENYLIST (2026-07-23). run_trade_forensics.py already PROVED which
# names lose money as a class (NOMUSDT -149bps/5 trades, PEOPLEUSDT -73/5, BNBUSDT
# -67/11, GTCUSDT -29/10) but nothing consumed its output, so the desk kept re-opening
# them. The funding+cost gate does not catch these: their funding clears the floor and
# their modelled cost looks fine -- the loss is realised execution, visible only in the
# closed-trade record. Evidence-driven, self-updating, and strictly RESTRICTIVE:
# NEW OPENS ONLY, so it can never force-close a held carry (that would be churn).
_BLEED_BPS = -20.0        # realised net bps at which a symbol is structurally bleeding
_BLEED_MIN_N = 5          # minimum closed trades before the verdict is trusted


_REENTRY = Path("data/execution_reentry.json")


def _reentry_conditions() -> dict[str, Any]:
    """Recorded L1.16a re-entry conditions for execution-denylisted symbols.

    An unreadable or absent file returns {} -- which DENIES every probe, keeping the denylist
    exactly as restrictive as it was before re-entry existed. This is the one direction the
    degrade may take: a corrupt file must never become a licence to re-open proven losers.
    """
    try:
        data = json.loads(_REENTRY.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


#: LAST-GOOD BLEED WINDOW (R0158). Written through on every non-empty `worst_symbols` read,
#: consulted only when the live artifact cannot be parsed. Runtime state, not configuration:
#: it is derived entirely from forensics and is rebuilt by the next good read.
_BLEED_CACHE = Path("data/structural_bleed_last_good.json")


def _remember_bleed_window(rows: list[Any]) -> None:
    """Persist a NON-EMPTY bleed window so an unreadable forensics cannot un-deny it.

    EMPTY IS NEVER CACHED, and that asymmetry is the whole design. `worst_symbols` is a 14-day
    rolling window over this book's own closes, so it empties during a pause -- and a pause is
    CAUSED by losses (test_structural_bleed_persistence). Writing an empty read through would
    let the ordinary paused state erase the cache, re-creating the forgetting defect one layer
    down. Only evidence of bleeding is recorded; absence of evidence overwrites nothing.

    Best-effort by construction: this is a cache, and a cache that can abort the executor is a
    worse defect than a cache that misses. A failed write leaves the previous entry in place.
    """
    if not rows:
        return
    try:
        _BLEED_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _BLEED_CACHE.with_suffix(".tmp")
        # `rows`, not `worst_symbols`: what gets cached is whichever list the fence actually
        # used, which is `bleeding_symbols` on a current artifact. Naming it after the rolling
        # key would misdescribe an all-time verdict to the next reader.
        tmp.write_text(json.dumps(
            {"rows": rows, "cached": datetime.now(UTC).isoformat()}), "utf-8")
        os.replace(tmp, _BLEED_CACHE)  # atomic: a reader never sees a half-written window
    except OSError as exc:
        print(f"bleed-cache write failed ({exc}) -- keeping previous last-good window")


def _last_good_bleed_window() -> list[Any]:
    """The most recent non-empty bleed window, or [] when none was ever recorded.

    NO AGE BOUND, deliberately. L1.44's contract for this artifact is that deny-direction data
    never loosens with age -- an expiry here would restore the fail-open it exists to close,
    just on a timer. The cache is consulted ONLY when the live read failed, so a healthy
    producer makes it unreachable; chasing a dead producer is the fence's job, not this
    function's.
    """
    try:
        data = json.loads(_BLEED_CACHE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    # `worst_symbols` is read too, so a cache written before the key was renamed still fences.
    # Dropping it would silently discard recorded denials, which is the one direction this
    # whole function exists to prevent.
    rows = data.get("rows") or data.get("worst_symbols")
    return rows if isinstance(rows, list) else []


def _probe_within_cap(sym: str, notional: float | None) -> bool:
    """Is an intended open small enough to be the BOUNDED probe the re-entry row authorises?

    `max_notional_usd` HAD NO READER ANYWHERE IN THE REPO (found 2026-08-13, two days before the
    first probe window opened). `reentry_allowed` granted the probe on a COUNT alone and
    `_structurally_bleeding` returned False, so the open then proceeded at whatever size ordinary
    sizing chose -- while data/execution_reentry.json documented a $100 cap and the protocol's own
    prose promised "a bounded number of MINIMUM-SIZE probes". The bound was documentation.

    That mattered on a date: both recorded rows (1000CATUSDT, COOKIEUSDT) open on 2026-08-15, and
    the mechanism the denylist exists to prevent is precisely a full-size open into a book that
    cannot absorb it -- NOMUSDT took $4,297 into a thin book on 2026-07-13 and cost 40.9% of venue
    equity in five minutes.

    UNKNOWN SIZE IS REFUSED. A caller that does not declare its notional gets False, so the probe
    is denied and the symbol stays blocked: the desk cannot certify a cap it cannot measure
    (L1.28a), and the fail-closed direction here is the one that keeps the verdict standing.
    """
    row = _reentry_conditions().get(sym)
    if not isinstance(row, dict):
        return False
    try:
        cap = float(row["max_notional_usd"])
    except (KeyError, TypeError, ValueError):
        return False                      # no declared cap => no bounded probe exists
    return notional is not None and 0.0 < float(notional) <= cap


def _probe_caps() -> dict[str, float]:
    """AUTHORISED probes this tick -> the recorded cap the open must be SIZED at (per-leg USDT).

    The SIZING half of the L1.16a re-entry protocol. `_probe_within_cap` above is the REFUSING
    half and has existed since 2026-08-13; alone it welded the door shut (L1.45): `_alloc` hands
    every candidate its funding-weighted share of free capital -- hundreds of dollars against a
    $100 cap -- so the gate refused every authorised probe at a size the sizer chose without ever
    learning the cap existed. Measured 2026-08-18: all 7 recorded rows REFUSED, windows open,
    budgets unspent. A bounded probe must be SIZED at its bound, not merely refused above it.

    TIGHTEN-ONLY BY CONSTRUCTION: both consumers apply min(share, cap), so this map can only
    SHRINK an open, never grow one; closes never read it; an unauthorised or capless row never
    enters the map, so every existing refusal is byte-identical.
    """
    out: dict[str, float] = {}
    rows = _reentry_conditions()
    if not rows:
        return out
    tape = execution_tape.read()
    for sym, row in rows.items():
        if sym.startswith("_") or not isinstance(row, dict):
            continue
        try:
            cap = float(row["max_notional_usd"])
        except (KeyError, TypeError, ValueError):
            continue                      # no declared cap => no bounded probe exists
        if cap <= 0.0:
            continue
        if excitation.reentry_allowed(sym, rows, tape)[0]:
            out[sym] = cap
    return out


def _size_refusal(notional: float | None) -> str:
    """Why the size half refused -- an UNKNOWN size and an OVER-CAP size are different claims
    (L1.55): the first is a diagnostic caller that declared no notional (max_audit's dormancy
    probe reads the gate this way), the second is a live sizing verdict. Only the second means
    the probe clamp failed, and a reader triaging fence output must be able to tell them apart.
    """
    if notional is None:
        return ("caller declared no intended notional (diagnostic read at unknown size) -- "
                "refused fail-closed, not a live sizing verdict")
    return f"intended notional {notional!r} is not within the recorded max_notional_usd"


def _structurally_bleeding(sym: str, notional: float | None = None) -> bool:
    """True => this symbol has PROVEN it loses money for the desk; block new opens.

    L1.44 contract (48h: forensics is produced daily): deny-direction data never loosens with
    age, so a STALE denylist STILL DENIES -- the fence owns chasing the dead producer. An
    unreadable file no longer falls back to a bare allow (R0158): it falls back to the last
    good window AND still consults the persistent graveyard below."""
    # R0159 EMPTY floor (min_rows=1): this is the deny-direction ledger that must be non-empty
    # -- a truncated forensics ({}) vaporises every recorded denial, so blocked bleeders
    # (COOKIEUSDT, 1000CATUSDT) become openable again with a young mtime as camouflage. A
    # legitimate forensics artifact always carries worst_symbols and its stamp. The empty read
    # is a recorded stale_read instead of a silent un-deny.
    fr = read_fresh(_FORENSICS, max_age_h=48.0, min_rows=1,
                    caller="run_cashcarry_executor._structurally_bleeding")
    # READS THE ALL-TIME KEY (2026-08-05, restored 2026-08-13). This read `worst_symbols`, which
    # run_trade_forensics computes over a 14-DAY ROLLING window -- correct for the pager (an
    # all-history flag re-pages forever after the fix works) and exactly wrong for a fence. A
    # symbol that proved it loses money does not stop having proved it because a fortnight
    # passed, so the denylist emptied itself on a rolling cycle and the desk re-opened the names
    # it had already paid to learn about. Measured at restoration: the window held 4 of 253
    # all-time closes and named ZERO, while six qualified all-time -- NOMUSDT (-149.4 bps, the
    # 2026-07-13 dead-man symbol), COMPUSDT, ONEUSDT, 1000CATUSDT, BNBUSDT, PEOPLEUSDT. The
    # window is near-empty BECAUSE the book is paused, so the fence protected nothing at exactly
    # the moment a re-arm would re-open the names that caused the pause.
    #
    # The `or` fallback keeps an OLD artifact fencing something rather than nothing: a forensics
    # build that predates `bleeding_symbols` still yields its rolling list. It is `or`, not
    # `if "bleeding_symbols" in doc`, DELIBERATELY: an EMPTY all-time list is falsy and falls
    # through to the rolling one, because a symbol can bleed inside 14d without yet clearing the
    # all-time n>=5 bar. Falling through therefore blocks MORE, never less -- and widening this
    # set can only ever REFUSE an open, never force-close a held carry.
    rows: Any = None
    if isinstance(fr.data, dict):
        rows = fr.data.get("bleeding_symbols") or fr.data.get("worst_symbols")
    # R0158. The old `if not isinstance(rows, list): return False` did TWO things, and only one
    # of them was the documented fallback. It allowed the open (documented), and it returned
    # BEFORE the persistent graveyard at the bottom of this function -- so the 2026-08-05 denial
    # layer, the one that survives an emptied rolling window, was unreachable on exactly the
    # input that most needs it: a corrupt or absent forensics artifact. The newest protection
    # was switched off by the oldest failure mode.
    #
    # Both halves are repaired DENY-DIRECTION ONLY. An unparseable window degrades to the last
    # NON-EMPTY window this executor saw (never to nothing), and control always reaches the
    # graveyard. A symbol in neither source is allowed exactly as before.
    if isinstance(rows, list):
        _remember_bleed_window(rows)
    else:
        rows = _last_good_bleed_window()
        print(f"forensics unreadable ({fr.why}) -- denylist falling back to "
              f"{len(rows)} cached row(s) + persistent graveyard")
    for r in rows:
        try:
            if (r.get("symbol") == sym and int(r.get("n", 0)) >= _BLEED_MIN_N
                    and float(r.get("bps", 0.0)) <= _BLEED_BPS):
                # L1.16a/L1.45 RE-ENTRY. This denylist is SELF-SEALING in a way the alpha
                # graveyard is not: it blocks new OPENS, and `n` -- the trade count its own
                # verdict is conditioned on -- can only grow through opens. So n freezes at the
                # instant of the block and the verdict becomes unrevisitable by construction.
                # Both currently-blocked names (COOKIEUSDT, 1000CATUSDT) are the incident-#6
                # symbols whose losses came from the desk's OWN close bug, fixed 2026-07-27.
                # A bounded, dated, named-change probe is what makes that verdict testable.
                # DEFAULT IS DENY: no recorded condition => blocked exactly as before.
                allowed, why = excitation.reentry_allowed(sym, _reentry_conditions(),
                                                          execution_tape.read())
                if allowed and _probe_within_cap(sym, notional):
                    print(f"re-entry probe {sym}: {why} (<= cap, ${notional:g})")
                    return False
                if allowed:
                    print(f"re-entry probe {sym} REFUSED: {why}, but {_size_refusal(notional)}")
                return True
        except (TypeError, ValueError):
            continue
    # PERSISTENT EXECUTION GRAVEYARD (2026-08-05). Everything above reads `worst_symbols` -- a
    # 14-DAY ROLLING window over this book's OWN closes -- so it EMPTIES while the book is
    # paused. A pause is CAUSED by losses, so the denylist is wiped exactly when it is most
    # needed. Measured this cycle on a freshly-regenerated artifact (not a stale one):
    # worst_symbols == [] and `_structurally_bleeding` returned False for COOKIEUSDT and
    # 1000CATUSDT -- the two incident-#6 symbols the comment above calls "currently-blocked" --
    # so a re-arm would have re-opened them at FULL size, ten days before the 2026-08-15 /
    # $100 / 3-probe ceiling their re-entry rows exist to impose. The careful protocol in
    # data/execution_reentry.json was unreachable code: it is only consulted for symbols the
    # rolling window still happens to carry.
    #
    # A denial that forgets itself is not a denial. A recorded re-entry row is therefore an
    # INDEPENDENT, PERSISTENT denial in its own right, released only through the same L1.16a
    # probe protocol used above. TIGHTEN-ONLY: this branch can add denials, never remove one --
    # symbols in the rolling window are decided before it, and symbols in neither source are
    # allowed exactly as before.
    row = _reentry_conditions().get(sym)
    if isinstance(row, dict):
        allowed, why = excitation.reentry_allowed(sym, _reentry_conditions(),
                                                  execution_tape.read())
        if allowed and _probe_within_cap(sym, notional):
            print(f"re-entry probe {sym} (persistent graveyard): {why} (<= cap, ${notional:g})")
            return False
        if allowed:
            print(f"re-entry probe {sym} (persistent graveyard) REFUSED: {why}, "
                  f"but {_size_refusal(notional)}")
        return True
    return False


#: Fewer realised pairs than this and the sample is an anecdote; the gate keeps using the model.
_MIN_FILLS_FOR_REALISED = 3


def _realised_rt_bps(sym: str) -> float | None:
    """Median round-trip slippage this desk ACTUALLY PAID on this symbol, or None if too few.

    L1.11(b): our own order flow is the one execution dataset no competitor has, and it disagreed
    with the cost surface by roughly fifty times -- surface said 0.35bps for BNB, our fills said
    ~16bps combined (spot +18.1 mean / +7.0 median, futures -1.7). The gate was admitting trades
    that needed twelve days of funding to repay one entry, which is why every post-fix hold bucket
    came back negative while the gate believed it was selecting winners.

    Median rather than mean: one catastrophic fill should cost a trade, not blacklist a symbol
    forever (mean +18.1 vs median +7.0 here -- the gap is a single outlier).
    """
    try:
        rows = json.loads(_TRADES.read_text("utf-8"))
    except Exception:
        return None
    slips = []
    for r in rows:
        if str(r.get("symbol")) != sym:
            continue
        sp, ft = r.get("spot_slip_bps"), r.get("fut_slip_bps")
        if sp is None:
            continue
        try:
            slips.append(abs(float(sp)) + abs(float(ft or 0.0)))
        except (TypeError, ValueError):
            continue
    if len(slips) < _MIN_FILLS_FOR_REALISED:
        return None
    slips.sort()
    return slips[len(slips) // 2]


def _print_rt_bps(sym: str) -> float | None:
    """Pair ROUND-TRIP cost from THIRD-PARTY PRINTS (R0483), or None when unmeasured.

    The third cost basis (L1.11b), beside the book walk and our own fills. Reads the pair table
    fit_print_impact.py publishes: `print_pair_open_bps` exists only when BOTH legs' fits are
    MEASURED at the fit notional and that size sits inside the identified flow range
    (ImpactFit.cost_bps returns None otherwise), so absence is the fail-closed state and no
    status logic is re-implemented here. Round trip = 2x the open: under the fit's own
    convention (half_spread + 0.5*lambda*N per leg) the closing pair pays the same half-spread
    and the same impact magnitude in the opposite direction.

    TIGHTEN-ONLY BY CONSTRUCTION: the caller folds this in through the same max() the realised
    floor uses, so a print basis reading CHEAPER than the book walk -- the thin-book ratios
    (CELR 0.40x, ZEN 0.43x, TST 0.44x) that deferred R0483 -- never binds; only a cost the book
    walk MISSED can change the gate, and that change is a refusal. Stale degrade direction,
    declared (L1.44): a stale print basis STILL TIGHTENS, exactly as the realised-fills floor
    and the stale-cost-model clamp already do. The fit is priced at its own desk_notional (the
    artifact records it); at gate sizes the spread is 91-99.75% of the number, so the size
    mismatch is bounded and points the conservative way (lambda fitted on small flow OVERSTATES
    larger orders -- ImpactFit.cost_bps's own caveat)."""
    fr = read_fresh(_PRINT_IMPACT, max_age_h=48.0, min_rows=1,
                    caller="run_cashcarry_executor._print_rt_bps")
    pairs = fr.data.get("pairs") if isinstance(fr.data, dict) else None
    if not isinstance(pairs, list):
        return None
    for p in pairs:
        if isinstance(p, dict) and p.get("symbol") == sym:
            v = p.get("print_pair_open_bps")
            if v is None:
                return None
            try:
                return 2.0 * float(v)
            except (TypeError, ValueError):
                return None
    return None


def _cost_bucket_key(pair: Any, notional: float | None) -> str:
    """R0247: the cost-model size bucket that COVERS the intended per-leg notional.

    run_cost_model measures FIVE buckets (100/250/500/1000/2500 USDT per leg -- its `_SIZES`,
    same units as the executor's per-leg allocation) but this gate read only '500', discarding
    the d(cost)/d(size) slope every capacity verdict is a statement about. Selection rounds UP
    to the smallest bucket >= notional: on a fixed book, VWAP slippage is monotone in size, so
    the covering bucket can overstate but never understate the order's cost. A notional past
    the largest bucket takes the largest (best measured floor of its true cost -- still tighter
    than the old fixed '500'). Every unknown input -- no notional, non-positive notional, a
    pair map without a usable multi-bucket set -- returns '500', i.e. EXACTLY the pre-R0247
    lookup: the fallback is current behaviour, never looser."""
    if notional is None or not isinstance(pair, dict):
        return "500"
    try:
        n = float(notional)
    except (TypeError, ValueError):
        return "500"
    if not n > 0:
        return "500"
    sizes: list[tuple[float, str]] = []
    for k, v in pair.items():
        if not isinstance(v, dict):
            continue
        try:
            sizes.append((float(k), k))
        except (TypeError, ValueError):
            continue
    if len(sizes) < 2:                    # bucket set absent/degenerate -> current behaviour
        return "500"
    sizes.sort()
    for s, k in sizes:
        if s >= n:
            return k
    return sizes[-1][1]


def _rt_bps(sym: str, notional: float | None = None) -> float:
    """This symbol's MEASURED round-trip cost AT THE INTENDED ORDER SIZE, else the desk median.
    Self-improving: as the recorder accrues the traded names, the gate automatically tightens on
    expensive books (NOMUSDT realised -149 bps, KNCUSDT -211 bps -- thin books where slippage
    dominates). `notional` is the per-leg USDT size the caller intends to send; None (and every
    caller that predates R0247) keeps the historical fixed-'500' lookup."""
    # R0159 EMPTY floor (min_rows=1): a truncated cost_model.json ({}) has a young mtime, so it
    # passed the age gate as FRESH while dropping every measured name -- proven-expensive books
    # (KNC -211bps) silently fall to the default with no record. A legitimate model always
    # carries at least its symbols map, so an empty payload now takes the stale path: same
    # default returned below (KeyError branch, unchanged), but recorded as a stale_read instead
    # of steering silently.
    fr = read_fresh(_COST_MODEL, max_age_h=48.0, min_rows=1,
                    caller="run_cashcarry_executor._rt_bps")
    try:
        pair = fr.data["symbols"][sym]["pair"]
        key = _cost_bucket_key(pair, notional)              # R0247: bucket covering the order
        m = pair[key]
        v = m.get("pair_roundtrip_bps") if isinstance(m, dict) else None
        if v is None and key != "500":
            # Chosen bucket unmeasured (book exhausted at that size in every snapshot) ->
            # fall back to the legacy '500' read, NOT straight to the default: fallback is
            # current behaviour, never looser -- and never cheaper than today for a book the
            # model has priced at the legacy size.
            key, m = "500", pair["500"]
            v = m.get("pair_roundtrip_bps") if isinstance(m, dict) else None
        if v is None:
            return _DEFAULT_RT_BPS
        v = float(v)
        if float(key) > 500.0:
            # R0247 tighten-only clamp: per-size medians exclude exhausted snapshots, so a
            # LARGER bucket can survive only on its deep-book hours and read CHEAPER than
            # '500'. A bigger order may never gate cheaper than the legacy lookup did.
            m500 = pair.get("500")
            v500 = m500.get("pair_roundtrip_bps") if isinstance(m500, dict) else None
            if v500 is not None:
                v = max(v, float(v500))
        # L1.44 stale degrade: a stale measured cost may only TIGHTEN this gate, never loosen
        # it. max() keeps a proven-expensive name (KNC -211bps) expensive when the model
        # freezes, and stops a stale "cheap" reading from admitting opens the current book
        # would refuse. New opens only, as ever -- this can never force-close a held carry.
        modelled = v if fr.fresh else max(v, _DEFAULT_RT_BPS)
    except (KeyError, TypeError, ValueError):
        modelled = _DEFAULT_RT_BPS
    # REALITY FLOORS THE MODEL (L1.11b). MAX, never average: this may only TIGHTEN the gate, the
    # same direction the stale-model rule above already enforces. A bad realised sample can cost
    # us a trade; it can never admit one. Three LABELLED bases (R0483): the book walk, our own
    # fills, and third-party prints -- each can only raise the bar the others set.
    bases = {"book_walk": modelled}
    real = _realised_rt_bps(sym)
    if real is not None:
        bases["own_fills"] = real
    print_rt = _print_rt_bps(sym)
    if print_rt is not None:
        bases["third_party_prints"] = print_rt
    return max(bases.values())


def _entry_gate(sym: str, funding: float, min_hold_h: float = _MIN_HOLD_H,
                notional: float | None = None) -> bool:
    """True => ALLOW opening this carry.

    Requires expected funding capture over the MINIMUM HOLD to beat this symbol's measured
    round-trip AT THE SIZE THE OPEN WOULD ACTUALLY SEND (R0247: `notional` = intended per-leg
    USDT; None keeps the historical fixed-'500' bucket). Applied to NEW OPENS ONLY -- never to
    the hold/target set, so raising the bar can never force-close existing carries (that would
    itself be a churn event)."""
    if _structurally_bleeding(sym, notional):
        return False                      # proven money-loser: never re-open it
    periods = max(1.0, min_hold_h / 8.0)
    return funding * 1e4 * periods > _rt_bps(sym, notional)


def _mkt_or_limit(conn: Any, sym: str, side: str, qty: float) -> str:
    """Close/hedge ``qty``: MARKET first, LIMIT fallback. On a thin/broken book a market order is
    rejected by the venue PERCENT_PRICE filter (-4131) -- and a market-only cover can then NEVER
    clear the leg, so the hedge stays broken forever (this is the gap that stranded orphans on
    illiquid perps). Fall back to a post-only limit at the near touch (bid for BUY / ask for SELL):
    accepted within the price band, rests as maker, fills when liquidity returns. Cancels any stale
    order on the symbol first so repeated reconcile ticks don't stack duplicates. Returns
    'mkt' | 'limit' | '' (nothing placed)."""
    if qty <= 0:
        return ""
    try:
        conn.place_market(sym, side, qty)
        return "mkt"
    except Exception:
        pass                                          # thin book / PERCENT_PRICE -> limit fallback
    with _safe():
        conn.cancel_all(sym)                          # clear stale fallbacks (no dup stacking)
    try:
        bid, ask = conn.book_ticker().get(sym, (0.0, 0.0))
        px = bid if side == "BUY" else ask
        if px and px > 0:
            conn.place_post_only(sym, side, qty, px)
            return "limit"
    except Exception:
        # THE FALLBACK FAILING IS A RESULT, NOT A CRASH -- and it does not lie about it.
        # `return "limit"` sits INSIDE the try, so a failure here falls through to the empty
        # string and the caller sees that no order rested. Swallowing would only be wrong if
        # it let the function claim a fill it did not get.
        pass
    return ""


def _start_equity(state: dict[str, Any], fallback: float) -> float:
    """The book's INCEPTION -- for P&L reporting and the ruin rail -- honouring any capital event.

    ONE function for both of this file's reader sites (the risk rail and `_mark`), and the same
    computation run_live_combined._start_equity performs on the same state key: R0322 pins the two
    published books to a single inception, because they had already drifted to two (this file was
    capital-events-aware, portfolio.json was not, so one ledgered deposit would have made the
    molded book report the deposit itself as P&L).

    Unreadable input falls back instead of raising: the previous inline `float(...)` would throw on
    a null key and take the whole risk block down with it (swallowed by `_safe()`), i.e. NO rail
    evaluation at all that tick. A rail that degrades to its fallback beats a rail that vanishes.
    """
    try:
        raw = float(state.get("start_futures_equity", fallback))
    except (TypeError, ValueError):
        raw = float(fallback)
    return float(capital_events.effective_start_equity(raw))


def _reconcile(pos: dict[str, dict[str, Any]], *, dry: bool,
               cooldown: dict[str, float] | None = None,
               fail_counts: dict[str, int] | None = None,
               orphan_seen: dict[str, int] | None = None,
               orphan_cool: dict[str, float] | None = None,
               flatten_only: bool = False) -> list[str]:
    """Heal hedge drift every cycle -- survival is priority #1. Two invariants restored:

    ``flatten_only`` (2026-07-28 incident): when the book is under a KILL or risk-flatten order
    its target state is FLAT, so the two branches here that ADD exposure -- re-shorting a missing
    futures leg and re-buying a sold spot leg -- are rebuilding exactly what the close path is
    tearing down in the same tick. That loop round-tripped the entire book through market orders
    every 600s and never terminated. Branches that move TOWARD flat (orphan cover, trim-excess,
    adl-flatten) stay live: a flatten order never means "stop reducing risk".

      * ORPHAN futures short (a short with no tracked carry) -> cover it (close to flat).
      * UNHEDGED tracked carry (state expects a short but the futures leg is missing/short) ->
        re-short the deficit so spot_long and perp_short match again (delta-neutral).
        EXCEPTION (2026-07-12 external review): if the VENUE force-closed the short
        (liquidation/ADL during a squeeze), re-shorting walks back into the squeeze that
        just took the leg -- flatten the SPOT leg instead and stand down 24h.

    Idempotent: does nothing when the book is already consistent, and self-corrects the moment a
    transient venue outage (that caused the drift) clears. A failed leg is swallowed, retried next
    cycle -- but NOT silently: `fail_counts` (persisted in executor state, keyed by symbol) tracks
    consecutive `_mkt_or_limit` failures, and 3+ in a row surfaces a RECONCILE-FAIL action line +
    a visible error-log write (2026-07-17 gap-register #16 fix -- a broken pair silently sat
    unhedged for 75 minutes on 2026-07-16 because a rejected re-hedge order returned '' and logged
    nothing)."""
    if dry or not fut.has_keys():
        return []
    try:
        actual = fut.positions()
    except Exception:
        return []                                          # venue read down -> try again next cycle
    acts: list[str] = []
    fails = fail_counts if fail_counts is not None else {}

    def _do(conn: Any, sym: str, side: str, qty: float) -> str:
        how = _mkt_or_limit(conn, sym, side, qty)
        if how:
            fails.pop(sym, None)
        else:
            n = fails.get(sym, 0) + 1
            fails[sym] = n
            if n >= 3:
                with _safe():
                    _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} reconcile fail x{n} "
                                    f"{sym}: both market and post-only limit rejected\n")
                acts.append(f"RECONCILE-FAIL {sym} x{n} (both market+limit rejected, see "
                           f"{_ERR})")
        return how

    tracked = set(pos)
    seen = orphan_seen if orphan_seen is not None else {}
    live_orphans = {s2 for s2, q2 in actual.items()
                    if s2 not in tracked and abs(float(q2)) > 0}
    for s2 in list(seen):                                  # a transient desync disappears -> forget
        if s2 not in live_orphans:
            seen.pop(s2, None)
    _cool = orphan_cool if orphan_cool is not None else {}
    _now = time.time()
    _recent = sum(1 for t0 in _cool.values() if _now - t0 < 3600.0)
    for sym in sorted(live_orphans):
        if _recent >= _ORPHAN_MAX_PER_HOUR:        # cascade -> venue is sick, stand down
            acts.append(f"orphan-CIRCUIT: {_recent} covers in the last hour "
                        f">= {_ORPHAN_MAX_PER_HOUR} -- halting live-ammo cover, page")
            break
        if _now - _cool.get(sym, 0.0) < _ORPHAN_COOLDOWN_S:
            acts.append(f"orphan {sym} in cover-cooldown "
                        f"({(_ORPHAN_COOLDOWN_S - (_now - _cool[sym])) / 60:.0f}m left)")
            continue
        qty = float(actual[sym])
        n = seen.get(sym, 0) + 1
        seen[sym] = n
        if n < _ORPHAN_CONFIRM:                            # must PERSIST before firing live ammo
            acts.append(f"orphan {sym} seen {n}/{_ORPHAN_CONFIRM} -- awaiting confirmation "
                        f"(transient desync is not covered)")
            continue
        cover = abs(qty)
        px = 0.0
        with _safe():                    # priced only when a confirmed orphan exists
            px = float(fut.mark_prices().get(sym, 0.0) or 0.0)
        if px > 0 and cover * px > _ORPHAN_MAX_USD:        # bound each pass; remainder next pass
            acts.append(f"orphan {sym} ${cover * px:.0f} exceeds ${_ORPHAN_MAX_USD:.0f}/pass cap "
                        f"-- covering a capped slice")
            cover = _ORPHAN_MAX_USD / px
        how = _do(fut, sym, "BUY" if qty < 0 else "SELL", cover)
        if how:
            acts.append(f"cover-orphan {sym} {round(cover, 8)} ({how})")
            seen.pop(sym, None)
            _cool[sym] = _now                      # start the quiet period
            _recent += 1
    dead: list[str] = []
    forced: dict[str, int] = {}
    if any(abs(float(actual.get(s, 0.0))) + 1e-9 < abs(float(p["perp_qty"])) * 0.98
           for s, p in pos.items()):                       # query venue only when a leg is short
        with _safe():
            forced = fut.force_orders(2.0)
    for sym, p in pos.items():                             # re-hedge missing/short futures legs
        want = abs(float(p["perp_qty"]))
        have = abs(float(actual.get(sym, 0.0)))
        if have + 1e-9 < want * 0.98:                      # >2% of the short leg is missing
            if sym in forced:                              # ADL/liquidation took it -> flatten pair
                with _safe():
                    if have > 0:
                        _mkt_or_limit(fut, sym, "BUY", round(have, 8))
                    fl = spot.exchange_filters().get(sym, {})
                    q = _round(float(p["spot_qty"]), fl.get("step", 0.0),
                               int(fl.get("qty_prec", 6)))
                    if q > 0:
                        _mkt_or_limit(spot, sym, "SELL", q)
                    dead.append(sym)
                    if cooldown is not None:
                        cooldown[sym] = time.time() + 86400.0
                    acts.append(f"adl-flatten {sym} (venue force-closed short; spot sold, 24h out)")
                continue
            if flatten_only:      # book ordered flat -> re-shorting walks back into the position
                acts.append(f"flatten-mode: skip re-hedge {sym} (book ordered flat)")
                continue
            with _safe():
                fut.set_leverage(sym, 3)
            how = _do(fut, sym, "SELL", round(want - have, 8))
            if how:
                acts.append(f"re-hedge {sym} +{round(want - have, 4)} ({how})")
        elif have > want * 1.02:                           # EXCESS short beyond the tracked leg --
            # an orphan absorbed into a tracked symbol (or a failed partial close) is naked
            # directional short the spot leg does NOT cover -> trim back to the tracked size.
            how = _do(fut, sym, "BUY", round(have - want, 8))
            if how:
                acts.append(f"trim-excess {sym} -{round(have - want, 4)} ({how})")
    for sym in dead:
        pos.pop(sym, None)

    # SPOT leg: a tracked carry whose spot WALLET holds less than the tracked long qty is under-
    # hedged (net short the deficit) -> buy it back. We never SELL excess (untracked orphan longs
    # are harmless junk). This catches spot under-fills the futures-only check would miss.
    with _safe():
        bal = spot.balances()
        sfl = spot.exchange_filters()
        for sym, p in pos.items():
            want = float(p["spot_qty"])
            held = bal.get(sym.replace("USDT", ""), 0.0)
            if held + 1e-9 < want * 0.98:
                if flatten_only:  # re-buying the leg the close just sold is the churn loop itself
                    acts.append(f"flatten-mode: skip spot-rehedge {sym} (book ordered flat)")
                    continue
                fl = sfl.get(sym, {})
                deficit = _round(want - held, fl.get("step", 0.0), int(fl.get("qty_prec", 6)))
                if deficit > 0:
                    how = _do(spot, sym, "BUY", deficit)
                    if how:
                        acts.append(f"spot-rehedge {sym} +{deficit} ({how})")
            elif want > 0 and held > want * 1.02:
                # STRANDED SPOT EXCESS -- REPORT ONLY (2026-07-26). A half-filled pair
                # (`OPEN-FAIL ... spot_ok=True fut_ok=False`) leaves the BOUGHT spot leg orphaned:
                # untracked, unhedged, and invisible to `_mark`, so it is naked long the book does
                # not carry on its own P&L. Selling it is a money-path action -- never automatic --
                # but it must never sit UNSEEN again, which is how it accumulated to multiples of
                # the tracked size. Surfaced in last_actions + the dashboard feed.
                acts.append(f"SPOT-EXCESS {sym}: wallet {held:.6g} vs tracked {want:.6g} "
                            f"(+{held - want:.6g}) -- untracked naked long, verify/flatten by hand")
        # R0321 -- WALLET-WIDE SWEEP FOR FULLY UNTRACKED SPOT LONGS. DETECT AND PAGE ONLY.
        # The loop above can only speak about symbols the tracker already knows: it is keyed on
        # `pos`, so `want` exists only for a tracked carry. An OPEN-FAIL half-fill
        # (`spot_ok=True fut_ok=False`) that never landed a `pos` entry leaves a BOUGHT spot leg
        # with NO tracked symbol at all -- and that orphan is invisible to every existing scan:
        # the futures orphan cover above walks `fut.positions()` (venue SHORTS only), and
        # scripts/hedge_integrity.py's ORPHAN class walks the same futures map. Nothing in the
        # desk ever looked at the spot WALLET for balances the book does not carry, which is the
        # exact shape of the inventory that stranded on 2026-07-19 (~$2,150 of real spot).
        # PLACES NO ORDERS, deliberately: selling spot is a money path, and the futures orphan
        # cover carries confirm/cap/cooldown/circuit bounds precisely because an automatic one
        # fires live ammo into thin books. This one pages a human and stops.
        # DUST FLOOR: the venue's own published `min_notional` (already fetched here as `sfl` --
        # a balance under it cannot even be sold, so paging on it is unactionable noise), floored
        # at the file's existing dollar-noise constant `_RSP_TOL`. No new threshold is minted.
        # Only assets with a tradeable `*USDT` spot market count -- the book buys nothing else,
        # so nothing else can be its orphan.
        spx: dict[str, float] = {}
        with _safe():
            spx = spot.prices()
        for _asset, _free in sorted(bal.items()):
            osym = f"{_asset}USDT"
            ofl = sfl.get(osym)
            if osym in pos or ofl is None or float(_free) <= 0.0:
                continue
            opx = float(spx.get(osym, 0.0) or 0.0)
            oval = float(_free) * opx
            if opx <= 0.0 or oval < max(float(ofl.get("min_notional", 0.0) or 0.0), _RSP_TOL):
                continue                                   # dust / below the venue's own minimum
            acts.append(f"SPOT-EXCESS {osym}: wallet {float(_free):.6g} (${oval:,.0f}) with NO "
                        f"tracked carry -- untracked naked long (half-filled open or manual "
                        f"balance), verify/flatten by hand")
    return acts


def _net_bps(sym: str, funding: float, min_hold_h: float = _MIN_HOLD_H) -> float:
    """Expected NET bps over the minimum hold: funding captured MINUS measured round-trip.

    This is the quantity the desk actually earns, and ranking on it rather than on gross funding
    is the whole of the 2026-07-27 universe switch. Unmeasured symbols carry the pessimistic
    _DEFAULT_RT_BPS, so they sink on their own without a separate denylist.
    """
    return funding * 1e4 * (min_hold_h / 8.0) - _rt_bps(sym)


def _funding_notional(p: dict[str, Any], fpx: float) -> float:
    """Average PERP mark notional over a hold -- the base funding is actually charged on (R0308).

    Funding is paid on the perp's MARK notional at each settlement stamp, never on entry cost
    basis. Entry basis is the one funding-accounting error of the three stacked at the close
    site that is BIASED: it grows with price drift instead of averaging out. With no mark path
    stored per position, the trapezoid of entry and exit perp marks is drift-unbiased to first
    order. Falls back to spot_cost for legacy positions without perp_entry (same fallback the
    liquidation-distance path uses).
    """
    entry = float(p.get("perp_entry") or p["spot_cost"])
    return abs(float(p["perp_qty"])) * (entry + float(fpx)) / 2.0


def _ranked() -> list[tuple[str, float]]:
    """All positive-funding USDT perps tradeable on BOTH testnets, ranked high->low funding."""
    f = current_funding()
    spot_syms, fut_syms = set(spot.exchange_filters()), set(fut.exchange_filters())
    cands = [(s, v) for s, v in f.items()
             if v > 0 and s.endswith("USDT") and s in spot_syms and s in fut_syms]
    return sorted(cands, key=lambda x: -x[1])


# -----------------------------------------------------------------------------------------
# GAP #54 / R0096 -- THE VENUE CAP'S PRODUCTION INPUT. The cap, its constant and its 12 tests
# have existed since 2026-07-29 and the branch was UNREACHABLE outside the suite: this file's
# sole `risk_controls.evaluate` call omitted `venue_equity`, it defaulted to None, and the
# breach branch is guarded by `if venue_equity and eq > 0`. A cap nothing feeds is not a cap.
# -----------------------------------------------------------------------------------------
_VENUE_FEED = Path("web/venue_equity.json")
# The ONE counterparty this book is executed against. `binance_spot_testnet` and
# `binance_testnet` are a spot account and a futures account AT THE SAME EXCHANGE, so for
# counterparty purposes they are one venue, not two -- an FTX-class failure takes both
# sub-accounts together. Naming them separately would halve every measured concentration
# fraction and turn the cap into decoration.
_VENUE = "binance-testnet"
# Max age of the venue-truth feed. REUSED, not minted: it is the desk's own cadence floor for
# this exact artifact (`run_cadence._FLOORS_S0["web/venue_equity.json"] = 1.0`), so the executor
# and the pager agree on when this feed is dead instead of disagreeing by a private constant.
_VENUE_FEED_MAX_AGE_H = 1.0


def _venue_equity(equity: float) -> tuple[dict[str, float], str | None]:
    """Per-venue equity map for the gap-#54 cap, plus an UNMEASURED note when the feed is dead.

    NEVER RETURNS None OR AN EMPTY MAP -- that is the entire point of this function. Both
    short-circuit `risk_controls.evaluate`'s breach branch, so an absent artifact would read
    exactly like "no venue is over the cap": the failure mode this row exists to remove, arrived
    at by a different route. Unknown is not zero (L1.41), and for a CONCENTRATION measurement
    the honest unknown is the WORST case, so the degrade direction here is CONCENTRATED: every
    dollar the executor can see is attributed to the single venue it is executed against. At any
    cap below 1.0 a dead feed therefore PAUSES OPENS instead of waving them through, and the
    note returned alongside is recorded in the decision's own reasons -- the same
    quiet-but-recorded convention `fee_burn_triggers` already uses for an unmeasured input.

    That fallback is not a pessimistic guess today, it is the literal truth: this book runs on
    one venue, so 100% is where the money actually is. Which is also why nothing changes at
    VENUE_CAP = 1.0 -- 100% is AT the cap, not over it, exactly as the one-venue cap intends.

    The numerator is the caller's own `equity` -- the SAME combined-book ruler `evaluate`
    divides by -- and deliberately NOT the feed's `equity` scalar, which measures the dead-man's
    FUTURES scope ("fut margin + tracked spot legs + USDT delta"). Dividing one scope by the
    other is the unit error scripts/claim_verifier.py records as a 175% phantom; here it would
    manufacture a venue breach out of an accounting definition.

    A REAL SPLIT IS HONOURED THE MOMENT ONE EXISTS. R0096 asks for a per-venue map; a `venues`
    object of {venue: equity} in the feed is consumed verbatim, so the day the producer emits
    one this executor needs no second edit and no second review.
    """
    # L1.44 contract: this is a decision-path read, and its fail direction is TIGHTEN (see
    # above), so a stale feed leaves a stale_read record for the fence AND still constrains.
    # R0159 EMPTY floor (min_rows=1): a truncated `{}` has a young mtime and would otherwise
    # pass the age gate carrying no venue information at all.
    fr = read_fresh(_VENUE_FEED, max_age_h=_VENUE_FEED_MAX_AGE_H, min_rows=1,
                    caller="run_cashcarry_executor._venue_equity")
    eq = max(0.0, float(equity))
    concentrated = {_VENUE: eq}
    if fr.fresh and isinstance(fr.data, dict):
        split = fr.data.get("venues")
        if isinstance(split, dict):
            book: dict[str, float] = {}
            for name, held in split.items():
                if isinstance(held, int | float) and not isinstance(held, bool):
                    book[str(name)] = max(0.0, float(held))
            if book:
                # A published split that does not ACCOUNT FOR the whole book leaves a remainder
                # sitting somewhere unnamed, and an unnamed remainder must never be allowed to
                # dilute every fraction toward zero -- that is the unreachable-cap defect all
                # over again, this time wearing a fresh timestamp instead of an absent file.
                # The shortfall is attributed to the venue this executor actually routes to: the
                # known counterparty, which is the worst case AND the likeliest place for it.
                # `_RSP_TOL` is this file's existing dollar-noise floor (no new threshold), so
                # rounding between two measures does not manufacture a PARTIAL every tick.
                named = sum(book.values())
                if eq - named > _RSP_TOL:
                    book[_VENUE] = book.get(_VENUE, 0.0) + (eq - named)
                    return book, (
                        f"venue-split PARTIAL: {_VENUE_FEED} names ${named:,.2f} of ${eq:,.2f} "
                        f"equity, so the unattributed ${eq - named:,.2f} is charged to {_VENUE} "
                        f"-- an unnamed remainder must never dilute the cap toward zero")
                return book, None
        # Scalar-only feed: today's publication, and NOT a failure -- one venue holds the whole
        # book, which is precisely what `concentrated` says. Measured, so no note.
        return concentrated, None
    return (concentrated,
            f"venue-split UNMEASURED ({fr.why}): {_VENUE_FEED} carries no readable per-venue "
            f"map, so 100% of equity is attributed to {_VENUE} -- the worst case, never a "
            f"waved-through 'no breach' (L1.41: unknown is not zero)")


def _rebalance(top: int, hold_top: int, capital: float, *, dry: bool) -> dict[str, Any]:
    # Close-only mode (top=0, hold_top=0: the KILL/flatten path) needs no market ranks --
    # closing reads `pos`, not funding. Decoupled so the kill can execute during a public-
    # data outage or IP ban (2026-07-31: premiumIndex 418 crashed every close-all tick).
    ranked = _ranked() if (top > 0 or hold_top > 0) else []
    # UNIVERSE SWITCH (principal-approved 2026-07-27). Was `ranked[:top]` = top-N by RAW
    # FUNDING. Funding is the COMPENSATION FOR ILLIQUIDITY, so funding-first ranking
    # systematically selected the names whose round-trips destroy the carry: COOKIEUSDT was
    # the most-traded symbol at 21 opens with a MEASURED 130.47bps pair round-trip against
    # ~6.7bps of funding over a 24h hold -- a ~19x loss per rotation. 11 of the 16 most-
    # traded names had no measured cost at all. That single defect explains the 7.75x
    # cost/funding ratio with no residual mystery. Rank by NET instead; _entry_gate still
    # has the final veto. OPENS ONLY -- `target`/`hold_set` are untouched below, so this can
    # never force-close a held carry (whose entry cost is already sunk).
    cands = sorted(ranked, key=lambda c: -_net_bps(c[0], c[1]))[:top]
    # HYSTERESIS: a held carry is kept while it stays in the broad top-`hold_top` positive set;
    # only names that fall out of it (or go non-positive) are closed. Kills noise-driven churn.
    hold_set = {s for s, _ in ranked[:hold_top]}
    target = hold_set
    state = json.loads(_STATE.read_text("utf-8")) if _STATE.exists() else {}
    pos: dict[str, dict[str, Any]] = state.get("positions", {})
    if "start" not in state:
        state["start"] = datetime.now(tz=UTC).isoformat()
        state["start_futures_equity"] = (fut.account_summary()["equity"] if fut.has_keys() else 0.0)
        state["start_spot_value"] = spot.account_value_usdt() if spot.has_keys() else 0.0
    cool: dict[str, float] = {s: float(t) for s, t in state.get("cooldown", {}).items()
                              if float(t) > time.time()}   # ADL/basis-stop names: 24h no re-entry
    state["cooldown"] = cool
    fails: dict[str, int] = {s: int(n) for s, n in state.get("reconcile_fail_counts", {}).items()}
    state["reconcile_fail_counts"] = fails
    ocool: dict[str, float] = {s: float(t) for s, t in state.get("orphan_cooldown", {}).items()}
    state["orphan_cooldown"] = ocool
    orph: dict[str, int] = {s2: int(n2) for s2, n2 in state.get("orphan_seen_counts", {}).items()}
    state["orphan_seen_counts"] = orph
    # FLATTEN MODE: a KILL file is authoritative this tick; a risk-flatten is only known AFTER
    # prices are read, so it latches through state and binds the NEXT tick's reconcile. Both stop
    # the reconciler rebuilding a book the close path is unwinding (2026-07-28 churn incident).
    _flatten_only = _PERMANENTLY_RETIRED or _KILL.exists() or state.get("last_risk_action") == "flatten"
    # GUARD CONSUMPTION (R0071d): live_guard computed a graded response for weeks --
    # effective_size_fraction and limit_only -- and nothing read either. Its binary KILL half
    # was wired (above); the graded half now scales this tick's sizing capital and, in
    # limit_only, forbids taker chasing in the maker path. Stale artifact = neutral.
    _refresh_guard()
    _guard_note = ""
    if _GUARD["size_frac"] < 1.0 or _GUARD["limit_only"]:
        capital = capital * _GUARD["size_frac"]
        _guard_note = (f"live_guard: sizing scaled to {_GUARD['size_frac']:.0%}"
                       + (" + limit-only" if _GUARD["limit_only"] else ""))
    recon = _reconcile(pos, dry=dry, cooldown=cool,          # heal hedge drift FIRST (survival #1)
                       fail_counts=fails, orphan_seen=orph,
                       flatten_only=_flatten_only)
    if cool:
        target -= set(cool)
        cands = [c for c in cands if c[0] not in cool]
    # ENTRY GATE (gap #43): opens only -- never filters hold_set/target, so raising the
    # bar cannot force-close existing carries.
    _pre = len(cands)
    # R0247: gate each candidate AT THE NOTIONAL THE OPEN PATH BELOW WOULD ACTUALLY SEND --
    # the same free-capital, funding-weighted, concentration-capped allocation the sizing
    # block computes (pos is not mutated between here and there, so `free` is the same
    # number). Iterated to a fixed point because removing a name ENLARGES the survivors'
    # allocations (same free capital over fewer names), which can only select an equal-or-
    # costlier size bucket: each pass only removes candidates, so the loop terminates and is
    # tighten-only. Zero free capital gates at notional 0 -> the historical '500' bucket.
    _deployed_gate = sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())
    _free_gate = max(0.0, capital - _deployed_gate)
    # L1.16a SIZING HALF: an authorised re-entry probe is gated AND sent at min(share, cap),
    # computed once per tick (reentry_allowed reads the tape) and applied at BOTH consumers so
    # the size the gate approves is the size the venue sees. Without this clamp the $100-capped
    # probes were unreachable (all 7 rows REFUSED, measured 2026-08-18): the sizer never learned
    # the cap, so `_probe_within_cap` refused every authorised probe at the share _alloc chose.
    _pcaps = _probe_caps()
    while cands:
        _int = _alloc(cands, _free_gate)
        _per_gate = _free_gate / max(1, len(cands))
        _kept = [c for c in cands
                 if _entry_gate(c[0], c[1],
                                notional=min(_int.get(c[0], _per_gate),
                                             _pcaps.get(c[0], float("inf"))))]
        if len(_kept) == len(cands):
            break
        cands = _kept
    if len(cands) < _pre:
        actions_gate = f"entry-gate: {_pre - len(cands)} cand(s) below funding/cost bar"
    else:
        actions_gate = ""
    spot_px, fut_px = spot.prices(), fut.mark_prices()
    # BASIS-BLOWOUT STOP (2026-07-12 external review): the pair is delta-neutral to PRICE, not
    # to BASIS -- it marks against us when the perp trades at a large PREMIUM to spot (short
    # squeeze), which is also the ADL/liquidation-risk state for the short leg. Normal carry
    # basis is a few bps; a >3% instantaneous premium is a dislocation, not harvest -> exit the
    # pair (existing close path) and stand down 24h. Never fires in calm markets: zero drag.
    for sym in list(pos):
        sp, fp = spot_px.get(sym), fut_px.get(sym)
        if sp and fp and (fp - sp) / sp > 0.03:
            target.discard(sym)
            # 6h cooldown (round-3 review: basis spikes are mean-reverting flash events --
            # a 24h stand-down overpays; ADL keeps 24h because a squeeze that force-closed
            # a leg is a different animal). Exit itself is maker-first like every close.
            cool[sym] = time.time() + 21600.0
            actions_pre = f"basis-stop {sym} premium {(fp - sp) / sp:.1%} -> exit pair, 6h out"
            recon = [*recon, actions_pre]
    spot_fl, fut_fl = spot.exchange_filters(), fut.exchange_filters()
    # Size opens from FREE capital only. Held carries are never resized, so their notional is
    # already deployed; allocating the FULL capital across the (often 1-2) fresh names is how
    # 2026-07-13 sized one micro-cap at ~the whole book. Names closing this same cycle still
    # count as deployed here -- one cycle of under-deploy is cheap, over-deploy is ruin.
    deployed = sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())
    free = max(0.0, capital - deployed)
    alloc = _alloc(cands, free)                             # funding-weighted, concentration-capped
    per = free / max(1, len(cands))                        # equal-weight fallback
    actions: list[str] = list(recon)                       # surface reconcile actions in the feed
    if _guard_note:
        actions.append(_guard_note)
    if actions_gate:
        actions.append(actions_gate)

    # GROWTH-POSITIVE risk controls (ruin-boundary sized). Flatten ONLY at the 35% ruin threshold
    # the leverage optimizer uses; PAUSE (not flatten) new opens in stress so existing carries keep
    # harvesting funding. In normal operation this does nothing -> zero drag on compounding.
    risk = None
    if fut.has_keys():
        with _safe():
            # COMBINED book equity, not futures-only: the book is delta-neutral, so in a broad
            # rally the perp shorts drain the futures account while the spot longs gain the same
            # amount in the spot wallet. Judged on the futures account alone, a big enough rally
            # reads as "ruin" and would flatten a perfectly-hedged book at full cost.
            eq = float(fut.account_summary()["equity"])
            spot_side = (sum(float(p["spot_qty"])
                             * (spot_px.get(s, float(p["spot_cost"])) - float(p["spot_cost"]))
                             for s, p in pos.items())
                         + float(state.get("realized_spot_pnl", 0.0)))
            eq_c = eq + spot_side
            # VENUE-TRUTH PERSISTENCE (R0071a, 2026-07-31): this key had THREE readers and no
            # writer -- record_capital_event.py fell through to inception-or-zero, so the ONE
            # command that runs on launch day would have recorded equity $0.00 and re-based the
            # rail ~89% below truth. The executor is the only organ that computes combined
            # equity from venue truth; it now persists that number with its timestamp so the
            # capital-event reader can demand freshness instead of trusting a corpse.
            state["last_combined_equity"] = round(eq_c, 2)
            state["last_combined_equity_at"] = datetime.now(tz=UTC).isoformat()
            # INCEPTION, honouring any RECORDED capital event (libs/risk/capital_events.py).
            # `start_futures_equity` is written once at inception and never re-based, so after a
            # ruin-floor breach the book entered a provably closed loop -- flatten, no opens, no
            # funding, equity constant, flatten -- measured at 113 consecutive rebalances on
            # 2026-07-30, and it froze Gate 0's live-fills clock at 26.42 of 28 days.
            #
            # This does NOT loosen the rail. effective_start_equity is read-only and returns its
            # argument unchanged when no capital event has ever been recorded, so behaviour on an
            # un-deposited box is byte-identical. Only a signed, ledgered deposit or an explicit
            # principal restart moves the inception -- the desk cannot clear its own stop.
            start_eq = _start_equity(state, eq)
            # R0320 -- THE PAUSE RAIL'S BASELINE, AND IT MUST NOT MOVE WHEN MONEY DOES.
            # This line was `peak = max(peak_combined_equity, eq_c)` on RAW equity: a deposit
            # lifts eq_c, eq_c becomes the new high-water, and a LIVE -15% pause clears in one
            # tick with nothing about the book's positions improved -- the denominator moving
            # under the rail (journal-verified 2026-08-01). The rail now measures equity NET of
            # ledgered external flows against a high-water carried ACROSS events: a deposit
            # raises it additively by exactly the cash deposited, a withdrawal lowers it by at
            # most the cash removed, and no event resets it downward. With no capital-event
            # ledger `flow_adjusted_rail` is the identity -- `rail.equity == eq_c` and
            # `rail.peak == max(stored_peak, eq_c)` -- so this is byte-identical arithmetic on
            # any box that has never had an event. `peak_combined_equity` keeps carrying the RAW
            # high-water its other readers (max_audit, record_capital_event) expect.
            _stored_adj = state.get("peak_combined_equity_flow_adj")
            rail = capital_events.flow_adjusted_rail(
                eq_c,
                None if _stored_adj is None else float(_stored_adj),
                float(state.get("peak_combined_equity", start_eq)))
            state["peak_combined_equity_flow_adj"] = rail.peak
            state["peak_combined_equity"] = rail.peak_raw
            gross = sum(float(p["spot_qty"]) * spot_px.get(s, float(p["spot_cost"]))
                        for s, p in pos.items())
            # GAP #54 / R0096 -- the venue cap's production input, previously omitted (so the
            # breach branch short-circuited on every live tick). `_venue_equity` never returns
            # None or {}: an unreadable feed degrades CONCENTRATED, never to "no map", because
            # "no map" and "no breach" are the same value to `evaluate`.
            venue_eq, venue_note = _venue_equity(eq_c)
            # Ruin rail: raw equity vs the ledgered inception (unchanged -- the signed way back
            # from a stop). Pause rail: the flow-adjusted pair. Two rails, two rulers, on purpose.
            risk = risk_controls.evaluate(eq_c, start_eq, rail.peak, gross, ruin_cap_lev=8.0,
                                          venue_equity=venue_eq,
                                          flow_adjusted_equity=rail.equity)
            if venue_note is not None:
                # Recorded in the DECISION, not just logged: `risk.to_dict()` is published into
                # web/cashcarry_live.json every cycle, so a dead venue feed is visible to the
                # dashboard and the alerting path instead of degrading in silence (L1.41).
                risk.reasons.append(venue_note)
            state["last_risk_action"] = risk.action   # latches flatten into next tick's reconcile
            # PER-VENUE PAUSE, NOT ONLY THE GLOBAL ONE (R0096 names this explicitly). `evaluate`
            # does set pause_opens on a breach, but the executor must gate on the BREACHING
            # VENUE it routes to rather than inherit a global verdict: on a multi-venue desk a
            # breach at venue A must not blanket-stop opens at venue B, and a breach at the
            # venue this book trades must stop opens HERE even if a future caller changes what
            # the global action means. OPENS ONLY -- `target` is untouched, so a concentration
            # breach can never force-close a carry (yanking capital off an exchange in a panic
            # realises losses and converts a concentration problem into a solvency one).
            state["venue_breaches"] = list(risk.venue_breaches)
            if _VENUE in risk.venue_breaches:
                cands = []
                actions.append(f"VENUE-CAP {_VENUE}: over {risk_controls.VENUE_CAP:.0%} of "
                               f"equity at one counterparty -- no new opens on this venue")
            if risk.action == "flatten":
                target, cands = set(), []                   # close all, open nothing (survival)
                actions.append("RISK-FLATTEN " + "; ".join(risk.reasons))
            elif risk.action == "pause_opens":
                cands = []                                  # hold + close, add no new risk
                actions.append("RISK-PAUSE-OPENS " + "; ".join(risk.reasons))

    # CLOSE carries that left the positive-funding set (sell spot, cover perp)
    # CHURN GUARD (gap #42): a rotation-driven close on a carry that has not yet earned its
    # round-trip is a measured -8.1%/yr drag. Rails are exempt and still close instantly.
    # KILL FORCES THE RAIL (2026-07-27, Tier 0). Without this the churn guard HELD carries
    # younger than _MIN_HOLD_H while DEADMAN_FIRED and CASHCARRY_KILL were both latched --
    # MOVEUSDT (07:21) and TSTUSDT (08:58) were both under 24h and survived a demanded full
    # unwind. A ruin rail a fee heuristic can veto is not a ruin rail. Opens are already
    # impossible at top=0, so widening the forced set can only ever CLOSE.
    _KILL_FORCES_RAIL = _PERMANENTLY_RETIRED or _KILL.exists()
    _rail_forced = set(cool) | (set(pos) if (_KILL_FORCES_RAIL or (
        risk is not None and risk.action == "flatten")) else set())
    for sym in list(pos):
        if sym not in target:
            p = pos[sym]
            if _churn_guard(_held_hours(p.get("opened")), float(p.get("funding", 0.0)),
                            sym in _rail_forced):
                actions.append(f"hold {sym}: churn-guard "
                               f"({_held_hours(p.get('opened')):.1f}h < {_MIN_HOLD_H:g}h)")
                continue
            # realized trade record: delta-neutral price legs (~cancel) + est funding harvested
            spx, fpx = spot_px.get(sym, p["spot_cost"]), fut_px.get(sym, p["perp_entry"])
            fill: dict[str, Any] = {}                    # dry places no orders -> no fill mode
            if not dry:
                t0 = int(time.time() * 1000) - 2000       # fill window (venue clock-skew slack)
                fill = _execute_pair(sym, float(p["spot_qty"]), "SELL", "BUY")  # close: sell/cover
                # VERIFY-BEFORE-DELETE (2026-07-19 incident, GAP row 34): a close that isn't
                # CONFIRMED filled on both legs must stay tracked, or its spot inventory strands
                # forever (deleted from `pos`, no longer visible to any reconciler pass, no error
                # anywhere). ~$2,150 of real spot inventory was lost this way before this fix.
                if not (fill.get("spot_ok") and fill.get("fut_ok")):
                    actions.append(f"CLOSE-FAIL {sym}: spot_ok={fill.get('spot_ok')} "
                                   f"fut_ok={fill.get('fut_ok')} -- kept tracked, retry next cycle")
                    continue
                # EXIT MARKS FROM ACTUAL FILLS (2026-07-13 incident): ticker marks are blind to
                # what a thin book actually paid us -- see the matching open-path fix below.
                spx = spot.avg_fill(sym, "SELL", t0) or spx
                fpx = fut.avg_fill(sym, "BUY", t0) or fpx
            held = _held_hours(p.get("opened"))
            notl = float(p["spot_qty"]) * float(p["spot_cost"])
            spot_real = float(p["spot_qty"]) * (spx - float(p["spot_cost"]))
            price_pnl = (spot_real
                         + abs(float(p["perp_qty"])) * (float(p["perp_entry"]) - fpx))
            # NOTE: realized_spot_pnl is NOT incremented here. It is re-derived from EXCHANGE GROUND
            # TRUTH at the end of every rebalance (_reconcile_spot_realized) -- a stale/crashed
            # executor or duplicate close-log can then never let it silently drift and fabricate a
            # dashboard loss (the 2026-07-10 phantom). price_pnl (logged below) is the basis input.
            # R0308: funding is charged on the perp's MARK notional (see _funding_notional),
            # never on entry cost basis. `notional` (entry basis) stays: it measures capital
            # deployed, not the base funding is paid on. (held/8.0 stays too: the
            # settlements-clock switch is R0304/L1.47, staged behind the L1.38 window with the
            # venue truth it validates against -- see libs/research/funding_clock.py.)
            fund_notl = _funding_notional(p, fpx)
            est_funding = float(p.get("funding", 0.0)) * fund_notl * (held / 8.0)
            _log_trade({"event": "close", "symbol": sym, "qty": p["spot_qty"],
                        "notional": round(notl, 2), "funding_rate": p.get("funding"),
                        "funding_notional": round(fund_notl, 2),
                        "opened": p.get("opened"), "closed": datetime.now(tz=UTC).isoformat(),
                        "held_hours": held, "price_pnl": round(price_pnl, 2),
                        "est_funding": round(est_funding, 2),
                        "net": round(price_pnl + est_funding, 2),
                        "spot_mode": fill.get("spot"), "fut_mode": fill.get("fut"),
                        **_tca(fill, spx, fpx, "SELL")})
            actions.append(f"close {sym}")
            del pos[sym]

    # OPEN new carries only up to `top` total (hold existing -> never resize an open carry)
    for sym, fnd in cands:
        if len(pos) >= top:                               # book full -> don't over-open
            break
        if sym in pos:
            continue
        px, ffl, sfl = spot_px.get(sym), fut_fl.get(sym), spot_fl.get(sym)
        if not px or not ffl or not sfl:
            continue
        step = max(ffl["step"], sfl["step"])              # coarser step keeps both legs matched
        # Probe symbols open at min(share, recorded cap) -- the same clamp the gate above
        # approved them at; a gate that certifies $100 while the venue sees $1,500 is the
        # NOMUSDT defect with extra steps.
        want_usd = min(alloc.get(sym, per), _pcaps.get(sym, float("inf")))
        qty = _round(want_usd / px, step, int(min(ffl["qty_prec"], sfl["qty_prec"])))
        if qty < max(ffl["min_qty"], sfl["min_qty"]) or qty <= 0:
            continue
        # THIN-BOOK GUARD: an open is optional -- never enter a book that cannot absorb the order.
        # The 2026-07-13 NOMUSDT open filled through a near-empty testnet spot book at a cost the
        # mark-based book never saw (~$4.7k of venue cash on a $4.3k "notional"). Require resting
        # liquidity within 1% of the touch on BOTH entry legs to cover the order several times.
        want = qty * px
        s_depth, f_depth = spot.quote_depth(sym, "BUY"), fut.quote_depth(sym, "SELL")
        if min(s_depth, f_depth) < want * _DEPTH_MULT:
            actions.append(f"skip {sym}: thin book (spot ${s_depth:.0f} / fut ${f_depth:.0f} "
                           f"< {_DEPTH_MULT:g}x ${want:.0f})")
            continue
        fpe = fut_px.get(sym, px)
        if not dry:
            t0 = int(time.time() * 1000) - 2000           # fill window (venue clock-skew slack)
            fill = _execute_pair(sym, qty, "BUY", "SELL")  # open: long spot, short perp
            # VERIFY-BEFORE-TRACK (2026-07-19 incident, GAP row 34): only track a position once
            # both legs are CONFIRMED filled -- an untracked failed/partial open is visible in the
            # error log for follow-up rather than silently absent from every future reconcile pass.
            if not (fill.get("spot_ok") and fill.get("fut_ok")):
                actions.append(f"OPEN-FAIL {sym}: spot_ok={fill.get('spot_ok')} "
                               f"fut_ok={fill.get('fut_ok')} -- not tracked, verify manually")
                continue
            # COST BASIS FROM ACTUAL FILLS (2026-07-13 incident): ticker-at-open recorded a
            # ~$4.7k thin-book fill cost as -$55 -- entry slippage must hit the book the moment
            # it happens. Ticker remains only the fallback when the venue read fails.
            px = spot.avg_fill(sym, "BUY", t0) or px
            fpe = fut.avg_fill(sym, "SELL", t0) or fpe
        pos[sym] = {"spot_qty": qty, "spot_cost": px, "perp_qty": -qty,
                    "perp_entry": fpe, "funding": round(fnd, 6),
                    "opened": datetime.now(tz=UTC).isoformat()}
        if not dry:
            _log_trade({"event": "open", "symbol": sym, "qty": qty,
                        "notional": round(qty * px, 2), "funding_rate": round(fnd, 6),
                        "opened": pos[sym]["opened"],
                        "spot_mode": fill.get("spot"), "fut_mode": fill.get("fut"),
                        **_tca(fill, px, fpe, "BUY"),
                        # L1.45: the assigned arm travels onto the permanent tape. WITHOUT this
                        # line the arm changes execution and leaves no trace, which is strictly
                        # worse than not exciting at all -- unrecorded variation is noise.
                        **{k: v for k, v in fill.items() if k.startswith("exc_")}})
        actions.append(f"open {sym} {qty}")

    # TOP UP undersized held carries toward the FULL-capital target so authorized capital is not
    # left idle (operator-directed 2026-07-19; gap #32). Held carries are otherwise never resized,
    # so a carry opened in a low-free-capital window stayed frozen small. Runs ONLY in normal state
    # (never while a risk rail flattens/pauses), ADDS only (never sizes down), through the SAME
    # 0.35 cap + thin-book depth guard as opens; _topup_plan bounds the aggregate to the free
    # headroom so the book never levers past `capital`.
    if risk is None or risk.action not in ("flatten", "pause_opens"):
        for sym, add in _topup_plan(pos, capital).items():
            px, ffl, sfl = spot_px.get(sym), fut_fl.get(sym), spot_fl.get(sym)
            if not px or not ffl or not sfl:
                continue
            step = max(ffl["step"], sfl["step"])
            qty = _round(add / px, step, int(min(ffl["qty_prec"], sfl["qty_prec"])))
            if qty < max(ffl["min_qty"], sfl["min_qty"]) or qty <= 0:
                continue
            want = qty * px
            s_depth, f_depth = spot.quote_depth(sym, "BUY"), fut.quote_depth(sym, "SELL")
            if min(s_depth, f_depth) < want * _DEPTH_MULT:
                actions.append(f"skip topup {sym}: thin book")
                continue
            p = pos[sym]
            fpe = fut_px.get(sym, px)
            if not dry:
                t0 = int(time.time() * 1000) - 2000
                fill = _execute_pair(sym, qty, "BUY", "SELL")  # add matched legs (spot+perp)
                # VERIFY-BEFORE-TRACK (2026-07-19 incident, GAP row 34): the exact bug class that
                # stranded ~$2,150 -- a topup that isn't CONFIRMED filled on both legs must never
                # be added to the tracked spot_qty/perp_qty, or the excess buy becomes permanently
                # invisible the moment this symbol is later closed against the (unchanged) old qty.
                if not (fill.get("spot_ok") and fill.get("fut_ok")):
                    actions.append(f"TOPUP-FAIL {sym}: spot_ok={fill.get('spot_ok')} "
                                   f"fut_ok={fill.get('fut_ok')} -- not tracked, verify manually")
                    continue
                px = spot.avg_fill(sym, "BUY", t0) or px
                fpe = fut.avg_fill(sym, "SELL", t0) or fpe
            old_q = float(p["spot_qty"])
            new_q = old_q + qty
            p["spot_cost"] = (old_q * float(p["spot_cost"]) + qty * px) / new_q
            p["perp_entry"] = (old_q * float(p["perp_entry"]) + qty * fpe) / new_q
            p["spot_qty"] = new_q
            p["perp_qty"] = -new_q
            if not dry:
                _log_trade({"event": "topup", "symbol": sym, "qty": qty,
                            "notional": round(qty * px, 2), "funding_rate": p.get("funding"),
                            "opened": p.get("opened"),
                            "spot_mode": fill.get("spot"), "fut_mode": fill.get("fut"),
                            **_tca(fill, px, fpe, "BUY")})
            actions.append(f"topup {sym} +{qty}")

    state["positions"] = pos
    if not dry:
        # VENUE-SIDE PROTECTIVE STOPS (R0071c): reconciled every tick against the held book --
        # place missing, replace drifted, remove orphaned. Survives total host death, which the
        # in-process rail cannot.
        actions.extend(_reconcile_protective_stops(pos, state))
    if not dry:                                           # only persist REAL (executed) positions
        _reconcile_spot_realized(state)                   # self-heal accounting from exchange truth
        _STATE.parent.mkdir(parents=True, exist_ok=True)
        _STATE.write_text(json.dumps(state, indent=2), "utf-8")
    return {"state": state, "pos": pos, "cands": cands, "actions": actions,
            "spot_px": spot_px, "fut_px": fut_px,
            "risk": risk.to_dict() if risk else None}


def _reconcile_spot_realized(state: dict[str, Any]) -> None:
    """Re-anchor realized_spot_pnl to exchange ground truth each rebalance (+ on restart).

    Derives it from the venue's own futures REALIZED_PNL (exact) plus the deduped trade-log basis,
    overwriting the stored value only when it has drifted past _RSP_TOL. This makes the phantom-loss
    class impossible: a stale/crashed executor self-heals on its first rebalance after restart, and
    duplicate close-logs can never double-count (see libs/execution/carry_accounting)."""
    if not (fut.has_keys() and state.get("start")):
        return
    with _safe():
        start_ms = int(datetime.fromisoformat(str(state["start"])).timestamp() * 1000)
        venue_realized = float(fut.income_summary(start_ms).get("realized_pnl", 0.0))
        trades = json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []
        derived = derive_spot_realized(venue_realized, trades)
        stored = float(state.get("realized_spot_pnl", 0.0))
        if abs(stored - derived) > _RSP_TOL:
            state["realized_spot_pnl"] = derived
            print(f"[reconcile] realized_spot_pnl {stored:.2f} -> {derived:.2f} "
                  f"(exchange-anchored; drift {derived - stored:+.2f})")


class _safe:
    """Best-effort order context -- a single leg failing must not abort the whole rebalance."""
    def __enter__(self) -> _safe:
        return self

    def __exit__(self, *exc: object) -> bool:
        return True                                       # swallow leg errors (logged via web)


_MAKER_WAIT = 8.0                                          # seconds a post-only quote may rest
# OPENS are patient (2026-07-23 fee audit): measured 75.8% taker fills paying 96.5% of all
# commissions; resting them as maker saves ~86% of fees. A carry open has no urgency (funding
# accrues on 8h boundaries) so waiting minutes for the maker rebate is nearly free. CLOSES keep
# the 8s wait -- the rails must exit fast and this must never slow the risk path.
_MAKER_WAIT_OPEN = 240.0                                   # seconds a post-only OPEN may rest


def _passive_price(bk: dict[str, Any], fl: dict[str, Any], sym: str, side: str) -> float | None:
    """Tick-rounded passive maker price: BUY at best bid, SELL at best ask (won't cross)."""
    bid, ask = bk.get(sym, (0.0, 0.0))
    px = bid if side == "BUY" else ask
    if px <= 0:
        return None
    tick = float(fl.get("tick", 0.0) or 0.0)
    return (round(round(px / tick) * tick, int(fl.get("price_prec", 8)))
            if tick > 0 else float(px))


_STOP_FRAC = 0.35                                          # spec section 3: ruin-line distance


def _stop_plan(pos: dict[str, dict[str, Any]],
               *, frac: float = _STOP_FRAC) -> dict[str, dict[str, float]]:
    """Desired venue-side protective stop per held carry (R0071c; pure -- fully testable).

    Every carry is short the perp, so the protective side is BUY reduce-only at
    entry*(1+frac). frac is the ruin-line distance (spec section 3): far beyond any funding
    wick a carry should survive, comfortably inside the leverage-cap liquidation band, and it
    exists for the host-death case -- an executor that dies leaves a book the venue itself
    will de-hedge cleanly instead of liquidating."""
    out: dict[str, dict[str, float]] = {}
    for sym, p in pos.items():
        qty = abs(float(p.get("perp_qty") or p.get("spot_qty") or 0.0))
        entry = float(p.get("perp_entry") or p.get("spot_cost") or 0.0)
        if qty > 0 and entry > 0:
            out[sym] = {"qty": qty, "stop": round(entry * (1.0 + frac), 8)}
    return out


def _stop_matches(order: dict[str, Any], want: dict[str, float]) -> bool:
    """True when a resting stop is close enough to the plan to keep (5% qty / 2% price)."""
    try:
        return (abs(float(order.get("origQty", 0.0)) - want["qty"]) <= 0.05 * want["qty"]
                and abs(float(order.get("stopPrice", 0.0)) - want["stop"]) <= 0.02 * want["stop"])
    except (TypeError, ValueError):
        return False


def _reconcile_protective_stops(pos: dict[str, dict[str, Any]],
                                state: dict[str, Any]) -> list[str]:
    """Venue-side stop = the rail that survives host death. Reconciled, not fire-and-forget:
    place missing, replace drifted (>5% qty / >2% price), cancel orphans whose position
    closed. Per-id cancels only -- see _resting_quotes for why cancel_all is forbidden near
    stops. No-op on connectors without stop support (testnet parity gap, recorded)."""
    if not fut.has_keys() or not hasattr(fut, "place_stop_market"):
        return []
    canceler = getattr(fut, "cancel_order", None)
    plan = _stop_plan(pos)
    acts: list[str] = []
    tracked = set(state.get("protective_stops", {})) | set(plan)
    for sym in sorted(tracked):
        with _safe():
            stops = [o for o in fut.open_orders(sym) if o.get("type") == "STOP_MARKET"]
            want = plan.get(sym)
            if want is None:                               # position gone -> its stop goes too
                for o in stops:
                    if canceler is not None:
                        canceler(sym, int(o.get("orderId", 0)))
                        acts.append(f"stop-cancel {sym} (position closed)")
                continue
            keep = next((o for o in stops if _stop_matches(o, want)), None)
            for o in stops:                                # drifted/duplicate stops go
                if o is not keep and canceler is not None:
                    canceler(sym, int(o.get("orderId", 0)))
            if keep is None:
                fut.place_stop_market(sym, "BUY", want["qty"], want["stop"])
                acts.append(f"stop {sym} {want['qty']} @{want['stop']} (ruin-line backstop)")
    state["protective_stops"] = plan
    return acts


def _resting_quotes(mod: Any, sym: str) -> list[dict[str, Any]]:
    """Open orders EXCLUDING protective stops (R0071c).

    The maker-pair protocol infers 'my quote filled' from an emptying open-orders book. A
    resting STOP_MARKET breaks that inference permanently: the book never reads empty, the wait
    loop always times out, and the fallback branch cancels the stop and re-takers an
    already-filled leg -- a double fill AND a naked position, triggered by the safety order
    itself. This is why the stop had zero callers; the filter is what makes wiring it safe."""
    try:
        return [o for o in mod.open_orders(sym) if o.get("type") != "STOP_MARKET"]
    except Exception:
        return []


# live_guard consumption (R0071d): refreshed once per tick from data/live_guard.json; the guard
# computed these for weeks with no consumer. size_frac scales the tick's sizing capital;
# limit_only suppresses taker fallbacks. Stale/absent guard = neutral (full size, takers
# allowed) -- the guard's own freeze path is the KILL file, which is already authoritative.
_GUARD: dict[str, Any] = {"size_frac": 1.0, "limit_only": False}


def _refresh_guard() -> None:
    _GUARD.update({"size_frac": 1.0, "limit_only": False})
    # L1.44 contract (0.25h = the guard's own 900s inline rule, now recorded): the fail direction
    # stays OPEN by documented design ("stale guard is no guard" -- the KILL file is the freeze
    # authority), but a dead guard can never write its own KILL, so run_alerts now pages
    # live_guard_dead and this read leaves a stale_read record instead of degrading silently.
    try:
        # R0159 EMPTY floor (min_rows=1): a truncated live_guard.json ({}) used to pass the age
        # gate and steer the tick at FULL SIZE with takers allowed -- the loosening direction,
        # indistinguishable from a healthy guard that chose 1.0. A legitimate guard artifact
        # always carries effective_size_fraction; an empty one now reads not-fresh, lands in the
        # `return` below ("stale guard is no guard", neutral as ever) and leaves a stale_read
        # record for run_alerts/the fence instead of degrading silently.
        fr = read_fresh("data/live_guard.json", max_age_h=0.25, min_rows=1,
                        caller="run_cashcarry_executor._refresh_guard")
        if not fr.fresh or not isinstance(fr.data, dict):
            return                                          # stale guard is no guard
        _GUARD["size_frac"] = min(1.0, max(0.0, float(fr.data.get("effective_size_fraction", 1.0))))
        _GUARD["limit_only"] = str(fr.data.get("canary", {}).get("mode", "")) == "limit_only"
    except Exception:
        return


def _maker_pair(sym: str, qty: float, spot_side: str, fut_side: str,
                *, wait: float, cycle: str | None = None) -> dict[str, Any]:
    """Quote BOTH legs post-only (maker), wait, then taker-fill whatever didn't rest+fill.

    Same qty on both legs -> the pair ends delta-neutral; the wait bounds any transient exposure.
    Returns modes plus spot_ok/fut_ok -- a leg only counts as filled once EITHER it rested and
    left the open-orders book (maker fill) OR its taker fallback returns a confirmed FILLED
    order; a leg that never confirms either way is reported unfilled, never assumed."""
    sbk, fbk = spot.book_ticker(), fut.book_ticker()
    sfl = spot.exchange_filters().get(sym, {})
    ffl = fut.exchange_filters().get(sym, {})
    legs = [("spot", spot, spot_side, sbk, sfl), ("fut", fut, fut_side, fbk, ffl)]
    modes: dict[str, str] = {}
    ok: dict[str, bool] = {"spot": False, "fut": False}
    for name, mod, side, bk, fl in legs:
        px = _passive_price(bk, fl, sym, side)
        with _safe():
            # THE SAME CYCLE ON THE QUOTE AND ON ITS OWN FALLBACK. Without it a retry of this
            # post-only -- including the market fallback below that catches it -- is a SECOND
            # order to the venue, and on a two-legged delta-neutral trade a duplicated leg is an
            # unhedged directional position. The `_pair_cycle` docstring already says this; the
            # maker path simply never received the token.
            o = mod.place_post_only(sym, side, qty, px, cycle=cycle) if px else {}
            modes[name] = "maker_pending" if o.get("orderId") else "taker"
    end = time.time() + wait
    while time.time() < end:                               # wait for the resting quotes to fill
        time.sleep(2.0)
        if not _resting_quotes(spot, sym) and not _resting_quotes(fut, sym):
            break
    for name, mod, side, _bk, _fl in legs:                 # cancel + taker any still-unfilled leg
        with _safe():
            resting = _resting_quotes(mod, sym)
            if resting:
                # Cancel OUR quotes by id, never the symbol's whole book (R0071c): cancel_all
                # here would take the protective STOP_MARKET down with the stale quote --
                # naked-stop removal as a side effect of a fill-timeout. Fall back to
                # cancel_all only on a connector without per-id cancel (testnet spot, where
                # no stops rest).
                canceler = getattr(mod, "cancel_order", None)
                if canceler is not None:
                    for o in resting:
                        canceler(sym, int(o.get("orderId", 0)))
                else:
                    mod.cancel_all(sym)
                if _GUARD["limit_only"]:
                    # live_guard degraded mode (R0071d): no taker chasing -- report the leg
                    # unfilled and let the next tick re-quote. The guard's whole point is that
                    # in a degraded venue state, paying taker to force a fill is the leak.
                    modes[name] = "limit_only_unfilled"
                else:
                    # SAME identity as the quote it replaces: this fallback exists because the
                    # quote did not fill, and the two must never be able to both land.
                    res = mod.place_market(sym, side, qty, cycle=cycle)
                    modes[name] = "taker_fallback"
                    ok[name] = _filled(res)
            elif modes.get(name) == "maker_pending":
                modes[name] = "maker"
                ok[name] = True                             # left the book with no cancel -> filled
    if not (ok["spot"] and ok["fut"]):
        with contextlib.suppress(Exception):
            _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} unfilled leg (maker path) {sym} "
                            f"ok={ok} modes={modes}\n")
    return {**modes, "spot_ok": ok["spot"], "fut_ok": ok["fut"]}


def _filled(res: object) -> bool:
    """True only for a CONFIRMED-filled order response (not merely 'no exception was thrown').

    2026-07-19 incident (GAP register row 34): `_safe()` swallows every exception with zero fill
    verification, so a rejected/partial order looked identical to a successful one to every
    caller -- three closes silently failed to sell their spot leg, stranding ~$2,150 of real
    inventory the position tracker had already deleted and would never revisit. A response is
    only trustworthy when the venue itself confirms FILLED."""
    return (isinstance(res, dict) and res.get("status") == "FILLED"
            and float(res.get("executedQty", 0.0)) > 0)


def _mid_of(conn: Any, sym: str) -> float | None:
    """Read-only mid quote. Returns None rather than 0.0 so a failed read is never mistaken for
    a real price and silently turned into a 100% slippage number."""
    try:
        bid, ask = conn.book_ticker().get(sym, (0.0, 0.0))
        bid, ask = float(bid), float(ask)
        return (bid + ask) / 2.0 if bid > 0 and ask > 0 else None
    except Exception:
        return None


def _tca(fill: dict[str, Any], spot_fill: float | None, fut_fill: float | None,
         spot_side: str) -> dict[str, Any]:
    """Per-leg transaction-cost attribution. POSITIVE bps ALWAYS MEANS WE PAID.

    On an open the carry buys spot and sells futures; on a close it is the reverse. Paying above
    mid when buying and receiving below mid when selling are both costs, so the sign is flipped
    per side to make the columns directly comparable and summable across opens and closes.
    """
    out: dict[str, Any] = {
        "spot_fill": spot_fill, "fut_fill": fut_fill,
        "spot_mid": fill.get("spot_mid"), "fut_mid": fill.get("fut_mid"),
        "wait_s": fill.get("wait_s"),
    }
    sm, fm = fill.get("spot_mid"), fill.get("fut_mid")
    if sm and spot_fill:
        s = (float(spot_fill) - sm) / sm * 1e4
        out["spot_slip_bps"] = round(s if spot_side == "BUY" else -s, 3)
    if fm and fut_fill:
        f = (float(fut_fill) - fm) / fm * 1e4          # futures leg is the opposite side of spot
        out["fut_slip_bps"] = round(-f if spot_side == "BUY" else f, 3)
    return out


def _execute_pair(sym: str, qty: float, spot_side: str, fut_side: str) -> dict[str, Any]:
    """TCA WRAPPER (2026-07-27). Captures the decision-time benchmark and elapsed time around the
    unchanged execution path, so realised slippage becomes measurable per leg, per symbol, per
    mode. Adds no order logic; the mid reads are read-only and failures degrade to None."""
    _t0 = time.time()
    _sm = _mid_of(spot, sym)
    _fm = _mid_of(fut, sym)
    res = _execute_pair_impl(sym, qty, spot_side, fut_side)
    if spot_side == "SELL":            # a CLOSE succeeds by reaching FLAT, not by filling an order
        res = _close_goal_state(sym, res)
    res["spot_mid"] = _sm
    res["fut_mid"] = _fm
    res["wait_s"] = round(time.time() - _t0, 3)
    return res


def _close_goal_state(sym: str, res: dict[str, Any]) -> dict[str, Any]:
    """Mark a CLOSE leg that is ALREADY at its goal state (flat) as done rather than failed.

    2026-07-28 incident: every futures hedge had been force-closed out from under the book, so
    the close path's reduceOnly cover had nothing to reduce. The venue rejects that order,
    `_filled` returns False, and `fut_ok=False` kept the pair tracked for a retry -- every tick,
    forever, while `_reconcile` rebuilt both legs in front of each attempt. 11,136 commission
    events against 251 logged round-trips; $1,456 of fees in 48h against $113 of LIFETIME funding
    harvest. The bug is definitional: `_ok` meant "an order filled" when a close only ever needed
    "the leg is flat".

    Checked PER LEG against the venue, so a leg that genuinely still holds inventory still fails
    and stays tracked -- the 2026-07-19 stranded-inventory fix (~$2,150 of real spot deleted from
    the tracker while still held) is preserved exactly, not loosened.
    """
    if not res.get("fut_ok"):
        with contextlib.suppress(Exception):
            if abs(float(fut.positions().get(sym, 0.0))) <= _FLAT_EPS:
                res["fut_ok"], res["fut"] = True, "already-flat"
    if not res.get("spot_ok"):
        with contextlib.suppress(Exception):
            step = float(spot.exchange_filters().get(sym, {}).get("step", 0.0) or 0.0)
            held = float(spot.balances().get(sym.replace("USDT", ""), 0.0))
            if held <= max(step, _FLAT_EPS):   # nothing left above the venue's tradable increment
                res["spot_ok"], res["spot"] = True, "already-flat"
    return res


_EXC_SEQ = itertools.count()
# The cadence jitter in force for the cycle that placed the current orders. Module-level because
# the draw happens in the main loop and is consumed at the fill site; it lands on the tape as
# `exc_cadence_jitter`, making the executor's own timing variation an identifying regressor
# instead of unrecorded noise.
_EXC_CADENCE: dict[str, float] = {}


def _excitation_arm(sym: str, spot_side: str, qty: float) -> excitation.Arm:
    """Assign this order its L1.45 excitation arm. NEVER raises, NEVER changes size.

    An experiment must not be able to take down the executor that feeds it, so every failure path
    degrades to the baseline arm -- which reproduces today's behaviour exactly (`_MAKER_WAIT_OPEN`
    is the design's baseline value). The reason is carried on the Arm and lands on the tape, so
    "why did this order not vary" is answerable afterwards; a silent degrade would make an inert
    experiment look identical to a running one.

    CLOSES RETURN BEFORE ANY I/O. `assign()` would refuse the SELL side anyway, but reaching it
    costs a design load plus a full tape read -- on the CLOSE path, which every comment in this
    file insists must be fast because the rails exit through it. Spending risk-path latency to
    compute an arm that is then discarded is exactly the wrong trade, and it would get worse as
    the tape grows.
    """
    if spot_side != "BUY":
        return excitation.Arm(name=excitation.BASELINE_ARM, maker_wait_s=_MAKER_WAIT,
                              cell="close", seed="", baseline=True,
                              reason="close side -- never excited (risk path, no I/O)")
    try:
        design = excitation.load_design()
        spent = excitation.spent_today(execution_tape.read())
        return excitation.assign(sym, spot_side, qty, design=design,
                                 spent_today_usd=spent, sequence=next(_EXC_SEQ))
    except Exception as e:  # observer-grade: the money path never fails for an experiment
        with contextlib.suppress(Exception):
            _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} excitation degraded {sym}: "
                            f"{e!r}\n")
        return excitation.Arm(name=excitation.BASELINE_ARM, maker_wait_s=_MAKER_WAIT_OPEN,
                              cell="unknown", seed="", baseline=True,
                              reason=f"excitation error, degraded to baseline: {e!r}")


def _exc_fields(arm: excitation.Arm, spot_side: str) -> dict[str, Any]:
    """Arm stamp for the tape -- OPENS ONLY.

    A close is stamped with NOTHING rather than with the baseline arm. `assign()` refuses the
    SELL side, so a close's arm carries the design's baseline wait (240s) while the close itself
    goes straight to market -- stamping it would write a wait the order never used, and the
    identification fit would read those rows as 240s-wait observations. A field that describes
    what did not happen is worse than an absent one.
    """
    if spot_side != "BUY":
        return {}
    out = arm.as_tape_fields()
    if "last_jitter" in _EXC_CADENCE:
        out["exc_cadence_jitter"] = _EXC_CADENCE["last_jitter"]
    return out
#: GAP #49. How long one pair-execution identity stays live. 300s comfortably spans an
#: ambiguous timeout plus its retries and a restart-and-reconcile pass, which are the two
#: paths that re-place an order, while staying far short of the next rebalance.
_CYCLE_S = 300


def _deterministic_pair_intent(
    *,
    symbol: str,
    qty: float,
    spot_side: str,
    fut_side: str,
    observation: dict[str, Any],
    rationale: str,
) -> dict[str, Any]:
    """Materialise the exact paired order through the frozen production path before submission."""
    signal = {"symbol": symbol, "rationale": rationale}
    desired = {"symbol": symbol, "qty": qty, "spot_side": spot_side, "fut_side": fut_side}
    replay = deterministic_hot_path(
        _MANIFEST,
        observation,
        lambda _observation, _manifest: signal,
        lambda _signal, _manifest: desired,
        lambda order, _manifest: order,
        lambda approved, _manifest: approved,
    )
    payload = {
        "manifest": _MANIFEST,
        "observation": observation,
        "signal": signal,
        "desired_order": desired,
        "risk_output": replay["order"],
        "adapter_order": replay["order"],
        "stage_hashes": replay["stage_hashes"],
        "path_hash": replay["path_hash"],
        "recorded_at": datetime.now(tz=UTC).isoformat(),
    }
    _HOT_REPLAY.parent.mkdir(parents=True, exist_ok=True)
    _HOT_REPLAY.write_text(json.dumps(payload, indent=2), "utf-8")
    order = replay.get("order")
    if not isinstance(order, dict):
        raise RuntimeError("deterministic hot path did not return a concrete order")
    return dict(order)

def _execution_preflight(
    *,
    ranked: list[tuple[str, float]],
    spot_prices: dict[str, float],
    fut_prices: dict[str, float],
    spot_filters: dict[str, Any],
    fut_filters: dict[str, Any],
    reconciled: bool,
    risk_measured: bool,
    authenticated: bool,
    dry: bool,
) -> dict[str, Any]:
    """Fail closed for NEW RISK only; reconciliation and exits remain available.

    A successful signed account read is also evidence that venue clock skew is within Binance's
    receive window. The artifact lets the completion program compare the production contract to
    reality instead of reconstructing it after the fact.
    """
    checks = {
        "data_fresh": bool(ranked and spot_prices and fut_prices),
        "clock_synchronised": bool(dry or authenticated),
        "manifest_hash_valid": bool(_MANIFEST.get("immutable") and _MANIFEST.get("manifest_hash")),
        "venue_eligible": bool(spot_filters and fut_filters),
        "auth_valid": bool(dry or authenticated),
        "reconciled": bool(reconciled),
        "risk_kernel_valid": bool(dry or risk_measured),
        "journal_writable": bool(os.access(_TRADES.parent, os.W_OK)),
    }
    venue_doc = {
        "capabilities": {
            "spot_symbols_available": bool(spot_filters),
            "futures_symbols_available": bool(fut_filters),
            "paired_symbol_count": len(set(spot_filters) & set(fut_filters)),
            "maker_first": bool(_MAKER),
            "paired_fill_verification": True,
        },
        "measured_at": datetime.now(tz=UTC).isoformat(),
    }
    _VENUE_CAPABILITIES.parent.mkdir(parents=True, exist_ok=True)
    _VENUE_CAPABILITIES.write_text(json.dumps(venue_doc, indent=2), "utf-8")
    report = {
        **preflight_contract(checks),
        "manifest_hash": _MANIFEST["manifest_hash"],
        "checked_at": datetime.now(tz=UTC).isoformat(),
        "scope": "NEW_OPENS_AND_TOPUPS; exits/reconciliation always remain available",
    }
    _PREFLIGHT.parent.mkdir(parents=True, exist_ok=True)
    _PREFLIGHT.write_text(json.dumps(report, indent=2), "utf-8")
    return report


def _pair_cycle(sym: str, spot_side: str, qty: float) -> str:
    """Stable identity for ONE logical pair execution, used to make order IDs idempotent.

    Quantity is included because two carries on the same symbol in the same direction and the
    same rebalance differ by size, and merging them under one ID would suppress the second as a
    duplicate -- trading a duplicate-fill risk for a missing-fill risk rather than removing it.
    The coarse time term still bounds how long an ID stays live, so a genuinely new pass tomorrow
    is never confused with today's.
    """
    return f"{sym}:{spot_side}:{qty:.10g}:{int(time.time() // _CYCLE_S)}"


def _execute_pair_impl(sym: str, qty: float, spot_side: str, fut_side: str) -> dict[str, Any]:
    """Fill both carry legs -- maker-first (execution alpha: lower fees) if enabled, else market.

    Returns {"spot": mode, "fut": mode, "spot_ok": bool, "fut_ok": bool} -- callers MUST check
    the _ok flags before treating a leg as filled; a leg failing must not abort the whole
    rebalance (that is what `_safe()` still protects), but it must never be reported as success.
    Maker path has a taker fallback; on ANY maker error we fall back to a plain market pair."""
    # CLOSES BYPASS THE MAKER PATH (2026-07-27, incident #6 recurrence). _MAKER=True made
    # _maker_pair the DEFAULT, and its post-only limits carry neither reduceOnly nor a venue
    # size cap -- so repeated close attempts accumulated resting fills that bought a short
    # through zero into a long. Twice: COOKIEUSDT +916,772, then 1000CATUSDT +1,138,985.
    # A close is a CERTAINTY problem, not a fee problem; the desk's own note already says
    # "patient on OPENS, fast on CLOSES". Opens keep the maker rebate, which is where it pays.
    _CLOSE_IS_MARKET_ONLY = spot_side == "SELL"
    # GAP #49: ONE cycle token per logical pair execution, computed HERE -- before the maker
    # attempt -- because the maker path and the market fallback that catches it must carry the
    # SAME identity. It used to be computed after the maker attempt returned, so a maker quote
    # and the market pair that replaced it were two different orders to the venue across the
    # maker wait, and a retry could land both.
    #
    # Retries of this pair reproduce the same client order IDs regardless of how long the retry
    # took, so the venue dedupes them. A wall-clock bucket alone would not: an order placed just
    # before a bucket rolls has a sub-second retry window, after which the duplicate is placed --
    # and a duplicated leg on a delta-neutral book is an unhedged directional position.
    _cycle = _pair_cycle(sym, spot_side, qty)
    arm = _excitation_arm(sym, spot_side, qty)
    if _MAKER and not _CLOSE_IS_MARKET_ONLY:
        try:
            # patient on OPENS (spot BUY = entering a carry), fast on CLOSES (spot SELL =
            # unwinding, where the rails need speed). See the fee audit note above.
            #
            # L1.45 EXCITATION: on OPENS the wait comes from the assigned arm, whose baseline
            # value IS _MAKER_WAIT_OPEN -- so an absent/disabled design reproduces this line's
            # previous behaviour exactly. Closes are never excited: `assign()` refuses the SELL
            # side outright, and this branch is unreachable for closes anyway.
            _w = arm.maker_wait_s if spot_side == "BUY" else _MAKER_WAIT
            res = _maker_pair(sym, qty, spot_side, fut_side, wait=_w, cycle=_cycle)
            return {**res, **_exc_fields(arm, spot_side)}
        except Exception as e:  # maker machinery failed -> safe market fallback
            with contextlib.suppress(Exception):
                _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} maker fail {sym}: {e!r}\n")
    spot_res: object = None
    fut_res: object = None
    # CLOSE legs are reduceOnly (2026-07-27 incident). spot_side=="SELL" IS the close/unwind
    # direction; the futures leg then BUYS to cover a short, which is exactly the order that
    # walked COOKIEUSDT through zero into a +916,772 long. reduceOnly makes that impossible.
    # Opens (spot BUY / futures SELL) must NOT be reduceOnly -- they establish the short.
    _reduce_only_leg = spot_side == "SELL"
    # GAP #49: one cycle token per logical pair execution. Retries of THIS pair reproduce the
    # same client order IDs regardless of how long the retry took, so the venue dedupes them.
    # A wall-clock bucket alone would not: an order placed just before a bucket rolls has a
    # sub-second retry window, after which the duplicate is placed -- and a duplicated leg on a
    # delta-neutral book is an unhedged directional position.
    with _safe():
        spot_res = spot.place_market(sym, spot_side, qty, cycle=_cycle)
    with _safe():
        fut_res = fut.place_market(sym, fut_side, qty, reduce_only=_reduce_only_leg,
                                   cycle=_cycle)
    spot_ok, fut_ok = _filled(spot_res), _filled(fut_res)
    if not (spot_ok and fut_ok):
        with contextlib.suppress(Exception):
            _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} unfilled leg {sym} "
                            f"spot_ok={spot_ok} fut_ok={fut_ok} spot_res={spot_res!r} "
                            f"fut_res={fut_res!r}\n")
    # The arm is stamped on the TAKER path too. It was assigned before the maker attempt, so a
    # fill that fell back to taker still belongs to its assigned condition -- dropping the stamp
    # here would silently delete exactly the observations where the maker path failed, which is
    # attrition correlated with the outcome and the classic way an experiment fools itself.
    return {"spot": "taker", "fut": "taker", "spot_ok": spot_ok, "fut_ok": fut_ok,
            **_exc_fields(arm, spot_side)}


def _mark(rb: dict[str, Any]) -> dict[str, float | None]:
    pos, spot_px, fut_px = rb["pos"], rb["spot_px"], rb["fut_px"]
    spot_pnl = perp_pnl = notional = 0.0
    fut_realized: float | None = None
    for _sym, p in pos.items():
        spx = spot_px.get(_sym, p["spot_cost"])
        fpx = fut_px.get(_sym, p["perp_entry"])
        spot_pnl += float(p["spot_qty"]) * (spx - float(p["spot_cost"]))   # our long-spot legs
        perp_pnl += abs(float(p["perp_qty"])) * (float(p["perp_entry"]) - fpx)   # short (display)
        notional += float(p["spot_qty"]) * spx
    # REAL net = spot side + futures side, SYMMETRIC on realized PnL. The futures-equity delta
    # already contains its realized closes + funding + fees; the spot side needs open marks PLUS
    # the accumulated realized PnL of closed spot legs (their proceeds sit in the spot wallet,
    # invisible to open-position marks -- omitting them fabricated a loss as carries closed).
    state = rb["state"]
    spot_realized = float(state.get("realized_spot_pnl", 0.0))
    net = spot_pnl + spot_realized
    fut_pnl = 0.0
    # None, NOT 0.0 -- these come from a separate venue call that can fail on its own, and a
    # failed measurement must never be publishable as a measured zero (2026-07-26 incident).
    funding: float | None = None
    fut_commission: float | None = None
    if fut.has_keys():
        with _safe():
            fut_eq = fut.account_summary()["equity"]
            # EFFECTIVE inception here too (R0071b, 2026-07-31): this reporting site kept the
            # raw inception after the rail site was fixed, so the first post-deposit dashboard
            # tick would have shown the whole deposit as fabricated P&L -- the exact two-sites/
            # one-truth class the equity bug came from.
            start_eq = _start_equity(state, fut_eq)
            fut_pnl = fut_eq - start_eq                   # futures leg (realized+funding+fees+unrl)
            net = spot_pnl + spot_realized + fut_pnl
        # SEPARATE guard from the equity read above. Sharing one `_safe()` made the failure
        # PARTIAL: the equity assignment landed, then the income call threw, and the swallowed
        # exception left funding/commission at zero -- publishing a real futures PnL next to a
        # fabricated zero harvest, which is exactly the combination the bleed alarm reads as a
        # total bleed. `read_income` retries transient 5xx and returns None when it truly cannot
        # measure, so "unknown" survives all the way to the dashboard instead of decaying to 0.
        if state.get("start"):
            with _safe():
                start_ms = int(datetime.fromisoformat(str(state["start"])).timestamp() * 1000)
                # ONE income call, BOTH numbers -- `income_summary` has always returned the exact
                # paginated `commission` and this book read only `funding`, discarding the fee
                # bill that is the single largest term of the leak it was alarming about.
                inc = read_income(lambda: fut.income_summary(start_ms))
                if inc is not None:
                    funding = float(inc.get("funding", 0.0))
                    fut_commission = abs(float(inc.get("commission", 0.0)))
                    # THE SECOND MEASUREMENT OF THE FUTURES LEG, and it was being thrown away.
                    # `realized_pnl` came back in this same payload and only `_reconcile_spot_
                    # realized` ever read it, so the equity-delta path above had nothing to be
                    # checked against -- which is how a $4,807.75 inception leak published as
                    # profit for four days (2026-08-05). One call, three numbers, all kept.
                    fut_realized = float(inc.get("realized_pnl", 0.0))
    # The gap a ledgered re-base would legitimately open between the two measurements. RAW state
    # inception minus the rail's effective one: `_start_equity` honours capital events, and every
    # dollar of that adjustment lands in the equity delta as fabricated P&L.
    try:
        raw_start = float(state.get("start_futures_equity", 0.0) or 0.0)
        rebase_usd = round(raw_start - capital_events.effective_start_equity(raw_start), 2)
    except (TypeError, ValueError):
        rebase_usd = 0.0
    return {"spot_pnl": round(spot_pnl, 2), "perp_pnl": round(perp_pnl, 2),
            "spot_realized": round(spot_realized, 2), "fut_pnl": round(fut_pnl, 2),
            "funding": None if funding is None else round(funding, 2), "net_pnl": round(net, 2),
            "fut_commission": None if fut_commission is None else round(fut_commission, 2),
            "fut_realized": None if fut_realized is None else round(fut_realized, 2),
            "rebase_usd": rebase_usd, "perp_unrealized": round(perp_pnl, 2),
            "notional": round(notional, 2)}


def _emit(rb: dict[str, Any], marks: dict[str, float | None], dry: bool) -> None:
    pos = rb["pos"]
    # CARRY-LEAK ALARM ON THE BOOK THAT HOLDS THE MONEY (2026-07-26). `carry_bleed_report` was
    # only ever wired into the MOLDED book (run_live_combined), so the PRIMARY executed book --
    # this file -- shipped a dashboard with NO bleed alarm at all, which is exactly how a leak
    # runs for weeks unnoticed. Same function, same thresholds, now on the executed book.
    # spot side = open marks + realized of closed spot legs; fut side = futures-equity delta.
    # CROSS-CHECK THE FUTURES LEG AGAINST ITSELF BEFORE JUDGING THE BOOK. The equity delta and the
    # venue income ledger measure the same leg; only the former has a re-baseable input, so their
    # disagreement is the accounting error rather than a market event. Computed BEFORE the bleed
    # report so the alarm can name the cause instead of guessing at a naked leg (2026-08-05).
    recon = reconcile_futures_leg(
        equity_delta=marks.get("fut_pnl"), venue_realized=marks.get("fut_realized"),
        funding=marks["funding"], commission=marks.get("fut_commission"),
        unrealized=marks.get("perp_unrealized") or 0.0,
        rebase_usd=float(marks.get("rebase_usd") or 0.0))
    bleed = carry_bleed_report(funding=marks["funding"],
                               spot_pnl=round((marks["spot_pnl"] or 0.0)
                                              + (marks["spot_realized"] or 0.0), 2),
                               fut_pnl=marks.get("fut_pnl") or 0.0,
                               open_legs=len(pos), recon=recon)
    # Attribute the leak ONLY when both terms are real measurements. With an unknown fee bill the
    # split would dump the entire commission into `residual`, manufacturing exactly the phantom
    # that `attribute_non_funding`'s own docstring warns against -- an unexplained quantity that
    # looks explained. No measurement is better than a confident wrong one.
    fut_comm = marks.get("fut_commission")
    leak = (attribute_non_funding(
        bleed.non_funding_pnl,
        dedup_basis(json.loads(_TRADES.read_text("utf-8")) if _TRADES.exists() else []),
        fut_comm)
        if bleed.non_funding_pnl is not None and fut_comm is not None else None)
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "mode": "dry" if dry else "live-paper",
        "strategy": "delta-neutral cash-and-carry (long spot + short perp, positive funding)",
        "executed": not dry, "n_carries": len(pos),
        "deployed_notional": marks["notional"],
        # THE HEADLINE FIELD CARRIES THE HONEST NUMBER, and the wrong one loses the name it had.
        # `hurdle_rate.py:97` reads exactly this key to ask whether the carry beats T-bills net of
        # costs (L1.5), and on 2026-08-05 it was being handed +2937.28 for a book that had really
        # lost 1869.74 -- a validation gate fed a $4.8k overstatement of the only sleeve it judges.
        # Publishing the truth under a NEW name and leaving the old one wrong would have fixed the
        # dashboard and left the gate corrupted, which is the more expensive half.
        "net_pnl": (marks["net_pnl"] if recon.reporting_pnl is None
                    else round((marks["spot_pnl"] or 0.0) + (marks["spot_realized"] or 0.0)
                               + recon.reporting_pnl, 2)),
        # The equity-delta reading, kept so the two never silently converge again.
        "net_pnl_equity_delta": marks["net_pnl"],
        "net_pnl_basis": ("venue-income-ledger" if recon.reporting_pnl is not None
                          else "equity-delta (income UNMEASURED -- cross-check unavailable)"),
        "funding_harvested": marks["funding"],
        "spot_leg_pnl": marks["spot_pnl"], "perp_leg_pnl": marks["perp_pnl"],
        "spot_realized_pnl": marks["spot_realized"],
        "fut_leg_net": marks.get("fut_pnl", 0.0),
        "non_funding_pnl": bleed.non_funding_pnl,
        "harvest_eaten_frac": bleed.harvest_eaten_frac,
        "bleed_alert": bleed.alert, "bleed_verdict": bleed.verdict,
        # Publishes WHETHER the harvest was measured at all. Downstream (max_audit, the dashboard,
        # the molded book) must be able to tell "earned nothing" from "could not read the venue";
        # they are opposite states and only one of them is an execution problem.
        "funding_measured": bleed.measured,
        # WHERE the leak went, not just how big it is -- the alarm alone is unactionable and the
        # integrity watch is required to attribute it every cycle.
        "leak_attribution": leak,
        # THE TWO MEASUREMENTS, PUBLISHED SIDE BY SIDE. `net_pnl` above is the equity-delta reading
        # and is kept so the disagreement stays visible rather than being quietly overwritten --
        # a number that silently changes meaning is how the first error survived. `net_pnl_reported`
        # is the one downstream should size on: it has no re-baseable input.
        "fut_leg_reconciliation": recon.model_dump(),
        "fut_commission": marks.get("fut_commission"),
        "carries": [{"symbol": s, "qty": p["spot_qty"], "funding_8h": p["funding"]}
                    for s, p in pos.items()],
        "last_actions": rb["actions"],
        "risk": rb.get("risk"),
        "note": ("PRIMARY executed book (paper). Delta-neutral: spot hedges perp, profit = funding "
                 "harvested on the short perp. Builds the forward track record the gate sizes on."),
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2, default=str), "utf-8")


def _live_params(top: int, hold_top: int, capital: float) -> tuple[int, int, float]:
    """LIVE-tunable params: override top / hold_top / capital from data/cashcarry_config.json each
    rebalance WITHOUT restarting the executor. Changing a param used to require the flatten+restart
    the 2026-07-10 churn fix needed; now just write the JSON and the running loop picks it up next
    cycle. argv are the defaults; any key present in the file overrides. Defensive -> any error
    (missing/corrupt file, bad type) silently falls back to the argv values."""
    try:
        if _CONFIG.exists():
            cfg = json.loads(_CONFIG.read_text("utf-8"))
            top = int(cfg.get("top", top))
            hold_top = int(cfg.get("hold_top", hold_top))
            capital = float(cfg.get("capital", capital))
    except (ValueError, TypeError, OSError):
        pass
    return top, hold_top, capital



def _foreign_executor_alive() -> bool:
    """True when a DIFFERENT live executor owns the heartbeat.

    SINGLE-BOOK INVARIANT (2026-07-26): two --live executors on one delta-neutral book
    double-order and churn. The startup-only lock could not catch a duplicate spawned during a
    slow heartbeat window -- both then refreshed the same file forever. Same failure the dead-man
    rail hit on 07-11 and fixed with a per-loop PID check; the executor now does the same.
    """
    try:
        parts = _HB.read_text("utf-8").split()
        if not parts or not parts[0].isdigit():
            return False                       # legacy/unowned heartbeat -- reclaim it
        pid = int(parts[0])
        if pid == os.getpid():
            return False
        return (time.time() - _HB.stat().st_mtime) < _HB_TICK * 2.5
    except (OSError, ValueError):
        return False


def main() -> None:
    # L1.42 STRICT: the executor must NOT trade under a tampered core or a doctrine
    # missing a law family. Every other organ pages and continues; here, refusing to
    # act IS the safe direction -- an unlawful trade cannot be undone.
    _law_guard(strict=True)
    ap = argparse.ArgumentParser()
    _enable_fee_burn()           # Gate-0 fee lever: on from the first tick
    ap.add_argument("--top", type=int, default=5, help="number of carries to hold (opens)")
    ap.add_argument("--hold-top", type=int, default=60,
                    help="hysteresis: keep a carry while it still pays positive funding (wide set)")
    ap.add_argument("--capital", type=float, default=2000.0)
    ap.add_argument("--minutes", type=float, default=0.0)
    ap.add_argument("--interval", type=float, default=600.0)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--no-maker", action="store_true", help="disable maker-first execution")
    args = ap.parse_args()
    global _MAKER
    _MAKER = not args.no_maker
    dry = not args.live
    if not (spot.has_keys() and fut.has_keys()):
        raise SystemExit("need BOTH spot-testnet and futures-testnet keys")

    # single-instance lock: a fresh heartbeat means another live executor runs (no double book).
    # STAND BY rather than exit. Exiting here returned 0, and under `Restart=always/RestartSec=15`
    # systemd respawned this process every ~19s for as long as the foreign owner lived -- the
    # IDENTICAL storm the kill path hit on 2026-07-13 (14,225 restarts over 3 days) and fixed by
    # idling instead of exiting. That fix was applied to the kill exit and left standing on this
    # one; on 2026-07-26 an orphaned pre-fix executor held the heartbeat and this path storm-
    # spawned ~190 processes/hour while the fixed code never got to run. Standing by also means
    # the book is picked up automatically the moment the foreign owner dies, instead of on the
    # next storm tick. `_foreign_executor_alive` is the SAME predicate the in-loop check uses
    # (PID-aware, reclaims a legacy/unowned heartbeat), so startup and runtime can no longer
    # disagree about who owns the book.
    standby_noted = False
    while not dry and _foreign_executor_alive():
        if not standby_noted:                     # log ONCE: a per-tick log is its own noise storm
            with contextlib.suppress(OSError):
                print(f"another cash-carry executor owns the book "
                      f"({_HB.read_text('utf-8').strip()}) -- standing by, not exiting "
                      f"(single-book invariant; will take over when it stops)")
            standby_noted = True
        time.sleep(_HB_TICK)

    forever = args.minutes <= 0
    deadline = time.monotonic() + args.minutes * 60.0
    print(f"CASH-CARRY executor | {'LIVE-PAPER' if args.live else 'DRY'} | top {args.top} | "
          f"${args.capital} | hb {_HB_TICK}s | rebalance {args.interval}s")
    last_work = 0.0
    jitter = 1.0                                          # +-15% cadence jitter (anti-front-run:
    rng = random.Random()                                 # a fixed 600s beat is detectable at size)
    killed = False
    while forever or time.monotonic() < deadline:
        if not dry and _foreign_executor_alive():
            print("another live executor owns the book -- exiting (single-book "
                  "invariant)")
            return
        if not dry:                                       # fast heartbeat (decoupled from work)
            _HB.parent.mkdir(parents=True, exist_ok=True)
            # PID-owned: lets every OTHER executor detect that it no longer owns
            # the book (single-book invariant, 2026-07-26).
            _HB.write_text(f"{os.getpid()} {datetime.now(tz=UTC).isoformat()}",
                           "utf-8")
        if _PERMANENTLY_RETIRED or _KILL.exists():
            # IDLE here instead of exiting: exiting made systemd respawn every ~17s for as long
            # as the kill file stood (14k restarts after the 2026-07-13 fire), which also starved
            # the daily data flywheel that rides this loop. Close everything (idempotent -- retried
            # while any leg remains), keep the flywheel + dashboard feeds alive, resume trading
            # automatically the moment the kill file is cleared.
            if not killed:
                msg = ("RETIRED: closing all carries + idling permanently (2026-08-19)"
                       if _PERMANENTLY_RETIRED else
                       "KILL: closing all carries + idling until the kill file clears")
                print(msg)
                killed = True
            with contextlib.suppress(Exception):
                _daily_data_tasks()                       # halted book must not starve the flywheel
            try:
                rb = _rebalance(0, 0, 0.0, dry=dry)       # top=0, hold=0 -> closes everything
            except Exception as exc:
                # A venue outage/ban must not kill the KILL loop: close-all is idempotent and
                # retried every tick while any leg remains. Crashing here made systemd respawn-
                # hammer a banned endpoint every ~5min (2026-07-31 418 incident).
                print(f"KILL: close-all deferred this tick ({exc})")
                time.sleep(_HB_TICK)
                continue
            with contextlib.suppress(Exception):
                _emit(rb, _mark(rb), dry)                 # dashboard stays honest while halted
            time.sleep(_HB_TICK)
            continue
        killed = False
        # EVERY tick: mark + write feeds (cheap, keeps the dashboard live). Orders every interval.
        try:
            if time.time() - last_work >= args.interval * jitter:
                _daily_data_tasks()                       # once per UTC day: archive OI/LS/taker
                top, hold_top, capital = _live_params(args.top, args.hold_top, args.capital)
                cap = _dynamic_capital(capital)           # dynamic-leverage sized (when proven)
                rb = _rebalance(top, hold_top, cap, dry=dry)   # places orders (live-tunable params)
                last_work = time.time()
                # L1.45: the jitter that governed the cycle JUST EXECUTED is recorded before the
                # next one is drawn. This line has produced genuine exogenous variation on the
                # live path since the anti-front-run jitter was added and DISCARDED every draw --
                # unrecorded variation is noise, and recording it costs nothing.
                _EXC_CADENCE["last_jitter"] = round(jitter, 4)
                jitter = rng.uniform(0.85, 1.15)
            else:
                rb = _book_snapshot()                     # just read + mark (no orders)
            marks = _mark(rb)
            _emit(rb, marks, dry)
            if not dry:                                   # refresh the dashboard molded feed now
                with contextlib.suppress(Exception):
                    subprocess.run([sys.executable, "scripts/run_live_combined.py"],
                                   timeout=60, capture_output=True, check=False)
            print(f"[{datetime.now(UTC):%H:%M:%S}] carries={len(rb['pos'])} "
                  f"net=${marks['net_pnl']} funding=${marks['funding']} {rb['actions']}")
        except Exception as e:  # loop must survive transient errors -- but LOG them visibly
            with contextlib.suppress(Exception):
                _ERR.write_text(f"{datetime.now(tz=UTC).isoformat()} cycle error: {e!r}\n")
            print(f"cycle error (logged): {e!r}"[:200])
        if not forever and time.monotonic() >= deadline:
            break
        time.sleep(_HB_TICK)
    print("cash-carry executor done.")




# --- BNB FEE DISCOUNT (principal 2026-07-23; Gate-0 lever) -----------------------------------
# Live VIP0 fees (~20-25 bps round-trip) are the single biggest live drag on a book that turns
# over; BNB burn takes ~25% off. Maker-first is already implemented (_MAKER) -- this is the
# other, RISKLESS half, wired now so it is already ON at Gate 0 rather than a day-1 scramble.
# Best-effort + idempotent: a venue that lacks or rejects the endpoint changes nothing.
def _enable_fee_burn() -> None:
    """Switch BNB fee burn ON for futures and spot. Pure cost reduction, no risk surface."""
    with contextlib.suppress(Exception):
        fut._signed("/fapi/v1/feeBurn", {"feeBurn": "true"}, method="POST")
    with contextlib.suppress(Exception):
        spot._signed("/sapi/v1/bnbBurn", {"spotBNBBurn": "true"}, method="POST")


if __name__ == "__main__":
    main()
