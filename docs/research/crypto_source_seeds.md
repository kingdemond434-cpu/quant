# CRYPTO SOURCE SEEDS — a hunting map, deliberately NOT the catalogue

**Status: SEEDS. Nothing here is verified, nothing here is catalogued, and nothing here may be
cited.** Principal-supplied 2026-08-07 as a Binance/crypto-native mining universe.

## Why this is a separate artifact from `data_axis_watchlist.md`

The watchlist is the CATALOGUE: every card in it carries a grade and owes a verification decision.
Measured 2026-08-07: **18 catalogued, 10 resolved, 8 still pending** (5 technical, 3 legitimacy).
The miners' own standing instruction is explicit about what that means —

> *the desk's bottleneck is verification, not cataloguing (it already catalogues faster than
> anything gets verified) … Cataloguing a new source while 10 sit unverified is breadth-theater
> and a DEFECT.*

Bulk-inserting 450 sources as cards would take the backlog from 8 to ~458 and make the desk's
worst-measured bottleneck an order of magnitude worse, while producing zero verified sources. So
this file is a **reading map with no verification debt**: a miner draws the next ground from here,
digs it, and only a source that produced something worth returning to is promoted into the
catalogue as a graded card — one at a time, through `scripts/source_backlog_next.py`.

**IT IS ALSO NOT A CEILING.** The list is seeds. `kimi_hunter` runs as the discovery layer above
the regional miners: its job is to find grounds NOT on this list — new forums, authors,
repositories, datasets, communities — and any miner that finishes a session having read only from
this file has treated a seed map as a boundary.

## Priority order — by what can be SETTLED, not by what sounds credible

`libs/research/evidence_tier.py` carries this as data (`SOURCE_CLASS_YIELD`). Executable artifacts
rank first because they are **cheapest to refute**, not because code is more honest — published bot
code is if anything more overfit than an anecdote, having been tuned until the curve looked good.

    bot frameworks > code repos > quant platforms > microstructure research > academic
      > alpha ecosystems > exchange research > on-chain analytics > governance forums
      > regional communities > general forums

## The grounds

**BOT FRAMEWORKS (highest executable yield — the code *is* the post).** Hummingbot (Discord,
GitHub, discussions, Botcamp, Bot Battle), Freqtrade (Discord, GitHub, strategy repos, FreqAI,
Telegram), OctoBot, Jesse, CCXT (issues + discussions), Gekko, Superalgos, NautilusTrader,
3Commas, Pionex.

**CODE REPOSITORIES.** GitHub: Binance spot/futures bots, market-making, arbitrage (cross-exchange,
triangular, CEX–DEX, DEX), MEV bots, liquidation bots, funding-arbitrage, basis trading, statistical
arbitrage, pairs trading, order-book/LOB-ML, HFT crypto, crypto RL/transformers/NLP/sentiment,
on-chain and DeFi trading systems.

**QUANT PLATFORMS.** QuantConnect / LEAN (forum, Discord, crypto research), vn.py + `vnpy.alpha`,
Microsoft Qlib, VectorBT, Backtrader, AlgoTrader.

**MICROSTRUCTURE / EXECUTION RESEARCH.** Order book, order flow, footprint, latency arbitrage,
market impact, transaction-cost and execution research communities.

**ACADEMIC.** arXiv q-fin (cryptocurrency, market microstructure, algorithmic trading), SSRN
crypto, Google Scholar, Papers With Code, Hugging Face.

**ALPHA ECOSYSTEMS.** WorldQuant BRAIN (forum, alpha discussions, operator taxonomy), Numerai +
Signals (forum, Discord), Quantiacs, Quantopian archives, Quantocracy, QuantStart, QuantInsti,
Alpha Architect, Robot Wealth, Quant SE / Wilmott / Nuclear Phynance / Elite Trader / futures.io.

**EXCHANGE RESEARCH + DEV.** Binance (Research, Square, Developers, GitHub, API + Futures
communities, Academy), Bybit, OKX, Coinbase Institutional, Kraken, Bitget, Gate, KuCoin,
Hyperliquid (community, GitHub, Discord), Deribit Insights, CME crypto research.

**ON-CHAIN / DEFI / MEV.** ethresear.ch, Flashbots (research + Discord), MEV-Boost, EigenLayer,
governance forums (Aave, Uniswap, Curve, Balancer, Yearn, Maker, Compound, Arbitrum, Optimism),
Dune, Flipside, Nansen, Glassnode, CryptoQuant, Coin Metrics, DeFiLlama, Token Terminal, Messari,
The Block Research, CoinGlass.

**DATA / DERIVATIVES / ALT-INFO.** Kaiko, Amberdata, CCData, IntoTheBlock, Santiment, LunarCrush,
Arkham, Artemis, Allium, TokenInsight, The Tie, Kaito; desk research from Paradigm, a16z crypto,
Multicoin, Dragonfly, Delphi, Galaxy, Pantera, Jump Crypto, Wintermute, Cumberland, GSR, Amber.

**REGIONAL — the desk's existing seven miners own these.** CN: 雪球, 知乎, CSDN, 掘金, 聚宽, 米筐,
优矿, BigQuant, 集思录, 巴比特/ChainNode archives, PANews, Odaily, 金色财经, BlockBeats, MarsBit,
ChainCatcher, 吴说, 深潮 TechFlow, 币乎, Foresight News. JP: 5ch, Qiita, Zenn, note, Hatena.
KR: Naver cafes, Coinpan, DC Inside, Tistory. RU: Smart-Lab, Habr, Telegram research channels.
IN/BR/AR/TR and SE-Asia (ID/VN/TH/PH/MY/SG/HK/TW) communities, TradingView locales, regional GitHub.

**GENERAL FORUMS (lowest yield, still ore).** r/algotrading, r/quant, r/HighFrequencyTrading,
r/MarketMicrostructure, r/BitcoinMarkets, r/CryptoMarkets, r/ethfinance, r/defi, r/MEV,
r/Flashbots, r/Hyperliquid, exchange subreddits, r/options, r/FuturesTrading.

## Mechanism vocabulary to extract against

`CRYPTO_MECHANISMS` in `libs/research/evidence_tier.py`: funding · open interest · liquidation ·
basis · order flow · book imbalance · trade intensity · volatility · market regime · cross-exchange
spread · stablecoin flows · on-chain flows · whale activity · CEX/DEX flows · MEV · arbitrage ·
liquidation cascades · sentiment · derivatives positioning · options skew · term structure · funding
dispersion · volume/price · latency & microstructure.

**A finding that maps to NONE of these is the interesting case**, not the discardable one: the
desk's entire feature set is in that list, so a mechanism outside it is the only kind that widens
the search space rather than re-searching it.

## What a source is allowed to produce

Ore. `libs/research/evidence_tier.Reproduction` keeps `claimed` and `verified` in separate columns,
`verified` starts as `None`, and no code path moves a number between them — that requires a run on
the desk's own data. A claimed 40% month is not a result, however precisely it is stated.

## Authority

**NONE.** This file catalogues nothing, verifies nothing, and promotes nothing. A source that
proves productive earns a graded card in `data_axis_watchlist.md`; everything else stays a lead.
