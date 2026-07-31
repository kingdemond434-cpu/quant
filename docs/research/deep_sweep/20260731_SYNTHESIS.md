# WEEKLY DEEP COLD AUDIT — SYNTHESIS (2026-07-31)

STATUS: COMPLETE

_Synthesis lead. Inputs: all 8 subsystem audits dated 20260731, every one carrying STATUS: COMPLETE —
the first sweep in this organ's history with 8/8 completed reports (07-29: 6/8; 07-30: alpha-discovery
and validation-stats died as skeletons). Additional live evidence gathered at synthesis time is marked
[SYNTH-VERIFIED] with its command._

---

## (A) OVERALL VERDICT + CEILING TABLE

**Verdict: the desk is a world-class mechanism factory bolted to a broken integration layer, and the
integration layer is now measurably the binding constraint on everything else — including on capital
ever deploying.** Every audit found the same two shapes at its own depth: (1) built-never-wired
(read-without-writer paths, write-only memory stores, computed-but-ignored deciders, zero-caller
mechanisms) appearing at ~7 new instances/day; (2) found-never-repaired — the meta seat measured the
repair queue at λ≈14 findings/day vs μ≈0.6/day cross-session, stock +10/day, and **no ledger row older
than 3.67 days has ever been implemented**. The desk's engineering quality is not in question (five
fail-closed, property-tested rail modules in one day; a Romano-Wolf/CSCV stack that survives
adversarial read; an honest fusion engine that measured its own flagship negative). What is in
question is whether anything built ever runs, and whether anything found ever gets fixed.

Three time-critical clusters dominate this week (details in (C)):
1. **The launch money path is wrong in ways that fire exactly once, on launch day** (exec F1: the
   capital-deposit trigger reads a phantom file → records equity $0.00 → ruin rail silently loosened
   ~89% into an append-only ledger; F2: the live connector keeps the exact equity bug that flattened
   the testnet book; F8: stops have zero callers → first position self-freezes the book).
2. **The scheduler is duplicated and corrupting data right now** (3 feeds measured at exactly 2×
   write rate; recorder double-spawn armed against the moat; ingest_axes collides daily at 06:40Z
   with different args and non-excluding locks). [SYNTH-VERIFIED still live at 03:00Z:
   `defi_lending.jsonl` 556 rows/hr vs 278 baseline; `crontab -l` duplicate-script check → 15+ scripts
   scheduled ≥2×.]
3. **The validation gate is now measured WELDED, not strict.** [SYNTH-VERIFIED from
   `/tmp/certify_audit_20260731.log`, 7 rows in]: true-Sharpe **2.0 and 3.0 controls FAIL both
   gauntlet paths on every seed** (blockers: dsr + reality_check); the first **SR 5.0 control PASSES
   per-candidate**. Min passing true SR on the fixed path is between 3 and 5; the legacy path fails
   even SR 5. No real crypto strategy has true SR 5 — the desk's screen provably cannot admit a real
   edge, which converts the entire 434-tested/0-promoted record from "fact about markets" to
   "instrument artifact" (L1.25's exact cautionary shape, now with its proving artifact).

**Ceiling table** (auditors' own scores; opportunity cost condensed):

| subsystem | current | ceiling | gap | opportunity_cost_1y (auditor's words, condensed) |
|---|---|---|---|---|
| alpha-discovery | 35% | ~85% | 50 | HIGH — generation at steady-state zero inside a search box that cannot power h≥5; 420 never re-scored under the fixed gate |
| data-intelligence | 36% | 85% | 49 | VERY HIGH — LLM dig tier funding-dead day 9-10; single-venue ban risk on everything |
| data-moat | 55% | 85% | 30 | HIGH + a countdown: zero backup, ~29d disk fuse on irreplaceable L2 |
| infrastructure | 62% | 93% | 31 | VERY HIGH — supply-chain PAT chain to a future live-key box; moat on one disk |
| execution-growth | 34% | 80% | 46 | dominant term: bounded-probability unbounded-severity launch-day failure |
| validation-stats | 58% | 90% | 32 | the conversion funnel's entire throughput (screen admits nobody; Stage-B runs at ~5× stated α) |
| research-engine | 35% | 85% | 50 | autonomous discovery contributes ~nothing for a year at tested=0 + dead review lane |
| meta-and-blindspots | 58% | 85% | 27 | ≥80% of all audit output converts to nothing; a falsified doctrine claim steered every organ 8 days |

Cross-audit consistency check: every seat independently put the ceiling at 80–93% with the gap
composed of **wiring, funding, and ownership — not new science or new technology**. Median current
≈ 45%, median ceiling ≈ 85%. The desk is running at roughly half its own already-built potential.

---

## (B) CAPABILITY MAP

**The missing capability that unlocks the most: INTEGRATION VERIFICATION — proving that built things
are called, called things are scheduled, scheduled things actuate, and found things get repaired.**
It has two halves, both cheap, both named precisely by the audits:

- **The class check (~40 lines): repo-wide read-implies-writer assertion in max_audit**
  (exec-growth #7, T5 census first). Kills the desk's most prolific defect generator: 7 new
  phantom-path instances in the 24h after the pattern was named (capital-event file+key,
  gate0_complete, ramp evidence, web/tca.json, keys_present glob, connector_verified,
  research_memory.db ×4 callers). Downstream unlocks: promotion queue produces its first real
  output, diversity metrics measurable, director dossier completes, launch board stops lying.
- **The repair wire (hours): R-rows into the §37 carry-over brief + a max_audit
  `recommendations-past-due` gate + repair-mode backpressure (open+past-due > 25 flips the next
  sweep window to repair) + MTTR/P(fix) born-fenced** (meta X1/X3/X4). Raises P(action) for every
  future finding from every organ, permanently. Queueing theory verdict (meta M8): at ρ≈4,
  exhortation cannot work — only capacity, caps, or admission control. This is capacity.

Everything else in all eight reports flows through these two. They are the compounding multipliers
of the week and they cost less combined than one subsystem audit.

**The existing capability whose failure is the greatest systemic risk: the single-box, single-disk,
single-IP, single-scheduler estate.**
- One disk holds the only copy of the irreplaceable moat (6.6G L2 depth at own timestamps + the
  execution tape), with a ~29-day fuse to the 80% disk guard and no fence (DM-1, infra F5).
- One push-capable plaintext PAT in the git remote feeds a 10-minute auto-deploy — a working
  supply-chain kill chain to the box that will hold live keys (infra F2).
- One egress IP is being 418-banned by the venue that serves the forward-evidence clocks and the
  NAV truth chain, and the scheduler duplication just doubled the request rate feeding the ban
  (DI-10, DI-1).
- One serial brain (mutex) is the research bottleneck, and the audit apparatus alone consumes
  15–19% of it while its conversion wire is open (meta M3).

**Second-biggest bottleneck: the one unfunded LLM line.** Both providers dead (Claude organs: no
API-key fallback file; OpenRouter: 402 with 59% of the monthly envelope unspent). Idled: dataaxis,
frontier ×7 languages, prospector, litminer, cro-ai, kimi unknown-unknown battery, the 13-seat panel
(10 days silent), the strategic director (built, never run once live), 5 triage components. The
entire external-adversarial-validation and multilingual-dig capability of the desk is off for want
of one ~$25–120 decision that has been on PRINCIPAL_ACTION for days (research-engine E-14, DI-2/9).

---

## (C) TOP OPPORTUNITIES — PRIORITIZED PORTFOLIO

Ranked by expected total long-term contribution (direct + cascade + optionality + compounding) /
(effort × maintenance × opportunity-cost). ⚡ = compounding multiplier. Existing ledger rows are
cited, not duplicated; NEW items were rowed into `scripts/recommendations.py` by this synthesis
(IDs noted after rowing).

**P0 — same-day (time-critical; ordering inside P0 matters):**

1. **De-duplicate the scheduler; disarm the 06:40Z ingest_axes collision and the recorder
   double-spawn race first** (DI-1 = infra F1 = research-engine E-7; three seats independently
   ranked it #1 same-day). Migrate legacy-only jobs into `ops/crontab.manifest`, delete the legacy
   block once, stagger the 13-job 08:21 herd, dedup the contaminated rows since 07-30T23:00, add a
   crontab-vs-manifest drift fence. Stops live data corruption feeding Stage-A screens, halves
   venue poll load, disarms the moat-corrupting respawn race. Hours. ⚡ (single-source scheduler is
   permanent).
2. **Launch money-path cluster, in order** (exec-growth #1–#6): (a) capital-event wiring — point
   `record_capital_event.py` + `check_gate0_ready.py` at `cashcarry_positions.json`, executor
   persists `last_combined_equity`, refuse $0-equity rebase (~15 lines; the ONE command that runs
   on launch day currently loosens the ruin rail ~89% into an append-only ledger); (b) copy the
   proven 3-line equity fix to `binance_live.py:188` (same hour); (c) wire `place_stop_market`
   into the open path; (d) give the executor the guard-consumer edge (`effective_size_fraction` +
   `limit_only`) + minutes-cadence live_guard; (e) THEN delete `_MIN_FUNDING` (R0057, open — the
   sole blocker on the frozen 26.42/28d tape clock) so the evidence clock restarts on a truthful
   rail. ~1 day total. Removes the unbounded launch-day tail.
3. **Security pair** (infra F2 + F8): rotate the PAT to fine-grained `contents:read` (principal
   owns the GitHub account — see PRINCIPAL_ACTION), separate credentialed push path; rebind 8080/8090
   to 127.0.0.1 (tunnel unaffected) + Cloudflare Access on the dashboard hostname. Hours.
4. **Moat survivability** (DM-1 = infra F5): TODAY copy the tape (136KB) + 3 sqlite stores off-box;
   disk fence in check_ratchets (page <15% free); this week hourly rclone of closed moat/lake hours
   to a Storage Box (€4/mo — principal decision) + monthly restore drill. Converts a certain ~29-day
   outage + permanent-moat-loss tail into a €50/yr line item.

**P1 — the structural multipliers (this week):**

5. ⚡⚡ **Read-implies-writer census + max_audit class check** (exec #7/T5; see (B)). ~40 lines.
6. ⚡⚡ **The repair wire** (meta X1+X3+X4+X7; see (B)). Includes: aging escalator, roi_bps split
   (measured-bps vs rank), admission dedup against open rows. This synthesis executed the X2 half
   (rows to ledger, below) — the prompt fix (R0056) still owes.
7. ⚡ **Fund and de-single-point the LLM tier**: principal tops up OpenRouter + creates
   `data/secrets/anthropic_api_key` (minutes); desk builds the $0 free-tier fallback lane with the
   §13 licence gate (research-engine rank 1) + page-on-402/quota alert class. Unblocks 6+ organs
   including the only non-Claude reviewer.
8. **Doctrine surgery** (meta M5/X5 = existing R0051 + R0002, both past/near due): retraction
   marker on the kimchi claim at `ops/principal_doctrine.txt:89` and `:275` TODAY, bloat cut back
   under the 16k guard, then principal-doctrine-diff → auto blind-spot row (X6). Every organ has
   been taught a falsified result for 8 days.

**P2 — validation/discovery conversion (this week → next):**

9. **Act on the certification** (validation X1/X2/T2 + alpha-discovery F14/O2): read
   `reports/gauntlet_certification.json` when it lands (~08:21 backstop); with the welded verdict
   now evidence-backed [SYNTH-VERIFIED above], make `screen_select` (BY-FDR) the DECIDER with
   dsr/RW demoted to ranking statistics — this is a gate-topology ruling, page it properly — and
   re-score the 420 under the fixed per-candidate gate as one pre-registered resurrection batch.
   Either outcome is decisive for the desk's central allocation narrative ("price dead / axis
   rich" currently has zero surviving positive exemplars — alpha F1). Add standing gate-CI +
   scheduled histogram regeneration (V2/X6) so the gate can never again drift unmeasured. ⚡
10. **Stage-B error honesty** (V7/V8/X8): wire the already-built `anytime_valid` e-process as the
    ELIGIBLE condition (or pre-committed looks at 40/90d), add the ledgered RETIRED-with-reason
    writer so attrition can't lower survivor bars, append-only forward-verdict history (one tee).
    The ONLY path to capital currently runs at ~×4.9 its stated α, and the fix is on the shelf.
11. **Horizon-honest Stage-A power gate** (alpha O1/T1, extends open R0030 — dispose that row with
    this design): `ic_min(h)=0.03·√h`, panel n_eff via measured ρ̄ (V12), re-verdict archived
    screens, then positive-control battery (alpha O5/T6) so "0 survivors" becomes informative.
    Re-opens the h≥5 dimension the harness structurally closed. ⚡
12. **Phantom-DB repoint ×4 + retire the campaign corpse first** (alpha F3/O4 = moat DM-2/M2;
    corpse retirement = existing R0009): then first-ever diversity measurement + promotion queue
    first real run. Low effort, unlocks the deployment race and the "420 candidates vs one
    question 420 ways" attribution.
13. **Capacity-gate coherence** (V5+V6, interacts with 07-29 F7): replace validate()'s 2×-book bar
    with the 10%-slice ADMIT band AND plumb real per-symbol ADV in the same change (fixing either
    alone misfires); delete the dead `deployed_equity_usd`/`n_sleeves` params.

**P3 — data estate (one–two weeks):**

14. **Bronze gets an owner** (DI-7): one manifest job for full-universe daily klines + backfill
    the 132 symbols frozen since 06-21 (Binance Vision, free) + ⚡ write-rate anomaly fence on every
    appending collector (DI-13 — would have caught the scheduler doubling in an hour, and will
    catch the next silent halving).
15. **Venue request-weight coordinator + 418 circuit breaker** (DI-10): protects the forward
    clocks and NAV chain; classify ban type on next occurrence (T6-DI).
16. **Options VRP unlock** (DI-12 + alpha O3): thicken the live Deribit collector (hourly + 3–5
    strikes), then the pre-registered VRP resurrection screen — the graveyard's own "real signal,
    starved" entry with its re-entry condition now satisfiable for free. Plus wire the resurrection
    queue consumer and fill the idle Holm slot (alpha F2 — an unfilled slot is evidence never
    accrued).
17. **Moat conversion restarts** (DM-5/M4/M6): schedule micro_factory, tape records
    attempts/partials (DM-12 made survivor bias a live catch), TCA fields on all open paths,
    vitals globs fixed (tape + lake visible), Stage-A screens for the 5 computed-unused micro
    features; futclose repair + COT via CFTC direct (DI-8/DI-11).

Deliberately NOT in the portfolio: renting compute (factory's own verdict: constraint is
mechanism, not volume); loosening any statistical bar by opinion (the certification + T2 decide);
new statistical machinery (the shelf is full and unwired — that IS the finding); full multi-venue
failover pre-Gate-0 (circular dependency noted by exec seat).

---

## (D) HARD WALLS (do not confuse with headroom)

1. **T=310 days of forward history** — the true bar-setter for DSR-class inference. No engineering
   removes it; only backfill/reconstruction, 8h panels (√3× evidence rate), and calendar time move
   it. (validation CEILING EXPANSION; alpha F5's residual after O1.)
2. **Calendar-time forward evidence** — Stage-B clocks accrue at one day per day. The honest
   accelerants are more observations/day and not-queueing; a shorter clock or lower bar is not one.
3. **Crypto history depth** — ETH 4,008d < the 4,268-obs h=1 wall even after the gate fix for some
   cells; intraday history before ~2017 does not exist free; pre-2026 L2 is destroyed at source
   (correctly graded residual_gap).
4. **The 2-core/3.7GB box** — 13-job herds, ~8-min CI, 6.5h daily cycles and 8×max-effort audits
   contend measurably (CI flake under load reverted good code for 90 min — infra F3). Scheduling
   discipline mitigates; only spend removes.
5. **Principal-gated decisions** — LLM funding, PAT rotation, storage spend, firewall/Access
   confirmation, ntfy topic check: all externally blocked on one human (bundled into one
   PRINCIPAL_ACTION line by this synthesis).
6. **Venue rate-limits on one IP** — physics until a second egress or WS-first collection exists.
7. **What no measurement can buy back**: the ~450 destroyed regime-label days (5th sweep), the
   pre-install portion of any silently-corrupted series, and Stage-B verdict history if it was
   never archived (validation U3) — losses are permanent; fences only stop the bleeding.

---

## (E) AUDITOR DISAGREEMENTS, ADJUDICATED

1. **Execution tape frozen: benign or broken?** DI-6 read it as "event-driven, not a defect";
   data-moat DM-12 caught a live fill at 01:34 whose hedge was REJECTED and whose record appears
   NOWHERE (tape records completed pairs only; orphan detector iterates tracked symbols only).
   **Adjudicated for DM-12 — the live catch settles it**: the tape is survivor-biased by
   construction; fix is M4's attempts/partials schema + a fence on `cashcarry_error.log`. DI-6's
   benign reading is refuted.
2. **Deep-sweep cadence.** Meta M3: daily-by-fossilized-crash-loop consuming 15–19% of the brain
   ceiling, "CONFIDENCE: inferred"; infra F4: the quota referee is dead and cadence inflates by
   inference; yet this very sweep produced the launch-blocking exec findings. **Adjudicated:
   both are right — the defect is unmetered cadence with zero backpressure, not detection itself.**
   Decision rule: weekly full-8 + daily 2-subsystem rotation (infra F4's shape), switched on
   measured marginal new-finding yield (meta X8), with repair-mode backpressure (X3). The manifest
   line must carry a DECIDED cadence.
3. **Kimchi's freed slot vs the retirement invariant.** Alpha F2 wants the idle Holm slot filled
   now; validation V8 shows retirement lowered every survivor's bar (m 12→11, 2.64→2.61) against
   the code's own stated invariant. **Adjudicated: both.** Kimchi was an invalid-measurement
   retirement (contaminated timestamps), for which m-shrink is defensible — but the mechanism
   cannot distinguish that from failed-on-merits, so: fill the slot from the resurrection queue AND
   ship the ledgered RETIRED writer that keeps merit-failures in the denominator (X3-val).
4. **"Price dead / axis rich."** Alpha F1/F14: the thesis has zero surviving positive exemplars
   and the 420 were never re-scored by the fixed instrument; research-engine E-22: the factory's
   nightly banner rests on a broken constant; validation V4: even the informative gates admit
   nobody. **Adjudicated: the narrative is currently EVIDENCE-FREE in both directions, and the
   certification's welded verdict [SYNTH-VERIFIED] means the 420/0 record cannot be cited as fact
   about markets at all.** Portfolio #9 (re-score + FDR decider) is the decisive, cheap experiment.
   Doctrine keeps SCREEN-ON-DISCOVERY's mechanism-first discipline (independently justified) but
   loses the kimchi proof-text (P0 #8).
5. **Disk runway: 29 vs 32 days.** DM-1 (0.5–0.6G/day to the 80% guard) vs infra F5 (0.7G/day to
   full). Consistent within measurement noise; **use 29d — the guard trips before the disk fills,
   and the guard's response is to sacrifice the moat.**
6. **Fusion.** Data-moat K3/DM-9: the premise died honestly (5/5 negative, flagship inverted) but
   the engine still runs leak-favoring keying 5×/day and the verdict-overrule bug is latent;
   research-engine E-9: fusion_search's REFUSED is the best discipline shipped this month. **No
   conflict — adopt both**: fix the two leaky copies (M3-moat, third sweep), graveyard the five
   negatives with permanence grades, keep the registry-gated search exactly as is.
7. **Capability scores overlap** (data-intelligence 36% vs data-moat 55% over the same estate):
   different scopes — collection/freshness vs composed-information. Both stand; no reconciliation
   needed, but next week's seats should cite each other's number where scopes touch (see F).

---

## (F) RECURSIVE META — improving the audit itself

**Most value this week:** (1) **execution-growth** — found the bounded-time unbounded-severity
launch cluster (F1/F2/F8) days before keys arrive; the single highest-EV report of the sweep.
(2) **meta-and-blindspots** — quantified the repair crisis (λ/μ≈4, P(fix|survives session)≈5%),
which re-prices every other report's findings. (3) **data-intelligence** — caught the scheduler
corruption the night it started, at row-level measurement.

**Least marginal value:** infrastructure and data-intelligence independently re-derived the same
scheduler duplication (as did research-engine); data-moat and infrastructure both derived the
backup/disk finding. That is triple coverage of two findings — good adversarial confirmation, poor
marginal yield. **Fix: assign estate-level topics (scheduler, disk/backup, secrets) to ONE seat per
sweep with the others instructed to cross-cite, not re-derive.**

**Questions no longer discriminative:** "does X exist / is it configured" — every seat now runs
outcome-not-config natively; retire the config-side prompts. The FUTURE perspective is converging
on the same answer every week ("wiring, not technology") — compress it to a delta unless it
produces a novel design. Delta-tables against yesterday (research-engine's Part A pattern) beat
re-derivation and should be the standard for daily-cadence periods.

**New audit section that should exist next week:** a **LAUNCH-READINESS seat** (money-path wiring,
board-vs-reality, drill coverage) active until Gate-0 passes and the first live week completes —
this week it lived inside execution-growth and produced the top findings; make it explicit while
the stakes are highest. Honorable mention (already covered by P1 items rather than a new seat):
the read-implies-writer census becomes a mechanical fence, not audit prose.

**Genome repairs owed (M4's two cut wires):** (1) the synthesis prompt still routes portfolio items
to `improvement_inbox.md`, a store the desk's own record establishes as write-only — this synthesis
rowed the portfolio into `scripts/recommendations.py` (the de facto winning queue, M10) and wrote
the inbox entry as a pointer; the prompt edit is existing R0056. (2) Output (F) has never edited
the prompt file — `prompts/deep_sweep_core.txt` last changed 07-28 while two syntheses since
computed concrete genome improvements. Whoever owns the runner: the seat-rotation fix (E-20,
position-8 starvation) and the R0056 prompt edit are one small commit.

**Prediction registered (carried from meta P1):** of the 9 ledger rows due 2026-08-01, ≥6 will be
past-due on 08-02 unless the repair wire (P1 #6) lands first. Check `recommendations.py report` on
08-02 and log the outcome either way — it calibrates the queue model this synthesis is built on.

---

## (G) RESEARCH CAPABILITY CAGR — is the engine getting stronger week over week?

Composite, component by component (measured deltas, not vibes):

- **Experiment throughput: DOWN.** Factory tested=0 for 7 days (dedup-locked on a pool scored by
  a broken gate); campaign layer dead 39 days; only 3 axis clocks accruing. The one throughput
  positive: 8h shadow panels running (√3× evidence density) when not 418-banned.
- **Hypothesis quality: instrumentation UP, generation IDLE.** Mechanism fingerprints, §33
  generation priors, fusion-search refusal discipline all landed; but no standing generator runs
  (agenda fossil 9 days; axis_generate unscheduled; LLM lane dead).
- **Validation quality: instruments UP sharply, measurement layer LAGGING, then breaking through
  at synthesis time.** Per-candidate CSCV/Romano-Wolf live, positive controls built, event-study
  gate live, CPCV real — and the certification (never produced before this sweep) is now half-run
  with a decisive early answer. Stage-B honesty (×4.9) is the open sore.
- **Automation: MIXED.** Activation layer (intelligence cycle, 13 caps) and self-installing
  scheduler landed — and the scheduler install DOUBLED the estate (the week's largest regression);
  exit-code conflation shipped into the newest organ.
- **Knowledge reuse: WRITE-SIDE UP, READ-SIDE FLAT-ZERO.** research_memory 160 rows, daily,
  negatives first-class; knowledge engine 247-item corpus with causal edges — and every composed
  store has zero downstream readers; novelty gate still 0% paraphrase recall (day 5 open as R0004).
- **Implementation velocity: THE NEGATIVE TERM, now measured.** Same-session: excellent (9/12
  implementations within ~6h, incl. a survival rail same-day). Cross-session: ≈0.6/day against
  14/day arrivals; stock 31→41→53 across three meta audits.
- **Data coverage: PARTIAL RECOVERY.** BTC/ETH bronze revived, 146/278 symbols current (132 still
  frozen), new axes alive (Deribit surface, stablecoin, liquidations, CNY premium, ETF flows) —
  against: cross-asset/macro lake frozen 40 days, COT dead, LLM dig tier dead, AR/RU/JP/TR at zero
  artifacts.

**Net: the engine's BUILD capability compounds week over week; its CONVERT capability does not,
and the gap between them is widening at a measured +10 findings/day.** Meta's capability score
rose 45→58 in two days on real same-session wins (sentinel grading, mutex, synthesis rowing, first
completed 8/8 sweep — this one). The honest CAGR statement: **positive on capability, ~zero on
realized conversion, and the entire spread is claimable by the two P1 multipliers.** The desk does
not need to get smarter this week; it needs to get connected.

---

## DISPOSITION LOG (what this synthesis itself executed)

- Rowed the portfolio into `scripts/recommendations.py` as **R0070–R0095** (26 bundled rows, each
  naming its covered finding IDs; existing rows R0002, R0003, R0004, R0008, R0009, R0023, R0026,
  R0030, R0033, R0051, R0056, R0057 cited above, not duplicated). Mapping: R0070=P0-1 scheduler,
  R0071=P0-2 launch path, R0072=P0-3 security, R0073=P0-4 moat backup, R0074=P1-5 class check,
  R0075=P1-6 repair wire, R0076=P1-7 LLM lane, R0077=P2-9 certification/FDR-decider,
  R0078=P2-10 Stage-B honesty, R0079=P2-12 phantom-DB, R0080=P2-13 capacity, R0081=P3-14 bronze,
  R0082=P3-15 venue limiter, R0083=P3-16 VRP, R0084=P3-17 moat conversion, R0085=P3-18 feeds,
  R0086=P2-19 val small fixes, R0087=P2-20 reject rescore, R0088=P1-8b cadence/referee,
  R0089=P0-2b exec carried table, R0090=P3-21 fusion graveyard, R0091=P3-22 era archaeology,
  R0092=P2-23 alpha small (EV hindsight/intraday/mechanism-tag), R0093=P1-8c doctrine auto-log,
  R0094=P3-24 DI misc, R0095=P1-8d intelligence-cycle honesty.
- **Implemented R0051 in this session** (meta X5: today, not the due date): the retracted kimchi
  claim is corrected at both doctrine sites (`ops/principal_doctrine.txt` SCREEN-ON-DISCOVERY
  evidence text + L1.11a "proves both halves"), with the internal 420/0-as-refutation clause
  reconciled to L1.25. R0002 (bloat, 53k vs 16k guard) remains scheduled-past-due — a
  consolidation job this seat did not attempt.
- Skipped (with reason): data-moat's staged `track_findings.py` adds — each item is already
  tracked by an R-row (R0006/R0008/R0090); double-storing them recreates the M10 split-store
  defect.
- Appended the portfolio pointer to `docs/research/improvement_inbox.md` (prompt-mandated; ledger
  is canonical).
- One bundled line added to `data/PRINCIPAL_ACTION.md` (four principal-gated decisions).
- Marked the dead 07-30 validation-stats skeleton SUPERSEDED (its completing auditor's request).
- Certification run left computing; the 08:21 cron fire is the backstop; next cycle owes the T1
  read of `reports/gauntlet_certification.json`.
- **Executed the R0070 narrow disarm same-session** (the 06:40Z collision would have fired before
  any cross-session repair at measured μ≈0.6/day): ported the legacy-proven locks + `--tranche
  400` into the managed manifest lines (commits 3f6bbb3, 738a3f8), reinstalled the fenced block,
  and removed the 11 legacy duplicate lines for every MEASURED corruption vector — ingest_axes,
  dl_oi_ls_universe, both recorder respawns, ensure_recorder, daily_research_cycle (the
  signal_halflife double-append source), watchdog, venue_divergence, defi_lending, oi_ls_live,
  coinmetrics. Verified: each scheduled exactly once, `check_scheduler_manifest` manifest-only
  drift = 0, and `comm` against the pre-surgery backup (`data/crontab_backup_20260731T04.txt`)
  shows zero jobs lost. Honest incident note: the dl_oi_ls_universe removal filter briefly
  dropped BOTH twins (~1 min); the drift checker flagged it immediately and the installer
  restored it — evidence the drift fence works, and the lesson (filter legacy lines by path
  prefix, never by lock string) is recorded here. **R0070 stays OPEN** for the residual scope:
  brain-organ/kimi/max_audit/quota_verdict/organ_catchup duplicates (mutex-serialized or
  non-corrupting), the 13-job 08:21 herd stagger, dedup of the contaminated 07-30T23:00→fix
  rows, and the standing crontab-vs-manifest duplicate fence in max_audit. Active cron lines
  95→84; write-rate fences (R0081) must confirm collectors return to baseline at their next
  fires (defi :17, oi_ls :32).
