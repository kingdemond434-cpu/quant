# CAPABILITY HUNT PROPOSALS 20260812 slot 3

LENS: CAPACITY & COMPOUNDING -- what lets the book carry more risk-adjusted size or compound FASTER: a decorrelated sleeve, a cost-tier cut (every bp is pure CAGR), a funding-harvest cadence, a capacity band we are leaving on the table.

## A -- Claude family

Hunt complete. The lens survived to one deep proposal that clears the bar, plus a 26-item brainstorm.

---

**MISSING CAPABILITY:** Inventory-yield truth — the spot hedge leg of the carry sleeve (soon the largest single deployment of capital on this desk) is treated as yield-dead everywhere, while master constitution §82 explicitly names "collateral yield" as an optimization axis and **zero code implements it** ("collateral yield" appears in no `.py` file; no earn/lending API adapter exists anywhere).

**WHY IT IS INVISIBLE TODAY:** Three stacked frames each exclude it, so its absence looks exactly like health (the L1.51 "what does absence look like" test fails). (1) `libs/research/idle_yield.py` — the desk's only yield organ — restricts its universe to **USD-pegged symbols by design** (line 71), so the alt spot leg is structurally outside its vocabulary, not merely unmeasured. (2) L1.51's verdict "lending loses to T-bills net of the 300bps haircut" reads as if the lending question is *settled* — but that comparison prices **idle** cash, whose counterfactual is the risk-free rate; the hedge leg must be held regardless, so its counterfactual is exactly **0%**, and any net-positive venue-native yield wins. The settled-looking verdict answers a different question. (3) The yield is trade-adjacent but generates no trade, so every trade-driven meter (TCA, fee burn, waterfall) is silent about it — a flat yield line produces no evidence of its own flatness.

**MECHANISM:** Two halves, phased across the L1.38 window. *Measurement half (no money-path touch, buildable now):* `scripts/collect_venue_yield.py` pulls Binance Simple Earn flexible APRs, cross-margin hourly borrow rates, and flexible-loan rates per asset daily into `data/venue_yield.jsonl`; `libs/execution/inventory_yield.py` joins the live carry basket to publish `data/inventory_yield_state.json` — per-asset `{holding, apr_now, fast_redemption_limit, redemption_p99, lendable_fraction, measured}` with both rungs and the breakeven published per L1.51's own rule. `scripts/check_inventory_yield.py` fence: **UNMEASURED** when the basket's yield surface is unread N days (never OK-on-absence, WS-005), **FAIL** on the NAV-completeness check — equity readers must enumerate every venue wallet product (spot/margin/futures/earn/funding) and cover 100% of nonzero balances, the generalization of the multiAssetsMargin lesson. *Acting half (post-window, first subscription is a wallet-architecture change = principal-visible act, same class as the multiAssetsMargin toggle):* subscribe/redeem adapter with a lendable-fraction rail sized so the basis-blowout stop's worst-case spot sale is always executable from the unlent buffer, and planted micro-redemptions (L1.45 pattern, pre-registered) to *measure* redemption latency rather than assume it. Yield lands as its own line in the L1.58 waterfall. Sizing authority: none — yield never justifies a bigger leg.

**WHAT IT WOULD HAVE CAUGHT:** `scripts/run_deadman_switch.py:126` — the dead-man's equity reader hid **$5,000 of USDC** under `multiAssetsMargin=False` and pinned `high_water` at $209.43; earn-wallet balances are the identical blindness class one product over, and today *nothing* asserts wallet-coverage completeness — the fence half pre-empts the repeat before the overlay ever lends a dollar. Second: L1.51's first run killed lending on `DEFAULT_HAIRCUT_BPS=300` **with no derivation in the repo** — this capability is the missing rung that analysis couldn't express.

**ROI:** Direct, honest: small today (book ≈ $5k, ramp-pinned) — roughly `f_lend × spot_notional × net_APR`, single-digit dollars/yr now, scaling linearly to ~0.5–2% additional CAGR on the spot leg at target book with **zero new thesis risk** (it is the same borrow-demand premium the sleeve already harvests, collected on the second of the two legs that carry it — the reachable half of the "negative funding structurally unreachable" premium flagged 2026-08-05, no short-basis construction needed). Cascade, larger near-term: (a) the NAV-completeness fence closes a live defect class; (b) the borrow-rate series is a **free new data axis** — the observable price of exactly the "nobody wants to hold this" latent that drives funding, with a stated mechanism prior (borrow spikes lead funding where shorts route through margin before perps) → screen-on-discovery applies; (c) redemption-latency is the desk's first measured venue-*exit* physics, feeding the counterparty/mobility drills the negative exemplars died without.

**COST:** ~0.5 day for collector + fence (measurement half); ~1–1.5 days for adapter + buffer policy + probes (acting half); low maintenance (one venue API surface). Competes with repair-mode drain — routes as one ledger row; the NAV-completeness fence half is arguably a defect-closer and drains *toward* the queue's direction.

**FALSIFIER:** Measured net APR across the actual carry basket below the priced redemption-tail cost (P(redemption gate during a blowout-stop window) × cost of the naked leg) at every lendable fraction; or fast-redemption limits too small to keep the stop executable at target book; or the venue ToS/legitimacy gate fails on programmatic subscribe/redeem. Any of these kills the acting half — the NAV-completeness fence survives on its own merits regardless.

**NOVELTY-CHECK:** `grep -rniE "collateral.?yield|simple.?earn|lend(ing)?\b|borrow.?rate" --include="*.py" libs/ scripts/` → only `idle_yield.py` (USD-pegged idle cash, different question); ledger grep → 0 rows; `grep -niE "lend|earn|borrow" docs/GAP_REGISTER.md` → no such row; `docs/research/TIER1_BENCHMARK.md:71` `inventory_treasury` covers BNB policy + sweeps, not deployed-inventory yield; `docs/MASTER_QUANT_CONSTITUTION.md:2341` (§82) names the axis in prose with no implementing organ and no explicit UNWIRED marker (L1.59 violation as found).

---

**BRAINSTORM** (raw generation, one line each — builder rows and screens; known-adjacent flagged honestly):

1. **Borrow/loan-rate axis collector** — free daily observable of short demand, mechanism prior: leads funding on no-perp listings — **S** — axis watchlist + screen-on-discovery.
2. **NAV-completeness fence** standalone — enumerate all venue wallet products, assert 100% nonzero-balance coverage in every equity reader — **S** — fence (defect-closer, USDC-blindness class).
3. **Earn-APR spike alarm as entry-timing signal** — borrow-demand shock precedes funding spike — **A** — axis watchlist.
4. **Residual-delta quantization meter** — lot rounding on two legs leaves per-carry residual delta; aggregate |Δ| and net across book, fence above x bps of NAV — **B** — fence.
5. **Ramp-runway meter** — days-to-next-rung at *measured* fill arrival rate, published beside ramp state; names the cheapest lawful observation-rate raise (more, smaller fills inside excitation design) — **A** — ledger.
6. **Wallet-imbalance runway + auto-sweep** — funding pays into futures wallet, entries drain spot wallet, so the binding wallet silently caps carry count — **A** — ledger (pairs with tier1 `inventory_treasury` T3 row).
7. **Venue-onboarding runway** — L1.18a deployment-race applied to venues: measured time from edge-found-on-X to capital-can-trade-on-X; §42 cross-venue grounds are DOA until this is a number — **A** — ledger.
8. **PM-eligibility trigger** — `run_capital_plan.py` models 1.8x efficiency; wire the alert that fires the week NAV crosses the venue minimum — **B** — fence (verify not already wired).
9. **Fee-promotion surveillance** — extend `collect_announcements.py` lexicon to zero-fee/discount campaigns; for a fee-dominated sleeve a promo is a temporary edge multiplier *and* a natural experiment for the cost model — **A** — axis watchlist.
10. **Quote-currency fee arb** — route the spot leg through the cheapest quote (USDT/USDC/FDUSD) including conversion cost; zero-fee quote pairs have existed — **A** — ledger.
11. **Spot-leg venue routing** — cost model says spot is ~90% of round-trip cost on thin names; execute spot wherever cheapest per symbol, perp stays — transfer/settlement risk priced in — **B** — ledger.
12. **Settlement-phase close experiment** — pre-registered A/B (close-after-next-settlement vs close-now when rails permit), converting L1.47's 9.2% walked-away revenue from a measured fact with a refuted story into a tested lever — **A** — forward experiment, measurement only.
13. **Funding-interval-aware ranking audit** — verify the *selector* (not just accounting) imports `funding_clock` so 4h names aren't half-ranked — **B** — fence breadth check.
14. **Fast-redemption/withdrawal limits census per asset** — the buffer rail's own denominator — **B** — data table.
15. **Quarterly withdrawal drill** — measured time to move $X off-venue and back; the counterparty actuator Alameda/FTX-era desks died without — **A** — fence with staleness.
16. **Listing-day §42 playbook artifact** — pre-approved runbook + reserved capital + armed collectors keyed on the announcement feed; converts a named ground into a minutes-latency executable — **A** — ledger.
17. **Compounding-latency meter** — realized-PnL→sizing-equity lag in hours; likely ~0, but unmeasured counts as zero (L1.28a), measure once — **B** — one-shot.
18. **Joint margin stress sim before any wallet-mode toggle** — multi-asset/PM/earn changes run through the gap-#108 block-bootstrap dependence engine simulating §83 liquidation coupling — **A** — ledger (pairs with #108).
19. **Basis-entry joint-limit execution** — work the pair as a spread order, enter only on joint fill at target basis; stops paying both spreads legging into thin names — **B** — ledger.
20. **Income auto-compounding hygiene** — earn interest + funding income swept into the quote buffer so it re-enters sizing equity — **B** — folds into 6.
21. **Per-leg maker-share ratchet** — E10 measured spot 33% maker vs futures 100%; floor and ratchet the *spot* maker share specifically, weight excitation arms toward spot-passive — **A** — fence (extends excitation, cites E10).
22. **Carries-per-dollar capacity column** — publish margin efficiency per candidate under current mode vs multi-asset vs PM; makes §82's margin-efficiency axis a number feeding the deployment race — **A** — ledger.
23. **Interval-mismatch screen wiring check** — verify `screen_funding_interval_mismatch.py` consumed the 4h-interval map in `collect_perpdex_funding.py` — **B** — wiring check.
24. **Per-sleeve subaccounts at sleeve #2** — sleeve-level NAV/rails clean by construction; §82 fragmentation measured, not suffered — **B** — ledger (pre-build decision note).
25. **Derive the 300bps haircut** — L1.51's own text says `DEFAULT_HAIRCUT_BPS=300` has no derivation; decompose into measured venue/bridge/depeg components so the T-bill-vs-lending verdict is defended, not defaulted — **A** — ledger.
26. **Funding-income reconciliation breadth** — verify realized-funding venue rows are pulled *paginated* (the 1000-row lesson) and differenced per-position continuously, not spot-checked — **B** — fence breadth.

Context remains — naming the next ground rather than closing (L1.40): I was about to generate (27) a covered-call overlay on the spot leg as a second inventory coupon (blocked today by options venue breadth, tier1 `vol_surface_expertise` T4), and (28) Earn locked-vs-flexible term-structure as a rate-expectations signal — the next run should resume there.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
