"""AUTOMATIC INVENTION OF NEW VALIDATION TESTS (Tier S layer 21).

The gauntlet must not stay static, and a new gate must not be adopted because it sounds strict.
This proposes checks from a small grammar over the per-case features the meta-benchmark computes
(`libs/tiers/meta_benchmark.features`):

    <feature> <op> <threshold>      e.g.  decay > 0.08,  zero_share > 0.12,  turnover > 0.9

Thresholds come from the feature's own quantiles on the PROPOSAL suite. Every candidate is added
to the incumbent validator and scored; the ones that raise the immune score without lowering power
are then re-scored on a CONFIRMATION suite with different seeds (a check that only works on the
cases it was fitted to is overfit to the benchmark, the very failure it exists to catch). A check
that survives both is a CANDIDATE GATE. It becomes constitutional only by principal ratification
(`libs/tiers/truth_kernel.constitution_status`) -- agents may propose, never enact.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from libs.tiers import meta_benchmark as mb
from libs.tiers.traps import Case, Truth

FEATURES: tuple[str, ...] = ("decay", "zero_share", "ac1", "turnover", "sr_second_half",
                             "variants", "sr_first_half")
QUANTILES: tuple[float, ...] = (0.1, 0.25, 0.75, 0.9)


def propose(cases: Sequence[tuple[Case, Truth]], features: Sequence[str] = FEATURES
            ) -> list[tuple[str, str, float]]:
    table: dict[str, list[float]] = {f: [] for f in features}
    for case, _t in cases:
        feats = mb.features(case)
        for f in features:
            table[f].append(feats[f])
    out: list[tuple[str, str, float]] = []
    for f, xs in table.items():
        arr = np.asarray(xs, dtype=float)
        if arr.size == 0 or float(arr.std()) == 0.0:
            continue
        for q in QUANTILES:
            thr = float(np.quantile(arr, q))
            out.append((f, ">" if q >= 0.5 else "<", round(thr, 6)))
    return out


def invent(incumbent: mb.ValidatorConfig, proposal: mb.Suite, confirmation: mb.Suite, *,
           max_power_loss: float = 0.0, top: int = 3) -> dict[str, Any]:
    return invent_from(incumbent, list(proposal.cases()), list(confirmation.cases()),
                       max_power_loss=max_power_loss, top=top)


def invent_from(incumbent: mb.ValidatorConfig, prop_cases: list[tuple[Case, Truth]],
                conf_cases: list[tuple[Case, Truth]], *, max_power_loss: float = 0.0,
                top: int = 3) -> dict[str, Any]:
    """The same proposal/confirmation discipline over explicit case lists -- e.g. the cases that
    actually FOOLED the production certifier, beside the genuine controls it must keep."""
    if not prop_cases or not conf_cases:
        return {"baseline": None, "n_tried": 0, "n_promising": 0, "candidate_gates": [],
                "why": "no cases to learn from"}
    base_p = mb.score(mb.reference_validator(incumbent), cases=prop_cases)
    base_c = mb.score(mb.reference_validator(incumbent), cases=conf_cases)
    tried: list[dict[str, Any]] = []
    for check in propose(prop_cases):
        cfg = mb.with_extra(incumbent, check)
        s = mb.score(mb.reference_validator(cfg), cases=prop_cases)
        d_imm = (s["immune_score"] or 0) - (base_p["immune_score"] or 0)
        d_pow = (s["power"] or 0) - (base_p["power"] or 0)
        tried.append({"check": list(check), "d_immune": round(d_imm, 4),
                      "d_power": round(d_pow, 4)})
    promising = [t for t in tried if t["d_immune"] > 0 and t["d_power"] >= -max_power_loss]
    promising.sort(key=lambda t: (-(t["d_immune"] + t["d_power"]), str(t["check"])))
    confirmed: list[dict[str, Any]] = []
    for t in promising[:top * 3]:
        chk = (str(t["check"][0]), str(t["check"][1]), float(t["check"][2]))
        s = mb.score(mb.reference_validator(mb.with_extra(incumbent, chk)), cases=conf_cases)
        d_imm = (s["immune_score"] or 0) - (base_c["immune_score"] or 0)
        d_pow = (s["power"] or 0) - (base_c["power"] or 0)
        if d_imm > 0 and d_pow >= -max_power_loss:
            confirmed.append({**t, "confirm_d_immune": round(d_imm, 4),
                              "confirm_d_power": round(d_pow, 4), "status": "CANDIDATE_GATE"})
        if len(confirmed) >= top:
            break
    return {"baseline": {"proposal": {k: base_p[k] for k in ("immune_score", "power")},
                         "confirmation": {k: base_c[k] for k in ("immune_score", "power")}},
            "n_tried": len(tried), "n_promising": len(promising), "candidate_gates": confirmed,
            "adoption": "candidate gates become constitutional only by principal ratification"}
