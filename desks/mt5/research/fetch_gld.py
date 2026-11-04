"""GLD / SLV / IAU holdings -- a manual probe of the issuer doors. NOT a lane and NOT a store.

This script used to fetch a GLD workbook to a retired laptop path (`C:\\Users\\...\\data\\lake`)
and ran on no clock. It is replaced by three doors of the `etf_issuers` pack in
`research/country_packs.py` (`etf_gld_holdings`, `etf_slv_holdings`, `etf_iau_holdings`), which
the world dataset hunter fetches every hour (leg `world_dataset_hunt`), stamps at publication,
lands in its PIT store (`data/world_datasets/obs/ETF_ISSUER/`) and reports in
`reports/COUNTRY_PACK_LIVENESS.json`.

Run by hand, it makes ONE attempt per door through the hunter's own polite client (robots,
holds, terms fence, the desk's honest agent) and prints what each door parsed. It writes
nothing: the store belongs to the hunter.

    python desks/mt5/research/fetch_gld.py [etf_gld_holdings ...]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parents[1]), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DOORS = ("etf_gld_holdings", "etf_slv_holdings", "etf_iau_holdings")


def main(argv: list[str] | None = None) -> int:
    from research import country_packs as cp
    from research import world_dataset_hunter as W

    now = datetime.now(UTC)
    client = W.Client(None, time.monotonic() + 120.0)
    out: dict[str, object] = {}
    for did in (argv if argv else list(DOORS)):
        door = cp.BY_ID[did]
        held = cp.gate(door)
        if held:
            out[did] = {"state": held[0], "why": held[1]}
            continue
        try:
            series = cp.fetch_door(door, lambda r: client.get(r.url, headers=r.headers or None),
                                   now, first=True)
        except (W.FetchError, cp.LoginRequired) as exc:
            out[did] = {"state": "FAILED", "why": str(exc)[:200]}
            continue
        out[did] = {"state": "PARSED" if series else "EMPTY",
                    "series": {s["code"]: {"points": len(s["points"]),
                                           "last": s["points"][-1] if s["points"] else None}
                               for s in series}}
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
