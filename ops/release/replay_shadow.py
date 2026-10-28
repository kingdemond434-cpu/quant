#!/usr/bin/env python3
"""The replay-shadow job: the live E8 gold book, base against PR, over a fixed scenario grid.

Each scenario is one server day (a seeded price path, an account, an optional open position)
stepped through the hours where the book acts. ops/release/replay_child.py runs it once on the
base tree and once on the PR's tree, each in a fresh process and an empty directory, unarmed. The
PR PASSES only when every step decides the same thing on both: the windows placed and skipped,
every intended order (side, price, stop, target, lot, risk fraction and its source), every
management action, the guard's verdict and the sizing inputs. Prose (`why`, `sizing`) and
timestamps are not decisions and are left out.

A difference is not judged good or bad here: a PR that changes what the live book does is not
eligible for a merge with no human, so it FAILS and takes the manual path (CLEAR + APPROVE
MERGES). It also FAILS when:

- it changes a money-path file the replay never imported (the Fusion gateway, a data or state
  file, another book): nothing here measured it, and an unmeasured change is never a pass;
- the base tree cannot run a scenario, or places nothing anywhere on the grid (UNMEASURED);
- the PR's tree raises where the base did not.

LIMIT: the PR's code runs in the child that writes its own result, so a PR written to fool this
check can. That is the reviewer's job (independent-review); this check catches regressions.

    python -I ops/release/replay_shadow.py --base <base tree> --head <PR tree> \
        --changed <file listing the PR's changed paths> [--report out.json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CHILD = HERE / "replay_child.py"
#: Changed files under these that the replay never imported are unmeasured money-path changes.
MONEY_PATH = (
    "desks/mt5/mt5desk/", "desks/mt5/prop/", "desks/mt5/data/", "data/", "libs/execution/",
    "libs/risk/", "libs/portfolio/",
)  # fmt: skip
#: Keys that carry prose or a wall-clock time, never a decision.
PROSE = frozenset(
    {
        "at",
        "why",
        "sizing",
        "alerts",
        "xacct_unpublished",
        "fusion_why",
        "detail",
        "note",
        "msg",
        "message",
    }
)
#: Server hours stepped each day: before, on and after every window's signal hour, and late.
HOURS = (0.5, 6.95, 7.03, 7.25, 8.0, 10.0, 13.03, 13.5, 15.0, 17.03, 17.5, 19.0, 21.5, 23.9)
SHAPES = ("range", "up_break", "down_break", "wide", "gap")
DAYS = ("2026-10-13", "2026-10-15")
TIMEOUT_S = 300


def _long(day: str, qty: float = 0.15) -> dict[str, Any]:
    from datetime import UTC, datetime

    opened = datetime.fromisoformat(day).replace(hour=7, minute=40, tzinfo=UTC)
    return {
        "id": 9001,
        "tradableInstrumentId": 6102,
        "side": "buy",
        "qty": qty,
        "avgPrice": 4310.0,
        "stopLossId": 9002,
        "openDate": int(opened.timestamp() * 1000),
    }


def scenarios() -> list[dict[str, Any]]:
    """The fixed grid: every shape x day x account. Deterministic, so both trees see the same."""
    out = []
    for day in DAYS:
        for shape in SHAPES:
            for acct, equity in (
                ("flat", 100_000.0),
                ("near_floor", 91_500.0),
                ("day_loss_edge", 98_310.0),
                ("profit_cap", 103_000.0),
                ("long_open", 100_000.0),
                ("heavy_open", 100_000.0),
            ):
                sc: dict[str, Any] = {
                    "id": f"{day}/{shape}/{acct}",
                    "day": day,
                    "shape": shape,
                    "seed": len(out),
                    "equity": equity,
                    "hours": list(HOURS),
                }
                if acct == "day_loss_edge":  # down 1,690 today: the risk budget's margin binds
                    sc["guard"] = {"day_start": 100_000.0, "peak_equity": 100_000.0}
                if acct in ("long_open", "heavy_open"):  # heavy: the budget's margin binds
                    sc["positions"] = [_long(day, 0.15 if acct == "long_open" else 0.335)]
                    sc["orders"] = [{"id": 9002, "stopPrice": 4270.0}]
                out.append(sc)
    return out


def canon(value: Any) -> Any:
    """The decision content of a value: prose keys, `*_at` keys and free text dropped."""
    if isinstance(value, dict):
        return {
            k: canon(v)
            for k, v in sorted(value.items())
            if k not in PROSE and not str(k).endswith("_at")
        }
    if isinstance(value, list):
        return [canon(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, str) and len(value) > 48 and " " in value:
        return "<text>"
    return value


def decisions(step: dict[str, Any]) -> dict[str, Any]:
    doc = step.get("doc") or {}
    guard = doc.get("guard_decision") or {}
    return canon(
        {
            "error": (step.get("error") or "").split(":", 1)[0] or None,
            "status": doc.get("status"),
            "placed": doc.get("placed"),
            "actions": doc.get("actions"),
            "skipped": sorted(
                str(s.get("window")) for s in doc.get("skipped") or [] if isinstance(s, dict)
            ),
            "sizing_source": doc.get("sizing_source"),
            "kelly_risk": doc.get("kelly_risk"),
            "cert_ceiling": doc.get("e8_cert_ceiling"),
            "risk_usd": doc.get("risk_usd"),
            "guard": {k: guard.get(k) for k in ("verdict", "flatten", "may_open")},
            "committed_usd": (doc.get("committed_risk") or {}).get("total_usd"),
            "windows": ((doc.get("state") or {}).get("windows")),
            "intents": step.get("intents"),
        }
    )


def run_tree(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
    """One scenario on one tree, in a fresh process and an empty directory."""
    with tempfile.TemporaryDirectory(prefix="shadow-") as tmp:
        work = Path(tmp)
        (work / "scenario.json").write_text(json.dumps(sc), "utf-8")
        out = work / "out.json"
        try:
            p = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(CHILD),
                    str(tree.resolve()),
                    str(work / "scenario.json"),
                    str(out),
                ],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"crash": f"timed out after {TIMEOUT_S}s"}
        if p.returncode != 0 or not out.exists():
            return {"crash": f"rc {p.returncode}: {(p.stderr or p.stdout)[-600:]}"}
        return json.loads(out.read_text("utf-8"))


def compare(
    base: Path, head: Path, changed: list[str], grid: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    grid = scenarios() if grid is None else grid
    problems: list[str] = []
    imported: set[str] = set()
    placed = 0
    for sc in grid:
        b, h = run_tree(base, sc), run_tree(head, sc)
        if "crash" in b:
            problems.append(f"UNMEASURED {sc['id']}: the base tree cannot run it ({b['crash']})")
            continue
        if "crash" in h:
            problems.append(f"{sc['id']}: the PR's tree crashed ({h['crash']})")
            continue
        base_root = str(base.resolve())
        imported.update(
            Path(f).relative_to(base_root).as_posix()
            for f in b["imported"]
            if f.startswith(base_root + "/")
        )
        for bs, hs in zip(b["steps"], h["steps"], strict=True):
            if bs.get("error"):
                problems.append(f"UNMEASURED {sc['id']} @{bs['hour']}: base raised {bs['error']}")
                continue
            placed += sum(1 for r in bs.get("intents") or [] if isinstance(r, dict))
            db, dh = decisions(bs), decisions(hs)
            if db != dh:
                keys = sorted(k for k in db if db.get(k) != dh.get(k))
                was = json.dumps({k: db.get(k) for k in keys})[:400]
                now = json.dumps({k: dh.get(k) for k in keys})[:400]
                problems.append(
                    f"{sc['id']} @{bs['hour']}: the PR decides differently on "
                    f"{', '.join(keys)}: base {was} PR {now}"
                )
    if not placed:
        problems.append("UNMEASURED: the base tree placed nothing anywhere on the grid")
    uncovered = sorted(f for f in changed if f.startswith(MONEY_PATH) and f not in imported)
    problems += [
        f"UNMEASURED money-path change (the replay never imported it): {f}" for f in uncovered
    ]
    return {
        "verdict": "FAIL" if problems else "PASS",
        "scenarios": len(grid),
        "steps": len(grid) * len(HOURS),
        "intents_compared": placed,
        "problems": problems,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--head", type=Path, required=True)
    ap.add_argument("--changed", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    a = ap.parse_args(argv)
    changed = [x.strip() for x in a.changed.read_text("utf-8").splitlines() if x.strip()]
    rep = compare(a.base, a.head, changed)
    if a.report:
        a.report.write_text(json.dumps(rep, indent=1), "utf-8")
    print(
        f"REPLAY-SHADOW {rep['verdict']}: {rep['scenarios']} scenarios, {rep['steps']} steps, "
        f"{rep['intents_compared']} intended orders compared"
    )
    for p in rep["problems"][:200]:
        print(" -", p)
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
