"""THE CANONICAL EXPERIMENT OBJECT -- one shape every research civilization compiles into.

THE PRINCIPAL'S ORDER (RD-Agent closure, item 1): *make every one of your research civilizations
behave like one experiment directly changing the next.* That is impossible while a factor lead, a
model idea, a world-miner claim, a physics law, a macro thesis, a country mechanism and a sandbox
hypothesis are seven different dicts with seven different key names. They cannot be compared, they
cannot be graphed against each other, no prior can be updated from them jointly, and no credit can
flow back through them. **This module is the one shape.**

    ExperimentSpec = lineage + data snapshot identity + model + representation + target
                     + state/regime conditioning + costs + falsifier + trial family
                     + novelty axes + status

NO PROSE-ONLY RESEARCH, AND THE DEFECT IS RECORDED RATHER THAN DROPPED. A research row that cannot
compile -- no instrument, no family, no falsifier, no data it would be measured on -- is not
silently skipped and is not quietly enqueued as a half-thing either. `compile_row` returns a
`CompileDefect` naming the reason and the missing fields, and the sweep that calls it writes those
into the conversion-debt report. A row of beautiful prose about the Bank of Japan that names no
instrument is a DEFECT with the reason `PROSE_ONLY`, and the desk's standing law is that
conversion debt goes to zero: either the row is enriched until it compiles, or its blocker is
named. Silence was the old behaviour and it is what made the world-miner's output unauditable.

THE CONSTRUCTORS ARE THE WIRING. `from_discovery` takes a registry `discoveries` row (what every
miner, forest, deep-forest crawl and country pack already writes through
`registry.record_discovery`), `from_candidate` a `research_candidates` row, `from_claim` a raw
claim/lead mapping from an organ that has not reached the registry yet (a compiler artifact row, a
`mine()` output, a transmission edge). All three produce the same object, so an experiment's
ancestry is comparable whatever civilization produced it.

`to_campaign()` produces the registry candidate -- the kwargs for
`libs.moat.registry.enqueue_candidate` -- with full provenance: parents, source, discovery id,
generator, method, trial family, falsifier, the data snapshot's hash and the novelty axes. `enqueue`
calls it and links `experiment -> cell` in the provenance DAG so credit can walk back.

STABILITY CONTRACT (a second builder owns the coevolution half and imports this): the names
`ExperimentSpec`, `DataSnapshot`, `CompileDefect`, `KINDS`, `compile_row`, `from_discovery`,
`from_candidate`, `from_claim`, `to_campaign`, `enqueue`, `spec_hash` are stable. Fields are ADDED
with defaults, never renamed or removed.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: What kind of research object this experiment came from. One vocabulary for every civilization.
KINDS: tuple[str, ...] = (
    "factor", "model", "world_lead", "physics_law", "macro_idea", "country_mechanism",
    "sandbox_hypothesis", "execution_rule", "residual", "unknown",
)

#: An experiment's life. PROPOSED -> QUEUED -> RUNNING -> JUDGED(survived|rejected) -> FORWARD
#: -> LIVE, or BLOCKED with a reason. RETIRED is a terminal state a survivor can reach later.
STATUSES: tuple[str, ...] = (
    "PROPOSED", "QUEUED", "RUNNING", "JUDGED", "SURVIVED", "REJECTED", "FORWARD", "LIVE",
    "BLOCKED", "RETIRED",
)

#: The compile contract: without these an experiment is not an experiment, it is a sentence.
REQUIRED_FIELDS: tuple[str, ...] = ("symbols", "family", "target", "falsifier", "data_snapshot")

#: Why a row failed to compile. Every defect carries one of these plus the field list.
DEFECT_REASONS: tuple[str, ...] = (
    "PROSE_ONLY",          # text about a mechanism naming no instrument and no rule
    "NO_INSTRUMENT",       # a rule and a family, but nothing to run it on
    "NO_FAMILY",           # an instrument and prose, but no testable family/model
    "NO_FALSIFIER",        # untestable by construction (LAWS 5k: a claim needs a falsifier)
    "NO_DATA",             # nothing names the data it would be measured on
    "OFF_UNIVERSE",        # a crypto-exchange-native row (mandate 2026-08-18)
    "UNREADABLE",          # the row is not a mapping / not parseable
)

#: Crypto-exchange venues the universe mandate bans from being hunted (2026-08-18). A row whose
#: instruments are exchange-native is a defect with a NAMED reason, never a silent drop.
_BANNED_VENUES: tuple[str, ...] = ("binance", "bybit", "okx", "hyperliquid", "deribit", "kraken",
                                   "coinbase", "bitmex", "kucoin", "gate.io", "huobi")

#: The default target when a row names a mechanism and a horizon but not the quantity predicted.
#: NOT invented out of nothing: a directional return over the row's own declared horizon is what
#: every family in this desk's grammar actually predicts, and it is stamped as `derived` so a
#: reader can tell it from a target the source named.
DEFAULT_TARGET = "forward_return"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _loads(value: Any) -> Any:
    """A registry column that may hold JSON text, a python object, or the string 'None'."""
    if value is None or value == "" or value == "None":
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _strs(value: Any) -> tuple[str, ...]:
    v = _loads(value)
    if v is None:
        return ()
    if isinstance(v, str):
        return (v,) if v else ()
    if isinstance(v, Mapping):
        return tuple(str(k) for k in v)
    if isinstance(v, Sequence):
        return tuple(str(x) for x in v if str(x))
    return (str(v),)


def _text(value: Any) -> str:
    v = _loads(value)
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return json.dumps(v, sort_keys=True, default=str)


def _fl(value: Any) -> float | None:
    try:
        return None if value is None or value == "None" else float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class DataSnapshot:
    """THE DATA IDENTITY AN EXPERIMENT WAS RUN AGAINST -- PIT vintage plus a hash.

    Two experiments that disagree are only comparable if they saw the same data, and the desk has
    been unable to say that: a candidate recorded its `required_data` and never the VINTAGE of the
    files it actually read. `vintage` is the as-of stamp (the snapshot date the run may see up
    to); `datasets` the declared inputs; `pit_status` the point-in-time discipline they are held
    under; `snapshot_hash` the content identity of the triple, which is what the graph joins on.
    """

    vintage: str = ""
    datasets: tuple[str, ...] = ()
    pit_status: str = "UNMEASURED"
    snapshot_hash: str = ""

    def resolved(self) -> DataSnapshot:
        """The same snapshot with its hash filled in; identity is derived, never supplied."""
        if self.snapshot_hash:
            return self
        h = _sha({"vintage": self.vintage, "datasets": sorted(self.datasets),
                  "pit": self.pit_status})[:32]
        return replace(self, snapshot_hash=h)

    def to_dict(self) -> dict[str, Any]:
        d = self.resolved()
        return {"vintage": d.vintage, "datasets": list(d.datasets), "pit_status": d.pit_status,
                "snapshot_hash": d.snapshot_hash}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any] | None) -> DataSnapshot:
        if not isinstance(d, Mapping):
            return cls()
        return cls(vintage=str(d.get("vintage") or ""),
                   datasets=_strs(d.get("datasets")),
                   pit_status=str(d.get("pit_status") or "UNMEASURED"),
                   snapshot_hash=str(d.get("snapshot_hash") or "")).resolved()


@dataclass(frozen=True)
class CompileDefect:
    """A research row that could NOT become an experiment, and exactly why.

    This is the recorded defect the mandate demands. It carries the row's own id so the organ that
    wrote it can be told, the reason from `DEFECT_REASONS`, the missing fields, and the source and
    generator so the conversion-debt report can rank blockers by who produces them.
    """

    row_id: str
    kind: str
    reason: str
    missing: tuple[str, ...] = ()
    source: str = ""
    generator: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"row_id": self.row_id, "kind": self.kind, "reason": self.reason,
                "missing": list(self.missing), "source": self.source,
                "generator": self.generator, "detail": self.detail}


@dataclass(frozen=True)
class ExperimentSpec:
    """ONE experiment, whatever civilization proposed it.

    Every field is either measured from the row or explicitly absent; nothing is invented. The
    only derived value is `target`, which falls back to `DEFAULT_TARGET` with `target_basis`
    saying so, because a family that predicts nothing is not a family.
    """

    experiment_id: str
    kind: str = "unknown"
    # ---- lineage -------------------------------------------------------------------------
    parents: tuple[str, ...] = ()
    children: tuple[str, ...] = ()
    method: str = ""            # the operator / search method that produced it
    source: str = ""            # source_id, url or organ that carries the claim
    generator: str = ""         # the miner / seat / engine that emitted the row
    origin: str = ""            # DESK | EXTERNAL | MOAT -- the registry's own vocabulary
    discovery_id: str = ""
    # ---- data ----------------------------------------------------------------------------
    data_snapshot: DataSnapshot = field(default_factory=DataSnapshot)
    # ---- model and representation --------------------------------------------------------
    model: str = ""
    model_params: Mapping[str, Any] = field(default_factory=dict)
    features: tuple[str, ...] = ()
    representation: str = ""
    # ---- what it predicts ----------------------------------------------------------------
    family: str = ""
    symbols: tuple[str, ...] = ()
    target: str = DEFAULT_TARGET
    target_basis: str = "derived"
    horizon: str = ""
    chart: str = ""
    # ---- state / regime conditioning -----------------------------------------------------
    regime: str = ""
    session: str = ""
    state_conditions: Mapping[str, Any] = field(default_factory=dict)
    # ---- economics -----------------------------------------------------------------------
    costs: Mapping[str, Any] = field(default_factory=dict)
    # ---- science -------------------------------------------------------------------------
    mechanism: str = ""
    economic_actor: str = ""
    falsifier: str = ""
    trial_family: str = ""
    novelty_axes: Mapping[str, Any] = field(default_factory=dict)
    # ---- bookkeeping ---------------------------------------------------------------------
    status: str = "PROPOSED"
    created_at: str = field(default_factory=_now)
    notes: str = ""

    # ---------------------------------------------------------------- identity / serialisation
    def content(self) -> dict[str, Any]:
        """The fields that make this experiment THIS experiment (identity, not bookkeeping)."""
        return {"kind": self.kind, "family": self.family, "symbols": sorted(self.symbols),
                "model": self.model, "representation": self.representation,
                "features": sorted(self.features), "target": self.target,
                "horizon": self.horizon, "chart": self.chart, "regime": self.regime,
                "session": self.session, "params": dict(self.model_params),
                "snapshot": self.data_snapshot.resolved().snapshot_hash}

    def spec_hash(self) -> str:
        return _sha(self.content())[:32]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["data_snapshot"] = self.data_snapshot.to_dict()
        d["parents"] = list(self.parents)
        d["children"] = list(self.children)
        d["features"] = list(self.features)
        d["symbols"] = list(self.symbols)
        d["model_params"] = dict(self.model_params)
        d["state_conditions"] = dict(self.state_conditions)
        d["costs"] = dict(self.costs)
        d["novelty_axes"] = dict(self.novelty_axes)
        d["spec_hash"] = self.spec_hash()
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ExperimentSpec:
        return cls(
            experiment_id=str(d.get("experiment_id") or ""),
            kind=str(d.get("kind") or "unknown"),
            parents=_strs(d.get("parents")), children=_strs(d.get("children")),
            method=str(d.get("method") or ""), source=str(d.get("source") or ""),
            generator=str(d.get("generator") or ""), origin=str(d.get("origin") or ""),
            discovery_id=str(d.get("discovery_id") or ""),
            data_snapshot=DataSnapshot.from_dict(d.get("data_snapshot")),
            model=str(d.get("model") or ""),
            model_params=dict(_loads(d.get("model_params")) or {}),
            features=_strs(d.get("features")),
            representation=str(d.get("representation") or ""),
            family=str(d.get("family") or ""), symbols=_strs(d.get("symbols")),
            target=str(d.get("target") or DEFAULT_TARGET),
            target_basis=str(d.get("target_basis") or "derived"),
            horizon=str(d.get("horizon") or ""), chart=str(d.get("chart") or ""),
            regime=str(d.get("regime") or ""), session=str(d.get("session") or ""),
            state_conditions=dict(_loads(d.get("state_conditions")) or {}),
            costs=dict(_loads(d.get("costs")) or {}),
            mechanism=str(d.get("mechanism") or ""),
            economic_actor=str(d.get("economic_actor") or ""),
            falsifier=str(d.get("falsifier") or ""),
            trial_family=str(d.get("trial_family") or ""),
            novelty_axes=dict(_loads(d.get("novelty_axes")) or {}),
            status=str(d.get("status") or "PROPOSED"),
            created_at=str(d.get("created_at") or _now()),
            notes=str(d.get("notes") or ""))

    # ------------------------------------------------------------------------ the campaign row
    def to_campaign(self) -> dict[str, Any]:
        """The registry candidate this experiment enqueues as, with full provenance.

        The keys are `libs.moat.registry.enqueue_candidate`'s own argument names, so the caller
        does `registry.enqueue_candidate(**spec.to_campaign())` and nothing here has to know the
        registry's column layout. Everything the credit walk needs to reach the ancestor -- the
        source, the discovery, the generator, the method and the parents -- travels with it.
        """
        snap = self.data_snapshot.resolved()
        params = {**dict(self.model_params)}
        if self.model:
            params.setdefault("model", self.model)
        if self.representation:
            params.setdefault("representation", self.representation)
        return {
            "family": self.family or self.kind,
            "symbol": self.symbols[0] if self.symbols else "",
            "params": params,
            "origin": self.origin or "DESK",
            "mechanism": self.mechanism,
            "candidate_id": f"exp_{self.spec_hash()}",
            "status": "queued",
            # provenance and the science contract
            "parent_ids": list(self.parents),
            "discovery_id": self.discovery_id,
            "source_id": self.source,
            "generator": self.generator or self.method,
            "transformation": self.method,
            "economic_actor": self.economic_actor,
            "causal_rationale": self.notes,
            "chart": self.chart, "session": self.session, "horizon": self.horizon,
            "regime": self.regime,
            "required_data": list(snap.datasets),
            "pit_status": snap.pit_status,
            "falsifier": self.falsifier,
            "trial_family": self.trial_family or self.family or self.kind,
            "information": self.representation,
            "lineage": {"experiment_id": self.experiment_id, "spec_hash": self.spec_hash(),
                        "kind": self.kind, "method": self.method,
                        "snapshot_hash": snap.snapshot_hash, "target": self.target,
                        "model": self.model, "representation": self.representation,
                        "features": list(self.features), "parents": list(self.parents)},
            **{k: v for k, v in (
                ("expected_costs", _fl(self.costs.get("expected_costs"))),
                ("expected_capacity", _fl(self.costs.get("expected_capacity"))),
                ("novelty_vs_live", _fl(self.novelty_axes.get("vs_live"))),
                ("novelty_vs_graveyard", _fl(self.novelty_axes.get("vs_graveyard"))),
                ("p_edge", _fl(self.novelty_axes.get("p_edge"))),
                ("mechanism_strength", _fl(self.novelty_axes.get("mechanism_strength"))),
                ("data_quality", _fl(self.novelty_axes.get("data_quality"))),
            ) if v is not None},
        }


# ------------------------------------------------------------------------------- constructors
def _snapshot_from(row: Mapping[str, Any], *, vintage: str = "") -> DataSnapshot:
    datasets = _strs(row.get("required_data_json") or row.get("required_data")
                     or row.get("datasets") or row.get("data"))
    pit = _text(row.get("pit_status") or row.get("pit_requirements_json")
                or row.get("PIT_requirements") or row.get("pit")) or "UNMEASURED"
    stamp = (vintage or _text(row.get("data_vintage")) or _text(row.get("as_of"))
             or _text(row.get("updated_at")) or _text(row.get("created_at")))
    return DataSnapshot(vintage=stamp, datasets=datasets, pit_status=pit).resolved()


def _off_universe(symbols: Sequence[str], text: str) -> bool:
    blob = " ".join([*symbols, text]).lower()
    return any(v in blob for v in _BANNED_VENUES)


def _defect(row_id: str, kind: str, reason: str, missing: Sequence[str], row: Mapping[str, Any],
            detail: str = "") -> CompileDefect:
    return CompileDefect(row_id=row_id, kind=kind, reason=reason, missing=tuple(missing),
                         source=str(row.get("source_id") or row.get("source") or ""),
                         generator=str(row.get("generator") or row.get("producer") or ""),
                         detail=detail)


def _finish(spec: ExperimentSpec, row: Mapping[str, Any],
            row_id: str) -> ExperimentSpec | CompileDefect:
    """The compile contract, applied once for every constructor."""
    missing = [f for f in REQUIRED_FIELDS
               if not getattr(spec, f, None)
               or (f == "data_snapshot" and not spec.data_snapshot.datasets)]
    if _off_universe(spec.symbols, f"{spec.mechanism} {spec.source}"):
        return _defect(row_id, spec.kind, "OFF_UNIVERSE", missing, row,
                       "crypto-exchange-native row; the MT5/Fusion mandate (2026-08-18) forbids "
                       "hunting this ground")
    if not spec.symbols and not spec.family:
        return _defect(row_id, spec.kind, "PROSE_ONLY", missing, row,
                       "the row carries a mechanism in prose and names neither an instrument nor "
                       "a testable family")
    if not spec.symbols:
        return _defect(row_id, spec.kind, "NO_INSTRUMENT", missing, row,
                       "a family with nothing to run it on")
    if not spec.family:
        return _defect(row_id, spec.kind, "NO_FAMILY", missing, row,
                       "an instrument with no testable family or model")
    if not spec.falsifier:
        return _defect(row_id, spec.kind, "NO_FALSIFIER", missing, row,
                       "LAWS 5k: a claim with no falsifier is not an experiment")
    if not spec.data_snapshot.datasets:
        return _defect(row_id, spec.kind, "NO_DATA", missing, row,
                       "nothing names the data this would be measured on")
    return spec


def from_discovery(row: Mapping[str, Any], *, kind: str = "",
                   vintage: str = "") -> ExperimentSpec | CompileDefect:
    """A registry `discoveries` row -> one ExperimentSpec (or the defect that stopped it)."""
    if not isinstance(row, Mapping):
        return CompileDefect(row_id="?", kind="unknown", reason="UNREADABLE",
                             detail=f"{type(row).__name__} is not a mapping")
    did = str(row.get("discovery_id") or row.get("id") or "")
    src_type = str(row.get("source_type") or "")
    k = kind or _kind_of(src_type, str(row.get("generator") or ""))
    payload = _loads(row.get("payload_json")) or {}
    payload = payload if isinstance(payload, Mapping) else {}
    rule = _loads(row.get("exact_rule") or row.get("exact_rule_if_known"))
    params = rule if isinstance(rule, Mapping) else {}
    horizons = _strs(row.get("horizons_json") or row.get("horizons"))
    sessions = _strs(row.get("sessions_json") or row.get("sessions"))
    regimes = _strs(row.get("regimes_json") or row.get("regimes"))
    spec = ExperimentSpec(
        experiment_id=f"exp_{did}" if did else "",
        kind=k,
        parents=_strs(row.get("parent_ids_json") or row.get("parent_ids")),
        method=str(row.get("generator") or row.get("origin") or ""),
        source=str(row.get("source_id") or ""),
        generator=str(row.get("generator") or ""),
        origin=str(row.get("origin") or ""),
        discovery_id=did,
        data_snapshot=_snapshot_from(row, vintage=vintage),
        model=str(payload.get("model") or ""),
        model_params=params if isinstance(params, Mapping) else {},
        features=_strs(payload.get("features")),
        representation=str(row.get("information") or payload.get("representation") or ""),
        family=str(payload.get("family") or row.get("mechanism_id") or
                   (str(rule) if isinstance(rule, str) and rule else "") or
                   _family_from_mechanism(str(row.get("mechanism") or ""))),
        symbols=_strs(row.get("assets_json") or row.get("assets")),
        target=str(payload.get("target") or DEFAULT_TARGET),
        target_basis="declared" if payload.get("target") else "derived",
        horizon=horizons[0] if horizons else "",
        chart=str(payload.get("chart") or ""),
        regime=regimes[0] if regimes else "",
        session=sessions[0] if sessions else "",
        state_conditions={"regimes": list(regimes), "sessions": list(sessions)},
        costs={"expected_costs": _fl(payload.get("expected_cost")),
               "expected_capacity": _fl(payload.get("expected_capacity"))},
        mechanism=str(row.get("mechanism") or ""),
        economic_actor=str(row.get("actor") or ""),
        falsifier=_text(row.get("falsifier")),
        trial_family=str(row.get("mechanism_id") or row.get("source_type") or ""),
        novelty_axes={"vs_live": _fl(row.get("novelty")),
                      "p_edge": _fl(row.get("confidence"))},
        status="BLOCKED" if str(row.get("state")) == "BLOCKED" else "PROPOSED",
        notes=_text(row.get("economic_rationale")),
    )
    return _finish(spec, row, did or "?")


def from_candidate(row: Mapping[str, Any], *,
                   vintage: str = "") -> ExperimentSpec | CompileDefect:
    """A registry `research_candidates` row -> one ExperimentSpec."""
    if not isinstance(row, Mapping):
        return CompileDefect(row_id="?", kind="unknown", reason="UNREADABLE",
                             detail=f"{type(row).__name__} is not a mapping")
    cid = str(row.get("id") or row.get("candidate_id") or "")
    lineage = _loads(row.get("lineage_json")) or {}
    lineage = lineage if isinstance(lineage, Mapping) else {}
    params = _loads(row.get("params_json") or row.get("params")) or {}
    params = params if isinstance(params, Mapping) else {}
    spec = ExperimentSpec(
        experiment_id=str(lineage.get("experiment_id") or (f"exp_{cid}" if cid else "")),
        kind=str(lineage.get("kind") or _kind_of(str(row.get("origin") or ""),
                                                 str(row.get("generator") or ""))),
        parents=_strs(row.get("parent_ids_json") or row.get("parent_ids")),
        method=str(lineage.get("method") or row.get("transformation") or ""),
        source=str(row.get("source_id") or ""),
        generator=str(row.get("generator") or ""),
        origin=str(row.get("origin") or ""),
        discovery_id=str(row.get("discovery_id") or ""),
        data_snapshot=_snapshot_from(row, vintage=vintage),
        model=str(lineage.get("model") or params.get("model") or ""),
        model_params={k: v for k, v in params.items() if k not in ("model", "representation")},
        features=_strs(lineage.get("features")),
        representation=str(lineage.get("representation") or params.get("representation")
                           or row.get("information") or ""),
        family=str(row.get("family") or ""),
        symbols=_strs(row.get("symbol")),
        target=str(lineage.get("target") or DEFAULT_TARGET),
        target_basis="declared" if lineage.get("target") else "derived",
        horizon=str(row.get("horizon") or ""), chart=str(row.get("chart") or ""),
        regime=str(row.get("regime") or ""), session=str(row.get("session") or ""),
        costs={"expected_costs": _fl(row.get("expected_costs")),
               "expected_capacity": _fl(row.get("expected_capacity"))},
        mechanism=str(row.get("mechanism") or ""),
        economic_actor=str(row.get("economic_actor") or ""),
        falsifier=_text(row.get("falsifier")),
        trial_family=str(row.get("trial_family") or row.get("family") or ""),
        novelty_axes={"vs_live": _fl(row.get("novelty_vs_live")),
                      "vs_graveyard": _fl(row.get("novelty_vs_graveyard")),
                      "p_edge": _fl(row.get("p_edge")),
                      "mechanism_strength": _fl(row.get("mechanism_strength")),
                      "data_quality": _fl(row.get("data_quality"))},
        status=_status_of(str(row.get("status") or "")),
        notes=_text(row.get("causal_rationale")),
    )
    return _finish(spec, row, cid or "?")


def from_claim(row: Mapping[str, Any], *, kind: str = "world_lead", source: str = "",
               generator: str = "", vintage: str = "") -> ExperimentSpec | CompileDefect:
    """A raw claim / lead / artifact row from an organ that has not reached the registry yet.

    This is the constructor the conversion sweep uses on the compilers' own artifacts (the
    discovery compiler's mechanism rows, the miner candidate compiler's hypotheses, the merged
    docket, a transmission edge, a country pack's `mine()` output). It reads the union of the
    key names those organs actually write, and names a defect for anything it cannot.
    """
    if not isinstance(row, Mapping):
        return CompileDefect(row_id="?", kind=kind, reason="UNREADABLE",
                             detail=f"{type(row).__name__} is not a mapping")
    rid = str(row.get("id") or row.get("claim_id") or row.get("cell") or row.get("key")
              or row.get("name") or _sha(dict(row))[:16])
    params = _loads(row.get("params") or row.get("parameters") or row.get("exact_rule")) or {}
    symbols = _strs(row.get("symbols") or row.get("instruments") or row.get("assets")
                    or row.get("symbol") or row.get("instrument"))
    horizons = _strs(row.get("horizons") or row.get("horizon"))
    spec = ExperimentSpec(
        experiment_id=f"exp_{_sha({'rid': rid, 'src': source})[:24]}",
        kind=kind,
        parents=_strs(row.get("parents") or row.get("parent_ids")),
        method=str(row.get("method") or row.get("transformation") or generator or ""),
        source=str(row.get("source_id") or row.get("source") or row.get("url") or source),
        generator=str(row.get("generator") or row.get("producer") or generator),
        origin=str(row.get("origin") or "DESK"),
        discovery_id=str(row.get("discovery_id") or ""),
        data_snapshot=_snapshot_from(row, vintage=vintage),
        model=str(row.get("model") or ""),
        model_params=params if isinstance(params, Mapping) else {},
        features=_strs(row.get("features")),
        representation=str(row.get("representation") or row.get("information") or ""),
        family=str(row.get("family") or row.get("mechanism_family") or ""),
        symbols=symbols,
        target=str(row.get("target") or DEFAULT_TARGET),
        target_basis="declared" if row.get("target") else "derived",
        horizon=horizons[0] if horizons else "",
        chart=str(row.get("chart") or row.get("timeframe") or ""),
        regime=str(row.get("regime") or ""), session=str(row.get("session") or ""),
        state_conditions=dict(_loads(row.get("state_conditions")) or {}),
        costs={"expected_costs": _fl(row.get("expected_costs") or row.get("expected_cost")),
               "expected_capacity": _fl(row.get("expected_capacity"))},
        mechanism=_text(row.get("mechanism") or row.get("claim") or row.get("text")),
        economic_actor=str(row.get("actor") or row.get("economic_actor") or ""),
        falsifier=_text(row.get("falsifier")),
        trial_family=str(row.get("trial_family") or row.get("family") or ""),
        novelty_axes={"vs_live": _fl(row.get("novelty")),
                      "p_edge": _fl(row.get("confidence") or row.get("p_edge"))},
        notes=_text(row.get("economic_rationale") or row.get("rationale")),
    )
    return _finish(spec, row, rid)


def compile_row(row: Any, *, kind: str = "", source: str = "", generator: str = "",
                vintage: str = "") -> ExperimentSpec | CompileDefect:
    """The one door. Routes a row to the right constructor by the keys it carries."""
    if not isinstance(row, Mapping):
        return CompileDefect(row_id="?", kind=kind or "unknown", reason="UNREADABLE",
                             detail=f"{type(row).__name__} is not a mapping")
    if row.get("discovery_id") and row.get("source_type") is not None:
        return from_discovery(row, kind=kind, vintage=vintage)
    if row.get("content_hash") is not None and row.get("grid_cell") is not None:
        return from_candidate(row, vintage=vintage)
    return from_claim(row, kind=kind or "world_lead", source=source, generator=generator,
                      vintage=vintage)


def _kind_of(source_type: str, generator: str) -> str:
    """Which civilization this row came from, from the vocabulary the desk already writes."""
    blob = f"{source_type} {generator}".lower()
    table: tuple[tuple[str, str], ...] = (
        ("physics", "physics_law"), ("math", "factor"), ("expression", "factor"),
        ("factor", "factor"), ("residual", "residual"),
        ("model", "model"), ("ml_", "model"), ("league", "model"),
        ("execution", "execution_rule"), ("tape", "execution_rule"),
        ("macro", "macro_idea"), ("fred", "macro_idea"), ("event", "macro_idea"),
        ("sandbox", "sandbox_hypothesis"),
        # THE ORDER IS THE ROUTING and it is not cosmetic: `deep_forest_miner` contains both
        # "deep_forest" and "forest", and the deep forest is a WORLD lead (a forum claim), not a
        # country pack. The longer, more specific token is matched first.
        ("deep_forest", "world_lead"), ("forum", "world_lead"), ("crawl", "world_lead"),
        ("web", "world_lead"), ("claim", "world_lead"), ("thread", "world_lead"),
        ("forest", "country_mechanism"), ("country", "country_mechanism"),
        ("korea", "country_mechanism"), ("japan", "country_mechanism"),
        ("china", "country_mechanism"),
    )
    for needle, k in table:
        if needle in blob:
            return k
    return "unknown"


def _family_from_mechanism(text: str) -> str:
    """A mechanism sentence carries its family when the desk's compiler wrote it as
    `<family> on <thing> -> <action>`; otherwise there is no family and the row is a defect."""
    head = text.split(" on ", 1)[0].strip()
    if head and " " not in head and head.replace("_", "").isalnum():
        return head
    return ""


def _status_of(registry_status: str) -> str:
    table = {"queued": "QUEUED", "claimed": "RUNNING", "donated": "QUEUED",
             "judged": "JUDGED", "survived": "SURVIVED", "rejected": "REJECTED",
             "live": "LIVE", "forward": "FORWARD", "retired": "RETIRED"}
    return table.get(registry_status.lower(), "PROPOSED")


def enqueue(spec: ExperimentSpec, *, conn: sqlite3.Connection | None = None) -> tuple[str, bool]:
    """Put the experiment on the CampaignQueue and link `experiment -> cell` in the DAG.

    Returns `(candidate_id, created)` exactly as `registry.enqueue_candidate` does, so a caller
    can count new work against re-proposals without a second query.
    """
    from libs.moat import registry

    cid, created = registry.enqueue_candidate(conn=conn, **spec.to_campaign())
    try:
        registry.link("experiment", spec.experiment_id, "cell", cid, "compiled", conn=conn)
        if spec.discovery_id:
            registry.link("discovery", spec.discovery_id, "experiment", spec.experiment_id,
                          "compiled", conn=conn)
        for p in spec.parents:
            registry.link("experiment", p, "experiment", spec.experiment_id, "derived", conn=conn)
    except (ValueError, sqlite3.Error):
        # The provenance edge is the credit path, not the queue. A registry that cannot take the
        # edge (an older schema without the `experiment` kind) must not lose the candidate.
        pass
    return cid, created
