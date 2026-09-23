# Read the current file
with open('/home/quant/quant-platform/desks/mt5/research/allocation.py', 'r') as f:
    content = f.read()

# Fix the equal-weight comparison bug
old_eq = '''    port_eq = daily.fillna(0.0).sum(axis=1)'''
new_eq = '''    port_eq = daily.fillna(0.0).mean(axis=1)  # equal weight = mean, not sum (N× exposure)'''
content = content.replace(old_eq, new_eq)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/research/allocation.py', 'w') as f:
    f.write(content)

print("allocation.py equal-weight bug fixed successfully")