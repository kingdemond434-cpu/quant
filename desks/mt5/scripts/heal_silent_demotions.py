"""Standing fixer: restore LIVE sleeves demoted to STANDBY with no reason recorded.

MEASURED 2026-09-11 on the big box, 56 minutes after the desk moved there:

    data/sleeves.json   65 rows   LIVE 44   STANDBY 21
    all 21 STANDBY rows: "(no reason recorded)"

The roster carried 65 LIVE rows at cutover. An organ rewrote it at 21:04 and 21 rows came back
STANDBY -- including every scalp but one, and 16 of the 53 certified family survivors -- with
no `retire_reason`, no `status_reason`, and nothing in any log naming a cell. The book shrank
by a third and no artifact said why.

A DEMOTION WITHOUT A REASON IS NOT A VERDICT. That is the same law the desk applies everywhere
else: absence never resolves to a clean verdict (WS-005 / L1.28a), and a retirement that does
not propagate its cause is a rename rather than a retirement (the 2026-08-26 RETIRED_ORPHAN
lesson, which cost 82 forward clocks). A promoter that demotes for cause records the cause; a
demotion that records nothing is indistinguishable from a file that was rewritten by something
that never read the row at all -- and this desk has spent the whole day finding exactly that.

WHAT IT WILL NOT DO. A row demoted WITH a reason is left alone, always. That is the promoter
doing its job -- automatic retirement is standing policy and this fixer never overrides a
judgement someone actually made. Only the silent ones are restored, and each restoration is
stamped so the next reader can tell a revived row from one that was never touched.

RESTORING LIVE IS NOT SIZING. A LIVE row is REACHABLE, not funded: `cap_by_heat` still prices
it, the allocator still decides its fraction, and the release identity still has to be clean
for anything to place. Restoring reachability cannot by itself put on a position.

    python desks/mt5/scripts/heal_silent_demotions.py            # report
    python desks/mt5/scripts/heal_silent_demotions.py --apply    # restore
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SLEEVES = ROOT / "desks" / "mt5" / "data" / "sleeves.json"
REPLICATION_WAIVER = ROOT / "desks" / "mt5" / "data" / "REPLICATION_WAIVER.json"

#: Fields any organ demoting for cause is expected to leave behind. If none carries text, the
#: demotion recorded nothing and this fixer treats it as an accident rather than a decision.
REASON_FIELDS = ("retire_reason", "status_reason", "reason", "why", "demoted_reason",
                 "retired_reason", "gate_reason", "demote_reason", "standby_reason")

#: THE FIXER UNDID A STOP ORDER (measured 2026-10-14). The 2026-10-13 21:30Z stop-the-bleed set
#: the AUDCHF/EURZAR/USDZAR gap-decay principals to STANDBY with `standby_reason` naming the
#: principal's order -- a field this list did not carry. So the three read as "demoted with no
#: reason" and were lifted back to LIVE at 0.10 within four hours (EURZAR 21:50Z, USDZAR 23:50Z,
#: AUDCHF 01:50Z). A fixed list of names is the defect class: any other `*_reason` spelling
#: repeats it. So ANY non-empty `<something>_reason` field counts as a recorded reason, except
#: the restorers' own stamps, which say why a row came BACK, not why it left.
_NOT_A_DEMOTION_REASON = ("restore_reason", "restored_reason")


def _admission_reason(row: dict) -> str:
    """The promoter's own STANDBY verdict, carried on the row's `admission` block.

    THE FIXER WAS UNDOING THE PROMOTER EVERY HOUR (measured 2026-09-30). `promoter.py` records a
    capital demotion as `demote_reason` plus `admission: {"status": "STANDBY", "why": ...}` --
    neither of which this fixer read. So every row the allocator zeroed read as "demoted with no
    reason", was lifted back to LIVE at :48, and traded until the next promoter pass demoted it
    again. `xauusd_macro_conditional_asia_p_5fa26e22` did exactly that: STANDBY at 0% heat, yet it
    placed live 0.01-lot orders on 2026-09-25 and 2026-09-30 inside those restored windows.
    """
    adm = row.get("admission")
    if isinstance(adm, dict) and str(adm.get("status") or "").upper() == "STANDBY":
        why = adm.get("why")
        if isinstance(why, str) and why.strip():
            return why.strip()
    return ""

#: Statuses this fixer will lift back to LIVE. STANDBY is the promoter's holding state; KILL,
#: RETIRED and QUARANTINED are verdicts and are never touched here whatever they do or do not
#: record, because lifting a verdict is a different act needing a different justification.
LIFTABLE = ("STANDBY",)


def _reason(row: dict) -> str:
    for f in REASON_FIELDS:
        v = row.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for f, v in row.items():
        if (isinstance(f, str) and f.endswith("_reason") and f not in _NOT_A_DEMOTION_REASON
                and isinstance(v, str) and v.strip()):
            return v.strip()
    return _admission_reason(row)


def _replication_refusal(row: dict, gate: object | None, waived: set[str]) -> str:
    """THE LIVE DOOR, AT THIS WRITER TOO (coordinator ruling C, 2026-10-14). This script writes
    sleeves.json itself, outside the promoter's `save_sleeves`, so restoring a canon certificate
    to LIVE here needs the same REPLICATED verdict (or the principal's named waiver). Fails closed
    when the verdict book cannot be read. "" means the row may be restored.

    The certificate is read by `admission_integrity.canon_certificate`, the function the promoter
    reads it by, and a scalp lane row passes only while `scalp_refusal` says the lane's ban stands.
    A main-lane row the promoter has not yet stamped with `canon_certificate` is looked up by its
    clock key, finds no verdict and is left for the promoter's own restore (fail closed)."""
    if gate is None:
        return ("REFUSED_UNREPLICATED: replication verdicts unreadable"
                if (row.get("certificate") or row.get("principal_certificate")) else "")
    import admission_integrity as ai
    if ai.scalp_lane_marker(row):
        return ai.scalp_refusal()
    if (row.get("canon_certificate") and not row.get("principal_certificate")
            and isinstance(row.get("certificate"), str)):
        # A lane row's stamped canon certificate is verified against the enrolment only by the
        # promoter (`_row_check`); this writer cannot, so it leaves the restore to the promoter.
        return ("REFUSED_UNREPLICATED: lane row's canon_certificate is verified against the "
                "clock enrolment by the promoter's restore, not here")
    cid = ai.canon_certificate(row)
    if not cid:
        return ""
    return gate.live_refusal(cid, waived=cid in waived) or ""  # type: ignore[attr-defined]


def _door() -> tuple[object | None, set[str]]:
    try:
        sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
        from admission_integrity import IntegrityGate
        gate: object | None = IntegrityGate.load()
    except Exception:
        gate = None
    try:
        doc = json.loads(REPLICATION_WAIVER.read_text(encoding="utf-8"))
        waived = {str(k) for k, v in ((doc or {}).get("certificates") or {}).items()
                  if isinstance(v, str) and v.strip()}
    except (OSError, ValueError, AttributeError):
        waived = set()
    return gate, waived


def _restore_door() -> Callable[[dict], str]:
    """THE PROMOTER'S RESTORE DOOR, AT THIS WRITER TOO (Judge 2026-10-20: a restore is a
    promotion). This script lifts STANDBY to LIVE outside the promoter, so a silent row it restores
    is asked the same doors `promoter.reconcile_capital` asks (`promoter.restore_door_refusal`:
    cost re-grade, blind reviewer, Tier S, principal stops). Fails closed: a promoter that does
    not import refuses every restore with its reason. "" means the row may be restored."""
    try:
        sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
        import promoter
        fails = promoter.regrade_failures()
    except Exception as exc:
        why = (f"RESTORE_DOOR_UNMEASURED: the promoter's restore door did not load "
               f"({type(exc).__name__}: {exc})")
        return lambda _row: why

    def ask(row: dict) -> str:
        try:
            return promoter.restore_door_refusal(row, fails)
        except Exception as exc:
            return (f"RESTORE_DOOR_UNMEASURED: the restore door raised "
                    f"({type(exc).__name__}: {exc})")
    return ask


def heal(apply: bool) -> int:
    doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    rows = doc["sleeves"]
    by_status = Counter(str(r.get("status") or "?") for r in rows)
    print(f"roster: {len(rows)} rows   {dict(by_status)}")

    # A PRINCIPAL STOP IS NEVER HEALED (2026-10-14). Reading the row's reason fields covers a stop
    # that wrote its reason in a field this fixer knows (#397 widens that to any `*_reason`); this
    # covers the one that did not -- a re-mint, a rewritten roster, a field someone dropped. A stop
    # in PRINCIPAL_STOPS.json holds the identity whatever the row records, and with no readable
    # stops file this fixer restores nothing: it cannot tell a stop from an accident.
    import sys as _sys
    _desk = str(ROOT / "desks" / "mt5")
    if _desk not in _sys.path:
        _sys.path.insert(0, _desk)
    from mt5desk.principal_stops import load, match
    stops, problem = load(SLEEVES.with_name("PRINCIPAL_STOPS.json"))
    if problem:
        print(f"PRINCIPAL STOPS UNREADABLE ({problem}): restoring nothing this pass")
        return 1

    silent, reasoned, held = [], [], []
    gate, waived = _door()
    door: Callable[[dict], str] | None = None
    for r in rows:
        if str(r.get("status") or "").upper() not in LIFTABLE:
            continue
        if match(r, stops) is not None:
            held.append(r)
            continue
        if str(r.get("restore_refusal") or "").strip():
            # THE RESTORE DOOR'S REFUSAL HOLDS HERE TOO (audit 2026-10-20, must-fix 1). It is not
            # a `*_reason` -- reconcile_capital re-asks the doors every pass and clears it the pass
            # they open -- so `_reason` reads "" for a row the door just refused, and lifting it
            # here would put back LIVE what the promoter withheld an hour earlier.
            reasoned.append(r)
            continue
        if not _reason(r):
            refusal = _replication_refusal(r, gate, waived)
            if refusal:
                # Recorded as the door's own field, NOT a `*_reason`: a reason would hold the row
                # forever, while this is re-asked every pass and clears the pass the certificate
                # replicates (audit of ruling C, 2026-10-14).
                r["replication_refusal"] = refusal
                reasoned.append(r)
                continue
            r.pop("replication_refusal", None)
            if door is None:
                door = _restore_door()
            refusal = door(r)
            if refusal:
                # The promoter's own field and wording: reconcile_capital re-asks and clears it.
                r["restore_refusal"] = refusal
                reasoned.append(r)
                continue
        (reasoned if _reason(r) else silent).append(r)
    print(f"STANDBY held by a principal stop: {len(held)}  (never restored here)")

    print(f"\nSTANDBY with a recorded reason : {len(reasoned)}  (left alone -- a real verdict)")
    for r in reasoned[:4]:
        why = (_reason(r) or str(r.get("restore_refusal") or "")
               or str(r.get("replication_refusal") or ""))
        print(f"   {str(r.get('name'))[:46]:<48} {why[:70]}")
    print(f"STANDBY with NO reason         : {len(silent)}  (restorable)")
    for r in silent[:8]:
        print(f"   {str(r.get('name'))[:46]:<48} exec={r.get('exec')} sym={r.get('symbol')}")
    if len(silent) > 8:
        print(f"   ... and {len(silent) - 8} more")

    if not silent:
        print("\nnothing to restore")
        return 0
    if not apply:
        print("\nreport only; nothing changed. Re-run with --apply to restore them.")
        return 0

    shutil.copy2(SLEEVES, SLEEVES.with_suffix(".json.pre_undemote"))
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for r in silent:
        r["status"] = "LIVE"
        r["restored_from"] = "STANDBY"
        r["restored_at"] = now
        r["restored_by"] = "heal_silent_demotions"
        r["restored_why"] = ("demoted to STANDBY with no reason recorded on any of "
                             f"{', '.join(REASON_FIELDS)}; a demotion that records nothing is "
                             "not a verdict")
    SLEEVES.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    after = Counter(str(x.get("status") or "?") for x in rows)
    print(f"\nrestored {len(silent)} row(s) -> {dict(after)}")
    print(f"previous file kept as {SLEEVES.name}.pre_undemote")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    return heal(ap.parse_args(argv).apply)


if __name__ == "__main__":
    raise SystemExit(main())
