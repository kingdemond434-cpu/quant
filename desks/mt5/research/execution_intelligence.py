"""Daily execution intelligence: refit the fill/slip surface, measure netting, price the leak.

Cycle entry point (`daily_cycle._state_research_feedback`).

WHAT THIS ORGAN ANSWERS. Three questions, in the order a desk should ask them. What does the
venue actually charge (`fill_surface`)? How much of that did the desk avoid paying by netting
opposing intents (`netting`)? And -- added 2026-09-05, the principal's order -- how much of the
research edge survived contact with the broker at all:

    AlphaCapture = realised edge / predicted FRICTIONLESS edge, per sleeve, session and symbol

"A strategy with +0.25R theoretical expectancy that loses 0.08R through execution has 0.17R.
Recover 0.04R of that and you've increased actual edge 24% without discovering another signal."
That is a capture ratio of 0.68 going to 0.84, and it is the one number that separates a strategy
which stopped working from a strategy which works exactly as researched and is being taken apart
between the decision and the fill. Those two have identical equity curves and opposite remedies.

IT IS TRENDED, NOT JUST REPORTED. Each daily pass appends one point -- ratio, n, the leakage
decomposition -- to `data/alpha_capture_history.jsonl`, and `reports/ALPHA_CAPTURE.json` carries
the slope over that history. A capture ratio measured once is a fact about last month; a capture
ratio with a slope is a control loop.

THE INPUT IS THE FILL CORPUS, WRITTEN BY THE HOURLY TWIN. This organ reads
`data/fill_corpus.jsonl` and computes; it never assembles the corpus itself, because the join
belongs next to the ledgers that resolve late and the twin already owns that clock. An empty or
absent corpus is reported as UNMEASURED with the reason and the sample each blocked model still
needs -- never as a capture ratio of zero, which would read as an execution catastrophe when in
fact nothing has traded.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import execution_registry, fill_surface, netting  # noqa: E402

from libs.execution import alpha_capture as ac  # noqa: E402
from libs.execution import execution_choice_model as ecm  # noqa: E402
from libs.execution import fill_corpus as fc  # noqa: E402
from libs.execution import meta_label as ml  # noqa: E402

#: The corpus the hourly execution twin assembles, and this organ's own two artifacts.
CORPUS = _DESK / "data" / "fill_corpus.jsonl"
HISTORY = _DESK / "data" / "alpha_capture_history.jsonl"
CAPTURE_REPORT = _DESK / "reports" / "ALPHA_CAPTURE.json"
#: THE SHADOW TAPE: `mt5desk.shadow_execution` reconstructs every shadow decision against the
#: venue's own recorded quotes -- a simulated STOP fill at the far side of the spread, its
#: slippage in R and the spread at the fill -- per symbol and session. It is the only execution
#: measurement this desk has produced (the fill corpus has never had a row), so when the corpus
#: is absent the capture ratio is computed from it, labelled `basis: shadow_tape`, and never
#: appended to the live capture history. The shadow ledgers beside it carry the bracket-price R
#: the decision was worth BEFORE any friction: that is the frictionless denominator.
SHADOW_TAPE = _DESK / "reports" / "execution_quality.json"
SHADOW_LEDGERS = _DESK / "reports" / "shadow"
SHADOW_BASIS = "shadow_tape"

#: The meta-label columns the daily report prices a sample requirement for. Must match the hourly
#: organ's scan width, or the two reports would quote different Bonferroni charges for one model.
META_LABEL_FEATURES: tuple[str, ...] = (
    "posterior_edge_r", "spread_frac_at_decision", "vol_frac", "momentum_z", "slip_r",
    "predicted_p_fill", "latency_decision_to_send_ms",
)


def _book_report() -> dict:
    """The theoretical-position ledger's savings, when the gateway has written one.

    The intent-based report above counts opposing INTENTS; the ledger counts opposing
    theoretical POSITIONS and prices the spread the netting saved against each symbol's own
    spread. An absent ledger is reported as such -- a box that has not run the wired gateway
    has no netting evidence yet, which is a different fact from "nothing to net".
    """
    try:
        book = netting.TheoreticalBook()
        if not book.symbols():
            return {"verdict": "UNMEASURED", "why": "no theoretical positions recorded yet"}
        return netting.savings_report(book, write=True)
    except Exception as exc:
        return {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


def _history() -> list[dict[str, Any]]:
    return fc.read_rows(HISTORY)


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _f(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def bracket_expectancy(ledger_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Per `<SYMBOL>.<session>` cell: the mean bracket-price R of the shadow decisions and their
    mean risk distance, from the same ledgers the tape reconstructed
    (`shadow_execution.collect`: ledger_<SYMBOL>_<session>.json, rows with entry/exit/r_multiple).

    The bracket R assumes a fill AT the intended level with no spread and no slippage -- exactly
    the frictionless edge `alpha_capture.frictionless_edge_r` demands as a denominator, and the
    reason the canon's `expected_value.ev` (charged with the modelled cost) is not used: that
    would be the cost model measured against itself.
    """
    # Resolved at CALL time, not bound at definition: the module paths are what a test or a
    # caller repoints, and a default frozen at import would read the box's real ledgers.
    ledger_dir = SHADOW_LEDGERS if ledger_dir is None else ledger_dir
    out: dict[str, dict[str, Any]] = {}
    try:
        ledgers = sorted(ledger_dir.glob("ledger_*.json"))
    except OSError:
        return out
    for ledger in ledgers:
        rows = _json_list(ledger)
        stem = ledger.stem[len("ledger_"):]
        parts = stem.split("_")
        key = f"{parts[0]}.{'_'.join(parts[1:]) or 'unknown'}"
        rs, risks = [], []
        for row in rows:
            r = _f(row.get("r_multiple"))
            if r is None:
                continue
            rs.append(r)
            entry, exit_ = _f(row.get("entry")), _f(row.get("exit"))
            if entry is not None and exit_ is not None and abs(r) > 1e-9:
                risk = abs((exit_ - entry) / r)
                if risk > 0:
                    risks.append(risk)
        if rs:
            out[key] = {"n": len(rs), "mean_r": sum(rs) / len(rs),
                        "mean_risk": (sum(risks) / len(risks) if risks else None),
                        "ledger": ledger.name}
    return out


def _json_list(path: Path) -> list[dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in doc if isinstance(r, dict)] if isinstance(doc, list) else []


def shadow_tape_capture(tape_path: Path | None = None,
                        ledger_dir: Path | None = None) -> dict[str, Any]:
    """The capture ratio from SIMULATED fills, per symbol/session, labelled so it can never be
    read as live capture.

        realised_shadow = bracket R - slippage_R - spread_R / 2
        ratio           = realised_shadow / bracket R

    Half the quoted spread, not the whole: the reconstructed fill is already taken at the far
    side of the book (`shadow_execution.reconstruct`, the "taker pays the far side" branch), so
    the entry crossing is inside `slippage_R`; the exit crossing is the half charged here. A
    cell needs `alpha_capture.MIN_N` fills with slippage in R, a ledger to supply its bracket
    expectancy, and a denominator above `alpha_capture.MIN_DENOM_R`; anything short of that is
    UNMEASURED with the reason. Nothing here is appended to the live history.
    """
    tape_path = SHADOW_TAPE if tape_path is None else tape_path
    tape = _json(tape_path)
    base: dict[str, Any] = {
        "basis": SHADOW_BASIS,
        "why_basis": ("SIMULATED fills: shadow decisions replayed against the venue tape "
                      "(execution_quality.json), NOT live fills. A ratio here says what execution "
                      "WOULD take on the decisions the desk shadows; it is never a live capture "
                      "ratio and never enters alpha_capture_history.jsonl"),
    }
    if not tape:
        return {**base, "status": ac.UNMEASURED,
                "why": (f"{tape_path.name} absent: the shadow execution leg has reconstructed no "
                        "fill on this host, so not even a simulated capture ratio exists")}
    cells = tape.get("by_symbol_session") or {}
    if not isinstance(cells, dict) or not cells:
        return {**base, "status": ac.UNMEASURED, "measured_at": tape.get("measured_at"),
                "why": (f"{tape_path.name} reconstructed {tape.get('filled', 0)} filled "
                        f"decision(s) ({tape.get('unfilled', 0)} unfilled): no cell to measure")}
    expect = bracket_expectancy(ledger_dir)
    per: dict[str, dict[str, Any]] = {}
    num = den = 0.0
    n_measured = 0
    for key, cell in sorted(cells.items()):
        if not isinstance(cell, dict):
            continue
        slip = cell.get("slippage_R") or {}
        n_slip = int(slip.get("n") or 0)
        slip_mean = _f(slip.get("mean"))
        spread_px = _f((cell.get("spread_at_fill") or {}).get("mean"))
        ex = expect.get(key)
        row: dict[str, Any] = {"fills": int(cell.get("fills") or 0), "n_slippage_r": n_slip,
                               "slippage_r": slip_mean, "spread_at_fill_px": spread_px}
        if ex is None:
            row.update({"status": ac.UNMEASURED,
                        "why": ("no shadow ledger rows for this cell: the bracket expectancy "
                                "(the frictionless denominator) is unavailable")})
        elif slip_mean is None or n_slip < ac.MIN_N:
            row.update({"status": ac.UNMEASURED, "predicted_bracket_r": round(ex["mean_r"], 6),
                        "why": (f"{n_slip} fill(s) carry slippage in R; a capture ratio needs "
                                f"{ac.MIN_N}")})
        elif ex["mean_r"] < ac.MIN_DENOM_R:
            row.update({"status": ac.UNMEASURED, "predicted_bracket_r": round(ex["mean_r"], 6),
                        "why": (f"bracket expectancy {ex['mean_r']:+.4f}R is below the "
                                f"{ac.MIN_DENOM_R}R floor: a ratio against it is division by "
                                "noise")})
        else:
            if spread_px is not None and ex.get("mean_risk"):
                spread_r = 0.5 * spread_px / float(ex["mean_risk"])
                spread_basis = "half the mean quoted spread at fill over the mean risk distance"
            else:
                spread_r = 0.0
                spread_basis = ("UNMEASURED: no spread or no risk distance; exit crossing "
                                "charged at 0")
            realised = ex["mean_r"] - slip_mean - spread_r
            row.update({"status": ac.MEASURED,
                        "predicted_bracket_r": round(ex["mean_r"], 6),
                        "realised_shadow_r": round(realised, 6),
                        "alpha_capture_ratio": round(realised / ex["mean_r"], 6),
                        "leakage": {"slippage": round(slip_mean, 6),
                                    "spread_exit_half": round(spread_r, 6),
                                    "spread_basis": spread_basis},
                        "n_decisions": ex["n"], "ledger": ex["ledger"]})
            num += n_slip * realised
            den += n_slip * ex["mean_r"]
            n_measured += n_slip
        per[key] = row
    measured = n_measured > 0 and den > 0
    return {
        **base,
        "status": ac.MEASURED if measured else ac.UNMEASURED,
        "measured_at": tape.get("measured_at"),
        "alpha_capture_ratio": (round(num / den, 6) if measured else None),
        "n_fills": n_measured,
        "n_cells": len(per), "n_cells_measured": sum(1 for r in per.values()
                                                     if r["status"] == ac.MEASURED),
        "by_symbol_session": per,
        "why": ("fill-weighted over the measured cells: sum(n x realised) / sum(n x bracket R)"
                if measured else
                "no cell reached MIN_N fills with slippage in R and a ledger-backed denominator"),
    }


def alpha_capture_report(write: bool = True) -> dict[str, Any]:
    """The capture ratio, its decomposition, its trend, and what the blocked models still need.

    Appends a history point ONLY when the overall cell is MEASURED. A point with a null ratio is
    not a measurement of a bad month, it is the absence of one, and a trend line fitted through
    absences would describe the desk's trading frequency rather than its execution.
    """
    rows = fc.read_rows(CORPUS)
    records = [fc.record_from_row(r) for r in rows]
    #: Append-only corpus: the LAST row per key is the resolved truth.
    latest: dict[str, fc.FillRecord] = {}
    for r in records:
        latest[r.key] = r
    recs = list(latest.values())
    hist = _history()
    rep: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "corpus": {"path": str(CORPUS), "rows": len(rows), "unique_executions": len(recs),
                   "exists": CORPUS.exists()},
        "completeness": fc.completeness(recs),
        "capture": ac.report(recs, history=hist),
        "requirements": {
            "execution_choice": ecm.requirements(),
            "meta_label": ml.requirements(n_features=len(META_LABEL_FEATURES)),
            "why": ("what each blocked model needs before it may be fitted. Reported every day "
                    "so 'not yet' always comes with a number the desk can plan against."),
        },
    }
    if not recs:
        rep["status"] = "UNMEASURED"
        rep["why"] = (f"no fill corpus at {CORPUS}: the hourly execution twin assembles it from "
                      "the gateway's ledgers, and this box has recorded no execution to join. "
                      "This is NOT a capture ratio of zero -- it is the absence of a fill.")
        # THE DENOMINATOR IT CAN ALREADY REACH. Live capture stays UNMEASURED above; the
        # simulated ratio sits beside it under its own basis and never writes a history point.
        rep["shadow_tape"] = shadow_tape_capture()
    else:
        overall = rep["capture"]["overall"]
        rep["status"] = overall["status"]
        rep["alpha_capture_ratio"] = overall.get("alpha_capture_ratio")
        rep["why"] = overall.get("why", "")
        if write and overall["status"] == ac.MEASURED:
            fc.append_rows(HISTORY, [{
                "at": rep["generated_utc"], "n": overall["n"],
                "ratio": overall["alpha_capture_ratio"],
                "realized_edge_r": overall["realized_edge_r"],
                "predicted_frictionless_edge_r": overall["predicted_frictionless_edge_r"],
                "leakage_r": overall["leakage_r"], "leakage": overall["leakage"],
            }])
            rep["capture"]["trend"] = ac.trend(_history())
    if write:
        CAPTURE_REPORT.parent.mkdir(parents=True, exist_ok=True)
        CAPTURE_REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    return rep


def run() -> dict:
    fs = fill_surface.run(write=True)
    nt = netting.savings_report(write=True)
    book = _book_report()
    try:
        board = execution_registry.scoreboard()
    except Exception as exc:
        board = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    try:
        cap = alpha_capture_report(write=True)
    except Exception as exc:
        cap = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}",
               "corpus": {"rows": 0}}
    shadow = cap.get("shadow_tape") or {}
    return {"fill_surface": fs.get("note"), "fills": fs.get("n_fills"),
            "netting": nt.get("verdict"), "opposing_share": nt.get("opposing_share"),
            "netting_book": book.get("verdict"), "netting_book_why": book.get("why"),
            "algo_scoreboard": board,
            "alpha_capture": cap.get("status"),
            "alpha_capture_ratio": cap.get("alpha_capture_ratio"),
            "alpha_capture_why": cap.get("why"),
            "corpus_rows": int(cap.get("corpus", {}).get("unique_executions") or 0),
            "alpha_capture_shadow_tape": shadow.get("status"),
            "alpha_capture_ratio_shadow_tape": shadow.get("alpha_capture_ratio"),
            "alpha_capture_shadow_tape_basis": shadow.get("basis"),
            "alpha_capture_shadow_tape_why": shadow.get("why")}


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"EXECUTION INTELLIGENCE  surface: {d['fill_surface']} ({d['fills']} fills); "
          f"netting: {d['netting']} opposing_share={d['opposing_share']}; "
          f"book: {d['netting_book']}; algos: {d['algo_scoreboard']}")
    print(f"  ALPHA CAPTURE {d['alpha_capture']} ratio={d['alpha_capture_ratio']} "
          f"corpus={d['corpus_rows']} executions -- {d['alpha_capture_why']}")
    if d.get("alpha_capture_shadow_tape"):
        print(f"  ALPHA CAPTURE [basis={d['alpha_capture_shadow_tape_basis']}] "
              f"{d['alpha_capture_shadow_tape']} ratio={d['alpha_capture_ratio_shadow_tape']} "
              f"-- simulated fills, never live capture -- {d['alpha_capture_shadow_tape_why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
