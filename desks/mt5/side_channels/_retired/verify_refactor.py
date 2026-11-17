import sys, time
sys.path.insert(0, ".")
import pandas as pd
from mt5desk import families
from mt5desk.engine import Costs, run_backtest

h1 = pd.read_parquet("data/universe/AUDCAD_H1.parquet")
h1 = families._h1(h1)
checks = [
    ("momentum_volgate", families.family_momentum_volgate, {}, "8034/-0.448/-6.94"),
    ("asia_momentum", families.family_asia_momentum, {}, "1829/-0.211/-4.60"),
    ("monday_gap_fade", families.family_monday_gap, {"mode": "fade"}, "354/0.087/1.40"),
    ("london_close_momentum", families.family_london_close_momentum, {}, "1763/-0.239/-6.33"),
    ("spread_state_avoidance", families.family7_spread_state_avoidance, {}, "9670/-0.443/-6.60"),
    ("dow_effect", families.family_dow_effect, {}, "856/-0.139/-1.94"),
    ("comex_settlement", families.family4_comex_settlement_effect, {}, "338/-0.327/-4.81"),
]
for name, fn, p, baseline in checks:
    t0 = time.time()
    sigs = fn(h1, **p)
    t1 = time.time()
    r = run_backtest(h1, sigs, Costs(spread_per_lot=1.2, commission_per_lot=3.5, contract_oz=100000))
    st = r.stats()
    got = f"{st['n']}/{st['expectancy_r']:.3f}/{st['t_stat']:.2f}"
    ok = "MATCH" if got == baseline else "DIFF"
    print(f"{name}: {got}  [{ok}]  siggen={t1-t0:.2f}s")