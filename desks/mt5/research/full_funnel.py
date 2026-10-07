"""THE FULL FUNNEL (ARCH-26): discovery -> acquisition -> usable observations -> tested
hypotheses -> qualified forecasts -> portfolio decisions, each stage read from the artifact that
OWNS it, the limiting stage named, and compute shifted at it with exploration protected.

WHY A SIBLING OF `bottleneck_law` AND NOT A SECOND LAW. `bottleneck_law` measures the hypothesis
funnel from the registry (discovered -> converted -> ... -> live) and already moves compute through
`research_auction`. It starts AFTER the data: nothing measured whether a discovered endpoint was
ever fetched, whether a fetched series ever earned point-in-time authority, or whether a usable
series ever reached a judged cell. This module measures exactly those joins and hands its shift to
`bottleneck_law.build`, which merges it (maximum per department, never the minimum) into the one
`compute_shift` the auction already reads. There is still ONE shift and ONE clearing.

The six stages and the artifact that owns each:

    discovery            data endpoints the crawler found
                         (data/intelligence/world/discoveries_*.json) plus every URL the acquirer
                         was ever pointed at (data/acquired/registry.json by_url); the
                         deep-forest ground registry is reported beside it
    acquisition          series fetched, parsed and dated (data/acquired/registry.json series)
    usable observations  series holding PIT authority (`pit_authority is True`, the same flag
                         `acquire_datasets.acquired_series` gates the cell vocabulary on) with at
                         least MIN_ROWS rows; their rows are the observation count. The MT5 bar
                         store (data/universe/*.parquet, row counts and last bar from each file's
                         parquet footer) is its own component beside them: bars are not acquired
                         through the acquirer, so they never enter the acquisition ratio
    tested hypotheses    judged cells in the canonical registry (research_candidates.judged_at)
    qualified forecasts  certified specs (reports/UNIVERSAL_SURVIVORS.json; the 7-day rate from
                         each certificate's gated_at); the forward clocks accruing in
                         reports/shadow/*_state.json are reported beside them, with how many
                         resolve to a certified spec and how (`match_clocks`)
    portfolio decisions  LIVE sleeves (data/sleeves.json) united with the allocator's last book
                         (data/pf_forecast_log.jsonl); decision_ledger.jsonl gives the 7-day rate

Transitions are measured in the UPSTREAM unit: the share of a stage's own objects that reached the
next stage. A stage whose artifact is absent, unreadable or empty is UNMEASURED with its reason,
never zero (L1.28a), and a transition with an UNMEASURED side is never the limiting stage. A
transition whose artifacts are older than STALE_AFTER_H is still reported but cannot move compute:
a stale feeder is a plumbing finding, not a demand signal.

PROTECTED EXPLORATION. Every stage keeps STAGE_FLOOR of the attention plan and discovery keeps
EXPLORATION_FLOOR on top of it, whatever binds (`stage_shares`). In the compute that actually
moves, `exploration_guard` raises each exploration department's factor to the geometric mean of
all factors, which is the exact amount that keeps its post-clearing auction share where it would
have been with no shift at all (the auction divides every bid by that geometric mean). Every factor
here is >= 1.0: nothing is cut, total mining is never reduced, and the auction's own [0.5, 2.0]
clip remains the last floor.

    desks/mt5/reports/FUNNEL_BOTTLENECK.json   written by the hourly `bottleneck_law` leg
"""
from __future__ import annotations

import contextlib
import itertools
import json
import math
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "FUNNEL_BOTTLENECK.json"
WORLD = BASE / "data" / "intelligence" / "world"
ACQUIRED = BASE / "data" / "acquired" / "registry.json"
BARS = BASE / "data" / "universe"
GROUNDS = BASE / "data" / "deep_forest_sources.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SHADOW = BASE / "reports" / "shadow"
SLEEVES = BASE / "data" / "sleeves.json"
FORECASTS = BASE / "data" / "pf_forecast_log.jsonl"
DECISIONS = BASE / "data" / "decision_ledger.jsonl"

UNMEASURED = "UNMEASURED"
STAGES: tuple[str, ...] = ("discovery", "acquisition", "usable_observations",
                           "tested_hypotheses", "qualified_forecasts", "portfolio_decisions")
#: The legs whose seconds raise each TRANSITION's conversion: the downstream stage's organs. Their
#: departments are resolved from hourly_cycle.LEG_DEPARTMENT, so a leg that moves department moves
#: the shift with it; FALLBACK names the department when no listed leg resolves.
ROUTE_LEGS: dict[str, tuple[str, ...]] = {
    "discovery->acquisition": ("acquire_datasets", "world_dataset_hunt",
                               "data_acquisition_scientist", "dukascopy_backfill"),
    "acquisition->usable_observations": ("acquire_datasets", "lake_promote",
                                         "dukascopy_backfill"),
    "usable_observations->tested_hypotheses": ("miner_candidate_compiler", "anomaly_miner"),
    "tested_hypotheses->qualified_forecasts": ("external_gauntlet", "judging_throughput",
                                               "judging_burndown"),
    "qualified_forecasts->portfolio_decisions": ("pf_allocator", "allocator_trigger",
                                                 "shadow_discovery"),
}
FALLBACK: dict[str, str] = {
    "discovery->acquisition": "data", "acquisition->usable_observations": "data",
    "usable_observations->tested_hypotheses": "discovery",
    "tested_hypotheses->qualified_forecasts": "validate",
    "qualified_forecasts->portfolio_decisions": "forward",
}
#: The legs that DISCOVER; their departments, plus these, are the protected exploration set.
EXPLORATION_LEGS: tuple[str, ...] = ("world_crawler", "deep_forest", "free_stack_hunt",
                                     "world_dataset_hunt")
EXPLORATION_DEPARTMENTS: tuple[str, ...] = ("intel", "discovery")
STAGE_FLOOR = 0.05          #: every stage's reserved share of the attention plan
EXPLORATION_FLOOR = 0.15    #: discovery's extra reserve, held whatever binds
MAX_SHIFT = 2.0             #: bottleneck_law.MAX_SHIFT; the auction clips at 2.0 anyway
STALE_AFTER_H = 72.0
MIN_ROWS_DEFAULT = 200      #: acquire_datasets.MIN_ROWS, read live when importable
MAX_WORLD_FILES = 600
_STAMP = re.compile(r"(\d{8})_(\d{4})")


def _dct(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _read(path: Path) -> dict[str, Any] | None:
    """The document, or None when it is absent or unreadable -- never an empty dict standing in
    for a measurement."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00").replace(" ", "T", 1))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _iso(t: datetime | None) -> str | None:
    return t.astimezone(UTC).isoformat(timespec="seconds") if t else None


def _newest(*ts: datetime | None) -> datetime | None:
    vals = [t for t in ts if t is not None]
    return max(vals) if vals else None


def _unmeasured(stage: str, why: str, **extra: Any) -> dict[str, Any]:
    return {"stage": stage, "measured": False, "count": UNMEASURED, "reason": why,
            "throughput_7d": UNMEASURED, **extra}


def _min_rows() -> int:
    try:
        import acquire_datasets
        return int(acquire_datasets.MIN_ROWS)
    except Exception:
        return MIN_ROWS_DEFAULT


# ------------------------------------------------------------------------------- stages
def measure_discovery(world_dir: Path, acquired: dict[str, Any] | None,
                      grounds: dict[str, Any] | None, now: datetime,
                      max_files: int = MAX_WORLD_FILES) -> dict[str, Any]:
    files: list[tuple[datetime, Path]] = []
    with contextlib.suppress(OSError):
        for f in world_dir.glob("discoveries_*.json"):
            m = _STAMP.search(f.name)
            if m:
                files.append((datetime.strptime("".join(m.groups()), "%Y%m%d%H%M")
                              .replace(tzinfo=UTC), f))
    files.sort(key=lambda x: x[0], reverse=True)
    files = files[:max_files]
    endpoints: set[str] = set()
    recent: set[str] = set()
    rows = 0
    cut = now - timedelta(days=7)
    for at, f in files:
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for r in doc if isinstance(doc, list) else []:
            if not isinstance(r, dict):
                continue
            rows += 1
            for u in r.get("endpoints") or []:
                if isinstance(u, str) and u:
                    endpoints.add(u)
                    if at >= cut:
                        recent.add(u)
    by_url = _dct(_dct(acquired).get("by_url"))
    if not files and not by_url:
        return _unmeasured("discovery", "no crawler discoveries file and no acquirer registry "
                                        "on this host")
    discovered = endpoints | set(by_url)
    g = _dct(grounds).get("grounds")
    return {"stage": "discovery", "measured": True, "count": len(discovered),
            "unit": "data endpoint", "urls": discovered,
            "throughput_7d": len(recent) if files else UNMEASURED,
            "as_of": _iso(_newest(files[0][0] if files else None,
                                  _ts(_dct(acquired).get("updated_at")))),
            "components": {"crawler_endpoints": len(endpoints), "crawler_rows": rows,
                           "crawler_files_read": len(files), "acquirer_urls": len(by_url),
                           "deep_forest_grounds": (len(g) if isinstance(g, (list, dict))
                                                   else UNMEASURED)},
            "basis": ["data/intelligence/world/discoveries_*.json",
                      "data/acquired/registry.json:by_url", "data/deep_forest_sources.json"]}


def measure_acquisition(acquired: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    if acquired is None:
        return _unmeasured("acquisition", "data/acquired/registry.json absent or unreadable")
    by_url = _dct(acquired.get("by_url"))
    series = _dct(acquired.get("series"))
    fetched_urls = {u for u, m in by_url.items() if _dct(m).get("series")}
    cut = now - timedelta(days=7)
    recent = sum(1 for m in series.values()
                 if (t := _ts(_dct(m).get("acquired_at"))) is not None and t >= cut)
    return {"stage": "acquisition", "measured": True, "count": len(series), "unit": "series",
            "urls": fetched_urls, "names": set(series),
            "rows": sum(int(_dct(m).get("rows") or 0) for m in series.values()),
            "throughput_7d": recent, "as_of": _iso(_ts(acquired.get("updated_at"))),
            "components": {"urls_fetched": len(fetched_urls), "urls_attempted": len(by_url)},
            "basis": ["data/acquired/registry.json:series"]}


def measure_usable(acquired: dict[str, Any] | None, now: datetime,
                   min_rows: int | None = None) -> dict[str, Any]:
    if acquired is None:
        return _unmeasured("usable_observations", "data/acquired/registry.json absent or "
                                                  "unreadable")
    floor = int(min_rows if min_rows is not None else _min_rows())
    series = _dct(acquired.get("series"))
    usable = {n: _dct(m) for n, m in series.items()
              if _dct(m).get("pit_authority") is True and int(_dct(m).get("rows") or 0) >= floor
              and _dct(m).get("first") and _dct(m).get("last")}
    cut = now - timedelta(days=7)
    recent = sum(1 for m in usable.values()
                 if (t := _ts(m.get("acquired_at"))) is not None and t >= cut)
    return {"stage": "usable_observations", "measured": True, "count": len(usable),
            "unit": "series", "names": set(usable),
            "observations": sum(int(m.get("rows") or 0) for m in usable.values()),
            "throughput_7d": recent, "as_of": _iso(_ts(acquired.get("updated_at"))),
            "components": {"no_pit_authority": sum(1 for m in series.values()
                                                   if _dct(m).get("pit_authority") is not True),
                           "below_min_rows": sum(1 for m in series.values()
                                                 if int(_dct(m).get("rows") or 0) < floor),
                           "min_rows": floor},
            "basis": ["data/acquired/registry.json:series[pit_authority, rows, first, last]"]}


def measure_mt5_bars(bar_dir: Path, now: datetime) -> dict[str, Any]:
    """The MT5 bar store, read from each parquet's FOOTER (row count, and the `time` column's
    max statistic as the last bar) -- no data page is read. An absent store, or no reader, is
    UNMEASURED; a file whose footer will not open is counted as unreadable, never as zero rows."""
    try:
        import pyarrow.parquet as pq
    except Exception as exc:
        return {"measured": False, "reason": f"no parquet reader: {type(exc).__name__}"}
    try:
        files = sorted(bar_dir.glob("*_*.parquet"))
    except OSError as exc:
        return {"measured": False, "reason": f"{bar_dir} unreadable: {type(exc).__name__}"}
    if not files:
        return {"measured": False, "reason": f"no bar parquet under {bar_dir}"}
    rows = 0
    by_tf: dict[str, int] = {}
    last: datetime | None = None
    fresh_7d = unreadable = 0
    cut = now - timedelta(days=7)
    for f in files:
        try:
            meta = pq.read_metadata(f)
        except Exception:
            unreadable += 1
            continue
        rows += int(meta.num_rows)
        tf = f.stem.rsplit("_", 1)[-1]
        by_tf[tf] = by_tf.get(tf, 0) + int(meta.num_rows)
        t_last: datetime | None = None
        with contextlib.suppress(Exception):
            names = [meta.schema.column(i).name for i in range(meta.num_columns)]
            col = names.index("time")
            for g in range(meta.num_row_groups):
                st = meta.row_group(g).column(col).statistics
                if st is not None and st.has_min_max:
                    v = st.max
                    t = (v.to_pydatetime() if hasattr(v, "to_pydatetime") else v)
                    if isinstance(t, datetime):
                        t = t if t.tzinfo else t.replace(tzinfo=UTC)
                        t_last = _newest(t_last, t)
        last = _newest(last, t_last)
        fresh_7d += int(t_last is not None and t_last >= cut)
    return {"measured": True, "files": len(files) - unreadable, "unreadable": unreadable,
            "rows": rows, "rows_by_timeframe": dict(sorted(by_tf.items())),
            "files_with_a_bar_in_7d": fresh_7d, "last_bar": _iso(last),
            "basis": f"{bar_dir.name}/*_<TF>.parquet footers (num_rows, time max statistic)"}


def with_bars(usable: dict[str, Any], bars: dict[str, Any]) -> dict[str, Any]:
    """MT5 bar rows as their own component of usable observations. They join the observation
    total but never the series count: the stage's count stays in the acquirer's unit so the
    acquisition -> usable share means what it says."""
    out = dict(usable)
    comp = dict(_dct(usable.get("components")))
    if bars.get("measured"):
        comp.update({"mt5_bar_files": bars["files"], "mt5_bar_rows": bars["rows"],
                     "mt5_bar_rows_by_timeframe": bars["rows_by_timeframe"],
                     "mt5_bar_files_fresh_7d": bars["files_with_a_bar_in_7d"],
                     "mt5_bar_last": bars["last_bar"],
                     "mt5_bar_unreadable_files": bars["unreadable"]})
        ext = usable.get("observations") if usable.get("measured") else UNMEASURED
        comp["external_observations"] = ext
        out["observations"] = (int(ext) + int(bars["rows"]) if isinstance(ext, int)
                               else int(bars["rows"]))
        out["observations_complete"] = isinstance(ext, int)
    else:
        comp["mt5_bar_rows"] = UNMEASURED
        comp["mt5_bar_reason"] = bars.get("reason")
    out["components"] = comp
    out["basis"] = [*list(usable.get("basis") or []), str(bars.get("basis") or
                                                           "data/universe/*.parquet")]
    return out


def measure_tested(conn: Any | None, usable_names: Iterable[str], now: datetime,
                   scan_limit: int = 200_000) -> dict[str, Any]:
    try:
        from libs.moat import registry
        c = conn or registry.connect()
    except Exception as exc:
        return _unmeasured("tested_hypotheses", f"registry unavailable: {type(exc).__name__}")
    try:
        def one(sql: str, *a: Any) -> Any:
            row = c.execute(sql, a).fetchone()
            return row[0] if row is not None else None
        try:
            total = int(one("SELECT COUNT(*) FROM research_candidates") or 0)
            judged = int(one("SELECT COUNT(*) FROM research_candidates WHERE judged_at IS NOT "
                             "NULL AND judged_at!=''") or 0)
            recent = int(one("SELECT COUNT(*) FROM research_candidates WHERE judged_at >= ?",
                             (now - timedelta(days=7)).isoformat()) or 0)
            last = one("SELECT MAX(judged_at) FROM research_candidates")
        except Exception as exc:
            return _unmeasured("tested_hypotheses",
                               f"registry research_candidates unreadable: {type(exc).__name__}")
        if total == 0:
            return _unmeasured("tested_hypotheses", "the registry holds no candidate rows on "
                                                    "this host (a stub is not a zero)")
        names = sorted(set(usable_names))
        fed: set[str] = set()
        if names:
            try:
                for r in c.execute(
                        "SELECT COALESCE(required_data_json,'') || ' ' || COALESCE(params_json,'')"
                        " || ' ' || COALESCE(exact_rules,'') FROM research_candidates WHERE "
                        "judged_at IS NOT NULL AND judged_at!='' AND (required_data_json LIKE "
                        "'%ext_%' OR params_json LIKE '%ext_%' OR exact_rules LIKE '%ext_%') "
                        "LIMIT ?", (int(scan_limit),)):
                    text = str(r[0] or "")
                    fed.update(n for n in names if n not in fed and f"ext_{n}" in text)
            except Exception:
                fed = set()
    finally:
        if conn is None:
            with contextlib.suppress(Exception):
                c.close()
    return {"stage": "tested_hypotheses", "measured": True, "count": judged, "unit": "cell",
            "series_fed": fed, "throughput_7d": recent, "as_of": _iso(_ts(last)),
            "components": {"candidates": total, "usable_series_in_a_judged_cell": len(fed)},
            "basis": ["registry research_candidates.judged_at",
                      "registry research_candidates.required_data_json/params_json/exact_rules"]}


#: The certificate a clock row may name as a field, in the order they are trusted.
_CLOCK_CERT_FIELDS = ("certificate", "certificate_at_revival")


def _spec_clock_keys(certified: Mapping[str, Any]) -> dict[str, list[str]]:
    """{clock key: [certificate ids]}, each certificate's `shadow_spec` keyed by the forward
    lane's OWN key function (`shadow_forward.sleeve_key`), so a clock and its certificate meet on
    the exact string the lane wrote. Several certificates can share one key -- the same spec
    certified under two ids (default parameters spelled out or not) -- and all are kept: the
    clock is that spec's clock whichever id certified it."""
    try:
        import shadow_forward
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    for cid, row in certified.items():
        spec = _dct(_dct(row).get("shadow_spec"))
        sym, sel = spec.get("symbol"), spec.get("selector")
        if not (isinstance(sym, str) and isinstance(sel, str)):
            continue
        try:
            key = shadow_forward.sleeve_key(
                sym, sel, dict(_dct(spec.get("params"))),
                str(spec.get("family") or "session_range_breakout"),
                str(spec.get("side") or "LONG"))
        except Exception:
            continue
        out.setdefault(key, []).append(str(cid))
    return {k: sorted(v) for k, v in out.items()}


def match_clocks(clocks: Mapping[str, dict[str, Any]],
                 certified: Mapping[str, Any] | Iterable[str]) -> dict[str, Any]:
    """Which accruing forward clocks resolve to a certified spec, and how. Exact identities only:

        named      the clock row names the certificate (`certificate` / `certificate_at_revival`,
                   a string or a {cell|key} dict) and that id is a certified key
        key        the clock's own key IS a certified key (the qquant lane keys clocks so)
        spec       the clock's key equals `shadow_forward.sleeve_key` of a certificate's own
                   `shadow_spec` (symbol, selector, family, params, side)

    A clock none of these resolve is UNMATCHED and listed, never assumed to share a spec."""
    specs = certified if isinstance(certified, Mapping) else {}
    cert = {str(k) for k in (certified.keys() if isinstance(certified, Mapping)
                             else certified)}
    by_spec = _spec_clock_keys(specs)
    matched: dict[str, list[str]] = {}
    how: dict[str, int] = {"named": 0, "key": 0, "spec": 0}
    unmatched: list[str] = []
    for key, row in clocks.items():
        hit = None
        for fld in _CLOCK_CERT_FIELDS:
            v = row.get(fld)
            v = (v.get("cell") or v.get("key")) if isinstance(v, dict) else v
            if isinstance(v, str) and v in cert:
                hit, kind = v, "named"
                break
        if hit is None and key in cert:
            hit, kind = key, "key"
        hits = [hit] if hit is not None else list(by_spec.get(key) or [])
        if hit is None and hits:
            kind = "spec"
        if not hits:
            unmatched.append(key)
        else:
            matched[key] = hits
            how[kind] += 1
    return {"clocks": len(clocks), "matched": len(matched),
            "specs_with_a_clock": len({c for cs in matched.values() for c in cs}),
            "matched_by": how,
            "unmatched": len(unmatched), "unmatched_sample": sorted(unmatched)[:20]}


def measure_qualified(survivors: dict[str, Any] | None, shadow_dir: Path,
                      now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    clocks: dict[str, dict[str, Any]] = {}
    last: datetime | None = None
    started_7d = 0
    cut = now - timedelta(days=7)
    with contextlib.suppress(OSError):
        for f in sorted(shadow_dir.glob("*_state.json")):
            for key, row in _dct(_read(f)).items():
                if isinstance(row, dict) and str(row.get("status") or "") in (
                        "ACTIVE", "PROMOTION CANDIDATE"):
                    clocks[f"{f.stem}:{key}" if key in clocks else str(key)] = row
                    last = _newest(last, _ts(row.get("last_attempt_at")))
                    t0 = _ts(row.get("forward_start"))
                    started_7d += int(t0 is not None and cut <= t0 <= now)
    if survivors is None:
        return _unmeasured("qualified_forecasts", "reports/UNIVERSAL_SURVIVORS.json absent",
                           components={"forward_clocks_accruing": len(clocks)})
    sv = survivors.get("survivors")
    rows = sv if isinstance(sv, dict) else {}
    n = len(sv) if isinstance(sv, (dict, list)) else int(survivors.get("n") or 0)
    gated = [t for r in rows.values() if isinstance(r, dict)
             if (t := _ts(r.get("gated_at"))) is not None]
    # THE 7-DAY RATE IS MEASURED ONLY WHEN EVERY CERTIFICATE CARRIES ITS gated_at: a partial
    # stamp would undercount, and an undercount reads as a slowdown.
    rate: int | str = (sum(1 for t in gated if cut <= t <= now)
                       if rows and len(gated) == len(rows) else UNMEASURED)
    match = match_clocks(clocks, rows)
    return {"stage": "qualified_forecasts", "measured": True, "count": n, "unit": "spec",
            "throughput_7d": rate,
            "as_of": _iso(_newest(_ts(survivors.get("swept_at")), last)),
            "components": {"certified_specs": n, "certified_7d": rate,
                           "certificates_with_gated_at": len(gated),
                           "last_gated_at": _iso(max(gated) if gated else None),
                           "forward_clocks_accruing": len(clocks),
                           "forward_clocks_started_7d": started_7d,
                           "clocks_matched_to_a_certified_spec": match["matched"],
                           "certified_specs_with_a_clock": match["specs_with_a_clock"]},
            "clock_match": match,
            "basis": ["reports/UNIVERSAL_SURVIVORS.json (survivors[*].gated_at)",
                      "reports/shadow/*_state.json (status, forward_start, certificate)"]}


def _tail_lines(path: Path, max_bytes: int = 4 << 20) -> list[str]:
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            return fh.read().decode("utf-8", "replace").splitlines()[1 if size > max_bytes
                                                                       else 0:]
    except OSError:
        return []


def measure_decisions(sleeves: dict[str, Any] | None, forecast_path: Path,
                      decision_path: Path, now: datetime) -> dict[str, Any]:
    book: dict[str, Any] = {}
    book_at: datetime | None = None
    for line in reversed(_tail_lines(forecast_path, 1 << 20)):
        with contextlib.suppress(ValueError):
            row = json.loads(line)
            if isinstance(row, dict) and isinstance(row.get("book"), dict):
                book, book_at = row["book"], _ts(row.get("t"))
                break
    cut = now - timedelta(days=7)
    recent = 0
    last_dec: datetime | None = None
    lines = _tail_lines(decision_path)
    for line in lines:
        with contextlib.suppress(ValueError):
            t = _ts(_dct(json.loads(line)).get("decided_at"))
            if t is not None:
                last_dec = _newest(last_dec, t)
                recent += int(t >= cut)
    if sleeves is None and not book:
        return _unmeasured("portfolio_decisions", "data/sleeves.json absent and no allocator "
                                                  "book in data/pf_forecast_log.jsonl")
    live = {str(r.get("name") or "") for r in (_dct(sleeves).get("sleeves") or [])
            if isinstance(r, dict) and r.get("status") == "LIVE"}
    weighted = {str(k) for k, v in book.items() if isinstance(v, (int, float)) and v > 0}
    return {"stage": "portfolio_decisions", "measured": True, "count": len(live | weighted),
            "unit": "spec", "throughput_7d": recent if lines else UNMEASURED,
            "as_of": _iso(_newest(book_at, last_dec)),
            "components": {"live_sleeves": len(live), "allocator_book_weighted": len(weighted),
                           "decisions_7d": recent if lines else UNMEASURED},
            "basis": ["data/sleeves.json", "data/pf_forecast_log.jsonl (last book)",
                      "data/decision_ledger.jsonl"]}


# -------------------------------------------------------------------------- transitions
def _advanced(name: str, up: dict[str, Any], down: dict[str, Any]) -> int | None:
    if not (up.get("measured") and down.get("measured")):
        return None
    if name == "discovery->acquisition":
        return len(set(up.get("urls") or ()) & set(down.get("urls") or ()))
    if name == "acquisition->usable_observations":
        return len(set(up.get("names") or ()) & set(down.get("names") or ()))
    if name == "usable_observations->tested_hypotheses":
        return len(set(down.get("series_fed") or ()))
    return min(int(down["count"]), int(up["count"]))


def _stale(stage: dict[str, Any], now: datetime) -> bool:
    t = _ts(stage.get("as_of"))
    return t is None or (now - t).total_seconds() > STALE_AFTER_H * 3600


def transitions(stages: Mapping[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a, b in itertools.pairwise(STAGES):
        name = f"{a}->{b}"
        up, down = stages[a], stages[b]
        adv = _advanced(name, up, down)
        n_in = int(up["count"]) if up.get("measured") else None
        measured = adv is not None and n_in is not None and n_in > 0
        why = None
        if not measured:
            why = (f"{a}: {up.get('reason')}" if not up.get("measured") else
                   f"{b}: {down.get('reason')}" if not down.get("measured") else
                   f"{a} holds no objects")
        ratio = round(min(adv, n_in) / n_in, 6) if measured and adv is not None and n_in else None
        out.append({"stage": name, "in": n_in if n_in is not None else UNMEASURED,
                    "advanced": adv if adv is not None else UNMEASURED,
                    "ratio": ratio, "unit": up.get("unit"), "measured": measured,
                    "stale": measured and (_stale(up, now) or _stale(down, now)),
                    "backlog": (max(n_in - adv, 0) if measured and adv is not None and n_in
                                else None),
                    "reason": why})
    return out


def limiting(trans: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The measured transition with the lowest ratio, fresh ones first; ties to the bigger
    backlog. A stale pick is returned but flagged, and `compute_shift` will not act on it."""
    measured = [t for t in trans if t["measured"] and t["ratio"] is not None]
    if not measured:
        return None
    fresh = [t for t in measured if not t["stale"]]
    return min(fresh or measured, key=lambda t: (float(t["ratio"]), -int(t["backlog"] or 0)))


# ------------------------------------------------------------------------ the shift
def leg_departments() -> tuple[dict[str, str], tuple[str, ...]]:
    try:
        import research_auction
        return research_auction.leg_departments()
    except Exception:
        return {}, ()


def routed_departments(stage: str, legs: Mapping[str, str]) -> tuple[list[str], list[str]]:
    routed = [lg for lg in ROUTE_LEGS.get(stage, ()) if lg in legs]
    depts = sorted({legs[lg] for lg in routed}) or [FALLBACK[stage]]
    return depts, routed


def exploration_departments(legs: Mapping[str, str]) -> list[str]:
    return sorted({*EXPLORATION_DEPARTMENTS,
                   *(legs[lg] for lg in EXPLORATION_LEGS if lg in legs),
                   *(d for lg, d in legs.items() if lg.startswith("forest_"))})


def exploration_guard(shift: Mapping[str, float], departments: Iterable[str],
                      protected: Iterable[str]) -> dict[str, float]:
    """Raise each protected department to the geometric mean of every department's factor.

    The auction clears factor_d = bid_d * shift_d / gmean(bid * shift). A protected department
    whose shift equals gmean(shift) clears exactly where it would have with no shift at all, so
    a shift toward the limiting stage is paid for by nobody in exploration. Iterated to the fixed
    point gmean^(n-k) = product of the unprotected shifts. Only ever RAISES a factor."""
    depts = sorted(set(departments) | set(shift))
    prot = set(protected) & set(depts)
    out = {d: max(1.0, float(shift.get(d, 1.0) or 1.0)) for d in depts}
    if not depts or not prot or len(prot) == len(depts):
        return {d: round(v, 4) for d, v in out.items()}
    for _ in range(200):
        g = math.exp(sum(math.log(v) for v in out.values()) / len(out))
        moved = False
        for p in prot:
            if out[p] < g - 1e-12:
                out[p], moved = g, True
        if not moved:
            break
    # rounded UP so the published factor never sits a hair below the mean it must match
    return {d: math.ceil(v * 10_000) / 10_000 for d, v in out.items()}


def stage_shares(limit: dict[str, Any] | None) -> dict[str, float]:
    """The attention plan: STAGE_FLOOR for every stage, EXPLORATION_FLOOR more for discovery,
    the remainder to the stage DOWNSTREAM of the limiting transition (its organs raise the
    conversion). With nothing limiting, the remainder spreads evenly -- never to zero anywhere."""
    shares = dict.fromkeys(STAGES, STAGE_FLOOR)
    shares["discovery"] += EXPLORATION_FLOOR
    rest = 1.0 - sum(shares.values())
    if limit is not None and not limit.get("stale"):
        shares[str(limit["stage"]).split("->")[1]] += rest
    else:
        for s in STAGES:
            shares[s] += rest / len(STAGES)
    return {s: round(v, 6) for s, v in shares.items()}


def compute_shift(limit: dict[str, Any] | None, legs: Mapping[str, str],
                  departments: Iterable[str]) -> tuple[dict[str, float], dict[str, Any]]:
    depts = set(departments) | set(FALLBACK.values())
    shift = dict.fromkeys(depts, 1.0)
    route: dict[str, Any] = {"departments": [], "legs": [], "applied": False}
    if limit is None:
        route["why"] = "no measured transition: nothing to shift toward"
    elif limit.get("stale"):
        route["why"] = (f"{limit['stage']} is the lowest ratio but its artifacts are older than "
                        f"{STALE_AFTER_H:.0f} h: a stale feeder is a plumbing finding, not demand")
    else:
        f = round(min(MAX_SHIFT, 1.0 + max(0.0, 1.0 - float(limit["ratio"] or 0.0))), 4)
        d_list, routed = routed_departments(str(limit["stage"]), legs)
        for d in d_list:
            shift[d] = max(shift.get(d, 1.0), f)
        route = {"departments": d_list, "legs": routed, "applied": True, "factor": f,
                 "data_stage": str(limit["stage"]).startswith(("discovery->", "acquisition->")),
                 "why": f"{limit['stage']} converts {limit['ratio']} of {limit['in']} "
                        f"{limit['unit']}(s)"}
    protected = exploration_departments(legs)
    guarded = exploration_guard(shift, depts, protected)
    route["protected_exploration"] = protected
    return guarded, route


# ------------------------------------------------------------------------------ build
def _public(stage: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in stage.items() if k not in ("urls", "names", "series_fed")}


def build(now: datetime | None = None, conn: Any | None = None, *,
          world_dir: Path = WORLD, acquired: dict[str, Any] | bool | None = True,
          grounds: dict[str, Any] | bool | None = True,
          survivors: dict[str, Any] | bool | None = True, shadow_dir: Path = SHADOW,
          sleeves: dict[str, Any] | bool | None = True, forecast_path: Path = FORECASTS,
          decision_path: Path = DECISIONS, bar_dir: Path = BARS,
          legs: tuple[dict[str, str], tuple[str, ...]] | None = None) -> dict[str, Any]:
    """`True` for a document argument means "read it from its owning artifact"; None means
    absent (UNMEASURED); a dict is injected."""
    now = now or datetime.now(tz=UTC)
    acq = _read(ACQUIRED) if acquired is True else acquired
    grd = _read(GROUNDS) if grounds is True else grounds
    srv = _read(SURVIVORS) if survivors is True else survivors
    slv = _read(SLEEVES) if sleeves is True else sleeves
    st: dict[str, dict[str, Any]] = {
        "discovery": measure_discovery(world_dir, acq if isinstance(acq, dict) else None,
                                       grd if isinstance(grd, dict) else None, now),
        "acquisition": measure_acquisition(acq if isinstance(acq, dict) else None, now),
    }
    st["usable_observations"] = with_bars(
        measure_usable(acq if isinstance(acq, dict) else None, now), measure_mt5_bars(bar_dir, now))
    st["tested_hypotheses"] = measure_tested(conn, st["usable_observations"].get("names") or (),
                                             now)
    st["qualified_forecasts"] = measure_qualified(srv if isinstance(srv, dict) else None,
                                                  shadow_dir, now)
    st["portfolio_decisions"] = measure_decisions(slv if isinstance(slv, dict) else None,
                                                  forecast_path, decision_path, now)
    trans = transitions(st, now)
    lim = limiting(trans)
    leg_map, depts = legs if legs is not None else leg_departments()
    shift, route = compute_shift(lim, leg_map, depts)
    unmeasured = [f"{s}: {st[s]['reason']}" for s in STAGES if not st[s]["measured"]]
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"), "stages": {s: _public(st[s]) for s in STAGES},
        "transitions": trans, "limiting": lim, "compute_shift": shift, "route": route,
        "stage_shares": stage_shares(lim),
        "floors": {"stage": STAGE_FLOOR, "exploration": EXPLORATION_FLOOR,
                   "auction_clip": [0.5, 2.0]},
        "unmeasured": unmeasured,
        "consumer": ("bottleneck_law.build merges compute_shift (max per department) into "
                     "BOTTLENECK_LAW.compute_shift -> research_auction.bids -> "
                     "research_budget.budget_s next epoch; research_dashboard"),
        "rule": ("each stage is read from the artifact that owns it; an absent one is UNMEASURED "
                 "and never limiting; the limiting transition is the lowest fresh out/in share "
                 "in the upstream unit; its downstream organs' departments rise to "
                 "1+(1-ratio) <= 2.0; exploration departments are raised to the geometric mean "
                 "so their cleared share never falls; no factor is below 1.0"),
    }
    if lim is None:
        doc["headline"] = (f"UNMEASURED: no transition measurable ({len(unmeasured)} stage(s) "
                           f"unmeasured)")
    else:
        doc["headline"] = (f"limiting {lim['stage']} ratio {lim['ratio']} of {lim['in']} "
                           f"{lim['unit']}(s)" + (" [STALE: no shift]" if lim["stale"] else
                                                  f" -> {route['departments']} "
                                                  f"x{route.get('factor')}"))
    return doc


def publish(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
