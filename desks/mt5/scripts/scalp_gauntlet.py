"""Ten-gate certificates for the scalp lane: the same gauntlet every other cell walks.

WHY THIS EXISTS (principal, 2026-09-05): "backtest-equivalent gauntlets should exist for all
types of sleeves -- this is cheap; a lane with no gauntlet is third-world behaviour in our
quant." The four gold scalp candidates in `research/scalp_shadow.CANDIDATES` matured on a forward
clock alone, because `external_gauntlet` only knew how to build H1 family cells: no scalp spec
could ever hold a ten-gate certificate, so the promoter had to call the forward clock the lane's
certificate. That is a lane judged by a different bar from the rest of the book, which is the
one thing the universal-gate directive forbids.

WHAT THIS DOES. One cell per candidate, built from the box's own M5/M15 bars through
`mt5desk.scalp_families.family_scalp` (the executor's bracket, bar by bar), priced by the
sanctioned constructor at the honest 2x median-spread round trip (`external_gauntlet.costs_for`,
the same call site that prices every other cell), and handed to `external_gauntlet.run_gauntlet`
-- the ONE validator -- so the identical ten gates, thresholds and attestation judge them. Nothing
here re-implements a gate.

WHAT IT WRITES. reports/SCALP_GAUNTLET.json: every verdict, plus a `certificates` map of exact
ten-gate passes carrying a `shadow_spec` with the lane's whole recipe. It does NOT write the
canon: UNIVERSAL_SURVIVORS.json is held by one writer with never-shrink, never-empty and
purge-on-write rules, and a second pen on that file is how the certifier wipe happened.
`canon_rows()` hands that writer the rows under `scalp.<candidate>` in the shape it already
merges; `research/shadow_admission` reads them back as the promoter's tuple.

WHAT IT REFUSES. Bars absent, a registry without the symbol's cost fields, or a cell the gates
could not judge is UNMEASURED with the reason and a non-zero exit -- never a pass. And the
multiplicity charge is checked against the lane's FULL search history (`swept_grid`): the sealed
gate charges a fixed campaign count that the principal pinned as never sweep-dependent, and this
script mints nothing if that count ever falls below the trials the lane actually spent. The
census is reported beside the charge so the number can be checked rather than trusted.

Exit codes: 0 every candidate judged (pass or fail is a verdict either way); 2 UNMEASURED or
partially so, with the reasons in the report; 1 the script itself failed.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

BASE = Path(__file__).resolve().parents[3]
DESK = BASE / "desks" / "mt5"
UNI = DESK / "data" / "universe"
REPORTS = DESK / "reports"
OUT = REPORTS / "SCALP_GAUNTLET.json"
for _p in (BASE, DESK, DESK / "research", DESK / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import external_gauntlet as eg  # noqa: E402
from desks.mt5.research import scalp_shadow as _scalp_shadow  # noqa: E402
from desks.mt5.research.frontier_identity import cell_id  # noqa: E402
from desks.mt5.research.gate_policy import ATTESTATION, all_ten_pass, is_exact_policy  # noqa: E402
from shadow_admission import (  # noqa: E402
    SCALP_EXEC,
    SCALP_KEY_PREFIX,
    SCALP_RECIPE_KEYS,
)

from mt5desk.scalp_families import family_scalp, swept_grid, utc_frame  # noqa: E402

HUNT = "scalp_gauntlet"
SYMBOL = "XAUUSD"
#: The candidates are the lane's own declaration; this script never declares a cell of its own.
CANDIDATES = _scalp_shadow.CANDIDATES
#: `Costs.from_symbol`'s honest baseline: a round trip crosses the spread twice and a median is
#: a median. The 3x stress arm is the sealed gate's own and is not set here.
BASELINE_SPREAD_MULT = 2.0
RC_OK, RC_FAIL, RC_UNMEASURED = 0, 1, 2

#: Gate 1 is a mechanism, not a pattern. These are the lane's stated hypotheses, from
#: `scalp_family_expansion`: the anti-signals fade public patterns on the claim that
#: pattern-following flow is the liquidity and the pattern's own failure rate is the edge. A
#: hypothesis the ten gates can falsify -- which is all gate 1 asks.
MECHANISM: dict[str, str] = {
    "anti_donchian_breakout": (
        "fade the public 20-bar Donchian breakout on gold: breakout-following flow supplies "
        "the liquidity and the pattern's failure rate is the edge (anti-crowd hypothesis, "
        "scalp_family_expansion; selected on the first 60% of bars, confirmed on the untouched "
        "40%, stable across chronological thirds)"),
    "anti_three_bar_momentum": (
        "fade a three-bar momentum burst exceeding 1.25 ATR on gold: momentum-chasing flow "
        "supplies the liquidity and the burst's mean reversion is the edge (anti-crowd "
        "hypothesis, scalp_family_expansion; same selection discipline as above)"),
}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    """Write whole or not at all: a torn report reads as a missing gauntlet, not a partial one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


def mechanism_note(family: str) -> str:
    note = MECHANISM.get(family)
    if note:
        return note
    if family.startswith("anti_"):
        return (f"fade the public {family[5:]} pattern on gold: pattern-following flow is the "
                f"liquidity (anti-crowd hypothesis, scalp_family_expansion)")
    return (f"public gold scalp pattern {family} "
            f"(scalp_family_expansion / scalp_reverse_engineering)")


def recipe(tf: str, choice: Any) -> dict[str, Any]:
    """The exact executable the gateway trades (`promoter.promote_scalp` writes these six keys)."""
    return {"timeframe": str(tf), "family": str(choice.family),
            "session": str(choice.session or "all"), "stop_atr": float(choice.stop_atr),
            "target_atr": float(choice.target_atr), "max_hold": int(choice.max_hold)}


def shadow_spec(name: str, tf: str, choice: Any) -> dict[str, Any]:
    """The certificate's spec: the whole recipe, the side, the executor, and the generic fields
    every other spec carries so a reader that does not know the lane still sees a complete row."""
    r = recipe(tf, choice)
    return {"symbol": SYMBOL, "selector": str(name), **r,
            # The lane fires both ways and `scalp_exec.plan_entry` plans either; declared so no
            # reader has to assume, which is how a certified SHORT once ran LONG on the main lane.
            "side": "BOTH", "exec": SCALP_EXEC, "lane": "scalp", "is_universe": False,
            "hunt": HUNT, "condition": None, "params": dict(r)}


def load_bars(tf: str, data_dir: Path) -> tuple[pd.DataFrame | None, str]:
    """The box's own bars for `tf`, UTC and de-duplicated, or (None, why)."""
    path = Path(data_dir) / f"{SYMBOL}_{tf}.parquet"
    if not path.exists():
        return None, f"no {path.name} on this box: the {tf} tape is absent, nothing to judge"
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        return None, f"{path.name} unreadable: {type(exc).__name__}: {exc}"
    if not isinstance(df.index, pd.DatetimeIndex) or len(df) == 0:
        return None, f"{path.name} carries no datetime-indexed bars"
    missing = [c for c in ("open", "high", "low", "close") if c not in df.columns]
    if missing:
        return None, f"{path.name} lacks {missing}"
    return utc_frame(df), ""


def build_cell(name: str, tf: str, choice: Any, bars: pd.DataFrame,
               meta: dict[str, Any]) -> dict[str, Any]:
    """One gauntlet cell in the shape `run_gauntlet` consumes, priced by the sanctioned model."""
    sigs = family_scalp(bars, family=choice.family, session=choice.session,
                        stop_atr=choice.stop_atr, target_atr=choice.target_atr,
                        max_hold=choice.max_hold, tag=name)
    costs = eg.costs_for(SYMBOL, meta, mult=BASELINE_SPREAD_MULT)
    params = recipe(tf, choice)
    return {
        "sym": SYMBOL, "family": str(choice.family), "params": params,
        "df": bars, "sigs": sigs, "costs": costs,
        "mechanism_status": "NAMED", "mechanism_note": mechanism_note(str(choice.family)),
        "_cost_basis": f"pooled_median_spread_x{BASELINE_SPREAD_MULT:g}",
        # The sealed sweep's own partial-day boundary, in the sealed sweep's own shape
        # (`frame.index[-1].normalize()`), handed to its own `_series_trim_partial`. Same value,
        # same helper, same outcome as every H1 cell -- whatever that helper does with it. The
        # four scalp columns share one tape end, so they align among themselves regardless.
        "_last_day": pd.Timestamp(bars.index[-1]).normalize(),
        "_scalp": {"name": str(name), "timeframe": str(tf), "bars": len(bars),
                   "first_bar": pd.Timestamp(bars.index[0]).isoformat(),
                   "last_bar": pd.Timestamp(bars.index[-1]).isoformat(),
                   "signals": len(sigs),
                   "cell": cell_id({"sym": SYMBOL, "family": str(choice.family),
                                    "params": params}),
                   "cost": {"spread_per_lot": float(costs.spread_per_lot),
                            "commission_per_lot": float(costs.commission_per_lot),
                            "contract_oz": float(costs.contract_oz),
                            "quote_per_account": float(costs.quote_per_account),
                            "round_trip_per_oz": float(costs.per_oz_roundtrip()
                                                       / costs.contract_oz)}},
    }


def _cost_basis(meta: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    """The registry row that prices the symbol, or (None, why). An absent row is not a free
    symbol: `Costs.from_symbol({})` prices at a 0.05 spread and no conversion, which is exactly
    the silent undercharge the sealed sweep documents -- so the lane is UNMEASURED instead."""
    if not isinstance(meta, dict) or not meta:
        return None, "no universe registry: the cost basis is absent, so nothing can be priced"
    row = meta.get(SYMBOL)
    if not isinstance(row, dict):
        return None, f"{SYMBOL} is absent from the universe registry: no cost basis"
    if row.get("tradeable") is False:
        return None, (f"{SYMBOL} is CLOSE_ONLY on this account (trade_mode "
                      f"{row.get('trade_mode')}); a certificate could never open a position")
    if float(row.get("median_spread_pts") or 0.0) <= 0 or float(row.get("tick_size") or 0.0) <= 0:
        return None, (f"{SYMBOL} registry row carries no spread/tick fields; pricing it would "
                      f"charge the constructor's floor, not the market")
    return row, ""


def _read_meta(data_dir: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads((Path(data_dir) / "universe.json").read_text("utf-8"))
        return doc if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return None


def run(*, meta: dict[str, Any] | None = None, data_dir: Path | None = None,
        out: Path | None = None, gauntlet: Any = None,
        candidates: dict[str, tuple[str, Any]] | None = None,
        now: datetime | None = None) -> dict[str, Any]:
    """Build, judge, and report. Returns the report; `rc` on it is the exit code."""
    data_dir = Path(data_dir or UNI)
    out = Path(out or OUT)
    candidates = dict(CANDIDATES if candidates is None else candidates)
    stamp = (now or datetime.now(UTC)).isoformat()
    judge = gauntlet or eg.run_gauntlet
    grid = swept_grid()
    report: dict[str, Any] = {
        "hunt": HUNT, "symbol": SYMBOL, "swept_at": stamp, "gate_policy": ATTESTATION,
        "validator": "external_gauntlet.run_gauntlet (the one validator; no gate is "
                     "re-implemented here)",
        "cost_basis": {"constructor": "Costs.from_symbol via external_gauntlet.costs_for",
                       "spread_mult": BASELINE_SPREAD_MULT,
                       "stress": "the sealed gate's own 3x arm (external_gauntlet.COST_SCENARIO)"},
        "adapter": "mt5desk.scalp_families.family_scalp (deviations from "
                   "scalp_reverse_engineering.simulate stated in its docstring)",
        "declared_candidates": len(candidates),
        "candidates": {}, "unmeasured": {}, "verdicts": [], "certificates": {},
        "certificates_withheld": {}, "multiplicity": grid, "gauntlet": {},
        "status": "UNMEASURED", "rc": RC_UNMEASURED,
    }
    meta = _read_meta(data_dir) if meta is None else meta
    cost_row, why = _cost_basis(meta)
    cells: list[dict[str, Any]] = []
    if cost_row is None:
        for name, (tf, _choice) in candidates.items():
            report["unmeasured"][name] = {"timeframe": tf, "why": why}
    else:
        frames: dict[str, tuple[pd.DataFrame | None, str]] = {}
        for name, (tf, choice) in candidates.items():
            if tf not in frames:
                frames[tf] = load_bars(tf, data_dir)
            bars, why = frames[tf]
            if bars is None:
                report["unmeasured"][name] = {"timeframe": tf, "why": why}
                continue
            try:
                cell = build_cell(name, tf, choice, bars, meta)  # type: ignore[arg-type]
            except Exception as exc:
                report["unmeasured"][name] = {
                    "timeframe": tf,
                    "why": f"cell could not be built: {type(exc).__name__}: {exc}"}
                continue
            cells.append(cell)
            report["candidates"][name] = {"choice": dict(choice.__dict__), **cell["_scalp"],
                                          "cost_basis": cell["_cost_basis"]}

    result: dict[str, Any] = {"verdicts": []}
    if cells:
        result = judge(cells, HUNT, meta)
    by_cell = {c["_scalp"]["cell"]: c["_scalp"] for c in cells}
    for v in result.get("verdicts") or []:
        info = by_cell.get(str(v.get("cell")), {})
        report["verdicts"].append({**v, "candidate": info.get("name"),
                                   "timeframe": info.get("timeframe")})

    # THE CHARGE MUST COVER THE SEARCH. `run_gauntlet` charges the sealed fixed campaign count;
    # this lane spent `grid["total"]` trials finding its four survivors. A charge below that is
    # not a harsher bar to substitute -- the sealed policy is not this script's to change -- it
    # is a reason to mint nothing until the policy and the search agree.
    charged = int(result.get("n_trials") or 0)
    covered = charged >= int(grid["total"]) and charged > 0
    report["multiplicity"].update({
        "charged_n_trials": charged, "charged_basis": result.get("trial_count_basis"),
        "covered_by_charge": bool(covered),
        "note": ("the sealed deflated-Sharpe charge is a fixed campaign count (gate_spec.yaml); "
                 "certificates are minted only while it is at least the lane's full swept grid"),
    })
    for v in report["verdicts"]:
        name = v.get("candidate")
        if not name or v.get("passed") is not True or not all_ten_pass(v.get("stages")):
            continue
        tf, choice = candidates[name]
        if not covered:
            report["certificates_withheld"][name] = {
                "cell": v.get("cell"),
                "why": (f"charged {charged} trials against a swept grid of {grid['total']}: "
                        f"the census is undercharged and a certificate would be a fake pass")}
            continue
        report["certificates"][name] = {
            "cell": v.get("cell"), "sym": SYMBOL, "days": v.get("days"),
            "gates": v.get("stages"), "gated_at": stamp,
            "shadow_spec": shadow_spec(name, tf, choice),
            "cost_basis": report["candidates"].get(name, {}).get("cost_basis"),
            "n_trials": charged,
        }

    report["gauntlet"] = {k: val for k, val in result.items() if k != "verdicts"}
    n_judged = sum(1 for v in report["verdicts"]
                   if v.get("candidate") and not v.get("unmeasured") and v.get("stages"))
    for v in report["verdicts"]:
        if v.get("unmeasured") and v.get("candidate"):
            report["unmeasured"][v["candidate"]] = {
                "timeframe": v.get("timeframe"),
                "why": ((v.get("stages") or {}).get("observations") or {}).get(
                    "why", "the gauntlet could not judge this cell")}
    if n_judged == 0:
        report["status"], report["rc"] = "UNMEASURED", RC_UNMEASURED
    elif report["unmeasured"]:
        report["status"], report["rc"] = "PARTIAL", RC_UNMEASURED
    else:
        report["status"], report["rc"] = "MEASURED", RC_OK
    report["n_judged"] = n_judged
    report["n_certified"] = len(report["certificates"])
    _atomic_json(out, report)
    return report


def canon_rows(report_path: Path = OUT) -> dict[str, dict[str, Any]]:
    """The certificate rows for UNIVERSAL_SURVIVORS.json, keyed `scalp.<candidate>`.

    Called by the canon's one writer (see the wiring in `external_gauntlet.main`), never by this
    script: the merge rules -- never shrink, never write empty, purge uncashable rows, file the
    ledger claim -- live with the pen. Only exact ten-gate passes under the exact attestation are
    returned; anything else is an empty dict, which merges nothing and revokes nothing.
    """
    try:
        doc = json.loads(Path(report_path).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict) or not is_exact_policy(doc.get("gate_policy")):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for name, cert in (doc.get("certificates") or {}).items():
        if not isinstance(cert, dict) or not all_ten_pass(cert.get("gates")):
            continue
        spec = cert.get("shadow_spec")
        if not isinstance(spec, dict) or not {"symbol", *SCALP_RECIPE_KEYS} <= set(spec):
            continue
        rows[f"{SCALP_KEY_PREFIX}{name}"] = {
            "hunt": HUNT, "cell": cert.get("cell"), "sym": str(spec["symbol"]),
            "days": cert.get("days"), "gates": cert["gates"],
            "gated_at": cert.get("gated_at") or doc.get("swept_at"),
            "shadow_spec": dict(spec), "lane": "scalp", "exec": SCALP_EXEC,
        }
    return rows


def main(argv: list[str] | None = None) -> int:
    try:
        report = run()
    except Exception as exc:
        print(f"scalp_gauntlet FAILED: {type(exc).__name__}: {exc}")
        return RC_FAIL
    print(f"\nSCALP GAUNTLET: {report['status']} -- {report['n_judged']} judged, "
          f"{report['n_certified']} certified, {len(report['unmeasured'])} unmeasured; "
          f"charge {report['multiplicity'].get('charged_n_trials')} vs swept grid "
          f"{report['multiplicity']['total']} -> {OUT}")
    for name, row in report["unmeasured"].items():
        print(f"  UNMEASURED {name}: {row['why']}")
    for name, row in report["certificates_withheld"].items():
        print(f"  WITHHELD {name}: {row['why']}")
    for name in report["certificates"]:
        print(f"  CERTIFIED {name} -> canon key {SCALP_KEY_PREFIX}{name} (merged by the canon "
              f"writer, not here)")
    return int(report["rc"])


if __name__ == "__main__":
    raise SystemExit(main())
