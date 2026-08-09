"""SIGNAL HALF-LIFE / DECAY TRACKER (Level-5 layer, instrumentation-first).

WHY BUILD IT BEFORE THERE IS A SURVIVOR: a decay curve needs a TIME SERIES THAT STARTS NOW. If
this waits until a signal is confirmed, the pre-confirmation baseline is permanently lost -- you
cannot retroactively record what you never instrumented. Recording is cheap and irreversible if
skipped; MODEL-FITTING is what must wait for evidence. So this appends one honest observation per
run from day zero and refuses to fit a decay curve until it has enough points.

The graveyard handles DEATH (a signal that failed validation). This handles AGEING -- a signal
that WORKED and is losing potency, which is invisible to a pass/fail gate and is how live books
quietly bleed. Tracks per signal: rolling IC over successive windows, its trend, and a half-life
estimate once enough history exists.

Appends to data/signal_halflife.jsonl (one row per signal per run). Read-only w.r.t. everything
else. Run from repo root, ideally on the daily cadence.
"""

from __future__ import annotations

import contextlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.upbit_data import upbit_daily_utc_keyed

SERIES = Path("data/signal_halflife.jsonl")
REPORT = Path("data/signal_halflife_report.json")
MIN_POINTS_TO_FIT = 8  # refuse to estimate a half-life below this


def _get(u, t=40):
    return json.loads(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
        )
        .read()
        .decode()
    )


def binance():
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=900")
    return {
        datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
        for r in rows
    }


def stables():
    d = _get("https://stablecoins.llama.fi/stablecoincharts/all")
    o = {}
    for x in d:
        v = x.get("totalCirculatingUSD") or {}
        p = v.get("peggedUSD") if isinstance(v, dict) else None
        if p is not None:
            o[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(p)
    return o


def kimchi(gb):
    # R0060/R0067 single source: the inline copy here printed a contaminated "kimchi STRENGTHENING"
    # row during the refutation audit. upbit_data owns the keying; never re-derive it.
    kb = upbit_daily_utc_keyed()
    res = _get("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=300d")[
        "chart"
    ]["result"][0]
    fx = {
        datetime.fromtimestamp(int(t), tz=UTC).date().isoformat(): float(c)
        for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"], strict=False)
        if c
    }
    return {d: kb[d] / fx[d] / gb[d] - 1.0 for d in (set(kb) & set(fx) & set(gb))}


def rolling_ic(sig: dict, gb: dict, win: int = 60, step: int = 20):
    """IC computed over successive non-overlapping-ish windows -> the ageing curve."""
    dates = sorted(set(sig) & set(gb))
    if len(dates) < win + 25:
        return []
    s = np.array([sig[d] for d in dates])
    px = np.array([gb[d] for d in dates])
    ret = np.zeros(len(px))
    ret[1:] = px[1:] / px[:-1] - 1.0
    fwd = np.roll(ret, -1)
    z = np.zeros(len(s))
    for t in range(20, len(s)):
        w = s[t - 20 : t]
        sd = w.std()
        z[t] = (s[t] - w.mean()) / sd if sd > 0 else 0.0
    out = []
    for a in range(20, len(s) - win - 1, step):
        zv, fv = z[a : a + win], fwd[a : a + win]
        if zv.std() and fv.std():
            out.append({"end_date": dates[a + win], "ic": float(np.corrcoef(zv, fv)[0, 1])})
    return out


def half_life(ics: list[float]) -> float | None:
    """Fit |IC| decay: |IC_t| ~ |IC_0| * exp(-t/tau).

    Returns tau in windows, None if not decaying.
    """
    y = np.array([abs(v) for v in ics])
    y = np.where(y < 1e-4, 1e-4, y)
    x = np.arange(len(y), dtype=float)
    b, _a = np.polyfit(x, np.log(y), 1)
    if b >= -1e-6:
        return None  # flat or improving -- no decay to report
    return float(-np.log(2) / b)


def main() -> None:
    gb = binance()
    sigs = {}
    with contextlib.suppress(Exception):
        sigs["stablecoin_supply"] = stables()
    with contextlib.suppress(Exception):
        sigs["kimchi_premium"] = kimchi(gb)

    today = datetime.now(tz=UTC).date().isoformat()
    rows, report = [], []
    for name, s in sigs.items():
        curve = rolling_ic(s, gb)
        if not curve:
            print(f"{name:22s} insufficient history for a curve")
            continue
        ics = [c["ic"] for c in curve]
        recent = float(np.mean(ics[-2:])) if len(ics) >= 2 else ics[-1]
        early = float(np.mean(ics[:2])) if len(ics) >= 2 else ics[0]
        trend = recent - early
        hl = half_life(ics) if len(ics) >= MIN_POINTS_TO_FIT else None
        status = "AGEING" if trend < -0.03 else "STRENGTHENING" if trend > 0.03 else "STABLE"
        rows.append(
            {
                "date": today,
                "signal": name,
                "n_windows": len(ics),
                "ic_early": round(early, 4),
                "ic_recent": round(recent, 4),
                "trend": round(trend, 4),
                "half_life_windows": hl,
                "status": status,
                "curve": [round(v, 4) for v in ics],
            }
        )
        report.append(rows[-1])
        hl_s = (
            f"{hl:.1f} windows"
            if hl
            else (
                "n/a (not decaying)"
                if len(ics) >= MIN_POINTS_TO_FIT
                else f"n/a (<{MIN_POINTS_TO_FIT} pts)"
            )
        )
        print(
            f"{name:22s} windows={len(ics):2d} | IC early {early:+.4f} -> recent {recent:+.4f} "
            f"| trend {trend:+.4f} | half-life {hl_s} | {status}"
        )
        print(f"{'':22s} curve: " + " ".join(f"{v:+.3f}" for v in ics))

    if rows:
        with SERIES.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({k: v for k, v in r.items() if k != "curve"}) + "\n")
        REPORT.write_text(
            json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "signals": report}, indent=1),
            "utf-8",
        )
    print(f"\nappended {len(rows)} observations -> {SERIES}")
    print("NOTE: ageing is invisible to a pass/fail gate -- a signal can pass validation and still")
    print("      be losing potency. Half-life is only FIT once >=8 windows exist; until then the")
    print("      tracker records and refuses to estimate.")


if __name__ == "__main__":
    main()
