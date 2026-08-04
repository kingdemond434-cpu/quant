# GATE-0 / LIVE-CAPITAL QUEUE — pre-registered, triggered, not forgotten

**Status: QUEUED, not built.** These guard *live capital*. The desk is on testnet and Gate-0 is
blocked by its own mandatory pre-mortem panel, so none of them are urgent today — but every one
becomes load-bearing the moment real money moves, and a thing remembered only in conversation is a
thing that will be forgotten. Each carries an explicit **trigger** so it activates on a condition
rather than on someone's memory.

Principle: *the desk is a scientific institution, so nothing enters live capital on confidence —
only on evidence, and only with its safety layer built first.*

---

## TIER 1 — MUST EXIST BEFORE THE FIRST LIVE EURO

| # | Item | Why it blocks | Trigger |
|---|---|---|---|
| G1 | **Gate-0 pre-mortem panel** (`PANEL_MISSION=premortem`) | The desk's OWN doctrine makes it mandatory and blocking: fire all 13 seats at the connector + breaker report, mandate "argue this go-live fails". Unresolved critical findings block the key request. | OpenRouter funded |
| G2 | **Capacity floor — FIX THE TWO DEFECTS** | `capacity_simulator.py` ships with futures `min_notional` reading 0.0 (filter-key mismatch) so the floor is UNDERSTATED, and it surfaced `COOKIEUSDT` at 59.17bps FLAT across all size buckets — either a degenerate cost-model entry or a symbol too illiquid to carry. Sizing decisions must not use the current number. | Before any live sizing |
| G3 | **Zero-trust collector monitor** | Announced and NOT built (my error). A collector that silently returns zeros makes the desk think a market is flat and fires false signals. Every collector needs a volume/row-count deviation kill-switch (>20% vs 30d mean → halt dependent signals). | Before any LLM-written collector feeds a live signal |
| G4 | **Universe liquidity gate** | The live paper universe is micro-cap alts (COOKIE, 1000CAT, MOVE, TST). If G2 confirms ~59bps/leg, the carry is structurally unprofitable there at ANY size — 4 legs ≈ 2.4% round-trip vs ~0.7%/mo harvest. | Immediately after G2 |

## TIER 2 — BEFORE SCALING BEYOND THE FIRST TRANCHE

| # | Item | Why | Trigger |
|---|---|---|---|
| G5 | **Macro regime circuit breaker** | Micro-alphas die instantly in a liquidity crisis. A macro state machine throttles capital when cross-asset vol/liquidity shifts to risk-off, before the immune system can react. | equity > first tranche |
| G6 | **Self-footprint monitor** | Once deployed, the desk becomes part of the market it reads. Own order flow must be subtracted from analysed data or the book front-runs itself into a false signal. | any symbol where our size > 1% of book depth |
| G7 | **Treasury / net-of-financing Sharpe** | An alpha earning 5% on 10x leverage at 6% borrow is a guaranteed loss. Net Sharpe must be computed AFTER borrow, margin and lock-up. | any leverage > 1x |
| G8 | **Exogenous risk sentinel** | A validated alpha goes to zero in an hour on an enforcement action or exchange seizure. Ingest SEC/CFTC/FCA/MAS/FSA actions + exchange rule changes. | live capital > 0 |

## TIER 3 — INSTITUTIONAL HYGIENE AT SCALE

| # | Item | Why | Trigger |
|---|---|---|---|
| G9 | **Chaos monkey** | Cannot backtest an exchange outage. Inject failures (disconnect 3 min, halve rate limits) and verify failover. | live capital > 0, monthly |
| G10 | **Ruthless garbage collector** | LLM-generated collectors break at machine speed on API drift. Auto-retire any collector failing 3× in a month; flag its data structurally unstable. | > 20 generated collectors live |
| G11 | **Crowding decay estimator** | An edge found in public data was found by others too. Well-known sources should require a HIGHER DSR bar than lonely ones. | first ELIGIBLE axis |
| G12 | **Regime mutation engine** | When a working strategy stops, do not just switch it off — deconstruct WHY, update the knowledge graph, broadcast the new market state. | first live strategy decay |

---

## THE INVARIANT (unchanged, overrides everything above)

No amount of architecture, model agreement, or apparent insight lets a hypothesis reach capital
without passing the fixed empirical validation gate. These layers make live capital *safer*; they
never make it *earlier*.

| G0 | **NAV RECONCILIATION GAP (TIER-1 BLOCKER, found 2026-07-27)** | venue_nav $5,262 vs mark_nav $14,508 = 175.7% divergence and GROWING (36.4% on 07-23). portfolio.json tracks the MARK not the VENUE, so the desk believes it holds ~$14.5k while the exchange reports ~$5.2k. Either different scopes or broken reconciliation. Catastrophic with real money -- every sizing/leverage/risk decision would run off a NAV that does not exist. | BEFORE any live capital |

| CV | **portfolio equity reconciles with the venue** `(CV-2026-07-27-portfolio equity reconcile)` | claims `equity $14,444 (tracks MARK)` but the source says `venue $5,211 vs mark $14,461 = 177.5% divergence` -- every sizing, leverage and risk decision runs off a NAV the exchange does not confirm; at Gate-0 this is capital-destroying | BEFORE any live capital |
| CV | **health all_ok is consistent with organ logs** `(CV-2026-07-27-health all_ok is consisten)` | claims `all_ok=True, organs_ok=True` but the source says `14 stub logs vs 13 real logs in last 48h` -- a green dashboard while organs are dead means silent research outage | BEFORE any live capital |

## CORRECTION 2026-07-27 -- the NAV CRITICAL was MY ERROR, not a missing $9k

G0 as originally written is WITHDRAWN. venue_equity.json measures the FUTURES scope ("fut margin + tracked spot legs + USDT delta"; 5,169 / 5,000 futures start = 1.03x) while portfolio.json measures the TOTAL book (14,363 / 15,000 = 0.96x). They were never the same quantity, so the "175.8% divergence" was a unit error on my part. NO CAPITAL IS MISSING: futures side +3%, total capital -4%.

**THE REAL DEFECT REPLACING IT (still a Tier-1 blocker):** `run_venue_divergence_shadow.py` computes pct_diff between those two scopes, and that series is explicitly intended to calibrate the GAP #19 circuit breaker at "~2x OBSERVED noise". Calibrating a breaker on a phantom 175% gap yields a breaker that never fires or always fires. The shadow must compare like-for-like (venue futures-scope vs the book's futures-scope) BEFORE anything is armed from it.

| CV | **venue and book NAV are compared on the SAME scope** `(CV-2026-08-03-venue and book NAV are com)` | claims `venue $6,070 (=0.58x futures start) vs book $13,160 (=0.88x total start)` but the source says `venue=FUTURES scope, portfolio=TOTAL scope -- not comparable` -- run_venue_divergence_shadow logs pct_diff between these and that series is what calibrates the GAP #19 breaker; calibrating on a scope mismatch produces a breaker that never fires or always fires. Fix the shadow to compare like-for-like BEFORE arming anything from it. | BEFORE any live capital |
| CV | **health all_ok is consistent with organ logs** `(CV-2026-08-03-health all_ok is consisten)` | claims `all_ok=True, organs_ok=False` but the source says `26 stub logs vs 14 real logs in last 48h` -- a green dashboard while organs are dead means silent research outage | BEFORE any live capital |
| CV | **axis_shadows.json freshness claim is true** `(CV-2026-08-03-axis_shadows.json freshnes)` | claims `updated 2026-08-02 02:38` but the source says `age 24.0h, mtime drift 0.0h` -- a stale artifact presented as current is read as live state | BEFORE any live capital |

| CV | **venue and book NAV are compared on the SAME scope** `(CV-2026-08-04-venue and book NAV are com)` | claims `venue $6,070 (=0.58x futures start) vs book $13,179 (=0.88x total start)` but the source says `venue=FUTURES scope, portfolio=TOTAL scope -- not comparable` -- run_venue_divergence_shadow logs pct_diff between these and that series is what calibrates the GAP #19 breaker; calibrating on a scope mismatch produces a breaker that never fires or always fires. Fix the shadow to compare like-for-like BEFORE arming anything from it. | BEFORE any live capital |
