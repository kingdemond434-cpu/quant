"""NEAR-DUPLICATE RULES and the CHEAP STRUCTURAL DUPLICATE CHECK (breadth law §3, producer law 7).

THE LAW (2026-10-05, ANTI-SATURATION §3). A candidate that differs from a certified sleeve ONLY by

    symbol            the same rule, parameters, chart and clock on another ticker
    small_param       every parameter within PARAM_BAND (10%) of the certified one
    small_stop        only stop-like parameters differ, each within STOP_BAND (25%)
    minor_tf_shift    the same rule on the adjacent chart (M15 vs M30, H1 vs H4)
    equivalent_ind    an equivalent indicator (EMA for SMA, Stochastic for RSI, ...)
    renamed_source    the identical spec under another producer's label

is a NEAR-DUPLICATE unless evidence demonstrates otherwise. The evidence the rule accepts is the
one the saturation map accepts for exception F: a measured return correlation on at least
`MIN_INDEPENDENCE_OBS` days whose upper 95% bound is within `INDEPENDENT_RHO` (row field
`measured_independence = {n, rho_upper}`), or a declared QUALITY challenger (exception G).

THE CHEAP STRUCTURAL CHECK (producer law 7, BREADTH-0246..0256) runs on the docket BEFORE the full
backtest: a row whose structural key -- mechanism, payer, information source, factor loading,
symbol cluster, session, timeframe, horizon, entry geometry, exit geometry, regime dependence --
equals a certified sleeve's is a structural duplicate. Each key component is published.

ORDER AND PRICE ONLY. A near-duplicate is never removed: it is TAXED (its breadth value is the
duplicate floor) and goes to the duplicate tail of its family stream, and when the judge reaches
it, it is charged its trial exactly like any cell. Nothing here touches a gate, a verdict, a
trial count, capital, sizing or promotion.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

PARAM_BAND = 0.10
STOP_BAND = 0.25
#: The rule names, in the order they are tested (first match is the reason recorded).
RULES = ("renamed_source", "symbol", "small_stop", "small_param", "minor_tf_shift",
         "equivalent_indicator")
TF_LADDER = ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1")
STOP_KEYS = frozenset({"stop", "sl", "stop_loss", "stop_mult", "atr_stop", "stop_atr", "trail",
                       "trail_mult", "trailing_stop", "stop_pct", "sl_mult", "sl_atr"})
#: Indicator equivalence classes (law: "equivalent indicator"). A family or an `indicator`
#: parameter in one class is a near-duplicate of the same rule built on another member.
EQUIVALENT_INDICATORS: tuple[frozenset[str], ...] = (
    frozenset({"sma", "ema", "wma", "hma", "dema", "tema", "kama", "ma"}),
    frozenset({"rsi", "stoch", "stochastic", "williams_r", "willr", "cci", "mfi"}),
    frozenset({"atr", "stdev", "std", "natr", "parkinson", "realized_vol"}),
    frozenset({"donchian", "channel_breakout", "highest_high", "range_breakout"}),
    frozenset({"bollinger", "keltner", "zscore_band", "envelope"}),
    frozenset({"macd", "ppo", "ma_cross", "trend_ma_cross"}),
)
MIN_INDEPENDENCE_OBS = 60
INDEPENDENT_RHO = 0.3


def _tf(row: Mapping[str, Any]) -> str:
    p = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    return str((p or {}).get("timeframe") or row.get("timeframe") or row.get("tf") or "H1").upper()


def _sym(row: Mapping[str, Any]) -> str:
    return str(row.get("symbol") or row.get("sym") or "").upper()


def _fam(row: Mapping[str, Any]) -> str:
    return str(row.get("family") or row.get("fam") or "")


def _session(row: Mapping[str, Any]) -> str:
    p = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    return str((p or {}).get("session") or row.get("selector") or row.get("sess")
               or row.get("session") or "").lower()


def _params(row: Mapping[str, Any]) -> dict[str, Any]:
    p = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    return {str(k): v for k, v in (p or {}).items() if k not in ("timeframe", "session")}


def _canon(params: Mapping[str, Any]) -> str:
    return json.dumps(dict(params), sort_keys=True, default=str)


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _within(a: Any, b: Any, band: float) -> bool:
    x, y = _num(a), _num(b)
    if x is None or y is None:
        return a == b
    if x == y:
        return True
    scale = max(abs(x), abs(y))
    return scale > 0 and abs(x - y) / scale <= band


def indicator_class(name: str) -> int | None:
    toks = {t for t in str(name).lower().replace("-", "_").split("_") if t} | {str(name).lower()}
    for i, cls in enumerate(EQUIVALENT_INDICATORS):
        if toks & cls:
            return i
    return None


def _ind_key(row: Mapping[str, Any]) -> tuple[int, str] | None:
    p = _params(row)
    ind = p.get("indicator")
    c = indicator_class(str(ind)) if ind is not None else indicator_class(_fam(row))
    if c is None:
        return None
    rest = {k: v for k, v in p.items() if k != "indicator"}
    return c, _canon(rest)


def has_evidence(row: Mapping[str, Any]) -> bool:
    """Evidence that overturns a near-duplicate rule: measured independence (exception F) on a
    sufficient sample, or a declared QUALITY challenger (exception G)."""
    ov = row.get("measured_overlap")
    ovs = _num(ov.get("overlap_score")) if isinstance(ov, Mapping) else _num(ov)
    # behavioural overlap (drawdown, co-crash, event, regime, signal, lead/lag) above the
    # independence bound: a low rho alone does not overturn the rule
    overlaps = ovs is not None and ovs > INDEPENDENT_RHO
    mi = row.get("measured_independence")
    if isinstance(mi, Mapping) and not overlaps:
        n, hi = _num(mi.get("n")), _num(mi.get("rho_upper"))
        if n is not None and hi is not None and n >= MIN_INDEPENDENCE_OBS \
                and abs(hi) <= INDEPENDENT_RHO:
            return True
    return str(row.get("breadth_exception") or "").strip().upper()[:1] == "G" or bool(
        row.get("challenger_of") or row.get("parent_certificate"))


def rule_between(cand: Mapping[str, Any], cert: Mapping[str, Any]) -> str | None:
    """The near-duplicate rule `cand` breaks against ONE certified spec, or None."""
    s1, s2 = _sym(cand), _sym(cert)
    f1, f2 = _fam(cand), _fam(cert)
    t1, t2 = _tf(cand), _tf(cert)
    c1, c2 = _session(cand), _session(cert)
    p1, p2 = _params(cand), _params(cert)
    same_clock = c1 == c2 or not c1 or not c2
    if f1 == f2 and s1 == s2 and t1 == t2 and same_clock and _canon(p1) == _canon(p2):
        # The identical spec, whatever label (producer, source) it arrives under.
        return "renamed_source"
    if f1 == f2 and s1 != s2 and t1 == t2 and same_clock and _canon(p1) == _canon(p2):
        return "symbol"
    if f1 == f2 and s1 == s2 and t1 == t2 and same_clock and set(p1) == set(p2):
        diff = [k for k in p1 if p1[k] != p2[k]]
        if diff and all(k.lower() in STOP_KEYS for k in diff) \
                and all(_within(p1[k], p2[k], STOP_BAND) for k in diff):
            return "small_stop"
        if diff and all(_within(p1[k], p2[k], PARAM_BAND) for k in diff):
            return "small_param"
    if f1 == f2 and s1 == s2 and same_clock and _canon(p1) == _canon(p2) and t1 != t2 \
            and t1 in TF_LADDER and t2 in TF_LADDER \
            and abs(TF_LADDER.index(t1) - TF_LADDER.index(t2)) == 1:
        return "minor_tf_shift"
    k1, k2 = _ind_key(cand), _ind_key(cert)
    if k1 is not None and k1 == k2 and s1 == s2 and t1 == t2 and same_clock \
            and (f1 != f2 or p1.get("indicator") != p2.get("indicator")):
        return "equivalent_indicator"
    return None


class Index:
    """The certified book keyed so each rule is a dictionary lookup, not a scan of the book."""

    def __init__(self, specs: Iterable[Mapping[str, Any]]):
        self.n = 0
        self.exact: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
        self.by_spec: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
        self.by_cell: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
        self.by_noTF: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
        self.by_ind: dict[tuple[int, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
        for s in specs:
            self.n += 1
            sym, fam, tf, can = _sym(s), _fam(s), _tf(s), _canon(_params(s))
            self.exact.setdefault((fam, sym, tf, can), s)
            self.by_spec[(fam, tf, can)].append(s)
            self.by_cell[(fam, sym, tf)].append(s)
            self.by_noTF[(fam, sym, can)].append(s)
            ik = _ind_key(s)
            if ik is not None:
                self.by_ind[(ik[0], ik[1], sym, tf)].append(s)

    def rule_for(self, row: Mapping[str, Any], cap: int = 200) -> tuple[str, str] | None:
        """(rule, twin key) for the first rule `row` breaks against the book, or None."""
        sym, fam, tf, can = _sym(row), _fam(row), _tf(row), _canon(_params(row))
        pools: list[list[Mapping[str, Any]]] = []
        ex = self.exact.get((fam, sym, tf, can))
        if ex is not None:
            pools.append([ex])
        pools += [self.by_spec.get((fam, tf, can), [])[:cap],
                  self.by_cell.get((fam, sym, tf), [])[:cap],
                  self.by_noTF.get((fam, sym, can), [])[:cap]]
        ik = _ind_key(row)
        if ik is not None:
            pools.append(self.by_ind.get((ik[0], ik[1], sym, tf), [])[:cap])
        for pool in pools:
            for cert in pool:
                r = rule_between(row, cert)
                if r is not None:
                    return r, str(cert.get("key") or f"{_sym(cert)}.{_fam(cert)}")
        return None


def near_duplicate(row: Mapping[str, Any], index: Index) -> tuple[str, str] | None:
    """(rule, twin) when `row` is a near-duplicate of a certified sleeve with no overturning
    evidence; None otherwise. Evidence is checked LAST: the rule is still recorded upstream."""
    hit = index.rule_for(row)
    if hit is None or has_evidence(row):
        return None
    return hit


# --------------------------------------------------------------- cheap structural check
#: The structural key, in the producer law's order (BREADTH-0246..0256).
STRUCTURAL_KEY = ("mechanism", "payer", "information_source", "factor", "symbol_cluster",
                  "session", "timeframe", "horizon", "entry_geometry", "exit_geometry",
                  "regime_dependence")


def structural_key(axes: Mapping[str, Any], cluster_of: Mapping[str, str] | None = None
                   ) -> tuple[str, ...]:
    """The key from a row's 21-axis reading (`certificate_saturation.axes_of`). A component the
    axes do not carry reads UNKNOWN, which matches only another UNKNOWN -- an unmeasured axis
    never makes two rows look different, and never makes them look identical by itself."""
    sym = str(axes.get("instrument") or "").upper()
    sc = (cluster_of or {}).get(sym) or str(axes.get("factor_residual")
                                            or axes.get("economic_factor") or "UNKNOWN")

    def g(k: str) -> str:
        return str(axes.get(k) or "UNKNOWN")
    return (g("_mechanism"), g("payer"), g("information_source"), g("economic_factor"), str(sc),
            g("session"), g("timeframe"), g("horizon"), g("entry_mechanism"),
            g("exit_mechanism"), g("regime"))


__all__ = [
    "EQUIVALENT_INDICATORS",
    "PARAM_BAND",
    "RULES",
    "STOP_BAND",
    "STRUCTURAL_KEY",
    "Index",
    "has_evidence",
    "indicator_class",
    "near_duplicate",
    "rule_between",
    "structural_key",
]
