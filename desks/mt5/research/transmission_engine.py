"""Canonical country-to-asset transmission graph, measured where both legs exist.

Country packs declare causal channels; declarations are hypotheses, never evidence. This organ
loads every pack, conserves every seed, aligns PIT-certified series or broker bars, measures the
declared lag out of sample, and publishes admitted plus unresolved edges. It proposes no capital.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import country_lab as CL  # noqa: E402

REPORT = DESK / "reports" / "TRANSMISSION_GRAPH.json"
PACK_ROOT = DESK / "research" / "countries"
MIN_N = 80
MIN_ABS_T = 2.0
MIN_OOS_SIGN = 0.5


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, path)


def load_packs() -> tuple[dict[str, CL.CountryPack], list[str]]:
    packs: dict[str, CL.CountryPack] = {}
    notes: list[str] = []
    for path in sorted(PACK_ROOT.glob("*/pack.py")):
        code = path.parent.name
        if code.startswith("_") or code in {"global", "institutional", "jp"}:
            continue
        pack = CL.resolve_pack(code)
        if pack is None:
            notes.append(f"{code}: pack did not resolve")
        else:
            packs[code] = pack
    return packs, notes


def seed_edges(packs: Mapping[str, CL.CountryPack]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, pack in sorted(packs.items()):
        for idx, raw in enumerate(pack.transmission_edges_seed):
            row = asdict(raw) if is_dataclass(raw) else dict(raw)
            source = (f"sym:{row.get('source_symbol')}" if row.get("source_symbol") else
                      f"series:{row.get('source_series')}" if row.get("source_series") else "")
            target = f"sym:{str(row.get('asset') or '').upper()}"
            rows.append({"id": f"{code}:{idx}:{row.get('asset')}", "origin": code,
                         "from_country": code, "to_country": row.get("to_country") or "global",
                         "source": source, "target": target, "asset": row.get("asset"),
                         "actor": row.get("actor"), "constraint": row.get("constraint"),
                         "flow": row.get("flow"), "lag_days": row.get("lag_days", 1.0),
                         "era": row.get("era"), "notes": row.get("notes"),
                         "evidence_state": "HYPOTHESIS", "measured": False})
    return rows


def _leg_series(selector: str) -> tuple[np.ndarray, np.ndarray] | None:
    kind, _, name = str(selector).partition(":")
    if kind == "sym" and name:
        for chart in ("D1", "H4", "H1"):
            path = DESK / "data" / "universe" / f"{name.upper()}_{chart}.parquet"
            if not path.exists():
                continue
            try:
                frame = pd.read_parquet(path)
                if "time" in frame.columns:
                    frame = frame.set_index("time")
                close = pd.to_numeric(frame["close"], errors="coerce")
                close.index = pd.to_datetime(close.index, utc=True, errors="coerce")
                close = close[~close.index.isna()].sort_index().resample("1D").last().dropna()
                ret = np.log(close).diff().dropna()
                return ret.index.values.astype("datetime64[D]"), ret.to_numpy(float)
            except Exception:
                continue
    if kind == "series" and name:
        try:
            from research.acquire_datasets import acquired_series
            series = acquired_series(require_authority=True).get(name)
            if series is None:
                return None
            s = pd.to_numeric(series, errors="coerce").dropna().sort_index()
            if len(s) < 3:
                return None
            values = s.diff().dropna()
            return pd.to_datetime(values.index, utc=True).values.astype("datetime64[D]"), \
                values.to_numpy(float)
        except Exception:
            return None
    return None


def _measure(row: Mapping[str, Any]) -> dict[str, Any]:
    a, b = _leg_series(str(row.get("source") or "")), _leg_series(str(row.get("target") or ""))
    if a is None or b is None:
        return {**row, "why": "source or target series is absent/PIT-uncertified"}
    common = np.intersect1d(a[0], b[0])
    lag = max(0, round(float(row.get("lag_days") or 0)))
    if len(common) <= MIN_N + lag:
        return {**row, "why": f"only {len(common)} aligned day(s); need > {MIN_N + lag}"}
    apos, bpos = np.searchsorted(a[0], common), np.searchsorted(b[0], common)
    x, y = np.asarray(a[1])[apos], np.asarray(b[1])[bpos]
    if lag:
        x, y = x[:-lag], y[lag:]
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < MIN_N or np.std(x) <= 0 or np.std(y) <= 0:
        return {**row, "why": "aligned series has insufficient finite variation"}
    cut = max(MIN_N // 2, int(len(x) * 0.67))
    rho = float(np.corrcoef(x, y)[0, 1])
    rho_is, rho_oos = float(np.corrcoef(x[:cut], y[:cut])[0, 1]), \
        float(np.corrcoef(x[cut:], y[cut:])[0, 1])
    t = rho * math.sqrt(max(1.0, (len(x) - 2) / max(1e-12, 1.0 - rho * rho)))
    stable = rho_is * rho_oos > 0 and abs(rho_oos) >= abs(rho_is) * MIN_OOS_SIGN
    admitted = abs(t) >= MIN_ABS_T and stable
    return {**row, "measured": True, "n": len(x), "strength": round(rho, 6),
            "t": round(t, 4), "is_strength": round(rho_is, 6),
            "oos_strength": round(rho_oos, 6),
            "evidence": {"admitted": admitted, "stable_oos": stable,
                         "why": "|t|>=2 and OOS sign/magnitude stable"},
            "evidence_state": "DESK_MEASURED" if admitted else "HYPOTHESIS"}


def run(*, budget_s: float = 900.0, out: Path = REPORT) -> dict[str, Any]:
    started = time.monotonic()
    packs, notes = load_packs()
    rows = seed_edges(packs)
    measured: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if time.monotonic() - started >= budget_s:
            deferred = rows[i:]
            break
        measured.append(_measure(row))
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "packs": len(packs), "seeds": len(rows), "measured": sum(
               bool(r.get("measured")) for r in measured),
           "admitted": sum(bool((r.get("evidence") or {}).get("admitted")) for r in measured),
           "deferred": len(deferred), "notes": notes, "edges": [*measured, *deferred],
           "conservation": {"identity_holds": len(rows) == len(measured) + len(deferred),
                            "seeded": len(rows), "disposed": len(measured),
                            "deferred": len(deferred)},
           "boundary": "declared channels are hypotheses; only measured stable OOS edges admit"}
    _atomic(out, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-s", type=float, default=900.0)
    parser.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    doc = run(budget_s=args.budget_s, out=args.out)
    print(f"transmission engine: packs={doc['packs']} seeds={doc['seeds']} "
          f"measured={doc['measured']} admitted={doc['admitted']} deferred={doc['deferred']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
