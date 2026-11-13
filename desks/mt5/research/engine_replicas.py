#!/usr/bin/env python3
"""ENGINE REPLICAS -- every promoted certificate replayed through LEAN's gap-aware fills and
Nautilus's adaptive bar path, beside the contract replica (hourly leg `engine_replicas`).

`independent_verifier` asks whether the desk's implementation and a second one agree on the
CONTRACT. This leg asks the next question: how much of a certificate's R is owed to the
contract's two most optimistic bar-level assumptions -- a stop the market gapped through
filled at the stop, and a bar that touched both stop and target resolved without regard to the
path the price took. It is the work the `lean` and `nautilus` adapters do (audit 2026-11-13);
the engines are `libs/validation/engine_replicas.py`, built on the replica's own bars, signals
and cost arithmetic.

WHICH CERTIFICATES: the independent verifier's order -- promoted (LIVE/STANDBY) first, then the
canon -- until the budget runs out. Per certificate: the contract sum R, each engine's sum R,
the difference, how many exits moved and how many were gap exits. A certificate whose family
the replica does not implement is UNSUPPORTED; a missing input is UNMEASURED. Neither is ever a
zero.

NOTHING HERE WITHDRAWS A CERTIFICATE. The report feeds no gate, promoter or sizer; making it
one would be a threshold change and the principal's call. Published reasons carry exception
TYPE NAMES only.

    python desks/mt5/research/engine_replicas.py --once [--budget-s 600] [--cell KEY]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
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

from libs.validation import engine_replicas as ER  # noqa: E402
from libs.validation import independent_replica as rep  # noqa: E402

_LOG = logging.getLogger(__name__)

CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
SLEEVES = DESK / "data" / "sleeves.json"
UNIVERSE = DESK / "data" / "universe"
REPORT = DESK / "reports" / "ENGINE_REPLICAS.json"
MEASURED, UNSUPPORTED, UNMEASURED = "MEASURED", "UNSUPPORTED", "UNMEASURED"


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def certificate_order(canon: dict[str, Any], sleeves: Any) -> tuple[list[str], set[str]]:
    from research.independent_verifier import certificate_order as order
    return order(canon, sleeves)


def replay_one(key: str, rec: dict[str, Any], universe_meta: dict[str, Any],
               spec_of: Any = None) -> dict[str, Any]:
    try:
        if spec_of is None:
            import blind_reviewer as br
            spec_of = br.certified_spec
        spec = spec_of(rec)
    except Exception as exc:  # noqa: BLE001
        _LOG.info("certified_spec failed for %s: %s", key, exc)
        return {"cell": key, "status": UNMEASURED, "why": f"certified_spec {type(exc).__name__}"}
    base = {"cell": key, "symbol": spec.get("symbol"), "family": spec.get("family"),
            "timeframe": spec.get("timeframe")}
    if spec.get("family") not in rep.SUPPORTED_FAMILIES:
        return {**base, "status": UNSUPPORTED, "why": "family has no replica implementation"}
    if not isinstance(spec.get("params"), dict):
        return {**base, "status": UNMEASURED, "why": "shadow_spec.params never recorded"}
    meta = universe_meta.get(str(spec["symbol"]))
    if not isinstance(meta, dict):
        return {**base, "status": UNMEASURED, "why": "symbol not in universe.json"}
    df = rep.load_bars(UNIVERSE / f"{spec['symbol']}_{str(spec['timeframe']).upper()}.parquet")
    if df is None:
        return {**base, "status": UNMEASURED, "why": "bars unavailable"}
    sigs, why = rep.signals_for(str(spec["family"]), df, spec["params"])
    if sigs is None:
        return {**base, "status": UNSUPPORTED, "why": "spec outside the replica"}
    return {**base, "status": MEASURED, **ER.replay(df, sigs, meta)}


def run(budget_s: float = 600.0, only: str | None = None) -> dict[str, Any]:
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
            rows.append({"cell": key, "status": UNMEASURED, "why": "budget exhausted"})
            continue
        try:
            rows.append(replay_one(key, canon[key], universe_meta))
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("engine replay failed for %s: %s", key, exc)
            rows.append({"cell": key, "status": UNMEASURED,
                         "why": f"replay raised {type(exc).__name__}"})
    for r in rows:
        r["promoted"] = r["cell"] in promoted
    return summarise(rows)


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [r for r in rows if r.get("status") == MEASURED]
    eng: dict[str, Any] = {}
    for e in ER.ENGINES:
        deltas = [float(r[e]["delta_sum_r"]) for r in measured]
        eng[e] = {"certificates": len(deltas),
                  "flattered_by_contract": sum(1 for d in deltas if d < -1e-9),
                  "penalised_by_contract": sum(1 for d in deltas if d > 1e-9),
                  "total_delta_sum_r": round(sum(deltas), 6),
                  "worst": sorted(({"cell": r["cell"], "delta_sum_r": r[e]["delta_sum_r"],
                                    "promoted": r["promoted"]} for r in measured),
                                  key=lambda x: float(x["delta_sum_r"]))[:10]}
    tally: dict[str, int] = {}
    for r in rows:
        tally[str(r.get("status"))] = tally.get(str(r.get("status")), 0) + 1
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": UNMEASURED if not measured else MEASURED,
        "adapters": {"lean": "lean_gap", "nautilus": "nautilus_path"},
        "engines": eng, "tally": tally, "n_certificates": len(rows),
        "promoted_measured": sum(1 for r in measured if r["promoted"]),
        "rows": rows,
        "rule": ("delta_sum_r = engine sum R - contract sum R on the replica's own signals; "
                 "negative means the contract flatters the certificate. Measurement only."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--cell", default=None)
    a = ap.parse_args(argv)
    doc = run(a.budget_s, a.cell)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, REPORT)
    except PermissionError:
        REPORT.unlink(missing_ok=True)
        os.replace(tmp, REPORT)
    print(json.dumps({"status": doc["status"], "tally": doc["tally"],
                      **{e: doc["engines"][e]["total_delta_sum_r"] for e in ER.ENGINES}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
