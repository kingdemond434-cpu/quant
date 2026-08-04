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

### WS-005 cross-asset early-warning rotation may have a crypto analog [observations: 1]
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
