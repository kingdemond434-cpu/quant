"""VALIDATOR GENOMES COMPETE ON THE REAL GAUNTLET'S VERDICTS (Tier S layer 33).

Until this module the validator genomes the Red Queen evolved (`libs/tiers/meta_benchmark.
ValidatorConfig`) were adopted on the score the REFERENCE validator gave them -- a model of a
validator, graded against another run of the same model. The desk's real certifier, the ten-gate
gauntlet (`desks/mt5/scripts/external_gauntlet.run_gauntlet`, reached read-only through
`adversary.real_gate`), never took part. A genome could be "adopted" for beating the model on
cases where the real gates already decided better, or decided differently, and nobody would know.

THE ARENA. The sealed trap suite (`tier_s.PROD_SUITE`) is judged BLIND by the real gauntlet,
hourly, and each verdict is kept per (kind, seed) for as long as the gauntlet's code is unchanged
(`tier_s.production_immune`). Every genome is then scored on EXACTLY those cases, against truth,
with the real verdict beside its own:

    joint        the desk's decision if the genome were laid over the real gates:
                 real passed AND genome accepts. immune / power / balanced of that decision --
                 the only thing adopting a validator could ever do to a certificate.
    vs_gauntlet  where the genome and the real gauntlet DISAGREE, who was right:
                 genome_right (genome correct, gauntlet wrong), gauntlet_right (the reverse),
                 net = genome_right - gauntlet_right, and McNemar's z on the pair.

THE ADOPTION RULE (`judge`), and it is judged by the real verdict, never by the model:

    UNMEASURED  fewer than `min_traps` traps or `min_genuine` genuine controls carry a real
                verdict on the gauntlet's current code: nothing is adopted on a guess
    ADOPT       the challenger never makes the joint decision worse than the incumbent's
                (joint balanced >= incumbent's), AND either raises it by `margin`, or beats the
                incumbent against the real gauntlet (net advantage over the incumbent of at
                least `margin` of the judged cases)
    REJECT      anything else

ADOPTED GENOMES STAY RESEARCH-SIDE. An adoption is a row in the tier_s research state that the
research organs (immune, Red Queen, test invention) read as their incumbent validator. Nothing
here writes a gauntlet, a gate, a promoter, a certificate or any sealed file: `sealed_fingerprint`
hashes the never-edit files so the caller can prove, per adoption, that they were not touched.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libs.tiers import traps
from libs.tiers.traps import Case

ROOT = Path(__file__).resolve().parents[2]

#: the files an adoption must never change (the task's never-edit list; read-only callers only)
SEALED_FILES: tuple[str, ...] = (
    "desks/mt5/scripts/external_gauntlet.py", "desks/mt5/research/universal_gate.py",
    "desks/mt5/research/promoter.py", "desks/mt5/mt5desk/gateway.py", "libs/portfolio/rails.py",
)

MIN_TRAPS = 200
MIN_GENUINE = 20
MARGIN = 0.01

Validator = Callable[[Case], tuple[bool, list[str]]]


@dataclass(frozen=True)
class Judged:
    """One sealed case with the real gauntlet's blind verdict on it."""
    kind: str
    seed: int
    genuine: bool
    real_passed: bool
    case: Case


def real_decisions(verdicts: Mapping[str, Mapping[str, Any]], code: str
                   ) -> dict[tuple[str, int], bool]:
    """(kind, seed) -> the real gauntlet's pass, for verdicts on its CURRENT code only; an
    unmeasured verdict (the certifier could not judge the cell) is not a decision."""
    out: dict[tuple[str, int], bool] = {}
    for key, v in verdicts.items():
        if not isinstance(v, Mapping) or v.get("code") != code or v.get("unmeasured"):
            continue
        try:
            kind, seed = str(key).split("|")
            out[(kind, int(seed))] = bool(v.get("passed"))
        except ValueError:
            continue
    return out


def judged_cases(decisions: Mapping[tuple[str, int], bool], n: int,
                 generate: Callable[[str, int, int], tuple[Case, Any]] = traps.generate,
                 limit: int | None = None) -> list[Judged]:
    """The sealed cases the real gauntlet judged, regenerated deterministically (same kind, seed
    and length as the docket it saw). `limit` keeps every trap the gauntlet let through and every
    genuine control, then fills with the rest in a stable order."""
    keys = sorted(decisions)
    if limit is not None and len(keys) > limit:
        first = [k for k in keys if (decisions[k] and k[0] in traps.TRAP_KINDS)
                 or k[0] in traps.TRUE_KINDS]
        chosen = set(first)
        rest = sorted((k for k in keys if k not in chosen),
                      key=lambda k: hashlib.sha256(f"{k[0]}|{k[1]}".encode()).hexdigest())
        keys = sorted((first + rest)[:limit])
    out = []
    for kind, seed in keys:
        case, _truth = generate(kind, seed, n)
        out.append(Judged(kind, seed, kind in traps.TRUE_KINDS, decisions[(kind, seed)], case))
    return out


def _rates(tp: int, fn: int, tn: int, fp: int) -> dict[str, float | None]:
    immune = tn / (tn + fp) if tn + fp else None
    power = tp / (tp + fn) if tp + fn else None
    bal = (immune + power) / 2 if immune is not None and power is not None else None
    return {"immune": immune, "power": power, "balanced": bal}


def arena_score(validator: Validator, cases: Sequence[Judged]) -> dict[str, Any]:
    """A genome scored on the real gauntlet's judged cases: its joint decision with the real
    gates, its standalone decision, and its disagreement record against the real gauntlet."""
    j = {"tp": 0, "fn": 0, "tn": 0, "fp": 0}
    g = {"tp": 0, "fn": 0, "tn": 0, "fp": 0}
    r = {"tp": 0, "fn": 0, "tn": 0, "fp": 0}
    genome_right = gauntlet_right = 0
    caught_beyond_real = lost_real_power = 0
    for c in cases:
        ok = bool(validator(c.case)[0])
        joint = c.real_passed and ok
        for tally, accepted in ((j, joint), (g, ok), (r, c.real_passed)):
            if c.genuine:
                tally["tp" if accepted else "fn"] += 1
            else:
                tally["fp" if accepted else "tn"] += 1
        if ok != c.real_passed:
            if ok == c.genuine:
                genome_right += 1
            else:
                gauntlet_right += 1
        if c.real_passed and not ok:
            if c.genuine:
                lost_real_power += 1
            else:
                caught_beyond_real += 1
    disagree = genome_right + gauntlet_right
    z = ((genome_right - gauntlet_right) / math.sqrt(disagree)) if disagree else 0.0
    return {"n": len(cases), "n_traps": sum(1 for c in cases if not c.genuine),
            "n_genuine": sum(1 for c in cases if c.genuine),
            "joint": _rates(j["tp"], j["fn"], j["tn"], j["fp"]),
            "genome": _rates(g["tp"], g["fn"], g["tn"], g["fp"]),
            "real_gauntlet": _rates(r["tp"], r["fn"], r["tn"], r["fp"]),
            "vs_gauntlet": {"genome_right": genome_right, "gauntlet_right": gauntlet_right,
                            "net": genome_right - gauntlet_right,
                            "mcnemar_z": round(z, 4)},
            "traps_caught_beyond_real": caught_beyond_real,
            "real_power_lost": lost_real_power}


def judge(challenger: Mapping[str, Any], incumbent: Mapping[str, Any], *,
          margin: float = MARGIN, min_traps: int = MIN_TRAPS,
          min_genuine: int = MIN_GENUINE) -> dict[str, Any]:
    """ADOPT / REJECT / UNMEASURED for a challenger genome against the incumbent genome, both
    scored by `arena_score` on the same real-verdict cases."""
    n_tr, n_gen = int(challenger.get("n_traps") or 0), int(challenger.get("n_genuine") or 0)
    if n_tr < min_traps or n_gen < min_genuine:
        return {"verdict": "UNMEASURED",
                "why": f"{n_tr} trap(s) and {n_gen} genuine control(s) carry a real verdict on "
                       f"the gauntlet's current code (need {min_traps} and {min_genuine})"}
    cj = (challenger.get("joint") or {}).get("balanced")
    ij = (incumbent.get("joint") or {}).get("balanced")
    if cj is None or ij is None:
        return {"verdict": "UNMEASURED", "why": "no joint score"}
    n = max(1, int(challenger.get("n") or 0))
    net_adv = (int((challenger.get("vs_gauntlet") or {}).get("net") or 0)
               - int((incumbent.get("vs_gauntlet") or {}).get("net") or 0))
    out = {"joint_challenger": cj, "joint_incumbent": ij,
           "net_vs_gauntlet_advantage": net_adv, "judged_cases": n}
    if float(cj) < float(ij) - 1e-12:
        return {**out, "verdict": "REJECT",
                "why": "laid over the real gates it would decide worse than the incumbent"}
    if float(cj) > float(ij) + margin:
        return {**out, "verdict": "ADOPT",
                "why": "raises the joint decision with the real gates by more than the margin"}
    if net_adv >= margin * n:
        return {**out, "verdict": "ADOPT",
                "why": "where it disagrees with the real gauntlet it is right more often than "
                       "the incumbent is, by more than the margin"}
    return {**out, "verdict": "REJECT",
            "why": "no better than the incumbent on the real gauntlet's verdicts"}


def sealed_fingerprint(root: Path = ROOT, files: Iterable[str] = SEALED_FILES
                       ) -> dict[str, str | None]:
    """sha256 of each never-edit file (None when absent), taken before and after an adoption."""
    out: dict[str, str | None] = {}
    for rel in files:
        p = root / rel
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return out
