"""Grounds the principal has put off-limits: no request ever reaches them.

zuck's standing order: WeChat and Baidu are off-limits as data grounds. That covers every Baidu
host (index.baidu.com, huiyan.baidu.com, tieba.baidu.com, ...), WeChat itself (weixin.qq.com,
mp.weixin.qq.com, wechat.com) and Sogou, whose public indexes (weixin.sogou.com,
zhihu.sogou.com) are the route into WeChat. A share CFD named Baidu is an instrument, not a
ground, and is untouched.

FAIL CLOSED: every transport that can fetch a URL (`polite_fetch.get`, `cn_sources`,
`free_stack.http_fetch`, `alt_proxies.http_get`, `asia_collector`) asks `off_limits(url)` first
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


def off_limits(url: str) -> str | None:
    """The refusal reason when `url` points at an off-limits host, else None."""
    try:
        host = (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    for dom in OFF_LIMITS_DOMAINS:
        if host == dom or host.endswith("." + dom):
            return f"{WHY} [{host}]"
    return None
