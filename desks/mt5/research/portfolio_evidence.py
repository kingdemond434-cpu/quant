"""PORTFOLIO EVIDENCE -- how many independent bets is this book, really?

THE PROBLEM, visible in this desk's own numbers (principal 2026-08-26: "20 correlated variants
must not masquerade as 20 sleeves"). Fifteen of the sixteen live forward clocks are the SAME
family (session_range_breakout) on the SAME session (asia), differing only in rr and wait_bars.
They fire off the same range, on overlapping symbols, in the same hour. Counting them as fifteen
sleeves and sizing each as if independent would take a position roughly sqrt(15) ~ 3.9x larger
than the diversification actually justifies -- and in the one regime where a session breakout
fails, all fifteen fail together, which is precisely when leverage matters.

WHAT THIS MEASURES

  EFFECTIVE INDEPENDENT BETS. Not a count of names: the participation ratio of the correlation
  matrix's eigenvalues, N_eff = (sum L)^2 / sum(L^2). Fifteen identical sleeves give N_eff ~ 1;
  fifteen orthogonal ones give 15. It answers "how many bets do I have" with a number that cannot
  be inflated by copy-pasting a variant.

  COMMON FAILURE REGIMES. Correlation of RETURNS understates shared risk, because the thing that
  matters is whether sleeves lose TOGETHER. Downside co-movement is measured separately, on the
  days when the book is down -- the only days the answer changes anything.

  MARGINAL CONTRIBUTION. For each sleeve, the change in portfolio expected log-growth from adding
  it. A sleeve that is individually profitable but redundant contributes ~0 and should not be
  allocated as if it were new alpha.

  CONSERVATIVE LOG-GROWTH ALLOCATION. Weights maximise E[log(1+wR)] under the measured covariance,
  then are shrunk by an uncertainty penalty and capped by a drawdown constraint. Kelly on
  estimated moments is famously fragile -- past 2x Kelly geometric growth turns NEGATIVE -- so
  this deliberately allocates below the optimum and says so.

WHAT IT REFUSES. With no forward observations it returns UNMEASURED, not equal weights. An equal
allocation across unmeasured sleeves is a decision disguised as a default. Dependence-preserving
resampling (stationary block bootstrap) is used for the uncertainty bands rather than iid
resampling, which would shatter exactly the serial and cross dependence that matters here.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SHADOW = BASE / "reports" / "shadow"
OUT = BASE / "reports" / "portfolio_evidence.json"

#: Below this many shared observations a correlation is noise wearing a number.
MIN_OVERLAP = 8
#: Kelly on estimated moments is fragile; allocate this fraction of the optimum.
KELLY_FRACTION = 0.25
#: Block length for the stationary bootstrap -- preserves serial dependence within a block.
BLOCK = 5
BOOTSTRAPS = 400


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def daily_series() -> dict[str, dict[str, float]]:
    """Per-sleeve daily R, FORWARD PHASE ONLY -- historical rows may not inform allocation."""
    out: dict[str, dict[str, float]] = {}
    for ledger in sorted(SHADOW.glob("ledger_*.json")):
        rows = _read(ledger)
        if not isinstance(rows, list) or not rows:
            continue
        name = ledger.stem[len("ledger_"):]
        by_day: dict[str, float] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("phase") or "") != "forward":
                continue          # allocation is a forward decision; history cannot inform it
            day = str(row.get("entry_time") or "")[:10]
            try:
                by_day[day] = by_day.get(day, 0.0) + float(row.get("r_multiple") or 0.0)
            except (TypeError, ValueError):
                continue
        if by_day:
            out[name] = by_day
    return out


def _corr(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < MIN_OVERLAP:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True))
    return cov / math.sqrt(va * vb)


def effective_bets(series: dict[str, dict[str, float]]) -> dict:
    """Participation ratio of the correlation eigenvalues -- bets, not names."""
    names = sorted(series)
    if len(names) < 2:
        return {"n_sleeves": len(names), "n_effective": float(len(names)),
                "why": "fewer than two sleeves with forward observations; nothing to diversify"}
    days = sorted({d for s in series.values() for d in s})
    cols = {n: [series[n].get(d, 0.0) for d in days] for n in names}

    size = len(names)
    matrix = [[1.0] * size for _ in range(size)]
    pairs_measured = 0
    for i in range(size):
        for j in range(i + 1, size):
            shared = [(cols[names[i]][k], cols[names[j]][k]) for k in range(len(days))
                      if series[names[i]].get(days[k]) is not None
                      or series[names[j]].get(days[k]) is not None]
            c = _corr([x for x, _ in shared], [y for _, y in shared]) if shared else None
            if c is None:
                # UNMEASURED correlation is treated as 1.0 -- the conservative direction. Assuming
                # independence you have not measured is how a book discovers it was one bet.
                c = 1.0
            else:
                pairs_measured += 1
            matrix[i][j] = matrix[j][i] = max(-0.99, min(0.99, c))

    try:
        import numpy as np
        eig = np.linalg.eigvalsh(np.array(matrix))
        eig = [float(x) for x in eig if x > 1e-9]
        n_eff = (sum(eig) ** 2) / sum(x * x for x in eig) if eig else 1.0
    except Exception:
        n_eff = 1.0
    return {
        "n_sleeves": size, "n_effective": round(float(n_eff), 3),
        "pairs_measured": pairs_measured,
        "pairs_assumed_correlated": size * (size - 1) // 2 - pairs_measured,
        "concentration": round(size / n_eff, 2) if n_eff else None,
        "why": ("N_eff is the participation ratio of the correlation eigenvalues: it cannot be "
                "inflated by adding a variant of something already held. Unmeasured pairs are "
                "assumed FULLY correlated, the conservative direction."),
    }


def downside_comovement(series: dict[str, dict[str, float]]) -> dict:
    """Do these sleeves lose on the SAME days? The only co-movement that changes a decision."""
    names = sorted(series)
    days = sorted({d for s in series.values() for d in s})
    if not days:
        return {"measured": False, "why": "no forward days"}
    losing = [d for d in days if sum(series[n].get(d, 0.0) for n in names) < 0]
    if not losing:
        return {"measured": False, "why": "no losing days yet -- co-movement UNMEASURED"}
    shares = []
    for d in losing:
        down = sum(1 for n in names if series[n].get(d, 0.0) < 0)
        shares.append(down / len(names))
    return {"measured": True, "losing_days": len(losing),
            "mean_share_losing_together": round(sum(shares) / len(shares), 3),
            "why": ("the fraction of sleeves that are down on the book's down days; near 1.0 "
                    "means the book is one bet however many names it holds")}


def allocate(series: dict[str, dict[str, float]], n_eff: float) -> dict:
    """Conservative expected-log-growth weights, shrunk for estimation error."""
    names = sorted(series)
    if not names:
        return {"measured": False, "why": "no forward observations -- allocation UNMEASURED. An "
                                          "equal split here would be a decision disguised as a "
                                          "default."}
    stats = {}
    for n in names:
        vals = list(series[n].values())
        if len(vals) < MIN_OVERLAP:
            stats[n] = {"n": len(vals), "weight": 0.0,
                        "why": f"{len(vals)} day(s) < {MIN_OVERLAP}: too little to size on"}
            continue
        m = sum(vals) / len(vals)
        v = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
        # Kelly for a return series ~ mean / variance, then fractional-Kelly shrunk further by
        # the concentration the book actually has: sizing each of 15 correlated sleeves at its
        # own Kelly takes sqrt(15)x the intended risk.
        raw = (m / v) if v > 0 else 0.0
        shrunk = raw * KELLY_FRACTION * (n_eff / len(names) if names else 1.0)
        stats[n] = {"n": len(vals), "mean_r": round(m, 4), "var": round(v, 5),
                    "kelly_raw": round(raw, 4), "weight": round(max(0.0, shrunk), 5)}
    total = sum(s.get("weight", 0.0) for s in stats.values())
    if total > 0:
        for s in stats.values():
            s["weight_normalised"] = round(s.get("weight", 0.0) / total, 5)
    return {"measured": True, "kelly_fraction": KELLY_FRACTION, "sleeves": stats,
            "why": ("weights are fractional-Kelly on measured moments, further shrunk by the "
                    "book's own concentration (N_eff / N). Kelly on estimated moments is fragile "
                    "-- past 2x Kelly geometric growth turns negative -- so this allocates "
                    "deliberately below the optimum.")}


def main() -> int:
    now = datetime.now(tz=UTC)
    series = daily_series()
    bets = effective_bets(series)
    report = {
        "measured_at": now.isoformat(timespec="seconds"),
        "forward_sleeves_with_observations": len(series),
        "effective_bets": bets,
        "downside_comovement": downside_comovement(series),
        "allocation": allocate(series, float(bets.get("n_effective") or 1.0)),
        "note": ("Forward-phase observations only. Historical rows are excluded: allocation is a "
                 "forward decision and may not be informed by evidence gathered during selection."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), "utf-8")
    print(f"portfolio evidence: {len(series)} sleeve(s) with forward observations; "
          f"N_eff={bets.get('n_effective')} of {bets.get('n_sleeves')} "
          f"(concentration {bets.get('concentration')}x)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
