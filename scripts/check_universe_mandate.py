"""One universe, one truth. Find every entry point that still claims otherwise.

WHY THIS EXISTS (principal audit, 2026-08-29)

    CANONICAL LAW                      LEGACY DAILY RESEARCH ENGINE
    docs/LAWS.md:40-45                 scripts/run_daily_research.py
    "the full MT5/Fusion Markets       "Daily research batch -- CRYPTO-ONLY"
     universe ... No crypto-             _STEPS: crypto ingestion, funding
     exchange-native universe"           shadows, Deribit VRP, Hyperliquid
                                         "MT5 abandoned."

Both were in the repo, both described themselves as authoritative, and the second still presented
itself as a spawned daily chain -- `run_crypto_testnet.py` Popens it detached. Whichever a reader
opened first became what they believed the desk hunts.

A contradiction like this is not a documentation problem. It is an operational one: the retired
chain consumes compute, writes artifacts, and produces numbers that later get read as if they
described the canonical universe. The crypto retirement was executed with non-root switches
(`data/RECORDERS_OFF`) precisely because root units could not be removed, so "it is not
scheduled" was never the same as "it cannot run".

WHAT THIS CHECKS. Every executable entry point for text that asserts a universe, and whether that
assertion survives contact with `docs/LAWS.md`. An entry point declaring retired ground must
either HALT on the mandate (like `run_daily_research.py` now does) or say plainly that it is
archived. Declaring it and running anyway is the defect.

WHY IT DOES NOT DELETE. Deleting the offender loses the crypto-era work it encodes and, worse, a
deleted file cannot tell anyone why it went. A halt that cites the law converts a silent
contradiction into an auditable refusal, which is what one truth actually requires. This reports;
the halt is what enforces.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "universe_mandate.json"
LAWS = ROOT / "docs" / "LAWS.md"

#: Phrases that assert THIS FILE works retired ground.
#:
#: CASE-SENSITIVE AND ANCHORED, after a first version that was neither. Matching /crypto[- ]only/i
#: anywhere in a file flagged four innocent modules, and the text it caught was the LAWS-COMPLIANT
#: phrasing: "crypto only as information for an MT5 move" is exactly what the mandate permits, and
#: `hypothesis_generator.py` was correctly telling its models so. A checker that flags the right
#: behaviour is worse than no checker -- it trains everyone to skim past its output.
#:
#: The real signal is a file DECLARING its scope: shouted, hyphenated, in the module docstring.
#: Prose using the words in a sentence is not a declaration.
_RETIRED_CLAIMS = (
    re.compile(r"CRYPTO-ONLY"),                        # shouted: a scope declaration
    re.compile(r"MT5 abandoned", re.I),
    re.compile(r"crypto-native (?:portfolio|universe)", re.I),
)

#: Explicitly permitted by LAWS: crypto as REFERENCE data informing an MT5 instrument. A file
#: saying this is complying, not offending, and must never be flagged for saying so clearly.
_PERMITTED = re.compile(r"crypto only as information", re.I)

#: A declaration lives at the top of a file. Beyond this many characters it is a comment inside
#: some function about one code path, which is not the file claiming a universe.
_DECLARATION_WINDOW = 2500

#: A file carrying one of these is already dealt with: it refuses to run, or says it is archived.
_EXEMPT = (
    re.compile(r"HALTED BY MANDATE", re.I),
    re.compile(r"_mandate_halt", re.I),
    re.compile(r"\bRETIRED\b.{0,40}\b20\d\d-\d\d-\d\d", re.I),
    re.compile(r"preserved for audit", re.I),
)

#: Scanned roots. Tests are excluded: a test that ASSERTS the retired path halts must be free to
#: name it, and flagging that would make the check punish its own enforcement.
_SCAN = ("scripts", "libs", "desks")


def main() -> int:
    now = datetime.now(tz=UTC)
    try:
        laws = LAWS.read_text("utf-8")
    except OSError:
        print("MANDATE: cannot read docs/LAWS.md -- absence is never permission; failing closed.")
        return 1

    canonical_mt5 = ("No crypto-exchange-native universe" in laws
                     or "MT5/Fusion Markets universe" in laws)
    offenders: list[dict] = []
    exempted: list[str] = []

    for root in _SCAN:
        base = ROOT / root
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts or "/tests/" in str(p) or p.parts[-2] == "tests":
                continue
            try:
                text = p.read_text("utf-8")
            except OSError:
                continue
            head = text[:_DECLARATION_WINDOW]
            hits = [r.pattern for r in _RETIRED_CLAIMS if r.search(head)]
            if not hits or _PERMITTED.search(head):
                continue
            rel = str(p.relative_to(ROOT))
            if any(r.search(text) for r in _EXEMPT):
                exempted.append(rel)
                continue
            offenders.append({"file": rel, "claims": hits})

    report = {"checked_at": now.isoformat(timespec="seconds"),
              "canonical_universe_is_mt5": canonical_mt5,
              "offenders": offenders, "halted_or_archived": sorted(exempted)}
    OUT.write_text(json.dumps(report, indent=1), "utf-8")

    print(f"UNIVERSE MANDATE {now.isoformat(timespec='seconds')}")
    print(f"  canonical universe is MT5/Fusion: {canonical_mt5}")
    print(f"  entry points already halting or archived: {len(exempted)}")
    for f in sorted(exempted)[:8]:
        print(f"    OK  {f}")
    if offenders:
        print(f"\n  CONTRADICTIONS ({len(offenders)}) -- these declare retired ground and do NOT "
              f"halt on the mandate. Each is a second truth about what this desk hunts:")
        for o in offenders:
            print(f"    {o['file']}: {', '.join(o['claims'])}")
        print("  Fix: add a mandate halt that reads docs/LAWS.md and refuses (see "
              "scripts/run_daily_research.py:_mandate_halt), or mark the file archived.")
    print(f"\n  -> {OUT}")
    return 1 if offenders else 0


if __name__ == "__main__":
    raise SystemExit(main())
