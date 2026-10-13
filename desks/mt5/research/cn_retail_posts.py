"""CN RETAIL POSTS -- point-in-time post volume and post text from the Guba and Xueqiu boards.

    python desks/mt5/research/cn_retail_posts.py --once [--budget-s 300] [--no-fetch] [--dry-run]

WHAT IT DOES, ONE PASS (hourly leg `cn_retail_posts`):

  1. For every board in `desks/mt5/data/cn_retail_boards.json` (MT5 targets CN50, HK50, USDCNH;
     each with its index board, its largest constituents' boards, or its FX boards), read the
     site's robots.txt (live, at most once a day per host) and fetch the board's public post LIST
     -- never a post body, never a logged-in page. One request per 3 s per host.
  2. A page that answers with a login wall, a CAPTCHA, a slider or a WAF challenge, or a route
     robots.txt disallows, is METHOD_BLOCKED with its evidence (marker, URL, bytes, body hash)
     and is never worked around: no rotating user agent, no forged header, no cookie.
  3. Every parsed row lands RAW in `text_store/cn_retail/raw/<day>.jsonl` with `published_time`
     (the site's own stamp, UTC), `available_time` (this fetch's time) and `source_hash`; ugly
     rows (no time, no counts, empty title) land too, with `parse_flags` saying what failed.
  4. The first sighting of each post is appended to `text_store/cn_retail/posts.jsonl`, the
     tone scorer's input, in the central-bank tone corpus's convention (`date`, `title`, `url`
     as in `bis_speech_tone.jsonl`; `published_utc`, `link`, `instruments` as in
     `cb_documents.jsonl`) plus `text`, `lang`, `available_time` and `source_hash`. This organ
     scores nothing; the LLM lab's Chinese tone scorer reads that file.
  5. Hourly post-volume series per target are rebuilt from the whole store and published as
     lake frames (`lake/series/cn_retail_<T>_hourly.parquet`, and the daily
     `lake/series/cn_retail_<T>.parquet` the attention admission test in `nlp_social_cells`
     reads), and the per-board artifact `reports/CN_RETAIL_POSTS.json` is written.

POINT IN TIME. An hour H of board b is OBSERVED only when a successful fetch of b at time t >= H+1h
listed back to at least H (its window start: the conservative max of the page's oldest publish
and oldest last-reply time, ignoring the two oldest rows, which can be pinned posts). The hour's
value is the posts published in H that were first seen at or before that fetch, and its
`available_time` is t. An hour no fetch covered is ABSENT, never zero (L1.28a): a box that was
off reads as a gap, not as a quiet crowd.

THE SITES' OWN TERMS ARE RECORDED VERBATIM in `libs.data.cn_sources.RETAIL_SITES`, with the
build session's one live probe per site (2026-10-13: Guba served a 身份核实 interstitial; Xueqiu
served an Alibaba Cloud WAF challenge and disallows every post-list route in robots.txt).
Live yield on the box is UNMEASURED until the box runs this leg.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import cn_sources as cn  # noqa: E402

SOURCE = "cn_retail_posts"
BOARDS = DESK / "data" / "cn_retail_boards.json"
#: NOT under `data/intelligence/` (the candidate compiler globs that tree as seat output);
#: `text_store/` is gitignored box-local state, the same home as the blog/NLP stores.
STORE = DESK / "data" / "text_store" / "cn_retail"
SERIES_DIR = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "CN_RETAIL_POSTS.json"
#: The China state sources (Eastmoney Connect / limit pools / institutional holdings, JiSiLu,
#: AKShare, TuShare) are rows of the free-stack roster -- the alt-data source registry -- and are
#: FETCHED by the free-stack hunter (hourly leg `free_stack_hunt`), whose PIT store, lake frames
#: and proposer already turn a roster row into CN50 / HK50 / USDCNH cells. This organ reports their
#: access state beside the boards' so one artifact answers "what China retail and stress data is
#: the desk actually getting".
ROSTER = DESK / "data" / "free_stack_sources.json"
FREE_STACK_YIELD = DESK / "reports" / "FREE_STACK_YIELD.json"
CN_STATE_IDS: tuple[str, ...] = ("em_connect_flows", "em_limit_pools", "em_institution_hold",
                                 "jsl_cb_index", "jsl_cb_list", "akshare", "tushare")

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36 quant-desk-cn-retail/1.0 (research)")
HOST_GAP_S = 3.0
ROBOTS_TTL = timedelta(hours=24)
#: Extra list pages a board may fetch while its history is shorter than HISTORY_TARGET.
MAX_BACKFILL_PAGES = 4
HISTORY_TARGET = timedelta(hours=72)
#: A day enters the daily frame only when this many of its hours were observed.
MIN_DAY_HOURS = 20
Z_WINDOW_DAYS = 28
Z_MIN_PRIOR = 10
UNMEASURED = "UNMEASURED"
COLLECTING = "COLLECTING"
METHOD_BLOCKED = "METHOD_BLOCKED"
LANG = "zh"

#: fetch(url) -> (http status, body). Raises on a network failure. Injected so tests never touch
#: the network.
Fetch = Callable[[str], tuple[int, bytes]]


def http_fetch(url: str) -> tuple[int, bytes]:
    """Plain GET, one honest user agent, no cookie jar, no retries."""
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=25.0) as resp:
            return int(resp.status), resp.read(8 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(65536) if exc.fp else b""


class Pacer:
    """At most one request per HOST_GAP_S per host."""

    def __init__(self, gap_s: float = HOST_GAP_S, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.gap_s, self.sleep, self.clock = gap_s, sleep, clock
        self.last: dict[str, float] = {}

    def wait(self, host: str) -> None:
        if host in self.last:
            due = self.last[host] + self.gap_s - self.clock()
            if due > 0:
                self.sleep(due)
        self.last[host] = self.clock()


# ------------------------------------------------------------------------------------- io
def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def _append(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _ts(v: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def _iso(d: datetime) -> str:
    return d.astimezone(UTC).isoformat(timespec="seconds")


def load_boards(path: Path = BOARDS) -> list[dict[str, Any]]:
    doc = _read_json(path, {})
    out: list[dict[str, Any]] = []
    for target, spec in (doc.get("targets") or {}).items():
        for b in spec.get("boards") or []:
            out.append({**b, "target": target})
    return out


# ---------------------------------------------------------------------------------- robots
def robots_for(site: str, now: datetime, fetch: Fetch, pacer: Pacer, store: Path,
               ) -> dict[str, Any]:
    """The host's robots.txt, re-read at most daily. A network failure is UNMEASURED and fetches
    nothing; a 404 is the standard 'no rules'."""
    meta = cn.RETAIL_SITES[site]
    path = store / "robots" / f"{meta['host']}.json"
    cached = _read_json(path, {})
    at = _ts(cached.get("fetched_at"))
    if at is not None and now - at < ROBOTS_TTL and cached.get("state") in ("OK", "ABSENT"):
        return dict(cached)
    pacer.wait(meta["host"])
    try:
        code, body = fetch(meta["robots_url"])
    except Exception as exc:
        doc = {"state": UNMEASURED, "fetched_at": _iso(now),
               "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        _atomic(path, json.dumps(doc, ensure_ascii=False))
        return doc
    if code == 404:
        doc = {"state": "ABSENT", "fetched_at": _iso(now), "text": ""}
    elif 200 <= code < 300 and cn.challenge_of(body) is None:
        doc = {"state": "OK", "fetched_at": _iso(now),
               "text": body.decode("utf-8", "replace")[:200_000]}
    else:
        doc = {"state": UNMEASURED, "fetched_at": _iso(now),
               "error": f"http {code}" + (f", {cn.challenge_of(body)}"
                                          if cn.challenge_of(body) else "")}
    _atomic(path, json.dumps(doc, ensure_ascii=False))
    return doc


# ------------------------------------------------------------------------------------ fetch
def _list_url(site: str, code: str, page: int) -> str:
    meta = cn.RETAIL_SITES[site]
    suffix = meta["page_suffix"].format(n=page) if (page > 1 and meta["page_suffix"]) else ""
    return str(meta["list_url"]).format(code=code, page=suffix, n=page)


def _source_hash(site: str, board: str, row: dict[str, Any]) -> str:
    core = {k: row.get(k) for k in ("post_id", "title", "published_raw", "read_count",
                                    "reply_count", "url")}
    blob = json.dumps({"site": site, "board": board, **core}, ensure_ascii=False,
                      sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _window_start(rows: list[dict[str, Any]]) -> str | None:
    """The oldest time a page provably lists back to. The conservative max of (oldest publish,
    oldest last-reply), with the two oldest rows ignored -- pinned posts sit at the top of a
    board with old stamps and would otherwise claim coverage the page does not have."""
    def floor(key: str) -> datetime | None:
        ts = sorted(t for r in rows if (t := _ts(r.get(key))) is not None)
        if not ts:
            return None
        return ts[min(2, len(ts) - 1)]

    pub = floor("published_time")
    last = floor("last_reply_time")
    picks = [t for t in (pub, last) if t is not None]
    return _iso(max(picks)) if picks else None


def fetch_board(board: dict[str, Any], now: datetime, fetch: Fetch, pacer: Pacer,
                robots: dict[str, Any], pages: int) -> dict[str, Any]:
    """Every request one board needs this pass. Never raises."""
    site = str(board["site"])
    meta = cn.RETAIL_SITES[site]
    out: dict[str, Any] = {"site": site, "board": board["board"], "target": board["target"],
                           "status": UNMEASURED, "evidence": "", "rows": [], "fetches": [],
                           "code": None}
    if robots.get("state") not in ("OK", "ABSENT"):
        out["evidence"] = (f"robots.txt for {meta['host']} unreadable "
                           f"({robots.get('error') or robots.get('state')}); nothing fetched")
        return out
    for code in board.get("codes") or []:
        first = _list_url(site, str(code), 1)
        if robots.get("state") == "OK" and not cn.robots_allows(str(robots.get("text") or ""),
                                                                 first):
            out.update(status=METHOD_BLOCKED, code=code,
                       evidence=(f"robots.txt ({meta['robots_url']}, read "
                                 f"{robots.get('fetched_at')}) disallows "
                                 f"{urlsplit(first).path}; not requested"))
            return out
        rows: list[dict[str, Any]] = []
        for page in range(1, max(1, pages) + 1):
            url = _list_url(site, str(code), page)
            pacer.wait(meta["host"])
            at = now
            rec: dict[str, Any] = {"site": site, "board": board["board"], "code": code,
                                   "page": page, "url": url, "at": _iso(at)}
            try:
                http, body = fetch(url)
            except Exception as exc:
                rec.update(state=UNMEASURED, error=f"{type(exc).__name__}: {str(exc)[:160]}")
                out["fetches"].append(rec)
                out["evidence"] = f"{url}: {rec['error']} (network; not a verdict on the site)"
                return out
            marker = cn.challenge_of(body)
            rec.update(http=http, bytes=len(body),
                       body_sha256=hashlib.sha256(body).hexdigest())
            if marker or http in (401, 403, 451):
                rec.update(state=METHOD_BLOCKED, marker=marker or f"http {http}")
                out["fetches"].append(rec)
                out.update(status=METHOD_BLOCKED, code=code,
                           evidence=(f"{url} answered http {http}, {len(body)} B, sha256 "
                                     f"{rec['body_sha256'][:16]}: {marker or 'refused'}; "
                                     "not worked around"))
                return out
            parsed = (cn.parse_guba_list(body, at) if site == "guba"
                      else cn.parse_xueqiu_list(body, at))
            for r in parsed:
                r["last_reply_time"] = cn._cn_time(str(r.get("last_reply_raw") or ""), at)[0] \
                    if r.get("last_reply_raw") else None
            trusted = [r for r in parsed if r.get("published_time") and not (
                {"time_is_last_update", "time_unparsed"} & set(r.get("parse_flags") or []))]
            rec.update(state="OK" if parsed else "EMPTY", n_rows=len(parsed),
                       n_publish_time=len(trusted), window_start=_window_start(trusted))
            out["fetches"].append(rec)
            if not parsed:
                break
            rows += [{**r, "page": page, "available_time": _iso(at)} for r in parsed]
        if rows:
            out.update(status=COLLECTING, code=code, rows=rows,
                       evidence=f"{len(rows)} rows from {len(out['fetches'])} list page(s)")
            return out
        if not out["evidence"]:
            out["evidence"] = (f"code {code}: page parsed no posts (wrong board code or a "
                               "markup change); next code tried")
    return out


# ------------------------------------------------------------------------------------- land
def land(result: dict[str, Any], store: Path, seen: dict[str, str]) -> tuple[int, int]:
    """Raw rows (every one) and first sightings (the tone corpus). Returns (raw, new)."""
    site, board, target = result["site"], result["board"], result["target"]
    raw_rows: list[dict[str, Any]] = []
    new_rows: list[dict[str, Any]] = []
    for r in result["rows"]:
        sh = _source_hash(site, board, r)
        user = str(r.get("user") or "")
        row = {"site": site, "board": board, "target": target, "code": result["code"],
               "post_id": r.get("post_id"), "title": r.get("title") or "",
               "published_raw": r.get("published_raw") or "",
               "published_time": r.get("published_time"),
               "last_reply_time": r.get("last_reply_time"),
               "available_time": r["available_time"], "read_count": r.get("read_count"),
               "reply_count": r.get("reply_count"), "url": r.get("url") or "",
               "page": r.get("page"),
               "author_hash": (hashlib.sha256(f"cnr|{user}".encode()).hexdigest()[:12]
                               if user else ""),
               "parse_flags": list(r.get("parse_flags") or []), "source_hash": sh}
        raw_rows.append(row)
        key = f"{site}:{r.get('post_id') or sh}"
        if key in seen:
            continue
        seen[key] = row["available_time"]
        pub = row["published_time"]
        trusted = pub and not ({"time_is_last_update", "time_unparsed"}
                               & set(row["parse_flags"]))
        new_rows.append({
            "source": f"cn_retail:{site}", "site": site, "board": board, "target": target,
            "instruments": [target], "post_id": row["post_id"],
            "date": (pub or row["available_time"])[:10],
            "published_utc": pub if trusted else None, "published_raw": row["published_raw"],
            "available_time": row["available_time"], "title": row["title"],
            "text": row["title"], "url": row["url"], "link": row["url"], "lang": LANG,
            "read_count": row["read_count"], "reply_count": row["reply_count"],
            "parse_flags": row["parse_flags"], "source_hash": sh})
    if raw_rows:
        day = raw_rows[0]["available_time"][:10]
        _append(store / "raw" / f"{day}.jsonl", raw_rows)
    _append(store / "posts.jsonl", new_rows)
    return len(raw_rows), len(new_rows)


# ----------------------------------------------------------------------------------- series
def _hour(d: datetime) -> datetime:
    return d.replace(minute=0, second=0, microsecond=0)


def board_hours(fetch_log: list[dict[str, Any]]) -> dict[tuple[str, str], dict[datetime, str]]:
    """(site, board) -> {hour start: available_time of the first fetch that covered it}."""
    passes: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for f in fetch_log:
        # A page whose rows carry no trustworthy PUBLISH time (the HTML layout prints only the
        # last-update time) observes nothing: counting it would publish zeros it never measured.
        if f.get("state") == "OK" and 2 * int(f.get("n_publish_time") or 0) >= int(
                f.get("n_rows") or 0) > 0:
            passes[(str(f.get("site")), str(f.get("board")), str(f.get("at")))].append(f)
    out: dict[tuple[str, str], dict[datetime, str]] = defaultdict(dict)
    for (site, board, at_s), recs in sorted(passes.items(), key=lambda kv: kv[0][2]):
        at = _ts(at_s)
        starts = [t for r in recs if (t := _ts(r.get("window_start"))) is not None]
        if at is None or not starts:
            continue
        h = _hour(min(starts))
        if h < min(starts):
            h += timedelta(hours=1)          # a partly listed hour is not observed
        cov = out[(site, board)]
        while h + timedelta(hours=1) <= at:
            cov.setdefault(h, at_s)
            h += timedelta(hours=1)
    return out


def hourly_series(posts: list[dict[str, Any]], fetch_log: list[dict[str, Any]],
                  boards: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Per target, one row per OBSERVED hour: posts, replies and reads summed over the boards
    that observed it, the count of those boards, and the hour's available_time."""
    cover = board_hours(fetch_log)
    target_of = {(b["site"], b["board"]): b["target"] for b in boards}
    bucket: dict[tuple[str, str, datetime], list[dict[str, Any]]] = defaultdict(list)
    for p in posts:
        pub = _ts(p.get("published_utc"))
        if pub is None:
            continue
        bucket[(p["site"], p["board"], _hour(pub))].append(p)
    rows: dict[str, dict[datetime, dict[str, Any]]] = defaultdict(dict)
    for (site, board), hours in cover.items():
        target = target_of.get((site, board))
        if target is None:
            continue
        for h, avail in hours.items():
            got = [p for p in bucket.get((site, board, h), [])
                   if str(p.get("available_time")) <= avail]
            r = rows[target].setdefault(h, {"period": _iso(h), "available_time": avail,
                                            "posts": 0, "replies": 0, "reads": 0,
                                            "boards_observed": 0})
            r["posts"] += len(got)
            r["replies"] += sum(int(p.get("reply_count") or 0) for p in got)
            r["reads"] += sum(int(p.get("read_count") or 0) for p in got)
            r["boards_observed"] += 1
            r["available_time"] = max(r["available_time"], avail)
    out: dict[str, list[dict[str, Any]]] = {}
    for target, by_h in rows.items():
        ordered = [by_h[h] for h in sorted(by_h)]
        for r in ordered:
            r["posts_per_board"] = round(r["posts"] / r["boards_observed"], 4)
        out[target] = ordered
    return out


def daily_frame(hourly: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Days with at least MIN_DAY_HOURS observed hours; `post_volume_z` is the day's log
    per-board-hour volume against its own trailing observed days (None until Z_MIN_PRIOR)."""
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in hourly:
        by_day[r["period"][:10]].append(r)
    days: list[dict[str, Any]] = []
    for day in sorted(by_day):
        hs = by_day[day]
        if len(hs) < MIN_DAY_HOURS:
            continue
        per = sum(h["posts_per_board"] for h in hs) / len(hs)
        days.append({"day": day, "available_time": max(h["available_time"] for h in hs),
                     "post_volume": sum(h["posts"] for h in hs), "observed_hours": len(hs),
                     "post_volume_per_board_hour": round(per, 4),
                     "_lv": math.log1p(per)})
    for i, d in enumerate(days):
        prior = [x["_lv"] for x in days[max(0, i - Z_WINDOW_DAYS):i]]
        z = None
        if len(prior) >= Z_MIN_PRIOR:
            mu = sum(prior) / len(prior)
            sd = math.sqrt(sum((x - mu) ** 2 for x in prior) / (len(prior) - 1))
            z = round((d["_lv"] - mu) / sd, 4) if sd > 0 else None
        d["post_volume_z"] = z
    for d in days:
        d.pop("_lv")
    return days


def write_lake(hourly: dict[str, list[dict[str, Any]]], series_dir: Path) -> dict[str, Any]:
    import pandas as pd

    out: dict[str, Any] = {}
    series_dir.mkdir(parents=True, exist_ok=True)
    for target, rows in hourly.items():
        if not rows:
            continue
        pd.DataFrame(rows).to_parquet(series_dir / f"cn_retail_{target}_hourly.parquet",
                                      index=False)
        days = daily_frame(rows)
        if days:
            pd.DataFrame(days).to_parquet(series_dir / f"cn_retail_{target}.parquet",
                                          index=False)
        out[target] = {"hourly_rows": len(rows), "daily_rows": len(days)}
    return out


# ------------------------------------------------------------------------- state sources
def state_sources(roster: Path = ROSTER, yield_path: Path = FREE_STACK_YIELD,
                  env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Per China state source: its access state as the hunter last measured it.

    COLLECTING (the hunter's last pass landed observations), METHOD_BLOCKED (robots, login,
    CAPTCHA or WAF, with the hunter's evidence), NEEDS_KEY (a credentialed route whose key is not
    on this host -- TuShare: no new key can be obtained, so the row is registered and stops
    there), or UNMEASURED (never run here, or a network failure)."""
    env = dict(os.environ) if env is None else env
    rows = {str(r.get("id")): r for r in (_read_json(roster, {}).get("sources") or [])
            if isinstance(r, dict)}
    per = (_read_json(yield_path, {}) or {}).get("per_source") or {}
    out: list[dict[str, Any]] = []
    for sid in CN_STATE_IDS:
        r = rows.get(sid)
        y = per.get(sid) or {}
        hunter = str(y.get("status") or UNMEASURED)
        key_env = str((r or {}).get("key_env") or "")
        if r is None:
            state, why = UNMEASURED, "not in the roster"
        elif key_env and not env.get(key_env):
            state, why = "NEEDS_KEY", f"{key_env} is not set on this host"
        elif hunter == "OK":
            state, why = COLLECTING, f"{y.get('obs_total')} observations landed"
        elif hunter == METHOD_BLOCKED:
            state, why = METHOD_BLOCKED, str(y.get("last_error") or "")
        else:
            state = UNMEASURED
            why = (f"hunter status {hunter}: {y.get('last_error') or ''}".strip()
                   if y else "the hunter has not run this source on this host")
        out.append({"id": sid, "name": (r or {}).get("name"), "route": (r or {}).get("route"),
                    "access_state": state, "evidence": why, "hunter_status": hunter,
                    "last_success": y.get("last_success", UNMEASURED),
                    "columns": y.get("columns", UNMEASURED),
                    "blocker_prior": (r or {}).get("blocker_prior", "")})
    return out


# -------------------------------------------------------------------------------------- run
def run(now: datetime | None = None, *, fetch: Fetch | None = None, fetching: bool = True,
        budget_s: float = 300.0, store: Path = STORE, boards_path: Path = BOARDS,
        series_dir: Path = SERIES_DIR, out: Path = REPORT, dry_run: bool = False,
        pacer: Pacer | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    t0 = time.monotonic()
    boards = load_boards(boards_path)
    state: dict[str, Any] = _read_json(store / "board_state.json", {})
    seen: dict[str, str] = _read_json(store / "seen.json", {})
    posts_before = _jsonl(store / "posts.jsonl")
    depth0: dict[str, datetime] = {}
    for p in posts_before:
        k = f"{p.get('site')}:{p.get('board')}"
        t = _ts(p.get("published_utc"))
        if t is not None and (k not in depth0 or t < depth0[k]):
            depth0[k] = t
    pacer = pacer or Pacer()
    transport = fetch or http_fetch
    pass_rows: dict[str, dict[str, Any]] = {}
    fetch_rows: list[dict[str, Any]] = []
    robots: dict[str, dict[str, Any]] = {}
    for b in boards:
        key = f"{b['site']}:{b['board']}"
        if b.get("site") not in cn.RETAIL_SITES:
            pass_rows[key] = {"status": UNMEASURED, "evidence": f"unknown site {b.get('site')}"}
            continue
        if not fetching or dry_run:
            pass_rows[key] = {"status": state.get(key, {}).get("status", UNMEASURED),
                              "evidence": (state.get(key, {}).get("evidence")
                                           or "no fetch this pass (--no-fetch / --dry-run); "
                                           "build-session prior: " + str(
                                               cn.RETAIL_SITES[b["site"]]["probe_2026_10_13"])),
                              "new": 0, "raw": 0, "skipped": True}
            continue
        if time.monotonic() - t0 >= budget_s:
            pass_rows[key] = {**state.get(key, {}), "new": 0, "raw": 0,
                              "skipped": True, "skip_reason": "pass budget spent"}
            continue
        if b["site"] not in robots:
            robots[b["site"]] = robots_for(b["site"], now, transport, pacer, store)
        oldest = depth0.get(key)
        pages = 1 + (MAX_BACKFILL_PAGES if oldest is None or now - oldest < HISTORY_TARGET
                     else 0)
        res = fetch_board(b, now, transport, pacer, robots[b["site"]], pages)
        fetch_rows += res["fetches"]
        raw_n, new_n = (0, 0) if dry_run else land(res, store, seen)
        pass_rows[key] = {"status": res["status"], "evidence": res["evidence"],
                          "code": res["code"], "new": new_n, "raw": raw_n,
                          "at": _iso(now)}
    if not dry_run and fetching:
        _append(store / "fetch_log.jsonl", fetch_rows)
        _atomic(store / "seen.json", json.dumps(seen, ensure_ascii=False))
        merged = {k: {kk: v.get(kk) for kk in ("status", "evidence", "code", "at")}
                  for k, v in pass_rows.items() if not v.get("skipped")}
        _atomic(store / "board_state.json",
                json.dumps({**state, **merged}, ensure_ascii=False, indent=1))
    posts = _jsonl(store / "posts.jsonl")
    log = _jsonl(store / "fetch_log.jsonl")
    hourly = hourly_series(posts, log, boards)
    lake = {} if dry_run else write_lake(hourly, series_dir)
    cover = board_hours(log)
    per_board: list[dict[str, Any]] = []
    for b in boards:
        key = f"{b['site']}:{b['board']}"
        mine = [p for p in posts if p.get("site") == b["site"] and p.get("board") == b["board"]]
        pubs = [t for p in mine if (t := _ts(p.get("published_utc"))) is not None]
        row = pass_rows.get(key, {})
        per_board.append({
            "target": b["target"], "site": b["site"], "board": b["board"],
            "role": b.get("role"), "codes": b.get("codes"), "live_code": row.get("code"),
            "status": row.get("status", UNMEASURED), "evidence": row.get("evidence", ""),
            "posts_landed": len(mine), "posts_landed_this_pass": int(row.get("new") or 0),
            "raw_rows_this_pass": int(row.get("raw") or 0),
            "history_depth_hours": (round((now - min(pubs)).total_seconds() / 3600, 1)
                                    if pubs else UNMEASURED),
            "series_length_hours": len(cover.get((b["site"], b["board"]), {})) or UNMEASURED})
    targets = sorted({b["target"] for b in boards})
    per_target = {t: {"series_length_hours": len(hourly.get(t, [])) or UNMEASURED,
                      "daily_rows": (lake.get(t) or {}).get("daily_rows", UNMEASURED),
                      "boards": sum(1 for b in boards if b["target"] == t),
                      "boards_collecting": sum(1 for r in per_board if r["target"] == t
                                               and r["status"] == COLLECTING),
                      "frames": ([f"desks/mt5/data/lake/series/cn_retail_{t}_hourly.parquet",
                                  f"desks/mt5/data/lake/series/cn_retail_{t}.parquet"]
                                 if t in lake else [])}
                  for t in targets}
    counts: dict[str, int] = defaultdict(int)
    for r in per_board:
        counts[r["status"]] += 1
    rep = {
        "generated_at": _iso(now), "source": SOURCE, "dry_run": dry_run, "fetching": fetching,
        "host": os.environ.get("COMPUTERNAME") or os.uname().nodename,
        "statuses": dict(counts), "boards": per_board, "targets": per_target,
        "state_sources": state_sources(),
        "sites": {s: {k: m[k] for k in ("host", "basis", "robots_evidence", "terms_url",
                                        "terms_quote", "terms_reading", "probe_2026_10_13")}
                  for s, m in cn.RETAIL_SITES.items()},
        "robots_this_pass": {s: {k: v for k, v in r.items() if k != "text"}
                             for s, r in robots.items()},
        "tone_corpus": {"path": "desks/mt5/data/text_store/cn_retail/posts.jsonl",
                        "rows": len(posts),
                        "convention": ("cb_tone corpus fields (date, title, url / published_utc,"
                                       " link, instruments) + text, lang, available_time, "
                                       "source_hash; titles only, no bodies")},
        "pit_rule": ("an hour is observed only when a fetch at >= hour end listed back to the "
                     "hour; its value counts posts first seen by that fetch; unobserved hours "
                     "are absent, never zero"),
        "live_yield": ("UNMEASURED until the trading box runs this leg"
                       if not any(r["status"] == COLLECTING for r in per_board) else
                       "MEASURED this pass"),
        "elapsed_s": round(time.monotonic() - t0, 2),
    }
    if not dry_run:
        _atomic(out, json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's call)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--no-fetch", action="store_true",
                    help="rebuild series and the report from the store; no request")
    ap.add_argument("--dry-run", action="store_true", help="measure, write nothing")
    a = ap.parse_args(argv)
    rep = run(fetching=not a.no_fetch, budget_s=a.budget_s, dry_run=a.dry_run)
    print(f"cn_retail_posts: {rep['statuses']} over {len(rep['boards'])} boards; "
          f"tone corpus {rep['tone_corpus']['rows']} rows; "
          + ", ".join(f"{t}={v['series_length_hours']}h" for t, v in rep["targets"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
