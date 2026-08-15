#!/usr/bin/env python3
"""Fetch BTC PRODUCER ECONOMICS -- hashprice and difficulty. The last starved input.

WHY THIS EXISTS

`_producer_margin_stress` is registered, wired, and reads `MarketSeries.hashprice`. The adapter
attaches that field when the frame carries the column. NOTHING PUT THE COLUMN THERE. So the
generator returns `np.zeros(len(s))` on every symbol, every cycle -- a mechanism that is correct,
scheduled, and silent. That is the third time this shape has appeared on this desk (the rho tracker
with no writer, the MarketSeries fields with no populator, this), and it is the most expensive kind
of defect because a starved component is indistinguishable from an early one.

`treasury_cost_base_liquidation` scores 0.70 orthogonality against a library that is otherwise
eleven rules across three census classes. It is the single best diversification available, and it
was blocked on data that is free.

WHAT HASHPRICE IS, AND THE ARITHMETIC

    hashprice ($/PH/day) = miner_revenue ($/day) / network_hashrate (PH/s)

Revenue is subsidy + fees, already denominated in dollars by the source, so the BTC price is
inside it. That is correct for this mechanism: the miner's obligations are fiat and their revenue
is coin, and hashprice is exactly the ratio those two meet at. When it falls, either coin fell or
competition rose, and both squeeze the same margin.

Difficulty is carried RAW. It is the second leg of the signal and it is a step function -- it holds
its level until the next retarget -- which is precisely why the generator compares it to its recent
peak rather than bar-to-bar.

WHAT IT REFUSES TO DO

Fabricate, interpolate, or forward-fill across a gap. A day the source did not publish is ABSENT.
The generator degrades to flat without producer data by design; a synthesised hashprice would
invent the compelled seller the whole claim rests on, and a mechanism whose payer is imaginary is
a price pattern wearing an economic story.

It also refuses a series whose UNIT changes mid-history. A source that switches from TH/s to H/s at
some date puts a 1000x step in the middle of the data, and a step in the denominator is a fake
regime change in hashprice -- the exact signal this generator trades. See `_to_ph` below for why
the unit check is about that discontinuity and NOT about the level.

    python scripts/fetch_producer_economics.py                 # 5 years, merge into existing
    python scripts/fetch_producer_economics.py --years 8
    python scripts/fetch_producer_economics.py --check         # read back and audit, no network
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import json
import statistics
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

_OUT = _ROOT / "data" / "producer_economics.json"

#: Free, no key, no account. Daily resolution, full history.
_BASE = "https://api.blockchain.info/charts"
_CHARTS = {
    "hashrate": "hash-rate",        # network hashrate, units vary -- see _to_ph
    "revenue": "miners-revenue",    # USD/day, subsidy + fees
    "difficulty": "difficulty",     # raw network difficulty
}

#: Symbols whose producer economics these ARE. Miners of BTC sell BTC; the compelled flow lands in
#: the BTC book and nowhere else. Attaching this series to an alt would assert a forced seller that
#: does not exist in that market.
BTC_SYMBOLS = ("BTCUSDT", "BTCUSD", "BTCUSDC", "XBTUSD")

#: Plausible band for BTC network hashrate in PH/s: 10 EH/s to 10,000 EH/s. Deliberately spans
#: only three decades, because the unit scales are 1000x apart -- a wider band would let two units
#: match the same number and the choice between them would be arbitrary. The median is taken over
#: RECENT data so early history (2013 was well under 1 EH/s) does not drag it out of band.
_PH_BAND = (1e4, 1e7)
_SCALES = {"H/s": 1e-15, "KH/s": 1e-12, "MH/s": 1e-9,
           "GH/s": 1e-6, "TH/s": 1e-3, "PH/s": 1.0, "EH/s": 1e3}


def _get(url: str, timeout: int) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-desk/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 -- fixed https host
        return json.loads(r.read().decode("utf-8"))


def fetch_chart(name: str, years: int, *, timeout: int = 60) -> dict[str, float]:
    """One blockchain.info chart as {YYYY-MM-DD: value}. Raises on anything unexpected."""
    url = f"{_BASE}/{_CHARTS[name]}?timespan={years}years&format=json&sampled=false"
    doc = _get(url, timeout)
    vals = doc.get("values") if isinstance(doc, dict) else None
    if not isinstance(vals, list) or not vals:
        raise ValueError(f"{name}: no 'values' array in response")
    out: dict[str, float] = {}
    for row in vals:
        try:
            x, y = row["x"], float(row["y"])
        except (TypeError, KeyError, ValueError):
            continue
        if y <= 0:
            continue                      # a zero hashrate or zero revenue is a source gap
        out[datetime.fromtimestamp(int(x), tz=UTC).date().isoformat()] = y
    if not out:
        raise ValueError(f"{name}: response parsed but produced no usable points")
    return out


def _to_ph(series: dict[str, float]) -> tuple[dict[str, float], str]:
    """Normalise network hashrate to PH/s, and REFUSE a series whose unit changes mid-history.

    THE LEVEL CHECK IS COSMETIC AND THE DISCONTINUITY CHECK IS NOT, which is worth stating plainly
    rather than dressing both up as safety. The generator z-scores hashprice over a rolling window,
    and a z-score is invariant under multiplication -- so a uniform 1000x unit error changes the
    signal by exactly nothing. Picking the right scale is for the human reading the number.

    A unit that CHANGES partway through is a different animal entirely. It puts a 1000x step in the
    denominator of hashprice, which reads as the deepest margin compression in recorded history on
    the day the source changed its mind, and the generator would short it. That is a fabricated
    regime, so it is refused rather than rescaled.
    """
    if not series:
        return {}, "empty"
    ordered = [series[k] for k in sorted(series)]
    recent = ordered[-90:] if len(ordered) >= 90 else ordered
    med = statistics.median(recent)

    # Every match is collected rather than taking the first, so an AMBIGUOUS reading is refused
    # instead of resolved by dict order. A silent arbitrary choice between two units is worse than
    # a stop, because it looks like a decision.
    hits = [u for u, f in _SCALES.items() if _PH_BAND[0] <= med * f <= _PH_BAND[1]]
    if len(hits) != 1:
        raise ValueError(
            f"hashrate median {med:.3g} matches {hits or 'no'} plausible unit(s); refusing to "
            "guess. Check the source's units before trusting anything downstream.")
    unit = hits[0]

    # Discontinuity scan on the RAW series. Ratios are unit-free, so this runs before scaling.
    for i in range(1, len(ordered)):
        prev, cur = ordered[i - 1], ordered[i]
        if prev > 0 and (cur / prev > 100.0 or prev / cur > 100.0):
            raise ValueError(
                f"hashrate jumps {prev:.3g} -> {cur:.3g} between consecutive days. That is a unit "
                "change or a corrupt point, not a network event -- BTC hashrate cannot move 100x "
                "in a day. Refusing: this step would read as the deepest margin compression on "
                "record and the generator would short it.")

    f = _SCALES[unit]
    return {k: v * f for k, v in series.items()}, unit


def build(years: int, *, timeout: int = 60) -> tuple[dict[str, dict[str, float]], list[str]]:
    """{date: {hashprice, difficulty}} plus a note per source. Intersects; never interpolates."""
    notes: list[str] = []
    raw: dict[str, dict[str, float]] = {}
    for name in _CHARTS:
        try:
            raw[name] = fetch_chart(name, years, timeout=timeout)
            notes.append(f"{name}: {len(raw[name])} day(s)")
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
            notes.append(f"{name}: FAILED ({type(exc).__name__}: {exc})")

    if "hashrate" not in raw or "revenue" not in raw:
        notes.append("hashprice needs BOTH hashrate and revenue; not computed")
        return ({d: {"difficulty": v} for d, v in raw.get("difficulty", {}).items()}, notes)

    hr, unit = _to_ph(raw["hashrate"])
    notes.append(f"hashrate unit detected: {unit} -> PH/s")

    rev = raw["revenue"]
    diff = raw.get("difficulty", {})

    out: dict[str, dict[str, float]] = {}
    # INTERSECT on hashrate and revenue. A day with one and not the other has no hashprice, and
    # carrying the last known value forward would state a margin that was never observed.
    for day in sorted(set(hr) & set(rev)):
        h = hr[day]
        if h <= 0:
            continue
        row = {"hashprice": round(rev[day] / h, 8)}
        if day in diff:                   # difficulty is independent; present when published
            row["difficulty"] = float(diff[day])
        out[day] = row
    skipped = len(set(hr) ^ set(rev))
    if skipped:
        notes.append(f"{skipped} day(s) had hashrate or revenue but not both -- left ABSENT")
    return out, notes


def merge(new: dict[str, dict[str, float]], out: Path) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "what": "BTC producer economics. hashprice = USD per PH/s per day (miner revenue divided "
                "by network hashrate); difficulty raw. Feeds _producer_margin_stress / "
                "treasury_cost_base_liquidation.",
        "source": "blockchain.info charts (free, no key)",
        "absent_policy": "a day the source did not publish is ABSENT, never interpolated or "
                         "forward-filled: a synthesised hashprice invents the compelled seller "
                         "the mechanism's entire claim rests on.",
        "symbols": list(BTC_SYMBOLS),
        "series": {},
    }
    if out.exists():
        try:
            existing = json.loads(out.read_text("utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("series"), dict):
                doc["series"] = existing["series"]
        except (OSError, ValueError):
            pass                          # a corrupt file is replaced, not appended to blindly
    doc["series"].update(new)
    doc["updated"] = datetime.now(tz=UTC).isoformat()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=False), "utf-8")
    return doc


def audit(path: Path) -> int:
    """Read back what is on disk and say whether the generator can actually use it."""
    if not path.exists():
        print(f"ABSENT: {path}\n  Run without --check to fetch.")
        return 1
    doc = json.loads(path.read_text("utf-8"))
    series = doc.get("series", {})
    if not series:
        print("EMPTY: file exists with no series. The generator will return flat.")
        return 1
    days = sorted(series)
    hp = [series[d]["hashprice"] for d in days if "hashprice" in series[d]]
    df = [d for d in days if "difficulty" in series[d]]
    print(f"PRODUCER ECONOMICS  {path}")
    print(f"  {len(days)} day(s)   {days[0]} -> {days[-1]}")
    print(f"  hashprice   {len(hp)} point(s)   "
          f"latest {hp[-1]:.2f} $/PH/day   min {min(hp):.2f}   max {max(hp):.2f}")
    print(f"  difficulty  {len(df)} point(s)")
    # The generator needs window+1; default window is 90.
    ok = len(hp) > 91
    print(f"\n  generator needs > 91 hashprice days for its 90-bar z-score: "
          f"{'OK' if ok else 'NOT YET'}")
    if not df:
        print("  NO DIFFICULTY -- the compression leg (short) works, the capitulation leg (long)\n"
              "  cannot fire. Difficulty is what makes the exit observable rather than guessed.")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--out", default=str(_OUT))
    ap.add_argument("--check", action="store_true", help="audit what is on disk; no network")
    a = ap.parse_args()

    if a.check:
        return audit(Path(a.out))

    rows, notes = build(a.years, timeout=a.timeout)
    print("SOURCES")
    for n in notes:
        print(f"  {n}")
    if not rows:
        print("\nNothing fetched. Nothing written -- an empty file would leave the generator\n"
              "starved while looking provisioned, which is the defect this script exists to end.")
        return 1

    merge(rows, Path(a.out))
    print()
    return audit(Path(a.out))


if __name__ == "__main__":
    raise SystemExit(main())
