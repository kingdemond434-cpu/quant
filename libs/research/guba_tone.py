"""CHINESE RETAIL BOARD TONE -- Guba board posts scored in Chinese, as a point-in-time daily series.

WHAT IT MEASURES. One Eastmoney Guba (股吧) board per instrument: how many retail posts the board
carried on a UTC day (ATTENTION) and which way their Chinese wording leans (TONE), published as
counted features against the board's own trailing days -- `volume_z`, `tone_mean`, `tone_delta`
(and `tone_delta_z`, `tone_shock_signed`). The scorer only PROPOSES: the series go to the lake and
`nlp_social_cells` gain-tests them against a shuffled-date placebo before any cell is donated.

NATIVE-LANGUAGE TONE, DETERMINISTIC. `lexicon_tone` is the baseline: longest-match-first over a
declared Chinese word list (涨/看多/抄底/满仓 vs 跌/看空/割肉/清仓 ...), with a negator immediately
before a term flipping it (不涨, 没跌, 别割肉). An FX board is scored on its own axis: the CNY
lexicon reads 人民币贬值/破7/购汇 as USDCNH UP and 人民币升值/结汇/红纸升值 as USDCNH DOWN, and a
升值/贬值 that names another currency (日元升值) is skipped rather than guessed. A post with no
lexicon word scores 0 and `scored=False` -- it still counts toward attention.

POINT-IN-TIME, AND NO BACKFILL. A post carries two clocks: `published_at` (the board's own
`post_publish_time`, Beijing time, converted to UTC) and `first_seen_at` (when the desk first
OBSERVED it -- a fetch or a vaulted page's `fetched_utc`). A post counts on the UTC day of its
publication ONLY IF it was observed before that day closed (`first_seen_at < next 00:00 UTC`).
A post first seen later is a LATE arrival: counted in `n_late` for audit and never folded into a
day that had already closed -- so today's pages cannot backfill yesterday's tone. A day enters
the series only if the board was observed that day (`observed`); a day the collector did not run
is UNMEASURED (no row), never a zero-attention day. Each row is `available_time` = next 00:00 UTC
and carries `known_at`, the instant a build first emitted it (the caller persists it).

Pure: numpy only, no file, no network. The organ is `desks/mt5/research/cn_retail_tone.py`.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np

from libs.research import social_mood as sm

UNMEASURED = "UNMEASURED"

#: Generic crowd-tone vocabulary for an equity-index or gold board. + bullish / - bearish.
#: Multi-character terms are matched first; the single characters 涨/跌 only score what no longer
#: term already claimed (大涨 is one bullish hit, not two).
EQUITY_LEXICON: tuple[tuple[str, int], ...] = (
    ("大涨", 1), ("暴涨", 1), ("涨停", 1), ("上涨", 1), ("拉升", 1), ("起飞", 1), ("反弹", 1),
    ("看多", 1), ("看涨", 1), ("做多", 1), ("抄底", 1), ("加仓", 1), ("满仓", 1), ("梭哈", 1),
    ("牛市", 1), ("大牛", 1), ("新高", 1), ("突破", 1), ("吃肉", 1), ("大肉", 1), ("翻红", 1),
    ("主升", 1), ("建仓", 1), ("见底", 1), ("稳了", 1), ("冲啊", 1),
    ("大跌", -1), ("暴跌", -1), ("跌停", -1), ("下跌", -1), ("跳水", -1), ("崩盘", -1),
    ("闪崩", -1), ("看空", -1), ("看跌", -1), ("做空", -1), ("割肉", -1), ("清仓", -1),
    ("跑路", -1), ("出逃", -1), ("熊市", -1), ("新低", -1), ("破位", -1), ("被套", -1),
    ("套牢", -1), ("亏损", -1), ("吃面", -1), ("大面", -1), ("翻绿", -1), ("接盘", -1),
    ("站岗", -1), ("见顶", -1), ("崩了", -1),
    ("涨", 1), ("跌", -1),
)
#: USDCNH axis: + = USDCNH UP (yuan weaker), - = USDCNH DOWN (yuan stronger). 红纸 is board slang
#: for the yuan; 结汇 is exporters selling dollars (yuan bid), 购汇 the reverse.
CNY_LEXICON: tuple[tuple[str, int], ...] = (
    ("人民币贬值", 1), ("人民币大跌", 1), ("红纸贬值", 1), ("美元升值", 1), ("美元走强", 1),
    ("美元大涨", 1), ("美元涨", 1), ("破7", 1), ("破七", 1), ("购汇", 1), ("贬值", 1),
    ("人民币升值", -1), ("人民币大涨", -1), ("红纸升值", -1), ("美元贬值", -1), ("美元走弱", -1),
    ("美元大跌", -1), ("美元跌", -1), ("结汇", -1), ("升值", -1),
)
LEXICONS: dict[str, tuple[tuple[str, int], ...]] = {"equity": EQUITY_LEXICON,
                                                    "cny": CNY_LEXICON}
#: A generic 升值/贬值 right after one of these names another currency, not the yuan: skipped.
_OTHER_CCY = ("日元", "欧元", "英镑", "韩元", "澳元", "加元", "瑞郎", "卢布", "港币")
_GENERIC_CCY_TERMS = frozenset({"升值", "贬值"})
_NEGATORS = ("不会", "没有", "不", "没", "别", "未", "难")


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def lexicon_hits(text: str, lexicon: str = "equity") -> tuple[int, int]:
    """(bull hits, bear hits) on the board's own axis. Longest term first; each character of the
    text is claimed by at most one term; a negator directly before a term flips it."""
    s = _norm(text)
    terms = sorted(LEXICONS[lexicon], key=lambda t: -len(t[0]))
    claimed = [False] * len(s)
    bull = bear = 0
    for term, sign in terms:
        start = 0
        while (i := s.find(term, start)) >= 0:
            start = i + 1
            j = i + len(term)
            if any(claimed[i:j]):
                continue
            if term in _GENERIC_CCY_TERMS and any(s[max(0, i - 4):i].endswith(c)
                                                  for c in _OTHER_CCY):
                for k in range(i, j):
                    claimed[k] = True
                continue
            pol = sign
            before = s[max(0, i - 2):i]
            if any(before.endswith(n) for n in _NEGATORS):
                pol = -sign
            for k in range(i, j):
                claimed[k] = True
            if pol > 0:
                bull += 1
            else:
                bear += 1
    return bull, bear


def lexicon_tone(text: str, lexicon: str = "equity") -> tuple[float, bool]:
    """((bull - bear) / (bull + bear) in [-1, 1], scored). An unscored post is (0.0, False)."""
    bull, bear = lexicon_hits(text, lexicon)
    tot = bull + bear
    return ((bull - bear) / tot, True) if tot else (0.0, False)


# ------------------------------------------------------------------------------------ parsing
@dataclass(frozen=True)
class BoardPost:
    """One board row. Titles only; the author is the board's user id reduced to a salted hash."""

    board: str
    post_id: str
    title: str
    published_at: datetime | None
    first_seen_at: datetime
    author: str = ""
    pinned: bool = False
    post_type: int = 0
    bar_code: str = ""


_ARTICLE_LIST = re.compile(r"var\s+article_list\s*=\s*(\{.*?\});", re.S)


def _bj_time(raw: Any) -> datetime | None:
    try:
        bj = datetime.strptime(f"{str(raw or '').strip()} +0800", "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None
    return bj.astimezone(UTC)


def parse_board(html: str, board: str, seen_at: datetime,
                hash_author: Callable[[Any], str] | None = None) -> list[BoardPost] | None:
    """Every row of a Guba `list,<board>.html` page (the embedded `var article_list={...}` JSON,
    the same block `libs.data.free_stack.parse_guba` reads, with the fields the tone series needs
    kept). Returns None when the page carries no article list -- not a board page, a challenge,
    or a board that does not exist -- so that is never read as a quiet board."""
    m = _ARTICLE_LIST.search(html or "")
    if not m:
        return None
    try:
        doc = json.loads(m.group(1))
    except ValueError:
        return None
    rows = doc.get("re") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return None
    if hash_author is None:
        from libs.data.free_stack import author_hash
        hash_author = author_hash
    hasher: Callable[[Any], str] = hash_author
    out: list[BoardPost] = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("post_id"):
            continue
        title = re.sub(r"\s+", " ", str(r.get("post_title") or "")).strip()
        if not title:
            continue
        try:
            ptype = int(r.get("post_type") or 0)
        except (TypeError, ValueError):
            ptype = 0
        out.append(BoardPost(
            board=board, post_id=str(r["post_id"]), title=title[:200],
            published_at=_bj_time(r.get("post_publish_time")), first_seen_at=seen_at,
            author=hasher(r.get("user_id")) if r.get("user_id") else "",
            pinned=bool(r.get("post_top_status")), post_type=ptype,
            bar_code=str(r.get("stockbar_code") or "")))
    return out


def split_vault_page(raw: bytes) -> tuple[dict[str, Any], str] | None:
    """A world-crawler vault entry is one JSON header line (`url`, `fetched_utc`) then the page."""
    head, sep, body = raw.partition(b"\n")
    if not sep:
        return None
    try:
        meta = json.loads(head.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(meta, dict) or not meta.get("url"):
        return None
    return meta, body.decode("utf-8", "replace")


def retail_posts(posts: Iterable[BoardPost]) -> list[BoardPost]:
    """The crowd's own posts: pinned rows, and rows whose bar is not this board (a cross-listed
    caifuhao article from another bar) are the platform's, not the board crowd's."""
    return [p for p in posts if not p.pinned and (not p.bar_code or p.bar_code == p.board)]


# ------------------------------------------------------------------------------------- series
@dataclass
class ToneRow:
    """One (day, instrument) reading. `available_time` is the next 00:00 UTC; `known_at` is the
    instant a build first emitted the row (filled by the organ from its own ledger)."""

    day: str
    instrument: str
    board: str
    n_posts: int
    n_scored: int
    n_late: int
    n_observations: int
    tone_mean: float
    tone_llm_mean: float
    n_llm: int
    available_time: str
    known_at: str = ""
    volume_z: float = math.nan
    tone_delta: float = math.nan
    tone_delta_z: float = math.nan
    tone_shock_signed: float = math.nan


def _utc(ts: datetime) -> datetime:
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def _day_close(day: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), datetime.min.time(), tzinfo=UTC) \
        + timedelta(days=1)


def daily_series(posts: Sequence[BoardPost], *, instrument: str, board: str, lexicon: str,
                 observations: Mapping[str, int], asof: datetime,
                 llm_tone: Mapping[str, float] | None = None) -> list[ToneRow]:
    """The board's daily rows, PIT. `observations` maps a UTC day to how many times the board was
    observed that day; only CLOSED observed days (`next 00:00 <= asof`) get a row. `llm_tone`
    (post_id -> tone) is the optional second reader, averaged into its own column."""
    cut = _utc(asof)
    days = sorted(d for d, n in observations.items() if n > 0 and _day_close(d) <= cut)
    first: dict[str, BoardPost] = {}
    for p in sorted((p for p in posts if p.board == board),
                    key=lambda q: _utc(q.first_seen_at)):
        first.setdefault(p.post_id, p)           # a post re-seen on a later fetch is ONE post
    kept, _ = sm.bot_filter([sm.Post(source=f"guba:{p.board}", ident=p.post_id, title=p.title,
                                     first_seen_at=_utc(p.first_seen_at), author=p.author,
                                     lang="zh", published_at=p.published_at)
                             for p in first.values()])
    kept_ids = {p.ident for p in kept}
    buckets: dict[str, list[BoardPost]] = {}
    late: dict[str, int] = {}
    for pid, p in first.items():
        if pid not in kept_ids or p.published_at is None:
            continue
        seen = _utc(p.first_seen_at)
        if seen > cut:
            continue
        day = _utc(p.published_at).date().isoformat()
        if seen >= _day_close(day):
            late[day] = late.get(day, 0) + 1
            continue
        buckets.setdefault(day, []).append(p)
    rows: list[ToneRow] = []
    llm = dict(llm_tone or {})
    for day in days:
        ps = buckets.get(day, [])
        tones = [lexicon_tone(p.title, lexicon) for p in ps]
        lt = [llm[p.post_id] for p in ps if p.post_id in llm and math.isfinite(llm[p.post_id])]
        rows.append(ToneRow(
            day=day, instrument=instrument, board=board, n_posts=len(ps),
            n_scored=sum(1 for _, ok in tones if ok), n_late=late.get(day, 0),
            n_observations=int(observations.get(day, 0)),
            tone_mean=round(float(np.mean([t for t, _ in tones])), 6) if tones else 0.0,
            tone_llm_mean=round(float(np.mean(lt)), 6) if lt else math.nan, n_llm=len(lt),
            available_time=_day_close(day).isoformat()))
    return features(rows)


def features(rows: Sequence[ToneRow]) -> list[ToneRow]:
    """volume_z (log1p posts), tone_delta and tone_delta_z against the PRIOR observed days'
    trailing window (`social_mood.TRAIL_DAYS`, at least `TRAIL_MIN`), never including the day."""
    rs = sorted(rows, key=lambda r: r.day)
    vol = [math.log1p(r.n_posts) for r in rs]
    tone = [r.tone_mean for r in rs]
    for i, r in enumerate(rs):
        tv, tt = sm._trail(vol, i), sm._trail(tone, i)
        if tv is not None:            # a flat history's std is float noise, not dispersion
            r.volume_z = _r((vol[i] - tv[0]) / tv[1] if tv[1] > _EPS else 0.0)
        if tt is not None:
            r.tone_delta = _r(tone[i] - tt[0])
            r.tone_delta_z = _r(r.tone_delta / tt[1] if tt[1] > _EPS else 0.0)
        if math.isfinite(r.volume_z) and math.isfinite(r.tone_delta):
            sgn = 1.0 if r.tone_delta > 0 else -1.0 if r.tone_delta < 0 else 0.0
            r.tone_shock_signed = _r(r.volume_z * sgn)
    return rs


_EPS = 1e-9


def _r(x: float) -> float:
    return round(x, 6) if math.isfinite(x) else math.nan


# --------------------------------------------------------------------------- optional LLM tier
LLM_SYSTEM = ("You score the tone of short Chinese retail forum titles for a research desk. You "
              "never forecast prices. Return JSON only.")
LLM_BATCH = 25
_SCRUB = (re.compile(r"https?://\S+"), re.compile(r"@\S+"), re.compile(r"\$[^$]{0,60}\$"),
          re.compile(r"\d{6,}"), re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"))

ChatFn = Callable[[str, str], tuple[str, str | None]]


def sanitize(title: str) -> str:
    """Title text only: no URL, handle, ticker tag, email or long digit run reaches a model."""
    s = str(title or "")
    for rx in _SCRUB:
        s = rx.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()[:120]


def llm_tones(posts: Sequence[BoardPost], lexicon: str, chat: ChatFn | None,
              *, max_posts: int = 100) -> tuple[dict[str, float], dict[str, Any]]:
    """The second reader. NEVER raises: no chat function, a refusal or an unparseable reply is
    a status, and a post without a parsed score has no LLM value (never 0)."""
    if chat is None:
        return {}, {"state": UNMEASURED, "why": "no free LLM seat"}
    axis = ("the US dollar against the Chinese yuan (+1 = yuan weaker / USDCNH up)"
            if lexicon == "cny" else "the board's own market (+1 = bullish)")
    out: dict[str, float] = {}
    errors: list[str] = []
    todo = [p for p in posts if sanitize(p.title)][:max_posts]
    for k in range(0, len(todo), LLM_BATCH):
        chunk = todo[k:k + LLM_BATCH]
        items = "\n".join(f"{i}: {sanitize(p.title)}" for i, p in enumerate(chunk))
        prompt = (f"Score each title's tone on {axis}, from -1 to 1, 0 when it has none. "
                  'Reply as {"scores": [{"i": <index>, "tone": <number>}]}.\n' + items)
        try:
            reply, err = chat(prompt, LLM_SYSTEM)
        except Exception as exc:                     # the tier never takes the pass down
            reply, err = "", f"{type(exc).__name__}: {str(exc)[:120]}"
        if err:
            errors.append(str(err)[:160])
            continue
        for row in _parse_scores(reply):
            i, t = row
            if 0 <= i < len(chunk):
                out[chunk[i].post_id] = max(-1.0, min(1.0, t))
    state = "MEASURED" if out else UNMEASURED
    return out, {"state": state, "scored": len(out), "asked": len(todo), "errors": errors[:5]}


def _parse_scores(reply: str) -> list[tuple[int, float]]:
    m = re.search(r"\{.*\}", reply or "", re.S)
    if not m:
        return []
    try:
        doc = json.loads(m.group(0))
    except ValueError:
        return []
    out: list[tuple[int, float]] = []
    for r in (doc.get("scores") if isinstance(doc, dict) else None) or []:
        try:
            t = float(r["tone"])
            i = int(r["i"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(t):
            out.append((i, t))
    return out
