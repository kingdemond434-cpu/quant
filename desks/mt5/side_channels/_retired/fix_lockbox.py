import re

# Read the current file
with open('/home/quant/quant-platform/desks/mt5/research/qquant_gates.py', 'r') as f:
    content = f.read()

# Fix the lockbox gate to use a genuine untouched holdout
# Find the lockbox section and replace it

old_lockbox = '''    stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}
    stages["lockbox"] = {"passed": bool(wf_oos >= 0.0),
                         "lockbox_sharpe": round(wf_oos, 4)}
    ev = float(arr.mean())'''

new_lockbox = '''    stages["stress_costs"] = {"passed": bool(exp3 > 0.0), "exp_x3": round(exp3, 4)}
    # GENUINE LOCKBOX: untouched holdout (last 20% of data, min 60 bars)
    # This is INDEPENDENT from walk_forward which uses purged/embargoed splits on the TRAIN portion
    lockbox_frac = 0.20
    lockbox_min = 60
    n_total = len(arr)
    lockbox_size = max(lockbox_min, int(n_total * lockbox_frac))
    train_size = n_total - lockbox_size
    if train_size >= 100 and lockbox_size >= lockbox_min:
        train_arr = arr[:train_size]
        lockbox_arr = arr[train_size:]
        lockbox_sharpe = float(sharpe_ratio(lockbox_arr))
        stages["lockbox"] = {"passed": bool(lockbox_sharpe > 0.0),
                             "lockbox_sharpe": round(lockbox_sharpe, 4),
                             "lockbox_n": lockbox_size,
                             "train_n": train_size,
                             "note": "genuine untouched holdout (last 20% of data)"}
    else:
        # Not enough data for genuine lockbox - fail closed
        stages["lockbox"] = {"passed": False,
                             "lockbox_sharpe": 0.0,
                             "lockbox_n": 0,
                             "train_n": n_total,
                             "note": "insufficient data for genuine lockbox holdout"}
    ev = float(arr.mean())'''

content = content.replace(old_lockbox, new_lockbox)

# Also update the docstring comment for lockbox
old_doc = '  9 lockbox            - wf OOS Sharpe >= 0 (holdout proxy)'
new_doc = '  9 lockbox            - genuine untouched holdout (last 20% of data, Sharpe > 0)'
content = content.replace(old_doc, new_doc)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/research/qquant_gates.py', 'w') as f:
    f.write(content)

print("qquant_gates.py lockbox fixed successfully")