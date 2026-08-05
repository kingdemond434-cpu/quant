"""Replacement registry: when a source dies, WHAT ELSE CARRIES THE SAME INFORMATION.

THE LOAD-BEARING DESIGN POINT. The desk does not need "another website" when Zhihu returns 403.
It needs another source of the SAME INFORMATION -- Chinese long-form analytical writing by
practitioners. Swapping a dead CN retail-sentiment forum for an English preprint server is not a
replacement, it is a topic change dressed as a fix, and it would quietly move the miner's corpus
while every dashboard stayed green. So every candidate here is filed under a NAMED INFORMATION
CLASS, the class is asserted to match the class of the source it substitutes for
(tests/research/test_source_alternatives.py enforces it), and a candidate that does not carry the
same information does not belong in this file at all.

WHAT SEEDED IT. Two things already in the tree, nothing invented:

  * the block reasons the desk has already measured and written down -- CN_SOURCES in
    scripts/mine_research_queue.py (baidu anti-bot shell, zhihu 403, bilibili 412-unsigned,
    joinquant/bigquant/ricequant JS shells) and libs/data/cn_sources.probe_all() (xueqiu WAF,
    csdn read timeout). Each registry group repeats that reason so the next reader is not
    re-diagnosing a solved question.
  * what is already KNOWN-GOOD here. Juejin and WeChat-via-Sogou are working parsers in
    libs/data/cn_sources.py, and they are in-class substitutes for CSDN and Zhihu respectively.
    An alternative that is already built and already passing is worth more than four aspirational
    URLs, so those are marked `in_tree` and listed FIRST.

EVERY CANDIDATE STARTS UNVERIFIED, AND THAT IS THE ONLY HONEST DEFAULT. Nothing in this file has
been probed by writing it down. A candidate becomes REACHABLE or FAILED only by passing through
:func:`probed` with a real result from scripts/hunt_source_alternatives.py; the registry itself is
frozen and never learns. A registry that promoted its own guesses to "working" would be the
fabrication this desk's whole probe discipline exists to prevent.

SOME CANDIDATES CANNOT BE VERIFIED FROM HERE, BY CONSTRUCTION. This container reaches the internet
through an egress proxy and the VPS does not, so "the same endpoint, from the unproxied box" is a
real and often correct answer to a datacenter-IP block -- and it is exactly the answer this box
cannot test. Those carry ``verify_from=VANTAGE_DIRECT`` and stay UNVERIFIED here with that reason
recorded, rather than being probed through the proxy and written off as FAILED on evidence that
does not bear on the claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Final

from libs.research.source_health import VANTAGE_DIRECT

# ------------------------------------------------------------------- information classes
#: A class is what the desk would LOSE if every member of it went dark. Named, because "quant
#: content" is not a class -- it is the whole miner, and it cannot be reasoned about.

CN_RETAIL_SENTIMENT: Final[str] = "cn_retail_investor_sentiment"
"""Chinese retail-investor discussion, positioning chatter and crowd mood. What Xueqiu carried."""

CN_LONGFORM_QA: Final[str] = "cn_longform_qa_analysis"
"""Chinese long-form question-and-answer and analytical essays. What Zhihu carried."""

CN_TECH_WRITEUP: Final[str] = "cn_technical_writeup"
"""Chinese technical write-ups with code -- backtest walk-throughs, library tutorials. CSDN."""

CN_QUANT_PLATFORM: Final[str] = "cn_quant_platform_community"
"""Chinese quant-PLATFORM strategy libraries and practitioner forums. JoinQuant/BigQuant/RiceQuant.
Distinct from CN_TECH_WRITEUP: these carry runnable strategies against a specific backtest engine,
not general programming articles."""

CN_WEB_SEARCH: Final[str] = "cn_web_search_index"
"""A general index OF the Chinese web -- the discovery layer, not a corpus of its own. Baidu."""

CN_VIDEO: Final[str] = "cn_video_discovery"
"""Chinese-language video listings with titles/descriptions/tags rich enough to rank. Bilibili."""

VIDEO_TRANSCRIPT: Final[str] = "video_transcript_text"
"""Machine-readable spoken-word text for a video. The desk's oldest dead lane: every YouTube
caption path is blocked from this IP, so the miner ranks videos it cannot read."""

EN_PRACTITIONER_FORUM: Final[str] = "en_practitioner_forum"
"""English-language practitioner discussion -- traders arguing about live results. Reddit."""

EN_PREPRINT: Final[str] = "en_academic_preprint"
"""English-language preprints and working papers with readable abstracts. arXiv / SSRN."""

INFORMATION_CLASSES: Final[tuple[str, ...]] = (
    CN_RETAIL_SENTIMENT, CN_LONGFORM_QA, CN_TECH_WRITEUP, CN_QUANT_PLATFORM,
    CN_WEB_SEARCH, CN_VIDEO, VIDEO_TRANSCRIPT, EN_PRACTITIONER_FORUM, EN_PREPRINT,
)

# --------------------------------------------------------------------------------- statuses
STATUS_UNVERIFIED: Final[str] = "UNVERIFIED"
STATUS_REACHABLE: Final[str] = "REACHABLE"
STATUS_FAILED: Final[str] = "FAILED"
#: Probed, answered, but what came back was a shell / challenge page rather than content. Its own
#: status because "200 OK, 1.4KB of anti-bot JavaScript" is neither reachable-and-usable nor a
#: network failure, and calling it either one sends the next reader down the wrong path.
STATUS_SHELL: Final[str] = "SHELL"

#: Below this a search-results page is a challenge/redirect shell, not results. Same number the
#: miner already uses (scripts/mine_research_queue.probe_cn), kept identical on purpose: two
#: different content thresholds on one desk is two different definitions of "working".
CONTENT_BYTES: Final[int] = 20_000


@dataclass(frozen=True)
class Candidate:
    """One substitute source, in the same information class as the source it would replace."""

    name: str
    information_class: str
    url: str
    #: What a parser would have to DO. Concrete, naming the module and the shape, because a
    #: report that says "alternative reachable" and stops has moved the work nowhere.
    next_action: str
    needs_auth: bool = False
    #: Content is client-rendered: a plain GET returns a shell no matter how healthy the site is.
    needs_js: bool = False
    #: Beyond JS -- a real browser session (cookie handshake / fingerprint) is required. Chromium
    #: is available in this environment, so this is a cost, not a blocker.
    needs_browser: bool = False
    #: Module path when the parser ALREADY EXISTS and passes here. Worth more than any URL.
    in_tree: str | None = None
    #: The name this candidate carries in the HEALTH LEDGER, when it differs from its registry
    #: name. Only meaningful alongside ``in_tree``: an already-built candidate's status is read
    #: off the miner's own daily measurement rather than re-probed, and that lookup has to hit
    #: the right key -- "wechat_via_sogou" is filed as "wechat", "hackernews_algolia" as "hn".
    #: Getting this wrong reports a working source as UNKNOWN, which is a silent downgrade.
    ledger_key: str | None = None
    #: Which vantage can settle this candidate. VANTAGE_DIRECT means "only the unproxied VPS can
    #: test it" -- probing it from this container would produce an answer to a different question.
    verify_from: str = "any"
    note: str = ""
    status: str = STATUS_UNVERIFIED
    probe_detail: str | None = None


@dataclass(frozen=True)
class Replacements:
    """Everything the desk knows about substituting one source."""

    source: str
    information_class: str
    #: The measured reason this source is a problem, quoted from where the desk recorded it.
    recorded_reason: str
    candidates: tuple[Candidate, ...]


def probed(candidate: Candidate, *, status: str, detail: str | None) -> Candidate:
    """A new Candidate carrying a REAL probe result. The registry is never mutated."""
    return replace(candidate, status=status, probe_detail=detail)


def _c(name: str, ic: str, url: str, next_action: str, **kw: Any) -> Candidate:
    return Candidate(name=name, information_class=ic, url=url, next_action=next_action, **kw)


#: THE REGISTRY. Order within a group is priority: already-built first, then plain-HTML hosts,
#: then anything needing JS or auth -- the miner's fetch path is urllib, so a server-rendered page
#: is worth strictly more than a prettier site behind a browser requirement.
_REGISTRY: Final[tuple[Replacements, ...]] = (
    Replacements(
        source="xueqiu",
        information_class=CN_RETAIL_SENTIMENT,
        recorded_reason=("HTML reachable (110KB) but the API sits behind a WAF challenge a plain "
                         "cookie handshake does not clear -- libs/data/cn_sources.probe_all()"),
        candidates=(
            _c("eastmoney_guba", CN_RETAIL_SENTIMENT, "https://guba.eastmoney.com/",
               "add libs/data/cn_sources.eastmoney_guba(keyword) parsing post title + reply count "
               "+ author out of the 股吧 list HTML into Article(source='guba'); wire it into the "
               "(name, fn) tuple in mine_research_queue's CN_ARTICLE_QUERIES loop",
               note="东方财富股吧 -- the largest CN retail forum by post volume; same crowd-mood "
                    "information Xueqiu carried, server-rendered lists"),
            _c("taoguba", CN_RETAIL_SENTIMENT, "https://www.taoguba.com.cn/",
               "parse the 淘股吧 topic list (title + author + view count) into Article; "
               "same wiring point as eastmoney_guba",
               note="淘股吧 -- smaller and more experienced cohort than 股吧, historically "
                    "plain HTML"),
            _c("jiuyangongshe", CN_RETAIL_SENTIMENT, "https://www.jiuyangongshe.com/",
               "confirm whether the article feed has a JSON endpoint; if not, this needs the "
               "Chromium path the JS-shell sources already need",
               needs_js=True,
               note="韭研公社 -- retail research notes; front end is a SPA"),
        ),
    ),
    Replacements(
        source="zhihu",
        information_class=CN_LONGFORM_QA,
        recorded_reason=("HTTP 403 to unauthenticated requests, API included -- "
                         "scripts/mine_research_queue.CN_SOURCES"),
        candidates=(
            _c("wechat_via_sogou", CN_LONGFORM_QA,
               "https://weixin.sogou.com/weixin?type=2&query=%E9%87%8F%E5%8C%96",
               "NONE -- already built and already mined. If Zhihu is retired, raise this "
               "source's query breadth in CN_ARTICLE_QUERIES to absorb the lost volume",
               in_tree="libs/data/cn_sources.sogou_weixin", ledger_key="wechat",
               note="微信公众号 via Sogou. The closest in-class match the desk has: long-form "
                    "practitioner essays, and it is ALREADY PARSING here (10 results on the "
                    "2026-08-05 probe). Rate-limits with an anti-bot page, which is transient"),
            _c("douban", CN_LONGFORM_QA,
               "https://www.douban.com/search?q=%E9%87%8F%E5%8C%96",
               "parse the 豆瓣 search result list (title + abstract + link) into Article("
               "source='douban'); groups carry long-form investing discussion threads",
               note="豆瓣 -- long-form discussion groups; historically server-rendered search"),
            _c("36kr", CN_LONGFORM_QA,
               "https://36kr.com/search/articles/%E9%87%8F%E5%8C%96",
               "check for the __NEXT_DATA__ JSON blob in the page; if present parse it "
               "directly rather than the DOM, which is the cheaper and more stable path",
               needs_js=True,
               note="36氪 -- professional finance/tech long-form; Next.js SPA, but Next.js "
                    "usually ships its data as embedded JSON"),
            _c("toutiao", CN_LONGFORM_QA,
               "https://so.toutiao.com/search?keyword=%E9%87%8F%E5%8C%96",
               "probe first: Toutiao gates search behind a signed parameter much like Bilibili's "
               "WBI. If the signature is required, this is the same class of work as "
               "libs/data/bilibili's signing, not a parser",
               needs_browser=True,
               note="今日头条 -- huge CN content index; expected to need request signing"),
        ),
    ),
    Replacements(
        source="csdn",
        information_class=CN_TECH_WRITEUP,
        recorded_reason="read timeout from this box -- libs/data/cn_sources.probe_all()",
        candidates=(
            _c("juejin", CN_TECH_WRITEUP,
               "https://api.juejin.cn/search_api/v1/search?query=%E9%87%8F%E5%8C%96&id_type=0",
               "NONE -- already built and already mined. CSDN's information class is fully "
               "covered here today; the open question is coverage breadth, not reachability",
               in_tree="libs/data/cn_sources.juejin", ledger_key="juejin",
               note="掘金 -- clean JSON search API, err_no 0, ~20 results/query, measured working "
                    "on 2026-08-05. This is why CSDN's death has cost the desk very little"),
            _c("cnblogs", CN_TECH_WRITEUP,
               "https://zzk.cnblogs.com/s?w=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
               "add libs/data/cn_sources.cnblogs(keyword) parsing the searchItem blocks "
               "(title anchor + .searchCon summary) into Article(source='cnblogs') -- the same "
               "block-wise shape as _parse_wechat_block, so reuse that structure",
               note="博客园 -- the oldest CN developer blog host; server-rendered search"),
            _c("segmentfault", CN_TECH_WRITEUP,
               "https://segmentfault.com/search?q=%E9%87%8F%E5%8C%96",
               "parse the search list into Article(source='segmentfault'); check for an /api/ "
               "JSON route first, which SegmentFault has historically exposed",
               note="思否 -- Q&A plus articles, developer-heavy"),
            _c("oschina", CN_TECH_WRITEUP,
               "https://www.oschina.net/search?q=%E9%87%8F%E5%8C%96",
               "parse the blog/news result list into Article(source='oschina')",
               note="开源中国 -- OSS-focused CN developer community"),
        ),
    ),
    Replacements(
        source="baidu",
        information_class=CN_WEB_SEARCH,
        recorded_reason=("returns a ~1.5KB anti-bot shell rather than results (measured 1438 "
                         "bytes) -- scripts/mine_research_queue.CN_SOURCES"),
        candidates=(
            _c("bing_cn", CN_WEB_SEARCH,
               "https://cn.bing.com/search?q=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
               "add a generic libs/data/cn_sources.web_search(engine, keyword) that parses "
               "result title + snippet + href into Article(source=engine); one parser, several "
               "engines, so a single engine going dark is a config line rather than a rewrite",
               note="Bing's CN index -- indexes the CN web without Baidu's bot wall"),
            _c("sogou_web", CN_WEB_SEARCH,
               "https://www.sogou.com/web?query=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
               "same generic web_search parser; Sogou's markup is already understood here "
               "because sogou_weixin parses the same result-block shape",
               note="搜狗 -- the desk already parses its WeChat vertical successfully"),
            _c("so360", CN_WEB_SEARCH,
               "https://www.so.com/s?q=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
               "same generic web_search parser, third engine -- three independent CN indexes is "
               "what turns the discovery layer from a single point of failure into a quorum",
               note="360搜索 -- third CN general index"),
            _c("duckduckgo_html", CN_WEB_SEARCH,
               "https://html.duckduckgo.com/html/?q=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
               "same generic web_search parser; the /html/ endpoint is explicitly the "
               "no-JavaScript surface, so the parse is stable",
               note="Not a CN-native index and its CN coverage is thinner -- listed LAST because "
                    "it is the weakest in-class match, not because it is hardest"),
        ),
    ),
    Replacements(
        source="joinquant",
        information_class=CN_QUANT_PLATFORM,
        recorded_reason=("reachable but JS-rendered (6KB shell); listings require Chromium, and "
                         "the API 404s or needs auth -- scripts/mine_research_queue.CN_SOURCES"),
        candidates=(
            _c("vnpy_forum", CN_QUANT_PLATFORM, "https://www.vnpy.com/forum/",
               "add libs/data/cn_sources.vnpy_forum() parsing thread title + author + reply "
               "count into Article(source='vnpy'); forum software renders server-side",
               note="vn.py 社区 -- the largest open-source CN quant framework's own forum; "
                    "carries live-trading write-ups against a real engine"),
            _c("gitee_search", CN_QUANT_PLATFORM,
               "https://search.gitee.com/?q=%E9%87%8F%E5%8C%96&type=repository",
               "parse repo name + description + stars into Article(source='gitee'); mirrors the "
               "GitHub path libs/data/papers.github already implements, so reuse its scoring",
               note="码云 -- where CN quant code that never reaches GitHub lives"),
            _c("myquant", CN_QUANT_PLATFORM, "https://www.myquant.cn/",
               "check whether the strategy/community listing has a JSON route before committing "
               "to the Chromium path",
               needs_js=True,
               note="掘金量化 -- same platform class as JoinQuant, same JS-shell risk"),
            _c("uqer", CN_QUANT_PLATFORM, "https://uqer.datayes.com/",
               "probe first; historically gated behind a login for anything beyond the shell",
               needs_auth=True, needs_js=True,
               note="优矿 -- institutional-leaning CN quant platform"),
        ),
    ),
    Replacements(
        source="bilibili",
        information_class=CN_VIDEO,
        recorded_reason=("the RAW search endpoint answers HTTP 412 without WBI request signing. "
                         "NOT a death: libs/data/bilibili signs its requests and mines this "
                         "source successfully (15 of 31 new rows on 2026-08-05). Registered "
                         "against a FUTURE outage, not a present one"),
        candidates=(
            _c("youtube_cn_queries", CN_VIDEO,
               "https://www.youtube.com/results?search_query=%E9%87%8F%E5%8C%96%E4%BA%A4%E6%98%93",
               "NONE -- already built. SEARCH_QUERIES in mine_research_queue already carries CN "
               "terms through the YouTube parser; if Bilibili dies, widen those",
               in_tree="scripts/mine_research_queue.search_youtube", ledger_key="youtube",
               note="CN quant creators cross-post to YouTube; the miner's own docstring says "
                    "those results never surface from English queries, which is why the CN "
                    "queries are already in SEARCH_QUERIES"),
            _c("ixigua", CN_VIDEO, "https://www.ixigua.com/search/%E9%87%8F%E5%8C%96/",
               "parse the embedded state JSON (ByteDance sites ship one) for title + author + "
               "play count into a bilibili.Video-shaped row so video_triage scores it unchanged",
               needs_js=True,
               note="西瓜视频 -- ByteDance's long-form video platform"),
            _c("haokan", CN_VIDEO,
               "https://haokan.baidu.com/web/search/page?query=%E9%87%8F%E5%8C%96",
               "probe first; shares Baidu's bot-wall infrastructure, so expect the shell",
               needs_js=True,
               note="好看视频 -- Baidu's video platform; listed last for exactly that reason"),
        ),
    ),
    Replacements(
        source="youtube_captions",
        information_class=VIDEO_TRANSCRIPT,
        recorded_reason=("no captionTracks in the watch page, api/timedtext returns 0 bytes, "
                         "youtube-transcript-api raises RequestBlocked -- a datacenter-IP block, "
                         "documented in scripts/mine_research_queue's module docstring"),
        candidates=(
            _c("youtube_timedtext_from_vps", VIDEO_TRANSCRIPT,
               "https://www.youtube.com/api/timedtext",
               "run the existing caption fetch ON THE VPS and record the result. If it works "
               "there, the fix is a vantage move (fetch captions in the VPS cron seat), not a "
               "new parser -- which would be the cheapest repair available to this desk",
               verify_from=VANTAGE_DIRECT,
               note="SAME ENDPOINT, DIFFERENT VANTAGE. The block is on the datacenter IP, and "
                    "this container's egress proxy is a datacenter IP. Cannot be settled from "
                    "here in either direction; it is a VPS experiment"),
            _c("bilibili_subtitle_api", VIDEO_TRANSCRIPT,
               "https://api.bilibili.com/x/player/v2?bvid=BV1GJ411x7h7&cid=1",
               "two calls: /x/web-interface/view?bvid= to get the cid, then /x/player/v2 for the "
               "subtitle list, then fetch the subtitle JSON URL. Reuse libs/data/bilibili's "
               "signing/session helpers. Note that many videos carry only AI-generated subtitles "
               "and some require a logged-in session",
               note="B站 subtitles. Same information class as YouTube captions -- spoken-word "
                    "text -- and Bilibili is the desk's highest-yielding video source, so this "
                    "unlocks transcripts where the corpus already converts"),
            _c("youtube_description_fallback", VIDEO_TRANSCRIPT,
               "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
               "parse `shortDescription` out of the watch page's player response and feed it to "
               "score_title alongside the title. STRICTLY WEAKER than a transcript and must be "
               "labelled as such in the queue row -- it is more signal than a bare title, not a "
               "substitute for reading the video",
               note="A partial, and recorded as a partial. Listed because the desk's measured "
                    "lesson is that snippet text roughly quadrupled WeChat's above-threshold "
                    "rate over title-only scoring"),
        ),
    ),
    Replacements(
        source="reddit",
        information_class=EN_PRACTITIONER_FORUM,
        recorded_reason=("declared 'HTTP 403 -- blocked' in libs/data/papers.probe_all(), which "
                         "hardcodes the row WITHOUT making a request. So this source's true "
                         "state here is UNKNOWN, not dead, and the ledger will not condemn it"),
        candidates=(
            _c("hackernews_algolia", EN_PRACTITIONER_FORUM,
               "https://hn.algolia.com/api/v1/search?query=quant%20trading%20backtest",
               "NONE -- already built and already mined via papers.hackernews",
               in_tree="libs/data/papers.hackernews", ledger_key="hn",
               note="HN is thinner on trading specifics than r/algotrading but it is in-class, "
                    "open, and working"),
            _c("quant_stackexchange", EN_PRACTITIONER_FORUM,
               "https://api.stackexchange.com/2.3/search/advanced?site=quant&q=backtest"
               "&order=desc&sort=votes&pagesize=20",
               "add libs/data/papers.stackexchange(site, query) parsing items[] title + body "
               "excerpt + score into the same Item shape the arXiv/SSRN path returns, so "
               "score_title needs no change. Anonymous quota is 300 requests/day, ample daily",
               note="quant.stackexchange -- moderated practitioner Q&A with a documented public "
                    "API and no auth for read. The strongest in-class candidate on this list"),
            _c("old_reddit_json", EN_PRACTITIONER_FORUM,
               "https://old.reddit.com/r/algotrading/top/.json?t=week&limit=25",
               "parse children[].data title + selftext + score into the Item shape; identical "
               "downstream to the stackexchange path",
               note="Same corpus as Reddit proper, different host and a JSON surface. Worth ONE "
                    "probe before assuming the 403 that was never actually measured"),
        ),
    ),
    Replacements(
        source="arxiv",
        information_class=EN_PREPRINT,
        recorded_reason=("healthy on the 2026-08-05 sweep. Registered against a FUTURE outage: "
                         "arXiv is a single point of failure for the only lane whose CONTENT "
                         "this desk can actually read (abstracts come back in the response)"),
        candidates=(
            _c("openalex", EN_PREPRINT,
               "https://api.openalex.org/works?search=quantitative%20trading&per-page=5",
               "add libs/data/papers.openalex(query) mapping results[] title + abstract_inverted"
               "_index (needs re-inversion) + doi into the Item shape",
               note="Open catalogue of ~250M works, no auth, polite-pool by email header. "
                    "Broadest in-class substitute available"),
            _c("crossref", EN_PREPRINT,
               "https://api.crossref.org/works?query=quantitative+trading&rows=5",
               "add libs/data/papers.crossref(query) mapping message.items[] title + abstract "
               "(JATS-tagged, needs stripping) + DOI into the Item shape",
               note="Registry of record for DOIs; abstracts present but inconsistently"),
            _c("semantic_scholar", EN_PREPRINT,
               "https://api.semanticscholar.org/graph/v1/paper/search?query=quantitative+trading"
               "&limit=5&fields=title,abstract,url",
               "add libs/data/papers.semantic_scholar(query); the fields= parameter returns "
               "abstracts directly, so the mapping is near-trivial",
               note="Rate-limited hard without a key (shared anonymous pool), which is why it is "
                    "below OpenAlex despite the cleaner response"),
            _c("osf_preprints", EN_PREPRINT,
               "https://api.osf.io/v2/preprints/?filter[title]=trading&page[size]=5",
               "add libs/data/papers.osf(query) mapping data[].attributes title + description "
               "into the Item shape",
               note="Covers preprint servers arXiv does not, including SocArXiv/EconStor-adjacent "
                    "material"),
        ),
    ),
)


def registry() -> tuple[Replacements, ...]:
    """The whole registry. Frozen dataclasses throughout -- callers cannot teach it anything."""
    return _REGISTRY


def alternatives_for(source: str) -> Replacements | None:
    """Replacements registered for ``source``, or None when the desk has none.

    None is a real and reportable answer: a dead source with no registered substitute is work
    the hunter must NAME rather than paper over.
    """
    key = source.strip()
    for entry in _REGISTRY:
        if entry.source == key:
            return entry
    return None


def by_information_class() -> dict[str, list[str]]:
    """Which sources this desk treats as interchangeable. Read it as the desk's actual redundancy
    map: a class with one member is a single point of failure."""
    out: dict[str, list[str]] = {}
    for entry in _REGISTRY:
        out.setdefault(entry.information_class, []).append(entry.source)
    return out


def candidate_to_row(candidate: Candidate) -> dict[str, Any]:
    """JSON-ready. Used by the hunt report; kept here so the shape has one definition."""
    return {
        "name": candidate.name,
        "information_class": candidate.information_class,
        "url": candidate.url,
        "status": candidate.status,
        "probe_detail": candidate.probe_detail,
        "needs_auth": candidate.needs_auth,
        "needs_js": candidate.needs_js,
        "needs_browser": candidate.needs_browser,
        "in_tree": candidate.in_tree,
        "ledger_key": candidate.ledger_key,
        "verify_from": candidate.verify_from,
        "note": candidate.note,
        "next_action": candidate.next_action,
    }


def class_of(source: str) -> str | None:
    """The information class ``source`` belongs to, or None if it is not registered."""
    entry = alternatives_for(source)
    return None if entry is None else entry.information_class


def unverified(entry: Replacements) -> tuple[Candidate, ...]:
    """Candidates in ``entry`` that no probe has spoken for yet."""
    return tuple(c for c in entry.candidates if c.status == STATUS_UNVERIFIED)


def summary() -> Mapping[str, Any]:
    """Counts for a report header -- how much substitute capacity the desk has on paper."""
    return {
        "sources_registered": len(_REGISTRY),
        "candidates_registered": sum(len(e.candidates) for e in _REGISTRY),
        "already_built_in_tree": sum(1 for e in _REGISTRY for c in e.candidates
                                     if c.in_tree is not None),
        "information_classes": {k: sorted(v) for k, v in by_information_class().items()},
    }
