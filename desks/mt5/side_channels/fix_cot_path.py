#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/crypto_adapter.py")
src = p.read_text()
old = '    base = Path(_LAKE_ROOT).parent / "data" / "cot"'
new = '    base = Path(_LAKE_ROOT).parent / "cot"'
if old not in src:
    print("Pattern not found")
    raise SystemExit(2)
src = src.replace(old, new)
p.write_text(src)
print("Fixed path -> data/cot")