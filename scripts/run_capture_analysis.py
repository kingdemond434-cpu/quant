"""Profit-retention / capture analysis (Phase 3) — honest, portfolio-level, from realized equity.

Capture Ratio = realized return / maximum favorable excursion (how much of the peak you kept).
Computed from the live equity curve since the drawdown-lock fix. This is a DIAGNOSTIC: it quantifies
the giveback we can see live. It does NOT test exit overlays here, because a valid exit study needs
the per-sleeve backtest series run through CPCV/DSR/PBO — testing overlays on a few dozen noisy
intraday points would be fitting noise, which the mandate forbids. Writes web/capture.json with the
gauntlet-gated next step. Per-sleeve capture-by-regime is queued behind the data build.

    python scripts/run_capture_analysis.py
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.profit_retention import capture_ratio, mfe_mae  # noqa: E402

_DB = Path("data/crypto_trades.sqlite")
_OUT = Path("web/capture.json")


def main() -> None:
    con = sqlite3.connect(_DB)
    curve = con.execute("SELECT ts,equity FROM equity_curve ORDER BY ts").fetchall()
    con.close()
    if len(curve) < 5:
        raise SystemExit("not enough equity history yet")
    eqs = [float(e) for _, e in curve]
    rets = [eqs[i] / eqs[i - 1] - 1.0 for i in range(1, len(eqs)) if eqs[i - 1]]
    rarr = np.array(rets)
    mfe_frac, _mae = mfe_mae(rarr)                          # engine: cumulative-path excursions
    mfe = mfe_frac * 100
    realized = (eqs[-1] / eqs[0] - 1.0) * 100
    cr = capture_ratio(rarr)
    capture = round(cr, 2) if cr is not None else None
    up = [r for r in rets if r > 0]
    dn = [r for r in rets if r < 0]
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "scope": "portfolio (live equity, since DD-lock fix)",
        "mfe_pct": round(mfe, 2),
        "realized_pct": round(realized, 2),
        "giveback_pct": round(mfe - realized, 2),
        "capture_ratio": capture,
        "up_steps": len(up), "down_steps": len(dn),
        "avg_up_pct": round((statistics.fmean(up) * 100) if up else 0.0, 3),
        "avg_down_pct": round((statistics.fmean(dn) * 100) if dn else 0.0, 3),
        "finding": (f"Peak {mfe:+.1f}% kept as {realized:+.1f}% -> capture {capture} (giveback). "
                    "Carry book has no exit logic, so favorable excursions bleed back."),
        "next_step": ("Gauntlet-gated exit study (per sleeve, backtest): trailing for trend, "
                      "funding/basis-collapse time-decay for carry, partial-profit for reversion. "
                      "Promote ONLY if it keeps CAGR + passes CPCV/DSR/PBO. Not on live noise."),
        "per_sleeve_status": "pending data build (capture-by-regime needs the lake rebuild)",
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"capture: MFE {out['mfe_pct']}% -> realized {out['realized_pct']}% "
          f"= capture {capture} (giveback {out['giveback_pct']}%)")


if __name__ == "__main__":
    main()
