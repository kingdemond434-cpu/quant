#!/usr/bin/env python3
"""L1.63 -- a robustness certificate whose partition CANNOT FAIL carries no information.

    FENCED by `scripts/check_partition_power.py` over `libs/validation/partition_power.py`.
                                                             -- docs/CONSTITUTION.md:2773

THE LAW. Gates like `regime_robust`, `min_regimes_positive` and `two_regimes` certify a sleeve by
splitting its returns into groups and requiring every group to be positive. That is only evidence
if some group COULD have been negative. A partition whose groups are too small to grade, or whose
labels collapse to one value, produces "every group was positive" from a test that could not have
said anything else -- and "every group passed" and "no group had enough observations to tell" are
different claims, only one of which is evidence (L1.28a).

WHY THIS FILE WAS ABSENT AND HAD TO BE REWRITTEN RATHER THAN RESTORED. The original fence graded
crypto-exchange partitions: its axes were `funding_state` and `funding_breadth`, it imported
`libs.research.crypto_regime`, and its basket size was documented as "the live carry sleeve's
basket size (run_cashcarry_executor `top`)". Every one of those is retired under the MT5 universe
mandate, so the file was correctly deleted with the crypto desk -- and the LAW it fenced was not
deleted with it. Measured 2026-09-05: `docs/CONSTITUTION.md` still names this path as L1.63's
fence, `desks/mt5/data/release_identity.json` still lists it, and four tests in
`tests/validation/test_partition_power.py` had been failing on `ModuleNotFoundError` for as long
as the file had been gone. A law whose enforcement was purged along with a retired desk is a law
that stopped being enforced without anyone deciding it should.

So this grades the SAME LAW over the partitions this desk actually certifies on:

    vol_terciles_WIRED   realised-vol terciles -- the axis `regime_robust` and friends use, which
                         is why it carries WIRED in its name: dropping it from the roster blinds
                         the fence to the live gate rather than merely narrowing it
    session              the desk's own trading windows, which is how every family cell is
                         selected and therefore the partition a session sleeve is most likely to
                         be silently welded on
    day_of_week          a cheap, always-available axis: a certificate that cannot fail on the
                         weekday split is one whose sample is too short to say anything

VERDICTS, and only two of five pass. `OK` and `PARTIAL` mean the partition could have failed and
did not. `WELDED` means it could not have failed -- the certificate is decoration. `UNMEASURED`
means there were not enough observations to know, which is NOT a pass: a report nobody can fail is
not a fence, and this exits non-zero on both.

    python scripts/check_partition_power.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.autodiscovery.regime import vol_regime_labels  # noqa: E402
from libs.validation.partition_power import (  # noqa: E402
    UNLABELLED,
    partition_power,
    summarise,
)

_OUT = _ROOT / "data" / "partition_power.json"

#: The only two verdicts that let this exit zero. WELDED and UNMEASURED are both failures and for
#: the same reason: neither is evidence that the sleeve survives a hostile split.
_PASSING = frozenset({"OK", "PARTIAL"})

#: The desk's trading windows, by UTC hour, as `run_hunt16.WINDOWS` defines them. Duplicated here
#: as BOUNDARIES rather than imported, because this fence must run on a machine with no desk
#: modules importable -- and the boundaries are a property of the sessions, not of that file.
_SESSIONS: tuple[tuple[str, int, int], ...] = (
    ("asia", 0, 7), ("london_am", 7, 13), ("ny_open", 13, 14), ("afternoon", 14, 24),
)


def _session_labels(index: pd.DatetimeIndex) -> np.ndarray:
    hours = np.asarray(index.hour if hasattr(index, "hour") else [0] * len(index))
    out = np.full(len(hours), UNLABELLED, dtype=object)
    for name, lo, hi in _SESSIONS:
        out[(hours >= lo) & (hours < hi)] = name
    return out.astype(str)


def build_partitions(returns: pd.Series) -> dict[str, np.ndarray]:
    """Every axis this fence grades, aligned to `returns`.

    THE ROSTER IS THE FENCE'S SCOPE, so a partition dropped from here is a partition nobody checks
    -- which is why `tests/validation/test_partition_power.py` asserts the WIRED axis is present.
    Each label array must be the same length as the series; a shorter one would silently grade a
    prefix and report the result as if it covered everything.
    """
    r = np.asarray(returns, dtype="float64")
    idx = returns.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(pd.Index(idx), errors="coerce", utc=True)
    vol = vol_regime_labels(r)
    return {
        "vol_terciles_WIRED": np.where(vol < 0, UNLABELLED, vol.astype(str)),
        "session": _session_labels(idx),
        "day_of_week": np.asarray([str(d) for d in getattr(idx, "dayofweek", [0] * len(r))]),
    }


def _series() -> tuple[dict[str, pd.Series], str]:
    """Certified sleeve daily returns, from the allocator's own replay. Never a second copy."""
    try:
        sys.path.insert(0, str(_ROOT / "desks" / "mt5" / "research"))
        from pf_allocator import certified_evidence
        series, acct = certified_evidence()
        return series, f"certified library: {acct.get('priced')} priced"
    except Exception as exc:
        return {}, f"certified evidence unavailable ({type(exc).__name__}: {exc})"


def check() -> dict[str, Any]:
    series, why = _series()
    if not series:
        return {"status": "UNMEASURED", "why": why, "partitions": {},
                "note": ("no certified return series on this host, so no partition can be graded. "
                         "UNMEASURED is not a pass -- it is the absence of the evidence L1.63 "
                         "requires, and it exits non-zero for that reason")}
    rows: list[Any] = []
    for name, ser in series.items():
        s = pd.Series(np.asarray(ser, dtype="float64"), index=pd.Index(ser.index))
        for axis, labels in build_partitions(s).items():
            rows.append(partition_power(np.asarray(s, dtype="float64"), labels,
                                        name=f"{name}::{axis}"))
    doc = summarise(rows)
    statuses = {str(getattr(v, "status", "")) for v in rows}
    failing = sorted(statuses - _PASSING)
    doc.update({
        "status": "OK" if not failing else "BREACH",
        "failing_statuses": failing,
        "sleeves": len(series), "partitions_graded": len(rows),
        "source": why,
        "law": ("a robustness certificate whose partition cannot fail carries no information; "
                "WELDED and UNMEASURED are both failures and neither is a pass"),
    })
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    out = check()
    try:
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    except OSError:
        pass
    if args.json:
        print(json.dumps(out, indent=1, default=str))
    else:
        print(f"partition power (L1.63): {out.get('partitions_graded', 0)} partition(s) over "
              f"{out.get('sleeves', 0)} sleeve(s) -- {out['status']}")
        if out.get("why"):
            print(f"  {out['why']}")
        for s in out.get("failing_statuses") or []:
            print(f"  FAILING STATUS {s}")
    return 0 if out["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
