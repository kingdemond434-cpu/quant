"""FEDERATION OPERATIONS, the pure half: the persisted ExternalResearchSystemRegistry row with
every field LAWS 5h/5m name, its content-hashed append-only history, the delta-scan hash set that
keeps an unchanged upstream at near-zero compute, the benchmark twin (native workflow vs
integrated variant at EQUAL compute), the spawn-signal -> ExternalSystem bridge, the delayed-yield
rule for the technique exchange, and the twelve invariants whose first failure is the one thing
the federation dashboard must name.

THE LAW THIS SERVES (docs/LAWS.md 5h and 5m, principal 2026-09-17/19, permanent). A system is
fully exploited only when it is REGISTERED and SANDBOXED and SCHEDULED and EXECUTED and PROGRESSED
and PRODUCED and CONSUMED and ATTRIBUTED; every system has a benchmark twin and if integration
makes it worse the native path is kept; every system is delta-scanned and the exact upstream
revision behind every candidate is persisted; the dashboard shows scientific outputs, never
uptime, and the exact first invariant preventing FEDERATION_CLOSED_AND_HEALTHY = true.

WHAT THIS MODULE IS AND IS NOT. Pure and typed: no I/O beyond `Registry.load/save`, no fetching,
no registry connection. `libs/research/external_federation.py` owns the roster, `admit()`, the
packet contract and ROI_s; `desks/mt5/research/source_civilizations.py` owns the spawn-signal
vocabulary, the extraction schema and the per-entity capability ledger; the ORGAN
`desks/mt5/research/federation_ops.py` reads desk state and writes the artifacts. This file adds
only what none of them hold: the persisted per-system row, its history, the hash set, the twin,
the delayed-yield rule and the invariants.

UNMEASURED IS A VALUE (L1.28a). A field nothing measured reads UNMEASURED by name; an invariant
nothing can measure reads ok=None and is still "not True", which is what the one bit needs.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.research import external_federation as fed

UNMEASURED = "UNMEASURED"

#: THE PERSISTED ROW, every field LAWS 5h/5m name. `system_id` keys it; the rest read UNMEASURED
#: until an organ measures them. The schema is CLOSED: a field outside it raises at `upsert`, so a
#: typo cannot quietly become a second, unqueryable copy of a real one.
REGISTRY_FIELDS: tuple[str, ...] = (
    "system_id", "name", "upstream_repo", "commit_version", "licence", "authors_lineage",
    "capability_fingerprint", "fingerprint_state", "capabilities", "axes", "integration_mode",
    "disposition", "security_profile", "data_dependencies", "compute_requirements",
    "native_search_algorithm", "native_representation_language", "native_validation_methods",
    "supported_markets", "historical_claims", "known_weaknesses", "duplicate_family_id",
    "sandbox_image_hash", "schedule", "progress_watermark", "outputs", "canonical_consumers",
    "trials_donated", "descendants_created", "forward_survivors", "live_portfolio_contribution",
    "compute_spent", "last_upstream_delta_scan", "next_upstream_delta_scan", "region",
    "languages", "discovery_source", "spawn_signal", "first_seen", "updated_at", "why",
)
#: Fields whose change is not a change of the system, so they never enter the history.
VOLATILE_FIELDS: frozenset[str] = frozenset({"updated_at"})
#: The watched surfaces (LAWS 5h): "delta scanning by hash (repos, commits, releases, docs,
#: issues, papers, websites, datasets) keeps unchanged sources at near-zero compute".
DELTA_SURFACES: tuple[str, ...] = ("repos", "commits", "releases", "docs", "issues", "papers",
                                   "websites", "datasets")
#: A changed surface reopens the capability fingerprint: what a system CAN DO may have changed.
FINGERPRINT_STATES: tuple[str, ...] = ("UNMEASURED", "MEASURED", "REOPENED")
TWIN_VARIANTS: tuple[str, ...] = ("native", "integrated")
TWIN_VERDICTS: tuple[str, ...] = ("NATIVE_STANDS", "INTEGRATED_BETTER", "TIE", UNMEASURED)
#: The twelve invariants of FEDERATION_CLOSED_AND_HEALTHY, in the order the first failure is
#: named: the eight operational terms for every DIRECT/WRAPPED/REBUILT row (LAWS 5m's
#: conjunction), then conservation, stranding, delta freshness and self-validation.
INVARIANTS: tuple[str, ...] = (
    "registered", "sandboxed", "scheduled", "executed", "progressed", "produced", "consumed",
    "attributed", "candidate_conservation", "zero_stranded", "delta_scans_fresh",
    "no_self_validation",
)
#: A delta scan older than this is not "unchanged", it is unwatched (mirrors the federation
#: organ's DELTA_STALE_DAYS so the two organs never disagree about what fresh means).
DELTA_STALE_DAYS = 14
#: The technique exchange judges DELAYED yield: a technique younger than this has no yield yet,
#: which is UNMEASURED and never a failure.
TECHNIQUE_DELAY_H = 24.0


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")


def _parse(stamp: Any) -> datetime | None:
    if not stamp or stamp == UNMEASURED:
        return None
    try:
        dt = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def measured(value: Any) -> bool:
    """A value somebody measured: not None, not "", not UNMEASURED, not an empty container."""
    if value is None or value == UNMEASURED or value == "":
        return False
    return not (isinstance(value, (list, tuple, dict)) and len(value) == 0)


def content_hash(content: bytes | str | Mapping[str, Any] | Sequence[Any]) -> str:
    if isinstance(content, (bytes, bytearray)):
        body = bytes(content)
    elif isinstance(content, str):
        body = content.encode("utf-8")
    else:
        body = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(body).hexdigest()[:32]


def registry_row(system_id: str, **fields: Any) -> dict[str, Any]:
    """A full row, UNMEASURED by name wherever nothing measured it."""
    unknown = sorted(k for k in fields if k not in REGISTRY_FIELDS)
    if unknown:
        raise ValueError(f"{unknown} are not registry fields; the schema is closed so a typo "
                         f"cannot become a second copy of a real field")
    row: dict[str, Any] = dict.fromkeys(REGISTRY_FIELDS, UNMEASURED)
    row["system_id"] = system_id
    row["fingerprint_state"] = UNMEASURED
    row.update(fields)
    return row


def row_from_system(system: fed.ExternalSystem, **state: Any) -> dict[str, Any]:
    """The registry row a roster entry starts as: what the roster knows, nothing invented."""
    base = registry_row(
        system.system_id, name=system.name, upstream_repo=system.upstream,
        licence=system.licence, integration_mode=system.integration,
        capabilities=list(system.capabilities), axes=list(system.axes),
        capability_fingerprint=fed.fingerprint(system),
        fingerprint_state="MEASURED" if system.capabilities else UNMEASURED,
        region=system.region, languages=list(system.languages),
        discovery_source=system.discovery_source,
        duplicate_family_id=system.lineage_parent or system.system_id,
        authors_lineage=([system.lineage_parent] if system.lineage_parent else []),
        why=system.notes or "")
    base.update(state)
    return base


# --------------------------------------------------------------------------- the hash set
@dataclass
class DeltaSet:
    """Per-source, per-surface content hashes. `changed_since` is what makes thousands of watched
    sources affordable: only a source whose hash moved is re-analysed."""

    hashes: dict[str, dict[str, str]] = field(default_factory=dict)
    scanned_at: dict[str, str] = field(default_factory=dict)

    def observe(self, source_id: str, surface: str,
                content: bytes | str | Mapping[str, Any] | Sequence[Any], *,
                at: str | None = None) -> bool:
        """Record the surface's hash; True when it DIFFERS from the last one recorded.

        A first sight is not a change (nothing to differ from), which matches
        `source_civilizations.delta_scan`'s `first_scan`.
        """
        if surface not in DELTA_SURFACES:
            raise ValueError(f"{surface!r} is not a watched surface {DELTA_SURFACES}")
        h = content_hash(content)
        prev = self.hashes.get(source_id, {}).get(surface)
        self.hashes.setdefault(source_id, {})[surface] = h
        self.scanned_at[source_id] = at or now_iso()
        return prev is not None and prev != h

    def changed_since(self, last: DeltaSet | Mapping[str, Mapping[str, str]]
                      ) -> dict[str, list[str]]:
        """source_id -> the surfaces whose hash differs from `last` or are new there. A source
        absent from the result is UNCHANGED and costs nothing this pass."""
        old = last.hashes if isinstance(last, DeltaSet) else last
        out: dict[str, list[str]] = {}
        for sid, surfaces in self.hashes.items():
            prev = old.get(sid) or {}
            moved = [s for s, h in surfaces.items() if prev.get(s) != h]
            if moved:
                out[sid] = sorted(moved)
        return out

    def snapshot(self) -> dict[str, dict[str, str]]:
        return {sid: dict(s) for sid, s in self.hashes.items()}

    def to_doc(self) -> dict[str, Any]:
        return {"surfaces": list(DELTA_SURFACES), "hashes": self.snapshot(),
                "scanned_at": dict(self.scanned_at)}

    @classmethod
    def from_doc(cls, doc: Mapping[str, Any] | None) -> DeltaSet:
        doc = doc or {}
        hashes = {str(k): {str(s): str(h) for s, h in (v or {}).items()}
                  for k, v in (doc.get("hashes") or {}).items() if isinstance(v, Mapping)}
        scanned = {str(k): str(v) for k, v in (doc.get("scanned_at") or {}).items()}
        return cls(hashes=hashes, scanned_at=scanned)


def delta_due(row: Mapping[str, Any], *, now: datetime | None = None) -> bool:
    """A source is due when it was never scanned or its next scan is in the past."""
    nxt = _parse(row.get("next_upstream_delta_scan"))
    return nxt is None or nxt <= (now or datetime.now(tz=UTC))


def delta_stale(row: Mapping[str, Any], *, now: datetime | None = None,
                stale_days: int = DELTA_STALE_DAYS) -> bool | None:
    """True when the last scan is older than `stale_days`; None when never scanned."""
    last = _parse(row.get("last_upstream_delta_scan"))
    if last is None:
        return None
    return last < (now or datetime.now(tz=UTC)) - timedelta(days=stale_days)


# --------------------------------------------------------------------------- the twin
@dataclass(frozen=True)
class TwinArm:
    """One variant's run at a recorded compute cost. Scientific outputs only, never uptime."""

    variant: str
    run_id: str
    compute_s: float
    candidates: int = 0
    unique_candidates: int | None = None
    mechanisms: int = 0
    representations: int = 0
    datasets: int = 0
    effective_trials: int = 0
    forward_survivors: int | None = None

    def scientific_yield(self) -> float:
        """Unique candidates, mechanisms, representations and datasets, plus forward survivors
        at ten times the weight when they are measured -- delayed truth outranks breadth."""
        base = float(self.unique_candidates if self.unique_candidates is not None
                     else self.candidates)
        base += self.mechanisms + self.representations + self.datasets
        if self.forward_survivors is not None:
            base += 10.0 * self.forward_survivors
        return base

    def yield_per_hour(self) -> float | None:
        if self.compute_s <= 0:
            return None
        return self.scientific_yield() / (self.compute_s / 3600.0)


def twin_verdict(system_id: str, native: TwinArm | None, integrated: TwinArm | None, *,
                 compute_tolerance: float = 0.25) -> dict[str, Any]:
    """Native workflow vs integrated variant AT EQUAL COMPUTE (LAWS 5m). If integration makes
    the system worse, the native path stands; a tie also keeps the native path, because "no
    evidence integration helps" is not evidence that it does."""
    rec: dict[str, Any] = {
        "system_id": system_id, "native": asdict(native) if native else None,
        "integrated": asdict(integrated) if integrated else None,
        "verdict": UNMEASURED, "kept": "native", "compute_ratio": None,
        "rule": "native workflow vs integrated variant at equal compute; if integration makes "
                "it worse the native path is kept (LAWS 5m)"}
    if native is None or integrated is None:
        missing = [v for v, arm in (("native", native), ("integrated", integrated)) if arm is None]
        rec["why"] = f"UNMEASURED: no {' and '.join(missing)} run recorded yet"
        return rec
    if native.compute_s <= 0 or integrated.compute_s <= 0:
        rec["why"] = ("UNMEASURED: a run with no recorded compute cannot be compared at equal "
                      "compute")
        return rec
    ratio = integrated.compute_s / native.compute_s
    rec["compute_ratio"] = round(ratio, 4)
    if abs(ratio - 1.0) > compute_tolerance:
        rec["why"] = (f"UNMEASURED: compute differs by {abs(ratio - 1.0):.0%} (tolerance "
                      f"{compute_tolerance:.0%}); not an equal-compute comparison")
        return rec
    yn, yi = native.yield_per_hour(), integrated.yield_per_hour()
    if yn is None or yi is None:
        rec["why"] = "UNMEASURED: yield per hour undefined"
        return rec
    rec["native_yield_per_hour"], rec["integrated_yield_per_hour"] = round(yn, 6), round(yi, 6)
    if yi < yn:
        rec.update(verdict="NATIVE_STANDS", kept="native",
                   why=f"integration makes it worse ({yi:.3f} < {yn:.3f} per hour): the native "
                       f"path is kept")
    elif yi > yn:
        rec.update(verdict="INTEGRATED_BETTER", kept="integrated",
                   why=f"the integrated variant yields more ({yi:.3f} > {yn:.3f} per hour)")
    else:
        rec.update(verdict="TIE", kept="native",
                   why="equal yield at equal compute: no evidence integration helps, native kept")
    return rec


# --------------------------------------------------------------------------- the registry
def _same(a: Any, b: Any) -> bool:
    try:
        return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True,
                                                                        default=str)
    except (TypeError, ValueError):
        return bool(a == b)


def _chain(prev: str, entry: Mapping[str, Any]) -> str:
    body = prev + "|" + json.dumps({k: v for k, v in entry.items() if k != "hash"},
                                   sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]


@dataclass
class Registry:
    """The persisted ExternalResearchSystemRegistry: rows, an append-only hash-chained history
    of every field change, the delta hash set and the benchmark twins."""

    rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    delta: DeltaSet = field(default_factory=DeltaSet)
    twins: dict[str, dict[str, Any]] = field(default_factory=dict)
    at: str = UNMEASURED

    def upsert(self, row: Mapping[str, Any], *, at: str | None = None) -> list[dict[str, Any]]:
        """Merge measured fields into the row; every changed field is one history entry."""
        sid = str(row.get("system_id") or "")
        if not sid:
            raise ValueError("a registry row needs a system_id")
        unknown = sorted(k for k in row if k not in REGISTRY_FIELDS)
        if unknown:
            raise ValueError(f"{unknown} are not registry fields")
        stamp = at or now_iso()
        cur = self.rows.get(sid)
        new = dict(cur) if cur is not None else registry_row(sid)
        changes: list[dict[str, Any]] = []
        if cur is None:
            changes.append({"at": stamp, "system_id": sid, "field": "system_id",
                            "before": None, "after": sid})
            if not measured(row.get("first_seen")):
                new["first_seen"] = stamp
        for k, v in row.items():
            if k == "system_id":
                continue
            if k in VOLATILE_FIELDS:
                new[k] = v
                continue
            if k == "first_seen" and not measured(v):
                continue                        # the stamp of first sight is never unset
            before = new.get(k, UNMEASURED)
            if _same(before, v):
                continue
            new[k] = v
            changes.append({"at": stamp, "system_id": sid, "field": k, "before": before,
                            "after": v})
        for c in changes:
            c["hash"] = _chain(self.history[-1]["hash"] if self.history else "", c)
            self.history.append(c)
        new["updated_at"] = stamp
        self.rows[sid] = new
        return changes

    def history_valid(self) -> tuple[bool, str]:
        """The chain re-derives end to end; a spliced or truncated history does not."""
        prev = ""
        for i, entry in enumerate(self.history):
            if entry.get("hash") != _chain(prev, entry):
                return False, f"history entry {i} does not chain from its predecessor"
            prev = str(entry["hash"])
        return True, "ok"

    def content_hash(self) -> str:
        return content_hash(self.rows)

    def running(self) -> dict[str, dict[str, Any]]:
        return {sid: r for sid, r in self.rows.items()
                if str(r.get("disposition")) in fed.RUNNING_DISPOSITIONS}

    def to_doc(self) -> dict[str, Any]:
        return {"version": 1, "at": self.at, "fields": list(REGISTRY_FIELDS),
                "content_hash": self.content_hash(), "rows": self.rows,
                "history": self.history, "history_rule": "append-only, hash-chained",
                "delta": self.delta.to_doc(), "twins": self.twins,
                "law": "LAWS 5h/5m: REGISTERED, SANDBOXED, SCHEDULED, EXECUTED, PROGRESSED, "
                       "PRODUCED, CONSUMED, ATTRIBUTED; every system delta-scanned; every "
                       "system has a benchmark twin"}

    @classmethod
    def from_doc(cls, doc: Mapping[str, Any]) -> Registry:
        rows = doc.get("rows")
        if not isinstance(rows, Mapping):
            raise ValueError("registry document has no rows mapping")
        reg = cls(rows={str(k): dict(v) for k, v in rows.items() if isinstance(v, Mapping)},
                  history=[dict(h) for h in (doc.get("history") or []) if isinstance(h, Mapping)],
                  delta=DeltaSet.from_doc(doc.get("delta")),
                  twins={str(k): dict(v) for k, v in (doc.get("twins") or {}).items()
                         if isinstance(v, Mapping)},
                  at=str(doc.get("at") or UNMEASURED))
        ok, why = reg.history_valid()
        if not ok:
            raise ValueError(f"registry history is corrupt: {why}")
        return reg

    @classmethod
    def load(cls, path: Path) -> Registry:
        """An absent file is an empty registry; a corrupt one RAISES, because saving over it
        would silently discard an append-only history."""
        if not path.exists():
            return cls()
        return cls.from_doc(json.loads(path.read_text(encoding="utf-8-sig")))

    def save(self, path: Path, *, at: str | None = None) -> Path:
        """Atomic write that REFUSES to shorten or rewrite the history already on disk."""
        if path.exists():
            on_disk = json.loads(path.read_text(encoding="utf-8-sig"))
            prior = [dict(h) for h in (on_disk.get("history") or []) if isinstance(h, Mapping)]
            if len(prior) > len(self.history) or any(
                    p.get("hash") != h.get("hash") for p, h in zip(prior, self.history,
                                                                   strict=False)):
                raise ValueError("registry history is append-only: the history on disk is not "
                                 "a prefix of the one being saved")
        self.at = at or now_iso()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_doc(), indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)
        return path


# --------------------------------------------------------------------------- spawn signals
#: CAPABILITIES, NOT BRANDS: what already-fetched text says a system can do, in the federation's
#: own vocabulary. A keyword is a prior for the fingerprint, never a verdict about the system.
_CAPABILITY_HINTS: tuple[tuple[str, str], ...] = (
    (r"\bmcts\b|monte[- ]carlo tree", "mcts"),
    (r"reinforcement|\brl\b|policy gradient|ppo\b|dqn\b", "rl_policy_search"),
    (r"causal", "causal_discovery"),
    (r"walk[- ]forward|backtest", "walk_forward_harness"),
    (r"execution|order routing|smart order", "execution_engine"),
    (r"microstructure|order book|limit order", "microstructure"),
    (r"data (?:loader|source|feed)|market data|\bapi wrapper\b|akshare|tushare", "data_source"),
    (r"multi[- ]agent|llm agent|agentic", "multi_agent_debate"),
    (r"genetic|evolution|mutation|crossover", "evolutionary_search"),
    (r"symbolic regression", "symbolic_regression"),
    (r"transformer|foundation model|pretrain", "foundation_model"),
    (r"sentiment|\bnlp\b|language model", "financial_nlp"),
    (r"portfolio", "portfolio_research"),
    (r"bayesian optim", "bayesian_optimization"),
    (r"conformal", "conformal_uncertainty"),
    (r"change[- ]?point|regime", "change_point"),
    (r"anomaly", "anomaly_detection"),
    (r"signature|rough path", "rough_paths"),
    (r"copula", "copula_dependence"),
    (r"hawkes|point process", "point_process"),
    (r"graph neural|\bgnn\b", "graph_learning"),
    (r"agent[- ]based|market simulat", "market_simulation"),
    (r"quality[- ]diversity|map[- ]elites", "quality_diversity"),
    (r"prompt optim|dspy", "prompt_optimization"),
    (r"factor (?:mining|model|library)|alpha (?:mining|factory|search)", "dsl_program_search"),
    (r"experiment (?:tracker|scheduler)|hyperparameter", "experiment_scheduler"),
    (r"replication|reproduc", "research_reproduction"),
    (r"verif(?:y|ier|ication)|adversarial review", "independent_verifier"),
    (r"representation learning|embedding", "representation_learning"),
    (r"feature (?:engineering|synthesis|generation)", "feature_synthesis"),
    (r"online learning|streaming", "online_learning"),
    (r"forecast", "forecast_zoo"),
)
_CAPABILITY_AXIS: dict[str, str] = {
    "mcts": "search_algorithm", "rl_policy_search": "search_algorithm",
    "evolutionary_search": "search_algorithm", "dsl_program_search": "hypothesis_language",
    "bayesian_optimization": "search_algorithm", "quality_diversity": "search_algorithm",
    "prompt_optimization": "research_workflow", "experiment_scheduler": "research_workflow",
    "research_reproduction": "research_workflow", "independent_verifier": "adversarial_verifier",
    "causal_discovery": "causal_machinery", "walk_forward_harness": "research_workflow",
    "execution_engine": "execution_method", "microstructure": "execution_method",
    "data_source": "data", "multi_agent_debate": "research_workflow",
    "symbolic_regression": "mathematical_method", "foundation_model": "model_family",
    "financial_nlp": "representation", "portfolio_research": "mathematical_method",
    "conformal_uncertainty": "uncertainty_method", "change_point": "mathematical_method",
    "anomaly_detection": "mathematical_method", "rough_paths": "mathematical_method",
    "copula_dependence": "mathematical_method", "point_process": "mathematical_method",
    "graph_learning": "representation", "market_simulation": "simulation_world",
    "representation_learning": "representation", "feature_synthesis": "representation",
    "online_learning": "search_algorithm", "forecast_zoo": "model_family",
}


def infer_capabilities(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(capabilities, axes) the federation vocabulary can read off already-fetched prose.
    Empty when nothing matches -- which admits as a DUPLICATE with lineage, never as breadth."""
    low = str(text or "").lower()
    caps: list[str] = []
    for pattern, cap in _CAPABILITY_HINTS:
        if cap not in caps and re.search(pattern, low):
            caps.append(cap)
    axes: list[str] = []
    for cap in caps:
        axis = _CAPABILITY_AXIS.get(cap)
        if axis and axis not in axes:
            axes.append(axis)
    return tuple(c for c in caps if c in fed.CAPABILITY_FAMILIES), tuple(
        a for a in axes if a in fed.NEW_AXES)


def system_from_signal(signal: Mapping[str, Any], *, system_id: str,
                       vocabulary: Iterable[str]) -> fed.ExternalSystem:
    """A spawn signal (the `source_civilizations.SPAWN_SIGNALS` contract: signal, kind, name,
    evidence, plus url/region/languages/capabilities) as the ExternalSystem `admit` judges.

    Region + language is a real axis (a Korean data stack over a known topology is the case the
    principal named), so a non-global region adds `region_language` when the text says nothing.
    """
    kind = str(signal.get("signal") or "")
    if kind not in set(vocabulary):
        raise ValueError(f"signal {kind!r} is not a spawn trigger")
    name = str(signal.get("name") or "").strip()
    if not name:
        raise ValueError("a spawn signal with no named entity")
    caps = tuple(str(c) for c in (signal.get("capabilities") or ()))
    axes = tuple(str(a) for a in (signal.get("axes") or ()))
    if not caps:
        caps, inferred = infer_capabilities(
            " ".join(str(signal.get(k) or "") for k in ("name", "evidence", "text", "title")))
        axes = axes or inferred
    region = str(signal.get("region") or "global")
    if region != "global" and "region_language" not in axes:
        axes = (*axes, "region_language")
    return fed.ExternalSystem(
        system_id=system_id, name=name, upstream=str(signal.get("url") or UNMEASURED),
        role=f"spawned by {kind}: {str(signal.get('evidence') or '')[:160]}",
        integration=str(signal.get("integration") or "WRAPPED"),
        capabilities=caps, axes=axes, region=region,
        languages=tuple(str(x) for x in (signal.get("languages") or ("en",))),
        discovery_source=f"spawn_signal:{kind}")


# --------------------------------------------------------------------------- techniques
def technique_survival(created_at: Any, yields: Mapping[str, Any], *,
                       now: datetime | None = None, delay_h: float = TECHNIQUE_DELAY_H
                       ) -> tuple[bool | None, str]:
    """DELAYED yield decides whether a technique transfers. None (UNMEASURED) while younger than
    the delay; True when any measured yield is positive; False when it had its time and yielded
    nothing -- which is a measurement, not a retirement."""
    at = _parse(created_at)
    t = now or datetime.now(tz=UTC)
    if at is None:
        return None, "UNMEASURED: the technique carries no readable creation stamp"
    age_h = (t - at).total_seconds() / 3600.0
    if age_h < delay_h:
        return None, f"UNMEASURED: {age_h:.1f} h old, delayed yield is judged after {delay_h:.0f} h"
    positive = {k: v for k, v in yields.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0}
    if positive:
        return True, "survives on delayed yield " + ", ".join(
            f"{k}={v}" for k, v in sorted(positive.items()))
    return False, f"no yield after {age_h:.0f} h across {sorted(yields)}"


# --------------------------------------------------------------------------- the dashboard
def health_state(row: Mapping[str, Any], stats: Mapping[str, Any], *,
                 now: datetime | None = None) -> str:
    """Scientific state, never uptime. UNDISPOSED/DUPLICATE/REJECTED rows say so; a running row
    is NOT_OPERATIONAL:<first missing term>, STALE (nothing in seven days) or HEALTHY."""
    disp = str(row.get("disposition") or UNMEASURED)
    if disp not in fed.RUNNING_DISPOSITIONS:
        return disp
    ok, missing = fed.operational(_operational_row(row, stats))
    if not ok:
        return f"NOT_OPERATIONAL:{missing[0]}"
    last = _parse(stats.get("last_run_at"))
    if last is None:
        return "NOT_OPERATIONAL:executed"
    if last < (now or datetime.now(tz=UTC)) - timedelta(days=7):
        return "STALE"
    return "HEALTHY"


def _operational_row(row: Mapping[str, Any], stats: Mapping[str, Any]) -> dict[str, bool]:
    runs = stats.get("runs")
    produced = sum(int(stats.get(k) or 0) for k in ("candidates", "mechanisms",
                                                     "representations", "datasets",
                                                     "research_methods"))
    return {
        "registered": (measured(row.get("upstream_repo")) and measured(row.get("commit_version"))
                       and str(row.get("licence")) not in (UNMEASURED, "UNVERIFIED", "")),
        "sandboxed": measured(row.get("sandbox_image_hash")),
        "scheduled": measured(row.get("schedule")),
        "executed": bool(isinstance(runs, (int, float)) and runs > 0),
        "progressed": measured(row.get("progress_watermark")),
        "produced": produced > 0,
        "consumed": bool(measured(row.get("canonical_consumers"))
                         and int(stats.get("consumed") or 0) > 0),
        "attributed": (measured(row.get("forward_survivors"))
                       or measured(row.get("live_portfolio_contribution"))
                       or measured(stats.get("delta_elog"))),
    }


def marginal_roi(row: Mapping[str, Any], stats: Mapping[str, Any]) -> float | None:
    """ROI_s through `external_federation.roi`: (live dElog + information gain) / spend;
    None when nothing was spent or nothing measured."""
    info = stats.get("information_gain")
    return fed.roi({"live_delta_elog": stats.get("delta_elog"),
                    "information_gain": info if isinstance(info, (int, float)) else None,
                    "compute_spent": stats.get("compute_s") or row.get("compute_spent"),
                    "trial_budget_spent": stats.get("effective_trials")})


def _inv(ok: bool | None, measured_value: Any, why: str) -> dict[str, Any]:
    return {"ok": ok, "measured": measured_value, "why": why}


def invariants(rows: Mapping[str, Mapping[str, Any]], stats: Mapping[str, Mapping[str, Any]],
               evidence: Mapping[str, Any], *, now: datetime | None = None
               ) -> dict[str, dict[str, Any]]:
    """The twelve, in order, each {ok, measured, why} in the control plane's own row shape.

    The eight operational terms are judged over every DIRECT/WRAPPED/REBUILT row -- ALL of them,
    because one unprovisioned worker is one folder pretending to be a worker. With no running row
    at all the terms are UNMEASURED (ok=None): the federation has not started, and "not started"
    is the first broken invariant, not a clean one.
    """
    t = now or datetime.now(tz=UTC)
    running = {sid: r for sid, r in rows.items()
               if str(r.get("disposition")) in fed.RUNNING_DISPOSITIONS}
    out: dict[str, dict[str, Any]] = {}
    n_all = len(rows)
    for term in (*fed.OPERATIONAL_TERMS, "attributed"):
        if not running:
            out[term] = _inv(None, {"running_rows": 0, "rows": n_all},
                             f"no DIRECT/WRAPPED/REBUILT row yet ({n_all} rows, none past "
                             f"admission and licence); {term} is UNMEASURED")
            continue
        failing = sorted(sid for sid, r in running.items()
                         if not _operational_row(r, stats.get(sid) or {})[term])
        out[term] = _inv(not failing, {"running_rows": len(running), "failing": failing[:20]},
                         (f"every running row is {term}" if not failing else
                          f"{len(failing)}/{len(running)} running rows are not {term}: "
                          f"{failing[:5]}"))
    donated, recorded = evidence.get("candidates_donated"), evidence.get("candidates_recorded")
    collapsed = int(evidence.get("candidates_collapsed") or 0)
    if not isinstance(donated, int) or not isinstance(recorded, int):
        out["candidate_conservation"] = _inv(None, {"donated": donated, "recorded": recorded},
                                             "UNMEASURED: no packet has donated a candidate yet")
    else:
        balanced = donated == recorded + collapsed
        out["candidate_conservation"] = _inv(
            balanced, {"donated": donated, "recorded": recorded, "collapsed": collapsed},
            ("every donated candidate is recorded or collapsed as a duplicate" if balanced else
             f"{donated} donated != {recorded} recorded + {collapsed} collapsed: a candidate "
             f"vanished between two organs"))
    stranded = evidence.get("stranded")
    if stranded is None:
        out["zero_stranded"] = _inv(None, None, "UNMEASURED: the canonical registry could not be "
                                                "read for capability and dataset routing")
    else:
        rows_s = list(stranded)
        out["zero_stranded"] = _inv(not rows_s, {"stranded": rows_s[:20]},
                                    ("every discovered capability and dataset has a downstream "
                                     "state" if not rows_s else
                                     f"{len(rows_s)} capabilities/datasets have no downstream "
                                     f"state: {rows_s[:5]}"))
    scanned = {sid: delta_stale(r, now=t) for sid, r in rows.items()}
    never = sorted(sid for sid, v in scanned.items() if v is None)
    stale = sorted(sid for sid, v in scanned.items() if v is True)
    if rows and len(never) == len(rows):
        out["delta_scans_fresh"] = _inv(None, {"never_scanned": len(never)},
                                        "UNMEASURED: no upstream delta scan has run yet")
    else:
        bad = stale + never
        out["delta_scans_fresh"] = _inv(
            not bad, {"stale": stale[:20], "never_scanned": never[:20], "rows": n_all},
            ("every system's upstream was delta-scanned inside the freshness window" if not bad
             else f"{len(stale)} stale and {len(never)} never-scanned of {n_all} systems"))
    leaks = evidence.get("verdict_fields_in_canonical")
    if leaks is None:
        out["no_self_validation"] = _inv(None, None, "UNMEASURED: canonical discoveries from "
                                                     "external generators could not be read")
    else:
        n = int(leaks)
        out["no_self_validation"] = _inv(
            n == 0, {"verdict_shaped_fields": n},
            ("no external verdict reached the canonical registry; the gauntlet judges" if n == 0
             else f"{n} canonical rows carry an external verdict-shaped field (LAWS 5h: an "
                  f"engine is a researcher, never a validator)"))
    return {name: out[name] for name in INVARIANTS}


def first_broken(inv: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    """The exact first invariant preventing FEDERATION_CLOSED_AND_HEALTHY = true, or None."""
    for name in INVARIANTS:
        row = inv.get(name) or {}
        if row.get("ok") is not True:
            return {"invariant": name, "ok": row.get("ok"), "measured": row.get("measured"),
                    "why": row.get("why")}
    return None
