#!/usr/bin/env python3
"""BYBIT FORWARD RECORDER (v1, 2026-07-21) -- second-venue tape, public data only.

WHY NOW, NOT POST-GATE-0: recording is not trading. The Bybit *connector* is Gate-0-gated
because it moves money; the *tape* is public market data and gated by nothing. Cross-venue
basis, funding dispersion, and lead-lag are all calendar-bound datasets -- a day not recorded
is a day that can never be bought back (pre-recorder L2 does not exist free at any venue).
Starting this clock today is the single highest-leverage act available toward deep breadth.

Mirrors run_recorder.py's shape deliberately (same hourly gzip-jsonl layout under
data/moat/bybit/<SYMBOL>/) so downstream loaders treat both venues identically.

Weight discipline: Bybit's public IP limit is ~600 req/5s -- vastly looser than Binance's
weight budget -- but this stays deliberately modest (20 symbols @ 4s depth + 20s trades =
~5 req/s) to leave headroom and be a good citizen. Read-only, keyless, no order paths.
"""
from __future__ import annotations

import gzip
import json
import ssl
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import certifi

_BASE = "https://api.bybit.com"
_ROOT = Path(__file__).resolve().parent.parent / "data/moat/bybit"
_HB = Path(__file__).resolve().parent.parent / "data/recorder_bybit_heartbeat"
_CTX = ssl.create_default_context(cafile=certifi.where())

#: FALLBACK universe only. Kept because a recorder that records NOTHING is the one failure this
#: organ cannot come back from -- an unrecorded day does not exist free at any venue afterwards.
_FALLBACK = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
             "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
             "TRXUSDT", "DOTUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT",
             "UNIUSDT", "APTUSDT", "FILUSDT", "ARBUSDT", "OPUSDT")
_MAX_SYMBOLS = 20                # weight budget: 20 @ 4s depth + 20s trades = ~6 req/s


def _listed_on_bybit(http=None) -> frozenset[str]:
    """What Bybit actually lists. Keyless, one call.

    Without this the traded universe would be copied across venue-blind and every name Bybit
    does not list would burn two requests a cycle forever, returning nothing -- the recorder
    would look busy and record less."""
    try:
        d = (http or _get)("/v5/market/instruments-info", "category=linear&limit=1000")
        rows = ((d or {}).get("result") or {}).get("list") or []
        return frozenset(str(r["symbol"]) for r in rows if r.get("symbol"))
    except (OSError, KeyError, TypeError, ValueError):
        return frozenset()


def _universe(http=None) -> tuple[str, ...]:
    """The SAME priority-ordered universe the Binance recorder derives, filtered to what Bybit
    lists. Gap #39 was closed on run_recorder.py and this second-venue tape kept a hardcoded
    list, so the two recorders drifted apart and this one could intersect the traded book at
    ZERO -- which is the precise defect #39 named, still live on the venue nobody re-checked.

    ORDER IS PRIORITY, same as the twin: benchmark, then held positions, then recently traded,
    then majors. When the cap binds it is the MAJORS that get dropped and the traded names that
    survive, because the whole point of a second-venue tape is cross-venue work on the book the
    desk actually holds.

    FALLS BACK RATHER THAN BLOCKS, and the asymmetry is deliberate. Elsewhere on this desk an
    unknown must block the action; here the "action" is reading public data with no key and no
    money at risk, while the harm of not acting is permanent -- an unrecorded day cannot be
    bought back at any price. So an unreadable universe or an unreachable instrument list keeps
    the fallback and says so loudly, rather than recording nothing while looking healthy."""
    try:
        from scripts.run_recorder import _universe as _binance_universe
        wanted = _binance_universe()
    except Exception as exc:
        print(f"bybit recorder: universe underivable ({type(exc).__name__}: {exc}) -- "
              "FALLBACK list in use; this is a degraded universe, not a healthy one")
        return _FALLBACK
    listed = _listed_on_bybit(http)
    if not listed:
        print("bybit recorder: instruments-info unreachable -- cannot filter to listed symbols; "
              "FALLBACK list in use rather than recording nothing")
        return _FALLBACK
    keep = tuple(s for s in wanted if s in listed)[:_MAX_SYMBOLS]
    if not keep:
        print("bybit recorder: NO derived symbol is listed on bybit -- FALLBACK in use")
        return _FALLBACK
    dropped = [s for s in wanted if s not in listed]
    print(f"bybit recorder universe: {len(keep)} symbols following the traded book"
          + (f"; {len(dropped)} not listed on bybit ({', '.join(dropped[:6])})" if dropped else ""))
    return keep


_DEPTH_EVERY_S = 4.0
_TRADES_EVERY_S = 20.0
_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
            "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
            "TRXUSDT", "DOTUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT",
            "UNIUSDT", "APTUSDT", "FILUSDT", "ARBUSDT", "OPUSDT")
# SAMPLING RESOLUTION. Was depth@4.0s / trades@20.0s = 6.0 req/s against a self-imposed cap of
# 20.0 -- i.e. the recorder ran at 30% of its OWN conservative limit, and that limit is itself
# far under what the venue allows. The moat is the desk's only unreplicable asset and every
# unrecorded moment is permanently unavailable, so unused headroom here is the one ceiling whose
# cost is irreversible: it cannot be bought back later at any price.
#
# depth@1.5s + trades@10s over 20 symbols = 20/1.5 + 20/10 = 15.3 req/s, still inside the cap
# with margin. That is 2.7x the depth resolution -- microstructure withdrawal happens on second
# scales, so this is resolution the M_LIQUIDITY_WITHDRAWAL mechanism can actually use.
# _assert_rate_budget() below still enforces the cap, so this cannot silently exceed it.
_DEPTH_EVERY_S = 1.5
_TRADES_EVERY_S = 10.0
_REQ_PER_S_CAP = 20.0            # bybit allows far more; stay modest and neighbourly


def _assert_rate_budget() -> None:
    rps = len(_SYMBOLS) / _DEPTH_EVERY_S + len(_SYMBOLS) / _TRADES_EVERY_S
    print(f"bybit recorder budget: {rps:.1f} req/s (cap {_REQ_PER_S_CAP}) | "
          f"{len(_SYMBOLS)} symbols depth@{_DEPTH_EVERY_S}s trades@{_TRADES_EVERY_S}s")
    if rps > _REQ_PER_S_CAP:
        raise SystemExit(f"REFUSING TO START: {rps:.1f} req/s over self-imposed cap "
                         f"{_REQ_PER_S_CAP}. Widen intervals or cut symbols. "
                         "(Binance lesson 2026-07-21: silent venue cutoff after 6h.)")


def _get(path: str, params: str) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(f"{_BASE}{path}?{params}",
                                     headers={"User-Agent": "research-recorder/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_CTX) as r:
            d = json.loads(r.read())
        return d if d.get("retCode") == 0 else None
    except Exception:
        return None                                   # a dropped poll is a gap, never a crash


#: Derived AFTER _get exists -- the universe call needs the HTTP helper, and a module-level
#: assignment above it raised NameError at import: the recorder would not start at all.
_SYMBOLS = _universe()


def _write(sym: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    hour = datetime.now(tz=UTC).strftime("%Y%m%d_%H")
    out = _ROOT / sym
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / f"{hour}.jsonl.gz", "at", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def main() -> None:
    _assert_rate_budget()
    _ROOT.mkdir(parents=True, exist_ok=True)
    print(f"bybit recorder v1 -> {_ROOT}/")
    buf: dict[str, list[dict[str, Any]]] = {s: [] for s in _SYMBOLS}
    last_trades = 0.0
    last_flush = time.time()

    while True:
        t0 = time.time()
        for sym in _SYMBOLS:
            d = _get("/v5/market/orderbook", f"category=linear&symbol={sym}&limit=25")
            if d:
                r = d["result"]
                # L1.46: until now a Bybit depth row carried NO venue identifier of any kind --
                # no time, no sequence -- so it could not be joined to the free first-party Bybit
                # archive (200 levels / 100ms / 345d) and a dropped poll was indistinguishable
                # from a quiet book. "vt" is result.ts (the venue's stamp, renamed to avoid
                # colliding with our `t`), "u"/"sq" are the update id and sequence.
                buf[sym].append({"t": int(time.time() * 1000), "k": "depth", "c": "recv",
                                 "vt": r.get("ts"), "u": r.get("u"), "sq": r.get("seq"),
                                 "b": r.get("b", [])[:25], "a": r.get("a", [])[:25]})
        now = time.time()
        if now - last_trades >= _TRADES_EVERY_S:
            for sym in _SYMBOLS:
                d = _get("/v5/market/recent-trade", f"category=linear&symbol={sym}&limit=200")
                if d:
                    # L1.46: stamp each batch at ITS OWN receipt, not at `now`. `now` is captured
                    # once above, before this 20-symbol serial loop, so every symbol after the
                    # first carried a receipt stamp EARLIER than the moment we received it -- a
                    # look-ahead in our own receipt axis, and the same defect class as the R0060
                    # leaky Upbit copies. Measured on the archive before this fix: 32.8% of
                    # 877,314 batches had a receipt stamp PRECEDING the newest trade in them.
                    buf[sym].append({"t": int(time.time() * 1000), "k": "trades", "c": "recv",
                                     "v": d["result"].get("list", [])})
            f = _get("/v5/market/tickers", "category=linear")
            # L1.46: one call serves every symbol, so a shared stamp is correct here -- but it
            # must be the receipt of THAT call, not the pre-loop `now` from ~20 requests ago.
            meta_recv = int(time.time() * 1000)
            if f:
                tk = {x["symbol"]: {"fr": x.get("fundingRate"), "oi": x.get("openInterest"),
                                    "mp": x.get("markPrice")}
                      for x in f["result"].get("list", []) if x["symbol"] in _SYMBOLS}
                for sym, v in tk.items():
                    buf[sym].append({"t": meta_recv, "k": "meta", "c": "recv", **v})
            last_trades = now

        if now - last_flush >= 60:
            for sym in _SYMBOLS:
                _write(sym, buf[sym])
                buf[sym] = []
            _HB.write_text(f"{time.time()}", "utf-8")
            last_flush = now

        time.sleep(max(0.0, _DEPTH_EVERY_S - (time.time() - t0)))


if __name__ == "__main__":
    main()
