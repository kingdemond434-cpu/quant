#!/usr/bin/env python3
"""THE PLACEBO AUDIT -- planted defects through the desk's real gates, and the recall they earn.

Item 16 of the principal's 2026-09-29 list: *"continuous placebo/adversarial testing: scramble
timestamps, reverse signs, perturb spreads, delay info, randomise labels, synthetic nulls, move
feature availability, inject leakage; positive controls pass, negatives fail; measure
audit-recall rate."*

WHAT ALREADY EXISTED, AND WHY IT WAS NOT THIS. `research/adversary.py` feeds five poison canaries
(noise, harness lookahead, survivor bias, sub-spread edge, overfit) through
`external_gauntlet.run_gauntlet` every hour and defends a 100% rejection constant. Every one of
those canaries is a NEGATIVE. A gate that rejects everything -- welded shut -- scores a perfect
canary record, so the canary constant cannot tell "the gates discriminate" from "the gates refuse".
`libs/validation/redteam.py` runs placebos against ONE real certificate, and
`libs/validation/positive_control.py` certifies a gauntlet offline against Sharpe-exact series;
none of them runs a KNOWN-GOOD strategy and its planted-defect twins through the same live judge
in the same docket, which is the only arrangement in which "the negative failed" means the DEFECT
was caught rather than that the judge refuses everything.

THE DESIGN. One strategy with a genuine, cost-surviving edge is built on synthetic daily bars
(`adversary.docket_cell`'s layout, so the harness is the one the canaries already use). Then the
SAME strategy is re-built with exactly one defect planted, eight different ways. The positive
control must PASS; every planted defect must FAIL. Because each negative differs from the positive
in exactly one respect, a negative that fails was failed for that respect.

    gauntlet (external_gauntlet.run_gauntlet, all ten gates, one docket)
      planted_edge              POSITIVE: a real one-bar edge, ~57x the round-trip cost
      scrambled_timestamps      the same signals placed on permuted bars
      sign_flip                 every side reversed: the mirror of a real edge is a real loss
      spread_perturbation       the same trades charged a spread larger than the edge
      info_delay                each signal acts on the PREVIOUS draw's information
      label_shuffle             the sides randomly re-assigned, count preserved
      synthetic_null            a noise signal on a noise market, fresh seed
      harness_lookahead         the feature stamped on the bar whose return it IS: a correct
                                engine fills at the next open, so the edge must vanish
    lookahead sentinel (libs.validation.falsifiers.truncation, the falsifier battery's gate)
      causal_feature            POSITIVE: a family that reads only closed bars
      moved_feature_availability  the same family reading a feature one bar before it exists
      injected_leakage          the same family normalised by a CENTRED window (the future)

AUDIT RECALL = negatives caught / negatives judged. POSITIVE PASS RATE = positives passed /
positives judged. Both must be 1.0. A negative that is NOT caught is a gate that has gone blind to
a defect class; a positive that fails is a gate that has welded shut -- and the latter is the one
the canary constant could never see.

UNMEASURED IS NOT CAUGHT. A planted defect the judge could not evaluate (import failure, too few
observations, a crash) counts against recall exactly as a pass does -- a gate nobody can run is no
protection -- and is named separately so a broken import never reads as a blind gate.

NOTHING HERE MOVES A THRESHOLD. It reads the gates' verdicts and writes one report. A recall below
1.0 is a defect report for whoever owns the gate; it retires, resizes and promotes nothing.

    python desks/mt5/research/placebo_audit.py            # measure and write the report
    python desks/mt5/research/placebo_audit.py --dry-run  # measure, print, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = BASE / "reports" / "PLACEBO_AUDIT.json"
HISTORY = BASE / "reports" / "placebo_audit_history.jsonl"

#: Fixed so a verdict that changes is a change in the GATES, never in the draw (adversary's rule).
SEED = 20260929
N_DRAWS = 400
#: The planted edge: signal = EDGE_LOADING * outcome + unit noise, so the signal/outcome
#: correlation is 1/sqrt(2) ~ 0.71 per trade and the gross gain ~57x the canary round trip.
#: MEASURED 2026-09-29 on this harness: loadings 30 and 60 (correlation 0.29 / 0.51) were refused
#: by `deflated_sharpe` ALONE -- dsr 0.056 against sr0 0.312 at the docket's 109 charged trials --
#: while passing the other nine. That is the gauntlet's measured power floor on a 400-trade daily
#: cell, not a defect: a positive control must sit above the bar to test whether the bar still
#: admits anything. 100 is the weakest round loading that clears it on every gate.
EDGE_LOADING = 100.0
#: The spread-perturbation defect prices the same trades at this many times the canary spread
#: (150 bp a round trip against the planted edge's ~57 bp gross gain per trade).
SPREAD_SHOCK = 150.0

POSITIVE, NEGATIVE = "positive", "negative"
GAUNTLET, SENTINEL = "external_gauntlet.run_gauntlet", "falsifiers.truncation"


@dataclass(frozen=True)
class Plant:
    """One control. `kind` says whether the judge must admit it (positive) or refuse it."""

    name: str
    kind: str
    judge: str
    defect: str


PLANTS: tuple[Plant, ...] = (
    Plant("planted_edge", POSITIVE, GAUNTLET,
          "none: a genuine one-bar edge, ~57x the round-trip cost"),
    Plant("scrambled_timestamps", NEGATIVE, GAUNTLET,
          "the planted edge's signals placed on permuted bars"),
    Plant("sign_flip", NEGATIVE, GAUNTLET, "every side of the planted edge reversed"),
    Plant("spread_perturbation", NEGATIVE, GAUNTLET,
          f"the planted edge charged {SPREAD_SHOCK:g}x the spread, above its gross gain"),
    Plant("info_delay", NEGATIVE, GAUNTLET,
          "each signal acts on the previous draw's information (one period stale)"),
    Plant("label_shuffle", NEGATIVE, GAUNTLET,
          "the planted edge's sides randomly re-assigned, count preserved"),
    Plant("synthetic_null", NEGATIVE, GAUNTLET, "a noise signal on a noise market"),
    Plant("harness_lookahead", NEGATIVE, GAUNTLET,
          "the feature stamped on the bar whose return it is; only a leaky engine trades it"),
    Plant("causal_feature", POSITIVE, SENTINEL,
          "none: a family that reads only closed bars"),
    Plant("moved_feature_availability", NEGATIVE, SENTINEL,
          "the causal family reading its feature one bar before the feature exists"),
    Plant("injected_leakage", NEGATIVE, SENTINEL,
          "the causal family normalised by a centred window that reaches into the future"),
)


def _rng(name: str) -> random.Random:
    off = int(hashlib.sha1(name.encode()).hexdigest()[:8], 16) % 10_000
    return random.Random(SEED + off)  # noqa: S311 -- control data, never a secret


# ------------------------------------------------------------------------ gauntlet controls
def _edge_draws() -> tuple[list[float], list[float]]:
    """(signal, outcome) for the planted edge. Deterministic."""
    rng = _rng("planted_edge")
    fwd = [rng.gauss(0.0, 0.01) for _ in range(N_DRAWS)]
    sig = [EDGE_LOADING * f + rng.gauss(0.0, 1.0) for f in fwd]
    return sig, fwd


def gauntlet_series(name: str) -> tuple[list[float], list[float], int, float]:
    """(signal, outcome, stamp_offset, spread multiplier) for one gauntlet control."""
    sig, fwd = _edge_draws()
    rng = _rng(name)
    if name == "planted_edge":
        return sig, fwd, 0, 1.0
    if name == "scrambled_timestamps":
        perm = list(range(len(sig)))
        rng.shuffle(perm)
        return [sig[p] for p in perm], fwd, 0, 1.0
    if name == "sign_flip":
        return [-s for s in sig], fwd, 0, 1.0
    if name == "spread_perturbation":
        return sig, fwd, 0, SPREAD_SHOCK
    if name == "info_delay":
        return [0.0, *sig[:-1]], fwd, 0, 1.0
    if name == "label_shuffle":
        return [abs(s) * (1.0 if rng.random() < 0.5 else -1.0) for s in sig], fwd, 0, 1.0
    if name == "synthetic_null":
        return ([rng.gauss(0.0, 1.0) for _ in range(N_DRAWS)],
                [rng.gauss(0.0, 0.01) for _ in range(N_DRAWS)], 0, 1.0)
    if name == "harness_lookahead":
        # The feature IS the bar's own return and is stamped on that bar: honest about when it
        # exists. A correct engine fills at the next open, so this trades the filler bar.
        return list(fwd), fwd, 1, 1.0
    raise KeyError(name)


def _gauntlet_cells(adversary: Any) -> list[dict[str, Any]]:
    from mt5desk.engine import Costs
    cells = []
    for p in PLANTS:
        if p.judge != GAUNTLET:
            continue
        sig, fwd, offset, spread_mult = gauntlet_series(p.name)
        meta = dict(adversary.CANARY_META[adversary.CANARY_SYMBOL])
        costs = Costs.from_symbol(meta, mult=spread_mult)
        cell = adversary.docket_cell(p.name, sig, fwd, stamp_offset=offset, costs=costs)
        cell["family"] = f"placebo_{p.name}"
        cells.append(cell)
    return cells


def judge_gauntlet(gauntlet: Any, adversary: Any) -> dict[str, dict[str, Any]]:
    """Every gauntlet control in ONE docket (PBO and SPA are program-level), verdict per plant."""
    out = gauntlet.run_gauntlet(_gauntlet_cells(adversary), "placebo-audit",
                                adversary.CANARY_META)
    verdicts = {str(v.get("family", "")).removeprefix("placebo_"): v
                for v in out.get("verdicts") or []}
    rows: dict[str, dict[str, Any]] = {}
    for p in PLANTS:
        if p.judge != GAUNTLET:
            continue
        v = verdicts.get(p.name)
        if v is None:
            rows[p.name] = {"judged": False, "passed": None,
                            "why": f"no verdict returned (docket error: {out.get('error')})"}
            continue
        stages = v.get("stages") or {}
        if v.get("unmeasured"):
            rows[p.name] = {"judged": False, "passed": None,
                            "why": (stages.get("observations") or {}).get("why",
                                                                          "UNMEASURED")}
            continue
        rows[p.name] = {"judged": True, "passed": bool(v.get("passed")),
                        "failed_gates": [g for g, s in stages.items()
                                         if isinstance(s, dict) and not s.get("passed")],
                        "days": v.get("days")}
    rows["_docket"] = {"n_cells": out.get("n_cells"), "n_trials": out.get("n_trials"),
                       "trial_count_basis": out.get("trial_count_basis"),
                       "error": out.get("error")}
    return rows


# ------------------------------------------------------------------------ sentinel controls
def _sentinel_bars() -> Any:
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(SEED)
    n = 600
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.005, n)))
    openp = np.concatenate([[close[0]], close[:-1]])
    idx = pd.date_range("2021-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": openp, "close": close,
                         "high": np.maximum(openp, close) * 1.001,
                         "low": np.minimum(openp, close) * 0.999}, index=idx)


def _family(feature: Callable[[Any], Any]) -> Callable[..., list[Any]]:
    """A family whose every signal carries its feature value in its stop, so any change in the
    feature at a bar changes the signal there -- the sentinel compares stops exactly."""
    from mt5desk.engine import Signal

    def fam(df: Any, **_kw: Any) -> list[Any]:
        f = feature(df)
        out = []
        for i in range(len(df)):
            v = float(f.iloc[i])
            if v != v:
                continue
            px = float(df["close"].iloc[i])
            side = 1 if v > 0 else -1
            out.append(Signal(time=df.index[i], side=side, stop=px - side * (1.0 + abs(v)),
                              target=px + side * (1.0 + abs(v)), ttl_bars=4, tag="placebo"))
        return out
    return fam


def sentinel_families() -> dict[str, Callable[..., list[Any]]]:
    def causal(df: Any) -> Any:
        c = df["close"].astype(float)
        return (c - c.rolling(20).mean()) / c.rolling(20).std()

    def moved(df: Any) -> Any:
        return causal(df).shift(-1)

    def leaked(df: Any) -> Any:
        c = df["close"].astype(float)
        return (c - c.rolling(21, center=True).mean()) / c.rolling(21, center=True).std()

    return {"causal_feature": _family(causal), "moved_feature_availability": _family(moved),
            "injected_leakage": _family(leaked)}


def judge_sentinel() -> dict[str, dict[str, Any]]:
    from libs.validation import falsifiers
    bars = _sentinel_bars()
    rows: dict[str, dict[str, Any]] = {}
    for name, fam in sentinel_families().items():
        try:
            res = falsifiers.truncation(bars, [], 0.0, family=fam, params={})
        except Exception as exc:
            rows[name] = {"judged": False, "passed": None,
                          "why": f"{type(exc).__name__}: {exc}"}
            continue
        verdict = str(res.get("verdict"))
        if verdict not in ("PASS", "FAIL"):
            rows[name] = {"judged": False, "passed": None, "why": verdict}
            continue
        rows[name] = {"judged": True, "passed": verdict == "PASS",
                      "lookahead_verdict": res.get("lookahead_verdict"),
                      "only_with_future": res.get("only_with_future")}
    return rows


# ------------------------------------------------------------------------ the score
def score(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Recall over negatives, pass rate over positives, and the status those two imply."""
    table = []
    for p in PLANTS:
        r = rows.get(p.name) or {"judged": False, "passed": None, "why": "not reached"}
        correct = (r.get("judged") is True
                   and (r.get("passed") is True if p.kind == POSITIVE
                        else r.get("passed") is False))
        table.append({"plant": p.name, "kind": p.kind, "judge": p.judge, "defect": p.defect,
                      "correct": bool(correct), **r})
    neg = [t for t in table if t["kind"] == NEGATIVE]
    pos = [t for t in table if t["kind"] == POSITIVE]
    caught = [t for t in neg if t["correct"]]
    admitted = [t for t in pos if t["correct"]]
    blind = [t["plant"] for t in neg if t["judged"] and t["passed"] is True]
    welded = [t["plant"] for t in pos if t["judged"] and t["passed"] is False]
    unjudged = [t["plant"] for t in table if not t["judged"]]
    recall = len(caught) / len(neg) if neg else None
    pos_rate = len(admitted) / len(pos) if pos else None
    by_judge: dict[str, dict[str, Any]] = {}
    for j in (GAUNTLET, SENTINEL):
        jn = [t for t in neg if t["judge"] == j]
        by_judge[j] = {"negatives": len(jn), "caught": sum(1 for t in jn if t["correct"]),
                       "recall": (sum(1 for t in jn if t["correct"]) / len(jn)) if jn else None}
    if blind:
        status = "GATE_BLIND"
    elif welded:
        status = "GATE_WELDED"
    elif unjudged:
        status = "UNMEASURED"
    else:
        status = "OK"
    return {"status": status, "audit_recall": recall, "positive_pass_rate": pos_rate,
            "negatives": len(neg), "caught": len(caught), "positives": len(pos),
            "admitted": len(admitted), "blind_to": blind, "welded_on": welded,
            "unjudged": unjudged, "by_judge": by_judge, "table": table}


def run() -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    gate_source = GAUNTLET
    try:
        import adversary
        import external_gauntlet
    except Exception as exc:
        gate_source = f"BLOCKED: external_gauntlet not importable ({type(exc).__name__}: {exc})"
        for p in PLANTS:
            if p.judge == GAUNTLET:
                rows[p.name] = {"judged": False, "passed": None, "why": gate_source}
    else:
        try:
            rows.update(judge_gauntlet(external_gauntlet, adversary))
        except Exception as exc:
            for p in PLANTS:
                if p.judge == GAUNTLET:
                    rows[p.name] = {"judged": False, "passed": None,
                                    "why": f"the docket raised {type(exc).__name__}: {exc}"}
    rows.update(judge_sentinel())
    docket = rows.pop("_docket", None)
    doc = {"measured_at": datetime.now(UTC).isoformat(timespec="seconds"), "seed": SEED,
           "n_draws": N_DRAWS, "gate_source": gate_source, "docket": docket, **score(rows),
           "rule": ("positives must PASS and every planted defect must FAIL, in one docket "
                    "through the real judge; an unjudged plant counts against recall and is "
                    "named apart from a blind gate. Measurement only: no threshold moves.")}
    return doc


def _history_row(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc.get(k) for k in ("measured_at", "status", "audit_recall",
                                    "positive_pass_rate", "blind_to", "welded_on", "unjudged")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--history", type=Path, default=HISTORY)
    a = ap.parse_args(argv)
    doc = run()
    print(f"placebo audit: {doc['status']} recall={doc['audit_recall']} "
          f"positive_pass_rate={doc['positive_pass_rate']} blind_to={doc['blind_to']} "
          f"welded_on={doc['welded_on']} unjudged={doc['unjudged']}")
    if not a.dry_run:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        with a.history.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_history_row(doc), default=str) + "\n")
    return 1 if doc["status"] in ("GATE_BLIND", "GATE_WELDED") else 0


if __name__ == "__main__":
    sys.exit(main())
