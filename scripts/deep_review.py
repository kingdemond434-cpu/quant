#!/usr/bin/env python3
"""SINGLE-FILE DEPTH PASS (build #2, principal 2026-07-21).

WHY: in the breadth panel each seat reads ~730k chars across 67 files and returns ~8-15k chars
covering ALL of them -- so binance_live.py, the code that will move real money, receives maybe
one or two paragraphs of attention per model. That is the wrong allocation for the risk lane.

THIS: 13 seats on ONE file with a focused adversarial prompt -> each returns its full response
about that file alone. Roughly 10-50x the attention per file.

This is NOT audit tooling: docs/LIVE_CONNECTOR_SPEC.md section 7 already REQUIRES a
second-model-family fuzz/breaker review before Gate 0. This is the cheap, immediate form of
that bar, and it should be run on all five money-path files before the connector ships.

Usage: deep_review.py libs/execution/binance_live.py [more files...]
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from libs.doctrine.constitution import OBJECTIVE_PREAMBLE  # noqa: E402

OUT = ROOT / "docs/research/deep_review_inbox.md"

# THE CONSTITUTION LEADS HERE TOO, and this is the organ where it earns its keep. A hostile
# reviewer with no objective will recommend caution as a free good -- every clamp looks
# prudent when nothing prices the growth it costs. P6 gives it the right frame: the survival
# rails are immovable AND every other conservative suggestion must name the ruin probability
# it reduces.
SYSTEM = OBJECTIVE_PREAMBLE + """
You are a hostile reviewer of RISK-PATH code for an autonomous crypto trading desk.
This file can move real money. You have zero attachment to its design and no obligation to be
polite. Assume a bug here costs the operator his capital.

Review ONLY the file given. Depth over breadth -- this is your single subject.

Hunt specifically for:
 1. SILENT FAILURE -- any path that swallows an error, returns a default, or continues on bad
    state. Name the exact line and what the caller then believes that is false.
 2. UNBOUNDED ACTION -- orders/retries/loops with no cap, no cooldown, no idempotency key.
 3. STATE RACES -- reads that can be stale between check and act; two writers on one file.
 4. WRONG-DIRECTION FAILURE -- where does it fail OPEN (keep trading) instead of CLOSED?
 5. ARITHMETIC -- sign errors, unit mismatches, float compare, precision/rounding on notionals.
 6. AUTH/CAPABILITY -- anything reachable that should not be (withdrawal, transfer, key mgmt).
 7. WHAT A TEST WOULD MISS -- the failure that only appears under real venue latency, partial
    fills, rate limits, or a 5xx mid-sequence.

For each finding give: LINE(s) | what breaks | the concrete sequence that triggers it | the
minimal fix. Rank by expected loss. If the file is genuinely sound, say so plainly and name the
single riskiest remaining assumption -- do not manufacture findings."""


#: Seat roster. The paid panel is the default; `--panel free` selects the :free tier.
#: THE FALLBACK IS NOT A NICETY -- IT IS THE DIFFERENCE BETWEEN A REVIEW AND NO REVIEW. The paid
#: roster returns HTTP 402 (account out of credit) while three free seats answer normally, so a
#: hardcoded paid path meant this bar could not be met at all during exactly the period when
#: nobody was going to top the account up. Fewer and weaker seats are a WEAKER review, never a
#: lower bar: the section-7 obligation is a second-model-family adversarial pass, and the
#: inbox records which roster produced it so a thin pass is never mistaken for a full one.
_PANELS = {"paid": "data/secrets/llm_panel.json", "free": "data/secrets/llm_panel_free.json"}


def main() -> None:
    argv = sys.argv[1:]
    panel = "paid"
    if "--panel" in argv:
        i = argv.index("--panel")
        panel = argv[i + 1] if i + 1 < len(argv) else "paid"
        if panel not in _PANELS:
            raise SystemExit(f"--panel must be one of {sorted(_PANELS)}, got {panel!r}")
        del argv[i:i + 2]
    files = argv
    if not files:
        raise SystemExit(__doc__)
    # THIS ORGAN HAS NEVER PRODUCED A SINGLE REVIEW, and not for want of credentials.
    # Commit 0debac3 changed `_ask(base_url, key, model, system, user, timeout)` to
    # `_ask(base_url, key, model, messages, timeout)` and updated every caller except this one and
    # capacity_test.py. The old call therefore passed SYSTEM as `messages` and the prompt as
    # `timeout`, so all 13 seats raised `TypeError: 'str' object cannot be interpreted as an
    # integer` -- and `one()` catches Exception, so the failure rendered as thirteen tidy "FAILED"
    # lines and an inbox reading "0/13 seats responded" rather than as a broken call. R0231 was
    # triaged BLOCKED-OPERATOR on missing panel credentials; data/secrets/llm_panel.json has held
    # 13 funded providers since 2026-07-23. The blocker was this.
    from scripts.run_external_panel import _ask

    from libs.llm.push import build_turns
    # risk-path depth passes run at MAX effort: this is the review standing between
    # the desk and real money, the one place where correctness outranks token cost
    # (elsewhere xhigh wins -- max is documented as prone to overthinking).
    providers = json.loads((ROOT / _PANELS[panel]).read_text())["providers"]
    ts = datetime.now(tz=UTC).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    for rel in files:
        fp = ROOT / rel
        if not fp.exists():
            print(f"skip (missing): {rel}")
            continue
        body = fp.read_text("utf-8", errors="ignore")
        prompt = (f"FILE UNDER REVIEW: {rel} ({len(body.splitlines())} lines)\n\n"
                  f"```python\n{body}\n```\n\nReview it per your mandate. Depth, not breadth.")
        print(f"\n=== DEEP REVIEW: {rel} ({len(body):,} chars) x {len(providers)} seats ===")

        def one(pv, prompt=prompt):  # bind loop var per-iteration (ruff B023)
            try:
                r = _ask(pv["base_url"], pv["key"], pv["model"], build_turns(SYSTEM, prompt))
                if len(r.strip()) < 200:
                    r = _ask(pv["base_url"], pv["key"], pv["model"], build_turns(SYSTEM, prompt))
                print(f"  {pv['model']}: {len(r)} chars")
                return {"model": pv["model"], "response": r}
            except Exception as e:
                print(f"  {pv['model']}: FAILED {e!r}"[:110])
                return {"model": pv["model"], "error": repr(e)[:200]}

        with ThreadPoolExecutor(max_workers=6) as ex:
            res = list(ex.map(one, providers))
        ok = [r for r in res if "response" in r]

        with OUT.open("a", encoding="utf-8") as f:
            f.write(f"\n\n# DEEP REVIEW -- {rel} -- {ts}\n"
                    f"{len(ok)}/{len(res)} seats responded on the {panel.upper()} roster. "
                    "RISK-PATH depth pass "
                    "(LIVE_CONNECTOR_SPEC section 7 bar). Triage per panel protocol: verify every "
                    "claim against the code; consensus = high prior; record each accepted finding "
                    "via scripts/track_findings.py so it cannot be silently dropped.\n")
            for r in ok:
                f.write(f"\n## {r['model']}\n\n{r['response']}\n")
        print(f"  -> {OUT} ({len(ok)}/{len(res)} responded)")


if __name__ == "__main__":
    main()
