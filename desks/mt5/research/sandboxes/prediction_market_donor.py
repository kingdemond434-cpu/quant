"""Prediction-market/public-tool donor rebuilt as MT5 research, never as venue execution.

The ten pinned public repositories are untrusted inputs.  This cell implements only transferable
mechanisms: prediction revisions/entropy/dispersion as reference sensors, prior-only participant
flow, calibrated weather revisions for commodities, replay contracts and execution failure
archetypes.  It cannot trade a prediction market, certify a cell, or size Fusion capital.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from statistics import fmean, pstdev
from typing import TypedDict

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "prediction_market_donor"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "information_acquisition"
UPSTREAM = (
    "polymarket_data", "prediction_market_backtesting", "polymarket_lp_tool", "polybot",
    "prediction_market_toolkits", "cloddsbot", "polymarket_mcp_server", "polyweather",
    "pydantic_ai", "awesome_prediction_market_tools",
)
FALLBACK = "desk-owned typed mechanism cards; no foreign package, credential or order authority"


class Atom(TypedDict):
    id: str
    family: str
    symbols: tuple[str, ...]
    mechanism: str
    falsifier: str
    sources: tuple[str, ...]

SOURCES = {
    "polymarket_data": "SII-WANGZJ/Polymarket_data@188eee28f09ba83d79c125bfb367f72ac93962c4",
    "prediction_market_backtesting": (
        "evan-kolberg/prediction-market-backtesting@"
        "c76e77af00ef53472a9da8f66dae7fdd2d3e5928"
    ),
    "polymarket_lp_tool": "lihanyu81/polymarket_lp_tool@32f779950de360d4a77187db89e0a1a1500da5d3",
    "polybot": "ent0n29/polybot@51e5362f026adf54162fc1256f453241d93680e6",
    "prediction_market_toolkits": (
        "HarrierOnChain/Prediction-Markets-Trading-Bot-Toolkits@"
        "b8a31fbedfa03554475e794691f72dea53f91dd9"
    ),
    "cloddsbot": "alsk1992/CloddsBot@c930628c47a4a745f497e29035a3b64622f97cc7",
    "polymarket_mcp_server": (
        "caiovicentino/polymarket-mcp-server@"
        "21f65f319ff0fc4250ea1e5094581761906839e1"
    ),
    "polyweather": "yangyuan-zhen/PolyWeather@43e658bbf6286e3cccdf4f09ce478ec90b3fb960",
    "pydantic_ai": "pydantic/pydantic-ai@ecb49988a2036bee051736c59c27e1232185b8d7",
    "awesome_prediction_market_tools": (
        "aarora4/Awesome-Prediction-Market-Tools@"
        "865e5e9fc4698c05a7b546159b097203cbe54af3"
    ),
}


def probability_delta(probabilities: Sequence[float], lookback: int = 1) -> list[float]:
    """Bounded probability revisions; missing history produces no invented observation."""
    if lookback < 1:
        raise ValueError("lookback must be positive")
    values = [min(1.0, max(0.0, float(p))) for p in probabilities]
    return [values[i] - values[i - lookback] for i in range(lookback, len(values))]


def binary_entropy(probability: float) -> float:
    """Natural-log binary entropy, zero at certainty and log(2) at maximum uncertainty."""
    p = min(1.0 - 1e-12, max(1e-12, float(probability)))
    return -(p * math.log(p) + (1.0 - p) * math.log(1.0 - p))


def venue_dispersion(probabilities: Iterable[float]) -> float | None:
    values = [min(1.0, max(0.0, float(p))) for p in probabilities]
    return pstdev(values) if len(values) >= 2 else None


def smart_flow(rows: Iterable[dict[str, float]]) -> float | None:
    """Prior-only signed flow; quality and independence must be estimated strictly earlier."""
    terms = []
    for row in rows:
        quality_raw = row.get("quality")
        direction_raw = row.get("direction")
        size_raw = row.get("size")
        independence_raw = row.get("independence")
        if (quality_raw is None or direction_raw is None or size_raw is None or
                independence_raw is None):
            continue
        quality = float(quality_raw)
        direction = float(direction_raw)
        size = float(size_raw)
        independence = float(independence_raw)
        terms.append(max(0.0, quality) * max(-1.0, min(1.0, direction)) *
                     max(0.0, size) * max(0.0, min(1.0, independence)))
    return fmean(terms) if terms else None


ATOMS: tuple[Atom, ...] = (
    {"id": "event_probability_revision", "family": "momentum_volgate",
     "symbols": ("XAUUSD", "US500", "NAS100", "EURUSD", "USDJPY", "XTIUSD"),
     "mechanism": "an event probability may update before the related CFD fully reprices",
     "falsifier": "PIT probability revisions add no net OOS value beyond asset and macro returns",
     "sources": ("polymarket_data", "prediction_market_backtesting")},
    {"id": "event_entropy_transition", "family": "vol_transition",
     "symbols": ("XAUUSD", "US500", "NAS100", "USDJPY", "XTIUSD"),
     "mechanism": "rapid resolution or expansion of event uncertainty changes hedging demand",
     "falsifier": "entropy changes do not improve OOS volatility or breakout forecasts",
     "sources": ("prediction_market_backtesting", "cloddsbot")},
    {"id": "cross_venue_probability_dispersion", "family": "vol_transition",
     "symbols": ("XAUUSD", "US500", "NAS100", "EURUSD", "USDJPY"),
     "mechanism": "venue disagreement measures unresolved information rather than direction",
     "falsifier": "dispersion has no stable incremental OOS relation to realised volatility",
     "sources": ("polymarket_data", "prediction_market_toolkits")},
    {"id": "prior_quality_participant_flow", "family": "momentum_volgate",
     "symbols": ("XAUUSD", "US500", "NAS100", "XTIUSD"),
     "mechanism": (
         "independent participants with previously measured calibration may reveal "
         "information arrival"
     ),
     "falsifier": "strictly prior participant scores add no OOS value over aggregate probability",
     "sources": ("polymarket_data", "polybot")},
    {"id": "weather_ensemble_revision", "family": "momentum_volgate",
     "symbols": ("XNGUSD", "XTIUSD", "XBRUSD", "CORN", "WHEAT", "SUGAR"),
     "mechanism": "calibrated forecast revisions change expected demand, supply and crop stress",
     "falsifier": "PIT weather revisions add no net OOS value after seasonality and reports",
     "sources": ("polyweather",)},
    {"id": "weather_model_dispersion", "family": "vol_transition",
     "symbols": ("XNGUSD", "XTIUSD", "XBRUSD", "CORN", "WHEAT", "SUGAR"),
     "mechanism": "forecast disagreement measures physical-state uncertainty and repricing risk",
     "falsifier": "calibrated ensemble dispersion does not improve OOS volatility forecasts",
     "sources": ("polyweather",)},
    {"id": "reference_book_imbalance", "family": "momentum_volgate",
     "symbols": ("XAUUSD", "US500", "NAS100", "XTIUSD"),
     "mechanism": "price discovery on the reference futures book can lead its MT5 CFD",
     "falsifier": "synchronised reference imbalance adds no net OOS value after latency and costs",
     "sources": ("polymarket_data", "polymarket_lp_tool", "prediction_market_toolkits")},
    {"id": "feed_disagreement_state", "family": "spread_state",
     "symbols": ("XAUUSD", "US500", "NAS100", "EURUSD", "USDJPY", "XTIUSD"),
     "mechanism": (
         "authoritative-versus-stream disagreement marks degraded information and "
         "execution conditions"
     ),
     "falsifier": "feed disagreement does not separate spread, slippage or forecast error OOS",
     "sources": ("polymarket_lp_tool", "polymarket_mcp_server")},
)


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    del ctx
    frames = bundle.frames()
    available = {(frame.symbol, frame.timeframe) for frame in frames if len(frame) >= 100}
    candidates = []
    for atom in ATOMS:
        for symbol in atom["symbols"]:
            timeframes = [tf for sym, tf in available if sym == symbol]
            for timeframe in sorted(timeframes)[:2]:
                candidates.append(A.candidate(
                    str(atom["family"]), [str(symbol)],
                    f"{atom['id']}: {atom['mechanism']}; falsifier: {atom['falsifier']}",
                    horizon=timeframe,
                    source=";".join(SOURCES[source] for source in atom["sources"]), evidence={
                        "source_claim_is_prior_only": True,
                        "required_external_axis": atom["id"],
                        "point_in_time_required": True,
                        "source_pins": {source: SOURCES[source] for source in atom["sources"]},
                        "venue_execution_authority": False,
                    }))
    methods = (
        {"kind": "EVENT_REPLAY_CONTRACT", "fields": ["source_time", "received_time",
          "processed_time", "sequence", "raw_hash", "normalised_hash", "consumer_ack"],
         "sources": [SOURCES["prediction_market_backtesting"]]},
        {"kind": "PROBABILITY_CALIBRATION", "scores": ["Brier", "log_loss", "ECE"],
         "references": ["base_rate", "BetaBinary"], "raw_votes_are_probability": False,
         "sources": [SOURCES["prediction_market_backtesting"], SOURCES["cloddsbot"]]},
        {"kind": "PUBLIC_PARTICIPANT_FINGERPRINT", "features": ["holding_time", "session",
          "entry_geometry", "clustering", "scaling", "side_asymmetry", "event_latency"],
         "rule": "quality is estimated on strictly prior resolved observations",
         "sources": [SOURCES["polybot"]]},
        {"kind": "STREAM_RECONCILIATION", "fast": "stream", "authority": "source API or broker",
         "guards": ["idempotency", "quote-shock filter", "stability confirmation",
                    "max chase", "post-fill cooldown"],
         "sources": [SOURCES["polymarket_lp_tool"]]},
        {"kind": "EXECUTION_FAILURE_ARCHETYPES", "tests": [
          "risk gate blocks but order continues", "wrong symbol/outcome mapping",
          "heartbeat healthy but stream consumes nothing", "reader starvation",
          "wrong dependency object reaches consumer"],
         "sources": [SOURCES["polymarket_mcp_server"]]},
        {"kind": "TYPED_AGENT_GRAPH_ABLATION", "baseline": "existing desk contracts",
         "challenger": "schema validation, durable graph state and trace evals",
         "admit_only_if": "measured reliability improves without parallel authority",
         "sources": [SOURCES["pydantic_ai"]]},
        {"kind": "SOURCE_FRONTIER_DELTA_SCAN", "seed": SOURCES["awesome_prediction_market_tools"],
         "rule": "new entries become source dispositions, never evidence by listing",
         "sources": [SOURCES["awesome_prediction_market_tools"]]},
    )
    datasets = ({"kind": "REFERENCE_SENSOR_SCHEMA", "source": SOURCES["polymarket_data"],
                 "fields": ["event_id", "source_time", "received_time", "probability",
                            "volume", "maker_taker", "participant_id", "resolution"],
                 "capital_authority": False},)
    mechanisms = tuple({
        "kind": "MECHANISM_ATOM", **atom,
        "source_pins": {source: SOURCES[source] for source in atom["sources"]},
    } for atom in ATOMS)
    return A.packet(SYSTEM, bundle, trials=0, candidates=candidates, datasets=datasets,
                    mechanisms=mechanisms, research_methods=methods,
                    note=(
                        "public sources are priors; all candidates pay ordinary "
                        "gates/multiplicity"
                    ))
