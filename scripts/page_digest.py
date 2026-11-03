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

import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGEST = ROOT / "docs/desk_digest.md"
STAMP = ROOT / "data/.last_digest_page"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    # AUDIENCE: DESK (owner, 2026-10-29: "only notify me on things which need me ... handle rest
    # n don't tell me"; rule in libs/ops/alert_channels.py). A digest asks him to DO nothing, so it
    # no longer posts to ntfy.sh directly: send_all routes it to the ledger and the non-personal
    # channels and records the phone as `routed: desk audience`. One patient retry is kept for a
    # transient failure of an armed channel; anything still failing is reported, never raised.
    for attempt in (0, 1):
        if attempt:
            time.sleep(90)
        try:
            from libs.ops.alert_channels import send_all
            # desk_row=False: a digest is information, never a problem to hold the desk RED
            res = send_all("Quant desk: daily digest", body, audience="desk", desk_row=False)
        except Exception as exc:                    # a failed digest must never break a cycle
            print(f"digest page failed{' (after retry)' if attempt else ''}: {exc!r}")
            continue
        if res.get("delivered"):
            try:
                STAMP.write_text(today, "utf-8")
            except OSError as exc:                  # same contract: report, never raise
                print(f"digest stamp not written: {exc!r}")
            print(f"digest paged to desk ({len(parts)} lines, {res.get('routed', 0)} routed)")
            return
        if not res.get("armed"):
            print("no alert channel armed -- digest ledgered NOT-ARMED, not paged")
            return
        print(f"digest page failed{' (after retry)' if attempt else ''}: "
              f"{[r.get('detail') for r in res.get('results', [])]!r}")


if __name__ == "__main__":
    main()
