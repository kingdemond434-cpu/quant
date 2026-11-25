"""THE LLM PROPOSER: free models propose mathematical objects IN THE LAB'S GRAMMAR, and the lab
tests them exactly as it tests its own.

THE ASK (owner, 2026-11-25): "is the math lab using the free LLMs too?" It was not. The lab's
twenty-eight coded traditions and the physics wing stay untouched; this adds ONE free-model job
(`math_proposer`, registered in `data/free_model_jobs.json`) and ONE tradition
(`math:llm_proposer`) that reads what the job proposed.

TWO HALVES, TWO CLOCKS, ONE QUEUE.

  1. THE JOB (`run_job`) runs inside the hourly `conversion_lanes` leg, through its provider-
     agnostic `route_ask` (OpenRouter's free rotation, then every lit cn_ensemble seat). The
     model is shown the grammar the lab can EVALUATE (operators, legal windows, the variables a
     panel carries), what the residual panel IS (a description, the targets, the column names --
     no data value and nothing held out), and the per-tradition yield aggregates the lab already
     publishes. It returns up to K expressions with a one-line mechanism each. Every proposal is
     re-validated HERE (`validate`): unparseable, an unknown operator or variable, any look-ahead
     (a forward shift, a negative lag, a centred window, a full-sample normalisation, a forward-
     looking variable), an `alt:` input the alt catalog does not offer as a PIT spec, or a
     duplicate of an object the lab already has is DROPPED and counted by reason. Accepted ones
     are appended to `data/conversion_lanes/math_proposals.jsonl` (the queue is also the job's
     memory: a re-proposal of a queued form is a duplicate, never a free re-roll).
  2. THE TRADITION (`LLMProposer`) runs inside the hourly `math_lab` leg like every other
     scientist. It takes the oldest unconsumed proposals (at most MAX_PER_PASS), marks them
     consumed BEFORE evaluating them -- a crash loses them rather than re-rolling them -- and
     emits each one on every panel it is routed, through `Scientist.emit`, so each is CHARGED as
     a trial. From there nothing is special: `burden.judge`, the dedup chain, the registry
     (`generator = math:llm_proposer`), the hash-chained trials ledger
     (`burden.record_trials`), donation to `data/intelligence/mathlab/` tagged
     `lane = math_proposer` (so FUNNEL.json `by_lane` scores the job and `conversion_lanes`
     re-weights it), the ten gates, and the same 2% floor / two-sided ROI share via
     `generator_yield`.

WHAT IT NEVER DOES. It invents no data series (a leaf must be a column the panel carries), moves
no gate or trial count, and never shows a model a held-out number.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from . import grammar as G
from .base import Scientist
from .objects import KINDS, MathObject, Panel

DESK = Path(__file__).resolve().parents[2]
TRADITION = "llm_proposer"
LANE = "math_proposer"
QUEUE = DESK / "data" / "conversion_lanes" / "math_proposals.jsonl"
CONSUMED = DESK / "data" / "conversion_lanes" / "math_proposals_consumed.json"
MATH_LAB_REPORT = DESK / "reports" / "MATH_LAB.json"
UNMEASURED = "UNMEASURED"
#: Proposals one model call may return; anything past K is dropped as `over_k`.
K = 8
#: Proposals the tradition takes per math_lab pass (oldest first); the rest wait their turn.
MAX_PER_PASS = 24
#: Set False by a dry-run math_lab pass so it reads the queue without consuming it.
CONSUME = True
#: Existing canonical forms shown to the model so it does not repeat them (never a data value).
SHOW_EXISTING = 30
PROPOSAL_KINDS = ("relationship", "representation", "search_method", "law")

Asker = Callable[[str, str], tuple[str, str, str | None]]

#: Operator names that can only mean "read a later bar" or "use the whole sample".
_LOOKAHEAD_OP = re.compile(
    r"lead|future|fwd|forward|ahead|shift|center|centre|centered|centred|full|whole|global|"
    r"normali[sz]e|standardi[sz]e|demean|rank_all|cumsum_rev|reverse|next|tomorrow|smooth2|"
    r"filtfilt|bidir", re.IGNORECASE)
#: Variable names that are the target, the residual, or anything forward-looking.
_LOOKAHEAD_VAR = re.compile(
    r"^(fwd|future|lead|next|target|label|y|epsilon|eps|resid|residual|outcome)(_|$)|"
    r"(_fwd|_future|_lead|_next|forward)", re.IGNORECASE)
DROP_REASONS = ("unparseable", "over_k", "no_mechanism", "look_ahead", "unknown_operator",
                "unknown_variable", "alt_not_offered", "alt_not_on_panel", "invalid_structure",
                "no_variable", "duplicate_existing", "duplicate_batch")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
    os.replace(tmp, p)


# ------------------------------------------------------------------------------ the parser
class ParseError(ValueError):
    pass


_TOKEN = re.compile(r"\s*(?:(?P<num>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)|"
                    r"(?P<name>[A-Za-z_][A-Za-z0-9_:.]*)|(?P<sym>[(),+\-*/]))")
_INFIX = {"+": "add", "-": "sub", "*": "mul", "/": "div"}


def _tokens(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise ParseError(f"unexpected character at {pos}: {text[pos:pos + 10]!r}")
        kind = m.lastgroup or ""
        out.append((kind, m.group(kind)))
        pos = m.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return out


def parse_expr(text: str) -> G.Expr:
    """The lab's own string form (`grammar.to_str`) back into a tree: `op(a, b, 24)` for every
    operator and `(a + b)` for the four infix ones. `parse_expr(to_str(t))` is `t`."""
    toks = _tokens(text)
    pos = [0]

    def peek() -> tuple[str, str] | None:
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take(value: str | None = None) -> tuple[str, str]:
        t = peek()
        if t is None or (value is not None and t[1] != value):
            raise ParseError(f"expected {value or 'a token'} at token {pos[0]}")
        pos[0] += 1
        return t

    def atom() -> G.Expr:
        t = take()
        if t[0] == "num":
            v = float(t[1])
            return int(v) if v.is_integer() and re.fullmatch(r"[-+]?\d+", t[1]) else v
        if t[0] == "name":
            nxt = peek()
            if nxt is not None and nxt[1] == "(":
                take("(")
                args: list[G.Expr] = []
                if peek() is not None and peek()[1] != ")":   # type: ignore[index]
                    args.append(expr())
                    while peek() is not None and peek()[1] == ",":  # type: ignore[index]
                        take(",")
                        args.append(expr())
                take(")")
                return [t[1], *args]
            return t[1]
        if t[1] == "(":
            inner = expr()
            take(")")
            return inner
        raise ParseError(f"unexpected {t[1]!r}")

    def expr() -> G.Expr:
        left = atom()
        while peek() is not None and peek()[1] in _INFIX:          # type: ignore[index]
            op = _INFIX[take()[1]]
            left = [op, left, atom()]
        return left

    tree = expr()
    if pos[0] != len(toks):
        raise ParseError("trailing tokens")
    return tree


def _as_tree(raw: Any) -> G.Expr:
    if isinstance(raw, str):
        return parse_expr(raw)
    if isinstance(raw, (list, int, float)) and not isinstance(raw, bool):
        return raw
    raise ParseError(f"expression is a {type(raw).__name__}")


def _ops_and_leaves(node: Any) -> tuple[list[Any], list[str], list[Any]]:
    """(operator names, variable leaves, windowed/threshold arguments with their op)."""
    ops: list[Any] = []
    leaves: list[str] = []
    args: list[Any] = []
    if isinstance(node, str):
        return ops, [node], args
    if not isinstance(node, (list, tuple)) or not node:
        return ops, leaves, args
    ops.append(node[0])
    for i, child in enumerate(node[1:]):
        if isinstance(child, (str, list, tuple)):
            o, lv, a = _ops_and_leaves(child)
            ops += o
            leaves += lv
            args += a
        elif i >= 1:
            args.append((node[0], child))
    return ops, leaves, args


# -------------------------------------------------------------------------- the validator
def screen(raw: Any, vocabulary: Iterable[str], offered_alt: Iterable[str] = ()
           ) -> tuple[G.Expr | None, str]:
    """(simplified tree, "") or (None, drop reason). Look-ahead is checked FIRST, so a forward
    operator is named as what it is rather than as merely unknown."""
    try:
        tree = _as_tree(raw)
    except (ParseError, RecursionError):
        return None, "unparseable"
    if isinstance(tree, list) and tree and not isinstance(tree[0], str):
        return None, "unparseable"
    vocab = set(vocabulary)
    offered = set(offered_alt)
    ops, leaves, args = _ops_and_leaves(tree)
    if any(not isinstance(o, str) for o in ops):
        return None, "unparseable"
    if any(_LOOKAHEAD_OP.search(o) for o in ops if o not in G.OPERATORS):
        return None, "look_ahead"
    if any(_LOOKAHEAD_VAR.search(v) for v in leaves):
        return None, "look_ahead"
    if any(op in G.WINDOWED and isinstance(a, (int, float)) and a < 0 for op, a in args):
        return None, "look_ahead"
    if any(o not in G.OPERATORS for o in ops):
        return None, "unknown_operator"
    for v in leaves:
        if v.startswith("alt:"):
            if not any(s == v or s.startswith(v + ":") for s in offered):
                return None, "alt_not_offered"
            if v not in vocab:
                return None, "alt_not_on_panel"
        elif v not in vocab:
            return None, "unknown_variable"
    if not G.valid(tree, sorted(vocab)):
        return None, "invalid_structure"
    simple = G.simplify(tree)
    if not G.variables_in(simple):
        return None, "no_variable"
    return simple, ""


def validate(proposals: list[Any], *, vocabulary: Iterable[str], existing: Iterable[str],
             offered_alt: Iterable[str] = (), k: int = K
             ) -> tuple[list[dict[str, Any]], Counter[str]]:
    """(accepted proposals, drops by reason). `existing` is the set of canonical strings the lab
    already holds; a proposal whose canonical form is in it is a duplicate, not a new trial."""
    vocab = list(vocabulary)
    seen = set(existing)
    batch: set[str] = set()
    kept: list[dict[str, Any]] = []
    dropped: Counter[str] = Counter()
    for i, p in enumerate(proposals):
        if i >= k:
            dropped["over_k"] += 1
            continue
        if not isinstance(p, Mapping):
            dropped["unparseable"] += 1
            continue
        mech = " ".join(str(p.get("mechanism") or "").split())[:300]
        if not mech:
            dropped["no_mechanism"] += 1
            continue
        tree, why = screen(p.get("expr", p.get("expression")), vocab, offered_alt)
        if tree is None:
            dropped[why] += 1
            continue
        canonical = G.algebraic_key(tree)
        if canonical in seen or G.to_str(tree) in seen:
            dropped["duplicate_existing"] += 1
            continue
        if canonical in batch:
            dropped["duplicate_batch"] += 1
            continue
        batch.add(canonical)
        kind = str(p.get("kind") or "relationship")
        side = str(p.get("side") or p.get("side_mode") or "follow")
        kept.append({"expression": tree, "canonical": G.to_str(tree),
                     "fingerprint": G.fingerprint(tree), "mechanism": mech,
                     "kind": kind if kind in PROPOSAL_KINDS else "relationship",
                     "side_mode": side if side in ("follow", "fade") else "follow"})
    return kept, dropped


# ------------------------------------------------------------------------- what is shown
def lab_context(report: Any) -> dict[str, Any]:
    """What the model may see, read from the lab's last published report: the targets, the
    panel source, the column names and per-tradition yield AGGREGATES. No value, no evidence
    block, nothing held out."""
    doc = report if isinstance(report, Mapping) else {}
    panel = doc.get("panel") if isinstance(doc.get("panel"), Mapping) else {}
    columns = [str(c) for c in (panel.get("columns") or []) if isinstance(c, str)]
    yields: dict[str, dict[str, Any]] = {}
    ypc = (doc.get("yield_per_compute_hour") or {}).get("by_tradition") or {}
    for t, row in (doc.get("per_tradition") or {}).items():
        if not isinstance(row, Mapping):
            continue
        y = ypc.get(t) if isinstance(ypc.get(t), Mapping) else {}
        yields[str(t)] = {"proposed": row.get("proposed"), "donated": row.get("donated"),
                          "cells": y.get("cells"), "judged": y.get("judged"),
                          "share": row.get("share")}
    canon = [str(o.get("canonical")) for o in ((doc.get("objects") or {}).get("top") or [])
             if isinstance(o, Mapping) and o.get("canonical")]
    return {"status": "READ" if doc else UNMEASURED,
            "targets": [str(t) for t in (panel.get("targets") or [])][:8],
            "panel_sources": sorted({str(v) for v in (panel.get("panel_sources") or {}).values()}),
            "columns": columns, "yields": yields, "canonicals": canon}


def vocabulary(ctx: Mapping[str, Any]) -> list[str]:
    """Bar terminals every panel carries, plus the columns the lab says its panels carried."""
    return sorted(set(G.BAR_VARIABLES) | set(ctx.get("columns") or []))


SYSTEM = (
    "You are a research mathematician proposing new mathematical objects (state variables, "
    "transforms, interaction laws) for a quantitative research lab. You may ONLY use the "
    "expression grammar you are given: its operators, its legal windows and its variables. "
    "Every operator looks back only; never propose anything that reads a later bar. Do not "
    "repeat an existing form. Reply with JSON only.")


def prompt(ctx: Mapping[str, Any], existing: list[str], k: int = K) -> tuple[str, str]:
    vocab = vocabulary(ctx)
    lines = [
        "GRAMMAR (the only operators that can be evaluated):",
        f"  unary op(x): {', '.join(G.UNARY)}",
        f"  windowed op(x, w), w in {list(G.WINDOWS)}: {', '.join(G.WINDOWED)} "
        "(lag = value w bars ago, diff = x - lag, curv = second difference, rmean/rstd/rmin/rmax "
        "= trailing window, z = trailing z-score)",
        f"  binary op(a, b): {', '.join(G.BINARY)}  (also infix: (a + b), (a - b), (a * b), "
        "(a / b))",
        f"  threshold op(x, c) -> 0/1 indicator, c a number: {', '.join(G.THRESHOLD)}",
        f"  max depth {G.MAX_DEPTH}; numeric constants allowed as leaves.",
        f"VARIABLES (columns every panel carries): {', '.join(vocab)}",
        "THE PANEL: for each target instrument, the target series is the part of the next "
        "bars' return a baseline model did NOT explain. An object is scored by how well its "
        "value at bar t lines up with that unexplained part, after a complexity penalty and a "
        "multiple-testing charge for every form tried. Simple forms with a clear mechanism win.",
        f"  targets this lab works on: {', '.join(ctx.get('targets') or []) or 'unknown'}; "
        f"panel source: {', '.join(ctx.get('panel_sources') or []) or 'unknown'}",
    ]
    ys = ctx.get("yields") or {}
    if ys:
        lines.append("WHAT EACH EXISTING TRADITION PRODUCED (counts only): tradition: proposed / "
                     "donated / cells / judged / compute share")
        for t, y in sorted(ys.items())[:60]:
            lines.append(f"  {t}: {y.get('proposed')} / {y.get('donated')} / {y.get('cells')} / "
                         f"{y.get('judged')} / {y.get('share')}")
    if existing:
        lines.append("EXISTING FORMS (do not repeat these or algebraic rewrites of them):")
        lines += [f"  {c}" for c in existing[:SHOW_EXISTING]]
    lines += [
        f"Propose exactly {k} NEW objects. Each: an expression in the grammar above, written as "
        "op(args) or with the four infix operators, a kind (relationship | representation | "
        "search_method | law), a side (follow | fade) and a ONE-LINE mechanism naming which "
        "market participant or process the object is the footprint of.",
        'Reply as JSON: {"proposals": [{"expr": "z(diff(close, 3), 24)", "kind": '
        '"relationship", "side": "fade", "mechanism": "..."}]}',
    ]
    return SYSTEM, "\n".join(lines)


def parse_reply(text: str) -> list[Any] | None:
    """The proposal list from a model reply, or None when no JSON is in it."""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    for cand in (t, t[t.find("{"):t.rfind("}") + 1] if "{" in t else "",
                 t[t.find("["):t.rfind("]") + 1] if "[" in t else ""):
        if not cand:
            continue
        try:
            doc = json.loads(cand)
        except ValueError:
            continue
        if isinstance(doc, Mapping) and isinstance(doc.get("proposals"), list):
            return list(doc["proposals"])
        if isinstance(doc, list):
            return doc
    return None


# ----------------------------------------------------------------------------- the queue
def read_queue(path: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with (path or QUEUE).open(encoding="utf-8") as fh:
            for line in fh:
                with contextlib.suppress(ValueError):
                    row = json.loads(line)
                    if isinstance(row, dict) and row.get("fingerprint"):
                        out.append(row)
    except OSError:
        return []
    return out


def _append(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")


def registry_canonicals(limit: int = 20_000) -> set[str] | None:
    """Canonical forms every math:* tradition has registered; None when the registry is absent."""
    try:
        from libs.moat import registry as reg
        if not reg.path().exists():
            return None
        conn = reg.connect()
    except Exception:
        return None
    try:
        cur = conn.execute("SELECT exact_rule FROM discoveries WHERE generator LIKE 'math:%' "
                           "AND exact_rule IS NOT NULL LIMIT ?", (int(limit),))
        return {str(r[0]) for r in cur.fetchall() if r[0]}
    except Exception:
        return None
    finally:
        with contextlib.suppress(Exception):
            conn.close()


def offered_alt_specs(cat: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(cat, Mapping):
        return []
    return [str(s) for r in (cat.get("series") or []) if isinstance(r, Mapping)
            for s in (r.get("specs") or [])]


def run_job(*, ask: Asker | None, calls: int, deadline: float, now: datetime | None = None,
            queue: Path | None = None, report: Any = None, cat: Mapping[str, Any] | None = None,
            existing: Iterable[str] | None = None, write: bool = True) -> dict[str, Any]:
    """The `math_proposer` job: `calls` model calls, every reply validated, the accepted ones
    queued for the lab. Never raises."""
    now = now or _now()
    qpath = queue or QUEUE
    out: dict[str, Any] = {"calls": 0, "proposed": 0, "accepted": 0, "models": {},
                           "dropped": dict.fromkeys(DROP_REASONS, 0), "errors": [],
                           "queue": str(qpath)}
    if ask is None or calls <= 0:
        out["status"] = "SKIPPED: no model (--no-llm) or no call share"
        return out
    ctx = lab_context(report if report is not None else _read(MATH_LAB_REPORT))
    out["context"] = {k: ctx[k] if k == "status" else len(ctx[k])
                      for k in ("status", "targets", "columns", "yields", "canonicals")}
    queued = read_queue(qpath)
    reg = set(existing) if existing is not None else registry_canonicals()
    out["registry"] = "READ" if reg is not None else f"{UNMEASURED}: no registry on host"
    known = set(reg or ()) | set(ctx["canonicals"]) | {str(r.get("canonical")) for r in queued}
    known |= {G.algebraic_key(r["expression"]) for r in queued if "expression" in r}
    offered = offered_alt_specs(cat)
    vocab = vocabulary(ctx)
    shown = sorted(set(ctx["canonicals"]) | {str(r.get("canonical")) for r in queued[-20:]})
    accepted: list[dict[str, Any]] = []
    for _ in range(int(calls)):
        if time.monotonic() > deadline:
            out["errors"].append("deadline")
            break
        system, user = prompt(ctx, shown)
        try:
            text, model, err = ask(system, user)
        except Exception as exc:
            text, model, err = "", "", type(exc).__name__
        out["calls"] += 1
        if err or not text:
            out["errors"].append(str(err or "empty")[:160])
            continue
        out["models"][model] = out["models"].get(model, 0) + 1
        proposals = parse_reply(text)
        if proposals is None:
            out["dropped"]["unparseable"] += 1
            continue
        out["proposed"] += len(proposals)
        kept, dropped = validate(proposals, vocabulary=vocab, existing=known,
                                 offered_alt=offered)
        for r, n in dropped.items():
            out["dropped"][r] = out["dropped"].get(r, 0) + n
        for row in kept:
            known.add(G.algebraic_key(row["expression"]))
            known.add(row["canonical"])
            shown.append(row["canonical"])
            accepted.append({**row, "id": f"mp_{row['fingerprint']}", "lane": LANE,
                             "model": model, "proposed_at": now.isoformat(timespec="seconds")})
    if write and accepted:
        _append(qpath, accepted)
    out["accepted"] = len(accepted)
    out["status"] = "OK"
    return out


# --------------------------------------------------------------------------- the tradition
def _consumed(path: Path) -> set[str]:
    doc = _read(path)
    return {str(x) for x in (doc.get("consumed") or [])} if isinstance(doc, Mapping) else set()


def take_pending(queue: Path | None = None, consumed: Path | None = None,
                 limit: int = MAX_PER_PASS, consume: bool | None = None) -> list[dict[str, Any]]:
    """The oldest unconsumed proposals, marked consumed BEFORE they are evaluated."""
    cpath = consumed or CONSUMED
    done = _consumed(cpath)
    pending = [r for r in read_queue(queue) if str(r.get("id")) not in done][:max(0, limit)]
    if pending and (CONSUME if consume is None else consume):
        _atomic(cpath, {"consumed": sorted(done | {str(r["id"]) for r in pending}),
                        "rule": "a proposal is consumed once, before it is evaluated: no "
                                "free re-rolls"})
    return pending


class LLMProposer(Scientist):
    """`math:llm_proposer`: the free models' proposals, tested like any tradition's objects."""

    tradition = TRADITION
    searches_for = ("relationship", "representation", "search_method", "law")

    def __init__(self) -> None:
        super().__init__()
        self._pending: list[dict[str, Any]] | None = None

    def _propose(self, panel: Panel, deadline: float, rng: np.random.Generator
                 ) -> list[MathObject | None]:
        if self._pending is None:
            try:
                self._pending = take_pending()
            except Exception as exc:
                self._pending = []
                self.note("queue", f"unreadable ({type(exc).__name__})")
            if not self._pending:
                self.note("queue", "no unconsumed math_proposer proposals; the conversion_lanes "
                                   "leg's math_proposer job fills it when a free model answers")
        out: list[MathObject | None] = []
        for row in self._pending:
            if time.monotonic() > deadline:
                self.note(f"proposal {row.get('id')}", "not reached before the deadline")
                continue
            # The queue was validated against the grammar when it was written; it is screened
            # again here against THIS panel, so a column the panel lacks is named, not invented.
            tree, why = screen(row.get("expression"), sorted(panel.columns))
            kind = str(row.get("kind") or "relationship")
            if tree is None:
                self.charge(row.get("expression") if isinstance(row.get("expression"), (str, list))
                            else "?")
                self.note(f"proposal {row.get('id')}", f"refused on this panel: {why}")
                continue
            out.append(self.emit(
                panel, kind if kind in KINDS else "relationship", tree,
                f"LLM-proposed ({row.get('model') or 'free model'}): {row.get('mechanism')}",
                side_mode=str(row.get("side_mode") or "follow"),
                diagnostics={"proposal_id": row.get("id"), "model": row.get("model"),
                             "proposed_at": row.get("proposed_at"), "lane": LANE},
                notes=[f"lane={LANE}"]))
        _ = rng
        return out


LLM_REGISTRY: dict[str, type[Scientist]] = {TRADITION: LLMProposer}
LLM_TRADITIONS: tuple[str, ...] = tuple(LLM_REGISTRY)
