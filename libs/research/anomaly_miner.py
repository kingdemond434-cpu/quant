"""Data-first discovery: find the anomaly IN THE DATA, then ask what could explain it.

WHY THIS IS THE MISSING HALF. This desk's validation side is strong and its discovery side is not
even in the same discipline, and the numbers say so plainly. Measured 2026-09-03 from
`miner_candidates.per_source`: broker_swaps turned 248 evidence rows into 248 executable
candidates, forexfactory 44 into 107, cot 11 into 7 -- while reddit, github, quant_se,
bis_speeches, amarkets and the world crawler produced 0 from 341. Every candidate the desk owns
came from STRUCTURED DATA. Every prose source converts at exactly zero, and it is not a tuning
gap: the compiler's rule is "exact recipe or structured causal data only", so an article
structurally cannot supply a family with exact params.

So the desk had one generator class that works, and it is fed by whatever tables happen to be
lying around. Everything else -- crawlers, LLM seats, forums -- is aimed at the class that cannot
pay. The bound on discovery is not the gauntlet's strictness; it is that almost nothing reaches it.

THE INVERSION. Prose generation asks a model to imagine an edge and then looks for it. This scans
the bars the desk ALREADY OWNS for conditional structure that is unlikely under a null, and only
then asks what could explain it. The imagination of a language model stops bounding the search;
the data does. That is the one generator whose supply scales with the universe (237 tradeable
symbols x sessions x horizons) rather than with how many articles were published this week.

WHAT IT EMITS AND WHAT IT REFUSES. It emits ANOMALIES -- (symbol, condition, horizon, effect,
n, t-like statistic) -- never candidates. An anomaly is an observation; a candidate needs a named
mechanism, and naming one from a correlation is precisely the prose-to-family guessing the
compiler exists to refuse. Anomalies go to the mechanism-naming queue, where a brain must name a
cause WITH EVIDENCE or the row dies. Nothing here sets a threshold that competes with the ten
gates: every survivor still walks the same pipeline, carrying an honest trial count so deflation
charges the full width of this search.

TRIALS ARE COUNTED AND CARRIED. A scan this wide is a multiplicity machine, and hiding that would
make every downstream deflated Sharpe a lie. `trials` on the report is the real number of
(symbol, condition, horizon) cells evaluated, not the number that survived.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
_BARS = _DESK / "data" / "universe"
_OUT = _DESK / "data" / "intelligence" / "anomalies"

#: Minimum observations in a conditional cell. Below this the statistic is noise wearing a number,
#: and the desk has been burned by cells that "fired" a handful of times.
MIN_N = 60

#: |t|-like screen. NOT a verdict and NOT a gate -- purely a reporting floor so the queue receives
#: structure rather than every cell ever evaluated. The ten gates remain the only arbiter, and
#: they will deflate against `trials` below, which counts everything looked at.
REPORT_T = 3.0

#: Horizons in bars. H1 data, so 1/3/6/12/24 spans an hour to a day.
HORIZONS = (1, 3, 6, 12, 24)


@dataclass(frozen=True)
class Anomaly:
    """One conditional regularity, stated so a brain can try to explain or kill it."""

    symbol: str
    condition: str
    horizon: int
    n: int
    mean_bp: float
    t_stat: float
    hit_rate: float
    baseline_bp: float
    question: str

    def as_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = "anomaly"
        d["mechanism_status"] = "UNNAMED"
        d["note"] = ("data-first anomaly: an OBSERVATION, not a candidate. A mechanism must be "
                     "named with evidence before this can become executable.")
        return d


def _conditions(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Point-in-time conditions from bars alone. Every one is knowable at decision time.

    NOTHING HERE PEEKS. Each mask is built from data at or before the bar it labels; the forward
    return is taken strictly after. That is the difference between a discovery and an artefact,
    and it is enforced here rather than hoped for downstream.
    """
    close = df["close"].astype(float)
    ret1 = close.pct_change()
    out: dict[str, np.ndarray] = {}

    vol = ret1.rolling(24).std()
    vq = vol.rolling(500, min_periods=200).rank(pct=True)
    out["vol_top_decile"] = (vq >= 0.9).to_numpy()
    out["vol_bottom_decile"] = (vq <= 0.1).to_numpy()

    mom = close.pct_change(24)
    mq = mom.rolling(500, min_periods=200).rank(pct=True)
    out["momentum_top_decile"] = (mq >= 0.9).to_numpy()
    out["momentum_bottom_decile"] = (mq <= 0.1).to_numpy()

    rng = (df["high"].astype(float) - df["low"].astype(float)) / close
    rq = rng.rolling(500, min_periods=200).rank(pct=True)
    out["range_top_decile"] = (rq >= 0.9).to_numpy()

    idx = pd.to_datetime(df.index, utc=True, errors="coerce")
    hours = pd.Series(idx.hour, index=df.index)
    for label, hrs in (("asia", (0, 1, 2, 3, 4, 5, 6)), ("london", (7, 8, 9, 10, 11)),
                       ("ny", (13, 14, 15, 16)), ("late", (18, 19, 20, 21))):
        out[f"session_{label}"] = hours.isin(hrs).to_numpy()

    gap = (df["open"].astype(float) / close.shift(1) - 1.0)
    gq = gap.abs().rolling(500, min_periods=200).rank(pct=True)
    out["gap_top_decile"] = (gq >= 0.9).to_numpy()
    return out


def scan_symbol(symbol: str, df: pd.DataFrame) -> tuple[list[Anomaly], int]:
    """Every (condition x horizon) cell for one symbol. Returns (reportable, trials_evaluated)."""
    if df is None or len(df) < 1200:
        return [], 0
    close = df["close"].astype(float)
    conds = _conditions(df)
    found: list[Anomaly] = []
    trials = 0
    for h in HORIZONS:
        fwd = (close.shift(-h) / close - 1.0).to_numpy()
        base = float(np.nanmean(fwd)) * 1e4
        for name, mask in conds.items():
            trials += 1
            m = np.asarray(mask, dtype=bool) & np.isfinite(fwd)
            n = int(m.sum())
            if n < MIN_N:
                continue
            vals = fwd[m]
            mu, sd = float(np.nanmean(vals)), float(np.nanstd(vals, ddof=1))
            if not (sd > 0 and math.isfinite(mu)):
                continue
            t = mu / (sd / math.sqrt(n))
            if abs(t) < REPORT_T:
                continue
            found.append(Anomaly(
                symbol=symbol, condition=name, horizon=h, n=n,
                mean_bp=round(mu * 1e4, 3), t_stat=round(t, 3),
                hit_rate=round(float((vals > 0).mean()), 4), baseline_bp=round(base, 3),
                question=(f"{symbol} returns over {h}h are {mu * 1e4:.1f}bp when "
                          f"{name} (n={n}, |t|={abs(t):.1f}) against a {base:.1f}bp baseline. "
                          f"WHAT MECHANISM would do that, and what would falsify it? "
                          f"Unnamed, this is a correlation and may never be traded.")))
    return found, trials


def scan(symbols: list[str] | None = None, *, limit: int = 40) -> dict[str, Any]:
    """Scan the tradeable universe for conditional structure. Emits anomalies, never candidates."""
    files = sorted(_BARS.glob("*_H1.parquet"))
    if symbols:
        want = {s.upper() for s in symbols}
        files = [f for f in files if f.stem.replace("_H1", "").upper() in want]
    files = files[:limit]

    rows: list[dict[str, Any]] = []
    trials = 0
    scanned, skipped = [], []
    for f in files:
        sym = f.stem.replace("_H1", "")
        try:
            df = pd.read_parquet(f, columns=["open", "high", "low", "close"])
        except Exception as exc:
            skipped.append({"symbol": sym, "why": f"{type(exc).__name__}: {exc}"})
            continue
        found, t = scan_symbol(sym, df)
        trials += t
        scanned.append(sym)
        rows.extend(a.as_row() for a in found)

    rows.sort(key=lambda r: -abs(float(r["t_stat"])))
    report = {
        "scanned_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "symbols_scanned": len(scanned), "symbols_skipped": skipped,
        "trials": trials,
        "anomalies": rows,
        "min_n": MIN_N, "report_t": REPORT_T,
        "honesty": {
            "trials_counted": trials,
            "why": ("every (symbol, condition, horizon) cell evaluated is counted and carried, so "
                    "deflation downstream charges the real width of this search rather than the "
                    "flattering subset that survived the reporting floor"),
            "report_t_is_not_a_gate": ("REPORT_T only decides what reaches the naming queue. It "
                                       "sets no bar: the canonical ten gates remain the only "
                                       "arbiter and nothing here competes with them"),
            "unnamed": ("every row is mechanism_status=UNNAMED. An anomaly is an observation; "
                        "turning one into a candidate without a named, falsifiable cause is the "
                        "prose-to-family guessing the compiler refuses"),
        },
    }
    _OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    (_OUT / f"anomalies_{stamp}.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = scan()
    print(f"anomaly miner: {r['symbols_scanned']} symbol(s), {r['trials']:,} cells evaluated, "
          f"{len(r['anomalies'])} reportable")
    for row in r["anomalies"][:10]:
        print(f"   |t|={abs(row['t_stat']):5.1f}  {row['symbol']:9s} {row['condition']:22s} "
              f"h={row['horizon']:2d}  n={row['n']:5d}  {row['mean_bp']:+8.1f}bp")
