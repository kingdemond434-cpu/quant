"""MERGE EVERY HYPOTHESIS SOURCE INTO THE ONE FILE THE GAUNTLET READS.

THE GAP THIS CLOSES (found 2026-08-26 while answering "will new certificates form in an hour?").
`external_gauntlet` reads exactly one input: `data/hypotheses/external_survivors.json`. Meanwhile
the generic search wrote `edge_search_results.json` and the orthogonal sweep wrote
`orthogonal_candidates.json`, and NOTHING read either. Both ran, both produced candidates, and
both were stranded one file away from the only door that grants certificates.

That is the same defect as the eight-gate barrier with no producer, pointed the other way: there
the gate had no input, here the producers had no consumer. A pipeline stage whose output nothing
consumes is not a stage, it is a log line -- and it would have kept the book at 95% one family
indefinitely while every dashboard showed the searcher running nightly.

WHAT THIS DOES, and what it deliberately does not. It merges the sources and deduplicates by
executable identity. It applies NO threshold of its own AND attaches no deflation input -- L1.60:
discovery → backtest → the ten gates AS DEFINED → certificate → forward → live. Everything
discovered reaches the gauntlet; the gauntlet decides, using its own sealed constants.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
HYP = BASE / "data" / "hypotheses"
TARGET = HYP / "external_survivors.json"

#: Every producer, and how to reach the rows inside it. Adding a producer means adding a line
#: here -- and the job manifest will report the target STALE if this stops running, so a new
#: source cannot go quietly unconsumed the way these two did.
SOURCES = (
    ("external_backtest_results.json", None),
    ("edge_search_results.json", "hypotheses"),
    ("orthogonal_candidates.json", "hypotheses"),
)


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _pipeline_started_at() -> datetime | None:
    """Return this orchestrated run's lower freshness bound, if supplied.

    Manual/recovery invocations remain backwards compatible and may merge the durable corpus.
    The hourly orchestrator always supplies this value, making stale producer output ineligible.
    """
    raw = os.environ.get("QUANT_PIPELINE_STARTED_AT", "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"invalid QUANT_PIPELINE_STARTED_AT={raw!r}") from None
    return parsed.astimezone(UTC)


def _fresh_for_run(path: Path, started_at: datetime | None) -> bool:
    if started_at is None:
        return True
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return False
    # Filesystems and scp can round mtimes to whole seconds.
    return modified.timestamp() >= started_at.timestamp() - 2.0


def _identity(row: dict) -> str:
    """Dedup by what would actually be EXECUTED, not by label.

    Two rows describing the same symbol, family and parameters are one candidate however they are
    titled or whichever producer emitted them -- and letting a duplicate through twice would
    inflate the trial count and the apparent breadth at the same time.
    """
    params = row.get("params") or {}
    return json.dumps({
        "symbol": str(row.get("symbol") or row.get("sym") or ""),
        "family": str(row.get("family") or ""),
        "params": {k: params[k] for k in sorted(params)},
    }, sort_keys=True, default=str)


def main() -> int:
    now = datetime.now(tz=UTC)
    started_at = _pipeline_started_at()
    merged: dict[str, dict] = {}
    per_source: dict[str, int] = {}
    source_state: dict[str, str] = {}

    for name, key in SOURCES:
        source_path = HYP / name
        doc = _read(source_path)
        if doc is None:
            per_source[name] = -1          # ABSENT is distinct from empty; -1 says so
            source_state[name] = "ABSENT"
            continue
        if not _fresh_for_run(source_path, started_at):
            # A previous run's output remains immutable provenance, but it is not a discovery
            # from THIS run and must not be represented or retested as one.
            per_source[name] = -2
            source_state[name] = "STALE_SKIPPED"
            continue
        rows = doc if isinstance(doc, list) else (doc.get(key) if key else None)
        if not isinstance(rows, list):
            per_source[name] = 0
            source_state[name] = "MALFORMED_OR_EMPTY"
            continue
        kept = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not (row.get("symbol") or row.get("sym")):
                continue
            ident = _identity(row)
            if ident in merged:
                continue
            enriched = dict(row)
            enriched.setdefault("family", "session_range_breakout")
            enriched["producer"] = name
            merged[ident] = enriched
            kept += 1
        per_source[name] = kept
        source_state[name] = "FRESH"

    # NOTHING ABOUT SEARCH WIDTH TRAVELS WITH A ROW. An earlier revision copied the search's
    # trial count onto every hypothesis so `deflated_sharpe` would deflate against it -- making
    # the ten gates harsher than their sealed definition. That is an unsanctioned bar, merely
    # hidden inside the gate instead of sitting in front of it. Trial counts stay in the search's
    # own report, for audit, and reach no gate.

    rows_out = list(merged.values())
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    # NEVER SHRINK THE DOCKET TO NOTHING. The freshness contract makes every source STALE_SKIPPED
    # on any run where producers have not written yet, and this merge then emitted an EMPTY file
    # -- which the pipeline shipped, and on which the gauntlet wiped the authority file to n=0.
    # An hourly cycle where "the searcher was slow this hour" cascades into "all certificates
    # revoked" is not a freshness contract, it is a self-destruct. If this run gathered nothing
    # fresh, the existing docket STANDS: yesterday's candidates are still candidates.
    if not rows_out:
        prior = _read(TARGET)
        if isinstance(prior, list) and prior:
            print(f"merge: 0 fresh rows this run -- PRESERVING the existing docket of "
                  f"{len(prior)} candidate(s) rather than shipping an empty file downstream.")
            return 0
    TARGET.write_text(json.dumps(rows_out, indent=1, default=str), "utf-8")
    (HYP / "merge_report.json").write_text(json.dumps({
        "merged_at": now.isoformat(timespec="seconds"),
        "pipeline_started_at": started_at.isoformat(timespec="seconds") if started_at else None,
        "per_source": per_source, "source_state": source_state, "total": len(rows_out),
        "families": {f: sum(1 for r in rows_out if r.get("family") == f)
                     for f in sorted({str(r.get("family")) for r in rows_out})},
        "note": ("no threshold applied here (L1.60) -- every discovered candidate reaches the "
                 "ten-gate gauntlet, which is the only arbiter"),
    }, indent=1), "utf-8")

    print(f"merged hypotheses: {len(rows_out)} unique candidate(s) -> {TARGET.name}")
    for name, n in per_source.items():
        state = source_state[name] if n < 0 else f"{n} new ({source_state[name]})"
        print(f"   {name:34} {state}")
    fam = {}
    for r in rows_out:
        fam[str(r.get("family"))] = fam.get(str(r.get("family")), 0) + 1
    print(f"   families going to the gauntlet: {fam}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
