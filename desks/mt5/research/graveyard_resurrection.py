"""M5/M23 -- THE GRAVEYARD IS MACHINERY, NOT STORAGE, and this is the organ that works it.

THE PRINCIPAL, 2026-09-17: a failed strategy can still contain a valuable economic mechanism.

The desk buries about thirty thousand cells and remembers only that they died. That is the most
expensive record it owns and the least used one: every one of those cells cost ten gates of compute
AND a share of a fixed family-wise error budget, and the only thing ever extracted from the pile is
a ranking of what to test next (`negative_knowledge`, whose EXPLORE_FLOOR and per-family gate
frequency this organ imports rather than re-derives). Nothing ever went back and ASKED THE FAILURES
A QUESTION.

A failure is not one fact, it is ten. "EURAUD overnight_gap_decay died at deflated_sharpe" leaves
open whether the mechanism is absent, absent HERE, absent AFTER COSTS, absent in this DIRECTION,
at this HORIZON, or perfectly present and expressed wrong. Each is a different repair and only one
of them is "the mechanism is not real"; the gauntlet answers none of them, because it judges a cell
and a mechanism is not a cell. SO EVERY FAILURE IS CLASSIFIED AND EVERY CLUSTER IS INTERROGATED:
one of `registry.FAILURE_CLASSES` per dead cell, read from its TERMINAL GATE and its own evidence
-- a gate this organ's table does not know leaves the cell UNMEASURED, never guessed (L1.28a) --
then, per cluster of family x mechanism x class, ten questions answered from the cluster's own
SIBLINGS in the graph, each carrying its n or saying UNMEASURED: did it fail everywhere, only in
high vol, only in Asia, only on gold, only after costs, only because of the entry, did the opposite
direction work, did the residual form work, did another asset preserve the mechanism, was the
mechanism right and the expression wrong.

THE MAP FROM FAILURE TO REPAIR IS THE POINT:

    cost_killed       -> REPAIR      a lower-frequency chart and a limit entry
    regime_specific   -> CONDITIONAL the variant that carries the regime tag
    wrong_direction   -> INVERSE     and only where the ontology says the payer pays both ways
    wrong_asset       -> TRANSFER    the sibling instruments where that payer exists
    wrong_horizon     -> REPAIR      the longer hold
    unstable          -> REPAIR      wider parameters from the family neighbourhood
    execution_killed  -> REPAIR      the delayed entry
    forward_decay     -> CONDITIONAL the state the decayed clock may still pay in
    mechanism alive in another family -> COMBINATION of this ground with that expression
    no_edge, redundant-> NOTHING. The mechanism PRIOR is lowered instead.

THAT LAST LINE IS THE DISCIPLINE. An organ that spawns a child from every corpse is a machine for
spending the multiplicity budget on its own history. "No edge" and "redundant" are the verdicts that
say the GROUND is barren rather than the expression wrong; the honest act there is to write the
prior down and walk away, while five or more identical deaths escalate into a COUNTER-HYPOTHESIS
naming the mechanism to test INSTEAD. Everything that does spawn is a DISCOVERY with parents
(EXPANDED -> COMPILED -> QUEUED with counters), a registry candidate charged to the dead cell's own
trial family, and a donated structured hypothesis. A cell already in the graph is never re-donated,
at most 60 candidates leave per run and never more than half from one family -- the cold floor that
stops one loud family eating the hour.

    python desks/mt5/research/graveyard_resurrection.py [--dry-run] [--max-candidates 60]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402
from libs.research import mechanism_ontology as onto  # noqa: E402
from research import axis_registry as ar  # noqa: E402
from research import negative_knowledge as nk  # noqa: E402
from research import proposer_common as pc  # noqa: E402
from research import universe_policy as upol  # noqa: E402

GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
GATE_LEDGER = nk.GATE_LEDGER
SHADOW = nk.SHADOW
GRAVEYARD_MD = ROOT / "backups" / "moat" / "graveyard"
OUT = DESK / "reports" / "GRAVEYARD_RESURRECTION.json"
SOURCE = "graveyard_resurrection"

#: Imported, never re-derived: the floor `negative_knowledge` reserves for the region its own
#: evidence is thinnest in. This organ is that argument in reverse -- it works ONLY where the desk
#: has already been wrong -- so it quotes the floor it lives under.
EXPLORE_FLOOR = nk.EXPLORE_FLOOR
MAX_CANDIDATES = 60
MAX_FAMILY_SHARE = 0.5
BUDGET_S = 240.0
#: Judged siblings a question needs before its answer is a measurement; below it, UNMEASURED with n.
MIN_SIBLINGS = 3
#: Identical deaths in one cluster before the desk stops repairing and writes a counter-hypothesis.
MIN_COUNTER = 5
TRANSFER_INSTRUMENTS = 3
#: |t| at which a NEGATIVE gross expectancy is evidence of a mirrored sign rather than of noise.
DIRECTION_T = 2.0
#: Pseudo-count in novelty_vs_graveyard = 1 - failed / (failed + NOVELTY_PSEUDO).
NOVELTY_PSEUDO = 3.0
MAX_ROWS = 400_000
MAX_MD_BYTES = 8 * 1024 * 1024

#: TERMINAL GATE -> FAILURE CLASS, in order, first needle wins. A gate NOT on this table leaves the
#: cell UNMEASURED: a class invented for an unrecognised gate spawns a repair for a disease nobody
#: diagnosed, which is the guess L1.28a forbids.
GATE_CLASS: tuple[tuple[str, str], ...] = (
    ("turnover", "cost_killed"), ("cost", "cost_killed"), ("swap", "cost_killed"),
    ("commission", "cost_killed"), ("slippage", "execution_killed"),
    ("execution", "execution_killed"), ("fill", "execution_killed"),
    ("spread", "execution_killed"), ("impact", "execution_killed"),
    ("one_regime", "regime_specific"), ("regime", "regime_specific"),
    ("walk_forward", "unstable"), ("walk", "unstable"), ("stability", "unstable"),
    ("stable", "unstable"), ("fragil", "unstable"), ("novelty", "redundant"),
    ("duplicate", "redundant"), ("redundan", "redundant"), ("correlation", "redundant"),
    ("horizon", "wrong_horizon"), ("ttl", "wrong_horizon"), ("holding", "wrong_horizon"),
    ("deflated", "no_edge"), ("reality", "no_edge"), ("sharpe", "no_edge"),
    ("screen", "no_edge"), ("expectancy", "no_edge"), ("t_stat", "no_edge"),
    ("power", "no_edge"), ("spa", "no_edge"), ("pbo", "no_edge"))
#: Classes whose repair is a NEW CELL, and the kind of move that repair is.
RESURRECTION: dict[str, tuple[str, str]] = {
    "cost_killed": ("repair", "lower_frequency_limit_entry"),
    "regime_specific": ("conditional", "regime_conditioned"),
    "wrong_direction": ("inverse", "mirrored_direction"),
    "wrong_asset": ("transfer", "sibling_instrument"),
    "wrong_horizon": ("repair", "longer_hold"), "unstable": ("repair", "wider_params"),
    "execution_killed": ("repair", "delayed_entry"),
    "forward_decay": ("conditional", "regime_conditioned_after_decay")}
#: The two verdicts that mean the GROUND is barren rather than the expression wrong.
BARREN: tuple[str, ...] = ("no_edge", "redundant")
#: The alternative mechanism a recurrent death points at, when the cluster's siblings name none.
COUNTER_MECHANISM: dict[str, str] = {
    "no_edge": "execution_microstructure", "cost_killed": "execution_microstructure",
    "execution_killed": "execution_microstructure", "regime_specific": "regime_transition",
    "unstable": "regime_transition", "redundant": "relative_value_dislocation",
    "wrong_direction": "positioning_crowding", "forward_decay": "positioning_crowding",
    "wrong_asset": "cross_market_lead", "wrong_horizon": "trend_persistence"}
#: Mechanisms whose payer is CONTRACTED or FORCED to act one way -- a margin call never becomes a
#: margin gift. Mirroring the sign there is not the hypothesis in reverse, it is a claim with no
#: payer at all.
ONE_WAY_MECHANISMS = frozenset({"carry_rollover", "forced_flow", "forced_liquidation",
                                "fx_fixing_flow", "hedging_demand_close_flow"})
_ONTOLOGY_ONE_WAY = frozenset({"PERP_FUNDING_CARRY", "FORCED_LIQUIDATION"})
SYMMETRIC_TRANSFORMS = frozenset({"ZSCORE", "DIFFERENCE", "DIVERGENCE", "RESIDUAL",
                                  "CROSS_SECTIONAL_RANK", "PERCENTILE"})
COARSER = {"M1": "M5", "M5": "M15", "M15": "H1", "M30": "H1", "H1": "H4", "H4": "D1"}
_WIDEN = ("lookback", "window", "win", "period", "span", "bars", "len")
_LOOSEN = ("entry_z", "_z", "thresh", "band", "atr", "mult")
_HOLD = ("ttl_bars", "max_hold", "hold_bars", "hold", "horizon")
_SIDE_NUM = ("side", "direction", "sign")
_SIDE_MODE = {"revert": "follow", "follow": "revert", "long": "short", "short": "long",
              "buy": "sell", "sell": "buy", "fade": "momentum", "momentum": "fade"}
_VOL = ("vol", "volatility", "turbulent", "stress", "crisis")
_TAG_RE = re.compile(r"`([a-z][a-z0-9_]{3,48})`")
_HEAD_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
RULE = ("every failure generates questions; failure -> {conditional, inverse, transfer, repair, "
        "combination}; no edge and redundancy lower the prior instead of spawning")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: Any) -> None:
    """Atomic where the filesystem allows it. `os.replace` onto a read-only file is WinError 5."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except OSError:
        path.write_text(tmp.read_text("utf-8"), "utf-8")
        tmp.unlink(missing_ok=True)


def _jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    """Tolerant: a missing file, a half-written line and a BOM are all 'nothing from here'."""
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                if len(out) >= limit:
                    break
                line = raw.strip().lstrip("﻿")
                try:
                    row = json.loads(line) if line else None
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        pass
    return out


def _share(flags: list[bool]) -> float:
    return float(np.asarray(flags, dtype=float).mean()) if flags else 0.0


def _family_root(family: Any) -> str:
    """The trial family a cell is charged to -- the name before any variant spelling."""
    return re.split(r"[.#(]", str(family or "").strip().lower(), maxsplit=1)[0]


# -------------------------------------------------------------- 1. failure classification
def _direction_evidence(ev: dict[str, Any]) -> bool:
    """A NEGATIVE gross expectancy carried by a real |t|: the sign is wrong, not the mechanism."""
    gross, t = ev.get("gross", ev.get("exp_r")), ev.get("t", ev.get("t_stat"))
    if not isinstance(gross, (int, float)) or isinstance(gross, bool) or gross >= 0:
        return False
    return isinstance(t, (int, float)) and not isinstance(t, bool) and abs(float(t)) >= DIRECTION_T


def classify_failure(terminal_gate: Any, evidence: dict[str, Any] | None = None) -> str:
    """ONE of `registry.FAILURE_CLASSES` for a dead cell, or UNMEASURED. Never a guess."""
    ev = evidence or {}
    if ev.get("forward_retired"):
        return "forward_decay"
    gate = str(terminal_gate or "").strip().lower()
    if not gate or gate in ("unknown", "none", "null", "passed"):
        return "wrong_direction" if _direction_evidence(ev) else "UNMEASURED"
    for needle, cls in GATE_CLASS:
        if needle in gate:
            # A no-edge gate over a SIGNED negative expectancy is not "no edge": the cell found the
            # mechanism and took the wrong side of it.
            return "wrong_direction" if cls == "no_edge" and _direction_evidence(ev) else cls
    return "UNMEASURED"


def allows_inverse(mechanism: str) -> tuple[bool, str]:
    """May this mechanism's sign be mirrored? The ontology decides; silence refuses."""
    m = str(mechanism or "").strip()
    if not m or m == ar.UNKNOWN:
        return False, "the mechanism is UNKNOWN: absence of a rule is not permission to mirror it"
    core = onto.CORE_MECHANISMS.get(m.upper())
    if core is not None:
        if m.upper() in _ONTOLOGY_ONE_WAY:
            return False, f"{m}: the ontology's payer pays in one direction only"
        if SYMMETRIC_TRANSFORMS & set(core.valid_transforms):
            return True, f"{m}: the ontology declares signed, two-sided transforms"
        return False, f"{m}: no signed transform in the ontology's own vocabulary"
    if m.lower() in ONE_WAY_MECHANISMS:
        return False, f"{m}: the payer is forced or contracted one way; the mirror has no payer"
    if m.lower() in ar.MECHANISM_ACTOR:
        return True, f"{m}: a registered two-sided participant, so the sign is a free parameter"
    return False, f"{m}: outside the desk's registered mechanism vocabulary"


# ----------------------------------------------------------------- 2. the dead population
@dataclass
class Dead:
    """One dead cell, whatever buried it."""

    cell: str
    symbol: str
    family: str
    params: dict[str, Any]
    terminal_gate: str
    origin: str
    at: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    failure_class: str = "UNMEASURED"
    axes: dict[str, str] = field(default_factory=dict)


def _axes(symbol: str, family: str, params: dict[str, Any]) -> dict[str, str]:
    try:
        return ar.axis_cell(symbol, family, params)
    except Exception:
        return {"mechanism": ar.UNKNOWN, "asset_class": ar.UNKNOWN, "chart": "H1",
                "session": "all", "regime": "unconditional", "horizon": ar.UNKNOWN}


def _dead(cell: str, sym: str, fam: str, params: dict[str, Any], gate: str, origin: str,
          at: str, ev: dict[str, Any]) -> Dead:
    return Dead(cell=cell, symbol=sym, family=fam, params=params, terminal_gate=gate,
                origin=origin, at=at, evidence=ev, axes=_axes(sym, fam, params))


def _gate_of_graph_row(row: dict[str, Any]) -> str:
    gates = row.get("gates") if isinstance(row.get("gates"), dict) else {}
    for name, val in gates.items():
        if isinstance(val, dict) and val.get("passed") is False:
            return str(name)
    m = re.search(r"terminal[_ ]gate[:= ]+([a-z0-9_]+)", str(row.get("why") or ""), re.I)
    return m.group(1) if m else ""


def read_graph(limit: int = MAX_ROWS) -> list[dict[str, Any]]:
    """Every graph row, latest write per id -- the graph is append-only with re-statements."""
    latest: dict[str, dict[str, Any]] = {}
    for row in _jsonl(GRAPH, limit):
        if str(row.get("id") or ""):
            latest[str(row["id"])] = row
    return list(latest.values())


def dead_cells(rows: list[dict[str, Any]], limit: int = MAX_ROWS) -> list[Dead]:
    """The whole dead population: the graph's FAILED cells, the gate ledger's rejections (the only
    store that names WHICH gate killed a cell), and retired forward clocks that HELD a certificate
    -- the one failure the gauntlet cannot see, because it happened after it."""
    out: list[Dead] = []
    keys = ("exp_r", "t_stat", "gross", "t", "n")
    for r in rows:
        if str(r.get("fate") or "").upper() not in ("FAILED", "BURIED"):
            continue
        params = r.get("params") if isinstance(r.get("params"), dict) else {}
        out.append(_dead(str(r.get("id") or ""), str(r.get("symbol") or ""),
                         str(r.get("family") or ""), params, _gate_of_graph_row(r),
                         "hypothesis_graph", str(r.get("at") or ""),
                         {k: r[k] for k in keys if k in r}))
    for r in _jsonl(GATE_LEDGER, limit):
        cell = str(r.get("cell") or "")
        if r.get("passed") or not cell:
            continue
        sym, fam = str(r.get("sym") or ""), str(r.get("family") or "")
        if not fam:
            parsed = ar.parse_shadow_key(cell)
            sym, fam = sym or str(parsed.get("symbol") or ""), str(parsed.get("family") or "")
        out.append(_dead(cell, sym, fam, {}, str(r.get("terminal_gate") or ""), "gate_ledger",
                         str(r.get("at") or ""), {k: r[k] for k in keys if k in r}))
    for path in SHADOW:
        doc = nk._load_json(path)
        for key, row in (doc.items() if isinstance(doc, dict) else ()):
            status = str(row.get("status") or "").upper() if isinstance(row, dict) else ""
            if not status.startswith(("RETIRED", "QUARANTINED")):
                continue
            if not str(row.get("gate_admission") or "").strip():
                continue                     # retired without ever certifying: not a decay
            parsed = ar.parse_shadow_key(key)
            out.append(_dead(key, str(parsed.get("symbol") or ""), str(parsed.get("family") or ""),
                             {}, "forward_retirement", "forward_clock",
                             str(row.get("last_attempt_at") or ""),
                             {"forward_retired": True, "status": status, "n": row.get("n"),
                              "exp_r": row.get("exp_r"), "t": row.get("forward_t")}))
    return out


def do_not_repeat(path: Path | None = None) -> dict[str, Any]:
    """The markdown graveyard, parsed tolerantly: names that may never be re-tested, and tags.

    Prose written by hand over a year, so nothing about its shape is assumed. A heading opens an
    entry, the inline-code spans inside it are its tags, and an entry whose NAME carries a family as
    a whole name BLOCKS that family's resurrection -- a permanent kill is a permanent kill, and an
    organ built to reopen graves is the one place that must honour it.
    """
    p = path or GRAVEYARD_MD
    try:
        if p.stat().st_size > MAX_MD_BYTES:
            return {"status": "UNMEASURED", "why": f"{p.name} over {MAX_MD_BYTES} bytes"}
        text = p.read_text("utf-8", errors="replace")
    except OSError as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__} reading {p}"}
    entries: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for line in text.splitlines():
        head = _HEAD_RE.match(line)
        if head:
            if cur is not None:
                entries.append(cur)
            raw = head.group(2).replace("`", "").replace("*", "")
            name = re.split(r"\s+[-—]{1,2}\s+|\s+\(", raw, maxsplit=1)[0].strip().lower()
            cur = {"name": name, "heading": raw.strip()[:160], "tags": []}
        elif cur is not None:
            cur["tags"].extend(t for t in _TAG_RE.findall(line) if "_" in t)
    if cur is not None:
        entries.append(cur)
    tags: Counter[str] = Counter()
    for e in entries:
        e["tags"] = sorted(set(e["tags"]))[:8]
        tags.update(e["tags"])
    return {"status": "OK", "n_entries": len(entries), "tags": dict(tags.most_common(20)),
            "names": [e["name"] for e in entries if e["name"]]}


def _blocked(family: str, names: list[str]) -> str:
    """A WHOLE-NAME match, underscores included: `carry` is not blocked by `cash_and_carry_lore`.
    Deliberately conservative -- this list is permanent and unappealable, so a loose match would
    silently retire families nobody killed."""
    fam = _family_root(family)
    if len(fam) < 4:
        return ""
    pat = re.compile(rf"(?<![a-z0-9_]){re.escape(fam)}(?![a-z0-9_])")
    return next((n for n in names if pat.search(n)), "")


# ---------------------------------------------------------------------- 3. the questions
@dataclass
class Sibling:
    symbol: str
    family: str
    params: dict[str, Any]
    fate: str
    axes: dict[str, str]


def _siblings(rows: list[dict[str, Any]]) -> list[Sibling]:
    out: list[Sibling] = []
    for r in rows:
        params = r.get("params") if isinstance(r.get("params"), dict) else {}
        sym, fam = str(r.get("symbol") or ""), str(r.get("family") or "")
        out.append(Sibling(sym, fam, params, str(r.get("fate") or "").upper(),
                           _axes(sym, fam, params)))
    return out


def _unmeasured(why: str, n: int = 0) -> dict[str, Any]:
    return {"answer": "UNMEASURED", "n": n, "why": why}


def _judged(sibs: list[Sibling]) -> list[Sibling]:
    return [s for s in sibs if s.fate in ("FAILED", "BURIED", "CERTIFIED")]


def _only_where(sibs: list[Sibling], pred: Any, label: str) -> dict[str, Any]:
    """Did survival land ONLY inside `pred`, with at least one failure outside it?"""
    judged = _judged(sibs)
    if len(judged) < MIN_SIBLINGS:
        return _unmeasured(f"{len(judged)} judged sibling(s) below {MIN_SIBLINGS}", len(judged))
    cert = [s for s in judged if s.fate == "CERTIFIED"]
    if not cert:
        return {"answer": False, "n": len(judged), "n_survivors": 0,
                "why": f"no sibling survived anywhere, so nothing is specific to {label}"}
    inside = [s for s in cert if pred(s)]
    outside_fail = any(not pred(s) for s in judged if s.fate != "CERTIFIED")
    return {"answer": bool(inside) and len(inside) == len(cert) and outside_fail,
            "n": len(judged), "n_survivors": len(cert), "n_inside": len(inside)}


def _class_share(deaths: list[Dead], cls: str) -> dict[str, Any]:
    known = [d for d in deaths if d.failure_class != "UNMEASURED"]
    if len(known) < MIN_SIBLINGS:
        return _unmeasured(f"{len(known)} classified death(s) below {MIN_SIBLINGS}", len(known))
    share = _share([d.failure_class == cls for d in known])
    return {"answer": bool(share >= 0.5), "n": len(known), "share": round(share, 4)}


def _side_of(params: dict[str, Any]) -> Any:
    for k in _SIDE_NUM:
        v = params.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0:
            return 1 if v > 0 else -1
    for k in ("side_mode", "mode", "bias"):
        v = params.get(k)
        if isinstance(v, str) and v.strip().lower() in _SIDE_MODE:
            return v.strip().lower()
    return None


def questions(deaths: list[Dead], fam_sibs: list[Sibling], mech_sibs: list[Sibling],
              fam_deaths: list[Dead]) -> dict[str, Any]:
    """The ten questions, each answered from the cluster's own siblings or left UNMEASURED."""
    judged = _judged(fam_sibs)
    cert = [s for s in judged if s.fate == "CERTIFIED"]
    everywhere = (_unmeasured(f"{len(judged)} judged sibling(s) below {MIN_SIBLINGS}", len(judged))
                  if len(judged) < MIN_SIBLINGS
                  else {"answer": not cert, "n": len(judged), "n_survivors": len(cert)})
    sides = {_side_of(s.params) for s in cert} - {None}
    dead_sides = {_side_of(d.params) for d in deaths} - {None}
    readable = [s for s in judged if _side_of(s.params) is not None]
    opposite = (_unmeasured("no sibling expresses a readable side", len(readable))
                if not dead_sides or not readable
                else {"answer": bool(sides - dead_sides), "n": len(readable),
                      "survivor_sides": sorted(str(x) for x in sides)})
    resid = [s for s in mech_sibs if "residual" in s.family.lower()]
    residual = (_unmeasured("the mechanism has no residual expression in the graph", len(resid))
                if not resid
                else {"answer": any(s.fate == "CERTIFIED" for s in resid), "n": len(resid)})
    dead_syms = {d.symbol.upper() for d in deaths}
    elsewhere = [s for s in cert if s.symbol.upper() not in dead_syms]
    other_asset = ({"answer": bool(elsewhere), "n": len({s.symbol.upper() for s in judged}),
                    "symbols": sorted({s.symbol.upper() for s in elsewhere})[:6]}
                   if len(judged) >= MIN_SIBLINGS
                   else _unmeasured("too few judged siblings", len(judged)))
    dead_fams = {_family_root(d.family) for d in deaths}
    other_fam = sorted({s.family for s in mech_sibs
                        if s.fate == "CERTIFIED" and _family_root(s.family) not in dead_fams})
    expression = ({"answer": bool(other_fam), "n": len({s.family for s in mech_sibs}),
                   "families": other_fam[:6]}
                  if len(_judged(mech_sibs)) >= MIN_SIBLINGS
                  else _unmeasured("too few judged cells on this mechanism",
                                   len(_judged(mech_sibs))))
    return {
        "did_it_fail_everywhere": everywhere,
        "only_high_vol": _only_where(
            fam_sibs, lambda s: any(t in s.axes.get("regime", "") for t in _VOL), "high vol"),
        "only_asia": _only_where(fam_sibs, lambda s: s.axes.get("session") == "asia", "Asia"),
        "only_xau": _only_where(
            fam_sibs, lambda s: s.symbol.upper().startswith(("XAU", "XAG"))
            or "metal" in s.axes.get("asset_class", ""), "gold"),
        "only_after_costs": _class_share(fam_deaths, "cost_killed"),
        "only_because_of_entry": _class_share(fam_deaths, "execution_killed"),
        "did_the_opposite_direction_work": opposite,
        "did_the_residual_form_work": residual,
        "did_another_asset_preserve_the_mechanism": other_asset,
        "was_the_mechanism_right_and_the_expression_wrong": expression}


# ------------------------------------------------------------------------- 4. the repairs
def _flip(params: dict[str, Any]) -> dict[str, Any] | None:
    p, hit = dict(params), False
    for k in _SIDE_NUM:
        v = p.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0:
            p[k], hit = -v, True
    for k in ("side_mode", "mode", "bias"):
        v = p.get(k)
        if isinstance(v, str) and v.strip().lower() in _SIDE_MODE:
            p[k], hit = _SIDE_MODE[v.strip().lower()], True
    return p if hit else None


def _widen(params: dict[str, Any]) -> dict[str, Any] | None:
    p, hit = dict(params), False
    for k, v in params.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        low = k.lower()
        if any(t in low for t in _WIDEN):
            p[k], hit = (int(v * 2) if isinstance(v, int) else round(float(v) * 2, 6)), True
        elif any(t in low for t in _LOOSEN):
            p[k], hit = round(float(v) * 1.25, 6), True
    return p if hit else None


def _lengthen(params: dict[str, Any]) -> dict[str, Any] | None:
    p = dict(params)
    for k in _HOLD:
        v = p.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            p[k] = int(v * 2) if isinstance(v, int) else round(float(v) * 2, 6)
            return p
    return None


def _regime_tag(qs: dict[str, Any], dead: Dead) -> tuple[str, str]:
    if qs["only_high_vol"].get("answer") is True:
        return "high_volatility", "measured: every surviving sibling carries a volatility state"
    if qs["only_asia"].get("answer") is True:
        return "asia_session", "measured: survival concentrates in the Asia session"
    own = dead.axes.get("regime", "unconditional")
    if own and own != "unconditional":
        return own, "the dead cell's own conditioning axis"
    return "high_volatility", "default state: no sibling names one, so the variant declares it"


def proposals_for(dead: Dead, qs: dict[str, Any], pool: dict[str, list[str]]
                  ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Every resurrection this dead cell earns, plus the refusals it earned instead."""
    cls = dead.failure_class
    out: list[dict[str, Any]] = []
    ref: list[dict[str, str]] = []
    if cls in BARREN or cls not in RESURRECTION:
        return out, ref
    kind, variant = RESURRECTION[cls]
    mech = dead.axes.get("mechanism", ar.UNKNOWN)
    base = {"kind": kind, "variant": variant, "family": dead.family, "symbol": dead.symbol,
            "params": dict(dead.params), "mechanism": mech, "parent": dead.cell,
            "failure_class": cls}
    if cls == "cost_killed":
        chart = COARSER.get(dead.axes.get("chart", "H1"))
        if chart is None:
            ref.append({"cell": dead.cell, "why": "already on the coarsest chart the desk has"})
        else:
            out.append({**base, "chart": chart,
                        "params": {**dead.params, "timeframe": chart, "entry_style": "limit"},
                        "why": (f"the round trip ate it at {dead.axes.get('chart')}: at {chart} "
                                f"the mechanism pays that cost once per bar, entering on a limit")})
    elif cls in ("regime_specific", "forward_decay"):
        tag, why = _regime_tag(qs, dead)
        out.append({**base, "params": {**dead.params, "regime": tag}, "regime": tag,
                    "why": f"conditioned on {tag} ({why})"})
    elif cls == "wrong_direction":
        ok, why = allows_inverse(mech)
        flipped = _flip(dead.params) if ok else None
        if not ok:
            ref.append({"cell": dead.cell, "why": f"inverse refused -- {why}"})
        elif flipped is None:
            ref.append({"cell": dead.cell,
                        "why": "no readable side in the params: nothing to mirror"})
        else:
            out.append({**base, "params": flipped,
                        "why": f"negative expectancy at a real |t|; {why}"})
    elif cls == "wrong_asset":
        actor = ar.MECHANISM_ACTOR.get(mech, ar.UNKNOWN)
        tried = {s.upper() for s in pool.get("_tried:" + _family_root(dead.family), [])}
        free = [s for s in pool.get(dead.axes.get("asset_class", ""), [])
                if s.upper() not in tried and s.upper() != dead.symbol.upper()]
        if actor == ar.UNKNOWN:
            ref.append({"cell": dead.cell, "why": "transfer refused -- the mechanism names no "
                                                  "payer to go looking for"})
        elif not free:
            ref.append({"cell": dead.cell,
                        "why": "every instrument of this class already carries the family"})
        else:
            out.extend({**base, "symbol": sym,
                        "why": (f"the mechanism's payer ({actor}) exists on {sym} too; the cell "
                                f"died on {dead.symbol}, not the mechanism")}
                       for sym in free[:TRANSFER_INSTRUMENTS])
    elif cls == "wrong_horizon":
        p = _lengthen(dead.params)
        if p is None:
            ref.append({"cell": dead.cell, "why": "no holding parameter to lengthen"})
        else:
            out.append({**base, "params": p, "why": "the same entry held twice as long"})
    elif cls == "unstable":
        p = _widen(dead.params)
        if p is None:
            ref.append({"cell": dead.cell, "why": "no numeric parameter wide enough to widen"})
        else:
            out.append({**base, "params": p,
                        "why": "wider parameters from the family neighbourhood, longer lookback"})
    elif cls == "execution_killed":
        out.append({**base, "why": "the fill killed it, not the signal: entry delayed, on a limit",
                    "params": {**dead.params, "entry_delay_bars": 1, "entry_style": "limit"}})
    return out, ref


def combination_for(dead: Dead, qs: dict[str, Any]) -> dict[str, Any] | None:
    """The mechanism survived in another family: combine THIS ground with THAT expression."""
    q = qs["was_the_mechanism_right_and_the_expression_wrong"]
    fams = q.get("families") or []
    if q.get("answer") is not True or not fams:
        return None
    mech = dead.axes.get("mechanism")
    return {"kind": "combination", "variant": "surviving_expression", "family": fams[0],
            "symbol": dead.symbol, "params": {}, "mechanism": mech, "parent": dead.cell,
            "failure_class": dead.failure_class,
            "why": (f"the mechanism {mech} certified as {fams[0]} elsewhere; this combines "
                    f"{dead.symbol} with the expression that survived")}


# ------------------------------------------------------------------------------ 5. the run
def _acceptable(p: dict[str, Any], known: set[str], names: list[str]) -> str:
    """'' when the proposal may leave, else the reason it may not."""
    sym, fam = str(p.get("symbol") or ""), _family_root(p.get("family"))
    if not sym or not fam:
        return "no symbol or family"
    if fam in ar.NOT_A_FAMILY:
        return f"{fam} is a spec constructor, not a family"
    try:
        if not upol.may_hypothesise(sym):
            return f"{sym} is not in the hypothesis lane (two-lane mandate)"
    except Exception:
        return f"{sym}: the lane policy is unreadable, and absence is not permission"
    blocked = _blocked(fam, names)
    if blocked:
        return f"the graveyard's do_not_repeat entry '{blocked}' covers this family"
    if reg.content_hash(str(p.get("family") or ""), sym, p.get("params")) in known:
        return "the graph already carries this exact cell"
    return ""


def _classify_all(dead: list[Dead], conn: Any, t0: float, budget_s: float
                  ) -> tuple[Counter[str], int, int]:
    by_cls: Counter[str] = Counter()
    marked = deferred = 0
    for d in sorted(dead, key=lambda x: x.at, reverse=True):
        d.failure_class = classify_failure(d.terminal_gate, d.evidence)
        by_cls[d.failure_class] += 1
        if d.failure_class == "UNMEASURED" or conn is None:
            continue
        if time.monotonic() - t0 > budget_s * 0.4:
            deferred += 1
            continue
        marked += int(reg.mark_candidate(d.cell, "judged", failure_class=d.failure_class,
                                         conn=conn))
    return by_cls, marked, deferred


def _reclassify_wrong_asset(dead: list[Dead], sibs: list[Sibling], by_cls: Counter[str]) -> int:
    """A family with a survivor SOMEWHERE and a no-edge death HERE is not barren ground, it is the
    WRONG ASSET. Measured from the cluster, never assumed: this is the only reclassification this
    organ makes, and it is what unlocks the transfer."""
    alive = {_family_root(s.family) for s in sibs if s.fate == "CERTIFIED"}
    n = 0
    for d in dead:
        if d.failure_class == "no_edge" and _family_root(d.family) in alive and not any(
                s.fate == "CERTIFIED" and s.symbol.upper() == d.symbol.upper()
                and _family_root(s.family) == _family_root(d.family) for s in sibs):
            d.failure_class, n = "wrong_asset", n + 1
            by_cls["no_edge"] -= 1
            by_cls["wrong_asset"] += 1
    return n


def build(*, max_candidates: int = MAX_CANDIDATES, budget_s: float = BUDGET_S,
          dry_run: bool = False, max_rows: int = MAX_ROWS) -> dict[str, Any]:
    t0 = time.monotonic()
    rows = read_graph(max_rows)
    dead = dead_cells(rows, max_rows)
    sibs = _siblings(rows)
    dnr = do_not_repeat()
    names = list(dnr.get("names") or [])
    fam_cap = max(1, int(max_candidates * MAX_FAMILY_SHARE))
    conn = None if dry_run else reg.connect()
    try:
        by_cls, marked, deferred = _classify_all(dead, conn, t0, budget_s)
        reclassified = _reclassify_wrong_asset(dead, sibs, by_cls)

        fam_sibs: dict[str, list[Sibling]] = {}
        mech_sibs: dict[str, list[Sibling]] = {}
        tried: dict[str, set[str]] = {}
        for s in sibs:
            fam_sibs.setdefault(_family_root(s.family), []).append(s)
            mech_sibs.setdefault(s.axes.get("mechanism", ar.UNKNOWN), []).append(s)
            tried.setdefault(_family_root(s.family), set()).add(s.symbol.upper())
        fam_deaths: dict[str, list[Dead]] = {}
        clusters: dict[tuple[str, str, str], list[Dead]] = {}
        for d in dead:
            fam_deaths.setdefault(_family_root(d.family), []).append(d)
            if d.failure_class != "UNMEASURED":
                clusters.setdefault((_family_root(d.family),
                                     d.axes.get("mechanism", ar.UNKNOWN),
                                     d.failure_class), []).append(d)
        known = {reg.content_hash(str(r.get("family") or ""), str(r.get("symbol") or ""),
                                  r.get("params") if isinstance(r.get("params"), dict) else {})
                 for r in rows}
        try:
            pool: dict[str, list[str]] = dict(ar.instruments_by_class())
        except Exception:
            pool = {}
        pool.update({"_tried:" + f: sorted(s) for f, s in tried.items()})

        accepted: list[dict[str, Any]] = []
        per_family: Counter[str] = Counter()
        refusals: list[dict[str, str]] = []
        cluster_rows: list[dict[str, Any]] = []
        priors: dict[str, dict[str, Any]] = {}
        counters: list[dict[str, Any]] = []
        seen: set[str] = set()
        n_unmeasured_q = 0
        budget_stop = False

        for (fam, mech, cls), deaths in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
            if time.monotonic() - t0 > budget_s:
                budget_stop = True
                break
            qs = questions(deaths, fam_sibs.get(fam, []), mech_sibs.get(mech, []),
                           fam_deaths.get(fam, []))
            n_unmeasured_q += sum(1 for v in qs.values() if v.get("answer") == "UNMEASURED")
            made = 0
            if cls in BARREN:
                row = priors.setdefault(mech, {"mechanism": mech, "n_failed": 0, "classes": {},
                                               "families": []})
                row["n_failed"] += len(deaths)
                row["classes"][cls] = row["classes"].get(cls, 0) + len(deaths)
                if fam not in row["families"]:
                    row["families"].append(fam)
            else:
                for d in sorted(deaths, key=lambda x: x.cell):
                    if len(accepted) >= max_candidates or per_family[fam] >= fam_cap:
                        break
                    if time.monotonic() - t0 > budget_s:
                        budget_stop = True
                        break
                    props, ref = proposals_for(d, qs, pool)
                    comb = combination_for(d, qs)
                    refusals.extend(ref)
                    for p in ([*props, comb] if comb is not None else props):
                        if len(accepted) >= max_candidates or per_family[fam] >= fam_cap:
                            break
                        why = _acceptable(p, known, names)
                        if why:
                            refusals.append({"cell": str(p.get("parent")), "why": why})
                            continue
                        key = reg.content_hash(str(p.get("family") or ""),
                                               str(p.get("symbol") or ""), p.get("params"))
                        if key in seen:
                            continue
                        seen.add(key)
                        p["trial_family"] = fam
                        p["novelty_vs_graveyard"] = round(
                            1.0 - len(deaths) / (len(deaths) + NOVELTY_PSEUDO), 4)
                        accepted.append(p)
                        per_family[fam] += 1
                        made += 1
            if len(deaths) >= MIN_COUNTER:
                alt = COUNTER_MECHANISM.get(cls, "execution_microstructure")
                counters.append({
                    "family": fam, "mechanism": mech, "failure_class": cls, "n": len(deaths),
                    "alternative_mechanism": alt, "alternative_expression": (
                        qs["was_the_mechanism_right_and_the_expression_wrong"].get("families")
                        or [None])[0],
                    "statement": (f"{len(deaths)} cells of {fam} died of {cls} on mechanism "
                                  f"{mech}: the counter-hypothesis is that the payer is not "
                                  f"{mech} but {alt}")})
            cluster_rows.append({"family": fam, "mechanism": mech, "failure_class": cls,
                                 "n": len(deaths), "questions": qs, "resurrections": made})
        donated = 0 if dry_run or not accepted else _write(accepted, conn, refusals)
    finally:
        if conn is not None:
            conn.close()

    prior_rows = sorted(priors.values(), key=lambda r: -r["n_failed"])
    if not dry_run:
        _lower_priors(prior_rows)
        _remember_counters(counters)
    return {
        "at": _now(), "n_failed_cells": len(dead), "by_failure_class": dict(by_cls.most_common()),
        "clusters": sorted(cluster_rows, key=lambda r: -r["n"])[:60],
        "candidates_generated": len(accepted), "candidates_donated": donated,
        "priors_lowered": prior_rows[:40], "counter_hypotheses": counters[:40],
        "unmeasured": {
            "cells_without_a_recognised_gate": int(by_cls.get("UNMEASURED", 0)),
            "questions_unmeasured": n_unmeasured_q, "verdicts_deferred_by_budget": deferred,
            "reclassified_no_edge_to_wrong_asset": reclassified,
            "graveyard_markdown": dnr.get("status"),
            "why": ("a gate this organ's table does not know leaves its cell UNMEASURED and spawns "
                    f"nothing; a question with fewer than {MIN_SIBLINGS} judged siblings is "
                    "UNMEASURED with its n. Neither is a zero")},
        "sources": {"hypothesis_graph": len(rows), "gate_ledger": str(GATE_LEDGER),
                    "forward_clocks": sum(1 for d in dead if d.origin == "forward_clock"),
                    "graveyard_markdown": dnr.get("n_entries", 0),
                    "do_not_repeat_tags": dnr.get("tags", {})},
        "caps": {"max_candidates": max_candidates, "max_per_family": fam_cap,
                 "max_family_share": MAX_FAMILY_SHARE, "budget_s": budget_s,
                 "budget_stop": budget_stop, "explore_floor": EXPLORE_FLOOR,
                 "elapsed_s": round(time.monotonic() - t0, 2)},
        "verdicts_written": {"marked_judged": marked, "deferred": deferred},
        "refusals": refusals[:40], "rule": RULE}


def _write(accepted: list[dict[str, Any]], conn: Any, refusals: list[dict[str, str]]) -> int:
    """Discovery -> candidate -> donation, in that order, for every accepted resurrection."""
    rows: list[dict[str, Any]] = []
    per_gen: Counter[str] = Counter()
    for p in accepted:
        gen = f"{SOURCE}:{p['kind']}"
        fam, sym, mech = str(p.get("family")), str(p.get("symbol")), str(p.get("mechanism") or "")
        params = p.get("params") if isinstance(p.get("params"), dict) else {}
        did, _ = reg.record_discovery(
            source_id=SOURCE, source_type="graveyard", mechanism=mech, origin="MOAT",
            generator=gen, parent_ids=[p["parent"]], assets=[sym],
            exact_rule=json.dumps({"family": fam, "params": params}, sort_keys=True, default=str),
            economic_rationale=str(p.get("why"))[:300], novelty=p.get("novelty_vs_graveyard"),
            falsifier=(f"the {p['kind']} variant fails the same gate as its parent "
                       f"({p['failure_class']})"), conn=conn)
        for state, cnt in (("EXPANDED", {"possible_cells": 1, "generated_cells": 1}),
                           ("COMPILED", {"compiled_cells": 1}), ("QUEUED", {"queued_cells": 1})):
            reg.set_discovery_state(did, state, conn=conn, **cnt)
        reg.enqueue_candidate(
            family=fam, symbol=sym, params=params, origin="MOAT", mechanism=mech, generator=gen,
            status="queued", source_id=SOURCE, discovery_id=did, transformation=p["kind"],
            parent_ids=[p["parent"]], trial_family=p["trial_family"],
            novelty_vs_graveyard=p["novelty_vs_graveyard"], chart=str(p.get("chart") or ""),
            regime=str(p.get("regime") or ""), causal_rationale=str(p.get("why"))[:300],
            failure_class=p["failure_class"], conn=conn)
        reg.generator_yield_update(gen, generated=1, conn=conn)
        per_gen[gen] += 1
        row = pc.candidate(SOURCE, sym, fam, params, mech,
                           f"resurrection[{p['kind']}/{p['variant']}] {fam} on {sym}",
                           {"failure_class": p["failure_class"], "parent_cell": p["parent"],
                            "kind_of_move": p["kind"], "variant": p["variant"],
                            "why": p.get("why"), "trial_family": p["trial_family"]})
        row.update({"kind": "hypothesis", "symbols": [sym],
                    "novelty_vs_graveyard": p["novelty_vs_graveyard"]})
        rows.append(row)
    path = pc.donate(SOURCE, rows, tests_run=len(accepted))
    donated = int(pc.donation_counts().get("donated") or 0)
    if path is not None and donated == len(rows):
        for gen, n in per_gen.items():
            reg.generator_yield_update(gen, donated=n, conn=conn)
    elif donated != len(rows):
        refusals.append({"cell": "donation",
                         "why": (f"{donated} of {len(rows)} rows reached the intake; "
                                 f"per-generator donation counts UNMEASURED for this run")})
    return donated


def _lower_priors(rows: list[dict[str, Any]]) -> None:
    for r in rows:
        dominant = max(r["classes"].items(), key=lambda kv: kv[1])[0]
        reg.remember(
            "mechanism_prior",
            (f"{r['n_failed']} cell(s) on mechanism {r['mechanism']} died of "
             f"{'/'.join(sorted(r['classes']))}: the ground is barren, not the expression. The "
             f"prior is lowered and NO resurrection is spawned."),
            kind="mechanism_prior", memory_key=f"prior:{r['mechanism']}", result="lowered",
            failure_cause=dominant, failure_stage="gauntlet",
            metrics={"n_failed": r["n_failed"], "class": dominant},
            payload={"classes": r["classes"], "families": r["families"][:20]})


def _remember_counters(counters: list[dict[str, Any]]) -> None:
    for c in counters:
        reg.remember("failure_cluster", c["statement"], kind="counter_hypothesis",
                     memory_key=f"counter:{c['family']}:{c['mechanism']}:{c['failure_class']}",
                     failure_cause=c["failure_class"],
                     metrics={"n": c["n"], "class": c["failure_class"]},
                     payload={"alternative_mechanism": c["alternative_mechanism"],
                              "alternative_expression": c["alternative_expression"]})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="work the graveyard: classify, question, resurrect")
    ap.add_argument("--max-candidates", type=int, default=MAX_CANDIDATES)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--max-rows", type=int, default=MAX_ROWS)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(argv)
    doc = build(max_candidates=a.max_candidates, budget_s=a.budget_s, dry_run=a.dry_run,
                max_rows=a.max_rows)
    print(f"graveyard resurrection: {doc['n_failed_cells']} dead cell(s), "
          f"{len(doc['clusters'])} cluster(s) reported, {doc['candidates_generated']} candidate(s)")
    print("   " + "".join(f"  {k} {v}"
                         for k, v in list(doc["by_failure_class"].items())[:12]))
    for c in doc["clusters"][:6]:
        print(f"  {c['family']:<26} {c['failure_class']:<18} n={c['n']:<6} "
              f"-> {c['resurrections']} resurrection(s)")
    for p in doc["priors_lowered"][:5]:
        print(f"  prior lowered: {p['mechanism']:<26} {p['n_failed']} failure(s)")
    for c in doc["counter_hypotheses"][:5]:
        print(f"  counter-hypothesis: {c['family']} -> test {c['alternative_mechanism']}")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    _atomic_json(OUT, doc)
    print(f"  donated {doc['candidates_donated']}\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
