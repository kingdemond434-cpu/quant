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
