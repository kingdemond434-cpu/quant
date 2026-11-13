"""Compile an extracted rule onto a REGISTERED gauntlet family, or say why it cannot be.

The compiler never invents a family. A rule descriptor (what the extractor read out of code or
prose: indicators with their parameters, named session patterns, the chart, the instruments)
maps onto the desk's existing `mt5desk.families` by a fixed table. What does not map is not
dropped: it becomes RESEARCH_ONLY and its claim goes to the deepening worker, whose LLM seat
reads the verbatim text and proposes a family (the existing `story_mechanism` path).

Parameters the source STATES are `directly_published_rules`; a family default filled in to make
the rule executable, or a symbol transfer to an instrument the source did not name, makes the
rule `reconstructed_rules`. Both are sealed in the preregistration either way, and the cell says
which it is.

Compile-stage kills, with their codes:
    LEAKAGE_LOOKAHEAD  the rule reads the future (a repainting ZigZag/fractal, a negative
                       shift into bars that have not closed)
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from libs.mining.rejection import Reason

#: Instruments a symbol-agnostic rule (an EA that names no chart) transfers to, in order. The
#: desk's two deepest-history, lowest-cost instruments; each transfer is a descendant in the
#: same trial family, so the multiplicity charge is the family's, not the transfer count's.
DEFAULT_TRANSFER: tuple[str, ...] = ("EURUSD", "XAUUSD")
TIMEFRAMES: frozenset[str] = frozenset({"M1", "M5", "M15", "M30", "H1", "H4", "D1"})
MAX_SPECS_PER_RULE = 4
#: USES. Every cell serves one of these; a source that serves none is COLD.
USES: tuple[str, ...] = ("direct_cells", "indirect_cells", "allocation_intel")
#: INDIRECT CELLS multiply an existing family by a regime condition the gauntlet applies
#: honestly (`mt5desk.cell_modifiers`: volatility masks, month/quarter-end windows). The two
#: volatility regimes are always tried -- whether a published rule works only in one volatility
#: state is the commonest way a practitioner rule is half-right -- and the calendar ones when the
#: source names them. Each is a descendant of the direct cell, charged to the same trial family.
DEFAULT_REGIMES: tuple[str, ...] = ("high_vol", "low_vol")
MAX_INDIRECT_PER_SPEC = 4


@dataclass
class CompiledSpec:
    sym: str
    family: str
    params: dict[str, Any]
    timeframe: str
    subtype: str
    published: bool                       # every parameter came from the source
    transferred: bool                     # the instrument was not named by the source
    required_data: list[str] = field(default_factory=list)

    def spec(self) -> dict[str, Any]:
        p = dict(self.params)
        if self.timeframe != "H1":
            p["timeframe"] = self.timeframe
        return {"sym": self.sym, "family": self.family, "params": p,
                "timeframe": self.timeframe}


@dataclass
class CompileResult:
    specs: list[CompiledSpec]
    reason: Reason | None = None          # a kill at the compile stage
    detail: str = ""
    research_only: bool = False           # nothing compiled; hand the claim to deepening


def _pick(rule: Mapping[str, Any], key: str) -> dict[str, Any]:
    v = (rule.get("indicators") or {}).get(key)
    return dict(v) if isinstance(v, Mapping) else {}


def _entry(subtype: str, family: str, stated: dict[str, Any], defaults: dict[str, Any]
           ) -> tuple[str, str, dict[str, Any], bool]:
    params = {**defaults, **{k: v for k, v in stated.items() if v is not None}}
    published = all(k in stated and stated[k] is not None for k in defaults)
    return subtype, family, params, published


def candidate_families(rule: Mapping[str, Any]) -> list[tuple[str, str, dict[str, Any], bool]]:
    """(subtype, registered family, params, all-params-published) for every mapping hit."""
    pats = {str(p) for p in (rule.get("patterns") or [])}
    out: list[tuple[str, str, dict[str, Any], bool]] = []
    rsi, ma, bb = _pick(rule, "rsi"), _pick(rule, "ma"), _pick(rule, "bb")
    if rsi:
        out.append(_entry("rsi_reversion", "mean_reversion_rsi",
                          {"rsi_n": rsi.get("n"), "oversold": rsi.get("lo"),
                           "overbought": rsi.get("hi")},
                          {"rsi_n": 14, "oversold": 30, "overbought": 70}))
    if bb and "squeeze" in pats:
        out.append(_entry("bollinger_squeeze", "volatility_squeeze",
                          {"bb_n": bb.get("n"), "bb_k": bb.get("k")},
                          {"bb_n": 20, "bb_k": 2.0}))
    elif bb:
        out.append(_entry("bollinger_reversion", "mean_reversion_bollinger",
                          {"bb_n": bb.get("n"), "bb_k": bb.get("k")},
                          {"bb_n": 20, "bb_k": 2.0}))
    if ma.get("fast") and ma.get("slow") and int(ma["fast"]) < int(ma["slow"]):
        out.append(_entry("ma_cross", "trend_ma_cross",
                          {"fast_ema": ma.get("fast"), "slow_ema": ma.get("slow")},
                          {"fast_ema": 12, "slow_ema": 50}))
    table: tuple[tuple[str, str, str, dict[str, Any]], ...] = (
        ("asian_range_breakout", "session_range_breakout", "asian_range_breakout",
         {"wait_bars": 8}),
        ("session_breakout", "session_range_breakout", "session_breakout", {"wait_bars": 8}),
        ("monday_gap", "monday_gap", "weekend_gap", {"mode": "momentum"}),
        ("monday_gap_fade", "monday_gap", "weekend_gap_fade", {"mode": "fade"}),
        ("day_of_week", "dow_effect", "day_of_week", {"dow_long": 0, "dow_short": 3}),
        ("london_close", "london_close_momentum", "london_close", {"lookback": 2}),
        ("overnight", "overnight_drift", "overnight_drift", {"anchor_hour": 0,
                                                              "hold_bars": 8}),
        ("volume_spike", "volume_spike", "volume_spike", {"vol_mult": 2.0}),
        ("failed_breakout", "failed_breakout", "stop_hunt_reversal", {"level": "pdh"}),
        ("range_reversion", "range_reversion", "range_reversion", {"range_n": 20}),
        ("prev_day_breakout", "level_breakout", "prev_day_breakout", {"level": "pdh"}),
        ("asia_momentum", "asia_momentum", "asia_momentum", {"mom_thresh": 0.35}),
        ("momentum", "momentum_volgate", "time_series_momentum", {"mom_n": 6}),
    )
    for pat, family, subtype, defaults in table:
        if pat in pats:
            stated = dict((rule.get("pattern_params") or {}).get(pat) or {})
            out.append(_entry(subtype, family, stated, defaults))
    seen: set[str] = set()
    uniq = []
    for o in out:
        if o[1] not in seen:
            seen.add(o[1])
            uniq.append(o)
    return uniq


def compile_rule(rule: Mapping[str, Any], *,
                 universe: set[str] | None = None,
                 family_params: Callable[[str], set[str] | None] | None = None
                 ) -> CompileResult:
    """Rule descriptor -> executable specs. `family_params(name)` returns the family's accepted
    keyword set (None when the family is not registered), so a param the family would reject
    is dropped here rather than failing the build later."""
    leaks = [str(x) for x in (rule.get("lookahead") or [])]
    if leaks:
        return CompileResult([], Reason.LEAKAGE_LOOKAHEAD,
                             "rule reads the future: " + "; ".join(leaks[:3]))
    fams = candidate_families(rule)
    if not fams:
        return CompileResult([], None, "no registered family expresses this rule",
                             research_only=True)
    tf = str(rule.get("timeframe") or "H1").upper()
    if tf not in TIMEFRAMES:
        tf = "H1"
    named = [str(s).upper() for s in (rule.get("symbols") or [])]
    if universe is not None:
        named = [s for s in named if s in universe]
    syms: list[tuple[str, bool]] = [(s, False) for s in dict.fromkeys(named)]
    if not syms:
        syms = [(s, True) for s in DEFAULT_TRANSFER if universe is None or s in universe]
    specs: list[CompiledSpec] = []
    for subtype, family, params, published in fams:
        accepted = family_params(family) if family_params is not None else None
        if family_params is not None and accepted is None:
            continue                                   # family not registered on this box
        if accepted is not None:
            params = {k: v for k, v in params.items() if k in accepted}
        for sym, transferred in syms:
            specs.append(CompiledSpec(
                sym=sym, family=family, params=dict(params), timeframe=tf, subtype=subtype,
                published=published and not transferred, transferred=transferred,
                required_data=[f"bars:{sym}:{tf}"]))
            if len(specs) >= MAX_SPECS_PER_RULE:
                break
        if len(specs) >= MAX_SPECS_PER_RULE:
            break
    if not specs:
        return CompileResult([], None, "mapped families are not registered here",
                             research_only=True)
    return CompileResult(specs)


def indirect_variants(spec: CompiledSpec, rule: Mapping[str, Any]) -> list[CompiledSpec]:
    """Regime-conditioned children of a direct spec (the `indirect_cells` use)."""
    stated = [str(r) for r in (rule.get("regimes") or [])]
    regimes = list(dict.fromkeys([*stated, *DEFAULT_REGIMES]))[:MAX_INDIRECT_PER_SPEC]
    out = []
    for r in regimes:
        if spec.params.get("regime") == r:
            continue
        out.append(CompiledSpec(sym=spec.sym, family=spec.family,
                                params={**spec.params, "regime": r}, timeframe=spec.timeframe,
                                subtype=f"{spec.subtype}@{r}",
                                published=spec.published and r in stated,
                                transferred=spec.transferred,
                                required_data=[*spec.required_data, f"regime:{r}"]))
    return out


def falsifier_for(spec: CompiledSpec) -> str:
    return (f"H0: {spec.family}{spec.params} on {spec.sym} {spec.timeframe} has net-of-cost "
            "expected return <= 0. Rejected unless every gate of the sealed external gauntlet "
            "passes (costs at 1x and 3x, walk-forward, CPCV, PBO, SPA, deflated Sharpe at "
            "lifetime trials, lockbox). The source's own performance claims are not evidence.")
