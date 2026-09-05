"""Always-on liquidation listener -> data/liquidations.parquet.

SOURCE: Bybit public `allLiquidation` stream (wss://stream.bybit.com/v5/public/linear), NOT Binance.
Verified 2026-07-09: Binance's mainnet fstream.binance.com WS completes the handshake (HTTP 101) but
delivers ZERO data frames from this network/location on ANY stream (tested on the highest-frequency
BTCUSDT aggTrade feed for 150s+, with and without permessage-deflate) -- a silent geo/network block,
not a code bug (REST to fapi.binance.com works fine; Binance TESTNET WS works fine; a generic echo
WS works fine). There is no Binance REST liquidation history to fall back to. Bybit's public linear
stream was verified reachable (subscribe ack + protocol round-trip) from this same network, so it
replaces Binance as the source. Economically still the same mechanism (forced-liquidation overshoot
mean-reversion) on a large, liquid derivatives venue -- not identical flow to Binance, but real and
free. See docs/institutional_knowledge.md for the diagnostic trail.

No REST history exists for liquidations on any major venue, so we accumulate our own forward archive
-- the raw input for the liquidation-reversal sleeve. Public stream, no API keys. Writes a heartbeat
every loop tick so the watchdog can resurrect it. Reconnects + re-subscribes automatically. Bybit
requires an application-level ping every <=20s or it drops the connection after 10 min idle.

    python scripts/liquidation_listener.py
"""

from __future__ import annotations

# PARK BEFORE THE HEAVY IMPORTS (2026-09-03). This module's stack is the expensive part: checking
# the kill switch after importing it means a switched-OFF unit still holds every library resident.
# Guarded by __main__ so importing this module (tests, tools) never parks -- only a real run does.
if __name__ == "__main__":  # pragma: no cover - process entry, not importable behaviour
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.insert(0, str(_P(__file__).resolve().parent))
    from recorder_switch import park_before_imports as _park

    _park('liquidation_listener')


import asyncio
import contextlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import websockets

_OUT = Path("data/liquidations.parquet")
_HB = Path("data/liquidation_heartbeat")
_SINCE = Path("data/liquidation_since")          # clock starts on connect, not on first event
_STATUS = Path("data/liquidation_status.json")   # the SECOND signal: a payload reached disk
_URL = "wss://stream.bybit.com/v5/public/linear"
_SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
    "SUIUSDT", "1000PEPEUSDT", "WLDUSDT", "NEARUSDT", "UNIUSDT",
)
_COLS = ["ts", "symbol", "side", "qty", "price", "notional"]
_BUF: list[dict[str, object]] = []
_PING_EVERY_S = 15


def _ensure_archive() -> None:
    """Create the archive + 'listening since' stamp on connect so the clock starts immediately and
    the dashboard shows 'LISTENING (0 events)' rather than MISSING while the market is quiet."""
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    if not _OUT.exists():
        pd.DataFrame({c: pd.Series([], dtype="float64" if c in ("qty", "price", "notional")
                                   else "object") for c in _COLS}).to_parquet(_OUT)
    if not _SINCE.exists():
        _SINCE.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")


def _flush() -> None:
    """Append the buffer to the archive. THE BUFFER IS CLEARED ONLY AFTER A DURABLE WRITE.

    RESTORED 2026-08-26 from commit 31a4969b, where it was written and then LOST -- the tests in
    tests/data/test_liquidation_flush_durability.py survived the merge and this implementation
    did not, which is the desk's kept-tests-dropped-code class. It was invisible because a
    SyntaxError elsewhere in this module (`_switch_wait` lost its `async`) made all four tests
    ERROR on import rather than FAIL on behaviour, and ruff/mypy/pytest --co all pass on that
    file: `await` outside `async` is caught in CPython's symbol-table pass, not the parser.

    THIS FUNCTION DESTROYED ~40 DAYS OF LIQUIDATIONS AND REPORTED A FRESH HEARTBEAT THROUGHOUT.
    The original cleared `_BUF` on line 2 and read the previous archive on line 4. A corrupt
    archive makes `read_parquet` raise, so every 60s the buffer was emptied, the read threw, the
    connection was torn down and re-established, and the events in hand were gone -- while
    `_HB.write_text` on the tick loop kept the watchdog perfectly green. That is the desk's
    single most-repeated lesson arriving verbatim: A HEARTBEAT PROVES THE LOOP IS ALIVE, NEVER
    THAT THE PIPE IS.

    HOW THE ARCHIVE BECAME CORRUPT, which is the half that must not recur: `to_parquet(_OUT)`
    wrote IN PLACE over the live file. A kill mid-write (the OOM killer is active on this box)
    truncates it before the footer, and parquet cannot be read without its footer -- so ONE
    interrupted write poisons the archive PERMANENTLY, and every later flush then destroys its
    own buffer against it. Measured on the corpse: opening magic `PAR1` present, closing magic
    absent, one `PAR1` occurrence in 465,580 bytes -- unrecoverable, and liquidations have no
    REST history on any venue to re-fetch from (see this module's own header).

    THREE CHANGES, EACH CLOSING ONE LINK: (1) the write is ATOMIC -- a temp file plus `replace`,
    so a kill damages only the temp and the archive is always a complete file; (2) `_BUF.clear()`
    moves AFTER the bytes are durable, so a failure anywhere retries on the next tick instead of
    discarding; (3) an unreadable archive is QUARANTINED rather than silently overwritten -- the
    corpse is evidence, and the buffer is never destroyed to protect it.
    """
    if not _BUF:
        return
    snap = pd.DataFrame(_BUF)
    prev: pd.DataFrame | None = None
    if _OUT.exists():
        try:
            prev = pd.read_parquet(_OUT)
        except Exception as e:  # ANY unreadable archive, not just ArrowInvalid
            # Unreadable archive. Preserve the corpse under a dated name and carry on with a
            # fresh one -- the alternative is overwriting evidence, and the alternative the
            # ORIGINAL took was throwing away live events to protect a file it could not read.
            quar = _OUT.with_name(f"{_OUT.stem}.corrupt-{int(time.time())}{_OUT.suffix}")
            with contextlib.suppress(OSError):
                _OUT.rename(quar)
            _STATUS.write_text(json.dumps({
                "archive_status": "QUARANTINED-CORRUPT",
                "quarantined_to": quar.name,
                "error": f"{type(e).__name__}: {e}"[:300],
                "at": datetime.now(tz=UTC).isoformat(),
                "note": "archive unreadable; a fresh one starts now. Prior span is LOST -- "
                        "liquidations have no REST backfill on any venue.",
            }, indent=2), "utf-8")
            prev = None
    if prev is not None and len(prev):
        snap = pd.concat([prev, snap], ignore_index=True)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = _OUT.with_name(f"{_OUT.name}.tmp")
    snap.to_parquet(tmp)          # a kill here damages only the temp file
    tmp.replace(_OUT)             # atomic on POSIX: the archive is never partially written
    n = len(_BUF)
    _BUF.clear()                  # ONLY after the bytes are durable
    # THE SECOND SIGNAL (desk lesson #1). A heartbeat says the loop ticked; this says a real
    # payload reached disk. A blocked pipe and a quiet market are indistinguishable without it,
    # and they were indistinguishable here for 41 days.
    _STATUS.write_text(json.dumps({
        "archive_status": "OK",
        "last_payload_utc": datetime.now(tz=UTC).isoformat(),
        "rows_this_flush": n,
        "rows_total": len(snap),
    }, indent=2), "utf-8")


async def _pinger(ws: websockets.ClientConnection) -> None:
    while True:
        await asyncio.sleep(_PING_EVERY_S)
        await ws.send(json.dumps({"op": "ping"}))


async def _run() -> None:
    async with websockets.connect(_URL, open_timeout=10) as ws:
        args = [f"allLiquidation.{s}" for s in _SYMBOLS]
        await ws.send(json.dumps({"op": "subscribe", "args": args}))
        last_flush = time.time()
        _HB.parent.mkdir(parents=True, exist_ok=True)
        _ensure_archive()                              # clock + empty archive start on connect
        _HB.write_text(str(time.time()), "utf-8")      # liveness immediately on connect
        ping_task = asyncio.create_task(_pinger(ws))
        try:
            while True:
                try:                                   # short timeout so the heartbeat stays fresh
                    msg = await asyncio.wait_for(ws.recv(), timeout=20)
                    d = json.loads(msg)
                    if str(d.get("topic", "")).startswith("allLiquidation"):
                        for o in d.get("data", []):
                            qty = float(o.get("v", 0) or 0)
                            px = float(o.get("p", 0) or 0)
                            ts_ms = o.get("T")
                            ts = (datetime.fromtimestamp(ts_ms / 1000, tz=UTC) if ts_ms
                                  else datetime.now(tz=UTC))
                            _BUF.append({"ts": ts, "symbol": o.get("s"), "side": o.get("S"),
                                         "qty": qty, "price": px, "notional": round(qty * px, 2)})
                except TimeoutError:
                    pass                               # quiet market -- no liquidation this window
                _HB.write_text(str(time.time()), "utf-8")  # liveness even with no events
                if time.time() - last_flush > 60:
                    _flush()
                    last_flush = time.time()
        finally:
            ping_task.cancel()




async def _switch_wait(label: str) -> None:
    """Pause while data/RECORDERS_OFF exists. See scripts/run_recorder_bybit.py._switch_wait.

    Same switch as the three L2 recorders, spelled `async` because this listener owns an event
    loop: the blocking `time.sleep` used there would hold the loop shut rather than idle it.
    Deliberately does NOT exit -- quant-liquidations.service is Restart=always and the `quant`
    user has no sudo, so an exit trades a full disk for a full journal every ten seconds.

    Added 2026-08-25 under the MT5 UNIVERSE MANDATE: this listener hunts a crypto-exchange
    universe (Bybit linear), which the mandate forbids outright, and it was the last crypto
    collector with no non-root off switch.
    """
    flag = Path(__file__).resolve().parent.parent / "data" / "RECORDERS_OFF"
    if not flag.exists():
        return
    print(f"{label}: data/RECORDERS_OFF present -- collection paused (not exiting;"
          " systemd would restart an exit). Remove the file to resume.", flush=True)
    while flag.exists():
        await asyncio.sleep(30)
    print(f"{label}: RECORDERS_OFF cleared -- resuming", flush=True)


async def _main() -> None:
    while True:
        await _switch_wait("liquidation listener")
        try:
            await _run()
        except Exception:  # network/timeout -> flush what we have and reconnect
            _flush()
            _HB.parent.mkdir(parents=True, exist_ok=True)
            _HB.write_text(str(time.time()), "utf-8")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(_main())
