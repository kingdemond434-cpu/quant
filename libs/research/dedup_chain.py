"""THE DEDUP CHAIN -- ten agents finding one strategy on ten repost sites produce ONE mechanism.

THE FAILURE IT EXISTS TO PREVENT. The forest federation runs eleven agents in each of seventeen
civilizations, and the deep forest is largely a REPOST ECOLOGY: one 七禾网 interview is quoted on
four aggregators, summarised on two blogs, screenshotted into a forum thread and mirrored by an
archive. Without a chain, that is nine extra mechanisms, nine extra cells, nine extra trials --
and the deflated-Sharpe charge and the program-level SPA/PBO tests divide ONE family-wise error
budget across every hypothesis the desk tests. Duplicate discovery is not untidy; it is a tax
every genuine hypothesis pays.

THE FIVE STAGES, IN THIS ORDER, AND THE VERDICT NAMES THE ONE THAT DECIDED:

  1. CANONICAL SOURCE   scheme/host lowercased, tracking parameters stripped, known mirrors
                        folded onto their origin, trailing slash and default ports removed. Two
                        rows that are the same page with different campaign tags are one row,
                        and this stage costs nothing.
  2. CONTENT HASH       sha256 of the NORMALISED text (whitespace folded, case folded, boilerplate
                        punctuation dropped). A verbatim repost on another host lands here.
  3. SEMANTIC SIMILARITY  cosine over k-shingles. A paraphrase, a translation-with-edits or a
                        quote-plus-commentary lands here. It fires only when the two rows do not
                        name DIFFERENT mechanisms -- high token overlap between two genuinely
                        different claims about the same instrument is common, and letting prose
                        similarity overrule a stated mechanism is how a real descendant gets
                        erased as a duplicate.
  4. MECHANISM IDENTITY the key the desk already reasons in (`lead_schema` / `hypothesis_graph`
                        conventions): family, instruments, condition, direction, horizon. Two
                        rows with no textual overlap at all that state the same edge are ONE
                        mechanism, which is the stage the other four cannot reach.
  5. GENEALOGY          what is left: a row that names an ancestor, or sits in the descendant
                        similarity band while stating a DIFFERENT mechanism, is a DESCENDANT --
                        it branches, with a provenance edge to its canonical ancestor, and is
                        tested on its own.

Pure and typed. It opens nothing, writes nothing and decides nothing about capital: it returns a
`Verdict` carrying the deciding stage, the score, the mechanism key and the provenance edges the
caller should write. `RegistryView` is the in-memory index the caller maintains -- one process,
one view -- so the chain never queries a database inside a scoring loop.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DESCENDANT_OF",
    "DESCENDANT_THRESHOLD",
    "DUPLICATE_OF",
    "MIRRORS",
    "NEW",
    "SEMANTIC_DUPLICATE_THRESHOLD",
    "SHINGLE_K",
    "STAGES",
    "TRACKING_PARAMS",
    "Item",
    "RegistryView",
    "Verdict",
    "canonical_url",
    "content_hash",
    "dedup",
    "fold",
    "mechanism_key",
    "normalise_text",
    "shingles",
    "similarity",
]

# --------------------------------------------------------------------------- vocabulary
NEW = "NEW"
DUPLICATE_OF = "DUPLICATE_OF"
DESCENDANT_OF = "DESCENDANT_OF"

#: The five stages, in the order they run. A verdict always names exactly one of them.
STAGES: tuple[str, ...] = ("canonical_source", "content_hash", "semantic_similarity",
                           "mechanism_identity", "genealogy")

#: Cosine over k-shingles at or above which two texts are THE SAME TELLING. Measured against the
#: repost ecology this desk actually mines: a verbatim repost scores 1.0 (and is caught one stage
#: earlier anyway), an aggregator's quote-plus-headline 0.85-0.95, a genuine follow-up study on
#: the same instrument 0.3-0.6. 0.82 sits in the empty band between the second and the third.
SEMANTIC_DUPLICATE_THRESHOLD = 0.82
#: At or above this -- but below the duplicate bar -- two rows are RELATED. With a different
#: mechanism key that is a descendant (it branches and is tested); below it, unrelated.
DESCENDANT_THRESHOLD = 0.55
#: Shingle width. 3 for space-delimited scripts; single CJK glyphs are shingled at 3 too, which
#: is roughly a word and a half in Chinese, Japanese and Korean -- the forests this desk is
#: under standing orders to mine to exhaustion, and where a token-level model finds nothing.
SHINGLE_K = 3

#: Query parameters that identify a VISIT rather than a PAGE. Stripped before hashing a url.
TRACKING_PARAMS: frozenset[str] = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "gclid", "fbclid", "yclid", "msclkid", "dclid", "igshid", "mc_cid", "mc_eid",
    "spm", "scm", "from", "share_source", "share_medium", "share_plat", "share_token",
    "vd_source", "ref", "referrer", "refer", "source", "src", "s", "sid", "session_id",
    "_hsenc", "_hsmi", "trk", "trkCampaign", "at_medium", "at_campaign", "wt_mc",
})

#: Hosts that SERVE ANOTHER HOST'S PAGES. Folding a mirror onto its origin is the cheapest real
#: dedup on this desk's ground: the Wayback Machine, the CJK and RU text mirrors, the nitter and
#: reddit front ends. The mapping is one-way and deliberately small -- a wrong entry MERGES two
#: different sources, which is worse than missing a duplicate.
MIRRORS: dict[str, str] = {
    "web.archive.org": "",            # "" means: unwrap the embedded original url
    "webcache.googleusercontent.com": "",
    "archive.ph": "", "archive.today": "", "archive.is": "",
    "r.jina.ai": "",
    "old.reddit.com": "reddit.com", "np.reddit.com": "reddit.com",
    "m.weibo.cn": "weibo.com", "xueqiu.com": "xueqiu.com",
    "zhuanlan.zhihu.com": "zhihu.com",
    "m.bilibili.com": "bilibili.com",
    "nitter.net": "twitter.com", "nitter.poast.org": "twitter.com", "x.com": "twitter.com",
    "mobile.twitter.com": "twitter.com",
    "m.habr.com": "habr.com", "translated.turbopages.org": "",
}

_DEFAULT_PORTS = {"http": "80", "https": "443"}
_INDEX_FILES = re.compile(r"/(index|default)\.(html?|php|aspx?|jsp)$", re.IGNORECASE)
_WS = re.compile(r"\s+")
#: The punctuation a repost REFLOWS, in forty scripts. RUF001 calls these characters
#: ambiguous; here they are the data, not a typo waiting to be found.
_PUNCT = re.compile(r"[\s　]*[\"'`´“”‘’«»(){}\[\]<>|/\\,;:!?.…、。，；：！？·—–\-_*#]+[\s　]*")  # noqa: RUF001
_URL_IN = re.compile(r"https?%3A%2F%2F[^\s&]+|https?://[^\s\"'<>]+", re.IGNORECASE)
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_TOKEN = re.compile(r"[a-z0-9]+|[぀-ヿ㐀-鿿가-힯]")


# --------------------------------------------------------------------------- stage 1: the url
def _unquote(text: str) -> str:
    """Percent-decoding without importing urllib: the mirrors embed an encoded original url."""
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "%" and i + 2 < len(text):
            try:
                out.append(chr(int(text[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(ch)
        i += 1
    return "".join(out)


def _split(url: str) -> tuple[str, str, str, str, str]:
    """(scheme, host, port, path, query) -- a small, total parser; a malformed url is data."""
    raw = str(url or "").strip()
    scheme = ""
    if "://" in raw:
        scheme, raw = raw.split("://", 1)
    raw = raw.split("#", 1)[0]
    query = ""
    if "?" in raw:
        raw, query = raw.split("?", 1)
    hostport, _, path = raw.partition("/")
    host, _, port = hostport.partition(":")
    return scheme.lower(), host.lower(), port, ("/" + path if path else "/"), query


def canonical_url(url: str, *, mirrors: Mapping[str, str] | None = None) -> str:
    """STAGE 1. One page, one string: scheme and host lowered, tracking parameters stripped,
    known mirrors folded (or unwrapped back to the original url they are serving), default port
    and trailing slash and index file removed, query parameters sorted.

    An empty or unparseable url returns "" -- which the chain reads as "this row names no page",
    never as "this row is the same page as the other row that names none".
    """
    table = dict(MIRRORS if mirrors is None else mirrors)
    seen: set[str] = set()
    current = str(url or "").strip()
    for _hop in range(4):                    # a mirror of a mirror; bounded, never a cycle
        scheme, host, port, path, query = _split(current)
        if not host:
            return ""
        target = table.get(host)
        if target == "":
            inner = _URL_IN.search(_unquote(f"{path}?{query}" if query else path))
            if inner and inner.group(0) not in seen:
                seen.add(inner.group(0))
                current = inner.group(0)
                continue
            target = None
        if target:
            host = target
        # `www.` IS NOT PART OF A SITE'S IDENTITY. Every host serves both spellings and the
        # aggregators pick whichever their crawler saw first, so keeping them apart would leave
        # the cheapest duplicate in the whole chain uncaught.
        if host.startswith("www.") and host.count(".") > 1:
            host = host[4:]
        if " " in host or ("." not in host and host != "localhost"):
            return ""              # not a host: a malformed row names no page, and no two
        #                            rows that name no page are therefore the same page
        port = "" if port in ("", _DEFAULT_PORTS.get(scheme or "https", "")) else port
        # NOR IS THE SCHEME. http and https serve the same page, and an aggregator linking the
        # plain-http spelling of a claim is not a second telling of it.
        scheme = "https"
        path = _INDEX_FILES.sub("/", path)
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        params = []
        for part in query.split("&"):
            if not part:
                continue
            name = part.split("=", 1)[0]
            if name.lower() in TRACKING_PARAMS:
                continue
            params.append(part)
        params.sort()
        netloc = f"{host}:{port}" if port else host
        tail = ("?" + "&".join(params)) if params else ""
        return f"{scheme}://{netloc}{path}{tail}"
    return ""


# --------------------------------------------------------------------------- stage 2: the text
def normalise_text(text: str) -> str:
    """The text with everything that is not the CLAIM removed: case, whitespace runs and the
    punctuation a repost reflows. Two tellings that differ only by formatting normalise equal."""
    body = _WS.sub(" ", str(text or "")).strip().lower()
    body = _PUNCT.sub(" ", body)
    return _WS.sub(" ", body).strip()


def content_hash(text: str) -> str:
    """STAGE 2. sha256 of the normalised text, truncated. "" for an empty body, which the chain
    reads as "nothing to hash" -- never as a hash two empty rows share."""
    norm = normalise_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32] if norm else ""


# --------------------------------------------------------------------------- stage 3: shingles
def shingles(text: str, k: int = SHINGLE_K) -> frozenset[str]:
    """k-shingles over the normalised token stream: the unit stage 3 compares.

    Tokens are alphanumeric runs plus SINGLE CJK glyphs, so a Japanese or Chinese claim shingles
    into overlapping character triples -- roughly a word and a half -- rather than into one token
    per sentence, which is what a space-delimited tokeniser does to those scripts and why a
    similarity model built on words silently scores every CJK pair at zero.
    """
    tokens = _TOKEN.findall(normalise_text(text))
    if not tokens:
        return frozenset()
    width = max(1, int(k))
    if len(tokens) <= width:
        return frozenset({" ".join(tokens)})
    return frozenset(" ".join(tokens[i:i + width]) for i in range(len(tokens) - width + 1))


def similarity(a: Iterable[str], b: Iterable[str]) -> float:
    """Set cosine |A and B| / sqrt(|A| |B|): 1.0 is the same shingle bag in any order."""
    sa, sb = frozenset(a), frozenset(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / math.sqrt(len(sa) * len(sb))


# --------------------------------------------------------------------------- stage 4: mechanism
_DIR_UP = ("long", "buy", "bull", "rise", "rising", "higher", "up", "positive", "outperform",
           "appreciat", "gain", "上涨", "做多", "买入", "看涨", "상승", "매수", "買い", "上昇")
_DIR_DOWN = ("short", "sell", "bear", "fall", "falling", "lower", "down", "negative",
             "underperform", "depreciat", "decline", "下跌", "做空", "卖出", "看跌", "하락",
             "매도", "売り", "下落")
#: Horizon vocabulary folded onto the desk's own three-value ladder. An unstated horizon is
#: `unknown` and NOT a default: two claims that differ only in an unstated horizon are the same
#: claim until one of them states one.
_HORIZON: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("intraday", ("intraday", "m1", "m5", "m15", "m30", "h1", "h4", "session", "minute", "hour",
                  "日内", "장중", "デイ")),
    ("overnight", ("overnight", "gap", "close to open", "翌日", "隔夜", "오버나이트")),
    ("multi_day", ("multi_day", "d1", "w1", "daily", "weekly", "monthly", "swing", "day",
                   "week", "month", "隔天", "数日", "周", "월간")),
)


def _direction(*texts: Any) -> int:
    """+1, -1 or 0 -- MAJORITY, not presence. "buy the dip and sell the rip" is not directional,
    and manufacturing a direction out of balanced prose manufactures contradictions."""
    low = " " + " ".join(str(t or "") for t in texts).lower() + " "
    up = sum(1 for w in _DIR_UP if w in low)
    down = sum(1 for w in _DIR_DOWN if w in low)
    if up == down:
        return 0
    return 1 if up > down else -1


def _horizon(value: Any, fallback: Any = "") -> str:
    low = " ".join((str(value or ""), str(fallback or ""))).lower()
    for name, needles in _HORIZON:
        if any(n in low for n in needles):
            return name
    return "unknown"


def _condition(value: Any) -> str:
    """The conditioning clause reduced to its significant tokens, order kept, bounded.

    "after the Tokyo fix on the 5th and 10th" and "on 五十日 after the Tokyo fixing" are the same
    condition wearing two sentences; eight tokens is enough to tell them from "after CPI".
    """
    toks = [t for t in _TOKEN.findall(normalise_text(value)) if len(t) > 1 or _CJK.match(t)]
    return " ".join(toks[:12])


def mechanism_key(*, family: str = "", instruments: Sequence[str] = (), condition: str = "",
                  direction: Any = None, horizon: str = "", text: str = "") -> str:
    """STAGE 4's identity: family x instruments x condition x direction x horizon.

    The five fields the desk already reasons in -- `lead_schema.SPEC_FIELDS` names the same edge
    and `hypothesis_graph.node_id` hashes the same shape -- so a mechanism minted here joins the
    hypothesis graph rather than starting a second vocabulary about the same claim.
    """
    insts = sorted({str(s).strip().upper() for s in instruments if str(s).strip()})
    dirn = _direction(text, condition, family) if direction is None else int(direction)
    payload = json.dumps({"f": str(family or "").strip().lower(), "i": insts,
                          "c": _condition(condition), "d": dirn,
                          "h": _horizon(horizon, condition or text)},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- the objects
@dataclass(frozen=True)
class Item:
    """One thing an agent found, in the only shape the chain reads."""

    item_id: str
    url: str = ""
    title: str = ""
    text: str = ""
    family: str = ""
    instruments: tuple[str, ...] = ()
    condition: str = ""
    direction: int | None = None
    horizon: str = ""
    source_id: str = ""
    forest: str = ""
    role: str = ""
    kind: str = "discovery"
    #: Ancestors this row NAMES. A claim, until the view resolves one -- an unresolvable parent
    #: is carried on the edge, never promoted into the verdict.
    parent_ids: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def mechanism_key(self) -> str:
        return mechanism_key(family=self.family, instruments=self.instruments,
                             condition=self.condition or self.title, direction=self.direction,
                             horizon=self.horizon,
                             text=" ".join((self.title, self.text, self.condition)))


@dataclass(frozen=True)
class Verdict:
    """What the chain decided, WHICH STAGE decided it, and the edges the caller should write."""

    verdict: str
    stage: str
    of: str = ""
    score: float | None = None
    mechanism_key: str = ""
    canonical: str = ""
    content: str = ""
    why: str = ""
    edges: tuple[tuple[str, str, str, str], ...] = field(default_factory=tuple)

    @property
    def is_new(self) -> bool:
        return self.verdict == NEW

    @property
    def is_duplicate(self) -> bool:
        return self.verdict == DUPLICATE_OF

    @property
    def is_descendant(self) -> bool:
        return self.verdict == DESCENDANT_OF

    def as_row(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "stage": self.stage, "of": self.of, "score": self.score,
                "mechanism_key": self.mechanism_key, "canonical_url": self.canonical,
                "content_hash": self.content, "why": self.why,
                "edges": [list(e) for e in self.edges]}


class RegistryView:
    """The in-process index the chain reads: one view per run, fed by what the run admits.

    NOT A DATABASE QUERY IN A LOOP. Eleven roles in seventeen forests times a few hundred rows is
    tens of thousands of comparisons per pass; a view built once and mutated as rows are admitted
    keeps the chain O(n) against the admitted population instead of O(n) round trips.
    """

    def __init__(self) -> None:
        self.by_url: dict[str, str] = {}
        self.by_hash: dict[str, str] = {}
        self.by_mechanism: dict[str, str] = {}
        self.shingles: dict[str, frozenset[str]] = {}
        self.mechanism_of: dict[str, str] = {}
        self.ids: list[str] = []

    def __len__(self) -> int:
        return len(self.ids)

    def add(self, item: Item, item_id: str | None = None, *, mech: str | None = None) -> str:
        """Admit one row as canonical. Idempotent per id; first writer of a key keeps it."""
        iid = str(item_id or item.item_id)
        key = mech if mech is not None else item.mechanism_key()
        url = canonical_url(item.url)
        digest = content_hash(" ".join((item.title, item.text)))
        if url:
            self.by_url.setdefault(url, iid)
        if digest:
            self.by_hash.setdefault(digest, iid)
        if key:
            self.by_mechanism.setdefault(key, iid)
        sh = shingles(" ".join((item.title, item.text, item.condition)))
        if sh:
            self.shingles[iid] = sh
        self.mechanism_of[iid] = key
        if iid not in self.ids:
            self.ids.append(iid)
        return iid

    def knows(self, item_id: str) -> bool:
        return item_id in self.mechanism_of

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping[str, Any]]) -> RegistryView:
        """A view over rows already in the registry (discoveries, claims): the caller's shape,
        read tolerantly, because six producers spell these fields six ways."""
        view = cls()
        for row in rows:
            iid = str(row.get("discovery_id") or row.get("id") or row.get("item_id") or "")
            if not iid:
                continue
            insts = row.get("instruments") or row.get("assets") or row.get("symbols") or ()
            if isinstance(insts, str):
                insts = [insts]
            view.add(Item(item_id=iid, url=str(row.get("url") or row.get("url_or_ref") or ""),
                          title=str(row.get("title") or "")[:400],
                          text=str(row.get("text") or row.get("claim") or
                                   row.get("mechanism") or "")[:4000],
                          family=str(row.get("family") or ""),
                          instruments=tuple(str(s) for s in insts),
                          condition=str(row.get("condition") or row.get("exact_rule") or ""),
                          horizon=str(row.get("horizon") or row.get("chart") or ""),
                          source_id=str(row.get("source_id") or "")))
        return view


# --------------------------------------------------------------------------- the chain
def _edge(src_kind: str, src_id: str, dst_id: str, relation: str) -> tuple[str, str, str, str]:
    return (src_kind, src_id, dst_id, relation)


def dedup(item: Item, registry_view: RegistryView) -> Verdict:
    """The five stages, in order, on one row. NEW | DUPLICATE_OF <id> | DESCENDANT_OF <id>.

    The verdict always names the DECIDING STAGE, because "duplicate" is not a fact on its own:
    a url collision and a mechanism collision are different findings about a forest -- the first
    says an agent walked the same page twice, the second says two independent grounds agree, and
    an audit that cannot tell them apart cannot tell a repost ecology from a consensus.
    """
    key = item.mechanism_key()
    url = canonical_url(item.url)
    digest = content_hash(" ".join((item.title, item.text)))
    src = item.source_id or item.forest or item.role or "forest"

    def dup(stage: str, of: str, why: str, score: float | None = None) -> Verdict:
        return Verdict(verdict=DUPLICATE_OF, stage=stage, of=of, score=score, mechanism_key=key,
                       canonical=url, content=digest, why=why,
                       edges=(_edge("source", src, of, "retold"),))

    # 1 -- CANONICAL SOURCE
    known = registry_view.by_url.get(url) if url else None
    if known and known != item.item_id:
        return dup("canonical_source", known,
                   f"the same page after canonicalisation ({url}): one visit, not one finding")

    # 2 -- CONTENT HASH
    known = registry_view.by_hash.get(digest) if digest else None
    if known and known != item.item_id:
        return dup("content_hash", known,
                   "byte-identical after normalisation: a verbatim repost on another host")

    # 3 -- SEMANTIC SIMILARITY
    mine = shingles(" ".join((item.title, item.text, item.condition)))
    best_id, best = "", 0.0
    for other_id, other in registry_view.shingles.items():
        if other_id == item.item_id:
            continue
        score = similarity(mine, other)
        if score > best:
            best_id, best = other_id, score
    other_key = registry_view.mechanism_of.get(best_id, "")
    same_mechanism = not (key and other_key) or key == other_key
    if best >= SEMANTIC_DUPLICATE_THRESHOLD and same_mechanism:
        return dup("semantic_similarity", best_id, score=round(best, 6),
                   why=f"cosine {best:.3f} over {SHINGLE_K}-shingles is at or above "
                       f"{SEMANTIC_DUPLICATE_THRESHOLD}: the same telling, reworded")

    # 4 -- MECHANISM IDENTITY
    known = registry_view.by_mechanism.get(key) if key else None
    if known and known != item.item_id:
        return dup("mechanism_identity", known,
                   "the same (family, instruments, condition, direction, horizon): two grounds "
                   "telling one mechanism is ONE mechanism with two provenance edges",
                   score=round(best, 6) if best else None)

    # 5 -- GENEALOGY
    ancestor = next((p for p in item.parent_ids if registry_view.knows(p)), "")
    if not ancestor and best >= DESCENDANT_THRESHOLD and best_id and not same_mechanism:
        ancestor = best_id
    if ancestor:
        return Verdict(verdict=DESCENDANT_OF, stage="genealogy", of=ancestor,
                       score=round(best, 6) if best else None, mechanism_key=key, canonical=url,
                       content=digest,
                       why=("states a DIFFERENT mechanism from its ancestor: it branches and is "
                            "tested on its own, with a provenance edge to where it came from"),
                       edges=(_edge("discovery", ancestor, item.item_id, "descendant"),
                              _edge("source", src, item.item_id, "produced")))
    return Verdict(verdict=NEW, stage="genealogy", of="", score=round(best, 6) if best else None,
                   mechanism_key=key, canonical=url, content=digest,
                   why="no canonical page, content, telling, mechanism or ancestor matches: new",
                   edges=(_edge("source", src, item.item_id, "produced"),))


def fold(items: Sequence[Item], view: RegistryView | None = None
         ) -> tuple[list[Verdict], RegistryView]:
    """Run the chain over a sequence IN ORDER, admitting each NEW or DESCENDANT row as it goes.

    This is the property the federation needs stated once: ten agents handing in ten tellings of
    one strategy produce ONE admitted mechanism and NINE provenance edges, whichever order they
    arrive in and whichever stage catches each one.
    """
    v = view if view is not None else RegistryView()
    out: list[Verdict] = []
    for item in items:
        verdict = dedup(item, v)
        if verdict.verdict in (NEW, DESCENDANT_OF):
            v.add(item, mech=verdict.mechanism_key)
        out.append(verdict)
    return out, v


def census(verdicts: Sequence[Verdict]) -> dict[str, Any]:
    """What a pass's chain did, by stage -- the audit that tells reposts from agreement."""
    by_stage: dict[str, int] = {}
    for v in verdicts:
        if v.verdict != NEW:
            by_stage[v.stage] = by_stage.get(v.stage, 0) + 1
    return {
        "n": len(verdicts),
        "new": sum(1 for v in verdicts if v.is_new),
        "duplicates": sum(1 for v in verdicts if v.is_duplicate),
        "descendants": sum(1 for v in verdicts if v.is_descendant),
        "by_deciding_stage": by_stage,
        "edges": sum(len(v.edges) for v in verdicts),
        "thresholds": {"semantic_duplicate": SEMANTIC_DUPLICATE_THRESHOLD,
                       "descendant": DESCENDANT_THRESHOLD, "shingle_k": SHINGLE_K},
        "rule": ("canonical source -> content hash -> semantic similarity -> mechanism identity "
                 "-> genealogy; ten reposts are one mechanism and nine provenance edges, and a "
                 "genuinely different descendant branches"),
    }
