"""THE DATASET TRANSLATOR -- every dataset the desk holds, turned into a signal on something the
desk trades (FX, indices, commodity CFDs, metals), every hour, including datasets that arrive
after this file was written.

THE TRANSLATION RULE (principal, permanent, 2026-11-18). The first ledger
(`reports/ideas/DATASET_WIRING.md`, 2026-11-18) measured 12 of 163 datasets wired -- 7%. The 151
orphans were not unusable; nothing translated them. A Riksbank page is a SEK signal, a Dalian
exchange file is an iron-ore and soy signal and therefore an AUD and BRL one, a Chinese stock
forum is a CHINAH / HK50 / USDCNH signal. Company-level data is rolled up to its country,
sector or commodity aggregate; nothing here mints on a share CFD.

ONE PASS:

  1. ENUMERATES every dataset from the same grounds DATASET_WIRING reads -- the free-stack roster,
     the deep-forest dataset rows, the axis files, the keyed-source roster, the free-data key
     catalogue -- plus every lake series no roster claims. A dataset added to any of them is
     picked up on the next pass by construction: nothing here is a list of datasets.
  2. INFERS country, central bank, commodity and sector from the dataset's host, publisher,
     language, region, title and declared fields against `data/translation_ontology.json`, and
     maps each to its tradables. Every symbol is re-checked against the broker registry on the
     pass; one the registry lacks is DROPPED AND COUNTED, never invented.
  3. JUDGES only what has a series. A dataset with a lake frame (`data/lake/series/<stem>`, the
     frame `family_exogenous_conditioner` loads, with its `available_time` stamp) gets ONE cell
     per pass -- the next (tradable, side) on its own ring -- as `exogenous_conditioner`, or
     `alt_release_drift` when the dataset is event-like and the frame carries `surprise_z`. Both
     families are registered builders (`miner_candidate_compiler._registered_family`); a test
     pins it. Datasets are visited newest first from a rotating offset, under a per-pass cap.
  4. RECORDS A MAPPING WITHOUT A SERIES AS `MAPPED_AWAITING_SERIES`, with the tradables named, so
     the hour a series lands under one of its declared prefixes it is judged. No series is ever
     fabricated and no cell is minted without one.
  5. WRITES `reports/DATASET_TRANSLATION.json`: the WIRED SHARE (datasets with at least one mapped
     tradable / all datasets), the same share counting only symbols the datasets DECLARED (the
     before-translation reading), the status breakdown, the top mappings and every row.

FENCES, ALL FAIL CLOSED. A host the terms ruling refuses (`libs.data.refused_hosts`, plus the
worker-rule refusals not yet in that list) is UNMAPPABLE `BLOCKED_ON_TERMS` with the tradables it
would have mapped and a missed_growth line. With no `research.universe_policy` the pass mints
nothing (`BLOCKED_DEPENDENCY`). Donation goes through `proposer_common.donate`, which stamps,
lane-filters and pre-registers every row, and `tests_run` charges each cell to the trial census.

    python desks/mt5/research/dataset_translator.py --once [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "dataset_translator"
ONTOLOGY = DESK / "data" / "translation_ontology.json"
REGISTRY = DESK / "data" / "universe" / "universe.json"
FREE_STACK = DESK / "data" / "free_stack_sources.json"
FS_COLUMNS = DESK / "data" / "free_stack" / "columns.json"
DEEP_FOREST = DESK / "data" / "deep_forest_datasets.jsonl"
AXES = DESK / "data" / "axes"
KEYED = DESK / "data" / "source_rosters" / "keyed_sources.json"
ENV_KEYS = ROOT / "libs" / "ops" / "env_keys_catalog.json"
LAKE = DESK / "data" / "lake" / "series"
CURSOR = DESK / "data" / "dataset_translation" / "cursor.json"
REPORT = DESK / "reports" / "DATASET_TRANSLATION.json"

#: The only families this organ mints. Both are registered builders; the test suite pins it.
EXO = "exogenous_conditioner"
RELEASE = "alt_release_drift"
EMITTED_FAMILIES: tuple[str, ...] = (EXO, RELEASE)

#: Cells per pass. NOT A BRAKE ON BREADTH: every dataset with a series gets at most one cell a
#: pass and the start rotates, so all of them are reached within `passes_to_cover` hours; the
#: bound keeps the registry write inside the hour (proposer_common measured ~4 rows/s unbatched).
PER_PASS = 400
MISSED_GROWTH_CAP = ("a dataset with a series past the per-pass cap waits for the next hour's "
                     "rotation; its cell is judged up to passes_to_cover hours later, never lost")
SIDES: tuple[int, ...] = (1, -1)
DEFAULT_LAG_H = 24
CHART = "H1"

CELL_EMITTED = "CELL_EMITTED"
CELL_QUEUED = "CELL_QUEUED"
AWAITING = "MAPPED_AWAITING_SERIES"
UNMAPPABLE = "UNMAPPABLE"

#: Worker-rule terms refusals not yet in `libs.data.refused_hosts` (2026-11-18). Matched by suffix.
EXTRA_REFUSED: dict[str, str] = {
    "reddit.com": "Reddit: Data API terms bar commercial use without an agreement",
    "arcgis.com": "IMF PortWatch via ArcGIS: terms pending reconciliation",
}
#: Terms-refused PROVIDERS named in a dataset's id or title where its URL is a sign-up or console
#: page rather than the refused host itself (the key catalogue's YouTube and Comtrade rows).
REFUSED_NAMES: dict[str, str] = {
    "youtube": "YouTube: terms refuse automated access",
    "comtrade": "UN Comtrade: terms refuse automated use (ruling 2026-11-13)",
    "fred": "FRED: refused for all automated fetches (terms ruling 2026-11-13)",
    "alfred": "FRED/ALFRED: refused for all automated fetches (terms ruling 2026-11-13)",
    "yahoo": "Yahoo: terms refuse automated collection",
    "dukascopy": "Dukascopy: terms refuse bots and commercial use",
    "portwatch": "IMF PortWatch: terms pending reconciliation",
}
#: Key-catalogue rows that are the companion of another credential, not a dataset of their own.
_KEY_COMPANIONS = ("_USER_AGENT", "_APP_ID", "_SECONDARY", "_PASS", "_PASSWORD", "_USER",
                   "_MAILADDRESS", "_REFRESH_TOKEN", "_HASH")
_EVENT_WORDS = ("press release", "news", "monetary policy", "announcement", "speech", "decision",
                "statement", "notices", "auction", "transcript", "disclosure", "filing",
                "periodic transaction")
_STAMP_COLS = frozenset({"event_time", "published_time", "available_time", "revision_time",
                         "retrieval_time", "ingested_time", "source_id", "vintage_id"})
_TEXT_COLS = frozenset({"series", "symbol", "date", "period", "unit", "units", "name", "id",
                        "source", "country", "currency", "code", "label", "title", "url"})


# ------------------------------------------------------------------------------------- io ---
def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _jsonl(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = p.read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def host_of(url: Any) -> str:
    try:
        return (urlsplit(str(url or "")).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


# ------------------------------------------------------------------------- the registry ---
def tradable_registry(path: Path | None = None) -> dict[str, str]:
    """{symbol: asset_class} for every broker symbol. Share CFDs are kept so a declared share can
    be ROLLED UP; nothing here ever mints on one."""
    doc = _read(path or REGISTRY, {}) or {}
    return {str(s): str((m or {}).get("asset_class") or "") for s, m in doc.items()
            if isinstance(m, dict)}


def load_ontology(registry: dict[str, str], path: Path | None = None
                  ) -> tuple[dict[str, Any], Counter[str]]:
    """The ontology with every tradable list re-checked against the LIVE registry. Returns the
    filtered ontology and the symbols dropped on this pass (counted, never invented)."""
    onto = _read(path or ONTOLOGY, {}) or {}
    dropped: Counter[str] = Counter()

    def keep(xs: Iterable[Any]) -> list[str]:
        out: list[str] = []
        for x in xs or []:
            s = str(x)
            if s in registry and registry[s] != "Equities":
                if s not in out:
                    out.append(s)
            else:
                dropped[s] += 1
        return out

    for sect in ("countries", "central_banks", "commodities", "sectors"):
        for row in (onto.get(sect) or {}).values():
            for k in ("fx", "index", "proxy", "cfd", "producer_fx"):
                if k in row:
                    row[k] = keep(row[k])
    onto["regions"] = {k: keep(v) for k, v in (onto.get("regions") or {}).items()}
    for s, n in (onto.get("dropped_not_in_registry") or {}).items():
        dropped[str(s)] += len(n) if isinstance(n, list) else 1
    return onto, dropped


# ------------------------------------------------------------------------- enumeration ---
def _ds(did: str, kind: str, **kw: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": did, "kind": kind, "title": "", "url": "", "host": "",
                           "lang": "", "region": "", "cluster": "", "declared": [],
                           "text": "", "available_time": "", "prefixes": [],
                           "event_like": False, "lag_hours": DEFAULT_LAG_H}
    row.update(kw)
    if not row["host"]:
        row["host"] = host_of(row["url"])
    blob = " ".join(str(row.get(k) or "") for k in ("title", "text", "url"))
    row["event_like"] = bool(row["event_like"]) or any(w in blob.lower() for w in _EVENT_WORDS)
    return row


def _free_stack(path: Path) -> list[dict[str, Any]]:
    out = []
    for r in (_read(path, {}) or {}).get("sources") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        sid = str(r["id"])
        tg = (r.get("targets") or {}).get("hypothesis")
        out.append(_ds(f"free_stack:{sid}", "free_stack", title=str(r.get("name") or sid),
                       url=str(r.get("url") or ""), lang=str(r.get("language") or ""),
                       region=str(r.get("region") or ""),
                       declared=list(tg) if isinstance(tg, list) else [],
                       text=f"{sid} {r.get('mechanism') or ''}",
                       lag_hours=max(DEFAULT_LAG_H, int(r.get("lag_hours") or 0)),
                       event_like=sid in ("congress_trades", "jp_ir_transcripts"),
                       prefixes=[f"fs_{sid}"]))
    return out


def _deep_forest(path: Path) -> list[dict[str, Any]]:
    out, seen = [], set()
    for r in _jsonl(path):
        key = str(r.get("url") or r.get("source_hash") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        host = str(r.get("host") or host_of(r.get("url")))
        h = str(r.get("source_hash") or r.get("vault_sha") or _slug(key))[:20]
        out.append(_ds(f"deep_forest:{h}", "deep_forest", title=str(r.get("title") or ""),
                       url=str(r.get("url") or ""), host=host,
                       lang=str(r.get("lang") or r.get("language") or ""),
                       region=str(r.get("region") or ""), cluster=str(r.get("cluster") or ""),
                       declared=list(r.get("symbols") or []),
                       text=f"{r.get('ground') or ''} {r.get('dataset_class') or ''}",
                       available_time=str(r.get("available_time") or r.get("published") or ""),
                       prefixes=[f"df_{_slug(host)}"]))
    return out


def _axes(path: Path) -> list[dict[str, Any]]:
    out = []
    for p in sorted(path.glob("*.json")) if path.is_dir() else []:
        d = _read(p, {}) or {}
        name = p.stem
        src = str(d.get("source") or "")
        url = src if "://" in src else (f"https://{src}" if "." in src and "/" not in src else "")
        if name == "fred":
            url = url or "https://fred.stlouisfed.org/"
        cur = " ".join(str(c) for c in d.get("currencies") or [])
        out.append(_ds(f"axis:{name}", "axis", title=f"{name} axis", url=url,
                       declared=list(d.get("symbols") or []), text=f"{name} {src} {cur}",
                       available_time=str(d.get("at") or ""), prefixes=[f"axis_{p.stem}"]))
    return out


def _keyed(path: Path) -> list[dict[str, Any]]:
    out = []
    for r in (_read(path, {}) or {}).get("sources") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        sid = str(r["id"])
        decl: list[str] = []
        for s in (r.get("series") or {}).values():
            for sym in ((s or {}).get("instruments") or {}) if isinstance(s, dict) else {}:
                if sym not in decl:
                    decl.append(str(sym))
        lag = int((r.get("rule") or {}).get("lag_days") or 1) * 24
        out.append(_ds(f"keyed:{sid}", "keyed", title=str(r.get("name") or sid),
                       url=str(r.get("url") or ""), lang=str(r.get("lang") or ""),
                       region=str(r.get("region") or ""), declared=decl,
                       text=f"{sid} {r.get('mechanism') or ''}",
                       lag_hours=max(DEFAULT_LAG_H, lag), prefixes=[f"ks_{sid}__"]))
    return out


def _key_feeds(path: Path, registry: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for k in (_read(path, {}) or {}).get("keys") or []:
        name = str((k or {}).get("name") or "")
        if k.get("group") != "free_data" or not name or name.endswith(_KEY_COMPANIONS):
            continue
        unlocks = str(k.get("unlocks") or "")
        decl = [t for t in re.findall(r"[A-Z0-9]{5,8}", unlocks) if t in registry]
        prov = _slug(re.sub(r"_(API_KEY|KEY|TOKEN|APP_ID|MAP_KEY|UA)$", "", name))
        out.append(_ds(f"key:{name}", "keyed_feed", title=unlocks[:120] or name,
                       url=str(k.get("signup") or "").split(" ")[0], declared=decl,
                       text=f"{prov} {unlocks} {k.get('owner') or ''}",
                       prefixes=[f"{prov}_", f"ks_{prov}"]))
    return out


def lake_stems(lake: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if lake.is_dir():
        for p in sorted(lake.iterdir()):
            if p.suffix in (".parquet", ".csv") and p.stem not in out:
                out[p.stem] = p
    return out


def enumerate_datasets(*, registry: dict[str, str], stems: dict[str, Path],
                       free_stack: Path = FREE_STACK, deep_forest: Path = DEEP_FOREST,
                       axes: Path = AXES, keyed: Path = KEYED, env_keys: Path = ENV_KEYS
                       ) -> list[dict[str, Any]]:
    """Every dataset the desk holds, from every ground. A lake series no roster row claims is a
    dataset in its own right, so a series that lands from any producer is translated too."""
    rows = (_free_stack(free_stack) + _deep_forest(deep_forest) + _axes(axes) + _keyed(keyed)
            + _key_feeds(env_keys, registry))
    claimed = {s for r in rows for s in stems if any(s.startswith(p) for p in r["prefixes"])}
    for stem in sorted(set(stems) - claimed):
        cc = stem.split("_", 1)[0]
        out = _ds(f"lake:{stem}", "lake", title=stem, text=stem.replace("_", " "),
                  region=cc if len(cc) == 2 else "", prefixes=[stem])
        out["exact_series"] = True
        rows.append(out)
    return rows


# ---------------------------------------------------------------------------- inference ---
def _hit(alias: str, text: str) -> bool:
    a = alias.strip().lower()
    if not a:
        return False
    if a.isascii():
        return re.search(r"(?<![a-z0-9])" + re.escape(a) + r"[a-z]{0,2}(?![a-z0-9])",
                         text) is not None
    return a in text


def infer(ds: dict[str, Any], onto: dict[str, Any], registry: dict[str, str]
          ) -> tuple[list[str], list[str], dict[str, str]]:
    """(tradables in priority order, entities, {tradable: first evidence}). Order: declared
    symbols, central bank, commodity, country, sector, regional cluster (only when nothing
    else placed the dataset)."""
    trad: list[str] = []
    why: dict[str, str] = {}
    ents: list[str] = []

    def add(syms: Iterable[str], ev: str) -> None:
        for s in syms:
            if s in registry and registry[s] != "Equities" and s not in trad:
                trad.append(s)
                why[s] = ev

    host = str(ds.get("host") or "")
    text = " ".join(str(ds.get(k) or "") for k in ("title", "text", "host", "url")).lower()
    countries = onto.get("countries") or {}
    # 1. declared symbols; a declared share CFD is ROLLED UP to the US index it lists on.
    rolled = [s for s in ds.get("declared") or [] if registry.get(str(s)) == "Equities"]
    add([str(s) for s in ds.get("declared") or []], "declared")
    if rolled:
        ents.append("rollup:US_equities")
        add((countries.get("US") or {}).get("index") or [], f"rollup of {len(rolled)} shares")
    # 2. central bank, by host first and its own name second.
    cbs: list[str] = []
    for k, cb in (onto.get("central_banks") or {}).items():
        by_host = any(host == h or host.endswith("." + h) for h in cb.get("hosts") or [])
        if by_host or any(_hit(a, text) for a in cb.get("aliases") or []):
            cbs.append(k)
            ents.append(f"central_bank:{k}")
            cc = cb.get("country")
            add((countries.get(cc) or {}).get("fx") or cb.get("fx") or [], f"central_bank:{k}")
    # 3. commodity -> its CFD, its producer currencies and its index proxy. Before the country:
    #    an EIA inventory page is a crude signal first and a US one second.
    for k, cm in (onto.get("commodities") or {}).items():
        if any(_hit(a, text) for a in cm.get("aliases") or []):
            ents.append(f"commodity:{k}")
            add(cm.get("cfd") or [], f"commodity:{k}")
            add(cm.get("producer_fx") or [], f"commodity:{k}:producer")
            add(cm.get("index") or [], f"commodity:{k}")
    # 4. country: declared region code, host TLD, name, then (non-English) language.
    found: list[str] = []
    reg = str(ds.get("region") or "").upper()
    if reg in countries:
        found.append(reg)
    for cc, c in countries.items():
        if cc in found:
            continue
        tlds = c.get("tlds") or []
        if any(host.endswith(t) for t in tlds if t != ".gov") or \
                (host.endswith(".gov") and ".gov" in tlds) or \
                any(_hit(a, text) for a in c.get("aliases") or []):
            found.append(cc)
    lang = str(ds.get("lang") or "").lower().split("/")[0]
    if not found and lang not in ("", "en", "multi"):
        found += [cc for cc, c in countries.items() if lang in (c.get("langs") or [])][:1]
    for cc in found:
        c = countries[cc]
        ents.append(f"country:{cc}")
        add(c.get("fx") or [], f"country:{cc}")
        add(c.get("index") or [], f"country:{cc}")
        add(c.get("proxy") or [], f"country:{cc}:proxy")
    # 5. sector -> index CFDs. A THEME (sentiment, positioning, labour ...) names US instruments,
    #    so it adds them only when no country placed the dataset or the country is the US.
    us_or_none = not found or found == ["US"] or "US" in found
    for k, sc in (onto.get("sectors") or {}).items():
        if any(_hit(a, text) for a in sc.get("aliases") or []):
            ents.append(f"sector:{k}")
            if not sc.get("theme") or us_or_none:
                add(sc.get("index") or [], f"sector:{k}")
    # 6. regional cluster, only as a last resort.
    if not trad:
        cl = str(ds.get("cluster") or ds.get("region") or "").lower()
        regions = onto.get("regions") or {}
        if regions.get(cl):
            ents.append(f"region:{cl}")
            add(regions[cl], f"region:{cl}")
    return trad, ents, why


# ------------------------------------------------------------------------------- series ---
def series_for(ds: dict[str, Any], stems: dict[str, Path]) -> list[str]:
    if ds.get("exact_series"):
        return [s for s in ds["prefixes"] if s in stems]
    return sorted(s for s in stems if any(s.startswith(p) for p in ds["prefixes"]))


def columns_of(path: Path) -> tuple[list[str], bool]:
    """(numeric signal columns, carries available_time). Reads the header only."""
    names: list[str] = []
    numeric: dict[str, bool] = {}
    try:
        if path.suffix == ".parquet":
            import pyarrow.parquet as pq
            sch = pq.read_schema(path)
            for f in sch:
                names.append(f.name)
                t = str(f.type)
                numeric[f.name] = t.startswith(("int", "uint", "float", "double", "decimal"))
        else:
            with path.open("r", encoding="utf-8") as fh:
                head = fh.readline().strip()
            names = [c.strip().strip('"') for c in head.split(",") if c.strip()]
            numeric = {c: c.lower() not in _TEXT_COLS for c in names}
    except Exception:
        return [], False
    sig = [c for c in names if c not in _STAMP_COLS and numeric.get(c)
           and c.lower() not in _TEXT_COLS]
    pref = ("surprise_z", "z", "value", "chg_z")
    sig.sort(key=lambda c: (pref.index(c) if c in pref else len(pref), names.index(c)))
    return sig, "available_time" in names


def refusal_of(url: str, host: str, name: str = "") -> str | None:
    """Why the dataset may not be used, or None. An unimportable host list fails CLOSED."""
    low = name.lower()
    for word, why in REFUSED_NAMES.items():
        if re.search(r"(?<![a-z0-9])" + word + r"(?![a-z0-9])", low):
            return why
    for dom, why in EXTRA_REFUSED.items():
        if host == dom or host.endswith("." + dom):
            return why
    if not url and not host:
        return None
    try:
        from libs.data.refused_hosts import REFUSED_HOSTS
    except Exception as exc:                                          # pragma: no cover
        return f"refused-host list unimportable ({type(exc).__name__}); fail closed"
    for dom, why in REFUSED_HOSTS.items():
        if host == dom or host.endswith("." + dom):
            return why
    return None


# -------------------------------------------------------------------------------- cells ---
def _cell(ds: dict[str, Any], sym: str, side: int, stem: str, col: str, family: str,
          trad: list[str], ents: list[str]) -> dict[str, Any]:
    from proposer_common import candidate
    if family == RELEASE:
        params: dict[str, Any] = {"source": stem, "prior_sign": side, "column": col,
                                  "threshold": 1.0, "side": 1, "timeframe": CHART}
    else:
        params = {"source": stem, "signal": col, "transform": "level_z", "threshold": 1.0,
                  "side_when_high": side, "lag_hours": int(ds["lag_hours"]),
                  "timeframe": CHART}
    mech = (f"translation rule: dataset {ds['id']} ({ds['title'][:80]}) maps via "
            f"{', '.join(ents[:4]) or 'declared symbols'} to {sym}; its series {stem}.{col} "
            f"conditions {sym}")
    c = candidate(SEAT, sym, family, params, mech,
                  f"{family} on {stem}.{col} -> {sym} {CHART} [translated]",
                  {"dataset_id": ds["id"], "dataset_kind": ds["kind"], "entities": ents,
                   "mapped_tradables": trad[:24], "lag_hours": ds["lag_hours"]})
    c["chart"] = CHART
    c["required_data"] = [f"desks/mt5/data/lake/series/{stem}"]
    c["dataset_id"] = ds["id"]
    c["falsifier"] = (f"{stem}.{col} has no measurable relation to {sym} at {CHART} out of "
                      "sample once lagged past its publication")
    return c


def translate(datasets: list[dict[str, Any]], onto: dict[str, Any], registry: dict[str, str],
              stems: dict[str, Path], cursor: dict[str, Any], *,
              gate: Callable[[str, str], bool] | None, per_pass: int = PER_PASS
              ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """(rows, cells, new cursor). One cell per dataset per pass, newest dataset first from a
    rotating offset; a dataset with no series NEVER yields a cell."""
    state = dict(cursor.get("datasets") or {})
    rows: list[dict[str, Any]] = []
    ready: list[tuple[dict[str, Any], list[str], list[str], str, str, str]] = []
    for ds in datasets:
        trad, ents, why = infer(ds, onto, registry)
        row: dict[str, Any] = {"id": ds["id"], "kind": ds["kind"], "title": ds["title"][:120],
                               "host": ds["host"], "available_time": ds["available_time"],
                               "tradables": trad, "entities": ents,
                               "evidence": {s: why[s] for s in trad[:12]},
                               "event_like": ds["event_like"], "lag_hours": ds["lag_hours"],
                               "series_prefixes": ds["prefixes"],
                               "declared_tradables": [s for s in ds.get("declared") or []
                                                      if s in registry
                                                      and registry[s] != "Equities"]}
        refused = refusal_of(ds["url"], ds["host"], f"{ds['id']} {ds['title']}")
        if refused:
            row.update(status=UNMAPPABLE, reason=f"BLOCKED_ON_TERMS: {refused}",
                       would_map=trad, tradables=[],
                       missed_growth=(f"{ds['id']} is never used ({refused}); the "
                                      f"{len(trad)} tradables it maps to get no cell from it"))
            rows.append(row)
            continue
        if not trad:
            row.update(status=UNMAPPABLE,
                       reason=("no country, central bank, commodity or sector evidence in its "
                               "host, title, language, region or declared fields"))
            rows.append(row)
            continue
        found = series_for(ds, stems)
        usable = [(s, cols, fam) for s in found for cols, ok in [columns_of(stems[s])] if ok
                  and cols for fam in [RELEASE if ds["event_like"] and cols[0] == "surprise_z"
                                       else EXO]]
        if not usable:
            row.update(status=AWAITING, series_found=found,
                       reason=("no lake series under its prefixes yet" if not found else
                               "series present but without available_time or a numeric column"))
            rows.append(row)
            continue
        stem, cols, fam = usable[0]
        row.update(series=stem, signal=cols[0], family=fam)
        rows.append(row)
        ready.append((ds, trad, ents, stem, cols[0], fam))
    cells: list[dict[str, Any]] = []
    if gate is None:
        for row in rows:
            if row.get("series"):
                row.update(status=CELL_QUEUED,
                           reason="BLOCKED_DEPENDENCY: research.universe_policy unimportable")
        return rows, cells, {"datasets": state, "offset": cursor.get("offset", 0)}
    ready.sort(key=lambda t: str(t[0]["available_time"]), reverse=True)
    off = int(cursor.get("offset") or 0) % max(1, len(ready))
    order = ready[off:] + ready[:off]
    by_id = {r["id"]: r for r in rows}
    for ds, trad, ents, stem, col, fam in order:
        row = by_id[ds["id"]]
        st = state.setdefault(ds["id"], {"next": 0, "emitted": 0})
        grid = [(s, side) for s in trad if gate(s, fam) for side in SIDES]
        if not grid:
            row.update(status=UNMAPPABLE, reason="no mapped tradable is in the hypothesis lane")
            continue
        if len(cells) >= per_pass:
            row.update(status=CELL_EMITTED if st["emitted"] else CELL_QUEUED,
                       reason=None if st["emitted"] else "per-pass cap reached",
                       missed_growth=None if st["emitted"] else MISSED_GROWTH_CAP)
            continue
        sym, side = grid[int(st["next"]) % len(grid)]
        cells.append(_cell(ds, sym, side, stem, col, fam, trad, ents))
        st["next"] = (int(st["next"]) + 1) % len(grid)
        st["emitted"] = int(st["emitted"]) + 1
        row.update(status=CELL_EMITTED, cell={"symbol": sym, "side": side, "family": fam})
    new_off = (off + len(cells)) % max(1, len(ready))
    return rows, cells, {"datasets": state, "offset": new_off}


def summarise(rows: list[dict[str, Any]], dropped: Counter[str]) -> dict[str, Any]:
    n = len(rows)
    mapped = [r for r in rows if r.get("tradables")]
    declared = [r for r in rows if r.get("declared_tradables")]
    status = Counter(str(r.get("status")) for r in rows)
    unm = Counter(str(r.get("reason") or "").split(":")[0] for r in rows
                  if r.get("status") == UNMAPPABLE)
    top = Counter(s for r in mapped for s in r["tradables"])
    ents = Counter(e for r in mapped for e in r.get("entities") or [])
    kinds: dict[str, dict[str, int]] = {}
    for r in rows:
        k = kinds.setdefault(r["kind"], {"datasets": 0, "mapped": 0})
        k["datasets"] += 1
        k["mapped"] += 1 if r.get("tradables") else 0
    return {"datasets": n, "mapped": len(mapped),
            "wired_share": round(len(mapped) / n, 4) if n else None,
            "wired_share_declared_only": round(len(declared) / n, 4) if n else None,
            "by_status": dict(status), "unmappable_reasons": dict(unm), "by_kind": kinds,
            "top_tradables": top.most_common(25), "top_entities": ents.most_common(25),
            "dropped_not_in_registry": {"symbols": len(dropped), "count": sum(dropped.values()),
                                        "names": sorted(dropped)}}


def universe_gate() -> Callable[[str, str], bool] | None:
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return None

    def gate(sym: str, fam: str) -> bool:
        try:
            return bool(may_hypothesise(sym, fam))
        except Exception:
            return False                 # an unreadable verdict mints nothing here
    return gate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    registry = tradable_registry()
    onto, dropped = load_ontology(registry)
    stems = lake_stems(LAKE)
    datasets = enumerate_datasets(registry=registry, stems=stems, free_stack=FREE_STACK,
                                  deep_forest=DEEP_FOREST, axes=AXES, keyed=KEYED,
                                  env_keys=ENV_KEYS)
    cursor = _read(CURSOR, {}) or {}
    rows, cells, nxt = translate(datasets, onto, registry, stems, cursor, gate=universe_gate())
    path = None
    counts: dict[str, Any] = {}
    if cells and not a.dry_run:
        from proposer_common import donate, donation_counts
        path = donate(source=SEAT, candidates=cells, tests_run=len(cells))
        counts = donation_counts()
    if not a.dry_run:
        CURSOR.parent.mkdir(parents=True, exist_ok=True)
        CURSOR.write_text(json.dumps(nxt, indent=1), "utf-8")
    with_series = sum(1 for r in rows if r.get("series"))
    doc: dict[str, Any] = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "writer": "research/dataset_translator.py", "seat": SEAT,
        "rule": ("TRANSLATION RULE (principal, 2026-11-18): every dataset becomes a signal on a "
                 "traded FX pair, index, commodity CFD or metal; company-level data rolls up"),
        "status": "DRY_RUN" if a.dry_run else "RAN",
        **summarise(rows, dropped),
        "deep_forest_rows_raw": len(_jsonl(DEEP_FOREST)),
        "deep_forest_note": ("deep-forest rows are de-duplicated by URL: one page fetched twice "
                             "is one dataset"),
        "lake_series_on_host": len(stems), "datasets_with_series": with_series,
        "cells_built": len(cells), "per_pass_cap": PER_PASS,
        "passes_to_cover": -(-with_series // PER_PASS) if with_series else 0,
        "missed_growth": MISSED_GROWTH_CAP if with_series > PER_PASS else None,
        "minted": counts.get("donated", 0),
        "refused_wrong_lane": counts.get("refused_wrong_lane", 0),
        "refused_unstamped": counts.get("refused_unstamped", 0),
        "trials_charged": len(cells) if path else 0,
        "contract": str(path) if path else None,
        "families": list(EMITTED_FAMILIES),
        "seconds": round(time.monotonic() - t0, 2),
        "rows": sorted(rows, key=lambda r: str(r.get("available_time") or ""), reverse=True),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    print(f"dataset_translator: {doc['mapped']}/{doc['datasets']} mapped "
          f"(wired share {doc['wired_share']}; declared-only {doc['wired_share_declared_only']}),"
          f" {len(cells)} cells, by status {doc['by_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
