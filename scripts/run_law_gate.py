#!/usr/bin/env python3
"""THE LAW GATE (L1.37) -- every law, enforced at every boundary, continuously.

PRINCIPAL ORDER (2026-07-31): *"make all these principles enforced 24/7 with every interaction
with anything."*

THE GAP THIS CLOSES, and it was large. Every fence this desk owns ran on a CRON TICK and nowhere
else. Between ticks -- and CI ran only pytest, with no git hooks at all -- a commit could land, a
push could ship, and an organ could spawn under a tampered constitution, a stripped doctrine, or
a broken law family, with nothing watching until the next scheduled run hours later. Laws were
enforced PERIODICALLY. This makes them enforced AT EVERY BOUNDARY:

    boundary                     mode      what it stops
    ------------------------------------------------------------------------------------------
    organ spawn (brain_env.sh)   --fast    an organ running under a tampered core or a doctrine
                                           that no longer carries the laws it is meant to obey
    git push (pre-push hook)     full      a breach leaving the box for master
    CI (every push + PR)         full      a breach entering the tree from anywhere
    hourly cron                  full      drift that arrives without a commit (state, artifacts)

TWO MODES, because a gate that is too slow to run at a boundary will be removed from it:
  --fast  (~1s, no subprocesses): the immutable-core seal + doctrine carries every family's laws.
          These are the two conditions under which an organ must NEVER be allowed to start.
  full    every fence, each in its own process, all failures collected and reported together --
          never first-failure-only, because a gate that hides four breaches behind one is a gate
          that gets run once and disbelieved.

REFUSAL IS THE DEFAULT. An unrunnable fence counts as a FAILED fence, never a skipped one: if
this gate cannot prove a law holds, it must not claim it does (L1.28a's rule applied to
enforcement itself).

    python scripts/run_law_gate.py [--fast] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: LAW FENCES -- portable. They read the REPO (constitution, doctrine, matrix, prompts, manifest),
#: so they mean the same thing in CI, in a fresh clone, and on the box. These gate every commit
#: and every push: a breach here is a breach anywhere.
_LAW_FENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check_constitution_core.py", ()),        # L2.8a -- the sealed core is intact
    # the index lock `Adopt-Release.ps1` already contends for: it either costs the adoption
    # window or parks the desk's state in an entry no organ pops. This fails on either key being
    # TRUE IN ANY SCOPE (not merely the effective one: a `true` a narrower scope happens to
    # override is one fresh clone away from winning) and on any stash entry existing at all.
    # UNSET is git's own default of false, so it passes and is reported UNPINNED rather than
    # failed -- a gate red on every clean clone is a gate that gets switched off (L1.43).
    # Portable: it reads git's own config and ref state, so it means the same in CI, a fresh
    # clone, on the VPS and on the box.
    ("check_autostash.py", ()),
    # PRODUCER BEFORE CONSUMER. build_enforcement_matrix WRITES data/enforcement_matrix.json and
    # check_law_families READS it; the matrix is gitignored (data/*), so on a VIRGIN tree the
    # consumer ran first against a file that did not exist yet. That is why this gate was green
    # on every machine that had run it before -- the box, a dev clone -- and RED on every clean
    # checkout: CI failed 10 consecutive times on master (30651154078..30654344515) with
    # "BREACH check_law_families.py (rc=2)" while the identical commit passed locally. Proven by
    # running the gate twice in a fresh worktree: first run FAIL, second run PASS, nothing
    # changed but the artifact the first run left behind. A gate whose verdict depends on
    # whether the machine happened to have run it before is not a gate in either direction.
    ("build_enforcement_matrix.py", ()),       # L2.0 -- no law is prose, no fence is an orphan
    ("check_law_families.py", ()),             # L1.36 -- families complete/fenced/reaching/guarded
    # L1.43 -- a cited enforcement that nothing EXECUTES leaves its law enforced by a docstring.
    # A LAW fence, not a state one: it reads scripts/, libs/ and the manifest, all committed, so it
    # means the same in CI, a fresh clone and on the box. Caught dist_shift.py (cited for L1.19 and
    # L2.10, importer count outside its own test: zero) on its first run.
    ("check_enforcement_execution.py", ()),
    # L1.28 -- every prompt surface, INCLUDING the charters/specs a dig prompt orders the organ to
    # read (one delegation hop still binds the organ; the count is read from the artifact, not
    # asserted here, because a hardcoded "all N surfaces" goes stale the first time one is added).
    ("check_timidity_language.py", ()),
    # --report-only: the LAW half is manifest<->repo integrity (exit 2). Live-crontab DRIFT
    # (exit 1) is BOX STATE -- on a red-parked box the manifest is *supposed* to be ahead of
    # the installed crontab until the puller vets the commit, so drift failing CI/pre-push
    # wedges the exact push that would heal it. The bare run lives in _STATE_FENCES.
    ("check_scheduler_manifest.py", ("--report-only",)),  # L1.28c -- every line is decided
    ("check_build_standard.py", ()),           # L1.41 -- nothing enters below standard
    ("check_sizing_derivation.py", ()),        # L1.41 -- no money number chosen by feel
    ("check_return_targeting.py", ()),         # handoff 2026-07-12 -- no CAGR target
    # L1.49/R0318 -- every hand-rolled extractor declares an invariant its own output must satisfy.
    # A LAW fence: it AST-walks libs/ and scripts/, all committed, so it means the same in CI, a
    # fresh clone and on the box. It is here because it was NOWHERE: built, tested, registered in
    # _GOVERNED, exempted from the scheduler on the grounds that it "reads SOURCE, not state,
    # exactly like check_sizing_derivation and check_return_targeting ... so the commit gate is the
    # information-arrival ceiling" -- and both named peers sit two lines above while this one had
    # zero invocation sites anywhere in the repo. The exemption cited a gate that never ran it.
    # data/enforcement_execution.json recorded it EXECUTED off a string literal in a dict in
    # build_enforcement_matrix.py, which invokes nothing -- crediting a mention as a run, the exact
    # error its own library refuses at extractor_invariants.py:201.
    ("check_extractor_invariants.py", ()),     # L1.49 -- 'it looks right' is not validation
    # --surfaces-only: the PORTABLE half (is the breadth mandate still on every hunting prompt?)
    # reads committed files, so it means the same in CI, a fresh clone and the box. The breadth
    # MEASUREMENT reads live coverage state no clean checkout has, so it runs in _STATE_FENCES --
    # a commit gate reporting BLIND on every PR is a gate that gets switched off (L1.43). Same
    # split as check_scheduler_manifest, and the half that belongs here is the right one: a
    # mandate leaves a prompt by an EDIT, so the edit is the moment to catch it.
    ("check_strategy_breadth.py", ("--surfaces-only",)),  # L1.32 -- never limit to one family
    # §36/L2.9 -- a new object must be BORN with its properties, judged at the boundary where its
    # author still exists. These predicates already ran, at 07:00 on cron and nowhere else, so an
    # unclaimed doc or an unwired script was always found hours later by a session that had to
    # reconstruct from cold why the file existed; four defect keys recurred that way for weeks
    # (commit 9f3e2fcf: "fix artifact-ungoverned that MY OWN commit introduced"). Portable by
    # construction -- it reads docs/, scripts/ and the tracked decision ledger, and judges only
    # what git TRACKS, so it means the same in CI, a fresh clone and on the box.
    ("check_birth_properties.py", ()),
    # EVERY OBLIGATION IS INHERITED, NOT REMEMBERED (LAWS 7, principal 2026-09-23). The same
    # shape as the line above, widened from documents and scripts to the five axes on which this
    # desk keeps acquiring obligations: an executable needs a clock, an artifact, a named consumer
    # and a row in the runtime attestation; a source needs a position in the collection chain; a
    # family needs to be inside the judge's derived coverage; a region arrives at the CURRENT
    # depth and breadth floors, never at zero; a destructive path arrives guarded against acting
    # on an absence. It derives each set from the tree and fails on the axis that REGRESSED,
    # naming the thing that arrived incomplete -- so a thing created next month inherits the
    # obligation instead of waiting for a session to remember it.
    ("check_birth_obligations.py", ()),
    # FIX THE CLASS, ON A CLOCK, OR IT IS NOT FIXED (LAWS 7, principal 2026-09-23). The twin of
    # the line above: that one stops a new thing arriving incomplete, this one proves every KNOWN
    # defect class still carries a detector, a repair, a fence and fresh evidence -- and ratchets
    # down the count of classes a human still has to find.
    ("check_self_repair.py", ()),
    # GROWTH GOVERNANCE (principal 2026-09-04): every risk-reduction mechanism proves it raises
    # robust forward E[log W]; every strong opportunity may raise capital above normal; the
    # 20% floor is flat and filled, growth free above it to 30%; the gateway deploys the book.
    ("check_growth_governance.py", ()),
    # NO QUOTA ON FORWARD EVIDENCE SLOTS, EVER (principal 2026-09-23). The portable half:
    # AST-walks the enrolment path and fails when a cap comes back -- a quota constant, a slice
    # of the certificate roster, a `len(enrolled) >= n` gate, or `forward_reconcile.family_budget`
    # declaring itself an enrolment cap again. A forward clock gathers evidence and deploys no
    # capital, so a cap bought no safety; the multiplicity and trial accounting are untouched and
    # this fence checks none of them. The state half runs in _STATE_FENCES.
    ("check_forward_enrolment.py", ("--surfaces-only",)),
    # THE TIER-5 INSTITUTION AUDIT (principal's two blueprints, 2026-09-22): every section of
    # the COMPLETE TIER-5 BLUEPRINT (I-CII) and the FINAL MAXIMUM-AGGRESSIVE mandate (1-170),
    # classified EXISTS+WIRED+LIVE / DORMANT / PARTIAL / MISSING / DUPLICATIVE /
    # REFUSED_CONSERVATIVE. The fence is that the audit cannot claim what the tree does not
    # hold: a LIVE row must cite a file that exists, a clock this repo knows and an artifact,
    # and a REFUSED_CONSERVATIVE row must carry the sentence saying whose aggressiveness it
    # would have cut. Portable: it reads only tracked files.
    ("check_tier5_audit.py", ()),
    # THE PLUMBING-INVARIANT HIERARCHY (Tier-1 B26). Not "are the money-path laws tested" --
    # they always were -- but WHAT EACH TEST SPEAKS FOR: one hand-written state (EXAMPLE), a
    # generator's draws (PROPERTY), or the whole finite domain (PROOF). The fence is that the
    # ledger cannot lie: every enforcing node must exist, carry its `def`, and be COLLECTED.
    # `--no-collect` is deliberately NOT passed: a test that no longer imports is exactly the
    # state this catches (L1.49, a gate that never ran).
    ("check_plumbing_invariants.py", ()),
    # IMMUTABLE EVALUATOR: research organs may change the hypothesis, never the judge.
    ("check_immutable_evaluator.py", ()),
    # THE EVOLVABLE / IMMUTABLE BOUNDARY (LAWS 5m): an evolvable organ's change set may not
    # touch a rail. Re-uses the evaluator's seal (one manifest, reported beside its own
    # verdict) and adds what a hash cannot see: the meta-evolution layer's lineage ledger
    # and the evolved-commit rule. Portable: the rails are code, the ledger optional.
    ("check_immutable_rails.py", ()),
    # THE OPEN-SOURCE RESEARCH FEDERATION (LAWS 5h, principal 2026-09-17). The PORTABLE half:
    # the roster, the vocabularies, the sandbox policy, the packet contract that cannot carry
    # a verdict, and the admission rule that collapses a fork storm into one lineage. The
    # live half (dispositions, schedules, watermarks, stranded data) needs desk state and
    # runs in _STATE_FENCES with --require-state.
    ("check_external_federation.py", ()),
    # THE BIRTH FENCE FOR EXECUTABLES (LAWS 7, principal 2026-09-17). Every executable python
    # file carries a ComponentSpec, the registry may not lie about itself (no missing code path,
    # no required component without a schedule), the count of executables with no clock may only
    # FALL, and no second registry (clock_fixer.RESIDENTS, moat_swarms.TASK_NAMES,
    # forests.FOREST_TASKS) may disagree with the specs. Portable: it reads the tree and the
    # manifest, so it means the same in CI, a fresh clone and on the box.
    ("check_component_registry.py", ()),
    # PRODUCTIVITY IS PROVEN OR IT IS NOT CLAIMED (external reviewer, 2026-09-23). The component
    # registry above proves every executable has a CLOCK; this proves the desk still knows which
    # producers turn that clock into CELLS. It fails on two things only -- a stale or missing
    # census, and a producer that burned compute past the stated window with no unique cell and
    # no named blocker -- and deliberately NOT on low productivity, because cutting the tail of
    # the search distribution is exactly the reduction in aggressiveness the desk refuses.
    ("check_productivity_census.py", ()),
    # EVERY PRODUCER OWES CELLS (LAWS 7, principal 2026-09-23). The census above asks whether a
    # producer ever paid; this asks what reached the ONE JUDGE in the last day and HOW ORTHOGONAL
    # it was -- cells emitted, unique after dedup, cells to the judge, and the marginal effective
    # rank each producer added, so a hundred copies of one momentum rule score as one cell's worth
    # of breadth. Fails on a producer owing with no declared exemption and no named blocker, on
    # the owing count RISING, and on throughput to the judge falling below its own best with no
    # stated reason. Ratchets fall only and nothing here caps a producer: the remedy for a barren
    # organ is to make it produce or retire it with a reason, never to throttle a working one.
    ("check_producer_yield.py", ("--cells-only",)),
    # NO EXEMPTION WITHOUT A FALSIFIER (2026-09-24). The two fences above let a producer pass by
    # DECLARING itself exempt -- and until this landed, an exemption was a sentence with no
    # condition under which it stops being true. `module_rent`'s 21 rows (plus two borrowed
    # registries) could excuse an organ from the rent ledger forever, and the neighbouring
    # ledger, docs/research/productivity_blockers.json, carried `retire_if` on every exemption
    # with nothing reading the field. So the structure whose whole purpose is that no module
    # exists for free was the one structure that could never be wrong. This holds both
    # registries to the same rule: every exemption names the MEASURED condition that deletes it.
    # --schema-only is the PORTABLE half -- it reads the module source and the docs ledger, so it
    # means the same in CI, in a fresh clone and on the box; which declarations have actually
    # expired needs desk artifacts and is published every day by the module_rent leg instead.
    # It disables nothing and caps nothing: the point is to delete stale excuses, not work.
    ("check_exemption_falsifiers.py", ("--schema-only",)),
    # THE GRID FILLS, AND ONLY AN EXHAUSTED LIST MAY STOP IT (principal 2026-09-23). The yield
    # fence above asks how orthogonal what reached the judge was; this asks whether the desk is
    # still CLAIMING ground it has never tested. Occupied cells of the family x instrument x
    # horizon grid ratchet up, and the filler must end a pass because the targets ran out --
    # never because a clock or a count did. Measured cause: `independence_intake` minted 8 cells
    # an hour into 8,418 reachable empty ones under a cap of 400, and the limit was an unindexed
    # `WHERE grid_cell=?` scan in libs/moat/registry.py, 0.927 s per cell, which no artifact
    # named. Every number here is a floor; nothing caps, and no bar moves.
    ("check_grid_occupancy.py", ()),
    # ONE CERTIFICATE TRUTH (principal 2026-09-22). One writer (external_gauntlet.py), one
    # authority file (UNIVERSAL_SURVIVORS.json), one consumer (promoter.py); every derived store
    # -- survivors ledger, sleeve registry, shadow/lane states, sleeves.json, forward_reconcile --
    # must agree with it, banned-family (discovered) certificates and clocks are residue, and the
    # fence fails on any divergence. Without desk state it reads UNMEASURED and passes; the
    # state half below requires the state.
    ("check_certificate_truth.py", ()),
    # THE RUNTIME ATTESTATION IS ABOUT ONE HOST (a GitHub reviewer, 2026-09-23). The committed
    # docs/research/runtime_state.json must name the machine it measured and be internally
    # consistent about it -- a document claiming one host while the measurement inside it came
    # from another is the exact lie the organ exists to prevent, so this half fails everywhere
    # and needs no desk state. Its freshness is judged only on the host it names (below).
    ("check_runtime_attestation.py", ()),
    # NOTHING IS RETIRED ON AN ABSENCE (LAWS 7, 2026-09-23). Every pass in this tree that REMOVES
    # rather than reports is inventoried with the reference it judges against, every guarded one
    # is proved from the AST to call `libs/ops/reference_freshness.require_live_reference`, every
    # guarded reference has a lease or a recorded cadence derivation, and the unguarded count
    # ratchets DOWN only. Measured cause: `certificate_truth --apply` retired 837 rows against a
    # canon holding n=0 and 46.7h stale. Portable: it reads the tree and one tracked module, so a
    # fresh clone and the box get the same answer; no desk state required.
    ("check_no_retirement_on_absence.py", ()),
    # REGIONAL PARITY (LAWS 5n, principal 2026-09-19). No region absent: every regional forest
    # resolves a country pack or runs a dedicated region package. Depth, coverage debt and the
    # Priority = P(useful) x Orthogonality x InformationGain x CoverageDebt / (Compute +
    # DataCost + TrialBurden) are MEASURED and published for research_roi to fold in as a bonus;
    # this fence caps no compute and the artifact says so in `caps_compute`. Portable: the packs
    # are code, so the depth half means the same in CI and on the box, and the live half
    # (resident, discovery window, lattice) reads UNMEASURED without the registry rather than
    # failing. `--strict` promotes the live flags and belongs in the hourly box gate, not here.
    ("check_regional_parity.py", ()),
    # EVERY REGION'S CELLS AND JUDGED CELLS RATCHET UP (principal 2026-09-23: equal maximum depth
    # per region, "like it's their native country quants"). `check_regional_parity` asserts the
    # federation has no absent region; this asserts the OUTPUT of those regions never falls back.
    # It fails on a region that once held cells and now holds none, on a fall in the count of
    # regions the desk NAMES, and on a fall in a measure's total -- never on a non-zero dip, which
    # is reported. Portable: it reads `REGION_RATCHET.json` and an absent artifact is UNMEASURED
    # here; the state half rides in _STATE_FENCES with --require-state.
    ("check_region_ratchet.py", ()),
    # THE RECOMMENDATION LANE MUST DRAIN (principal 2026-09-23). Every OPEN ledger row names an
    # owner and a next action, and the OPEN backlog ratchets DOWN only. Portable: the ledger and
    # the ratchet are tracked, so both halves mean the same in CI, a fresh clone and on the box.
    # The STALENESS half is state and rides in _STATE_FENCES with --require-state.
    ("check_recommendation_flow.py", ()),
    # THE UNCRAWLED SET MUST FALL (principal 2026-09-23). `research/coverage_drain.py` measures
    # the gap between the ground the desk could lawfully hold and the ground it has actually
    # fetched, and this ratchets it: the OVERDUE backlog and the oldest wait may fall and never
    # rise, the cumulative drained count may rise and never fall. The headline uncrawled count
    # may rise ONLY in a pass that registered new lawful ground -- seeding what the registry had
    # never heard of is the organ's first duty and a fence that punished it would teach the next
    # session to stop. Portable: without the report it reads UNMEASURED and passes, and the
    # box half rides in _STATE_FENCES with --require-state.
    ("check_coverage_drain.py", ()),
    # THE JUDGE TESTS 100% OF WHAT THE DESK MINES (principal 2026-09-23). `research/
    # judge_coverage.py` allocates the hour by UNJUDGED BACKLOG per family and interleaves the
    # docket so every prefix the sealed gauntlet reaches carries every family holding one. This
    # ratchets it: a family with unjudged cells and no place in the queue FAILS, a family that
    # drained nothing it already held FAILS, and a family whose oldest unjudged cell sits past
    # twice its own drain window FAILS. The ratchet is on the CARRIED cohort, never on raw
    # backlog -- raw backlog rises when the miners outrun the judge, which is mining working,
    # and a fence that punished it would be switched off inside a week. Portable: without the
    # report it reads UNMEASURED and passes; the box half rides in _STATE_FENCES.
    ("check_judge_coverage.py", ()),
    # THE WRITE-OR-EXPLAIN CONTRACT IS STILL WIRED (2026-09-23). Eight failures in one day shared
    # one shape: an organ that produced nothing was indistinguishable from an organ with nothing
    # to produce. `libs/ops/write_or_explain.py` stats each leg's DECLARED artifact either side of
    # the leg at the one boundary every leg passes through, and names the three outcomes --
    # LEG_FAILED (loud, with the exit code and stderr), SILENT_NO_OP (exited 0, wrote nothing,
    # said nothing) and DECLARED_NO_OP (nothing to write, and said so). PORTABLE HALF: this reads
    # the cycle source and fails if the two call sites are gone, so an edit that quietly removes
    # the contract reddens CI on a fresh clone. A contract nothing calls is the same defect one
    # layer up. The live half rides in _STATE_FENCES.
    ("check_write_or_explain.py", ("--wiring-only",)),
    # NO WRITE FAILS IN SILENCE (2026-09-23 swallowed-write audit). A handler that is BLIND (no
    # `as exc`) and MUTE (body is only `pass`) around a call that puts bytes on disk discards the
    # only evidence the artifact is missing -- the registry verdict sync stranded 3,368 verdicts
    # exactly this way, and `donate` swallowing `register` is why 0 of 107 sampled donation rows
    # carry a prereg hash. RATCHETED TO FILE WRITES, which the audit took from 10 to 0: the class
    # is fenced at zero so it cannot regress, while the 25 pre-existing DONATION findings stay
    # reported rather than dumped red into another lane (L1.43).
    ("check_bare_excepts.py", ("--file-writes-only",)),
)

#: STATE FENCES -- box-only. They measure LIVE STATE (artifacts, ledgers, organ freshness) that
#: exists solely on the VPS, so in CI or a fresh clone their "failure" means "this machine has no
#: desk state", not "a law was broken". Running them as a commit gate would make the gate cry
#: wolf on every PR, and a gate that cries wolf gets disabled -- which is how enforcement dies.
#: They run in the hourly box gate, where their verdict is real.
_STATE_FENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check_conversion.py", ()),               # L1.28b -- FLATLINE fails
    # EVERY SOURCE COLLECTED AND CONVERTED (principal 2026-09-23, "make sure they are always
    # collected, 100% exploited and converted"). Two ratchets that may only fall -- sources never
    # collected, and sources collected whose cells never reached the gauntlet -- plus the oldest
    # never-collected source against its own cadence window. A FALLING backlog is never a breach;
    # this fails on the direction, never on the size, so it can never be an argument for
    # collecting less. State, because it reads the drain ledger the box writes.
    ("check_source_drain.py", ()),
    # NOTHING IS PARKED (principal 2026-09-23, "nothing should be queued in the research system,
    # all immediate tested"). Fails when any queue's oldest row is older than ONE CYCLE of the
    # organ that owns it, when a queue has open rows and no drainer at all, or when rows carry no
    # enqueue timestamp so their age cannot be measured (L1.28a). It ships RED on purpose: the
    # first census measured 63,110 rows waiting and a 654 h oldest row, and a fence tuned to pass
    # on today's backlog would pin that backlog in place (L1.43).
    ("check_no_queues.py", ()),
    ("check_universe_integrity.py", ()),       # bars: corrupt is quarantined, stale named
    ("check_external_federation.py", ("--require-state",)),   # LAWS 5h -- the live half
    # LAWS 5h / L1.32 -- the SANDBOX half: no runnable federated system goes a rotation window
    # without the hour (the ROI ratchet that starves a frontier), and no UNMEASURED reason sits
    # unchanged for a week while its install task moves nowhere. A settled
    # PERMANENTLY_UNAVAILABLE row with its exact error and its named cover is an answer, not a
    # stall, and passes.
    ("check_sandbox_liveness.py", ()),
    ("check_exploration.py", ()),              # L1.32 -- no exploration organ gone dark
    ("check_calibration.py", ()),              # L1.29 -- no ungraded past-due forecast
    ("check_strategy_breadth.py", ()),         # L1.32 -- the breadth MEASUREMENT
    ("run_organ_er.py", ()),                   # L1.32 -- no organ left in coma
    ("check_replacement_rate.py", ()),         # L1.30 -- births vs deaths
    ("check_change_window.py", ()),            # L1.38 -- money-path freeze windows
    ("check_scheduler_manifest.py", ()),       # L1.28c state half -- live crontab drift (rc=1)
    ("check_mechanism_attribution.py", ()),    # L1.6 -- no survival on unexplained P&L
    ("check_organ_liveness.py", ()),           # L1.28c -- every organ actually produces
    # L1.28c, THE SEAT HALF -- every configured intelligence seat donates on ITS OWN cadence.
    # A seat with no clock is UNMEASURED and counted, never a silent pass; a seat clocked on the
    # other host is UNMEASURED_HERE and named; the overdue debt is DECLARED by seat name and may
    # only shrink, so a newly dark seat fails this immediately.
    ("check_seat_health.py", ()),
    # L1.49, THE LEG HALF -- every leg of the hourly cycle actually REACHES its own clock.
    # Measured 2026-09-23 from the compute ledger: 19 of 112 CORE_LEGS had never executed once,
    # because `main()` is a 325-leg straight line inside a 40-minute task and the tail was
    # structurally unreachable -- `clock_liveness`, `clock_ledger`, `fill_recorder` and
    # `evidence_chain` among them. A leg that never runs raises no error and writes no artifact,
    # so it is indistinguishable from a leg with nothing to do; this fails on `never_run` and on
    # `outside_window` by NAME rather than letting either be inferred from silence. It can only
    # ever demand that more legs run: there is no threshold here that attempting less can satisfy.
    ("check_leg_rotation.py", ()),
    # THROUGHPUT IS A RATCHET (2026-09-23). The desk's canonical write door was measured at FOUR
    # rows a second -- 345,600 a day at a 100% duty cycle against a target of millions -- and it
    # broke nothing: every row landed, every gate passed, a 231.9 ms table scan per write simply
    # set the desk's whole mint rate. A ceiling is invisible because it is not a failure, so this
    # fails on its behalf when any stage of mint -> judge falls below its own high-water mark.
    # It can only ever demand MORE rows per second; there is no threshold here that minting or
    # judging less can satisfy. State, because it reads the hourly THROUGHPUT.json.
    ("check_throughput_ratchet.py", ()),
    ("check_promotion_gate.py", ()),           # L1.6 -- expansion is bought with evidence
    ("check_excitation.py", ()),               # L1.45 -- no absorbing set, no dead experiment
    ("check_clock_provenance.py", ()),         # L1.46 -- the tape declares which clock stamped it
    ("check_heat_floor_wiring.py", ()),        # growth governance -- the 20% floor is DEPLOYED
    # GROWTH GOVERNANCE Rule 1, THE COST DIRECTION WITH NO ALARM (principal 2026-09-23, "just in
    # case we dismissed edges net based on overcharged false costs"). An UNDERCHARGED cell
    # manufactures a survivor and every gate here exists to catch it; an OVERCHARGED cell dies in
    # the gauntlet silently and leaves no artifact anywhere. This fence compares what the model
    # CHARGES against what the broker QUOTES and what the account has PAID, fails on a NEW
    # overcharged symbol or a RISING commission overcharge, and lowers its own declaration when
    # the debt shrinks. A STATE fence: the measurement needs the terminal, so a box without one
    # reads UNMEASURED, which is a real answer and not a pass by silence.
    ("check_cost_truth.py", ()),
    # L1.5 / L2.10, THE OTHER DIRECTION. check_cost_truth catches the desk charging itself MORE
    # than the venue; this one catches a LIVE sleeve charged LESS -- the direction that
    # manufactures survivors. It was written 2026-08-29 and never referenced by this gate or by
    # ops/gates.sh, so it returned rc=2 for weeks and blocked nothing (LAWS 7: unwired is a
    # defect). Its ruler was repointed 2026-09-23 from the H1 bar spread STAMP to the broker's
    # own quote in reports/COST_TRUTH.json, because the stamp samples the widest instant of its
    # hour and overstated the executable book by orders of magnitude (EURUSD 12 pts stamped
    # against a live and 44,640-bar-M1 median of 0.0). Thresholds unchanged. A STATE fence: with
    # no COST_TRUTH.json it reads NOT-READABLE-HERE, which is a real answer about the HOST.
    ("check_cost_surface.py", ()),
    # L1.5 / L1.28a, THE THIRD DIRECTION AND THE SILENT ONE. The two fences above compare a
    # charge against a quote; both need a charge to EXIST. Measured on the trading box
    # 2026-09-24: 13 of 355 LIVE clocks carried NO cost_fields AT ALL -- 8 of them XAUUSD,
    # covering the asia, london_am and afternoon gold windows, which are essentially the desk's
    # entire realised P&L. A null cost is not a zero cost: shadow_forward line 758 falls through
    # to LIVE re-measured costs, so the basis moves under the clock every pass and nothing says
    # so. One more LIVE row had its family and selector TRANSPOSED, which breaks every join the
    # canonical identity (symbol|family|selector) exists to make. Both came from the one
    # freeze() caller that omitted cost_fields. NO RATCHET, deliberately -- the defect is a LIVE
    # row on the money path and the residue is thirteen rows, not a debt in someone else's file.
    # A STATE fence: no registry on this host reads NOT-READABLE-HERE, a verdict about the HOST.
    ("check_live_sleeve_cost.py", ()),
    # THE STATE HALF of the enrolment law: no certificate clockless past one cycle. An absent
    # FORWARD_ENROLMENT.json is UNMEASURED, which is a real answer on a clean checkout.
    ("check_forward_enrolment.py", ("--state-only",)),
    # NO FORWARD CLOCK IS EVER FROZEN OR STALE (principal 2026-09-23). The enrolment fence above
    # asks whether a certificate HAS a clock; this one asks whether that clock is still MOVING --
    # a different defect and the silent one, because a clock stops when its identity leaves the
    # certificate canon while its ledger row survives reading ACTIVE, and nothing raises. It
    # fails while any clock is FROZEN past its OWN window (counted in the venue's open bars, so
    # a weekend is not a freeze), while the frozen count sits above its ratchet floor, or while
    # CLOCK_LIVENESS.json is stale. A STATE fence: off the trading box the report is absent and
    # the verdict is UNMEASURED, which is a real answer about the host and not a pass.
    ("check_clock_liveness.py", ()),
    # LAWS 5c -- everything ingested is exploited; the exploitation floor ratchets UP, the
    # DATA STRANDING count ratchets DOWN, and no qualified datum sits in storage without a
    # defined downstream state. A STATE fence: on a clean checkout the ingestion artifact is
    # absent and the verdict is UNMEASURED, which is a real answer and not a pass.
    ("check_ingestion_exploitation.py", ()),
    # LAWS 5b -- every mined row ends as a testable cell or a recorded, reasoned refusal. The
    # CONVERSION DEBT (rows that are neither) ratchets DOWN and may never be raised, including
    # by hand: the enforced ceiling is min(ceiling, lowest_ever). A STATE fence for the same
    # reason as the line above -- a checkout with no registry reads UNMEASURED, which is a real
    # answer and not a pass.
    ("check_conversion_debt.py", ()),
    # the live half of ONE CERTIFICATE TRUTH: on the box an absent authority file is a defect
    ("check_certificate_truth.py", ("--require-state",)),
    # the live half of THE PRODUCTIVITY CENSUS: on a host with desk state, NO census is the leg
    # not running, and a census older than its window is the same fact arriving late. The
    # portable half above passes with UNMEASURED on a clean checkout, where there is nothing to
    # judge; here there is, and an absent scoreboard is the defect it looks like.
    ("check_productivity_census.py", ("--require-state",)),
    # the live half of THE RUNTIME ATTESTATION: on the host that publishes it, an attestation
    # older than its own cadence means the hourly leg has stopped and the committed file has
    # quietly become a photograph of the past -- which is worse than no file, because it still
    # reads as current runtime state to anyone on GitHub.
    ("check_runtime_attestation.py", ("--require-state",)),
    # the live half of REGIONAL PARITY (LAWS 5n): on the box the registry IS open and the forest
    # reports DO exist, so "no resident", "no discovery in the trailing window" and "no candidate
    # in the lattice" are measured absences and the law calls each one a defect. It still caps no
    # compute -- it fails the gate and publishes the debt; the allocator does the rest.
    ("check_regional_parity.py", ("--strict",)),
    # the live half of THE REGION RATCHET: on the box the registry IS open and
    # `attribution_census` runs hourly, so an ABSENT `REGION_RATCHET.json` is an organ that did
    # not run (L1.49) rather than a fresh clone, and it fails here.
    ("check_region_ratchet.py", ("--require-state",)),
    # NOTHING IS STALE (principal 2026-09-22). Every artifact the desk publishes has an expected
    # refresh interval -- its lease, else its declared artifact_class, else DERIVED from its
    # organ's cadence and recorded -- and one past it is a DEFECT named with its organ, its clock
    # and its last exit. A STATE fence: it reads the live artifact set, and UNMEASURED is a
    # verdict rather than a pass. Repairs are raised through the EXISTING control-plane
    # reconciler (observe -> plan -> apply_plan), never by a fixer of the fence's own, and the
    # per-artifact ratchet is suspended -- and says so -- while every MT5 clock on the box is
    # disabled, because that is one administrative fact and not 100 separate defects.
    ("check_no_staleness.py", ()),
    # the live half of the recommendation lane: on the box the implementer leg runs hourly, so a
    # ledger past its own cadence means the drain has stopped rather than "this machine has no
    # desk state" -- which is exactly the 281.7-hour silence this fence was built for.
    ("check_recommendation_flow.py", ("--require-state",)),
    # the live half of the coverage drain: on the box the `coverage_drain` leg runs hourly, so an
    # absent or stale COVERAGE_DRAIN.json means the drain stopped -- which is the state the
    # `sources_ingested` stage was already in when this organ was written (148 uncrawled, oldest
    # waiting 134 hours, and nothing owning the number).
    ("check_coverage_drain.py", ("--require-state",)),
    # the live half of judge coverage: on the box the `judge_coverage` leg runs hourly at intake,
    # so an absent or stale JUDGE_COVERAGE.json means the allocation stopped and the judge is
    # back to re-testing whichever families the docket happens to put first -- the exact state
    # the 120,000-verdict measurement found (18% of the judge on a family banned from capital,
    # the three largest mined populations barely judged at all).
    ("check_judge_coverage.py", ("--require-state",)),
    # THE PLUMBING MAY NOT STOP SILENTLY (principal 2026-09-23). The `plumbing_watchdog` leg
    # proves by OBSERVATION every fifteen minutes that the adoption clock exists and is enabled
    # with a next run inside the hour, that HEAD descends from the branch tip it should have
    # adopted, that the git-writer lock can be TAKEN right now, that no orphaned pool worker is
    # holding commit, that every declared task is present, that each producer/consumer pair
    # agrees about its path, and that every registered fence has run. This gate refuses to pass
    # while any of those defects is older than its own escalation window -- and an ABSENT
    # watchdog report is itself such a defect, because a watchdog that stopped is the quietest
    # failure the desk can have: no defects reported, because nothing looked.
    ("check_plumbing_watchdog.py", ()),
    # THE ADOPTION ITSELF, JUDGED DIRECTLY (2026-09-24). The watchdog above reaches the same
    # defect, but only through three hops -- it must be RUNNING, it must re-stamp `age_s`, and
    # `adoption_lag` must then sit past a six-hour escalation window before the gate arm reddens.
    # Measured the night the box fell 443 commits behind: every one of those hops held, and the
    # gate was still green while a full night of shipped work sat on origin unexecuted. This one
    # reads the adoption's OWN heartbeat -- `started_at` with no `finished_at` is a run the
    # scheduler killed, which is a positive fact rather than an inferred silence -- and fails on
    # no success within three cadences, on a run that outlived the task's execution limit, and on
    # HEAD behind origin past the same grace. It caps nothing and gates no capital; it fails when
    # the machine that trades is not running the code that was shipped to it. A host with neither
    # the task nor any adoption artifact is NOT_APPLICABLE and passes saying so, so CI, a fresh
    # clone and the VPS stay green (L1.43) -- but on the box, no evidence is UNMEASURED and
    # UNMEASURED fails, because no evidence is exactly what the outage looked like (L1.28a).
    ("check_adoption_freshness.py", ()),
    # on a schedule and whose artifact no production file reads is BURNING -- an orphan the desk
    # pays compute for every hour -- and the BURNING count ratchets DOWN only. The clock half is
    # exact (the four scheduler planes), so BURNING is the one population this census may fence
    # on; UNREACHED and NO_CLOCK rest on a consumer heuristic that under-reports and stay report-
    # only, because fencing on them would licence deleting organs nobody has proved are dead.
    # The two repairs are to name a consumer or retire the organ with a reason -- never to mask a
    # timer or trim a budget, which would be a reduction in aggressiveness with no E[log W] proof.
    # Portable: it reads the tree and the manifest, so it means the same in CI and on the box.
    ("check_dead_architecture.py", ("--ratchet",)),
    # THE MONEY BRAIN PRODUCED, PROVED AND PUBLISHED THIS CYCLE (principal 2026-09-23). The heat
    # fence above asks whether the FLOOR is deployed; this one asks whether the allocator RAN at
    # all, whether its certificate is still alive, whether each input it conditioned on is inside
    # its own clock, and whether a cycle that could not complete left a NAMED stand-down instead
    # of nothing. Written because a probe read two absent paths -- `data/pf_allocation.json` and
    # `desks/mt5/reports/ALLOCATOR_PROOF.json`, neither of which the allocator writes -- and
    # concluded the allocator was dead while both real artifacts were minutes old. A STATE fence:
    # a host that has never run the allocator reads UNMEASURED, which is a fact about the host.
    ("check_allocator_liveness.py", ()),
    # THE WRITE-OR-EXPLAIN CONTRACT, LIVE HALF (2026-09-23). Reads the contract ledger every leg
    # boundary appends to and sentences the desk on the latest row per leg: SILENT_NO_OP (exited
    # clean, wrote nothing, named no reason), LEG_FAILED/LEG_TIMEOUT, and NEVER_OBSERVED -- a leg
    # that declares an artifact and produced no row at all, which is how `ground_depth` and
    # `independence_intake` sat at ZERO ledger rows on the trading box while both ran perfectly by
    # hand. It also publishes `desks/mt5/reports/WRITE_OR_EXPLAIN.json`. State, because an absent
    # ledger means "no cycle has run here", not "a law was broken" -- and --require-state makes
    # that absence fail on the box, where a missing ledger means the contract never ran at all.
    ("check_write_or_explain.py", ("--require-state",)),
    # WHAT THE HOURLY ADOPTION IS ABOUT TO EAT (failure 8 of 2026-09-23). `MT5-AdoptRelease` lands
    # the branch's tree in place at :12 and keeps only STATE paths, so an uncommitted CODE edit --
    # or one committed here but never pushed -- is reverted with no error and a tree that looks
    # like nobody ever edited it. This names those paths while they can still be saved. It never
    # touches the tree: committing on a builder's behalf, with four builders live, would be a
    # worse failure than the one it reports. State, because it measures a working tree.
    ("check_box_reversion.py", ("--require-git",)),
)


def fast_gate(root: Path | None = None) -> dict[str, Any]:
    """The organ-spawn gate: the two conditions under which no organ may ever start.

    Deliberately in-process and dependency-free -- it runs before EVERY organ, so anything
    slower would be deleted from the spawn path the first time someone profiled a cycle."""
    root = root or _ROOT
    failures: list[str] = []

    # 1. THE SEALED CORE. An organ running under a tampered constitution is worse than no organ.
    try:
        r = subprocess.run([sys.executable, str(root / "scripts/check_constitution_core.py")],
                           capture_output=True, text=True, timeout=60, cwd=root)
        if r.returncode != 0:
            failures.append(f"CORE-SEAL: {(r.stdout + r.stderr).strip()[:200]}")
    except (OSError, subprocess.TimeoutExpired) as exc:
        failures.append(f"CORE-SEAL unrunnable ({exc}) -- counts as FAILED, never skipped")

    # 2. THE DOCTRINE CARRIES EVERY FAMILY. What reaches the organ is, since the 2026-08-25
    #    consolidation, the doctrine PLUS docs/LAWS.md (ops/brain_env.sh concatenates them into
    #    the appended system prompt), so the family check reads the same concatenation; if a
    #    family's laws are missing from it, that organ is about to run without them (L2.3).
    try:
        from scripts.check_law_families import FAMILIES
        doctrine = (root / "ops/principal_doctrine.txt").read_text("utf-8", errors="ignore") \
            + (root / "docs/LAWS.md").read_text("utf-8", errors="ignore")
        for fam, (members, _fence, _prevents) in FAMILIES.items():
            missing = [m for m in members if m not in doctrine]
            if missing:
                failures.append(f"DOCTRINE-GAP: family '{fam}' missing {missing} -- an organ "
                                "spawning now would never be told these laws")
    except Exception as exc:
        failures.append(f"DOCTRINE-CHECK unrunnable ({exc}) -- counts as FAILED")

    return {"mode": "fast", "ok": not failures, "failures": failures,
            "generated": datetime.now(tz=UTC).isoformat()}


def _dirty(root: Path) -> list[str]:
    """Files that differ from HEAD, tracked or not. Empty means the tree IS HEAD."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []                          # no git -- nothing to reconcile against, judge in place
    return [ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()] \
        if out.returncode == 0 else []


#: A lawgate HEAD checkout CANNOT outlive its own run: the re-exec is capped at timeout=1800 and
#: the `worktree add` at 300, so ~35min is the ceiling on a live one. Two hours is >3x that, which
#: keeps the reaper off a sibling law gate that is merely slow -- the only way to be wrong here is
#: to delete a checkout still being read, so the threshold is deliberately far past the maximum.
_ORPHAN_AFTER_S = 2 * 60 * 60


def _is_tmpfs(path: Path) -> bool:
    """True only when `path` demonstrably sits on a tmpfs. Unknown reads as False.

    Longest-prefix match against /proc/mounts, the way the kernel resolves it. Unknown must NOT
    read as tmpfs: the consequence of a wrong True is relocating a checkout onto a path that may
    not exist on a host this gate has never seen, and this gate's verdict must never depend on
    where its scratch landed.
    """
    try:
        lines = Path("/proc/mounts").read_text("utf-8").splitlines()
    except OSError:
        return False
    best, fstype = "", ""
    for line in lines:
        parts = line.split()
        if len(parts) > 2 and str(path).startswith(parts[1]) and len(parts[1]) > len(best):
            best, fstype = parts[1], parts[2]
    return fstype == "tmpfs"


def _checkout_base() -> Path:
    """Where a HEAD checkout is allocated: DISK, never RAM.

    THE DEFECT THIS CLOSES (gap-fixer 2026-08-29). `_reap_stale_checkouts` below already knows
    this checkout lands on a tmpfs -- its own docstring says "150MB of tmpfs owned by no
    process" -- and answered by reaping it after two hours. That treats the symptom. Measured
    this cycle the checkout is 297MB, it has DOUBLED since that note was written, and the box
    has 3815MB with ZERO swap: one law gate on a dirty tree claims ~50% of typical free RAM for
    its whole run, and a reaper cannot help while the run is legitimately alive. Four of these
    were allocated inside thirty minutes on this box.

    Disk is the correct home for a throwaway checkout and there is 12GB of it. `~/.cache` is the
    conventional place, is outside the repo (a checkout INSIDE it would show up in `git status`
    and is the mass-deletion launder R0423 names), and is verified not to be a tmpfs itself
    before it is used. Any failure -- no HOME, unwritable, or itself in RAM -- falls back to
    `tempfile.gettempdir()`, which is exactly today's behaviour, so this can only improve.
    """
    try:
        base = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "quant-lawgate"
        if _is_tmpfs(base.parent if not base.exists() else base):
            return Path(tempfile.gettempdir())
        base.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError):
        return Path(tempfile.gettempdir())
    return base


def _reap_stale_checkouts(root: Path, *, now: float | None = None) -> int:
    """Delete lawgate HEAD checkouts left by runs that DIED before reaching their own cleanup.

    THE DEFECT THIS CLOSES (R0407 one producer further on). `_at_head` allocates a 150MB detached
    worktree under /tmp and `full_gate` removes it in a `finally` -- which covers every path the
    interpreter walks out of, and NOT the one that actually leaks: SIGKILL. A law gate killed by
    the OOM killer never runs `finally`, so its checkout becomes 150MB of tmpfs owned by no
    process, and tmpfs is never reclaimed under pressure. That closes a loop on itself: low memory
    makes the kill likelier, the kill orphans another 150MB, and the next run starts poorer. Two
    such orphans (300MB, both clean, neither open by any process) were measured on 2026-08-13 with
    MemAvailable at 270MB against a 400MB floor -- the box could not have run its own test suite.

    WHY THE REAPER LIVES HERE AND NOT IN THE FENCE. `max_audit.check_host_memory_headroom` watches
    total /tmp occupancy and deliberately deletes NOTHING, because /tmp is shared with the live
    executor, three recorders and several concurrent agent sessions, and reaping another process's
    scratch mid-run is a worse failure than the one it fixes. That reasoning is right, and it is
    exactly why the cleanup belongs to the PRODUCER: this function touches only the `lawgate-head-`
    prefix it alone creates, and only past a lifetime a live run cannot reach. A watcher of a
    shared resource cannot safely free it; the process that allocated it can.

    Best-effort by construction. A reaper that raised would turn a disk-hygiene problem into a
    refused push, and the law gate's verdict must never depend on whether /tmp was tidy.
    """
    now = now if now is not None else time.time()
    reaped = 0
    # BOTH bases, always. The gate RE-EXECS HEAD's copy of itself, so an older HEAD still
    # allocates under gettempdir() -- and every orphan that predates the move lives there too.
    # Sweeping only the new base would strand exactly the pile this relocation exists to stop.
    candidates: list[Path] = []
    for base in {_checkout_base(), Path(tempfile.gettempdir())}:
        try:
            candidates.extend(base.glob("lawgate-head-*"))
        except OSError:
            continue                        # unreadable base is not this gate's verdict to fail
    candidates.sort()
    for d in candidates:
        try:
            if not d.is_dir() or now - d.stat().st_mtime < _ORPHAN_AFTER_S:
                continue
        except OSError:
            continue                        # vanished under us -- a concurrent reaper is fine
        subprocess.run(["git", "worktree", "remove", "--force", str(d / "t")],
                       cwd=root, capture_output=True, text=True, timeout=120, check=False)
        shutil.rmtree(d, ignore_errors=True)
        reaped += 1
    if reaped:
        # Leave no stale registration behind: `git worktree list` would keep naming a path that
        # no longer exists, and a later `worktree add` at the same path then fails outright.
        subprocess.run(["git", "worktree", "prune"], cwd=root, capture_output=True,
                       text=True, timeout=120, check=False)
    return reaped


def _at_head(root: Path) -> tuple[Path, str, list[str]]:
    """(where to run, what that place IS, why it is not HEAD). A pristine checkout when dirty.

    THE DEFECT THIS CLOSES (R0402). laws_only exists for CI and the pre-push hook, both of which
    judge COMMITTED state -- and both read the shared working tree instead. On this box that is
    not a technicality: sibling sessions build continuously in the same checkout, and on
    2026-08-05 the gate returned rc=2 on nine scripts "scheduled by the manifest but absent from
    the repo" where every one of those manifest lines existed ONLY in another session's
    uncommitted ops/crontab.manifest. `git show HEAD:ops/crontab.manifest` had zero occurrences.
    So the pre-push hook refused EVERY push on this box for a breach owned by somebody else's
    unsaved files, and the only way out was --no-verify -- which trains the desk to bypass its
    own law gate, the exact "a gate that cries wolf gets disabled" death L1.37 rule 1 names.

    A CLEAN TREE IS ALREADY HEAD, so the checkout is paid for ONLY when the verdict would
    otherwise be wrong: CI and a fresh clone are untouched and cost nothing extra.
    """
    dirt = _dirty(root)
    if not dirt:
        return root, "cwd==HEAD (tree clean)", []
    _reap_stale_checkouts(root)             # sweep our own dead before allocating another 150MB
    tmp = Path(tempfile.mkdtemp(prefix="lawgate-head-", dir=_checkout_base()))
    wt = tmp / "t"
    try:
        r = subprocess.run(["git", "worktree", "add", "--detach", str(wt), "HEAD"],
                           cwd=root, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise OSError((r.stderr or r.stdout).strip()[:200])
    except (OSError, subprocess.SubprocessError) as exc:
        # NEVER silently fall back to the dirty tree: the whole point is that the verdict names
        # its own subject. Judging in place is still better than no verdict, but it is REPORTED.
        shutil.rmtree(tmp, ignore_errors=True)
        return root, f"cwd (HEAD CHECKOUT UNAVAILABLE: {exc}) -- verdict covers UNCOMMITTED work", \
            [f"head-checkout-unavailable: {exc}"]
    return wt, f"HEAD in a detached worktree ({len(dirt)} file(s) dirty in cwd, excluded)", []


def full_gate(root: Path | None = None, *, laws_only: bool = False,
              in_place: bool = False) -> dict[str, Any]:
    """Every fence, all failures collected. Never first-failure-only.

    laws_only=True runs the portable LAW fences alone -- the correct mode for CI and the
    pre-push hook, where live desk state does not exist and its absence is not a breach. It also
    judges HEAD rather than the working tree (R0402), because that is what those two boundaries
    are actually gating; pass in_place=True to judge the tree as it sits.

    The HEAD run RE-EXECS this script from the checkout, so the fence LIST is HEAD's too. A gate
    that judged HEAD's files against the working tree's roster would be a third artifact, which
    is the same confusion one layer down.
    """
    root = root or _ROOT
    in_place = in_place or os.environ.get("QUANT_LAWGATE_IN_PLACE") == "1"
    if laws_only and not in_place:
        where, subject, why = _at_head(root)
        if where != root:
            try:
                # RECURSION IS SUPPRESSED BY ENV, NOT BY A FLAG, and the difference is
                # load-bearing: the checkout is of HEAD, which may predate this very code. An
                # unknown --in-place makes an older copy die in argparse with empty stdout (this
                # bug, hit on the first run); an unknown env var is ignored, and an older copy
                # then does exactly what it always did -- judge in place, no recursion possible.
                env = {**os.environ, "QUANT_LAWGATE_IN_PLACE": "1"}
                r = subprocess.run([sys.executable, str(where / "scripts/run_law_gate.py"),
                                    "--laws-only", "--json"], cwd=where, env=env,
                                   capture_output=True, text=True, timeout=1800)
                rep = json.loads(r.stdout)
                rep["subject"] = subject
                return rep
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                why = [f"head-gate-unrunnable: {exc} -- counts as FAILED, never skipped"]
                return {"mode": "laws", "ok": False, "n_fences": 0, "n_failed": len(why),
                        "failures": why, "results": [], "subject": subject,
                        "generated": datetime.now(tz=UTC).isoformat()}
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(where)],
                               cwd=root, capture_output=True, text=True, timeout=120)
                shutil.rmtree(where.parent, ignore_errors=True)
        head_note, head_why = subject, why
    else:
        head_note, head_why = ("cwd (in-place: the working tree as it sits)"
                               if laws_only else "cwd (full gate judges LIVE state)"), []
    battery = _LAW_FENCES if laws_only else _LAW_FENCES + _STATE_FENCES
    results, failures = [], []
    for script, extra in battery:
        p = root / "scripts" / script
        if not p.exists():
            failures.append(f"{script}: MISSING -- an absent fence is a failed fence")
            results.append({"fence": script, "ok": False, "detail": "missing"})
            continue
        try:
            r = subprocess.run([sys.executable, str(p), *extra], capture_output=True,
                               text=True, timeout=600, cwd=root)
            ok = r.returncode == 0
            tail = (r.stdout or r.stderr or "").strip().splitlines()
            results.append({"fence": script, "ok": ok, "rc": r.returncode,
                            "detail": tail[-1][:200] if tail else ""})
            if not ok:
                failures.append(f"{script} (rc={r.returncode}): "
                                f"{tail[-1][:160] if tail else 'no output'}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"fence": script, "ok": False, "detail": f"unrunnable: {exc}"})
            failures.append(f"{script}: UNRUNNABLE ({exc}) -- counts as FAILED, never skipped")
    failures += head_why
    return {"mode": "laws" if laws_only else "full", "ok": not failures,
            "n_fences": len(battery), "subject": head_note,
            "n_failed": len(failures), "failures": failures, "results": results,
            "generated": datetime.now(tz=UTC).isoformat()}


#: HOW LONG A FENCE'S VERDICT STANDS, and therefore how long the rotation has to reach every
#: fence in the battery. MEASURED, not chosen for comfort: `full_gate` gives each of the 53
#: fences up to 600 s, so one battery can cost eight hours and no hourly window can hold it --
#: which is exactly why `data/law_gate.json` on the trading box was 270 h old with 14 of 53
#: fences in it, and why every green claim the desk made rested on a gate that had not run.
#: A fence whose verdict is older than this window is DROPPED from the record, so the watchdog
#: reports it as never run. That is the measurement (L1.49), never a failure of the record.
ROTATION_WINDOW_H: float = 48.0

#: The longest a single fence may hold the rotation, matching `full_gate`'s own per-fence bound.
ROTATION_FENCE_TIMEOUT_S: float = 600.0

#: The least budget a fence may be started with. Below this the pass ends instead of starting a
#: fence it cannot let finish.
_ROTATION_FLOOR_S: float = 120.0


def _run_fence(root: Path, script: str, extra: tuple[str, ...],
               timeout: float) -> dict[str, Any]:
    """One fence, one verdict. An absent or unrunnable fence FAILS, it is never skipped."""
    p = root / "scripts" / script
    if not p.exists():
        return {"fence": script, "ok": False, "detail": "missing"}
    try:
        r = subprocess.run([sys.executable, str(p), *extra], capture_output=True,
                           text=True, timeout=timeout, cwd=root)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"fence": script, "ok": False,
                "detail": f"unrunnable: {exc} -- counts as FAILED, never skipped"}
    tail = (r.stdout or r.stderr or "").strip().splitlines()
    return {"fence": script, "ok": r.returncode == 0, "rc": r.returncode,
            "detail": tail[-1][:200] if tail else ""}


def _record_age_s(row: dict[str, Any], now: datetime) -> float:
    """Seconds since this fence last ran; infinite when the record cannot be read."""
    try:
        return (now - datetime.fromisoformat(str(row.get("ran_at")))).total_seconds()
    except (TypeError, ValueError):
        return float("inf")


def rotate_gate(root: Path | None = None, *, budget_s: float = 1800.0,
                now: datetime | None = None) -> dict[str, Any]:
    """THE WHOLE BATTERY, IN ROTATION, INSIDE A STATED WINDOW.

    The full battery does not fit an hourly window, and a gate that cannot fit its window does
    not run at all -- which is how the box reached 270 h with no battery record. This mode runs
    the fences that have gone longest without a verdict until the budget is spent, then MERGES
    them into `data/law_gate.json` so the record carries every fence with the time it ran.

    Three properties the record must keep, because the whole point is that it can be cashed:

      EVERY FENCE NAMES ITS OWN HOUR.  Each row carries `ran_at` and `elapsed_s`, so "the gate
      is green" can always be answered with "measured when?".

      THE WINDOW IS STATED AND ENFORCED.  A verdict older than ROTATION_WINDOW_H is dropped,
      not carried forward -- a fence that stops running disappears from the record within the
      window and is reported as never run.

      NOTHING IS EVER SKIPPED FOR BEING SLOW.  Oldest-first ordering means a slow fence cannot
      be starved by fast ones: it only ever climbs the queue.
    """
    root = root or _ROOT
    t0 = now or datetime.now(tz=UTC)
    # One entry per fence SCRIPT, carrying every argument set the battery declares for it (the
    # same script rides both batteries with different flags; the record is keyed by name because
    # `check_fences_ran` asks by name).
    declared: dict[str, list[tuple[str, ...]]] = {}
    for script, extra in (*_LAW_FENCES, *_STATE_FENCES):
        declared.setdefault(script, []).append(tuple(extra))
    prior: dict[str, dict[str, Any]] = {}
    try:
        doc = json.loads((root / "data/law_gate.json").read_text("utf-8"))
        rec = doc.get("fences") if isinstance(doc, dict) else None
        if isinstance(rec, dict):
            prior = {str(k): dict(v) for k, v in rec.items() if isinstance(v, dict)}
    except (OSError, ValueError):
        prior = {}
    due = sorted(declared, key=lambda n: (-_record_age_s(prior.get(n, {}), t0), n))
    ran: list[str] = []
    for name in due:
        left = budget_s - (datetime.now(tz=UTC) - t0).total_seconds()
        # A FENCE IS NEVER JUDGED ON A TRUNCATED CLOCK. Measured on the first rotation pass:
        # check_enforcement_execution was started with 32 s of budget left, timed out, and was
        # recorded as FAILED -- a verdict about the budget wearing the costume of a verdict about
        # the desk. Below the floor the pass simply ends and the fence stays at the head of the
        # queue for the next one.
        if ran and left < _ROTATION_FLOOR_S:
            break
        started = datetime.now(tz=UTC)
        rows = [_run_fence(root, name, extra,
                           min(ROTATION_FENCE_TIMEOUT_S, max(_ROTATION_FLOOR_S, left)))
                for extra in declared[name]]
        bad = [r for r in rows if not r["ok"]]
        row = dict(bad[0] if bad else rows[0])
        row["ok"] = not bad
        row["n_invocations"] = len(rows)
        row["ran_at"] = started.isoformat()
        row["elapsed_s"] = round((datetime.now(tz=UTC) - started).total_seconds(), 1)
        prior[name] = row
        ran.append(name)
    t1 = datetime.now(tz=UTC)
    window_s = ROTATION_WINDOW_H * 3600.0
    fences = {n: r for n, r in prior.items()
              if n in declared and _record_age_s(r, t1) <= window_s}
    results = [fences[n] for n in sorted(fences)]
    failures = [f"{r['fence']} (rc={r.get('rc', '?')}): {r.get('detail', '')}"
                for r in results if not r.get("ok")]
    missing = sorted(n for n in declared if n not in fences)
    failures += [f"{n}: no verdict inside the {ROTATION_WINDOW_H:.0f}h rotation window -- "
                 f"a gate that never ran is a claim the desk cannot cash (L1.49)"
                 for n in missing]
    return {"mode": "rotation", "ok": not failures, "n_fences": len(declared),
            "subject": f"cwd (rotation judges LIVE state; {ROTATION_WINDOW_H:.0f}h window)",
            "n_failed": len(failures), "failures": failures, "results": results,
            "fences": fences,
            "rotation": {"window_h": ROTATION_WINDOW_H, "budget_s": budget_s,
                         "ran_this_pass": ran, "n_recorded": len(fences),
                         "n_declared": len(declared), "never_recorded": missing,
                         "oldest_ran_at": min((str(r.get("ran_at")) for r in results),
                                              default=None)},
            "generated": t1.isoformat()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="organ-spawn gate: sealed core + doctrine carries every family")
    ap.add_argument("--laws-only", action="store_true",
                    help="portable law fences only -- for CI and the pre-push hook, where live "
                         "desk state does not exist and its absence is not a breach")
    ap.add_argument("--in-place", action="store_true",
                    help="judge the working tree as it sits instead of HEAD. --laws-only judges "
                         "HEAD by default because that is what a push and CI actually gate; this "
                         "is the escape hatch, and the re-exec inside the HEAD checkout uses it")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rotate", action="store_true",
                    help="run the OLDEST fences until --budget-s is spent and merge them into "
                         "data/law_gate.json: the battery costs hours and no clock window holds "
                         "it, so it rides a rotation whose window is stated in the record")
    ap.add_argument("--budget-s", type=float, default=1800.0,
                    help="seconds of fence time one rotation pass may spend (default 1800)")
    args = ap.parse_args()
    if args.fast:
        rep = fast_gate()
    elif args.rotate:
        rep = rotate_gate(budget_s=args.budget_s)
    else:
        rep = full_gate(laws_only=args.laws_only, in_place=args.in_place)
    if not args.fast:
        (_ROOT / "data/law_gate.json").write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        head = "LAW GATE" + (" (fast)" if args.fast
                             else f" -- {rep.get('n_fences', 0)} fences")
        rot = rep.get("rotation")
        if isinstance(rot, dict):
            head += (f" [rotation: {len(rot.get('ran_this_pass') or [])} ran this pass, "
                     f"{rot.get('n_recorded')} of {rot.get('n_declared')} inside "
                     f"{rot.get('window_h')}h]")
        print(f"{head}: {'PASS' if rep['ok'] else 'FAIL'}")
        # The verdict NAMES ITS OWN SUBJECT (R0402): "PASS" is meaningless until you know which
        # artifact passed -- HEAD, or a working tree three sessions are writing to right now.
        if not args.fast and rep.get("subject"):
            print(f"  judged: {rep['subject']}")
        for f in rep["failures"]:
            print(f"  BREACH  {f}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
