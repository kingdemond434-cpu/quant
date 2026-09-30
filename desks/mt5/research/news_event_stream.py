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

UNWIRED IS A DEFECT AND IS STATED RATHER THAN HIDDEN (III.16). This ships as a RESIDENT with its
tests and no scheduler leg: `--resident` loops every 60 s, `--once` is one pass, `--dry-run`
measures and writes nothing at all. Registering it on a clock is the next commit, not this one.

    python research/news_event_stream.py --once
    python research/news_event_stream.py --resident --interval-s 60
    python research/news_event_stream.py --once --dry-run
"""
from __future__ import annotations

import argparse
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
MAX_ITEMS = 400            # items read in one pass; the resident catches up across passes
MAX_TEXT = 4000
MAX_EXEC_ROWS = 12


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
    """One collected document or claim, before anything is read off it."""

    item_id: str
    source_id: str
    url: str
    title: str
    text: str
    seen_at: str
    knowable_at: str
    language: str = ""
    origin: str = ""


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


def collect_items(limit: int = MAX_ITEMS, notes: list[str] | None = None) -> list[Item]:
    """The newest collected documents, claims and RSS captures, from every ground that exists.

    Three grounds, each read tolerantly and each REPORTED when absent: the moat collectors'
    normalised store, the desk's own news captures, and the news-like intelligence seats. An
    absent ground is UNMEASURED and named -- never a clean zero (L1.28a).
    """
    out: list[Item] = []
    say = notes if notes is not None else []
    if MOAT_NORMALIZED.exists():
        files = sorted(MOAT_NORMALIZED.rglob("*.json"), key=lambda p: p.stat().st_mtime)[-limit:]
        for path in files:
            doc = _read_json(path)
            if isinstance(doc, dict):
                got = _item(str(doc.get("source_id") or path.parent.name), doc, "moat_normalized")
                if got is not None:
                    out.append(got)
    else:
        say.append(f"{MOAT_NORMALIZED} absent: the moat collectors' normalised store is "
                   f"{UNMEASURED} on this box, so no captured document reached the fast lane")
    if NEWS_CAPTURES.exists():
        for row in _tail_rows(NEWS_CAPTURES, limit):
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
        files = sorted(folder.glob("*.json*"), key=lambda p: p.stat().st_mtime)[-8:]
        for path in files:
            for row in _rows_of(path, limit // 4 or 1):
                got = _item(str(row.get("source") or seat), row, f"intelligence:{seat}")
                if got is not None:
                    out.append(got)
    if not seen_seats:
        say.append(f"none of the {len(NEWS_SEATS)} declared news seats exists under {INTEL}")
    out.sort(key=lambda i: i.seen_at)
    return out[-limit:]


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
                payload={"event_id": eid, "state_vars": mech.get("state_vars")})
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


def run(*, limit: int = MAX_ITEMS, deep_threshold: float = DEEP_THRESHOLD, dry_run: bool = False,
        now: datetime | None = None) -> dict[str, Any]:
    """One pass of the fast lane over every new item, and the deep lane over what earns it."""
    when = now or _now()
    notes: list[str] = []
    atlas_doc = _read_json(ACTOR_ATLAS)
    actor_rows = atlas_doc.get("rows") if isinstance(atlas_doc, dict) else None
    graph = onto.seed_entity_graph(_read_json(UNIVERSE) or {},
                                   actor_rows if isinstance(actor_rows, list) else None)
    if not graph.universe:
        notes.append(f"{UNIVERSE} unreadable: affected assets resolve to `class:` selectors only")
    log = _tail_rows(EVENT_LOG)
    seen_items = {str(r.get("item_id")) for r in log if r.get("item_id")}
    cutoff = when - timedelta(hours=RECENT_HOURS)
    recent = [r for r in log if (_parse_time(r.get("at")) or cutoff) >= cutoff]
    items = collect_items(limit, notes)
    fresh = [i for i in items if i.item_id not in seen_items]
    state = load_state(when)
    history = _atlas_history()

    published: list[dict[str, Any]] = []
    log_rows: list[dict[str, Any]] = []
    deltas: dict[str, dict[str, float]] = {}
    requests: list[dict[str, Any]] = []
    affected_all: list[str] = []
    for item in fresh:
        body = f"{item.title}. {item.text}"
        lang, concepts = _understand(body)
        guess = onto.classify(body, concepts)
        # A FOLLOW-UP JOINS THE RUNNING STORY. Keying on the exact entity set would make
        # "Israel and Iran" and "Iran" two events, and one story would walk the state twice.
        eid = onto.resolve_event_id(guess.kind, guess.entities, recent)
        row = {"kind": guess.kind, "entities": list(guess.entities), "claim": body[:600],
               "event_id": eid, "title": item.title}
        nov = onto.novelty_of(row, recent)
        exp = _calendar_expectation(item, guess.kind)
        sur = onto.surprise_of(row, exp)
        tier = source_tier(item.source_id, item.url)
        corroborations = sum(1 for r in recent if str(r.get("event_id")) == eid
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
        }
        if wants_deep:
            deep = deep_lane(guess, {**event_row, "text": body}, graph, history, notes)
            event_row["deep_detail"] = deep
            event_row["recorded"] = ({"status": "dry run: nothing recorded"} if dry_run
                                     else record_deep(event_row, deep, notes))
        if any(abs(float(d["delta"])) >= RESOLVE_DELTA for d in delta.values()) or wants_deep:
            requests.append({
                "at": _iso(when), "reason": f"{guess.kind} ({tier}, novelty {nov.score:.2f}, "
                                            f"surprise {sur.score:.2f})",
                "event_id": eid,
                "affected": [a.asset for a in affected],
                "world_state_delta": {k: v["delta"] for k, v in delta.items()},
                "rule": "a REQUEST, not an instruction: the allocator may consume it and nothing "
                        "here sizes, caps or vetoes anything"})
        published.append(event_row)
        log_row = dict(event_row)
        log_row.pop("deep_detail", None)
        log_row["at"] = _iso(when)
        log_rows.append(log_row)
        recent.append({"at": _iso(when), "event_id": eid, "kind": guess.kind,
                       "entities": list(guess.entities), "claim": body[:600],
                       "source_id": item.source_id})

    state["at"] = _iso(when)
    state["events_seen"] = int(state.get("events_seen", 0)) + len(published)
    shocks = shock_model([e["kind"] for e in published])
    state["shock_model"] = shocks
    liquidity = float(state["components"]["liquidity_shock"]["value"])
    payload = {
        "at": _iso(when), "rule": RULE, "items_seen": len(items), "items_new": len(fresh),
        "events": published, "world_state_delta": deltas,
        "world_state": {k: {"value": round(float(v["value"]), 6),
                            "sd": round(float(v["sd"]), 6), "n_events": v["n_events"]}
                        for k, v in state["components"].items()},
        "resolve_requests": requests, "shock_model": shocks,
        "execution_recommendations": execution_recommendations(affected_all, liquidity, notes),
        "liquidity_model": liquidity_model(affected_all, notes),
        "deep_threshold": deep_threshold, "deep_events": sum(1 for e in published if e["deep"]),
        "inputs": {str(p): ("present" if p.exists() else "absent")
                   for p in (MOAT_NORMALIZED, NEWS_CAPTURES, INTEL, UNIVERSE, ATLAS, EXEC_ALPHA,
                             COT, MACRO_STATE, CALENDAR)},
        "unmeasured": notes,
        "wiring": "RESIDENT, not yet on a scheduler leg (III.16, stated rather than hidden)",
    }
    if dry_run:
        payload["written"] = {"world_state": None, "resolve_request": None, "event_log": 0,
                              "report": None, "status": "dry run: nothing written"}
        return payload
    _atomic_json(WORLD_STATE, state)
    appended = _append(EVENT_LOG, log_rows)
    if requests:
        _atomic_json(RESOLVE_REQUEST, {"at": _iso(when), "requests": requests,
                                       "rule": requests[0]["rule"]})
    _atomic_json(REPORT, payload)
    payload["written"] = {"world_state": str(WORLD_STATE),
                          "resolve_request": str(RESOLVE_REQUEST) if requests else None,
                          "event_log": appended, "report": str(REPORT), "status": "written"}
    return payload


def resident(interval_s: float = 60.0, limit: int = MAX_ITEMS,
             max_passes: int | None = None) -> int:
    """The loop. One pass every `interval_s`; a failing pass is reported and never fatal."""
    passes = 0
    while max_passes is None or passes < max_passes:
        started = time.time()
        try:
            out = run(limit=limit)
            print(f"{SOURCE} at={out['at']} items={out['items_seen']} new={out['items_new']} "
                  f"events={len(out['events'])} deep={out['deep_events']} "
                  f"requests={len(out['resolve_requests'])}", flush=True)
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
    ap.add_argument("--limit", type=int, default=MAX_ITEMS)
    ap.add_argument("--deep-threshold", type=float, default=DEEP_THRESHOLD)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    args = ap.parse_args(argv)
    if args.resident:
        return resident(args.interval_s, args.limit)
    out = run(limit=args.limit, deep_threshold=args.deep_threshold, dry_run=args.dry_run)
    kinds: dict[str, int] = {}
    for event in out["events"]:
        kinds[event["kind"]] = kinds.get(event["kind"], 0) + 1
    print(f"{SOURCE} at={out['at']} items={out['items_seen']} new={out['items_new']}")
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
