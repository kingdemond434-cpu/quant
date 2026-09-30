"""THE WORLD DATA OS'S ONE RECORD PER SOURCE, AND ACQUISITION GAIN SCORED ON GATE YIELD (Tier S
layer 2, the half `bitemporal.py` did not close).

THREE LEDGERS DESCRIBE THE SAME SOURCES AND NEVER MEET.

    data_registry.json          what a source IS: lifecycle, provenance, path, declared series
    ingestion_ledger.jsonl      what the desk INGESTED from it: units, PIT stamps, dispositions,
                                downstream states (`desks/mt5/research/ingestion_ledger.py`)
    data/vintages/<series>.jsonl  what the desk KNEW WHEN: the revision log (libs/research/vintage)

`source_records()` joins them into ONE record per source. The join is declared, never guessed
silently: every attachment carries its `basis` (exact name, declared path, declared series, or the
leading name token), and a side with no counterpart is UNMEASURED with the reason on the record --
a registry entry nothing ingested, an ingested dataset the registry never declared, a vintage log
no registry entry names. Those three orphan kinds are the data OS's own defects and are counted.

GATE YIELD, NOT PIT SHARE. The acquisition ledger used to score a ranker's prediction by how much
the intelligence PIT share moved after the item landed. That rewards timestamps, not alpha. A
source earns its place by what the gates CERTIFY from the information it carries, so each source
is mapped to the information class the desk's own axis registry uses (`axis_registry
.classify_family` -> information_source: price_only, macro, positioning, carry, event, ...), and
its GATE YIELD is the pass share of the verdicts, in a trailing window, on families that read that
class of information. An acquisition's realised gain is the move in its class's gate yield. A class
no verdict in the window touched has no yield: UNMEASURED, never 0.0.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from libs.tiers.replay import parse_t

UNMEASURED = "UNMEASURED"
UNKNOWN = "UNKNOWN"
#: the trailing window a gate yield is measured over
YIELD_WINDOW_DAYS = 30

#: information class of a source, from its own name / path / kind tokens. ORDERED: the first rule
#: whose token set meets the source's tokens wins. The vocabulary is the axis registry's
#: `INFORMATION_SOURCES`, so a source's class and a family's class are the same word.
CLASS_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("carry", frozenset({"swap", "swaps", "carry", "financing", "rollover"})),
    ("positioning", frozenset({"cot", "tff", "disagg", "positioning", "crowding", "holdings",
                               "gld"})),
    ("event", frozenset({"news", "gdelt", "calendar", "event", "events", "claim", "claims",
                         "filing", "filings", "release", "releases", "speeches", "forest",
                         "intel", "normalized"})),
    ("macro", frozenset({"fred", "macro", "bis", "ecb", "boe", "alfred", "cpi", "rates",
                         "yield", "yields", "eer", "country", "customs", "vaults", "lbma",
                         "wgc", "goldhub", "axis", "glc"})),
    ("cross_asset", frozenset({"sge", "shfe", "cme", "gc", "futures", "benchmark"})),
    ("microstructure", frozenset({"tape", "tick", "ticks", "depth", "fill", "fills", "spread",
                                  "cost", "scalp"})),
    ("price_only", frozenset({"universe", "bars", "h1", "m1", "m5", "m15", "ohlc", "mt5",
                              "parquet", "sleeve", "ledger"})),
)


def tokens(*names: Any) -> set[str]:
    out: set[str] = set()
    for n in names:
        if n is None:
            continue
        if isinstance(n, (list, tuple)):
            out |= tokens(*n)
            continue
        out.update(t for t in re.split(r"[^a-z0-9]+", str(n).lower()) if t)
    return out


def info_class(*names: Any) -> str:
    toks = tokens(*names)
    for cls, keys in CLASS_RULES:
        if toks & keys:
            return cls
    return UNKNOWN


def _stem(dataset: str) -> str:
    d = str(dataset or "").strip().lower()
    return d.split(":", 1)[1] if ":" in d else d


# ------------------------------------------------------------------------------------ ingestion

def ingestion_by_dataset(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per ingested dataset: units (latest row per unit), PIT share, dispositions, downstream
    states, the three access/credibility/predictive labels and the last ingestion stamp."""
    latest: dict[tuple[str, str], Mapping[str, Any]] = {}
    for r in rows:
        ds = str(r.get("dataset") or r.get("kind") or "")
        uid = str(r.get("unit_id") or "")
        if not ds or not uid:
            continue
        latest[(ds, uid)] = r                       # the ledger is append-only: last row wins
    out: dict[str, dict[str, Any]] = {}
    for (ds, _uid), r in latest.items():
        rec = out.setdefault(ds, {"units": 0, "pit": 0, "dispositions": Counter(),
                                  "downstream": Counter(), "access": Counter(),
                                  "kinds": set(), "paths": set(), "last_at": ""})
        rec["units"] += 1
        rec["pit"] += int(bool(r.get("pit")))
        rec["dispositions"][str(r.get("disposition") or UNMEASURED)] += 1
        rec["downstream"][str(r.get("downstream_state") or UNMEASURED)] += 1
        rec["access"][str(r.get("access_label") or UNMEASURED)] += 1
        rec["kinds"].add(str(r.get("kind") or ""))
        if r.get("path"):
            rec["paths"].add(str(r["path"]).replace("\\", "/"))
        rec["last_at"] = max(rec["last_at"], str(r.get("at") or ""))
    for rec in out.values():
        n = rec["units"]
        rec["pit_share"] = rec["pit"] / n if n else None
        stranded = rec["dispositions"].get("STRANDED", 0)
        rec["stranded_share"] = stranded / n if n else None
        for k in ("dispositions", "downstream", "access"):
            rec[k] = dict(rec[k])
        rec["kinds"] = sorted(k for k in rec["kinds"] if k)
        rec["paths"] = sorted(rec["paths"])[:5]
    return out


# ------------------------------------------------------------------------------------- vintages

def vintage_series(roots: Sequence[Path]) -> dict[str, Path]:
    """series id -> the root whose `data/vintages/<series>.jsonl` holds its revision log."""
    out: dict[str, Path] = {}
    for root in roots:
        d = root / "data" / "vintages"
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.jsonl")):
            out.setdefault(p.stem, root)
    return out


def _vintage_summary(root: Path, series: str) -> dict[str, Any]:
    try:
        from libs.research import vintage
        s = vintage.summarise(root, series)
    except Exception as exc:                         # a corrupt log costs one series, never all
        return {"series": series, "status": UNMEASURED, "why": f"{type(exc).__name__}"}
    return {k: s.get(k) for k in ("series", "status", "n_rows", "n_periods", "n_vintages",
                                  "first_vintage", "last_vintage", "n_revised") if k in s}


# ----------------------------------------------------------------------------------------- join

def _match(ds: str, rec: Mapping[str, Any], registry: Mapping[str, Mapping[str, Any]]
           ) -> tuple[str | None, str]:
    """The registry entry an ingested dataset belongs to, and the basis of the attachment."""
    stem = _stem(ds)
    if stem in registry:
        return stem, "exact_name"
    paths = [p.lower() for p in rec.get("paths") or []]
    for name in sorted(registry):
        rp = str(registry[name].get("path") or "").lower()
        prefix = rp.split("*", 1)[0].rstrip("/")
        if prefix and any(prefix in p for p in paths):
            return name, "declared_path"
    for name in sorted(registry):
        if name.split("_", 1)[0] == stem or stem.split("_", 1)[0] == name:
            return name, "leading_name_token"
    return None, ""


def source_records(registry: Mapping[str, Mapping[str, Any]],
                   ingestion: Mapping[str, Mapping[str, Any]],
                   vintages: Mapping[str, Path],
                   gate_yield: Mapping[str, Mapping[str, Any]] | None = None,
                   summarise: Callable[[Path, str], dict[str, Any]] | None = None
                   ) -> dict[str, Any]:
    """One record per source joining the three ledgers, plus the orphan census."""
    summarise = summarise or _vintage_summary
    gate_yield = gate_yield or {}
    recs: dict[str, dict[str, Any]] = {}
    for name, entry in sorted(registry.items()):
        recs[name] = {"source": name, "registry": {
            k: entry.get(k) for k in ("lifecycle", "source", "path", "format", "ingested",
                                      "provenance") if entry.get(k) is not None},
            "ingestion": [], "vintage": [], "join": []}
    orphans: dict[str, list[str]] = {"registry_only": [], "ingestion_only": [],
                                     "vintage_only": []}
    for ds, rec in sorted(ingestion.items()):
        found, basis = _match(ds, rec, registry)
        name = found or ""
        if found is None:
            name = f"ingested:{_stem(ds)}"
            recs.setdefault(name, {"source": name, "registry": {
                "status": UNMEASURED, "why": f"dataset {ds!r} is not declared in data_registry"},
                "ingestion": [], "vintage": [], "join": []})
            orphans["ingestion_only"].append(ds)
            basis = "unregistered"
        recs[name]["ingestion"].append({"dataset": ds, **rec})
        recs[name]["join"].append({"side": "ingestion", "dataset": ds, "basis": basis})
    # a registry entry that lists its series owns their vintage logs
    series_owner: dict[str, str] = {}
    for name, entry in registry.items():
        ser = entry.get("series")
        for s in (ser if isinstance(ser, list) else []):
            series_owner.setdefault(str(s), name)
    for series, root in sorted(vintages.items()):
        owner = series_owner.get(series)
        name = owner or ""
        basis = "declared_series"
        if owner is None:
            name = f"vintage:{series}"
            recs.setdefault(name, {"source": name, "registry": {
                "status": UNMEASURED, "why": f"no data_registry entry lists series {series!r}"},
                "ingestion": [], "vintage": [], "join": []})
            orphans["vintage_only"].append(series)
            basis = "unregistered"
        recs[name]["vintage"].append(summarise(root, series))
        recs[name]["join"].append({"side": "vintage", "series": series, "basis": basis})
    for name, r in recs.items():
        entry = registry.get(name) or {}
        r["info_class"] = info_class(name, entry.get("source"), entry.get("path"),
                                     [i["dataset"] for i in r["ingestion"]],
                                     [k for i in r["ingestion"] for k in i.get("kinds") or []])
        gy = gate_yield.get(r["info_class"])
        r["gate_yield"] = dict(gy) if gy else {
            "status": UNMEASURED, "why": (f"no gate verdict in the window on a family reading "
                                          f"{r['info_class']} information")}
        if not r["ingestion"]:
            r["ingestion_status"] = {"status": UNMEASURED,
                                     "why": "no ingestion_ledger unit names this source"}
            if name in registry:
                orphans["registry_only"].append(name)
        if not r["vintage"]:
            r["vintage_status"] = {"status": UNMEASURED,
                                   "why": "no vintage log: current-vintage reads are unaudited"}
        r["joined"] = sorted(s for s, ok in (("registry", name in registry),
                                              ("ingestion", bool(r["ingestion"])),
                                              ("vintage", bool(r["vintage"]))) if ok)
    full = sum(1 for r in recs.values() if len(r["joined"]) == 3)
    return {"records": [recs[k] for k in sorted(recs)], "n_sources": len(recs),
            "fully_joined": full,
            "orphans": {k: sorted(v) for k, v in orphans.items()},
            "by_class": dict(Counter(r["info_class"] for r in recs.values()))}


# ------------------------------------------------------------------------------------ gate yield

def gate_yield(rows: Iterable[Mapping[str, Any]], classify: Callable[[str], str], now: datetime,
               window_days: int = YIELD_WINDOW_DAYS) -> dict[str, dict[str, Any]]:
    """Pass share of gate verdicts in the trailing window, per information class (and `all`).
    A row with no parseable `at` is counted out loud (`undated`), never silently in-window."""
    lo = now - timedelta(days=window_days)
    n: Counter[str] = Counter()
    k: Counter[str] = Counter()
    undated = 0
    for r in rows:
        at = parse_t(r.get("at"))
        if at is None:
            undated += 1
            continue
        if at < lo or at > now:
            continue
        cls = classify(str(r.get("family") or ""))
        ok = bool(r.get("passed"))
        for c in (cls, "all"):
            n[c] += 1
            k[c] += int(ok)
    out: dict[str, dict[str, Any]] = {}
    for c in n:
        out[c] = {"status": "MEASURED", "verdicts": n[c], "passed": k[c],
                  "yield": round(k[c] / n[c], 6), "window_days": window_days}
    if undated:
        out.setdefault("all", {"status": UNMEASURED, "why": "no dated verdict in the window"})
        out["all"]["undated_rows"] = undated
    return out


def yield_metric(cls: str) -> str:
    return f"gate_yield:{cls}"


def metric_now(yields: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    return {yield_metric(c): float(v["yield"]) for c, v in yields.items()
            if v.get("status") == "MEASURED" and v.get("yield") is not None}


def retarget(preds: Sequence[Any], metrics: Mapping[str, float]) -> dict[str, int]:
    """Move open predictions onto the gate-yield metric of their item's class, and stamp a
    `metric_before` on any open prediction that was made while its yield was UNMEASURED (the
    baseline is the first measured reading before the item lands, never a back-filled zero)."""
    moved = stamped = 0
    for p in preds:
        if p.resolved:
            continue
        if not str(p.metric).startswith("gate_yield:"):
            p.metric = yield_metric(info_class(p.item, p.kind))
            p.metric_before = None
            moved += 1
        if p.metric_before is None:
            m = metrics.get(p.metric)
            if m is None and p.metric != yield_metric("all"):
                # a class no verdict touched falls back to the desk-wide yield, said on the row
                p.metric = yield_metric("all")
                m = metrics.get(p.metric)
            if m is not None:
                p.metric_before = m
                stamped += 1
    return {"retargeted": moved, "baseline_stamped": stamped}



# --------------------------------------------------------------------- known-by-date (PIT) lags

#: PUBLICATION LAG PER SOURCE: when a value that is TRUE AT its valid time becomes KNOWABLE.
#:
#: Every external dataset research reads needs one of two things before a backtest may join it
#: to a bar: a declared lag here (knowledge time = valid time + `lag_s`) or a knowledge-time
#: column carried on the rows themselves (`knowledge_column`). A source with neither can only be
#: joined by the date it DESCRIBES, which is the look-ahead this desk has paid for three times
#: (the macro-sweep same-date join, the COT Tuesday label, the monthly FRED prints).
#:
#: THE READS THAT DEFINE A READER. `readers` are the tokens whose presence in a research module
#: marks it as reading the source -- `scripts/check_known_by_date.py` names every such module that
#: joins by valid date without routing through a lag, and `scripts/check_pit.py` fails on a
#: registered dataset (`desks/mt5/data/data_registry.json`) that has no entry here and no
#: `pit.publication_lag_days` of its own. Lags are CONSERVATIVE on purpose: a lag that is a day
#: too long costs a day of signal; a lag that is a day too short manufactures an edge.
#:
#: `valid` says what the valid time IS for that source, because the lag means nothing without it.
PUBLICATION_LAGS: dict[str, dict[str, Any]] = {
    # the broker's own bars: a bar is known at its close, and every family acts on closed bars
    # (`libs/research/bar_clock`, `family_call`). Valid time = the bar's open stamp.
    "mt5_h1_universe": {"lag_s": 3600, "valid": "H1 bar open (broker time under UTC tzinfo)",
                        "basis": "known at the bar's close, one bar after its stamp",
                        "readers": ()},
    "xauusd_scalp_bars": {"lag_s": 300, "valid": "M5 bar open", "basis": "known at bar close",
                          "readers": ()},
    # daily market prints (DGS10, T10YIE, VIX, DXY, SPX, CL): posted the following day; the bar
    # index is broker time (+2 winter / +3 summer), so one day plus the largest offset is the
    # earliest bar that could read the print under either clock.
    "cross_asset_anchors": {"lag_s": 27 * 3600, "valid": "the market day the print refers to",
                            "basis": "run_edges_macro_fusion_sweep.MACRO_KNOWABLE_AFTER: 1 day + "
                                     "the 3h broker offset",
                            "readers": ("macro_regime.load_history", "cross_asset_anchors")},
    "fred_macro": {"lag_s": 27 * 3600, "valid": "observation date (daily market series only)",
                   "basis": "orthogonal_sweep.MACRO_PUBLICATION_LAG_D = 1 day, plus the broker "
                            "offset; monthly releases are admissible only through data/vintages",
                   "readers": ("fred_macro.json", "lake/fred_", "fred_macro")},
    # CFTC: as-of TUESDAY, published the FOLLOWING FRIDAY 15:30 ET (19:30/20:30 UTC)
    "cot_fx": {"lag_s": 4 * 86400, "valid": "report date (Tuesday)",
               "basis": "owned_data._COT_PUBLICATION_LAG_DAYS = 4: Friday release, Saturday "
                        "under every DST/broker-clock combination",
               "readers": ("cot_zcache", "data/cot/", "cot_tff", "cot_disagg")},
    "cot": {"lag_s": 4 * 86400, "valid": "report date (Tuesday)",
            "basis": "the same CFTC release as cot_fx", "readers": ("cot.json",)},
    "eur_cot_blocked": {"lag_s": 4 * 86400, "valid": "report date (Tuesday)",
                        "basis": "the same CFTC release as cot_fx", "readers": ()},
    "bis_eer": {"lag_s": 20 * 86400, "valid": "reference month end",
                "basis": "monthly official statistic; pit_stamp.DEFAULT_LAG_DAYS['monthly']",
                "readers": ("bis_eer",)},
    "spdr_gld_holdings": {"lag_s": 86400, "valid": "holdings date",
                          "basis": "published the same US evening: usable next day",
                          "readers": ("gld_holdings", "spdr_gld")},
    "sge_benchmark": {"lag_s": 86400, "valid": "fixing date",
                      "basis": "the PM fix prints 15:30 CST; next day is unambiguous",
                      "readers": ("sge_daily", "sge_benchmark")},
    "shfe_gold": {"lag_s": 86400, "valid": "trade date", "basis": "daily settlement",
                  "readers": ("shfe",)},
    "lbma_vaults": {"lag_s": 40 * 86400, "valid": "reference month end",
                    "basis": "LBMA publishes vault holdings with a one-month lag on the 5th "
                             "business day",
                    "readers": ("lbma_vault",)},
    "swiss_customs_gold": {"lag_s": 25 * 86400, "valid": "reference month end",
                           "basis": "FOCBS monthly trade data, about three weeks after month end",
                           "readers": ("swiss_customs",)},
    "wgc_goldhub": {"lag_s": 20 * 86400, "valid": "reference month end",
                    "basis": "monthly ETF/flow tables; pit_stamp.DEFAULT_LAG_DAYS['monthly']",
                    "readers": ("goldhub",)},
    "cme_gc": {"lag_s": 86400, "valid": "trade date", "basis": "daily settlement",
               "readers": ("cme_gc",)},
    "gdelt": {"lag_s": 3600, "valid": "event time",
              "basis": "15-minute update cadence; one bar is conservative",
              "knowledge_column": "published_time", "readers": ("gdelt",)},
}


def declared_lag(source: str, registry_row: Mapping[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    """The source's declared publication lag, or None when it has none.

    A registry row's own `pit.publication_lag_days` (the field `libs/data/pit_stamp.lag_for`
    reads) counts as a declaration and wins; else `PUBLICATION_LAGS`. A cadence DEFAULT is not a
    declaration -- it is what `pit_stamp` falls back to when nobody declared anything, which is
    exactly the state this registry exists to end."""
    pit = (registry_row or {}).get("pit") if isinstance(registry_row, Mapping) else None
    if isinstance(pit, Mapping) and pit.get("publication_lag_days") is not None:
        try:
            days = float(pit["publication_lag_days"])
        except (TypeError, ValueError):
            days = -1.0
        if days >= 0:
            return {"lag_s": days * 86400, "basis": "data_registry pit.publication_lag_days",
                    "valid": str(pit.get("valid") or "declared by the registry row")}
    entry = PUBLICATION_LAGS.get(source)
    return dict(entry) if entry is not None else None


def knowledge_time(source: str, valid_time: datetime) -> datetime:
    """valid_time + the source's declared lag. KeyError for an undeclared source: a value whose
    publication lag nobody declared cannot be given a knowledge time by guessing one."""
    lag = declared_lag(source)
    if lag is None:
        raise KeyError(f"source {source!r} has no declared publication lag (data_os."
                       "PUBLICATION_LAGS) and no knowledge-time column")
    return valid_time + timedelta(seconds=float(lag["lag_s"]))


def store_from_series(series: Any, *, source: str, entity: str, attribute: str) -> Any:
    """A valid-dated pandas Series as BITEMPORAL rows: valid time = its index, knowledge time =
    valid + the source's declared lag. The one door a research reader uses to turn a dataset it
    would otherwise join by date into one it can only read as of what was known."""
    import pandas as pd

    from libs.tiers.bitemporal import BitemporalStore, Datum
    lag = declared_lag(source)
    if lag is None:
        raise KeyError(f"source {source!r} has no declared publication lag")
    delta = pd.Timedelta(seconds=float(lag["lag_s"]))
    store = BitemporalStore()
    for t, val in series.items():
        if val is None or (isinstance(val, float) and val != val):
            continue
        ts = pd.Timestamp(t)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        store.add(Datum(entity=entity, attribute=attribute,
                        value=val.item() if hasattr(val, "item") else val,
                        valid_time=ts.isoformat(), knowledge_time=(ts + delta).isoformat(),
                        source=source, latency_s=float(lag["lag_s"])))
    return store


def lag_census(registry: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Which registered datasets carry a declared lag, which do not, and where each came from."""
    declared: dict[str, str] = {}
    undeclared: list[str] = []
    for name, row in sorted(registry.items()):
        lag = declared_lag(name, row if isinstance(row, Mapping) else None)
        if lag is None:
            undeclared.append(name)
        else:
            declared[name] = str(lag.get("basis") or "")
    return {"n": len(registry), "declared": sorted(declared), "undeclared": undeclared,
            "basis": declared}


def tail_jsonl(path: Path, max_bytes: int = 8 * 1024 * 1024) -> list[dict[str, Any]]:
    """The last `max_bytes` of an append-only JSONL ledger, whole lines only: the latest row per
    unit lives at the tail, and the head of a years-long ledger is history the join does not need.
    """
    import json
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            raw = fh.read()
    except OSError:
        return []
    lines = raw.split(b"\n")
    if size > max_bytes:
        lines = lines[1:]                            # the first line is cut mid-row
    out: list[dict[str, Any]] = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out
