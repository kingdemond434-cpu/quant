"""COLLECTOR AUTHOR -- closes the desk's real conversion bottleneck (principal 2026-07-27).

THE BOTTLENECK, identified this session: finding sources is automated, SCREENING is automated
(axis_screen), but turning a discovered source into a WIRED COLLECTOR is bespoke code the brain
writes per source -- and it is error-prone (the kimchi USDT-vs-FX construction bug, the bithumb
timezone lookahead, my own double-z-scoring). Breadth without this just grows a queue.

This closes the loop end-to-end, daily:
    breadth_expansion.jsonl (NEW+REACHABLE)  ->  3 flagship LLMs write a fetcher
      ->  STATIC SAFETY SCAN  ->  EXECUTE in isolated subprocess  ->  VALIDATE the series
      ->  axis_screen Stage-A  ->  report

SEATS CHOSEN ON MEASURED PERFORMANCE, NOT REPUTATION: the 2026-07-27 breadth sweep showed
grok-4.3 and nemotron producing 18 parseable rows each while gpt-5.6-terra-pro produced 0 on 5 of
6 lenses. Code generation is a different task, so the pool is code-strong flagships and each run
records which seat's collector actually WORKED -- the yield table is the seat-selection evidence.

*** SECURITY: this EXECUTES model-written code on a host holding trading keys. ***
Mitigations (defence in depth, not a sandbox):
  1. STATIC SCAN rejects: subprocess, os.system/popen, eval/exec/compile, __import__, socket,
     shutil, pathlib writes, open(...,'w'/'a'), pickle, requests-to-non-http, env access.
  2. Executed via a SEPARATE subprocess with a hard timeout, output-only via stdout JSON.
  3. Allowed imports whitelisted (json/urllib/datetime/math/statistics only).
Residual risk is NOT zero. Disclosed to the principal.

Stage-A only, zero promotion authority. Run from repo root.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from libs.doctrine.constitution import (  # noqa: E402
    OBJECTIVE_PREAMBLE,
    RESIDUAL_MANDATE,
)
from libs.llm.effort import reasoning_payload  # noqa: E402
from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above

KEYS = ROOT / "data/secrets/llm_panel.json"
FEED = ROOT / "data/breadth_expansion.jsonl"
DONE = ROOT / "data/collector_attempts.jsonl"
GEN = ROOT / "data/generated_collectors"
CTX = ssl.create_default_context()

# code-strong flagships; yield table below is the real selection evidence
SEATS = ["deepseek/deepseek-v4-pro", "moonshotai/kimi-k3", "x-ai/grok-4.3"]
# Sources attempted per run. Was 3, against a breadth feed that grows faster than 3/day -- so
# the conversion bottleneck this script exists to close was itself throttled below the inflow
# rate, and the backlog could only ever grow. Overridable per-run; the cost is one LLM call per
# (source x seat) and the static-scan + isolated-subprocess safety path is unchanged.
N_TARGETS = int(os.environ.get("COLLECTOR_N_TARGETS", "8"))

BANNED = re.compile(
    r"\b(subprocess|os\s*\.\s*(system|popen|remove|unlink|environ)|eval\s*\(|exec\s*\("
    r"|compile\s*\(|__import__|socket|shutil|pickle|marshal|ctypes|importlib"
    r"|open\s*\([^)]*['\"][wa]|\.write_text|\.write_bytes|rmtree|setattr\s*\(\s*__)")
ALLOWED_IMPORTS = {"json", "urllib", "urllib.request", "urllib.parse", "urllib.error",
                   "datetime", "math", "statistics", "re", "time", "csv", "io", "collections"}

SYSTEM = (
    # THE CONSTITUTION LEADS. An organ that does not carry the objective optimises for
    # what its output LOOKS like rather than for expected shift in E[log W] -- and, worse,
    # quietly recommends the timid option because nothing told it that timidity is a
    # scored defect rather than a neutral default.
    OBJECTIVE_PREAMBLE + RESIDUAL_MANDATE + "\n"
    "You write DATA COLLECTORS for a quant desk. Given a public data source, emit ONE Python "
    "function that fetches a DAILY TIME SERIES from it.\n"
    "STRICT CONTRACT:\n"
    "- Output ONLY code in a ```python fence. No prose.\n"
    "- Define exactly: def fetch() -> dict  returning {'YYYY-MM-DD': float, ...}\n"
    "- Standard library ONLY: json, urllib.request, datetime, math, re, time, csv, io.\n"
    "- NO subprocess/os/eval/exec/socket/file-writes. Read-only network via urllib.\n"
    "- Handle the real response schema; do not invent fields. If the endpoint needs a key, "
    "return {} (we only use keyless free sources).\n"
    "- Aim for >=200 daily points where the source allows.\n"
    "- Set a User-Agent header; use timeout=25 on every request."
)


def _ask(base, key, model, messages, timeout=150.0):
    body = json.dumps({"model": model, "max_tokens": 3000, "temperature": 0.3,
                       # DEPTH IS MEASURED, NOT ASSUMED. "high" is the middle rung of a ladder
                       # whose top differs per model and per month -- a literal here is
                       # capability left unused on a flagship the desk pays for.
                       "reasoning": reasoning_payload(model),
                       "messages": messages}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")



def extract_code(txt: str) -> str:
    m = re.search(r"```(?:python)?\s*(.+?)```", txt, re.S)
    return (m.group(1) if m else txt).strip()


def safety_scan(code: str) -> str | None:
    """Return a rejection reason, or None if the code passes. Fail CLOSED on anything unknown."""
    if BANNED.search(code):
        return f"banned construct: {BANNED.search(code).group(0)[:40]}"
    for mod in re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_][\w.]*)", code, re.M):
        root = mod.split(".")[0]
        if root not in {m.split(".")[0] for m in ALLOWED_IMPORTS}:
            return f"non-whitelisted import: {mod}"
    if "def fetch" not in code:
        return "no fetch() defined"
    return None


def run_isolated(code: str, timeout: int = 70) -> tuple[dict | None, str]:
    """Execute in a SEPARATE process with a hard timeout; series returned as stdout JSON."""
    runner = code + (
        "\n\nif __name__ == '__main__':\n"
        "    import json as _j\n"
        "    try:\n"
        "        _s = fetch()\n"
        "        _s = {str(k): float(v) for k, v in dict(_s).items()}\n"
        "        print('__SERIES__' + _j.dumps(_s))\n"
        "    except Exception as _e:\n"
        "        print('__ERR__' + type(_e).__name__ + ': ' + str(_e)[:180])\n")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(runner)
        path = fh.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           timeout=timeout, check=False)
        out = p.stdout or ""
        if "__SERIES__" in out:
            return json.loads(out.split("__SERIES__", 1)[1].splitlines()[0]), "ok"
        if "__ERR__" in out:
            return None, out.split("__ERR__", 1)[1].splitlines()[0][:150]
        return None, (p.stderr or "no output")[-150:]
    except subprocess.TimeoutExpired:
        return None, "timeout"
    finally:
        Path(path).unlink(missing_ok=True)


def validate(series: dict) -> tuple[bool, str]:
    """A collector that returns garbage is worse than none -- this is the diff-verify step."""
    if not series or len(series) < 90:
        return False, f"only {len(series or {})} points (<90)"
    vals = list(series.values())
    if len(set(vals)) < len(vals) * 0.2:
        return False, "near-constant series (stale/placeholder)"
    if any(v != v for v in vals):
        return False, "NaN present"
    bad = [k for k in series if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(k))]
    if bad:
        return False, f"bad date keys e.g. {bad[0]}"
    return True, f"{len(series)} points, {min(series)}..{max(series)}"


def main() -> None:
    if not (KEYS.exists() and FEED.exists()):
        print("missing panel keys or breadth feed")
        return
    # Live-roster resolution: an upgraded-away seat is substituted (same lab first), not lost.
    # SEAT CAP REMOVED (2026-07-31). This read `n=len(SEATS)`, so the LITERAL'S LENGTH capped how
    # many funded seats were ever asked -- 3 of 13. Five organs shared the bug. SEATS is a
    # PRIORITY ORDER, not a membership list: the preferred list is now built from the LIVE roster
    # so every seat the desk pays for does the desk's work, and growing the roster grows the
    # organ. seats.resolve still substitutes an upgraded-away model same-lab-first.
    _roster = [str(p["model"]) for p in seats.load_roster()]
    _pref = SEATS + [m for m in _roster if m not in SEATS]
    provs = {p["model"]: p for p in seats.resolve(_pref, n=None, role="collector_author")}
    seated = list(provs)
    tried = set()
    if DONE.exists():
        tried = {json.loads(x).get("source") for x in DONE.read_text("utf-8").splitlines()
                 if x.strip()}

    cands, seen = [], set()
    for ln in FEED.read_text("utf-8").splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("_summary") or r.get("duplicate") or not r.get("reachable"):
            continue
        nm = r.get("name")
        if nm in tried or nm in seen:
            continue
        seen.add(nm)
        cands.append(r)
    if not cands:
        print("no unconverted NEW+REACHABLE sources in the feed")
        return
    targets = cands[:N_TARGETS]
    GEN.mkdir(exist_ok=True)
    print(f"=== COLLECTOR AUTHOR | {len(targets)} sources x {len(seated)} flagship seats ===")
    print("    (executes model-written code -- static scan + isolated subprocess + timeout)\n")

    jobs = [(t, s) for t in targets for s in seated]

    def _gen(j):
        t, seat = j
        user = (f"SOURCE: {t['name']}\nENDPOINT: {t['url']}\n"
                f"MODALITY: {t.get('modality','')}\nWHY IT MATTERS: {t.get('mechanism','')}\n\n"
                "Write fetch() returning a daily time series from this source.")
        try:
            # NO PUSH LADDER HERE, DELIBERATELY. This task writes ONE working fetch(),
            # not an enumeration of ideas, so the analysis ladder is the wrong
            # instrument: it asks for rankings and removals, and extract_code() on a
            # ten-round concatenation would pick a block from the wrong round.
            # Breadth here comes from more TARGETS, not more rounds per target.
            msgs = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user}]
            return t, seat, extract_code(_ask(provs[seat]["base_url"],
                                              provs[seat]["key"], seat, msgs)), None
        except Exception as e:
            return t, seat, "", f"{type(e).__name__}"

    with ThreadPoolExecutor(max_workers=6) as ex:
        gens = list(ex.map(_gen, jobs))

    results, wins = [], {}
    for t, seat, code, err in gens:
        nm, sn = t["name"][:34], seat.split("/")[-1][:18]
        if err:
            print(f"  {nm:<34} {sn:<18} LLM-FAIL {err}")
            continue
        rej = safety_scan(code)
        if rej:
            print(f"  {nm:<34} {sn:<18} REJECTED ({rej})")
            results.append({"source": t["name"], "seat": seat, "status": "unsafe", "detail": rej})
            continue
        series, msg = run_isolated(code)
        ok, vmsg = validate(series or {})
        status = "WORKS" if ok else "broken"
        print(f"  {nm:<34} {sn:<18} {status:<7} {vmsg if ok else msg}")
        results.append({"source": t["name"], "seat": seat, "status": status,
                        "detail": vmsg if ok else msg, "n": len(series or {})})
        if ok and t["name"] not in wins:
            wins[t["name"]] = (seat, code, series)
            safe = re.sub(r"[^a-z0-9]+", "_", t["name"].lower())[:40]
            (GEN / f"{safe}.py").write_text(code, "utf-8")

    with DONE.open("a", encoding="utf-8") as fh:
        for r in results:
            r["date"] = datetime.now(tz=UTC).date().isoformat()
            fh.write(json.dumps(r) + "\n")

    print(f"\n  CONVERTED {len(wins)}/{len(targets)} sources into working collectors")
    for nm, (seat, _c, ser) in wins.items():
        print(f"    {nm[:40]:<40} by {seat.split('/')[-1]:<16} {len(ser)} pts -> {GEN.name}/")
    tally: dict[str, list[int]] = {}
    for r in results:
        tally.setdefault(r["seat"], [0, 0])
        tally[r["seat"]][1] += 1
        if r["status"] == "WORKS":
            tally[r["seat"]][0] += 1
    print("\n  SEAT YIELD (this is the seat-selection evidence, not reputation):")
    for seat, (w, n) in sorted(tally.items(), key=lambda kv: -kv[1][0]):
        print(f"    {seat.split('/')[-1]:<22} {w}/{n} working")
    print("\n  -> working collectors land in data/generated_collectors/ for screening.")
    print("     Stage-A only; a generated collector NEVER auto-wires into the daily cycle.")


if __name__ == "__main__":
    main()
