#!/usr/bin/env python3
import os
os.chdir("/home/quant/quant-platform")
from libs.autodiscovery.generators import GENERATORS
for s in GENERATORS:
    if s.subtype in ('derivative_carry_basis', 'taker_flow', 'funding_stress_reversal'):
        print(f'{s.subtype}: {len(s.param_variants)} variants')
print('Total generators:', len(GENERATORS))