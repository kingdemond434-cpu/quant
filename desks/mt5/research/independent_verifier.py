#!/usr/bin/env python3
"""THE INDEPENDENT VERIFIER -- every promoted certificate rebuilt by a second implementation.

Item 15 of the principal's 2026-09-29 list. The second implementation is
`libs/validation/independent_replica.py`, which imports nothing from `mt5desk`, `research` or
`scripts` and rebuilds signals, fills, costs and R from the certificate's frozen `shadow_spec`
and the universe registry's contract terms. This organ runs BOTH implementations on the same bars
and publishes, per certificate, whether they agree trade by trade.

    original   `mt5desk.executables.resolve_family` -> `family_inputs` -> `family_call.signals`
               -> `engine.run_backtest` with `Costs.from_symbol(universe row)` -- the exact path
               `research/blind_reviewer.py` reproduces a certificate through, which is the path
               the forward clock and the gateway share
    replica    `independent_replica.signals_for` -> `independent_replica.simulate`

THE COMPARISON is keyed on (entry time, side): trades only one side made, and for matched trades
the largest disagreement in gross R, in cost R and in net R. AGREE needs identical trade sets and
every matched net R within `TOL_R`. Anything else is DISAGREE, with the first differing entry
times named -- a defect report, because one of the two implementations is wrong about the
strategy the desk is trading. UNSUPPORTED (a family or filter the replica does not implement) and
UNMEASURED (no bars, no registry row, an import or build failure) are published as themselves and
never counted as agreement.

WHICH CERTIFICATES. Every certificate a LIVE or STANDBY sleeve in `data/sleeves.json` names first
(the promoted strategies the item is about), then the rest of the canon, until the budget runs
out. Coverage is reported against the promoted set.

NOTHING HERE WITHDRAWS A CERTIFICATE. A DISAGREE row is evidence for whoever owns the family or the
engine; the verdict feeds no gate, no promoter and no sizing. Making it a promotion veto is a
threshold change and is the principal's call.

    python desks/mt5/research/independent_verifier.py --apply [--budget-s 900] [--cell KEY]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.validation import independent_replica as rep  # noqa: E402

CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
SLEEVES = DESK / "data" / "sleeves.json"
UNIVERSE = DESK / "data" / "universe"
REPORT = DESK / "reports" / "INDEPENDENT_VERIFIER.json"
HISTORY = DESK / "reports" / "independent_verifier_history.jsonl"

AGREE, DISAGREE, UNSUPPORTED, UNMEASURED = "AGREE", "DISAGREE", "UNSUPPORTED", "UNMEASURED"
#: Net R per matched trade. Both sides compute in float64 from the same bars and the same
#: contract terms, so any honest difference is arithmetic noise far below this.
TOL_R = 1e-6


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def certificate_order(canon: dict[str, Any], sleeves: Any) -> tuple[list[str], set[str]]:
    """Promoted certificates first (named by a LIVE/STANDBY sleeve), then the rest of the canon."""
    promoted: list[str] = []
    rows = sleeves.get("sleeves") if isinstance(sleeves, dict) else None
    for r in rows or []:
        if not isinstance(r, dict) or str(r.get("status")) not in ("LIVE", "STANDBY"):
            continue
        cert = r.get("certificate")
        cell = cert.get("cell") if isinstance(cert, dict) else None
        if cell and cell in canon and cell not in promoted:
            promoted.append(str(cell))
    rest = sorted(k for k in canon if k not in promoted)
    return promoted + rest, set(promoted)


def _original(spec: dict[str, Any], meta: dict[str, Any]) -> tuple[list[dict[str, Any]] | None,
                                                                   str, Any]:
    """The desk's own implementation, through blind_reviewer's reproduction path."""
    try:
        import blind_reviewer as br
        from mt5desk.engine import Costs, run_backtest
        from mt5desk.family_call import signals as family_signals
    except Exception as exc:
        return None, f"original implementation not importable ({type(exc).__name__}: {exc})", None
    fn, population = br.resolve_family(spec["family"])
    if fn is None:
        return None, f"no constructor for {spec['family']!r}", None
    if population == "hunt16":
        return None, "hunt16 family: its parameterisation is not in the certificate", None
    bars = br.load_bars(spec["symbol"], spec["timeframe"], UNIVERSE)
    if bars is None or len(bars) < 60:
        return None, f"{spec['symbol']}_{spec['timeframe']} bars unavailable", None
    call, why = br.call_params(spec, bars)
    if call is None:
        return None, why, None
    sigs = family_signals(fn, bars, side=int(spec.get("side") or 1), params=dict(call))
    trades = run_backtest(bars, list(sigs), Costs.from_symbol(meta)).trades
    return _rows(trades), "ok", bars


def _prim_cache() -> dict[Any, Any] | None:
    """`families_orthogonal._PRIM_CACHE`, the process-wide primitive cache `family_discovered`
    reads -- or None where it does not exist."""
    try:
        from mt5desk import families_orthogonal as fo
    except Exception:
        return None
    cache = getattr(fo, "_PRIM_CACHE", None)
    return cache if isinstance(cache, dict) else None


def _rows(trades: Any) -> list[dict[str, Any]]:
    out = []
    for t in trades:
        unit = abs(float(t.entry) - float(t.stop))
        gross = int(t.side) * (float(t.exit) - float(t.entry)) / unit if unit > 0 else 0.0
        out.append({"entry_time": t.entry_time, "side": int(t.side), "gross_r": gross,
                    "cost_r": gross - float(t.r_multiple), "r": float(t.r_multiple)})
    return out


def verify_one(key: str, rec: dict[str, Any], universe_meta: dict[str, Any]) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        import blind_reviewer as br
        spec = br.certified_spec(rec)
    except Exception as exc:
        return {"cell": key, "verdict": UNMEASURED,
                "why": f"certified_spec unavailable ({type(exc).__name__}: {exc})"}
    base = {"cell": key, "symbol": spec.get("symbol"), "family": spec.get("family"),
            "params": spec.get("params"), "timeframe": spec.get("timeframe")}
    if spec.get("family") not in rep.SUPPORTED_FAMILIES:
        return {**base, "verdict": UNSUPPORTED,
                "why": f"family {spec.get('family')!r} has no independent implementation yet"}
    if not isinstance(spec.get("params"), dict):
        return {**base, "verdict": UNMEASURED, "why": "shadow_spec.params never recorded"}
    meta = universe_meta.get(str(spec["symbol"]))
    if not isinstance(meta, dict):
        return {**base, "verdict": UNMEASURED, "why": "symbol not in universe.json"}
    # THE SWAP UNIT IS A CONTRACT TERM, HANDED TO BOTH SIDES AS DATA. A registry row without its
    # own `swap_mode` gets the venue's recorded one, so the replica prices financing in the same
    # unit the original does (and refuses by name when neither knows it).
    if meta.get("swap_mode") is None:
        try:
            from mt5desk.engine import swap_mode_of
            _mode, _src = swap_mode_of({**meta, "symbol": meta.get("symbol") or spec["symbol"]})
        except Exception:
            _mode = None
        if _mode is not None:
            meta = {**meta, "swap_mode": _mode}
    df = rep.load_bars(UNIVERSE / f"{spec['symbol']}_{str(spec['timeframe']).upper()}.parquet")
    if df is None:
        return {**base, "verdict": UNMEASURED, "why": "bars unavailable to the replica"}
    sigs, why = rep.signals_for(str(spec["family"]), df, spec["params"])
    if sigs is None:
        return {**base, "verdict": UNSUPPORTED, "why": why}
    replica = [dataclasses.asdict(f) for f in rep.simulate(df, sigs, meta)]
    # THE ORIGINAL RUNS TWICE WHEN IT HOLDS PROCESS STATE. First exactly as a long-lived process
    # (the gauntlet's sweep, the gateway's pass) would run it -- whatever the process-wide
    # primitive cache already holds -- then again on an EMPTY cache. The replica is compared with
    # the second, so a verdict is about the two IMPLEMENTATIONS; the first is compared with the
    # second, so a result that depends on which cell ran before it in the same process is named
    # as the defect it is (`state_contamination`), not blamed on either implementation.
    cache = _prim_cache()
    shared = None
    try:
        if cache is not None and spec.get("family") == "discovered":
            shared, _w, _b = _original(spec, meta)
            cache.clear()
        original, owhy, _bars = _original(spec, meta)
    except Exception as exc:
        original, owhy = None, f"the original raised ({type(exc).__name__}: {exc})"
    if original is None:
        return {**base, "verdict": UNMEASURED, "why": owhy, "n_replica": len(replica)}
    cmp = rep.compare(original, replica, tol_r=TOL_R)
    verdict = AGREE if cmp["agree"] else DISAGREE
    if not original and not replica:
        verdict, cmp["why"] = UNMEASURED, "neither implementation produced a trade"
    out = {**base, "verdict": verdict, **cmp, "n_signals_replica": len(sigs),
           "seconds": round(time.monotonic() - t0, 2)}
    if shared is not None:
        sc = rep.compare(shared, original, tol_r=TOL_R)
        out["state_contamination"] = not sc["agree"] and bool(shared or original)
        out["shared_process"] = {"n_trades_shared": sc["n_original"],
                                 "n_trades_fresh": sc["n_replica"], "matched": sc["matched"],
                                 "n_r_disagree": sc["n_r_disagree"]}
    return out


def run(budget_s: float = 900.0, only: str | None = None) -> dict[str, Any]:
    canon_doc = _json(CANON)
    canon = dict((canon_doc or {}).get("survivors") or {}) if isinstance(canon_doc, dict) else {}
    order, promoted = certificate_order(canon, _json(SLEEVES))
    if only:
        order = [k for k in order if k == only]
    universe_meta = _json(UNIVERSE / "universe.json") or {}
    rows: list[dict[str, Any]] = []
    t0 = time.monotonic()
    for key in order:
        if time.monotonic() - t0 > budget_s:
            rows.append({"cell": key, "verdict": UNMEASURED, "why": "budget exhausted"})
            continue
        try:
            rows.append(verify_one(key, canon[key], universe_meta))
        except Exception as exc:
            rows.append({"cell": key, "verdict": UNMEASURED,
                         "why": f"verifier raised {type(exc).__name__}: {exc}"})
    for r in rows:
        r["promoted"] = r["cell"] in promoted

    def tally(sel: list[dict[str, Any]]) -> dict[str, int]:
        out = {AGREE: 0, DISAGREE: 0, UNSUPPORTED: 0, UNMEASURED: 0}
        for r in sel:
            out[r["verdict"]] = out.get(r["verdict"], 0) + 1
        return out

    prom = [r for r in rows if r["promoted"]]
    tp = tally(prom)
    doc = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": ("UNMEASURED" if not rows else
                   "DISAGREEMENT" if tally(rows)[DISAGREE] else "MEASURED"),
        "promoted": len(prom), "promoted_tally": tp,
        "promoted_agree_fraction": (tp[AGREE] / len(prom)) if prom else None,
        "all_tally": tally(rows), "n_certificates": len(rows),
        # A CERTIFICATE WHOSE ORIGINAL DEPENDS ON WHAT RAN BEFORE IT IN THE SAME PROCESS. Measured
        # 2026-09-29: `families_orthogonal._PRIM_CACHE` is keyed on (bar count, first stamp, last
        # stamp, extra keys) and not on the symbol, so two instruments with the same bar extent
        # share one primitive set -- AUDUSD's `dd_12` read back as AUDCAD's after an AUDCAD cell.
        "state_contamination": sorted(r["cell"] for r in rows if r.get("state_contamination")),
        "replica": "libs/validation/independent_replica.py (imports no mt5desk/research/scripts)",
        "supported_families": list(rep.SUPPORTED_FAMILIES), "tol_r": TOL_R,
        "rows": rows,
        "rule": ("AGREE only on identical trade sets with every matched net R within tol_r; "
                 "UNSUPPORTED and UNMEASURED are never agreement. Measurement only: a DISAGREE "
                 "withdraws nothing."),
    }
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true", help="write the report (else print only)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--cell", default=None)
    a = ap.parse_args(argv)
    doc = run(a.budget_s, a.cell)
    print(f"independent verifier: {doc['status']} promoted {doc['promoted']} "
          f"{doc['promoted_tally']} all {doc['all_tally']}")
    for r in doc["rows"]:
        if r["verdict"] == DISAGREE:
            print(f"  DISAGREE {r['cell']}: original {r.get('n_original')} replica "
                  f"{r.get('n_replica')} matched {r.get('matched')} max|dR| {r.get('max_abs_r')}")
    if a.apply:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        with HISTORY.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({k: doc[k] for k in ("measured_at", "status", "promoted",
                                                     "promoted_tally", "all_tally")},
                                default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
