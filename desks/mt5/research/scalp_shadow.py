"""Forward-only shadow clock for the four stable anti-crowd gold scalp candidates.

Discovery bars end before ``SHADOW_START`` and are never counted as forward trades. The engine
replays only newly acquired M5/M15 broker bars, overwrites deterministic ledgers idempotently, and
cannot grant promotion authority while the feed is a non-Fusion proxy. Fifty trades can mature a
sleeve immediately; after fourteen calendar days at least twenty trades are still required.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from desks.mt5.research import scalp_family_expansion as families  # noqa: E402
from desks.mt5.research import scalp_reverse_engineering as core  # noqa: E402

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data" / "universe"
SHADOW = DESK / "reports" / "shadow"
STATE = SHADOW / "scalp_shadow_state.json"
SHADOW_START = pd.Timestamp("2026-08-22T18:00:00Z")

CANDIDATES = {
    "xau_m5_anti_breakout_overlap": (
        "M5", families.Choice("anti_donchian_breakout", "overlap", 1.0, 1.5, 9)
    ),
    "xau_m5_anti_momentum_ny": (
        "M5", families.Choice("anti_three_bar_momentum", "new_york", 1.0, 1.5, 9)
    ),
    "xau_m15_anti_breakout": (
        "M15", families.Choice("anti_donchian_breakout", "all", 1.0, 1.5, 6)
    ),
    "xau_m15_anti_momentum": (
        "M15", families.Choice("anti_three_bar_momentum", "all", 1.0, 1.5, 6)
    ),
}


def _source() -> dict:
    path = DATA / "XAUUSD_scalp_source.json"
    if not path.exists():
        return {"promotion_authority": False, "reason": "missing source manifest"}
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"promotion_authority": False, "reason": f"invalid source manifest: {exc}"}


def _drawdown(rs: list[float]) -> float:
    if not rs:
        return 0.0
    curve = np.r_[0.0, np.cumsum(rs)]
    return float(np.min(curve - np.maximum.accumulate(curve)))


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    source = _source()
    authority = bool(source.get("promotion_authority"))
    state: dict = {
        "updated_at": now.isoformat(timespec="seconds"),
        "shadow_start": SHADOW_START.isoformat(),
        "source": source, "sleeves": {},
    }
    SHADOW.mkdir(parents=True, exist_ok=True)
    cache: dict[str, tuple[pd.DataFrame, dict[str, np.ndarray]]] = {}
    for name, (tf, choice) in CANDIDATES.items():
        path = DATA / f"XAUUSD_{tf}.parquet"
        if not path.exists():
            state["sleeves"][name] = {"status": "NO_DATA", "n": 0}
            continue
        if tf not in cache:
            df = pd.read_parquet(path).sort_index()
            cache[tf] = (df, families._base_signals(df))
        df, all_signals = cache[tf]
        signal = all_signals[choice.family].copy()
        signal[~families._session_mask(df.index, choice.session)] = 0
        signal[df.index < SHADOW_START] = 0
        records = core.simulate(
            df, families._cfg(choice, "bounded_structural"), signal_override=signal,
            detailed=True,
        )
        assert isinstance(records, list)
        ledger = SHADOW / f"ledger_{name}.json"
        ledger.write_text(json.dumps(records, indent=2), "utf-8")
        rs = [float(row["r"]) for row in records]
        n = len(rs)
        last_bar = pd.Timestamp(df.index[-1])
        days = max(0, (last_bar.date() - SHADOW_START.date()).days)
        exp = float(np.mean(rs)) if rs else None
        max_dd = _drawdown(rs)
        matured = n >= 50 or (days >= 14 and n >= 20)
        if last_bar < SHADOW_START:
            status = "WAITING_FOR_FORWARD_BARS"
        elif not authority:
            status = "PROXY_SHADOW"
        elif not matured:
            status = "ACCUMULATING"
        elif exp is not None and exp > 0.05 and max_dd > -25.0:
            status = "PROMOTION_CANDIDATE"
        else:
            status = "KILL"
        state["sleeves"][name] = {
            "status": status, "timeframe": tf, "choice": choice.__dict__,
            "n": n, "days": days, "expectancy_r": exp, "max_drawdown_r": max_dd,
            "last_source_bar": last_bar.isoformat(), "matured": matured,
            "promotion_authority": authority,
            "note": ("Proxy bars may accrue diagnostic evidence but cannot authorize capital."
                     if not authority else "Fusion-native forward shadow."),
        }
    STATE.write_text(json.dumps(state, indent=2), "utf-8")
    return state


def main() -> int:
    state = run()
    for name, sleeve in state["sleeves"].items():
        print(name, sleeve["status"], f"n={sleeve['n']}",
              f"E={sleeve.get('expectancy_r')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
