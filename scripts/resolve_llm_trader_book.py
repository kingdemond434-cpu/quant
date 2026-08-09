#!/usr/bin/env python3
"""GRADE THE llm_trader BOOK -- every CALL and every DECLINE, against its own stated horizon.

WHY THIS EXISTS (R0123, external critique GPT 2026-07-31). The sleeve's brief promises the model
that "a PASS is also scored ... marked against the same horizon as a real call", and the code kept
that promise for nobody: `record_call` logged a forecast only for `action == "CALL"`, and
`resolve_paper_book.py:605` skips PASS rows outright. Measured 2026-08-05: NINE book rows, nine of
them PASS, zero scoreable forecasts ever logged. A model graded only on the trades it chooses to be
graded on has a dominant strategy, and it had already found it.

THE HALF THAT MAKES LOGGING SAFE, and it is why this ships in the same commit as the logging.
`check_calibration.py` FAILS (exit 2) on any forecast still unresolved past its `resolve_by`. So
logging declines without a grader would not merely be incomplete -- it would convert a green
survival fence into a permanently red one within eight hours, and a fence that cries wolf is a
fence somebody disables. Logging and grading are one change or they are a regression.

WHAT "RIGHT" MEANS FOR A DECLINE. The row carries the model's own `direction` and `probability` --
what it WOULD have done. Grading that against the realised move over the same window answers the
only question worth asking about a filter, and the good answer is a coin flip: a 50/50 trade loses
money once fees are paid, so declining it was correct. See libs/research/decline_value.py, which
holds the arithmetic and the verdict bands; this script is the IO around it.

RETROACTIVE REGISTRATION IS EXPLICIT, NEVER QUIET. Rows written before the logging fix carry no
forecast, so this re-registers them from the row's OWN recorded `at`, `resolve_by`, `direction` and
`probability` -- it copies a pre-registration, it never authors one. Those entries get the distinct
kind `discretionary_pass_backfill` so any later reader can exclude them, because a claim whose
pre-registration is evidenced only by an untracked file is weaker evidence than one this desk
watched being made, and the difference must stay visible rather than being averaged away.

    python scripts/resolve_llm_trader_book.py [--dry-run] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.crypto_source import fetch_price_at  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.decline_value import (  # noqa: E402
    filter_verdict,
    make_decline,
    pass_rate,
    scoreable,
)
from libs.self_improvement import forecast_calibration as fc  # noqa: E402

_BOOK = _ROOT / "data/llm_trader_book.jsonl"
_OUT = _ROOT / "reports/llm_trader_decline_value.json"


def _rows() -> list[dict[str, Any]]:
    """Book rows, malformed ones COUNTED rather than silently dropped."""
    if not _BOOK.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in _BOOK.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            out.append({"_malformed": True})
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _key(row: dict[str, Any]) -> str:
    """The forecast key, matching record_call's scheme so a backfill cannot mint a duplicate."""
    return str(row.get("forecast_key") or f"llm_trader:{row.get('at')}")


def _due(row: dict[str, Any], now: datetime) -> bool:
    try:
        rb = datetime.fromisoformat(str(row.get("resolve_by")))
    except (TypeError, ValueError):
        return False
    return (rb if rb.tzinfo else rb.replace(tzinfo=UTC)) <= now


def run(*, write: bool = True, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows = _rows()
    malformed = sum(1 for r in rows if r.get("_malformed"))
    rows = [r for r in rows if not r.get("_malformed")]

    declines, calls_graded = [], []
    skipped: list[dict[str, str]] = []
    registered = 0

    for row in rows:
        key = _key(row)
        is_pass = row.get("action") == "PASS"
        ok, why = scoreable(row)
        if not ok:
            skipped.append({"key": key, "why": f"ungradeable: {why}"})
            continue
        if not _due(row, now):
            skipped.append({"key": key, "why": "horizon not yet elapsed"})
            continue
        existing = fc.get_forecast(key)
        if existing and existing.get("resolved"):
            continue                                        # already scored; resolve() is a no-op

        entry = fetch_price_at(str(row["symbol"]), int(
            datetime.fromisoformat(str(row["at"])).timestamp() * 1000))
        exit_px = fetch_price_at(str(row["symbol"]), int(
            datetime.fromisoformat(str(row["resolve_by"])).timestamp() * 1000))
        if entry is None or exit_px is None:
            # REFUSES rather than substituting a nearby print. A guessed outcome corrupts the
            # measurement the grading exists to produce.
            skipped.append({"key": key, "why": f"no venue price for {row['symbol']} at "
                                               f"{'entry' if entry is None else 'exit'}"})
            continue

        d = make_decline(row, entry, exit_px, key=key)
        (declines if is_pass else calls_graded).append(d)

        if write:
            if not existing:
                # Retroactive registration, copied from the row -- never authored here.
                kind = "discretionary_pass_backfill" if is_pass else "discretionary"
                fc.log_forecast(key, d.probability, kind, resolve_by=str(row["resolve_by"]),
                                claim=(f"{'DECLINED ' if is_pass else ''}{d.direction} {d.symbol} "
                                       f"over {row.get('horizon_hours', 8)}h @ {row['at']}"))
                registered += 1
            fc.resolve(key, d.would_have_been_right)

    # THE REFUSAL PATH (L1.28a): an absent book and a book of perfect declines are different
    # facts, and a grader that returns the same shape for both reports OK on absent input. NO-DATA
    # is reserved for "the sleeve has produced nothing to grade"; UNMEASURED means rows exist but
    # none of them could be graded -- ungradeable, immature, or the venue had no price. Neither is
    # OK, and neither is silently absorbed into a zero.
    verdict = filter_verdict(declines)
    if not rows:
        status = "NO-DATA"
    elif not declines and not calls_graded:
        status = "UNMEASURED"
    else:
        status = verdict["verdict"]

    report = {
        "generated": now.isoformat(),
        "row": "R0123",
        "status": status,
        "book": str(_BOOK.relative_to(_ROOT)),
        "mode": "WRITE" if write else "DRY-RUN",
        "malformed_rows": malformed,
        "participation": pass_rate(rows),
        "declines": verdict,
        "calls_graded": len(calls_graded),
        "retroactively_registered": registered,
        "skipped": skipped[:20],
        "n_skipped": len(skipped),
        "graded_detail": [
            {"key": d.key, "symbol": d.symbol, "direction": d.direction, "p": d.probability,
             "entry": d.entry_px, "exit": d.exit_px, "right": d.would_have_been_right,
             "forgone_bps": d.forgone_bps, "pass_reason": d.pass_reason}
            for d in declines],
    }
    return report


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="grade but never touch the store")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = run(write=not args.dry_run)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        part, dec = rep["participation"], rep["declines"]
        print(f"llm_trader book ({rep['mode']}): {rep['status']} -- {part['flag']}: {part['why']}")
        print(f"  declines graded: {dec['n_declines']} -> {dec['verdict']}")
        print(f"  {dec['why']}")
        if rep["calls_graded"]:
            print(f"  calls graded: {rep['calls_graded']}")
        if rep["retroactively_registered"]:
            print(f"  retroactively registered: {rep['retroactively_registered']} "
                  f"(kind *_backfill, excluded from the sizing pool)")
        if rep["n_skipped"]:
            print(f"  skipped: {rep['n_skipped']}")
            for s in rep["skipped"][:5]:
                print(f"    {s['key'][:44]:<46} {s['why']}")
    # A GRADER REPORTS; it is not a fence and must not fail a build. check_calibration is the
    # fence, and it fires on exactly what this script exists to prevent.
    return 0


if __name__ == "__main__":
    sys.exit(main())
