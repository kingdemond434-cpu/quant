# MECHANISM GRAPH — the research-organisation layer (principal 2026-07-27)

**Not a strategy. Not an alpha. A research accelerator.** It consumes zero alpha-testing budget and
changes only *what questions get asked*.

## The shift

| Old question | New question |
|---|---|
| "Can I find another indicator?" | "How many INDEPENDENT ways can I observe the same economic process?" |

A feature that dies tells you nothing about the world. A **mechanism** that dies tells you the whole
family is dead; a mechanism that survives tells you every remaining observable on that chain is worth
building. That is why mechanisms transfer across datasets and indicators do not.

## Rule (binding)

Every hypothesis entering the EV gate must name its **mechanism node**. A hypothesis that cannot name
one is a curve-fit and is rejected before it consumes a forward slot. This is the cheapest possible
filter and it costs no compute.

---

## M1 — LIQUIDITY EXPANSION (the desk's most-covered chain)

    capital enters crypto -> stablecoins minted -> exchange balances rise -> funding changes
      -> perp positioning shifts -> altcoin rotation -> volatility expands

| Node | Observable | Desk status |
|---|---|---|
| capital entry | ETF flows | COVERED (`ingest_etfs`) |
| stablecoin mint | total supply | **LIVE CLOCK** (`stablecoin_supply_momentum`) |
| exchange balances | on-chain reserves | COVERED (`stablecoin_flows`) |
| funding | perp funding | COVERED (carry book, the desk's only real edge) |
| positioning | OI / long-short | **LIVE CLOCK** (`oi_divergence`, `ls_contrarian`, Aug 7) |
| rotation | breadth / dominance | COVERED (`free_signals`, `market_breadth`) |
| vol expansion | Deribit surface, liquidations | COVERED |

**Read:** 7/7 nodes observed — this chain is saturated. New observables here are marginal.
The value is now in *joint* tests along the chain (does node N lead node N+1?), not new sensors.

## M2 — REGIONAL CAPITAL CONTROL (the only chain that ever produced a survivor)

    local capital trapped -> local venue premium -> arbitrage constrained by FX/controls
      -> premium persists and mean-reverts

| Node | Observable | Status |
|---|---|---|
| KR controls | Upbit kimchi premium | **LIVE CLOCK** (flagged `ic_exceeds_contemporaneous`) |
| CN controls | USDT/CNY P2P premium | **LIVE CLOCK** (z warming up) |
| TR / JP / BR | tested | DEAD (arbitraged or timing artifacts) |

**Read:** the mechanism is REAL but venue-specific — it needs *strict* capital controls. Only KR/CN
qualify. Do not test more regional premiums without a capital-control argument first.

## M3 — PARTICIPANT BEHAVIOUR (tested to exhaustion 2026-07-27)

    skilled participants act -> their flow/positioning moves -> price follows

| Node | Result |
|---|---|
| skill persistence | REFUTED (rho -0.019, n=1400, powered) |
| elite positioning | REFUTED (t +0.15) |
| elite order flow | REFUTED (unstable + contemporaneous) |
| **risk-discipline persistence** | **CONFIRMED (t +7.63) — but manager-selection, not market signal** |

**Read:** the *market-signal* branch is dead. The *risk* branch is real but unusable by this desk
(we allocate to no external managers). Mechanism closed unless the desk ever allocates externally.

## M4 — INFORMATION DIFFUSION (untested at the right speed — THE OPEN CHAIN)

    researcher/dev -> code -> regional forums (CN/KR/JP/RU) -> aggregators -> retail -> price

| Node | Observable | Status |
|---|---|---|
| dev activity | commits, contributors | REFUTED at cross-sectional monthly (t <2) |
| attention | multilingual Wikipedia pageviews | **KILLED AT DAILY ONLY -> horizon-search candidate** |
| aggregate interest | search trends | untested |

**Read:** diffusion is INHERENTLY SLOW — days-to-weeks. Every test so far used a 1-day horizon,
which is the wrong clock for the mechanism. This is the single strongest argument for the horizon
search, and the reason `multilingual_wikipedia_attention` sits on the resurrection shortlist.

## M5 — REFLEXIVITY / FEEDBACK (genuinely uncovered)

    price move -> leverage responds -> liquidations -> forced flow -> larger price move

| Node | Observable | Status |
|---|---|---|
| leverage response | OI change vs price change | partially (OI live) |
| liquidation cascade | liquidation stream | COLLECTING (29k events) |
| feedback strength | ??? | **UNBUILT — the real gap** |

**Read:** the desk *collects* every input to this chain but has never modelled the LOOP. The
testable question is not "do liquidations predict price" (tested, weak) but "is the feedback
coefficient rising?" — a regime property, not a signal. Cheapest genuinely-new mechanism available.

---

## Coverage verdict

- **M1 saturated** — stop adding sensors, start testing links.
- **M2 real but venue-limited** — no more premiums without a controls argument.
- **M3 closed** — refuted at power.
- **M4 open and mis-tested** — wrong horizon, not wrong idea. → horizon search.
- **M5 open and unbuilt** — inputs already on disk. → best new-mechanism candidate.

## How this feeds the pipeline

    mechanism node -> observable -> hypothesis -> EV gate -> Stage-A screen -> forward clock -> Stage-B

Unchanged pipeline. The graph only decides *which* hypotheses are worth generating, and makes
"we already observe this process 7 ways" visible before someone builds an 8th sensor.
