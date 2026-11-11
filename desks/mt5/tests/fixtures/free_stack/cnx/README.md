# China exchange fixtures (free_stack `cn_exchange`, audit package P2)

Every file here is HAND-BUILT. None was fetched: the build sandbox's proxy refuses every exchange
host (SHFE, INE, DCE, CZCE, GFEX, CFFEX), so these prove the parsers, not the sources. The live
yield is UNMEASURED until the trading box runs `free_stack_hunt` with the row's `terms` confirmed.
The numbers are invented; only the layout follows the exchange.

What each layout is based on. These are the field names and layouts the exchanges publish, as
read by the open-source parsers that have consumed them for years (AKShare `futures_*` and
`get_*_rank_table`, and the `tushare` / `opendatatools` exchange readers), and as the exchanges
document them on their data pages:

| File | Exchange publication | Layout reproduced |
|---|---|---|
| `shfe_kx.synthetic.json` | SHFE `data/dailydata/kx/kx<YYYYMMDD>.dat` | `o_curinstrument[]` with PRODUCTID (`cu_f`), PRODUCTGROUPID, DELIVERYMONTH (`2611`, or `小计` subtotal), PRESETTLEMENTPRICE, OPEN/HIGHEST/LOWEST/CLOSE/SETTLEMENTPRICE, VOLUME, OPENINTEREST, OPENINTERESTCHG; padded strings as the exchange pads them |
| `shfe_pm.synthetic.json` | SHFE `data/dailydata/kx/pm<YYYYMMDD>.dat` | `o_cursor[]` per contract: INSTRUMENTID, RANK 1-20 (999 = member total row), PARTICIPANTABBR1/CJ1/CJ1_CHG (volume), PARTICIPANTABBR2/CJ2/CJ2_CHG (long OI), PARTICIPANTABBR3/CJ3/CJ3_CHG (short OI) |
| `shfe_dailystock.synthetic.json` | SHFE `data/dailydata/<YYYYMMDD>dailystock.dat` | `o_cursor[]`: VARNAME `铜$$Copper`, REGNAME, WHABBRNAME (warehouse; `合计$$Subtotal` region rows; `总计$$Total` product row), WRTWGHTS (warrant weight), WRTCHANGE, UNIT |
| `shfe_weeklystock.synthetic.json` | SHFE `data/dailydata/<YYYYMMDD>weeklystock.dat` (Fridays) | same shape with WHSTOCKS (inventory) beside WRTWGHTS |
| `dce_daily.synthetic.txt` | DCE `exportDayQuotesChData.html?...&exportFlag=txt` | tab-separated, header 商品名称 交割月份 开盘价 最高价 最低价 收盘价 前结算价 结算价 涨跌 涨跌1 成交量 持仓量 持仓量变化 成交额, thousands separators, 小计 / 总计 rows |
| `dce_rank_i.synthetic.txt` | DCE `exportMemberDealPosiQuotesData.html?...&exportFlag=txt` | three blocks headed 名次 会员简称 成交量/持买单量/持卖单量 增减, each closed by 总计 |
| `czce_daily.synthetic.txt` | CZCE `DFSStaticFiles/Future/<YYYY>/<YYYYMMDD>/FutureDataDaily.txt` | title line, then pipe-separated 品种月份 昨结算 今开盘 最高价 最低价 今收盘 今结算 涨跌1 涨跌2 成交量(手) 持仓量 增减量 成交额(万元) 交割结算价; 3-digit YMM contract codes |
| `czce_holding.synthetic.txt` | CZCE `.../FutureDataHolding.txt` | `品种：棉花CF  日期：` (product) and `合约：CF601  日期：` (contract) blocks; pipe rows 名次 会员简称 成交量（手） 增减量 会员简称 持买仓量 增减量 会员简称 持卖仓量 增减量; 合计 row |
| `gfex_daily.synthetic.json` | GFEX `u/interfacesWebTiDayQuotes/loadList` (POST) | `data[]`: variety, varietyOrder, delivMonth, open/high/low/close, lastClear, clearPrice, volumn (the exchange's spelling), openInterest, diffI |
| `gfex_rank.synthetic.json` | GFEX `u/interfacesWebTiMemberDealPosiQuotes/loadList` (POST, data_type 1/2/3) | `data[]`: rank, abbr, todayQty, qtySub |
| `cffex_daily.synthetic.xml` | CFFEX `sj/hqsj/rtj/<YYYYMM>/<DD>/index.xml` | `<dailydatas><dailydata>` with instrumentid, openprice ... preopeninterest, openinterest, presettlementprice, settlementprice, volume, productid; an option row (IO...-C-...) the parser must skip |
| `cffex_rank_IF.synthetic.xml` | CFFEX `sj/ccpm/<YYYYMM>/<DD>/IF.xml` | `<positionRank><data>` with instrumentid, datatypeid 0/1/2 (volume/long/short), rank, shortname, volume, varvolume, productid |

Known uncertainties the box must measure (the fetcher tries every template in
`libs/data/free_stack_cnx.URLS` and records which surface was missing per day in the raw
archive's `missing_surfaces`): SHFE and INE moved to `data/tradedata/future/dailydata/` paths in
2024-25; DCE's `contract.contract_id=all` product-scope ranking and GFEX's member field spellings
vary by release. A shape the parser does not recognise yields NO observation for that surface,
never a zero.
