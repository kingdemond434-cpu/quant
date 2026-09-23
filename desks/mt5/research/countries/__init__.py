"""THE COUNTRY DEPARTMENTS -- one pack per economy, held as DATA and validated against the broker.

WHAT THIS PACKAGE IS. `desks/mt5/research/japan` is the first region department: a mandate held as
frozen objects rather than as prose in a document nothing loads. Section 46 of the principal's
mandate says each region discovers its OWN mechanics rather than inheriting Japan's, and the
principal's order of 2026-09-17 says every country gets the same DEPTH as Japan and none of its
ontology. So this package holds the sibling packs -- `kr`, `cn`, `hk`, `tw` -- and each one is
written from its own market's mechanics: Korea's second-Thursday expiry and its customs 1st-20th
export print, China's 09:15 Beijing central parity and its counter-cyclical factor, Hong Kong's
7.75/7.85 convertibility undertakings and its Aggregate Balance, Taiwan's third-Wednesday TAIFEX
expiry and its monthly-revenue disclosure. Nothing here is a translated Japanese calendar.

WHY A PACK IS DATA AND NOT A DOCUMENT. A mandate in Markdown is read by whoever happens to open
it. A mandate as data is READ BY THE MINERS and CHECKED BY THE TESTS: `check_pack` refuses a pack
whose executable instrument is not in the broker's own registry, refuses a single-name equity
under the two-lane order (2026-09-06), refuses an actor missing any of the eleven fields, and
refuses a domain with no negative control. An unvalidated country pack is a wish with a flag on it.

THE THREE BOUNDARIES THAT NEVER MOVE HERE.

  1. THE UNIVERSE IS THE BROKER'S (mandate 2026-08-18). `executable_instruments` may contain only
     symbols present in `desks/mt5/data/universe/universe.json`. An instrument the desk cannot
     trade -- USDTWD is the standing example -- is NAMED in `ABSENT_INSTRUMENTS` and its economics
     are routed through `transmission_edges_seed` into symbols that do exist. Absence is recorded,
     never silently dropped.
  2. NO SINGLE-NAME EQUITY IS EVER A HYPOTHESIS (two-lane order 2026-09-06). Korea's and Taiwan's
     semiconductor complexes are the loudest mechanism in East Asia and they enter these packs as
     INDEX and FX transmission only. A foundry's monthly revenue is an observable; it is never a
     symbol on a docket.
  3. NO CRYPTO-EXCHANGE GROUND IS EVER HUNTED (mandate 2026-08-18). The Korean pack carries the
     kimchi premium because it is a real KRW/risk observable, and it carries it as PUBLIC
     COMMENTARY with `pit_feasible=False` -- no venue order book, no venue feed, no venue named in
     any source class. The executable leg is the broker's own crypto CFD, which is inside the MT5
     universe by the same order that forbids the venue.

THE ADAPTER. A sibling builder owns `libs/research/country_lab.py` and the frozen `CountryPack`
dataclass these packs instantiate. It is imported LAZILY, once, and if it has not landed
`build_pack` returns a plain dict with the SAME twenty-one keys -- so a pack, its validator and
its tests are green on either tree and the country work does not block on the framework's clock.
`get(pack, field)` reads either shape, and every test in this package goes through it.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[2]
#: The executable universe. Module-level so a test can point it elsewhere; re-read with an mtime
#: cache because the collector rewrites the broker registry while the desk runs.
UNIVERSE_JSON: Path = DESK / "data" / "universe" / "universe.json"

#: Section 2 of the region mandate. The eleven things a pack must be able to say about an actor
#: before the chain Actor -> Constraint -> Observable -> Flow -> MarketImpact -> Candidate can be
#: walked. Kept as a local copy so this package runs on a tree where the framework has not landed.
ACTOR_FIELDS: tuple[str, ...] = ("holds", "forced_to", "when", "information", "constraints",
                                 "instruments", "counterparties", "observables", "impact",
                                 "persistence", "falsifier")

#: The twenty-one fields of `libs.research.country_lab.CountryPack`, in the builder's order.
PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")

#: The ten fields every dataset entry owes. `pit_feasible` is the one the catalogue exists for: a
#: dataset whose vintage cannot be reconstructed can only ever produce NOT_PIT_SAFE cells.
DATASET_FIELDS: tuple[str, ...] = (
    "name", "source", "coverage", "frequency", "publication_lag_days", "revisions", "licence",
    "history_from", "pit_feasible", "assets", "mechanism_families", "how_to_fetch")

#: The four EAST ASIA packs written against this module's vocabulary. Japan is a department of
#: its own (`research/japan`), and OTHER country packs are being written into this directory
#: concurrently by other builders with their own row vocabularies -- `codes()` discovers whatever
#: is actually on disk, and this tuple says only which packs `check_pack`'s default field names
#: were written for.
EAST_ASIA_CODES: tuple[str, ...] = ("kr", "cn", "hk", "tw")
CODES: tuple[str, ...] = EAST_ASIA_CODES

#: Asset classes the broker registry uses for single names. The two-lane order forbids hunting
#: them, so no pack may name one as executable.
EQUITY_CLASSES: frozenset[str] = frozenset({"equities", "equity", "shares", "stock", "stocks",
                                            "share cfd", "share cfds"})

#: Evidence labels an edge seed may carry. A seed is a HYPOTHESIS until a gauntlet says otherwise;
#: `MEASURED_ELSEWHERE` means a public study exists and the desk has not reproduced it.
EDGE_EVIDENCE: tuple[str, ...] = ("HYPOTHESIS", "MEASURED_ELSEWHERE", "DESK_MEASURED")

_UNIVERSE_CACHE: dict[str, Any] = {"path": None, "mtime": None, "rows": {}}


# --------------------------------------------------------------------------- framework bridge
def _country_lab() -> Any:
    """`libs.research.country_lab` when it has landed, else None.

    Imported HERE rather than at module scope: these packs ship before the framework does and a
    country department that cannot be read because a sibling builder has not pushed yet is a
    department that does not exist.
    """
    try:
        from libs.research import country_lab
    except Exception:  # pragma: no cover -- absent module, or a partial one mid-landing
        return None
    return country_lab


def pack_class() -> Any:
    """The frozen `CountryPack` dataclass, or None when the framework has not landed."""
    lab = _country_lab()
    return getattr(lab, "CountryPack", None) if lab is not None else None


def build_pack(**fields: Any) -> Any:
    """One country pack, as `CountryPack` when the framework is present and as a dict when not.

    Only keys the real dataclass declares are passed to it; anything this package knows that the
    dataclass does not is dropped from the object and kept in the dict form, because a frozen
    dataclass raises on an unknown keyword and a pack that cannot be built is worse than a pack
    that carries one field fewer.
    """
    missing = [f for f in PACK_FIELDS if f not in fields]
    if missing:
        raise ValueError(f"country pack is missing required field(s): {missing}")
    cls = pack_class()
    if cls is None:
        return dict(fields)
    try:
        import dataclasses
        names = {f.name for f in dataclasses.fields(cls)}
    except Exception:  # pragma: no cover -- a CountryPack that is not a dataclass
        names = set(PACK_FIELDS)
    try:
        return cls(**{k: v for k, v in fields.items() if k in names})
    except Exception:  # pragma: no cover -- a signature the builder changed under us
        return dict(fields)


def get(pack: Any, field: str, default: Any = None) -> Any:
    """One field of a pack, whichever shape it is in. Every test in this package reads this way."""
    if isinstance(pack, Mapping):
        return pack.get(field, default)
    return getattr(pack, field, default)


def as_dict(pack: Any) -> dict[str, Any]:
    """The pack as a plain dict of its twenty-one fields, for JSON, diffing and tests."""
    return {f: get(pack, f) for f in PACK_FIELDS}


# --------------------------------------------------------------------------- the universe
def universe(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The broker's registry, re-read when its mtime moves. `{}` when the file is absent.

    An empty registry is UNMEASURED, not an empty universe (L1.28a): `check_pack` says so by name
    rather than passing a pack whose symbols were never checked against anything.
    """
    target = Path(path) if path is not None else UNIVERSE_JSON
    try:
        mtime = target.stat().st_mtime
    except OSError:
        return {}
    if _UNIVERSE_CACHE["path"] == str(target) and _UNIVERSE_CACHE["mtime"] == mtime:
        return dict(_UNIVERSE_CACHE["rows"])
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = {str(k): dict(v) for k, v in raw.items() if isinstance(v, Mapping)} \
        if isinstance(raw, Mapping) else {}
    _UNIVERSE_CACHE.update({"path": str(target), "mtime": mtime, "rows": rows})
    return dict(rows)


def universe_symbols(path: Path | None = None) -> frozenset[str]:
    """Every symbol the box can quote."""
    return frozenset(universe(path))


def asset_class(symbol: str, path: Path | None = None) -> str:
    """The broker's own class for a symbol, or ABSENT. Never a guess from the ticker's shape."""
    row = universe(path).get(str(symbol))
    if row is None:
        return "ABSENT"
    raw = str(row.get("asset_class") or "").lower().replace("_", " ")
    return " ".join(raw.split()) or "UNCLASSIFIED"


def is_equity(symbol: str, path: Path | None = None) -> bool:
    """True for a single-name share CFD. The two-lane order forbids hunting one statistically."""
    return asset_class(symbol, path) in EQUITY_CLASSES


def resolve(symbols: Iterable[str], path: Path | None = None) -> dict[str, list[str]]:
    """Split a symbol list into what the box can trade, what is an equity and what is absent."""
    tradable: list[str] = []
    equities: list[str] = []
    absent: list[str] = []
    for sym in symbols:
        klass = asset_class(sym, path)
        if klass == "ABSENT":
            absent.append(str(sym))
        elif klass in EQUITY_CLASSES:
            equities.append(str(sym))
        else:
            tradable.append(str(sym))
    return {"tradable": tradable, "equities": equities, "absent": absent}


# --------------------------------------------------------------------------- the row builders
def actor(name: str, *, holds: str, forced_to: Sequence[str], when: str,
          information: Sequence[str], constraints: Sequence[str], instruments: Sequence[str],
          counterparties: Sequence[str], observables: Sequence[str], impact: str,
          persistence: str, falsifier: str, notes: str = "") -> dict[str, Any]:
    """One economic actor with all eleven fields. An actor whose FALSIFIER is blank is a story."""
    return {"name": name, "holds": holds, "forced_to": tuple(forced_to), "when": when,
            "information": tuple(information), "constraints": tuple(constraints),
            "instruments": tuple(instruments), "counterparties": tuple(counterparties),
            "observables": tuple(observables), "impact": impact, "persistence": persistence,
            "falsifier": falsifier, "notes": notes}


def domain(did: str, title: str, *, objects: Sequence[str], conditions: Sequence[str],
           instruments: Sequence[str], controls: Sequence[str],
           notes: str = "") -> dict[str, Any]:
    """One research domain. `controls` is never optional: without it an effect cannot be told
    apart from the desk's own sampling."""
    return {"id": did, "title": title, "objects": tuple(objects),
            "conditions": tuple(conditions), "instruments": tuple(instruments),
            "controls": tuple(controls), "notes": notes}


def dataset(name: str, *, source: str, coverage: str, frequency: str,
            publication_lag_days: float, revisions: str, licence: str, history_from: str,
            pit_feasible: bool, assets: Sequence[str], mechanism_families: Sequence[str],
            how_to_fetch: str) -> dict[str, Any]:
    """One catalogue entry of the data-discovery swarm."""
    return {"name": name, "source": source, "coverage": coverage, "frequency": frequency,
            "publication_lag_days": float(publication_lag_days), "revisions": revisions,
            "licence": licence, "history_from": history_from, "pit_feasible": bool(pit_feasible),
            "assets": tuple(assets), "mechanism_families": tuple(mechanism_families),
            "how_to_fetch": how_to_fetch}


#: THE TEN SOURCE LAYERS (principal's per-country depth rule, 2026-09-17). A pack that adopts
#: them names at least one source in each, or declares the layer ABSENT with a reason. A country
#: is never "covered" by five obvious sources: five official roots is ONE layer done and nine
#: missing, and the missing nine are where an untested mechanism is still lying around.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")
#: What the terms permit. A legal fact, independent of quality.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
#: How much the desk believes it. FRINGE and CONTRADICTED public material is KEPT at low weight,
#: never dropped: a claim that looks false is still a dated, testable claim.
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")
#: The only label the desk can EARN. UNTESTED is the honest default, not a criticism.
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


def source_class(sid: str, label: str, *, roots: Sequence[str], languages: Sequence[str],
                 licence: str, layer: str = "", queries: Sequence[str] = (),
                 access_label: str = "", credibility: str = "", predictive_state: str = "",
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source, with the concrete roots a crawler can actually start from.

    The depth-rule fields (`layer`, `queries` and the three independent labels) are OPTIONAL here
    and VALIDATED when given, so a pack written before the rule landed keeps working while a pack
    written after it is checked. `queries` must be native-script terms: a miner that searches an
    English phrase on a native ground finds the English corner of it and reports the corner as
    the ground.

    `machine_use_allowed` IS A REDISTRIBUTION LABEL, NOT A BRAKE (LAWS 5e, rewritten
    2026-09-23). It used to mean "the terms forbid machine extraction: registered, never
    scraped", and consumers keyed on it SKIPPED the source. That was a discovery brake the desk
    imposed on itself, and it is deleted: the desk mines and tests everything it can see on the
    open internet, and this field now records only what the desk may REDISTRIBUTE. **Leave it
    True and put the terms fact in `licence` / `notes`.** Passing False no longer stops any
    fetch, and it is kept only so the ~291 rows still carrying it from the old convention keep
    parsing; new packs should not use it. What is never crossed is the five ACTS -- no credential
    theft or logging in as someone else, no bypassing an access control or a paywall, no material
    non-public information, no stolen or leaked private data, no personal data harvesting or
    doxxing -- and none of those is a licence, a robots note or a source class.
    """
    if layer and layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label and access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} is not recognised")
    if credibility and credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r} is not recognised")
    if predictive_state and predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} is not recognised")
    return {"id": sid, "label": label, "layer": layer, "roots": tuple(roots),
            "queries": tuple(queries), "languages": tuple(languages),
            "access_label": access_label, "credibility": credibility,
            "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer a country has nothing in, declared BY NAME with the reason.

    A blank layer and an absent layer look identical in a table and mean opposite things: one is
    work not done, the other is a measurement. This row makes the second one visible (L1.28a).

    It carries `machine_use_allowed=True` since 2026-09-23 (LAWS 5e): a declared-absent layer is
    a NAMED GAP, and marking the gap unscrapable told every consumer to skip the one row whose
    whole job is to be noticed.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": True, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


def layer_counts(classes: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """How many real sources a pack names in each of the ten layers. A zero is a hole, and an
    `absent_*` row does not count toward it -- declaring a layer absent is honest, not coverage.
    """
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in classes:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def edge(eid: str, *, source: str, mechanism: str, targets: Sequence[str], sign: str,
         horizon: str, lag: str, control: str, evidence: str = "HYPOTHESIS",
         notes: str = "") -> dict[str, Any]:
    """One transmission seed: a foreign observable, the mechanism, and the EXECUTABLE symbols it
    is claimed to move. `targets` are broker symbols and `check_pack` refuses any that are not."""
    if evidence not in EDGE_EVIDENCE:
        raise ValueError(f"edge {eid}: evidence {evidence!r} not one of {list(EDGE_EVIDENCE)}")
    return {"id": eid, "source": source, "mechanism": mechanism, "targets": tuple(targets),
            "sign": sign, "horizon": horizon, "lag": lag, "control": control,
            "evidence": evidence, "notes": notes}


def era(eid: str, *, start: str, end: str | None, label: str, what_changed: str,
        invalidates: str, notes: str = "") -> dict[str, Any]:
    """One policy or market-design regime. `invalidates` names what a study pooled ACROSS this
    boundary is actually measuring, which is the only reason an era table is worth keeping."""
    return {"id": eid, "start": start, "end": end, "label": label, "what_changed": what_changed,
            "invalidates": invalidates, "notes": notes}


def miner(name: str, *, domain_ids: Sequence[str], kind: str, entry: str,
          cadence_s: float = 3600.0, steerable: bool = True, notes: str = "") -> dict[str, Any]:
    """One named specialist. `entry` is a dotted "module:function" that must actually resolve."""
    return {"name": name, "domain_ids": tuple(domain_ids), "kind": kind, "entry": entry,
            "cadence_s": float(cadence_s), "steerable": bool(steerable), "notes": notes}


# --------------------------------------------------------------------------- script detection
_HAN_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x2A6DF))
_HANGUL_RANGES = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xA960, 0xA97F), (0xAC00, 0xD7A3))
_KANA_RANGES = ((0x3040, 0x309F), (0x30A0, 0x30FF))
_SCRIPTS: dict[str, tuple[tuple[int, int], ...]] = {
    "han": _HAN_RANGES, "hangul": _HANGUL_RANGES, "kana": _KANA_RANGES,
}


def has_script(text: str, script: str) -> bool:
    """True when `text` contains at least one codepoint of the named script.

    Terminology is the one part of a pack that CANNOT be written in English: a miner reading
    Korean boards for `외국인 순매수` finds nothing if the pack spells it "foreign net buying".
    The tests assert on this function so a pack cannot quietly become an English glossary.
    """
    ranges = _SCRIPTS.get(script)
    if not ranges:
        raise ValueError(f"unknown script {script!r}; known: {sorted(_SCRIPTS)}")
    return any(any(lo <= ord(ch) <= hi for lo, hi in ranges) for ch in str(text))


def native_terms(terminology: Mapping[str, Sequence[str]], script: str) -> list[str]:
    """Every term in a terminology table that is actually written in the native script."""
    out: list[str] = []
    for terms in terminology.values():
        out.extend(t for t in terms if has_script(t, script))
    return out


def term_count(terminology: Mapping[str, Sequence[str]]) -> int:
    """Distinct terms across every domain key of a terminology table."""
    return len({t for terms in terminology.values() for t in terms})


# --------------------------------------------------------------------------- holidays
def holiday_table(rule: Mapping[str, Any], year: int) -> dict[str, str]:
    """The resolved closure table for one year: `{"YYYY-MM-DD": name}`.

    A pack's `holidays_rule` carries BOTH the derivation (the statute, the lunar anchor, the
    substitution law) and the resolved table, because the lunar calendars of East Asia cannot be
    computed from a weekday rule and a table with no rule beside it cannot be extended. An
    absent year returns `{}` rather than an invented one.
    """
    table = rule.get("table") or {}
    got = table.get(year) or table.get(str(year)) or {}
    return {str(k): str(v) for k, v in dict(got).items()}


def is_closed(rule: Mapping[str, Any], day: date) -> bool:
    """True when the local cash market is closed on `day` by this pack's table. Weekends are the
    caller's business: the table holds statutory closures only."""
    return day.isoformat() in holiday_table(rule, day.year)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Mon=0) of a month -- the shape both KRX and TAIFEX expiries take."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


# --------------------------------------------------------------------------- validation
def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (tuple, list, dict, set, frozenset)):
        return len(value) > 0
    return True


def check_pack(pack: Any, *, path: Path | None = None, min_actors: int = 12,
               min_domains: int = 10, min_edges: int = 8,
               actor_fields: Sequence[str] = ACTOR_FIELDS) -> list[str]:
    """Every way this pack is not yet a pack, named. An empty list is the only pass.

    The checks are the ones that cannot be skipped without the rest becoming decorative: an actor
    missing a field breaks the research-target chain, a domain with no control cannot tell an
    effect from its own selection, an executable instrument outside the broker's registry is a
    cell that can never be compiled, and an equity in that list spends the desk's shared
    family-wise error budget on the asset class the method suits least.
    """
    problems: list[str] = []
    for f in PACK_FIELDS:
        if f == "custom_miners":
            continue
        if not _nonempty(get(pack, f)):
            problems.append(f"{f}: empty; every country pack owes all twenty-one fields")

    code = str(get(pack, "code") or "")
    reg = universe(path)
    if not reg:
        problems.append(f"universe: {UNIVERSE_JSON} is unreadable -- UNMEASURED, so no symbol in "
                        f"this pack has been checked against anything (L1.28a)")

    execs = tuple(get(pack, "executable_instruments") or ())
    res = resolve(execs, path)
    for sym in res["absent"]:
        problems.append(f"executable_instruments: {sym} is not in the broker universe; it belongs "
                        f"in transmission_targets, named")
    for sym in res["equities"]:
        problems.append(f"executable_instruments: {sym} is a single-name equity; the two-lane "
                        f"order (2026-09-06) forbids hunting it for statistical hypotheses")

    actors = tuple(get(pack, "actors") or ())
    if len(actors) < min_actors:
        problems.append(f"actors: {len(actors)} < {min_actors}")
    seen: set[str] = set()
    for a in actors:
        name = str(get(a, "name") or "").strip()
        if not name:
            problems.append("actor: an actor with no name")
            continue
        if name in seen:
            problems.append(f"actor {name}: declared twice")
        seen.add(name)
        for f in actor_fields:
            if not _nonempty(get(a, f)):
                problems.append(f"actor {name}: {f} is empty; every declared actor field is "
                                f"required -- an actor missing one breaks the research chain")

    domains = tuple(get(pack, "domains") or ())
    if len(domains) < min_domains:
        problems.append(f"domains: {len(domains)} < {min_domains}")
    domain_ids: set[str] = set()
    for d in domains:
        did = str(get(d, "id") or "").strip()
        if not did:
            problems.append("domain: a domain with no id")
            continue
        if did in domain_ids:
            problems.append(f"domain {did}: declared twice")
        domain_ids.add(did)
        if not _nonempty(get(d, "controls")):
            problems.append(f"domain {did}: no negative controls")
        if not _nonempty(get(d, "objects")):
            problems.append(f"domain {did}: no research objects")
        for sym in resolve(get(d, "instruments") or (), path)["equities"]:
            problems.append(f"domain {did}: instrument {sym} is a single-name equity")

    edges = tuple(get(pack, "transmission_edges_seed") or ())
    if len(edges) < min_edges:
        problems.append(f"transmission_edges_seed: {len(edges)} < {min_edges}")
    for e in edges:
        eid = str(get(e, "id") or "?")
        targets = tuple(get(e, "targets") or ())
        if not targets:
            problems.append(f"edge {eid}: names no executable target")
        split = resolve(targets, path)
        for sym in split["absent"]:
            problems.append(f"edge {eid}: target {sym} is not in the broker universe")
        for sym in split["equities"]:
            problems.append(f"edge {eid}: target {sym} is a single-name equity")
        if str(get(e, "evidence") or "") not in EDGE_EVIDENCE:
            problems.append(f"edge {eid}: evidence must be one of {list(EDGE_EVIDENCE)}")

    names: set[str] = set()
    for ds in tuple(get(pack, "datasets") or ()):
        dname = str(get(ds, "name") or "").strip()
        if not dname:
            problems.append("dataset: an entry with no name")
            continue
        if dname in names:
            problems.append(f"dataset {dname}: declared twice")
        names.add(dname)
        for f in DATASET_FIELDS:
            if f == "pit_feasible":
                continue
            if not _nonempty(get(ds, f)) and f != "publication_lag_days":
                problems.append(f"dataset {dname}: {f} is empty")
        if float(get(ds, "publication_lag_days") or 0.0) < 0:
            problems.append(f"dataset {dname}: negative publication_lag_days")

    for mi in tuple(get(pack, "custom_miners") or ()):
        mname = str(get(mi, "name") or "?")
        if not _nonempty(get(mi, "entry")):
            problems.append(f"miner {mname}: no entry point")
        for did in tuple(get(mi, "domain_ids") or ()):
            if did not in domain_ids:
                problems.append(f"miner {mname}: names unknown domain {did!r}")

    rule = get(pack, "holidays_rule") or {}
    if isinstance(rule, Mapping):
        if not _nonempty(rule.get("rule")):
            problems.append("holidays_rule: no derivation text; a table with no rule cannot be "
                            "extended past the years somebody typed")
        for year in (2024, 2025, 2026):
            if not holiday_table(rule, year):
                problems.append(f"holidays_rule: no table for {year}")
        for year, tbl in dict(rule.get("table") or {}).items():
            for iso in tbl:
                try:
                    parsed = date.fromisoformat(str(iso))
                except ValueError:
                    problems.append(f"holidays_rule[{year}]: {iso!r} is not an ISO date")
                    continue
                if parsed.year != int(year):
                    problems.append(f"holidays_rule[{year}]: {iso} is not in that year")
    else:
        problems.append("holidays_rule: must be a mapping carrying rule, table and status")

    if not code:
        problems.append("code: empty; every row this department writes is tagged with it")
    return problems


# --------------------------------------------------------------------------- the registry
def codes() -> tuple[str, ...]:
    """Every country pack actually present on disk, discovered rather than declared.

    Several country departments are being written into this directory at once. A hard-coded list
    here would be a claim about other builders' work, and a wrong one within the hour.
    """
    here = Path(__file__).resolve().parent
    found = sorted(p.name for p in here.iterdir()
                   if p.is_dir() and (p / "pack.py").is_file() and not p.name.startswith("_"))
    return tuple(found)


def load(code: str) -> Any:
    """One country's pack by directory name. Imported lazily -- a pack costs something to build."""
    key = str(code).strip().lower()
    if key not in codes():
        raise KeyError(f"no pack module for {code!r}; present: {list(codes())}")
    from importlib import import_module
    module = import_module(f"{__name__}.{key}.pack")
    return module.pack()


def load_all() -> dict[str, Any]:
    """Every pack present in this package, keyed by directory name."""
    return {code: load(code) for code in codes()}


__all__ = ["ACCESS_LABELS", "ACTOR_FIELDS", "CODES", "CREDIBILITY_LABELS", "DATASET_FIELDS",
           "EAST_ASIA_CODES", "EDGE_EVIDENCE", "PACK_FIELDS", "PREDICTIVE_STATES",
           "SOURCE_LAYERS", "UNIVERSE_JSON", "absent_layer", "actor", "as_dict", "asset_class",
           "build_pack", "check_pack", "codes", "dataset", "domain", "edge", "era", "get",
           "has_script", "holiday_table", "is_closed", "is_equity", "layer_counts", "load",
           "load_all", "miner", "native_terms", "nth_weekday", "resolve", "source_class",
           "term_count", "universe", "universe_symbols"]
