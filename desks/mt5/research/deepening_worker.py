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

THE SEAT IS THE SCARCE THING, AND MOST ROWS MUST NOT SPEND IT (measured 2026-09-24, trading box
vmi3571445). Three separate bounds were throttling this organ and only one of them was real:

  1. ONE ITEM PER CYCLE, and it was an accident of a sentinel. `DEFAULT_LIMIT` is 0 meaning
     "work the whole queue"; `hourly_cycle.deepen()` read it as a COUNT, scaled it by the
     bandit's share (0 x 0.274 = 0) and floored it with `max(1, _lim)`. The leg therefore
     passed `--limit 1` -- verified live. A sentinel for "unlimited" became "exactly one".

  2. THE MODEL SEAT'S DAILY CEILING IS REAL AND CANNOT BE WISHED AWAY. All fifteen configured
     seats are OpenRouter free models on ONE account key, and OpenRouter's free allowance is
     per-ACCOUNT per-day, not per-model: the provider refused at 458 calls on 2026-09-23
     (`limit_source: openrouter_free_tier_daily`). Adding models does not add budget. Measured
     mean latency 26.7s per call, so a serial lane exhausts the day by about 07:00 UTC and then
     has seventeen hours with no seat at all.

  3. WHAT THOSE SEVENTEEN HOURS WERE SPENT ON, and this was the real collapse. With the budget
     gone every task still entered the seat lane, took a refusal in 0.103s and appended a
     BLOCKED_SEAT_UNAVAILABLE row. 1,222,789 of 1,234,517 ledger rows (99.05%) were that same
     outage written over and over: an 849 MB worked-ledger and a 622 MB log, re-read TWICE at
     every startup (`worked_ids` then `cost_by_run`).

SO THE SEAT IS NOW SPENT ONLY WHERE IT CAN WIN, and the rest is decided by rule on the same pass.
The compiler already records WHY it could not compile each row, and its own source says an
EMPTY_CAPTURE row is "an LLM call that cannot possibly succeed -- there is nothing in the row to
read". Measured against that label: EMPTY_CAPTURE recovered 1 candidate in 1,000 seat calls
(0.10%) while NEEDS_SYMBOL_EXTRACTION recovered 11 in 1,114 (0.99%) -- ten times the yield per
call, and EMPTY_CAPTURE is 59% of the backlog. Routing by the compiler's own label therefore
moves the entire daily allowance onto rows that can pay for it.

NOTHING IS CAPPED, DEFERRED OR DISCARDED BY THIS. A row the seat will not read is decided on the
SAME pass by `no_seat_work`, which first re-runs the compiler for free (its vocabulary grows, so
a row refused last month can compile today) and, failing that, records a NAMED REFUSAL carrying
its reason and the remedy that would reopen it. The refusal is a terminal decision and a
`libs.research.set_aside` row, so the backlog falls by conversion and by naming, never by
dropping. `DEEPENING_BACKLOG.json` publishes the depth and the OLDEST AGE every pass, which is
what the no-queues law asks of a drain that cannot finish in one hour.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
#: THE BACKLOG, PUBLISHED. The no-queues law (LAWS §5e) allows a budget to leave work over and
#: requires the leftover's AGE to be published; `QUEUE_CENSUS.json` reported this queue
#: UNMEASURED because its rows carry no enqueue stamp. The worker stamps what it sees instead,
#: which is the honest measurement anyway: the compiler rewrites the queue file every hour, so a
#: stamp written there resets, while first-seen-by-the-drain does not.
BACKLOG = BASE / "reports" / "DEEPENING_BACKLOG.json"
#: THE RATCHET. Decisions per hour, and the high-water mark that only ever rises. A pass that
#: measures below the mark is a REGRESSION and says so; `tests/test_deepening_worker.py` fences
#: the direction so a later change cannot quietly lower it.
THROUGHPUT = BASE / "reports" / "DEEPENING_THROUGHPUT.json"

#: THE COMPILER'S OWN LABEL DECIDES THE LANE. Each entry is the disposition the compiler recorded
#: on the row -> (terminal disposition, why the seat cannot win here, what would reopen it).
#: These are REFUSALS WITH A NAMED REMEDY, never discards: the row keeps its identity, the reason
#: is recorded against it, and the moment the remedy lands the row compiles or returns to the
#: seat lane on its own.
NO_SEAT_LANE: dict[str, tuple[str, str, str]] = {
    "EMPTY_CAPTURE": (
        "REFUSED_NO_BODY_CAPTURED",
        "the miner captured a LINK, not a page: the row carries a title and a url and no body, "
        "so there is no text for a reader to quote. Measured across 1,000 seat calls on this "
        "label: 1 candidate recovered (0.10%)",
        "re-fetch the page body -- this is a COLLECTOR defect, not a research backlog; a row "
        "that gains text is compiled by the hourly compiler and returns to the seat lane"),
    "OPERATIONAL_ROW": (
        "REFUSED_OPERATIONAL_ROW",
        "the compiler read this row as operational (a selector job, a fetch chore): it states no "
        "market claim, so there is no mechanism for a reader to recover",
        "none needed -- an operational row is not a hypothesis and never becomes one"),
    "BANNED_FAMILY": (
        "REFUSED_BANNED_FAMILY",
        "the family on this row is refused upstream (the two-lane rule, or a family the gauntlet "
        "has measured as producing zero judgeable cells). A seat cannot un-ban it",
        "the ban is data-driven and re-derived every sweep; a family that leaves the banned set "
        "puts its rows back in the ordinary lane with no action here"),
}

#: How many seat calls may be in flight at once. DERIVED FROM THIS BOX, never a constant sized
#: off another machine (CLAUDE.md's standing cautionary tale). A seat call is HTTP wait -- 26.7s
#: mean, 15.1s median, measured over 5,314 calls -- so these are threads parked on a socket and
#: cost neither a core nor a gigabyte; the subtraction is what leaves the live terminal and the
#: gateway their cores on the box that trades. The daily ceiling is unchanged by this: the same
#: 458 calls are made, they are simply made inside the hour the desk is awake instead of
#: trickling out one at a time until the budget dies unspent.
def seat_workers() -> int:
    raw = os.environ.get("DEEPEN_SEAT_WORKERS", "").strip()
    if raw:
        with contextlib.suppress(ValueError):
            return max(1, int(raw))
    return max(2, min(12, (os.cpu_count() or 4) - 2))


#: Above this many bytes the worked ledger is compacted before it is read. It is read TWICE per
#: run (`worked_ids`, then `cost_by_run`), both with `read_text().splitlines()`, so its size is
#: startup latency spent before the first task: 849 MB measured 10.9s + 20.5s on the trading box.
#: 64 MB holds every terminal decision this desk has ever made many times over.
COMPACT_OVER_BYTES = int(os.environ.get("DEEPEN_COMPACT_OVER_BYTES", str(64 * 1024 * 1024)))

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

#: The bandit's budget file. `libs.research.bandit` writes the arm shares here; when it also
#: carries a `controller_variant`, every worked row is stamped with it so two allocation policies
#: run side by side can later be compared on certificates per compute-hour. Read, stamped, and
#: NOT acted on: this worker does not split its queue by variant yet.
BUDGET = BASE / "data" / "research_budget.json"

#: A task class's measured cost is floored here before it divides the score. A seat call's clock
#: is not resolved below a second, so a class whose mean came out at a few hundred milliseconds
#: would otherwise be promoted by measurement noise rather than by being cheap.
MIN_TASK_COST_S = 1.0

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


def worked_ids(*, retry_seat_blocks: bool = False) -> set[str]:
    """Return terminal task identities.

    A missing model seat is an infrastructure dependency, not evidence against the
    source row.  Preserve that distinction in the ledger and make those rows
    eligible again only once a seat is actually configured; otherwise an hourly
    retry would spend the entire conversion budget rediscovering the same outage.
    Older ledgers used ``REJECTED: seat error`` for this condition, so recognize
    them too rather than permanently burying work due to the old label.
    """
    if not WORKED.exists():
        return set()
    out: set[str] = set()
    for line in WORKED.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            disposition = str(row.get("disposition") or "")
            seat_blocked = (disposition.startswith("BLOCKED_SEAT_UNAVAILABLE:")
                            or disposition.startswith("REJECTED: seat error:"))
            if retry_seat_blocks and seat_blocked:
                continue
            out.add(str(row["id"]))
        except (ValueError, KeyError):
            continue
    return out


def ledger_ids() -> tuple[set[str], set[str]]:
    """(terminal ids, seat-outage ids) in ONE read of the worked ledger.

    THE TWO SETS ANSWER DIFFERENT QUESTIONS AND MUST NOT BE CONFLATED. Whether a seat-blocked row
    is retried THIS PASS depends on whether a seat exists right now; whether it is still WAITING
    does not. Measured 2026-09-24: the published backlog read `depth: 0` while 6,674 rows were
    sitting unread, because a pass that found no configured seat treated every outage row as
    decided and the census inherited that. An absence reported as a clean verdict is the exact
    failure L1.28a names, and a backlog artifact is the last place it belongs.
    """
    terminal: set[str] = set()
    outage: set[str] = set()
    if not WORKED.exists():
        return terminal, outage
    try:
        with WORKED.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    tid = str(row["id"])
                except (ValueError, KeyError):
                    continue
                (outage if is_outage(str(row.get("disposition") or ""))
                 else terminal).add(tid)
    except OSError:
        return terminal, outage
    return terminal, outage - terminal


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
    # THE TWO EXPERIENCE CLASSES, RETRIEVED BEFORE GENERATION (Tier-1 Q17). `semantic_memory`
    # distils the corpus into POSITIVE (constructions that survived, per family) and NEGATIVE
    # (the six classes of mistake, derived from the gate each cell died at) every build. Both
    # halves ride the prompt: the first says what has worked in this family, the second says what
    # keeps killing things here. An absent distillation adds nothing and is never fabricated.
    try:
        exp = _experience_lines(task)
        if exp:
            lines.append("DESK EXPERIENCE:\n" + exp)
    except Exception:
        pass
    return "\n".join(lines)


def _experience_lines(task: dict, limit_chars: int = 900) -> str:
    """`data/experience_memory.json` rendered for this task: positive constructions in its family
    first, then the negative classes by count. Empty when the distillation is UNMEASURED."""
    import semantic_memory as _sm
    doc = _sm.experience()
    if not isinstance(doc, dict) or doc.get("status") != "MEASURED":
        return ""
    fam = str(task.get("family") or "").strip()
    out: list[str] = []
    pos = doc.get("positive") or {}
    if isinstance(pos, dict):
        rows = ([(fam, pos[fam])] if fam and fam in pos else
                list(pos.items())[:2])
        for name, slot in rows:
            if not isinstance(slot, dict):
                continue
            out.append(f"[survived] {name}: {slot.get('n')} certified, classes "
                       f"{sorted(slot.get('asset_classes') or {})}")
            for c in (slot.get("constructions") or [])[:2]:
                out.append(f"    + {str(c.get('text') or '')[:160]}")
    neg = doc.get("negative") or {}
    if isinstance(neg, dict):
        ranked = sorted(((k, int(v.get("n") or 0)) for k, v in neg.items()
                         if isinstance(v, dict)), key=lambda kv: -kv[1])
        out.append("[killed by] " + ", ".join(f"{k}={n}" for k, n in ranked if n))
        worst = ranked[0][0] if ranked and ranked[0][1] else ""
        for e in ((neg.get(worst) or {}).get("examples") or [])[:2]:
            out.append(f"    - {worst}: {str(e.get('text') or '')[:160]}")
    return "\n".join(out)[:limit_chars]


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
        if why.startswith("seat error:"):
            return [], f"BLOCKED_SEAT_UNAVAILABLE: {why}"
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


def lane(task: dict) -> str:
    """Which lane decides this row: ``"rule"`` (no seat) or ``"seat"``.

    THE COMPILER ALREADY SAID WHICH. Every queued row carries the disposition the compiler
    recorded when it refused to compile it, and that label is a statement about what the row
    CONTAINS, not about how interesting it is. A row labelled EMPTY_CAPTURE has no body text;
    the compiler's own source calls a seat call on one "an LLM call that cannot possibly
    succeed". Believing that label is not a quality screen and not a cap -- the row is decided
    on this pass either way -- it is refusing to spend a 458-a-day allowance on the one class of
    row that measured 0.10% against another class's 0.99%.

    A MUTATION ALREADY CARRIES ITS RECIPE, so it has never needed a seat either.
    """
    if (str(task.get("kind") or "") == "mutation" and isinstance(task.get("family"), str)
            and isinstance(task.get("params"), dict) and task.get("symbols")):
        return "rule"
    return "rule" if str(task.get("disposition") or "") in NO_SEAT_LANE else "seat"


def no_seat_work(task: dict, universe: set[str]) -> tuple[list[dict], str]:
    """Decide a row WITHOUT a seat call: compile it if the compiler now can, else name the refusal.

    THE FREE RETRY COMES FIRST, and it is not a formality. `compile_row` is the same door every
    miner row goes through and its vocabulary GROWS -- aliases, family phrases, newly registered
    families, a ban lifted by the gauntlet's own measurement. A row the compiler refused last
    month can compile today at no cost and with no seat, so it is offered the door again before
    anything else is said about it.

    THE REFUSAL IS NAMED, AND IT IS NOT A DISCARD. When the compiler still refuses, the row gets
    a terminal disposition that says WHY a reader could not have helped and WHAT would reopen it.
    That is the difference the desk cares about: a silent drop is indistinguishable from an empty
    search, while a named refusal is a measurement that points at the organ which can fix it --
    for EMPTY_CAPTURE, the crawler that captured a link instead of a page.
    """
    try:
        candidates, disposition = compile_row(str(task.get("source") or "unknown"),
                                              dict(task), universe)
    except Exception as exc:                     # the compiler must never end the pass
        return [], f"ERROR: {type(exc).__name__}: {exc}"
    if candidates:
        for c in candidates:
            c["deepened"] = True
            c.setdefault("evidence", "recompiled without a seat: the compiler's vocabulary now "
                                     "reads this row")
        return candidates, f"RECOVERED_{disposition}"
    label, why, remedy = NO_SEAT_LANE.get(
        str(task.get("disposition") or ""),
        ("REFUSED_NOT_CONVERTIBLE",
         f"the compiler refused this row again as {disposition}", "none recorded"))
    return [], f"{label}: {why}; remedy: {remedy}"


def task_class(task: dict) -> str:
    """The cost class a task is billed under: its `kind`, as a run name the compute ledger can
    aggregate. `deepen:<kind>` so the rows sit beside the cycle's own `deepen` leg row and are
    never confused with it."""
    return f"deepen:{task.get('kind') or 'unknown'}"


def task_costs() -> tuple[dict[str, float], str]:
    """Measured mean wall seconds per task class, and the basis the order will cite.

    THE DENOMINATOR, FROM THE LEDGER THAT ALREADY EXISTS. `libs.ops.compute_ledger.cost_by_run`
    aggregates any append-only ledger whose rows carry `at`, `run` and `wall_s`; the worked
    ledger here is one row per decided task, so once each row is stamped with its class and its
    seconds (below) the SAME function prices a task class with no second ledger and no join.
    Falls back to 1.0 for every class when nothing is costed yet, which leaves the order exactly
    what it was -- a divisor of one changes nothing -- and says so in the basis.

    The hourly cycle's own `deepen` row in the compute ledger is the LEG's wall time; it is
    class-blind, so it cannot order tasks against each other and is only cited.
    """
    try:
        from libs.ops.compute_ledger import cost_by_run
    except Exception:
        return {}, "uncosted: compute ledger unavailable; every class divides by 1.0"
    costs: dict[str, float] = {}
    try:
        for name, c in cost_by_run(path=WORKED).items():
            mean = c.get("mean_wall_s")
            if name.startswith("deepen:") and isinstance(mean, (int, float)) and mean > 0:
                costs[name] = float(mean)
    except Exception:
        costs = {}
    if costs:
        return costs, (f"measured: mean wall seconds per task class from "
                       f"cost_by_run({WORKED.name}), {len(costs)} class(es), floored at "
                       f"{MIN_TASK_COST_S}s")
    leg = ""
    try:
        d = cost_by_run().get("deepen") or {}
        if d.get("runs"):
            leg = (f"; the cycle's `deepen` leg row is {d.get('mean_wall_s')}s over "
                   f"{d['runs']} run(s), class-blind")
    except Exception:
        leg = ""
    return {}, f"uncosted: no per-class task rows in {WORKED.name} yet; order unchanged{leg}"


def controller_variant() -> str | None:
    """`controller_variant` from the bandit's budget file, when it carries one. Stamped on every
    worked row so two allocation policies can later be compared; not acted on here."""
    try:
        v = json.loads(BUDGET.read_text("utf-8")).get("controller_variant")
    except (OSError, ValueError, AttributeError):
        return None
    return str(v) if v not in (None, "") else None


def voi_order(tasks: list[dict], costs: dict[str, float] | None = None,
              scorer=None) -> list[dict]:
    """Work the tasks with the highest expected value of information PER MEASURED SECOND first.

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

    DIVIDED BY THE CLASS'S MEASURED COST (2026-09-09). The score had no denominator: a task
    worth 2 that takes 40 seconds of seat time sat ahead of one worth 1.5 that takes 3, and the
    budget that binds every hour was spent as if seconds were free. `costs` is
    `task_class -> mean wall seconds` from `task_costs()`; a class with no measurement divides
    by 1.0, so an uncosted queue orders exactly as before. Nothing is dropped by this -- the
    same tasks are worked, cheapest information first.

    Deterministic, so two runs on the same queue work the same tasks in the same order.
    """
    score = scorer if scorer is not None else _scorer()
    costs = costs or {}

    def _key(t: dict) -> tuple[float, str]:
        cost = max(MIN_TASK_COST_S, float(costs.get(task_class(t), 1.0)))
        return (-score(t) / cost, task_id(t))

    return sorted(tasks, key=_key)


def _scorer():
    """The value-of-information score for one task, as a callable built once per run."""
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
        # ENSEMBLE DISAGREEMENT IS INFORMATION (Tier-1 item G20). The compiler already measures
        # two things nothing acted on: how many independent engines named a cell, and whether a
        # symbol is CONTESTED -- two engines proposing DIFFERENT families for it. Agreement is
        # the ordinary signal, and it is deliberately the weaker multiplier here: several
        # crawlers naming one cell is often one story reprinted. A CONTESTED cell is the more
        # valuable trial, because testing it SETTLES which engine was right about that symbol,
        # and that answer prices every future proposal from both of them.
        #
        # NOTHING IS DROPPED AND NOTHING IS CAPPED. This multiplies a score that only orders the
        # queue; an uncontested task with one source multiplies by 1.0 and sits exactly where it
        # sat before. The same tasks are worked, highest information first.
        agree = 1.0 + 0.25 * max(0, int(t.get("n_independent_sources") or 1) - 1)
        # 1.75, so a contested cell always outranks even three engines agreeing
        # (1 + 0.25 x 2 = 1.5). The ordering is the claim: settling a disagreement
        # beats confirming an echo, and the constants must not make them a tie.
        contested = 1.75 if t.get("contested") else 1.0
        return p * worth * novelty * direction * agree * contested

    return _score


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


def is_outage(disposition: str) -> bool:
    """Is this row the seat being unavailable rather than a decision about the source?"""
    return (disposition.startswith("BLOCKED_SEAT_UNAVAILABLE:")
            or disposition.startswith("REJECTED: seat error:"))


def ends_the_day(disposition: str) -> bool:
    """Is this refusal the DAY's allowance, rather than "slow down for a minute"?

    THE TWO ARE OPPOSITE INSTRUCTIONS AND LOOK IDENTICAL AT THE ORGAN. A daily refusal means
    every further call today takes the same refusal, so continuing is pure waste; a burst refusal
    means the next call in a few seconds succeeds, so STOPPING on one would throw away most of an
    allowance the desk has already been granted. `llm_seat` already owns this distinction -- it
    matches the provider's own wording rather than the status code, because a 429 alone cannot
    tell them apart -- so this asks it rather than guessing a second time.

    Unrecognised is NOT treated as terminal: an unfamiliar refusal ends one row, never the pass.
    """
    if not is_outage(disposition):
        return False
    try:
        from libs.ops.llm_seat import _is_daily_free_refusal
        return bool(_is_daily_free_refusal(disposition))
    except Exception:
        return "daily" in disposition.lower() or "per-day" in disposition.lower()


def compact_ledger(path: Path | None = None, *, over_bytes: int | None = None) -> dict:
    """Drop the repeated OUTAGE rows from the worked ledger, keeping every DECISION.

    NOTHING DECIDED IS LOST, and that is what makes this safe rather than a deletion. A
    BLOCKED_SEAT_UNAVAILABLE row is already NON-TERMINAL by construction -- `worked_ids` skips it
    the moment a seat exists, precisely because an outage is not evidence about the source -- so
    it can be re-derived at zero cost by the row simply being worked again. What cannot be
    re-derived is a real disposition, and every one of those is kept.

    ONE OUTAGE ROW PER UTC DAY SURVIVES, so the history of the outage is still readable: the desk
    can still see that the seat was exhausted on a given day without carrying 145,814 identical
    lines that say it. Returns the census; never raises.
    """
    p = path or WORKED
    limit = COMPACT_OVER_BYTES if over_bytes is None else over_bytes
    try:
        size = p.stat().st_size
    except OSError:
        return {"compacted": False, "why": "ledger absent"}
    if size <= limit:
        return {"compacted": False, "why": f"{size} bytes is within the {limit}-byte budget",
                "bytes": size}
    kept: list[str] = []
    outage_days: set[str] = set()
    rows = dropped = 0
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rows += 1
                try:
                    row = json.loads(line)
                except ValueError:
                    kept.append(line.rstrip("\n"))     # unreadable is never silently dropped
                    continue
                disposition = str(row.get("disposition") or "")
                if not is_outage(disposition):
                    kept.append(line.rstrip("\n"))
                    continue
                day = str(row.get("at") or "")[:10]
                if day in outage_days:
                    dropped += 1
                    continue
                outage_days.add(day)
                kept.append(line.rstrip("\n"))
        tmp = p.with_suffix(".jsonl.compact")
        tmp.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        os.replace(tmp, p)
    except OSError as exc:
        return {"compacted": False, "why": f"{type(exc).__name__}: {exc}"}
    after = p.stat().st_size
    return {"compacted": True, "rows_before": rows, "rows_after": len(kept),
            "outage_rows_dropped": dropped, "outage_days_kept": len(outage_days),
            "bytes_before": size, "bytes_after": after,
            "why": ("repeated seat-outage rows are non-terminal by construction (worked_ids "
                    "already skips them when a seat exists) and are re-derived for free; one "
                    "row per UTC day is kept so the outage stays readable")}


def _first_seen(pending_ids: set[str], now: datetime) -> dict[str, str]:
    """When this drain FIRST saw each open task, persisted across passes.

    THE QUEUE FILE CANNOT CARRY THIS. `miner_candidate_compiler` rewrites
    `miner_deepening_queue.json` from scratch every hour, so a stamp written into a task there is
    reset every hour and would report a backlog that is permanently one hour old. The drain's own
    first sighting is both stable and the number the no-queues law actually asks for: how long
    has this row been waiting on the organ that owes it a decision.
    """
    stamp = now.isoformat(timespec="seconds")
    prior: dict[str, str] = {}
    with contextlib.suppress(OSError, ValueError, AttributeError):
        doc = json.loads(BACKLOG.read_text("utf-8"))
        raw = doc.get("first_seen")
        if isinstance(raw, dict):
            prior = {str(k): str(v) for k, v in raw.items()}
    return {tid: prior.get(tid, stamp) for tid in pending_ids}


def publish_backlog(pending: list[dict], census: dict, now: datetime,
                    rate_per_h: float) -> dict:
    """Publish the backlog and ITS OLDEST AGE -- the no-queues law's actual requirement.

    A budget may leave work over. What it may not do is leave it over unmeasured: an 18,128-row
    backlog with no published age is the exact shape LAWS §5e exists to prevent, and
    `QUEUE_CENSUS.json` was reporting this queue UNMEASURED for precisely that reason ("28,450
    rows, no per-row time"). UNMEASURED is a real answer and it is not this one any more.
    """
    seen = _first_seen({task_id(t) for t in pending}, now)
    ages = []
    for value in seen.values():
        dt = None
        with contextlib.suppress(ValueError):
            dt = datetime.fromisoformat(value)
        if dt is not None:
            ages.append(dt if dt.tzinfo else dt.replace(tzinfo=UTC))
    oldest = min(ages) if ages else None
    depth = len(pending)
    doc = {
        "at": now.isoformat(timespec="seconds"),
        "queue": "miner_deepening",
        "drainer": "desks/mt5/research/deepening_worker.py",
        "depth": depth,
        "rows_stamped": len(seen),
        "age_measurable": oldest is not None,
        "oldest_age_h": (round((now - oldest).total_seconds() / 3600.0, 3)
                         if oldest is not None else None),
        "oldest_at": oldest.isoformat(timespec="seconds") if oldest is not None else None,
        # A FIRST PASS CANNOT REPORT AN OLD BACKLOG AND MUST NOT PRETEND TO. Every stamp is
        # written the first time this drain sees a row, so on the pass that creates the sidecar
        # every age is zero -- which is a fact about the measurement, not about the queue. Saying
        # so here stops the next reader mistaking a young ledger for a drained one.
        "age_basis": ("nothing is waiting: there is no age to measure" if not ages else
                      "FIRST PASS: every open row was stamped by this run, so 0.0h is the age of "
                      "the MEASUREMENT and not of the backlog. Real ages accrue from the next "
                      "pass onward" if not any(a < now for a in ages) else
                      "measured from each row's first sighting by this drain"),
        "decisions_per_h": round(rate_per_h, 2),
        # UNMEASURED, not "never": a pass that decided nothing cannot price the clearance.
        "days_to_clear": (round(depth / (rate_per_h * 24.0), 2) if rate_per_h > 0 else None),
        "lanes": census,
        "law": ("LAWS §5e: nothing is queued; a budget may leave work over and its AGE is "
                "published. Age is FIRST SEEN BY THIS DRAIN, not a stamp in the queue file -- "
                "the compiler rewrites that file hourly, so a stamp there would reset every hour "
                "and report a backlog that is permanently one hour old"),
        "first_seen": seen,
    }
    with contextlib.suppress(OSError):
        BACKLOG.parent.mkdir(parents=True, exist_ok=True)
        tmp = BACKLOG.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, BACKLOG)
    return doc


def publish_throughput(decided: int, elapsed_s: float, backlog_before: int,
                       backlog_after: int, now: datetime, counts: dict[str, int],
                       *, work_limited: bool = False) -> dict:
    """The ratchet: decisions per hour, and a high-water mark that only ever rises.

    A THROUGHPUT NUMBER THAT CAN FALL SILENTLY IS NOT A MEASUREMENT, it is a mood. The mark here
    only ever goes up, every pass records itself against it, and a pass that got SLOWER is
    labelled REGRESSION in its own artifact so the next reader sees it without being told. The
    test suite fences the direction; this file is the evidence it fences.

    BUT RUNNING OUT OF WORK IS NOT GETTING SLOWER, and a ratchet that cannot tell them apart
    cries wolf until nobody reads it. Measured the same night: the pass that drained 11,613
    rule-lane rows set a mark of 714,009/h, and the very next pass -- with the rule lane EMPTY
    because the first one had finished it, and the provider refusing the day's allowance -- came
    in at 398/h. Nothing regressed; there was simply nothing left to decide. So a pass that ran
    out of work reports WORK_LIMITED, which is a different sentence from REGRESSION and is the
    true one.

    AN OUTAGE IS NOT A DECISION EITHER, so it never enters the numerator. A pass that made six
    calls and took six refusals decided nothing, and a rate that counted those would measure how
    fast this desk can be told no.
    """
    outages = sum(v for k, v in counts.items() if k == "BLOCKED_SEAT_UNAVAILABLE")
    decided = max(0, decided - outages)
    rate = (decided / (elapsed_s / 3600.0)) if elapsed_s > 0 else 0.0
    prior: dict = {}
    with contextlib.suppress(OSError, ValueError, AttributeError):
        loaded = json.loads(THROUGHPUT.read_text("utf-8"))
        if isinstance(loaded, dict):
            prior = loaded
    best = float(prior.get("best_decisions_per_h") or 0.0)
    mark = max(best, rate)
    doc = {
        "at": now.isoformat(timespec="seconds"),
        "decisions": decided, "outages": outages, "elapsed_s": round(elapsed_s, 1),
        "decisions_per_h": round(rate, 2),
        "best_decisions_per_h": round(mark, 2),
        "best_at": (now.isoformat(timespec="seconds") if rate >= best
                    else prior.get("best_at")),
        "backlog_before": backlog_before, "backlog_after": backlog_after,
        "drained": backlog_before - backlog_after,
        "dispositions": counts,
        "work_limited": bool(work_limited),
        "status": ("RATCHET" if rate >= best else
                   "WORK_LIMITED" if work_limited else "REGRESSION"),
        "rule": ("the high-water mark only ever rises. A pass that got SLOWER is a REGRESSION and "
                 "is labelled one here; a pass that ran out of work is WORK_LIMITED, which is a "
                 "different sentence and the true one. An outage is not a decision and never "
                 "enters the numerator. tests/test_deepening_worker.py fences all three"),
    }
    with contextlib.suppress(OSError):
        THROUGHPUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = THROUGHPUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, THROUGHPUT)
    return doc


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
    # THE RATE IS MEASURED OVER THE WHOLE PASS, not over the work loop. Compaction, the ledger
    # reads and the VOI sort are seconds this organ spent and did not convert in; charging them
    # to the rate is what makes two passes comparable and what makes the ratchet mean something.
    # The first measurement on the trading box read 714,009/h against a work loop of 58.6s while
    # the pass had taken 274.3s -- a number that flatters whichever pass happened to find the
    # most rule-lane rows, which is not a throughput.
    pass_started = time.monotonic()

    queue = json.loads(DEEPEN.read_text("utf-8")) if DEEPEN.exists() else {}
    tasks = [t for t in (queue.get("tasks") or []) if isinstance(t, dict)]
    if not tasks:
        dlog("queue empty or unreadable -- nothing to work")
        return 0

    # COMPACT BEFORE READING, because the ledger is read twice and its size IS startup latency.
    if not args.dry_run:
        squeeze = compact_ledger()
        if squeeze.get("compacted"):
            dlog(f"worked-ledger compacted: {squeeze['rows_before']} -> {squeeze['rows_after']} "
                 f"rows, {squeeze['bytes_before']} -> {squeeze['bytes_after']} bytes "
                 f"({squeeze['outage_rows_dropped']} repeated outage rows, "
                 f"{squeeze['outage_days_kept']} day(s) kept)")

    # A MISSING SEAT IS AN OUTAGE, NOT A VERDICT (theirs, 2026-09-10). A row blocked on an
    # unconfigured external model was buried permanently; retried every hour it would spend the
    # whole conversion budget rediscovering the same outage. Eligible again only once a seat
    # actually exists.
    try:
        from libs.ops.llm_seat import primary_seat
        retry_seat_blocks = primary_seat() is not None
    except Exception:
        retry_seat_blocks = False
    # ONE read, TWO questions: what is DECIDED (never re-worked) and what is merely BLOCKED
    # (re-worked when a seat exists, and OPEN in the census either way).
    terminal, outage = ledger_ids()
    done = terminal if retry_seat_blocks else (terminal | outage)
    costs, cost_basis = task_costs()
    variant = controller_variant()
    open_tasks = [t for t in tasks if task_id(t) not in done]

    # TWO LANES, SPLIT BEFORE ANYTHING IS ORDERED. The rule lane needs no ordering -- every row
    # in it gets the same free compiler retry and, failing that, its named refusal -- and keeping
    # it out of `voi_order` is not a nicety: scoring calls the hypothesis graph and the graveyard
    # model per task, and ordering all 18,423 pending rows measured 245.5 SECONDS of a 2,400s
    # budget on the trading box. The seat lane is the only lane whose order can change an outcome,
    # because it is the only lane with a scarce resource to spend.
    rule_tasks = [t for t in open_tasks if lane(t) == "rule"]
    seat_tasks = voi_order([t for t in open_tasks if lane(t) == "seat"], costs=costs)
    pending = rule_tasks + seat_tasks
    lane_census = {"rule": len(rule_tasks), "seat": len(seat_tasks)}
    dlog(f"queue={len(tasks)} already-decided={len(done)} pending={len(pending)} "
         f"lanes={lane_census} limit={args.limit} cost_basis={cost_basis} "
         f"controller_variant={variant}")
    if args.dry_run:
        for t in (pending if args.limit <= 0 else pending[:args.limit]):
            dlog(f"  would work {task_id(t)} [{lane(t)}] [{t.get('source')}] "
                 f"{str(t.get('title'))[:70]}")
        return 0
    if not pending:
        dlog("every queued task already has a decision -- no spend this run")
        return 0

    universe = known_symbols()
    recovered: list[dict] = []
    counts: dict[str, int] = {}
    started = time.monotonic()
    backlog_before = len(pending)
    write_lock = threading.Lock()
    decided_ids: set[str] = set()

    def commit(task: dict, candidates: list[dict], disposition: str, wall_s: float) -> None:
        """Record one decision. Holds the lock only for the append, so the pool never serialises
        on a seat call -- only on the few microseconds of writing a line."""
        cls = task_class(task)
        head = disposition.split(":")[0]
        entry = {"id": task_id(task), "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                 "source": task.get("source"), "url": task.get("url"),
                 "disposition": disposition, "n_candidates": len(candidates),
                 "run": cls, "kind": task.get("kind"), "lane": lane(task),
                 "wall_s": round(wall_s, 3),
                 "cost_basis": (f"measured:{cls}:{costs[cls]:.2f}s" if cls in costs
                                else "uncosted:1.0"),
                 "controller_variant": variant}
        # AND IT SAYS WHAT WOULD UNBLOCK IT. A row parked on an unconfigured seat is an outage
        # with a remedy, not a rejection; without this the ledger records only that it stopped.
        if disposition.startswith("BLOCKED_SEAT_UNAVAILABLE:"):
            entry["retry_action"] = "retry automatically after an external-model seat is configured"
        with write_lock:
            counts[head] = counts.get(head, 0) + 1
            recovered.extend(candidates)
            # AN OUTAGE ROW IS NOT A DECISION, so it never counts against the backlog: the row
            # keeps its place and its published age, which is the whole point of the distinction.
            if not is_outage(disposition):
                decided_ids.add(entry["id"])
            record(entry)

    def out_of_time() -> bool:
        return time.monotonic() - started > RUN_BUDGET_SEC

    # ---- THE RULE LANE, FIRST AND UNBOUNDED BY ANY QUOTA -----------------------------------
    # It runs before the seat lane on purpose. It costs no request, it is the lane that actually
    # moves the backlog, and running it first means a pass that dies later still drained.
    budget = args.limit if args.limit > 0 else len(pending)
    for task in rule_tasks[:budget]:
        if out_of_time():
            dlog("run budget spent in the rule lane; the rest carries to the next pass -- "
                 "nothing is dropped and its age is published in DEEPENING_BACKLOG.json")
            break
        t0 = time.monotonic()
        try:
            candidates, disposition = no_seat_work(task, universe)
        except Exception as exc:
            candidates, disposition = [], f"ERROR: {type(exc).__name__}: {exc}"
        commit(task, candidates, disposition, time.monotonic() - t0)
    rule_done = sum(counts.values())
    dlog(f"rule lane: {rule_done} decided with no seat call, "
         f"{len(recovered)} candidate(s) recovered")
    # THE NAMED REFUSAL, IN THE DESK'S OWN LEDGER. `set_aside` is where a pass records what it
    # did not carry, so a reader can tell a principled routing from an arbitrary drop.
    refused = sum(v for k, v in counts.items() if k.startswith("REFUSED_"))
    if refused:
        with contextlib.suppress(Exception):
            from libs.research import set_aside
            set_aside.note("deepening_worker", "no_seat_lane", kept=rule_done - refused,
                           considered=rule_done,
                           ordering="compiler disposition: EMPTY_CAPTURE / OPERATIONAL_ROW / "
                                    "BANNED_FAMILY carry no text a reader could quote; each is "
                                    "refused BY NAME with its remedy, never dropped")

    # ---- THE SEAT LANE, PARALLEL, AND IT STOPS THE MOMENT THE DAY'S ALLOWANCE IS GONE -------
    # Before this, an exhausted budget still cost one refusal per row at 0.103s each: the pass
    # spent its whole 40 minutes appending the same outage. Asked ONCE, up front.
    left, why_seat = _seat_budget()
    if seat_tasks and left == 0:
        commit(seat_tasks[0], [], f"BLOCKED_SEAT_UNAVAILABLE: {why_seat}", 0.0)
        dlog(f"seat lane stood down: {why_seat}. ONE outage row recorded for the pass instead of "
             f"one per row -- {len(seat_tasks)} row(s) keep their place and their published age")
    elif seat_tasks:
        workers = seat_workers()
        share = seat_tasks[:min(budget, left)] if left > 0 else seat_tasks[:budget]
        dlog(f"seat lane: {len(share)} of {len(seat_tasks)} row(s) this pass on {workers} "
             f"worker(s); {why_seat}")
        stop = threading.Event()

        def run_one(task: dict) -> None:
            if stop.is_set() or out_of_time():
                return
            t0 = time.monotonic()
            try:
                candidates, disposition = work_task(task, universe)
            except Exception as exc:
                candidates, disposition = [], f"ERROR: {type(exc).__name__}: {exc}"
            # A DAILY REFUSAL ENDS THE LANE, not just this row: every further call today would
            # take the same refusal and record the same nothing. A BURST refusal must NOT --
            # stopping on "slow down for a minute" would hand back most of an allowance the desk
            # has already been granted, which is the timid reading this house does not take.
            if ends_the_day(disposition):
                stop.set()
            commit(task, candidates, disposition, time.monotonic() - t0)

        with ThreadPoolExecutor(max_workers=workers,
                                thread_name_prefix="deepen-seat") as pool:
            list(pool.map(run_one, share))
        if stop.is_set():
            dlog("seat lane stopped: the provider refused the DAY's allowance, not a burst. The "
                 "remaining rows keep their place and their published age, and the rule lane has "
                 "already had its turn at every row it can decide")

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

    elapsed = max(1e-6, time.monotonic() - pass_started)
    # THE CENSUS COUNTS EVERY ROW WITHOUT A TERMINAL DECISION, including the rows this pass never
    # reached and the ones a seat outage left where they were. `pending` is what this pass was
    # willing to work; the BACKLOG is what the desk still owes an answer on, and they differ by
    # exactly the outage set whenever no seat is configured.
    settled = terminal | decided_ids
    still_open = [t for t in tasks if task_id(t) not in settled]
    now = datetime.now(tz=UTC)
    rate = sum(counts.values()) / (elapsed / 3600.0)
    back = publish_backlog(still_open, lane_census, now, rate)
    # WORK-LIMITED means the pass stopped because there was nothing left it could decide, not
    # because it was slow: an empty rule lane plus a seat that will not answer today. Saying so
    # is what stops one enormous drain's mark from labelling every later pass a regression.
    work_limited = not rule_tasks or bool(counts.get("BLOCKED_SEAT_UNAVAILABLE"))
    ratchet = publish_throughput(sum(counts.values()), elapsed, backlog_before,
                                 len(still_open), now, counts, work_limited=work_limited)
    dlog(f"worked {sum(counts.values())} task(s): {counts}; "
         f"{len(recovered)} new candidate(s) -> {OUT.name}")
    dlog(f"throughput {ratchet['decisions_per_h']}/h (best {ratchet['best_decisions_per_h']}/h, "
         f"{ratchet['status']}); backlog {backlog_before} -> {len(still_open)}, oldest "
         f"{back['oldest_age_h']}h, days_to_clear {back['days_to_clear']}")
    return 0


def _seat_budget() -> tuple[int, str]:
    """How many free seat requests today still has, and the sentence that explains the number.

    THE CEILING IS EXTERNAL AND CANNOT BE WISHED AWAY. All fifteen configured seats are free
    OpenRouter models on ONE account key and the provider's free allowance is per-ACCOUNT per-day
    -- it refused at 458 calls on 2026-09-23 with `limit_source: openrouter_free_tier_daily` --
    so adding models buys nothing. What asking here buys is the seventeen hours a day AFTER the
    allowance is gone: they are now spent in the rule lane instead of on one refusal per row.

    -1 means UNMEASURED (the seat module could not be read), which is never treated as zero: an
    unreadable counter must not silence a lane that might be working.
    """
    try:
        from libs.ops import llm_seat
        left = int(llm_seat.free_budget_left())
        return left, (f"{left} free request(s) left today of a {llm_seat.free_daily_max()} "
                      f"ceiling ({llm_seat.calls_today()} used)")
    except Exception as exc:
        return -1, (f"seat budget UNMEASURED ({type(exc).__name__}): the lane runs rather than "
                    f"stand down on an unreadable counter")


if __name__ == "__main__":
    raise SystemExit(main())
