"""PLATFORM TERMS FENCES -- the named platforms whose own agreement bars this desk's automated use.

WHY THIS FILE EXISTS (2026-09-30, the project coordinator's Reddit ruling). Reddit's User Agreement
and its Data API terms govern ALL automated access -- the OAuth API, the anonymous `.json`
listings and the `.rss` feeds alike -- and require a separate agreement for commercial use. This
desk is commercial and holds no such agreement, so no Reddit-derived data may feed a cell, the
lake, trading or allocation. It is the same basis as the earlier Discord ruling (bot token only,
never a user token) and the keyed-sources fence on #144 (`machine_use_allowed=false` on the Reddit
OAuth rows). StockTwits is fenced on the same basis: its Terms s.5 forbid extracting data "by
automated means except as expressly authorized by us in writing or through an approved API", and
it licenses that data commercially instead.

HOW THIS SITS WITH LAWS s.5e, stated so a later session does not read it as a re-introduced brake.
s.5e deleted SELF-IMPOSED discovery brakes -- a robots Disallow, a generic `machine_use_allowed`
label, a quarantine on ACCESS_UNCLEAR -- because none of them "was ever a legal requirement". This
is not a label read as a refusal: it is a short, NAMED list of platforms whose contract with every
automated reader requires an agreement the desk does not hold, each with the ruling that put it
here. Nothing else is fenced by it, it never generalises from a label, and an entry leaves the
list the day an agreement exists (set `agreement` on the entry, with its reference).

THE FENCE IS AT THE SOURCE, and it is one function per question:

    fenced_url(url)      -> the terms reason when the URL is on a fenced platform, else None
    fenced_row(row, src) -> the platform when a discovery row came from one, else None
    check_url(url)       -> raises TermsFenced; the one guard every fetch helper calls

Every refusal carries its reason and its status, BLOCKED_WITH_SUBSTITUTE when the information
class it served has a lawful substitute wired (`substitutes`), so no fenced route ever reads as
silent, dead or UNMEASURED.

EXISTING CELLS ARE NOT RE-JUDGED. A cell already judged from a fenced platform's rows keeps its
verdict; the organs that write docket and candidate rows stamp `provenance_label` with the
entry's `label` (`reddit_fenced`) through `label_row`, so the lineage is visible without deleting
or re-judging anything.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

BLOCKED_WITH_SUBSTITUTE = "BLOCKED_WITH_SUBSTITUTE"
BLOCKED_TERMS = "BLOCKED_TERMS"

#: The Reddit ruling, verbatim in every artifact that refuses a Reddit route.
REDDIT_TERMS_REASON = (
    "Reddit's User Agreement and Data API terms cover all automated access, including RSS and the "
    "anonymous JSON listings, and require a separate agreement for commercial use; this desk is "
    "commercial and holds none, so no Reddit data may feed cells, the lake, trading or allocation "
    "(project coordinator ruling 2026-09-30, same basis as the Discord ruling)")

STOCKTWITS_TERMS_REASON = (
    "StockTwits Terms s.5 forbid extracting data from the Service by automated means except as "
    "expressly authorized in writing or through an approved API, and s.8 reserves commercial "
    "licensing of that data to StockTwits; the desk holds no authorization, so no StockTwits data "
    "may feed cells, the lake, trading or allocation (checked 2026-09-30 at "
    "stocktwits.com/about/legal/terms)")

#: platform -> the fence. `hosts` match the registrable domain and every subdomain. `sources` are
#: the discovery-row source names (intelligence directory / `source` field) the platform wrote.
PLATFORMS: dict[str, dict[str, Any]] = {
    "reddit": {
        "hosts": ("reddit.com", "redd.it", "redditmedia.com", "redditstatic.com",
                  "reddituploads.com", "redditblog.com"),
        "sources": ("reddit", "miner:reddit"),
        "source_prefixes": ("ext_reddit_", "reddit_"),
        "routes": ("reddit",),
        "reason": REDDIT_TERMS_REASON,
        "status": BLOCKED_WITH_SUBSTITUTE,
        "label": "reddit_fenced",
        "fenced_at": "2026-09-30T00:00:00+00:00",
        "agreement": None,
        # The information class Reddit served -- retail attention and practitioner chatter -- and
        # the lawful doors that now carry it (desks/mt5/research/attention_substitutes.py).
        "substitutes": ("wikipedia_pageviews", "gdelt_doc_timeline", "google_trends"),
    },
    "stocktwits": {
        "hosts": ("stocktwits.com",),
        "sources": ("stocktwits", "miner:stocktwits"),
        "source_prefixes": ("stocktwits_",),
        "routes": ("stocktwits",),
        "reason": STOCKTWITS_TERMS_REASON,
        "status": BLOCKED_WITH_SUBSTITUTE,
        "label": "stocktwits_fenced",
        "fenced_at": "2026-09-30T00:00:00+00:00",
        "agreement": None,
        "substitutes": ("wikipedia_pageviews", "gdelt_doc_timeline", "google_trends"),
    },
}


class TermsFenced(RuntimeError):
    """A fetch was asked for a URL on a fenced platform. Carries the platform and its reason."""

    def __init__(self, platform: str, url: str) -> None:
        self.platform = platform
        self.reason = str(PLATFORMS[platform]["reason"])
        self.status = str(PLATFORMS[platform]["status"])
        super().__init__(f"{self.status}:{platform}: {url[:120]} -- {self.reason}")


def _active(platform: str) -> bool:
    return not PLATFORMS[platform].get("agreement")


def _host(url: str) -> str:
    u = str(url or "").strip()
    if not u:
        return ""
    if "://" not in u:
        u = "https://" + u.lstrip("/")
    try:
        return (urlparse(u).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def platform_of_url(url: str) -> str | None:
    """The fenced platform a URL belongs to, or None. Subdomains match (old.reddit.com)."""
    h = _host(url)
    if not h:
        return None
    for name, p in PLATFORMS.items():
        if not _active(name):
            continue
        for dom in p["hosts"]:
            if h == dom or h.endswith("." + dom):
                return name
    return None


def fenced_url(url: str) -> str | None:
    """The terms reason when `url` is on a fenced platform, else None."""
    p = platform_of_url(url)
    return str(PLATFORMS[p]["reason"]) if p else None


def check_url(url: str) -> None:
    """Raise `TermsFenced` for a URL on a fenced platform. EVERY fetch helper calls this first."""
    p = platform_of_url(url)
    if p:
        raise TermsFenced(p, str(url))


def fenced_source(source: str) -> str | None:
    """The platform a discovery SOURCE name belongs to ("reddit", "miner:reddit",
    "ext_reddit_EURUSD_..."), or None."""
    s = str(source or "").strip().lower()
    if not s:
        return None
    for name, p in PLATFORMS.items():
        if not _active(name):
            continue
        if s in p["sources"] or any(s.startswith(x) for x in p["source_prefixes"]):
            return name
    return None


_URL_FIELDS = ("url", "link", "source_url", "permalink", "canonical_url")


def fenced_row(row: Mapping[str, Any], source: str = "") -> str | None:
    """The fenced platform a discovery / candidate / docket row came from, or None.

    A row is platform-derived when its intake source, its own `source`, any `contributing_sources`
    entry, its `route` (deep_forest's ground route) or any of its URL fields names the platform.
    `contributing_sources` makes a cell that ANOTHER miner also proposed count as touched; the
    labeller stamps it, but the compiler refuses only the fenced ROW, so the other miner's
    proposal still reaches the docket on its own evidence.
    """
    if not isinstance(row, Mapping):
        return None
    for s in (source, row.get("source"), row.get("origin"), row.get("miner")):
        p = fenced_source(str(s or ""))
        if p:
            return p
    route = str(row.get("route") or "").split(":", 1)[0].lower()
    for name, p in PLATFORMS.items():
        if _active(name) and route in p["routes"]:
            return name
    for f in _URL_FIELDS:
        v = row.get(f)
        if isinstance(v, str):
            p2 = platform_of_url(v)
            if p2:
                return p2
    return None


def touched_row(row: Mapping[str, Any]) -> str | None:
    """`fenced_row`, plus any contributing source -- the LABELLER's test (a cell one fenced
    platform helped propose carries the label even when another miner proposed it too)."""
    p = fenced_row(row)
    if p:
        return p
    cs = row.get("contributing_sources") if isinstance(row, Mapping) else None
    for s in cs if isinstance(cs, list) else []:
        p = fenced_source(str(s or ""))
        if p:
            return p
    return None


def label_row(row: dict[str, Any]) -> str | None:
    """Stamp `provenance_label` (and `terms_fence`) on a row a fenced platform touched.

    Returns the label it stamped, or None. Idempotent. `provenance` itself is NOT overwritten:
    several readers treat it as a dict (`(row.get("provenance") or {}).get(...)`), so a string
    there would crash them. Nothing about the row's verdict, identity or ordering changes.
    """
    p = touched_row(row)
    if not p:
        return None
    lab = str(PLATFORMS[p]["label"])
    row["provenance_label"] = lab
    row["terms_fence"] = {"platform": p, "status": PLATFORMS[p]["status"],
                          "reason": PLATFORMS[p]["reason"]}
    return lab


def registry_rows() -> list[dict[str, Any]]:
    """One row per fenced platform, for the source registry and the roster reports."""
    return [{"platform": name, "status": p["status"] if _active(name) else "AGREEMENT_HELD",
             "reason": p["reason"], "label": p["label"], "fenced_at": p["fenced_at"],
             "hosts": list(p["hosts"]), "substitutes": list(p["substitutes"]),
             "agreement": p.get("agreement")}
            for name, p in PLATFORMS.items()]


def refusal(platform: str, **extra: Any) -> dict[str, Any]:
    """The artifact a fenced route writes instead of data: status, platform, reason, substitutes."""
    p = PLATFORMS[platform]
    return {"status": p["status"], "platform": platform, "reason": p["reason"],
            "why": f"terms fence ({platform}): {p['reason']}",
            "substitutes": list(p["substitutes"]), "fetched": 0, **extra}


if __name__ == "__main__":
    print(json.dumps(registry_rows(), indent=1))
