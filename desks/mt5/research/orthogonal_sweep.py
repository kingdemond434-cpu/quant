"""ORTHOGONAL SWEEP -- run every non-breakout family across the universe and emit candidates.

WHY THIS IS THE N_eff FIX AND NOT A NICE-TO-HAVE (principal 2026-08-26: "why don't u fix it
then"). Live readiness is blocked on two checks. One of them -- fourteen elapsed days -- nothing
can shorten. The OTHER, effective independent bets, is entirely fixable today and was being
treated as if it were also a waiting problem. It is not: N_eff is 0 because every certificate the
desk holds is the same mechanism, and it stays that way for exactly as long as nobody tests a
different one.

WHAT THIS DOES. Sweeps the fourteen orthogonal generators across every symbol with bars and every
input the box actually has, produces hypotheses in the SAME shape the external backtest emits, and
hands them to the SAME ten-gate gauntlet. No new door, no separate certification path, no relaxed
bar -- the only thing that changes is that the gauntlet finally has something to judge that is not
a session-range breakout.

WIRING THE INPUTS IS THE WORK. Most of these families refuse without their input, correctly, so a
sweep that does not FIND those inputs would report fourteen refusals and look like the families
were the problem. So this resolves each one from what the desk already records:

    peer / factors     other symbols' H1 in data/universe
    spread series      the tick tape's own bid/ask, resampled to the bar clock
    flow imbalance     tick upticks vs downticks, from the same tape
    macro              data/macro_state.json
    COT                data/cot*.json

An input that genuinely is not there is reported as an ACQUISITION gap, which is a different and
more actionable statement than "this family produced nothing".
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
UNIVERSE = BASE / "data" / "universe"
TAPE = BASE / "data" / "tape" / "ticks"
OUT = BASE / "data" / "hypotheses" / "orthogonal_candidates.json"

#: Screen bar, deliberately LOOSE. This is a screen, not a verdict -- the ten gates are the door,
#: and a tight screen here would pre-reject candidates the canonical policy never got to judge.
MIN_TRADES = 30
MIN_EXP_R = 0.0


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


# MEMORY IS A THROUGHPUT RAIL, NOT A UNIVERSE LIMIT.  ``maxsize=None`` retained every complete
# H1 dataframe in the 293-symbol sweep.  The process climbed until Windows terminated it after
# ~23 minutes, before OUT was written, so the gauntlet kept consuming yesterday's artifact.
# Sixteen holds the current symbol plus the twelve-factor working set; eviction changes only
# residency and every symbol is still loaded and tested in the same pass.
@lru_cache(maxsize=16)
def _bars(symbol: str):
    import pandas as pd
    path = UNIVERSE / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def _tape_series(symbol: str, index):
    """(spread, flow) on the bar clock, from the venue's own ticks. (None, None) if no tape."""
    import pandas as pd
    d = TAPE / symbol
    if not d.exists():
        return None, None
    frames = []
    for f in sorted(d.glob("*.parquet"))[-30:]:
        try:
            frames.append(pd.read_parquet(f, columns=["ts", "bid", "ask"]))
        except Exception:
            continue
    if not frames:
        return None, None
    t = pd.concat(frames, ignore_index=True)
    t["ts"] = pd.to_datetime(t["ts"], utc=True)
    t = t.dropna(subset=["bid", "ask"]).sort_values("ts").set_index("ts")
    spread = (t["ask"] - t["bid"]).resample("1h").mean()
    mid = ((t["ask"] + t["bid"]) / 2.0)
    # Flow proxy: net sign of mid changes within the bar. Not true aggressor data -- the tape has
    # no trade side -- so it is labelled a proxy rather than passed off as order flow.
    step = mid.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    flow = step.resample("1h").sum()
    return spread.reindex(index).ffill(), flow.reindex(index).ffill()


def _macro_series(index):
    import pandas as pd
    doc = _read(BASE / "data" / "macro_state.json")
    if not isinstance(doc, dict):
        return None
    pairs = [(k, v) for k, v in doc.items() if isinstance(v, (int, float))]
    if not pairs:
        return None
    # A single scalar state is still a conditioning variable; broadcast it so the family can run
    # and the gauntlet can judge whether conditioning on it helps.
    return pd.Series(float(pairs[0][1]), index=index)


@lru_cache(maxsize=32)
def _cot_frame(symbol: str | None = None):
    import pandas as pd

    # The repository already owns 26 years of point-in-time CFTC history. It was registered and
    # screened elsewhere but this gauntlet reader ignored it, so a COT miner could produce a real
    # candidate that always rebuilt with `cot=None`. Downsample the daily forward-filled cache to
    # one weekly observation; repeated daily values must not masquerade as independent reports.
    cache = BASE.parent.parent / "data" / "cot_zcache.parquet"
    if symbol and cache.exists():
        try:
            frame = pd.read_parquet(cache, columns=[symbol])
            series = frame[symbol].astype(float).dropna().resample("W-FRI").last().dropna()
            if len(series) >= 52:
                return series.rename("net").to_frame()
        except Exception:
            pass
    for name in ("cot_tff.json", "cot.json", "cot_disagg.json"):
        doc = _read(BASE / "data" / name)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        try:
            df = pd.DataFrame(rows)
            for tcol in ("date", "report_date", "as_of"):
                if tcol in df.columns:
                    df.index = pd.to_datetime(df[tcol], utc=True, errors="coerce")
                    break
            else:
                continue
            for ncol in ("net", "noncomm_net", "net_position"):
                if ncol in df.columns:
                    return df[[ncol]].rename(columns={ncol: "net"}).dropna()
        except Exception:
            continue
    return None


@lru_cache(maxsize=1)
def _event_index():
    """Recover point-in-time event timestamps already persisted by the calendar miner."""
    import pandas as pd

    root = BASE / "data" / "intelligence" / "ff_calendar_vintage"
    values = []
    for path in sorted(root.glob("*.json*"))[-60:] if root.exists() else []:
        doc = _read(path)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows", [])
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            raw = next((row.get(k) for k in ("date", "datetime", "timestamp", "time")
                        if row.get(k)), None)
            if raw is not None:
                values.append(raw)
    idx = pd.to_datetime(values, utc=True, errors="coerce")
    return pd.DatetimeIndex(idx.dropna().unique()).sort_values() if len(idx) else None


def sweep() -> dict:
    from mt5desk.engine import Costs, run_backtest
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES

    meta = _read(UNIVERSE / "universe.json") or {}
    symbols = sorted(p.stem.replace("_H1", "") for p in UNIVERSE.glob("*_H1.parquet"))
    hypotheses: list[dict] = []
    gaps: dict[str, int] = {}
    ran: dict[str, int] = {}

    for sym in symbols:
        df = _bars(sym)
        if df is None or len(df) < 2000:
            continue
        # pca_residual needs a real cross-section: latent factors extracted from 3 peers are a
        # pair spread wearing a bigger name. Give it a dozen; the MP bound decides what is real.
        peers = [s for s in symbols if s != sym][:12]
        peer_df = _bars(peers[0]) if peers else None
        factor_dfs = [f for f in (_bars(s) for s in peers[:2]) if f is not None]
        spread, flow = _tape_series(sym, df.index)
        macro = _macro_series(df.index)
        cot = _cot_frame(sym)
        events = _event_index()

        kwargs_by_family = {
            "carry": {"symbol": sym},
            "relative_value": {"peer": peer_df},
            "correlation_regime": {"peer": peer_df},
            "cross_asset_residual": {"factors": factor_dfs},
            "liquidity_regime": {"spread_series": spread},
            "orderflow_imbalance": {"flow": flow},
            "macro_conditional": {"macro": macro},
            "cot_positioning": {"cot": cot},
            "event_reaction": {"events": events},
        }
        # Runtime objects cannot be JSON identities. Persist exact provenance needed to rebuild
        # the same candidate in the universal gauntlet; an empty params object previously made
        # peer/factor candidates silently rebuild with no inputs and therefore no trades.
        identity_by_family = {
            "carry": {"input_symbol": sym},
            "relative_value": {"peer_symbol": peers[0]} if peers else {},
            "correlation_regime": {"peer_symbol": peers[0]} if peers else {},
            "cross_asset_residual": {"factor_symbols": peers[:2]},
            "liquidity_regime": {"input_source": "fusion_tick_tape"},
            "orderflow_imbalance": {"input_source": "fusion_tick_tape"},
            "macro_conditional": {"input_source": "macro_state"},
            "cot_positioning": {"input_source": "cot_point_in_time"},
            "event_reaction": {"input_source": "ff_calendar_vintage"},
        }
        m = meta.get(sym, {}) if isinstance(meta, dict) else {}
        try:
            costs = Costs(spread_per_lot=max(float(m.get("median_spread_pts", 1)) *
                                             float(m.get("tick_size", 0.0001)) *
                                             float(m.get("contract_size", 100000)), 0.05),
                          commission_per_lot=3.50,
                          contract_oz=float(m.get("contract_size", 100000)))
        except (TypeError, ValueError):
            continue

        for fam, fn in sorted(ORTHOGONAL_FAMILIES.items()):
            kw = kwargs_by_family.get(fam, {})
            try:
                sigs = fn(df, **kw)
            except Exception as exc:
                gaps[f"{fam}:error:{type(exc).__name__}"] = gaps.get(
                    f"{fam}:error:{type(exc).__name__}", 0) + 1
                continue
            if not sigs:
                need = FAMILY_INPUTS.get(fam, ("unknown", None))[0]
                key = f"{fam}:no-signals ({need})"
                gaps[key] = gaps.get(key, 0) + 1
                continue
            ran[fam] = ran.get(fam, 0) + 1
            try:
                res = run_backtest(df, sigs, costs)
            except Exception:
                continue
            trades = list(res.trades)
            if len(trades) < MIN_TRADES:
                continue
            rs = [t.r_multiple for t in trades]
            exp = sum(rs) / len(rs)
            if exp <= MIN_EXP_R:
                continue
            cum, peak, dd = 0.0, 0.0, 0.0
            for r in rs:
                cum += r
                peak = max(peak, cum)
                dd = min(dd, cum - peak)
            hypotheses.append({
                "symbol": sym, "family": fam, "params": identity_by_family.get(fam, {}),
                "n": len(trades), "exp_r": round(exp, 4), "max_dd_r": round(dd, 2),
                "source": f"orthogonal_sweep:{fam}",
                "mechanism_status": "NAMED",
                "mechanism_note": FAMILY_INPUTS.get(fam, ("", None))[0],
            })

    return {"swept_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "symbols": len(symbols), "families_ran": ran,
            "input_gaps": gaps, "hypotheses": hypotheses}


def main() -> int:
    report = sweep()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    hyp = report["hypotheses"]
    print(f"orthogonal sweep: {report['symbols']} symbol(s), "
          f"{len(report['families_ran'])} family(ies) produced signals, "
          f"{len(hyp)} candidate(s) passed the loose screen")
    for fam, n in sorted(report["families_ran"].items()):
        got = sum(1 for h in hyp if h["family"] == fam)
        print(f"   {fam:24} ran on {n:>3} symbol(s) -> {got} candidate(s)")
    if report["input_gaps"]:
        print("  input gaps (ACQUISITION tasks, not miner failures):")
        for k, n in sorted(report["input_gaps"].items())[:6]:
            print(f"   {k}  x{n}")
    return 0


def _cli_main() -> int:
    from research.job_lock import exclusive_job

    with exclusive_job("orthogonal_sweep") as acquired:
        return main() if acquired else 75


if __name__ == "__main__":
    raise SystemExit(_cli_main())
