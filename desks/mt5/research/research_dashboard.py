"""THE FINAL RESEARCH DASHBOARD (Tier-5 mandate 162): the twenty-one numbers the mandate says the
institution must report, joined hourly from the artifacts that measure them, plus this session's
organs. Writes desks/mt5/reports/RESEARCH_DASHBOARD.json and the DERIVED page
docs/research/RESEARCH_DASHBOARD.md (never hand-edited; the JSON is the truth).

Every number names its source and reads UNMEASURED when the source is absent. Rates per day are
counted from stamps in the last 24 h, never annualised from a smaller window.

    sources alive / countries / languages   registry `sources` (status, country, language)
    documents/day, mechanisms/day           registry `claims`, `mechanisms` created_at
    observations/day                        registry `discoveries` created_at
    canonical hypotheses/day, raw cells/day registry `research_candidates` (distinct content_hash)
    effective cells/day                     candidates minus search_count re-hits
    cheap screens/day, gauntlet verdicts    universal_gates_external (n_judged, swept_at)
    gauntlet submissions/day                candidates reaching status donated in the window
    survivors, independent survivors        UNIVERSAL_SURVIVORS.n, EFFECTIVE_BREADTH.effective
    forward clocks, live sleeves            sleeves.json STANDBY / LIVE
    effective independent bets              EFFECTIVE_BREADTH.effective.effective_breadth
    conversion backlog                      queue_store pending + discoveries UNPROCESSED
    gauntlet backlog                        candidates with no judged_at
    compute utilization                     compute_ledger hours in 24 h over 24 h of one box
    research value / compute                scaling_laws.json, RESEARCH_ROI.json when present
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

R = BASE / "reports"
OUT = R / "RESEARCH_DASHBOARD.json"
MD = REPO / "docs" / "research" / "RESEARCH_DASHBOARD.md"
GATES = R / "universal_gates_external.json"
SURVIVORS = R / "UNIVERSAL_SURVIVORS.json"
BREADTH = R / "EFFECTIVE_BREADTH.json"
SLEEVES = BASE / "data" / "sleeves.json"
SCALING = R / "scaling_laws.json"
ROI = R / "RESEARCH_ROI.json"
ORGANS = {
    "portfolio_bounty": R / "PORTFOLIO_BOUNTY.json",
    "research_auction": R / "RESEARCH_AUCTION.json",
    "bottleneck_law": R / "BOTTLENECK_LAW.json",
    "research_latency": R / "RESEARCH_LATENCY.json",
    "alpha_replenishment": R / "ALPHA_REPLENISHMENT.json",
    "trade_autopsy": R / "TRADE_AUTOPSY.json",
    "drawdown_alpha_miner": R / "DRAWDOWN_ALPHA_MINER.json",
}
UNMEASURED = "UNMEASURED"


def _lst(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _dct(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def registry_block(now: datetime, conn: Any | None = None) -> dict[str, Any]:
    from libs.moat import registry
    c = conn or registry.connect()
    cut = (now - timedelta(days=1)).isoformat()
    out: dict[str, Any] = {}

    def q(sql: str, *args: Any) -> Any:
        try:
            row = c.execute(sql, args).fetchone()
            return row[0] if row is not None else None
        except Exception:
            return None

    try:
        out["sources_alive"] = q("SELECT COUNT(*) FROM sources WHERE status IS NULL OR status "
                                 "NOT IN ('dead','retired','blocked')")
        out["sources_total"] = q("SELECT COUNT(*) FROM sources")
        out["countries_covered"] = q("SELECT COUNT(DISTINCT country) FROM sources WHERE country "
                                     "IS NOT NULL AND country!=''")
        out["languages_covered"] = q("SELECT COUNT(DISTINCT language) FROM sources WHERE "
                                     "language IS NOT NULL AND language!=''")
        out["documents_per_day"] = q("SELECT COUNT(*) FROM claims WHERE created_at >= ?", cut)
        out["observations_per_day"] = q("SELECT COUNT(*) FROM discoveries WHERE created_at >= ?",
                                        cut)
        out["mechanisms_per_day"] = q("SELECT COUNT(*) FROM mechanisms WHERE created_at >= ?", cut)
        out["raw_cells_per_day"] = q("SELECT COUNT(*) FROM research_candidates WHERE "
                                     "created_at >= ?", cut)
        out["canonical_hypotheses_per_day"] = q("SELECT COUNT(DISTINCT content_hash) FROM "
                                                "research_candidates WHERE created_at >= ?", cut)
        out["effective_cells_per_day"] = q("SELECT COUNT(*) FROM research_candidates WHERE "
                                           "created_at >= ? AND COALESCE(search_count,1) <= 1",
                                           cut)
        out["gauntlet_submissions_per_day"] = q("SELECT COUNT(*) FROM research_candidates WHERE "
                                                "status='donated' AND updated_at >= ?", cut)
        out["gauntlet_backlog"] = q("SELECT COUNT(*) FROM research_candidates WHERE judged_at IS "
                                    "NULL OR judged_at=''")
        out["conversion_backlog_discoveries"] = q("SELECT COUNT(*) FROM discoveries WHERE "
                                                  "state='UNPROCESSED'")
    finally:
        if conn is None:
            c.close()
    return {k: (v if v is not None else UNMEASURED) for k, v in out.items()}


def queue_pending() -> Any:
    try:
        qs = importlib.import_module("queue_store")
        c = qs.counts()
        return int(c.get("pending", 0)) if isinstance(c, dict) else UNMEASURED
    except Exception:
        return UNMEASURED


def compute_block(now: datetime) -> dict[str, Any]:
    try:
        from libs.ops.compute_ledger import rows
        rs = rows(window_days=1)
    except Exception:
        return {"hours_24h": UNMEASURED, "utilization": UNMEASURED}
    hours = sum(float(r.get("wall_s") or 0.0) for r in rs) / 3600.0
    return {"hours_24h": round(hours, 3), "utilization": round(hours / 24.0, 4),
            "costed_runs_24h": len(rs), "basis": "compute_ledger wall_s over 24 h of one box"}


def lineage_concentration(survivors: dict[str, Any]) -> dict[str, Any]:
    """HHI of the survivor set by family -- the monoculture reading, REPORTED and never capped.

    The family is the second token of the survivor's cell (`<sym> <family> ...`) or its
    `family` field. 1.0 is one family holding everything; 1/n is n equal families. An organ
    that reads this may raise exploration elsewhere; nothing may cap the leading family."""
    sv = survivors.get("survivors")
    items = list(sv.values()) if isinstance(sv, dict) else _lst(sv)
    fams: dict[str, int] = {}
    for s in items:
        if not isinstance(s, dict):
            continue
        fam = str(s.get("family") or "")
        if not fam:
            toks = str(s.get("cell") or "").split()
            fam = toks[1] if len(toks) > 1 else (toks[0] if toks else "")
        if fam:
            fams[fam] = fams.get(fam, 0) + 1
    n = sum(fams.values())
    if n == 0:
        return {"status": UNMEASURED, "n_survivors": 0, "capped": False}
    shares = {k: v / n for k, v in fams.items()}
    top = max(shares.items(), key=lambda kv: kv[1])
    return {"status": "MEASURED", "n_survivors": n, "n_families": len(fams),
            "hhi": round(sum(v * v for v in shares.values()), 4),
            "top_family": top[0], "top_share": round(top[1], 4), "capped": False,
            "rule": "reported for exploration to rise elsewhere; the leader is never capped"}


def gates_block(gates: dict[str, Any], now: datetime) -> dict[str, Any]:
    swept = gates.get("swept_at") or gates.get("at")
    recent = False
    try:
        d = datetime.fromisoformat(str(swept).replace("Z", "+00:00"))
        recent = (now - (d if d.tzinfo else d.replace(tzinfo=UTC))) <= timedelta(days=1)
    except (TypeError, ValueError):
        pass
    if not gates:
        return {"cheap_screens_per_day": UNMEASURED, "gauntlet_verdicts_per_day": UNMEASURED}
    n_judged = gates.get("n_judged")
    return {"cheap_screens_per_day": gates.get("n_cells") if recent else 0,
            "gauntlet_verdicts_per_day": n_judged if recent else 0,
            "last_sweep": swept, "survivors_passing_all": gates.get("survivors_passing_all")}


def build(now: datetime | None = None, conn: Any | None = None,
          gates: dict[str, Any] | None = None, survivors: dict[str, Any] | None = None,
          breadth: dict[str, Any] | None = None, sleeves: dict[str, Any] | None = None,
          organs: dict[str, dict[str, Any]] | None = None,
          with_registry: bool = True) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    gates = gates if gates is not None else _read(GATES)
    survivors = survivors if survivors is not None else _read(SURVIVORS)
    breadth = breadth if breadth is not None else _read(BREADTH)
    sleeves = sleeves if sleeves is not None else _read(SLEEVES)
    organs = organs if organs is not None else {k: _read(p) for k, p in ORGANS.items()}
    unmeasured: list[str] = []
    reg: dict[str, Any] = {}
    if with_registry:
        try:
            reg = registry_block(now, conn)
        except Exception as exc:
            unmeasured.append(f"registry unavailable: {type(exc).__name__}: {exc}")
    rows = _lst(sleeves.get("sleeves"))
    status = [str(r.get("status")) for r in rows if isinstance(r, dict)]
    eff = _dct(breadth.get("effective"))
    sv = survivors.get("survivors")
    n_surv = len(sv) if isinstance(sv, (dict, list)) else survivors.get("n", UNMEASURED)
    metrics: dict[str, Any] = {
        "sources_alive": reg.get("sources_alive", UNMEASURED),
        "countries_covered": reg.get("countries_covered", UNMEASURED),
        "languages_covered": reg.get("languages_covered", UNMEASURED),
        "documents_per_day": reg.get("documents_per_day", UNMEASURED),
        "observations_per_day": reg.get("observations_per_day", UNMEASURED),
        "mechanisms_per_day": reg.get("mechanisms_per_day", UNMEASURED),
        "canonical_hypotheses_per_day": reg.get("canonical_hypotheses_per_day", UNMEASURED),
        "raw_cells_per_day": reg.get("raw_cells_per_day", UNMEASURED),
        "effective_cells_per_day": reg.get("effective_cells_per_day", UNMEASURED),
        **gates_block(gates, now),
        "gauntlet_submissions_per_day": reg.get("gauntlet_submissions_per_day", UNMEASURED),
        "survivors": n_surv,
        "independent_survivors": eff.get("effective_breadth", UNMEASURED),
        "forward_clocks": status.count("STANDBY"),
        "live_sleeves": status.count("LIVE"),
        "effective_independent_bets": eff.get("effective_breadth", UNMEASURED),
        "lineage_concentration": lineage_concentration(survivors),
        "conversion_backlog": {"queue_pending": queue_pending(),
                               "discoveries_unprocessed":
                                   reg.get("conversion_backlog_discoveries", UNMEASURED)},
        "gauntlet_backlog": reg.get("gauntlet_backlog", UNMEASURED),
        "compute_utilization": compute_block(now),
        "research_value_per_compute": {
            "scaling_laws": (_read(SCALING).get("headline") or _read(SCALING).get("fit")
                             or UNMEASURED),
            "research_roi": _read(ROI).get("headline") or UNMEASURED},
    }
    organ_lines = {
        "portfolio_bounty": organs.get("portfolio_bounty", {}).get("headline", UNMEASURED),
        "research_auction": organs.get("research_auction", {}).get("headline", UNMEASURED),
        "bottleneck_law": organs.get("bottleneck_law", {}).get("headline", UNMEASURED),
        "research_latency": organs.get("research_latency", {}).get("headline", UNMEASURED),
        "alpha_replenishment": organs.get("alpha_replenishment", {}).get("headline", UNMEASURED),
        "trade_autopsy": organs.get("trade_autopsy", {}).get("headline", UNMEASURED),
        "drawdown_alpha_miner": organs.get("drawdown_alpha_miner", {}).get("headline",
                                                                            UNMEASURED),
    }
    n_unm = sum(1 for v in metrics.values() if v == UNMEASURED)
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"), "metrics": metrics, "organs": organ_lines,
        "n_metrics": len(metrics), "n_unmeasured_metrics": n_unm, "unmeasured": unmeasured,
        "derived_page": "docs/research/RESEARCH_DASHBOARD.md",
        "consumer": "docs/research/RESEARCH_DASHBOARD.md (derived), check_tier5_audit (162)",
        "rule": ("each number names its source; an absent source reads UNMEASURED; per-day rates "
                 "are counted from the last 24 h of stamps, never annualised"),
    }
    doc["headline"] = (f"{len(metrics) - n_unm}/{len(metrics)} metrics measured; "
                       f"live {metrics['live_sleeves']}, forward {metrics['forward_clocks']}, "
                       f"survivors {metrics['survivors']}, n_eff "
                       f"{metrics['effective_independent_bets']}")
    return doc


def render(doc: dict[str, Any]) -> str:
    out = ["# Research dashboard (derived -- edit nothing here)", "",
           f"Generated {doc['at']} by `desks/mt5/research/research_dashboard.py` "
           f"(hourly leg `research_dashboard`). {doc['headline']}.", "",
           "| metric | value |", "|---|---|"]
    for k, v in doc["metrics"].items():
        out.append(f"| {k} | {json.dumps(v, default=str) if isinstance(v, dict) else v} |")
    out += ["", "## Organs", "", "| organ | headline |", "|---|---|"]
    for k, v in doc["organs"].items():
        out.append(f"| {k} | {v} |")
    if doc.get("unmeasured"):
        out += ["", "## Unmeasured", ""] + [f"- {u}" for u in doc["unmeasured"]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--md", type=Path, default=MD)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = build()
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    doc["budget_s"] = a.budget_s
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    a.md.parent.mkdir(parents=True, exist_ok=True)
    a.md.write_text(render(doc), "utf-8")
    print(f"research dashboard: {doc['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
