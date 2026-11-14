# SYNTHETIC FIXTURE -- written for desks/mt5/tests/test_cell_emitter.py, not recorded from any site.
# Shaped like a freqtrade strategy: exchange-native ground, so it may map ONLY onto crypto CFDs.
from freqtrade.strategy import IStrategy
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class SyntheticEma(IStrategy):
    timeframe = '1h'
    pairs = ["ETH/USDT", "SOL/USDT"]

    def populate_indicators(self, dataframe, metadata):
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=30)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[qtpylib.crossed_above(dataframe['ema_fast'], dataframe['ema_slow']),
                      'enter_long'] = 1
        return dataframe
