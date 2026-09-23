"""RESEARCH PRIORS -- every completed experiment moves a posterior the next allocation reads.

THE PRINCIPAL (RD-Agent closure, item 4): *priors updated by every completed experiment --
P(family works), P(operator works), P(source yields value), P(model works with representation) as
Beta/Dirichlet posteriors, persisted, and CONSUMED by the next allocation.*

THE DEFECT THIS CLOSES. The desk has measured yields for weeks -- generator_yield, source_yield,
family trials -- and every one of them is a COUNT. A count cannot be allocated against, because it
does not distinguish "0 survivors from 1 try" from "0 survivors from 400 tries", and the desk's
search organs draw families and operators as though those were the same evidence. They are not:
the first is ignorance and deserves compute, the second is knowledge and deserves less. A Beta
posterior is the smallest object that tells them apart, and it is the object every bandit, every
Thompson draw and every expected-information calculation in this repository already wants.

    THE FOUR DIMENSIONS, and what a "success" is on each

    family          a registered strategy family        an experiment that SURVIVED the gauntlet
    operator        the search method / math operator   ditto, credited to the method that minted it
    source          a miner, forum, dataset or crawl    ditto, credited to the source that suggested
    model_repr      model x representation (a PAIR)     ditto, for the pair that was run

    Plus one Dirichlet per dimension over the OUTCOME CLASSES -- survived / rejected_no_edge /
    rejected_cost / rejected_unstable / blocked / unmeasured -- because "it failed" and "it failed
    on costs" send the next allocation to opposite places.

THE API IS SMALL AND STABLE ON PURPOSE (the maths/physics factory and the coevolution builder both
call it):

    record_outcome(outcome, *, family=, operator=, source=, model=, representation=,
                   experiment_id=, weight=)   -> dict of the keys it moved
    prior_for(dimension, key)                 -> Prior(mean, a, b, n, lo, hi, status)
    posterior_mean(dimension, key)            -> float  (the prior's mean, or the PRIOR when unseen)
    thompson(dimension, keys, rng=)           -> {key: sampled p}   for an allocation draw
    rank(dimension, keys)                     -> keys ordered by mean + uncertainty bonus
    snapshot()                                -> everything, for a report
    load()/save()                             -> persisted state (desks/mt5/data/research_priors)

UNSEEN IS NOT ZERO. A key with no observations returns the UNIFORM Beta(1,1): mean 0.5, status
`PRIOR`. It never returns 0.0, because a family nobody has tried must not be ranked below a family
measured to fail -- that is how a search collapses onto what it has already done. Conversely
nothing here is a cap or a veto: a posterior ORDERS the draw, it never forbids one, and
`rank` keeps every key in the list (GROWTH_GOVERNANCE Rule 1 -- a reduction must prove it raises
robust forward E[log W], and "we stopped looking" proves nothing).

DECAY IS TIME, NOT FORGETTING. `half_life_days` shrinks old evidence toward the prior when a
posterior is read with `as_of`, so a family that worked in 2024 and has not been retested does not
hold its authority forever. The stored counts are never rewritten: the decay is applied at read
time and the raw record stays auditable.
"""
from __future__ import annotations

import json
import math
import os
import random
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / "desks" / "mt5" / "data" / "research_priors"
BETA_PATH = STATE_DIR / "beta.json"
DIRICHLET_PATH = STATE_DIR / "dirichlet.json"

#: The dimensions a prior is kept on. `model_repr` is the PAIR (model, representation), because
#: the principal's question is "P(model works with representation)" -- a model that works on
#: ranks and fails on levels is one fact, not two.
DIMENSIONS: tuple[str, ...] = ("family", "operator", "source", "model_repr", "kind", "region")

#: The outcome classes the Dirichlet is over. `unmeasured` is a class, not a gap: an experiment
#: that could not be judged consumed compute and must appear in the denominator.
OUTCOME_CLASSES: tuple[str, ...] = ("survived", "rejected_no_edge", "rejected_cost",
                                    "rejected_unstable", "blocked", "unmeasured")

#: Which outcome classes count as a Beta success. Only a real survivor.
_SUCCESS: frozenset[str] = frozenset({"survived"})

#: Uniform Beta(1,1): an unseen key is ignorance, never failure.
PRIOR_A = 1.0
PRIOR_B = 1.0

#: Dirichlet concentration on an unseen key: uniform over the outcome classes.
PRIOR_ALPHA = 1.0

#: Evidence older than this loses half its weight when a posterior is read with `as_of`.
HALF_LIFE_DAYS = 180.0

#: The exploration bonus `rank` adds: one posterior standard deviation. Not tuned -- it is the
#: UCB1-normal shape, and it is the smallest bonus that keeps an unseen key ahead of a key
#: measured to fail.
_UCB_K = 1.0


@dataclass(frozen=True)
class Prior:
    """One Beta posterior, with its evidence and its status."""

    dimension: str
    key: str
    a: float = PRIOR_A
    b: float = PRIOR_B
    n: int = 0
    last_at: str = ""
    status: str = "PRIOR"          # PRIOR (unseen) | POSTERIOR
    outcomes: Mapping[str, float] = None  # type: ignore[assignment]

    @property
    def mean(self) -> float:
        return self.a / (self.a + self.b)

    @property
    def sd(self) -> float:
        t = self.a + self.b
        return math.sqrt(self.a * self.b / (t * t * (t + 1.0)))

    def interval(self, z: float = 1.96) -> tuple[float, float]:
        """A normal-approximation credible interval, clipped to [0,1]. The approximation is
        stated rather than hidden: at n<5 it is wide and that is the correct signal."""
        m, s = self.mean, self.sd
        return (max(0.0, m - z * s), min(1.0, m + z * s))

    def to_dict(self) -> dict[str, Any]:
        lo, hi = self.interval()
        return {"dimension": self.dimension, "key": self.key, "a": round(self.a, 6),
                "b": round(self.b, 6), "n": self.n, "mean": round(self.mean, 6),
                "sd": round(self.sd, 6), "lo": round(lo, 6), "hi": round(hi, 6),
                "status": self.status, "last_at": self.last_at,
                "outcomes": dict(self.outcomes or {})}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _atomic_write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True, default=str)
        os.replace(tmp, path)
    except OSError:
        # A read-only destination raises WinError 5 on Windows where POSIX allows the replace;
        # a prior that cannot be persisted must not take the caller's pass down with it.
        Path(tmp).unlink(missing_ok=True)


def _paths(state_dir: Path | None) -> tuple[Path, Path]:
    d = state_dir or STATE_DIR
    return d / "beta.json", d / "dirichlet.json"


def load(state_dir: Path | None = None) -> dict[str, Any]:
    """The persisted state: {"beta": {dim: {key: [a,b,n,last_at]}}, "dirichlet": {...}}."""
    beta_path, dir_path = _paths(state_dir)
    beta = _read(beta_path)
    diri = _read(dir_path)
    return {"beta": beta.get("dimensions") or {}, "dirichlet": diri.get("dimensions") or {},
            "updated_at": str(beta.get("updated_at") or ""),
            "n_updates": int(beta.get("n_updates") or 0)}


def save(state: Mapping[str, Any], state_dir: Path | None = None) -> None:
    beta_path, dir_path = _paths(state_dir)
    at = _now()
    _atomic_write(beta_path, {"updated_at": at, "n_updates": int(state.get("n_updates") or 0),
                              "prior": {"a": PRIOR_A, "b": PRIOR_B},
                              "dimensions": state.get("beta") or {}})
    _atomic_write(dir_path, {"updated_at": at, "classes": list(OUTCOME_CLASSES),
                             "prior_alpha": PRIOR_ALPHA,
                             "dimensions": state.get("dirichlet") or {}})


def classify(verdict: str, *, rejection_reason: str = "", failure_class: str = "") -> str:
    """Map a desk verdict onto one of `OUTCOME_CLASSES`. The reason matters: a family killed by
    costs is not a family with no edge, and the two send the next allocation opposite ways."""
    v = (verdict or "").strip().upper()
    if v in ("SURVIVED", "LIVE", "FORWARD"):
        return "survived"
    if v == "BLOCKED":
        return "blocked"
    if v in ("", "UNJUDGED", "UNMEASURED", "PROPOSED", "QUEUED", "RUNNING"):
        return "unmeasured"
    blob = f"{rejection_reason} {failure_class}".lower()
    if any(t in blob for t in ("cost", "spread", "slippage", "commission", "execution")):
        return "rejected_cost"
    if any(t in blob for t in ("unstable", "fragil", "regime", "decay", "drift", "pbo")):
        return "rejected_unstable"
    return "rejected_no_edge"


def _keys_from(family: str | None, operator: str | None, source: str | None,
               model: str | None, representation: str | None, kind: str | None,
               region: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if family:
        out["family"] = str(family)
    if operator:
        out["operator"] = str(operator)
    if source:
        out["source"] = str(source)
    if model or representation:
        out["model_repr"] = f"{model or '?'}|{representation or '?'}"
    if kind:
        out["kind"] = str(kind)
    if region:
        out["region"] = str(region)
    return out


def record_outcome(outcome: str, *, family: str | None = None, operator: str | None = None,
                   source: str | None = None, model: str | None = None,
                   representation: str | None = None, kind: str | None = None,
                   region: str | None = None, weight: float = 1.0,
                   experiment_id: str = "", rejection_reason: str = "",
                   failure_class: str = "", state: dict[str, Any] | None = None,
                   state_dir: Path | None = None,
                   persist: bool = True) -> dict[str, Any]:
    """ONE completed experiment updates every posterior it is evidence for.

    `outcome` is a verdict (`SURVIVED`/`REJECTED`/...) or an outcome class directly. `weight` lets
    a caller charge partial evidence (half a trial for a screening pass), and is why the counts
    are floats. Pass `state` to batch many updates without touching disk; call `save` once after.

    Returns `{"outcome_class": ..., "moved": {dimension: key}}` so a caller can log exactly what
    its experiment taught, which is the whole point of the item.
    """
    cls = outcome if outcome in OUTCOME_CLASSES else classify(
        outcome, rejection_reason=rejection_reason, failure_class=failure_class)
    st = state if state is not None else load(state_dir)
    beta: dict[str, Any] = st.setdefault("beta", {})
    diri: dict[str, Any] = st.setdefault("dirichlet", {})
    keys = _keys_from(family, operator, source, model, representation, kind, region)
    w = max(0.0, float(weight))
    at = _now()
    for dim, key in keys.items():
        row = beta.setdefault(dim, {}).setdefault(key, {"a": 0.0, "b": 0.0, "n": 0,
                                                        "last_at": "", "last_experiment": ""})
        if cls in _SUCCESS:
            row["a"] = float(row.get("a", 0.0)) + w
        elif cls != "unmeasured":
            # An UNMEASURED experiment is not a failure. It consumed compute and it appears in
            # the Dirichlet, but charging it as a Beta failure would teach the allocator that
            # the thing does not work when what happened is that nobody looked.
            row["b"] = float(row.get("b", 0.0)) + w
        row["n"] = int(row.get("n", 0)) + 1
        row["last_at"] = at
        if experiment_id:
            row["last_experiment"] = experiment_id
        drow = diri.setdefault(dim, {}).setdefault(key, {})
        drow[cls] = float(drow.get(cls, 0.0)) + w
    st["n_updates"] = int(st.get("n_updates") or 0) + 1
    st["updated_at"] = at
    if persist and state is None:
        save(st, state_dir)
    return {"outcome_class": cls, "moved": keys, "weight": w}


def _decay(count: float, last_at: str, as_of: datetime | None,
           half_life_days: float) -> float:
    if as_of is None or not last_at or half_life_days <= 0:
        return count
    try:
        t = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
    except ValueError:
        return count
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    days = max(0.0, (as_of - t).total_seconds() / 86400.0)
    return float(count * (0.5 ** (days / half_life_days)))


def prior_for(dimension: str, key: str, *, state: Mapping[str, Any] | None = None,
              state_dir: Path | None = None, as_of: datetime | None = None,
              half_life_days: float = HALF_LIFE_DAYS) -> Prior:
    """The posterior for one key. An unseen key is Beta(1,1) with status PRIOR, never zero."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}; known: {DIMENSIONS}")
    st = state if state is not None else load(state_dir)
    row = ((st.get("beta") or {}).get(dimension) or {}).get(key)
    outs = ((st.get("dirichlet") or {}).get(dimension) or {}).get(key) or {}
    if not isinstance(row, Mapping):
        return Prior(dimension, key, PRIOR_A, PRIOR_B, 0, "", "PRIOR", dict(outs))
    last = str(row.get("last_at") or "")
    a = PRIOR_A + _decay(float(row.get("a", 0.0)), last, as_of, half_life_days)
    b = PRIOR_B + _decay(float(row.get("b", 0.0)), last, as_of, half_life_days)
    n = int(row.get("n", 0))
    return Prior(dimension, key, a, b, n, last, "POSTERIOR" if n else "PRIOR", dict(outs))


def posterior_mean(dimension: str, key: str, **kw: Any) -> float:
    return prior_for(dimension, key, **kw).mean


def outcome_posterior(dimension: str, key: str, *, state: Mapping[str, Any] | None = None,
                      state_dir: Path | None = None) -> dict[str, float]:
    """The Dirichlet posterior mean over `OUTCOME_CLASSES` -- where this key's failures GO."""
    st = state if state is not None else load(state_dir)
    counts = ((st.get("dirichlet") or {}).get(dimension) or {}).get(key) or {}
    alphas = {c: PRIOR_ALPHA + float(counts.get(c, 0.0)) for c in OUTCOME_CLASSES}
    tot = sum(alphas.values())
    return {c: round(v / tot, 6) for c, v in alphas.items()}


def thompson(dimension: str, keys: Sequence[str], *, rng: random.Random | None = None,
             state: Mapping[str, Any] | None = None, state_dir: Path | None = None,
             as_of: datetime | None = None) -> dict[str, float]:
    """One Thompson draw per key: sample p ~ Beta(a,b). This is the allocation draw the search
    organs make -- an unseen key draws from the uniform and therefore competes, which is exactly
    the behaviour a desk that must keep exploring needs."""
    r = rng or random.Random()   # noqa: S311 -- a Thompson draw, not a secret
    st = state if state is not None else load(state_dir)
    out: dict[str, float] = {}
    for k in keys:
        p = prior_for(dimension, k, state=st, as_of=as_of)
        out[k] = r.betavariate(max(p.a, 1e-6), max(p.b, 1e-6))
    return out


def rank(dimension: str, keys: Iterable[str], *, state: Mapping[str, Any] | None = None,
         state_dir: Path | None = None, as_of: datetime | None = None,
         k: float = _UCB_K) -> list[dict[str, Any]]:
    """Keys ordered by posterior mean PLUS an uncertainty bonus, every key kept.

    The bonus is one posterior standard deviation. Without it the ranking collapses onto whatever
    has been tried most, which is the failure mode the priors exist to prevent; with it, a family
    with two tries and one survivor outranks a family with two hundred tries and four, and both
    stay in the list. NOTHING IS DROPPED: this orders a draw, it never vetoes one.
    """
    st = state if state is not None else load(state_dir)
    rows: list[dict[str, Any]] = []
    for key in keys:
        p = prior_for(dimension, key, state=st, as_of=as_of)
        rows.append({**p.to_dict(), "score": round(p.mean + k * p.sd, 6)})
    rows.sort(key=lambda r: (-float(r["score"]), str(r["key"])))
    return rows


def dimension_keys(dimension: str, *, state: Mapping[str, Any] | None = None,
                   state_dir: Path | None = None) -> list[str]:
    st = state if state is not None else load(state_dir)
    return sorted((st.get("beta") or {}).get(dimension) or {})


def snapshot(*, state: Mapping[str, Any] | None = None, state_dir: Path | None = None,
             top: int = 25) -> dict[str, Any]:
    """Everything, for the report: per dimension the top keys by score and the totals."""
    st = state if state is not None else load(state_dir)
    out: dict[str, Any] = {"updated_at": st.get("updated_at") or "",
                           "n_updates": int(st.get("n_updates") or 0),
                           "dimensions": {}, "classes": list(OUTCOME_CLASSES),
                           "prior": {"a": PRIOR_A, "b": PRIOR_B,
                                     "why": "an unseen key is ignorance (mean 0.5), never a "
                                            "measured failure"}}
    for dim in DIMENSIONS:
        keys = dimension_keys(dim, state=st)
        ranked = rank(dim, keys, state=st)[:top]
        for row in ranked:
            row["outcomes"] = outcome_posterior(dim, str(row["key"]), state=st)
        out["dimensions"][dim] = {
            "n_keys": len(keys),
            "n_observations": sum(int(((st.get("beta") or {}).get(dim) or {}).get(kk, {})
                                      .get("n", 0)) for kk in keys),
            "top": ranked,
        }
    return out
