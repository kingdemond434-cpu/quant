"""Prediction-market data (Polymarket) -- the one funds-barred, solo-advantaged information domain.

Pulls RESOLVED binary markets (Gamma API) + their pre-resolution price history (CLOB API) so we can
test calibration / favorite-longshot bias: does the de-vigged market probability match the realized
outcome frequency? Free, public, read-only. Point-in-time: only prices strictly BEFORE resolution
are used; the outcome is known only after settlement.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import pandas as pd

_GAMMA = "https://gamma-api.polymarket.com"
_CLOB = "https://clob.polymarket.com"


def _get(url: str, *, tries: int = 4) -> Any:
    last: Exception | None = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-platform/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            last = exc
            time.sleep(1.0)
    raise RuntimeError(f"GET failed: {url} :: {last}")


def fetch_resolved_markets(*, max_markets: int = 1500) -> list[dict[str, Any]]:
    """Resolved binary (Yes/No) markets, highest-volume first. Returns clean 0/1 outcomes only."""
    out: list[dict[str, Any]] = []
    offset = 0
    while len(out) < max_markets:
        url = (f"{_GAMMA}/markets?closed=true&limit=500&offset={offset}"
               f"&order=volumeNum&ascending=false")
        try:
            batch = _get(url)
        except RuntimeError:
            break  # API pagination cap (422) -> return what we have
        if not batch:
            break
        for m in batch:
            try:
                outcomes = json.loads(m.get("outcomes", "[]"))
                prices = json.loads(m.get("outcomePrices", "[]"))
                tokens = json.loads(m.get("clobTokenIds", "[]"))
            except (json.JSONDecodeError, TypeError):
                continue
            if outcomes != ["Yes", "No"] or m.get("umaResolutionStatus") != "resolved":
                continue
            if prices not in (["1", "0"], ["0", "1"]) or len(tokens) != 2:
                continue
            out.append({
                "question": m.get("question", ""), "yes_token": tokens[0],
                "outcome": float(prices[0]),          # 1.0 if Yes won, else 0.0
                "end": m.get("endDate", ""), "start": m.get("startDate", ""),
                "volume": float(m.get("volumeNum", 0.0) or 0.0),
            })
        offset += 500
        time.sleep(0.2)
    return out[:max_markets]


def fetch_price_history(token_id: str, *, fidelity: int = 720) -> pd.DataFrame:
    """YES-token price history (implied probability over time). fidelity in minutes."""
    url = f"{_CLOB}/prices-history?market={token_id}&interval=max&fidelity={fidelity}"
    data = _get(url)
    hist = data.get("history", []) if isinstance(data, dict) else []
    if not hist:
        return pd.DataFrame()
    return pd.DataFrame({
        "ts": pd.to_datetime([h["t"] for h in hist], unit="s", utc=True),
        "p": [float(h["p"]) for h in hist],
    })


def implied_prob_before(
    history: pd.DataFrame, end: pd.Timestamp, *, lead_days: float
) -> float | None:
    """Last YES price >= ``lead_days`` before resolution (no look-ahead); None if unavailable."""
    if history.empty:
        return None
    cutoff = end - pd.Timedelta(days=lead_days)
    prior = history[history["ts"] <= cutoff]
    if prior.empty:
        return None
    return float(prior["p"].iloc[-1])
