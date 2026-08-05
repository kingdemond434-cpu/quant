# PAID-DATASET TARGET REGISTRY (charter §39)

_The ANTICIPATORY half of §38. §38 hunts a replacement when a source FAILS; this hunts one for every valuable paid dataset BEFORE it fails, so the desk already knows what it would do if any vendor vanished tomorrow._

**Standing rule:** every digger reads this list every run, advances at least the top OPEN item it can, and ADDS any paid dataset it encounters that is not yet listed. Hunt order is always primary-source reconstruction first (facts are not copyrightable), then differently-licensed vendors, mirrors, community datasets, regional venues, archives -- searched across forums, obscure repos, papers, channels and NON-ENGLISH sources.

**This list is deliberately INCOMPLETE.** A fixed list is the same blind spot in a different shape, so growing it is a per-dig deliverable (§39(3)).

| Paid vendor | What it sells | Free-replacement status |
|---|---|---|
| Glassnode | on-chain metrics/indicators (SOPR, MVRV, HODL waves, entity-adjusted) | REPLACED (metric class) 2026-07-26: blockchain.info chain facts via collect_onchain_metrics; entity-adjusted + UTXO-cohort derivatives still OPEN -- reconstructable from a node/Blockchair |
| Coin Metrics | on-chain + reference rates (AdrActCnt, TxCnt, FeeTotUSD) | REPLACED 2026-07-26 (excluded on licence: CC BY-NC + ToU 6(iii) AI ban) -- same facts reconstructed from chain |
| CryptoQuant | exchange flows, miner flows, stablecoin flows | OPEN -- exchange netflow is reconstructable from labelled addresses (public label sets + own clustering); hunt free label corpora |
| Nansen | wallet labels, smart-money flows | PARTIAL (advanced 2026-07-30, prospector §39): **dawsbot/eth-labels VERIFIED — MIT license, 169k+ labeled addresses, 7 EVM chains (ETH/Base/Arb/OP/BSC/Gnosis/Celo), free public API (eth-labels.com/swagger), repo browsable JSON**. Clean-license adoptable. NOTE: exchange-address labels in this corpus are the enabling ingredient for the netflow graveyard row's named re-entry condition (per-exchange decomposition — graveyard L185). Still OPEN: Etherscan tags, Dune spellbook, own clustering |
| Chainalysis / TRM | compliance-grade entity attribution | OPEN -- likely UNPURCHASABLE-equivalent free; document the failed search honestly |
| Kaiko | consolidated multi-venue tick/L1-L2 + reference rates | PARTIAL -- raw ticks via own recorder; index METHODOLOGY public (BMR rulebook, VWM+TWAP) so the rate is reconstructable |
| Tardis.dev | historical tick + full-depth L2 across venues | PARTIAL -- free first-of-month full-depth L2 verified (~88 ground-truth days, HTTP 200); forward coverage by own recorder; mid-month history OPEN |
| Amberdata | market + on-chain + derivatives/options analytics | OPEN |
| Coinglass / Coinalyze | aggregated OI, funding, liquidations across venues | LARGELY REPLACED -- pulled per-venue direct from exchange public APIs (own aggregation) |
| Laevitas / Block Scholes / GVol | options surfaces, skew, term structure | PARTIAL -- Deribit public API gives the raw surface; own IV/skew computation |
| Santiment | social + dev activity + on-chain composites | OPEN -- dev activity from GitHub API direct; social from public endpoints |
| The Tie / LunarCrush | social sentiment aggregation | OPEN -- deprioritised (sentiment is weak-signal per the desk's own graveyard) |
| Messari / Token Terminal | protocol fundamentals, revenue, treasury | OPEN -- DefiLlama free API + protocol subgraphs cover much of this |
| Dune / Flipside / Footprint | SQL over indexed chain data | PARTIAL -- free tiers exist; heavy queries OPEN, reconstructable via own node/RPC |
| Arkham | entity attribution + flow graphs | OPEN -- overlaps the Nansen label hunt |
| CoinAPI / CryptoCompare / Velo | market-data aggregation APIs | LARGELY REPLACED -- exchange-native APIs pulled direct |
| IntoTheBlock | on-chain analytics composites | OPEN -- composites are derived; reconstruct from the same chain facts |
| Checkonchain | MVRV / realised-price charts | OPEN (excluded-no-licence) -- realised cap = UTXOs valued at last-move price, so RECONSTRUCTABLE from a node; genuinely recoverable capability |
| DefiLlama Emissions (paid tier) | dated token-unlock/vesting release schedules per protocol (`/emissions`, `/emission/<protocol>`) | OPEN — hunted 2026-08-05, NOT yet replaced. **Encountered live**: `/emissions` and `/emission/aptos` both HTTP **402 Payment Required**; `defillama.com/api/emissions` HTTP 403. Distinct product from DefiLlama's FREE protocol API (`/protocol/<x>` verified 200), which carries no schedule. Candidate free routes, in charter order: (1) PRIMARY-SOURCE RECONSTRUCTION — unlock schedules are enforced by on-chain vesting contracts, so the release calendar is chain state and facts are not copyrightable; this is the route to build. (2) project tokenomics docs, which publish the schedule directly. (3) DefiLlama's own emission ADAPTERS if open-source — **UNVERIFIED**: GitHub API answers 403 through this container's proxy and raw-path guesses 404'd, so the licence could not be checked from here and is NOT claimed. Blocks the NUMERATOR of screen_unlock_supply_series (36 declared cells); the DENOMINATOR is already accruing free via scripts/collect_circulating_supply.py. |

_seeded 2026-07-26 with 18 vendors, +1 encountered live 2026-08-05; grows every dig_
