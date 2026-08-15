#!/usr/bin/env python3
"""HOW MANY INDEPENDENT BETS THE DESK HOLDS, AND WHICH FAMILY THE NEXT ONE SHOULD COME FROM.

The desk's objective is max E[log wealth], whose maximum is S^2/2. So every return target is a
Sharpe requirement, and the only lever the desk controls on S is breadth -- s*sqrt(k) for k
INDEPENDENT sleeves. Leverage cannot do it (past Kelly, more lowers growth) and a better single
edge is a hope rather than a plan.

**THE WORD THAT GETS ASSUMED IS "INDEPENDENT".** Eleven momentum variants are one bet in eleven
hats: at rho 0.8, k_eff is 1.2, not 11. Nothing else the desk publishes distinguishes those two
books -- both report "11 strategies" -- and the difference is the entire gap between the current
book and the principal's monthly floor.

**THIS IS THE CALLER FOR TWO MODULES THAT HAD NONE** (III.16). `libs.research.breadth` computes the
k_eff arithmetic and `libs.validation.family_multiplicity` partitions the Holm cohort so seats stop
being globally rationed. Both were correct and idle, which is byte-identical to absent in every
report that counts modules. This runs them daily, on the LIVE cohort, and leaves an artifact.

**IT DECIDES NOTHING.** No seat is granted, no bar is loosened, no candidate promoted. It publishes
what the partition WOULD cost (`family_error_budget`) beside what it buys, and ranks where marginal
breadth is highest so research effort follows the derivative rather than the newest idea.

    python scripts/report_breadth.py [--json] [--target-monthly 0.05]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research import breadth
from libs.research import mechanism_census as census
from libs.validation import family_multiplicity as fm
from libs.validation.forward_stats import holm_bar

_OUT = Path("web/breadth_ledger.json")

#: THE PER-SLEEVE SHARPE USED FOR THE PRICING VIEW, and it is an ASSUMPTION rather than a
#: measurement -- stated here so it cannot be mistaken for one downstream. No sleeve on this desk
#: has enough overlapping live history to publish its own Sharpe with a usable standard error, so
#: `sleeves_needed_at_rho_0` answers "at THIS quality, how many?" and not "how many do we need".
_ASSUMED_SLEEVE_SHARPE = 0.48

#: The principal's standing floor, set 2026-08-15: at least 5%/month. Priced rather than hoped --
#: 5%/mo is 79.6%/yr, which at the Kelly optimum needs Sharpe 1.26, which at today's per-sleeve
#: quality needs SEVEN uncorrelated sleeves. The earlier 7% figure needed eleven. Both numbers are
#: requirements on BREADTH, and neither is reachable by leverage: past Kelly, more borrowing lowers
#: growth. Stated here so the target and its cost never drift apart in different documents.
DEFAULT_TARGET_MONTHLY = 0.05


def _cohort() -> list[str]:
    """Live forward-clock names. Empty on a clone -- data/ is gitignored, so that is UNMEASURED."""
    from libs.research.slot_registry import derive_slots

    return [str(s.get("name", "")) for s in derive_slots().get("slots", []) if s.get("name")]


def _rules() -> list[str]:
    """The discretionary playbook, which is where the desk's LIVE breadth actually sits today.

    NO `except: return []`. The first draft of this function wrapped the import in a bare except
    and printed "0 rules" against a playbook holding ten -- READY and TAPE_RULES are name->func
    DICTS, not sets of functions, so the comprehension raised AttributeError and the handler turned
    a crash into a clean, plausible zero. That is WS-005 in four lines, in the file whose whole job
    is to stop a count being trusted. An exception here is the correct behaviour: the breadth of
    the live book is not something this script may guess at.
    """
    from libs.discretionary import rules

    return sorted(set(rules.READY) | set(rules.TAPE_RULES))


def build(target_monthly: float = DEFAULT_TARGET_MONTHLY, *, alpha: float = 0.05) -> dict[str, Any]:
    cohort = _cohort()
    rule_names = _rules()
    names = cohort + rule_names

    parts = fm.partition(names) if names else {}
    # `effective_m`, NOT len(). UNCLASSIFIED is floored at the largest declared family so that
    # declining to declare a mechanism is never the cheaper bar.
    eff = fm.effective_m(parts)
    m_global = max(1, len(names))
    fam_rows = []
    for fam, members in sorted(parts.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        m = eff[fam]
        cls = census.CLASS_BY_ID.get(fam)
        fam_rows.append({
            "family": fam, "m": m, "n_members": len(members), "members": sorted(members),
            # DECLARED, NOT MEASURED, and labelled so nowhere downstream can read it as a rho.
            # It ranks where to look; it never sizes anything.
            "declared_orthogonality": None if cls is None else cls.orthogonality,
            "payer": None if cls is None else cls.payer,
            "holm_bar_rank1": holm_bar(m, 1, alpha=alpha),
            "bh_bar_rank1": fm.bh_bar(m, 1, alpha=alpha),
            # WHAT THE PARTITION BUYS, per family: the bar this member would have faced in one
            # global cohort, against the bar it faces in its own. The saving is the seat.
            "holm_bar_if_one_global_cohort": holm_bar(m_global, 1, alpha=alpha),
        })

    # BREADTH IS COMPUTED WITH RHO=None ON PURPOSE. There is no overlapping live history to measure
    # pairwise correlation from, and substituting zero would multiply the projected Sharpe by
    # sqrt(n) while the book behaves like one position. The curve is published instead.
    rho: float | None = None
    rep = breadth.report(dict.fromkeys(names, _ASSUMED_SLEEVE_SHARPE), rho,
                         target_monthly=target_monthly)

    # MARGINAL BREADTH, RANKED. Adding to a family the book is already saturated in buys ~nothing;
    # the first sleeve of an uncorrelated family buys the most available anywhere. Assumed within-
    # family rho 0.8 and cross-family 0.3 -- both STATED, both unmeasured, and the ranking they
    # produce is robust to the exact values because the gap is two orders of magnitude wide.
    n_held = len(names)
    marginal = []
    for label, cand_rho in (("same family as the book", 0.8),
                            ("a different declared family", 0.3),
                            ("a genuinely orthogonal family", 0.0)):
        if n_held:
            marginal.append({"candidate": label, "assumed_rho_to_book": cand_rho,
                             **breadth.marginal_breadth(n_held, 0.8, cand_rho)})

    # WHERE THE DESK IS NOT. The census declares 26 mechanism classes, each with a named payer and
    # a declared orthogonality; the live book occupies a handful. An EMPTY high-orthogonality class
    # is the first sleeve of an uncorrelated family -- exactly the case `marginal_breadth` prices
    # two orders of magnitude above another variant of what is already held. This turns "find ways
    # to 5% a month" into a named, ranked list of mechanisms rather than a search for a better
    # version of the mechanisms already in the book.
    held = set(parts)
    vacant = [
        {"class": c.id, "declared_orthogonality": c.orthogonality, "plausibility": c.plausibility,
         "priority": c.priority, "payer": c.payer,
         "data": c.data.availability.value if hasattr(c.data.availability, "value")
                 else str(c.data.availability)}
        for c in census.TAXONOMY
        if c.id not in held and c.orthogonality >= fm.ORTHOGONALITY_FLOOR
    ]
    vacant.sort(key=lambda r: (-(float(r["declared_orthogonality"]) * float(r["plausibility"])),
                               r["priority"]))

    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "assumed_per_sleeve_sharpe": _ASSUMED_SLEEVE_SHARPE,
        "assumption_state": "ASSUMED -- no sleeve has enough overlapping live history to publish "
                            "its own Sharpe with a usable standard error",
        "n_forward_clocks": len(cohort), "n_discretionary_rules": len(rule_names),
        "breadth": rep,
        "families": fam_rows,
        "family_error_budget": fm.family_error_budget(len(parts), alpha=alpha),
        "marginal_breadth": marginal,
        "orthogonality_floor": fm.ORTHOGONALITY_FLOOR,
        "vacant_high_orthogonality_classes": vacant,
        "seats": ("under partition, seats are PER FAMILY: a new clock in one family costs the "
                  "others exactly nothing, so the total is bounded by how many genuinely distinct "
                  "questions the desk can ask rather than by MAX_FORWARD_SLOTS"),
        "decides": "NOTHING -- no seat granted, no bar loosened, no candidate promoted",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--target-monthly", type=float, default=DEFAULT_TARGET_MONTHLY)
    args = ap.parse_args()

    rep = build(args.target_monthly)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
        return 0

    b = rep["breadth"]
    print(f"=== BREADTH === {b['n_sleeves']} sleeve(s) "
          f"({rep['n_forward_clocks']} forward clocks + {rep['n_discretionary_rules']} rules), "
          f"rho {b['rho_state']}, k_eff {b['effective_breadth']}, S {b['combined_sharpe']}")
    if not b["n_sleeves"]:
        print("  NOTHING HELD on this host -- data/ is gitignored, so a clone sees no clocks. That "
              "is UNMEASURED, not an empty book")
    t = b["target"]
    print(f"  target {t['monthly']:.1%}/mo = {t['annual']:.1%}/yr -> needs Sharpe "
          f"{t['required_sharpe']:.2f}; at s={rep['assumed_per_sleeve_sharpe']} that is "
          f"{b['sleeves_needed_at_rho_0']} UNCORRELATED sleeves")

    print("\n  rho curve (what the SAME sleeves are worth across the plausible range):")
    for row in b["rho_curve"]:
        print(f"    rho {row['rho']:.1f} -> k_eff {row['k_eff']:.2f}  S {row['combined_sharpe']:.2f}"
              f"  {row['monthly']:+.2%}/mo")

    if rep["families"]:
        print("\n  families (m is corrected WITHIN the family, not across the desk):")
        for f in rep["families"]:
            floored = " [m FLOORED: undeclared pays the worst bar on the desk]" \
                if f["m"] > f["n_members"] else ""
            orth = f["declared_orthogonality"]
            print(f"    {f['family']:<30} m={f['m']:<3} holm t {f['holm_bar_rank1']:.2f}  "
                  f"BH t {f['bh_bar_rank1']:.2f}  "
                  f"orth {'  n/a' if orth is None else f'{orth:5.2f}'}  "
                  f"(one cohort: {f['holm_bar_if_one_global_cohort']:.2f}){floored}")
        eb = rep["family_error_budget"]
        print(f"  cost: {eb['why']}")

    if rep["marginal_breadth"]:
        print("\n  marginal breadth -- WHERE THE NEXT BUILD SHOULD GO:")
        for m in rep["marginal_breadth"]:
            print(f"    {m['candidate']:<32} rho {m['assumed_rho_to_book']:.1f} -> "
                  f"+{m['delta_k']:.3f} effective bets  (S x{m['sharpe_multiplier']:.3f})")

    if rep["vacant_high_orthogonality_classes"]:
        print(f"\n  VACANT mechanism classes (census orthogonality >= "
              f"{rep['orthogonality_floor']}) -- the desk holds NOTHING here, so each is a FIRST "
              "sleeve of an uncorrelated family rather than another variant of what is held:")
        for v in rep["vacant_high_orthogonality_classes"][:8]:
            print(f"    {v['class']:<34} orth {v['declared_orthogonality']:.2f}  "
                  f"plaus {v['plausibility']:.2f}  data {v['data']}")
            print(f"      payer: {str(v['payer'])[:96]}")

    print(f"\n-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
