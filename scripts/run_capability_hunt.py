#!/usr/bin/env python3
"""CAPABILITY HUNT (L1.31) -- two model families hunt what is MISSING, and one builds it. Daily.

PRINCIPAL ORDER (2026-07-31): *"make sure quant does this every day, max ROI frequency, where
ChatGPT and Claude both hunt for what to add, what's missing, and implement it -- like now."*

WHAT THIS AUTOMATES. Every fence this desk owns audits things that EXIST: is the gate strict, is
the queue converting, is the cadence maxed. Nothing hunted for capabilities that were never
conceived -- those arrived only when a human asked "what else?" and a model went looking. That
made the desk's growth rate a function of how often the principal happened to ask. This organ
makes it a daily property of the system.

WHY TWO FAMILIES, NOT ONE RUN TWICE. A model cannot see its own blind spot: ask the same family
twice and the second answer is the first answer restated with more confidence. Agreement ACROSS
families (Claude and GPT-9) is evidence; agreement within one is style. So both propose
INDEPENDENTLY -- neither sees the other's answer -- and the synthesis step treats cross-family
agreement as the strongest signal available and cross-family DISAGREEMENT as the second
strongest (one family saw something the other could not).

WHY IT BUILDS, NOT JUST PROPOSES. A proposal nobody implements is the found-never-fixed defect
L1.28b exists to kill, and this desk's measured conversion rate makes a pure-proposal organ a
debt generator. So the third stage IMPLEMENTS the winner in the same run -- code, fence, law,
tests -- exactly as the principal's own sessions do.

THE PROMPTS ARE THE GENOME. They are written here, versioned, and improved by the deep sweep's
recursive-meta section like every other prompt on this desk.

    python scripts/run_capability_hunt.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():                                     # dev/CI checkout
    _ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "docs/research/capability_hunt"

#: The evidence every hunter reads first -- today's real gaps, not yesterday's impressions.
_CONTEXT = """Read these BEFORE proposing (they are today's measured state, regenerated hours ago):
  data/max_push_queue.json     every aspect not yet at 100%, ranked
  data/conversion_status.json  is the desk converting findings at all (L1.28b)
  data/calibration_status.json is the desk's own confidence scored (L1.29)
  data/replacement_rate.json   are validated edges being born faster than they die (L1.30)
  docs/research/TIER1_BENCHMARK.md   every layer's distance to tier-1 process
  docs/CONSTITUTION.md         the laws (skim L1.28a-c, L1.25a, L1.29-L1.31)
  docs/GAP_REGISTER.md + docs/research/recommendation_ledger.json   what is ALREADY known"""

_HUNT_BRIEF = """You are hunting for what would most RAISE THIS DESK'S LONG-TERM GEOMETRIC GROWTH
(max E[log wealth]) and its rate of VALIDATED ALPHA DISCOVERY -- the two supreme objectives.
Every proposal is judged by one question: how much validated compounding does it add, directly
or through what it multiplies? A new edge, a cheaper fill, a decorrelated sleeve, a faster
promotion path, a data asymmetry no competitor can buy -- all qualify; so does a capability whose
absence would let a live edge die uncaught. Aim at the GROWTH, not at the org chart.

{context}

THE BAR -- this is not a backlog-grooming exercise. Everything already in the ledger, the gap
register, or the max-push queue is OUT OF SCOPE by construction: those are known, owned, and
being worked. You are looking for the thing that is missing from the LIST ITSELF -- the question
nobody on this desk has asked, the failure mode no fence watches, the measurement whose absence
is invisible precisely because nothing reports it.

YOUR PRIMARY LENS THIS RUN (rotated -- see below). Push it to exhaustion FIRST, then sweep the
others briefly for anything it missed:

    >>> {lens} <<<

The full lens set (yours is above; the rotation guarantees the desk explores every region and
never re-draws from the same distribution twice running):
 1. INVERT A FENCE: every fence checks the desk did what it said. What checks whether what it
    SAID was true? (That reasoning produced L1.29 -- calibration -- and it was worth building.)
 2. FOLLOW A NUMBER NOBODY OWNS: name a quantity that determines terminal wealth and is computed
    NOWHERE. (That produced L1.30 -- replacement rate: births vs deaths of validated edges.)
 3. ASK WHAT A TIER-1 PROP DESK HAS THAT WE DO NOT -- Jane Street, XTX, Jump, DRW, Optiver, HRT,
    Wintermute; and RenTech/Medallion as the ceiling exemplar. Process, not capital.
 4. READ THE NEGATIVE EXEMPLARS: Alameda, LTCM, Archegos each died of something specific. Which
    of their deaths would this desk currently NOT detect in time?
 5. TIME-TRAVEL: it is 12 months from now and the desk failed. What was the cause, and what
    single capability would have caught it?
 6. CROSS-DOMAIN TRANSFER: take one idea from control theory, epidemiology, reliability
    engineering, information theory, or aviation safety that has no equivalent here.
 7. THE ADVERSARY: a competitor is trying to end this desk. What is their cheapest attack, and
    what would detect it? (Includes crowding into our own edges, venue-side adverse selection.)
 8. THE UNASKED QUESTION: what does this desk assume so deeply it has never written down? Find
    an assumption nobody has ever tested, and design the test.

OUTPUT (strict, and keep it SHORT -- one proposal, deeply argued, beats five sketched):
  MISSING CAPABILITY: <one line>
  WHY IT IS INVISIBLE TODAY: <what makes its absence unnoticeable>
  MECHANISM: <how it would work, concretely -- files, artifact, fence status values>
  WHAT IT WOULD HAVE CAUGHT: <a real incident from this desk's own record, cited>
  ROI: <direct + cascade, and what it multiplies>
  COST: <hours, maintenance, and what it competes with>
  FALSIFIER: <what evidence would prove this is NOT worth building>
Then one line: NOVELTY-CHECK: <grep/read command you ran proving this does not already exist>.
An honest "I could not find one that clears the bar, here is what I checked and why each failed"
is a VALID and useful answer -- padding the list with known items is a defect.

THEN, ALWAYS -- THE BRAINSTORM (breadth, principal 2026-07-31 "brainstorms too"). After the one
deep proposal, list EVERY additional high-ROI idea you can substantiate, one line each, no cap
and no minimum -- if there are twenty, write twenty; if the seam is thin, say so. Depth AND
breadth, never one at the cost of the other (L1.35). Each: IDEA -- mechanism/why it raises
growth -- rough ROI tier (S/A/B) -- where it routes (axis watchlist / ledger / a fence). These
are RAW GENERATION: they are not required to be novel-checked or built this run -- the builder
rows the strongest into the ledger for later screening, and screen-on-discipline decides. A run
that produces one deep proposal and an empty brainstorm has left growth ideas on the table.

THE BRAINSTORM IS ENDLESS AND MAY NEVER TERMINATE (L1.40, principal 2026-07-31: "maximum
aggressive, endless list of max-ROI ideas always"). There is no state in which this desk has
"enough ideas": generation sits at the top of every funnel, ideas are free, and screening is what
costs -- so the correct number of ideas is always MORE. Specifically: an empty or near-empty
brainstorm is a FAILED run, not a thin seam -- if your lens genuinely ran dry, SWITCH LENS mid-run
and keep generating rather than stopping. Never write a closing summary, never say "that covers
it", never rank-and-truncate to a comfortable number (L1.35). If you produced ten, the eleventh
exists -- go get it. The only legitimate stop is your context window, and when you hit it, say so
and name what you were about to write next so the following run resumes generating there."""

_BUILD_BRIEF = """You are the BUILDER stage of the capability hunt. Two independent model
families each proposed a missing capability. Read BOTH proposals:

--- PROPOSAL A (Claude family) ---
{a}

--- PROPOSAL B (GPT-9 family, independent) ---
{b}

ADJUDICATE with the desk's own discipline, then BUILD.
 1. If both families converged on the same capability, that is the strongest signal available --
    build it. If they diverged, judge on expected contribution to long-term compounding per unit
    of effort (L2.7), and say plainly why the loser lost; a divergence often means one family saw
    a blind spot the other could not, so check whether the loser is worth a ledger row.
 2. VERIFY IT DOES NOT EXIST before writing a line -- this desk's most common defect is building
    something already present but unwired. If it exists unwired, WIRE it; that is a better
    outcome than a new file.
 3. BUILD IT FULLY, in the desk's style: the script, its artifact, its status values (with an
    UNMEASURED/refusal path -- never let an unmeasured thing report OK), a law in
    docs/CONSTITUTION.md and ops/principal_doctrine.txt if it is a standing duty, the mapping in
    scripts/build_enforcement_matrix.py, a line in ops/crontab.manifest with EVIDENCE and
    CONFIDENCE, and TESTS that fail if the wiring is removed.
 4. RUN IT. If its first run reports a defect, that is success, not failure -- record it. If its
    first run reports OK on an empty measurement set, FIX THAT FIRST: unmeasured must never read
    as fine (L1.28a).
 5. Verify the tree: pytest on the suites you touched, build_enforcement_matrix (zero orphans),
    check_scheduler_manifest, check_timidity_language. Then commit and push to master with a
    message naming what was missing and what it would have caught.
 6. Row anything you deliberately did NOT build via scripts/recommendations.py, with the reason.
 7. IF THE WINNING PROPOSAL IS A DEFECT (a bug/flaw found by a defect lens): FIX IT IN THIS RUN,
    add the test that fails without the fix, and say what it would have cost. A found-unfixed bug
    is the L1.28b defect in its most expensive form. If the fix touches the money path, check
    scripts/check_change_window.py first -- inside a live window, stage improvements but ALWAYS
    proceed with repairs (L1.38).
 8. ALPHA CANDIDATES GET THE SAME TREATMENT AS CAPABILITIES (principal 2026-07-31: "this is what
    our system should always do, 6 times a day, with GPT and Claude both"). If the winning
    proposal is a TRADEABLE AXIS rather than an engine capability, its build IS its Stage-A
    screen: write the screen script + tests, schedule it in ops/crontab.manifest, run it, and
    record the verdict -- exactly as scripts/screen_funding_spread.py (R0115) and
    scripts/screen_collateral_allocation.py (R0120) were built. A candidate rowed but unscreened
    is the L1.39 idle defect; the screen is how "implement immediately" applies to an axis.
    NEVER size it -- Stage A earns a pre-registered forward clock, never capital (L1.6).

Write your session record to {report} (what both families proposed, what you built, what you
refused, what its first run said). If you cannot finish the build, the record IS the deliverable
and the next run resumes from it -- never leave a half-built capability unrecorded."""


#: THE LENS SET. Rotation is what makes repeated hunting EXPLORATION rather than repetition: six
#: runs of "use every heuristic" converge on the same region because the model's own priors
#: dominate; one deep lens per run forces genuinely different draws, and the rotation guarantees
#: every region is visited. Deterministic on (date, slot) so a resumed run keeps its lens and the
#: yield record stays attributable.
#: EVERY lens resolves to the same question -- "what raises long-term geometric growth of THIS
#: book?" -- because the supreme objective is max E[log wealth] and max validated-alpha rate
#: (principal 2026-07-31: "always use a similar question in exploration relative to the growth
#: and alpha-maxxing goal so we get maximum output of high-ROI ideas"). Two halves, alternating
#: by rotation: OFFENSIVE lenses hunt new growth directly (edges, data, capacity, compounding);
#: DEFENSIVE lenses protect the growth that exists (the failure that ends compounding is a
#: negative term in the same objective). Offense is listed first so a majority of daily draws
#: point at new alpha.
_ALPHA_LENSES: list[str] = [
    "NEW EDGE FAMILY -- name a mechanism class with a FORCED participant (liquidation cascades, "
    "index/ETF rebalances, funding-settlement flows, options-dealer gamma, stablecoin "
    "mint/redeem, miner/validator flows) that this desk has never screened, and the free data "
    "that would test it. Mechanism first, never a pattern.",
    "DATA ASYMMETRY -- information that could exist ONLY because of how WE combine data (our "
    "own-timestamp L2, our execution tape, cross-source joins). What proprietary feature is a "
    "competitor structurally unable to buy? (L1.11a: rank by reconstruction cost.)",
    "CAPACITY & COMPOUNDING -- what lets the book carry more risk-adjusted size or compound "
    "FASTER: a decorrelated sleeve, a cost-tier cut (every bp is pure CAGR), a funding-harvest "
    "cadence, a capacity band we are leaving on the table.",
    "REGIME-CONDITIONED EDGE -- an edge that exists only in a nameable, DETECTABLE regime "
    "(high-funding, high-vol, post-liquidation, low-liquidity) we could switch on and off. What "
    "regime do we not yet detect, and what edge would it gate?",
    "SMALL-CAPACITY FRONTIER -- an edge too small for a tier-1 desk to touch and therefore ours "
    "for free (L1.18a): a niche venue, a long-tail pair, an era archive, a language ecosystem. "
    "Which structurally-abandoned band are we not harvesting?",
    "FASTER PROMOTION -- what shortens the path from screen-hit to sized-capital without lowering "
    "a bar: an evidence accelerant (8h panels, event-density), a paper-sleeve auto-spawn, a "
    "resurrection-queue consumer. Time-to-alpha is a growth term.",
    # PRINCIPAL 2026-07-31: "find every crypto strat even discretionary n all n never limit to
    # just one thing." The lenses above all hunt NEW ground; none asked whether the ground already
    # walked is one family walked repeatedly. On the desk's record 41 buried candidates cluster
    # into 7 worked families out of 14, which no lens could have surfaced.
    "STRATEGY-FAMILY BREADTH -- UNLIMITED, ALL-SURFACE, NEVER-ENDING. No surface is out of scope: "
    "every venue, era, language, asset class, timeframe, format and STYLE (systematic, "
    "discretionary, manual, hybrid, market-making, event-driven). There is no terminal state -- "
    "'covered' and 'we already looked' are claims requiring a dated search with its residual gap, "
    "never defaults. No quota on families, findings or depth; a count is a quota in disguise. The "
    "only two limits are the licence gate and never installing third-party tooling, and neither "
    "is a scope limit. Concretely: read data/strategy_coverage.json and take a "
    "family marked NEVER-HUNTED or "
    "THIN, not one marked HUNTED. Coverage is DISTINCT FAMILIES, never candidates: twelve "
    "candidates from one family are correlated by construction, so they die together and the desk "
    "learns one thing while the log reports twelve tests. Name the family, the free data that "
    "would test it, and its forced participant. DISCRETIONARY-SHAPED FAMILIES COUNT -- "
    "level-reaction, session/calendar flow, positioning extremes: how a human discretionary "
    "trader actually decides is a mechanism class like any other, disqualified only for being "
    "unfalsifiable, never for being judgement-shaped.",
]
#: DEFECT LENSES (principal 2026-07-31: "all bugs flaws should always be hunted and fixed too").
#: The fences catch KNOWN defect classes; nothing hunted for the unknown ones. These lenses hunt
#: code, not governance -- and the hunt FIXES what it finds in the same run (L1.39), which is why
#: a defect draw is as valuable as an alpha draw: an undetected bug on the money path costs more
#: than a missed edge.
_DEFECT_LENSES: list[str] = [
    "READ-WITHOUT-WRITER -- find a key/file/artifact that code READS and nothing WRITES. This "
    "desk's most prolific defect class (the capital-event equity bug was exactly this). grep the "
    "readers, then prove a writer exists.",
    "SILENT-EXCEPT -- find an except/try that swallows a failure and lets the caller proceed as "
    "if it succeeded. A swallowed order error once stranded ~$2,150 of real inventory.",
    "UNMEASURED-REPORTED-AS-OK -- find a check or metric that returns a PASS/zero when its input "
    "was absent. Unmeasured must never read as fine (L1.28a); both fences built today shipped "
    "with this bug in their first run.",
    "STALE-CONSUMER -- find code reading an artifact without checking its age, so a frozen "
    "producer silently feeds yesterday's number into today's decision.",
    "DEAD-BRANCH / ZERO-CALLER -- find a function, flag or config knob nothing calls or passes. "
    "Built-never-wired is engineering already paid for returning zero (L2.9).",
    "BOUNDARY / OFF-BY-ONE -- find an inequality, window edge, timezone join or rounding step "
    "that is wrong at the boundary. Cross-source timestamp joins are the desk's repeat offender.",
]

_DEFENSIVE_LENSES: list[str] = [
    "INVERT A FENCE -- find the claim no fence tests for TRUTH (only for compliance).",
    "FOLLOW A NUMBER NOBODY OWNS -- a quantity that sets terminal wealth and is computed nowhere.",
    "TIER-1 PROCESS GAP -- what Jane Street/XTX/Jump/DRW/Optiver/HRT/Wintermute have and we do "
    "not, with RenTech/Medallion as the ceiling exemplar. Process, never capital.",
    "NEGATIVE EXEMPLARS -- Alameda, LTCM, Archegos: which of their deaths would this desk NOT "
    "detect in time, today?",
    "TIME-TRAVEL -- it is 12 months out and the desk failed. Name the cause and the one "
    "capability that would have caught it.",
    "CROSS-DOMAIN TRANSFER -- import one idea from control theory, epidemiology, reliability "
    "engineering, information theory, or aviation safety that has no equivalent here.",
    "THE ADVERSARY -- a competitor is trying to end this desk. Cheapest attack, and what detects "
    "it? Include crowding into our own edges and venue-side adverse selection.",
    "THE UNASKED QUESTION -- an assumption held so deeply it was never written down. Test it.",
]
#: 2:1 OFFENSE, so a majority of every day's 6 draws hunt NEW growth while the rest protect it.
#: Pattern A,A,D repeated: alpha lenses cycle (each ~twice per cycle), defensive lenses cycle
#: through all 8 across days -- so a 6-slot window is 4 offensive / 2 defensive, and over a few
#: days every lens of both kinds is drawn (yield stays measurable per lens).
def _build_lenses() -> list[str]:
    """Weave the three kinds so EVERY 6-slot day hunts new alpha, guards the desk, AND hunts bugs.

    Pattern per 6 slots: alpha, alpha, defect, alpha, defensive, defect -> 3 offensive / 2 defect
    / 1 defensive. Defect draws are weighted equal to defensive ones because an undetected bug on
    the money path costs more than a missed edge, and the fences only cover KNOWN defect classes.
    Deterministic and fully covering: each list cycles independently, so every lens of every kind
    is drawn as the days advance and per-lens yield stays measurable."""
    kinds = ("A", "A", "X", "A", "D", "X")                 # X = defect
    out: list[str] = []
    ai = di = xi = 0
    # CYCLE LENGTH 48, and the number is load-bearing -- a 24-slot cycle (the first version)
    # contained only 4 defensive slots, so 4 of the 8 defensive lenses were UNREACHABLE FOREVER:
    # half the defensive space silently dead while the rotation looked fair. 48 slots = 8
    # defensive draws (all 8 lenses), 24 alpha (4 full cycles of 6) and 16 defect (covers all 6).
    # Any future lens list must keep this invariant -- the coverage test pins it.
    for k in range(48):                                    # divisible by the 6-slot day
        kind = kinds[k % len(kinds)]
        if kind == "A":
            out.append(_ALPHA_LENSES[ai % len(_ALPHA_LENSES)])
            ai += 1
        elif kind == "D":
            out.append(_DEFENSIVE_LENSES[di % len(_DEFENSIVE_LENSES)])
            di += 1
        else:
            out.append(_DEFECT_LENSES[xi % len(_DEFECT_LENSES)])
            xi += 1
    return out


_LENSES: list[str] = _build_lenses()


def _lens_for(stamp: str, slot: int) -> str:
    """Deterministic rotation over (day, slot) with PROVABLE coverage: every lens is drawn within
    one 8-day cycle, and the same slot never repeats a lens day to day.

    THE BUG THIS FIXES (found by its own coverage test): the first version indexed on
    `int(stamp)`, so consecutive days were not consecutive integers -- 20260831 -> 20260901 jumps
    by 70, not 1. The rotation therefore skipped a chunk of the lens list at every month boundary
    and left several lenses effectively unreachable. A date ORDINAL makes day-to-day steps
    exactly +1, so 48 slots (6/day x 8 days) sweep the whole list with nothing dead."""
    try:
        d = datetime.strptime(stamp, "%Y%m%d").replace(tzinfo=UTC).date().toordinal()
    except ValueError:                                     # non-date stamp: degrade, never crash
        d = sum(ord(c) for c in stamp)
    return _LENSES[(d * 6 + slot) % len(_LENSES)]


def _record_yield(root: Path, entry: dict[str, object]) -> None:
    """Append-only hunt history -- so the desk can MEASURE which lens actually produces adopted
    capabilities and drop the ones that never do (the audit's own recursive-meta discipline,
    applied to exploration itself)."""
    p = root / "data/capability_hunt_history.json"
    try:
        hist = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        hist = {"runs": []}
    hist["runs"].append(entry)
    hist["runs"] = hist["runs"][-500:]
    p.write_text(json.dumps(hist, indent=2), "utf-8")


def _claude(prompt: str, timeout: int = 2400) -> tuple[bool, str]:
    r = subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check || { echo BRAIN_AUTH_FAILED; exit 90; } && '
         'claude --effort max --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")[-400:]


def _gpt(prompt: str) -> tuple[bool, str]:
    """The GPT-9 seat -- a genuinely INDEPENDENT model family, reusing the strategic director's
    provider chain (scripts/run_strategic_director.py:_ask, which never raises: a dead provider
    must not crash a cycle). Dormant until OpenRouter is funded, and it says so rather than
    silently degrading the hunt to one family."""
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    try:
        from scripts.run_strategic_director import MODEL, _ask
    except Exception as exc:
        return False, f"GPT seat unimportable: {exc}"
    text, err = _ask(prompt, MODEL)
    if err or not text.strip():
        return False, err or "empty response"
    return True, text


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write the prompts, call no model")
    ap.add_argument("--slot", type=int, default=0,
                    help="which daily slot this is -- selects the exploration lens")
    args = ap.parse_args()
    _OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    lens = _lens_for(stamp, args.slot)
    report = _OUT / f"{stamp}_s{args.slot}_hunt.md"
    brief = _HUNT_BRIEF.format(context=_CONTEXT, lens=lens)
    print(f"[hunt] slot={args.slot} lens={lens[:60]}...", flush=True)

    if args.dry_run:
        (_OUT / f"{stamp}_s{args.slot}_prompts.txt").write_text(
            brief + "\n\n=== BUILD ===\n" + _BUILD_BRIEF.format(a="<A>", b="<B>", report=report),
            "utf-8")
        print(f"[hunt] dry-run: prompts -> {_OUT}/{stamp}_s{args.slot}_prompts.txt")
        return 0

    # STAGE 1+2: both families propose INDEPENDENTLY -- neither sees the other's answer.
    ok_a, a = _claude(brief + "\n\nWork READ-ONLY: propose only, do not modify anything.", 1500)
    ok_g, b = _gpt(brief)
    if not ok_a:
        a = f"(Claude seat failed: {a[-300:]})"
    if not ok_g:
        # HONEST DEGRADATION: a dead GPT seat does not cancel the hunt -- it runs single-family
        # and SAYS SO, so the record never implies cross-family agreement that never happened.
        b = (f"(GPT-9 seat unavailable: {b}. This run is SINGLE-FAMILY -- treat its proposal as "
             "unconfirmed by an independent family, and note that in the record.)")
    (_OUT / f"{stamp}_s{args.slot}_proposals.md").write_text(
        f"# CAPABILITY HUNT PROPOSALS {stamp} slot {args.slot}\n\nLENS: {lens}\n\n"
        f"## A -- Claude family\n\n{a}\n\n"
        f"## B -- GPT-9 family (independent)\n\n{b}\n", "utf-8")

    # STAGE 3: adjudicate + BUILD. Proposal without implementation is the defect (L1.28b).
    ok_b, out = _claude(_BUILD_BRIEF.format(a=a, b=b, report=report), 3000)
    status = {"stamp": stamp, "slot": args.slot, "lens": lens,
              "claude_proposed": ok_a, "gpt_proposed": ok_g,
              "cross_family": ok_a and ok_g, "built": ok_b and report.exists(),
              "report": str(report), "generated": datetime.now(tz=UTC).isoformat()}
    (_ROOT / "data/capability_hunt.json").write_text(json.dumps(status, indent=2), "utf-8")
    _record_yield(_ROOT, status)
    print(f"[hunt] {json.dumps(status)}")
    if not ok_b:
        print(f"[hunt] builder tail: {out[-500:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
