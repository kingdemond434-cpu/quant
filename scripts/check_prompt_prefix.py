#!/usr/bin/env python3
"""PROMPT PREFIX FENCE -- the shared doctrine must stay byte-identical across every seat.

WHY THIS NEEDS A FENCE AND NOT JUST A CONVENTION (measured 2026-08-26). 88% of each regional
frontier prompt was the same doctrine as the other six, but scattered through the file rather
than hoisted, so the identical PREFIX was ZERO lines long: prompt caching could hold none of it
and ~41,500 tokens of the same text were re-sent from scratch every cycle across seven seats.

Hoisting it fixed that. The problem is that the fix is invisible and fragile in the same breath:
a single character edited into one seat's copy of the shared block -- a typo, a well-meant
regional tweak, a merge -- splits the cache for ALL of them, restores the old cost in full, and
nothing anywhere would say so. The saving would evaporate silently, which is the same class as
every other defect this desk has had to find by hand.

So the invariant is checked: every regional prompt must open with the same prefix, and that
prefix must be at least MIN_PREFIX_LINES long. A drift is reported with the seat and the first
differing line, because "the prompts differ" is not actionable and "seat ru diverges at line 212"
is.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIONS = ("en", "ru", "ar", "cn", "br", "kr", "jp")
OUT = ROOT / "data" / "prompt_prefix.json"
ALARM = ROOT / "data" / "PROMPT_PREFIX_ALARM.txt"

#: Below this the hoist has effectively been undone and the cache saving is gone.
MIN_PREFIX_LINES = 300


def main() -> int:
    now = datetime.now(tz=UTC)
    texts: dict[str, list[str]] = {}
    for r in REGIONS:
        p = ROOT / "ops" / f"frontier_{r}_prompt.txt"
        if p.exists():
            texts[r] = p.read_text("utf-8").split("\n")
    if len(texts) < 2:
        print("prompt prefix: fewer than two seats present -- nothing to compare")
        return 0

    base = texts["en"] if "en" in texts else next(iter(texts.values()))
    n = 0
    diverged: dict[str, int] = {}
    while n < len(base):
        line = base[n]
        bad = [r for r, v in texts.items() if n >= len(v) or v[n] != line]
        if bad:
            for r in bad:
                diverged.setdefault(r, n)
            break
        n += 1

    words = len(" ".join(base[:n]).split())
    report = {
        "checked_at": now.isoformat(timespec="seconds"),
        "seats": len(texts), "prefix_lines": n, "prefix_words": words,
        "approx_cacheable_tokens": int(words * 1.33),
        "approx_tokens_saved_per_cycle": int(words * 1.33) * max(0, len(texts) - 1),
        "first_divergence": diverged,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1), "utf-8")

    if n >= MIN_PREFIX_LINES:
        if ALARM.exists():
            ALARM.unlink()
        print(f"prompt prefix: {n} identical lines across {len(texts)} seats "
              f"(~{report['approx_cacheable_tokens']:,} cacheable tokens, "
              f"~{report['approx_tokens_saved_per_cycle']:,} saved per cycle)")
        return 0

    body = (f"PROMPT PREFIX DRIFT {now.isoformat(timespec='seconds')}\n\n"
            f"  shared prefix is {n} lines, below the {MIN_PREFIX_LINES}-line floor.\n"
            f"  seats diverging first: {diverged}\n"
            f"  Effect: prompt caching can no longer hold the shared doctrine, so ~"
            f"{int(5300 * 1.33) * 6:,} tokens per cycle are re-sent uncached. Re-hoist the "
            f"shared block to the top of every seat, byte-identical.\n")
    ALARM.write_text(body, "utf-8")
    print(body)
    return 1


if __name__ == "__main__":
    sys.exit(main())
