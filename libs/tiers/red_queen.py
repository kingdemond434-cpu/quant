"""THE RED QUEEN (Tier S layers 9 and 39): attackers and defenders that co-evolve.

A fixed ten-gate checklist is a target that stands still, and a search that runs long enough
learns where it is blind. So the desk keeps two populations and lets them race:

  ATTACKERS are trap generators. An attack genome is (trap kind, subtlety, researcher) -- how
  hard the trap is to see (leakage on fewer bars, trials under-reported, a later regime break, a
  noisier factor clone, fewer stale quotes, a smaller survivorship cull) and WHOSE output it is
  shaped like: the researcher gene charges the trap the trials that researcher's pipeline really
  spends per certificate (its gate verdicts per pass, from the market), so a blind spot is found
  against the protection each researcher's candidates actually get. An attacker's fitness is the
  share of its traps the CURRENT defender accepts. Attackers that learn a blind spot multiply,
  and every success is ATTRIBUTED to the researcher it imitated (`by_researcher`).

  DEFENDERS are validator configurations (the genome of `libs.tiers.meta_benchmark.
  ValidatorConfig`: probe counts, thresholds, fold rules). A defender's fitness is balanced
  accuracy on the sealed suite PLUS the attackers' current elite traps -- it must catch the new
  attacks WITHOUT losing power on genuine planted signals.

THREE ATTACK KINDS THE SEALED SUITE DOES NOT PLANT (they live here, so the sealed suite's hash
and every score history stay comparable):

  hidden_factor     the edge is a factor the desk already holds, and the DECLARED factor list
                    carries it less and less as subtlety rises -- only the held universe does
  overlap           the desk's own live momentum sleeve re-found with a longer window: real
                    edge, no new information, declared overlap shrinking with subtlety
  false_causality   a driver whose level tracks a confounder that also moved the target; the
                    confounder stops acting on the target part-way, later as subtlety rises

One `generation()` evolves each side once against the other's best. The report publishes the
attack success rate over time (the arms race, measured), the blind spots attackers found, the
attribution per researcher, and the best defender -- which is a CHALLENGER for the architecture
evolver, never adopted directly.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import fields, replace
from typing import Any

import numpy as np

from libs.tiers import meta_benchmark as mb
from libs.tiers import traps
from libs.tiers.traps import Case, Truth

Attack = dict[str, Any]

NEW_KINDS: tuple[str, ...] = ("hidden_factor", "overlap", "false_causality")
ATTACK_KINDS: tuple[str, ...] = traps.TRAP_KINDS + NEW_KINDS
#: kinds whose trap lives outside the signal and the returns the production certifier is shown
INEXPRESSIBLE_TO_GAUNTLET: frozenset[str] = traps.INEXPRESSIBLE_TO_GAUNTLET | frozenset(
    {"hidden_factor", "overlap"})
UNATTRIBUTED = "unattributed"
#: a researcher's trial charge is clamped here: past it the deflation is saturated anyway
MAX_TRIALS = 400


def _cid(kind: str, seed: int, n: int, s: float) -> str:
    return "c" + hashlib.sha256(f"{kind}|{seed}|{n}|{s}".encode()).hexdigest()[:16]


def _hidden_factor(seed: int, n: int, s: float) -> tuple[Case, Truth]:
    """The duplicate_factor path, with the factor moved out of the declared list and into the
    held universe as subtlety rises: at 0 the declared factor IS the edge, at 1 it is noise."""
    case, _t = traps.generate("duplicate_factor", seed, n, 0.0)
    rng = np.random.default_rng(seed + 7_000_003)
    f = case.factor_returns
    decoy = rng.normal(0, float(np.std(f)) or 0.01, size=f.shape)
    univ = case.universe_returns.copy()
    univ[:, 0] = f[1: univ.shape[0] + 1]
    c = replace(case, case_id=_cid("hidden_factor", seed, n, s),
                factor_returns=(1.0 - s) * f + s * decoy, universe_returns=univ,
                universe_alive=np.ones(univ.shape[1], dtype=bool))
    return c, Truth(c.case_id, "hidden_factor", False)


def _overlap(seed: int, n: int, s: float) -> tuple[Case, Truth]:
    """A genuine AR edge the desk already trades as a one-bar momentum sleeve (declared as the
    held factor), re-found as a (1 + 3s)-bar momentum: the overlap is the trap."""
    case, _t = traps.generate("true_signal", seed, n, 0.0)
    held = traps._ar_signal_fn(1)
    pos = np.array([held(case.prices, t) for t in range(len(case.prices))], dtype=float)
    rng = np.random.default_rng(seed + 9_000_011)
    factor = pos * np.abs(rng.normal(0.01, 0.002, size=pos.shape))
    c = replace(case, case_id=_cid("overlap", seed, n, s),
                signal_fn=traps._ar_signal_fn(1 + round(3 * s)), factor_returns=factor)
    return c, Truth(c.case_id, "overlap", False)


def _false_causality(seed: int, n: int, s: float) -> tuple[Case, Truth]:
    """Driver level ~ confounder; target drift ~ confounder only until `cut`. The rule 'long the
    target while the driver is up' is a correlation through a common cause, not a mechanism."""
    rng = np.random.default_rng(seed)
    sigma = 0.01
    conf = np.sign(np.cumsum(rng.normal(0, 1, size=n + 1)) + 1e-12)
    driver = conf + rng.normal(0, 0.6, size=n + 1)
    cut = int(n * (0.5 + 0.4 * s))
    r = rng.normal(0, sigma, size=n)
    r[:cut] += 0.15 * sigma * conf[:cut]
    prices = traps._mk_prices(rng, r)
    lows, highs = traps._lohi(rng, prices)

    def signal_fn(px: Any, t: int, _d: Any = driver) -> float:
        return float(np.sign(_d[t])) if t < len(_d) else 0.0

    c = Case(case_id=_cid("false_causality", seed, n, s), prices=prices, signal_fn=signal_fn,
             fills=prices.copy(), lows=lows, highs=highs, cost_per_trade=0.0002,
             n_variants_tried=1, factor_returns=rng.normal(0, sigma, size=n + 1),
             universe_returns=rng.normal(0, sigma, size=(n, 20)),
             universe_alive=np.ones(20, dtype=bool))
    return c, Truth(c.case_id, "false_causality", False)


_NEW = {"hidden_factor": _hidden_factor, "overlap": _overlap,
        "false_causality": _false_causality}


def generate(kind: str, seed: int, n: int = 1500, subtlety: float = 0.0) -> tuple[Case, Truth]:
    """traps.generate, plus the Red Queen's own kinds."""
    s_ = min(1.0, max(0.0, float(subtlety)))
    if kind in _NEW:
        return _NEW[kind](int(seed), int(n), s_)
    return traps.generate(kind, seed, n, s_)


def trials_of(profile: Mapping[str, Any] | None) -> int | None:
    """Trials a researcher's pipeline spends per certificate: its gate verdicts per pass."""
    if not profile:
        return None
    judged = int(profile.get("judged") or 0)
    if judged <= 0:
        return None
    return int(min(MAX_TRIALS, max(1, round(judged / max(1, int(profile.get("passed") or 0))))))


def _pick(rng: np.random.Generator, researchers: Sequence[str] | None) -> str:
    rs = list(researchers or [])
    return rs[int(rng.integers(len(rs)))] if rs else UNATTRIBUTED


def random_attack(rng: np.random.Generator, researchers: Sequence[str] | None = None) -> Attack:
    return {"kind": ATTACK_KINDS[int(rng.integers(len(ATTACK_KINDS)))],
            "subtlety": round(float(rng.uniform(0.0, 1.0)), 3),
            "researcher": _pick(rng, researchers)}


def mutate_attack(a: Attack, rng: np.random.Generator,
                  researchers: Sequence[str] | None = None) -> Attack:
    out = dict(a)
    if rng.random() < 0.2:
        out["kind"] = ATTACK_KINDS[int(rng.integers(len(ATTACK_KINDS)))]
    if researchers and rng.random() < 0.2:
        out["researcher"] = _pick(rng, researchers)
    out.setdefault("researcher", UNATTRIBUTED)
    out["subtlety"] = round(min(1.0, max(0.0, float(out["subtlety"])
                                         + float(rng.normal(0, 0.15)))), 3)
    return out


def attack_cases(a: Attack, seeds: Sequence[int], n: int = 1200,
                 profiles: Mapping[str, Mapping[str, Any]] | None = None
                 ) -> list[tuple[Case, Truth]]:
    trials = trials_of((profiles or {}).get(str(a.get("researcher") or "")))
    out = []
    for s in seeds:
        case, truth = generate(str(a["kind"]), int(s), n, float(a["subtlety"]))
        if trials is not None and a["kind"] != "selection":
            # the selection trap's under-reported trial count IS the attack; everywhere else
            # the trap is charged what its researcher's pipeline really charges
            case = replace(case, n_variants_tried=trials)
        out.append((case, truth))
    return out


def attack_fitness(a: Attack, validator: mb.Validator, seeds: Sequence[int],
                   profiles: Mapping[str, Mapping[str, Any]] | None = None) -> float:
    cases = attack_cases(a, seeds, profiles=profiles)
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


def attribute(scored: Sequence[tuple[Attack, float]],
              profiles: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Attack success per researcher: how many attacks imitated it, their mean success, and the
    kinds that got through. A researcher with a high share is one whose certificates the
    validator protects least, at the trial charge its own pipeline pays."""
    rows: dict[str, dict[str, Any]] = {}
    for a, fit in scored:
        r = str(a.get("researcher") or UNATTRIBUTED)
        d = rows.setdefault(r, {"attacks": 0, "success_sum": 0.0, "kinds_through": set(),
                                "trials": trials_of((profiles or {}).get(r))})
        d["attacks"] += 1
        d["success_sum"] += float(fit)
        if fit > 0:
            d["kinds_through"].add(str(a["kind"]))
    return {r: {"attacks": d["attacks"], "success": round(d["success_sum"] / d["attacks"], 4),
                "kinds_through": sorted(d["kinds_through"]), "trials_charged": d["trials"]}
            for r, d in sorted(rows.items())}


def generation(attackers: Sequence[Attack], defender: mb.ValidatorConfig,
               sealed: list[tuple[Case, Truth]], *, seed: int, pop: int = 10,
               defenders: int = 5, attack_seeds: int = 3,
               researchers: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """`researchers`: name -> {"judged", "passed"} (the market's table). Absent -> every attack
    is UNATTRIBUTED and charged its trap's own trials, as before."""
    rng = np.random.default_rng(seed)
    names = sorted(researchers or {})
    pool = [dict(a) for a in attackers] or [random_attack(rng, names) for _ in range(pop)]
    # every kind the sealed suite does not plant is attacked every generation, so its blind
    # spot is measured hourly rather than waiting for a mutation to wander onto it
    have = {str(a.get("kind")) for a in pool}
    pool += [{"kind": k, "subtlety": round(float(rng.uniform(0.0, 1.0)), 3),
              "researcher": _pick(rng, names)} for k in NEW_KINDS if k not in have]
    known = set(names)
    for a in pool:
        if known and a.get("researcher") not in known:
            a["researcher"] = _pick(rng, names)
        a.setdefault("researcher", UNATTRIBUTED)
    seeds = [seed * 7 + i for i in range(attack_seeds)]
    incumbent_v = mb.reference_validator(defender)
    scored = [(a, attack_fitness(a, incumbent_v, seeds, researchers)) for a in pool]
    scored.sort(key=lambda af: (-af[1], str(af[0])))
    success = float(np.mean([f for _a, f in scored])) if scored else 0.0
    elite = [a for a, _f in scored[: max(2, pop // 3)]]
    nxt = list(elite)
    while len(nxt) < pop:
        parent = elite[int(rng.integers(len(elite)))]
        nxt.append(mutate_attack(parent, rng, names) if rng.random() < 0.8
                   else random_attack(rng, names))
    elite_cases: list[tuple[Case, Truth]] = []
    for a in elite:
        elite_cases.extend(attack_cases(a, seeds[:1], profiles=researchers))
    inc_fit = defender_fitness(defender, sealed, elite_cases)
    best_cfg, best_fit = defender, inc_fit
    for _ in range(defenders):
        cand = mutate_defender(defender, rng)
        f = defender_fitness(cand, sealed, elite_cases)
        if f["balanced"] > best_fit["balanced"] + 1e-9:
            best_cfg, best_fit = cand, f
    blind: dict[str, float] = {}
    by_kind: dict[str, list[float]] = {}
    for a, fit in scored:
        k = str(a["kind"])
        by_kind.setdefault(k, []).append(fit)
        if fit > 0:
            blind[k] = max(blind.get(k, 0.0), fit)
    return {"attack_success": round(success, 4), "blind_spots": blind,
            "next_attackers": nxt,
            "elite_attacks": [{"attack": a, "success": f} for a, f in scored[:5]],
            "by_researcher": attribute(scored, researchers),
            "new_kinds": {k: round(float(np.mean(by_kind[k])), 4) if k in by_kind else None
                          for k in NEW_KINDS},
            "incumbent_defender": inc_fit, "best_defender": best_fit,
            "challenger": best_cfg.genome() if best_cfg is not defender else None}


#: the validator that accepts everything: a screen rule must separate a kind from genuine edges
#: ON ITS OWN, because in the pre-judge screen it stands in front of no other check
NULL_VALIDATOR = mb.ValidatorConfig(lookahead_on=False, fills_on=False, dsr_on=False,
                                    wf_on=False, factor_on=False, survivorship_on=False,
                                    stale_on=False)


def defender_rule(kind: str, incumbent: mb.ValidatorConfig,
                  sealed: list[tuple[Case, Truth]], *, seed: int, subtlety: float = 0.5,
                  per: int = 4, n: int = 1200, features: Sequence[str] | None = None
                  ) -> dict[str, Any]:
    """THE RED QUEEN'S FINDING GIVEN A CONSEQUENCE (layer 9). `kind` fooled the certifier; find
    the defender rule that stops it:

      1. PROPOSE a check over the screenable features on `per` cases of the kind (at the
         subtlety that fooled) beside the genuine positive controls, against a validator that
         accepts everything -- so the rule separates the kind from real edges by itself;
      2. CONFIRM it on fresh seeds of both (`test_invention.invent_from`);
      3. the CHALLENGER (the incumbent validator + the rule) must SURVIVE THE SEALED TRAP SUITE:
         no genuine edge the incumbent accepts is lost and no trap it rejects gets through.

    Only a rule that clears all three is returned ADOPTABLE; the caller writes it into the
    pre-judge screen. Every other outcome is returned with its reason."""
    from libs.tiers import prejudge_screen, test_invention
    feats = tuple(features or prejudge_screen.SCREEN_FEATURES)

    def cases(base: int) -> list[tuple[Case, Truth]]:
        out = [generate(kind, base + i, n, subtlety) for i in range(per)]
        out += [traps.generate(k, base + 97 + i, n) for k in traps.TRUE_KINDS
                for i in range(max(1, per // 2))]
        return out

    inv = test_invention.invent_from(NULL_VALIDATOR, cases(seed * 1009 + 17),
                                     cases(seed * 1009 + 50_021), top=1, features=feats)
    gates = inv.get("candidate_gates") or []
    base = {"kind": kind, "subtlety": round(float(subtlety), 3), "n_tried": inv.get("n_tried"),
            "n_promising": inv.get("n_promising")}
    if not gates:
        return {**base, "status": "NO_CONFIRMED_CHECK",
                "why": "no screenable check separated the kind from genuine edges on both "
                       "the proposal and the confirmation seeds"}
    g = gates[0]
    surv = prejudge_screen.sealed_survival(incumbent, g["check"], sealed)
    out = {**base, "check": list(g["check"]),
           "proposal": {"d_immune": g["d_immune"], "d_power": g["d_power"]},
           "confirmation": {"d_immune": g["confirm_d_immune"],
                            "d_power": g["confirm_d_power"]},
           "sealed": surv}
    if not surv["survives"]:
        return {**out, "status": "FAILED_SEALED_SUITE",
                "why": "the challenger lost power or immunity on the sealed trap suite"}
    return {**out, "status": "ADOPTABLE"}


def from_state(state: Mapping[str, Any]) -> list[Attack]:
    return [dict(a) for a in state.get("attackers") or [] if isinstance(a, Mapping)
            and a.get("kind") in ATTACK_KINDS]
