"""BLOG / SOCIAL ATTENTION AND MOOD -- daily indices from Asian retail writing, as DELTAS.

THE METHOD (Pluga-style blog mining, with the HKMA's bot hygiene). Count what a retail crowd is
writing about an instrument each day (ATTENTION) and which way it leans (MOOD), from Japanese,
Korean and Chinese blogs and forums, and publish the CHANGE against the crowd's own trailing
mean -- never the level. A level is dominated by who happens to be indexed (a feed added last
month doubles "attention" and means nothing); a delta against the same crowd's own recent past is
what an overreaction looks like.

WHY THESE CROWDS (participant structure, not novelty). Japanese retail is the largest FX-margin
population outside the US and trades USDJPY and the Nikkei with a tax-year and a Mrs-Watanabe
carry habit; Korean retail is a majority of KOSPI turnover and the most leveraged semis crowd in
the world; China's A-share market is roughly four-fifths retail by turnover and T+1. Their
attention cycles are not the English-language cycle, which is why they are worth measuring.

BOT FILTERING, BEFORE ANYTHING IS COUNTED:

  duplicate_text   the same normalised text twice (URLs, digits, punctuation stripped) -- kept once
  near_duplicate   character-shingle Jaccard >= NEAR_DUP_JACCARD to a post already kept (MinHash
                   banding finds the candidates; the exact Jaccard decides)
  burst_account    an author posting more than BURST_MAX times inside BURST_WINDOW OF THE POSTS'
                   OWN PUBLISHED TIMES -- every post in the burst is dropped, because a burst IS
                   the account's signature. Keyed on `published_at`, never on the fetch instant:
                   one fetch returns a whole feed at once, and keying on it dropped any author
                   with more than BURST_MAX items per fetch (every per-blog feed). A post with no
                   published time falls back to `first_seen_at`. Single-author blog feeds
                   (SINGLE_AUTHOR_FEED_SOURCES: one configured blog per feed id) are exempt --
                   the feed IS one author by construction, so a burst test measures nothing.

POINT-IN-TIME: a post counts on the UTC day of `first_seen_at` (when the desk first fetched it),
never its claimed publication time, which a feed can back-date. `daily_index(posts, asof=t)`
drops every post first seen after `t`, and a day's row is stamped available at the following
00:00 UTC. A day the collector never ran is UNMEASURED (NaN), never a zero-attention day.

Pure: numpy only, no file, no network. The desk organ is `desks/mt5/research/blog_social_mining.py`.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta

import numpy as np

__all__ = [
    "INSTRUMENT_TOPICS",
    "TOPIC_KEYWORDS",
    "BotReport",
    "IndexRow",
    "Post",
    "bot_filter",
    "daily_index",
    "deltas",
    "mood_of",
    "topics_of",
]

#: keyword -> topic. Substring match on the lower-cased title + snippet; CJK has no word bounds.
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "jp_equity": ("日経平均", "日経225", "日本株", "日経", "株価", "株"),
    "jpy": ("円安", "円高", "ドル円", "為替"),
    "kr_equity": ("코스피", "코스닥", "국내 증시", "국장"),
    "semis": ("삼성전자", "sk하이닉스", "하이닉스", "반도체", "半导体", "芯片", "半導体",
              "nvidia", "엔비디아", "英伟达", "tsmc", "台积电", "마이크론", "美光"),
    "krw": ("환율", "원달러", "원화"),
    "cn_equity": ("a股", "沪指", "上证", "大盘", "沪深"),
    "hk_equity": ("港股", "恒指", "恒生"),
    "cny": ("人民币", "离岸人民币", "汇率"),
}

#: topic -> instrument -> orientation of the topic's MOOD on that instrument's own axis. `jpy`
#: mood is written in USDJPY terms already (円安 = USDJPY up); a bullish KOSPI crowd reads as a
#: stronger won, i.e. USDKRW DOWN. The sign is the quoting convention, never a forecast.
INSTRUMENT_TOPICS: dict[str, dict[str, int]] = {
    "jp_equity": {"JPN225": 1},
    "jpy": {"USDJPY": 1},
    "kr_equity": {"USDKRW": -1},
    "semis": {"NVIDIA": 1, "MicronTechnology": 1, "TSMC": 1, "AMD": 1, "Intel": 1},
    "krw": {"USDKRW": 1},
    "cn_equity": {"CHINAH": 1, "HK50": 1},
    "hk_equity": {"HK50": 1, "CHINAH": 1},
    "cny": {"USDCNH": 1},
}

#: Crowd-mood vocabulary, generic across topics. + bullish / - bearish.
_MOOD: tuple[tuple[str, int], ...] = (
    # ja
    ("爆上げ", 1), ("上昇", 1), ("反発", 1), ("買い増し", 1), ("強気", 1), ("最高値", 1),
    ("爆益", 1), ("ロング", 1), ("暴落", -1), ("下落", -1), ("急落", -1), ("売り", -1),
    ("弱気", -1), ("損切り", -1), ("含み損", -1), ("ショート", -1), ("大損", -1),
    # ko
    ("떡상", 1), ("상승", 1), ("반등", 1), ("매수", 1), ("풀매수", 1), ("가즈아", 1), ("불장", 1),
    ("떡락", -1), ("하락", -1), ("폭락", -1), ("매도", -1), ("손절", -1), ("물렸", -1),
    ("한강", -1),
    # zh
    ("大涨", 1), ("涨停", 1), ("牛市", 1), ("看多", 1), ("抄底", 1), ("反弹", 1), ("上涨", 1),
    ("大跌", -1), ("跌停", -1), ("熊市", -1), ("看空", -1), ("割肉", -1), ("暴跌", -1),
    ("下跌", -1), ("被套", -1),
    # en (Latin titles on the same forums)
    ("bullish", 1), ("rally", 1), ("to the moon", 1), ("bearish", -1), ("crash", -1),
    ("sell-off", -1),
)
#: Topic-specific directional words, oriented to the topic's INSTRUMENT axis (see above).
_TOPIC_MOOD: dict[str, tuple[tuple[str, int], ...]] = {
    "jpy": (("円安", 1), ("円高", -1), ("介入", -1)),
    "krw": (("환율 상승", 1), ("환율 급등", 1), ("원화 약세", 1), ("환율 하락", -1),
            ("원화 강세", -1)),
    "cny": (("人民币贬值", 1), ("贬值", 1), ("人民币升值", -1), ("升值", -1)),
}

NEAR_DUP_JACCARD = 0.8
SHINGLE = 3
MINHASH_K = 16
BANDS = 8
BURST_MAX = 5
BURST_WINDOW = timedelta(hours=1)
#: Sources whose every feed is ONE configured blog (`{id}` in the source URL of
#: `libs.data.blog_social_sources`): exempt from the burst test.
SINGLE_AUTHOR_FEED_SOURCES: frozenset[str] = frozenset({"ameblo_user_rss", "livedoor_user_rss"})
TRAIL_DAYS = 28
TRAIL_MIN = 7


@dataclass(frozen=True)
class Post:
    source: str
    ident: str
    title: str
    first_seen_at: datetime
    snippet: str = ""
    author: str = ""
    url: str = ""
    lang: str = ""
    published_at: datetime | None = None

    @property
    def text(self) -> str:
        return f"{self.title} {self.snippet}".strip()


def _utc(ts: datetime) -> datetime:
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def topics_of(text: str) -> tuple[str, ...]:
    low = unicodedata.normalize("NFKC", str(text or "")).lower()
    return tuple(t for t, kws in TOPIC_KEYWORDS.items() if any(k in low for k in kws))


def mood_of(text: str, topic: str = "") -> float:
    """(bull - bear) / (bull + bear) in [-1, 1]; 0.0 for a post that carries no mood word."""
    low = unicodedata.normalize("NFKC", str(text or "")).lower()
    bull = bear = 0
    for term, s in _TOPIC_MOOD.get(topic, ()) + _MOOD:
        if term in low:
            n = low.count(term)
            low = low.replace(term, " ")
            if s > 0:
                bull += n
            else:
                bear += n
    tot = bull + bear
    return (bull - bear) / tot if tot else 0.0


# --------------------------------------------------------------------------------- bot filter
_URL = re.compile(r"https?://\S+")


def _normal(text: str) -> str:
    s = unicodedata.normalize("NFKC", _URL.sub(" ", str(text or ""))).lower()
    return "".join(ch for ch in s if ch.isalpha())


def _shingles(norm: str) -> set[str]:
    if len(norm) <= SHINGLE:
        return {norm} if norm else set()
    return {norm[i:i + SHINGLE] for i in range(len(norm) - SHINGLE + 1)}


def _h(s: str, seed: int) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8,
                                          salt=seed.to_bytes(8, "little")).digest(), "little")


def _minhash(sh: set[str]) -> tuple[int, ...]:
    if not sh:
        return (0,) * MINHASH_K
    return tuple(min(_h(x, k) for x in sh) for k in range(MINHASH_K))


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


@dataclass(frozen=True)
class BotReport:
    n_in: int
    n_kept: int
    dropped: Mapping[str, int]


def _posted_at(p: Post) -> datetime:
    """The post's own time: its published time, else (no stamp in the feed) its first sighting."""
    return _utc(p.published_at) if p.published_at is not None else _utc(p.first_seen_at)


def bot_filter(posts: Sequence[Post], *,
               single_author_sources: Iterable[str] = SINGLE_AUTHOR_FEED_SOURCES
               ) -> tuple[list[Post], BotReport]:
    """Drop duplicate text, near-identical posts and burst accounts. Order = first_seen_at."""
    ordered = sorted(posts, key=lambda p: (_utc(p.first_seen_at), p.source, p.ident))
    dropped = {"duplicate_text": 0, "near_duplicate": 0, "burst_account": 0}
    exempt = frozenset(single_author_sources)
    # BURSTS FIRST: an account whose posts are all dropped as a burst must not seed the
    # duplicate index and take an honest author's identical-looking post down with it.
    by_author: dict[str, list[int]] = {}
    for i, p in enumerate(ordered):
        if p.author and p.source not in exempt:
            by_author.setdefault(f"{p.source}:{p.author}", []).append(i)
    burst: set[int] = set()
    for members in by_author.values():
        idxs = sorted(members, key=lambda i: _posted_at(ordered[i]))
        times = [_posted_at(ordered[i]) for i in idxs]
        lo = 0
        for hi in range(len(idxs)):
            while times[hi] - times[lo] > BURST_WINDOW:
                lo += 1
            if hi - lo + 1 > BURST_MAX:
                burst.update(idxs[lo:hi + 1])
    exact: set[str] = set()
    buckets: dict[tuple[int, tuple[int, ...]], list[int]] = {}
    kept_sh: dict[int, set[str]] = {}
    kept: list[Post] = []
    rows = MINHASH_K // BANDS
    for i, p in enumerate(ordered):
        if i in burst:
            dropped["burst_account"] += 1
            continue
        norm = _normal(p.text)
        if not norm:
            kept.append(p)
            continue
        key = hashlib.sha1(norm.encode()).hexdigest()
        if key in exact:
            dropped["duplicate_text"] += 1
            continue
        sh = _shingles(norm)
        sig = _minhash(sh)
        bands = [(b, sig[b * rows:(b + 1) * rows]) for b in range(BANDS)]
        cands = {j for band in bands for j in buckets.get(band, [])}
        if any(_jaccard(sh, kept_sh[j]) >= NEAR_DUP_JACCARD for j in cands):
            dropped["near_duplicate"] += 1
            continue
        exact.add(key)
        kept_sh[i] = sh
        for band in bands:
            buckets.setdefault(band, []).append(i)
        kept.append(p)
    return kept, BotReport(n_in=len(posts), n_kept=len(kept), dropped=dropped)


# ----------------------------------------------------------------------------------- indices
@dataclass(frozen=True)
class IndexRow:
    """One (day, instrument) reading. Levels are carried for audit; the published signals are the
    deltas (`attention_delta_z`, `mood_delta`, `mood_delta_z`, `attention_shock_signed`)."""

    day: str
    instrument: str
    n_posts: int
    attention: float
    mood: float
    n_mood: int
    available_time: str
    attention_delta_z: float = math.nan
    mood_delta: float = math.nan
    mood_delta_z: float = math.nan
    attention_shock_signed: float = math.nan


def _next_midnight(day: str) -> str:
    return (datetime.combine(date.fromisoformat(day), datetime.min.time(), tzinfo=UTC)
            + timedelta(days=1)).isoformat()


def daily_index(posts: Iterable[Post], *, observed_days: Iterable[str],
                asof: datetime | None = None) -> list[IndexRow]:
    """(day, instrument) attention and mood from FILTERED posts, PIT on `first_seen_at`.

    `observed_days` are the UTC days the collector actually ran; only those days get a row, and
    an instrument with no post on an observed day reads attention 0 -- a measured quiet day. A day
    outside `observed_days` has no row at all and is UNMEASURED downstream.
    """
    cut = _utc(asof) if asof is not None else None
    days = sorted({str(d) for d in observed_days})
    if cut is not None:
        days = [d for d in days if date.fromisoformat(d) <= cut.date()]
    counts: dict[tuple[str, str], int] = {}
    moods: dict[tuple[str, str], list[float]] = {}
    for p in posts:
        seen = _utc(p.first_seen_at)
        if cut is not None and seen > cut:
            continue
        day = seen.date().isoformat()
        for topic in topics_of(p.text):
            m = mood_of(p.text, topic)
            for inst, orient in INSTRUMENT_TOPICS.get(topic, {}).items():
                counts[(day, inst)] = counts.get((day, inst), 0) + 1
                if m != 0.0:
                    moods.setdefault((day, inst), []).append(orient * m)
    insts = sorted({i for per in INSTRUMENT_TOPICS.values() for i in per})
    out: list[IndexRow] = []
    for day in days:
        for inst in insts:
            n = counts.get((day, inst), 0)
            ms = moods.get((day, inst), [])
            out.append(IndexRow(day=day, instrument=inst, n_posts=n,
                                attention=round(math.log1p(n), 6),
                                mood=round(float(np.mean(ms)), 6) if ms else 0.0,
                                n_mood=len(ms), available_time=_next_midnight(day)))
    return deltas(out)


def _trail(values: list[float], i: int) -> tuple[float, float] | None:
    lo = max(0, i - TRAIL_DAYS)
    seg = [v for v in values[lo:i] if math.isfinite(v)]
    if len(seg) < TRAIL_MIN:
        return None
    arr = np.asarray(seg, dtype=float)
    return float(arr.mean()), float(arr.std(ddof=1)) if arr.size > 1 else 0.0


def deltas(rows: Sequence[IndexRow]) -> list[IndexRow]:
    """Change against the trailing mean of the PRIOR `TRAIL_DAYS` observed days (strictly before
    today, so a day never normalises itself). Fewer than `TRAIL_MIN` prior days is NaN."""
    by_inst: dict[str, list[IndexRow]] = {}
    for r in rows:
        by_inst.setdefault(r.instrument, []).append(r)
    out: list[IndexRow] = []
    for inst_rows in by_inst.values():
        inst_rows = sorted(inst_rows, key=lambda r: r.day)
        att = [r.attention for r in inst_rows]
        mood = [r.mood for r in inst_rows]
        for i, r in enumerate(inst_rows):
            ta, tm = _trail(att, i), _trail(mood, i)
            az = md = mz = sh = math.nan
            if ta is not None:
                az = (r.attention - ta[0]) / ta[1] if ta[1] > 0 else 0.0
            if tm is not None:
                md = r.mood - tm[0]
                mz = md / tm[1] if tm[1] > 0 else 0.0
            if math.isfinite(az) and math.isfinite(md):
                sh = az * (1.0 if md > 0 else -1.0 if md < 0 else 0.0)
            out.append(replace(r, attention_delta_z=_r(az), mood_delta=_r(md),
                               mood_delta_z=_r(mz), attention_shock_signed=_r(sh)))
    return sorted(out, key=lambda r: (r.day, r.instrument))


def _r(x: float) -> float:
    return round(x, 6) if math.isfinite(x) else math.nan
