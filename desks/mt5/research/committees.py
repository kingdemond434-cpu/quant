#!/usr/bin/env python3
"""TWO ADVERSARIAL COMMITTEES. LLMs argue about explanations; deterministic evidence decides.

    python desks/mt5/research/committees.py --once [--budget-s 600] [--calls 12]
    python desks/mt5/research/committees.py --dry-run

WHERE THIS CAME FROM. The 2026-09-25 box lane "Adversarial committees and PIT discipline",
written from a review of TradingAgents (Apache-2.0), was cut off by a weekly usage limit before
it committed anything. Its brief is carried out here, with one change of vocabulary: what the
brief called the Judge is `judge()` below, and it is ARITHMETIC, not a model.

THE ONE RULE. A committee may never certify, promote, size, rank or veto anything. Its only
product is a FALSIFICATION CONTRACT: the competing explanations for a hypothesis, and the
cheapest set of DETERMINISTIC experiments that separates the claimed mechanism from all of them.
The judge cannot vote on profitability; it has no input that could let it. The gauntlet and its
ten gates keep every piece of authority they had (L1.60), and a KILLED experiment here is a dated
defect report beside the hypothesis, exactly like `falsifier_run.py`'s.

COMMITTEE 1, ADVERSARIAL SCIENTIFIC, sits between hypothesis generation and the gauntlet. Its
input is the bank the gauntlet sweeps (`data/hypotheses/external_survivors.json`), one row per
(symbol, family, params) with the miner's own mechanism note. Its roles speak in turn, each
seeing what the previous ones said, so every explanation is written against the others:

    mechanism_advocate          the strongest honest statement of the claimed cause
    causal_skeptic              why the cause may not be the cause (NO_EDGE, STATE_FRAGILE)
    alternative_explainer       a different, simpler cause that produces the same numbers
    leakage_selection           lookahead, survivorship, the maximum of a search (LEAKAGE,
                                SELECTION_BIAS, LOW_SAMPLE)
    execution_cost              spread, slippage, swap, fills (COST_DEATH, EXECUTION_FAILURE)
    cross_market_translator     where else the mechanism must show if it is real, and what a
                                common factor would look like instead (CORRELATION_DUPLICATE)

and the seventh seat, the independent experimental designer, is `judge()`: a weighted set cover
over the explanation classes the other six raised, priced in the falsifier catalogue's own
declared seconds. The chosen experiments are then RUN, bounded, on the cell the gauntlet itself
would build (`falsifier_run.build_inputs`), so the kill rate is measured, not asserted.

COMMITTEE 2, EXTREME-RETURN FORENSIC, works on records whose returns look too good: SARES'
public-trader cells and the largest measured-but-unnamed effects in the mechanism naming queue.
Its roles (forensic accountant, execution analyst, strategy archaeologist, statistical skeptic,
behavioural classifier, leverage/tail investigator, cross-market translator) propose COMPETING
MECHANISMS M1..Mk, each named as one of SARES' registered mechanism branches. The judge picks the
discriminator (the branch's own falsifier plus the catalogue experiments for its failure class),
and every mechanism with a registered desk family becomes an AlphaCell donation the compiler reads
from `data/intelligence/committees/`. That is ADDITIVE: it mints candidates, it never removes one.

THE DISCIPLINES THE BRIEF ABSORBED, and where each one lives:
  * cheap screening before LLM reasoning -- `screen()`: no mechanism text, unreadable identity or
    an input already reviewed is set aside BEFORE a single call, with the reason counted.
  * claim-type separation -- every contract carries the claim type its evidence actually is
    (signal / sim / broker_replay / shadow / live / public_record), and an explanation that
    cites a stronger claim type than the record holds is discarded by `_valid_explanation`.
  * run-state fingerprints -- every contract carries the sha of its input row, this file, the
    model and the prompts' roles, so a re-run on the same state is recognised, not repeated.
  * delayed settlement and reflection -- `settle()` joins each contract to the hypothesis
    graph's later fate and scores every ROLE by whether the class it raised was the one the
    gauntlet or the falsifier battery later killed it for. That per-role hit rate is the
    committee's reflection; it is written, never self-applied.
  * known-by-date semantics and as-filed data are Tier S's point-in-time work (AC3) and the
    data-hunting lane's; they are not re-spelled here.

IT MUST PAY FOR ITSELF, and the report proves it or scraps it. Every pass meters its LLM calls,
seconds, effective trials charged and experiments run. `value()` compares the compute a correct
pre-gauntlet kill would have saved with what the committee spent. After MIN_SETTLED settled
kills, a committee whose kill precision is below KILL_PRECISION_FLOOR, or whose measured net
compute is negative, writes SCRAPPED to its state file and stops calling the seat. UNMEASURED
never resolves to a scrap (L1.28a): with no gauntlet cost reading, the committee keeps running
and says why it cannot yet be priced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNMEASURED = "UNMEASURED"
BANK = BASE / "data" / "hypotheses" / "external_survivors.json"
NAMING_QUEUE = BASE / "data" / "hypotheses" / "mechanism_naming_queue.json"
SARES_DONATIONS = BASE / "data" / "intelligence" / "sares"
STATE_DIR = BASE / "data" / "committees"
CONTRACTS = STATE_DIR / "contracts.jsonl"
SETTLEMENTS = STATE_DIR / "settlements.jsonl"
STATE = STATE_DIR / "state.json"
PREMORTEMS = STATE_DIR / "premortems.json"
DONATE_DIR = BASE / "data" / "intelligence" / "committees"
#: The lifetime union of looks at return data, shared with committee_ensembles: the experiment
#: ledger charges each distinct line once (libs/research/experiment_ledger.COMMITTEE_UNION).
TRIAL_UNION = STATE_DIR / "trial_union.txt"
REPORT = BASE / "reports" / "COMMITTEES.json"
THROUGHPUT = BASE / "reports" / "JUDGING_THROUGHPUT.json"

SCIENTIFIC = "scientific_committee"
FORENSIC = "forensic_committee"
COMMITTEES: tuple[str, ...] = (SCIENTIFIC, FORENSIC)

#: Bounds for one hourly pass. The call cap is the budget that matters: the seat's free roster
#: has a daily request ceiling that every other organ shares.
DEFAULT_BUDGET_S = 600.0
DEFAULT_CALLS = 12
EXPERIMENT_BUDGET_S = 240.0
MAX_DONATIONS = 60
#: The scrap rule's evidence floor and bar. Below MIN_SETTLED settled kills nothing is scrapped.
MIN_SETTLED = 50
KILL_PRECISION_FLOOR = 0.5

#: Failure classes, the graveyard model's own vocabulary (libs/research/graveyard_model.CLASSES)
#: minus UNKNOWN, plus MECHANISM for the advocate's claim itself.
CLASSES: tuple[str, ...] = ("COST_DEATH", "NO_EDGE", "SELECTION_BIAS", "STATE_FRAGILE",
                            "TAIL_FAILURE", "CORRELATION_DUPLICATE", "LEAKAGE", "LOW_SAMPLE",
                            "EXECUTION_FAILURE")
MECHANISM = "MECHANISM"

#: The deterministic experiments the judge may choose from: declared seconds (the falsifier
#: catalogue's own figure where it has one) and the explanation classes each one SEPARATES from
#: the claimed mechanism. `runner` says who runs it: `falsifiers` = this pass, through
#: libs/validation/falsifiers on the gauntlet's own cell; `gauntlet` = a gate the canonical
#: gauntlet already applies to every cell (named so the contract is complete, never re-run here).
@dataclass(frozen=True)
class Experiment:
    name: str
    cost_s: float
    separates: frozenset[str]
    runner: str
    refutes_if: str


EXPERIMENTS: dict[str, Experiment] = {e.name: e for e in (
    Experiment("cost_surface", 0.5, frozenset({"COST_DEATH", "EXECUTION_FAILURE"}), "falsifiers",
               "net expectancy <= 0 at 1.5x the modelled round trip"),
    Experiment("tail_worst_decile", 0.5, frozenset({"TAIL_FAILURE"}), "falsifiers",
               "the worst-decile trade cluster holds the whole edge"),
    Experiment("half_stability", 1.0, frozenset({"STATE_FRAGILE", "NO_EDGE"}), "falsifiers",
               "either half of the history loses the sign or most of the magnitude"),
    Experiment("usd_residual", 1.0, frozenset({"CORRELATION_DUPLICATE"}), "falsifiers",
               "the P&L does not survive regressing out the USD driver"),
    Experiment("truncation", 2.0, frozenset({"LEAKAGE"}), "falsifiers",
               "signals change when the future is cut off (lookahead sentinel)"),
    Experiment("placebo_battery", 20.0, frozenset({"LEAKAGE", "NO_EDGE", "SELECTION_BIAS"}),
               "falsifiers", "entry-shift / side-flip / random-entry controls match the edge"),
    Experiment("min_sample", 0.01, frozenset({"LOW_SAMPLE"}), "gauntlet",
               "fewer trades than the gauntlet's sample gate admits"),
    Experiment("family_deflation", 0.05, frozenset({"SELECTION_BIAS"}), "gauntlet",
               "the deflated Sharpe over the family's lifetime trial count is not significant"),
)}

#: Role -> (committee, the classes that role may raise, what it is asked).
ROLES: dict[str, tuple[str, tuple[str, ...], str]] = {
    "mechanism_advocate": (SCIENTIFIC, (MECHANISM,),
                           "State the strongest honest version of the claimed cause, and what "
                           "the data must show if it is the cause."),
    "causal_skeptic": (SCIENTIFIC, ("NO_EDGE", "STATE_FRAGILE"),
                       "Explain why the claimed cause may not be the cause of the effect."),
    "alternative_explainer": (SCIENTIFIC, CLASSES,
                              "Give a DIFFERENT, simpler explanation that would produce the "
                              "same observed behaviour without the claimed mechanism."),
    "leakage_selection": (SCIENTIFIC, ("LEAKAGE", "SELECTION_BIAS", "LOW_SAMPLE"),
                          "Find the lookahead, survivorship or search-maximum that could have "
                          "manufactured this."),
    "execution_cost": (SCIENTIFIC, ("COST_DEATH", "EXECUTION_FAILURE"),
                       "Find the spread, slippage, swap or fill assumption that could erase it."),
    "cross_market_translator": (SCIENTIFIC, ("CORRELATION_DUPLICATE", "STATE_FRAGILE"),
                                "Say where else this mechanism must show if real, and what a "
                                "common factor would look like instead."),
    "forensic_accountant": (FORENSIC, ("SELECTION_BIAS", "LOW_SAMPLE", "NO_EDGE"),
                            "Audit how the record was counted: which trades, which period, "
                            "which account, what is missing."),
    "execution_analyst": (FORENSIC, ("COST_DEATH", "EXECUTION_FAILURE"),
                          "Explain the returns through execution: rebates, fills, spreads, "
                          "latency, swap."),
    "strategy_archaeologist": (FORENSIC, CLASSES,
                               "Name the mechanism families that could have produced this "
                               "record."),
    "statistical_skeptic": (FORENSIC, ("SELECTION_BIAS", "LOW_SAMPLE", "NO_EDGE"),
                            "Explain the record as luck or as the best of many tries."),
    "behavioural_classifier": (FORENSIC, ("STATE_FRAGILE", "TAIL_FAILURE"),
                               "Classify the behaviour: grid, martingale, averaging down, "
                               "short volatility, trend, reversion."),
    "tail_risk_investigator": (FORENSIC, ("TAIL_FAILURE",),
                               "Find the hidden leverage or the tail the record has not yet "
                               "paid."),
    "forensic_translator": (FORENSIC, ("CORRELATION_DUPLICATE",),
                            "Say which Fusion instruments would carry the same mechanism."),
}

#: Evidence tiers, weakest first. An explanation may cite evidence only of the record's own
#: tier or weaker: a hypothesis with a backtest is never "confirmed by live results".
CLAIM_TYPES: tuple[str, ...] = ("public_record", "signal", "sim", "broker_replay", "shadow",
                                "live")
_CLAIM_WORDS: dict[str, re.Pattern[str]] = {
    "broker_replay": re.compile(r"\bbroker[- ]?replay|\breplayed on the broker", re.I),
    "shadow": re.compile(r"\bshadow (?:book|results?|trading|clock)|\bforward clock", re.I),
    "live": re.compile(r"\blive (?:results?|trading|p&l|pnl|account|money)|\bin production\b",
                       re.I),
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha(obj: Any, n: int = 16) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:n]


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def _append(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in text.splitlines():
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


_CODE_SHA = ""


def code_sha() -> str:
    global _CODE_SHA
    if not _CODE_SHA:
        try:
            _CODE_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
        except OSError:
            _CODE_SHA = UNMEASURED
    return _CODE_SHA


# ------------------------------------------------------------------------------ the inputs
@dataclass
class Subject:
    """One thing a committee reviews. `claim_type` is the strongest evidence the record holds."""

    committee: str
    subject_id: str
    symbol: str
    family: str
    params: dict[str, Any]
    mechanism: str
    claim_type: str
    source: str
    extra: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        return _sha({"c": self.committee, "s": self.symbol, "f": self.family, "p": self.params,
                     "m": self.mechanism, "k": self.claim_type})


def scientific_subjects(bank: Path | None = None) -> list[Subject]:
    rows = _json(bank or BANK, [])
    if isinstance(rows, dict):
        rows = next((v for v in rows.values() if isinstance(v, list)), [])
    out: list[Subject] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        sym, fam = str(r.get("symbol") or r.get("sym") or ""), str(r.get("family") or "")
        params: dict[str, Any] = r["params"] if isinstance(r.get("params"), dict) else {}
        out.append(Subject(SCIENTIFIC, str(r.get("genome_id") or _sha([sym, fam, params])),
                           sym, fam, dict(params),
                           str(r.get("mechanism_note") or r.get("mechanism") or ""),
                           "signal", str(r.get("source") or ""),
                           {"graveyard_premortem": (r.get("premortem") or {}).get(
                               "failure_class")}))
    return out


def forensic_subjects(sares_dir: Path | None = None,
                      queue: Path | None = None) -> list[Subject]:
    """SARES' public-record cells, newest file first, then the largest unnamed effects."""
    sares_dir, queue = sares_dir or SARES_DONATIONS, queue or NAMING_QUEUE
    out: list[Subject] = []
    files = sorted(sares_dir.glob("discoveries_*.json"), reverse=True) if sares_dir.is_dir() \
        else []
    for f in files[:3]:
        for r in _json(f, {}).get("discoveries") or []:
            if not isinstance(r, dict):
                continue
            syms = [str(s) for s in r.get("symbols") or [] if s]
            params: dict[str, Any] = r["params"] if isinstance(r.get("params"), dict) else {}
            out.append(Subject(FORENSIC, str(r.get("url") or _sha(r)),
                               syms[0] if syms else "", str(r.get("family") or ""),
                               dict(params),
                               str(r.get("testable_claim") or r.get("mechanism") or ""),
                               "public_record", "sares",
                               {"symbols": syms, "evidence_grade": r.get("evidence_grade"),
                                "branch": r.get("mechanism"),
                                "genealogy": r.get("genealogy")}))
    effects = _json(queue, [])
    if isinstance(effects, list):
        ranked = sorted((e for e in effects if isinstance(e, dict)),
                        key=lambda e: -abs(float(e.get("t_stat") or 0.0)))
        for e in ranked:
            desc = (f"measured out-of-sample effect with no named cause: {e.get('feature')} in "
                    f"band {e.get('band')} -> side {e.get('side')} over {e.get('horizon')} bars, "
                    f"n_oos={e.get('n_oos')}")
            out.append(Subject(FORENSIC, "naming:" + _sha(e), str(e.get("symbol") or ""), "",
                               {}, desc, "sim", "mechanism_naming_queue",
                               {"symbols": [str(e.get("symbol") or "")],
                                "feature": e.get("feature"), "n_oos": e.get("n_oos")}))
    return out


def screen(subjects: Sequence[Subject], seen: set[str]) -> tuple[list[Subject], dict[str, int]]:
    """CHEAP SCREENING BEFORE ANY LLM CALL. Only facts, never a judgement of the edge."""
    keep: list[Subject] = []
    why: dict[str, int] = {}
    for s in subjects:
        reason = ""
        if not s.symbol:
            reason = "no_symbol"
        elif len(s.mechanism.strip()) < 20:
            reason = "no_mechanism_text"
        elif s.fingerprint() in seen:
            reason = "already_reviewed"
        if reason:
            why[reason] = why.get(reason, 0) + 1
        else:
            keep.append(s)
    return keep, why


# ------------------------------------------------------------------------------ the roles
def _valid_explanation(allowed: Sequence[str], claim_type: str
                       ) -> Callable[[Any], str | None]:
    tier = CLAIM_TYPES.index(claim_type) if claim_type in CLAIM_TYPES else 0

    def check(p: Any) -> str | None:
        if not isinstance(p, dict):
            return "not an object"
        text = str(p.get("explanation") or "").strip()
        if not (10 <= len(text) <= 400):
            return "explanation missing or longer than 400 chars"
        if str(p.get("class") or "") not in allowed:
            return f"class must be one of {list(allowed)}"
        for kind, pat in _CLAIM_WORDS.items():
            if CLAIM_TYPES.index(kind) > tier and (pat.search(text)
                                                   or pat.search(str(p.get("predicts") or ""))):
                return (f"cites {kind} evidence; this record holds only {claim_type} "
                        "(claim-type separation)")
        return None
    return check


def _grammar(allowed: Sequence[str], branches: Sequence[str]) -> str:
    g = ('{"explanation": "<the cause, <=300 chars>", "class": "<one of: '
         + ", ".join(allowed) + '>", "predicts": "<what the data would show if THIS explanation '
         'is true and the claimed mechanism is not, <=200 chars>"')
    if branches:
        g += ', "mechanism_branch": "<one of: ' + ", ".join(branches) + '>"'
    return g + "}"


def _context(s: Subject, prior: Sequence[Mapping[str, Any]]) -> list[str]:
    ctx = [f"committee: {s.committee}", f"instrument: {s.symbol}",
           f"desk family: {s.family or 'unnamed'}",
           f"evidence held: {s.claim_type} (cite nothing stronger)",
           f"claimed mechanism: {s.mechanism[:600]}"]
    if s.params:
        ctx.append(f"parameters: {json.dumps(s.params, sort_keys=True, default=str)[:300]}")
    for k in ("evidence_grade", "branch", "feature", "n_oos"):
        if s.extra.get(k) not in (None, ""):
            ctx.append(f"{k}: {s.extra[k]}")
    for p in prior[-12:]:
        ctx.append(f"already argued by {p['role']} ({p['class']}): {p['explanation'][:220]}")
    return ctx


def _seat() -> Any:
    try:
        from libs.research import proposer_seat as ps
    except Exception:                                     # pragma: no cover - import guard
        return None
    return ps


def deliberate(s: Subject, *, calls_left: int, branches: Sequence[str] = (),
               ask: Callable[..., Any] | None = None) -> tuple[list[dict[str, Any]],
                                                              dict[str, Any]]:
    """Every role of the subject's committee speaks once, in order, seeing the earlier ones."""
    ps = _seat()
    ask = ask or (ps.ask if ps is not None else None)
    meter: dict[str, Any] = {"calls": 0, "trials_charged": 0.0, "discarded": 0, "reasons": [],
             "roles_unmeasured": 0}
    said: list[dict[str, Any]] = []
    if ask is None:
        meter["why"] = "proposer seat unimportable"
        return said, meter
    for role, (committee, allowed, task) in ROLES.items():
        if committee != s.committee:
            continue
        if meter["calls"] >= calls_left:
            meter["roles_unmeasured"] += 1
            continue
        reply = ask(committee, "candidates",
                    task=f"You are the {role.replace('_', ' ')}. {task}",
                    grammar=_grammar(allowed, branches if s.committee == FORENSIC else ()),
                    context=_context(s, said), n=2,
                    validate=_valid_explanation(allowed, s.claim_type))
        meter["calls"] += 1
        meter["trials_charged"] += float(getattr(reply, "trials_charged", 0.0) or 0.0)
        meter["discarded"] += int(getattr(reply, "discarded", 0) or 0)
        meter["reasons"] += list(getattr(reply, "reasons", []) or [])[:2]
        if getattr(reply, "verdict", UNMEASURED) != "RAN":
            meter["roles_unmeasured"] += 1
            meter["why"] = str(getattr(reply, "why", "") or "seat dark")[:200]
            if meter["calls"] == 1 and not getattr(reply, "items", None):
                break                                     # a dark seat stays dark this pass
            continue
        for item in getattr(reply, "items", []) or []:
            if isinstance(item, dict):
                row = {"role": role, "class": str(item.get("class")),
                       "explanation": str(item.get("explanation"))[:400],
                       "predicts": str(item.get("predicts") or "")[:240]}
                if item.get("mechanism_branch"):
                    row["mechanism_branch"] = str(item["mechanism_branch"])
                said.append(row)
    meter["reasons"] = sorted(set(meter["reasons"]))[:6]
    return said, meter


# ------------------------------------------------------------------------------ the judge
def judge(explanations: Sequence[Mapping[str, Any]],
          experiments: Mapping[str, Experiment] = EXPERIMENTS) -> dict[str, Any]:
    """THE INDEPENDENT EXPERIMENTAL DESIGNER. No model, no vote, no profitability input.

    Greedy weighted set cover: while a competing class is unseparated, take the experiment with
    the lowest declared seconds per newly separated class (ties by name, so the choice is
    reproducible). A class no experiment separates is published as `uncovered` -- the desk's
    missing-experiment backlog -- never silently dropped.
    """
    rivals = sorted({str(e.get("class")) for e in explanations
                     if str(e.get("class")) in CLASSES})
    todo = set(rivals)
    chosen: list[str] = []
    while todo:
        best, best_price = "", float("inf")
        for name in sorted(experiments):
            gain = len(experiments[name].separates & todo)
            if gain:
                price = experiments[name].cost_s / gain
                if price < best_price:
                    best, best_price = name, price
        if not best:
            break
        chosen.append(best)
        todo -= experiments[best].separates
    # The failure class most rivals raised leads the falsifier battery's order (ordering only).
    counts: dict[str, int] = {}
    for e in explanations:
        c = str(e.get("class"))
        if c in CLASSES:
            counts[c] = counts.get(c, 0) + 1
    lead = sorted(counts, key=lambda c: (-counts[c], c))[0] if counts else ""
    return {"rival_classes": rivals, "experiments": chosen,
            "cost_s": round(sum(experiments[n].cost_s for n in chosen), 3),
            "refutes_if": {n: experiments[n].refutes_if for n in chosen},
            "runners": {n: experiments[n].runner for n in chosen},
            "uncovered": sorted(todo), "lead_class": lead}


# ------------------------------------------------------------------------------ the experiments
def run_experiments(s: Subject, verdict: Mapping[str, Any], deadline: float, *,
                    build: Callable[..., Any] | None = None,
                    meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run the judge's falsifier experiments on the cell the gauntlet would build. Bounded."""
    names = [n for n in verdict.get("experiments") or []
             if (verdict.get("runners") or {}).get(n) == "falsifiers"]
    if not names:
        return {"status": "NO_RUNNABLE_EXPERIMENT", "results": {}}
    if not s.family:
        return {"status": UNMEASURED, "why": "the record names no desk family to build",
                "results": {}}
    try:
        import falsifier_run as fr

        from libs.validation import falsifiers as fz
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"falsifier battery unimportable: {exc}",
                "results": {}}
    try:
        build = build or fr._builder()
        meta = meta if meta is not None else fr._meta()
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"gauntlet builder unavailable: {exc}",
                "results": {}}
    cert = {"shadow_spec": {"symbol": s.symbol, "family": s.family, "params": s.params}}
    t0 = time.monotonic()
    inputs, why = fr.build_inputs(cert, dict(meta), build)
    if inputs is None:
        return {"status": UNMEASURED, "why": why, "results": {},
                "seconds": round(time.monotonic() - t0, 3)}
    results: dict[str, Any] = {}
    kills: list[str] = []
    for name in names:
        if time.monotonic() > deadline:
            results[name] = {"verdict": "NOT_REACHED"}
            continue
        if inputs["cost"] is None and name in fr.COST_DEPENDENT:
            results[name] = {"verdict": UNMEASURED, "why": inputs["cost_basis"]}
            continue
        try:
            res = dict(fz.FALSIFIERS[name](inputs["df"], inputs["signals"],
                                           float(inputs["cost"] or 0.0),
                                           family=inputs.get("family"), params={},
                                           usd=inputs.get("usd")))
        except Exception as exc:
            res = {"verdict": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
        results[name] = {k: v for k, v in res.items() if k in ("verdict", "why", "n")}
        if str(res.get("verdict")) == "FAIL":
            kills.append(name)
    ran = [n for n, r in results.items() if r.get("verdict") in ("PASS", "FAIL")]
    return {"status": "KILLED" if kills else ("SURVIVED" if ran else UNMEASURED),
            "kills": kills, "results": results,
            "seconds": round(time.monotonic() - t0, 3)}


def falsifier_looks(s: Subject, outcome: Mapping[str, Any]) -> set[str]:
    """The falsifier looks at this cell's returns that actually ran (PASS or FAIL), one per
    (cell, falsifier). A falsifier that was NOT_REACHED or UNMEASURED looked at nothing."""
    try:
        from libs.research.hypothesis_graph import node_id
        cell = node_id(s.symbol, s.family, s.params)
    except Exception:
        cell = s.subject_id
    return {f"{cell}|falsifier:{n}" for n, r in (outcome.get("results") or {}).items()
            if isinstance(r, Mapping) and r.get("verdict") in ("PASS", "FAIL")}


def charge_looks(looks: set[str], write: bool, union: Path | None = None) -> dict[str, Any]:
    """MULTIPLE-TESTING CHARGE (audit, 2026-10-07). Each falsifier look is a trial, charged at
    its original count: once over the lifetime union, so a re-look on the same cell with the same
    falsifier is never charged again and nothing is inflated."""
    union = union or TRIAL_UNION
    try:
        known = set(union.read_text(encoding="utf-8").split())
    except OSError:
        known = set()
    new = sorted(looks - known)
    if write and new:
        union.parent.mkdir(parents=True, exist_ok=True)
        with union.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(new) + "\n")
    return {"looks_this_pass": len(looks), "new_in_union": len(new)}


# ------------------------------------------------------------------------------ the contract
def contract(s: Subject, said: Sequence[Mapping[str, Any]], verdict: Mapping[str, Any],
             outcome: Mapping[str, Any], meter: Mapping[str, Any], model: str) -> dict[str, Any]:
    return {
        "at": _now(), "committee": s.committee, "subject_id": s.subject_id,
        "symbol": s.symbol, "family": s.family, "params": s.params, "source": s.source,
        "claim_type": s.claim_type,
        "may_not_cite": [c for c in CLAIM_TYPES
                         if CLAIM_TYPES.index(c) > CLAIM_TYPES.index(s.claim_type)],
        "mechanism": s.mechanism[:600],
        "explanations": list(said), "judge": dict(verdict), "outcome": dict(outcome),
        "meter": {k: meter.get(k) for k in ("calls", "trials_charged", "discarded",
                                            "roles_unmeasured")},
        "fingerprint": {"input": s.fingerprint(), "code": code_sha(), "model": model,
                        "roles": [r for r, v in ROLES.items() if v[0] == s.committee]},
        "graph_id": _graph_id(s),
        "authority": "NONE: a contract certifies, promotes, sizes, ranks and vetoes nothing",
    }


def _graph_id(s: Subject) -> str:
    if not (s.symbol and s.family):
        return ""
    try:
        from libs.research.hypothesis_graph import node_id
        return node_id(s.symbol, s.family, s.params)
    except Exception:                                     # pragma: no cover - defensive
        return ""


def _branches() -> dict[str, tuple[str, ...]]:
    """SARES' registered mechanism branches -> the desk families that express each."""
    try:
        from archaeology import sares
        return {b.name: tuple(b.families) for b in sares.BRANCHES}
    except Exception:
        return {}


def alpha_cells(s: Subject, said: Sequence[Mapping[str, Any]],
                verdict: Mapping[str, Any], branches: Mapping[str, Sequence[str]]
                ) -> list[dict[str, Any]]:
    """Committee 2's competing mechanisms, each with a registered family, as compiler donations."""
    rows: list[dict[str, Any]] = []
    symbols = [x for x in (s.extra.get("symbols") or [s.symbol]) if x]
    for e in said:
        b = str(e.get("mechanism_branch") or "")
        for fam in (branches.get(b) or ())[:2]:
            rows.append({
                "source": "committees", "kind": "hypothesis", "generator": f"committees:{FORENSIC}",
                "title": f"forensic committee: {b} explains {s.symbol} ({e.get('role')})",
                "family": fam, "symbols": symbols, "mechanism": b,
                "mechanism_tags": [b, fam], "testable_claim": str(e.get("explanation"))[:300],
                "falsifier": "; ".join(f"{n}: {r}" for n, r in
                                       (verdict.get("refutes_if") or {}).items())
                             or str(e.get("predicts") or ""),
                "competes_with": s.subject_id, "claim_type": s.claim_type,
                "url": f"committees://{FORENSIC}/{s.subject_id}/{b}",
                "copy_trade": False, "credibility_inherited": False, "gauntlet_bypass": False})
    return rows


def donate(rows: Sequence[Mapping[str, Any]], directory: Path | None = None) -> Path | None:
    if not rows:
        return None
    directory = directory or DONATE_DIR
    path = directory / f"discoveries_{_now().replace(':', '').replace('-', '')[:15]}.json"
    _atomic(path, {"source": "committees", "generated_at": _now(),
                   "rule": "a competing mechanism is a candidate, never a verdict",
                   "discoveries": [dict(r) for r in rows[:MAX_DONATIONS]]})
    return path


# ------------------------------------------------------------------------------ settlement
def settle(contracts: Sequence[Mapping[str, Any]], settled_ids: set[str],
           fates: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """DELAYED SETTLEMENT. Join each contract to the hypothesis graph's later fate.

    A contract settles once the graph holds a CERTIFIED or FAILED/BURIED row for its cell. The
    reflection scores each ROLE: a hit when the class it raised is the class the cell later
    failed for. A committee KILL is correct when the gauntlet also failed the cell.
    """
    try:
        from libs.research import graveyard_model as gm
        classify: Callable[..., str] = gm.failure_class
    except Exception:                                     # pragma: no cover - defensive
        def classify(gates: Any, why: str = "") -> str:
            return "UNKNOWN"
    out: list[dict[str, Any]] = []
    for c in contracts:
        gid = str(c.get("graph_id") or "")
        key = f"{gid}:{(c.get('fingerprint') or {}).get('input')}"
        if not gid or key in settled_ids:
            continue
        fate = fates.get(gid) or {}
        f = str(fate.get("fate") or "")
        if f not in ("CERTIFIED", "FAILED", "BURIED"):
            continue
        died_of = ("" if f == "CERTIFIED"
                   else classify(fate.get("gates") or {}, str(fate.get("why") or "")))
        killed = str((c.get("outcome") or {}).get("status")) == "KILLED"
        out.append({
            "at": _now(), "key": key, "committee": c.get("committee"), "graph_id": gid,
            "fate": f, "died_of": died_of, "committee_killed": killed,
            "kill_correct": (f != "CERTIFIED") if killed else None,
            "lead_class": (c.get("judge") or {}).get("lead_class"),
            "lead_hit": bool(died_of) and died_of == (c.get("judge") or {}).get("lead_class"),
            "roles": {e.get("role"): (bool(died_of) and e.get("class") == died_of)
                      for e in c.get("explanations") or [] if e.get("role")},
        })
    return out


def value(settled: Sequence[Mapping[str, Any]], spent_s: float,
          gauntlet_cell_s: float | None) -> dict[str, Any]:
    """Kill precision and net compute. UNMEASURED where the inputs are absent."""
    kills = [r for r in settled if r.get("committee_killed")]
    correct = sum(1 for r in kills if r.get("kill_correct"))
    precision = (correct / len(kills)) if kills else None
    lead = [r for r in settled if r.get("died_of")]
    roles: dict[str, list[int]] = {}
    for r in settled:
        for role, hit in (r.get("roles") or {}).items():
            roles.setdefault(role, [0, 0])
            roles[role][0] += int(bool(hit))
            roles[role][1] += 1
    net = (correct * gauntlet_cell_s - spent_s) if gauntlet_cell_s else None
    return {"settled": len(settled), "kills_settled": len(kills), "kills_correct": correct,
            "kill_precision": (round(precision, 4) if precision is not None else UNMEASURED),
            "lead_class_hit_rate": (round(sum(r["lead_hit"] for r in lead) / len(lead), 4)
                                    if lead else UNMEASURED),
            "role_hit_rate": {k: round(h / n, 4) for k, (h, n) in sorted(roles.items()) if n},
            "committee_seconds": round(spent_s, 1),
            "gauntlet_seconds_per_cell": gauntlet_cell_s or UNMEASURED,
            "net_compute_s": (round(net, 1) if net is not None else UNMEASURED)}


def scrap_verdict(v: Mapping[str, Any]) -> tuple[bool, str]:
    if int(v.get("kills_settled") or 0) < MIN_SETTLED:
        return False, f"{v.get('kills_settled')} settled kills, below the {MIN_SETTLED} floor"
    prec = v.get("kill_precision")
    if isinstance(prec, float) and prec < KILL_PRECISION_FLOOR:
        return True, f"kill precision {prec} below {KILL_PRECISION_FLOOR}"
    net = v.get("net_compute_s")
    if isinstance(net, float) and net < 0:
        return True, f"net compute {net}s: the committee costs more than its kills save"
    return False, "earning its keep" if isinstance(net, float) else \
        "precision holds; net compute UNMEASURED until the gauntlet's cell cost is published"


def _gauntlet_cell_seconds(path: Path | None = None) -> float | None:
    doc = _json(path or THROUGHPUT, {})
    for k in ("seconds_per_cell", "median_seconds_per_cell", "cell_seconds"):
        v = doc.get(k) if isinstance(doc, dict) else None
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


def _fates() -> dict[str, dict[str, Any]]:
    try:
        from libs.research.hypothesis_graph import Graph
        return Graph().current()
    except Exception:
        return {}


# ------------------------------------------------------------------------------ the pass
def run(*, budget_s: float = DEFAULT_BUDGET_S, calls: int = DEFAULT_CALLS, write: bool = True,
        ask: Callable[..., Any] | None = None, build: Callable[..., Any] | None = None,
        meta: Mapping[str, Any] | None = None, fates: Mapping[str, Any] | None = None,
        subjects: Mapping[str, Sequence[Subject]] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(0.0, float(budget_s))
    state = _json(STATE, {}) if write else {}
    prior = _jsonl(CONTRACTS)
    seen = {str((c.get("fingerprint") or {}).get("input")) for c in prior}
    ps = _seat()
    seat_on = bool(ask) or bool(ps is not None and ps.enabled())
    model = UNMEASURED
    if ps is not None and not ask:
        try:
            # `ask` does not surface the served model; the seat's resolved sources are the
            # fingerprint's best available statement of what argued.
            model = ",".join((ps.seat_status() or {}).get("sources") or []) or UNMEASURED
        except Exception:
            model = UNMEASURED
    branches = _branches()
    doc: dict[str, Any] = {"generated_utc": _now(), "seat": "ON" if seat_on else "DARK",
                           "law": ("LLMs argue about explanations; deterministic evidence "
                                   "decides. No committee certifies, promotes, sizes, ranks "
                                   "or vetoes."), "committees": {}}
    new_contracts: list[dict[str, Any]] = []
    looks: set[str] = set()
    donations: list[dict[str, Any]] = []
    calls_left = max(0, int(calls))
    for name in COMMITTEES:
        cstate = state.get(name) or {}
        entry: dict[str, Any] = {"status": "RAN", "reviewed": 0, "calls": 0,
                                 "trials_charged": 0.0, "kills": 0, "survived": 0,
                                 "unmeasured_outcomes": 0, "uncovered_classes": {}}
        if cstate.get("status") == "SCRAPPED":
            entry.update({"status": "SCRAPPED", "why": cstate.get("why")})
            doc["committees"][name] = entry
            continue
        if subjects is not None:
            pool = list(subjects.get(name) or [])
        else:
            pool = scientific_subjects() if name == SCIENTIFIC else forensic_subjects()
        todo, set_aside = screen(pool, seen)
        entry.update({"population": len(pool), "set_aside": set_aside,
                      "eligible": len(todo)})
        if not seat_on:
            entry.update({"status": UNMEASURED,
                          "why": "no proposer seat on this host; nothing was argued"})
            doc["committees"][name] = entry
            continue
        share = calls_left // (len(COMMITTEES) - COMMITTEES.index(name))
        for s in todo:
            if share < 3 or time.monotonic() > deadline:
                break
            said, meter = deliberate(s, calls_left=share, branches=sorted(branches), ask=ask)
            share -= meter["calls"]
            calls_left -= meter["calls"]
            entry["calls"] += meter["calls"]
            entry["trials_charged"] += meter["trials_charged"]
            if not said:
                entry["why"] = meter.get("why") or "the seat said nothing usable"
                break
            verdict = judge(said)
            outcome = (run_experiments(s, verdict, min(deadline, time.monotonic()
                                                       + EXPERIMENT_BUDGET_S),
                                       build=build, meta=meta)
                       if name == SCIENTIFIC else
                       {"status": "DONATED", "why": "competing mechanisms enter the docket as "
                                                     "candidates; the gauntlet judges them"})
            looks |= falsifier_looks(s, outcome)
            c = contract(s, said, verdict, outcome, meter, model)
            new_contracts.append(c)
            seen.add(s.fingerprint())
            entry["reviewed"] += 1
            st = str(outcome.get("status"))
            entry["kills"] += st == "KILLED"
            entry["survived"] += st == "SURVIVED"
            entry["unmeasured_outcomes"] += st == UNMEASURED
            for u in verdict["uncovered"]:
                entry["uncovered_classes"][u] = entry["uncovered_classes"].get(u, 0) + 1
            if name == FORENSIC:
                donations += alpha_cells(s, said, verdict, branches)
        entry["kill_rate"] = (round(entry["kills"] / entry["reviewed"], 4)
                              if entry["reviewed"] else UNMEASURED)
        doc["committees"][name] = entry
    # delayed settlement, reflection, and the scrap rule
    all_contracts = prior + new_contracts
    prior_settled = _jsonl(SETTLEMENTS)
    fresh = settle(all_contracts, {str(r.get("key")) for r in prior_settled},
                   fates if fates is not None else _fates())
    cell_s = _gauntlet_cell_seconds()
    spent = float(state.get("seconds_spent") or 0.0) + (time.monotonic() - t0)
    for name in COMMITTEES:
        rows = [r for r in prior_settled + fresh if r.get("committee") == name]
        v = value(rows, spent / len(COMMITTEES), cell_s)
        scrap, why = scrap_verdict(v)
        doc["committees"][name]["value"] = v
        doc["committees"][name]["scrap_rule"] = why
        if scrap:
            state[name] = {"status": "SCRAPPED", "why": why, "at": _now()}
            doc["committees"][name]["status"] = "SCRAPPED"
    # ordering hints for the falsifier battery: the committee's lead class per certificate cell
    hints = {c["graph_id"]: {"failure_class": c["judge"]["lead_class"], "source": "committees",
                             "at": c["at"]}
             for c in all_contracts if c.get("graph_id") and (c.get("judge") or {}).get(
                 "lead_class")}
    doc["falsifier_trials"] = charge_looks(looks, write)
    doc.update({"new_contracts": len(new_contracts), "settled_this_pass": len(fresh),
                "donations": len(donations), "premortem_hints": len(hints),
                "seconds": round(time.monotonic() - t0, 3)})
    if write:
        _append(CONTRACTS, new_contracts)
        _append(SETTLEMENTS, fresh)
        state["seconds_spent"] = round(spent, 1)
        _atomic(STATE, state)
        _atomic(PREMORTEMS, hints)
        path = donate(donations)
        doc["donation_file"] = str(path) if path else None
        _atomic(REPORT, doc)
    return doc


def premortem_for(graph_id: str, path: Path | None = None) -> dict[str, Any] | None:
    """The committee's lead failure class for one cell, for the falsifier battery's ORDER only."""
    hint = _json(path or PREMORTEMS, {}).get(graph_id) if graph_id else None
    return dict(hint) if isinstance(hint, dict) and hint.get("failure_class") else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--dry-run", action="store_true", help="argue and judge, write nothing")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--calls", type=int, default=DEFAULT_CALLS)
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, calls=args.calls, write=not args.dry_run)
    print(json.dumps({k: doc[k] for k in ("seat", "new_contracts", "settled_this_pass",
                                          "donations", "seconds")}
                     | {n: {k: v for k, v in e.items() if k in ("status", "reviewed", "calls",
                                                                "kills", "kill_rate", "why")}
                        for n, e in doc["committees"].items()}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
