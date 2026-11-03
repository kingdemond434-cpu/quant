"""Every organ declares what it must PRODUCE, and is judged on that, not on exit code 0.

WHY THIS EXISTS. Four separate failures on 2026-09-11, all with the same shape -- the organ
reported success and did nothing, and no artifact contradicted it:

  * MT5-Universe returned result 1 on every run for an unknown number of days; the expander
    never completed and the registry repair chained behind it never ran at all.
  * dashboard_relay logged "relay pass complete" every three minutes over a desk_state.json
    that had not moved in 149 minutes -- the scp was failing and the error went to a log
    another instance held open.
  * shadow_health reported `missing_sleeves: 0` while 87 lanes sat retired, because from its
    own point of view nothing was missing: it had retired them.
  * MT5-Gateway, MT5-DeskState and MT5-Healers all returned 0xC0000142 with no log at all,
    because the process never started.

And the same thing measured in the wild: in AI-Hypercomputer/xpk an hourly triage workflow
logged 6,290 successful runs and zero agent executions. Its gating search matched nothing,
every time. Green pipeline, no work.

THE RULE. "It ran" and "it did something" are different facts, and a task result only ever
answers the first. So each organ names an ARTIFACT and a MAX AGE: the contract is satisfied
when that file exists and is younger than the age its own cadence implies. A task that exits 0
without refreshing its artifact is FAILING and says so, and a task that exits non-zero while
its artifact is current is fine -- which matters, because several organs here legitimately
return non-zero as a verdict rather than as an error.

WHAT THIS IS NOT. It is not a scheduler and it does not restart anything: it is a VERIFIER, and
keeping it separate from the thing it judges is the whole point. It writes
`desks/mt5/reports/organ_contract.json` and prints a table.

    python ops/organ_contract.py            # report
    python ops/organ_contract.py --json     # the artifact only
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "organ_contract.json"

#: organ -> (artifact it must refresh, max age in minutes, what the artifact is FOR)
#: The age is the organ's cadence with room for one missed run: an organ on a 15-minute clock
#: is late at 40, not at 16, because a single slow pass is not a defect and an alarm that cries
#: at every slow pass gets muted, which is how a real one goes unseen.
CONTRACTS: dict[str, tuple[str, int, str]] = {
    # THE GATEWAY RUNS AS MT5-GatewayResident (box_tasks.manifest, 2026-09-23): MT5-Gateway has
    # been Disabled since 2026-09-16 and is the superseded registration. Contracting the retired
    # name made the one organ that moves money read DISABLED or NOT_SCHEDULED on every pass while
    # the resident task wrote gateway_state.json every ten minutes -- a permanent false alarm on
    # the row an operator must never learn to scroll past.
    "MT5-GatewayResident": ("desks/mt5/data/gateway_state.json", 10,
                            "the pass state the executor writes every loop"),
    "MT5-AccountState":   ("desks/mt5/data/account_state.json", 45,
                           "the live equity the dashboard's account panel reads"),
    "MT5-DeskState":      ("web/desk_state.json", 45,
                           "the dashboard payload itself"),
    "MT5-AllocatorFast":  ("desks/mt5/reports/pf_allocation.json", 90,
                           "the book the gateway sizes from"),
    "MT5-StallWatch":     ("desks/mt5/data/stall_watch.json", 90,
                           "the organ-health snapshot"),
    "MT5-Shadow":         ("desks/mt5/reports/shadow/shadow_health.json", 180,
                           "forward-lane health and enrolment counts"),
    "MT5-Gauntlet":       ("desks/mt5/reports/UNIVERSAL_SURVIVORS.json", 240,
                           "the certificate registry"),
    # MIS-ATTRIBUTED UNTIL 2026-09-11, and the mistake was mine. `gauntlet_build_cursor.json` is
    # written by scripts/external_gauntlet.py -- MT5-Gauntlet -- not by the hourly cycle, so this
    # row held MT5-Hourly responsible for an artifact it does not produce and reported it FAILING
    # at 357m while the cycle was running normally. A contract that names the wrong artifact
    # manufactures a defect, which is worse than having no contract: it spends attention and
    # teaches the reader to distrust the board.
    #
    # The cursor's staleness WAS a real signal, just about a different organ -- the gauntlet was
    # re-testing one head of the docket forever because the rotation key never advanced. That is
    # now its own row below, where it can be read as what it is.
    "MT5-Hourly":         ("desks/mt5/data/events.jsonl", 180,
                           "every research leg appends here; silence means no leg ran"),
    # NOT A TASK, AND NAMING IT LIKE ONE COST A PERMANENT FALSE ALARM. There is no
    # `MT5-Gauntlet-Rotation` in the scheduler and there never was: rotation is a PROPERTY of
    # MT5-Gauntlet, measured by whether its build cursor advances. Because process_health joins
    # contracts to scheduled tasks by name, this row reported NOT_SCHEDULED -- "this organ cannot
    # run at all" -- on every single pass, about an organ that runs hourly and is healthy.
    #
    # The suffix makes the ownership explicit while keeping the signal, which is real and was
    # being drowned by the false half: a cursor that stops advancing means the docket has stopped
    # rotating and the tail is never reached, which is how 11,146 cells sat deferred forever.
    "MT5-Gauntlet (rotation)": ("desks/mt5/data/hypotheses/gauntlet_build_cursor.json", 240,
                                "which symbols the gauntlet last BUILT -- a stale cursor means "
                                "the docket has stopped rotating and the tail is never reached. "
                                "Owned by MT5-Gauntlet; this is not a task of its own"),
    "MT5-Universe":       ("desks/mt5/data/universe/universe.json", 1440,
                           "the symbol registry the whole hypothesis lane reads"),
    "MT5-LocalConvert":   ("desks/mt5/data/hypotheses/local_candidates.json", 180,
                           "deterministic row -> candidate conversion"),

    # THE E8 PROP ORGANS, CONTRACTED 2026-09-13 -- and the gap they close is one I made.
    #
    # The comment below says every organ built on 2026-09-12 was UNCONTRACTED on the day it was
    # written. So was every organ I built for the prop account, and I wrote that comment. The
    # board listed E8-Book, E8-Executor and E8-Spreads under "unwatched: 12 organ(s) with no
    # artifact contract" -- the three organs that decide what a $100,000 funded account trades.
    #
    # An uncontracted organ is not merely unmonitored. If E8-Executor stops, the book stops
    # placing and NOTHING SAYS SO: the guard keeps reporting the account is within its drawdown,
    # which it trivially is when no order has been sent, and a 5-day speed floor bleeds away
    # against a 2% daily cap that strips what it does not use. The failure and the healthy state
    # produce the same artifact. That is the E8 version of `live: 0`.
    #
    # Budgets are the task's own cadence plus one period of slack, so a single skipped run is not
    # an alarm and two are.
    "E8-Executor":        ("desks/mt5/reports/E8_EXEC.json", 15,
                           "five-minute certified FX evaluation, broker guard and position "
                           "management"),
    "E8-Gold":            ("desks/mt5/reports/E8_GOLD.json", 15,
                           "the mirrored Fusion gold windows actually sent, or refused and why"),
    "E8-Book":            ("desks/mt5/reports/E8_BOOK.json", 180,
                           "hourly venue-listed, positive-risk certified sleeve selection"),
    "MT5-HourlyCore (replication)": (
        "desks/mt5/reports/REPLICATION.json", 180,
        "independent certificate and forward replay required by the live door; "
        "detect missed hourly refreshes before its six-hour evidence expiry"),
    "E8-Spreads":         ("desks/mt5/reports/E8_SPREADS.json", 120,
                           "the venue cost sample the executor's spread fence refuses against"),
    # NO E8-Guard ROW, AND REMOVING IT IS THE POINT. I added one earlier tonight naming
    # `E8_GUARD.json`, and both halves were wrong: there is no `E8-Guard` task in the scheduler,
    # and that artifact has never existed. The guard is a PROPERTY of E8-Executor -- its verdict
    # rides inside `E8_EXEC.json` under `guard`, which is where the executor reads it before
    # sending. Contracting it as a task would have reported NOT_SCHEDULED on every pass about an
    # organ that runs hourly and is healthy, which is exactly the mistake recorded ten lines above
    # for `MT5-Gauntlet-Rotation`. Writing the same bug twice in one file in one night is the
    # argument for reading a file's own scar tissue before adding to it.
    # THE ORGANS BUILT 2026-09-12. Every one was UNCONTRACTED on the day it was written, which is
    # the gap that lets a new organ stop without anyone noticing -- exactly the class the
    # principal asked to end. A contract is the difference between an organ and a hope.
    "MT5-DataAxis":       ("desks/mt5/reports/DATA_AXES.json", 180,
                           "which free data axes this box can actually reach"),
    "MT5-AxisIngest":     ("desks/mt5/reports/AXIS_INGEST.json", 1560,
                           "reachable axes turned into dated series a family can condition on"),
    "MT5-CEODocket":      ("desks/mt5/reports/CEO_DOCKET.json", 1560,
                           "the daily ranked proposals the frontier scout produced"),
    "MT5-NeverStale":     ("desks/mt5/reports/NEVER_STALE.json", 60,
                           "the watchdog's own reading -- if THIS goes stale nothing is watching"),
    "MT5-ProcessHealth":  ("desks/mt5/reports/process_health.json", 60,
                           "every process, its last run and whether it is healthy"),
    "MT5-Healers":        ("desks/mt5/logs/MT5-Healers.log", 180,
                           "proof the standing fixers actually ran"),
    "MT5-MoatRecorder":   ("desks/mt5/data/moat_coverage.json", 180,
                           "moat capture coverage"),
    # THE TICK RECORDER, JUDGED ON THE TAPE'S OWN CLOCK (2026-10-14). It returned 1 at
    # 2026-10-12 19:56 box time and never ran again: boot/logon triggers only, and the scheduler's
    # restart-on-failure does not fire on a non-zero exit. process_health called it FAILING for
    # two days and never_stale escalated rather than started it, because no contract existed. Its
    # status file is rewritten every cycle even while nothing is captured, so the age is read
    # from `last_tick_utc` inside it (INTERNAL_STAMPS below), not from the file's mtime: a
    # recorder that beats but records nothing reads STALE, and never_stale starts it.
    "MT5-TickRecorder":   ("desks/mt5/reports/TAPE_RECORDER.json", 120,
                           "the bronze tick tape; age is its newest tick, true UTC"),
    # THE FOURTEEN UNCONTRACTED ORGANS (2026-09-12). Every one appeared on the board as
    # "no artifact contract: this process could stop and nothing would notice" -- which is
    # exactly the gap that lets a new organ die quietly, and the principal asked for it closed.
    #
    # EACH PATH WAS VERIFIED TO EXIST ON THE TRADING BOX BEFORE IT WAS WRITTEN HERE, with its
    # real age read at the same time. That check is not ceremony: this file already carries a
    # scar from naming an artifact its organ does not produce, which reported a healthy organ
    # FAILING at 357m and taught the reader to distrust the whole board. A contract pointed at
    # the wrong file manufactures a defect, and that is worse than having no contract.
    #
    # A LOG IS A LEGITIMATE ARTIFACT for an organ whose product is an ACTION rather than a
    # document -- the healer, the boot check, the deadman. MT5-Healers already worked this way.
    # What a log must never do is stand in for a document the organ genuinely writes.
    "MT5-Frontier":       ("desks/mt5/reports/FRONTIER_INTELLIGENCE.json", 180,
                           "the frontier scout's hourly intelligence sweep"),
    "MT5-MoatMiner":      ("desks/mt5/data/moat_miner_state.json", 180,
                           "which slice of the 245-symbol moat the miner last profiled"),
    "MT5-MoatSilver":     ("desks/mt5/logs/MT5-MoatSilver.log", 180,
                           "bronze -> silver day-file conversion for the moat tape"),
    "MT5-QQuantGatesCertify": ("desks/mt5/reports/QQUANT_GATES.json", 180,
                               "the qquant lane's gate verdicts"),
    "MT5-QQuantShadow":   ("desks/mt5/reports/shadow/qquant_shadow_state.json", 180,
                           "the qquant forward lane's clocks"),
    "MT5-RiskUnitsFence": ("data/risk_units.json", 180,
                           "the risk-unit fence -- what one R is worth per instrument"),
    "MT5-UniversalGate":  ("desks/mt5/logs/MT5-UniversalGate.log", 180,
                           "the ten-gate certifier; UNIVERSAL_SURVIVORS.json is MT5-Gauntlet's "
                           "row, so this watches that the gate RAN rather than its shared output"),
    "MT5-CacheWarm":      ("desks/mt5/logs/MT5-CacheWarm.log", 180,
                           "pre-warms the gauntlet's bar cache; when it stops, every sweep pays "
                           "the fetch cost again and the docket's tail is never reached"),
    "MT5-IdentityHealer": ("desks/mt5/logs/MT5-IdentityHealer.log", 180,
                           "clears IDENTITY_BROKEN clocks. It had NEVER ONCE RUN before "
                           "2026-09-12 and nothing noticed, which is this row's whole reason"),
    # GRADED ON THE PASSED PROBE, NOT THE LOG (2026-10-06): every refusal appends to the log, so
    # a watchdog wedged on "refusing" kept the log fresh and read OK. ensure_terminal.ps1 writes
    # terminal_boot_ok.json only when the read-only IPC/account probe passes.
    "MT5-TerminalBoot":   ("desks/mt5/data/terminal_boot_ok.json", 180,
                           "keeps the MT5 terminal up and its IPC answering -- without it every "
                           "other organ's market data goes stale while each reports success"),
    # DAILY OR EVENT-DRIVEN, so the age is generous on purpose. An alarm that fires on a
    # legitimately quiet organ is the cry-wolf failure, and these three are quiet by design.
    "MT5-ResearchReports": ("desks/mt5/reports/RESEARCH_REPORT_CLOCK.json", 1560,
                            "the research report clock"),
    "MT5-NewsDesk":       ("desks/mt5/logs/MT5-NewsDesk.log", 1440,
                           "the news daemon; its log moves when news moves, so a quiet window "
                           "is not a defect and only a silent DAY is"),
    # A clean pass writes the state stamp but no log line. Watching the log called the guard
    # STALE for five days while its checked_at advanced every scheduled pass.
    "MT5-FusionDeadman":  ("desks/mt5/data/fusion_deadman_state.json", 90,
                           "the Fusion dead-man watch and its latest safety verdict"),
    # THE ONLY LOSS ON THIS DESK THAT CANNOT BE UNDONE. Every other defect costs time; an
    # unrecorded day costs the thing the time was buying, because 2029 cannot re-record 2026.
    # 90 minutes against a 30-minute clock: this must be noticed inside the window the broker
    # still serves tick history for, not on a daily review.
    # WIRED 2026-09-12, after check_enforcement_execution measured libs/research/dist_shift.py
    # DECORATIVE: built 2026-07-29 and never called from outside its own module or its tests. A
    # detector that runs nowhere has detected nothing. Its first live pass flagged EURUSD DRIFT
    # with two funded sleeves riding on it.
    "MT5-ShiftWatch":     ("desks/mt5/reports/DIST_SHIFT.json", 180,
                           "whether each live sleeve's symbol still trades in the distribution "
                           "its thresholds were calibrated in"),
    # F1 OF THE 28, and the principal ranks it first of everything remaining. The release and
    # signing guards both existed and neither had a caller: the box that moves money never
    # verified which build it was running or whether the record saying so was authentic.
    # THE RECONCILER THAT HAD NEVER RUN ON THE BOX THAT TRADES. forward_reconcile is called from
    # daily_cycle.py:134 and daily_cycle is not scheduled here, so 32 clocks sat ACTIVE and
    # structurally unpromotable, accruing evidence they could never cash.
    "MT5-ForwardReconcile": ("desks/mt5/data/forward_reconcile.json", 1560,
                             "every clock certified or retired -- nothing squats"),
    # Certificates that passed the gates and can never be enrolled still counted toward the total
    # and still spent a share of the fixed family-wise error budget.
    "MT5-CertHygiene":    ("desks/mt5/reports/CERTIFICATE_HYGIENE.json", 1560,
                           "certificates the enrolment engine can never run, evicted with their "
                           "evidence kept"),
    "MT5-ReleaseAuthority": ("desks/mt5/reports/RELEASE_AUTHORITY_AUDIT.json", 45,
                             "does the running tree match a SIGNED release, and would the hourly "
                             "adopter overwrite unpushed money-path work"),
    "MT5-MoatCapture":    ("desks/mt5/reports/MOAT_CAPTURE.json", 90,
                           "per-day capture completeness -- which SYMBOLS a short day is "
                           "missing, while a targeted re-pull can still recover them"),
    # THE FRONTIER MEASUREMENT LANE (ops/run_frontier_audit.cmd). Five reports from one daily
    # task. Each was built, correct, and had no caller anywhere in the tree -- the class of
    # defect III.16 names. Each is a pure measurement: reads artifacts, writes a report, touches
    # no ledger, no sizing and no order.
    "MT5-FrontierAudit":  ("desks/mt5/reports/PIT_AUDIT.json", 1560,
                           "the nine point-in-time facts, asked of EVERY data path the desk "
                           "reads -- not only the acquired ones certify() already covers"),
    "MT5-FrontierAudit (forward null)": (
        "desks/mt5/reports/FORWARD_CALIBRATION.json", 1560,
        "what fraction of PURE NOISE this forward lane would promote, drawn at the desk's own "
        "trade counts and dispersion -- the lane's false-admission rate, measured not assumed"),
    "MT5-FrontierAudit (orthogonality)": (
        "desks/mt5/reports/ORTHOGONALITY.json", 1560,
        "n_eff of the live book by linear AND tail dependence, and the pairs whose tail "
        "coincidence is hidden behind a low Pearson"),
    "MT5-FrontierAudit (unknown unknowns)": (
        "desks/mt5/reports/UNKNOWN_UNKNOWNS.json", 1560,
        "a queue of what the desk's models CANNOT explain, phrased as questions for a seat -- "
        "the only observations carrying information about a missing ontology"),
    "MT5-FrontierAudit (book forensics)": (
        "desks/mt5/reports/BOOK_FORENSICS.json", 1560,
        "where the live book's P&L actually came from, against what the book believed"),
    "MT5-FrontierAudit (world model)": (
        "desks/mt5/reports/WORLD_MODEL.json", 1560,
        "nine market axes as POSTERIORS with per-axis estimator disagreement, where the regime "
        "engine emitted one label and one confidence scalar"),
    "MT5-FrontierAudit (representations)": (
        "desks/mt5/reports/REPRESENTATION_DISCOVERY.json", 1560,
        "learned representations scored head-to-head against the symbolic grammar on OOS "
        "predictive information, with the trial count declared and magnitude split from "
        "direction"),
    # F6. Hourly, with the audit lane: the tree only reaches depth by being expanded, so its
    # cadence is its reach.
    "MT5-AuditLane (research tree)": (
        "desks/mt5/reports/RESEARCH_TREE.json", 180,
        "which research branch earns the next cell, by expected information gain per "
        "cell-equivalent -- and which branches are permanently pruned on their own evidence"),
    # F7. Daily at 00:30 UTC, right after the free budget resets -- at any other hour the panel
    # competes for a budget the rest of the desk has already spent and seats nobody.
    "MT5-ScientistTournament": (
        "desks/mt5/reports/SCIENTIST_TOURNAMENT.json", 1560,
        "ten critics on DIFFERENT evidence and different vendors, a reviewer forbidden to "
        "resolve a dissent, and a meta-reviewer whose only job is to catch dissents that went "
        "missing"),
    "MT5-FrontierAudit (evidence vault)": (
        "desks/mt5/reports/EVIDENCE_VAULT.json", 1560,
        "sealed holdout tiers with irreversible reveal counters, a dependency fingerprint over "
        "the judge and the cost model, and the certificates minted under a lower "
        "multiple-testing charge than the one in force"),
    "MT5-FrontierAudit (causal discovery)": (
        "desks/mt5/reports/CAUSAL_DISCOVERY.json", 1560,
        "the PC constraint phase over the live book: which dependencies vanish given a third "
        "series, which edges the data can ORIENT, which it cannot and what experiment would -- "
        "with conflicting orientations counted as the assumption violation they are"),
    "MT5-FrontierAudit (credit assignment)": (
        "desks/mt5/reports/CREDIT_ASSIGNMENT.json", 1560,
        "realised forward R attributed back through certificate and docket row to the scientist "
        "that proposed it -- ranked by what it EARNED, with the certificate count beside it, and "
        "the certificates that have earned nothing counted"),
    "MT5-FrontierAudit (adversary evolution)": (
        "desks/mt5/reports/ADVERSARY_EVOLUTION.json", 1560,
        "a PERSISTENT population of parameterised attacks judged by the real ten gates, each "
        "declaring the verdict it ought to receive -- so a breach is a breach and a clean edge "
        "refused is the gates' other error"),
    "MT5-FrontierAudit (modifier counterfactuals)": (
        "desks/mt5/reports/MODIFIER_COUNTERFACTUALS.json", 1560,
        "every applied capital multiplier priced in E[log W] against the SAME average heat "
        "spread flat -- the modifier's timing, not its level, so a modifier that doubles "
        "everything scores zero"),
    "MT5-FrontierAudit (missed growth)": (
        "desks/mt5/reports/MISSED_GROWTH.json", 1560,
        "22 rails walked against the allocator's own growth curve, each carrying what it cost "
        "and what it earned -- and naming the event it is still waiting for"),
    "MT5-FrontierAudit (formal invariants)": (
        "desks/mt5/reports/FORMAL_INVARIANTS.json", 1560,
        "seven structural invariants, each PROVEN by exhaustion, ENFORCED by a complete static "
        "enumeration, or carried as a named OBLIGATION -- never as a weaker check reported as "
        "the same thing"),
    "MT5-FrontierAudit (independent verifier)": (
        "desks/mt5/reports/INDEPENDENT_VERIFIER.json", 1560,
        "every promoted certificate rebuilt by a second implementation that imports no desk "
        "code -- signals, fills, costs and R compared trade by trade, with UNSUPPORTED and "
        "UNMEASURED published as themselves and never as agreement"),
    "MT5-FrontierAudit (meta R&D)": (
        "desks/mt5/reports/META_RND.json", 1560,
        "the arena a challenger research-system must beat -- sealed traps, the adversary, the "
        "forward credit record -- with the knobs it may move enumerated and the ones it may "
        "never move enumerated beside them"),
    "MT5-FrontierAudit (quantbench)": (
        "desks/mt5/reports/QUANTBENCH.json", 1560,
        "every defect this desk has actually survived, as an executable probe against the "
        "CURRENT tree -- with a case count that ratchets, so deleting one is a visible act"),
    "MT5-FrontierAudit (capacity frontier)": (
        "desks/mt5/reports/CAPACITY_FRONTIER.json", 1560,
        "how many multiples of today's round trip each mechanism's edge survives, against the "
        "multiple its symbol's spread already widens by intraday -- and the venue's own verdict "
        "that it publishes no order book at all"),
    "MT5-FrontierAudit (capacity floor)": (
        "desks/mt5/reports/CAPACITY.json", 1560,
        "the LOWER capacity bound: the equity below which the venue's minimum lot forces more "
        "risk per trade than the policy asked for"),
    "MT5-FrontierAudit (execution science)": (
        "desks/mt5/reports/EXECUTION_SCIENCE.json", 1560,
        "signal alpha and execution drag separated by scoring the SAME signals at a zero cost "
        "multiplier, and each fill-and-exit policy ranked on held-out bars"),
    "MT5-FrontierAudit (sub-hour replay)": (
        "desks/mt5/reports/SUBHOUR_COUNTERFACTUALS.json", 1560,
        "counterfactuals for the sub-H1 sleeves action_counterfactuals skips, at the resolution "
        "they actually trade, plus the error the H1 approximation was making"),
    "MT5-FrontierAudit (information value)": (
        "desks/mt5/reports/INFORMATION_VALUE.json", 1560,
        "which MISSING observation is worth obtaining, harvested from every UNMEASURED verdict "
        "the desk publishes, plus the acquired series nothing has ever referenced"),
    "MT5-FrontierAudit (market ecology)": (
        "desks/mt5/reports/MARKET_ECOLOGY.json", 1560,
        "the tape footprint each participant class must leave if it is there -- systematic "
        "rebalance, vol-control, CTA triggers, dealer gamma, round-number magnets, session "
        "makers -- each against a block-permuted null, plus the desk's own edge-decay slope"),
    # F28 and F11/F27. budget_market prices the three resources; meta_controller spends those
    # prices across nine kinds of action. Both were built and running nowhere.
    "MT5-FrontierAudit (budget market)": (
        "desks/mt5/reports/BUDGET_MARKET.json", 1560,
        "compute, trials and capital priced against each other in dE[log W] per unit of each, "
        "with every denominator's basis stated and an unmeasurable one publishing UNMEASURED"),
    "MT5-FrontierAudit (meta controller)": (
        "desks/mt5/reports/META_CONTROLLER.json", 1560,
        "nine kinds of research action -- new hypothesis, deepen, acquire, falsify, investigate, "
        "gather forward, evolve, transfer, abandon -- ranked per unit of the resource each one "
        "actually consumes, with the binding resource named"),
    "MT5-FrontierAudit (frontier map)": (
        "desks/mt5/reports/FRONTIER_MAP.json", 1560,
        "the one map: data x mechanism x market x horizon x state x representation x execution x "
        "payoff, with occupancy, confidence width and expected information per region, and the "
        "regions ONE axis from somewhere the desk has already been"),
    "MT5-FrontierAudit (negative knowledge)": (
        "desks/mt5/reports/NEGATIVE_KNOWLEDGE.json", 1560,
        "a trained P(survive) over the desk's own 21,582 judged cells, with an absolute "
        "exploration floor and its own out-of-sample evidence stated as UNMEASURED when the "
        "held-out window holds too few survivors to judge it"),
    "MT5-FrontierAudit (joint evolution)": (
        "desks/mt5/reports/JOINT_EVOLUTION.json", 1560,
        "whether the desk's strategy LAYERS are separable -- the share of fitness variance each "
        "axis pair carries in its interaction alone, and what the joint genome scores against "
        "the fixed recipe out of sample"),
    # Tier-5 audit XCI/107 and XCIV (2026-09-29): both were built and ran on no clock.
    "MT5-FrontierAudit (market posteriors)": (
        "desks/mt5/reports/MARKET_POSTERIORS.json", 1560,
        "F3: nine market axes as posteriors, two estimators each, disagreement kept per axis"),
    # #521 audit MF-B (2026-10-29): the merge-pipeline watcher runs inside Quant-WorkflowGate, so
    # a task that stops firing would leave its report simply un-updated. This board runs on its
    # own clock; 45 min = the watcher's 25-min re-read plus two 10-min sweep runs.
    "Quant-WorkflowGate (merge pipeline)": (
        "desks/mt5/reports/MERGE_PIPELINE.json", 45,
        "queued-check ages, CLEARed or green work waiting, LIVE's last code, the box sweep's "
        "heartbeat; owned by Quant-WorkflowGate, not a task of its own"),
    "MT5-FrontierAudit (chart allocation)": (
        "desks/mt5/reports/CHART_ALLOCATION.json", 1560,
        "research effort per chart, inverse to the docket share each chart already holds"),
}


#: EVERY BOX TASK GETS A FRESHNESS CONTRACT (row 118 / class fix, 2026-11-03). process_health
#: measured 77 desk tasks UNCONTRACTED on the trading box, among them MT5-AdoptRelease (the only
#: road code takes onto the box) and MT5-IntelShip (whose upstream went silent for 14 h with the
#: task reporting rc 0 every hour). An UNCONTRACTED task can stop and nothing notices, so every
#: TASK line of `desks/mt5/ops/box_tasks.manifest` now owes a row here, in RESIDENT_CONTRACTS
#: (derived), or in NOT_CONTRACTABLE (named reason, ratcheted down by
#: tests/ops/test_box_task_contracts.py). The artifact for each is the file its own script
#: writes, read from that script: a report where one exists, its log where its product is an
#: action. Ages follow the file's convention: cadence with room for one missed run (5 min -> 15,
#: 15 min -> 45, 30 min -> 90, hourly -> 180, 2 h -> 360, 6 h -> 1080, daily -> 1560).
BOX_TASK_CONTRACTS: dict[str, tuple[str, int, str]] = {
    # THE TWO THAT STALLED SILENTLY.
    "MT5-AdoptRelease": ("desks/mt5/reports/ADOPTION_HEARTBEAT.json", 180,
                         "Adopt-And-Seal.ps1 stamps started_at/finished_at every pass; whether "
                         "the box is actually RUNNING LIVE's code is process_health's "
                         "`adoption` block (RELEASE.json age against LIVE's code head)"),
    "MT5-IntelShip":    ("desks/mt5/reports/INTEL_SHIP.json", 180,
                         "age = the newest intel-ship/send commit the box landed "
                         "(INTERNAL_STAMPS ship_head_at), so a silent upstream miner reads "
                         "STALE even while this task exits 0 every hour"),
    "MT5-CostState":    ("desks/mt5/reports/COST_HONESTY.json", 1560,
                         "the last of the three daily cost producers (surface, carry, honesty)"),
    "MT5-AuditLane":    ("desks/mt5/logs/MT5-AuditLane.log", 180,
                         "audit intake + kimi hunter; the cmd appends every step here"),
    "MT5-FusionDeadmanDryRun": ("desks/mt5/logs/fusion_deadman.log", 15,
                                "every deadman pass logs; one stamp file has one writer"),
    "MT5-FusionDeadmanLive": ("desks/mt5/data/fusion_deadman_state.json", 15,
                              "the live deadman's stamp, written every 5-minute pass"),
    "MT5-ResearchSupervisor": ("desks/mt5/logs/supervisor_state.json", 90,
                               "the supervisor's child table, rewritten every pass"),
    "MT5-AllocatorPulse": ("desks/mt5/data/allocator_trigger_state.json", 15,
                           "the 5-minute allocator trigger's own state"),
    "MT5-Deepening":    ("desks/mt5/reports/DEEPENING_MEMORY_GUARD.json", 180,
                         "the deepening worker's per-pass memory guard (published to git)"),
    "MT5-DeepSeek":     ("desks/mt5/logs/MT5-DeepSeek.log", 180,
                         "the DeepSeek seat's hourly run log"),
    "MT5-TickIntegrity": ("desks/mt5/reports/TICK_INTEGRITY.json", 180,
                          "the hourly tick-tape integrity verdict"),
    "MT5-TapeFeatures": ("desks/mt5/reports/TAPE_FEATURES.json", 180,
                         "the hourly tape-derived cost/slippage features"),
    "MT5-VolArchive":   ("desks/mt5/reports/VOL_ARCHIVE.json", 1560,
                         "the vol archive's report; cadence UNDECLARED, so a day's room"),
    "MT5-MoatFence":    ("desks/mt5/logs/MT5-MoatFence.log", 90,
                         "the tape recorder's 30-minute watchdog log"),
    "MT5-ContractTerms": ("desks/mt5/logs/MT5-ContractTerms.log", 180,
                          "install_contract_terms_task.ps1 sends every hourly run here"),
    "MT5-BoxHeartbeat": ("desks/mt5/reports/BOX_HEARTBEAT.json", 15,
                         "the box's 5-minute heartbeat"),
    "MT5-OffsiteBackup": ("desks/mt5/reports/OFFSITE_BACKUP.json", 1080,
                          "the 6-hourly offsite backup verdict"),
    "MT5-PrivateNetAudit": ("desks/mt5/data/private_net.json", 1560,
                            "the daily private-network audit"),
    "MT5-ReapGitWriters": ("desks/mt5/reports/GIT_WRITER_REAP.json", 45,
                           "the 15-minute hung-git-writer reaper's verdict"),
    "MT5-RebootDrill":  ("desks/mt5/reports/REBOOT_DRILL.json", 1560,
                         "the daily reboot drill PASS/FAIL"),
    "MT5-ShadowSync":   ("desks/mt5/logs/sync_shadow_to_git.log", 45,
                         "the 15-minute box-state publish to git"),
    "MT5-HourlyCore":   ("desks/mt5/reports/REPLICATION.json", 180,
                         "the core hourly plan's replication leg (published to git)"),
    "MT5-GateAttest":   ("data/gate_attestation_run.json", 360,
                         "the 2-hourly gate attestation run"),
    "MT5-SshGuard":     ("desks/mt5/data/ssh_guard.json", 15,
                         "the 5-minute SSH guard verdict"),
    "MT5-PlumbingWatchdog": ("desks/mt5/reports/PLUMBING_WATCHDOG.json", 45,
                             "the 15-minute plumbing defects report"),
    "MT5-ClockFixer":   ("desks/mt5/reports/CLOCK_FIXER.json", 45,
                         "the 15-minute resident/clock repair report"),
    "MT5-Daily":        ("desks/mt5/logs/daily_cycle.log", 1560,
                         "the daily cycle's step log"),
    "MT5-ConvertSwarm": ("desks/mt5/logs/MT5-ConvertSwarm.log", 180,
                         "the hourly conversion swarm's run log"),
    "MT5-NoLog":        ("desks/mt5/reports/NO_LOG.json", 1560,
                         "the daily silent-gateway-log audit"),
    "MT5-RegimeMonitor": ("desks/mt5/data/regime_state.json", 45,
                          "the 15-minute regime state (published to git)"),
    "MT5-MoatRecorder-Watchdog": ("desks/mt5/data/moat_coverage.json", 90,
                                  "the moat recorder's coverage, which the watchdog restarts"),
    "MT5-FTMOFollow":   ("desks/mt5/data/ftmo_follow_state.json", 10,
                         "the legacy 1-minute follower's state"),
    "MT5-FTMO-Follower": ("desks/mt5/reports/FTMO_FOLLOWER.json", 10,
                          "the 1-minute FTMO follower's report"),
    "MT5-FTMO-VenueReader": ("desks/mt5/reports/FTMO_ACCOUNT_STATE.json", 15,
                             "the 5-minute FTMO account read"),
    "MT5-FTMO-Executor": ("desks/mt5/reports/FTMO_EXEC.json", 15,
                          "the 5-minute FTMO executor's report"),
    "MT5-E8WindowGuard": ("desks/mt5/data/e8_window_guard_state.json", 10,
                          "the 1-minute E8 window guard's handled-set"),
    "MT5-GoldHourSweep": ("desks/mt5/logs/MT5-GoldHourSweep.log", 1560,
                          "the gold hour sweep's log; cadence UNDECLARED, so a day's room"),
    "MT5-CycleMidnight": ("desks/mt5/data/cro_cycle_ledger.jsonl", 1560,
                          "both CRO lanes append one row per cycle; a day without one is a "
                          "missed lane"),
    "MT5-CycleNoon":    ("desks/mt5/data/cro_cycle_ledger.jsonl", 1560,
                         "both CRO lanes append one row per cycle"),
    "MT5-LawGate":      ("data/law_gate.json", 180,
                         "the rotating law gate's record of every fence and when it ran"),
    "Claude-Bridge-Watchdog": ("C:/ProgramData/ClaudeBridge/logs/bridge_watchdog.json", 15,
                               "refreshed at least every 60 s while the watchdog lives"),
    "Quant-BootRecord": ("C:/ProgramData/QuantBox/logs/boot_session.log", 30,
                         "the 10-minute boot-session record"),
    "Quant-WorkflowGate": ("C:/ProgramData/QuantBox/logs/workflow_gate.json", 30,
                           "the 10-minute workflow gate's own state"),
    "Quant-SignTrain":  ("C:/ProgramData/QuantBox/logs/sign_train.json", 30,
                         "the 10-minute sign train leg's state"),
}

#: Box tasks that genuinely produce no artifact a freshness contract could read, each with the
#: reason. tests/ops/test_box_task_contracts.py fails if this grows, and fails if a manifest task
#: is in neither table -- so a new task cannot join the box without saying what it produces.
NOT_CONTRACTABLE: dict[str, str] = {
    "MT5-SealIfClean": "retired: MT5-AdoptRelease owns sealing (manifest 'legacy compatibility')",
    "MT5-LocalDashboard": "an HTTP server with no artifact; liveness is a probe, not a file age",
    "MT5-DeskDashboard": "an HTTP server with no artifact; liveness is a probe, not a file age",
    "MT5-DashMirror": "not installed (manifest runs=UNKNOWN, trigger UNDECLARED)",
    "Quant-BootSession": "fires once at logon; Quant-BootRecord's 10-minute row carries the log",
}

#: The prefixes of task names this desk owns. A scheduler row outside them (Google updater, a
#: sibling project) is FOREIGN to process_health: listed, never a desk fault.
DESK_TASK_PREFIXES: tuple[str, ...] = ("MT5-", "E8-", "Quant-", "Claude-Bridge-", "Codex-")


def resident_contracts() -> dict[str, tuple[str, int, str]]:
    """Keep-alive task -> contract for every 24/7 resident, DERIVED from the component registry
    (desks/mt5/ops/components.resident_specs), never hand-listed: a department or forest proves a
    COMPLETED pass through its progress watermark, a moat swarm through MOAT_SWARMS.json, each
    against its family's own derived max silence. Empty if the registry cannot be loaded."""
    try:
        import sys as _sys
        for p in (str(ROOT), str(DESK)):
            if p not in _sys.path:
                _sys.path.insert(0, p)
        from desks.mt5.ops import components

        from libs.ops.control_plane import watermarks
        specs = components.resident_specs()
    except Exception:
        return {}
    out: dict[str, tuple[str, int, str]] = {}
    for s in specs:
        silence_min = max(15, -(-int(s.max_silence_s or 11_400) // 60))
        if s.component_id.startswith("resident:dept_"):
            rel = watermarks.path_for(s.component_id).relative_to(ROOT).as_posix()
            what = f"{s.component_id}'s progress watermark: written once per COMPLETED pass"
        else:
            rel = "desks/mt5/reports/MOAT_SWARMS.json"
            what = f"{s.component_id}: the swarms' shared pass report"
        out.setdefault(str(s.schedule), (rel, silence_min, what))
    return out


def all_contracts() -> dict[str, tuple[str, int, str]]:
    """Curated CONTRACTS, then the box-task table, then the derived residents. Curated wins."""
    out = dict(resident_contracts())
    out.update(BOX_TASK_CONTRACTS)
    out.update(CONTRACTS)
    return out


#: Artifacts whose age is the stamp INSIDE them, not the file's mtime: artifact -> JSON key
#: holding an ISO-8601 UTC instant. For an organ that rewrites its status every pass whether or
#: not it produced anything, mtime only proves the process is alive. An absent, unreadable,
#: unstamped or future stamp reads as no artifact at all, which never_stale answers by starting
#: the task.
INTERNAL_STAMPS: dict[str, str] = {
    "desks/mt5/reports/TAPE_RECORDER.json": "last_tick_utc",
    # The newest commit the box landed from intel-ship/send, not when the task last ran: an
    # upstream miner that stops shipping reads STALE while the task keeps exiting 0.
    "desks/mt5/reports/INTEL_SHIP.json": "ship_head_at",
}

#: A stamp further than this past now is a clock defect, never freshness.
FUTURE_SLACK_MIN = 5.0


def _stamp_age_min(p: Path, key: str, now: datetime) -> float | None:
    try:
        # utf-8-sig: PowerShell 5's Set-Content -Encoding UTF8 writes a BOM (INTEL_SHIP.json).
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
        at = datetime.fromisoformat(str(doc[key]).replace("Z", "+00:00"))
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    age = (now - at).total_seconds() / 60.0
    return None if age < -FUTURE_SLACK_MIN else max(age, 0.0)


def artifact_age_min(rel: str, now: datetime | None = None, root: Path = ROOT) -> float | None:
    """The contract age of `rel`: its internal stamp where INTERNAL_STAMPS names one, else the
    file's mtime. None means the organ has produced nothing usable."""
    now = now or datetime.now(UTC)
    key = INTERNAL_STAMPS.get(rel)
    if key:
        return _stamp_age_min(root / rel, key, now)
    return _age_min(root / rel, now)


def _age_min(p: Path, now: datetime) -> float | None:
    try:
        return (now - datetime.fromtimestamp(p.stat().st_mtime, UTC)).total_seconds() / 60.0
    except OSError:
        return None


def check() -> dict:
    now = datetime.now(UTC)
    rows = []
    for organ, (rel, max_age, what) in sorted(all_contracts().items()):
        age = artifact_age_min(rel, now)
        if age is None:
            verdict, why = "ABSENT", f"{rel} does not exist -- the organ has never produced it"
        elif age > max_age:
            verdict, why = "STALE", f"{age:.0f} min old against a {max_age} min contract"
        else:
            verdict, why = "OK", f"{age:.0f} min old"
        rows.append({"organ": organ, "artifact": rel, "max_age_min": max_age,
                     "age_min": None if age is None else round(age, 1),
                     "verdict": verdict, "why": why, "artifact_is": what})
    bad = [r for r in rows if r["verdict"] != "OK"]
    return {
        "measured_at": now.isoformat(timespec="seconds"),
        "contracts": len(rows),
        "ok": len(rows) - len(bad),
        "failing": len(bad),
        # STATUS IS THE WORST ROW, never an average. An average would let eleven healthy organs
        # hide the one that stopped, which is the failure this file exists to make impossible.
        "status": "OK" if not bad else "FAILING",
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    if a.json:
        print(json.dumps(rep, indent=1))
        return 0 if rep["status"] == "OK" else 1
    print(f"organ contracts: {rep['ok']}/{rep['contracts']} OK   status {rep['status']}")
    print(f"{'organ':<22}{'verdict':<9}{'age':>8}  artifact")
    print("-" * 96)
    for r in rep["rows"]:
        age = "-" if r["age_min"] is None else f"{r['age_min']:.0f}m"
        print(f"{r['organ']:<22}{r['verdict']:<9}{age:>8}  {r['artifact']}")
    if rep["failing"]:
        print()
        print("FAILING -- each of these reported success while producing nothing:")
        for r in rep["rows"]:
            if r["verdict"] != "OK":
                print(f"  {r['organ']:<22} {r['why']}")
                print(f"  {'':<22} the artifact is {r['artifact_is']}")
    print(f"\n-> {OUT}")
    return 0 if rep["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
