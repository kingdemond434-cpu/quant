#!/usr/bin/env python3
"""WORLD CELLS -- every published world series used three ways: direct, indirect, allocation.

THE PRINCIPAL'S RULE FOR THE WORLD FACTORY (2026-09-30). "Every alt, macro or intelligence dataset
must feed (a) DIRECT cells via new families, (b) INDIRECT cells -- conditioning, regime filters and
interactions on existing families -- and (c) ALLOCATION intelligence, as state inputs written as
an artifact." Before this organ an acquired alt series (`data/acquired/*.parquet`) was executable
only as an `ext_<name>` primitive of the banned `discovered` family, and an ALFRED vintage file
(`data/lake/alfred/*.parquet`) was read by nothing on a clock. Both were datasets feeding no
producer.

WHAT IT DOES, per pass (inside leg `world_factory`, before the measurement):

  1. PUBLISH. Every PIT-authoritative acquired series of an `alt_dataset_sources.json` row, and
     every ALFRED vintage file, is written as ONE lake frame
     `data/lake/series/<source>.parquet` carrying an `available_time` column: for alt rows, the
     period date plus the row's declared `publication_lag_s`; for ALFRED, the vintage's
     realtime date plus one day. That frame is exactly what `family_exogenous_conditioner`
     already loads, so no new loader and no new join exists. A series without PIT authority is
     WITHHELD and counted with the certifier's reasons; nothing is published on a guess.
  2. DIRECT cells: `exogenous_conditioner` over (signal x transform x instrument x chart), for the
     MT5 instruments the source row maps to -- through `libs.moat.registry.enqueue_candidate`,
     the one door `pack_cells` also uses.
  3. INDIRECT cells: `exogenous_gate` -- every wrappable price-only base family on the same
     instrument, kept only while the series sits in a band. Minted in a rotating order, a pass at
     a time; the minted set is remembered, so a cell is enqueued ONCE and the census is charged
     once, never hourly.
  4. ALLOCATION: `reports/WORLD_STATE_INPUTS.json`, the current lagged z of every published
     series, per instrument it maps to. ADVISORY: the allocator is sealed and is not edited; this
     is a state input it may read, stamped with its age.
  5. DONATE. Every cell minted this pass is ALSO donated through
     `data/intelligence/world_cells/discoveries_*.json` (`proposer_common.donate`, the door every
     seat uses), with `tests_run` = the cells minted, so each one is charged. The gauntlet
     never opens the SQLite registry: the moat exchange leases the best-SCORED rows (these
     carry no score) and `libs.moat.docket_feed` carries the bare registry cell, never through
     the compiler and never charged. The donation is the compiler's own door, the same one
     every seat uses. The registry row is written `claimed` by this organ so no second door
     offers it again; a cell whose donation is refused stays out of the minted set and is
     re-offered next pass, never lost.

Nothing here sizes, vetoes or shrinks. UNMEASURED is never zero: a source not yet acquired is
listed as NOT_PUBLISHED with its reason, not as a source with zero cells.

    python research/world_cells.py              # publish, mint, write both artifacts
    python research/world_cells.py --dry-run    # count what would be minted, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
LAKE = DESK / "data" / "lake" / "series"
ALFRED_DIR = DESK / "data" / "lake" / "alfred"
ALT_SOURCES = DESK / "data" / "alt_dataset_sources.json"
ACQUIRED = DESK / "data" / "acquired" / "registry.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
CURSOR = DESK / "data" / "world_cells_cursor.json"
CELLS_REPORT = DESK / "reports" / "WORLD_CELLS.json"
STATE_REPORT = DESK / "reports" / "WORLD_STATE_INPUTS.json"
#: WHO READS WORLD_STATE_INPUTS, said as it is (audit of PR #123, 2026-09-30). The allocation
#: consumer of a world state input is the allocator's context (`pf_allocator` via
#: `libs.portfolio.macro_state`), which this organ may not edit; the reader is staged as a patch
#: and this label says so until it lands. It is NOT a claim that the file is wired. The dataset
#: exploitation fence (CRO D18) reads this field.
STATE_CONSUMER = "PENDING_PATCH /mnt/project-files/patches/world_state_inputs_allocator/"

GENERATOR = "world_cells"
CHARTS: tuple[str, ...] = ("H1", "H4", "D1")
TRANSFORMS: tuple[str, ...] = ("level_z", "delta", "delta_z")
#: Signals of one source minted as direct cells. A source rarely has more; the rest are the
#: acquirer's derived columns of the same statistic.
SIGNALS_PER_SOURCE = 6
#: Gate shape of the indirect cells. `calm` is the regime a mean-reverting base may need; `high` /
#: `low` the one-sided extremes. One threshold: the family's own grid is not re-searched here.
GATE_BANDS: tuple[str, ...] = ("high", "low", "calm")
GATE_THRESHOLD = 1.0
GATE_CHART = "H1"
#: NEW indirect cells enqueued per pass. PACING, never a ceiling: the enumeration resumes from
#: the minted set next hour, so every (source, base, instrument, band) is reached in turn.
GATE_CELLS_PER_PASS = 1_000

#: The instruments US macro vintages condition. Each is checked against the universe and the
#: two-lane policy before a cell is minted on it.
ALFRED_TARGETS: tuple[str, ...] = ("USDX", "EURUSD", "USDJPY", "XAUUSD", "US500", "UST10Y")
#: ALFRED stamps a vintage with its release DATE. The release is intraday US time, so the value
#: is made available at the start of the NEXT UTC day, and the family lags it a further day.
ALFRED_AVAILABLE_AFTER = timedelta(days=1)

#: CULTURE PROVENANCE (principal, 2026-09-30 14:18): every cell carries these three keys, named
#: exactly so. `libs/research/cell_culture.py` will own the schema; until it lands the plain keys
#: are emitted, on the registry row when it has the columns and always in WORLD_CELLS.json.
CULTURE_KEYS: tuple[str, ...] = ("source_culture", "participant_structure",
                                 "failure_mode_hypothesis")
PARTICIPANT_STRUCTURES: frozenset[str] = frozenset({
    "retail_heavy", "institutional", "tax_driven", "policy_driven", "settlement_constrained",
    "physical_flow", "broker_specific", "mixed", UNMEASURED})
ALFRED_CULTURE: dict[str, str] = {
    "source_culture": "US",
    "participant_structure": "policy_driven",
    "failure_mode_hypothesis": (
        "a US first print is what the Fed and rates desks react to on the day, and the "
        "revised series every Western backtest reads is not, so the first-print version "
        "fails at benchmark revisions and policy pivots rather than when the revised "
        "macro signal does")}


def culture_of(row: Mapping[str, Any]) -> dict[str, str]:
    """The three culture keys of a source row: declared on the row, else the jurisdiction from its
    region, else UNMEASURED. Never guessed from the instrument."""
    out: dict[str, str] = {}
    region = str(row.get("region") or "").strip()
    declared = str(row.get("source_culture") or "").strip()
    out["source_culture"] = declared or (region.upper() if region else UNMEASURED)
    ps = str(row.get("participant_structure") or "").strip()
    out["participant_structure"] = ps if ps in PARTICIPANT_STRUCTURES else UNMEASURED
    out["failure_mode_hypothesis"] = (str(row.get("failure_mode_hypothesis") or "").strip()
                                      or UNMEASURED)
    return out


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


# ----------------------------------------------------------------------------------- targets
def _universe(path: Path | None = None) -> set[str]:
    doc = _read_json(path or UNIVERSE)
    return set(doc) if isinstance(doc, dict) else set()


def admissible_targets(symbols: Iterable[str], family: str,
                       universe: set[str] | None = None) -> list[str]:
    """Symbols in the MT5 universe that the two-lane policy lets `family` hypothesise on."""
    uni = _universe() if universe is None else universe
    try:
        from universe_policy import may_hypothesise
    except Exception:                                     # noqa: BLE001
        def may_hypothesise(symbol: str, family: object = None) -> bool:   # type: ignore[misc]
            return False
    out: list[str] = []
    for s in symbols:
        s = str(s)
        if s in uni and s not in out:
            try:
                ok = bool(may_hypothesise(s, family))
            except Exception:                             # noqa: BLE001
                ok = False
            if ok:
                out.append(s)
    return out


# ----------------------------------------------------------------------------------- publish
def _template_regex(template: str) -> re.Pattern[str]:
    parts = re.split(r"(\{[a-z_]+\})", template)
    return re.compile("^" + "".join("[^&]*" if p.startswith("{") and p.endswith("}")
                                    else re.escape(p) for p in parts) + "$")


def acquired_for_row(row: Mapping[str, Any], reg: Mapping[str, Any]
                     ) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    """(authoritative series of this row, withheld series -> the certifier's blocking reasons)."""
    url = str(row.get("url") or "")
    if not url:
        return {}, {}
    pat = _template_regex(url)
    ok: dict[str, dict[str, Any]] = {}
    withheld: dict[str, list[str]] = {}
    for name, meta in (reg.get("series") or {}).items():
        if not isinstance(meta, dict) or not pat.match(str(meta.get("url") or "")):
            continue
        if meta.get("pit_authority") is True:
            ok[str(name)] = meta
        else:
            withheld[str(name)] = [str(b) for b in (meta.get("pit_blocking") or ["no certificate"])]
    return ok, withheld


def alt_frame(row: Mapping[str, Any], series: Mapping[str, Mapping[str, Any]]) -> pd.DataFrame | None:
    """The row's authoritative series as one frame on its own `available_time` clock."""
    cols: dict[str, pd.Series] = {}
    for name, meta in sorted(series.items()):
        try:
            df = pd.read_parquet(str(meta["path"]))
            s = pd.to_numeric(df["value"], errors="coerce")
            s.index = pd.to_datetime(df.index, errors="coerce", utc=True)
        except Exception:                                 # noqa: BLE001
            continue
        s = s[s.index.notna()].dropna()
        if not s.empty:
            cols[re.sub(r"[^A-Za-z0-9_]+", "_", name)[:60]] = s[~s.index.duplicated(keep="last")]
    if not cols:
        return None
    frame = pd.DataFrame(cols).sort_index()
    lag = float(row.get("publication_lag_s") or 0.0)
    if lag <= 0:
        return None      # no declared publication lag means no honest available_time
    frame["event_time"] = frame.index
    frame["available_time"] = frame.index + pd.Timedelta(seconds=lag)
    frame["source_id"] = str(row.get("id"))
    return frame.reset_index(drop=True)


def alfred_frame(df: pd.DataFrame, series_id: str) -> pd.DataFrame | None:
    """First prints and the revision of the prior period, on the vintage clock.

    `first_print` is the value of each observation as FIRST published; `revision_prior` is how far
    the previous observation had moved from its own first print by the day this one printed --
    the revision the market learned at the same release. Observations whose first print is the
    start of ALFRED's vintage record are dropped: their true first print is not observable, and a
    history stamped at the record start would be a backfill (see `fetch_alfred.release_lag`).
    """
    need = {"observation_date", "realtime_date", "value"}
    if df is None or df.empty or not need <= set(df.columns):
        return None
    d = df[list(need)].copy()
    d["observation_date"] = pd.to_datetime(d["observation_date"], errors="coerce")
    d["realtime_date"] = pd.to_datetime(d["realtime_date"], errors="coerce")
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    d = d.dropna().sort_values(["realtime_date", "observation_date"])
    if d.empty:
        return None
    start = d["realtime_date"].min()
    first = (d.sort_values("realtime_date").groupby("observation_date", as_index=False).head(1)
             .sort_values("observation_date").reset_index(drop=True))
    first = first[first["realtime_date"] > start + pd.Timedelta(days=7)].reset_index(drop=True)
    if first.empty:
        return None
    prev_obs = first["observation_date"].shift(1)
    probe = pd.DataFrame({"observation_date": prev_obs, "realtime_date": first["realtime_date"],
                          "i": range(len(first))}).dropna()
    rev = pd.Series(float("nan"), index=first.index)
    if not probe.empty:
        right = d.sort_values("realtime_date")
        joined = pd.merge_asof(probe.sort_values("realtime_date"), right,
                               on="realtime_date", by="observation_date", direction="backward")
        fp = first.set_index("observation_date")["value"]
        for _, r in joined.iterrows():
            base = fp.get(r["observation_date"])
            if base is not None and pd.notna(r["value"]):
                rev.iloc[int(r["i"])] = float(r["value"]) - float(base)
    out = pd.DataFrame({
        "first_print": first["value"].astype(float),
        "revision_prior": rev.astype(float),
        "event_time": pd.to_datetime(first["observation_date"]).dt.tz_localize(UTC),
        "available_time": (pd.to_datetime(first["realtime_date"]).dt.tz_localize(UTC)
                           + ALFRED_AVAILABLE_AFTER),
    })
    out["source_id"] = f"alfred_{series_id}"
    return out


def _write_frame(frame: pd.DataFrame, source: str, lake: Path) -> Path:
    lake.mkdir(parents=True, exist_ok=True)
    path = lake / f"{source}.parquet"
    tmp = path.with_suffix(".parquet.tmp")
    frame.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return path


def _signals(frame: pd.DataFrame) -> list[str]:
    from mt5desk.family_exogenous_conditioner import STAMP_COLUMNS
    return [c for c in frame.columns
            if c not in STAMP_COLUMNS and pd.api.types.is_numeric_dtype(frame[c])]


def pack_sources(lake: Path | None = None) -> list[dict[str, Any]]:
    """The data packs whose canonical frame is already in the lake (written by `asia_parser`).

    Their DIRECT cells belong to `pack_cells` and are not minted again here (the same params
    would only bump the registry's search count). What they lacked was the INDIRECT and the
    ALLOCATION use, which this adds. Culture is the pack's own declared country.
    """
    try:
        import pack_cells as pc
    except Exception:                                     # noqa: BLE001
        return [{"source": "packs_*", "kind": "pack", "status": "NOT_PUBLISHED",
                 "reason": f"{UNMEASURED}: pack_cells unimportable", "targets": [],
                 "consumers": []}]
    base = lake or LAKE
    out: list[dict[str, Any]] = []
    for pack in pc.packs():
        pid = str(pack.get("id"))
        path = next((base / f"{pid}{s}" for s in (".parquet", ".csv")
                     if (base / f"{pid}{s}").exists()), None)
        country = str(pack.get("country") or "").strip()
        rec: dict[str, Any] = {
            "source": pid, "kind": "pack", "class": str(pack.get("plane") or "data_pack"),
            "targets": pc.targets_of(pack), "direct_owner": "pack_cells",
            "consumers": ["exogenous_gate", "WORLD_STATE_INPUTS"],
            **culture_of({"region": country,
                          "participant_structure": pack.get("participant_structure"),
                          "failure_mode_hypothesis": pack.get("failure_mode_hypothesis")})}
        if path is None:
            rec.update(status="NOT_PUBLISHED", reason="no canonical frame in the lake yet")
            out.append(rec)
            continue
        sigs, n, why = pc.signals_of(path)
        if not sigs:
            rec.update(status="NOT_PUBLISHED", reason=why or "no signal column")
            out.append(rec)
            continue
        rec.update(status="PUBLISHED", signals=sigs, rows=int(n))
        out.append(rec)
    return out


def publish(*, alt_path: Path | None = None, acquired_path: Path | None = None,
            alfred_dir: Path | None = None, lake: Path | None = None,
            dry_run: bool = False, packs: bool = True) -> list[dict[str, Any]]:
    """Every source: PUBLISHED with its signals and targets, or NOT_PUBLISHED with the reason."""
    lake = lake or LAKE
    out: list[dict[str, Any]] = []
    rows = ((_read_json(alt_path or ALT_SOURCES) or {}).get("rows") or [])
    reg = _read_json(acquired_path or ACQUIRED)
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "")
        rec: dict[str, Any] = {"source": rid, "kind": "alt", "class": row.get("class"),
                               "targets": list(row.get("instruments") or []),
                               **culture_of(row),
                               "consumers": ["exogenous_conditioner", "exogenous_gate",
                                             "WORLD_STATE_INPUTS"]}
        if not row.get("fetch") or not row.get("keyless") or not row.get("machine_use_allowed"):
            rec.update(status="NOT_PUBLISHED",
                       reason=f"not fetchable: {row.get('blocker') or 'keyed or not machine-use'}")
            out.append(rec)
            continue
        if not isinstance(reg, dict):
            rec.update(status="NOT_PUBLISHED", reason=f"{UNMEASURED}: no acquired registry")
            out.append(rec)
            continue
        ok, withheld = acquired_for_row(row, reg)
        rec["withheld"] = {k: v[:3] for k, v in withheld.items()}
        if not ok:
            rec.update(status="NOT_PUBLISHED",
                       reason=("acquired but withheld: no PIT authority" if withheld
                               else "not yet acquired by acquire_datasets"))
            out.append(rec)
            continue
        frame = alt_frame(row, ok)
        if frame is None:
            rec.update(status="NOT_PUBLISHED",
                       reason="unreadable series or no declared publication lag")
            out.append(rec)
            continue
        if not dry_run:
            _write_frame(frame, rid, lake)
        rec.update(status="PUBLISHED", signals=_signals(frame), rows=int(len(frame)),
                   last_available=str(frame["available_time"].max()))
        out.append(rec)
    adir = alfred_dir or ALFRED_DIR
    files = sorted(adir.glob("*.parquet")) if adir.exists() else []
    if not files:
        out.append({"source": "alfred_*", "kind": "alfred", "status": "NOT_PUBLISHED",
                    "reason": (f"{UNMEASURED}: no ALFRED vintages on disk (fetch_alfred needs a "
                               "FRED key; reports/alfred_vintages.json says which)"),
                    "targets": list(ALFRED_TARGETS), "consumers": []})
    for f in files:
        sid = f.stem
        src = f"alfred_{sid}"
        rec = {"source": src, "kind": "alfred", "class": "macro_vintage",
               "targets": list(ALFRED_TARGETS), **ALFRED_CULTURE,
               "consumers": ["exogenous_conditioner", "exogenous_gate", "WORLD_STATE_INPUTS"]}
        try:
            frame = alfred_frame(pd.read_parquet(f), sid)
        except Exception as exc:                          # noqa: BLE001
            frame = None
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:80]}"
        if frame is None or frame.empty:
            rec.update(status="NOT_PUBLISHED", reason="no observable first prints")
            out.append(rec)
            continue
        if not dry_run:
            _write_frame(frame, src, lake)
        rec.update(status="PUBLISHED", signals=_signals(frame), rows=int(len(frame)),
                   last_available=str(frame["available_time"].max()))
        out.append(rec)
    if packs:
        out.extend(pack_sources(lake))
    return out


# -------------------------------------------------------------------------------------- mint
def _key(*parts: Any) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:14]


def gate_bases() -> list[str]:
    """Price-only families the gate can rebuild, minus the class-panel families (they need
    `symbol`, which a wrapper does not pass)."""
    try:
        from mt5desk.families import live_family_names
        from mt5desk.family_exogenous_gate import gateable
    except Exception:                                     # noqa: BLE001
        return []
    try:
        from mt5desk.families_cross_sectional import CROSS_SECTIONAL_FAMILIES
        xs = set(CROSS_SECTIONAL_FAMILIES)
    except Exception:                                     # noqa: BLE001
        xs = set()
    try:
        from mt5desk.families_orthogonal import FAMILY_INPUTS
    except Exception:                                     # noqa: BLE001
        FAMILY_INPUTS = {}

    def _price_only(name: str) -> bool:
        # An orthogonal family declares its input; only "price only" rebuilds from bars alone
        # (`correlation_regime` needs a peer, `calendar_month` a source-named month). Families
        # outside that dict are the decorated/hunt16 populations, all bar-built.
        inp = FAMILY_INPUTS.get(name)
        return inp is None or str(inp[0]).startswith("price only")

    return sorted(f for f in live_family_names()
                  if f not in xs and gateable(f) and _price_only(f))


Enqueue = Callable[..., tuple[str, bool]]


def _registry_door() -> tuple[Enqueue, Callable[..., tuple[str, bool]]]:
    from libs.moat.registry import enqueue_candidate, record_discovery
    return enqueue_candidate, record_discovery


def donation_row(*, cid: str, family: str, symbol: str, params: Mapping[str, Any],
                 chart: str, mechanism: str, falsifier: str,
                 common: Mapping[str, Any]) -> dict[str, Any]:
    """One minted cell in the shape the compiler's EXACT_RECIPE door reads (family + params +
    symbol). A chart other than H1 rides in `params.timeframe`, the desk-wide spelling the
    gauntlet reads (`external_gauntlet.timeframe_of`; H1 by absence), so the compiler keeps the
    chart the cell was minted on instead of re-expanding it."""
    p = dict(params)
    if chart and chart != "H1":
        p["timeframe"] = chart
    return {"source": GENERATOR, "kind": "world_cell", "symbol": symbol, "family": family,
            "params": p, "mechanism": mechanism, "falsifier": falsifier, "chart": chart,
            "title": f"{symbol} {family} on {common.get('source_id')} ({chart})",
            "url": f"world_cells://{common.get('source_id')}",
            "candidate_id": cid, "discovery_id": common.get("discovery_id"),
            "source_id": common.get("source_id"), "pit_status": common.get("pit_status"),
            "required_data": list(common.get("required_data") or []),
            **{k: str(common.get(k) or UNMEASURED) for k in CULTURE_KEYS},
            "evidence": {"candidate_id": cid, "screen": "none: minted, never pre-screened; the "
                                                        "gauntlet is the only judge"}}


def mint(published: list[dict[str, Any]], *, minted: set[str], bases: list[str],
         universe: set[str] | None = None, dry_run: bool = False,
         gate_cap: int = GATE_CELLS_PER_PASS,
         door: tuple[Enqueue, Callable[..., tuple[str, bool]]] | None = None,
         pending: list[tuple[str, dict[str, Any]]] | None = None
         ) -> dict[str, Any]:
    """Direct then indirect cells for every PUBLISHED source; each cell enqueued once, ever.

    With `pending` given (the produce path), a minted cell is NOT added to `minted` here: it is
    appended to `pending` with its donation row, and `produce` adds it to `minted` only once its
    donation was written. The registry row is then enqueued `claimed` by this organ."""
    claim: dict[str, Any] = ({} if pending is None else
                             {"status": "claimed", "claimed_by": GENERATOR,
                              "claimed_at": _iso(_now())})
    stats: dict[str, Any] = {"direct": {"minted": 0, "created": 0, "already": 0},
                             "indirect": {"minted": 0, "created": 0, "already": 0,
                                          "deferred_to_next_pass": 0},
                             "errors": [], "by_source": {}}
    if dry_run:
        enqueue = record = None
    else:
        try:
            enqueue, record = door or _registry_door()
        except Exception as exc:                          # noqa: BLE001
            stats["errors"].append(f"registry door: {type(exc).__name__}: {str(exc)[:80]}")
            return stats
    gates_left = int(gate_cap)
    for src in published:
        if src.get("status") != "PUBLISHED":
            continue
        sid = str(src["source"])
        sigs = list(src.get("signals") or [])[:SIGNALS_PER_SOURCE]
        d_targets = admissible_targets(src.get("targets") or [], "exogenous_conditioner",
                                       universe)
        g_targets = admissible_targets(src.get("targets") or [], "exogenous_gate", universe)
        per = {"direct": 0, "indirect": 0, "targets": d_targets,
               **{k: str(src.get(k) or UNMEASURED) for k in CULTURE_KEYS}}
        stats["by_source"][sid] = per
        mech = (f"{sid} is published world information on its own clock: while its series is at "
                f"an extreme, {', '.join(d_targets) or 'its instruments'} trade differently")
        did = ""
        if record is not None and (d_targets or g_targets):
            try:
                did, _ = record(source_id=sid, source_type="world_dataset", mechanism=mech,
                                origin="world_factory", generator=GENERATOR,
                                assets=list(d_targets or g_targets), exact_rule_if_known="",
                                horizons=list(CHARTS),
                                note="world factory: direct and indirect cells per series")
            except Exception as exc:                      # noqa: BLE001
                stats["errors"].append(f"{sid}: record_discovery {type(exc).__name__}")
        common = {"origin": "world_factory", "generator": GENERATOR, "department": "information",
                  "source_id": sid, "discovery_id": did or None, "pit_status": "STAMPED",
                  "required_data": [f"desks/mt5/data/lake/series/{sid}.parquet"],
                  "causal_rationale": mech,
                  **{k: str(src.get(k) or UNMEASURED) for k in CULTURE_KEYS}}
        for sig in (sigs if not src.get("direct_owner") else []):
            for tf in TRANSFORMS:
                for sym in d_targets:
                    for chart in CHARTS:
                        k = _key("d", sid, sig, tf, sym, chart)
                        if k in minted:
                            stats["direct"]["already"] += 1
                            continue
                        stats["direct"]["minted"] += 1
                        per["direct"] += 1
                        if enqueue is None:
                            continue
                        try:
                            dparams = {"source": sid, "signal": sig, "transform": tf}
                            dfals = (f"the {tf} of {sid}.{sig} has no measurable relation "
                                     f"to {sym} at {chart} out of sample")
                            _cid, new = enqueue(
                                family="exogenous_conditioner", symbol=sym,
                                params=dparams,
                                mechanism=mech, chart=chart, horizon=chart, asset_class="",
                                transformation="world_series",
                                falsifier=dfals, **common, **claim)
                            stats["direct"]["created"] += int(bool(new))
                            if pending is None:
                                minted.add(k)
                            else:
                                pending.append((k, donation_row(
                                    cid=str(_cid), family="exogenous_conditioner", symbol=sym,
                                    params=dparams, chart=chart, mechanism=mech,
                                    falsifier=dfals, common=common)))
                        except Exception as exc:          # noqa: BLE001
                            stats["errors"].append(f"{sid}/{sig}/{sym}: {type(exc).__name__}")
        # INDIRECT: the first signal gates every base family; further signals follow once the
        # first is exhausted, so breadth across sources comes before depth within one.
        for sig in sigs:
            for base in bases:
                for sym in g_targets:
                    for band in GATE_BANDS:
                        k = _key("g", sid, sig, base, sym, band)
                        if k in minted:
                            stats["indirect"]["already"] += 1
                            continue
                        if gates_left <= 0:
                            stats["indirect"]["deferred_to_next_pass"] += 1
                            continue
                        gates_left -= 1
                        stats["indirect"]["minted"] += 1
                        per["indirect"] += 1
                        if enqueue is None:
                            continue
                        try:
                            gparams = {"base_family": base, "base_params": {}, "source": sid,
                                       "signal": sig, "transform": "level_z",
                                       "threshold": GATE_THRESHOLD, "band": band}
                            gmech = (f"{base} on {sym} behaves differently while "
                                     f"{sid}.{sig} is {band}")
                            gfals = (f"{base} on {sym} gated to {sid}.{sig} {band} is no "
                                     "better than the ungated base out of sample")
                            _cid, new = enqueue(
                                family="exogenous_gate", symbol=sym, params=gparams,
                                mechanism=gmech,
                                chart=GATE_CHART, horizon=GATE_CHART, asset_class="",
                                transformation="world_series_gate",
                                falsifier=gfals, **common, **claim)
                            stats["indirect"]["created"] += int(bool(new))
                            if pending is None:
                                minted.add(k)
                            else:
                                pending.append((k, donation_row(
                                    cid=str(_cid), family="exogenous_gate", symbol=sym,
                                    params=gparams, chart=GATE_CHART, mechanism=gmech,
                                    falsifier=gfals, common=common)))
                        except Exception as exc:          # noqa: BLE001
                            stats["errors"].append(f"{sid}/{base}/{sym}: {type(exc).__name__}")
    stats["errors"] = stats["errors"][:20]
    return stats


# -------------------------------------------------------------------------------- allocation
def state_inputs(published: list[dict[str, Any]], now: datetime, *,
                 lake: Path | None = None) -> dict[str, Any]:
    """The current lagged z of every published series, per instrument it maps to. ADVISORY."""
    from mt5desk.family_exogenous_conditioner import conditioner
    per_series: list[dict[str, Any]] = []
    by_instrument: dict[str, list[dict[str, Any]]] = {}
    for src in published:
        if src.get("status") != "PUBLISHED":
            continue
        for sig in list(src.get("signals") or [])[:SIGNALS_PER_SOURCE]:
            cond = conditioner(str(src["source"]), sig, "level_z", root=lake or LAKE)
            if cond is None or cond.empty:
                z, at = UNMEASURED, None
            else:
                known = cond[cond.index <= pd.Timestamp(now)]
                if known.empty:
                    z, at = UNMEASURED, None
                else:
                    z, at = round(float(known.iloc[-1]), 4), known.index[-1]
            age_h = (round((now - at.to_pydatetime()).total_seconds() / 3600, 1)
                     if at is not None else UNMEASURED)
            row = {"source": src["source"], "signal": sig, "z_lagged": z,
                   "usable_since": str(at) if at is not None else None, "age_h": age_h,
                   "instruments": list(src.get("targets") or [])}
            per_series.append(row)
            for sym in row["instruments"]:
                by_instrument.setdefault(sym, []).append(
                    {"source": src["source"], "signal": sig, "z_lagged": z, "age_h": age_h})
    return {"generated_at": _iso(now), "advisory": True,
            "consumer": STATE_CONSUMER, "wired": False,
            "rule": ("state inputs the allocator MAY read; nothing here is read by the sealed "
                     "allocator today and nothing here sizes anything. z is the series' own "
                     "level z-score, lagged one publication day on its available_time clock. "
                     "`consumer` names the staged reader; `wired` turns true only when it lands"),
            "series": per_series, "by_instrument": by_instrument,
            "n_series": len(per_series), "n_instruments": len(by_instrument)}


# --------------------------------------------------------------------------------------- run
Donor = Callable[[list[dict[str, Any]], int], tuple[Any, dict[str, Any]]]


def _intake_donor(cands: list[dict[str, Any]], tests_run: int) -> tuple[Any, dict[str, Any]]:
    from research import proposer_common as pc
    # The registry rows were written by `mint` (claimed, with falsifier and culture keys); the
    # donation door must not enqueue them a second time.
    path = pc.donate(GENERATOR, cands, tests_run, record_in_registry=False)
    return path, pc.donation_counts()


def donate_cells(pending: list[tuple[str, dict[str, Any]]], minted: set[str], *,
                 donor: Donor | None = None) -> dict[str, Any]:
    """Donate this pass's minted cells to the intake the compiler reads, charging one test per
    cell. A cell enters `minted` only when its donation file was written, so a refused or failed
    donation is re-offered next pass rather than lost (the registry dedups its re-enqueue)."""
    if not pending:
        return {"status": "NOTHING_MINTED", "donated": 0, "tests_run": 0}
    cands = [c for _, c in pending]
    try:
        path, counts = (donor or _intake_donor)(cands, len(cands))
    except Exception as exc:                              # noqa: BLE001
        return {"status": "FAILED", "why": f"{type(exc).__name__}: {str(exc)[:160]}",
                "tests_run": len(cands), "donated": 0, "carried_to_next_pass": len(cands)}
    if not path:
        return {"status": "REFUSED", "tests_run": len(cands), "donated": 0,
                "carried_to_next_pass": len(cands),
                "why": "the donation door wrote no file; every cell is re-offered next pass",
                "counts": {k: counts.get(k) for k in ("refused_unstamped", "refused_wrong_lane")}}
    for k, _ in pending:
        minted.add(k)
    return {"status": "DONATED", "path": str(path), "tests_run": len(cands),
            "donated": int(counts.get("donated") or 0),
            "refused_unstamped": int(counts.get("refused_unstamped") or 0),
            "refused_wrong_lane": int(counts.get("refused_wrong_lane") or 0),
            "consumer": ("desks/mt5/research/miner_candidate_compiler.py (EXACT_RECIPE) -> "
                         "data/hypotheses docket -> external_gauntlet")}


def produce(*, now: datetime | None = None, dry_run: bool = False,
            door: tuple[Enqueue, Callable[..., tuple[str, bool]]] | None = None,
            paths: Mapping[str, Any] | None = None,
            donor: Donor | None = None) -> dict[str, Any]:
    now = now or _now()
    p = dict(paths or {})
    lake = p.get("lake", LAKE)
    cursor_path = p.get("cursor", CURSOR)
    published = publish(alt_path=p.get("alt"), acquired_path=p.get("acquired"),
                        alfred_dir=p.get("alfred"), lake=lake, dry_run=dry_run,
                        packs=bool(p.get("packs", True)))
    cur = _read_json(cursor_path) or {}
    minted = set(cur.get("minted") or [])
    bases = gate_bases()
    pending: list[tuple[str, dict[str, Any]]] = []
    stats = mint(published, minted=minted, bases=bases, dry_run=dry_run,
                 universe=_universe(p["universe"]) if "universe" in p else None, door=door,
                 pending=None if dry_run else pending)
    stats["donation"] = ({"status": "DRY_RUN"} if dry_run else
                         donate_cells(pending, minted, donor=donor))
    if not dry_run:
        _atomic_json(cursor_path, {"updated_at": _iso(now), "minted": sorted(minted)})
    n_pub = sum(1 for s in published if s.get("status") == "PUBLISHED")
    doc = {
        "generated_at": _iso(now), "generator": GENERATOR, "dry_run": dry_run,
        "sources": published,
        "published": n_pub,
        "not_published": [{"source": s["source"], "reason": s.get("reason")}
                          for s in published if s.get("status") != "PUBLISHED"],
        "gate_bases": len(bases),
        "cells": stats,
        "rule": ("direct = exogenous_conditioner, indirect = exogenous_gate on price-only bases, "
                 "allocation = reports/WORLD_STATE_INPUTS.json (advisory). A cell is enqueued "
                 "once; `already` counts cells minted on an earlier pass, never re-charged. "
                 "Every minted cell is donated to data/intelligence/world_cells/ with "
                 "tests_run = cells minted, which is its road to the docket and the gauntlet"),
    }
    if not dry_run:
        _atomic_json(p.get("report", CELLS_REPORT), doc)
        _atomic_json(p.get("state", STATE_REPORT), state_inputs(published, now, lake=lake))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = produce(dry_run=a.dry_run)
    c = doc["cells"]
    print(f"world_cells: {doc['published']} published, {len(doc['not_published'])} not; "
          f"direct {c['direct']['minted']} new ({c['direct']['created']} created), "
          f"indirect {c['indirect']['minted']} new ({c['indirect']['created']} created, "
          f"{c['indirect']['deferred_to_next_pass']} next pass), bases {doc['gate_bases']}; "
          f"donation {c['donation'].get('status')} ({c['donation'].get('donated', 0)} rows, "
          f"{c['donation'].get('tests_run', 0)} tests charged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
