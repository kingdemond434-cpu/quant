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
import contextlib
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
#: Mapped and with a series, but another proposer (or the registry) already holds every cell the
#: translator would mint. Counts toward the wired share: the dataset IS a signal on a tradable.
COVERED = "COVERED_ELSEWHERE"

#: TERMS REFUSALS ARE READ, NOT RESTATED. Hosts come from `libs.data.refused_hosts.REFUSED_HOSTS`
#: (matched by suffix, and by the host's first label as a word of the dataset's id, which is how a
#: key-catalogue row whose URL is a sign-up console -- YOUTUBE_API_KEY, COMTRADE_API_KEY -- is
#: caught); a lake series published by `alt_proxies` is judged by that organ's own `TERMS`.
#: THIS LOCAL LIST HOLDS ONLY WHAT NEITHER CARRIES YET (2026-11-18), each by the worker-rule
#: ruling that names it, and an entry leaves the day `refused_hosts.py` carries it:
#:   * Reddit -- refused by the data and fetching law; absent from refused_hosts.py today.
#:   * IMF PortWatch -- the law says "pending reconciliation"; it is refused BY NAME below, never
#:     by its host: arcgis.com serves many unrelated public datasets, and refusing the host would
#:     black out every one of them. missed_growth: PortWatch's port-call and chokepoint boards
#:     stay unmapped until the quoted terms clause is recorded (Governance 2026-11-18).
LOCAL_REFUSED_HOSTS: dict[str, str] = {
    "reddit.com": "Reddit: Data API terms bar commercial use without an agreement",
}
LOCAL_REFUSED_NAMES: dict[str, str] = {
    "reddit": "Reddit: Data API terms bar commercial use without an agreement",
    "portwatch": "IMF PortWatch: terms pending reconciliation (alt_proxies.TERMS disagrees)",
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
        bare = re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", src.lower()) and not src.lower().endswith(
            (".csv", ".json", ".zip", ".txt"))
        url = src if "://" in src else (f"https://{src}" if bare else "")
        cur = " ".join(str(c) for c in d.get("currencies") or [])
        out.append(_ds(f"axis:{name}", "axis", title=f"{name} axis", url=url,
                       refused=axis_refusal(name),
                       declared=list(d.get("symbols") or []), text=f"{name} {src} {cur}",
                       available_time=str(d.get("at") or ""), prefixes=[f"axis_{p.stem}"]))
    return out


def axis_refusal(name: str) -> str | None:
    """The axis organ's own terms ruling (`axis_ingest.REFUSED_LAKE_AXES`), read, not restated.
    Unimportable fails closed."""
    try:
        from axis_ingest import REFUSED_LAKE_AXES
    except Exception as exc:                                          # pragma: no cover
        return f"axis_ingest.REFUSED_LAKE_AXES unimportable ({type(exc).__name__}); fail closed"
    return REFUSED_LAKE_AXES.get(name)


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


# ------------------------------------------------------------- cloud deep-forest claims ---
#: THE CLOUD DEEP-FOREST CLAIMS AS A DATASET FAMILY (hourly pass idea 25, 2026-11-18). The cloud
#: crawl's claim ledger lives on a mount the trading box cannot read, so a COMPACT DERIVED file
#: is committed instead, rebuilt by `--build-cloud-claims <ledger.jsonl>`. THE REPO IS PUBLIC: the
#: file holds identities and vocabulary buckets only -- never a claim's words, a title, a page
#: body or a URL path -- and `CLAIM_FIELDS` / `TELLING_FIELDS` are the whole of it (a test pins it).
#: Each mechanism_key is ONE record however many times it was told: ten tellings are one trial.
CLOUD_CLAIMS = DESK / "data" / "deep_forest_cloud_claims.json"
CLAIM_KIND = "deep_forest_claim"
CLAIM_FIELDS: frozenset[str] = frozenset({
    "mechanism_key", "mechanism_class", "analogues", "direction", "horizon", "quantity_kind",
    "lang", "event_time", "claim_hash", "host", "ingested_time", "tellings"})
TELLING_FIELDS: frozenset[str] = frozenset({"claim_hash", "host", "ingested_time", "event_time"})
#: H1 bars a claim's horizon bucket (`mechanism_claims._HOR_BUCKET_TERMS`) holds for. A horizon
#: the claim does not state uses the family's own declared `ttl_bars` default, read from its
#: signature, so the spec is still fixed before the judge sees it. A TICK horizon has no H1
#: builder: it is QUEUED, never stretched to an hour.
HOLD_BARS: dict[str, int] = {"intraday": 6, "daily": 24, "weekly": 120, "monthly": 480}
#: Why a class the deepener's own map (`rule_deepening.CLASS_FALLBACK`, then its
#: QUANTITY_FALLBACK) gives no price-only family is QUEUED: the builder it would need.
MISSING_BUILDER: dict[str, str] = {
    "carry": ("carry: the registered `carry` family takes its side from the broker swap, not "
              "from a claim; a claim-sided carry builder does not exist"),
    "policy": ("policy: needs `event_reaction` with a point-in-time policy-event calendar for the "
               "analogue; no such event feed is wired to a claim"),
    "calendar": ("calendar: `calendar_month` / `turn_of_month` need the month or day the claim "
                 "names, which the compact file does not carry"),
    "positioning": ("positioning: needs a positioning series (COT / retail ratio) conditioner on "
                    "the analogue; none is joined to a claim"),
    "inventory": ("inventory: needs an inventory-release series conditioner on the analogue; "
                  "none is joined to a claim"),
    "flow": "flow: needs a flow series conditioner on the analogue; none is joined to a claim",
    "cross_asset": ("cross_asset: needs a lead_lag / relative_value builder with the peer the "
                    "claim implies; the claim names no peer series"),
    "microstructure": ("microstructure: only a REVERT claim maps (range_reversion); other "
                       "microstructure claims need tick/order-book builders the desk lacks"),
    "momentum": "momentum: direction word in no bucket the deepener maps",
    "reversion": "reversion: direction word in no bucket the deepener maps",
    "other": ("other: the claim names no mechanism class and no breakout / reversion / momentum "
              "quantity, so no family is implied"),
}
_CLAIM_DIRECTION_SIDES: dict[str, int] = {"long": 1, "short": -1}


def _quantity_kind(quantities: Iterable[Any]) -> str:
    """The deepener's quantity bucket (`rule_deepening.QUANTITY_FALLBACK`), or ''."""
    from libs.research import rule_deepening as rd
    qlow = " ".join(str(q) for q in quantities or []).lower()
    for kind, terms in rd.QUANTITY_FALLBACK:
        if rd._first(terms, qlow):
            return kind
    return ""


def compact_cloud_claims(rows: Iterable[dict[str, Any]], *, source: str = "") -> dict[str, Any]:
    """The public, compact claim file from the cloud ledger's rows. Verbatim text never leaves:
    only the fields in CLAIM_FIELDS / TELLING_FIELDS are written. A row naming a crypto exchange
    is dropped (standing order), counted by reason."""
    from libs.research import mechanism_claims as mc
    by_key: dict[str, dict[str, Any]] = {}
    excluded: Counter[str] = Counter()
    n = 0
    for r in rows:
        n += 1
        mkey = str(r.get("mechanism_key") or "")
        if not mkey:
            excluded["no mechanism_key"] += 1
            continue
        if mc.forbidden_venue(str(r.get("claim") or "") + " " + str(r.get("title") or "")):
            excluded["crypto-exchange venue named (standing order)"] += 1
            continue
        ingested = str(r.get("ingested_time") or r.get("available_time")
                       or r.get("fetched_utc") or "")
        if not ingested:
            excluded["no ingestion time"] += 1
            continue
        inst = r.get("instruments") or {}
        tell = {"claim_hash": str(r.get("claim_hash") or ""), "host": host_of(r.get("url")),
                "ingested_time": ingested, "event_time": str(r.get("event_time") or "")}
        rec = by_key.get(mkey)
        if rec is None:
            by_key[mkey] = {
                "mechanism_key": mkey,
                "mechanism_class": str(r.get("mechanism_class") or "other"),
                "analogues": [str(a) for a in inst.get("analogues") or []],
                "direction": [str(w) for w in r.get("direction") or []],
                "horizon": [str(w) for w in r.get("horizon") or []],
                "quantity_kind": _quantity_kind(r.get("quantities") or []),
                "lang": str(r.get("lang") or r.get("language") or ""),
                "tellings": [tell]}
            continue
        rec["tellings"].append(tell)
        for k, vals in (("analogues", inst.get("analogues")), ("direction", r.get("direction")),
                        ("horizon", r.get("horizon"))):
            for v in vals or []:
                if str(v) not in rec[k]:
                    rec[k].append(str(v))
        rec["quantity_kind"] = rec["quantity_kind"] or _quantity_kind(r.get("quantities") or [])
    claims = []
    for rec in by_key.values():
        rec["tellings"].sort(key=lambda t: t["ingested_time"])
        first = rec["tellings"][0]
        # THE KNOWABLE TIME IS THE EARLIEST INGESTION, never the claim's own event_time.
        rec.update(claim_hash=first["claim_hash"], host=first["host"],
                   ingested_time=first["ingested_time"], event_time=first["event_time"])
        claims.append(rec)
    claims.sort(key=lambda c: (c["ingested_time"], c["mechanism_key"]))
    return {"writer": "research/dataset_translator.py --build-cloud-claims",
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": source, "ledger_rows": n, "claims": len(claims),
            "excluded": dict(excluded),
            "note": ("derived identities and vocabulary buckets only; no claim text, title, page "
                     "body or URL path. knowable time = earliest ingested_time of the key"),
            "rows": claims}


def build_cloud_claims(ledger: Path, out: Path = CLOUD_CLAIMS) -> dict[str, Any]:
    doc = compact_cloud_claims(_jsonl(ledger), source=ledger.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return doc


def _cloud_claims(path: Path) -> list[dict[str, Any]]:
    """One dataset row per mechanism_key in the compact file. A telling from a refused host is
    dropped before the knowable time is taken; a key with no usable telling is refused."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in (_read(path, {}) or {}).get("rows") or []:
        mkey = str((rec or {}).get("mechanism_key") or "")
        if not mkey or mkey in seen:
            continue
        seen.add(mkey)
        tells = [t for t in rec.get("tellings") or [] if isinstance(t, dict)]
        ok = [t for t in tells if not refusal_of("", str(t.get("host") or ""))]
        refused = None
        if tells and not ok:
            refused = refusal_of("", str(tells[0].get("host") or ""))
        use = sorted(ok or tells, key=lambda t: str(t.get("ingested_time") or ""))
        knowable = str((use[0] if use else rec).get("ingested_time") or "")
        cls = str(rec.get("mechanism_class") or "other")
        out.append(_ds(f"dfc:{mkey}", CLAIM_KIND, title=f"deep-forest claim {mkey} ({cls})",
                       host=str((use[0] if use else rec).get("host") or ""),
                       lang=str(rec.get("lang") or ""),
                       declared=[str(a) for a in rec.get("analogues") or []],
                       available_time=knowable, refused=refused,
                       claim={**rec, "knowable_at": knowable, "n_tellings": len(ok or tells)}))
    return out


def claim_tradables(analogues: Iterable[str], registry: dict[str, str], onto: dict[str, Any]
                    ) -> tuple[list[str], list[str], list[str]]:
    """(tradables, rolled-up shares, dropped). A share CFD analogue is ROLLED UP to the US index
    set, never minted; a symbol the registry lacks is dropped and counted."""
    trad: list[str] = []
    rolled: list[str] = []
    dropped: list[str] = []
    for a in analogues:
        cls = registry.get(a)
        if cls is None:
            dropped.append(a)
        elif cls == "Equities":
            rolled.append(a)
        elif a not in trad:
            trad.append(a)
    if rolled:
        for s in ((onto.get("countries") or {}).get("US") or {}).get("index") or []:
            if s in registry and registry[s] != "Equities" and s not in trad:
                trad.append(s)
    return trad, rolled, dropped


def _family_default_hold(fam: str) -> int | None:
    import inspect

    from mt5desk.executables import resolve_family
    fn = resolve_family(fam)
    try:
        p = inspect.signature(fn).parameters.get("ttl_bars") if fn else None
    except (TypeError, ValueError):
        return None
    return int(p.default) if p is not None and isinstance(p.default, int) else None


def claim_spec(claim: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """({family, hold, sides, buckets}, None) -- or (None, the QUEUED reason). The family comes
    ONLY from the deepener's own class map and quantity fallback, and only when registered."""
    from mt5desk.executables import resolve_family

    from libs.research import mechanism_claims as mc
    from libs.research import rule_deepening as rd
    cls = str(claim.get("mechanism_class") or "other")
    words = [str(w) for w in claim.get("direction") or []]
    dbucket = mc._bucket(mc._DIR_BUCKET_TERMS, words)
    hbucket = mc._bucket(mc._HOR_BUCKET_TERMS, [str(w) for w in claim.get("horizon") or []])
    fam = rd.CLASS_FALLBACK.get((cls, dbucket))
    basis = "class_map"
    qk = str(claim.get("quantity_kind") or "")
    if fam is None and dbucket != "other" and qk:
        basis = f"quantity_fallback:{qk}"
        # The deepener's quantity map; with no session in the compact file a breakout is a level
        # breakout (rule_deepening.deepen picks session_range_breakout only on a named session).
        fam = {"breakout": "level_breakout", "reversion": "range_reversion",
               "momentum": "momentum_volgate"}.get(qk)
    base = {"class": cls, "direction_bucket": dbucket, "horizon_bucket": hbucket,
            "family_basis": basis}
    if fam is None:
        return None, f"NO_BUILDER: {MISSING_BUILDER.get(cls, cls + ': no registered builder')}"
    if resolve_family(fam) is None:
        return None, f"NO_BUILDER: {fam} has no registered builder on this tree"
    if hbucket == "tick":
        return None, "NO_BUILDER: a tick-horizon claim has no sub-bar builder on H1"
    hold = HOLD_BARS.get(hbucket) or _family_default_hold(fam)
    if hold is None:
        return None, f"NO_BUILDER: {fam} declares no ttl_bars default and the claim states none"
    buckets = {mc._bucket(mc._DIR_BUCKET_TERMS, [w]) for w in words} & set(_CLAIM_DIRECTION_SIDES)
    sides = ((_CLAIM_DIRECTION_SIDES[next(iter(buckets))],) if len(buckets) == 1 else SIDES)
    return {**base, "family": fam, "hold": int(hold), "sides": sides}, None


def _claim_cell(ds: dict[str, Any], sym: str, side: int, spec: dict[str, Any],
                trad: list[str]) -> dict[str, Any]:
    from proposer_common import candidate
    cl = ds["claim"]
    fam = spec["family"]
    params = {"ttl_bars": spec["hold"], "side_mode": "long" if side > 0 else "short"}
    mech = (f"deep-forest claim {cl['mechanism_key']} (class {spec['class']}, direction "
            f"{spec['direction_bucket']}, horizon {spec['horizon_bucket']}, "
            f"{cl.get('n_tellings', 1)} telling(s), lang {ds['lang'] or '?'}) on analogue "
            f"{sym}: {fam} {params['side_mode']}, held {spec['hold']} {CHART} bars")
    c = candidate(SEAT, sym, fam, params, mech,
                  f"{fam} {params['side_mode']} ttl{spec['hold']} -> {sym} {CHART} "
                  "[deep-forest claim]",
                  {"dataset_id": ds["id"], "dataset_kind": CLAIM_KIND,
                   "mechanism_key": cl["mechanism_key"], "claim_hash": cl.get("claim_hash"),
                   "mapped_tradables": trad[:24], "knowable_at": cl["knowable_at"],
                   "forward_evidence_from": cl["knowable_at"],
                   "preregistered_from": "claim: horizon -> ttl_bars, direction -> side_mode"})
    c["chart"] = CHART
    c["dataset_id"] = ds["id"]
    c["mechanism_key"] = cl["mechanism_key"]
    # POINT IN TIME: the claim was knowable when the desk INGESTED it. `pit.stamp` keeps a field
    # the producer set, so the donated row carries this, not the claim's (earlier) event_time;
    # bars before it are in-sample history to the judge, and no forward clock can start earlier.
    c["available_time"] = cl["knowable_at"]
    c["knowable_at"] = cl["knowable_at"]
    if cl.get("event_time"):
        c["event_time"] = str(cl["event_time"])
    c["falsifier"] = (f"{fam} {params['side_mode']} on {sym} held {spec['hold']} {CHART} bars "
                      f"shows no edge net of cost in bars after {cl['knowable_at']}")
    return c


def lake_stems(lake: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if lake.is_dir():
        for p in sorted(lake.iterdir()):
            if p.suffix in (".parquet", ".csv") and p.stem not in out:
                out[p.stem] = p
    return out


def enumerate_datasets(*, registry: dict[str, str], stems: dict[str, Path],
                       free_stack: Path = FREE_STACK, deep_forest: Path = DEEP_FOREST,
                       axes: Path = AXES, keyed: Path = KEYED, env_keys: Path = ENV_KEYS,
                       cloud_claims: Path = CLOUD_CLAIMS) -> list[dict[str, Any]]:
    """Every dataset the desk holds, from every ground. A lake series no roster row claims is a
    dataset in its own right, so a series that lands from any producer is translated too. The
    cloud deep-forest claims are a dataset family of their own (one row per mechanism_key)."""
    rows = (_free_stack(free_stack) + _deep_forest(deep_forest) + _axes(axes) + _keyed(keyed)
            + _key_feeds(env_keys, registry))
    claims = _cloud_claims(cloud_claims)
    claimed = {s for r in rows for s in stems if any(s.startswith(p) for p in r["prefixes"])}
    for stem in sorted(set(stems) - claimed):
        cc = stem.split("_", 1)[0]
        out = _ds(f"lake:{stem}", "lake", title=stem, text=stem.replace("_", " "),
                  region=cc if len(cc) == 2 else "", prefixes=[stem])
        out["exact_series"] = True
        rows.append(out)
    return rows + claims


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


def _id_words(name: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", name.lower()) if w}


def refusal_of(url: str, host: str, name: str = "") -> str | None:
    """Why the dataset may not be used, or None. `name` is the dataset's id. An unimportable
    host list fails CLOSED; an unimportable alt_proxies.TERMS fails closed for its series."""
    words = _id_words(name)
    try:
        from libs.data.refused_hosts import REFUSED_HOSTS
    except Exception as exc:                                          # pragma: no cover
        return f"refused-host list unimportable ({type(exc).__name__}); fail closed"
    hosts = {**REFUSED_HOSTS, **LOCAL_REFUSED_HOSTS}
    for dom, why in hosts.items():
        if host and (host == dom or host.endswith("." + dom)):
            return why
        if dom.split(".")[0] in words:
            return why
    for word, why in LOCAL_REFUSED_NAMES.items():
        if word in words:
            return why
    m = re.search(r"(?:^|[:_])alt_([a-z0-9_]+?)__", name.lower())
    if m:
        try:
            from alt_proxies import TERMS
        except Exception as exc:                                      # pragma: no cover
            return f"alt_proxies.TERMS unimportable ({type(exc).__name__}); fail closed"
        state, why = TERMS.get(m.group(1), ("to_confirm", "no TERMS row"))
        if state != "confirmed":
            return f"alt_proxies.TERMS {state}: {why}"
    return None


# ------------------------------------------------------------------------------ coverage ---
class Coverage:
    """WHAT ANOTHER PROPOSER ALREADY MINTS, so no translator cell is a second trial.

    Trial count is a shared multiple-testing cost (CLAUDE.md, TWO LANES): a cell that repeats one
    the desk already charged raises the bar every other hypothesis must clear and buys nothing.
    Three layers, each keyed WITHOUT the parameters, so nothing slips past on lag_hours alone:
      * `owners`  -- a series a proposer mints from by construction (free stack: `fs_<id>` with
        signal columns; keyed roster: `ks_<id>__<series>` with mapped instruments);
      * `pairs`   -- every (params.source, symbol) already in the canonical registry;
      * `exists`  -- the registry's own dedupe identity (`registry.content_hash` over family,
        symbol, params and chart), the key that makes two cells one trial.
    """

    def __init__(self, owners: dict[str, str], pairs: set[tuple[str, str]],
                 exists: Callable[[dict[str, Any]], bool]) -> None:
        self.owners = owners
        self.pairs = pairs
        self._exists = exists

    @classmethod
    def empty(cls) -> Coverage:
        return cls({}, set(), lambda _c: False)

    def owner(self, stem: str) -> str | None:
        return self.owners.get(stem)

    def covered(self, stem: str, sym: str) -> bool:
        return (stem, sym) in self.pairs

    def exists(self, cell: dict[str, Any]) -> bool:
        return self._exists(cell)


#: LAKE PREFIXES WHOSE WRITER MINTS ITS OWN CELLS on the series it publishes (Auditor SF1,
#: 2026-11-18). A newly landed series under one of these is its writer's trial, never the
#: translator's: minting first would make the owner's own cell a second, differently-
#: parameterised trial that neither the pair index nor content_hash can see.
SELF_MINTING_PREFIXES: dict[str, str] = {
    "alt_": "alt_proxies",
    "mes_": "macro_event_states",
    "axis_": "axis_proposer",
    "latent_": "macro_state_engine",
    "nlp_events_": "nlp_event_factors / nlp_social_cells",
    "blog_social_": "nlp_social_cells",
}


def proposer_owners(stems: Iterable[str], fs_columns: Path | None = None,
                    keyed: Path | None = None) -> dict[str, str]:
    """{stem: proposer} for every lake series another proposer mints from: the free-stack and
    keyed proposers by their manifests, and every self-minting writer by its lake prefix."""
    cols = _read(fs_columns or FS_COLUMNS, {}) or {}
    ks: dict[str, str] = {}
    for r in (_read(keyed or KEYED, {}) or {}).get("sources") or []:
        for name, s in ((r or {}).get("series") or {}).items():
            if isinstance(s, dict) and s.get("instruments"):
                ks[f"ks_{r.get('id')}__{name}"] = "keyed_sources"
    out: dict[str, str] = {}
    for stem in stems:
        own = next((o for p, o in SELF_MINTING_PREFIXES.items() if stem.startswith(p)), None)
        if own:
            out[stem] = own
        elif stem.startswith("fs_") and cols.get(stem[3:]):
            out[stem] = "free_stack_proposer"
        elif stem in ks:
            out[stem] = ks[stem]
    return out


class RegistryIndex:
    """A read-only handle on the canonical registry: its (params.source, symbol) pairs and its
    content-hash identity. Close it (or use it as a context manager) when the pass is done."""

    def __init__(self, conn: Any, pairs: set[tuple[str, str]]) -> None:
        self.conn = conn
        self.pairs = pairs

    def exists(self, cell: dict[str, Any]) -> bool:
        from libs.moat import registry as reg
        h = reg.content_hash(str(cell.get("family") or ""), str(cell.get("symbol") or ""),
                             cell.get("params") or {}, str(cell.get("chart") or ""))
        try:
            return self.conn.execute("SELECT 1 FROM research_candidates WHERE content_hash=? "
                                     "LIMIT 1", (h,)).fetchone() is not None
        except Exception:
            return True                  # an unreadable identity is treated as a duplicate

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()

    def __enter__(self) -> RegistryIndex:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def registry_coverage(db: Path | None = None) -> RegistryIndex | None:
    """The registry's pairs and identity, or None when it cannot be read -- and then the
    translator mints NOTHING: an unread dedupe is not a clean one."""
    import sqlite3
    try:
        from libs.moat import registry as reg
        path = Path(db or reg.path())
        if not path.exists():
            return None
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30)
    except Exception:
        return None
    pairs: set[tuple[str, str]] = set()
    try:
        for sym, pj in conn.execute("SELECT symbol, params_json FROM research_candidates "
                                    "WHERE params_json LIKE '%\"source\"%'"):
            try:
                src = (json.loads(pj or "{}") or {}).get("source")
            except ValueError:
                continue
            if src:
                pairs.add((str(src), str(sym)))
    except Exception:
        conn.close()
        return None
    return RegistryIndex(conn, pairs)


# -------------------------------------------------------------------------------- cells ---
def _cell(ds: dict[str, Any], sym: str, side: int, stem: str, col: str, family: str,
          trad: list[str], ents: list[str]) -> dict[str, Any]:
    from proposer_common import candidate
    if family == RELEASE:
        params: dict[str, Any] = {"source": stem, "prior_sign": side, "column": col,
                                  "threshold": 1.0, "side": 1, "timeframe": CHART}
    else:
        params = {"source": stem, "signal": col, "transform": "level_z", "threshold": 1.0,
                  "side_when_high": side, "timeframe": CHART}
        if int(ds["lag_hours"]) > DEFAULT_LAG_H:     # the family's own default is 24h
            params["lag_hours"] = int(ds["lag_hours"])
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
              gate: Callable[[str, str], bool] | None, coverage: Coverage | None,
              per_pass: int = PER_PASS
              ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """(rows, cells, new cursor). One cell per dataset per pass, newest dataset first from a
    rotating offset; a dataset with no series NEVER yields a cell, and no cell repeats a
    (series, tradable) another proposer already mints or the registry already holds."""
    state = dict(cursor.get("datasets") or {})
    rows: list[dict[str, Any]] = []
    ready: list[tuple[dict[str, Any], list[str], list[str], str, str, str]] = []
    claim_ready: list[tuple[dict[str, Any], list[str], dict[str, Any]]] = []
    for ds in datasets:
        if ds["kind"] == CLAIM_KIND:
            got = _claim_row(ds, onto, registry)
            rows.append(got[0])
            if got[1] is not None:
                claim_ready.append((ds, got[0]["tradables"], got[1]))
            continue
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
        refused = ds.get("refused") or refusal_of(ds["url"], ds["host"], ds["id"])
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
    #: ONE PASS, ONE TRIAL PER (stem, symbol, side, family): two datasets resolving to the same
    #: lake stem would otherwise mint the same cell twice and charge the trial census twice.
    minted: set[tuple[str, str, int, str]] = set()
    if gate is None or coverage is None:
        why = ("research.universe_policy unimportable" if gate is None else
               "the registry's dedupe identity is unreadable, so a cell could be a second trial")
        for row in rows:
            if row.get("series") or row.get("claim_spec"):
                row.update(status=CELL_QUEUED, reason=f"BLOCKED_DEPENDENCY: {why}",
                           missed_growth=("the series waits for the dependency; no cell is "
                                          "lost, it is judged the first pass both are readable"))
        return rows, cells, {"datasets": state, "offset": cursor.get("offset", 0),
                             "claims_offset": cursor.get("claims_offset", 0)}
    ready.sort(key=lambda t: str(t[0]["available_time"]), reverse=True)
    off = int(cursor.get("offset") or 0) % max(1, len(ready))
    order = ready[off:] + ready[:off]
    by_id = {r["id"]: r for r in rows}
    for ds, trad, ents, stem, col, fam in order:
        row = by_id[ds["id"]]
        st = state.setdefault(ds["id"], {"next": 0, "emitted": 0})
        owner = coverage.owner(stem)
        if owner:
            row.update(status=COVERED, covered_by=owner,
                       reason=f"{owner} already mints from {stem}; a translator cell would be a "
                              "second trial")
            continue
        lane = [s for s in trad if gate(s, fam)]
        grid = [(s, side) for s in lane if not coverage.covered(stem, s) for side in SIDES]
        if not lane:
            row.update(status=UNMAPPABLE, reason="no mapped tradable is in the hypothesis lane")
            continue
        if not grid:
            row.update(status=COVERED, covered_by="registry",
                       reason=f"every mapped tradable already has a registry cell on {stem}")
            continue
        if len(cells) >= per_pass:
            row.update(status=CELL_EMITTED if st["emitted"] else CELL_QUEUED,
                       reason=None if st["emitted"] else "per-pass cap reached",
                       missed_growth=None if st["emitted"] else MISSED_GROWTH_CAP)
            continue
        cell = None
        for k in range(len(grid)):
            sym, side = grid[(int(st["next"]) + k) % len(grid)]
            key = (stem, sym, int(side), fam)
            if key in minted:
                continue
            cand = _cell(ds, sym, side, stem, col, fam, trad, ents)
            if not coverage.exists(cand):
                minted.add(key)
                cell = cand
                st["next"] = (int(st["next"]) + k + 1) % len(grid)
                break
        if cell is None:
            row.update(status=COVERED, covered_by="registry",
                       reason="every (tradable, side) is already a registry trial or was "
                              "minted earlier this pass")
            continue
        cells.append(cell)
        st["emitted"] = int(st["emitted"]) + 1
        row.update(status=CELL_EMITTED,
                   cell={"symbol": cell["symbol"], "side": side, "family": fam})
    new_off = (off + len(cells)) % max(1, len(ready))
    coff = _mint_claims(claim_ready, by_id, state, cells, minted, cursor, gate=gate,
                        coverage=coverage, per_pass=per_pass)
    return rows, cells, {"datasets": state, "offset": new_off, "claims_offset": coff}


def _claim_row(ds: dict[str, Any], onto: dict[str, Any], registry: dict[str, str]
               ) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """(report row, spec or None) for one cloud claim, before any gate or dedupe."""
    cl = ds["claim"]
    trad, rolled, dropped = claim_tradables(ds.get("declared") or [], registry, onto)
    row: dict[str, Any] = {"id": ds["id"], "kind": CLAIM_KIND, "title": ds["title"],
                           "host": ds["host"], "available_time": ds["available_time"],
                           "knowable_at": cl.get("knowable_at"),
                           "event_time": cl.get("event_time") or None,
                           "mechanism_key": cl.get("mechanism_key"),
                           "mechanism_class": cl.get("mechanism_class") or "other",
                           "tradables": trad, "entities": [f"claim:{cl.get('mechanism_class')}"]
                           + (["rollup:US_equities"] if rolled else []),
                           "rolled_up": rolled, "dropped_not_in_registry": dropped,
                           "n_tellings": cl.get("n_tellings"),
                           "declared_tradables": [s for s in ds.get("declared") or []
                                                  if s in registry
                                                  and registry[s] != "Equities"]}
    if ds.get("refused"):
        row.update(status=UNMAPPABLE, reason=f"BLOCKED_ON_TERMS: {ds['refused']}",
                   would_map=trad, tradables=[],
                   missed_growth=(f"{ds['id']} is never used ({ds['refused']}); the "
                                  f"{len(trad)} tradables it maps to get no cell from it"))
        return row, None
    if not trad:
        row.update(status=UNMAPPABLE, reason="no analogue the broker registry prices")
        return row, None
    spec, why = claim_spec(cl)
    if spec is None:
        row.update(status=CELL_QUEUED, reason=why,
                   missed_growth=(f"claim {cl.get('mechanism_key')} on {', '.join(trad[:4])} "
                                  "is never judged until the named builder exists"))
        return row, None
    row.update(claim_spec={k: (list(v) if isinstance(v, tuple) else v)
                           for k, v in spec.items()}, family=spec["family"])
    return row, spec


def _mint_claims(ready: list[tuple[dict[str, Any], list[str], dict[str, Any]]],
                 by_id: dict[str, dict[str, Any]], state: dict[str, Any],
                 cells: list[dict[str, Any]], minted: set[tuple[str, str, int, str]],
                 cursor: dict[str, Any], *, gate: Callable[[str, str], bool],
                 coverage: Coverage, per_pass: int) -> int:
    """One cell per claim per pass, on the claim's own (tradable, side) ring, through the same
    dedupe layers as the series cells. Returns the next claims offset."""
    ready = sorted(ready, key=lambda t: str(t[0]["available_time"]), reverse=True)
    off = int(cursor.get("claims_offset") or 0) % max(1, len(ready))
    before = len(cells)
    for ds, trad, spec in ready[off:] + ready[:off]:
        row = by_id[ds["id"]]
        st = state.setdefault(ds["id"], {"next": 0, "emitted": 0})
        fam = spec["family"]
        stem = f"dfc_{ds['claim']['mechanism_key']}"
        owner = coverage.owner(stem)
        if owner:
            row.update(status=COVERED, covered_by=owner,
                       reason=f"{owner} already mints this claim; a cell would be a second trial")
            continue
        lane = [s for s in trad if gate(s, fam)]
        if not lane:
            row.update(status=UNMAPPABLE, reason="no mapped tradable is in the hypothesis lane")
            continue
        grid = [(s, side) for s in lane if not coverage.covered(stem, s)
                for side in spec["sides"]]
        if not grid:
            row.update(status=COVERED, covered_by="registry",
                       reason=f"every mapped tradable already has a registry cell on {stem}")
            continue
        if len(cells) >= per_pass:
            row.update(status=CELL_EMITTED if st["emitted"] else CELL_QUEUED,
                       reason=None if st["emitted"] else "per-pass cap reached",
                       missed_growth=None if st["emitted"] else MISSED_GROWTH_CAP)
            continue
        cell = None
        side = 0
        for k in range(len(grid)):
            sym, side = grid[(int(st["next"]) + k) % len(grid)]
            # The spec IS the trial: two claims (or two keys) resolving to the same family, hold,
            # tradable and side are one cell, whatever the claims' words.
            key = (f"claim:ttl{spec['hold']}", sym, int(side), fam)
            if key in minted:
                continue
            cand = _claim_cell(ds, sym, side, spec, trad)
            if not coverage.exists(cand):
                minted.add(key)
                cell = cand
                st["next"] = (int(st["next"]) + k + 1) % len(grid)
                break
        if cell is None:
            row.update(status=COVERED, covered_by="registry",
                       reason="every (tradable, side) is already a registry trial or was "
                              "minted earlier this pass")
            continue
        cells.append(cell)
        st["emitted"] = int(st["emitted"]) + 1
        row.update(status=CELL_EMITTED,
                   cell={"symbol": cell["symbol"], "side": side, "family": fam,
                         "ttl_bars": spec["hold"]})
    return (off + len(cells) - before) % max(1, len(ready))


def claims_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Cloud-claim counts by class and status, and the classes with no builder."""
    by_class: dict[str, Counter[str]] = {}
    nob: Counter[str] = Counter()
    for r in rows:
        if r.get("kind") != CLAIM_KIND:
            continue
        cls = str(r.get("mechanism_class") or "other")
        by_class.setdefault(cls, Counter())[str(r.get("status"))] += 1
        if str(r.get("reason") or "").startswith("NO_BUILDER"):
            nob[cls] += 1
    from libs.research import rule_deepening as rd
    mapped = {c for c, _ in rd.CLASS_FALLBACK}
    return {"claims": sum(sum(c.values()) for c in by_class.values()),
            # Classes the deepener's class map gives no family: they reach a cell only through
            # the quantity fallback, otherwise they are queued with the builder they lack.
            "classes_without_class_builder": sorted(k for k in by_class if k not in mapped),
            "by_class": {k: dict(v) for k, v in sorted(by_class.items())},
            "queued_no_builder_by_class": dict(nob),
            "classes_without_any_cell": sorted(k for k, v in by_class.items()
                                               if not v.get(CELL_EMITTED))}


def summarise(rows: list[dict[str, Any]], dropped: Counter[str]) -> dict[str, Any]:
    """The wired share is a fact about DATASETS: cloud claims are counted in `cloud_claims`
    (`claims_summary`), never in the share, so 375 claim rows cannot inflate it."""
    rows = [r for r in rows if r.get("kind") != CLAIM_KIND]
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
    ap.add_argument("--build-cloud-claims", metavar="LEDGER", type=Path,
                    help="rebuild data/deep_forest_cloud_claims.json from the cloud claim ledger")
    a = ap.parse_args(argv)
    if a.build_cloud_claims:
        built = build_cloud_claims(a.build_cloud_claims)
        print(f"dataset_translator: {built['claims']} mechanism keys from "
              f"{built['ledger_rows']} ledger rows -> {CLOUD_CLAIMS.name}")
        return 0
    t0 = time.monotonic()
    registry = tradable_registry()
    onto, dropped = load_ontology(registry)
    stems = lake_stems(LAKE)
    datasets = enumerate_datasets(registry=registry, stems=stems, free_stack=FREE_STACK,
                                  deep_forest=DEEP_FOREST, axes=AXES, keyed=KEYED,
                                  env_keys=ENV_KEYS, cloud_claims=CLOUD_CLAIMS)
    cursor = _read(CURSOR, {}) or {}
    rc = registry_coverage()
    coverage = None if rc is None else Coverage(proposer_owners(stems), rc.pairs, rc.exists)
    try:
        rows, cells, nxt = translate(datasets, onto, registry, stems, cursor,
                                     gate=universe_gate(), coverage=coverage)
    finally:
        if rc is not None:
            rc.close()
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
        "registry_dedupe": ("UNREADABLE: nothing minted" if coverage is None else
                            {"registry_pairs": len(coverage.pairs),
                             "proposer_owned_series": len(coverage.owners)}),
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
        "cloud_claims": {"file": CLOUD_CLAIMS.name,
                         **claims_summary(rows)},
        "seconds": round(time.monotonic() - t0, 2),
        "rows": sorted(rows, key=lambda r: str(r.get("available_time") or ""), reverse=True),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    print(f"dataset_translator: {doc['mapped']}/{doc['datasets']} mapped "
          f"(wired share {doc['wired_share']}; declared-only {doc['wired_share_declared_only']}),"
          f" {len(cells)} cells, by status {doc['by_status']}; cloud claims "
          f"{doc['cloud_claims']['claims']} ({doc['cloud_claims']['by_class']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
