"""Why this box has no LLM seat, answered precisely and without ever printing a key.

    py -3 desks\\mt5\\scripts\\check_llm_seat.py

WHAT THIS IS FOR. Measured on the box 2026-09-07: `world_crawler` worked 910 tasks and rejected
every one of them with

    seat error: no seat: export OPENROUTER_API_KEY ... or write data/secrets/llm_panel.json

That single message is the whole diagnostic the desk had, and it is the same string whether the
key is absent, present under a different name, present in the wrong file, present in a file that
does not parse, or present in an environment the scheduled task cannot see. Those have five
different fixes, and "no seat" points at none of them.

It also matters more than it looks. A dark seat does not stop the desk, it makes the desk
PRODUCTIVE AND STERILE: the miners keep producing rows, the deepening worker rejects every one,
and the issue board reports "miners are producing rows and no survivors" -- which reads as a
research quality problem and is actually an unset variable.

NO KEY IS EVER PRINTED, and that is not negotiable (`data/secrets/` never leaves the box). This
reports PRESENCE, length class and the last four characters at most -- enough to tell two keys
apart, never enough to use one.

THE WINDOWS FAILURE THIS EXISTS TO CATCH. `setx` writes the variable into the user's registry
environment, and the Task Scheduler service caches its environment block: a task REGISTERED
BEFORE the variable was set keeps running without it, indefinitely, while an interactive
PowerShell in the same account shows the variable set. That is why "the key is there" and "the
box has no seat" can both be true, and why this checks the scheduled-task view separately.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
REPO = DESK.parent.parent
for _p in (str(DESK), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: Every place a `llm_panel.json` plausibly gets written by hand. Only the FIRST is read by
#: `llm_seat`; the rest are checked so a file in the wrong place is reported as such rather than
#: as an absence. Putting it under the desk's own data directory is the obvious mistake, because
#: every other secret and artifact on this desk lives there.
CANDIDATE_SECRETS = (
    REPO / "data" / "secrets" / "llm_panel.json",          # the one llm_seat reads
    DESK / "data" / "secrets" / "llm_panel.json",
    REPO / "desks" / "mt5" / "data" / "secrets" / "llm_panel.json",
    Path.home() / "llm_panel.json",
)


def _mask(value: str) -> str:
    """Enough to tell two keys apart, never enough to use one."""
    v = (value or "").strip()
    if not v:
        return "(empty)"
    return f"set, {len(v)} chars, ends {v[-4:]!r}"


def main() -> int:
    try:
        from libs.ops import llm_seat
    except Exception as exc:                                            # noqa: BLE001
        print(f"FATAL: cannot import libs.ops.llm_seat ({type(exc).__name__}: {exc})")
        print(f"       expected the repository root on sys.path: {REPO}")
        return 2

    print("LLM SEAT DIAGNOSTIC")
    print(f"  repo root     {REPO}")
    print(f"  seat reads    {llm_seat.SECRETS}")
    print()

    print("ENVIRONMENT (this process's view)")
    env_hits = 0
    for var, name, _base in llm_seat.KEY_ENV_VARS:
        raw = os.environ.get(var, "")
        if raw.strip():
            env_hits += 1
            print(f"  [OK  ] {var:22} {_mask(raw)}  -> seat '{name}'")
        else:
            print(f"  [    ] {var:22} not set")
    print()

    print("SECRETS FILE")
    found_elsewhere: list[Path] = []
    for path in CANDIDATE_SECRETS:
        if not path.exists():
            continue
        is_the_one = path.resolve() == Path(llm_seat.SECRETS).resolve()
        try:
            cfg = json.loads(path.read_text("utf-8"))
            providers = cfg.get("providers") or []
            keyed = sum(1 for p in providers if str(p.get("key") or "").strip())
            detail = f"{len(providers)} provider(s), {keyed} with a key"
        except (json.JSONDecodeError, OSError) as exc:
            detail = f"UNREADABLE: {type(exc).__name__}: {exc}"
        if is_the_one:
            print(f"  [OK  ] {path}  ({detail})")
        else:
            found_elsewhere.append(path)
            print(f"  [WRONG PLACE] {path}  ({detail})")
    if not any(p.exists() for p in CANDIDATE_SECRETS):
        print(f"  [    ] no llm_panel.json at any of {len(CANDIDATE_SECRETS)} checked locations")
    print()

    got = llm_seat.seats()
    print(f"SEATS RESOLVED: {len(got)}")
    for seat in got:
        print(f"  {seat.name:12} via {seat.source:26} {_mask(seat.key)}")
    print()

    if got:
        print("VERDICT: this process can reach a seat.")
        # THE POINT OF SPLITTING THE TWO. A seat here does NOT mean the scheduled tasks have one:
        # they run in a different process with a different environment block.
        if env_hits and not found_elsewhere:
            print()
            print("  If the SCHEDULED TASKS still report 'no seat' while this says OK, the")
            print("  variable is set in your interactive session and NOT in the environment")
            print("  Task Scheduler cached. Two fixes, either is enough:")
            print("    1. setx OPENROUTER_API_KEY \"<key>\"   then RESTART the box (the service")
            print("       re-reads the environment at boot; re-registering the task is not enough)")
            print(f"    2. write the key into {llm_seat.SECRETS} instead -- a file has no")
            print("       environment-inheritance problem at all, and is the durable answer here")
        return 0

    print("VERDICT: NO SEAT. Every LLM organ on this box is dark, which presents as")
    print("         'miners are producing rows and no survivors' rather than as a config error.")
    print()
    if found_elsewhere:
        print("  A panel file EXISTS but not where the seat layer reads it. Move it:")
        for path in found_elsewhere:
            print(f"    move  {path}")
            print(f"      to  {llm_seat.SECRETS}")
    else:
        print("  Write the panel file (survives reboots and Task Scheduler's cached env):")
        print(f"    {llm_seat.SECRETS}")
        print('    {"providers": [{"name": "openrouter",')
        print('                    "base_url": "https://openrouter.ai/api/v1",')
        print('                    "key": "<your key>"}]}')
    print()
    print("  data/secrets/ is git-ignored and never leaves this box.")
    return 1


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
