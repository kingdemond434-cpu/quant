"""WHAT A REJECTED CONTRACT COSTS A TIER S ORGAN: ITS AUTHORITY, NEVER ITS RESEARCH.

The admission rule says a layer ships only with a measurable contract. Before 2026-09-30 a
REJECTED verdict was a line in CONTRACTS.json that changed nothing. Now an organ whose every
contracted layer is REJECTED is SUSPENDED: its STEERING outputs stop steering anything, while
the organ keeps running so its metric can still recover (a suspended organ that stopped running
could never be re-admitted).

What "steering" means, per consumer (every one calls `suspended(<organ>)` before acting):
  * `market`         -> cycle_pricing ignores researcher_prices.json (no leg is repriced by it);
  * `grammar`        -> grammar_bias returns {} (the generators draw the uniform grammar);
  * `topology`       -> its weights stop ordering the orthogonal emissions, and the market
                        stops discounting producers by ancestry novelty;
  * `genomes`        -> every genome draws its candidates at random (no falsify ordering);
  * `failure_memory` -> emissions are no longer re-ordered by the mapped dead regions;
  * `frontier`       -> the market's frontier factor is 1 for every producer;
  * `predictions`    -> the market's honesty term is 1 for every producer;
  * `red_queen`      -> its defenders are not registered as validator challengers;
  * `arena`          -> its verdicts propose nothing to the scheduler tournament (its contract is
                        the `leg_contracts` row with `steers: arena`);
  * `twin`           -> a challenger that beats the incumbent is PENDING_AUTHORITY, not ADOPTED;
  * `self_model`     -> the implementer takes no rows from its docket;
  * `online_fdr`, `immune` -> the promotion door (`promotion_authority`) ignores their verdicts.

WHAT IS NEVER STOPPED: hypothesis emission. The standing order is that research generation is
never reduced, so a suspended organ's rows still reach the compiler and are still judged; only
its power to re-weight other organs' compute or sampling is withdrawn. Two-sided: re-admission is
automatic on the first hour any of its layers reads ADMITTED or UNMEASURED again.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "desks" / "mt5" / "data" / "tier_s" / "AUTHORITY.json"
#: how old the verdict file may be before its suspensions lapse (a stale verdict is no verdict)
MAX_AGE_H = 6.0


def compute(ledger: Mapping[str, Any], verdicts: Mapping[str, Mapping[str, Any]]
            ) -> dict[str, Any]:
    """organ -> {suspended, layers, verdicts}. Suspended only when EVERY layer is REJECTED."""
    by_organ: dict[str, list[tuple[str, str]]] = {}
    for layer in ledger.get("layers") or []:
        organ = str((layer.get("contract") or {}).get("organ") or "")
        if not organ:
            continue
        lid = str(layer.get("id"))
        v = str((verdicts.get(lid) or {}).get("verdict") or "UNMEASURED")
        by_organ.setdefault(organ, []).append((lid, v))
    # A LEG CONTRACT MAY GOVERN A STEERING ORGAN TOO (`steers`, e.g. the arena's contract, whose
    # verdicts reach the scheduler only through the tournament): its verdict joins that organ's.
    for lc in ledger.get("leg_contracts") or []:
        organ = str(lc.get("steers") or "") if isinstance(lc, Mapping) else ""
        if not organ:
            continue
        lid = f"leg:{lc.get('leg')}"
        v = str((verdicts.get(lid) or {}).get("verdict") or "UNMEASURED")
        by_organ.setdefault(organ, []).append((lid, v))
    organs = {o: {"suspended": all(v == "REJECTED" for _l, v in rows),
                  "layers": [lid for lid, _v in rows],
                  "verdicts": dict(rows)} for o, rows in by_organ.items()}
    return {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "organs": organs,
            "suspended": sorted(o for o, r in organs.items() if r["suspended"]),
            "rule": "an organ whose every contracted layer is REJECTED loses its steering "
                    "authority until one reads ADMITTED or UNMEASURED; its hypothesis emissions "
                    "are never stopped"}


def suspended(organ: str, path: Path | None = None, max_age_h: float = MAX_AGE_H) -> bool:
    try:
        doc = json.loads((path or AUTHORITY).read_text("utf-8"))
        at = datetime.fromisoformat(str(doc.get("generated_utc")))
    except (OSError, ValueError, TypeError):
        return False
    if (datetime.now(UTC) - at).total_seconds() > max_age_h * 3600:
        return False
    return organ in (doc.get("suspended") or [])
