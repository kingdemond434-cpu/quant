"""ALLOCATOR LIVENESS -- did the money brain produce, prove and publish THIS cycle, on fresh inputs?

WHY THIS EXISTS. On 2026-09-23 a read-only probe of the trading box reported

    desks/mt5/data/pf_allocation.json       ABSENT
    desks/mt5/reports/ALLOCATOR_PROOF.json  ABSENT
    desks/mt5/reports/HEAT.json             ABSENT

and concluded the allocator was not running. Every one of those readings was true and every
conclusion drawn from it was false: the allocator writes `desks/mt5/reports/pf_allocation.json`
(not `data/`), `allocator_proof.certify` writes the certificate under the REPO ROOT's `reports/`
(not the desk's), and `HEAT.json` has never existed -- the heat is a block inside the allocation.
Both real artifacts were minutes old at the moment the probe called them absent.

THE DEFECT WAS NEVER THE ALLOCATOR. It was that NOTHING PUBLISHED WHERE THE ALLOCATOR'S OUTPUTS
LIVE, how old they may be, or which input each pass actually conditioned on. A desk that cannot
answer "is the allocator alive right now" from ONE artifact will answer it from whichever path a
reader guesses, and a guess that lands on an absent path is indistinguishable from a dead organ.
Absence must be impossible to confuse with "it decided not to" (L1.28a), and that is a publishing
duty, not an inference anyone should have to make.

SO THIS ORGAN PUBLISHES THE TRUTH, EVERY CYCLE:

  * every allocator OUTPUT with its real path, its age, the cadence it is held to and the named
    CONSUMER that reads it -- an output nothing reads is a defect the report states by name;
  * every allocator INPUT with its age, its own freshness bound and whether the allocator
    DECLARED it used, neutral or UNMEASURED on the pass that is on disk -- so a pass conditioned
    on yesterday's world is visible as exactly that instead of being averaged into a number;
  * the heat the pass RESOLVED against the floor it must fill, and the heat the LIVE book is
    actually carrying, so "the book is sized below its floor" is a measurement and not an
    opinion;
  * the allocator's join to the live sleeve rows (`scripts/check_allocator_join.measure`),
    because a book that funds ten sleeves and reaches none of them sizes nothing while every
    artifact still looks correct;
  * the last NAMED STAND-DOWN (`reports/ALLOCATOR_STANDDOWN.json`, written by `pf_allocator`
    on each of its own `return 0` paths), so a cycle that could not complete says why.

IT SIZES NOTHING AND VETOES NOTHING. Every number here is read off artifacts that already
exist; this organ has no path to a fraction, a cap or the heat floor. Its only power is that
`scripts/check_allocator_liveness.py` fails the law gate on what it measures.

    python desks/mt5/research/allocator_liveness.py --once --budget-s 120 [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT = REPORTS / "ALLOCATOR_LIVENESS.json"
ALLOCATION = REPORTS / "pf_allocation.json"
#: `allocator_proof.certify(root=ROOT)` writes under the REPO ROOT, not the desk. Both are read:
#: the desk copy is what a reader expects and the root copy is what the code writes, and
#: `check_closed_loop` already reads either. Publishing both ages is how the next probe stops
#: guessing.
PROOF_PATHS = (ROOT / "reports" / "ALLOCATOR_PROOF.json", REPORTS / "ALLOCATOR_PROOF.json")
STANDDOWN = REPORTS / "ALLOCATOR_STANDDOWN.json"

#: TWO ALLOCATOR CLOCKS. `hourly_cycle` runs `pf_allocator` once an hour (`_allocator_mode_for
#: _the_hour`), so an allocation older than two firings is a missed cycle rather than a slow one.
#: This is the same bound `scripts/check_heat_floor_wiring.py` holds the artifact to; one number,
#: not two that drift apart.
ALLOCATION_MAX_AGE_S = 2 * 3600
#: The hourly cadence itself, for the report's own arithmetic.
CYCLE_S = 3600

UNMEASURED = "UNMEASURED"

#: Tokens an allocator's own why-string uses when it did NOT condition on an input. Matching any
#: of them is the allocator DECLARING the input unused -- which is what makes a stale input legal
#: (the pass degraded honestly) instead of a silent conditioning on yesterday's world.
_NEUTRAL_TOKENS = ("absent", "unreadable", "neutral", "unmeasured", "not measured",
                   "no readable", "h old", "min old (", "stale", "nothing is re-weighted",
                   "every term neutral", "no sleeves block", "is not 'evidence'")


def _age_s(p: Path, *, now: float) -> float | None:
    try:
        return max(0.0, now - p.stat().st_mtime)
    except OSError:
        return None


def _read(p: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _dig(doc: Any, dotted: str) -> Any:
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _declaration(alloc: dict[str, Any] | None, paths: tuple[str, ...]) -> tuple[bool | None, str]:
    """Did the pass on disk DECLARE this input used? (used, the allocator's own words).

    `None` is not "no": it is "the allocation artifact says nothing about this input", which is
    itself a finding -- an input nobody records conditioning on cannot be shown to have been read.
    """
    if alloc is None:
        return None, "no allocation artifact to declare against"
    for dotted in paths:
        val = _dig(alloc, dotted)
        if val is None:
            continue
        text = val if isinstance(val, str) else json.dumps(val, default=str)
        low = text.lower()
        if any(tok in low for tok in _NEUTRAL_TOKENS):
            return False, f"{dotted}: {text[:220]}"
        return True, f"{dotted}: {text[:220]}"
    return None, f"allocation artifact carries none of {list(paths)}"


class Input:
    """One thing the allocator conditions on, with the authority for its freshness bound."""

    def __init__(self, key: str, path: Path, max_age_s: float, bound_from: str,
                 how: str, declared_by: tuple[str, ...] = ()) -> None:
        self.key, self.path, self.max_age_s = key, path, max_age_s
        self.bound_from, self.how, self.declared_by = bound_from, how, declared_by


def _evidence_max_age() -> tuple[float, str]:
    """The evidence pack's OWN staleness rule, from the module that enforces it -- never a
    number chosen here. An unimportable library degrades to two allocator clocks with the reason
    recorded, which is the same bound the allocation artifact is held to."""
    try:
        from libs.portfolio.allocator_evidence import MAX_AGE_S
        return float(MAX_AGE_S), "libs/portfolio/allocator_evidence.MAX_AGE_S"
    except Exception as exc:                                   # pragma: no cover - import guard
        return float(ALLOCATION_MAX_AGE_S), f"two allocator clocks ({type(exc).__name__})"


def _proof_max_age() -> tuple[float, str]:
    try:
        from libs.portfolio.allocator_proof import MAX_AGE_S
        return float(MAX_AGE_S), "libs/portfolio/allocator_proof.MAX_AGE_S"
    except Exception as exc:                                   # pragma: no cover - import guard
        return float(ALLOCATION_MAX_AGE_S), f"two allocator clocks ({type(exc).__name__})"


def inputs() -> list[Input]:
    """Every input `pf_allocator` reads, with the clock that owns its freshness.

    THE BOUND IS THE PRODUCER'S CADENCE, NOT A PREFERENCE. An artifact a scheduled leg rewrites
    every hour is stale at two firings; one the evidence library dates itself is held to the
    library's own constant. Both are cited on the row so a reader can check the authority rather
    than trust the number.
    """
    ev_age, ev_from = _evidence_max_age()
    two_clocks = "two allocator clocks (hourly_cycle runs pf_allocator once per hour)"
    return [
        Input("allocator_evidence", DATA / "allocator_evidence.json", ev_age, ev_from,
              "apply_allocator_evidence: lineage, ROI, forward posterior, marginal breadth, "
              "factor tier and net-of-cost tilts plus the financing shift",
              ("allocator_evidence.evidence", "allocator_evidence.status")),
        Input("roi_capital_evidence", DATA / "roi_capital_evidence.json", ev_age, ev_from,
              "per-mechanism ROI prior tilt", ("allocator_evidence.roi",)),
        Input("net_edge", REPORTS / "NET_EDGE.json", 2 * CYCLE_S, two_clocks,
              "net of spread/slippage/impact/financing/multiplicity and per-sleeve capacity, "
              "through allocator_evidence's net_of_cost tilt (door c of the spine)",
              ("allocator_evidence.net_of_cost",)),
        Input("posterior_alpha", REPORTS / "POSTERIOR_ALPHA.json", ev_age, ev_from,
              "hierarchical forward posterior tilt and marginal-breadth tilt",
              ("allocator_evidence.forward_posterior", "allocator_evidence.marginal_breadth")),
        Input("exposure_decomposition", REPORTS / "EXPOSURE_DECOMPOSITION.json", ev_age, ev_from,
              "twelve-factor exposure -> factor-tier tilt", ("allocator_evidence.factor_tier",)),
        Input("state_vector", DATA / "state_vector.json", 2 * CYCLE_S, two_clocks,
              "the admitted non-session dimensions' CURRENT buckets, which pick the state the "
              "book is solved and certified in (_admitted_extra_dims)",
              ("state_vector.status", "state_vector.why", "state_vector")),
        Input("state_admission", REPORTS / "STATE_ADMISSION.json", 26 * 3600,
              "the sealed admission judge's own daily cadence",
              "which dimensions MAY condition the book at all",
              ("state_vector.admitted", "heat.state")),
        Input("regime_state", DATA / "regime_state.json", 2 * CYCLE_S, two_clocks,
              "regime probabilities that weight the sampled worlds",
              ("regime.status", "regime.why", "regime")),
        Input("macro_view", REPORTS / "MACRO_VIEW.json", 2 * CYCLE_S, two_clocks,
              "macro conditioning of the world population and the regime tilts",
              ("macro_regime.status", "macro_regime.why", "macro_regime")),
        Input("drift", REPORTS / "DRIFT.json", 26 * 3600,
              "drift_monitor's own daily change-point cadence",
              "crisis-world share of the sampled population",
              ("drift_overlay.status", "drift_overlay.why", "drift_overlay")),
        Input("sleeve_registry", DATA / "sleeve_registry.json", 26 * 3600,
              "the promoter's daily roster cadence",
              "the roster the book is solved over", ("evidence.sleeves",)),
        Input("sleeves", DATA / "sleeves.json", 26 * 3600,
              "the promoter's daily roster cadence",
              "the LIVE rows the book must reach (the join)", ()),
    ]


def outputs() -> list[dict[str, Any]]:
    """Every artifact the allocator writes, and the organ that READS it. An output with no named
    consumer is dead architecture and says so on its own row."""
    proof_age, proof_from = _proof_max_age()
    return [
        {"key": "allocation", "path": ALLOCATION, "max_age_s": ALLOCATION_MAX_AGE_S,
         "bound_from": "scripts/check_heat_floor_wiring.MAX_AGE_S (two allocator clocks)",
         "consumers": ["desks/mt5/mt5desk/gateway.py allocator_book (sizes the live book)",
                       "scripts/check_allocator_join.py", "scripts/check_heat_floor_wiring.py",
                       "desks/mt5/research/allocator_attribution.py",
                       "desks/mt5/research/net_edge_spine.py heat_reallocation",
                       "desks/mt5/research/tier1_scorecard.py",
                       "desks/mt5/research/missed_growth.py"]},
        {"key": "proof", "path": PROOF_PATHS[0], "max_age_s": proof_age,
         "bound_from": proof_from, "alt_path": PROOF_PATHS[1],
         "consumers": ["desks/mt5/mt5desk/gateway.py allocator_book via "
                       "libs/portfolio/allocator_proof.read_certificate + select "
                       "(decides WHICH book may size)",
                       "libs/ops/release.py", "scripts/check_closed_loop.py",
                       "desks/mt5/research/live_system_state.py",
                       "desks/mt5/research/live_manifest.py"]},
        {"key": "done_marker", "path": REPORTS / "DONE_pf_allocation",
         "max_age_s": ALLOCATION_MAX_AGE_S, "bound_from": "same clock as the allocation",
         "consumers": ["desks/mt5/research/hourly_cycle.py (leg completion)",
                       "desks/mt5/ops box task health"]},
        {"key": "forecast_log", "path": DATA / "pf_forecast_log.jsonl",
         "max_age_s": ALLOCATION_MAX_AGE_S, "bound_from": "appended once per allocator pass",
         "consumers": ["desks/mt5/research/allocator_attribution.py (expected vs realised)"]},
    ]


def _heat(alloc: dict[str, Any] | None) -> dict[str, Any]:
    """The pass's own heat arithmetic, and the LIVE book's, side by side.

    REPORTED, NEVER ENFORCED. Nothing here can raise or lower a fraction; a shortfall against the
    20% floor is published so it can be FIXED UPWARD, which is the only direction the principal's
    standing order allows anyone to move it.
    """
    out: dict[str, Any] = {"status": UNMEASURED}
    try:
        from mt5desk.gateway_config_fallback import HEAT_HARD_CEILING, HEAT_TARGET
        out["floor"], out["hard_ceiling"] = float(HEAT_TARGET), float(HEAT_HARD_CEILING)
        out["floor_from"] = "mt5desk.gateway_config_fallback.HEAT_TARGET"
    except Exception as exc:                                   # pragma: no cover - import guard
        out["floor_why"] = f"heat floor unreadable ({type(exc).__name__}: {exc})"
    if alloc is None:
        out["why"] = "no allocation artifact on disk"
        return out
    h = alloc.get("heat") or {}
    book = {str(k): float(v) for k, v in (alloc.get("book") or {}).items()}
    out.update({
        "status": "MEASURED",
        "resolved": h.get("resolved", h.get("total")),
        "deployed": h.get("heat_deployed"),
        "binding": h.get("binding"),
        "certified": h.get("certified"),
        "filled": h.get("filled"),
        "shortfall": h.get("shortfall"),
        "book_sum": round(sum(book.values()), 6),
        "n_funded": len(book),
        "state": h.get("state"),
    })
    floor = out.get("floor")
    resolved = out.get("resolved")
    if isinstance(floor, float) and isinstance(resolved, (int, float)):
        out["at_or_above_floor"] = bool(float(resolved) >= floor - 1e-4)
    out["live_book"] = _live_book(alloc, book)
    return out


def _live_book(alloc: dict[str, Any], book: dict[str, float]) -> dict[str, Any]:
    """What the LIVE rows will actually be sized at, joined against the allocator's book.

    The fraction a live row gets is `clamp_risk_frac(book fraction if the join lands, else the
    row's own)`, which FLOORS at BASE_RISK_FRAC -- so this is the number that answers "is the
    live book carrying its heat", and it can only be read by doing the same join the gateway
    does.
    """
    out: dict[str, Any] = {"status": UNMEASURED}
    try:
        from mt5desk.sizing import clamp_risk_frac
        from scripts.check_allocator_join import _book_key
    except Exception as exc:
        out["why"] = f"join/sizing unimportable ({type(exc).__name__}: {exc})"
        return out
    doc = _read(DATA / "sleeves.json")
    rows = (doc or {}).get("sleeves") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        out["why"] = "data/sleeves.json unreadable or has no sleeves list"
        return out
    live = [r for r in rows if isinstance(r, dict)
            and str(r.get("status") or "").upper() == "LIVE"]
    fb = {str(k): float(v) for k, v in
          ((alloc.get("book_fallback") or {}).get("book") or {}).items()}
    per: dict[str, Any] = {}
    total = 0.0
    n_joined = 0
    for r in live:
        key = _book_key(r, book) or _book_key(r, fb)
        src = book.get(key, fb.get(key)) if key else None
        frac = clamp_risk_frac(src if src is not None else r.get("risk_frac"))
        n_joined += int(key is not None)
        total += frac
        per[str(r.get("name"))] = {"frac": round(float(frac), 6),
                                   "from_book": key is not None, "book_key": key,
                                   "book_frac": (round(float(src), 6)
                                                 if src is not None else None)}
    out.update({"status": "MEASURED", "n_live": len(live), "n_joined": n_joined,
                "sum_risk_frac": round(total, 6), "rows": per,
                "note": ("sum of per-trade risk fractions over LIVE rows: not the portfolio "
                         "heat (positions are not simultaneous), but it is the number that "
                         "falls when a join breaks and every row drops to BASE_RISK_FRAC")})
    return out


def _join() -> dict[str, Any]:
    try:
        from scripts.check_allocator_join import measure
        return dict(measure())
    except Exception as exc:                                   # pragma: no cover - import guard
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}


def _stand_down(now: float) -> dict[str, Any]:
    """The last NAMED stand-down `pf_allocator` wrote, and whether it still covers the gap."""
    doc = _read(STANDDOWN)
    if doc is None:
        return {"status": "NONE", "covers_gap": False, "reason": None,
                "why": "no reports/ALLOCATOR_STANDDOWN.json on disk"}
    age = _age_s(STANDDOWN, now=now)
    return {"status": str(doc.get("status") or "UNKNOWN"), "at": doc.get("at"),
            "mode": doc.get("mode"), "reason": doc.get("reason"), "why": doc.get("why"),
            "age_s": None if age is None else round(age, 1),
            "covers_gap": bool(age is not None and age <= ALLOCATION_MAX_AGE_S
                               and str(doc.get("status") or "").upper() == "STOOD_DOWN")}


def measure(*, now: float | None = None) -> dict[str, Any]:
    """The whole liveness reading. Pure: reads artifacts, writes nothing."""
    now = time.time() if now is None else now
    alloc = _read(ALLOCATION)
    out_rows: list[dict[str, Any]] = []
    for spec in outputs():
        p: Path = spec["path"]
        age = _age_s(p, now=now)
        alt = spec.get("alt_path")
        alt_age = _age_s(alt, now=now) if isinstance(alt, Path) else None
        if age is None and alt_age is not None and isinstance(alt, Path):
            age, p = alt_age, alt
        row = {"key": spec["key"], "path": str(p.relative_to(ROOT)).replace("\\", "/"),
               "exists": age is not None,
               "age_s": None if age is None else round(age, 1),
               "age_h": None if age is None else round(age / 3600.0, 2),
               "max_age_s": spec["max_age_s"], "bound_from": spec["bound_from"],
               "fresh": bool(age is not None and age <= float(spec["max_age_s"])),
               "consumers": spec["consumers"]}
        if isinstance(alt, Path):
            row["alt_path"] = str(alt.relative_to(ROOT)).replace("\\", "/")
            row["alt_age_h"] = None if alt_age is None else round(alt_age / 3600.0, 2)
        out_rows.append(row)

    in_rows: list[dict[str, Any]] = []
    for inp in inputs():
        age = _age_s(inp.path, now=now)
        used, said = _declaration(alloc, inp.declared_by)
        if age is None:
            verdict = UNMEASURED
        elif age <= inp.max_age_s:
            verdict = "FRESH"
        else:
            verdict = "STALE"
        in_rows.append({
            "key": inp.key, "path": str(inp.path.relative_to(ROOT)).replace("\\", "/"),
            "exists": age is not None,
            "age_s": None if age is None else round(age, 1),
            "age_h": None if age is None else round(age / 3600.0, 2),
            "max_age_s": inp.max_age_s, "bound_from": inp.bound_from,
            "verdict": verdict, "how_used": inp.how,
            # `used` is the ALLOCATOR's own declaration, read out of the pass on disk -- never
            # this organ's inference. None means the artifact records nothing either way.
            "used": used, "declared": said,
            # A stale input the allocator declared neutral is an honest degrade; a stale one it
            # declared USED is the pass conditioning on yesterday's world, which is the breach.
            "degraded_honestly": bool(verdict != "FRESH" and used is False),
        })

    heat = _heat(alloc)
    join = _join()
    sd = _stand_down(now)
    alloc_row = next(r for r in out_rows if r["key"] == "allocation")
    proof_row = next(r for r in out_rows if r["key"] == "proof")

    breaches: list[dict[str, str]] = []
    if not alloc_row["exists"]:
        breaches.append({"check": "ALLOCATION", "why": "no allocation on disk at "
                                                       f"{alloc_row['path']}"})
    elif not alloc_row["fresh"]:
        breaches.append({"check": "ALLOCATION_STALE",
                         "why": f"allocation is {alloc_row['age_h']}h old "
                                f"(> {alloc_row['max_age_s'] / 3600:.1f}h)"})
    if not proof_row["exists"]:
        breaches.append({"check": "PROOF", "why": f"no certificate at {proof_row['path']}"})
    elif not proof_row["fresh"]:
        breaches.append({"check": "PROOF_STALE",
                         "why": f"certificate is {proof_row['age_h']}h old "
                                f"(> {proof_row['max_age_s'] / 3600:.1f}h)"})
    for r in in_rows:
        if r["verdict"] != "FRESH" and r["used"] is not False:
            breaches.append({"check": f"INPUT_{r['key'].upper()}",
                             "why": f"{r['path']} is {r['verdict']} (age {r['age_h']}h > "
                                    f"{r['max_age_s'] / 3600:.1f}h) and the pass on disk does "
                                    f"not declare it UNMEASURED ({r['declared']})"})
    if str(join.get("status")) == "BROKEN":
        breaches.append({"check": "JOIN", "why": str(join.get("why"))[:300]})

    # A CYCLE THAT PRODUCED NEITHER. The only legal states are "there is a fresh allocation" and
    # "there is a named stand-down that covers the gap". Nothing is the third state, and it is
    # the one this organ exists to make impossible to read as a decision.
    if (not alloc_row["fresh"]) and not sd["covers_gap"]:
        breaches.append({"check": "SILENT",
                         "why": "no fresh allocation and no named stand-down covering the gap: "
                                "the cycle produced nothing and said nothing"})
    verdict = "LIVE" if alloc_row["fresh"] else ("STOOD_DOWN" if sd["covers_gap"] else "ABSENT")
    return {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "schema": 1,
        "verdict": verdict,
        "ok": not breaches,
        "why": ("allocation and certificate are fresh and every input the pass conditioned on is "
                "within its own bound" if not breaches
                else "; ".join(b["why"] for b in breaches)[:600]),
        "cadence_s": {"cycle": CYCLE_S, "allocation_max_age_s": ALLOCATION_MAX_AGE_S},
        "outputs": out_rows,
        "inputs": in_rows,
        "n_inputs_fresh": sum(1 for r in in_rows if r["verdict"] == "FRESH"),
        "n_inputs_stale": sum(1 for r in in_rows if r["verdict"] == "STALE"),
        "n_inputs_unmeasured": sum(1 for r in in_rows if r["verdict"] == UNMEASURED),
        "heat": heat,
        "join": join,
        "stand_down": sd,
        "breaches": breaches,
        "boundary": ("REPORT ONLY. This organ reads artifacts and publishes ages, declarations "
                     "and the join. It sets no fraction, no cap and no veto, and it never "
                     "touches the 20% heat floor, the 0.02-lot gold floor or the daily-loss "
                     "parameters."),
    }


def run(*, budget_s: float = 120.0, write: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    rep = measure()
    rep["elapsed_s"] = round(time.monotonic() - started, 3)
    rep["budget_s"] = float(budget_s)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
        try:
            from libs.ops.events import leg_events
            leg_events("allocator_liveness", "OK" if rep["ok"] else "BREACH",
                       verdict=rep["verdict"], n_breaches=len(rep["breaches"]),
                       n_inputs_stale=rep["n_inputs_stale"], artifact=str(OUT))
        except Exception:                                      # pragma: no cover - events opt.
            pass
    return rep


def _print(rep: dict[str, Any]) -> None:
    h = rep["heat"]
    print(f"ALLOCATOR LIVENESS: {rep['verdict']} -- {rep['why'][:200]}")
    for r in rep["outputs"]:
        print(f"  out {r['key']:13} {'FRESH' if r['fresh'] else 'STALE/ABSENT':12} "
              f"age={r['age_h']}h  {r['path']}")
    for r in rep["inputs"]:
        mark = r["verdict"] if r["used"] is not False else f"{r['verdict']}/declared-neutral"
        print(f"  in  {r['key']:22} {mark:24} age={r['age_h']}h  used={r['used']}")
    lb = h.get("live_book") or {}
    print(f"  heat resolved={h.get('resolved')} floor={h.get('floor')} "
          f"book_sum={h.get('book_sum')} filled={h.get('filled')}")
    print(f"  live book: {lb.get('n_joined')}/{lb.get('n_live')} rows joined, "
          f"sum_risk_frac={lb.get('sum_risk_frac')}")
    print(f"  join: {rep['join'].get('status')} -- {str(rep['join'].get('why'))[:160]}")
    sd = rep["stand_down"]
    print(f"  stand-down: {sd.get('status')} {sd.get('reason') or ''} "
          f"covers_gap={sd.get('covers_gap')}")
    for b in rep["breaches"]:
        print(f"  BREACH {b['check']}: {b['why'][:200]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled shape)")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rep = run(budget_s=args.budget_s, write=not args.dry_run)
    if args.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        _print(rep)
    # NEVER NON-ZERO. The leg publishes; `scripts/check_allocator_liveness.py` is the fence that
    # fails, and a measurement organ that exits 1 would take the hourly cycle's remaining legs
    # with it for a condition the gate already owns.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
