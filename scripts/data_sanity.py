"""DATA SANITY SCANNER -- systematise the two artifacts that were only caught by eyeball.

TODAY'S EVIDENCE (2 for 2): every data artifact found on 2026-07-27 was found by a human looking
at a number and thinking "that can't be right" -- never by a check.
  COOKIEUSDT  59.17bps slippage IDENTICAL at $100/$250/$500/$1000/$2500. Flat impact across a 25x
              size range is not physically possible. It passed every numeric validator because
              nothing tested for IMPLAUSIBILITY, only for presence.
  mSOL/SOL    539bps std on a ratio that tracks within ~100bps -- a pipeline artifact
              (non-synchronous daily legs), read as a market finding.
Both would have propagated into sizing and alpha decisions. Neither errored. That is the danger:
these are not crashes, they are CONFIDENT WRONG NUMBERS.

SEVEN IMPLAUSIBILITY CHECKS -- each encodes a physical fact about markets, not a threshold:
  1 FLAT-ACROSS-SIZE   slippage identical across size buckets (impact must rise with size)
  2 ZERO-VARIANCE      a "series" that never moves is a constant, not data
  3 IMPLAUSIBLE-VOL    daily vol far outside what the asset class can produce
  4 STALE-REPEAT       long runs of identical consecutive values (cached/failed fetch)
  5 IMPOSSIBLE-RANGE   ratios/premia outside economically possible bounds
  6 GAP-HOLES          missing dates inside the covered span (silent partial failure)
  7 MONOTONE-DRIFT     a bounded quantity that only ever goes one way (accumulator bug)

Scans the desk's own artifacts. Read-only, no LLM, no keys. Run from repo root, daily.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "data_sanity_report.json"

# asset-class physical bounds for daily returns (what markets can actually produce)
MAX_DAILY_VOL = 0.35  # 35% daily std would be extraordinary even for a microcap
MIN_DAILY_VOL = 1e-6
STALE_RUN = 5  # identical consecutive values
FLAT_MIN_BUCKETS = 3


def flag(findings, sev, where, what, why):
    findings.append({"severity": sev, "where": where, "finding": what, "why_impossible": why})
    print(f"  [{sev:<8}] {where:<34} {what}")
    print(f"             -> {why}")


def scan_cost_model(findings):
    p = DATA / "cost_model.json"
    if not p.exists():
        return
    cm = json.loads(p.read_text("utf-8"))
    for sym, legs in cm.get("symbols", {}).items():
        for leg, buckets in legs.items():
            if not isinstance(buckets, dict) or len(buckets) < FLAT_MIN_BUCKETS:
                continue
            pts = sorted(
                (int(k), v.get("median_bps"))
                for k, v in buckets.items()
                if isinstance(v, dict) and v.get("median_bps") is not None
            )
            vals = [v for _, v in pts]
            if len(vals) < FLAT_MIN_BUCKETS:
                continue
            # CHECK 1: impact MUST rise with size; identical across a wide size range is impossible
            if len({round(v, 4) for v in vals}) == 1:
                flag(
                    findings,
                    "CRITICAL",
                    f"cost_model/{sym}/{leg}",
                    f"slippage {vals[0]:.2f}bps IDENTICAL across {len(vals)} size buckets "
                    f"(${pts[0][0]}-${pts[-1][0]})",
                    "market impact must increase with order size; a flat curve means the "
                    "estimator returned a constant, so any sizing decision using it is unfounded",
                )
            # CHECK 5: a leg costing more than ~1% is not tradeable for a carry
            elif max(vals) > 100:
                flag(
                    findings,
                    "HIGH",
                    f"cost_model/{sym}/{leg}",
                    f"max {max(vals):.0f}bps per leg",
                    "4 legs per carry round-trip => >4% cost vs ~0.7%/mo funding harvest; "
                    "structurally unprofitable at any size",
                )


def scan_jsonl(findings):
    for p in sorted(DATA.glob("*.jsonl")):
        rows = []
        for ln in p.read_text("utf-8", errors="ignore").splitlines():
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if not r.get("_summary"):
                rows.append(r)
        if len(rows) < 4:
            continue
        # numeric payload fields
        # CONFIG / METADATA fields are CONSTANT OR MONOTONE BY DESIGN. Flagging them is a false
        # positive, and a validator with a high FP rate trains the reader to ignore it -- which is
        # worse than no validator. window_s=3600 and partition_s=300 are settings; ts is a clock;
        # start_* is a fixed baseline. Only genuine MARKET quantities are checked.
        CONFIG = {
            "n_hist",
            "n_quotes",
            "window_s",
            "partition_s",
            "ts",
            "timestamp",
            "time",
            "interval_s",
            "period_s",
            "lookback",
            "n",
            "count",
            "rows",
            "day",
            "epoch",
            "min_days",
            "need",
            "version",
            "seq",
        }
        keys = [
            k
            for k, v in rows[-1].items()
            if isinstance(v, (int, float))
            and k not in CONFIG
            and not k.startswith(("start_", "cfg_", "param_", "n_", "num_"))
            and not k.endswith(("_s", "_ms", "_id", "_count", "_n", "_seq"))
        ]
        for k in keys:
            vals = [r.get(k) for r in rows if isinstance(r.get(k), (int, float))]
            if len(vals) < 4:
                continue
            arr = np.asarray(vals, dtype="float64")
            # CHECK 2
            if arr.std() == 0:
                flag(
                    findings,
                    "HIGH",
                    f"{p.name}/{k}",
                    f"zero variance across {len(arr)} rows (value {arr[0]})",
                    "a series that never moves is a constant; the collector is echoing, "
                    "not reading",
                )
                continue
            # CHECK 4
            run = mx = 1
            for i in range(1, len(arr)):
                run = run + 1 if arr[i] == arr[i - 1] else 1
                mx = max(mx, run)
            if mx >= STALE_RUN:
                flag(
                    findings,
                    "HIGH",
                    f"{p.name}/{k}",
                    f"{mx} identical consecutive values",
                    "repeated values mean a cached or failed fetch is being recorded as fresh data",
                )
            # CHECK 7: bounded quantities should not be monotone over long stretches
            if (
                len(arr) >= 8
                and "cum" not in k
                and "total" not in k
                and (np.all(np.diff(arr) >= 0) or np.all(np.diff(arr) <= 0))
            ):
                flag(
                    findings,
                    "MEDIUM",
                    f"{p.name}/{k}",
                    f"monotone across all {len(arr)} rows",
                    "a market quantity that only ever moves one way is usually an accumulator "
                    "or a counter mislabelled as a level",
                )
        # CHECK 6: date holes inside the covered span
        ds = sorted({r["date"] for r in rows if r.get("date")})
        if len(ds) >= 3:
            try:
                a, b = date.fromisoformat(ds[0]), date.fromisoformat(ds[-1])
                span = (b - a).days + 1
                if span - len(ds) >= 2:
                    missing = [
                        str(a + timedelta(days=i))
                        for i in range(span)
                        if str(a + timedelta(days=i)) not in set(ds)
                    ]
                    flag(
                        findings,
                        "MEDIUM",
                        f"{p.name}/dates",
                        f"{span - len(ds)} missing days inside span {ds[0]}..{ds[-1]}",
                        f"silent partial failure -- e.g. {missing[:3]}",
                    )
            except ValueError:
                pass


def scan_screens(findings):
    """CHECK 3: implausible vol / IC in saved screen artifacts."""
    for name in (
        "batch_altdata_screen.json",
        "batch_premium_screen.json",
        "structural_spreads.json",
        "hl_feature_factory.json",
    ):
        p = DATA / name
        if not p.exists():
            continue
        d = json.loads(p.read_text("utf-8"))
        for r in d.get("results", []):
            if not isinstance(r, dict):
                continue
            sd = r.get("sd_pct")
            if isinstance(sd, (int, float)) and sd > MAX_DAILY_VOL * 100:
                flag(
                    findings,
                    "CRITICAL",
                    f"{name}/{r.get('name')}",
                    f"sd {sd:.1f}% on a spread/ratio",
                    "far beyond what this quantity can physically produce; almost certainly "
                    "non-synchronous legs or a unit error, not a market observation",
                )
            ic = r.get("ic")
            if isinstance(ic, (int, float)) and abs(ic) > 0.5:
                flag(
                    findings,
                    "CRITICAL",
                    f"{name}/{r.get('name')}",
                    f"IC {ic:+.3f}",
                    "daily-horizon IC above 0.5 implies near-perfect foresight; lookahead or "
                    "alignment error is far more likely than a real signal",
                )


def main() -> None:
    print("=== DATA SANITY SCANNER ===")
    print("    2 of 2 artifacts today were caught by EYEBALL, not by a check. This is the check.")
    print("    These are not crashes -- they are CONFIDENT WRONG NUMBERS that pass every")
    print("    presence-based validator and then propagate into sizing and alpha decisions.\n")
    findings: list[dict] = []
    scan_cost_model(findings)
    scan_jsonl(findings)
    scan_screens(findings)

    sev = {}
    for f in findings:
        sev[f["severity"]] = sev.get(f["severity"], 0) + 1
    print(
        f"\n  {len(findings)} implausibility findings"
        + (f"  ({', '.join(f'{k}:{v}' for k, v in sorted(sev.items()))})" if sev else "")
    )
    if not findings:
        print(
            "  (nothing implausible found -- note this is a WEAKER statement than 'data is "
            "correct')"
        )
    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "n": len(findings),
                "by_severity": sev,
                "findings": findings,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n  -> {OUT}")
    print("  CRITICAL findings should block any sizing or promotion decision that uses that input.")


if __name__ == "__main__":
    main()
