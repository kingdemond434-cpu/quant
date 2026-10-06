"""Rotate producers over the WHOLE legal universe, least-covered ground first, instead of a prefix.

THE DEFECT THIS CURES (measured 2026-09-30 while inventorying every cell producer). Several
producers bound their per-pass work with a slice -- `[:PROPOSAL_SYMBOLS]` over a class list,
`[:12]` over a sorted book, a fixed twelve-name PREFERRED tuple. A bound on the WORK per pass is
legitimate: an hourly organ that cannot finish inside its hour lands no artifact. A bound that
always takes the SAME prefix is not a budget, it is a permanent exclusion: `qd_frontier` proposed
every niche on the first three instruments of each asset class for its whole life, so the other
forty-odd forex symbols of the hypothesis lane were reachable by its explorer arm on no pass.

THE CURE IS A RING, NOT A WIDER SLICE. The per-pass count is unchanged -- the judge's load from
each producer stays what it was -- and the window slides one width per hour, so a lap of
`ceil(n / k)` hours visits every legal instrument. The ring is ordered LEAST-COVERED FIRST (fewest
cells the sealed gauntlet has already judged on that instrument, or on that (instrument, family)
pair), so the first hours of a lap go to the orthogonal ground and the saturated instruments come
last. That ordering influences only what a producer MINTS; the judge's own queue order is Tier S's
and is not touched here.

NOTHING HERE IS A GATE. An unreadable coverage file yields an empty count, and the ring then falls
back to name order -- a measurement outage changes which instruments come first, never how many.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
UNIVERSE = BASE / "data" / "universe"
#: Every cell the sealed gauntlet has judged, keyed `SYMBOL.family.p=<hash>`. The judge writes it;
#: this module only reads it, so the coverage it reports is the JUDGE's, not a producer's claim.
SEEN_CELLS = BASE / "data" / "hypotheses" / "gauntlet_seen_cells.json"


def hour_turn(now: datetime | None = None) -> int:
    """Whole hours since the epoch: the cursor every hourly ring advances by. Stateless on
    purpose -- a cursor file is one more box state path to reconcile, and an hour index cannot be
    lost, reverted by a merge or left behind by a killed pass."""
    at = now or datetime.now(UTC)
    return int(at.timestamp() // 3600)


def rotating_window(items: Sequence[Any], k: int, *, turn: int) -> list[Any]:
    """`k` consecutive items of the ring `items`, starting one width further on per `turn`.

    Over `ceil(len(items) / k)` consecutive turns every item is returned at least once. A ring no
    wider than `k` is returned whole, which is exactly what the old prefix returned for it.
    """
    n = len(items)
    k = max(0, int(k))
    if n <= k:
        return list(items)
    if k == 0:
        return []
    start = (int(turn) * k) % n
    out = list(items[start:start + k])
    if len(out) < k:
        out += list(items[:k - len(out)])
    return out


@lru_cache(maxsize=4)
def _judged_at(path: str, mtime_ns: int) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return {}, {}
    by_sym: Counter[str] = Counter()
    by_pair: Counter[tuple[str, str]] = Counter()
    keys: Iterable[Any] = doc.keys() if isinstance(doc, dict) else (doc or [])
    for key in keys:
        parts = str(key).split(".")
        if len(parts) < 2:
            continue
        sym, fam = parts[0].upper(), parts[1]
        by_sym[sym] += 1
        by_pair[(sym, fam)] += 1
    return dict(by_sym), dict(by_pair)


def judged_counts(path: Path | None = None) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    """`({SYMBOL: n}, {(SYMBOL, family): n})` of cells the sealed gauntlet has judged.

    Empty when the file is absent or unreadable -- the caller then orders by name, which is what
    it did before this existed (L1.28a: an absent count is not a zero anyone acts on)."""
    p = path or SEEN_CELLS
    try:
        mtime = p.stat().st_mtime_ns
    except OSError:
        return {}, {}
    return _judged_at(str(p), mtime)


def saturation_tier(symbol: str, family: str, sat: Any = None) -> float:
    """-novelty credit of `family` on `symbol` against the certified book (one decimal, so the
    tier is coarse and the judged count still orders inside it); 0.0 when the map is UNMEASURED.

    THE ANTI-SATURATION LAW (2026-10-05): a producer's per-pass window should land first on the
    instruments where ANOTHER copy of this family would be a new bet, and last on the ones where
    the certified book already holds the same mechanism on the same factor."""
    if sat is None:
        return 0.0
    try:
        return -round(float(sat.score_fields(str(symbol).upper(), family, {}, None, None,
                                             None)["novelty_credit"]), 1)
    except Exception:
        return 0.0


def _saturation_scorer() -> Any:
    try:
        from research.certificate_saturation import scorer
        return scorer()
    except Exception:
        try:
            from certificate_saturation import scorer as _scorer  # type: ignore[import-not-found]
            return _scorer()
        except Exception:
            return None


def orthogonal_ring(symbols: Iterable[str], family: str | None = None, *,
                    counts: tuple[dict[str, int], dict[tuple[str, str], int]] | None = None,
                    saturation: Any = "auto") -> list[str]:
    """`symbols`, least-SATURATED first when a family is named (the certified book's effective
    local density, `saturation_tier`), then least-judged, then by name.

    Deduplicated, order-stable for equal keys, and never shorter than its input. `saturation`
    is a `certificate_saturation.Scorer`, None to disable, or "auto" to read the published map."""
    by_sym, by_pair = counts if counts is not None else judged_counts()
    uniq = sorted({str(s) for s in symbols if str(s)})
    if family:
        sat = _saturation_scorer() if saturation == "auto" else saturation
        return sorted(uniq, key=lambda s: (saturation_tier(s, family, sat),
                                           by_pair.get((s.upper(), family), 0), s))
    return sorted(uniq, key=lambda s: (by_sym.get(s.upper(), 0), s))


def hypothesis_symbols(universe: Path | None = None) -> list[str]:
    """Every hypothesis-lane symbol with an H1 parquet on disk, by name.

    The two-lane law is applied here at the source (`universe_policy.may_hypothesise`, by
    MetaTrader's own asset class); an unimportable policy yields [] rather than every symbol, so a
    missing import can never turn a single-name equity into a hypothesis target."""
    root = universe or UNIVERSE
    have = sorted({p.name[:-len("_H1.parquet")] for p in root.glob("*_H1.parquet")})
    try:
        import sys
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        from research.universe_policy import may_hypothesise
    except Exception:
        return []
    out: list[str] = []
    for s in have:
        try:
            if may_hypothesise(s):
                out.append(s)
        except Exception:
            continue
    return out
