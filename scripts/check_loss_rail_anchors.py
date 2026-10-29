"""RED when an ARMED loss rail does not publish its anchor and headroom, or publishes them stale.

MEASURED 2026-10-29: the Fusion deadman's weekly-loss rail was ARMED at -19.5% from peak and its
stamp (`desks/mt5/data/fusion_deadman_state.json`) recorded neither what the 20% was 20% OF nor
how far the realised week stood from it. A rail whose distance to tripping nobody can read is a
rail nobody can plan around (L1.28a: absence never resolves to a clean verdict).

THE CLASS, not the instance: every stamp matched by STAMP_GLOBS that is ARMED (`mode == "LIVE"`
or `armed.principal` true) and declares any `*_LOSS_PCT` rail in its `rails` block must carry,
for each such rail, `loss_rails[<CODE>]` with a numeric anchor, an anchor_ts, a window_start, and
-- when `measured` -- numeric loss_frac, headroom_frac and headroom_ccy. `measured: false` is an
UNMEASURED headroom on an armed rail and is RED too. A stamp whose `checked_at` is older than
--max-age-h is RED. An unarmed stamp is reported and passes; no stamp at all is UNMEASURED and
passes unless --require-state. Reads only; changes no threshold.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP_GLOBS = ("desks/mt5/data/*deadman*_state.json", "desks/mt5/data/*loss_rail*_state.json")
REQUIRED = ("anchor", "anchor_ts", "window_start")
MEASURED_REQUIRED = ("loss_frac", "headroom_frac", "headroom_ccy")


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def armed(stamp: dict) -> bool:
    a = stamp.get("armed")
    return stamp.get("mode") == "LIVE" or (isinstance(a, dict) and a.get("principal") is True)


def judge(stamp: dict, *, now: datetime, max_age_h: float) -> list[str]:
    """Defects of one stamp (empty = clean). Pure."""
    if not armed(stamp):
        return []
    out: list[str] = []
    try:
        at = datetime.fromisoformat(str(stamp.get("checked_at")).replace("Z", "+00:00"))
        age = (now - at).total_seconds() / 3600
        if age > max_age_h:
            out.append(f"stamp is {age:.1f}h old (> {max_age_h:g}h)")
    except ValueError:
        out.append("checked_at absent or unparseable")
    codes = [k[: -len("_PCT")] for k in (stamp.get("rails") or {}) if k.endswith("_LOSS_PCT")]
    blocks = stamp.get("loss_rails") if isinstance(stamp.get("loss_rails"), dict) else {}
    for code in codes:
        b = blocks.get(code)
        if not isinstance(b, dict):
            out.append(f"{code}: no loss_rails entry (anchor and headroom unpublished)")
            continue
        miss = [k for k in REQUIRED if b.get(k) in (None, "")]
        if not _num(b.get("anchor")) or (b.get("anchor") or 0) <= 0:
            miss.append("anchor>0")
        if b.get("measured") is not True:
            out.append(f"{code}: headroom UNMEASURED on an armed rail")
        else:
            miss += [k for k in MEASURED_REQUIRED if not _num(b.get(k))]
        if miss:
            out.append(f"{code}: missing {sorted(set(miss))}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--max-age-h", type=float, default=2.0)
    ap.add_argument("--require-state", action="store_true")
    a = ap.parse_args(argv)
    now = datetime.now(tz=UTC)
    paths = sorted({p for g in STAMP_GLOBS for p in a.root.glob(g)})
    if not paths:
        print("check_loss_rail_anchors: UNMEASURED -- no loss-rail stamp on this tree")
        return 1 if a.require_state else 0
    red = 0
    for p in paths:
        try:
            stamp = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError) as exc:
            print(f"RED {p.name}: unreadable ({type(exc).__name__})")
            red += 1
            continue
        if not isinstance(stamp, dict):
            continue
        defects = judge(stamp, now=now, max_age_h=a.max_age_h)
        if stamp.get("stamp_state") == "LOST":
            print(f"AMBER {p.name}: STAMP LOST -- peak restarted at current equity, the anchor "
                  f"may have moved down ({stamp.get('peak_equity_ts_basis')})")
        if not armed(stamp):
            print(f"ok  {p.name}: not armed ({stamp.get('mode')})")
        elif defects:
            red += 1
            print(f"RED {p.name}: " + "; ".join(defects))
        else:
            w = (stamp.get("loss_rails") or {}).get("WEEKLY_LOSS") or {}
            print(f"ok  {p.name}: armed; weekly headroom {w.get('headroom_ccy')} "
                  f"of anchor {w.get('anchor')}")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
