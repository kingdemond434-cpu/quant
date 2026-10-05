"""THE METRIC FENCE -- an impossible number never becomes a cell or a claim.

WHY (committee dry run on PR #160, 2026-09-30). The Extreme-Return Forensic committee's
`record_integrity` seat flagged an MQL5 record carrying a 2,296% win rate. It was not one record.
Measured on the committed `data/intelligence/mql5_survivors/` (308 files, 3,154 rows): 2,985 rows
carried `win_pct` above 100, because `mql5_survivor_hunter.field` read the COUNT on the page line
`Profit Trades: 2 281 (76.90%)` -- the thousands separator is a space, the number regex tolerates
spaces, and the percent sits in parentheses after it. A win count written into a win-rate field
passed straight into the compiler, where a track record may become a cell.

WHAT THIS IS. One bounds check, shared by every door a scraped metric passes through on its way
to a cell or a claim:

    win rate        in [0, 100] %
    profit factor   >= 0
    drawdown        |dd| in [0, 100] %       (desks write drawdown with either sign)
    trades          >= 0
    Sharpe          inside [-SHARPE_ABS_MAX, SHARPE_ABS_MAX]

A non-finite value (NaN, inf) is out of bounds too. A metric that is ABSENT is not checked --
absence is UNMEASURED, never a defect and never a pass. A string with a percent sign or a comma
thousands separator is read the way a person would read it; a string that is not a number at all
is left to the row's own consumer (the fence judges numbers, it does not invent them).

WHERE IT RUNS. `miner_candidate_compiler.compile_row` (every seat's row, before any cell exists)
and `mechanism_claims.extract` (every verbatim claim the crawlers pull from prose). A row or
claim that fails is REFUSED with a counted reason: the compiler publishes
`impossible_metrics` in `miner_candidates.json` and the claim extractor returns
`dropped_impossible_metric` beside its other fences. Nothing is dropped silently.

WHAT IT IS NOT. It is not a quality screen: a 99% win rate, a 0.2 profit factor or a 95%
drawdown are all POSSIBLE and pass. It refuses only what cannot be true of any record.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

#: A Sharpe ratio outside this band is not a trading record, it is a unit error (a daily figure
#: annualised twice, a t-stat in the Sharpe field, a return in percent). The best audited
#: multi-year books sit below 5; 10 leaves a full factor of two for HFT-style claims.
SHARPE_ABS_MAX = 10.0

WIN_KEYS: tuple[str, ...] = ("win_pct", "win_rate_pct", "win_rate", "winrate", "hit_rate_pct",
                             "profitable_trades_pct", "win_ratio_pct")
PF_KEYS: tuple[str, ...] = ("pf", "profit_factor")
DD_KEYS: tuple[str, ...] = ("max_dd_pct", "drawdown_pct", "max_drawdown_pct", "dd_pct",
                            "maxdd_pct")
TRADE_KEYS: tuple[str, ...] = ("trades", "n_trades", "num_trades", "total_trades",
                               "trade_count")
SHARPE_KEYS: tuple[str, ...] = ("sharpe", "sharpe_ratio", "reported_sharpe")
#: Blocks a scraper nests its numbers in. Only one level deep: a record is a record.
NESTED_KEYS: tuple[str, ...] = ("claimed_performance", "performance", "metrics", "stats",
                                "record", "track_record")


def _num(v: Any) -> float | None:
    """A number as a reader would take it, or None when the value is not a number at all."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace("%", "").replace(",", "").replace("\u00a0", "").replace(" ", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _first(block: Mapping[str, Any], keys: Iterable[str]) -> tuple[str, float] | None:
    for k in keys:
        if k in block:
            x = _num(block.get(k))
            if x is not None:
                return k, x
    return None


def check_metrics(block: Mapping[str, Any]) -> list[str]:
    """Reasons this block of metrics is impossible; [] when every PRESENT metric is in bounds."""
    bad: list[str] = []

    def fin(name: str, key: str, x: float) -> bool:
        if not math.isfinite(x):
            bad.append(f"{name}_non_finite:{key}")
            return False
        return True

    hit = _first(block, WIN_KEYS)
    if hit and fin("win_rate", *hit) and not 0.0 <= hit[1] <= 100.0:
        bad.append(f"win_rate_out_of_bounds:{hit[0]}={hit[1]:g}")
    hit = _first(block, PF_KEYS)
    if hit and fin("profit_factor", *hit) and hit[1] < 0.0:
        bad.append(f"profit_factor_negative:{hit[0]}={hit[1]:g}")
    hit = _first(block, DD_KEYS)
    if hit and fin("drawdown", *hit) and not 0.0 <= abs(hit[1]) <= 100.0:
        bad.append(f"drawdown_out_of_bounds:{hit[0]}={hit[1]:g}")
    hit = _first(block, TRADE_KEYS)
    if hit and fin("trades", *hit) and hit[1] < 0.0:
        bad.append(f"trades_negative:{hit[0]}={hit[1]:g}")
    hit = _first(block, SHARPE_KEYS)
    if hit and fin("sharpe", *hit) and not -SHARPE_ABS_MAX <= hit[1] <= SHARPE_ABS_MAX:
        bad.append(f"sharpe_out_of_band:{hit[0]}={hit[1]:g}")
    return bad


def fence_row(row: Mapping[str, Any]) -> list[str]:
    """Reasons a scraped row must be refused: its own metrics, then each nested metric block."""
    if not isinstance(row, Mapping):
        return []
    bad = check_metrics(row)
    for k in NESTED_KEYS:
        sub = row.get(k)
        if isinstance(sub, Mapping):
            bad.extend(f"{k}.{r}" for r in check_metrics(sub))
    return bad


def reason_class(reason: str) -> str:
    """`win_rate_out_of_bounds:win_pct=2296` -> `win_rate_out_of_bounds` (the counted class)."""
    return reason.split(":", 1)[0].rsplit(".", 1)[-1]


@dataclass
class FenceTally:
    """What the fence refused, by reason class and by source, with a few examples to audit."""

    checked: int = 0
    refused: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    examples: list[dict[str, Any]] = field(default_factory=list)
    max_examples: int = 12

    def add(self, source: str, reasons: list[str], ref: str = "") -> bool:
        """Record one checked row; True when it was refused."""
        self.checked += 1
        if not reasons:
            return False
        self.refused += 1
        for cls in sorted({reason_class(r) for r in reasons}):
            self.by_reason[cls] = self.by_reason.get(cls, 0) + 1
        self.by_source[source] = self.by_source.get(source, 0) + 1
        if len(self.examples) < self.max_examples:
            self.examples.append({"source": source, "ref": ref[:200], "reasons": reasons[:4]})
        return True

    def to_dict(self) -> dict[str, Any]:
        return {"checked": self.checked, "refused": self.refused,
                "by_reason": dict(sorted(self.by_reason.items(), key=lambda kv: -kv[1])),
                "by_source": dict(sorted(self.by_source.items(), key=lambda kv: -kv[1])),
                "examples": self.examples,
                "bounds": {"win_rate_pct": [0, 100], "profit_factor_min": 0,
                           "drawdown_pct_abs": [0, 100], "trades_min": 0,
                           "sharpe": [-SHARPE_ABS_MAX, SHARPE_ABS_MAX]},
                "rule": ("an impossible metric is refused with its reason before it becomes a "
                         "cell or a claim; an absent metric is UNMEASURED and never checked")}
