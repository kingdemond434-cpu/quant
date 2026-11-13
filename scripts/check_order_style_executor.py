#!/usr/bin/env python3
"""ORDER-STYLE EXECUTOR FENCE -- does any row that can hold capital need an order the gateway
cannot place?

THE DEFECT (audit of #222, 2026-10-07). #222 made `execution_style=limit` a real, judged variant:
`cell_modifiers.apply` turns the parent's signal into a resting limit at the signal close and
`engine.run_backtest` fills it only when price comes back to it. The gateway's family executor
(`exec="family_market"`) has no limit executor -- it sends a MARKET order at the next open for
every signal `family_call.signals` returns, whatever `Signal.order_type` says. So a certified
limit cell promoted to capital would trade a different strategy under its certificate's name:
every signal filled instead of the ones price returned to, the spread paid instead of earned.

THE BOUNDARY lives in `mt5desk/executables.py` (`GATEWAY_ORDER_STYLES`, `order_style_gap`), the
registry the promoter already asks before writing a `family_market` row. The sealed promoter
does not yet ask it about order style -- that is the desktop patch
`/mnt/project-files/patches/limit_executor_refusal.patch`, which writes such a row
`status: PENDING_EXECUTOR` (withheld, not retired). Until that patch is applied, THIS FENCE is
what makes a leak visible: it fails the law gate the first time a limit-style row holds LIVE or
STANDBY status in the gateway roster or the sleeve registry.

STANDBY COUNTS. `promoter.reconcile_capital` restores a STANDBY row to LIVE on the allocator's
readings alone, without passing the promotion door again, so a STANDBY limit row is a LIVE limit
row one reading away.

WHAT IT DOES NOT DO. It never retires, demotes, sizes or edits a row. It reads two files and
publishes `desks/mt5/reports/ORDER_STYLE_EXECUTOR.json`.

  OK                 (exit 0) -- no LIVE/STANDBY row declares an order style outside
                                 `GATEWAY_ORDER_STYLES`.
  PENDING_EXECUTOR   (exit 2) -- at least one does; each is named with its gap.
  UNMEASURED         (exit 2) -- the files parsed but hold no LIVE/STANDBY row to judge.
  NOT-READABLE-HERE  (exit 0) -- neither file exists on this host (a verdict about the HOST).

Run: python scripts/check_order_style_executor.py [--json] [--roster P] [--registry P]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import executables  # noqa: E402

from libs.ops.fence_exit import fence_exit  # noqa: E402

ROSTER = _DESK / "data" / "sleeves.json"
REGISTRY = _DESK / "data" / "sleeve_registry.json"
REPORT = _DESK / "reports" / "ORDER_STYLE_EXECUTOR.json"
#: Statuses that hold capital now or can be restored to it without the promotion door.
CAPITAL_STATUSES = frozenset({"LIVE", "STANDBY"})

OK, PENDING, UNMEASURED, NOT_READABLE = ("OK", executables.PENDING_EXECUTOR, "UNMEASURED",
                                         "NOT-READABLE-HERE")
_PASSING = frozenset({OK, NOT_READABLE})


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rows(doc: Any) -> list[tuple[str, dict[str, Any]]]:
    sleeves = doc.get("sleeves") if isinstance(doc, dict) else doc
    if isinstance(sleeves, dict):
        return [(str(k), v) for k, v in sleeves.items() if isinstance(v, dict)]
    if isinstance(sleeves, list):
        return [(str(v.get("name") or i), v) for i, v in enumerate(sleeves)
                if isinstance(v, dict)]
    return []


def row_gap(name: str, row: dict[str, Any]) -> str | None:
    """The row's order-style gap: its own params (roster) or identity params (registry), else
    the style its clock key spells."""
    params = row.get("params")
    if not isinstance(params, dict):
        params = (row.get("identity") or {}).get("params")
    return executables.order_style_gap(params) or executables.order_style_gap_of_key(name)


def scan(roster_path: Path = ROSTER, registry_path: Path = REGISTRY) -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    docs = {"roster": (roster_path, _load(roster_path)),
            "registry": (registry_path, _load(registry_path))}
    if all(doc is None for _, doc in docs.values()):
        return {"status": NOT_READABLE, "at": now, "n_judged": 0, "pending": [],
                "why": f"neither {roster_path} nor {registry_path} is readable here"}
    judged = 0
    pending: list[dict[str, Any]] = []
    for label, (path, doc) in docs.items():
        for name, row in _rows(doc):
            status = str(row.get("status") or "").upper()
            if status not in CAPITAL_STATUSES:
                continue
            judged += 1
            gap = row_gap(name, row)
            if gap:
                pending.append({"source": label, "path": str(path), "name": name,
                                "status": status, "why": gap})
    status = PENDING if pending else (OK if judged else UNMEASURED)
    return {"status": status, "at": now, "n_judged": judged, "n_pending": len(pending),
            "gateway_order_styles": sorted(executables.GATEWAY_ORDER_STYLES),
            "pending": pending,
            "repair": ("apply /mnt/project-files/patches/limit_executor_refusal.patch (the "
                       "promoter writes such rows PENDING_EXECUTOR) or land the limit executor "
                       "(/mnt/project-files/patches/limit_executor_spec.md) and add the style "
                       "to executables.GATEWAY_ORDER_STYLES"),
            "why": (f"{len(pending)} LIVE/STANDBY row(s) need an order style the gateway cannot "
                    f"place" if pending else f"{judged} LIVE/STANDBY row(s) judged")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Can the gateway place every capital row's order?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--roster", type=Path, default=ROSTER)
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--report", type=Path, default=REPORT)
    a = ap.parse_args(argv)
    rep = scan(a.roster, a.registry)
    try:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    except OSError:
        pass
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        print(f"ORDER-STYLE EXECUTOR: {rep['status']} -- {rep['why']}")
        for p in rep["pending"][:20]:
            print(f"  {p['status']:8s} {p['name']}  ({p['source']}): {p['why']}")
    scanned = None if rep["status"] == NOT_READABLE else rep["n_judged"]
    return fence_exit(rep["status"], _PASSING, scanned=scanned,
                      of="LIVE/STANDBY rows in sleeves.json and sleeve_registry.json",
                      fence="check_order_style_executor")


if __name__ == "__main__":
    raise SystemExit(main())
