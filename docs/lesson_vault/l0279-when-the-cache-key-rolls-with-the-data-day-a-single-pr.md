---
id: L0279
cost: slow
tags: ["throughput"]
enforced_by: desks/mt5/tests/test_gauntlet_parallel_prewarm.py::test_the_deadline_is_the_loop_s_own_clock_not_a_second_budget
---

# L0279

When the cache key rolls with the data day, a single-process build cannot converge a large docket at all -- it is structurally unable, not slow. Parallelise the fresh path into the cache and let the existing cached branch consume it; share ONE budget clock.

## Evidence

~22s a cell x 23,465 cells = 143 CPU-hours against a 24-hour cache key; 3,000 cells a day single-process.

## Enforced by

`desks/mt5/tests/test_gauntlet_parallel_prewarm.py::test_the_deadline_is_the_loop_s_own_clock_not_a_second_budget`

## Tags

#throughput

## Related

- [[l0068-to-prove-a-failing-test-is-environment-rather-than-you]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0101-assert-the-discriminating-property-in-a-fixture-contro]]
- [[l0126-when-a-new-guard-trips-an-existing-test-check-the-fixt]]
- [[l0129-never-read-a-clean-git-status-as-evidence-your-output-]]
- [[l0133-when-a-fence-reports-an-organ-dead-that-you-can-see-pr]]
- [[l0220-before-trusting-a-lag-x-hour-offset-scan-s-winning-cel]]
- [[l0242-a-corrupt-directory-entry-blocks-git-updates-because-g]]
