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
post-promotion confirmation: 2026-07-28 · EN session D, Quantopian In&Out thread — the OP was
absent from the capture entirely, yet EVERY load-bearing finding lived in replies: the bond-beta
decomposition (R15/R40/R41), the rebalance-artifact catch (R82/R83), the ratio-instability
demonstration (R88), and the complete final code verbatim (R106). Fourth platform, fourth era,
same direction — and this time the OP was not even needed.
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

## 2026-08-04 — KR corridor: per-coin premium DISPERSION is retail-tooled, and the route layer is open-source (KR miner s1-on-branch)
first-seen: 2026-08-04 · velog @hansanghun "코코아 제작기" (coincoin.kr, OSS github.com/joshephan/cocoa,
built live on YouTube Feb-2025, 3,128 views) — a public route-optimizer computing WHICH coin to send
KRW→overseas with least (per-coin kimchi premium + fees). Archived: data/velog_kr_quant_posts.jsonl.
direction: the KR corridor's rent-collection layer is now productized RETAIL tooling (the KR twin of
the RU corridor-tech-export signal one section up — two regions, same shape, same day). If retail
route-optimizes across transfer coins, per-coin premium DISPERSION should compress toward fees faster
than the LEVEL compresses, and flow should concentrate in the cheapest-route coins (XRP/TRX class).
Desk hook: the live kimchi axis reads the LEVEL; dispersion-across-coins is an untested second moment
with a stated mechanism and a named counterparty (route-optimizing retail).
independence: single instance (one tool, one region) — but the RU export signal is an independent
second region for the CLASS (barrier-rent tooling productization).
promotion-check: pre-registerable once a per-coin KR premium panel exists (Upbit/Bithumb keyless REST
already provide the legs; construction must declare FX timestamp alignment per the standing trap).
Note the tool itself crawls Google Finance USD-KRW — retail's FX leg is a DIFFERENT timestamp than
any daily FX fix, i.e. the crowd's own premium number is not the desk's number.

## 2026-08-04 — KR retail order-flow stack is COMMODITIZED at 10s–1m resolution, and its folk liquidation-long is self-refuted (KR miner s1-on-branch)
first-seen: 2026-08-04 · velog @vividbaek CoinWhale series (12 parts, 2026-04→07): Kafka 18-topic +
ClickHouse + Binance Vision S3 backfill pipeline, signal taxonomy CVD_BULL/LIQ_CASCADE/FUNDING_EXTREME/
OI_SPIKE, shadow-mode + promotion criteria (DD, fees, latency) — a retail mini two-stage discovery.
Archived: data/velog_kr_quant_posts.jsonl.
direction: (a) CROWDING — the short-horizon order-flow family (CVD/OI/liquidation/funding follow) is
now retail-commoditized in KR on the exact free sources the desk holds; treat naive constructions in
this family as crowded, demand orthogonality. (b) FREE PRIOR — his own backtests: folk "long the
liquidation cascade" = 45% WR (BTC, 10s bars, 10d, costless) — the KR folk belief INVERTED on its
believer's own data; CVD>threshold long = 50.2%→60.9% WR moving threshold 50→300 (threshold-regime
fragility); OI-drop short 57.6%. All screen-grade, one symbol, 10 days, no costs — priors, not results.
(c) GENRE-EVOLUTION (3rd region after RU/CN): KR retail writeups now ship exit-reason attribution,
single-factor WR discipline, backtest-live parity, survivorship/look-ahead/cost checks (velog @papapat
ran an honest 0-for-6 falsification of KR-equity folk beliefs as a NON-developer using Claude Code) —
the "pink backtest" tell is obsolete; source-audit must move to meta-level defects, and the marginal
retail participant's methodological competence is rising fast (tooling democratization).
independence: two authors, one platform, one region; genre claim corroborated by RU s1-on-branch +
CN s3 independently.
promotion-check: none as-is (crowding/prior knowledge, not a hypothesis). The liquidation-echo prior
becomes testable only inside the desk's own liquidation-listener clock (GAP row 76 forward clock).

## 2026-08-04 — hours-band reversion pockets MIGRATE across timeframes, and 2024-03 closed one (JP miner s1-on-branch)
observation (n=1 lineage, 3 corroborating deaths): the richmanbtc ATR-limit reversion family
did not die once — it died PER TIMEFRAME. 15m incarnation dead ~2022-23 (community consensus +
desk C62 kill); a 12H incarnation then worked 2022-mid→2024-03 with positive-fee modeling and
3 months of live confirmation including a 90%-WR month, dying 2024-03 (chanta, Advent Calendar
2024 d22 — graveyard jp_atr_limit_reversion_timeframe_migration). Same-dated deaths: SFD
abolished 2024-03; desk's own H8 screen this run shows the 24h-lag contrarian's sign FLIPPED
to momentum post-2024-04 (SCREEN-WEAK both directions). Pattern claim: the reversion band
relocates across bar sizes as each incarnation crowds/decays, and 2024-03 is a JP-documented
regime boundary where the hours-band pocket closed.
independence: chanta (live-traded), Hoheto lineage (published anomalies), desk screen — three
routes, one region's corpus + own data.
promotion-check: NONE as-is — no mechanism predicts WHICH timeframe hosts the band next, so
there is nothing pre-registrable; the signal's use is as a PRIOR: (a) any revived
ATR-limit/reversion claim must name bar size + post-2024-03 evidence; (b) if a future screen
finds an hours-band reversion cell alive, check whether it is this band relocated before
calling it new. Converges with the desk's low-pass lesson (daily price alpha dead ≠ all price
alpha dead) from the opposite side: the fast pocket existed, and it CLOSES too.

## WS-006 — THE MICROSTRUCTURE EDGE IS REAL AND SMALLER THAN THE SPREAD (2026-08-07, mined from committed data)

**Mined from `docs/research/moat_microstructure_screen.json` — an existing, committed, previously
unmined 450-cell measurement.** No new data was collected. This is what the desk already had and
had not read.

**THE SIGNAL IS REAL.** `flow_momentum @ 60s` clears Holm across 45 symbols: mean IC **+0.0069**,
cross-symbol **t = +3.95** against a Holm bar of 2.81. That is a genuine, multiple-testing-corrected
positive result on order-flow momentum, and it is the only one of ten arms that clears.

**IT DOES NOT PAY.** That same arm nets **−0.656 bp per bar**, with **1 of 45 symbols net-positive**.
Every one of the ten arms has a negative mean net. The effect is smaller than the cost of
expressing it.

**NINE CELLS PASS A FULL NET/POWER/DECONTAMINATION FILTER, AND THEIR COMMON PROPERTY IS NOT THE
SIGNAL.** Filtering all 450 for `net_positive AND powered_honest AND decontam_passed` leaves 9.
They span four different constructions and both bar sizes — no construction dominates. What they
share is the book:

    median spread, the 9 survivors      0.053 bp
    median spread, the other 441        2.520 bp      (48x wider)
    BTCUSDT + ETHUSDT                   6 of 9

**So the finding is about LIQUIDITY, not about order-flow imbalance.** The edge exists everywhere
and clears costs only where the spread is effectively zero. Reported as a signal discovery it would
be false; reported as a liquidity boundary it is true and useful.

**AND THE NINE HAVE NOT FACED THE BAR THEY WOULD HAVE TO CLEAR.** They were selected on net P&L out
of 450 cells with no deflation applied — √(2 ln 450) = **3.50**. The panel test IS the correctly
corrected statistic, and it clears exactly one arm, which loses money. Every one of the nine is
additionally labelled **SCREEN-WEAK by the harness's own verdict**: they are net-positive and
statistically weak, which are different populations, and taking their intersection as a survivor
set would be selection on the axis that was not tested.

**THE LEAK SIGNATURE IS SUBSTANTIAL AND SEPARATE.** 105 of 360 leak probes (**29%**) collapse under
a one-bar lag — the apparent edge disappears when entry moves one bar later. That is a harness-wide
property worth its own investigation, and it bounds how much of the +0.0069 should be believed.

**WHAT THIS IS WORTH, stated without inflation.** It is not a survivor. It is a **measured boundary
condition**: the microstructure family pays only at the very top of the liquidity distribution, and
that is precisely where the desk's carry book already trades — so the marginal opportunity is
narrower than the raw 36 SCREEN-INTERESTING count suggested. It also gives the first real
independent-mechanism count on this desk: **one mechanism (order-flow momentum), not thirty-six
candidates.**

**NEXT TEST, if the family is pursued:** restrict to the top decile by book depth, re-run with the
trial budget declared for THAT universe only, and require the net-positive arms to clear the
deflated bar rather than be selected by it. Any other continuation is fitting the 450.

### WS-007 issuer-hedging flow from packaged short-vol products is a standing crypto flow axis nobody on the desk owns   [observations: 1]
first-seen: 2026-08-12 EN frontier miner sG (NP 161162, sas reply: Napoleon/reverse cliquets "quite notorious" — retail-packaged short-vol whose issuer hedging flows became predictable)
latest: same
direction: the crypto analogue is DOV/covered-call-vault settlement flow (weekly auction pressure on Deribit vols) + dual-currency-note hedging on CEXs; the TRADFI version was documented tradeable era lore. Desk expression unclear (no options venue) — perp-level vol/funding patterns around vault settlement windows would be the testable shadow.
independence: single path (one 2012 NP reply). Known-published for 2021-22 DOVs (Paradigm/QCP commentary) ⇒ crowded_known prior applies to any direct port; the WEAK part worth retaining is the perp-shadow expression, which nobody published.
promotion-check: converged-with: none yet. If a second independent path (different region/era) names vault-settlement flow bleeding into PERP funding/vol, promote to hypothesis with the event-study gate (libs/validation/event_study.py — it is event-shaped, ~weekly).

### WS-008 funding-settlement phase reaches INTO the liquidation boundary — settlement-time liquidation clustering on the paying side   [observations: 1]
first-seen: 2026-08-12 CN frontier miner (8btc thread-166158, 2018-05-08, BitMEX era: practitioner explains an instant-on-releverage liquidation with "爆仓线好像要算一期的资金费率" — the liquidation line embeds the upcoming funding period; at max leverage the margin tier + funding-due puts the liquidation price through the current mark)
latest: same
direction: on venues where funding settles against margin balance (Binance perps), positions near maintenance on the PAYING side get tipped at the settlement stamp ⇒ liquidation intensity should CLUSTER in the minutes after funding settlement, conditional on side and proximity-to-liquidation, strongest on low-OI tails where the liquidation bands are close to the book. The desk holds both halves of the instrument: its own liquidation tape + libs/research/funding_clock.py (L1.47's one clock). Event-shaped ⇒ event-shaped gate (libs/validation/event_study.py), never a continuous screen.
independence: single path (one 2018 CN forum reply explaining BitMEX margin arithmetic). The BitMEX-specific rule (funding in the liquidation calc) is venue arithmetic, not alpha; the WEAK part worth retaining is the settlement-phase→cascade coupling as a TIMING conditioner for the desk's existing liquidation/cascade family — L1.47 already proved desk-side closes cluster in the final pre-settlement hour, so the flow exists; the question is whether forced flow (liquidations) shares the phase structure.
promotion-check: converged-with: none yet. Promote to hypothesis when EITHER (a) a second independent path (any region/era) names settlement-time liquidation clustering, OR (b) a desk event-study on own liquidation tape around funding stamps (tails vs majors, paying side vs receiving) shows the clustering at pre-registered window/threshold — that study is one afternoon against data already collected.

### WS-009 era-venue public tape is DISPLAY-ROUNDED and book-truncated — a provenance prior for every archived pre-2017 tape   [observations: 1]
first-seen: 2026-08-12 RU frontier miner s2-on-branch (forum.btcsec.com topic 8115, May-2014, primary trade/book captures in-thread: BTC-E trades printed at prices ABSENT from the displayed book ("магический rate 10.53"), amounts rounded vs book precision (10.0657 vs 10.06566151), a filled level's displayed size INCREASING through a trade; reply 4: the venue's own trade API returned a ROUNDED fill while the account settled the unrounded amount; replies 5+9: MetaTrader-bridge orders were matchable but INVISIBLE in the public depth — a second order-entry channel outside the displayed book; topic 4382 reply 11: BTC-E served NO history API, so ALL era history is self-collected or derived from this same rounded public feed)
latest: same
direction: this is the L1.46 provenance family at the PRECISION layer rather than the clock layer: any archived BTC-E (and by prior, era-venue) tape carries (a) display-rounding of price/size, (b) a hidden-liquidity channel making displayed depth a loose LOWER bound, (c) taker-dominance by construction (the era's retail bots were taker-only by design — resting orders "freeze capital", topic 4382 reply 6 — and BTC-E charged flat 0.2% with no maker rebate). Consequence for the desk: era backtests reconstructing queue position, book-imbalance features, or fill prices from such tape are structurally optimistic/contaminated; any era-tape screen must declare this in its cost/leak model.
independence: single path (one 2014 RU thread, but with in-thread primary captures — closer to a measurement than a claim). The desk's own L1.45 lesson ("a book-walk measures DISPLAYED depth") is the live-market twin derived independently from own fills.
promotion-check: not a tradeable signal — a DATA-QUALITY prior. Consume it wherever an era-tape axis is screened (the moat's historical-monopolisation program); if a second era venue's hidden-channel/rounding evidence surfaces, harden from prior to rule in the era-tape screen harness.

### WS-010 strategy-file monoculture: mass-distributed identical rule-sets synchronize retail flow   [observations: 1]
first-seen: 2026-08-12 RU frontier miner s2-on-branch (forum.btcsec.com topic 4382, Jan-2014, page 1 of 75: the 1b-bot vendor shipped downloadable strategy FILES ("Скачиваем стратегию с сайта... работала на реальных деньгах, практически безрисковая") loaded verbatim into identical rule-table engines (book-imbalance thresholds like deltaVolume5m, 5× bid/ask volume ratios, wall-detection with spoof-ignore limits); N buyers ran the SAME triggers on the same venue; group-buys ("складчина") widened distribution further)
latest: same
direction: identical-rule herding turns a private trigger into a synchronized flow event: when the shared condition fires, the crowd's orders arrive together, amplifying imbalance cascades at exactly the thresholds the files encode. Modern echoes with the same structure: copy-trading leaders on Bybit/Binance/BingX, Telegram signal channels, TradingView public scripts with alert-webhook bridges (the RU diaspora census already found webhook bridges standard tooling). Desk-testable shadow: order-flow bursts time-clustered around round-number indicator thresholds on high-copy-trade symbols; also an ecology prior — any public backtest genre popular enough to be mass-copied degrades ITSELF (crowding-at-threshold), which is a decay mechanism to price into any mined-from-public mechanism.
independence: single path (2014 RU vendor thread; the era's monoculture is documented, its flow effect is inferred, not measured). Adjacent but distinct from known copy-trading literature: the WEAK part is threshold-synchronization as a MEASURABLE microstructure event, not the social fact of copying.
promotion-check: converged-with: none yet. Promote to hypothesis if a second independent path names threshold-time flow clustering on copy-traded symbols, or if a desk look at trade-intensity around canonical indicator levels (from own tape) shows the clustering; event-shaped ⇒ event-study gate.

### WS-011 venue OUTAGE freezes the tape and manufactures a cross-venue spread — a provenance prior for every KR premium/spread axis   [observations: 1]
first-seen: 2026-08-12 KR frontier miner s2-on-branch (Ppomppu 가상화폐 era corpus, intra-KR basis threads mined to comment depth). Load-bearing primary: **52389** (2018-01-11, the Park Sang-ki shock day) — OP: "항상 업비트가 더 높았는데, 아까전 폭락할때 **빗썸 서버 터지면서 멈추더니** 하락않고 정체되어 이젠 거의 14만원 차이 나네요" (Upbit was ALWAYS higher, but during the crash **Bithumb's server blew up and froze** — it did not fall, it stalled — and now they are ~140,000 KRW apart), with independent in-thread corroboration from a commenter: "서버다운 됐어요" (the server went down). Supporting: **5835** (2017-12-09) a routine ~300k KRW Upbit-vs-Bithumb gap (~1.6% on a ~18.5M KRW BTC); **6465** (2017-12-10) asks why 빗썸 is dearer on everything — i.e. the persistent intra-KR sign was BITHUMB-rich in Dec-2017 and the same board reports UPBIT-rich by Jan-2018, so the intra-KR sign is REGIME-DEPENDENT, not structural.
latest: same
direction: a halted or lagging matching engine keeps printing its last trade, so the stale venue's close does not move while the live venue's does — and the difference is booked by any downstream consumer as a *spread*. The reason this is not ordinary noise: **outages are correlated with the treatment.** Venue tapes freeze during crashes and volume spikes, which is exactly when premium extremes, rail-state transitions and the events these axes study occur. A confounder aligned with the event does not average out; it biases the event window specifically. This is the L1.46 tape-provenance family reached by a different mechanism than the clock layer (WS-009 = display-rounding; kimchi retraction = clock mislabeling; this = liveness), and it is the one that makes a DEAD venue look like a PRICED one.
desk exposure (checked this session, not assumed): `libs/research/upbit_data.py:64 upbit_daily_utc_keyed` returns `{UTC date: trade_price}` and **discards `candle_acc_trade_volume`** — the one field in the payload that distinguishes "price stable" from "venue not trading" is dropped at the boundary. And `data/kr_perasset_premium_history.jsonl` (3,008 rows, 2018-05-04→2026-07-28) carries **`fx_ffill`** — a staleness flag for the FX leg — with **no equivalent field for the venue-price leg**. The two legs of the same ratio are instrumented asymmetrically, and the uninstrumented leg is the one the era corpus says froze.
honest qualification (stated so a later reader does not over-read this): the era evidence is INTRADAY and the desk's premium series is DAILY, so an outage contaminates a daily close only when it spans the sampling instant — the daily exposure is strictly weaker than the era anecdote implies. 2017-18 KR venue reliability is also not 2026 reliability. This is a prior to MEASURE, never one to assume forward.
independence: single path, but with dual in-thread corroboration (OP + an unrelated commenter independently naming the outage) rather than one voice. Converges in FAMILY with the desk's own kimchi ~73%-timestamp-artifact retraction and with WS-009, all three saying the same thing about archived venue tape from three unrelated regions/eras: the tape's defects are correlated with the events it is used to study.
promotion-check: not a tradeable signal — a DATA-QUALITY prior, and it gates axes the desk is collecting RIGHT NOW (card #26 KR venue-state, `kr_rail_state_transition_global_leg`). Decisive test is one afternoon on data already held: retain `candle_acc_trade_volume`, flag zero/low-volume and flat-close days, then measure what share of the 3,008-row premium series sits on such days and whether those days cluster at |premium| extremes. If they do, every KR premium result to date owes a re-read; if they do not, the prior is retired for the daily axis and retained for any intraday build.
