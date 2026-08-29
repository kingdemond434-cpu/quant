"""s21: port the 100k-eval GA's fitness layer verbatim and measure its optimum.

Source: zhutoutoutousan/worldquant-miner @ 6a0c9433, stone_age/python/gui/alpha_mining.py
(AlphaMiner.evaluate_fitness + helpers, transcribed, not imported).
RESEARCH FREEZE: writes only data/*.
"""
import json, numpy as np, pandas as pd

# ---- verbatim port of the source's fitness layer ----------------------------
def apply_alpha(data, p):
    op, w, wt = p['operator'], p['window'], p['weight']
    if op == 'rank':
        s = data['close'].rolling(w).rank()
    elif op == 'decay':
        wts = np.exp(-p['decay_rate'] * np.arange(w))
        s = data['close'].rolling(w).apply(lambda x: np.sum(x * wts) / np.sum(wts), raw=True)
    elif op == 'scale':
        s = data['close'].rolling(w).mean() * p['scale_factor']
    else:
        s = data['close'].diff(w)
    return s * wt

def sharpe(s):
    r = s.pct_change()
    return float(np.sqrt(252) * r.mean() / r.std())

def turnover(s):
    return float(np.abs(s.diff()).mean())

def ic(s, rets):
    return float(s.corr(rets))

def fitness(data, p):
    s = apply_alpha(data, p)
    sh, to, c = sharpe(s), turnover(s), ic(s, data['returns'])
    return sh * 0.4 + c * 0.4 - to * 0.2, sh, to, c

# ---- data arms --------------------------------------------------------------
def source_data(seed=0):
    """The source's own in-code dataset, verbatim: close and returns INDEPENDENT."""
    np.random.seed(seed)
    idx = pd.date_range(start='2020-01-01', periods=1000)
    return pd.DataFrame({'close': np.random.random(1000),
                         'returns': np.random.random(1000)}, index=idx)

def desk_data():
    df = pd.read_parquet('desks/mt5/data/universe/EURUSD_H1.parquet')
    df = df.rename(columns=str.lower)
    d = pd.DataFrame({'close': df['close'].astype(float).values})
    d['returns'] = d['close'].pct_change().shift(-1)   # next-bar return, the honest target
    return d.dropna().reset_index(drop=True).tail(5000).reset_index(drop=True)

OUT = {'source': 'zhutoutoutousan/worldquant-miner@6a0c9433 stone_age/python/gui/alpha_mining.py',
       'arms': {}}

for name, data in (('source_random', source_data()), ('desk_EURUSD_H1', desk_data())):
    arm = {}
    base = {'operator': 'delta', 'window': 20, 'weight': 1.0,
            'decay_rate': 0.2, 'scale_factor': 1.0}

    # A: sign invariance of the two scale-free-reward legs
    pos = fitness(data, dict(base, weight=+1.0))
    neg = fitness(data, dict(base, weight=-1.0))
    arm['sign_invariance'] = {
        'sharpe_pos': pos[1], 'sharpe_neg': neg[1], 'sharpe_identical': abs(pos[1]-neg[1]) < 1e-12,
        'turnover_pos': pos[2], 'turnover_neg': neg[2], 'turnover_identical': abs(pos[2]-neg[2]) < 1e-12,
        'ic_pos': pos[3], 'ic_neg': neg[3], 'ic_flips': abs(pos[3]+neg[3]) < 1e-12}

    # B: the degenerate optimum -- reward is scale-invariant, penalty is not
    scan = []
    for w in (1e-6, 1e-4, 1e-2, 0.1, 1.0, 10.0, 100.0):
        f, sh, to, c = fitness(data, dict(base, weight=w))
        scan.append({'weight': w, 'fitness': f, 'sharpe': sh, 'turnover': to, 'ic': c})
    arm['weight_scan'] = scan
    arm['fitness_monotone_decreasing_in_weight'] = all(
        scan[i]['fitness'] >= scan[i+1]['fitness'] - 1e-12 for i in range(len(scan)-1))

    # C: what the GA would actually converge on, per operator, at w -> 0
    arm['limit_at_zero_weight'] = {
        op: fitness(data, dict(base, operator=op, weight=1e-9))[0]
        for op in ('rank', 'decay', 'scale', 'delta')}

    # D: does the reward half carry ANY information on this data?
    rng = np.random.default_rng(7)
    ics = []
    for _ in range(200):
        p = {'operator': rng.choice(['rank', 'decay', 'scale', 'delta']),
             'window': int(rng.choice([5, 10, 20, 60])), 'weight': float(rng.uniform(-1, 1)),
             'decay_rate': float(rng.uniform(0, 0.5)), 'scale_factor': float(rng.uniform(0.5, 2.0))}
        _, _, _, c = fitness(data, p)
        if np.isfinite(c):
            ics.append(abs(c))
    arm['abs_ic_random_search'] = {'n': len(ics), 'mean': float(np.mean(ics)),
                                   'max': float(np.max(ics)), 'p95': float(np.percentile(ics, 95))}
    OUT['arms'][name] = arm

print(json.dumps(OUT, indent=2, default=float))
json.dump(OUT, open('data/brain_hunter_s21_fitness_layer.json', 'w'), indent=2, default=float)

# ---- Arm E: run the source's own GA loop (reduced iterations) and read the winner ----
def run_ga(data, iters=60, pop=100, seed=1):
    rng = np.random.default_rng(seed)
    def rand_p():
        return {'operator': str(rng.choice(['rank','decay','scale','delta'])),
                'window': int(rng.choice([5,10,20,60])), 'weight': float(rng.uniform(-1,1)),
                'decay_rate': float(rng.uniform(0,0.5)), 'scale_factor': float(rng.uniform(0.5,2.0))}
    P = [rand_p() for _ in range(pop)]
    best, bf = None, float('-inf')
    for _ in range(iters):
        for p in P:
            f = fitness(data, p)[0]
            if f > bf:      # the source's own comparison: NaN never wins
                bf, best = f, dict(p)
        new = []
        while len(new) < pop:
            if rng.random() < 0.8:
                a, b = P[rng.integers(pop)], P[rng.integers(pop)]
                c = {k: (a[k] if rng.random() < 0.5 else b[k]) for k in a}
            else:
                c = dict(P[rng.integers(pop)])
            if rng.random() < 0.1:
                k = str(rng.choice(list(c)));  c[k] = rand_p()[k]
            new.append(c)
        P = new
    return bf, best

for name, data in (('source_random', source_data()), ('desk_EURUSD_H1', desk_data())):
    bf, best = run_ga(data)
    OUT['arms'][name]['ga_winner'] = {'fitness': bf, 'params': best,
                                      'abs_weight': abs(best['weight'])}
    print(name, 'GA winner:', round(bf, 4), best)
json.dump(OUT, open('data/brain_hunter_s21_fitness_layer.json', 'w'), indent=2, default=float)
