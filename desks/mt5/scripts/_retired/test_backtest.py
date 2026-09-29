import subprocess
r = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && PYTHONPATH=desks/mt5 /home/quant/quant-platform/.venv/bin/python -c \""
     "import pandas as pd; "
     "from mt5desk.families import get_family_func; "
     "from mt5desk.engine import Costs, run_backtest; "
     "from mt5desk import families; "
     "df = pd.read_parquet('/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet'); "
     "h1 = families._h1(df); "
     "fn = get_family_func('session_range_breakout'); "
     "sigs = fn(h1, range_start=7, wait_bars=8, atr_n=20, ttl_bars=12, rr=2.0); "
     "print('signals:', len(sigs)); "
     "costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0); "
     "res = run_backtest(h1, sigs, costs); "
     "print('trades:', len(res.trades)); "
     "if res.trades: print('exp_r:', sum(t.r_multiple for t in res.trades)/len(res.trades))\""],
    capture_output=True, text=True, timeout=30
)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:500])