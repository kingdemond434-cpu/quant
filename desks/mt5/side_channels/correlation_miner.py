"""Cross-market correlation miner.

Calculates real-time correlations between assets and detects
correlation breakdowns (which often signal regime changes).
When gold and USD suddenly decouple = something is happening.
"""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "correlations"
OUT.mkdir(parents=True, exist_ok=True)

#: Short window, baseline window (trading days), and the |z| a correlation shift must reach.
SHORT, BASE_DAYS, Z_MIN = 20, 250, 2.5
#: Rows kept per pass, strongest |z| first. Every pair is still MEASURED; this bounds donations.
TOP_K = 40


def _returns(universe: Path | None = None) -> pd.DataFrame:
    """Daily log returns of every hypothesis-lane symbol, aligned on common days."""
    try:
        from side_channels._bars import daily_close, hypothesis_symbols
    except ModuleNotFoundError:
        from _bars import daily_close, hypothesis_symbols
    cols = {}
    for sym in hypothesis_symbols(universe):
        c = daily_close(sym, universe)
        if c is not None and len(c) > BASE_DAYS + SHORT:
            cols[sym] = np.log(c).diff()
    if not cols:
        return pd.DataFrame()
    df = pd.DataFrame(cols)
    df = df[df.index.dayofweek < 5].iloc[-(BASE_DAYS + 3 * SHORT):]   # crypto's weekends out
    return df.dropna(axis=1, thresh=int(len(df) * 0.8))


def mine_correlations(universe: Path | None = None) -> list[dict]:
    """Every pair's 20-day correlation against the distribution of its own 20-day correlation
    over the past year. A shift of |z| >= Z_MIN is a regime break between two instruments; the
    strongest TOP_K are donated as hypotheses.

    It replaces eight hard-coded pairs, three of which named symbols the broker does not carry
    (DXY, USOIL), and two fixed thresholds (|change| > 0.4, |corr| > 0.7) that the remaining
    pairs never crossed: 0 rows on every box run (2026-11-13 19:45Z, 21:45Z)."""
    r = _returns(universe)
    if r.shape[1] < 2:
        return []
    syms = list(r.columns)
    x = r.to_numpy(dtype="float64")
    rows: list[dict] = []
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            pair = pd.DataFrame({"a": x[:, i], "b": x[:, j]}).dropna()
            if len(pair) < BASE_DAYS // 2 + SHORT:
                continue
            roll = pair["a"].rolling(SHORT).corr(pair["b"]).dropna()
            if len(roll) < BASE_DAYS // 2:
                continue
            now = float(roll.iloc[-1])
            hist = roll.iloc[-BASE_DAYS:-SHORT] if len(roll) > BASE_DAYS else roll.iloc[:-SHORT]
            sd = float(hist.std())
            if not np.isfinite(now) or not np.isfinite(sd) or sd < 1e-6:
                continue
            z = (now - float(hist.mean())) / sd
            if abs(z) < Z_MIN:
                continue
            a, b = syms[i], syms[j]
            rows.append({
                "source": "correlation",
                "type": "correlation_breakdown" if abs(now) < abs(float(hist.mean()))
                        else "correlation_surge",
                "pair": f"{a}~{b}",
                "symbol1": a,
                "symbol2": b,
                "short_correlation": round(now, 3),
                "baseline_correlation": round(float(hist.mean()), 3),
                "z": round(z, 2),
                "symbols": [a, b],
                "confidence": round(min(0.7, abs(z) / 8), 3),
                "description": (f"{a}/{b} {SHORT}d correlation {now:+.2f} vs one-year mean "
                                f"{float(hist.mean()):+.2f} (z={z:+.1f})"),
            })
    rows.sort(key=lambda d: -abs(d["z"]))
    return rows[:TOP_K]


def run_and_save() -> list[dict]:
    discoveries = mine_correlations()
    out_file = OUT / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"correlations: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
