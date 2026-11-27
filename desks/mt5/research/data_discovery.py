"""LLM DATA DISCOVERY -- the free-model generators propose the DATA, not only the cells.

THE GAP (principal, 2026-11-25). `alt_catalog` hands the free-model generators (kimi_hunter waves
2/3, the DeepSeek cold phase) every lake series the gauntlet can apply as an `alt:` conditioner.
But the lake is written only by organs a human wired: the generators could condition on what the
desk already holds and never ask for what it lacks. An indirect edge often sits in a series nobody
here has thought to fetch -- a central bank's balance-sheet line, a trade-weighted index, an
official survey diffusion index -- and every one of those is public, keyless and machine-readable.

WHAT THIS IS. A library with no clock of its own; its readers are on clocks:

  prompt_block()   a small "propose a data source" task each generator pass: up to MAX_PER_REPLY
                   series from KEYLESS OFFICIAL SDMX providers (`PROVIDERS`), each named by its
                   dataflow and ONE series key, the release frequency and lag, the MT5 instruments
                   it should move and the mechanism (an indirect edge, not a restatement).
  parse_lines()    kimi's `DATA_SOURCE | ...` lines -> raw proposal dicts (DeepSeek returns the
                   same fields as JSON in `data_sources`).
  vet()            STRICT schema and the hard boundaries, fail closed: provider on the allowlist
                   (the URL is BUILT here from the provider's own base -- the model never supplies
                   a host), dataflow and key structurally valid with exactly ONE series (no
                   wildcard, no OR), no key / token / paid / login vocabulary, no crypto-exchange
                   ground, MT5 hypothesis-lane instruments only, a stated mechanism, and a release
                   lag never SHORTER than the frequency's floor (late costs edge, early invents it).
  record()         the seat's single queue file
                   `data/intelligence/<seat>/data_source_proposals.json`: counts, rejections
                   by reason, and the accepted proposals.
  discovered_rows() what `research/keyed_sources.py` (the box's hourly keyless/keyed fetcher)
                   unions into its roster: each accepted proposal RE-VETTED on the reading host and
                   rebuilt as an ordinary `kind: sdmx`, `key_env: []` row. That organ fetches it on
                   its own clock with its own fences (machine_use_allowed, terms, budget,
                   stalest-first), stores it point-in-time, publishes `ks_<id>__<series>.csv` with
                   trailing z / chg_z (verified PIT in `alt_catalog.PIT_Z_COLUMNS`), mints its
                   direct and indirect cells, and `alt_catalog` then offers the series back to the
                   generators. No new fetcher and no fetch-any-URL executor exist here.
  provenance()     lake series -> {discovered_by, method, ...}, so a cell on a discovered series
                   carries who found the data; `method_view()` is the funnel's `by_method` block.

Nothing here judges, sizes or charges: the cells minted on a discovered series are charged where
keyed_sources and the compiler already charge them, and the bar never moves because a model found
a series. An unreadable queue is UNMEASURED, never 0 (L1.28a).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
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
METHOD = "llm_data_discovery"
#: The free-model JOB name (the shared job registry / FUNNEL `by_lane` key) and its own seat.
LANE = "data_discovery"
QUEUE_NAME = "data_source_proposals.json"
#: Where seat output lives (the compiler reads both roots; so does this intake).
INTEL_ROOTS: tuple[Path, ...] = (ROOT / "data" / "intelligence", DESK / "data" / "intelligence")
LAKE = DESK / "data" / "lake" / "series"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
ID_PREFIX = "disc_"
#: Proposals read per reply (a flood is not breadth).
MAX_PER_REPLY = 6
#: Rejection samples kept in the queue file (the counters keep every one).
KEEP_REJECTIONS = 60
LINE = re.compile(r"^\s*DATA_SOURCE\s*\|", re.IGNORECASE)

#: KEYLESS OFFICIAL SDMX PROVIDERS -- the only hosts a proposal can reach. Every one serves
#: SDMX-CSV (TIME_PERIOD / OBS_VALUE, which `libs.data.keyed_sources.parse_sdmx_csv` reads) from
#: a public statistical API built for machine use, with free reuse under attribution. `suffix`
#: is appended to `<dataflow>/<key>` to ask for CSV; the base is the provider's own data root.
PROVIDERS: dict[str, dict[str, str]] = {
    "BIS": {"base": "https://stats.bis.org/api/v1/data/", "suffix": "/all?format=csv",
            "licence": "BIS statistics terms (free reuse with attribution)", "region": "GLOBAL"},
    "OECD": {"base": "https://sdmx.oecd.org/public/rest/data/", "suffix": "?format=csvfile",
             "licence": "OECD terms (CC BY 4.0)", "region": "GLOBAL"},
    "IMF": {"base": "https://api.imf.org/external/sdmx/2.1/data/", "suffix": "?format=csv",
            "licence": "IMF data terms (free reuse with attribution)", "region": "GLOBAL"},
    "ECB": {"base": "https://data-api.ecb.europa.eu/service/data/", "suffix": "?format=csvdata",
            "licence": "ECB statistics reuse policy (free reuse with attribution)",
            "region": "EU"},
    "EUROSTAT": {"base": "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/",
                 "suffix": "?format=SDMX-CSV",
                 "licence": "Eurostat copyright notice (CC BY 4.0, free reuse)", "region": "EU"},
}
#: Minimum release lag by frequency, in days. A model-declared lag below it is RAISED to it: a
#: backfilled value is stamped at period end + lag, so a short lag would back-date the history.
LAG_FLOOR_DAYS = {"D": 2, "W": 8, "M": 35, "Q": 100}
FREQS = tuple(LAG_FLOOR_DAYS)
MAX_LAG_DAYS = 400
FLOW = re.compile(r"^[A-Za-z0-9_.,@\-]{2,80}$")
#: One series: dot-separated non-empty segments, no wildcard, no OR (`+`), nothing URL-shaped.
KEY = re.compile(r"^[A-Za-z0-9_\-]{1,24}(\.[A-Za-z0-9_\-]{1,24}){0,11}$")
SYMBOL = re.compile(r"^[A-Z0-9.]{3,12}$")
#: Vocabulary of a source that is not free or not keyless, or of scraping around terms.
NOT_FREE = re.compile(r"\b(api[ _-]?key|apikey|access[ _-]?key|token|bearer|subscription|"
                      r"(paid|premium)[ -](data|feed|plan|tier|access|api)|"
                      r"paywall|login|log[ -]in|password|licen[cs]ed feed|scrap(e|ed|ing)|"
                      r"bloomberg|refinitiv|factset)\b", re.IGNORECASE)
#: MT5 universe mandate: no crypto-exchange ground is ever hunted.
CRYPTO_EXCHANGE = re.compile(r"\b(binance|bybit|okx|okex|hyperliquid|coinbase|kraken|deribit|"
                             r"bitmex|bitfinex|huobi|kucoin|bitget|gate\.io|perpetuals?|perps?|"
                             r"funding[ -]rates?|open interest on)\b", re.IGNORECASE)
URL = re.compile(r"https?://([^/\s|]+)", re.IGNORECASE)


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


def _slug(text: str, n: int = 40) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", text.lower())).strip("_")[:n] or "x"


# ---------------------------------------------------------------------------- the prompt ---
def prompt_block(*, json_contract: bool = False, existing: Iterable[str] = ()) -> str:
    """The "find data yourself" task appended to a generator's prompt. `existing` names flows
    the desk already fetches so the model does not spend its slots re-proposing them."""
    have = sorted({str(x) for x in existing})[:12]
    lines = [
        "FIND DATA THE DESK DOES NOT HAVE (optional, up to "
        f"{MAX_PER_REPLY}). Propose free, KEYLESS, official statistical series that should move "
        "an MT5 instrument INDIRECTLY (a forced flow, a balance-sheet or policy constraint, a "
        "real-economy shock that reaches FX / gold / indices / energy with a lag). Only these "
        "keyless SDMX providers: " + ", ".join(sorted(PROVIDERS)) + ". Name the dataflow and ONE "
        "series key exactly as the provider's SDMX API spells it (dot-separated, every dimension "
        "filled: no wildcard, no '+'); never a credentialed API, paid feed, scraped page or any "
        "crypto-exchange data. Frequency is one of D, W, M, Q and must appear as a segment of "
        "the key; the lag is the days after period end the value is PUBLISHED.",
    ]
    if have:
        lines.append("Already fetched (do not repeat): " + "; ".join(have) + ".")
    if json_contract:
        lines.append('In the JSON, add a top-level "data_sources" list of objects: '
                     '{"provider": ..., "dataflow": ..., "key": ..., "freq": "D|W|M|Q", '
                     '"lag_days": int, "instruments": {"EURUSD": 1, "XAUUSD": -1}, '
                     '"mechanism": "who is forced to trade, and why this series sees it first"}; '
                     "[] when you know no such series exactly.")
    else:
        lines += ["For each, output ONE line, exactly:",
                  "DATA_SOURCE | <provider> | <dataflow> | <series key> | <D|W|M|Q> | "
                  "<lag days> | <SYMBOL:+1, SYMBOL:-1 (MT5 symbols; no share CFDs)> | "
                  "<mechanism: who is forced to trade, and why this series sees it first>"]
    return "\n".join(lines)


def _instruments(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in re.split(r"[,;]", text or ""):
        m = re.fullmatch(r"\s*([A-Za-z0-9.]{3,12})\s*:\s*([+-]?1)\s*", part)
        if m:
            out[m.group(1).upper()] = int(m.group(2))
    return out


def parse_lines(text: str) -> list[dict[str, Any]]:
    """Raw proposals from a reply's `DATA_SOURCE | ...` lines (unvetted)."""
    out: list[dict[str, Any]] = []
    for ln in (text or "").splitlines():
        if not LINE.match(ln):
            continue
        p = [x.strip() for x in ln.split("|")]
        if len(p) < 8:
            out.append({"_malformed": ln[:160]})
            continue
        out.append({"provider": p[1], "dataflow": p[2], "key": p[3], "freq": p[4],
                    "lag_days": p[5], "instruments": _instruments(p[6]),
                    "mechanism": " | ".join(p[7:]), "_line": ln[:400]})
    return out


# ------------------------------------------------------------------------------- vetting ---
def _universe() -> tuple[set[str] | None, Any]:
    uni = _read(UNIVERSE)
    syms = {str(k) for k in uni} if isinstance(uni, dict) and uni else None
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        may_hypothesise = None
    return syms, may_hypothesise


def proposal_id(provider: str, dataflow: str, key: str) -> str:
    h = hashlib.sha256(f"{provider}|{dataflow}|{key}".encode()).hexdigest()[:8]
    return f"{ID_PREFIX}{provider.lower()}_{h}"


def vet(raw: Mapping[str, Any], *, universe: set[str] | None = None,
        may_hypothesise: Any = None, known_paths: Iterable[str] = ()
        ) -> tuple[dict[str, Any] | None, str]:
    """(normalised proposal, "") when admitted, else (None, reason). Fails closed on every field.

    `universe` / `may_hypothesise` default to this host's broker registry and two-lane policy;
    an unreadable registry leaves membership to keyed_sources (which filters again at mint)."""
    if not isinstance(raw, Mapping) or raw.get("_malformed"):
        return None, "malformed"
    if raw.get("_reject"):                     # a caller's own fence (kimi's forbidden zones)
        return None, str(raw["_reject"])[:60]
    whole = " ".join(str(raw.get(k) or "") for k in ("provider", "dataflow", "key", "mechanism",
                                                     "_line"))
    if CRYPTO_EXCHANGE.search(whole):
        return None, "crypto_exchange_ground"
    if NOT_FREE.search(whole):
        return None, "not_free_or_keyed"
    prov = str(raw.get("provider") or "").strip().upper()
    if prov not in PROVIDERS:
        return None, "provider_not_on_keyless_allowlist"
    hosts = {m.group(1).lower() for m in URL.finditer(whole)}
    own = URL.match(PROVIDERS[prov]["base"])
    if hosts - {own.group(1).lower() if own else ""}:
        return None, "endpoint_off_the_allowlist"
    flow, key = str(raw.get("dataflow") or "").strip(), str(raw.get("key") or "").strip()
    if not FLOW.match(flow) or ".." in flow:
        return None, "dataflow_not_structural"
    if not KEY.match(key):
        return None, "key_not_one_series"
    freq = str(raw.get("freq") or "").strip().upper()[:1]
    if freq not in FREQS:
        return None, "frequency_not_D_W_M_Q"
    segs = set(key.split("."))
    if freq not in segs:
        return None, "frequency_not_in_the_key"
    try:
        lag = int(float(str(raw.get("lag_days"))))
    except ValueError:
        return None, "lag_not_a_number"
    if lag < 0 or lag > MAX_LAG_DAYS:
        return None, "lag_out_of_range"
    # The floor of the SLOWEST frequency the key could carry: a key with an "M" and a "D"
    # segment is lagged as monthly. Late costs edge; early invents it.
    lag = max([lag] + [LAG_FLOOR_DAYS[f] for f in FREQS if f in segs])
    inst = raw.get("instruments")
    if not isinstance(inst, Mapping):
        return None, "no_instruments"
    if universe is None and may_hypothesise is None:
        universe, may_hypothesise = _universe()
    keep: dict[str, int] = {}
    for s, sign in inst.items():
        sym = str(s).upper().strip()
        try:
            sg = int(sign)
        except (TypeError, ValueError):
            continue
        if sg not in (1, -1) or not SYMBOL.match(sym):
            continue
        if universe is not None and sym not in universe:
            continue
        if may_hypothesise is not None and not may_hypothesise(sym):
            continue
        keep[sym] = sg
    if not keep:
        return None, "no_hypothesis_lane_instrument"
    mech = re.sub(r"\s+", " ", str(raw.get("mechanism") or "")).strip()
    if len(mech) < 20:
        return None, "no_mechanism"
    path = f"{flow}/{key}{PROVIDERS[prov]['suffix']}"
    if f"{PROVIDERS[prov]['base']}{path}" in set(known_paths):
        return None, "duplicate_of_a_fetched_series"
    return {"id": proposal_id(prov, flow, key), "provider": prov, "dataflow": flow, "key": key,
            "freq": freq, "lag_days": lag, "instruments": dict(sorted(keep.items())),
            "mechanism": mech[:600], "series": _slug(key), "path": path}, ""


def roster_row(p: Mapping[str, Any], *, discovered_by: str) -> dict[str, Any]:
    """An ordinary keyed_sources `kind: sdmx` row (every REQUIRED field), built HERE from the
    vetted proposal and the provider table -- never from text the model supplied as a URL."""
    prov = PROVIDERS[str(p["provider"])]
    return {
        "id": str(p["id"]),
        "name": f"{p['provider']} {p['dataflow']} {p['key']} (proposed by {discovered_by})",
        "kind": "sdmx", "cadence": "daily", "auth": "none", "key_env": [],
        "credential": f"KEYLESS:{p['provider']}", "licence": prov["licence"],
        "region": prov["region"], "lang": "en", "url": prov["base"], "base": prov["base"],
        "start_param": "startPeriod", "confirm_on_box": True,
        # The provider table's own terms ruling: an official statistical API built for machine
        # reuse. A provider without that ruling is not in PROVIDERS, so cannot reach here.
        "machine_use_allowed": True,
        "rule": {"lag_days": int(p["lag_days"]), "hour": 0,
                 "why": f"declared release lag, floored at {LAG_FLOOR_DAYS[str(p['freq'])]}d "
                        f"for frequency {p['freq']}"},
        "series": {str(p["series"]): {"path": str(p["path"]), "lag_days": int(p["lag_days"]),
                                      "instruments": dict(p["instruments"])}},
        "mechanism": str(p["mechanism"]),
        "source_culture": prov["region"], "participant_structure": "policy_driven",
        "failure_mode_hypothesis": "UNMEASURED: proposed by a free model; the gauntlet decides",
        "crowding_prior": "unknown",
        "discovered_by": discovered_by, "method": METHOD, "lane": LANE,
        "uses": {"direct": {"families": ["exogenous_conditioner"],
                            "organ": "research/keyed_sources.py"},
                 "indirect": {"families": ["<certified parent> + params.conditioner alt:"],
                              "organ": "research/keyed_sources.py + research/alt_catalog.py"},
                 "allocation": {"organ": "research/keyed_sources.py allocation_intel"}},
    }


def lake_series(p: Mapping[str, Any]) -> str:
    """The lake series keyed_sources publishes for an accepted proposal."""
    return f"ks_{p['id']}__{p['series']}"


ROSTER = DESK / "data" / "source_rosters" / "keyed_sources.json"


def known(roster: Path | None = None, roots: Iterable[Path] | None = None
          ) -> tuple[list[str], set[str]]:
    """(labels for the prompt's "already fetched" line, full URLs for the duplicate check): every
    series the keyed_sources roster and the accepted queue already carry."""
    doc = _read(roster or ROSTER)
    labels: list[str] = []
    full: set[str] = set()
    for r in (doc.get("sources") if isinstance(doc, dict) else None) or []:
        if not isinstance(r, dict) or r.get("kind") != "sdmx":
            continue
        for s in (r.get("series") or {}).values():
            if isinstance(s, dict) and s.get("path"):
                full.add(str(r.get("base") or "") + str(s["path"]))
                labels.append(str(s["path"]).split("?")[0])
    for p in accepted(roots):
        full.add(PROVIDERS[p["provider"]]["base"] + p["path"])
        labels.append(f"{p['dataflow']}/{p['key']}")
    return labels, full


# ------------------------------------------------------------------------------ the queue ---
def queue_path(seat: str, root: Path | None = None) -> Path:
    return (root or INTEL_ROOTS[0]) / seat / QUEUE_NAME


def record(seat: str, raws: Iterable[Mapping[str, Any]], *, organ: str, model: str = "",
           root: Path | None = None, known_paths: Iterable[str] = (),
           universe: set[str] | None = None, may_hypothesise: Any = None,
           now: datetime | None = None) -> dict[str, Any]:
    """Vet one reply's proposals and merge them into the seat's queue file. Returns the counts of
    this call. A proposal already accepted is counted as proposed again but not re-added."""
    path = queue_path(seat, root)
    doc = _read(path)
    doc = doc if isinstance(doc, dict) else {}
    counts = doc.setdefault("counts", {"proposed": 0, "accepted": 0, "rejected": 0})
    by_reason = doc.setdefault("rejected_by_reason", {})
    acc = doc.setdefault("accepted", {})
    rej = doc.setdefault("recent_rejections", [])
    at = (now or _now()).isoformat(timespec="seconds")
    known = set(known_paths) | {PROVIDERS[str(r["provider"])]["base"] + str(r["path"])
                                for r in acc.values() if isinstance(r, dict)
                                and str(r.get("provider")) in PROVIDERS}
    got = {"proposed": 0, "accepted": 0, "rejected": 0, "reasons": {}}
    for raw in list(raws)[:MAX_PER_REPLY]:
        got["proposed"] += 1
        p, why = vet(raw, universe=universe, may_hypothesise=may_hypothesise, known_paths=known)
        if p is None:
            got["rejected"] += 1
            got["reasons"][why] = got["reasons"].get(why, 0) + 1
            by_reason[why] = int(by_reason.get(why) or 0) + 1
            rej.append({"at": at, "organ": organ, "reason": why,
                        "raw": {k: str(v)[:160] for k, v in dict(raw).items()}})
            continue
        got["accepted"] += 1
        known.add(PROVIDERS[p["provider"]]["base"] + p["path"])
        acc[p["id"]] = {**p, "discovered_by": organ, "method": METHOD, "lane": LANE,
                        "model": model,
                        "proposed_at": at, "lake_series": lake_series(p)}
    for k in ("proposed", "accepted", "rejected"):
        counts[k] = int(counts.get(k) or 0) + got[k]
    doc["recent_rejections"] = rej[-KEEP_REJECTIONS:]
    doc.update({"seat": seat, "method": METHOD, "updated_at": at,
                "rule": ("free-model data-source proposals, vetted here (keyless official SDMX "
                         "allowlist, one series, PIT lag floor, MT5 hypothesis lane); accepted "
                         "rows are fetched ONLY by research/keyed_sources.py on the box, which "
                         "re-vets them on read")})
    with contextlib.suppress(OSError):
        _atomic(path, doc)
    return got


def queue_files(roots: Iterable[Path] | None = None) -> list[Path]:
    out: list[Path] = []
    for r in roots if roots is not None else INTEL_ROOTS:
        if r.is_dir():
            out += sorted(r.glob(f"*/{QUEUE_NAME}"))
    return out


def accepted(roots: Iterable[Path] | None = None) -> list[dict[str, Any]]:
    """Every accepted proposal on this host, RE-VETTED here (the file may have come through git
    from another host's code), first occurrence of an id wins."""
    out: dict[str, dict[str, Any]] = {}
    files = queue_files(roots)
    uni, may = _universe() if files else (None, None)
    for f in files:
        d = _read(f)
        for row in ((d or {}).get("accepted") or {}).values() if isinstance(d, dict) else []:
            if not isinstance(row, dict) or str(row.get("id")) in out:
                continue
            p, _ = vet(row, universe=uni, may_hypothesise=may)
            if p is None or p["id"] != row.get("id"):
                continue
            out[p["id"]] = {**p, "discovered_by": str(row.get("discovered_by") or f.parent.name),
                            "method": METHOD, "proposed_at": row.get("proposed_at")}
    return list(out.values())


def discovered_rows(existing: Iterable[Mapping[str, Any]],
                    roots: Iterable[Path] | None = None) -> list[dict[str, Any]]:
    """keyed_sources roster rows for every accepted proposal the roster does not already carry
    (by id or by the same base + series path)."""
    ids, paths = set(), set()
    for r in existing:
        ids.add(str(r.get("id")))
        for s in (r.get("series") or {}).values():
            if isinstance(s, Mapping) and s.get("path"):
                paths.add(str(r.get("base") or "") + str(s["path"]))
    out = []
    for p in accepted(roots):
        full = PROVIDERS[p["provider"]]["base"] + p["path"]
        if p["id"] in ids or full in paths:
            continue
        ids.add(p["id"])
        paths.add(full)
        out.append(roster_row(p, discovered_by=p["discovered_by"]))
    return out


def provenance(roots: Iterable[Path] | None = None) -> dict[str, dict[str, Any]]:
    """lake series -> {discovered_by, method, source_row, provider} for every accepted proposal."""
    return {lake_series(p): {"discovered_by": p["discovered_by"], "method": METHOD,
                             "lane": LANE, "source_row": p["id"], "provider": p["provider"]}
            for p in accepted(roots)}


# ------------------------------------------------------------------------------- the funnel --
def _sum(vals: list[Any]) -> Any:
    return UNMEASURED if any(not isinstance(v, int) for v in vals) else sum(vals)


def method_view(alt_cov: Mapping[str, Any] | None, *, roots: Iterable[Path] | None = None,
                lake: Path | None = None) -> dict[str, Any]:
    """FUNNEL `by_method`: proposals -> accepted -> landed -> offered -> rows -> testable ->
    judged -> certified for `llm_data_discovery`, per discovering organ, beside the series every
    other method wrote. A stage whose input is unreadable is UNMEASURED, never 0."""
    files = queue_files(roots)
    base = lake or LAKE
    acc = accepted(roots)
    series = (alt_cov or {}).get("series") if isinstance(alt_cov, Mapping) else None
    series = series if isinstance(series, Mapping) else None

    def stages(rows: list[dict[str, Any]], proposed: Any) -> dict[str, Any]:
        landed = [r for r in rows if any((base / f"{lake_series(r)}{x}").exists()
                                         for x in (".csv", ".parquet"))] if base.is_dir() else None
        ents = [series.get(lake_series(r)) for r in rows] if series is not None else None
        ents = [e for e in ents if isinstance(e, Mapping)] if ents is not None else None
        seeing = [e.get("generators_seeing") for e in ents] if ents is not None else None
        return {"proposals": proposed, "accepted": len(rows),
                "landed": len(landed) if landed is not None else UNMEASURED,
                "offered": (UNMEASURED if seeing is None or any(not isinstance(s, list)
                                                                for s in seeing)
                            else sum(1 for s in seeing if s)),
                **{k: (_sum([e.get(src) for e in ents]) if ents is not None else UNMEASURED)
                   for k, src in (("rows", "rows"), ("testable", "testable_rows"),
                                  ("judged", "judged"), ("certified", "certified"))}}

    if not files:
        disc: dict[str, Any] = {**stages(acc, UNMEASURED),
                                "why": f"{UNMEASURED}: no data_source_proposals.json under "
                                       "data/intelligence/<seat>/ on this host yet"}
        organs: dict[str, Any] = {}
    else:
        prop: dict[str, int] = {}
        rej: dict[str, int] = {}
        for f in files:
            d = _read(f)
            d = d if isinstance(d, dict) else {}
            prop[f.parent.name] = prop.get(f.parent.name, 0) + int(
                (d.get("counts") or {}).get("proposed") or 0)
            for k, v in (d.get("rejected_by_reason") or {}).items():
                rej[k] = rej.get(k, 0) + int(v or 0)
        disc = stages(acc, sum(prop.values()))
        disc["rejected_by_reason"] = rej
        names = sorted({r["discovered_by"] for r in acc} | set(prop))
        organs = {o: stages([r for r in acc if r["discovered_by"] == o],
                            prop.get(o, UNMEASURED)) for o in names}
    mine = {lake_series(r) for r in acc}
    other = [e for n, e in (series or {}).items() if n not in mine and isinstance(e, Mapping)]
    return {
        METHOD: {**disc, "lane": LANE, "by_organ": organs},
        "registered_sources": ({"series": len(other),
                                **{k: _sum([e.get(src) for e in other])
                                   for k, src in (("rows", "rows"),
                                                  ("testable", "testable_rows"),
                                                  ("judged", "judged"),
                                                  ("certified", "certified"))}}
                               if series is not None else {"status": UNMEASURED}),
        "stages": ["proposals", "accepted", "landed", "offered", "rows", "testable", "judged",
                   "certified"],
        "rule": ("accepted = passed vet(); landed = keyed_sources published its ks_ lake series "
                 "on this host; offered = alt_catalog showed it to >= 1 generator; rows .. "
                 "certified = the by_alt_source counts on those series"),
    }


def stage_counts(alt_cov: Mapping[str, Any] | None = None, *,
                 roots: Iterable[Path] | None = None, lake: Path | None = None
                 ) -> dict[str, Any]:
    """The `data_discovery` lane's stage counts alone (proposals .. certified), for a caller such
    as the funnel's `by_lane` block; the same numbers `method_view` publishes."""
    v = method_view(alt_cov, roots=roots, lake=lake)[METHOD]
    return {k: v.get(k, UNMEASURED) for k in ("proposals", "accepted", "landed", "offered",
                                               "rows", "testable", "judged", "certified")}


# --------------------------------------------------------------------- the job on its clock --
#: Every free route this host can reach (OpenRouter, Groq, SiliconFlow, DeepSeek, Kimi, any
#: future seat): the environment and `llm_panel.json` through `llm_seat.seats()`, then the free
#: roster. Keys stay inside the Seat objects; only provider NAMES are ever recorded.
FREE_ROSTER = ROOT / "data" / "secrets" / "llm_panel_free.json"
REPORT = DESK / "reports" / "DATA_DISCOVERY.json"
#: Worded to pass `cn_ensemble.assert_public` (no broker name, no credential word), so every
#: route of the shared free chain -- relays included -- may serve this job.
SYSTEM = ("You find free, keyless, official statistical data for a quant desk trading the "
          "MT5 CFD universe (FX, gold, metals, indices, energy). You never propose crypto-"
          "exchange data, paid data, keyed APIs or scraping. Output ONLY the requested lines.")


def seat_chain() -> list[Any]:
    """The SHARED free chain's lit routes (libs/ops/free_chain: OpenRouter, llm_seat seats, the
    free roster, every cn_ensemble provider, Cerebras, GitHub Models and any FREE_LLM_<NAME>_KEY),
    deduplicated there. Relays are included when this job's prompt is public, which it is."""
    try:
        from libs.ops import free_chain
        return free_chain.routes(LANE, public=free_chain.is_public(SYSTEM, prompt_block()))
    except Exception:
        return []


def run_job(*, chat: Any = None, chain: list[Any] | None = None, root: Path | None = None,
            budget_s: float = 300.0, now: datetime | None = None) -> dict[str, Any]:
    """One `data_discovery` pass: ask the shared free chain (rotating start, failover across
    every lit key), vet the DATA_SOURCE lines into `data/intelligence/data_discovery/`. An
    explicit `chat` / `chain` walks that chain in order instead (tests, callers with their own
    seats). Never raises; a pass with no route is a named state, not 0."""
    import time
    t0 = time.monotonic()
    os.environ.setdefault("QUANT_LLM_ORGAN", LANE)          # the lane's budget attribution
    labels, full = known()
    prompt = prompt_block(existing=labels)
    tried: list[dict[str, str]] = []
    text, served = "", ""
    if chat is None and chain is None:
        routes = seat_chain()
        if routes:
            from libs.ops import free_chain
            text, who, err = free_chain.ask(LANE, SYSTEM, prompt, max_tokens=3000,
                                            temperature=0.5, chain=routes, budget_s=budget_s)
            if text:
                served = who.replace("/", ":", 1)
            else:
                tried = [{"seat": "free_chain", "error": str(err or "empty response")[:400]}]
    else:
        if chat is None:
            from libs.ops import llm_seat
            chat = llm_seat.chat
        routes = list(chain or [])
        for st in routes:
            if time.monotonic() - t0 > budget_s:
                tried.append({"seat": str(st.name), "error": "pass budget reached"})
                break
            txt, err = chat(prompt, system=SYSTEM, seat=st, max_tokens=3000, temperature=0.5)
            if not err and txt.strip():
                text, served = txt, f"{st.name}:{st.model or 'discovered'}"
                break
            tried.append({"seat": str(st.name), "error": str(err or "empty response")[:200]})
            if err and "daily" in str(err).lower() and "budget" in str(err).lower():
                break                               # the shared allowance: every seat refuses
    doc: dict[str, Any] = {"generated_at": (now or _now()).isoformat(timespec="seconds"),
                           "writer": "research/data_discovery.py", "lane": LANE,
                           "method": METHOD, "routes": len(routes), "tried": tried,
                           "served_by": served or None}
    if not routes:
        doc.update(status="NO_ROUTE", why="no free seat configured on this host")
    elif not text:
        doc.update(status="NO_ANSWER", why="every route failed or was refused this pass")
    else:
        got = record(LANE, parse_lines(text), organ=LANE, model=served,
                     root=root, known_paths=full, now=now)
        doc.update(status="RAN", **{k: got[k] for k in ("proposed", "accepted", "rejected",
                                                         "reasons")})
    doc["seconds"] = round(time.monotonic() - t0, 1)
    return doc


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="free-model data discovery (one pass)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    a = ap.parse_args(argv)
    doc = run_job(budget_s=a.budget_s)
    with contextlib.suppress(OSError):
        _atomic(REPORT, doc)
    print(f"data_discovery: {doc['status']} served_by={doc.get('served_by')} "
          f"accepted={doc.get('accepted', 0)}/{doc.get('proposed', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
