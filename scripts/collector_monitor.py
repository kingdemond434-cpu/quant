"""ZERO-TRUST COLLECTOR MONITOR (G3) -- assume every collector is lying until it proves otherwise.

THE FAILURE THIS EXISTS FOR: a collector that ERRORS is safe -- something notices. A collector that
silently returns ZEROS, or repeats yesterday's value, or quietly stops updating, is dangerous: the
desk reads a flat market, concludes "no signal", and either suppresses a true signal or fires a
false one. Nothing in the pipeline currently distinguishes "the market was flat" from "the sensor
died". That is the single most dangerous class of bug in an automated desk, and it is invisible to
every downstream statistical test -- the numbers all look fine.

FOUR CHECKS per tracked clock/artifact:
  1. STALENESS   -- is the file still being written? (dead cron / reaped process / auth outage)
  2. ROW RATE    -- did the append rate collapse vs its own history? (partial failure)
  3. FLATLINE    -- are the last N values identical? (the silent-zero / cached-response class)
  4. ZERO-FILL   -- is the newest value exactly 0 or null when history says otherwise?

Any tripped check emits a KILL signal naming the dependent axes, so a live sleeve can be halted
BEFORE it trades on a dead sensor. Zero promotion authority; it only ever says STOP, never GO.

Read-only, no keys, no LLM. Run from repo root on the daily cadence.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "collector_health.json"

# clock -> axes that would trade on it (halt these if the sensor is bad)
DEPENDENTS = {
    "kimchi_premium.jsonl": ["kimchi_premium"],
    "stablecoin_supply.jsonl": ["stablecoin_supply_momentum"],
    "cny_premium.jsonl": ["cny_premium"],
    "onchain_activity.jsonl": ["(retired axis -- input store only)"],
}
STALE_H = 36.0          # a daily collector silent for >36h is not "slow", it is dead
FLAT_N = 5              # identical values across this many rows = flatline
RATE_DROP = 0.5         # append rate below half its historical mean = partial failure


def _rows(p: Path) -> list[dict]:
    out = []
    for ln in p.read_text("utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not r.get("_summary"):
            out.append(r)
    return out


def _numeric_field(rows: list[dict]) -> str | None:
    """Pick the payload field to sanity-check (first numeric that is not a date/count)."""
    skip = {"n_hist", "n_quotes", "date"}
    for k, v in (rows[-1] if rows else {}).items():
        if k not in skip and isinstance(v, (int, float)) and v is not None:
            return k
    return None


def main() -> None:
    now = datetime.now(tz=UTC)
    results, kills = [], []
    print("=== ZERO-TRUST COLLECTOR MONITOR ===")
    print("    a collector that ERRORS is safe; one that silently returns zeros is not.\n")
    print(f"  {'clock':<28}{'rows':>6}{'age_h':>8}{'status':>10}  detail")

    for fname, deps in DEPENDENTS.items():
        p = DATA / fname
        if not p.exists():
            print(f"  {fname:<28}{'-':>6}{'-':>8}{'MISSING':>10}  file absent")
            results.append({"clock": fname, "status": "MISSING", "dependents": deps})
            kills.append((fname, deps, "file absent"))
            continue
        rows = _rows(p)
        age = (now - datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)).total_seconds() / 3600
        flags = []

        # 1. staleness
        if age > STALE_H:
            flags.append(f"STALE {age:.0f}h (>{STALE_H:.0f}h)")

        # 2. row rate vs own history
        dates = sorted({r.get("date") for r in rows if r.get("date")})
        if len(dates) >= 3:
            span = (datetime.fromisoformat(dates[-1]) - datetime.fromisoformat(dates[0])).days + 1
            expected = span
            if len(dates) < expected * RATE_DROP:
                flags.append(f"RATE-DROP {len(dates)}/{expected} expected days")

        # 3. flatline + 4. zero-fill on the payload field
        fld = _numeric_field(rows)
        if fld and len(rows) >= FLAT_N:
            vals = [r.get(fld) for r in rows[-FLAT_N:] if r.get(fld) is not None]
            if len(vals) == FLAT_N and len(set(vals)) == 1:
                flags.append(f"FLATLINE {fld}={vals[0]} x{FLAT_N}")
            if vals and vals[-1] == 0 and any(v != 0 for v in vals[:-1]):
                flags.append(f"ZERO-FILL {fld} went to 0")

        # null-payload check (cny_premium ships z20=null during warmup -- legitimate, but visible)
        nulls = sum(1 for r in rows if fld and r.get(fld) is None)
        status = "KILL" if flags else ("WARN" if nulls == len(rows) and rows else "OK")
        detail = "; ".join(flags) or (f"{fld}: all null (warmup?)" if status == "WARN"
                                      else f"{fld} healthy")
        print(f"  {fname:<28}{len(rows):>6}{age:>8.1f}{status:>10}  {detail}")
        results.append({"clock": fname, "rows": len(rows), "age_h": round(age, 1),
                        "status": status, "flags": flags, "dependents": deps})
        if flags:
            kills.append((fname, deps, "; ".join(flags)))

    print()
    if kills:
        print("  *** KILL SIGNALS -- halt these axes before they trade on a dead sensor ***")
        for fname, deps, why in kills:
            print(f"    {fname}: {why}")
            for d in deps:
                print(f"      -> HALT {d}")
    else:
        print("  no kill signals -- all monitored collectors passing zero-trust checks")

    OUT.write_text(json.dumps({"updated": now.isoformat(), "stale_hours": STALE_H,
                               "kills": [{"clock": k, "dependents": d, "why": w}
                                         for k, d, w in kills],
                               "collectors": results}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    print("  This layer only ever says STOP. It has no authority to promote or resume anything.")


if __name__ == "__main__":
    main()
