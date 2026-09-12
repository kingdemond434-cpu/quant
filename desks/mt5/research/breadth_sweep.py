"""CLOSE THE NAMED BREADTH GAPS BY GENERATING THEIR CELLS.

The breadth board lists seven families the book does not hold and marks each REACHABLE with the
input it needs. REACHABLE means the constructor already exists on this tree and the family has
simply never been swept -- so the gap is not research, it is a docket that was never written.

WHY THIS IS THE HIGHEST-VALUE SWEEP ON THE DESK. Measured 2026-09-12: 15 funded sleeves behave as
~7.9 INDEPENDENT bets (n_eff covariance), the largest mechanism is 60% of the book, and the growth
curve stops paying above 22.5% heat BECAUSE of that concentration. The ceiling is set by n_eff,
not by sleeve count -- so another `discovered` cell moves nothing and a genuinely orthogonal
family raises the ceiling itself. These seven are the only named, costed routes to that.

AND IT IS FREE TO TRY. `gate_policy` charges a FIXED 597 trials with a FIXED variance-of-Sharpes,
so adding several hundred cells raises no other candidate's bar (pinned by
test_the_trial_charge_is_fixed_and_never_taxes_breadth). Under the old batch-scaled charge this
sweep would have made every existing candidate harder to certify, which is precisely why it was
never run.

WHAT IS SWEPT AND WHAT IS NOT. Only families whose inputs the desk ALREADY HOLDS are emitted. A
family blocked on an input it does not have is listed in `BLOCKED` with the reason, because a cell
built without its input is not a test of the mechanism -- it is a test of the fallback, and it
would fail for a reason that says nothing about the hypothesis. That distinction is the whole
difference between a gap being measured and a gap being papered over.

NO PERFORMANCE IS CLAIMED on any emitted row: n=0 and every metric null. The gauntlet attaches the
only numbers that will ever attach.

    python desks/mt5/research/breadth_sweep.py [--apply] [--family vol_transition]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
UNIVERSE = DESK / "data" / "universe"

#: FAMILIES WHOSE INPUTS THE DESK ALREADY HOLDS, with the grid each is swept over.
#:
#: The grids are deliberately coarse. A wide grid is not a better search -- it is the same search
#: with more ways to fit, and the deflated-Sharpe bar does not care how hard you looked. Each axis
#: here is one the family's own docstring names as mechanically meaningful, not every knob it has.
READY: dict[str, dict] = {
    # Price only. The board says "needs: price only", so there is no blocker whatsoever.
    "vol_transition": {
        "why": "the moment realised vol expands out of compression -- fires when breakouts stall, "
               "which is the failure regime of the family that dominates the book",
        "grid": [
            {"fast": f, "slow": s, "ratio_in": r, "rr": rr, "ttl_bars": 24, "atr_n": 20}
            for f, s in ((12, 96), (24, 192))
            for r in (1.4, 1.8)
            for rr in (1.5, 2.5)
        ],
    },
}

#: FAMILIES STILL BLOCKED, with the input each is waiting on. Listed rather than silently skipped:
#: an absent family is a gap the desk should be able to SEE, and the reason is the work item.
BLOCKED: dict[str, str] = {
    "liquidity_regime": "a spread series from the tick tape. fetch_dukascopy.py is ported and its "
                        "offline test passes, but outbound HTTPS to datafeed.dukascopy.com is "
                        "refused on this box (URLError), so no tick history has landed yet.",
    "event_reaction": "dated events carrying the moment the market could know. "
                      "data/macro/event_ledger.jsonl holds 88 rows and is growing at ~25/pass "
                      "since the source expansion, so this unblocks on sample, not on code.",
    "macro_conditional": "a macro state series. 28 first-party feeds now cover 25 of 27 domains "
                         "(0.926), so the inputs exist; what is missing is the series assembled "
                         "into a per-bar state the family can condition on.",
    "cot_positioning": "COT net positioning. The CFTC feed was added to macro/sources.py; the "
                       "positioning series itself is not yet parsed out of it.",
    "relative_value": "a peer instrument on this cell's own chart -- needs the multi-symbol "
                      "loader, which the single-symbol build path does not have.",
    "cross_asset_residual": "2+ factor instruments on this cell's own chart. Same loader.",
}

#: Instruments to sweep. THE LIQUID CORE, not the whole registry: a mechanism that cannot be found
#: on the majors and metals is not going to be rescued by an exotic cross, and 267 symbols x a
#: parameter grid is a docket nobody can converge. Restricted further to symbols that actually
#: have H1 bars on disk, because a cell with no bars is UNMEASURED rather than tested.
CORE = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
        "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "XTIUSD", "NAS100", "US500",
        "US30", "GER40", "UK100", "JPN225", "BTCUSD", "ETHUSD", "USDZAR", "USDMXN")


def _with_bars() -> list[str]:
    have = {p.name.split("_")[0].upper() for p in UNIVERSE.glob("*_H1.parquet")}
    return [s for s in CORE if s in have]


def cells(only: str | None = None) -> list[dict]:
    now = datetime.now(tz=UTC).isoformat()
    syms = _with_bars()
    out: list[dict] = []
    for fam, spec in READY.items():
        if only and fam != only:
            continue
        for sym in syms:
            for params in spec["grid"]:
                out.append({
                    "symbol": sym, "family": fam, "params": dict(params),
                    "n": 0, "exp_r": None, "max_dd_r": None, "t_stat": None,
                    "profit_factor": None, "win_rate": None,
                    "source": f"breadth_sweep/{fam}",
                    "url": None,
                    "producer": "desks/mt5/research/breadth_sweep.py",
                    "first_seen": now, "pit_stamp": now,
                    "why": (f"closing a NAMED breadth gap: {spec['why']}. No performance is "
                            f"claimed -- the gauntlet attaches the only numbers that attach."),
                })
    return out


def apply(new: list[dict]) -> tuple[int, int]:
    """Merge, deduped on the executable spec, so a daily clock cannot grow the
    docket without bound."""
    try:
        docket = json.loads(DOCKET.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        docket = []
    if not isinstance(docket, list):
        raise SystemExit(f"{DOCKET} is not a list; refusing to overwrite a docket I cannot read")

    def key(r: dict) -> str:
        return json.dumps([r.get("symbol"), r.get("family"), r.get("params") or {}],
                          sort_keys=True, default=str)

    seen = {key(r) for r in docket if isinstance(r, dict)}
    add = [r for r in new if key(r) not in seen]
    if add:
        docket.extend(add)
        tmp = DOCKET.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(docket), encoding="utf-8")
        tmp.replace(DOCKET)
    return len(add), len(docket)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--family", default=None, help="sweep one ready family only")
    a = ap.parse_args(argv)
    syms = _with_bars()
    new = cells(a.family)
    print(f"breadth sweep: {len(new)} cell(s) over {len(syms)} instrument(s) with H1 bars")
    for fam, spec in READY.items():
        if a.family and fam != a.family:
            continue
        print(f"  READY   {fam:<22} {len(spec['grid'])} param set(s) x {len(syms)} symbols")
    for fam, why in BLOCKED.items():
        print(f"  BLOCKED {fam:<22} {why[:96]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    added, total = apply(new)
    print(f"  merged {added} new cell(s); docket now {total} row(s)")
    if not added:
        print("  (all already present -- the sweep is idempotent on the executable spec)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
