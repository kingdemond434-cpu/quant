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

Multiplicity: m = the FULL concurrent forward cohort (libs.research.slot_registry), Holm-corrected
via forward_stats.holm_bar, so running many clocks in parallel does not inflate the family-wise
error rate. It counted len(_AXES) until 2026-07-30 -- the axis clocks only -- which applied
holm_bar(4)=2.24 while 12 clocks were accruing (2.64): a bar ~3.2x too loose, in the phantom-edge
direction, on the desk's only path from research to capital. The cohort spans axis + standing +
derivative clocks, so no single file may count it.

OPTIONAL STOPPING: this script runs on a cron and the first crossing wins, so the Holm bar -- a
ONE-LOOK threshold -- was being consulted ~daily for free. Measured on 1200 true-null paths at
m=12 over 180 days: a single look realises 0.0042 against a nominal 0.00417, daily peeking 0.0367
(8.8x nominal). Since R0187 (2026-08-05) ELIGIBLE additionally requires the anytime-valid
e-process (libs.research.anytime_valid) to cross 1/alpha at the SAME Holm alpha, which by Ville's
inequality is valid at every t simultaneously -- realised 0.0017. That is a strict tightening on
top of an unchanged t bar, never a replacement for it and never a speedup (GAP #25-RESULT
measured the e-process as SLOWER; it is adopted here as the stricter secondary check that ruling
sanctioned).

    python scripts/run_axis_shadows.py
"""
from __future__ import annotations

import json
import math
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.anytime_valid import e_value
from libs.research.evidence_clock import MIN_OBS, Sufficiency, sufficient
from libs.research.slot_registry import cohort_m_for_bar
from libs.validation.forward_stats import holm_alpha, holm_bar, nw_tstat

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "web" / "axis_shadows.json"
_STATE = _ROOT / "data" / "axis_shadow_state.json"

_BINANCE = "https://fapi.binance.com/fapi/v1/klines"

# axis registry: name -> (clock file, target symbol, signal field, direction)
# direction: +1 = momentum (long when z>0), -1 = reversal
_AXES: dict[str, tuple[str, str, str, int]] = {
    # kimchi_premium RETIRED 2026-07-30: RETRACTED 2026-07-29 (registry E-02f2917dfb, decision
    # REFUTED). The retraction STANDS but its stated mechanism was itself refuted on 2026-08-01
    # (R0067): the death is NO EDGE AT FULL DEPTH (h=1d IC +0.0148 vs a 0.041 floor at n=2,303,
    # per-era signs flipping), NOT a KST-vs-UTC lookahead -- Upbit dailies are UTC-midnight-
    # boundary, unlike bithumb's. Do not cite this as a timestamp-artifact precedent. Its clock
    # agreed: day 8/40 at ann Sharpe -5.13, nw_t -0.71. The retraction was never propagated here,
    # so a refuted hypothesis went on holding 1 of MAX_FORWARD_SLOTS=12 -- reading the cohort FULL
    # and blocking 9 verified axes from a clock (the clock-saturation defect), exactly the
    # "raises the confirmation bar on the LIVE axes for zero benefit" case set by
    # onchain_activity_throughput above. NOTE the distinction that licenses dropping m here:
    # kimchi was refuted as an INVALID MEASUREMENT, not failed on its merits, and an invalid trial
    # is not a trial -- a candidate that legitimately accrued and lost must STAY in the denominator
    # (ADAPTIVE VALIDATION WINDOWS v2: attrition must never lower the bar). Collector keeps
    # archiving (input store). Re-admission needs a NEW construction with declared UTC alignment
    # that clears the shift-sensitivity rail in scripts/revalidate_clocks.py first.
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
    # DeFi system utilisation (total borrow / total supply, Aave+Compound+Morpho+Spark).
    # M_FORCED_DELEVERAGE -- the desk's BEST-supported mechanism (2/10 survival, holds the only
    # confirmed edge). Direction -1: extreme utilisation = leverage crowded = fragile, so the
    # prior is that it precedes weakness. Stated in ADVANCE; the clock decides, not the story.
    # Stage-B slot 4 of 5 -- Holm bar rises 2.39 -> 2.52, which stageb_capacity computed as cheap.
    "defi_utilisation": ("data/defi_util_axis.jsonl", "BTCUSDT", "z20", -1),
    "stablecoin_supply_momentum": ("data/stablecoin_supply.jsonl", "BTCUSDT", "z20", +1),
    # USDT/CNY P2P premium (capital-control pressure; kimchi CN-analog). Direction +1
    # PRE-REGISTERED from mechanism 2026-07-24 (peek-safe: chosen before any forward
    # return existed). TRY-falsifier logged in the collector: thin 30d std => FAILING.
    "cny_premium": ("data/cny_premium.jsonl", "BTCUSDT", "z20", +1),
    # WALCL reserve-quantity impulse (R0031, registered 2026-07-31 into the slot kimchi's
    # retirement freed -- cohort 11 -> 12). Mechanism: the Fed balance sheet is the QUANTITY
    # of system reserves, an inelastic constraint on the marginal dollar bidding risk assets;
    # the highest-beta sink responds over weeks. Stage-A: IC +0.1106 (n=815 weekly), decontam
    # PASSED (resid +0.0964), stopped ONLY by the power gate (n_eff 116 vs MDI 0.1816) -- the
    # power wall closes by FORWARD ACCRUAL, nothing else. Direction +1 (momentum) stated in
    # advance from the screen's mechanism-consistent sign. Signal = 4wk log change, +2d
    # release lag, z20 -- construction frozen in scripts/derive_walcl_clock.py; the clock
    # decides, not the story. Peek-safe: first forward row is the registration day.
    "walcl_reserve_impulse": ("data/walcl_impulse.jsonl", "BTCUSDT", "z20", +1),
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


#: Dated rows required before "this clock yields nothing" is a statement about the INSTRUMENT
#: rather than about a clock that simply started yesterday.
_DEGENERATE_MIN_ROWS = 3


def _payload(row: dict[str, object]) -> str:
    """A row minus its date key -- what has to change for a new day to be new evidence.

    R0257. A deriver that runs on the desk's cron cadence while its SOURCE publishes on a slower
    one re-emits the same measurement under today's date. That is one observation recorded twice,
    not two observations, and it is invisible to every staleness check the desk owns because the
    artifact really is fresh and the row count really did grow (L1.46: a configured cadence is not
    evidence of a cadence).
    """
    return json.dumps({k: v for k, v in row.items() if k != "date"}, sort_keys=True)


def _e_shortfall(arr: np.ndarray, e: float, thr: float) -> int:
    """Extra OBSERVATIONS the e-process needs to reach `thr` at the current effect size.

    log-wealth accumulates roughly linearly in n (each observation contributes ~mu^2/2sigma^2), so
    n_needed ~ n * log(thr)/log(e). Reported in observations, never days (L1.48). Returns -1 when
    the series is not growing wealth at all -- there is no honest extrapolation from a bettor who
    is losing money, and "more data will not fix it" is the truthful answer.
    """
    n = int(arr.size)
    if e <= 1.0 or thr <= 1.0:
        return -1
    need = math.ceil(n * math.log(thr) / math.log(e))
    return max(0, need - n)


def _stage_b_verdict(arr: np.ndarray, t: float, bar: float, *,
                     alpha: float) -> tuple[str, int, Sufficiency]:
    """L1.48: eligibility asks the EVIDENCE (sample size + t-stat), never a flat day count.

    R0187 (2026-08-05): eligibility ALSO requires the anytime-valid e-process to cross 1/alpha.

    WHY, MEASURED ON THIS GATE. Everything below is re-evaluated EVERY DAY by the cron line that
    runs this script, and the first crossing wins -- which is optional stopping on a fixed-sample
    statistic. `holm_bar` is calibrated for ONE look. Simulated on 1200 true-null paths at m=12
    over a 180-day horizon (the reproduction is pinned in
    tests/scripts/test_axis_shadows_anytime_valid.py):

        nominal per-clock alpha                    0.00417
        single look, NW t >= 2.64                  0.0042    <- correctly calibrated
        DAILY peeking, first crossing              0.0367    <- 8.8x nominal, the status quo
        daily peeking AND e >= 1/alpha             0.0017    <- 0.4x nominal, this change

    So the desk was taking daily monitoring for free on the ONE path that reaches capital. Ville's
    inequality is what makes it payable: the e-process is a non-negative supermartingale under
    H0 (mean <= 0), so P(sup_t E_t >= 1/alpha) <= alpha holds at every t SIMULTANEOUSLY. Reading
    it daily is valid by construction rather than by permission.

    NOTHING LOOSENS, AND THAT IS STRUCTURAL, NOT A JUDGEMENT CALL. This is an AND: the Newey-West
    t must still clear the Holm bar and evidence_clock must still be satisfied, exactly as before,
    and the e-process is an additional hurdle on top. An AND of two gates is never looser than
    either one alone whatever the second gate's own calibration -- which is also why the e-process
    is safe here despite its two known weaknesses: it standardises by the full-sample sigma
    (not strictly predictable) and it assumes independence across observations, where funding-like
    series are autocorrelated. Both would make it anti-conservative ON ITS OWN; neither can make
    the conjunction looser than the Newey-West leg that already corrects for autocorrelation.

    THIS IS NOT A SPEEDUP AND IS NOT SOLD AS ONE. GAP_REGISTER #25-RESULT measured the e-process
    as strictly SLOWER than the fixed clock and adopted it as "a stricter SECONDARY check for
    high-stakes promotions" -- promotion to capital is the high-stakes promotion, and this is that
    adoption. At the desk's alpha the e-bar is equivalent to a plain t of sqrt(2*ln(1/alpha))
    ~ 3.31 against the fixed-sample 2.64, so ~57% more observations at the same effect size. It is
    a real hurdle and NOT a welded gate (L1.43): measured over marginal-effect fixtures it admits
    4-19% where the t-bar alone admits 19-57%, so it still carries information.

    The e-process does NOT touch FAILING. A negative effect is called by evidence_clock at the
    trust floor as before; asking a wealth process to certify failure would be a category error,
    since e stays near zero both for an edge that is absent and for one merely not yet proven.

    Replaced `_MIN_DAYS = 40` (2026-08-05) -- the exact constant evidence_clock's docstring names
    as the habit being killed. The statistical bar is UNTOUCHED: ELIGIBLE still requires the
    Newey-West t to clear the Holm-corrected cohort bar, and additionally requires
    evidence_clock's own sufficiency (observation floor + plain-t at the same bar), so this is a
    strict tightening on the t axis. What changed is the WAITING: a strong axis no longer idles
    behind a 40-observation wall it has already out-argued, and a non-positive effect
    (t <= 0 at >= MIN_OBS observations) is called FAILING at the point where evidence_clock says
    "more data will not fix it" instead of after an arbitrary 40. A weakly-positive axis is
    ACCRUING with its shortfall stated in OBSERVATIONS (obs_short), never in days -- that is the
    reporting form L1.48 mandates, and it is actionable (open slots, widen the universe) where
    "wait N days" was not.

    Returns (verdict, need, sufficiency) where `need` is the total observations currently
    required: the trust floor below MIN_OBS, n + obs_short while short of the bar at the current
    effect size, and n once the question is decided either way (readers compute progress as
    forward_days/need, which now measures evidence rather than elapsed time).
    """
    n = int(arr.size)
    stdev = float(arr.std(ddof=1)) if n >= 2 else 0.0
    suff = sufficient(float(arr.mean()), stdev, n, min_t=bar)
    e, thr = e_value(arr), 1.0 / alpha
    if suff.sufficient and t >= bar and e >= thr:
        return "ELIGIBLE", n, suff
    if n >= MIN_OBS and t <= 0.0:
        return "FAILING", n, suff
    if n < MIN_OBS:
        return "ACCRUING", MIN_OBS, suff
    # `need` states the BINDING constraint. Where the fixed-sample t already clears but the
    # peek-safe process does not, the honest shortfall is the e-process's, and hiding it would
    # report a clock as nearly-eligible when the gate it actually faces is far away.
    e_short = _e_shortfall(arr, e, thr)
    need = n + max(int(suff.obs_short), int(e_short), 1)
    return "ACCRUING", need, suff


def _evaluate(name: str, clock: str, symbol: str, field: str, direction: int, m: int) -> dict:
    rows = _clock_rows(_ROOT / clock)
    if len(rows) < 2:
        return {"axis": name, "verdict": "ACCRUING", "forward_days": len(rows),
                "need": MIN_OBS, "note": "clock just started -- forward evidence begins now"}

    closes = _closes(symbol)
    rets, used = [], []
    restamped = flat = unusable = 0
    for i in range(len(rows) - 1):
        d0, d1 = rows[i].get("date"), rows[i + 1].get("date")
        c0, c1 = closes.get(d0), closes.get(d1)
        z = rows[i].get(field)
        if None in (c0, c1, z) or c0 == 0:
            unusable += 1
            continue
        # R0257, the two ways a dated row is not an observation. Both SUBTRACT evidence and can
        # never add any, which is what makes this safe to apply to a live promotion path.
        #   RE-STAMP: rows[i] repeats rows[i-1] verbatim, so the position at d0 is the same
        #   measurement already counted -- betting one signal value on two days is one observation
        #   with autocorrelation, not two independent ones.
        if i > 0 and _payload(rows[i]) == _payload(rows[i - 1]):
            restamped += 1
            continue
        pos = float(np.sign(float(z))) * direction     # position taken AT d0 close
        #   FLAT: sign(0) == 0, so no position was taken. A day the signal declined to bet is not
        #   an observation OF the signal; counting it walks `n` toward MIN_OBS while dragging the
        #   t-stat toward zero -- loosening the power gate and tightening the statistic at once,
        #   and both are wrong.
        if pos == 0.0:
            flat += 1
            continue
        rets.append(pos * (c1 / c0 - 1.0))             # realised over d0 -> d1 (no lookahead)
        used.append(d1)

    n = len(rets)
    # A clock that keeps producing dated rows while yielding no usable observation -- or throwing
    # away at least as many as it keeps -- is a broken INSTRUMENT, and the desk must never read it
    # as a weak or refuted EFFECT. Measured 2026-08-05: walcl_reserve_impulse re-stamped one
    # 2026-07-29 observation (3 rows, 1 distinct payload) and read ACCRUING 2/20; defi_utilisation
    # took no position on 4 of 5 days and read ACCRUING 5/20; cny_premium collected 14 dated rows
    # whose signal field was null in every one and read ACCRUING 0/20. The dangerous case is not
    # the flattering one: an all-zero return series is ACCRUING only below MIN_OBS and turns
    # FAILING at n>=20 via the `t <= 0` branch, so a clock that has never once measured anything
    # would have retired its own research ground as a refuted hypothesis (L1.25: the ordered
    # diagnostic starts at the INSTRUMENT, and a killed axis raises no alarm).
    diag = {"dated_rows": len(rows), "distinct_observations": n, "restamped": restamped,
            "flat_position": flat, "unusable": unusable}
    if len(rows) >= _DEGENERATE_MIN_ROWS and (n == 0 or (restamped + flat) >= n):
        return {"axis": name, "verdict": "DEGENERATE", "forward_days": n, "need": MIN_OBS, **diag,
                "note": (f"{len(rows)} dated rows yielded {n} distinct observation(s) "
                         f"({restamped} re-stamped, {flat} flat, {unusable} unusable) -- this is "
                         "an instrument fault, NOT evidence about the hypothesis")}
    if n < 2:
        return {"axis": name, "verdict": "ACCRUING", "forward_days": n, "need": MIN_OBS, **diag,
                "note": "not enough aligned forward days yet"}

    arr = np.asarray(rets, dtype="float64")
    cum = float(np.prod(1.0 + arr) - 1.0)
    sharpe = float(arr.mean() / arr.std() * np.sqrt(365)) if arr.std() > 0 else 0.0
    t = float(nw_tstat(arr)) if n >= 3 else 0.0
    bar = float(holm_bar(m, rank=1))
    alpha = float(holm_alpha(m, rank=1))

    verdict, need, suff = _stage_b_verdict(arr, t, bar, alpha=alpha)
    e = float(e_value(arr))
    # `forward_days` counts aligned forward OBSERVATIONS, not calendar days -- the key name is kept
    # for its readers (revalidate_clocks, claim_verifier). Until R0257 this comment claimed the
    # count excluded degenerate rows and it did not: the claim was the documentation, the exclusion
    # was nowhere. The diagnostics are published beside it so the gap can never re-open silently.
    return {"axis": name, "verdict": verdict, "forward_days": n, "need": int(need), **diag,
            "obs_short": int(suff.obs_short), "evidence": suff.reason,
            "cum_return": round(cum, 5), "ann_sharpe": round(sharpe, 2),
            "nw_t": round(t, 3), "holm_bar": round(bar, 3), "m_concurrent": m,
            # The peek-safe leg, published so a reader can see WHICH gate is binding rather than
            # inferring it. `e_short` is -1 when the e-process is not growing wealth at all.
            "e_value": round(e, 4), "e_threshold": round(1.0 / alpha, 1),
            "holm_alpha": round(alpha, 6), "e_short": _e_shortfall(arr, e, 1.0 / alpha),
            "peek_safe": bool(e >= 1.0 / alpha),
            "first_forward_day": used[0] if used else None, "last": used[-1] if used else None,
            "stage": "B (forward-only; eligibility != deployment)"}


_REGISTRY = Path("data/axis_clock_registry.json")


def _all_axes() -> tuple[dict[str, tuple[str, str, str, int]], list[dict]]:
    """Hand-curated axes UNION whatever earned or was owed a clock elsewhere.

    `_AXES` above is hand-maintained, so a candidate that EARNED a forward clock did not appear in
    Stage-B -- or on the dashboard -- until a human edited this file. The live box printed
    "9 survivor(s) owed a shadow start; 0 record(s) laddered" every cycle because of it. That
    failure is silent and looks exactly like "no new candidates", which is the one shape nobody
    investigates.

    CURATED WINS A COLLISION: a considered decision here outranks anything auto-registered, so a
    re-screen can never redirect a live clock's target. An axis registered WITHOUT a target symbol
    is returned UNTRACKED rather than dropped or guessed -- dropping recreates the invisibility,
    and guessing scores a candidate against the wrong asset.
    """
    merged = dict(_AXES)
    untracked: list[dict] = []
    try:
        blob = json.loads(_REGISTRY.read_text("utf-8"))
    except (OSError, ValueError):
        return merged, untracked
    for name, rec in (blob.get("axes") or {}).items():
        if name in merged or not isinstance(rec, dict):
            continue
        target = str(rec.get("target_symbol") or "")
        clock = str(rec.get("clock") or "")
        if not target or not clock:
            untracked.append({
                "axis": name, "verdict": "UNTRACKED", "auto_registered": True,
                "owed_since": rec.get("owed_since", ""),
                "note": ("clock owed or registered without a target symbol, so forward P&L cannot "
                         "be scored. Listed rather than dropped -- an invisible candidate is the "
                         "defect this union exists to prevent -- and NOT guessed at, because "
                         "scoring against the wrong asset is worse than not scoring"),
                "stage": "B (registered, unscoreable)"})
            continue
        merged[name] = (clock, target, str(rec.get("method") or "z20"),
                        int(rec.get("sign") or 1))
    return merged, untracked


def main() -> None:
    # One cohort read for the whole run: every clock in this file is judged against the SAME
    # concurrent-m, and re-deriving per axis would let the bar drift mid-run.
    cohort = cohort_m_for_bar()
    m = cohort.m
    tracked, untracked = _all_axes()
    results = [_evaluate(k, *v, m) for k, v in tracked.items()]
    results.extend(untracked)
    for r in results:
        r.setdefault("auto_registered", r.get("axis") not in _AXES)
    payload = {"updated": datetime.now(tz=UTC).isoformat(), "min_observations": MIN_OBS,
               # A bar is only auditable if its artifact says which cohort it was computed
               # against, and with what provenance (MEASURED vs floored) -- L1.6 fence reads this.
               "m_concurrent": cohort.m, "m_provenance": cohort.provenance,
               "m_detail": cohort.detail,
               "axes": results,
               "note": ("Forward-only Stage-B tracking. P&L starts at the clock's first row, never "
                        "the screen sample. ELIGIBLE means the evidence bar is met and a promotion "
                        "decision may be taken -- it is NOT an automatic deployment. Eligibility "
                        "asks evidence_clock (L1.48): observations + t-stat, never elapsed days.")}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    _STATE.write_text(json.dumps(payload, indent=1), "utf-8")
    for r in results:
        extra = f"t={r.get('nw_t')} bar={r.get('holm_bar')}" if "nw_t" in r else r.get("note", "")
        # .get(): untracked-registry rows carry no forward_days/need, and a KeyError HERE -- after
        # both artifacts were already written -- made every cron run of this organ exit nonzero,
        # which read as "organ always dies" while the artifact quietly aged.
        print(f"axis-shadow | {r.get('axis')}: {r.get('verdict')} "
              f"({r.get('forward_days', '-')}/{r.get('need', '-')} obs) {extra}")
    print(f"-> {_OUT}")


if __name__ == "__main__":
    main()
