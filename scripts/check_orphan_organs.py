#!/usr/bin/env python3
"""IS ANYTHING ELSE SITTING LIKE run_derivative_shadow.py DID -- BUILT, RUNNABLE, NEVER RUN?

WHY THIS EXISTS. The principal asked directly why the desk had not noticed oi_divergence and
ls_contrarian could not have accrued a single day in the ~40 days since they were pre-registered.
The honest answer, measured rather than guessed: `check_build_standard.py`'s governed set --
the ONE fence on this desk that checks an organ is scheduled, tested, and refusal-capable -- names
61 scripts. `scripts/` holds 463, of which 448 look like real, invocable organs (`def main(` or
`if __name__ == "__main__":`). Two of the other 387 turned out to be exactly the defect the
principal asked about, found only because a direct question sent someone looking. The other 385
have never been looked at by anything automated at all.

`_GOVERNED` is a hand-maintained allowlist, and a hand-maintained allowlist for "things we check"
has exactly the failure mode this desk's own doctrine names for everything else: an organ that
does not appear on it is not exempt, it is simply invisible, and invisible is indistinguishable
from fine until someone happens to ask. This organ removes the "happens to ask" dependency.

WHAT IT CHECKS, for every scripts/*.py NOT already in check_build_standard._GOVERNED (that fence
owns its own 61 to its own five-dimension standard; this one is a coarser, broader net over
everything else):

    ORPHAN              looks like a real organ (has an entrypoint), has NO schedule (direct or
                        via a scheduled parent -- reusing check_build_standard's own transitive
                        detector so the two fences cannot disagree about what "scheduled" means),
                        and NO test references it. This is exactly the run_derivative_shadow.py /
                        screen_oi_ls_axes.py shape: built, never exercised by anything.
    UNSCHEDULED_TESTED  has test coverage (so CI would catch an import/logic break) but nothing
                        runs it live. A weaker defect -- verified but idle -- named separately so
                        it does not drown in the ORPHAN count.
    SCHEDULED_NO_TEST   runs live with no automated check that it still imports cleanly. Also
                        named, not silently passed.
    HEALTHY             scheduled (direct or transitive) and tested.

NOT EVERY UNSCHEDULED SCRIPT IS A DEFECT, and this organ does not pretend otherwise. Many of the
463 are legitimately one-off: a migration run once, a manual diagnostic invoked by hand, a
CLI tool for an operator. `_EXEMPT` is where those are named, each with a reason -- exactly the
pattern _SCHEDULE_EXEMPT already uses in check_build_standard.py. It starts SMALL on purpose:
pre-populating it with guesses about which of 387 unaudited scripts "are probably fine" would
recreate the exact blind spot this organ exists to close. Triage happens by a person reading the
report, not by this organ assuming innocence.

PAGES ONLY ON A NEW NAME, never on the standing count. The baseline from the first run will be
large -- reporting all of it as an alert every day would train everyone to ignore the alert, which
is worse than no alert. What has to reach a person immediately is the NEXT run_derivative_shadow.py:
an organ that did not exist in the last recorded set and now does, unscheduled and untested. The
full current list is always in the artifact for anyone who wants to triage the backlog.

    python scripts/check_orphan_organs.py [--json] [--page]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_build_standard import _GOVERNED, _scheduled_parent  # noqa: E402

OUT = "data/orphan_organs.json"

#: Scripts deliberately excluded, each with a stated reason. Kept SMALL and MANUALLY CURATED --
#: see the module docstring for why pre-populating this from a guess would recreate the exact
#: blind spot this organ exists to close.
_EXEMPT: dict[str, str] = {
    "check_orphan_organs.py": "this organ; it does not audit itself for the same reason "
                              "check_build_standard.py does not appear in its own _GOVERNED",
}


def _looks_like_an_organ(src: str) -> bool:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return True
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            left = node.test.left
            if isinstance(left, ast.Name) and left.id == "__name__":
                return True
    return False


def _is_scheduled(name: str, manifest: str, root: Path) -> tuple[bool, str]:
    if any(name in ln and ln[:1] in "0123456789*" for ln in manifest.splitlines()):
        return True, "direct cron/systemd line"
    if any(f'exec="scripts/{name}"' in ln for ln in manifest.splitlines()):
        return True, "direct systemd line"
    parent = _scheduled_parent(root, name, manifest)
    return (bool(parent), f"invoked by scheduled {parent}" if parent else "")


def audit(root: Path | None = None) -> dict[str, Any]:
    base = root or _ROOT
    try:
        manifest = (base / "ops/crontab.manifest").read_text("utf-8", errors="ignore")
    except OSError as exc:
        return {"status": "UNMEASURED", "why": f"manifest unreadable: {exc}"}

    test_blob = ""
    for t in (base / "tests").rglob("*.py"):
        with __import__("contextlib").suppress(OSError):
            test_blob += t.read_text("utf-8", errors="ignore")

    rows: list[dict[str, Any]] = []
    for p in sorted((base / "scripts").glob("*.py")):
        name = p.name
        if name in _GOVERNED or name in _EXEMPT:
            continue
        try:
            src = p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if not _looks_like_an_organ(src):
            continue
        scheduled, sched_why = _is_scheduled(name, manifest, base)
        tested = Path(name).stem in test_blob
        if scheduled and tested:
            cls = "HEALTHY"
        elif scheduled:
            cls = "SCHEDULED_NO_TEST"
        elif tested:
            cls = "UNSCHEDULED_TESTED"
        else:
            cls = "ORPHAN"
        rows.append({"organ": name, "class": cls, "scheduled": scheduled,
                    "scheduled_via": sched_why, "tested": tested})

    by_class: dict[str, list[str]] = {}
    for r in rows:
        by_class.setdefault(r["class"], []).append(r["organ"])

    prev, prev_orphans = {}, set()
    with __import__("contextlib").suppress(OSError, ValueError):
        prev = json.loads((base / OUT).read_text("utf-8"))
        prev_orphans = set(prev.get("by_class", {}).get("ORPHAN", []))
    new_orphans = sorted(set(by_class.get("ORPHAN", [])) - prev_orphans)

    return {
        "n_scripts_total": len(list((base / "scripts").glob("*.py"))),
        "n_governed_elsewhere": len(_GOVERNED),
        "n_exempt": len(_EXEMPT),
        "n_audited_here": len(rows),
        "by_class": {k: sorted(v) for k, v in sorted(by_class.items())},
        "new_orphans_since_last_run": new_orphans,
        "authority": "MEASUREMENT ONLY. Names candidates for scheduling or exemption; schedules "
                     "nothing, exempts nothing, fixes nothing.",
        "why_this_exists": "check_build_standard._GOVERNED audits 61 of 463 scripts by hand. "
                           "run_derivative_shadow.py and screen_oi_ls_axes.py were both built, "
                           "runnable, and never exercised by anything for weeks because neither "
                           "was ever added to that list -- this sweeps the other 402 so the next "
                           "one is a name in a report, not a question that has to be asked first.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--page", action="store_true")
    args = ap.parse_args(argv)

    doc = audit()
    if doc.get("status") == "UNMEASURED":
        if args.json:
            print(json.dumps(doc, indent=2))
        else:
            print(f"orphan-organ sweep: UNMEASURED -- {doc['why']}")
        return 0

    p = _ROOT / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), "utf-8")

    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        n_orphan = len(doc["by_class"].get("ORPHAN", []))
        print(f"orphan-organ sweep: {doc['n_audited_here']} audited, {n_orphan} ORPHAN, "
              f"{len(doc['new_orphans_since_last_run'])} new since last run")
        for cls, names in doc["by_class"].items():
            print(f"  {cls}: {len(names)}")

    if args.page and doc["new_orphans_since_last_run"]:
        try:
            from libs.ops.alert_channels import send_all
            send_all(f"{len(doc['new_orphans_since_last_run'])} new orphan organ(s)",
                     "Built, runnable, scheduled nowhere, tested nowhere -- the exact shape "
                     "run_derivative_shadow.py had for weeks:\n\n"
                     + "\n".join(f"  {n}" for n in doc["new_orphans_since_last_run"])
                     + f"\n\nFull list ({len(doc['by_class'].get('ORPHAN', []))} standing) in "
                       f"{OUT}. Each one needs either a cron line or a stated exemption.")
        except (OSError, ValueError, ImportError):
            pass
    return 0


if __name__ == "__main__":
    from libs.ops.lawful import guard as _law_guard
    _law_guard()
    raise SystemExit(main())
