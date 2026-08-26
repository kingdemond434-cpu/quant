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

WHAT THIS DOES, and what it deliberately does not. It merges the sources, deduplicates by
executable identity, and carries `search_trials` through so the canonical `deflated_sharpe`
deflates against the true multiplicity. It applies NO threshold of its own -- L1.60: discovery →
backtest → the ten gates → certificate → forward → live, and no screen may insert a gate in
either direction. Everything discovered reaches the gauntlet; the gauntlet decides.
"""
from __future__ import annotations

import json
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
    merged: dict[str, dict] = {}
    per_source: dict[str, int] = {}
    max_trials = 0

    for name, key in SOURCES:
        doc = _read(HYP / name)
        if doc is None:
            per_source[name] = -1          # ABSENT is distinct from empty; -1 says so
            continue
        rows = doc if isinstance(doc, list) else (doc.get(key) if key else None)
        if not isinstance(rows, list):
            per_source[name] = 0
            continue
        try:
            max_trials = max(max_trials, int(doc.get("total_trials") or 0)
                             if isinstance(doc, dict) else 0)
        except (TypeError, ValueError):
            pass
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

    # THE SEARCH'S OWN WIDTH TRAVELS WITH EVERY ROW. A candidate selected as best-of-N has already
    # survived a selection the gauntlet cannot see; if that N does not reach `deflated_sharpe`,
    # the gate credits it with significance the search already spent.
    for row in merged.values():
        declared = int(row.get("search_trials") or 0)
        if max_trials and declared < max_trials and row.get("producer") != SOURCES[0][0]:
            row["search_trials"] = max_trials

    rows_out = list(merged.values())
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(rows_out, indent=1, default=str), "utf-8")
    (HYP / "merge_report.json").write_text(json.dumps({
        "merged_at": now.isoformat(timespec="seconds"),
        "per_source": per_source, "total": len(rows_out),
        "declared_search_trials": max_trials,
        "families": {f: sum(1 for r in rows_out if r.get("family") == f)
                     for f in sorted({str(r.get("family")) for r in rows_out})},
        "note": ("no threshold applied here (L1.60) -- every discovered candidate reaches the "
                 "ten-gate gauntlet, which is the only arbiter"),
    }, indent=1), "utf-8")

    print(f"merged hypotheses: {len(rows_out)} unique candidate(s) -> {TARGET.name}")
    for name, n in per_source.items():
        state = "ABSENT" if n < 0 else f"{n} new"
        print(f"   {name:34} {state}")
    fam = {}
    for r in rows_out:
        fam[str(r.get("family"))] = fam.get(str(r.get("family")), 0) + 1
    print(f"   families going to the gauntlet: {fam}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
