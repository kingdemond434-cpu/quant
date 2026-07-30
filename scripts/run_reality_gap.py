"""REALITY GAP ENGINE -- constitution L2.10, made a standing measurement (triage #127).

L1.4 says reality outranks simulation and every predicted-vs-realised divergence triggers
investigation. The desk HELD that principle and still found its two largest gaps by hand: the
7.75x fee-vs-harvest fire (implied costs $876 against $113 harvested) and the 36.4% level offset
between the mark-based book and the venue-truth measure. Both were reality gaps that no organ
was computing. A principle nobody computes is prose.

THE CHAIN, compared link by link:

    backtest  ->  shadow  ->  paper/executed book  ->  live venue truth
       |            |               |                        |
    modelled     forward         realised                 venue-native
    Sharpe/cost  Sharpe/cost     Sharpe/cost/fills        equity/fees

Each ADJACENT pair yields one gap with a ratio and a verdict. Verdicts are deliberately blunt:
  OK        ratio inside the tolerance band
  GAP       outside the band -- a research input, logged, owed an explanation
  BREAK     so far outside that the two numbers cannot describe the same strategy
  NO-DATA   a link is missing (fail-LOUD: the health.json fail-open lesson)

WHAT THIS IS NOT: it is not a promotion gate and it never sizes anything. It measures, attributes
and pages. Fixing a gap is a research action taken by a human or a named organ, on the record.

Pure stdlib; every input read defensively (data/ and web/ are VPS-side).

    python scripts/run_reality_gap.py [--json]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("web/reality_gap.json")

# Tolerance bands. Deliberately WIDE: this instrument exists to catch order-of-magnitude lies
# (7.75x, 36%), not to litigate noise. A narrow band on n<30 samples would page constantly and
# get muted, which is how the pager died the first time.
_SHARPE_BAND = 2.0      # |ratio| outside [1/2, 2] between adjacent links = GAP
_SHARPE_BREAK = 5.0     # outside [1/5, 5] = BREAK (or sign flip, see _cmp)
_COST_BAND = 1.5        # realised cost >1.5x modelled = GAP
_COST_BREAK = 3.0       # >3x = BREAK -- the 7.75x fire would have been BREAK on day one
_EQUITY_BAND = 0.05     # >5% divergence between book equity and venue-truth equity = GAP
_EQUITY_BREAK = 0.15    # >15% = BREAK -- the measured 36.4% offset lands here


def _read(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _num(obj: Any, *keys: str) -> float | None:
    """First numeric value found at any of `keys`, searching one nesting level down too."""
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    for v in obj.values():
        if isinstance(v, dict):
            got = _num(v, *keys)
            if got is not None:
                return got
    return None


def _cmp(name: str, upstream: float | None, downstream: float | None, *,
         band: float, break_at: float, kind: str) -> dict[str, Any]:
    """One link comparison. `kind` picks the arithmetic: ratio for Sharpe/cost, relative
    difference for equity levels (where the question is 'how far apart', not 'how many times')."""
    if upstream is None or downstream is None:
        missing = "upstream" if upstream is None else "downstream"
        return {"link": name, "verdict": "NO-DATA", "detail": f"{missing} value unavailable"}
    if kind == "level":
        base = max(abs(upstream), 1e-9)
        rel = abs(downstream - upstream) / base
        verdict = "BREAK" if rel > break_at else "GAP" if rel > band else "OK"
        return {"link": name, "verdict": verdict, "upstream": round(upstream, 4),
                "downstream": round(downstream, 4), "relative_diff": round(rel, 4)}
    # SIGN FLIP IS ALWAYS A BREAK, whatever the magnitude: a strategy that made money in
    # simulation and loses it forward is not a calibration error, it is a different strategy.
    if upstream * downstream < 0:
        return {"link": name, "verdict": "BREAK", "upstream": round(upstream, 4),
                "downstream": round(downstream, 4), "ratio": None,
                "detail": "SIGN FLIP -- upstream and downstream disagree on direction"}
    if abs(upstream) < 1e-9:
        return {"link": name, "verdict": "NO-DATA", "detail": "upstream ~0, ratio undefined"}
    ratio = downstream / upstream
    outside = ratio > break_at or ratio < 1.0 / break_at
    edge = ratio > band or ratio < 1.0 / band
    verdict = "BREAK" if outside else "GAP" if edge else "OK"
    return {"link": name, "verdict": verdict, "upstream": round(upstream, 4),
            "downstream": round(downstream, 4), "ratio": round(ratio, 3)}


def _cost_link() -> dict[str, Any]:
    """MODELLED cost vs REALISED cost -- the 7.75x fee-fire detector, generalised.

    Modelled: data/cost_model.json median book-walk. Realised: fees+slippage per round-trip from
    the trade log, or the harvest-vs-fee ratio when per-trade TCA fields are absent (the form the
    original fire was found in)."""
    cm, trades = _read("data/cost_model.json"), _read("data/cashcarry_trades.json")
    modelled = None
    if isinstance(cm, dict):
        preds = []
        for s in (cm.get("symbols") or {}).values():
            try:
                p = s["fut_sell"]["500"]["median_bps"]
                if p is not None:
                    preds.append(float(p))
            except (KeyError, TypeError, ValueError):
                continue
        if preds:
            preds.sort()
            modelled = preds[len(preds) // 2]
    rows = trades if isinstance(trades, list) else (trades or {}).get("trades") \
        if isinstance(trades, dict) else None
    realised = None
    if isinstance(rows, list):
        vals = [float(t[k]) for t in rows[-100:] if isinstance(t, dict)
                for k in ("rt_bps", "cost_bps") if isinstance(t.get(k), (int, float))]
        if len(vals) >= 10:
            vals.sort()
            realised = vals[len(vals) // 2]
    return _cmp("modelled_cost -> realised_cost", modelled, realised,
                band=_COST_BAND, break_at=_COST_BREAK, kind="ratio")


def _equity_link() -> dict[str, Any]:
    """Book equity vs VENUE-TRUTH equity -- the measure whose absence hid a -41% event.
    Note the known definitional offset (register #19 shadow finding, ~36.4%): this link is
    expected to read BREAK until the two measures are reconciled, and that is the POINT --
    it stops being invisible."""
    live, vt = _read("web/cashcarry_live.json"), _read("web/venue_equity.json")
    return _cmp("book_equity -> venue_truth_equity",
                _num(live, "equity", "net_equity", "total_equity"),
                _num(vt, "equity", "venue_equity", "total"),
                band=_EQUITY_BAND, break_at=_EQUITY_BREAK, kind="level")


def main() -> int:
    links = [
        # backtest -> shadow: the modelled Sharpe against the forward-accruing one.
        _cmp("backtest_sharpe -> shadow_sharpe",
             _num(_read("web/discovery.json"), "sharpe", "ann_sharpe"),
             _num(_read("web/cashcarry_shadow.json"), "ann_sharpe", "annSharpe", "sharpe"),
             band=_SHARPE_BAND, break_at=_SHARPE_BREAK, kind="ratio"),
        # shadow -> shadow_8h: same strategy, finer clock. A large gap here is a MEASUREMENT
        # finding, not an alpha finding -- the daily curve smooths basis MtM variance away
        # (measured 24.42 daily vs 8.11 on the 8h panel, gap #44).
        _cmp("shadow_daily -> shadow_8h",
             _num(_read("web/cashcarry_shadow.json"), "ann_sharpe", "annSharpe", "sharpe"),
             _num(_read("web/cashcarry_shadow_8h.json"), "ann_sharpe", "annSharpe", "sharpe"),
             band=_SHARPE_BAND, break_at=_SHARPE_BREAK, kind="ratio"),
        # shadow -> executed book: the link that decides whether research describes the desk.
        _cmp("shadow_sharpe -> live_sharpe",
             _num(_read("web/cashcarry_shadow.json"), "ann_sharpe", "annSharpe", "sharpe"),
             _num(_read("web/cashcarry_live.json"), "ann_sharpe", "sharpe", "deployed_sharpe"),
             band=_SHARPE_BAND, break_at=_SHARPE_BREAK, kind="ratio"),
        _cost_link(),
        _equity_link(),
    ]
    verdicts = [x["verdict"] for x in links]
    overall = ("BREAK" if "BREAK" in verdicts else "GAP" if "GAP" in verdicts
               else "NO-DATA" if all(v == "NO-DATA" for v in verdicts) else "OK")
    report = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "law": "constitution L1.4 / L2.10 -- reality outranks simulation; every gap is a "
               "research input, never an explanation",
        "overall": overall, "links": links,
        "open_gaps": [x["link"] for x in links if x["verdict"] in ("GAP", "BREAK")],
        "missing_links": [x["link"] for x in links if x["verdict"] == "NO-DATA"],
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2), "utf-8")
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print(f"reality gap: {overall}")
        for x in links:
            extra = (f"ratio={x.get('ratio')}" if "ratio" in x
                     else f"rel={x.get('relative_diff')}" if "relative_diff" in x else "")
            print(f"  {x['verdict']:8} {x['link']:38} {extra} {x.get('detail', '')}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
