#!/usr/bin/env python3
import os

os.chdir("/home/quant/quant-platform")
from pathlib import Path

from migrations import MIGRATIONS

from libs.autodiscovery.crypto_adapter import build_lab, load_universe
from libs.data.timeframe import Timeframe
from libs.store.connection import Database
from libs.store.migrations import run_migrations

symbols, provider = load_universe(Timeframe.D1, limit=5, offset=0)
print(f"Test symbols: {symbols}")

db = Database(Path("data/test_new_gens.sqlite"))
run_migrations(db, MIGRATIONS)
lab = build_lab(db, provider, timeframe=Timeframe.D1, families=None)
result = lab.cycle(symbols)
print(f"tested={result.tested} survivors={result.survivors} skipped_dup={result.skipped_duplicate}")

# Check if new generators were in the cycle
from libs.autodiscovery.generators import GENERATORS

new_specs = [s for s in GENERATORS if s.subtype in ('derivative_carry_basis', 'taker_flow')]
print("New generator specs:")
for s in new_specs:
    print(f"  {s.subtype}: {len(s.param_variants)} variants, {s.family.value}/{s.mechanism.value}")

db.close()
import os

os.remove("data/test_new_gens.sqlite")
