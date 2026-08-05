#!/usr/bin/env python3
"""AXIS SHADOW SLEEVES -- Stage-B forward tracking for every screened data axis.

Closes the loop the two-stage law needs: Stage A (libs/research/axis_screen) writes a forward
clock, but NOTHING read those clocks, so evidence accrued into a file nobody evaluated and
eligibility could never be detected. This runs the shadow book for each axis and computes the
Stage-B statistics that actually govern promotion.

STRICTLY FORWARD-ONLY. The in-sample screen history is IGNORED: P&L starts at the clock's first
row (pre-registration date). A hypothesis registered before its window cannot have overfit that
window -- that is the entire statistical basis for Stage B, and reading back into the screen
sample would destroy it.

ZERO PROMOTION AUTHORITY of its own: it reports ACCRUING / ELIGIBLE / FAILING. ELIGIBLE means the
evidence bar is met and a promotion decision may now be TAKEN by the normal gauntlet + principal
path -- never an automatic deployment of capital.

Multiplicity: m = the FULL concurrent forward cohort from libs.research.slot_registry, NOT the
number of axes this script happens to track. Holm-corrected via forward_stats.holm_bar.

  This was wrong until 2026-08-05 and it was wrong in the dangerous direction. `holm_bar(len(_AXES))`
  charged these clocks m=3 (bar 2.13) while 11 forward clocks were accruing concurrently (bar 2.61)
  -- alpha 0.0167 per clock against a designed 0.0045, a family-wise error rate 3.67x the design.
  An axis is not its own family: every OTHER clock racing beside it is what makes a lucky t-stat
  likely, so the multiplicity a clock pays is a property of the DESK, never of the script that
  happens to run it. slot_registry.cohort_m_for_bar() is the only source of that number.

    python scripts/run_axis_shadows.py
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.slot_registry import cohort_m_for_bar
from libs.validation.forward_stats import holm_bar, nw_tstat

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "web" / "axis_shadows.json"
_STATE = _ROOT / "data" / "axis_shadow_state.json"

_MIN_DAYS = 40          # pre-registered minimum forward window before eligibility
_BINANCE = "https://fapi.binance.com/fapi/v1/klines"

# axis registry: name -> (clock file, target symbol, signal field, direction)
# direction: +1 = momentum (long when z>0), -1 = reversal
_AXES: dict[str, tuple[str, str, str, int]] = {
    "kimchi_premium": ("data/kimchi_premium.jsonl", "BTCUSDT", "z20", +1),
    # orthogonal on-chain USAGE axis (not price/derivative): economic throughput,
    # reversal. Weak+fragile in-sample (composite Sharpe collapsed) -> forward clock
    # under the Holm bar decides. same-period corr ~-0.06 = genuinely leading.
    # onchain_activity_throughput RETIRED 2026-07-24: killed by 11y reconstructed held-out
    # OOS (IC ~0, ann Sharpe -0.03, regime thirds [-0.3,-0.08,+0.37] = recent-era overfit;
    # reports/reconstructed_oos/onchain_throughput.json). A permanently-unpromotable axis
    # holding a Holm slot raises the confirmation bar on the LIVE axes for zero benefit.
    # Collector keeps archiving (input store); the CLOCK slot is freed. Re-admission needs
    # a NEW construction that passes held-out OOS first.
    # macro dollar-liquidity: total stablecoin supply (all issuers, DefiLlama),
    # momentum. Weak (IC 0.067) but economically grounded + orthogonal. SAME construct
    # as the supply field in run_stablecoin_flows -> ONE hypothesis, this is the tracked one.
    "stablecoin_supply_momentum": ("data/stablecoin_supply.jsonl", "BTCUSDT", "z20", +1),
    # USDT/CNY P2P premium (capital-control pressure; kimchi CN-analog). Direction +1
    # PRE-REGISTERED from mechanism 2026-07-24 (peek-safe: chosen before any forward
    # return existed). TRY-falsifier logged in the collector: thin 30d std => FAILING.
    "cny_premium": ("data/cny_premium.jsonl", "BTCUSDT", "z20", +1),
}


def _closes(symbol: str, n: int = 400) -> dict[str, float]:
    """Daily closes keyed by ISO date (UTC), from the venue the desk actually trades."""
    url = f"{_BINANCE}?symbol={symbol}&interval=1d&limit={n}"
    req = urllib.request.Request(url, headers={"User-Agent": "quant-desk/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    return {datetime.fromtimestamp(k[0] / 1000, tz=UTC).date().isoformat(): float(k[4])
            for k in rows}


def _clock_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text("utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _evaluate(name: str, clock: str, symbol: str, field: str, direction: int,
              *, cohort) -> dict:
    rows = _clock_rows(_ROOT / clock)
    if len(rows) < 2:
        return {"axis": name, "verdict": "ACCRUING", "forward_days": len(rows),
                "need": _MIN_DAYS, "note": "clock just started -- forward evidence begins now"}

    closes = _closes(symbol)
    rets, used = [], []
    for i in range(len(rows) - 1):
        d0, d1 = rows[i].get("date"), rows[i + 1].get("date")
        c0, c1 = closes.get(d0), closes.get(d1)
        z = rows[i].get(field)
        if None in (c0, c1, z) or c0 == 0:
            continue
        pos = float(np.sign(float(z))) * direction     # position taken AT d0 close
        rets.append(pos * (c1 / c0 - 1.0))             # realised over d0 -> d1 (no lookahead)
        used.append(d1)

    n = len(rets)
    if n < 2:
        return {"axis": name, "verdict": "ACCRUING", "forward_days": n, "need": _MIN_DAYS,
                "note": "not enough aligned forward days yet"}

    arr = np.asarray(rets, dtype="float64")
    cum = float(np.prod(1.0 + arr) - 1.0)
    sharpe = float(arr.mean() / arr.std() * np.sqrt(365)) if arr.std() > 0 else 0.0
    t = float(nw_tstat(arr)) if n >= 3 else 0.0
    bar = float(holm_bar(cohort.m, rank=1))

    if n < _MIN_DAYS:
        verdict = "ACCRUING"
    elif t >= bar:
        verdict = "ELIGIBLE"                            # bar met -- decision may now be taken
    else:
        verdict = "FAILING"                             # forward evidence does not support it
    return {"axis": name, "verdict": verdict, "forward_days": n, "need": _MIN_DAYS,
            "cum_return": round(cum, 5), "ann_sharpe": round(sharpe, 2),
            "nw_t": round(t, 3), "holm_bar": round(bar, 3), "m_concurrent": cohort.m,
            "m_provenance": cohort.provenance, "m_detail": cohort.detail,
            "first_forward_day": used[0] if used else None, "last": used[-1] if used else None,
            "stage": "B (forward-only; eligibility != deployment)"}


def main() -> None:
    # Derived ONCE, and BEFORE _STATE is rewritten below -- derive_slots() reads that same file to
    # count the axis clocks, so deriving per-axis would both re-read it 3x and let this run's own
    # write feed back into its own bar.
    cohort = cohort_m_for_bar()
    results = [_evaluate(k, *v, cohort=cohort) for k, v in _AXES.items()]
    payload = {"updated": datetime.now(tz=UTC).isoformat(), "min_forward_days": _MIN_DAYS,
               "axes": results,
               "m_concurrent": cohort.m, "m_provenance": cohort.provenance,
               "m_detail": cohort.detail,
               "note": ("Forward-only Stage-B tracking. P&L starts at the clock's first row, never "
                        "the screen sample. ELIGIBLE means the evidence bar is met and a promotion "
                        "decision may be taken -- it is NOT an automatic deployment. m is the FULL "
                        "desk cohort (slot_registry), never len(_AXES) -- see the module docstring "
                        "for the 3.67x error-rate inflation that cost.")}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    _STATE.write_text(json.dumps(payload, indent=1), "utf-8")
    for r in results:
        extra = f"t={r.get('nw_t')} bar={r.get('holm_bar')}" if "nw_t" in r else r.get("note", "")
        print(f"axis-shadow | {r['axis']}: {r['verdict']} "
              f"({r['forward_days']}/{r['need']}d) {extra}")
    print(f"holm cohort m={cohort.m} [{cohort.provenance}] {cohort.detail}")
    print(f"-> {_OUT}")


if __name__ == "__main__":
    main()
