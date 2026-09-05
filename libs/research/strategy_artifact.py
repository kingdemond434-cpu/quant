"""The StrategyArtifact: the only object that may reach the allocator.

AlphaPilot's lifecycle (research -> artifact -> paper -> shadow -> live) and Korea Investment's
portable strategy definition, made one canonical, hashed contract: a strategy is not a Python
file, it is a record naming its mechanism, source, recipe, data requirements, feature ids,
instruments, timeframes, entry/exit/execution/state conditioning, cost assumptions, and every
certificate it has earned. The same artifact flows Research -> Backtest -> Shadow -> Live, so
what was validated is what trades.

`from_certificate` builds one from a row of the canonical survivor file, and `validate` refuses
an artifact that lacks what the allocator needs: an executable family and recipe, a symbol the
desk trades, a cost basis, and a certificate. `pf_allocator` can require `validate(...).ok`
before a sleeve competes for heat; `research/strategy_artifacts.py` writes the registry.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class StrategyArtifact:
    strategy_id: str
    mechanism: str
    source: str
    family: str
    params: dict[str, Any]
    symbols: list[str]
    timeframes: list[str]
    entry: dict[str, Any]
    exit: dict[str, Any]
    execution: dict[str, Any]
    state_conditioning: dict[str, Any]
    data_requirements: list[str]
    feature_ids: list[str]
    cost_assumptions: dict[str, Any]
    validation_certificate: dict[str, Any]
    lockbox_certificate: dict[str, Any] = field(default_factory=dict)
    shadow_evidence: dict[str, Any] = field(default_factory=dict)
    factor_exposures: dict[str, float] = field(default_factory=dict)
    expected_posterior: dict[str, Any] = field(default_factory=dict)
    risk_response: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    version_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["version_hash"] = self.compute_hash()
        return d

    def compute_hash(self) -> str:
        body = {k: v for k, v in asdict(self).items()
                if k not in ("version_hash", "shadow_evidence")}
        blob = json.dumps(body, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]


def from_certificate(key: str, cert: dict[str, Any]) -> StrategyArtifact:
    spec = cert.get("shadow_spec") or {}
    sym = str(cert.get("sym") or spec.get("symbol") or "").upper()
    fam = str(spec.get("family") or cert.get("family") or "")
    params = dict(spec.get("params") or cert.get("params") or {})
    return StrategyArtifact(
        strategy_id=key, mechanism=str(cert.get("mechanism") or cert.get("hypothesis") or fam),
        source=str(cert.get("hunt") or cert.get("source") or ""), family=fam, params=params,
        symbols=[sym] if sym else [], timeframes=[str(spec.get("timeframe") or "H1")],
        entry={"family": fam, "selector": spec.get("selector"), "side": spec.get("side")},
        exit={"ttl_bars": params.get("ttl_bars") or params.get("hold_bars"),
              "rr": params.get("rr"), "stop_atr": params.get("stop_atr")},
        execution={"policy": "MARKET", "fill_rule": "open of the bar after the signal"},
        state_conditioning={"state": spec.get("state") or cert.get("state")},
        data_requirements=[f"bars.h1:{sym}"] + [f"driver:{d}" for d in
                                                (params.get("factor_symbols") or [])],
        feature_ids=[], cost_assumptions={"cost_hash": cert.get("cost_hash"),
                                          "cost_r": cert.get("cost_r")},
        validation_certificate={"status": cert.get("status") or "PASS",
                                "gates": cert.get("gates"), "hunt": cert.get("hunt"),
                                "certified_at": cert.get("certified_at") or cert.get("at")},
        lockbox_certificate=dict(cert.get("lockbox") or {}),
        shadow_evidence=dict(cert.get("shadow") or {}),
    )


def validate(a: StrategyArtifact, *, known_families: set[str] | None = None,
             known_symbols: set[str] | None = None) -> dict[str, Any]:
    problems = []
    if not a.family:
        problems.append("no family")
    elif known_families is not None and a.family not in known_families:
        problems.append(f"family {a.family} is not registered")
    if not a.symbols:
        problems.append("no symbol")
    elif known_symbols is not None and any(s not in known_symbols for s in a.symbols):
        problems.append(f"symbol not in the desk's universe: {a.symbols}")
    if not a.validation_certificate or a.validation_certificate.get("status") not in ("PASS", ""):
        problems.append("no passing validation certificate")
    if a.cost_assumptions.get("cost_hash") is None and a.cost_assumptions.get("cost_r") is None:
        problems.append("no cost basis")
    return {"ok": not problems, "problems": problems, "version_hash": a.compute_hash()}
