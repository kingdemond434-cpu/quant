---
id: L0115
cost: blind
tags: ["testing"]
---

# L0115

Check whether a module's store path is ABSOLUTE before trusting monkeypatch.chdir to isolate a test. An absolute ROOT/data path is untouched by chdir, so a fixture that drives a failure handler writes phantom evidence into the LIVE tally -- the test then manufactures the very failures it asserts about.

## Evidence

build_audit_coverage.MANIFEST = ROOT / 'data/audit_coverage.json'; the R0343 total-failure fixture calls record_blank once per dead seat, which would have injected 4 blanks into the seat_blanks tally the chronic-seat defect reads as evidence

## Tags

#testing

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0058-check-the-as-of-date-of-a-ratio-s-denominator-separate]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0061-before-grading-a-cross-venue-join-defect-check-whether]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0063-run-a-leak-detector-on-data-you-know-is-clean-before-y]]
