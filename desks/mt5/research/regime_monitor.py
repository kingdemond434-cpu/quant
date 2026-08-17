"""Regime/Decay Desk seed: realized-expectancy monitor over live trades.

Reads data/live_ledger.jsonl, computes per-sleeve rolling realized expectancy
(win/loss in R) and flags hibernation candidates when the trailing window is
clearly negative. Writes data/regime_state.json + a log line. Watchdog only:
it never touches gateway execution.

Sleeve id convention in ledger: tag like "XAUUSD|asia" (promoted) or
"shadow|XAUUSD|asia" (shadow). Both are monitored.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
LEDGER = BASE / "data" / "live_ledger.jsonl"
STATE = BASE / "data" / "regime_state.json"
WINDOW = 90
HIBERNATE_EXP = -0.10
WARN_EXP = -0.05


def main() -> None:
    rows = []
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    by_sleeve: dict[str, list[float]] = {}
    for r in rows:
        if "r_multiple" not in r:
            continue
        tag = str(r.get("tag", "")).split("|")
        if len(tag) < 2:
            continue
        sleeve = f"{tag[0]}|{tag[1]}"
        by_sleeve.setdefault(sleeve, []).append(float(r["r_multiple"]))
    state = {"swept_at": datetime.now(timezone.utc).isoformat(), "sleeves": {}}
    for sleeve, rs in by_sleeve.items():
        rs = rs[-WINDOW:]
        exp = float(np.mean(rs))
        n = len(rs)
        win = float(np.mean([x for x in rs if x > 0])) if any(x > 0 for x in rs) else 0.0
        loss = float(np.mean([x for x in rs if x < 0])) if any(x < 0 for x in rs) else 0.0
        cum = np.cumsum(rs)
        maxdd = float(min(cum[i] - cum[:i + 1].max() for i in range(len(cum)))) if n else 0.0
        flag = "hibernate" if ((n >= 30 and exp < HIBERNATE_EXP)
                               or (n >= 10 and maxdd < -25.0)) else (
            "warn" if (n >= 30 and exp < WARN_EXP) else "ok")
        state["sleeves"][sleeve] = dict(n=n, exp_r=round(exp, 4),
                                        avg_win_r=round(win, 3),
                                        avg_loss_r=round(loss, 3),
                                        max_dd_r=round(maxdd, 1),
                                        flag=flag)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    flags = {s: v["flag"] for s, v in state["sleeves"].items() if v["flag"] != "ok"}
    if flags:
        from mt5desk import gateway  # noqa: PLC0415
        gateway.log(f"REGIME: {flags}")


if __name__ == "__main__":
    main()