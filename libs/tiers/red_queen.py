"""THE RED QUEEN (Tier S layers 9 and 39): attackers and defenders that co-evolve.

A fixed ten-gate checklist is a target that stands still, and a search that runs long enough
learns where it is blind. So the desk keeps two populations and lets them race:

  ATTACKERS are trap generators. An attack genome is (trap kind, subtlety) -- how hard the trap
  is to see: leakage on fewer bars, trials under-reported, a later regime break, a noisier factor
  clone, fewer stale quotes, a smaller survivorship cull. An attacker's fitness is the share of its
  traps the CURRENT defender accepts. Attackers that learn a blind spot multiply.

  DEFENDERS are validator configurations (the genome of `libs.tiers.meta_benchmark.
  ValidatorConfig`: probe counts, thresholds, fold rules). A defender's fitness is balanced
  accuracy on the sealed suite PLUS the attackers' current elite traps -- it must catch the new
  attacks WITHOUT losing power on genuine planted signals.

One `generation()` evolves each side once against the other's best. The report publishes the
attack success rate over time (the arms race, measured), the blind spots attackers found, and the
best defender -- which is a CHALLENGER for the architecture evolver, never adopted directly.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields, replace
from typing import Any

import numpy as np

from libs.tiers import meta_benchmark as mb
from libs.tiers import traps
from libs.tiers.traps import Case, Truth

Attack = dict[str, Any]


def random_attack(rng: np.random.Generator) -> Attack:
    return {"kind": traps.TRAP_KINDS[int(rng.integers(len(traps.TRAP_KINDS)))],
            "subtlety": round(float(rng.uniform(0.0, 1.0)), 3)}


def mutate_attack(a: Attack, rng: np.random.Generator) -> Attack:
    out = dict(a)
    if rng.random() < 0.2:
        out["kind"] = traps.TRAP_KINDS[int(rng.integers(len(traps.TRAP_KINDS)))]
    out["subtlety"] = round(min(1.0, max(0.0, float(out["subtlety"])
                                         + float(rng.normal(0, 0.15)))), 3)
    return out


def attack_cases(a: Attack, seeds: Sequence[int], n: int = 1200) -> list[tuple[Case, Truth]]:
    return [traps.generate(str(a["kind"]), int(s), n, float(a["subtlety"])) for s in seeds]


def attack_fitness(a: Attack, validator: mb.Validator, seeds: Sequence[int]) -> float:
    cases = attack_cases(a, seeds)
    return sum(1 for c, _t in cases if validator(c)[0]) / max(1, len(cases))


#: the defender genes: numeric ValidatorConfig fields and the bounds they may move within
DEFENDER_BOUNDS: dict[str, tuple[float, float]] = {
    "lookahead_probes": (10, 200), "dsr_threshold": (0.8, 0.995), "wf_min_positive": (2, 4),
    "factor_corr_max": (0.2, 0.9), "factor_resid_t": (1.0, 3.5), "survivorship_corr": (0.2, 0.9),
    "survivorship_t": (1.0, 3.5), "stale_zero_share": (0.05, 0.5), "cost_stress": (1.0, 3.0),
}
_INT_FIELDS = {f.name for f in fields(mb.ValidatorConfig) if f.type in ("int", int)}


def mutate_defender(cfg: mb.ValidatorConfig, rng: np.random.Generator, rate: float = 0.3
                    ) -> mb.ValidatorConfig:
    changes: dict[str, Any] = {}
    for name, (lo, hi) in DEFENDER_BOUNDS.items():
        if rng.random() >= rate:
            continue
        v = float(getattr(cfg, name)) + float(rng.normal(0, (hi - lo) * 0.15))
        v = min(hi, max(lo, v))
        changes[name] = round(v) if name in _INT_FIELDS else round(v, 4)
    return replace(cfg, **changes) if changes else cfg


def defender_fitness(cfg: mb.ValidatorConfig, sealed: list[tuple[Case, Truth]],
                     attacks: list[tuple[Case, Truth]]) -> dict[str, Any]:
    v = mb.reference_validator(cfg)
    s = mb.score(v, cases=sealed + attacks)
    return {"balanced": s["balanced"] or 0.0, "immune": s["immune_score"],
            "power": s["power"]}


def generation(attackers: Sequence[Attack], defender: mb.ValidatorConfig,
               sealed: list[tuple[Case, Truth]], *, seed: int, pop: int = 10,
               defenders: int = 5, attack_seeds: int = 3) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    pool = list(attackers) or [random_attack(rng) for _ in range(pop)]
    seeds = [seed * 7 + i for i in range(attack_seeds)]
    incumbent_v = mb.reference_validator(defender)
    scored = [(a, attack_fitness(a, incumbent_v, seeds)) for a in pool]
    scored.sort(key=lambda af: (-af[1], str(af[0])))
    success = float(np.mean([f for _a, f in scored])) if scored else 0.0
    elite = [a for a, _f in scored[: max(2, pop // 3)]]
    nxt = list(elite)
    while len(nxt) < pop:
        parent = elite[int(rng.integers(len(elite)))]
        nxt.append(mutate_attack(parent, rng) if rng.random() < 0.8 else random_attack(rng))
    elite_cases: list[tuple[Case, Truth]] = []
    for a in elite:
        elite_cases.extend(attack_cases(a, seeds[:1]))
    inc_fit = defender_fitness(defender, sealed, elite_cases)
    best_cfg, best_fit = defender, inc_fit
    for _ in range(defenders):
        cand = mutate_defender(defender, rng)
        f = defender_fitness(cand, sealed, elite_cases)
        if f["balanced"] > best_fit["balanced"] + 1e-9:
            best_cfg, best_fit = cand, f
    blind: dict[str, float] = {}
    for a, fit in scored:
        if fit > 0:
            k = str(a["kind"])
            blind[k] = max(blind.get(k, 0.0), fit)
    return {"attack_success": round(success, 4), "blind_spots": blind,
            "next_attackers": nxt,
            "elite_attacks": [{"attack": a, "success": f} for a, f in scored[:5]],
            "incumbent_defender": inc_fit, "best_defender": best_fit,
            "challenger": best_cfg.genome() if best_cfg is not defender else None}


def from_state(state: Mapping[str, Any]) -> list[Attack]:
    return [dict(a) for a in state.get("attackers") or [] if isinstance(a, Mapping)
            and a.get("kind") in traps.TRAP_KINDS]
