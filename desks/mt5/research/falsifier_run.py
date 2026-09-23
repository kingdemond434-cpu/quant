#!/usr/bin/env python3
"""Ask every certificate the objections nobody has asked it, cheapest and most lethal first.

    python desks/mt5/research/falsifier_run.py [--budget-sec 600] [--limit N]

THE BATTERY WAS WRITTEN AND NEVER FIRED. `libs/validation/falsifiers.py` is the blueprint object
exactly -- six executable objections, each with a declared cost in seconds and a prior kill rate
by failure class, scheduled by `argsort(-P(kill | class) / cost_s)` with the pre-mortem's own
class first -- and a grep across the tree for its importers returns nothing. `redteam.py`, the
per-certificate placebo battery (entry_shift / side_flip / random_entry / label_shuffle), is
reachable only through it. Measured 2026-09-08: 66 certificates in UNIVERSAL_SURVIVORS.json, and
not one has been asked whether its edge survives a one-bar shift, a mirrored side, a random entry
with the same risk geometry, a truncated history or the loss of its best decile of trades. Only
the 3x cost stress and the parameter/state neighbourhood ever ran.

WHAT THIS IS, AND WHAT IT IS NOT. This is a DEFECT REPORT written beside the certificate, which
is what `redteam.py` already specifies for itself ("it withdraws nothing on its own: a red-team
finding is a defect report for a human"). A KILLED verdict here revokes nothing, gates nothing,
resizes nothing and touches no canon file; the gauntlet remains the arbiter and the forward clock
remains the evidence. What changes is that a certificate the placebos cannot distinguish from
noise is now a dated fact on disk instead of a question nobody asked.

THE INPUTS ARE THE GAUNTLET'S OWN. Bars, signals and the cost model for a certificate come from
`external_gauntlet.build_cell`, the one function that builds the executable the certificate was
granted on -- so the falsifiers test the thing that was certified, not a re-implementation of it.
The truncation test needs the family as a callable; it is given the same builder on a truncated
frame (`h1_override`), so a lookahead in the builder's input resolution is caught as well as one
in the family. A test whose input this desk cannot supply (the USD driver: no instrument on the
desk is named for that role) is UNMEASURED with the reason, never skipped silently.

BOUNDED, AND HONEST ABOUT THE BOUND. A wall-clock budget (default 600s, inside the cycle's
720s leg timeout) is checked before every certificate and before every test; whatever it does
not reach is recorded as NOT_REACHED carrying its previous verdict, and the next run starts with
the certificates measured longest ago -- the gauntlet's own starvation-rotation rule, applied
here for the same reason: a fixed order would re-test the head of the list every hour and never
reach its tail.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.validation import falsifiers  # noqa: E402

#: The certificates. The reports file is the published canon; the data-side canon is read when
#: the reports file is absent, and the report records which one it read.
CERTS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
REPORT = BASE / "reports" / "FALSIFIER_VERDICTS.json"

#: Wall clock one run may spend. 600s sits inside `hourly_cycle.SEARCH_BUDGET_SEC` (720s), the
#: subprocess timeout a producer leg runs under, with margin for the interpreter start and the
#: report write. A run that overran the leg would be killed with its report unwritten.
DEFAULT_BUDGET_SEC = 600.0
#: Memory this run declares to the job lock. A frame cache of up to 1.3M bar rows plus the
#: placebo battery's 50 re-placements per certificate; declared at the level `backfill_coverage`
#: declares for the same frame loads.
NEED_MB = 700
#: The graveyard model refuses to name a failure class below this many judged rows (its own
#: `deepening_worker` threshold); under it the catalogue order alone is used and the report
#: says so.
MIN_JUDGED_FOR_PREMORTEM = 50

#: Why the USD driver is never supplied, written into every report so the UNMEASURED
#: `usd_residual` row is read as a desk gap and not as a test that was skipped.
USD_GAP = ("no USD driver bars: the alpha grammar names a `usd` driver ROLE and nothing on the "
           "desk names the instrument that fills it, so usd_residual is UNMEASURED for every "
           "certificate until one is registered")

LAW = ("DEFECT REPORT ONLY. A KILLED verdict withdraws nothing, gates nothing and resizes "
       "nothing: the gauntlet remains the arbiter and the forward clock the evidence. This file "
       "records, beside each certificate, which executable objection it failed first.")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def load_certificates(path: Path = CERTS, fallback: Path = CANON) -> tuple[dict[str, dict], str]:
    """`id -> certificate` from the reports canon, else the data canon, and which one was read.

    Both files carry `survivors` keyed by certificate id, each with a `shadow_spec` naming the
    symbol, family and params the certificate was granted on. An unreadable or empty file is
    an empty docket with its reason -- never a run over nothing that reports SURVIVED.
    """
    for p in (path, fallback):
        doc = _json(p)
        surv = doc.get("survivors")
        if isinstance(surv, dict) and surv:
            return {str(k): v for k, v in surv.items() if isinstance(v, dict)}, str(p)
    return {}, f"neither {path} nor {fallback} carries a non-empty `survivors` map"


def _meta(path: Path = UNIVERSE) -> dict:
    return _json(path)


def _builder() -> Callable[..., dict | None]:
    """`external_gauntlet.build_cell`, imported lazily.

    The gauntlet module loads pandas, every family module and a frame cache at import; a
    `--help`, an empty docket or a test with its own builder must not pay for that.
    """
    import external_gauntlet as eg  # type: ignore[import-not-found]
    return eg.build_cell


def cost_fraction(df: Any, costs: Any) -> tuple[float | None, str]:
    """The cell's round-trip cost in LOG-RETURN units, which is what the falsifiers subtract.

    `Costs.per_oz_roundtrip()` is the round trip per lot in the convention the engine divides by
    `contract_oz`, so the ratio is a price-unit cost; over the median close it is a fraction of
    price, which at these magnitudes is the log return the falsifiers compare against. A cost
    that cannot be priced is None, and every cost-dependent test is then UNMEASURED: running
    them at zero would grade the certificate on its GROSS edge and call it a pass.
    """
    if costs is None:
        return None, "unpriced: the cell carries no cost model"
    if isinstance(costs, (int, float)) and not isinstance(costs, bool):
        return float(costs), "given as a fraction"
    try:
        import numpy as np
        per_unit = float(costs.per_oz_roundtrip()) / float(costs.contract_oz)
        px = float(np.nanmedian(df["close"].to_numpy(dtype=float)))
    except Exception as exc:
        return None, f"unpriced: {type(exc).__name__}: {exc}"
    if not (px > 0) or not (per_unit >= 0):
        return None, f"unpriced: median close {px!r}, per-unit round trip {per_unit!r}"
    return per_unit / px, "Costs.per_oz_roundtrip()/contract_oz over the median close"


def build_inputs(cert: dict, meta: dict,
                 build: Callable[..., dict | None]) -> tuple[dict | None, str]:
    """Bars, signals, cost and a truncation callable for one certificate, or why not."""
    spec = cert.get("shadow_spec") or {}
    sym = str(spec.get("symbol") or cert.get("sym") or "")
    family = str(spec.get("family") or "")
    params = dict(spec.get("params") or {})
    if not sym or not family:
        return None, "certificate names no symbol/family in shadow_spec"
    try:
        obj = build(sym, family, params, meta)
    except Exception as exc:
        return None, f"build_cell raised {type(exc).__name__}: {exc}"
    if not obj or obj.get("df") is None:
        return None, (f"build_cell returned no executable cell for {sym}.{family}: the bars or "
                      f"the family's inputs are absent on this host")
    sigs = list(obj.get("sigs") or [])
    cost, cost_basis = cost_fraction(obj["df"], obj.get("costs"))

    def family_fn(frame: Any, **_kw: Any) -> list:
        # The SAME builder on a truncated frame: the truncation test then covers the builder's
        # input resolution as well as the family itself.
        out = build(sym, family, params, meta, h1_override=frame)
        return list((out or {}).get("sigs") or [])

    return {"df": obj["df"], "signals": sigs, "cost": cost, "cost_basis": cost_basis,
            "family": family_fn, "params": {}, "usd": None,
            "symbol": sym, "family_name": family, "timeframe": obj.get("timeframe"),
            "cell_params": params}, ""


#: Tests that subtract the cost and are therefore UNMEASURED when it cannot be priced.
COST_DEPENDENT = frozenset({"cost_surface", "half_stability", "usd_residual",
                            "tail_worst_decile", "placebo_battery"})


def falsify(inputs: dict, deadline: float,
            premortem: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the catalogue in schedule order against one certificate, bounded by `deadline`.

    Every test is run (no stop at the first kill): the report wants the count of kills, not
    only the first, because two independent objections failing is a different fact from one.
    The FIRST killer in schedule order is still named -- it is the cheapest objection that
    settled the question, which is what a re-test should start with.
    """
    order = falsifiers.schedule(premortem)
    results: dict[str, Any] = {}
    run: list[str] = []
    not_reached: list[str] = []
    unmeasured: dict[str, str] = {}
    kills: list[str] = []
    t_start = time.monotonic()
    for name in order:
        if time.monotonic() > deadline:
            not_reached.append(name)
            continue
        if inputs["cost"] is None and name in COST_DEPENDENT:
            res: dict[str, Any] = {"verdict": "UNMEASURED", "why": inputs["cost_basis"]}
        elif name == "usd_residual" and inputs.get("usd") is None:
            res = {"verdict": "UNMEASURED", "why": USD_GAP}
        else:
            t0 = time.monotonic()
            try:
                res = dict(falsifiers.FALSIFIERS[name](
                    inputs["df"], inputs["signals"], float(inputs["cost"] or 0.0),
                    family=inputs.get("family"), params=inputs.get("params") or {},
                    usd=inputs.get("usd")))
            except Exception as exc:
                res = {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
            res["seconds"] = round(time.monotonic() - t0, 3)
        res.setdefault("seconds", 0.0)
        results[name] = res
        run.append(name)
        v = str(res.get("verdict"))
        if v == "FAIL":
            kills.append(name)
        elif v != "PASS":
            unmeasured[name] = str(res.get("why") or f"n={res.get('n')}")
    passed = [n for n in run if str(results[n].get("verdict")) == "PASS"]
    status = ("KILLED" if kills else "SURVIVED" if passed else "UNMEASURED")
    return {
        "status": status, "order": order, "tests_run": run, "kills": kills,
        "first_killer": (kills[0] if kills else None), "passed": passed,
        "unmeasured": unmeasured, "not_reached": not_reached,
        "complete": not not_reached, "results": results,
        "premortem_class": (premortem or {}).get("failure_class"),
        "seconds": round(time.monotonic() - t_start, 3),
    }


def _premortems(certs: dict[str, dict]) -> tuple[dict[str, dict], str]:
    """The graveyard model's failure class per certificate, so it can jump the queue."""
    try:
        from libs.research.graveyard_model import GraveyardModel
        from libs.research.hypothesis_graph import Graph
        gm = GraveyardModel().fit(Graph().rows())
    except Exception as exc:
        return {}, f"catalogue order only: graveyard model unavailable ({type(exc).__name__})"
    if gm.n < MIN_JUDGED_FOR_PREMORTEM:
        return {}, (f"catalogue order only: {gm.n} judged rows in the graveyard, below the "
                    f"{MIN_JUDGED_FOR_PREMORTEM} the model needs to name a class")
    out: dict[str, dict] = {}
    for cid, c in certs.items():
        spec = c.get("shadow_spec") or {}
        try:
            out[cid] = gm.premortem({"family": spec.get("family"), "symbol": spec.get("symbol"),
                                     "source": "", "params": dict(spec.get("params") or {})})
        except Exception:
            continue
    return out, (f"GraveyardModel over {gm.n} judged rows: each certificate's most likely "
                 f"failure class is tested first")


def rotation(cert_ids: list[str], prior: dict[str, dict]) -> list[str]:
    """Longest-unmeasured first, then id. Never-measured certificates lead."""
    def key(cid: str) -> tuple[str, str]:
        return (str((prior.get(cid) or {}).get("measured_at") or ""), cid)
    return sorted(cert_ids, key=key)


def run(*, certs_path: Path = CERTS, fallback: Path = CANON, report_path: Path = REPORT,
        budget_sec: float = DEFAULT_BUDGET_SEC, limit: int = 0, premortem: bool = True,
        universe: Path = UNIVERSE, write: bool = True) -> dict[str, Any]:
    t_run = time.monotonic()
    deadline = t_run + max(0.0, float(budget_sec))
    certs, source = load_certificates(certs_path, fallback)
    prior = (_json(report_path).get("per_certificate") or {}) if report_path.exists() else {}
    doc: dict[str, Any] = {
        "generated_utc": _now(), "law": LAW, "source": source,
        "budget_sec": float(budget_sec), "n_certificates": len(certs),
        "catalogue": {n: {"cost_s": c, "class": k, "prior_kill": falsifiers.DEFAULT_KILL.get(k)}
                      for n, (c, k) in falsifiers.CATALOGUE.items()},
        "order_rule": ("argsort(-P(kill | class) / cost_s), the pre-mortem's own class first "
                       "(libs/validation/falsifiers.schedule)"),
        "input_gaps": {"usd_residual": USD_GAP},
        "rotation": ("certificates measured longest ago run first; NOT_REACHED entries carry "
                     "their previous verdict so the report converges across hourly runs"),
    }
    if not certs:
        doc.update({"status": "NO_CERTIFICATES", "why": source, "per_certificate": {},
                    "summary": {}, "seconds": round(time.monotonic() - t_run, 3)})
        if write:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        return doc

    pre, pre_basis = _premortems(certs) if premortem else ({}, "catalogue order only: disabled")
    doc["premortem_basis"] = pre_basis
    meta = _meta(universe)
    build: Callable[..., dict | None] | None = None
    build_err = ""
    try:
        build = _builder()
    except Exception as exc:
        build_err = f"gauntlet builder unavailable: {type(exc).__name__}: {exc}"

    order = rotation(list(certs), prior)
    chosen = set(order[:limit] if limit > 0 else order)
    per: dict[str, dict] = {}
    for cid in order:
        spec = certs[cid].get("shadow_spec") or {}
        entry: dict[str, Any] = {
            "symbol": spec.get("symbol") or certs[cid].get("sym"),
            "family": spec.get("family"), "params": spec.get("params") or {},
        }
        previous = prior.get(cid) or {}
        if cid not in chosen or time.monotonic() > deadline:
            entry.update({"status": "NOT_REACHED",
                          "why": ("outside --limit" if cid not in chosen else
                                  f"the {budget_sec:.0f}s budget was spent before this "
                                  f"certificate; it leads the next run"),
                          "measured_at": previous.get("measured_at"),
                          "previous": ({k: previous.get(k) for k in
                                        ("status", "first_killer", "kills", "measured_at")}
                                       if previous else None)})
            per[cid] = entry
            continue
        if build is None:
            entry.update({"status": "UNMEASURED", "why": build_err, "measured_at": _now()})
            per[cid] = entry
            continue
        t0 = time.monotonic()
        inputs, why = build_inputs(certs[cid], meta, build)
        build_s = round(time.monotonic() - t0, 3)
        if inputs is None:
            entry.update({"status": "UNMEASURED", "why": why, "measured_at": _now(),
                          "seconds": {"build": build_s, "tests": 0.0}})
            per[cid] = entry
            continue
        out = falsify(inputs, deadline, pre.get(cid))
        entry.update(out)
        entry.update({"n_signals": len(inputs["signals"]), "timeframe": inputs.get("timeframe"),
                      "cost_fraction": (round(inputs["cost"], 8) if inputs["cost"] is not None
                                        else None),
                      "cost_basis": inputs["cost_basis"], "measured_at": _now(),
                      "seconds": {"build": build_s, "tests": out["seconds"]}})
        per[cid] = entry

    counts: dict[str, int] = {}
    killers: dict[str, int] = {}
    for e in per.values():
        counts[e["status"]] = counts.get(e["status"], 0) + 1
        if e.get("first_killer"):
            killers[e["first_killer"]] = killers.get(e["first_killer"], 0) + 1
    reached = [c for c, e in per.items() if e["status"] != "NOT_REACHED"]
    doc.update({
        "status": "MEASURED" if reached else "NOT_REACHED",
        "n_reached": len(reached), "n_not_reached": len(per) - len(reached),
        "summary": {"by_status": counts, "first_killers": killers,
                    "incomplete_batteries": sum(1 for e in per.values()
                                                if e.get("complete") is False)},
        "per_certificate": per,
        "seconds": round(time.monotonic() - t_run, 3),
    })
    if write:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="run the falsifier catalogue over every certificate")
    ap.add_argument("--budget-sec", type=float, default=DEFAULT_BUDGET_SEC,
                    help="wall clock the run may spend; what it does not reach is recorded")
    ap.add_argument("--limit", type=int, default=0, help="certificates per run (0 = all)")
    ap.add_argument("--certs", type=Path, default=CERTS)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    ap.add_argument("--no-premortem", action="store_true",
                    help="catalogue order only; skip the graveyard model")
    args = ap.parse_args(argv)
    try:
        from job_lock import exclusive_job
    except Exception:
        exclusive_job = None                                              # type: ignore[assignment]
    if exclusive_job is not None:
        with exclusive_job("falsifier_run", need_mb=NEED_MB) as go:
            if not go:
                print("falsifier_run: stood down (duplicate writer or no room); the next hourly "
                      "pass resumes from the same rotation")
                return 0
            doc = run(certs_path=args.certs, report_path=args.report, budget_sec=args.budget_sec,
                      limit=args.limit, premortem=not args.no_premortem, universe=args.universe)
    else:
        doc = run(certs_path=args.certs, report_path=args.report, budget_sec=args.budget_sec,
                  limit=args.limit, premortem=not args.no_premortem, universe=args.universe)
    s = doc.get("summary") or {}
    print(f"falsifier_run: {doc.get('status')} {doc.get('n_reached', 0)}/{doc['n_certificates']} "
          f"certificate(s) reached in {doc.get('seconds')}s of {doc['budget_sec']:.0f}s; "
          f"{s.get('by_status', {})} first killers {s.get('first_killers', {})}")
    for cid, e in list((doc.get("per_certificate") or {}).items())[:12]:
        print(f"   {e['status']:12} {cid[:60]:60} first_killer={e.get('first_killer')} "
              f"kills={len(e.get('kills') or [])} unmeasured={len(e.get('unmeasured') or {})}")
    print(f"written: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
