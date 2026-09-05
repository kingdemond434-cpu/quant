# MT5 SOURCE SEEDS — a hunting map, deliberately NOT the catalogue

**Status: SEEDS. Nothing here is verified, nothing here is catalogued, and nothing here may be
cited.** Retargeted 2026-09-05 to the MT5/Fusion universe under the 2026-08-18 principal mandate.
It replaces `crypto_source_seeds.md` (later `offbook_source_seeds.md`), which was a
Binance/crypto-native mining universe and is retired with the desk that hunted it. The *structure*
of that file — a reading map carrying no verification debt — was the part worth keeping, and it is
kept here verbatim in spirit.

## Why this is a separate artifact from `data_axis_watchlist.md`

The watchlist is the CATALOGUE: every card in it carries a grade and owes a verification decision.
Measured 2026-08-07: **18 catalogued, 10 resolved, 8 still pending** (5 technical, 3 legitimacy).
The miners' own standing instruction is explicit about what that means —

> *the desk's bottleneck is verification, not cataloguing (it already catalogues faster than
> anything gets verified) … Cataloguing a new source while 10 sit unverified is breadth-theater
> and a DEFECT.*

Bulk-inserting hundreds of sources as cards would take the backlog from 8 to several hundred and
make the desk's worst-measured bottleneck an order of magnitude worse, while producing zero
verified sources. So this file is a **reading map with no verification debt**: a miner draws the
next ground from here, digs it, and only a source that produced something worth returning to is
promoted into the catalogue as a graded card — one at a time, through
`scripts/source_backlog_next.py`.

**IT IS ALSO NOT A CEILING.** The list is seeds. The discovery layer above the regional miners
exists to find grounds NOT on this list — new forums, authors, repositories, datasets,
communities — and any miner that finishes a session having read only from this file has treated a
seed map as a boundary.

## Priority order — by what can be SETTLED, not by what sounds credible

Executable artifacts rank first because they are **cheapest to refute**, not because code is more
honest — published EA code is if anything more overfit than an anecdote, having been tuned until
the curve looked good.

    platform-native strategy code > code repos > quant platforms > microstructure/execution
      research > academic > alpha ecosystems > broker and exchange research > macro/official data
      > regional practitioner communities > general forums

## The grounds

**PLATFORM-NATIVE STRATEGY CODE (highest executable yield — the code *is* the post).** MQL5.com
CodeBase, Articles, Forum and Signals (and the MQL4 CodeBase archive, a finite and
one-time-exhaustible corpus); TradingView public Pine scripts and their comment threads;
cTrader cBots and the cTDN forum; NinjaTrader and MultiCharts user strategy libraries.

**CODE REPOSITORIES.** GitHub/GitLab/Gitee: MetaTrader5 Python API projects, MQL4/MQL5 EA
collections, FX and gold backtesting frameworks, tick-data tooling, broker-API wrappers, order
book / execution-quality analysis, statistical arbitrage and pairs trading on FX crosses,
walk-forward and optimisation harnesses.

**QUANT PLATFORMS.** QuantConnect / LEAN (forum and FX/futures research), Backtrader, VectorBT,
NautilusTrader, vn.py, Microsoft Qlib, Zipline forks.

**MICROSTRUCTURE / EXECUTION RESEARCH.** Order flow, DOM and footprint, spread and slippage
studies, latency and last-look research, transaction-cost analysis, retail-broker execution
studies, and the academic FX-microstructure literature.

**ACADEMIC.** arXiv q-fin (market microstructure, algorithmic trading, FX), SSRN (FX, commodities,
index futures, carry, momentum), Google Scholar, Papers With Code, central-bank and BIS working
papers (the BIS Triennial FX survey is a standing structural read).

**ALPHA ECOSYSTEMS.** WorldQuant BRAIN (forum, alpha discussions, operator taxonomy), Numerai +
Signals, Quantiacs, Quantopian archives, Quantocracy, QuantStart, QuantInsti, Alpha Architect,
Robot Wealth, Quant SE / Wilmott / Nuclear Phynance / Elite Trader / futures.io.

**BROKER, VENUE AND EXCHANGE RESEARCH.** Fusion Markets and peer-broker specs, swap tables and
execution disclosures (the desk's own cost surface is the benchmark); CME/ICE/LME product
specifications, settlement procedures and roll calendars; LBMA gold and silver benchmark
documentation; exchange holiday and session calendars, which drive the desk's session axis.

**MACRO / OFFICIAL DATA.** CFTC Commitments of Traders, FRED, central-bank calendars and
statements, Treasury and rates curves, DXY constituents, EIA and USDA reports for energy and
softs, and the release-time metadata that makes an event study point-in-time correct.

**REGIONAL — the desk's existing seven miners own these.** Each seat's own brief carries its
grounds, era targets, native lexicon and diaspora list; see `ops/frontier_<region>_prompt.txt`.
In one line each: EN legacy quant forums and the MQL4/MQL5 EN community; RU habr, smart-lab and
the MQL5 Russian author base; CN Gitee/Zhihu/Xueqiu plus the domestic futures program-trading
boards; JP note.com, Qiita/Zenn, 5ch and the MT4/MT5 EA ecosystem; KR Naver, DCInside and the HTS
Open API ecosystems; AR Gulf gold and FX communities and the MQL5 Arabic sections; BR PT-BR
channels and the B3-adjacent algo communities.

## What is NOT a ground

Crypto-exchange-native venues, on-chain analytics, DeFi governance forums and perpetual-funding
research are **retired** (principal mandate, 2026-08-18). Crypto reference data may be read only
when it informs a Fusion-executable MT5 instrument, never as a universe hunted for its own sake.
The historical record of that era is preserved under `docs/archive/` and in the desk-memory files
(`docs/graveyard.md`, `docs/institutional_knowledge.md`, `docs/research/negative_knowledge.md`);
it is history to learn from, not a list to dig.
