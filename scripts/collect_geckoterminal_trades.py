#!/usr/bin/env python3
"""GECKOTERMINAL WALLET-RESOLVED SIGNED DEX TRADES (R0291) -- keyless, forward-only.

MECHANISM (stated before any screen): true SIGNED order flow WITH counterparty identity.
Every trade row carries tx_from_address, buy/sell kind, volume_in_usd, block_number and
tx_hash -- the flow-attribution surface (who is forced to trade, and which side) that no
CEX feed exposes at any price. Venue retention is ~300 trades per pool, so the axis is
FORWARD-ONLY-UNRECOVERABLE (L1.28b(f)): every hour not recorded is permanently gone, which
is why this collector exists and runs hourly rather than waiting for a consumer.

SOURCE (§13): the documented public API at https://api.geckoterminal.com/api/v2 -- keyless,
free tier, link attribution requested (satisfiable; this is a research reader, not a
redistribution). Documented limit 30 calls/min; measured burst ~3 rapid calls then 429
(R0291). This collector issues <= ~14 calls per run at 2.6s spacing (~23/min pace).

WHAT ONE RUN APPENDS to data/geckoterminal_trades.jsonl (append-only, dedup on
(network, pool, tx_hash) against the status file's rolling hash memory):
  * one row per NEW trade in the top trending pools per network: both clocks, wallet,
    side, usd size, block number, token amounts.

SAMPLING TRUNCATION IS RECORDED, NEVER SILENT: the venue serves only the LAST ~300 trades,
so a busy pool can turn over its whole window between runs. When every fetched trade is
new against a pool's existing watermark, the run sets overflow=true for that pool in
data/geckoterminal_status.json -- "captured everything the venue still had" and "captured
everything that happened" are different claims and only one is evidence.

CLOCK PROVENANCE (L1.46, libs/research/clock_provenance.py convention): the venue DOES
publish a stamp -- block_timestamp, the chain's clock -- retained as t_venue (ms) beside
our receipt t (ms), c = "recv". delta = t - t_venue is first-class and structurally
unbuyable. Rows are appended in RECEIPT order (mixed-clock file ordering rule).

SCREEN-DEFERRAL (declared, computed from the harness's stated minimum): the derived daily
axis (net signed flow per pool per day) needs zwin(20)+30+1 = 51 aligned daily
observations; seeded 2026-08-12 at hourly capture -> screenable (not yet powered) from
2026-10-02. No screen before depth exists.

    .venv/bin/python scripts/collect_geckoterminal_trades.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_BASE = "https://api.geckoterminal.com/api/v2"
_OUT = "data/geckoterminal_trades.jsonl"
_STATUS = "data/geckoterminal_status.json"
_UA = "quant-desk-research/1.0 (public-endpoint reader; attribution: geckoterminal.com)"
_TIMEOUT = 25
#: 30 req/min documented, but the live limiter is burstier: first run at 2.6s spacing still
#: drew 429 on 3 of 8 calls. 4.5s (~13/min) + one 20s-backoff retry measured clean.
_SLEEP_S = 4.5
_RETRY_429_S = 20.0
_NETWORKS: tuple[str, ...] = ("eth", "solana")
_POOLS_PER_NETWORK = 6            # 2 discovery + 12 trade calls = 14/run, well under 30/min
_HASH_MEMORY = 900                # rolling dedup window per pool; venue retention is ~300


def _get(url: str, *, retried: bool = False) -> tuple[Any, str]:
    """(payload, error). Never raises -- one dead endpoint must not kill the capture.
    A 429 gets ONE backoff retry: the limiter is burstier than its documented 30/min."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore")), ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        msg = f"{type(exc).__name__}: {str(exc)[:140]}"
        if "429" in msg and not retried:
            time.sleep(_RETRY_429_S)
            return _get(url, retried=True)
        return None, msg


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _venue_ms(iso: Any) -> int | None:
    """block_timestamp (chain clock) -> epoch ms; None when unparseable, never a guess."""
    if not isinstance(iso, str) or not iso:
        return None
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def trade_row(attrs: dict[str, Any], *, network: str, pool: str, pool_name: str,
              recv_ms: int) -> dict[str, Any] | None:
    """One trade. None when the payload lacks the dedup key -- absent must stay absent."""
    tx = attrs.get("tx_hash")
    if not tx:
        return None
    return {"t": recv_ms, "c": "recv", "t_venue": _venue_ms(attrs.get("block_timestamp")),
            "network": network, "pool": pool, "pool_name": pool_name,
            "tx_hash": str(tx), "tx_from": attrs.get("tx_from_address"),
            "kind": attrs.get("kind"), "volume_usd": _num(attrs.get("volume_in_usd")),
            "block_number": attrs.get("block_number"),
            "from_amount": _num(attrs.get("from_token_amount")),
            "to_amount": _num(attrs.get("to_token_amount")),
            "price_to_usd": _num(attrs.get("price_to_in_usd")),
            "price_from_usd": _num(attrs.get("price_from_in_usd"))}


def discover_pools(network: str) -> tuple[list[tuple[str, str]], str]:
    """Top trending pools -> [(address, name)]. Trending IS the point: capture goes where
    flow is now; the archive accumulates whichever pools mattered each hour."""
    payload, err = _get(f"{_BASE}/networks/{network}/trending_pools")
    if err:
        return [], err
    pools: list[tuple[str, str]] = []
    for item in (payload or {}).get("data", [])[:_POOLS_PER_NETWORK]:
        attrs = item.get("attributes") or {}
        addr = attrs.get("address")
        if addr:
            pools.append((str(addr), str(attrs.get("name") or "")))
    return pools, "" if pools else "trending payload held zero addressable pools"


def fetch_all(status: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], int, int]:
    """Discovery -> per-pool trades, deduped against the rolling hash memory."""
    recv_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    rows: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    overflow: dict[str, bool] = {}
    seen: dict[str, list[str]] = status.get("recent_hashes", {})
    n_calls = 0
    n_pools = 0
    for net in _NETWORKS:
        pools, err = discover_pools(net)
        n_calls += 1
        n_pools += len(pools)
        if err:
            errors[f"{net}/trending"] = err
        time.sleep(_SLEEP_S)
        for addr, name in pools:
            key = f"{net}:{addr}"
            payload, err = _get(f"{_BASE}/networks/{net}/pools/{addr}/trades")
            n_calls += 1
            time.sleep(_SLEEP_S)
            if err:
                errors[f"{net}/{addr}/trades"] = err
                continue
            known = set(seen.get(key, []))
            served = (payload or {}).get("data", [])
            fresh: list[dict[str, Any]] = []
            for item in served:
                row = trade_row(item.get("attributes") or {}, network=net, pool=addr,
                                pool_name=name, recv_ms=recv_ms)
                if row and row["tx_hash"] not in known:
                    fresh.append(row)
            # Venue serves only the LAST ~300 trades: when a pool we HAVE captured before
            # comes back with EVERY served trade new, its window turned over between runs
            # and the gap is a real loss -- record the truncation loudly rather than let
            # it read as a quiet market (no silent caps).
            if key in seen and served and len(fresh) == len(served):
                overflow[key] = True
            rows.extend(fresh)
            seen[key] = ([r["tx_hash"] for r in fresh] + seen.get(key, []))[:_HASH_MEMORY]
    status["recent_hashes"] = seen
    status["overflow"] = overflow
    return rows, errors, n_calls, n_pools


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    out, status_p = _ROOT / _OUT, _ROOT / _STATUS
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        status = json.loads(status_p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        status = {}
    rows, errors, n_calls, n_pools = fetch_all(status)

    # REFUSAL PATH: a run that reached NO pool at all appends nothing, says so, and exits
    # red -- an outage and a quiet market must never look alike. A partial degradation
    # (one network's discovery down) is recorded per endpoint but does not fail a run
    # that still captured the reachable side.
    if rows:
        with out.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    status.update({
        "ts": datetime.now(tz=UTC).isoformat(), "calls": n_calls,
        "pools_reached": n_pools, "appended": len(rows), "errors": errors,
        "verdict": ("CAPTURED" if rows else
                    "REFUSED-EMPTY: zero pools reachable; see errors" if n_pools == 0 else
                    "QUIET: pools reached, zero new trades"),
        "screen_defer": {"first_capture": "2026-08-12", "harness_min_daily_obs": 51,
                         "screenable_from": "2026-10-02"},
    })
    status_p.write_text(json.dumps(status, indent=1) + "\n", "utf-8")
    line = (f"geckoterminal-trades: +{len(rows)} rows, {n_calls} calls, {n_pools} pools, "
            f"{len(errors)} error(s), overflow={list(status.get('overflow', {}))}")
    print(json.dumps(status, indent=1) if args.json else line)
    return 0 if n_pools > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
