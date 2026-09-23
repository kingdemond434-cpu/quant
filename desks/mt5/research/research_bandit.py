"""Daily research-direction budget: run the bandit, print the shares. See `libs.research.bandit`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import bandit  # noqa: E402

#: The growth attribution's per-source verdict. `allocator_attribution` names a source DEAD
#: INFORMATION when it has burned trials past the exploration floor and bought no growth in the
#: funded book; that naming only becomes a decision where the budget is set, which is here.
ATTRIBUTION = _DESK / "reports" / "allocator_attribution.json"


def dead_information() -> list[str]:
    """Sources the growth attribution named DEAD INFORMATION.

    A dead SOURCE does not stop the ARM -- an arm is many sources, and killing an arm for one
    exhausted feed would throw away the others with it. It stops being a REASON to fund the arm,
    which is what the share is computed from.
    """
    import json
    try:
        doc = json.loads(ATTRIBUTION.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return sorted(str(s) for s in ((doc.get("information") or {}).get("dead_information") or []))


def run(seed: int = 0) -> dict:
    d = bandit.run(seed=seed)
    d["dead_information"] = dead_information()
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    d = run(seed=a.seed)
    # AUTHORITY IS CLAIMED BY THE ORGAN THAT OBEYED (2026-09-16): `research_budget` records which
    # legs spent by these shares; this only reads that record back onto its own report.
    try:
        import json as _json

        from research_budget import authority as _authority
        ok, why = _authority()
        # AND THE WHOLE CYCLE'S PRICES, NOT JUST THESE TWO LEGS (Tier-1 B27, 2026-09-22).
        # `research_budget` knows the two legs whose arms this bandit prices; `cycle_pricing`
        # applies the price stack to EVERY leg's seconds and to the order they run in, and
        # records planned against applied. Either one obeying makes the controller
        # authoritative, and the evidence says which -- a claim made by the organ that SPENT.
        try:
            from cycle_pricing import authority as _cyc_authority
            cok, cwhy = _cyc_authority()
            if cok:
                ok, why = True, f"{cwhy}; {why}"
            else:
                why = f"{why}; cycle_pricing: {cwhy}"
        except Exception as _exc:
            why = f"{why}; cycle_pricing unmeasured ({type(_exc).__name__})"
        p = Path(bandit.BUDGET)
        budget_doc = _json.loads(p.read_text(encoding="utf-8"))
        budget_doc["authoritative"] = bool(ok)
        budget_doc["authority_evidence"] = why
        p.write_text(_json.dumps(budget_doc, indent=1, default=str), encoding="utf-8")
        # THE REPORT IS THE FULL RUN, NOT THE TRIMMED BUDGET (Tier-1 B11/B12, 2026-09-23).
        #
        # `bandit.run` writes TWO documents: the whole measurement to `reports/RESEARCH_BANDIT.json`
        # and a three-key extract (generated_utc, controller_variant, shares) to
        # `data/research_budget.json`, because `research_budget.budget_s` only ever needs the
        # shares. This block then read the EXTRACT back and wrote it over the report -- so the
        # published report carried five keys and every block the readers actually ask for was
        # destroyed by the act of stamping authority onto it. Measured on the box 2026-09-23:
        # `realised_credit` was `null` in the report while `bandit.realised_credit()` returned
        # basis=live, applied=true on 151 realised deals, so `check_closed_loop.research`
        # reported "the bandit carries no realised_credit block yet" -- delayed live truth was
        # reaching the information budget and being deleted one line before publication.
        #
        # The report is stamped from `d`, the run's own return value; the budget keeps its
        # extract. Same two paths, same act, neither one a truncation of the other.
        doc = dict(d)
        doc["authoritative"] = bool(ok)
        doc["authority_evidence"] = why
        # AND PUBLISHED WHERE ITS READERS ACTUALLY LOOK (2026-09-22, Tier-1 B27/B28).
        #
        # `bandit.BUDGET` is `data/research_budget.json`. Every consumer on this desk reads
        # `reports/RESEARCH_BANDIT.json` instead -- `research_budget.BANDIT`,
        # `research_os_archive.BANDIT`, `cycle_pricing.BANDIT`, `libs/ops/allocators.py`,
        # `libs/ops/capability_graph.py` and `scripts/check_closed_loop.py` all name that path --
        # and NOTHING WROTE IT. Measured: the file on this box carried an older schema with no
        # `shares` key at all, so `research_budget.budget_s` answered "bandit shares unreadable
        # for these arms; base budget" on every call, the closed-loop attestation read
        # `evig_controller_authoritative` false, and the bandit's prices reached nothing. The
        # producer published to a path with no readers and the readers read a path with no
        # producer, which is the exact shape of an organ that looks wired and is not (LAWS 7).
        #
        # One document, two paths, written in the same act so they cannot drift.
        rep = _DESK / "reports" / "RESEARCH_BANDIT.json"
        rep.parent.mkdir(parents=True, exist_ok=True)
        rep.write_text(_json.dumps(doc, indent=1, default=str), encoding="utf-8")
        print(f"  authoritative: {ok} -- {why[:110]}")
        print(f"  published: {rep}")
    except Exception as exc:
        print(f"  authoritative: unmeasured ({type(exc).__name__}: {exc})")
    print(f"RESEARCH BANDIT  {d['graph_rows']} graph rows, pooled certify rate "
          f"{d['arms'].get('_pooled_rate')}")
    for arm, s in sorted(d["shares"].items(), key=lambda kv: -kv[1]):
        e = d["arms"][arm]
        print(f"  {arm:24s} share={s:5.1%}  born={e['born']:6d} failed={e['failed']:6d} "
              f"certified={e['certified']:3d}  p={e['p_survivor']:.3f} worth={e['worth']:.2f} "
              f"cost={e['cost']:.1f}")
    print(f"written: {bandit.BUDGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
