#!/usr/bin/env python3
"""ALPHABENCH -- nine skills measured per seat, so a research role is ALLOCATED rather than dealt.

THE STRONGEST GENERAL MODEL IS NOT AUTOMATICALLY THE STRONGEST QUANT RESEARCHER, and this desk has
never checked. `scientist_tournament` deals its twelve roles ROUND-ROBIN across whatever vendors
the free tier served that hour; `free_panel.ROLE_TIER` sorts by parameter count and context
window; `llm_seat.flagship_rank` sorts by the version number the provider printed on the box.
All three are proxies for general capability and none is a measurement of the nine things this
desk needs a model to DO -- and the model that writes a beautiful causal story is not the model
that notices a leaked timestamp. The measurement needs no benchmark suite, no eval harness and
not one extra API call; it is already written down, hour after hour, in ledgers kept for other
reasons:

    generation          hypothesis_graph.jsonl      rows the seat minted BORN inside the window
    criticism           tournament_dissents.jsonl   dissents whose cell LATER FAILED the gauntlet
    novelty             NOVELTY_GATE.json           novel / screened, per source
    coding_accuracy     miner_candidates.json       rows that compiled to a cell / rows submitted
    economic_reasoning  gate_verdict_ledger.jsonl   cells that cleared economic_prior / judged
    search_efficiency   hypothesis_graph.jsonl      CERTIFIED / BORN
    leakage_detection   PIT_CENSUS / pit_findings   point-in-time findings raised, per seat
    factor_ranking      intelligence/<seat>/*       the seat's own score vs how far the cell got
    failure_diagnosis   premortem vs terminal_gate  predicted failure stage vs the real one

EVERY SKILL IS A RATE WITH AN n AND A WILSON LOWER BOUND, and below n=5 it is UNMEASURED rather
than zero. One certified hypothesis out of one is not a 100% researcher: a point estimate seats it
first, the lower bound seats it where the evidence does, and n<5 refuses to seat it at all.
UNMEASURED IS A REAL ANSWER (L1.28a) -- an absent ledger means the skill was never observed, never
that the seat is bad at it, and the two must not collapse into one number.

ROLES ARE ALLOCATED BY WEIGHTED LOWER BOUND, the weights stated once in `ROLE_WEIGHTS` rather than
at ten call sites. An unmeasured skill contributes ZERO rather than being normalised away -- a
seat never observed doing the job has not earned it -- and `coverage` publishes how much of the
role's weight the winner answered for. When NO seat is measured on ANY of a role's skills the role
reads UNASSIGNED with the reason named, never a silent round-robin: that fallback is how twelve
roles came to be dealt by vendor alphabet and called independence. NOTHING HERE SIZES, CERTIFIES
OR PROMOTES -- it allocates attention, and every finding still faces the identical ten gates.

    python desks/mt5/research/model_role_benchmark.py [--dry-run] [--days 28]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
GRAPH = BASE / "data" / "hypothesis_graph.jsonl"
GATES = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
NOVELTY = BASE / "reports" / "NOVELTY_GATE.json"
COMPILED = BASE / "data" / "hypotheses" / "miner_candidates.json"
COMPILED_ALT = BASE / "data" / "miner_candidates.json"
CONVERSION = BASE / "reports" / "ROW_CONVERSION.json"
DISSENTS = BASE / "data" / "tournament_dissents.jsonl"
TOURNAMENT = BASE / "reports" / "SCIENTIST_TOURNAMENT.json"
PIT_CENSUS = BASE / "reports" / "PIT_CENSUS.json"
PIT_FINDINGS = BASE / "data" / "pit_findings.jsonl"
SKILL_TRACK = BASE / "data" / "model_skill_track.jsonl"
INTEL = BASE / "data" / "intelligence"
OUT = BASE / "reports" / "MODEL_ROLE_BENCHMARK.json"

#: Below this many observations a rate is UNMEASURED, not small.
MIN_N, WILSON_Z, DEFAULT_DAYS = 5, 1.96, 28
#: `factor_ranking` is the only skill that must open donation files and there are ~9,000 of them.
#: The scan is BOUNDED and the bound is published: a reporting organ must not become an hour of IO
#: on the box that holds the live terminal.
MAX_FILES_PER_SEAT, MAX_INTEL_FILES = 6, 600
#: Mirrored from `libs/research/hypothesis_graph.GATE_ORDER` -- local, so this organ measures the
#: machinery without importing it.
GATE_ORDER: tuple[str, ...] = (
    "symbol_eligibility", "economic_prior", "observations", "in_sample_screen", "deflated_sharpe",
    "pbo", "reality_check_spa", "cpcv", "walk_forward", "stress_costs", "lockbox",
    "expected_value")
#: Mirrored from `libs/research/graveyard_model.GATE_CLASS`: used only to decide whether a seat's
#: predicted failure stage and the gate that refused are one claim in two vocabularies --
#: "deflated_sharpe" and "SELECTION_BIAS" are the same prediction.
_GATE_CLASS: tuple[tuple[str, str], ...] = (
    ("cost", "COST_DEATH"), ("stress", "COST_DEATH"), ("spread", "EXECUTION_FAILURE"),
    ("fill", "EXECUTION_FAILURE"), ("deflated", "SELECTION_BIAS"), ("leak", "LEAKAGE"),
    ("multiplic", "SELECTION_BIAS"), ("placebo", "LEAKAGE"), ("lookahead", "LEAKAGE"),
    ("walk", "STATE_FRAGILE"), ("regime", "STATE_FRAGILE"), ("stability", "STATE_FRAGILE"),
    ("drawdown", "TAIL_FAILURE"), ("tail", "TAIL_FAILURE"), ("redund", "CORRELATION_DUPLICATE"),
    ("corr", "CORRELATION_DUPLICATE"), ("sample", "LOW_SAMPLE"), ("n_trades", "LOW_SAMPLE"),
    ("power", "NO_EDGE"), ("expect", "NO_EDGE"), ("t_stat", "NO_EDGE"), ("sharpe", "NO_EDGE"))

SKILLS: tuple[str, ...] = (
    "generation", "criticism", "novelty", "coding_accuracy", "economic_reasoning",
    "search_efficiency", "leakage_detection", "factor_ranking", "failure_diagnosis")
SKILL_CODE: dict[str, str] = dict(zip(SKILLS, (
    "gen", "crt", "nov", "cod", "eco", "eff", "lek", "rnk", "dia"), strict=True))
#: The seven skills that reduce to a (successes, trials) pair from one ledger, with the basis
#: sentence the artifact prints and the reason an absent ledger gets. The last two skills need a
#: join and are built by their own functions.
COUNTED: dict[str, tuple[str, str]] = {
    "generation": ("hypothesis_graph: {k} BORN row(s) in the window of {n} the desk minted",
                   "hypothesis_graph holds no BORN row for this seat in the window"),
    "criticism": ("tournament dissents: {k} of {n} resolved dissent(s) named a cell that later "
                  "FAILED the gauntlet; dissents nothing has judged are excluded",
                  "this seat has never dissented on a cell the gauntlet later judged"),
    "novelty": ("NOVELTY_GATE: {k} novel of {n} screened",
                "NOVELTY_GATE.json names no screened row for this seat"),
    "coding_accuracy": ("miner_candidates per_source: {k} of {n} submitted row(s) compiled to an "
                        "executable cell; the rest went to the deepening queue",
                        "the compiler's per-source census holds no row for this seat"),
    "economic_reasoning": ("gate_verdict_ledger: {k} of {n} judged cell(s) cleared "
                           "economic_prior; cells refused before that gate ran are excluded",
                           "no cell this seat proposed has been judged at economic_prior"),
    "search_efficiency": ("hypothesis_graph: {k} CERTIFIED of {n} BORN",
                          "this seat has minted no hypothesis the graph recorded"),
    "leakage_detection": ("point-in-time findings: {k} of {n} raised across the desk",
                          "no point-in-time finding is attributed to this seat"),
}
#: WHICH SKILLS WEIGH FOR WHICH ROLE, in one table rather than ten call sites. Weights sum to 1.0
#: so `coverage` reads as "fraction of the role's weight this seat answered for". The table is a
#: CLAIM about the jobs, meant to be argued with in one place: a scout is judged on finding what
#: nobody has and on rows that survive the compiler; an adversarial researcher is judged on being
#: RIGHT when it objects, never on objecting often.
ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    "data_scout": {"novelty": 0.45, "coding_accuracy": 0.30, "generation": 0.25},
    "mechanism_miner": {"economic_reasoning": 0.40, "generation": 0.30, "novelty": 0.30},
    "hypothesis_scientist": {"search_efficiency": 0.45, "economic_reasoning": 0.30,
                             "generation": 0.25},
    "adversarial_researcher": {"criticism": 0.50, "failure_diagnosis": 0.30,
                               "leakage_detection": 0.20},
    "statistical_validator": {"criticism": 0.40, "search_efficiency": 0.35,
                              "failure_diagnosis": 0.25},
    "cross_asset_analyst": {"factor_ranking": 0.45, "search_efficiency": 0.30, "novelty": 0.25},
    "macro_analyst": {"economic_reasoning": 0.50, "generation": 0.25, "novelty": 0.25},
    "execution_researcher": {"coding_accuracy": 0.50, "leakage_detection": 0.30,
                             "failure_diagnosis": 0.20},
    "portfolio_researcher": {"factor_ranking": 0.45, "search_efficiency": 0.35,
                             "economic_reasoning": 0.20},
    "replicator": {"coding_accuracy": 0.50, "criticism": 0.25, "leakage_detection": 0.25},
}
RULE = ("every skill is a rate with an n and a Wilson LOWER bound; below n=5 it is UNMEASURED "
        "rather than zero, and an unmeasured skill contributes 0 to a role score rather than "
        "being normalised away. A role no seat is measured for reads UNASSIGNED with the reason "
        "named -- never a silent round-robin.")
Pair = tuple[float, float]
Cells = dict[tuple[str, str], list[dict[str, Any]]]


# ------------------------------------------------------------------------------ small mechanics

def wilson_lower(k: float, n: float, z: float = WILSON_Z) -> float:
    """Lower end of the Wilson score interval: 0.0 at n<=0, never negative, never above k/n."""
    if n <= 0:
        return 0.0
    p = min(1.0, max(0.0, k / n))
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return max(0.0, (p + z * z / (2.0 * n) - half) / (1.0 + z * z / n))

def _measure(k: float, n: float, basis: str) -> dict[str, Any]:
    if n < MIN_N:
        return {"rate": None, "n": int(n), "lower": None,
                "basis": f"UNMEASURED (n={int(n)} < {MIN_N}): {basis}"}
    return {"rate": round(min(1.0, max(0.0, k / n)), 4), "n": int(n),
            "lower": round(wilson_lower(k, n), 4), "basis": basis}

def _absent(why: str) -> dict[str, Any]:
    return {"rate": None, "n": 0, "lower": None, "basis": f"UNMEASURED: {why}"}

def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None

def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    try:
        handle = path.open("r", encoding="utf-8-sig")
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                row = json.loads(line) if line.strip() else None
            except ValueError:
                row = None
            if isinstance(row, dict):
                yield row

def _blocks(doc: Any, keys: Sequence[str]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Every (seat, record) pair under any of `keys`, however the other organ spelled it."""
    for key in keys if isinstance(doc, dict) else ():
        for raw, val in (doc.get(key).items() if isinstance(doc.get(key), dict) else ()):
            seat = normalise_seat(raw)
            if seat and isinstance(val, dict):
                yield seat, val

def _num(row: dict[str, Any], *names: str) -> float:
    for name in names:
        try:
            return float(row[name])
        except (KeyError, TypeError, ValueError):
            continue
    return 0.0

def normalise_seat(raw: Any) -> str:
    """One identity for a seat however a ledger spelled it.

    `miner:anomalies`, `anomalies` and `fund_playbook:AQR:A` are the intake door's spellings of
    two seats; a model id (`minimax/minimax-m3:free`) is its own seat, keeping its slash but not
    the free-tier suffix, which is a billing fact rather than a different model.
    """
    text = str(raw or "").strip()
    if "/" in text:
        return re.sub(r"[:\-]free$", "", text.lower())
    low = text.lower()
    for prefix in ("miner:", "seat:", "source:", "intelligence:"):
        low = low[len(prefix):] if low.startswith(prefix) else low
    return low.split(":", 1)[0].strip()

def _ts(value: Any) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)

def _cell(sym: Any, fam: Any, fallback: Any = "") -> tuple[str, str]:
    s, f = str(sym or "").strip().lower(), str(fam or "").strip().lower()
    parts = str(fallback or "").split(".")
    if not (s and f) and len(parts) >= 2:
        s, f = s or parts[0].strip().lower(), f or parts[1].strip().lower()
    return s, f

def _failure_class(text: str) -> str:
    low = str(text or "").strip().lower()
    if low.upper().replace(" ", "_") in {c for _n, c in _GATE_CLASS}:
        return low.upper().replace(" ", "_")
    return next((k for needle, k in _GATE_CLASS if needle in low), "UNKNOWN")

def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out, i = [0.0] * len(values), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return out

def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Rank correlation, or None where it is undefined (n<3, or one side constant)."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx <= 0.0 or dy <= 0.0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True)) / (dx * dy)


# ---------------------------------------------------------------------------------- the ledgers

def graph_pass(days: int, now: datetime) -> dict[str, Any]:
    """BORN / CERTIFIED per seat, and the (symbol, family) -> seats map every gate join needs."""
    cutoff = now - timedelta(days=days)
    seat_of: dict[str, str] = {}
    fate_of: dict[str, str] = {}
    born_at: dict[str, datetime | None] = {}
    cells: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in _jsonl(GRAPH):
        hid, seat = str(row.get("id") or ""), normalise_seat(row.get("source"))
        if not hid:
            continue
        if seat:
            seat_of[hid] = seat
            sym, fam = _cell(row.get("symbol"), row.get("family"), row.get("region"))
            if sym and fam:
                cells[(sym, fam)].add(seat)
        fate_of[hid] = str(row.get("fate") or fate_of.get(hid, "")).strip().upper()
        born_at[hid] = born_at.get(hid) or _ts(row.get("at"))
    born: Counter[str] = Counter()
    certified: Counter[str] = Counter()
    recent: Counter[str] = Counter()
    for hid, seat in seat_of.items():
        born[seat] += 1
        certified[seat] += 1 if fate_of.get(hid) == "CERTIFIED" else 0
        stamp = born_at.get(hid)
        recent[seat] += 1 if stamp is not None and stamp >= cutoff else 0
    return {"born": born, "certified": certified, "recent": recent, "cells": cells}

def gate_pass() -> Cells:
    """Every judged cell indexed by (symbol, family): how it was refused, and when."""
    by_cell: Cells = defaultdict(list)
    for row in _jsonl(GATES):
        sym, fam = _cell(row.get("sym"), row.get("family"), row.get("cell"))
        if sym and fam:
            by_cell[(sym, fam)].append({
                "at": _ts(row.get("at")), "passed": bool(row.get("passed")),
                "gate": str(row.get("terminal_gate") or "").strip()})
    return by_cell

def _economic_verdict(gate: str, passed: bool) -> bool | None:
    """True when the cell cleared economic_prior, False when it died there, None when unjudged."""
    low = gate.strip().lower()
    if passed or low == "passed":
        return True
    if low not in GATE_ORDER:
        return None
    here, prior = GATE_ORDER.index(low), GATE_ORDER.index("economic_prior")
    return None if here < prior else here != prior

def economic_counts(by_cell: Cells, cells: dict[tuple[str, str], set[str]]) -> dict[str, Pair]:
    tally: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for key, verdicts in by_cell.items():
        for verdict in verdicts:
            cleared = _economic_verdict(verdict["gate"], verdict["passed"])
            for seat in (cells.get(key) or ()) if cleared is not None else ():
                tally[seat][0] += 1.0 if cleared else 0.0
                tally[seat][1] += 1.0
    return {s: (v[0], v[1]) for s, v in tally.items()}

def novelty_counts() -> dict[str, Pair]:
    """novel / screened per source, read tolerantly -- another organ owns this artifact's shape."""
    doc = _read_json(NOVELTY)
    out: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for seat, val in _blocks(doc, ("per_source", "per_seat", "by_source", "sources", "seats")):
        novel = _num(val, "novel", "n_novel")
        out[seat][0] += novel
        out[seat][1] += _num(val, "screened", "n_screened") or novel + _num(val, "redundant",
                                                                           "n_redundant")
    rows = (doc.get("rows") or doc.get("findings") or doc.get("verdicts") or []
            if isinstance(doc, dict) else doc if isinstance(doc, list) else [])
    for row in rows if isinstance(rows, list) else []:
        seat = normalise_seat(row.get("source") or row.get("seat")) if isinstance(row, dict) else ""
        if seat:
            out[seat][0] += 1.0 if (bool(row.get("novel"))
                                    or str(row.get("verdict") or "").upper() == "NOVEL") else 0.0
            out[seat][1] += 1.0
    return {s: (v[0], v[1]) for s, v in out.items()}

def compiler_counts() -> dict[str, Pair]:
    """Compiled rows / submitted rows per seat, from the compiler's own per-source census.

    `candidates` counts CELLS and one row can mint several, so the numerator is rows-minus-
    deepened: a row that produced no executable cell is one the compiler could not read.
    """
    doc = next((d for d in (_read_json(COMPILED), _read_json(COMPILED_ALT),
                            _read_json(CONVERSION)) if isinstance(d, dict)), None)
    out: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for seat, val in _blocks(doc, ("per_source", "per_seat", "seats")):
        rows = _num(val, "rows")
        if rows > 0:
            out[seat][0] += max(0.0, rows - min(rows, _num(val, "deepening")))
            out[seat][1] += rows
    return {s: (v[0], v[1]) for s, v in out.items()}

def leakage_counts() -> tuple[dict[str, Pair], str]:
    """Point-in-time findings raised per seat, as a share of every finding on the record."""
    raised: dict[str, float] = defaultdict(float)
    doc = _read_json(PIT_CENSUS)
    for seat, val in _blocks(doc, ("per_seat", "by_seat", "per_source", "seats")):
        raised[seat] += _num(val, "findings", "raised", "n")
    rows = list(doc.get("findings") or []) if isinstance(doc, dict) else []
    for row in rows + list(_jsonl(PIT_FINDINGS)):
        seat = normalise_seat(row.get("seat") or row.get("source")) if isinstance(row, dict) else ""
        if seat:
            raised[seat] += 1.0
    total = float(sum(raised.values()))
    if total <= 0:
        return {}, ("no point-in-time finding ledger attributes a finding to a seat -- "
                    "PIT_CENSUS.json publishes a canary verdict and a sidecar census, neither "
                    "naming a proposer, and data/pit_findings is absent: never a clean bill.")
    return {s: (float(v), total) for s, v in raised.items()}, ""

def dissent_counts(by_cell: Cells) -> tuple[dict[str, Pair], str]:
    """Dissents whose cell LATER FAILED / dissents whose cell has been judged at all.

    A dissent nothing has tested is not evidence either way, so it leaves the denominator. The
    dissenter said UNDERMINES; the model it spoke from is joined out of SCIENTIST_TOURNAMENT.json
    whenever the dissent row does not carry it.
    """
    role_model: dict[tuple[str, str], str] = {}
    rows: list[dict[str, Any]] = []
    report = _read_json(TOURNAMENT)
    for res in (report.get("results") or [] if isinstance(report, dict) else []):
        subject = str((res.get("subject") or {}).get("key") or "") if isinstance(res, dict) else ""
        for verdict in (res.get("verdicts") or [] if isinstance(res, dict) else []):
            if isinstance(verdict, dict) and verdict.get("model"):
                role_model[(subject, str(verdict.get("role")))] = str(verdict["model"])
        rows += [{"at": report.get("at"), "subject": subject, **p} for p in
                 (res.get("dissent_pairs") or [] if isinstance(res, dict) else [])
                 if isinstance(p, dict)]
    rows += list(_jsonl(DISSENTS))
    if not rows:
        return {}, ("no tournament dissent is on the record: data/tournament_dissents.jsonl and "
                    "reports/SCIENTIST_TOURNAMENT.json are absent or empty, and a panel that "
                    "never sat says nothing about any model's criticism.")
    seen: set[str] = set()
    tally: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        subject = str(row.get("subject") or row.get("cell") or "")
        role = str(row.get("undermines") or row.get("role") or "")
        identity = json.dumps([subject, role, str(row.get("at") or "")], sort_keys=True)
        if identity in seen:
            continue
        seen.add(identity)
        seat = normalise_seat(row.get("seat") or row.get("model") or row.get("undermines_model")
                              or role_model.get((subject, role)))
        verdict = row.get("confirmed")
        if verdict is None:
            verdict = _failed_after(subject, _ts(row.get("at")), by_cell)
        if not seat or verdict is None:
            continue                        # nothing has judged it yet: not evidence either way
        tally[seat][0] += 1.0 if verdict else 0.0
        tally[seat][1] += 1.0
    return {s: (v[0], v[1]) for s, v in tally.items()}, ""

def _failed_after(subject: str, stamp: datetime | None, by_cell: Cells) -> bool | None:
    """Did the cell this dissent named later fail? None means nothing has judged it."""
    tokens = {t.strip().lower() for t in re.split(r"[.\s|]+", subject) if t.strip()}
    for (sym, fam), verdicts in by_cell.items():
        if sym not in tokens or fam not in tokens:
            continue
        later = [v for v in verdicts if stamp is None or v["at"] is None or v["at"] >= stamp]
        if later:
            return any(not v["passed"] for v in later)
    return None

def intel_scan(days: int, now: datetime) -> dict[str, Any]:
    """BOUNDED read of the donation doors: each seat's own score field, and its model if stamped."""
    cutoff, opened = now - timedelta(days=days), 0
    ranked: dict[str, list[tuple[float, str, str]]] = defaultdict(list)
    models: dict[str, str] = {}
    try:
        seat_dirs = sorted(p for p in INTEL.iterdir() if p.is_dir())
    except OSError:
        return {"ranked": {}, "models": {}, "files_read": 0}
    for seat_dir in seat_dirs:
        seat = normalise_seat(seat_dir.name)
        files = sorted(seat_dir.glob("discoveries_*.json"), reverse=True)[:MAX_FILES_PER_SEAT]
        for path in files:
            stamp = _file_stamp(path)
            if opened >= MAX_INTEL_FILES or (stamp is not None and stamp < cutoff):
                continue
            opened += 1
            doc = _read_json(path)
            rows = doc if isinstance(doc, list) else (
                doc.get("rows") or doc.get("discoveries") or doc.get("items") or []
                if isinstance(doc, dict) else [])
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                stamped = row.get("model") or row.get("llm_model") or row.get("engine")
                if stamped:
                    models.setdefault(seat, str(stamped))
                syms = row.get("symbols")
                sym, fam = _cell(row.get("symbol") or (syms[0] if isinstance(syms, list) and syms
                                                       else ""), row.get("family"))
                keys = ("priority", "score", "rank", "confidence")
                if sym and fam and any(k in row for k in keys):
                    ranked[seat].append((_num(row, *keys), sym, fam))
    return {"ranked": dict(ranked), "models": models, "files_read": opened}

def _file_stamp(path: Path) -> datetime | None:
    hit = re.search(r"(\d{8})[_-](\d{4})", path.name)
    try:
        if hit:
            return datetime.strptime(hit.group(1) + hit.group(2), "%Y%m%d%H%M").replace(tzinfo=UTC)
        return datetime.fromtimestamp(path.stat().st_mtime, UTC)
    except (OSError, ValueError):
        return None

def _depth(verdicts: list[dict[str, Any]]) -> float:
    """How far the gauntlet carried a cell: its index in the gate order, full marks for a pass."""
    best = 0.0
    for verdict in verdicts:
        if verdict["passed"]:
            return float(len(GATE_ORDER))
        gate = verdict["gate"].strip().lower()
        best = max(best, float(GATE_ORDER.index(gate))) if gate in GATE_ORDER else best
    return best

def diagnosis_predictions() -> dict[str, list[tuple[str, str, str]]]:
    """Each seat's predicted failure stage per cell: (prediction, symbol, family)."""
    doc = next((d for d in (_read_json(COMPILED), _read_json(COMPILED_ALT))
                if isinstance(d, dict)), None)
    out: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for row in (doc.get("hypotheses") or [] if isinstance(doc, dict) else []):
        if not isinstance(row, dict):
            continue
        pre = row.get("premortem")
        pre = pre if isinstance(pre, dict) else {}
        pred = str(row.get("expected_failure") or row.get("falsifier")
                   or row.get("predicted_failure") or pre.get("failure_class") or "").strip()
        seat = normalise_seat(row.get("source"))
        sym, fam = _cell(row.get("symbol"), row.get("family"))
        if seat and sym and fam and pred and pred.upper() not in ("UNKNOWN", "NONE"):
            out[seat].append((pred, sym, fam))
    return dict(out)

def seat_models(stamped: dict[str, str]) -> dict[str, str]:
    """What answered for each seat, wherever a ledger stamped it. None is a real answer."""
    models = dict(stamped)
    for row in _jsonl(SKILL_TRACK):
        if row.get("model"):
            models.setdefault(normalise_seat(row["model"]), str(row["model"]))
    report = _read_json(TOURNAMENT)
    for res in (report.get("results") or [] if isinstance(report, dict) else []):
        for verdict in (res.get("verdicts") or [] if isinstance(res, dict) else []):
            if isinstance(verdict, dict) and verdict.get("model"):
                models.setdefault(normalise_seat(verdict["model"]), str(verdict["model"]))
    return models


# ----------------------------------------------------------------------------- the measurement

def build(days: int = DEFAULT_DAYS, now: datetime | None = None) -> dict[str, Any]:
    """Measure every seat on nine skills and allocate the ten roles. Reads only; never calls out."""
    now = now or datetime.now(UTC)
    graph, by_cell, intel = graph_pass(days, now), gate_pass(), intel_scan(days, now)
    leaks, leak_why = leakage_counts()
    dissents, dissent_why = dissent_counts(by_cell)
    minted = float(sum(graph["recent"].values()))
    counts: dict[str, dict[str, Pair]] = {
        "generation": {s: (float(n), minted) for s, n in graph["recent"].items()},
        "criticism": dissents,
        "novelty": novelty_counts(),
        "coding_accuracy": compiler_counts(),
        "economic_reasoning": economic_counts(by_cell, graph["cells"]),
        "search_efficiency": {s: (float(graph["certified"].get(s, 0)), float(n))
                              for s, n in graph["born"].items()},
        "leakage_detection": leaks}
    dark = {"criticism": dissent_why, "leakage_detection": leak_why}
    preds, models = diagnosis_predictions(), seat_models(intel["models"])
    names = set().union(*(set(c) for c in counts.values()), set(intel["ranked"]), set(preds))
    names.discard("")
    seats: dict[str, dict[str, Any]] = {}
    for seat in sorted(names):
        skills: dict[str, dict[str, Any]] = {}
        for name, (basis, why) in COUNTED.items():
            k, n = counts[name].get(seat, (0.0, 0.0))
            skills[name] = (_measure(k, n, basis.format(k=int(k), n=int(n))) if n > 0
                            else _absent(dark.get(name) or why))
        skills["factor_ranking"] = _ranking_skill(intel["ranked"].get(seat), by_cell)
        skills["failure_diagnosis"] = _diagnosis_skill(preds.get(seat), by_cell)
        seats[seat] = {"model": models.get(seat), "skills": skills}
    return {
        "at": now.isoformat(timespec="seconds"), "days": days, "seats": seats,
        "roles": allocate(seats), "unmeasured": _unmeasured(seats), "rule": RULE,
        "role_weights": ROLE_WEIGHTS,
        "coverage": {"n_seats": len(seats), "min_n": MIN_N,
                     "n_seats_measured": sum(1 for r in seats.values() if _any_measured(r)),
                     "intel_files_read": intel["files_read"], "intel_bound": MAX_INTEL_FILES}}

def _any_measured(record: dict[str, Any]) -> bool:
    return any(s.get("lower") is not None for s in record["skills"].values())

def _ranking_skill(pairs: list[tuple[float, str, str]] | None, by_cell: Cells) -> dict[str, Any]:
    """Spearman between the seat's own score and how far the gauntlet carried the cell.

    Published as a CONCORDANCE, (rho+1)/2, so it sits on the same [0,1] scale as every other
    skill and the same Wilson bound applies; the raw rho is named in the basis.
    """
    if not pairs:
        return _absent("this seat's donated rows carry no priority/score field on a cell the "
                       "gauntlet has judged, so its ranking has never been scored")
    xs: list[float] = []
    ys: list[float] = []
    for value, sym, fam in pairs:
        verdicts = by_cell.get((sym, fam))
        if verdicts:
            xs.append(value)
            ys.append(_depth(verdicts))
    rho = spearman(xs, ys)
    if rho is None:
        return _absent(f"{len(xs)} judged pair(s): too few, or the seat scored every row the "
                       "same, so a rank correlation is undefined rather than zero")
    return _measure((rho + 1.0) / 2.0 * len(xs), float(len(xs)),
                    f"spearman(own score, gate depth) = {rho:+.3f} over {len(xs)} judged cell(s), "
                    f"published as the concordance (rho+1)/2")

def _diagnosis_skill(preds: list[tuple[str, str, str]] | None, by_cell: Cells) -> dict[str, Any]:
    """Share of a seat's predicted failure stages that named the gate which actually refused."""
    if not preds:
        return _absent("this seat's rows carry no expected_failure / falsifier / premortem class, "
                       "so it has never predicted where a cell would die")
    hit = n = 0
    for pred, sym, fam in preds:
        gate = next((v["gate"] for v in by_cell.get((sym, fam)) or ()
                     if v["gate"] and v["gate"].lower() not in ("unknown", "passed")), "")
        if not gate:
            continue
        n += 1
        klass = _failure_class(pred)
        hit += 1 if (pred.strip().lower() == gate.strip().lower()
                     or (klass != "UNKNOWN" and klass == _failure_class(gate))) else 0
    if not n:
        return _absent(f"{len(preds)} prediction(s), none on a cell the gauntlet has refused yet")
    return _measure(float(hit), float(n),
                    f"premortem vs terminal_gate: {hit} of {n} predicted stage(s) named the gate "
                    f"that actually refused (the same gate, or the same failure class)")

def allocate(seats: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Rank seats per role by weighted Wilson lower bound; UNASSIGNED when nothing is measured."""
    out: dict[str, dict[str, Any]] = {}
    for role, weights in ROLE_WEIGHTS.items():
        total_w = sum(weights.values()) or 1.0
        cands: list[dict[str, Any]] = []
        for seat, rec in seats.items():
            got = [s for s in weights if (rec["skills"].get(s) or {}).get("lower") is not None]
            cands += [{"seat": seat, "measured": sorted(got),
                       "score": round(sum(weights[s] * float(rec["skills"][s]["lower"])
                                          for s in got), 4),
                       "coverage": round(sum(weights[s] for s in got) / total_w, 3)}] if got else []
        cands.sort(key=lambda c: (-float(c["score"]), str(c["seat"])))
        if not cands:
            out[role] = {"assigned": None, "margin": None, "candidates": [], "why": (
                f"UNASSIGNED: every seat is UNMEASURED on all of {', '.join(sorted(weights))}. "
                f"The desk will not deal this role by round-robin -- wire the ledger that would "
                f"measure those skills, or the role stays open.")}
            continue
        best, runner = cands[0], (float(cands[1]["score"]) if len(cands) > 1 else 0.0)
        margin = round(float(best["score"]) - runner, 4)
        out[role] = {"assigned": best["seat"], "margin": margin, "candidates": cands[:5], "why": (
            f"{best['seat']} scores {best['score']} on "
            f"{', '.join(f'{s}x{weights[s]:g}' for s in sorted(weights))}, covering "
            f"{best['coverage']:.0%} of the role's weight, against "
            + (f"{cands[1]['seat']} at {cands[1]['score']}" if len(cands) > 1
               else "no other measured seat")
            + (". The margin is ZERO: these seats are indistinguishable on this role's evidence "
               "and the pick is arbitrary." if margin <= 0.0 else "."))}
    return out

def _unmeasured(seats: dict[str, dict[str, Any]], cap: int = 250) -> list[str]:
    """Every skill a PARTICIPATING seat was not measured on. A seat measured on nothing is noise."""
    out = [f"{seat}.{name}" for seat, rec in sorted(seats.items()) if _any_measured(rec)
           for name in SKILLS if (rec["skills"].get(name) or {}).get("lower") is None]
    return out if len(out) <= cap else [
        *out[:cap], f"... and {len(out) - cap} more seat/skill pair(s) with no ledger"]


# -------------------------------------------------------------------------------------- the face

def render(doc: dict[str, Any]) -> str:
    cov = doc["coverage"]
    lines = [f"MODEL ROLE BENCHMARK  at={doc['at']}  window={doc['days']}d  "
             f"seats={cov['n_seats']} (measured on something: {cov['n_seats_measured']})", "",
             "seat".ljust(26) + "model".ljust(20)
             + "".join(SKILL_CODE[s].rjust(7) for s in SKILLS)]
    rows = [(s, r) for s, r in doc["seats"].items() if _any_measured(r)]
    rows.sort(key=lambda kv: -sum(v["lower"] or 0.0 for v in kv[1]["skills"].values()))
    for seat, rec in rows[:20]:
        lines.append(seat[:25].ljust(26) + str(rec.get("model") or "-")[:19].ljust(20) + "".join(
            ("--" if (v := (rec["skills"].get(s) or {}).get("lower")) is None
             else f"{v:.2f}").rjust(7) for s in SKILLS))
    lines += [f"... and {len(rows) - 20} more measured seat(s)"] if len(rows) > 20 else []
    lines += ["", "role".ljust(24) + "assigned".ljust(26) + "margin".rjust(8) + "  why"]
    for role, verdict in doc["roles"].items():
        lines.append(role.ljust(24) + str(verdict["assigned"] or "UNASSIGNED")[:25].ljust(26)
                     + ("--" if verdict["margin"] is None else f"{verdict['margin']:.3f}").rjust(8)
                     + "  " + str(verdict["why"])[:86])
    return "\n".join([*lines, "", f"rule: {doc['rule']}"])

def _write(doc: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name(OUT.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, OUT)

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="score every seat on nine skills, allocate ten roles")
    ap.add_argument("--dry-run", action="store_true", help="print the table, write nothing")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS, help="generation window, in days")
    args = ap.parse_args(argv)
    doc = build(max(1, int(args.days)))
    print(render(doc))
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    _write(doc)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
