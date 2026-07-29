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
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS = ROOT / "data/secrets/llm_panel.json"
OUT = ROOT / "data/code_audit.jsonl"
CTX = ssl.create_default_context()

SEATS = ["deepseek/deepseek-v4-pro", "x-ai/grok-4.3", "moonshotai/kimi-k3"]
N_COMMITS = 3
MAX_DIFF_CHARS = 45000

SYSTEM = (
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



def _doctrine(role: str = "") -> str:
    """Runtime doctrine preamble. One source (scripts/doctrine.py); never a pasted copy."""
    try:
        from scripts.doctrine import preamble
        return preamble(role)
    except Exception:  # blind-except intentional (BLE001)
        try:
            import sys as _s
            _s.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
            from doctrine import preamble  # type: ignore
            return preamble(role)
        except Exception:  # blind-except intentional (BLE001)
            return ""          # never break a caller over a preamble


def _ask(base, key, model, system, user, timeout=240.0):
    body = json.dumps({"model": model, "max_tokens": 3000, "temperature": 0.2,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": _doctrine("llm_code_auditor") + system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


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
    provs = {p["model"]: p for p in json.loads(KEYS.read_text("utf-8"))["providers"]
             if isinstance(p, dict)}
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
    for seat in SEATS:
        prov = provs.get(seat)
        if not prov:
            print(f"  {seat}: not in roster")
            continue
        try:
            txt = _ask(prov["base_url"], prov["key"], seat, SYSTEM, user)
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
