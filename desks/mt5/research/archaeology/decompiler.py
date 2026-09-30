"""Mechanism decompiler for public trading-system archaeology.

Outputs are hypotheses with falsifiers.  They never inherit a source's profitability claim and
never bypass the universal gauntlet.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

import numpy as np

from archaeology import phenotype as ph
from libs.moat import registry as reg

UNMEASURED = "UNMEASURED"
SOURCE_TYPE = "archaeology"
ORIGIN = "EXTERNAL"

_MAP: dict[str, tuple[tuple[str, str, str], ...]] = {
    "recovery_ladder": (("range_reversion", "inventory/recovery ladder", "shuffle entry spacing"),
                        ("vol_mean_reversion", "short volatility", "condition on volatility spikes")),
    "short_vol_or_reversion": (("mean_reversion_rsi", "mean reversion", "shuffle distance to anchor"),
                               ("vol_mean_reversion", "short volatility", "remove tail intervals")),
    "trend_or_breakout": (("trend_ma_cross", "trend persistence", "shuffle trend state"),
                          ("session_range_breakout", "forced session flow", "shuffle session boundary")),
    "mixed_unresolved": (("range_reversion", "local price reversion", "shuffle anchor distance"),
                         ("trend_ma_cross", "directional persistence", "shuffle return ordering")),
}


def _scrub(value: Any) -> tuple[Any, list[str]]:
    """Remove secrets/private payload fields recursively and report what was removed."""
    removed: list[str] = []
    banned = ("password", "secret", "token", "api_key", "private_key", "cookie")
    def walk(x: Any, path: str = "") -> Any:
        if isinstance(x, Mapping):
            out = {}
            for k, v in x.items():
                p = f"{path}.{k}" if path else str(k)
                if any(b in str(k).lower() for b in banned):
                    removed.append(p)
                else:
                    out[k] = walk(v, p)
            return out
        if isinstance(x, list):
            return [walk(v, f"{path}[]") for v in x]
        return x
    return walk(value), removed


def _asset_lane(symbols: list[str]) -> tuple[list[str], list[str]]:
    keep, refused = [], []
    for raw in symbols:
        s = str(raw).strip()
        if not s:
            continue
        # Single-name equities are an event-lane asset.  The compiler performs the final
        # universe check; this boundary catches common public-record spellings.
        if s.lower() in {"apple", "aapl", "tesla", "tsla", "amazon", "amzn"}:
            refused.append(s)
        else:
            keep.append(s)
    return sorted(set(keep)), sorted(set(refused))


def era_of(value: str) -> str:
    try:
        year = datetime.fromisoformat(str(value).replace("Z", "+00:00")).year
    except ValueError:
        try:
            year = int(str(value)[:4])
        except ValueError:
            return "unknown"
    return f"{year // 5 * 5}s"


def explanations(archetype: str) -> tuple[tuple[str, str, str], ...]:
    return _MAP.get(str(archetype), _MAP["mixed_unresolved"])


def explanation_table(archetypes: Sequence[str]) -> list[dict[str, Any]]:
    return [{"archetype": a,
             "competing": [{"family": f, "mechanism": m, "falsifier": z}
                           for f, m, z in explanations(a)]}
            for a in archetypes]


def counterfactual(trades: Sequence[Mapping[str, Any]], *, bars: Any = None) -> dict[str, Any]:
    if not trades:
        return {"status": UNMEASURED, "why": "no trade path"}
    pnl = [ph._pick(t, "profit", "pnl", "net_profit", "return") for t in trades]
    lots = [ph._pick(t, "lot", "lots", "volume", "size") for t in trades]
    pairs = [(p, l) for p, l in zip(pnl, lots, strict=True) if p is not None and l not in (None, 0)]
    if not pairs:
        return {"status": UNMEASURED, "why": "trade path has no PnL and size"}
    raw = float(np.mean([p for p, _ in pairs]))
    unit = float(np.mean([p/l for p, l in pairs]))
    # Concurrent same-side positions approximate recovery clusters without pretending to know
    # the platform's order grouping.
    parsed = []
    for t in trades:
        o = ph._time(ph._first(t, "open_time", "opened_at", "entry_time", "time"))
        c = ph._time(ph._first(t, *ph._CLOSE_KEYS))
        if o and c:
            parsed.append((o, c, ph._side(t)))
    deepest = 1
    for o, _c, side in parsed:
        deepest = max(deepest, sum(1 for a, b, s in parsed if a <= o < b and s == side))
    first = []
    for i, (o, _c, _s) in enumerate(parsed):
        if not any(a < o < b for a, b, _ in parsed):
            p = pnl[i] if i < len(pnl) else None
            if p is not None:
                first.append(p)
    first_exp = float(np.mean(first)) if first else None
    survives = bool(unit > 0 and (first_exp is None or first_exp > 0))
    return {"status": "measured", "raw_expectancy": raw, "unit_size_expectancy": unit,
            "first_entry_expectancy": first_exp, "deepest_cluster": deepest,
            "information_survives": survives,
            "interpretation": "size and clustered entries stripped before asking if information remains"}


def mechanism_rows(archetype: str, *, platform: str, era: str, region: str,
                   source_id: str) -> list[dict[str, Any]]:
    return [{"archetype": archetype, "family": f, "mechanism": m, "falsifier": z,
             "platform": platform, "era": era, "region": region, "source_id": source_id}
            for f, m, z in explanations(archetype)]


def synthesis(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for r in rows:
        buckets.setdefault((str(r.get("family")), str(r.get("mechanism"))), []).append(r)
    out = []
    for (fam, mech), xs in buckets.items():
        grounds = {(str(x.get("platform")), str(x.get("era")), str(x.get("region"))) for x in xs}
        out.append({"family": fam, "mechanism": mech, "n": len(xs),
                    "independent_grounds": len(grounds), "grounds": sorted(grounds),
                    "replicated": len(grounds) >= 2})
    return sorted(out, key=lambda x: (-x["independent_grounds"], -x["n"], x["family"]))


def evolution(versions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(versions) < 2:
        return {"status": UNMEASURED, "why": "fewer than two public versions"}
    ordered = sorted((dict(x) for x in versions), key=lambda x: str(x.get("at") or x.get("version") or ""))
    changed = []
    for a, b in zip(ordered, ordered[1:]):
        keys = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k) and k not in {"at", "version"})
        changed.append({"from": a.get("version"), "to": b.get("version"), "changed": keys})
    return {"status": "measured", "n_versions": len(ordered), "transitions": changed}


def decompile(cluster: Mapping[str, Any], *, source_id: str, family: str,
              trade_paths: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
              bars: Any = None, conn: Any = None, dry_run: bool = False) -> dict[str, Any]:
    archetype = str(cluster.get("archetype") or "mixed_unresolved")
    members = [str(x) for x in cluster.get("members") or []]
    cf = next((counterfactual((trade_paths or {}).get(m, []), bars=bars)
               for m in members if (trade_paths or {}).get(m)),
              {"status": UNMEASURED, "why": "no member trade path"})
    recorded = existing = errors = 0
    ids = []
    for fam, mechanism, falsifier in explanations(archetype):
        payload = {"kind": "archaeology_hypothesis", "archetype": archetype,
                   "members": members, "proof": False, "gauntlet_bypass": False,
                   "counterfactual": cf}
        if dry_run:
            ids.append("dry:" + hashlib.sha256(f"{source_id}|{fam}|{archetype}".encode()).hexdigest()[:12])
            continue
        try:
            did, made = reg.record_discovery(
                source_id=source_id, source_type=SOURCE_TYPE, mechanism=mechanism,
                origin=ORIGIN, generator=f"archaeology:{family}", assets=[], sessions=["all"],
                horizons=["unknown"], information="public behavioural record",
                actor="observable public-system population",
                economic_rationale=f"{mechanism}; inferred from {archetype}, not copied trades",
                falsifier=falsifier, required_data=["public record", "desk PIT bars"],
                confidence=0.2, exact_rule=f"{archetype}|{fam}", payload=payload, conn=conn)
            ids.append(did)
            recorded += int(bool(made)); existing += int(not made)
        except Exception:
            errors += 1
    return {"archetype": archetype, "competing": explanation_table([archetype])[0]["competing"],
            "counterfactual": cf,
            "discoveries": {"recorded": recorded, "existing": existing, "errors": errors,
                            "ids": ids}}

