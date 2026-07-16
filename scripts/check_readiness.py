"""Run deployment readiness checks and print the report. Exit 0 if ready, 1 otherwise.

Usage: python scripts/check_readiness.py [--db data/sor_demo.sqlite]
Runs fully offline (no MT5, no web server).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from migrations import MIGRATIONS

from app.readiness import readiness_check
from libs.store.connection import Database
from libs.store.migrations import run_migrations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sor_demo.sqlite")
    args = parser.parse_args()

    path = Path(args.db)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(path)
    try:
        run_migrations(db, MIGRATIONS)
        report = readiness_check(db)
    finally:
        db.close()

    for check in report.checks:
        flag = "PASS" if check.passed else ("WARN" if not check.critical else "FAIL")
        print(f"[{flag}] {check.name}: {check.detail}")
    print(f"\nREADY: {report.ready}")
    if report.warnings:
        print(f"warnings: {report.warnings}")
    return 0 if report.ready else 1


if __name__ == "__main__":
    sys.exit(main())
