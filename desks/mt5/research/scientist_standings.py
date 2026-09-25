"""B7 -- THE SCIENTISTS' LEAGUE TABLE, IN THE ONLY CURRENCY THAT PAYS: live marginal E[log W].

THE BLUEPRINT ITEM: "AI scientist tournament scored on future certified marginal Elog". THE GAP,
in the ledger's words: "scored on report quality and certification, not on live marginal Elog".

That gap is exact. `scientist_tournament` scores a panel on the quality of its reasoning about a
subject, which is the right way to judge a REVIEW and the wrong way to judge a SCIENTIST. A desk
that promotes the seat with the best prose is running a writing competition. The question this
answers instead is: of everything this scientist proposed, what did the funded book actually earn
-- in log-wealth per day, and in realised R on live deals.

BOTH HALVES ARE READ, NEITHER IS INVENTED:
  dElogW/day  `reports/allocator_attribution.json`.information.sources[*] -- the allocator's own
              growth attribution per proposing source, over its measured window.
  realised R  `reports/CREDIT_ASSIGNMENT.json`.by_scientist -- live deals credited through the
              sleeve that placed them to the certificate to the scientist, when the live ledger
              is above its floor; the artifact says which basis it used and this carries it.

A SCIENTIST WITH NO EVIDENCE IS UNMEASURED, NEVER LAST. This is the whole difficulty of scoring
research: a seat that proposed three cells that have not finished their forward clocks has not
lost, and ranking it below a seat with a small negative would spend the desk's compute on the
wrong signal. Unmeasured scientists are listed with their reason and keep an EXPLORATION SHARE
(`min_share`), because failure to discover is never evidence there is nothing to discover (L1.25)
and because the principal's standing order is that the desk never gets smaller.

    python desks/mt5/research/scientist_standings.py [--once] [--budget-s N]
        -> desks/mt5/reports/SCIENTIST_STANDINGS.json
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
R = DESK / "reports"
OUT = R / "SCIENTIST_STANDINGS.json"
ATTRIBUTION = R / "allocator_attribution.json"
CREDIT = R / "CREDIT_ASSIGNMENT.json"

#: The floor share of attention an unmeasured or negative scientist keeps. Ranking orders the
#: queue; it never empties a seat, because a seat with no compute can never produce the evidence
#: that would change its rank -- which is how a league table becomes a self-fulfilling prophecy.
MIN_SHARE = 0.05
#: Trades behind a realised-R number before it outranks an allocator attribution. Below it the
#: realised term is carried and reported but weighted by n/(n+k).
CREDIT_K = 30.0
#: An input older than this is reported with its age and still used -- staleness is a fact about
#: the evidence, not a reason to pretend there is none.
STALE_H = 48.0


def _read(p: Path) -> dict[str, Any]:
    try:
        doc = json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _age_h(p: Path) -> float | None:
    try:
        return (time.time() - p.stat().st_mtime) / 3600.0
    except OSError:
        return None


def measure() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    att, cred = _read(ATTRIBUTION), _read(CREDIT)
    info = att.get("information") if isinstance(att.get("information"), dict) else {}
    sources = info.get("sources") if isinstance(info.get("sources"), dict) else {}

    rows: dict[str, dict[str, Any]] = {}
    for src, row in sources.items():
        if not isinstance(row, dict):
            continue
        try:
            v = float(row.get("delta_elogw_per_day"))
        except (TypeError, ValueError):
            continue
        rows.setdefault(str(src), {})["delta_elogw_per_day"] = round(v, 9)
        rows[str(src)]["elogw_basis"] = str(info.get("basis") or "allocator_attribution")

    for row in (cred.get("by_scientist") or []):
        if not isinstance(row, dict):
            continue
        src = str(row.get("source") or "")
        if not src:
            continue
        r = rows.setdefault(src, {})
        try:
            realised, n = float(row.get("realised_r") or 0.0), int(row.get("n_trades") or 0)
        except (TypeError, ValueError):
            continue
        r["realised_r"] = round(realised, 4)
        r["n_trades"] = n
        r["r_per_trade"] = round(realised / n, 5) if n else None
        r["credit_basis"] = str(cred.get("evidence_source") or "none")

    out: list[dict[str, Any]] = []
    for src, r in rows.items():
        elog = r.get("delta_elogw_per_day")
        rpt = r.get("r_per_trade")
        n = int(r.get("n_trades") or 0)
        shrunk = (float(rpt) * (n / (n + CREDIT_K))) if rpt is not None else None
        # ONE SCORE, AND IT SAYS WHICH TERMS IT HAS. dE[log W] per day is the desk's objective;
        # realised R per trade is the same truth one step earlier and enters shrunk by its own
        # sample size. A scientist carrying only one of the two is scored on that one and the
        # row says so -- never a zero substituted for an absence.
        terms = [x for x in (elog, shrunk) if x is not None]
        score = sum(terms) if terms else None
        out.append({
            "scientist": src, "score": (round(score, 9) if score is not None else None),
            "status": "MEASURED" if terms else "UNMEASURED",
            "terms": {"delta_elogw_per_day": elog, "r_per_trade_shrunk": (
                round(shrunk, 6) if shrunk is not None else None)},
            "n_trades": n,
            "why": ("scored on " + " + ".join(
                [t for t, v in (("dE[logW]/day", elog), ("realised R/trade", shrunk))
                 if v is not None]) if terms else
                "no allocator attribution and no credited live deal: UNMEASURED, not last"),
            **{k: v for k, v in r.items() if k.endswith("_basis")},
        })
    measured = [r for r in out if r["status"] == "MEASURED"]
    measured.sort(key=lambda r: -float(r["score"] or 0.0))
    unmeasured = sorted((r for r in out if r["status"] != "MEASURED"),
                        key=lambda r: str(r["scientist"]))
    ranked = measured + unmeasured
    # SHARES: rank order with a floor, never a winner-take-all. The consumers below use this to
    # ORDER their queue; nothing is excluded, so a seat can always earn its way back.
    n = len(ranked) or 1
    raw = [max(0.0, float(r["score"] or 0.0)) for r in ranked]
    tot = sum(raw)
    # THE FLOOR IS A REAL FLOOR, NOT A ROUNDING ERROR. Every seat keeps MIN_SHARE, or an equal
    # split of half the budget when there are too many seats for that to fit -- so fifteen seats
    # of which one has evidence still leaves two thirds of the attention with the fourteen that
    # have not yet had the chance to produce any. The measured leader takes the rest, which is
    # the whole of the ranking's authority and is plenty.
    floor = min(MIN_SHARE, 0.5 / n)
    for i, r in enumerate(ranked):
        share = (raw[i] / tot) if tot > 0 else 1.0 / n
        r["share"] = round(floor + (1.0 - n * floor) * share, 4)
        r["rank"] = i + 1
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK" if measured else "UNMEASURED",
        "n_scientists": len(ranked), "n_measured": len(measured),
        "standings": ranked,
        "inputs": {"allocator_attribution_age_h": _age_h(ATTRIBUTION),
                   "credit_assignment_age_h": _age_h(CREDIT),
                   "credit_basis": str(cred.get("evidence_source") or "absent"),
                   "n_live_deals": cred.get("n_live_deals"),
                   "stale_after_h": STALE_H},
        "rule": ("a scientist is scored on what the funded book earned from its proposals -- "
                 "log-wealth per day from the allocator's attribution plus realised R per trade "
                 "from live deals, shrunk by n/(n+30). Report quality is not a term. Unmeasured "
                 "is not last, and every seat keeps an exploration floor."),
        "consumers": ["desks/mt5/research/scientist_tournament.py::_subjects (queue order)",
                      "desks/mt5/research/frontier_ceo.py::propose (proposal rank)"],
    }


def order(names: list[str]) -> list[str]:
    """Consumer helper: the given scientists, best-evidenced first, unmeasured after, unknown
    last -- with every name kept. Nothing is dropped by this table, ever."""
    doc = _read(OUT)
    rank = {str(r.get("scientist")): int(r.get("rank") or 10_000)
            for r in (doc.get("standings") or []) if isinstance(r, dict)}
    return sorted(names, key=lambda n: (rank.get(n, 10_000), n))


def score_of(name: str) -> tuple[float | None, str]:
    """This scientist's live score and why, or (None, reason) when nothing has measured it."""
    doc = _read(OUT)
    for r in (doc.get("standings") or []):
        if isinstance(r, dict) and str(r.get("scientist")) == name:
            return (r.get("score"), str(r.get("why")))
    return None, "no standings row for this scientist"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=60.0)
    ap.parse_args(argv)
    doc = measure()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"scientist standings: {doc['status']}  {doc['n_measured']}/{doc['n_scientists']} "
          f"measured (credit basis {doc['inputs']['credit_basis']})")
    for r in doc["standings"][:10]:
        print(f"  {r['rank']:>2}. {str(r['scientist'])[:30]:<30} score={r['score']} "
              f"share={r['share']} {str(r['why'])[:70]}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
