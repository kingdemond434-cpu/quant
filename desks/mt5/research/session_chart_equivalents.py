"""Take the mechanisms this desk has PROVEN in Asia and ask whether they work in London and NY.

THE GAP. Seven of twenty-four UTC hours (17:00-23:00) carry no forward clock at all, and both
books are overwhelmingly `asia`: 30 of 39 live MT5 sleeves and all 20 E8 sleeves. No allocator
fixes that, because there is nothing in those hours to allocate TO. Capital cannot work around
the clock while two thirds of the clock has never been hunted.

WHY EXPANSION BEATS A COLD HUNT, and this is the whole argument for the file. The desk's Asia
book is not a habit, it is an edge: `session_allocator` measures exp_R 0.5384 +/- 0.0803 over 155
trades there, a 6.7-sigma result. A `session_range_breakout` anchored at 13:00 is a genuinely NEW
cell -- different bars, different liquidity, different participants -- but it inherits a strong
prior from a mechanism already shown to work, which a randomly mined cell does not. Cold hunting
`discovered` returns 2.0 survivors per 1,000 ruled cells; `session_range_breakout` returns 105.6.

THE SESSION IS A PARAMETER, WHICH IS WHY THIS IS CHEAP. `family_session_range_breakout` takes
`range_start`; `opening_range` takes `open_hour`; `overnight_drift` takes `anchor_hour`. The
families were always able to trade any hour and nothing ever asked them to. Seven families expose
such a parameter and this file finds them BY INTROSPECTION rather than from a list, so a family
that gains one is covered the day it does, and one that loses it stops being expanded.

WHAT IT DOES NOT DO. It mints no certificate, grants no authority and sizes nothing: it appends
candidates to the docket and every one clears the same ten gates as anything else. It is also
DELIBERATELY CAPPED. Every cell added raises the deflated-Sharpe bar that every OTHER cell must
clear -- the desk paid for that once when single-name equities took 61% of the multiple-testing
charge -- so an unbounded cross-product would tax the families that work to subsidise a guess.
The cap is per parent, and hours are ranked by MEASURED coverage so the budget goes where the
desk has no clocks rather than back into the session it already owns.

    python desks/mt5/research/session_chart_equivalents.py            # report only
    python desks/mt5/research/session_chart_equivalents.py --apply    # append to the docket
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
UNIVERSE = BASE / "data" / "universe"
SESSION_REPORT = BASE / "reports" / "SESSION_ALLOCATION.json"
OUT = BASE / "reports" / "SESSION_CHART_EXPANSION.json"

#: Parameters that MEAN "which hour does this mechanism key on". Matched by name against every
#: registered family's signature, never listed per family.
_HOURISH = re.compile(r"(range_start|signal_hour|entry_hour|open_hour|anchor_hour|stamp_hour|"
                      r"settle_hour|session_start)$")

#: UTC hours to try, named for the session each one opens. LONDON and NEW YORK are the point:
#: they are where the desk has mechanisms and no clocks. Spread rather than dense, because two
#: variants three hours apart are far less correlated than two an hour apart, so a coarse grid
#: buys more independence per cell spent.
ANCHOR_HOURS: dict[int, str] = {
    0: "asia_open", 3: "asia_mid", 7: "asia_late",
    8: "london_open", 12: "london_pm",
    13: "ny_open", 16: "ny_mid", 19: "ny_late", 21: "ny_close",
}

#: THE WHOLE LADDER. A mechanism that works on one chart is a hypothesis about the other six, and
#: the desk collects all of them now -- there is no reason left to ask about only some.
#:
#: A variant is only emitted for a chart whose parquet EXISTS for that symbol. Proposing a cell
#: whose bars are absent produces an unjudgeable build, which is exactly how `lvc_asia_london`
#: came to look like thirteen lost candidates: an M5-pinned family on symbols that had no M5.
#: The existence check is what keeps this generator from manufacturing that failure at scale.
_CHARTS = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")

#: Which UTC hours each named window owns. Used ONLY to turn per-session clock counts into a
#: per-hour coverage ranking; it mirrors `session_allocator.SESSION_HOURS` and is duplicated
#: rather than imported so this file runs on a checkout where the desk package is not importable.
_SESSION_HOURS: dict[str, tuple[int, ...]] = {
    "asia": (0, 1, 2, 3, 4, 5, 6, 7),
    "london_am": (8, 9, 10, 11),
    "overlap": (12, 13, 14, 15),
    "new_york": (16, 17, 18, 19),
    "afternoon": (12, 13, 14, 15, 16),
    "ny_open": (13, 14),
}

#: Most variants any single parent may contribute.
#:
#: EVERY PARENT IS EXPANDED, NOT JUST THE ASIA ONES. The loop runs over all certificates and
#: proposes every anchor hour except the one that parent already trades, so an NY mechanism gets
#: its London and Asia equivalents exactly as an Asia one gets its NY equivalents. The desk's
#: certificates happen to be mostly Asia today; the rule is not.
#:
#: THE FULL CROSS-PRODUCT: every anchor hour against every chart the symbol has. Nine hours and
#: up to seven charts is 63 per parent, and a parent is never truncated before its own set is
#: complete.
#:
#: I CAPPED THIS AT SIX, THEN TWELVE, THEN SIXTEEN AGAINST A COST THAT DOES NOT EXIST. The stated
#: reason was that each added cell raises the deflated-Sharpe bar every other cell must clear.
#: Measured on the live report: `n_trials` is 597 and `sr0` is 0.3786 for ALL 4,235 judged cells,
#: identically. The charge is a SEALED CAMPAIGN CONSTANT (gate_spec.yaml
#: `fixed_campaign_trials`), not a function of docket size, so proposing more candidates costs
#: nothing at the margin. And the sealed basis is
#: `ceil(null_calibrated_participation_ratio_effective_cells * 7)` -- the EFFECTIVE count -- so
#: even a scaling charge would absorb correlated session and chart siblings rather than billing
#: them as independent bets. That was the whole point of the 2026-08-27 fix.
#:
#: THE REAL CONSTRAINT IS THE BUILD WINDOW, and it is why this expands CERTIFICATES ONLY. The
#: gauntlet has ~45 minutes an hour. 66 certificates at 63 variants is ~4,000 cells, which the
#: yield allocator will reach because their parent families return 105.6 survivors per 1,000
#: ruled cells. The same cross-product over all 22,143 docket candidates would be ~1.2 MILLION,
#: swamping the queue for months to test variants of things that have never passed anything. The
#: choice is about compute, not statistics, and saying so correctly matters: the wrong reason
#: would have kept this capped forever.
MAX_PER_PARENT = 63


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def session_params() -> dict[str, list[str]]:
    """family -> the parameter names that select its hour, found by introspection."""
    if str(BASE) not in sys.path:
        sys.path.insert(0, str(BASE))
    out: dict[str, list[str]] = {}
    for mod in ("mt5desk.families", "mt5desk.families_orthogonal"):
        try:
            m = importlib.import_module(mod)
        except Exception:
            continue
        for name, fn in vars(m).items():
            if not name.startswith("family_") or not callable(fn):
                continue
            try:
                sig = inspect.signature(fn)
            except (TypeError, ValueError):
                continue
            hrs = [p for p in sig.parameters if _HOURISH.search(p)]
            if hrs:
                out.setdefault(name[len("family_"):], hrs)
    return out


def _flat_params(spec: dict[str, Any]) -> dict[str, Any]:
    """The parent's parameters FLAT, because `build_cell` takes them flat and nothing said so.

    EVERY VARIANT THIS GENERATOR HAS EVER EMITTED WAS UNBUILDABLE (measured 2026-09-14). A
    certificate's `shadow_spec` carries the docket envelope -- `{"condition": null, "params":
    {...}}` -- and copying it through produced variants whose params read:

        {"condition": null, "params": {"rr": 1.5, "wait_bars": 12}, "range_start": 19}

    `build_cell` is then handed `condition=` and `params=` instead of `rr=` and `wait_bars=`, and
    refuses. The gauntlet recorded all 1,090 of them as NOT_RUN_BUILD_FAILED, so 996
    session_range_breakout variants, 63 overnight_gap_decay, 26 spread_state and 5 carry sat on
    the docket for days without one gate ever running on them. They did not fail -- they were
    never asked. Unwrapped, the same cells build and carry ~3,600 signals each.

    This is the SAME envelope fault `e8_executor._call_params` was carrying, in a different
    producer, found the same afternoon. The shape is worth recognising: a docket row and a family
    signature disagree about one level of nesting, and the disagreement presents as a refusal that
    nothing reads.

    Unwrapped by SHAPE, not by family, so a producer writing flat params keeps working.
    """
    out = dict(spec or {})
    inner = out.pop("params", None)
    out.pop("condition", None)
    if isinstance(inner, dict):
        out.update(inner)
    return out


def _charts_for(symbol: str) -> list[str]:
    return [c for c in _CHARTS if (UNIVERSE / f"{symbol}_{c}.parquet").exists()]


def _cell(sym: str, fam: str, params: dict[str, Any]) -> str:
    return f"{sym}.{fam}.{json.dumps(params, sort_keys=True)}"


def _parent_mechanism() -> dict[str, dict[str, Any]]:
    """cell id -> the mechanism claim on the DOCKET row that earned the certificate.

    THE FIELD THAT MAKES A PARENT ADMISSIBLE IS NOT ON THE OBJECT THIS GENERATOR READS.
    `economic_prior` refuses any cell whose family is `discovered` unless it carries
    `mechanism_status`, and measured 2026-09-14 all 33 certified `discovered` cells carry
    `mechanism_status: NAMED` on their DOCKET row while their `shadow_spec` -- the summary this
    generator builds variants from -- carries nothing:

        economic_prior(docket row)  -> passed True,  NAMED
        economic_prior(shadow_spec) -> passed False, STATISTICAL_ONLY

    So every variant of a discovered parent died at the FIRST gate with "statistical discovery has
    no economic prior", and 33 of the desk's 58 certificates -- including all 17 minted that day --
    could produce no session or chart variant at all. The breadth expansion was structurally
    blind to its own largest family.

    CARRYING IT IS NOT LAUNDERING AN ECONOMIC PRIOR. The parent's claim was examined and accepted
    when the parent certified; this generator's entire premise is that a mechanism surviving on
    one chart in one session is a hypothesis about every (hour, chart) pair, and the MECHANISM is
    what is being carried across -- not the evidence, which each variant must still earn through
    all ten gates on its own. A variant whose parent has no claim inherits nothing and is refused
    exactly as before.
    """
    rows = _read(DOCKET)
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict) or not row.get("mechanism_status"):
            continue
        try:
            cid = _cell(str(row.get("symbol") or ""), str(row.get("family") or ""),
                        row.get("params") or {})
        except Exception:
            continue
        out.setdefault(cid, {"mechanism_status": row.get("mechanism_status"),
                             "mechanism_note": row.get("mechanism_note")})
    return out


def expand() -> dict[str, Any]:
    """Variants of every certified mechanism, at hours and charts it has not been tried on."""
    surv = (_read(SURVIVORS) or {}).get("survivors") or {}
    docket = _read(DOCKET, [])
    if isinstance(docket, dict):
        docket = docket.get("survivors", [])
    known = {_cell(str(r.get("symbol")), str(r.get("family")), r.get("params") or {})
             for r in docket if isinstance(r, dict)}
    sess_params = session_params()

    # HOURS ARE RANKED BY MEASURED COVERAGE, ASCENDING -- not merely idle-first.
    #
    # Idle-first alone was not enough and the first run showed exactly why: with six variants per
    # parent, the two idle anchors were proposed and then the remaining slots went in HOUR ORDER,
    # so asia_open, asia_mid and asia_late took three of six while ny_open and ny_mid got none.
    # The generator was spending half its budget re-hunting the one session already carrying a
    # 6.7-sigma edge and 61.5% of the book.
    #
    # Coverage is read from `session_allocator`, so this ranks itself the way the research and
    # capital allocators do: on what was measured this cycle, not on a written order. As London
    # and NY fill up they stop being cheap and Asia becomes eligible again -- the loop closes
    # rather than permanently condemning a session.
    report = _read(SESSION_REPORT) or {}
    idle = set(report.get("idle_utc_hours") or range(24))
    per_hour: dict[int, int] = dict.fromkeys(ANCHOR_HOURS, 0)
    for sess, row in (report.get("by_session") or {}).items():
        for h in _SESSION_HOURS.get(str(sess), ()):
            if h in per_hour:
                per_hour[h] += int((row or {}).get("clocks", 0) or 0)
    hours = sorted(ANCHOR_HOURS, key=lambda h: (0 if h in idle else 1, per_hour.get(h, 0), h))

    new: list[dict[str, Any]] = []
    per_parent: dict[str, int] = {}
    mech = _parent_mechanism()
    for key, val in surv.items():
        spec = val.get("shadow_spec") or {}
        sym = str(spec.get("symbol") or "").upper()
        fam = str(spec.get("family") or "")
        if not sym or not fam:
            continue
        base = _flat_params({k: v for k, v in spec.items()
                             if k not in ("symbol", "family", "selector",
                                          "is_universe", "hunt")})
        # THE CROSS-PRODUCT, not two separate lists. An M15 breakout at 13:00 is a different bet
        # from an H1 breakout at 13:00 AND from an M15 breakout at 07:00; emitting hours and
        # charts as independent one-dimensional variations asks neither question. A mechanism
        # that survives on one chart in one session is a hypothesis about every (hour, chart)
        # pair, and the desk now holds the bars to ask.
        variants: list[tuple[dict[str, Any], str]] = []
        charts = _charts_for(sym) or [str(base.get("timeframe") or "H1").upper()]
        hour_params = sess_params.get(fam, [])
        for ch in charts:
            chart_base = base if str(base.get("timeframe") or "H1").upper() == ch else {
                **base, "timeframe": ch}
            if not hour_params:
                # A family with no hour parameter still varies by chart -- it simply cannot be
                # moved between sessions, which is a property of the mechanism, not a gap.
                if chart_base is not base:
                    variants.append((chart_base, f"chart_{ch}"))
                continue
            for hp in hour_params:
                for h in hours:
                    if base.get(hp) == h and chart_base is base:
                        continue               # this is the parent itself
                    variants.append(({**chart_base, hp: h},
                                     f"{ANCHOR_HOURS[h]}@{ch}"))

        for params, why in variants:
            if per_parent.get(key, 0) >= MAX_PER_PARENT:
                break
            cid = _cell(sym, fam, params)
            if cid in known:
                continue
            known.add(cid)
            per_parent[key] = per_parent.get(key, 0) + 1
            new.append({
                "symbol": sym, "family": fam, "params": params,
                # PROVENANCE, because a candidate that cannot name its parent cannot be audited,
                # and this generator's whole claim is that its parents are proven.
                "source": f"session_chart_equivalent:{why}",
                "producer": "session_chart_equivalents.py",
                "parent_certificate": key,
                "variant_of": why,
                # THE PARENT'S MECHANISM CLAIM TRAVELS WITH THE VARIANT, because `economic_prior`
                # refuses a `discovered` cell that carries none -- and the certificate's
                # shadow_spec does not carry it while its docket row does. Without this, every
                # variant of the desk's largest certified family died at gate one.
                **(mech.get(str(key).split(".", 1)[1] if str(key).startswith("external.")
                            else str(key)) or {}),
                "first_seen": datetime.now(UTC).isoformat(timespec="seconds"),
            })

    by_variant: dict[str, int] = {}
    for r in new:
        by_variant[str(r["variant_of"])] = by_variant.get(str(r["variant_of"]), 0) + 1
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "authority": ("PROPOSES ONLY -- mints no certificate and grants no authority. Every "
                      "variant clears the same ten gates as anything else on the docket."),
        "parents_certified": len(surv),
        "families_with_a_session_parameter": sorted(sess_params),
        "idle_hours_targeted": sorted(idle),
        "max_per_parent": MAX_PER_PARENT,
        "n_new": len(new),
        "by_variant": dict(sorted(by_variant.items(), key=lambda kv: -kv[1])),
        "new": new,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="append the variants to the docket")
    args = ap.parse_args(argv)

    doc = expand()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({k: v for k, v in doc.items() if k != "new"}, indent=1),
                   encoding="utf-8")
    print(f"session/chart expansion: {doc['n_new']} new candidate(s) from "
          f"{doc['parents_certified']} certificate(s)")
    print(f"  families with a session parameter: {doc['families_with_a_session_parameter']}")
    print(f"  idle hours targeted first: {doc['idle_hours_targeted']}")
    print(f"  by variant: {doc['by_variant']}")
    if not args.apply:
        print("  report only; re-run with --apply to append them to the docket")
        return 0

    docket = _read(DOCKET, [])
    if isinstance(docket, dict):
        docket.setdefault("survivors", []).extend(doc["new"])
        n = len(docket["survivors"])
    else:
        docket = list(docket) + doc["new"]
        n = len(docket)
    DOCKET.write_text(json.dumps(docket, indent=1), encoding="utf-8")
    print(f"  appended; docket is now {n} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
