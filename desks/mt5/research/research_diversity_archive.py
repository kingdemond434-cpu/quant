"""Populate the research-wide quality-diversity archive from canonical experiment evidence."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _path in (str(ROOT), str(DESK), str(DESK / "research")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from libs.moat import registry  # noqa: E402
from libs.research import diversity_archive as QD  # noqa: E402
from libs.research import experiment_graph  # noqa: E402

STATE = DESK / "data" / "research_diversity_archive.json"
REPORT = DESK / "reports" / "RESEARCH_DIVERSITY_ARCHIVE.json"


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def run(*, dry_run: bool = False, state: Path = STATE, report: Path = REPORT,
        rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if rows is None:
        conn = registry.connect()
        try:
            rows = experiment_graph.experiments(limit=100000, conn=conn)
        finally:
            conn.close()
    archive = QD.update(_read(state), rows)
    sources = {r["descriptor"]["information_source"] for r in archive["items"].values()}
    mechanisms = {r["descriptor"]["economic_mechanism"] for r in archive["items"].values()}
    report_doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                  "counts": archive["counts"], "source_breadth": len(sources),
                  "mechanism_breadth": len(mechanisms),
                  "niches": list(archive["niches"].values()),
                  "coverage_challenge": {
                      "anomaly_first_required": True,
                      "cross_factory_ablation_required": True,
                      "empty_dimension_values": [name for name in QD.DIMENSIONS if not {
                          r["descriptor"][name] for r in archive["items"].values()
                          if r["descriptor"][name] != "UNCLASSIFIED"}],
                      "next_action": "route underrepresented descriptors to the existing frontier"},
                  "authority": "research preservation only; no trading or certificate authority"}
    if not dry_run:
        archive["at"] = report_doc["at"]
        _atomic(state, archive)
        _atomic(report, report_doc)
    return report_doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    print(f"research diversity archive: {doc['counts']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
