"""Standing fixer: revive forward clocks stopped by a code identity that no longer exists.

WHY A STANDING FIXER AND NOT A ONE-OFF. `IDENTITY_BROKEN` is write-once by design and only
`reconcile()` ever cleared it -- and only when the frozen hash comes BACK, which is right for a
transient sync and useless when the desk deliberately edits a family. So every real code edit
permanently killed every clock on that family, and nothing in the desk noticed or recovered.
Measured 2026-09-03: 15 of 52 sleeves -- 29% of the forward book, 110 accrued forward-days --
were terminal on `code_hash changed after the clock froze`, all marked within 13 minutes of each
other while module ships landed. They had been accruing nothing while their day counters kept
running, which the same-day fence calls the worst combination: the clock matures on stale data.

TWO DIFFERENT REPAIRS, AND THE DIFFERENCE IS THE POINT:

  * `reconcile()` first -- the identity came back byte-identical, so the whole replayed series is
    the frozen strategy's own output and the WINDOW IS KEPT. Nothing was lost, nothing is
    laundered.
  * `rebase_code()` only when reconcile refuses -- the frozen code exists nowhere, so the desk
    cannot prove the logic is unchanged and the window RESETS. The sleeve re-earns its days
    against the code actually running. That price is deliberate: the pre-registration named one
    strategy and a different one may not inherit its days.

Going forward the common cause is gone: `sleeve_registry.behaviour_hash` records bytecode rather
than source text, so editing a comment or docstring can no longer read as a strategy change.
This fixer exists for rows frozen before that field existed, and for genuine logic edits -- which
should be rare, and which should cost a window.

    python3 desks/mt5/scripts/heal_identity_broken_clocks.py [--apply]

Reports and changes nothing without --apply, because reviving a clock is a change to what the
desk will treat as evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK.parents[1]))

import sleeve_registry as reg  # noqa: E402


def current_identity(row: dict) -> dict | None:
    """Rebuild the identity this sleeve WOULD freeze today, or None if it cannot be computed.

    UNMEASURED IS A REAL ANSWER (L1.28a). If the family cannot be loaded the row is left exactly
    as it is: a clock that cannot be evaluated is not a clock that may be revived.
    """
    frozen = dict(row.get("identity") or {})
    if not frozen:
        return None
    # THE SAME RESOLUTION THE FORWARD ENGINE USES, not a narrower one. `get_family_func` only
    # searches FAMILY_REGISTRY, and the desk's most numerous family -- `discovered`, the one
    # edge_search mints -- lives in ORTHOGONAL_FAMILIES. Resolving with the narrow lookup returned
    # None for every one of those rows, so they were silently skipped and the backfill reported
    # zero: a healer that appeared to run cleanly while covering none of the clocks that needed it.
    fam = str(frozen.get("family") or "")
    fn = None
    try:
        from mt5desk import families
        fn = getattr(families, f"family_{fam}", None)
    except ImportError:
        return None
    if fn is None:
        try:
            from mt5desk import families_orthogonal as _fo
            fn = _fo.ORTHOGONAL_FAMILIES.get(fam)
        except ImportError:
            fn = None
    if fn is None:
        return None
    ident = dict(frozen)
    ident["code_hash"] = reg.code_hash(fn)
    ident["behaviour_hash"] = reg.behaviour_hash(fn)
    return ident


def backfill_behaviour(registry_path: Path, *, apply: bool) -> int:
    """Record a behaviour hash on every INTACT clock that lacks one. Returns rows immunised.

    WHY THIS IS THE OTHER HALF OF THE FIX. `behaviour_hash` only stops a prose edit from killing a
    clock when BOTH the frozen identity and the current one carry it -- absence never clears a
    drift, deliberately, because a missing hash is not evidence of anything. So every row frozen
    before the field existed is still one comment away from going terminal. Measured 2026-09-03
    after the first repair: 15 of 52 rows carried the field (the ones just rebased) and 37 did
    not. Those 37 were exactly as fragile as the 15 had been an hour earlier.

    THE BACKFILL IS SAFE BECAUSE OF ITS PRECONDITION, WHICH IS NOT NEGOTIABLE. It fires only when
    the frozen `code_hash` still EQUALS the current one. That equality means the function's source
    is byte-identical to what the clock froze, so its bytecode is necessarily the bytecode that
    was frozen too -- recording it asserts nothing new, it writes down a fact the identity check
    has already verified this pass. A row whose code_hash has drifted is skipped entirely: for
    that row the current behaviour is NOT known to be the frozen behaviour, and guessing would be
    the laundering this whole mechanism exists to prevent.
    """
    reg = json.loads(registry_path.read_text("utf-8"))
    changed = 0
    for _key, row in (reg.get("sleeves") or {}).items():
        frozen = row.get("identity") or {}
        if not frozen or frozen.get("behaviour_hash"):
            continue
        ident = current_identity(row)
        if ident is None:
            continue
        if frozen.get("code_hash") != ident.get("code_hash"):
            continue                    # drifted: current behaviour is not the frozen behaviour
        beh = ident.get("behaviour_hash")
        if not beh or str(beh).startswith("nocode:"):
            continue                    # UNMEASURED is a real answer -- never write a guess
        if apply:
            frozen["behaviour_hash"] = beh
            row["behaviour_backfilled_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        changed += 1
    if changed and apply:
        reg["updated_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        tmp = registry_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(reg, indent=1), "utf-8")
        tmp.replace(registry_path)
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually revive; without it this only reports")
    args = ap.parse_args()

    registry = json.loads((DESK / "data" / "sleeve_registry.json").read_text("utf-8"))
    # BACKFILL FIRST, AND UNCONDITIONALLY. This ran after an early `return 0` taken when nothing
    # was broken -- so it fired only on cycles where a clock had ALREADY died, which is precisely
    # when immunisation is too late. Immunising healthy rows is the entire point: it is what stops
    # the next prose edit from breaking them. Measured 2026-09-03: the first shipped version left
    # 37 of 52 rows uncovered because every run took that early exit.
    immunised = backfill_behaviour(DESK / "data" / "sleeve_registry.json", apply=args.apply)
    if immunised:
        print(f"identity healer: recorded a behaviour hash on {immunised} intact clock(s) "
              f"-- a prose edit can no longer stop them")
        registry = json.loads((DESK / "data" / "sleeve_registry.json").read_text("utf-8"))

    broken = {k: v for k, v in (registry.get("sleeves") or {}).items()
              if str(v.get("status") or "").upper() == "IDENTITY_BROKEN"}
    if not broken:
        print("identity healer: no IDENTITY_BROKEN clocks")
        return 0

    resumed, rebased, refused = [], [], []
    for key, row in sorted(broken.items()):
        ident = current_identity(row)
        if ident is None:
            refused.append((key, "family not loadable here; nothing computed, nothing changed"))
            continue
        if args.apply:
            why = reg.reconcile(key, ident, replayed=True)
            if why:
                resumed.append((key, why))
                continue
            why = reg.rebase_code(key, ident)
            if why:
                rebased.append((key, why))
                continue
            refused.append((key, "drift is not code_hash alone -- a strategy change stays dead"))
        else:
            drift = reg.verify(key, ident)
            if not drift:
                resumed.append((key, "identity intact again -- window would be KEPT"))
            elif drift == ["code_hash"]:
                rebased.append((key, f"code {row['identity'].get('code_hash')} -> "
                                     f"{ident.get('code_hash')} -- window would RESET"))
            else:
                refused.append((key, f"drifted on {drift} -- stays dead"))

    verb = "" if args.apply else " (dry run -- pass --apply)"
    print(f"identity healer{verb}: {len(broken)} broken -> "
          f"{len(resumed)} resumed (window kept), {len(rebased)} rebased (window reset), "
          f"{len(refused)} left terminal")
    for group, label in ((resumed, "RESUMED"), (rebased, "REBASED"), (refused, "TERMINAL")):
        for key, why in group:
            print(f"  {label:9s} {key[:46]:<48} {why[:96]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
