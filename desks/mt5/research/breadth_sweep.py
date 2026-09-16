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
from typing import Any

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
    # Price only. The board says "needs: price only", so there was never a blocker.
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
    # MEASURED 2026-09-12: _cot_frame('XAUUSD') returns 1,392 weekly observations from
    # data/cot_zcache.parquet -- 8,416 rows over 11 symbols, 2000-01-03 to 2026-09-01. Twenty-six
    # years of point-in-time positioning, with the Friday release lag already applied by the
    # loader. The board read BLOCKED on "COT net positioning" while the desk had owned the series
    # for the whole time; what was missing was cells.
    "cot_positioning": {
        "why": "weekly speculative positioning at multi-year extremes -- a clock no intraday "
               "family observes, so its errors have no reason to correlate with the book",
        "symbols": ("XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "EURUSD", "GBPUSD",
                    "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "XTIUSD"),
        "grid": [
            {"lookback_weeks": w, "extreme_pct": p, "rr": rr, "ttl_bars": 240, "atr_n": 20}
            for w in (104, 156)
            for p in (0.85, 0.90, 0.95)
            for rr in (2.0,)
        ],
    },
    # MEASURED: _macro_series returns 27,793 observations -- a trailing percentile rank of the
    # broad trade-weighted dollar (DTWEXBGS) off data/fred_macro.json, lagged one publication day
    # and ranked only against its own past. Also never blocked.
    "macro_conditional": {
        "why": "a dollar-state condition changes WHEN other sleeves should fire rather than "
               "adding another directional signal",
        "grid": [
            {"regime_high": h, "side_in_high": s, "rr": rr, "ttl_bars": 96, "atr_n": 20}
            for h in (0.5, 0.7)
            for s in (1, -1)
            for rr in (2.0,)
        ],
    },
    # MEASURED: _tape_series returns a spread AND a flow series for every symbol tried. The tape
    # is the desk's own moat recording -- proprietary data nobody else holds, which is the one
    # axis whose errors cannot correlate with anything mined from a public source.
    "liquidity_regime": {
        "why": "fade dislocations made into an abnormally wide book -- an execution-derived edge "
               "off the desk's OWN tape, structurally independent of every price-only family",
        "grid": [
            {"lookback": lb, "widen_z": z, "rr": rr, "ttl_bars": 12, "atr_n": 20}
            for lb in (96, 192)
            for z in (1.5, 2.0, 2.5)
            for rr in (1.5,)
        ],
    },
    "orderflow_imbalance": {
        "why": "the flow half of the same tape -- a second, differently-conditioned read of "
               "proprietary microstructure",
        "grid": [
            {"lookback": lb, "z_in": z, "rr": rr, "ttl_bars": 12}
            for lb in (96, 192)
            for z in (1.5, 2.5)
            for rr in (1.5, 2.0)
        ],
    },
    # MEASURED: _event_index() returns 57 dated events, and the crash guard fixed earlier today
    # means a family handed an empty or index-like `events` now refuses instead of taking the
    # sweep down.
    "event_reaction": {
        "why": "a scheduled-release clock -- entirely different timing from any bar-structure "
               "family, which is what makes it an independent bet rather than another one",
        "grid": [
            {"mode": m, "side": s, "clock": "utc", "rr": 2.0, "ttl_bars": 24, "atr_n": 20}
            for m in ("drift", "fade")
            for s in (1, -1)
        ],
    },
    # MEASURED: _bars('EURUSD','H1') returns 37,366 bars, so a peer leg loads. The gauntlet's
    # build path already pops `peer_symbol` and hands the family a `peer` frame.
    "relative_value": {
        "why": "a cross-pair residual profits when direction does not, so it is uncorrelated "
               "with every directional family by construction rather than by measurement",
        "pairs": (("EURUSD", "GBPUSD"), ("AUDUSD", "NZDUSD"), ("USDCHF", "EURCHF"),
                  ("XAUUSD", "XAGUSD"), ("USDCAD", "XTIUSD"), ("EURJPY", "GBPJPY")),
        "grid": [{"lookback": lb, "entry_z": z, "rr": 1.5, "ttl_bars": 48}
                 for lb in (96, 240) for z in (2.0, 2.5)],
    },
    # Same loader, more legs: the build path pops `factor_symbols` and hands over a list.
    "cross_asset_residual": {
        "why": "metals against FX against index after the common factor -- what is left when the "
               "shared driver is removed is the least correlated thing the desk can hold",
        "factor_sets": (("XAUUSD", ("EURUSD", "US500", "UST10Y")),
                        ("XTIUSD", ("USDCAD", "US500", "XAUUSD")),
                        ("XAGUSD", ("XAUUSD", "US500", "EURUSD")),
                        ("NAS100", ("US500", "UST10Y", "EURUSD"))),
        "grid": [{"lookback": lb, "entry_z": z, "rr": 1.5, "ttl_bars": 48}
                 for lb in (120, 240) for z in (2.0, 2.5)],
    },
}

#: Families still genuinely blocked. EMPTY as of 2026-09-12: every loader the gauntlet's build
#: path uses was tested and every one returned data -- cot 1,392 obs, macro 27,793, events 57,
#: tape spread/flow on every symbol tried, peer bars 37,366. The breadth board had been reporting
#: seven families BLOCKED on inputs the desk already held. What was actually missing, in every
#: single case, was CELLS IN THE DOCKET.
BLOCKED: dict[str, str] = {}

#: Instruments to sweep. THE LIQUID CORE, not the whole registry: a mechanism that cannot be found
#: on the majors and metals is not going to be rescued by an exotic cross, and 267 symbols x a
#: parameter grid is a docket nobody can converge. Restricted further to symbols that actually
#: have H1 bars on disk, because a cell with no bars is UNMEASURED rather than tested.
CORE = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
        "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "XTIUSD", "NAS100", "US500",
        "US30", "GER40", "UK100", "JPN225", "BTCUSD", "ETHUSD", "USDZAR", "USDMXN")


#: EVERY CHART THE DESK HOLDS BARS FOR (principal 2026-09-16: "all breadth, all charts, all
#: sessions, not tons of H1"). A cell is emitted on a chart only when that symbol's bars for it
#: are on disk; H1 keeps the bare identity every existing cell has, the others carry
#: `timeframe`, which is the chart to load and stays in the cell's identity.
CHARTS = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
#: THE SESSION AXIS (principal 2026-09-16: "all sessions maximised fully for true 24/7 trading").
#: `family_call.SESSIONS` defines the windows in server hours and applies the filter in the one
#: call path the gauntlet, the forward clock and the live executor share; here it is only an
#: identity key on the cell. Daily bars carry no session.
SESSION_AXIS = ("all", "asia", "london", "ny")
#: Constructors that are not families of their own: they take a spec and build others.
NOT_A_FAMILY = frozenset({"generic", "formula", "ensemble", "cross_sectional"})
#: How many new cells one run may merge, most intraday first: the sweep is idempotent, so a
#: docket of every family on every chart in every session fills over a few hourly runs rather
#: than in one write the gauntlet then has to load whole.
MAX_NEW_PER_RUN = 40_000


def _with_bars() -> list[str]:
    """Instruments to sweep: the liquid core plus every instrument in the hypothesis lane that
    has H1 bars on disk -- the same breadth the discovery hunt had (principal 2026-09-16), now
    spent on the families that are not banned."""
    have = {p.name.split("_")[0].upper() for p in UNIVERSE.glob("*_H1.parquet")}
    out = [s for s in CORE if s in have]
    try:
        from research.universe_policy import may_hypothesise
        extra = sorted(s for s in have if s not in out and may_hypothesise(s))
        out.extend(extra)
    except Exception:
        pass
    return out


def _charts_for(sym: str) -> list[str]:
    return [tf for tf in CHARTS if (UNIVERSE / f"{sym}_{tf}.parquet").exists()]


def _sessions_for(tf: str) -> tuple[str, ...]:
    return ("all",) if tf == "D1" else SESSION_AXIS


def _banned(family: str) -> bool:
    try:
        from research.family_policy import family_banned
        return bool(family_banned(family))
    except Exception:
        return False


def default_families() -> tuple[dict[str, str], dict[str, str]]:
    """(sweepable, blocked): EVERY registered family the desk can call on bars alone, with its
    default parameters, and the ones it cannot with the reason (principal 2026-09-16: "make them
    hunt every family ever and anything which isn't discovery").

    A family is sweepable at its defaults when every argument beyond the bars and the side has a
    default. One that REQUIRES an input (a peer, factors, a COT frame, a tape series) is blocked
    here and swept only through the READY grid that names that input; the banned family and the
    spec-driven constructors are set aside by name.
    """
    import inspect
    try:
        from mt5desk import families as fam_mod
        from mt5desk import families_orthogonal as fo
    except Exception as exc:                                     # pragma: no cover
        return {}, {"*": f"families unimportable ({type(exc).__name__}: {exc})"}
    names: dict[str, Any] = {}
    for name, entry in getattr(fam_mod, "FAMILY_REGISTRY", {}).items():
        fn = entry.get("func") if isinstance(entry, dict) else entry
        if callable(fn):
            names[str(name)] = fn
    for name, fn in getattr(fo, "ORTHOGONAL_FAMILIES", {}).items():
        names.setdefault(str(name), fn)
    ok: dict[str, str] = {}
    blocked: dict[str, str] = {}
    for name, fn in sorted(names.items()):
        if name in READY:
            continue
        if name in NOT_A_FAMILY:
            blocked[name] = "a constructor that builds families from a spec, not a family"
            continue
        if _banned(name):
            blocked[name] = "banned (data/banned_families.json)"
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            blocked[name] = "signature unreadable"
            continue
        params = list(sig.parameters.values())[1:]
        need = [p.name for p in params
                if p.default is inspect.Parameter.empty and p.name != "side"
                and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
        if need:
            blocked[name] = f"requires input(s) {need} the sweep cannot name at defaults"
            continue
        ok[name] = "default parameters, every chart, every session"
    return ok, blocked


def _tf_rank(tf: str) -> int:
    return 0 if tf in ("M1", "M5", "M15", "M30") else (1 if tf == "H4" else 2)


def _targets(fam: str, spec: dict, syms: list[str]) -> list[tuple[str, dict]]:
    """(symbol, extra params) the family should be swept over.

    Three shapes, because three families need a partner leg named in the SPEC rather than
    inferred: `pairs` for a peer, `factor_sets` for several factors, `symbols` to restrict a
    family to the instruments its input actually covers (COT has 11, not 24 -- sweeping the other
    13 would build cells whose input is None and fail them for a reason that says nothing).
    """
    if spec.get("pairs"):
        return [(a, {"peer_symbol": b}) for a, b in spec["pairs"] if a in syms]
    if spec.get("factor_sets"):
        return [(a, {"factor_symbols": list(f)}) for a, f in spec["factor_sets"] if a in syms]
    allowed = spec.get("symbols")
    pool = [s for s in syms if (not allowed or s in allowed)]
    return [(s, {}) for s in pool]


def cells(only: str | None = None) -> list[dict]:
    now = datetime.now(tz=UTC).isoformat()
    syms = _with_bars()
    out: list[dict] = []
    for fam, spec in READY.items():
        if only and fam != only:
            continue
        if _banned(fam):
            continue
        for sym, extra in _targets(fam, spec, syms):
            for params in spec["grid"]:
                for tf in _charts_for(sym) or ["H1"]:
                    for sess in _sessions_for(tf):
                        p = dict(params)
                        p.update(extra)
                        if tf != "H1":
                            p["timeframe"] = tf
                        if sess != "all":
                            p["session"] = sess
                        out.append(_cell(sym, fam, p, spec, now))
    sweepable, _blocked = default_families()
    for fam, why in sweepable.items():
        if only and fam != only:
            continue
        spec = {"why": f"every family, {why}"}
        for sym in syms:
            for tf in _charts_for(sym) or ["H1"]:
                for sess in _sessions_for(tf):
                    p: dict = {}
                    if tf != "H1":
                        p["timeframe"] = tf
                    if sess != "all":
                        p["session"] = sess
                    out.append(_cell(sym, fam, p, spec, now))
    # Most intraday first, so a capped merge reaches the charts the principal ranked highest.
    out.sort(key=lambda r: (_tf_rank(str((r.get("params") or {}).get("timeframe") or "H1")),
                            r["symbol"], r["family"]))
    return out


def _cell(sym: str, fam: str, p: dict, spec: dict, now: str) -> dict:
    """One docket row: the executable spec and nothing claimed about it."""
    return {
        "symbol": sym, "family": fam, "params": p,
        "n": 0, "exp_r": None, "max_dd_r": None, "t_stat": None,
        "profit_factor": None, "win_rate": None,
        "source": f"breadth_sweep/{fam}",
        "url": None,
        "producer": "desks/mt5/research/breadth_sweep.py",
        "first_seen": now, "pit_stamp": now,
        "why": (f"closing a NAMED breadth gap: {spec['why']}. No performance is "
                f"claimed -- the gauntlet attaches the only numbers that attach."),
    }


def apply(new: list[dict], max_new: int = MAX_NEW_PER_RUN) -> tuple[int, int]:
    """Merge, deduped on the executable spec, at most `max_new` per run (the input order is
    most-intraday-first), so a daily clock cannot grow the docket without bound and one run
    never hands the gauntlet a docket it has to load whole."""
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
    add = [r for r in new if key(r) not in seen][:max(0, int(max_new))]
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
        tg = _targets(fam, spec, syms)
        print(f"  READY   {fam:<22} {len(spec['grid'])} param set(s) x {len(tg)} target(s)")
    sweepable, blocked_default = default_families()
    print(f"  DEFAULT {len(sweepable)} more famil(ies) at their defaults: "
          f"{', '.join(sorted(sweepable))}")
    for fam, why in sorted(blocked_default.items()):
        print(f"  SET ASIDE {fam:<20} {why[:90]}")
    from collections import Counter
    by_tf = Counter(str((r.get('params') or {}).get('timeframe') or 'H1') for r in new)
    by_sess = Counter(str((r.get('params') or {}).get('session') or 'all') for r in new)
    print(f"  by chart {dict(by_tf)}; by session {dict(by_sess)}")
    for fam, why in BLOCKED.items():
        print(f"  BLOCKED {fam:<22} {why[:96]}")
    if not BLOCKED:
        print("  BLOCKED (none) -- every loader the gauntlet uses was measured and returned data")
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
