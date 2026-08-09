"""IDLE CAPITAL PRICING (L1.51) -- the single leaf that owns what an undeployed dollar forgoes.

WHY THIS MODULE EXISTS. This desk prices what its capital LOSES and has never once priced what
its capital FAILS TO EARN while doing nothing. Every meter here is trade-driven: no fills means no
TCA row, no drawdown, no fee line, no P&L. A flat book therefore generates no evidence of its own
flatness, and `data/fee_burn_window.json` is the proof -- 15 samples across all of 2026-08-05, all
identical (funding 113.06, commission 1750.88). Nothing changes, so nothing alarms.

THE DEFECT THAT MADE IT URGENT, measured 2026-08-05. L1.28a's own fence
(`scripts/check_utilisation.py`) reported the capital ceiling as `utilisation 1.0, SATURATED`
while `web/cashcarry_live.json` held `n_carries: 0, deployed_notional: 0.0`. `_capital()` passed
`live_book_usd()` as the numerator and `_desk_equity_usd()` as the denominator, and
`live_book_usd()` IS the first rung inside `_desk_equity_usd()` -- so the ratio was identically
1.0 BY CONSTRUCTION, not by coincidence. The desk's only idleness law was fenced by a gate
structurally incapable of reporting idleness (L1.43, the welded gate).

ONE DEFINITION, NO PER-CALLER COPIES. This is the `capacity_policy.py` pattern and it is here for
the same reason: the moment two callers each carry their own idea of "what the book is" they
drift, and the drift is invisible because both look reasonable. `check_utilisation._capital()` and
`check_idle_cost.py` both read `book_state()` and neither owns a private copy.

THE THREE TRAPS THIS MODULE EXISTS TO NOT FALL INTO
  1. `hurdle_rate.json:risk_free` IS A PERIOD RETURN, NOT AN ANNUAL RATE. It is written as
     `rf_annual * (days / 365.0)` (scripts/hurdle_rate.py:68). Reading the stored 0.0034663 as
     an annual rate understates the true 3.73%/yr by 10.8x -- and it would understate it SILENTLY,
     in the conservative direction, which is the one direction no fence here catches because a
     too-small idle cost raises no alarm. De-annualise or do not use the field.
  2. A MOLDED CURVE IS NOT A BALANCE. `molded_curve_usd` carries its own `_note`: "a
     MOLDED/SIMULATED curve, not venue truth and not a track record". All 13 attestation rows are
     `mode: "PAPER (testnet) -- pre-Gate-0"`. Computing a dollar cost from a simulated denominator
     is exactly what welded the incumbent fence, so this module REFUSES rather than returning a
     number that would look like a measurement.
  3. THE HAIRCUT DECIDES THE VERDICT, SO IT IS PUBLISHED, NEVER BURIED. See below.

WHAT THE FIRST MEASUREMENT ACTUALLY SAID, AND WHY THE HEADLINE IS A NEGATIVE RESULT. The
capability was proposed on the premise of a "reachable yield band structurally forbidden to a
tier-1 desk" -- per-account promotional tiers and small pools that only a small book can reach.
Measured on 2026-08-05 against the 39,190-row `defi_lending.jsonl` snapshot, that premise FAILS
its own falsifier: the best stablecoin supply APY reachable anywhere in the collected universe is
3.78% (aave-v3 USDC, Ethereum, $162M TVL) against a risk-free rate of 3.73%/yr. Net of the desk's
own mandated 300bps haircut the lending rung yields 0.78% and LOSES to T-bills.

    THE HAIRCUT IS DOING 100% OF THAT WORK. Gross, the lending rung wins by 5bps. The entire
    "DeFi loses" verdict rests on `DEFAULT_HAIRCUT_BPS = 300.0`, a constant with no derivation
    anywhere in the repo. So this module reports the verdict AND the gross comparison AND the
    breakeven haircut, and never lets the constant hide inside a single netted number. A screen
    whose answer is an assumption wearing a measurement's clothes is the L1.47 defect class.

Consequently the floor is `max(risk_free, lending_net)` and TODAY THAT IS SIMPLY THE RISK-FREE
RATE. The module keeps both rungs because the comparison is the deliverable: the day a rung wins
is the day the number changes, and a floor that only ever read one input could never notice.

WHAT IS NOT IN SCOPE HERE. This module MOVES NO FUNDS and recommends no allocation. It publishes a
number so that the L1.27 adjudication -- "am I protecting capital, or avoiding uncertainty?" --
has a dollar figure on one side of it instead of being rhetorical every time. Sizing, allocation
and rail-lifting remain principal decisions (L1.6, L1.23).
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: Symbols treated as USD-pegged for the lending rung. Deliberately EXCLUDES yield-bearing and
#: wrapped derivatives (sUSDe, sDAI, PT-*): their quoted "supply APY" is not a lending rate on a
#: dollar, it is a second strategy with its own duration, unwind and depeg profile. Folding those
#: in would manufacture a higher floor out of a different risk, which is how a comparison lies.
STABLE_SYMBOLS: frozenset[str] = frozenset({
    "USDT", "USDC", "USDC.E", "USDBC", "DAI", "FDUSD", "TUSD", "PYUSD",
    "LUSD", "FRAX", "GHO", "USDS", "CRVUSD", "USDP", "GUSD", "USDE",
})

#: A pool must hold at least this much to be quoted. NOT a size gate on us -- our whole book fits
#: in any of these many times over. It is a RATE-STABILITY floor: in a $9,881 pool (aave-v3 FRAX,
#: observed in the same snapshot) a deposit our size IS the utilisation curve, so the advertised
#: APY is not the APY we would receive. Quoting it would price a yield nobody can actually get.
MIN_POOL_TVL_USD: float = 1_000_000.0

#: Beyond this the lending snapshot is not evidence about today's rates.
DEFI_STALE_HOURS: float = 48.0
#: Beyond this the hurdle artifact is not evidence about today's risk-free rate.
HURDLE_STALE_HOURS: float = 168.0

_NAV = "data/nav_attestation.jsonl"
_LIVE = "web/cashcarry_live.json"
_DEFI = "data/defi_lending.jsonl"
_HURDLE = "data/hurdle_rate.json"


def _haircut_bps() -> float:
    """The lending haircut, IMPORTED and never copied.

    `screen_collateral_allocation.py` already owns this constant and already refuses to run at
    zero. A second literal here would be two definitions of one risk judgement, drifting silently
    -- the precise failure `capacity_policy.py` was created to end. If the import breaks, that is
    a REFUSAL, not a default: silently substituting a local number is how the drift starts.
    """
    from scripts.screen_collateral_allocation import DEFAULT_HAIRCUT_BPS
    return float(DEFAULT_HAIRCUT_BPS)


def _read_json(root: Path, rel: str) -> tuple[dict[str, Any] | None, float | None]:
    """Return (payload, age_hours). Age comes from an explicit stamp when present, else mtime."""
    p = root / rel
    try:
        data = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None, None
    stamp = None
    for k in ("generated", "updated", "ts"):
        if isinstance(data, dict) and data.get(k):
            try:
                stamp = datetime.fromisoformat(str(data[k]))
                break
            except ValueError:
                stamp = None
    if stamp is None:
        try:
            stamp = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        except OSError:
            return data, None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return data, (datetime.now(tz=UTC) - stamp).total_seconds() / 3600.0


@dataclass
class BookState:
    """What the book actually is, with the PAPER question answered before any arithmetic."""
    equity_usd: float
    deployed_usd: float
    idle_usd: float
    n_positions: int
    mode: str
    is_paper: bool
    measurable: bool
    why: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def book_state(root: Path | None = None) -> BookState:
    """Attested equity vs ACTUALLY deployed notional -- the two numbers the welded fence conflated.

    THE ORDER IS THE WHOLE POINT. `is_paper` is decided FIRST and gates `measurable`, because a
    dollar cost computed from a simulated denominator is worse than no number at all: it is a
    number a reader will act on. On a PAPER attestation this returns the observed figures for the
    record and `measurable=False`, so every downstream consumer must handle the refusal explicitly
    rather than receiving a plausible float.
    """
    root = root or _ROOT
    equity, mode, n_att = 0.0, "", 0
    try:
        lines = [ln for ln in (root / _NAV).read_text("utf-8").splitlines() if ln.strip()]
        n_att = len(lines)
        row = json.loads(lines[-1])
        equity = float(row.get("molded_curve_usd", row.get("equity_marked")) or 0.0)
        mode = str(row.get("mode") or "")
    except (OSError, ValueError, IndexError, TypeError):
        # source="unreadable", NOT the path: consumers distinguish "the chain says zero" from
        # "the chain could not be read", and naming the path here made the second look like the
        # first -- the fence's NO-DATA rung became unreachable and an absent book fell through to
        # a shallower status.
        return BookState(0.0, 0.0, 0.0, 0, "", False, False,
                         "NAV attestation chain absent or unreadable -- the book is unknown, and "
                         "unknown is never zero-cost", "unreadable")

    deployed, n_pos, live_src = 0.0, 0, _LIVE
    try:
        live = json.loads((root / _LIVE).read_text("utf-8"))
        deployed = float(live.get("deployed_notional") or 0.0)
        n_pos = int(live.get("n_carries") or 0)
    except (OSError, ValueError, TypeError):
        # Fall back to the attestation's own copy rather than assuming zero deployment: assuming
        # zero would MAXIMISE the reported idle cost on an unreadable file, and a fence that gets
        # louder when its input breaks is a fence that gets muted.
        try:
            row = json.loads([ln for ln in (root / _NAV).read_text("utf-8").splitlines()
                              if ln.strip()][-1])
            deployed = float(row.get("deployed_notional") or 0.0)
            n_pos = int(row.get("n_carries") or 0)
            live_src = _NAV
        except (OSError, ValueError, IndexError, TypeError):
            live_src = "unreadable"

    is_paper = ("PAPER" in mode.upper()) or ("TESTNET" in mode.upper())
    live_enable = (root / "data/LIVE_ENABLE").exists()
    idle = max(equity - deployed, 0.0)

    if is_paper or not live_enable:
        why = (
            f"attestation mode is {mode!r} across {n_att} row(s) and data/LIVE_ENABLE is "
            f"{'present' if live_enable else 'ABSENT'} -- `molded_curve_usd` is a MOLDED/SIMULATED "
            f"curve by its own _note, so ${equity:,.2f} is not a balance and no dollar cost may be "
            f"derived from it. The honest statement is that the desk has never deployed live "
            f"capital, not that its idle cost is ${idle:,.2f}."
        )
        return BookState(equity, deployed, idle, n_pos, mode or "unknown", True, False, why,
                         f"{_NAV}+{live_src}")

    return BookState(equity, deployed, idle, n_pos, mode or "LIVE", False, True,
                     f"venue-attested equity ${equity:,.2f}, deployed ${deployed:,.2f} across "
                     f"{n_pos} position(s)", f"{_NAV}+{live_src}")


def risk_free_annual(root: Path | None = None) -> tuple[float | None, str]:
    """The T-bill rate as an ANNUAL fraction, de-annualised from the period return on disk.

    TRAP 1 FROM THE MODULE DOCSTRING LIVES HERE. `hurdle_rate.json` stores `risk_free` as
    `rf_annual * (days / 365.0)`, so the raw field is the return over the measured window. On the
    2026-08-05 artifact that is 0.0034663 over 33.92 days = 3.73%/yr. Using the stored number as
    an annual rate understates the desk's idle cost by 10.8x, in the direction nothing alarms on.
    """
    data, age = _read_json(root or _ROOT, _HURDLE)
    if not isinstance(data, dict):
        return None, f"{_HURDLE} absent or unreadable"
    if age is not None and age > HURDLE_STALE_HOURS:
        return None, f"{_HURDLE} is {age:.0f}h old (>{HURDLE_STALE_HOURS:.0f}h) -- not evidence"
    try:
        period, days = float(data["risk_free"]), float(data["days"])
    except (KeyError, TypeError, ValueError):
        return None, f"{_HURDLE} lacks a usable risk_free/days pair"
    if days <= 0:
        return None, f"{_HURDLE} reports days={days} -- cannot de-annualise"
    return period * 365.0 / days, f"{period:.6f} over {days:.2f}d de-annualised"


def best_stable_apy(root: Path | None = None) -> tuple[dict[str, Any] | None, str]:
    """Best USD-pegged supply APY in the latest collected snapshot, as an annual FRACTION.

    Reads only the most recent timestamp: `defi_lending.jsonl` is a repeated CROSS-SECTION, not a
    series (8 distinct days across 39,190 rows -- R0042), so pooling every row would average
    today's rate against last week's and quote a yield nobody can get right now.
    """
    root = root or _ROOT
    rows: list[dict[str, Any]] = []
    try:
        for ln in (root / _DEFI).read_text("utf-8", errors="ignore").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("ts"):
                rows.append(r)
    except OSError:
        return None, f"{_DEFI} absent or unreadable"
    if not rows:
        return None, f"{_DEFI} holds no parseable rows"

    latest = max(str(r["ts"]) for r in rows)
    try:
        stamp = datetime.fromisoformat(latest)
    except ValueError:
        return None, f"{_DEFI} latest timestamp {latest!r} is unparseable"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    age_h = (datetime.now(tz=UTC) - stamp).total_seconds() / 3600.0
    if age_h > DEFI_STALE_HOURS:
        return None, (f"{_DEFI} snapshot is {age_h:.0f}h old (>{DEFI_STALE_HOURS:.0f}h) -- "
                      f"lending rates move, so this is not evidence about today")

    snap = [r for r in rows if str(r.get("ts")) == latest]
    best: dict[str, Any] | None = None
    n_stable = 0
    for r in snap:
        if str(r.get("symbol") or "").upper() not in STABLE_SYMBOLS:
            continue
        n_stable += 1
        try:
            apy_pct, tvl = float(r.get("supply_apy") or 0.0), float(r.get("tvl_usd") or 0.0)
        except (TypeError, ValueError):
            continue
        if tvl < MIN_POOL_TVL_USD or apy_pct <= 0:
            continue
        if best is None or apy_pct > best["apy_pct"]:
            best = {"apy_pct": apy_pct, "apy": apy_pct / 100.0, "tvl_usd": tvl,
                    "project": r.get("project"), "chain": r.get("chain"),
                    "symbol": str(r.get("symbol") or "").upper()}
    if best is None:
        return None, (f"no USD-pegged pool in the {age_h:.0f}h-old snapshot clears "
                      f"${MIN_POOL_TVL_USD:,.0f} TVL with a positive APY "
                      f"({n_stable} stable rows seen)")
    best["snapshot_ts"], best["snapshot_age_h"] = latest, round(age_h, 2)
    best["n_stable_pools"] = n_stable
    return best, (f"{best['project']}/{best['chain']} {best['symbol']} "
                  f"{best['apy_pct']:.2f}% on ${best['tvl_usd']:,.0f} TVL")


@dataclass
class Floor:
    """The reachable-yield floor, with BOTH rungs kept visible and the haircut never buried."""
    annual_rate: float | None
    winner: str
    risk_free_annual: float | None
    lending_gross_annual: float | None
    lending_net_annual: float | None
    haircut_bps: float
    breakeven_haircut_bps: float | None
    measurable: bool
    notes: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reachable_floor(root: Path | None = None, *, haircut_bps: float | None = None) -> Floor:
    """`max(risk_free, lending - haircut)`, publishing the comparison rather than just the max.

    WHY THE LOSER IS PUBLISHED TOO. On 2026-08-05 the lending rung loses by 295bps NET and wins by
    5bps GROSS -- the entire verdict is one underived constant. Reporting only the winning scalar
    would present an assumption as a measurement and would make the day the rungs cross invisible.
    `breakeven_haircut_bps` is the number that makes the decision auditable: below it, lending
    wins and the floor moves.
    """
    root = root or _ROOT
    hc = _haircut_bps() if haircut_bps is None else float(haircut_bps)
    if hc <= 0:
        raise ValueError(
            "haircut_bps must be > 0: smart-contract, depeg and withdrawal-queue risk are real "
            "and correlated with the moments you need the collateral back. Modelling them as "
            "zero is how a screen manufactures a winner (L1.5).")

    rf, rf_why = risk_free_annual(root)
    best, defi_why = best_stable_apy(root)
    notes = [f"risk_free: {rf_why}", f"lending: {defi_why}"]

    gross = float(best["apy"]) if best else None
    net = (gross - hc / 10_000.0) if gross is not None else None
    breakeven = (round((gross - rf) * 10_000.0, 1)
                 if (gross is not None and rf is not None) else None)

    candidates = {k: v for k, v in (("risk_free", rf), ("lending_net", net)) if v is not None}
    if not candidates:
        notes.append("NEITHER rung is measurable -- no floor can be published, and an unmeasured "
                     "floor is never 0%: a zero floor would price idle capital as free (L1.28a).")
        return Floor(None, "none", rf, gross, net, hc, breakeven, False, notes)

    winner = max(candidates, key=lambda k: candidates[k])
    # `gross` is narrowed alongside `net` because net is DERIVED from it -- true by construction,
    # but stating it keeps the arithmetic below provably total rather than relying on that.
    if net is not None and gross is not None and rf is not None:
        notes.append(
            f"lending loses by {(rf - net) * 10_000:.0f}bps NET but wins by "
            f"{(gross - rf) * 10_000:.0f}bps GROSS -- the {hc:.0f}bps haircut decides this "
            f"verdict entirely, and it has no derivation in the repo (brainstorm item 22)."
            if net < rf else
            f"lending wins by {(net - rf) * 10_000:.0f}bps NET of the {hc:.0f}bps haircut.")
    return Floor(candidates[winner], winner, rf, gross, net, hc, breakeven, True, notes,
                 {"best_pool": best} if best else {})


def idle_cost(root: Path | None = None, *, haircut_bps: float | None = None) -> dict[str, Any]:
    """Price the idle dollars. Returns a refusal, never a plausible float, when it cannot."""
    root = root or _ROOT
    bs, fl = book_state(root), reachable_floor(root, haircut_bps=haircut_bps)
    out: dict[str, Any] = {"book": bs.to_dict(), "floor": fl.to_dict()}

    # Gate on the RATE itself, not only on the `measurable` flag: the flag is a summary and the
    # rate is the thing every line below divides by. Two names for one condition is how a None
    # reaches arithmetic that "cannot" receive one.
    rate = fl.annual_rate
    if not fl.measurable or rate is None:
        out["status"] = "NO-FLOOR"
        out["usd_per_day"] = None
        out["why"] = "no yield rung is measurable -- " + "; ".join(fl.notes)
        return out
    if not bs.measurable:
        out["status"] = "UNMEASURABLE-PAPER-BOOK"
        out["usd_per_day"] = None
        # The counterfactual is still worth stating: it is what the cost WOULD be if the attested
        # figure were a balance. Labelled `hypothetical_` so nothing can mistake it for measured.
        out["hypothetical_usd_per_day"] = round(bs.idle_usd * rate / 365.0, 4)
        out["hypothetical_usd_per_year"] = round(bs.idle_usd * rate, 2)
        out["why"] = bs.why
        return out

    out["status"] = "PRICED"
    out["usd_per_day"] = round(bs.idle_usd * rate / 365.0, 4)
    out["usd_per_year"] = round(bs.idle_usd * rate, 2)
    out["why"] = (f"${bs.idle_usd:,.2f} idle at the {fl.winner} floor of "
                  f"{rate * 100:.2f}%/yr")
    return out
