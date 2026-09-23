"""Is this desk still structurally hourly, and does anything still assume it?

    py -3 desks\\mt5\\scripts\\check_timeframe_coverage.py

TWO QUESTIONS, ONE ANSWER EACH, AND NEITHER WAS BEING ASKED.

**Can the desk see other charts?** `download_all_symbols.py` keyed its "already downloaded" set by
SYMBOL alone, computed from `*_H1.parquet` -- so the moment a symbol had an H1 file the downloader
considered it finished and never fetched a second timeframe for it. Not once, ever. The store held
101 H1 files and six non-H1 in total, all placed by hand, and the desk was structurally hourly
while looking like it had chosen to be. That keying is fixed and every timeframe is now eligible;
nothing checks whether the fetch has actually HAPPENED, which is this script's first job.

**Does anything still assume H1 anyway?** A filled lake buys nothing if the code reads `_H1`
regardless. The severity of that assumption depends entirely on where it sits, so hits are graded
rather than counted:

    MONEY / PIPELINE   a cell hunted on M5 gets replayed on H1 bars and fails, and the failure
                       reads as "this mechanism does not work" rather than "it was never tested"
    MINER SOURCE       `"timeframe": "H1"` written as a DEFAULT into every mined row flattens the
                       chart a strategy was actually described on, before the docket ever sees it
    THROWAWAY          a one-off debug script with a hardcoded path. Noise in a grep, harmless.

A raw count over the tree reports ~330 and is useless; three of those hits matter more than the
other three hundred put together.

WHY IT IS AN EDGE QUESTION, not tidiness. Mechanisms live on charts. A desk that researches one
timeframe cannot discover anything whose signal is faster or slower than that timeframe, and it
will never know what it missed, because an untested mechanism produces no evidence of its absence.
Breadth across charts is breadth.

Reads only. It downloads nothing and edits nothing; `download_all_symbols.py` fetches.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
REPO = DESK.parent.parent
for _p in (str(DESK), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = DESK / "data" / "universe"
REPORT = DESK / "reports" / "TIMEFRAME_COVERAGE.json"

#: Charts the desk stores, in speed order. Kept in step with `download_all_symbols.TIMEFRAME_DEPTH`
#: -- and the check below asserts they agree, because two lists that must match and are compared
#: by nothing will drift.
EXPECTED_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")

#: Directories whose H1 literals are one-off debugging, not desk behaviour. Everything else is
#: graded on where it sits rather than excused by where it sits.
THROWAWAY_HINTS = ("sg_debug", "dbg_", "debug_", "check_", "probe_", "verify_", "mech_battery",
                   "diag", "_test", "patch_shadows", ".canonical.")

_H1_LITERAL = re.compile(r'"_?H1"|_H1\.parquet|=\s*"H1"|\'_?H1\'')


def lake() -> dict[str, set[str]]:
    """{symbol: {timeframes present}} from the parquet store."""
    out: dict[str, set[str]] = defaultdict(set)
    if not UNIVERSE.exists():
        return {}
    for path in UNIVERSE.glob("*.parquet"):
        stem = path.stem
        if "_" not in stem:
            continue
        sym, _, tf = stem.rpartition("_")
        if sym:
            out[sym].add(tf.upper())
    return dict(out)


def _hunted(symbol: str) -> bool:
    """Is this instrument HUNTED for statistical hypotheses, or traded on events?

    PRINCIPAL'S ORDER, 2026-09-06: single-name equities are traded on news, financial reports and
    earnings reaction, and are never hunted for statistical hypotheses. So the chart ladder is
    required for the hypothesis lane and NOT for the event lane -- demanding M1 through D1 for
    three hundred share CFDs would report a gap that is a deliberate policy, and would spend the
    download budget filling it.

    Routed by ASSET CLASS from MetaTrader's own registry via `universe_policy`, never by a symbol
    list: a ticker is exactly what lies about a share CFD called `3M` or `A`.
    """
    try:
        sys.path.insert(0, str(DESK / "research"))
        from research import universe_policy
        return bool(universe_policy.may_hypothesise(symbol))
    except Exception:                                                   # noqa: BLE001
        # UNKNOWN IS NOT PERMISSION. Unable to route means unable to say the ladder is required,
        # and reporting a gap we cannot substantiate is how a board gets ignored.
        return False


def coverage() -> dict[str, Any]:
    have = lake()
    symbols = sorted(have)
    hunted = [s for s in symbols if _hunted(s)]
    event = [s for s in symbols if s not in set(hunted)]
    # ONLY THE HUNTED LANE IS GRADED. Counting charts across every share CFD would drown the one
    # number that matters: whether the instruments this desk actually researches can be
    # researched on more than one clock.
    by_tf = Counter(tf for s in hunted for tf in have[s])
    h1_only = [s for s in hunted if have[s] == {"H1"}]
    return {
        "symbols": len(symbols),
        "hunted_symbols": len(hunted),
        "event_lane_symbols": len(event),
        "event_lane_note": ("single-name equities are traded on news and are never hunted, so the "
                            "chart ladder is not required for them (principal, 2026-09-06)"),
        "series_hunted": sum(len(have[s]) for s in hunted),
        "by_timeframe": {tf: by_tf.get(tf, 0) for tf in EXPECTED_TIMEFRAMES},
        "absent_timeframes": [tf for tf in EXPECTED_TIMEFRAMES if not by_tf.get(tf)],
        "h1_only_symbols": len(h1_only),
        "multi_timeframe_symbols": sum(1 for s in hunted if len(have[s]) > 1),
        "examples_h1_only": h1_only[:8],
    }


def _tier(path: Path) -> str:
    rel = path.as_posix()
    name = path.name
    if any(h in name or h in rel for h in THROWAWAY_HINTS):
        return "THROWAWAY"
    if "/sources/" in rel:
        return "MINER_SOURCE"
    if "/mt5desk/" in rel or "/research/" in rel or "/libs/" in rel:
        return "PIPELINE"
    return "PIPELINE" if "/side_channels/" in rel else "OTHER"


def hardcoding() -> dict[str, Any]:
    """Graded H1 literals across the tree. Tests are excluded -- a test may name a chart."""
    hits: dict[str, list[str]] = defaultdict(list)
    for root in (DESK, REPO / "libs"):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel = path.as_posix()
            if "/tests/" in rel or "__pycache__" in rel:
                continue
            try:
                text = path.read_text("utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                if _H1_LITERAL.search(line):
                    hits[_tier(path)].append(f"{path.relative_to(REPO).as_posix()}:{i}")
    return {tier: {"count": len(v), "examples": v[:6]} for tier, v in sorted(hits.items())}


def downloader_agrees() -> tuple[bool, str]:
    """The downloader's timeframe list and this script's must not drift apart."""
    src = DESK / "scripts" / "download_all_symbols.py"
    try:
        text = src.read_text("utf-8")
    except OSError as exc:
        return False, f"cannot read {src.name}: {exc}"
    block = re.search(r"TIMEFRAME_DEPTH:\s*dict\[str, int\]\s*=\s*\{(.*?)\}", text, re.S)
    if not block:
        return False, "download_all_symbols.py no longer declares TIMEFRAME_DEPTH"
    declared = set(re.findall(r'"([A-Z0-9]+)":', block.group(1)))
    if declared != set(EXPECTED_TIMEFRAMES):
        return False, (f"downloader stores {sorted(declared)}; this check expects "
                       f"{sorted(EXPECTED_TIMEFRAMES)}")
    return True, f"downloader and this check agree on {len(declared)} timeframes"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="print only, write nothing")
    args = ap.parse_args(argv)

    cov = coverage()
    hard = hardcoding()
    agree, why = downloader_agrees()

    payload = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "coverage": cov,
        "hardcoding": hard,
        "downloader_agrees": agree,
        "downloader_note": why,
        "law": ("mechanisms live on charts: a desk that researches one timeframe cannot discover "
                "anything faster or slower than it, and produces no evidence of what it missed"),
    }
    if not args.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"timeframe coverage: {cov['series_hunted']} series over {cov['hunted_symbols']} "
          f"HUNTED symbol(s) ({cov['event_lane_symbols']} on the event lane, ladder not required)")
    print("  by timeframe: " + ", ".join(
        f"{tf}={cov['by_timeframe'][tf]}" for tf in EXPECTED_TIMEFRAMES))
    if cov["absent_timeframes"]:
        print(f"  ABSENT ENTIRELY: {', '.join(cov['absent_timeframes'])} -- no mechanism on these "
              f"charts can be discovered at all")
    print(f"  {cov['h1_only_symbols']} hunted symbol(s) hold H1 and nothing else; "
          f"{cov['multi_timeframe_symbols']} hold more than one chart")
    print(f"  downloader: {why}")
    print("  H1 literals by tier (tests excluded):")
    for tier in ("PIPELINE", "MINER_SOURCE", "OTHER", "THROWAWAY"):
        if tier in hard:
            print(f"    {tier:13} {hard[tier]['count']:4}   {hard[tier]['examples'][0] if hard[tier]['examples'] else ''}")
    # NON-ZERO IS A VERDICT, not a crash: a desk that can see one chart is a desk with a research
    # ceiling nobody chose, and a green exit here would say the opposite.
    return 1 if (cov["absent_timeframes"] or hard.get("MINER_SOURCE", {}).get("count")) else 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
