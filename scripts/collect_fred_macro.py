"""FRED macro archiver -- REFUSED ON TERMS; it now writes only its BLOCKED_ON_TERMS status.

FRED/ALFRED terms refuse every automated fetch (governance/fred-terms-ruling-2026-11-13.md).
This collector used to pull ~11.5 years of DGS10, T10Y2Y, VIXCLS, DTWEXBGS, WALCL, M2SL and DFII10
from the FRED API each run, record their vintages (libs.research.vintage) and overwrite
`data/fred_macro.json`, `data/fred_macro_long.json` and `web/fred_macro.json`.

Now `main` reads no key and builds no request. It writes `data/fred_macro_status.json`
(status BLOCKED_ON_TERMS, a reason citing the ruling, a missed_growth line) and exits 0, so the
hourly `fred_macro` leg stays honest rather than red. The archives and the vintage log already
on disk are left exactly as they are and stay readable by their consumers
(`mt5desk.macro_view`, `libs.portfolio.macro_state`, `libs.portfolio.leg_factors`,
`orthogonal_sweep`), whose own freshness rules decay a stale archive toward "no claim".

    python scripts/collect_fred_macro.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.data.fred_terms import FredTermsRefused, refusal  # noqa: E402

_ARCHIVE = Path("data/fred_macro.json")
_STATUS = Path("data/fred_macro_status.json")
#: The series the archive holds. Named so the status says what is no longer refreshed.
_SERIES = ("DGS10", "T10Y2Y", "VIXCLS", "DTWEXBGS", "WALCL", "M2SL", "DFII10")


def _fetch(key: str, sid: str) -> list[tuple[str, float]]:
    """REFUSED ON TERMS before any request is built. A caller that still asks fails loudly."""
    raise FredTermsRefused(sid)


def refuse() -> dict[str, Any]:
    """Write and return the BLOCKED_ON_TERMS status. The archives on disk are not touched."""
    doc: dict[str, Any] = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                           **refusal("collect_fred_macro"), "series": list(_SERIES),
                           "archive_kept": str(_ARCHIVE), "archive_present": _ARCHIVE.exists()}
    _STATUS.parent.mkdir(parents=True, exist_ok=True)
    _STATUS.write_text(json.dumps(doc, indent=1), "utf-8")
    print(f"fred-macro: {doc['status']} -- {doc['reason']}")
    return doc


def main() -> None:
    """FRED is refused on terms: no key is read, no request is built, exit 0."""
    refuse()


if __name__ == "__main__":
    main()
