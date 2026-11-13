"""Component Harvesting — extracts useful pieces from failed strategies.

Breaks every external strategy apart:
ENTRY / EXIT / STOP / TRAIL / SESSION / REGIME FILTER / RE-ENTRY / POSITION MANAGEMENT

Then independently tests the information content of each component.
A bad full EA can have fantastic components.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from enum import Enum
from collections import defaultdict

import pandas as pd

try:
    from ...base import (  # noqa: F401
        DATA_DIR,
        SideChannelAxis,
        SideChannelHypothesis,
        generate_id,
        save_hypothesis,
    )
except ImportError:  # pragma: no cover - the `component_harvest` hourly leg runs this file
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from side_channels.base import (  # type: ignore[no-redef]  # noqa: F401
        DATA_DIR,
        SideChannelAxis,
        SideChannelHypothesis,
        generate_id,
        save_hypothesis,
    )


class ComponentType(Enum):
    ENTRY = "entry"
    EXIT = "exit"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    SESSION_FILTER = "session_filter"
    REGIME_FILTER = "regime_filter"
    RE_ENTRY = "re_entry"
    POSITION_SIZING = "position_sizing"
    ENTRY_METHOD = "entry_method"
    EXIT_METHOD = "exit_method"
    MARTINGALE = "martingale"
    GRID = "grid"
    AVERAGING = "averaging"
    HEDGING = "hedging"
    TRAILING = "trailing"


@dataclass
class StrategyComponent:
    """A single atomic component from a decomposed strategy."""
    component_type: ComponentType
    value: str                              # e.g., "ema_cross", "atr_1.5", "london_session"
    source_strategy: str                    # original strategy ID
    economic_meaning: str                   # what this piece represents
    standalone_edge_bps: float = 0.0        # edge when this component was tested alone
    frequency: float = 0.0                  # how often this component appears
    orthogonality_score: float = 1.0        # 0-1, higher = more independent
    win_rate_contribution: float = 0.0      # contribution to win rate
    profit_factor_contribution: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ComponentTestResult:
    """Result of testing a component in isolation."""
    component: StrategyComponent
    tested_in_isolation: bool = False
    edge_bps: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    n_trades: int = 0
    n_winners: int = 0
    n_losers: int = 0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    avg_holding_bars: float = 0.0
    regime_performance: dict[str, float] = field(default_factory=dict)
    session_performance: dict[str, float] = field(default_factory=dict)
    symbol_performance: dict[str, float] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class ComponentExtractor:
    """Extracts atomic components from parsed strategies."""
    
    def __init__(self):
        self.component_library: dict[ComponentType, list[StrategyComponent]] = defaultdict(list)
        self.component_index: dict[str, StrategyComponent] = {}
    
    def extract_from_parsed_strategy(self, strategy: Any) -> list[StrategyComponent]:
        """Extract components from a parsed MQL5 strategy."""
        components = []
        source_id = getattr(strategy, 'source_id', 'unknown')
        
        # Entry component
        if hasattr(strategy, 'entry_rules') and strategy.entry_rules:
            entry = StrategyComponent(
                component_type=ComponentType.ENTRY,
                value="; ".join(strategy.entry_rules[:2]),
                source_strategy=source_id,
                economic_meaning=f"Entry trigger: {strategy.entry_rules[0] if strategy.entry_rules else 'unknown'}",
            )
            components.append(entry)
        
        # Exit component
        if hasattr(strategy, 'exit_rules') and strategy.exit_rules:
            exit_comp = StrategyComponent(
                component_type=ComponentType.EXIT,
                value="; ".join(strategy.exit_rules[:2]),
                source_strategy=source_id,
                economic_meaning=f"Exit logic: {strategy.exit_rules[0] if strategy.exit_rules else 'unknown'}",
            )
            components.append(exit_comp)
        
        # Stop loss
        if hasattr(strategy, 'stop_loss') and strategy.stop_loss:
            stop = StrategyComponent(
                component_type=ComponentType.STOP_LOSS,
                value=strategy.stop_loss,
                source_strategy=source_id,
                economic_meaning=f"Stop loss: {strategy.stop_loss}",
            )
            components.append(stop)
        
        # Trailing stop
        if hasattr(strategy, 'trailing_stop') and strategy.trailing_stop:
            trail = StrategyComponent(
                component_type=ComponentType.TRAILING_STOP,
                value=strategy.trailing_stop,
                source_strategy=source_id,
                economic_meaning=f"Trailing stop: {strategy.trailing_stop}",
            )
            components.append(trail)
        
        # Session filter
        if hasattr(strategy, 'session_filters') and strategy.session_filters:
            session = StrategyComponent(
                component_type=ComponentType.SESSION_FILTER,
                value="; ".join(strategy.session_filters),
                source_strategy=source_id,
                economic_meaning=f"Session filter: {', '.join(strategy.session_filters)}",
            )
            components.append(session)
        
        # Timeframe/regime
        if hasattr(strategy, 'timeframe') and strategy.timeframe:
            regime = StrategyComponent(
                component_type=ComponentType.REGIME_FILTER,
                value=f"timeframe_{strategy.timeframe}",
                source_strategy=source_id,
                economic_meaning=f"Timeframe filter: {strategy.timeframe}",
            )
            components.append(regime)
        
        # Entry method
        if hasattr(strategy, 'indicators') and strategy.indicators:
            entry_method = StrategyComponent(
                component_type=ComponentType.ENTRY_METHOD,
                value=", ".join(strategy.indicators[:3]),
                source_strategy=source_id,
                economic_meaning=f"Entry method using: {', '.join(strategy.indicators[:3])}",
            )
            components.append(entry_method)
        
        # Position sizing
        if hasattr(strategy, 'position_sizing') and strategy.position_sizing:
            sizing = StrategyComponent(
                component_type=ComponentType.POSITION_SIZING,
                value=strategy.position_sizing,
                source_strategy=source_id,
                economic_meaning=f"Position sizing: {strategy.position_sizing}",
            )
            components.append(sizing)
        
        # Martingale/Grid/Averaging detection
        if getattr(strategy, 'grid_martingale', False):
            grid = StrategyComponent(
                component_type=ComponentType.GRID,
                value="grid_martingale",
                source_strategy=source_id,
                economic_meaning="Grid/martingale position management",
            )
            components.append(grid)
        
        if getattr(strategy, 'averaging_down', False):
            avg = StrategyComponent(
                component_type=ComponentType.AVERAGING,
                value="averaging_down",
                source_strategy=source_id,
                economic_meaning="Averaging down on adverse moves",
            )
            components.append(avg)
        
        if getattr(strategy, 'hedging', False):
            hedge = StrategyComponent(
                component_type=ComponentType.HEDGING,
                value="hedging",
                source_strategy=source_id,
                economic_meaning="Hedging positions",
            )
            components.append(hedge)
        
        # Register components
        for comp in components:
            comp_id = f"{comp.component_type.value}:{comp.value}:{source_id}"
            self.component_index[comp_id] = comp
            self.component_library[comp.component_type].append(comp)
        
        return components


class ComponentTester:
    """Tests components in isolation and in combination."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.results: list[ComponentTestResult] = []
    
    def test_component_isolation(self, component: StrategyComponent, 
                                  price_data: dict[str, pd.DataFrame],
                                  regime_labels: pd.Series | None = None) -> ComponentTestResult:
        """Test a single component in isolation."""
        # NO ISOLATION BACKTEST EXISTS FOR A BARE COMPONENT, so the result says so. Until
        # 2026-09-30 this returned `tested_in_isolation=True` with zero trades -- a mock that read
        # as "tested, found nothing", which is a verdict nobody measured (L1.28a).
        result = ComponentTestResult(component=component)
        result.tested_in_isolation = False
        result.metadata = {"status": "UNMEASURED",
                           "why": "no single-component backtest is implemented; components are "
                                  "judged only inside a full hypothesis by the gauntlet"}
        return result

    def test_component_combination(self, components: list[StrategyComponent],
                                    price_data: dict[str, pd.DataFrame]) -> ComponentTestResult:
        """Test a combination of components together."""
        result = ComponentTestResult(component=components[0] if components else None)
        result.metadata = {"status": "UNMEASURED",
                           "why": "no combination backtest is implemented here"}
        return result
    
    def test_all_components(self, components: list[StrategyComponent],
                             price_data: dict[str, pd.DataFrame]) -> list[ComponentTestResult]:
        """Test each component in isolation."""
        results = []
        for comp in components:
            result = self.test_component_isolation(comp, price_data)
            results.append(result)
        return results


class ComponentHarvester:
    """Harvests useful components from failed/near-miss strategies."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.extractor = ComponentExtractor()
        self.tester = ComponentTester(base_path)
        self.harvested_components: list[StrategyComponent] = []
    
    def harvest_from_failed_strategies(self, failed_strategies: list[Any],
                                        price_data: dict[str, pd.DataFrame]) -> list[StrategyComponent]:
        """Extract and test components from failed strategies."""
        all_components = []
        
        for strategy in failed_strategies:
            components = self.extractor.extract_from_parsed_strategy(strategy)
            all_components.extend(components)
        
        # Test each component
        for comp in all_components:
            # In production, would run actual backtests
            # For now, use heuristics to estimate value
            score = self._heuristic_component_score(comp)
            if score > 0.3:  # Threshold for "potentially useful"
                comp.metadata["heuristic_score"] = score
                self.harvested_components.append(comp)
        
        return self.harvested_components
    
    def _heuristic_component_score(self, component: StrategyComponent) -> float:
        """Heuristic scoring of component potential."""
        score = 0.0
        
        # High-value component types
        high_value_types = {
            ComponentType.ENTRY: 0.3,
            ComponentType.STOP_LOSS: 0.25,
            ComponentType.TRAILING_STOP: 0.2,
            ComponentType.REGIME_FILTER: 0.2,
            ComponentType.SESSION_FILTER: 0.15,
            ComponentType.ENTRY_METHOD: 0.15,
            ComponentType.EXIT_METHOD: 0.1,
        }
        score += high_value_types.get(component.component_type, 0.05)
        
        # Bonus for specific high-value values
        high_value_values = {
            "ema_cross": 0.15,
            "rsi": 0.1,
            "macd": 0.1,
            "bollinger": 0.1,
            "atr": 0.15,
            "session": 0.1,
            "london": 0.1,
            "ny": 0.1,
            "atr_1.5": 0.1,
            "atr_2.0": 0.1,
        }
        for val, bonus in high_value_values.items():
            if val in component.value.lower():
                score += bonus
        
        # Penalty for known bad patterns
        bad_patterns = ["martingale", "grid", "averaging_down", "hedging"]
        for bad in bad_patterns:
            if bad in component.value.lower():
                score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def generate_component_hypotheses(self, min_score: float = 0.4) -> list[dict]:
        """Generate hypotheses from high-scoring components."""
        hypotheses = []
        
        for comp in self.harvested_components:
            score = comp.metadata.get("heuristic_score", 0)
            if score < min_score:
                continue
            
            hypothesis = {
                "id": generate_id(),
                "origin": {
                    "region": "global",
                    "language": "en",
                    "source_type": "component_harvesting",
                    "source_id": comp.source_strategy,
                    "evidence_tier": "component_derived",
                },
                "mechanism": {
                    "mechanism_class": "execution_alpha" if comp.component_type in [ComponentType.STOP_LOSS, ComponentType.TRAILING_STOP, ComponentType.ENTRY_METHOD] else "information_shock",
                    "participant": "retail",
                    "constraint": "component_extraction",
                    "information_source": "failed_strategy_decomposition",
                    "why_edge_should_exist": f"Harvested {comp.component_type.value} component from failed strategy: {comp.economic_meaning}",
                },
                "market": {
                    "symbols": ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"],
                    "primary_symbol": "XAUUSD",
                },
                "rule": {
                    "inputs": ["price", comp.value],
                    "trigger": f"Component: {comp.component_type.value} = {comp.value}",
                    "direction": 0,
                    "holding_horizon": "4h",
                    "exit": "component_defined",
                    "stop": "atr_1.5",
                },
                "economics": {
                    "expected_edge_bps_per_trade": score * 10,
                    "expected_trades_per_month": 20,
                    "expected_capacity_lots": 10,
                    "expected_capacity_category": "small",
                },
                "falsifier": {
                    "condition": "component_edge_vanishes",
                    "horizon": "50_trades",
                    "threshold": 0.0,
                    "data_source": "shadow_forward",
                },
                "metadata": {
                    "source": "component_harvesting",
                    "component_type": comp.component_type.value,
                    "component_value": comp.value,
                    "source_strategy": comp.source_strategy,
                    "heuristic_score": score,
                },
            }
            hypotheses.append(hypothesis)
        
        return hypotheses


def harvest_components(failed_strategies: list[Any], 
                        price_data: dict[str, pd.DataFrame]) -> list[StrategyComponent]:
    """Entry point for component harvesting."""
    base = Path("/home/quant/quant-platform")
    harvester = ComponentHarvester(base)
    return harvester.harvest_from_failed_strategies(failed_strategies, price_data)


def generate_component_hypotheses(components: list[StrategyComponent]) -> list[dict]:
    """Generate hypotheses from harvested components."""
    base = Path("/home/quant/quant-platform")
    harvester = ComponentHarvester(base)
    harvester.harvested_components = components
    return harvester.generate_component_hypotheses()


# =============================================================================================
# REJECTED-CELL HARVEST: the clock, the isolation test and the Judge door (2026-11-13)
#
# The classes above were never run: no clock, no input, a heuristic score and an isolation test
# that reports UNMEASURED. "A bad full EA can have fantastic components" is testable on the
# desk's own failures, which are exact recipes: every candidate the gauntlet REJECTED is a
# (family, symbol, chart, params) whose rule can be rebuilt bar for bar. So, each hourly pass:
#
#   1. DECOMPOSE. A rejected recipe's params split by role -- ENTRY (whatever is not below),
#      STOP (stop_atr, atr_n, ...), EXIT (rr, ttl_bars, hold_bars, bank/trail keys), SESSION
#      (hour/session keys), REGIME (regime/vol/adx/filter keys).
#   2. TEST THE ENTRY IN ISOLATION. Rebuild the signals, then score the ENTRY alone: signed
#      log return from the next bar's open over h in {1, 3, 6, 12, 24} bars, net of the symbol's
#      own measured spread, signals declustered to be at least h bars apart. The horizon is chosen
#      on the first 70% of signals (in-sample) and judged ONCE on the last 30% (out of sample): one
#      pre-chosen test, so no horizon search is charged against the verdict.
#   3. TEST THE EXIT AGAINST IT. Replay the recipe's own stop / target / ttl on the same entries
#      (a bar touching both stop and target counts as the stop). EXIT_DESTROYED_EDGE = the entry's
#      OOS time-exit is significant and positive while the recipe's own exit is not positive.
#   4. RE-MATE AND DONATE. A harvested entry (IS t >= 2, OOS t >= 2, OOS mean > 0, >= 20 OOS
#      signals) is re-mated with a time exit at the chosen horizon -- once with its own stop and
#      once with a wide 4-ATR stop -- and enqueued for the Judge through
#      `libs.moat.registry.enqueue_candidate` (origin `component_harvest`, parent = the rejected
#      cell). Only parameters the family's own signature accepts are set; a family with no
#      time-exit parameter is reported NO_TIME_EXIT_PARAM, never forced.
#   5. LEDGER. Every component verdict is appended to data/component_harvest/component_ledger.jsonl
#      (gitignored, OUTSIDE data/intelligence so the compiler can never read rejected params as a
#      donation -- Auditor HOLD on #1146, MF4); the pass writes reports/COMPONENT_HARVEST.json. A
#      rejected cell is examined once in its life: the registry is walked by rowid with a cursor,
#      so the walk never stalls on a top-N (SF1).
#
# WHAT THE AUDITOR HELD AND HOW IT IS PAID (HOLD on #1146, MF1, 2026-11-13):
#   * THE SCREEN NEVER SEES THE LOCKBOX. Every screen reads only the bars dated before the
#      screen cut: the last SCREEN_HOLDOUT of the symbol's calendar (twice the gauntlet's own
#      lockbox fraction, so the cut sits before the gauntlet's union-calendar cut on any cell
#      whose history is not more than twice as long as the shortest) is never read here.
#   * THE SEARCH IS CHARGED. A re-mate carries `claim_family = harvest:<parent>` and
#      `claim_selection_trials = screened looks this pass (cells x horizons) + the parent's own
#      search_count`, in its lineage (lifted onto the docket row by `libs.moat.docket_feed`) and in
#      the lifetime claim ledger (`libs.research.claim_selection`), so the screen AND the parent's
#      trials are paid on top of the Judge's own charge.
#   * NO HARVEST OF A HARVEST: a component_harvest / component_remate row is never re-screened.
#   * LANE ROUTING FIRST: `universe_policy.may_hypothesise(symbol, family)` runs before every
#      enqueue; a cell the routing sets aside is reported LANE_SET_ASIDE, never enqueued.
#   * The parent's entry-timing keys (wait_bars, cooldown_bars) ride onto every re-mate (SF5).
#
# Clock: hourly leg `component_harvest` (research/hourly_cycle.py), 240 s.
# =============================================================================================

import inspect
import time

import numpy as np

_DESK = Path(__file__).resolve().parents[3]
HARVEST_DIR = _DESK / "data" / "component_harvest"
STATE_P = HARVEST_DIR / "state.json"
LEDGER_P = HARVEST_DIR / "component_ledger.jsonl"
REPORT_P = _DESK / "reports" / "COMPONENT_HARVEST.json"
#: Origins a harvest never re-screens.
HARVEST_ORIGINS = ("component_harvest",)

HORIZONS = (1, 3, 6, 12, 24)
IS_SHARE = 0.70
MIN_T = 2.0
MIN_OOS = 20
WIDE_STOP_ATR = 4.0
NO_TARGET_RR = 50.0
PER_PASS = 200
#: Entry-timing keys a re-mate inherits unchanged (they gate WHEN the entry fires, not the exit).
_TIMING_KEYS = ("wait_bars", "cooldown_bars")


def _screen_holdout() -> float:
    try:
        from research.gate_policy import LOCKBOX_FRAC
        return min(0.5, 2.0 * float(LOCKBOX_FRAC))
    except Exception:
        return 0.4


SCREEN_HOLDOUT = _screen_holdout()


def screen_cut(bars: pd.DataFrame) -> pd.Timestamp | None:
    """The first calendar day the screen may NOT read: the last SCREEN_HOLDOUT of the dates."""
    days = pd.DatetimeIndex(bars.index).normalize().unique().sort_values()
    if len(days) < 10:
        return None
    return days[int(len(days) * (1.0 - SCREEN_HOLDOUT))]

_EXIT_KEYS = {"rr", "ttl_bars", "hold_bars", "bank_frac", "bank_protect_k", "runner_trail_k",
              "target_atr", "tp_atr", "exit_bars", "max_hold", "wait_bars", "cooldown_bars"}
_STOP_KEYS = {"stop_atr", "sl_atr", "atr_n", "stop_pct", "trail_atr", "stop_mult"}


def decompose(params: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """params -> {entry, stop, exit, session, regime}; every key lands in exactly one role."""
    out: dict[str, dict[str, Any]] = {k: {} for k in ("entry", "stop", "exit", "session",
                                                      "regime")}
    for k, v in (params or {}).items():
        kl = k.lower()
        if kl in _EXIT_KEYS:
            out["exit"][k] = v
        elif kl in _STOP_KEYS:
            out["stop"][k] = v
        elif "hour" in kl or "session" in kl or kl in {"weekday", "dow", "active_month"}:
            out["session"][k] = v
        elif any(t in kl for t in ("regime", "vol_gate", "adx", "filter", "trend_gate")):
            out["regime"][k] = v
        else:
            out["entry"][k] = v
    return out


def _cost_frac(symbol: str, price: float) -> float:
    """One round trip of the symbol's own measured median spread, as a fraction of price."""
    try:
        u = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
        r = u.get(symbol) or {}
        pts = float(r.get("median_spread_pts") or r.get("spread_pts_at_collection") or 0.0)
        point = 10.0 ** -int(r.get("digits", 5))
        return pts * point / price if price > 0 else 0.0
    except Exception:
        return 0.0


def _t(x: np.ndarray) -> float:
    if len(x) < 3:
        return float("nan")
    sd = float(np.std(x, ddof=1))
    return float(np.mean(x) / (sd / np.sqrt(len(x)))) if sd > 0 else float("nan")


def _decluster(idx: np.ndarray, h: int) -> np.ndarray:
    keep, last = [], -10 ** 9
    for k, i in enumerate(idx):
        if i - last >= h:
            keep.append(k)
            last = i
    return np.asarray(keep, dtype=int)


def entry_markout(bars: pd.DataFrame, signals: list[Any], symbol: str
                  ) -> dict[str, Any]:
    """The entry alone: per horizon, IS/OOS net mean and t, horizon chosen in-sample."""
    d = bars.sort_index()
    pos = d.index.get_indexer(pd.DatetimeIndex([s.time for s in signals]))
    sides = np.array([int(s.side) for s in signals])
    ok = (pos >= 0) & (sides != 0)
    pos, sides = pos[ok], sides[ok]
    order = np.argsort(pos, kind="stable")
    pos, sides = pos[order], sides[order]
    opens = d["open"].to_numpy(float)
    closes = d["close"].to_numpy(float)
    if not len(pos):
        return {"status": "NO_SIGNALS"}
    cost = _cost_frac(symbol, float(np.nanmedian(closes)))
    split = int(len(pos) * IS_SHARE)
    res: dict[str, Any] = {"n_signals": int(len(pos)), "cost_frac": cost, "by_h": {}}
    for h in HORIZONS:
        e = pos + 1
        x = pos + 1 + h
        v = x < len(d)
        r = np.full(len(pos), np.nan)
        r[v] = sides[v] * np.log(closes[x[v] - 1] / opens[e[v]]) - cost
        k_is = _decluster(pos[:split], h)
        k_oos = split + _decluster(pos[split:], h)
        ris, roos = r[k_is], r[k_oos]
        ris, roos = ris[np.isfinite(ris)], roos[np.isfinite(roos)]
        res["by_h"][h] = {"is_n": int(len(ris)), "is_mean": float(np.mean(ris)) if len(ris)
                          else float("nan"), "is_t": _t(ris),
                          "oos_n": int(len(roos)), "oos_mean": float(np.mean(roos)) if len(roos)
                          else float("nan"), "oos_t": _t(roos)}
    cand = {h: v for h, v in res["by_h"].items() if np.isfinite(v["is_t"])}
    if not cand:
        res["status"] = "UNMEASURED"
        return res
    h_star = max(cand, key=lambda h: cand[h]["is_t"])
    b = res["by_h"][h_star]
    res["h_star"] = h_star
    res["harvest"] = bool(b["is_t"] >= MIN_T and np.isfinite(b["oos_t"]) and
                          b["oos_t"] >= MIN_T and b["oos_mean"] > 0 and b["oos_n"] >= MIN_OOS)
    res["status"] = "HARVESTED" if res["harvest"] else "NOT_INFORMATIVE"
    return res


def own_exit_returns(bars: pd.DataFrame, signals: list[Any], symbol: str) -> np.ndarray:
    """The recipe's own stop/target/ttl replayed from the next open; a bar touching both counts
    as the stop (the conservative read of an unknown intrabar path)."""
    d = bars.sort_index()
    idx = d.index
    o, hi, lo, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    cost = _cost_frac(symbol, float(np.nanmedian(c)))
    out = []
    for s in signals:
        i = idx.get_indexer([s.time])[0]
        if i < 0 or i + 1 >= len(d) or not s.side:
            continue
        e, px = i + 1, o[i + 1]
        end = min(len(d) - 1, e + max(1, int(s.ttl_bars)) - 1)
        exit_px = c[end]
        for j in range(e, end + 1):
            hit_stop = lo[j] <= s.stop if s.side > 0 else hi[j] >= s.stop
            hit_tgt = hi[j] >= s.target if s.side > 0 else lo[j] <= s.target
            if hit_stop:
                exit_px = s.stop
                break
            if hit_tgt:
                exit_px = s.target
                break
        out.append(s.side * np.log(exit_px / px) - cost)
    return np.asarray(out, dtype=float)


def _build(family: str, symbol: str, params: dict[str, Any], bars: pd.DataFrame
           ) -> tuple[list[Any] | None, str]:
    try:
        from mt5desk.families import get_family_func
    except Exception as exc:                          # pragma: no cover
        return None, f"families unavailable: {type(exc).__name__}"
    fn = get_family_func(family)
    if fn is None:
        return None, "no constructor"
    kw = dict(params)
    sig = inspect.signature(fn).parameters
    if "symbol" in sig and "symbol" not in kw:
        kw["symbol"] = symbol
    kw = {k: v for k, v in kw.items() if k in sig or any(
        p.kind == p.VAR_KEYWORD for p in sig.values())}
    try:
        return list(fn(bars, **kw) or []), ""
    except Exception as exc:
        return None, type(exc).__name__


def remate(family: str, params: dict[str, Any], h: int) -> list[dict[str, Any]]:
    """The entry with a time exit at h: own stop, and a wide stop. Only accepted keys are set."""
    try:
        from mt5desk.families import get_family_func
        fn = get_family_func(family)
        sig = set(inspect.signature(fn).parameters) if fn else set()
    except Exception:
        sig = set()
    time_keys = [k for k in ("ttl_bars", "hold_bars", "max_hold", "exit_bars") if k in sig]
    if not time_keys:
        return []
    parts = decompose(params)
    base = {**parts["entry"], **parts["session"], **parts["regime"],
            **{k: v for k, v in parts["exit"].items() if k.lower() in _TIMING_KEYS}}
    exit_ = {k: int(h) for k in time_keys}
    if "rr" in sig:
        exit_["rr"] = NO_TARGET_RR
    out = [{**base, **parts["stop"], **exit_}]
    stop_key = next((k for k in ("stop_atr", "sl_atr", "stop_mult") if k in sig), None)
    if stop_key:
        wide = {**base, **{k: v for k, v in parts["stop"].items() if k != stop_key}, **exit_,
                stop_key: WIDE_STOP_ATR}
        if wide != out[0]:
            out.append(wide)
    return out


def _rejected_after(cursor: int, limit: int) -> list[dict[str, Any]]:
    """Rejected registry cells after `cursor` (rowid), oldest first, harvest children excluded."""
    from libs.moat import registry as reg
    c = reg.connect()
    try:
        q = ("SELECT rowid AS _rowid, * FROM research_candidates WHERE status='rejected' "
             "AND rowid > ? AND COALESCE(origin, '') NOT IN ({}) "
             "AND COALESCE(transformation, '') != 'component_remate' "
             "ORDER BY rowid LIMIT ?").format(",".join("?" * len(HARVEST_ORIGINS)))
        cur = c.execute(q, [int(cursor), *HARVEST_ORIGINS, int(limit)])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]
    finally:
        c.close()


def _may_hypothesise(symbol: str, family: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return False                                  # routing unknown: fail closed
    try:
        return bool(may_hypothesise(symbol, family))
    except Exception:
        return False


def harvest_pass(*, budget_s: float = 240.0, per_pass: int = PER_PASS,
                 rejected: list[dict[str, Any]] | None = None,
                 bars_for: Any = None, enqueue: Any = None, write: bool = True,
                 out_dir: Path | None = None, report_path: Path | None = None,
                 claim_ledger: Path | None = None, lane_ok: Any = None) -> dict[str, Any]:
    """One hourly pass over rejected cells not yet examined.

    Screens each cell on the bars before its screen cut only; enqueues re-mates AFTER the pass,
    each charged the whole pass's screen plus its parent's own trials (see the section note)."""
    t_end = time.monotonic() + budget_s
    od = out_dir or HARVEST_DIR
    try:
        st = json.loads((od / STATE_P.name).read_text("utf-8"))
    except (OSError, ValueError):
        st = {}
    cursor = int(st.get("cursor_rowid") or 0)
    seen = list(st.get("seen_injected") or [])
    seen_set = set(seen)
    tally: dict[str, int] = defaultdict(int)
    if rejected is None:
        try:
            todo = _rejected_after(cursor, per_pass)
        except Exception as exc:
            todo = []
            st["registry_error"] = type(exc).__name__
        held = len(todo)
    else:
        todo = [r for r in rejected if str(r.get("id")) not in seen_set
                and str(r.get("origin") or "") not in HARVEST_ORIGINS
                and str(r.get("transformation") or "") != "component_remate"][:per_pass]
        held = len(rejected)
    if bars_for is None:
        from research.orthogonal_sweep import _bars
        bars_for = _bars
    if enqueue is None and write:
        try:
            from libs.moat.registry import enqueue_candidate as enqueue
        except Exception:
            enqueue = None
    lane_ok = lane_ok or _may_hypothesise
    ledger: list[dict[str, Any]] = []
    pending: list[tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]] = []
    looks = 0
    for r in todo:
        if time.monotonic() > t_end:
            tally["deferred_budget"] += 1
            break
        cid, fam, sym = str(r.get("id")), str(r.get("family") or ""), str(r.get("symbol") or "")
        chart = str(r.get("chart") or "H1") or "H1"
        if rejected is None:
            cursor = max(cursor, int(r.get("_rowid") or 0))
        else:
            seen.append(cid)
            seen_set.add(cid)
        try:
            params = json.loads(r.get("params_json") or "{}") if isinstance(
                r.get("params_json"), str) else dict(r.get("params_json") or {})
        except ValueError:
            params = {}
        bars = bars_for(sym, chart)
        if bars is None or len(bars) < 300 or not {"open", "high", "low", "close"} <= set(
                bars.columns):
            tally["no_bars"] += 1
            continue
        cut = screen_cut(bars)
        if cut is None:
            tally["no_bars"] += 1
            continue
        screen = bars[pd.DatetimeIndex(bars.index).normalize() < cut]
        if len(screen) < 300:
            tally["screen_too_short"] += 1
            continue
        sigs, why = _build(fam, sym, params, screen)
        if sigs is None or not sigs:
            tally["unbuildable" if sigs is None else "no_signals"] += 1
            continue
        parts = decompose(params)
        em = entry_markout(screen, sigs, sym)
        looks += len(HORIZONS)
        own = own_exit_returns(screen, sigs, sym)
        split = int(len(own) * IS_SHARE)
        own_oos = own[split:]
        exit_verdict = "UNMEASURED"
        if em.get("h_star"):
            b = em["by_h"][em["h_star"]]
            if em.get("harvest") and (not len(own_oos) or float(np.mean(own_oos)) <= 0):
                exit_verdict = "EXIT_DESTROYED_EDGE"
            elif len(own_oos):
                exit_verdict = ("EXIT_ADDS" if float(np.mean(own_oos)) > b["oos_mean"]
                                else "EXIT_COSTS")
        row = {"candidate": cid, "family": fam, "symbol": sym, "chart": chart,
               "terminal_gate": r.get("terminal_gate"), "failure_class": r.get("failure_class"),
               "components": parts, "entry": em, "exit_verdict": exit_verdict,
               "own_exit_oos_mean": float(np.mean(own_oos)) if len(own_oos) else None,
               "screen_cut": str(cut.date()), "at": datetime.now(UTC).isoformat()}
        tally[em.get("status", "UNMEASURED")] += 1
        tally[exit_verdict] += 1
        if em.get("harvest"):
            recipes = remate(fam, params, int(em["h_star"]))
            if not recipes:
                tally["NO_TIME_EXIT_PARAM"] += 1
            elif not lane_ok(sym, fam):
                tally["LANE_SET_ASIDE"] += 1
                row["lane"] = "SET_ASIDE"
            else:
                pending.append((r, row, recipes))
        ledger.append(row)

    # THE BILL: every look this pass, plus each parent's own trials, charged to each child family.
    charges: dict[str, dict[str, Any]] = {}
    donated = 0
    for r, row, recipes in pending:
        cid, fam, sym, chart = row["candidate"], row["family"], row["symbol"], row["chart"]
        em = row["entry"]
        parent_trials = max(1, int(r.get("search_count") or 1))
        n_charge = looks + parent_trials + len(recipes)
        claim = f"harvest:{cid}"
        charge = charges.setdefault(claim, {"cells": 0, "selection_trials": n_charge,
                                            "sources": ["miner:component_harvest"],
                                            "families": [fam], "genome_ids": []})
        row["trial_charge"] = {"claim_family": claim, "selection_trials": n_charge,
                               "screen_looks": looks, "parent_trials": parent_trials}
        row["remated"] = []
        if enqueue is None:
            continue
        b = em["by_h"][em["h_star"]]
        mech = (f"component harvest: the ENTRY of rejected cell {cid} ({fam} on {sym} {chart}) "
                f"carries information alone -- {em['h_star']}-bar markout net of spread IS "
                f"t={b['is_t']:.2f}, OOS t={b['oos_t']:.2f} over {b['oos_n']} declustered "
                f"signals, screened before {row['screen_cut']} only -- while its own exit was "
                f"{row['exit_verdict']}. Re-mated with a time exit at the in-sample horizon; "
                f"charged {n_charge} selection trials ({looks} screen looks this pass + "
                f"{parent_trials} parent trials + {len(recipes)} re-mates).")
        for p in recipes:
            try:
                new_id, created = enqueue(
                    family=fam, symbol=sym, params=p, origin="component_harvest",
                    mechanism=mech, chart=chart, horizon=str(em["h_star"]),
                    generator="component_harvesting", department="research",
                    transformation="component_remate", parent_ids_json=[cid],
                    lineage_json={"parent_ids": [cid], "parent_family": fam,
                                  "claim_family": claim, "claim_selection_trials": n_charge,
                                  "screen_looks": looks, "parent_trials": parent_trials,
                                  "screen_cut": row["screen_cut"], "h_star": int(em["h_star"]),
                                  "producer": "component_harvest"},
                    causal_rationale=mech, pit_status="BARS_ONLY",
                    falsifier=(f"the re-mated rule loses its edge out of sample, or the "
                               f"entry's {em['h_star']}-bar markout falls below 0 net of "
                               f"spread"))
                row["remated"].append({"id": new_id, "created": bool(created), "params": p})
                if created:
                    donated += 1
                    charge["cells"] += 1
                    charge["genome_ids"].append(str(new_id))
            except Exception as exc:
                row.setdefault("enqueue_errors", []).append(type(exc).__name__)
    charged: dict[str, Any] = {"families": len(charges), "screen_looks": looks,
                               "selection_trials": sum(int(c["selection_trials"])
                                                       for c in charges.values())}
    if charges and write:
        try:
            from libs.research import claim_selection as cs
            lifetime = cs.update_ledger({"claim_families": charges}, path=claim_ledger,
                                        count_as="grid_cells")
            charged["lifetime_selection_trials"] = lifetime.get("lifetime_selection_trials")
        except Exception as exc:  # noqa: BLE001 - an uncharged pass is named, never silent
            charged["error"] = type(exc).__name__
            tally["TRIALS_UNCHARGED"] += len(charges)
    doc = {"generated_utc": datetime.now(UTC).isoformat(),
           "rejected_held": held, "examined_this_pass": len(ledger),
           "cursor_rowid": cursor, "tally": dict(tally), "donated_to_judge": donated,
           "trials_charged": charged,
           "rules": {"horizons": list(HORIZONS), "is_share": IS_SHARE, "min_t": MIN_T,
                     "min_oos": MIN_OOS, "wide_stop_atr": WIDE_STOP_ATR,
                     "screen_holdout": SCREEN_HOLDOUT},
           "external_ea_components": ("UNMEASURED: no parsed external EA corpus is held; the "
                                      "ComponentExtractor runs when one is"),
           "state": ("PRODUCING" if donated else "EXAMINING" if ledger else
                     "UNMEASURED: no rejected cells reachable" if not held else "IDLE")}
    if write:
        od.mkdir(parents=True, exist_ok=True)
        (od / STATE_P.name).write_text(json.dumps({"cursor_rowid": cursor,
                                                   "seen_injected": seen[-50000:]}),
                                       encoding="utf-8")
        with open(od / LEDGER_P.name, "a", encoding="utf-8") as fh:
            for row in ledger:
                fh.write(json.dumps(row, default=str) + "\n")
        rp = report_path or (od / REPORT_P.name if out_dir is not None else REPORT_P)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    import argparse
    for p in (str(_DESK), str(_DESK.parents[1])):
        if p not in __import__("sys").path:
            __import__("sys").path.insert(0, p)
    ap = argparse.ArgumentParser(description="Harvest informative entries from rejected cells")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--per-pass", type=int, default=PER_PASS)
    a = ap.parse_args(argv)
    doc = harvest_pass(budget_s=a.budget_s, per_pass=a.per_pass)
    print(json.dumps({k: doc[k] for k in ("examined_this_pass", "donated_to_judge", "state")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
