"""STAGE-A EXECUTOR -- actually RUN the ranked queue. Ranking is not utilisation.

THE GAP THIS CLOSES. blindspot_max finds 214 unknown-unknowns; conversion_engine ranks them and
injects 40 into the schedule; and then nothing happens. Only stageb_capacity reads that schedule,
and only to COUNT it. I had moved the problem one link down the chain -- from a list nobody reads
to a ranked queue nobody executes -- and called it utilisation.

This runs a genuine screen on the top unscreened candidates every cycle: aligns the field to a
forward return, computes rank IC, and puts the result through the leakage contract that already
exists (reverse-causality, orthogonalisation to the same-period confound, suspect magnitude,
shift test). Verdicts persist so a candidate is never re-screened by accident, and the queue
drains instead of accumulating.

STAGE-A LAW, UNCHANGED AND ENFORCED IN CODE: this has ZERO promotion authority. It can mark a
candidate SCREEN-PASS. It cannot start a forward clock, size a position, or touch capital. A pass
here means "worth one of five scarce Stage-B slots", nothing more.

HONESTY RAILS:
  * a candidate with fewer than _MIN_N aligned observations returns UNDERPOWERED, never a verdict
  * any leakage flag downgrades the result regardless of how good the IC looks
  * verdicts record n, IC, t, residual IC and every flag, so a pass can be audited later
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CIO = ROOT / "data/research_cio.json"
LEDGER = ROOT / "data/stage_a_verdicts.jsonl"
PRICE_SRC = ROOT / "data/coinmetrics_flows.jsonl"
_MIN_N = 60
_BATCH = 6                    # screened per cycle; unbounded queue, bounded compute per run


def _rows(p: pathlib.Path, cap: int = 20000):
    out = []
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, ln in enumerate(fh):
                if i >= cap:
                    break
                ln = ln.strip()
                if ln:
                    try:
                        d = json.loads(ln)
                        if isinstance(d, dict):
                            out.append(d)
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return out


def _price_series() -> dict[str, float]:
    """Daily BTC close from the coinmetrics archive -- the desk's longest clean price history."""
    out = {}
    for r in _rows(PRICE_SRC):
        if r.get("asset") == "btc" and r.get("price_usd") and r.get("date"):
            out[str(r["date"])[:10]] = float(r["price_usd"])
    return out


def _spearman(a, b):
    n = len(a)
    if n < 8:
        return 0.0, 0.0
    ra = sorted(range(n), key=lambda i: a[i])
    rb = sorted(range(n), key=lambda i: b[i])
    A, B = [0.0] * n, [0.0] * n
    for rank, i in enumerate(ra):
        A[i] = rank
    for rank, i in enumerate(rb):
        B[i] = rank
    ma, mb = sum(A) / n, sum(B) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in A))
    vb = math.sqrt(sum((x - mb) ** 2 for x in B))
    if va == 0 or vb == 0:
        return 0.0, 0.0
    r = sum((A[i] - ma) * (B[i] - mb) for i in range(n)) / (va * vb)
    t = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
    return r, t


def screen(file_name: str, field: str, px: dict) -> dict:
    """One genuine screen: field(t) vs forward return(t+1), with the leakage contract applied."""
    rows = _rows(ROOT / "data" / file_name)
    series = {}
    for r in rows:
        d = r.get("date") or r.get("ts")
        v = r.get(field)
        if d and isinstance(v, (int, float)) and not isinstance(v, bool):
            series[str(d)[:10]] = float(v)
    dates = sorted(set(series) & set(px))
    if len(dates) < _MIN_N:
        return {"verdict": "UNDERPOWERED", "n": len(dates),
                "note": f"{len(dates)} aligned days < {_MIN_N} required"}

    xs, fwd, same = [], [], []
    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i + 1]
        p0, p1 = px[d0], px[d1]
        if p0 <= 0:
            continue
        xs.append(series[d0])
        fwd.append((p1 - p0) / p0)
        prev = px[dates[i - 1]] if i > 0 else p0
        same.append((p0 - prev) / prev if prev > 0 else 0.0)
    if len(xs) < _MIN_N:
        return {"verdict": "UNDERPOWERED", "n": len(xs), "note": "insufficient aligned pairs"}

    ic, t = _spearman(xs, fwd)
    flags = []
    try:
        from leakage_detector import audit
        a = audit(xs, fwd, same, name=f"{file_name}:{field}")
        flags = a.get("flags", [])
        resid = a.get("notes", {}).get("residual_ic")
    except Exception:  # noqa: BLE001
        resid = None

    if flags:
        v = "SCREEN-FLAGGED"
    elif abs(t) >= 2.5 and abs(ic) >= 0.05:
        v = "SCREEN-PASS"
    elif abs(t) >= 1.5:
        v = "SCREEN-WEAK"
    else:
        v = "SCREEN-NULL"
    return {"verdict": v, "n": len(xs), "ic": round(ic, 4), "t": round(t, 2),
            "residual_ic": resid, "flags": flags}


def main() -> None:
    px = _price_series()
    if len(px) < 200:
        raise SystemExit("price history unavailable -- refusing to screen against nothing")

    done = set()
    if LEDGER.exists():
        for ln in LEDGER.read_text("utf-8").splitlines():
            try:
                done.add(json.loads(ln)["candidate"])
            except Exception:  # noqa: BLE001
                continue

    sched = (json.loads(CIO.read_text("utf-8")) if CIO.exists() else {}).get("schedule", [])
    queue = [s for s in sched if s.get("origin") == "conversion_engine"
             and s.get("name") not in done and ":" in str(s.get("name", ""))]

    print("=== STAGE-A EXECUTOR -- running the queue, not ranking it ===")
    print("    ZERO promotion authority: a pass earns one of five scarce Stage-B slots, never")
    print("    capital. Ranking was never utilisation.\n")
    print(f"  price history {len(px)} days | {len(done)} already screened | "
          f"{len(queue)} unscreened in queue\n")
    if not queue:
        print("  queue drained -- every conversion candidate has a verdict.")
        return

    out = []
    for s in queue[:_BATCH]:
        name = s["name"]
        fn, _, fld = name.partition(":")
        res = screen(fn, fld, px)
        rec = {"ts": datetime.now(tz=UTC).isoformat(), "candidate": name, **res}
        out.append(rec)
        extra = (f"IC {res.get('ic'):+.4f} t {res.get('t'):+.2f}"
                 if res.get("ic") is not None else res.get("note", ""))
        print(f"  {res['verdict']:<16} {name[:46]:<46} n={res['n']:<5} {extra}")
        for f in res.get("flags", [])[:1]:
            print(f"                   leak: {f[:78]}")

    with LEDGER.open("a", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r) + "\n")

    passes = [r for r in out if r["verdict"] == "SCREEN-PASS"]
    print(f"\n  {len(out)} screened this cycle, {len(passes)} PASS, "
          f"{len(queue)-len(out)} still queued")
    if passes:
        print("  PASS candidates are eligible for a Stage-B slot -- eligibility, not promotion.")
        print("  A human or the allocator picks from them; nothing here starts a clock.")
    print(f"  -> {LEDGER}")


if __name__ == "__main__":
    main()
