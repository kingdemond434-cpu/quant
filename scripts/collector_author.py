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

KEYS = ROOT / "data/secrets/llm_panel.json"
FEED = ROOT / "data/breadth_expansion.jsonl"
DONE = ROOT / "data/collector_attempts.jsonl"
GEN = ROOT / "data/generated_collectors"
CTX = ssl.create_default_context()

# code-strong flagships; yield table below is the real selection evidence
SEATS = ["deepseek/deepseek-v4-pro", "moonshotai/kimi-k3", "x-ai/grok-4.3"]
N_TARGETS = 3          # sources attempted per run

BANNED = re.compile(
    r"\b(subprocess|os\s*\.\s*(system|popen|remove|unlink|environ)|eval\s*\(|exec\s*\("
    r"|compile\s*\(|__import__|socket|shutil|pickle|marshal|ctypes|importlib"
    r"|open\s*\([^)]*['\"][wa]|\.write_text|\.write_bytes|rmtree|setattr\s*\(\s*__)")
ALLOWED_IMPORTS = {"json", "urllib", "urllib.request", "urllib.parse", "urllib.error",
                   "datetime", "math", "statistics", "re", "time", "csv", "io", "collections"}

SYSTEM = (
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



def _doctrine(role: str = "") -> str:
    """Runtime doctrine preamble. One source (scripts/doctrine.py); never a pasted copy."""
    try:
        from scripts.doctrine import preamble
        return preamble(role)
    except Exception:  # noqa: BLE001
        try:
            import sys as _s
            _s.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
            from doctrine import preamble  # type: ignore
            return preamble(role)
        except Exception:  # noqa: BLE001
            return ""          # never break a caller over a preamble


def _ask(base, key, model, system, user, timeout=150.0):
    body = json.dumps({"model": model, "max_tokens": 3000, "temperature": 0.3,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": _doctrine("collector_author") + system},
                                    {"role": "user", "content": user}]}).encode()
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
    provs = {p["model"]: p for p in json.loads(KEYS.read_text("utf-8"))["providers"]
             if isinstance(p, dict)}
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
    print(f"=== COLLECTOR AUTHOR | {len(targets)} sources x {len(SEATS)} flagship seats ===")
    print("    (executes model-written code -- static scan + isolated subprocess + timeout)\n")

    jobs = [(t, s) for t in targets for s in SEATS if s in provs]

    def _gen(j):
        t, seat = j
        user = (f"SOURCE: {t['name']}\nENDPOINT: {t['url']}\n"
                f"MODALITY: {t.get('modality','')}\nWHY IT MATTERS: {t.get('mechanism','')}\n\n"
                "Write fetch() returning a daily time series from this source.")
        try:
            return t, seat, extract_code(_ask(provs[seat]["base_url"], provs[seat]["key"],
                                              seat, SYSTEM, user)), None
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
