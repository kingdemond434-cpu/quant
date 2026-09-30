"""Typed contracts for public research-factory surfaces and cross-factory experiments.

This is deliberately policy-free about alpha.  It records what a surface permits, what was
actually acquired, and how a reconstructed component may be evaluated.  A surface record or a
synthesis plan has no capital or certification authority.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

RIGHTS = ("read", "automate", "download", "reuse", "execute", "redistribute", "submit")
SURFACE_TYPES = ("documentation", "platform", "competition", "strategy_corpus", "data_vendor",
                 "public_history", "historical_archive", "platform_native",
                 "native_language_platform", "executable_research_engine", "paper")
DISPOSITIONS = ("DIRECT_CANDIDATE", "EXTERNAL_PREDICTOR", "IMPERFECT_PROXY", "RESEARCH_ONLY",
                "DATA_BLOCKED", "ACCESS_BLOCKED")


@dataclass(frozen=True)
class Surface:
    factory_id: str
    surface_id: str
    source_uri: str
    surface_type: str
    language: str
    rights: Mapping[str, str]
    cadence_hours: int
    evaluation_lane: str
    worker: str

    @property
    def key(self) -> str:
        return f"{self.factory_id}:{self.surface_id}"


def load_manifest(doc: Mapping[str, Any]) -> list[Surface]:
    out: list[Surface] = []
    for factory in doc.get("factories") or []:
        for row in factory.get("surfaces") or []:
            rights = dict(row.get("rights") or {})
            missing = [name for name in RIGHTS if not str(rights.get(name) or "")]
            if missing:
                name = f"{factory.get('factory_id')}:{row.get('surface_id')}"
                raise ValueError(f"{name} missing rights {missing}")
            kind = str(row.get("surface_type") or "")
            if kind not in SURFACE_TYPES:
                raise ValueError(f"unknown factory surface type {kind!r}")
            out.append(Surface(
                factory_id=str(factory["factory_id"]), surface_id=str(row["surface_id"]),
                source_uri=str(row["source_uri"]), surface_type=kind,
                language=str(row.get("language") or "unknown"), rights=rights,
                cadence_hours=max(1, int(row.get("cadence_hours") or 24)),
                evaluation_lane=str(row["evaluation_lane"]), worker=str(factory["worker"])))
    keys = [row.key for row in out]
    if len(keys) != len(set(keys)):
        raise ValueError("factory surface ids are not unique")
    return out


def version_id(surface: Surface, content_hash: str) -> str:
    raw = json.dumps({"surface": surface.key, "uri": surface.source_uri,
                      "content_hash": content_hash}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def content_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def access_blocker(surface: Surface) -> str | None:
    """Name the exact acquisition blocker.  UNKNOWN is never silently promoted to permission."""
    automate = str(surface.rights["automate"]).upper()
    read = str(surface.rights["read"]).upper()
    if read in {"NO", "PRIVATE", "NOT_AUTHORIZED"}:
        return "READ_NOT_AUTHORIZED"
    if automate in {"NO", "TERMS_UNKNOWN"}:
        return f"AUTOMATION_{automate}"
    return None


def synthesis_plan(parents: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Ablation-complete plan for components from distinct factories; never a verdict."""
    factories = sorted({str(p.get("factory_id") or p.get("system_id") or "") for p in parents
                        if p.get("factory_id") or p.get("system_id")})
    if len(factories) < 2:
        raise ValueError("cross-factory synthesis requires at least two distinct factories")
    ids = [str(p.get("component_id") or p.get("id") or p.get("run_id") or "") for p in parents]
    digest = hashlib.sha256(json.dumps([factories, ids], sort_keys=True).encode()).hexdigest()[:20]
    return {"experiment_id": f"factory-synth-{digest}", "parent_factories": factories,
            "parent_components": ids, "ablation_plan": [
                {"name": "baseline", "include": []},
                *({"name": f"only_{f}", "include": [f]} for f in factories),
                {"name": "combined", "include": factories}],
            "authority": "research proposal only; independent evaluator and forward clock judge"}
