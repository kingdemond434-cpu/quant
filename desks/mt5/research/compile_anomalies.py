"""Turn explained anomalies into executable candidates the gauntlet can actually judge.

THE LAST GAP IN THE CHAIN. The miner proposes structure, the adapters attach a cause and a
falsifier, the store records the path -- and then nothing happened, because an anomaly is not a
candidate. `miner_candidate_compiler` refuses to cross that line for PROSE, correctly: "exact
recipe or structured causal data only, no prose-to-family guessing", which is why six prose
sources converted 0 of 341 rows. But a mined anomaly is not prose. It already carries the exact
recipe -- a feature name the executor resolves, a quantile band, a horizon and a direction -- and
refusing it would be applying a rule written for articles to something that is not an article.

WHY THIS IS NOT THE GUESSING THE COMPILER FORBIDS. Nothing here invents a family, a parameter or a
mechanism. `family_discovered(feature, band, horizon, side)` is the desk's existing executor for
"any edge the searcher discovered, from its parameters alone", and every field is copied from the
measurement:

    feature  <- the canonical primitive the condition was ranked on (build_primitives supplies it)
    band     <- the quantile band the effect was measured in
    horizon  <- the forward horizon it was measured over
    side     <- the SIGN of the measured effect, never a preference

The mechanism comes from an adapter that matched, with its falsifier attached, so gate 0 has a
named cause to judge rather than a correlation with a story.

TRIALS ARE CARRIED, WHICH IS WHAT MAKES THIS HONEST. Each candidate carries `selection_trials` --
the width of the search over its OWN symbol -- so deflated Sharpe charges it for the multiplicity
it was actually selected from. A compiler that dropped that number would be laundering a wide
search into a narrow-looking candidate, and this desk's whole deflation policy would become a
formality.

IT PROMOTES NOTHING. Output is a docket appended to the same hypotheses file every other producer
writes to. The ten gates remain the only arbiter, unchanged and no harsher.
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
sys.path.insert(0, str(ROOT))

from libs.research.mechanism_adapters import explain  # noqa: E402

ANOMALIES = DESK / "data" / "intelligence" / "anomalies"
OUT = DESK / "data" / "hypotheses" / "anomaly_candidates.json"

#: Per-symbol cap on emitted candidates. NOT a quality bar -- the gates are the only arbiter --
#: but a docket where one symbol contributes a thousand near-identical bands crowds out every
#: other symbol's best, and the gauntlet's hourly budget is finite. The strongest are kept.
PER_SYMBOL = 25


def _side(mean_bp: float) -> int:
    """Direction is the SIGN OF THE MEASURED EFFECT. Never a preference, never a default."""
    return 1 if float(mean_bp) >= 0 else -1


def compile_latest() -> dict[str, Any]:
    files = sorted(glob.glob(str(ANOMALIES / "anomalies_*.json")))
    if not files:
        return {"error": "no anomaly file -- nothing to compile", "candidates": []}
    doc = json.loads(Path(files[-1]).read_text("utf-8"))
    rows = doc.get("anomalies") or []

    by_symbol: dict[str, list[dict[str, Any]]] = {}
    skipped_unexplained = skipped_shape = 0

    for a in rows:
        cond = str(a.get("condition") or "")
        if "_q" not in cond:
            skipped_shape += 1           # cross-sectional rows have no single-feature recipe yet
            continue
        feature, _, band_s = cond.rpartition("_q")
        try:
            lo_s, hi_s = band_s.split("-")
            band = [float(lo_s), float(hi_s)]
        except ValueError:
            skipped_shape += 1
            continue

        e = explain(a)
        causes = e.get("candidate_explanations") or []
        if not causes:
            skipped_unexplained += 1     # a correlation with no named cause may not be traded
            continue
        cause = causes[0]

        sym = str(a.get("symbol") or "")
        by_symbol.setdefault(sym, []).append({
            "symbol": sym,
            "family": "discovered",
            "params": {"feature": feature, "band": band,
                       "horizon": int(a.get("horizon") or 1),
                       "side": _side(a.get("mean_bp") or 0.0)},
            "n": int(a.get("n") or 0),
            "t_stat": float(a.get("t_stat") or 0.0),
            "exp_r": float(a.get("mean_bp") or 0.0) / 1e4,
            "source": f"anomaly_miner:{feature}",
            "mechanism_status": "NAMED",
            "mechanism": cause.get("mechanism"),
            "mechanism_note": cause.get("causal_story"),
            "falsifier": cause.get("falsifier"),
            "payer": cause.get("payer"),
            "measurement_class": cause.get("measurement_class"),
            # THE WIDTH IT WAS SELECTED FROM, carried so deflation charges the real multiplicity.
            "selection_trials": int(a.get("selection_trials") or doc.get("trials") or 0),
        })

    candidates: list[dict[str, Any]] = []
    for rows_ in by_symbol.values():
        rows_.sort(key=lambda r: -abs(r["t_stat"]))
        candidates.extend(rows_[:PER_SYMBOL])

    report = {
        "compiled_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_file": files[-1],
        "anomalies_in": len(rows),
        "candidates_out": len(candidates),
        "symbols": len(by_symbol),
        "skipped_unexplained": skipped_unexplained,
        "skipped_no_single_feature_recipe": skipped_shape,
        "per_symbol_cap": PER_SYMBOL,
        "candidates": candidates,
        "rule": ("Nothing is invented. feature/band/horizon are copied from the measurement and "
                 "side is the SIGN of the measured effect; the mechanism comes from an adapter "
                 "that matched, with its falsifier attached. selection_trials is carried so "
                 "deflation charges the multiplicity the candidate was really selected from."),
        "promotes_nothing": ("a docket, not a verdict. The ten gates remain the only arbiter."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = compile_latest()
    if r.get("error"):
        print("compile:", r["error"])
        raise SystemExit(1)
    print(f"compiled {r['candidates_out']} candidates from {r['anomalies_in']} anomalies "
          f"across {r['symbols']} symbol(s) -> {OUT}")
    print(f"  skipped: {r['skipped_unexplained']} unexplained, "
          f"{r['skipped_no_single_feature_recipe']} without a single-feature recipe")
    for c in r["candidates"][:6]:
        p = c["params"]
        print(f"   {c['symbol']:9s} {p['feature']:22s} band={p['band']} h={p['horizon']:2d} "
              f"side={p['side']:+d}  t={c['t_stat']:+6.1f}  {c['mechanism']}")
