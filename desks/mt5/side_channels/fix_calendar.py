#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/ops/crontab.manifest")
src = p.read_text()

fixes = {
    'on="*:00"': 'on="*:0"',
    'on="*:03"': 'on="*:3"',
    'on="*:13"': 'on="*:13"',
    'on="*:23"': 'on="*:23"',
    'on="*:33"': 'on="*:33"',
}
for old, new in fixes.items():
    src = src.replace(old, new)

# Verify actual OnCalendar values from unit files match
import re
from pathlib import Path as P
for i in range(10):
    t = P(f"/home/quant/quant-platform/ops/quant-autodiscovery-slice{i}.timer").read_text()
    m = re.search(r"OnCalendar=(\S+)", t)
    print(f"slice{i}: OnCalendar={m.group(1)}")

p.write_text(src)
print("Manifest updated")