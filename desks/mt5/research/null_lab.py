#!/usr/bin/env python3
"""THE NULL LAB, HOURLY: every hunted family's own pipeline on data where no edge can exist.

    python desks/mt5/research/null_lab.py                   # one budgeted pass, write the report
    python desks/mt5/research/null_lab.py --budget-s 60     # a shorter pass
    python desks/mt5/research/null_lab.py --dry-run         # measure and print, write nothing

The library (`libs/research/null_lab.py`) says what the three nulls are and why each exists. This
file is the organ: it picks the families the desk actually hunts (every family in the docket,
`data/hypotheses/external_survivors.json`), takes one of THAT family's own docketed specs, and
hands `external_gauntlet.build_cell` -- the gauntlet's own cell builder, read-only, the one door
every certificate walks through -- a frame on which no edge can exist. The cell's signals are
backtested by the desk's engine and scored by the gauntlet's per-cell statistics.

BOUNDED BY A BUDGET, ACCUMULATED ACROSS HOURS. One draw is one backtest; sixty families times
three arms times the dozens of draws a rate needs is far more than an hour. So each pass spends
its budget on the (family, arm) pairs with the FEWEST draws so far and appends every draw to
`reports/null_lab_draws.jsonl`; the report is the summary of the whole ledger. A pass that is killed
loses at most the draw it was in -- every finished draw is already on disk.

A DRAW THAT COULD NOT RUN IS RECORDED, NEVER DROPPED: a family whose inputs cannot be rebuilt, a
chart that is absent, a builder that raises -- each is a `NOT_RUN` row with its reason, so a
family with no measurement reads UNMEASURED with the why attached, not as a clean null.

THE CONSEQUENCE, and where it lands: `families[*].fpr_charge` is read by the Tier S online-FDR
organ (`desks/mt5/research/tier_s.py organ_online_fdr` -> `libs/tiers/online_fdr
.charge_null_fpr`), which multiplies that family's p-values by it before the lifetime LORD++ /
e-LOND replay. A family whose deflated-Sharpe gate passes its own null above 5% therefore spends
more lifetime budget per certificate, and a certificate that can no longer afford its level
reads `over_budget` -- which the promotion door already withholds on. `exceeds_nominal` names
each such family as a defect in the report itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from libs.research import null_lab as nl  # noqa: E402

REPORT = BASE / "reports" / "NULL_LAB.json"
#: the draw ledger, append-only, beside the report (placebo_audit_history.jsonl's precedent):
#: gitignored like every report, because it grows by ~100 KB an hour on the box
LEDGER = BASE / "reports" / "null_lab_draws.jsonl"
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
UNI = BASE / "data" / "universe"
SEED = 20260930
#: bars per draw from the spec's own chart, most recent window; 0 = the whole chart, which is
#: what the gauntlet judges. A year of H1 left most low-frequency families under the gauntlet's
#: own 60-day floor, so their gate could not be judged on the null at all.
NULL_BARS = 0
#: specs tried per draw before it is recorded NOT_RUN. A docketed spec whose modifier the
#: gauntlet refuses (`NOT_RUN_MODIFIER`) carries no certificate either, so it is not the
#: population whose false-positive rate matters: the family's next spec is tried instead.
SPEC_TRIES = 6
DEFAULT_BUDGET_S = 600.0
#: a draw is not STARTED with less than this left: one draw on a feature-heavy family is ~10 s
MARGIN_S = 30.0
#: the ledger tail read for the summary (draw rows are ~600 bytes)
MAX_LEDGER_ROWS = 200_000
#: candidate specs considered per family per draw
SPEC_SAMPLE = 64


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def read_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text("utf-8").splitlines()[-MAX_LEDGER_ROWS:]
    except OSError:
        return rows
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def docket_specs(docket: Any) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """family -> its docketed (symbol, params) specs, in docket order."""
    out: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for r in docket if isinstance(docket, list) else []:
        if not isinstance(r, dict) or not r.get("family") or not r.get("symbol"):
            continue
        params = r.get("params")
        out.setdefault(str(r["family"]), []).append(
            (str(r["symbol"]), dict(params) if isinstance(params, dict) else {}))
    return out


def next_pairs(families: list[str], ledger: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Every (family, arm), fewest draws first: the budget goes where the rate is least known."""
    have = Counter((str(r.get("family")), str(r.get("arm"))) for r in ledger)
    pairs = [(f, a) for f in families for a in nl.ARMS]
    return sorted(pairs, key=lambda fa: (have[fa], fa[0], fa[1]))


def _chart(sym: str, tf: str) -> Path:
    return UNI / f"{sym}_{tf}.parquet"


def _params_hash(params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()
                          ).hexdigest()[:16]


def _daily(trades: list[Any]) -> list[float]:
    """`external_gauntlet.daily_series`, over the trades already in hand: R summed per entry
    day."""
    by: dict[Any, float] = {}
    for t in trades:
        import pandas as pd
        d = pd.Timestamp(t.entry_time).date()
        by[d] = by.get(d, 0.0) + float(t.r_multiple)
    return [by[k] for k in sorted(by)]


def one_draw(eg: Any, family: str, arm: str, specs: list[tuple[str, dict[str, Any]]],
             meta: dict[str, Any], seed: int) -> dict[str, Any]:
    """One null draw for one family: pick a spec whose chart is on disk, build the null, run the
    gauntlet's cell builder, backtest, score. Never raises: failure is a NOT_RUN row."""
    import pandas as pd
    from mt5desk.engine import run_backtest
    rng = np.random.default_rng(seed)
    row: dict[str, Any] = {"at": datetime.now(UTC).isoformat(timespec="seconds"),
                           "family": family, "arm": arm, "seed": seed}
    idx = rng.permutation(len(specs))[:SPEC_SAMPLE]
    candidates = [specs[int(i)] for i in idx]
    candidates = [(s, p, eg.timeframe_of(p, family)) for s, p in candidates]
    candidates = [c for c in candidates if c[0] in meta and _chart(c[0], c[2]).exists()]
    if not candidates:
        return {**row, "status": "NOT_RUN",
                "why": "no docketed spec of this family has its chart and registry row here"}
    tried: list[str] = []
    trades: list[Any] | None = None
    sigs: list[Any] = []
    for sym, params, tf in candidates[:SPEC_TRIES]:
        row.update({"symbol": sym, "timeframe": tf, "params_hash": _params_hash(params)})
        try:
            bars = pd.read_parquet(_chart(sym, tf))
            bars = bars.tail(NULL_BARS) if NULL_BARS else bars
            if arm == "block_shuffle":
                frame = nl.block_shuffle(bars, rng)
            elif arm == "random_walk":
                frame = nl.random_walk(bars, rng)
            else:
                frame = bars
            cell = eg.build_cell(sym, family, params, meta, h1_override=frame)
            if cell is None:
                tried.append(f"build_cell: {getattr(eg, 'LAST_BUILD_FAILURE', None) or 'None'}")
                continue
            sigs = list(cell.get("sigs") or [])
            if arm == "sign_permute":
                sigs = nl.sign_permute(sigs, cell["df"], rng)
            trades = list(run_backtest(cell["df"], sigs, cell["costs"]).trades)
            break
        except Exception as exc:                       # one family never takes the pass
            tried.append(f"{type(exc).__name__}: {str(exc)[:160]}")
    row["specs_tried"] = len(tried) + (trades is not None)
    if trades is None:
        return {**row, "status": "NOT_RUN", "why": (tried[-1] if tried else "no spec ran")[:200]}
    row["n_signals"] = len(sigs)
    row["stats"] = nl.gate_stats([float(t.r_multiple) for t in trades], _daily(trades))
    row["status"] = "RUN"
    return row


def run(budget_s: float = DEFAULT_BUDGET_S, *, ledger_path: Path = LEDGER,
        dry_run: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    docket = _read_json(DOCKET)
    specs = docket_specs(docket)
    meta = _read_json(UNI / "universe.json") or {}
    ledger = read_ledger(ledger_path)
    blocked = None
    drawn: list[dict[str, Any]] = []
    if not specs:
        blocked = f"UNMEASURED: no docket at {DOCKET.relative_to(ROOT).as_posix()}"
    else:
        try:
            import external_gauntlet as eg
        except Exception as exc:
            eg = None
            blocked = f"BLOCKED: external_gauntlet not importable ({type(exc).__name__}: {exc})"
        if eg is not None:
            count = len(ledger)
            for family, arm in next_pairs(sorted(specs), ledger):
                if time.monotonic() - t0 > budget_s - MARGIN_S:
                    break
                seed = SEED + count + len(drawn)
                d = one_draw(eg, family, arm, specs[family], meta, seed)
                d["elapsed_s"] = round(time.monotonic() - t0, 2)
                drawn.append(d)
                if not dry_run:
                    ledger_path.parent.mkdir(parents=True, exist_ok=True)
                    with ledger_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(d, default=str) + "\n")
    fams = nl.summarise([*ledger, *drawn])
    exceeds = sorted(f for f, r in fams.items()
                     if (r["gates"][nl.CHARGED_GATE].get("exceeds_nominal")))
    unmeasured = sorted(set(specs) - {f for f, r in fams.items() if r["status"] == "MEASURED"})
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": blocked or "MEASURED",
        "budget_s": budget_s, "elapsed_s": round(time.monotonic() - t0, 2),
        "draws_this_pass": len(drawn),
        "run_this_pass": sum(1 for d in drawn if d.get("status") == "RUN"),
        "ledger_draws": len(ledger) + len(drawn),
        "families_hunted": len(specs), "families_measured": len(specs) - len(unmeasured),
        "unmeasured_families": unmeasured,
        "charged_gate": nl.CHARGED_GATE, "nominal": nl.NOMINAL,
        # THE NAMED DEFECTS: a family whose deflated-Sharpe gate passes its own null above the
        # gate's nominal level, with the Wilson lower bound (not the point rate) above it.
        "exceeds_nominal": exceeds,
        "defects": [{"family": f, "defect": "NULL_PASS_RATE_ABOVE_NOMINAL",
                     "rate": fams[f]["gates"][nl.CHARGED_GATE]["rate"],
                     "wilson": fams[f]["gates"][nl.CHARGED_GATE]["wilson"],
                     "nominal": fams[f]["gates"][nl.CHARGED_GATE]["nominal"],
                     "fpr_charge": fams[f]["fpr_charge"]} for f in exceeds],
        "charges": nl.charges({"families": fams}),
        "families": fams,
        "arms": list(nl.ARMS), "bars_per_draw": NULL_BARS,
        "pipeline": ("external_gauntlet.build_cell(h1_override=<null frame>) -> "
                     "mt5desk.engine.run_backtest -> the gauntlet's per-cell statistics"),
        "consumer": ("desks/mt5/research/tier_s.py organ_online_fdr -> "
                     "libs/tiers/online_fdr.charge_null_fpr (p x fpr_charge before the lifetime "
                     "LORD++/e-LOND replay; over_budget certificates are withheld by "
                     "libs/tiers/promotion_authority._fdr)"),
    }
    if not dry_run:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(REPORT)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(a.budget_s, dry_run=a.dry_run)
    print(f"null lab: {doc['status']} draws={doc['draws_this_pass']} "
          f"(run {doc['run_this_pass']}) ledger={doc['ledger_draws']} "
          f"measured={doc['families_measured']}/{doc['families_hunted']} "
          f"exceeds_nominal={doc['exceeds_nominal']}")
    return 0 if doc["status"] == "MEASURED" else 2


if __name__ == "__main__":
    sys.exit(main())
