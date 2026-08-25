#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/crypto_adapter.py")
src = p.read_text()

old = "import numpy as np\n\nfrom libs.autodiscovery.memory import CandidateStore"
new = "import numpy as np\nimport pandas as pd\n\nfrom libs.autodiscovery.memory import CandidateStore"
if old not in src:
    print("Import anchor not found")
    raise SystemExit(2)
src = src.replace(old, new)
p.write_text(src)
print("Added pandas import")