"""Compact the FX Blue raw harvest into the artifact a reader actually needs.

The raw records are ~14MB per 350-account wave, almost all of it repeated chart scaffolding.
Committing every wave rots the repo by growth (the desk has paid for that once already, at
487KB -> 637MB). The RAW waves stay on the box and are re-harvestable in ~40 minutes from a
public, keyless, §13-clean route; what is committed is this gzipped digest: one slim row per account
carrying the mechanism structure -- the hour clock, the instrument set, direction and duration
splits -- which is everything the summariser and any downstream study reads.
"""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "data" / "intelligence" / "fxblue"
OUT = SRC / "mechanism_digest.jsonl.gz"

KEEP = ("ch_hourtrades", "ch_hourprofit", "ch_symboltrades", "ch_symbolprofit",
        "ch_directionprofit", "ch_dowprofit", "ch_tradedurationprofit")


def main() -> int:
    seen: set[str] = set()
    n = 0
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        for path in sorted(SRC.glob("track_records*.jsonl")):
            for ln in path.read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                r = json.loads(ln)
                user = str(r.get("user", ""))
                if user in seen:
                    continue
                seen.add(user)
                charts = r.get("charts") or {}
                mineable = any(
                    v for c in charts.values() for _, v in (c.get("rows") or [])
                ) or bool((r.get("overview") or {}).get("balance"))
                slim: dict[str, object] = {
                    "user": user,
                    "status": r.get("status"),
                    "mineable": mineable,
                    "overview": r.get("overview") or {},
                    "harvested_utc": r.get("harvested_utc"),
                }
                for c in KEEP:
                    rows = (charts.get(c) or {}).get("rows")
                    if rows:
                        slim[c] = [[str(a), b] for a, b in rows]
                fh.write(json.dumps(slim, ensure_ascii=False) + "\n")
                n += 1
    by_status: dict[str, int] = defaultdict(int)
    with gzip.open(OUT, "rt", encoding="utf-8") as rh:
        digest_lines = rh.read().splitlines()
    for ln in digest_lines:
        by_status[str(json.loads(ln)["status"])] += 1
    print(f"{n} unique accounts -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    print(dict(sorted(by_status.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
