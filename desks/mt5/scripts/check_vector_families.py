#!/usr/bin/env python3
"""BOX IDENTITY CHECK FOR `MT5_VECTOR_FAMILIES`: same signals, measured on THIS machine.

`mt5desk.families_vector` makes the judge's costliest families fast and must return the same
Signal lists as the original loops it shadows -- on the live gateway's signal path too. The
identity proof that ships with the change ran on the build containers (pandas 3.0.5 / numpy
2.5.3 and pandas 2.3.3 / numpy 2.4.6). The trading box's own versions were never measured, and
the fast paths lean on pandas behaviour (groupby order, rolling, Timestamp boxing) that a
version can move. So before default-on takes effect on the box, this runs there:

    python desks/mt5/scripts/check_vector_families.py                 # report, exit 0/1/2
    python desks/mt5/scripts/check_vector_families.py \
        --out desks/mt5/reports/vector_families_check.json

READ-ONLY unless `--out` is given. Cheap: a few real parquets from `data/universe`, every
vectorised family on a handful of parameter sets, `_atr`, and the hostile inputs the 2026-10-28
audit named (NaT stamps, nullable/object dtypes, duplicated columns), each run with the switch
OFF then ON in this process. Well under two minutes on either box.

Exit 0: every case identical. Exit 1: a mismatch -- set `MT5_VECTOR_FAMILIES=0` for the judge
and the gateway and report the JSON. Exit 2: UNMEASURED (no parquets here), which is not a pass.
The JSON names python / pandas / numpy versions and the switch's mode as read now, so the
artifact is also the attestation of which path a box was running.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from mt5desk import families, families_vector  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402

UNIVERSE = DESK / "data" / "universe"
CHARTS = ("EURUSD_H1", "XAUUSD_H1", "AUDCAD_M15", "XAUUSD_M15", "USDJPY_H1")
MAX_CHARTS = 3


def _fam(name: str) -> Any:
    fn = getattr(families, f"family_{name}", None)
    return fn if fn is not None else fo.ORTHOGONAL_FAMILIES[name]


#: (family, params) run on every chart. Extend when a family joins `families_vector`.
CASES: list[tuple[str, dict[str, Any]]] = [
    ("session_range_breakout", {}),
    ("session_range_breakout", {"range_start": 8, "range_end": 13, "midpoint_filter": "prev_day",
                                "trend_filter": "aligned", "vol_filter": "high"}),
    ("session_range_breakout", {"range_start": 22, "range_end": 2, "spread_gate": True,
                                "range_filter": "large"}),
    ("failed_breakout", {}),
    ("failed_breakout", {"level": "pwh", "spread_gate": True, "min_pierce_atr": 0.0}),
    ("ict_fvg", {}),
    ("ict_fvg", {"ema_fast": 5, "ema_slow": 55, "atr_n": 10}),
    ("multi_speed_trend", {}),
    ("multi_speed_trend", {"crisis_only": True, "hold_days": 1, "min_agreement": 0.5}),
    ("formula", {"expr": "sub(close, open)", "entry_z": 0.5}),
    ("formula", {"expr": ["ts_rank", "spread", 240], "side_mode": "fade", "hold_bars": 8}),
]

#: (family, params) run on the hostile variants of the first chart.
HOSTILE: list[tuple[str, dict[str, Any]]] = [
    ("session_range_breakout", {"midpoint_filter": "prev_day"}),
    ("failed_breakout", {}),
    ("ict_fvg", {}),
    ("multi_speed_trend", {"hold_days": 1, "min_agreement": 0.5}),
    ("formula", {"expr": "sub(close, open)"}),
]


def _same(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, pd.Timestamp):
        return bool(a.value == b.value and a.unit == b.unit and str(a.tz) == str(b.tz))
    if isinstance(a, (float, np.floating)):
        return np.asarray(a).tobytes() == np.asarray(b).tobytes()
    return bool(a == b)


def _call(flag: str, fn: Any, frame: pd.DataFrame, kw: dict[str, Any]) -> Any:
    os.environ[families_vector.ENV] = flag
    try:
        out = fn(frame, **kw)
    except Exception as exc:  # the exception IS the answer being compared
        return ("raised", type(exc).__name__, str(exc))
    if isinstance(out, pd.Series):
        return ("series", str(out.name), str(out.dtype), out.to_numpy().tobytes(), out.index)
    return list(out or [])


def _diff(old: Any, new: Any) -> str | None:
    if isinstance(old, tuple) or isinstance(new, tuple):
        if isinstance(old, tuple) and isinstance(new, tuple) and old[0] == "series" == new[0]:
            same = old[1:4] == new[1:4] and old[4].equals(new[4])
            return None if same else "series values differ"
        return None if old == new else f"outcome {str(old)[:120]} vs {str(new)[:120]}"
    if len(old) != len(new):
        return f"len {len(old)} != {len(new)}"
    for k, (x, y) in enumerate(zip(old, new, strict=True)):
        if type(x) is not type(y):
            return f"signal {k} type"
        for f in dataclasses.fields(x):
            if not _same(getattr(x, f.name), getattr(y, f.name)):
                return f"signal {k} field {f.name}"
    return None


def _hostile(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = df.iloc[:3000]
    stamps = df.index.to_numpy().copy()
    stamps[[0, 100, 1500]] = np.datetime64("NaT", "ns")
    out = {"nat": df.set_axis(pd.DatetimeIndex(stamps, tz=df.index.tz), axis=0),
           "nullable": df.convert_dtypes(),
           "object_close": df.astype({"close": object}),
           "dup_high": pd.concat([df, df[["high"]]], axis=1)}
    return out


def run() -> dict[str, Any]:
    started = time.perf_counter()
    prior = os.environ.get(families_vector.ENV)
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "host": platform.node(),
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "mode_as_found": families_vector.mode(),
        "charts": [], "cases": 0, "signals": 0, "mismatches": [], "verdict": "UNMEASURED",
    }
    charts = [c for c in CHARTS if (UNIVERSE / f"{c}.parquet").exists()][:MAX_CHARTS]
    report["charts"] = charts
    try:
        for k, chart in enumerate(charts):
            df = pd.read_parquet(UNIVERSE / f"{chart}.parquet")
            jobs: list[tuple[str, str, Any, pd.DataFrame, dict[str, Any]]] = [
                (chart, name, _fam(name), df, kw) for name, kw in CASES]
            jobs += [(chart, "_atr", lambda f, n: families._atr(families._h1(f), n), df, {"n": n})
                     for n in (14, 20)]
            if k == 0:
                for label, frame in _hostile(df).items():
                    jobs += [(f"{chart}:{label}", name, _fam(name), frame, kw)
                             for name, kw in HOSTILE]
                    jobs.append((f"{chart}:{label}", "_atr", families._atr, frame, {"n": 14}))
            for where, name, fn, frame, kw in jobs:
                old = _call("0", fn, frame, kw)
                new = _call("1", fn, frame, kw)
                report["cases"] += 1
                if isinstance(old, list):
                    report["signals"] += len(old)
                why = _diff(old, new)
                if why:
                    report["mismatches"].append({"chart": where, "family": name,
                                                 "params": {q: str(v) for q, v in kw.items()},
                                                 "why": why})
    finally:
        if prior is None:
            os.environ.pop(families_vector.ENV, None)
        else:
            os.environ[families_vector.ENV] = prior
    report["fast_path_exceptions"] = families_vector.fallback_counts()
    if charts:
        report["verdict"] = "IDENTICAL" if not report["mismatches"] else "MISMATCH"
    report["seconds"] = round(time.perf_counter() - started, 1)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", help="also write the JSON report here (default: write nothing)")
    args = parser.parse_args(argv)
    report = run()
    text = json.dumps(report, indent=1, default=str)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(text + "\n", encoding="utf-8")
        os.replace(tmp, out)
    return {"IDENTICAL": 0, "MISMATCH": 1}.get(report["verdict"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
