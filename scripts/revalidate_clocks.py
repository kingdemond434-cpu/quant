"""LIVE-CLOCK RE-VALIDATION against the rails added 2026-07-23..27.

Every currently-tracked axis was screened BEFORE some of these controls existed. A signal that
passed a weaker gate is not validated -- it is unexamined. This re-runs each LIVE axis through:
  1. the hardened harness (de-contamination + SUSPECT-LOOKAHEAD plausibility rail)
  2. the SHIFT-SENSITIVITY test that killed bithumb_KR (timezone/candle-label lookahead): a genuine
     leading signal degrades smoothly under a +/-1 day shift; a lookahead artifact keeps or peaks
     its IC when the signal is shifted FORWARD (i.e. it already contained future price).
KIMCHI USES UPBIT DAILY CANDLES, and bithumb -- another KRW venue -- died of a KST day-open
timestamp sitting ~1.6d ahead of Binance UTC closes. THOSE ARE DIFFERENT VENUES WITH DIFFERENT
CANDLE BOUNDARIES, and assuming otherwise is what produced the 07-29 keying regression (R0067):
Upbit dailies are UTC-midnight-boundary, proven from Upbit's own hourly candles. Per-venue candle
boundaries are MEASURED (tests/research/test_upbit_boundary.py), never inherited from a sibling.
Read-only diagnostic. Run from repo root."""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.dist_shift import split_and_check  # noqa: E402
from libs.research.upbit_data import upbit_daily_utc_keyed  # noqa: E402
from libs.validation.revalidation import (  # noqa: E402
    RevalidationController,
    WalkForwardReport,
    WalkForwardStatus,
)

_OUT = _ROOT / "data/clock_revalidation.json"
_SHADOW = _ROOT / "data/axis_shadow_state.json"


def _forward_report(axis: str) -> WalkForwardReport:
    """The axis's CURRENT standing, read from its forward clock rather than asserted.

    PASSED only where the clock has actually met its bar -- an ACCRUING axis is PENDING, never
    passing. This matters because the controller's whole job is downgrading PASSED -> STALE on a
    hard trigger: hand it a fake PASSED and the downgrade is theatre.
    """
    status, sharpe, stability, msg = WalkForwardStatus.PENDING, 0.0, 0.0, "no forward clock"
    try:
        axes = json.loads(_SHADOW.read_text("utf-8")).get("axes", [])
    except (OSError, ValueError):
        axes = []
    for a in axes:
        if a.get("axis") != axis:
            continue
        sharpe = float(a.get("ann_sharpe") or 0.0)
        fwd, need = int(a.get("forward_days") or 0), int(a.get("need") or 40)
        stability = min(1.0, fwd / need) if need else 0.0
        verdict = str(a.get("verdict") or "")
        status = (WalkForwardStatus.PASSED if verdict == "ELIGIBLE"
                  else WalkForwardStatus.PENDING)
        msg = f"clock {verdict} {fwd}/{need}d, ann_sharpe={sharpe:.2f}"
        break
    return WalkForwardReport(status=status, walk_forward_score=0.0, n_windows=0,
                             oos_sharpe=sharpe, oos_mean_return=0.0, stability=stability,
                             message=msg)


def _z(series: np.ndarray, win: int = 20) -> np.ndarray:
    """Causal trailing z-score -- the desk's standard signal transform (same window the Stage-A
    screen uses), warmup dropped.

    NOT COSMETIC, and the first wiring got this wrong. A two-window distribution test fed RAW
    LEVELS fires on any trending series: a deterministic constant-increment ramp -- a process with
    no distributional change whatsoever -- returns SHIFT, and stablecoin supply is very nearly that
    ramp. The first run of this wiring duly reported SHIFT on both axes with an identical 0.35
    haircut, which is the welded-gate signature: a detector that fires on everything carries zero
    information (L1.43, gate-optimality duty).

    The right question is whether the distribution of the signal AS THE STRATEGY CONSUMES IT has
    moved, and the strategy consumes the z-score, which is stationary by construction. Positive
    controls: iid noise -> STABLE, a genuine mean/variance regime change -> SHIFT.
    """
    x = np.asarray(series, dtype=float)
    if len(x) <= win:
        return np.array([], dtype=float)
    out = np.zeros(len(x))
    for t in range(win, len(x)):
        w = x[t - win:t]
        sd = w.std()
        out[t] = (x[t] - w.mean()) / sd if sd > 0 else 0.0
    return out[win:]


def dist_revalidate(name: str, series: np.ndarray, results: list[dict]) -> dict:
    """DISTRIBUTION-SHIFT REVALIDATION -- the wiring that did not exist until 2026-08-01.

    `libs/research/dist_shift.py` was built 2026-07-29, unit-tested green, and cited by the
    enforcement matrix as the evidence that L1.19 (information decay) and L2.10 (reality gap) were
    enforced -- while its only importer in the repo was its own test. `RevalidationController`
    consumes exactly what it produces (`drift` / `structural_break`) and had no caller either.
    Producer and consumer both existed, fit each other exactly, and were never connected.

    Direction is downward-only by construction: a SHIFT can strip production capital from a
    passing axis, never grant it. A monitor that could promote would be an alpha claim wearing a
    diagnostic's clothes.
    """
    d = split_and_check(_z(np.asarray(series, dtype=float)), name=name)
    verdict = d.get("verdict", "INSUFFICIENT-DATA")

    # ONLY *SHIFT* IS A HARD TRIGGER, and this is the caller's decision to make -- dist_shift is
    # explicitly advisory ("the caller decides, and the caller logs the decision").
    #
    # DRIFT fires on ONE marginal indicator, and a bare KS flag is the cheapest of the three: at
    # n_ref=659/n_recent=220 the 5% critical value is ~0.106, so the test is badly overpowered, and
    # financial series are autocorrelated, which violates the iid assumption KS rests on and
    # inflates the false-positive rate further. Measured here: a benign drifting random walk
    # returns DRIFT. Wiring that to _HARD_TRIGGERS -- which DRIFT is a member of -- would strip
    # production capital from healthy axes on a noisy statistic, and a clamp that fires on nothing
    # real is a compounding cost, not prudence (L1.27/L1.28).
    #
    # SHIFT is the defensible bar: it needs a break-magnitude move (>4x variance or >2.5 MADs) OR
    # agreement between two independent views. That is the module's own corroboration discipline,
    # and it is what "conclude" should mean. DRIFT stays what its author intended -- a flag plus a
    # downward-only confidence haircut, carried in the artifact, blocking nothing.
    hard = verdict == "SHIFT"
    decision = RevalidationController().assess(_forward_report(name), structural_break=hard)
    row = {"axis": name, "dist_verdict": verdict, "haircut": d.get("haircut"),
           "advisory_only": verdict == "DRIFT",
           "ks_d": d.get("ks_d"), "ks_crit_5pct": d.get("ks_crit_5pct"),
           "var_ratio": d.get("var_ratio"), "level_move_mads": d.get("level_move_mads"),
           "n_ref": d.get("n_ref"), "n_recent": d.get("n_recent"),
           "revalidation_status": decision.status.value,
           "production_capital_allowed": decision.production_capital_allowed,
           "triggers": [t.value for t in decision.triggers],
           "rationale": decision.rationale}
    results.append(row)
    print(f"  DIST-SHIFT {name}: {verdict} haircut={d.get('haircut')} "
          f"-> revalidation={decision.status.value} "
          f"capital_allowed={decision.production_capital_allowed}")
    return row


def _get(url, timeout=35):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-reval/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def binance(sym="BTCUSDT", n=900):
    rows = _get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d&limit={n}")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def yahoo(sym):
    r = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=300d")
    res = r["chart"]["result"][0]
    return {datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
            for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"], strict=False) if c}


def upbit():
    # ONE copy of the alignment policy (see libs/research/upbit_data.py): this script carried its
    # own inline keying and kept printing a stale IC after the collector was changed -- two copies
    # of one policy means fixing one only moves the bug.
    return upbit_daily_utc_keyed("KRW-BTC", 200)


def stablesupply():
    d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
    out = {}
    for x in d:
        v = x.get("totalCirculatingUSD") or {}
        p = v.get("peggedUSD") if isinstance(v, dict) else None
        if p is not None:
            out[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(p)
    return out


def shift_ic(signal: dict, gb: dict, shift: int, fx: dict | None = None) -> float:
    """IC of z(signal shifted by `shift` days) vs NEXT-day return.

    THE SIGNAL IS BUILT SAME-INSTANT FIRST, THEN THE FINISHED SERIES IS SHIFTED. This used to
    shift only the numerator leg -- signal[i+shift] over fx[i]/gb[i] -- which for a ratio signal
    whose DENOMINATOR is the target's own price does not shift the signal at all: it rebuilds it
    as roughly gb[i+1]/gb[i], i.e. the forward return itself. Measured on an i.i.d.-noise premium
    with zero predictive content by construction, the old form reported a +1d cell of +0.931.

    That false positive is not hypothetical: it is what produced the "kimchi is a ~73% timestamp
    artifact" verdict on 2026-07-29, which justified a +1d keying change that then 24h-mispaired
    three days of live collection and put a refuted mechanism in the graveyard (R0067). A leak
    detector that fires on clean data is worse than none -- it makes good data look broken and
    gets "fixed" in the direction of the damage.
    """
    dates = sorted(set(signal) & set(gb) & (set(fx) if fx else set(gb)))
    if len(dates) < 60:
        return float("nan")
    btc = np.array([gb[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0
    fwd = np.roll(ret, -1)
    series = np.array([signal[d] / fx[d] / gb[d] - 1.0 for d in dates]) if fx else \
        np.array([signal[d] for d in dates], dtype=float)
    sig, rr = [], []
    for i in range(len(dates)):
        j = i + shift
        if 0 <= j < len(dates):
            sig.append(series[j])
            rr.append(fwd[i])
    sig, rr = np.array(sig, float), np.array(rr, float)
    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0
    zv, fv = z[20:-1], rr[20:-1]
    return float(np.corrcoef(zv, fv)[0, 1]) if zv.std() and fv.std() else 0.0


def main() -> None:
    _law_guard()
    dist: list[dict] = []
    gb = binance()
    print("=== LIVE CLOCK RE-VALIDATION (hardened harness + shift test) ===\n")

    # ---- 1. KIMCHI (highest risk: KRW venue, same class as the bithumb lookahead kill) ----
    try:
        kb, fx = upbit(), yahoo("KRW=X")
        dates = sorted(set(kb) & set(gb) & set(fx))
        prem = np.array([kb[d] / fx[d] / gb[d] - 1.0 for d in dates])
        btc = np.array([gb[d] for d in dates])
        ret = np.zeros(len(btc))
        ret[1:] = btc[1:] / btc[:-1] - 1.0
        r = stage_a_screen(prem, ret, name="kimchi_premium", zwin=20)
        s = {k: shift_ic(kb, gb, k, fx) for k in (-1, 0, 1)}
        print(f"KIMCHI n={len(dates)} | IC {r.get('ic'):+.4f} same {r.get('same_period_corr'):+.3f} "
              f"resid {r.get('residual_ic'):+.4f} | {r['verdict']}")
        print(f"  SHIFT TEST  -1d {s[-1]:+.3f} | 0d {s[0]:+.3f} | +1d {s[1]:+.3f}")
        fwd_leak = abs(s[1]) > abs(s[0]) * 1.5 and abs(s[1]) > 0.3
        print(f"  -> {'*** FORWARD-SHIFT LEAK SUSPECTED ***' if fwd_leak else 'no lookahead pattern (shift0 not dominated by +1d)'}")
        dist_revalidate("kimchi_premium", prem, dist)
        print()
    except Exception as e:
        print(f"KIMCHI: ERROR {type(e).__name__}: {e}\n")

    # ---- 2. STABLECOIN SUPPLY ----
    try:
        sup = stablesupply()
        dates = sorted(set(sup) & set(gb))
        sig = np.array([sup[d] for d in dates])
        btc = np.array([gb[d] for d in dates])
        ret = np.zeros(len(btc))
        ret[1:] = btc[1:] / btc[:-1] - 1.0
        r = stage_a_screen(sig, ret, name="stablecoin_supply", zwin=20)
        s = {k: shift_ic(sup, gb, k) for k in (-1, 0, 1)}
        print(f"STABLECOIN SUPPLY n={len(dates)} | IC {r.get('ic'):+.4f} "
              f"same {r.get('same_period_corr'):+.3f} resid {r.get('residual_ic'):+.4f} | {r['verdict']}")
        print(f"  SHIFT TEST  -1d {s[-1]:+.3f} | 0d {s[0]:+.3f} | +1d {s[1]:+.3f}")
        print(f"  -> {'*** FORWARD-SHIFT LEAK SUSPECTED ***' if abs(s[1])>abs(s[0])*1.5 and abs(s[1])>0.3 else 'no lookahead pattern'}")
        dist_revalidate("stablecoin_supply_momentum", sig, dist)
        print()
    except Exception as e:
        print(f"STABLECOIN: ERROR {type(e).__name__}\n")

    # ---- 3. CNY premium clock health ----
    p = Path("data/cny_premium.jsonl")
    if p.exists():
        rows = [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
        nz = [r for r in rows if r.get("z20") is not None]
        print(f"CNY PREMIUM clock: {len(rows)} rows, {len(nz)} with usable z20 "
              f"(needs ~20 for warmup)")
        print(f"  -> {'ACCRUING but z still null -- forward evidence has NOT started' if not nz else 'z live'}\n")

    # ---- 4. clock row counts (is forward evidence actually accruing?) ----
    print("=== FORWARD CLOCK ACCRUAL (are rows landing daily?) ===")
    for f in ("kimchi_premium", "stablecoin_supply", "cny_premium", "onchain_activity"):
        fp = Path(f"data/{f}.jsonl")
        if fp.exists():
            rows = [json.loads(x) for x in fp.read_text("utf-8").splitlines() if x.strip()]
            ds = sorted({r.get("date") for r in rows if r.get("date")})
            print(f"  {f:22s} rows={len(rows):3d} span {ds[0] if ds else '-'} .. {ds[-1] if ds else '-'}")
        else:
            print(f"  {f:22s} MISSING")

    # ARTIFACT. This organ was print-only for its whole life, so nothing downstream -- including
    # check_fence_yield, which classifies a fence by the verdicts it has produced -- could tell a
    # clean run from a run that never happened. UNMEASURED is a real status here, not a filler:
    # every upstream fetch above is network-dependent, and a failed fetch must never read as "no
    # drift detected" (L1.28a).
    blocked = [r for r in dist if not r["production_capital_allowed"]
               and r["dist_verdict"] in ("DRIFT", "SHIFT")]
    if not dist:
        status = "UNMEASURED"
    elif any(r["dist_verdict"] == "SHIFT" for r in dist):
        status = "SHIFT"
    elif any(r["dist_verdict"] == "DRIFT" for r in dist):
        status = "DRIFT"
    elif all(r["dist_verdict"] == "INSUFFICIENT-DATA" for r in dist):
        status = "UNMEASURED"
    else:
        status = "OK"
    payload = {"generated": datetime.now(UTC).isoformat(), "status": status, "axes": dist,
               "capital_blocked": [r["axis"] for r in blocked],
               "note": "UNMEASURED means no axis series was fetched (upstream fetch failed) or "
                       "every window was too short -- never that the distribution is stable."}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    print(f"\nDIST-SHIFT REVALIDATION: {status} ({len(dist)} axes) -> "
          f"{_OUT.relative_to(_ROOT)}")


if __name__ == "__main__":
    main()
