"""THE INTEL FEED, PRODUCED ON THE BOX (2026-11-03): hel8's two hourly producers, as one intel leg.

WHY. The Linux VPS hel8 produced the intelligence feed hourly -- `side_channels/seed_miners.py`
at :22 and `research/hourly_discovery.py --budget-s 2700` at :35 -- and shipped it on the
data-only branch `intel-ship/send`. Its last ship was 2026-11-03T02:50Z; it is silent now. The
box's consumers read `desks/mt5/data/intelligence` directly (`local_converter.SOURCES`), so this
leg writes the feed straight there: no ship, no git, no VPS.

WHERE IT RUNS. `intel_feed` is a leg of the `intel` department (MT5-Dept-Intel, a 24/7 resident
at BELOW_NORMAL), beside world_crawler and deep_forest. No new scheduled task, no admin step. The
money legs live on MT5-HourlyCore and the gateway's own resident, so nothing here ever runs ahead
of, or inside, a trading leg. The leg gates itself to hel8's cadence: it starts at most once per
MIN_INTERVAL_S, so a fast intel pass returns NOT_DUE in milliseconds.

WHAT A PASS DOES, inside BUDGET_S (hourly_cycle's LEG_BUDGET_SEC cap sits above it):

  1. seed_miners, in a child killed at SEED_BOUND_S, behind `scripts/memory_guard.py` (hel8's
     600 MB cap). The child installs `box_rails` FIRST: an honest User-Agent naming the project's
     research crawler, robots.txt honoured for `*`, the crawler's token and ClaudeBot on EVERY
     source, and no contact at all with a host the VPS walls (`seed_miners.SOURCE_WALLS`). The
     miner's own browser-string header never reaches the wire from this box.
  2. hourly_discovery over the organs NOTHING ELSE ON THE BOX ALREADY CLOCKS, with whatever budget
     is left. An organ named by EITHER box roster is excluded -- hourly_cycle (world_crawler,
     deep_forest, alpha_evolution, ...) and daily_cycle (its proposers, world miners and
     fetch_futures_curves) -- read from the two files' own source, so no organ ever has two
     non-atomic writers and an hourly UNMEASURED never overwrites a daily MEASURED verdict
     (audit HOLD on 84e1e474b). An unreadable roster excludes the pinned fallback: fail closed.
     The same rails reach every organ child through the environment (`hourly_discovery
     --organ` installs them when QUANT_BOX_RAILS=1).

ONE PASS AT A TIME. The cadence check runs under an O_EXCL lease (`data/locks/
box_intel_feed.lease`), so two concurrent intel passes can never both start the feed; a lease
older than LEASE_STALE_S belongs to a killed pass and is taken over, and says so.

ONLY ON THE INTEL DEPARTMENT'S CLOCK. hourly_cycle pins the leg to HOURLY_PLAN=dept:intel
(`DEPT_ONLY_LEGS`): an `all`, `heavy` or `core` pass skips it, so it can never sit inline ahead
of release_identity, burn_in or fill_recorder.

A REFUSED SOURCE IS NAMED, NEVER SILENT. Every rail refusal is grouped by host in the report's
`refused_sources`, with a `missed_growth` line per host: a source the box may not fetch is dark
by policy, and the growth it would have fed is a recorded cost.

CPU. Both children are spawned BELOW_NORMAL explicitly -- the miners' class, which is the class
`judge_priority` levels the judge to -- and NO affinity is set: miners are never confined to
fewer cores, and the judge's share is protected by priority parity, not by pinning
(test_judge_cpu_fair_share). One child at a time, so the leg costs about one core.

NO PAID CALLS. QUANT_PROPOSER_SEAT=0 in both children: the optional external-model seat stays
dark on this path, so the leg never spends on a model API. Public data only; no login, no key.

Writes `reports/BOX_INTEL_FEED.json` (what this pass did) and keeps its clock in
`data/box_intel_feed_state.json`. The FEED's freshness is judged on what the producers write --
`reports/HOURLY_DISCOVERY.json` and `data/intelligence/seed_miners_state.json` -- by
`ops/organ_contract.py` and `scripts/box_heartbeat.py`, never by this file's exit code.

    python side_channels/box_intel_feed.py [--budget-s 2040] [--force] [--dry-run]
    python side_channels/box_intel_feed.py --child seed          # child: seed_miners under rails
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parent.parent
for _p in (str(HERE), str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = BASE / "reports" / "BOX_INTEL_FEED.json"
STATE = BASE / "data" / "box_intel_feed_state.json"
HOURLY_CYCLE = BASE / "research" / "hourly_cycle.py"
DAILY_CYCLE = BASE / "research" / "daily_cycle.py"
ROSTERS: tuple[Path, ...] = (HOURLY_CYCLE, DAILY_CYCLE)
LEASE = BASE / "data" / "locks" / "box_intel_feed.lease"
DISCOVERY = BASE / "research" / "hourly_discovery.py"
MEMORY_GUARD = ROOT / "scripts" / "memory_guard.py"

#: The leg's own wall budget. hourly_cycle's LEG_BUDGET_SEC["intel_feed"] (2,400 s) sits above it
#: plus the cycle's write margin, so the cycle never kills this before it writes its report.
BUDGET_S = 2040.0
#: hel8's timers fired hourly; a pass starts at most this often (five minutes of slack for a pass
#: that starts a little early on the next resident loop).
MIN_INTERVAL_S = 3300.0
#: seed_miners: request caps and 20 s timeouts bound most sources; regional_survivors carries its
#: own 900 s budget (`regional_survivor_hunters.RUN_BUDGET_S`).
SEED_BOUND_S = 1080.0
SEED_NEED_MB = 600
MEMORY_WAIT_S = 120
EX_TEMPFAIL = 75
#: hourly_discovery kills an organ at its budget plus 120 s grace, so a pass can run that far past
#: its total; the child bound adds that grace and a write margin on top of the budget given.
DISCOVERY_GRACE_S = 120.0
WRITE_MARGIN_S = 60.0
#: Below this, a discovery pass would floor every organ at 60 s and finish nothing.
MIN_DISCOVERY_S = 300.0
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
RESULT_PREFIX = "INTEL_FEED_RESULT "
REFUSALS_SHOWN = 10

#: The organs the two box rosters run, if a roster cannot be read. Kept in step with the live
#: reading by test_box_intel_feed. hourly_cycle legs first, then daily_cycle's.
BOX_OWNED_FALLBACK: frozenset[str] = frozenset({
    "world_crawler", "deep_forest_miner", "acquire_datasets", "weak_signal_compiler",
    "alpha_evolution", "cross_asset_graph", "world_causal_graph", "execution_twin",
    "factor_model_coevolution",
    "plumbing_miner", "transition_alpha", "fund_playbook", "microstructure_miner",
    "style_premia_sweep", "anomaly_factory", "tail_alpha_search", "survivor_distiller",
    "repo_miner", "data_prospector", "fetch_futures_curves",
})
#: A kill of the leg at its cycle cap (2,400 s) leaves its lease behind; past this it is stale.
LEASE_STALE_S = 3000.0

#: Seed sources the box never runs, whatever the rails allow. `regional_survivors` answers a
#: 403 by retrying the listing on sibling hosts with a Referer borrowed from the site root
#: (regional_survivor_hunters.py, its "403" recovery). That is a way around a server's refusal,
#: and the rails can't see it: each retry is a fresh, allowed host. It stays off the box until
#: that recovery becomes a hard stop (queue row 305); removing a name here is the only switch.
BOX_EXCLUDED_SEEDS: frozenset[str] = frozenset({"regional_survivors"})

Runner = Callable[[list[str], float, dict[str, str]], tuple[int | None, str]]


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(p: Path, doc: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _iso_ts(v: Any) -> float | None:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def _named_in(text: str, organ: str) -> bool:
    """Does a roster's source run `organ`? A quoted name (a `_producer` leg, a daily proposer
    tuple, an `__import__` roster), an import, or a script path. Over-matching only ever
    EXCLUDES an organ here, which is the safe direction: it still runs on the roster naming it."""
    o = re.escape(organ)
    return bool(re.search(rf'["\']{o}["\']|\bimport {o}\b|\bfrom {o} import\b|/{o}\.py\b',
                          text))


def box_owned_organs(organs: list[str] | None = None,
                     rosters: tuple[Path, ...] = ROSTERS) -> tuple[frozenset[str], str]:
    """(organs any box roster already runs, basis). An unreadable roster adds the fallback."""
    if organs is None:
        import hourly_discovery
        organs = list(hourly_discovery.ORGANS)
    owned: set[str] = set()
    basis: list[str] = []
    for roster in rosters:
        try:
            text = roster.read_text(encoding="utf-8")
        except OSError as exc:
            owned |= BOX_OWNED_FALLBACK
            basis.append(f"{roster.name} unreadable ({type(exc).__name__}): fallback")
            continue
        hit = {o for o in organs if _named_in(text, o)}
        owned |= hit
        basis.append(f"{roster.name}: {len(hit)}")
    return frozenset(owned), "rosters " + "; ".join(basis)


def discovery_organs(rosters: tuple[Path, ...] = ROSTERS) -> tuple[list[str], list[str], str]:
    """(organs this leg runs, organs excluded because the box already clocks them, basis)."""
    import hourly_discovery
    names = list(hourly_discovery.ORGANS)
    owned, basis = box_owned_organs(names, rosters)
    return ([n for n in names if n not in owned], [n for n in names if n in owned], basis)


#: lease path -> the token this process wrote into it. Release unlinks only a lease holding it.
_TOKENS: dict[str, str] = {}


def take_lease(path: Path | None = None, now: float | None = None,
               stale_s: float = LEASE_STALE_S) -> tuple[bool, str]:
    """O_EXCL lease: (held_by_us, why). A lease older than `stale_s` is a killed pass's.

    A STALE LEASE IS RENAMED, NEVER UNLINKED (audit of ebdc349e9). Two passes that both see it
    stale would each unlink it, and the second could delete the first's FRESH lease. Here each
    renames it to its own unique tombstone: only one rename can succeed, and only the pass whose
    rename did may try the O_EXCL create. A tombstone that turns out fresh -- another pass's new
    lease, renamed after that pass took over -- is put back (os.link, which never overwrites)
    and this pass stands down."""
    import uuid
    p = path or LEASE
    now = time.time() if now is None else now
    p.parent.mkdir(parents=True, exist_ok=True)
    why = "lease taken"
    for _attempt in range(2):
        try:
            fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = now - p.stat().st_mtime
            except OSError:
                continue  # released between the two calls: try once more
            if age < stale_s:
                return False, f"another pass holds the lease ({age:.0f}s old)"
            tomb = p.with_name(f"{p.name}.stale.{os.getpid()}.{uuid.uuid4().hex}")
            try:
                os.rename(p, tomb)
            except OSError:
                continue  # another pass renamed it first: its lease, if any, wins the create
            try:
                tage = now - tomb.stat().st_mtime
            except OSError:
                tage = stale_s
            if tage < stale_s:
                with contextlib.suppress(OSError):
                    os.link(tomb, p)
                with contextlib.suppress(OSError):
                    tomb.unlink()
                return False, "another pass took over the stale lease first"
            with contextlib.suppress(OSError):
                tomb.unlink()
            why = f"took over a stale lease ({age:.0f}s old, over {stale_s:.0f}s)"
            continue
        token = uuid.uuid4().hex
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"pid": os.getpid(), "lease_id": token, "at": _now_iso()}))
        _TOKENS[str(p)] = token
        return True, why
    return False, "the lease could not be taken"


def release_lease(path: Path | None = None) -> bool:
    """Unlink the lease only when it still holds OUR token; True when it was ours and removed.
    A lease another pass took over after ours went stale is never deleted by our finally."""
    p = path or LEASE
    token = _TOKENS.pop(str(p), None)
    if token is None:
        return False
    try:
        held = json.loads(p.read_text(encoding="utf-8")).get("lease_id")
    except (OSError, ValueError, AttributeError):
        return False
    if held != token:
        return False
    with contextlib.suppress(OSError):
        p.unlink()
        return True
    return False


def refused_by_host(refused: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """({host: {n, why}}, missed_growth lines): every refusal named, never a silent zero."""
    from urllib.parse import urlsplit
    hosts: dict[str, dict[str, Any]] = {}
    for r in refused:
        h = urlsplit(str(r.get("url", ""))).hostname or "?"
        e = hosts.setdefault(h, {"n": 0, "why": str(r.get("why", ""))[:200]})
        e["n"] += 1
    lines = [f"{h}: {e['n']} request(s) refused by the box rails ({e['why']}); this source is "
             f"dark on the box by policy, and whatever it would have fed is not mined here"
             for h, e in sorted(hosts.items())]
    return hosts, lines


def due(state: dict[str, Any], now: float | None = None,
        interval_s: float = MIN_INTERVAL_S) -> tuple[bool, str]:
    now = time.time() if now is None else now
    last = _iso_ts(state.get("last_started_at"))
    if last is None:
        return True, "never started on this box"
    if last > now + 300:
        return True, "last start is dated in the future: a clock defect, not freshness"
    age = now - last
    if age >= interval_s:
        return True, f"last start {age / 60:.0f} min ago"
    return False, f"last start {age / 60:.0f} min ago, under the {interval_s / 60:.0f} min cadence"


def child_env(log: str, base: dict[str, str] | None = None) -> dict[str, str]:
    """The children's environment: the rails on, their refusal log, the paid seat off."""
    env = dict(os.environ if base is None else base)
    env["QUANT_BOX_RAILS"] = "1"
    env["QUANT_BOX_RAILS_LOG"] = log
    env["QUANT_PROPOSER_SEAT"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def popen_kwargs() -> dict[str, Any]:
    """BELOW_NORMAL on Windows, explicitly (the miners' class). No affinity, anywhere."""
    return {"creationflags": BELOW_NORMAL_PRIORITY_CLASS} if sys.platform == "win32" else {}


def _default_runner(cmd: list[str], timeout_s: float,
                    env: dict[str, str]) -> tuple[int | None, str]:
    try:
        from libs.ops.proctree import run as _run
    except Exception:
        _run = subprocess.run  # type: ignore[assignment]
    try:
        r = _run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False,
                 cwd=str(BASE), env=env, **popen_kwargs())
    except subprocess.TimeoutExpired:
        return None, ""
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-16000:]


def seed_cmd() -> list[str]:
    inner = [sys.executable, "-u", str(Path(__file__).resolve()), "--child", "seed"]
    if MEMORY_GUARD.exists():
        return [sys.executable, str(MEMORY_GUARD), "--label", "box_intel_feed:seed_miners",
                "--need-mb", str(SEED_NEED_MB), "--max-wait-s", str(MEMORY_WAIT_S), "--", *inner]
    return inner


def discovery_cmd(budget_s: float, organs: list[str]) -> list[str]:
    return [sys.executable, "-u", str(DISCOVERY), "--budget-s", f"{budget_s:.0f}",
            "--only", ",".join(organs)]


def _parse(tail: str) -> dict[str, Any]:
    for line in reversed(tail.splitlines()):
        if line.startswith(RESULT_PREFIX):
            with contextlib.suppress(ValueError):
                d = json.loads(line[len(RESULT_PREFIX):])
                return d if isinstance(d, dict) else {}
            return {}
    return {}


def _status(rc: int | None, ok_rcs: tuple[int, ...] = (0,)) -> str:
    if rc is None:
        return "KILLED_AT_BOUND"
    if rc == EX_TEMPFAIL:
        return "DEFERRED_MEMORY"
    return "OK" if rc in ok_rcs else "FAILED"


def _discovery_summary(path: Path) -> dict[str, Any]:
    d = _read(path)
    organs = d.get("organs") if isinstance(d.get("organs"), dict) else {}
    return {"at": d.get("at"), "ok": d.get("ok"), "failed": d.get("failed"),
            "deferred": d.get("deferred"), "spent_s": d.get("spent_s"),
            "statuses": {n: (r or {}).get("status") for n, r in organs.items()}}


def run_pass(budget_s: float = BUDGET_S, *, runner: Runner | None = None,
             now: float | None = None, force: bool = False, write: bool = True,
             rosters: tuple[Path, ...] = ROSTERS) -> dict[str, Any]:
    held, lease_why = take_lease(now=now)
    if not held:
        return {"status": "LEASE_HELD", "why": lease_why}
    try:
        state = _read(STATE)
        ok, why = due(state, now)
        if not ok and not force:
            # NOT_DUE writes nothing: the report keeps saying what the last real pass did.
            return {"status": "NOT_DUE", "why": why}
        rep = _pass(state, why, budget_s, runner or _default_runner, write, rosters)
        rep["lease"] = lease_why
        if write:
            _write(REPORT, rep)
        return rep
    finally:
        release_lease()


def _pass(state: dict[str, Any], why: str, budget_s: float, runner: Runner, write: bool,
          rosters: tuple[Path, ...]) -> dict[str, Any]:
    t0 = time.monotonic()
    state["last_started_at"] = _now_iso()
    if write:
        _write(STATE, state)
    fd, log = tempfile.mkstemp(prefix="box_intel_feed_rails_", suffix=".jsonl")
    os.close(fd)
    env = child_env(log)
    rep: dict[str, Any] = {"at": state["last_started_at"], "due_because": why,
                           "budget_s": budget_s,
                           "cpu": {"priority": "BELOW_NORMAL", "affinity": None,
                                   "why": "the miners' class; judge_priority levels the judge to "
                                          "it; miners are never confined to fewer cores"},
                           "proposer_seat": "off (QUANT_PROPOSER_SEAT=0): no model API spend"}
    try:
        # 1. seed_miners under the rails
        s0 = time.monotonic()
        rc, tail = runner(seed_cmd(), SEED_BOUND_S, env)
        res = _parse(tail)
        seed = {"status": _status(rc), "rc": rc, "wall_s": round(time.monotonic() - s0, 1),
                "bound_s": SEED_BOUND_S, "sources": res.get("sources"), "rows": res.get("rows"),
                "tail": "" if res else tail[-400:]}
        rep["seed_miners"] = seed
        # 2. hourly_discovery over the organs nothing else on the box clocks
        organs, excluded, basis = discovery_organs(rosters)
        left = budget_s - (time.monotonic() - t0)
        disc_budget = left - DISCOVERY_GRACE_S - WRITE_MARGIN_S
        disc: dict[str, Any] = {"organs": organs, "excluded_box_owned": excluded,
                                "excluded_basis": basis}
        if not organs:
            disc["status"] = "NOTHING_TO_RUN"
        elif disc_budget < MIN_DISCOVERY_S:
            disc.update({"status": "DEFERRED_NO_TIME", "left_s": round(left)})
        else:
            d0 = time.monotonic()
            bound = disc_budget + DISCOVERY_GRACE_S + WRITE_MARGIN_S
            # hourly_discovery exits 1 when any organ failed; the pass itself still ran and wrote
            rc, tail = runner(discovery_cmd(disc_budget, organs), bound, env)
            disc.update({"status": _status(rc, (0, 1)), "rc": rc,
                         "wall_s": round(time.monotonic() - d0, 1),
                         "budget_s": round(disc_budget), "bound_s": round(bound),
                         "report": _discovery_summary(BASE / "reports" / "HOURLY_DISCOVERY.json"),
                         "tail": tail[-400:] if rc not in (0, 1) else ""})
        rep["discovery"] = disc
    finally:
        import box_rails
        logged = box_rails.logged_refusals(log)
        # robots signals are LABELS (LAWS §5e): the fetch went ahead; they are reported, never
        # counted as refused ground.
        refused = [r for r in logged if not r.get("label")]
        labelled = [r for r in logged if r.get("label")]
        with contextlib.suppress(OSError):
            os.unlink(log)
    hosts, missed = refused_by_host(refused)
    rep["refused_sources"] = hosts
    rep["missed_growth"] = missed
    rep["rails"] = {"user_agent": box_rails.USER_AGENT,
                    "robots_tokens": list(box_rails.ROBOTS_TOKENS),
                    "refused_n": len(refused),
                    "refused": [{"url": str(r.get("url", ""))[:150],
                                 "why": str(r.get("why", ""))[:150]}
                                for r in refused[:REFUSALS_SHOWN]],
                    "robots_labelled_n": len(labelled),
                    "robots_labelled_hosts": sorted({str(r.get("url", "")).split("/")[2]
                                                     for r in labelled
                                                     if str(r.get("url", "")).count("/") >= 2})}
    rep["spent_s"] = round(time.monotonic() - t0, 1)
    ran = [k for k in ("seed_miners", "discovery")
           if (rep.get(k) or {}).get("status") == "OK"]
    rep["status"] = "OK" if len(ran) == 2 else ("PARTIAL" if ran else "FAILED")
    state.update({"last_finished_at": _now_iso(), "last_status": rep["status"],
                  "last_seed_status": seed["status"],
                  "last_discovery_status": rep["discovery"].get("status")})
    if write:
        _write(STATE, state)
    return rep


# ------------------------------------------------------------------------------- child mode

def _child_seed() -> int:
    """seed_miners in this process, the rails installed before any miner module is imported."""
    import box_rails
    try:
        box_rails.install()
    except Exception as exc:
        print(RESULT_PREFIX + json.dumps({"status": "FAILED", "error": (
            f"box rails could not install, nothing fetched: {type(exc).__name__}: {exc}")[:300]}),
              flush=True)
        return 1
    import seed_miners
    miners = getattr(seed_miners, "MINERS", None)
    excluded = []
    if isinstance(miners, dict):
        for name in sorted(BOX_EXCLUDED_SEEDS & set(miners)):
            del miners[name]
            excluded.append(name)
    res = seed_miners.run_and_save()
    rows = sum(int((v or {}).get("count") or 0) for v in res.values() if isinstance(v, dict))
    print(RESULT_PREFIX + json.dumps({"status": "OK", "sources": len(res), "rows": rows,
                                      "rails_refused_here": len(box_rails.refused()),
                                      "excluded_on_box": excluded}),
          flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--force", action="store_true", help="run even inside the cadence")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, run nothing")
    ap.add_argument("--child", default="", help="child mode: 'seed'")
    a = ap.parse_args(argv)
    if a.child == "seed":
        return _child_seed()
    if a.child:
        print(f"unknown child {a.child!r}", flush=True)
        return 2
    if a.dry_run:
        ok, why = due(_read(STATE))
        organs, excluded, basis = discovery_organs()
        print(f"due={ok} ({why})")
        print(f"seed_miners bound {SEED_BOUND_S:.0f}s under box_rails")
        print(f"discovery organs ({len(organs)}): {', '.join(organs)}")
        print(f"excluded, already box legs ({basis}): {', '.join(excluded)}")
        return 0
    rep = run_pass(a.budget_s, force=a.force)
    if rep.get("status") in ("NOT_DUE", "LEASE_HELD"):
        print(f"INTEL FEED {rep['status']}: {rep['why']}", flush=True)
        return 0
    print(f"INTEL FEED {rep['status']} seed={rep['seed_miners']['status']} "
          f"discovery={rep['discovery'].get('status')} refused={rep['rails']['refused_n']} "
          f"spent={rep['spent_s']}s of {rep['budget_s']:.0f}s -> {REPORT}", flush=True)
    return 0 if rep["status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
