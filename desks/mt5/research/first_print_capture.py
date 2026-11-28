"""FIRST-PRINT CAPTURE: the value each scheduled US macro release FIRST published, kept apart
from every later revision, read from the primary publisher and stamped at the release time.

WHY (row 45 of the 2026-11-18 build check). The desk's only first-print path was ALFRED's
"initial release" view inside `futures_state`, and FRED/ALFRED are refused for every automated
fetch. A publisher's API serves only its CURRENT vintage, so the only way to own a first print
without ALFRED is to be there when it lands and write it down before the next revision replaces
it. This leg does that, hourly.

WHAT IT WRITES, per series, under `data/lake/first_prints/<series>/` (box-local, gitignored):

    first_prints.jsonl  one row per period, written ONCE, the first value ever seen for it.
                        Never rewritten, never deleted: a revision cannot reach it.
    revisions.jsonl     one row each time a later pass sees a DIFFERENT value for a period
                        that already has a first print (vintage 2, 3, ...).
    baseline.jsonl      the periods already published the first time the series was read. Their
                        vintage is unknown (the API may already have revised them), so they are
                        NOT first prints and are kept out of first_prints.jsonl on purpose.

THE STAMP, AND WHY IT CANNOT LOOK AHEAD. A publisher API carries no release instant. Each first
print carries two times:

    seen_at     when this leg first read the value. Always at or after the true release.
    release_at  the series' scheduled New York slot (`at`, e.g. 08:30) on the latest weekday at
                or before `seen_at`. Every release of a series in the grounds file comes out at
                that slot on a weekday, so the true release is on that day or earlier, and the
                stamp is never earlier than the truth (late is safe; early would be lookahead).
                A slot that would fall on or before the period's own end is impossible for a
                release, and the stamp falls back to `seen_at`.

`available_at` = `seen_at` is the conservative instant a bar may use the number.

SOURCES (`desks/mt5/data/first_print_sources.json` holds the robots and terms record):
  * BLS API v2 with `BLS_API_KEY`, read only through `libs.ops.env_keys.read_key` and the
    credential registry's accepted names, never printed; without it, the keyless API v1, at most
    once per 110 minutes so the 25-a-day v1 limit is never reached.
  * Census EITS (keyless). DOL and BEA are recorded NOT_BUILT with the reason (no keyless
    machine route that carries the headline).
  No FRED, no ALFRED. robots.txt is read live with this leg's own agent before any data request;
  an unreadable robots file (an HTML page included) refuses the publisher for the pass.
  401, 403, 451 or a WAF wall hold the publisher HELD_UNTIL_RELEASED (a person sets `release`
  in data/lake/first_prints/_fetch_state.json); a 429 holds it for 24 hours.

Artifact: `desks/mt5/reports/FIRST_PRINT_CAPTURE.json`. Not money path: nothing here sizes or
places an order.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE_ID = "first_print_capture"
UNMEASURED = "UNMEASURED"
NY = ZoneInfo("America/New_York")
GROUNDS = DESK / "data" / "first_print_sources.json"
LAKE = ROOT / "data" / "lake" / "first_prints"
REPORT = DESK / "reports" / "FIRST_PRINT_CAPTURE.json"
FETCH_STATE = "_fetch_state.json"

ROBOTS_AGENT = "quant-desk-research"
HONEST_UA = f"{ROBOTS_AGENT}/1.0 (first_print_capture; research; honours robots.txt)"
TIMEOUT = 30.0
MAX_BYTES = 4 * 1024 * 1024
#: The fetch law (#1300, #1327): a refusal of who we are -- 401, 403, 451 or a WAF wall -- is
#: HELD_UNTIL_RELEASED, persisted in _fetch_state.json and lifted only when a person sets the
#: publisher's `release` field there. A 429 asks us to slow down and alone gets a timed hold.
HELD_CODES = frozenset({401, 403, 451})
TIMED_CODES = frozenset({429})
HOLD = timedelta(hours=24)
HELD_UNTIL_RELEASED = "HELD_UNTIL_RELEASED"
_WALL = re.compile(r"(?i)incapsula|captcha|cf-chl|challenge-platform|access denied|"
                   r"are you a robot|request rejected|_Incapsula_Resource")
#: BLS v1 (keyless) allows 25 queries a day; one request per 110 minutes is at most 14.
BLS_V1_MIN_GAP = timedelta(minutes=110)
#: The registered key's 500/day is shared with the keyed_sources leg; hourly is 24.
DEFAULT_MIN_GAP = timedelta(minutes=50)
BLS_V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
CENSUS = "https://api.census.gov/data/"
BLS_KEY_VAR = "BLS_API_KEY"


class Refused(Exception):
    """'<STATUS>:<why>' -- a publisher this pass may not or could not read."""


class Wall(Exception):
    """A WAF / challenge page where the API's JSON should be: held until released."""
    code = "WALL"


def _looks_like_html(body: bytes) -> bool:
    """The same test as #1335: a body starting with '<', or holding <html / <!doctype."""
    head = body[:4096].lstrip().lower()
    return head.startswith(b"<") or b"<html" in head or b"<!doctype" in head


def _check_api_body(body: bytes, who: str) -> bytes:
    """A JSON API answering HTML is a wall (held until released) or a shape error."""
    if _looks_like_html(body):
        text = body[:8192].decode("utf-8", "replace")
        if _WALL.search(text):
            raise Wall(f"{who} answered a challenge/WAF page")
        raise Refused(f"SHAPE:{who} answered HTML where JSON was expected")
    return body


@dataclass(frozen=True)
class Obs:
    series: str          # grounds-file id, e.g. bls_payrolls
    period: str          # YYYY-MM
    value: float
    flags: tuple[str, ...] = ()


# ------------------------------------------------------------------------------ small helpers
def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(d: datetime) -> str:
    return d.astimezone(UTC).isoformat(timespec="seconds")


def _t(s: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    os.replace(tmp, p)


def _jsonl(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with contextlib.suppress(OSError):
        for line in p.read_text("utf-8").splitlines():
            with contextlib.suppress(ValueError):
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
    return out


def _append(p: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def _num(s: Any) -> float | None:
    try:
        v = float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def period_end(period: str) -> date:
    y, m = (int(x) for x in period.split("-"))
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return nxt - timedelta(days=1)


# ---------------------------------------------------------------------------------- the stamp
def release_instant(seen: datetime, at: str, period: str) -> tuple[datetime, str]:
    """(release_at, basis): the scheduled slot on the latest weekday at or before `seen`.

    Never later than `seen` and, for a series released at `at` on a weekday, never earlier than
    the true release -- so it carries no lookahead. A slot on or before the period's own end is
    impossible for a release of that period: fall back to `seen`."""
    hh, mm = (int(x) for x in str(at or "08:30").split(":"))
    local = seen.astimezone(NY)
    slot = datetime(local.year, local.month, local.day, hh, mm, tzinfo=NY)
    while slot > local or slot.weekday() >= 5:
        prev = slot.date() - timedelta(days=1)
        slot = datetime(prev.year, prev.month, prev.day, hh, mm, tzinfo=NY)
    if slot.date() <= period_end(period):
        return seen.astimezone(UTC), "seen_at"
    return slot.astimezone(UTC), "scheduled_slot_at_or_before_first_sight"


# ------------------------------------------------------------------------------ the grounds
def load_grounds(path: Path = GROUNDS) -> dict[str, Any]:
    doc = _read(path, {}) or {}
    return doc if isinstance(doc, dict) else {}


def publisher_refusal(pub: str, grounds: Mapping[str, Any]) -> str | None:
    g = (grounds.get("publishers") or {}).get(pub)
    if not isinstance(g, dict):
        return f"BLOCKED_ON_TERMS:{pub} has no row in the grounds file (terms unread)"
    if g.get("verdict") != "CONFIRMED" or g.get("built") is not True:
        return f"{g.get('verdict') or 'BLOCKED_ON_TERMS'}:{g.get('why_not') or 'not built'}"
    return None


# ------------------------------------------------------------------------------------- http
Fetch = Callable[[str, bytes | None, Mapping[str, str]], bytes]


def _tls() -> Any:
    with contextlib.suppress(Exception):
        from libs.data.polite_fetch import ssl_context
        return ssl_context()
    return None


def http(url: str, data: bytes | None = None, headers: Mapping[str, str] | None = None) -> bytes:
    """One honest request. Redirects are checked against the refused-hosts list and, for a
    request carrying a credential, never leave the host (libs.data.keyed_sources)."""
    from libs.data import keyed_sources as ks
    from libs.data.refused_hosts import refusal
    why = refusal(url)
    if why:
        raise Refused(f"BLOCKED_ON_TERMS:{why}")
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"User-Agent": HONEST_UA, "Accept": "application/json",
                                          **(headers or {})})
    with ks.keyed_opener(_tls()).open(req, timeout=TIMEOUT) as resp:
        return bytes(resp.read(MAX_BYTES))


_ROBOTS: dict[str, urllib.robotparser.RobotFileParser | str] = {}


def robots_refusal(url: str, fetch: Fetch) -> str | None:
    """None when the host's robots.txt allows this path for our agent. 404/410 = no rules;
    401/403 = disallow all; anything else unreadable is a refusal, never an assumed yes."""
    parts = urllib.parse.urlsplit(url)
    key = f"{parts.scheme}://{parts.netloc}"
    rules = _ROBOTS.get(key)
    if rules is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            body = fetch(f"{key}/robots.txt", None, {})
            if _looks_like_html(body):
                # an HTML reject page parses as "no rules": that is unread, never a yes
                rules = "robots.txt unreadable (HTML body)"
            else:
                rp.parse(body.decode("utf-8", "replace").splitlines())
                rules = rp
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                rp.parse([])
                rules = rp
            elif e.code in (401, 403):
                rp.parse(["User-agent: *", "Disallow: /"])
                rules = rp
            else:
                rules = f"robots.txt unreadable (HTTP {e.code})"
        except Exception as e:
            rules = f"robots.txt unreadable ({type(e).__name__})"
        _ROBOTS[key] = rules
    if isinstance(rules, str):
        return rules
    return None if rules.can_fetch(ROBOTS_AGENT, url) else "robots.txt disallows this path"


# ------------------------------------------------------------------------------------- BLS
def bls_key() -> tuple[str, str]:
    """(key, name it was found under) or ('', ''). Read through the registry's accepted names
    and the desk's one key loader; the value goes into the request body and nowhere else."""
    try:
        from libs.data import credentials as cred
        from libs.ops.env_keys import read_key
        names = cred.accepted_names(BLS_KEY_VAR)
    except Exception:
        return "", ""
    for name in names:
        with contextlib.suppress(Exception):
            val = read_key(name)
            if val:
                return val, name
    return "", ""


def bls_request(codes: list[str], key: str, year: int) -> tuple[str, bytes]:
    body: dict[str, Any] = {"seriesid": codes, "startyear": str(year - 1), "endyear": str(year)}
    if key:
        body["registrationkey"] = key
    return (BLS_V2 if key else BLS_V1), json.dumps(body).encode("utf-8")


def parse_bls(body: bytes, code_to_id: Mapping[str, str]) -> list[Obs]:
    try:
        doc = json.loads(body.decode("utf-8", "replace"))
    except ValueError as e:
        raise Refused("SHAPE:BLS answer is not JSON") from e
    if not isinstance(doc, dict) or str(doc.get("status")) != "REQUEST_SUCCEEDED":
        msg = "; ".join(str(m) for m in (doc.get("message") or [])) if isinstance(doc, dict) else ""
        raise Refused(f"API_ERROR:BLS status {doc.get('status') if isinstance(doc, dict) else '?'}"
                      f" {msg[:200]}")
    out: list[Obs] = []
    for s in (doc.get("Results") or {}).get("series") or []:
        sid = code_to_id.get(str((s or {}).get("seriesID")))
        for d in (s or {}).get("data") or []:
            per = str((d or {}).get("period") or "")
            v = _num((d or {}).get("value"))
            if not sid or v is None or not re.fullmatch(r"M(0[1-9]|1[0-2])", per):
                continue
            flags = tuple(sorted({str(f.get("code")) for f in d.get("footnotes") or []
                                  if isinstance(f, dict) and f.get("code")}))
            out.append(Obs(sid, f"{int(d['year']):04d}-{per[1:]}", v, flags))
    return out


# ----------------------------------------------------------------------------------- Census
def census_url(row: Mapping[str, Any], year: int) -> str:
    q = {"get": "cell_value,data_type_code,category_code,seasonally_adj,error_data",
         "for": "us:*", "time": f"from {year - 1}",
         "category_code": str(row["category_code"]), "data_type_code": str(row["data_type_code"]),
         "seasonally_adj": str(row.get("seasonally_adj") or "yes")}
    return f"{CENSUS}{row['dataset']}?{urllib.parse.urlencode(q)}"


def parse_census(body: bytes, sid: str) -> list[Obs]:
    try:
        rows = json.loads(body.decode("utf-8", "replace"))
    except ValueError as e:
        raise Refused(f"SHAPE:Census answer is not JSON ({body[:80]!r})") from e
    if not isinstance(rows, list) or len(rows) < 1 or not isinstance(rows[0], list):
        raise Refused("SHAPE:Census answer is not a header-plus-rows table")
    head = [str(h) for h in rows[0]]
    if "cell_value" not in head or "time" not in head:
        raise Refused(f"SHAPE:Census header lacks cell_value/time: {head}")
    ix = {h: i for i, h in enumerate(head)}
    out: list[Obs] = []
    for r in rows[1:]:
        if not isinstance(r, list) or len(r) != len(head):
            continue
        if "error_data" in ix and str(r[ix["error_data"]]).lower() not in ("no", ""):
            continue
        per, v = str(r[ix["time"]]), _num(r[ix["cell_value"]])
        if v is not None and re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", per):
            out.append(Obs(sid, per, v))
    return out


# ------------------------------------------------------------------------------------ store
def series_state(lake: Path, sid: str) -> dict[str, Any]:
    """{'seeded': bool, 'first': {period: value}, 'last': {period: (value, vintage)}} read from
    the series' own files -- the files ARE the state, so nothing can drift from them."""
    d = lake / sid
    first = {r["period"]: r["value"] for r in _jsonl(d / "first_prints.jsonl") if "period" in r}
    base = {r["period"]: r["value"] for r in _jsonl(d / "baseline.jsonl") if "period" in r}
    last: dict[str, tuple[float, int]] = {p: (v, 1) for p, v in {**base, **first}.items()}
    for r in _jsonl(d / "revisions.jsonl"):
        if "period" in r:
            last[r["period"]] = (r["value"], int(r.get("vintage") or 2))
    return {"seeded": bool(first or base), "first": first, "last": last}


def record(lake: Path, row: Mapping[str, Any], obs: list[Obs], seen: datetime,
           source: str) -> dict[str, int]:
    """Write what is new. A first print is appended once and never touched again; a changed
    value for a known period goes to revisions.jsonl; a series read for the first time is
    baseline, not first prints, because its vintage is unknown."""
    sid = str(row["id"])
    st = series_state(lake, sid)
    firsts: list[dict[str, Any]] = []
    revs: list[dict[str, Any]] = []
    base: list[dict[str, Any]] = []
    for o in sorted(obs, key=lambda x: x.period):
        if o.series != sid:
            continue
        common = {"series": sid, "period": o.period, "value": o.value, "source": source,
                  "seen_at": _iso(seen)}
        if o.flags:
            common["footnotes"] = list(o.flags)
        prior = st["last"].get(o.period)
        if prior is None:
            if not st["seeded"]:
                base.append({**common, "kind": "baseline", "vintage": None,
                             "note": "already published at first read; vintage unknown"})
            else:
                rel, basis = release_instant(seen, str(row.get("at") or "08:30"), o.period)
                firsts.append({**common, "kind": "first_print", "vintage": 1,
                               "release_at": _iso(rel), "release_basis": basis,
                               "available_at": _iso(seen), "release_tz_slot": row.get("at")})
            st["last"][o.period] = (o.value, 1)
        elif abs(float(prior[0]) - o.value) > 1e-12:
            vint = int(prior[1]) + 1
            revs.append({**common, "kind": "revision", "vintage": vint,
                         "previous_value": prior[0], "first_print": st["first"].get(o.period),
                         "available_at": _iso(seen)})
            st["last"][o.period] = (o.value, vint)
    d = lake / sid
    _append(d / "first_prints.jsonl", firsts)
    _append(d / "revisions.jsonl", revs)
    _append(d / "baseline.jsonl", base)
    return {"first_prints": len(firsts), "revisions": len(revs), "baseline": len(base)}


def release_vintages(sid: str, lake: Path = LAKE) -> dict[str, list[dict[str, Any]]]:
    """The reader: {'first_prints': [...], 'revisions': [...]} for one series, oldest first.
    Baseline rows (vintage unknown) are not returned: they are not first prints."""
    d = lake / sid
    return {"first_prints": sorted(_jsonl(d / "first_prints.jsonl"), key=lambda r: r["period"]),
            "revisions": _jsonl(d / "revisions.jsonl")}


def first_print_frame_rows(sid: str, lake: Path = LAKE) -> list[dict[str, Any]]:
    """[{period, released, value}] in the shape futures_state's ALFRED path produces: `released`
    is the New York calendar date of `release_at`, `period` the period's first day.

    futures_state re-adds the 08:30 slot to `released` (release_available). That is right only
    for a scheduled-slot stamp. A row stamped at first sight (`release_basis` "seen_at") may have
    been seen after 08:30, so its date moves to the NEXT weekday, whose 08:30 is after first
    sight: late, never early."""
    out: list[dict[str, Any]] = []
    for r in release_vintages(sid, lake)["first_prints"]:
        rel = _t(r.get("release_at"))
        if rel is None or r.get("value") is None:
            continue
        day = rel.astimezone(NY).date()
        if r.get("release_basis") != "scheduled_slot_at_or_before_first_sight":
            day += timedelta(days=1)
            while day.weekday() >= 5:
                day += timedelta(days=1)
        out.append({"period": f"{r['period']}-01", "value": float(r["value"]),
                    "released": day.isoformat()})
    return out


# -------------------------------------------------------------------------------------- run
def _due(state: Mapping[str, Any], pub: str, gap: timedelta, now: datetime) -> str | None:
    s = state.get(pub) or {}
    if s.get("held_until_released") and not s.get("release"):
        return (f"{HELD_UNTIL_RELEASED}:{s.get('hold_reason')} since {s.get('held_at')}; "
                f"set \"release\" on {pub} in {FETCH_STATE} to lift it")
    hold = _t(s.get("hold_until"))
    if hold and hold > now:
        return f"HELD:{s.get('hold_reason')} until {_iso(hold)}"
    last = _t(s.get("last_fetch"))
    if last and now - last < gap:
        return f"NOT_DUE:last fetch {_iso(last)}, gap {int(gap.total_seconds() // 60)} min"
    return None


def _fail(state: dict[str, Any], pub: str, exc: BaseException, now: datetime,
          secrets: tuple[str, ...] = ()) -> str:
    code = getattr(exc, "code", None)
    if isinstance(exc, Wall):
        msg = f"WALL:{exc}"
    else:
        msg = f"HTTP_{code}" if code else f"{type(exc).__name__}:{exc}"
    with contextlib.suppress(Exception):
        from libs.data.keyed_sources import redact
        msg = redact(msg, secrets)
    prior = {k: v for k, v in (state.get(pub) or {}).items()
             if k not in ("hold_until", "release", "released_by")}
    if isinstance(exc, Wall) or code in HELD_CODES:
        state[pub] = {**prior, "held_until_released": True, "held_at": _iso(now),
                      "hold_reason": "WALL" if isinstance(exc, Wall) else f"HTTP_{code}"}
    elif code in TIMED_CODES:
        state[pub] = {**prior, "hold_until": _iso(now + HOLD), "hold_reason": f"HTTP_{code}"}
    return msg[:300]


def _lift_release(state: dict[str, Any], pub: str, now: datetime) -> dict[str, Any] | None:
    """A person set `release` on a held publisher: clear the hold, keep the record."""
    s = state.get(pub) or {}
    if not (s.get("held_until_released") and s.get("release")):
        return None
    lifted = {"hold_reason": s.get("hold_reason"), "held_at": s.get("held_at"),
              "release": s.get("release"), "lifted_at": _iso(now)}
    state[pub] = {**{k: v for k, v in s.items()
                     if k not in ("held_until_released", "held_at", "hold_reason", "release")},
                  "last_release": lifted}
    return lifted


def run(*, grounds_path: Path = GROUNDS, lake: Path = LAKE, report: Path | None = REPORT,
        fetch: Fetch = http, now: datetime | None = None,
        key_reader: Callable[[], tuple[str, str]] = bls_key) -> dict[str, Any]:
    now = now or _now()
    grounds = load_grounds(grounds_path)
    rows = [r for r in grounds.get("series") or [] if isinstance(r, dict) and r.get("id")]
    state = _read(lake / FETCH_STATE, {}) or {}
    pubs: dict[str, dict[str, Any]] = {}
    per_series: dict[str, dict[str, int]] = {}

    names = {str(r.get("publisher")) for r in rows} | set(grounds.get("publishers") or {})
    for pub in sorted(names):
        mine = [r for r in rows if r.get("publisher") == pub]
        why = publisher_refusal(pub, grounds)
        if why:
            pubs[pub] = {"status": why.split(":", 1)[0], "why": why, "series": len(mine)}
            continue
        if not mine:
            pubs[pub] = {"status": "NO_SERIES"}
            continue
        key, key_name = key_reader() if pub == "bls" else ("", "")
        gap = BLS_V1_MIN_GAP if (pub == "bls" and not key) else DEFAULT_MIN_GAP
        wait = _due(state, pub, gap, now)
        lifted = None if wait else _lift_release(state, pub, now)
        info: dict[str, Any] = {"series": len(mine)}
        if lifted:
            info["hold_lifted"] = lifted
        if pub == "bls":
            info["api"] = "v2_registered" if key else "v1_keyless"
            info["key_found_under"] = key_name or None    # a NAME, never the value
        if wait:
            pubs[pub] = {**info, "status": wait.split(":", 1)[0], "why": wait}
            continue
        obs: list[Obs] = []
        errors: list[str] = []
        try:
            if pub == "bls":
                code_to_id = {str(r["code"]): str(r["id"]) for r in mine if r.get("code")}
                url, body = bls_request(sorted(code_to_id), key, now.year)
                why = robots_refusal(url, fetch)
                if why:
                    raise Refused(f"BLOCKED_ROBOTS:{why}")
                obs = parse_bls(_check_api_body(
                    fetch(url, body, {"Content-Type": "application/json"}), "BLS"), code_to_id)
            elif pub == "census":
                for r in mine:
                    url = census_url(r, now.year)
                    why = robots_refusal(url, fetch)
                    if why:
                        raise Refused(f"BLOCKED_ROBOTS:{why}")
                    try:
                        obs += parse_census(_check_api_body(fetch(url, None, {}), "Census"),
                                            str(r["id"]))
                    except Refused as e:
                        errors.append(f"{r['id']}:{e}")
            else:
                raise Refused(f"NO_FETCHER:{pub}")
            state[pub] = {**(state.get(pub) or {}), "last_fetch": _iso(now)}
            status = "OK" if obs else ("ERROR" if errors else "EMPTY")
        except Refused as e:
            status, errors = str(e).split(":", 1)[0], [*errors, str(e)[:300]]
        except Exception as e:
            status = "ERROR"
            errors.append(_fail(state, pub, e, now, (key,) if key else ()))
            s_now = state.get(pub) or {}
            if s_now.get("held_until_released") and s_now.get("held_at") == _iso(now):
                status = HELD_UNTIL_RELEASED
            elif s_now.get("hold_until") == _iso(now + HOLD):
                status = "HARD_STOP"
        for r in mine:
            got = [o for o in obs if o.series == r["id"]]
            if got:
                src = f"{pub}:{info.get('api', 'api')}"
                per_series[str(r["id"])] = record(lake, r, got, now, src)
        pubs[pub] = {**info, "status": status, "observations": len(obs),
                     **({"errors": errors} if errors else {})}

    _atomic(lake / FETCH_STATE, state)
    totals = {"first_prints": 0, "revisions": 0, "baseline": 0}
    series_out: dict[str, Any] = {}
    for r in rows:
        sid = str(r["id"])
        st = series_state(lake, sid)
        fp = _jsonl(lake / sid / "first_prints.jsonl")
        series_out[sid] = {
            "publisher": r.get("publisher"), "title": r.get("title"),
            "first_prints_held": len(st["first"]),
            "revisions_held": len(_jsonl(lake / sid / "revisions.jsonl")),
            "baseline_periods": len(_jsonl(lake / sid / "baseline.jsonl")),
            "latest_first_print": fp[-1] if fp else None,
            "this_pass": per_series.get(sid, {"first_prints": 0, "revisions": 0, "baseline": 0}),
        }
        for k in totals:
            totals[k] += series_out[sid]["this_pass"][k]
    doc = {
        "generated_at": _iso(now), "source": SOURCE_ID, "lake": str(lake),
        "publishers": pubs, "series": series_out, "this_pass": totals,
        "first_prints_held": sum(s["first_prints_held"] for s in series_out.values()),
        "terms": {p: {k: g.get(k) for k in ("verdict", "built", "terms", "robots", "why_not",
                                            "notice") if g.get(k)}
                  for p, g in (grounds.get("publishers") or {}).items()},
        "no_fred_no_alfred": True,
        "money_path": False,
    }
    if not rows:
        doc["status"] = UNMEASURED
    if report is not None:
        _atomic(report, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = run()
    print(json.dumps({"publishers": {p: v.get("status") for p, v in doc["publishers"].items()},
                      "this_pass": doc["this_pass"], "first_prints_held": doc["first_prints_held"],
                      "seconds": round(time.monotonic() - t0, 1), "budget_s": a.budget_s}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
