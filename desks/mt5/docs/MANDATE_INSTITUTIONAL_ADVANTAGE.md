# MANDATE: Institutional Information Advantage (legal, never MNPI)

Approved 2026-08-17. Supersedes nothing; binds all future research and execution.

## Target

A small systematic institution whose edge over ordinary MT5 participants comes
from knowing more, knowing it earlier, interpreting it better, and executing it
better - strictly through legal means. **Hard boundary: no material non-public
information, no insider trading, no misuse of any MNPI. Everything is derived
from public, licensed, or self-generated data.**

## The moat hierarchy (in order of defensibility)

1. **Public + institutionally-licensed data** (free: FRED, CFTC COT/TFF, BIS,
   bank statements, exchange data; licensed only if ever required and then only
   via legal license agreements).
2. **Proprietary synthetic states** - combinations of public feeds that retail
   does not hold: JPY_FLOW_STATE (TFF dealer/AM/LM net pct, am_minus_lm),
   GOLD_PHYSICAL_PRESSURE (physical-vs-paper), ASIA_LIQUIDITY_STATE,
   MACRO_STRESS, REAL_YIELD_Z, USD_LIQUIDITY_Z, session states, dealer-flow
   breadth. The free_shadows lake (data/states/free_states.parquet) is the
   production implementation - PIT-safe, 21 series, 49k bars.
3. **Private data moat** - our own accumulated observations: broker quotes,
   spreads, slippage, fills, rejections, MAE/MFE, markouts, signal outcomes,
   live ledger (data/live_ledger.jsonl), trade-path evidence, regime state.
   Retail can copy an indicator; they cannot copy years of our fills and
   decisions. **Rule: store every quote/state/signal/decision/fill/outcome
   forever (private-data compounding).**
4. **Cross-market intelligence before the MT5 chart**: Treasury yields, USD,
   JPY futures proxy flows, COT positioning, Gold physical/paper pressure,
   options-adjacent proxies (VIX-based risk state), equities and commodity
   states inform the XAUUSD/JPY/commodity interpretation - never trade the
   chart alone.
5. **Flow over indicators**: COT/TFF dealer and managed-money flows, breadth
   and crowding states replace lagging indicator reading.
6. **Predictive market-state engine**: TREND_DAY/NORMAL/RANGE/FAILED_BREAK
   (prior-NY displacement), session states, macro stress states - probabilities
   feeding every sleeve as conditioning, never replacing the mechanism.
7. **Event intelligence**: quantify surprise, revision, expectation gap and
   abnormal reaction (free: ALFRED point-in-time vintages + market reaction
   measurement). News text feeds only if free/legal.
8. **Institutional macro desk**: rates differentials, real yields, liquidity
   (Fed/ECB/BoJ balance sheets via FRED), policy-path proxies, global risk
   state, cross-asset transmission (rates -> USDJPY -> JPY crosses -> Gold;
   DXY/rates -> Gold).
9. **Execution advantage**: predict spread/slippage, select entry type, compare
   brokers on realized expectancy (broker microstructure profiler), exploit
   small niches large funds cannot trade (small-capacity advantage).
10. **Research advantage**: thousands of hypotheses, brutal OOS rejection,
   deflated t, WF + cost stress, multiplicity, auto survivor expansion,
   permanent unknown-unknown hunting.
11. **Capital advantage**: next unit of risk goes to the highest marginal
    E[log W] (allocation.py advisory; forward ledger decides).
12. **Adaptation advantage**: auto-retire (promoter), auto-hibernate (regime
    monitor now kills the gold book too), before a static EA would notice.

## The information hierarchy (target flow)

Retail sees XAUUSD moving -> our system already saw: rates moved -> JPY futures
flow -> COT dealer flow -> physical-vs-paper pressure -> risk state -> options
skew proxy -> Gold regime updated -> MT5 signal receives higher/lower expected
R -> sizing and execution adjust automatically.

## Standing rules

- NEVER purchase data (free-data supremacy directive). Buy nothing.
- Every new feature/dataset/hypothesis must beat the current best alternative
  on expected marginal forward E[log W] (Research-Capital Governor rule).
- PIT discipline on every derived series (states activate report_date+6d;
  FRED via ff_daily; no lookahead ever).
- All generated data stored forever (private data moat).
- Legal boundary is absolute: public data, licensed data with valid license
  agreements, or data we generate ourselves. If a source would be MNPI,
  it is out - permanently.