"""Run the desk's OWN generator families against a bar-permutation null on real OKX bars.

THE QUESTION. Every one of the twelve declared families is a rule over the SEQUENCE of bars. The
gauntlet currently asks whether a candidate beats a cohort (Romano-Wolf), whether it survives
resampled blocks (bootstrap), and whether it beats parametric draws (positive_control). None of
those asks the one question a price-pattern rule lives or dies on: is there information in the
ORDER, or is the rule harvesting drift the asset would have handed a coin-flip?

THE CONTROL THAT MAKES THE ANSWER READABLE. `buy_and_hold` is run alongside every rule. The
permutation reorders the close-to-close returns without changing them, so buy-and-hold's Sharpe is
identical on every draw and its p-value measures the permutation's OWN bias rather than any skill
-- it belongs up near 1.0. If it lands low, the null is systematically easier to beat than the
real series and EVERY p-value in the report is inflated by that amount. This is not hypothetical:
it is exactly what the source's two-independent-permutations construction did (p = 0.007), and it
is why `bar_permutation` carries each gap on its own bar. The report states the reading rather
than quietly handing back significance the construction manufactured.

This writes reports/permutation_null.json and asserts nothing. It is a measurement, not a gate --
`libs/validation/bar_permutation.py` explains at length why adding a rejection here would be the
double-correction defect the 2026-08-01 audit was written to stop.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.generators import GENERATORS, net_returns
from libs.autodiscovery.models import MarketSeries
from libs.validation.bar_permutation import (
    DEFAULT_PERMUTATIONS,
    Bars,
    invalid_bars,
    permutation_moment_report,
    permutation_pvalue,
    permute_bars,
    to_log_bars,
)

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "reports" / "permutation_null.json"
_OKX = "https://www.okx.com"
_PAGE = 100
_REQ_SLEEP = 0.12
_PPY = 365.0
#: Rules needing data the daily OHLC feed does not carry degrade to flat by design
#: (generators.py header). A flat rule has no Sharpe and would burn permutations to learn that.
_MIN_ACTIVE_FRACTION = 0.01


def _okx_get(url: str, tries: int = 4) -> list[list[str]]:
    last: Exception | None = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as fh:
                body = json.loads(fh.read().decode())
            if str(body.get("code")) != "0":
                raise RuntimeError(f"okx code={body.get('code')} msg={body.get('msg')}")
            rows: list[list[str]] = body.get("data") or []
            return rows
        except Exception as exc:
            last = exc
            time.sleep(1.0)
    raise RuntimeError(f"okx GET failed after {tries}: {url} :: {last}")


def fetch_ohlc(base: str, days: int) -> dict[str, np.ndarray]:
    """Daily CONFIRMED OHLC perp bars. Only confirm=="1" -- the newest row is the in-progress bar
    and its "close" is the current price, which would put a partial bar at the panel edge."""
    rows: list[list[str]] = []
    cursor = ""
    for _ in range(max(1, -(-days // _PAGE))):
        page = _okx_get(f"{_OKX}/api/v5/market/history-candles?instId={base}-USDT-SWAP"
                        f"&bar=1D&limit={_PAGE}{cursor}")
        if not page:
            break
        rows.extend(page)
        cursor = f"&after={page[-1][0]}"
        time.sleep(_REQ_SLEEP)
    good = [r for r in rows if len(r) >= 9 and r[8] == "1"]
    good.sort(key=lambda r: int(r[0]))
    return {k: np.array([float(r[i]) for r in good], dtype="float64")
            for k, i in (("open", 1), ("high", 2), ("low", 3), ("close", 4))}


def _series(b: Bars) -> MarketSeries:
    """Log-space Bars -> the price-space MarketSeries the generators expect."""
    return MarketSeries(close=np.exp(b.close), high=np.exp(b.high), low=np.exp(b.low))


def _sharpe(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    if r.size < 30:
        return float("nan")
    sd = float(np.std(r, ddof=1))
    if sd <= 1e-12:
        return float("nan")
    return float(np.mean(r) / sd * np.sqrt(_PPY))


def _buy_and_hold(s: MarketSeries) -> np.ndarray:
    return np.ones(len(s.close))


def _rules() -> list[dict[str, Any]]:
    """Every declared family x param variant, plus the buy-and-hold control."""
    out: list[dict[str, Any]] = [{
        "family": "CONTROL", "subtype": "buy_and_hold", "params": {}, "fn": _buy_and_hold,
        "control": True,
    }]
    for spec in GENERATORS:
        for variant in spec.param_variants:
            out.append({"family": str(spec.family), "subtype": spec.subtype,
                        "params": dict(variant), "fn": spec.position_fn, "control": False})
    return out


def _score(rule: dict[str, Any], s: MarketSeries) -> tuple[float, float]:
    """(sharpe, active fraction). Returns NaN sharpe when the rule degraded to flat."""
    try:
        pos = np.asarray(rule["fn"](s, rule["params"]), dtype="float64")
    except Exception:
        return float("nan"), 0.0
    active = float(np.mean(pos != 0.0)) if pos.size else 0.0
    if active < _MIN_ACTIVE_FRACTION:
        return float("nan"), active
    return _sharpe(net_returns(s, pos)), active


def run(symbol: str, days: int, n_perm: int, seed: int) -> dict[str, Any]:
    raw = fetch_ohlc(symbol, days)
    n = len(raw["close"])
    if n < 200:
        raise RuntimeError(f"{symbol}: only {n} confirmed daily bars")
    bars = to_log_bars(raw["open"], raw["high"], raw["low"], raw["close"])
    bad = int(invalid_bars(bars).sum())

    rules = _rules()
    real = [_score(r, _series(bars)) for r in rules]

    rng = np.random.default_rng(seed)
    perm_stats: list[list[float]] = [[] for _ in rules]
    kept: list[Bars] = []
    t0 = time.time()
    for k in range(n_perm):
        p = permute_bars(bars, rng=rng)
        if len(kept) < 60:
            kept.append(p)
        ps = _series(p)
        for i, r in enumerate(rules):
            perm_stats[i].append(_score(r, ps)[0])
        if (k + 1) % 100 == 0:
            print(f"  {symbol} {k + 1}/{n_perm} [{time.time() - t0:5.1f}s]", flush=True)

    rows: list[dict[str, Any]] = []
    for i, r in enumerate(rules):
        sharpe, active = real[i]
        stats = np.array(perm_stats[i], dtype="float64")
        usable = int(np.sum(np.isfinite(stats)))
        try:
            pval: float | None = permutation_pvalue(sharpe, stats)
            note = None
        except ValueError as exc:
            pval, note = None, str(exc)
        rows.append({
            "family": r["family"], "subtype": r["subtype"], "params": r["params"],
            "control": r["control"], "real_ann_sharpe": None if np.isnan(sharpe) else sharpe,
            "active_fraction": active, "usable_permutations": usable, "p_value": pval,
            "permuted_sharpe_median": (float(np.nanmedian(stats)) if usable else None),
            "permuted_sharpe_p95": (float(np.nanpercentile(stats, 95)) if usable else None),
            "unmeasurable": note,
        })

    control = next(r for r in rows if r["control"])
    moments = permutation_moment_report(bars, kept)
    vr = moments.get("variance_ratio_median")
    return {
        "symbol": symbol, "n_bars": n, "invalid_input_bars": bad,
        "n_permutations": n_perm, "seed": seed,
        "moments": moments,
        "control": control,
        "control_reading": _read_control(control["p_value"], vr),
        "rules": sorted(
            [r for r in rows if not r["control"]],
            key=lambda r: (r["p_value"] is None, r["p_value"] if r["p_value"] is not None else 1.0),
        ),
    }


def _read_control(p: float | None, variance_ratio: float | None) -> str:
    """What the buy-and-hold p-value says about every OTHER p-value in the report."""
    if p is None:
        return ("UNMEASURED: the buy-and-hold control produced no usable statistic, so the "
                "permutation's own bias is unknown and no p-value here is interpretable.")
    vr = f"{variance_ratio:.4f}" if variance_ratio is not None else "unmeasured"
    if p < 0.40:
        return (f"BIASED: buy-and-hold scores p={p:.4f} on a null that preserves its entire return "
                f"distribution -- it has NO timing skill by construction, so a low reading is the "
                f"permutation flattering the real series, not evidence. Permuted close-to-close "
                f"variance ratio {vr} (must be ~1.0; drifting away means the gap/bar pairing "
                "broke). Every p-value below is inflated by roughly this much and none should be "
                "read as evidence of edge until the construction is corrected.")
    return (f"CLEAN: buy-and-hold scores p={p:.4f}, high as a zero-skill rule should be on a null "
            f"that reorders its returns without changing them (variance ratio {vr}, expected "
            "~1.0). The permutation is not measurably biased and the p-values below read as "
            "written.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTC,ETH,SOL")
    ap.add_argument("--days", type=int, default=800)
    ap.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    ap.add_argument("--seed", type=int, default=90210)
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    symbols = [s.strip().upper() for s in str(args.symbols).split(",") if s.strip()]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "RUNNING",
        "question": ("do the desk's twelve declared families carry information in the ORDER of "
                     "bars, or are they harvesting drift the asset hands out for free"),
        "method": ("libs.validation.bar_permutation on okx:history-candles:1D:confirmed; every "
                   "GeneratorSpec x param_variant scored by generators.net_returns; buy-and-hold "
                   "run as the control that measures the permutation's own bias"),
        "source": "okx:history-candles:1D:confirmed",
        "symbols": symbols, "results": [], "blocked": {},
    }
    for sym in symbols:
        print(f"== {sym} ==", flush=True)
        try:
            doc["results"].append(run(sym, args.days, args.permutations, args.seed))
        except Exception as exc:
            doc["blocked"][sym] = str(exc)
        out.write_text(json.dumps(doc, indent=2), "utf-8")
    doc["status"] = "MEASURED" if doc["results"] else "BLOCKED"
    out.write_text(json.dumps(doc, indent=2), "utf-8")
    print(f"wrote {out} :: {doc['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
