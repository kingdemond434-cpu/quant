# Korea / Hong Kong official-plane fixtures (2026-10-06)

SYNTHETIC values in the DOCUMENTED wire format; no number here was fetched or is a measurement.

- `kr_ecos_*.json`: BOK ECOS `StatisticSearch` JSON (`StatisticSearch.row[]` with `STAT_CODE`,
  `ITEM_CODE1..4`, `UNIT_NAME`, `TIME` YYYYMMDD/YYYYMM, `DATA_VALUE` as a string), the shape the
  existing `kr_bok_card_spend.json` fixture and ECOS's Open API guide use.
- `hk_hkma_*.json`: HKMA Open API envelope `{"header": {"success": ...}, "result": {"datasize",
  "records": [...]}}` with the field names from apidocs.hkma.gov.hk (read 2026-10-06):
  daily-figures-interbank-liquidity (`end_of_date`, `closing_balance`, `forex_trans_t1`,
  `hibor_fixing_1m`, `forecast_aggregate_bal_t1`, ...), hk-interbank-ir-daily segment
  `hibor.fixing` (`end_of_day`, `ir_overnight` .. `ir_12m`), daily-figures-monetary-base
  (`aggr_balance_af_disc_win`, `outstanding_efbn`, `cert_of_indebt`, `mb_bf_disc_win_total`).

- `bis_kr_policy_rate.csv` (FIXTURE, 2026-10-07): BIS WS_CBPOL in the SDMX-CSV layout a keyed
  `stats.bis.org/api/v1/data/WS_CBPOL/D.KR/all?format=csv` query returns -- dimension columns
  (`FREQ`, `REF_AREA`), then `TIME_PERIOD` (YYYY-MM-DD for daily), `OBS_VALUE` and attributes
  (`SOURCE_REF` names the originating central bank). Based on the dataflow's key shape
  (FREQ.REF_AREA) and the column codes `axis_ingest.ingest_bis` reads, as recorded in
  docs/research/data_axis_watchlist.md and data/data_universe_map.json. The values (a synthetic
  2.50 -> 2.25 step), the `NaN` row, the monthly `M` row and the `US` row are SYNTHETIC; the last
  three exist only to prove the parser drops them. The bulk flat-file shape (`CODE:Label`
  columns, zipped) is built in-test from the same rows.

Live yield is UNMEASURED until the trading box runs `alt_proxies`: this container's proxy refuses
both hosts (and www.bis.org / data.bis.org / stats.bis.org).
