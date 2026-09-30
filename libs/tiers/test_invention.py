"""AUTOMATIC INVENTION OF NEW VALIDATION TESTS (Tier S layer 21).

The gauntlet must not stay static, and a new gate must not be adopted because it sounds strict.
This proposes checks from a small grammar over the per-case features the meta-benchmark computes
(`libs/tiers/meta_benchmark.features`):

    <feature> <op> <threshold>      e.g.  decay > 0.08,  zero_share > 0.12,  turnover > 0.9

Thresholds come from the feature's own quantiles on the PROPOSAL suite. Every candidate is added
to the incumbent validator and scored; the ones that raise the immune score without lowering power
are then re-scored on a CONFIRMATION suite with different seeds (a check that only works on the
cases it was fitted to is overfit to the benchmark, the very failure it exists to catch). A check
that survives both is a CANDIDATE GATE.

MACHINE RATIFICATION (principal's standing order: no approvals needed). A candidate gate
proposed on one suite and confirmed on another is RATIFIED BY THE MACHINE when, added to the
incumbent validator, it also survives a THIRD, sealed trap suite neither half saw (it rejects at
least as many traps and accepts every genuine planted edge the incumbent accepts:
`libs/tiers/prejudge_screen.sealed_survival`) and its feature is one a real candidate's backtest
yields (`prejudge_screen.SCREEN_FEATURES`). `ratification_row` is the evidence record appended to
desks/mt5/data/tier_s/test_ratifications.jsonl, and the ratified check is adopted into the
pre-judge screen, where it runs on every candidate `run_external_backtest` tests before the
docket reaches the judge. What machine ratification does NOT do is edit the sealed judge: adding
a gate to `external_gauntlet.py` itself stays the principal's constitutional act
(`libs/tiers/truth_kernel.constitution_status`, docs/research/tier_s_ratifications.jsonl).
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping, Sequence
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
                top: int = 3, features: Sequence[str] = FEATURES) -> dict[str, Any]:
    """The same proposal/confirmation discipline over explicit case lists -- e.g. the cases that
    actually FOOLED the production certifier, beside the genuine controls it must keep."""
    if not prop_cases or not conf_cases:
        return {"baseline": None, "n_tried": 0, "n_promising": 0, "candidate_gates": [],
                "why": "no cases to learn from"}
    base_p = mb.score(mb.reference_validator(incumbent), cases=prop_cases)
    base_c = mb.score(mb.reference_validator(incumbent), cases=conf_cases)
    tried: list[dict[str, Any]] = []
    for check in propose(prop_cases, features):
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


#: who ratifies, and on what authority
RATIFIED_BY = "machine:tier_s.test_invention"
RATIFICATION_BASIS = ("principal standing order: no approvals needed -- a test proposed on one "
                      "suite, confirmed on another and surviving the sealed trap suite is "
                      "ratified automatically into the research-side pre-judge screen")


def ratifiable(gate: Mapping[str, Any], screen_features: Sequence[str]) -> str | None:
    """None when the gate may be ratified, else why not."""
    if gate.get("status") != "CANDIDATE_GATE":
        return f"status {gate.get('status')!r} is not CANDIDATE_GATE"
    chk = gate.get("check")
    if not isinstance(chk, (list, tuple)) or len(chk) != 3:
        return "malformed check"
    if str(chk[0]) not in screen_features:
        return (f"feature {chk[0]!r} is not one a candidate's backtest yields before judging "
                "(certificate fields exist only after the judge ran)")
    proposed = gate.get("d_immune", (gate.get("proposal") or {}).get("d_immune"))
    confirmed = gate.get("confirm_d_immune", (gate.get("confirmation") or {}).get("d_immune"))
    if not (isinstance(proposed, (int, float)) and proposed > 0
            and isinstance(confirmed, (int, float)) and confirmed > 0):
        return "not both proposed and confirmed with a positive immune gain"
    return None


def ratification_row(gate: Mapping[str, Any], sealed: Mapping[str, Any], *, at: str,
                     seal: str, rule: str) -> dict[str, Any]:
    """The evidence record: the check, both suites' deltas, the sealed-suite survival and the
    rule id it runs under in the pre-judge screen."""
    return {"at": at, "kind": "invented_test", "check": list(gate["check"]),
            "by": RATIFIED_BY, "basis": RATIFICATION_BASIS,
            "source": gate.get("source") or "synthetic_suites",
            "evidence": {"proposal": gate.get("proposal") or {
                             "d_immune": gate.get("d_immune"), "d_power": gate.get("d_power")},
                         "confirmation": gate.get("confirmation") or {
                             "d_immune": gate.get("confirm_d_immune"),
                             "d_power": gate.get("confirm_d_power")},
                         "confirmations": gate.get("confirmations"),
                         "first_seen": gate.get("first_seen"),
                         "sealed_suite": {**dict(sealed), "seal": seal}},
            "runs_in": "libs/tiers/prejudge_screen (run_external_backtest -> merge_hypotheses)",
            "rule_id": rule}


# ------------------------------------------------------------------------------------------------
# THE LABELLED REAL SUITE: the desk's own certificates, labelled by what their forward clocks did
# ------------------------------------------------------------------------------------------------

#: a forward clock with fewer trades than this labels nothing
MIN_FORWARD_N = 10
#: each half (proposal, confirmation) needs this many of each label to judge a check on it
MIN_PER_LABEL = 3


def certificate_features(row: Mapping[str, Any]) -> dict[str, float]:
    """Every numeric field a certificate's gates recorded, as `<gate>.<field>`, plus `days`."""
    out: dict[str, float] = {}
    for gate, st in (row.get("gates") or {}).items():
        if not isinstance(st, Mapping):
            continue
        for k, v in st.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if math.isfinite(float(v)):
                out[f"{gate}.{k}"] = float(v)
    if isinstance(row.get("days"), (int, float)):
        out["days"] = float(row["days"])
    return out


def labelled_suite(certificates: Mapping[str, Mapping[str, Any]],
                   forward: Mapping[str, Mapping[str, Any]],
                   forward_key: Callable[[Mapping[str, Any]], str],
                   min_n: int = MIN_FORWARD_N) -> dict[str, Any]:
    """certificate x forward outcome. label True = the forward clock's mean R is positive on at
    least `min_n` trades; a certificate without such a clock is UNLABELLED (never a pass)."""
    rows: list[dict[str, Any]] = []
    unlabelled = 0
    for key, cert in certificates.items():
        if not isinstance(cert, Mapping):
            continue
        fk = forward_key(cert)
        fw = forward.get(fk) or {}
        n = int(fw.get("n") or 0)
        er = fw.get("exp_r")
        if n < min_n or not isinstance(er, (int, float)):
            unlabelled += 1
            continue
        rows.append({"key": str(key), "forward_key": fk, "n": n, "exp_r": float(er),
                     "label": float(er) > 0.0, "features": certificate_features(cert)})
    held = sum(r["label"] for r in rows)
    return {"rows": rows, "n_labelled": len(rows), "n_unlabelled": unlabelled,
            "forward_holds": held, "forward_fails": len(rows) - held,
            "precision": round(held / len(rows), 4) if rows else None}


def _half(fk: str) -> int:
    return int(hashlib.sha256(fk.encode()).hexdigest(), 16) % 2


def _score_real(rows: Sequence[Mapping[str, Any]], check: tuple[str, str, float]
                ) -> dict[str, Any]:
    f, op, thr = check
    fails = [r for r in rows if not r["label"]]
    holds = [r for r in rows if r["label"]]

    def rejects(r: Mapping[str, Any]) -> bool:
        v = r["features"].get(f)
        return v is not None and ((op == ">" and v > thr) or (op == "<" and v < thr))

    caught = sum(1 for r in fails if rejects(r))
    lost = sum(1 for r in holds if rejects(r))
    return {"caught": caught, "of_fails": len(fails), "lost": lost, "of_holds": len(holds),
            "d_immune": round(caught / len(fails), 4) if fails else 0.0,
            "d_power": round(-lost / len(holds), 4) if holds else 0.0}


def invent_real(suite: Mapping[str, Any], *, max_power_loss: float = 0.0, top: int = 3
                ) -> dict[str, Any]:
    """The proposal/confirmation discipline on REAL outcomes. The suite is split by forward
    clock (never by certificate: certificates sharing a clock share a label, and splitting them
    would leak the label across halves), checks are proposed from feature quantiles on the
    proposal half only, and a check survives only if on BOTH halves it rejects certificates whose
    forward clock failed while costing no more than `max_power_loss` of the ones that held."""
    rows = list(suite.get("rows") or [])
    prop = [r for r in rows if _half(r["forward_key"]) == 0]
    conf = [r for r in rows if _half(r["forward_key"]) == 1]
    need = {"proposal": (sum(r["label"] for r in prop), sum(not r["label"] for r in prop)),
            "confirmation": (sum(r["label"] for r in conf), sum(not r["label"] for r in conf))}
    short = [f"{h}: {a} holds / {b} fails" for h, (a, b) in need.items()
             if a < MIN_PER_LABEL or b < MIN_PER_LABEL]
    if short:
        return {"status": "UNMEASURED", "why": f"fewer than {MIN_PER_LABEL} of a label in "
                + "; ".join(short), "n_tried": 0, "candidate_gates": [], "halves": need}
    table: dict[str, list[float]] = {}
    for r in prop:
        for k, v in r["features"].items():
            table.setdefault(k, []).append(v)
    checks: list[tuple[str, str, float]] = []
    for f, xs in sorted(table.items()):
        arr = np.asarray(xs, dtype=float)
        if arr.size < 2 * MIN_PER_LABEL or float(arr.std()) == 0.0:
            continue
        for q in QUANTILES:
            checks.append((f, ">" if q >= 0.5 else "<", round(float(np.quantile(arr, q)), 6)))
    tried: list[dict[str, Any]] = []
    confirmed: list[dict[str, Any]] = []
    for chk in checks:
        p = _score_real(prop, chk)
        tried.append({"check": list(chk), **p})
        if p["d_immune"] > 0 and p["d_power"] >= -max_power_loss:
            c = _score_real(conf, chk)
            if c["d_immune"] > 0 and c["d_power"] >= -max_power_loss:
                confirmed.append({"check": list(chk), "proposal": p, "confirmation": c,
                                  "status": "CANDIDATE_GATE", "source": "real_certificates"})
    confirmed.sort(key=lambda g: (-(g["proposal"]["d_immune"] + g["confirmation"]["d_immune"]),
                                  str(g["check"])))
    return {"status": "MEASURED", "halves": need, "n_tried": len(tried),
            "n_promising": sum(1 for t in tried if t["d_immune"] > 0
                               and t["d_power"] >= -max_power_loss),
            "candidate_gates": confirmed[:top],
            "adoption": "candidate gates become constitutional only by principal ratification"}


# ------------------------------------------------------------------------------------------------
# THE GATE REDUNDANCY MATRIX: which gates kill the same cases
# ------------------------------------------------------------------------------------------------

def redundancy_matrix(vectors: Sequence[Mapping[str, Any]], *, min_kills: int = 5,
                      subsume_at: float = 0.98) -> dict[str, Any]:
    """vectors: one per real-certifier verdict, {"failed": [gate...], "gates": [...],
    "genuine": bool, "truncated": bool}.

    On the TRAPS: kills per gate, UNIQUE kills (the only gate that failed), P(b fails | a fails)
    and the Jaccard overlap of kill sets. A gate is SUBSUMED by another when it has at least
    `min_kills` kills, none of them unique, and the other fails on >= `subsume_at` of them. On
    the GENUINE controls: false rejections per gate (what the gate costs). Truncated vectors (a
    writer that kept only the first few failures) count as kills but make co-failure a LOWER
    bound, and never count as unique. A report, never a removal: a gate leaves the gauntlet only
    through the ratified constitution."""
    trap_v = [v for v in vectors if not v.get("genuine")]
    gen_v = [v for v in vectors if v.get("genuine")]
    gates = sorted({str(g) for v in vectors for g in (v.get("failed") or [])}
                   | {str(g) for v in vectors for g in (v.get("gates") or [])})
    if not trap_v or not gates:
        return {"status": "UNMEASURED", "why": "no real-certifier verdicts with gate vectors",
                "n_vectors": len(vectors)}
    kills: dict[str, set[int]] = {g: set() for g in gates}
    unique: dict[str, int] = dict.fromkeys(gates, 0)
    for i, v in enumerate(trap_v):
        failed = [str(g) for g in v.get("failed") or []]
        for g in failed:
            kills[g].add(i)
        if len(failed) == 1 and not v.get("truncated"):
            unique[failed[0]] += 1
    cond: dict[str, dict[str, float | None]] = {}
    jac: dict[str, dict[str, float | None]] = {}
    for a in gates:
        cond[a], jac[a] = {}, {}
        for b in gates:
            if a == b:
                continue
            inter = len(kills[a] & kills[b])
            union = len(kills[a] | kills[b])
            cond[a][b] = round(inter / len(kills[a]), 4) if kills[a] else None
            jac[a][b] = round(inter / union, 4) if union else None
    subsumed = []
    for a in gates:
        if len(kills[a]) < min_kills or unique[a]:
            continue
        for b in gates:
            p = cond[a].get(b)
            if b != a and p is not None and p >= subsume_at:
                subsumed.append({"gate": a, "by": b, "p_by_fails_given_gate_fails": p,
                                 "kills": len(kills[a])})
    false_rej: dict[str, int] = dict.fromkeys(gates, 0)
    for v in gen_v:
        for g in v.get("failed") or []:
            false_rej[str(g)] = false_rej.get(str(g), 0) + 1
    return {"status": "MEASURED", "gates": gates, "n_traps": len(trap_v),
            "n_genuine": len(gen_v),
            "n_truncated": sum(1 for v in vectors if v.get("truncated")),
            "kills": {g: len(kills[g]) for g in gates}, "unique_kills": unique,
            "p_cofail": cond, "jaccard": jac, "subsumed": subsumed,
            "no_unique_kill": sorted(g for g in gates if kills[g] and not unique[g]),
            "false_rejects": false_rej,
            "use": "a report: a redundant gate is a candidate for ratified removal, never "
                   "removed by an agent"}
