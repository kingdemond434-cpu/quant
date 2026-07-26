#!/usr/bin/env python3
"""DAILY FINDINGS PAGE -- one push a day carrying what the desk actually found.

BOSS DECISION on the principal's question ("can you report findings immediately when I'm not
there?"). I cannot write to a chat window while he is away, but the pager reaches him and the
digest is already generated daily -- what was missing was DELIVERY, not content.

DELIBERATELY NOT one page per finding. The desk already learned this the hard way: pager spam
(deadman + growth_defect + latched nags) trained the principal to ignore the channel and forced a
per-key dedupe. A channel he ignores is worse than no channel, and findings are exactly the class
that would spam it -- the miners produce dozens of cards a day. So:

  * IMMEDIATE page (already live in run_alerts) stays reserved for what genuinely needs a human:
    money-path defects, risk alarms, licence/legal blockers, and anything requiring his decision
    or spend.
  * THIS page is the once-daily digest: book state, validation clocks, what was mined and
    converted, and the top open item -- high signal, one buzz, readable in ten seconds.

Idempotent: writes data/.last_digest_page so a re-run inside the same UTC day is a no-op.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST = ROOT / "docs/desk_digest.md"
STAMP = ROOT / "data/.last_digest_page"
NTFY = ROOT / "data/secrets/ntfy.json"


def _section(text: str, name: str, limit: int = 3) -> list[str]:
    """The first few bullet lines under a '## <name>' heading."""
    out: list[str] = []
    hit = False
    for ln in text.splitlines():
        if ln.startswith("## "):
            hit = ln[3:].strip().lower().startswith(name.lower())
            continue
        if hit and ln.strip().startswith("-"):
            out.append(re.sub(r"[*_`\[\]]", "", ln.strip("- ").strip()))
            if len(out) >= limit:
                break
    return out


def main() -> None:
    today = datetime.now(tz=UTC).date().isoformat()
    if STAMP.exists() and STAMP.read_text("utf-8").strip() == today:
        print("digest already paged today")
        return
    if not DIGEST.exists():
        print("no digest to page")
        return
    txt = DIGEST.read_text("utf-8", errors="ignore")

    parts: list[str] = []
    for name, lim in (("Book", 2), ("Validation clocks", 2), ("Mined", 2), ("Open", 2)):
        for ln in _section(txt, name, lim):
            parts.append(f"- {ln[:150]}")
    if not parts:                                   # fall back to the first bullets in the file
        parts = [f"- {re.sub(r'[*_`]', '', ln.strip()[:150])}"
                 for ln in txt.splitlines() if ln.strip().startswith("-")][:5]

    body = f"DESK DIGEST {today}\n" + "\n".join(parts[:8])
    try:
        topic = json.loads(NTFY.read_text("utf-8")).get("topic")
    except Exception:
        topic = None
    if not topic:
        print("no ntfy topic configured -- digest not paged")
        return
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
                                 method="POST")
    req.add_header("Title", "Quant desk: daily digest")
    req.add_header("Priority", "low")               # informational -- never buzzes like an alarm
    try:
        urllib.request.urlopen(req, timeout=20)
        STAMP.write_text(today, "utf-8")
        print(f"digest paged ({len(parts)} lines)")
    except Exception as exc:                        # a failed digest must never break a cycle
        print(f"digest page failed: {exc!r}")


if __name__ == "__main__":
    main()
