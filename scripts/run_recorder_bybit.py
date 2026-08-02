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
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import certifi

_R = Path(__file__).resolve().parent.parent
if str(_R) not in sys.path:
    sys.path.insert(0, str(_R))

from libs.ops.disk import PAUSE_FRAC, headroom  # noqa: E402

_BASE = "https://api.bybit.com"
_ROOT = Path(__file__).resolve().parent.parent / "data/moat/bybit"
_HB = Path(__file__).resolve().parent.parent / "data/recorder_bybit_heartbeat"
_CTX = ssl.create_default_context(cafile=certifi.where())

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


def _get(path: str, params: str) -> dict | None:
    try:
        req = urllib.request.Request(f"{_BASE}{path}?{params}",
                                     headers={"User-Agent": "research-recorder/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_CTX) as r:
            d = json.loads(r.read())
        return d if d.get("retCode") == 0 else None
    except Exception:
        return None                                   # a dropped poll is a gap, never a crash


def _write(sym: str, rows: list[dict]) -> None:
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
    buf: dict[str, list[dict]] = {s: [] for s in _SYMBOLS}
    last_trades = 0.0
    last_flush = time.time()
    disk_warned = False

    while True:
        t0 = time.time()
        # DISK GUARD. This recorder shipped WITHOUT one while both Binance recorders had it, and
        # it is the fastest writer on the box -- 20 symbols at 1.5s depth, ~2.7x the others. So
        # the two guarded recorders would have paused at 80% while this one kept writing to a
        # full filesystem, at which point every organ that writes an artifact fails, including
        # the audit that would explain why. The guard is not a courtesy; without it the failure
        # takes the whole desk down rather than one venue's tape.
        if headroom("/")["paused"]:
            if not disk_warned:
                print(f"bybit recorder: DISK >{PAUSE_FRAC:.0%} -- writing paused "
                      "(heartbeat continues, so supervision must read the MARKER not the mtime)")
                disk_warned = True
            # The marker, not silence. A paused recorder keeps a fresh heartbeat, so liveness
            # supervision sees a healthy process -- the state has to be written down or the tape
            # stops with nothing anywhere recording that it did.
            _HB.write_text(f"{time.time()} DISK-PAUSED", "utf-8")
            for s in _SYMBOLS:
                buf[s].clear()          # drop rather than grow unbounded in memory
            time.sleep(30.0)
            continue
        disk_warned = False
        for sym in _SYMBOLS:
            d = _get("/v5/market/orderbook", f"category=linear&symbol={sym}&limit=25")
            if d:
                r = d["result"]
                buf[sym].append({"t": int(time.time() * 1000), "k": "depth",
                                 "b": r.get("b", [])[:25], "a": r.get("a", [])[:25]})
        now = time.time()
        if now - last_trades >= _TRADES_EVERY_S:
            for sym in _SYMBOLS:
                d = _get("/v5/market/recent-trade", f"category=linear&symbol={sym}&limit=200")
                if d:
                    buf[sym].append({"t": int(now * 1000), "k": "trades",
                                     "v": d["result"].get("list", [])})
            f = _get("/v5/market/tickers", "category=linear")
            if f:
                tk = {x["symbol"]: {"fr": x.get("fundingRate"), "oi": x.get("openInterest"),
                                    "mp": x.get("markPrice")}
                      for x in f["result"].get("list", []) if x["symbol"] in _SYMBOLS}
                for sym, v in tk.items():
                    buf[sym].append({"t": int(now * 1000), "k": "meta", **v})
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
