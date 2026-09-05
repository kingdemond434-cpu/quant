"""Every certificate gathers forward evidence, and no sleeve stays blocked. On a clock.

WHY THIS EXISTS

A certificate that is not accruing forward evidence is worth nothing. It cannot cure a power
deficit, it cannot earn promotion authority, and it cannot be falsified -- it just sits, looking
like an asset on a dashboard while producing no information at all. Two different failures put
certificates in that state, and this heals both, at the CAUSE rather than the symptom.

FAILURE ONE -- BLOCKED SLEEVES. Measured 2026-08-29T13:16:54Z: all 34 live forward clocks in
`shadow_state.json` went `BLOCKED_SLEEVE_ERROR` at once, every one of them reading

    ModuleNotFoundError: No module named 'mt5desk.family_inputs'

The module was committed, matched HEAD, and was on the drift watchlist. It was ABSENT on the
trading box, and the drift healer scored absence the same as an unreachable box -- it skipped
both -- so a clean drift report was printed over a forward lane that had stopped dead. The whole
desk's forward evidence stopped for the one class of file the healer structurally could not see.

The lesson is not "ship that module". It is that a blocked sleeve names its own cause in
`last_error`, in a machine-readable form, and nothing was reading it. This reads it.

FIX THE CAUSE, NEVER THE STATUS. `shadow_forward` already clears `BLOCKED_SLEEVE_ERROR` by itself
the moment a sleeve evaluates end to end, so this NEVER writes sleeve status. It could: a loop
that reset every blocked row to ACTIVE would empty this report and change nothing underneath,
because the next pass would re-block on the same missing import while the ledger claimed health.
A fixer that can hide its own failure is worse than no fixer. So the only thing here that writes
is the shipping of a file the box is missing, and the proof is the box's own hash afterwards.

FAILURE TWO -- IDLE CERTIFICATES. A certificate can be perfectly enrollable and still have no
forward clock, because enrolment is a separate step that can silently no-op. Those never show up
as errors -- there is no row to be blocked -- so they are invisible to every check that reads
the ledger. This counts certificates against clocks and names the difference, which is the only
way an absent thing gets noticed.

WHAT IT WILL NOT DO. It does not promote, size, or arm anything, and it never edits the sleeve
registry. Getting evidence flowing is mechanical and safe to automate; deciding what to do with
that evidence is not, and mixing the two would put an unattended script on the money path.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "data" / "forward_lane_health.json"
SHADOW = ROOT / "desks" / "mt5" / "reports" / "shadow"
REMOTE = "contabo-mt5"

#: Ledgers holding forward clocks. Each is a different admission path into the same lane, and a
#: check that read only the main one would have missed three-quarters of the desk.
LEDGERS = ("shadow_state.json", "qquant_shadow_state.json",
           "scalp_shadow_state.json", "external_shadow_state.json")

#: Statuses that mean "this sleeve is not gathering evidence and something broke". RETIRED_* are
#: deliberately absent: a retired sleeve is a decision, not a fault, and healing it would be
#: re-animating something the desk chose to stop.
BLOCKED = ("BLOCKED_SLEEVE_ERROR", "BLOCKED_POWER_UNCURED", "BLOCKED_UNIVERSAL_GATES",
           # Written by the engine when a family's runtime inputs cannot be rebuilt. Distinct
           # from BLOCKED_SLEEVE_ERROR on purpose: that means "this raised", while this means
           # "this was reached and had nothing to run with" -- a wiring gap, and the two need
           # different fixes.
           "BLOCKED_INPUTS_UNAVAILABLE")

#: `ModuleNotFoundError: No module named 'x.y'` -- the one root cause that is unambiguous enough
#: to fix without a human, because the fix is "put the committed file where it belongs".
_MISSING_MODULE = re.compile(r"No module named ['\"]([\w.]+)['\"]")

#: Roots a desk module can live under, in the order a box import would find them.
_SEARCH_ROOTS = ("desks/mt5", "libs", ".")


def _run(cmd: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return r.returncode, (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return 124, ""


def _resolve_module(dotted: str) -> str | None:
    """Repo-relative path of a module named the way an importer on the box would name it.

    `mt5desk.family_inputs` is imported that way because the box puts `desks/mt5` on the path, so
    the dotted name is NOT the repo path and cannot be turned into one by string surgery alone.
    """
    tail = Path(*dotted.split(".")).with_suffix(".py")
    for root in _SEARCH_ROOTS:
        cand = ROOT / root / tail
        if cand.exists():
            return str(cand.relative_to(ROOT))
    hits = [p for p in ROOT.rglob(tail.name)
            if "__pycache__" not in p.parts and ".venv" not in p.parts
            and p.parts[-len(tail.parts):] == tail.parts]
    return str(hits[0].relative_to(ROOT)) if len(hits) == 1 else None


def _ship(rel: str) -> tuple[bool, str]:
    """Ship a file to the box, but ONLY the version HEAD agrees with.

    Same safety property as the drift healer, restated rather than imported loosely: this box has
    a replayer that reverts working-tree files to ancient copies, and a fixer that shipped
    whatever was on disk would propagate a trampled file straight onto the box that trades.
    """
    rc_l, local = _run(["git", "hash-object", str(ROOT / rel)])
    rc_h, head = _run(["git", "rev-parse", f"HEAD:{rel}"])
    if rc_l != 0 or rc_h != 0 or not local or not head:
        return False, f"{rel}: cannot hash locally or in HEAD -- not shipped"
    if local != head:
        return False, (f"{rel}: local copy differs from HEAD -- NOT shipped. Commit or restore it "
                       f"here first; shipping a trampled file is how the box got an ancient engine")
    rc, _ = _run(["scp", "-o", "ConnectTimeout=45", "-q",
                  str(ROOT / rel), f"{REMOTE}:C:/opt/quant/{rel}"], timeout=180)
    if rc != 0:
        return False, f"{rel}: scp failed (box unreachable?)"
    rc_r, out = _run(["ssh", "-o", "ConnectTimeout=25", REMOTE,
                      f"cd C:\\opt\\quant && git hash-object {rel}"])
    landed = (out.replace("\r", "").strip().splitlines() or [""])[-1].strip()
    if rc_r == 0 and landed == head:
        return True, f"{rel}: SHIPPED, box now matches HEAD ({head[:8]})"
    return False, f"{rel}: shipped but box reports {landed[:8] or 'nothing'} != HEAD {head[:8]}"


def _watchlist_gap(rels: set[str]) -> list[str]:
    """Modules this had to ship that the drift healer is not watching.

    Anything that went missing once will go missing again -- a box rebuild, a partial sync, a new
    module next week. Shipping it fixes today; naming the watchlist gap is what stops the repeat.
    """
    try:
        watch = (ROOT / "scripts" / "check_desk_module_drift.py").read_text("utf-8")
    except OSError:
        return sorted(rels)
    return sorted(r for r in rels if r not in watch)


def _engine_last_run() -> datetime | None:
    """Newest `last_attempt_at` anywhere -- when the forward engine last evaluated ANYTHING.

    This is the clock a stale error is measured against. There is no single "engine ran at"
    stamp, but any row it touched carries one, so the maximum across all rows is the engine's
    own heartbeat and needs no new artifact to maintain.
    """
    newest: datetime | None = None
    for name in LEDGERS:
        f = SHADOW / name
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = data.get("sleeves", data) if isinstance(data, dict) else {}
        for st in rows.values():
            if not isinstance(st, dict):
                continue
            t = _parse_ts(st.get("last_attempt_at"))
            if t and (newest is None or t > newest):
                newest = t
    return newest


def _blocked_rows() -> list[dict]:
    rows: list[dict] = []
    for name in LEDGERS:
        p = SHADOW / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key, st in data.items():
            if isinstance(st, dict) and st.get("status") in BLOCKED:
                rows.append({"ledger": name, "key": key,
                             "status": st.get("status"),
                             "error": str(st.get("last_error") or
                                          st.get("gate_reason") or "")[:200],
                             "at": st.get("last_error_at"),
                             "last_attempt_at": st.get("last_attempt_at")})
    return rows


def _error_is_stale(row: dict) -> bool:
    """True only when this same sleeve was attempted after the recorded error.

    Comparing a row with the book-wide newest attempt is invalid because sleeves are evaluated
    sequentially: every failing row except the last then looks stale during the very pass that
    produced its live error.  That bug prevented the healer from shipping a missing dependency
    shared by seven EURCHF clocks.
    """
    error_at = _parse_ts(row.get("at"))
    attempted_at = _parse_ts(row.get("last_attempt_at"))
    return bool(error_at and attempted_at and attempted_at > error_at)


#: A sleeve the engine has not touched in this long is not "accumulating", it is stopped. Two
#: hours spans the hourly cycle plus a slow sweep without flagging a merely late run.
_STALE_ATTEMPT_H = 2.0

#: An ACCUMULATING sleeve older than this with ZERO trades is not early, it is not firing.
#: Sleeves on this desk average ~8 trades per 12 days, so three days with none is well outside
#: the normal rate and worth naming rather than waiting out.
_SILENT_DAYS = 3


def _stalled_rows() -> list[dict]:
    """Sleeves that LOOK alive and are not: stale, silent, or accruing nothing.

    WHY THESE THREE, AND WHY THEY ARE NOT ERRORS. A blocked sleeve announces itself; these do
    not. `ACCUMULATING` at day 0 with no trades reads exactly like a healthy new sleeve, which is
    how three scalp rows sat at "day 0/14" for days while their clock was being restamped every
    cycle. A status that is indistinguishable from health is the one that needs a watchdog most,
    because nobody will ever go looking for it.

      STALE_SOURCE / stale attempt -- the engine stopped evaluating this row at all.
      SILENT        -- alive for days, zero fills: the signal is not firing or is being dropped.
      CLOCK_AHEAD   -- forward_start later than its own first trade (see check_forward_clock).

    Reported, never auto-reset. Each has a DIFFERENT cause -- a dead engine pass, a missing input,
    a broken signal, a restamped clock -- and the one shared response ("set it back to ACTIVE")
    would hide all four while fixing none.
    """
    now = datetime.now(tz=UTC)
    out: list[dict] = []
    for name in LEDGERS:
        f = SHADOW / name
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = data.get("sleeves", data) if isinstance(data, dict) else {}
        for key, st in rows.items():
            if not isinstance(st, dict):
                continue
            status = str(st.get("status") or "")
            if status.startswith("RETIRED") or status in ("KILL", "PROMOTED"):
                continue
            n = int(st.get("n") or 0)

            if st.get("bar_source_stale"):
                out.append({"ledger": name, "key": key, "kind": "STALE_SOURCE", "n": n,
                            "why": f"bar source {st.get('bar_source')} is stale; the row cannot "
                                   f"accrue honest forward evidence until it is fresh"})
                continue

            last = _parse_ts(st.get("last_attempt_at"))
            if last is not None:
                age_h = (now - last).total_seconds() / 3600.0
                if age_h > _STALE_ATTEMPT_H:
                    out.append({"ledger": name, "key": key, "kind": "STALE_ATTEMPT", "n": n,
                                "why": f"engine last evaluated this row {age_h:.1f}h ago; the "
                                       f"hourly cycle is not reaching it"})
                    continue

            start = _parse_ts(st.get("forward_start"))
            if n == 0 and start is not None:
                days = (now - start).days
                if days >= _SILENT_DAYS:
                    out.append({"ledger": name, "key": key, "kind": "SILENT", "n": 0,
                                "why": f"{days} days enrolled and ZERO trades -- the signal is "
                                       f"not firing or its fills are being dropped"})
    return out


def _parse_ts(v: object) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        d = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _tradeable(sym: str) -> tuple[bool, str]:
    """Can this desk ever place an order on `sym` and replay a clock on it?

    The SAME predicate gate 0 applies (`external_gauntlet.symbol_is_tradeable`), imported rather
    than restated so the two can never disagree about which symbols exist. Gate 0 stops NEW
    untradeable certificates; this names the ones minted before it.
    """
    try:
        sys.path.insert(0, str(ROOT / "desks" / "mt5" / "scripts"))
        from external_gauntlet import symbol_is_tradeable

        meta = json.loads((ROOT / "desks" / "mt5" / "data" / "universe" / "universe.json")
                          .read_text("utf-8"))
        return symbol_is_tradeable(sym, meta)
    except Exception as exc:
        # UNKNOWN IS NOT UNTRADEABLE. If the predicate cannot run, the certificate keeps its
        # place in the idle list rather than being quietly written off (L1.28a).
        return True, f"tradeability UNMEASURED ({type(exc).__name__})"


def _idle_certificates() -> dict:
    """Certificates that should have a forward clock and do not.

    USE THE PRODUCER'S OWN MAPPING. A certificate is named `external.XAUUSD.session_range_breakout`
    and its clock is keyed `XAUUSD.asia#rr=2.0_wb=12`; no string surgery turns one into the other,
    because the selector, the parameter signature and the family alias all come from admission's
    own logic. A first cut here compared the raw strings and reported 40 of 41 certificates idle
    when nearly all of them were running -- a false alarm that, on a clock, would have trained
    everyone to ignore this check.

    So this asks `shadow_admission` what runs it authorizes and keys them with its own `run_key`.
    The check is then exact, and it cannot drift from admission because it IS admission.
    """
    desk = ROOT / "desks" / "mt5"
    sys.path.insert(0, str(desk))
    try:
        from research.shadow_admission import authorized_runs, run_key
    except ImportError as exc:
        return {"error": f"cannot import shadow_admission: {exc}"}
    try:
        runs = authorized_runs(desk)
    except Exception as exc:                     # admission failing IS the finding
        return {"error": f"authorized_runs raised {type(exc).__name__}: {str(exc)[:120]}"}

    expected = {run_key(r): r for r in runs}
    clocked: set[str] = set()
    for name in LEDGERS:
        f = SHADOW / name
        if not f.exists():
            continue
        try:
            clocked |= set(json.loads(f.read_text("utf-8")))
        except (OSError, json.JSONDecodeError):
            continue

    # UNTRADEABLE IS NOT IDLE, and reporting it as idle is worse than not reporting it. Measured
    # 2026-09-02: eight certificates on AFG and AFL -- symbols absent from the universe registry
    # with no H1 parquet on the box -- were named IDLE every twenty minutes, for weeks. There is
    # no repair for them: no clock can ever enrol a symbol the broker does not quote and no
    # replay can run on bars that do not exist (L1.49, a gate that cannot be cashed is not a
    # survivor). A permanent finding on a rolling health report is how a reader learns to skip
    # the row, which then costs the real ones. Named separately and counted, never mixed in.
    untradeable: dict[str, str] = {}
    idle_real: list[str] = []
    for key in sorted(k for k in expected if k not in clocked):
        if str(key).startswith("scalp."):
            continue                      # accrues on scalp_shadow's clock, not this lane's
        sym = str(key).split(".")[0].split("#")[0]
        ok, why = _tradeable(sym)
        if ok:
            idle_real.append(key)
        else:
            untradeable[key] = why
    return {"authorized_runs": len(expected),
            "with_clock": len(expected) - len(idle_real) - len(untradeable),
            "idle": idle_real[:40], "idle_count": len(idle_real),
            "untradeable": dict(list(untradeable.items())[:40]),
            "untradeable_count": len(untradeable)}


def main() -> int:
    now = datetime.now(tz=UTC)
    rows = _blocked_rows()
    report: dict = {"checked_at": now.isoformat(timespec="seconds"),
                    "blocked_total": len(rows), "healed": [], "unfixable": [],
                    "watchlist_gap": [], "idle": {}, "stalled": [], "stale_errors": []}

    print(f"FORWARD LANE {now.isoformat(timespec='seconds')}")
    print(f"  blocked sleeves: {len(rows)}")

    # One missing module blocks every sleeve that needs it, so fix per CAUSE, not per sleeve --
    # 34 rows here were 34 copies of one defect, and shipping once clears all of them.
    # A STALE ERROR IS NOT A LIVE CAUSE, and treating it as one is worse than ignoring it.
    # Measured 2026-08-29T20:42: seven EURCHF.discovered rows carried
    # `ModuleNotFoundError: mt5desk.family_inputs` stamped 13:46:59 with last_attempt_at NULL,
    # while the module was verifiably importable on the box (`OK C:\opt\quant\...`). This healer
    # re-shipped a correct module on every run for hours, reported HEALED each time, and the real
    # cause -- the engine reaching those rows and skipping them without recording an attempt --
    # stayed completely hidden behind a fixed-looking symptom.
    #
    # An error older than the engine's last pass describes a world that no longer exists.
    engine_run = _engine_last_run()
    live_rows, stale_rows = [], []
    for r in rows:
        if _error_is_stale(r):
            observed = engine_run or _parse_ts(r.get("last_attempt_at"))
            stale_rows.append({**r, "engine_ran_at": (
                observed.isoformat(timespec="seconds") if observed else None
            )})
        else:
            live_rows.append(r)
    report["stale_errors"] = stale_rows
    if stale_rows:
        print(f"  STALE ({len(stale_rows)}) -- error predates the engine's last pass "
              f"({engine_run.isoformat(timespec='seconds') if engine_run else '?'}), so it does "
              f"NOT describe the current cause. Not acted on; the row is being skipped without "
              f"recording an attempt, which is the real defect:")
        for r in stale_rows[:5]:
            print(f"    {r['key'][:46]:48s} err@{str(r.get('at'))[:19]}")
    rows = live_rows

    wanted: dict[str, list[str]] = {}
    for r in rows:
        m = _MISSING_MODULE.search(r["error"])
        if m:
            wanted.setdefault(m.group(1), []).append(r["key"])
        else:
            report["unfixable"].append({"key": r["key"], "status": r["status"],
                                        "error": r["error"]})

    shipped: set[str] = set()
    for dotted, keys in sorted(wanted.items()):
        rel = _resolve_module(dotted)
        if rel is None:
            report["unfixable"].append(
                {"key": f"{len(keys)} sleeves", "status": "MISSING_MODULE",
                 "error": f"'{dotted}' blocks {len(keys)} sleeves and resolves to no committed "
                          f"file here -- it was never written, or lives outside the search roots"})
            print(f"  UNRESOLVED {dotted}: blocks {len(keys)} sleeves, no such file in this repo")
            continue
        ok, detail = _ship(rel)
        print(f"  {'HEALED ' if ok else 'FAILED '}{dotted} ({len(keys)} sleeves): {detail}")
        if ok:
            shipped.add(rel)
            report["healed"].append({"module": dotted, "path": rel, "sleeves": len(keys)})
        else:
            report["unfixable"].append({"key": f"{len(keys)} sleeves",
                                        "status": "SHIP_FAILED", "error": detail})

    if shipped:
        gap = _watchlist_gap(shipped)
        report["watchlist_gap"] = gap
        if gap:
            print("\n  WATCHLIST GAP -- shipped but unwatched, so free to go missing again:")
            for rel in gap:
                print(f"    {rel}  -> add to MODULES in scripts/check_desk_module_drift.py")

    stalled = _stalled_rows()
    report["stalled"] = stalled
    if stalled:
        from collections import Counter
        kinds = Counter(r["kind"] for r in stalled)
        print(f"\n  STALLED ({len(stalled)}) -- alive-looking rows that are not accruing: "
              f"{dict(kinds)}")
        for r in stalled[:10]:
            print(f"    {r['kind']:14s} {r['key'][:40]:42s} {r['why'][:70]}")

    report["idle"] = _idle_certificates()
    idle_n = report["idle"].get("idle_count")
    if idle_n is not None:
        print(f"\n  authorized runs: {report['idle']['authorized_runs']}, "
              f"with a forward clock: {report['idle']['with_clock']}, idle: {idle_n}")
        for n in report["idle"]["idle"][:10]:
            print(f"    IDLE {n} -- authorized to run forward, no clock exists")
    unt = report["idle"].get("untradeable_count") or 0
    if unt:
        print(f"\n  UNTRADEABLE ({unt}) -- certified on a symbol this desk cannot trade or "
              f"replay. Not idle and not repairable; gate 0 now refuses these at admission:")
        for k, why in list(report["idle"]["untradeable"].items())[:6]:
            print(f"    {k[:52]:54s} {why[:70]}")

    if report["unfixable"]:
        print(f"\n  NOT AUTO-FIXABLE ({len(report['unfixable'])}) -- each needs a named cause, "
              f"and is left blocked rather than reset, so it cannot be mistaken for healthy:")
        for u in report["unfixable"][:8]:
            print(f"    {u['key']}: {u['error'][:110]}")

    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    # Idle certificates are a real finding but not this script's to fix, so they do not fail it;
    # a sleeve still blocked after a heal attempt is, because it means the lane is still stopped.
    return 1 if (report["unfixable"] or report["stalled"]
                 or report["stale_errors"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
