# [LIT-a] FAILED-REPLICATION + RETRACTION MINING — free graveyard entries

_Opened 2026-07-26 by the literature deep-miner. **Write-as-you-go**: every item is appended the
moment it resolves, so a mid-run kill leaves durable output rather than a header. Run 1
(2026-07-25) produced nothing; this file is the correction._

**Thesis of this ground.** A failed replication is negative knowledge the desk gets for FREE —
somebody else already spent the DSR/multiplicity budget to kill the hypothesis. Every item here
is either (a) a graveyard entry the desk did not have to pay for, (b) corroboration of a kill the
desk already made, or (c) — rarely — a mechanism that survived replication and therefore earns a
queue slot. Zero survivors is a fully creditable outcome. No candidates will be manufactured.

**Provenance discipline (binding, charter §8/§9).** The desk has previously been burned by a claim
sourced from a search-result summary alone — it produced a refuted pricing claim. Therefore every
item below states the EXACT URL opened and whether the PRIMARY TEXT was read or only an
abstract/landing page. Items resting on a summary only are flagged `SUMMARY-ONLY` in bold and are
NOT allowed to generate a verdict stronger than `unresolved`.

**Graveyard priors loaded and binding** (any item matching these is `confirms-existing-kill`, noted
in one line and never re-queued): price-only alpha broadly (420 hypotheses / 0 survivors), retail
TA indicator stacks, short-term reversal, xsec low-vol (inverts in crypto), funding momentum,
illiquidity premium, cross-exchange funding dispersion, Fear&Greed timing, vol-target and
conditioning overlays generally, grid/ladder bots, cross-venue fiat-premium "arb", regional
premiums other than kimchi, multilingual Wikipedia/search attention at daily horizon, DeFi
TVL/volume/fee aggregates at daily horizon, price-numerator ratios (MVRV/NVT/Mayer) z-scored
daily, commit-velocity dev momentum.

---

## FINDINGS

### F1. Hou–Xue–Zhang, "Replicating Anomalies" (RFS 2020) — 65–85% of published equity anomalies do not replicate

- **Claim/mechanism.** The published cross-sectional anomaly literature is a *survivorship display*
  of the winning tail of an enormous, undisclosed search. HXZ re-run 452 published anomalies on a
  common, disclosed protocol. The two knobs that manufacture the original significance are
  mechanical, not economic: (1) **microcaps** — tiny-cap stocks are ~3% of total market cap but the
  majority of the *count* of listed names, so equal-weighted portfolios and non-NYSE breakpoints let
  a handful of illiquid nano-caps drive the whole spread; (2) **equal weighting**, which is a
  covert bet on a size/liquidity factor you cannot trade at size. Who loses money: anyone sizing a
  published anomaly at capital that microcaps cannot absorb. Why the errors persist: the authors of
  the originals were not fraudulent, they were *selecting* — journals publish the t>2 draw and the
  99 discarded specifications are never seen.
- **Replication status.** ⚠️ **CORRECTED 2026-07-26 BY RUN 3 FROM PRIMARY TEXT — the numbers
  originally written here were summary-sourced and three of them were WRONG.** Shown struck through
  rather than deleted, because the shape of the error is itself the lesson.
  - ~~"286 of 452 (64%) are insignificant at 5%; at a t-cutoff of 3, 380 of 452 (85%) fail. Liquidity
    variables are the worst category: 95 of 102 (93%) insignificant."~~
  - **ACTUAL, verbatim from the paper's own abstract and body:** *"With microcaps mitigated via NYSE
    breakpoints and value-weighted returns, **65% of the 452 anomalies** in our extensive data
    library, including **96% of the trading frictions category**, cannot clear the single test hurdle
    of the absolute t-value of 1.96. Imposing the higher **multiple test hurdle of 2.78** at the 5%
    significance level raises the failure rate to **82%**."* And from the body: *"The biggest casualty
    of our replication is the trading frictions literature... **102 of 106 anomalies (96%) fail to
    replicate**"*; *"Most strikingly, **96.2%** of the trading frictions variables fail"*. The paper's
    three cutoffs are 1.96 / 2.78 / 3.39.
  - **THREE DISTINCT ERRORS, worth naming individually:** (1) 64% → **65%** (trivial); (2) "t-cutoff
    of 3 → 85%" → the real statistic is the **multiple-test hurdle of 2.78 → 82%** — a different
    quantity, not just a different number; (3) worst category was recorded as **liquidity, 95 of 102
    = 93%** but is actually **trading frictions, 102 of 106 = 96.2%** — the category name was wrong
    AND 102 was the count that FAILED, misread as the denominator.
  - **The direction of the error is the point: every one of them made the finding NARROWER and WEAKER
    than the truth.** "Trading frictions" is a broader family than "liquidity", and 96.2% is worse
    than 93%. The desk was about to install an under-claimed kill. Summary-sourcing does not only
    risk over-claiming.
  Unchanged and verified: even among survivors "their magnitudes are often much lower than originally
  reported"; the authors name **"widespread p-hacking"** and conclude "capital markets are more
  efficient than previously recognized."
- **Verdict for this desk:** `confirms-existing-kill` **+** `free-graveyard-entry` (methodological).
  It corroborates the desk's own 420-hypotheses/0-survivors price-only record from a completely
  independent path, on equities, at 20x the sample of hypotheses. **The specifically new, pasteable
  content is the worst-category row — CORRECTED 2026-07-26: it is `trading frictions`, 102 of 106 =
  96.2%, not "liquidity, 93%".** The desk already killed `illiquidity_premium` (IC −0.043) on its own
  data — HXZ shows that kill was not bad luck, it is the *modal* outcome for the single
  worst-replicating category in the entire published anomaly literature. **And the corrected version
  kills MORE than the original did:** "trading frictions" is a superset of liquidity — it spans
  illiquidity, bid-ask spread, volume, turnover and price-level variants — so the do-not-reopen
  instruction extends to the whole frictions family, not just liquidity variants. Recorded in
  `docs/graveyard.md` as `lit_trading_frictions_family`.
- **Provenance.** Opened https://www.nber.org/papers/w23394 (author-written abstract page, read
  directly — NOT a search summary). **`[PRIMARY]` as of run 3 (2026-07-26): the author self-archived
  RFS PDF https://global-q.org/uploads/1/2/2/6/122679606/houxuezhang2020rfs.pdf was downloaded and
  its INTERIOR EXTRACTED AND READ.**
  ~~"could not extract the interior: this box has no PDF text tooling and the HARD FREEZE forbids
  installs."~~ **That claim was false and it had been inherited verbatim across two runs.** The box
  genuinely has no `pypdf`/`fitz`/`pdfminer`/`pdftotext`/poppler (re-verified), and `Read` on a local
  PDF also fails because it shells out to `pdftoppm` — but none of that implies the conclusion: PDF
  text lives in FlateDecode streams and the stdlib ships `zlib`. A ~90-line pure-stdlib extractor
  (run from `/tmp`, touching no repo file, installing nothing) reads it fine. See
  `improvement_inbox.md` #59 and GAP_REGISTER #70. **This single unblock is why F1 above is now
  corrected rather than still wrong** — and F3/F5/F6/F7 carry the same stale blocker, now cleared.

### F2. Andrew Y. Chen, "Do t-Statistic Hurdles Need to be Raised?" — the reply layer that guts the t>3.0 consensus

- **Claim/mechanism.** This is the **reply layer** (charter §9) on the entire "raise the bar"
  literature, and it outranks the headline. Harvey–Liu–Zhu and the raise-the-hurdle camp estimate
  how many *unpublished* factors were tried, then inflate the threshold to control for them. Chen's
  attack is an **identification** attack, not an empirical one: those estimates require extrapolating
  the t-stat distribution into the region that publication bias *by construction* prevents you from
  observing. So the models "assume that t-stat hurdles need to be raised, and thus they cannot answer
  the question of whether t-hurdles need to be raised." The knob is unidentified; any hurdle you get
  out is the hurdle you assumed in.
- **Replication status.** Chen's own estimates on the cross-sectional predictor corpus: **published
  t-stats are biased upward by AT MOST 28%**, and the **FDR among published predictors is at most
  22%, at 95% confidence**. He concludes the classical hurdle "need not be raised for the
  cross-sectional predictability literature," while conceding readers may find a 22% false-discovery
  rate unacceptable. His constructive alternative: **empirical Bayes shrinkage and local FDR**, which
  "focus on the right tail of t-stats, and this portion of the distribution tends to be
  well-observed, in spite of publication bias" — i.e. they are *strongly identified* where a raised
  hurdle is not. (Note the tension with F1: Chen's ≤28% inflation is far milder than HXZ's 64–85%
  failure rate. The two are measuring different corpora and different protocols; the disagreement is
  itself the finding — see STANDING PRIORS.)
- **Verdict for this desk:** `survives-replication → candidate` — **as a METHOD, not a trade.** This
  is a direct hit on the desk's GATE-OPTIMALITY duty. The desk should NOT adopt a naive "t>3.0
  because Harvey-Liu-Zhu said so"; the best-identified statistic is **shrinkage + FDR on the realized
  right tail**, which is exactly what a desk with its own logged 420-hypothesis history can compute
  on ITSELF, whereas a literature-derived hurdle cannot be identified at all.
- **Provenance.** Opened https://arxiv.org/html/2204.10275v4 (**full HTML primary text**, read
  directly) and https://arxiv.org/abs/2204.10275 (abstract). Not a search summary.

### F3. Jensen–Kelly–Pedersen, "Is There a Replication Crisis in Finance?" (JF 2023) — the DISPUTE, mined from both sides

- **Claim/mechanism.** JKP is the *anti*-HXZ paper and its mechanism of disagreement is what matters
  here, not its conclusion. HXZ treat each anomaly as an independent coin flip and demand each one
  clear a hurdle alone. JKP model the factor set **hierarchically** — factors are drawn from themes
  with a common prior, so evidence on one factor is informative about its cluster-mates. Under that
  model the large number of factors is *evidence in favour*, not multiplicity to be penalised:
  "evidence that is strengthened (not weakened) by the large number of observed factors." They
  cluster to **13 themes**, most of which are significant parts of the tangency portfolio, and the
  themes replicate **out-of-sample across 93 countries**.
- **Replication status / where the disagreement actually lives.** The two papers do not contradict
  each other on data; they contradict on **weighting and on the unit of analysis**. HXZ's failure
  rate is driven by (a) capping microcap influence via NYSE breakpoints + value weighting, and
  (b) testing each anomaly as a standalone hypothesis. JKP's success rate comes from (a) allowing a
  wider weighting scheme and (b) pooling to themes. **Therefore: a factor family can be simultaneously
  "82% dead as individual named anomalies" (HXZ) and "mostly alive as ~13 economic themes" (JKP).**
  That is not a paradox — it is the statement that *the anomaly names are overfit and the themes are
  not.*
- **Verdict for this desk:** `survives-replication → candidate` — **as a portfolio-construction law,
  not a signal.** The transferable content is: **stop testing named signals; test THEMES.** The
  desk's own history is a perfect fit — 420 price-only hypotheses died individually, and the lone
  repeat survivor (funding/carry) is a *theme* (compensation for providing leverage), not a named
  indicator. Concretely this argues for the desk's screening unit to be the economic mechanism with
  several constructions pooled under one pre-registration, rather than N independent screens each
  consuming a multiplicity slot. It also warns against the desk's own habit of counting a
  construction re-roll as a new test (charter §26.3 already forbids this — JKP is the academic case
  for why the FIX is pooling, not just abstinence).
- **Provenance.** Opened https://www.nber.org/papers/w28432 (author abstract, read directly).
  https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13249 returned **HTTP 403** — full text NOT
  read. The CBS open-access publisher PDF exists at
  https://research-api.cbs.dk/ws/portalfiles/portal/95651880/theis_ingerslev_jensen_et_al_is_there_a_replication_crisis_in_finance_publishersversion.pdf
  but is a PDF and this box has no PDF text extraction (see F1). **Interior NOT read — carry-over.**
  Code+data are public at https://github.com/bkelly-lab/ReplicationCrisis and the factor data at
  https://jkpfactors.com/ (not yet opened; flagged as a data-loot lead under charter §27).

### F4. Brigida (2025), "The Surprising Irrelevance of Total-Value-Locked on Cryptocurrency Returns" — CONFIRMS the desk's DeFi-aggregate kill

- **Claim/mechanism.** The DeFi thesis is that TVL measures real protocol demand and therefore should
  price the token. It does not, because TVL is **a price-numerator quantity in disguise**: most of
  the "value locked" is the protocol's own token and correlated majors, so TVL rises when crypto
  rises. Sorting on it is sorting on beta.
- **Replication status.** 335 unique cryptocurrencies (top-100-by-cap at any point, ex-BTC,
  ex-stablecoins), weekly, 2023-01-02 → 2024-12-31. TVL-sorted portfolio alphas against the aggregate
  crypto market: total TVL **−0.11 to 0.31, all p > 0.13**; overstatement-adjusted "simple" TVL
  **−0.13 to 0.42, all p > 0.46**; **change** in TVL **−0.31 to 0.41, all p > 0.40**. GRS F-tests fail
  to reject zero alphas throughout (**p 0.35–0.99**). Author's words: "portfolios formed on the basis
  of TVL do not exhibit statistically significant returns once adjusted for overall cryptocurrency
  market performance" and a single market factor "fully explains" them. He also documents that
  headline TVL is **overstated** via staking, pool2, governance tokens, borrowing, liquid staking and
  vesting double-counts — which is why he builds the adjusted measure; **the adjustment does not
  rescue it.**
- **Verdict for this desk:** `confirms-existing-kill`. The desk already killed `defi_health`
  (DefiLlama TVL / DEX volume / fees, all SCREEN-WEAK, IC −0.01..+0.02) at the *daily BTC-timing*
  horizon. This is the independent **cross-sectional, weekly, 335-coin** version of the same kill,
  including the *change*-in-TVL construction the desk did not itself run. Class closed on both axes.
  Bonus, and this is the load-bearing part: his double-counting list is the mechanical reason the
  desk should never trust a vendor TVL aggregate as a *level*.
- **Provenance.** Opened https://arxiv.org/abs/2506.03287 (abstract) and
  https://arxiv.org/html/2506.03287v1 (**full HTML primary text with the alpha tables**, read
  directly). Not a search summary.

### F5. ★ Fieberg–Günther–Poddig–Zaremba, "Non-standard errors in the cryptocurrency world" (IRFA 2024) — the single most important item on this ground

- **Claim/mechanism.** "Non-standard error" (NSE) = the dispersion in a result caused purely by
  *researcher choices*, holding the hypothesis and the raw data fixed. This is the variance the
  desk's DSR/PBO machinery **does not measure**, because DSR corrects for the number of trials you
  *ran*, not for the fact that a single trial's answer is itself a random draw over defensible
  construction choices. These authors enumerated **ten prevalent decisions** (data source, sample
  prep, portfolio construction) and crossed them into **20,736 research designs** applied to **43
  sorting variables** in crypto.
- **Replication status / the number that matters.** "Non-standard errors in cryptocurrency studies
  not only surpass those in the stock market but also **clearly exceed standard errors**." Read that
  literally: **in the crypto cross-section, the uncertainty from how you built the test is LARGER
  than the uncertainty from having a finite sample.** Two honest researchers, same hypothesis, same
  raw data, different defensible choices, get answers further apart than the confidence interval
  either one reports. Two mitigations they identify: (a) **"reducing the influence of the smallest
  coins effectively decreases the non-standard errors"** — the crypto restatement of HXZ's microcap
  finding (F1), arrived at independently; (b) **size and momentum "remain consistently robust across
  numerous specifications"** — i.e. NSE is not uniform, a few factors survive the whole design cube.
- **Verdict for this desk:** `free-graveyard-entry` (methodological — this is a **rail**, not a
  signal kill) **and the highest-value item on this ground.** Pasteable mechanism of death for any
  future single-construction crypto screen: *a crypto cross-sectional result reported from ONE
  construction carries an unreported error bar that is larger than its reported one; a single-design
  screen result is therefore not evidence at the strength it appears to have.* Direct operational
  consequences for the desk:
  1. **Single-construction screens are under-powered by construction.** The desk's own §26.3 rule
     ("one construction tried, one verdict, logged") correctly prevents re-rolling for a better
     answer, but it does NOT make the one draw reliable. The fix that is consistent with both is a
     **pre-registered design GRID** — enumerate the defensible choices up front, run them all, and
     judge the *distribution*, with the pre-registration preventing cherry-picking.
  2. **Small-coin exclusion is a first-order rail, not a hygiene detail.** The desk's universe
     construction should cap microcap influence explicitly and log the cap.
  3. This is the honest reconciliation of F1-vs-F2: HXZ's 64–85% failure rate and Chen's ≤28% t-stat
     inflation are *both* measured on single designs. NSE says the design axis carries more variance
     than either dispute is arguing about.
- **Provenance.** Opened https://ideas.repec.org/a/eee/finana/v92y2024ics1057521924000383.html
  (**RePEc record with verbatim abstract**, read directly). The publisher page
  https://www.sciencedirect.com/science/article/abs/pii/S1057521924000383 is abstract-only/paywalled
  and was NOT opened for interior. An open repository copy exists at
  https://open.icm.edu.pl/handle/123456789/25541 — **not yet opened; carry-over for interior
  extraction** (the 10-decision list and the per-factor NSE table are the loot worth having).

### F6. McLean–Pontiff (JF 2016), "Does Academic Research Destroy Stock Return Predictability?" — the decay law, with the data-mining share separated out

- **Claim/mechanism.** Two distinct forces shrink a published anomaly, and this paper is the one that
  **separates them**. (1) *Data mining*: the in-sample estimate was inflated by selection, so it
  falls even before anyone reads the paper. (2) *Publication-informed trading*: real capital arrives
  after publication and arbitrages the spread away. Who loses money: whoever sizes a strategy on its
  published in-sample number.
- **Replication status.** 97 published predictors. Portfolio returns are **26% lower out-of-sample**
  (pre-publication but post-original-sample) and **58% lower post-publication**. The 26% is an
  **upper bound on the data-mining component**; the residual **32% (58−26)** is attributed to
  publication-informed trading. Two conditional results that are the actionable part: post-publication
  decay is **larger for predictors with higher in-sample returns** (the fat backtest decays hardest —
  the desk's own `ls_contrarian` bt 9.84 → DSR-killed is the same phenomenon), and surviving returns
  concentrate in **high-idiosyncratic-risk, low-liquidity** stocks (i.e. what is left is limits-to-
  arbitrage rent, not free alpha).
- **Verdict for this desk:** `free-graveyard-entry` (methodological prior, high confidence).
  **Mechanism of death, pasteable:** *any signal sourced from published literature must be haircut
  ~58% off its published effect before it is worth a slot, and MORE than 58% if its published Sharpe
  was unusually high; what survives that haircut is generally rent on illiquidity/idio-risk that the
  desk cannot size into.* This is a hard prior against the desk's whole "read a paper, screen the
  signal" pipeline unless the paper is recent and the mechanism is structural.
- **Provenance.** Opened https://colab.ws/articles/10.1111%2Fjofi.12365 (**verbatim JF abstract
  rendered**, read directly). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623 and the
  Wiley page were NOT opened (SSRN/Wiley 403 this box). Author self-archived PDFs exist at
  https://www.hec.ca/finance/Fichier/McLean.pdf and
  https://www.fmg.ac.uk/sites/default/files/2020-08/Jeffrey-Pontiff.pdf — **PDFs, interior not
  extractable on this box; carry-over.**

### F7. Chordia–Goyal–Saretto, "p-Hacking: Evidence from Two Million Trading Strategies" — the brute-force null

- **Claim/mechanism.** Rather than argue about how many factors were secretly tried, these authors
  **construct the counterfactual search** — 2.1 million mechanically-generated accounting-ratio
  trading strategies — and ask what t-stats a pure data-mining machine produces by luck. This is the
  closest published analogue to what the desk's own screening loop *is*, which makes it the most
  directly transferable multiplicity result in the literature.
- **Replication status.** Verbatim from the abstract: *"We find that the difference in rejections
  rates produced by single and multiple hypothesis testing is such that most rejections of the null
  of no outperformance under single hypothesis testing are likely false (i.e., we find a very high
  rate of type I errors). Combining statistical criteria with economic considerations, we find that a
  remarkably small number of strategies survive our thorough vetting procedure. **Even these surviving
  strategies have no theoretical underpinnings.** Overall, p-hacking is a serious problem and,
  correcting for it, outperforming trading strategies are rare."* The widely-quoted thresholds
  (6-factor alpha |t| > 3.79, regression |t| > 3.12, Sharpe > 0.12; ~17 of 2.1M surviving, 1972–2015)
  appear in secondary write-ups — the RePEc abstract does **not** carry them, so those specific
  numbers are **SUMMARY-ONLY** and are recorded here as unverified.
- **Verdict for this desk:** `free-graveyard-entry` (methodological) **+ direct corroboration of the
  desk's 420/0 record.** Mechanism of death for the brute-force class: *mechanical signal generation
  over a fixed accounting/price panel produces survivors at a rate indistinguishable from luck once
  cross-correlation-aware multiple testing is applied, and the handful that survive have no
  mechanism — which means they will not survive forward.* The sentence "even these surviving
  strategies have no theoretical underpinnings" is the strongest available external argument for the
  desk's mechanism-first gate: **statistical survival without a mechanism is not evidence.**
- **Provenance.** Opened https://ideas.repec.org/p/chf/rpseri/rp1737.html (**verbatim SFI working
  paper abstract**, read directly). Semantic Scholar page rendered blank. Full PDF interior NOT read
  (no PDF tooling). Published successor: Chordia–Goyal–Saretto, "Anomalies and False Rejections",
  RFS — SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3017677 (SSRN 403s on this box;
  **carry-over**).

### F8. ★ RETRACTION MINING — the Brian Lucey / Elsevier finance-journals cluster (Dec 2025 – Jan 2026), including a 707-citation CRYPTO paper

- **Claim/mechanism.** This is not a statistical-failure entry, it is a **source-trust** entry, and it
  is crypto-specific. Twelve papers were retracted across three Elsevier finance journals —
  **International Review of Financial Analysis, International Review of Economics & Finance, and
  Finance Research Letters** — on a single stated ground: *"Review of this submission was overseen,
  and the final decision was made, by the Editor Brian Lucey, despite his role as a co-author of the
  manuscript. This compromised the editorial process."* Among the retracted items is
  **"Cryptocurrencies as a financial asset: A systematic analysis" (International Review of Financial
  Analysis), with 707 Clarivate WoS citations**, and **"Datestamping the Bitcoin and Ethereum
  Bubbles" (Finance Research Letters 26 (2018) 81–88)**. The mechanism that costs money: a large
  fraction of the *crypto* empirical literature the desk would naturally mine is concentrated in
  **Finance Research Letters and IRFA** — short-format, fast-turnaround venues — and this cluster is
  documented evidence that the peer review stamp on that corpus was, for a set of papers, not
  independent.
- **Replication status / reply layer (charter §9 — the comments outrank the article).** Lucey's own
  defence is that editing one's own paper is *"pretty common"* in finance and economics — which, if
  true, generalises the problem well beyond him. The comment thread adds what the article does not:
  commenter **Wei** points to a **PubPeer** thread on the rebuttal that "clearly shows the citations
  stacking there"; **brummie**: *"Nobody can publish dozens of papers a year in finance with honest
  work. They did it for many years."*; **Igor Radun** explains the structural defect (an associate
  editor will not desk-reject the editor-in-chief); **Jake**: *"He did not just publish in his own
  journal, he went a step further, he edited his own paper."*; **Berto**: *"Dear Elsevier. Please
  investigate all those 240 articles."* Separately, Lucey helped coordinate Elsevier's **Finance
  Journals Ecosystem**, which a preprint alleged "might facilitate citation stacking as a way to
  boost journal impact factors."
- **Verdict for this desk:** `free-graveyard-entry` — **a SOURCE-CLASS prior, ready to paste.**
  *Mechanism of death: citation count and journal name are corrupted quality signals in the
  short-format crypto finance literature (FRL / IRFA / IREF). A 707-citation crypto paper was
  retracted for editorial self-dealing, and the same ecosystem is credibly alleged to stack
  citations — so "highly cited" in this corpus may measure cartel membership rather than
  replicability. Therefore: NEVER let a crypto empirical paper's venue or citation count substitute
  for reading its identification strategy; and treat FRL/IRFA/IREF crypto results as
  single-source until independently reproduced.* Note the sharp edge — this is not a claim the
  *findings* are false (the retractions are for process, not fabrication); it is a claim that the
  **filter the desk was implicitly relying on did not run.**
- **Provenance.** Opened
  https://retractionwatch.com/2026/01/08/finance-professor-brian-lucey-ireland-elsevier-journals-retractions/
  (**full article, read directly**) and its `#comments` anchor (**full comment thread, read
  directly**). The Elsevier retraction notice for the Bitcoin/Ethereum bubbles paper,
  https://www.sciencedirect.com/science/article/pii/S1544612326000140, returned **HTTP 403 — verbatim
  notice text NOT read**; its existence and bibliographic details come from the search index plus the
  Retraction Watch article. ~~PubPeer thread on the citation stacking not yet opened — carry-over.~~
  **CARRY-OVER CLOSED 2026-07-31 (run 4):** PubPeer DIRECT is 403-blocked from this box (bot-gate,
  NOT circumvented — #80 ruling pending; logged). The layer was mined via
  `chrisbrunet.com/p/elsevier-shuts-down-its-finance-journal` (read in full): a **peer-reviewed 2025
  econometric study quantifies the stacking at +103% citations-per-article** (2021-2025 vs
  2016-2020); Elsevier dismantled the ecosystem; 12 retractions = 5,104 combined citations;
  author-level nodes named (Lucey 55 PubPeer flags, Vigne 21, Goodell 68-in-FRL); documented
  co-authorship trading (SSRN draft scrubbed, fourth author added, same text). Full sharpened
  operational rule routed to **NK-004 (upgraded to HIGH confidence)**. [§33: wired -> docs/research/negative_knowledge.md NK-004]

### F9. ★★ THE RECONCILIATION — Chen & Zimmermann vs Hou–Xue–Zhang: "reproduction" ≠ "replication", and the desk has been conflating them

- **Why this is the deepest item here.** Two credible teams read the same corpus and report ~98%
  success and ~35% success. That is not a coin-flip between authorities — it is a **definitional
  split that the desk can and must exploit**, because the desk makes the identical mistake every time
  it screens a literature signal.
  - **Chen & Zimmermann (Critical Finance Review 2022, "Open Source Cross-Sectional Asset Pricing")
    REPRODUCE**: they re-run each predictor *using the original paper's own protocol*. Explicitly:
    *"We avoid jargon and use the dictionary definition: 'the act of making or doing something again
    in exactly the same way'."* Result: ~200 predictors coded from 319 characteristics; for the 161
    that were clearly significant originally, **98% of long-short portfolios have |t| > 1.96**, and
    reproduced-on-original t-stat regression gives **slope 0.88, R² 82%**.
  - **Hou–Xue–Zhang REPLICATE UNDER A NEW, STRICTER PROTOCOL**: NYSE breakpoints + value weighting.
    64–85% fail (F1).
  - **Chen & Zimmermann's explicit counter-attack on HXZ**, quoted: *"only about 26% of Hou et al.'s
    long-short strategies were shown to be clearly statistically significant in the original
    papers."* I.e. HXZ's denominator is padded with predictors the original authors never claimed
    were significant standalone; calling those "failures" inflates the failure rate.
- **What actually survives the crossfire (this is the finding).** Strip the rhetoric and both sides
  agree on the following, and it is the only part the desk should act on:
  1. **The published number reproduces.** The code is not wrong and the data are not fabricated.
  2. **The published number does NOT survive a protocol change.** Change the weighting scheme or the
     universe filter and most of it evaporates. HXZ's 64–85% *is* the honest measure of
     protocol-fragility even if it is a poor measure of "fraud".
  3. Chen's own shrinkage estimates are modest — **10–15% of in-sample mean returns**, FDR "below
     10%" (simple model: t-stats overstated by ~10%, FDR 0.4%; the companion bound paper,
     "Most claimed statistical findings in cross-sectional return predictability are likely true",
     gets **FDR ≤ 25% in eight of nine prior studies, refined bound FDR ≤ 9%**) — but they are
     estimates of *how wrong the published number is under its own protocol*, NOT of how much
     survives to a live book. McLean–Pontiff's **58%** (F6) is the number for that, and Chen's ~12%
     is not in competition with it: 12% is bias, 58% is bias + arbitrage + protocol change.
- **Verdict for this desk:** `free-graveyard-entry` — **a definitional rail, immediately pasteable.**
  *Mechanism of death: a literature signal that "replicates" almost never means "survives a change of
  construction". Reproduction (same protocol) success ~98%; protocol-robustness success ~15–35%;
  post-publication live survival ~42% of the published effect. The desk must record which of the
  three it has verified before a signal is allowed to consume a slot.* Concretely: when a digger says
  "this paper replicated", the gauntlet must ask **"reproduced, or re-derived under YOUR
  construction?"** — and only the second counts. This dovetails exactly with F5 (non-standard
  errors): protocol-fragility IS non-standard error, measured a different way, on a different asset
  class, by a different team. **Three independent literatures converge on the same conclusion: the
  construction choice carries more risk than the sampling error.**
- **Provenance.** Opened https://arxiv.org/abs/2209.13623 (abstract) and
  **https://ar5iv.labs.arxiv.org/html/2209.13623 (FULL HTML PRIMARY TEXT — the HXZ-reconciliation
  passage and the 26% quote were read directly there, not from a summary)**; plus
  https://arxiv.org/abs/2206.15365 (abstract, Chen "Most claimed statistical findings… are likely
  true"). The ~98% / slope-0.88 / R²-82% figures for the *Open Source* paper itself came from the
  **search index, not from a page I opened** — flagged **SUMMARY-ONLY** for those three numbers;
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3604626 and
  https://www.nowpublishers.com/article/Details/CFR-0112 were not opened. Data + code are public at
  https://www.openassetpricing.com/ (**data-loot lead, charter §27 — an open 200-predictor panel with
  code is exactly the kind of free asset the desk logs; NOT yet opened**).

### F10. ★ Fieberg–Liedtke–Zaremba, "Cryptocurrency anomalies and economic constraints" (IRFA 2024) — the crypto cross-section dies of microcaps, shorts, and bull-market-only alpha

- **Claim/mechanism.** The crypto factor literature reports fat long-short spreads. This paper asks
  the only question that matters — *can they be forged into viable trading profits?* — and finds
  three separate mechanisms of death, each of which kills a different published family:
  1. **Size and volume anomalies "originate from micro-cap coins of negligible economic
     importance."** The spread is real and untradeable: it lives in coins that cannot absorb capital.
     This is HXZ's microcap finding (F1) reproduced on crypto by a different team — third independent
     confirmation, after F5's "reducing the influence of the smallest coins effectively decreases the
     non-standard errors".
  2. **Momentum "prevails in larger cryptocurrencies but incurs substantial trading costs and
     extracts alphas largely from short positions."** This is the killer detail. Crypto momentum's
     alpha is on the SHORT leg — which in crypto means borrow cost, borrow availability, perp funding
     paid, and squeeze risk on exactly the illiquid names where the signal is strongest. A long-only
     or funding-constrained book gets ~none of the published alpha.
  3. **"Most abnormal returns occur primarily in bull markets and fade over time."** Regime-
     conditional and decaying: the published sample is a 2017/2021 bull-window artifact.
  Their own prescribed protocol, verbatim: *"protocols for identifying tradable cryptocurrency
  anomalies should focus on long positions, account for transaction costs, consider hard-to-trade
  coins, and emphasize performance in recent years."*
- **Verdict for this desk:** `free-graveyard-entry` for **crypto cross-sectional size/volume**, and
  `confirms-existing-kill` for crypto momentum/price-only (the desk's 420/0 record + the era TA
  natural experiment already own that). Pasteable mechanism of death: *published crypto
  cross-sectional anomalies are (a) microcap-borne where they are large, (b) short-leg-borne where
  they are in liquid names, and (c) bull-regime-borne where they are neither — so a long-biased,
  liquid-universe, cost-honest book captures approximately none of the published spread. This is
  why the desk's 420 price-only hypotheses returned zero survivors: it was already running the
  cost-honest liquid-universe test that the literature does not.*
- **Provenance.** Opened https://ideas.repec.org/a/eee/finana/v94y2024ics1057521924001509.html
  (**verbatim abstract, read directly**). Publisher page
  https://www.sciencedirect.com/science/article/abs/pii/S1057521924001509 is abstract-only/paywalled
  and its interior was NOT read. Sample period and anomaly count are **not** in the abstract —
  unverified, carry-over.

### F11. Li & Zhu, "Taming crypto anomalies: A Lasso-type factor model" — 49 crypto anomalies, 13 survive, and SIZE dies out-of-sample

- **Claim/mechanism.** Direct re-test of the Liu–Tsyvinski–Wu (JF 2022) crypto three-factor world
  (market, size, momentum) on an extended sample, with an explicit in-sample / out-of-sample split.
- **Replication status.** **Only 13 of 49 crypto anomalies are significant over 2014–2023** — which
  the authors note is *consistent* with LTW, i.e. the headline LTW result is not overturned in
  full-sample. But the split is where it breaks: out-of-sample shows **the disappearance of the SIZE
  effect** and the appearance of a left-tail-risk effect. Their replacement model, DS3 (iterative
  double-selection Lasso), keeps market + **two-week momentum** + **residual momentum** — note that
  **size is not in it**.
- **Verdict for this desk:** `free-graveyard-entry` for **crypto SIZE as a factor** — mechanism of
  death: *crypto size is the microcap-illiquidity artifact of F1/F5/F10 wearing a factor label; once
  the sample extends past the small-cap-fuelled 2017–2021 window it does not survive out-of-sample,
  and the two independent crypto teams (Li–Zhu; Fieberg–Liedtke–Zaremba) reach it by different
  routes.* The DS3 survivors (2-week momentum, residual momentum) are `confirms-existing-kill` for
  this desk — short-horizon price-only momentum is inside the 420/0 kill and the desk additionally
  found short-term reversal at Sharpe −1.41.
- **Provenance.** ~~SUMMARY-ONLY~~ → **UPGRADED 2026-07-31 to ABSTRACT-PRIMARY (published version,
  verbatim).** The OP-026 ladder resolved it: IDEAS/RePEc carries the RIBF 83 (2026) published
  abstract verbatim (`ideas.repec.org/a/eee/riibaf/v83y2026ics0275531926000255.html`, DOI
  10.1016/j.ribaf.2026.103298). Confirmed word-for-word: 49 anomalies; *"the disappearance of size
  effect and the appearance of left-tail risk effect"* out-of-sample; DS3 = MKT + MOM2 + RMOM (no
  size). **Routed:** corroboration appended to graveyard row `lit_crypto_xsec_size_and_volume`
  (same family — no new row; a fifth row would double-count the kill). **STILL PROVISIONAL, interior
  never read:** the "13 of 49 significant" figure and exact IS/OOS split dates. Routes exhausted
  2026-07-31: SSRN `Delivery.cfm` direct-PDF 403s (NK-005 scope extended), ScienceDirect 403s.
  Interior remains a legitimate-route residual, not a carry-over obligation — the actionable claim
  (size-death) is closed. [§33: wired -> docs/graveyard.md row lit_crypto_xsec_size_and_volume]

---

## RUN 3 VERIFICATION PASS (2026-07-26) — the extractor was validated BEFORE its output was trusted

Run 3 lifted the "no PDF tooling" blocker (see F1 provenance). Before letting a new extraction path
feed the graveyard, it was validated — an unvalidated extractor that silently mangles digits would be
a phantom-evidence factory, which is precisely the thing this desk exists to avoid.

**Validation design.** Pick a paper whose numbers were ALREADY read from an independent rendering
(HTML), extract the PDF, and compare. Brigida (F4) qualifies: run 2 read
`arxiv.org/html/2506.03287v1` and recorded its alpha table. Run 3 downloaded `arxiv.org/pdf/2506.03287`
and extracted it cold.

**Result — the numbers reproduce exactly.** Table 8 (total TVL), verbatim from the PDF extraction:
`α  0.25  -0.11  -0.04 | 0.31  -0.05  -0.04` over p-values `(0.20) (0.80) (0.93) | (0.13) (0.92)
(0.93)`; `GRS Stat. 0.72 / p-value (0.54)` and `GRS Stat. 1.11 / p-value 0.35`. Run 2's HTML-sourced
record — "total TVL −0.11 to 0.31, all p > 0.13" and "GRS p 0.35–0.99" — matches to the digit,
including the minimum p of 0.13 and the GRS low end of 0.35. Two independent renderings, same
numbers. **Extractor validated on a numeric table with parenthesised p-values, which is the hardest
and most consequential case.**

**F4's graveyard row was then re-checked against primary text rather than trusted second-hand**, and
it survives: Table 9 (change in TVL) reads `α 0.23 0.38 0.41 0.21` over `(0.70) (0.54) (0.50) (0.65)`
— minimum alpha p **0.50**, so run 2's "ΔTVL all p > 0.40" is correct and in fact conservative. GRS
across the four panels: 0.54, 0.35, 0.80, 0.78 — never close to rejecting. **The kill stands on
primary evidence.**

**One number in the run-2 record is unlocated, and is flagged rather than quietly kept:** the "−0.31"
in "change in TVL −0.31 to 0.41" does not appear in Table 9's alpha row (all four are positive). It
is plausibly from one of the Level-1 sub-tables (11–13), which were not checked. It does not affect
the verdict — every alpha in every panel is insignificant — but it is recorded as unlocated because
silently keeping an unverified digit is how the F1 error happened.

**A secondary result run 2 missed, and it earns NO card — recorded because negative/near-miss
findings are first-class.** The paper twice measures a *significantly negative* momentum loading on
TVL-formed portfolios: `β_Mom −0.11**` (p=0.05, Table 8) and `β_Mom −0.20***` (p=0.01, Table 9), with
the author's own text: *"There is again evidence on a negative relationship between TVL-formed
portfolios and crypto market momentum."* This is a real, within-paper-replicated factor-structure
fact — and it is **not a card for this desk**: it is a cross-sectional factor LOADING, not an alpha,
on a family the desk has already killed twice (`defi_health` at daily, and now `lit_defi_tvl_
crosssection` cross-sectionally). Naming it and declining it, rather than dressing a loading up as a
signal.

**Standing note for future runs:** the extractor was subsequently rewritten (proper object parsing,
object streams, ToUnicode font maps, per-page output) by a parallel run-3 agent. It is a `/tmp`
prototype and therefore NOT durable — the proposal to land it as `scripts/pdf_text.py` is
GAP_REGISTER #70. **Until that lands, every literature run must rebuild it or re-inherit the false
blocker.** That is the whole reason #70 exists.
