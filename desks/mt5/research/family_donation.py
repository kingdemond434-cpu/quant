"""family_donation: donate mechanically converted cells ONE FILE PER TRIAL FAMILY.

The shared door of every converting producer (`compile_proposals`, `axis_ingest_all`,
`axis_proposer`), built on `proposer_common.donate`. It lives in its own module, not in
proposer_common, because proposer_common sits in the box entry points' import closure and its
knobs are judged by replay-shadow; nothing here touches a money path, so it stays outside it.
"""
from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from research import proposer_common as pc
except ImportError:                                               # pragma: no cover - import ctx
    import proposer_common as pc  # type: ignore[no-redef]


#: Where `donate_per_family` remembers the cells it has already charged, one JSONL per source.
#: NOT under `data/intelligence/` (the compiler reads every file there as evidence) and not under
#: `data/hypotheses/` (the conversion audit reads idea-named files there as sources). Box state,
#: gitignored. Losing it re-charges every cell once more -- an over-count, never an under-count.
DONATION_LEDGERS = pc._DESK / "data" / "donation_ledgers"


def _expanded_count(cells: list[dict]) -> int:
    """The cells the compiler will mint from these rows AFTER its own chart x session expansion.
    Charging the pre-expansion count would under-count the trials the gauntlet actually runs."""
    try:
        from research.miner_candidate_compiler import expand_axes
    except Exception:
        try:
            from miner_candidate_compiler import expand_axes  # type: ignore[no-redef]
        except Exception:
            return len(cells)
    try:
        return max(len(cells), len(expand_axes([dict(c) for c in cells])))
    except Exception:
        return len(cells)


def donate_per_family(source: str, cells: list[dict], *, ledger: Path | None = None,
                      dry_run: bool = False) -> dict[str, Any]:
    """Donate mechanically converted cells ONE FILE PER TRIAL FAMILY, each charged its own trials.

    The shape every converting producer shares (`compile_proposals`, `axis_ingest_all`,
    `axis_proposer`): rows carry `symbol`, a registered `family` and exact `params`, so
    `miner_candidate_compiler` admits them as EXACT_RECIPE. `tests_run` on each contract file is
    the family's post-expansion count, so deflation charges the multiplicity the gauntlet really
    pays. A cell already in `ledger` was charged when it was first donated and is not re-charged;
    a row with no symbol, family or params is counted as `incomplete`, never guessed.
    """
    held: set[str] = set()
    if ledger is not None:
        try:
            with ledger.open(encoding="utf-8") as fh:
                for line in fh:
                    with contextlib.suppress(ValueError, AttributeError):
                        held.add(str(json.loads(line).get("cell_id") or ""))
        except OSError:
            pass
    by_family: dict[str, list[dict]] = {}
    already = incomplete = 0
    seen: set[str] = set()
    for c in cells:
        sym, fam, params = str(c.get("symbol") or ""), str(c.get("family") or ""), c.get("params")
        if not sym or not fam or not isinstance(params, dict):
            incomplete += 1
            continue
        cid = pc.identity(sym, fam, params)
        if cid in held or cid in seen:
            already += 1
            continue
        seen.add(cid)
        by_family.setdefault(fam, []).append({**c, "trial_family": fam, "cell_id": cid})
    out: dict[str, Any] = {"source": source, "offered": len(cells), "already_charged": already,
                           "incomplete": incomplete, "tests_run_by_family": {},
                           "donated_by_family": {}, "refused_wrong_lane": {}, "files": [],
                           "dry_run": dry_run}
    rows: list[dict[str, Any]] = []
    at = datetime.now(tz=UTC).isoformat(timespec="seconds")
    for fam, fam_cells in sorted(by_family.items()):
        tests = _expanded_count(fam_cells)
        out["tests_run_by_family"][fam] = tests
        if dry_run:
            out["donated_by_family"][fam] = len(fam_cells)
            continue
        path = pc.donate(source, fam_cells, tests, suffix=fam)
        counts = pc.donation_counts()
        out["donated_by_family"][fam] = int(counts.get("donated") or 0)
        out["refused_wrong_lane"][fam] = int(counts.get("refused_wrong_lane") or 0)
        if path is not None:
            out["files"].append(str(path))
        # Charged whether or not the door admitted every row: the trials were spent the moment
        # the cells were enumerated, and a re-offer next pass must not be charged twice.
        rows.extend({"cell_id": c["cell_id"], "family": fam, "symbol": c["symbol"],
                     "params": c["params"], "charged_at": at, "tests_charged_with_family": tests}
                    for c in fam_cells)
    out["tests_run_total"] = sum(out["tests_run_by_family"].values())
    out["donated_total"] = sum(out["donated_by_family"].values())
    if rows and ledger is not None:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
    return out
