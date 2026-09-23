"""THE QUALITY-DIVERSITY FRONTIER: one elite per behavioural niche, so what grows is n_eff.

WHY THIS EXISTS (the GoAnt mechanism, principal 2026-09-16)

The leaderboard was XAU breakout v1, XAU breakout v2, XAU breakout v3. Each was an honest
improvement on the one before it, each passed the same ten gates, and the book held three
near-copies of one bet. A ranked list has exactly one equilibrium: the family that scores best
takes the whole budget, and the desk spends the next month buying correlation it already owns.
Sleeve count went up. n_eff did not.

So the budget is kept per NICHE, not per SCORE. A niche is WHO PAYS, WHAT FORCES THEM, WHERE THE
INFORMATION COMES FROM, THE MECHANISM, THE ASSET CLASS, THE HORIZON, THE SESSION and THE REGIME --
eight of `desks/mt5/research/axis_registry.py`'s ten axes, the eight that describe a BEHAVIOUR
rather than a spelling. (`instrument` and `execution_style` are left out on purpose: EURUSD and
GBPUSD carry the same behaviour, and a limit order is a way of taking a bet, not a different bet.)
One elite is retained per niche, so a fourth XAU breakout no longer displaces a mediocre carry
cell -- it is not competing with it, it competes with the three XAU breakouts.

THREE OF THE EIGHT AXES ARE DERIVED, AND THAT IS SAID OUT LOUD. `economic_actor` and `constraint`
are functions of `mechanism`; `information_source` moves with the family table. They multiply no
niches. They are in the key because a niche nobody can READ is a niche nobody defends: "nobody has
ever asked what the margin-called trader pays in Asian-session metals" is an instruction, and a
hash is not. So adjacency is computed over the axes that move INDEPENDENTLY (`FREE_AXES`), or a
one-mechanism step would read as a three-axis leap and the explorer would find nothing adjacent to
anything.

QUALITY IS EVIDENCE-RANKED BEFORE IT IS SCORE-RANKED. A forward clock with exp_r over n trades
beats an in-sample t whatever the magnitudes, and an in-sample t beats "reached deflated_sharpe
and stopped": `BASIS_RANK` decides first and the score only orders within a tier. Comparing the
numbers instead -- letting a 3.4 in-sample t outrank a 0.11 forward exp_r -- is how a desk ends up
holding the cells that fitted best rather than the cells that paid.

THREE WORKERS, ONE BUDGET, AND THEY FAIL DIFFERENTLY. EXPLORER takes EMPTY niches one free axis
from an occupied one -- the only arm that can add a niche. EXPLOITER mutates the elite of a niche
that improved recently -- the only arm that compounds. CONNECTOR carries one niche's elite family
onto another niche's session and horizon where the two share an asset class or a mechanism -- the
only arm that crosses. Explore alone never compounds; exploit alone rebuilds the leaderboard;
connect alone has nothing to connect. An arm with no work leaves its share unspent.

WHAT IT REFUSES: families the desk cannot call, the event lane (single-name equities are traded on
news, never hunted), unnamed mechanisms (`economic_prior` is the gauntlet's first gate), sessions
and charts the call path cannot run, and every regime but `unconditional` -- the proposal path
builds no regime condition, so a row naming a state it cannot switch on would claim a conditioning
it does not have. That makes `regime` read-only for proposals, better said than worked around.

    python desks/mt5/research/qd_frontier.py [--dry-run] [--max-proposals N]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import axis_registry as ar
    _AR_ERROR = ""
except Exception as exc:                        # pragma: no cover - the sibling is always there
    ar = None                                   # type: ignore[assignment]
    _AR_ERROR = f"{type(exc).__name__}: {exc}"

AXIS_REPORT = BASE / "reports" / "AXIS_REGISTRY.json"
AXIS_CELLS = BASE / "data" / "axis_registry.jsonl"
GATE_LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
UNIVERSAL_SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
SHADOW_STATE = BASE / "reports" / "shadow" / "shadow_state.json"
SLEEVES = BASE / "data" / "sleeves.json"
OUT_REPORT = BASE / "reports" / "QD_FRONTIER.json"
OUT_MAP = BASE / "data" / "qd_mental_map.json"
INTAKE = BASE / "data" / "intelligence" / "qd_frontier"

UNKNOWN = "UNKNOWN"
#: The behavioural coordinate: eight of the registry's ten.
NICHE_AXES = ("economic_actor", "constraint", "information_source", "mechanism",
              "asset_class", "horizon", "session", "regime")
#: These four move TOGETHER -- all are read off the family table's mechanism entry.
MECHANISM_BUNDLE = ("mechanism", "information_source", "economic_actor", "constraint")
#: What a proposal can move by itself; `mechanism` here means the whole bundle above.
FREE_AXES = ("mechanism", "asset_class", "horizon", "session", "regime")

WORKERS = ("explorer", "exploiter", "connector")
DEFAULT_PROPOSALS = 45
#: The structural ceiling, shared with `axis_registry`: both organs donate into one compiler and
#: one run may not flood it. It lives in `build`, not the CLI -- a bound a flag can argue away is
#: not a bound.
MAX_PROPOSALS = 60
PROPOSAL_SYMBOLS = 3
#: How long an elite counts as freshly improved: one weekend plus a trading day, so a Friday
#: improvement is still exploitable on Monday.
IMPROVED_WINDOW_H = 72
IMPROVE_EPS = 1e-9              #: float noise on a re-read of the same artifacts is no improvement
CONNECTOR_POOL = 40             #: bound on the O(n^2) pairing: the strongest elites only
REPORT_NICHES = 400             #: rows in the report; the map on disk keeps every niche
EXPLOIT_PER_NICHE = 3           #: turns one niche takes before the next gets the exploiter's arm

PROPOSABLE_SESSIONS = ("all", "asia", "london", "ny")
PROPOSABLE_HORIZONS = ("intrabar", "sub_4h", "sub_1d", "multi_day")
#: `axis_registry.horizon_of` read backwards: the chart a proposal uses to REACH a horizon.
HORIZON_CHART = {"intrabar": "M15", "sub_4h": "H1", "sub_1d": "H4", "multi_day": "D1"}
PROPOSAL_REGIME = "unconditional"

#: mechanism -> WHAT FORCES THE ACTOR TO PAY, by hand, from the payer clauses in
#: `libs/research/alpha_schema.EVENTS` and `Mechanism.constraint` in
#: `side_channels/hypothesis_schema.py`. Keyed exactly like `axis_registry.MECHANISM_ACTOR`, and a
#: test pins the two together so neither grows a mechanism the other has never heard of.
MECHANISM_CONSTRAINT = {
    "session_handover": "must_transfer_risk_across_a_closed_book",
    "session_information_handoff": "must_price_a_session_it_did_not_trade",
    "fx_fixing_flow": "must_trade_at_the_published_benchmark",
    "forced_flow": "must_transact_inside_a_known_calendar_window",
    "macro_release": "must_reprice_on_a_scheduled_print",
    "carry_rollover": "must_pay_the_rate_differential_daily",
    "positioning_crowding": "must_exit_a_crowded_book",
    "calendar_seasonality": "must_act_on_a_calendar_it_does_not_choose",
    "relative_value_dislocation": "must_close_a_spread_at_a_limit",
    "cross_market_lead": "must_wait_for_the_slower_venue",
    "trend_persistence": "must_accumulate_an_opinion_over_time",
    "range_reversion": "must_take_liquidity_at_the_extreme",
    "volatility_shock": "must_hedge_short_gamma_into_the_move",
    "regime_transition": "must_re_estimate_a_state_it_priced_as_stable",
    "breakout_liquidity": "must_stop_out_at_a_published_level",
    "execution_microstructure": "must_quote_both_sides_continuously",
    "gamma_hedging_state": "must_delta_hedge_an_option_book",
    "hedging_demand_close_flow": "must_rebalance_at_the_close",
    "inventory_shock": "must_offload_inventory_it_did_not_want",
    "forced_liquidation": "must_close_on_a_margin_call",
    UNKNOWN: UNKNOWN,
}

#: The ten gates in the order the gauntlet runs them, from a certificate's own `gates` block. A
#: cell's depth is how far down this it reached before it stopped.
GATE_LADDER = ("economic_prior", "in_sample_screen", "deflated_sharpe", "pbo",
               "reality_check_spa", "cpcv", "walk_forward", "stress_costs", "lockbox",
               "expected_value")
GATE_DEPTH = {g: round((i + 1) / len(GATE_LADDER), 4) for i, g in enumerate(GATE_LADDER)}

#: EVIDENCE BEATS MAGNITUDE. The tier decides; the score only orders within a tier.
FORWARD_BASIS = "forward_exp_r_sqrt_n"
BASIS_RANK = {FORWARD_BASIS: 3, "in_sample_t": 2, "in_sample_sharpe": 2, "gate_depth": 1,
              "UNMEASURED": 0}

RULE = ("one elite per behavioural niche, never one leaderboard: quality is ranked by evidence "
        "basis first (forward exp_r*sqrt(n) > in-sample t > deepest gate reached) and by score "
        "only within a basis; the explorer takes EMPTY niches one free axis from an occupied one, "
        "the exploiter mutates elites that improved inside the window, the connector carries an "
        "elite across a shared asset class or mechanism; an empty niche is a measurement")


# ------------------------------------------------------------------ tolerant reading
def _num(value: Any) -> float | None:
    """A real number, or None. `True` is not 1.0 -- a presence flag is not a measurement."""
    return None if isinstance(value, bool) or not isinstance(value, (int, float)) else float(value)


def _ts(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# ------------------------------------------------------------------ the niche
def constraint_of(mechanism: Any) -> str:
    """What forces the actor. UNKNOWN when unmapped -- counted, never guessed."""
    return MECHANISM_CONSTRAINT.get(str(mechanism), UNKNOWN)


def niche_of(cell: dict[str, Any]) -> dict[str, str]:
    """The eight-axis behavioural coordinate of one cell."""
    mech = str(cell.get("mechanism") or UNKNOWN)
    out = {a: str(cell.get(a) or UNKNOWN) for a in NICHE_AXES}
    out["mechanism"], out["constraint"] = mech, constraint_of(mech)
    return out


def niche_key(niche: dict[str, str]) -> str:
    """A stable, READABLE id: the axes are the identity and they stay spelled out."""
    return "|".join(str(niche.get(a, UNKNOWN)) for a in NICHE_AXES)


def quality(row: dict[str, Any]) -> tuple[float, str]:
    """(score, basis) for one cell's evidence. Forward first, in-sample second, gate depth last."""
    exp_r, n = _num(row.get("exp_r")), _num(row.get("n"))
    if exp_r is not None and n is not None and n > 0:
        return exp_r * math.sqrt(n), FORWARD_BASIS
    sharpe, days = _num(row.get("sharpe")), _num(row.get("days"))
    if sharpe is not None and days is not None and days > 0:
        return sharpe * math.sqrt(days / 252.0), "in_sample_t"
    if sharpe is not None:
        return sharpe, "in_sample_sharpe"
    depth = _num(row.get("gate_depth"))
    return (depth, "gate_depth") if depth is not None else (0.0, "UNMEASURED")


# ------------------------------------------------------------------ the evidence join
def _merge(ev: dict[str, dict[str, Any]], axes: dict[str, str], family: Any, state: str, *,
           gate: Any = "", exp_r: float | None = None, n: float | None = None,
           sharpe: float | None = None, days: float | None = None) -> dict[str, Any]:
    """Fold one observation into the cell it describes, keeping the strongest of each kind."""
    cid = ar.cell_id(axes)
    row = ev.get(cid)
    if row is None:
        row = {"cell_id": cid, **axes, "family": "", "state": "UNMEASURED", "gate": "",
               "gate_depth": None, "exp_r": None, "n": None, "sharpe": None, "days": None}
        ev[cid] = row
    if family and not row["family"]:
        row["family"] = ar._tok(family)
    if ar.STATE_RANK.get(state, 0) > ar.STATE_RANK.get(row["state"], 0):
        row["state"] = state
    depth = 1.0 if str(gate).upper() == "PASSED" else GATE_DEPTH.get(str(gate))
    if depth is not None and (row["gate_depth"] is None or depth > row["gate_depth"]):
        row["gate_depth"], row["gate"] = depth, str(gate)
    # The forward reading with the most trades behind it wins; sqrt(n) is doing real work here.
    if exp_r is not None and n is not None and (row["n"] is None or n > row["n"]):
        row["exp_r"], row["n"] = exp_r, n
    if sharpe is not None and row["sharpe"] is None:
        row["sharpe"], row["days"] = sharpe, days
    return row


def collect_evidence(note: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Per-cell quality evidence from the four sources carrying a NUMBER, not merely a state."""
    ev: dict[str, dict[str, Any]] = {}
    if ar is None:
        return ev

    for row in ar._read_jsonl(GATE_LEDGER, note):
        parsed = ar.parse_shadow_key(str(row.get("cell") or ""))
        fam = row.get("family") or parsed["family"]
        passed = bool(row.get("passed"))
        _merge(ev, ar.axis_cell(row.get("sym") or parsed["symbol"], fam, None,
                                session=parsed["session"], regime_hint=parsed["regime"]),
               fam, "CERTIFIED" if passed else "MEASURED_FAIL",
               gate="PASSED" if passed else str(row.get("terminal_gate") or ""))

    doc = ar._read_json(UNIVERSAL_SURVIVORS, note)
    survivors = doc.get("survivors") if isinstance(doc, dict) else None
    for row in survivors.values() if isinstance(survivors, dict) else []:
        spec = row.get("shadow_spec") if isinstance(row, dict) else None
        if not isinstance(spec, dict):
            continue
        gates = row.get("gates") if isinstance(row.get("gates"), dict) else {}
        screen = gates.get("in_sample_screen")
        screen = screen if isinstance(screen, dict) else {}
        _merge(ev, ar.axis_cell(spec.get("symbol") or row.get("sym"), spec.get("family"),
                                spec.get("params"), spec.get("timeframe"), spec.get("selector"),
                                regime_hint=spec.get("condition")),
               spec.get("family"), "CERTIFIED", gate="PASSED",
               sharpe=_num(screen.get("sharpe")), days=_num(row.get("days")))

    shadow = ar._read_json(SHADOW_STATE, note)
    for key, row in shadow.items() if isinstance(shadow, dict) else []:
        if not isinstance(row, dict):
            continue
        parsed = ar.parse_shadow_key(str(key))
        n = _num(row.get("n"))
        # A REFUSED or BLOCKED clock produced no forward observation; scoring it as forward
        # evidence would let an enrolment the desk never ran hold a niche's elite seat.
        ran = bool(n) or str(row.get("status") or "").upper().startswith(("ACTIVE", "PROMOTION"))
        _merge(ev, ar.axis_cell(parsed["symbol"], parsed["family"],
                                dict.fromkeys(parsed["param_names"], True),
                                session=parsed["session"], regime_hint=parsed["regime"]),
               parsed["family"], "FORWARD" if ran else "MEASURED_FAIL",
               exp_r=_num(row.get("exp_r")) if ran else None, n=n if ran else None)

    doc = ar._read_json(SLEEVES, note)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        sess = row.get("session") or row.get("selector") or row.get("window")
        _merge(ev, ar.axis_cell(row.get("symbol"), row.get("family"), row, row.get("timeframe"),
                                sess, row.get("exec"), regime_hint=row.get("state")),
               row.get("family"),
               "LIVE" if str(row.get("status") or "").upper() == "LIVE" else "FORWARD",
               exp_r=_num(row.get("shadow_exp")), n=_num(row.get("shadow_n")))
    return ev


def collect_cells(note: dict[str, str], evidence: dict[str, dict[str, Any]]
                  ) -> dict[str, dict[str, Any]]:
    """The judged-cell inventory from the registry's own ledger, scored by the evidence. A cell
    only the evidence knows about is still a cell -- an absent `axis_registry.jsonl` must degrade
    the inventory, never erase the frontier."""
    cells: dict[str, dict[str, Any]] = {}
    for row in ar._read_jsonl(AXIS_CELLS, note) if ar else []:
        cid = str(row.get("cell_id") or "")
        state = str(row.get("state") or "UNMEASURED")
        if cid:
            cells[cid] = {"cell_id": cid, **{a: str(row.get(a) or UNKNOWN) for a in ar.AXES},
                          "state": state if state in ar.STATES else "UNMEASURED", "family": ""}
    for cid, row in evidence.items():
        cell = cells.get(cid)
        if cell is None:
            cell = {"cell_id": cid, **{a: str(row.get(a) or UNKNOWN) for a in ar.AXES},
                    "state": "UNMEASURED", "family": ""}
            cells[cid] = cell
        if not cell["family"]:
            cell["family"] = row["family"]
        if ar.STATE_RANK.get(row["state"], 0) > ar.STATE_RANK.get(cell["state"], 0):
            cell["state"] = row["state"]
        cell["score"], cell["basis"] = quality(row)
    for cell in cells.values():
        cell.setdefault("score", 0.0)
        cell.setdefault("basis", "UNMEASURED")
    return cells


# ------------------------------------------------------------------ the mental map
def build_niches(cells: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """niche key -> what the desk tried there, and which single cell holds the seat."""
    out: dict[str, dict[str, Any]] = {}
    for cell in sorted(cells.values(), key=lambda c: c["cell_id"]):
        niche = niche_of(cell)
        row = out.setdefault(niche_key(niche), {
            "niche": niche, "n_cells_tried": 0, "n_certified": 0, "n_forward": 0, "n_live": 0,
            "elite": None, "elite_family": "", "elite_score": 0.0,
            "elite_evidence_basis": "UNMEASURED", "last_improved_at": None})
        row["n_cells_tried"] += 1
        row["n_certified"] += int(cell["state"] == "CERTIFIED")
        row["n_forward"] += int(cell["state"] == "FORWARD")
        row["n_live"] += int(cell["state"] == "LIVE")
        challenger = (BASIS_RANK.get(cell["basis"], 0), cell["score"], cell["cell_id"])
        holder = (BASIS_RANK.get(row["elite_evidence_basis"], 0), row["elite_score"],
                  (row["elite"] or {}).get("cell_id", ""))
        if row["elite"] is None or challenger > holder:
            row["elite"] = {"cell_id": cell["cell_id"], "instrument": cell["instrument"],
                            "family": cell["family"], "chart": cell["chart"],
                            "session": cell["session"], "state": cell["state"],
                            "score": round(cell["score"], 6), "basis": cell["basis"]}
            row["elite_family"], row["elite_score"] = cell["family"], cell["score"]
            row["elite_evidence_basis"] = cell["basis"]
    return out


def merge_map(niches: dict[str, dict[str, Any]], previous: dict[str, Any], now: str) -> None:
    """Carry `last_improved_at` forward. A run that re-reads the same artifacts improves nothing,
    and the exploiter must not be fooled into thinking every niche just got better."""
    prev = previous.get("niches") if isinstance(previous, dict) else None
    prev = prev if isinstance(prev, dict) else {}
    for key, row in niches.items():
        old = prev.get(key)
        if not isinstance(old, dict):
            row["first_seen_at"] = row["last_improved_at"] = now
            continue
        row["first_seen_at"] = str(old.get("first_seen_at") or now)
        old_rank = BASIS_RANK.get(str(old.get("elite_evidence_basis")), 0)
        old_score = _num(old.get("elite_score")) or 0.0
        new_rank = BASIS_RANK.get(row["elite_evidence_basis"], 0)
        improved = new_rank > old_rank or (new_rank == old_rank
                                           and row["elite_score"] > old_score + IMPROVE_EPS)
        row["last_improved_at"] = now if improved else str(old.get("last_improved_at") or now)


# ------------------------------------------------------------------ the candidate space
def mechanism_bundles(families: frozenset[str]) -> list[tuple[str, str]]:
    """(mechanism, information_source) pairs a REGISTERED family actually implements."""
    return sorted({(m, i) for f, (m, i, _) in ar.FAMILY_TABLE.items()
                   if m != UNKNOWN and i != UNKNOWN and f in families}) if ar else []


def _bundle(niche: dict[str, str], mechanism: str, information_source: str) -> dict[str, str]:
    """The four mechanism-derived axes set together, in `MECHANISM_BUNDLE`'s own order."""
    values = (mechanism, information_source, ar.MECHANISM_ACTOR.get(mechanism, UNKNOWN),
              constraint_of(mechanism))
    return {**niche, **dict(zip(MECHANISM_BUNDLE, values, strict=True))}


def candidate_niches(families: frozenset[str],
                     by_class: dict[str, list[str]]) -> dict[str, dict[str, str]]:
    """Every niche the desk COULD build, bounded by construction: registered mechanisms, priced
    hypothesis-lane classes, runnable charts and sessions, and the one regime it may claim.

    THE LANE IS RE-CHECKED HERE and not inherited from the caller. `instruments_by_class` already
    filters, but a candidate space is the thing every arm ranks against: if an event-lane class
    ever reached it, the frontier would report equity ground as unexplored and send three workers
    at it forever."""
    out: dict[str, dict[str, str]] = {}
    classes = [k for k in sorted(by_class) if _symbols(k, by_class)]
    for mech, info in mechanism_bundles(families):
        for klass in classes:
            for horizon in PROPOSABLE_HORIZONS:
                for sess in PROPOSABLE_SESSIONS:
                    if HORIZON_CHART[horizon] == "D1" and sess != "all":
                        continue                    # a daily bar carries no session
                    niche = _bundle({"asset_class": klass, "horizon": horizon, "session": sess,
                                     "regime": PROPOSAL_REGIME}, mech, info)
                    out[niche_key(niche)] = niche
    return out


def one_move(niche: dict[str, str], bundles: list[tuple[str, str]],
             classes: list[str]) -> list[tuple[str, dict[str, str]]]:
    """Every niche exactly ONE free axis away. The mechanism bundle moves as a unit -- an economic
    actor without its mechanism is not a cell anything could build."""
    out = [("mechanism", _bundle(niche, mech, info)) for mech, info in bundles
           if mech != niche.get("mechanism") or info != niche.get("information_source")]
    values = {"asset_class": tuple(classes), "horizon": PROPOSABLE_HORIZONS,
              "session": PROPOSABLE_SESSIONS, "regime": (PROPOSAL_REGIME,)}
    for axis in FREE_AXES[1:]:                      # FREE_AXES[0] is the bundle, moved above
        out.extend((axis, {**niche, axis: v}) for v in values[axis] if v != niche.get(axis))
    return out


def explorer_targets(niches: dict[str, dict[str, Any]], space: dict[str, dict[str, str]],
                     bundles: list[tuple[str, str]], classes: list[str]) -> list[dict[str, Any]]:
    """EMPTY niches bordering occupied ground, most-bordered first: a niche with four occupied
    neighbours inherits four pieces of evidence, one with a single neighbour inherits one."""
    found: dict[str, dict[str, Any]] = {}
    for key, row in sorted(niches.items()):
        rank, score = BASIS_RANK.get(row["elite_evidence_basis"], 0), float(row["elite_score"])
        for axis, niche in one_move(row["niche"], bundles, classes):
            k = niche_key(niche)
            if k in niches or k not in space:
                continue
            cur = found.get(k)
            if cur is None:
                found[k] = {"niche": niche, "from": key, "axis": axis, "neighbours": 1,
                            "rank": rank, "score": score}
                continue
            cur["neighbours"] += 1
            if (rank, score) > (cur["rank"], cur["score"]):
                cur.update({"from": key, "axis": axis, "rank": rank, "score": score})
    return sorted(found.values(), key=lambda r: (-r["neighbours"], -r["rank"], -r["score"],
                                                 niche_key(r["niche"])))


def sibling_families(mechanism: str, information_source: str,
                     families: frozenset[str]) -> list[str]:
    """Registered, unbanned families implementing the same mechanism -- the nearest thing to a
    parameter neighbour the registry's vocabulary can name."""
    return sorted(f for f, (m, i, _) in ar.FAMILY_TABLE.items()
                  if m == mechanism and i == information_source and f in families
                  and not ar._banned(f)) if ar else []


def elite_mutations(niche: dict[str, str], elite: dict[str, Any],
                    families: frozenset[str]) -> list[tuple[str, str, dict[str, str]]]:
    """(axis, value, niche) one step off the elite: an adjacent chart, another session, a sibling
    family. The family move keeps the niche and raises its elite; the other two move it."""
    out: list[tuple[str, str, dict[str, str]]] = []
    charts = ar.CHARTS if ar else ()
    here = str(elite.get("chart") or "")
    idx = charts.index(here) if here in charts else -1
    for step in (-1, 1):
        if idx >= 0 and 0 <= idx + step < len(charts):
            chart = charts[idx + step]
            horizon = ar.horizon_of(chart, {})
            if horizon in PROPOSABLE_HORIZONS and HORIZON_CHART[horizon] == chart:
                out.append(("chart", chart, {**niche, "horizon": horizon}))
    out.extend(("session", s, {**niche, "session": s})
               for s in PROPOSABLE_SESSIONS if s != niche.get("session"))
    out.extend(("family", f, dict(niche)) for f in
               sibling_families(niche["mechanism"], niche["information_source"], families)
               if f != elite.get("family"))
    return out


def exploiter_targets(niches: dict[str, dict[str, Any]], now: datetime,
                      window_h: int = IMPROVED_WINDOW_H) -> list[tuple[str, dict[str, Any]]]:
    """Niches whose elite improved inside the window, strongest evidence first."""
    fresh: list[tuple[int, float, str, dict[str, Any]]] = []
    for key, row in niches.items():
        stamp = _ts(row.get("last_improved_at"))
        if stamp is not None and row["elite"] and now - stamp <= timedelta(hours=window_h):
            fresh.append((BASIS_RANK.get(row["elite_evidence_basis"], 0),
                          float(row["elite_score"]), key, row))
    fresh.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [(key, row) for _rank, _score, key, row in fresh]


def connector_pairs(niches: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordered pairs of occupied niches sharing an asset class or a mechanism: the LEFT elite's
    family carried onto the RIGHT niche's session and horizon."""
    rows = [(k, r) for k, r in niches.items() if r["elite"] and r["elite_family"]]
    rows.sort(key=lambda t: (-BASIS_RANK.get(t[1]["elite_evidence_basis"], 0),
                             -float(t[1]["elite_score"]), t[0]))
    out: list[dict[str, Any]] = []
    for left_key, left in rows[:CONNECTOR_POOL]:
        for right_key, right in rows[:CONNECTOR_POOL]:
            a, b = left["niche"], right["niche"]
            share = ("asset_class" if a["asset_class"] == b["asset_class"]
                     else "mechanism" if a["mechanism"] == b["mechanism"] else "")
            if left_key == right_key or not share:
                continue
            if b["session"] not in PROPOSABLE_SESSIONS or b["horizon"] not in PROPOSABLE_HORIZONS:
                continue
            if a["session"] == b["session"] and a["horizon"] == b["horizon"]:
                continue                    # nothing crosses; this is the left niche restated
            out.append({"niche": {**a, "session": b["session"], "horizon": b["horizon"],
                                  "regime": PROPOSAL_REGIME},
                        "left": left_key, "right": right_key, "share": share,
                        "elite": left["elite"], "other": right["elite"],
                        "rank": BASIS_RANK.get(left["elite_evidence_basis"], 0)
                        + BASIS_RANK.get(right["elite_evidence_basis"], 0),
                        "score": float(left["elite_score"]) + float(right["elite_score"])})
    out.sort(key=lambda r: (-r["rank"], -r["score"], niche_key(r["niche"])))
    return out


# ------------------------------------------------------------------ proposals
def _symbols(klass: str, by_class: dict[str, list[str]]) -> list[str]:
    """The deepest-history hypothesis-lane instruments of a class; equities reach nothing."""
    return [s for s in by_class.get(klass, []) if ar.may_hypothesise(s)][:PROPOSAL_SYMBOLS]


def proposal(niche: dict[str, str], family: str | None, symbols: list[str], worker: str,
             why: str, score: float) -> dict[str, Any] | None:
    """One intake row in `axis_registry`'s exact shape, or None when the niche cannot be built."""
    chart = HORIZON_CHART.get(str(niche.get("horizon")), "")
    sess = str(niche.get("session"))
    if not chart or sess not in PROPOSABLE_SESSIONS or not family or not symbols:
        return None
    if chart == "D1" and sess != "all":
        return None
    # AN UNNAMED MECHANISM IS RECORDED, NEVER PROPOSED. `discovered` cells hold real niche seats
    # and are counted in occupancy and dominance, but a cell with no payer is what `economic_prior`
    # -- the gauntlet's FIRST gate -- exists to refuse, so donating one spends trial budget that
    # cannot convert. Same discipline as the equity cells in `axis_registry`.
    if UNKNOWN in (niche.get("mechanism"), niche.get("information_source")):
        return None
    params: dict[str, Any] = {}
    if chart != ar.DEFAULT_CHART:
        params["timeframe"] = chart
    if sess != "all":
        params["session"] = sess
    return {"kind": "hypothesis", "family": family, "symbols": symbols, "params": params,
            "timeframe": chart, "session": sess, "source": f"qd_frontier:{worker}", "why": why,
            "axis_cell": ar.axis_cell(symbols[0], family, params, chart, sess),
            "selector_mode": worker, "rank_score": round(float(score), 5),
            "niche": niche_key(niche)}


def _take(out: dict[str, list[dict[str, Any]]], worker: str, row: dict[str, Any] | None,
          seen: set[str], caps: dict[str, int]) -> bool:
    """Admit a row unless the arm is full or the desk has already judged that exact coordinate."""
    if row is None or len(out[worker]) >= caps[worker]:
        return False
    cid = ar.cell_id(row["axis_cell"])
    if cid in seen:
        return False
    seen.add(cid)
    out[worker].append(row)
    return True


def select(cells: dict[str, dict[str, Any]], niches: dict[str, dict[str, Any]],
           space: dict[str, dict[str, str]], families: frozenset[str],
           by_class: dict[str, list[str]], now: datetime,
           max_proposals: int = DEFAULT_PROPOSALS) -> dict[str, list[dict[str, Any]]]:
    """Three arms, one budget, an equal share each. The remainder goes to the explorer: it is the
    only arm that can add a niche, and a desk short one proposal should spend it on new ground."""
    out: dict[str, list[dict[str, Any]]] = {w: [] for w in WORKERS}
    budget = max(0, int(max_proposals))
    share = budget // len(WORKERS)
    caps = dict.fromkeys(WORKERS, share)
    caps[WORKERS[0]] += budget - share * len(WORKERS)
    if ar is None or not budget:
        return out
    prefer = ar.compiler_vocab()
    classes = [k for k in sorted(by_class) if _symbols(k, by_class)]
    bundles, seen = mechanism_bundles(families), set(cells)

    for target in explorer_targets(niches, space, bundles, classes):
        if len(out["explorer"]) >= caps["explorer"]:
            break
        niche = target["niche"]
        _take(out, "explorer", proposal(
            niche, ar.family_for(niche["mechanism"], niche["information_source"], families,
                                 prefer, niche_key(niche)),
            _symbols(niche["asset_class"], by_class), "explorer",
            f"EMPTY NICHE: nothing the desk has judged sits at {niche_key(niche)}; it is ONE free "
            f"axis ({target['axis']}) from {target['from']}, and {target['neighbours']} occupied "
            f"niche(s) border it", target["neighbours"]), seen, caps)

    for key, row in exploiter_targets(niches, now):
        if len(out["exploiter"]) >= caps["exploiter"]:
            break
        elite, taken = row["elite"], 0
        for axis, value, niche in elite_mutations(row["niche"], elite, families):
            if taken >= EXPLOIT_PER_NICHE or len(out["exploiter"]) >= caps["exploiter"]:
                break
            fam = value if axis == "family" else (elite.get("family") or ar.family_for(
                niche["mechanism"], niche["information_source"], families, prefer,
                niche_key(niche)))
            if fam not in families:
                continue
            taken += int(_take(out, "exploiter", proposal(
                niche, fam, _symbols(niche["asset_class"], by_class), "exploiter",
                f"ELITE MUTATION: {key} improved at {row['last_improved_at']} -- its elite "
                f"{elite.get('instrument')} {elite.get('family') or UNKNOWN} scores "
                f"{elite.get('score')} on {elite.get('basis')}; this moves ONE step "
                f"({axis} -> {value})", row["elite_score"]), seen, caps))

    for pair in connector_pairs(niches):
        if len(out["connector"]) >= caps["connector"]:
            break
        niche, elite = pair["niche"], pair["elite"]
        fam = elite.get("family")
        if fam not in families:
            continue
        _take(out, "connector", proposal(
            niche, fam, _symbols(niche["asset_class"], by_class), "connector",
            f"CROSS-NICHE: {pair['left']} and {pair['right']} share {pair['share']}; this carries "
            f"the left elite ({elite.get('instrument')} {fam}, {elite.get('basis')} "
            f"{elite.get('score')}) onto the right niche's session/horizon "
            f"({niche['session']}/{niche['horizon']})", pair["score"]), seen, caps)
    return out


# ------------------------------------------------------------------ accounting, build, write
def accounting(niches: dict[str, dict[str, Any]], space: dict[str, dict[str, str]],
               selection: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """The anti-monoculture numbers. `dominance` is measured over elites whose family is NAMED:
    UNKNOWN is not a family, and letting it hold the top share would report monoculture where
    there is only missing provenance."""
    counts = Counter(r["elite_family"] for r in niches.values() if r["elite_family"])
    total = sum(counts.values())
    return {"niches_occupied": len(niches),
            "niches_empty": sum(1 for k in space if k not in niches),
            "n_candidate_niches": len(space), "elite_families": len(counts),
            "elites_without_family": sum(1 for r in niches.values() if not r["elite_family"]),
            "dominance": round(max(counts.values()) / total, 4) if total else 0.0,
            "dominant_family": counts.most_common(1)[0][0] if counts else UNKNOWN,
            "elite_basis": dict(Counter(r["elite_evidence_basis"]
                                        for r in niches.values()).most_common()),
            "proposals": {w: len(selection[w]) for w in WORKERS}}


def build(max_proposals: int = DEFAULT_PROPOSALS, previous: dict[str, Any] | None = None
          ) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """(report, niches, proposals). Every input may be absent; none of them may raise."""
    now, registry_at = datetime.now(UTC), UNKNOWN
    note: dict[str, str] = {}
    why: list[str] = []
    cells: dict[str, dict[str, Any]] = {}
    niches: dict[str, dict[str, Any]] = {}
    space: dict[str, dict[str, str]] = {}
    selection: dict[str, list[dict[str, Any]]] = {w: [] for w in WORKERS}
    max_proposals = min(int(max_proposals), MAX_PROPOSALS)       # structural, not a flag

    if ar is None:                                              # pragma: no cover - see the try
        why.append(f"UNMEASURED: axis_registry is unimportable ({_AR_ERROR}) -- the ten axes, the "
                   "family table and the cell id all live there, so no niche can be named")
    else:
        doc = ar._read_json(AXIS_REPORT, note)
        registry_at = str(doc.get("at")) if isinstance(doc, dict) else UNKNOWN
        cells = collect_cells(note, collect_evidence(note))
        niches = build_niches(cells)
        if previous is None:
            doc = ar._read_json(OUT_MAP, note)
            previous = doc if isinstance(doc, dict) else {}
        merge_map(niches, previous, now.isoformat())
        families, by_class = ar.registered_families(), ar.instruments_by_class()
        space = candidate_niches(families, by_class)
        if not families:
            why.append("no registered family could be imported, so nothing may be proposed")
        if not by_class:
            why.append("no hypothesis-lane instrument is priced, so no niche can be built")
        if not cells:
            why.append("no judged cell was readable: there is no occupied niche to explore from, "
                       "mutate or connect")
        selection = select(cells, niches, space, families, by_class, now, max_proposals)

    ranked = sorted(niches.items(),
                    key=lambda kv: (-BASIS_RANK.get(kv[1]["elite_evidence_basis"], 0),
                                    -float(kv[1]["elite_score"]), -kv[1]["n_cells_tried"], kv[0]))
    report = {"at": now.isoformat(), "n_cells": len(cells), "n_niches": len(niches),
              "niches": dict(ranked[:REPORT_NICHES]),
              "summary": {**accounting(niches, space, selection), "n_niches": len(niches),
                          "niches_in_file": min(len(niches), REPORT_NICHES),
                          "axis_registry_at": registry_at},
              "proposals": selection, "unmeasured": {"inputs": note, "why": why}, "rule": RULE}
    return report, niches, [p for w in WORKERS for p in selection[w]]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write(report: dict[str, Any], niches: dict[str, dict[str, Any]],
          proposals: list[dict[str, Any]]) -> Path:
    """Report, persistent map and the intake donation -- all three atomic, in that order."""
    _atomic_write(OUT_REPORT, json.dumps(report, indent=1, default=str))
    _atomic_write(OUT_MAP, json.dumps({"at": report["at"], "n_niches": len(niches),
                                       "niches": niches}, indent=1, default=str))
    donation = INTAKE / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    _atomic_write(donation, json.dumps(proposals, indent=1, default=str))
    return donation


def summary(report: dict[str, Any], proposals: list[dict[str, Any]], target: str) -> list[str]:
    """Exactly eight lines: what was read, where the elites are, how diverse, what next."""
    s = report["summary"]
    top = next(iter(report["niches"].items()), None)
    elite = (top[1]["elite"] or {}) if top else {}
    return [
        f"QD FRONTIER {report['at']}  inputs: "
        + (", ".join(f"{k}={v}" for k, v in report["unmeasured"]["inputs"].items()) or "none"),
        f"  cells {report['n_cells']}  niches occupied {s['niches_occupied']}  empty "
        f"{s['niches_empty']} of {s['n_candidate_niches']} candidates",
        "  elite basis  " + ("  ".join(f"{k}={v}" for k, v in s["elite_basis"].items()) or "none"),
        f"  diversity  elite_families={s['elite_families']}  dominance={s['dominance']} "
        f"({s['dominant_family']})  unnamed={s['elites_without_family']}",
        f"  best niche  {top[0] if top else 'none'}",
        f"    elite {elite.get('instrument', UNKNOWN)} {elite.get('family') or UNKNOWN} "
        f"{elite.get('score', 0.0)} ({elite.get('basis', 'UNMEASURED')})",
        f"  proposals {len(proposals)} ("
        + " ".join(f"{w}={s['proposals'][w]}" for w in WORKERS) + f") -> {target}",
        "  UNMEASURED  " + ("; ".join(report["unmeasured"]["why"]) or "nothing withheld"),
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="quality-diversity frontier: one elite per niche")
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    ap.add_argument("--max-proposals", type=int, default=DEFAULT_PROPOSALS,
                    help=f"cap the intake donation (default {DEFAULT_PROPOSALS}, "
                         f"hard ceiling {MAX_PROPOSALS})")
    args = ap.parse_args(argv)
    report, niches, proposals = build(args.max_proposals)
    target = "DRY RUN (nothing written)" if args.dry_run else str(
        write(report, niches, proposals))
    for line in summary(report, proposals, target):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
