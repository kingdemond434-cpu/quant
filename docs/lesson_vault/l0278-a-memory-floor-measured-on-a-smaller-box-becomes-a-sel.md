---
id: L0278
cost: slow
tags: ["throughput"]
enforced_by: desks/mt5/tests/test_gauntlet_budgets_fit_the_box.py::test_the_declared_memory_floor_is_sized_for_the_80gb_box
---

# L0278

A memory floor measured on a smaller box becomes a SELF-TIGHTENING throttle on a bigger one: budget = max(declared, p75 of observed peaks) can never rise past a cap that defers at the declaration. Re-measure every floor when the hardware changes.

## Evidence

2026-09-08: 1200MB declared on the 8GB box, 42 cells judged an hour against a docket of 23,465 on the 80GB box -- 558 passes, 23 days, to judge work already delivered.

## Enforced by

`desks/mt5/tests/test_gauntlet_budgets_fit_the_box.py::test_the_declared_memory_floor_is_sized_for_the_80gb_box`

## Tags

#throughput

## Related

- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0074-an-alarm-must-name-the-cause-its-data-supports-never-t]]
- [[l0081-persist-accumulated-state-in-a-finally-never-only-at-t]]
- [[l0082-a-positive-control-is-not-enough-add-a-no-treatment-co]]
- [[l0097-when-a-check-grades-a-timestamp-read-what-writes-it-a-]]
