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

Live yield is UNMEASURED until the trading box runs `alt_proxies`: this container's proxy refuses
both hosts.
