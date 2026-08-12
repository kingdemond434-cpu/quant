"""UPSTREAM LINEAGE + NO FALSE DATA DIVERSITY -- gate items 17/18, mandate XIX-A..C.

THE LAW. "Never assume a terminal constitutes a new independent information source merely because
it exposes a different interface." For every external terminal or aggregator reconstruct the full
station list -- DATA FIELD -> UPSTREAM ORIGIN -> ORIGINAL PROVIDER -> TRANSFORMATION -> AGGREGATION
-> UPDATE FREQUENCY -> LATENCY -> HISTORY -> RIGHTS -> COST -> RELIABILITY -> EXISTING DESK
COVERAGE -> UNIQUE INCREMENTAL INFORMATION -- and then count sources HONESTLY:

    SOURCE_COUNT   is how many endpoints the desk talks to.
    EFFECTIVE_INDEPENDENT_INFORMATION_SOURCE_COUNT is how many independent observations of the
    world those endpoints actually carry.

THE DEFECT THIS MEASURES, and it is live on this desk. The collectors currently reach
api.binance.com, fapi.binance.com, api.bybit.com, api.coingecko.com, api.llama.fi,
yields.llama.fi, stablecoins.llama.fi, api.dexscreener.com and more. Counted naively that is nine
sources. But coingecko's perp prices are Binance's prices with a normalisation pass, and the three
llama hosts are one provider behind three subdomains. A breadth metric that counts endpoints
rewards adding a fourth dashboard over adding a genuinely new observation -- and worse, it inflates
the effective-N that the desk's own cross-mechanism correlation work depends on. An N_eff computed
over redundant routes is not conservative, it is WRONG IN THE DANGEROUS DIRECTION: it says the
portfolio is more diversified than it is.

REDUNDANCY IS NOT WORTHLESS, AND THIS MODULE NEVER SAYS IT IS. XIX-B is explicit: redundant routes
remain useful for failover, latency comparison, gap filling, quality verification and revision
detection. So a duplicate is classified USEFUL_BUT_NOT_INDEPENDENT with its uses named -- it loses
its INFORMATION credit, not its place on the desk. Deleting a redundant route because it failed an
independence test would be this module causing the very kind of loss it exists to prevent.

RAW BEATS DERIVED (XIX-C). The layers below are ordered by fidelity. Scraping a heatmap when the
numerical observation behind it is lawfully available is a downgrade dressed as a data source, so
a field whose layer is worse than an available alternative's is flagged.

AUTHORITY: MEASUREMENT ONLY. This module classifies and counts. It never removes a source, never
blocks an integration, and never decides what to buy -- purchasing is the principal's call.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "DERIVATION_LAYERS",
    "REDUNDANCY_USES",
    "STATIONS",
    "Field",
    "effective_independent_sources",
    "reconstruct",
    "upstream_vs_aggregator",
]

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = "docs/research/source_lineage.json"

#: XIX-C, ordered BEST fidelity first. Index is the fidelity rank.
DERIVATION_LAYERS: tuple[str, ...] = (
    "RAW_OBSERVATION",         # the venue's own tick/book/print
    "UPSTREAM_NORMALIZED",     # same observation, schema cleaned
    "AGGREGATED",              # combined across venues
    "ESTIMATED",               # inferred where not observed
    "MODEL_DERIVED",           # output of somebody's model
    "HEATMAP_DERIVED",         # read back off a picture
    "AI_DERIVED",              # an LLM's answer about the data
    "TERMINAL_VISUALIZATION",  # a chart, with the numbers thrown away
)

#: XIX-B. What a redundant route is still GOOD FOR. Naming these is what stops an independence
#: test being read as a delete order.
REDUNDANCY_USES: tuple[str, ...] = (
    "failover", "latency_comparison", "gap_filling", "quality_verification", "revision_detection",
)

#: XIX's reconstruction stations. A blank station is an unasked question, never a negative answer.
STATIONS: tuple[str, ...] = (
    "data_field", "upstream_origin", "original_provider", "transformation", "aggregation",
    "update_frequency", "latency", "history", "rights", "cost", "reliability",
    "existing_desk_coverage", "unique_incremental_information",
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Field:
    """One data field exposed by one terminal, walked through the XIX stations."""

    terminal: str
    data_field: str
    upstream_source_id: str          # THE KEY: who originally OBSERVED this
    derivation_layer: str = "RAW_OBSERVATION"
    upstream_origin: str = ""
    original_provider: str = ""
    transformation: str = ""
    aggregation: str = ""
    update_frequency: str = ""
    latency: str = ""
    history: str = ""
    rights: str = ""
    cost: str = ""
    reliability: str = ""
    existing_desk_coverage: str = ""
    unique_incremental_information: str = ""
    redistribution_chain: tuple[str, ...] = ()

    def missing_stations(self) -> list[str]:
        return [s for s in STATIONS if not str(getattr(self, s, "")).strip()]

    def fidelity_rank(self) -> int:
        try:
            return DERIVATION_LAYERS.index(self.derivation_layer)
        except ValueError:
            return len(DERIVATION_LAYERS)          # unknown ranks WORST, never best


def reconstruct(fields: list[Field]) -> dict[str, Any]:
    """GATE ITEM 17. Reconstruct one terminal's lineage and say what is still unasked.

    A field with blank stations is reported as INCOMPLETE with the stations named. It is NOT
    dropped: a half-reconstructed field is a shopping list for the next reader, and dropping it
    would hide the terminal's least-understood fields -- exactly the ones worth understanding.
    """
    if not fields:
        return {"status": "UNMEASURED", "why": "no fields supplied -- nothing was examined, which "
                                               "is not the same as a terminal with no fields"}
    terminals = sorted({f.terminal for f in fields})
    out_fields = []
    for f in fields:
        missing = f.missing_stations()
        out_fields.append({
            **asdict(f),
            "fidelity_rank": f.fidelity_rank(),
            "station_status": "COMPLETE" if not missing else "INCOMPLETE",
            "missing_stations": missing,
        })
    complete = sum(1 for f in out_fields if f["station_status"] == "COMPLETE")
    return {
        "generated_utc": _now(),
        "status": "MEASURED",
        "terminals": terminals,
        "n_fields": len(fields),
        "n_complete": complete,
        "n_incomplete": len(fields) - complete,
        "fields": out_fields,
        "law": "an INCOMPLETE field is retained with its gaps named -- dropping it would hide the "
               "terminal's least-understood fields, which are the ones worth understanding",
        "authority": "MEASUREMENT ONLY -- classifies and counts; removes no source.",
    }


def effective_independent_sources(fields: list[Field]) -> dict[str, Any]:
    """GATE ITEM 18. SOURCE_COUNT vs EFFECTIVE_INDEPENDENT_INFORMATION_SOURCE_COUNT.

    Independence is keyed on UPSTREAM_SOURCE_ID -- who originally observed the thing -- not on the
    hostname the desk happens to call. Five dashboards reading Binance are one observation of the
    world and five ways to fetch it.

    Within an upstream group the RETAINED representative is the HIGHEST-FIDELITY route (XIX-C):
    if the desk can get the raw print and also a heatmap of it, the raw print is the source and
    the heatmap is redundancy. Ties break toward the shorter redistribution chain, because every
    extra hop is another party who can silently revise, delay or drop a field.
    """
    if not fields:
        return {"status": "UNMEASURED", "source_count": 0,
                "effective_independent_information_source_count": 0,
                "why": "nothing examined -- an unmeasured count is UNKNOWN, never zero (L1.41)"}

    groups: dict[str, list[Field]] = {}
    for f in fields:
        groups.setdefault(f.upstream_source_id, []).append(f)

    independent: list[dict[str, Any]] = []
    redundant: list[dict[str, Any]] = []
    for upstream, members in sorted(groups.items()):
        ranked = sorted(members, key=lambda f: (f.fidelity_rank(), len(f.redistribution_chain),
                                                f.terminal))
        primary = ranked[0]
        independent.append({
            "upstream_source_id": upstream,
            "retained_route": f"{primary.terminal}:{primary.data_field}",
            "derivation_layer": primary.derivation_layer,
            "why": "highest-fidelity route to this upstream observation; ties break toward the "
                   "shorter redistribution chain, since every hop is another party who can "
                   "silently revise, delay or drop a field",
        })
        for dup in ranked[1:]:
            redundant.append({
                "upstream_source_id": upstream,
                "route": f"{dup.terminal}:{dup.data_field}",
                "derivation_layer": dup.derivation_layer,
                "classification": "USEFUL_BUT_NOT_INDEPENDENT",
                "still_good_for": list(REDUNDANCY_USES),
                "why": f"redistributes the same upstream observation as "
                       f"{primary.terminal}:{primary.data_field}. It loses its INFORMATION credit, "
                       "NOT its place on the desk -- XIX-B keeps redundant routes for failover, "
                       "latency comparison, gap filling, quality verification and revision "
                       "detection",
            })

    n_routes = len(fields)
    n_eff = len(independent)
    return {
        "generated_utc": _now(),
        "status": "MEASURED",
        "source_count": n_routes,
        "effective_independent_information_source_count": n_eff,
        "false_diversity": n_routes - n_eff,
        "inflation_factor": round(n_routes / n_eff, 3) if n_eff else None,
        "independent": independent,
        "redundant": redundant,
        "law": "counting endpoints instead of observations inflates the effective-N the desk's "
               "own cross-mechanism correlation work depends on -- and it errs in the DANGEROUS "
               "direction, reporting the portfolio as more diversified than it is",
        "authority": "MEASUREMENT ONLY -- no route is removed by this count.",
    }


def upstream_vs_aggregator(*, direct: Field | None, aggregator: Field,
                           notes: str = "") -> dict[str, Any]:
    """XIX-A UPSTREAM-FIRST. Compare direct ingestion against the aggregator, dimension by
    dimension, and say which wins WITH ITS REASON rather than by default.

    Neither side wins automatically. Direct is preferred on fidelity, precision, history, latency,
    rights, reliability, cost, schema stability and provenance; an aggregator earns its place
    through unique normalisation, difficult integrations, derived measurements, historical
    preservation, cross-source fusion, cleaner semantics, lower engineering cost, superior
    reliability, novel metadata or genuinely unique information.
    """
    if direct is None:
        return {
            "verdict": "AGGREGATOR_ONLY_ROUTE_KNOWN",
            "aggregator": f"{aggregator.terminal}:{aggregator.data_field}",
            "why": "no direct upstream route has been identified for this field. That is a "
                   "RESEARCH GAP, not evidence that none exists -- XIX-A requires the comparison "
                   "to be attempted before an aggregator is accepted as the permanent route",
            "next_action": "identify the original provider's own API/feed and re-run this "
                           "comparison",
        }
    d_rank, a_rank = direct.fidelity_rank(), aggregator.fidelity_rank()
    if d_rank < a_rank:
        return {
            "verdict": "PREFER_DIRECT_UPSTREAM",
            "direct": f"{direct.terminal}:{direct.data_field}",
            "aggregator": f"{aggregator.terminal}:{aggregator.data_field}",
            "direct_layer": direct.derivation_layer,
            "aggregator_layer": aggregator.derivation_layer,
            "why": f"the direct route is {direct.derivation_layer} and the aggregator is "
                   f"{aggregator.derivation_layer}; taking the derived copy when the raw "
                   "observation is lawfully available is a downgrade dressed as a data source "
                   "(XIX-C)",
            "notes": notes,
        }
    if aggregator.unique_incremental_information.strip():
        return {
            "verdict": "PREFER_AGGREGATOR",
            "why": "the aggregator carries stated incremental value: "
                   f"{aggregator.unique_incremental_information}",
            "notes": notes,
        }
    return {
        "verdict": "PREFER_DIRECT_UPSTREAM",
        "why": "same fidelity layer and the aggregator states no incremental value, so the extra "
               "hop buys nothing and adds a party who can silently revise, delay or drop a field",
        "notes": notes,
    }


def write_report(fields: list[Field], *, root: Path | None = None) -> Path:
    base = root or _ROOT
    doc = {
        "what": "XIX lineage reconstruction + effective independent information source count",
        "lineage": reconstruct(fields),
        "independence": effective_independent_sources(fields),
    }
    p = base / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False), "utf-8")
    return p


#: THE DESK'S REAL ROUTES, read off the collectors in libs/data and scripts/collect_*. Seeded
#: rather than invented: every terminal here is a host this desk actually calls today.
DESK_FIELDS: tuple[Field, ...] = (
    Field(terminal="binance_spot", data_field="ohlcv", upstream_source_id="binance",
          derivation_layer="RAW_OBSERVATION", upstream_origin="api.binance.com",
          original_provider="Binance", transformation="none", aggregation="none",
          update_frequency="per-trade / 1m klines", latency="sub-second",
          history="years via klines endpoint", rights="public API, ToS-bound, no redistribution",
          cost="free (rate-limited)", reliability="high, occasional 418/429",
          existing_desk_coverage="primary spot tape",
          unique_incremental_information="the venue's own prints"),
    Field(terminal="binance_futures", data_field="funding_rate", upstream_source_id="binance",
          derivation_layer="RAW_OBSERVATION", upstream_origin="fapi.binance.com",
          original_provider="Binance", transformation="none", aggregation="none",
          update_frequency="8h settlement, 1m mark", latency="sub-second",
          history="since listing", rights="public API, ToS-bound", cost="free (rate-limited)",
          reliability="high", existing_desk_coverage="funding/basis mechanism class",
          unique_incremental_information="the settlement the desk is actually paid or charged"),
    Field(terminal="coingecko", data_field="price", upstream_source_id="binance",
          derivation_layer="AGGREGATED", upstream_origin="api.coingecko.com",
          original_provider="Binance and other venues, via CoinGecko",
          transformation="volume-weighted across venues", aggregation="cross-venue",
          update_frequency="~1min", latency="tens of seconds to minutes",
          history="long, daily granularity", rights="free tier, attribution",
          cost="free tier rate-limited", reliability="medium",
          existing_desk_coverage="already covered by the venue tape",
          unique_incremental_information="",
          redistribution_chain=("binance", "coingecko")),
    Field(terminal="defillama_tvl", data_field="protocol_tvl", upstream_source_id="defillama",
          derivation_layer="ESTIMATED", upstream_origin="api.llama.fi",
          original_provider="DefiLlama", transformation="on-chain balances priced and summed",
          aggregation="per-protocol", update_frequency="hourly", latency="~1h",
          history="multi-year", rights="free, open", cost="free",
          reliability="medium; methodology revisions occur",
          existing_desk_coverage="none direct",
          unique_incremental_information="cross-protocol TVL the desk does not compute itself"),
    Field(terminal="defillama_yields", data_field="pool_apy", upstream_source_id="defillama",
          derivation_layer="MODEL_DERIVED", upstream_origin="yields.llama.fi",
          original_provider="DefiLlama", transformation="APY modelled from reward emissions",
          aggregation="per-pool", update_frequency="hourly", latency="~1h",
          history="multi-year", rights="free, open", cost="free",
          reliability="medium", existing_desk_coverage="same provider as TVL",
          unique_incremental_information="",
          redistribution_chain=("defillama",)),
    Field(terminal="defillama_stables", data_field="stablecoin_supply",
          upstream_source_id="defillama", derivation_layer="AGGREGATED",
          upstream_origin="stablecoins.llama.fi", original_provider="DefiLlama",
          transformation="chain balances summed per issuer", aggregation="per-chain",
          update_frequency="hourly", latency="~1h", history="multi-year", rights="free, open",
          cost="free", reliability="medium", existing_desk_coverage="same provider as TVL",
          unique_incremental_information="",
          redistribution_chain=("defillama",)),
    Field(terminal="ethereum_rpc", data_field="unlock_transfers", upstream_source_id="ethereum_l1",
          derivation_layer="RAW_OBSERVATION",
          upstream_origin="ethereum-rpc.publicnode.com",
          original_provider="Ethereum L1 (public node)",
          transformation="none -- logs read directly", aggregation="none",
          update_frequency="per block (~12s)", latency="one block",
          history="full chain via archive calls", rights="public chain data, no licence",
          cost="free, keyless", reliability="medium (public endpoint)",
          existing_desk_coverage="token-unlock mechanism class",
          unique_incremental_information="the settlement itself, not a report about it"),
    Field(terminal="bybit", data_field="funding_rate", upstream_source_id="bybit",
          derivation_layer="RAW_OBSERVATION", upstream_origin="api.bybit.com",
          original_provider="Bybit", transformation="none", aggregation="none",
          update_frequency="8h settlement", latency="sub-second", history="since listing",
          rights="public API, ToS-bound", cost="free (rate-limited)", reliability="high",
          existing_desk_coverage="cross-venue funding dispersion",
          unique_incremental_information="a SECOND venue's own settlement -- genuinely "
                                         "independent of Binance's"),
)
