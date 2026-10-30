# SYNTHETIC FIXTURE -- written for desks/mt5/tests/test_cell_emitter.py, not recorded from any site.
# A stochastic crossover: no registered family carries it, so it must land as an unmapped hypothesis.
import backtrader as bt


class StochCross(bt.Strategy):
    params = (('k_period', 14), ('d_period', 3))

    def __init__(self):
        self.stoch = bt.indicators.Stochastic(self.data, period=self.p.k_period)

    def next(self):
        if self.stoch.percK[0] > self.stoch.percD[0] and self.stoch.percK[-1] <= self.stoch.percD[-1]:
            self.buy()
