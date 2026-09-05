"""FeatureROI: what each feature earned per unit of effort, and the effort the desk stops spending.

    FeatureROI_j = dE[logW | F_j] / (acquisition + compute + maintenance + multiplicity)

THE HALF OF THE WAREHOUSE THAT WAS MISSING. `libs.data.feature_store` records what every feature
IS -- its source, its clock, its code, its coverage. Nothing recorded what any of it was WORTH,
so the vocabulary could only ever grow: every parameterisation anyone tried kept its block, kept
being refreshed, kept counting against the multiplicity charge of everything tested beside it,
and no organ had grounds to stop. This is the feedback arm. It measures, it writes a lifecycle
state onto every sidecar, and `feature_lifecycle.withdraw` turns that state into the one
operational answer: may an organ spend compute on this.

WHAT IT JOINS, AND WHAT EACH SIDE CONTRIBUTES

  the sidecars          the population -- every block in the warehouse, its name, its source, how
                        many variants of it exist and how long each took to compute
  the conditioning      `data/capital_modifier_ledger.jsonl` and `reports/CAPITAL_MODIFIERS.json`:
  ledger                per funded sleeve, what conditioning on a state CLAIMED -- the shrunk
                        conditional mean against the unconditional one. That claim, times the
                        sleeve's share of the book, is dE[logW | F_j] in log-wealth per day.
  RESEARCH_PNL.json     the allocator's own `share_of_heat` per funded sleeve. Preferred over the
                        ledger row's raw heat because it is the share the allocator actually
                        solved for; when a sleeve is missing from it the row's own heat is used
                        and the fallback is COUNTED, never hidden.
  allocator_attribution the growth decomposition's `state` term. When it is measured, the
                        ledger's total claim is scaled to it, so what the features claim can
                        never exceed what the decomposition attributes to state. When it is
                        UNMEASURED the scale is 1.0 and the report says so.

HOW A FEATURE IS JOINED TO A STATE. The ledger names the STATE the allocator conditioned on
(`weekday`, `event`, a phase key), not the feature underneath it. A feature is credited when its
name appears as a token in that state key or as an admitted dimension in STATE_ADMISSION.json.
MEASURED ON THIS TREE, 2026-09-05: no state dimension is named after any warehouse feature, so
every feature reads UNMEASURED and the report says exactly that under `gaps`. That is the honest
state of the join and not a defect in it -- the day a dimension is named `cot_z`, the arithmetic
below starts returning numbers with no further wiring.

THE COST IS IN DECLARED UNITS, exactly as `research_pnl` prices a trial: compute is the store's
own measured seconds, and acquisition / maintenance / multiplicity are a declared table, because
pretending to measure the cost of maintaining a feed in seconds would be a fiction with a decimal
point on it. What matters for a RATIO is that every feature is priced the same way.

BELOW MIN_N NOTHING DIES. A verdict needs `feature_lifecycle.MIN_N` observations; under that the
ROI is reported with its n and the verdict is UNMEASURED (L1.28a), which is not zero and not a
pass, and the lifecycle refuses to move a feature to DEAD on it.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.data import feature_lifecycle as lc  # noqa: E402
from libs.data import feature_store as fs  # noqa: E402
from libs.data.feature_store import DEFAULT_SOURCE, FeatureStore  # noqa: E402

#: The warehouse this pass reads. Named here rather than taken from `FeatureStore()`'s default so
#: one pass can be pointed at a fixture tree without the store's own default moving.
FEATURES = fs.STORE
LEDGER = _DESK / "data" / "capital_modifier_ledger.jsonl"
MODIFIERS = _DESK / "reports" / "CAPITAL_MODIFIERS.json"
ATTRIBUTION = _DESK / "reports" / "allocator_attribution.json"
RESEARCH_PNL = _DESK / "reports" / "RESEARCH_PNL.json"
STATE_ADMISSION = _DESK / "reports" / "STATE_ADMISSION.json"
CANON = _DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
EXECUTION = _DESK / "reports" / "execution_intelligence.json"
REPORT = _DESK / "reports" / "FEATURE_ROI.json"

#: DECLARED cost units, per the `research_pnl` doctrine: the two halves of a ROI must price
#: effort the same way, and a declared table both halves read beats a measured number only one
#: of them has. Compute is the exception -- the store measures it -- and is converted at
#: COMPUTE_UNITS_PER_S so it lands on the same scale as the rest.
COMPUTE_UNITS_PER_S = 1.0
#: Fetching, parsing and date-checking an external feed, per feature, per pass. Bars cost none of
#: this: they are already on the box for every other reason the desk has.
ACQUISITION_EXTERNAL = 5.0
#: Keeping an external feed honest: re-certification, revision handling, the schema watch.
MAINTENANCE_EXTERNAL = 3.0
#: Every additional parameterisation is another trial everything tested beside it must deflate
#: against. This is the multiplicity the feature imposes on the desk, charged to the feature.
MULTIPLICITY_PER_VARIANT = 1.0
#: A ROI needs a positive denominator. A feature that somehow cost nothing measurable still costs
#: the attention of being in the vocabulary.
MIN_COST_UNITS = 1.0

#: |corr| at or above `feature_lifecycle.REDUNDANT_ABS_CORR` makes a feature REDUNDANT. Bounded
#: so one pass cannot spend its whole budget loading blocks: the widest group of same-bar blocks
#: is compared, the rest are reported as not compared.
MAX_SPAN_BLOCKS = 64
#: Rows two blocks must share, finite in both, before a correlation between them means anything.
MIN_SPAN_OVERLAP = 100

UNMEASURED = "UNMEASURED"


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in lines:
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _tokens(key: str) -> set[str]:
    """A state key split into the names it could be naming. `xauusd_cot_z_high` names `cot_z`."""
    low = str(key or "").lower()
    parts = [p for p in low.replace("-", "_").replace(".", "_").split("_") if p]
    out = {low}
    for i in range(len(parts)):
        for j in range(i + 1, len(parts) + 1):
            out.add("_".join(parts[i:j]))
    return out


def state_features(state_key: str, names: set[str]) -> set[str]:
    """Which warehouse features a ledger row's state key names. Containment on TOKENS, never on
    substrings: `hour` must not match `hourly_phase` by accident."""
    toks = _tokens(state_key)
    return {n for n in names if n.lower() in toks}


# --------------------------------------------------------------------------- the numerator
def claims(rows: list[dict[str, Any]], names: set[str],
           share_of_heat: dict[str, float]) -> tuple[dict[str, list[float]], dict[str, int]]:
    """Per feature, the log-wealth-per-day increments conditioning on it claimed.

        d_i = (mu_state - mu_uncond) * w_i

    where `w_i` is the sleeve's share of the book -- the allocator's own `share_of_heat` from
    RESEARCH_PNL when it carries the sleeve, else the ledger row's raw heat. The fallback is
    counted per feature so the report can say how much of the number rests on it.
    """
    per: dict[str, list[float]] = {}
    fallback: dict[str, int] = {}
    for r in rows:
        hit = state_features(str(r.get("state") or ""), names)
        if not hit:
            continue
        try:
            mu_s = float(r.get("mu_state"))
            mu_u = float(r.get("mu_uncond"))
            heat = float(r.get("heat") or 0.0)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(mu_s) and math.isfinite(mu_u)):
            continue
        sleeve = str(r.get("sleeve") or "")
        w = share_of_heat.get(sleeve)
        used_fallback = w is None
        if w is None:
            w = heat
        d = (mu_s - mu_u) * float(w)
        if not math.isfinite(d):
            continue
        for name in hit:
            per.setdefault(name, []).append(d)
            if used_fallback:
                fallback[name] = fallback.get(name, 0) + 1
    return per, fallback


def mean_ci(values: list[float]) -> tuple[float, tuple[float, float] | None, int]:
    """Mean, 95% normal CI and n. A single observation has a mean and no interval: reporting one
    from n=1 would be inventing a width the data never had."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n == 0:
        return 0.0, None, 0
    mean = float(arr.mean())
    if n < 2:
        return mean, None, n
    se = float(arr.std(ddof=1) / math.sqrt(n))
    if not math.isfinite(se) or se <= 0.0:
        return mean, (mean, mean), n
    return mean, (mean - 1.96 * se, mean + 1.96 * se), n


# --------------------------------------------------------------------------- the denominator
def cost_units(blocks: list[dict[str, Any]]) -> dict[str, float]:
    """The four cost terms for one feature, from its own blocks. Declared units throughout."""
    external = any(str(b.get("source") or DEFAULT_SOURCE) != DEFAULT_SOURCE for b in blocks)
    compute_s = 0.0
    for b in blocks:
        try:
            compute_s += float(b.get("compute_s") or 0.0)
        except (TypeError, ValueError):
            continue
    variants = len({json.dumps(b.get("params") or {}, sort_keys=True, default=str)
                    for b in blocks})
    acq = ACQUISITION_EXTERNAL if external else 0.0
    maint = MAINTENANCE_EXTERNAL if external else 0.0
    comp = round(compute_s * COMPUTE_UNITS_PER_S, 6)
    mult = variants * MULTIPLICITY_PER_VARIANT
    total = max(MIN_COST_UNITS, acq + comp + maint + mult)
    return {"acquisition": acq, "compute": comp, "maintenance": maint, "multiplicity": mult,
            "total": round(total, 6), "compute_s": round(compute_s, 6), "variants": variants,
            "external": external}


# --------------------------------------------------------------------------- who reads it
def consumers(name: str, ledger_names: set[str], admitted: set[str],
              canon_text: str, execution_text: str) -> frozenset[str]:
    """Which layers read this feature. Containment on tokens, on the artifacts each layer writes.

    THE CANON IS THE ONLY PROOF OF A GAUNTLET PASS on this desk, so a feature named inside a
    certificate is a certified consumer; STATE_ADMISSION's `admitted` list is the state layer's
    own record; the execution report is the execution layer's.
    """
    out: set[str] = set()
    low = name.lower()
    if low in canon_text:
        out.add(lc.CONSUMER_GAUNTLET)
    if name in ledger_names or low in {a.lower() for a in admitted}:
        out.add(lc.CONSUMER_STATE)
    if low in execution_text:
        out.add(lc.CONSUMER_EXECUTION)
    return frozenset(out)


# --------------------------------------------------------------------------- redundancy
def spanning(store: FeatureStore, blocks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per feature, the OTHER feature whose block correlates most with one of its own.

    Compared only within a group of blocks computed on the SAME bars (same `data_hash`), because
    a correlation between two different histories is not a statement about the features. The
    largest such group is used and the rest are reported as not compared: a bounded, stated
    sample beats an unbounded scan of the whole warehouse on a box that also has to trade.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for b in blocks:
        groups.setdefault(str(b.get("data_hash") or ""), []).append(b)
    if not groups:
        return {}
    key = max(groups, key=lambda k: len(groups[k]))
    chosen = groups[key][:MAX_SPAN_BLOCKS]
    loaded: list[tuple[str, np.ndarray]] = []
    for b in chosen:
        arr_p = store.root / f"{b.get('id')}.npy"
        try:
            arr = np.load(arr_p)
        except (OSError, ValueError):
            continue
        if arr.ndim == 1 and np.isfinite(arr).sum() >= MIN_SPAN_OVERLAP:
            loaded.append((str(b.get("name")), arr))
    out: dict[str, dict[str, Any]] = {}
    for i, (name_a, a) in enumerate(loaded):
        for j, (name_b, b_arr) in enumerate(loaded):
            if i == j or name_a == name_b or a.shape != b_arr.shape:
                continue
            ok = np.isfinite(a) & np.isfinite(b_arr)
            if int(ok.sum()) < MIN_SPAN_OVERLAP:
                continue
            x, y = a[ok], b_arr[ok]
            if x.std() <= 0 or y.std() <= 0:
                continue
            r = float(np.corrcoef(x, y)[0, 1])
            if not math.isfinite(r):
                continue
            cur = out.get(name_a)
            if cur is None or abs(r) > abs(float(cur["max_abs_corr"])):
                out[name_a] = {"spanned_by": name_b, "max_abs_corr": round(abs(r), 6),
                               "overlap": int(ok.sum()), "on_data_hash": key}
    return out


# --------------------------------------------------------------------------- the pass
def _share_of_heat(pnl: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for sleeve, row in (pnl.get("sleeves") or {}).items():
        if not isinstance(row, dict):
            continue
        try:
            out[str(sleeve)] = float(row["share_of_heat"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _state_scale(attribution: dict[str, Any], total_claim: float) -> tuple[float, str]:
    """Scale the ledger's total claim to the decomposition's measured `state` term.

    A ledger records what conditioning CLAIMED; the growth decomposition records what the book
    attributes to state. When both are measured and the claim is positive, the claims are scaled
    so their sum equals the attributed term -- the features may divide up the state term, never
    invent one beside it. When the term is UNMEASURED the scale is 1.0 and the claims are read
    as claims, which the report says out loud.
    """
    term = ((attribution.get("growth_decomposition") or {}).get("terms") or {}).get("state") or {}
    value = term.get("value")
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return 1.0, ("allocator_attribution's state term is UNMEASURED on this host, so the "
                     "conditioning ledger's claims are reported unscaled -- they are claims, not "
                     "attributed growth")
    if total_claim <= 0.0:
        return 1.0, (f"the state term is {float(value):+.8f}/day but the ledger's total claim is "
                     f"{total_claim:+.8f}: nothing positive to scale, so the claims stand as they "
                     "are")
    scale = float(value) / total_claim
    return scale, (f"claims scaled by {scale:.4f} so their sum equals allocator_attribution's "
                   f"state term ({float(value):+.8f} log-wealth/day): features divide the state "
                   "term, they do not add to it")


def run(*, write: bool = True) -> dict[str, Any]:
    store = FeatureStore(FEATURES)
    blocks = store.sidecars()
    by_name: dict[str, list[dict[str, Any]]] = {}
    for b in blocks:
        by_name.setdefault(str(b.get("name")), []).append(b)
    names = set(by_name)

    gaps: dict[str, str] = {}
    if not blocks:
        gaps["warehouse"] = (f"no feature blocks under {store.root}: the warehouse is empty on "
                             "this host, so there is nothing to price")

    rows = _jsonl(LEDGER)
    if not rows:
        gaps["conditioning_ledger"] = (
            f"{LEDGER.name} absent or empty on this host; pf_allocator writes it every pass, so "
            "no pass has run here. Every feature reads UNMEASURED, which is not zero")
    pnl = _json(RESEARCH_PNL)
    if not pnl:
        gaps["research_pnl"] = (f"{RESEARCH_PNL.name} absent; the allocator's share_of_heat per "
                                "sleeve is unavailable and the ledger's own heat is used instead")
    attribution = _json(ATTRIBUTION)
    if not attribution:
        gaps["allocator_attribution"] = (f"{ATTRIBUTION.name} absent; the state term cannot scale "
                                         "the ledger's claims")

    share = _share_of_heat(pnl)
    per_feature, fallback = claims(rows, names, share)
    ledger_states = sorted({str(r.get("state") or "") for r in rows if r.get("state")})
    if rows and not per_feature:
        gaps["state_join"] = (
            "no ledger state key names a warehouse feature. The allocator conditions on "
            f"{len(ledger_states)} state(s) ({', '.join(ledger_states[:6])}) and the warehouse "
            f"holds {len(names)} feature(s); until a dimension is named after one, dE[logW|F_j] "
            "has no evidence and every feature is UNMEASURED")

    total_claim = float(sum(sum(v) / max(1, len(v)) for v in per_feature.values()))
    scale, scale_why = _state_scale(attribution, total_claim)

    admitted = {str(a) for a in (_json(STATE_ADMISSION).get("admitted") or [])}
    canon_text = ""
    try:
        canon_text = CANON.read_text("utf-8").lower()
    except OSError:
        gaps["canon"] = f"{CANON.name} absent; no feature can be shown to sit inside a certificate"
    execution_text = ""
    try:
        execution_text = EXECUTION.read_text("utf-8").lower()
    except OSError:
        execution_text = ""
    ledger_named = {n for n in names if per_feature.get(n)}
    span = spanning(store, blocks)

    features: dict[str, dict[str, Any]] = {}
    counts = {"useful": 0, "state_only": 0, "execution_only": 0, "redundant": 0, "decaying": 0,
              "dead": 0, "revived": 0, "new": 0, "unmeasured": 0}
    for name, group in sorted(by_name.items()):
        cost = cost_units(group)
        values = per_feature.get(name, [])
        raw_mean, ci, n = mean_ci(values)
        benefit = raw_mean * scale
        ci_scaled = ((ci[0] * scale, ci[1] * scale) if ci is not None else None)
        measured = n >= lc.MIN_N
        roi = (benefit / cost["total"]) if measured else None
        roi_ci = ((ci_scaled[0] / cost["total"], ci_scaled[1] / cost["total"])
                  if (measured and ci_scaled is not None) else None)
        prior = str(group[0].get("status") or lc.NEW)
        # FALLING WINDOWS come from the feature's own previous ROI line: the ledger remembers its
        # last verdict, so decay is measured across passes rather than re-derived each day.
        prev = group[0].get("roi") if isinstance(group[0].get("roi"), dict) else {}
        falling = int(prev.get("falling_windows") or 0)
        prev_roi = prev.get("roi")
        if roi is not None and isinstance(prev_roi, (int, float)):
            falling = falling + 1 if roi < float(prev_roi) else 0
        sp = span.get(name, {})
        ev = lc.Evidence(
            roi=roi, n=n, ci=roi_ci,
            consumers=consumers(name, ledger_named, admitted, canon_text, execution_text),
            spanned_by=(str(sp["spanned_by"]) if sp else None),
            max_abs_corr=(float(sp["max_abs_corr"]) if sp else None),
            falling_windows=falling,
            revival=str(prev.get("revival") or ""),
        )
        status, why = lc.transition(prior, ev)
        effort = lc.withdraw(status)
        line = {
            "roi": (round(roi, 10) if roi is not None else None),
            "verdict": (UNMEASURED if not measured else "MEASURED"),
            "n": n, "min_n": lc.MIN_N,
            "ci": ([round(roi_ci[0], 10), round(roi_ci[1], 10)] if roi_ci else None),
            "benefit_logw_per_day": round(benefit, 10),
            "benefit_unscaled": round(raw_mean, 10),
            "state_scale": round(scale, 6),
            "cost_units": cost,
            "falling_windows": falling,
            "heat_fallback_rows": fallback.get(name, 0),
            "spanned": sp or None,
            "consumers": sorted(ev.consumers),
            "measured_at": datetime.now(tz=UTC).isoformat(),
            "why": why,
        }
        features[name] = {"status": status, "prior_status": prior,
                          "may_spend_compute": bool(effort), "effort_why": effort.why,
                          "blocks": len(group), **line}
        counts[status.lower()] = counts.get(status.lower(), 0) + 1
        if not measured:
            counts["unmeasured"] += 1
        if write:
            store.set_status(name, status, line)

    doc = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "formula": ("FeatureROI_j = dE[logW | F_j] / (acquisition + compute + maintenance + "
                    "multiplicity), in log-wealth per day per declared cost unit"),
        "min_n": lc.MIN_N,
        "blocks": len(blocks), "features": len(by_name),
        "ledger_rows": len(rows), "ledger_states": ledger_states[:40],
        "state_scale": round(scale, 6), "state_scale_why": scale_why,
        "counts": counts,
        "gaps": gaps,
        "cost_table": {"compute_units_per_s": COMPUTE_UNITS_PER_S,
                       "acquisition_external": ACQUISITION_EXTERNAL,
                       "maintenance_external": MAINTENANCE_EXTERNAL,
                       "multiplicity_per_variant": MULTIPLICITY_PER_VARIANT,
                       "min_cost_units": MIN_COST_UNITS,
                       "why": ("declared units, not seconds, for everything the desk cannot "
                               "honestly measure in seconds; compute IS measured and converted "
                               "onto the same scale so the ratio is comparable across features")},
        "per_feature": features,
        "rule": ("a feature earns compute or loses it: DEAD (ROI <= 0 with n >= MIN_N) and "
                 "REDUNDANT (spanned by another feature) withdraw effort; below MIN_N the "
                 "verdict is UNMEASURED and nothing dies on it"),
    }
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    # ARGV IS EXPLICIT because the daily cycle calls `mod.main()` with no arguments inside a
    # process that has its own command line; parsing sys.argv there would make the organ fail on
    # the caller's flags.
    argparse.ArgumentParser(
        description="FeatureROI: the warehouse's feedback arm").parse_args(argv or [])
    d = run()
    c = d["counts"]
    print(f"FEATURE ROI  {d['features']} feature(s) over {d['blocks']} block(s), "
          f"{d['ledger_rows']} conditioning-ledger row(s)")
    print(f"  useful={c.get('useful', 0)} state_only={c.get('state_only', 0)} "
          f"execution_only={c.get('execution_only', 0)} redundant={c.get('redundant', 0)} "
          f"decaying={c.get('decaying', 0)} dead={c.get('dead', 0)} "
          f"revived={c.get('revived', 0)} unmeasured={c.get('unmeasured', 0)}")
    for name, f in sorted(d["per_feature"].items(),
                          key=lambda kv: -(kv[1]["roi"] or 0.0))[:14]:
        roi = "UNMEASURED" if f["roi"] is None else f"{f['roi']:+.8f}"
        spend = "yes" if f["may_spend_compute"] else "NO"
        print(f"  {name[:28]:28s} {f['status']:14s} roi={roi:>14s} n={f['n']:4d} "
              f"cost={f['cost_units']['total']:.1f}u compute={spend}")
    for g, why in d["gaps"].items():
        print(f"  GAP {g}: {why}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
