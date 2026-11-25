#!/usr/bin/env python3
"""Run the backup watch once (libs/ops/backup_watch.py); MT5-Guardian calls it every 15 min.

    python scripts/output_watch.py --once     # writes desks/mt5/reports/BACKUP_WATCH.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import backup_watch as bw  # noqa: E402


def _page(msg: str) -> None:
    try:
        from libs.ops import principal_page

        principal_page.page(msg, marker="BACKUP WATCH:", path=ROOT / "data" / "PRINCIPAL_ACTION.md")
    except Exception as exc:  # a lost page is logged, never a crash of the guardian leg
        print(f"page failed: {type(exc).__name__}: {exc}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", required=True)
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    doc = bw.run_once(Path(a.root), page=_page)
    print(json.dumps({k: doc.get(k) for k in ("at", "verdict", "flags", "repair",
                                              "last_success_at")}, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
