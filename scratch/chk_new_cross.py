#!/usr/bin/env python3
import os
os.chdir("/home/quant/quant-platform")
from libs.autodiscovery.generators import GENERATORS, mechanism_class_counts, census_class
for s in GENERATORS:
    if s.subtype in ('oi_funding_interaction', 'perpdex_hl_spread_arb', 'basis_liquidation_interaction', 'taker_liquidation_interaction'):
        print(f'{s.subtype}: family={s.family.value}, mech={s.mechanism.value}, census={census_class(s)}, variants={len(s.param_variants)}')
print('Mechanism counts:', mechanism_class_counts())