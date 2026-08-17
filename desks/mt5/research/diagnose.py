"""diagnose.py — structured failure forensics + autonomous descendant generation.

For a hunt report (default: the most recent hunt18/hunt17), decompose WHERE_LOSS_OCCURRED
by direction / session / cost-state / maxDD, then generate descendant experiments that
remain in the SAME trial genealogy (geneology_id) so significance cannot be manufactured
by endless tweaking. Descendants are appended to data/research_queue.json for the
research_loop to execute autonomously.

Usage: python research/diagnose.py [hunt_file.json]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
QUEUE = BASE / "data" / "research_queue.json"
MAX_DESCENDANTS_PER_RUN = 3


def load_queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    try:
        return json.loads(QUEUE.read_text("utf-8"))
    except Exception:
        return []


def save_queue(q: list[dict]) -> None:
    QUEUE.write_text(json.dumps(q, indent=2, default=str), encoding="utf-8")


def diagnose(hunt_file: str) -> dict:
    report = json.loads((REPORTS / hunt_file).read_text("utf-8"))
    cells = report.get("all", [])
    if not cells:
        return {"n_cells": 0}
    df = pd.DataFrame(cells)
    out: dict = {"n_cells": len(df), "n_survivors": len(report.get("survivors", []))}
    # direction
    if "side" in df:
        by_side = df.groupby("side")[["exp", "t", "n"]].mean()
        out["where_loss"] = {
            "by_direction": {k: {"exp": round(float(v["exp"]), 4), "t": round(float(v["t"]), 2)}
                             for k, v in by_side.iterrows()},
        }
    # session (win key if present)
    if "win" in df:
        by_win = df.groupby("win")[["exp", "t"]].mean()
        out["where_loss"]["by_session"] = {k: {"exp": round(float(v["exp"]), 4),
                                               "t": round(float(v["t"]), 2)}
                                           for k, v in by_win.iterrows()}
    # family
    if "fam" in df:
        by_fam = df.groupby("fam")[["exp", "t", "n"]].agg({"exp": "mean", "t": "mean",
                                                            "n": "sum"})
        out["where_loss"]["by_family"] = {k: {"exp": round(float(v["exp"]), 4),
                                              "t": round(float(v["t"]), 2),
                                              "trades": int(v["n"])}
                                          for k, v in by_fam.iterrows()}
    # cost-state: how much of the edge dies under 2x stress
    if "exp" in df and "exp_stress" in df:
        decay = (df["exp"] - df["exp_stress"]).abs().mean()
        out["cost_state"] = {"mean_edge_decay_2x_costs": round(float(decay), 4)}
    # vol-state proxy: maxDD concentration
    if "maxdd" in df:
        worst = df.loc[df["maxdd"].idxmin()]
        out["vol_state"] = {"worst_cell_maxdd": round(float(worst["maxdd"]), 2),
                            "worst_cell": worst.to_dict()}
    return out


def descendants(hunt_file: str) -> list[dict]:
    """Generate param-level descendants of the failed population (same genealogy)."""
    report = json.loads((REPORTS / hunt_file).read_text("utf-8"))
    cells = report.get("all", [])
    if not cells:
        return []
    df = pd.DataFrame(cells)
    fams = sorted(df["fam"].unique()) if "fam" in df else ["d1_trend_pullback", "d1_swing_break",
                                                           "h4_momentum", "h4_vol_break",
                                                           "d1_inside"]
    gene = hunt_file.split(".")[0]
    out = []
    for f in fams:
        sub = df[df["fam"] == f] if "fam" in df else df
        neg = sub[sub["exp"] < 0]
        pos = sub[sub["exp"] > 0]
        side_neg = pos["side"].mode().iloc[0] if len(pos) and "side" in pos else "LONG"
        flip = "SHORT" if side_neg == "LONG" else "LONG"
        out.append({
            "id": f"{gene}-desc-{f}-flip", "geneology_id": f"{gene}:{f}",
            "hypothesis": (f"{f}: direction flip to {flip} — "
                           f"the losing side ({neg['side'].mode().iloc[0] if len(neg) and 'side' in neg else '?'}) "
                           f"showed mean exp {round(float(sub['exp'].mean()), 3)}; "
                           "opposite direction tests the anti-mechanism within the same genealogy"),
            "family": f, "side": flip,
            "params": {"rr": 1.5, "ttl": 24},
        })
    # tighten the least-bad cell if one exists
    best = cells[0]
    for c in cells:
        if c.get("exp", -9) > best.get("exp", -9):
            best = c
    if best.get("exp", -9) > -0.5 and len(out) < MAX_DESCENDANTS_PER_RUN:
        out.append({
            "id": f"{gene}-desc-{best.get('fam', 'cell')}-tighten", "geneology_id": f"{gene}:best",
            "hypothesis": (f"tighten the least-bad cell ({best.get('fam')} "
                           f"{best.get('side', '?')} exp {round(float(best['exp']), 3)}): "
                           "lower rr to 1.5 and longer ttl 24 — let winners run, cut the "
                           "2R-exit friction that dominated the loss profile"),
            "family": best.get("fam"), "side": best.get("side") or "LONG",
            "params": {"rr": 1.5, "ttl": 24},
        })
    return out[:MAX_DESCENDANTS_PER_RUN]


def main() -> int:
    hunt_file = sys.argv[1] if len(sys.argv) > 1 else "hunt18.json"
    d = diagnose(hunt_file)
    print(json.dumps(d, indent=2, default=str), flush=True)
    q = load_queue()
    for desc in descendants(hunt_file):
        if all(it.get("id") != desc["id"] for it in q):
            desc["created_at"] = datetime.now(timezone.utc).isoformat()
            desc["status"] = "QUEUED"
            q.append(desc)
    save_queue(q)
    print(f"diagnosis done; queue now has {len(q)} items", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())