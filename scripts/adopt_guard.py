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
    python scripts/adopt_guard.py drift --run <id>            # 0 saved/none, 10 could not save
    python scripts/adopt_guard.py canary                      # 0 pass/wait/none, 12 roll back
    python scripts/adopt_guard.py canary-clear --release <sha>  # after that rollback: 0

THE ADOPT CANARY (libs/ops/adopt_canary). `health --arm-canary --release <sha> --prev <sha>` puts
the canary hold up BEFORE it lifts the guard's own hold, so new code never opens a position
outside the canary window(s) until one has sent a clean order on it. `canary` (first thing in
every Adopt-And-Seal run) lifts it on PASS, keeps it on WAIT, lifts it into the watch and pages on
EXPIRED (a window with no armed send in 7 days is never armed: straight to the watch), and on
FAIL -- or a post-lift SPIKE -- exits 12 with `rollback_to` and `bad`; the caller rolls back with
the hold standing and then calls `canary-clear`.

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
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import adopt_canary, new_risk_hold  # noqa: E402
from libs.ops import adopt_guard as ag  # noqa: E402

#: A hold of ours still up after this long, on a release that is still unhealthy, is a run that
#: died mid-adoption or a rollback nobody has fixed: page instead of waiting another hour.
HEAL_PAGE_AFTER_S = 90 * 60


def _since(v: str) -> datetime:
    t = datetime.fromisoformat(v)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


#: e8_gold's windows (GOLD_WINDOWS): the published budget is read for each.
WINDOWS = ("asia", "london_am", "afternoon")


def _caps(root: Path) -> dict[str, float | None]:
    return {w: adopt_canary.published_frac(root, w)[0] for w in WINDOWS}


def _arm(root: Path, release: str, prev: str, doc: dict) -> tuple[int, dict]:
    pol = ag.load_policy(root)
    now = datetime.now(UTC)
    # A CANARY THAT CANNOT SING (Audit should-fix 1): a window with no armed send in 7 days would
    # hold every lane until someone noticed. Then the new code goes straight to the watch.
    if not adopt_canary.recently_armed(adopt_canary.rows(root), pol["canary_allow"], now):
        adopt_canary.save_state(root, {"lifted_at": now.isoformat(), "release_id": release,
                                       "prev_head": prev, "mode": "watch_only"})
        ag.page(root, f"canary windows {pol['canary_allow']} sent nothing armed in "
                      f"{adopt_canary.RECENT_DAYS} days: {release[:12]} goes straight to the "
                      f"{pol['canary_watch_h']}h post-adoption watch")
        return ag.GO, {**doc, "canary_armed": False, "canary_mode": "watch_only"}
    deadline = now + timedelta(hours=float(pol["canary_deadline_h"]))
    ok = new_risk_hold.place_canary(
        f"new code {release[:12]} trades only the canary window(s) until one sends cleanly",
        release_id=release, allow=list(pol["canary_allow"]), deadline=deadline,
        prev_head=prev, root=root)
    if not ok:
        return ag.UNHEALTHY, {**doc, "decision": "UNHEALTHY",
                              "reason": "the canary hold could not be written"}
    # a new canary ends the previous release's post-lift watch
    adopt_canary.save_state(root, {"armed_at": datetime.now(UTC).isoformat(),
                                   "release_id": release})
    return ag.GO, {**doc, "canary_armed": True, "canary_deadline": deadline.isoformat()}


def _emit(root: Path, step: str, code: int, doc: dict) -> int:
    doc = {"step": step, "exit": code, **doc}
    ag.write_report(root, doc)
    print(json.dumps(doc, sort_keys=True, default=str))
    return code


def _canary(root: Path) -> int:
    now = datetime.now(UTC)
    try:
        hold = new_risk_hold.canary(root)
        if hold == {}:
            ag.page(root, "the canary hold is unreadable; new risk stays held until it is fixed")
            return _emit(root, "canary", ag.GO, {"decision": "CANARY_UNREADABLE"})
        if hold is None:
            st = adopt_canary.load_state(root)
            lifted = adopt_canary._ts(st.get("lifted_at"))
            if lifted is None or not st.get("prev_head"):
                return _emit(root, "canary", ag.GO, {"decision": "NO_CANARY"})
            hours = float(ag.load_policy(root)["canary_watch_h"])
            w = adopt_canary.watch(lifted, adopt_canary.rows(root), now, hours,
                                   caps=_caps(root))
            if w["verdict"] != "SPIKE":
                return _emit(root, "canary", ag.GO, {"decision": f"WATCH_{w['verdict']}", **w})
            ag.page(root, f"after the canary lift, {st.get('release_id', '?')[:12]} shows "
                          f"{w['rejects']} rejects (baseline {w['baseline']}) and "
                          f"{len(w['bound'])} bound failure(s): rolling back")
            return _emit(root, "canary", ag.ROLLBACK_FAILED,
                         {"decision": "CANARY_SPIKE", "rollback_to": st["prev_head"],
                          "bad": st.get("release_id"), **w})
        v = adopt_canary.judge(hold, adopt_canary.rows(root), now, caps=_caps(root))
        if v["verdict"] == adopt_canary.PASS:
            lifted = new_risk_hold.lift(by=new_risk_hold.CANARY_BY, root=root)
            if lifted:
                adopt_canary.save_state(root, {"lifted_at": now.isoformat(),
                                               "release_id": hold.get("release_id"),
                                               "prev_head": hold.get("prev_head")})
            return _emit(root, "canary", ag.GO,
                         {"decision": "CANARY_PASS" if lifted else "CANARY_PASS_LIFT_FAILED", **v})
        if v["verdict"] == adopt_canary.FAIL:
            ag.page(root, f"canary FAILED on {str(hold.get('release_id'))[:12]}: "
                          f"{str(v.get('failed') or v.get('why'))[:300]}; rolling back")
            return _emit(root, "canary", ag.ROLLBACK_FAILED,
                         {"decision": "CANARY_FAIL", "rollback_to": hold.get("prev_head"),
                          "bad": hold.get("release_id"), **v})
        if v["verdict"] == adopt_canary.EXPIRED:
            # silence proves nothing either way: lift into the watch, which still rolls back
            lifted = new_risk_hold.lift(by=new_risk_hold.CANARY_BY, root=root)
            if lifted:
                adopt_canary.save_state(root, {"lifted_at": now.isoformat(),
                                               "release_id": hold.get("release_id"),
                                               "prev_head": hold.get("prev_head"),
                                               "mode": "expired_watch"})
            ag.page(root, f"no canary send on {str(hold.get('release_id'))[:12]} by its deadline; "
                          + ("lifted into the post-adoption watch" if lifted
                             else "the canary hold could NOT be lifted; every lane held"))
            # not 12: there is nothing to roll back to, only a hold that would not come down
            return _emit(root, "canary", ag.GO if lifted else ag.ERROR,
                         {"decision": "CANARY_EXPIRED_WATCH" if lifted
                          else "CANARY_EXPIRED_LIFT_FAILED", **v})
        return _emit(root, "canary", ag.GO, {"decision": "CANARY_WAIT", **v})
    except Exception as exc:  # fail closed: the hold stays, nothing is adopted, and say why
        ag.page(root, f"the canary check failed ({type(exc).__name__}: {exc}); not adopting")
        return _emit(root, "canary", ag.ERROR,
                     {"decision": "ERROR", "reason": f"{type(exc).__name__}: {exc}"})


def _canary_clear(root: Path, release: str) -> int:
    """After a canary rollback succeeded: the release it guarded is gone, so its hold goes."""
    hold = new_risk_hold.canary(root)
    if hold and hold.get("release_id") == release:
        ok = new_risk_hold.lift(by=new_risk_hold.CANARY_BY, root=root)
        decision = "CANARY_CLEARED" if ok else "CANARY_CLEAR_FAILED"
        if not ok:
            ag.page(root, f"the canary hold for rolled-back {release[:12]} could not be lifted; "
                          "every lane stays held")
    else:
        ok, decision = True, "NOT_THIS_RELEASE"
    adopt_canary.save_state(root, {"cleared_at": datetime.now(UTC).isoformat(),
                                   "release_id": release})
    return _emit(root, "canary-clear", ag.GO if ok else ag.ROLLBACK_FAILED, {"decision": decision})


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
    h.add_argument("--arm-canary", action="store_true")
    h.add_argument("--release")
    h.add_argument("--prev")
    dr = sub.add_parser("drift")
    dr.add_argument("--run", required=True)
    sub.add_parser("canary")
    cc = sub.add_parser("canary-clear")
    cc.add_argument("--release", required=True)
    a = ap.parse_args(argv)
    root = Path(a.root)
    if a.cmd == "health" and a.arm_canary and not (
        a.release and a.prev and ag.HEX40.match(a.release) and ag.HEX40.match(a.prev)
    ):
        ap.error("--arm-canary needs --release and --prev as 40-hex shas")
    if a.cmd == "canary":
        return _canary(root)
    if a.cmd == "canary-clear":
        return _canary_clear(root, a.release)

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
        elif a.cmd == "drift":
            code, doc = ag.drift_evidence(root, a.run)
            if code != ag.GO:
                ag.page(root, f"box code drift could not be saved as evidence; not adopting: "
                              f"{doc.get('reason')}")
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
            # THE CANARY GOES UP BEFORE OUR HOLD COMES DOWN: no instant where new code may open
            # outside the canary window. It cannot be written -> unhealthy (the caller rolls back).
            if code == ag.GO and a.cmd == "health" and a.arm_canary:
                code, doc = _arm(root, a.release, a.prev, doc)
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
