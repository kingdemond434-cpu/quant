#!/usr/bin/env python3
from libs.autodiscovery.generators import GENERATORS, census_class, mechanism_class_counts

spec = next(s for s in GENERATORS if s.subtype == "cot_positioning_reversal")
print("spec ok:", spec.subtype, spec.family, spec.mechanism, spec.param_variants)
print("census class:", census_class(spec))
print("counts:", mechanism_class_counts())
