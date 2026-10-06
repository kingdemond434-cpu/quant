# China official-table fixtures (cn_official_tables / asia_parser ledger tests)

This container's proxy refuses safe.gov.cn, chinamoney.com.cn, pbc.gov.cn, stats.gov.cn and
customs.gov.cn, so none of these bytes was fetched live. Each file reproduces the PUBLISHED layout
of its source as documented by the source's own pages and by the public client libraries that read
them; the VALUES are illustrative and are never presented as measured. The first box pass of
`asia_collector` -> `asia_parser` is the live measurement: a changed shape reads PARSE_ERROR /
NO_TABLE with its reason, never as an empty series.

| file | shape it reproduces |
|---|---|
| `ccpr.json` | ChinaMoney `r/cms/www/chinamoney/data/fx/ccpr.json`: `data.lastDate` ("YYYY-MM-DD 9:15") + `records[]` with `vrtEName` / `price` / `bp` |
| `ccpr_history.json` | ChinaMoney `ags/ms/cm-u-bk-ccpr/CcprHisNew`: `data.head[]` pair names + `records[]` of `{date, values[]}` |
| `shibor.json` | ChinaMoney `r/cms/www/chinamoney/data/shibor/shibor.json`: `data.showDateCN` + `records[]` of `{termCode, shibor}` |
| `nbs_pmi.json` | NBS `data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgyd` cube: `returndata.datanodes[]` keyed `zb.<code>_sj.<yyyymm>` + `returndata.wdnodes[]` code -> cname/unit (sub-index names as NBS prints them) |
| `safe_index.html` | SAFE column index (`/safe/<column>/index.html`): release articles linked as `/safe/YYYY/MMDD/<id>.html` |
| `safe_article.html` | SAFE monthly release article: `<meta name="PubDate">`, `发布时间`, an inline months-across table with `一、结汇 / （一）银行自身结汇 / （二）代客结汇 / 二、售汇 / ... / 三、差额` and forward-contract rows, `单位：亿元人民币`, and an .xlsx attachment link |
| `pboc_omo_index.html` | PBOC 公开市场业务交易公告 list page |
| `pboc_omo_article.html` | PBOC OMO announcement prose ("以固定利率、数量招标方式开展了N亿元7天期逆回购操作", "中标利率为x%", "当日有N亿元逆回购到期") |
| `customs_import_table.html` | GACC monthly "进口主要商品量值表": two-row header (month / cumulative over 数量 / 金额), 计量单位 column, title carrying the month and direction |
| `sge_daily_quote.html` | SGE 每日行情 table (合约 / 开盘价 / 最高价 / 最低价 / 收盘价 / 加权平均价 / 成交量 / 成交金额 / 持仓量 / 交收量) -- parsed ONLY when SGE's terms are confirmed; they are REFUSED (see alt_proxies.TERMS_EVIDENCE) |
| `sge_benchmark.html` | SGE 上海金基准价 table (日期 / 早盘价 / 午盘价) and silver benchmark (日期 / 基准价) -- same terms gate |
