import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, '<CLONE_ROOT>/Miasyster_QuantGPT')
from quantgpt.adversarial_validator import AdversarialValidator, _daily_spearman_ic

def build(true_ic, seed, n_stocks=40, n_days=200):
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range('2020-01-01', periods=n_days)
    f = rng.normal(size=(n_stocks, n_days)); eps = rng.normal(size=(n_stocks, n_days))
    fwd = true_ic*f + np.sqrt(max(0.0,1-true_ic**2))*eps
    return pd.DataFrame({
        'stock_code': np.repeat([f'S{s:03d}' for s in range(n_stocks)], n_days),
        'trade_date': np.tile(dates, n_stocks),
        'factor_value': f.ravel(),
        'daily_ret': rng.normal(0,0.01,size=n_stocks*n_days),
        '_fwd': fwd.ravel()})

def run(true_ic, seed):
    df = build(true_ic, seed)
    v = AdversarialValidator(df[['stock_code','trade_date','factor_value','daily_ret']].copy(), 5)
    key = df.set_index(['stock_code','trade_date'])['_fwd']
    v.df['fwd_ret'] = pd.MultiIndex.from_arrays([v.df['stock_code'], v.df['trade_date']]).map(key)
    realized = float(_daily_spearman_ic(v.df).mean())
    return realized, v.test_random_universe(n_trials=12), v.test_noise_injection()

print(f"{'true_ic':>7} {'realized':>9} | {'RU':>6} {'consist':>8} | {'NI':>6} {'reten@0.5':>10}", flush=True)
out=[]
for tic in [0.0,0.0,0.0,0.05,0.10,0.20,0.40]:
    for seed in [1,2]:
        ric, ru, ni = run(tic, seed)
        c=ru.details.get('consistency'); r=ni.details.get('retention_at_0.5x')
        print(f"{tic:7.2f} {ric:9.4f} | {str(ru.passed):>6} {str(c):>8} | {str(ni.passed):>6} {str(r):>10}", flush=True)
        out.append(dict(true_ic=tic,seed=seed,realized_ic=ric,ru_passed=bool(ru.passed),
                        consistency=c,ni_passed=bool(ni.passed),retention_at_0_5=r,
                        noise_curve=ni.details.get('noise_ics')))
json.dump(out,open('<CLONE_ROOT>/ctl/power_results.json','w'),indent=1)
print("DONE", flush=True)
