# SYNTHETIC FIXTURE -- written for desks/mt5/tests/test_cell_emitter.py, not recorded from any site.
# An exchange-native mechanism: it reads the perpetual funding rate, which no CFD has.
from freqtrade.strategy import IStrategy
import talib.abstract as ta


class SyntheticFunding(IStrategy):
    def populate_indicators(self, dataframe, metadata):
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['funding'] = self.dp.funding_rate(metadata['pair'])
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[(dataframe['funding'] < -0.01) & (dataframe['rsi'] < 30), 'enter_long'] = 1
        return dataframe
