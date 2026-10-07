"""FENCE: only the order path may hold order authority over the trading terminal (ARCH-12).

THE ARCHITECTURE: research proposes, forecasting publishes beliefs, validation decides
eligibility, the allocator proposes, independent controls enforce, EXECUTION manages orders. AI
researchers hold no production trading credentials. Until 2026-10-07, about fifty non-order
modules (research, recorders, miners, one-off downloaders) imported the raw `MetaTrader5` module
on the trading box, and that module carries `order_send`, `order_delete` and the package's own
`Buy` / `Sell` / `Close` helpers: any of them could place or close an order on the live account.

WHAT IT FAILS, on every tracked .py outside the tests:
  1. a direct `MetaTrader5` import -- `import MetaTrader5`, `from MetaTrader5 import ...`,
     `importlib.import_module("MetaTrader5")`, `__import__("MetaTrader5")` -- outside ORDER_PATH
     and the read-only proxy itself. Everything else uses `libs.ops.mt5_readonly.readonly_mt5()`,
     an allowlist proxy that refuses every callable that is not a read.
  2. any `.order_send(` / `.order_delete(` call, or the package's `Buy(` / `Sell(` / `Close(`
     helpers on a module object, outside ORDER_PATH.

PENDING_DESKTOP is the ratchet: money-path files the cloud may not edit (the promoter, the
allocator) and the legacy app adapter that logs in with credentials. Each entry must still
offend (a healed entry fails until it is removed), and the list may only shrink: adding to it is
lowering the gate. The desktop pass converts them with the same two-line change.

A COMMIT FENCE (`_LAW_FENCES`): it reads the code, so it is as true in CI as on the box.
Exit 0 clean, 1 on any offence. `--json` prints the report.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: The order path: the gateway, its single order door, the execution broker layer and the Tier-3
#: deadman rail (never modified autonomously, LAWS section 4).
ORDER_PATH: frozenset[str] = frozenset({
    "desks/mt5/mt5desk/gateway.py",
    "desks/mt5/mt5desk/order_door.py",
    "libs/execution/broker.py",
    "desks/mt5/proposals/fusion_deadman.py",
    # The operator's order-routing smoke test: its one send (allow_send=1) goes through
    # order_door.guard, on the same ledger as the gateway's. Not a research module.
    "desks/mt5/research/probe_terminal.py",
})
#: The read-only proxy is the one other module that imports the package (to wrap it).
PROXY = "libs/ops/mt5_readonly.py"
#: Offenders awaiting the desktop pass. RATCHET: may only shrink; every entry must still offend.
PENDING_DESKTOP: dict[str, str] = {
    "desks/mt5/research/promoter.py": "money path; cloud edits refused -- desktop converts",
    "desks/mt5/research/pf_allocator.py": "allocator; cloud edits refused -- desktop converts",
    "app/mt5_adapter.py": "legacy app adapter that calls mt5.login with credentials",
}
PENDING_CEILING = 3
PACKAGE = "MetaTrader5"
WRITE_CALLS = frozenset({"order_send", "order_delete"})
HELPER_CALLS = frozenset({"Buy", "Sell", "Close"})


def tracked_py(root: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "*.py"], capture_output=True,
                         text=True, check=False).stdout.split()
    return [p for p in out if not p.startswith("tests/") and "/tests/" not in p]


def _str_arg(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value,
                                                                           str):
        return call.args[0].value
    return None


def offences(source: str) -> list[dict[str, Any]]:
    """(kind, line, detail) for every direct package import and every write call."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [{"kind": "unparseable", "line": exc.lineno or 0, "detail": str(exc)}]
    found: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] == PACKAGE:
                    found.append({"kind": "import", "line": node.lineno, "detail": a.name})
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == PACKAGE:
                found.append({"kind": "import", "line": node.lineno, "detail": node.module})
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else None)
            if name in ("import_module", "__import__") and _str_arg(node) == PACKAGE:
                found.append({"kind": "import", "line": node.lineno, "detail": name})
            elif isinstance(fn, ast.Attribute) and (fn.attr in WRITE_CALLS
                                                    or fn.attr in HELPER_CALLS):
                found.append({"kind": "write_call", "line": node.lineno, "detail": fn.attr})
    return found


def _is_helper_noise(rel: str, hit: dict[str, Any], source: str) -> bool:
    """`x.Close(` is a pandas column far more often than the MT5 helper: count a helper only in a
    file that also names the package."""
    return hit["detail"] in HELPER_CALLS and PACKAGE not in source and "mt5" not in source


def measure(root: Path = ROOT) -> dict[str, Any]:
    bad: dict[str, list[dict[str, Any]]] = {}
    pending_seen: dict[str, list[dict[str, Any]]] = {}
    for rel in tracked_py(root):
        if rel in ORDER_PATH or rel == PROXY:
            continue
        try:
            source = (root / rel).read_text("utf-8", errors="replace")
        except OSError:
            continue
        if PACKAGE not in source and not any(w in source for w in WRITE_CALLS | HELPER_CALLS):
            continue
        hits = [h for h in offences(source) if not _is_helper_noise(rel, h, source)]
        if not hits:
            continue
        (pending_seen if rel in PENDING_DESKTOP else bad)[rel] = hits
    healed = sorted(set(PENDING_DESKTOP) - set(pending_seen))
    problems: list[str] = [f"{rel}:{h['line']} {h['kind']} {h['detail']}"
                           for rel, hs in sorted(bad.items()) for h in hs]
    problems += [f"{rel}: listed in PENDING_DESKTOP but no longer offends -- remove it (ratchet)"
                 for rel in healed]
    if len(PENDING_DESKTOP) > PENDING_CEILING:
        problems.append(f"PENDING_DESKTOP grew to {len(PENDING_DESKTOP)} > {PENDING_CEILING}: "
                        "the list only shrinks")
    return {"verdict": "FAIL" if problems else "PASS", "problems": problems,
            "order_path": sorted(ORDER_PATH), "pending_desktop": sorted(pending_seen),
            "offenders": dict(sorted(bad.items()))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = measure()
    if args.json:
        print(json.dumps(doc, indent=2))
    elif doc["problems"]:
        print("ORDER AUTHORITY: a module outside the order path can reach the venue "
              "(use libs.ops.mt5_readonly.readonly_mt5):")
        for p in doc["problems"]:
            print(f"  {p}")
    else:
        print(f"order authority: clean ({len(doc['pending_desktop'])} money-path file(s) await "
              "the desktop pass)")
    return 0 if doc["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
