#!/usr/bin/env python3
import os
os.chdir("/home/quant/quant-platform")
from libs.autodiscovery.generators import GENERATORS, mechanism_class_counts, census_class
for s in GENERATORS:
    if s.subtype in ('funding_taker_interaction', 'basis_funding_interaction', 'basis_taker_interaction'):
        print(f'{s.subtype}: family={s.family.value}, mech={s.mechanism.value}, census={census_class(s)}, variants={len(s.param_variants)}')
print('Mechanism counts:', mechanism_class_counts())