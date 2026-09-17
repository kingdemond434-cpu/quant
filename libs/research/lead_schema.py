"""ONE LEAD SCHEMA -- every paper, story, forum post, competition record, filing, data release
and broker change the intelligence layer finds, in a single shape.

WHY THIS EXISTS (W2 / Q17 memory banks, principal 2026-09-16). The desk reads seventy-six seat
directories, five hundred declared grounds, a frontier queue and a deep forest, and each producer
writes its own dict. Measured on this tree the same idea arrives as at least six different rows:

    hypothesis      {"kind":"hypothesis","family":...,"symbols":[...],"source":"literature",...}
    story_mechanism {"kind":"story_mechanism","claim":...,"ground":...,"mechanism_class":...}
    dataset         {"kind":"dataset","endpoints":[...],"dataset_class":...,"host":...}
    crawler row     {"source":"reddit","title":...,"symbols":[...],"patterns":[...]}
    paper           {"source":"arxiv_qfin","kind":"paper","title":...,"text":...}
    frontier        {"candidate_id":...,"claim":...,"firm":...,"evidence_grade":...}

`miner_candidate_compiler` reads all six and mints candidates; nothing ever held the LEAD itself,
so the desk could say how many candidates it compiled and never "what do we know about gold, where
did it come from, and what did it become". This module is that missing noun. It converts, it never
judges: no row is scored, refused or ranked here.

THREE THINGS IT IS DELIBERATE ABOUT.

**A DOCUMENT IS NOT A CLAIM.** An arXiv abstract carries five assertions and a 七禾网 interview
twenty; storing the document as one lead makes "five sources agree" unmeasurable and buries the
one testable sentence inside four paragraphs of context. `claims_from_text` splits a document into
claim-bearing sentences -- a sentence with a number, an instrument or a mechanism verb -- and each
Lead is ONE claim carrying its `doc_id` and `claim_index`, so the document is still reconstructible
and the claim is the unit that gets counted, deduplicated and contradicted.

**VERBATIM OR IT IS NOT EVIDENCE.** `claim_text` is the source's own words, bounded, never a
paraphrase; `quality.verbatim` is False when the row gave nothing but a title, because a title is a
label and an extractor has nothing to work on. A summarised claim cannot be audited back to its
ground, and the desk's licence position (concept reimplemented, provenance cited) depends on the
citation being exact.

**INCOMPLETE IS LOW PRIORITY, NEVER DROPPED (principal 2026-09-16).** The fourteen-field
`structured` block is the full specification of an edge -- who pays, what constrains them, why it
can persist, what would falsify it. Almost nothing arrives with all fourteen. A lead missing some
is `priority="low"` and stays in the intake with `structured_complete=False`, because absence is a
measurement (L1.28a) and a queue that silently discards its own backlog cannot report one.

WHAT JOINS A LEAD TO THE REST OF THE DESK. `libs/research/hypothesis_graph.record_candidates`
stamps every compiled candidate with `seed_key = sha256({"s": source, "t": title, "u": url})[:16]`
(and, when the candidate names no parent cell, into `parent` as well, which is where it lived
alone until 2026-09-17). That hash IS how a cell names the lead it came from,
and `compiler_parent_key` reproduces it exactly, so `provenance["cell_key"]` on a Lead is the
join key into `hypothesis_graph.jsonl`; `cell_seed_key` reads it back off a graph row.
Verified on the live ledger: `miner:reddit`/`miner:youtube`/`miner:forexfactory`/`miner:cot`
parents resolve back to rows still sitting in `data/intelligence/`.

Adapts and validates. Fetches nothing, writes nothing, decides nothing.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

__all__ = [
    "KINDS",
    "MAX_CLAIMS_PER_DOC",
    "MAX_CLAIM_CHARS",
    "PIT_STATUSES",
    "PRIORITY_LOW",
    "PRIORITY_NORMAL",
    "SPEC_FIELDS",
    "Lead",
    "blank_spec",
    "cell_seed_key",
    "claims_from_text",
    "compiler_parent_key",
    "dedupe_key",
    "direction_of",
    "doc_id_of",
    "from_intelligence_row",
    "from_row",
    "lead_id_of",
    "leads_from_intelligence_row",
    "row_cell_key",
    "structured_complete",
    "title_key",
    "to_row",
    "token_cosine",
    "token_set",
    "urls_in_text",
    "validate",
]

#: What a lead IS. `other` is a real answer -- a row the desk cannot classify is carried and
#: counted, never dropped, because the unclassified population is the frontier's own measurement.
KINDS: tuple[str, ...] = ("paper", "story", "forum", "competition", "filing", "data_release",
                          "broker_change", "other")

#: The fourteen fields of a fully specified edge (principal 2026-09-16). EXACTLY these, in this
#: order: a block with more is a different schema and a block with fewer is an incomplete lead,
#: which is a state this module records rather than a row it refuses.
SPEC_FIELDS: tuple[str, ...] = (
    "actor", "constraint", "counterparty", "mechanism", "why_edge_can_persist", "asset_mapping",
    "horizon", "session", "required_data", "pit_status", "expected_cost", "falsifier", "source",
    "language",
)

#: Point-in-time honesty of the claim's own data. UNKNOWN is the default and is not a failure.
PIT_STATUSES: tuple[str, ...] = ("PIT_CLEAN", "LAGGED", "UNKNOWN", "NOT_PIT")

PRIORITY_LOW = "low"
PRIORITY_NORMAL = "normal"

#: A claim is a sentence, not a corpus. 2,000 characters holds the longest real claim measured on
#: this tree (a 七禾网 story with its numbers) and refuses a scraped page body pretending to be one.
MAX_CLAIM_CHARS = 2000
#: Claims carried from ONE document. A page that yields more than this is a listing, not a claim.
MAX_CLAIMS_PER_DOC = 12
#: The compiler truncates a candidate's `source_title` here, so the join key must too.
MAX_TITLE_CHARS = 300

# --------------------------------------------------------------------------- vocabularies
#: Instrument tokens a claim-bearing sentence may name. ISO codes are listed rather than matched
#: as "any six letters", which would make `market`, `signal` and `return` into instruments and
#: every sentence in every document claim-bearing.
_CCY_TOKENS = """USD EUR JPY GBP AUD NZD CAD CHF CNH CNY SEK NOK DKK PLN HUF CZK TRY ZAR MXN
SGD HKD KRW INR BRL ILS RUB THB"""
_CCY = frozenset(_CCY_TOKENS.split())
_INSTRUMENT_TOKENS = """xauusd xagusd xtiusd gold silver oil crude wti brent copper us500 us30
nas100 ger40 uk100 jp225 aus200 hk50 fra40 esp35 btcusd ethusd bitcoin ethereum dxy vix
黄金 白银 原油 螺纹钢 沪金 恒生 金"""
_INSTRUMENT_WORDS = frozenset(_INSTRUMENT_TOKENS.split())
_PAIR_RE = re.compile(r"(?<![a-z])([a-z]{3})\s?[/\-]?\s?([a-z]{3})(?![a-z])")

#: Verbs and nouns that make a sentence a CLAIM about a market rather than a description of one.
_CLAIM_TOKENS = """predict predicts predicted forecast leads lags lagged revert reverts reversion
breakout breaks break rally rallies rise rises rose fall falls fell drop drops outperform
underperform returns return yield carry spread premium discount momentum trend persists persist
decay decays correlate correlated buy sell long short hedge fade fades squeeze gap gaps drift
drifts seasonal significant sharpe drawdown winrate impact liquidity cost costs volatility flow
flows imbalance basis funding fix fixing session overnight rollover settlement
胜率 回撤 收益 突破 回归 趋势 反转 上涨 下跌 做多 做空 基差 换月"""
_CLAIM_WORDS = frozenset(_CLAIM_TOKENS.split())

#: Direction, for CONTRADICTS. Substring-matched so `rising`, `appreciates` and `bullishly` all
#: land; the pair is deliberately symmetric so neither side is the default.
_DIR_UP = ("long", "buy", "bull", "rise", "rises", "rising", "rose", "rally", "higher", "up ",
           "positive", "outperform", "appreciat", "gain", "上涨", "做多", "买入", "看涨")
_DIR_DOWN = ("short", "sell", "bear", "fall", "falls", "falling", "fell", "lower", "down ",
             "negative", "underperform", "depreciat", "decline", "下跌", "做空", "卖出", "看跌")

#: Row `kind` -> lead kind. The desk's producers already say what they found; this reads them
#: rather than guessing from prose.
_KIND_BY_ROW_KIND: dict[str, str] = {
    "paper": "paper", "article": "paper", "preprint": "paper", "academic": "paper",
    "story_mechanism": "story", "story": "story", "claim": "story", "interview": "story",
    "forum": "forum", "qa": "forum", "post": "forum", "thread": "forum", "video": "forum",
    "competition": "competition", "contest": "competition", "leaderboard": "competition",
    "signal": "competition", "track_record": "competition",
    "filing": "filing", "form4": "filing", "edgar": "filing", "regulatory": "filing",
    "dataset": "data_release", "data": "data_release", "release": "data_release",
    "calendar": "data_release", "event": "data_release", "vintage": "data_release",
    "swap": "broker_change", "broker": "broker_change", "swap_table": "broker_change",
    "hypothesis": "other", "anomaly": "other", "dropped": "other",
}

#: Producer name -> lead kind, matched as a substring on the row's `source`/`ground`/`seat`. Only
#: producers whose OUTPUT is uniformly one kind are listed; anything else stays `other`.
_KIND_BY_SOURCE: tuple[tuple[str, str], ...] = (
    ("arxiv", "paper"), ("ssrn", "paper"), ("literature", "paper"), ("academic", "paper"),
    ("papers", "paper"), ("bis_speeches", "filing"), ("sec_edgar", "filing"), ("form4", "filing"),
    ("cftc", "filing"), ("cot", "data_release"), ("ff_calendar", "data_release"),
    ("calendar", "data_release"), ("fred", "data_release"), ("swap", "broker_change"),
    ("broker", "broker_change"), ("reddit", "forum"), ("forexfactory", "forum"),
    ("forexpeacearmy", "forum"), ("quant_se", "forum"), ("stackexchange", "forum"),
    ("tradingview", "forum"), ("youtube", "forum"), ("bilibili", "forum"), ("zhihu", "forum"),
    ("知乎", "forum"), ("雪球", "forum"), ("七禾", "story"), ("deep_forest", "story"),
    ("mql5_signals", "competition"), ("myfxbook", "competition"), ("fxblue", "competition"),
    ("darwinex", "competition"), ("collective2", "competition"), ("copy", "competition"),
    ("signals", "competition"), ("大赛", "competition"), ("蓝海密剑", "competition"),
)

#: Ground kind (deep_forest_sources.json) -> lead kind.
_KIND_BY_GROUND_KIND: dict[str, str] = {
    "competition": "competition", "qa": "forum", "forum": "forum", "web": "story",
    "academic": "paper", "dataset": "data_release", "official": "data_release",
    "code": "forum", "video": "forum", "blog": "story",
}

#: Operational bookkeeping a miner writes about ITSELF. Never a lead (the compiler's own list,
#: `_OPERATIONAL_KINDS`, kept in step).
_OPERATIONAL_KINDS = frozenset({"walled", "fetch_error", "stub", "probe", "error", "skipped"})

#: Where a row keeps the source's OWN WORDS, best first. A title is not in this list on purpose.
_VERBATIM_FIELDS = ("claim", "text", "description", "mechanism", "body", "abstract", "summary",
                    "content", "why", "excerpt")
#: When a row has no body at all, the title is what there is -- carried, and marked not verbatim.
_TITLE_FIELDS = ("title", "name", "repo", "question", "headline")

#: WHEN THE DESK SAW IT. Crawl timestamps only.
_SEEN_FIELDS = ("found_at", "at", "seen_at", "available_time", "ingested_time", "fetched_utc",
                "crawled_at", "generated_utc")
#: WHEN THE WORLD COULD HAVE KNOWN IT. Publication timestamps only -- never a crawl time, because
#: a lead dated by the crawler is a lookahead waiting to happen.
_KNOWABLE_FIELDS = ("published_time", "published", "event_time", "posted_at", "date", "pub_date",
                    "created_at", "publication_date")

_URL_FIELDS = ("url", "link", "source_url", "href", "permalink")

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}|[一-鿿]")
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"')]+")
#: Sentence boundaries in both scripts. The CJK terminators (U+3002 ideographic full stop and the
#: fullwidth !, ? and ;) are written as escapes so they cannot be misread as their ASCII
#: lookalikes, and because they need no trailing space to end a sentence.
_SENTENCE_SPLIT = re.compile("(?<=[.!?;])\\s+|[\\n\\r]+|(?<=[\\u3002\\uff01\\uff1f\\uff1b])")
_WS = re.compile(r"\s+")


# --------------------------------------------------------------------------- the lead

@dataclass(frozen=True)
class Lead:
    """One atomic claim, with where it came from and everything the desk could read off it.

    Frozen on purpose: a lead is a RECORD of what a source said at a moment. Enriching it later
    means writing a new lead with a new `seen_at`, not editing the evidence.
    """

    lead_id: str
    kind: str
    source_id: str
    url_or_ref: str
    seen_at: str
    knowable_at: str
    language: str
    claim_text: str
    doc_id: str
    claim_index: int
    mechanism_ids: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    axes: dict[str, str] = field(default_factory=dict)
    asset_classes: list[str] = field(default_factory=list)
    testable: bool = False
    #: The fourteen-field edge specification, or None when the row declared none of it.
    structured: dict[str, Any] | None = None
    #: The EXECUTABLE triple the compiler's intake speaks in: family, params, symbols. Separate
    #: from `structured` because the principal's block is exactly fourteen named fields and a
    #: family name is not one of them -- but dropping the family would throw away the only part
    #: of a seat's hypothesis row the gauntlet can run.
    executable: dict[str, Any] | None = None
    structured_complete: bool = False
    priority: str = PRIORITY_NORMAL
    provenance: dict[str, str] = field(default_factory=dict)
    quality: dict[str, bool] = field(default_factory=dict)

    def dedupe_key(self) -> str:
        """The CLAIM's identity, across every source that ever tells it."""
        return dedupe_key(self)

    def spec_gaps(self) -> list[str]:
        """Which of the fourteen fields this lead does not have. Empty means complete."""
        block = self.structured or {}
        return [f for f in SPEC_FIELDS if _empty(block.get(f))]


def blank_spec() -> dict[str, Any]:
    """The fourteen fields, all None. The shape every `structured` block has."""
    return dict.fromkeys(SPEC_FIELDS)


def structured_complete(block: Mapping[str, Any] | None) -> bool:
    """All fourteen fields present and non-empty. A block with extra keys is NOT complete --
    it is a different schema, and saying otherwise would make the field unfalsifiable."""
    if not block:
        return False
    if set(block) != set(SPEC_FIELDS):
        return False
    return not any(_empty(block[f]) for f in SPEC_FIELDS)


# --------------------------------------------------------------------------- identities

def _norm_claim(text: str) -> str:
    return _WS.sub(" ", str(text or "")).strip().lower()


def lead_id_of(source_id: str, claim_text: str) -> str:
    """sha of source + claim: the same sentence from two grounds is two leads, one claim."""
    payload = f"{str(source_id or '').strip().lower()}\x00{_norm_claim(claim_text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def doc_id_of(source_id: str, url: str, title: str) -> str:
    """The DOCUMENT a claim was cut out of, so a split page is still one page."""
    payload = json.dumps({"s": str(source_id or ""), "u": str(url or ""),
                          "t": str(title or "")[:MAX_TITLE_CHARS]},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def dedupe_key(lead: Lead) -> str:
    """One key per CLAIM. Five grounds repeating a story collapse onto this; the graph keeps the
    five as PRODUCED edges rather than five nodes, which is what makes agreement countable."""
    instruments = sorted({str(s).upper() for s in lead.instruments})
    payload = json.dumps({"c": _norm_claim(lead.claim_text)[:400], "i": instruments},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compiler_parent_key(source: str, title: Any, url: Any) -> str:
    """The exact string `hypothesis_graph.record_candidates` stamps as a candidate's `parent`.

    Reproduced byte for byte, including the `miner:` prefix the compiler adds and the 300-char
    title truncation, because this is the ONLY deterministic join from a mined row to the cells it
    became. Verified against the live ledger: `miner:reddit` parent `306df02d8962f16e` resolves to
    a row still on disk under `data/intelligence/reddit/`.
    """
    src = str(source or "")
    if src and not src.startswith("miner:"):
        src = f"miner:{src}"
    # `url` is passed through UNSTRINGIFIED, because the compiler stores `row.get("url") or
    # row.get("link") or ""` raw and `json.dumps` would render a non-string differently. The
    # title is always stringified and truncated, because the compiler always does both.
    payload = json.dumps({"u": url if url else "", "t": str(title or "")[:MAX_TITLE_CHARS],
                          "s": src}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def row_cell_key(row: Mapping[str, Any], seat: str = "") -> str:
    """`compiler_parent_key` fed EXACTLY the fields the compiler feeds it, off a raw intake row.

    The three reads are the compiler's own, character for character
    (`miner_candidate_compiler._candidate` and `recent_rows`): the source falls back to the
    artifact's parent directory, the title falls back to `description`, and the url falls back to
    `link`. A near-miss here silently costs every BECAME edge for that miner, so it is duplicated
    deliberately rather than approximated with this module's more tolerant field chains.
    """
    source = str(row.get("source") or seat or "unknown")
    title = row.get("title") or row.get("description") or ""
    url = row.get("url") or row.get("link") or ""
    return compiler_parent_key(source, title, url)


def cell_seed_key(row: Mapping[str, Any]) -> str:
    """The other end of the same join, read off a HYPOTHESIS-GRAPH row: `seed_key`, then `parent`.

    `row_cell_key` computes the key from the intake row; this reads the key a cell was stamped
    with. Two fields because `hypothesis_graph` split them on 2026-09-17: `parent` now holds the
    CELL a candidate was mutated from when the donor named one the graph holds, and `seed_key`
    always holds the miner-row sha. Rows written before that date have no `seed_key` and carry
    the seed in `parent`, which is why the fallback is not optional -- 35,199 of them are on this
    box and every BECAME edge the desk has depends on it.
    """
    return str(row.get("seed_key") or row.get("parent") or "")


def title_key(title: str) -> str:
    """A title's identity for DERIVES_FROM: its first eight significant tokens, order kept."""
    toks = [t for t in _TOKEN_RE.findall(str(title or "").lower()) if len(t) > 2][:8]
    return " ".join(toks)


# --------------------------------------------------------------------------- text work

def urls_in_text(text: str, limit: int = 10) -> list[str]:
    """Links a claim CITES, in order, deduplicated. The genealogy edge's cheapest evidence: a
    forum post that pastes an arXiv link is naming its parent, and that is a fact, not a guess."""
    out: list[str] = []
    for match in _URL_IN_TEXT.finditer(str(text or "")):
        url = match.group(0).rstrip(".,;)")
        if url not in out:
            out.append(url)
        if len(out) >= limit:
            break
    return out


def token_set(text: str) -> frozenset[str]:
    """Tokens for near-duplicate work: alphanumerics of two or more, plus single CJK glyphs."""
    return frozenset(_TOKEN_RE.findall(str(text or "").lower()))


def token_cosine(a: Iterable[str], b: Iterable[str]) -> float:
    """Set cosine: |A and B| / sqrt(|A| |B|). 1.0 is the same bag of words in any order."""
    sa, sb = frozenset(a), frozenset(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / math.sqrt(len(sa) * len(sb))


def direction_of(text: str) -> int:
    """+1 long/up, -1 short/down, 0 when the text states neither or is evenly split.

    MAJORITY, NOT PRESENCE. "gold falls after a positive excess return, short it" contains one up
    word and two down words; an any/any rule reads that as ambivalent and loses the contradiction
    it is in with "gold rises after a positive excess return". A tie is still 0 rather than a coin
    flip -- "buy the dip and sell the rip" is not a directional claim, and pretending it is would
    manufacture contradictions out of balanced prose.
    """
    low = f" {str(text or '').lower()} "
    up = sum(1 for w in _DIR_UP if w in low)
    down = sum(1 for w in _DIR_DOWN if w in low)
    if up == down:
        return 0
    return 1 if up > down else -1


#: THE TOKENISER CUTS CJK INTO SINGLE GLYPHS, so a two-character term like 基差 or 换月 can never
#: be a token and a set-membership test would silently never fire on Chinese, Japanese or Korean
#: prose -- the forests this desk is under standing orders to mine to exhaustion. The non-ASCII
#: vocabulary is therefore matched as a SUBSTRING, which is how those scripts work anyway.
_CJK_PHRASES: tuple[str, ...] = tuple(sorted(
    {t for t in _CLAIM_WORDS if not t.isascii()} | {t for t in _INSTRUMENT_WORDS if not t.isascii()}
))
#: A claim in Chinese fits in six characters; the same claim in English does not fit in twelve.
_MIN_SENTENCE, _MIN_CJK_SENTENCE = 12, 6
_CJK_RE = re.compile(r"[㐀-鿿぀-ヿ가-힯]")


def _is_claim_sentence(sentence: str) -> bool:
    low = sentence.lower()
    if any(ch.isdigit() for ch in low):
        return True
    toks = set(_TOKEN_RE.findall(low))
    if toks & _INSTRUMENT_WORDS or toks & _CLAIM_WORDS:
        return True
    if any(phrase in low for phrase in _CJK_PHRASES):
        return True
    for m in _PAIR_RE.finditer(low):
        if m.group(1).upper() in _CCY and m.group(2).upper() in _CCY:
            return True
    return False


def claims_from_text(text: str, max_claims: int = MAX_CLAIMS_PER_DOC) -> list[str]:
    """A document, cut into the sentences that actually assert something.

    A sentence qualifies when it carries a NUMBER, an INSTRUMENT or a MECHANISM VERB -- the three
    things an extractor can do anything with. "We thank the anonymous referees" carries none and
    is dropped; "gold rallies into the London fix in 62% of sessions" carries all three.

    Verbatim, in document order, bounded both per claim and per document. A page that yields more
    than `max_claims` is a listing rather than a claim, and truncating it is the honest read.
    """
    body = str(text or "").strip()
    if not body:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in _SENTENCE_SPLIT.split(body):
        sentence = _WS.sub(" ", raw).strip()
        floor = _MIN_CJK_SENTENCE if _CJK_RE.search(sentence) else _MIN_SENTENCE
        if len(sentence) < floor or not _is_claim_sentence(sentence):
            continue
        sentence = sentence[:MAX_CLAIM_CHARS]
        norm = _norm_claim(sentence)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(sentence)
        if len(out) >= max(1, int(max_claims)):
            break
    return out


# --------------------------------------------------------------------------- row reading

def _empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _first_str(row: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    return ""


def _str_list(row: Mapping[str, Any], keys: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        value = row.get(key)
        items: list[Any]
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple)):
            items = list(value)
        else:
            continue
        for item in items:
            if not isinstance(item, (str, int, float)) or isinstance(item, bool):
                continue
            token = str(item).strip()
            if not token or token.lower() in seen:
                continue
            seen.add(token.lower())
            out.append(token)
    return out


def _kind_of(row: Mapping[str, Any], source_id: str) -> str:
    raw = str(row.get("kind") or row.get("type") or "").strip().lower()
    hit = _KIND_BY_ROW_KIND.get(raw)
    ground_kind = str(row.get("ground_kind") or row.get("source_kind") or "").strip().lower()
    if hit and hit != "other":
        return hit
    haystack = " ".join(str(row.get(k) or "") for k in
                        ("source", "ground", "cluster", "seat", "miner")).lower()
    haystack = f"{haystack} {source_id.lower()}"
    for needle, kind in _KIND_BY_SOURCE:
        if needle in haystack:
            return kind
    ground_hit = _KIND_BY_GROUND_KIND.get(ground_kind)
    if ground_hit:
        return ground_hit
    if "forum" in ground_kind or "public" in ground_kind:
        return "forum"
    return "other"


def _mechanisms_of(row: Mapping[str, Any]) -> list[str]:
    # `capability` is deliberately absent: on a frontier row it is the FIRM's capability
    # (MACRO / PORTFOLIO / OPS), which is an org chart, not a market mechanism.
    raw = _str_list(row, ("mechanism_class", "mechanism_tags", "patterns", "phenotypes",
                          "mechanism_key", "tags"))
    out: list[str] = []
    seen: set[str] = set()
    for token in raw:
        norm = re.sub(r"[^a-z0-9_]+", "_", token.strip().lower()).strip("_")
        if not norm or len(norm) > 48 or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out[:12]


def _axes_of(row: Mapping[str, Any]) -> dict[str, str]:
    """The axis coordinates the ROW DECLARES. Nothing is inferred from prose: an axis the source
    never named is absent, which `axis_registry` reads as UNMEASURED rather than as a default."""
    axes: dict[str, str] = {}
    chart = _first_str(row, ("chart", "timeframe", "tf"))
    if not chart:
        frames = _str_list(row, ("timeframes",))
        chart = frames[0] if frames else ""
    if chart:
        axes["chart"] = chart.upper()[:8]
    for axis, keys in (("session", ("session", "asia_plane", "window")),
                       ("horizon", ("horizon", "hold", "holding_period", "max_hold")),
                       # NOT `state`: on a frontier row that is the workflow state (DISCOVERED,
                       # QUEUED), and recording it as a market regime would invent a coordinate.
                       ("regime", ("regime", "market_state", "vol_state", "band")),
                       ("information_source", ("information_source", "expression_kind",
                                               "channel")),
                       ("economic_actor", ("actor", "firm", "participant", "payer"))):
        value = _first_str(row, keys)
        if value:
            axes[axis] = value[:48]
    return axes


def _spec_of(row: Mapping[str, Any], *, instruments: list[str], language: str,
             source_id: str) -> tuple[dict[str, Any] | None, bool]:
    """The fourteen-field block, filled ONLY from what the row states.

    An unstated field stays None. Filling `pit_status` with PIT_CLEAN because nobody said
    otherwise would convert silence into a point-in-time guarantee, which is the single most
    expensive lie an intake can tell.
    """
    declared = row.get("structured") or row.get("spec")
    block = blank_spec()
    if isinstance(declared, Mapping):
        for f in SPEC_FIELDS:
            if not _empty(declared.get(f)):
                block[f] = declared[f]
    pairs: tuple[tuple[str, Sequence[str]], ...] = (
        ("actor", ("actor", "participant", "payer", "firm", "trader")),
        ("constraint", ("constraint", "constraints", "blocked_on", "limit")),
        ("counterparty", ("counterparty", "opposing_side", "taker")),
        ("mechanism", ("mechanism", "mechanism_class", "why", "family")),
        ("why_edge_can_persist", ("why_edge_can_persist", "persistence", "expected_decay",
                                  "why_persists")),
        ("horizon", ("horizon", "hold", "holding_period")),
        ("session", ("session", "window")),
        ("expected_cost", ("expected_cost", "cost", "spread_cost", "expected_costs")),
        ("falsifier", ("falsifier", "falsifiers", "kill_criterion")),
    )
    for name, keys in pairs:
        if _empty(block[name]):
            value = _first_str(row, keys)
            if value:
                block[name] = value[:400]
    if _empty(block["asset_mapping"]) and instruments:
        block["asset_mapping"] = list(instruments)
    if _empty(block["required_data"]):
        data = _str_list(row, ("required_data", "endpoints", "inputs", "uses_data", "datasets"))
        if data:
            block["required_data"] = data[:20]
    if _empty(block["pit_status"]):
        block["pit_status"] = _pit_status(row)
    if _empty(block["source"]):
        block["source"] = source_id or None
    if _empty(block["language"]) and language:
        block["language"] = language
    stated = [f for f in SPEC_FIELDS if not _empty(block[f])]
    # `source`, `language` and `pit_status` are stamped by this adapter rather than by the source,
    # so a block carrying only those three states nothing and is not a specification.
    if len(stated) <= 3 and not set(stated) - {"source", "language", "pit_status"}:
        return None, False
    return block, structured_complete(block)


def _pit_status(row: Mapping[str, Any]) -> str:
    pit = row.get("pit")
    if isinstance(pit, Mapping):
        lag = pit.get("publication_lag_days")
        if isinstance(lag, (int, float)) and not isinstance(lag, bool):
            return "LAGGED" if float(lag) > 0 else "PIT_CLEAN"
        return "UNKNOWN"
    declared = str(row.get("pit_status") or "").strip().upper()
    if declared in PIT_STATUSES:
        return declared
    return "UNKNOWN"


def _executable_of(row: Mapping[str, Any], instruments: list[str]) -> dict[str, Any] | None:
    family = _first_str(row, ("family",))
    if not family:
        return None
    params = row.get("params")
    return {"family": family,
            "params": dict(params) if isinstance(params, Mapping) else {},
            "symbols": list(instruments)}


def _language_of(row: Mapping[str, Any]) -> str:
    raw = _first_str(row, ("language", "lang", "locale"))
    token = re.sub(r"[^a-zA-Z_+-]", "", raw)[:12].lower()
    return token


# --------------------------------------------------------------------------- the adapters

def leads_from_intelligence_row(row: Mapping[str, Any], *, seat: str = "", run: str = "",
                                asset_class_of: Mapping[str, str] | None = None,
                                max_claims: int = MAX_CLAIMS_PER_DOC) -> list[Lead]:
    """Every atomic claim in one intelligence row, in document order. `[]` for a row that is not
    evidence: a miner's own bookkeeping, a selector failure, or a row with nothing to read.

    TOLERANT BY CONSTRUCTION. The six intake shapes disagree about every field name, and a new
    miner will disagree again -- so this reads a row by what it CONTAINS rather than by what it
    calls itself, and a shape nobody has written yet lands as `kind="other"` with whatever text
    it carries rather than being rejected. The compiler learned that lesson the expensive way: an
    inclusion list failed closed against 119,902 rows in 583 artifacts.
    """
    if not isinstance(row, Mapping):
        return []
    raw_kind = str(row.get("kind") or row.get("type") or "").strip().lower()
    if raw_kind in _OPERATIONAL_KINDS or row.get("needs_selector_work"):
        return []
    source_id = _first_str(row, ("source", "ground", "seat", "cluster")) or seat or "unknown"
    title = _first_str(row, _TITLE_FIELDS)
    body = _first_str(row, _VERBATIM_FIELDS)
    url = _first_str(row, _URL_FIELDS)
    if not body and not title:
        return []
    instruments = _str_list(row, ("symbols", "instruments", "symbol", "analogues"))
    classes = _str_list(row, ("asset_class", "asset_classes"))
    if not classes and asset_class_of:
        folded = {str(k).upper(): str(v) for k, v in asset_class_of.items()}
        classes = [c for c in dict.fromkeys(folded.get(s.upper(), "") for s in instruments) if c]
    language = _language_of(row)
    mechanisms = _mechanisms_of(row)
    axes = _axes_of(row)
    executable = _executable_of(row, instruments)
    spec, complete = _spec_of(row, instruments=instruments, language=language,
                              source_id=source_id)
    kind = _kind_of(row, source_id)
    seen_at = _first_str(row, _SEEN_FIELDS)
    knowable_at = _first_str(row, _KNOWABLE_FIELDS)
    doc = doc_id_of(source_id, url, title)
    cell_key = row_cell_key(row, seat)
    provenance = {"miner": _first_str(row, ("miner", "source", "cluster")) or source_id,
                  "seat": seat or _first_str(row, ("seat", "ground", "cluster")) or source_id,
                  "run": run or _first_str(row, ("run", "candidate_id", "claim_hash",
                                                 "mission_id", "cell_id")),
                  "cell_key": cell_key}

    claims = claims_from_text(body, max_claims) if body else []
    verbatim = bool(claims)
    if not claims:
        # NOTHING BUT A LABEL. `FX Blue user fxpl` satisfies any "does this row have text" test
        # and carries no instrument, no mechanism and no rule -- carried, and marked for what it
        # is, because the deepening queue is exactly the population of rows in this state.
        fallback = body or title
        claims = [fallback[:MAX_CLAIM_CHARS]] if fallback else []
        verbatim = bool(body)
    out: list[Lead] = []
    for index, claim in enumerate(claims):
        quality = {"verbatim": verbatim,
                   "has_instrument": bool(instruments),
                   "has_mechanism": bool(mechanisms) or bool(executable)}
        testable = bool(executable) or (quality["has_instrument"] and quality["has_mechanism"])
        out.append(Lead(
            lead_id=lead_id_of(source_id, claim),
            kind=kind,
            source_id=source_id,
            url_or_ref=url,
            seen_at=seen_at,
            knowable_at=knowable_at,
            language=language,
            claim_text=claim,
            doc_id=doc,
            claim_index=index,
            mechanism_ids=list(mechanisms),
            instruments=list(instruments),
            axes=dict(axes),
            asset_classes=list(classes),
            testable=testable,
            structured=dict(spec) if spec else None,
            executable=dict(executable) if executable else None,
            structured_complete=complete,
            priority=PRIORITY_NORMAL if complete else PRIORITY_LOW,
            provenance=dict(provenance),
            quality=quality,
        ))
    return out


def from_intelligence_row(row: Mapping[str, Any], *, seat: str = "", run: str = "",
                          asset_class_of: Mapping[str, str] | None = None) -> Lead | None:
    """The row's FIRST claim, or None. `leads_from_intelligence_row` returns all of them."""
    leads = leads_from_intelligence_row(row, seat=seat, run=run, asset_class_of=asset_class_of)
    return leads[0] if leads else None


# --------------------------------------------------------------------------- validation

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")


def validate(lead: Lead) -> list[str]:
    """Everything wrong with this lead, in plain words. Empty means nothing is.

    It returns problems rather than raising: a malformed lead is a measurement about a miner, and
    an intake that dies on the first bad row reports nothing about the other four thousand.
    """
    problems: list[str] = []
    if lead.kind not in KINDS:
        problems.append(f"kind {lead.kind!r} is not one of {KINDS}")
    if not lead.source_id.strip():
        problems.append("source_id is empty: a lead with no source cannot be credited or audited")
    if not lead.claim_text.strip():
        problems.append("claim_text is empty")
    if len(lead.claim_text) > MAX_CLAIM_CHARS:
        problems.append(f"claim_text is {len(lead.claim_text)} chars, over {MAX_CLAIM_CHARS}")
    if lead.lead_id != lead_id_of(lead.source_id, lead.claim_text):
        problems.append("lead_id does not hash its own source and claim")
    if lead.claim_index < 0:
        problems.append("claim_index is negative")
    for name, stamp in (("seen_at", lead.seen_at), ("knowable_at", lead.knowable_at)):
        if stamp and not _ISO.match(stamp):
            problems.append(f"{name} {stamp!r} is not an ISO timestamp")
    if lead.seen_at and lead.knowable_at and _ISO.match(lead.seen_at) \
            and _ISO.match(lead.knowable_at) and lead.knowable_at > lead.seen_at:
        problems.append("knowable_at is after seen_at: the desk cannot have crawled a claim "
                        "before the world could read it")
    if lead.structured is not None and set(lead.structured) != set(SPEC_FIELDS):
        missing = sorted(set(SPEC_FIELDS) - set(lead.structured))
        extra = sorted(set(lead.structured) - set(SPEC_FIELDS))
        problems.append(f"structured block is not the fourteen fields (missing={missing}, "
                        f"extra={extra})")
    if lead.structured_complete != structured_complete(lead.structured):
        problems.append("structured_complete disagrees with the block it describes")
    if lead.priority not in (PRIORITY_LOW, PRIORITY_NORMAL):
        problems.append(f"priority {lead.priority!r} is not low or normal")
    if lead.structured_complete and lead.priority != PRIORITY_NORMAL:
        problems.append("a complete lead is not low priority")
    if not lead.structured_complete and lead.priority != PRIORITY_LOW:
        problems.append("an incomplete lead is LOW PRIORITY, never normal and never dropped")
    if lead.executable is not None and not str(lead.executable.get("family") or "").strip():
        problems.append("executable block carries no family")
    expected = bool(lead.executable) or (bool(lead.instruments) and bool(lead.mechanism_ids))
    if lead.testable != expected:
        problems.append("testable disagrees with what the lead actually names "
                        "(a family, or an instrument AND a mechanism)")
    if len(lead.instruments) != len({s.lower() for s in lead.instruments}):
        problems.append("instruments repeat")
    if any(not isinstance(v, str) for v in lead.axes.values()):
        problems.append("axis values must be strings")
    for key in ("miner", "seat", "run", "cell_key"):
        if key not in lead.provenance:
            problems.append(f"provenance has no {key}")
    for key in ("verbatim", "has_instrument", "has_mechanism"):
        if key not in lead.quality:
            problems.append(f"quality has no {key}")
    return problems


# --------------------------------------------------------------------------- serialisation

def to_row(lead: Lead) -> dict[str, Any]:
    """JSON-safe dict. Round-trips through `from_row` unchanged."""
    return asdict(lead)


def from_row(row: Mapping[str, Any]) -> Lead:
    """A stored row back into a Lead, tolerating a row written before a field existed."""
    structured = row.get("structured")
    executable = row.get("executable")
    quality = row.get("quality")
    provenance = row.get("provenance")
    axes = row.get("axes")
    return Lead(
        lead_id=str(row.get("lead_id") or ""),
        kind=str(row.get("kind") or "other"),
        source_id=str(row.get("source_id") or ""),
        url_or_ref=str(row.get("url_or_ref") or ""),
        seen_at=str(row.get("seen_at") or ""),
        knowable_at=str(row.get("knowable_at") or ""),
        language=str(row.get("language") or ""),
        claim_text=str(row.get("claim_text") or ""),
        doc_id=str(row.get("doc_id") or ""),
        claim_index=int(row.get("claim_index") or 0),
        mechanism_ids=[str(m) for m in (row.get("mechanism_ids") or [])],
        instruments=[str(s) for s in (row.get("instruments") or [])],
        axes={str(k): str(v) for k, v in (axes.items() if isinstance(axes, Mapping) else ())},
        asset_classes=[str(c) for c in (row.get("asset_classes") or [])],
        testable=bool(row.get("testable")),
        structured=dict(structured) if isinstance(structured, Mapping) else None,
        executable=dict(executable) if isinstance(executable, Mapping) else None,
        structured_complete=bool(row.get("structured_complete")),
        priority=str(row.get("priority") or PRIORITY_NORMAL),
        provenance={str(k): str(v)
                    for k, v in (provenance.items() if isinstance(provenance, Mapping) else ())},
        quality={str(k): bool(v)
                 for k, v in (quality.items() if isinstance(quality, Mapping) else ())},
    )
