#!/usr/bin/env python3
"""THE ONION LANE: PERMANENTLY OFF (auditor ruling, 2026-11-03).

No onion or Tor egress, ever. The lane that once fetched an allowlist of public onion mirrors
through a local Tor SOCKS port is withdrawn: this module opens no socket, reads no environment
variable and no ruling file, and has no override of any kind. `REFUSED` below is a hard-coded
module constant; the only way to change it is a reviewed code change, which the ruling forbids.

Every call to `run` returns a report whose gate is `REFUSED:AUDITOR_RULING_2026-11-03` and
measures nothing. `libs.data.terms_fence.SOURCE_POLICY["onion_mirrors"]` states the ruling and
carries the missed-growth line; every .onion host still resolves to that row, so no onion page is
ever input. Tor Metrics' public CLEARNET statistics (`research/tor_metrics.py`) are a separate,
unaffected source and never import this module.

    python desks/mt5/research/onion_mirrors.py --once
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any, Final

#: Hard-coded. No environment variable, file or argument can change it.
REFUSED: Final[bool] = True
RULING: Final[str] = ("auditor 2026-11-03: no onion or Tor egress, ever; the onion lane is "
                      "permanently off")
GATE: Final[str] = "REFUSED:AUDITOR_RULING_2026-11-03"


def run(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Refuse. Accepts and ignores any argument so no caller can pass its way to a fetch."""
    return {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "gate": GATE, "refused": REFUSED, "ruling": RULING,
            "n_entries": 0, "n_refused": 0, "n_measured": 0, "rows": []}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.parse_args(argv)
    print(json.dumps({k: v for k, v in run().items() if k != "rows"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
