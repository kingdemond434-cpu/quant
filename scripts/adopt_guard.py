#!/usr/bin/env python3
"""The unattended adopter's guard: audited code only, never near a trade window, roll back on its
own. See `libs.ops.adopt_guard` for the rules; Adopt-And-Seal.ps1 is the only scheduled caller.

    python scripts/adopt_guard.py pre --target <sha>          # 0 go, 10 hold, 2 error
    python scripts/adopt_guard.py smoke                       # 0 ok, 11 unhealthy
    python scripts/adopt_guard.py blackout [--margin-min 30]  # 0 clear, 10 inside a window
    python scripts/adopt_guard.py gateway-alive               # prints 1 or 0
    python scripts/adopt_guard.py loaded-since --since <iso>  # prints 1 or 0
    python scripts/adopt_guard.py health (--sealed <code sha> | --sealed-at <commit>) \\
        --since <iso> --gateway-expected 0|1 [--page-on-fail]  # 0 healthy (lifts our hold) / 11
    python scripts/adopt_guard.py heal --gateway-expected 0|1 # one look; lifts our hold if healthy
    python scripts/adopt_guard.py hold --why "<text>" --run <id>  # 0 placed / 12 unwritable
    python scripts/adopt_guard.py lift --run <id>             # 0; only the hold <id> placed
    python scripts/adopt_guard.py rollback --to <sha> --bad <sha> --why "<text>"  # 0 / 12
    python scripts/adopt_guard.py state-apply                 # 0 applied/nothing, 10 waiting
    python scripts/adopt_guard.py state-verify                # 0 / 11 restored / 12 restore failed
    python scripts/adopt_guard.py clear-row --commit <sha> --verdict CLEAR \\
        --report reports/audit/2026-10-28/X.md --base origin/<live branch>   # for the lander

THE NEW-RISK HOLD. Adopt-And-Seal puts it up (`hold`) BEFORE Adopt-Release writes a byte, so a run
killed half-way leaves every lane held, not trading a half-written tree; `rollback` puts it up too
when it is not already. A `health` or `heal` that passes lifts it; `lift` is called only on the
exits where nothing was adopted. A rollback that fails, a health check after a rollback that
fails, and a `heal` that finds the hold older than 90 minutes and the release still unhealthy,
page.

Every subcommand prints one JSON object and rewrites desks/mt5/reports/ADOPT_GUARD.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import adopt_guard as ag  # noqa: E402

#: A hold of ours still up after this long, on a release that is still unhealthy, is a run that
#: died mid-adoption or a rollback nobody has fixed: page instead of waiting another hour.
HEAL_PAGE_AFTER_S = 90 * 60


def _since(v: str) -> datetime:
    t = datetime.fromisoformat(v)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pre")
    p.add_argument("--target", required=True)
    sub.add_parser("smoke")
    b = sub.add_parser("blackout")
    b.add_argument("--margin-min", type=int, default=0)
    sub.add_parser("gateway-alive")
    ls = sub.add_parser("loaded-since")
    ls.add_argument("--since", required=True)
    h = sub.add_parser("health")
    which = h.add_mutually_exclusive_group(required=True)
    which.add_argument("--sealed")
    which.add_argument("--sealed-at")
    h.add_argument("--since", required=True)
    h.add_argument("--gateway-expected", type=int, choices=(0, 1), required=True)
    h.add_argument("--page-on-fail", action="store_true")
    hl = sub.add_parser("heal")
    hl.add_argument("--gateway-expected", type=int, choices=(0, 1), required=True)
    ho = sub.add_parser("hold")
    ho.add_argument("--why", required=True)
    ho.add_argument("--run", required=True)
    li = sub.add_parser("lift")
    li.add_argument("--run", required=True)
    r = sub.add_parser("rollback")
    r.add_argument("--to", required=True)
    r.add_argument("--bad", required=True)
    r.add_argument("--why", required=True)
    sub.add_parser("state-apply")
    sub.add_parser("state-verify")
    c = sub.add_parser("clear-row")
    c.add_argument("--commit", required=True)
    c.add_argument("--verdict", choices=("CLEAR", "HOLD"), required=True)
    c.add_argument("--report", required=True)
    c.add_argument("--base", required=True)
    a = ap.parse_args(argv)
    root = Path(a.root)

    if a.cmd == "gateway-alive":
        print("1" if ag.gateway_alive(root) else "0")
        return 0
    if a.cmd == "loaded-since":
        print("1" if ag.loaded_since(root, _since(a.since)) else "0")
        return 0
    if a.cmd == "clear-row":
        row = ag.clear_row(root, a.commit, a.verdict, a.report, base=a.base)
        print(json.dumps(row, sort_keys=True))
        return 0
    if a.cmd in ("hold", "lift"):
        # a "nothing was adopted" lift removes only the hold THIS run placed: one a failed
        # rollback left standing stays until a health check passes (adopter v3 audit MF1)
        if a.cmd == "hold":
            ok = ag.hold_new_risk(root, a.why, run=a.run)
            decision = "HELD" if ok else "HOLD_UNWRITABLE"
        else:
            ok = True
            decision = "LIFTED" if ag.lift_hold(root, run=a.run) else "NOT_OURS_TO_LIFT"
        doc = {"step": a.cmd, "exit": 0 if ok else ag.ROLLBACK_FAILED, "decision": decision}
        ag.write_report(root, doc)
        print(json.dumps(doc, sort_keys=True))
        return int(doc["exit"])
    if a.cmd == "rollback":
        # The hold goes up before anything else, so no lane opens on a half-restored tree.
        held = ag.hold_new_risk(root, f"rollback of {a.bad[:12]} in progress: {a.why}")
    try:
        if a.cmd == "pre":
            code, doc = ag.pre(root, a.target)
        elif a.cmd == "smoke":
            code, doc = ag.smoke(root)
        elif a.cmd == "blackout":
            why = ag.blackout(datetime.now(UTC), ag.load_policy(root), margin_min=a.margin_min)
            code, doc = (
                (ag.HOLD, {"decision": "HOLD_BLACKOUT", "reason": why})
                if why
                else (ag.GO, {"decision": "CLEAR_OF_WINDOWS"})
            )
        elif a.cmd == "state-apply":
            from libs.ops import desired_state

            code, doc = desired_state.apply(root)
        elif a.cmd == "state-verify":
            from libs.ops import desired_state

            # the two run independently (v8 audit): a garbled provisional record fails the
            # verify closed, and must not also stop a cancel request
            try:
                code, doc = desired_state.verify(root)
            except ag.GuardError as exc:
                code, doc = ag.ERROR, {"decision": "ERROR", "reason": str(exc)}
            # a cancel request never waits for the release gate or a gold window
            try:
                any_code, any_doc = desired_state.apply(root, any_time_only=True)
            except ag.GuardError as exc:
                any_code, any_doc = ag.ERROR, {"decision": "ERROR", "reason": str(exc)}
            doc["any_time"] = any_doc
            if code == ag.GO and any_code not in (ag.GO, ag.HOLD):
                code = any_code
        elif a.cmd == "heal" and (held_at := ag.own_hold_since(root)) is None:
            code, doc = ag.GO, {"decision": "NO_HOLD_OF_OURS"}
        elif a.cmd in ("health", "heal"):
            if a.cmd == "heal":
                since = held_at or datetime.fromtimestamp(0, UTC)  # not None: checked above
                sealed = ag.sealed_code_sha(root, "HEAD")
            else:
                since = _since(a.since)
                sealed = a.sealed or ag.sealed_code_sha(root, a.sealed_at)
            code, doc = ag.health(
                root,
                sealed,
                since,
                gateway_expected=bool(a.gateway_expected),
                wait_s=0 if a.cmd == "heal" else None,
                running_ok=a.cmd == "heal",
            )
            # a run killed mid-write leaves the seal unchanged and the code half-written: the
            # lanes import from disk, so heal never lifts over a dirty code tree
            dirty = ag.code_dirty(root) if a.cmd == "heal" and code == ag.GO else []
            if dirty:
                code, doc = (
                    ag.UNHEALTHY,
                    {
                        "decision": "UNHEALTHY",
                        "reason": f"{len(dirty)} code path(s) on disk differ from HEAD: {dirty[:5]}",
                    },
                )
            if code == ag.GO and ag.lift_hold(root):
                doc["lifted_new_risk_hold"] = True
            stuck = (
                a.cmd == "heal"
                and code != ag.GO
                and (datetime.now(UTC) - since).total_seconds() > HEAL_PAGE_AFTER_S
            )
            if code != ag.GO and (getattr(a, "page_on_fail", False) or stuck):
                ag.page(
                    root,
                    f"the release is unhealthy; new risk held on every lane since "
                    f"{since:%Y-%m-%d %H:%MZ}: {doc.get('reason')}",
                )
        else:
            code, doc = ag.rollback(root, a.to, bad=a.bad, why=a.why)
    except ag.GuardError as exc:
        code, doc = ag.ERROR, {"decision": "ERROR", "reason": str(exc)}
    except Exception as exc:  # fail closed and say why; a traceback alone pages nobody
        code, doc = ag.ERROR, {"decision": "ERROR", "reason": f"{type(exc).__name__}: {exc}"}
    if a.cmd == "rollback":
        doc["new_risk_hold"] = held
        if code != ag.GO:
            code = ag.ROLLBACK_FAILED
            ag.page(
                root,
                f"rollback of {a.bad[:12]} FAILED; new risk held on every lane: "
                f"{doc.get('reason')}",
            )
        if not held:
            ag.page(root, f"rollback of {a.bad[:12]}: the new-risk hold could not be written")
    doc = {"step": a.cmd, "exit": code, **doc}
    ag.write_report(root, doc)
    print(json.dumps(doc, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
