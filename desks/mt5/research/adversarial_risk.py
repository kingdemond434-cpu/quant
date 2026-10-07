#!/usr/bin/env python3
"""ADVERSARIAL BATTERY FOR THE INDEPENDENT RISK CONTROLS (ARCH-05) -- poisoned optimizer, agent
and forecast output driven through the REAL decision path, with the controls asserted to hold.

    python desks/mt5/research/adversarial_risk.py          # hourly leg `adversarial_risk`
    python desks/mt5/research/adversarial_risk.py --json

WHY (PM delivery check 2026-10-07, ARCH-05). The desk has independent controls -- the heat
ceiling's second reading (`decision_core.live_heat_ceiling`), the per-trade envelope
(`MAX_RISK_FRAC`), the venue-minimum refusal (`implementable_lot`), the order door's broker
pre-check (`order_door.send`), the gateway's margin kill switch (`gateway.margin_ok`), the prop
venue's daily-loss bar (`venue_cap`) and the release interlock (`release_gate`). Nothing showed
that a MALFORMED input cannot walk past them: a NaN or infinite fraction from the optimiser, a
wrong-sign weight, a stale or corrupt allocation artifact, a symbol the desk cannot price, a lot
above the venue's volume_max, a margin call above free margin.

WHAT IT DRIVES. Only public functions, unedited, on synthetic inputs in a temp directory:
  * sizing: `promoted_lot` (book and non-book), `gold_book_lot`, `implementable_lot`;
  * the book: `book_from_allocation` -> `promoted_lot(from_book=True)`, end to end;
  * the heat ceiling: `allocator_heat` over a poisoned `pf_allocation.json`, its answer fed to
    `cap_by_heat` exactly as `gateway.cap_by_heat` feeds it, plus the prop `venue_cap`;
  * the order door: `order_door.send` against a broker double (pre-check rejects, a broken
    pre-check, a duplicate in-doubt resend);
  * the gateway's `margin_ok`, in a child process with MetaTrader5 replaced by a double before
    import and `MT5_DESK_ROOT` pointed at a temp directory (the `libs.tiers.gateway_drill`
    sandbox), so no terminal is reached and no live path is written;
  * `release_gate` on a root with no seal.

THE VERDICTS, per case:
  HELD      the poisoned input produced no exposure past the control on the live path
            (a refusal by exception counts: every live call site of a raising function is
            wrapped and skips the sleeve -- named per case in `held_by`).
  BYPASS    a poisoned input produced exposure past a control ON THE LIVE PATH. The battery's
            verdict is FAIL and the case names the fix (a patch under context/patches/, because
            these files are money path and are not edited from a research session).
  LATENT    the control breaks when its function is called DIRECTLY with an input the live path
            demonstrably cannot produce (proved by another case in this battery, named in
            `unreachable_because`). Not a bypass today; a defence-in-depth gap with its patch.
  UNMEASURED  the case could not run (sandbox failure, import error). Never a pass (L1.28a).

Writes desks/mt5/reports/ADVERSARIAL_RISK.json; `recovery_drills` grades it as the
`independent_controls` row and the acceptance drills read it for model-to-decision.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "ADVERSARIAL_RISK.json"
PATCH = "context/patches/arch05_decision_core_nonfinite.patch"

HELD, BYPASS, LATENT, UNMEASURED = "HELD", "BYPASS", "LATENT", "UNMEASURED"

#: The poisons every fraction-shaped input is driven with.
POISONS: tuple[tuple[str, Any], ...] = (
    ("nan", float("nan")), ("inf", float("inf")), ("neg_inf", float("-inf")),
    ("negative", -0.05), ("huge", 1e9), ("string", "0.05; DROP"), ("none", None),
)
EQUITY = 10_000.0
#: A live-shaped EURUSD handle: 0.00001 tick worth 0.85 EUR, so 85,000 EUR per price unit per lot.
EURUSD_INFO = SimpleNamespace(trade_tick_size=0.00001, trade_tick_value=0.85, volume_min=0.01,
                              volume_step=0.01, volume_max=100.0)
EURUSD_STOP = 0.0020
GOLD_STOP = 19.1
GOLD_INFO = SimpleNamespace(trade_tick_size=0.01, trade_tick_value=0.86, volume_min=0.01,
                            volume_step=0.01, volume_max=100.0)
#: One lot step of slack on every per-trade bound: a lot is snapped to the 0.01 grain.
LOT_STEP = 0.01


def _dc() -> Any:
    from mt5desk import decision_core
    return decision_core


def _finite(x: Any) -> bool:
    try:
        return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
    except TypeError:
        return False


def _case(cid: str, control: str, poison: str, verdict: str, why: str,
          **kw: Any) -> dict[str, Any]:
    return {"case": cid, "control": control, "poison": poison, "verdict": verdict,
            "why": why, **kw}


def _run(cid: str, control: str, poison: str,
         fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """One case; a battery that breaks is an UNMEASURED case, never a pass."""
    try:
        return fn()
    except Exception as exc:
        return _case(cid, control, poison, UNMEASURED,
                     f"case raised {type(exc).__name__}: {exc}"[:300])


# ------------------------------------------------------------------------------- sizing
def _risk_eur(lot: float, stop: float, info: Any) -> float:
    return float(lot) * stop * float(info.trade_tick_value) / float(info.trade_tick_size)


def _per_trade_bound(stop: float, info: Any) -> float:
    """The most one trade may risk: MAX_RISK_FRAC of equity, plus one lot step of grain."""
    from mt5desk.sizing import MAX_RISK_FRAC
    return MAX_RISK_FRAC * EQUITY + _risk_eur(LOT_STEP, stop, info)


def _sizing_cases() -> list[dict[str, Any]]:
    dc = _dc()
    sovereign = bool(dc.allocator_sovereign())
    out: list[dict[str, Any]] = []
    for pname, val in POISONS:
        # 1. the allocator's own fraction for a non-gold sleeve (the optimiser's output)
        def book(pname: str = pname, val: Any = val) -> dict[str, Any]:
            cid = f"book_fraction_{pname}"
            ctl = "per-trade envelope (MAX_RISK_FRAC) + venue-minimum refusal"
            try:
                lot = dc.promoted_lot(EQUITY, 0, EURUSD_STOP, "EURUSD", EURUSD_INFO, val,
                                      None, from_book=True)
            except Exception as exc:
                return _case(cid, ctl, pname, HELD, f"refused by {type(exc).__name__}",
                             held_by="gateway place_family_sleeve wraps promoted_lot and "
                                     "skips the sleeve as 'unpriceable'")
            risk = _risk_eur(lot, EURUSD_STOP, EURUSD_INFO) if _finite(lot) else math.inf
            bound = _per_trade_bound(EURUSD_STOP, EURUSD_INFO)
            # inf and huge are POSITIVE: the envelope must clamp them. NaN, <= 0 and non-numbers
            # are not a size at all, and a sovereign allocator must send nothing for them.
            nonpos = not (isinstance(val, (int, float)) and not isinstance(val, bool)
                          and float(val) > 0)
            if not _finite(lot) or lot < 0 or lot > 5.0 + 1e-9 or risk > bound + 1e-6:
                return _case(cid, ctl, pname, BYPASS,
                             f"lot {lot} risks {risk:.2f} EUR against a {bound:.2f} bound",
                             lot=lot, fix=PATCH)
            if sovereign and nonpos and lot > 0:
                return _case(cid, ctl, pname, BYPASS,
                             f"a non-positive/non-numeric fraction sized {lot} lots while the "
                             "allocator is sovereign (zero must send nothing)", lot=lot,
                             fix=PATCH)
            return _case(cid, ctl, pname, HELD,
                         f"lot {lot} risks {risk:.2f} EUR <= {bound:.2f} "
                         f"({'no order' if lot == 0 else 'clamped to the envelope'})", lot=lot)
        out.append(_run(f"book_fraction_{pname}", "per-trade envelope", pname, book))

        # 2. the same fraction on the gold book (the one book that has ever traded live)
        def gold(pname: str = pname, val: Any = val) -> dict[str, Any]:
            cid = f"gold_fraction_{pname}"
            ctl = "per-trade envelope on the gold book"
            try:
                lot, basis = dc.gold_book_lot(EQUITY, GOLD_STOP, GOLD_INFO, val)
            except Exception as exc:
                return _case(cid, ctl, pname, HELD, f"refused by {type(exc).__name__}",
                             held_by="gateway gold placement wraps the sizer")
            risk = _risk_eur(lot, GOLD_STOP, GOLD_INFO) if _finite(lot) else math.inf
            bound = _per_trade_bound(GOLD_STOP, GOLD_INFO)
            if not _finite(lot) or lot < 0 or risk > bound + 1e-6:
                return _case(cid, ctl, pname, BYPASS,
                             f"gold lot {lot} risks {risk:.2f} EUR against {bound:.2f}",
                             lot=lot, basis=basis, fix=PATCH)
            note = None
            if not _finite(val) and lot > 0 and "not a number" in str(basis):
                note = ("a non-numeric allocator fraction falls back to the gold POLICY lot "
                        "(Q_OPT), not to zero; bounded by the envelope and named in the basis")
            return _case(cid, ctl, pname, HELD,
                         f"gold lot {lot} risks {risk:.2f} EUR <= {bound:.2f}: {basis}",
                         lot=lot, note=note)
        out.append(_run(f"gold_fraction_{pname}", "per-trade envelope", pname, gold))

        # 3. the promoter's risk_frac on a non-book sleeve (agent output, not the optimiser's)
        def promoted(pname: str = pname, val: Any = val) -> dict[str, Any]:
            cid = f"promoter_fraction_{pname}"
            ctl = "clamp_risk_frac ladder [BASE, MAX] x authority ramp"
            try:
                lot = dc.promoted_lot(EQUITY, 0, EURUSD_STOP, "EURUSD", EURUSD_INFO, val, None,
                                      from_book=False)
            except Exception as exc:
                return _case(cid, ctl, pname, HELD, f"refused by {type(exc).__name__}: {exc}",
                             held_by="gateway place_family_sleeve wraps promoted_lot and "
                                     "skips the sleeve as 'unpriceable'")
            risk = _risk_eur(lot, EURUSD_STOP, EURUSD_INFO) if _finite(lot) else math.inf
            bound = _per_trade_bound(EURUSD_STOP, EURUSD_INFO)
            if not _finite(lot) or lot < 0 or risk > bound + 1e-6:
                return _case(cid, ctl, pname, BYPASS, f"lot {lot} risks {risk:.2f} EUR",
                             lot=lot, fix=PATCH)
            return _case(cid, ctl, pname, HELD,
                         f"lot {lot} risks {risk:.2f} EUR <= {bound:.2f} (junk falls to the "
                         "documented base fraction, ramped)", lot=lot)
        out.append(_run(f"promoter_fraction_{pname}", "risk ladder", pname, promoted))

    def unknown_symbol() -> dict[str, Any]:
        ctl = "risk_units: an unpriceable instrument is refused, never sized from gold"
        try:
            lot = dc.promoted_lot(EQUITY, 0, 0.5, "ZZZ_NOT_IN_UNIVERSE", None, 0.05, None,
                                  from_book=True)
        except Exception as exc:
            return _case("unknown_symbol_sizing", ctl, "symbol not in universe", HELD,
                         f"refused by {type(exc).__name__}",
                         held_by="gateway skips the sleeve as 'unpriceable'")
        return _case("unknown_symbol_sizing", ctl, "symbol not in universe",
                     BYPASS if lot > 0 else HELD, f"sized {lot} lots for an unknown symbol",
                     lot=lot, fix=PATCH if lot > 0 else None)
    out.append(_run("unknown_symbol_sizing", "risk_units", "symbol not in universe",
                    unknown_symbol))

    def unknown_symbol_heat() -> dict[str, Any]:
        ctl = "cap_by_heat charges an unpriceable leg at the most expensive measured one"
        sleeves = [{"name": "known", "symbol": "EURUSD", "q_charge": 0.04},
                   {"name": "alien", "symbol": "ZZZ_NOT_IN_UNIVERSE", "dist": 0.5}]
        admitted, note = dc.cap_by_heat(sleeves, EQUITY, allocation=(0.05, "battery"))
        names = [s["name"] for s in admitted]
        # billed 0.04 (the most expensive measured leg), so both cannot fit in 0.05 + slide
        ok = len(names) < 2
        return _case("unknown_symbol_heat", ctl, "symbol not in universe",
                     HELD if ok else BYPASS,
                     f"admitted {names}: the alien leg was billed at the dearest known leg"
                     if ok else f"an unpriceable leg rode free: admitted {names} ({note})",
                     admitted=names, fix=None if ok else PATCH)
    out.append(_run("unknown_symbol_heat", "cap_by_heat", "symbol not in universe",
                    unknown_symbol_heat))

    def volume_max() -> dict[str, Any]:
        ctl = "implementable_lot: the desk's own lot snap and per-order ceiling"
        info = SimpleNamespace(**{**vars(EURUSD_INFO), "volume_max": 1.0})
        lot = dc.implementable_lot(50.0, "EURUSD", info)
        if lot > float(info.volume_max) + 1e-9:
            return _case("volume_max_desk_side", ctl, "lot above volume_max", LATENT,
                         f"implementable_lot returned {lot} for a symbol whose volume_max is "
                         f"{info.volume_max}: the desk does not read volume_max, the venue does",
                         unreachable_because="order_door_volume_max_* cases: the broker "
                                             "pre-check refuses it, and a broken pre-check "
                                             "leaves the venue's own refusal",
                         lot=lot, fix=PATCH)
        return _case("volume_max_desk_side", ctl, "lot above volume_max", HELD,
                     f"implementable_lot returned {lot} <= volume_max {info.volume_max}")
    out.append(_run("volume_max_desk_side", "implementable_lot", "lot above volume_max",
                    volume_max))
    return out


# ---------------------------------------------------------------------- the optimiser's book
def _book_cases() -> list[dict[str, Any]]:
    dc = _dc()
    out: list[dict[str, Any]] = []
    total = 0.20
    for pname, val in POISONS:
        def one(pname: str = pname, val: Any = val) -> dict[str, Any]:
            cid = f"book_weight_{pname}"
            ctl = "book_from_allocation -> promoted_lot(from_book=True), end to end"
            book = {"poisoned": val, "honest": 0.10, "other": 0.10}
            res, why = dc.book_from_allocation(total, book, None, certified=True,
                                               why="battery")
            if res is None:
                return _case(cid, ctl, pname, HELD, f"book refused: {why}")
            weights = list(res.values())
            layer_ok = all(_finite(w) and w >= 0 for w in weights) and \
                sum(weights) <= total + 0.005
            risk = 0.0
            for w in weights:
                try:
                    lot = dc.promoted_lot(EQUITY, 0, EURUSD_STOP, "EURUSD", EURUSD_INFO, w,
                                          None, from_book=True)
                except Exception:
                    lot = 0.0
                risk += _risk_eur(lot, EURUSD_STOP, EURUSD_INFO)
            # end to end: the book may deploy its total plus one lot step per leg, never more
            e2e_bound = total * EQUITY + len(weights) * _risk_eur(LOT_STEP, EURUSD_STOP,
                                                                    EURUSD_INFO)
            if risk > e2e_bound + 1e-6:
                return _case(cid, ctl, pname, BYPASS,
                             f"the book deployed {risk:.2f} EUR against {e2e_bound:.2f}: {res}",
                             fix=PATCH)
            if not layer_ok:
                return _case(cid, ctl, pname, LATENT,
                             f"book_from_allocation returned {res} ('{why[:80]}'), a non-finite "
                             "or over-budget weight reported as authoritative; the sizer turned "
                             f"it into {risk:.2f} EUR of risk (<= {e2e_bound:.2f})",
                             unreachable_because="promoted_lot(from_book=True) sizes a "
                                                 "non-finite fraction at zero in sovereign mode",
                             book=dict(res), fix=PATCH)
            return _case(cid, ctl, pname, HELD,
                         f"book {({k: round(v, 4) for k, v in res.items()})} deployed "
                         f"{risk:.2f} EUR <= {e2e_bound:.2f}")
        out.append(_run(f"book_weight_{pname}", "book_from_allocation", pname, one))
    return out


# ---------------------------------------------------------------------- the heat ceiling
@contextlib.contextmanager
def _allocation_base(heat: dict[str, Any] | None, *, armed: bool = True, age_s: float = 0.0,
                     growth: Any = 12.0, raw: str | None = None) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="adv_risk_") as tmp:
        base = Path(tmp)
        (base / "data").mkdir()
        (base / "reports").mkdir()
        if armed:
            (base / "data" / "PF_ALLOCATOR_ARMED").write_text("battery", "utf-8")
        f = base / "reports" / "pf_allocation.json"
        if raw is not None:
            f.write_text(raw, "utf-8")
        else:
            doc = {"heat": heat or {}, "growth": {"annual_growth_pct": growth},
                   "marginal_delta_elog": {"s0": 0.1}}
            f.write_text(json.dumps(doc), "utf-8")      # json writes NaN/Infinity tokens
        if age_s:
            t = time.time() - age_s
            os.utime(f, (t, t))
        yield base


def _heat(total: Any, operative: Any = 0.25, status: str = "MEASURED",
          certified: bool = True) -> dict[str, Any]:
    return {"total": total, "certified": certified,
            "envelope": {"operative_ceiling": operative,
                         "survival": {"status": status, "why": "battery"}}}


HEAT_POISONS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("total_nan", {"heat": _heat(float("nan"))}),
    ("total_inf", {"heat": _heat(float("inf"))}),
    ("total_negative", {"heat": _heat(-0.10)}),
    ("total_huge", {"heat": _heat(1e9)}),
    ("total_string", {"heat": _heat("0.25")}),
    ("ceiling_nan", {"heat": _heat(0.45, float("nan"))}),
    ("ceiling_inf", {"heat": _heat(0.45, float("inf"))}),
    ("ceiling_negative", {"heat": _heat(0.45, -1.0)}),
    ("ceiling_above_sim_max", {"heat": _heat(5.0, 50.0)}),
    ("survival_unmeasured", {"heat": _heat(0.90, 0.90, status="UNMEASURED")}),
    ("uncertified", {"heat": _heat(0.25, certified=False)}),
    ("growth_neg_inf", {"heat": _heat(0.25), "growth": float("-inf")}),
    ("growth_nan", {"heat": _heat(0.25), "growth": float("nan")}),
    ("stale_forecast", {"heat": _heat(0.28), "age_s": 7200.0}),
    ("unarmed", {"heat": _heat(0.28), "armed": False}),
    ("corrupt_json", {"raw": "{\"heat\": {\"total\": 0.3, "}),
)


def _heat_cases() -> list[dict[str, Any]]:
    dc = _dc()
    out: list[dict[str, Any]] = []
    sleeves = [{"name": f"s{i}", "symbol": "EURUSD", "q_charge": 0.02} for i in range(60)]
    for pname, spec in HEAT_POISONS:
        def one(pname: str = pname, spec: dict[str, Any] = spec) -> dict[str, Any]:
            cid = f"heat_{pname}"
            ctl = "allocator_heat (live_heat_ceiling second reading) -> cap_by_heat"
            with _allocation_base(spec.get("heat"), armed=spec.get("armed", True),
                                  age_s=float(spec.get("age_s", 0.0)),
                                  growth=spec.get("growth", 12.0), raw=spec.get("raw")) as base:
                budget, why = dc.allocator_heat(base)
                rank = dc.allocator_rank(base)
            # The ceiling this artifact may claim: the recorded bar unless survival MEASURED a
            # finite operative ceiling, and never above the simulation bound.
            env = ((spec.get("heat") or {}).get("envelope") or {})
            op = env.get("operative_ceiling")
            measured = (env.get("survival") or {}).get("status") == "MEASURED" and _finite(op) \
                and float(op) > 0
            bar = min(float(op), dc.ABSOLUTE_SIM_MAX) if measured else float(dc.MAX_HEAT_CEILING)
            if budget is not None and (not _finite(budget) or budget <= 0
                                       or budget > bar + 1e-9):
                return _case(cid, ctl, pname, BYPASS,
                             f"allocator_heat returned {budget!r} against the {bar:.2%} bar "
                             f"({why})", fix=PATCH)
            admitted, note = dc.cap_by_heat(sleeves, EQUITY, allocation=(budget, why),
                                            rank=rank)
            used = 0.02 * len(admitted)
            ceiling = max(float(dc.MAX_HEAT_CEILING), budget or 0.0) + dc.HEAT_SLIDE
            if used > ceiling + 1e-9:
                return _case(cid, ctl, pname, BYPASS,
                             f"cap_by_heat admitted {used:.2%} past {ceiling:.2%}", fix=PATCH)
            stale = pname == "stale_forecast"
            if stale and (budget is not None or rank is not None):
                return _case(cid, ctl, pname, BYPASS,
                             "a stale allocation was still believed "
                             f"(budget {budget}, rank {rank is not None})", fix=PATCH)
            note = None
            if measured and bar > float(dc.MAX_HEAT_CEILING):
                # Not a bypass of any control the code declares, and NOT a cap proposal: the
                # bar above 30% is the allocator's OWN survival measurement, bounded only by
                # ABSOLUTE_SIM_MAX. That is the open MI05 blocker `risk_not_independent`, a
                # principal decision under growth governance; the battery records it, it does
                # not decide it.
                note = (f"a survival envelope the artifact itself reports as MEASURED authorises "
                        f"{bar:.0%}; the only bound is ABSOLUTE_SIM_MAX "
                        "(MI05 blocker risk_not_independent)")
            return _case(cid, ctl, pname, HELD,
                         (f"budget {'refused' if budget is None else f'{budget:.2%}'} "
                          f"({why[:90]}); book admitted {used:.2%} <= {ceiling:.2%}"),
                         budget=budget, admitted_heat=round(used, 4), note=note)
        out.append(_run(f"heat_{pname}", "allocator_heat", pname, one))

    for pname, val in (("nan", float("nan")), ("inf", float("inf"))):
        def direct(pname: str = pname, val: float = val) -> dict[str, Any]:
            cid = f"cap_by_heat_direct_{pname}"
            ctl = "cap_by_heat handed a non-finite budget directly"
            admitted, _ = dc.cap_by_heat(sleeves, EQUITY, allocation=(val, "battery"))
            used = 0.02 * len(admitted)
            ceiling = float(dc.MAX_HEAT_CEILING) + dc.HEAT_SLIDE
            if used > ceiling + 1e-9:
                return _case(cid, ctl, pname, LATENT,
                             f"a {pname} budget admitted {used:.0%} of heat: cap_by_heat "
                             "trusts its allocation tuple to be finite",
                             unreachable_because="every heat_* case: allocator_heat, the only "
                                                 "producer of that tuple on the live path, "
                                                 "never returns a non-finite budget",
                             admitted_heat=round(used, 4), fix=PATCH)
            return _case(cid, ctl, pname, HELD, f"admitted {used:.2%} <= {ceiling:.2%}")
        out.append(_run(f"cap_by_heat_direct_{pname}", "cap_by_heat", pname, direct))

    # THE LOSS LIMIT: a prop venue's daily-loss bar over a huge allocation, and a poisoned bar.
    def venue_bar() -> dict[str, Any]:
        admitted, note = dc.cap_by_heat(sleeves, EQUITY, allocation=(0.30, "battery"),
                                        venue_cap=(0.04, "prop daily-loss bar"))
        used = 0.02 * len(admitted)
        return _case("venue_loss_bar", "venue daily-loss bar (account_profile.venue_heat_cap)",
                     "allocation far above the venue bar",
                     HELD if used <= 0.04 + 1e-9 else BYPASS,
                     f"admitted {used:.2%} under a 4% venue bar ({(note or '')[:80]})",
                     fix=None if used <= 0.04 + 1e-9 else PATCH)
    out.append(_run("venue_loss_bar", "venue_cap", "huge allocation", venue_bar))

    def venue_bar_nan() -> dict[str, Any]:
        admitted, _ = dc.cap_by_heat(sleeves, EQUITY, allocation=(0.30, "battery"),
                                     venue_cap=(float("nan"), "poisoned"))
        used = 0.02 * len(admitted)
        if used > 0:
            return _case("venue_loss_bar_nan", "venue daily-loss bar", "nan venue bar", LATENT,
                         f"a NaN venue bar is ignored (`nan < limit` is False) and the book "
                         f"took {used:.2%}; a declared prop account with an unreadable bar "
                         "should open nothing",
                         unreachable_because="account_profile.venue_heat_cap derives the bar "
                                             "from a declared finite daily_loss_limit; no "
                                             "account is declared on this desk",
                         admitted_heat=round(used, 4), fix=PATCH)
        return _case("venue_loss_bar_nan", "venue daily-loss bar", "nan venue bar", HELD,
                     "a NaN venue bar admits nothing")
    out.append(_run("venue_loss_bar_nan", "venue_cap", "nan venue bar", venue_bar_nan))

    def poisoned_charge() -> dict[str, Any]:
        legs = [{"name": f"p{i}", "symbol": "EURUSD", "dist": EURUSD_STOP,
                 "q_charge": v} for i, v in enumerate(
                     [float("nan"), -0.5, float("-inf"), float("inf")] * 15)]
        admitted, _ = dc.cap_by_heat(legs, EQUITY, allocation=(0.20, "battery"))
        honest = sum(dc.realised_q(EQUITY, EURUSD_STOP, "EURUSD", EURUSD_INFO)
                     for _ in admitted)
        limit = 0.20 + dc.HEAT_SLIDE
        ok = honest <= limit + 1e-6
        return _case("poisoned_q_charge", "cap_by_heat per-leg charge",
                     "nan/negative/inf q_charge", HELD if ok else BYPASS,
                     f"{len(admitted)} legs admitted at an honest {honest:.2%} vs {limit:.2%}: "
                     "a poisoned charge is re-priced from the leg's own stop",
                     fix=None if ok else PATCH)
    out.append(_run("poisoned_q_charge", "cap_by_heat", "poisoned q_charge", poisoned_charge))
    return out


# ---------------------------------------------------------------------- the order door
class _Broker:
    """The broker double for the door: `order_check` answers `check`, `order_send` answers
    `send` (an int retcode, or None), and every send is recorded."""

    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_MODIFY = 7
    TRADE_ACTION_REMOVE = 8
    TRADE_ACTION_CLOSE_BY = 10
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_BUY_STOP = 4

    def __init__(self, check: int | None | str = 0, send: int | None = 10009,
                 lands: bool = False) -> None:
        self.check, self.send, self.lands = check, send, lands
        self.sent: list[dict[str, Any]] = []
        self.orders: list[SimpleNamespace] = []

    def order_check(self, req: dict[str, Any]) -> Any:
        if self.check == "missing":
            raise AttributeError("order_check")
        if self.check is None:
            return None
        vol = req.get("volume")
        rc = self.check
        if not _finite(vol) or float(vol) <= 0:
            rc = 10014
        return SimpleNamespace(retcode=rc, comment={10014: "Invalid volume",
                                                    10019: "No money"}.get(int(rc), "ok"))

    def order_send(self, req: dict[str, Any]) -> Any:
        self.sent.append(dict(req))
        if self.lands:
            self.orders.append(SimpleNamespace(
                ticket=7000 + len(self.sent), symbol=req.get("symbol"),
                volume_initial=req.get("volume"), price_open=req.get("price"),
                type=req.get("type"), magic=req.get("magic"), comment=req.get("comment"),
                time_setup=int(time.time())))
        if self.send is None:
            return None
        ok = self.send in (10008, 10009)
        return SimpleNamespace(retcode=self.send, order=7000 + len(self.sent) if ok else 0,
                               deal=0, volume=req.get("volume"), price=req.get("price"),
                               comment="double")

    def orders_get(self, **_: Any) -> tuple[SimpleNamespace, ...]:
        return tuple(self.orders)

    def positions_get(self, **_: Any) -> tuple[()]:
        return ()

    def history_deals_get(self, *_: Any, **__: Any) -> tuple[()]:
        return ()

    def history_orders_get(self, *_: Any, **__: Any) -> tuple[()]:
        return ()

    def last_error(self) -> tuple[int, str]:
        return (-10005, "IPC timeout")


def _request(volume: Any = 0.10) -> dict[str, Any]:
    return {"action": 5, "symbol": "EURUSD", "volume": volume, "type": 4, "price": 1.1000,
            "sl": 1.0980, "tp": 1.1040, "magic": 341953, "comment": "DWbattery"}


@contextlib.contextmanager
def _door_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="adv_door_") as tmp:
        prev = os.environ.get("MT5_ORDER_DOOR_DIR")
        os.environ["MT5_ORDER_DOOR_DIR"] = tmp
        try:
            yield Path(tmp)
        finally:
            if prev is None:
                os.environ.pop("MT5_ORDER_DOOR_DIR", None)
            else:
                os.environ["MT5_ORDER_DOOR_DIR"] = prev


def _door_cases() -> list[dict[str, Any]]:
    from mt5desk import order_door as door
    out: list[dict[str, Any]] = []
    quiet: Callable[[str], None] = lambda _m: None  # noqa: E731

    def refused(cid: str, poison: str, check: int, volume: Any = 0.10) -> dict[str, Any]:
        ctl = "order_door broker pre-check"
        with _door_dir() as d:
            b = _Broker(check=check)
            res = door.send(b, _request(volume), caller="battery", log=quiet)
            rows = door.read_ledger(d / door.LEDGER_NAME)
        ok = bool(getattr(res, "door_refused", False)) and not b.sent
        return _case(cid, ctl, poison, HELD if ok else BYPASS,
                     (f"refused before order_send ({getattr(res, 'door_reason', None)}, "
                      f"retcode {getattr(res, 'retcode', None)}); ledgered {len(rows)} row")
                     if ok else f"{len(b.sent)} order(s) reached the venue", fix=None if ok
                     else PATCH)

    out.append(_run("order_door_volume_max_checked", "order_door", "lot above volume_max",
                    lambda: refused("order_door_volume_max_checked", "lot above volume_max",
                                    10014, 50.0)))
    out.append(_run("order_door_margin_checked", "order_door", "margin above free margin",
                    lambda: refused("order_door_margin_checked", "margin above free margin",
                                    10019)))
    out.append(_run("order_door_nan_volume", "order_door", "nan volume",
                    lambda: refused("order_door_nan_volume", "nan volume", 0, float("nan"))))

    def fail_open(cid: str, poison: str, venue_rc: int) -> dict[str, Any]:
        ctl = "order_door with a broken pre-check (CHECK_FAIL_OPEN) -> the venue's refusal"
        with _door_dir() as d:
            b = _Broker(check=None, send=venue_rc)
            res = door.send(b, _request(50.0), caller="battery", log=quiet)
            rows = door.read_ledger(d / door.LEDGER_NAME)
        verdict, _notes = door.validate(door.OPEN, _request(50.0), res)
        row = rows[-1] if rows else {}
        ok = len(b.sent) == 1 and verdict == "rejected" and bool(row.get("check_fail_open"))
        return _case(cid, ctl, poison, HELD if ok else BYPASS,
                     ("the pre-check was unmeasured, the order went once to the venue, which "
                      f"refused it (retcode {venue_rc}); validated '{verdict}' and ledgered "
                      "with check_fail_open -- the venue is the last control here, by the "
                      "door's documented design") if ok else
                     f"sends={len(b.sent)} validation={verdict} ledger={row}",
                     held_by="venue (order_door.CHECK_FAIL_OPEN)", venue_only=True,
                     fix=None if ok else PATCH)

    out.append(_run("order_door_volume_max_fail_open", "order_door", "lot above volume_max",
                    lambda: fail_open("order_door_volume_max_fail_open",
                                      "lot above volume_max, pre-check broken", 10014)))
    out.append(_run("order_door_margin_fail_open", "order_door", "margin above free margin",
                    lambda: fail_open("order_door_margin_fail_open",
                                      "margin above free margin, pre-check broken", 10019)))

    def duplicate() -> dict[str, Any]:
        ctl = "order_door in-doubt guard (operational: no duplicate execution)"
        with _door_dir():
            b = _Broker(check=0, send=None, lands=True)
            first = door.send(b, _request(), caller="battery", log=quiet)
            second = door.send(b, _request(), caller="battery", log=quiet)
        ok = first is None and len(b.sent) == 1 and \
            getattr(second, "door_reason", None) == "duplicate_of_in_doubt"
        return _case("order_door_duplicate_resend", ctl, "identical resend after a lost ack",
                     HELD if ok else BYPASS,
                     "the resend was refused as a duplicate of the in-doubt attempt the venue "
                     "shows landed" if ok else
                     f"sends={len(b.sent)} second={getattr(second, 'door_reason', second)}",
                     fix=None if ok else PATCH)
    out.append(_run("order_door_duplicate_resend", "order_door", "duplicate", duplicate))
    return out


# ---------------------------------------------------------------------- gateway margin + release
_MARGIN_CHILD = r'''
import json, sys, types
from types import SimpleNamespace as NS
cases = json.loads(sys.argv[1])
state = {"free": 0.0, "need": 0.0}
m = types.ModuleType("MetaTrader5")
m.__getattr__ = lambda name: (1000 + sum(map(ord, name)) % 5000) if name.isupper() else (
    (_ for _ in ()).throw(AttributeError(name)))
m.account_info = lambda: NS(login=1, equity=1000.0, balance=1000.0,
                            margin_free=state["free"], currency="EUR", server="sandbox")
m.order_calc_margin = lambda *a: state["need"]
m.order_send = lambda req: (_ for _ in ()).throw(RuntimeError("battery: no order may be sent"))
for name in ("terminal_info", "initialize", "symbol_info_tick", "symbol_info", "orders_get",
             "positions_get", "last_error"):
    setattr(m, name, lambda *a, **k: None)
sys.modules["MetaTrader5"] = m
sys.path.insert(0, sys.argv[2]); sys.path.insert(0, sys.argv[3])
out = {}
try:
    from mt5desk import gateway
    out["root"] = str(gateway.BASE)
    out["new_risk_ok_at_import"] = bool(gateway.NEW_RISK_OK)
    for c in cases:
        state["free"] = c["free"]; state["need"] = c["need"]
        out[c["id"]] = bool(gateway.margin_ok("EURUSD", 50.0, 1.1))
except Exception as exc:
    out["import_exc"] = f"{type(exc).__name__}: {exc}"
print("ADV_JSON " + json.dumps(out))
'''

MARGIN_CASES: tuple[tuple[str, Any, Any, bool], ...] = (
    # (id, free margin, margin the order needs, the answer the control must give)
    ("margin_above_free", 100.0, 500.0, False),
    ("margin_at_95pct_of_free", 100.0, 95.0, False),
    ("margin_free_nan", float("nan"), 10.0, False),
    ("margin_free_negative", -5.0, 1.0, False),
    ("margin_need_nan", 1000.0, float("nan"), False),
    ("margin_need_inf", 1000.0, float("inf"), False),
    ("margin_within", 1000.0, 10.0, True),
)


def _gateway_cases() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="adv_gw_") as tmp:
        root = Path(tmp)
        (root / "data").mkdir()
        (root / "logs").mkdir()
        env = {**os.environ, "MT5_DESK_ROOT": str(root), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": os.pathsep.join([str(ROOT), str(DESK)])}
        payload = json.dumps([{"id": i, "free": f, "need": n} for i, f, n, _ in MARGIN_CASES])
        try:
            proc = subprocess.run([sys.executable, "-c", _MARGIN_CHILD, payload, str(DESK),
                                   str(ROOT)], capture_output=True, text=True, timeout=90,
                                  env=env, cwd=str(root))
            line = next((x for x in proc.stdout.splitlines() if x.startswith("ADV_JSON ")), "")
            obs: dict[str, Any] = json.loads(line[len("ADV_JSON "):]) if line else {
                "import_exc": f"no result (rc={proc.returncode}) {proc.stderr[-300:]}"}
        except subprocess.TimeoutExpired:
            obs = {"import_exc": "timed out"}
    sandboxed = "adv_gw_" in str(obs.get("root", ""))
    for cid, free, need, want in MARGIN_CASES:
        ctl = "gateway.margin_ok (machine kill switch, 0.9 x free margin)"
        poison = f"free={free} need={need}"
        if obs.get("import_exc") or not sandboxed:
            out.append(_case(cid, ctl, poison, UNMEASURED,
                             f"gateway sandbox unavailable: {obs.get('import_exc') or 'root '}"
                             f"{'' if sandboxed else obs.get('root')}"))
            continue
        got = obs.get(cid)
        ok = got is want
        out.append(_case(cid, ctl, poison, HELD if ok else BYPASS,
                         f"margin_ok answered {got} (must be {want})", fix=None if ok
                         else PATCH))
    if not obs.get("import_exc") and sandboxed:
        ok = obs.get("new_risk_ok_at_import") is False
        out.append(_case("release_interlock_default", "gateway.NEW_RISK_OK before the first "
                         "release check", "fresh process", HELD if ok else BYPASS,
                         f"NEW_RISK_OK at import = {obs.get('new_risk_ok_at_import')}"))
    out.append(_case("margin_need_unreadable", "gateway.margin_ok", "order_calc_margin None",
                     HELD, "margin_ok answers True when the terminal cannot compute the margin "
                           "('let broker decide'); the door's order_check and then the venue "
                           "refuse an order above free margin (order_door_margin_* cases)",
                     held_by="order_door pre-check, then the venue", venue_only=True))

    def unsealed() -> dict[str, Any]:
        from mt5desk import decision_core as dc
        with tempfile.TemporaryDirectory(prefix="adv_rel_") as tmp:
            ok, why = dc.release_gate(Path(tmp))
        return _case("release_gate_unsealed", "decision_core.release_gate", "no seal",
                     HELD if ok is False else BYPASS, f"release_gate -> {ok}: {why[:120]}")
    out.append(_run("release_gate_unsealed", "release_gate", "no seal", unsealed))
    return out


# ---------------------------------------------------------------------- the report
def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    t0 = time.perf_counter()
    cases: list[dict[str, Any]] = []
    for fam in (_sizing_cases, _book_cases, _heat_cases, _door_cases, _gateway_cases):
        try:
            cases.extend(fam())
        except Exception as exc:          # a family that cannot start is unmeasured, not passed
            cases.append(_case(fam.__name__.strip("_"), fam.__name__, "family", UNMEASURED,
                               f"{type(exc).__name__}: {exc}"[:300]))
    counts = {k: sum(1 for c in cases if c["verdict"] == k)
              for k in (HELD, BYPASS, LATENT, UNMEASURED)}
    verdict = ("FAIL" if counts[BYPASS] else "UNMEASURED" if counts[UNMEASURED] or not cases
               else "PASS")
    poisons = sorted({str(c["poison"]) for c in cases})
    return {
        "generated_utc": now.isoformat(timespec="seconds"),
        "verdict": verdict, "status": verdict, "counts": counts, "n": len(cases),
        "completed_work": len(cases) - counts[UNMEASURED],
        "bypasses": [c["case"] for c in cases if c["verdict"] == BYPASS],
        "latent": [{"case": c["case"], "why": c["why"],
                    "unreachable_because": c.get("unreachable_because"), "fix": c.get("fix")}
                   for c in cases if c["verdict"] == LATENT],
        "venue_only": [c["case"] for c in cases if c.get("venue_only")],
        "poisons": poisons, "cases": cases,
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "patch": PATCH,
        "rule": "HELD only when the live path produced no exposure past the control; BYPASS is "
                "a live-path breach (FAIL); LATENT is a control that breaks only on an input "
                "the live path is shown not to produce, with its patch; UNMEASURED is never a "
                "pass",
        "valid_until": (now + timedelta(hours=3)).isoformat(timespec="seconds"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, OUT)
    if a.json:
        print(json.dumps(doc, default=str))
    else:
        print(f"adversarial_risk: {doc['verdict']} {doc['counts']} in {doc['elapsed_s']}s")
        for c in doc["cases"]:
            if c["verdict"] != HELD:
                print(f"  {c['verdict']:<10} {c['case']:<34} {c['why'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
