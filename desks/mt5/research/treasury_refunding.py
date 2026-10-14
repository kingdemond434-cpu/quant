"""TREASURY REFUNDING: the Quarterly Refunding Announcement's size and guidance surprise, PIT.

THE IDEA (coordinator's hourly pass 4, idea F5, 2026-10-14): once a quarter the US Treasury says
how many coupons it will sell (the 3-, 10- and 30-year refunding auction sizes) and what it
expects to do next ("at least the next several quarters" vs "anticipates increases"). More
duration supply than the market was told to expect raises the term premium: Treasuries cheapen,
the dollar firms against the yen, equities and gold lose a discount-rate tailwind. The desk had
no record of these announcements. This organ reads them from home.treasury.gov, writes one lake
series, and donates exactly pre-registered conditioner cells on UST10Y, USDJPY, US500 and XAUUSD.

NO MODEL IS IN THE PATH, ON PURPOSE (the same rule as `election_calendar`, #388). The sizes and
the guidance are read by FIXED CODE from the statement's own words: a dollar amount next to a
tenor, and a guidance phrase inside a sentence about coupon auction sizes. A model scoring the
"tone" could be scoring with hindsight of what yields did next, which is look-ahead no cutoff
guard can trim when the model's training ends after the whole history; fixed code has no such
channel. The cells' sides are fixed below from the stated mechanism, never from data or a model.

TWO SIGNALS, BOTH SURPRISES RELATIVE TO WHAT TREASURY ITSELF HAD SAID.
  * `size_surprise`: the fractional change in the refunding's coupon sizes (tenors common to this
    and the previous statement), counted ONLY when the previous statement's guidance did not
    point that way. A change Treasury pre-announced is priced; a change against guidance is news.
  * `guidance_shift`: this statement's guidance (+1 increases ahead, 0 maintain, -1 reductions)
    minus the previous one's. A move to "increases ahead" is supply news before any auction.
Each is non-zero on the release day and the POST_DAYS - 1 days after it, and 0.0 on a day with
no statement ONLY when the desk can show there was none: the day is published before the last
successful read of the most-recent index, and no listed-but-unread statement could fall on it.
An unread statement's possible dates are bounded by its DATED neighbours in the index's own
order; with no such bound it blocks every day. Any other day (index unreachable since, a row
not yet published) is blank, UNMEASURED, never a clean zero (audits on #394 v2-v4).

POINT IN TIME. The statement is released at 08:30 New York time on the announcement day; each
held row is stamped at RELEASE_HOUR_UTC that day (after 08:30 ET in summer and winter). A
statement the desk first read while its surprise was still held is stamped no earlier than that
read (`stamp_basis = first_sight`); one read after its hold ended is history, stamped at its own
publication and flagged `published_history`. The conditioner's own 24 h lag then acts. Rows
exist only up to today. Each row's vintage hashes the ONE statement it carries, so a new quarter
never re-vintages history; a statement whose first read is unrecorded is blank (fail closed).

WHAT IS NOT YET READ, said rather than hidden: the TBAC minutes and the primary-dealer
expectations they summarise. They would sharpen the surprise (dealer consensus vs outcome) and
are the next step; until then the surprise is measured against Treasury's own prior guidance.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = BASE / "data" / "treasury_refunding"
STATEMENTS = STATE_DIR / "statements.json"
FETCHED = STATE_DIR / "fetched.json"
SERIES_DIR = BASE / "data" / "lake" / "series"
DONATE_DIR = BASE / "data" / "intelligence" / "treasury_refunding"
REPORT = BASE / "reports" / "TREASURY_REFUNDING.json"
SOURCE_ID = "treasury_refunding"
UNMEASURED = "UNMEASURED"

POST_DAYS = 5
RELEASE_HOUR_UTC = 14
REFETCH_S = 20 * 3600.0
#: Most statement pages fetched per pass; a statement never changes once read, so it is cached.
MAX_NEW_PER_PASS = 8
EARLIEST = date(1990, 1, 1)
TENORS = ("3", "10", "30")

INDEXES: tuple[str, ...] = (
    "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/"
    "most-recent-quarterly-refunding-documents",
    "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/"
    "quarterly-refunding-archives",
)

#: symbol -> side while a signal is POSITIVE (more supply than guided / guidance turned to
#: increases). Treasuries cheapen (UST10Y is a price), USD firms vs JPY, equities and gold soften.
MECHANISMS: dict[str, int] = {"UST10Y": -1, "USDJPY": 1, "US500": -1, "XAUUSD": -1}
SIGNALS = ("size_surprise", "guidance_shift")

_MONTHS = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"))}
_DATE = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})\b", re.I)
_SIZE = re.compile(r"\$\s?(\d+(?:\.\d+)?)\s+billion\s+(?:of\s+)?(?:(?:the|a|new)\s+)*"
                   r"(3|10|30)[-\s]year\s+(?:notes?|bonds?)\b", re.I)
#: The statement's own phrasing: "a 10-year note in the amount of $42 billion".
_SIZE_AFTER = re.compile(r"\b(3|10|30)[-\s]year\s+(?:notes?|bonds?)\b"
                         r"(?:(?!\d+[-\s]year)[^.$]){0,60}?"
                         r"\$\s?(\d+(?:\.\d+)?)\s+billion", re.I)
#: A reopening sentence sizes one auction, never the refunding list (audit #394 v2).
_REOPEN = re.compile(r"\breopen", re.I)
#: A clause about NOMINAL coupon sizes: TIPS, FRN and bill sizes are other supply.
_COUPON = re.compile(r"\bcoupon", re.I)
_NOMINAL = re.compile(r"\bnominal coupon", re.I)
_OTHER_SUPPLY = re.compile(r"\bTIPS\b|inflation[- ]protected|\bFRNs?\b|floating rate|\bbills?\b",
                           re.I)
#: Negation binds to the GUIDED VERB only: a negation word in the 40 characters before it, or
#: "... will not be needed" after it, never one in a reason clause ("because it can no longer
#: rely on bills") -- audit should-fix on #394 v3.
_NEG_BEFORE = re.compile(r"\bnot\b(?!\s+only)|\bno longer\b|n't\b|\bwithout\b|\bcannot\b"
                         r"|\bnever\b|\bunlikely\b", re.I)
_NEG_AFTER = re.compile(r"\b(?:not|no longer|unlikely to)\b(?:\s+be)?\s+"
                        r"(?:needed|necessary|required|warranted)", re.I)
_VERB = re.compile(r"\b(?:increas|reduc|decreas|cut(?:s|ting)?\b)", re.I)
#: Only a CAUSAL clause ends the negation's reach: a parenthetical (", as of now,", ", given
#: current projections,") never does (audit must-fix on #394 v4).
_REASON = re.compile(r"\b(?:because|since|due to|owing to)\b", re.I)
#: How far before the guidance word ("anticipate", "expects", "will") a negation still binds it.
NEG_LEAD = 25
#: Clause boundaries: a separator, or a bare "and"/"while" that starts a new verb phrase, so
#: "maintaining nominal coupon sizes and will increase TIPS" is two clauses (audit #394 v2).
_CLAUSE = re.compile(r";|,\s*(?:while|but|and|whereas)\b|\bwhile\b|\bwhereas\b"
                     r"|\s\band\s+(?=(?:will|plans?|anticipates?|expects?|intends?|is|are|"
                     r"also)\b)", re.I)
_LINK = re.compile(r"""<a\b[^>]*?href\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a\s*>""", re.I | re.S)
_ABOUT = re.compile(r"coupon|auction sizes?|issuance sizes?", re.I)
_UP = re.compile(r"\b(?:anticipates?|expects?|plans?|will)\b[^.]{0,100}?\b(increas)"
                 r"|\b(increas)(?:es?|ing) (?:to|in) (?:nominal )?coupon", re.I)
_DOWN = re.compile(r"\b(?:anticipates?|expects?|plans?|will)\b[^.]{0,100}?"
                   r"\b(reduc|decreas|cut(?=s?\b|ting\b))"
                   r"|\b(reduc|decreas|cut)(?:es?|tions?|ing|s)? (?:to|in) (?:nominal )?coupon",
                   re.I)
_FLAT = re.compile(r"at least the next several quarters|\bmaintain|\bunchanged\b"
                   r"|\bno changes?\b|\bkeep\b[^.]{0,60}\bsteady", re.I)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def statement_links(body: bytes, base_url: str) -> list[str]:
    """Every link on an index page whose text names a refunding statement, on a treasury.gov
    host. A link elsewhere is never followed."""
    import html
    out: list[str] = []
    for href, text in _LINK.findall(body.decode("utf-8", errors="replace")):
        label = html.unescape(re.sub(r"(?s)<[^>]+>", " ", text)).lower()
        if "refunding" not in label or "statement" not in label:
            continue
        url = urllib.parse.urljoin(base_url, html.unescape(href.strip()))
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        on_site = host == "treasury.gov" or host.endswith(".treasury.gov")
        if urllib.parse.urlsplit(url).scheme == "https" and on_site and url not in out:
            out.append(url)
    return out


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"\n|(?<=[.!?])\s+", text) if s.strip()]


def release_date(text: str, *, today: date | None = None) -> date | None:
    """The statement's own date: the first Month D, YYYY in its first 15 blocks."""
    limit = today or datetime.now(UTC).date()
    for line in text.split("\n")[:15]:
        for mt in _DATE.finditer(line):
            try:
                d = date(int(mt.group(3)), _MONTHS[mt.group(1).lower()], int(mt.group(2)))
            except ValueError:
                continue
            if EARLIEST <= d <= limit:
                return d
    return None


def _sizes_in(seg: str) -> dict[str, float]:
    found: dict[str, float] = {}
    used: list[tuple[int, int]] = []
    for mt in _SIZE.finditer(seg):
        found.setdefault(mt.group(2), float(mt.group(1)))
        used.append(mt.span(1))
    for mt in _SIZE_AFTER.finditer(seg):
        # a dollar amount already read as "$N billion <tenor>" belongs to that tenor
        if any(a <= mt.start(2) < b for a, b in used):
            continue
        found.setdefault(mt.group(1), float(mt.group(2)))
    return found


def _without_reopenings(sent: str) -> str:
    """The sentence minus every comma/semicolon clause that names a reopening, so a full list
    sentence that also mentions one keeps its list (audit should-fix on #394 v3)."""
    if not _REOPEN.search(sent):
        return sent
    return ", ".join(c for c in re.split(r"[;,]", sent) if not _REOPEN.search(c))


def sizes(text: str) -> dict[str, float]:
    """Tenor -> $bn, read ONLY from the refunding list: the first block or sentence that
    sizes all three of the 3/10/30-year tenors, else the first that sizes two; a sentence about a
    reopening is never read (audit must-fix 4 on #394 and its v2 follow-up). Empty when
    the statement has no such list -- UNMEASURED, never a size read elsewhere."""
    segs = [(seg, _sizes_in(seg)) for seg in map(_without_reopenings, _sentences(text))]
    for need in (len(TENORS), 2):        # the sentence that sizes all three wins, then two
        for _seg, found in segs:
            if sum(t in found for t in TENORS) >= need:
                return {t: found[t] for t in TENORS if t in found}
    return {}


def _clause_reading(clause: str) -> int | None:
    nominal = bool(_NOMINAL.search(clause))
    if not nominal and (not _COUPON.search(clause) or _OTHER_SUPPLY.search(clause)):
        return None
    up, down = _UP.search(clause), _DOWN.search(clause)
    for mt, v in ((up, 1), (down, -1)):
        if mt is None:
            continue
        verb = next(mt.start(g) for g in range(1, 3) if mt.group(g)) if mt.lastindex else 0
        # The guided phrase: from just before its guidance word up to the verb. A negation in
        # it holds sizes ("does not currently anticipate that it will need to increase", "will
        # not, given current projections, increase"); one earlier in the clause that this
        # window cannot bind makes the clause UNMEASURED, never the wrong sign.
        prefix = _REASON.split(clause[:verb])[-1]
        phrase = clause[max(0, mt.start() - NEG_LEAD):verb]
        phrase = _REASON.split(phrase)[-1]
        after = _REASON.split(clause[mt.end():mt.end() + 60])[0]
        if _NEG_BEFORE.search(phrase) or _NEG_AFTER.search(after):
            return 0        # "does not anticipate needing to increase": sizes held
        if _NEG_BEFORE.search(prefix):
            return None
        if any(not re.search(r"\bnot only\s*$", clause[:f.start()], re.I)
               for f in _FLAT.finditer(clause)):
            return None     # "maintain ... despite reduced demand": two readings, none taken
        # the object of the verb must be nominal coupons, not TIPS / FRN / bills
        if not _OTHER_SUPPLY.search(after[:40]):
            return v
    if up or down:
        return None
    bare = _VERB.search(clause)
    lead = clause[max(0, bare.start() - 40):bare.start()] if bare else ""
    if bare and _NEG_BEFORE.search(_REASON.split(lead)[-1]):
        return 0            # "cannot foresee a need to increase", with no guidance verb
    if _FLAT.search(clause):
        return 0
    return None


def guidance(text: str) -> int | None:
    """Treasury's guidance on NOMINAL coupon auction sizes: +1 increases ahead, -1 reductions
    ahead, 0 held. Read per clause, so a TIPS, FRN or bill clause never counts, and a negated
    increase reads as held (audit must-fixes 1 and 2 on #394). Clauses that disagree, or none
    that say anything, are None: UNMEASURED, never a guess."""
    seen = set()
    for sent in _sentences(text):
        if not _ABOUT.search(sent):
            continue
        for clause in _CLAUSE.split(sent):
            v = _clause_reading(clause)
            if v is not None:
                seen.add(v)
    return seen.pop() if len(seen) == 1 else None


def parse(text: str, url: str, seen: str, *, today: date | None = None) -> dict[str, Any] | None:
    d = release_date(text, today=today)
    if d is None:
        return None
    return {"date": d.isoformat(), "url": url, "first_seen": seen, "sizes": sizes(text),
            "guidance": guidance(text)}


def _change(prev: dict[str, Any], cur: dict[str, Any]) -> float | None:
    """Fractional change in coupon sizes over the tenors both statements size, or None."""
    common = [t for t in TENORS if t in (cur.get("sizes") or {})
              and t in (prev.get("sizes") or {})]
    before = sum(float(prev["sizes"][t]) for t in common)
    if not common or before <= 0:
        return None
    return sum(float(cur["sizes"][t]) for t in common) / before - 1.0


def _prior_step(pair_changes: Sequence[tuple[str, float | None]], before: str) -> float | None:
    """The size of a missed step: the median measured |move| over statement pairs dated
    strictly BEFORE `before` -- never a later quarter (audit must-fix on #394 v3: the
    whole-record median re-scored history every quarter)."""
    moves = sorted(abs(c) for d, c in pair_changes if d < before and c)
    return moves[len(moves) // 2] if moves else None


def _one_per_date(statements: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """One statement per release date, oldest first. Two pages dated the same day that agree are
    one statement; two that disagree on sizes or guidance are that day's statement with both
    readings UNMEASURED -- never the later page silently overriding with a 0.0 change (audit
    should-fix on #394 v4)."""
    by_day: dict[str, dict[str, Any]] = {}
    for st in sorted((x for x in statements if x.get("date")),
                     key=lambda x: (x["date"], str(x.get("url") or ""))):
        have = by_day.get(st["date"])
        if have is None:
            by_day[st["date"]] = dict(st)
            continue
        for k in ("sizes", "guidance"):
            if have.get(k) != st.get(k):
                have[k] = {} if k == "sizes" else None
        seen = [t for t in (have.get("first_seen"), st.get("first_seen")) if t]
        have["first_seen"] = min(seen) if seen else None
    return [by_day[d] for d in sorted(by_day)]


def surprises(statements: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each statement with its two surprises against the one before it (None = UNMEASURED)."""
    rows = _one_per_date(statements)
    pair_changes = [(c["date"], _change(p, c)) for p, c in pairwise(rows)]
    out: list[dict[str, Any]] = []
    for prev, cur in zip([None, *rows][:len(rows)], rows, strict=True):
        size_s: float | None = None
        shift: float | None = None
        if prev is not None:
            change = _change(prev, cur)
            guided = prev.get("guidance")
            if change is not None and isinstance(guided, int):
                sign = (change > 0) - (change < 0)
                if sign == guided:
                    size_s = 0.0
                elif sign != 0:
                    size_s = round(change, 6)
                elif (step := _prior_step(pair_changes, cur["date"])) is not None:
                    # guided increases (or cuts) that did not come: less (more) supply than
                    # promised, by one typical step (audit should-fix on #394 v2)
                    size_s = round(-guided * step, 6)
            # an unreadable prior guidance leaves the surprise UNMEASURED (must-fix 3)
            g0, g1 = prev.get("guidance"), cur.get("guidance")
            if isinstance(g0, int) and isinstance(g1, int):
                shift = float(g1 - g0)
        out.append({**cur, "size_surprise": size_s, "guidance_shift": shift})
    return out


SERIES_COLUMNS = ("available_time", "published_time", "retrieval_time", "source_id",
                  "vintage_id", "stamp_basis", *SIGNALS)


def _seen_at(ev: dict[str, Any]) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ev.get("first_seen")))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _stamp(d: date, ev: dict[str, Any] | None) -> tuple[datetime, str]:
    """When day D's row became knowable (audit must-fix 5 on #394, #388's rule). A statement
    the desk first read while its surprise was still being held is stamped no earlier than that
    read (`first_sight`). One first read after its hold had ended is history: stamped at its own
    08:30 ET publication (RELEASE_HOUR_UTC), the document's public time, and flagged."""
    pub = datetime(d.year, d.month, d.day, RELEASE_HOUR_UTC, tzinfo=UTC)
    if ev is None:
        return pub, "calendar"
    seen = _seen_at(ev)
    rel = date.fromisoformat(str(ev["date"]))
    hold_end = datetime(rel.year, rel.month, rel.day, tzinfo=UTC) + timedelta(days=POST_DAYS)
    if seen is None:
        return pub, "unstamped"          # fail closed: its values are written blank
    if seen < hold_end:
        return max(pub, seen), "first_sight"
    return pub, "published_history"


def _vintage(s: dict[str, Any] | None) -> str:
    """One statement's content hash: a re-read (corrected size or guidance) is a visible
    revision of THAT row, and a new quarter never re-vintages history (audit #394 v2)."""
    body = (["none"] if s is None else
            [s["date"], s.get("sizes"), s.get("guidance"), s.get("size_surprise"),
             s.get("guidance_shift")])
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:12]


def series_rows(scored: Sequence[dict[str, Any]], *, today: date | None = None,
                measured_until: datetime | None = None, now: datetime | None = None,
                blocked: Sequence[tuple[date | None, date | None]] = ()
                ) -> list[dict[str, Any]]:
    """One row a day from the first statement to today; each surprise is held POST_DAYS days.
    A day with no statement is 0.0 only when published at or before `measured_until` (the last
    read of the most-recent index), not after `now`, and outside every `blocked` window (the
    dates an unread listed statement could carry); otherwise it is blank, as is any UNMEASURED
    surprise. Never a clean zero for a day nobody looked at."""
    if not scored:
        return []
    end = today or datetime.now(UTC).date()
    clock = now or datetime.now(UTC)
    events = [(date.fromisoformat(s["date"]), s) for s in scored]
    d = events[0][0]
    rows: list[dict[str, Any]] = []
    while d <= end:
        ev = next((s for e, s in reversed(events) if 0 <= (d - e).days < POST_DAYS), None)
        avail, basis = _stamp(d, ev)
        row: dict[str, Any] = {"available_time": avail.isoformat(),
                               "published_time": datetime(d.year, d.month, d.day,
                                                          RELEASE_HOUR_UTC,
                                                          tzinfo=UTC).isoformat(),
                               "retrieval_time": ev.get("first_seen", "") if ev else "",
                               "source_id": SOURCE_ID, "vintage_id": _vintage(ev),
                               "stamp_basis": basis}
        known_none = (measured_until is not None and avail <= measured_until
                      and avail <= clock
                      and not any((lo is None or lo <= d) and (hi is None or d <= hi)
                                  for lo, hi in blocked))
        if ev is None and not known_none:
            row["stamp_basis"] = UNMEASURED
        for sig in SIGNALS:
            v = (ev.get(sig) if basis != "unstamped" else None) if ev else (
                0.0 if known_none else None)
            row[sig] = "" if v is None else v
        rows.append(row)
        d += timedelta(days=1)
    return rows


def unread_windows(unread: Sequence[str], fetched: dict[str, Any], store: dict[str, Any]
                   ) -> list[dict[str, Any]]:
    """For each listed-but-unread statement, the dates it could carry: between its nearest DATED
    neighbours in the order an index lists them (the order's direction read from the dated
    links themselves). Unbounded on a side with no neighbour that bounds it; wholly unbounded
    when no index lists it with two dated links to orient by (audit should-fix on #394 v4)."""
    def day(u: str) -> date | None:
        st = store.get(u)
        try:
            return date.fromisoformat(str(st["date"])) if isinstance(st, dict) else None
        except (KeyError, ValueError):
            return None

    out: list[dict[str, Any]] = []
    for u in unread:
        lo: date | None = None
        hi: date | None = None
        for idx in INDEXES:
            links = list((fetched.get(idx) or {}).get("links") or [])
            if u not in links:
                continue
            dated = [(j, d) for j, x in enumerate(links) if (d := day(x)) is not None]
            if len(dated) < 2 or dated[0][1] == dated[-1][1]:
                continue
            ascending = dated[-1][1] > dated[0][1]
            i = links.index(u)
            before = [d for j, d in dated if j < i]
            after = [d for j, d in dated if j > i]
            b, a = (before[-1] if before else None), (after[0] if after else None)
            lo, hi = ((b, a) if ascending else (a, b))
            break
        out.append({"url": u, "from": lo.isoformat() if lo else None,
                    "to": hi.isoformat() if hi else None})
    return out


def write_series(rows: Sequence[dict[str, Any]]) -> Path:
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    path = SERIES_DIR / f"{SOURCE_ID}.csv"
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(SERIES_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    return path


def cells(scored: Sequence[dict[str, Any]], uni: dict[str, str] | None = None,
          lane_ok: Callable[[str, str], bool] | None = None) -> list[dict[str, Any]]:
    """The pre-registered cells, once at least two surprises of a signal are measured non-zero."""
    out: list[dict[str, Any]] = []
    for sig in SIGNALS:
        n = sum(1 for s in scored if isinstance(s.get(sig), (int, float)) and s[sig] != 0)
        if n < 2:
            continue
        for sym, side in MECHANISMS.items():
            if uni is not None and sym not in uni:
                continue
            if lane_ok is not None and not lane_ok(sym, "exogenous_conditioner"):
                continue
            params = {"source": SOURCE_ID, "signal": sig, "transform": "level_z",
                      "threshold": 1.0, "side_when_high": side}
            ident = hashlib.sha256(json.dumps(
                {"family": "exogenous_conditioner", "params": params, "symbol": sym},
                sort_keys=True).encode()).hexdigest()[:16]
            what = ("coupon sizes moved against Treasury's own prior guidance"
                    if sig == "size_surprise" else "Treasury's size guidance shifted")
            out.append({
                "kind": "hypothesis", "family": "exogenous_conditioner", "params": params,
                "symbols": [sym], "symbol": sym, "cell_id": f"refunding_{ident}",
                "mechanism": (f"duration-supply surprise at the Quarterly Refunding: when {what}, "
                              f"the term premium reprices; {sym} is taken "
                              f"{'long' if side > 0 else 'short'} on more supply than guided "
                              f"({n} measured surprises)"),
                "falsifier": (f"{sym} returns in the {POST_DAYS} days after a refunding "
                              f"{sig.replace('_', ' ')} are no different from unconditioned "
                              f"returns, or carry the opposite sign"),
                "title": f"treasury refunding: {sym} on the {sig.replace('_', ' ')}",
                "mechanism_class": "event", "novelty_class": "GENUINELY_NOVEL",
                "lineage": {"root": f"treasury_refunding:{sig}", "operator": "fixed_rule"},
                "producer": "treasury_refunding", "url": f"lake://{SOURCE_ID}",
                "copy_trade": False, "credibility_inherited": False,
                "gauntlet_bypass": False})
    return out


def run(*, budget_s: float = 60.0, get: Any = None, resolve: Any = None,
        uni: dict[str, str] | None = None, lane_ok: Callable[[str, str], bool] | None = None,
        today: date | None = None) -> dict[str, Any]:
    """Refresh the index pages at most once per REFETCH_S, read up to MAX_NEW_PER_PASS new
    statements, rebuild the series and donate new cells."""
    import collector_lab
    from election_calendar import page_text
    started = time.time()
    deadline = started + max(5.0, budget_s)
    store: dict[str, Any] = _read_json(STATEMENTS, {}) or {}
    fetched: dict[str, Any] = _read_json(FETCHED, {}) or {}
    queue: list[str] = list(fetched.get("_queue") or [])
    per: list[dict[str, Any]] = []

    def left() -> float:
        return min(float(collector_lab.FETCH_S), max(1.0, deadline - time.time()))

    for url in INDEXES:
        last = float((fetched.get(url) or {}).get("at_epoch") or 0)
        if time.time() - last < REFETCH_S:
            per.append({"url": url, "status": "FRESH"})
            continue
        if time.time() > deadline - 5:
            per.append({"url": url, "status": "NOT_REACHED"})
            continue
        body, why = collector_lab.fetch(url, url, get=get, resolve=resolve, budget_s=left())
        prior = fetched.get(url) or {}
        fetched[url] = {"at_epoch": time.time(), "status": why or "OK",
                        **({"ok_epoch": time.time()} if not why else
                           {"ok_epoch": prior["ok_epoch"]} if prior.get("ok_epoch") else {}),
                        # the last good listing stays the order unread statements are bounded by
                        **({"links": prior["links"]} if why and prior.get("links") else {})}
        if why:
            per.append({"url": url, "status": why})
            continue
        links = statement_links(body, url)
        fetched[url]["links"] = links
        queue.extend(u for u in links if u not in store and u not in queue)
        per.append({"url": url, "status": "OK", "links": len(links)})
    # A listed statement the desk holds no DATED reading of (refused, gated, 404, undated) is
    # retried once per REFETCH_S and, until it reads, blocks every 0.0 (audit must-fix #394 v3).
    undated = sorted(u for u, st in store.items() if not (isinstance(st, dict) and st.get("date")))
    for u in undated:
        if (u not in queue and time.time() - float((fetched.get(u) or {}).get("at_epoch") or 0)
                >= REFETCH_S):
            queue.append(u)
    read = 0
    for url in list(queue):
        if read >= MAX_NEW_PER_PASS or time.time() > deadline - 5:
            break
        body, why = collector_lab.fetch(url, url, get=get, resolve=resolve, budget_s=left())
        read += 1
        if why:
            fetched[url] = {"at_epoch": time.time(), "status": why}
            if not why.startswith("UNREACHABLE"):
                queue.remove(url)        # a refusal waits REFETCH_S; an outage retries now
                if not (store.get(url) or {}).get("date"):
                    store[url] = {"url": url, "status": UNMEASURED, "why": why}
            continue
        queue.remove(url)
        fetched[url] = {"at_epoch": time.time(), "status": "OK"}
        st = parse(page_text(body), url, _now(), today=today)
        store[url] = st or {"url": url, "status": UNMEASURED, "why": "no statement date"}
    fetched["_queue"] = queue
    _write_json(STATEMENTS, store)
    _write_json(FETCHED, fetched)
    good = [s for s in store.values() if isinstance(s, dict) and s.get("date")]
    scored = surprises(good)
    # What the desk can vouch for: no listed statement unread, and the most-recent index read
    # successfully at ok_epoch. Past that, a day without a statement is UNMEASURED.
    ok_epoch = (fetched.get(INDEXES[0]) or {}).get("ok_epoch")
    unread = sorted({*queue, *(u for u, st in store.items()
                               if not (isinstance(st, dict) and st.get("date")))})
    measured_until = datetime.fromtimestamp(float(ok_epoch), UTC) if ok_epoch else None
    windows = unread_windows(unread, fetched, store)
    blocked = [(date.fromisoformat(w["from"]) if w["from"] else None,
                date.fromisoformat(w["to"]) if w["to"] else None) for w in windows]
    rows = series_rows(scored, today=today, measured_until=measured_until, blocked=blocked)
    if rows:
        write_series(rows)
    if lane_ok is None:
        try:
            import llm_lab
            lane_ok = llm_lab._lane_ok
        except Exception:
            def lane_ok(_s: str, _f: str) -> bool:    # no lane policy, no permission
                return False
    donate = cells(scored, uni, lane_ok)
    known = set(_read_json(STATE_DIR / "donated.json", []) or [])
    fresh = [r for r in donate if r["cell_id"] not in known]
    if fresh:
        DONATE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = _now().replace(":", "").replace("-", "")[:15]
        _write_json(DONATE_DIR / f"discoveries_{stamp}.json",
                    {"source": "treasury_refunding", "generated_at": _now(),
                     "rule": "fixed-code extraction; pre-registered sides; the gauntlet judges",
                     "discoveries": fresh})
        _write_json(STATE_DIR / "donated.json", sorted(known | {r["cell_id"] for r in fresh}))
    measured = {sig: sum(1 for s in scored if isinstance(s.get(sig), (int, float)))
                for sig in SIGNALS}
    ran = read > 0 or any(p["status"] == "OK" for p in per)
    fresh_all = all(p["status"] == "FRESH" for p in per)
    # UNMEASURED IS A STATE (the #388 audit's rule, applied here too): no statement on record,
    # or none whose surprise could be measured, is never "RAN" or "FRESH".
    why = None
    if not good:
        why = "no refunding statement with a readable date is on record"
    elif not any(measured.values()):
        why = "no statement pair yields a measurable size or guidance surprise"
    state = ("DARK" if not ran and not fresh_all else UNMEASURED if why
             else "RAN" if ran else "FRESH")
    doc = {"generated_at": _now(), "state": state, **({"why": why} if why else {}),
           "indexes": per, "statements_read": read,
           "statements_on_record": len(good), "queued": len(queue),
           "measured": measured, "rows": len(rows),
           "measured_until": measured_until.isoformat() if measured_until else None,
           "blocking_zeros": windows[:20],
           "rows_unmeasured": sum(1 for r in rows if r["stamp_basis"] == UNMEASURED),
           "cells_total": len(donate),
           "cells_donated": len(fresh), "seconds": round(time.time() - started, 1),
           "not_yet_read": "TBAC minutes / primary-dealer expectations (surprise is vs "
                           "Treasury's own prior guidance until they are)",
           "pit": f"release-day row stamped {RELEASE_HOUR_UTC}:00 UTC (after the 08:30 ET "
                  f"release), held {POST_DAYS} days; first sight kept in retrieval_time"}
    _write_json(REPORT, doc)
    return doc
