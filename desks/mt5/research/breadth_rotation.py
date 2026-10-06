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


def orthogonal_ring(symbols: Iterable[str], family: str | None = None, *,
                    counts: tuple[dict[str, int], dict[tuple[str, str], int]] | None = None
                    ) -> list[str]:
    """`symbols`, least-judged first (per (symbol, family) when a family is named), then by name.

    Deduplicated, order-stable for equal counts, and never shorter than its input."""
    by_sym, by_pair = counts if counts is not None else judged_counts()
    uniq = sorted({str(s) for s in symbols if str(s)})
    if family:
        return sorted(uniq, key=lambda s: (by_pair.get((s.upper(), family), 0), s))
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


# ============================================================================ TIMEFRAME x SESSION
# THE PRINCIPAL'S ORDER (2026-10-06): "we dont want only h1 100 percent being discovered ... but
# rather all timeframes, m1 m15 m30 h1 h4 d1 ... its fr sessions too ... basically all breadths
# targetted". Measured on the last tracked docket snapshot (2026-09-24): 69% of 57,538 docket rows
# were H1 and 20,882 of 20,900 judged cells (99.9%) were H1 -- the judge's own seen-cells file
# names a non-H1 chart as `SYM@TF`, so that split needs no join.
#
# THIS SECTION MEASURES THE SPLIT AND PUBLISHES A KEY; IT FILTERS NOTHING. `tf_session_census`
# reads the docket (streamed, systematically sampled under a parse budget so a 1.6M-row docket
# never lands in memory), the judge's seen cells, and the judge's own per-bucket count
# (`reports/GAUNTLET_ORDER.json`), and sets a TARGET: an equal share for every (chart, session)
# bucket the desk holds bars for. `tf_session_key` turns the published census into a sort key any
# producer or docket orderer can PREPEND to its own: under-target buckets first, the rest after,
# every row kept. A missing census is UNMEASURED and the key is then neutral (0 for every row), so
# an outage changes nothing about anybody's order (L1.28a).

#: Every chart the desk can hold bars for, most intraday first.
CHART_LADDER: tuple[str, ...] = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
#: The session axis `family_call.SESSIONS` executes. D1 carries `all` only: a daily bar has no
#: session inside it.
SESSION_AXIS: tuple[str, ...] = ("all", "asia", "london", "ny")
#: Families pinned to one chart whatever their params say (the sealed judge's `_PINNED_TIMEFRAME`).
PINNED_CHART = {"lvc_asia_london": "M5"}
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
GAUNTLET_ORDER = BASE / "reports" / "GAUNTLET_ORDER.json"
#: Where the census is PUBLISHED: a block of the hourly producer-breadth report, so one artifact
#: carries per-producer breadth and the desk-level chart x session split.
CENSUS_REPORT = BASE / "reports" / "PRODUCER_BREADTH.json"
CENSUS_KEY = "timeframe_session"
#: Rows parsed per census at most. The docket is one JSON row per line (merge_hypotheses'
#: streaming writer), so reading every line is cheap and parsing is the cost; a systematic sample
#: of every k-th line keeps the parse bounded and the share estimate unbiased over the file.
MAX_PARSED_ROWS = 250_000
UNMEASURED = "UNMEASURED"


def chart_of(row: dict[str, Any]) -> str:
    """The chart the JUDGE will load for a row: the family pin, else params, else the row, else
    H1 (the desk-wide spelling of H1 is its absence -- `frontier_identity.REFERENCE_TIMEFRAME`)."""
    fam = str(row.get("family") or "")
    if fam in PINNED_CHART:
        return PINNED_CHART[fam]
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    tf = params.get("timeframe") or row.get("timeframe") or row.get("chart") or "H1"
    return str(tf).upper()


def session_of(row: dict[str, Any]) -> str:
    """The session window a row is filtered to; `all` when it names none."""
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    raw = (params.get("session") or params.get("selector") or row.get("session")
           or row.get("selector") or "all")
    s = str(raw).strip().lower()
    return s or "all"


def bucket_of(row: dict[str, Any]) -> tuple[str, str]:
    chart = chart_of(row)
    sess = "all" if chart == "D1" else session_of(row)
    return chart, sess


def _bucket_name(b: tuple[str, str]) -> str:
    return f"{b[0]}/{b[1]}"


def charts_on_disk(universe: Path | None = None) -> dict[str, int]:
    """{chart: instruments with that chart's bars on disk}. The reachable half of the target."""
    root = universe or UNIVERSE
    out: dict[str, int] = {}
    for tf in CHART_LADDER:
        try:
            out[tf] = sum(1 for _ in root.glob(f"*_{tf}.parquet"))
        except OSError:
            out[tf] = 0
    return out


def iter_docket(path: Path, *, max_parsed: int = MAX_PARSED_ROWS
                ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(sampled rows, how they were read). Bounded memory whatever the docket's size.

    Pass 1 counts lines (no parse). Pass 2 parses every k-th row-line with k = ceil(lines /
    max_parsed). A docket written in the legacy indented shape has no row-per-line structure; it
    is parsed whole only when it is small enough to be harmless, and is UNMEASURED otherwise.
    """
    meta: dict[str, Any] = {"path": str(path), "format": UNMEASURED}
    try:
        size = path.stat().st_size
    except OSError:
        meta["why"] = f"{UNMEASURED}: no docket at {path.name}"
        return [], meta
    meta["bytes"] = size
    try:
        with path.open("rb") as fh:
            first, second = fh.readline(), fh.readline()
    except OSError as exc:
        meta["why"] = f"{UNMEASURED}: unreadable ({type(exc).__name__})"
        return [], meta
    one_per_line = (first.strip() == b"[" and second.lstrip().startswith(b"{")
                    and second.rstrip().rstrip(b",").endswith(b"}"))
    if not one_per_line:
        if size > 256 * 1024 * 1024:
            meta["why"] = (f"{UNMEASURED}: {size >> 20} MB docket is not one row per line; "
                           "refusing to parse it whole")
            return [], meta
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            meta["why"] = f"{UNMEASURED}: unparseable ({type(exc).__name__})"
            return [], meta
        rows = [r for r in doc if isinstance(r, dict)] if isinstance(doc, list) else []
        meta.update({"format": "whole_json", "rows": len(rows), "parsed": len(rows), "stride": 1})
        return rows, meta
    n = 0
    with path.open("rb") as fh:
        for raw in fh:
            if raw.lstrip().startswith(b"{"):
                n += 1
    stride = max(1, -(-n // max(1, int(max_parsed))))
    out: list[dict[str, Any]] = []
    bad = 0
    i = 0
    with path.open("rb") as fh:
        for raw in fh:
            s = raw.strip()
            if not s.startswith(b"{"):
                continue
            if i % stride == 0:
                try:
                    row = json.loads(s.rstrip(b","))
                except ValueError:
                    bad += 1
                else:
                    if isinstance(row, dict):
                        out.append(row)
            i += 1
    meta.update({"format": "row_per_line", "rows": n, "parsed": len(out), "stride": stride,
                 "unparseable": bad})
    return out, meta


def _seen_split(path: Path) -> tuple[dict[str, int], set[str], str]:
    """({chart: judged cells}, the judged ids, why) from the judge's own seen-cells file."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {}, set(), f"{UNMEASURED}: seen cells unreadable ({type(exc).__name__})"
    keys = [str(k) for k in (doc.keys() if isinstance(doc, dict) else (doc or []))]
    by_chart: Counter[str] = Counter()
    for k in keys:
        sym = k.split(".", 1)[0]
        by_chart[sym.split("@", 1)[1].upper() if "@" in sym else "H1"] += 1
    return dict(by_chart), set(keys), f"{path.name}: {len(keys)} judged cell(s)"


def _shares(counts: dict[str, int]) -> dict[str, float]:
    tot = sum(counts.values())
    return {k: round(v / tot, 4) for k, v in sorted(counts.items())} if tot else {}


def tf_session_census(*, docket: Path | None = None, seen: Path | None = None,
                      order: Path | None = None, universe: Path | None = None,
                      max_parsed: int = MAX_PARSED_ROWS) -> dict[str, Any]:
    """The desk's discovery and judged share by chart and by (chart, session), against a target.

    TARGET: every bucket the desk holds bars for gets an equal share -- `1 / reachable charts` per
    chart and `1 / reachable buckets` per (chart, session). It is a FLOOR to reach, never a
    ceiling: H1 above its share is not cut, the buckets under theirs are put first.
    """
    import time as _time
    t0 = _time.monotonic()
    on_disk = charts_on_disk(universe)
    reach_charts = [tf for tf in CHART_LADDER if on_disk.get(tf)]
    reach_buckets = [(tf, s) for tf in reach_charts
                     for s in (("all",) if tf == "D1" else SESSION_AXIS)]
    rows, dmeta = iter_docket(docket or DOCKET, max_parsed=max_parsed)
    by_chart_seen, judged_ids, seen_why = _seen_split(seen or SEEN_CELLS)
    stride = int(dmeta.get("stride") or 1)
    disc_chart: Counter[str] = Counter()
    disc_bucket: Counter[str] = Counter()
    judged_bucket: Counter[str] = Counter()
    try:
        from research.frontier_identity import docket_cell_id
    except Exception:
        try:
            from frontier_identity import docket_cell_id  # type: ignore[no-redef]
        except Exception:
            docket_cell_id = None  # type: ignore[assignment]
    for r in rows:
        b = bucket_of(r)
        disc_chart[b[0]] += stride
        disc_bucket[_bucket_name(b)] += stride
        if judged_ids and docket_cell_id is not None:
            try:
                if docket_cell_id(r) in judged_ids:
                    judged_bucket[_bucket_name(b)] += stride
            except Exception:
                continue
    judge_order: dict[str, int] = {}
    order_why = f"{UNMEASURED}: {(order or GAUNTLET_ORDER).name} absent"
    try:
        od = json.loads((order or GAUNTLET_ORDER).read_text("utf-8"))
        judge_order = {str(k): int(v) for k, v in (od.get("buckets_judged") or {}).items()}
        order_why = f"{(order or GAUNTLET_ORDER).name} at {od.get('at')}"
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    chart_target = round(1 / len(reach_charts), 4) if reach_charts else None
    bucket_target = round(1 / len(reach_buckets), 4) if reach_buckets else None
    disc_share_c = _shares(dict(disc_chart))
    judged_share_c = _shares(by_chart_seen)
    disc_share_b = _shares(dict(disc_bucket))
    judged_share_b = _shares(dict(judged_bucket))
    measured_disc = bool(rows)
    measured_judged = bool(judged_ids)

    def _row(share: dict[str, float], key: str, target: float | None, measured: bool) -> Any:
        if not measured or target is None:
            return UNMEASURED
        got = share.get(key, 0.0)
        return {"share": got, "target": target, "gap": round(target - got, 4),
                "ratio": round(got / target, 3) if target else None}

    charts = {tf: {"bars_instruments": on_disk.get(tf, 0),
                   "reachable": tf in reach_charts,
                   "discovery": _row(disc_share_c, tf, chart_target, measured_disc),
                   "judged": _row(judged_share_c, tf, chart_target, measured_judged),
                   "judged_cells": by_chart_seen.get(tf, 0) if measured_judged else UNMEASURED,
                   "docket_rows_est": disc_chart.get(tf, 0) if measured_disc else UNMEASURED}
              for tf in CHART_LADDER}
    buckets = {}
    for b in reach_buckets:
        name = _bucket_name(b)
        buckets[name] = {
            "discovery": _row(disc_share_b, name, bucket_target, measured_disc),
            "judged": _row(judged_share_b, name, bucket_target, measured_disc and measured_judged),
            "judge_order_judged": judge_order.get(name, 0) if judge_order else UNMEASURED}
    # PRIORITY: the order a producer or orderer should reach buckets in. Judged share leads (it is
    # what turns into certificates), discovery share breaks ties; a bucket with no measurement
    # sorts by name behind every measured under-target one.
    def _ratio(cell: Any) -> float:
        return float(cell["ratio"]) if isinstance(cell, dict) and cell.get("ratio") is not None \
            else float("inf")
    priority = sorted(buckets, key=lambda n: (_ratio(buckets[n]["judged"]),
                                              _ratio(buckets[n]["discovery"]), n))
    under = [n for n in priority
             if (_ratio(buckets[n]["judged"]) < 1.0) or (_ratio(buckets[n]["discovery"]) < 1.0)]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("TARGET = an equal share for every chart and every (chart, session) bucket the "
                 "desk holds bars for. A floor to reach, never a ceiling: no bucket is cut, the "
                 "under-target ones are reached first by every producer and orderer that composes "
                 "breadth_rotation.tf_session_key. UNMEASURED where no data exists, never zero."),
        "sources": {"docket": dmeta, "seen_cells": seen_why, "judge_order": order_why,
                    "bars": {tf: on_disk.get(tf, 0) for tf in CHART_LADDER}},
        "targets": {"per_chart": chart_target, "per_bucket": bucket_target,
                    "reachable_charts": reach_charts,
                    "reachable_buckets": [_bucket_name(b) for b in reach_buckets]},
        "charts": charts,
        "buckets": buckets,
        "priority": priority,
        "under_target": under,
        "h1_share": {"discovery": disc_share_c.get("H1") if measured_disc else UNMEASURED,
                     "judged": judged_share_c.get("H1") if measured_judged else UNMEASURED},
        "wall_s": round(_time.monotonic() - t0, 2),
    }


def load_census(path: Path | None = None) -> dict[str, Any] | None:
    """The last published census, or None (UNMEASURED) when absent or unreadable."""
    try:
        doc = json.loads((path or CENSUS_REPORT).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    block = doc.get(CENSUS_KEY) if isinstance(doc, dict) else None
    return block if isinstance(block, dict) and block.get("buckets") else None


def tf_session_rank(census: dict[str, Any] | None) -> dict[str, int]:
    """{"CHART/session": rank} -- 0 for an under-target bucket, 1 otherwise. Empty when
    UNMEASURED, which makes `tf_session_key` neutral."""
    if not census:
        return {}
    under = set(census.get("under_target") or [])
    return {name: (0 if name in under else 1) for name in (census.get("buckets") or {})}


def tf_session_key(census: dict[str, Any] | None = None) -> Any:
    """A COMPOSABLE sort key: `row -> 0|1`, under-target (chart, session) bucket first.

    Prepend it to any existing key -- `(tf_session_key()(r), *old_key(r))` -- and the old order
    holds inside each tier. Built for `breadth_sweep` (which uses it) and for the docket orderer
    (`judge_coverage.order_docket`, another builder's) to compose without editing this file. With
    no census every row maps to 0 and the composed order is exactly the old one."""
    rank = tf_session_rank(census if census is not None else load_census())

    def key(row: dict[str, Any]) -> int:
        if not rank:
            return 0
        return rank.get(_bucket_name(bucket_of(row)), 1)
    return key
