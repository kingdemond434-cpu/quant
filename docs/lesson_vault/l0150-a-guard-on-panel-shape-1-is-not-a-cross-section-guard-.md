---
id: L0150
cost: blind
tags: ["data-quality"]
enforced_by: tests/research/test_cross_section_floor.py::test_fence_flags_the_width_guard_as_a_near_miss
---

# L0150

A guard on panel.shape[1] is NOT a cross-section guard. It counts declared columns, which cannot fall when a date's cross-section empties -- floor the FINITE VALUES PER ROW via libs.research.cross_section_floor.measure_cross_section.

## Evidence

data/cross_section_floor.json first run: 49 per-date collapse sites, 13 guarded by shape[1] only. Live OI/LS panel declares 373 columns; thinnest date carries 99.

## Enforced by

`tests/research/test_cross_section_floor.py::test_fence_flags_the_width_guard_as_a_near_miss`

## Tags

#data-quality

## Related

- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0020-know-an-estimator-s-floor-before-reading-it-as-a-findi]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
- [[l0067-before-replacing-a-fabricated-default-with-unmeasured-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0074-an-alarm-must-name-the-cause-its-data-supports-never-t]]
