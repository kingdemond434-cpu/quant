"""The ONE deployed-portfolio object -- single source of truth for live capital.

Every surface that shows "what is actually deployed" (dashboard molded card, testnet, live,
portfolio.json) derives from `LivePortfolio`. It reads the real testnet accounts + the cash-carry
state + the equity curve + the trade log, and exposes ONE consistent set of numbers: deployed
capital, the live sleeve(s), net PnL, day-count, winrate and the DEPLOYED Sharpe (computed from the
forward live equity curve -- NOT a backtest number). Research/shadow sleeves are labelled separately
and never mixed into the deployed Sharpe. This kills duplicate portfolio maths across scripts.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STATE = Path("data/cashcarry_positions.json")
_CC = Path("web/cashcarry_live.json")
_CURVE = Path("data/live_combined_state.json")
_TRADES = Path("data/cashcarry_trades.json")


def _load(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _num(v: object, d: float = 0.0) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return d


@dataclass
class LivePortfolio:
    """Canonical deployed book. Build via `LivePortfolio.load(base_per_leg=...)`."""

    base_per_leg: float
    start: str | None
    fut_equity: float
    fut_start_equity: float
    fut_unrealized: float
    spot_leg_pnl: float
    spot_realized: float = 0.0     # banked PnL of CLOSED spot legs (lives in the spot wallet)
    spot_usdt: float = 0.0
    funding: float = 0.0
    carries: list[dict[str, Any]] = field(default_factory=list)
    mcurve: list[list[Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)

    # -- the single deployed truth --------------------------------------------------
    LIVE_SLEEVES = ("cash_and_carry",)                 # what is ACTUALLY deployed to capital

    @property
    def fut_pnl(self) -> float:
        return round(self.fut_equity - self.fut_start_equity, 2)

    @property
    def net_pnl(self) -> float:
        # delta-neutral reconciled total: futures-account delta (realized + funding + fees) +
        # OPEN spot marks + banked realized of CLOSED spot legs (symmetric on realized PnL)
        return round(self.fut_pnl + self.spot_leg_pnl + self.spot_realized, 2)

    @property
    def start_capital(self) -> float:
        return round(2 * self.base_per_leg, 2)

    @property
    def equity(self) -> float:
        return round(self.start_capital + self.net_pnl, 2)

    @property
    def days_live(self) -> float:
        if not self.start:
            return 0.0
        try:
            dt = datetime.fromisoformat(str(self.start))
            return round((datetime.now(tz=UTC) - dt).total_seconds() / 86400, 2)
        except (ValueError, TypeError):
            return 0.0

    @property
    def closed_trades(self) -> list[dict[str, Any]]:
        return [t for t in self.trades if t.get("event") == "close"]

    @property
    def n_closed(self) -> int:
        return len(self.closed_trades)

    @property
    def winrate(self) -> float | None:
        """% of CLOSED carries that netted positive. None until there is closed history (honest)."""
        cl = self.closed_trades
        if not cl:
            return None
        wins = sum(1 for t in cl if _num(t.get("net")) > 0)
        return round(100.0 * wins / len(cl), 1)

    # minimum forward window before an annualised Sharpe is statistically meaningful (not noise).
    _MIN_SHARPE_DAYS = 5.0

    def _hourly_equity(self) -> list[float]:
        """Resample the ~60s curve to one point per UTC hour (last obs) -- kills fee noise."""
        buckets: dict[str, float] = {}
        for t, e in self.mcurve:
            try:
                key = str(t)[:13]                             # 'YYYY-MM-DDTHH'
            except (ValueError, TypeError):
                continue
            buckets[key] = _num(e)
        return [buckets[k] for k in sorted(buckets)]

    @property
    def deployed_sharpe(self) -> float | None:
        """Annualised Sharpe from the FORWARD live curve, hourly-resampled. None until meaningful.

        Corresponds to the money actually on the testnet -- NOT a backtest. Deliberately returns
        None until >= `_MIN_SHARPE_DAYS` of forward history: a Sharpe computed on intra-hour fee
        noise is meaningless (and misleading), so we refuse to print one. Honesty > a filled cell.
        """
        if self.days_live < self._MIN_SHARPE_DAYS:
            return None
        eq = self._hourly_equity()
        if len(eq) < 48:                                       # >= ~2 days of hourly points
            return None
        rets = [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq)) if eq[i - 1] > 0]
        if len(rets) < 40:
            return None
        mu = sum(rets) / len(rets)
        var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
        sd = math.sqrt(var)
        if sd <= 0:
            return None
        return round((mu / sd) * math.sqrt(365 * 24), 2)      # per-hour Sharpe -> annualised

    @classmethod
    def load(cls, base_per_leg: float, *, fut: Any = None, spot: Any = None) -> LivePortfolio:
        state = _load(_STATE, {})
        cc = _load(_CC, {})
        curve = _load(_CURVE, {})
        trades = _load(_TRADES, [])
        fa = fut.account_summary() if (fut and fut.has_keys()) else {}
        fut_eq = round(_num(fa.get("equity")), 2)
        return cls(
            base_per_leg=base_per_leg,
            start=state.get("start"),
            fut_equity=fut_eq,
            fut_start_equity=_num(state.get("start_futures_equity"), fut_eq),
            fut_unrealized=round(_num(fa.get("unrealized_pnl")), 2),
            spot_leg_pnl=round(_num(cc.get("spot_leg_pnl")), 2),
            spot_realized=round(_num(state.get("realized_spot_pnl")), 2),
            spot_usdt=round(spot.usdt_balance(), 2) if (spot and spot.has_keys()) else 0.0,
            funding=round(_num(cc.get("funding_harvested")), 2),
            carries=cc.get("carries", []) if isinstance(cc.get("carries"), list) else [],
            mcurve=curve.get("mcurve", []) if isinstance(curve.get("mcurve"), list) else [],
            trades=trades if isinstance(trades, list) else [],
        )

    def to_public(self) -> dict[str, Any]:
        """The web/portfolio.json payload -- deployed vs research clearly separated."""
        return {
            "updated": datetime.now(tz=UTC).isoformat(),
            "deployed": {
                "sleeves": list(self.LIVE_SLEEVES),
                "start_capital": self.start_capital,
                "equity": self.equity,
                "net_pnl": self.net_pnl,
                "return_pct": round(self.net_pnl / self.start_capital * 100, 3)
                if self.start_capital else 0.0,
                "days_live": self.days_live,
                "winrate_pct": self.winrate,
                "n_closed_trades": self.n_closed,
                "deployed_sharpe": self.deployed_sharpe,
                "funding": self.funding,
                "n_carries": len(self.carries),
            },
            "note": ("Single source of truth for DEPLOYED capital. Sharpe here is from the live "
                     "forward equity curve on the testnet -- NOT a backtest. Research/shadow "
                     "sleeves are shown in their own cards and never fold into this Sharpe."),
        }
