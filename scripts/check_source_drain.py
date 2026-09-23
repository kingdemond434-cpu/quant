"""THE TWO RATCHETS: uncollected sources and collected-but-unconverted sources only ever fall.

The principal, 2026-09-23: *"make sure they are always collected, 100% exploited and converted."*
A priced queue that is never drained is a backlog with a ranking on it. This fence makes the
backlog's direction a law:

  1. `uncollected` may never RISE above its own best (the ratchet in
     `desks/mt5/data/source_drain_ratchet.json`, written by `research/source_drain.py`)
  2. `collected_but_unconverted` may never RISE above its own best
  3. the OLDEST never-collected source may never age past its own cadence window

A rise is a breach and exits 1. A LARGE backlog that is falling is not a breach -- the fence
exists to force the direction, never to punish the size. An absent artifact is UNMEASURED and
exits 1 with that reason: the organ not having run is exactly the failure this fence is for
(LAWS 7, unwired or idle is a defect).

    python scripts/check_source_drain.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RATCHET = ROOT / "desks" / "mt5" / "data" / "source_drain_ratchet.json"
REPORT = ROOT / "desks" / "mt5" / "reports" / "SOURCE_DRAIN.json"


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def check(ratchet: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    problems: list[str] = []
    if not ratchet:
        return ([f"UNMEASURED: no {RATCHET.relative_to(ROOT)} -- research/source_drain.py has "
                 f"not run on this host, so the backlog has no measured direction"], {})
    unc = int(ratchet.get("uncollected", 0))
    conv = int(ratchet.get("unconverted", 0))
    best_unc = int(ratchet.get("best_uncollected", unc))
    best_conv = int(ratchet.get("best_unconverted", conv))
    if unc > best_unc:
        problems.append(f"uncollected RATCHET BREACHED: {unc} sources uncollected against a best "
                        f"of {best_unc} -- the backlog grew")
    if conv > best_conv:
        problems.append(f"unconverted RATCHET BREACHED: {conv} collected sources have no judged "
                        f"cell against a best of {best_conv} -- conversion went backwards")
    age = float(ratchet.get("oldest_age_h") or 0.0)
    window = float(ratchet.get("oldest_window_h") or 0.0)
    oldest = ratchet.get("oldest_never_collected")
    if oldest and window > 0 and age > window:
        problems.append(f"STALE SOURCE: {oldest} has been uncollected for {age:.1f}h against its "
                        f"own {window:.0f}h cadence window")
    return problems, {"uncollected": unc, "best_uncollected": best_unc,
                      "unconverted": conv, "best_unconverted": best_conv,
                      "oldest_never_collected": oldest, "oldest_age_h": age,
                      "oldest_window_h": window,
                      "drain_rate_per_pass": _read(REPORT).get("drain_rate_per_pass")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    problems, census = check(_read(RATCHET))
    if a.json:
        print(json.dumps({"ok": not problems, "problems": problems, "census": census}, indent=1))
    else:
        for p in problems:
            print(f"  BREACH {p}")
        if census:
            print(f"source drain: uncollected {census['uncollected']} (best "
                  f"{census['best_uncollected']}), unconverted {census['unconverted']} (best "
                  f"{census['best_unconverted']}), oldest {census['oldest_never_collected']} at "
                  f"{census['oldest_age_h']:.1f}h of {census['oldest_window_h']:.0f}h, rate "
                  f"{census['drain_rate_per_pass']}/pass")
        print("source drain: OK" if not problems else "source drain: RATCHET BREACHED")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
