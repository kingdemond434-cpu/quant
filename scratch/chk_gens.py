#!/usr/bin/env python3
import os

os.chdir("/home/quant/quant-platform")
from libs.autodiscovery.generators import GENERATORS, census_class, mechanism_class_counts

for s in GENERATORS:
    if s.subtype in ('derivative_carry_basis', 'taker_flow'):
        print(f'{s.subtype}: family={s.family.value}, mech={s.mechanism.value}, census={census_class(s)}')
print('Mechanism counts:', mechanism_class_counts())
