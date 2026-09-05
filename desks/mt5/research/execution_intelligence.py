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
    return {"fill_surface": fs.get("note"), "fills": fs.get("n_fills"),
            "netting": nt.get("verdict"), "opposing_share": nt.get("opposing_share"),
            "netting_book": book.get("verdict"), "netting_book_why": book.get("why"),
            "algo_scoreboard": board,
            "alpha_capture": cap.get("status"),
            "alpha_capture_ratio": cap.get("alpha_capture_ratio"),
            "alpha_capture_why": cap.get("why"),
            "corpus_rows": int(cap.get("corpus", {}).get("unique_executions") or 0)}


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"EXECUTION INTELLIGENCE  surface: {d['fill_surface']} ({d['fills']} fills); "
          f"netting: {d['netting']} opposing_share={d['opposing_share']}; "
          f"book: {d['netting_book']}; algos: {d['algo_scoreboard']}")
    print(f"  ALPHA CAPTURE {d['alpha_capture']} ratio={d['alpha_capture_ratio']} "
          f"corpus={d['corpus_rows']} executions -- {d['alpha_capture_why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
