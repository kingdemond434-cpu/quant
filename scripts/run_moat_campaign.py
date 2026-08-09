#!/usr/bin/env python3
"""Score the moat microstructure candidates against the RECORDED TAPE, through the real gauntlet.

WHY THIS RUNS ON THE BOX AND NOWHERE ELSE. The features here need 20-level depth at ~4s cadence.
That history is not purchasable at retail -- it exists only because this desk has been recording
it since 2026-07-21. Daily OHLCV can be pulled from any public venue anywhere; this cannot.

WHAT IT IS FOR. On 2026-08-01 the desk ran 129 textbook mechanisms (Bollinger, RSI, Donchian,
CMF, golden cross...) across 10 liquid pairs on daily bars and got 0 survivors -- with a maximum
out-of-sample Sharpe of 0.100 across the whole set. That was not the gate being harsh; those
mechanisms are picked clean. This campaign asks the same question of the one dataset the crowd
does not have.

DELIBERATELY MODEST SCOPE. Four mechanisms, not four hundred. The desk's own audit measured that
campaign WIDTH buys nothing (N=420/100/30 all scored identical power) while campaign LENGTH buys
everything, so a wide sweep over microstructure variants would spend multiplicity budget for no
resolution. Four pre-registered constructions across the recorded symbols is the shape that can
actually resolve.

    .venv/bin/python scripts/run_moat_campaign.py [--venue fut] [--bar-ms 60000]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402

from libs.autodiscovery.models import Family, Hypothesis  # noqa: E402
from libs.autodiscovery.validation import campaign_gate_stats, validate  # noqa: E402
from libs.research.moat_microstructure import (  # noqa: E402
    CANDIDATES,
    MOAT,
    bar_returns,
    partitions,
    read_partition,
    resample,
)
from libs.validation.campaign_design import (  # noqa: E402
    DEFAULT_TARGET_SHARPE,
    preflight,
)
from libs.validation.dsr import sharpe_ratio  # noqa: E402
from libs.validation.economic_prior import MechanismType  # noqa: E402

_OUT = Path("reports/moat_campaign.json")
#: validate() refuses under 250 observations, and a campaign that cannot clear that is not a
#: weak result -- it is no result. Reported as BLOCKED with the shortfall named.
_MIN_BARS = 250

_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="microstructure", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY,
    edge_source="recorded L2 depth and aggressor-signed flow",
    failure_modes=["decays as venue latency and maker competition change",
                   "depth snapshots at 4s miss sub-second refills",
                   "one venue's book is not the consolidated book"],
)


def load_bars(symbol: str, venue: str, bar_ms: int) -> list[Any]:
    """Every recorded partition for one symbol, folded into bars.

    Reads ALL partitions rather than a recent window: the binding constraint measured by the gate
    audit is sample length, and this tape is the shortest history the desk owns.
    """
    parts = partitions(symbol, venue)
    if not parts:
        return []
    def _stream() -> Any:
        for p in parts:
            yield from read_partition(p)
    return resample(_stream(), ms=bar_ms)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", default="fut", help="fut | spot | bybit")
    ap.add_argument("--bar-ms", type=int, default=60_000)
    ap.add_argument("--max-symbols", type=int, default=12)
    args = ap.parse_args()

    root = MOAT / args.venue
    symbols = sorted(d.name for d in root.iterdir() if d.is_dir()) if root.is_dir() else []
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _OUT.parent.mkdir(parents=True, exist_ok=True)

    if not symbols:
        _OUT.write_text(json.dumps({
            "generated": stamp, "status": "BLOCKED", "venue": args.venue,
            "blocker": f"no recorded symbols under {root}",
            "consequence": "the moat candidates cannot be scored; this is the ONLY dataset the "
                           "desk owns that the crowd does not, so an unscored tape is the "
                           "largest unexploited asset on the desk",
            "rows": []}, indent=2), "utf-8")
        print(f"BLOCKED: no recorded symbols under {root}")
        return 1

    names, series, per_symbol = [], [], {}
    for sym in symbols[:args.max_symbols]:
        bars = load_bars(sym, args.venue, args.bar_ms)
        per_symbol[sym] = len(bars)
        if len(bars) < _MIN_BARS:
            continue
        for cname, fn in CANDIDATES.items():
            r = bar_returns(fn(bars), bars)
            if len(r) >= _MIN_BARS and float(np.std(r)) > 0:
                names.append(f"{cname}:{sym}")
                series.append(r)
        print(f"  {sym}: {len(bars)} bars", flush=True)

    if len(series) < 2:
        _OUT.write_text(json.dumps({
            "generated": stamp, "status": "BLOCKED", "venue": args.venue,
            "blocker": f"only {len(series)} scorable candidate(s); need >=2 for cohort statistics",
            "bars_per_symbol": per_symbol, "min_bars_required": _MIN_BARS,
            "consequence": "not a weak result -- NO result. The tape is too short at this bar "
                           "size. Either wait for it to accrue or lower --bar-ms, which trades "
                           "sample length against per-bar signal.",
            "rows": []}, indent=2), "utf-8")
        print(f"BLOCKED: {len(series)} scorable candidates (need >=2). "
              f"bars/symbol: {per_symbol}")
        return 1

    ppy = 365.0 * 24.0 * 3600_000.0 / args.bar_ms      # bars per year at this cadence
    _TARGET_SR = DEFAULT_TARGET_SHARPE

    # THE PANEL IS CHOSEN FOR POWER, not by whichever series is shortest.
    #
    # `T = min(len(r) for r in series)` truncated EVERY candidate to the worst one. Measured
    # 2026-08-05: the moat campaign ran at T=1,065 one-minute bars -- under eighteen hours --
    # against a tape the desk holds gigabytes of, because one late-added symbol capped the panel
    # and every other column was cropped to match it. Sample LENGTH is the single lever the desk's
    # own Type-II report names ("Sample LENGTH and pooling are the levers; alpha is not"), and this
    # line was throwing away almost all of it to keep a column that could not carry a test anyway.
    #
    # Dropping a column costs one hypothesis. Keeping it cost every other hypothesis its history,
    # AND raised N for all of them -- both of the two things that destroy power, to save one
    # candidate. So the panel is now selected by maximising the campaign's OWN measured power:
    # sort by length, and for each prefix price preflight(k columns, T_k observations). This is a
    # DESIGN choice made before the compute is spent, not a filter on results -- no candidate is
    # dropped for what it scored, only for how little history it brings.
    # THE OBJECTIVE IS EXPECTED DISCOVERIES, k * power(k) -- NOT power alone.
    #
    # Maximising power by itself drives k to its minimum, because every added hypothesis tightens
    # the multiplicity bar for all of them. On the real shape that picks k=2 at 41.5% power and
    # throws away ten live hypotheses to do it -- which is the opposite of this desk's stated
    # philosophy: many weak uncorrelated edges, never a narrow search. k * power(k) prices what is
    # actually wanted, the expected NUMBER of true edges the campaign will surface:
    #
    #     k=2  0.83     k=6  0.96     k=10  1.02
    #     k=11 1.03  <- chosen: every column that brings history is kept
    #     k=12 0.007 <- the one short column collapses the panel by a factor of 150
    #
    # So the rule keeps almost everything and drops only the columns that destroy the panel, which
    # is the honest reading of the trade-off rather than a preference for a narrow search.
    order = sorted(range(len(series)), key=lambda i: -len(series[i]))
    best_k, best_yield, best_power, ladder = len(order), -1.0, 0.0, []
    for k in range(2, len(order) + 1):
        keep = order[:k]
        t_k = min(len(series[i]) for i in keep)
        design = preflight(k, t_k, ppy=ppy)
        expected = k * float(design.power_at_target)
        ladder.append({"k": k, "T": int(t_k),
                       "power_at_target": round(float(design.power_at_target), 4),
                       "expected_discoveries": round(expected, 4),
                       "hurdle_annual_sharpe": round(float(design.hurdle_annual_sharpe), 3)})
        if expected > best_yield:
            best_k, best_yield, best_power = k, expected, float(design.power_at_target)
    keep_idx = sorted(order[:best_k])
    dropped = [names[i] for i in range(len(names)) if i not in set(keep_idx)]
    names = [names[i] for i in keep_idx]
    series = [series[i] for i in keep_idx]

    T = min(len(r) for r in series)
    m = np.column_stack([r[-T:] for r in series])
    print(f"campaign {m.shape[1]} candidates x {m.shape[0]} bars "
          f"(panel chosen to maximise expected discoveries {best_yield:.2f} = "
          f"{m.shape[1]} x {best_power:.1%} at true SR{_TARGET_SR:g}; "
          f"{len(dropped)} short column(s) dropped)", flush=True)
    if dropped:
        print(f"  dropped for insufficient history: {', '.join(dropped[:6])}"
              f"{'...' if len(dropped) > 6 else ''}", flush=True)

    gates = campaign_gate_stats(m)
    if gates is None:
        print("campaign_gate_stats returned None")
        return 1
    sh = np.array([sharpe_ratio(m[:, i]) for i in range(m.shape[1])])
    # CAN THIS CAMPAIGN SEE AN EDGE AT ALL -- asked BEFORE the compute is spent, not after.
    # `n_trials` here is `m.shape[1]`, an ACCIDENT OF GENERATION VOLUME rather than a design
    # decision, and until now nothing computed what that N did to the campaign's resolving power.
    # The measured consequence is on the record: at T=310 / N=420 the DSR hurdle is an annualised
    # Sharpe of 5.04 and the power against a TRUE annual Sharpe of 3 is 2.98%. The desk's
    # 420-tested / 0-survivors history has been read repeatedly as a fact about the market; it is
    # substantially a fact about the INSTRUMENT (L1.25 branch 1: "is the instrument broken?").
    # `informative_null()` is what makes that difference readable in the artifact instead of
    # arguable after the fact.
    #
    # IT NEVER BLOCKS. An UNDERPOWERED verdict LABELS the result; it does not veto the run,
    # shrink the candidate set, or move a gate -- the campaign still runs and still reports in
    # full (L1.25a: null streaks throttle nothing; L1.28b(f): acquisition is never cut).
    design = preflight(int(m.shape[1]), int(m.shape[0]), ppy=ppy)
    print(f"design: {design.verdict} -- hurdle annSR {design.hurdle_annual_sharpe:.2f}, "
          f"power at target {design.power_at_target:.1%}, "
          f"a zero-survivor result {'IS' if design.informative_null() else 'is NOT'} "
          "evidence about the market", flush=True)

    rows: list[dict[str, Any]] = []
    for i, nm in enumerate(names):
        # `ppy` is derived from the recorded bar width above -- the same number the row's own
        # ann_sharpe uses, so the artifact and the verdict can no longer disagree (R0086).
        v = validate(m[:, i], hypothesis=_HYP, periods_per_year=ppy,
                     n_trials=m.shape[1], sharpe_estimates=sh,
                     returns_matrix=m, campaign=gates, column=i)
        # THE FIELDS THAT MAKE A ROW READABLE BY THE SURVIVOR PIPELINE, and their absence made
        # this campaign's output unreachable. `screen_conversion.is_scored_row` requires an effect
        # estimate AND a sample size; these rows carried neither in a recognised spelling, so the
        # ONE dataset the desk owns that the crowd does not produced candidates that could never
        # be admitted to a forward slot. `sharpe_per_period` is the effect in the same currency
        # the resolution formula uses -- over n periods a strategy's t-stat is SR_period*sqrt(n),
        # exactly as an IC's is IC*sqrt(n) -- so the two are interchangeable there and neither is
        # rescaled to flatter the other.
        rows.append({"name": nm, "survived": bool(v.survived),
                     "n": int(m.shape[0]), "n_eff": float(m.shape[0]),
                     "sharpe_per_period": float(sharpe_ratio(m[:, i])),
                     "ic": float(sharpe_ratio(m[:, i])),
                     "ic_is_sharpe_per_period": True,
                     "horizon_ms": int(args.bar_ms),
                     "periods_per_year": float(ppy),
                     "ann_sharpe": float(sharpe_ratio(m[:, i]) * np.sqrt(ppy)),
                     "failed": [g for g, ok in v.gates.items() if not ok],
                     "dsr": float(v.metrics.dsr), "pbo": float(v.metrics.pbo),
                     "reality_p": float(v.metrics.reality_p),
                     "oos_sharpe": float(v.metrics.oos_sharpe)})
    rows.sort(key=lambda r: -float(r["ann_sharpe"]))
    surv = [r for r in rows if r["survived"]]

    report: dict[str, Any] = {
        "generated": stamp, "status": "COMPLETE", "venue": args.venue, "bar_ms": args.bar_ms, "n_candidates": len(rows), "n_obs": int(T),
           "n_survivors": len(surv), "bars_per_symbol": per_symbol,
           "reading": ("Survivors here are SCREEN survivors with zero promotion authority. They "
                       "owe pre-registered forward evidence exactly like anything else. The "
                       "column that decides whether this was worth doing is oos_sharpe: the "
                       "2026-08-01 daily-bar campaign topped out at 0.100 across 129 textbook "
                       "mechanisms."),
           # THE DESIGN, ON THE ARTIFACT. Without it a zero-survivor campaign reads as a
           # verdict on the market when it may only be a verdict on the sample. as_dict() rather
           # than a hand-spelled subset: it is the dataclass's own contract, so se_annual_sharpe,
           # periods_per_year and the power_curve travel too, and a field added to the design
           # later cannot go missing here by omission.
           "design": design.as_dict(),
           "rows": rows}
    _OUT.write_text(json.dumps(report, indent=2), "utf-8")

    print(f"\nSURVIVORS: {len(surv)} of {len(rows)}")
    print(f"{'candidate':<34} {'annSR':>8} {'OOS':>7} {'dsr':>6} {'rc_p':>6}  blockers")
    for row in rows[:15]:
        mark = "PASS" if row["survived"] else ",".join(row["failed"])[:30]
        print(f"{row['name']!s:<34} {float(row['ann_sharpe']):>8.2f} "
              f"{float(row['oos_sharpe']):>7.3f} {float(row['dsr']):>6.3f} "
              f"{float(row['reality_p']):>6.3f}  {mark}")
    best_oos = max((float(row["oos_sharpe"]) for row in rows), default=0.0)
    print(f"\nbest OOS Sharpe {best_oos:.3f}  (daily-bar textbook campaign topped out at 0.100)")
    print(f"wrote {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
