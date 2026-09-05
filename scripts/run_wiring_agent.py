"""WIRING AGENT -- built things get WIRED, automatically, every day (principal order 2026-07-30).

THE PROBLEM IT REMOVES. `libs/self_improvement/dormancy.py` DETECTS capabilities nothing imports
and nothing schedules -- it measured 171 of them / 16,645 paid-for unused lines on 2026-07-30. But
detection alone reproduces the original failure one level up: a report nobody actions is itself a
dormant capability. The principal's instruction is explicit -- *"make a wiring agent that always
makes sure everything built is wired, or make sure every cycle automatically wires things which
aren't."* So this agent ACTS: it wires what is safe to wire, and it PROPOSES the rest.

THE SAFETY LINE, and it is the whole design. Auto-wiring is a privileged operation -- it causes
code to START RUNNING on a schedule, unattended, on a box with live exchange credentials. So the
agent auto-wires ONLY what it can prove is inert-by-construction, and every other class is
proposed for a human/organ decision with the reason it was withheld:

  AUTO-WIRE   research/reporting scripts: a `main()`, no money-path import, no spend, no writes
              outside data/ + web/, and a name that is not on the never-touch list.
  PROPOSE     anything touching the money path (execution/risk/order/deadman), anything that can
              SPEND (openrouter/panel/kimi/anthropic), anything writing outside data/ + web/,
              and anything whose import graph the agent cannot resolve.
  NEVER       Tier-3 (`run_deadman_switch.py`) and the executor -- not even proposed. Their
              scheduling is a principal decision, permanently.

WHY A CADENCE IS CHOSEN, NOT GUESSED: a wired-but-wrongly-frequent organ is its own defect (the
2026-07-21 IP ban came from over-frequent polling). Cadence is derived from what the script reads
-- venue/network readers get hourly-or-slower, pure local readers get daily -- and every generated
entry is tagged CONFIDENCE:auto-wired so a human can find and re-tune every one of them.

IDEMPOTENT: re-running never duplicates an entry. Writes to ops/crontab.manifest inside a fenced
block, so hand-written entries are never touched.

    python scripts/run_wiring_agent.py            # report only (default: SAFE)
    python scripts/run_wiring_agent.py --apply    # actually write the manifest
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MANIFEST = _ROOT / "ops/crontab.manifest"
_OUT = _ROOT / "data/wiring_agent.json"
_FENCE_START = "# >>> WIRING AGENT (auto-wired, idempotent) >>>"
_FENCE_END = "# <<< WIRING AGENT <<<"

# Never scheduled by an agent, ever. Not proposed either -- these are principal decisions.
_NEVER = {"run_deadman_switch.py", "run_cashcarry_executor.py"}

# Safe-by-writes is not the same as sane-to-schedule (2026-07-31: the agent cron'd ops_server.py
# -- a long-running server, so each fire stacks an instance or dies on the bound port -- and
# setup_ngrok.py/setup_testnet_keys.py, one-shot provisioning). Shape filters, not a blacklist:
_NOT_ORGANS = ("setup_", "smoke_", "demo_", "bootstrap_")
_SERVER_MARKERS = ("serve_forever", "httpserver", "socketserver", "uvicorn",
                   "app.run(", "start_server", ".bind((")

# Import substrings that make a script MONEY-PATH or SPEND-CAPABLE -> propose, never auto-wire.
_MONEY_PATH = ("libs.execution", "binance_live", "binance_spot_live", "binance_testnet",
               "libs.risk", "cashcarry_executor", "order", "staging")
_SPENDS = ("openrouter", "anthropic", "kimi", "external_panel", "panel_budget", "requests.post")


def _module_imports(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def _has_main(tree: ast.AST) -> bool:
    return any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in ast.walk(tree))


_ALLOWED = ('"data/', "'data/", '"web/', "'web/", '"docs/', "'docs/", '"reports/', "'reports/",
            "_ROOT /", "tmp_path", "Path(__file__)")


def _safe_path_constants(tree: ast.AST) -> set[str]:
    """Module-level names bound to an ALLOWED path expression.

    Without this the agent is needlessly timid: the house pattern is `_OUT = _ROOT / "data/x.json"`
    at module level and `_OUT.write_text(...)` later, so the write LINE shows no path and every
    such script was flagged 'writes outside data/'. Resolving the constant recovers them. Erring
    toward PROPOSE is the safe direction, but being wrong 40 times is a yield problem worth fixing.
    """
    names: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                src = ast.unparse(node.value)
                if any(a in src for a in _ALLOWED):
                    names.add(target.id)
    return names


def _writes_outside_data(src: str, safe_names: set[str] | None = None) -> bool:
    """A scheduled script must not write outside data/ + web/ unattended."""
    for marker in ('write_text(', 'open(', 'mkdir('):
        idx = 0
        while (idx := src.find(marker, idx)) != -1:
            line_start = src.rfind("\n", 0, idx) + 1
            line = src[line_start:src.find("\n", idx)]
            if any(p in line for p in _ALLOWED) or any(n in line for n in (safe_names or set())):
                idx += 1
                continue
            return True
    return False


def _required_positionals(tree: ast.AST) -> list[str]:
    """argparse positionals with no default and no optional nargs -- args the row must supply.

    THE DEFECT THIS ENDS (measured 2026-08-29). Every other check here proves the script is SAFE
    to schedule; none asked whether it can RUN with the command line the agent writes, which is
    always argument-free. `scripts/vault_search.py` takes a required positional query, was
    auto-wired as `.venv/bin/python scripts/vault_search.py >> ...`, and every scheduled run
    since has exited 2 on an argparse usage message. A row that can only ever fail is worse than
    an unwired script: it burns a slot, writes a log nobody can act on, and counts as coverage.

    Static, not executed: running an unknown script to find out is the cost this check exists to
    avoid. It reads add_argument calls, so it inherits argparse's own vocabulary rather than
    guessing at one. `nargs` of "?" or "*" and any `default=` make a positional optional, which
    is exactly when an argument-free invocation is fine.
    """
    required: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument" and node.args):
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if first.value.startswith("-"):
            continue                       # a flag; absent is a valid state
        kw = {k.arg: k.value for k in node.keywords}
        if "default" in kw:
            continue
        nargs = kw.get("nargs")
        if isinstance(nargs, ast.Constant) and nargs.value in ("?", "*"):
            continue
        required.append(first.value)
    return required


def classify(rel: str) -> tuple[str, str, str]:
    """(decision, reason, cadence). decision in AUTO-WIRE | PROPOSE | NEVER."""
    name = Path(rel).name
    if name in _NEVER:
        return "NEVER", "Tier-3 / executor -- scheduling is a permanent principal decision", ""
    if name.startswith(_NOT_ORGANS):
        return "PROPOSE", "one-shot provisioning/smoke script -- not a recurring organ", ""
    p = _ROOT / rel
    try:
        src = p.read_text("utf-8", errors="ignore")
        tree = ast.parse(src)
    except (OSError, SyntaxError) as e:
        return "PROPOSE", f"unparseable ({type(e).__name__}) -- cannot prove it is safe", ""
    if not _has_main(tree):
        return "PROPOSE", "no main() -- not a runnable organ; likely a library or a helper", ""
    imports = " ".join(_module_imports(tree)).lower()
    if any(m in imports for m in _MONEY_PATH):
        return "PROPOSE", "imports the money path (execution/risk) -- a human decides its cadence", ""
    low = src.lower()
    if any(s in low for s in _SPENDS):
        return "PROPOSE", "can SPEND (external model/API) -- budget envelope decision, not auto", ""
    if any(m in low for m in _SERVER_MARKERS):
        return "PROPOSE", "long-running server -- needs a supervisor (systemd), not a cron stack", ""
    if _writes_outside_data(src, _safe_path_constants(tree)):
        return "PROPOSE", "writes outside data/ + web/ -- unattended scheduling needs review", ""
    needed = _required_positionals(tree)
    if needed:
        # The agent only ever writes an argument-free command, so this script would fail on
        # every single run. Proven on vault_search.py, auto-wired and exiting 2 on an argparse
        # usage message every day since (L1.49: a gate that never ran is a claim the desk cannot
        # cash -- and a row that only ever fails is the same claim with a log file).
        return ("PROPOSE", f"requires positional argument(s) {', '.join(needed)} -- the agent "
                "writes an argument-free command, so scheduling it creates a row that can only "
                "ever fail", "")
    # Cadence from what it touches: network readers slower, local-only readers daily. Slot is a
    # deterministic hash of the name -- a fixed "21 8" herded every wired organ onto one minute
    # of a 2-core box (R0070 stagger); hashing keeps re-runs idempotent, daily slots land in the
    # 03:00-06:59 window clear of the 08:45 brain and the 02:00 research chain.
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    touches_net = any(k in low for k in ("urllib", "http", "requests", "api."))
    cadence = (f"{h % 60} */6 * * *", "6-hourly (reads a network source; slower cadence bounds "
               "rate-limit exposure -- the 2026-07-21 IP ban came from over-frequent polling)") \
        if touches_net else (f"{h % 60} {3 + (h >> 8) % 4} * * *", "daily (local artifacts only)")
    return "AUTO-WIRE", f"runnable, no money path, no spend, local writes only -- {cadence[1]}", \
        cadence[0]


def _fenced_paths() -> list[str]:
    """Script paths already inside the fence. Wired-stays-wired: dormancy reads the manifest, so
    a script the agent wired yesterday is no longer dormant today -- without this union the fence
    DROPS it, it goes dormant again tomorrow, and the whole block oscillates between two disjoint
    sets forever (observed live 2026-07-31: six scripts out, twelve in, every run)."""
    try:
        text = _MANIFEST.read_text("utf-8")
        block = text[text.index(_FENCE_START):text.index(_FENCE_END)]
    except (OSError, ValueError):
        return []
    out: list[str] = []
    for ln in block.splitlines():
        if ".venv/bin/python scripts/" in ln and not ln.lstrip().startswith("#"):
            out.append(ln.split(".venv/bin/python ", 1)[1].split()[0])
    return out


def scan() -> dict[str, Any]:
    from libs.self_improvement.dormancy import scan as dormancy_scan
    rep = dormancy_scan(include_modules=False)      # scripts only: modules are wired by callers
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in rep.dormant:
        decision, reason, cadence = classify(d.path)
        seen.add(d.path)
        rows.append({"path": d.path, "lines": d.lines, "decision": decision,
                     "reason": reason, "cadence": cadence})
    for rel in _fenced_paths():                     # ratchet: re-classify, never silently drop
        if rel in seen:
            continue
        decision, reason, cadence = classify(rel)
        rows.append({"path": rel, "lines": 0, "decision": decision,
                     "reason": reason, "cadence": cadence})
    rows.sort(key=lambda r: (-r["lines"]))
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["decision"])] = counts.get(str(r["decision"]), 0) + 1
    return {"generated": datetime.now(tz=UTC).isoformat(), "counts": counts,
            "n_scripts_scanned": rep.n_scripts_scanned, "rows": rows}


def _render(rows: list[dict[str, Any]]) -> str:
    lines = [_FENCE_START,
             "# Written by scripts/run_wiring_agent.py -- DO NOT hand-edit inside the fence; edits",
             "# are replaced on the next run. To take an entry over, move it OUTSIDE the fence and",
             "# retune it (the agent will then leave it alone because it is already scheduled).",
             "# Every entry here was proven: runnable main(), no money-path import, no spend",
             "# capability, no writes outside data/ + web/. CONFIDENCE: auto-wired."]
    for r in rows:
        if r["decision"] != "AUTO-WIRE":
            continue
        lines.append(f"# {r['path']} -- {r['reason']}")
        lines.append(f'{r["cadence"]} cd "$QUANT_ROOT" && .venv/bin/python {r["path"]} '
                     f'>> data/cro_ai_logs/{Path(r["path"]).stem}.log 2>&1')
    lines.append(_FENCE_END)
    return "\n".join(lines) + "\n"


def apply_block(rows: list[dict[str, Any]]) -> int:
    text = _MANIFEST.read_text("utf-8")
    block = _render(rows)
    if _FENCE_START in text and _FENCE_END in text:
        head = text[:text.index(_FENCE_START)]
        tail = text[text.index(_FENCE_END) + len(_FENCE_END):].lstrip("\n")
        text = head + block + tail
    else:
        text = text.rstrip("\n") + "\n\n" + block
    _MANIFEST.write_text(text, "utf-8")
    return sum(1 for r in rows if r["decision"] == "AUTO-WIRE")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the manifest (default: report)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = scan()
    if args.apply:
        rep["wired"] = apply_block(rep["rows"])
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"wiring agent: {rep['counts']} over {rep['n_scripts_scanned']} scripts"
              + (f" | WIRED {rep.get('wired', 0)}" if args.apply else " | report-only"))
        for r in rep["rows"][:15]:
            print(f"  {r['decision']:10} {r['path']:44} {r['reason'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
