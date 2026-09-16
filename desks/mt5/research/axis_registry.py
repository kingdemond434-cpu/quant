"""THE INFORMATION-AXIS REGISTRY: every cell the desk has judged, on ten axes, and the ground it
has never touched.

WHY THIS EXISTS (blueprint item 3; the AlphaSchema semantic-frontier mechanism)

The desk can say how many hypotheses it tested and how many survived. It could not say WHERE it
tested them. "Exhausted" gets claimed per FAMILY, and a family is one coordinate out of ten: a
docket of 23,627 cells that was 44.8% single-name equities, almost all on H1, almost all in one
session, is not breadth -- it is one region sampled 23,627 times. L1.51 says exhaustion needs
PER-AXIS evidence, and before this organ no artifact on this tree could name a chart, a session,
a mechanism or an economic actor the desk had never once tried. A gap nobody can name is a gap
nobody searches. So: ten axes, one state per cell, and UNMEASURED is a STATE rather than a blank
(L1.28a) -- a cell nothing has ever judged is a measured fact about the search, and it is the
fact this organ is really for.

PRECEDENCE IS STATED, NOT INFERRED. Six sources describe overlapping cells and disagree by
construction -- a live sleeve is also a certificate is also a docket row. LIVE > FORWARD >
CERTIFIED > MEASURED_FAIL > UNMEASURED answers one question: the STRONGEST thing known about this
cell. It is deliberately NOT `libs/research_os/credit.STAGE_VALUE`, which answers how much
PROGRESS a cell represents and puts an unmatured forward clock (0.60) below a clean certificate
(1.00). Both orderings are the desk's; neither is bent to flatter the other.

THE PRIOR RANKS AND NEVER GATES. `libs/research_os/surrogate.py` is reused exactly as written:
additive per-axis empirical Bayes, each axis value shrunk toward the global mean by n/(n+8), plus
a UCB-shaped bonus over the LEAST-observed axis. Its five positional axes are fed
(asset_class, mechanism, information_source, chart, session) -- the five that describe a REGION
rather than one instrument, which is the only level at which an unseen coordinate can inherit
anything. Nothing here refuses a candidate, lowers a bar or shrinks a book.

UNKNOWN IS COUNTED, NEVER GUESSED. `FAMILY_TABLE` maps a family to a mechanism, an information
source and an execution style by hand, from `libs/research/mechanism_ontology.py`,
`libs/research/alpha_schema.py` EVENTS (which carry the PAYER -- the economic actor) and
`side_channels/hypothesis_schema.py` MechanismClass. A family the table does not name is UNKNOWN
and COUNTED. The largest such population is `discovered`, the desk's own generated family, and
that number is the point: a docket dominated by cells with no named mechanism is one the
economic-prior gate cannot defend, and this is where that becomes visible.

Equity cells are RECORDED -- they were judged and they spent the multiplicity budget, and erasing
them would hide the very cost the two-lane order exists to stop. They are never PROPOSED:
`universe_policy.may_hypothesise` gates every proposal.

    python desks/mt5/research/axis_registry.py [--dry-run] [--max-proposals N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EXTERNAL_SURVIVORS = BASE / "data" / "hypotheses" / "external_survivors.json"
GATE_LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
RESEARCH_QUEUE = BASE / "data" / "research_queue.json"
UNIVERSAL_SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SHADOW_STATE = BASE / "reports" / "shadow" / "shadow_state.json"
SLEEVES = BASE / "data" / "sleeves.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
OUT_REPORT = BASE / "reports" / "AXIS_REGISTRY.json"
OUT_CELLS = BASE / "data" / "axis_registry.jsonl"
INTAKE = BASE / "data" / "intelligence" / "axis_registry"

#: A JSON input larger than this is NOT loaded. The box holding the live terminal has 8 GB and a
#: dozen resident python processes; the report says TOO_LARGE rather than pretending it was absent.
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_LEDGER_LINES = 500_000
MAX_PROPOSALS = 60
PROPOSAL_SYMBOLS = 3
EMPTY_REGIONS = 50
#: How the proposal budget splits. Explore takes the largest share because it is the only arm that
#: can reach ground no axis value has ever been paired with.
SHARES = (("global_explore", 0.40), ("learned_exploit", 0.30), ("local_mutate", 0.30))

AXES = ("asset_class", "instrument", "chart", "session", "horizon", "mechanism",
        "information_source", "economic_actor", "regime", "execution_style")
#: The five axes describing a REGION, fed positionally to the surrogate's five-axis coordinate.
#: The other five are DERIVED from these plus the cell's parameters, so ranking on them would
#: double-count the same evidence.
REGION_AXES = ("asset_class", "mechanism", "information_source", "chart", "session")

STATES = ("UNMEASURED", "MEASURED_FAIL", "CERTIFIED", "FORWARD", "LIVE")
STATE_RANK = {s: i for i, s in enumerate(STATES)}
#: State -> the desk's own progress ladder, so one definition of "progress" governs the prior and
#: credit assignment alike.
STATE_STAGE = {"UNMEASURED": "IDEA", "MEASURED_FAIL": "COMPILED", "CERTIFIED": "CERTIFIED",
               "FORWARD": "FORWARD_ENROLLED", "LIVE": "LIVE"}

UNKNOWN = "UNKNOWN"
CHARTS = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
CHART_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}
#: A cell with no declared chart is H1 -- the bare identity every docket row has (`breadth_sweep`
#: writes `timeframe` only when it is NOT H1), so defaulting elsewhere invents an unknown.
DEFAULT_CHART = "H1"
CHART_ALIAS = {"1M": "M1", "5M": "M5", "15M": "M15", "30M": "M30", "1H": "H1", "60": "H1",
               "4H": "H4", "1D": "D1", "DAILY": "D1", "H01": "H1"}
#: `overlap` is recorded but never proposed: `family_call.session_filter` has no window for it and
#: would silently keep every bar, so a proposal naming it would mean `all` while claiming not to.
SESSIONS = ("all", "asia", "london", "ny", "overlap")
PROPOSABLE_SESSIONS = ("all", "asia", "london", "ny")
SESSION_ALIAS = {"asia": "asia", "asian": "asia", "tokyo": "asia", "sydney": "asia",
                 "london": "london", "london_am": "london", "london_pm": "london",
                 "europe": "london", "eu": "london", "frankfurt": "london", "ny": "ny",
                 "new_york": "ny", "newyork": "ny", "us": "ny", "afternoon": "ny", "nyc": "ny",
                 "london_close": "ny", "overlap": "overlap", "london_ny": "overlap",
                 "all": "all", "continuous": "all", "any": "all", "none": "all", "": "all"}

HORIZONS = ("intrabar", "sub_4h", "sub_1d", "multi_day", UNKNOWN)
HOLD_KEYS = ("max_hold", "hold_bars", "ttl_bars", "ttl", "hold", "horizon")
REGIME_KEYS = ("state", "regime", "condition", "band", "vol_state", "liquidity_state",
               "crisis_only", "side_mode", "market_state")
INFORMATION_SOURCES = ("price_only", "cross_asset", "macro", "positioning", "event", "carry",
                       "microstructure", "seasonality", UNKNOWN)

#: Mechanism -> the participant who PAYS, from `alpha_schema.EVENTS['payer']` where the mechanism
#: is one of its events and from `mechanism_ontology.expected_actors` /
#: `hypothesis_schema.Mechanism.participant` otherwise. An edge with no payer is a chart pattern,
#: which is exactly what `economic_prior` refuses.
MECHANISM_ACTOR = {
    "session_handover": "cross_session_risk_transferor",
    "session_information_handoff": "later_session_participant",
    "fx_fixing_flow": "benchmark_tracking_customer", "macro_release": "scheduled_repricer",
    "carry_rollover": "negative_carry_holder", "positioning_crowding": "crowded_speculator",
    "calendar_seasonality": "calendar_constrained_allocator",
    "relative_value_dislocation": "relative_value_arbitrageur",
    "cross_market_lead": "slow_venue_participant", "trend_persistence": "underreacting_holder",
    "range_reversion": "overextended_liquidity_taker", "volatility_shock": "short_gamma_hedger",
    "regime_transition": "stale_regime_positioner", "breakout_liquidity": "stop_loss_holder",
    "execution_microstructure": "liquidity_provider", "gamma_hedging_state": "option_dealer",
    "hedging_demand_close_flow": "close_rebalancing_issuer",
    "inventory_shock": "inventory_laden_dealer", "forced_liquidation": "margin_called_trader",
    UNKNOWN: UNKNOWN,
}

#: (mechanism, information_source, execution_style) -> the families that implement it. EXPLICIT,
#: BY HAND, AND SHORT OF A GUESS. Every registered family in `mt5desk.families` and
#: `mt5desk.families_orthogonal` is here, plus the historic docket names whose constructor is gone
#: -- those cells were judged and the registry must still say what they were about. A name absent
#: from this table maps to UNKNOWN and is counted, never silently bucketed.
_FAMILY_GROUPS: dict[str, str] = {
    "trend_persistence price_only market": "anti_three_bar_momentum h4_momentum momentum_volgate"
                                           " multi_speed_trend trend_ma_cross",
    "trend_persistence price_only stop": "adx_channel_hybrid",
    "trend_persistence price_only limit": "pullback_entry",
    "session_handover price_only market": "asia_momentum clock_transition monday_gap"
                                          " overnight_drift overnight_gap_decay",
    "session_handover price_only limit": "asia_meanrev",
    "session_information_handoff price_only market": "lvc_asia_london session_handoff",
    "hedging_demand_close_flow price_only market": "comex_settlement hedging_demand_close"
                                                   " london_close_momentum",
    "fx_fixing_flow price_only market": "fx_fixing_reversal",
    "macro_release macro market": "macro_conditional macro_gold_yield",
    "macro_release event market": "event_reaction",
    "macro_release cross_asset market": "usd_session_shock",
    "carry_rollover carry market": "carry",
    "positioning_crowding positioning market": "cot_change_fade cot_change_momentum"
                                               " cot_comm_follow cot_net_fade cot_positioning"
                                               " retail_overlap_reversal",
    "calendar_seasonality seasonality market": "calendar_month dow_effect turn_of_month",
    "relative_value_dislocation cross_asset market": "correlation_regime cross_asset_residual"
                                                     " cross_sectional pca_residual"
                                                     " relative_value style_premia",
    "relative_value_dislocation microstructure limit": "triangle",
    "cross_market_lead cross_asset market": "gold_dxy_shock lead_lag",
    "range_reversion price_only limit": "dav_range_filter_adx ict_fvg mean_reversion_bollinger"
                                        " mean_reversion_rsi range_reversion",
    "range_reversion price_only market": "engulfing_reversal pin_bar_reversal",
    "breakout_liquidity price_only stop": "anti_donchian_breakout d1_swing_break level_breakout"
                                          " london_ny_breakout opening_range"
                                          " session_range_breakout",
    "breakout_liquidity price_only limit": "failed_breakout",
    "volatility_shock price_only market": "jump vol_mean_reversion",
    "volatility_shock price_only stop": "d1_inside volatility_squeeze",
    "regime_transition price_only market": "drawdown_conditional regime_transition"
                                           " vol_transition",
    "execution_microstructure microstructure market": "liquidity_regime orderflow_imbalance",
    "execution_microstructure microstructure limit": "execution_state moat_spread_window"
                                                     " spread_state",
    "gamma_hedging_state microstructure market": "liquidity_gamma_reversal",
    "inventory_shock microstructure market": "volume_spike",
    # NO MECHANISM NAMED, AND THAT IS THE MEASUREMENT. `discovered` is the desk's own generated
    # family and dominates the docket; `generic`/`formula`/`ensemble`/`joint_genome` are spec
    # constructors. All map to UNKNOWN so the count is visible rather than assumed away.
    f"{UNKNOWN} price_only market": "discovered",
    f"{UNKNOWN} price_only {UNKNOWN}": "ensemble formula generic joint_genome",
}
FAMILY_TABLE: dict[str, tuple[str, str, str]] = {}
for _key, _fams in _FAMILY_GROUPS.items():
    _mech, _info, _style = _key.split()
    for _fam in _fams.split():
        FAMILY_TABLE[_fam] = (_mech, _info, _style)

#: Constructors that build families from a spec rather than being one -- never proposed.
NOT_A_FAMILY = frozenset({"generic", "formula", "ensemble", "cross_sectional", "joint_genome"})

RULE = ("a cell is UNMEASURED until a source says otherwise, the strongest source wins "
        "(LIVE>FORWARD>CERTIFIED>MEASURED_FAIL>UNMEASURED), an unmapped family is UNKNOWN and "
        "counted, and the prior ranks regions it may never gate")


# ------------------------------------------------------------------ tolerant reading
def _read_json(path: Path, note: dict[str, str]) -> Any:
    """Parse `path`, or record exactly why it produced nothing. Never raises."""
    try:
        size = path.stat().st_size
    except OSError:
        note[path.name] = "ABSENT"
        return None
    if size > MAX_INPUT_BYTES:
        note[path.name] = f"TOO_LARGE({size})"
        return None
    try:
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        note[path.name] = f"UNREADABLE({type(exc).__name__})"
        return None
    note[path.name] = "READ"
    return doc


def _read_jsonl(path: Path, note: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8-sig") as fh:
            for i, raw in enumerate(fh):
                if i >= MAX_LEDGER_LINES:
                    note[path.name] = f"TRUNCATED({MAX_LEDGER_LINES})"
                    return rows
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        note[path.name] = "ABSENT"
        return rows
    note[path.name] = "READ"
    return rows


# ------------------------------------------------------------------ axis derivation
def _tok(value: Any) -> str:
    return "_".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())


def asset_class_of(symbol: str) -> str:
    """The broker registry's class for `symbol`, as a token; UNKNOWN when it has none."""
    try:
        from research.universe_policy import asset_class_of as _ac
        return _tok(_ac(symbol)) or UNKNOWN
    except Exception:
        return UNKNOWN


def may_hypothesise(symbol: str) -> bool:
    """True only for instruments whose edge is sought statistically (the two-lane order)."""
    try:
        from research.universe_policy import may_hypothesise as _mh
        return bool(_mh(symbol))
    except Exception:
        return False


def normalise_chart(value: Any) -> str:
    """A timeframe as one of `CHARTS`; a missing chart is H1, an unreadable one UNKNOWN."""
    raw = str(value or "").strip().upper().replace(" ", "")
    if not raw:
        return DEFAULT_CHART
    raw = CHART_ALIAS.get(raw, raw)
    return raw if raw in CHARTS else UNKNOWN


def normalise_session(value: Any) -> str:
    """A session as one of `SESSIONS`; an unmapped non-empty token is UNKNOWN."""
    key = _tok(value)
    if key in SESSION_ALIAS:
        return SESSION_ALIAS[key]
    return UNKNOWN if key else "all"


def classify_family(family: Any) -> tuple[str, str, str]:
    """(mechanism, information_source, execution_style) for a family, or three UNKNOWNs."""
    return FAMILY_TABLE.get(_tok(family), (UNKNOWN, UNKNOWN, UNKNOWN))


def horizon_of(chart: str, params: dict[str, Any] | None) -> str:
    """The holding bucket: a declared hold in bars against the chart, else the chart itself."""
    params = params or {}
    per_bar = CHART_MINUTES.get(chart)
    minutes: float | None = None
    days = params.get("hold_days") or params.get("horizon_days")
    if isinstance(days, (int, float)) and not isinstance(days, bool) and days > 0:
        minutes = float(days) * 1440.0
    else:
        for key in HOLD_KEYS:
            bars = params.get(key)
            if isinstance(bars, (int, float)) and not isinstance(bars, bool) and bars > 0:
                minutes = float(bars) * float(per_bar or CHART_MINUTES[DEFAULT_CHART])
                break
    if minutes is None:
        if chart in ("M1", "M5", "M15"):
            return "intrabar"
        if chart in ("M30", "H1"):
            return "sub_4h"
        if chart == "H4":
            return "sub_1d"
        return "multi_day" if chart == "D1" else UNKNOWN
    if per_bar and minutes <= per_bar:
        return "intrabar"
    if minutes < 240:
        return "sub_4h"
    return "sub_1d" if minutes < 1440 else "multi_day"


def regime_of(params: dict[str, Any] | None, hint: Any = None) -> str:
    """The state the cell is CONDITIONAL on, or `unconditional` when it is always on."""
    tok = _tok(hint)
    if tok and tok not in ("none", "null", "all", "continuous"):
        return tok
    for key in REGIME_KEYS:
        value = (params or {}).get(key)
        if value is None or value is False or value == "" or value == []:
            continue
        if isinstance(value, str):
            return _tok(value) or key
        return f"{key}_conditional"
    return "unconditional"


def execution_style_of(exec_field: Any, family: Any) -> str:
    """`market`, `stop` or `limit` -- the exec field first, the family's own habit second."""
    token = _tok(exec_field)
    for style in ("market", "stop", "limit"):
        if style in token:
            return style
    return classify_family(family)[2]


def axis_cell(symbol: Any, family: Any, params: dict[str, Any] | None = None,
              timeframe: Any = None, session: Any = None, exec_field: Any = None,
              regime_hint: Any = None) -> dict[str, str]:
    """The ten axes of one cell. Every axis resolves to a token; none is ever blank."""
    params = params if isinstance(params, dict) else {}
    mech, info, _ = classify_family(family)
    chart = normalise_chart(timeframe if timeframe is not None else params.get("timeframe"))
    sess = normalise_session(session if session is not None else params.get("session"))
    return {"asset_class": asset_class_of(symbol),
            "instrument": str(symbol or UNKNOWN).strip().upper() or UNKNOWN,
            "chart": chart, "session": sess, "horizon": horizon_of(chart, params),
            "mechanism": mech, "information_source": info,
            "economic_actor": MECHANISM_ACTOR.get(mech, UNKNOWN),
            "regime": regime_of(params, regime_hint),
            "execution_style": execution_style_of(exec_field, family)}


def cell_id(axes: dict[str, str]) -> str:
    """A stable id for the ten-axis coordinate -- the axes ARE the identity."""
    raw = "|".join(str(axes.get(a, UNKNOWN)) for a in AXES)
    return hashlib.blake2s(raw.encode("utf-8"), digest_size=8).hexdigest()


def region_key(axes: dict[str, str]) -> str:
    """The five-axis region coordinate, in the order the surrogate reads positionally."""
    return "|".join(str(axes.get(a, UNKNOWN)) for a in REGION_AXES)


def _param_name(chunk: str) -> str:
    """The parameter NAME out of `1.5_wait_bars` (a value then a name) without mangling
    `peer_symbol` (one name that happens to contain an underscore). A leading run is dropped only
    when it LOOKS like a value -- digits or brackets -- never because a name has an underscore."""
    while "_" in chunk:
        head, _, rest = chunk.partition("_")
        if not head or not any(c.isdigit() or c in "[](),'\"" for c in head):
            break
        chunk = rest
    return _tok(chunk)


def parse_shadow_key(key: str) -> dict[str, Any]:
    """Split a forward-clock key into what it actually says.

    Four shapes are live on this tree: `XAUUSD.asia#rr=1.5`, `GBPMXN.overnight_gap_decay.asia`,
    `EURJPY.asia.NORMAL_DAY` and `USDMXN.overnight_gap_decay.p=44136fa355b3678a`. The second
    segment is a SELECTOR in the first and third and a FAMILY in the second, and reading it wrong
    makes a session look like a family forever.

    A SEGMENT CARRYING `=` IS PARAMETERS, NEVER A REGIME. Measured on this tree 2026-09-16:
    reading it as one put 646 cells at regime `p=44136fa355b3678a` and 926 more at other
    fingerprints -- 1,569 distinct "regimes" for 5,361 cells, an axis with one value per cell,
    which is an axis that measures nothing. A parameter hash is a spelling of the cell, not a
    state of the market it is conditional on.
    """
    head, _, tail = str(key or "").partition("#")
    parts = [p for p in head.split(".") if p]
    out: dict[str, Any] = {"symbol": parts[0] if parts else "", "family": "", "session": None,
                           "regime": None, "param_names": []}
    rest = parts[1:]
    if rest and _tok(rest[0]) in SESSION_ALIAS:
        out["session"], rest = rest[0], rest[1:]
    elif rest and "=" not in rest[0]:
        out["family"], rest = rest[0], rest[1:]
        if rest and _tok(rest[0]) in SESSION_ALIAS:
            out["session"], rest = rest[0], rest[1:]
    for seg in rest:
        if "=" not in seg and out["regime"] is None:
            out["regime"] = seg
    names = [n for piece in [*(s for s in rest if "=" in s), tail] if piece
             for n in (_param_name(c) for c in piece.split("=")[:-1]) if n.isidentifier()]
    out["param_names"] = names
    return out


# ------------------------------------------------------------------ the sources
def _add(cells: dict[str, dict[str, Any]], axes: dict[str, str], state: str, source: str) -> None:
    """Record one observation of a cell, keeping the STRONGEST state any source claims."""
    cid = cell_id(axes)
    row = cells.get(cid)
    if row is None:
        cells[cid] = {"cell_id": cid, **axes, "state": state, "sources": [source]}
        return
    if source not in row["sources"]:
        row["sources"].append(source)
    if STATE_RANK[state] > STATE_RANK[row["state"]]:
        row["state"] = state


def collect_cells(note: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Every cell the desk has judged, certified, run forward or traded, on ten axes."""
    note = note if note is not None else {}
    cells: dict[str, dict[str, Any]] = {}

    docket = _read_json(EXTERNAL_SURVIVORS, note)
    for row in docket if isinstance(docket, list) else []:
        if isinstance(row, dict):
            _add(cells, axis_cell(row.get("symbol"), row.get("family"), row.get("params"),
                                  row.get("timeframe")), "UNMEASURED", "external_survivors")

    queue = _read_json(RESEARCH_QUEUE, note)
    for row in queue if isinstance(queue, list) else []:
        if not isinstance(row, dict):
            continue
        state = "MEASURED_FAIL" if "REJECT" in str(row.get("status") or "").upper() \
            else "UNMEASURED"
        _add(cells, axis_cell(row.get("symbol") or (row.get("params") or {}).get("symbol"),
                              row.get("family"), row.get("params")), state, "research_queue")

    for row in _read_jsonl(GATE_LEDGER, note):
        parsed = parse_shadow_key(str(row.get("cell") or ""))
        _add(cells, axis_cell(row.get("sym") or parsed["symbol"],
                              row.get("family") or parsed["family"], None,
                              session=parsed["session"], regime_hint=parsed["regime"]),
             "CERTIFIED" if row.get("passed") else "MEASURED_FAIL", "gate_verdict_ledger")

    universal = _read_json(UNIVERSAL_SURVIVORS, note)
    survivors = universal.get("survivors") if isinstance(universal, dict) else None
    for row in survivors.values() if isinstance(survivors, dict) else []:
        spec = row.get("shadow_spec") if isinstance(row, dict) else None
        if not isinstance(spec, dict):
            continue
        _add(cells, axis_cell(spec.get("symbol") or row.get("sym"), spec.get("family"),
                              spec.get("params"), spec.get("timeframe"), spec.get("selector"),
                              regime_hint=spec.get("condition")),
             "CERTIFIED", "UNIVERSAL_SURVIVORS")

    shadow = _read_json(SHADOW_STATE, note)
    for key, row in shadow.items() if isinstance(shadow, dict) else []:
        if not isinstance(row, dict):
            continue
        parsed = parse_shadow_key(str(key))
        # A clock that was REFUSED or BLOCKED never produced a forward observation. Calling that
        # FORWARD would let an enrolment the desk never ran read as evidence that it did.
        ran = bool(row.get("n")) or str(row.get("status") or "").upper().startswith(
            ("ACTIVE", "PROMOTION"))
        _add(cells, axis_cell(parsed["symbol"], parsed["family"],
                              dict.fromkeys(parsed["param_names"], True),
                              session=parsed["session"], regime_hint=parsed["regime"]),
             "FORWARD" if ran else "MEASURED_FAIL", "shadow_state")

    doc = _read_json(SLEEVES, note)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        sess = row.get("session") or row.get("selector") or row.get("window")
        _add(cells, axis_cell(row.get("symbol"), row.get("family"), row, row.get("timeframe"),
                              sess, row.get("exec"), regime_hint=row.get("state")),
             "LIVE" if str(row.get("status") or "").upper() == "LIVE" else "FORWARD", "sleeves")
    return cells


# ------------------------------------------------------------------ the tensor
OCCUPANCY_PAIRS = (("asset_class", "mechanism"), ("chart", "session"),
                   ("mechanism", "information_source"), ("asset_class", "information_source"))


def occupancy(cells: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, int]]]:
    """Per-axis-pair coverage with a count per state -- the tensor, flattened to what is read."""
    out: dict[str, dict[str, dict[str, int]]] = {}
    for a, b in OCCUPANCY_PAIRS:
        pair: dict[str, dict[str, int]] = {}
        for row in cells.values():
            cell = pair.setdefault(f"{row.get(a, UNKNOWN)}|{row.get(b, UNKNOWN)}", {})
            cell[row["state"]] = cell.get(row["state"], 0) + 1
        out[f"{a}x{b}"] = dict(sorted(pair.items()))
    return out


def axis_counts(cells: dict[str, dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Every value seen on every axis, with its cell count, most common first."""
    return {a: dict(Counter(str(r.get(a, UNKNOWN)) for r in cells.values()).most_common())
            for a in AXES}


def unknown_counts(cells: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Cells whose axis could not be derived. Counted, never guessed, never smoothed away."""
    return {a: sum(1 for r in cells.values() if r.get(a) == UNKNOWN) for a in AXES}


# ------------------------------------------------------------------ what can be proposed
def registered_families() -> frozenset[str]:
    """Every family the desk can actually call, read the way `breadth_sweep` reads it."""
    try:
        from mt5desk import families as fam_mod
        from mt5desk import families_orthogonal as fo
    except Exception:
        return frozenset()
    names: set[str] = set()
    for name, entry in (getattr(fam_mod, "FAMILY_REGISTRY", {}) or {}).items():
        fn = entry.get("func") if isinstance(entry, dict) else entry
        if callable(fn):
            names.add(str(name))
    for name, fn in (getattr(fo, "ORTHOGONAL_FAMILIES", {}) or {}).items():
        if callable(fn):
            names.add(str(name))
    return frozenset(names - NOT_A_FAMILY)


def _banned(family: str) -> bool:
    try:
        from research.family_policy import family_banned
        return bool(family_banned(family))
    except Exception:
        return False


def compiler_vocab() -> frozenset[str]:
    """Families the intake compiler admits by name. A PREFERENCE, never a filter: the bound is
    the compiler's and it moves, and a proposal outside it still reaches the deepening worker."""
    try:
        from research.miner_candidate_compiler import _FAMILY_VOCAB
        return frozenset(_FAMILY_VOCAB)
    except Exception:
        return frozenset()


def instruments_by_class() -> dict[str, list[str]]:
    """Hypothesis-lane instruments per asset class, deepest history first (a liquidity proxy)."""
    registry = _read_json(UNIVERSE, {})
    out: dict[str, list[tuple[int, str]]] = {}
    for sym, row in registry.items() if isinstance(registry, dict) else []:
        if not isinstance(row, dict) or not may_hypothesise(sym):
            continue
        out.setdefault(asset_class_of(sym), []).append((-int(row.get("bars") or 0),
                                                        str(sym).upper()))
    return {k: [s for _, s in sorted(v)] for k, v in out.items()}


def family_for(mechanism: str, information_source: str, families: frozenset[str],
               prefer: frozenset[str], salt: str = "") -> str | None:
    """A registered, unbanned family that implements this region, or None.

    SPREAD DETERMINISTICALLY, NOT ALPHABETICALLY. Taking `pool[0]` gave every breakout region on
    every asset class the same family, which is a breadth organ proposing one idea sixty times.
    The salt is the region coordinate, so the choice is stable across runs and varies across
    regions -- and the families the intake compiler admits by name are preferred within the pool,
    because a proposal it cannot read lands nowhere.
    """
    pool = sorted(f for f, (m, i, _) in FAMILY_TABLE.items()
                  if m == mechanism and i == information_source and f in families
                  and not _banned(f))
    if not pool:
        return None
    head = [f for f in pool if f in prefer] or pool
    idx = int.from_bytes(hashlib.blake2s(salt.encode("utf-8"), digest_size=2).digest(), "big")
    return head[idx % len(head)]


# ------------------------------------------------------------------ the prior
def fit_prior(cells: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], str]:
    """Fit the desk's own surrogate on the regions it has already spent trials in."""
    rows = [{"coordinate": region_key(r), "stage": STATE_STAGE.get(r["state"], "IDEA")}
            for r in cells.values()]
    try:
        from libs.research_os import surrogate
        return surrogate.fit(rows), "libs/research_os/surrogate.py"
    except Exception as exc:
        return ({"global": 0.0, "effects": {}, "n": 0,
                 "why": f"UNMEASURED: surrogate unimportable ({type(exc).__name__})"}, UNKNOWN)


def score_region(model: dict[str, Any], coordinate: str) -> dict[str, Any]:
    """The surrogate's score for a region, or a flat UNMEASURED score when it is unreachable."""
    try:
        from libs.research_os import surrogate
        return surrogate.score(model, coordinate)
    except Exception:
        return {"coordinate": coordinate, "predicted": 0.0, "exploration_bonus": 0.0,
                "rank_score": 0.0, "least_observed_axis_n": 0.0, "contributions": {}}


def candidate_regions(cells: dict[str, dict[str, Any]],
                      families: frozenset[str]) -> list[tuple[str, ...]]:
    """Every (asset_class, mechanism, information_source, chart, session) the desk COULD run.

    Bounded by construction: only classes present in the broker registry and in the hypothesis
    lane, only (mechanism, information_source) pairs a registered family implements, and no
    session on D1 -- daily bars carry no session, so those cells cannot be built at all.
    """
    classes = sorted(instruments_by_class()) or sorted(
        {r["asset_class"] for r in cells.values() if r["asset_class"] != UNKNOWN})
    pairs = sorted({(m, i) for f, (m, i, _) in FAMILY_TABLE.items()
                    if m != UNKNOWN and i != UNKNOWN and f in families})
    return [(klass, mech, info, chart, sess)
            for klass in classes for mech, info in pairs for chart in CHARTS
            for sess in (("all",) if chart == "D1" else PROPOSABLE_SESSIONS)]


def empty_regions(cells: dict[str, dict[str, Any]], model: dict[str, Any],
                  families: frozenset[str], limit: int = EMPTY_REGIONS) -> list[dict[str, Any]]:
    """The unoccupied regions, ranked by the prior. An empty region is the whole point."""
    occupied = {region_key(r) for r in cells.values()}
    scored: list[dict[str, Any]] = []
    for region in candidate_regions(cells, families):
        coord = "|".join(region)
        if coord in occupied:
            continue
        s = score_region(model, coord)
        scored.append({"region": dict(zip(REGION_AXES, region, strict=False)),
                       "coordinate": coord, "rank_score": s["rank_score"],
                       "predicted": s["predicted"],
                       "exploration_bonus": s["exploration_bonus"]})
    scored.sort(key=lambda r: (-r["rank_score"], r["coordinate"]))
    return scored[:limit]


# ------------------------------------------------------------------ selection
def _proposal(region: dict[str, str], mode: str, why: str, families: frozenset[str],
              prefer: frozenset[str], by_class: dict[str, list[str]],
              rank_score: float) -> dict[str, Any] | None:
    """One intake row, or None when the region cannot be built, has no registered family, or has
    no priced hypothesis-lane instrument."""
    if region["session"] not in PROPOSABLE_SESSIONS or region["chart"] not in CHARTS:
        return None                 # `overlap` and UNKNOWN have no window the call path can run
    fam = family_for(region["mechanism"], region["information_source"], families, prefer,
                     "|".join(region[a] for a in REGION_AXES))
    symbols = [s for s in by_class.get(region["asset_class"], [])
               if may_hypothesise(s)][:PROPOSAL_SYMBOLS]
    if fam is None or not symbols:
        return None
    params: dict[str, Any] = {}
    if region["chart"] != DEFAULT_CHART:
        params["timeframe"] = region["chart"]
    if region["session"] != "all":
        params["session"] = region["session"]
    return {"kind": "hypothesis", "family": fam, "symbols": symbols, "params": params,
            "timeframe": region["chart"], "session": region["session"],
            "source": "axis_registry", "why": why,
            "axis_cell": axis_cell(symbols[0], fam, params, region["chart"], region["session"]),
            "selector_mode": mode, "rank_score": round(float(rank_score), 5)}


def select(cells: dict[str, dict[str, Any]], model: dict[str, Any], regions: list[dict[str, Any]],
           max_proposals: int = MAX_PROPOSALS) -> dict[str, list[dict[str, Any]]]:
    """Three arms on one budget: unexplored ground, the prior's best ground, and one-axis
    mutations of the cells that already work. They are separate because they fail differently --
    explore alone never compounds, exploit alone collapses onto what the desk already believes.

    IT DOES NOT RE-DONATE THE SAME SIXTY FOREVER. The same inputs give the same rows by design
    (the family choice is salted by the coordinate, not randomised), but once the compiler lands
    a proposal the region stops being empty, so the next run reaches the next-best ground. A run
    that keeps proposing identical cells is therefore evidence the intake is NOT reading them."""
    families, prefer = registered_families(), compiler_vocab()
    by_class = instruments_by_class()
    budget = max(0, int(max_proposals))
    out: dict[str, list[dict[str, Any]]] = {m: [] for m, _ in SHARES}
    caps = {m: max(1, int(budget * share)) if budget else 0 for m, share in SHARES}
    seen = {region_key(r) for r in cells.values()}

    def take(mode: str, region: dict[str, str], coord: str, why: str, score: float) -> None:
        if coord in seen or len(out[mode]) >= caps[mode]:
            return
        row = _proposal(region, mode, why, families, prefer, by_class, score)
        if row is not None:
            out[mode].append(row)
            seen.add(coord)

    for r in regions:
        take("global_explore", r["region"], r["coordinate"],
             f"UNOCCUPIED: no cell the desk has ever judged sits at {r['coordinate']}; the prior "
             f"ranks it {r['rank_score']} (explore bonus {r['exploration_bonus']})",
             r["rank_score"])
    for r in sorted(regions, key=lambda x: (-x["predicted"], x["coordinate"])):
        take("learned_exploit", r["region"], r["coordinate"],
             f"LEARNED: the fitted per-axis effects put {r['coordinate']} at {r['predicted']} "
             f"before any exploration bonus -- the prior's own best untested ground",
             r["predicted"])

    strong = sorted((r for r in cells.values() if r["state"] in ("LIVE", "FORWARD", "CERTIFIED")),
                    key=lambda r: (-STATE_RANK[r["state"]], r["cell_id"]))
    for row in strong:
        if len(out["local_mutate"]) >= caps["local_mutate"]:
            break
        for axis, values in (("chart", CHARTS), ("session", PROPOSABLE_SESSIONS)):
            for value in values:
                region = {a: row[a] for a in REGION_AXES}
                region[axis] = value
                coord = "|".join(region[a] for a in REGION_AXES)
                if value == row[axis] or coord in seen:
                    continue
                if region["chart"] == "D1" and region["session"] != "all":
                    continue
                take("local_mutate", region, coord,
                     f"MUTATION: {row['instrument']} holds state {row['state']} at "
                     f"{region_key(row)}; this moves ONE axis ({axis} -> {value}) onto ground no "
                     f"cell occupies", score_region(model, coord)["rank_score"])
                break
    total = sum(len(v) for v in out.values())
    while total > budget:
        out[max(out, key=lambda m: len(out[m]))].pop()
        total -= 1
    return out


# ------------------------------------------------------------------ build and write
def build(max_proposals: int = MAX_PROPOSALS) -> tuple[dict[str, Any], dict[str, dict[str, Any]],
                                                       list[dict[str, Any]]]:
    """(report, cells, proposals). Reads everything tolerantly; never raises on a missing input."""
    note: dict[str, str] = {}
    max_proposals = min(int(max_proposals), MAX_PROPOSALS)   # the ceiling is structural, not a flag
    cells = collect_cells(note)
    model, prior_source = fit_prior(cells)
    families = registered_families()
    regions = empty_regions(cells, model, families)
    selection = select(cells, model, regions, max_proposals)
    proposals = [p for mode, _ in SHARES for p in selection[mode]]
    why_none = "" if proposals else (
        "no proposal: " + ("no registered family could be imported" if not families else
                           "every candidate region is already occupied, or no hypothesis-lane "
                           "instrument is priced for its asset class"))
    report = {"at": datetime.now(UTC).isoformat(), "n_cells": len(cells),
              "by_state": {s: sum(1 for r in cells.values() if r["state"] == s) for s in STATES},
              "axes": axis_counts(cells), "occupancy": occupancy(cells),
              "empty_regions": regions, "unknown_counts": unknown_counts(cells),
              "selection": selection, "rule": RULE, "inputs": note,
              "prior": {"source": prior_source, "n": model.get("n"),
                        "global": model.get("global"), "why": model.get("why")},
              "families_registered": len(families), "family_table_size": len(FAMILY_TABLE),
              "candidate_regions": len(candidate_regions(cells, families)),
              "why_no_proposals": why_none}
    return report, cells, proposals


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write(report: dict[str, Any], cells: dict[str, dict[str, Any]],
          proposals: list[dict[str, Any]]) -> Path:
    """Report, cell ledger and the intake donation -- all three atomic, in that order."""
    _atomic_write(OUT_REPORT, json.dumps(report, indent=1, default=str))
    lines = [json.dumps({"cell_id": r["cell_id"], **{a: r[a] for a in AXES},
                         "state": r["state"], "sources": sorted(r["sources"])}, default=str)
             for r in sorted(cells.values(), key=lambda r: r["cell_id"])]
    _atomic_write(OUT_CELLS, "\n".join(lines) + ("\n" if lines else ""))
    donation = INTAKE / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    _atomic_write(donation, json.dumps(proposals, indent=1, default=str))
    return donation


def summary(report: dict[str, Any], proposals: list[dict[str, Any]], target: str) -> list[str]:
    """Exactly six lines: what was read, what is known, what is unknown, what is next."""
    unknowns = report["unknown_counts"]
    top = report["empty_regions"][0]["coordinate"] if report["empty_regions"] else "none"
    return [
        f"AXIS REGISTRY {report['at']}  inputs: "
        + ", ".join(f"{k}={v}" for k, v in report["inputs"].items()),
        f"  cells {report['n_cells']} on {len(AXES)} axes  "
        + "  ".join(f"{s}={report['by_state'][s]}" for s in STATES),
        "  axis values  " + "  ".join(f"{a}={len(report['axes'][a])}" for a in AXES),
        "  UNKNOWN  " + ("  ".join(f"{a}={unknowns[a]}" for a in AXES if unknowns[a]) or "none"),
        f"  empty regions {len(report['empty_regions'])} of "
        f"{report['candidate_regions']} candidates; best {top}",
        f"  proposals {len(proposals)} ("
        + " ".join(f"{m}={len(report['selection'].get(m) or [])}" for m, _ in SHARES)
        + f") -> {target}",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="information-axis registry and occupancy tensor")
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    ap.add_argument("--max-proposals", type=int, default=MAX_PROPOSALS,
                    help=f"cap the intake donation (default and hard ceiling {MAX_PROPOSALS})")
    args = ap.parse_args(argv)
    report, cells, proposals = build(min(int(args.max_proposals), MAX_PROPOSALS))
    target = "DRY RUN (nothing written)" if args.dry_run else str(
        write(report, cells, proposals))
    for line in summary(report, proposals, target):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
