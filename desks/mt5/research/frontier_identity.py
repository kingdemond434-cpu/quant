"""Exact identity and economic-prior rules shared by discovery and the universal gauntlet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from libs.validation.economic_prior import REQUIRED_FIELDS, economic_prior_gate

#: The chart every historical cell was hunted on, and the one whose name stays unwritten.
#:
#: THE CORRUPTION THIS PREVENTS (2026-09-05, when the sweep gained the full M1..D1 ladder). Cell
#: identity feeds the gauntlet's content-addressed series cache and the certificate key. If it
#: does not carry the CHART, then the same symbol and family on M5 and on H1 are the SAME CELL:
#: the cache serves one result for the other and a certificate minted on one chart is claimed by
#: the other. Every number in that record is internally consistent, so no gate downstream can see
#: it -- which makes it strictly worse than the H1-only limitation it would arrive with.
#:
#: H1 IS SPELLED BY ITS ABSENCE, and the asymmetry is deliberate rather than untidy -- it is the
#: same rule `shadow_forward.sleeve_key` already applies to direction ("every key ever written by
#: this desk is a long clock"). Every cell id, certificate, forward-clock key and cache entry this
#: desk has ever written is an H1 cell. Writing `@H1` into all of them would rename the entire
#: canon at once and orphan every running clock against its own ledger. So an H1 id is
#: byte-identical to what it has always been, and every other chart is named explicitly.
REFERENCE_TIMEFRAME = "H1"


def timeframe_of(cell: dict[str, Any]) -> str:
    """The chart a cell is hunted on: its own `timeframe`, its params', or H1 by default."""
    for source in (cell, cell.get("params") or {}):
        if isinstance(source, dict) and source.get("timeframe"):
            return str(source["timeframe"]).upper()
    return REFERENCE_TIMEFRAME


def _tf_suffix(cell: dict[str, Any]) -> str:
    tf = timeframe_of(cell)
    return "" if tf == REFERENCE_TIMEFRAME else f"@{tf}"


def cell_id(cell: dict[str, Any]) -> str:
    """Executable identity; arbitrary DSL parameters must never collapse onto rr=?/wb=? IDs."""
    params = dict(cell.get("params") or {})
    # THE LEGACY SHORT FORM IS ONLY SAFE WHEN rr/wait_bars ARE THE WHOLE PARAMETER SET.
    # It used to fire whenever EITHER key was present, so every other parameter collapsed out
    # of the identity -- measured 2026-08-29 on H-20260828-005, where 24 distinct trials
    # (3 symbols x 2 rr x 2 ttl_bars x 2 directions) printed as 8 ids, three cells deep each,
    # with opposite-signed Sharpes under the SAME name. The docstring above already forbade
    # exactly this; the branch predicate did not enforce it. Anything richer than {rr,
    # wait_bars} now takes the digest form, so no historical id whose params were only those
    # two keys changes value.
    # THE CHART IS PART OF THE NAME, not only of the digest. `timeframe` normally rides in
    # `params` and so already changes the digest -- but a cell whose chart is carried on the row
    # instead, and the legacy short form below (which drops params entirely), would both collapse
    # two charts onto one id. Reading it through `timeframe_of` and appending it makes the
    # identity right whichever way the chart was recorded, and leaves it VISIBLE: an operator
    # reading a docket can see that `XAUUSD@M5.carry.p=ab12` is not the H1 cell of that name.
    # It rides on the SYMBOL rather than at the end because every consumer that splits a cell id
    # splits on "." -- `<sym>.<family>.<params>` -- and a fourth dot-separated field would change
    # that arity for every reader at once.
    tf = _tf_suffix(cell)
    if params and set(params) <= {"rr", "wait_bars"}:
        return (f"{cell['sym']}{tf}.{cell['family']}.rr={params.get('rr', '?')}"
                f"_wb={params.get('wait_bars', '?')}")
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{cell['sym']}{tf}.{cell['family']}.p={digest}"


def docket_cell(row: dict[str, Any]) -> dict[str, Any]:
    """A DOCKET ROW, normalised into the cell the judge will key its verdict by.

    THE ONE PLACE THE ROW->CELL RULE LIVES, and the reason it has to exist at all. `cell_id`
    answers "what is this cell called"; it cannot answer "which cell is this ROW", because a
    producer may carry the chart in `params["timeframe"]`, on the row's own `timeframe` field, or
    in both. `external_gauntlet.main` groups the docket into cells by folding a non-H1 ROW chart
    into `params` and then naming the cell from `params` alone -- so the chart is inside the
    identity DIGEST. Any reader that instead hands `cell_id` a separate `timeframe` key gets the
    right `@TF` suffix over a digest computed WITHOUT the chart, and lands in a different key
    space that happens to look identical for H1.

    WHAT THAT COST, MEASURED ON THE BOX 2026-09-24/25. `judge_coverage` banks every cell whose
    build failed (88,488 rows) under the judge's own verdict key, and filters the docket by that
    bank under the second key. Overlap of the bank with the 539,462-row docket:

        bank INTERSECT judge_coverage's keys     0
        bank INTERSECT the judge's own keys  78,771

    So the bank held the answer for 78,771 docket rows and removed none of them: the judge
    rebuilt every one of them, every pass, and its pre-warm failure count never moved
    (81,588 -> 88,246 -> 109,792 -> 93,320). 192,757 of 539,462 rows (35.7%) were keyed
    differently by the two sides. The same gap silently told the coverage table that every
    non-H1 cell it had ever judged was still unjudged, because `judged_index` reads the gate
    ledger, which is in the judge's key space too.

    Two shapes diverge, and they diverge in OPPOSITE directions -- which is why a partial
    overlap, rather than none at all, is what a reader saw:

      * chart on the row only  (row `timeframe` M15, absent from params)
          judge: GBPAUD@M15.cross_asset_residual.p=6403309d7977b134   (chart IS in the digest)
          here : GBPAUD@M15.cross_asset_residual.p=a7abf4646a7e6aca   (chart is NOT)
      * chart in params, row says H1 (the orthogonal sweep writes both, row stamped H1)
          judge: UK100@M1.exogenous_conditioner.p=4174b6f6734b5405
          here : UK100.exogenous_conditioner.p=4174b6f6734b5405       (suffix lost entirely)

    `timeframe_of` reads the cell-level field FIRST, so passing `timeframe` beside `params`
    overrides the chart the params themselves name. Returning a cell with NO separate
    `timeframe` key is therefore load-bearing, not tidiness: params alone must decide.
    """
    params = dict(row.get("params") or {})
    row_tf = str(row.get("timeframe") or "").upper()
    if row_tf and row_tf != REFERENCE_TIMEFRAME and "timeframe" not in params:
        params["timeframe"] = row_tf
    return {"sym": row.get("symbol") or row.get("sym"), "family": row.get("family"),
            "params": params}


def docket_cell_id(row: dict[str, Any]) -> str:
    """The judge's identity for a docket ROW. See `docket_cell` for why the row needs its own."""
    return cell_id(docket_cell(row))


#: THE SIX-FIELD ECONOMIC PRIOR (H3: why an edge exists, and why it persists). A bare NAMED tag
#: says only that some producer believed a mechanism existed; it does not say WHAT the mechanism
#: is, why it might fail, why it might be overfit, why it might decay, how decay is seen, or what
#: replaces it. `libs.validation.economic_prior.EconomicPrior` is that artifact. This module now
#: asks for it on the judge path, and records which fields are missing when it is absent.
#:
#: WHERE A CELL'S PRIOR COMES FROM, in order: the cell's own `economic_prior` mapping, then the
#: family's entry in `desks/mt5/data/economic_priors.json`. The family file exists because the
#: sealed judge (`external_gauntlet`) builds its cells from a fixed list of docket fields, so a
#: per-row prior never reaches this function on that path. A mechanism is a property of the
#: family, so the family is where it is written once.
PRIOR_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "economic_priors.json"

PRIOR_COMPLETE = "PRIOR_COMPLETE"
PRIOR_INCOMPLETE = "PRIOR_INCOMPLETE"
GRANDFATHERED_UNMEASURED = "GRANDFATHERED_UNMEASURED"
STATISTICAL_ONLY = "STATISTICAL_ONLY"

#: Every field an `EconomicPrior` must carry, `mechanism` first.
PRIOR_FIELDS: tuple[str, ...] = ("mechanism", *REQUIRED_FIELDS)

#: THE GRANDFATHER ROSTER, FROZEN 2026-11-18. Measured that day on the live branch's own data:
#: 0 of 57,538 docket rows, 0 of 58 certificates and 0 of 26 STANDBY sleeves carried a six-field
#: prior, and no family had one written. Requiring it of them at once would have stopped 100% of
#: the docket at gate 1 -- a cut in research breadth by fiat, which growth governance forbids.
#: So the requirement binds NEW mechanisms only: a family absent from this list must arrive with
#: its six fields or be recorded PRIOR_INCOMPLETE. A family on it keeps passing exactly as it did,
#: and its verdict reads GRANDFATHERED_UNMEASURED with the missing fields named, so the debt is
#: visible (`research/economic_prior_backfill.py` reports it hourly) and never silent.
#:
#: The list is the union of every family the desk could reach that day: the four constructor
#: populations (FAMILY_REGISTRY, `family_*` functions, ORTHOGONAL_FAMILIES, hunt16), the axis
#: registry's FAMILY_TABLE, every `family` in data/hypotheses/*.json, the certificates and the
#: sleeve registries. It is code, not a data file, on purpose: a roster anyone can append to is a
#: way round the rule. It only ever shrinks, as families gain a complete prior.
GRANDFATHERED_FAMILIES: frozenset[str] = frozenset({
    "adx_channel_hybrid", "ae_latent", "alt_conditioned", "alt_release_drift",
    "alt_series_momentum", "analyst_cross_market_lead", "analyst_revision_drift",
    "anti_donchian_breakout", "anti_three_bar_momentum", "asia_meanrev", "asia_momentum",
    "attention_ts", "calendar_month", "carry", "carry+overnight_gap_decay",
    "carry+session_range_breakout", "carry_risk_off", "clock_transition", "comex_settlement",
    "correlation_regime", "cot_change_fade", "cot_change_momentum", "cot_comm_follow",
    "cot_net_fade", "cot_positioning", "crisis_only_class_defensive", "cross_asset_residual",
    "cross_sectional", "cross_sectional_class_carry", "cross_sectional_class_low_vol",
    "cross_sectional_class_momentum", "cross_sectional_class_reversal",
    "cross_sectional_class_value", "d1_inside", "d1_swing_break", "dav_abc_structure",
    "dav_bb_meanrev", "dav_breakout_fakeout", "dav_ema_trend_pullback", "dav_fakeout_reverse",
    "dav_hull_trend", "dav_keltner_break", "dav_macd_qqe", "dav_momentum_cont",
    "dav_range_filter_adx", "dav_rsi_div_rev", "dav_squeeze_expansion", "dav_supertrend_trail",
    "dav_t3_trend", "dip_atr_shock", "dip_pullback_pct", "dip_rsi_reclaim", "discovered",
    "dow_effect", "drawdown_conditional", "ema_crossover", "engulfing_reversal", "ensemble",
    "entry_conditioned", "event_reaction", "execution_state", "exit_operated",
    "exogenous_conditioner", "failed_breakout", "forced_flow", "formula", "fx_fixing_reversal",
    "generic", "gnn_propagation", "gold_dxy_shock", "h4_momentum", "hedging_demand_close",
    "htf_anchor_trend", "hunt16_cell", "ict_fvg", "joint_genome", "jump", "lead_lag",
    "lead_lag_class_catchup", "level_breakout", "liquidity_gamma_reversal", "liquidity_regime",
    "london_close_momentum", "london_ny_breakout", "lvc_asia_london", "macro_conditional",
    "macro_gold_yield", "macro_swing", "mass_screen_carry", "mass_screen_clock",
    "mass_screen_cond", "mass_screen_lead", "mass_screen_thresh", "mean_reversion_bollinger",
    "mean_reversion_rsi", "moat_spread_window", "momentum_basic", "momentum_volgate", "monday_gap",
    "month_end_rebalance", "multi_speed_trend", "opening_range", "orderflow_imbalance",
    "overnight_drift", "overnight_gap_decay", "overnight_gap_decay+session_range_breakout",
    "pca_residual", "pin_bar_reversal", "pullback_entry", "range_reversion", "regime_disagreement",
    "regime_split", "regime_transition", "relative_value", "retail_overlap_reversal", "rocket_ts",
    "seasonal_window", "session_handoff", "session_range_breakout", "sig_path", "sma_crossover",
    "spread_state", "style_premia", "trend_ma_cross", "triangle", "turn_of_month",
    "usd_session_shock", "vol_mean_reversion", "vol_transition", "volatility_squeeze",
    "volume_spike", "world_macro_state",
})

_REGISTRY_CACHE: dict[str, Any] = {}


def _family_priors() -> dict[str, Any]:
    """The family prior file, read once per process. Unreadable or absent reads as empty."""
    if "families" not in _REGISTRY_CACHE:
        fams: dict[str, Any] = {}
        try:
            doc = json.loads(PRIOR_REGISTRY_PATH.read_text("utf-8"))
            raw = doc.get("families") if isinstance(doc, dict) else None
            if isinstance(raw, dict):
                fams = {str(k): v for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, ValueError):
            fams = {}
        _REGISTRY_CACHE["families"] = fams
    out: dict[str, Any] = _REGISTRY_CACHE["families"]
    return out


def prior_for(cell: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """The six-field prior this cell is judged with, and where it came from."""
    own = cell.get("economic_prior")
    if isinstance(own, dict) and own:
        return own, "cell"
    fam = str(cell.get("family") or "")
    reg = _family_priors().get(fam)
    if reg:
        return reg, "family_registry"
    return None, None


def prior_missing(prior: dict[str, Any] | None) -> list[str]:
    """Which of the seven `EconomicPrior` fields are absent or blank; [] when it is complete."""
    if not prior:
        return list(PRIOR_FIELDS)
    gate = economic_prior_gate(prior)
    return [] if gate.passed else list(gate.missing)


def is_grandfathered(family: str) -> bool:
    return family in GRANDFATHERED_FAMILIES


def economic_prior(cell: dict[str, Any]) -> dict[str, Any]:
    """Gate 1. Statistical finds fail closed; a NAMED cell needs the six-field EconomicPrior.

    Verdicts, each recorded on the stage and never dropped:
      * STATISTICAL_ONLY          -- no mechanism at all; fails, as it always has.
      * PRIOR_COMPLETE            -- NAMED, and the prior validates as an EconomicPrior; passes.
      * PRIOR_INCOMPLETE          -- NAMED, a family outside the grandfather roster, and the
                                     prior is absent or short; fails, naming the missing fields.
      * GRANDFATHERED_UNMEASURED  -- NAMED, a family on the 2026-11-18 roster with no complete
                                     prior yet; passes as before, with the missing fields named.
    """
    status = str(cell.get("mechanism_status") or "")
    if not status:
        status = STATISTICAL_ONLY if cell.get("family") == "discovered" else "NAMED"
    named = status == "NAMED"
    note = str(cell.get("mechanism_note") or "")
    if not named:
        return {
            "passed": False,
            "message": note or "statistical discovery has no economic prior",
            "mechanism_status": status,
            "verdict": STATISTICAL_ONLY,
            "missing": list(PRIOR_FIELDS),
            "prior_source": None,
        }
    prior, source = prior_for(cell)
    missing = prior_missing(prior)
    family = str(cell.get("family") or "")
    if not missing:
        verdict, passed = PRIOR_COMPLETE, True
        message = note or "six-field economic prior complete"
    elif is_grandfathered(family):
        verdict, passed = GRANDFATHERED_UNMEASURED, True
        message = note or "named registered family"
    else:
        verdict, passed = PRIOR_INCOMPLETE, False
        message = (f"family {family!r} is not on the 2026-11-18 grandfather roster and its "
                   f"economic prior is missing {missing}")
    return {
        "passed": passed,
        "message": message,
        "mechanism_status": status,
        "verdict": verdict,
        "missing": missing,
        "prior_source": source,
    }
