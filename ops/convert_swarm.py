"""Fan the deepening queue across EVERY working free model at once.

WHY. The deepening worker is one process talking to one model, and on the free tier that is
~60-70 s a row. Against a 28,564-row queue that is ~476 hours, and the box it runs on has 18
cores doing nothing. Meanwhile the panel holds TEN distinct zero-cost models that each return
strict JSON, and each has its OWN rate limit -- so ten workers on ten models is not ten times
the pressure on one provider, it is ten independent lanes.

Measured 2026-09-11 before this existed: 1 lane, 1 model, 0 candidates/hour because the seat
was mis-selected. After the seat fix a single lane converts; this is what makes the rate worth
having.

HOW THE KEY IS HANDLED. It is read from data/secrets/llm_panel.json inside this process and
passed to children through their environment. It is never an argument, so it never appears in
a process listing, a log line or a shell history -- `data/secrets/**` never leaves the box and
no tool prints a key.

EACH LANE IS BOUNDED. Every child gets its own --limit slice and inherits DEEPEN_RUN_BUDGET_SEC,
so a lane that hangs on a slow provider dies with the budget instead of running into the next
hour. A lane that fails does not take the others with it; its model is reported and the rest
carry on, which is the whole reason for ten of them.

    python ops/convert_swarm.py [--per-lane 200] [--budget-sec 2400]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
PANEL = ROOT / "data" / "secrets" / "llm_panel.json"
WORKER = DESK / "research" / "deepening_worker.py"
CANDIDATES = DESK / "data" / "hypotheses" / "deepened_candidates.json"
REPORT = DESK / "reports" / "CONVERT_SWARM.json"


def _snapshot(path: Path = CANDIDATES) -> dict:
    """Candidates held and rows decided so far, from the worker's own output. None = unreadable."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"candidates": None, "decided": None}
    disp = d.get("dispositions") if isinstance(d, dict) else None
    decided = (sum(int(v) for v in disp.values() if isinstance(v, (int, float)))
               if isinstance(disp, dict) else None)
    return {"candidates": len(d.get("candidates") or []), "decided": decided}


def write_report(before: dict, after: dict, lanes: list[dict], *, path: Path = REPORT,
                 now: str | None = None) -> dict:
    """THE SWARM'S OWN CONTRACT ARTIFACT (6h pass red team, 2026-11-25: MT5-ConvertSwarm ran
    hourly while PRODUCER_YIELD credited it 0 compute and 0 cells, because its work lands in the
    deepening worker's files under the worker's name). Exit code 0 proved only that lanes ran.
    `last_decided_utc` advances ONLY on a run that decided at least one queue row, and it is the
    stamp ops/organ_contract.py ages, so a swarm that runs and converts nothing goes stale and
    says so. Unmeasurable before/after is UNMEASURED, never 0."""
    stamp = now or datetime.now(UTC).isoformat(timespec="seconds")
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    def _delta(k: str) -> int | str:
        a, b = before.get(k), after.get(k)
        return (b - a) if isinstance(a, int) and isinstance(b, int) else "UNMEASURED"
    decided, gained = _delta("decided"), _delta("candidates")
    doc = {"schema": "convert_swarm/1", "at_utc": stamp, "lanes": lanes,
           "lanes_ok": sum(1 for x in lanes if x.get("rc") == 0),
           "lanes_killed": sum(1 for x in lanes if x.get("killed")),
           "before": before, "after": after, "rows_decided": decided,
           "candidates_gained": gained,
           "last_decided_utc": (stamp if isinstance(decided, int) and decided > 0
                                else (prev.get("last_decided_utc") if isinstance(prev, dict)
                                      else None)),
           "verdict": ("CONVERTING" if isinstance(decided, int) and decided > 0
                       else "UNMEASURED" if decided == "UNMEASURED" else "IDLE")}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-lane", type=int, default=200,
                    help="rows each lane attempts; 0 = the whole queue per lane")
    ap.add_argument("--budget-sec", type=int, default=2400)
    a = ap.parse_args(argv)

    if not PANEL.exists():
        print(f"no panel at {PANEL}")
        return 1
    cfg = json.loads(PANEL.read_text(encoding="utf-8"))
    providers = [p for p in (cfg.get("providers") or []) if p.get("key") and p.get("model")]
    if not providers:
        print("panel carries no usable provider")
        return 1

    key = str(providers[0]["key"])
    models = [str(p["model"]) for p in providers]
    print(f"lanes: {len(models)}")
    for m in models:
        print(f"   {m}")

    before = _snapshot()
    procs: list[tuple[str, subprocess.Popen]] = []
    for model in models:
        env = dict(os.environ)
        # env-seat path in libs.ops.llm_seat: <NAME>_API_KEY plus <NAME>_MODEL
        env["OPENROUTER_API_KEY"] = key
        env["OPENROUTER_MODEL"] = model
        env["DEEPEN_RUN_BUDGET_SEC"] = str(a.budget_sec)
        env["PYTHONPATH"] = f"{ROOT};{DESK}"
        env["PYTHONUNBUFFERED"] = "1"
        log = DESK / "logs" / f"convert_lane_{model.replace('/', '_').replace(':', '_')}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        fh = log.open("a", encoding="utf-8")
        p = subprocess.Popen(
            [sys.executable, "-u", str(WORKER), "--limit", str(a.per_lane)],
            cwd=str(DESK), env=env, stdout=fh, stderr=subprocess.STDOUT)
        procs.append((model, p))
        time.sleep(1.0)      # stagger the opening burst so the provider sees a ramp

    print(f"\nlaunched {len(procs)} lanes; budget {a.budget_sec}s each")
    started = time.time()
    done: list[tuple[str, int]] = []
    killed: list[str] = []
    while procs:
        for model, p in list(procs):
            rc = p.poll()
            if rc is not None:
                done.append((model, rc))
                procs.remove((model, p))
                print(f"  lane finished rc={rc:<4} {model}")
        if time.time() - started > a.budget_sec + 300:
            for model, p in procs:
                p.kill()
                killed.append(model)
                print(f"  lane KILLED (over budget) {model}")
            break
        time.sleep(5)

    ok = sum(1 for _, rc in done if rc == 0)
    print(f"\nlanes complete: {len(done)}  rc=0: {ok}")
    lanes = ([{"model": m, "rc": rc} for m, rc in done]
             + [{"model": m, "rc": None, "killed": True} for m in killed])
    rep = write_report(before, _snapshot(), lanes)
    print(f"rows decided this run: {rep['rows_decided']}  verdict: {rep['verdict']}")
    out = DESK / "data" / "hypotheses" / "deepened_candidates.json"
    if out.exists():
        try:
            d = json.loads(out.read_text(encoding="utf-8"))
            print(f"deepened_candidates: {len(d.get('candidates') or [])} candidate(s), "
                  f"built_at {d.get('built_at')}")
            print(f"dispositions: {d.get('dispositions')}")
        except (OSError, ValueError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
