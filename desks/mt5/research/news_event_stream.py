#!/usr/bin/env python3
"""NEWS AS A FIRST-CLASS EVENT STREAM -- two brains, one world state, and nothing that sizes.

THE PRINCIPAL'S ORDER (2026-09-17, permanent). News feeds the world model and the allocator; an
LLM never improvises a trade off a headline. There is no rule on this desk of the form
WAR = BUY GOLD. What the machine estimates is

    p(R_i | event, location, energy exposure, rates, USD state, positioning, liquidity, regime)

and the path is fixed: headline -> source verification -> classification -> affected countries and
assets -> transmission graph -> vol/liquidity shock estimate -> conditional sleeve distributions
-> ALLOCATOR RE-SOLVE -> execution -> continuous re-pricing. The realistic edge is seconds-to-
minutes repricing, cross-asset propagation, regime change, positioning unwinds and hours-to-days
of transmission. The first millisecond belongs to somebody with a microwave tower and is not
hunted here.

TWO BRAINS, AND THE SPLIT IS THE DESIGN.

  THE FAST LANE is deterministic and runs on every item: receipt stamp, SOURCE CONFIDENCE off the
  ontology's ladder, classification, entities, novelty against what the log already holds,
  surprise against the calendar, the affected set, and one PRECISION-WEIGHTED NUDGE to the world
  state in logit space. No model is called, no text is generated, nothing is sized. It writes
  `data/world_state.json` atomically and lodges a RE-SOLVE REQUEST the allocator MAY read.

  THE DEEP LANE runs only above novelty x surprise, and it is where interpretation lives: the
  transmission edges spelled out, analogues from the event atlas, cross-country transmission
  through the entity graph, positioning from COT, macro implications, a scenario tree with
  DECLARED priors, and the secondary and tertiary effects two and three hops out. Its output is a
  `research_memory` row of kind `event_deep` and a DISCOVERY per newly implied mechanism, so the
  compiler and the ten gates judge it exactly as harshly as anything else. It mints no cells of
  its own and it trades nothing.

THE FIRST HEADLINE IS NEVER FINAL. A follow-up on the same (kind, entities) key carries the same
`event_id` and moves the SAME posterior: `m += k * w/(tau + w)`, `tau += w`, with w falling as
novelty falls. So fourteen re-filings of one wire story move the state once and then barely at
all, while a genuinely new escalation on the same story moves it again -- which is the difference
between evidence and echo, and it is arithmetic rather than a filter somebody has to maintain.

NOTHING HERE SIZES, CAPS, VETOES OR SHRINKS (GROWTH_GOVERNANCE, and the standing order of
2026-09-08 that the desk never reduces its aggressiveness). The heat floor is untouched, no
allocator fraction is written, and the execution recommendations are ADVISORY rows in a report.
The nudge table is TWO-SIDED by construction: a ceasefire lowers geopolitical risk exactly as a
strike raises it, and a restored export terminal raises `energy_supply`. A one-sided table would
make the world state a ratchet towards fear, which is a capital modifier nobody voted for.

WIRING (III.16). The hourly leg `news_event_stream` runs `--once` inside the macro department's
24/7 resident, and `--resident` (every 60 s, singleton-locked) is the box task MT5-NewsResident
(`desks/mt5/scripts/install_news_resident_task.ps1`, declared in `ops/box_tasks.manifest`).

THE WORLD SENSOR LAYER (principal 2026-10-05/06). Intake is a FIREHOSE, not a quota: every ground
is read from a cursor, so nothing between two passes is skipped (until 2026-10-06 a pass kept only
the newest 400 items and silently dropped the rest); a pass that runs out of budget spills what
it did not reach to a durable pending file read first next time. GDELT's 15-minute export blobs,
English and machine-translated, already vaulted by `alt_proxies`, are read here as machine-coded
story groups whose surprise is their coverage ANOMALY against their own (kind, country) history.
A syndicated copy -- the same normalised headline inside the window -- is counted as an
observation and never as independent evidence. Every document becomes a
`libs.research.sensor_contract` observation on the shared ledger with its separate clocks, and
`reports/WORLD_SENSOR_INTAKE.json` publishes the day's measured throughput, compression,
coverage, latency distributions and conversion. Re-solve requests are SEQUENCED and appended to
`data/allocator_resolve_queue.jsonl` with the world-state fingerprint, so a busy consumer misses
none and can tell which inputs it last solved on.

    python research/news_event_stream.py --once
    python research/news_event_stream.py --resident --interval-s 60
    python research/news_event_stream.py --once --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import event_ontology as onto  # noqa: E402

DATA = _DESK / "data"
REPORTS = _DESK / "reports"
WORLD_STATE = DATA / "world_state.json"
RESOLVE_REQUEST = DATA / "allocator_resolve_request.json"
EVENT_LOG = DATA / "events" / "events.jsonl"
REPORT = REPORTS / "NEWS_EVENT_STREAM.json"
NEWS_CAPTURES = DATA / "news_captures.jsonl"
INTEL = DATA / "intelligence"
MOAT_NORMALIZED = _ROOT / "data" / "moat" / "normalized"
UNIVERSE = DATA / "universe" / "universe.json"
ATLAS = REPORTS / "EVENT_RESPONSE_ATLAS.json"
EXEC_ALPHA = REPORTS / "EXECUTION_ALPHA.json"
COT = DATA / "axes" / "cot.json"
MACRO_STATE = DATA / "macro_state.json"
CALENDAR = DATA / "forced_flow_calendar.json"
ACTOR_ATLAS = DATA / "actor_atlas.json"
SENSOR_ROOT = DATA / "sensors"

UNMEASURED = "UNMEASURED"
SOURCE = "news_event_stream"
RULE = ("news is an event stream feeding the world model and the allocator; there is no rule of "
        "the form WAR = BUY GOLD. Nothing here sizes, caps, vetoes or shrinks: the fast lane "
        "publishes a posterior with its uncertainty and REQUESTS a re-solve, and the allocator "
        "decides by dE[log W].")

#: The world-state vector, with each component's RESTING value -- where it relaxes to when no
#: event has spoken for a while. `energy_supply` and `usd_liquidity` rest at 0.5 because they are
#: two-sided availabilities: a disruption lowers them and a restart raises them.
COMPONENTS: dict[str, float] = {
    "vol_shock": 0.20, "liquidity_shock": 0.15, "risk_off": 0.35, "energy_supply": 0.50,
    "usd_liquidity": 0.50, "geopolitical_risk": 0.25, "rates_repricing": 0.20,
    "inflation_pressure": 0.35, "trade_friction": 0.20, "sovereign_stress": 0.15,
}

#: PER-KIND LOGISTIC NUDGE, in LOGIT units, and TWO-SIDED by construction. The magnitude is a
#: DECLARED prior, not a measurement: it says how far one fully-confident, fully-novel, fully-
#: surprising item of this kind may move a component, and the falsifier is the event atlas's own
#: realised distribution once the desk has counted enough of the kind.
NUDGE: dict[str, dict[str, float]] = {
    "war_escalation": {"geopolitical_risk": 1.6, "vol_shock": 1.0, "risk_off": 0.8,
                       "energy_supply": -0.7, "liquidity_shock": 0.5},
    "ceasefire": {"geopolitical_risk": -1.4, "vol_shock": -0.6, "risk_off": -0.6,
                  "energy_supply": 0.5},
    "sanctions": {"geopolitical_risk": 0.9, "trade_friction": 1.2, "energy_supply": -0.6,
                  "usd_liquidity": -0.3, "vol_shock": 0.4},
    "tariffs": {"trade_friction": 1.5, "risk_off": 0.5, "vol_shock": 0.4,
                "inflation_pressure": 0.5},
    "central_bank_surprise": {"rates_repricing": 1.5, "vol_shock": 0.8, "usd_liquidity": -0.4,
                              "risk_off": 0.3},
    "inflation_surprise": {"inflation_pressure": 1.4, "rates_repricing": 0.9, "vol_shock": 0.5},
    "labour_surprise": {"rates_repricing": 1.0, "vol_shock": 0.5, "inflation_pressure": 0.4},
    "supply_disruption": {"energy_supply": -1.4, "inflation_pressure": 0.6, "vol_shock": 0.6,
                          "trade_friction": 0.4},
    "sovereign_default": {"sovereign_stress": 1.7, "risk_off": 1.0, "liquidity_shock": 0.9,
                          "usd_liquidity": -0.7, "vol_shock": 0.8},
    "natural_disaster": {"vol_shock": 0.5, "inflation_pressure": 0.4, "energy_supply": -0.4},
    "corporate_shock": {"vol_shock": 0.5, "risk_off": 0.3, "liquidity_shock": 0.2},
    "fx_intervention": {"vol_shock": 1.0, "liquidity_shock": 0.7, "usd_liquidity": 0.3,
                        "rates_repricing": 0.4},
    "election": {"vol_shock": 0.6, "risk_off": 0.3, "sovereign_stress": 0.3},
    "political_instability": {"geopolitical_risk": 1.2, "sovereign_stress": 0.8, "vol_shock": 0.7,
                              "risk_off": 0.5},
    "strike": {"energy_supply": -0.5, "trade_friction": 0.5, "inflation_pressure": 0.3},
    "cyber_attack": {"liquidity_shock": 1.0, "vol_shock": 0.6, "risk_off": 0.4},
    "pandemic": {"risk_off": 0.9, "vol_shock": 0.7, "trade_friction": 0.6, "energy_supply": -0.3},
    "other": {},
}

#: DECLARED shock-covariance adjustment per kind: how much the correlation between two asset
#: classes moves while the event is live, and how much the TAIL dependence rises with it. A
#: prior for the allocator to read, published with that word on it -- never fitted here.
SHOCK_CORR: dict[str, tuple[tuple[str, str, float], ...]] = {
    "war_escalation": (("Energy", "Commodities", 0.25), ("Indices", "Forex", 0.20),
                       ("Commodities", "Forex", 0.15), ("Indices", "Bonds", -0.20)),
    "ceasefire": (("Energy", "Commodities", -0.15), ("Indices", "Forex", -0.10)),
    "sanctions": (("Energy", "Commodities", 0.20), ("Forex Exotics", "Indices", 0.20)),
    "tariffs": (("Indices", "Forex", 0.25), ("Soft Commodity", "Indices", 0.15)),
    "central_bank_surprise": (("Bonds", "Forex", 0.30), ("Bonds", "Indices", 0.25),
                              ("Commodities", "Forex", 0.20)),
    "inflation_surprise": (("Bonds", "Indices", 0.30), ("Bonds", "Commodities", 0.20)),
    "labour_surprise": (("Bonds", "Forex", 0.25), ("Bonds", "Indices", 0.20)),
    "supply_disruption": (("Energy", "Soft Commodity", 0.20), ("Energy", "Indices", 0.15)),
    "sovereign_default": (("Forex Exotics", "Bonds", 0.35), ("Indices", "Forex", 0.30),
                          ("Commodities", "Indices", 0.25)),
    "fx_intervention": (("Forex", "Forex Exotics", 0.30), ("Forex", "Bonds", 0.20)),
    "political_instability": (("Forex Exotics", "Commodities", 0.20), ("Indices", "Forex", 0.15)),
    "cyber_attack": (("Indices", "Forex", 0.20), ("Indices", "Bonds", 0.15)),
    "pandemic": (("Indices", "Energy", 0.30), ("Indices", "Forex", 0.25)),
}
#: How far tail dependence rises with the correlation shock. One number per kind; absent means
#: the kind has no declared shock structure and the model says UNMEASURED for it.
TAIL_LIFT: dict[str, float] = {"war_escalation": 0.30, "sovereign_default": 0.40,
                               "central_bank_surprise": 0.20, "pandemic": 0.30,
                               "cyber_attack": 0.25, "supply_disruption": 0.20,
                               "tariffs": 0.20, "fx_intervention": 0.20,
                               "sanctions": 0.20, "political_instability": 0.20,
                               "inflation_surprise": 0.20, "labour_surprise": 0.15,
                               "ceasefire": -0.15}

#: Which ladder tier a seat, host or source id sits on. Matched as a substring, longest first, so
#: `federalreserve.gov` reaches `official_statement` before `reserve` reaches anything else.
SOURCE_TIERS: tuple[tuple[str, str], ...] = (
    ("federalreserve", "official_statement"), ("central_bank", "official_statement"),
    ("centralbank", "official_statement"), ("ecb.europa", "official_statement"),
    ("boj.or.jp", "official_statement"), ("bis.org", "official_statement"),
    ("bis_speeches", "official_statement"), ("sec_edgar", "official_statement"),
    ("treasury", "official_statement"), ("imf.org", "official_statement"),
    ("bls.gov", "official_data_release"), ("eia.gov", "official_data_release"),
    ("eurostat", "official_data_release"), ("statistics", "official_data_release"),
    ("reuters", "major_wire"), ("apnews", "major_wire"), ("bloomberg", "major_wire"),
    ("xinhua", "major_wire"), ("tass", "major_wire"), ("afp.com", "major_wire"),
    ("kyodo", "major_wire"), ("yonhap", "major_wire"), ("interfax", "major_wire"),
    ("investing", "credible_reporting"), ("ft.com", "credible_reporting"),
    ("nikkei", "credible_reporting"), ("caixin", "credible_reporting"),
    ("forexfactory", "aggregator"), ("ff_calendar", "aggregator"), ("feed", "aggregator"),
    ("reddit", "social_claim"), ("tradingview", "social_claim"), ("youtube", "social_claim"),
    ("telegram", "social_claim"), ("weibo", "social_claim"), ("twitter", "social_claim"),
)
#: Seats under `data/intelligence/` whose rows are NEWS-LIKE. A seat absent from this tuple is
#: not read by the stream and is named in the report, so the gap is visible rather than assumed.
NEWS_SEATS: tuple[str, ...] = ("central_banks", "bis_speeches", "investing", "forexfactory",
                               "earnings", "shipping", "weather", "china", "asia", "korea",
                               "world", "sec_edgar")

TAU0 = 4.0                 # resting precision of a world-state component, in effective items
WEIGHT_SCALE = 3.0         # what one fully-confident, fully-novel, fully-surprising item weighs
HALF_LIFE_H = 6.0          # how fast the state relaxes back towards rest with no new evidence
DEEP_THRESHOLD = 0.35      # novelty x surprise above which the deep lane runs
DEEP_CONFIDENCE = 0.35     # and the source confidence it must also clear
RESOLVE_DELTA = 0.02       # |delta value| on any component that justifies a re-solve request
LOG_TAIL_BYTES = 4 * 1024 * 1024
RECENT_HOURS = 48.0        # the novelty window
#: NO ARTICLE QUOTA (principal 2026-10-05: "5,000/day is not a target or ceiling"). Until
#: 2026-10-06 this was MAX_ITEMS = 400 and `collect_items` kept the 400 NEWEST items of each
#: pass, so on a busy hour everything older than the newest 400 was never classified at all --
#: a silent drop, not a backlog. Intake is now CURSOR-driven: every ground is read from where the
#: last pass stopped, a pass works for at most `--budget-s`, and whatever it could not reach is
#: spilled to PENDING and read FIRST next pass. 0 means unbounded; a positive limit is for tests.
MAX_ITEMS = 0
DEFAULT_BUDGET_S = 240.0   # wall time one pass may spend classifying before it spills
MAX_TEXT = 4000
MAX_EXEC_ROWS = 12
#: Per-kind slice of the novelty window a candidate is compared against. Without it novelty and
#: story resolution scan the WHOLE 48 h window for every item, which is quadratic in throughput.
#: Same kind is the only thing those functions compare anyway; the newest rows are the ones a
#: follow-up continues, so the slice keeps the semantics and drops the quadratic cost.
RECENT_PER_KIND = 600
CURSOR = DATA / "news_event_stream_cursor.json"
PENDING = DATA / "news_event_stream_pending.jsonl"
#: Every re-solve request ever lodged, append-only and SEQUENCED, so a consumer that was busy when
#: two arrived misses neither (the single-file request is overwritten each pass and kept only for
#: readers that already know it). Each row carries the world-state FINGERPRINT the allocator can
#: compare to the inputs it last solved on.
RESOLVE_QUEUE = DATA / "allocator_resolve_queue.jsonl"
INTAKE_REPORT = REPORTS / "WORLD_SENSOR_INTAKE.json"
LOCK = DATA / "locks" / "news_event_stream.lock"
#: Held for the length of ONE pass by every caller (hourly --once and each resident pass).
PASS_LOCK = DATA / "locks" / "news_event_stream.pass.lock"
#: GDELT 2.0 export blobs that `alt_proxies` already fetches and vaults every pass: the English
#: stream and the machine-translated stream of 65 source languages. Read here, never re-fetched.
GDELT_VAULTS: tuple[tuple[str, Path], ...] = (
    ("gdelt_events", DATA / "lake" / "vault" / "alt_gdelt_events_country"),
    ("gdelt_translingual", DATA / "lake" / "vault" / "alt_gdelt_translingual_country"),
)
#: How a syndicated copy is recognised: the same normalised headline (or opening text) inside
#: the novelty window. A copy is counted as a raw observation and never as independent evidence.
COPY_WINDOW_H = RECENT_HOURS
SEEN_TTL_D = 7.0


# ============================================================================= small utilities
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(when: datetime) -> str:
    return when.astimezone(UTC).isoformat(timespec="seconds")


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text:
        return None
    with suppress(ValueError):
        got = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return got if got.tzinfo else got.replace(tzinfo=UTC)
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"):
        with suppress(ValueError):
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
    return None


def _logit(p: float) -> float:
    q = min(max(float(p), 1e-6), 1.0 - 1e-6)
    return math.log(q / (1.0 - q))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, float(x)))))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:                  # a read-only destination is WinError 5 on this box
        path.chmod(0o644)
        os.replace(tmp, path)


def _append(path: Path, rows: Sequence[Mapping[str, Any]]) -> int:
    """APPEND-ONLY. The log is never rewritten, never truncated, never deduplicated in place."""
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), default=str) + "\n")
    return len(rows)


def _tail_rows(path: Path, limit: int = 4000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - LOG_TAIL_BYTES))
            blob = handle.read().decode("utf-8", "replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in blob.splitlines()[-limit:]:
        if line.strip().startswith("{"):
            with suppress(ValueError):
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    rows.append(parsed)
    return rows


def _understand(text: str) -> tuple[str, tuple[str, ...]]:
    """Language and polyglot concept ids, when polyglot is importable; ('', ()) when it is not."""
    try:
        from libs.research.polyglot import understand
    except ImportError:                                  # pragma: no cover - import-context only
        return "", ()
    try:
        got = understand(text)
    except Exception:                                    # pragma: no cover - polyglot is pure
        return "", ()
    return str(got.lang), tuple(c.concept_id for c in got.concepts)


# ============================================================================= intake
@dataclass(frozen=True)
class Item:
    """One collected document or claim, before anything is read off it.

    `preset_kind` is set only by a MACHINE-CODED ground (GDELT's CAMEO codes): the coder already
    decided the kind, so the keyword classifier is not asked to re-guess it from a synthetic
    sentence. `corroborations` is the ground's own count of INDEPENDENT sources, when it has one.
    """

    item_id: str
    source_id: str
    url: str
    title: str
    text: str
    seen_at: str
    knowable_at: str
    language: str = ""
    origin: str = ""
    preset_kind: str = ""
    entities: tuple[str, ...] = ()
    corroborations: int = 0
    copies: int = 0
    anomaly_key: str = ""
    volume: float = 0.0
    geography: str = ""


def source_tier(source_id: str, url: str = "") -> str:
    """Where a source sits on the confidence ladder, by the longest matching token."""
    hay = f"{source_id} {url}".lower()
    best, best_len = "", -1
    for token, tier in SOURCE_TIERS:
        if token in hay and len(token) > best_len:
            best, best_len = tier, len(token)
    return best or "credible_reporting"


def _item(source_id: str, row: Mapping[str, Any], origin: str) -> Item | None:
    title = str(row.get("title") or row.get("headline") or row.get("name") or "").strip()
    text = str(row.get("text") or row.get("claim") or row.get("summary")
               or row.get("body") or "").strip()[:MAX_TEXT]
    if not title and not text:
        return None
    url = str(row.get("url") or row.get("link") or row.get("source_url") or "")
    prov = row.get("provenance")
    # THE RECEIPT STAMP AND THE KNOWABLE STAMP ARE DIFFERENT FACTS AND ARE READ SEPARATELY. The
    # first is when THIS desk saw it, the second is when the WORLD could -- and a joiner that
    # confuses them has a look-ahead it cannot see.
    seen = _parse_time(row.get("received_at") or row.get("found_at") or row.get("fetched_utc")
                       or (prov.get("fetched_at") if isinstance(prov, Mapping) else None))
    know = _parse_time(row.get("knowable_at") or row.get("published_utc")
                       or row.get("published_at") or row.get("happened_at") or row.get("at"))
    body = f"{title}. {text}".strip()
    item_id = "it_" + onto.event_id("item", (source_id, url, title[:200], body[:200]))[3:]
    return Item(item_id=item_id, source_id=source_id, url=url, title=title, text=text,
                seen_at=_iso(seen) if seen else _iso(_now()),
                knowable_at=_iso(know) if know else UNMEASURED,
                language=str(row.get("language") or ""), origin=origin)


def _rows_of(path: Path, limit: int) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return _tail_rows(path, limit)
    doc = _read_json(path)
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)][-limit:]
    if isinstance(doc, dict):
        for key in ("discoveries", "items", "rows", "documents"):
            value = doc.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)][-limit:]
        return [doc]
    return []


def _norm_text(text: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())


def fingerprint(item: Item) -> str:
    """The SYNDICATION key: the normalised headline, else the opening of the text.

    Fourteen outlets re-filing one wire carry one headline; their bylines, URLs and boilerplate
    differ. Keyed on the headline, the fourteen are one document and thirteen copies.
    """
    base = _norm_text(item.title) or _norm_text(item.text)[:240]
    return hashlib.sha1(base.encode("utf-8"), usedforsecurity=False).hexdigest()[:20]


# ------------------------------------------------------------------- GDELT: machine-coded events
#: CAMEO codes whose MEANING is one of the ontology's kinds. Conservative on purpose: a code is
#: listed only where the CAMEO definition and the kind say the same thing; everything else is
#: counted as an observation and left `other`, which is a measurement of the frontier.
CAMEO_KIND: tuple[tuple[str, str], ...] = (
    ("0871", "ceasefire"), ("0874", "ceasefire"), ("0872", "ceasefire"),
    ("163", "sanctions"), ("1621", "sanctions"),
    ("143", "strike"), ("1431", "strike"), ("1432", "strike"), ("1433", "strike"),
    ("145", "political_instability"), ("1451", "political_instability"),
    ("1452", "political_instability"), ("1453", "political_instability"),
    ("1454", "political_instability"), ("175", "political_instability"),
    ("19", "war_escalation"), ("20", "war_escalation"), ("183", "war_escalation"),
    ("1831", "war_escalation"), ("1832", "war_escalation"), ("1833", "war_escalation"),
    ("195", "war_escalation"), ("196", "war_escalation"),
)
_CAMEO_KIND = dict(CAMEO_KIND)
#: CAMEO actor country (ISO alpha-3) and GDELT ActionGeo (FIPS 10-4) -> the ontology's codes.
_ISO3 = {"USA": "US", "EUR": "EU", "DEU": "DE", "FRA": "FR", "GBR": "GB", "JPN": "JP",
         "CHN": "CN", "RUS": "RU", "UKR": "UA", "ISR": "IL", "IRN": "IR", "SAU": "SA",
         "ARE": "AE", "VEN": "VE", "NGA": "NG", "AUS": "AU", "NZL": "NZ", "CAN": "CA",
         "NOR": "NO", "CHE": "CH", "TUR": "TR", "IND": "IN", "KOR": "KR", "ZAF": "ZA",
         "BRA": "BR", "MEX": "MX", "TWN": "TW"}
_FIPS = {"US": "US", "GM": "DE", "FR": "FR", "UK": "GB", "JA": "JP", "CH": "CN", "RS": "RU",
         "UP": "UA", "IS": "IL", "IR": "IR", "SA": "SA", "AE": "AE", "VE": "VE", "NI": "NG",
         "AS": "AU", "NZ": "NZ", "CA": "CA", "NO": "NO", "SZ": "CH", "TU": "TR", "IN": "IN",
         "KS": "KR", "SF": "ZA", "BR": "BR", "MX": "MX", "TW": "TW"}
#: The independent-source count GDELT reports is capped before it reaches the ladder: GDELT counts
#: outlets, and outlets that syndicate one wire are not independent.
GDELT_MAX_CORROBORATIONS = 5
#: The vault short names -> the alt_proxies registry ids the mining registry credits.
GDELT_REGISTRY_ID = {"gdelt_events": "gdelt_events_country",
                     "gdelt_translingual": "gdelt_translingual_country"}


def _gdelt_kind(code: str, base: str, root: str) -> str:
    for c in (code, base, root):
        k = _CAMEO_KIND.get(str(c).strip())
        if k:
            return k
    return "other"


def _gdelt_slot(meta: Mapping[str, Any]) -> str:
    url = str(meta.get("url") or "")
    tail = url.rsplit("/", 1)[-1]
    slot = tail.split(".", 1)[0]
    return slot if len(slot) == 14 and slot.isdigit() else ""


def gdelt_items(body: bytes, slot: str, ground: str, fetched_utc: str
                ) -> tuple[list[Item], dict[str, int]]:
    """One 15-minute GDELT export -> one item per (kind, country) STORY GROUP, plus a census.

    Every export row is a raw observation; rows sharing a SOURCEURL are one document; rows of the
    same kind in the same country in the same slot are one story group, whose corroboration is
    GDELT's own distinct-source count and whose volume is its article count. Only groups whose
    kind the ontology knows reach the fast lane; the rest are counted, not dropped silently.
    """
    try:
        from alt_proxies import _gdelt_rows  # type: ignore[import-not-found]
    except Exception:                                    # pragma: no cover - import context
        try:
            from research.alt_proxies import _gdelt_rows
        except Exception:
            return [], {"rows": 0, "unreadable": 1}
    rows = _gdelt_rows(body)
    census = {"rows": len(rows), "documents": 0, "groups": 0, "economic_groups": 0}
    urls: set[str] = set()
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for c in rows:
        url = c[60].strip() if len(c) > 60 else ""
        urls.add(url)
        kind = _gdelt_kind(c[26], c[27], c[28].strip().zfill(2) if c[28].strip() else "")
        geo = _FIPS.get(c[53].strip(), "")
        ents = {e for e in (_ISO3.get(c[7].strip(), ""), _ISO3.get(c[17].strip(), ""), geo) if e}
        where = geo or (sorted(ents)[0] if ents else c[53].strip() or "XX")
        g = groups.setdefault((kind, where), {"rows": 0, "articles": 0.0, "sources": 0,
                                               "urls": set(), "entities": set(),
                                               "names": set(), "tone": 0.0})
        g["rows"] += 1
        try:
            arts = float(c[33] or 0.0)
            g["articles"] += arts
            g["sources"] = max(g["sources"], int(float(c[32] or 0)))
            g["tone"] += float(c[34] or 0.0) * max(arts, 1.0)
        except ValueError:
            pass
        if url:
            g["urls"].add(url)
        g["entities"].update(ents)
        for name in (c[6].strip(), c[16].strip(), c[52].strip()):
            if name:
                g["names"].add(name)
    census["documents"] = len(urls - {""})
    added = _parse_time(f"{slot[:4]}-{slot[4:6]}-{slot[6:8]}T{slot[8:10]}:{slot[10:12]}:00+00:00")
    knowable = _iso(added + timedelta(minutes=15)) if added else UNMEASURED
    out: list[Item] = []
    for (kind, where), g in sorted(groups.items()):
        census["groups"] += 1
        if kind == "other":
            continue
        census["economic_groups"] += 1
        names = ", ".join(sorted(g["names"])[:6])
        title = f"{kind.replace('_', ' ')} in {where}: {g['rows']} coded events, " \
                f"{int(g['articles'])} articles ({names})"
        url = sorted(g["urls"])[0] if g["urls"] else ""
        item_id = "it_" + onto.event_id("item", (ground, slot, kind, where))[3:]
        out.append(Item(item_id=item_id, source_id=ground, url=url, title=title,
                        text=f"{title}. tone {g['tone'] / max(g['articles'], 1.0):.2f}",
                        seen_at=fetched_utc or _iso(_now()), knowable_at=knowable,
                        language="multi" if "translingual" in ground else "en",
                        origin=f"gdelt:{ground}", preset_kind=kind,
                        entities=tuple(sorted(g["entities"] or {where})),
                        corroborations=min(GDELT_MAX_CORROBORATIONS, max(0, g["sources"] - 1)),
                        copies=max(0, g["rows"] - 1), anomaly_key=f"{kind}|{where}",
                        volume=float(g["articles"]), geography=where))
    return out, census


# ------------------------------------------------------------------- the cursor
def load_cursor(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or CURSOR)
    if not isinstance(doc, dict):
        doc = {}
    for key in ("files", "offsets", "seen", "fps", "gdelt", "baseline", "day", "pages"):
        doc.setdefault(key, {})
    doc.setdefault("seq", 0)
    return doc


def _prune_cursor(cur: dict[str, Any], when: datetime) -> None:
    now_s = when.timestamp()
    ttl = SEEN_TTL_D * 86400.0
    cur["seen"] = {k: v for k, v in cur["seen"].items() if now_s - float(v) <= ttl}
    win = COPY_WINDOW_H * 3600.0
    cur["fps"] = {k: v for k, v in cur["fps"].items() if now_s - float(v[0]) <= win}
    cur["gdelt"] = {k: v for k, v in cur["gdelt"].items() if now_s - float(v) <= ttl}


def _new_files(files: Iterable[Path], key: str, cur: dict[str, Any]) -> list[Path]:
    """Files under one ground that are new or CHANGED since the cursor last read them."""
    first = key not in cur["files"]
    known: dict[str, list[float]] = cur["files"].setdefault(key, {})
    horizon = _now().timestamp() - RECENT_HOURS * 3600.0
    out = []
    for path in files:
        try:
            st = path.stat()
        except OSError:
            continue
        sig = [round(st.st_mtime, 3), st.st_size]
        # THE FIRST SIGHT OF A GROUND is not a licence to classify its whole history: a file
        # last written before the novelty window cannot describe NOW, so it is marked read.
        if first and st.st_mtime < horizon:
            known[str(path)] = sig
            continue
        if known.get(str(path)) != sig:
            out.append(path)
    return sorted(out, key=lambda p: p.stat().st_mtime if p.exists() else 0.0)


def _mark_files(paths: Iterable[Path], key: str, cur: dict[str, Any]) -> None:
    known: dict[str, list[float]] = cur["files"].setdefault(key, {})
    for path in paths:
        with suppress(OSError):
            st = path.stat()
            known[str(path)] = [round(st.st_mtime, 3), st.st_size]


#: Rows one call may take from one jsonl ground, and rows one pass may take from one seat (paged
#: across that seat's files by `_seat_page`). NOT A CAP: the offset stops at the last row
#: taken, so the rest is read on the next pass (60 s later on the resident) and nothing is lost.
#: It bounds the memory one pass can hold, which a single fh.read() of a ground did not.
MAX_ROWS_PER_READ = 20_000
#: The same bound for the file grounds (audit #204, 2026-10-07): new files a pass takes from the
#: moat store or one seat, and GDELT blobs from one vault. The oldest go first and the rest stay
#: unmarked, so they are read on the next pass -- a bound on memory, never a drop.
MAX_FILES_PER_READ = 2_000
MAX_GDELT_BLOBS_PER_READ = 96
#: While the owed file holds this many items, a pass works the owed set and reads NO ground: the
#: grounds keep their cursors, so nothing is skipped, and the owed file cannot grow without bound.
OWED_GATE = 20_000


def _jsonl_since(path: Path, key: str, cur: dict[str, Any],
                 max_rows: int = MAX_ROWS_PER_READ) -> list[dict[str, Any]]:
    """Rows appended since the cursor's byte offset, STREAMED line by line. A file that SHRANK
    was rotated and is read from the start; the offset moves only over whole lines, and stops
    after `max_rows` rows so one pass never holds a whole ground in memory."""
    try:
        size = path.stat().st_size
    except OSError:
        return []
    # First sight: start from the tail the old reader read, never from a 50 MB history.
    first = key not in cur["offsets"]
    off = int(cur["offsets"].get(key, max(0, size - LOG_TAIL_BYTES)))
    if size < off:
        off = 0
    rows: list[dict[str, Any]] = []
    pos = off
    with path.open("rb") as fh:
        fh.seek(off)
        if first and off > 0:
            skipped = fh.readline()                      # a partial line at the tail cut
            if not skipped.endswith(b"\n"):
                return []
            pos += len(skipped)
        for raw in fh:
            if not raw.endswith(b"\n"):
                break                                    # a row still being written
            pos += len(raw)
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("{"):
                with suppress(ValueError):
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
            if len(rows) >= max_rows:
                break
    cur["offsets"][key] = pos
    return rows


def _iter_seat_rows(path: Path) -> Iterable[dict[str, Any]]:
    """EVERY row of one seat file, oldest (file order) first. A jsonl file is STREAMED line by
    line; a json document is loaded whole (it already was) and its row list walked in order."""
    if path.suffix == ".jsonl":
        try:
            fh = path.open("rb")
        except OSError:
            return
        with fh:
            for raw in fh:
                if not raw.endswith(b"\n"):
                    break                                    # a row still being written
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("{"):
                    with suppress(ValueError):
                        row = json.loads(line)
                        if isinstance(row, dict):
                            yield row
        return
    doc = _read_json(path)
    if isinstance(doc, list):
        yield from (r for r in doc if isinstance(r, dict))
    elif isinstance(doc, dict):
        for key in ("discoveries", "items", "rows", "documents"):
            value = doc.get(key)
            if isinstance(value, list):
                yield from (r for r in value if isinstance(r, dict))
                return
        yield doc


def _row_digest(row: Mapping[str, Any]) -> str:
    blob = json.dumps(row, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _seat_page(path: Path, key: str, cur: dict[str, Any],
               max_rows: int) -> tuple[list[dict[str, Any]], bool]:
    """The next page of a seat file's UNCONSUMED rows, oldest first, and whether the file is now
    consumed to its last row (audit #204 v3, 2026-10-07).

    Until this, a seat file was read as its newest 20,000 rows and then MARKED READ, so every
    older row of a big file was lost for good: a mining cut. Now a file is consumed in bounded
    pages across passes and the caller marks it read only once this returns `done`.

    The page cursor `cur["pages"][key][path]` is one of two shapes:
      * PARTIAL  `{"taken": [digest, ...]}` -- the digest of every row consumed so far. A file
        that changes mid-consumption (an append, or a rewrite that reorders or inserts rows) is
        re-digested and only rows whose digest was not taken are read: none lost, none twice.
      * FINISHED `{"n": rows, "prefix": chained digest of those rows}` -- a few bytes. A later
        APPEND re-digests the first `n` rows, finds the prefix intact and reads only the tail.
        A finished file REWRITTEN in place has no recoverable prefix and is read again from its
        first row; the pass's item-id dedup (`cur["seen"]`) keeps those re-reads from counting.
    Identical rows share a digest and so one item id; they are one observation, read once.
    """
    pages: dict[str, Any] = cur.setdefault("pages", {}).setdefault(key, {})
    state = pages.get(str(path)) or {}
    digests = [_row_digest(r) for r in _iter_seat_rows(path)]
    if "taken" in state:
        consumed = set(state["taken"])
    else:
        n = int(state.get("n", 0))
        consumed = (set(digests[:n]) if 0 < n <= len(digests)
                    and _prefix_of(digests[:n]) == state.get("prefix") else set())
    want: set[int] = set()
    picked: set[str] = set()
    left = 0
    for i, d in enumerate(digests):
        if d in consumed or d in picked:
            continue
        if len(want) < max_rows:
            want.add(i)
            picked.add(d)
        else:
            left += 1
    page = [r for i, r in enumerate(_iter_seat_rows(path))
            if i in want and i < len(digests) and _row_digest(r) == digests[i]]
    if len(page) != len(want):
        # The file was rewritten between the two reads: take nothing, keep the state, and read
        # it again next pass -- nothing marked, so nothing lost.
        return [], False
    if left == 0:
        pages[str(path)] = {"n": len(digests), "prefix": _prefix_of(digests)}
        return page, True
    pages[str(path)] = {"taken": sorted(consumed | picked)}
    return page, False


def _prefix_of(digests: Sequence[str]) -> str:
    acc = ""
    for d in digests:
        acc = hashlib.sha1(f"{acc}|{d}".encode(), usedforsecurity=False).hexdigest()[:16]
    return acc


def collect_items(limit: int = MAX_ITEMS, notes: list[str] | None = None,
                  cursor: dict[str, Any] | None = None,
                  census: dict[str, Any] | None = None) -> list[Item]:
    """Everything NEW since the last pass, from every ground that exists, oldest first.

    Grounds, each read tolerantly and each REPORTED when absent: the moat collectors' normalised
    store, the desk's own news captures, the news-like intelligence seats and the GDELT export
    blobs `alt_proxies` vaults. An absent ground is UNMEASURED and named -- never a clean zero
    (L1.28a). With no cursor (a probe), the newest rows are read as before. `limit` > 0 keeps the
    newest `limit` items and is for tests; the hourly pass and the resident run unbounded.
    """
    out: list[Item] = []
    say = notes if notes is not None else []
    cur = cursor if cursor is not None else load_cursor(Path("/nonexistent/cursor"))
    tally = census if census is not None else {}
    probe_cap = limit if limit > 0 else 4000
    if MOAT_NORMALIZED.exists():
        files = list(MOAT_NORMALIZED.rglob("*.json"))
        fresh = (_new_files(files, "moat_normalized", cur)[:MAX_FILES_PER_READ]
                 if cursor is not None
                 else sorted(files, key=lambda p: p.stat().st_mtime)[-probe_cap:])
        for path in fresh:
            doc = _read_json(path)
            if isinstance(doc, dict):
                got = _item(str(doc.get("source_id") or path.parent.name), doc, "moat_normalized")
                if got is not None:
                    out.append(got)
        _mark_files(fresh, "moat_normalized", cur)
    else:
        say.append(f"{MOAT_NORMALIZED} absent: the moat collectors' normalised store is "
                   f"{UNMEASURED} on this box, so no captured document reached the fast lane")
    if NEWS_CAPTURES.exists():
        rows = (_jsonl_since(NEWS_CAPTURES, "news_captures", cur) if cursor is not None
                else _tail_rows(NEWS_CAPTURES, probe_cap))
        for row in rows:
            got = _item(str(row.get("source") or "news_desk"), row, "news_captures")
            if got is not None:
                out.append(got)
    else:
        say.append(f"{NEWS_CAPTURES} absent: the news desk's own captures are {UNMEASURED}")
    seen_seats = 0
    for seat in NEWS_SEATS:
        folder = INTEL / seat
        if not folder.is_dir():
            continue
        seen_seats += 1
        files = list(folder.glob("*.json*"))
        fresh = (_new_files(files, f"seat:{seat}", cur)[:MAX_FILES_PER_READ]
                 if cursor is not None
                 else sorted(files, key=lambda p: p.stat().st_mtime)[-8:])
        if cursor is None:
            for path in fresh:
                rows = (_rows_of(path, MAX_ROWS_PER_READ) if not path.name.endswith(".gz")
                        else [])
                out.extend(i for r in rows
                           if (i := _item(str(r.get("source") or seat), r,
                                          f"intelligence:{seat}")) is not None)
            continue
        # PAGED, NEVER CUT (audit #204 v3): one pass takes at most MAX_ROWS_PER_READ rows from
        # one seat, oldest file first and oldest row first; a file is marked read only once its
        # last row is taken, and whatever the budget did not reach stays owed to the next pass.
        budget = MAX_ROWS_PER_READ
        t = tally.setdefault(f"seat:{seat}", {"rows": 0, "partial_files": 0,
                                              "deferred_files": 0})
        known: dict[str, list[float]] = cur["files"].setdefault(f"seat:{seat}", {})
        for path in fresh:
            try:
                st = path.stat()                         # the signature BEFORE the read: a row
            except OSError:                              # appended during it changes the file's
                continue                                 # signature, so it is read next pass
            sig = [round(st.st_mtime, 3), st.st_size]
            if path.name.endswith(".gz"):
                known[str(path)] = sig
                continue
            if budget <= 0:
                t["deferred_files"] += 1                 # unmarked: the next pass reads it
                continue
            rows, done = _seat_page(path, f"seat:{seat}", cur, budget)
            budget -= len(rows)
            t["rows"] += len(rows)
            for row in rows:
                got = _item(str(row.get("source") or seat), row, f"intelligence:{seat}")
                if got is not None:
                    out.append(got)
            if done:
                known[str(path)] = sig
            else:
                t["partial_files"] += 1                  # unmarked: its next page is owed
    if not seen_seats:
        say.append(f"none of the {len(NEWS_SEATS)} declared news seats exists under {INTEL}")
    now_s = _now().timestamp()
    for ground, folder in GDELT_VAULTS:
        g = tally.setdefault(ground, {"blobs": 0, "rows": 0, "documents": 0, "groups": 0,
                                      "economic_groups": 0, "too_old": 0})
        if not folder.is_dir():
            g["status"] = f"{folder} absent: {UNMEASURED} on this box"
            continue
        taken = 0
        # THE BACKLOG IS WORKED IN TIME ORDER (audit #204 v3): the oldest 15-minute slot first,
        # chronologically -- never in content-hash order, which is a random walk through time
        # and let a deferred slot from hours ago wait behind newer ones. A meta with no
        # readable slot sorts last (it is history either way and is marked too_old below).
        backlog: list[tuple[str, str, Path, dict[str, Any]]] = []
        for meta_path in folder.glob("*.meta.json"):
            digest = meta_path.name.split(".", 1)[0]
            if digest in cur["gdelt"]:
                continue
            meta = _read_json(meta_path)
            meta = meta if isinstance(meta, dict) else {}
            backlog.append((_gdelt_slot(meta) or "9" * 14, digest, meta_path, meta))
        backlog.sort(key=lambda b: (b[0], b[1]))
        for _slot_key, digest, _meta_path, meta in backlog:
            if taken >= MAX_GDELT_BLOBS_PER_READ:
                g["deferred"] = int(g.get("deferred", 0)) + 1     # unmarked: next pass reads it
                continue
            slot = _gdelt_slot(meta)
            slot_t = _parse_time(f"{slot[:4]}-{slot[4:6]}-{slot[6:8]}T{slot[8:10]}:"
                                 f"{slot[10:12]}:00+00:00") if slot else None
            cur["gdelt"][digest] = now_s
            # A BACKFILL slot is history, not news: the alt_proxies panel owns it. Only a slot
            # inside the novelty window can move the world state that describes NOW.
            if slot_t is None or (now_s - slot_t.timestamp()) > RECENT_HOURS * 3600.0:
                g["too_old"] += 1
                continue
            blob = folder / f"{digest}.gz"
            try:
                import gzip
                body = gzip.decompress(blob.read_bytes())
            except (OSError, EOFError, ValueError):
                continue
            items, c = gdelt_items(body, slot, ground, str(meta.get("fetched_utc") or ""))
            taken += 1
            g["blobs"] += 1
            for k in ("rows", "documents", "groups", "economic_groups"):
                g[k] += int(c.get(k, 0))
            out.extend(items)
    out.sort(key=lambda i: i.seen_at)
    return out[-limit:] if limit > 0 else out


def _spill(items: Sequence[Item]) -> int:
    """Items a pass could not reach are owed to the next one, durably."""
    if not items:
        return 0
    return _append(PENDING, [asdict(i) for i in items])


def _settle_pending(spilled: Sequence[Item]) -> int:
    """After a pass has committed (cursor written): the owed file becomes exactly what THIS pass
    could not reach. Atomic, so a crash leaves either the old owed set or the new one."""
    if not spilled:
        with suppress(OSError):
            PENDING.unlink()
        return 0
    PENDING.parent.mkdir(parents=True, exist_ok=True)
    tmp = PENDING.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for i in spilled:
            fh.write(json.dumps(asdict(i), default=str, ensure_ascii=False) + "\n")
    os.replace(tmp, PENDING)
    return len(spilled)


def _unspill() -> list[Item]:
    """The items the last pass owed. READ ONLY: the file is replaced by `_settle_pending` after
    the pass that processed them has written its cursor, so a crash mid-pass re-owes them."""
    if not PENDING.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with PENDING.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                with suppress(ValueError):
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
    except OSError:
        return []
    out: list[Item] = []
    for r in rows:
        with suppress(TypeError):
            r["entities"] = tuple(r.get("entities") or ())
            out.append(Item(**r))
    return out


# ============================================================================= the world state
def _blank_state(when: datetime) -> dict[str, Any]:
    return {"at": _iso(when), "rule": RULE,
            "components": {name: {"value": rest, "logit": _logit(rest), "sd": 1.0 / math.sqrt(TAU0),
                                  "precision": TAU0, "n_events": 0, "rest": rest,
                                  "updated_at": _iso(when), "last_event": ""}
                           for name, rest in COMPONENTS.items()},
            "shock_model": {}, "events_seen": 0}


def load_state(when: datetime, path: Path | None = None) -> dict[str, Any]:
    """The stored world state, RELAXED towards rest by however long it has been unattended."""
    doc = _read_json(path or WORLD_STATE)
    if not isinstance(doc, dict) or not isinstance(doc.get("components"), dict):
        return _blank_state(when)
    stamp = _parse_time(doc.get("at")) or when
    hours = max(0.0, (when - stamp).total_seconds() / 3600.0)
    decay = 0.5 ** (hours / HALF_LIFE_H)
    state = _blank_state(when)
    for name, rest in COMPONENTS.items():
        stored = doc["components"].get(name)
        if not isinstance(stored, Mapping):
            continue
        rest_logit = _logit(rest)
        m = rest_logit + (float(stored.get("logit", rest_logit)) - rest_logit) * decay
        tau = TAU0 + (float(stored.get("precision", TAU0)) - TAU0) * decay
        state["components"][name] = {
            "value": _sigmoid(m), "logit": m, "sd": 1.0 / math.sqrt(max(tau, 1e-6)),
            "precision": tau, "n_events": int(stored.get("n_events", 0)), "rest": rest,
            "updated_at": str(stored.get("updated_at") or _iso(when)),
            "last_event": str(stored.get("last_event") or "")}
    state["events_seen"] = int(doc.get("events_seen", 0))
    return state


def fast_update(state: dict[str, Any], kind: str, weight: float, event_id: str,
                when: datetime) -> dict[str, dict[str, float]]:
    """ONE precision-weighted nudge, in logit space, two-sided, with its uncertainty.

    `m += k * w/(tau + w)` and `tau += w`. The second telling of the same story arrives with a
    lower `w` (novelty fell) against a higher `tau` (the state already heard it), so it moves the
    posterior LESS -- which is what makes a wire's fourteen re-filings one event rather than
    fourteen, without a rule anybody has to maintain.
    """
    delta: dict[str, dict[str, float]] = {}
    for name, k in NUDGE.get(kind, {}).items():
        cell = state["components"][name]
        before_value, before_sd = float(cell["value"]), float(cell["sd"])
        tau = float(cell["precision"])
        moved = float(k) * weight / (tau + weight)
        m = float(cell["logit"]) + moved
        tau += weight
        cell.update({"logit": m, "value": _sigmoid(m), "precision": tau,
                     "sd": 1.0 / math.sqrt(max(tau, 1e-6)),
                     "n_events": int(cell["n_events"]) + 1,
                     "updated_at": _iso(when), "last_event": event_id})
        delta[name] = {"before": round(before_value, 6), "after": round(cell["value"], 6),
                       "delta": round(cell["value"] - before_value, 6),
                       "logit_delta": round(moved, 6), "sd_before": round(before_sd, 6),
                       "sd_after": round(float(cell["sd"]), 6)}
    return delta


def shock_model(kinds: Iterable[str]) -> dict[str, Any]:
    """The declared shock-covariance adjustment for the kinds seen this pass, for the allocator.

    Correlations RISE between the classes an event reaches at once, and tail dependence rises with
    them: that is the part a Gaussian book gets wrong precisely when it matters. Published as a
    prior with that word attached; the allocator may read it and nothing here applies it.
    """
    pairs: dict[tuple[str, str], float] = {}
    tails: list[float] = []
    named: list[str] = []
    unmeasured: list[str] = []
    for kind in dict.fromkeys(kinds):
        structure = SHOCK_CORR.get(kind)
        if structure is None:
            unmeasured.append(kind)
            continue
        named.append(kind)
        for a, b, d in structure:
            key = (a, b) if a <= b else (b, a)
            pairs[key] = max(pairs.get(key, -1.0), float(d)) if d >= 0 else min(
                pairs.get(key, 1.0), float(d))
        tails.append(TAIL_LIFT.get(kind, 0.0))
    return {"kinds": named, "pairs": [{"a": a, "b": b, "delta_rho": round(d, 4)}
                                      for (a, b), d in sorted(pairs.items())],
            "tail_dependence_lift": round(max(tails), 4) if tails else None,
            "unmeasured_kinds": unmeasured,
            "basis": "DECLARED prior per kind, never fitted here; the falsifier is the realised "
                     "cross-class correlation in the event windows the atlas measures"}


# ============================================================================= the models
def liquidity_model(symbols: Sequence[str], notes: list[str]) -> dict[str, Any]:
    """Spread, gap and slippage expectations from the tape's own event-window statistics.

    Reads `moat_series`' realised spread store. It does not exist on every box, and where it does
    not this returns UNMEASURED BY NAME rather than a default spread -- a made-up cost estimate is
    worse than none, because everything downstream would treat it as measured.
    """
    try:
        from research import moat_series as ms
    except ImportError:                                  # pragma: no cover - import-context only
        notes.append(f"moat_series not importable: the liquidity model is {UNMEASURED}")
        return {"status": UNMEASURED, "why": "moat_series not importable", "symbols": {}}
    out: dict[str, Any] = {}
    missing: list[str] = []
    for symbol in list(dict.fromkeys(symbols))[:MAX_EXEC_ROWS]:
        if symbol.startswith("class:"):
            continue
        frame = ms.series_frame("realised_spread_session", symbol)
        if frame.empty or "spread_median" not in frame.columns:
            missing.append(symbol)
            continue
        tail = frame.tail(20)
        median = float(tail["spread_median"].median())
        p95 = float(tail["spread_median"].quantile(0.95))
        out[symbol] = {"spread_median": round(median, 8), "spread_p95": round(p95, 8),
                       "event_window_multiple": round(p95 / median, 4) if median > 0 else None,
                       "days": len(tail), "source": str(ms.store_path(
                           "realised_spread_session", symbol))}
    if missing:
        notes.append(f"realised_spread_session {UNMEASURED} for {len(missing)} affected symbols: "
                     + ", ".join(missing[:8]))
    return {"status": "measured" if out else UNMEASURED, "symbols": out,
            "unmeasured_symbols": missing,
            "why": "" if out else "the moat's realised-spread store holds none of these symbols"}


def _exec_rows() -> list[dict[str, Any]]:
    doc = _read_json(EXEC_ALPHA)
    rows = doc.get("delayed_vs_immediate") if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def execution_recommendations(symbols: Sequence[str], liquidity: float,
                              notes: list[str]) -> list[dict[str, Any]]:
    """Immediate / delayed / staged / no_trade per affected asset. ADVISORY, and it sizes nothing.

    The evidence is `EXECUTION_ALPHA.delayed_vs_immediate`, which is a PAIRED measurement on this
    broker's own tape: positive `diff_bps` means waiting paid, negative means it cost. A symbol
    the artifact has never measured gets UNMEASURED, not a default -- and `no_trade` appears only
    where the world state's own liquidity-shock reading is extreme, as a row in a report that
    nothing reads as an order.
    """
    rows = _exec_rows()
    if not rows:
        notes.append(f"{EXEC_ALPHA} carries no delayed_vs_immediate rows: every execution "
                     f"recommendation is {UNMEASURED}")
    out: list[dict[str, Any]] = []
    for symbol in list(dict.fromkeys(symbols))[:MAX_EXEC_ROWS]:
        if symbol.startswith("class:"):
            continue
        mine = [r for r in rows if str(r.get("symbol") or "").upper() == symbol.upper()]
        significant = [r for r in mine if bool(r.get("significant"))]
        if liquidity >= 0.75:
            action, why = "no_trade", (f"liquidity_shock {liquidity:.2f}: the tape is not where "
                                       "the desk measured its costs. ADVISORY ONLY")
            best: dict[str, Any] = {}
        elif significant:
            best = max(significant, key=lambda r: abs(float(r.get("diff_bps") or 0.0)))
            diff = float(best.get("diff_bps") or 0.0)
            action = "delayed" if diff > 0 else "immediate"
            why = (f"{best.get('cell')} delay={best.get('delay_s')}s diff={diff:+.3f}bp "
                   f"n={best.get('n')} (paired, this broker's tape)")
        elif mine:
            best = max(mine, key=lambda r: abs(float(r.get("diff_bps") or 0.0)))
            action, why = "staged", ("measured cells exist but none excludes zero: split the "
                                     "order rather than pick a side the tape does not support")
        else:
            best, action, why = {}, UNMEASURED, f"no measured timing cell for {symbol}"
        out.append({"symbol": symbol, "action": action, "why": why, "advisory": True,
                    "delay_s": best.get("delay_s"), "diff_bps": best.get("diff_bps"),
                    "n": best.get("n")})
    return out


def _atlas_history() -> list[dict[str, Any]]:
    """Prior events with a MEASURED reaction, from the event-response atlas's published cells."""
    doc = _read_json(ATLAS)
    if not isinstance(doc, dict) or not isinstance(doc.get("cells"), list):
        return []
    at = str(doc.get("at") or UNMEASURED)
    out: list[dict[str, Any]] = []
    for cell in doc["cells"][:400]:
        if not isinstance(cell, dict):
            continue
        out.append({"event_id": str(cell.get("cell") or ""), "kind": str(cell.get("kind") or ""),
                    "at": at, "entities": (), "title": str(cell.get("cell") or ""),
                    "reaction": {"symbol": cell.get("symbol"), "horizon": cell.get("horizon"),
                                 "mean_bp": cell.get("mean_bp"), "n": cell.get("n"),
                                 "t": cell.get("t"), "hit_rate": cell.get("hit_rate")}})
    return out


def _positioning(symbols: Sequence[str]) -> dict[str, Any]:
    doc = _read_json(COT)
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "why": f"{COT} absent or unreadable", "symbols": {}}
    found = {s: doc[s] for s in symbols if s in doc}
    return {"status": "measured" if found else UNMEASURED, "symbols": found,
            "why": "" if found else "COT carries none of the affected symbols"}


def deep_lane(guess: onto.EventGuess, event: Mapping[str, Any], graph: onto.EntityGraph,
              history: Sequence[Mapping[str, Any]], notes: list[str]) -> dict[str, Any]:
    """Causal interpretation, analogues, transmission, positioning, macro and a scenario tree.

    Everything here is INTERPRETATION over measured inputs, and every part of it says which. The
    scenario probabilities are DECLARED priors per kind tilted by the source confidence; they are
    published with that word on them so nothing downstream can read them as a forecast the desk
    measured.
    """
    kind = guess.kind
    spec = onto.ONTOLOGY.get(kind)
    ents = list(guess.entities)
    affected = [a.asset for a in onto.affected({"kind": kind, "entities": ents}, graph)]
    hops1 = sorted({n for e in ents for n in graph.neighbours(e)})
    hops2 = sorted({n for e in hops1 for n in graph.neighbours(e)} - set(ents) - set(hops1))
    secondary = sorted({a for e in hops1 for a in graph.assets_for(e)} - set(affected))
    tertiary = sorted({a for e in hops2 for a in graph.assets_for(e)}
                      - set(affected) - set(secondary))
    macro = _read_json(MACRO_STATE)
    prior = spec.scenario_prior if spec is not None else (0.0, 1.0, 0.0)
    tilt = 0.5 + 0.5 * float(guess.confidence)
    raw = (prior[0] * tilt, prior[1], prior[2] * (2.0 - tilt))
    total = sum(raw) or 1.0
    scenarios = [
        {"name": "escalates", "p": round(raw[0] / total, 4),
         "drivers": ["further items of the same kind on the same entities raise the posterior"],
         "affected": affected[:8]},
        {"name": "holds", "p": round(raw[1] / total, 4),
         "drivers": ["no follow-up: the state relaxes towards rest on the "
                     f"{HALF_LIFE_H:g}h half-life"], "affected": affected[:8]},
        {"name": "de-escalates", "p": round(raw[2] / total, 4),
         "drivers": ["a ceasefire/restart/settlement item of the mirror kind arrives"],
         "affected": affected[:8]},
    ]
    mechanisms = [
        {"mechanism": f"{kind} on {'/'.join(ents) or 'an unnamed entity'} transmits to "
                      f"{edge.asset_class} within {edge.horizon}; the sign is decided by "
                      f"{', '.join(edge.state_vars)}",
         "asset_class": edge.asset_class, "horizon": edge.horizon,
         "state_vars": list(edge.state_vars), "note": edge.note}
        for edge in (spec.edges if spec is not None else ())]
    if not mechanisms:
        notes.append(f"the deep lane fired on kind {kind!r}, which declares no transmission edge")
    return {
        "kind": kind, "entities": ents,
        "causal": mechanisms,
        "analogues": [asdict(a) for a in onto.analogues(dict(event), history)],
        "cross_country": {"one_hop": hops1, "two_hop": hops2,
                          "actors": list(graph.actors[:12])},
        "positioning": _positioning(affected),
        "macro": ({"status": "measured", "states": macro.get("states"),
                   "updated": macro.get("updated")} if isinstance(macro, dict)
                  else {"status": UNMEASURED, "why": f"{MACRO_STATE} absent"}),
        "scenarios": scenarios,
        "scenario_basis": "DECLARED per-kind priors tilted by source confidence, not a forecast",
        "secondary_effects": secondary[:16], "tertiary_effects": tertiary[:16],
        "rule": "interpretation over measured inputs; it mints no cell and trades nothing",
    }


# ============================================================================= recording
def _registry() -> Any | None:
    try:
        from libs.moat import registry as reg
    except ImportError:                                  # pragma: no cover - import-context only
        return None
    return reg


def record_deep(event: Mapping[str, Any], deep: Mapping[str, Any],
                notes: list[str]) -> dict[str, Any]:
    """One `event_deep` memory per event and one DISCOVERY per newly implied mechanism.

    Keyed by `event_id`, so a follow-up headline REFRESHES the event's row rather than writing a
    second one, and the discovery content hash collapses a mechanism the registry already holds.
    """
    reg = _registry()
    if reg is None:
        notes.append("libs.moat.registry not importable: the deep lane recorded nothing")
        return {"memory": None, "discoveries": 0, "status": "registry unavailable"}
    eid = str(event.get("event_id") or "")
    # PROVENANCE FOR THE MINING REGISTRY (2026-10-06): the registry credits a donated row to the
    # source id its producer stamps, and only when that registry row registers this organ. GDELT
    # grounds are named by their alt_proxies registry ids, never the vault's short name.
    src = str(event.get("source_id") or SOURCE)
    prov_id = GDELT_REGISTRY_ID.get(src, src)
    provenance = {"organ": SOURCE, "use": "deep_lane", "source_id": prov_id}
    try:
        memory_id = reg.remember(
            "news", f"{event.get('kind')} on {', '.join(deep.get('entities') or []) or 'unnamed'}: "
                    f"{str(event.get('title') or '')[:300]}",
            kind="event_deep", memory_key=f"event_deep:{eid}", result="pending",
            payload=dict(deep), evidence={"event": dict(event)})
        recorded = 0
        for mech in deep.get("causal") or []:
            _did, created = reg.record_discovery(
                source_id=str(event.get("source_id") or SOURCE), source_type="news_event_stream",
                mechanism=str(mech.get("mechanism") or ""), origin="MOAT", generator=SOURCE,
                assets=[mech.get("asset_class")], horizons=[mech.get("horizon")],
                information="news event stream", economic_rationale=str(mech.get("note") or ""),
                confidence=float(event.get("confidence") or 0.0),
                novelty=float(event.get("novelty") or 0.0),
                falsifier="the event atlas measures no reaction of this kind on this class",
                payload={"event_id": eid, "state_vars": mech.get("state_vars"),
                         "provenance": provenance, "origin_source_id": prov_id})
            recorded += int(bool(created))
        return {"memory": memory_id, "discoveries": recorded, "status": "recorded"}
    except Exception as exc:                             # pragma: no cover - registry write path
        notes.append(f"deep-lane record refused: {type(exc).__name__}: {exc}")
        return {"memory": None, "discoveries": 0, "status": f"refused: {type(exc).__name__}"}


# ============================================================================= the pass
def _calendar_expectation(item: Item, kind: str) -> dict[str, Any]:
    """What the calendar said to expect, where it carries anything at all for this kind."""
    doc = _read_json(CALENDAR)
    rows = doc.get("events") if isinstance(doc, dict) else doc
    scheduled = bool(onto.ONTOLOGY.get(kind, onto.ONTOLOGY["other"]).scheduled)
    if not isinstance(rows, list):
        return {"scheduled": scheduled}
    low = f"{item.title} {item.text}".lower()
    for row in rows[:2000]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("kind") or "").lower()
        if name and len(name) > 3 and name in low:
            return {"scheduled": True, "consensus": row.get("consensus"),
                    "actual": row.get("actual"), "sigma": row.get("sigma"),
                    "calendar_row": name}
    return {"scheduled": scheduled}


#: The anomaly baseline for machine-coded groups: an EWMA of article volume per (kind, country)
#: slot group. Below WARMUP observations the surprise is the declared prior, named UNMEASURED.
ANOMALY_ALPHA = 0.05
ANOMALY_WARMUP = 20


def anomaly_surprise(baseline: dict[str, Any], key: str, volume: float) -> onto.Surprise:
    """How unusual this slot's coverage of (kind, country) is, against its own history.

    A war that has been running for a year produces fighting events in every slot; an ordinary
    slot of it is not news, a slot with five times its usual coverage is. The baseline is updated
    AFTER the score is read, so a slot never surprises itself.
    """
    b = baseline.setdefault(key, {"n": 0, "mean": 0.0, "var": 0.0})
    n, mean, var = int(b["n"]), float(b["mean"]), float(b["var"])
    if n < ANOMALY_WARMUP:
        out = onto.Surprise(onto.SCHEDULED_PRIOR,
                            f"coverage anomaly UNMEASURED: {n}/{ANOMALY_WARMUP} slots of "
                            f"baseline, declared prior {onto.SCHEDULED_PRIOR}", False)
    else:
        sd = math.sqrt(max(var, 1e-9))
        z = (float(volume) - mean) / sd
        out = onto.Surprise(round(min(1.0, max(0.02, z / onto.SURPRISE_Z_CAP)), 4),
                            f"article volume z {z:.2f} against the (kind, country) EWMA "
                            f"({n} slots)", True, z)
    delta = float(volume) - mean
    mean += ANOMALY_ALPHA * delta if n else delta
    var = (1.0 - ANOMALY_ALPHA) * (var + ANOMALY_ALPHA * delta * delta) if n else 0.0
    b.update({"n": n + 1, "mean": mean, "var": var})
    return out


def _state_fingerprint(state: Mapping[str, Any]) -> str:
    comps = state.get("components") or {}
    blob = json.dumps({k: [round(float(v.get("value", 0.0)), 6), round(float(v.get("sd", 0.0)), 6)]
                       for k, v in sorted(comps.items())}, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _conversion() -> dict[str, Any]:
    """What the deep lane's discoveries became, read from the canonical registry."""
    reg = _registry()
    path = getattr(reg, "_PATH", None) if reg is not None else None
    if reg is None or path is None or not Path(path).exists():
        return {"status": UNMEASURED, "why": "alpha_registry.sqlite absent on this host"}
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            rows = con.execute(
                "SELECT state, COUNT(*), COALESCE(SUM(queued_cells),0), "
                "COALESCE(SUM(tested_cells),0) FROM discoveries WHERE generator=? "
                "GROUP BY state", (SOURCE,)).fetchall()
        finally:
            con.close()
    except Exception as exc:                             # pragma: no cover - box registry only
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    by_state = {str(r[0]): int(r[1]) for r in rows}
    return {"status": "measured", "discoveries_by_state": by_state,
            "discoveries": sum(by_state.values()),
            "queued_cells": sum(int(r[2]) for r in rows),
            "tested_cells": sum(int(r[3]) for r in rows),
            "survivors": UNMEASURED,
            "survivors_why": ("the registry's discovery rows carry no survivor flag; survivor "
                              "yield is read from the gauntlet's own verdict ledger")}


def _ledger() -> Any:
    from libs.research import sensor_contract as sc
    return sc.SensorLedger(SENSOR_ROOT)


def _observation(item: Item, *, kind_label: str, story_id: str, event_id: str | None,
                 novelty: float | None, confidence: float | None, affected_classes: Sequence[str],
                 copy_of: str = "", fp: str = "") -> Any:
    from libs.research import sensor_contract as sc
    know = item.knowable_at if item.knowable_at != UNMEASURED else None
    return sc.make(
        sensor_id=f"news:{item.origin or 'unknown'}", source_id=item.source_id,
        dataset_id=item.origin, metric="document", kind="document", sensor_class="news",
        entity=(item.entities[0] if item.entities else ""),
        geography=item.geography or ",".join(item.entities[:3]),
        asset_domain=",".join(sorted(set(affected_classes))[:4]),
        text=item.title[:400] or item.text[:400], language=item.language or UNMEASURED,
        source_publication_time=know, knowable_at=know,
        knowable_basis="printed_stamp" if know else UNMEASURED, received_at=item.seen_at,
        parse_complete_at=_now(), source_confidence=confidence,
        commercial_rights=("GDELT open data, citation" if item.origin.startswith("gdelt")
                           else UNMEASURED),
        licence=("GDELT unrestricted use with citation" if item.origin.startswith("gdelt")
                 else UNMEASURED),
        provenance_hash=fp or fingerprint(item), raw_pointer=item.url,
        attributes={"story_id": story_id, "event_id": event_id, "novelty": novelty,
                    "event_kind": kind_label, "copy_of": copy_of, "copies": item.copies,
                    "item_id": item.item_id})


def run(*, limit: int = MAX_ITEMS, deep_threshold: float = DEEP_THRESHOLD, dry_run: bool = False,
        now: datetime | None = None, budget_s: float = DEFAULT_BUDGET_S) -> dict[str, Any]:
    """One pass, under the PASS LOCK. The hourly `--once` leg and the MT5-NewsResident loop both
    call this, and two passes at once would read the same cursor, process the same items twice
    and race on the cursor, the owed file and the ledger. A pass that cannot take the lock does
    nothing and says so (status LOCKED); the holder's pass covers the same items."""
    if dry_run:
        return _run_pass(limit=limit, deep_threshold=deep_threshold, dry_run=True, now=now,
                         budget_s=budget_s)
    lock = _claim_lock(PASS_LOCK)
    if lock is None:
        when = now or _now()
        return {"at": _iso(when), "status": "LOCKED", "rule": RULE,
                "why": f"another pass holds {PASS_LOCK}; this one did nothing",
                "items_seen": 0, "items_new": 0, "items_processed": 0, "items_spilled": 0,
                "items_owed_from_last_pass": 0, "syndicated_copies": 0, "events": [],
                "deep_events": 0, "resolve_requests": [], "unmeasured": [],
                "world_state_delta": {}, "written": {"status": "locked: nothing written"}}
    try:
        return _run_pass(limit=limit, deep_threshold=deep_threshold, dry_run=False, now=now,
                         budget_s=budget_s)
    finally:
        _release_lock(lock)


def _run_pass(*, limit: int, deep_threshold: float, dry_run: bool, now: datetime | None,
              budget_s: float) -> dict[str, Any]:
    """One pass of the fast lane over every new item, and the deep lane over what earns it."""
    when = now or _now()
    t0 = time.monotonic()
    notes: list[str] = []
    atlas_doc = _read_json(ACTOR_ATLAS)
    actor_rows = atlas_doc.get("rows") if isinstance(atlas_doc, dict) else None
    graph = onto.seed_entity_graph(_read_json(UNIVERSE) or {},
                                   actor_rows if isinstance(actor_rows, list) else None)
    if not graph.universe:
        notes.append(f"{UNIVERSE} unreadable: affected assets resolve to `class:` selectors only")
    log = _tail_rows(EVENT_LOG)
    cur = load_cursor()
    _prune_cursor(cur, when)
    when_s = when.timestamp()
    seen_items = set(cur["seen"]) | {str(r.get("item_id")) for r in log if r.get("item_id")}
    cutoff = when - timedelta(hours=RECENT_HOURS)
    recent = [r for r in log if (_parse_time(r.get("at")) or cutoff) >= cutoff]
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for r in recent:
        by_kind.setdefault(str(r.get("kind") or "other"), []).append(r)
    census: dict[str, Any] = {}
    owed = [] if dry_run else _unspill()
    if len(owed) >= OWED_GATE:
        notes.append(f"{len(owed)} owed items >= {OWED_GATE}: this pass works the owed set and "
                     f"reads no ground (their cursors stay put, nothing is skipped)")
        census["owed_gate"] = {"owed": len(owed), "gate": OWED_GATE}
        items = list(owed)
    else:
        items = owed + collect_items(limit, notes, cursor=cur, census=census)
    fresh: list[Item] = []
    for i in items:
        if i.item_id not in seen_items:
            seen_items.add(i.item_id)
            fresh.append(i)
    state = load_state(when)
    history = _atlas_history()

    published: list[dict[str, Any]] = []
    log_rows: list[dict[str, Any]] = []
    observations: list[Any] = []
    deltas: dict[str, dict[str, float]] = {}
    requests: list[dict[str, Any]] = []
    affected_all: list[str] = []
    spilled: list[Item] = []
    copies = discoveries = 0
    for idx, item in enumerate(fresh):
        if budget_s and budget_s > 0 and time.monotonic() - t0 > budget_s:
            spilled = fresh[idx:]
            break
        cur["seen"][item.item_id] = when_s
        fp = fingerprint(item)
        prior_fp = cur["fps"].get(fp)
        if prior_fp is not None and not item.preset_kind:
            # A SYNDICATED COPY: counted as an observation, never as independent evidence.
            prior_fp[2] = int(prior_fp[2]) + 1
            copies += 1
            observations.append(_observation(
                item, kind_label="copy", story_id=str(prior_fp[3]), event_id=None, novelty=0.0,
                confidence=None, affected_classes=(), copy_of=str(prior_fp[1]), fp=fp))
            continue
        body = f"{item.title}. {item.text}"
        if item.preset_kind:
            lang, concepts = item.language, ()
            guess = onto.EventGuess(kind=item.preset_kind, entities=item.entities,
                                    confidence=0.6, matched=("cameo",),
                                    languages=(item.language,) if item.language else (),
                                    rule="machine-coded by GDELT's CAMEO coder")
        else:
            lang, concepts = _understand(body)
            guess = onto.classify(body, concepts)
        same_kind = by_kind.get(guess.kind, [])[-RECENT_PER_KIND:]
        # A FOLLOW-UP JOINS THE RUNNING STORY. Keying on the exact entity set would make
        # "Israel and Iran" and "Iran" two events, and one story would walk the state twice.
        eid = onto.resolve_event_id(guess.kind, guess.entities, same_kind)
        row = {"kind": guess.kind, "entities": list(guess.entities), "claim": body[:600],
               "event_id": eid, "title": item.title}
        nov = onto.novelty_of(row, same_kind)
        if item.preset_kind:
            sur = anomaly_surprise(cur["baseline"], item.anomaly_key, item.volume)
        else:
            exp = _calendar_expectation(item, guess.kind)
            sur = onto.surprise_of(row, exp)
        tier = "aggregator" if item.preset_kind else source_tier(item.source_id, item.url)
        corroborations = item.corroborations + sum(
            1 for r in same_kind if str(r.get("event_id")) == eid
            and str(r.get("source_id")) != item.source_id)
        confidence = onto.source_confidence(tier, corroborations=corroborations)
        affected = onto.affected(row, graph)
        affected_all.extend(a.asset for a in affected)
        weight = confidence * nov.score * sur.score * WEIGHT_SCALE
        delta = ({} if guess.kind == "other"
                 else fast_update(state, guess.kind, weight, eid, when))
        for name, moved in delta.items():
            prior_cell = deltas.setdefault(name, dict(moved))
            prior_cell["after"] = moved["after"]
            prior_cell["delta"] = round(moved["after"] - float(prior_cell["before"]), 6)
            prior_cell["sd_after"] = moved["sd_after"]
        deep_score = nov.score * sur.score
        wants_deep = (deep_score >= deep_threshold and confidence >= DEEP_CONFIDENCE
                      and guess.kind != "other")
        event_row = {
            "id": eid, "item_id": item.item_id, "kind": guess.kind,
            "entities": list(guess.entities), "confidence": round(confidence, 4),
            "source_tier": tier, "corroborations": corroborations,
            "novelty": nov.score, "novelty_basis": nov.basis,
            "surprise": sur.score, "surprise_basis": sur.basis,
            "surprise_measured": sur.measured,
            "affected": [{"asset": a.asset, "horizon": a.horizon,
                          "state_vars": list(a.state_vars)} for a in affected],
            "fast_update": delta, "weight": round(weight, 5), "deep": bool(wants_deep),
            "language": lang or item.language or UNMEASURED, "source_id": item.source_id,
            "url": item.url, "title": item.title, "seen_at": item.seen_at,
            "knowable_at": item.knowable_at, "matched": list(guess.matched),
            "origin": item.origin, "fingerprint": fp, "copies": item.copies,
        }
        if wants_deep:
            deep = deep_lane(guess, {**event_row, "text": body}, graph, history, notes)
            event_row["deep_detail"] = deep
            event_row["recorded"] = ({"status": "dry run: nothing recorded"} if dry_run
                                     else record_deep(event_row, deep, notes))
            discoveries += int((event_row["recorded"] or {}).get("discoveries") or 0)
        if any(abs(float(d["delta"])) >= RESOLVE_DELTA for d in delta.values()) or wants_deep:
            requests.append({
                "at": _iso(when), "reason": f"{guess.kind} ({tier}, novelty {nov.score:.2f}, "
                                            f"surprise {sur.score:.2f})",
                "event_id": eid,
                "affected": [a.asset for a in affected],
                "world_state_delta": {k: v["delta"] for k, v in delta.items()},
                "knowable_at": item.knowable_at, "received_at": item.seen_at,
                "rule": "a REQUEST, not an instruction: the allocator may consume it and nothing "
                        "here sizes, caps or vetoes anything"})
        obs = _observation(item, kind_label=guess.kind, story_id=eid,
                           event_id=f"{eid}:{fp[:10]}", novelty=nov.score,
                           confidence=confidence,
                           affected_classes=[str(a.asset).split(":", 1)[0] for a in affected],
                           fp=fp)
        observations.append(obs)
        event_row["observation_id"] = obs.observation_id
        published.append(event_row)
        log_row = dict(event_row)
        log_row.pop("deep_detail", None)
        log_row["at"] = _iso(when)
        log_rows.append(log_row)
        fresh_row = {"at": _iso(when), "event_id": eid, "kind": guess.kind,
                     "entities": list(guess.entities), "claim": body[:600],
                     "source_id": item.source_id}
        recent.append(fresh_row)
        by_kind.setdefault(guess.kind, []).append(fresh_row)
        cur["fps"][fp] = [when_s, obs.observation_id, 0, eid]

    state["at"] = _iso(when)
    state["events_seen"] = int(state.get("events_seen", 0)) + len(published)
    shocks = shock_model([e["kind"] for e in published])
    state["shock_model"] = shocks
    liquidity = float(state["components"]["liquidity_shock"]["value"])
    fingerprint_now = _state_fingerprint(state)
    day = when.date().isoformat()
    tallies = cur["day"].setdefault(day, {"items": 0, "copies": 0, "events": 0, "deep": 0,
                                          "discoveries": 0, "requests": 0, "spilled": 0})
    for k, v in (("items", len(fresh) - len(spilled)), ("copies", copies),
                 ("events", len(published)), ("deep", sum(1 for e in published if e["deep"])),
                 ("discoveries", discoveries), ("requests", len(requests)),
                 ("spilled", len(spilled))):
        tallies[k] = int(tallies.get(k, 0)) + int(v)
    cur["day"] = {d: v for d, v in cur["day"].items() if d >= (when - timedelta(days=14))
                  .date().isoformat()}
    payload = {
        "at": _iso(when), "rule": RULE, "items_seen": len(items), "items_new": len(fresh),
        "items_processed": len(fresh) - len(spilled), "items_spilled": len(spilled),
        "items_owed_from_last_pass": len(owed), "syndicated_copies": copies,
        "budget_s": budget_s, "wall_s": round(time.monotonic() - t0, 3),
        "grounds": census,
        "events": published, "world_state_delta": deltas,
        "world_state": {k: {"value": round(float(v["value"]), 6),
                            "sd": round(float(v["sd"]), 6), "n_events": v["n_events"]}
                        for k, v in state["components"].items()},
        "world_state_fingerprint": fingerprint_now,
        "resolve_requests": requests, "shock_model": shocks,
        "execution_recommendations": execution_recommendations(affected_all, liquidity, notes),
        "liquidity_model": liquidity_model(affected_all, notes),
        "deep_threshold": deep_threshold, "deep_events": sum(1 for e in published if e["deep"]),
        "inputs": {str(p): ("present" if p.exists() else "absent")
                   for p in (MOAT_NORMALIZED, NEWS_CAPTURES, INTEL, UNIVERSE, ATLAS, EXEC_ALPHA,
                             COT, MACRO_STATE, CALENDAR, *(v for _g, v in GDELT_VAULTS))},
        "unmeasured": notes,
        "wiring": ("hourly leg `news_event_stream` (macro department resident) plus the 60 s "
                   "resident task MT5-NewsResident (desks/mt5/scripts/"
                   "install_news_resident_task.ps1); intake is cursor-driven with no item cap"),
    }
    if dry_run:
        payload["written"] = {"world_state": None, "resolve_request": None, "event_log": 0,
                              "report": None, "status": "dry run: nothing written"}
        return payload
    _atomic_json(WORLD_STATE, state)
    appended = _append(EVENT_LOG, log_rows)
    if requests:
        cur["seq"] = int(cur.get("seq", 0)) + 1
        asked_ids = {r["event_id"] for r in requests}
        # The sensor-ledger ids the allocator's answer is stamped against (`allocator_at`), so
        # receipt -> allocation is measured per observation, not per pass.
        envelope = {"at": _iso(when), "seq": cur["seq"], "world_state_fingerprint": fingerprint_now,
                    "requests": requests, "rule": requests[0]["rule"],
                    "observation_ids": [e["observation_id"] for e in published
                                        if e["id"] in asked_ids]}
        _append(RESOLVE_QUEUE, [envelope])
        _atomic_json(RESOLVE_REQUEST, envelope)
    ledger_census: dict[str, Any] = {}
    try:
        led = _ledger()
        ledger_census = led.append(observations, now=when)
        if requests:
            asked = {r["event_id"] for r in requests}
            led.stamp_downstream([e["observation_id"] for e in published if e["id"] in asked],
                                 "decision_available_at", _now(), SOURCE,
                                 {"seq": cur["seq"], "fingerprint": fingerprint_now})
        intake = _intake_report(led, when, payload, ledger_census, tallies)
    except Exception as exc:                             # pragma: no cover - ledger guard
        notes.append(f"sensor ledger refused: {type(exc).__name__}: {str(exc)[:160]}")
        intake = None
    # THE OWED FILE IS WRITTEN BEFORE THE CURSOR (audit #204). The cursor marks the grounds read
    # and the items seen; written first, a crash before the owed file landed lost every spilled
    # item for good (seen, past the offset, and absent from the old owed set). In this order a
    # crash between the two re-reads the grounds from the old cursor: a duplicate, never a loss.
    _settle_pending(spilled)
    _atomic_json(CURSOR, cur)
    payload["sensor_ledger"] = ledger_census
    payload["intake"] = intake
    _atomic_json(REPORT, payload)
    payload["written"] = {"world_state": str(WORLD_STATE),
                          "resolve_request": str(RESOLVE_REQUEST) if requests else None,
                          "event_log": appended, "report": str(REPORT),
                          "intake": str(INTAKE_REPORT), "status": "written"}
    return payload


#: The meter's view of today's shard, kept across resident passes: (shard, offset, compact rows).
#: Each pass reads only the bytes appended since the last one instead of the whole day.
_METER: dict[str, Any] = {}
_METER_FIELDS = ("kind", "provenance_hash", "observation_id", "language", "geography",
                 "asset_domain", "sensor_class", "source_id", "source_publication_time",
                 "publication_time", "knowable_at", "received_at", "parse_complete_at")
_METER_ATTRS = ("copies", "story_id", "event_id", "novelty", "event_kind")


def _day_rows(led: Any, day: str) -> list[dict[str, Any]]:
    """Today's ledger rows for the meter, read INCREMENTALLY: a new day or another ledger root
    starts over; otherwise only rows past the saved offset are parsed, projected to the fields
    `intake_metrics` reads, and added to the held list."""
    root = str(getattr(led, "root", ""))
    if _METER.get("day") != day or _METER.get("root") != root:
        _METER.clear()
        _METER.update({"day": day, "root": root, "offset": 0, "rows": []})
    new, off = led.rows_since(day, int(_METER["offset"]))
    for r in new:
        attrs = r.get("attributes") if isinstance(r.get("attributes"), Mapping) else {}
        _METER["rows"].append({**{k: r.get(k) for k in _METER_FIELDS},
                               "attributes": {k: attrs.get(k) for k in _METER_ATTRS}})
    _METER["offset"] = off
    return list(_METER["rows"])


def _intake_report(led: Any, when: datetime, payload: Mapping[str, Any],
                   ledger_census: Mapping[str, Any], tallies: Mapping[str, Any]
                   ) -> dict[str, Any]:
    """The day's MEASURED intake across every sensor that writes the ledger, not only news."""
    from libs.research import sensor_contract as sc
    day = when.date().isoformat()
    metrics = sc.intake_metrics(_day_rows(led, day), led.clock_rows(day))
    doc = {
        "at": _iso(when), "day": day, "schema": "world_sensor_intake/1",
        "rule": ("throughput is a measurement, not a quota: no article target exists; every "
                 "number is over ledger rows that exist and anything without stamps is "
                 "UNMEASURED"),
        "metrics": metrics,
        "news_pass": {k: payload.get(k) for k in ("items_seen", "items_new", "items_processed",
                                                  "items_spilled", "syndicated_copies",
                                                  "wall_s", "budget_s")},
        "news_day": dict(tallies),
        "grounds": payload.get("grounds"),
        "conversion": {
            "information_to_hypothesis": {
                "deep_events": tallies.get("deep", 0),
                "discoveries_recorded": tallies.get("discoveries", 0),
                "per_unique_document": (round(tallies.get("discoveries", 0)
                                              / metrics["unique_documents"], 6)
                                        if isinstance(metrics["unique_documents"], int)
                                        and metrics["unique_documents"] else UNMEASURED)},
            "hypothesis_to_gauntlet": _conversion(),
        },
        "compute": {
            "wall_s_this_pass": payload.get("wall_s"),
            "s_per_useful_observation": (
                round(float(payload.get("wall_s") or 0.0)
                      / max(1, len(payload.get("events") or [])), 6)
                if payload.get("events") else UNMEASURED)},
        "ledger_append": dict(ledger_census),
    }
    _atomic_json(INTAKE_REPORT, doc)
    return doc


def _claim_lock(path: Path | None = None) -> Any:
    """A non-blocking exclusive lock on `path` (default: the resident singleton), or None."""
    target = path or LOCK
    target.parent.mkdir(parents=True, exist_ok=True)
    fh = target.open("a+")
    try:
        if os.name == "nt":                              # pragma: no cover - the trading box
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


class _Skip(Exception):
    """A resident pass that found another pass holding the lock."""


def _release_lock(fh: Any) -> None:
    with suppress(OSError):
        if os.name == "nt":                              # pragma: no cover - the trading box
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    with suppress(OSError):
        fh.close()


def resident(interval_s: float = 60.0, limit: int = MAX_ITEMS,
             max_passes: int | None = None, budget_s: float | None = None) -> int:
    """The loop. One pass every `interval_s`; a failing pass is reported and never fatal."""
    lock = _claim_lock()
    if lock is None:
        print(f"{SOURCE} resident already running: this start is a no-op", flush=True)
        return 0
    passes = 0
    per_pass = budget_s if budget_s is not None else max(10.0, interval_s * 0.8)
    while max_passes is None or passes < max_passes:
        started = time.time()
        try:
            out = run(limit=limit, budget_s=per_pass)
            if out.get("status") == "LOCKED":
                print(f"{SOURCE} at={out['at']} LOCKED: {out['why']}", flush=True)
                raise _Skip
            print(f"{SOURCE} at={out['at']} items={out['items_seen']} new={out['items_new']} "
                  f"processed={out['items_processed']} spilled={out['items_spilled']} "
                  f"copies={out['syndicated_copies']} events={len(out['events'])} "
                  f"deep={out['deep_events']} requests={len(out['resolve_requests'])}",
                  flush=True)
        except _Skip:
            pass
        except Exception as exc:                         # pragma: no cover - resident guard
            print(f"{SOURCE} pass failed: {type(exc).__name__}: {exc}", flush=True)
        passes += 1
        if max_passes is not None and passes >= max_passes:
            break
        time.sleep(max(1.0, interval_s - (time.time() - started)))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass and exit")
    ap.add_argument("--resident", action="store_true", help="loop every --interval-s")
    ap.add_argument("--interval-s", type=float, default=60.0)
    ap.add_argument("--limit", type=int, default=MAX_ITEMS,
                    help="newest items kept per pass; 0 (the default) is unbounded")
    ap.add_argument("--budget-s", type=float, default=None,
                    help=f"wall time a pass may classify before it spills the rest to the next "
                         f"pass (default {DEFAULT_BUDGET_S:g}s; resident: 0.8 x interval)")
    ap.add_argument("--deep-threshold", type=float, default=DEEP_THRESHOLD)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    args = ap.parse_args(argv)
    if args.resident:
        return resident(args.interval_s, args.limit, budget_s=args.budget_s)
    out = run(limit=args.limit, deep_threshold=args.deep_threshold, dry_run=args.dry_run,
              budget_s=DEFAULT_BUDGET_S if args.budget_s is None else args.budget_s)
    if out.get("status") == "LOCKED":
        print(f"{SOURCE} at={out['at']} LOCKED: {out['why']}")
        return 0
    kinds: dict[str, int] = {}
    for event in out["events"]:
        kinds[event["kind"]] = kinds.get(event["kind"], 0) + 1
    print(f"{SOURCE} at={out['at']} items={out['items_seen']} new={out['items_new']} "
          f"processed={out['items_processed']} spilled={out['items_spilled']} "
          f"copies={out['syndicated_copies']}")
    print(f"  kinds        {kinds or 'none'}")
    print(f"  deep         {out['deep_events']} above novelty x surprise "
          f">= {out['deep_threshold']}")
    print("  world state  " + ", ".join(
        f"{k}={v['value']:.3f}+-{v['sd']:.2f}" for k, v in list(out["world_state"].items())[:5]))
    print(f"  requests     {len(out['resolve_requests'])}; shock pairs "
          f"{len(out['shock_model']['pairs'])}")
    print(f"  unmeasured   {len(out['unmeasured'])}; {out['written']['status']}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
