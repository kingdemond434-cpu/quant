#!/usr/bin/env python3
"""DEXSCREENER LONG-TAIL DEX LIQUIDITY + NEW-LISTING FEED (R0100 axis 3) -- keyless.

MECHANISM (stated before any screen): DEX-first price discovery. Deployer/LP behaviour on the
long tail leads CEX listing flows and is invisible in every venue feed the desk collects. The
observables are the NEW-LISTING/PROFILE surface (which tokens are surfacing right now) and the
long-tail pair state (liquidity, volume, age) around them -- accumulated daily, the axis is the
DELTA of that surface, which no snapshot vendor sells retroactively.

SOURCE (§13): the documented public API at https://api.dexscreener.com -- keyless, and
docs.dexscreener.com/api/reference states a per-endpoint "rate-limit 60 requests per minute" for
the feed endpoints (fetched 2026-08-05). This collector issues <= ~10 requests per run with a
1.2s spacing -- an order of magnitude under the strictest documented limit.

WHAT ONE RUN APPENDS to data/dexscreener_snapshots.jsonl (append-only, dedup on (date, kind,
key) where key = pairAddress for pair rows -- i.e. (date, pairAddress) as specified by R0100):
  * kind="profile": every token in /token-profiles/latest/v1 and /token-boosts/latest/v1 -- the
    new-listing/attention feed, stamped the day the desk first saw it.
  * kind="pair": the full pair state for every pool of those tokens via /tokens/v1 (batched 30
    addresses per chain per call): price, liquidity.usd, fdv, marketCap, 24h volume, 24h
    buys/sells, pairCreatedAt and derived age_days.

CLOCK PROVENANCE (L1.46, libs/research/clock_provenance.py convention): DexScreener returns NO
server stamp on the snapshot payload, so the observation clock is OURS: t = receipt ms,
c = "recv_only". `pairCreatedAt` is a venue-stamped EVENT attribute retained verbatim beside it
-- it stamps the pair's creation, never this observation.

SCREEN-DEFERRAL (declared, computed from the harness's stated minimum): stage_a_screen returns
INSUFFICIENT-DATA below n(zv)=30, i.e. zwin(20)+30+1 = 51 aligned daily observations. Seeded
2026-08-05 at daily cadence -> the 51st snapshot lands 2026-09-24; the axis is screenable (not
yet powered) from that date. No screen is run before depth exists -- a screen on 1 snapshot
would be theatre.

    .venv/bin/python scripts/collect_dexscreener.py [--json]
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

_BASE = "https://api.dexscreener.com"
_OUT = "data/dexscreener_snapshots.jsonl"
_STATUS = "data/dexscreener_status.json"
_UA = "quant-desk-research/1.0 (public-endpoint reader)"
_TIMEOUT = 25
_SLEEP_S = 1.2                     # 60 req/min documented; this is ~50/min pace, ~10 calls/run
_BATCH = 30                        # /tokens/v1 accepts up to 30 comma-separated addresses

_FEEDS: tuple[tuple[str, str], ...] = (
    ("profiles", f"{_BASE}/token-profiles/latest/v1"),
    ("boosts", f"{_BASE}/token-boosts/latest/v1"),
)

#: First snapshot date + the harness floor -> the screenable-from date, kept in the artifact so
#: the deferral is a dated fact rather than a memory. 51 = zwin(20) + n_min(30) + 1.
SCREEN_DEFER = {"first_snapshot": "2026-08-05", "harness_min_daily_obs": 51,
                "screenable_from": "2026-09-24"}


def _get(url: str) -> tuple[Any, str]:
    """(payload, error). Never raises -- one dead endpoint must not kill the snapshot."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore")), ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:140]}"


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def pair_row(p: dict[str, Any], *, now_ms: int, date: str, feed: str) -> dict[str, Any] | None:
    """One pair's state. None when the payload lacks the dedup key -- absent must stay absent."""
    addr = p.get("pairAddress")
    if not addr:
        return None
    liq = p.get("liquidity") or {}
    vol = p.get("volume") or {}
    tx = (p.get("txns") or {}).get("h24") or {}
    created = p.get("pairCreatedAt")
    age_days = (round((now_ms - int(created)) / 86_400_000, 2)
                if isinstance(created, (int, float)) and created else None)
    return {"t": now_ms, "c": "recv_only", "date": date, "kind": "pair",
            "pairAddress": str(addr), "chainId": p.get("chainId"), "dexId": p.get("dexId"),
            "baseSymbol": (p.get("baseToken") or {}).get("symbol"),
            "baseAddress": (p.get("baseToken") or {}).get("address"),
            "quoteSymbol": (p.get("quoteToken") or {}).get("symbol"),
            "priceUsd": _num(p.get("priceUsd")), "liquidityUsd": _num(liq.get("usd")),
            "fdv": _num(p.get("fdv")), "marketCap": _num(p.get("marketCap")),
            "volumeH24": _num(vol.get("h24")),
            "buysH24": tx.get("buys"), "sellsH24": tx.get("sells"),
            "pairCreatedAt": created, "age_days": age_days, "source_feed": feed}


def fetch_all() -> tuple[list[dict[str, Any]], dict[str, str], int]:
    """Feed tokens -> batched pair resolution. Failures RECORDED per endpoint, never absent."""
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    date = datetime.now(tz=UTC).date().isoformat()
    rows: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    n_calls = 0

    by_chain: dict[str, list[str]] = {}
    feed_of: dict[tuple[str, str], str] = {}   # (chain, address) -> originating feed
    for feed, url in _FEEDS:
        doc, err = _get(url)
        n_calls += 1
        time.sleep(_SLEEP_S)
        if err:
            errors[feed] = err
            continue
        for item in doc if isinstance(doc, list) else []:
            chain, addr = item.get("chainId"), item.get("tokenAddress")
            if not chain or not addr:
                continue
            rows.append({"t": now_ms, "c": "recv_only", "date": date, "kind": "profile",
                         "key": f"{chain}:{addr}", "chainId": chain, "tokenAddress": addr,
                         "source_feed": feed})
            # KEY BY (chain, addr), NOT addr ALONE. Deterministic EVM deploys put the SAME
            # address on ethereum/base/bsc, so an address-only guard resolved a token on
            # whichever chain was seen first and silently never fetched the others' pools --
            # while the profile row two lines up already used the correct f"{chain}:{addr}".
            # Two disagreeing dedup keys over one surface is a coverage hole that reports OK.
            if (chain, addr) not in feed_of:
                feed_of[(chain, addr)] = feed
                by_chain.setdefault(chain, []).append(addr)

    for chain, addrs in by_chain.items():
        for i in range(0, len(addrs), _BATCH):
            batch = addrs[i:i + _BATCH]
            doc, err = _get(f"{_BASE}/tokens/v1/{chain}/{','.join(batch)}")
            n_calls += 1
            time.sleep(_SLEEP_S)
            if err:
                errors[f"tokens:{chain}"] = err
                continue
            for p in doc if isinstance(doc, list) else []:
                base = ((p.get("baseToken") or {}).get("address") or "")
                # look up on the SAME (chain, addr) key the guard above records, so a
                # multi-chain address attributes to the feed that surfaced it on THIS chain
                row = pair_row(p, now_ms=now_ms, date=date,
                               feed=feed_of.get((chain, base),
                                                feed_of.get((chain, base.lower()),
                                                            "resolved")))
                if row:
                    rows.append(row)
    return rows, errors, n_calls


def _existing_keys(path: Path, date: str) -> set[tuple[str, str]]:
    """Today's (kind, key) pairs -- the idempotency set. Only today's rows are loaded."""
    keys: set[tuple[str, str]] = set()
    if not path.exists():
        return keys
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
                if d.get("date") != date:
                    continue
                keys.add((d.get("kind", ""), d.get("pairAddress") or d.get("key") or ""))
            except ValueError:
                continue
    return keys


def collect(root: Path, rows: list[dict[str, Any]],
            errors: dict[str, str]) -> dict[str, Any]:
    """Append with (date, kind, pairAddress-or-key) dedup -- idempotent per day."""
    date = datetime.now(tz=UTC).date().isoformat()
    out = root / _OUT
    seen = _existing_keys(out, date)
    fresh = []
    for row in rows:
        k = (row["kind"], row.get("pairAddress") or row.get("key") or "")
        if not k[1] or k in seen:
            continue
        seen.add(k)
        fresh.append(row)
    if fresh:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row) + "\n")

    n_pairs = sum(1 for r in fresh if r["kind"] == "pair")
    both_feeds_dead = all(f in errors for f, _ in _FEEDS)
    status = ("ALL-SOURCES-DOWN" if both_feeds_dead else
              "DEGRADED" if errors else
              "NO-NEW-ROWS (idempotent rerun)" if not fresh and rows else
              "NO-DATA" if not fresh else "OK")
    return {"generated": datetime.now(tz=UTC).isoformat(), "status": status,
            "n_fetched": len(rows), "n_new": len(fresh), "n_new_pairs": n_pairs,
            "n_new_profiles": len(fresh) - n_pairs, "source_errors": errors,
            "screen_deferral": SCREEN_DEFER,
            "clock_provenance": "t=receipt ms, c=recv_only (venue publishes no snapshot stamp; "
                                "pairCreatedAt is a venue-stamped event attribute) -- L1.46",
            "detail": (f"{len(fresh)} new of {len(rows)} fetched ({n_pairs} pair snapshots); "
                       f"{len(errors)} endpoint error(s)")}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows, errors, n_calls = fetch_all()
    rep = collect(_ROOT, rows, errors)
    rep["n_http_calls"] = n_calls
    (_ROOT / _STATUS).write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"dexscreener (R0100 axis 3): {rep['status']} -- {rep['detail']}")
    if rep["status"] in ("ALL-SOURCES-DOWN", "NO-DATA"):
        print(f"REFUSED to report success: {rep['status']} -- an empty snapshot must never "
              "read as a quiet day (L1.28a)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
