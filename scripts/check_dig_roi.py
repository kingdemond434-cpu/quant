"""DIG ROI -- a cycle is scored by TESTABLE CANDIDATES AND CERTIFICATES, never by bytes written.

WHY THIS EXISTS (principal 2026-08-28: "big doesn't mean token wastage -- it means maximum
breadth, depth, orthogonal discovery, certificates, forwards and survivor hunts. Max ROI
testable candidates mined is success, and certificates").

The seat scorecard defines PRODUCED as a log file over 1,500 bytes. That is output VOLUME: a dig
that writes three kilobytes of reasoning and mines nothing scores exactly like one that adds
fifty judgeable cells to the docket. Optimising that number is optimising token spend, which is
the opposite of the order. Worse, it is the same class as every defect found on this desk: a
metric that moves without the thing it claims to measure moving.

WHAT IS MEASURED INSTEAD, from artifacts the desk already writes:
  * TESTABLE candidates added to the docket -- judgeable cells only. A candidate the gauntlet
    must terminal-reject at gate 1, or one that cannot reach the 60 trading days the gates
    need, is not a yield; it is compute the cycle spent on a question no gate can answer.
  * BREADTH -- distinct asset classes and families the day's candidates touch, because the
    binding constraint is orthogonality (n_eff ~5.5 across 23 certificates), not cell count.
  * CERTIFICATES minted, and FORWARD clocks started. The end of the pipeline is the only
    unambiguous ROI.
  * COST -- launches spent to get it. Yield per launch is the ratio the principal is asking for.

A day with 200 statistical-only candidates and a day with 20 named, judgeable, class-diverse
ones are NOT the same day, and this report is where that stops being invisible.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "dig_roi.json"


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    now = datetime.now(tz=UTC)
    cutoff = now - timedelta(days=1)
    m: dict = {"measured_at": now.isoformat(timespec="seconds"), "window": "24h"}

    # --- TESTABLE candidates in the docket (judgeable, named mechanism)
    docket = _read(DESK / "data" / "hypotheses" / "external_survivors.json") or []
    named = [r for r in docket if isinstance(r, dict)
             and r.get("mechanism_status") == "NAMED"]
    fresh = []
    for r in named:
        seen = str(r.get("first_seen") or "")
        if seen and seen >= cutoff.isoformat():
            fresh.append(r)
    m["docket_total"] = len(docket)
    m["docket_named_testable"] = len(named)
    m["added_last_24h"] = len(fresh)

    # --- BREADTH: the binding constraint is orthogonality, not volume
    sys.path.insert(0, str(DESK))
    try:
        from mt5desk.universe import asset_class
        classes = Counter(asset_class(str(r.get("symbol") or r.get("sym") or ""))
                          for r in named)
        classes.pop("unknown", None)
    except Exception:
        classes = Counter()
    families = Counter(str(r.get("family") or "?") for r in named)
    m["classes_touched"] = len(classes)
    m["families_touched"] = len(families)
    m["by_class"] = dict(classes.most_common())
    m["top_families"] = dict(families.most_common(8))

    # --- THE END OF THE PIPELINE: certificates and clocks
    uni = _read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json") or {}
    survivors = uni.get("survivors") or {}
    m["certificates"] = len(survivors)
    # distinct RUNNABLE strategies, not certificate rows: rows without params are legacy
    # duplicates of parameterized twins and double-count the book (measured 2026-08-28: 23
    # rows, 17 distinct runnable strategies).
    runnable = [k for k, v in survivors.items()
                if isinstance(v, dict) and (v.get("shadow_spec") or {}).get("params")]
    m["certificates_runnable"] = len(runnable)
    new_certs = [k for k, v in survivors.items()
                 if isinstance(v, dict) and str(v.get("gated_at") or "") >= cutoff.isoformat()]
    m["certificates_last_24h"] = len(new_certs)

    shadow = _read(DESK / "reports" / "shadow" / "shadow_state.json") or {}
    active = [k for k, v in shadow.items()
              if isinstance(v, dict) and v.get("status") == "ACTIVE"]
    m["forward_clocks_active"] = len(active)
    m["forward_trades_total"] = sum(int(shadow[k].get("n") or 0) for k in active)

    # --- COST: launches spent for that yield
    sy = _read(ROOT / "data" / "seat_launch_yield.json") or {}
    launches = int(sy.get("launches") or 0)
    m["launches_7d"] = launches
    m["testable_per_launch"] = (round(len(named) / launches, 1) if launches else None)

    # --- THE VERDICT, in the principal's terms
    m["verdict"] = (
        f"{len(named)} testable candidates across {len(classes)} asset class(es) and "
        f"{len(families)} family(ies); {len(runnable)} runnable certificates, "
        f"{len(active)} forward clocks holding {m['forward_trades_total']} trade(s). "
        f"Bytes written are not counted here on purpose."
    )
    OUT.write_text(json.dumps(m, indent=1), "utf-8")
    print(m["verdict"])
    print(f"  by class: {m['by_class']}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
