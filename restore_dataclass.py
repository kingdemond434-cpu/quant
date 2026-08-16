#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/generators.py")
src = p.read_text()

old = "\n\nclass GeneratorSpec:"
new = "\n\n@dataclass(frozen=True)\nclass GeneratorSpec:"
if old not in src:
    print("Class anchor not found")
    raise SystemExit(2)
src = src.replace(old, new, 1)
p.write_text(src)
print("Restored @dataclass on GeneratorSpec")
