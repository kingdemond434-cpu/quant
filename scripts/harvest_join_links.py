#!/usr/bin/env python3
"""JOIN-LINK HARVEST -- the miner finds the doors, the principal walks through them.

THE LOOP THIS CLOSES, and nothing else on the desk closes it. The miners index the OPEN web. The
material that actually converts lives in CLOSED rooms -- WeChat 群, Telegram channels, Discord
servers, KakaoTalk open chats -- which no amount of engineering reaches, because a membership is a
person and not a credential. But those rooms ADVERTISE THEMSELVES on the open web: an invite link
in a Qiita post, a t.me URL in a DCInside thread, a QR page linked from a 公众号 article. The
miners were already fetching pages carrying those links and throwing them away.

    miner (open web) -> invite link found -> ntfy push -> PRINCIPAL JOINS -> drops content
                                                                    -> ingest_principal_drop
                                                                    -> same triage bar as anything

So the desk cannot join a room, and it CAN tell the principal which door is worth walking through.
That is a strictly better division of labour than either half alone: the desk has the reach to
find a thousand candidate rooms and no way in; the principal has the way in and no time to search.

WHAT IS PUSHED, AND WHY IT IS RANKED. Every invite link on the open web is not worth joining --
most are paid-signal groups and pump channels, which is why they advertise. A link is scored by
the CONTEXT it appeared in, using the same `video_triage` ranker that scores everything else: a
t.me URL inside a post about funding-rate settlement mechanics is worth a look, the same URL
inside a post about 10x guaranteed signals is not. Only links whose surrounding text clears the
miner's own threshold are pushed, and the push CARRIES that context so the principal can decide in
one glance rather than by opening it.

DE-DUPLICATED ACROSS RUNS, permanently. A link seen once is recorded in data/join_links.jsonl and
never pushed again, whatever the principal decided -- because a pager that re-sends the same
invite every six hours is a pager that gets muted, and a muted pager is how this desk lost eleven
and a half days of alerting once already.

NOTHING HERE JOINS ANYTHING, and it cannot. It sends a message. Every decision -- whether to join,
under what identity, and whether the room's contents may be used -- is the principal's, made
outside this repo. The desk has no account and asks for none.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.alert_channels import send_all  # noqa: E402
from libs.research.video_triage import score_title  # noqa: E402

QUEUE = _ROOT / "reports/research_queue.json"
SEEN = _ROOT / "data/join_links.jsonl"
OUT = _ROOT / "reports/join_links.json"

#: Invite-link shapes, per platform. Deliberately NARROW: these match the canonical invite forms
#: and nothing else, because a false positive costs the principal a wasted click on a pager push
#: and the pager's credibility is the scarce resource here, not the link.
_PATTERNS: dict[str, re.Pattern[str]] = {
    "telegram": re.compile(r"https?://(?:t\.me|telegram\.me)/(?:joinchat/)?[\w+-]{5,}", re.I),
    "discord": re.compile(r"https?://(?:discord\.gg|discord\.com/invite)/[\w-]{5,}", re.I),
    "kakao": re.compile(r"https?://open\.kakao\.com/o/[\w]{5,}", re.I),
    "line": re.compile(r"https?://line\.me/(?:ti/g|R/ti/g)/[\w-]{5,}", re.I),
    "wechat": re.compile(r"https?://(?:weixin\.qq\.com/g/|mp\.weixin\.qq\.com/s/)[\w-]{5,}", re.I),
    "slack": re.compile(r"https?://join\.slack\.com/t/[\w-]+/shared_invite/[\w-]+", re.I),
    "matrix": re.compile(r"https?://matrix\.to/#/[#!][\w:.-]{5,}", re.I),
}


def _seen_urls(path: Path) -> set[str]:
    """Every link ever pushed. Read permissively: a corrupt line must not cause a re-push of the
    whole history, which is the failure that mutes a pager."""
    out: set[str] = set()
    if not path.exists():
        return out
    for line in path.read_text("utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            out.add(str(json.loads(line).get("url", "")))
        except ValueError:
            continue
    return out


def find_links(text: str) -> list[tuple[str, str]]:
    """(platform, url) pairs in one blob of text, de-duplicated, order preserved."""
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for platform, pat in _PATTERNS.items():
        for m in pat.finditer(text or ""):
            url = m.group(0).rstrip(".,);]\"'")
            if url in seen:
                continue
            seen.add(url)
            hits.append((platform, url))
    return hits


def harvest(root: Path | None = None, *, threshold: float = 3.0,
            seen_path: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    seen_file = seen_path if seen_path is not None else SEEN
    already = _seen_urls(seen_file)
    queue_path = root / "reports/research_queue.json"

    rows: list[dict[str, Any]] = []
    if queue_path.exists():
        try:
            doc = json.loads(queue_path.read_text("utf-8"))
        except (OSError, ValueError):
            doc = {}
        for r in doc.get("queue") or []:
            if not isinstance(r, dict):
                continue
            # Title AND url: an invite sometimes IS the row's url (a 公众号 article that is
            # nothing but a QR page), and sometimes sits inside the title text.
            blob = f"{r.get('title', '')} {r.get('url', '')}"
            for platform, url in find_links(blob):
                if url in already:
                    continue
                # SCORED BY CONTEXT, not by existing. Most invite links on the open web advertise
                # paid-signal groups -- that is WHY they advertise. The surrounding text is the
                # only evidence available about whether the room is worth a person's time.
                context = str(r.get("title", ""))
                score, why = score_title(context)
                if score < threshold:
                    continue
                already.add(url)
                rows.append({
                    "platform": platform, "url": url,
                    "context": context[:200],
                    "found_in": str(r.get("channel", "")),
                    "source_url": str(r.get("url", ""))[:200],
                    "score": round(score, 1), "why": why,
                    "found_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                })
    rows.sort(key=lambda r: -float(r["score"]))
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "threshold": threshold,
        "n_new": len(rows),
        "n_seen_all_time": len(already),
        "links": rows,
        "note": ("The desk CANNOT join any of these -- a membership is a person, not a "
                 "credential. It can only say which door looks worth walking through. Joining, "
                 "the identity used, and whether the room's contents may be used are the "
                 "principal's decisions, made outside this repo."),
        "loop": ("miner (open web) -> invite link -> ntfy push -> principal joins -> drops "
                 "content into data/inbox -> ingest_principal_drop -> same triage bar"),
    }


def _record(rows: list[dict[str, Any]], seen_file: Path) -> None:
    seen_file.parent.mkdir(parents=True, exist_ok=True)
    with seen_file.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threshold", type=float, default=3.0)
    ap.add_argument("--no-push", action="store_true",
                    help="find and record, but do not page (for a dry run)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rep = harvest(threshold=args.threshold)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1, ensure_ascii=False), "utf-8")

    pushed = 0
    if rep["links"] and not args.no_push:
        # ONE PUSH FOR THE BATCH, never one per link. A pager that fires eight times in a minute
        # trains the principal to swipe it away, and this desk has already lost eleven and a half
        # days of alerting to a pager nobody was reading.
        lines = [f"{r['score']:.0f} [{r['platform']}] {r['context'][:70]}\n{r['url']}"
                 for r in rep["links"][:8]]
        extra = f"\n(+{len(rep['links']) - 8} more in reports/join_links.json)" \
            if len(rep["links"]) > 8 else ""
        body = ("Rooms the miner found and cannot enter. Join any that look worth it, then drop "
                "their content into data/inbox for the desk to read.\n\n"
                + "\n\n".join(lines) + extra)
        send_all(f"{len(rep['links'])} join link(s) found", body)
        pushed = len(rep["links"])
        _record(rep["links"], SEEN)          # recorded ONLY after a push was attempted
    elif rep["links"]:
        _record(rep["links"], SEEN)

    if args.json:
        print(json.dumps(rep, indent=1, ensure_ascii=False))
    else:
        print(f"join links: {rep['n_new']} new, {rep['n_seen_all_time']} seen all-time"
              f"{'  (pushed)' if pushed else ''}")
        for r in rep["links"][:10]:
            print(f"  {r['score']:5.1f} [{r['platform']:9s}] {r['url']}")
            print(f"         from {r['found_in']}: {r['context'][:66]}")
        if not rep["n_new"]:
            print("  no new invite links in the current queue -- the miner surfaces these only "
                  "when a page it already fetched happens to carry one")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
