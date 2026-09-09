"""WHERE ALPHA IS LIKELY TO EMERGE NEXT, from the desk's own record of where it emerged before.

MEASURED 2026-09-08 (Tier-1 programme item P15): everything the desk measures says where the
opportunity ISN'T -- the coverage gap, the empty clusters, the binding cause. Nothing forecasts
where it is likely to appear, so the generators are pointed by absence rather than by
expectation, and a symbol/family cell that certified twice this month competes for the same
attention as one that has been buried four times since June.

THE FORECAST IS THE HYPOTHESIS GRAPH READ FORWARD. Every candidate the compiler minted and every
verdict the gauntlet returned is a row with a symbol, a family, a fate and a stamp. Per cell
(symbol, family) that gives a certify rate, a burial rate, and how recently each happened; the
emergence score is the Laplace certify rate discounted by the age of the last success and by
the burial count in the cell's own region -- so a cell that certified recently and has not
been buried ranks first, a cell nobody has judged ranks by its family's rate (the family
prior), and a cell buried repeatedly ranks last however often a crawler re-names it.

THREE LISTS, NOT ONE. `ranked` is where to look; `unexplored` is cells the compiler has named
and nobody has judged (BORN only) -- the frontier the docket already holds; `stale_graveyard`
is cells whose last burial is older than STALE_D, which a new regime may have revived and
which the novelty gate would otherwise keep buried for ever. Everything is READ-ONLY and a
report; the deepening worker and the EVSI docket are the consumers, and they decide.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = BASE / "reports" / "opportunity_forecast.json"
HALF_LIFE_D = 45.0      # a success 45 days old counts half; the same clock the forward bar uses x3
STALE_D = 180.0         # a burial older than this is a fact about a regime, not about the cell
TOP = 40


def _age_d(stamp: Any, now: datetime) -> float | None:
    try:
        d = datetime.fromisoformat(str(stamp))
        d = d if d.tzinfo else d.replace(tzinfo=UTC)
        return max(0.0, (now - d).total_seconds() / 86400.0)
    except (TypeError, ValueError):
        return None


def cells(rows: list[dict[str, Any]], now: datetime) -> dict[tuple[str, str], dict[str, Any]]:
    """Per (symbol, family): fate counts and the age of the newest row per fate."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        key = (str(r.get("symbol") or "").upper(), str(r.get("family") or ""))
        if not key[0] or not key[1]:
            continue
        c = out.setdefault(key, {"fates": defaultdict(int), "newest": {}, "sources": set()})
        fate = str(r.get("fate") or "BORN")
        c["fates"][fate] += 1
        age = _age_d(r.get("at"), now)
        if age is not None and (fate not in c["newest"] or age < c["newest"][fate]):
            c["newest"][fate] = age
        if r.get("source"):
            c["sources"].add(str(r["source"]))
    return out


def family_prior(cell_map: dict[tuple[str, str], dict[str, Any]]) -> dict[str, float]:
    """Laplace certify rate per family over judged rows -- the prior an unjudged cell inherits."""
    cert: dict[str, int] = defaultdict(int)
    judged: dict[str, int] = defaultdict(int)
    for (_, fam), c in cell_map.items():
        f = c["fates"]
        cert[fam] += f.get("CERTIFIED", 0)
        judged[fam] += f.get("CERTIFIED", 0) + f.get("FAILED", 0) + f.get("BURIED", 0) \
            + f.get("RETIRED", 0)
    return {fam: (cert[fam] + 1.0) / (judged[fam] + 2.0) for fam in judged}


def score(c: dict[str, Any], prior: float) -> dict[str, Any]:
    f = c["fates"]
    certified = f.get("CERTIFIED", 0)
    judged = certified + f.get("FAILED", 0) + f.get("BURIED", 0) + f.get("RETIRED", 0)
    rate = (certified + 1.0) / (judged + 2.0) if judged else prior
    basis = "cell" if judged else "family_prior"
    age = c["newest"].get("CERTIFIED")
    recency = math.exp(-math.log(2) * age / HALF_LIFE_D) if age is not None else 0.5
    burials = f.get("BURIED", 0) + f.get("FAILED", 0)
    penalty = 1.0 / (1.0 + burials)
    return {"score": round(rate * recency * penalty, 6), "certify_rate": round(rate, 4),
            "basis": basis, "judged": judged, "certified": certified, "burials": burials,
            "last_success_age_d": round(age, 1) if age is not None else None,
            "born": f.get("BORN", 0), "sources": sorted(c["sources"])[:6]}


def forecast(rows: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    cmap = cells(rows, now)
    prior = family_prior(cmap)
    ranked, unexplored, stale = [], [], []
    for (sym, fam), c in cmap.items():
        s = score(c, prior.get(fam, 0.05))
        entry = {"symbol": sym, "family": fam, **s}
        f = c["fates"]
        judged = s["judged"]
        if judged == 0 and f.get("BORN", 0) > 0:
            unexplored.append(entry)
        else:
            ranked.append(entry)
        last_burial = min((a for k, a in c["newest"].items() if k in ("BURIED", "FAILED")),
                          default=None)
        if last_burial is not None and last_burial >= STALE_D and s["certified"] == 0:
            stale.append({**entry, "last_burial_age_d": round(last_burial, 1)})
    ranked.sort(key=lambda e: (-e["score"], e["symbol"], e["family"]))
    unexplored.sort(key=lambda e: (-e["score"], -e["born"], e["symbol"]))
    stale.sort(key=lambda e: (-e["last_burial_age_d"], e["symbol"]))
    return {
        "at": now.isoformat(timespec="seconds"), "rows": len(rows), "cells": len(cmap),
        "family_prior": {k: round(v, 4) for k, v in sorted(prior.items())},
        "ranked": ranked[:TOP], "unexplored": unexplored[:TOP], "stale_graveyard": stale[:TOP],
        "counts": {"ranked": len(ranked), "unexplored": len(unexplored), "stale": len(stale)},
        "parameters": {"half_life_d": HALF_LIFE_D, "stale_d": STALE_D},
        "why": ("score = Laplace certify rate x 2^(-age of last success / half-life)"
                " / (1 + burials); "
                "an unjudged cell carries its family's rate; a report, the docket decides"),
        "status": "MEASURED" if cmap else "UNMEASURED",
    }


def main(argv: list[str] | None = None) -> int:
    from libs.research.hypothesis_graph import Graph
    try:
        rows = Graph().rows()
    except Exception as exc:
        rows, err = [], f"{type(exc).__name__}: {exc}"
    else:
        err = ""
    doc = forecast(rows)
    if err:
        doc["status"], doc["why_unmeasured"] = "UNMEASURED", err
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    head = ", ".join(f"{e['symbol']}.{e['family']}={e['score']}" for e in doc["ranked"][:3])
    print(f"opportunity forecast: {doc['status']} over {doc['cells']} cells; "
          f"top [{head}]; {doc['counts']['unexplored']} unexplored, "
          f"{doc['counts']['stale']} stale burials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
