"""THE ALT CATALOG -- every lake series the gauntlet can apply as an `alt:` conditioner, handed to
the free-model generators in the exact spec syntax, weighted toward the series nobody has tested.

THE DEFECT (measured 2026-11-25 on the repo's committed state). `mt5desk.cell_modifiers` applies
exactly one conditioner form -- `alt:<series>:<column>:<op>:<threshold>`, read from
`data/lake/series/<series>.(parquet|csv)` on its `available_time` clock -- and refuses every
other value. The lake is written by a dozen organs (alt_proxies, keyed_sources, free_stack,
macro_state_engine, tick_features, futures_state, asia_parser ...). Yet NO free-model generator's
prompt named a single lake series or the spec syntax, and of the ~9.4k committed compiler rows
carrying a `conditioner`, NONE was a well-formed `alt:` spec: every one was a prose axis
("macro", "carry", "positioning") that the gauntlet refuses by construction. The alt data
reached the deterministic organs that wrote it and stopped there.

WHAT THIS IS. A library (no clock of its own; its readers are on clocks):

  catalog()       every lake series with a PIT `available_time` stamp and >= 1 numeric column,
                  its source (the dataset-level unit), the columns, and the `alt:` specs whose
                  threshold is MEASURED (0 for a z-shaped column; the column's own median for a
                  level column, read from the frame; a column with neither offers no spec).
  coverage(rows)  per series: compiled rows, testable rows (family_spec EXECUTABLE), judged
                  (the cell's frontier identity in gauntlet_seen_cells) and certified (in
                  certificate_provenance), plus which generators were SHOWN it (exposure log).
  prompt_block()  a bounded, rotating, gap-weighted slice for one generator's prompt, with the
                  spec syntax, the families it may condition and the output line it must use.
                  Weight = 1 / (1 + testable rows), doubled for a producer_loop alt gap target;
                  EXPLORE_SHARE of the slots is drawn uniformly so a covered series is re-shown.
  parse_cells()   the generator's `ALT_CELL | family | SYMBOL | alt:... | mechanism` lines,
                  validated against the catalog and the family list, as donation rows the
                  compiler admits as EXACT_RECIPE (family + params + symbols).

Nothing here judges, sizes or charges: trials are charged where the compiler and the gauntlet
already charge them, and the bar never moves because a model suggested a series. A lake that is
absent on this host makes the catalog UNMEASURED, never empty-and-clean (L1.28a).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import random
import re
import sys
import tempfile
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
PREFIX = "alt:"
LAKE = DESK / "data" / "lake" / "series"
EXPOSURE = DESK / "data" / "alt_catalog" / "exposure.json"
FUNNEL = DESK / "reports" / "FUNNEL.json"
PRESCRIPTIONS = DESK / "data" / "PRODUCER_PRESCRIPTIONS.json"
SEEN = DESK / "data" / "hypotheses" / "gauntlet_seen_cells.json"
PROVENANCE = DESK / "data" / "certificate_provenance.json"

#: Series per prompt. Bounded so the block stays a few hundred tokens whatever the lake holds.
PROMPT_K = 12
#: Share of the slots drawn uniformly (exploration), the rest gap-weighted.
EXPLORE_SHARE = 0.25
#: Weight multiplier for a series the producer loop names as an alt gap target.
GAP_BOOST = 2.0
#: ALT_CELL lines accepted per reply (a flood is not breadth).
MAX_CELLS = 24
#: Columns read as z-shaped: their threshold 0 is the series' own mean, a measured midpoint.
Z_SUFFIXES = ("_z", "z")
STAMP_COLS = frozenset({"event_time", "published_time", "available_time", "revision_time",
                        "retrieval_time", "ingested_time", "source_id", "vintage_id"})
#: Per-symbol producers: the source is the prefix, the series is one per instrument.
PER_SYMBOL_PREFIXES = ("tick_features_", "tick_news_", "dealer_gamma_", "gamma_price_",
                       "blog_social_")
OPS = ("gt", "lt")
CELL_LINE = re.compile(r"^\s*ALT_CELL\s*\|", re.IGNORECASE)
#: Price-only families the compiler admits as an exact recipe; the conditioner rides on them.
DEFAULT_FAMILIES = ("session_range_breakout", "trend_ma_cross", "mean_reversion_bollinger",
                    "overnight_gap_decay", "momentum_volgate", "volatility_squeeze",
                    "range_reversion", "london_close_momentum", "asia_momentum")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
    os.replace(tmp, p)


# ------------------------------------------------------------------------------- the spec ---
def parse_spec(value: Any) -> tuple[str, str, str, float] | None:
    """`alt:<series>:<column>:<op>:<threshold>` -> (series, column, op, threshold), else None.

    THE GAUNTLET'S OWN PARSER (`mt5desk.cell_modifiers.alt_conditioner`) when importable, so the
    two can never disagree about what is well formed; the fallback mirrors it exactly."""
    try:
        from mt5desk.cell_modifiers import alt_conditioner
        return alt_conditioner(value)
    except Exception:
        text = str(value if value is not None else "").strip()
        if not text.startswith(PREFIX):
            return None
        parts = text[len(PREFIX):].split(":")
        if len(parts) != 4 or not parts[0] or not parts[1] \
                or parts[2] not in ("gt", "ge", "lt", "le"):
            return None
        if any(c in parts[0] for c in ("/", "\\", "..")):
            return None
        try:
            return parts[0], parts[1], parts[2], float(parts[3])
        except ValueError:
            return None


def spec(series: str, column: str, op: str, threshold: float) -> str:
    thr = f"{threshold:.6g}"
    return f"{PREFIX}{series}:{column}:{op}:{thr}"


def source_of(series: str) -> str:
    """The dataset-level unit a series belongs to (a keyed source's id, an asia pack's id, a
    per-symbol producer's prefix); else the series itself."""
    s = str(series or "")
    if "__" in s:
        return s.split("__", 1)[0]
    for p in PER_SYMBOL_PREFIXES:
        if s.startswith(p):
            return p.rstrip("_")
    return s


#: z columns whose WRITER computes them from strictly-prior observations only (read 2026-11-25),
#: so a threshold of 0 splits history with no out-of-sample information. A z column from any
#: other writer may be a full-sample z, which would leak the OOS mean and spread into the split,
#: so it is not offered until its writer is read and added here.
#:   alt_<src>__<series>.surprise_z  alt_proxies: sd over prior surprises only (expanding)
#:   ks_<src>__<series>.z / .chg_z   keyed_sources._z: mean/sd over the prior Z_WINDOW points
#:   *.shock_z                       futures_state: rolling mean/sd of chg.shift(1)
PIT_Z_COLUMNS: tuple[tuple[str, str], ...] = (("alt_", "surprise_z"), ("ks_", "z"),
                                               ("ks_", "chg_z"), ("", "shock_z"))


def _pit_z(series: str, column: str) -> bool:
    return any(series.startswith(pre) and column == col for pre, col in PIT_Z_COLUMNS)


def _is_z(column: str) -> bool:
    c = column.lower()
    return c.endswith(Z_SUFFIXES) and (c == "z" or c.endswith("_z"))


# ---------------------------------------------------------------------------- the catalog ---
def discovered() -> dict[str, dict[str, Any]]:
    """Lake series a free model proposed the DATA for (research/data_discovery.py), with who
    found it; {} when that module or its queue is unreadable (provenance only, never a gate)."""
    try:
        from research import data_discovery
        return data_discovery.provenance()
    except Exception:
        return {}


def _columns(path: Path) -> tuple[list[str], bool]:
    """(numeric signal columns, has available_time) -- the dataset translator's own reader."""
    try:
        from dataset_translator import columns_of
        return columns_of(path)
    except Exception:
        pass
    try:
        with path.open("r", encoding="utf-8") as fh:
            head = fh.readline().strip()
    except OSError:
        return [], False
    names = [c.strip().strip('"') for c in head.split(",") if c.strip()]
    return [c for c in names if c not in STAMP_COLS], "available_time" in names


def _median(path: Path, column: str) -> float | None:
    try:
        import pandas as pd
        df = (pd.read_parquet(path, columns=[column]) if path.suffix == ".parquet"
              else pd.read_csv(path, usecols=[column]))
        v = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(v) < 5:
            return None
        m = float(v.median())
        return m if m == m else None
    except Exception:
        return None


def _stems(lake: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if lake.is_dir():
        for p in sorted(lake.iterdir()):
            if p.suffix in (".parquet", ".csv") and p.stem not in out:
                out[p.stem] = p
    return out


def catalog(lake: Path | None = None, *, thresholds: bool = False) -> dict[str, Any]:
    """Every executable `alt:` series on this host.

    `thresholds=False` (the cheap read every coverage pass takes) offers specs only on z-shaped
    columns whose writer is PIT (`PIT_Z_COLUMNS`); `thresholds=True` also reads a level column's
    WHOLE-FILE median, which is look-ahead (it splits history at a point chosen with the OOS
    window), so no generator prompt may use it -- it is kept for offline inspection only.
    A missing lake is UNMEASURED with the reason, never an empty catalog."""
    base = lake or LAKE
    if not base.is_dir():
        return {"status": UNMEASURED, "why": f"no lake directory at {base} on this host",
                "series": []}
    rows: list[dict[str, Any]] = []
    refused: dict[str, str] = {}
    found = discovered()
    for stem, path in _stems(base).items():
        cols, stamped = _columns(path)
        if not stamped:
            refused[stem] = "no available_time stamp: no honest PIT join"
            continue
        if not cols:
            refused[stem] = "no numeric signal column"
            continue
        specs: list[str] = []
        for c in cols[:6]:
            if _is_z(c):
                thr: float | None = 0.0 if _pit_z(stem, c) else None
            else:
                thr = _median(path, c) if thresholds else None
            if thr is None:
                continue
            specs += [spec(stem, c, op, thr) for op in OPS]
        rows.append({"series": stem, "source": source_of(stem), "columns": cols[:12],
                     "z_columns": [c for c in cols if _is_z(c)], "specs": specs,
                     "symbol": (stem[len(p):].upper() if (p := next(
                         (x for x in PER_SYMBOL_PREFIXES if stem.startswith(x)), "")) else ""),
                     **({"discovered_by": found[stem]["discovered_by"],
                         "method": found[stem]["method"]} if stem in found else {})})
    return {"status": "READ", "series": rows, "refused": refused,
            "n_series": len(rows), "n_sources": len({r["source"] for r in rows})}


# --------------------------------------------------------------------------- the coverage ---
def series_of(row: Mapping[str, Any]) -> str | None:
    p = row.get("params")
    got = parse_spec(p.get("conditioner")) if isinstance(p, Mapping) else None
    return got[0] if got else None


def _cell(row: Mapping[str, Any]) -> str | None:
    try:
        from research import frontier_identity as fi
        return str(fi.cell_id(fi.docket_cell(dict(row))))
    except Exception:
        return None


def _quality(row: Mapping[str, Any]) -> str:
    try:
        from research import family_spec as fs
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        return str(fs.to_executable(str(row.get("family") or ""), params)["status"])
    except Exception:
        return UNMEASURED


def read_judged(path: Path | None = None) -> set[str] | None:
    d = _read(path or SEEN)
    return {str(k) for k in d} if isinstance(d, dict | list) else None


def read_certified(path: Path | None = None) -> set[str] | None:
    d = _read(path or PROVENANCE)
    recs = d.get("records") if isinstance(d, dict) else None
    if isinstance(recs, dict):
        return {str(k) for k in recs}
    if isinstance(recs, list):
        return {str(r.get("cell")) for r in recs if isinstance(r, dict) and r.get("cell")}
    return None


def read_exposure(path: Path | None = None) -> dict[str, Any]:
    d = _read(path or EXPOSURE)
    return d if isinstance(d, dict) and isinstance(d.get("series"), dict) else \
        {"series": {}, "organs": {}}


def coverage(cat: Mapping[str, Any], rows: Iterable[Mapping[str, Any]], *,
             judged: set[str] | None = None, certified: set[str] | None = None,
             exposure: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Per series: generators_seeing, rows, testable_rows, judged, certified; and the zero list.

    A count whose input is unreadable is UNMEASURED for every series, never 0. A row naming a
    series the catalog does not hold is counted under `off_catalog` (the gauntlet will refuse it
    UNMEASURED on this host)."""
    names = [str(r["series"]) for r in cat.get("series") or []]
    src = {str(r["series"]): str(r["source"]) for r in cat.get("series") or []}
    exp = (exposure or {}).get("series") if isinstance(exposure, Mapping) else None
    per: dict[str, dict[str, Any]] = {}
    for n in names:
        organs = sorted(((exp or {}).get(n) or {}).get("organs") or {}) \
            if isinstance(exp, Mapping) else []
        per[n] = {"source": src[n], "generators_seeing": organs,
                  "rows": 0, "testable_rows": 0,
                  "judged": 0 if judged is not None else UNMEASURED,
                  "certified": 0 if certified is not None else UNMEASURED,
                  "quality_unmeasured": 0}
    off: dict[str, int] = {}
    n_rows = 0
    for row in rows:
        s = series_of(row)
        if s is None:
            continue
        n_rows += 1
        if s not in per:
            off[s] = off.get(s, 0) + 1
            continue
        e = per[s]
        e["rows"] += 1
        q = _quality(row)
        if q in ("EXECUTABLE", "EXECUTABLE_VARIANT"):          # family_spec.TESTABLE
            e["testable_rows"] += 1
        elif q == UNMEASURED:
            e["quality_unmeasured"] += 1
        if judged is not None or certified is not None:
            cid = _cell(row)
            if cid and judged is not None and cid in judged:
                e["judged"] += 1
            if cid and certified is not None and cid in certified:
                e["certified"] += 1
    zero = sorted(n for n, e in per.items() if e["testable_rows"] == 0)
    by_source: dict[str, dict[str, int]] = {}
    for e in per.values():
        b = by_source.setdefault(e["source"], {"series": 0, "rows": 0, "testable_rows": 0})
        b["series"] += 1
        b["rows"] += e["rows"]
        b["testable_rows"] += e["testable_rows"]
    return {
        "status": cat.get("status", UNMEASURED), "why": cat.get("why"),
        "n_series": len(per), "n_sources": len(by_source),
        "n_alt_rows": n_rows,
        "n_series_seen_by_a_generator": (sum(1 for e in per.values() if e["generators_seeing"])
                                         if isinstance(exp, Mapping) else UNMEASURED),
        "n_series_with_testable_rows": sum(1 for e in per.values() if e["testable_rows"]),
        "zero_coverage_series": zero,
        "zero_coverage_sources": sorted(k for k, v in by_source.items()
                                        if v["testable_rows"] == 0),
        "by_source": by_source, "series": per, "off_catalog": off,
    }


# ----------------------------------------------------------------------- the prompt slice ---
def gap_series(prescriptions: Path | None = None, organ: str = "") -> set[str]:
    """Alt series the producer loop names as gap targets (its desk list, or the organ's own)."""
    d = _read(prescriptions or PRESCRIPTIONS)
    gt = d.get("gap_target") if isinstance(d, dict) else None
    if not isinstance(gt, dict):
        return set()
    own = gt.get(organ) if organ else None
    lists = [own] if isinstance(own, dict) else [v for v in gt.values() if isinstance(v, dict)]
    out: set[str] = set()
    for v in lists:
        a = v.get("alt_sources")
        if isinstance(a, list):
            out |= {str(x) for x in a}
    return out


def tested_counts(funnel: Path | None = None) -> dict[str, int]:
    """testable_rows per series from the last FUNNEL.json `by_alt_source`; {} when unread."""
    d = _read(funnel or FUNNEL)
    b = d.get("by_alt_source") if isinstance(d, dict) else None
    ser = b.get("series") if isinstance(b, dict) else None
    if not isinstance(ser, dict):
        return {}
    return {str(k): int(v.get("testable_rows") or 0) for k, v in ser.items()
            if isinstance(v, dict) and isinstance(v.get("testable_rows"), int)}


def choose(cat: Mapping[str, Any], *, k: int = PROMPT_K, tested: Mapping[str, int] | None = None,
           gaps: set[str] | None = None, seed: str = "",
           explore_share: float = EXPLORE_SHARE) -> list[dict[str, Any]]:
    """k catalog rows (with at least one spec): (1 - explore_share) gap-weighted without
    replacement -- weight 1/(1+testable rows), x GAP_BOOST for a gap target -- and the rest
    uniform over what is left. Deterministic in `seed`, so a pass is replayable."""
    pool = [r for r in cat.get("series") or [] if r.get("specs")]
    if not pool or k <= 0:
        return []
    rng = random.Random(hashlib.sha256(seed.encode()).hexdigest())  # noqa: S311 -- replayable rotation, not security
    tested = tested or {}
    gaps = gaps or set()
    n_explore = round(k * max(0.0, min(1.0, explore_share)))
    n_gap = max(0, min(len(pool), k) - n_explore)
    left = list(pool)
    out: list[dict[str, Any]] = []
    for _ in range(n_gap):
        if not left:
            break
        w = [(GAP_BOOST if (r["series"] in gaps or r["source"] in gaps) else 1.0)
             / (1.0 + max(0, int(tested.get(r["series"], 0)))) for r in left]
        x = rng.random() * sum(w)
        acc = 0.0
        for i, wi in enumerate(w):
            acc += wi
            if x <= acc:
                out.append(left.pop(i))
                break
        else:
            out.append(left.pop())
    rng.shuffle(left)
    out += left[:max(0, k - len(out))]
    return out


def families() -> list[str]:
    try:
        import miner_candidate_compiler as mcc
        fams = sorted(f for f in mcc._FAMILY_VOCAB if f not in ("calendar_month",))
        return fams or list(DEFAULT_FAMILIES)
    except Exception:
        return list(DEFAULT_FAMILIES)


def record_exposure(organ: str, series: Iterable[str], *, path: Path | None = None,
                    now: datetime | None = None) -> None:
    """Which generator was SHOWN which series, and when (the `generators_seeing` measurement)."""
    p = path or EXPOSURE
    doc = read_exposure(p)
    at = (now or _now()).isoformat(timespec="seconds")
    ser = doc.setdefault("series", {})
    for s in series:
        e = ser.setdefault(str(s), {"organs": {}})
        o = e["organs"].setdefault(organ, {"shown": 0, "last": ""})
        o["shown"] = int(o.get("shown") or 0) + 1
        o["last"] = at
    og = doc.setdefault("organs", {}).setdefault(organ, {"prompts": 0, "last": ""})
    og["prompts"] = int(og.get("prompts") or 0) + 1
    og["last"] = at
    doc["rule"] = ("append-only counters of which free-model generator's prompt carried which "
                   "alt series; read by research/funnel.py by_alt_source.generators_seeing")
    with contextlib.suppress(OSError):
        _atomic(p, doc)


def prompt_block(organ: str, *, k: int = PROMPT_K, lake: Path | None = None,
                 now: datetime | None = None, record: bool = True,
                 cat: Mapping[str, Any] | None = None) -> str:
    """The block a generator appends to its prompt, or "" when no executable series is on this
    host (an absent lake is not a reason to send the model a list it cannot be tested on)."""
    cat = cat if cat is not None else catalog(lake)     # PIT z columns only: see catalog()
    now = now or _now()
    picked = choose(cat, k=k, tested=tested_counts(), gaps=gap_series(organ=organ),
                    seed=f"{organ}|{now:%Y-%m-%dT%H}")
    if not picked:
        return ""
    if record:
        record_exposure(organ, [r["series"] for r in picked], now=now)
    lines = [
        "ALT DATA THE GAUNTLET CAN TEST (point-in-time lake series on this desk). A conditioner "
        "keeps a family's signal only on bars where the series condition held at that bar "
        "(lagged one publication day). Spec syntax, exactly: "
        "alt:<series>:<column>:<gt|lt>:<threshold>. Use ONLY the specs listed:",
    ]
    for r in picked:
        tag = f" (instrument {r['symbol']})" if r.get("symbol") else ""
        lines.append(f"  - {r['series']} [source {r['source']}]{tag}: "
                     + ", ".join(r["specs"][:4]))
    lines += [
        "Families a conditioner may ride on: " + ", ".join(families()) + ".",
        "For each alt-conditioned hypothesis with an economic reason the series should gate "
        "the family on that instrument, output ONE line, exactly:",
        "ALT_CELL | <family> | <MT5 SYMBOL, e.g. EURUSD, XAUUSD, US500; no share CFDs> | "
        "<one alt: spec from the list> | <mechanism: who is forced to trade, and why>",
        "Prefer series from DIFFERENT sources: two cells on one source are one idea.",
    ]
    return "\n".join(lines)


def parse_cells(text: str, *, cat: Mapping[str, Any] | None = None, organ: str = "",
                universe: set[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """(donation rows, rejection reasons) from a reply's ALT_CELL lines.

    A row is kept only when the spec parses, names a catalog series and column, and the family is
    one the block offered. The row is the compiler's EXACT_RECIPE shape: family + params +
    symbols; the gauntlet then applies the conditioner exactly as written."""
    allowed = set(families())
    found = {str(r["series"]): r for r in (cat or {}).get("series") or []
             if r.get("discovered_by")} if cat is not None else {}
    known = {str(r["series"]): set(r.get("columns") or []) for r in (cat or {}).get("series")
             or []} if cat is not None else None
    rows: list[dict[str, Any]] = []
    why: list[str] = []
    for ln in (text or "").splitlines():
        if not CELL_LINE.match(ln):
            continue
        if len(rows) >= MAX_CELLS:
            why.append("over MAX_CELLS")
            break
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 5:
            why.append(f"malformed: {ln[:80]}")
            continue
        fam, sym, cond, mech = parts[1], parts[2].upper(), parts[3], " | ".join(parts[4:])
        got = parse_spec(cond)
        if got is None:
            why.append(f"not an alt: spec: {cond[:60]}")
            continue
        if fam not in allowed:
            why.append(f"family not offered: {fam[:40]}")
            continue
        if not re.fullmatch(r"[A-Z0-9.]{3,12}", sym):
            why.append(f"not a symbol: {sym[:20]}")
            continue
        if universe is not None and sym not in universe:
            why.append(f"symbol outside the universe: {sym}")
            continue
        if known is not None and (got[0] not in known or got[1] not in known[got[0]]):
            why.append(f"series/column not in the catalog: {got[0]}.{got[1]}")
            continue
        if len(mech) < 12:
            why.append("no mechanism stated")
            continue
        canon = spec(*got)
        rows.append({"kind": "hypothesis", "family": fam, "symbols": [sym],
                     "params": {"conditioner": canon},
                     "title": f"{fam} on {sym} conditioned on {got[0]}.{got[1]} {got[2]} "
                              f"{got[3]:g}"[:300],
                     "mechanism": mech[:600], "text": mech[:600],
                     "alt_series": got[0], "alt_source": source_of(got[0]),
                     "alt_catalog_organ": organ,
                     # The series' DATA was found by a free model: credit it per method.
                     **({"discovered_by": found[got[0]]["discovered_by"],
                         "method": found[got[0]]["method"]} if got[0] in found else {})})
    return rows, why
