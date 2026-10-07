# Japan official-plane fixtures (2026-10-06)

SYNTHETIC values in the DOCUMENTED wire format; no number here was fetched or is a measurement,
except the intervention rows, which reproduce MOF's published record (dates and amounts) so the
signed-event logic is tested on the real history's shape.

- `jp_mof_securities_weekly.csv`: MOF `week.csv` (International Transactions in Securities,
  weekly), Shift_JIS, CRLF. Layout read 2026-10-06 from
  https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.csv:
  bilingual title / unit rows, a two-line quoted header, then `YYYY年M月D日～M月D日` and 22
  numeric columns (assets: equity acq/disp/net, bonds acq/disp/net, subtotal, bills acq/disp/net,
  total; liabilities the same), comma-thousands quoted, unit 100 million yen. The cross-year
  period form `YYYY年12月D日～YYYY年1月D日` is ASSUMED (no such row was read); the parser also
  infers the year when the end month precedes the start month.
- `jp_mof_securities_investor_bonds.csv`: MOF `monthb3.csv` (same layout as the `monthb1.csv`
  read 2026-10-06): col 0 year on January rows only, col 1 Japanese month, col 2 English month,
  then 17 (acquisition, disposition, net) triplets; `-` is an empty cell.
- `jp_mof_fx_intervention.csv`: MOF `foreign_exchange_intervention_operations.csv`, Shift_JIS,
  nine columns (Japanese era year / month / day, Year, Month, Day, amount in 100 million yen,
  Japanese pair, English pair); Year and Month appear only where they change; quarterly subtotal
  rows carry no pair. Read 2026-10-06.
- `jp_boj_*.json`: BOJ Time-Series Data Search API `getDataCode` JSON. Field names (STATUS,
  MESSAGE, RESULTSET, SERIES_CODE, FREQUENCY, SURVEY_DATES, VALUES, LAST_UPDATE, NEXTPOSITION)
  are the API manual's (api_manual_en.pdf, read 2026-10-06); the manual does not print the
  nesting, so these fixtures nest SURVEY_DATES / VALUES under `VALUES` and the parser also reads
  them flat on the series. TANKAN codes are the manual's own example; the current-account and
  JGB-holdings codes are placeholders (`SYNTHETIC_*`) because the real codes are set on the box.
- `jp_jquants_investor_types.json`: J-Quants investor-type trading as `{"data": [...]}` with
  V2-style abbreviated keys (`PubDate`, `EnDate`, `Section`, `FrgnBal`, ...); the parser also
  reads V1 `trades_spec` long names (`PublishedDate`, `EndDate`, `ForeignersBalance`). The exact
  V2 field names are UNVERIFIED (the spec page was not readable here). Not an alt_proxies source:
  the lane is BLOCKED_ON_TERMS:to_confirm and reads PR #218's stored collector output.

Live yield is UNMEASURED until the trading box runs `alt_proxies`: this container's proxy refuses
www.mof.go.jp and www.stat-search.boj.or.jp for programmatic fetches.
