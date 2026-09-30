"""LATENT ACTOR POPULATIONS -- who is on the other side, estimated from the tape the desk owns.

THE GAP THE LEDGER NAMED (Tier-1 B15): *"positioning families read the public positioning data;
no explicit latent-actor model of who is on the other side."* The `cot_*` families read what the
CFTC published about last Tuesday, twelve days late and only for the instruments that report. That
is a MEASUREMENT of one actor class, not a model of the population that is actually pressing on a
price right now -- and it says nothing at all about the majority of this desk's universe.

THE POPULATIONS, and each one's pressure is an observable of the price series itself, so the model
exists for every instrument with bars rather than for the handful with a positioning report:

    trend_follower     managed-futures style: the sign of the 20/60/120-bar trend, weighted by
                       its own |z|. When it is stretched the population is ALREADY long and the
                       marginal buyer is gone -- pressure and CROWDING are reported separately
                       for exactly that reason.
    vol_control        target-vol and risk-parity books hold size ~ target / realised vol. Their
                       pressure is the CHANGE in that ratio: rising realised vol is mechanical
                       selling into weakness regardless of anyone's view.
    dealer_gamma       a PROXY, named as one: the serial correlation of returns at the hedging
                       horizon. Negative autocorrelation is the pinning a long-gamma dealer book
                       produces; positive is the amplification a short-gamma book produces. The
                       desk has no options chain, so this is an inference from behaviour and it
                       is stamped PROXY in every row.
    rebalancer         calendar flow: the last three sessions of a month and of a quarter,
                       measured against that instrument's own other days, so a "month-end effect"
                       that is not there on this symbol reads zero instead of folklore.
    carry_chaser       the venue's own swap rates: a positive carry differential pays a
                       population to hold the position, and that population unwinds together.
                       UNMEASURED where the registry carries no swap for the symbol.

CROWDING IS THE SECOND NUMBER, and it is the one that answers the question the row asks. A
population's PRESSURE says which way it is pushing; its CROWDING says how much of its capacity is
already spent. `crowded_against` names the population whose position is opposite the desk's own
live side -- the counterparty most likely to be forced -- and `crowded_with` the population the
desk is standing beside, which is the more dangerous place to be.

WHAT IT CHANGES. Rows are published onto the state vector's `conditioning` block through
`state_vector_build.world_conditioning`, which is INFORMATION AND NEVER AUTHORITY by that
module's own law: the allocator may condition on them, and a dimension the state-admission
gauntlet has not judged may not condition capital. Nothing here sizes, vetoes or refuses
anything, and the sealed judge is not read or touched.

    python desks/mt5/research/actor_pressure.py --once --budget-s 300
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
UNIVERSE_JSON = UNI / "universe.json"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "ACTOR_PRESSURE.json"

BARS = 6_000              # ~8 months of H1: enough for a quarter-end sample and three trends
MIN_BARS = 400
TREND_SPANS = (20, 60, 120)
VOL_WIN = 120
ACTORS = ("trend_follower", "vol_control", "dealer_gamma", "rebalancer", "carry_chaser")


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _bars(symbol: str) -> Any:
    try:
        import pandas as pd
    except ImportError:
        return None
    p = UNI / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p).tail(BARS)
    except (OSError, ValueError):
        return None
    return df if "close" in df.columns and len(df) >= MIN_BARS else None


def _clip(x: float) -> float:
    return float(max(-1.0, min(1.0, x)))


def _trend_follower(close: Any) -> dict[str, Any]:
    import numpy as np
    c = np.asarray(close, dtype=float)
    r = np.diff(np.log(np.maximum(c, 1e-12)))
    sd = float(np.std(r[-VOL_WIN:], ddof=1)) if len(r) > VOL_WIN else float(np.std(r, ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        return {"status": "UNMEASURED", "why": "zero realised volatility"}
    zs: list[float] = []
    for span in TREND_SPANS:
        if len(c) <= span:
            continue
        move = math.log(max(c[-1], 1e-12)) - math.log(max(c[-1 - span], 1e-12))
        zs.append(move / (sd * math.sqrt(span)))
    if not zs:
        return {"status": "UNMEASURED", "why": "fewer bars than the shortest trend span"}
    mean_z = sum(zs) / len(zs)
    agree = sum(1 for z in zs if (z > 0) == (mean_z > 0)) / len(zs)
    return {"status": "MEASURED", "pressure": _clip(math.tanh(mean_z)),
            "crowding": round(min(abs(mean_z) / 2.0, 1.0) * agree, 4),
            "spans": list(TREND_SPANS), "z": [round(z, 4) for z in zs],
            "basis": "sign and |z| of the 20/60/120-bar move in units of its own vol"}


def _vol_control(close: Any) -> dict[str, Any]:
    import numpy as np
    c = np.asarray(close, dtype=float)
    r = np.diff(np.log(np.maximum(c, 1e-12)))
    if len(r) < 2 * VOL_WIN:
        return {"status": "UNMEASURED", "why": f"fewer than {2 * VOL_WIN} returns"}
    now = float(np.std(r[-VOL_WIN:], ddof=1))
    prev = float(np.std(r[-2 * VOL_WIN:-VOL_WIN], ddof=1))
    if not (math.isfinite(now) and math.isfinite(prev)) or prev <= 0 or now <= 0:
        return {"status": "UNMEASURED", "why": "a volatility window is degenerate"}
    # Size ~ target/vol, so the flow is the CHANGE in 1/vol: vol up is mechanical selling.
    d_size = (prev / now) - 1.0
    return {"status": "MEASURED", "pressure": _clip(math.tanh(2.0 * d_size)),
            "crowding": round(min(abs(d_size), 1.0), 4),
            "vol_now": round(now, 8), "vol_prev": round(prev, 8),
            "basis": "change in target-vol size (prev_vol/now_vol - 1) over two 120-bar windows"}


def _dealer_gamma(close: Any) -> dict[str, Any]:
    import numpy as np
    c = np.asarray(close, dtype=float)
    r = np.diff(np.log(np.maximum(c, 1e-12)))
    r = r[-VOL_WIN * 4:]
    if len(r) < 200:
        return {"status": "UNMEASURED", "why": "fewer than 200 returns at the hedging horizon"}
    a, b = r[:-1], r[1:]
    sa, sb = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
    if sa <= 0 or sb <= 0:
        return {"status": "UNMEASURED", "why": "degenerate return series"}
    rho = float(np.corrcoef(a, b)[0, 1])
    if not math.isfinite(rho):
        return {"status": "UNMEASURED", "why": "autocorrelation undefined"}
    se = 1.0 / math.sqrt(len(a))
    # rho < 0 is pinning (a long-gamma dealer book sells rallies); rho > 0 is amplification.
    return {"status": "PROXY", "pressure": _clip(-rho / max(2.0 * se, 1e-9) / 3.0),
            "crowding": round(min(abs(rho) / max(2.0 * se, 1e-9) / 3.0, 1.0), 4),
            "rho": round(rho, 5), "se": round(se, 5), "n": len(a),
            "sign_reading": ("PINNING (long gamma)" if rho < 0 else "AMPLIFYING (short gamma)"),
            "basis": ("serial correlation of hourly returns as a behavioural proxy; this desk "
                      "holds no options chain, so the row is a PROXY and never a measurement")}


def _rebalancer(df: Any) -> dict[str, Any]:
    import numpy as np
    import pandas as pd
    idx = None
    for col in ("time", "date", "datetime"):
        if col in df.columns:
            idx = pd.to_datetime(df[col], utc=True, errors="coerce")
            break
    if idx is None:
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
    c = pd.Series(np.asarray(df["close"], dtype=float))
    r = np.log(c).diff()
    days = pd.Series(idx).dt.normalize()
    if days.isna().all():
        return {"status": "UNMEASURED", "why": "no usable timestamp column"}
    month_end = pd.Series(idx).dt.days_in_month - pd.Series(idx).dt.day <= 2
    win = np.asarray(r[month_end.to_numpy()].dropna(), dtype=float)
    rest = np.asarray(r[(~month_end).to_numpy()].dropna(), dtype=float)
    if len(win) < 30 or len(rest) < 100:
        return {"status": "UNMEASURED",
                "why": f"month-end sample too small (n={len(win)} vs {len(rest)})"}
    diff = float(np.mean(win) - np.mean(rest))
    se = math.sqrt(float(np.var(win, ddof=1)) / len(win) + float(np.var(rest, ddof=1)) / len(rest))
    t = diff / se if se > 0 else 0.0
    now_is_window = bool(month_end.to_numpy()[-1])
    return {"status": "MEASURED",
            "pressure": (_clip(math.tanh(t / 2.0)) if now_is_window else 0.0),
            "crowding": round(min(abs(t) / 4.0, 1.0), 4) if now_is_window else 0.0,
            "t": round(t, 3), "n_window": len(win), "n_rest": len(rest),
            "in_window_now": now_is_window,
            "basis": ("mean hourly return in the last three sessions of a month against every "
                      "other session on this symbol; zero outside the window by construction")}


def _carry_chaser(symbol: str, meta: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    row = meta.get(symbol) if isinstance(meta, dict) else None
    if not isinstance(row, dict):
        return {"status": "UNMEASURED", "why": "no registry row for this symbol"}
    sl, ss = row.get("swap_long"), row.get("swap_short")
    try:
        long_s, short_s = float(sl), float(ss)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {"status": "UNMEASURED", "why": "registry row carries no swap pair"}
    edge = long_s - short_s
    if not math.isfinite(edge) or edge == 0.0:
        return {"status": "UNMEASURED", "why": "swap differential is zero or non-finite"}
    # The carry population is paid to hold the financed side; it crowds when the trend agrees.
    p = _clip(math.tanh(edge / 5.0))
    tp = float(trend.get("pressure") or 0.0) if trend.get("status") == "MEASURED" else 0.0
    return {"status": "MEASURED", "pressure": p,
            "crowding": round(min(abs(p) * (0.5 + 0.5 * (1.0 if p * tp > 0 else 0.0)), 1.0), 4),
            "swap_long": long_s, "swap_short": short_s, "differential": round(edge, 4),
            "basis": "the venue's own swap pair: the financed side is the side a carry book holds"}


def _desk_side(symbol: str) -> str | None:
    doc = _read(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    sides: set[str] = set()
    for r in rows or []:
        if not isinstance(r, dict) or str(r.get("symbol") or "").upper() != symbol.upper():
            continue
        if str(r.get("status") or r.get("state") or "").upper() not in ("LIVE", "STANDBY", ""):
            continue
        side = str(r.get("side") or r.get("direction") or "").upper()
        if side in ("LONG", "SHORT", "BUY", "SELL"):
            sides.add("LONG" if side in ("LONG", "BUY") else "SHORT")
    return sides.pop() if len(sides) == 1 else None


def judge_symbol(symbol: str, meta: dict[str, Any]) -> dict[str, Any]:
    df = _bars(symbol)
    if df is None:
        return {"symbol": symbol, "status": "UNMEASURED",
                "why": f"no usable H1 parquet with >= {MIN_BARS} bars"}
    close = df["close"]
    actors: dict[str, dict[str, Any]] = {}
    actors["trend_follower"] = _trend_follower(close)
    actors["vol_control"] = _vol_control(close)
    actors["dealer_gamma"] = _dealer_gamma(close)
    actors["rebalancer"] = _rebalancer(df)
    actors["carry_chaser"] = _carry_chaser(symbol, meta, actors["trend_follower"])
    live = {k: v for k, v in actors.items() if v.get("status") in ("MEASURED", "PROXY")}
    net = sum(float(v.get("pressure") or 0.0) for v in live.values())
    side = _desk_side(symbol)
    with_side: list[str] = []
    against: list[str] = []
    if side is not None:
        want = 1.0 if side == "LONG" else -1.0
        for name, v in live.items():
            p = float(v.get("pressure") or 0.0)
            if p == 0.0:
                continue
            (with_side if p * want > 0 else against).append(name)
    dominant = max(live.items(), key=lambda kv: abs(float(kv[1].get("pressure") or 0.0)),
                   default=(None, {}))[0] if live else None
    return {
        "symbol": symbol, "status": "MEASURED" if live else "UNMEASURED",
        "n_actors": len(live), "actors": actors,
        "net_pressure": round(_clip(net / max(len(live), 1)), 6),
        "dominant_actor": dominant,
        "desk_side": side,
        "crowded_with": sorted(with_side), "crowded_against": sorted(against),
        "bars": len(df),
    }


def book_symbols(limit: int = 0) -> list[str]:
    """The instruments the book actually trades, else every symbol with H1 bars."""
    syms: list[str] = []
    doc = _read(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    for r in rows or []:
        if isinstance(r, dict) and r.get("symbol"):
            s = str(r["symbol"])
            if s not in syms:
                syms.append(s)
    if not syms:
        syms = sorted(p.name[: -len("_H1.parquet")] for p in UNI.glob("*_H1.parquet"))
    return syms[:limit] if limit > 0 else syms


def _meta() -> dict[str, Any]:
    doc = _read(UNIVERSE_JSON)
    if isinstance(doc, dict):
        rows = doc.get("symbols") if isinstance(doc.get("symbols"), (dict, list)) else doc
        if isinstance(rows, dict):
            return {str(k): v for k, v in rows.items() if isinstance(v, dict)}
        if isinstance(rows, list):
            return {str(r.get("symbol") or r.get("name")): r for r in rows
                    if isinstance(r, dict) and (r.get("symbol") or r.get("name"))}
    return {}


def hints_for(symbols: list[str]) -> dict[str, list[dict[str, Any]]]:
    """THE CONSUMER'S DOOR. `state_vector_build.world_conditioning` calls this and merges the
    rows onto the vector's conditioning block -- information, never authority. An absent or
    unreadable artifact returns {} and the vector is exactly what it was."""
    doc = _read(OUT)
    if not isinstance(doc, dict):
        return {}
    by_symbol = doc.get("by_symbol")
    if not isinstance(by_symbol, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for sym in symbols:
        row = by_symbol.get(sym)
        if not isinstance(row, dict) or row.get("status") != "MEASURED":
            continue
        rows: list[dict[str, Any]] = []
        for name, v in (row.get("actors") or {}).items():
            if not isinstance(v, dict) or v.get("status") not in ("MEASURED", "PROXY"):
                continue
            rows.append({"node": f"actor:{name}", "source": "actor_pressure",
                         "pressure": v.get("pressure"), "crowding": v.get("crowding"),
                         "proxy": v.get("status") == "PROXY",
                         "weight": round(abs(float(v.get("pressure") or 0.0)), 6),
                         "stale": False, "basis": v.get("basis")})
        if rows:
            rows.append({"node": "actor:net", "source": "actor_pressure",
                         "pressure": row.get("net_pressure"),
                         "dominant": row.get("dominant_actor"),
                         "crowded_with": row.get("crowded_with"),
                         "crowded_against": row.get("crowded_against"),
                         "weight": abs(float(row.get("net_pressure") or 0.0)), "stale": False})
            out[sym] = rows
    return out


def build(budget_s: float = 300.0, symbols: list[str] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    meta = _meta()
    syms = symbols if symbols is not None else book_symbols()
    by_symbol: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []
    for s in syms:
        if time.monotonic() - started > budget_s:
            skipped.append(s)
            continue
        try:
            by_symbol[s] = judge_symbol(s, meta)
        except Exception as exc:                                # a bad symbol never stops a pass
            by_symbol[s] = {"symbol": s, "status": "UNMEASURED",
                            "why": f"{type(exc).__name__}: {exc}"}
    per_actor: dict[str, dict[str, int]] = {a: {} for a in ACTORS}
    for row in by_symbol.values():
        for name, v in (row.get("actors") or {}).items():
            st = str((v or {}).get("status"))
            per_actor.setdefault(name, {})[st] = per_actor.setdefault(name, {}).get(st, 0) + 1
    measured = [r for r in by_symbol.values() if r.get("status") == "MEASURED"]
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "OK" if measured else "UNMEASURED",
        "n_symbols": len(by_symbol), "n_measured": len(measured), "n_skipped": len(skipped),
        "skipped_for_budget": skipped[:20],
        "actors": list(ACTORS), "per_actor_status": per_actor,
        "by_symbol": by_symbol,
        "consumers": [
            "desks/mt5/research/state_vector_build.py world_conditioning -> hints_for(book): "
            "actor rows ride the state vector's conditioning block as INFORMATION; the "
            "state-admission gauntlet still decides what may condition capital",
        ],
        "boundary": (
            "NOTHING HERE SIZES, VETOES OR REFUSES. The rows are a description of who is pressing "
            "on a price; no allocator fraction, heat floor or gate reads them as authority, and "
            "the dealer-gamma row is a behavioural PROXY because this desk holds no options "
            "chain -- it is labelled so in every row it appears in."),
        "why": ("the cot_* families measure one actor class, twelve days late, on the few "
                "instruments that report. This estimates five populations on every instrument "
                "with bars, and names which of them the desk's own live side is standing with."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--symbol", action="append", help="limit to these symbols")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, symbols=a.symbol)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        print(f"actor pressure: could not write {OUT}: {exc}")
        return 1
    print(f"actor pressure: {doc['n_measured']}/{doc['n_symbols']} symbol(s) measured, "
          f"{doc['n_skipped']} left for the next pass")
    for row in list(doc["by_symbol"].values())[:10]:
        if row.get("status") != "MEASURED":
            continue
        print(f"  {row['symbol']:<10} net={row['net_pressure']:+.3f} "
              f"dominant={row.get('dominant_actor')} "
              f"with={','.join(row.get('crowded_with') or []) or '-'} "
              f"against={','.join(row.get('crowded_against') or []) or '-'}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
