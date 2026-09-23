---
id: L0118
cost: blind
tags: ["fences", "denominator"]
enforced_by: tests/ops/test_dig_depth_markers.py::test_a_stub_newest_log_does_not_exempt_the_substantial_dig_behind_it
---

# L0118

A fence that picks the NEWEST item and then skips it as unjudgeable exempts everything behind it. Select the newest JUDGEABLE item instead, or one stub silently empties the scan and the pass is over nothing.

## Evidence

max_audit.check_dig_depth took logs[0] then skipped <1500b; a 171-byte 'DEFERRED -- brain mutex held' notice exempted the whole frontier family while 4 substantial digs went unread (2026-08-12)

## Enforced by

`tests/ops/test_dig_depth_markers.py::test_a_stub_newest_log_does_not_exempt_the_substantial_dig_behind_it`

## Tags

#fences #denominator

## Related

- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0070-a-detector-that-has-never-fired-is-not-evidence-of-hea]]
- [[l0078-a-fence-with-an-ordered-status-ladder-can-have-a-fabri]]
- [[l0079-grep-for-a-governance-flag-s-consumers-not-its-writers]]
- [[l0086-adding-a-doc-to-a-scanned-set-is-not-the-same-as-count]]
- [[l0088-a-guard-that-fails-closed-on-a-missing-data-file-must-]]
