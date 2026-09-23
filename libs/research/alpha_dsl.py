"""THE EXPRESSION FACTORY'S DSL: typed fields, the 101 parent genomes, canonical form, panels.

This module EXTENDS `alpha_grammar` (ledger G2) rather than writing a second grammar. The grammar
owns the operators, the type and unit algebra, evaluation and the search moves; this module owns
what the WorldQuant-style factory (LAWS 5l, RESEARCH 11) adds on top of it:

  * TYPED FIELDS from the desk's data lake -- bars per symbol, the `axes/*.json` series (COT
    positioning, BIS policy rates, ECB/FRED macro levels, the shadow latents), the representation
    forge's manifest -- each with a SEMANTIC TYPE (price, volume, spread, flow, macro_level,
    macro_surprise, positioning, rate, event_intensity), the grammar terminal that carries it, and
    an AVAILABILITY RULE: how the field's `available_time` is known. A field whose availability is
    UNKNOWN is not a field the factory may search on (Tier 0, future-data impossibility), because
    a series joined at its period time rather than its publication time is a lookahead nobody can
    see in a backtest.
  * THE 101 FORMULAIC ALPHAS (Kakushadze 2016, arXiv:1601.00991, a public paper) transcribed as
    PARENT GENOMES A_i = (D, O, T, H, S, N, E): data fields, operator tree, transformations,
    horizon, state, normalisation / cross-section, execution assumptions. The paper's formulas are
    carried verbatim as the parent's O and TRANSPILED into the grammar by semantic type: equity
    volume -> tick activity, adv{d} -> rolling activity, cross-sectional rank -> basket rank
    (`xrank`), industry neutralisation -> basket z-score (`xzscore`). An alpha whose fields have no
    lawful MT5 analogue (vwap: the grammar's own unit algebra refuses the proxy; cap: no market
    capitalisation for a CFD) is NONTESTABLE with the missing field NAMED, never approximated. An
    alpha whose transcription is deeper than the executor's `MAX_DEPTH` is TOO_DEEP: a real genome
    whose descendants reach the executor only through the factory's pruning moves.
  * CANONICAL FORM: exact simplifications and commutative argument ordering, so two spellings of
    one recipe hash the same (Tier 0, duplicate AST) and the trial FAMILY -- the skeleton with its
    windows blanked -- is what an evaluation is charged to (LAWS 5k: EMA(19,57) and EMA(20,58)
    are one family).
  * PANEL SEEDING: the grammar's `xrank` / `xzscore` nodes evaluate only where a caller has
    computed the child on every member of the cell's basket and seeded each member's memo with
    the cross-sectional series. `seed_panels` is that caller.

Nothing here has authority: a genome is a hypothesis about a public formula, a field is a series
the desk can read, and the factory (desks/mt5/research/expression_factory.py) is the only consumer.
"""
from __future__ import annotations

import json
import math
import re
import warnings
from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.research import alpha_grammar as ag

Expr = Any

# ============================================================================ semantic types
SEMANTIC_TYPES: tuple[str, ...] = ("price", "volume", "spread", "flow", "macro_level",
                                   "macro_surprise", "positioning", "rate", "event_intensity")
#: Semantic type -> the grammar terminal that carries it: THE MT5 ANALOGUE BY SEMANTIC TYPE.
#: `volume` is tick activity because Fusion publishes tick counts, not contracts; `rate` rides
#: the grammar's FUNDAMENTAL terminal (carry, the instrument's own fundamental); both macro types
#: ride MACRO; event intensity rides EVENT.
SEMANTIC_TERMINAL: dict[str, str] = {
    "price": "close", "volume": "activity", "spread": "spread", "flow": "flow",
    "macro_level": "macro", "macro_surprise": "macro", "positioning": "positioning",
    "rate": "fundamental", "event_intensity": "event",
}
#: Availability rules a field may declare. UNKNOWN is a rule too: it is the rule that forbids.
AVAILABILITY_RULES: tuple[str, ...] = ("bar_close", "knowable_at", "available_time",
                                       "period_end+1d", "month_end+1d", "UNKNOWN")


@dataclass(frozen=True)
class Field:
    """One typed field: what it is, which terminal carries it, and WHEN a bar may know it."""

    name: str
    semantic: str
    terminal: str
    source: str
    availability: str
    unit: str = "dimensionless"
    description: str = ""
    n_points: int = 0
    symbol: str = ""                 #: empty = global (macro); else the instrument it belongs to

    def causal(self) -> bool:
        """Can a bar be told when this field became known? UNKNOWN cannot be searched on."""
        return self.availability in AVAILABILITY_RULES and self.availability != "UNKNOWN"


_BAR_SEMANTIC: dict[str, str] = {
    "close": "price", "open": "price", "high": "price", "low": "price", "atr": "price",
    "ret": "price", "range": "price", "body": "price", "vol": "price",
    "activity": "volume", "spread": "spread", "flow": "flow",
}


def bar_fields() -> tuple[Field, ...]:
    """The fields every symbol's own bars carry, plus the economic-driver closes."""
    out = [Field(t, _BAR_SEMANTIC[t], t, "bars", "bar_close", str(ag.TERMINAL_UNITS[t]),
                 f"bar terminal {t}") for t in ag.BAR_TERMINALS]
    out += [Field(t, "price", t, f"driver:{t}", "bar_close", "quote",
                  f"economic driver role {t.upper()} (another instrument's close)")
            for t in ag.DRIVER_TERMINALS]
    return tuple(out)


# ---------------------------------------------------------------------------- the data lake
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


#: Per-axis publication lag for series that carry a PERIOD date rather than a release time. The
#: ECB reference rate and a FRED daily series are published after the close of the day they
#: describe; one day is the conservative declaration and it is a declaration, not a measurement.
_SERIES_LAG_DAYS = 1


def axis_fields(axes_dir: Path) -> tuple[Field, ...]:
    """Typed fields from `desks/mt5/data/axes/*.json`, one per numeric column or series.

    Shapes seen on this desk: COT (`rows` keyed by symbol + knowable_at), BIS policy rates
    (`rows` keyed by symbol + month), ECB / FRED (`series[name].points` of `d`,`v`), the shadow
    latents (`points` carrying their own `available_time`). Anything else is read as a series with
    UNKNOWN availability, which names it without letting the search touch it.
    """
    out: list[Field] = []
    for path in sorted(axes_dir.glob("*.json")):
        doc = _read_json(path)
        if not isinstance(doc, dict):
            continue
        axis = str(doc.get("axis") or "")
        aid = str(doc.get("id") or path.stem)
        rows = doc.get("rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            sample = rows[0]
            numeric = [k for k, v in sample.items()
                       if isinstance(v, (int, float)) and not isinstance(v, bool)
                       and k not in ("knowable_at", "as_of")]
            syms = sorted({str(r.get("symbol") or "") for r in rows if r.get("symbol")})
            if axis == "positioning":
                sem, rule = "positioning", "knowable_at"
            elif axis == "policy":
                sem, rule = "rate", "month_end+1d"
            else:
                sem, rule = "macro_level", ("knowable_at" if "knowable_at" in sample
                                            else "UNKNOWN")
            for col in numeric:
                for sym in syms:
                    n = sum(1 for r in rows if r.get("symbol") == sym
                            and isinstance(r.get(col), (int, float)))
                    out.append(Field(f"{aid}.{col}", sem, SEMANTIC_TERMINAL[sem],
                                     f"axis:{path.stem}", rule, "dimensionless",
                                     str(doc.get("shape") or ""), n, sym))
            continue
        series = doc.get("series")
        if isinstance(series, dict):
            for name, s in series.items():
                pts = s.get("points") if isinstance(s, dict) else None
                n = len(pts) if isinstance(pts, list) else 0
                first: dict[str, Any] = (pts[0] if isinstance(pts, list) and pts
                                         and isinstance(pts[0], dict) else {})
                rule = ("available_time" if first.get("available_time") else
                        "period_end+1d" if first.get("d") else "UNKNOWN")
                out.append(Field(f"{aid}.{name}", "macro_level", "macro", f"axis:{path.stem}",
                                 rule, "dimensionless",
                                 str((s or {}).get("what") if isinstance(s, dict) else ""), n))
    return tuple(out)


def representation_fields(repr_dir: Path) -> tuple[Field, ...]:
    """Typed fields from the representation forge's manifest, if it is present."""
    doc = _read_json(repr_dir / "manifest.json")
    if not isinstance(doc, dict):
        return ()
    out: list[Field] = []
    for r in doc.get("representations") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        info = str(r.get("information_type") or "").lower()
        sem = ("rate" if info == "policy" else "positioning" if info == "positioning"
               else "flow" if info == "flow" else "macro_level")
        out.append(Field(str(r["id"]), sem, SEMANTIC_TERMINAL[sem],
                         f"representation:{r.get('file') or ''}", "available_time",
                         "dimensionless", str(r.get("dataset") or ""),
                         int(r.get("n") or 0)))
    return tuple(out)


def _utc(ts: Any) -> pd.Timestamp | None:
    try:
        t = pd.Timestamp(ts)
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _availability_time(row: Mapping[str, Any], rule: str) -> pd.Timestamp | None:
    """When a bar may first know this row, under its declared rule. None = never."""
    if rule == "available_time":
        return _utc(row.get("available_time"))
    if rule == "knowable_at":
        return _utc(row.get("knowable_at"))
    if rule == "period_end+1d":
        t = _utc(row.get("d") or row.get("period_time") or row.get("date"))
        return None if t is None else t + pd.Timedelta(days=_SERIES_LAG_DAYS)
    if rule == "month_end+1d":
        raw = str(row.get("knowable_at") or row.get("d") or "")
        m = re.match(r"^(\d{4})-(\d{2})", raw)
        if not m:
            return None
        y, mo = int(m.group(1)), int(m.group(2))
        first_next = datetime(y + (mo == 12), 1 if mo == 12 else mo + 1, 1, tzinfo=UTC)
        return pd.Timestamp(first_next + timedelta(days=1))
    return None


class FieldCatalogue:
    """Every typed field the lake exposes, and the causal join that puts one on a bar index."""

    def __init__(self, axes_dir: Path | None = None, repr_dir: Path | None = None,
                 extra: Iterable[Field] = ()) -> None:
        self.axes_dir = axes_dir
        self.repr_dir = repr_dir
        fields = list(bar_fields())
        if axes_dir is not None and axes_dir.exists():
            fields += list(axis_fields(axes_dir))
        if repr_dir is not None and repr_dir.exists():
            fields += list(representation_fields(repr_dir))
        fields += list(extra)
        self.fields: tuple[Field, ...] = tuple(fields)
        self._docs: dict[str, Any] = {}

    def by_name(self, name: str, symbol: str = "") -> Field | None:
        for f in self.fields:
            if f.name == name and (not f.symbol or f.symbol == symbol):
                return f
        return None

    def external(self, symbol: str) -> list[Field]:
        """Fields that could bind an EXTERNAL grammar terminal for `symbol`, causal ones first."""
        out = [f for f in self.fields if f.terminal in ag.EXTERNAL_TERMINALS
               and (not f.symbol or f.symbol == symbol) and f.n_points > 0]
        return sorted(out, key=lambda f: (not f.causal(), f.terminal, f.name))

    def census(self) -> dict[str, Any]:
        by_sem: dict[str, int] = {}
        for f in self.fields:
            by_sem[f.semantic] = by_sem.get(f.semantic, 0) + 1
        return {"n_fields": len(self.fields), "by_semantic": by_sem,
                "uncausal": sorted({f.name for f in self.fields if not f.causal()})[:50],
                "n_uncausal": sum(1 for f in self.fields if not f.causal())}

    # ---- the causal join
    def _doc(self, source: str) -> Any:
        if source not in self._docs:
            kind, _, stem = source.partition(":")
            base = self.axes_dir if kind == "axis" else self.repr_dir
            self._docs[source] = (_read_json(base / f"{stem}.json") if base is not None
                                  and kind == "axis" else
                                  _read_json(base / stem) if base is not None else None)
        return self._docs[source]

    def _rows(self, f: Field) -> list[dict[str, Any]]:
        doc = self._doc(f.source)
        if not isinstance(doc, dict):
            return []
        col = f.name.split(".", 1)[1] if "." in f.name else f.name
        rows = doc.get("rows")
        if isinstance(rows, list):
            return [{"t": _availability_time(r, f.availability), "v": r.get(col)}
                    for r in rows if isinstance(r, dict) and r.get("symbol") == f.symbol]
        series = doc.get("series")
        if isinstance(series, dict) and col in series and isinstance(series[col], dict):
            pts = series[col].get("points") or []
            return [{"t": _availability_time(p, f.availability),
                     "v": p.get("v", p.get("value"))} for p in pts if isinstance(p, dict)]
        pts = doc.get("points")
        if isinstance(pts, list):
            return [{"t": _availability_time(p, f.availability),
                     "v": p.get("v", p.get("value"))} for p in pts if isinstance(p, dict)]
        return []

    def series(self, f: Field, index: pd.Index) -> pd.Series | None:
        """The field on `index`: the value LAST KNOWN at each bar, or None when unbindable.

        Rows are placed at their availability time and forward-filled -- the only causal join.
        An uncausal field returns None here as well as failing Tier 0, so no path evaluates it.
        """
        if not f.causal() or f.source == "bars" or f.source.startswith("driver:"):
            return None
        rows = [(r["t"], r["v"]) for r in self._rows(f)
                if r["t"] is not None and isinstance(r["v"], (int, float))
                and not isinstance(r["v"], bool) and math.isfinite(float(r["v"]))]
        if not rows:
            return None
        s = pd.Series({t: float(v) for t, v in rows}).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        idx = pd.DatetimeIndex(pd.to_datetime(index, utc=True, errors="coerce"))
        return s.reindex(idx, method="ffill")


# ---------------------------------------------------------------------------- Tier 0 checks
def future_data_impossible(expr: Expr, bindings: Mapping[str, Field]) -> str | None:
    """Why this tree could read the future, or None when every external terminal is causal.

    The grammar has no forward operator, so the only lookahead channel is a FIELD joined at a
    time the desk could not have known it. Every external terminal in the tree must be bound to
    a field whose availability rule is known; an unbound external is 'UNMEASURED', which is the
    same refusal for a different reason.
    """
    for t in sorted(ag.terminals_in(expr)):
        if t not in ag.EXTERNAL_TERMINALS:
            continue
        f = bindings.get(t)
        if f is None:
            return f"external terminal {t} is unbound: UNMEASURED, not searchable"
        if not f.causal():
            return f"field {f.name} bound to {t} has availability {f.availability}: a join " \
                   f"at period time is a lookahead"
    return None


# ============================================================================ canonical form
_COMMUTATIVE = frozenset({"add", "mul", "max2", "min2", "corr", "cov"})


def canonical(expr: Expr) -> Expr:
    """An EXACT canonical form: same recipe, one spelling.

    neg(neg(x)) = x; abs(abs(x)) = abs(neg(x)) = abs(x); sign(sign(x)) = sign(x);
    xrank(xrank(x)) = xrank(x) (a percentile of a percentile across the same peers);
    add(neg(a), neg(b)) = neg(add(a, b)); commutative arguments sorted by key. Every rule is an
    identity, so the canonical tree evaluates to the same series as the original.
    """
    if not isinstance(expr, (list, tuple)):
        return expr
    op = str(expr[0])
    kids = [canonical(c) if isinstance(c, (list, tuple, str)) else c for c in expr[1:]]
    out: list[Any] = [op, *kids]
    a: Any = kids[0] if kids else None
    if isinstance(a, list) and a:
        inner = str(a[0])
        if op == "neg" and inner == "neg":
            return a[1]
        if op == "abs" and inner in ("abs", "neg"):
            return ["abs", a[1]] if inner == "neg" else a
        if op == "sign" and inner == "sign":
            return a
        if op == "xrank" and inner == "xrank":
            return a
    if op == "add" and len(kids) == 2 and all(isinstance(k, list) and k and k[0] == "neg"
                                              for k in kids):
        return canonical(["neg", ["add", kids[0][1], kids[1][1]]])
    if op in _COMMUTATIVE and len(kids) >= 2:
        x, y = kids[0], kids[1]
        if ag.key(x) > ag.key(y):
            out[1], out[2] = y, x
    return out


def canonical_key(expr: Expr) -> str:
    return ag.key(canonical(expr))


def skeleton(expr: Expr) -> Expr:
    """The tree with every window blanked: what a trial FAMILY is."""
    if not isinstance(expr, (list, tuple)):
        return expr
    return [expr[0], *[skeleton(c) if isinstance(c, (list, tuple, str)) else 0
                       for c in expr[1:]]]


def family_key(expr: Expr) -> str:
    """The family an evaluation is charged to: the canonical skeleton, windows blanked."""
    return ag.key(skeleton(canonical(expr)))


def windows_in(expr: Expr) -> list[int]:
    if not isinstance(expr, (list, tuple)):
        return []
    out: list[int] = []
    for c in expr[1:]:
        if isinstance(c, (list, tuple, str)):
            out.extend(windows_in(c))
        elif isinstance(c, int) and not isinstance(c, bool):
            out.append(int(c))
    return out


# ============================================================================ the 101 alphas
#: THE PAPER'S FORMULAS, VERBATIM (Kakushadze, "101 Formulaic Alphas", arXiv:1601.00991, 2016;
#: the formulas are public and the law names them as seeds). The transpiler below decides what
#: each one becomes on this desk; nothing here is edited to make it fit.
ALPHA101: dict[str, str] = {
    "alpha001": "(rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)",  # noqa: E501
    "alpha002": "(-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))",
    "alpha003": "(-1 * correlation(rank(open), rank(volume), 10))",
    "alpha004": "(-1 * Ts_Rank(rank(low), 9))",
    "alpha005": "(rank((open - (sum(vwap, 10) / 10))) * (-1 * abs(rank((close - vwap)))))",
    "alpha006": "(-1 * correlation(open, volume, 10))",
    "alpha007": "((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1 * 1))",  # noqa: E501
    "alpha008": "(-1 * rank(((sum(open, 5) * sum(returns, 5)) - delay((sum(open, 5) * sum(returns, 5)), 10))))",  # noqa: E501
    "alpha009": "((0 < ts_min(delta(close, 1), 5)) ? delta(close, 1) : ((ts_max(delta(close, 1), 5) < 0) ? delta(close, 1) : (-1 * delta(close, 1))))",  # noqa: E501
    "alpha010": "rank(((0 < ts_min(delta(close, 1), 4)) ? delta(close, 1) : ((ts_max(delta(close, 1), 4) < 0) ? delta(close, 1) : (-1 * delta(close, 1)))))",  # noqa: E501
    "alpha011": "((rank(ts_max((vwap - close), 3)) + rank(ts_min((vwap - close), 3))) * rank(delta(volume, 3)))",  # noqa: E501
    "alpha012": "(sign(delta(volume, 1)) * (-1 * delta(close, 1)))",
    "alpha013": "(-1 * rank(covariance(rank(close), rank(volume), 5)))",
    "alpha014": "((-1 * rank(delta(returns, 3))) * correlation(open, volume, 10))",
    "alpha015": "(-1 * sum(rank(correlation(rank(high), rank(volume), 3)), 3))",
    "alpha016": "(-1 * rank(covariance(rank(high), rank(volume), 5)))",
    "alpha017": "(((-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1))) * rank(ts_rank((volume / adv20), 5)))",  # noqa: E501
    "alpha018": "(-1 * rank(((stddev(abs((close - open)), 5) + (close - open)) + correlation(close, open, 10))))",  # noqa: E501
    "alpha019": "((-1 * sign(((close - delay(close, 7)) + delta(close, 7)))) * (1 + rank((1 + sum(returns, 250)))))",  # noqa: E501
    "alpha020": "(((-1 * rank((open - delay(high, 1)))) * rank((open - delay(close, 1)))) * rank((open - delay(low, 1))))",  # noqa: E501
    "alpha021": "((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1 * 1) : (((sum(close, 2) / 2) < ((sum(close, 8) / 8) - stddev(close, 8))) ? 1 : (((1 < (volume / adv20)) || ((volume / adv20) == 1)) ? 1 : (-1 * 1))))",  # noqa: E501
    "alpha022": "(-1 * (delta(correlation(high, volume, 5), 5) * rank(stddev(close, 20))))",
    "alpha023": "(((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)",
    "alpha024": "((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05) || ((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05)) ? (-1 * (close - ts_min(close, 100))) : (-1 * delta(close, 3)))",  # noqa: E501
    "alpha025": "rank(((((-1 * returns) * adv20) * vwap) * (high - close)))",
    "alpha026": "(-1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))",
    "alpha027": "((0.5 < rank((sum(correlation(rank(volume), rank(vwap), 6), 2) / 2.0))) ? (-1 * 1) : 1)",  # noqa: E501
    "alpha028": "scale(((correlation(adv20, low, 5) + ((high + low) / 2)) - close))",
    "alpha029": "(min(product(rank(rank(scale(log(sum(ts_min(rank(rank((-1 * rank(delta((close - 1), 5))))), 2), 1))))), 1), 5) + ts_rank(delay((-1 * returns), 6), 5))",  # noqa: E501
    "alpha030": "(((1.0 - rank(((sign((close - delay(close, 1))) + sign((delay(close, 1) - delay(close, 2)))) + sign((delay(close, 2) - delay(close, 3)))))) * sum(volume, 5)) / sum(volume, 20))",  # noqa: E501
    "alpha031": "((rank(rank(rank(decay_linear((-1 * rank(rank(delta(close, 10)))), 10)))) + rank((-1 * delta(close, 3)))) + sign(scale(correlation(adv20, low, 12))))",  # noqa: E501
    "alpha032": "(scale(((sum(close, 7) / 7) - close)) + (20 * scale(correlation(vwap, delay(close, 5), 230))))",  # noqa: E501
    "alpha033": "rank((-1 * ((1 - (open / close))^1)))",
    "alpha034": "rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) + (1 - rank(delta(close, 1)))))",  # noqa: E501
    "alpha035": "((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low), 16))) * (1 - Ts_Rank(returns, 32)))",  # noqa: E501
    "alpha036": "(((((2.21 * rank(correlation((close - open), delay(volume, 1), 15))) + (0.7 * rank((open - close)))) + (0.73 * rank(Ts_Rank(delay((-1 * returns), 6), 5)))) + rank(abs(correlation(vwap, adv20, 6)))) + (0.6 * rank((((sum(close, 200) / 200) - open) * (close - open)))))",  # noqa: E501
    "alpha037": "(rank(correlation(delay((open - close), 1), close, 200)) + rank((open - close)))",
    "alpha038": "((-1 * rank(Ts_Rank(close, 10))) * rank((close / open)))",
    "alpha039": "((-1 * rank((delta(close, 7) * (1 - rank(decay_linear((volume / adv20), 9)))))) * (1 + rank(sum(returns, 250))))",  # noqa: E501
    "alpha040": "((-1 * rank(stddev(high, 10))) * correlation(high, volume, 10))",
    "alpha041": "(((high * low)^0.5) - vwap)",
    "alpha042": "(rank((vwap - close)) / rank((vwap + close)))",
    "alpha043": "(ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8))",
    "alpha044": "(-1 * correlation(high, rank(volume), 5))",
    "alpha045": "(-1 * ((rank((sum(delay(close, 5), 20) / 20)) * correlation(close, volume, 2)) * rank(correlation(sum(close, 5), sum(close, 20), 2))))",  # noqa: E501
    "alpha046": "((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))) ? (-1 * 1) : (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < 0) ? 1 : ((-1 * 1) * (close - delay(close, 1)))))",  # noqa: E501
    "alpha047": "((((rank((1 / close)) * volume) / adv20) * ((high * rank((high - close))) / (sum(high, 5) / 5))) - rank((vwap - delay(vwap, 5))))",  # noqa: E501
    "alpha048": "(indneutralize(((correlation(delta(close, 1), delta(delay(close, 1), 1), 250) * delta(close, 1)) / close), IndClass.subindustry) / sum(((delta(close, 1) / delay(close, 1))^2), 250))",  # noqa: E501
    "alpha049": "(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.1)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))",  # noqa: E501
    "alpha050": "(-1 * ts_max(rank(correlation(rank(volume), rank(vwap), 5)), 5))",
    "alpha051": "(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.05)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))",  # noqa: E501
    "alpha052": "((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank(((sum(returns, 240) - sum(returns, 20)) / 220))) * ts_rank(volume, 5))",  # noqa: E501
    "alpha053": "(-1 * delta((((close - low) - (high - close)) / (close - low)), 9))",
    "alpha054": "((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))",
    "alpha055": "(-1 * correlation(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12)))), rank(volume), 6))",  # noqa: E501
    "alpha056": "(0 - (1 * (rank((sum(returns, 10) / sum(sum(returns, 2), 3))) * rank((returns * cap)))))",  # noqa: E501
    "alpha057": "(0 - (1 * ((close - vwap) / decay_linear(rank(ts_argmax(close, 30)), 2))))",
    "alpha058": "(-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.sector), volume, 3.92795), 7.89291), 5.50322))",  # noqa: E501
    "alpha059": "(-1 * Ts_Rank(decay_linear(correlation(IndNeutralize(((vwap * 0.728317) + (vwap * (1 - 0.728317))), IndClass.industry), volume, 4.25197), 16.2289), 8.19648))",  # noqa: E501
    "alpha060": "(0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume)))) - scale(rank(ts_argmax(close, 10))))))",  # noqa: E501
    "alpha061": "(rank((vwap - ts_min(vwap, 16.1219))) < rank(correlation(vwap, adv180, 17.9282)))",
    "alpha062": "((rank(correlation(vwap, sum(adv20, 22.4101), 9.91009)) < rank(((rank(open) + rank(open)) < (rank(((high + low) / 2)) + rank(high))))) * -1)",  # noqa: E501
    "alpha063": "((rank(decay_linear(delta(IndNeutralize(close, IndClass.industry), 2.25164), 8.22237)) - rank(decay_linear(correlation(((vwap * 0.318108) + (open * (1 - 0.318108))), sum(adv180, 37.2467), 13.557), 12.2883))) * -1)",  # noqa: E501
    "alpha064": "((rank(correlation(sum(((open * 0.178404) + (low * (1 - 0.178404))), 12.7054), sum(adv120, 12.7054), 16.6208)) < rank(delta(((((high + low) / 2) * 0.178404) + (vwap * (1 - 0.178404))), 3.69741))) * -1)",  # noqa: E501
    "alpha065": "((rank(correlation(((open * 0.00817205) + (vwap * (1 - 0.00817205))), sum(adv60, 8.6911), 6.40374)) < rank((open - ts_min(open, 13.635)))) * -1)",  # noqa: E501
    "alpha066": "((rank(decay_linear(delta(vwap, 3.51013), 7.23052)) + Ts_Rank(decay_linear(((((low * 0.96633) + (low * (1 - 0.96633))) - vwap) / (open - ((high + low) / 2))), 11.4157), 6.72611)) * -1)",  # noqa: E501
    "alpha067": "((rank((high - ts_min(high, 2.14593)))^rank(correlation(IndNeutralize(vwap, IndClass.sector), IndNeutralize(adv20, IndClass.subindustry), 6.02936))) * -1)",  # noqa: E501
    "alpha068": "((Ts_Rank(correlation(rank(high), rank(adv15), 8.91644), 13.9333) < rank(delta(((close * 0.518371) + (low * (1 - 0.518371))), 1.06157))) * -1)",  # noqa: E501
    "alpha069": "((rank(ts_max(delta(IndNeutralize(vwap, IndClass.industry), 2.72412), 4.79344))^Ts_Rank(correlation(((close * 0.490655) + (vwap * (1 - 0.490655))), adv20, 4.92416), 9.0615)) * -1)",  # noqa: E501
    "alpha070": "((rank(delta(vwap, 1.29456))^Ts_Rank(correlation(IndNeutralize(close, IndClass.industry), adv50, 17.8256), 17.9171)) * -1)",  # noqa: E501
    "alpha071": "max(Ts_Rank(decay_linear(correlation(Ts_Rank(close, 3.43976), Ts_Rank(adv180, 12.0647), 18.0175), 4.20501), 15.6948), Ts_Rank(decay_linear((rank(((low + open) - (vwap + vwap)))^2), 16.4662), 4.4388))",  # noqa: E501
    "alpha072": "(rank(decay_linear(correlation(((high + low) / 2), adv40, 8.93345), 10.1519)) / rank(decay_linear(correlation(Ts_Rank(vwap, 3.72469), Ts_Rank(volume, 18.5188), 6.86671), 2.95011)))",  # noqa: E501
    "alpha073": "(max(rank(decay_linear(delta(vwap, 4.72775), 2.91864)), Ts_Rank(decay_linear(((delta(((open * 0.147155) + (low * (1 - 0.147155))), 2.03608) / ((open * 0.147155) + (low * (1 - 0.147155)))) * -1), 3.33829), 16.7411)) * -1)",  # noqa: E501
    "alpha074": "((rank(correlation(close, sum(adv30, 37.4843), 15.1365)) < rank(correlation(rank(((high * 0.0261661) + (vwap * (1 - 0.0261661)))), rank(volume), 11.4791))) * -1)",  # noqa: E501
    "alpha075": "(rank(correlation(vwap, volume, 4.24304)) < rank(correlation(rank(low), rank(adv50), 12.4413)))",  # noqa: E501
    "alpha076": "(max(rank(decay_linear(delta(vwap, 1.24383), 11.8259)), Ts_Rank(decay_linear(Ts_Rank(correlation(IndNeutralize(low, IndClass.sector), adv81, 8.14941), 19.569), 17.1543), 19.383)) * -1)",  # noqa: E501
    "alpha077": "min(rank(decay_linear(((((high + low) / 2) + high) - (vwap + high)), 20.0451)), rank(decay_linear(correlation(((high + low) / 2), adv40, 3.1614), 5.64125)))",  # noqa: E501
    "alpha078": "(rank(correlation(sum(((low * 0.352233) + (vwap * (1 - 0.352233))), 19.7428), sum(adv40, 19.7428), 6.83313))^rank(correlation(rank(vwap), rank(volume), 5.77492)))",  # noqa: E501
    "alpha079": "(rank(delta(IndNeutralize(((close * 0.60733) + (open * (1 - 0.60733))), IndClass.sector), 1.23438)) < rank(correlation(Ts_Rank(vwap, 3.60973), Ts_Rank(adv150, 9.18637), 14.6644)))",  # noqa: E501
    "alpha080": "((rank(Sign(delta(IndNeutralize(((open * 0.868128) + (high * (1 - 0.868128))), IndClass.industry), 4.04545)))^Ts_Rank(correlation(high, adv10, 5.11456), 5.53756)) * -1)",  # noqa: E501
    "alpha081": "((rank(Log(product(rank((rank(correlation(vwap, sum(adv10, 49.6054), 8.47743))^4)), 14.9655))) < rank(correlation(rank(vwap), rank(volume), 5.07914))) * -1)",  # noqa: E501
    "alpha082": "(min(rank(decay_linear(delta(open, 1.46063), 14.8717)), Ts_Rank(decay_linear(correlation(IndNeutralize(volume, IndClass.sector), ((open * 0.634196) + (open * (1 - 0.634196))), 17.4842), 6.92131), 13.4283)) * -1)",  # noqa: E501
    "alpha083": "((rank(delay(((high - low) / (sum(close, 5) / 5)), 2)) * rank(rank(volume))) / (((high - low) / (sum(close, 5) / 5)) / (vwap - close)))",  # noqa: E501
    "alpha084": "SignedPower(Ts_Rank((vwap - ts_max(vwap, 15.3217)), 20.7127), delta(close, 4.96796))",  # noqa: E501
    "alpha085": "(rank(correlation(((high * 0.876703) + (close * (1 - 0.876703))), adv30, 9.61331))^rank(correlation(Ts_Rank(((high + low) / 2), 3.70596), Ts_Rank(volume, 10.1595), 7.11408)))",  # noqa: E501
    "alpha086": "((Ts_Rank(correlation(close, sum(adv20, 14.7444), 6.00049), 20.4195) < rank(((open + close) - (vwap + open)))) * -1)",  # noqa: E501
    "alpha087": "(max(rank(decay_linear(delta(((close * 0.369701) + (vwap * (1 - 0.369701))), 1.91233), 2.65461)), Ts_Rank(decay_linear(abs(correlation(IndNeutralize(adv81, IndClass.industry), close, 13.4132)), 4.89768), 14.4535)) * -1)",  # noqa: E501
    "alpha088": "min(rank(decay_linear(((rank(open) + rank(low)) - (rank(high) + rank(close))), 8.06882)), Ts_Rank(decay_linear(correlation(Ts_Rank(close, 8.44728), Ts_Rank(adv60, 20.6966), 8.01266), 6.65053), 2.61957))",  # noqa: E501
    "alpha089": "(Ts_Rank(decay_linear(correlation(((low * 0.967285) + (low * (1 - 0.967285))), adv10, 6.94279), 5.51607), 3.79744) - Ts_Rank(decay_linear(delta(IndNeutralize(vwap, IndClass.industry), 3.48158), 10.1466), 15.3012))",  # noqa: E501
    "alpha090": "((rank((close - ts_max(close, 4.66719)))^Ts_Rank(correlation(IndNeutralize(adv40, IndClass.subindustry), low, 5.38375), 3.21856)) * -1)",  # noqa: E501
    "alpha091": "((Ts_Rank(decay_linear(decay_linear(correlation(IndNeutralize(close, IndClass.industry), volume, 9.74928), 16.398), 3.83219), 4.8667) - rank(decay_linear(correlation(vwap, adv30, 4.01303), 2.6809))) * -1)",  # noqa: E501
    "alpha092": "min(Ts_Rank(decay_linear(((((high + low) / 2) + close) < (low + open)), 14.7221), 18.8683), Ts_Rank(decay_linear(correlation(rank(low), rank(adv30), 7.58555), 6.94024), 6.80584))",  # noqa: E501
    "alpha093": "(Ts_Rank(decay_linear(correlation(IndNeutralize(vwap, IndClass.industry), adv81, 17.4193), 19.848), 7.54455) / rank(decay_linear(delta(((close * 0.524434) + (vwap * (1 - 0.524434))), 2.77377), 16.2664)))",  # noqa: E501
    "alpha094": "((rank((vwap - ts_min(vwap, 11.5783)))^Ts_Rank(correlation(Ts_Rank(vwap, 19.6462), Ts_Rank(adv60, 4.02992), 18.0926), 2.70756)) * -1)",  # noqa: E501
    "alpha095": "(rank((open - ts_min(open, 12.4105))) < Ts_Rank((rank(correlation(sum(((high + low) / 2), 19.1351), sum(adv40, 19.1351), 12.8742))^5), 11.7584))",  # noqa: E501
    "alpha096": "(max(Ts_Rank(decay_linear(correlation(rank(vwap), rank(volume), 3.83878), 4.16783), 8.38151), Ts_Rank(decay_linear(Ts_ArgMax(correlation(Ts_Rank(close, 7.45404), Ts_Rank(adv60, 4.13242), 3.65459), 12.6556), 14.0365), 13.4143)) * -1)",  # noqa: E501
    "alpha097": "((rank(decay_linear(delta(IndNeutralize(((low * 0.721001) + (vwap * (1 - 0.721001))), IndClass.industry), 3.3705), 20.4523)) - Ts_Rank(decay_linear(Ts_Rank(correlation(Ts_Rank(low, 7.87871), Ts_Rank(adv60, 17.255), 4.97547), 18.5925), 15.7152), 6.71659)) * -1)",  # noqa: E501
    "alpha098": "(rank(decay_linear(correlation(vwap, sum(adv5, 26.4719), 4.58418), 7.18088)) - rank(decay_linear(Ts_Rank(Ts_ArgMin(correlation(rank(open), rank(adv15), 20.8187), 8.62571), 6.95668), 8.07206)))",  # noqa: E501
    "alpha099": "((rank(correlation(sum(((high + low) / 2), 19.8975), sum(adv60, 19.8975), 8.8136)) < rank(correlation(low, volume, 6.28259))) * -1)",  # noqa: E501
    "alpha100": "(0 - (1 * (((1.5 * scale(indneutralize(indneutralize(rank(((((close - low) - (high - close)) / (high - low)) * volume)), IndClass.subindustry), IndClass.subindustry))) - scale(indneutralize((correlation(close, rank(adv20), 5) - rank(ts_argmin(close, 30))), IndClass.subindustry))) * (volume / adv20))))",  # noqa: E501
    "alpha101": "((close - open) / ((high - low) + .001))",
}

#: The paper's fields and their semantic types. `vwap` and `cap` have NO lawful MT5 analogue and
#: say so; `IndClass` is a grouping, carried by the basket rather than by a field.
PAPER_FIELDS: dict[str, tuple[str, str | None]] = {
    "open": ("price", "open"), "high": ("price", "high"), "low": ("price", "low"),
    "close": ("price", "close"), "returns": ("price", "ret"), "volume": ("volume", "activity"),
    "adv": ("volume", "activity"), "vwap": ("price", None), "cap": ("fundamental", None),
}
PARENT_STATUSES: tuple[str, ...] = ("TESTABLE", "TOO_DEEP", "NONTESTABLE")


# ---------------------------------------------------------------------------- parser
_TOKEN = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)|([A-Za-z_][A-Za-z0-9_.]*)"
                    r"|(\|\||==|[-+*/^<>?:(),]))")


def _tokens(src: str) -> list[str]:
    out: list[str] = []
    pos = 0
    s = src.strip()
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise ValueError(f"cannot tokenise at {s[pos:pos + 12]!r}")
        out.append(next(g for g in m.groups() if g is not None))
        pos = m.end()
    return out


class _Parser:
    """A recursive-descent parser for the paper's infix syntax: numbers, identifiers, calls,
    unary minus, ^ (right-assoc), * /, + -, comparisons, ||, and the ternary."""

    def __init__(self, src: str) -> None:
        self.toks = _tokens(src)
        self.i = 0

    def peek(self) -> str | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, expected: str | None = None) -> str:
        tok = self.peek()
        if tok is None or (expected is not None and tok != expected):
            raise ValueError(f"expected {expected!r}, got {tok!r} at token {self.i}")
        self.i += 1
        return tok

    def parse(self) -> Any:
        node = self.ternary()
        if self.peek() is not None:
            raise ValueError(f"trailing token {self.peek()!r}")
        return node

    def ternary(self) -> Any:
        cond = self.logical()
        if self.peek() == "?":
            self.take("?")
            a = self.ternary()
            self.take(":")
            b = self.ternary()
            return ("tern", cond, a, b)
        return cond

    def logical(self) -> Any:
        node = self.comparison()
        while self.peek() == "||":
            self.take()
            node = ("bin", "||", node, self.comparison())
        return node

    def comparison(self) -> Any:
        node = self.additive()
        while self.peek() in ("<", ">", "=="):
            op = self.take()
            node = ("bin", op, node, self.additive())
        return node

    def additive(self) -> Any:
        node = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            node = ("bin", op, node, self.term())
        return node

    def term(self) -> Any:
        node = self.power()
        while self.peek() in ("*", "/"):
            op = self.take()
            node = ("bin", op, node, self.power())
        return node

    def power(self) -> Any:
        node = self.unary()
        if self.peek() == "^":
            self.take()
            return ("bin", "^", node, self.power())
        return node

    def unary(self) -> Any:
        if self.peek() == "-":
            self.take()
            return ("neg", self.unary())
        return self.primary()

    def primary(self) -> Any:
        tok = self.take()
        if tok == "(":
            node = self.ternary()
            self.take(")")
            return node
        if re.match(r"^(\d+\.\d*|\.\d+|\d+)$", tok):
            return ("num", float(tok))
        if self.peek() == "(":
            self.take("(")
            args: list[Any] = []
            if self.peek() != ")":
                args.append(self.ternary())
                while self.peek() == ",":
                    self.take(",")
                    args.append(self.ternary())
            self.take(")")
            return ("call", tok, tuple(args))
        return ("id", tok)


def parse_formula(src: str) -> Any:
    """The paper's formula as a tuple AST. Raises ValueError on a formula it cannot read."""
    return _Parser(src).parse()


# ---------------------------------------------------------------------------- transpiler
#: THE AFFINE WRAPPER. The paper's formulas are full of constants -- `1 - rank(x)`, `2 * scale(y)`,
#: `(high + low) / 2`, `sum(close, 8) / 8` -- and the grammar has NO numeric constant: a window
#: is the only number a node may carry. So a constant is never dropped where it changes the
#: hypothesis: every transpiled subtree is `a * tree + b`, the algebra below propagates (a, b)
#: through each operator exactly (a shift commutes with a delay, flips under a negation, is
#: invisible to a rank), and a constant that reaches an operator where it MATTERS -- a weight
#: inside a sum, a shift inside a product, a threshold in a comparison -- makes the formula
#: NONTESTABLE with that constant named. At the root, `a` and `b` are dropped: the formula
#: family z-scores the signal on its own history, so a positive scale and a shift are invisible
#: and a negative scale is a negation.
@dataclass(frozen=True)
class _Aff:
    tree: Any                 #: a grammar tree, or None for a pure constant
    a: float = 1.0
    b: float = 0.0

    @property
    def const(self) -> bool:
        return self.tree is None


class _Missing:
    """A subtree that has no lawful analogue. It propagates upward; the reasons are collected
    on the transpiler so a report names EVERY missing field, not the first one met."""


_MISSING = _Missing()
_WINDOWED_CALLS: dict[str, str] = {
    "delay": "delay", "delta": "delta", "ts_min": "min", "ts_max": "max", "ts_rank": "ts_rank",
    "sum": "sum", "stddev": "std", "decay_linear": "decay", "ts_argmax": "bars_since_max",
    "ts_argmin": "bars_since_min",
}
_BINARY_WINDOWED_CALLS: dict[str, str] = {"correlation": "corr", "covariance": "cov"}
_RANK_OPS = frozenset({"xrank", "ts_rank"})
_EPSILON_GUARD = 0.01
_FLIP = {"min": "max", "max": "min", "bars_since_max": "bars_since_min",
         "bars_since_min": "bars_since_max"}


def nearest_window(days: float, minimum: int = 2) -> int:
    """The grammar window nearest a paper window (days on the paper's clock, BARS on the
    desk's): the H axis of the genome is where the clock changes, the tree keeps the number."""
    d = max(float(minimum), float(days))
    return min((w for w in ag.WINDOWS if w >= minimum), key=lambda w: (abs(w - d), w))


def _fmt(v: float) -> str:
    return f"{v:g}"


class _Transpiler:
    def __init__(self) -> None:
        self.missing: set[str] = set()
        self.notes: list[str] = []
        self.fields: set[str] = set()
        self.transforms: set[str] = set()
        self.days: list[float] = []

    def miss(self, why: str) -> _Missing:
        self.missing.add(why)
        return _MISSING

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    # -- the affine algebra
    @staticmethod
    def _sgn(x: _Aff) -> Any:
        """The tree with a negative scale folded in as a negation; the shift is the caller's."""
        return x.tree if x.a > 0 else ["neg", x.tree]

    def unwrap(self, x: _Aff, where: str) -> Any:
        """Drop the affine constants where they cannot matter (a rank, a sign, the root)."""
        if x.const:
            return self.miss(f"degenerate:constant_{where}")
        if x.a != 1.0 or x.b != 0.0:
            self.note(f"affine constant ({_fmt(x.a)} * x + {_fmt(x.b)}) dropped at {where}: "
                      "invisible to it")
        return self._sgn(x)

    def window(self, node: Any, minimum: int = 2) -> int | _Missing:
        v = self.tx(node)
        if isinstance(v, _Aff) and v.const:
            self.days.append(v.b)
            w = nearest_window(v.b, minimum)
            if abs(w - v.b) > 0.5:
                self.note(f"window {_fmt(v.b)} -> {w} (nearest grammar window)")
            return w
        return self.miss("op:variable_window")

    # -- the walk
    def tx(self, node: Any) -> Any:
        kind = node[0]
        if kind == "num":
            return _Aff(None, 0.0, float(node[1]))
        if kind == "id":
            return self.ident(str(node[1]))
        if kind == "neg":
            a = self.tx(node[1])
            return a if a is _MISSING else _Aff(a.tree, -a.a, -a.b)
        if kind == "bin":
            return self.binary(str(node[1]), node[2], node[3])
        if kind == "tern":
            return self.ternary(node[1], node[2], node[3])
        if kind == "call":
            return self.call(str(node[1]).lower(), list(node[2]))
        return self.miss(f"op:{kind}")

    def ident(self, name: str) -> Any:
        low = name.lower()
        m = re.match(r"^adv(\d+)$", low)
        if m:
            self.fields.add("adv")
            self.days.append(float(m.group(1)))
            self.note("adv{d} (average daily dollar volume) -> rolling mean of tick activity")
            return _Aff(["mean", "activity", nearest_window(float(m.group(1)))])
        if low in PAPER_FIELDS:
            self.fields.add(low)
            _sem, term = PAPER_FIELDS[low]
            if term is None:
                return self.miss(f"field:{low}")
            if low == "volume":
                self.note("volume -> tick activity (Fusion publishes tick counts, not contracts)")
            return _Aff(term)
        if low.startswith("indclass."):
            return self.miss("field:industry_classification")
        return self.miss(f"field:{low}")

    def binary(self, op: str, left: Any, right: Any) -> Any:
        # sum(x, d) / d is the MEAN, not a scalar to drop: read it off the AST before walking.
        if (op == "/" and left[0] == "call" and str(left[1]).lower() == "sum"
                and len(left[2]) == 2 and left[2][1][0] == "num" and right[0] == "num"
                and float(left[2][1][1]) == float(right[1])):
            self.transforms.add("mean")
            x = self.tx(left[2][0])
            w = self.window(left[2][1])
            if x is _MISSING or isinstance(w, _Missing):
                return _MISSING
            if x.const:
                return self.miss("degenerate:mean_of_constant")
            self.note("sum(x, d) / d -> mean(x, d)")
            return _Aff(["mean", x.tree, w], x.a, x.b)
        a, b = self.tx(left), self.tx(right)
        if a is _MISSING or b is _MISSING:
            return _MISSING
        if op in ("+", "-"):
            return self.add(a, b if op == "+" else _Aff(b.tree, -b.a, -b.b))
        if op == "*":
            return self.mul(a, b)
        if op == "/":
            return self.div(a, b)
        if op == "^":
            return self.power(a, b)
        if op in ("<", ">"):
            lo, hi = (a, b) if op == "<" else (b, a)                    # lo < hi
            return self.less(lo, hi)
        if op == "==":
            return self.miss("op:equality")
        if op == "||":
            return self.miss("op:logical_or")
        return self.miss(f"op:{op}")

    def add(self, a: _Aff, b: _Aff) -> Any:
        if a.const and b.const:
            return _Aff(None, 0.0, a.b + b.b)
        if a.const or b.const:
            c, x = (a, b) if a.const else (b, a)
            # 1 - rank(x) IS rank(-x): the one shift the grammar can say exactly.
            if c.b == 1.0 and x.a == -1.0 and x.b == 0.0 and isinstance(x.tree, list) \
                    and x.tree[0] in _RANK_OPS:
                self.note(f"1 - {x.tree[0]}(x) -> {x.tree[0]}(-x): the mirrored percentile")
                return _Aff([x.tree[0], ["neg", x.tree[1]], *x.tree[2:]])
            return _Aff(x.tree, x.a, x.b + c.b)
        if a.a == b.a:
            return _Aff(["add", a.tree, b.tree], a.a, a.b + b.b)
        if a.a == -b.a:
            return _Aff(["sub", a.tree, b.tree], a.a, a.b + b.b)
        return self.miss(f"constant_weight:{_fmt(abs(a.a))}:{_fmt(abs(b.a))} (a weighted sum "
                         "has no grammar analogue)")

    def mul(self, a: _Aff, b: _Aff) -> Any:
        if a.const and b.const:
            return _Aff(None, 0.0, a.b * b.b)
        if a.const or b.const:
            c, x = (a, b) if a.const else (b, a)
            if c.b == 0:
                return self.miss("degenerate:zero_factor")
            return _Aff(x.tree, x.a * c.b, x.b * c.b)
        if a.b == 0 and b.b == 0:
            return _Aff(["mul", a.tree, b.tree], a.a * b.a, 0.0)
        return self.miss(f"constant_shift_in_product:{_fmt(a.b if a.b else b.b)}")

    def div(self, a: _Aff, b: _Aff) -> Any:
        if b.const:
            if b.b == 0:
                return self.miss("degenerate:division_by_zero")
            return _Aff(a.tree, a.a / b.b, a.b / b.b)
        if a.const:
            return self.miss("op:reciprocal")
        if b.b != 0 and abs(b.b) <= _EPSILON_GUARD and b.a > 0:
            # `(high - low) + .001`: a guard against a zero denominator, not a hypothesis. The
            # grammar's `div` already refuses a zero divisor, so the guard is dropped as such.
            self.note(f"epsilon guard {_fmt(b.b)} in a denominator dropped (div guards zero)")
            b = _Aff(b.tree, b.a, 0.0)
        if a.b != 0 or b.b != 0:
            return self.miss(f"constant_shift_in_quotient:{_fmt(a.b if a.b else b.b)}")
        return _Aff(self._div_tree(a.tree, b.tree), a.a / b.a, 0.0)

    def _div_tree(self, a: Any, b: Any) -> Any:
        """Division, with the price-ratio spellings the grammar carries as terminals."""
        if isinstance(a, list) and a[0] == "sub" and a[1:] == ["close", "open"] \
                and b in ("open", "close"):
            self.note("(close - open) / open -> body (the grammar's own bar-body ratio, over "
                      "close)")
            return "body"
        if isinstance(a, list) and a[0] == "sub" and a[1:] == ["high", "low"] \
                and b in ("open", "close"):
            self.note("(high - low) / close -> range (the grammar's own bar-range ratio)")
            return "range"
        if (isinstance(a, list) and isinstance(b, list) and a[0] == "delta" and b[0] == "delay"
                and a[1] == b[1] == "close" and a[2] == b[2]):
            self.note(f"delta(close, w) / delay(close, w) -> sum(ret, w): the relative change "
                      f"over {a[2]} bars in logs")
            return ["sum", "ret", a[2]]
        return ["div", a, b]

    def power(self, a: _Aff, b: _Aff) -> Any:
        if not b.const:
            return self.miss("op:pow(expr,expr)")
        if a.const:
            return _Aff(None, 0.0, a.b ** b.b)
        if b.b == 1.0:
            return a
        if b.b == 2.0:
            if a.b != 0:
                return self.miss("constant_shift_in_power")
            self.transforms.add("square")
            return _Aff(["mul", a.tree, a.tree], a.a * a.a, 0.0)
        if b.b == 0.5:
            return self.miss("op:sqrt")
        return self.miss("op:pow")

    def less(self, lo: _Aff, hi: _Aff) -> Any:
        """lo < hi -> sign(hi - lo): +1 where true, -1 where false, 0 at equality."""
        diff = self.add(hi, _Aff(lo.tree, -lo.a, -lo.b))
        if diff is _MISSING:
            return _MISSING
        if diff.const:
            return self.miss("degenerate:constant_comparison")
        if diff.b != 0:
            return self.miss(f"constant_threshold:{_fmt(-diff.b / diff.a)}")
        self.transforms.add("comparison")
        self.note("a < b -> sign(b - a): +1 where true, -1 where false")
        return _Aff(["sign", self._sgn(diff)])

    def ternary(self, c: Any, a: Any, b: Any) -> Any:
        gate, ta, tb = self.tx(c), self.tx(a), self.tx(b)
        if gate is _MISSING or ta is _MISSING or tb is _MISSING:
            return _MISSING
        if gate.const:
            return self.miss("degenerate:constant_gate")
        if gate.b != 0:
            return self.miss(f"constant_threshold:{_fmt(-gate.b / gate.a)}")
        g = self._sgn(gate)
        if ta.const and tb.const:
            return self.miss("op:conditional(constant branches)")
        self.transforms.add("conditional")
        if tb.const:
            self.note(f"else-branch constant {_fmt(tb.b)} replaced by HOLD (trade_when keeps "
                      "the previous value where its gate fails)")
            return _Aff(["trade_when", g, ta.tree], ta.a, ta.b)
        if ta.const:
            self.note(f"then-branch constant {_fmt(ta.b)} replaced by HOLD (trade_when on the "
                      "negated gate)")
            return _Aff(["trade_when", ["neg", g], tb.tree], tb.a, tb.b)
        if ta.b == 0 and tb.b == 0 and ta.a == -tb.a \
                and canonical(ta.tree) == canonical(tb.tree):
            self.note("cond ? x : -x -> sign(cond) * x (exact for a +/-1 gate)")
            return _Aff(["mul", g, ta.tree], ta.a, 0.0)
        return self.miss("op:conditional(two live branches)")

    def windowed(self, op: str, x: _Aff, w: int, name: str) -> Any:
        """A windowed operator on `a * t + b`, the constants carried through exactly."""
        if x.const:
            return self.miss(f"degenerate:{name}_of_constant")
        if op in ("delay", "decay", "mean"):
            return _Aff([op, x.tree, w], x.a, x.b)
        if op == "delta":
            return _Aff([op, x.tree, w], x.a, 0.0)
        if op == "sum":
            return _Aff([op, x.tree, w], x.a, x.b * w)
        if op in ("min", "max"):
            return _Aff([_FLIP[op] if x.a < 0 else op, x.tree, w], x.a, x.b)
        if op == "std":
            return _Aff([op, x.tree, w], abs(x.a), 0.0)
        if op == "ts_rank":
            return _Aff([op, self._sgn(x), w])
        if op in ("bars_since_max", "bars_since_min"):
            self.note("ts_argmax/argmin -> bars since the window extreme (same information, "
                      "counted from the bar rather than from the window start)")
            return _Aff([_FLIP[op] if x.a < 0 else op, x.tree, w])
        return self.miss(f"op:{name}")

    def call(self, name: str, args: list[Any]) -> Any:
        if name == "rank" and len(args) == 1:
            self.transforms.add("rank")
            x = self.tx(args[0])
            if x is _MISSING:
                return _MISSING
            if x.const:
                return self.miss("degenerate:rank_of_constant")
            self.note("rank(x) -> xrank(x): the percentile across the cell's BASKET (currency "
                      "basket / asset class), where the paper ranks across an equity universe")
            return _Aff(["xrank", self._sgn(x)])
        if name == "indneutralize" and len(args) == 2:
            self.transforms.add("indneutralize")
            x = self.tx(args[0])
            if x is _MISSING:
                return _MISSING
            if x.const:
                return self.miss("degenerate:neutralise_constant")
            self.note("IndNeutralize(x, class) -> xzscore(x): demeaned and scaled across the "
                      "cell's asset-class basket, the desk's analogue of an industry group")
            return _Aff(["xzscore", self._sgn(x)])
        if name in _WINDOWED_CALLS and len(args) == 2:
            op = _WINDOWED_CALLS[name]
            self.transforms.add(name)
            inner = args[0]
            if op == "delta" and inner[0] == "call" and str(inner[1]).lower() == "log" \
                    and len(inner[2]) == 1:
                y = self.tx(inner[2][0])
                w = self.window(args[1])
                if y is _MISSING or isinstance(w, _Missing):
                    return _MISSING
                if y.const or y.b != 0:
                    return self.miss("op:log")
                self.note("delta(log(x), w) -> delta(x, w) / delay(x, w): the relative change")
                return _Aff(["div", ["delta", y.tree, w], ["delay", y.tree, w]])
            x = self.tx(inner)
            w = self.window(args[1])
            if x is _MISSING or isinstance(w, _Missing):
                return _MISSING
            return self.windowed(op, x, w, name)
        if name in _BINARY_WINDOWED_CALLS and len(args) == 3:
            self.transforms.add(name)
            x, y = self.tx(args[0]), self.tx(args[1])
            w = self.window(args[2], minimum=3)
            if x is _MISSING or y is _MISSING or isinstance(w, _Missing):
                return _MISSING
            if x.const or y.const:
                return self.miss(f"degenerate:{name}_with_constant")
            tree = [_BINARY_WINDOWED_CALLS[name], x.tree, y.tree, w]
            if name == "correlation":
                return _Aff(tree, float(np.sign(x.a * y.a)))
            return _Aff(tree, x.a * y.a, 0.0)
        if name == "scale" and args:
            self.transforms.add("scale")
            x = self.tx(args[0])
            if x is _MISSING:
                return _MISSING
            if x.const:
                return self.miss("degenerate:scale_constant")
            if x.b != 0:
                return self.miss("constant_shift_in_scale")
            self.note("scale(x) (cross-sectional |x| normalisation) -> scale(x, 24): the "
                      "grammar's rolling |x| normalisation over one H1 day")
            return _Aff(["scale", self._sgn(x), 24])
        if name in ("abs", "sign") and len(args) == 1:
            x = self.tx(args[0])
            if x is _MISSING:
                return _MISSING
            if x.const:
                return _Aff(None, 0.0, abs(x.b) if name == "abs" else float(np.sign(x.b)))
            if x.b != 0:
                return self.miss(f"constant_shift_in_{name}")
            self.transforms.add(name)
            if name == "abs":
                return _Aff(["abs", x.tree], abs(x.a), 0.0)
            return _Aff(["sign", self._sgn(x)])
        if name in ("min", "max") and len(args) == 2:
            b = self.tx(args[1])
            if isinstance(b, _Aff) and b.const:              # the paper's min(x, d) is ts_min
                return self.call("ts_" + name, args)
            a = self.tx(args[0])
            if a is _MISSING or b is _MISSING:
                return _MISSING
            if a.const:
                return self.miss(f"degenerate:{name}_with_constant")
            if a.a == b.a and a.b == b.b:
                op = name if a.a > 0 else _FLIP[name]
                return _Aff([op + "2", a.tree, b.tree], a.a, a.b)
            return self.miss(f"constant_weight:{_fmt(abs(a.a))}:{_fmt(abs(b.a))} (an "
                             f"unequal-weight {name} has no grammar analogue)")
        if name == "signedpower" and len(args) == 2:
            self.transforms.add("signedpower")
            e = self.tx(args[1])
            x = self.tx(args[0])
            if x is _MISSING or e is _MISSING:
                return _MISSING
            if not e.const:
                return self.miss("op:signedpower(variable exponent)")
            if e.b == 2.0 and not x.const and x.b == 0:
                self.note("SignedPower(x, 2) -> x * |x|")
                return _Aff(["mul", x.tree, ["abs", x.tree]], x.a * abs(x.a), 0.0)
            return self.miss("op:signedpower")
        if name == "log":
            self.transforms.add("log")
            if args:
                self.tx(args[0])
            return self.miss("op:log")
        if name == "product":
            self.transforms.add("product")
            for a in args:
                self.tx(a)
            return self.miss("op:product")
        for a in args:
            self.tx(a)
        return self.miss(f"op:{name}")


#: Exact hand derivations for the two formulas whose nested conditional has an algebraic form
#: the transpiler does not see: (0 < ts_min(d, w)) ? d : ((ts_max(d, w) < 0) ? d : -d) is d when
#: every delta in the window shares one sign and -d otherwise, i.e. sign(min) * sign(max) * d.
def _consistent_momentum(w: int) -> Expr:
    d: Expr = ["delta", "close", 2]
    return ["mul", ["mul", ["sign", ["min", d, w]], ["sign", ["max", d, w]]], d]


OVERRIDES: dict[str, tuple[Expr, str]] = {
    "alpha009": (_consistent_momentum(5),
                 "nested conditional -> sign(ts_min) * sign(ts_max) * delta: exact, the delta "
                 "keeps its sign only while the window's deltas agree"),
    "alpha010": (["xrank", _consistent_momentum(3)],
                 "rank of alpha009's form (window 4 -> 3, the nearest grammar window)"),
}


@dataclass(frozen=True)
class ParentGenome:
    """A_i = (D, O, T, H, S, N, E), plus what this desk can do with it."""

    alpha_id: str
    formula: str
    D: tuple[str, ...]                 #: the paper's fields, by name
    D_semantic: tuple[str, ...]        #: their semantic types
    tree: Expr | None                  #: O, the operator tree in the grammar, when it has one
    T: tuple[str, ...]                 #: transformations the formula applies
    H: float                           #: the horizon: the longest window, in the paper's days
    S: str                             #: state conditioning (the paper: none)
    N: str                             #: normalisation / cross-section
    E: str                             #: execution assumptions
    status: str                        #: TESTABLE | TOO_DEEP | NONTESTABLE
    missing: tuple[str, ...] = ()      #: what has no lawful MT5 analogue, by name
    translations: tuple[str, ...] = ()
    depth: int = 0

    def render(self) -> str:
        if self.tree is None:
            return f"NONTESTABLE({', '.join(self.missing)})"
        return ag.to_str(self.tree)

    def as_dict(self) -> dict[str, Any]:
        return {"alpha_id": self.alpha_id, "formula": self.formula, "D": list(self.D),
                "D_semantic": list(self.D_semantic), "O": self.tree, "T": list(self.T),
                "H_days": self.H, "S": self.S, "N": self.N, "E": self.E,
                "status": self.status, "missing": list(self.missing),
                "translations": list(self.translations), "depth": self.depth,
                "rendered": self.render()}


_PAPER_E = ("paper: daily close-to-close rebalance, cross-sectional long/short, dollar-neutral; "
            "desk: H1 bars, the formula family's hold_bars horizon, z-scored on own history")


def transpile(alpha_id: str, formula: str) -> ParentGenome:
    """One paper formula -> one parent genome, with the desk's verdict on it."""
    t = _Transpiler()
    tree: Any = None
    try:
        got = t.tx(parse_formula(formula))
        tree = _MISSING if got is _MISSING else t.unwrap(got, "root")
    except ValueError as exc:
        t.miss(f"parse:{exc}")
        tree = _MISSING
    fields = tuple(sorted(t.fields))
    sem = tuple(sorted({PAPER_FIELDS[f][0] for f in fields if f in PAPER_FIELDS}))
    horizon = max(t.days) if t.days else 1.0
    n = ("cross_sectional_rank" if "rank" in t.transforms or "indneutralize" in t.transforms
         else "none")
    state = "none (paper: unconditional)"
    transforms = tuple(sorted(t.transforms))
    if alpha_id in OVERRIDES:
        tree, why = OVERRIDES[alpha_id]
        t.note(why)
        t.missing.clear()
    if tree is _MISSING or t.missing:
        return ParentGenome(alpha_id, formula, fields, sem, None, transforms, horizon, state, n,
                            _PAPER_E, "NONTESTABLE", tuple(sorted(t.missing)), tuple(t.notes))
    tree = canonical(tree)
    if not ag.well_formed(tree):
        return ParentGenome(alpha_id, formula, fields, sem, tree, transforms, horizon, state, n,
                            _PAPER_E, "NONTESTABLE", (f"unit_algebra:{ag.type_of(tree)}",),
                            tuple(t.notes), ag.depth(tree))
    d = ag.depth(tree)
    status = "TOO_DEEP" if d > ag.MAX_DEPTH else "TESTABLE"
    missing = (f"depth:{d}>{ag.MAX_DEPTH}",) if status == "TOO_DEEP" else ()
    return ParentGenome(alpha_id, formula, fields, sem, tree, transforms, horizon, state, n,
                        _PAPER_E, status, missing, tuple(t.notes), d)


@lru_cache(maxsize=1)
def parent_genomes() -> dict[str, ParentGenome]:
    """Every one of the 101, transcribed. Cached: the paper does not change between calls."""
    return {aid: transpile(aid, f) for aid, f in ALPHA101.items()}


def genome_census() -> dict[str, Any]:
    """What the desk can say of the 101, by status and by the missing field that stops it."""
    gs = parent_genomes()
    by_status: dict[str, int] = dict.fromkeys(PARENT_STATUSES, 0)
    by_missing: dict[str, list[str]] = {}
    for g in gs.values():
        by_status[g.status] += 1
        if g.status == "NONTESTABLE":
            for m in g.missing:
                by_missing.setdefault(m, []).append(g.alpha_id)
    return {"n_parents": len(gs), "by_status": by_status,
            "nontestable_by_missing": {k: sorted(v) for k, v in sorted(by_missing.items())},
            "testable": sorted(a for a, g in gs.items() if g.status == "TESTABLE"),
            "too_deep": sorted(a for a, g in gs.items() if g.status == "TOO_DEEP"),
            "rule": ("a formula whose fields have no lawful MT5 analogue is NONTESTABLE with the "
                     "field named; TOO_DEEP is a real genome the executor reaches only through "
                     f"pruning (MAX_DEPTH {ag.MAX_DEPTH})")}


# ============================================================================ panel seeding
def memo_key(expr: Expr) -> str:
    """The key `alpha_grammar.evaluate` looks a subtree up under. Seeding uses the same one."""
    return json.dumps(expr, default=str)


def panel_nodes(expr: Expr) -> list[Expr]:
    """Every PANEL subtree, innermost first, each once."""
    out: list[Expr] = []
    seen: set[str] = set()

    def _walk(x: Expr) -> None:
        if not isinstance(x, (list, tuple)):
            return
        for c in x[1:]:
            _walk(c)
        if str(x[0]) in ag.PANEL and ag.key(x) not in seen:
            seen.add(ag.key(x))
            out.append(x)
    _walk(expr)
    return out


def has_panel(expr: Expr) -> bool:
    return bool(panel_nodes(expr))


def _xs_rank(vals: np.ndarray, min_members: int) -> np.ndarray:
    """Per-row percentile of each column among the row's finite columns; NaN where thin."""
    finite = np.isfinite(vals)
    n = finite.sum(axis=1)
    filled = np.where(finite, vals, np.inf)
    order = np.argsort(np.argsort(filled, axis=1, kind="stable"), axis=1).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        pct = (order + 1.0) / n[:, None]
    pct[~finite] = np.nan
    pct[n < min_members, :] = np.nan
    return np.asarray(pct)


def _xs_z(vals: np.ndarray, min_members: int) -> np.ndarray:
    finite = np.isfinite(vals)
    n = finite.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        # an all-NaN row (a bar no member has a value on) is NaN below, not a warning
        warnings.simplefilter("ignore", category=RuntimeWarning)
        mean = np.nanmean(np.where(finite, vals, np.nan), axis=1)
        std = np.nanstd(np.where(finite, vals, np.nan), axis=1)
        z = (vals - mean[:, None]) / std[:, None]
    z[~finite] = np.nan
    z[(n < min_members) | ~np.isfinite(std), :] = np.nan
    return np.asarray(z)


def seed_panels(expr: Expr, frames: Mapping[str, Mapping[str, pd.Series]],
                memos: MutableMapping[str, Any], min_members: int = 3) -> int:
    """Compute every panel node of `expr` across the basket and seed each member's memo.

    `frames` is symbol -> that symbol's terminal frames; `memos` is symbol -> the memo
    `alpha_grammar.evaluate` will be handed for it (a dict or a cache scope). After this call
    `ag.evaluate(expr, frames[s], memos[s])` is the cell's series for any member `s`. Returns the
    number of panel nodes seeded. A basket thinner than `min_members` at a bar is NaN there.
    """
    n_seeded = 0
    for node in panel_nodes(expr):
        child = node[1]
        cols: dict[str, pd.Series] = {}
        for sym, fr in frames.items():
            memo = memos.setdefault(sym, {})
            cols[sym] = ag.evaluate(child, dict(fr), memo)
        if not cols:
            continue
        mat = pd.DataFrame(cols)
        vals = mat.to_numpy(dtype=float)
        out = _xs_rank(vals, min_members) if node[0] == "xrank" else _xs_z(vals, min_members)
        k = memo_key(node)
        for j, sym in enumerate(mat.columns):
            idx = next(iter(frames[sym].values())).index
            memos[sym][k] = pd.Series(out[:, j], index=mat.index).reindex(idx)
        n_seeded += 1
    return n_seeded


def evaluate_cell(expr: Expr, frames: Mapping[str, Mapping[str, pd.Series]], target: str,
                  memos: MutableMapping[str, Any] | None = None) -> pd.Series:
    """The expression on `target`, with its panel nodes computed across every symbol in
    `frames`. Never raises: what cannot be computed is NaN, as in the grammar."""
    memos = {} if memos is None else memos
    if target not in frames:
        return pd.Series(dtype=float)
    if has_panel(expr):
        seed_panels(expr, frames, memos)
    return ag.evaluate(expr, dict(frames[target]), memos.setdefault(target, {}))


# ============================================================================ typed DAG
#: THE FACTORY'S SEVEN-WORD TYPE VOCABULARY (mandate: every node typed price / return / volume /
#: count / ratio / time / bool). The grammar's dtype x unit algebra is the AUTHORITY -- `kind`
#: is its reading in the words the mandate uses, so a report and a catalogue can say what a
#: node IS without a second algebra. `time` is what a window argument is (bars); `bool` is what
#: the logic macros below return (a -1/0/+1 gate, the only truth value the grammar can carry).
DSL_TYPES: tuple[str, ...] = ("price", "return", "volume", "count", "ratio", "time", "bool")
_VOLUME_DTYPES = frozenset({"ACTIVITY", "FLOW", "POSITIONING"})


class CompileError(ValueError):
    """The expression cannot be compiled: a structural, type or unit defect, named by path."""

    def __init__(self, why: str, path: tuple[int, ...] = ()) -> None:
        super().__init__(f"{why} at {'/'.join(map(str, path)) or 'root'}")
        self.why = why
        self.path = path


class UnitMismatch(CompileError):
    """Two quantities the unit algebra refuses to combine: a compile error, never a NaN."""


@dataclass(frozen=True)
class TypedNode:
    """One node of the typed DAG: hashed by structure, typed by the grammar, read as a kind."""

    node_id: str
    op: str
    kind: str
    dtype: str
    unit: str
    dimension: str
    children: tuple[str, ...]
    window: int | None
    depth: int

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.node_id, "op": self.op, "kind": self.kind, "dtype": self.dtype,
                "unit": self.unit, "dimension": self.dimension, "children": list(self.children),
                "window": self.window, "depth": self.depth}


def kind_of(expr: Expr) -> str:
    """The node's kind in the seven-word vocabulary; `bool` for a logic macro head, INVALID
    where the grammar's algebra refuses the composition."""
    if isinstance(expr, (list, tuple)) and expr and str(expr[0]) in _LOGIC_MACROS:
        return "bool" if ag.is_valid(lower(expr)) else ag.INVALID
    e = lower(expr)
    t = ag.type_of(e)
    if t == ag.INVALID:
        return ag.INVALID
    dim = ag.dimension_of(e)
    unit = ag.unit_of(e)
    if dim is None or unit is None:
        return ag.INVALID
    if t == "COUNT" or unit == ag.BARS:
        return "time" if unit == ag.BARS else "count"
    if t in _VOLUME_DTYPES:
        return "volume"
    if t == "RETURN":
        return "return"
    if dim.price != 0:
        return "price"
    if dim.count != 0:
        return "volume"
    if dim.time != 0:
        return "time"
    return "ratio"


def typed_dag(expr: Expr) -> dict[str, TypedNode]:
    """The expression as a DAG of typed nodes keyed by `ag.subtree_hash`: a subtree that
    appears twice is ONE node (the cache's own key), and every node carries its kind, dtype,
    unit and dimension. Raises `CompileError` / `UnitMismatch` on the innermost bad node."""
    out: dict[str, TypedNode] = {}

    def _walk(x: Expr, path: tuple[int, ...], d: int) -> str:
        if isinstance(x, str):
            if x not in ag.TERMINALS:
                raise CompileError(f"unknown terminal {x!r}", path)
            nid = ag.subtree_hash(x)
            if nid not in out:
                out[nid] = TypedNode(nid, x, kind_of(x), ag.DTYPES[x], str(ag.TERMINAL_UNITS[x]),
                                     str(ag.TERMINAL_DIMENSIONS[x]), (), None, d)
            return nid
        if not isinstance(x, (list, tuple)) or not x:
            raise CompileError("empty node", path)
        op = str(x[0])
        if op in _MACROS or op in _ALIASES:
            return _walk(lower(x), path, d)
        if op not in ag.ALL_OPERATORS:
            raise CompileError(f"unknown operator {op!r}", path)
        kids: list[str] = []
        window: int | None = None
        for i, c in enumerate(x[1:], start=1):
            if isinstance(c, (list, tuple, str)):
                kids.append(_walk(c, (*path, i), d + 1))
            elif isinstance(c, int) and not isinstance(c, bool):
                if c not in ag.WINDOWS:
                    raise CompileError(f"window {c} is not one of {ag.WINDOWS}", (*path, i))
                window = int(c)
                wid = f"w{c}"
                if wid not in out:
                    out[wid] = TypedNode(wid, "window", "time", "COUNT", str(ag.BARS),
                                         str(ag.DIMENSIONLESS), (), int(c), d + 1)
                kids.append(wid)
            else:
                raise CompileError(f"bad argument {c!r}", (*path, i))
        lowered = lower(x)
        if not ag._structurally_valid(lowered):
            raise CompileError(f"malformed {op} node", path)
        t = ag.type_of(lowered)
        u = ag.unit_of(lowered)
        dim = ag.dimension_of(lowered)
        if t == ag.INVALID or u is None or dim is None:
            raise UnitMismatch(
                f"{op}({', '.join(_brief(c) for c in x[1:])}): "
                f"{'type' if t == ag.INVALID else 'unit'} mismatch", path)
        nid = ag.subtree_hash(lowered)
        if nid not in out:
            out[nid] = TypedNode(nid, op, kind_of(x), t, str(u), str(dim), tuple(kids),
                                 window, d)
        return nid

    _walk(expr, (), 0)
    return out


def _brief(x: Expr) -> str:
    if isinstance(x, str):
        return f"{x}:{ag.TERMINAL_KINDS.get(x, ag.INVALID)}"
    if isinstance(x, (list, tuple)) and x:
        return f"{x[0]}(..):{ag.kind_of(lower(x))}"
    return str(x)


@dataclass
class Compiled:
    """A compiled expression: lowered to the grammar, typed, hashed, with its family."""

    expr: Expr
    source: Expr
    dag: dict[str, TypedNode]
    root: str
    kind: str
    dtype: str
    unit: str
    canonical: str
    family: str
    hits: int = 0
    misses: int = 0

    @property
    def n_nodes(self) -> int:
        return len(self.dag)

    def evaluate(self, frames: Mapping[str, pd.Series], memo: Any = None) -> pd.Series:
        """Vectorised evaluation through the grammar, every subtree memoised by its hash in
        `memo` (a dict or an `ag.SubtreeCache` scope): the second call is a lookup."""
        m: Any = {} if memo is None else memo
        k = memo_key(self.expr)
        if k in m:
            self.hits += 1
            return m[k]
        self.misses += 1
        return ag.evaluate(self.expr, dict(frames), m)

    def as_dict(self) -> dict[str, Any]:
        return {"expr": self.expr, "rendered": ag.to_str(self.expr), "kind": self.kind,
                "dtype": self.dtype, "unit": self.unit, "root": self.root,
                "n_nodes": self.n_nodes, "family": self.family, "canonical": self.canonical}


def compile_expr(expr: Expr, terminals: Sequence[str] | None = None) -> Compiled:
    """THE COMPILER. Lowers the macros, builds the typed DAG (raising `UnitMismatch` on the
    first node the unit algebra refuses), runs the production screen, and returns the
    compiled form with its canonical key and trial family. A `terminals` pool narrows the
    legal leaves to the series a world actually has."""
    lowered = lower(expr)
    dag = typed_dag(lowered)
    if ag.depth(lowered) > ag.MAX_DEPTH:
        raise CompileError(f"depth {ag.depth(lowered)} > MAX_DEPTH {ag.MAX_DEPTH}")
    if not ag.is_valid(lowered, terminals=terminals):
        bad = sorted(set(ag.terminals_in(lowered)) - set(terminals or ag.TERMINALS))
        raise CompileError(f"terminal(s) {bad} not available on this world" if bad
                           else "production screen refused the tree")
    root = ag.subtree_hash(lowered)
    node = dag[root]
    return Compiled(lowered, expr, dag, root, node.kind, node.dtype, node.unit,
                    canonical_key(lowered), family_key(lowered))


# ============================================================================ operator catalogue
@dataclass(frozen=True)
class OpSpec:
    """One operator's entry: category, arity, whether it takes a window, and its type/unit
    signature. `lowers_to` names the grammar expansion of a macro; "" for a primitive."""

    name: str
    category: str
    arity: int
    windowed: bool
    signature: str
    lowers_to: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "category": self.category, "arity": self.arity,
                "windowed": self.windowed, "signature": self.signature,
                "lowers_to": self.lowers_to}


OP_CATEGORIES: tuple[str, ...] = ("time_series", "cross_sectional", "group", "math", "logic",
                                  "event", "regime")

#: MACROS: the DSL's logic, event and regime-conditioned operators, each an expansion into the
#: grammar's own nodes, so the unit algebra, the evaluator and the cache see one vocabulary.
#: Without numeric constants in the grammar a truth value is a sign: gt(a, b) is sign(a - b),
#: which the algebra refuses unless a and b share a unit -- the compile error the mandate asks
#: for -- and `trade_when` reads a gate as "on" where it is > 0.
_LOGIC_MACROS: dict[str, Callable[[list[Any]], Expr]] = {
    "gt": lambda a: ["sign", ["sub", a[0], a[1]]],
    "lt": lambda a: ["sign", ["sub", a[1], a[0]]],
    "and": lambda a: ["min2", ["sign", a[0]], ["sign", a[1]]],
    "or": lambda a: ["max2", ["sign", a[0]], ["sign", a[1]]],
    "not": lambda a: ["neg", ["sign", a[0]]],
}
_EVENT_MACROS: dict[str, Callable[[list[Any]], Expr]] = {
    "event_decay": lambda a: ["decay", "event", a[0]],
    "bars_since_event": lambda a: ["bars_since_max", "event", a[0]],
    "event_gate": lambda a: ["trade_when", "event", a[0]],
}
_REGIME_MACROS: dict[str, Callable[[list[Any]], Expr]] = {
    "when_regime": lambda a: ["trade_when", "state_prob", a[0]],
    "regime_neutral": lambda a: ["group_zscore", a[0], "state_prob", a[1]],
    "regime_rank": lambda a: ["group_rank", a[0], "state_prob", a[1]],
}
_ALIASES: dict[str, str] = {"ts_argmax": "bars_since_max", "ts_argmin": "bars_since_min",
                            "ts_mean": "mean", "ts_std": "std", "ts_delta": "delta",
                            "ts_delay": "delay", "ts_corr": "corr", "ts_cov": "cov",
                            "ts_decay": "decay", "ts_sum": "sum", "ts_min": "min",
                            "ts_max": "max", "rank": "xrank", "neutralise": "group_zscore"}
_MACROS: dict[str, Callable[[list[Any]], Expr]] = {**_LOGIC_MACROS, **_EVENT_MACROS,
                                                   **_REGIME_MACROS}


def lower(expr: Expr) -> Expr:
    """Expand every macro and alias, innermost first, into the grammar's closed operator set.
    A tree with no macro comes back structurally equal (a fresh copy)."""
    if not isinstance(expr, (list, tuple)) or not expr:
        return expr
    op = str(expr[0])
    kids = [lower(c) if isinstance(c, (list, tuple)) else c for c in expr[1:]]
    if op in _MACROS:
        return lower(_MACROS[op](kids))
    return [_ALIASES.get(op, op), *kids]


def _sig_windowed(op: str) -> str:
    rule = ag._WINDOWED_OUT[op]
    out = {"same": "T[u]", "diff": "dT[u]", "SCALE": "SCALE[u]", "RANK": "RANK[1]",
           "Z": "Z[1]", "COUNT": "COUNT[bars]"}.get(rule, rule)
    if op == "atr_norm":
        return "(x: PRICE[quote], w: time[bars]) -> Z[1]"
    return f"(x: T[u], w: time[bars]) -> {out}"


def _catalogue() -> dict[str, OpSpec]:
    cat: dict[str, OpSpec] = {}
    ts_ops = ("delay", "delta", "mean", "std", "min", "max", "ts_rank", "zscore", "decay",
              "sum", "bars_since_max", "bars_since_min", "atr_norm", "ts_backfill", "scale")
    for op in ts_ops:
        cat[op] = OpSpec(op, "time_series", 1, True, _sig_windowed(op))
    cat["corr"] = OpSpec("corr", "time_series", 2, True, "(x: T[u], y: S[v], w) -> Z[1]")
    cat["cov"] = OpSpec("cov", "time_series", 2, True, "(x: T[u], y: S[v], w) -> SCALE[u v]")
    cat["residual"] = OpSpec("residual", "time_series", 2, True,
                             "(x: T[u], y: S[v], w) -> T[u]  (x minus its rolling beta to y)")
    for op in ag.PANEL:
        cat[op] = OpSpec(op, "cross_sectional", 1, False,
                         f"(x: T[u]) -> {'RANK' if op == 'xrank' else 'Z'}[1] across the "
                         "cell's basket")
    cat["group_rank"] = OpSpec("group_rank", "group", 2, True,
                               "(x: T[u], g: group, w) -> RANK[1] within g's peers")
    cat["group_zscore"] = OpSpec("group_zscore", "group", 2, True,
                                 "(x: T[u], g: group, w) -> Z[1] neutralised within g")
    for op in ("neg", "abs"):
        cat[op] = OpSpec(op, "math", 1, False, "(x: T[u]) -> T[u]")
    cat["sign"] = OpSpec("sign", "math", 1, False, "(x: T[u]) -> Z[1]")
    for op in ("add", "sub", "max2", "min2"):
        cat[op] = OpSpec(op, "math", 2, False, "(x: T[u], y: T[u]) -> T[u]  (units must match)")
    cat["mul"] = OpSpec("mul", "math", 2, False, "(x: T[u], y: S[v]) -> [u v]")
    cat["div"] = OpSpec("div", "math", 2, False, "(x: T[u], y: S[v]) -> [u / v]; T/T -> RATIO")
    cat["trade_when"] = OpSpec("trade_when", "logic", 2, False,
                               "(gate: bool|Z[1], x: T[u]) -> T[u] held where gate <= 0")
    for op in ("gt", "lt", "and", "or"):
        cat[op] = OpSpec(op, "logic", 2, False, "(a: T[u], b: T[u]) -> bool",
                         ag.to_str(_LOGIC_MACROS[op](["a", "b"])))
    cat["not"] = OpSpec("not", "logic", 1, False, "(a: T[u]) -> bool",
                        ag.to_str(_LOGIC_MACROS["not"](["a"])))
    cat["event_decay"] = OpSpec("event_decay", "event", 0, True, "(w) -> EVENT[1]",
                                ag.to_str(_EVENT_MACROS["event_decay"]([24])))
    cat["bars_since_event"] = OpSpec("bars_since_event", "event", 0, True,
                                     "(w) -> COUNT[bars]",
                                     ag.to_str(_EVENT_MACROS["bars_since_event"]([24])))
    cat["event_gate"] = OpSpec("event_gate", "event", 1, False, "(x: T[u]) -> T[u]",
                               ag.to_str(_EVENT_MACROS["event_gate"](["x"])))
    cat["when_regime"] = OpSpec("when_regime", "regime", 1, False, "(x: T[u]) -> T[u]",
                                ag.to_str(_REGIME_MACROS["when_regime"](["x"])))
    cat["regime_neutral"] = OpSpec("regime_neutral", "regime", 1, True,
                                   "(x: T[u], w) -> Z[1] within the regime",
                                   ag.to_str(_REGIME_MACROS["regime_neutral"](["x", 24])))
    cat["regime_rank"] = OpSpec("regime_rank", "regime", 1, True,
                                "(x: T[u], w) -> RANK[1] within the regime",
                                ag.to_str(_REGIME_MACROS["regime_rank"](["x", 24])))
    return cat


OPERATOR_CATALOGUE: dict[str, OpSpec] = _catalogue()


def catalogue_census() -> dict[str, Any]:
    by_cat: dict[str, list[str]] = {c: [] for c in OP_CATEGORIES}
    for spec in OPERATOR_CATALOGUE.values():
        by_cat[spec.category].append(spec.name)
    return {"n_operators": len(OPERATOR_CATALOGUE), "by_category": by_cat,
            "primitives": sorted(k for k, v in OPERATOR_CATALOGUE.items() if not v.lowers_to),
            "macros": sorted(k for k, v in OPERATOR_CATALOGUE.items() if v.lowers_to),
            "aliases": dict(_ALIASES), "types": list(DSL_TYPES)}


def operators_in(expr: Expr) -> set[str]:
    if not isinstance(expr, (list, tuple)) or not expr:
        return set()
    out = {str(expr[0])}
    for c in expr[1:]:
        out |= operators_in(c)
    return out


# ============================================================================ mutation engine
#: THE MOVES, each DIMENSION-PRESERVING BY CONSTRUCTION: a child is returned only when the
#: production screen accepts it AND its root unit equals the parent's (units imply dimensions).
#: The grammar's only numeric constants are its windows, so `constant` perturbation is a window
#: step; `simplify` is the exact canonical form (a no-op, returned as None, on a canonical tree).
MUTATIONS: tuple[str, ...] = ("point", "subtree", "crossover", "constant", "operator_swap",
                              "simplify")


def dimension_preserving(parent: Expr, child: Expr) -> bool:
    if not ag.is_valid(child):
        return False
    pu, cu = ag.unit_of(parent), ag.unit_of(child)
    return pu is not None and cu is not None and pu == cu


def _internal_paths(expr: Expr) -> list[tuple[int, ...]]:
    return [p for p in ag._paths(expr) if isinstance(ag._get(expr, p), list)]


def _leaf_paths(expr: Expr) -> list[tuple[int, ...]]:
    return [p for p in ag._paths(expr) if isinstance(ag._get(expr, p), str)]


def mutate(expr: Expr, move: str, rng: np.random.Generator,
           terminals: Sequence[str] | None = None, partner: Expr | None = None,
           tries: int = 16) -> Expr | None:
    """One named move on a copy of `expr`; None when no dimension-preserving child was found
    in `tries` draws (the caller counts that as a move that produced nothing)."""
    pool = tuple(terminals) if terminals else ag.terminal_pool(True)
    base = lower(expr)
    if move == "simplify":
        c = canonical(base)
        return None if ag.key(c) == ag.key(base) else c
    for _ in range(tries):
        cand: Expr | None = None
        if move == "point":
            leaves = _leaf_paths(base)
            p = leaves[int(rng.integers(len(leaves)))]
            old = ag._get(base, p)
            same = [t for t in pool if t != old
                    and ag.TERMINAL_KINDS.get(t) == ag.TERMINAL_KINDS.get(old)]
            if not same:
                continue
            cand = ag._set(ag._clone(base), p, str(rng.choice(same)))
        elif move == "subtree":
            paths = _internal_paths(base) or [()]
            p = paths[int(rng.integers(len(paths)))]
            cand = ag._set(ag._clone(base), p, ag.random_expr(rng, 2, terminals=pool))
        elif move == "crossover":
            if partner is None:
                return None
            other = lower(partner)
            pa, pb = ag._paths(base), ag._paths(other)
            cand = ag._set(ag._clone(base), pa[int(rng.integers(len(pa)))],
                           ag._clone(ag._get(other, pb[int(rng.integers(len(pb)))])))
        elif move == "constant":
            paths = [p for p in _internal_paths(base)
                     if str(ag._get(base, p)[0]) in ag.WINDOWED + ag.BINARY_WINDOWED]
            if not paths:
                return None
            p = paths[int(rng.integers(len(paths)))]
            node = list(ag._get(base, p))
            w = int(node[-1])
            i = ag.WINDOWS.index(w) if w in ag.WINDOWS else -1
            j = i + (1 if rng.random() < 0.5 else -1)
            node[-1] = int(ag.WINDOWS[j]) if 0 <= j < len(ag.WINDOWS) \
                else int(rng.choice(ag.WINDOWS))
            if node[-1] == w:
                continue
            cand = ag._set(ag._clone(base), p, node)
        elif move == "operator_swap":
            paths = _internal_paths(base)
            if not paths:
                return None
            p = paths[int(rng.integers(len(paths)))]
            node = list(ag._get(base, p))
            cls = next((c for c in (ag.UNARY, ag.WINDOWED, ag.BINARY, ag.BINARY_WINDOWED,
                                    ag.PANEL) if node[0] in c), None)
            if cls is None or len(cls) < 2:
                continue
            new_op = str(rng.choice([o for o in cls if o != node[0]]))
            node[0] = new_op
            cand = ag._set(ag._clone(base), p, node)
        else:
            raise ValueError(f"unknown move {move!r}; one of {MUTATIONS}")
        if cand is not None and ag.key(cand) != ag.key(base) \
                and dimension_preserving(base, cand):
            return cand
    return None


__all__ = [
    "ALPHA101",
    "AVAILABILITY_RULES",
    "DSL_TYPES",
    "MUTATIONS",
    "OPERATOR_CATALOGUE",
    "OP_CATEGORIES",
    "OVERRIDES",
    "PAPER_FIELDS",
    "PARENT_STATUSES",
    "SEMANTIC_TERMINAL",
    "SEMANTIC_TYPES",
    "CompileError",
    "Compiled",
    "Field",
    "FieldCatalogue",
    "OpSpec",
    "ParentGenome",
    "TypedNode",
    "UnitMismatch",
    "axis_fields",
    "bar_fields",
    "canonical",
    "canonical_key",
    "catalogue_census",
    "compile_expr",
    "dimension_preserving",
    "evaluate_cell",
    "family_key",
    "future_data_impossible",
    "genome_census",
    "has_panel",
    "kind_of",
    "lower",
    "memo_key",
    "mutate",
    "nearest_window",
    "operators_in",
    "panel_nodes",
    "parent_genomes",
    "parse_formula",
    "representation_fields",
    "seed_panels",
    "skeleton",
    "transpile",
    "typed_dag",
    "windows_in",
]
