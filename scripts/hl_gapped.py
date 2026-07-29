"""GAPPED skill-persistence test -- kills the position-overlap / beta confound.

The adjacent-window test found rho=+0.12 (t=10.9), but formation (weeks -4..-1) and holding
(week -1..0) TOUCH: a trader holding one position across the boundary gets mechanically correlated
PnL (an open position, not skill), and persistent directional bias in a trending market shows the
same way. Fix = insert a GAP so no single position can span both windows:

  A adjacent  formation=(month-week)      holding=week      gap 0      <- the original (confounded)
  B GAPPED    formation=(allTime-month)   holding=week      gap ~3wk   <- decisive
  C long-horz formation=(allTime-month)   holding=month     gap 0      <- longer holding

If B survives, past skill predicts future performance ACROSS a 3-week gap -> position-overlap and
short-horizon beta cannot explain it. If B collapses to ~null while A is strong, the 'skill' was
mechanical position carry. Also reports BTC's move per window for the beta discussion.
Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_LB = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
MIN_AV, MIN_VLM = 10_000.0, 100_000.0


def _get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "quant-hl/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _spear(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, 0.0
    rho = float(np.corrcoef(ra, rb)[0, 1])
    n = len(a)
    t = rho * np.sqrt((n - 2) / max(1e-12, 1 - rho ** 2)) if n > 2 and abs(rho) < 1 else 0.0
    return rho, float(t)


def _dec(form, hold, q=10):
    o = np.argsort(form); k = len(form) // q
    if k < 5:
        return None
    top, bot = hold[o[-k:]], hold[o[:k]]
    d = top.mean() - bot.mean()
    se = np.sqrt(top.var(ddof=1) / k + bot.var(ddof=1) / k)
    return {"top": round(float(top.mean()), 5), "bot": round(float(bot.mean()), 5),
            "spread": round(float(d), 5), "t": round(float(d / se), 2) if se > 0 else 0.0}


def _wins(x):
    lo, hi = np.percentile(x, [0.5, 99.5])
    return np.clip(x, lo, hi)


def main() -> None:
    rows = json.loads(_get(_LB))
    rows = rows.get("leaderboardRows", rows) if isinstance(rows, dict) else rows
    recs = []
    for r in rows:
        try:
            av = float(r.get("accountValue", 0) or 0)
            wp = dict(r.get("windowPerformances", []))
            mp = float(wp.get("month", {}).get("pnl", 0) or 0)
            wk = float(wp.get("week", {}).get("pnl", 0) or 0)
            at = float(wp.get("allTime", {}).get("pnl", 0) or 0)
            vlm = float(wp.get("month", {}).get("vlm", 0) or 0)
            if av < MIN_AV or vlm < MIN_VLM:
                continue
            recs.append((av, at, mp, wk))
        except (TypeError, ValueError):
            continue
    av = np.array([x[0] for x in recs]); at = np.array([x[1] for x in recs])
    mp = np.array([x[2] for x in recs]); wk = np.array([x[3] for x in recs])
    print(f"cohort: {len(recs)} traders")

    variants = {
        "A adjacent  form=month-week  hold=week   (gap 0)":   ((mp - wk) / av, wk / av),
        "B GAPPED    form=allTime-mo  hold=week   (gap ~3wk)": ((at - mp) / av, wk / av),
        "C long-horz form=allTime-mo  hold=month  (gap 0)":    ((at - mp) / av, mp / av),
    }
    out = []
    for label, (f, h) in variants.items():
        f, h = _wins(f), _wins(h)
        rho, t = _spear(f, h)
        rng = np.random.default_rng(11)
        null = float(np.percentile([abs(_spear(rng.permutation(f), h)[0]) for _ in range(150)], 95))
        d = _dec(f, h)
        sig = "SURVIVES" if abs(t) >= 3.0 and abs(rho) > null else "COLLAPSES"
        print(f"\n[{label}]")
        print(f"  rho={rho:+.4f} t={t:+.2f} null_p95={null:.4f} -> {sig}")
        if d:
            print(f"  decile: top {d['top']:+.4f} bot {d['bot']:+.4f} spread {d['spread']:+.4f} (t {d['t']:+.2f})")
        out.append({"variant": label, "rho": round(rho, 4), "t": round(t, 2),
                    "null_p95": round(null, 4), "decile": d, "status": sig})

    # BTC context for the beta discussion
    try:
        k = json.loads(_get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1w&limit=6", 30))
        w = [(float(x[4]) / float(x[1]) - 1.0) for x in k]
        print(f"\nBTC weekly returns (last {len(w)}): " + " ".join(f"{x*100:+.1f}%" for x in w))
    except Exception:
        pass

    Path("data/hl_gapped_persistence.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "cohort": len(recs), "variants": out},
        indent=1), "utf-8")


if __name__ == "__main__":
    main()
