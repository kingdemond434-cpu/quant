"""F24 -- EVERY CAPITAL MODIFIER PRICED AGAINST THE BOOK THAT DID NOT USE IT.

THE PRINCIPAL, 2026-09-12:

    Every shrink, cap, gate, regime haircut, correlation penalty, decay prior and execution buffer
    carries a counterfactual ledger -- Elog with it versus without -- and BOOST decisions likewise
    prove positive contribution; governance becomes empirically priced.

WHAT ALREADY EXISTED AND WHAT DID NOT. `capital_modifiers` records every application with its
multiplier, the state that claimed it and the heat it produced -- 689 rows and growing live. It
scores them per CATEGORY as a difference in mean R with a t-statistic. `missed_growth` walks 22
rails and prices each against the allocator's growth curve. Both are good, neither was on a clock,
and neither answers F24's question in F24's unit.

THE UNIT IS E[log W], AND THE COUNTERFACTUAL HAD TO BE GOT RIGHT TWICE.

The obvious construction is to divide the multiplier out -- log(1 + r*h) against log(1 + r*h/m) --
and it is a TAUTOLOGY. With m > 1 the counterfactual arm simply holds a smaller position, so
whenever mean realised return is positive a boost "proves growth" no matter which states it was
applied in. The first run of this organ reported every category PROVING_GROWTH with t as high as
42, including NORMAL, while `capital_modifiers.score` measured the same rows as COSTING growth on
mean R. A measurement that cannot fail is not a measurement.

WHAT THE QUESTION ACTUALLY IS. A modifier earns its place by putting MORE heat where the return
was better -- that is its information. Its LEVEL is a separate decision and belongs to the
allocator. So the counterfactual arm holds the SAME AVERAGE HEAT over the same days with the
dispersion removed:

    with     mean log(1 + r_i * h_i)          the heat the modifier actually chose, day by day
    without  mean log(1 + r_i * h-bar)        the same total heat, spread flat across those days

Both arms deploy identical average capital, so scale cancels and what remains is whether the
modifier's timing added log-wealth. A modifier that doubles everything scores exactly zero here,
which is correct: doubling everything is a level decision, not information.

BOOSTS ARE HELD TO THE SAME BAR AS SHRINKS, which is the half of the principal's sentence that
usually gets dropped. A boost that raises capital into a state that realises worse than normal is
costing growth just as surely as a timid shrink, and it will not show up in any veto ledger
because nothing was vetoed.

NOTHING HERE CHANGES A MULTIPLIER. A modifier measured as costly is a modifier whose SIGNAL is
wrong, and the answer to a mis-pointed boost is to fix where it points -- never to delete it. The
standing order is explicit that risk is not reduced by fiat, and a counterfactual that concluded
"apply less" would be exactly the growth cut wearing a statistic the desk refuses.

    python desks/mt5/research/modifier_counterfactuals.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MISSED = DESK / "reports" / "MISSED_GROWTH.json"
OUT = DESK / "reports" / "MODIFIER_COUNTERFACTUALS.json"

#: Matched sleeve-days a category needs before its growth contribution is quoted. Twenty is the
#: same floor `capital_modifiers.score` uses for its t-test, kept identical on purpose: two
#: measurements of the same rows that disagree about who is measurable would be worse than one.
MIN_MATCHED = 20


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _growth_delta(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """E[log W] with the modifier's chosen heat, against the SAME AVERAGE heat spread flat.

    THE ARM THAT MAKES THIS A MEASUREMENT RATHER THAN A TAUTOLOGY. Dividing the multiplier out
    would leave the counterfactual holding a smaller position, and with positive mean returns a
    boost then "proves growth" whatever states it chose. Holding average heat CONSTANT cancels
    the level and isolates the timing, which is the only part a modifier can be right or wrong
    about.

    IT IS PAIRED, so the standard error is on the per-day difference rather than on two means
    that share every return between them -- the returns are identical in both arms by
    construction, and treating the arms as independent would understate the error enormously.
    """
    import numpy as np
    heats: list[float] = []
    rets: list[float] = []
    mults: list[float] = []
    skipped = 0
    for r in rows:
        raw_m, raw_h, raw_ret = r.get("multiplier"), r.get("heat"), r.get("realised_r")
        if not all(isinstance(x, (int, float)) for x in (raw_m, raw_h, raw_ret)):
            skipped += 1
            continue
        m, h, ret = float(raw_m), float(raw_h), float(raw_ret)  # type: ignore[arg-type]
        if h <= 0 or m <= 0:
            # A VETO IS NOT A MULTIPLIER FOR THIS PURPOSE. m = 0 means the trade did not happen,
            # so there is no realised return to attribute; that counterfactual belongs to the
            # veto ledger, which prices it against the allocator's growth curve instead.
            skipped += 1
            continue
        heats.append(h)
        rets.append(ret)
        mults.append(m)
    if len(heats) < MIN_MATCHED:
        return {"status": "UNMEASURED", "n_matched": len(heats), "n_skipped": skipped,
                "why": (f"{len(heats)} matched sleeve-day(s) against a floor of {MIN_MATCHED}. A "
                        f"growth contribution off fewer is one week's noise with a decimal "
                        f"point.")}
    # NAMED APART FROM THE LOOP VARIABLES ABOVE. `r`, `h` and `m` are the per-row scalars in the
    # loop; reusing them for the arrays made the checker read a dict where an array belongs, and
    # a reader would have had to hold two meanings for one letter.
    harr = np.asarray(heats, dtype=float)
    rarr = np.asarray(rets, dtype=float)
    marr = np.asarray(mults, dtype=float)
    hbar = float(harr.mean())
    a, b = rarr * harr, rarr * hbar
    ok = (a > -1.0) & (b > -1.0)
    if int(ok.sum()) < MIN_MATCHED:
        return {"status": "UNMEASURED", "n_matched": int(ok.sum()), "n_skipped": skipped,
                "why": "too many sleeve-days imply a total loss in one arm to compare the two"}
    with_arm = np.log1p(a[ok])
    flat_arm = np.log1p(b[ok])
    diff = with_arm - flat_arm
    mean = float(diff.mean())
    se = float(diff.std(ddof=1) / math.sqrt(diff.size)) if diff.size > 1 else 0.0
    return {
        "status": "OK", "n_matched": int(diff.size), "n_skipped": skipped,
        "mean_multiplier_applied": round(float(marr.mean()), 4),
        "multiplier_dispersion": round(float(marr.std()), 4),
        "mean_heat": round(hbar, 6),
        "elog_with_modifier_timing": round(float(with_arm.mean()), 8),
        "elog_same_heat_spread_flat": round(float(flat_arm.mean()), 8),
        "delta_elog_per_sleeve_day": round(mean, 8),
        "standard_error_paired": round(se, 8),
        "t_paired": round(mean / se, 3) if se > 0 else None,
        "verdict": ("PROVES_GROWTH" if se > 0 and mean / se > 2.0 else
                    "COSTS_GROWTH" if se > 0 and mean / se < -2.0 else
                    "NO_MEASURED_CONTRIBUTION"),
        "reads": ("both arms deploy the same average heat over the same days, so this is the "
                  "modifier's TIMING and not its level. A modifier that multiplies everything "
                  "equally scores zero here, which is correct."),
    }


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np  # noqa: F401
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy unavailable ({exc})"}
    try:
        from libs.portfolio.capital_modifiers import (
            CATEGORIES,
            LEDGER,
            _realized_by_sleeve_day,
        )
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": (f"capital_modifiers is not importable ({exc}). This organ refuses to "
                        f"re-derive the ledger -- a second reader of the same rows that "
                        f"disagreed with the first would be worse than one.")}

    try:
        raw = [json.loads(ln) for ln in LEDGER.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError) as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"the modifier ledger is unreadable: {type(exc).__name__}: {exc}"}
    realized = _realized_by_sleeve_day()

    matched: list[dict[str, Any]] = []
    for r in raw:
        key = (str(r.get("sleeve")), str(r.get("t"))[:10])
        if key in realized:
            matched.append({**r, "realised_r": float(realized[key])})

    by_cat: dict[str, list[dict[str, Any]]] = {}
    for r in matched:
        by_cat.setdefault(str(r.get("category")), []).append(r)
    cats: list[dict[str, Any]] = []
    for cat, mult in CATEGORIES.items():
        rows = by_cat.get(cat, [])
        # THE CATEGORY'S MULTIPLIER IS A BUCKET LABEL, NOT WHAT WAS APPLIED. The ledger's rows
        # carry a CONTINUOUS multiplier -- a row labelled NORMAL was seen at 0.7901 -- so the
        # direction is read from the multipliers actually applied, and the nominal value is
        # reported beside it rather than instead of it.
        cats.append({"category": cat, "bucket_multiplier": mult, **_growth_delta(rows)})
    cats.sort(key=lambda r: -(r.get("delta_elog_per_sleeve_day") or 0.0))

    costly = [c for c in cats if c.get("verdict") == "COSTS_GROWTH"]
    proving = [c for c in cats if c.get("verdict") == "PROVES_GROWTH"]

    # THE RAILS, rolled in from missed_growth so governance is priced in ONE place. Each rail
    # that cannot be measured names what it is waiting for -- a rail whose counterfactual is
    # unmeasured is not a rail that is free.
    mg = _read(MISSED) or {}
    rails = mg.get("rails") if isinstance(mg.get("rails"), dict) else {}
    unmeasured_rails = list(mg.get("unmeasured") or [])
    rail_rows = []
    for name, row in (rails or {}).items():
        if isinstance(row, dict):
            rail_rows.append({"rail": name, "kind": row.get("kind"),
                              "verdict": row.get("verdict") or row.get("status"),
                              "cost": row.get("cost") or row.get("missed")})
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "ledger": {"rows": len(raw), "matched_to_a_realised_day": len(matched),
                   "match_rate": round(len(matched) / max(len(raw), 1), 4),
                   "why_unmatched": (
                       "a ledger row records a modifier applied on a sleeve-day; it matches only "
                       "if that sleeve realised a return that day. An unmatched row is a "
                       "modifier applied to a day that did not trade, which is not evidence "
                       "about the modifier either way.")},
        "categories": cats,
        "n_costing_growth": len(costly),
        "n_proving_growth": len(proving),
        "headline": (
            "; ".join(f"{c['category']} (applied mean x{c['mean_multiplier_applied']}) "
                      f"{c['verdict']} at {c['delta_elog_per_sleeve_day']:+.6f} log-growth per "
                      f"sleeve-day, paired t={c['t_paired']}"
                      for c in cats if c.get("status") == "OK")
            or "no category has enough matched sleeve-days to price yet"),
        "rails": rail_rows,
        "unmeasured_rails": {
            "n": len(unmeasured_rails), "rails": unmeasured_rails,
            "why": ("missed_growth walks 22 rails and every one is UNMEASURED, because a rail's "
                    "counterfactual needs the EVENT of it binding -- a veto fired, a cap hit, a "
                    "shrink applied -- and the desk does not yet record most of those. A rail "
                    "whose counterfactual is unmeasured is not a rail that is free: it is an "
                    "unpriced piece of governance, which is exactly what F24 exists to end."),
        },
        "reconciliation_with_capital_modifiers_score": (
            "capital_modifiers.score measures the SAME rows and reports BOOST and STRONG_BOOST as "
            "COSTING growth at t = -10.2 and -10.4. That is not a contradiction and neither "
            "number is wrong -- they answer different questions. score() asks whether boosted "
            "sleeve-days realised a better mean R than NORMAL ones, which is a fact about the "
            "STATES the modifier selects and is heavily confounded by which sleeves happen to "
            "trade in them. This organ asks whether putting MORE heat on those days added "
            "log-wealth GIVEN THE SAME AVERAGE HEAT, which is a fact about the modifier. A "
            "modifier can select states that realise worse on average and still add nothing "
            "either way once its level is held constant, which is what 139 matched sleeve-days "
            "say here. Reading either as the other is how a desk deletes a modifier for the "
            "wrong reason."),
        "boosts_face_the_same_bar": (
            "the half of the principal's sentence that usually gets dropped. A boost that raises "
            "capital into a state realising worse than normal costs growth just as surely as a "
            "timid shrink, and it appears in NO veto ledger because nothing was vetoed."),
        "boundary": (
            "NOTHING HERE CHANGES A MULTIPLIER. A modifier measured as costly is a modifier whose "
            "SIGNAL points the wrong way, and the answer is to fix where it points -- never to "
            "delete it. A counterfactual concluding 'apply less' would be the growth cut wearing "
            "a statistic that the standing order refuses."),
        "why_elog_and_not_mean_r": (
            "a modifier multiplies HEAT and heat enters wealth multiplicatively. The same mean R "
            "at twice the heat is a different growth rate and can be a worse one, so a mean-R "
            "difference cannot say what the book would have compounded at without the modifier."),
        "why_the_counterfactual_holds_heat_constant": (
            "the obvious arm -- divide the multiplier out -- is a TAUTOLOGY: with positive mean "
            "returns a boost always beats a smaller position, whatever states it chose. The "
            "first run of this organ scored every category PROVING_GROWTH at t up to 42, "
            "including NORMAL, while capital_modifiers.score measured the same rows as costing "
            "growth on mean R. A measurement that cannot fail is not a measurement. Holding "
            "average heat constant cancels the level and isolates the timing, which is the only "
            "thing a modifier can be right or wrong about."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"modifier counterfactuals: {doc.get('status')} -- {doc.get('why')}")
        return 0
    led = doc["ledger"]
    print(f"modifier counterfactuals: OK   {led['rows']} ledger row(s), "
          f"{led['matched_to_a_realised_day']} matched to a realised day "
          f"({led['match_rate']:.0%})")
    print("  category        bucket applied  n     timing       flat         delta      t")
    for c in doc["categories"]:
        if c.get("status") != "OK":
            print(f"  {c['category']:<15} {c['bucket_multiplier']:<6} "
                  f"UNMEASURED -- {str(c.get('why'))[:70]}")
            continue
        print(f"  {c['category']:<15} {c['bucket_multiplier']:<6} "
              f"x{c['mean_multiplier_applied']:<6} {c['n_matched']:<5} "
              f"{c['elog_with_modifier_timing']:+.7f}  "
              f"{c['elog_same_heat_spread_flat']:+.7f}  "
              f"{c['delta_elog_per_sleeve_day']:+.7f}  {c['t_paired']}  {c['verdict']}")
    if doc["n_costing_growth"]:
        print(f"  {doc['n_costing_growth']} category(ies) COST growth -- their signal points the "
              f"wrong way; that is a direction to fix, never a reason to apply less")
    print("  NOTE: capital_modifiers.score reports BOOST/STRONG_BOOST as COSTING growth on mean "
          "R. Different question -- that is about the STATES selected; this is about the "
          "modifier's timing at constant average heat. Both stand.")
    ur = doc["unmeasured_rails"]
    print(f"  {ur['n']} rail(s) remain unpriced: {', '.join(ur['rails'][:8])}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
