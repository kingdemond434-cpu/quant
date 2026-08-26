#!/usr/bin/env python3
"""Money-path content fence (GAP 128) -- canon files defend themselves in the shared tree.

MEASURED ATTACK, 2026-08-25: a sibling session overwrote gateway.py and promoter.py with a
stale 478-line ancestor at 19:39/19:43/19:46 -- twice within minutes of a manual restore --
and the hourly tree-sweep committer then wrote the stale versions into history (cbeb287d).
Manual restores lose that race by construction; this fence runs on a clock and restores canon
whenever a protected file loses its canon MARKER (a symbol that exists only in the canonical
version and in no ancestor). A marker check beats a hash pin because legitimate new work on
these files keeps its markers and passes untouched.

    python3 scripts/check_moneypath_fence.py          # restore + commit if breached; exit 1
"""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "moneypath_fence.log"

#: Known-good commit holding every protected file with its marker; the fallback source when
#: HEAD itself has been swept stale. Advancing this pin is a deliberate act in a commit that
#: also changes the protected file -- never automatic.
CANON_COMMIT = "73ca07b9"  # verified 2026-08-26 (2nd advance): all 16 markers present in this tree
                           # (b239108d, the prior pin, lacked BOTH shadow_forward markers, so a
                           # canon-fallback restore would itself have stripped the properties)

#: file -> marker(s) that exist ONLY in the canonical lineage of that file. A tuple means
#: EVERY marker must be present: one marker per protected property, because a trample can
#: revert one property while keeping another (measured 2026-08-26 on shadow_forward.py).
PROTECTED: dict[str, str | tuple[str, ...]] = {
    "desks/mt5/mt5desk/gateway.py": "run_family_sleeves",
    "desks/mt5/mt5desk/sizing.py": "BASE_RISK_FRAC",
    "desks/mt5/research/promoter.py": "authorized_specs",
    "desks/mt5/research/qquant_shadow.py": "PROMOTION_CANDIDATE",
    "desks/mt5/moat/moat_recorder.py": "copy_ticks_range",
    "desks/mt5/moat/moat_fence.py": "symbols_floor",
    # 2026-08-26: the hourly sync bus committed the DESK BOX's stale copies over these two
    # VPS-owned files -- the certifier then ran the pre-patch writer and produced 15 spec-less
    # certificates (authority the admission door refuses). Marker = the patch each file must
    # never lose: the gauntlet's spec/attestation writer, the state builder's live MT5 snapshot.
    "desks/mt5/scripts/external_gauntlet.py": "ATTESTATION",
    "scripts/build_zentech_state.py": "_mt5_snapshot",
    # the same-day engine's stamped clock + certificate auto-enrolment (RESEARCH 6d), AND its
    # broker-independent bar source. 2026-08-26: a sync trample stripped the h1_source repoint
    # (a0c3de04) while KEEPING certified_sleeves, so a single marker read the file as healthy
    # while the shadow engine was re-welded to a Windows terminal it does not have -- every
    # protected property needs its own marker, hence tuples.
    "desks/mt5/research/shadow_forward.py": (
        "certified_sleeves", "from research.h1_source import fetch_h1"),
    "desks/mt5/research/decay_monitor.py": "DD_HARD_R",
    # grandfathering is over: SLEEVES must stay empty and enrolment must stay certificate-driven
    "desks/mt5/research/forward_reconcile.py": "RETIRED_ORPHAN",
    # 2026-08-26 (gap-wirer): five more unification-reverted properties re-applied and fenced.
    # Each marker is the patch the file must never lose; every one of these was ALREADY lost
    # once to a sync trample or branch unification, which is exactly why it is here.
    "desks/mt5/research/universal_gate.py": "retained_exact_survivors",
    "desks/mt5/research/run_hunt12.py": "_day_states_same_day",
    "desks/mt5/research/allocation.py": "from mt5desk.gateway import Q_OPT",
    "desks/mt5/research/portfolio_projection.py": "from_symbol",
    "desks/mt5/mt5desk/config.py": "def desk_root",
    "desks/mt5/mt5desk/families.py": "d1_session_filtered",
    # 2026-08-26 01:19-01:21 UTC, MEASURED: the C:-side hourly pusher overwrote EVERY unmarkered
    # file above-and-below with stale copies and the sweep commit (eb1818f4) laundered them into
    # history within two minutes -- the fence's own docstring scenario, executed end to end.
    # Marker coverage is therefore the survival condition for a fix in this tree, not a nicety.
    "desks/mt5/mt5desk/engine.py": "trail_tighten_k",       # pessimistic intrabar order + exits
    "desks/mt5/research/run_hunt17.py": "d1_session_filtered",
    "desks/mt5/research/regime_discovery.py": "d1_session_filtered",
    "desks/mt5/research/fragility.py": "d1_session_filtered",
    "desks/mt5/research/orthogonality.py": "research.portfolio_projection",
}


def _markers(spec: str | tuple[str, ...]) -> tuple[str, ...]:
    return (spec,) if isinstance(spec, str) else spec


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=120, check=False)


def head_has_marker(path: str, spec: str | tuple[str, ...]) -> bool:
    r = git("show", f"HEAD:{path}")
    return r.returncode == 0 and all(m in r.stdout for m in _markers(spec))


def main() -> int:
    breached: list[str] = []
    for path, spec in PROTECTED.items():
        f = ROOT / path
        try:
            text = f.read_text("utf-8", errors="ignore") if f.is_file() else ""
            missing = [m for m in _markers(spec) if m not in text]
            ok = f.is_file() and not missing
        except OSError:
            ok, missing = False, list(_markers(spec))
        if ok:
            continue
        src = "HEAD" if head_has_marker(path, spec) else CANON_COMMIT
        r = git("checkout", src, "--", path)
        if r.returncode == 0:
            log(f"BREACH+RESTORED {path}: marker(s) {missing} missing; restored from {src}")
            breached.append(path)
        else:
            log(f"BREACH UNRESTORABLE {path}: {r.stderr.strip()[:200]}")
            breached.append(path)
    if not breached:
        return 0
    # Commit ONLY the protected paths, so a sweep cannot re-commit the stale content on top
    # of a restored tree. Explicit paths per R0423; never -A.
    git("add", "--", *breached)
    r = git("commit", "-m",
            f"moneypath fence: restored {len(breached)} canon file(s) after shared-tree "
            f"revert (GAP 128)\n\nFiles: {', '.join(breached)}\n"
            f"The fence restores by canon marker; see data/moneypath_fence.log.")
    log(f"fence commit rc={r.returncode} for {breached}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
