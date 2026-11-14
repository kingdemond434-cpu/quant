"""COST SURFACE ACCURACY: the modelled entry-hour spread against what the account's fills met.

`research/entry_hour_cost.py` charges every gate and forward clock the spread of the slot a
trade crosses the ask in. A cost model nobody checks against a fill is a guess with a schema, so
this publishes, per symbol, the modelled charge at each fill's own broker (weekday, hour) beside
the spread actually quoted at that fill and the slippage paid:

    realized_spread_pts   (quote_ask - quote_bid) / tick_size at the fill   (fill_corpus)
    modelled_spread_pts   entry_hour_cost.dow_hour_spread_pts(surface, sym, dow, hour)
    ratio                 realized / modelled  -- > 1 means the surface UNDER-charges

Hours in `fill_corpus` are UTC (`filled_at` / `decided_at`, written with +00:00 from the
gateway's own clock); the surface is on the broker clock (NY+7), so each fill is converted with
`libs.regime.session_clock.utc_offset_h` before the lookup. A fill with no quote, no symbol row
or no tick size is counted as UNMEASURED by name; a symbol with no measurable fill is UNMEASURED,
never "accurate".

Writes `desks/mt5/reports/COST_SURFACE_ACCURACY.json`. Hourly leg `cost_surface_accuracy`.

    python desks/mt5/research/cost_surface_accuracy.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parent.parent
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FILL_CORPUS = _DESK / "data" / "fill_corpus.jsonl"
REGISTRY = _DESK / "data" / "universe" / "universe.json"
OUT = _DESK / "reports" / "COST_SURFACE_ACCURACY.json"

#: A symbol needs this many quoted fills before its ratio is called MEASURED.
MIN_FILLS = 3


def _rows(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        return []
    return out


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def broker_slot(ts_utc: Any) -> tuple[int, int] | None:
    """(weekday Monday=0, hour) on the broker clock for a UTC instant, or None."""
    try:
        t = datetime.fromisoformat(str(ts_utc).replace("Z", "+00:00"))
    except ValueError:
        return None
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    from libs.regime.session_clock import utc_offset_h
    b = t.astimezone(UTC) + timedelta(hours=utc_offset_h(t))
    return b.weekday(), b.hour


LIVE_LEDGER = _DESK / "data" / "live_ledger.jsonl"
UNIVERSE_DIR = _DESK / "data" / "universe"


def _m1_quotes_at_deals(reg: dict[str, Any], surface: dict[str, Any] | None,
                        skip: Any) -> dict[str, dict[str, Any]]:
    """Per symbol: Fusion's own M1 quoted spread at each live deal's minute vs the modelled charge.

    The M1 index is the broker clock stored as UTC; deal times are true UTC, so each deal is
    moved onto the broker clock before the minute lookup. Trading-box only (the M1 tape lives
    there); absent bars are UNMEASURED by name.
    """
    import pandas as pd

    from research.entry_hour_cost import dow_hour_spread_pts

    deals: dict[str, list[datetime]] = {}
    for r in _rows(LIVE_LEDGER):
        sym, t = str(r.get("symbol") or ""), r.get("time")
        if not sym or not t:
            continue
        try:
            ts = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        except ValueError:
            continue
        ts = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        from libs.regime.session_clock import utc_offset_h
        deals.setdefault(sym, []).append(ts.astimezone(UTC) + timedelta(hours=utc_offset_h(ts)))
    out: dict[str, dict[str, Any]] = {}
    for sym, stamps in sorted(deals.items()):
        f = UNIVERSE_DIR / f"{sym}_M1.parquet"
        ts_ = _f(((reg or {}).get(sym) or {}).get("tick_size"))
        if not f.exists():
            out[sym] = {"status": "UNMEASURED: no M1 tape on this host", "n_deals": len(stamps)}
            continue
        try:
            df = pd.read_parquet(f, columns=["spread"])
        except (OSError, ValueError, KeyError):
            out[sym] = {"status": "UNMEASURED: M1 tape unreadable", "n_deals": len(stamps)}
            continue
        idx = pd.DatetimeIndex(df.index)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
        by_min = dict(zip((int(x.timestamp()) // 60 for x in idx),
                          df["spread"].astype(float), strict=False))
        real, mod = [], []
        for b in stamps:
            v = by_min.get(int(b.timestamp()) // 60)
            if v is None:
                continue
            m, _ = dow_hour_spread_pts(surface, sym, b.weekday(), b.hour)
            if m is None:
                continue
            real.append(float(v))
            mod.append(float(m))
        if not real:
            out[sym] = {"status": "UNMEASURED: no M1 bar at the deal minutes",
                        "n_deals": len(stamps)}
            continue
        rp, mp = statistics.median(real), statistics.median(mod)
        out[sym] = {"status": "MEASURED" if len(real) >= MIN_FILLS else
                    "UNMEASURED: too few matched deals",
                    "n_deals": len(stamps), "n_matched": len(real),
                    "realized_spread_pts_p50": round(rp, 3),
                    "modelled_spread_pts_p50": round(mp, 3),
                    "realized_over_modelled": round(rp / mp, 3) if mp > 0 else None,
                    "tick_size_known": bool(ts_)}
    return out


def build(*, fills: list[dict[str, Any]] | None = None,
          registry: dict[str, Any] | None = None,
          surface: dict[str, Any] | None = None) -> dict[str, Any]:
    from research.entry_hour_cost import dow_hour_spread_pts, load_surface

    now = datetime.now(UTC)
    fills = _rows(FILL_CORPUS) if fills is None else fills
    if registry is None:
        try:
            registry = json.loads(REGISTRY.read_text("utf-8"))
        except (OSError, ValueError):
            registry = {}
    reg = registry.get("symbols", registry) if isinstance(registry, dict) else {}
    surface = load_surface() if surface is None else surface
    per: dict[str, dict[str, list[float]]] = {}
    skipped: dict[str, int] = {}

    def skip(why: str) -> None:
        skipped[why] = skipped.get(why, 0) + 1

    for r in fills:
        if r.get("rejected") or not r.get("fill_price"):
            continue
        sym = str(r.get("symbol") or "")
        row = reg.get(sym) if isinstance(reg, dict) else None
        ts = _f((row or {}).get("tick_size"))
        bid, ask = _f(r.get("quote_bid")), _f(r.get("quote_ask"))
        when = r.get("filled_at") or r.get("decided_at")
        if not sym or not row or not ts or ts <= 0:
            skip("symbol or tick_size absent from the registry")
            continue
        if bid is None or ask is None or ask < bid:
            skip("no quote at the fill")
            continue
        slot = broker_slot(when)
        if slot is None:
            skip("no fill time")
            continue
        modelled, _info = dow_hour_spread_pts(surface, sym, slot[0], slot[1])
        if modelled is None:
            skip("surface cannot price the symbol")
            continue
        d = per.setdefault(sym, {"realized": [], "modelled": [], "slip": [], "hours": []})
        d["realized"].append((ask - bid) / ts)
        d["modelled"].append(float(modelled))
        d["hours"].append(float(slot[1]))
        slip = _f(r.get("slip_frac"))
        if slip is not None:
            d["slip"].append(slip)

    m1 = _m1_quotes_at_deals(reg, surface, skip)
    symbols: dict[str, Any] = {}
    for sym, d in sorted(per.items()):
        n = len(d["realized"])
        real = statistics.median(d["realized"])
        mod = statistics.median(d["modelled"])
        symbols[sym] = {
            "n_fills": n,
            "status": "MEASURED" if n >= MIN_FILLS else "UNMEASURED: too few quoted fills",
            "realized_spread_pts_p50": round(real, 3),
            "modelled_spread_pts_p50": round(mod, 3),
            "realized_over_modelled": round(real / mod, 3) if mod > 0 else None,
            "slip_frac_p50": (round(statistics.median(d["slip"]), 6) if d["slip"] else None),
            "fill_hours_broker": sorted({int(h) for h in d["hours"]}),
        }
    for sym, block in m1.items():
        symbols.setdefault(sym, {"n_fills": 0, "status": "UNMEASURED: no quoted fills"})
        symbols[sym]["m1_quote_at_deal"] = block
        if (symbols[sym]["status"] != "MEASURED" and block.get("status") == "MEASURED"):
            symbols[sym].update({
                "status": "MEASURED",
                "realized_spread_pts_p50": block["realized_spread_pts_p50"],
                "modelled_spread_pts_p50": block["modelled_spread_pts_p50"],
                "realized_over_modelled": block["realized_over_modelled"],
                "source": "M1 quoted spread at the deal minute (Fusion tape)"})
    measured = [s for s in symbols.values() if s["status"] == "MEASURED"
                and s["realized_over_modelled"] is not None]
    under = sorted((k for k, s in symbols.items() if s["status"] == "MEASURED"
                    and (s["realized_over_modelled"] or 0) > 1.5))
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "status": "MEASURED" if measured else "UNMEASURED: no symbol has enough quoted fills",
        "surface_built_at": (surface or {}).get("built_at"),
        "clock": "fills UTC -> broker (NY+7) via session_clock.utc_offset_h",
        "n_symbols_measured": len(measured),
        "median_realized_over_modelled": (round(statistics.median(
            [s["realized_over_modelled"] for s in measured]), 3) if measured else None),
        "undercharged_symbols": under,
        "skipped": skipped,
        "symbols": symbols,
        "rule": ("ratio = realized quoted spread at the fill / the surface's charge at that "
                 "fill's broker (weekday, hour); > 1.5 is listed as UNDER-charged"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    doc = build()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(out)
    print(f"cost surface accuracy: {doc['status']}  {doc['n_symbols_measured']} symbol(s), "
          f"median realized/modelled {doc['median_realized_over_modelled']}  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
