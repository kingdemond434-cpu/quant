#!/usr/bin/env python3
with open('/home/quant/quant-platform/scripts/collect_x_signals.py', 'r') as f:
    content = f.read()
content = content.replace('"jacks_",', '"jacks_",\n    "l1vsun", "shmidt", "cvxv666",')
with open('/home/quant/quant-platform/scripts/collect_x_signals.py', 'w') as f:
    f.write(content)
print('Done')