#!/usr/bin/env python3
with open('/home/quant/quant-platform/scripts/collect_x_signals.py', 'r') as f:
    content = f.read()
content = content.replace('"l1vsun", "shmidt", "cvxv666",', '"l1vsun", "shmidtqq", "antpalkin",')
with open('/home/quant/quant-platform/scripts/collect_x_signals.py', 'w') as f:
    f.write(content)
print('Done')