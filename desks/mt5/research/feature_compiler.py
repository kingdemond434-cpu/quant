"""THE MULTIMODAL FEATURE COMPILER WITH ITS FEATURE GENOME (LAWS 5m; RESEARCH 11).

WHAT IT DOES. Every ingested modality the desk holds -- prices, text claims (through polyglot),
physical observations (the shadow and country data-plane sensors), calendars, rule states,
positioning and macro releases -- is turned into TYPED candidate representations: point-in-time
series with both clocks, a DatasetContract, a content-hashed lineage record and a FEATURE GENOME
(data origin -> PIT normalisation -> entity alignment -> representation -> transform -> ...).
Every new field is routed DISCOVERED -> PIT_ARCHIVED -> SEMANTICS -> ENTITY_MAPPED -> FORGED ->
WORLD_MODEL_INPUT: the compiler's own series are handed to `representation_forge.run(inputs=)`,
whose store the World Model reads and whose donations the discovery compiler turns into
candidates and interactions. Nothing here duplicates the forge, the ledger or the world model:
this organ TYPES what they carry and records the chain they lose.

WHAT IT REFUSES. A series without a knowable stamp is not typed (absence is not permission); a
single-name equity's bars are typed and contracted but NOT forged into the hypothesis lane (the
two-lane mandate); a modality with no artifact on this box is named UNMEASURED with what would
measure it. Legality rides on every contract and the gate is `DatasetContract.admissible()`.

RUNS: hourly leg `feature_compiler` (data department, information layer), 900 s, and writes
`reports/FEATURE_COMPILER.json`; its state lives under `data/feature_genome/`. `--dry-run`
writes nothing at all.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from research import ingestion_ledger as IL
    from research import representation_forge as RF
    from research import world_model as WM
except ImportError:                                                          # pragma: no cover
    import ingestion_ledger as IL  # type: ignore[no-redef]
    import representation_forge as RF  # type: ignore[no-redef]
    import world_model as WM  # type: ignore[no-redef]
from libs.moat import registry as REG  # noqa: E402
from libs.research import access_classifier as AC  # noqa: E402
from libs.research import data_contract as DC  # noqa: E402
from libs.research import feature_genome as FG  # noqa: E402
from libs.research import polyglot as PG  # noqa: E402
from libs.research import representations as R  # noqa: E402

STORE = DESK / "data" / "feature_genome"
GENOMES = STORE / "genomes.json"
CONTRACTS = STORE / "contracts.json"
LINEAGE = STORE / "lineage.jsonl"
CURSOR = STORE / "cursor.json"
OUT = DESK / "reports" / "FEATURE_COMPILER.json"
CALENDAR = DESK / "data" / "forced_flow_calendar.json"
#: Rule states are published by the market constitution compiler; absent here = UNMEASURED.
CONSTITUTION = DESK / "reports" / "MARKET_CONSTITUTION.json"
UNIVERSE_JSON = DESK / "data" / "universe" / "universe.json"

UNMEASURED = "UNMEASURED"
MODALITIES: tuple[str, ...] = ("prices", "text_claims", "physical_observations", "calendars",
                               "rule_states", "positioning", "macro_releases", "representations",
                               "UNCLASSIFIED")
ROUTE: tuple[str, ...] = ("DISCOVERED", "PIT_ARCHIVED", "SEMANTICS", "ENTITY_MAPPED", "FORGED",
                          "WORLD_MODEL_INPUT")
RULE = ("every ingested modality becomes typed, contracted, lineage-hashed representations with "
        "a feature genome, and every new field is routed discover -> PIT archive -> semantics -> "
        "entity mapping -> representation forge -> world model / candidates / interactions; a "
        "modality with no artifact is UNMEASURED, never zero")

BUDGET_S = 900.0
MAX_SERIES = 160          # numeric PIT series read through the world model's loader
MAX_PRICE_SYMBOLS = 8     # rotating window over the universe per pass
MAX_PRICE_POINTS = 1_500
MAX_CLAIMS = 400
MAX_CLAIM_SERIES = 24
MAX_CALENDAR_SERIES = 24
MAX_TYPED = 240
MAX_FORGE_NEW = 24
MAX_GENOMES = 4_000
MAX_CONTRACTS = 2_000
MAX_LINEAGE_BYTES = 8 * 1024 * 1024
PIT_PAD_H = 1.0           # an H1 bar closing at t is knowable at t + 1h

#: WHAT THE DESK KNOWS ABOUT ITS OWN HELD DATASETS, declared per modality and refined per source.
#: These are facts about the sources the desk already trades on, not defaults that look like a
#: review: a field genuinely unknown stays UNMEASURED and the contract is then inadmissible.
CONTRACT_BASE: dict[str, dict[str, Any]] = {
    "prices": {"source": "Fusion Markets MT5 terminal bars", "owner": "Fusion Markets (licensor)",
               "acquisition_method": "MT5 terminal history download (research/fetch_universe.py)",
               "public_or_licensed": "LICENSED",
               "licence_version": "MT5 account data licence (Fusion Markets client terms)",
               "permitted_uses": ("research", "backtest", "live_signal"),
               "redistribution_rights": "NONE: broker data is not redistributed",
               "personal_data_status": "NONE", "mnpi_review_status": "NOT_APPLICABLE",
               "jurisdiction": "AU (Fusion Markets, ASIC)", "revision_policy": "APPEND_ONLY",
               "retention_policy": "LICENCE_TERM", "compliance_owner": "principal",
               "timestamp_semantics": "both", "source_class": "broker"},
    "text_claims": {"source": "registry claims table (crawled public pages, seat donations)",
                    "owner": "the publishing site or the seat that wrote the claim",
                    "acquisition_method": "world crawler / deep forest / seat donation",
                    "public_or_licensed": "PUBLIC",
                    "licence_version": "publisher terms as recorded on the source row",
                    "permitted_uses": ("research", "evidence", "narrative_feature"),
                    "redistribution_rights": "NONE: verbatim claims are held, never republished",
                    "personal_data_status": "AGGREGATED",
                    "mnpi_review_status": "REVIEWED_CLEAR",
                    "jurisdiction": "publisher's; counted, never quoted, in this feature",
                    "revision_policy": "APPEND_ONLY", "retention_policy": "INDEFINITE",
                    "compliance_owner": "principal", "timestamp_semantics": "available_time",
                    "source_class": "media"},
    "physical_observations": {"source": "desk shadow axes and country data planes",
                              "owner": "the publishing agency named on the axis header",
                              "acquisition_method": "asia_collector / shadow axis builders",
                              "public_or_licensed": "OPEN_DATA",
                              "licence_version": "open government / agency data terms",
                              "permitted_uses": ("research", "backtest", "live_signal"),
                              "redistribution_rights": "as the agency's open licence allows",
                              "personal_data_status": "NONE",
                              "mnpi_review_status": "NOT_APPLICABLE",
                              "jurisdiction": "publishing agency's",
                              "revision_policy": "REVISED_IN_PLACE",
                              "retention_policy": "INDEFINITE", "compliance_owner": "principal",
                              "timestamp_semantics": "both", "source_class": "official"},
    "calendars": {"source": "desk forced-flow calendar (rule-derived, rules_version stamped)",
                  "owner": "the desk", "acquisition_method": "research/forced_flow_calendar.py",
                  "public_or_licensed": "OPEN_DATA",
                  "licence_version": "desk-authored rules over public venue conventions",
                  "permitted_uses": ("research", "backtest", "live_signal"),
                  "redistribution_rights": "the desk's own",
                  "personal_data_status": "NONE", "mnpi_review_status": "NOT_APPLICABLE",
                  "jurisdiction": "venue conventions (public)",
                  "revision_policy": "IMMUTABLE_VINTAGES", "retention_policy": "INDEFINITE",
                  "compliance_owner": "principal", "timestamp_semantics": "both",
                  "source_class": "official"},
    "rule_states": {"source": "market constitution compiler (venue rule states)",
                    "owner": "the venue that publishes the rule",
                    "acquisition_method": "research/market_constitution.py",
                    "public_or_licensed": "PUBLIC",
                    "licence_version": "venue rulebook, public", "permitted_uses": (
                        "research", "backtest", "live_signal"),
                    "redistribution_rights": "public rulebooks; cited, not republished",
                    "personal_data_status": "NONE", "mnpi_review_status": "NOT_APPLICABLE",
                    "jurisdiction": "venue's", "revision_policy": "IMMUTABLE_VINTAGES",
                    "retention_policy": "INDEFINITE", "compliance_owner": "principal",
                    "timestamp_semantics": "available_time", "source_class": "official"},
    "positioning": {"source": "CFTC Commitments of Traders (axis cot)",
                    "owner": "US Commodity Futures Trading Commission",
                    "acquisition_method": "research/fetch_cot.py (public release files)",
                    "public_or_licensed": "OPEN_DATA",
                    "licence_version": "US government work (public domain)",
                    "permitted_uses": ("research", "backtest", "live_signal"),
                    "redistribution_rights": "public domain", "personal_data_status": "NONE",
                    "mnpi_review_status": "NOT_APPLICABLE", "jurisdiction": "US",
                    "revision_policy": "IMMUTABLE_VINTAGES", "retention_policy": "INDEFINITE",
                    "compliance_owner": "principal", "timestamp_semantics": "both",
                    "source_class": "official"},
    "macro_releases": {"source": "FRED / ECB / BIS macro axes",
                       "owner": "St. Louis Fed, ECB, BIS",
                       "acquisition_method": "research/fetch_fred.py and the axis collectors",
                       "public_or_licensed": "OPEN_DATA",
                       "licence_version": "FRED terms of use; ECB/BIS open data terms",
                       "permitted_uses": ("research", "backtest", "live_signal"),
                       "redistribution_rights": "as each publisher's terms allow",
                       "personal_data_status": "NONE", "mnpi_review_status": "NOT_APPLICABLE",
                       "jurisdiction": "US / EU / CH", "revision_policy": "REVISED_IN_PLACE",
                       "retention_policy": "INDEFINITE", "compliance_owner": "principal",
                       "timestamp_semantics": "both", "source_class": "official"},
    "representations": {"source": "representation forge store (derived from held series)",
                        "owner": "the desk (derived); the origin dataset's owner (content)",
                        "acquisition_method": "research/representation_forge.py",
                        "public_or_licensed": "LICENSED",
                        "licence_version": "inherits the origin dataset's contract",
                        "permitted_uses": ("research", "backtest", "live_signal"),
                        "redistribution_rights": "inherits the origin dataset's",
                        "personal_data_status": "NONE",
                        "mnpi_review_status": "NOT_APPLICABLE",
                        "jurisdiction": "inherits the origin dataset's",
                        "revision_policy": "IMMUTABLE_VINTAGES", "retention_policy": "INDEFINITE",
                        "compliance_owner": "principal", "timestamp_semantics": "both",
                        "source_class": "desk"},
}
#: The PIT basis a modality's stamp rests on, in the ingestion ledger's own words where it has
#: them, so the genome's second layer speaks the same vocabulary as the ledger.
PIT_LABEL: dict[str, str] = {
    "prices": "each bar carries its own close time; knowable at close + 1h",
    "text_claims": IL.PIT_BASIS["claim"],
    "physical_observations": IL.PIT_BASIS["country_plane"],
    "calendars": "rule-derived event window; knowable at the window's end",
    "rule_states": "the rule's own effective/announcement stamp",
    "positioning": IL.PIT_BASIS["axis_series"],
    "macro_releases": IL.PIT_BASIS["axis_series"],
    "representations": "carried from the inputs; a value at t uses only inputs available at t",
}


# ---------------------------------------------------------------------------- small helpers
def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def _code_version() -> str:
    """The commit the tree is at, read without spawning git; UNMEASURED when unreadable."""
    try:
        head = (ROOT / ".git" / "HEAD").read_text("utf-8").strip()
        if head.startswith("ref: "):
            ref = ROOT / ".git" / head[5:]
            return ref.read_text("utf-8").strip()[:12] if ref.exists() else UNMEASURED
        return head[:12]
    except OSError:
        return UNMEASURED


def universe_symbols() -> frozenset[str]:
    doc = _read_json(UNIVERSE_JSON, {})
    rows = doc.get("symbols") if isinstance(doc, dict) else None
    if isinstance(rows, dict):
        return frozenset(str(k).upper() for k in rows)
    if isinstance(rows, list):
        return frozenset(str(r.get("symbol") or r.get("name") or "").upper()
                         for r in rows if isinstance(r, dict))
    if isinstance(doc, dict):
        return frozenset(str(k).upper() for k, v in doc.items() if isinstance(v, dict))
    return frozenset()


def may_hypothesise(symbol: str) -> bool:
    """The two-lane mandate's verdict for one symbol; an unreadable verdict is not a refusal."""
    try:
        from research.universe_policy import may_hypothesise as _may
    except Exception:
        return True
    try:
        return bool(_may(symbol))
    except Exception:
        return True


def modality_of(series: R.Series) -> str:
    ds = str(series.dataset).lower()
    sid = str(series.series_id).lower()
    info = str(series.information_type).lower()
    if ds.startswith("bars:") or info == "price":
        return "prices"
    if ds.startswith("claims:"):
        return "text_claims"
    if ds.startswith("calendar:"):
        return "calendars"
    if ds.startswith("rule_state:"):
        return "rule_states"
    if ds.startswith("representation:"):
        return "representations"
    if ds.endswith(":cot") or sid.startswith("cot:") or "positioning" in info:
        return "positioning"
    if "shadow_" in ds or sid.startswith(("kr_", "jp_")) or ds.startswith(("axis:kr_", "axis:jp_")):
        return "physical_observations"
    if ds == "fred_macro" or ds.startswith(("axis:fred", "axis:ecb", "axis:bis")) \
            or info == "macro_state":
        return "macro_releases"
    return "UNCLASSIFIED"


def entity_of(series: R.Series, universe: frozenset[str]) -> str:
    """Entity alignment: the MT5 instrument a series is ABOUT, or the region it describes."""
    for token in str(series.series_id).replace(".", ":").split(":"):
        if token.upper() in universe:
            return token.upper()
    return f"region:{series.region or 'UNKNOWN'}"


# ---------------------------------------------------------------- the compiler's own series
def price_symbols() -> list[str]:
    return sorted(p.stem[:-3] for p in WM.UNIVERSE_DIR.glob("*_H1.parquet")
                  if p.stem.endswith("_H1"))


def price_series(symbols: list[str]) -> tuple[list[R.Series], list[dict[str, str]]]:
    out: list[R.Series] = []
    unmeasured: list[dict[str, str]] = []
    for symbol in symbols:
        bars = WM.load_bars(symbol)
        if bars is None:
            unmeasured.append({"name": f"bars:{symbol}", "why": "no readable H1 parquet or too "
                                                                 "few rows",
                               "measured_by": "the refresh_bars leg"})
            continue
        stamps, closes = bars
        points: list[R.Point] = []
        for stamp, close in zip(stamps[-MAX_PRICE_POINTS:], closes[-MAX_PRICE_POINTS:],
                                strict=True):
            period = datetime.fromtimestamp(int(stamp), tz=UTC)
            points.append(R.Point(available_time=(period + timedelta(hours=PIT_PAD_H)).isoformat(),
                                  period_time=period.isoformat(), value=float(close)))
        if len(points) >= R.MIN_PRIOR:
            out.append(R.Series(series_id=f"bars:{symbol}:close", points=tuple(points),
                                dataset=f"bars:{symbol}", region="MT5",
                                information_type="price"))
    return out, unmeasured


def claim_rows(conn: Any, limit: int = MAX_CLAIMS) -> list[dict[str, Any]]:
    try:
        return [dict(r) for r in conn.execute(
            "SELECT claim_id, source_id, text, language, knowable_at, created_at, kind, "
            "instruments_json FROM claims WHERE text IS NOT NULL ORDER BY created_at DESC "
            "LIMIT ?", (limit,))]
    except Exception:
        return []


def claim_series(rows: list[dict[str, Any]], universe: frozenset[str]
                 ) -> tuple[list[R.Series], dict[str, Any]]:
    """Text claims through polyglot: daily counts per mechanism class and per instrument named.
    A claim without a knowable stamp is COUNTED AS REFUSED and never contributes a point."""
    by_key: dict[str, Counter[str]] = {}
    languages: Counter[str] = Counter()
    refused = 0
    seat = 0
    for row in rows:
        at = R.parse_time(str(row.get("knowable_at") or ""))
        if at is None:
            refused += 1
            continue
        text = str(row.get("text") or "")
        if not text.strip():
            continue
        understood = PG.understand(text, universe=set(universe))
        languages[understood.lang or "und"] += 1
        seat += int(understood.needs_seat)
        day = at.date().isoformat()
        classes = {c.mechanism_class or "unmapped" for c in understood.concepts} or {"none"}
        for cls in classes:
            by_key.setdefault(f"claims:mechanism:{cls}", Counter())[day] += 1
        for sym in understood.instruments[:6]:
            by_key.setdefault(f"claims:instrument:{sym.upper()}", Counter())[day] += 1
    out: list[R.Series] = []
    for key, days in sorted(by_key.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        if len(days) < R.MIN_PRIOR:
            continue
        points = tuple(R.Point(available_time=f"{day}T23:59:59+00:00",
                               period_time=f"{day}T00:00:00+00:00", value=float(n))
                       for day, n in sorted(days.items()))
        out.append(R.Series(series_id=key, points=points, dataset=f"claims:{key.split(':')[1]}",
                            region="GLOBAL", information_type="narrative"))
        if len(out) >= MAX_CLAIM_SERIES:
            break
    return out, {"rows": len(rows), "refused_unstamped": refused, "needs_seat": seat,
                 "languages": dict(languages.most_common(12)), "keys": len(by_key),
                 "series": len(out)}


def calendar_series(path: Path = CALENDAR) -> tuple[list[R.Series], dict[str, Any]]:
    doc = _read_json(path, {})
    events = doc.get("events") if isinstance(doc, dict) else None
    if not isinstance(events, list) or not events:
        return [], {"status": UNMEASURED, "why": f"{path.name} absent or holds no events",
                    "measured_by": "the forced_flow_calendar builder"}
    by_kind: dict[str, Counter[str]] = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        day = str(ev.get("date") or "")[:10]
        if not day:
            continue
        by_kind.setdefault(str(ev.get("kind") or "event"), Counter())[day] += 1
    out: list[R.Series] = []
    for kind, days in sorted(by_kind.items()):
        if len(days) < R.MIN_PRIOR:
            continue
        points = tuple(R.Point(available_time=f"{day}T23:59:59+00:00",
                               period_time=f"{day}T00:00:00+00:00", value=float(n))
                       for day, n in sorted(days.items()))
        out.append(R.Series(series_id=f"calendar:{kind}:count", points=points,
                            dataset=f"calendar:{kind}", region="GLOBAL",
                            information_type="calendar"))
        if len(out) >= MAX_CALENDAR_SERIES:
            break
    return out, {"status": "measured", "events": len(events), "kinds": len(by_kind),
                 "rules_version": doc.get("rules_version"), "series": len(out)}


def rule_state_series(path: Path = CONSTITUTION) -> tuple[list[R.Series], dict[str, Any]]:
    doc = _read_json(path, None)
    rows = doc.get("rule_states") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return [], {"status": UNMEASURED,
                    "why": f"{path.name} absent: the market constitution compiler has not "
                           f"published venue rule states on this box",
                    "measured_by": "the market constitution compiler leg"}
    by_key: dict[str, list[R.Point]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        at = R.parse_time(str(row.get("available_time") or row.get("knowable_at")
                              or row.get("since") or ""))
        value = row.get("value", row.get("state"))
        if at is None:
            continue
        try:
            number = float(value) if not isinstance(value, str) else float(
                {"on": 1, "off": 0, "active": 1, "inactive": 0, "true": 1, "false": 0}
                .get(value.lower(), "nan"))
        except (TypeError, ValueError):
            continue
        if number != number:
            continue
        key = f"rule_state:{row.get('venue') or 'venue'}:{row.get('rule') or 'rule'}"
        by_key.setdefault(key, []).append(R.Point(available_time=at.isoformat(),
                                                  period_time=at.isoformat(), value=number))
    out = [R.Series(series_id=k, points=tuple(sorted(v, key=lambda p: p.available_time)),
                    dataset=f"rule_state:{k.split(':')[1]}", region="VENUE",
                    information_type="rule_state")
           for k, v in sorted(by_key.items()) if len(v) >= R.MIN_PRIOR]
    return out, {"status": "measured", "rows": len(rows), "series": len(out)}


# --------------------------------------------------------------------- contract and genome
def contract_for(series: R.Series, modality: str, at: str) -> DC.DatasetContract:
    base = CONTRACT_BASE.get(modality)
    if base is None:
        return DC.DatasetContract(dataset_id=series.dataset, provenance_state=UNMEASURED,
                                  notes=f"modality {modality}: no declared contract; the field "
                                        f"is typed but inadmissible until one is written")
    meta = {"source_id": series.dataset, "source_class": base["source_class"],
            "licence": base["licence_version"],
            "is_open_data": base["public_or_licensed"] == "OPEN_DATA"}
    verdict = AC.classify(meta)
    schema = {"available_time": "iso8601", "period_time": "iso8601", "value": "float"}
    return DC.DatasetContract(
        dataset_id=series.dataset, source=f"{base['source']} [{series.dataset}]",
        owner=base["owner"], acquisition_method=base["acquisition_method"],
        public_or_licensed=base["public_or_licensed"], licence_version=base["licence_version"],
        permitted_uses=tuple(base["permitted_uses"]),
        redistribution_rights=base["redistribution_rights"],
        personal_data_status=base["personal_data_status"],
        mnpi_review_status=base["mnpi_review_status"], jurisdiction=base["jurisdiction"],
        point_in_time_timestamp=at, revision_policy=base["revision_policy"],
        retention_policy=base["retention_policy"], compliance_owner=base["compliance_owner"],
        provenance_state=DC.provenance_from_verdict(refused=verdict.refused,
                                                    quarantine=verdict.quarantine),
        schema=schema, timestamp_semantics=base["timestamp_semantics"],
        notes=f"access verdict {verdict.access_label}: {verdict.reason}")


def observation_latency_s(series: R.Series) -> float | None:
    """Median seconds between what a point describes and when the desk could read it."""
    gaps: list[float] = []
    for p in series.points[-64:]:
        a, b = R.parse_time(p.available_time), R.parse_time(p.period_time)
        if a is not None and b is not None:
            gaps.append((a - b).total_seconds())
    if not gaps:
        return None
    gaps.sort()
    return gaps[len(gaps) // 2]


def genome_for(series: R.Series, modality: str, entity: str, contract: DC.DatasetContract,
               lineage_id: str, *, researcher: str, transform: tuple[str, ...] = ("identity",),
               lang: str = "") -> FG.Genome:
    meta: dict[str, Any] = {"modality": modality, "n": len(series.points),
                            "information_type": series.information_type, "region": series.region}
    latency = observation_latency_s(series)
    if latency is not None:
        meta["observation_latency_s"] = latency
    if modality == "physical_observations":
        meta["sensor_lineage"] = series.dataset
    if lang:
        meta["language"] = lang
    return FG.genome(series.series_id, data_origin=[series.dataset],
                     pit_normalisation=[PIT_LABEL.get(modality, UNMEASURED)],
                     entity_alignment=[entity],
                     representation=[f"{modality}:{series.information_type or 'series'}"],
                     transform=list(transform), researcher=[researcher],
                     contract_ids=[contract.content_hash()[:16]], lineage_ids=[lineage_id],
                     meta=meta)


def _points_rows(series: R.Series) -> list[dict[str, Any]]:
    return [{"available_time": p.available_time, "period_time": p.period_time, "value": p.value}
            for p in series.sorted().points]


# ------------------------------------------------------------------------------- the pass
def _append_lineage(records: list[dict[str, Any]]) -> None:
    LINEAGE.parent.mkdir(parents=True, exist_ok=True)
    if LINEAGE.exists() and LINEAGE.stat().st_size > MAX_LINEAGE_BYTES:
        tail = LINEAGE.read_text("utf-8").splitlines()[-20_000:]
        LINEAGE.write_text("\n".join(tail) + "\n", "utf-8")
    with LINEAGE.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, default=str, sort_keys=True) + "\n")


def _bounded(store: dict[str, Any], new: dict[str, Any], cap: int) -> dict[str, Any]:
    merged = {**store, **new}
    if len(merged) <= cap:
        return merged
    keep = sorted(merged.items(), key=lambda kv: str(kv[1].get("recorded_at") or ""))[-cap:]
    return dict(keep)


def run(*, budget_s: float = BUDGET_S, dry_run: bool = False, max_typed: int = MAX_TYPED,
        conn: Any = None) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + budget_s
    at = now_iso()
    code = _code_version()
    universe = universe_symbols()
    cursor = _read_json(CURSOR, {}) if CURSOR.exists() else {}
    if not isinstance(cursor, dict):
        cursor = {}
    unmeasured: list[dict[str, Any]] = []
    modality_notes: dict[str, Any] = {}

    # 1. DISCOVER: the numeric PIT series the desk holds, through the world model's own loader.
    held = WM.load_inputs(max_series=MAX_SERIES)
    unmeasured.extend({"modality": "numeric", **u} for u in held.unmeasured)
    own: list[R.Series] = []
    # 1a. prices, a rotating window over the universe so every symbol is typed over time.
    symbols = price_symbols()
    if symbols:
        start = int(cursor.get("prices") or 0) % len(symbols)
        window = [symbols[(start + i) % len(symbols)] for i in range(min(MAX_PRICE_SYMBOLS,
                                                                          len(symbols)))]
        cursor["prices"] = (start + len(window)) % len(symbols)
        prices, missing = price_series(window)
        own.extend(prices)
        unmeasured.extend({"modality": "prices", **m} for m in missing)
        modality_notes["prices"] = {"universe": len(symbols), "window": window,
                                    "series": len(prices)}
    else:
        unmeasured.append({"modality": "prices", "name": "universe bars",
                           "why": "no *_H1.parquet under data/universe",
                           "measured_by": "the refresh_bars leg"})
    # 1b. text claims through polyglot.
    c = conn or REG.connect()
    try:
        claims = claim_rows(c)
        if claims and time.monotonic() < deadline:
            texts, note = claim_series(claims, universe)
            own.extend(texts)
            modality_notes["text_claims"] = note
        else:
            unmeasured.append({"modality": "text_claims", "name": "registry claims",
                               "why": "no claim with text in the registry on this host",
                               "measured_by": "the world crawler / deep forest / seat legs"})
        # 1c. calendars and rule states.
        cal, cal_note = calendar_series()
        own.extend(cal)
        modality_notes["calendars"] = cal_note
        if cal_note.get("status") == UNMEASURED:
            unmeasured.append({"modality": "calendars", **cal_note})
        rules, rule_note = rule_state_series()
        own.extend(rules)
        modality_notes["rule_states"] = rule_note
        if rule_note.get("status") == UNMEASURED:
            unmeasured.append({"modality": "rule_states", **rule_note})

        # 2-4. PIT ARCHIVE, SEMANTICS, ENTITY MAPPING: contract + lineage + genome per field.
        everything = [*own, *held.series]
        typed: dict[str, dict[str, Any]] = {}
        contracts: dict[str, dict[str, Any]] = {}
        lineage_rows: list[dict[str, Any]] = []
        route: Counter[str] = Counter()
        per_modality: dict[str, Counter[str]] = {m: Counter() for m in MODALITIES}
        examples: dict[str, list[str]] = {m: [] for m in MODALITIES}
        inadmissible: list[dict[str, Any]] = []
        lane_held: list[str] = []
        forge_inputs: list[R.Series] = []
        for series in everything:
            if len(typed) >= max_typed or time.monotonic() >= deadline:
                break
            modality = modality_of(series)
            per_modality[modality]["discovered"] += 1
            route["DISCOVERED"] += 1
            if len(series.points) < R.MIN_PRIOR:
                per_modality[modality]["short"] += 1
                continue
            contract = contracts.get(series.dataset)
            if contract is None:
                built = contract_for(series, modality, at)
                snap = DC.snapshot(built, _points_rows(series), at=at, code_version=code,
                                   transform="type")
                contracts[series.dataset] = {"contract": snap.contract.to_json(),
                                             "admission": snap.contract.admission().to_json(),
                                             "recorded_at": at}
                lineage_rows.append(snap.lineage.to_json())
                contract = contracts[series.dataset]
                if not snap.contract.admissible():
                    inadmissible.append({"dataset_id": series.dataset,
                                         "reasons": list(snap.contract.admission().reasons)})
            lineage_id = str(lineage_rows[-1]["lineage_id"]) if lineage_rows else UNMEASURED
            route["PIT_ARCHIVED"] += 1
            route["SEMANTICS"] += 1
            entity = entity_of(series, universe)
            route["ENTITY_MAPPED"] += 1
            researcher = "representation_forge" if modality == "representations" \
                else "feature_compiler"
            gen = genome_for(series, modality, entity, DC.DatasetContract.from_json(
                contract["contract"]), lineage_id, researcher=researcher)
            admissible = bool(contract["admission"]["admitted"])
            forge_ok = admissible and series in own and modality != "representations"
            symbol = entity if not entity.startswith("region:") else ""
            if forge_ok and modality == "prices" and symbol and not may_hypothesise(symbol):
                forge_ok = False
                lane_held.append(series.series_id)
            if forge_ok:
                forge_inputs.append(series)
            typed[series.series_id] = {
                "feature_id": series.series_id, "modality": modality, "entity": entity,
                "dataset": series.dataset, "n": len(series.points), "admissible": admissible,
                "route": ("FORGED" if forge_ok else
                          ("WORLD_MODEL_INPUT" if series in held.series else "ENTITY_MAPPED")),
                "genome": gen.to_json(), "recorded_at": at,
            }
            per_modality[modality]["typed"] += 1
            if len(examples[modality]) < 6:
                examples[modality].append(series.series_id)

        # 5. THE FORGE: the compiler's own admissible fields become transforms, compositions and
        #    interactions in the forge's store, which the world model reads next pass.
        forge_report: dict[str, Any] = {"status": "SKIPPED", "why": "no forgeable inputs"}
        minted_genomes = 0
        if forge_inputs and time.monotonic() < deadline:
            remaining = max(30.0, (deadline - time.monotonic()) * 0.6)
            inputs = WM.Inputs(series=forge_inputs, unmeasured=[], arrays=WM._prepare(forge_inputs))
            try:
                forged = RF.run(budget_s=remaining, dry_run=dry_run, max_new=MAX_FORGE_NEW,
                                inputs=inputs)
                forge_report = {"status": "RAN", "minted": forged.get("minted"),
                                "refused": forged.get("refused"),
                                "newest_ids": forged.get("newest_ids"),
                                "elapsed_s": forged.get("elapsed_s"),
                                "store": forged.get("store")}
                route["FORGED"] += len(forge_inputs)
                if not dry_run:
                    mine = {s.series_id for s in forge_inputs}
                    for rid, row in RF.existing_manifest().items():
                        srcs = {str(x) for x in (row.get("inputs") or [])}
                        if not srcs & mine or rid in typed:
                            continue
                        origin = next((s for s in forge_inputs if s.series_id in srcs), None)
                        if origin is None:
                            continue
                        modality = modality_of(origin)
                        gen = FG.genome(rid, data_origin=[origin.dataset],
                                        pit_normalisation=[PIT_LABEL["representations"]],
                                        entity_alignment=[entity_of(origin, universe)],
                                        representation=[f"representation:{row.get('family')}"],
                                        transform=str(row.get("transform") or "").split("|"),
                                        researcher=["representation_forge"],
                                        contract_ids=[str(contracts.get(origin.dataset, {})
                                                          .get("contract", {})
                                                          .get("contract_hash", ""))[:16]],
                                        meta={"modality": modality, "n": row.get("n"),
                                              "forge_inputs": sorted(srcs)})
                        typed[rid] = {"feature_id": rid, "modality": "representations",
                                      "entity": entity_of(origin, universe),
                                      "dataset": str(row.get("dataset")), "n": row.get("n"),
                                      "admissible": True, "route": "WORLD_MODEL_INPUT",
                                      "genome": gen.to_json(), "recorded_at": at}
                        minted_genomes += 1
                        route["WORLD_MODEL_INPUT"] += 1
            except Exception as exc:  # the forge never takes the compiler's report with it
                forge_report = {"status": "ERROR", "why": f"{type(exc).__name__}: {exc}"}
        route["WORLD_MODEL_INPUT"] += sum(1 for t in typed.values()
                                          if t["route"] == "WORLD_MODEL_INPUT") - minted_genomes

        # 6. RECORD: genomes, contracts, lineage, registry -- unless dry.
        registry_status: dict[str, Any] = {"status": "SKIPPED_DRY_RUN"}
        if not dry_run:
            old_genomes = _read_json(GENOMES, {}).get("genomes", {}) if GENOMES.exists() else {}
            old_contracts = _read_json(CONTRACTS, {}).get("contracts", {}) \
                if CONTRACTS.exists() else {}
            genomes_doc = _bounded(old_genomes if isinstance(old_genomes, dict) else {},
                                   typed, MAX_GENOMES)
            contracts_doc = _bounded(old_contracts if isinstance(old_contracts, dict) else {},
                                     contracts, MAX_CONTRACTS)
            _atomic(GENOMES, {"at": at, "rule": FG.RULE, "layers": list(FG.LAYERS),
                              "n": len(genomes_doc), "genomes": genomes_doc})
            _atomic(CONTRACTS, {"at": at, "rule": DC.LEGALITY_RULE,
                                "fields": list(DC.CONTRACT_FIELDS), "n": len(contracts_doc),
                                "contracts": contracts_doc})
            _append_lineage(lineage_rows)
            _atomic(CURSOR, cursor)
            new_rows = 0
            for fid, row in typed.items():
                if row["modality"] == "representations" and row["genome"]["researcher"] == [
                        "representation_forge"] and fid not in (forge_report.get("newest_ids")
                                                                or []):
                    continue
                try:
                    new_rows += int(REG.representation_upsert(
                        fid, dataset=str(row["dataset"]),
                        transform="|".join(row["genome"]["transform"]) or "identity",
                        family="ingested" if row["modality"] != "representations" else str(
                            row["genome"]["representation"][0].split(":")[-1]),
                        n_points=int(row["n"] or 0), origin="feature_compiler",
                        genome_json=row["genome"], contract_id=str(
                            row["genome"]["contract_ids"][0] if row["genome"]["contract_ids"]
                            else ""),
                        lineage_hash=str(row["genome"]["lineage_ids"][0]
                                         if row["genome"]["lineage_ids"] else ""), conn=c))
                except Exception as exc:
                    registry_status = {"status": "ERROR", "why": f"{type(exc).__name__}: {exc}"}
                    break
            else:
                registry_status = {"status": "OK", "upserted": len(typed), "new": new_rows}
    finally:
        if conn is None:
            c.close()

    genomes_all = [FG.Genome.from_json(t["genome"]) for t in typed.values()]
    concentration = FG.lineage_concentration((g, 1.0) for g in genomes_all)
    depth: Counter[int] = Counter(g.depth for g in genomes_all)
    report = {
        "at": at, "rule": RULE, "law": "LAWS 5m; RESEARCH 11 (UniversalCell / DatasetContract)",
        "budget_s": budget_s, "elapsed_s": round(time.monotonic() - started, 2),
        "dry_run": dry_run, "code_version": code,
        "modalities": {m: {**dict(per_modality[m]), "examples": examples[m],
                           "note": modality_notes.get(m)} for m in MODALITIES},
        "route": {step: int(route.get(step, 0)) for step in ROUTE},
        "typed": len(typed), "max_typed": max_typed,
        "lane_held": {"n": len(lane_held), "ids": lane_held[:20],
                      "why": "single-name equities are typed and contracted but never forged "
                             "into the hypothesis lane (two-lane mandate)"},
        "contracts": {"n": len(contracts),
                      "admissible": sum(1 for v in contracts.values()
                                        if v["admission"]["admitted"]),
                      "inadmissible": inadmissible[:20], "fields": list(DC.CONTRACT_FIELDS),
                      "gate": DC.LEGALITY_RULE},
        "genome": {"n": len(genomes_all), "layers": list(FG.LAYERS),
                   "depth_histogram": {str(k): v for k, v in sorted(depth.items())},
                   "by_researcher": dict(Counter(
                       t["genome"]["researcher"][0] if t["genome"]["researcher"] else "none"
                       for t in typed.values())),
                   "forge_minted_genomes": minted_genomes},
        "lineage": {"records_written": 0 if dry_run else len(lineage_rows),
                    "records_built": len(lineage_rows), "path": str(LINEAGE),
                    "replay_keys": [r["replay_key"] for r in lineage_rows[:10]]},
        "concentration": {"of": "the feature store, equal weights (the allocator's own reading "
                                "is feature_genome.lineage_concentration over the book)",
                          **concentration.to_json()},
        "forge": forge_report,
        "registry": registry_status,
        "store": {"genomes": str(GENOMES), "contracts": str(CONTRACTS), "cursor": cursor},
        "unmeasured": unmeasured[:60],
        "n_unmeasured": len(unmeasured),
    }
    if not dry_run:
        _atomic(OUT, report)
    return report


def summary_lines(doc: dict[str, Any]) -> list[str]:
    mods = doc.get("modalities", {})
    counts = ", ".join(f"{m}={v.get('typed', 0)}" for m, v in mods.items() if v.get("typed"))
    return [f"feature_compiler: typed {doc.get('typed')} fields ({counts})"
            f" contracts {doc['contracts']['admissible']}/{doc['contracts']['n']} admissible; "
            f"forge {doc['forge'].get('status')} minted={doc['forge'].get('minted')}; "
            f"unmeasured {doc.get('n_unmeasured')}; {doc.get('elapsed_s')}s"
            + (" DRY-RUN" if doc.get("dry_run") else "")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--max-typed", type=int, default=MAX_TYPED)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, dry_run=args.dry_run, max_typed=args.max_typed)
    for line in summary_lines(doc):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
