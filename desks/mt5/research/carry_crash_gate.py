"""Carry-crash gate, hourly: the carry family's hazard, its Rule-1 proof, and today's multiplier.

Runs inside the `weak_signal_book` leg on the series that leg has just loaded (every judged carry
cell that cleared validity, plus any `combiner_inputs/` book whose id names carry), so it costs no
extra build and covers every carry member the combiner can see. Standalone: `--once` rebuilds
from the series store.

WRITES desks/mt5/reports/CARRY_CRASH.json. It proposes a multiplier and says whether it is armed;
nothing here sizes an order. The multiplier reaches sizing only once `proof.armed` is true and a
separate, audited change registers it in `libs/portfolio/capital_modifiers.REGISTRY` and the
missed-growth ledger -- until then `missed_growth_per_day` is what staying disarmed costs (or
saves), so the disarmed state is itself measured (Growth Governance Rule 1).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import carry_crash as cc  # noqa: E402

REPORT = _DESK / "reports" / "CARRY_CRASH.json"
COT_JPY = _DESK / "data" / "cot_tff" / "jpy.parquet"
#: Judge families whose return IS the carry trade. A cell id is `SYM[@TF].family.p=digest`.
CARRY_FAMILIES = frozenset({"carry", "cross_sectional_class_carry"})


def family_of(cid: str) -> str:
    if cid.startswith("EXT:"):
        return "carry" if "carry" in cid.lower() else ""
    parts = cid.split(".")
    return parts[1] if len(parts) >= 3 else ""


def carry_book(series: dict[str, tuple[pd.Series, pd.Series | None]],
               ) -> tuple[pd.Series | None, pd.Series | None, list[str]]:
    """Equal-weight mean over carry members, on the days each member has a reading."""
    ids = sorted(c for c in series if family_of(c) in CARRY_FAMILIES)
    if not ids:
        return None, None, []
    r1 = pd.concat({c: series[c][0] for c in ids}, axis=1).sort_index()
    r3s = {c: series[c][1] for c in ids if series[c][1] is not None}
    r3 = (pd.concat(r3s, axis=1).reindex(r1.index).mean(axis=1) if r3s else None)
    return r1.mean(axis=1), r3, ids


def load_cot() -> pd.DataFrame | None:
    try:
        d = pd.read_parquet(COT_JPY)
    except Exception:  # noqa: BLE001 - absent or unreadable is UNMEASURED, said in the report
        return None
    if "market" in d.columns:
        d = d[d["market"].astype(str).str.upper().str.startswith("JAPANESE YEN -")]
    return d


def load_vix() -> pd.Series | None:
    try:
        from libs.portfolio import macro_state
        rows = (macro_state.load_pit()[0] or {}).get("VIXCLS") or []
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in rows}).sort_index()
    return s


def _age_days(ts: pd.Timestamp | None, now: datetime) -> float | None:
    if ts is None or pd.isna(ts):
        return None
    return round((pd.Timestamp(now).tz_localize(None) - pd.Timestamp(ts).tz_localize(None))
                 .total_seconds() / 86400.0, 1)


def run_from(series: dict[str, tuple[pd.Series, pd.Series | None]]) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    r1, r3, ids = carry_book(series)
    cot, vix = load_cot(), load_vix()
    inputs = {
        "carry_members": len(ids), "carry_member_sample": ids[:10],
        "cot_jpy_last": (str(pd.to_datetime(cot["report_date"]).max().date())
                         if cot is not None and len(cot) else None),
        "cot_jpy_age_days": (_age_days(pd.to_datetime(cot["report_date"]).max(), now)
                             if cot is not None and len(cot) else None),
        "vix_last": str(vix.index.max().date()) if vix is not None and len(vix) else None,
        "vix_age_days": _age_days(vix.index.max(), now) if vix is not None and len(vix) else None,
    }
    doc: dict[str, Any] = {"generated_utc": now.isoformat(timespec="seconds"),
                           "family": sorted(CARRY_FAMILIES), "inputs": inputs,
                           "authority": "proposes only; the multiplier is applied by no sizing "
                                        "code until proof.armed and a registered modifier"}
    if r1 is None or r1.dropna().empty:
        doc.update({"status": "UNMEASURED", "why": "no carry member series in the combiner pool",
                    "current": {"category": "UNMEASURED", "multiplier": 1.0}})
        return _write(doc)
    haz = cc.hazard(r1, cot, vix)
    proof = cc.prove(r1, r3, haz["hazard"])
    cur = cc.current(haz, proof)
    doc.update({
        "status": "ARMED" if proof.armed else ("UNMEASURED" if proof.reason.startswith(
            "UNMEASURED") else "DISARMED"),
        "proof": proof.as_dict(),
        "current": cur,
        "missed_growth_per_day": (None if proof.delta_elog_per_day is None or proof.armed
                                  else proof.delta_elog_per_day),
        "carry_days": int(r1.dropna().size),
        "hazard_days": int(haz["hazard"].notna().sum()),
    })
    return _write(doc)


def _write(doc: dict[str, Any]) -> dict[str, Any]:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, REPORT)
    return doc


def main() -> int:
    import weak_signal_book as job  # the desk job: series store and index
    idx = job._read_json(job.STORE_INDEX, {}) or {}
    series = {}
    for cid, row in idx.items():
        if family_of(cid) in CARRY_FAMILIES and (row or {}).get("origin") != "empty":
            got = job.store_load(cid)
            if got is not None:
                series[cid] = got
    doc = run_from(series)
    print(json.dumps({k: doc.get(k) for k in ("status", "current", "carry_days")}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
