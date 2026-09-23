# Read the current file
with open('/home/quant/quant-platform/desks/mt5/research/book_sizing.py', 'r') as f:
    content = f.read()

# Fix book_sizing.py to use canonical Costs.from_symbol()
old_cost = '''    cost = Costs(
        spread_per_lot=0.48 if sym == "XAUUSD" else max(
            m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05),
        commission_per_lot=3.50, contract_oz=m["contract_size"])'''
new_cost = '''    cost = Costs.from_symbol(m, mult=2.0)  # canonical costs (round-trip spread * 2)'''
content = content.replace(old_cost, new_cost)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/research/book_sizing.py', 'w') as f:
    f.write(content)

print("book_sizing.py canonical costs fixed successfully")