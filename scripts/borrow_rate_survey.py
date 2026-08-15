#!/usr/bin/env python3
"""WHICH ASSET TO BORROW -- free growth, no research required.

THE POINT, IN ONE LINE: the venue charges a DIFFERENT hourly rate per asset, and the book's growth
rate moves one-for-one with the rate it pays on the borrowed part. Borrowing the wrong stablecoin
is a pure, recurring, avoidable cost.

WHY THIS IS WORTH A SCRIPT RATHER THAN A GLANCE

`binance_margin_live.borrow_rate()` already reads the live rate correctly, and defaults to USDC.
Nobody ever checked whether USDC is the cheap one. The rates float independently -- they are set by
supply and demand in each asset's lending pool -- and the spread between the cheapest and dearest
stablecoin is routinely tens of basis points, occasionally more than a point. On a levered book
that is growth, given away, forever, for a default nobody revisited.

THE ARITHMETIC THAT MAKES IT ONE-FOR-ONE

    g(f) = f*mu - r*(f-1) - f^2 sigma^2 / 2

At the Kelly optimum f* = (mu - r)/sigma^2, so dg/dr = -(f* - 1). Below f = 1 the book borrows
nothing and the rate is irrelevant; at f = 2 a point off the rate is a point of growth; at f = 3 it
is two. The saving SCALES WITH LEVERAGE, which is exactly when it is least visible on a statement.

WHAT THIS DOES NOT DO

Move any money, and it never will. It reads published rates and prints arithmetic. Switching the
borrowed asset is a decision with venue mechanics behind it -- conversion cost, pair liquidity,
whether the book's quote currency changes -- and none of that is a thing a survey should decide.

**A CHEAPER RATE IS NOT A REASON TO BORROW MORE.** Kelly already contains the rate: f* rises as r
falls, on its own, by the correct amount. Reading a cheap rate and then adding leverage on top of
what Kelly returned is double-counting the same fact.

    python scripts/borrow_rate_survey.py
    python scripts/borrow_rate_survey.py --assets USDC,USDT,FDUSD,BTC --f 2.0
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys
from pathlib import Path

# The assignment must not sit BETWEEN the imports: ruff's E402 tolerates a bare sys.path guard
# and not an intervening statement, so `_ROOT` is bound after the import block instead.
if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from datetime import UTC, datetime
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "reports" / "borrow_rate_survey.json"

#: FUNDING ASSETS -- the only ones this survey may recommend. Borrowing one of these is a pure
#: financing decision because the book's P&L is already denominated in dollars, so the liability
#: does not move against you.
FUNDING_ASSETS = frozenset({"USDC", "USDT", "FDUSD", "TUSD", "DAI", "USDP", "BUSD"})

#: Surveyed for INFORMATION only. Borrowing BTC is not cheap money at any rate -- see
#: `_is_funding` below.
DEFAULT_ASSETS = ("USDC", "USDT", "FDUSD", "BTC", "ETH")


def _is_funding(asset: str) -> bool:
    """Can borrowing this asset be compared on RATE ALONE? Only for the quote currency.

    **THIS DISTINCTION IS THE WHOLE SAFETY PROPERTY OF THIS SCRIPT, AND ITS FIRST VERSION DID NOT
    HAVE IT.** That version sorted every asset by rate and recommended the cheapest. Run live it
    returned "cheapest BTC at 0.44%/yr -- borrowing the cheapest is free growth", which is wrong
    in a way that can cost far more than the entire edge.

    Borrowing BTC does not give you cheap dollars. It gives you a SHORT BTC POSITION: the
    liability is denominated in BTC, so it grows with the BTC price. On a $10,000 BTC loan a 30%
    BTC year costs $3,000 -- not the $44 the interest rate implies. The rate is low precisely
    because it is nearly irrelevant to the true cost of that trade.

    A stablecoin loan has no such exposure. The book's P&L is in dollars, the debt is in dollars,
    and the rate genuinely is the cost. Those are the only ones that can be ranked against each
    other, so those are the only ones ranked.

    Deliberately a WHITELIST, not a "is it volatile" heuristic: a new stablecoin absent from the
    list is treated as non-funding and merely reported, which errs toward not recommending
    something. A depegged stablecoin also stops being a pure funding asset, and no rate table can
    see a depeg -- so the list is necessary and never sufficient.
    """
    return str(asset).upper() in FUNDING_ASSETS


def growth(f: float, mu: float, sigma: float, r: float) -> float:
    """g(f) = f*mu - r*max(0, f-1) - f^2 sigma^2/2. Interest on the BORROWED part only."""
    f = float(f)
    return f * mu - r * max(0.0, f - 1.0) - (f ** 2) * (sigma ** 2) / 2.0


def kelly(mu: float, sigma: float, r: float) -> float:
    excess = mu - r
    return excess / (sigma ** 2) if excess > 0 and sigma > 0 else 0.0


def survey(assets: tuple[str, ...]) -> list[dict[str, Any]]:
    """Live rate per asset. An unreadable rate is UNMEASURED, never a default."""
    from libs.execution.binance_margin_live import borrow_rate
    out = []
    for a in assets:
        try:
            rate, why = borrow_rate(a)
        except Exception as exc:                      # a survey must not break a trading path
            rate, why = None, f"{type(exc).__name__}: {exc}"
        out.append({"asset": a.upper(), "annual_rate": rate, "why": why})
    return out


def report(rows: list[dict[str, Any]], *, mu: float, sigma: float,
           f_at: float | None = None) -> dict[str, Any]:
    for r in rows:
        r["funding_asset"] = _is_funding(r.get("asset", ""))
    priced = [r for r in rows
              if isinstance(r.get("annual_rate"), (int, float)) and r["funding_asset"]]
    informational = [r for r in rows
                     if isinstance(r.get("annual_rate"), (int, float)) and not r["funding_asset"]]
    rep: dict[str, Any] = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "mu_annual": mu, "sigma_annual": sigma,
        "rows": rows, "n_priced": len(priced),
        "n_informational": len(informational),
        "n_unmeasured": sum(1 for r in rows if r.get("annual_rate") is None),
        "funding_assets_only": sorted(FUNDING_ASSETS),
    }
    if not priced:
        rep["verdict"] = ("NO FUNDING-ASSET RATE COULD BE READ. Not zero, not 10% -- unknown. "
                          "Sizing leverage "
                          "against an unmeasured cost of capital is how a book borrows into "
                          "negative growth while its printed leverage looks considered.")
        return rep

    priced.sort(key=lambda r: r["annual_rate"])
    cheap, dear = priced[0], priced[-1]
    for r in priced:
        rr = r["annual_rate"]
        f_star = kelly(mu, sigma, rr)
        r["kelly_f"] = round(f_star, 3)
        r["growth_at_kelly"] = round(growth(f_star, mu, sigma, rr), 5)
        if f_at:
            r["growth_at_f"] = round(growth(f_at, mu, sigma, rr), 5)

    spread = dear["annual_rate"] - cheap["annual_rate"]
    gain = cheap["growth_at_kelly"] - dear["growth_at_kelly"]
    rep.update({
        "cheapest": cheap["asset"], "cheapest_rate": cheap["annual_rate"],
        "dearest": dear["asset"], "dearest_rate": dear["annual_rate"],
        "rate_spread": round(spread, 6),
        "growth_gain_at_kelly": round(gain, 6),
        "verdict": (
            f"cheapest {cheap['asset']} at {cheap['annual_rate']:.2%}/yr, dearest "
            f"{dear['asset']} at {dear['annual_rate']:.2%}/yr -- a {spread:.2%} spread worth "
            f"{gain:.2%}/yr of growth at each one's own Kelly. "
            + ("Borrowing the cheapest is free growth, subject to the venue mechanics of "
               "actually holding it." if gain > 0.002 else
               "Too small to be worth a conversion; the default is fine.")),
    })
    return rep


def render(rep: dict[str, Any], f_at: float | None) -> str:
    L = [f"BORROW RATE SURVEY  ({rep['updated'][:19]}Z)", "",
         f"  book mu {rep['mu_annual']:.2%}/yr   sigma {rep['sigma_annual']:.2%}/yr", ""]
    hdr = f"  {'asset':<8}{'rate/yr':>10}{'kelly f':>10}{'g at kelly':>13}"
    if f_at:
        hdr += f"{'g at f=' + format(f_at, '.1f'):>13}"
    L += [hdr, "  " + "-" * (len(hdr) - 2)]
    for r in rep["rows"]:
        rate = r.get("annual_rate")
        if rate is None:
            L.append(f"  {r['asset']:<8}{'UNMEASURED':>10}   {r.get('why','')[:52]}")
            continue
        if not r.get("funding_asset"):
            L.append(f"  {r['asset']:<8}{rate:>9.2%}{'--':>10}{'NOT A FUNDING ASSET':>26}")
            continue
        line = (f"  {r['asset']:<8}{rate:>9.2%}{r['kelly_f']:>10.2f}"
                f"{r['growth_at_kelly']:>12.2%}")
        if f_at:
            line += f"{r.get('growth_at_f', 0):>12.2%}"
        L.append(line)

    if rep.get("n_informational"):
        L += ["",
              "  ASSETS SHOWN BUT NOT RANKED, and the reason is not conservatism:",
              "  borrowing BTC or ETH is NOT cheap funding at any rate. The liability is",
              "  denominated in that asset, so the loan IS a short position in it. A",
              "  $10,000 BTC loan through a 30% BTC year costs $3,000, not the $44 the",
              "  rate implies. Those rates are low precisely because the interest is the",
              "  smallest part of what that trade costs.",
              "",
              "  Only assets your P&L is already denominated in can be compared on rate."]
    L += ["", "  " + rep.get("verdict", "")]
    L += ["",
          "  dg/dr = -(f* - 1): the saving scales with LEVERAGE and is zero unlevered.",
          "  A cheaper rate is NOT a reason to add leverage on top -- Kelly already",
          "  contains the rate, and f* rises on its own by exactly the right amount."]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", default=",".join(DEFAULT_ASSETS))
    ap.add_argument("--mu", type=float, default=0.10, help="book annual drift")
    ap.add_argument("--sigma", type=float, default=0.208, help="book annual vol")
    ap.add_argument("--f", type=float, default=None, help="also price growth at this leverage")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    assets = tuple(x.strip().upper() for x in a.assets.split(",") if x.strip())
    rows = survey(assets)
    rep = report(rows, mu=a.mu, sigma=a.sigma, f_at=a.f)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if a.json else render(rep, a.f))
    print(f"\n-> {_OUT}")


if __name__ == "__main__":
    main()
