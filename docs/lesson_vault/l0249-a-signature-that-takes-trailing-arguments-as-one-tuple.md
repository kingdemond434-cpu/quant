---
id: L0249
cost: 7 legs per hour, and an issue board that reported its own symptom
tags: ["python", "api-design", "hourly-cycle", "silent-failure"]
---

# L0249

A signature that takes trailing arguments as ONE tuple will be called the obvious way sooner or later. `_producer(name, script, args=())` was called as `_producer(name, script, '--mode', 'normal')` -- the natural spelling -- and the TypeError is raised while BUILDING the call, so no wrapper around the call's EXECUTION can catch it. The cycle died at pf_allocator and publish_state, issue_board and the four research reports never ran; the board then froze and reported those reports as STALLED. Accept both shapes and flatten.

## Evidence

TypeError: _producer() takes from 2 to 3 positional arguments but 4 were given, hourly_cycle.py:961 on the live box

## Tags

#python #api-design #hourly-cycle #silent-failure

## Related

- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0023-never-accept-done-for-a-human-step-verify-with-the-act]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0072-a-gate-that-must-execute-an-artifact-to-judge-it-is-no]]
- [[l0073-a-rail-s-reference-point-and-a-performance-number-may-]]
