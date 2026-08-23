#!/usr/bin/env python3
"""RETIRED, GENUINELY VENUE-SPECIFIC (2026-08-23): a fact about one crypto exchange's own archive
retention policy, with no MT5/Fusion equivalent question to ask. Kept in the repo per standing
instruction, but never wire this into any live schedule again.

IS THE FREE BYBIT L2 ARCHIVE ON ROLLING RETENTION? -- R0243's T7, as a standing instrument.

WHAT IS AT STAKE. quote-saver.bycsi.com is Bybit's own publication of its own L2 book at 200
levels / 100ms / 24h per file -- 8x the depth and 41x the resolution of the desk's own recorder,
and it refutes this desk's headline "irreplaceable Bybit L2" claim outright: our copy is a
strictly-worse subsample of a free file. The 2026-08-01 data-moat sweep measured the earliest
available BTCUSDT date at 2025-08-21 and INFERRED -- explicitly, in the doc -- that retention might
be ROLLING, in which case every day of delay destroys a day of free history permanently. That
inference set the row's whole urgency, and nothing ever tested it.

A DUTY WITH NO INSTRUMENT IS A WISH. The row's own remedy was "run three HEAD probes on
2026-08-08" -- a diary entry, which is what the desk keeps paying for. This is the probe as a
committed, scheduled organ that RECORDS its boundary and FAILS LOUD when the boundary advances,
so the rolling-vs-fixed question is answered continuously by the artifact instead of annually by
whoever remembers.

THE MEASUREMENT IS A BISECTION, NOT A GUESS. HEAD is enough -- the archive answers 200/404 on
existence without transferring the 149 MiB body -- so a full boundary costs ~9 requests per
symbol. The window is bisected between a known-absent and a known-present date, and the result is
the FIRST date that exists.

WHAT ADVANCE MEANS, AND WHY BOTH ANSWERS MATTER:
  * boundary ADVANCED since the last recorded run -> retention is ROLLING. Free history is
    expiring, the acquisition is time-critical, and this exits non-zero to say so.
  * boundary UNMOVED while the recent end grows -> retention is FIXED and the span is GROWING.
    The archive is not expiring; the urgency the row was built on is refuted and the ingest can be
    sequenced behind higher-ERV work without losing anything. A refutation that WITHDRAWS a
    deadline is worth exactly as much as one that creates it.

DEGRADE DIRECTION. A network failure is UNREACHABLE, never "boundary unmoved" -- the desk has
already recorded a verdict about the HOST being read as a verdict about the WORLD. UNREACHABLE
does not overwrite the stored boundary and does not fail the fence, because a probe that cannot
see is not evidence that nothing changed.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "data/bybit_archive_retention.json"
_URL = ("https://quote-saver.bycsi.com/orderbook/linear/{sym}/"
        "{d}_{sym}_ob200.data.zip")

#: Widest plausible window. The bisection needs an outer bound that is certainly absent; two years
#: back is safely outside any retention this archive has ever shown.
_LOOKBACK_DAYS = 730

#: §13 legitimacy, recorded where the fetcher lives rather than in a doc nobody re-reads: this is
#: Bybit's FIRST-PARTY publication of its OWN market data, served openly over HTTPS with no
#: authentication, no paywall and no scrape of a third party's aggregation. HEAD-only here; the
#: bulk fetch is a separate, rate-limited organ.
_TIMEOUT_S = 25.0
_UA = "quant-desk-archive-probe/1.0"


def _exists(symbol: str, d: date, *, timeout: float = _TIMEOUT_S) -> bool | None:
    """True/False for a day's file; None when the network could not answer.

    None is a THIRD state on purpose. Folding an unreachable host into False would move the
    measured boundary forward and report ROLLING RETENTION on a wifi drop -- a false alarm on the
    one signal this organ exists to raise.
    """
    req = urllib.request.Request(
        _URL.format(sym=symbol, d=d.isoformat()), method="HEAD",
        headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 300
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        return None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def earliest_available(symbol: str, *, today: date, lookback: int = _LOOKBACK_DAYS,
                       probe=_exists) -> tuple[date | None, int]:
    """Bisect the first date whose file exists. Returns (boundary, n_requests).

    ``boundary`` is None when the archive could not be read at all, or when even the oldest probed
    date exists -- which would mean retention extends past the lookback and the window is too
    narrow to bound it. Both are reported rather than guessed at.
    """
    n = 0
    # `hi` must EXIST for the bisection to be well-posed. The archive publishes T+1 (measured:
    # last-modified 00:03 UTC for the prior day), so start at T-1 and walk back a few days rather
    # than assuming a lag.
    hi = None
    for back in range(1, 8):
        cand = today - timedelta(days=back)
        n += 1
        got = probe(symbol, cand)
        if got is None:
            return None, n
        if got:
            hi = cand
            break
    if hi is None:
        return None, n

    lo = today - timedelta(days=lookback)
    n += 1
    got = probe(symbol, lo)
    if got is None:
        return None, n
    if got:
        return None, n          # retention exceeds the lookback -- unbounded by this window

    # invariant: lo does NOT exist, hi DOES. Converge on the first existing date.
    while (hi - lo).days > 1:
        mid = lo + timedelta(days=(hi - lo).days // 2)
        n += 1
        got = probe(symbol, mid)
        if got is None:
            return None, n
        if got:
            hi = mid
        else:
            lo = mid
    return hi, n


def build_report(root: Path, symbols: list[str], *, today: date, probe=_exists) -> dict:
    prior = {}
    p = root / "data/bybit_archive_retention.json"
    if p.exists():
        try:
            prior = json.loads(p.read_text("utf-8")).get("symbols", {})
        except (OSError, ValueError):
            prior = {}

    out: dict[str, dict] = {}
    advanced, unreachable = [], []
    for sym in symbols:
        boundary, n = earliest_available(sym, today=today, probe=probe)
        was = (prior.get(sym) or {}).get("earliest")
        if boundary is None:
            unreachable.append(sym)
            # THE STORED BOUNDARY SURVIVES AN UNREADABLE PROBE. Overwriting it with a null would
            # destroy the only baseline the advance test has.
            out[sym] = {"earliest": was, "status": "UNREACHABLE", "probes": n,
                        "first_seen": (prior.get(sym) or {}).get("first_seen")}
            continue
        moved = bool(was and boundary.isoformat() > was)
        if moved:
            advanced.append(f"{sym} {was}->{boundary.isoformat()}")
        out[sym] = {
            "earliest": boundary.isoformat(),
            "span_days": (today - boundary).days,
            "status": "ADVANCED" if moved else ("BASELINE" if not was else "UNMOVED"),
            "previous_earliest": was,
            "first_seen": (prior.get(sym) or {}).get("first_seen") or today.isoformat(),
            "probes": n,
        }

    measured = [v for v in out.values() if v["status"] != "UNREACHABLE"]
    if advanced:
        status, detail = "ROLLING", (
            f"the earliest available date ADVANCED on {len(advanced)} symbol(s): "
            f"{'; '.join(advanced)}. Free history is EXPIRING -- every day of delay destroys a "
            f"day permanently, and the ingest is now time-critical.")
    elif not measured:
        status, detail = "UNREACHABLE", (
            f"could not read the archive for any of {len(symbols)} symbol(s) -- a verdict about "
            f"this host, NOT about the archive. The stored boundaries are unchanged.")
    elif any(v["status"] == "UNMOVED" for v in measured):
        span = max(v["span_days"] for v in measured)
        status, detail = "FIXED", (
            f"the earliest available date has NOT moved since the last run; the span has GROWN to "
            f"{span} days from the recent end. Retention is a FIXED floor, not a rolling window, "
            f"so the 2026-08-01 sweep's rolling-retention inference is REFUTED and the ingest "
            f"carries no expiry deadline.")
    else:
        span = max(v["span_days"] for v in measured)
        status, detail = "BASELINE", (
            f"first run -- boundaries recorded for {len(measured)} symbol(s), widest span {span} "
            f"days. Rolling vs fixed is UNDECIDABLE from one observation and is not claimed; the "
            f"next run decides it.")

    return {"generated": datetime.now(tz=UTC).isoformat(), "as_of": today.isoformat(),
            "source": "quote-saver.bycsi.com (Bybit first-party, unauthenticated HTTPS)",
            "status": status, "detail": detail,
            "n_unreachable": len(unreachable), "symbols": out}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()]
    rep = build_report(_ROOT, syms, today=datetime.now(tz=UTC).date())
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"bybit archive retention: {rep['status']} -- {rep['detail']}")
        for sym, v in rep["symbols"].items():
            print(f"  {sym}: earliest={v['earliest']} status={v['status']} probes={v['probes']}")
        print(f"-> {_OUT}")
    # ROLLING is the only failure: it means free history is expiring while the desk waits.
    # UNREACHABLE does NOT fail -- a probe that cannot see is not evidence of a change, and a
    # fence that goes red on every network blip gets switched off (L1.43).
    return 2 if rep["status"] == "ROLLING" else 0


if __name__ == "__main__":
    raise SystemExit(main())
