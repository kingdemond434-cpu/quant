"""ENTSO-E TRANSPARENCY PLATFORM: HOURLY EU POWER LOAD AND GENERATION PER TYPE (DE-LU, FR).

A KEYED producer registered in `alt_proxies.run` (it rides the `alt_proxies` hourly leg; nothing
here is a second clock). Two data items per bidding zone, read through the documented RESTful
API at https://web-api.tp.entsoe.eu/api:

    Actual Total Load [6.1.A]                     documentType=A65, processType=A16
    Actual Generation per Production Type [16.1.B&C] documentType=A75, processType=A16

DE-LU is 10Y1001A1001A82H, FR is 10YFR-RTE------C. Hourly (or quarter-hourly) points are folded
per Brussels local day into daily series per zone: mean load, residual load (load minus wind
and solar), gas and nuclear generation, and the wind+solar share. They feed `exogenous_
conditioner` cells on XNGUSD, GER40, FRA40 and EURUSD (declared priors, untested; the gain test
decides).

KEY PLACEMENT: A HEADER, NEVER THE URL. The API user guide (Transparency Platform RESTful API
user guide, section 2.2 "Post Method", read 2026-10-20 at transparency.entsoe.eu/content/
static_content/Static%20content/web%20api/Guide_prod_backup_06_11_2024.html) documents a header
form: "Token has be present in http header. Key is SECURITY_TOKEN." (the GET form puts it in the
query as `securityToken`, which this module never uses). So every request is a POST of the
guide's `StatusRequest_MarketDocument` with the token in the `SECURITY_TOKEN` header, to a URL
that carries no credential. Redirects are REFUSED, never followed: urllib's default redirect
handler copies request headers to the next hop, which would hand the token to whatever host a
3xx names. Every error text, vaulted body and report line is scrubbed of the token (raw,
quote and quote_plus forms) before it is written. The token is read once per pass by
`read_token` (`libs.ops.env_keys.read_key("ENTSOE_API_TOKEN")` when that module is on the
branch, else the process environment), never printed, logged or stored. Absent, the pass reads
NEEDS_KEY, never zero. The guide page is the archived copy ENTSO-E links from its knowledge
base ("will not be updated"); the knowledge-base article "Request Methods" names GET and POST
and shows only GET in text. If the box ever sees POST refused, the GET/query form would need
`libs/data/keyed_sources.keyed_urlopen(secrets=(token,))` and an auditor's ruling; this module
does not fall back to it on its own.

TERMS: IDEAS_ONLY, FAIL CLOSED, AUDITOR RULING REQUESTED. `SOURCE_POLICY_ROW` quotes ENTSO-E's
own Terms of Use (29/03/2023, applicable from 01/11/2023) and its List of Data available for free
re-use (18/10/2023). The free list grants CC-BY 4.0, but neither Actual Total Load (6.1.A) nor
Actual Generation per Production Type (16.1.B&C) is on it; for data off the list the Terms of
Use (cl. 3.1) require the Data User to "seek the prior agreement of the holder of the copyright
or related right" "in case of a risk to cause prejudice to said right". Clause 3.1 also opens
"when using of the Transparency Platform Data for any purpose whatsoever" and clause 3.3 offers
an M2M interface to "all interested parties using automated tools". Whether internal research
use of the off-list items is permitted without the TSOs' agreement is a reading, not a quoted
permission, so the row is IDEAS_ONLY: fetched politely and measured, never live input -- no axis
or lake series is written, no cell is donated, and `entsoe_asof` answers IDEAS_ONLY. The flip to
LIVE is one row edit (`status`) after the auditor rules. Attribution, required by cl. 3.1 on
every use, is on every payload (`CREDIT`).

POINT IN TIME. Regulation 543/2013 sets the publication deadline for both items at "no later
than one hour after the operational period" (Art. 6.1(a), Art. 16.1(b)). Each point is
therefore available no earlier than max(its own response's fetch instant, point end + 1h); the
daily value is available no earlier than max(the fetch instant, the local day's last hour end +
1h) -- the latest of its points. `merge_vintages` (stamp_floor_fetch) applies exactly that, with
the response's own fetch time as the floor, and `series_asof` shows a cell only a value whose
stamp is at or before its decision time (and whose day is strictly before it).

FETCH. robots.txt of web-api.tp.entsoe.eu decides every pass (fail closed: unreadable is not
permission). DESK UA, retries=0. 401/403/429, an HTML/WAF body or a challenge is a hard stop held
for a PERSON in the shared hold shape (`hold_row`: key site:<host>, verdict, status, host, url
scrubbed, held_at, released_by null, released_at null, missed_growth). The guide's limit is
"Maximum of 400 requests are accepted per user per minute" (a 429 earns a 10-minute ban); this
pass spaces requests MIN_INTERVAL_S apart, far under it. A per-zone cursor walks forward in
whole local-day windows; a caught-up zone re-reads its last RECENT_D days. Outcomes: OK |
UNCHANGED (a re-read with nothing new) | PARTIAL:BUDGET (cursor kept) | FAILED:<cause> (an empty
pass is FAILED, never zero) | HELD:HARD_STOP | NEEDS_KEY | UNMEASURED (no fetch this pass).

CELLS. Judged by `libs.research.release_gain.release_gain`, whose Tier S bar is
`release_gain.tier_s_t_required` at each cell's own n and return shape; no bar literal lives
here. Every tested cell is charged (`alt_proxies._donate`, the null-trials ledger when nothing
is donated).

LIVE YIELD IS UNMEASURED until the trading box runs the alt_proxies leg with the token set: this
was written against fixtures in a container that cannot reach the host and holds no token.
"""
from __future__ import annotations

import contextlib
import importlib
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

SOURCE_ID = "entsoe_power"
API_URL = "https://web-api.tp.entsoe.eu/api"
HOST = "web-api.tp.entsoe.eu"
KEY_NAME = "ENTSOE_API_TOKEN"
TOKEN_HEADER = "SECURITY_TOKEN"  # noqa: S105 - the header NAME the guide gives, not a value
UNMEASURED = "UNMEASURED"
#: Bidding zone -> (EIC, series slug).
ZONES: dict[str, tuple[str, str]] = {"DE-LU": ("10Y1001A1001A82H", "de_lu"),
                                     "FR": ("10YFR-RTE------C", "fr")}
#: Data item -> (documentType, processType, the POST attribute naming the zone). Attribute
#: names follow the guide's POST example (OutBiddingZone_Domain for 6.1.A) and the GET
#: parameter names capitalised (in_Domain -> In_Domain for 16.1.B&C); a wrong name comes back as
#: the API's own acknowledgement, recorded (scrubbed), never as a zero.
DOCS: dict[str, tuple[str, str, str]] = {"load": ("A65", "A16", "OutBiddingZone_Domain"),
                                         "gen": ("A75", "A16", "In_Domain")}
#: Regulation 543/2013 publication deadlines: Art. 6.1(a) actual total load and Art. 16.1(b)
#: actual generation per type, both "no later than one hour after the operational period".
PUBLICATION_LAG: dict[str, timedelta] = {"load": timedelta(hours=1), "gen": timedelta(hours=1)}
DEPTH_D = 365                   # a zone's first pass reaches this far back
CHUNK_D = 31                    # local days per request window (the API allows one year)
RECENT_D = 3                    # a caught-up zone re-reads its last days for late points
MIN_INTERVAL_S = 2.0            # 30/min against a stated 400/min
BUDGET_S = 60.0                 # this producer's share of the alt_proxies leg
TIMEOUT_S = 60.0
MAX_BYTES = 32 * 1024 * 1024
HARD_STOP = (401, 403, 429)
#: polite_fetch.BLOCK_STATUS, so a hold reads the same as every other organ's.
BLOCK_VERDICT: dict[int, str] = {401: "NEEDS_KEY", 403: "METHOD_BLOCKED", 429: "METHOD_BLOCKED"}
#: ENTSO-E production types read (codes from the API's PsrType list).
PSR_SOLAR, PSR_WIND_OFF, PSR_WIND_ON = "B16", "B18", "B19"
PSR_GAS, PSR_NUCLEAR = "B04", "B14"
WIND_SOLAR = (PSR_SOLAR, PSR_WIND_OFF, PSR_WIND_ON)
ACK_NO_DATA = "999"

CREDIT = ("Source: ENTSO-E Transparency Platform (transparency.entsoe.eu), Actual Total Load "
          "[6.1.A] and Actual Generation per Production Type [16.1.B&C]; daily aggregates "
          "computed by the desk.")
TERMS_URL = ("https://transparencyplatform.zendesk.com/hc/en-us/articles/"
             "40921911218961-Legal-Terms-and-Conditions")
TERMS_OF_USE_URL = ("https://transparencyplatform.zendesk.com/hc/en-us/article_attachments/"
                    "40921869376401")
FREE_LIST_URL = ("https://transparencyplatform.zendesk.com/hc/en-us/article_attachments/"
                 "40921869379729")
API_GUIDE_URL = ("https://transparency.entsoe.eu/content/static_content/Static%20content/"
                 "web%20api/Guide_prod_backup_06_11_2024.html")
READ_AT = "2026-10-20"
IDEAS_ONLY = "IDEAS_ONLY"
#: The statuses under which this source is LIVE input (terms_fence's permitting status).
LIVE_STATUSES = frozenset({"API_PERMITTED"})

#: THIS SOURCE'S ROW, in `libs/data/terms_fence.SOURCE_POLICY`'s shape. terms_fence is not on
#: this branch's line (claude/novel-alt-p8); the row moves into SOURCE_POLICY unchanged when the
#: two meet, and until then this is its one register (alt_proxies.TERMS keeps its own sources).
SOURCE_POLICY_ROW: dict[str, dict[str, Any]] = {
    "entsoe_transparency": {
        "hosts": (HOST,), "status": IDEAS_ONLY, "key_env": (KEY_NAME,),
        "sources": (SOURCE_ID,), "routes": (SOURCE_ID,),
        "why": ("ENTSO-E's Terms of Use permit use 'for any purpose whatsoever' under conditions, "
                "but Actual Total Load (6.1.A) and Actual Generation per Production Type "
                "(16.1.B&C) are NOT on the List of Data available for free re-use (CC-BY 4.0); "
                "off-list data needs the copyright holder's prior agreement where re-use risks "
                "prejudice. No quoted clause permits automated internal-research use of these "
                "items outright, so FAIL CLOSED: fetched politely and measured, never live "
                "input, until the auditor rules"),
        "auditor_ruling_requested": (
            "Does cl. 3.1 ('for any purpose whatsoever') with cl. 3.3 (M2M for 'all interested "
            "parties using automated tools') permit internal, non-redistributed research use of "
            "6.1.A and 16.1.B&C without the TSOs' prior agreement? Yes -> status API_PERMITTED "
            "(LIVE). No -> stays IDEAS_ONLY; DE-LU load/generation also exist under CC BY 4.0 "
            "via SMARD (Bundesnetzagentur), a candidate LIVE substitute."),
        "key_placement": ("header SECURITY_TOKEN (guide s2.2 POST method, documented); never the "
                          "securityToken query parameter"),
        "attribution": CREDIT,
        "terms": {
            "url": TERMS_URL, "checked_at": READ_AT,
            "documents": {"terms_of_use": TERMS_OF_USE_URL, "free_reuse_list": FREE_LIST_URL,
                          "api_guide": API_GUIDE_URL},
            "clauses": {
                "use_3_1": ("In accordance with the applicable legislation, the Data User "
                            "shall, when using of the Transparency Platform Data for any "
                            "purpose whatsoever:"),
                "attribution_3_1": ("mention the ENTSO-E Transparency Platform as the source of "
                                    "publication of the data"),
                "prejudice_3_1": ("In case of a risk to cause prejudice to said right, the Data "
                                  "User shall seek the prior agreement of the holder of the "
                                  "copyright or related right."),
                "free_list_3_1": ("The Data User has responsibility to check this list before "
                                  "each re-use of the Transparency Platform Data."),
                "m2m_3_3": ("To facilitate access to all interested parties using automated "
                            "tools to gather data from the Transparency Platform,"),
                "free_list_licence": ("Creative Commons Attribution 4.0 International License "
                                      "(CC-BY 4.0)"),
                "free_list_attribution": ("by giving appropriate credit (attribution) to its "
                                          "source and indicating if they have made any "
                                          "changes"),
                "api_header": "Token has be present in http header. Key is SECURITY_TOKEN.",
                "api_rate": "Maximum of 400 requests are accepted per user per minute.",
            },
            "free_list_membership": {
                "Actual Total Load [6.1.A]": "ABSENT (list of 18/10/2023 rows 1-35)",
                "Actual Generation per Production Type [16.1.B&C]": "ABSENT",
            },
        },
        "missed_growth": {
            "delta_elogw": UNMEASURED,
            "cause": ("entsoe_power IDEAS_ONLY: DE-LU/FR load and generation-mix cells on "
                      "XNGUSD, GER40, FRA40, EURUSD are measured but never donated or read as "
                      "live input until the auditor rules on the ENTSO-E terms")},
    },
}
POLICY_KEY = "entsoe_transparency"


def policy() -> dict[str, Any]:
    return SOURCE_POLICY_ROW[POLICY_KEY]


def live_input() -> bool:
    """True only when the terms row permits live input. FAIL CLOSED."""
    return str(policy().get("status")) in LIVE_STATUSES


# ============================================================================ the secret
def read_token(environ: Mapping[str, str] | None = None) -> str:
    """The token, or ''. Through `libs.ops.env_keys.read_key` (registry, then process env) when
    that module is on the branch; the process environment otherwise. `environ` replaces both
    (tests). The value is returned to the caller and goes nowhere else."""
    if environ is not None:
        return str(environ.get(KEY_NAME) or "").strip()
    try:
        env_keys = importlib.import_module("libs.ops.env_keys")
    except ImportError:
        return str(os.environ.get(KEY_NAME) or "").strip()
    return str(env_keys.read_key(KEY_NAME) or "").strip()


def _forms(secrets: Iterable[str]) -> list[str]:
    out: set[str] = set()
    for s in secrets:
        if s:
            out.update({s, urllib.parse.quote(s, safe=""), urllib.parse.quote_plus(s)})
    return sorted(out, key=len, reverse=True)


def scrub(text: str, secrets: Iterable[str]) -> str:
    """`text` with every sent form of every secret replaced by <ENTSOE_API_TOKEN>."""
    out = str(text)
    for f in _forms(secrets):
        out = out.replace(f, f"<{KEY_NAME}>")
    return out


def scrub_bytes(body: bytes, secrets: Iterable[str]) -> bytes:
    out = body
    for f in _forms(secrets):
        out = out.replace(f.encode("utf-8"), f"<{KEY_NAME}>".encode())
    return out


# ============================================================================ the request
def request_xml(kind: str, eic: str, start: datetime, end: datetime, created: datetime) -> bytes:
    """The guide's StatusRequest_MarketDocument for one data item, zone and UTC interval."""
    doc, proc, dom = DOCS[kind]

    def t(x: datetime) -> str:
        return x.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")

    attrs = (("DocumentType", doc), ("ProcessType", proc), (dom, eic),
             ("TimeInterval", f"{t(start)}/{t(end)}"))
    comps = "".join(f"<AttributeInstanceComponent><attribute>{a}</attribute>"
                    f"<attributeValue>{v}</attributeValue></AttributeInstanceComponent>"
                    for a, v in attrs)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<StatusRequest_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-5:'
            'statusrequestdocument:4:0">'
            f"<mRID>desk-{doc}-{eic}-{t(start)}</mRID><type>A59</type>"
            '<sender_MarketParticipant.mRID codingScheme="A01">10X1001A1001A450'
            "</sender_MarketParticipant.mRID>"
            "<sender_MarketParticipant.marketRole.type>A07</sender_MarketParticipant.marketRole"
            ".type>"
            '<receiver_MarketParticipant.mRID codingScheme="A01">10X1001A1001A450'
            "</receiver_MarketParticipant.mRID>"
            "<receiver_MarketParticipant.marketRole.type>A32</receiver_MarketParticipant."
            "marketRole.type>"
            f"<createdDateTime>{created.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}"
            f"</createdDateTime>{comps}</StatusRequest_MarketDocument>").encode()


class RedirectRefused(urllib.error.HTTPError):
    """A 3xx answer. Never followed: the next hop would receive the token header."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any,
                         newurl: str) -> None:
        raise RedirectRefused(req.full_url, code, f"redirect refused ({code})", headers, fp)


def _ua(ap: Any) -> str:
    """The desk's honest UA: polite_fetch.DESK_UA where it exists, else alt_proxies.UA (the
    same string, pinned there until polite_fetch carries it)."""
    with contextlib.suppress(ImportError, AttributeError):
        from libs.data import polite_fetch
        return str(polite_fetch.DESK_UA)  # type: ignore[attr-defined,unused-ignore]
    return str(ap.UA)


Poster = Callable[[str, bytes, dict[str, str]], tuple[bytes, str]]


def http_post(url: str, body: bytes, headers: dict[str, str]) -> tuple[bytes, str]:
    """One POST, no retry, redirects refused. Raises HTTPError / URLError on failure."""
    ctx = None
    with contextlib.suppress(Exception):
        from libs.data.polite_fetch import ssl_context
        ctx = ssl_context()
    opener = urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=ctx))
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with opener.open(req, timeout=TIMEOUT_S) as fh:
        return fh.read(MAX_BYTES), str(fh.headers.get("Content-Type") or "")


# ============================================================================ the answer
@dataclass(frozen=True)
class Series:
    psr: str                     # production type for A75, "" for load
    consumption: bool            # an A75 series measuring consumption (pumped storage load)
    points: tuple[tuple[datetime, datetime, float], ...]   # (start, end, MW)


@dataclass(frozen=True)
class Answer:
    kind: str                    # doc | ack | not_xml
    series: tuple[Series, ...] = ()
    reason: str = ""
    text: str = ""


_DTD = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.I)
_RES = re.compile(r"^PT(\d+)M$")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el: ET.Element, name: str) -> ET.Element | None:
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _find_all(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el.iter() if _local(c.tag) == name]


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _iso(s: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def parse_answer(body: bytes) -> Answer:
    """A GL_MarketDocument (TimeSeries/Period/Point), an Acknowledgement_MarketDocument, or
    not XML at all (a WAF or HTML page). A body with a DTD or entity is refused unparsed."""
    head = body.lstrip()[:1]
    if head != b"<" or _DTD.search(body[:4096]) or b"<html" in body[:2048].lower():
        return Answer("not_xml")
    try:
        root = ET.fromstring(body)  # DTD/entities refused above
    except ET.ParseError:
        return Answer("not_xml")
    name = _local(root.tag)
    if name.startswith("Acknowledgement"):
        reason = _find_all(root, "Reason")
        code = _text(_child(reason[0], "code")) if reason else ""
        txt = _text(_child(reason[0], "text")) if reason else ""
        return Answer("ack", reason=code, text=txt)
    out: list[Series] = []
    for ts in _find_all(root, "TimeSeries"):
        psr_el = [e for e in ts.iter() if _local(e.tag) == "psrType"]
        psr = _text(psr_el[0]) if psr_el else ""
        consumption = _child(ts, "outBiddingZone_Domain.mRID") is not None and bool(psr)
        pts: list[tuple[datetime, datetime, float]] = []
        for per in [c for c in ts if _local(c.tag) == "Period"]:
            ti = _child(per, "timeInterval")
            start = _iso(_text(_child(ti, "start"))) if ti is not None else None
            m = _RES.match(_text(_child(per, "resolution")))
            if start is None or m is None:
                continue
            step = timedelta(minutes=int(m.group(1)))
            for p in [c for c in per if _local(c.tag) == "Point"]:
                try:
                    pos = int(_text(_child(p, "position")))
                    q = float(_text(_child(p, "quantity")))
                except ValueError:
                    continue
                if pos < 1 or not math.isfinite(q):
                    continue
                s = start + step * (pos - 1)
                pts.append((s, s + step, q))
        out.append(Series(psr, consumption, tuple(pts)))
    return Answer("doc", series=tuple(out))


def point_available_at(kind: str, end: datetime, fetched_at: datetime) -> datetime:
    """THE PIT RULE FOR ONE POINT: late-biased, max(its own response's fetch instant, the end of
    its operational period + the regulation's publication deadline)."""
    return max(fetched_at, end + PUBLICATION_LAG[kind])


# ============================================================================ the fold
def _local_midnight_utc(d: date, cet_offset_h: Callable[[datetime], int]) -> datetime:
    guess = datetime(d.year, d.month, d.day, tzinfo=UTC)
    return guess - timedelta(hours=cet_offset_h(guess - timedelta(hours=1)))


def day_bounds(d: date, cet_offset_h: Callable[[datetime], int]) -> tuple[datetime, datetime]:
    """[start, end) of Brussels local day `d`, in UTC."""
    return (_local_midnight_utc(d, cet_offset_h),
            _local_midnight_utc(d + timedelta(days=1), cet_offset_h))


def _hourly(points: Iterable[tuple[datetime, datetime, float]]) -> dict[int, float]:
    """UTC hour index -> mean MW over the points that start inside it."""
    acc: dict[int, list[float]] = {}
    for s, _e, q in points:
        acc.setdefault(int(s.timestamp() // 3600), []).append(q)
    return {h: sum(v) / len(v) for h, v in acc.items()}


def fold_days(slug: str, load: Answer | None, gen: Answer | None, days: Iterable[date],
              cet_offset_h: Callable[[datetime], int]) -> list[tuple[str, date, float]]:
    """(series, local day, value) for every COMPLETE local day: a component is published for a
    day only when every UTC hour of that day (23, 24 or 25) carries it. A production type that
    covers part of a day makes the day's generation incomplete; one absent all day is absent
    (never zero). Derived series need every component they use."""
    load_h = _hourly(p for s in (load.series if load else ()) for p in s.points)
    gen_h: dict[str, dict[int, float]] = {}
    for s in (gen.series if gen else ()):
        if s.consumption or not s.psr:
            continue
        cur = gen_h.setdefault(s.psr, {})
        for h, v in _hourly(s.points).items():
            cur[h] = cur.get(h, 0.0) + v
    out: list[tuple[str, date, float]] = []
    for d in days:
        a, b = day_bounds(d, cet_offset_h)
        hours = list(range(int(a.timestamp() // 3600), int(b.timestamp() // 3600)))
        ld = [load_h[h] for h in hours if h in load_h] if load_h else []
        load_ok = len(ld) == len(hours) and bool(hours)
        if load_ok:
            out.append((f"{slug}_load_mean", d, round(sum(ld) / len(ld), 3)))
        present = {p: m for p, m in gen_h.items() if any(h in m for h in hours)}
        gen_ok = bool(present) and all(all(h in m for h in hours) for m in present.values())
        if not gen_ok:
            continue
        mean = {p: sum(m[h] for h in hours) / len(hours) for p, m in present.items()}
        total = sum(mean.values())
        ws = sum(mean.get(p, 0.0) for p in WIND_SOLAR) if any(
            p in mean for p in WIND_SOLAR) else None
        if PSR_GAS in mean:
            out.append((f"{slug}_gen_gas", d, round(mean[PSR_GAS], 3)))
        if PSR_NUCLEAR in mean:
            out.append((f"{slug}_gen_nuclear", d, round(mean[PSR_NUCLEAR], 3)))
        if ws is not None and total > 0:
            out.append((f"{slug}_ren_share", d, round(100.0 * ws / total, 4)))
        if ws is not None and load_ok:
            resid = [load_h[h] - sum(gen_h.get(p, {}).get(h, 0.0) for p in WIND_SOLAR)
                     for h in hours]
            out.append((f"{slug}_residual_load", d, round(sum(resid) / len(resid), 3)))
    return out


# ============================================================================ the source row
#: Declared priors, untested (the gain test decides and charges every cell). Load is a
#: same-day activity print for the zone's index and the euro; residual load (what wind and solar
#: leave to dispatchable plant) and gas burn are marginal gas demand; French nuclear output
#: displaces gas at the margin; a high wind+solar share displaces it too.
SERIES_INSTRUMENTS: dict[str, dict[str, int]] = {
    "de_lu_load_mean": {"GER40": 1, "EURUSD": 1},
    "fr_load_mean": {"FRA40": 1, "EURUSD": 1},
    "de_lu_residual_load": {"XNGUSD": 1},
    "fr_residual_load": {"XNGUSD": 1},
    "de_lu_gen_gas": {"XNGUSD": 1},
    "fr_gen_nuclear": {"XNGUSD": -1},
    "de_lu_ren_share": {"XNGUSD": -1},
}
SIGNAL_SERIES = tuple(SERIES_INSTRUMENTS)


def rule_for(cet_offset_h: Callable[[datetime], int]) -> Callable[[date], datetime]:
    def rule(period: date) -> datetime:
        """Local day `period` is complete one hour after its last hour ends (the deadline of
        its latest point); `stamp_floor_fetch` raises it to the read when later."""
        return day_bounds(period, cet_offset_h)[1] + max(PUBLICATION_LAG.values())
    return rule


def make_source(ap: Any) -> Any:
    return ap.Source(
        id=SOURCE_ID, name="ENTSO-E actual load and generation per type, DE-LU and FR",
        url=API_URL, region="EU", language="en", cadence="daily", parse=None,
        rule=rule_for(ap.cet_offset_h), stamp_floor_fetch=True, transform="anomaly_daily",
        instruments={}, series_instruments=dict(SERIES_INSTRUMENTS),
        signal_series=SIGNAL_SERIES, key_env=KEY_NAME,
        terms="confirmed" if live_input() else "to_confirm",
        mechanism=("metered load and the generation mix are published within an hour of each "
                   "hour; gas burn and residual load move European gas demand, and load tracks "
                   "industrial activity, weeks before any survey or official print"),
        payer="gas and index holders pricing European demand from monthly data and weather",
        constraint="official activity and gas-demand statistics are monthly and late",
        licence=f"ENTSO-E Terms of Use; {policy()['status']} (see SOURCE_POLICY_ROW)",
        source_culture="EU/en", participant_structure=("physical_flow", "institutional"),
        failure_mode_hypothesis=("fails when load moves with temperature already in the "
                                 "forecast, or when LNG supply rather than burn sets the gas "
                                 "price"),
        crowding_prior="medium",
        note="keyed (ENTSOE_API_TOKEN, SECURITY_TOKEN header); hourly items folded to days")


# ============================================================================ holds
def hold_row(status: int | str, url: str, cause: str, now: datetime,
             secrets: Iterable[str] = ()) -> dict[str, Any]:
    """THE SHARED PERSON-HELD RECORD (polite_fetch.hold_record's shape) plus the fields
    alt_proxies.held_by_person reads (`since`, `cause`, `release`). No expiry, no retry clock."""
    verdict = (BLOCK_VERDICT.get(status, "METHOD_BLOCKED") if isinstance(status, int)
               else "METHOD_BLOCKED")
    safe_url = scrub(url, secrets)[:300]
    safe_cause = scrub(cause, secrets)[:300]
    mg = {"delta_elogw": UNMEASURED,
          "cause": (f"{SOURCE_ID} held after {safe_cause}: no load or generation rows until a "
                    "person releases the hold")}
    return {"key": f"site:{HOST}", "verdict": verdict,
            "status": status if isinstance(status, int) else (status or None),
            "host": HOST, "url": safe_url, "held_at": now.timestamp(),
            "released_by": None, "released_at": None,
            "since": now.isoformat(timespec="seconds"), "cause": safe_cause,
            "waits_for": "a person",
            "release": ("a person sets released_by and released_at on sources.entsoe_power."
                        "hard_stop in desks/mt5/data/alt_proxies/state.json (or deletes it)"),
            "missed_growth": mg}


# ============================================================================ the pass
@dataclass
class Window:
    zone: str
    first: date
    last: date


def _windows(cursor: str | None, now: datetime, zone: str) -> Window:
    yesterday = (now - timedelta(days=1)).date()
    try:
        since = date.fromisoformat(str(cursor))
    except ValueError:
        since = (now - timedelta(days=DEPTH_D)).date()
    since = min(since, yesterday)
    return Window(zone, since, min(since + timedelta(days=CHUNK_D - 1), yesterday))


def collect(ap: Any, paths: Any, src: Any, sst: dict[str, Any], store: dict[str, Any],
            now: datetime, *, fetch: bool, fixtures: Path | None, deadline: float,
            poster: Poster = http_post,
            getter: Callable[[str], tuple[bytes, str]] | None = None,
            environ: Mapping[str, str] | None = None,
            sleep: Callable[[float], None] = time.sleep,
            clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> dict[str, Any]:
    """Fetch (or read fixtures), fold, merge into the vintage store. Returns the pass record."""
    out: dict[str, Any] = {"requests": 0, "fetched": 0, "parsed": 0, "errors": [],
                           "merge": {"added": 0, "revised": 0}, "unmeasured_windows": []}
    secrets: tuple[str, ...] = ()

    def fail(cause: str, *, hold: int | str | None = None) -> dict[str, Any]:
        cause = scrub(cause, secrets)
        out["errors"].append(cause)
        out["outcome"] = out["status"] = f"FAILED:{cause.split(':', 1)[0]}"
        out["why"] = cause
        if hold is not None:
            sst["hard_stop"] = hold_row(hold, API_URL, cause, now, secrets)
            out["hard_stop"] = dict(sst["hard_stop"])
        return out

    def take(slug: str, load: Answer | None, gen: Answer | None, days: list[date],
             seen: datetime) -> None:
        rows = fold_days(slug, load, gen, days, ap.cet_offset_h)
        obs = [ap.Obs(s, d, v) for s, d, v in rows]
        out["parsed"] += len(obs)
        m = ap.merge_vintages(store, src, obs, seen)
        out["merge"]["added"] += m["added"]
        out["merge"]["revised"] += m["revised"]

    if fixtures is not None:
        for zone, (_eic, slug) in ZONES.items():
            fx: dict[str, Answer] = {}
            for kind in DOCS:
                fp = fixtures / f"{SOURCE_ID}.{slug}.{kind}.xml"
                if fp.exists():
                    fx[kind] = parse_answer(fp.read_bytes())
            series = [p for a in fx.values() if a.kind == "doc"
                      for s in a.series for p in s.points]
            if not series:
                continue
            first = min(p[0] for p in series)
            last = max(p[0] for p in series)
            days = list(_days(ap.cet_local(first).date(), ap.cet_local(last).date()))
            take(slug, _doc(fx.get("load")), _doc(fx.get("gen")), days, now)
            out["fetched"] += 1
            out.setdefault("zones", []).append(zone)
        if not out["parsed"]:
            return fail("EMPTY: no fixture folded to a complete local day")
        out["outcome"] = "OK"
        return out
    if not fetch:
        out["why"] = "no fetch this pass (--no-fetch): UNMEASURED, not zero"
        out["outcome"] = UNMEASURED
        return out
    if ap.held_by_person(sst, now, out):
        return out
    token = read_token(environ)
    if not token:
        out["outcome"] = out["status"] = f"NEEDS_KEY:{KEY_NAME}"
        out["why"] = f"{KEY_NAME} is not set on this machine: a named state, never zero"
        out["missed_growth"] = {"delta_elogw": UNMEASURED,
                                "cause": f"{SOURCE_ID} not read: {KEY_NAME} absent"}
        return out
    secrets = (token,)
    rb = ap.robots_verdict(API_URL, getter or ap.http_get)
    out["robots"] = rb
    if rb["verdict"] == "hard_stop":
        rcode = re.search(r"(\d{3})", str(rb.get("note")))
        return fail(f"HARD_STOP: {rb['note']}", hold=int(rcode.group(1)) if rcode else "ROBOTS")
    if rb["verdict"] != "allow":
        return fail(f"ROBOTS_{rb['verdict'].upper()}: {rb['note']}")
    delay = max(MIN_INTERVAL_S, float(rb.get("crawl_delay") or 0.0))
    headers = {"User-Agent": _ua(ap), "Content-Type": "application/xml",
               "Accept": "application/xml, text/xml", TOKEN_HEADER: token}
    cursors: dict[str, str] = sst.setdefault("cursor", {})
    yesterday = (now - timedelta(days=1)).date()
    done: dict[str, bool] = dict.fromkeys(ZONES, False)
    first_req = True
    cut = False
    for zone, (eic, slug) in ZONES.items():
        while not done[zone] and not cut:
            w = _windows(cursors.get(zone), now, zone)
            a = day_bounds(w.first, ap.cet_offset_h)[0]
            b = day_bounds(w.last, ap.cet_offset_h)[1]
            got: dict[str, Answer] = {}
            seen: datetime | None = None
            for kind in DOCS:
                if not first_req:
                    if time.monotonic() + delay > deadline:
                        out["errors"].append(f"budget reached at {zone} {kind} {w.first}: the "
                                             "rest is owed to the next pass (cursor kept)")
                        cut = True
                        break
                    sleep(delay)
                first_req = False
                out["requests"] += 1
                try:
                    body, _ctype = poster(API_URL, request_xml(kind, eic, a, b, now), headers)
                except RedirectRefused as exc:
                    return fail(f"REDIRECT_REFUSED: HTTP {exc.code} on {zone} {kind} (the "
                                "token header is never sent to another hop)")
                except urllib.error.HTTPError as exc:
                    code = int(exc.code)
                    with contextlib.suppress(Exception):
                        exc.close()
                    if code in HARD_STOP:
                        return fail(f"HARD_STOP: HTTP {code} on {zone} {kind}", hold=code)
                    return fail(f"HTTP_ERROR: HTTP {code} on {zone} {kind}")
                except Exception as exc:
                    return fail(f"TRANSPORT: {type(exc).__name__}: {str(exc)[:120]}")
                at = clock()
                seen = at if seen is None else max(seen, at)
                out["fetched"] += 1
                ans = parse_answer(body)
                if ans.kind == "not_xml":
                    return fail(f"WAF: a non-XML body on {zone} {kind}", hold="WAF")
                if ans.kind == "ack" and ans.reason != ACK_NO_DATA:
                    return fail(f"ACK_{ans.reason or 'UNKNOWN'}: {ans.text[:160]}")
                if ans.kind == "ack":
                    win = {"zone": zone, "item": kind, "from": w.first.isoformat(),
                           "to": w.last.isoformat(), "status": UNMEASURED,
                           "why": "acknowledgement 999: no matching data for this window",
                           "at": now.isoformat(timespec="seconds")}
                    out["unmeasured_windows"].append(win)
                with contextlib.suppress(Exception):
                    ap.vault(paths, src, scrub_bytes(body, secrets), API_URL,
                             "application/xml", at)
                got[kind] = ans
            if cut:
                break
            assert seen is not None
            take(slug, _doc(got.get("load")), _doc(got.get("gen")),
                 list(_days(w.first, w.last)), seen)
            if w.last >= yesterday:
                done[zone] = True
                cursors[zone] = (yesterday - timedelta(days=RECENT_D - 1)).isoformat()
            else:
                cursors[zone] = (w.last + timedelta(days=1)).isoformat()
    out["caught_up"] = done
    if not out["parsed"]:
        if cut:
            return fail("BUDGET: the budget ended before any window completed (cursor kept)")
        if out["fetched"] and len(out["unmeasured_windows"]) >= out["fetched"]:
            return fail("ALL_WINDOWS_EMPTY: every answer was acknowledgement 999")
        return fail("EMPTY: the API answered with no complete local day" if out["fetched"]
                    else "BUDGET: no request completed inside the budget")
    if not all(done.values()):
        behind = ",".join(z for z, ok in done.items() if not ok)
        out["outcome"] = out["status"] = "PARTIAL:BUDGET"
        out["why"] = f"budget cut before {behind} caught up (cursor kept)"
        return out
    out["outcome"] = out["status"] = ("UNCHANGED" if not (out["merge"]["added"]
                                                          or out["merge"]["revised"]) else "OK")
    return out


def _doc(a: Answer | None) -> Answer | None:
    return a if a is not None and a.kind == "doc" else None


def _days(a: date, b: date) -> Iterable[date]:
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


# ============================================================================ cells
def gain_tests(ap: Any, paths: Any, src: Any, pts: dict[str, list[dict[str, Any]]]
               ) -> dict[str, dict[str, Any]]:
    """Every (series, mapped instrument) cell the two-lane order allows, judged by
    release_gain at the Tier S bar `release_gain.tier_s_t_required` gives THAT cell's n and
    return shape. The bar is recorded per cell; a PASS whose |t| sits under the canonical bar at
    its n (never possible through release_gain, checked anyway) is demoted, never promoted."""
    from libs.research.release_gain import release_gain, tier_s_t_required
    cells = [(s, sym) for s in src.signal_series if pts.get(s)
             for sym in src.instruments_for(s) if ap.may_mint(sym)]
    out: dict[str, dict[str, Any]] = {}
    closes: dict[str, Any] = {}
    for series, sym in cells:
        key = f"{SOURCE_ID}|{series}|{sym}"
        if sym not in closes:
            closes[sym] = ap._bars_close(paths, sym)
        close = closes[sym]
        if close is None:
            out[key] = {"verdict": UNMEASURED, "why": f"no {sym}_H1 bars on this box"}
            continue
        ev = [(p["available_time"], float(p["surprise_z"])) for p in pts[series]
              if p.get("surprise_z") is not None]
        res = release_gain(ev, close, horizon_bars=ap.HORIZON_BARS).as_dict()
        n = int(res.get("n") or 0)
        bar = res.get("t_bar")
        if bar is None:
            bar = tier_s_t_required(n)
        res["t_bar"] = bar if bar is None or math.isfinite(float(bar)) else None
        res["t_bar_judge"] = "libs.research.release_gain.tier_s_t_required"
        if res.get("verdict") == "PASS" and not (
                res.get("t") is not None and abs(float(res["t"])) >= tier_s_t_required(n)):
            res["verdict"] = "FAIL"
            res["why"] = f"|t| under tier_s_t_required({n})"
        res["cells_in_family"] = len(cells)
        res["live_input"] = live_input()
        out[key] = res
    return out


def cells(ap: Any, src: Any, gains: dict[str, dict[str, Any]], now: datetime
          ) -> list[dict[str, Any]]:
    """PASSING cells as exogenous_conditioner recipes (alt_proxies.direct_cells' shape), each
    carrying the attribution and its live-input standing."""
    out: list[dict[str, Any]] = []
    for key, g in sorted(gains.items()):
        if g.get("verdict") != "PASS" or not g.get("ic"):
            continue
        _sid, series, sym = key.split("|")
        if not ap.may_mint(sym):
            continue
        side = 1 if float(g["ic"]) > 0 else -1
        lake = ap.lake_file(src, series)
        out.append({
            "source": SOURCE_ID, "kind": "hypothesis", "symbol": sym, "symbols": [sym],
            "family": ap.DIRECT_FAMILY, "url": "",
            "params": {"source": lake, "signal": "surprise_z", "transform": "level_z",
                       "threshold": 1.0, "side_when_high": side, "lag_hours": 24,
                       "ttl_bars": ap.HORIZON_BARS},
            "cell": f"{sym}.{ap.DIRECT_FAMILY}.{lake}",
            "title": f"{src.name}: {series} surprise -> {sym} ({'+' if side > 0 else '-'})"[:120],
            "available_time": now.isoformat(timespec="seconds"),
            "event_time": now.isoformat(timespec="seconds"),
            **ap._meta(src), "prior_sign": src.instruments_for(series).get(sym),
            "falsifier": (f"IC of {series} surprise on {sym} {ap.HORIZON_BARS}-bar post-release "
                          "returns no longer beats the shifted-release placebo"),
            "evidence": {k: g.get(k) for k in ("ic", "n", "t", "t_bar", "t_bar_judge", "p_t",
                                               "p_placebo", "min_detectable_ic", "why")},
            "credit": CREDIT, "live_input": live_input(), "terms_status": policy()["status"],
            "provenance": {"organ": "entsoe_power", "registered_in": "alt_proxies",
                           "series": series, "terms_row": POLICY_KEY}})
    return out


# ============================================================================ the producer
def run_pass(ap: Any, paths: Any, state: dict[str, Any], now: datetime, *, fetch: bool,
             fixtures: Path | None, deadline: float, dry_run: bool = False,
             donate: bool = True, poster: Poster = http_post,
             getter: Callable[[str], tuple[bytes, str]] | None = None,
             environ: Mapping[str, str] | None = None,
             sleep: Callable[[float], None] = time.sleep,
             clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> dict[str, Any]:
    """One pass: collect, build PIT points, judge cells, charge trials, donate only when LIVE.
    `ap` is the alt_proxies module that registered this producer (its store, PIT and gain
    machinery are used as they are; nothing is copied)."""
    src = make_source(ap)
    sst = state.setdefault("sources", {}).setdefault(SOURCE_ID, {})
    store_p = paths.obs_dir / f"{SOURCE_ID}.json"
    store = ap._read_json(store_p, {})
    rec = collect(ap, paths, src, sst, store, now, fetch=fetch, fixtures=fixtures,
                  deadline=deadline, poster=poster, getter=getter, environ=environ,
                  sleep=sleep, clock=clock)
    if not dry_run:
        ap._atomic(store_p, store)
    rec["store_rows"] = len(store)
    pts = ap.build_points(src, store) if store else {}
    rec["series"] = {k: len(v) for k, v in sorted(pts.items())}
    live = live_input()
    gains = gain_tests(ap, paths, src, pts) if pts and fixtures is None else {}
    tested = ("PASS", "FAIL", "UNDERPOWERED")
    n_tested = sum(1 for g in gains.values() if g.get("verdict") in tested)
    passing = cells(ap, src, gains, now)
    donation: dict[str, Any] = {"donated": 0}
    if donate and not dry_run:
        donation = ap._donate(paths, SOURCE_ID, passing if live else [], n_tested,
                              {ap.DIRECT_FAMILY: n_tested}, now)
    if live and pts and not dry_run:
        ap._atomic(paths.axes / f"alt_{SOURCE_ID}.json", {**ap.axis_doc(src, pts, now),
                                                         "credit": CREDIT})
        rec["lake_series"] = ap.write_lake_series(paths, src, pts)
    return {
        **rec, "id": SOURCE_ID, "credit": CREDIT,
        "terms": {"row": POLICY_KEY, "status": policy()["status"], "live_input": live,
                  "missed_growth": None if live else policy()["missed_growth"]},
        "key": {"name": KEY_NAME, "placement": f"header {TOKEN_HEADER}",
                "present": bool(read_token(environ)) if fixtures is None and fetch else None},
        "pit_rule": ("point available = max(response fetch instant, point end + 1h "
                     "(Reg. 543/2013 Art. 6.1(a), 16.1(b))); daily value = max(fetch, local day "
                     "end + 1h)"),
        "gain_tests": gains, "n_cells_tested": n_tested,
        "cells": {"n_passing": len(passing), "donation": donation,
                  "rule": ("passing cells donate only when the terms row is LIVE; every tested "
                           "cell is charged either way"),
                  "passing": passing},
        "live_yield": ("UNMEASURED until the trading box runs the alt_proxies leg with "
                       f"{KEY_NAME} set"),
    }


def entsoe_asof(ap: Any, decision_at: datetime, store_path: Path | None = None
                ) -> dict[str, Any]:
    """The consumer: latest daily values KNOWN at `decision_at` (alt_proxies.series_asof, the
    one PIT reader). IDEAS_ONLY answers with no values: never live input."""
    if not live_input():
        return {"status": IDEAS_ONLY, "series": {}, "credit": CREDIT,
                "why": "ENTSO-E terms row is IDEAS_ONLY: never read as live input"}
    got = ap.series_asof(SOURCE_ID, decision_at, store_path)
    return {**got, "credit": CREDIT}
