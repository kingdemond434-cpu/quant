"""MOAT PHASE 1 -- validate the order-book mine BEFORE mining it, then extract liquidity state.

WHY PHASE 1 FIRST, and it is not bureaucracy: TWO of today's "findings" (COOKIEUSDT 59bps flat,
mSOL/SOL 539bps sd) were DATA ARTIFACTS caught only by eyeball. Running unsupervised regime
clustering on 4.4GB of unvalidated snapshots would manufacture "regimes" out of gaps, stale books
and crossed quotes -- and they would look completely convincing because clustering always returns
clusters. The Book Quality Score below is what stops that.

data/moat = 11,980 hourly .jsonl.gz files, top-20 both sides, 30 symbols x {spot, fut}. This is the
only PROPRIETARY dataset the desk owns: nobody else has these snapshots at these timestamps.
Everything else it researches (GitHub, TVL, on-chain, social) is available to anyone.

PHASE 1 CHECKS (per symbol):
  coverage      -- hours present vs hours expected across the span (gaps = silent recorder death)
  crossed       -- bid >= ask: impossible; means a torn/interleaved snapshot
  stale         -- consecutive identical top-of-book: the recorder echoing, not reading
  spread sanity -- absurd spreads flag a malformed or illiquid book
  depth present -- zero/empty ladders

PHASE 2 (only on symbols that PASS): extract the liquidity state series that regime discovery
would consume -- spread_bps, depth within 1% of touch (both sides), and book imbalance. Reports
the DISPERSION of those states, because a regime model is only worth building if the states
actually vary.

Read-only. Samples rather than reading 4.4GB. Run from repo root.
"""
from __future__ import annotations

import gzip
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MOAT = ROOT / "data/moat"
OUT = ROOT / "data/moat_quality.json"
SAMPLE_FILES = 6          # hourly files per symbol
SAMPLE_ROWS = 250         # snapshots per file


def parse(line: str):
    """Parse a DEPTH record only. The moat is a MIXED stream: k='d' depth records interleaved
    with k='t' TRADE records (~8x more numerous). The first audit read the first N lines of each
    file -- almost all trades -- and counted them as corrupt books, producing 82-99% 'stale' and
    a verdict that the dataset was unusable. It is not; the parser was."""
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        return None
    if d.get("k") != "d":
        return "skip"
    b, a = d.get("b") or d.get("bids"), d.get("a") or d.get("asks")
    if not b or not a:
        return None
    try:
        bp, _bq = float(b[0][0]), float(b[0][1])
        ap, _aq = float(a[0][0]), float(a[0][1])
    except (TypeError, ValueError, IndexError):
        return None
    if bp <= 0 or ap <= 0:
        return None
    mid = (bp + ap) / 2
    # depth within 1% of touch, both sides
    db = sum(float(p) * float(q) for p, q in b if float(p) >= mid * 0.99)
    da = sum(float(p) * float(q) for p, q in a if float(p) <= mid * 1.01)
    return {"bp": bp, "ap": ap, "mid": mid, "spread_bps": (ap - bp) / mid * 1e4,
            "db": db, "da": da, "t": d.get("t") or d.get("E") or d.get("ts")}


def audit(sym_dir: Path):
    files = sorted(sym_dir.glob("*.jsonl.gz"))
    if not files:
        return None
    pick = files if len(files) <= SAMPLE_FILES else random.sample(files, SAMPLE_FILES)
    rows, crossed, stale, bad = [], 0, 0, 0
    prev = None
    for f in sorted(pick):
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()   # scan all; depth rows are ~10% of the stream
        except Exception:
            continue
        for ln in lines:
            r = parse(ln)
            if r == "skip":
                continue
            if r is None:
                bad += 1
                continue
            if r["bp"] >= r["ap"]:
                crossed += 1
                continue
            if prev is not None and r["bp"] == prev["bp"] and r["ap"] == prev["ap"]:
                stale += 1
            prev = r
            rows.append(r)
    if len(rows) < 50:
        return None
    n = len(rows) + bad + crossed
    sp = np.array([r["spread_bps"] for r in rows])
    dep = np.array([r["db"] + r["da"] for r in rows])
    imb = np.array([r["db"] / max(r["db"] + r["da"], 1e-9) for r in rows])
    # hours covered vs span
    span_h = len(files)
    q = 100.0
    q -= min(40, crossed / max(1, n) * 100 * 4)         # crossed books are fatal
    q -= min(25, stale / max(1, len(rows)) * 100)       # stale = recorder echoing
    q -= min(20, bad / max(1, n) * 100 * 2)             # unparseable
    if np.median(sp) > 100:
        q -= 15                                          # absurd median spread
    if dep.std() == 0:
        q -= 20                                          # depth never varies = not real
    return {"snapshots": len(rows), "files": span_h, "bad": bad, "crossed": crossed,
            "stale": stale, "stale_pct": round(stale / max(1, len(rows)) * 100, 2),
            "spread_bps_med": round(float(np.median(sp)), 3),
            "spread_bps_p95": round(float(np.percentile(sp, 95)), 3),
            "depth_usd_med": round(float(np.median(dep)), 0),
            "depth_cv": round(float(dep.std() / max(dep.mean(), 1e-9)), 3),
            "imbalance_sd": round(float(imb.std()), 4),
            "quality": round(max(0.0, q), 1)}


def main() -> None:
    random.seed(7)
    have_mine = MOAT.exists()
    if not have_mine:
        # The order-book mine lives on the recording box. Its absence is not a reason to skip the
        # REGISTRY half of the moat picture, which is measurable anywhere -- skipping it here is
        # how "audit the moat" quietly came to mean "audit the one dataset this file knew about".
        print("no data/moat -- order-book audit skipped; registry portfolio still measured")
    print("=== MOAT PHASE 1: validate before mining ===" if have_mine else "")
    print("    clustering unvalidated books manufactures regimes from gaps -- this stops that\n")
    out = {}
    for side in ("fut", "spot"):
        base = MOAT / side
        if not base.exists():
            continue
        syms = sorted(p for p in base.iterdir() if p.is_dir())
        print(f"--- {side}: {len(syms)} symbols")
        print(f"  {'symbol':<14}{'snaps':>7}{'files':>7}{'stale%':>8}{'sprd_med':>10}"
              f"{'depth$':>12}{'depthCV':>9}{'imbSD':>8}{'Q':>6}")
        for sd in syms:
            a = audit(sd)
            if not a:
                print(f"  {sd.name:<14} (unreadable / too few snapshots)")
                continue
            out[f"{side}/{sd.name}"] = a
            print(f"  {sd.name:<14}{a['snapshots']:>7}{a['files']:>7}{a['stale_pct']:>8.1f}"
                  f"{a['spread_bps_med']:>10.2f}{a['depth_usd_med']:>12,.0f}"
                  f"{a['depth_cv']:>9.2f}{a['imbalance_sd']:>8.3f}{a['quality']:>6.0f}")
        print()

    if out:
        qs = np.array([v["quality"] for v in out.values()])
        cvs = np.array([v["depth_cv"] for v in out.values()])
        good = [k for k, v in out.items() if v["quality"] >= 80]
        print(f"  {len(out)} symbol-sides audited | median quality {np.median(qs):.0f} "
              f"| {len(good)} pass (Q>=80)")
        print(f"  depth coefficient-of-variation: median {np.median(cvs):.2f}")
        print(f"  -> {'STATES VARY ENOUGH for regime discovery' if np.median(cvs) > 0.25 else 'DEPTH BARELY VARIES -- regime clustering would be fitting noise'}")
        worst = sorted(out.items(), key=lambda kv: kv[1]["quality"])[:3]
        print("\n  lowest quality (exclude from any regime model):")
        for k, v in worst:
            print(f"    {k:<20} Q={v['quality']:.0f}  stale {v['stale_pct']:.1f}%  "
                  f"crossed {v['crossed']}  bad {v['bad']}")
    # ---------------------------------------------------------------- RANK 4 registry feed
    # THE ORDER-BOOK MINE IS NOT THE WHOLE MOAT, and auditing only what this file already knew
    # about is how the desk ends up measuring the moat it remembers rather than the one it owns --
    # exactly GAP_REGISTER #77's failure, one layer up. The data registry MEASURES every asset a
    # collector writes, so it is the authority on what exists; this audit stays the authority on
    # order-book QUALITY. Reading it here means a newly-added perishable feed appears in the moat
    # picture automatically, with no edit to this script.
    portfolio: dict[str, Any] = {}
    try:
        from libs.research.data_registry import REPL_PROPRIETARY, build
        assets = build(ROOT)
        moaty = [a for a in assets if a.moat_score > 0]
        portfolio = {
            "assets_scored": len(assets),
            "with_moat": len(moaty),
            "proprietary": [a.id for a in assets if a.replication == REPL_PROPRIETARY],
            "top": [{"id": a.id, "moat": a.moat_score, "research_value": a.research_value,
                     "span_days": a.span.days, "dqs": a.quality.dqs, "replication": a.replication}
                    for a in sorted(moaty, key=lambda x: -x.moat_score)[:10]],
            # Long history nobody queries is paid-for capability sitting idle (L2.9) -- the
            # cot_zcache case row #77 called out separately.
            "unread_long_history": [a.id for a in assets
                                    if (a.span.days or 0) > 365 and not a.consumers],
        }
        print(f"\n  REGISTRY FEED: {len(assets)} assets scored, {len(moaty)} carry any moat")
        for t in portfolio["top"][:5]:
            print(f"    {t['id']:<26} moat={t['moat']:<6} value={t['research_value']:<6} "
                  f"{t['span_days'] or '?'}d  {t['replication']}")
        if portfolio["unread_long_history"]:
            print(f"    PARALYSIS (>1y history, no reader): "
                  f"{', '.join(portfolio['unread_long_history'])}")
        if not moaty:
            print("    no asset carries moat on this box -- expected where the lake is absent; "
                  "moat is scored from MEASURED span, and an unmeasured span scores nothing")
    except Exception as e:
        portfolio = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
        print(f"\n  REGISTRY FEED unavailable: {portfolio['error']}")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "sample_files_per_symbol": SAMPLE_FILES,
                               "symbols": out,
                               "registry_portfolio": portfolio}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
