"""Grounds no request may ever reach: the principal's off-limits list, and congressional
disclosure reports (5 U.S.C. 13107(c), see STATUTE_HOSTS).

zuck's standing order: WeChat and Baidu are off-limits as data grounds. That covers every Baidu
host (index.baidu.com, huiyan.baidu.com, tieba.baidu.com, ...), WeChat itself (weixin.qq.com,
mp.weixin.qq.com, wechat.com) and Sogou, whose public indexes (weixin.sogou.com,
zhihu.sogou.com) are the route into WeChat. A share CFD named Baidu is an instrument, not a
ground, and is untouched.

FAIL CLOSED: every transport that can fetch a URL (`polite_fetch.get`, `cn_sources`,
`free_stack.http_fetch`, `free_stack_hunter.run`, `alt_proxies.http_get`, `asia_collector`)
asks `off_limits(url)` first
and refuses on a hit, without touching the network. The refusal lives here, in code, rather than
in the rosters under desks/mt5/data/ (money path for replay-shadow): a roster row that names one
of these hosts (baidu_index, cn_baidu_migration, cn_zhihu via Sogou, the Sogou-WeChat ground)
stays visible, and every fetch of it is refused with this reason.

missed_growth: whatever CN sentiment, attention and mobility these grounds carried is UNMEASURED
from them; the substitutes named on each row (HK ImmD crossings, Juejin, Bilibili) stand in.
"""
from __future__ import annotations

from urllib.parse import urlsplit

#: Registrable domains whose every host is off-limits.
OFF_LIMITS_DOMAINS: tuple[str, ...] = ("baidu.com", "sogou.com", "weixin.qq.com", "wechat.com")
STATUS = "BLOCKED_TERMS"
WHY = ("principal off-limits ground (WeChat/Baidu, incl. the Sogou route into WeChat): "
       "never fetched")
#: Congressional financial disclosure reports and their mirrors: 5 U.S.C. 13107(c) makes it
#: unlawful to obtain or use them for a commercial purpose, and a trading desk's use is one.
STATUTE_HOSTS: tuple[str, ...] = (
    "disclosures-clerk.house.gov", "efdsearch.senate.gov",
    "house-stock-watcher-data.s3-us-west-2.amazonaws.com",
    "senate-stock-watcher-data.s3-us-west-2.amazonaws.com")
WHY_STATUTE = ("5 U.S.C. 13107(c): congressional financial disclosure reports may not be "
               "obtained or used for a commercial purpose; never fetched")


def off_limits(url: str) -> str | None:
    """The refusal reason when `url` points at an off-limits host, else None. A URL whose host
    cannot be read is refused too (fail closed)."""
    try:
        host = (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower().rstrip(".")
    except ValueError:
        return f"unparseable URL, refused (fail closed): {url[:80]!r}"
    for dom in OFF_LIMITS_DOMAINS:
        if host == dom or host.endswith("." + dom):
            return f"{WHY} [{host}]"
    if host in STATUTE_HOSTS:
        return f"{WHY_STATUTE} [{host}]"
    return None


def redirected_off_limits(requested: str, final: str | None) -> str | None:
    """After a fetch that may have followed redirects: the refusal when the FINAL hop is an
    off-limits host. Callers drop the body unread, so an allowed host can never launder a
    banned one through a 30x."""
    if not final or final == requested:
        return None
    refused = off_limits(final)
    return f"redirected into an off-limits host, body discarded: {refused}" if refused else None
