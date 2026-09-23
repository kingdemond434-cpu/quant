"""Retire certificates whose symbol this desk can never trade (L1.49).

A certificate is EARNED EVIDENCE and the authority ratchet exists so evidence never silently
falls. But a certificate on a symbol absent from the universe registry -- or with no
`<sym>_H1.parquet` to replay -- is not evidence of an edge this desk can own: it can never enrol
a forward clock, never be allocated, never be cashed. Measured 2026-09-02T13:07:21Z, ONE gauntlet
pass minted eight such rows (six `AFG`, two `AFL`) and every artifact that counts certificates
counted them, so the desk's certificate count was inflated by things it can never trade.

`external_gauntlet.symbol_is_tradeable` now refuses these at gate 0, so no NEW row can be minted.
This retires the ones minted before that limb existed, and stands as a recurring check so the
class cannot come back silently.

NOT A DELETION. The rows move to `retired_certificates` with the reason that disqualified them,
which is exactly the "explicit recorded revocation" the authority ratchet accepts as grounds to
lower a floor (`check_authority_ratchet.REVOCATION_KEYS`). Deleting them instead would read to the
ratchet as evidence vanishing, which is the alarm it exists to raise.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.reference_freshness import require_live_reference  # noqa: E402

DESK = ROOT / "desks" / "mt5"
AUTHORITY = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
BARS = DESK / "data" / "universe"

#: STUMP FLOOR. The same number `scripts/purge_untradeable_certs.py` carries: a registry this
#: short is a collector outage, and retiring the book against it is the incident LAWS 7 names.
UNIVERSE_FLOOR = 50


def _reason(sym: str, meta: dict) -> str:
    """Why this symbol can never be cashed, or "" if it can."""
    if not sym:
        return "certificate carries no symbol"
    if sym not in meta:
        return f"symbol {sym!r} is absent from the universe registry"
    if not (BARS / f"{sym}_H1.parquet").exists():
        return f"symbol {sym!r} has no {sym}_H1.parquet; no forward clock can replay it"
    row = meta.get(sym)
    if isinstance(row, dict) and row.get("tradeable") is False:
        return (f"symbol {sym!r} is CLOSE_ONLY on this account "
                f"(trade_mode {row.get('trade_mode')}); no new position can be opened")
    return ""


def retire(path: Path, meta: dict, stamp: str) -> tuple[int, list[str]]:
    """Move every uncashable survivor in `path` to `retired_certificates`. Returns (n, names)."""
    if not path.exists():
        return 0, []
    doc = json.loads(path.read_text("utf-8"))
    survivors = doc.get("survivors") or {}
    moved: dict[str, dict] = {}
    for key, row in list(survivors.items()):
        why = _reason(str((row or {}).get("sym") or ""), meta)
        if why:
            entry = dict(row or {})
            entry["retired_at"] = stamp
            entry["retired_reason"] = why
            moved[key] = entry
            survivors.pop(key, None)
    if not moved:
        return 0, []
    retired = doc.get("retired_certificates") or {}
    retired.update(moved)
    doc["retired_certificates"] = retired
    doc["survivors"] = survivors
    doc["n"] = len(survivors)
    doc["revoked_at"] = stamp
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1), "utf-8")
    tmp.replace(path)
    return len(moved), sorted(moved)


def main() -> int:
    # NOTHING IS RETIRED ON AN ABSENCE (LAWS 7). `if not meta` caught the empty registry but not
    # the two cases that kill just as many certificates: a TRUNCATED registry (23 symbols passes
    # `not meta` and retires the whole book -- the floor `purge_untradeable_certs.py:43` already
    # carries) and a STALE one (the collector died and the symbols it has not re-listed since look
    # absent). One call answers all three and records the refusal where an operator sees it.
    state = require_live_reference(
        UNIVERSE, actor="retire_uncashable_certs.main",
        action="retire certificates whose symbol the registry does not carry",
        min_rows=UNIVERSE_FLOOR)
    if not state.live:
        print(f"registry UNMEASURED ({state.verdict}) -- refusing to judge any certificate "
              f"uncashable: {state.why}")
        return 1
    meta = json.loads(UNIVERSE.read_text("utf-8"))
    stamp = datetime.now(UTC).isoformat()
    total = 0
    for path in (AUTHORITY, CANON):
        n, names = retire(path, meta, stamp)
        total += n
        if n:
            print(f"{path.name}: retired {n} uncashable certificate(s)")
            for name in names:
                print(f"    {name}")
        else:
            print(f"{path.name}: no uncashable certificates")
    if total:
        print(f"retired {total} row(s) as an explicit revocation; the ratchet floor may now fall")
    return 0


if __name__ == "__main__":
    sys.exit(main())
