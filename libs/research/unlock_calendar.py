"""Unlock-calendar parsing and point-in-time reads (R0288).

The desk owns data/unlock_events.json -- 24,201 events, s13-passed -- and until this module it had
ZERO python readers: a one-shot 2026-07-24 snapshot whose forward calendar expires 2026-08-23. The
snapshot's `pct_circ_now` is %-of-TODAY's-supply applied to events back to 2016, which is a
look-ahead in the CONDITIONING variable (desk lesson: it structurally empties the historical
high-threshold bucket and fails toward a FALSE NULL).

This module is the honest replacement for that field:

  * events parsed from defillama.com/unlocks carry the supply OBSERVED AT COLLECTION TIME
    (`circ_at_obs`, `pct_circ_at_obs`) and a `retrospective` flag. A FUTURE event's pct-of-float
    at first sight is a genuine point-in-time measure; a PAST event's is the same look-ahead the
    snapshot had, so it stays flagged and `forward_events` never serves it.
  * `supply_at` answers "what was circulating supply as of DATE" from the desk's own accruing
    point-in-time series (collect_circulating_supply.py) and returns None when the series does not
    cover the date -- UNMEASURED, never a fabricated backfill.

Cliff vs linear: the forced-supply mechanism is CLIFF-shaped (a dated tranche hits the float).
Linear-rate rows are kept for completeness but carry tokens=None -- a rate change is not a tranche,
and summing its [from, to] pair would fabricate a tranche size no venue ever saw.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent

SNAPSHOT = "data/unlock_events.json"
CALENDAR = "data/unlock_calendar.jsonl"
SUPPLY_SERIES = "data/circulating_supply.jsonl"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def parse_next_data(html: str) -> dict[str, Any]:
    """The unlocks page's embedded JSON, or a refusal -- never a guessed shape.

    Raises ValueError when the marker is absent or the payload does not carry the protocol list:
    a page redesign must surface as a loud collector failure, not as zero events appended (zero
    events and a broken parser are different claims -- L1.57).
    """
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ marker absent -- page shape changed")
    doc = json.loads(m.group(1))
    props = doc.get("props", {}).get("pageProps", {})
    data = props.get("data")
    if not isinstance(data, list) or not data:
        raise ValueError("pageProps.data missing or empty -- page shape changed")
    return {"generated_at_sec": props.get("generatedAtSec"), "protocols": data}


def extract_events(protocols: list[dict[str, Any]], observed_utc: datetime) -> list[dict[str, Any]]:
    """Flatten protocol rows into one dict per unlock event, stamped with observation time.

    `pct_circ_at_obs` divides by the supply CURRENT AT COLLECTION -- honest for events still in
    the future (`retrospective` False), the known look-ahead for past ones (flag kept True so no
    screen can consume it silently).
    """
    obs_ts = observed_utc.timestamp()
    out: list[dict[str, Any]] = []
    for p in protocols:
        if not isinstance(p, dict):
            continue
        symbol = (p.get("tSymbol") or "").upper()
        circ = p.get("circSupply")
        maxs = p.get("maxSupply")
        for ev in p.get("events") or []:
            ts = ev.get("timestamp")
            if not isinstance(ts, (int, float)) or ts <= 0:
                continue
            raw = [t for t in (ev.get("noOfTokens") or []) if isinstance(t, (int, float))]
            cliff = (ev.get("unlockType") == "cliff")
            tokens = float(sum(raw)) if (cliff and raw) else None
            pct_circ = (
                round(tokens / circ * 100.0, 6)
                if tokens is not None and isinstance(circ, (int, float)) and circ > 0 else None)
            pct_max = (
                round(tokens / maxs * 100.0, 6)
                if tokens is not None and isinstance(maxs, (int, float)) and maxs > 0 else None)
            out.append({
                "key": f"{p.get('protocolSlug') or p.get('name')}|{int(ts)}|"
                       f"{ev.get('unlockType')}|{round(tokens, 4) if tokens else 0}",
                "symbol": symbol,
                "protocol": p.get("name"),
                "gecko_id": p.get("gecko_id"),
                "ts": int(ts),
                "date": datetime.fromtimestamp(int(ts), tz=UTC).date().isoformat(),
                "tokens": tokens,
                "tokens_raw": raw,
                "category": ev.get("category"),
                "unlock_type": ev.get("unlockType"),
                "circ_at_obs": circ,
                "max_supply": maxs,
                "pct_circ_at_obs": pct_circ,
                "pct_max": pct_max,
                "retrospective": ts < obs_ts,
                "observed_utc": observed_utc.isoformat(),
            })
    return out


def append_new(events: list[dict[str, Any]], root: Path | None = None) -> int:
    """Append first-seen events to the registry; the file is append-only and never rewritten.

    A changed event (same protocol+ts, different size) gets a NEW row under its own key -- both
    observations are real, and overwriting the first would destroy the point-in-time record the
    whole collector exists for (L1.46).
    """
    path = (root or _ROOT) / CALENDAR
    seen: set[str] = set()
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    seen.add(json.loads(line)["key"])
                except (json.JSONDecodeError, KeyError):
                    continue  # a corrupt line must not block accrual; the row stays re-appendable
    fresh = [e for e in events if e["key"] not in seen]
    if fresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for e in fresh:
                fh.write(json.dumps(e, separators=(",", ":")) + "\n")
    return len(fresh)


def load_snapshot(root: Path | None = None) -> list[dict[str, Any]]:
    """The 2026-07-24 one-shot snapshot -- its first python reader.

    Rows come back as stored; the `pct_circ_now` field is served under the truthful name
    `pct_circ_lookahead` so a downstream screen has to OPT IN to the flawed denominator.
    """
    path = (root or _ROOT) / SNAPSHOT
    doc = json.loads(path.read_text("utf-8"))
    out = []
    for e in doc.get("events", []):
        row = dict(e)
        if "pct_circ_now" in row:
            row["pct_circ_lookahead"] = row.pop("pct_circ_now")
        out.append(row)
    return out


def load_calendar(root: Path | None = None) -> list[dict[str, Any]]:
    """Every accrued live-calendar observation, oldest first. Empty list when none accrued yet."""
    path = (root or _ROOT) / CALENDAR
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def forward_events(now: datetime, *, within_days: float = 90.0,
                   min_pct_circ: float = 0.0, root: Path | None = None) -> list[dict[str, Any]]:
    """Upcoming cliff events with a POINT-IN-TIME pct-of-float, retrospective rows excluded.

    Only rows first observed BEFORE their event qualify -- that is the entire discipline: the
    conditioning variable must have been knowable at decision time.
    """
    horizon = now.timestamp() + within_days * 86400.0
    out = []
    for e in load_calendar(root):
        if e.get("retrospective") or e.get("tokens") is None:
            continue
        if not (now.timestamp() <= e["ts"] <= horizon):
            continue
        pct = e.get("pct_circ_at_obs")
        if pct is None or pct < min_pct_circ:
            continue
        out.append(e)
    return sorted(out, key=lambda e: e["ts"])


def supply_at(coin: str, as_of: datetime, root: Path | None = None) -> dict[str, Any] | None:
    """Circulating supply as of `as_of` from the desk's own accruing series, else None.

    Matches on coin_id or symbol (case-insensitive). Uses only observations stamped AT OR BEFORE
    `as_of` -- an observation made later must never inform an earlier date, however plausible the
    number. None means UNMEASURED: the series does not cover that date, and no other source is
    consulted (a fabricated denominator is the exact defect this module replaces).
    """
    path = (root or _ROOT) / SUPPLY_SERIES
    if not path.exists():
        return None
    coin_l = coin.lower()
    best: dict[str, Any] | None = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("coin_id", "").lower() != coin_l and \
               row.get("symbol", "").lower() != coin_l:
                continue
            try:
                obs = datetime.fromisoformat(row["observed_utc"])
            except (KeyError, ValueError):
                continue
            if obs <= as_of and (best is None or obs > best["_obs"]):
                best = {**row, "_obs": obs}
    if best:
        best.pop("_obs", None)
    return best
