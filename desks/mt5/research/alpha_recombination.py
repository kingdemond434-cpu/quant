"""M5 -- SURVIVING MECHANISMS ARE GENES, AND GENES RECOMBINE ONLY WHERE THE ECONOMICS TOUCH.

THE PRINCIPAL, 2026-09-17 (ledger item M5, the eight internal exploitation engines): the desk owns
a small population of mechanisms that have actually survived something -- three promoted sleeves,
fifty-odd ten-gate certificates, and the cells that walked the whole gauntlet and died on the last
gate. Each one cost a campaign to find. Combining them is the cheapest research the desk can do,
because the mechanisms are already paid for; the only new thing being bought is the INTERACTION.

WHAT THIS IS NOT. It is not a cross product. Two mechanisms multiplied together produce a rule that
fits better than either -- always, on any data -- and a population of such rules is the purest
form of the overfitting the ten gates exist to catch. Worse, it is expensive overfitting: the
deflated-Sharpe charge and the program-level SPA/PBO tests divide ONE family-wise error budget
across every cell the desk tests, so a thousand arbitrary crosses raise the bar that every honest
FX and metals cell then has to clear. 58 certificates cross-producted three deep is 195,000 cells
and about nine of them would have a reason to exist.

SO THE INTERACTION TABLE IS THE PRODUCT. A pair is generated only where the two mechanism CLASSES
plausibly act on each other, and the reason is recorded on the combination as `why`:

    session breakout x macro release   an event-day breakout is a different population: the range
                                       break is carrying scheduled information rather than stop
                                       liquidity, and pooling the two hides both.
    forced flow x positioning extreme  flow into a crowded book -- the liquidation must cross the
                                       side everyone is already on, so the overshoot is largest
                                       exactly where positioning is extreme.
    carry x volatility state           carry is a premium for warehousing risk: it is collected in
                                       the calm and repaid in the shock, so the vol state is the
                                       carry's own off switch rather than a filter bolted on.

`libs/research/mechanism_ontology.py` is asked FIRST for such a table (it owns the desk's
mechanism contracts, and if it ever grows a pair relation this organ must use that one rather than
a second opinion). Today it exposes `compatible` -- observable x transform x horizon x state, the
pruning for ONE mechanism -- and no pair relation at all, so the table below is declared here, in
the desk's own mechanism-class vocabulary (`axis_registry.FAMILY_TABLE`), and the ontology's table
takes precedence the moment it exists.

MAX THREE GENES, and a triple only where ALL THREE pairs are in the table. Beyond three the
combination stops being a mechanism and becomes a description of the sample, and the `why` stops
being readable by the person who has to defend it.

HOW A COMBINATION IS EXPRESSED. The primary gene keeps its family and parameters; the second gene
becomes a CONDITION TAG. Where a family can host that tag it is donated as an ordinary EXACT_RECIPE
candidate and walks the ten gates with no inherited credibility -- `session` is hostable by EVERY
family because `family_call.signals` pops it and applies `session_filter`, and any other knob is
hostable only if the family's own signature accepts it (MEASURED on this tree: of 28 registered
families exactly one takes a `session` argument and none takes a regime, so a tag the signature
does not name would be silently dropped by the gauntlet's param filter and the "combination" would
be its parent wearing a label). Where no family can host it, the combination leaves as a
`combination` payload on the discovery and the discovery compiler owns the conversion.

    python desks/mt5/research/alpha_recombination.py [--dry-run] [--max-combinations 40]
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SLEEVES = DESK / "data" / "sleeves.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
GATES_EXTERNAL = DESK / "reports" / "universal_gates_external.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
OUT = DESK / "reports" / "ALPHA_RECOMBINATION.json"

SEAT = "alpha_recombination"
MAX_COMBINATIONS = 40
MAX_GENES = 3
BUDGET_S = 240.0
#: Coherent combinations ENUMERATED before the cap is allocated. Bounded so a large gene pool
#: cannot turn the second pass into the combinatorial walk the first pass exists to avoid.
POOL_MAX = 4000
#: How close to the deflated-Sharpe bar a dead cell must have come to count as a GENE. 20% of the
#: hurdle: near enough that the mechanism is the question and the sample size is the answer.
NEAR_FRAC = 0.20
#: The deflated-Sharpe gate's own pass mark, from `gate_policy`; the literal is the fallback when
#: the policy is unimportable, and the report says which was used.
DSR_BAR = 0.95
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_LEDGER_LINES = 500_000
UNKNOWN = "UNKNOWN"
LANE_RANK = {"LIVE": 4, "STANDBY": 3, "CERTIFIED": 2, "NEAR_SURVIVOR": 1}
#: Families that are spec CONSTRUCTORS rather than mechanisms -- never a gene.
NOT_A_GENE = frozenset({"generic", "formula", "ensemble", "cross_sectional", "joint_genome"})

#: WHICH PAIRS OF MECHANISM CLASSES MAY BE BUILT AT ALL, and why. Keys are the desk's own
#: mechanism classes (`axis_registry.FAMILY_TABLE`); an unlisted pair is REFUSED and counted.
#: UNKNOWN never appears here on purpose: a family with no named mechanism has no economics to
#: interact with, and a combination whose `why` cannot be written is one nobody can defend.
INTERACTIONS: dict[frozenset[str], str] = {
    frozenset({"breakout_liquidity", "macro_release"}):
        "event-day breakout: a range break on a scheduled-release day is carrying macro "
        "information rather than stop liquidity, and pooling the two populations hides both",
    frozenset({"breakout_liquidity", "volatility_shock"}):
        "compression release: a break out of a squeezed range is the compression paying, while a "
        "break inside an already-wide range is the same rule firing on noise",
    frozenset({"breakout_liquidity", "session_handover"}):
        "the range that breaks was built by the previous session, so the handover's own drift "
        "decides which side of it the break takes",
    frozenset({"forced_flow", "positioning_crowding"}):
        "flow into a crowded book: the liquidation must cross the side everyone is already on, so "
        "the overshoot is largest exactly where reported positioning is extreme",
    frozenset({"carry_rollover", "volatility_shock"}):
        "carry conditioned on calm: carry is a premium for warehousing risk, collected in quiet "
        "states and repaid in the shock, so the vol state is the carry's own off switch",
    frozenset({"carry_rollover", "regime_transition"}):
        "the transition is when a state-dependent premium is repaid; conditioning carry on it is "
        "the same claim with the repayment named in advance",
    frozenset({"macro_release", "session_handover"}):
        "a release lands inside one session and is priced in the next; the handover is the "
        "transmission channel, not a second effect",
    frozenset({"macro_release", "fx_fixing_flow"}):
        "the release moves the benchmark the fixing then has to trade at; the fixing flow is the "
        "mechanical follow-through of the information",
    frozenset({"macro_release", "cross_market_lead"}):
        "lead-lag is an information transport and a macro release is the information that has to "
        "travel; the lead says where it arrives first",
    frozenset({"positioning_crowding", "calendar_seasonality"}):
        "reported positioning is a calendar object (the COT print) and the seasonal window says "
        "when the unwind is forced rather than discretionary",
    frozenset({"relative_value_dislocation", "volatility_shock"}):
        "a spread is a relative-value claim only while its correlation holds; the shock is where "
        "it does not, which is where the dislocation looks largest and is least tradable",
    frozenset({"relative_value_dislocation", "cross_market_lead"}):
        "the leg that leads reprices first, so a residual with a known lead is a timing rule as "
        "well as a level rule",
    frozenset({"trend_persistence", "regime_transition"}):
        "trend persistence is a flow effect and the transition is where the flow turns; the state "
        "tag is the trend's own kill switch rather than a filter bolted on",
    frozenset({"trend_persistence", "volatility_shock"}):
        "the same momentum in a high-volatility state is a different risk-adjusted bet, and the "
        "vol state is what separates the two",
    frozenset({"range_reversion", "volatility_shock"}):
        "reversion inside a range assumes the range is the boundary; a volatility shock is "
        "exactly the state in which it is not",
    frozenset({"range_reversion", "execution_microstructure"}):
        "a reversion entry is a passive order and its fill quality is most of the edge; the "
        "spread state says whether the reversion is capturable at all",
    frozenset({"execution_microstructure", "forced_flow"}):
        "forced flow consumes the book and the spread/depth state measures what is left to "
        "consume; the microstructure is the mechanism's own gauge",
    frozenset({"execution_microstructure", "inventory_shock"}):
        "a volume spike is an inventory shock only where the book failed to absorb it; the spread "
        "and depth are what tell the two apart",
    frozenset({"session_handover", "calendar_seasonality"}):
        "the handover gap is a weekday object: Monday's gap carries a weekend of information and "
        "no other day's does",
    frozenset({"session_information_handoff", "macro_release"}):
        "the handoff is the channel a release travels down; conditioning it on the release names "
        "which handoffs carry information and which are noise",
    frozenset({"hedging_demand_close_flow", "calendar_seasonality"}):
        "hedging demand at the close is a settlement-calendar object; the month or day window is "
        "when the flow is mandatory rather than optional",
    frozenset({"gamma_hedging_state", "volatility_shock"}):
        "dealer gamma decides whether hedging damps or amplifies a move, and the vol state is the "
        "sign of that feedback",
}

#: What the SECOND gene contributes to the first, as a tag kind. `session` is hostable by every
#: family; the others are hostable only where a family's signature names them.
CONDITION_KIND: dict[str, str] = {
    "session_handover": "session", "session_information_handoff": "session",
    "macro_release": "event", "forced_flow": "event", "fx_fixing_flow": "event",
    "hedging_demand_close_flow": "event", "calendar_seasonality": "event",
    "volatility_shock": "regime", "regime_transition": "regime", "gamma_hedging_state": "regime",
    "positioning_crowding": "state", "carry_rollover": "state", "inventory_shock": "state",
    "execution_microstructure": "state", "relative_value_dislocation": "state",
    "cross_market_lead": "state", "trend_persistence": "state", "range_reversion": "state",
    "breakout_liquidity": "state",
}
#: Parameter names a family's signature may expose for each tag kind, in preference order.
CONDITION_KNOBS: dict[str, tuple[str, ...]] = {
    "session": ("session", "selector"), "event": ("event", "event_filter", "condition"),
    "regime": ("regime", "vol_state", "market_state", "state"),
    "state": ("state", "condition", "band", "liquidity_state"),
}
RULE = ("genes recombine only where the mechanisms plausibly interact; exploitation of knowledge "
        "already paid for")


# ------------------------------------------------------------------ tolerant reading
def _read_json(path: Path, note: dict[str, str], default: Any = None) -> Any:
    """Parse `path`, or record exactly why it produced nothing. Never raises."""
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            note[path.name] = f"TOO_LARGE({path.stat().st_size})"
            return default
        doc = json.loads(path.read_text("utf-8-sig"))
    except OSError:
        note[path.name] = "ABSENT"
        return default
    except ValueError as exc:
        note[path.name] = f"UNREADABLE({type(exc).__name__})"
        return default
    note[path.name] = "READ"
    return doc


def _read_jsonl(path: Path, note: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8-sig") as fh:
            for i, line in enumerate(fh):
                if i >= MAX_LEDGER_LINES:
                    note[path.name] = f"TRUNCATED({MAX_LEDGER_LINES})"
                    return rows
                text = line.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        note[path.name] = "ABSENT"
        return rows
    note[path.name] = "READ"
    return rows


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


# ------------------------------------------------------------------ the desk's own vocabulary
def mechanism_class(family: str) -> str:
    """The family's mechanism class, from the desk's own table. UNKNOWN is COUNTED, never guessed
    -- and an UNKNOWN gene can enter no combination, because a `why` cannot be written for it."""
    try:
        from research.axis_registry import classify_family
    except Exception:                                            # pragma: no cover - desk import
        return UNKNOWN
    return str(classify_family(family)[0] or UNKNOWN)


def family_knobs(family: str) -> frozenset[str]:
    """The parameter names a registered family's signature accepts. THE SIGNATURE IS THE AUTHORITY
    -- the gauntlet filters a cell's params to it, so a tag the signature does not name is dropped
    and the combination silently becomes its parent."""
    try:
        import inspect

        from mt5desk import families as fam_mod
        entry = (getattr(fam_mod, "FAMILY_REGISTRY", {}) or {}).get(str(family))
        fn = entry.get("func") if isinstance(entry, dict) else entry
        if not callable(fn):
            return frozenset()
        return frozenset(n for n in list(inspect.signature(fn).parameters)[1:] if n != "side")
    except Exception:
        return frozenset()


def may_hypothesise(symbol: str) -> bool:
    """The two-lane mandate at the door: a single-name equity is traded on news and earnings
    reaction, never hunted for statistical hypotheses -- so it is not a gene either."""
    try:
        from research.axis_registry import may_hypothesise as policy
    except Exception:                                            # pragma: no cover - desk import
        return True
    try:
        return bool(policy(symbol))
    except Exception:
        return True


def interaction_table() -> tuple[dict[frozenset[str], str], str]:
    """(table, where it came from). The ONTOLOGY IS ASKED FIRST: it owns the mechanism contracts,
    and two organs holding two opinions about which mechanisms touch is how a refusal here becomes
    a permission there. Today it exposes `compatible` only -- one mechanism against a transform,
    horizon and state -- and no pair relation, so this module's table is used and said so."""
    try:
        from libs.research import mechanism_ontology as mo
    except Exception:                                            # pragma: no cover - install
        return INTERACTIONS, "module(mechanism_ontology unimportable)"
    for name in ("INTERACTIONS", "MECHANISM_INTERACTIONS", "PAIR_INTERACTIONS"):
        table = getattr(mo, name, None)
        if isinstance(table, dict) and table:
            out: dict[frozenset[str], str] = {}
            for key, value in table.items():
                why = value.get("why") if isinstance(value, Mapping) else value
                out[frozenset(key)] = str(why)
            return out, f"mechanism_ontology.{name}"
    return INTERACTIONS, "module(the ontology exposes no pair relation, only `compatible`)"


def cell_id(symbol: str, family: str, params: Mapping[str, Any]) -> str:
    """The graph's own id for a spec, so a gene's parent id JOINS the desk's record."""
    try:
        from libs.research.hypothesis_graph import node_id
        return str(node_id(symbol, family, dict(params)))
    except Exception:                                            # pragma: no cover - desk import
        body = json.dumps({"s": symbol, "f": family, "p": dict(params)}, sort_keys=True,
                          default=str)
        return f"{symbol}.{family}.{hashlib.sha256(body.encode()).hexdigest()[:16]}"


# ------------------------------------------------------------------ the genes
def _gene(lane: str, symbol: str, family: str, params: dict[str, Any], chart: str, session: str,
          evidence: dict[str, Any]) -> dict[str, Any] | None:
    symbol, family = str(symbol or "").upper(), str(family or "")
    if not symbol or not family or family in NOT_A_GENE or not may_hypothesise(symbol):
        return None
    mech = mechanism_class(family)
    if mech == UNKNOWN:
        return None
    return {"gene_id": cell_id(symbol, family, params), "lane": lane, "symbol": symbol,
            "family": family, "params": dict(params), "chart": chart or "H1",
            "session": session or "all", "mechanism": mech, "evidence": evidence}


def dsr_bar() -> tuple[float, str]:
    try:
        from research.gate_policy import DSR_THRESHOLD
        return float(DSR_THRESHOLD), "gate_policy.DSR_THRESHOLD"
    except Exception:                                            # pragma: no cover - desk import
        return DSR_BAR, "module fallback"


def last_gate() -> tuple[str, str]:
    try:
        from libs.research.hypothesis_graph import GATE_ORDER
        return str(GATE_ORDER[-1]), "hypothesis_graph.GATE_ORDER"
    except Exception:                                            # pragma: no cover - desk import
        return "expected_value", "module fallback"


def near_survivor(row: dict[str, Any], bar: float, final: str) -> dict[str, Any] | None:
    """THE 20% RULE. A cell is a near-survivor when it died on the LAST gate -- it cleared
    everything the desk knows how to ask -- or when its deflated Sharpe came within NEAR_FRAC of
    the bar. Both are cells whose MECHANISM is the open question and whose sample was the answer,
    which is exactly the population a recombination should draw from."""
    if row.get("passed"):
        return None
    raw = row.get("stages")
    stages: dict[str, Any] = raw if isinstance(raw, dict) else {}
    terminal = str(row.get("terminal_gate") or "")
    if terminal == final:
        return {"near_basis": "terminal gate was the last gate", "terminal_gate": terminal,
                "ratio": None}
    raw_ds = stages.get("deflated_sharpe")
    ds: dict[str, Any] = raw_ds if isinstance(raw_ds, dict) else {}
    dsr, sr0 = _num(ds.get("dsr")), _num(ds.get("sr0"))
    raw_iss = stages.get("in_sample_screen")
    iss: dict[str, Any] = raw_iss if isinstance(raw_iss, dict) else {}
    sharpe = _num(iss.get("sharpe"))
    if dsr is not None and bar > 0 and dsr >= (1.0 - NEAR_FRAC) * bar:
        return {"near_basis": f"dsr {dsr:.4f} within {NEAR_FRAC:.0%} of the {bar:.2f} bar",
                "terminal_gate": terminal, "ratio": round(dsr / bar, 4)}
    if sharpe is not None and sr0 is not None and sr0 > 0 and sharpe >= (1.0 - NEAR_FRAC) * sr0:
        return {"near_basis": f"in-sample sharpe {sharpe:.4f} within {NEAR_FRAC:.0%} of the "
                              f"deflated hurdle sr0 {sr0:.4f}",
                "terminal_gate": terminal, "ratio": round(sharpe / sr0, 4)}
    return None


def collect(note: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(genes, unmeasured) from the three lanes: LIVE/STANDBY sleeves, ten-gate certificates, and
    the near-survivors of the gauntlet. Ranked strongest lane first, because the cap is real."""
    genes: dict[str, dict[str, Any]] = {}
    unmeasured: list[dict[str, Any]] = []
    refused_lane: set[str] = set()
    unknown_mech = 0

    def add(row: dict[str, Any] | None, symbol: str, family: str) -> None:
        nonlocal unknown_mech
        if row is not None:
            prev = genes.get(row["gene_id"])
            if prev is None or LANE_RANK.get(row["lane"], 0) > LANE_RANK.get(prev["lane"], 0):
                genes[row["gene_id"]] = row
            return
        if symbol and not may_hypothesise(symbol):
            refused_lane.add(symbol)
        elif family and family not in NOT_A_GENE and mechanism_class(family) == UNKNOWN:
            unknown_mech += 1

    doc = _read_json(SLEEVES, note, default={})
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        lane = str(row.get("status") or "").upper()
        if lane not in ("LIVE", "STANDBY"):
            continue
        fam, sym = str(row.get("family") or ""), str(row.get("symbol") or "")
        params = {k: row[k] for k in ("stop_atr", "target_atr", "max_hold", "rr", "wait_bars")
                  if k in row}
        add(_gene(lane, sym, fam, params, str(row.get("timeframe") or "H1"),
                  str(row.get("session") or "all"),
                  {"source": "sleeves.json", "risk_frac": row.get("risk_frac")}), sym, fam)

    doc = _read_json(SURVIVORS, note, default={})
    for cell, row in ((doc.get("survivors") if isinstance(doc, dict) else None) or {}).items():
        if not isinstance(row, dict):
            continue
        raw = row.get("shadow_spec")
        spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
        raw_gates = row.get("gates")
        gates: dict[str, Any] = raw_gates if isinstance(raw_gates, dict) else {}
        sym = str(spec.get("symbol") or row.get("sym") or "")
        fam = str(spec.get("family") or "")
        raw_params = spec.get("params")
        add(_gene("CERTIFIED", sym, fam, raw_params if isinstance(raw_params, dict) else {},
                  str(spec.get("timeframe") or "H1"),
                  str(spec.get("selector") or spec.get("session") or "all"),
                  {"source": "UNIVERSAL_SURVIVORS.json", "cell": str(cell),
                   "ev": _num((gates.get("expected_value") or {}).get("ev")),
                   "in_sample_sharpe": _num((gates.get("in_sample_screen") or {}).get("sharpe"))}),
            sym, fam)

    bar, bar_src = dsr_bar()
    final, gate_src = last_gate()
    note["dsr_bar"] = f"{bar} ({bar_src})"
    note["last_gate"] = f"{final} ({gate_src})"
    doc = _read_json(GATES_EXTERNAL, note, default={})
    verdicts = (doc.get("verdicts") if isinstance(doc, dict) else None) or []
    thin = _read_jsonl(GATE_LEDGER, note)
    n_near = 0
    for row in list(verdicts) + thin:
        if not isinstance(row, dict):
            continue
        near = near_survivor(row, bar, final)
        if near is None:
            continue
        n_near += 1
        sym, fam = str(row.get("sym") or ""), str(row.get("family") or "")
        add(_gene("NEAR_SURVIVOR", sym, fam, {}, "H1", "all",
                  {"source": "gate verdicts", "cell": str(row.get("cell") or ""), **near}),
            sym, fam)

    if refused_lane:
        unmeasured.append({"what": "genes refused by the two-lane mandate", "n": len(refused_lane),
                           "symbols": sorted(refused_lane)[:12],
                           "why": "these instruments are traded on news and earnings reaction, "
                                  "never hunted for statistical hypotheses, so their cells are "
                                  "not genes either"})
    if unknown_mech:
        unmeasured.append({"what": "cells whose family has no named mechanism", "n": unknown_mech,
                           "why": "an UNKNOWN mechanism has no economics to interact with, so no "
                                  "`why` can be written for any combination it enters; the count "
                                  "is the measurement, not an omission"})
    if not n_near:
        unmeasured.append({"what": "near-survivors", "n": 0,
                           "why": f"no judged cell died on `{final}` or came within "
                                  f"{NEAR_FRAC:.0%} of the {bar} deflated-Sharpe bar in the "
                                  "readable verdicts"})
    ordered = sorted(genes.values(), key=lambda g: (-LANE_RANK.get(g["lane"], 0), g["gene_id"]))
    return ordered, unmeasured


# ------------------------------------------------------------------ the combinations
def coherent(classes: tuple[str, ...], table: dict[frozenset[str], str]
             ) -> tuple[bool, list[str]]:
    """A combination is coherent only when EVERY pair inside it is in the table. A triple with one
    unexplained pair is a triple nobody can defend, and the `why` would be two thirds of a
    sentence."""
    whys: list[str] = []
    for a, b in itertools.combinations(sorted(set(classes)), 2):
        why = table.get(frozenset({a, b}))
        if why is None:
            return False, []
        whys.append(f"{a} x {b}: {why}")
    return bool(whys), whys


def express_best(combo: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick WHICH gene is the base rule and which are conditions. Lane rank answers it first --
    the strongest survivor keeps its family and parameters -- but if that ordering cannot be
    hosted and another can, the hostable one wins and says so. The alternative is donating
    nothing while a perfectly expressible version of the same claim sits one permutation away."""
    ordered = sorted(combo, key=lambda g: (-LANE_RANK.get(g["lane"], 0), g["gene_id"]))
    first = express(ordered[0], ordered[1:])
    if first["hosted_by"]:
        return {**first, "ordered": ordered, "primary_chosen_for": "lane rank"}
    for i in range(1, len(ordered)):
        alt = [ordered[i]] + [g for j, g in enumerate(ordered) if j != i]
        built = express(alt[0], alt[1:])
        if built["hosted_by"]:
            return {**built, "ordered": alt, "primary_chosen_for": "hostability"}
    return {**first, "ordered": ordered, "primary_chosen_for": "lane rank"}


def express(primary: dict[str, Any], others: list[dict[str, Any]]) -> dict[str, Any]:
    """How the combination is BUILT: the primary gene's family and parameters, with each other
    gene as a condition tag. `hosted_by` is the family when it can honour every tag, and None when
    the combination has to leave as a payload for the discovery compiler."""
    params = dict(primary["params"])
    knobs = family_knobs(primary["family"])
    tags: list[dict[str, Any]] = []
    hosted = True
    for gene in others:
        knob: str | None
        window = str(gene["session"] or "all")
        if window not in ("", "all"):
            # THE STRONGEST CONDITION A GENE CAN CONTRIBUTE IS THE ONE IT PROVED OUT IN. A gene
            # carrying a real window donates that window, and EVERY family honours it:
            # `family_call.signals` pops `session` and applies `session_filter`, so it never
            # reaches the family's own signature. Its mechanism class is used only when it has no
            # window of its own to lend.
            kind, value, knob = "session", window, "session"
        else:
            kind = CONDITION_KIND.get(gene["mechanism"], "state")
            value = str(gene["mechanism"])
            knob = next((k for k in CONDITION_KNOBS.get(kind, ()) if k in knobs), None)
        tags.append({"gene_id": gene["gene_id"], "mechanism": gene["mechanism"], "kind": kind,
                     "value": value, "knob": knob})
        if knob is None:
            hosted = False
        else:
            params[knob] = value
    return {"params": params, "tags": tags,
            "hosted_by": primary["family"] if hosted else None,
            "host_note": ("the primary family honours every condition tag" if hosted else
                          "no registered family can host these tags -- the gauntlet filters params "
                          "to the family's signature, so the tag would be dropped and the "
                          "combination would be its parent wearing a label")}


def allocate(pool: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    """Spend the cap round-robin: at each step take the coherent combination whose mechanism-class
    SHAPE has been picked least, breaking ties by the primary gene picked least and then by lane
    strength. Breadth first, and the leftover budget still gets spent."""
    by_shape: dict[frozenset[str], int] = {}
    by_primary: dict[str, int] = {}
    left = list(pool)
    out: list[dict[str, Any]] = []
    while left and len(out) < cap:
        left.sort(key=lambda c: (by_shape.get(c["_shape"], 0), by_primary.get(c["_primary"], 0),
                                 -int(c["_strength"]), c["n_genes"], c["combination_id"]))
        pick = left.pop(0)
        by_shape[pick["_shape"]] = by_shape.get(pick["_shape"], 0) + 1
        by_primary[pick["_primary"]] = by_primary.get(pick["_primary"], 0) + 1
        out.append({k: v for k, v in pick.items() if not k.startswith("_")})
    return out


def combinations(genes: list[dict[str, Any]], table: dict[frozenset[str], str], *,
                 cap: int, budget_s: float, t0: float
                 ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(combinations, refusal census). Every coherent combination is ENUMERATED, and the cap is
    then spent BREADTH FIRST: the shape with the fewest picks so far goes next, then the primary
    gene with the fewest.

    MEASURED ON THIS BOX, 2026-09-17, and it is why the allocation is a second pass. The gene pool
    is lopsided -- 22 of 48 genes are `breakout_liquidity` and 16 are `session_handover` -- so a
    single walk in lane order spent all 40 slots on forty spellings of one pair. A hard per-shape
    cap fixed the repetition and then filled 2 of 40 slots, which throws away paid-for knowledge to
    avoid repeating it. Round-robin does both: every shape and every primary is reached before any
    is repeated, and the leftover budget still gets spent.
    """
    refused: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    pool: list[dict[str, Any]] = []
    seen: set[frozenset[str]] = set()
    walked = 0
    for size in (2, min(MAX_GENES, 3)):
        for combo in itertools.combinations(genes, size):
            walked += 1
            if len(pool) >= POOL_MAX or time.monotonic() - t0 > budget_s:
                break
            ids = frozenset(g["gene_id"] for g in combo)
            if len(ids) < size or ids in seen:
                continue
            classes = tuple(g["mechanism"] for g in combo)
            if len(set(classes)) < size:
                refused["same_mechanism_class"] = refused.get("same_mechanism_class", 0) + 1
                continue
            ok, whys = coherent(classes, table)
            if not ok:
                key = " x ".join(sorted(set(classes)))
                refused[key] = refused.get(key, 0) + 1
                if len(samples) < 12:
                    samples.append({"classes": sorted(set(classes)),
                                    "why_refused": "no declared interaction: these mechanisms do "
                                                   "not act on each other, so the combination "
                                                   "would fit better with nothing to defend it"})
                continue
            seen.add(ids)
            built = express_best(list(combo))
            ordered = built["ordered"]
            primary = ordered[0]
            pool.append({
                "combination_id": hashlib.sha256("|".join(sorted(ids)).encode()).hexdigest()[:16],
                "genes": [{"gene_id": g["gene_id"], "lane": g["lane"], "symbol": g["symbol"],
                           "family": g["family"], "mechanism": g["mechanism"],
                           "session": g["session"]} for g in ordered],
                "n_genes": size, "why": whys, "primary": primary["family"],
                "symbol": primary["symbol"], "chart": primary["chart"],
                "params": built["params"], "tags": built["tags"],
                "primary_chosen_for": built["primary_chosen_for"],
                "hosted_by": built["hosted_by"], "host_note": built["host_note"], "queued": False,
                "_shape": frozenset(classes), "_primary": primary["gene_id"],
                "_strength": sum(LANE_RANK.get(g["lane"], 0) for g in ordered)})
        if len(pool) >= POOL_MAX or time.monotonic() - t0 > budget_s:
            break
    out = allocate(pool, cap)
    return out, {"by_pair": dict(sorted(refused.items(), key=lambda kv: -kv[1])[:20]),
                 "n_refused": sum(refused.values()), "samples": samples,
                 "n_coherent": len(pool), "n_walked": walked,
                 "n_crowded_out": max(0, len(pool) - len(out)),
                 "diversity_rule": "the cap is spent round-robin over mechanism-class shapes and "
                                   "then over primary genes, so every shape is reached before any "
                                   "is repeated and the leftover budget is still spent"}


# ------------------------------------------------------------------ recording and donation
def rows_for(combos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Intake rows for the hosted combinations: EXACT_RECIPE candidates carrying every gene."""
    try:
        from research.proposer_common import candidate
    except Exception:                                            # pragma: no cover - desk import
        return []
    rows = []
    for c in combos:
        if not c["hosted_by"]:
            continue
        names = " + ".join(f"{g['family']}({g['mechanism']})" for g in c["genes"])
        row = candidate(SEAT, c["symbol"], c["primary"], dict(c["params"]),
                        mechanism="; ".join(c["why"])[:600],
                        title=f"{c['symbol']} {names} -- recombination of "
                              f"{c['n_genes']} surviving genes",
                        evidence={"genes": c["genes"], "why": c["why"], "tags": c["tags"],
                                  "combination_id": c["combination_id"], "rule": RULE})
        row.update({"parent": c["genes"][0]["gene_id"], "operator": f"recombine:{c['n_genes']}",
                    "trial_family": c["primary"], "timeframe": c["chart"],
                    "lineage": {"genes": [g["gene_id"] for g in c["genes"]],
                                "mechanisms": [g["mechanism"] for g in c["genes"]]}})
        rows.append(row)
    return rows


def record(combos: list[dict[str, Any]], note: dict[str, str]) -> tuple[int, int]:
    """(discoveries created, candidates enqueued). Each combination is ONE DiscoveryObject in state
    EXPANDED -- the genes are the parents, the interaction is the mechanism, and the counters are
    the conversion debt the compiler then owes."""
    try:
        from libs.moat import registry as reg
    except Exception as exc:                                     # pragma: no cover - install
        note["registry"] = f"UNIMPORTABLE({type(exc).__name__})"
        return 0, 0
    try:
        conn = reg.connect()
    except Exception as exc:
        note["registry"] = f"UNREACHABLE({type(exc).__name__}: {exc})"
        return 0, 0
    created = queued = 0
    try:
        for c in combos:
            parents = [g["gene_id"] for g in c["genes"]]
            payload = {"kind": "combination", "combination_id": c["combination_id"],
                       "genes": c["genes"], "why": c["why"], "tags": c["tags"],
                       "hosted_by": c["hosted_by"], "host_note": c["host_note"],
                       "family": c["primary"], "params": c["params"], "chart": c["chart"],
                       "symbol": c["symbol"], "rule": RULE}
            did, new = reg.record_discovery(
                source_id=f"{SEAT}:{c['combination_id']}", source_type="recombination",
                origin="MOAT", generator=SEAT, parent_ids=parents,
                mechanism=" + ".join(g["mechanism"] for g in c["genes"]),
                economic_rationale="; ".join(c["why"])[:900], assets=[c["symbol"]],
                sessions=[g["session"] for g in c["genes"]],
                exact_rule=json.dumps({"family": c["primary"], "params": c["params"]},
                                      sort_keys=True, default=str),
                falsifier=("the combination adds nothing over its strongest gene alone on the "
                           "same instrument and window"),
                payload=payload, conn=conn)
            created += int(new)
            hosted = 1 if c["hosted_by"] else 0
            reg.set_discovery_state(did, "EXPANDED", possible_cells=1, generated_cells=1,
                                    compiled_cells=hosted, queued_cells=hosted,
                                    blocked_cells=0 if hosted else 1, conn=conn)
            for pid in parents:
                reg.link("cell", pid, "discovery", did, "recombined", conn=conn)
            if c["hosted_by"]:
                reg.enqueue_candidate(
                    family=c["primary"], symbol=c["symbol"], params=c["params"], origin="MOAT",
                    mechanism="; ".join(c["why"])[:200], status="queued", generator=SEAT,
                    source_id=SEAT, discovery_id=did, transformation="recombination",
                    trial_family=c["primary"], parent_ids=parents, chart=c["chart"],
                    session=c["params"].get("session") or "all",
                    mechanism_strength=0.7, causal_rationale="; ".join(c["why"])[:900], conn=conn)
                c["queued"] = True
                queued += 1
        reg.generator_yield_update(SEAT, generated=len(combos), conn=conn)
    except Exception as exc:
        note["registry"] = f"WRITE_FAILED({type(exc).__name__}: {exc})"
    finally:
        conn.close()
    return created, queued


# ------------------------------------------------------------------ build
def build(*, max_combinations: int = MAX_COMBINATIONS, budget_s: float = BUDGET_S
          ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(report, combinations). Never raises on a missing input."""
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    note: dict[str, str] = {}
    genes, unmeasured = collect(note)
    table, source = interaction_table()
    combos, refused = combinations(genes, table, cap=max(0, int(max_combinations)),
                                   budget_s=budget_s, t0=t0)
    by_lane: dict[str, int] = {}
    for g in genes:
        by_lane[g["lane"]] = by_lane.get(g["lane"], 0) + 1
    if len(genes) < 2:
        unmeasured.append({"what": "combinations", "n": 0,
                           "why": f"{len(genes)} gene(s) reachable: a recombination needs two "
                                  "survivors with different named mechanisms"})
    if time.monotonic() - t0 > budget_s:
        unmeasured.append({"what": "gene pairs not walked",
                           "why": f"the {budget_s:g}s budget ran out; the walk is strongest lane "
                                  "first, so what was skipped is the weakest evidence"})
    unhosted = [c for c in combos if not c["hosted_by"]]
    if unhosted:
        unmeasured.append({"what": "combinations no family can host", "n": len(unhosted),
                           "why": "their condition tags are not in any registered family's "
                                  "signature, so they leave as `combination` payloads for the "
                                  "discovery compiler rather than as donated cells"})
    report = {
        "at": now, "n_genes": len(genes), "by_lane": by_lane,
        "interaction_table": {"source": source, "n_pairs": len(table)},
        "combinations": combos, "refused_incoherent": refused,
        "discoveries_recorded": 0, "donated": 0, "inputs": note,
        "max_combinations": max_combinations, "budget_s": budget_s,
        "seconds": round(time.monotonic() - t0, 2), "unmeasured": unmeasured, "rule": RULE}
    return report, combos


def _write(path: Path, doc: dict[str, Any]) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="print; write nothing, record nothing, donate nothing")
    ap.add_argument("--max-combinations", type=int, default=MAX_COMBINATIONS)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    a = ap.parse_args(argv)
    rep, combos = build(max_combinations=a.max_combinations, budget_s=a.budget_s)
    if not a.dry_run and combos:
        created, queued = record(combos, rep["inputs"])
        rep["discoveries_recorded"] = created
        rows = rows_for(combos)
        if rows:
            from research.proposer_common import donate, donation_counts
            donate(SEAT, [dict(r) for r in rows], tests_run=len(combos))
            rep["donation"] = donation_counts()
            rep["donated"] = int(rep["donation"].get("donated") or 0)
        rep["queued"] = queued
    print(f"ALPHA_RECOMBINATION {rep['at']}  genes={rep['n_genes']} "
          f"combinations={len(rep['combinations'])} "
          f"hosted={sum(1 for c in rep['combinations'] if c['hosted_by'])} "
          f"refused={rep['refused_incoherent']['n_refused']} "
          f"recorded={rep['discoveries_recorded']} donated={rep['donated']} {rep['seconds']}s")
    print(f"  lanes    {rep['by_lane']}  table={rep['interaction_table']['source']} "
          f"({rep['interaction_table']['n_pairs']} pairs)")
    for c in rep["combinations"][:5]:
        host = c["hosted_by"] or "PAYLOAD"
        print(f"  {c['symbol']:<10} {'+'.join(g['mechanism'] for g in c['genes']):<52} -> {host}")
    for u in rep["unmeasured"][:5]:
        print(f"  UNMEASURED {u['what']}: {str(u['why'])[:84]}")
    if a.dry_run:
        print("  --dry-run: nothing written, nothing recorded, nothing donated")
        return 0
    _write(OUT, rep)
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
