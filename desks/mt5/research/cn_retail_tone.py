"""CN RETAIL TONE -- Guba board attention and Chinese tone for CHINAH, HK50, USDCNH, XAUUSD.

NO CLOCK OF ITS OWN, BY DESIGN. This is a library organ called by `nlp_social_cells.ingest`
(itself on the ORGANS battery rotation as `--ingest`, and on `daily_cycle`'s proposer list), the
same way `blog_social_mining` is. `nlp_social_cells.build_grid` then puts every series published
here through the shuffled-date placebo gain test, and only a pre-declared cell whose own
(series, instrument) passed is donated to the gauntlet. The scorer only PROPOSES.

ONE PASS:

  1. GATE each declared source (`gate`): the per-source terms row in
     `desks/mt5/data/free_stack_sources.json` must say `auth: none` and `machine_use_allowed`, the
     source must not need a login, an account cookie or a WAF/anti-bot token, and the host's
     robots.txt must allow the board path for this agent (RFC 9309: a 4xx robots.txt allows all,
     an unreachable one allows nothing this pass). A refused source is not fetched and its reason
     is published. Xueqiu is declared BLOCKED: its board posts are served only after a WAF
     challenge (`_waf_` renderData page in the world-crawler vault, 2026-09-02; acw_sc__v2 in
     `libs.data.free_stack`; `libs.data.cn_sources`, 2026-08-01) and a token cookie, and clearing
     either is an anti-bot bypass this desk does not do.
  2. FETCH each allowed Guba board's public list page ONCE, with the desk's declared research
     User-Agent (`libs.data.free_stack.http_fetch`), a pause between requests, no retry, no
     cookie. New posts are appended to the store with `first_seen_at = now`.
  3. HARVEST the world crawler's vaulted Guba list pages
     (`data/intelligence/world/vault/guba.eastmoney.com/*.gz`, written by
     `side_channels/world_crawler.vault`): each page is an observation at its own `fetched_utc`,
     so it adds honest history without one extra request.
  4. BUILD per board the PIT daily rows (`libs.research.guba_tone.daily_series`: a post
     counts on its publication day only if observed before that day closed) and publish:

       direct   desks/mt5/data/lake/series/cn_retail_tone_<SYMBOL>.parquet  (available_time)
       axis     desks/mt5/data/axes/cn_retail_tone.json  (series[<SYMBOL>.<signal>].points)
       report   desks/mt5/reports/CN_RETAIL_TONE.json    (postures, gates, rows)
       digest   desks/mt5/data/digests/asia_alt_data_digest.json  (section `cn_retail_tone`)

THE STORE: `desks/mt5/data/text_store/cn_retail_tone/` (gitignored) -- `posts.jsonl` (titles and
hashed authors only), `observations.json` ({board: {day: n}}), `vault_seen.json`,
`known_at.json` ({"<SYMBOL>|<day>": first emission}) and `llm_tone.json`.

THE OPTIONAL LLM COLUMN (`tone_llm_mean`) runs only with QUANT_CN_TONE_LLM=1 and the seat on the
free tier (`libs.ops.llm_seat.free_tier_only()`); titles are sanitized first, a post is scored once,
and a score counts toward a day only if it was made before that day closed. Absent, the column is
NaN and the lexicon carries the series.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import asia_alt_digest  # noqa: E402
from libs.research import guba_tone as crt  # noqa: E402

SOURCE = "cn_retail_tone"
STORE = DESK / "data" / "text_store" / "cn_retail_tone"
SERIES_DIR = DESK / "data" / "lake" / "series"
AXIS_OUT = DESK / "data" / "axes" / "cn_retail_tone.json"
REPORT = DESK / "reports" / "CN_RETAIL_TONE.json"
TERMS = DESK / "data" / "free_stack_sources.json"
VAULT = DESK / "data" / "intelligence" / "world" / "vault" / "guba.eastmoney.com"
SIGNALS = ("volume_z", "tone_mean", "tone_delta", "tone_delta_z", "tone_shock_signed",
           "tone_llm_mean")
GUBA_LIST = "https://guba.eastmoney.com/list,{board}.html"
ROBOTS_AGENT = "quant-desk-free-stack"
MAX_POSTS = 200_000

LIVE, BLOCKED, HELD = "LIVE", "BLOCKED", "HELD"


@dataclass(frozen=True)
class Board:
    """One Guba board and the instrument its tone is published for."""

    instrument: str
    board: str
    lexicon: str
    terms_id: str = "cn_guba"
    evidence: str = ""


#: The boards. `waihui` is VERIFIED: the world crawler vaulted it on 2026-09-03 with an
#: `article_list` of 80 外汇吧 rows. The others are the board codes the desk already declares
#: (`libs.data.free_stack.GUBA_BOARDS`: HSI -> hk, GOLD -> gjgold) or Guba's 上证指数吧, none
#: reachable from the authoring container; a board that does not answer with an article list is
#: published as NO_ARTICLE_LIST and gets no series -- whether it exists is MEASURED on the box.
BOARDS: tuple[Board, ...] = (
    Board("USDCNH", "waihui", "cny", evidence="vaulted 2026-09-03 (80 rows)"),
    Board("CHINAH", "zssh000001", "equity", evidence="unverified from the build container"),
    Board("HK50", "hk", "equity", evidence="free_stack.GUBA_BOARDS['HSI']; unverified"),
    Board("XAUUSD", "gjgold", "equity", evidence="free_stack.GUBA_BOARDS['GOLD']; unverified"),
)

#: Sources this organ declares but does not fetch, and why. Never worked around.
DECLARED_BLOCKED: dict[str, str] = {
    "xueqiu": ("BLOCKED: Xueqiu serves board/status posts only after a WAF challenge "
               "(xueqiu.com answers a `_waf_` renderData page -- world-crawler vault "
               "2026-09-02; acw_sc__v2 recorded by libs.data.free_stack and libs.data.cn_sources "
               "2026-08-01) and an xq_a_token cookie. Clearing either is an anti-bot bypass "
               "(access_classifier.HARD_BOUNDARY: no bypassing an access control), so no request "
               "is made; Guba ships alone."),
}

Fetch = Callable[[str, Mapping[str, str] | None, bytes | None], bytes]


# ------------------------------------------------------------------------------------ helpers
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


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


# --------------------------------------------------------------------------------------- gate
def terms_gate(terms_id: str, terms_path: Path = TERMS) -> tuple[str, str]:
    """The source's own terms row in free_stack_sources.json, fail closed: (LIVE|HELD, why)."""
    doc = _read_json(terms_path, {}) or {}
    rows = doc.get("sources") if isinstance(doc, dict) else None
    row = next((r for r in rows or [] if isinstance(r, dict) and r.get("id") == terms_id), None)
    if row is None:
        return HELD, f"no terms row `{terms_id}` in {terms_path.name}: held (fail closed)"
    if str(row.get("auth") or "").lower() != "none":
        return HELD, f"terms row `{terms_id}` needs auth={row.get('auth')!r}: held"
    if row.get("machine_use_allowed") is not True:
        return HELD, f"terms row `{terms_id}` does not declare machine_use_allowed: held"
    return LIVE, f"terms row `{terms_id}`: {row.get('licence')}"


def robots_gate(url: str, fetch: Fetch, cache: dict[str, Any]) -> tuple[str, str]:
    """(ALLOWED | ROBOTS_DISALLOWED | ROBOTS_UNREADABLE, why) for this agent on `url`. RFC 9309:
    a 4xx robots.txt allows everything; a 5xx or an unreachable one allows nothing this pass.
    robots.txt is read once per host per pass (`cache`)."""
    from urllib.robotparser import RobotFileParser

    parts = urllib.parse.urlsplit(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    if robots not in cache:
        try:
            body = fetch(robots, None, None).decode("utf-8", "replace")
            rp = RobotFileParser()
            rp.parse(body.splitlines())
            cache[robots] = rp
        except Exception as exc:
            reason = str(getattr(exc, "reason", "") or type(exc).__name__)
            code = reason[5:] if reason.startswith("http_") else ""
            cache[robots] = ("allow_all" if code.isdigit() and 400 <= int(code) < 500
                             else f"unreachable ({reason})")
    got = cache[robots]
    if got == "allow_all":
        return "ALLOWED", "robots.txt absent (4xx): allowed per RFC 9309"
    if isinstance(got, str):
        return "ROBOTS_UNREADABLE", f"robots.txt {got}: not fetched this pass (RFC 9309)"
    if got.can_fetch(ROBOTS_AGENT, url):
        return "ALLOWED", "robots.txt allows this path"
    return "ROBOTS_DISALLOWED", "robots.txt disallows this path"


# -------------------------------------------------------------------------------------- store
def _post_row(p: crt.BoardPost) -> dict[str, Any]:
    row = asdict(p)
    row["first_seen_at"] = p.first_seen_at.isoformat()
    row["published_at"] = p.published_at.isoformat() if p.published_at else None
    return row


def load_posts(path: Path) -> list[crt.BoardPost]:
    out: list[crt.BoardPost] = []
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()[-MAX_POSTS:]
    except OSError:
        return out
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        seen = _ts(r.get("first_seen_at")) if isinstance(r, dict) else None
        if seen is None or not r.get("post_id") or not r.get("board"):
            continue
        out.append(crt.BoardPost(
            board=str(r["board"]), post_id=str(r["post_id"]), title=str(r.get("title") or ""),
            published_at=_ts(r.get("published_at")), first_seen_at=seen,
            author=str(r.get("author") or ""), pinned=bool(r.get("pinned")),
            post_type=int(r.get("post_type") or 0), bar_code=str(r.get("bar_code") or "")))
    return out


class _Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        known = {(p.board, p.post_id) for p in load_posts(root / "posts.jsonl")}
        self.seen: set[tuple[str, str]] = known
        self.obs: dict[str, dict[str, int]] = _read_json(root / "observations.json", {}) or {}
        self.new: list[dict[str, Any]] = []

    def observe(self, board: str, at: datetime, posts: Sequence[crt.BoardPost]) -> int:
        day = at.date().isoformat()
        per = self.obs.setdefault(board, {})
        per[day] = int(per.get(day, 0)) + 1
        fresh = 0
        for p in posts:
            if (p.board, p.post_id) in self.seen:
                continue
            self.seen.add((p.board, p.post_id))
            self.new.append(_post_row(p))
            fresh += 1
        return fresh

    def flush(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.new:
            with (self.root / "posts.jsonl").open("a", encoding="utf-8") as fh:
                for r in sorted(self.new, key=lambda r: r["first_seen_at"]):
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            self.new = []
        _atomic(self.root / "observations.json", json.dumps(self.obs, sort_keys=True))


# -------------------------------------------------------------------------------------- fetch
def fetch_pass(now: datetime, store: _Store, *, fetch: Fetch, boards: Sequence[Board] = BOARDS,
               terms_path: Path = TERMS, budget_s: float = 40.0,
               pause_s: float = 2.0) -> dict[str, Any]:
    """One request per allowed board, no retry; every board gets a posture."""
    started = time.monotonic()
    robots_cache: dict[str, Any] = {}
    postures: dict[str, Any] = {}
    requests = 0
    for b in boards:
        url = GUBA_LIST.format(board=b.board)
        verdict, why = terms_gate(b.terms_id, terms_path)
        if verdict != LIVE:
            postures[b.board] = {"posture": HELD, "why": why}
            continue
        if time.monotonic() - started > budget_s:
            postures[b.board] = {"posture": "NOT_REACHED", "why": "pass budget exhausted"}
            continue
        rstate, rwhy = robots_gate(url, fetch, robots_cache)
        if rstate != "ALLOWED":
            postures[b.board] = {"posture": rstate, "why": rwhy}
            continue
        if pause_s > 0:
            time.sleep(pause_s)                  # paced after robots.txt and between boards
        requests += 1
        try:
            raw = fetch(url, {"Referer": "https://guba.eastmoney.com/",
                              "Accept-Language": "zh-CN,zh;q=0.9"}, None)
        except Exception as exc:
            postures[b.board] = {"posture": "UNREACHABLE",
                                 "why": str(getattr(exc, "reason", "") or type(exc).__name__)}
            continue
        posts = crt.parse_board(raw.decode("utf-8", "replace"), b.board, now)
        if posts is None:
            postures[b.board] = {"posture": "NO_ARTICLE_LIST",
                                 "why": "the page carried no article_list: missing board, "
                                        "layout change or a challenge page -- not a quiet board"}
            continue
        fresh = store.observe(b.board, now, posts)
        postures[b.board] = {"posture": "OK", "n": len(posts), "new": fresh, "robots": rwhy}
    return {"at": now.isoformat(timespec="seconds"), "requests": requests, "postures": postures}


def harvest_vault(store: _Store, *, vault: Path = VAULT, boards: Sequence[Board] = BOARDS,
                  now: datetime | None = None) -> dict[str, Any]:
    """Every vaulted Guba list page not yet harvested, as an observation at its `fetched_utc`."""
    done: set[str] = set(_read_json(store.root / "vault_seen.json", []) or [])
    by_url = {GUBA_LIST.format(board=b.board).split("://", 1)[1]: b.board for b in boards}
    pages = new = 0
    try:
        files = sorted(vault.glob("*.gz"))
    except OSError:
        files = []
    for f in files:
        if f.name in done:
            continue
        done.add(f.name)
        try:
            got = crt.split_vault_page(gzip.decompress(f.read_bytes()))
        except (OSError, EOFError, ValueError):
            continue
        if got is None:
            continue
        meta, html = got
        board = by_url.get(str(meta["url"]).split("://", 1)[-1])
        at = _ts(meta.get("fetched_utc"))
        if board is None or at is None or (now is not None and at > now):
            continue
        posts = crt.parse_board(html, board, at)
        if posts is None:
            continue
        pages += 1
        new += store.observe(board, at, posts)
    _atomic(store.root / "vault_seen.json", json.dumps(sorted(done)))
    return {"pages": pages, "new_posts": new}


# -------------------------------------------------------------------------------------- build
def _llm_chat() -> tuple[crt.ChatFn | None, str]:
    if os.environ.get("QUANT_CN_TONE_LLM", "0") != "1":
        return None, "off (set QUANT_CN_TONE_LLM=1 to run the free-tier second reader)"
    try:
        from libs.ops import llm_seat
    except Exception as exc:
        return None, f"llm_seat unimportable: {type(exc).__name__}"
    if not llm_seat.free_tier_only():
        return None, "seat is not on the free tier (QUANT_FREE_TIER=0): this column runs free only"
    seat = llm_seat.primary_seat()
    if seat is None:
        return None, "no seat"

    def call(prompt: str, system: str) -> tuple[str, str | None]:
        return llm_seat.chat(prompt, system=system, seat=seat, max_tokens=2000, temperature=0.0)

    return call, "free tier"


def llm_pass(posts: Sequence[crt.BoardPost], now: datetime, store_root: Path, *,
             chat: crt.ChatFn | None, why: str, boards: Sequence[Board] = BOARDS,
             max_posts: int = 100) -> dict[str, Any]:
    """Score posts not yet scored, once each, stamped `scored_at`. Never raises."""
    ledger: dict[str, Any] = _read_json(store_root / "llm_tone.json", {}) or {}
    if chat is None:
        return {"state": crt.UNMEASURED, "why": why, "scored_total": len(ledger)}
    lex = {b.board: b.lexicon for b in boards}
    status: dict[str, Any] = {}
    budget = max_posts
    for board, lexicon in lex.items():
        todo = [p for p in crt.retail_posts(posts)
                if p.board == board and f"{board}|{p.post_id}" not in ledger][:budget]
        if not todo:
            continue
        scores, st = crt.llm_tones(todo, lexicon, chat, max_posts=budget)
        budget -= len(todo)
        status[board] = st
        for pid, t in scores.items():
            ledger[f"{board}|{pid}"] = {"tone": t, "scored_at": now.isoformat()}
        if budget <= 0:
            break
    _atomic(store_root / "llm_tone.json", json.dumps(ledger, sort_keys=True))
    return {"state": "RAN", "boards": status, "scored_total": len(ledger)}


def _llm_for(board: str, store_root: Path, posts: Sequence[crt.BoardPost]) -> dict[str, float]:
    """LLM scores usable PIT: made before the post's publication day closed."""
    ledger: dict[str, Any] = _read_json(store_root / "llm_tone.json", {}) or {}
    out: dict[str, float] = {}
    for p in posts:
        row = ledger.get(f"{board}|{p.post_id}")
        at = _ts((row or {}).get("scored_at"))
        if not row or at is None or p.published_at is None:
            continue
        close = datetime.combine(p.published_at.date(), datetime.min.time(), tzinfo=UTC)
        if (at - close).total_seconds() < 86400:
            out[p.post_id] = float(row["tone"])
    return out


def build_rows(now: datetime, store_root: Path, boards: Sequence[Board] = BOARDS
               ) -> list[crt.ToneRow]:
    posts = crt.retail_posts(load_posts(store_root / "posts.jsonl"))
    obs: dict[str, dict[str, int]] = _read_json(store_root / "observations.json", {}) or {}
    known: dict[str, str] = _read_json(store_root / "known_at.json", {}) or {}
    rows: list[crt.ToneRow] = []
    for b in boards:
        mine = [p for p in posts if p.board == b.board]
        rs = crt.daily_series(mine, instrument=b.instrument, board=b.board, lexicon=b.lexicon,
                              observations=obs.get(b.board) or {}, asof=now,
                              llm_tone=_llm_for(b.board, store_root, mine))
        for r in rs:
            r.known_at = known.setdefault(f"{r.instrument}|{r.day}", now.isoformat())
        rows += rs
    _atomic(store_root / "known_at.json", json.dumps(known, sort_keys=True))
    return rows


def _by_inst(rows: Sequence[crt.ToneRow]) -> dict[str, list[crt.ToneRow]]:
    out: dict[str, list[crt.ToneRow]] = {}
    for r in rows:
        out.setdefault(r.instrument, []).append(r)
    return out


def write_lake(rows: Sequence[crt.ToneRow], series_dir: Path = SERIES_DIR) -> dict[str, int]:
    import pandas as pd

    out: dict[str, int] = {}
    for inst, rs in _by_inst(rows).items():
        frame = pd.DataFrame([asdict(r) for r in rs]).drop(columns=["instrument"])
        frame.insert(1, "period", frame["day"])
        frame["source_id"] = SOURCE
        series_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(series_dir / f"{SOURCE}_{inst}.parquet", index=False)
        out[inst] = len(frame)
    return out


def axis_doc(rows: Sequence[crt.ToneRow], now: datetime) -> dict[str, Any]:
    block: dict[str, Any] = {}
    for inst, rs in _by_inst(rows).items():
        for sig in SIGNALS:
            pts = [{"d": r.available_time[:10], "v": getattr(r, sig),
                    "available_time": r.available_time, "known_at": r.known_at, "period": r.day}
                   for r in rs if math.isfinite(getattr(r, sig))]
            if pts:
                block[f"{inst}.{sig}"] = {"what": f"{sig} of the Guba {rs[0].board} board",
                                          "n": len(pts), "first": pts[0]["d"],
                                          "last": pts[-1]["d"], "points": pts}
    return {"axis": "retail_attention", "id": SOURCE, "source": SOURCE,
            "at": now.isoformat(timespec="seconds"), "n_series": len(block),
            "shape": "series[<SYMBOL>.<signal>].points [{d = knowable date, v}]",
            "pit": ("a post counts on its publication day only if observed before that day "
                    "closed; a day is knowable at next 00:00 UTC; known_at = first emission"),
            "series": block}


def source_states(fetch_rep: Mapping[str, Any]) -> dict[str, Any]:
    """LIVE vs BLOCKED per source, the line a reviewer reads first."""
    post = (fetch_rep.get("postures") or {}) if isinstance(fetch_rep, Mapping) else {}
    guba_ok = [k for k, v in post.items() if v.get("posture") == "OK"]
    out: dict[str, Any] = {"guba": {"state": LIVE if guba_ok else crt.UNMEASURED,
                                    "boards_ok_this_pass": sorted(guba_ok),
                                    "why": ("public board list pages, no login or cookie"
                                            if guba_ok else "no board answered this pass "
                                            "(see postures); vaulted pages still harvested")}}
    for sid, why in DECLARED_BLOCKED.items():
        out[sid] = {"state": BLOCKED, "why": why}
    return out


def run(now: datetime | None = None, *, fetch: bool = True, budget_s: float = 40.0,
        dry_run: bool = False, get: Fetch | None = None, store_root: Path = STORE,
        series_dir: Path = SERIES_DIR, axis_out: Path = AXIS_OUT, report: Path = REPORT,
        vault: Path = VAULT, terms_path: Path = TERMS, pause_s: float = 2.0,
        chat: crt.ChatFn | None = None, digest_path: Path = asia_alt_digest.DIGEST
        ) -> dict[str, Any]:
    """One pass: gate, fetch, harvest the vault, build, publish. `dry_run` writes nothing."""
    now = now or datetime.now(tz=UTC)
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"), "organ": SOURCE}
    store = _Store(store_root)
    if fetch and not dry_run:
        if get is None:
            from libs.data.free_stack import http_fetch
            get = http_fetch
        rep["fetch"] = fetch_pass(now, store, fetch=get, terms_path=terms_path,
                                  budget_s=budget_s, pause_s=pause_s)
    else:
        rep["fetch"] = {"state": "SKIPPED", "why": "fetch=False or dry_run"}
    rep["vault"] = harvest_vault(store, vault=vault, now=now) if not dry_run else {}
    if not dry_run:
        store.flush()
        posts = load_posts(store_root / "posts.jsonl")
        how = "injected"
        if chat is None:
            chat, how = _llm_chat()
        rep["llm"] = llm_pass(posts, now, store_root, chat=chat, why=how)
    rep["sources"] = source_states(rep["fetch"])
    rows = build_rows(now, store_root) if not dry_run else []
    rep["index_rows"] = len(rows)
    rep["instruments"] = {i: {"rows": len(rs), "first": rs[0].day, "last": rs[-1].day,
                              "n_posts": sum(r.n_posts for r in rs),
                              "n_late_excluded": sum(r.n_late for r in rs)}
                          for i, rs in _by_inst(rows).items()}
    rep["boards"] = [asdict(b) for b in BOARDS]
    if not dry_run:
        rep["lake_rows"] = write_lake(rows, series_dir)
        _atomic(axis_out, json.dumps(axis_doc(rows, now), ensure_ascii=False))
        _atomic(report, json.dumps(rep, indent=1, default=str, ensure_ascii=False))
        asia_alt_digest.publish(SOURCE, digest_section(rep), digest_path)
    return rep


def digest_section(rep: Mapping[str, Any]) -> dict[str, Any]:
    postures = (rep.get("fetch") or {}).get("postures") or {}
    ok = [b for b, v in postures.items() if v.get("posture") == "OK"]
    return asia_alt_digest.section(
        at=str(rep.get("generated_at")), status=("MEASURED_THIS_PASS" if ok
                                                 else "UNMEASURED_LIVE_YIELD"),
        rows=int(rep.get("index_rows") or 0), measured=ok,
        unmeasured=[b.board for b in BOARDS if b.board not in ok], gain={},
        postures={b: str(v.get("posture")) for b, v in sorted(postures.items())},
        sources={k: v["state"] for k, v in sorted((rep.get("sources") or {}).items())},
        vault_pages=int((rep.get("vault") or {}).get("pages") or 0),
        gain_tested_by="nlp_social_cells")
