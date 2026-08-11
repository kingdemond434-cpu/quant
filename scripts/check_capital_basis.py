#!/usr/bin/env python3
"""CAPITAL-BASIS FENCE (R0287, under L1.58's waterfall discipline) -- no return without its
denominator.

WHAT IT CATCHES: a performance artifact publishing a return-like number (`return`, `cagr`,
`roi`, `growth_pct`, ...) with NO `capital_basis` declaration anywhere in the document. That is
the Quantopian-2019 shape (190% headline, 58% on capital actually drawn) and this desk's own
recurring class (R0234 ~25x equity undercount, R0235 testnet-sizing-live, the 13,155/4,500
split): the number is plausible, the units are right, and leverage is hiding in the denominator.

WHAT IT DOES NOT DO: it does not judge WHICH basis was declared. `portfolio_value` is legal to
declare precisely because a visible flawed basis can be argued with (L1.51's principle); only an
UNDECLARED one cannot. Computation belongs to libs/research/capital_basis.py.

SCOPE: every *.json under web/ and reports/ (the desk's published performance surface). PnL
DELTAS are not returns -- `net_pnl_equity_delta` needs no basis, `return_pct` does. Research
series named `returns` inside axis/screen payloads are ratios of PRICE series, not book
performance, so the key match is on REPORTING names, not every occurrence of the substring.

STATUS (fence_exit, L1.57 denominator declared):
  UNMEASURED           neither web/ nor reports/ exists -- nothing can be examined.
  UNDECLARED-RETURNS   >=1 artifact reports a return with no capital_basis. Exit 2.
  OK                   every return-reporting artifact declares its basis (including the honest
                       pre-launch case: N files scanned, zero of them report returns yet).

    python scripts/check_capital_basis.py [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: Key names that REPORT a return. Anchored on the whole key (after path-splitting), so
#: `net_pnl_equity_delta` (a dollar delta) and a nested `returns` price-series inside research
#: payloads do not match, while `return_pct`, `annual_return` and `cagr` do. Bare `roi` is
#: deliberately absent: on this desk `roi` fields are research-value estimates (dataset ROI,
#: queue ROI), not capital returns, and flagging them would teach readers to ignore the fence.
_RETURN_KEY = re.compile(
    r"(^|_)(return|cagr)(_pct|_frac|_annual|_net|_gross)?$|^(annual|total|net|gross)_return")

_SCAN_DIRS = ("web", "reports")

#: BOOTSTRAP DEBT, measured 2026-08-11 (R0287's first live run): every artifact already
#: publishing returns without a basis on the day the fence was born. The line holds going
#: forward -- a NEW undeclared artifact fails the fence -- while this list may only SHRINK as
#: producers migrate to libs.research.capital_basis.declare(). Adding to it is the one edit
#: this fence treats as loosening (the check_build_standard pattern: hold the line, migrate
#: deliberately).
_KNOWN_UNDECLARED: frozenset[str] = frozenset({
    "web/axis_shadows.json", "web/binance.json", "web/cashcarry_shadow.json",
    "web/combined.json", "web/crypto_portfolio.json", "web/crypto_shadow.json",
    "web/data.json", "web/firm_alphas.json", "web/freedata.json", "web/live_combined.json",
    "web/overlays.json", "web/portfolio.json", "web/shadow.json",
    "web/trend_regime_shadow.json", "web/trend_shadow.json",
    "reports/crypto_portfolio/report.json", "reports/mt5_portfolio/report.json",
})


def _return_keys(obj: Any, path: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{path}.{k}" if path else str(k)
            if isinstance(k, str) and _RETURN_KEY.search(k.lower()) and \
               isinstance(v, (int, float)):
                out.append(here)
            out.extend(_return_keys(v, here))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:200]):
            out.extend(_return_keys(v, f"{path}[{i}]"))
    return out


def _has_basis(obj: Any) -> bool:
    if isinstance(obj, dict):
        if "capital_basis" in obj:
            return True
        return any(_has_basis(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_basis(v) for v in obj[:200])
    return False


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    files: list[Path] = []
    for d in _SCAN_DIRS:
        base = root / d
        if base.is_dir():
            files.extend(sorted(base.rglob("*.json")))
    if not files:
        return {"status": "UNMEASURED", "scanned": 0,
                "why": "neither web/ nor reports/ holds a json artifact -- nothing examined"}
    undeclared: list[dict[str, Any]] = []
    n_reporting = 0
    for p in files:
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue  # unreadable artifacts are the freshness/provenance fences' beat, not ours
        keys = _return_keys(doc)
        if not keys:
            continue
        n_reporting += 1
        if not _has_basis(doc):
            undeclared.append({"artifact": str(p.relative_to(root)), "return_keys": keys[:6]})
    new = [u for u in undeclared if u["artifact"] not in _KNOWN_UNDECLARED]
    debt = [u for u in undeclared if u["artifact"] in _KNOWN_UNDECLARED]
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "R0287 -- a return without its capital basis is a numerator wearing a "
               "measurement's clothes; declare via libs.research.capital_basis.declare()",
        "status": "UNDECLARED-RETURNS" if new else ("BOOTSTRAP-DEBT" if debt else "OK"),
        "scanned": len(files),
        "n_reporting_returns": n_reporting,
        "undeclared_new": new,
        "bootstrap_debt": [u["artifact"] for u in debt],
        "n_bootstrap_remaining": len(debt),
    }


#: BOOTSTRAP-DEBT passes the gate (the debt is dated, listed and shrink-only) but stays a
#: distinct status so max_push and the ratchet see the remaining count, not a clean OK.
_PASSING = frozenset({"OK", "BOOTSTRAP-DEBT"})


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/capital_basis_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1) + "\n", "utf-8")
    print(json.dumps(rep, indent=1) if args.json else
          f"capital-basis: {rep['status']} -- {rep.get('n_reporting_returns', 0)} return-reporting "
          f"artifact(s) of {rep.get('scanned', 0)} scanned, "
          f"{len(rep.get('undeclared_new', []))} new undeclared, "
          f"{rep.get('n_bootstrap_remaining', 0)} bootstrap debt")
    return fence_exit(rep["status"], _PASSING, scanned=rep.get("scanned"),
                      of="web/**/*.json+reports/**/*.json")


if __name__ == "__main__":
    sys.exit(main())
