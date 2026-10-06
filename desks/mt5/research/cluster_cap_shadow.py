"""THE PER-CLUSTER CAP, RUN IN SHADOW (producer law §19, BREADTH-0326): never enforced, measured.

Producer law §19 asks for a certificate cap per saturated effective cluster: one champion, a small
challenger set, the rest archived. The research side is enforced (the saturation map's
champion / challengers / archive, and `champion_cap`, which counts breadth only). THE CAPITAL SIDE
IS NOT ENFORCED AND WILL NOT BE, for two standing orders:

  * AUTOMATIC PROMOTION (principal, 2026-09-04): every promotion candidate with a ten-gate
    certificate goes LIVE on the cycle its clock matures, with no waiting, no permission and no
    kill-by-comparison. A cap on LIVE certificates per cluster is exactly such a kill.
  * GROWTH GOVERNANCE RULE 1: every risk-reduction mechanism must PROVE that it raises robust
    forward E[log W]. An untested cap that blocks promotions is a veto without that proof.

So the cap runs here as a SHADOW. Each hourly `alpha_breadth` pass reads the promoter's LIVE rows
(data/sleeves.json, READ-ONLY -- the promoter and every sealed file are untouched), maps each
LIVE sleeve to its saturation-map cluster, and records which promotions a cap of
1 champion + CHALLENGERS would have blocked in a SATURATED cluster, in promotion order. For each
it writes the missed-growth line in research/missed_growth.py's ledger convention
(`{day, rail, value, at}`, value in log-wealth per day, NEGATIVE when the rail would have cost
growth): -admission.delta_elogw_per_day where the allocator measured it, otherwise UNMEASURED with
the undeployed risk fraction published (the E8 duplicate-guard convention: risk, not profit).
The lines accumulate in the shadow's own ledger, so the cap's Rule-1 verdict can be read off
its own evidence; nothing is appended to the live missed-growth ledger, whose rails are the
sealed registry's.

READ-ONLY BY CONSTRUCTION: this module opens sleeves.json for reading and writes only
reports/CLUSTER_CAP_SHADOW.json and reports/cluster_cap_shadow_ledger.jsonl.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "CLUSTER_CAP_SHADOW.json"
LEDGER = DESK / "reports" / "cluster_cap_shadow_ledger.jsonl"
RAIL = "cluster_cap_shadow"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
REASON = ("COVERED_SHADOW: the per-cluster cap on LIVE certificates is measured in shadow and "
          "never enforced. Enforcing it would block promotions that AUTOMATIC PROMOTION (standing "
          "order 2026-09-04) sends LIVE without waiting or kill-by-comparison, and growth "
          "governance Rule 1 admits a risk-reduction mechanism only once it proves it raises "
          "robust forward E[log W]. This shadow is that proof's evidence: each blocked promotion "
          "carries its missed-growth line.")
_PARAM_KEYS = ("stop_atr", "target_atr", "max_hold", "side", "window")


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _cs() -> Any:
    try:
        from research import certificate_saturation as cs
    except ImportError:                                                  # pragma: no cover
        import certificate_saturation as cs  # type: ignore[import-not-found,no-redef]
    return cs


def live_rows(sleeves: Any) -> list[dict[str, Any]]:
    rows = sleeves if isinstance(sleeves, list) else (
        (sleeves or {}).get("sleeves") if isinstance(sleeves, Mapping) else None)
    return [dict(r) for r in rows or []
            if isinstance(r, Mapping) and str(r.get("status") or "").upper() == "LIVE"]


def cluster_of(row: Mapping[str, Any]) -> str:
    cs = _cs()
    params = dict(row.get("params") or {}) if isinstance(row.get("params"), Mapping) else {}
    params.update({k: row[k] for k in _PARAM_KEYS if k in row})
    ax = cs.axes_of(str(row.get("symbol") or ""), str(row.get("family") or ""), params,
                    timeframe=row.get("timeframe"),
                    session=row.get("session") or row.get("selector"))
    return str(cs.cluster_key(ax))


def _order_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("promoted_at") or row.get("restored_at") or "~"),
            str(row.get("name") or ""))


def missed_growth_line(row: Mapping[str, Any], day: str, at: str) -> dict[str, Any]:
    """The ledger line in research/missed_growth.py's convention for one blocked promotion."""
    adm = row.get("admission") if isinstance(row.get("admission"), Mapping) else {}
    d = _num((adm or {}).get("delta_elogw_per_day"))
    line: dict[str, Any] = {"day": day, "rail": RAIL, "sleeve": row.get("name"), "at": at}
    if d is not None:
        line["value"] = -d
        line["status"] = MEASURED
    else:
        line["value"] = None
        line["status"] = UNMEASURED
        line["undeployed_risk_frac"] = _num(row.get("risk_frac"))
        line["why"] = ("the allocator has not measured this sleeve's delta E[log W]; the risk "
                       "the cap would have left undeployed is published, never priced as zero")
    return line


def build(*, sat: Mapping[str, Any], sleeves: Any = None,
          now: datetime | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    at, day = t.isoformat(timespec="seconds"), t.date().isoformat()
    if sat.get("status") != MEASURED:
        return {"status": UNMEASURED, "at": at, "why": "saturation map unmeasured",
                "reason": REASON}
    cs = _cs()
    cap = 1 + int(cs.CHALLENGERS)
    if sleeves is None:
        try:
            sleeves = json.loads(SLEEVES.read_text("utf-8-sig"))
        except (OSError, ValueError):
            return {"status": UNMEASURED, "at": at, "why": "data/sleeves.json unreadable",
                    "reason": REASON}
    live = live_rows(sleeves)
    clusters = sat.get("clusters") if isinstance(sat.get("clusters"), Mapping) else {}
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in live:
        by[cluster_of(r)].append(r)
    blocked: list[dict[str, Any]] = []
    per_cluster: dict[str, Any] = {}
    for ck, rows in sorted(by.items()):
        state = str(((clusters or {}).get(ck) or {}).get("state") or "NOT_IN_MAP")
        rows.sort(key=_order_key)
        would = rows[cap:] if state == "SATURATED" else []
        per_cluster[ck] = {"state": state, "live": len(rows), "cap": cap if state == "SATURATED"
                           else None, "would_block": [r.get("name") for r in would]}
        for r in would:
            blocked.append({"sleeve": r.get("name"), "cluster": ck,
                            "promoted_at": r.get("promoted_at") or r.get("restored_at"),
                            "missed_growth": missed_growth_line(r, day, at)})
    vals = [b["missed_growth"]["value"] for b in blocked if b["missed_growth"]["value"] is not None]
    return {
        "status": MEASURED, "at": at, "rail": RAIL, "enforced": False,
        "reason": REASON, "cap_per_saturated_cluster": cap,
        "n_live": len(live), "n_clusters": len(by),
        "n_saturated_clusters_live": sum(1 for v in per_cluster.values()
                                         if v["state"] == "SATURATED"),
        "n_would_block": len(blocked),
        "missed_growth": {"lines": len(blocked), "measured": len(vals),
                          "sum_logw_per_day": round(sum(vals), 10) if vals else None,
                          "unmeasured": len(blocked) - len(vals),
                          "undeployed_risk_frac": round(sum(
                              float(b["missed_growth"].get("undeployed_risk_frac") or 0.0)
                              for b in blocked), 6)},
        "would_block": blocked, "clusters": per_cluster,
        "rule": (f"shadow cap = 1 champion + {cs.CHALLENGERS} challengers per SATURATED cluster, "
                 "in promotion order; read-only on the promoter's rows; never changes a "
                 "promotion"),
    }


def publish(doc: Mapping[str, Any], path: Path | None = None,
            ledger: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(p)
    lp = ledger or p.with_name(LEDGER.name)
    seen: set[tuple[str, str]] = set()
    try:
        for ln in lp.read_text("utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                seen.add((str(r.get("day")), str(r.get("sleeve"))))
    except (OSError, ValueError):
        pass
    new = [b["missed_growth"] for b in doc.get("would_block") or []
           if (str(b["missed_growth"].get("day")), str(b["missed_growth"].get("sleeve")))
           not in seen]
    if new:
        with lp.open("a", encoding="utf-8") as fh:
            for row in new:
                fh.write(json.dumps(row, default=str) + "\n")
    return p


__all__ = ["OUT", "RAIL", "REASON", "build", "cluster_of", "live_rows", "missed_growth_line",
           "publish"]
