"""HYPERLIQUID SKILL-PERSISTENCE TEST -- the foundational question behind copytrading.

THE QUESTION: does a trader's PAST performance predict their FUTURE performance? If not,
copytrading has no basis (you would be selecting on luck), and the 26-layer trader-intelligence
spec collapses regardless of how well engineered it is.

WHY THIS BEATS THE FAILED AGGREGATE TEST: per-trader (no averaging away the skilled minority),
skill-defined-by-PnL (not by account size like Binance's 'top trader' cohort), and it measures
PERSISTENCE (the actual luck/skill discriminator) rather than a positioning level.

SURVIVORSHIP HANDLING (honest): Hyperliquid's public leaderboard is a CURRENT snapshot of ~41k
addresses that INCLUDES large losers (verified: sample account -$3.3M month PnL), so it is NOT a
winners-only list. RESIDUAL BIAS STATED: accounts fully liquidated and closed mid-window may be
absent entirely -> persistence could be biased UP. This test can therefore REFUTE persistence
cleanly; a positive result needs the forward-clock confirmation (seeded separately).

NON-OVERLAPPING WINDOWS (no lookahead):
    formation = month_pnl - week_pnl   (approx weeks -4..-1)
    holding   = week_pnl               (the most recent week)
Both normalised by accountValue -> comparable returns. Ranked-correlation + decile spread.

CONFOUND CONTROLS: (1) min accountValue + min volume filters kill micro-account ROI noise;
(2) within-size-bucket repeat -- if persistence is only market beta (everyone long in an up week),
it should NOT survive inside homogeneous size buckets and the decile spread would be flat;
(3) a shuffled-label null gives the luck baseline.

Read-only screen. Zero promotion authority. Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

_LB = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
MIN_ACCT_VALUE = 10_000.0     # kill micro accounts (ROI noise)
MIN_MONTH_VLM = 100_000.0     # kill dormant accounts


def _fetch() -> list[dict]:
    req = urllib.request.Request(_LB, headers={"User-Agent": "quant-hl/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode())
    return d.get("leaderboardRows", d) if isinstance(d, dict) else d


def _spearman(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, 0.0
    rho = float(np.corrcoef(ra, rb)[0, 1])
    n = len(a)
    t = rho * np.sqrt((n - 2) / max(1e-12, 1 - rho ** 2)) if n > 2 and abs(rho) < 1 else 0.0
    return rho, float(t)


def _decile_spread(form: np.ndarray, hold: np.ndarray, q: int = 10):
    order = np.argsort(form)
    k = len(form) // q
    if k < 5:
        return None
    bot, top = hold[order[:k]], hold[order[-k:]]
    diff = top.mean() - bot.mean()
    se = np.sqrt(top.var(ddof=1) / len(top) + bot.var(ddof=1) / len(bot))
    return {"top_decile_mean_ret": round(float(top.mean()), 5),
            "bottom_decile_mean_ret": round(float(bot.mean()), 5),
            "spread": round(float(diff), 5),
            "t": round(float(diff / se), 2) if se > 0 else 0.0,
            "n_per_decile": int(k)}


def _run(form: np.ndarray, hold: np.ndarray, label: str) -> dict:
    rho, t = _spearman(form, hold)
    dec = _decile_spread(form, hold)
    rng = np.random.default_rng(7)
    null = [abs(_spearman(rng.permutation(form), hold)[0]) for _ in range(200)]
    out = {"label": label, "n": len(form), "spearman_rho": round(rho, 4),
           "t_stat": round(t, 2), "null_rho_p95": round(float(np.percentile(null, 95)), 4),
           "decile": dec}
    print(f"\n[{label}] n={len(form)}")
    print(f"  rank-corr(formation, holding) rho={rho:+.4f}  t={t:+.2f}  "
          f"(shuffled-null |rho| p95={np.percentile(null,95):.4f})")
    if dec:
        print(f"  top-decile fwd ret {dec['top_decile_mean_ret']:+.4f} vs bottom "
              f"{dec['bottom_decile_mean_ret']:+.4f} | spread {dec['spread']:+.4f} (t {dec['t']:+.2f})")
    return out


def main() -> None:
    rows = _fetch()
    print(f"leaderboard rows fetched: {len(rows)}")
    recs = []
    for r in rows:
        try:
            av = float(r.get("accountValue", 0) or 0)
            wp = {w: v for w, v in r.get("windowPerformances", [])}
            m, w7 = wp.get("month", {}), wp.get("week", {})
            mp, wpnl = float(m.get("pnl", 0) or 0), float(w7.get("pnl", 0) or 0)
            vlm = float(m.get("vlm", 0) or 0)
            if av < MIN_ACCT_VALUE or vlm < MIN_MONTH_VLM:
                continue
            recs.append({"av": av, "form": (mp - wpnl) / av, "hold": wpnl / av, "vlm": vlm})
        except (TypeError, ValueError):
            continue
    print(f"after filters (acctValue>=${MIN_ACCT_VALUE:,.0f}, monthVlm>=${MIN_MONTH_VLM:,.0f}): "
          f"{len(recs)} traders")
    if len(recs) < 200:
        raise SystemExit("insufficient cohort")

    form = np.array([x["form"] for x in recs])
    hold = np.array([x["hold"] for x in recs])
    # winsorise the tails so a few extreme accounts cannot drive the rank stats
    lo, hi = np.percentile(form, [0.5, 99.5]); form_w = np.clip(form, lo, hi)
    lo2, hi2 = np.percentile(hold, [0.5, 99.5]); hold_w = np.clip(hold, lo2, hi2)

    results = [_run(form_w, hold_w, "ALL (formation=month-week, holding=week)")]

    # confound control: within homogeneous size buckets (beta/size cannot explain persistence here)
    av = np.array([x["av"] for x in recs])
    edges = np.percentile(av, [0, 33, 66, 100])
    for i, nm in enumerate(["small", "mid", "large"]):
        m = (av >= edges[i]) & (av <= edges[i + 1])
        if m.sum() >= 200:
            results.append(_run(form_w[m], hold_w[m], f"size-bucket {nm} (n={int(m.sum())})"))

    verdict = ("PERSISTENCE DETECTED" if abs(results[0]["t_stat"]) >= 3.0
               and abs(results[0]["spearman_rho"]) > results[0]["null_rho_p95"]
               else "NO PERSISTENCE (selecting past winners does not predict future)")
    print(f"\n=== VERDICT: {verdict} ===")
    Path("data/hl_skill_persistence.json").write_text(json.dumps(
        {"updated": datetime.now(tz=UTC).isoformat(), "cohort": len(recs),
         "verdict": verdict, "results": results,
         "caveat": "leaderboard is a current snapshot; fully-closed blowups may be absent -> "
                   "persistence may be biased UP. Refutation is clean; confirmation needs a "
                   "forward clock."}, indent=1), "utf-8")


if __name__ == "__main__":
    main()
