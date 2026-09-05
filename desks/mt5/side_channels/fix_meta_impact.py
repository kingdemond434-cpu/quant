# Read the current file
with open('/home/quant/quant-platform/desks/mt5/research/meta_desk.py', 'r') as f:
    content = f.read()

# Fix the impact network significance calculation
old_se = '''                beta = (x * y).sum() / (x * x).sum()
                res = y - beta * x
                se = res.std(ddof=1) / np.sqrt(len(x)) if len(x) > 2 else 0'''
new_se = '''                beta = (x * y).sum() / (x * x).sum()
                res = y - beta * x
                # Correct standard error for regression coefficient: se = sigma_res / (sigma_x * sqrt(n))
                x_std = x.std(ddof=1)
                if x_std > 0:
                    se = res.std(ddof=1) / (x_std * np.sqrt(len(x))) if len(x) > 2 else 0
                else:
                    se = 0'''
content = content.replace(old_se, new_se)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/research/meta_desk.py', 'w') as f:
    f.write(content)

print("meta_desk.py impact network fixed successfully")