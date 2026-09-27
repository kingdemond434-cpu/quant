"""Observable trading-system phenotypes used by archaeology and SARES.

This module deliberately infers behaviour, not the author's private rules.  Missing trade
paths stay UNMEASURED; summary statistics are never promoted into fictitious timestamps.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np

UNMEASURED = "UNMEASURED"
# Public API used by SARES: timestamp key aliases for one trade.
_TRADE_KEYS = ("open_time", "opened_at", "entry_time", "time")
_CLOSE_KEYS = ("close_time", "closed_at", "exit_time", "time_close")
_CONTAINER_KEYS = ("trades", "deals", "history", "positions")


def _num(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _time(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except ValueError:
        return None


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    # Older consumers pass either `_first(row, "a", "b")` or `_first(row, ("a", "b"))`.
    # Accept both; this tiny adapter is load-bearing for every SARES trade column.
    flat: list[str] = []
    for key in keys:
        if isinstance(key, (tuple, list)):
            flat.extend(str(x) for x in key)
        else:
            flat.append(str(key))
    return next((row[k] for k in flat if k in row and row[k] not in (None, "")), None)


def _pick(row: Mapping[str, Any], *keys: str) -> float | None:
    return _num(_first(row, *keys))


def _stats(row: Mapping[str, Any]) -> Mapping[str, Any]:
    x = row.get("stats")
    return x if isinstance(x, Mapping) else row


def _split(row: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    head = dict(row)
    trades: list[dict[str, Any]] = []
    for key in _CONTAINER_KEYS:
        raw = head.pop(key, None)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            trades = [dict(x) for x in raw if isinstance(x, Mapping)]
            break
    return head, trades


def _side(row: Mapping[str, Any]) -> float | None:
    s = str(_first(row, "side", "direction", "type") or "").lower()
    if "buy" in s or s in ("long", "1"):
        return 1.0
    if "sell" in s or s in ("short", "-1"):
        return -1.0
    return None


def _session_of(hour: int) -> tuple[str, ...]:
    out = []
    if 22 <= hour or hour < 8:
        out.append("asia")
    if 7 <= hour < 16:
        out.append("london")
    if 12 <= hour < 22:
        out.append("ny")
    return tuple(out or ("all",))


def _bar_state(bars: Any, symbol: str, chart: str, at: datetime) -> dict[str, float] | None:
    try:
        frame = bars(symbol, chart) if callable(bars) else bars
        if frame is None or len(frame) < 30:
            return None
        sub = frame.loc[:at] if hasattr(frame, "loc") else frame
        close = np.asarray(sub["close"], dtype=float)[-60:]
        high = np.asarray(sub["high"], dtype=float)[-60:]
        low = np.asarray(sub["low"], dtype=float)[-60:]
        if close.size < 20:
            return None
        tr = high - low
        atr = float(np.mean(tr[-14:]))
        ref = float(np.mean(tr))
        sd = float(np.std(close[-20:]))
        trend = 0.0 if sd <= 0 else float((close[-1] - close[-20]) / sd)
        return {"atr": atr, "atr_ref": ref, "trend_z": trend}
    except Exception:
        return None


def _trade_columns(trades: Sequence[Mapping[str, Any]]) -> dict[str, list[Any]]:
    return {
        "opens": [_time(_first(t, "open_time", "opened_at", "entry_time", "time")) for t in trades],
        "closes": [_time(_first(t, *_CLOSE_KEYS)) for t in trades],
        "profits": [_pick(t, "profit", "pnl", "net_profit", "return") for t in trades],
        "lots": [_pick(t, "lot", "lots", "volume", "size") for t in trades],
        "sides": [_side(t) for t in trades],
        "symbols": [str(_first(t, "symbol", "instrument") or "") for t in trades],
        "prices": [_pick(t, "open_price", "entry_price", "price") for t in trades],
    }


def fingerprint(row: Mapping[str, Any], bars: Any = None, *, events: Any = None) -> dict[str, Any]:
    head, trades = _split(row)
    stats = _stats(head)
    sid = str(head.get("system_id") or head.get("id") or hashlib.sha256(
        json.dumps(head, sort_keys=True, default=str).encode()).hexdigest()[:16])
    fields: dict[str, Any] = {}
    source = "stats_only"
    if trades:
        source = "trade_path"
        c = _trade_columns(trades)
        pnl = np.asarray([x for x in c["profits"] if x is not None], dtype=float)
        lots = np.asarray([x for x in c["lots"] if x is not None], dtype=float)
        opens = [x for x in c["opens"] if x is not None]
        holds = [(b-a).total_seconds()/3600 for a, b in zip(c["opens"], c["closes"], strict=True)
                 if a is not None and b is not None and b >= a]
        fields.update({
            "n_trades": len(trades),
            "holding_hours_median": float(np.median(holds)) if holds else None,
            "win_rate": float(np.mean(pnl > 0)) if pnl.size else None,
            "payoff": (float(pnl[pnl > 0].mean() / -pnl[pnl < 0].mean())
                       if np.any(pnl > 0) and np.any(pnl < 0) else None),
            # Signed tail asymmetry: a short-vol path has a deep lower tail relative to its
            # ordinary upper tail.  A raw sum is scale-dependent and missed 36 wins / 4 losses.
            "convexity": (float(np.percentile(pnl, 10) /
                                max(abs(float(np.percentile(pnl, 90))), 1e-12))
                          if pnl.size >= 5 else None),
            "directionality": (float(np.mean([x for x in c["sides"] if x is not None]))
                               if any(x is not None for x in c["sides"]) else None),
            "lot_growth": (float(np.median(lots[1:] / lots[:-1]))
                           if lots.size > 2 and np.all(lots[:-1] > 0) else None),
            "session": (Counter(s for o in opens for s in _session_of(o.hour)).most_common(1)[0][0]
                        if opens else None),
        })
        if bars is not None and opens:
            states = [_bar_state(bars, s, "H1", o) for s, o in zip(c["symbols"], c["opens"], strict=True)
                      if o is not None and s]
            states = [x for x in states if x]
            fields["vol_beta"] = (float(np.mean([x["atr"] / x["atr_ref"] for x in states
                                                  if x["atr_ref"]])) if states else None)
    else:
        win = _pick(stats, "win_rate")
        fields.update({"n_trades": _pick(stats, "trades", "n_trades"),
                       "win_rate": (win / 100.0 if win is not None and win > 1 else win),
                       "payoff": None, "convexity": None, "directionality": None,
                       "holding_hours_median": None, "vol_beta": None})
    return {"system_id": sid, "platform": str(head.get("platform") or "unknown"),
            "source": source, "fields": fields, "trades": len(trades)}


def fingerprint_population(rows: Sequence[Mapping[str, Any]], bars: Any = None,
                           trade_paths: Mapping[str, Sequence[Mapping[str, Any]]] | None = None
                           ) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        x = dict(row)
        sid = str(x.get("system_id") or x.get("id") or "")
        if sid and trade_paths and sid in trade_paths:
            x["trades"] = list(trade_paths[sid])
        out.append(fingerprint(x, bars))
    return out


def _clusters(phis: Sequence[Mapping[str, Any]], k: int | None = None) -> list[dict[str, Any]]:
    """Trade clusters for SARES, or interpretable phenotype archetypes.

    SARES passes raw trades and expects lists of integer positions belonging to one concurrent
    same-symbol/side campaign.  The archaeology civilization passes fingerprints and expects
    named archetype dictionaries.  The shapes are deliberately distinguishable.
    """
    if phis and any("open_time" in x or "opened_at" in x or "entry_time" in x for x in phis):
        parsed = []
        for i, trade in enumerate(phis):
            opened = _time(_first(trade, "open_time", "opened_at", "entry_time", "time"))
            closed = _time(_first(trade, *_CLOSE_KEYS))
            parsed.append((i, opened, closed, str(trade.get("symbol") or ""), _side(trade)))
        groups: list[list[int]] = []
        used: set[int] = set()
        for i, opened, closed, symbol, side in parsed:
            if i in used:
                continue
            cluster = [i]
            end = closed
            for j, oj, cj, sj, dj in parsed[i + 1:]:
                if oj is None or opened is None or sj != symbol or dj != side:
                    continue
                # Same campaign when the next order opens while the current basket remains open,
                # or within one hour when public records use a common basket close timestamp.
                if (end is not None and oj <= end) or abs((oj-opened).total_seconds()) <= 3600:
                    cluster.append(j)
                    if cj is not None and (end is None or cj > end):
                        end = cj
            used.update(cluster)
            groups.append(cluster)
        return groups  # type: ignore[return-value]
    """Deterministic, interpretable archetypes; no unstable random labels."""
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for p in phis:
        f = p.get("fields") or {}
        wr, pay, growth = _num(f.get("win_rate")), _num(f.get("payoff")), _num(f.get("lot_growth"))
        if growth is not None and growth >= 1.4:
            name = "recovery_ladder"
        elif wr is not None and wr >= .72 and (pay is None or pay < 1):
            name = "short_vol_or_reversion"
        elif pay is not None and pay >= 1.2 and (wr is None or wr <= .55):
            name = "trend_or_breakout"
        else:
            name = "mixed_unresolved"
        groups[name].append(p)
    return [{"archetype": n, "members": [str(x.get("system_id")) for x in xs],
             "n": len(xs), "centroid": {}}
            for n, xs in sorted(groups.items())]


def archetypes(phis: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not phis:
        return {"status": UNMEASURED, "why": "no fingerprints", "clusters": []}
    clusters = _clusters(phis)
    return {"status": "measured", "clusters": clusters, "k": len(clusters),
            "silhouette": UNMEASURED, "stability_rand": 1.0, "split_half_rand": UNMEASURED,
            "stable": True, "warning": "interpretable deterministic partition",
            "method": "behavioural_rules"}


def archetype_counts(clusters: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {str(c.get("archetype")): int(c.get("n") or len(c.get("members") or [])) for c in clusters}


def crowding(counts: Mapping[str, int]) -> dict[str, Any]:
    total = sum(max(0, int(v)) for v in counts.values())
    if not total:
        return {"status": UNMEASURED, "why": "no archetypes"}
    shares = {k: v / total for k, v in counts.items()}
    return {"status": "measured", "n": total, "shares": shares,
            "hhi": sum(x*x for x in shares.values()),
            "largest": max(shares, key=shares.get)}


def negative_space(trades: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(trades) < 5:
        return {"status": UNMEASURED, "why": "fewer than five timestamped entries"}
    c = _trade_columns(trades)
    hours = Counter(x.hour for x in c["opens"] if x is not None)
    if not hours:
        return {"status": UNMEASURED, "why": "entries have no timestamps"}
    absent = [h for h in range(24) if h not in hours]
    return {"status": "measured", "entry_hours": dict(hours), "absent_hours": absent,
            "concentration": max(hours.values()) / sum(hours.values())}


def survivorship(rows: Sequence[Mapping[str, Any]], *, phis: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    dates = sorted({str(r.get("snapshot_at") or "") for r in rows if r.get("snapshot_at")})
    if len(dates) < 2:
        return {"status": UNMEASURED, "why": "fewer than two prospective snapshots",
                "n_snapshots": len(dates), "horizons": {}}
    by_date = {d: {str(r.get("system_id")) for r in rows if str(r.get("snapshot_at")) == d}
               for d in dates}
    a, b = dates[-2:]
    base = by_date[a]
    survived = base & by_date[b]
    return {"status": "measured", "n_snapshots": len(dates),
            "horizons": {f"{a}->{b}": {"base": len(base), "survived": len(survived),
                                         "rate": len(survived) / max(1, len(base))}}}
