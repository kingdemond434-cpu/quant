# CN OSS TOOL-CHAIN EXTRACTION — 2026-07-31

> ## ⛔ CORRECTIONS 2026-08-01 (CN frontier miner session 3) — READ BEFORE ACTING ON ANYTHING BELOW
> Two headline verdicts in this document are **REFUTED** by a deeper pass that read the primary
> sources. Corrected here at source rather than only in a session note, because a retraction that
> lands in one place is the kimchi failure mode.
>
> 1. **"AlphaGPT — the in-repo `paper/20251226.pdf` is the one real target" — WRONG.** That PDF is
>    *"Defense in Predatory Markets: A Differential Game Framework for AMM Liquidity via Uniswap V4
>    Hooks"* — not a factor-mining paper. Its whole validation is 1,000 Monte-Carlo paths of a
>    synthetic jump-diffusion (**zero real observations**), and it is internally contradictory:
>    Proposition 1 asserts the opposite of what its own proof derives, with unedited first-person
>    LLM self-correction (*"Ah, the initial modeling as zero-sum was an oversimplification"*) left
>    inside the text. **Treat as unreviewed LLM output; cite none of its numbers.** The repo's real
>    method is a REINFORCE Transformer over **6 price features**, scored in-sample with no
>    train/test split — the already-refuted 420/0 class.
>    ⚠ `times.py:13` holds a **hardcoded live Tushare token** (a third party's credential). Do not use.
> 2. **"NOFX — 3 mechanism constructions worth carding" — REFUTED, 0 of 3 exist in the code.** The
>    phrase that entered this record, *"the crowd's fuel and walls"*, is **verbatim README marketing
>    copy (line 70)** — a README was read and recorded as a code reading. Two of the three are one
>    purchased endpoint (`claw402.ai/.../cost-liquidation-heatmap`); cross-exchange net flow does
>    not exist. **That row is retired as secondhand.**
> 3. **Baseline caveat below is CLOSED:** `data/data_universe_map.json` **does** exist on the box
>    (87KB). It contains **zero** entries for geckoterminal / birdeye / dexscreener / tushare /
>    akshare / solscan / helius / moralis, and the collector inventory has **no DEX-native host at
>    all** — so the NEW flags stand, and the on-chain pool/trade axis is entirely uncovered.
> 4. **Vibe-Trading's crypto layer is strictly WEAKER than ours** (OHLCV + funding only; no book, no
>    tape, no liquidations) — honest null on the tranche's stated purpose. Its value turned out to be
>    an unrelated keyless **Eastmoney CN alt-data stack** (6 feeds, up to 26y) — **§13 UNRESOLVED,
>    undocumented internal APIs with no stated terms; decision owed as R0290, do NOT build against
>    it until that clears.**
> 5. ⚠ **`discord.gg/2vDYc2w5` (the old Vibe-Trading README invite) is a hostile impostor server
>    running a wallet drainer**, disowned by a repo collaborator. Official: `discord.gg/6TdQnT5xcF`.
>
> _Rows opened by this pass: R0289 (leakage-guard blindness), R0290 (§13 Eastmoney), R0291 (GeckoTerminal)._

**Provenance:** principal-supplied LLM survey of 10 Chinese-ecosystem crypto/quant OSS projects,
verified same-day by a bounded web extraction (public pages only; no clones, no installs — the
MINE-NEVER-ADOPT rule in `ops/frontier_cn_prompt.txt` stands). This is the permanent record; the
CN frontier seat's tranche block points here for verdicts so verification is never re-spent.

**Baseline caveat honestly logged:** `data/data_universe_map.json` does not exist in the checkout
this ran against (the watchlist references it) — the ALREADY/NEW flags below were built from
`data_axis_watchlist.md` (full read), `data/data_assets.json`, and the API hosts in
`scripts/collect_*.py`. If the universe map lives on the box only, re-check the NEW flags there.

## VERDICTS (10 projects)

| project | verdict | licence | extraction value |
|---|---|---|---|
| Vibe-Trading (HKUDS, 28.9k★) | REAL; 452-factor claim TRUE (now 460) | MIT | **highest** — CN flow feeds + methods |
| QuantDinger (Open Byte, 10.1k★) | REAL | Apache-2.0 backend ONLY (frontend/mobile proprietary) | medium — AkShare/venue list |
| NOFX (12.7k★) | REAL; multi-model self-evolution confirmed | **AGPL-3.0 — no code lift, read-only** | high — 3 mechanism constructions |
| DeerFlow (ByteDance, 78.3k★) | REAL; now a general SuperAgent harness | MIT | engine patterns only, no market data |
| ValueCell (~11k★) | REAL | Apache-2.0 | low — agent shell over exchanges |
| AlphaGPT (imbue-bit, ~3k★) | REAL but thinner than described; sources undisclosed | Apache-2.0 | one target: in-repo paper PDF |
| evmscope (3★) | REAL but marginal | MIT | its free-API map, not its code |
| coin-mcp (0★) | REAL but marginal; 49-tool claim TRUE | MIT | 2-3 feed pointers |
| cola_ai | **NOT FOUND — probable hallucination** | — | zero; do not cite |
| Kimi Work (Moonshot) | EXISTS-BUT-DIFFERENT: proprietary desktop agent, not OSS | proprietary | none (browser-session pattern is ToS-grey class) |

## TOP-5 NEW-TO-DESK AXES (each with stated mechanism — screen-on-discovery applies)

1. **CN A-share flow microstructure, free APIs (Eastmoney/AkShare/Tushare via Vibe-Trading):**
   northbound Stock Connect flows, dragon-tiger lists (龙虎榜), **margin balances**. Mechanism:
   mainland retail leverage appetite propagates into crypto through the same CN-retail channel the
   desk validated as real-but-contrarian on the CNY OTC premium axis (Card 9); margin balance is a
   direct leverage-cycle observable orthogonal to everything collected.
2. **Liquidation-heatmap / cost-basis distribution reconstruction** (NOFX's Claw402 concept —
   rebuild free from the existing Coinalyze lead + OI/funding; never buy the proprietary feed).
   Mechanism: clustered liquidation prices are pre-committed forced flow; price is drawn toward
   the largest pool of forced buyers/sellers and cascade fuel is measurable ex-ante.
3. **DexScreener long-tail DEX pair liquidity + new-listing feed** (coin-mcp pointer). Mechanism:
   price discovery for new tokens happens DEX-first; liquidity-depth migration and deployer/LP
   behaviour lead CEX listing flows — invisible in every venue feed currently recorded.
4. **Token-holder concentration deltas** (Ethplorer/Etherscan-family via evmscope). Mechanism:
   supply concentrating into few wallets raises forced-sale fragility and marks
   accumulation/distribution BEFORE it prints on exchange netflow — wallet-distribution
   resolution where Coin Metrics aggregate flows (screened flat) are exchange-aggregate.
5. **Perp-DEX funding on access-segmented venues (Aster/Lighter)**. Mechanism: the same
   participant-segmentation argument the desk accepted for Cboe-vs-offshore basis (card 22),
   opposite end — degen-retail perp-DEX funding vs CEX funding isolates a cohort the
   Binance/Bybit/Hyperliquid set only partially sees. Runner-up: CoinGecko corporate-treasury
   holdings.

## MECHANISM-CARRYING CONSTRUCTIONS (graveyard-check before carding)

- Liquidation heat mapping; cost-basis distribution ("crowd's fuel and walls"); cross-exchange
  net flow as positioning migration (all NOFX/Claw402 concepts, reconstruct-don't-buy).
- Academic family from Vibe-Trading: FF5 premia proxies, Carhart momentum (slow diffusion),
  Frazzini-Pedersen Betting-Against-Beta (leverage-constrained investors flatten the SML).
  NOTE: qlib158/alpha101/gtja191 are bare price-pattern families — the 420/0-refuted class;
  excluded by design, do NOT breadth-screen them.

## ENGINE IDEAS (routed to the §42 ledger, not built now — the gate repair outranks a faster generator)

- Vibe-Trading: AST purity gates + operator-level lookahead ban on a factor DSL; factor lifecycle
  triage alive/reversed/dead via IC+IR (close to §26); Ebbinghaus-decay quality-scored agent memory.
- NOFX: strict LLM-proposes / runtime-clamps separation (hard limits the model cannot override —
  the desk already lives this; their account-PnL-selected prompt evolution is the novel half).
- DeerFlow: delegate-only-when-wall-clock-savings-exceed-duplicated-discovery cost rule;
  sub-agent context isolation with structured reporting.

## DIG GROUNDS FOR THE CN SEAT (deeper passes)

- **Vibe-Trading** issues #476 (security audit), #331, discussion #468, Discord — highest-quality
  target of the list.
- **AlphaGPT** `paper/20251226.pdf` — the only real extraction target there.
- **NOFX** issues (452 open) + Telegram + OneKey's governance post-mortem
  ("Hackgate/Infighting-gate/Open-source-gate") — read the post-mortem BEFORE trusting anything
  operational from that codebase.
- QuantDinger issues/discussions; DeerFlow discussions (engine patterns only).

**Licence flags:** NOFX AGPL-3.0 (read-only inspiration; any code lift needs a ruling);
QuantDinger frontend/mobile proprietary (backend Apache-2.0 fine); Kimi Work proprietary.
