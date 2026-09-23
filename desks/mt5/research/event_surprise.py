"""W21 -- THE EVENT-SURPRISE CLUSTER: actual against consensus, and what the tape did about it.

WHAT WAS MISSING, IN ONE SENTENCE. `event_response_atlas` measures the reaction to an event
HAPPENING; its own rule line says so -- "consensus-based surprise UNMEASURED until the calendar
carries actuals" -- and the calendar does not carry them. Measured on this tree: 1,085 rows in
`forced_flow_calendar.json` and 162 in `macro/event_ledger.jsonl`, of which ZERO carry an
`actual` and ZERO carry a `consensus`. So every macro reaction the desk has ever measured is the
reaction to a scheduled MOMENT, not to NEWS. A payroll print in line with consensus and one three
sigma above it are the same row.

This organ is the other half:

    z = (actual - consensus) / sd(this release's OWN historical surprises)

and then, per instrument, per horizon, per regime, the MEASURED reaction conditioned on the
bucket z falls in. The arithmetic of z is `macro.surprise.z_score` and nothing is reimplemented
here: sigma is the release's own surprise history, thin history returns UNMEASURED with its
count, and a release with fewer than the module's MIN_SURPRISE_N past surprises gets no z at all
rather than one computed against a pooled sigma.

THE SIGN IS MEASURED, NEVER DERIVED FROM z. `macro/surprise.py` is emphatic and it is right: a
hot CPI where real yields do not move and the dollar sells off must not mechanically produce a
short gold. So z is used ONLY to BUCKET the observations (up/down, >=1 sigma or below), and the
number published for each bucket is the observed mean drift in that bucket. "Up surprises are
followed by -4bp on gold at 1h" is an observation about a bucket, not a rule mapping the sign of
z to a side.

TWO RESPONSES, AND THE TRADABLE ONE IS THE ONE THAT IS TESTED. `impact` is the pre-event close to
the event bar's close: the part that happens while the tape is unfillable at a quoted price.
`drift` is the event bar's close to +h: the part a desk that reads the print can actually take.
Cells are judged on DRIFT, impact is published beside it, and a cell whose whole effect is in the
impact bar is therefore visibly untradable rather than silently counted.

THE COLLECTOR, AND ITS POLICY -- STATED HERE BECAUSE IT BINDS.
  * consensus/actual is non-API data and there is NO browser automation in this process. No LLM
    is used anywhere in this file, for anything.
  * EVERY page REGISTERED in `desks/mt5/data/event_consensus_sources.json` that names an address
    and a field map is FETCHED (LAWS 5e, 2026-09-23). `machine_use_allowed`, `access` and the
    licence line are ROUTING AND PROVENANCE LABELS carried on the row as `terms_note`: they say
    what the desk may REDISTRIBUTE, never whether it may read the published numbers. The two
    refusals that remain are not about access at all -- a row with no http(s) url has no address
    to reach, and a row with no declared `fields` map has no shape, and this file never guesses
    a shape.
  * The fetch itself goes through the desk's existing guarded helper,
    `research.asia_collector.collect_one`, which caps the body, does a conditional GET and vaults
    the bytes under their content hash. Nothing here re-implements an HTTP client.
  * NO ACCESS CONTROL IS EVER BYPASSED -- hard-boundary act 2, and it is the only thing in this
    file that still says no. A 401/403 is recorded as exactly that and never worked around. A
    source declaring key or paid access has its OPEN SURFACE fetched with no credential at all;
    no key, header or secret is ever read or printed by this file.
  * NO SHAPE IS GUESSED. A source carries a declared `fields` map (which column/key is the
    release name, the date, the actual, the consensus) and rows are read through that map only.
    A source with no map is NO_FIELD_MAP and contributes nothing.
  * If the guarded helper cannot be imported the collector records UNMEASURED-NO-FETCHER with the
    reason and the organ still runs on whatever actual/consensus pairs the calendar artifacts
    already carry. An absent collector degrades; it never crashes and it never invents a
    consensus.

EVERYTHING ABSENT IS A VERDICT. No consensus anywhere -> `status: UNMEASURED`, the report is
still written, the reason is named, and nothing is donated. A pair whose release has thin history
is counted under `unmeasured.thin_history`, not dropped silently.

    python desks/mt5/research/event_surprise.py [--once] [--budget-s 300] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GROUNDS = DESK / "data" / "event_consensus_sources.json"
STORE = DESK / "data" / "macro" / "consensus_actuals.jsonl"
COLLECTOR_STATE = DESK / "data" / "macro" / "consensus_collector_state.json"
REPORT = DESK / "reports" / "EVENT_SURPRISE.json"

SOURCE = "event_surprise"
FAMILY = "event_reaction"

#: Minutes after the release the reaction is read at. The same four the atlas uses, so a cell
#: here and a cell there are comparable rows rather than two different clocks.
HORIZONS: dict[str, int] = {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}
#: Observations a (kind, symbol, bucket, horizon, regime) cell needs before it is a measurement.
MIN_EVENTS = 12
#: A regime slice is a SECOND cut of the same events; it needs its own floor or every cell
#: spawns four thin ones and the trial count triples for nothing.
MIN_EVENTS_REGIME = 20
ALPHA = 0.05
MAX_PUBLISHED = 400
MAX_DONATIONS = 10
#: Days of history read for the pairs. Macro releases are monthly: 400 days is ~13 prints of a
#: given release, which is the order of MIN_SURPRISE_N and no more.
DAYS = 1200
#: Sources fetched in one pass, and the share of the budget the collector may spend. The rest of
#: the pass is the measurement, which is the part that produces evidence.
#:
#: RAISED FROM 6 TO 16 (2026-09-24). A windowed calendar endpoint answers one bounded window per
#: call, so a registry that covers two years of history is a dozen-odd rows and SIX per pass made
#: the desk wait three hours for a history it could hold in one. The budget share below still
#: bounds the pass in seconds; this bounds only how many of them it may spend, and a cap that
#: makes the desk wait for evidence it can already reach is a brake, not a guard.
MAX_SOURCES_PER_PASS = 16
COLLECT_BUDGET_SHARE = 0.4
#: A source is re-fetched no more often than this. These are monthly and quarterly publications;
#: hammering them hourly is three wasted requests and one rate-limit away from a ban.
DEFAULT_DUE_S = 12 * 3600

RULE = ("z = (actual - consensus) / sd(that release's own historical surprises); the reaction "
        "published per bucket is MEASURED, never derived from the sign of z")
POLICY = ("every registered page that names an address and a field map is fetched (LAWS 5e, "
          "2026-09-23): licence, terms, robots and access labels ride along as `terms_note` and "
          "route redistribution, never discovery; no access control is bypassed, no key is read, "
          "no LLM is used, no shape is guessed")
UNMEASURED = "UNMEASURED"


# --------------------------------------------------------------------------------- plumbing
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _f(value: Any) -> float | None:
    """A finite float, or None. NaN and inf are absences, not measurements."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


#: Multipliers a calendar prints beside a number. A release value is published for a human --
#: "348K", "15.2B", "-0.1%" -- and `float()` reads every one of them as an absence, which turns a
#: measured print into a missing one. Scaling them is READING the published number, not guessing:
#: the suffix is the publisher's own declared unit.
_SCALE: dict[str, float] = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
#: Characters that decorate a printed value and carry no magnitude: currency marks, the thin
#: spaces a calendar renders between number and unit, and the thousands separator. Built from
#: code points on purpose -- a zero-width space and a narrow no-break space are INVISIBLE in a
#: source file, and a character a reader cannot see is a character nobody can check.
_STRIP: str = "".join(chr(c) for c in (
    0x200B, 0x00A0, 0x2009, 0x202F, 0x2007,   # zero-width, nbsp, thin, narrow-nbsp, figure
    0x0024, 0x20AC, 0x00A3, 0x00A5, 0x20A3,   # dollar, euro, pound, yen, franc
    0x20B9, 0x20BD, 0x20A9, 0x002C,           # rupee, rouble, won, thousands separator
))


def _num(value: Any) -> float | None:
    """A published release value as a number, or None -- and None only when there is no number.

    `_f` is the desk's strict float and stays strict: it is used wherever a JSON field is already
    numeric. This is the parser for the OTHER kind of field, the one a calendar prints for a
    reader. A dash is the publisher saying there is no consensus, and it stays an absence.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _f(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text in ("-", "--", "n/a", "N/A"):
        return None
    for ch in _STRIP:
        text = text.replace(ch, "")
    text = text.strip()
    mult = 1.0
    if text.endswith("%"):
        text = text[:-1].strip()
    elif text and text[-1].lower() in _SCALE:
        mult = _SCALE[text[-1].lower()]
        text = text[:-1].strip()
    got = _f(text)
    return None if got is None else got * mult


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def _read_rows(path: Path, limit: int = 200_000) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8-sig", "replace").splitlines()[:limit]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            when = (datetime.fromisoformat(text) if fmt is None
                    else datetime.strptime(text, fmt).replace(tzinfo=UTC))
        except ValueError:
            continue
        return when if when.tzinfo else when.replace(tzinfo=UTC)
    return None


def _memory_floor_rows(default: int = 200_000) -> int:
    """Rows held in memory at once, DERIVED from the box, never sized off a machine's claim.

    25% of measured free physical memory at ~2 KB a row, floored at `default` so an unreadable
    counter changes nothing. The trading box and the build box differ by an order of magnitude
    and a constant sized for either is wrong on the other.
    """
    try:
        import psutil  # type: ignore[import-untyped]
    except Exception:                                    # pragma: no cover - optional dependency
        return default
    try:
        free = int(psutil.virtual_memory().available)
    except Exception:                                    # pragma: no cover - counter unreadable
        return default
    return max(default, int(free * 0.25 / 2048))


# --------------------------------------------------------------------------------- collector
def load_grounds() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The registered source table, and the accounting of what it says.

    Never raises: an absent or malformed grounds file is a named absence, and the organ then runs
    on whatever the calendar artifacts already carry.
    """
    doc = _read_json(GROUNDS)
    if not isinstance(doc, dict) or not isinstance(doc.get("sources"), list):
        return [], {"path": str(GROUNDS), "status": "absent",
                    "why": "no registered source table; the collector has no registered ground "
                           "to fetch and fetches nothing"}
    rows = [r for r in doc["sources"] if isinstance(r, dict)]
    allowed = sum(1 for r in rows if admissible(r)[0])
    return rows, {"path": str(GROUNDS), "status": "present", "n": len(rows),
                  "machine_use_allowed": allowed,
                  # NOT an access count any more: a row here lacks an address, lacks a field map,
                  # or is one of the five refused acts (LAWS 5e, 2026-09-23).
                  "refused": len(rows) - allowed,
                  "n_labelled": sum(1 for r in rows if terms_label(r)),
                  "licence_note": str(doc.get("licence_note") or "")[:300]}


#: Access strings that name one of the five refused ACTS rather than a licence. `key` and `paid`
#: are NOT here: their OPEN surface is fetched with no credential, which is reading, not bypassing.
REFUSED_ACCESS: frozenset[str] = frozenset({"private", "mnpi", "confidential", "stolen",
                                            "leaked", "credentialed"})


def admissible(src: dict[str, Any]) -> tuple[bool, str]:
    """IS THIS REGISTERED ROW FETCHED? Yes, unless it has no address, no shape, or is one of the
    five refused acts.

    LAWS 5e (2026-09-23): `machine_use_allowed=false`, `access != "public"` and a restrictive
    licence line used to refuse a row here. Those were DISCOVERY BRAKES THE DESK IMPOSED ON
    ITSELF -- reading a publisher's published numbers is lawful, and the terms bear on
    REDISTRIBUTION, which this organ does not do. They are deleted; `terms_label()` carries the
    same facts onto the row instead.

    What is left is not about access: a row with no http(s) url has nothing to reach for, and a
    row with no declared field map has no shape (and this file never guesses one). `private` /
    MNPI / stolen access strings stay refused -- that is the hard boundary, and no credential is
    ever sent for a `key` or `paid` row either, only its open surface is read.
    """
    access = str(src.get("access") or "").lower()
    if access in REFUSED_ACCESS:
        return False, (f"HARD BOUNDARY: access {access!r} names an authenticated, private or "
                       f"unlawfully-obtained surface; the desk does not break in")
    url = str(src.get("url") or "")
    if not url.lower().startswith(("http://", "https://")):
        return False, "NO_ADDRESS: no http(s) url registered, so there is nothing to reach for"
    if not isinstance(src.get("fields"), dict) or not src["fields"]:
        return False, "NO_FIELD_MAP: no declared field map, and no shape is ever guessed"
    note = terms_label(src)
    return True, f"fetched; field map declared{'; ' + note if note else ''}"


def terms_label(src: dict[str, Any]) -> str:
    """THE ROUTING LABEL a registered row carries -- never a reason to skip it (LAWS 5e).

    Terms, licence, an `access` string other than `public` and a declared
    `machine_use_allowed=false` all land here as free text and travel with the row. They bound
    what may be REDISTRIBUTED; they have never bounded what may be read and tested.
    """
    bits: list[str] = []
    access = str(src.get("access") or "").lower()
    if src.get("machine_use_allowed") is False:
        bits.append("row declares machine_use_allowed=false: mined, redistribution withheld")
    if access and access != "public":
        bits.append(f"access={access!r}: the open surface is read with no credential; the wall "
                    f"is never bypassed")
    lic = str(src.get("licence") or "").strip()
    if lic:
        bits.append(f"licence: {lic[:200]}")
    return "; ".join(bits)


def _fetcher() -> tuple[Any, str]:
    """The desk's guarded HTTP helper, or (None, why). Never a private client of our own."""
    try:
        from research.asia_collector import collect_one
    except Exception as exc:                             # pragma: no cover - import-context only
        return None, f"UNMEASURED-NO-FETCHER: {type(exc).__name__}: {str(exc)[:120]}"
    return collect_one, "research.asia_collector.collect_one (size-capped, conditional GET)"


def _records_from(doc: Any, fields: dict[str, Any], source_id: str) -> list[dict[str, Any]]:
    """Rows through the DECLARED field map only. An unmapped document yields nothing.

    `fields` names four keys -- `release`, `date`, `actual`, `consensus` -- and optionally a
    `path` (a dotted route to the list inside a JSON document) and a constant `release_const`
    for a single-series endpoint. Anything the map does not name is not read.

    `release_keys` IS THE FIFTH, AND IT EXISTS BECAUSE ONE NAME IS NOT AN IDENTITY. A world
    calendar prints "CPI m/m" for the euro area and "CPI m/m" for Britain, and a store that keys
    a release on the title alone pools two countries' surprises into one sigma -- which is not a
    thin history, it is a WRONG one, and it would be invisible. A source may therefore declare an
    ORDERED LIST of keys whose values compose the release identity (`["CurrencyCode",
    "EventName"]` -> "EUR CPI m/m"). Every key is still declared; nothing is guessed.
    """
    node = doc
    for step in str(fields.get("path") or "").split("."):
        if not step:
            continue
        if isinstance(node, dict):
            node = node.get(step)
        else:
            return []
    if isinstance(node, dict):
        node = next((v for v in node.values() if isinstance(v, list)), None)
    if not isinstance(node, list):
        return []
    provides = str(fields.get("provides") or "both").lower()
    need_actual = provides in ("both", "actual")
    need_consensus = provides in ("both", "consensus")
    out: list[dict[str, Any]] = []
    const = fields.get("release_const")
    compose = [str(k) for k in (fields.get("release_keys") or []) if isinstance(k, str)]
    for raw in node:
        if not isinstance(raw, dict):
            continue
        when = _parse_time(raw.get(str(fields.get("date") or "")))
        actual = _num(raw.get(str(fields.get("actual") or ""))) if need_actual else None
        consensus = _num(raw.get(str(fields.get("consensus") or ""))) if need_consensus else None
        if compose:
            release = " ".join(str(raw.get(k) or "").strip() for k in compose).strip()
        else:
            release = str(raw.get(str(fields.get("release") or "")) or const or "").strip()
        if when is None or not release:
            continue
        if (need_actual and actual is None) or (need_consensus and consensus is None):
            continue
        # THE REFERENCE PERIOD IS THE JOIN KEY, AND A MONTH IS THE WRONG GRAIN FOR A WEEKLY
        # RELEASE. `join_sides` keeps ONE pair per (release, period), so a month-grained period
        # silently collapses the four EIA crude prints of a month into one and throws three
        # measured surprises away. A source whose document carries BOTH sides needs no coarse
        # join at all -- the release INSTANT identifies the occurrence exactly -- so it declares
        # `period_grain: "instant"`. Default stays "month": every source written before this
        # keeps the behaviour it had.
        grain = str(fields.get("period_grain") or "month").lower()
        default_period = (f"{when:%Y-%m-%dT%H:%M}" if grain == "instant" else f"{when:%Y-%m}")
        period = str(raw.get(str(fields.get("period") or "")) or "").strip() or default_period
        out.append({"release": release, "at": when.isoformat(timespec="seconds"),
                    "period": period, "actual": actual, "consensus": consensus,
                    "source_id": source_id, "provides": provides,
                    "instruments": _instruments_for(raw, fields),
                    "kind": str(fields.get("kind") or "macro_release")})
    return out


def _instruments_for(raw: dict[str, Any], fields: dict[str, Any]) -> list[str]:
    """The instruments a row's release bears on -- a constant list, or a DECLARED routing map.

    `measure()` only reaches an instrument an event NAMES, so a world calendar registered as one
    source with one constant list would measure every currency's release against the same tape
    and every reaction cell would be noise. The alternative -- one registered source per currency
    -- multiplies the registry by seven for a routing decision that is one lookup. So a source may
    declare `instruments_by`: the KEY whose value routes the row, and the MAP from that value to
    instruments. Both are written in the registry; neither is inferred from the row.
    """
    by = fields.get("instruments_by")
    if isinstance(by, dict) and isinstance(by.get("map"), dict):
        value = str(raw.get(str(by.get("key") or "")) or "").strip()
        got = by["map"].get(value)
        if isinstance(got, list):
            return [str(s) for s in got if isinstance(s, str)]
        return []
    return [str(s) for s in (fields.get("instruments") or []) if isinstance(s, str)]


def join_sides(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Half-rows into pairs on (release, reference period). A half with no partner is NOT a pair.

    THE CONSENSUS AND THE ACTUAL ALMOST NEVER LIVE IN THE SAME PUBLIC DOCUMENT. A statistical
    agency publishes the print; a public forecast survey publishes the expectation; commercial
    calendars sell the two side by side and their terms forbid the machine use that would matter.
    So the desk joins what it may lawfully read, on the release's REFERENCE PERIOD -- the quantity
    both documents are about -- and a half-row waits in the store until its partner is published.
    It is never completed with a guess, a previous value, or a zero.

    A pair is stamped at the LATER of the two halves: that is when the desk could first have held
    both, and a surprise dated to the earlier one would claim knowledge nobody had.
    """
    halves: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        release = str(row.get("release") or "")
        period = str(row.get("period") or "") or str(row.get("at") or "")[:7]
        if not release:
            continue
        if row.get("actual") is not None and row.get("consensus") is not None:
            halves[(release, period)]["both"] = row
        elif row.get("actual") is not None:
            halves[(release, period)].setdefault("actual", row)
        elif row.get("consensus") is not None:
            halves[(release, period)].setdefault("consensus", row)
    out: list[dict[str, Any]] = []
    for (release, period), sides in halves.items():
        if "both" in sides:
            out.append({**sides["both"], "period": period, "joined": "single_document"})
            continue
        a, c = sides.get("actual"), sides.get("consensus")
        if a is None or c is None:
            continue
        at = max(str(a.get("at") or ""), str(c.get("at") or ""))
        out.append({"release": release, "period": period, "at": at,
                    "actual": _f(a.get("actual")), "consensus": _f(c.get("consensus")),
                    "kind": str(a.get("kind") or c.get("kind") or "macro_release"),
                    "instruments": list(a.get("instruments") or c.get("instruments") or []),
                    "source_id": f"{c.get('source_id')}+{a.get('source_id')}",
                    "joined": "consensus_source joined to actual_source on reference period"})
    out.sort(key=lambda r: str(r.get("at") or ""))
    return out


def _collected_doc(rec: dict[str, Any]) -> Any:
    """The parsed document the guarded helper left on disk, or None. Never re-fetches."""
    parse = rec.get("parse")
    if not isinstance(parse, dict) or not parse.get("parsed"):
        return None
    path = Path(str(parse.get("path") or ""))
    if path.suffix == ".json":
        return _read_json(path)
    if path.suffix in (".csv", ".parquet"):
        try:
            import pandas as pd
            frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        except Exception:                                # pragma: no cover - optional dependency
            return None
        return frame.to_dict(orient="records")
    return None


def _due(state: dict[str, Any], src: dict[str, Any], now: datetime) -> bool:
    row = state.get(str(src.get("id") or ""))
    if not isinstance(row, dict):
        return True
    last = _parse_time(row.get("last_fetch_utc"))
    if last is None:
        return True
    every = _f(src.get("refetch_s")) or float(DEFAULT_DUE_S)
    return (now - last).total_seconds() >= every


def collect(*, budget_s: float, now: datetime, fetch: Any = None,
            max_sources: int = MAX_SOURCES_PER_PASS) -> dict[str, Any]:
    """One guarded pass over the registered grounds. Never raises, never bypasses anything."""
    started = time.monotonic()
    sources, grounds_status = load_grounds()
    fetcher, how = (fetch, "injected fetcher") if fetch is not None else _fetcher()
    out: dict[str, Any] = {"grounds": grounds_status, "fetcher": how, "policy": POLICY,
                           "attempted": 0, "rows": [], "sources": []}
    if fetcher is None:
        out["status"] = UNMEASURED
        out["why"] = how
        return out
    state = _read_json(COLLECTOR_STATE)
    state = state if isinstance(state, dict) else {}
    rows: list[dict[str, Any]] = []
    for src in sources:
        sid = str(src.get("id") or "")
        ok, why = admissible(src)
        if not ok:
            # NOT AN ACCESS REFUSAL (LAWS 5e): no address, no field map, or one of the five
            # refused acts. A licence, terms or robots note never lands here any more.
            out["sources"].append({"id": sid, "status": "NOT_FETCHABLE", "why": why,
                                   "terms_note": terms_label(src),
                                   "licence": str(src.get("licence") or "")[:160]})
            continue
        if out["attempted"] >= max_sources or time.monotonic() - started > budget_s:
            out["sources"].append({"id": sid, "status": "DEFERRED",
                                   "why": "pass budget or per-pass source cap reached; the next "
                                          "pass picks it up (this is a queue, not a drop)"})
            continue
        if not _due(state, src, now):
            out["sources"].append({"id": sid, "status": "NOT_DUE",
                                   "why": "fetched inside its declared cadence; these are "
                                          "monthly publications and re-asking is rude, not free"})
            continue
        out["attempted"] += 1
        try:
            rec = fetcher(dict(src), timeout=float(src.get("timeout_s") or 25.0),
                          validators=(state.get(sid) or {}).get("validators"))
        except Exception as exc:                         # pragma: no cover - helper is guarded
            out["sources"].append({"id": sid, "status": UNMEASURED,
                                   "why": f"{type(exc).__name__}: {str(exc)[:120]}"})
            continue
        rec = rec if isinstance(rec, dict) else {"status": UNMEASURED, "why": "no verdict"}
        status = str(rec.get("status") or UNMEASURED)
        got = _records_from(_collected_doc(rec), dict(src.get("fields") or {}), sid) \
            if status == "COLLECTED" else []
        rows.extend(got)
        state[sid] = {"last_fetch_utc": now.isoformat(timespec="seconds"),
                      "status": status, "validators": rec.get("validators") or {}}
        out["sources"].append({"id": sid, "status": status, "pairs": len(got),
                               "http": rec.get("http"), "robots": rec.get("robots"),
                               "licence": str(src.get("licence") or "")[:160],
                               "terms_note": terms_label(src),
                               "why": str(rec.get("why") or "")[:220]})
    out["rows"] = rows
    out["state"] = state
    out["status"] = "present" if rows else UNMEASURED
    if not rows:
        out["why"] = ("no registered public ground produced an (actual, consensus) pair this "
                      "pass; the organ runs on the calendar's own pairs, which may be none")
    out["elapsed_s"] = round(time.monotonic() - started, 2)
    return out


def _pair_key(row: dict[str, Any]) -> str:
    return hashlib.sha1(
        f"{row.get('release', '')}|{row.get('period', '')}|{row.get('at', '')}"
        f"|{row.get('provides', '')}|{row.get('source_id', '')}".encode()
    ).hexdigest()[:16]


def merge_store(fresh: list[dict[str, Any]], *, now: datetime) -> tuple[list[dict[str, Any]], int]:
    """The point-in-time store after this pass. First writing of a pair wins; nothing is edited.

    A vintage is a record of what was known when. Overwriting an earlier (actual, consensus) with
    a later revision would silently restate history, which is the one thing a PIT store exists to
    prevent -- a revision arrives as its own row under its own ingested stamp.
    """
    kept = {_pair_key(r): r for r in _read_rows(STORE)[-_memory_floor_rows():]}
    added = 0
    for row in fresh:
        key = _pair_key(row)
        if key in kept:
            continue
        kept[key] = {**row, "pair_key": key,
                     "ingested_utc": now.isoformat(timespec="seconds")}
        added += 1
    return sorted(kept.values(), key=lambda r: str(r.get("at") or "")), added


# --------------------------------------------------------------------------------- the pairs
def _atlas() -> Any:
    """`event_response_atlas`, imported and NEVER edited. None when it cannot be imported."""
    try:
        import event_response_atlas as atlas  # type: ignore[import-not-found]
    except Exception:                                    # pragma: no cover - import-context only
        try:
            from research import event_response_atlas as atlas
        except Exception:
            return None
    return atlas


def calendar_pairs(days: int, now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every calendar event that already carries BOTH an actual and a consensus.

    Read through the atlas's own `load_events`, so the two organs see the same events, the same
    normalisation and the same windows -- and so a pair that appears in the calendar tomorrow is
    picked up here with no edit to either file.
    """
    atlas = _atlas()
    if atlas is None:
        return [], {"status": "absent", "why": "event_response_atlas is not importable here; no "
                                               "calendar pairs read"}
    try:
        events, accounting = atlas.load_events(days, now)
    except Exception as exc:                             # pragma: no cover - atlas is guarded
        return [], {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    out: list[dict[str, Any]] = []
    for ev in events:
        actual, consensus = _f(ev.get("actual")), _f(ev.get("consensus"))
        if actual is None or consensus is None:
            continue
        out.append({"release": str(ev.get("name") or ev.get("kind") or ""),
                    "at": ev["at"].isoformat(timespec="seconds"), "actual": actual,
                    "consensus": consensus, "kind": str(ev.get("kind") or "macro_release"),
                    "instruments": list(ev.get("instruments") or []),
                    "source_id": str(ev.get("source") or "calendar")})
    return out, {"status": "present", "n_events": len(events), "with_pair": len(out),
                 "sources": accounting}


def store_pairs(days: int, now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The collector's own point-in-time store, read back as pairs."""
    rows = _read_rows(STORE)
    if not rows:
        return [], {"status": "absent", "path": str(STORE),
                    "why": "no collected pair has ever been stored; the collector has produced "
                           "nothing yet, which is a state and not a zero"}
    cutoff = now - timedelta(days=int(days))
    live = []
    for row in rows:
        when = _parse_time(row.get("at"))
        if when is None or not (cutoff <= when <= now):
            continue
        live.append({**row, "at": when.isoformat(timespec="seconds"),
                     "actual": _f(row.get("actual")), "consensus": _f(row.get("consensus")),
                     "instruments": list(row.get("instruments") or []),
                     "kind": str(row.get("kind") or "macro_release")})
    out = join_sides(live)
    return out, {"status": "present", "path": str(STORE), "rows": len(rows),
                 "in_window": len(live), "joined_pairs": len(out),
                 "unpaired_halves": max(0, len(live) - sum(
                     1 if p.get("joined") == "single_document" else 2 for p in out))}


def standardize(pairs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """`z` per pair, through `macro.surprise.z_score` and nothing else.

    Each release's sigma is ITS OWN strictly-earlier surprises. The first MIN_SURPRISE_N prints of
    a release therefore carry NO z -- counted under `thin_history`, never computed against a
    pooled sigma, never filled with a zero.
    """
    try:
        from macro.surprise import MIN_SURPRISE_N, z_score
    except Exception as exc:                             # pragma: no cover - import-context only
        return [], {"status": UNMEASURED,
                    "why": f"macro.surprise unavailable: {type(exc).__name__}: {str(exc)[:90]}"}
    by_release: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        by_release[str(pair.get("release") or "")].append(pair)
    out: list[dict[str, Any]] = []
    thin = 0
    for name, rows in by_release.items():
        rows.sort(key=lambda r: str(r.get("at") or ""))
        for i, row in enumerate(rows):
            history = [float(r["actual"]) - float(r["consensus"]) for r in rows[:i]]
            est = z_score(float(row["actual"]), float(row["consensus"]), history, release_id=name)
            z = _f(est.z)
            if z is None:
                thin += 1
                continue
            out.append({**row, "z": round(z, 4), "sigma": _f(est.sigma),
                        "n_history": int(est.n), "surprise": round(
                            float(row["actual"]) - float(row["consensus"]), 8)})
    out.sort(key=lambda r: str(r.get("at") or ""))
    return out, {"status": "present" if out else UNMEASURED, "n_pairs": len(pairs),
                 "n_standardized": len(out), "thin_history": thin,
                 "min_surprise_n": int(MIN_SURPRISE_N), "n_releases": len(by_release),
                 "why": ("" if out else
                         f"{len(pairs)} pair(s) and none with {MIN_SURPRISE_N} prior surprises "
                         f"of the same release: z is UNMEASURED, which is a verdict")}


# ------------------------------------------------------------------------------- the reaction
def bucket_of(z: float) -> str:
    """The four buckets. The BUCKET carries the sign; the measured mean carries the claim."""
    size = "ge1sigma" if abs(z) >= 1.0 else "lt1sigma"
    return f"{'up' if z > 0 else 'dn'}_{size}"


def _chart(symbol: str) -> Any:
    """The finest chart the desk holds, via the atlas. A seam so a test needs no parquet."""
    atlas = _atlas()
    return None if atlas is None else atlas.chart(symbol)


def _bar_time(when: datetime) -> tuple[datetime | None, str]:
    """The event instant in the BARS' own frame. An unconverted stamp is a wrong observation."""
    atlas = _atlas()
    if atlas is None:
        return None, "NO_ATLAS"
    got = atlas.bar_time(when)
    return (got[0], str(got[1])) if isinstance(got, tuple) else (None, "NO_BAR_CLOCK")


def _regimes() -> tuple[list[tuple[float, str]], str]:
    atlas = _atlas()
    if atlas is None:
        return [], "NO_ATLAS"
    try:
        timeline, status = atlas.regime_timeline()
    except Exception:                                    # pragma: no cover - atlas is guarded
        return [], UNMEASURED
    return list(timeline), str(status)


def _regime_at(when: datetime, timeline: list[tuple[float, str]]) -> str:
    if not timeline:
        return "ALL"
    stamp = when.timestamp()
    found = "ALL"
    for at, name in timeline:
        if at <= stamp:
            found = str(name)
        else:
            break
    return found


def _stats(values: list[float], floor: int) -> dict[str, Any] | None:
    array = np.asarray(values, dtype=float)
    if array.size < floor:
        return None
    mean, sd = float(np.mean(array)), float(np.std(array, ddof=1))
    if not math.isfinite(mean) or not math.isfinite(sd) or sd <= 0:
        return None
    return {"n": int(array.size), "mean_bp": round(mean * 1e4, 3),
            "median_bp": round(float(np.median(array)) * 1e4, 3), "sd_bp": round(sd * 1e4, 3),
            "hit_rate": round(float(np.mean(array > 0)), 4),
            "t": round(float(mean / (sd / math.sqrt(array.size))), 3)}


def _bonferroni_t(n_cells: int, alpha: float = ALPHA) -> float:
    atlas = _atlas()
    if atlas is not None:
        try:
            return float(atlas.bonferroni_t(n_cells, alpha))
        except Exception:                                # pragma: no cover - atlas is guarded
            pass
    from statistics import NormalDist
    return float("inf") if n_cells <= 0 else float(NormalDist().inv_cdf(1 - alpha / (2 * n_cells)))


def _cost_bp(symbol: str, close: Any) -> tuple[float, str]:
    atlas = _atlas()
    if atlas is None:
        return 0.0, "NO_ATLAS"
    try:
        surface = atlas.cost_surface()
        frac, why = atlas.cost_fraction(symbol, np.asarray(close, dtype=float), surface)
        return round(float(frac) * 1e4, 3), str(why)
    except Exception:                                    # pragma: no cover - atlas is guarded
        return 0.0, UNMEASURED


def observations(symbol: str, events: list[dict[str, Any]],
                 timeline: list[tuple[float, str]]) -> tuple[list[dict[str, Any]], str]:
    """Per event: the impact bar and the drift at every horizon, in the bars' own frame."""
    got = _chart(symbol)
    if got is None:
        return [], "NO_CHART"
    frame, timeframe, per_bar = got
    try:
        index = frame.index
        close = np.asarray(frame["close"], dtype=float)
    except (KeyError, TypeError, ValueError):
        return [], "UNREADABLE_CHART"
    if close.size < 64 or not np.all(np.isfinite(close)) or not np.all(close > 0):
        return [], "THIN_CHART"
    log_close = np.log(close)
    stamps = np.asarray([t.timestamp() for t in index], dtype=float)
    out: list[dict[str, Any]] = []
    for ev in events:
        raw = _parse_time(ev.get("at"))
        if raw is None:
            continue
        moved, status = _bar_time(raw)
        if moved is None:
            continue
        pos = int(np.searchsorted(stamps, moved.timestamp(), side="right")) - 1
        if pos < 1 or pos >= close.size - 1:
            continue
        row: dict[str, Any] = {
            "at": moved.isoformat(timespec="seconds"), "z": float(ev["z"]),
            "bucket": bucket_of(float(ev["z"])), "kind": str(ev.get("kind") or "macro_release"),
            "release": str(ev.get("release") or ""), "clock": status,
            "regime": _regime_at(moved, timeline),
            "impact": float(log_close[pos] - log_close[pos - 1])}
        for name, minutes in HORIZONS.items():
            step = max(1, round(minutes / max(1, int(per_bar))))
            row[f"drift_{name}"] = (float(log_close[pos + step] - log_close[pos])
                                    if pos + step < close.size else None)
        out.append(row)
    return out, f"{timeframe}/{per_bar}m"


def cells_for(symbol: str, rows: list[dict[str, Any]], cost_bp: float) -> list[dict[str, Any]]:
    """One cell per (kind, bucket, horizon, regime). The regime slice carries its own floor."""
    grouped: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    impacts: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        for horizon in HORIZONS:
            value = _f(row.get(f"drift_{horizon}"))
            if value is None:
                continue
            for regime in ("ALL", str(row.get("regime") or "ALL")):
                key = (str(row["kind"]), str(row["bucket"]), horizon, regime)
                grouped[key].append(value)
                impacts[key].append(float(row["impact"]))
    out: list[dict[str, Any]] = []
    for (kind, bucket, horizon, regime), values in grouped.items():
        floor = MIN_EVENTS if regime == "ALL" else MIN_EVENTS_REGIME
        stats = _stats(values, floor)
        if stats is None:
            continue
        impact = _stats(impacts[(kind, bucket, horizon, regime)], floor)
        out.append({"cell": f"{symbol} {kind} {bucket} {horizon} {regime}", "symbol": symbol,
                    "kind": kind, "bucket": bucket, "horizon": horizon, "regime": regime,
                    "cost_bp": cost_bp, **stats,
                    "impact_mean_bp": (impact or {}).get("mean_bp"),
                    "direction": "with_surprise" if (
                        (stats["mean_bp"] > 0) == bucket.startswith("up")) else "against_surprise",
                    "tradable_share": (round(abs(stats["mean_bp"]) /
                                             (abs(stats["mean_bp"])
                                              + abs(float((impact or {}).get("mean_bp") or 0.0))
                                              + 1e-9), 4))})
    return out


def measure(events: list[dict[str, Any]], *, budget_s: float,
            started: float | None = None) -> dict[str, Any]:
    """Every instrument the events name, measured. A budget stop is reported, never hidden."""
    began = time.monotonic() if started is None else started
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        for symbol in ev.get("instruments") or []:
            by_symbol[str(symbol).upper()].append(ev)
    timeline, regime_status = _regimes()
    cells: list[dict[str, Any]] = []
    charts: dict[str, str] = {}
    stopped = False
    reached = 0
    for symbol in sorted(by_symbol):
        if time.monotonic() - began > budget_s:
            stopped = True
            break
        reached += 1
        rows, status = observations(symbol, by_symbol[symbol], timeline)
        charts[symbol] = status
        if not rows:
            continue
        got = _chart(symbol)
        cost_bp, _why = (_cost_bp(symbol, got[0]["close"]) if got is not None else (0.0, "NONE"))
        cells.extend(cells_for(symbol, rows, cost_bp))
    cells.sort(key=lambda c: -abs(float(c.get("t") or 0.0)))
    threshold = _bonferroni_t(len(cells))
    for cell in cells:
        cell["clears"] = bool(abs(float(cell["t"])) >= threshold
                              and abs(float(cell["mean_bp"])) > float(cell["cost_bp"]))
    return {"cells": cells[:MAX_PUBLISHED], "n_cells": len(cells), "threshold_t": round(
        threshold, 3) if math.isfinite(threshold) else None,
        "symbols_named": len(by_symbol), "symbols_reached": reached, "stopped_on_budget": stopped,
        "charts": charts, "regime_timeline": regime_status,
        "clearing": [c for c in cells if c["clears"] and c["regime"] == "ALL"]}


# --------------------------------------------------------------------------------- donation
def _may_hypothesise(symbol: str) -> bool | None:
    try:
        from research.universe_policy import may_hypothesise
    except Exception:                                    # pragma: no cover - import-context only
        return None
    try:
        return bool(may_hypothesise(symbol))
    except Exception:                                    # pragma: no cover - policy is pure json
        return None


def _registered(family: str) -> bool:
    try:
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    except Exception:                                    # pragma: no cover - import-context only
        return False
    return family in ORTHOGONAL_FAMILIES


def donation_params(horizon: str, mean_bp: float) -> dict[str, Any]:
    """`event_reaction` parameters only. `side` is the MEASURED sign, never the sign of z."""
    hold = max(1, round(HORIZONS[horizon] / 60))
    return {"mode": "drift", "side": 1 if mean_bp > 0 else -1, "hold_bars": hold,
            "ttl_bars": 2 * hold, "cooldown_bars": hold, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}


def donation_rows(clearing: list[dict[str, Any]],
                  limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(candidates, refusals). A single-name equity may be MEASURED above and never leaves here."""
    out: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    if clearing and not _registered(FAMILY):
        return [], [{"cell": c["cell"], "why": f"{FAMILY} is not in ORTHOGONAL_FAMILIES on this "
                                               f"tree; nothing donated"} for c in clearing[:5]]
    seen: set[tuple[str, str, str]] = set()
    for cell in clearing:
        if len(out) >= max(int(limit), 0):
            break
        # ONE CELL PER (symbol, release kind, bucket). The same bucket clearing at four horizons
        # is ONE measured reaction seen at four ranges, and shipping all four spends the
        # family-wise error budget four times for one mechanism -- the same rule
        # `proposer_common.best_per_cell` applies to a sweep's parameter variants. The clearing
        # list arrives sorted by |t|, so the survivor is that bucket's strongest horizon.
        key = (str(cell["symbol"]), str(cell["kind"]), str(cell["bucket"]))
        if key in seen:
            refused.append({"cell": cell["cell"], "symbol": cell["symbol"],
                            "why": "a stronger horizon of this same (symbol, kind, bucket) is "
                                   "already donated; four horizons of one reaction is one "
                                   "mechanism with four tickets"})
            continue
        allowed = _may_hypothesise(cell["symbol"])
        if allowed is not True:
            refused.append({"cell": cell["cell"], "symbol": cell["symbol"],
                            "why": ("the two-lane mandate: this instrument is traded on news, "
                                    "reports and earnings reaction and is never hunted for a "
                                    "statistical hypothesis"
                                    if allowed is False else
                                    "universe policy unreadable here; absence is not permission")})
            continue
        seen.add(key)
        params = donation_params(cell["horizon"], float(cell["mean_bp"]))
        out.append({"source": SOURCE, "kind": "hypothesis", "symbol": cell["symbol"],
                    "symbols": [cell["symbol"]], "family": FAMILY, "params": params, "url": "",
                    "cell": cell["cell"],
                    "title": f"{cell['kind']} {cell['bucket']} reaction on "
                             f"{cell['symbol']} at {cell['horizon']}"[:120],
                    "mechanism": (
                        f"standardized surprise bucket {cell['bucket']} over {cell['n']} "
                        f"{cell['kind']} releases: mean drift {cell['mean_bp']}bp at "
                        f"{cell['horizon']} measured from the event bar's CLOSE (the tradable "
                        f"half; the impact bar carried {cell['impact_mean_bp']}bp), t={cell['t']}"
                        f", hit {cell['hit_rate']}, cost {cell['cost_bp']}bp. The side is the "
                        f"MEASURED sign of that drift, never the sign of z")[:400],
                    "evidence": {k: cell.get(k) for k in
                                 ("n", "t", "mean_bp", "sd_bp", "hit_rate", "impact_mean_bp",
                                  "cost_bp", "bucket", "horizon", "regime", "direction",
                                  "tradable_share")} | {"screen": RULE}})
    return out, refused


def _donate(candidates: list[dict[str, Any]], tests_run: int) -> Any:
    """The seam. One import, one call, so a test can watch what leaves without a live intake."""
    from research.proposer_common import donate
    return donate(SOURCE, candidates, tests_run)


# --------------------------------------------------------------------------------- the organ
def build(*, days: int = DAYS, budget_s: float = 300.0, max_donations: int = MAX_DONATIONS,
          collect_enabled: bool = True, apply: bool = True, now: datetime | None = None,
          fetch: Any = None) -> dict[str, Any]:
    """Measure, and return the payload. Touches disk only through `main`."""
    started = time.monotonic()
    now = now or _now()
    collected = (collect(budget_s=budget_s * COLLECT_BUDGET_SHARE, now=now, fetch=fetch)
                 if collect_enabled else
                 {"status": "skipped", "rows": [], "sources": [], "policy": POLICY,
                  "why": "--no-collect: the measurement ran on the stored and calendar pairs"})
    fresh_rows = collected.get("rows") or []
    stored, added = merge_store([r for r in fresh_rows if isinstance(r, dict)], now=now)
    cal, cal_status = calendar_pairs(days, now)
    kept, store_status = store_pairs(days, now)
    pairs = cal + kept
    events, surprise_status = standardize(pairs)
    reaction = (measure(events, budget_s=max(1.0, budget_s - (time.monotonic() - started)),
                        started=started) if events else
                {"cells": [], "n_cells": 0, "threshold_t": None, "clearing": [],
                 "symbols_named": 0, "symbols_reached": 0, "stopped_on_budget": False,
                 "charts": {}, "regime_timeline": "NOT_REACHED"})
    cands, refusals = donation_rows(list(reaction["clearing"]), max_donations)
    path = _donate(cands, int(reaction["n_cells"] or len(cands))) if (apply and cands) else None
    status = ("present" if reaction["cells"] else UNMEASURED)
    why = ""
    if status == UNMEASURED:
        why = (surprise_status.get("why") or "")
        if not why:
            why = ("no instrument named by a standardized event had a readable chart in the "
                   "bars' own frame; nothing was measured, which is a verdict")
    report = {
        "at": now.isoformat(timespec="seconds"), "source": SOURCE, "status": status, "why": why,
        "rule": RULE, "policy": POLICY, "days": days,
        "elapsed_s": round(time.monotonic() - started, 2),
        "budget_s": budget_s,
        "collector": {k: v for k, v in collected.items() if k not in ("rows", "state")},
        "store": {**store_status, "added_this_pass": added, "rows_after": len(stored)},
        "calendar": cal_status,
        "surprise": surprise_status,
        "n_pairs": len(pairs), "n_events": len(events),
        "by_bucket": {b: sum(1 for e in events if bucket_of(float(e["z"])) == b)
                      for b in ("up_ge1sigma", "up_lt1sigma", "dn_lt1sigma", "dn_ge1sigma")},
        "n_cells": reaction["n_cells"], "threshold_t": reaction["threshold_t"],
        "symbols_named": reaction["symbols_named"], "symbols_reached": reaction["symbols_reached"],
        "stopped_on_budget": reaction["stopped_on_budget"],
        "regime_timeline": reaction["regime_timeline"],
        "cells": reaction["cells"],
        "n_clearing": len(reaction["clearing"]),
        "donated": {"n": len(cands) if path else 0, "path": str(path) if path else None,
                    "cells": [c["cell"] for c in cands],
                    "refused": refusals[:20], "n_refused": len(refusals),
                    "status": ("donated" if path else
                               "nothing cleared, or the donation door refused every row")},
        "unmeasured": {"thin_history": surprise_status.get("thin_history"),
                       "charts": {k: v for k, v in reaction["charts"].items() if v != "NO_CHART"
                                  and not v[0].isdigit()},
                       "rule": "absence is a verdict, never a zero (L1.28a)"},
    }
    return {"report": report, "store": stored, "collector_state": collected.get("state") or {}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the event-surprise cluster: actual vs consensus")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode there is)")
    ap.add_argument("--budget-s", type=float, default=300.0, help="wall-clock budget")
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--max-donations", type=int, default=MAX_DONATIONS)
    ap.add_argument("--no-collect", action="store_true",
                    help="measure on the stored and calendar pairs; fetch nothing")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(argv)
    built = build(days=a.days, budget_s=a.budget_s, max_donations=a.max_donations,
                  collect_enabled=not a.no_collect and not a.dry_run, apply=not a.dry_run)
    rep = built["report"]
    col = rep["collector"]
    print(f"event_surprise at={rep['at']} status={rep['status']} elapsed={rep['elapsed_s']}s")
    print(f"  collector  {col.get('status')} via {col.get('fetcher', 'n/a')}; "
          f"attempted={col.get('attempted', 0)} "
          f"sources={len(col.get('sources') or [])} -> +{rep['store']['added_this_pass']} pair(s)")
    print(f"  pairs      {rep['n_pairs']} (calendar {rep['calendar'].get('with_pair', 0)}, "
          f"store {rep['store'].get('in_window', 0)}); standardized {rep['n_events']}, "
          f"thin history {rep['surprise'].get('thin_history')}")
    print("  buckets    " + "  ".join(f"{k}:{v}" for k, v in rep["by_bucket"].items()))
    top = (rep["cells"] or [{}])[0]
    print(f"  cells      {rep['n_cells']} over {rep['symbols_reached']}/{rep['symbols_named']} "
          f"symbol(s); threshold_t={rep['threshold_t']}")
    print(f"  top        {top.get('cell', 'NONE')} mean={top.get('mean_bp')}bp "
          f"t={top.get('t')} n={top.get('n')}")
    print(f"  clearing   {rep['n_clearing']} -> donated {rep['donated']['n']} "
          f"({rep['donated']['status']}); {rep['donated']['n_refused']} refused")
    print(f"  rule       {RULE}")
    if a.dry_run:
        print(f"  --dry-run: nothing written, nothing donated; would have written {REPORT.name}")
        return 0
    _atomic(REPORT, json.dumps(rep, indent=1, default=str))
    if built["store"]:
        _atomic(STORE, "".join(json.dumps(r, default=str) + "\n" for r in built["store"]))
    if built["collector_state"]:
        _atomic(COLLECTOR_STATE, json.dumps(built["collector_state"], indent=1, default=str))
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
