# WEAK SIGNAL REGISTRY — permanent (Charter §23)
_Individually-weak but repeatedly-observed signals, source leads, and sub-threshold hypotheses
are RETAINED here, never discarded. PROMOTION RULE: >=2 weak signals from INDEPENDENT
discovery paths converging on the same direction auto-promote to combined hypothesis
generation + full adversarial validation (EV gate -> pre-registration -> gauntlet). The brain
checks convergence each cycle during inbox triage._

## Record schema
```
### WS-<nnn> <signal>                                   [observations: N]
first-seen: <date + path>          latest: <date + path>
direction: <what it weakly suggests>
independence: <are the observation paths independent? which>
promotion-check: <converged-with: WS-nnn | none yet>
```

## CONVERGENCE CHECK LOG
_The promotion rule is only real if the check leaves a trace. Each entry: date, records examined,
promotions fired. Bar: §36 holds this file to 3 days (max_audit `_PRODUCER_CADENCE`), measured from
the last COMMIT — re-reading without recording earns nothing._

- **2026-07-26 — first check ever run, and the one-time retro-mine backfill DONE.** Seeded
  2026-07-19 and left empty for 7 days, so the "checked each cycle during inbox triage" convention
  was never once executed: with zero records the check was trivially vacuous, which is exactly how
  an empty registry hides that nobody is looking. Backfilled 4 records (WS-001..WS-004) by
  retro-mining `improvement_inbox.md`, `GAP_REGISTER.md` and this cycle's canary run. **3 of the 4
  already satisfy the >=2-independent-paths promotion rule on arrival** — WS-001, WS-003, WS-004 —
  which is the finding, not a coincidence: converging evidence had been accumulating in separate
  documents for a week with no organ to notice it. Promotions routed below. WS-002 converged on a
  weaker basis (one path re-run from a second host, plus one genuinely separate surface) and is
  recorded honestly as such rather than counted as two.

## RECORDS

### WS-001 a cross-venue premium's size tracks BARRIER HEIGHT, not price inefficiency [observations: 2]
first-seen: 2026-07-25 · EN frontier miner era-archaeology (improvement_inbox #56)
latest: 2026-07-26 · this backfill
direction: a persistent regional/venue premium is RENT on a capital-control or withdrawal barrier,
collectable only by whoever holds the specific rail — so premium magnitude should be PREDICTABLE
from the venue's control regime, before any data is pulled.
independence: YES, and unusually clean. Path A = 2013 Bitcointalk operator testimony (topics
171349, 330209): the China-premium fund's stated advantage was "as Shenzhen citizens we have
several bank accounts in Hong Kong", and the MtGox premium's binding constraint was
payment-processor reserves and withdrawal time — it resolved to zero when Gox failed. Path B = the
desk's OWN 2026-07-23 regional-premium screens, run with no knowledge of Path A: kimchi survives
(KRW capital controls, premium std 1.42%) while Japan (0.37%, free capital flows), Brazil, Turkey
(0.23%, arbs globally) and Coinbase (USD≈USDT, 0.06%) all died. Different century, different
method, same ordering.
promotion-check: **CONVERGED -> PROMOTED 2026-07-26.** Two actions, both free: (i) screen new
premium axes by BARRIER HEIGHT FIRST — check the venue's capital-control/withdrawal regime before
spending a screen slot (this ordering alone would have deprioritised JP/BR ahead of testing);
candidates named: NGN, ARS, any venue under active withdrawal restriction. (ii) STANDING
CONSTRAINT on the live kimchi clock: kimchi is legitimate as an information/timing signal and must
NEVER be sized as an arb — the barrier that creates the premium is the barrier that stops you
realising it, and the last people to treat it as riskless were holding balances at an insolvent
venue.

### WS-002 free-tier ENCLOSURE is a trend, not a series of accidents [observations: 3 across 2 paths]
first-seen: 2026-07-25 · improvement_inbox #58 (RPC probe from the VPS)
latest: 2026-07-26 · canary C9 (this cycle, different host)
direction: keyless public data access is being progressively walled; each enclosure should trigger
a TARGETED rediscovery rather than a shrug, and structurally-stable free classes (MEV-relay RPCs,
whose incentive is to RECEIVE traffic) should be preferred over goodwill-funded ones.
independence: PARTIAL — stated honestly rather than inflated. Path A (#58 VPS probe 07-25) and the
C9 canary (07-26, this host) are the SAME METHOD re-run elsewhere: that is confirmation, not
independence. The second genuine path is the vendor surface — max_audit `vendor-replacement`
flags Glassnode/CryptoQuant and Kaiko as having no ground_truth_for_diff, and CryptoCompare's
min-api went key-walled in the same window. Two paths, one of them doubly observed.
promotion-check: converged-with: none yet (holds at 2 paths, one weak). ACTED ON ANYWAY because
the action was free: canary C9 installed 2026-07-26 so the next enclosure is detected before a
collector breaks. Escalate to full promotion if a THIRD independent path (e.g. an exchange REST
endpoint moving behind auth) lands.

### WS-003 at this desk the yield is in the REPLY, not the OP [observations: 6]
first-seen: 2026-07-25 · improvement_inbox #55 (HN 9642325, depth-2 reply — "the OP had nothing,
the reply had this")
latest: 2026-08-04 · Quantopian dig, THREE more in one session: the In&Out kill is a depth-1/2
REPLY (Sarnachev's perturbation test, not the OP's claim); the fund post-mortem's surviving
diagnosis is d--b's depth-1 comment; the crash-day OHLC/margin-call execution prior sat at
DEPTH 5 (justrobert, HN 15652997) — the deepest-ranked comment was the only execution-reality
content in 94.
direction: the correction, the debunk and the practitioner detail live BELOW the top level; mining
that stops at OPs and search summaries systematically harvests the least reliable layer.
independence: YES — two different platforms (Hacker News, Bitcointalk), two different eras (2015,
2011), found in separate sessions; plus a third surface pointing the same way, #54, where source
grades written from search-engine SUMMARIES were wrong in BOTH directions and only opening the
primary artifact was right.
promotion-check: **CONVERGED -> PROMOTED 2026-07-26.** (i) Prospector query shapes must fetch
THREAD BODIES, not OP text, and rank depth-N replies rather than discard them. (ii) It is the
mechanical justification for new register row #64 (abandoned-by-capacity scanner), which is
precisely a reply-level pattern match — the two should be built together, since the fetch layer is
shared. (iii) Already hardened on the grading side by #54's `primary_artifact` requirement: a
search summary is a LEAD, never evidence.

### WS-004 the desk's estimation errors are DEFENSIVE-biased, and defensive is not safe [observations: 3]
first-seen: 2026-07-18 · gap #14 (the contaminated optimizer sized the book DOWN)
latest: 2026-07-25 · improvement_inbox #54 (both re-verified source grades were too pessimistic)
direction: when this desk substitutes an assumption for a measurement, the error lands on the
CONSERVATIVE side — and a conservative error costs compounding exactly like an unjustified sizing
clamp, while being far harder to notice because it looks like prudence.
independence: YES — three unrelated subsystems. (a) DATA GRADING: Tardis graded
`destroyed-at-source` when full-depth L2 (2,115 levels, 19.2M rows/day) is free for the 1st of
every month back to 2019-04; Kaiko's index methodology graded the same way when the rulebook is a
public unauthenticated PDF, its "$1,000-2,500/mo" price having zero primary support. (b) SIZING:
gap #14 — the 07-16 clamp capped only the UPSIDE, so a contaminated confidence quietly deployed
~25% of authorized capital and the growth_defect alert was first MISDIAGNOSED as depth-justified.
(c) COST MODEL: gap #45 — screening charged a guessed 5 bps/side against a MEASURED 0.009 bps on
BTC, ~3%/yr of phantom cost, killing genuine 0.6-0.9-Sharpe candidates at the margin.
promotion-check: **CONVERGED -> PROMOTED 2026-07-26.** The strongest record here: a systematic,
directional bias with three independent instances, and the only one that has already cost measured
growth. Promoted to a standing screen rather than a hypothesis, since it is a process defect, not a
market claim: on any growth-relevant path, a number that is an ASSUMPTION rather than a MEASUREMENT
is a defect with a direction, and the burden is on the assumption. Next targets named so this is
checkable, not a slogan: the Glassnode/CryptoQuant watchlist card (improvement_inbox #54's own
"burn down §7 next") still carries search-summary provenance; register #4's `_DEPTH_MULT` is still
hand-set; register #59's fee model is still two hardcoded VIP0 constants.

### WS-005 the desk's DETECTORS read "not measured" as "measured and fine" [observations: 5 across 5 subsystems]
first-seen: 2026-08-02 · moat closure verdict (frozen grid races coverage to 100%)
latest: 2026-08-02 · law_effectiveness (a law convictable by observing it)
direction: when a detector on this desk meets ABSENCE — no stamp, no sample, no growth, a NaN —
its default resolves to the CLEAN verdict. So the least-instrumented state of any subsystem is
also its healthiest-looking one, and the only way to trip a check is to have been measured before
and then regressed. A subsystem that never started is invisible to the organ built to watch it.
independence: YES — five unrelated subsystems, five separate authors, found on five different days:
(a) REGISTER: `register_health` sets age = -1.0 when no `Re-ranked` stamp was ever written; -1.0
fails every `age > bar` comparison, so a register never driven ONCE reported "re-rank current".
(b) §33 SELF-AUDIT: `law_effectiveness` gated conclusiveness on `min_snapshots`, which counts how
often the AUDITOR RAN — measured at exactly +1 per `max_audit` invocation. The bar was reachable
in one afternoon with no mining at all: a law convictable by observing it.
(c) MOAT COVERAGE: coverage is filled/total and total only grows while the recorders write, so a
paused recorder freezes the denominator and the miner closes the last holes to 100% — a GREEN
number produced by the exact event that ends the asset.
(d) MOAT CELLS (2026-08-01): a NaN scalar was summarised as n=1, marking a coverage cell FILLED on
a measurement never taken.
(e) CEILING CHECK: `check_no_ceiling` only interrogated organs whose source contained the string
"coverage", so two organs escaped the law by not mentioning it.
promotion-check: **CONVERGED -> PROMOTED 2026-08-02.** Five independent instances of one
mechanism is past any reasonable bar. Promoted to a STANDING SCREEN rather than a hypothesis,
because it is a process defect and not a market claim:

  > Any detector whose input can be ABSENT must state its verdict for absence EXPLICITLY, and that
  > verdict may not be the clean one. "Never measured" is a third state — not a pass, not a fail —
  > and collapsing it into pass is the single most repeated defect in this desk's history.

Already applied this cycle in five places: never-stamped is now both stale and breach; thin
evidence yields `mine-law-unjudgeable` rather than silence; a frozen tape yields
`RECORDING-STOPPED` with `coverage_is_meaningful: false`; a NaN leaves the cell open; membership
rather than a keyword triggers the ceiling check. Next targets, named so this is checkable rather
than a slogan: every remaining `if not X: return` early-exit in scripts/max_audit.py — each one is
a detector deciding that missing input means nothing to report.

RELATION TO WS-004, AND THE DIRECTIONS ARE OPPOSITE — which is why this is a separate record and
not another observation under it. WS-004 says the desk's ASSUMPTIONS err conservative (too
pessimistic, costing growth while looking like prudence). WS-005 says the desk's DETECTORS err
permissive (too optimistic, reporting health it never observed). Same root habit — substituting a
default for a measurement — pointing in opposite directions depending on whether the substitution
happens in an estimate or in a check. Filing them together would average out a sign that matters:
the fix for one is "measure it", and the fix for the other is "refuse to conclude".


### 2026-08-02 — convergence check (records examined: 5; promotions fired: 1)
Examined WS-001..WS-004 against evidence produced this cycle, and added WS-005.

- **WS-005 PROMOTED** on five independent instances of one mechanism, three of them found today
  (register never-stamped, §33 convictable-by-observation, moat frozen-grid) and two earlier
  (NaN-as-observation, ceiling keyword escape). Independence is genuine: five subsystems, five
  authors, five days. Recorded as a standing screen, with its opposite-signed relation to WS-004
  stated rather than merged away.
- **WS-002 unchanged at 2 paths, one weak.** Today's canary run measured 0/9 endpoints reachable,
  which is NOT evidence of free-tier enclosure — it is this container's egress proxy, a fact about
  the observer. Counting it would have inflated a real signal with a self-inflicted one, which is
  the exact error WS-005 describes. Explicitly declined.
- WS-001, WS-003, WS-004 already PROMOTED 2026-07-26; no new evidence this cycle, so no re-weighing.
  Re-litigating promoted records without new evidence is how a convergence check becomes a ritual.

### WS-006 cross-asset early-warning rotation may have a crypto analog [observations: 1]
first-seen: 2026-08-04 · EN frontier miner, Quantopian In&Out thread (mechanism: early-value-chain
assets — base metals, industrials, short-rate yields — lead broad risk assets at ~3mo horizons)
latest: same
direction: if industrial-demand / funding-cost proxies genuinely lead equities, they may lead BTC
risk-off too (crypto responds to real-yield and liquidity shocks). The INSTANCE is graveyarded
(`inout_early_warning_rotation_fragility`, parameter-fragile) — this signal is only the residual
GENERAL question, and it must clear the de-contamination gate (the desk's own finding: no SLOW
price alpha at daily resolution survives — a cross-ASSET input is the one variant not yet tested).
independence: single path so far. NOT promotable; logged so a second independent observation
(e.g. a macro-lead paper or another region's era lore) can converge on it.
promotion-check: none yet.

## ltw_ewvw_significance_flip (2026-08-04, CN frontier miner s2)
Independent CN replicator (GitHub user LeoLi2002, own unseen code, commenting on the YungFuu
HKU replication of Liu-Tsyvinski-Wu 2022) reports that in crypto cross-sectional factor
portfolios, **equal-weighting vs value-weighting flips factor-portfolio significance and even
the SIGN of significant returns** (「甚至会出现显著性的反转，组合收益率由正显著变为负显著」).
Mechanism if real: the "factor" return is carried by the microcap/illiquid tail that EW
overweights — a capacity/implementability red flag for any EW crypto factor result, including
the desk's own crypto_xsec screens if any are EW. The HOST repo's own momentum test is
invalidated by OP-047 binning forensics (see graveyard `ltw2022_crypto_momentum_nonreplication_claim`);
this comment is the one piece of that thread with independent evidentiary value.
independence: single path (one practitioner's report; the host repo's code does NOT corroborate
it because the host code is void). Converges with the general SMB-in-crypto capacity literature
but no second direct observation yet.
promotion-check: none yet. Promotable to a checkable hypothesis the day the desk's crypto_xsec
weighting scheme is audited: re-run any live cross-sectional screen VW vs EW and compare signs —
if a desk factor flips, this stops being weak.

## 2026-08-04 — barrier-rent infrastructure is being productized and EXPORTED across EM corridors (RU miner s1-on-branch)
Source: forum.bits.media section 74 (P2P) live census, 2026-08-04 — public service ads only,
no closed-group material. A single "P2P процессинг" recruiting ad prices one integrated
gray-payments stack across RUB, TRY, KZT, INR, AZN, PKR, SAR, AED, EGP, KRW simultaneously;
several ads quote explicit rent ladders ("AML < 25%", corridor fees) with USDT-TRC20 as the
universal settlement leg and Telegram bots as the interface.
Signal if real: the 2022 sanctions-rail tech (built to move RUB past a double barrier) is now
sold as generic corridor infrastructure to OTHER barrier currencies. Productized rent
infrastructure should COMPRESS cross-EM premium dispersion toward a common rent floor — i.e.
fiat-barrier premiums (TRY, EGP, PKR, NGN analogs) become more alike over time as the same
stack serves them, and premium MAGNITUDE becomes less about local barrier idiosyncrasy and
more about corridor-tech pricing. Relevant to the desk's premium-family priors (kimchi as
information signal; premium=barrier-rent law, sixth instance).
independence: single path (one board's ad census, one date). Needs a second observation —
e.g. the same multi-corridor stacks advertised on non-RU boards, or measured convergence in
public premium series across EM pairs.
promotion-check: none. Promotable the day two independent premium series (licensed, public,
non-sanctioned venues) show dispersion compression coinciding with corridor-tech spread; until
then this is structure knowledge, not a hypothesis.
