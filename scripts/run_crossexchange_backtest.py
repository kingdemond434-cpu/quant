"""NEW ALPHA FAMILY -- cross-exchange funding dispersion, sampled on the THIN-PAIR cohort.

ECONOMIC HYPOTHESIS: when a perp's funding on ONE venue is rich relative to the cross-venue
consensus, longs are crowded on that venue -> fade it; when relatively cheap, lean long.
This is VENUE-RELATIVE crowding -- orthogonal to the market-wide leverage demand the existing
single-venue carry sleeve trades. Two sleeves are built on the same 8h panel:
  * xexch_dispersion  -- the new signal, -zscore(binance_funding - cross_venue_mean)
  * single_venue_carry -- baseline, -zscore(binance_funding); used to MEASURE orthogonality
Both run the real gauntlet (DSR/PBO/Reality-Check via the validator), net of cost + funding.

COHORT (R0295 redesign, 2026-08-12): the original run hardcoded 14 large caps -- the cohort
most heavily cross-venue arbitraged, where venue funding converges BY CONSTRUCTION, i.e. the
signal was sampled exactly where its variance is minimised (design inversion vs §42's named
ground 'thin-pair cross-venue funding'). The universe is now DISCOVERED: the thinnest
cross-venue-resolvable Binance USDT perps by 24h quote volume (bottom-K, dead-market floor),
joined to OKX through the VERIFIED resolver (R0294: both name forms, ctVal collision guard,
counted misses). The large-cap run stays priced as a prior construction (trial accounting
below); a null from THAT cohort was evidence about the cohort, not the mechanism.
HONESTY: ~90-day overlap = ~1 regime -> PRELIMINARY; forward validation still required. Nothing
fabricated. Writes web/crossexchange_backtest.json and registers the candidate.
REFUSAL PATH (L1.41, ledger R0297): every failed venue fetch is recorded in a `blocked` dict and
surfaced in the artifact + stdout -- a symbol never vanishes silently. Universe discovery
failure exits UNMEASURED rather than falling back to the large-cap hardcode; fewer than 2
venues with data, or a panel below the 6-symbol minimum, exits UNMEASURED instead of computing
on survivors.

    python scripts/run_crossexchange_backtest.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.crypto_source import (
    fetch_funding,
    fetch_klines,
    list_perp_symbols,
    perp_quote_volumes,
)
from libs.data.multiexchange import (
    OkxResolution,
    fetch_bybit_funding,
    fetch_okx_funding,
    fetch_okx_instruments,
    resolve_okx,
)
from libs.research.ic import evaluate_signal
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_OUT = Path("web/crossexchange_backtest.json")
_PPY = 3 * 365.0                              # 8h funding periods per year
_COST = 0.0005
_FAIL = ["edge crowds/decays", "venue convergence", "thin sample (~1 regime)",
         "cost exceeds edge", "thin-book data quality"]
_VENUES = ("binance", "bybit", "okx")
_MIN_SYMBOLS = 6                              # min panel width; threshold unchanged from day one
_THIN_COHORT_SIZE = 40                        # bottom-of-book cohort width (runtime cap)
_MIN_QUOTE_VOL_USD = 10_000.0                 # dead-market floor: no book, no funding to earn
# Garden-of-forking-paths accounting (screen-on-discovery duty item 3): constructions TRIED in
# this program, not just the kept one. 2 sleeves x {14-large-cap 2026-08-01, thin-pair 2026-08-12}.
_CONSTRUCTIONS_TRIED = 4


def _universe() -> tuple[list[str], OkxResolution, dict[str, object]]:
    """§42 thin-pair cohort: the THINNEST cross-venue-resolvable Binance perps by 24h volume.

    Rule is frozen in code (bottom-_THIN_COHORT_SIZE among OKX-verified names above the
    dead-market floor) -- deterministic and mechanism-blind, chosen BEFORE any returns are
    seen. Discovery failure raises: a silent fallback to large caps would resurrect the
    R0295 inversion invisibly."""
    perps = list_perp_symbols()
    vols = perp_quote_volumes()
    res = resolve_okx(perps, fetch_okx_instruments())
    active = [s for s in res.resolved if vols.get(s, 0.0) >= _MIN_QUOTE_VOL_USD]
    thin = sorted(active, key=lambda s: vols[s])[:_THIN_COHORT_SIZE]
    accounting: dict[str, object] = {
        "binance_perps": len(perps),
        # R0294 part 3: the resolver's misses are COUNTED into the artifact, never silent.
        "okx_resolve": {"attempted": res.attempted, "resolved": len(res.resolved),
                        "dropped": len(res.dropped),
                        "dropped_examples": dict(sorted(res.dropped.items())[:8])},
        "cohort_rule": (f"bottom-{_THIN_COHORT_SIZE} by 24h quoteVolume among OKX-resolvable "
                        f"active perps with volume >= ${_MIN_QUOTE_VOL_USD:,.0f}"),
        "prior_constructions": ["14 hardcoded large caps (2026-08-01) -- design inversion, "
                                "R0295: null there was evidence about the cohort"],
        "median_cohort_quote_vol_usd": (float(pd.Series([vols[s] for s in thin]).median())
                                        if thin else None),
    }
    return thin, res, accounting


def _fetch_venues(sym: str, start_ms: int, blocked: dict[str, str],
                  inst: str | None = None) -> dict[str, pd.Series | pd.DataFrame]:
    """All fetches for one symbol (`inst` = VERIFIED OKX instId from resolve_okx). Every
    failure or empty response is RECORDED in `blocked` (L1.41 refusal path: absent input is
    reported, never silently OK)."""
    fetchers = {
        "binance": lambda: fetch_funding(sym, start_ms=start_ms).set_index("timestamp")["funding"],
        "bybit": lambda: fetch_bybit_funding(sym).set_index("timestamp")["funding"],
        "okx": lambda: fetch_okx_funding(sym, inst=inst).set_index("timestamp")["funding"],
        "klines": lambda: fetch_klines(sym, interval="8h", start_ms=start_ms),
    }
    got: dict[str, pd.Series | pd.DataFrame] = {}
    for venue, fetch in fetchers.items():
        try:
            v = fetch()
        except Exception as e:  # blind-except intentional (BLE001)
            blocked[f"{sym}:{venue}"] = f"{type(e).__name__}: {e}"
            continue
        if v.empty:
            blocked[f"{sym}:{venue}"] = "empty response (no rows)"
            continue
        got[venue] = v
    return got


def _panel(universe: list[str], res: OkxResolution,
           ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str], list[str]]:
    """Aligned 8h panels: cross-venue funding dispersion, binance funding, next-period return.

    Thin names are often listed on only one of {Bybit, OKX}; requiring all three venues would
    quietly re-select the liquid cohort (the inversion again, one layer down). A symbol enters
    with binance + klines + AT LEAST ONE other venue; the consensus is the mean over the venues
    that exist for THAT symbol. Also returns `blocked` (failed fetch -> reason) and the venues
    that returned data anywhere, so a shrunken panel is visible instead of silently reported
    over the survivors (R0297)."""
    disp, bfund, fwd = {}, {}, {}
    blocked: dict[str, str] = {}
    venues_ok: set[str] = set()
    start_ms = int((pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=110)).timestamp() * 1000)
    for sym in universe:
        got = _fetch_venues(sym, start_ms, blocked, inst=res.resolved.get(sym))
        have = [v for v in _VENUES if v in got]
        venues_ok |= set(have)
        if "binance" not in have or "klines" not in got or len(have) < 2:
            if "binance" in have and "klines" in got:   # fetches fine, listing too narrow
                blocked[f"{sym}:panel"] = f"only {have} returned data -- dispersion needs >=2"
            continue                  # fetch failures are already named in `blocked`
        f = pd.DataFrame({v: got[v] for v in have}).sort_index().ffill().dropna()
        mean = f.mean(axis=1)
        disp[sym] = f["binance"] - mean               # venue-relative crowding (the new signal)
        bfund[sym] = f["binance"]
        px = got["klines"].set_index("timestamp")["close"].astype(float).reindex(f.index).ffill()
        fwd[sym] = px.pct_change().shift(-1)
    d = pd.DataFrame(disp).sort_index()
    return (d, pd.DataFrame(bfund).reindex(d.index), pd.DataFrame(fwd).reindex(d.index),
            blocked, sorted(venues_ok))


def _xs_weights(signal: pd.DataFrame) -> pd.DataFrame:
    z = signal.sub(signal.mean(axis=1), axis=0).div(signal.std(axis=1) + 1e-9, axis=0)
    w = -z                                            # fade the (relatively) rich-funding names
    w = w.sub(w.mean(axis=1), axis=0)                 # market-neutral
    return w.div(w.abs().sum(axis=1) + 1e-9, axis=0)


def _ret(weights: pd.DataFrame, fwd: pd.DataFrame, bfund: pd.DataFrame) -> np.ndarray:
    price = (weights * fwd).sum(axis=1)
    funding = -(weights * bfund).sum(axis=1)          # earn/pay binance funding on the book
    cost = _COST * weights.diff().abs().sum(axis=1)
    return (price + funding - cost).dropna().to_numpy()


def main() -> None:
    universe, res, discovery = _universe()
    if len(universe) < _MIN_SYMBOLS:
        raise SystemExit(
            f"UNMEASURED: universe discovery produced {len(universe)} cross-venue-resolvable "
            f"thin perps (<{_MIN_SYMBOLS}); refusing the large-cap fallback. "
            f"okx_resolve={discovery.get('okx_resolve')}")
    disp, bfund, fwd, blocked, venues_ok = _panel(universe, res)
    if blocked:                   # L1.41: every dropped fetch is NAMED before any verdict prints
        print(f"BLOCKED fetches ({len(blocked)}):")
        for key, why in blocked.items():
            print(f"  {key}: {why}")
    if len(venues_ok) < 2:        # dispersion vs a "cross-venue mean" of one venue is no signal
        raise SystemExit(
            f"UNMEASURED: only {len(venues_ok)}/{len(_VENUES)} venues returned data "
            f"({', '.join(venues_ok) or 'none'}) -- cross-venue dispersion needs >=2 venues; "
            f"refusing to compute on a degenerate panel. blocked={blocked}")
    if disp.shape[1] < _MIN_SYMBOLS:
        raise SystemExit(
            f"UNMEASURED: insufficient cross-venue panel -- {disp.shape[1]}/{len(universe)} "
            f"symbols resolved (<{_MIN_SYMBOLS} minimum). blocked={blocked}")
    sleeves = {
        "xexch_dispersion": _ret(_xs_weights(disp), fwd, bfund),
        "single_venue_carry": _ret(_xs_weights(bfund), fwd, bfund),
    }
    n = min(len(v) for v in sleeves.values())
    matrix = np.column_stack([v[-n:] for v in sleeves.values()])
    sharpes = np.array([sharpe_ratio(v[v != 0.0]) for v in sleeves.values()])
    # per-candidate gates (gap #87 flip, principal-ruled 2026-07-29); thresholds unchanged
    campaign = campaign_gate_stats(matrix)
    corr = float(np.corrcoef(matrix[:, 0], matrix[:, 1])[0, 1])

    fwd_arr = fwd.to_numpy()                              # IC = rank-corr of signal vs fwd return
    sig = {"xexch_dispersion": (-disp).to_numpy(), "single_venue_carry": (-bfund).to_numpy()}

    results = []
    # enumerate order == column_stack order over `sleeves`, so `col` is the sleeve's matrix column
    for col, (name, r) in enumerate(sleeves.items()):
        active = r[r != 0.0]
        ann = round(float(sharpe_ratio(active) * np.sqrt(_PPY)), 2) if len(active) > 5 else 0.0
        v = (validate(active, hypothesis=Hypothesis(
            family=Family.CARRY, subtype=name, symbol="CRYPTO", params={},
            mechanism=MechanismType.RISK_PREMIUM, edge_source=name, failure_modes=_FAIL),
            periods_per_year=_PPY,        # 8h funding bars, 1095/yr (R0086)
            n_trials=_CONSTRUCTIONS_TRIED, sharpe_estimates=sharpes, returns_matrix=matrix,
            campaign=campaign, column=col)
            if len(active) >= 250 else None)
        ic = evaluate_signal(sig[name], fwd_arr, periods_per_year=_PPY)
        results.append({"sleeve": name, "ann_sharpe": ann, "n_obs": len(active),
                        "gates": f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250",
                        "pbo": round(float(v.metrics.pbo), 3) if v else None,
                        "rc_p": round(float(v.metrics.reality_p), 3) if v else None,
                        "survived": bool(v.survived) if v else False,
                        "failed_gates": [k for k, ok in v.gates.items() if not ok] if v else [],
                        "ic": ic["mean_ic"], "ic_ir": ic["ic_ir"], "hit_rate": ic["hit_rate"],
                        "ic_decay": ic["ic_decay"]})

    bars = int(disp.shape[0])
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "family": "cross-exchange funding dispersion", "venues": venues_ok,
        "cohort": "thin-pair (§42 named ground; R0295 redesign)",
        "frequency": "8h", "symbols": int(disp.shape[1]), "bars": bars,
        "calendar_days": round(bars / 3, 1),
        "constructions_tried": _CONSTRUCTIONS_TRIED,
        # R0297 / L1.41: attempted-vs-resolved accounting; dropped fetches are named with reason,
        # so a panel that shrank is visible in the artifact, never silently OK. R0294: the
        # resolver's own attempted/resolved/dropped counters ride along in `universe_discovery`.
        "universe_discovery": discovery,
        "panel_accounting": {"symbols_attempted": len(universe),
                             "symbols_resolved": int(disp.shape[1]),
                             "blocked": blocked},
        "dispersion_vs_carry_correlation": round(corr, 3),
        "orthogonal": abs(corr) < 0.4,
        # campaign-level legacy PBO/RC kept as SEARCH-PROCEDURE diagnostics (gap #87); the gate
        # values are per-sleeve now -- see results[*].pbo / results[*].rc_p.
        "pbo": (round(float(campaign.legacy_pbo.pbo), 3)
                if campaign is not None and campaign.legacy_pbo is not None else None),
        "reality_check_p": (round(float(campaign.legacy_rc.p_value), 3)
                            if campaign is not None and campaign.legacy_rc is not None else None),
        "results": results,
        "honesty": ("~90-day venue overlap = ~1 regime; PRELIMINARY. The point is BREADTH: a new "
                    "orthogonal data family. Forward validation still required before production."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"panel: {disp.shape[1]}/{len(universe)} thin-cohort symbols resolved on "
          f"{len(venues_ok)}/{len(_VENUES)} venues; {len(blocked)} blocked fetches; "
          f"okx_resolve {discovery['okx_resolve']}")
    for r in results:
        print(f"  {r['sleeve']:20} annSharpe~{r['ann_sharpe']:6} n={r['n_obs']:4} "
              f"gates={r['gates']:5} survived={r['survived']}")
    print(f"dispersion vs carry corr = {corr:.2f} -> orthogonal={out['orthogonal']} "
          f"over {out['calendar_days']}d (PRELIMINARY)")


if __name__ == "__main__":
    main()
