"""THE EFFECTIVE-TRIAL LEDGER (LAWS 5k): the trial count follows the FAMILY.

EMA(19,57), EMA(20,58) and EMA(21,59) are three rows in any ledger and ONE search. A deflated
Sharpe that charges them as three independent trials is too harsh on the family; one that
charges the winner of a million-cell sweep as a single trial is the winners' curse with a
certificate. This module prices a set of trials by their SIMILARITY -- across hypotheses,
features, signals, parameters, mechanisms, datasets and model families, whatever descriptors a
row carries -- and reports N_effective beside N_raw, both directions at once:

    * clones collapse: a family of parameter-neighbours is worth its participation ratio, not
      its row count (the count FALLS);
    * families expand: a family that reports one winner but DECLARED the width it searched is
      charged that width scaled by the redundancy measured on its visible members (the count
      RISES, and a million cells can never report one winner as one trial).

THE ESTIMATOR is the participation ratio of the similarity matrix's eigen-spectrum,
(sum lambda)^2 / sum lambda^2 -- the same statistic `mt5desk.canonical.effective_trials` takes
of the RETURN correlation matrix, applied here to descriptors so it can be computed before any
return series exists. All-identical members give one eigenvalue and N_eff = 1; independent
members give the identity and N_eff = M. Similarity between two trials of the same family is
half the share of equal descriptors and half the closeness of their parameters (numeric
parameters decay with relative distance, so 19 vs 20 is close and 19 vs 57 is not); two trials
of DIFFERENT families are independent by construction. That is the conservative direction for
a multiple-testing charge -- two mechanisms on the same symbol are charged as two searches --
and the ledger says so in `basis`.

DECLARED WIDTH. A trial may carry `declared_width`, the number of cells its search evaluated
before this row was reported (a sweep's matrix width, an evolutionary population times its
generations). The family is charged max(PR, width_max x PR / M): the unseen cells are assumed
to be as redundant as the visible members, which is the only assumption the visible members can
support. A family of one member with width one million is charged one million.

WHO READS IT. `libs.validation.gauntlet.Gauntlet` prices its deflated-Sharpe charge at
ceil(N_effective x multiplier) instead of ceil(rows x multiplier) and reports both; the desk's
external gauntlet publishes the census beside its sealed fixed charge; the science controller
walks the registry and writes N_effective per family. Pure, typed, numpy only.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: Relative distance at which a numeric parameter's closeness has decayed to 1/e.
PARAM_SCALE = 0.25
#: Members whose pairwise similarity reaches this are reported as clone pairs.
CLONE_SIMILARITY = 0.9
#: The row-count ceiling for one family's similarity matrix; larger families are priced on
#: a deterministic sample of members (the ratio PR/M transfers to the whole family).
MAX_MEMBERS = 2500
UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class Trial:
    """One trial as the ledger sees it. `descriptors` are categorical axes (mechanism, data
    source, representation, geography, state, horizon, execution, failure mode, symbol, chart,
    model family ... any string-valued axis); `params` the free parameters; `declared_width`
    the cells searched before this row was reported; `lineage` a family id when a genome has
    been stamped (it overrides `family` as the grouping key)."""

    trial_id: str
    family: str
    descriptors: Mapping[str, str] = field(default_factory=dict)
    params: Mapping[str, Any] = field(default_factory=dict)
    declared_width: int = 1
    lineage: str = ""

    @property
    def group(self) -> str:
        return self.lineage or self.family or "?"


@dataclass(frozen=True)
class FamilyCensus:
    group: str
    n_raw: int
    n_effective_members: float
    declared_width: int
    n_effective: float
    clone_pairs: int
    basis: str

    def to_dict(self) -> dict[str, Any]:
        return {"group": self.group, "n_raw": self.n_raw,
                "n_effective_members": round(self.n_effective_members, 3),
                "declared_width": self.declared_width,
                "n_effective": round(self.n_effective, 3), "clone_pairs": self.clone_pairs,
                "basis": self.basis}


@dataclass(frozen=True)
class LedgerCensus:
    n_raw: int
    n_effective: float
    families: dict[str, FamilyCensus]
    basis: str

    @property
    def inflation(self) -> float:
        return self.n_raw / self.n_effective if self.n_effective > 0 else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"n_raw": self.n_raw, "n_effective": round(self.n_effective, 3),
                "inflation": round(self.inflation, 4), "n_families": len(self.families),
                "basis": self.basis,
                "families": {k: v.to_dict() for k, v in self.families.items()}}


# ------------------------------------------------------------------ similarity
def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v) if math.isfinite(float(v)) else None
    return None


def param_closeness(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    """Mean over the union of keys: numeric pairs decay as exp(-|a-b| / (PARAM_SCALE x
    max(|a|,|b|,1))), other pairs are 1 when equal; a key one side lacks scores 0. Two empty
    parameter sets are identical (1.0)."""
    keys = set(a) | set(b)
    if not keys:
        return 1.0
    total = 0.0
    for k in keys:
        if k not in a or k not in b:
            continue
        x, y = _num(a[k]), _num(b[k])
        if x is not None and y is not None:
            total += math.exp(-abs(x - y) / (PARAM_SCALE * max(abs(x), abs(y), 1.0)))
        elif str(a[k]) == str(b[k]):
            total += 1.0
    return total / len(keys)


def descriptor_share(a: Mapping[str, str], b: Mapping[str, str]) -> float:
    """Share of the union of descriptor axes on which both agree; no axes at all is 1.0."""
    keys = set(a) | set(b)
    if not keys:
        return 1.0
    return sum(1.0 for k in keys if k in a and k in b and str(a[k]) == str(b[k])) / len(keys)


def similarity(a: Trial, b: Trial) -> float:
    """1.0 for the same trial, 0.0 across groups, else the descriptor/parameter blend. A half
    that neither trial carries (no parameters, or no descriptors) is uninformative and drops
    out rather than counting as agreement: two rows with no parameters are not "the same
    parameters", they are rows whose parameters nobody wrote down."""
    if a.group != b.group:
        return 0.0
    if a.trial_id == b.trial_id:
        return 1.0
    has_desc = bool(a.descriptors or b.descriptors)
    has_par = bool(a.params or b.params)
    if has_desc and has_par:
        return 0.5 * descriptor_share(a.descriptors, b.descriptors) + 0.5 * param_closeness(
            a.params, b.params)
    if has_desc:
        return descriptor_share(a.descriptors, b.descriptors)
    if has_par:
        return param_closeness(a.params, b.params)
    return 1.0


def _similarity_matrix(members: Sequence[Trial]) -> np.ndarray:
    """Vectorised similarity within one group: descriptor equality per axis and parameter
    closeness per key, averaged over the union of axes/keys per pair."""
    m = len(members)
    axes = sorted({k for t in members for k in t.descriptors})
    keys = sorted({k for t in members for k in t.params})
    desc = np.ones((m, m))
    if axes:
        eq = np.zeros((m, m))
        present = np.zeros((m, m))
        for ax in axes:
            vals = [t.descriptors.get(ax) for t in members]
            codes = {v: i for i, v in enumerate(sorted({str(v) for v in vals if v is not None}))}
            c = np.array([codes[str(v)] if v is not None else -1 for v in vals])
            has = (c >= 0)
            both = has[:, None] & has[None, :]
            either = has[:, None] | has[None, :]
            eq += both & (c[:, None] == c[None, :])
            present += either
        desc = np.where(present > 0, eq / np.maximum(present, 1.0), 1.0)
    par = np.ones((m, m))
    if keys:
        close = np.zeros((m, m))
        present = np.zeros((m, m))
        for key in keys:
            vals = [t.params.get(key) if key in t.params else None for t in members]
            has = np.array([v is not None for v in vals])
            nums = np.array([_num(v) if v is not None else None for v in vals], dtype=object)
            isnum = np.array([n is not None for n in nums])
            if isnum.any():
                x = np.array([float(n) if n is not None else np.nan for n in nums])
                scale = PARAM_SCALE * np.maximum(np.maximum(np.abs(x[:, None]),
                                                            np.abs(x[None, :])), 1.0)
                with np.errstate(invalid="ignore"):
                    dec = np.exp(-np.abs(x[:, None] - x[None, :]) / scale)
                dec = np.where(isnum[:, None] & isnum[None, :], np.nan_to_num(dec), 0.0)
            else:
                dec = np.zeros((m, m))
            strs = [str(v) if (v is not None and n is None) else None
                    for v, n in zip(vals, nums, strict=True)]
            codes = {s: i for i, s in enumerate(sorted({s for s in strs if s is not None}))}
            c = np.array([codes[s] if s is not None else -1 for s in strs])
            seq = (c[:, None] >= 0) & (c[:, None] == c[None, :])
            close += dec + seq
            present += has[:, None] | has[None, :]
        par = np.where(present > 0, close / np.maximum(present, 1.0), 1.0)
    has_desc = np.zeros((m, m), dtype=bool)
    has_par = np.zeros((m, m), dtype=bool)
    if axes:
        hd = np.array([bool(t.descriptors) for t in members])
        has_desc = hd[:, None] | hd[None, :]
    if keys:
        hp = np.array([bool(t.params) for t in members])
        has_par = hp[:, None] | hp[None, :]
    s = np.where(has_desc & has_par, 0.5 * desc + 0.5 * par,
                 np.where(has_desc, desc, np.where(has_par, par, 1.0)))
    np.fill_diagonal(s, 1.0)
    return np.clip(s, 0.0, 1.0)


def participation_ratio(s: np.ndarray) -> float:
    """(sum lambda)^2 / sum lambda^2 of a symmetric similarity matrix, clipped to [1, M]."""
    if s.size == 0:
        return 0.0
    if s.shape[0] == 1:
        return 1.0
    ev = np.clip(np.linalg.eigvalsh(s), 0.0, None)
    denom = float((ev ** 2).sum())
    if denom <= 0.0:
        return float(s.shape[0])
    return float(max(1.0, min(ev.sum() ** 2 / denom, float(s.shape[0]))))


def family_census(members: Sequence[Trial]) -> FamilyCensus:
    group = members[0].group if members else "?"
    m = len(members)
    if m == 0:
        return FamilyCensus(group, 0, 0.0, 0, 0.0, 0, UNMEASURED)
    width = max(max(int(t.declared_width), 1) for t in members)
    if m == 1:
        pr, pairs = 1.0, 0
    else:
        sample = list(members)
        if m > MAX_MEMBERS:
            step = max(1, m // MAX_MEMBERS)
            sample = list(members)[::step][:MAX_MEMBERS]
        s = _similarity_matrix(sample)
        pr = participation_ratio(s) * (m / len(sample))
        pr = max(1.0, min(pr, float(m)))
        iu = np.triu_indices(len(sample), k=1)
        pairs = int((s[iu] >= CLONE_SIMILARITY).sum()) if iu[0].size else 0
    n_eff = max(pr, width * pr / m)
    basis = (f"participation ratio of {m} member(s) = {pr:.2f}; declared width {width} x "
             f"{pr:.2f}/{m} = {width * pr / m:.2f}; charged {n_eff:.2f}")
    return FamilyCensus(group, m, pr, width, n_eff, pairs, basis)


def census(trials: Iterable[Trial]) -> LedgerCensus:
    """N_raw, N_effective and the per-family breakdown; empty input is UNMEASURED at 0/0."""
    groups: dict[str, list[Trial]] = {}
    for t in trials:
        groups.setdefault(t.group, []).append(t)
    fams = {g: family_census(ms) for g, ms in groups.items()}
    n_raw = sum(f.n_raw for f in fams.values())
    n_eff = float(sum(f.n_effective for f in fams.values()))
    if not fams:
        return LedgerCensus(0, 0.0, {}, UNMEASURED)
    return LedgerCensus(n_raw, n_eff, fams,
                        "sum over families of max(participation ratio of descriptor/parameter "
                        "similarity, declared width x PR/M); families independent")


# ------------------------------------------------------------------ records -> trials
_IDENTITY_KEYS = frozenset({"candidate_id", "hypothesis_id", "id", "trial_id", "cell",
                            "genome_id", "node_id", "run_id"})
_DESCRIPTOR_KEYS: tuple[str, ...] = (
    "mechanism", "data", "representation", "geography", "state", "horizon", "execution",
    "failure", "symbol", "sym", "chart", "timeframe", "session", "regime", "information",
    "asset_class", "model_family", "dataset", "feature", "signal", "method")


def trial_from_record(rec: Mapping[str, Any] | Any, *, index: int = 0) -> Trial:
    """A Trial from any record the desk writes: a registry `research_candidates` or
    `trials_ledger` row, a `libs.store.models.TrialRecord`, a sweep cell, a genome dict.
    Missing descriptors are simply absent -- never invented."""
    get: Any
    if isinstance(rec, Mapping):
        get = rec.get
    else:
        def get(k: str, default: Any = None) -> Any:
            return getattr(rec, k, default)
    params = get("params")
    if params is None:
        raw = get("params_json")
        if isinstance(raw, str) and raw:
            import json
            try:
                params = json.loads(raw)
            except ValueError:
                params = {}
    # Identities are not parameters: two gauntlet rows that differ only in candidate_id are
    # the same search until a descriptor or a parameter says otherwise. A genome or a declared
    # width carried INSIDE the params (the libs gauntlet's ledger row) is lifted out of them.
    params = ({k: v for k, v in params.items() if k not in _IDENTITY_KEYS}
              if isinstance(params, Mapping) else {})
    desc: dict[str, str] = {}
    genome = get("genome") or params.pop("genome", None)
    width_in_params = params.pop("declared_width", None) or params.pop("search_width", None)
    nested = params.pop("params", None)
    if isinstance(nested, Mapping):
        params.update({str(k): v for k, v in nested.items() if k not in _IDENTITY_KEYS})
    if isinstance(genome, Mapping):
        desc.update({str(k): str(v) for k, v in genome.items() if v not in (None, "")})
    for k in _DESCRIPTOR_KEYS:
        v = get(k)
        if v not in (None, "") and k not in desc:
            desc[k] = str(v)
    tid = str(get("trial_id") or get("id") or get("candidate_id") or get("hypothesis_id")
              or get("cell") or f"trial_{index}")
    width = get("declared_width") or get("search_width") or width_in_params or 1
    try:
        width_i = max(1, int(width))
    except (TypeError, ValueError):
        width_i = 1
    return Trial(tid, str(get("family") or get("trial_family") or ""), desc, params, width_i,
                 str(get("lineage") or get("family_id") or ""))


def effective_count_of_records(records: Iterable[Mapping[str, Any] | Any]) -> float:
    """N_effective of any iterable of records; 0.0 for none."""
    return census(trial_from_record(r, index=i) for i, r in enumerate(records)).n_effective


# ------------------------------------------- THE CHARGE: effective independent tests
# WHY A SECOND ESTIMATOR, AND WHY IT IS THE ONE THAT MAY BE CHARGED. `census` above prices a
# family by the eigen-spectrum of a similarity matrix -- the right instrument when descriptors
# are continuous and the question is "how redundant is this family". The multiplicity BUDGET asks
# a coarser and more auditable question: HOW MANY DISTINCT TESTS WERE ACTUALLY RUN. Thirty-one
# parameter variants of one rule on one instrument at one horizon are one test that was tuned,
# not thirty-one independent looks at the data, and the desk already measures the three
# identities that say so:
#
#     grid cell  (family, symbol, horizon)   -- where the test was pointed
#     content    (descriptors + parameters)  -- what was actually evaluated
#     mechanism  (the family/lineage group)  -- which economic claim was being tested
#
# The estimator is the SAME participation ratio, taken of the identity-group SIZES:
# (sum n_i)^2 / sum n_i^2 over the distinct (grid, content) identities within one mechanism.
# k identical clones collapse to 1; k genuinely distinct identities count k; k groups of unequal
# size count somewhere between, weighted toward the larger. It cannot exceed the row count and it
# cannot fall below 1, so a family can never be charged as less than one search.
#
# DIRECTION AND THE FLOOR. This number is only ever SMALLER than the nominal row count, so it can
# only make a multiple-testing bar easier; that is the whole reason the floor below is not
# negotiable. The charge is floored at the number of distinct MECHANISMS -- you cannot have run
# fewer independent tests than you had distinct economic claims -- and any census that cannot
# measure fails closed to the nominal count, never to the smaller one.
GRID_AXES: tuple[str, ...] = ("family", "symbol", "horizon")
#: Descriptor axes that carry the grid cell, in order of preference per axis.
_GRID_SOURCES: dict[str, tuple[str, ...]] = {
    "symbol": ("symbol", "sym"),
    "horizon": ("horizon", "timeframe", "chart"),
}


def grid_key(trial: Trial) -> str:
    """(family, symbol, horizon) -- where a test was pointed. Missing axes are `?`, never
    invented: two rows that both fail to name a symbol are not thereby the same symbol, but they
    ARE the same state of knowledge, and charging them apart would reward not writing it down."""
    parts = [trial.group or "?"]
    for axis in ("symbol", "horizon"):
        val = ""
        for src in _GRID_SOURCES[axis]:
            v = trial.descriptors.get(src)
            if v:
                val = str(v)
                break
        parts.append(val or "?")
    return "|".join(parts)


def content_key(trial: Trial) -> str:
    """What was actually evaluated: every descriptor and parameter, canonically ordered. Two rows
    with the same content are the same evaluation however many ids the desk minted for them."""
    desc = ";".join(f"{k}={trial.descriptors[k]}" for k in sorted(trial.descriptors))
    par = ";".join(f"{k}={trial.params[k]!r}" for k in sorted(trial.params))
    return f"{desc}#{par}"


def mechanism_key(trial: Trial) -> str:
    """Which economic claim was under test -- the lineage when a genome was stamped, else the
    family. This is the identity that showed the collapse: many cells, one mechanism."""
    return trial.group


@dataclass(frozen=True)
class FamilyCharge:
    """One mechanism's nominal row count beside the effective tests it may be charged."""

    family: str
    n_nominal: int
    n_effective: float
    n_grid_cells: int
    n_identities: int
    ratio: float
    basis: str

    def to_dict(self) -> dict[str, Any]:
        return {"family": self.family, "n_nominal": self.n_nominal,
                "n_effective": round(self.n_effective, 3),
                "n_grid_cells": self.n_grid_cells, "n_identities": self.n_identities,
                "ratio": round(self.ratio, 4), "basis": self.basis}


@dataclass(frozen=True)
class ChargeCensus:
    """The whole docket: nominal rows, effective independent tests, and the ratio between."""

    n_nominal: int
    n_effective: float
    n_mechanisms: int
    families: dict[str, FamilyCharge]
    basis: str
    status: str = "MEASURED"

    @property
    def ratio(self) -> float:
        """Nominal per effective test. 1.0 when nothing was measured -- never a free discount."""
        return self.n_nominal / self.n_effective if self.n_effective > 0 else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "n_nominal": self.n_nominal,
                "n_effective": round(self.n_effective, 3), "ratio": round(self.ratio, 4),
                "n_mechanisms": self.n_mechanisms, "basis": self.basis,
                "families": {k: v.to_dict() for k, v in sorted(self.families.items())}}


def _identity_participation(sizes: Sequence[int]) -> float:
    """(sum n)^2 / sum n^2 of identity-group sizes, clipped to [1, sum n]."""
    total = float(sum(sizes))
    if total <= 0.0:
        return 0.0
    denom = float(sum(float(n) * float(n) for n in sizes))
    if denom <= 0.0:
        return total
    return float(max(1.0, min(total * total / denom, total)))


def _grid_cell_effective(members: Sequence[Trial]) -> float:
    """Effective independent tests INSIDE one grid cell -- one mechanism, one symbol, one horizon.

    EXACT IDENTITY IS THE WRONG KNIFE HERE and measuring it said so: on the live docket every one
    of 22,925 rows carried a distinct content key, because a sweep's rows differ in the parameter
    it swept. `EMA(19,57)` and `EMA(20,58)` are two contents and one search. So inside the cell
    the charge is the module's OWN similarity participation ratio -- numeric parameters decay with
    relative distance -- which collapses a neighbourhood of tunings toward one and keeps genuinely
    different rules apart. Across cells nothing is collapsed: a different symbol or horizon is a
    different test of the claim, and charging those together would be the loose direction.
    """
    m = len(members)
    if m <= 1:
        return float(m)
    sample = list(members)
    if m > MAX_MEMBERS:
        step = max(1, m // MAX_MEMBERS)
        sample = sample[::step][:MAX_MEMBERS]
    pr = participation_ratio(_similarity_matrix(sample)) * (m / len(sample))
    return float(max(1.0, min(pr, float(m))))


def family_charge(members: Sequence[Trial]) -> FamilyCharge:
    """One mechanism's charge: its grid cells, each priced by within-cell participation ratio."""
    if not members:
        return FamilyCharge("?", 0, 0.0, 0, 0, 1.0, UNMEASURED)
    fam = mechanism_key(members[0]) or "?"
    cells: dict[str, list[Trial]] = {}
    identities: set[tuple[str, str]] = set()
    for t in members:
        g = grid_key(t)
        cells.setdefault(g, []).append(t)
        identities.add((g, content_key(t)))
    n_eff = float(sum(_grid_cell_effective(ms) for ms in cells.values()))
    n_raw = len(members)
    n_eff = max(1.0, min(n_eff, float(n_raw)))
    ratio = n_raw / n_eff if n_eff > 0 else 1.0
    biggest = max(len(ms) for ms in cells.values())
    basis = (f"{n_raw} row(s) over {len(cells)} grid cell(s) and {len(identities)} "
             f"(grid, content) identit(ies); sum of within-cell participation ratios "
             f"{n_eff:.2f}; largest grid cell holds {biggest} row(s)")
    return FamilyCharge(fam, n_raw, n_eff, len(cells), len(identities), ratio, basis)


def effective_independent_tests(
        records: Iterable[Mapping[str, Any] | Any]) -> ChargeCensus:
    """Nominal rows versus effective independent tests, per mechanism and in total.

    Mechanisms are independent by construction (the conservative direction: two mechanisms on one
    symbol are two searches), so the total is the sum over mechanisms of each one's participation
    ratio, floored at the number of distinct mechanisms.
    """
    by_fam: dict[str, list[Trial]] = {}
    for i, rec in enumerate(records):
        t = trial_from_record(rec, index=i)
        by_fam.setdefault(mechanism_key(t) or "?", []).append(t)
    if not by_fam:
        return ChargeCensus(0, 0.0, 0, {}, UNMEASURED, UNMEASURED)
    charges = {fam: family_charge(ms) for fam, ms in by_fam.items()}
    n_nominal = sum(c.n_nominal for c in charges.values())
    n_eff = float(sum(c.n_effective for c in charges.values()))
    n_eff = max(n_eff, float(len(charges)))
    return ChargeCensus(
        n_nominal, n_eff, len(charges), charges,
        "sum over mechanisms of the participation ratio of their (grid cell, content) identity "
        "sizes; mechanisms independent; floored at the number of distinct mechanisms")


def campaign_charge(nominal_campaign_trials: int, census: ChargeCensus,
                    *, floor: int = 2) -> tuple[int, str]:
    """Scale a standing campaign trial count by MEASURED redundancy, and fail closed upward.

    The campaign charge is a policy constant so that a candidate's bar is not a property of the
    batch it was scheduled into. What this does is correct that constant for the redundancy the
    desk can actually measure in the tests it ran: charging thirty-one tunings of one rule as
    thirty-one independent looks is an over-correction, and an over-correction is still a wrong
    correction. Every failure path returns the UNCHANGED nominal count -- an unmeasurable census
    buys no relief at all.
    """
    nominal = int(max(0, nominal_campaign_trials))
    if nominal < floor:
        return max(floor, nominal), "nominal_campaign_trials (below floor, unchanged)"
    if census.status != "MEASURED" or census.n_nominal <= 0 or census.n_effective <= 0:
        return nominal, f"nominal_campaign_trials({nominal}) fail_closed (census {census.status})"
    ratio = census.n_effective / census.n_nominal
    if not math.isfinite(ratio) or ratio <= 0.0 or ratio > 1.0:
        return nominal, f"nominal_campaign_trials({nominal}) fail_closed (ratio {ratio:.4f})"
    charged = math.ceil(nominal * ratio)
    hard_floor = max(floor, census.n_mechanisms)
    charged = max(charged, hard_floor)
    charged = min(charged, nominal)
    return charged, (f"effective_campaign_trials({charged}) = ceil({nominal} x "
                     f"{census.n_effective:.2f}/{census.n_nominal}) floored at "
                     f"{hard_floor} distinct mechanism(s)")
