"""Work the deepening queue: recover a falsifiable rule from the source, or reject it.

    python desks/mt5/research/deepening_worker.py [--limit N] [--dry-run]

THE QUEUE HAD NO READER. `miner_candidate_compiler` writes
`data/hypotheses/miner_deepening_queue.json` and declares its consumer in the artifact itself --
"hourly/daily research brains must recover a falsifiable rule or reject" -- and a grep for that
filename across every module on this desk returns exactly one hit: the line in the compiler that
DEFINES the write path. Measured 2026-09-03: 705 tasks, every one at status None, from 35 of the
39 miner sources. Of 1,151 evidence rows compiled that hour, 370 became executable candidates and
705 went here to be read by nobody.

That is the whole yield of the world crawler (50 rows, 0 candidates, 50 deepened), amarkets,
reddit, fxblue, bis_speeches, quant_se, github, forextsd_cdx and trading_latam. The desk pays to
crawl the world hourly and then drops most of what it finds into a write-only file.

WHAT THIS DOES NOT DO, and the distinction is the whole point. It does not invent a rule. The
compiler's first line is "without inventing rules" and this reader is held to it harder, because
an LLM will happily supply a plausible strategy for any title you show it. So:

  * the model is given ONLY the row's own text (title, url, tags) and asked what that text
    STATES -- not what would be a good strategy for it;
  * every extraction must carry `evidence`, a verbatim span from the text it was given. No
    evidence, no candidate. A quote that is not actually in the input is a fabrication and is
    rejected as one, checked here rather than trusted;
  * an extracted symbol must be in the desk's own universe, and an extracted family must be
    registered. The model cannot widen either set by naming something;
  * anything ambiguous is REJECTED with its reason recorded. A rejection is a result: it stops
    the row being re-billed every hour forever.

ENRICH AND RE-COMPILE, NEVER EMIT DIRECTLY. A recovered symbol or recipe is written back onto a
copy of the ORIGINAL row and passed through `compile_row`, the same function every miner row
goes through. This reader therefore adds no new admission path to the candidate store -- it can
only cause the existing door to open, never bypass it, and every guard the compiler already
applies still applies. The gauntlet remains the arbiter of profitability.

WORK IS BOUNDED BY TIME, AND PAID FOR ONCE. `libs.ops.llm_seat` still carries the spend ledger,
but the desk runs on free tiers so a per-run TASK COUNT no longer protects anything worth
protecting; the whole queue is worked in value-of-information order until `RUN_BUDGET_SEC` is
spent. The append-only worked-ledger is what keeps a task from being billed twice, so re-running
the hour is free for everything already decided and a budget that binds simply defers the least
informative rows to the next pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
sys.path.insert(0, str(BASE / "research"))
sys.path.insert(0, str(ROOT))

from miner_candidate_compiler import (  # noqa: E402
    DEEPEN,
    compile_row,
    known_symbols,
)

#: Append-only: one line per task ever decided, so a decision is paid for once. Deliberately not
#: a set inside the output file -- that file is rewritten each run and a crash mid-write would
#: lose the record of work already billed.
WORKED = BASE / "data" / "hypotheses" / "deepening_worked.jsonl"
#: Candidates recovered here, in the compiler's own contract, for the same consumers.
OUT = BASE / "data" / "hypotheses" / "deepened_candidates.json"
LOG = BASE / "logs" / "deepening_worker.log"

#: A run's ceiling. It WAS a budget decision -- the original note read "the queue is 705 deep and
#: grows hourly; working it all in one pass would spend the month's cap in an afternoon on the
#: least-certain rows the desk holds" -- and it is not one any more.
#:
#: RE-DERIVED 2026-09-05, on two measurements taken the same day. The compiler was reading 60 of
#: 5,524 discovery files, so the queue it fed was a fraction of what the miners produce; reading
#: every artifact took the queue from 882 tasks to 6,350. And nothing had ever run this worker --
#: no cron row, no cycle call -- so `deepening_worked.jsonl` did not exist and the lifetime
#: decision count was zero. A 25/hour ceiling against 6,350 queued is 254 hours of uptime, which
#: is not an hourly conversion loop; it is a queue with a trickle attached.
#:
#: THE MONETARY CONSTRAINT IS GONE (principal 2026-09-05: "we r usin all free tiers so its fine
#: remove budget constraint"), so the COUNT ceiling goes with it: 0 means work the whole queue.
#: The original note's fear was spending "the month's cap in an afternoon", and on free tiers there
#: is no month's cap to spend.
#:
#: WHAT STILL BOUNDS A RUN IS TIME, NOT MONEY, and pretending otherwise would break the thing this
#: feeds. `hourly_cycle` calls this in-process and then goes on to mine, heal clocks and write its
#: marker; a run attempting 6,350 seat calls back to back would still be going when the next hour
#: began, so the cycle would overlap itself and every leg after this one would stop happening.
#: Free tiers also rate-limit per minute, so wall clock is the real ceiling whatever the budget is.
#:
#: RUN_BUDGET_SEC is therefore the live constraint, and it is strictly MORE throughput than any
#: count: a fast seat drains far more than 75 in an hour, a slow one is never cut off mid-task,
#: and `voi_order` still spends the time highest-value-of-information first, so a budget that
#: binds costs the LEAST informative rows rather than an arbitrary slice.
#:
#: Worth writing where it will be read: this is not the real ceiling today either. The desk is
#: running three seats that have produced NOTHING in seven days and five launches that died in 24
#: hours. Asking more of a failing seat layer produces more of the same nothing.
DEFAULT_LIMIT = int(os.environ.get("DEEPEN_LIMIT", "0"))          # 0 = the whole queue

#: Wall clock a single run may spend. 40 minutes inside the 60-minute cycle leaves the remaining
#: legs their time and absorbs an overrun on the last task without colliding with the next hour.
RUN_BUDGET_SEC = float(os.environ.get("DEEPEN_RUN_BUDGET_SEC", "2400"))

#: GROWTH GOVERNANCE, carried on every prompt surface (principal 2026-09-04, fenced by
#: scripts/check_growth_governance.py G7): research is anti-timid, capital is evidence-hard.
GOVERNANCE = (
    "Desk governance: "
    "Every risk reduction mechanism must prove that it increases robust forward E[log W]. "
    "Every strong opportunity must be allowed to increase capital above normal when the evidence supports it. "  # noqa: E501
    "Research is anti-timid: weak, anecdotal and unverified public claims are welcome as "
    "hypotheses and are never privileged by their source; nothing you report is capital "
    "advice, and restraint language in any instruction is never a licence to do less."
)

_SYSTEM = (
    "You read one row of trading research evidence and report only what its text STATES. "
    "You never propose a strategy, never fill a gap with something plausible, and never name a "
    "symbol or rule the text does not contain. Reporting that the text is insufficient is a "
    "correct and useful answer; inventing a rule is the one unacceptable one. " + GOVERNANCE
)

_CONTRACT = """Return ONE JSON object, no prose around it:

{
  "symbols":  ["EURUSD"],          // instruments the TEXT names; [] if it names none
  "family":   "session_range_breakout" | null,   // only if the text states an exact mechanism
  "params":   {"lookback": 20} | null,           // only parameters the text actually gives
  "evidence": "verbatim span copied from the text above that supports the above",
  "why_not":  "why nothing could be extracted, if symbols is [] and family is null"
}

Rules you must follow:
- `evidence` MUST be copied character-for-character from the text you were given. If you cannot
  quote it, you have nothing to report: return empty symbols, null family, and say why in
  `why_not`.
- A generic mention of "forex", "trading" or "MT5" is NOT a symbol. Only concrete instruments.
- Do not infer a family from a tag. "scalping" is a style, not an exact mechanism.
- Prefer returning nothing over returning something you had to reason your way to."""


#: THE ONE KIND THAT GENERATES RATHER THAN EXTRACTS. An alpha_expression task asks the seat for
#: a formulaic alpha the grammar search has not found; there is no source text to quote, so the
#: evidence guard is replaced by a STRUCTURAL one: the expression must parse and type-check in
#: `libs.research.alpha_grammar`, the recipe must be executable by the `formula` family, and a
#: mechanism sentence is mandatory. What the seat returns is a CANDIDATE like any other -- it
#: goes through compile_row, the multiplicity charge and the gauntlet; the LLM has no more
#: authority than the genetic search it complements.
_CONTRACT_EXPR = """Return ONE JSON object, no prose around it:

{
  "symbols":   ["XAUUSD"],                  // one or more instruments named in the task
  "family":    "formula",
  "params":    {"expr": ["zscore", ["delta", "close", 24], 240], "side_mode": "fade",
                "entry_z": 1.5, "hold_bars": 8},
  "mechanism": "who pays and why they cannot stop, in one or two sentences",
  "why_not":   "why no expression is warranted, if you return no params"
}

Rules you must follow:
- `expr` is a JSON tree over the grammar in the system prompt: a terminal string, or
  [op, child] for unary ops, [op, child, window] for windowed ops, [op, left, right] for
  binary ops, [op, left, right, window] for corr/residual/cov. Windows are one of 2, 3, 5, 8,
  12, 24, 48, 120, 240. Only terminals the task lists as available may be used.
- Do NOT return an expression the task lists as already tried.
- `mechanism` must state an economic cause; an expression without one is rejected."""


def dlog(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def task_id(task: dict) -> str:
    """Stable across runs and across queue rebuilds: the row's own identity, not its position."""
    key = f"{task.get('source')}|{task.get('url')}|{task.get('title')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def worked_ids() -> set[str]:
    if not WORKED.exists():
        return set()
    out: set[str] = set()
    for line in WORKED.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.add(str(json.loads(line)["id"]))
        except (ValueError, KeyError):
            continue
    return out


def record(entry: dict) -> None:
    WORKED.parent.mkdir(parents=True, exist_ok=True)
    with WORKED.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")


def task_text(task: dict) -> str:
    """Everything the model is allowed to see. No fetching: the row is the evidence."""
    tags = ", ".join(str(t) for t in (task.get("mechanism_tags") or []))
    lines = [
        f"TITLE: {task.get('title') or ''}",
        f"URL: {task.get('url') or ''}",
        f"TAGS: {tags}",
        f"SOURCE: {task.get('source') or ''}",
        f"SYMBOLS ALREADY RESOLVED: {task.get('symbols') or []}",
    ]
    # THE ROW'S OWN TEXT IS THE EVIDENCE. Feedback engines (coverage gaps, revival, the repo and
    # deep-forest miners, anomalies) write what they found into `description`; a claim miner
    # writes the verbatim sentence. Before 2026-09-04 the seat saw only title/url/tags, so a
    # story_mechanism task carried its mechanism in a field the reader never received.
    for key, label in (("description", "DESCRIPTION"), ("claim", "CLAIM"),
                       ("evidence_grade", "EVIDENCE GRADE"),
                       ("claimed_performance", "STORY'S NUMBERS"),
                       ("transfer_only", "NO-ANALOGUE INSTRUMENTS"), ("params", "PARAMS"),
                       ("family", "FAMILY HINT")):
        v = task.get(key)
        if v not in (None, "", [], {}):
            lines.append(f"{label}: {str(v)[:1200]}")
    # WHAT THE DESK ALREADY KNOWS about this region -- failures first, so a corpse is not
    # re-proposed. Optional: an absent memory module changes nothing.
    try:
        from libs.research.memory import prompt_context
        ctx = prompt_context(task)
        if ctx:
            lines.append("DESK MEMORY:\n" + ctx)
    except Exception:
        pass
    return "\n".join(lines)


def _parse(text: str) -> dict | None:
    """The object, or None. A model that wraps JSON in prose is common; a broken one is not fatal."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        v = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def validate(found: dict, source_text: str, universe: set[str]) -> tuple[dict, str]:
    """The extraction, cleaned -- or ({}, reason) when it may not be trusted.

    EVERY REJECTION HERE IS A FABRICATION CAUGHT. The quote check is the one that matters: a
    model that cannot ground its answer in the text will still return a confident answer, and
    without this it would enter the candidate store wearing the miner's provenance.
    """
    evidence = str(found.get("evidence") or "").strip()
    symbols = [str(s).upper().strip() for s in (found.get("symbols") or []) if str(s).strip()]
    family = found.get("family")
    family = str(family).strip() if isinstance(family, str) and family.strip() else None
    params = found.get("params") if isinstance(found.get("params"), dict) else None

    if not symbols and not family:
        return {}, f"nothing extractable: {found.get('why_not') or 'no reason given'}"
    if not evidence:
        return {}, "extraction carried no evidence span"
    # Normalised containment: models re-wrap whitespace even when quoting faithfully.
    hay = " ".join(source_text.split()).lower()
    needle = " ".join(evidence.split()).lower()
    if needle not in hay:
        return {}, f"evidence span is not in the source text (fabricated quote): {evidence[:80]!r}"

    unknown = [s for s in symbols if s not in universe]
    if unknown:
        return {}, f"symbols outside the desk universe: {unknown}"
    if params is not None and any(isinstance(v, (dict, list)) for v in params.values()):
        return {}, "params must be flat scalars"
    return {"symbols": symbols, "family": family, "params": params, "evidence": evidence}, ""


def validate_expression(found: dict, universe: set[str]) -> tuple[dict, str]:
    """A generated alpha, cleaned -- or ({}, reason). Structure replaces the quote check."""
    from libs.research import alpha_grammar as ag
    symbols = [str(s).upper().strip() for s in (found.get("symbols") or []) if str(s).strip()]
    params = found.get("params") if isinstance(found.get("params"), dict) else None
    mechanism = str(found.get("mechanism") or "").strip()
    if not params or not symbols:
        return {}, f"no expression: {found.get('why_not') or 'no reason given'}"
    unknown = [s for s in symbols if s not in universe]
    if unknown:
        return {}, f"symbols outside the desk universe: {unknown}"
    expr = params.get("expr")
    if not ag.is_valid(expr) or not ag.well_typed(expr):
        return {}, f"expression is not a valid, well-typed grammar tree: {str(expr)[:80]!r}"
    side = str(params.get("side_mode") or "follow")
    try:
        entry_z = float(params.get("entry_z", 1.5))
        hold = int(params.get("hold_bars", 8))
    except (TypeError, ValueError):
        return {}, "entry_z / hold_bars are not numbers"
    if side not in ("follow", "fade") or not (0.5 <= entry_z <= 4.0) or not (1 <= hold <= 240):
        return {}, f"recipe outside the formula family's executable range: {params}"
    if len(mechanism) < 20:
        return {}, "no economic mechanism stated"
    clean = {"expr": expr, "side_mode": side, "entry_z": entry_z, "hold_bars": hold,
             "norm": int(params.get("norm", 240))}
    return {"symbols": symbols, "family": "formula", "params": clean,
            "evidence": f"generated: {mechanism} [{ag.to_str(expr)}]"}, ""


def extract(task: dict, *, chat=None) -> tuple[dict, str]:
    """Ask the seat what the row's own text states. ({}, reason) on any doubt."""
    if chat is None:
        from libs.ops import llm_seat
        chat = llm_seat.chat
    text = task_text(task)
    kind = str(task.get("kind") or "")
    system = _SYSTEM_BY_KIND.get(kind, _SYSTEM)
    contract = _CONTRACT_EXPR if kind == "alpha_expression" else _CONTRACT
    reply, err = chat(f"{text}\n\n{contract}", system=system, max_tokens=700, temperature=0.0)
    if err:
        return {}, f"seat error: {err}"
    found = _parse(reply)
    if found is None:
        return {}, "reply was not a JSON object"
    if kind == "alpha_expression":
        return validate_expression(found, known_symbols())
    return validate(found, text, known_symbols())


def work_task(task: dict, universe: set[str], *, chat=None) -> tuple[list[dict], str]:
    """Candidates recovered from this task, and the disposition recorded for it.

    The recovered fields are written onto a COPY of the original row and re-compiled by
    `compile_row`. Nothing here writes a candidate itself, so no guard in the compiler can be
    skipped by coming through this door.
    """
    # A MUTATION TASK ALREADY CARRIES ITS RECIPE (survivor_distiller: parent certificate, one
    # grid step, the operator named). Asking a seat to "extract" it would be paying to be told
    # what the row says; it goes straight to the compiler, which still owns the admission.
    if (str(task.get("kind") or "") == "mutation" and isinstance(task.get("family"), str)
            and isinstance(task.get("params"), dict) and task.get("symbols")):
        enriched = dict(task)
        enriched.setdefault("mechanism", f"mutation of {task.get('parent')} by "
                                         f"{task.get('operator')}")
        candidates, disposition = compile_row(str(task.get("source") or "unknown"),
                                              enriched, universe)
        if not candidates:
            return [], f"STILL_{disposition}"
        for c in candidates:
            c["deepened"] = True
            c["evidence"] = f"exact recipe on the task: {task.get('operator')}"
        return candidates, f"RECOVERED_{disposition}"
    found, why = extract(task, chat=chat)
    if not found:
        return [], f"REJECTED: {why}"

    enriched = dict(task)
    if found["symbols"]:
        enriched["symbols"] = found["symbols"]
    if found["family"]:
        enriched["family"] = found["family"]
        enriched["params"] = found["params"] or {}
    enriched["mechanism"] = f"deepened from source text: {found['evidence'][:160]}"

    candidates, disposition = compile_row(str(task.get("source") or "unknown"),
                                          enriched, universe)
    if not candidates:
        # The compiler still refused it. That is the compiler's call, not this reader's.
        return [], f"STILL_{disposition}"
    for c in candidates:
        c["deepened"] = True
        c["evidence"] = found["evidence"][:400]
    return candidates, f"RECOVERED_{disposition}"


def voi_order(tasks: list[dict]) -> list[dict]:
    """Work the tasks with the highest expected value of information first.

    THE QUEUE WAS FIFO. 882 tasks and a 25-per-run limit meant a coverage gap the allocator
    asked about yesterday sat behind a month of low-grade crawler rows. Value of information for
    a task is what a certificate from it would be worth times how likely one is:

        P(certify | family)   `funnel_census`'s Beta posterior for the task's family hint, or
                              the pooled rate when it names none
        worth                 a coverage-gap task enters an uncovered state (weight 3);
                              a fund-playbook A-grade claim carries a strong prior (2);
                              a plain crawler row is 1
        novelty               a task whose (symbol, family) region the hypothesis graph has
                              already buried is discounted by 1 / (1 + n_failed)

    Deterministic, so two runs on the same queue work the same tasks in the same order.
    """
    try:
        from libs.research import funnel_census as fc
        recs = fc.build(ROOT)
        p_fam = {}
        for name, r in recs.items():
            a, b = r.posterior("certified")
            p_fam[name] = a / (a + b) if (a + b) > 0 else 0.05
        pooled = float(sum(p_fam.values()) / max(1, len(p_fam))) if p_fam else 0.05
    except Exception:
        p_fam, pooled = {}, 0.05
    try:
        from libs.research.hypothesis_graph import Graph
        graph = Graph()
        graph.buried()
    except Exception:
        graph = None
    # THE META-MODEL OF RESEARCH SUCCESS: P(survivor | family, symbol, source, ...) from the
    # graveyard, blended with the pooled family rate wherever the task names enough to ask.
    # The bandit's 20% exploration floor still applies through `direction`, so the queue
    # cannot become trapped by its own history.
    try:
        from libs.research.graveyard_model import GraveyardModel
        gm = GraveyardModel().fit(graph.rows()) if graph is not None else None
        if gm is not None and gm.n < 50:
            gm = None
    except Exception:
        gm = None

    def _score(t: dict) -> float:
        fam = str(t.get("family") or "")
        p = p_fam.get(fam, pooled)
        if gm is not None and fam and t.get("symbols"):
            try:
                pm = gm.premortem({"family": fam, "symbol": str(t["symbols"][0]),
                                   "source": str(t.get("source") or ""),
                                   "params": dict(t.get("params") or {})})
                if pm.get("p_survivor") is not None:
                    p = 0.5 * p + 0.5 * float(pm["p_survivor"])
            except Exception:
                pass
        src = str(t.get("source") or "")
        # A gap the desk's OWN ledgers found (an uncovered state, a dead session phase) is worth
        # entering: 3. An exit hypothesis from measured excursions, or an A-grade fund claim,
        # carries a strong prior: 2. A plain crawler row is 1.
        # The exit and action ledgers (2026-09-04) are measured on the desk's own trades and
        # carry the same prior as excursions. A deep-forest or repo claim that names an
        # instrument the desk quotes and comes from a competition record, an interview, code or
        # a transcript sits between a crawler row and a measured gap: 1.5.
        strong_story = (src in ("deep_forest", "repo_miner") and bool(t.get("symbols"))
                        and str(t.get("evidence_grade")) in ("COMPETITION_RECORD", "INTERVIEW",
                                                             "CODE", "VIDEO_TRANSCRIPT"))
        worth = 3.0 if src in ("regime_coverage", "opportunity_curve") else (
            2.0 if src in ("excursions", "exit_accounts", "action_counterfactuals")
            or (src == "fund_playbook" and str(t.get("evidence_grade")) == "A")
            else (1.5 if strong_story else 1.0))
        novelty = 1.0
        if graph is not None and fam and t.get("symbols"):
            try:
                pf = graph.prior_failures(str(t["symbols"][0]), fam, dict(t.get("params") or {}))
                novelty = 1.0 / (1.0 + float(pf.get("n_failed", 0)))
            except Exception:
                pass
        # THE BANDIT'S SHARE for this task's research direction (uniform budget = 1.0), so the
        # queue works the directions that have been earning certificates per unit of cost.
        try:
            from libs.research.bandit import arm_weight
            direction = arm_weight(src, str(t.get("kind") or "") or None)
        except Exception:
            direction = 1.0
        return p * worth * novelty * direction

    return sorted(tasks, key=lambda t: (-_score(t), task_id(t)))


#: Specialist system prompts by task kind. One seat, three roles: the prospector reads a row for
#: DATA it names, the mechanism reader for an exact RULE, the red team for why a claim would
#: fail. Each is the same contract with a different question, which is what makes them
#: comparable and keeps the extraction guard (verbatim evidence) applying to all three.
_SYSTEM_BY_KIND = {
    "coverage_gap": (
        "You are given a market STATE in which no known mechanism pays, and the families already "
        "tried there. Propose ONE family from the desk's registry and exact parameters whose "
        "economic cause is specific to that state, or say why none is plausible. Never propose "
        "a re-parameterisation of a family listed as already losing there."),
    "fund_claim": (
        "You read a public claim about how a named fund trades. Report only the mechanism the "
        "text STATES, as a family and parameters the desk can test, and quote the span. A claim "
        "with no testable mechanism is reported as such; you never fill it in."),
    "data_source": (
        "You read a row for DATA SOURCES it names: series, feeds, files, APIs. Report each with "
        "the verbatim span that names it and what quantity it carries. Never infer a source."),
    "dead_phase": (
        "You are given a SESSION PHASE (a range of broker hours) in which no sleeve on the desk "
        "has positive conditional expectancy, and what was measured there. Propose ONE family "
        "from the desk's registry and exact parameters whose economic cause is specific to that "
        "phase -- who is forced to trade then, what is rebalanced, which venue opens or closes -- "
        "or say why none is plausible. Never a re-parameterisation of what already loses there."),
    "exit_hypothesis": (
        "You are given a certified sleeve whose trades give back a measured fraction of their "
        "favourable excursion before exit. Propose ONE exit rule (trail, partial, time stop) as "
        "exact parameters for a NEW cell that keeps the certified entry unchanged, or say why "
        "the excursion pattern does not support one. Never change the entry."),
    "sizing_hypothesis": (
        "You are given a certified sleeve whose measured counterfactuals say a different size "
        "would have raised E[log W]. State the exact sizing rule the evidence supports as a "
        "capital modifier (kind, multiplier, condition) and quote the numbers; never propose a "
        "size change the row's own measurement does not show."),
    "repo_mechanism": (
        "You read a verbatim MECHANISM CLAIM from a public repository's README (licence and "
        "provenance given). Report only the mechanism the text STATES, as a registered family "
        "and exact parameters the desk can test on an MT5 instrument, quoting the span. Concept "
        "only: never copy code, never invent a rule the text does not state, and reject a claim "
        "that names no testable rule."),
    "story_mechanism": (
        "You read a verbatim claim from a practitioner story -- a trader interview, a competition "
        "record, a forum or community post, a video transcript -- in Chinese or English, with the "
        "instrument already mapped to its MT5 analogue where one exists. A dubious story can "
        "still name a TESTABLE mechanism: state it as a registered family and exact parameters "
        "on the analogue instrument (or, for a no-analogue instrument, on the closest MT5 asset "
        "class named in the row), quoting the span. The story's own performance numbers are NOT "
        "evidence and must not raise your confidence. Reject when the text states no rule."),
    "revival": (
        "You are given a BURIED region (symbol, family, parameters), the failure class it died "
        "of, and what has changed since. Say whether a re-test as a NEW pre-registered cell is "
        "warranted by the stated change alone, with the exact recipe unchanged; never "
        "re-parameterise, never argue from the original result."),
    "anomaly": (
        "You are given a data-first ANOMALY: a conditional regularity with its condition, "
        "horizon, sample and t-statistic, and no mechanism. Name the economic mechanism that "
        "would produce it (who pays, why they cannot stop) and the registered family that "
        "expresses it with exact parameters, or say that no mechanism is plausible. An anomaly "
        "without a named mechanism is an observation, not a candidate."),
    "model_pairing": (
        "You are given a feature-set x model pairing with a measured out-of-sample gain net of "
        "its complexity tax. State the ONE state-conditioned family recipe that would use it "
        "(which family, which parameters, which condition), or say why the pairing does not "
        "translate into a tradeable rule."),
    "mutation": (
        "You are given a certified cell and a proposed parameter mutation inside the survivor "
        "prior. Say whether the mutation keeps the stated mechanism intact and give the exact "
        "recipe, or reject it as a re-parameterisation without an economic reason."),
    "alpha_expression": (
        "You are asked for ONE formulaic alpha as a JSON expression tree over the desk's alpha "
        "grammar (terminals: close, open, high, low, ret, range, body, activity, spread, and the "
        "driver roles usd, rates, risk, gold, oil, growth; operators: neg, abs, sign, delay, "
        "delta, mean, std, min, max, ts_rank, zscore, decay, sum, add, sub, mul, div, corr, "
        "residual, cov; windows 2..240) with a side_mode (follow|fade) and the economic mechanism "
        "it expresses. Return it as family 'formula' with params {expr, side_mode, entry_z, "
        "hold_bars}. Never emit an expression you cannot justify economically."),
}


#: Where the single-flight lock lives, and how long a lock may be held before it is presumed dead.
#: DERIVED FROM THE RUN BUDGET, not chosen: a run may legitimately hold this for `RUN_BUDGET_SEC`
#: plus the last task it was already inside when the budget expired, so the stale threshold has to
#: clear both or a healthy long run would be killed by the next hour's tick. One extra budget is
#: the margin, which on the default puts the threshold at eighty minutes -- comfortably past any
#: honest run and comfortably short of leaving a crashed one locked out for a day.
LOCK = BASE / "data" / "hypotheses" / ".deepening.lock"


def _single_flight():
    """Acquire the run lock, or None when another run holds it.

    A CRASHED RUN MUST NOT LOCK THE DESK OUT FOR EVER, which is the failure mode of every naive
    lock file: the process dies mid-task, the file stays, and the organ is silently dark until a
    person notices. So the lock carries its own start time and a run older than the stale
    threshold is TAKEN OVER with the takeover logged -- an unattended desk cannot wait for someone
    to clear a file by hand.
    """
    stale_after = RUN_BUDGET_SEC * 2.0
    try:
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        if LOCK.exists():
            try:
                held = json.loads(LOCK.read_text("utf-8"))
                age = time.time() - float(held.get("at") or 0.0)
            except (OSError, ValueError, TypeError):
                age = stale_after + 1.0                       # unreadable lock is a dead lock
                held = {}
            if age <= stale_after:
                dlog(f"another deepening run holds the lock (pid={held.get('pid')}, "
                     f"{age:.0f}s old): exiting rather than racing it. The queue is worked once "
                     f"per hour whichever schedule wins -- MT5-Deepening or hourly_cycle -- and "
                     f"two runs would choose the same tasks and overwrite each other's output")
                return None
            dlog(f"taking over a stale lock ({age:.0f}s > {stale_after:.0f}s): the run holding it "
                 f"is presumed dead, because an unattended desk cannot wait for a person to "
                 f"clear a file")
        LOCK.write_text(json.dumps({"pid": os.getpid(), "at": time.time()}), "utf-8")
    except OSError as exc:
        # A LOCK THAT CANNOT BE TAKEN MUST NOT STOP THE WORK. The race it prevents is wasteful,
        # not dangerous -- the worked-ledger still stops double billing -- so an unwritable path
        # degrades to the previous behaviour rather than silencing the organ.
        dlog(f"lock unavailable ({type(exc).__name__}: {exc}); running unlocked")
        return LOCK
    return LOCK


def _release(lock) -> None:
    if lock is not None:
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    """Acquire the run lock, work the queue, and ALWAYS release -- including on a crash.

    The release is a `finally` rather than a line at the end, because the one run whose lock most
    needs clearing is the one that died: a lock left by a crash is what turns a wasteful race into
    a silently dark organ until the stale threshold expires.
    """
    lock = _single_flight()
    if lock is None:
        return 0
    try:
        return _work(argv)
    finally:
        _release(lock)


def _work(argv: list[str] | None = None) -> int:
    # `argv` accepts an explicit list so an in-process caller can invoke this without inheriting
    # ITS argv, matching daily_cycle.main. Added 2026-09-05 when hourly_cycle began draining the
    # queue: `parse_args()` with no argument reads sys.argv, so `hourly_cycle.py --whatever` would
    # have been parsed as this worker's flags -- an unrelated caller's arguments silently changing
    # how much the desk spends on seat calls.
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be worked; call no seat and write nothing")
    args = ap.parse_args(argv)

    queue = json.loads(DEEPEN.read_text("utf-8")) if DEEPEN.exists() else {}
    tasks = [t for t in (queue.get("tasks") or []) if isinstance(t, dict)]
    if not tasks:
        dlog("queue empty or unreadable -- nothing to work")
        return 0

    done = worked_ids()
    pending = voi_order([t for t in tasks if task_id(t) not in done])
    dlog(f"queue={len(tasks)} already-decided={len(done)} pending={len(pending)} "
         f"limit={args.limit}")
    if args.dry_run:
        for t in (pending if args.limit <= 0 else pending[:args.limit]):
            dlog(f"  would work {task_id(t)} [{t.get('source')}] {str(t.get('title'))[:70]}")
        return 0
    if not pending:
        dlog("every queued task already has a decision -- no spend this run")
        return 0

    universe = known_symbols()
    recovered: list[dict] = []
    counts: dict[str, int] = {}
    started = time.monotonic()
    for task in (pending if args.limit <= 0 else pending[:args.limit]):
        # THE BUDGET IS TIME. Checked BEFORE each task so a run never starts work it cannot finish
        # inside the cycle hosting it; an in-flight task always completes, because abandoning a
        # seat call mid-flight bills it and records nothing.
        if time.monotonic() - started > RUN_BUDGET_SEC:
            dlog(f"run budget {RUN_BUDGET_SEC:.0f}s spent; the remaining tasks carry to the next "
                 f"hourly pass in VOI order -- nothing is dropped")
            break
        tid = task_id(task)
        try:
            candidates, disposition = work_task(task, universe)
        except Exception as exc:
            # One bad row must not end the run: the rest of the batch is still worth working,
            # and the failure is recorded so it is not silently retried forever.
            candidates, disposition = [], f"ERROR: {type(exc).__name__}: {exc}"
        head = disposition.split(":")[0]
        counts[head] = counts.get(head, 0) + 1
        recovered.extend(candidates)
        record({"id": tid, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "source": task.get("source"), "url": task.get("url"),
                "disposition": disposition, "n_candidates": len(candidates)})
        dlog(f"  {tid} [{task.get('source')}] {disposition} -> {len(candidates)} candidate(s)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prior = []
    if OUT.exists():
        try:
            prior = (json.loads(OUT.read_text("utf-8")) or {}).get("candidates") or []
        except ValueError:
            prior = []
    OUT.write_text(json.dumps({
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "candidates": prior + recovered,
        "recovered_this_run": len(recovered),
        "dispositions": counts,
    }, indent=1), encoding="utf-8")
    dlog(f"worked {sum(counts.values())} task(s): {counts}; "
         f"{len(recovered)} new candidate(s) -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
