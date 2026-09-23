"""LLM CODE AUDITOR -- adversarial review of the desk's own recent diffs.

*** WRITTEN BUT NEVER EXECUTED (OpenRouter 402 on 2026-07-27). UNTESTED CODE. ***
The brain must run it once and check the output before anything relies on it. Given that the two
validators I DID test both shipped with high false-positive rates, assume this one has bugs too.

WHY IT EXISTS -- measured, not theoretical. On 2026-07-27 I shipped and self-corrected NINE
defects, several in safety-critical machinery:
  * activation gate FAILED OPEN (counted keyword hits in prose, found "63 survivors" against a
    true count of 0, and authorised itself -- the gate built to prevent fitting-on-noise licensed
    exactly that)
  * budget guard read keys that DO NOT EXIST (monthly_usd_cap vs monthly_envelope_usd), printed
    "no cap configured" while a real $120 envelope sat in the file
  * leak-detection condition written BACKWARDS (flagged the healthy pattern as the artifact)
  * "FAILS TO REPLICATE" printed for a result that replicated, because z missed an arbitrary 2.0
  * cost estimate 27x optimistic ($0.008 vs measured $0.225/call) -> caused a 402 mid-run
  * double z-scoring collapsed every signal to zeros (INSUFFICIENT-DATA on everything)
  * futures MIN_NOTIONAL read via the spot key -> returned 0.0, understating a capacity floor
  * two validators shipped flagging config constants and clocks as market-data anomalies
I caught them all by re-reading. A cold model reading the diff would plausibly catch several
FASTER, and -- the actual point -- would catch the ones I cannot see, because I cannot audit my
own blind spots.

The prompt below encodes THIS taxonomy rather than generic "find bugs", because these are the
failure modes this codebase actually produces.
"""
from __future__ import annotations

import json
import ssl
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from libs.doctrine.constitution import (  # noqa: E402
    OBJECTIVE_PREAMBLE,
    RESIDUAL_MANDATE,
    RESIDUAL_PROTOCOL,
)
from libs.llm.effort import reasoning_payload  # noqa: E402
from libs.llm.push import PUSH_LADDER, push_rounds  # noqa: E402
from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above

KEYS = ROOT / "data/secrets/llm_panel.json"
OUT = ROOT / "data/code_audit.jsonl"
CTX = ssl.create_default_context()

SEATS = ["deepseek/deepseek-v4-pro", "x-ai/grok-4.3", "moonshotai/kimi-k3"]
N_COMMITS = 3
MAX_DIFF_CHARS = 45000

SYSTEM = (
    # THE CONSTITUTION LEADS. An organ that does not carry the objective optimises for
    # what its output LOOKS like rather than for expected shift in E[log W] -- and, worse,
    # quietly recommends the timid option because nothing told it that timidity is a
    # scored defect rather than a neutral default.
    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + RESIDUAL_PROTOCOL + "\n"
    "You are a hostile code reviewer for a quantitative trading desk. Your job is to find bugs "
    "that would cause SILENT WRONG BEHAVIOUR -- not style, not typing, not performance. A crash "
    "is safe because someone notices. A confident wrong number is not.\n\n"
    "This codebase has a MEASURED history of these exact defect classes. Hunt them first:\n"
    "1. FAIL-OPEN GUARDS  -- a safety gate whose default/ambiguous branch ALLOWS the action. Any "
    "gate must fail CLOSED. Check what happens on missing files, empty lists, exceptions, None.\n"
    "2. WRONG KEY NAMES   -- reading a dict key that does not exist, silently getting 0/None/'' "
    "and treating it as real. Cross-check every .get() against the file it reads.\n"
    "3. INVERTED CONDITIONS -- comparison or sign written backwards so the healthy case is "
    "flagged and the broken case passes.\n"
    "4. MECHANICAL THRESHOLDS -- a hard cutoff (z>=2.0, p<0.05) applied without checking SIGN or "
    "effect size, mislabelling a real result or blessing a fake one.\n"
    "5. DOUBLE TRANSFORMATION -- normalising/z-scoring/scaling data that is already normalised; "
    "look for a value passed through the same transform twice.\n"
    "6. UNIT / MAGNITUDE ERRORS -- bps vs %, seconds vs ms, per-call vs per-run cost.\n"
    "7. MISSING GATE -- the test runs correctly but omits a check that would invalidate every "
    "passing result (e.g. a spread screen with no transaction-cost comparison).\n"
    "8. LOOKAHEAD -- using data timestamped at or after the prediction target; misaligned "
    "candle/timezone conventions; forward-shifted series.\n\n"
    "Output ONE finding per line, most severe first, format:\n"
    "SEVERITY | FILE:LINE | CLASS | what breaks | concrete input that triggers it\n"
    "SEVERITY is CRITICAL (wrong trading/sizing decision), HIGH (wrong research conclusion) or "
    "MED. If you find nothing real, output exactly: NO-FINDINGS. Do not invent findings to seem "
    "useful -- a false finding costs more than a missed one here."
)


def _ask(base, key, model, messages, timeout=240.0):
    body = json.dumps({"model": model, "max_tokens": 3000, "temperature": 0.2,
                       # DEPTH IS MEASURED, NOT ASSUMED. "high" is the middle rung of a ladder
                       # whose top differs per model and per month -- a literal here is
                       # capability left unused on a flagship the desk pays for.
                       "reasoning": reasoning_payload(model),
                       "messages": messages}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def _ask_pushed(base, key, model, system, user):
    """Push until the seat is measurably exhausted -- standing policy across every LLM organ.

    The context (system prompt + payload) is the expensive half and is already paid for; the
    ladder reuses it and keeps asking until novelty dies, the model surrenders, or the round cap
    binds. Returns (joined_text, stop_reason).
    """
    r = push_rounds(lambda msgs: _ask(base, key, model, msgs), system, user, ladder=PUSH_LADDER)
    return r.text, f"{r.rounds} push round(s); {r.stop_reason}"


def recent_diff(n: int) -> str:
    try:
        return subprocess.run(["git", "diff", f"HEAD~{n}", "HEAD", "--", "*.py"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              check=False, timeout=60).stdout
    except Exception:
        return ""


def main() -> None:
    if not KEYS.exists():
        print("no panel keys")
        return
    # Live-roster resolution: an upgraded-away seat is substituted (same lab first), not lost.
    # SEAT CAP REMOVED (2026-07-31). This read `n=len(SEATS)`, so the LITERAL'S LENGTH capped how
    # many funded seats were ever asked -- 3 of 13. Five organs shared the bug. SEATS is a
    # PRIORITY ORDER, not a membership list: the preferred list is now built from the LIVE roster
    # so every seat the desk pays for does the desk's work, and growing the roster grows the
    # organ. seats.resolve still substitutes an upgraded-away model same-lab-first.
    _roster = [str(p["model"]) for p in seats.load_roster()]
    _pref = SEATS + [m for m in _roster if m not in SEATS]
    provs = {p["model"]: p for p in seats.resolve(_pref, n=None, role="llm_code_auditor")}
    diff = recent_diff(N_COMMITS)
    if not diff.strip():
        print("no python diff in the last commits")
        return
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n...[truncated]"
    print(f"=== LLM CODE AUDITOR | last {N_COMMITS} commits | {len(diff)} chars ===")
    print("    *** UNTESTED SCRIPT -- verify output before trusting it ***\n")

    user = ("Review this diff. Report only defects causing SILENT WRONG BEHAVIOUR.\n\n" + diff)
    rows = []
    for seat in list(provs):
        prov = provs.get(seat)
        if not prov:
            print(f"  {seat}: not in roster")
            continue
        try:
            txt, _stop = _ask_pushed(prov["base_url"], prov["key"], seat, SYSTEM, user)
            print(f"  {seat}: {_stop}")
        except Exception as e:
            print(f"  {seat.split('/')[-1]:<20} FAILED ({type(e).__name__} "
                  f"{getattr(e, 'code', '')})")
            continue
        found = 0
        for ln in txt.splitlines():
            if ln.strip().upper().startswith("NO-FINDINGS"):
                break
            if ln.count("|") >= 4:
                parts = [x.strip() for x in ln.split("|")]
                rows.append({"date": datetime.now(tz=UTC).isoformat(), "seat": seat,
                             "severity": parts[0][:12], "where": parts[1][:80],
                             "klass": parts[2][:40], "what": parts[3][:220],
                             "trigger": parts[4][:220]})
                found += 1
        print(f"  {seat.split('/')[-1]:<20} {found} findings")

    if rows:
        with OUT.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    crit = [r for r in rows if r["severity"].upper().startswith("CRIT")]
    print(f"\n  {len(rows)} findings ({len(crit)} CRITICAL)")
    for r in sorted(rows, key=lambda x: x["severity"])[:12]:
        print(f"    [{r['severity']:<8}] {r['where']:<44} {r['klass']}")
        print(f"               {r['what'][:110]}")
    print("\n  AGREEMENT ACROSS SEATS is the signal -- one seat alone is a hypothesis, not a bug.")
    print("  Every finding must be REPRODUCED before acting; models invent plausible defects.")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
