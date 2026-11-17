"""SELF-PUBLISHED PROP-TRADER GROUNDS -- the lawful route to the same mechanisms.

The firms' own sites are shut (prop_showcase_fetch.TERMS: six refuse automated or commercial
use in writing, four wall the read of their terms). The principal's order of 2026-11-17 is to
reach the same people another way: funded traders who publish their own methods and results,
and anyone who publicly claims prop-capital earnings, verified or not. Those live in feeds the
publisher syndicates on purpose: podcast RSS (interview show notes) and personal-blog RSS.

WHAT THIS FILE HOLDS
  GROUNDS         one row per feed: url, kind, language and the VERIFICATION LEVEL of its claims.
  TERMS(+EVIDENCE) the per-ground terms gate, fail closed, same vocabulary as the firm gate plus
                  two verdicts the principal opened on 2026-11-17 ("if no, then just do it"):
                    no_ban      the publisher's terms were read and hold no clause against
                                automated reading or commercial/internal use
                    no_terms    the publisher links no terms page at all
                  Both still need recorded evidence (what was read, where, when), and robots.txt
                  remains a second gate on every request. A written ban is `refused`, a walled
                  or unread terms page is `to_confirm`; neither is ever contacted.
  harvest_feeds   feed -> items -> claim rows (title + show notes only; no audio, no page
                  crawl, no transcript host), appended to the same claims file the firm
                  harvest writes, so one lexicon, one screen and one trial ledger serve both.

VERIFICATION LEVEL rides on every claim and reaches the candidate's evidence, so the judge can
learn which kind of claimant carries edge. It is a label, never a weight: an unverified claim
is a hypothesis like any other and the gauntlet decides.
  firm_published        the paying firm published the story (the firm-site ground)
  interview             a third-party host interviewed the trader; results as stated on air
  self_reported         the trader's own blog/feed; nothing checked by anyone
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import prop_showcase_fetch as _fetch
from prop_showcase_lexicon import extract

VERIFICATION = ("firm_published", "interview", "self_reported")
OPEN_VERDICTS = ("confirmed", "no_ban", "no_terms")
TERMS_VALUES = (*OPEN_VERDICTS, "to_confirm", "refused")
MAX_NEW_PER_GROUND = 60

#: Feeds the publisher syndicates. `claims` is the verification level of what the feed states.
#: A ground is added HERE with its terms row below; nothing is fetched on a missing row.
GROUNDS: dict[str, dict[str, Any]] = {
    "chatwithtraders": {"url": "https://feeds.megaphone.fm/CWT9205947236", "kind": "podcast_rss",
                        "claims": "interview", "lang": "en",
                        "home": "https://chatwithtraders.com/"},
    "twoblokestrading": {
        "url": "https://feeds.captivate.fm/twoblokestradinglearntotradeonline/",
        "kind": "podcast_rss", "claims": "interview", "lang": "en",
        "home": "https://twoblokestrading.com/"},
    "desiretotrade": {"url": "https://desiretotrade.libsyn.com/rss", "kind": "podcast_rss",
                      "claims": "interview", "lang": "en",
                      "home": "https://www.desiretotrade.com/"},
    "pricesquawk": {"url": "https://pricesquawk.com/feed/podcast/", "kind": "podcast_rss",
                    "claims": "interview", "lang": "en", "home": "https://pricesquawk.com/"},
}

#: (verdict, why). Unlisted = to_confirm. See the module docstring for the vocabulary.
_BASIS = ("principal 2026-11-17 20:49Z: where the terms do not ban it and the site does not "
          "block the honest agent, read it")
_HOST_UNREAD = ("feed host terms unread (Auditor HOLD 2026-11-17): an unreadable terms page is "
                "not evidence of no ban; reopens when the host terms are read and silent")
TERMS: dict[str, tuple[str, str]] = {
    "chatwithtraders": ("to_confirm", _HOST_UNREAD + "; megaphone.spotify.com/terms is "
                        "robots-disallowed"),
    "twoblokestrading": ("to_confirm", _HOST_UNREAD + "; captivate.fm/terms-of-service "
                         "returned an error"),
    "desiretotrade": ("to_confirm", "Libsyn Master Terms 5.1(g): \"use any robot, spider, data "
                      "scraping, extraction tool or similar mechanism with respect to the Libsyn "
                      "Platform\" (libsyn.com/tos-policies/tos-website/); not silence"),
    "pricesquawk": ("no_terms", _BASIS),
}

#: Evidence per open ground: `url` (terms page read, or the home page where none is linked),
#: `checked` (date) and `quote` (the permitting clause for `confirmed`; for no_ban/no_terms a
#: plain statement of what was read and found absent).
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "pricesquawk": {
        "url": "https://pricesquawk.com/", "checked": "2026-11-17",
        "quote": ("NO TERMS PUBLISHED: the home page links a Privacy Policy and risk and "
                  "testimonial disclosures only, no terms of use; robots.txt has an empty "
                  "Disallow; the feed is served from the publisher's own domain and carries no "
                  "copyright line")},
}

#: Grounds looked at and shut, with the clause. Kept so the next pass does not re-ask, and so
#: the missed growth is a named line and not a silence.
REFUSED: dict[str, dict[str, str]] = {
    "substack": {
        "url": "https://substack.com/tos", "checked": "2026-11-17",
        "quote": "“Crawls,” “scrapes,” or “spiders” any page, data, or "
                 "portion of Substack (through use of manual or automated means)"},
    "tradingnut": {
        "url": "https://tradingnut.com/terms/", "checked": "2026-11-17",
        "quote": "5. Intellectual Property: \"Copying, redistributing, or re-selling content "
                 "without written consent is strictly prohibited.\""},
    "forex_in_rs": {
        "url": "https://www.forex.in.rs/robots.txt", "checked": "2026-11-17",
        "quote": "robots.txt disallows about 23 named AI and data crawlers site-wide and says "
                 "so in a comment; this agent is not named, the intent is, so it is not read"},
    "toptradersunplugged": {
        "url": "https://feeds.captivate.fm/top-traders-unplugged/", "checked": "2026-11-17",
        "quote": "feed copyright: \"The content can not be used for commercial use without "
                 "written permission from CMC AG.\""},
    "fxnx": {
        "url": "https://fxnx.com/legal/terms-of-service.pdf", "checked": "2026-11-17",
        "quote": "s5: \"scrape or copy the Services with bots without our written consent;\""},
    "tradethepool": {
        "url": "https://tradethepool.com/terms-and-conditions", "checked": "2026-11-17",
        "quote": "compile, collect or assemble information pertaining to the Website in order "
                 "to make use of it commercially"},
}


def terms_ok(ground: str, terms: dict[str, tuple[str, str]] | None = None,
             evidence: dict[str, dict[str, str]] | None = None) -> bool:
    """Open only on an open verdict backed by recorded evidence (url, checked, quote)."""
    verdict = (TERMS if terms is None else terms).get(ground, ("to_confirm", ""))[0]
    ev = (TERMS_EVIDENCE if evidence is None else evidence).get(ground, {})
    return verdict in OPEN_VERDICTS and all(ev.get(k) for k in ("url", "checked", "quote"))


# ------------------------------------------------------------------------------- feed parse
_ITEM = re.compile(r"<(item|entry)\b[^>]*>(.*?)</\1>", re.S | re.I)


def _tag(block: str, *names: str) -> str:
    for n in names:
        m = re.search(rf"<{n}\b[^>]*>(.*?)</{n}>", block, re.S | re.I)
        if m:
            s = re.sub(r"^\s*<!\[CDATA\[(.*)\]\]>\s*$", r"\1", m.group(1), flags=re.S)
            return s.strip()
    return ""


def _plain(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _when(block: str) -> str | None:
    raw = _tag(block, "pubDate", "published", "updated", "dc:date")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone(UTC).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        pass
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC).isoformat(
            timespec="seconds")
    except ValueError:
        return None


def parse_feed(body: bytes) -> list[dict[str, Any]]:
    """RSS 2.0 / Atom items -> {id, url, title, text, published}. Show notes only."""
    s = body.decode("utf-8", "replace")
    out = []
    for m in _ITEM.finditer(s):
        b = m.group(2)
        link = _plain(_tag(b, "link"))
        if not link:
            lm = re.search(r"<link\b[^>]*href=[\"']([^\"']+)", b, re.I)
            link = html.unescape(lm.group(1)) if lm else ""
        title = _plain(_tag(b, "title"))[:200]
        text = _plain(max((_tag(b, n) for n in ("content:encoded", "description", "summary",
                                                "itunes:summary", "content")), key=len))
        ident = _plain(_tag(b, "guid", "id")) or link or title
        if ident and (title or text):
            out.append({"id": ident, "url": link or ident, "title": title, "text": text,
                        "published": _when(b)})
    return out


# ------------------------------------------------------------------------------- harvest
def harvest_feeds(fetcher: _fetch._Fetcher | None = None,
                  grounds: dict[str, dict[str, Any]] | None = None, budget_s: float = 600.0,
                  terms: dict[str, tuple[str, str]] | None = None,
                  evidence: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """New feed items -> claim rows in the shared claims file. A ground without an open terms
    verdict is not contacted at all. One request per ground per pass (the feed itself)."""
    f = fetcher or _fetch._Fetcher()
    started = time.monotonic()
    seen = _fetch._load_seen()
    rep: dict[str, Any] = {"by_ground": {}}
    blocked: dict[str, str] = {}
    new: list[dict[str, Any]] = []
    table = GROUNDS if grounds is None else grounds
    for gid, cfg in table.items():
        if not terms_ok(gid, terms, evidence):
            blocked[gid] = (TERMS if terms is None else terms).get(gid, ("to_confirm", ""))[0]
            if blocked[gid] in OPEN_VERDICTS:          # open verdict with no evidence: shut
                blocked[gid] = "to_confirm"
            rep["by_ground"][gid] = {"skipped": "terms", "terms": blocked[gid]}
            continue
        if time.monotonic() - started > budget_s:
            rep["by_ground"][gid] = {"skipped": "budget"}
            continue
        level = cfg.get("claims", "self_reported")
        if level not in VERIFICATION:
            level = "self_reported"
        body = f.get(cfg["url"])          # newest items lead; a truncated feed still parses
        row = {"items": 0, "items_new": 0, "claims_with_mechanism": 0, "outcome": f.outcome}
        now = datetime.now(UTC).isoformat(timespec="seconds")
        for it in parse_feed(body or b"")[: 4 * MAX_NEW_PER_GROUND]:
            row["items"] += 1
            key = f"{gid}:{it['id']}"
            if key in seen or row["items_new"] >= MAX_NEW_PER_GROUND:
                continue
            seen[key] = now
            row["items_new"] += 1
            text = (it["title"] + " " + it["text"]).strip()
            claim = {"firm": gid, "ground_kind": cfg.get("kind", "rss"), "url": it["url"],
                     "title": it["title"], "published_time": it["published"],
                     "available_time": now, "knowable_from": it["published"] or now,
                     "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                     "verification": level, "lang": cfg.get("lang", "en"), **extract(text)}
            if claim["styles"] and claim["instruments"]:
                row["claims_with_mechanism"] += 1
            new.append(claim)
        rep["by_ground"][gid] = row
    if new:
        _fetch.CLAIMS.parent.mkdir(parents=True, exist_ok=True)
        with _fetch.CLAIMS.open("a", encoding="utf-8") as fh:
            for c in new:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
        _fetch._write_atomic(_fetch.SEEN, json.dumps(seen, indent=0))
    rep["fetch_log"] = dict(f.log)
    rep["terms_blocked"] = blocked
    rep["refused_grounds"] = sorted(REFUSED)
    rep["new_claims"] = len(new)
    read = sum(int(r.get("items", 0)) for r in rep["by_ground"].values())
    rep["harvest_status"] = (
        "BLOCKED_ON_TERMS: no ground has an open terms verdict with evidence"
        if not table or len(blocked) == len(table) else
        "MEASURED" if read else
        "UNMEASURED: no feed was read this pass (walls, robots or network)")
    return rep
