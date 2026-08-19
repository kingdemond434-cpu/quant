"""R0484: screen Bybit isBlockTrade / isRPITrade as institutional-vs-retail conditioning axes.

Every bybit print the desk records carries both flags and ZERO feature code reads them. The
mechanism prior, stated before the run: block prints are negotiated institutional flow (informed,
size-seeking, minimum-size gated by the venue) and RPI prints are retail flow the venue itself
labels for price-improvement matching -- so an interval's block/RPI volume share is a direct
institutional-vs-retail flow mix, the conditioning variable a microstructure edge that only works
against retail flow needs. Bybit's PUBLIC archive does not carry either flag: the desk's own tape
is the only source (L1.46 delta class -- structurally unbuyable), which is also why the 2026-08-17
`rm -rf data/moat` (19.46 GB) cannot be backfilled and this screen starts from the ~9h that has
re-accrued since the recorders came back 08-18 ~19:00 UTC.

SCREEN DISCIPLINE (screen-on-discovery duty): audited harness only (stage_a_screen -- angle-20
de-contam gate baked in), every construction tried is logged as a DSR-counted trial, timestamp
clock DECLARED: bars are cut on the VENUE trade stamp (`time`, ms), never our receipt clock `t`
(L1.46); prints dedup on execId. The pre-registered trial set is deliberately SKINNY (2 signals x
1 horizon x 1 target): the tape cannot power more, and burning multiplicity on cells that cannot
answer is the p-hacking shape the sweep duty forbids. The full mechanism-appropriate sweep runs at
re-screen when the tape has accrued (the report computes that date from its own bar count).

Verdict expectation, stated before the run: SCREEN-UNDERPOWERED. ~9h x 96 bars/day of 15-minute
bars is far under any honest detection floor at ic_min=0.03. That is a real deliverable: the
extraction exists, the axis is registered with a measured n_eff, and the re-screen is one command
-- never record UNDERPOWERED as refuted (L1.28a).
"""

from __future__ import annotations

import gzip
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.ops.lawful import guard  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.panel_breadth import measure_panel_breadth  # noqa: E402

BYBIT = ROOT / "data/moat/bybit"
OUT = ROOT / "reports/axis_screens/bybit_print_flags.json"
BAR_MIN = 15                          # pre-registered; not swept (garden-of-forking-paths rule)
MIN_OBS_PER_SYM = 30                  # bars, before the harness's own z-window warmup
HORIZON_DAYS = BAR_MIN / (60.0 * 24)  # drives Sharpe annualisation in the harness

TRIALS: list[dict] = []


def load_bars() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """15-min bars per symbol: close, block volume share, RPI volume share.

    Bars are labelled by the VENUE trade stamp (`time`), the clock the prints actually happened
    on; our receipt stamp `t` stays in the tape untouched (L1.46: the delta is first-class, the
    mix is not). execId dedups reconnect replays -- counted, never silent (L1.60).
    """
    closes: dict[str, pd.Series] = {}
    blocks: dict[str, pd.Series] = {}
    rpis: dict[str, pd.Series] = {}
    n_files = n_rows = n_dupes = n_badrows = 0
    for symdir in sorted(BYBIT.iterdir() if BYBIT.is_dir() else []):
        if not symdir.is_dir():
            continue
        seen: set[str] = set()
        recs: list[tuple[int, float, float, bool, bool]] = []
        for f in sorted(symdir.glob("*.jsonl.gz")):
            n_files += 1
            try:
                raw = gzip.decompress(f.read_bytes()).decode("utf-8", errors="ignore")
            except OSError:
                n_badrows += 1        # attrition counted: an unreadable file is not "no trades"
                continue
            for line in raw.splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    n_badrows += 1
                    continue
                if r.get("k") != "trades":
                    continue
                for p in r.get("v") or []:
                    eid = str(p.get("execId"))
                    if eid in seen:
                        n_dupes += 1
                        continue
                    seen.add(eid)
                    try:
                        recs.append((int(p["time"]), float(p["price"]),
                                     float(p["price"]) * float(p["size"]),
                                     bool(p.get("isBlockTrade")), bool(p.get("isRPITrade"))))
                    except (KeyError, TypeError, ValueError):
                        n_badrows += 1
        if not recs:
            continue
        n_rows += len(recs)
        df = pd.DataFrame(recs, columns=["ms", "px", "usd", "blk", "rpi"])
        df["bar"] = pd.to_datetime(df["ms"], unit="ms", utc=True).dt.floor(f"{BAR_MIN}min")
        g = df.sort_values("ms").groupby("bar")
        vol = g["usd"].sum()
        closes[symdir.name] = g["px"].last()
        blocks[symdir.name] = g.apply(
            lambda x: x.loc[x["blk"], "usd"].sum(), include_groups=False) / vol
        rpis[symdir.name] = g.apply(
            lambda x: x.loc[x["rpi"], "usd"].sum(), include_groups=False) / vol
    info = {"files": n_files, "prints": n_rows, "dupes_dropped": n_dupes,
            "bad_rows": n_badrows}
    return (pd.DataFrame(closes).sort_index(), pd.DataFrame(blocks).sort_index(),
            pd.DataFrame(rpis).sort_index(), info)


def stack(sig: pd.DataFrame, tgt: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict]:
    """Symbol-major stack for the harness (screen_oi_ls_axes idiom, boundary bleed reported)."""
    ss, tt, blocks = [], [], 0
    for c in sig.columns:
        j = pd.concat([sig[c].rename("s"), tgt[c].rename("t")], axis=1).dropna()
        if len(j) < MIN_OBS_PER_SYM:
            continue
        ss.append(j["s"].to_numpy("float64"))
        tt.append(j["t"].to_numpy("float64"))
        blocks += 1
    if not ss:
        return np.array([]), np.array([]), {"blocks": 0, "rows": 0}
    s, t = np.concatenate(ss), np.concatenate(tt)
    return s, t, {"blocks": blocks, "rows": len(s),
                  "boundary_bleed_frac": round((blocks * 21) / max(len(s), 1), 5)}


def run(name: str, sig: pd.DataFrame, tgt: pd.DataFrame) -> dict:
    s, t, info = stack(sig, tgt)
    if len(s) < 100:
        out: dict = {"name": name, "verdict": "INSUFFICIENT-DATA", "n": len(s)}
    else:
        breadth = measure_panel_breadth(sig.to_numpy(), tgt.to_numpy(),
                                        min_obs=MIN_OBS_PER_SYM)
        out = stage_a_screen(s, t, name=name, horizon_days=HORIZON_DAYS,
                             panel_width=info["blocks"], overlap_periods=1.0,
                             xs_neff=breadth.xs_neff if breadth.measured else None)
        out["breadth"] = breadth.as_dict()
    out.update(info)
    TRIALS.append(out)
    print(f"  {name:44s} n={out.get('n', 0):>6} ic={out.get('ic', 0):+.4f} "
          f"{out['verdict']}", flush=True)
    return out


def novelty() -> dict:
    """Graveyard gate BEFORE compute (universal duty). Advisory; the decision is recorded."""
    try:
        from scripts.build_graveyard_priors import load_priors

        from libs.alpha_factory.hypothesis_novelty import hypothesis_novelty
        res = hypothesis_novelty(
            "bybit isBlockTrade isRPITrade institutional retail flow mix conditioning "
            "microstructure block share per interval",
            features=["bybit", "block_trade", "rpi", "retail_flow", "conditioning"],
            priors=load_priors())
        return {"novelty_score": round(res.novelty_score, 4), "nearest": res.nearest_id,
                "redundant": res.is_redundant}
    except Exception as e:                                    # advisory gate, absence recorded
        return {"unavailable": f"{type(e).__name__}: {e}"}


def main() -> int:
    guard()
    nov = novelty()
    print(f"novelty gate: {nov}", flush=True)
    if nov.get("redundant"):
        print("REFUSING: redundant vs graveyard -- re-testing dead ground burns DSR twice")
        return 2
    px, blk, rpi, load_info = load_bars()
    print(f"bars loaded: {load_info} | panel {px.shape}", flush=True)
    ret = px.pct_change(fill_method=None)
    # Pre-registered trials -- BOTH reported, whatever the verdicts (no winner-only logging).
    run("bybit_block_share->next_bar_abs_ret", blk, ret)
    run("bybit_rpi_share->next_bar_abs_ret", rpi, ret)
    bars_per_day = 24 * 60 // BAR_MIN
    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "bybit_print_flags (isBlockTrade / isRPITrade)",
        "row": "R0484",
        "clock": "bars cut on VENUE trade stamp `time` (ms); receipt `t` untouched (L1.46)",
        "bar_minutes": BAR_MIN,
        "load": load_info,
        "variants_tried": len(TRIALS),   # DSR-counted trials, all reported
        "trials": TRIALS,
        "context": ("tape restarts 2026-08-18 ~19:00 UTC after the 08-17 rm -rf destroyed "
                    "19.46 GB; flags are absent from Bybit's public archive, so history is "
                    "unbackfillable and power accrues only at recorder speed "
                    f"(~{bars_per_day} bars/day/symbol)."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}", flush=True)
    # Research-memory duty: one row per construction, including (expected) underpowered nulls.
    for tr in TRIALS:
        verdict = tr.get("verdict", "")
        result = {"SCREEN-INTERESTING": "screening", "SCREEN-WEAK": "rejected"}.get(
            verdict, "screening")
        subprocess.run(
            [sys.executable, "scripts/research_memory.py", "log",
             "--category", "hypothesis", "--statement",
             f"{tr['name']}: bybit print-flag conditioning axis (R0484)",
             "--result", result, "--axis", "bybit_print_flags",
             "--metrics", json.dumps({k: tr.get(k) for k in
                                      ("verdict", "n", "ic", "n_eff") if k in tr}),
             "--lessons", f"verdict {verdict}; re-screen when powered "
                          f"(~{bars_per_day} bars/day/symbol accruing)"],
            cwd=ROOT, timeout=60, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
