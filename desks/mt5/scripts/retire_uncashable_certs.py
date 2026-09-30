"""Retire certificates whose symbol the VENUE will not let this desk trade (L1.49).

A certificate is EARNED EVIDENCE and the authority ratchet exists so evidence never silently
falls. But a certificate on a symbol the broker refuses to open a new position in can never enrol
a forward clock, never be allocated, never be cashed. Measured 2026-09-02T13:07:21Z, ONE gauntlet
pass minted eight such rows (six `AFG`, two `AFL`) and every artifact that counts certificates
counted them, so the desk's certificate count was inflated by things it can never trade.

`external_gauntlet.symbol_is_tradeable` refuses these at gate 0, so no NEW row can be minted.
This retires the ones minted before that limb existed, and stands as a recurring check so the
class cannot come back silently.

THIS FILE'S OWN PREDICATE WAS FALSE, AND IT CUT THE CERTIFICATE STORE FROM 58 TO 28
(measured 2026-09-24). `_reason` was a SECOND, PRIVATE copy of the gate-0 eligibility test --
registry membership, then `(BARS / f"{sym}_H1.parquet").exists()`. The sealed writer had already
been corrected away from exactly that rule, in words this file did not inherit:

    Correction: eligibility for a NEW test is not proof for revoking an EXISTING result.
    A missing host cache must not erase every certificate on the Windows box.
                                            -- external_gauntlet.certificate_retirement_reason

and `test_certificates_cannot_be_lost_to_an_outage` pins the sealed version with
`assert "symbol_is_tradeable(" not in fn, "a missing chart must never retire a certificate"`.
The pin protected ONE pen. This one kept the old rule and fired it on 2026-09-20/21 against nine
FX majors and crosses whose `<sym>_H1.parquet` files are 1.0-1.4 MB and present in the registry:
AUDCAD, AUDCHF, AUDNZD, AUDUSD, EURCHF, EURGBP, EURUSD, NZDCAD, USDCAD, USDCHF. The parquet
directory is rewritten every hour by the collector; `.exists()` is False for the instant of a
replace, and a retirement taken in that instant is PERMANENT while the outage is a second long.
AUDCHF was retired this way on the 21st and `certificate_truth` restored it on the 23rd -- the
round trip is the proof the predicate was false, and 24 more rows never made it back because a
standing family ban holds them, not the parquet.

SO THERE IS ONE JUDGE NOW. The question "does this symbol disqualify an EXISTING certificate"
has exactly one owner, `external_gauntlet.certificate_retirement_reason`, and it is CALLED rather
than re-spelled. Missing bars block execution and testing; they do not invalidate statistical
evidence that was measured when the bars were there. If that judge cannot be imported this script
retires NOTHING and says so: the absence of the predicate is never grounds for a revocation
(L1.28a).

NOT A DELETION. The rows move to `retired_certificates` with the reason that disqualified them,
which is exactly the "explicit recorded revocation" the authority ratchet accepts as grounds to
lower a floor (`check_authority_ratchet.REVOCATION_KEYS`). Deleting them instead would read to the
ratchet as evidence vanishing, which is the alarm it exists to raise.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.reference_freshness import require_live_reference  # noqa: E402

DESK = ROOT / "desks" / "mt5"
AUTHORITY = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
#: DELIBERATELY ABSENT: a path to the bar cache. This file used to hold one and test
#: `<sym>_H1.parquet` for existence; see the module docstring for what that cost.

#: STUMP FLOOR. The same number `scripts/purge_untradeable_certs.py` carries: a registry this
#: short is a collector outage, and retiring the book against it is the incident LAWS 7 names.
UNIVERSE_FLOOR = 50


#: The sealed writer's `certificate_retirement_reason`: (symbol, registry) -> reason or None.
VenueJudge = Callable[[str, dict[str, Any]], "str | None"]


def _venue_judge() -> VenueJudge | None:
    """The sealed writer's `certificate_retirement_reason`, or None when it cannot be reached.

    Imported, never re-implemented -- see the module docstring. None is UNMEASURED and the caller
    must retire nothing on it, exactly as `certificate_truth._tradeable_now` does.
    """
    for path in (DESK / "scripts", DESK / "research", DESK):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    try:
        import external_gauntlet as eg  # type: ignore[import-not-found]
    except Exception:
        try:
            from desks.mt5.scripts import external_gauntlet as eg  # type: ignore[no-redef]
        except Exception:
            return None
    fn = getattr(eg, "certificate_retirement_reason", None)
    return fn if callable(fn) else None


def _reason(sym: str, meta: dict[str, Any], judge: VenueJudge | None) -> str:
    """Why the VENUE will never let this certificate be cashed, or "" if it can be.

    NO LOCAL PREDICATE. Everything here is the sealed judge's answer, plus the one case it cannot
    be asked about -- a row with no symbol at all, which names no instrument and so can never be
    enrolled whatever the registry says. A `judge` of None means the question could not be asked,
    which returns "" (retire nothing), never a guess.
    """
    if not sym:
        return "certificate carries no symbol"
    if judge is None:
        return ""
    try:
        why = judge(sym, meta)
    except Exception:
        return ""
    return str(why) if why else ""


def retire(path: Path, meta: dict[str, Any], stamp: str,
           judge: VenueJudge | None = None) -> tuple[int, list[str]]:
    """Move every uncashable survivor in `path` to `retired_certificates`. Returns (n, names)."""
    if not path.exists():
        return 0, []
    doc = json.loads(path.read_text("utf-8"))
    survivors = doc.get("survivors") or {}
    moved: dict[str, dict[str, Any]] = {}
    for key, row in list(survivors.items()):
        why = _reason(str((row or {}).get("sym") or ""), meta, judge)
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
    judge = _venue_judge()
    if judge is None:
        # THE PREDICATE IS THE AUTHORITY, AND ITS ABSENCE IS NOT ONE. Falling back to a local copy
        # is how this file came to hold a rule the sealed writer had already retracted.
        print("external_gauntlet.certificate_retirement_reason could not be imported -- refusing "
              "to judge any certificate uncashable. UNMEASURED is not a revocation.")
        return 1
    stamp = datetime.now(UTC).isoformat()
    total = 0
    for path in (AUTHORITY, CANON):
        n, names = retire(path, meta, stamp, judge)
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
