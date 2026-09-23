"""THE ALPHA GENOME: one identity for a strategy, whatever shape it is wearing.

MEASURED 2026-09-08 (Tier-1 programme item A1): four incompatible records describe the same
strategy at different stages -- the compiler's 8-field candidate, the gauntlet's 8-field
certificate row, the hypothesis graph's 11-field node and the 22-field StrategyArtifact -- and
only the last is ever built, only from certificates. A candidate that failed the gauntlet has no
artifact; a graph node has no certificate; a certificate carries `sym` where a candidate carries
`symbol`. Nothing joins them, so "follow hypothesis X from source to deal" (acceptance property
AP3) breaks at the first hand-off.

WHAT THIS IS NOT. Not a fifth shape. The four records stay exactly as they are -- each is the
right shape for the organ that writes it -- and every one of them already contains the three
fields that define a strategy: symbol, family, params. `genome_id` is the sha of those three,
computed by ONE function (the graph's `node_id`, imported, never re-spelled), so every record can
be stamped with the same id at birth and the chain is a join on one key rather than a matcher.

`AlphaGenome` is the READ view: `from_any(record)` sniffs which shape it was handed and returns
the same normalised object, so a consumer walking the funnel never learns four vocabularies.
`stamp(record)` writes `genome_id` into a record in place and returns it -- the producers call
this at the point they build their row, which is the whole change needed at each pen.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from libs.research.hypothesis_graph import node_id

#: The stage a record's shape implies. The order is the funnel's order.
STAGES = ("CANDIDATE", "NODE", "CERTIFICATE", "ARTIFACT")


def genome_id(symbol: str, family: str, params: dict[str, Any] | None) -> str:
    """The one identity. `node_id` upper-cases the symbol and sorts the params, so a certificate
    spelling `sym: "xauusd"` and a candidate spelling `symbol: "XAUUSD"` agree."""
    return node_id(str(symbol or ""), str(family or ""), dict(params or {}))


@dataclass
class AlphaGenome:
    genome_id: str
    symbol: str
    family: str
    params: dict[str, Any]
    stage: str
    source: str = ""
    mechanism: str = ""
    parent: str = ""
    fate: str = ""
    gates: dict[str, Any] = field(default_factory=dict)
    certificate: dict[str, Any] = field(default_factory=dict)
    origin: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def shape_of(rec: dict[str, Any]) -> str | None:
    """Which of the four records this is, by the fields only that shape carries."""
    if not isinstance(rec, dict):
        return None
    if "strategy_id" in rec and "validation_certificate" in rec:
        return "ARTIFACT"
    if "gates" in rec and ("sym" in rec or "shadow_spec" in rec or "cell" in rec):
        return "CERTIFICATE"
    if "fate" in rec and "family" in rec:
        return "NODE"
    if "family" in rec and ("symbol" in rec or "symbols" in rec):
        return "CANDIDATE"
    return None


def from_candidate(c: dict[str, Any]) -> AlphaGenome:
    sym = c.get("symbol") or (c.get("symbols") or [""])[0]
    return AlphaGenome(
        genome_id=genome_id(sym, c.get("family", ""), c.get("params")),
        symbol=str(sym).upper(), family=str(c.get("family") or ""),
        params=dict(c.get("params") or {}), stage="CANDIDATE",
        source=str(c.get("source") or ""), mechanism=str(c.get("mechanism_note") or ""),
        origin={"source_url": c.get("source_url"), "source_title": c.get("source_title"),
                "n_independent_sources": c.get("n_independent_sources")})


def from_node(n: dict[str, Any]) -> AlphaGenome:
    return AlphaGenome(
        genome_id=genome_id(n.get("symbol", ""), n.get("family", ""), n.get("params")),
        symbol=str(n.get("symbol") or "").upper(), family=str(n.get("family") or ""),
        params=dict(n.get("params") or {}), stage="NODE", source=str(n.get("source") or ""),
        parent=str(n.get("parent") or ""), fate=str(n.get("fate") or ""),
        gates=dict(n.get("gates") or {}), origin={"why": n.get("why"), "at": n.get("at")})


def from_certificate(c: dict[str, Any]) -> AlphaGenome:
    spec = c.get("shadow_spec") or {}
    sym = c.get("sym") or spec.get("symbol") or ""
    fam = spec.get("family") or c.get("family") or ""
    params = spec.get("params") if spec.get("params") is not None else c.get("params")
    unrunnable = bool(spec) and spec.get("params") is None
    # AN UNRUNNABLE CERTIFICATE HAS NO PARAMETERISATION, and `{}` is not "unknown" -- it is the
    # complete parameterisation "family defaults" (see build_zentech_state._certificate_census).
    # Hashing the unknown as {} would join a certificate nothing can run onto the defaults
    # genome, so it gets an identity of its own, keyed on the cell the gauntlet named.
    id_params = {"__unrunnable_cell__": c.get("cell")} if unrunnable else params
    _raw_gates = c.get("gates")
    _gates: dict[str, Any] = (_raw_gates if isinstance(_raw_gates, dict)
                              else {"stages": _raw_gates})
    return AlphaGenome(
        genome_id=genome_id(sym, fam, id_params), symbol=str(sym).upper(), family=str(fam),
        params=dict(params or {}), stage="CERTIFICATE",
        source=str(c.get("hunt") or spec.get("hunt") or ""),
        mechanism=str(c.get("mechanism") or c.get("hypothesis") or ""),
        gates=_gates,
        certificate={"cell": c.get("cell"), "days": c.get("days"), "gated_at": c.get("gated_at"),
                     "status": c.get("status"), "unrunnable": unrunnable})


def from_artifact(a: dict[str, Any]) -> AlphaGenome:
    sym = (a.get("symbols") or [""])[0]
    return AlphaGenome(
        genome_id=genome_id(sym, a.get("family", ""), a.get("params")),
        symbol=str(sym).upper(), family=str(a.get("family") or ""),
        params=dict(a.get("params") or {}), stage="ARTIFACT", source=str(a.get("source") or ""),
        mechanism=str(a.get("mechanism") or ""),
        certificate=dict(a.get("validation_certificate") or {}),
        origin={"strategy_id": a.get("strategy_id"), "version_hash": a.get("version_hash")})


_READERS = {"CANDIDATE": from_candidate, "NODE": from_node,
            "CERTIFICATE": from_certificate, "ARTIFACT": from_artifact}


def from_any(rec: dict[str, Any]) -> AlphaGenome | None:
    """The record's genome, or None when it is none of the four shapes."""
    shape = shape_of(rec)
    return _READERS[shape](rec) if shape else None


def stamp(rec: dict[str, Any]) -> dict[str, Any]:
    """Write `genome_id` into a record at the pen that builds it. Idempotent; a record of no
    known shape is returned untouched so a producer can call this unconditionally."""
    g = from_any(rec)
    if g is not None:
        rec["genome_id"] = g.genome_id
    return rec


def chain(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """genome_id -> the stages seen for it, in funnel order. The measure behind AP3's first
    half: a genome present at CANDIDATE and CERTIFICATE but absent at NODE is a graph that
    never recorded what the gauntlet judged."""
    seen: dict[str, set[str]] = {}
    for rec in records:
        g = from_any(rec)
        if g is not None:
            seen.setdefault(g.genome_id, set()).add(g.stage)
    return {k: [s for s in STAGES if s in v] for k, v in seen.items()}
