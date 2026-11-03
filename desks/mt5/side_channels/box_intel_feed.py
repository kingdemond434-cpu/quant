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
     is left. Organs hourly_cycle already runs as legs of their own (world_crawler, deep_forest,
     alpha_evolution, ...) are excluded, read from hourly_cycle's own `_producer` calls, so no
     organ gets two writers. The same rails reach every organ child through the environment
     (`hourly_discovery --organ` installs them when QUANT_BOX_RAILS=1).

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

#: The organs hourly_cycle runs as legs of their own, if its source cannot be read. Kept in step
#: with the regex below by test_box_intel_feed.
BOX_OWNED_FALLBACK: frozenset[str] = frozenset({
    "world_crawler", "deep_forest_miner", "acquire_datasets", "weak_signal_compiler",
    "alpha_evolution", "cross_asset_graph", "world_causal_graph", "execution_twin",
    "factor_model_coevolution",
})
_PRODUCER_RE = re.compile(r'_producer\(\s*"[^"]*"\s*,\s*"(?:[\w.]+/)*(\w+)\.py"')

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


def box_owned_organs(cycle: Path = HOURLY_CYCLE) -> tuple[frozenset[str], str]:
    """(script stems hourly_cycle already runs through `_producer`, basis)."""
    try:
        text = cycle.read_text(encoding="utf-8")
    except OSError as exc:
        return BOX_OWNED_FALLBACK, f"fallback: {cycle.name} unreadable ({type(exc).__name__})"
    return frozenset(_PRODUCER_RE.findall(text)), f"{cycle.name} _producer calls"


def discovery_organs(cycle: Path = HOURLY_CYCLE) -> tuple[list[str], list[str], str]:
    """(organs this leg runs, organs excluded because the box already clocks them, basis)."""
    import hourly_discovery
    owned, basis = box_owned_organs(cycle)
    names = list(hourly_discovery.ORGANS)
    return ([n for n in names if n not in owned], [n for n in names if n in owned], basis)


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
             cycle: Path = HOURLY_CYCLE) -> dict[str, Any]:
    runner = runner or _default_runner
    state = _read(STATE)
    ok, why = due(state, now)
    if not ok and not force:
        # NOT_DUE writes nothing: the report keeps saying what the last real pass did.
        return {"status": "NOT_DUE", "why": why}
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
        organs, excluded, basis = discovery_organs(cycle)
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
        refused = box_rails.logged_refusals(log)
        with contextlib.suppress(OSError):
            os.unlink(log)
    rep["rails"] = {"user_agent": box_rails.USER_AGENT,
                    "robots_tokens": list(box_rails.ROBOTS_TOKENS),
                    "refused_n": len(refused),
                    "refused": [{"url": str(r.get("url", ""))[:150],
                                 "why": str(r.get("why", ""))[:150]}
                                for r in refused[:REFUSALS_SHOWN]]}
    rep["spent_s"] = round(time.monotonic() - t0, 1)
    ran = [k for k in ("seed_miners", "discovery")
           if (rep.get(k) or {}).get("status") == "OK"]
    rep["status"] = "OK" if len(ran) == 2 else ("PARTIAL" if ran else "FAILED")
    state.update({"last_finished_at": _now_iso(), "last_status": rep["status"],
                  "last_seed_status": seed["status"],
                  "last_discovery_status": rep["discovery"].get("status")})
    if write:
        _write(STATE, state)
        _write(REPORT, rep)
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
    res = seed_miners.run_and_save()
    rows = sum(int((v or {}).get("count") or 0) for v in res.values() if isinstance(v, dict))
    print(RESULT_PREFIX + json.dumps({"status": "OK", "sources": len(res), "rows": rows,
                                      "rails_refused_here": len(box_rails.refused())}),
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
    if rep.get("status") == "NOT_DUE":
        print(f"INTEL FEED not due: {rep['why']}", flush=True)
        return 0
    print(f"INTEL FEED {rep['status']} seed={rep['seed_miners']['status']} "
          f"discovery={rep['discovery'].get('status')} refused={rep['rails']['refused_n']} "
          f"spent={rep['spent_s']}s of {rep['budget_s']:.0f}s -> {REPORT}", flush=True)
    return 0 if rep["status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
