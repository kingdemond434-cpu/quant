"""ANALYST VIEWS AS POINT-IN-TIME EVENTS -- the Alpha Capture substitute's schema, store, tracker
and admission contract.

WHAT THIS IS. Alpha Capture systems (the sell-side "trade idea" feeds a buy-side desk reads) and
ResearchAlum-style scoring both reduce to one object: a broker's DATED view on an instrument, and
what the instrument did AFTER the desk could have read it. The public, no-login surfaces of that
information -- Yahoo's upgrade/downgrade history, SEC 8-K guidance language, eastmoney's research
report list, Naver's research lists and TDnet forecast revisions -- are collected by
`desks/mt5/research/alpha_capture.py`. This module is the part that never touches the network:

    AnalystView         one view, normalised: action, 5-point ratings, targets, conviction
    AnalystViewStore    append-only JSONL, every row stamped by `libs.data.pit` at the one door
    observations()      views -> (target instrument, knowable instant, direction) rows
    track()             cumulative return after each observation at +1/+5/+21 trading days
    placebo_contract()  the admission test: real drift t by source against shifted publication
                        dates, which is what separates information from calendar noise

THE POINT-IN-TIME RULE IS `first_seen_at`, NEVER `published_at`. `published_at` is the vendor's
own stamp and can be backfilled, date-only or wrong by a timezone. `first_seen_at` is the instant
THIS desk's collector first held the row, so every return measured here starts at or after it
(`knowable_at = max(first_seen_at, published_at + precision lag)`). A view first seen more than
`LIVE_STALENESS` after its publication is a BACKFILL: it is stored and counted, and it is never an
observation, because measuring a 2019 upgrade from a 2026 first sighting is not a measurement of
anything. The vendor-dated history is published beside the strict numbers under a label that says
exactly what it is (`research_only_vendor_dated`) and feeds no cell, no axis and no contract.

ABSENCE IS UNMEASURED, NEVER ZERO (L1.28a). A missing target is `None` and its name is listed in
`unmeasured`; a missing target never becomes a 0% target change, and a view with no direction is
stored and counted and never traded.

Pure: stdlib, numpy and pandas. Fetches nothing.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

UNMEASURED = "UNMEASURED"

#: The five things a view can DO. `UNMEASURED` is a real answer: the page said nothing we can read.
ACTIONS: tuple[str, ...] = ("up", "down", "init", "reiterate", UNMEASURED)
#: A view is either ABOUT the instrument (`direct`) or about a related issuer in another market
#: whose information is hypothesised to arrive in the instrument later (`lead`).
RELATIONS: tuple[str, ...] = ("direct", "lead")
KINDS: tuple[str, ...] = ("broker_rating", "company_guidance", "industry_view", "macro_view")

#: A view first seen more than this after publication is a backfill, never an observation.
LIVE_STALENESS = timedelta(days=3)
#: A date-only publication stamp is knowable no earlier than 06:00 UTC on the NEXT day: the end
#: of that local day in every timezone the five sources publish from (UTC+9 .. UTC-5).
DATE_PRECISION_LAG = timedelta(hours=30)
#: Trading-day horizons the tracker measures.
HORIZONS_D: tuple[int, ...] = (1, 5, 21)
#: Daily observations a group needs before its mean is a measurement.
MIN_EVENTS = 12
#: A reiteration moves the book only when it carries a target move at least this large (%).
REITERATE_TARGET_MOVE_PCT = 5.0

#: Lead groups -> the MT5 instruments they are hypothesised to lead. ONE TABLE, read by the organ
#: and by the family, so the gauntlet replays exactly the mapping the proposer measured. The SIGN
#: of a lead is never declared here: it is MEASURED by the tracker and carried on the cell.
SEMIS_US: tuple[str, ...] = ("NVIDIA", "AMD", "MicronTechnology", "TSMC", "AppliedMaterials",
                             "Broadcom", "Qualcomm", "Intel", "TexasInstruments")
LEAD_TARGETS: dict[str, tuple[str, ...]] = {
    "kr_semis": (*SEMIS_US, "USDKRW"),
    "kr_market": ("USDKRW",),
    "cn_market": ("CHINAH", "HK50", "USDCNH"),
    "cn_semis": SEMIS_US,
    "cn_internet": ("AlibabaGroup", "Baidu", "TMEGroup", "CHINAH", "HK50"),
    "cn_auto": ("NIO", "CHINAH"),
    "jp_market": ("JPN225", "USDJPY"),
}

# ------------------------------------------------------------------------------ ratings
#: Exact rating words -> the 5-point scale (5 strong buy .. 1 strong sell). EN, CN, KR, JP.
_EXACT: dict[str, int] = {
    # English (Yahoo firms, Naver's English labels)
    "strong buy": 5, "conviction buy": 5, "top pick": 5, "strong-buy": 5,
    "buy": 4, "outperform": 4, "overweight": 4, "accumulate": 4, "add": 4, "positive": 4,
    "market outperform": 4, "sector outperform": 4, "moderate buy": 4, "long-term buy": 4,
    "speculative buy": 4, "trading buy": 4, "above average": 4,
    "hold": 3, "neutral": 3, "market perform": 3, "sector perform": 3, "equal-weight": 3,
    "equal weight": 3, "in-line": 3, "in line": 3, "peer perform": 3, "sector weight": 3,
    "market weight": 3, "perform": 3, "mixed": 3, "marketperform": 3, "average": 3,
    "underperform": 2, "underweight": 2, "reduce": 2, "moderate sell": 2,
    "sector underperform": 2, "market underperform": 2, "negative": 2, "below average": 2,
    "sell": 1, "strong sell": 1, "strong-sell": 1,
    # Chinese (eastmoney emRatingName / sRatingName)
    "买入": 5, "强烈推荐": 5, "强推": 5, "增持": 4, "推荐": 4, "优于大市": 4, "跑赢行业": 4,
    "谨慎增持": 4, "审慎增持": 4, "谨慎推荐": 4, "强于大市": 4, "看好": 4, "跑赢大市": 4,
    "中性": 3, "持有": 3, "同步大市": 3, "观望": 3, "区间操作": 3,
    "减持": 2, "弱于大市": 2, "跑输行业": 2, "跑输大市": 2, "回避": 2, "看淡": 2,
    "卖出": 1,
    # Korean (Naver research detail pages)
    "강력매수": 5, "적극매수": 5, "매수": 4, "비중확대": 4, "단기매수": 4,
    "중립": 3, "보유": 3, "시장수익률": 3, "시장평균": 3,
    "비중축소": 2, "매도": 1,
    # Japanese
    "強気": 4, "やや強気": 4, "中立": 3, "やや弱気": 2, "弱気": 1,
}
#: Substring fallbacks, most specific first, so "underweight" is never read as "weight".
_SUBSTR: tuple[tuple[str, int], ...] = (
    ("strong buy", 5), ("conviction", 5), ("strong sell", 1), ("underperform", 2),
    ("underweight", 2), ("outperform", 4), ("overweight", 4), ("accumulate", 4), ("buy", 4),
    ("sell", 1), ("reduce", 2), ("hold", 3), ("neutral", 3), ("perform", 3), ("equal", 3),
)
#: Explicit non-ratings. "Not rated" is not a neutral: it is no rating at all.
_NOT_RATED = frozenset({"", "nr", "n/a", "na", "not rated", "none", "-", "--", "없음",
                        "无", "未评级", "투자의견없음", "suspended", "under review"})


def normalise_rating(raw: Any) -> int | None:
    """A rating word in any of the four languages -> 1..5, or None when it is not a rating."""
    if raw is None:
        return None
    text = re.sub(r"\s+", " ", str(raw).strip().lower())
    if text in _NOT_RATED:
        return None
    if text in _EXACT:
        return _EXACT[text]
    compact = text.replace(" ", "")
    if compact in _EXACT:
        return _EXACT[compact]
    for word, score in _SUBSTR:
        if word in text:
            return score
    return None


def _num(value: Any) -> float | None:
    """A finite float from a published number ("85,000", "12.5", 12), or None. Never 0 for blank."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = float(value)
        return x if math.isfinite(x) and x > 0 else None
    text = str(value).strip().replace(",", "").replace("$", "").replace("원", "")
    text = text.replace("元", "").replace("円", "")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    x = float(m.group(0))
    return x if math.isfinite(x) and x > 0 else None


def _iso(when: datetime | None) -> str | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.astimezone(UTC).isoformat(timespec="seconds")


def parse_time(value: Any) -> datetime | None:
    """An ISO string or datetime as aware UTC; None when it is not one."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


# ------------------------------------------------------------------------------ the view
@dataclass
class AnalystView:
    """One analyst/broker/company view, normalised. `None` means UNMEASURED and is listed."""

    source: str
    published_at: str | None
    issuer: str
    title: str
    first_seen_at: str | None = None
    published_precision: str = UNMEASURED        # "datetime" | "date" | UNMEASURED
    issuer_name: str = ""
    instrument: str | None = None                # the MT5 symbol the view is ABOUT, if any
    leads: list[str] = field(default_factory=list)   # LEAD_TARGETS keys
    broker: str | None = None
    action: str = UNMEASURED
    rating_old_raw: str | None = None
    rating_new_raw: str | None = None
    rating_old: int | None = None
    rating_new: int | None = None
    target_old: float | None = None
    target_new: float | None = None
    target_change_pct: float | None = None
    conviction: float | None = None
    direction: int = 0
    language: str = "en"
    region: str = ""
    kind: str = "broker_rating"
    url: str = ""
    native_id: str = ""
    event_id: str = ""
    prior_from_store: bool = False
    unmeasured: list[str] = field(default_factory=list)

    def finish(self) -> AnalystView:
        """Derive every dependent field from the published ones. Idempotent."""
        if self.rating_old is None:
            self.rating_old = normalise_rating(self.rating_old_raw)
        if self.rating_new is None:
            self.rating_new = normalise_rating(self.rating_new_raw)
        self.target_old = _num(self.target_old)
        self.target_new = _num(self.target_new)
        if self.target_old is not None and self.target_new is not None:
            self.target_change_pct = round(100.0 * (self.target_new / self.target_old - 1.0), 4)
        else:
            self.target_change_pct = None
        if self.action not in ACTIONS:
            self.action = UNMEASURED
        if self.action == UNMEASURED:
            self.action = _infer_action(self)
        self.direction = direction_of(self)
        self.conviction = conviction_of(self)
        if not self.event_id:
            self.event_id = event_id_of(self)
        self.unmeasured = sorted(k for k in ("published_at", "broker", "rating_old", "rating_new",
                                             "target_old", "target_new", "target_change_pct",
                                             "conviction", "instrument")
                                 if getattr(self, k) is None)
        if self.action == UNMEASURED:
            self.unmeasured.append("action")
        return self


def _infer_action(v: AnalystView) -> str:
    """The action from what the page DID say, never from what it did not. Two ratings compare;
    anything less stays UNMEASURED (a target move still gives a direction in `direction_of`)."""
    if v.rating_new is not None and v.rating_old is not None:
        if v.rating_new > v.rating_old:
            return "up"
        if v.rating_new < v.rating_old:
            return "down"
        return "reiterate"
    return UNMEASURED


def direction_of(v: AnalystView) -> int:
    """+1 bullish, -1 bearish, 0 no directional content. The rule is the whole claim:

    up -> +1, down -> -1; an initiation takes the side of its rating (>=4 long, <=2 short, 3 none);
    a reiteration moves only with a target change of at least REITERATE_TARGET_MOVE_PCT; an
    unreadable action falls back to a target move of that size, and otherwise has no direction.
    """
    tc = v.target_change_pct
    big = tc is not None and abs(tc) >= REITERATE_TARGET_MOVE_PCT
    if v.action == "up":
        return 1
    if v.action == "down":
        return -1
    if v.action == "init":
        if v.rating_new is None:
            return 0
        return 1 if v.rating_new >= 4 else (-1 if v.rating_new <= 2 else 0)
    if big and tc is not None:
        return 1 if tc > 0 else -1
    return 0


def conviction_of(v: AnalystView) -> float | None:
    """0..1: rating steps moved (two steps = 1.0), else the target move (20% = 1.0). None when
    neither was published -- a direction with no size is not a conviction of zero."""
    if v.rating_new is not None and v.rating_old is not None and v.rating_new != v.rating_old:
        return round(min(1.0, abs(v.rating_new - v.rating_old) / 2.0), 4)
    if v.target_change_pct is not None:
        return round(min(1.0, abs(v.target_change_pct) / 20.0), 4)
    if v.action == "init" and v.rating_new is not None:
        return round(abs(v.rating_new - 3) / 2.0, 4)
    return None


def event_id_of(v: AnalystView) -> str:
    """Stable id: the source's own id when it has one, else the content that identifies a view."""
    if v.native_id:
        raw = f"{v.source}|{v.native_id}"
    else:
        raw = "|".join(str(x) for x in (v.source, v.issuer, v.broker, v.published_at, v.title))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def knowable_at(row: Mapping[str, Any]) -> tuple[datetime | None, str]:
    """(instant, status). The first instant a row may condition a return, or None with why.

    `max(first_seen_at, published_at + precision lag)`; a row first seen more than
    LIVE_STALENESS after its publication is BACKFILL and is never an observation.
    """
    seen = parse_time(row.get("first_seen_at"))
    if seen is None:
        return None, "NO_FIRST_SEEN"
    pub = parse_time(row.get("published_at"))
    if pub is None:
        return None, "NO_PUBLISHED_AT"
    effective = pub + (DATE_PRECISION_LAG if row.get("published_precision") == "date"
                       else timedelta(0))
    if seen - pub > LIVE_STALENESS:
        return None, "BACKFILL"
    return max(seen, effective), "LIVE"


def vendor_knowable_at(row: Mapping[str, Any]) -> datetime | None:
    """The VENDOR-dated instant (published_at + precision lag). Research only; never a cell."""
    pub = parse_time(row.get("published_at"))
    if pub is None:
        return None
    return pub + (DATE_PRECISION_LAG if row.get("published_precision") == "date"
                  else timedelta(0))


# ------------------------------------------------------------------------------ the store
_CONTENT_KEYS = ("action", "rating_old", "rating_new", "target_old", "target_new", "title",
                 "broker", "published_at", "instrument")


class AnalystViewStore:
    """Append-only JSONL. A row is never rewritten: a changed re-serve is a chained revision."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def rows(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            with self.path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        out.append(row)
        except OSError:
            return []
        return out

    def first_rows(self) -> dict[str, dict[str, Any]]:
        """event_id -> the row as FIRST seen. Later revisions never move first_seen_at."""
        first: dict[str, dict[str, Any]] = {}
        for row in self.rows():
            eid = str(row.get("event_id") or "")
            if eid and eid not in first:
                first[eid] = row
        return first

    def append(self, views: Iterable[AnalystView], *, now: datetime,
               source_version: str | None = None) -> dict[str, Any]:
        """Stamp and append. New ids get `first_seen_at = now`; a re-served id with the same
        content is a no-op; a re-served id with changed content is appended as a revision whose
        `first_seen_at` is the ORIGINAL sighting. Returns counts, never raises on a bad row."""
        from libs.data import pit

        latest: dict[str, dict[str, Any]] = {}
        for row in self.rows():
            eid = str(row.get("event_id") or "")
            if eid:
                latest.setdefault(eid, row)
                if row.get("revision_of"):
                    latest[eid] = {**row, "first_seen_at": latest[eid].get("first_seen_at")}
        now_iso = _iso(now)
        fresh: list[dict[str, Any]] = []
        revised: list[dict[str, Any]] = []
        same = 0
        for v in views:
            v.finish()
            body = asdict(v)
            prev = latest.get(v.event_id)
            if prev is None:
                body["first_seen_at"] = now_iso
                body["available_time"] = now_iso          # the desk knew it when it SAW it
                body["event_time"] = body.get("published_at")
                fresh.append(body)
                latest[v.event_id] = body
                continue
            if all(prev.get(k) == body.get(k) for k in _CONTENT_KEYS):
                same += 1
                continue
            body["first_seen_at"] = prev.get("first_seen_at")
            body["event_time"] = body.get("published_at")
            revised.append(pit.revise(body, revision_of=str(prev.get("payload_hash") or ""),
                                      reason="the source re-served this view with changed content",
                                      source=f"alpha_capture:{v.source}", now=now))
            latest[v.event_id] = revised[-1]
        stamped, refused = pit.stamp_or_refuse(fresh, "alpha_capture",
                                               source_version=source_version, now=now)
        out_rows = stamped + [r for r in revised if pit.is_stamped(r)]
        if out_rows:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                for row in out_rows:
                    fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return {"added": len(stamped), "revised": len(out_rows) - len(stamped),
                "unchanged": same, "refused_unstamped": len(refused)}


def fill_prior(views: Sequence[AnalystView], history: Iterable[Mapping[str, Any]]) -> int:
    """Complete target_old / rating_old from the SAME broker's previous view on the SAME issuer.

    Naver's and eastmoney's pages publish today's target and opinion only. The previous one is in
    the store -- a row the desk saw EARLIER -- so reading it is point-in-time by construction.
    Returns how many views were completed. A view with no prior stays UNMEASURED.
    """
    by_key: dict[tuple[str, str, str], list[tuple[datetime, Mapping[str, Any]]]] = defaultdict(list)
    for row in history:
        pub = parse_time(row.get("published_at"))
        if pub is None or not row.get("broker"):
            continue
        by_key[(str(row.get("source")), str(row.get("issuer")), str(row.get("broker")))].append(
            (pub, row))
    for rows in by_key.values():
        rows.sort(key=lambda x: x[0])
    filled = 0
    for v in views:
        if not v.broker or (v.target_old is not None and v.rating_old is not None):
            continue
        pub = parse_time(v.published_at)
        if pub is None:
            continue
        prior = [r for t, r in by_key.get((v.source, v.issuer, v.broker), []) if t < pub]
        if not prior:
            continue
        p = prior[-1]
        touched = False
        if v.target_old is None and _num(p.get("target_new")) is not None:
            v.target_old = _num(p.get("target_new"))
            touched = True
        if v.rating_old is None and v.rating_old_raw in (None, "") and p.get("rating_new"):
            v.rating_old_raw = str(p.get("rating_new_raw") or "")
            v.rating_old = int(p["rating_new"])
            touched = True
        if touched:
            v.prior_from_store = True
            filled += 1
    return filled


# ------------------------------------------------------------------------------ observations
@dataclass(frozen=True)
class Observation:
    target: str
    relation: str
    lead: str
    source: str
    broker: str
    at: datetime              # knowable instant, UTC
    direction: int
    n_views: int = 1


def targets_of(row: Mapping[str, Any],
               universe: set[str] | None = None) -> list[tuple[str, str, str]]:
    """(target, relation, lead-group) for a stored row. Unquoted targets are dropped by name."""
    out: list[tuple[str, str, str]] = []
    inst = row.get("instrument")
    if inst:
        out.append((str(inst), "direct", ""))
    for lead in row.get("leads") or []:
        for t in LEAD_TARGETS.get(str(lead), ()):
            if t != inst:
                out.append((t, "lead", str(lead)))
    if universe is not None:
        out = [x for x in out if x[0] in universe]
    return out


def observations(rows: Iterable[Mapping[str, Any]], *, basis: str = "first_seen",
                 universe: set[str] | None = None) -> tuple[list[Observation], dict[str, int]]:
    """Every directional view -> one observation per target. Returns (obs, census of refusals).

    `basis="first_seen"` is the point-in-time rule and the only basis any cell uses;
    `basis="vendor_dated"` is research-only and labelled wherever it is published.
    """
    rows = list(rows)
    census: dict[str, int] = defaultdict(int)
    out: list[Observation] = []
    # THE FIRST ROW OF AN EVENT THAT CARRIES A DIRECTION IS THE OBSERVATION. A view first seen
    # without its target (a list row whose detail page came a pass later) becomes directional only
    # through a REVISION, whose available_time is the revision's own instant -- so the knowable
    # time is floored there, never back-dated to the directionless first sighting.
    chosen: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        eid = str(row.get("event_id") or "")
        if not eid or eid in chosen:
            continue
        try:
            if int(row.get("direction") or 0) != 0:
                chosen[eid] = row
        except (TypeError, ValueError):
            continue
    all_ids = {str(r.get("event_id") or "") for r in rows}
    census["no_direction"] = len(all_ids - set(chosen) - {""})
    for row in chosen.values():
        direction = int(row.get("direction") or 0)
        if basis == "first_seen":
            at, status = knowable_at(row)
            avail = parse_time(row.get("available_time"))
            if at is not None and avail is not None and avail > at:
                at = avail
        else:
            at, status = vendor_knowable_at(row), "VENDOR"
        if at is None:
            census[status.lower() if status else "unknowable"] += 1
            continue
        tg = targets_of(row, universe)
        if not tg:
            census["no_quoted_target"] += 1
            continue
        for target, relation, lead in tg:
            out.append(Observation(target, relation, lead, str(row.get("source") or ""),
                                   str(row.get("broker") or ""), at, direction))
    return out, dict(census)


def daily_net(obs: Iterable[Observation], *, by_broker: bool = False) -> list[Observation]:
    """Collapse to one observation per (target, source, relation, lead[, broker], UTC day).

    Six brokers upgrading one name on one day are ONE information event, not six independent
    trials. The day's direction is the sign of the net; a day that nets to zero carries none. The
    knowable instant is the LATEST in the day, so the net is never used before its last part.
    """
    groups: dict[tuple[str, ...], list[Observation]] = defaultdict(list)
    for o in obs:
        key = (o.target, o.source, o.relation, o.lead, o.broker if by_broker else "",
               o.at.date().isoformat())
        groups[key].append(o)
    out: list[Observation] = []
    for (target, source, relation, lead, broker, _day), members in groups.items():
        net = sum(m.direction for m in members)
        if net == 0:
            continue
        out.append(Observation(target, relation, lead, source, broker,
                               max(m.at for m in members), 1 if net > 0 else -1, len(members)))
    out.sort(key=lambda o: (o.at, o.target, o.source))
    return out


# ------------------------------------------------------------------------------ bars
@dataclass
class DailyBars:
    """Daily closes derived from an intraday frame, each with the instant its close was known."""

    dates: np.ndarray            # datetime64[D]
    close: np.ndarray            # float
    known: np.ndarray            # float epoch seconds: last bar open + bar length (bar clock)


def to_daily(frame: pd.DataFrame, bar_minutes: int = 60) -> DailyBars | None:
    """H1 (or any intraday) bars -> one close per bar-clock date. None when unusable."""
    if frame is None or len(frame) == 0 or "close" not in frame.columns:
        return None
    idx = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
    close = pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float)
    ok = np.logical_not(np.asarray(idx.isna())) & np.isfinite(close) & (close > 0)
    if ok.sum() < 3:
        return None
    s = pd.Series(close[ok], index=idx[ok]).sort_index()
    s = s[np.logical_not(np.asarray(s.index.duplicated(keep="last")))]
    day = pd.DatetimeIndex(s.index).normalize()
    last = s.groupby(day).tail(1)
    lidx = pd.DatetimeIndex(last.index)
    # Seconds by Timedelta division: pandas 3 may hold microsecond resolution, so a bare
    # `.asi8 / 1e9` would be off by a factor of a thousand on one install and not another.
    known = ((lidx + pd.Timedelta(minutes=int(bar_minutes))) - pd.Timestamp(0, tz="UTC")) \
        / pd.Timedelta(seconds=1)
    return DailyBars(dates=np.asarray(lidx.normalize().tz_localize(None),
                                      dtype="datetime64[D]"),
                     close=last.to_numpy(dtype=float), known=np.asarray(known, dtype=float))


Clock = Callable[[datetime], datetime | None]


def identity_clock(when: datetime) -> datetime | None:
    return when


def bar_clock() -> Clock:
    """UTC -> the bars' own broker frame via `libs.research.bar_clock`; None = drop the event."""
    try:
        from libs.research.bar_clock import to_bar_time
    except Exception:                                     # pragma: no cover - import context
        return lambda _w: None

    def _conv(when: datetime) -> datetime | None:
        moved, _status, _why = to_bar_time(when)
        return moved
    return _conv


def entry_index(bars: DailyBars, at_bar_clock: datetime) -> int:
    """The first daily close KNOWN at or after the instant: never a close that preceded it."""
    return int(np.searchsorted(bars.known, at_bar_clock.timestamp(), side="left"))


def track(obs: Sequence[Observation], bars: Mapping[str, DailyBars | None], *,
          bench: Mapping[str, str] | None = None, clock: Clock = identity_clock,
          horizons: Sequence[int] = HORIZONS_D) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Per observation: log return from the first close known after it to +h trading days,
    minus the benchmark's return over the same dates when one is named and held (CAR), and the
    SIGNED CAR (direction x CAR: long upgrades, short downgrades). Returns (rows, census)."""
    census: dict[str, int] = defaultdict(int)
    rows: list[dict[str, Any]] = []
    bench = bench or {}
    for o in obs:
        b = bars.get(o.target)
        if b is None:
            census["no_bars"] += 1
            continue
        moved = clock(o.at)
        if moved is None:
            census["unconvertible_clock"] += 1
            continue
        pos = entry_index(b, moved)
        if pos >= len(b.close):
            census["pending"] += 1
            continue
        bsym = bench.get(o.target)
        bb = bars.get(bsym) if bsym else None
        row: dict[str, Any] = {"target": o.target, "relation": o.relation, "lead": o.lead,
                               "source": o.source, "broker": o.broker,
                               "at": _iso(o.at), "direction": o.direction,
                               "n_views": o.n_views, "entry_date": str(b.dates[pos]),
                               "benchmark": bsym if bb is not None else "none"}
        for h in horizons:
            j = pos + int(h)
            if j >= len(b.close):
                row[f"car_{h}d"] = None
                row[f"signed_{h}d"] = None
                continue
            r = float(math.log(b.close[j] / b.close[pos]))
            if bb is not None:
                i0 = np.searchsorted(bb.dates, b.dates[pos])
                i1 = np.searchsorted(bb.dates, b.dates[j])
                if (i0 < len(bb.dates) and i1 < len(bb.dates) and bb.dates[i0] == b.dates[pos]
                        and bb.dates[i1] == b.dates[j]):
                    r -= float(math.log(bb.close[i1] / bb.close[i0]))
                else:
                    row["benchmark"] = "none"
            row[f"car_{h}d"] = round(r, 8)
            row[f"signed_{h}d"] = round(o.direction * r, 8)
        rows.append(row)
    return rows, dict(census)


def stats(values: Sequence[float], floor: int = MIN_EVENTS) -> dict[str, Any]:
    """n, mean, sd, t, hit. Below `floor` the numbers are published and the status says so."""
    a = np.asarray([v for v in values if v is not None and math.isfinite(v)], dtype=float)
    n = int(a.size)
    if n < 2:
        return {"n": n, "status": UNMEASURED, "why": f"{n} observation(s)"}
    mean, sd = float(a.mean()), float(a.std(ddof=1))
    t = mean / (sd / math.sqrt(n)) if sd > 0 else None
    out = {"n": n, "mean_bp": round(mean * 1e4, 3), "sd_bp": round(sd * 1e4, 3),
           "t": None if t is None else round(t, 3), "hit": round(float((a > 0).mean()), 4),
           "status": "MEASURED" if n >= floor and t is not None else UNMEASURED}
    if out["status"] == UNMEASURED:
        out["why"] = f"n={n} < {floor}" if n < floor else "zero dispersion"
    return out


def aggregate(rows: Sequence[Mapping[str, Any]], keys: Sequence[str],
              horizons: Sequence[int] = HORIZONS_D, floor: int = MIN_EVENTS
              ) -> list[dict[str, Any]]:
    """Signed-CAR statistics grouped by `keys` (e.g. ("source",), ("source", "broker"))."""
    groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[tuple(str(r.get(k) or "") for k in keys)].append(r)
    out: list[dict[str, Any]] = []
    for key, members in sorted(groups.items()):
        rec: dict[str, Any] = dict(zip(keys, key, strict=True))
        rec["n_up"] = sum(1 for m in members if int(m.get("direction") or 0) > 0)
        rec["n_down"] = sum(1 for m in members if int(m.get("direction") or 0) < 0)
        for h in horizons:
            rec[f"{h}d"] = stats([float(m[f"signed_{h}d"]) for m in members
                                  if m.get(f"signed_{h}d") is not None], floor)
        out.append(rec)
    return out


# ------------------------------------------------------------------------------ the contract
def _t_of(values: np.ndarray) -> float | None:
    n = values.size
    if n < 2:
        return None
    sd = float(values.std(ddof=1))
    return float(values.mean() / (sd / math.sqrt(n))) if sd > 0 else None


def placebo_contract(obs: Sequence[Observation], bars: Mapping[str, DailyBars | None], *,
                     horizon: int = 5, n_placebo: int = 200, min_shift: int = 30,
                     max_shift: int = 250, seed: int = 0, clock: Clock = identity_clock,
                     floor: int = MIN_EVENTS, alpha: float = 0.05, t_bar: float = 2.0,
                     key: Callable[[Observation], str] | None = None
                     ) -> dict[str, dict[str, Any]]:
    """THE ADMISSION TEST, per source: is the post-publication drift information or calendar?

    Real: the t-statistic of signed +`horizon`-day returns after each observation's first known
    close. Placebo: the SAME observations, same directions, same instruments, with each entry moved
    by a random +/-[min_shift, max_shift] trading days -- so any drift the instruments carry
    unconditionally (a trending sample, a direction imbalance) is in the placebo too, and only
    what is tied to the publication date is not. Admit when n >= floor, |t| >= t_bar and the
    two-sided placebo p <= alpha. Below the floor the verdict is UNMEASURED, never a pass.

    `key` groups the observations (default: by source). `cell_key` groups them per direct cell
    -- (target, source, relation, lead) -- so each cell a pass would donate is judged against
    its own shifted-date placebo, not only its source's.
    """
    rng = np.random.default_rng(seed)
    by_source: dict[str, list[tuple[DailyBars, int, int]]] = defaultdict(list)
    for o in obs:
        b = bars.get(o.target)
        moved = clock(o.at) if b is not None else None
        if b is None or moved is None:
            continue
        pos = entry_index(b, moved)
        if pos + horizon < len(b.close):
            by_source[key(o) if key is not None else o.source].append((b, pos, o.direction))
    out: dict[str, dict[str, Any]] = {}
    for source, items in sorted(by_source.items()):
        real = np.asarray([d * math.log(b.close[p + horizon] / b.close[p]) for b, p, d in items])
        n = int(real.size)
        t_real = _t_of(real)
        if n < floor or t_real is None:
            out[source] = {"status": UNMEASURED, "n": n, "t": t_real, "horizon_d": horizon,
                           "why": f"n={n} < {floor} observations known before their horizon"
                                  if n < floor else "zero dispersion"}
            continue
        placebo_t: list[float] = []
        for _ in range(int(n_placebo)):
            vals: list[float] = []
            for b, p, d in items:
                size = len(b.close)
                for _try in range(8):
                    shift = int(rng.integers(min_shift, max_shift + 1)) * (
                        1 if rng.random() < 0.5 else -1)
                    q = p + shift
                    if q >= 0 and q + horizon < size:
                        vals.append(d * math.log(b.close[q + horizon] / b.close[q]))
                        break
            tp = _t_of(np.asarray(vals, dtype=float))
            if tp is not None:
                placebo_t.append(tp)
        pt = np.asarray(placebo_t, dtype=float)
        if pt.size < 20:
            out[source] = {"status": UNMEASURED, "n": n, "t": round(t_real, 3),
                           "horizon_d": horizon,
                           "why": f"only {pt.size} placebo draws were placeable: the bars are too "
                                  "short to shift the events away from their own dates"}
            continue
        p_value = float((1 + np.sum(np.abs(pt) >= abs(t_real))) / (1 + pt.size))
        admit = abs(t_real) >= t_bar and p_value <= alpha
        out[source] = {"status": "ADMIT" if admit else "REJECT", "n": n,
                       "t": round(t_real, 3), "mean_bp": round(float(real.mean()) * 1e4, 3),
                       "horizon_d": horizon, "placebo_draws": int(pt.size),
                       "placebo_t_mean": round(float(pt.mean()), 3),
                       "placebo_t_sd": round(float(pt.std(ddof=1)), 3),
                       "p_placebo": round(p_value, 4),
                       "rule": f"|t| >= {t_bar} and placebo p <= {alpha} at n >= {floor}"}
    return out


def cell_key(o: Observation) -> str:
    """The direct-cell grouping `alpha_capture.cell_rows` donates on."""
    return f"{o.target}|{o.source}|{o.relation}|{o.lead}"


def rows_by_day(rows: Iterable[Mapping[str, Any]], *, universe: set[str] | None = None,
                window_days: int = 21) -> list[dict[str, Any]]:
    """Per (instrument, UTC day): the axis row -- counts, net breadth and trailing breadth.

    `knowable_at` is the LATEST knowable instant of the day's first-seen observations, so a
    consumer joining on it never sees the day's net before its last component existed.
    """
    obs, _ = observations(rows, basis="first_seen", universe=universe)
    per: dict[tuple[str, date], list[Observation]] = defaultdict(list)
    for o in obs:
        per[(o.target, o.at.date())].append(o)
    days_by_sym: dict[str, list[tuple[date, list[Observation]]]] = defaultdict(list)
    for (sym, d), members in per.items():
        days_by_sym[sym].append((d, members))
    out: list[dict[str, Any]] = []
    for sym, days in sorted(days_by_sym.items()):
        days.sort(key=lambda x: x[0])
        for i, (d, members) in enumerate(days):
            up = sum(1 for m in members if m.direction > 0)
            dn = sum(1 for m in members if m.direction < 0)
            lo = d - timedelta(days=window_days - 1)
            trail = [m for dd, mm in days[: i + 1] if dd >= lo for m in mm]
            tu = sum(1 for m in trail if m.direction > 0)
            td = sum(1 for m in trail if m.direction < 0)
            out.append({"symbol": sym, "knowable_at": _iso(max(m.at for m in members)),
                        "as_of": d.isoformat(), "n_views": len(members), "n_up": up,
                        "n_down": dn, "net_breadth": round((up - dn) / len(members), 4),
                        "n_views_21d": len(trail),
                        "breadth_21d": round((tu - td) / len(trail), 4)})
    return out
