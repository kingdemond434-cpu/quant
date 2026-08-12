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
from scipy import stats

from libs.research.order_sensitive_decay import decay_verdict
from libs.research.upbit_data import upbit_daily_utc_keyed

SERIES = Path("data/signal_halflife.jsonl")
REPORT = Path("data/signal_halflife_report.json")
MIN_POINTS_TO_FIT = 8  # refuse to estimate a half-life below this
IC_WINDOW = 60  # rolling_ic's window length -- the sample size behind each window's IC


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


def rolling_ic(sig: dict, gb: dict, win: int = IC_WINDOW, step: int = 20):
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


def _window_pvalues(ics: list[float], n_obs: int) -> list[float]:
    """One-sided p-value per rolling window: is THIS window's IC better than chance?

    Sub-period p-values are what the mean-p combination needs, and they have to be real ones --
    feeding it something merely p-shaped makes the Uniform(0,1) null false and the combined error
    rate meaningless. n_obs is the window LENGTH (the correlation's sample size), not the number
    of windows.
    """
    out = []
    for r in ics:
        rc = min(max(float(r), -0.999999), 0.999999)
        t = rc * np.sqrt(max(n_obs - 2, 1) / (1.0 - rc * rc))
        out.append(float(stats.t.sf(t, df=max(n_obs - 2, 1))))
    return out


def merge_series(existing: list[dict], new: list[dict]) -> list[dict]:
    """One row per (date, signal). The last write for a day WINS; order is (date, signal).

    THE DEFECT THIS CLOSES (R0314). This file was APPENDED once per RUN while its only time key
    is the DATE, and the daily cycle fires more than once a day -- so by 2026-08-12, 32 of its 34
    (date, signal) keys carried 2-3 byte-identical copies. Nothing reads the file yet, and that is
    precisely why it had to be fixed rather than left: its whole stated purpose is to BE the decay
    series a future fit runs on ("a decay curve needs a TIME SERIES THAT STARTS NOW"), so the
    duplicates would have weighted those days 2-3x in that fit, silently, long after anyone
    remembered the writer appended per-run. Observation count is not sample size.

    A RETRACTION IS NEVER SILENTLY DROPPED. Re-running a past date cannot happen today (the script
    only ever writes `today`), but if it ever did, last-write-wins would quietly un-retract a row
    that was judged contaminated. The judgement survives the value.
    """
    out: dict[tuple[str, str], dict] = {}
    for r in [*existing, *new]:
        key = (str(r.get("date", "")), str(r.get("signal", "")))
        prior = out.get(key)
        if prior and prior.get("retracted_lookahead") and not r.get("retracted_lookahead"):
            r = {**r, "retracted_lookahead": prior["retracted_lookahead"],
                 "retraction": prior.get("retraction", "")}
        out[key] = r
    return [out[k] for k in sorted(out)]


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
        # R0312: `status` above is a bare +/-0.03 on a two-window difference, with no null behind
        # it -- it will call noise AGEING and has been publishing that verdict daily. The
        # order-sensitive bar keeps it (continuity) and adds a verdict that a null can refuse:
        # each window's IC becomes a one-sided p-value, and the early and late halves are
        # combined SEPARATELY at a pre-registered split. DSR/PSR cannot do this at all -- they
        # are order-invariant, so decay is invisible to them by construction.
        # NON-OVERLAPPING windows only. rolling_ic strides 20 through a 60-wide window, so
        # consecutive ICs share two thirds of their data and their p-values are strongly
        # positively dependent -- and mean-p's Irwin-Hall null assumes INDEPENDENCE. Feeding it
        # the overlapping series would produce an error rate that looks like a probability and is
        # not one, which is worse than no number. Taking every (win/step)-th window costs
        # resolution and buys a null that is actually true.
        stride = max(1, -(-IC_WINDOW // 20))                  # ceil(win / step)
        decay = decay_verdict(_window_pvalues(ics[::stride], IC_WINDOW))
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
                "decay": decay,
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
        if decay["verdict"] == "UNDERPOWERED":
            print(f"{'':22s} decay: UNDERPOWERED -- {decay['why']}")
        else:
            print(f"{'':22s} decay: {decay['verdict']} (order-sensitive, mean-p at a "
                  f"pre-registered split: early {decay['error_rate_early']:.4f} -> late "
                  f"{decay['error_rate_late']:.4f} over {decay['n_periods']} windows)")

    if rows:
        existing = []
        if SERIES.exists():
            existing = [json.loads(ln) for ln in SERIES.read_text("utf-8").splitlines() if ln.strip()]
        merged = merge_series(
            existing, [{k: v for k, v in r.items() if k != "curve"} for r in rows])
        # Rewrite via a temp file: a half-written series is worse than a stale one, and this is
        # the artifact a future decay fit is supposed to trust.
        tmp = SERIES.with_name(SERIES.name + ".tmp")
        tmp.write_text("".join(json.dumps(r) + "\n" for r in merged), "utf-8")
        tmp.replace(SERIES)
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
