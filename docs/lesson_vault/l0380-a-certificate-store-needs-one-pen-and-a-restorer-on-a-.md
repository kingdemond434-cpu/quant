---
id: L0380
cost: capital
tags: ["certificates", "governance"]
enforced_by: desks/mt5/tests/test_certificate_truth.py::test_a_second_writer_that_empties_the_authority_file_is_repaired_on_the_next_pass
---

# L0380

A certificate store needs ONE pen and a restorer on a clock, not one pen and an alarm. When a forked writer (desks/mt5/side_channels/ug_remote.py) rewrote reports/UNIVERSAL_SURVIVORS.json from an empty dict with no gate_policy key, the canon went 56 -> 0 and stayed there for six days while 13 sleeves traded and 855 forward clocks ran: losing the ATTESTATION was the worse half, because every reader then fell through to the seal, and the sealed gauntlet's own restore loop reads retired_certificates out of the file the wipe had just emptied, so it restored nothing for ever. Graft a guard onto every copy of a writer you fix (retain + attest + refuse empty + refuse shrink), and give the audit organ the power to RESTORE on its own hourly clock through the lane's own rules -- seal, then git, then re-ask each retirement its own question -- because a report that names an empty canon is not a remedy for one.

## Evidence

reports/UNIVERSAL_SURVIVORS.json n=56 at 2026-09-17 08:44 and n=0 at 09:52; 183 bytes with no gate_policy re-written hourly by leg auto_ug_remote (compute_ledger 2026-09-23T08:39:08-08:39:19, swept_at 08:39:16); seal retired 60 ten-gate passes on 2026-09-21T10:08:50 under a predicate the writer had already corrected; certificate_truth repair restored 28 and left 32 banned, canon 0 -> 28, divergences 14 -> 6, fatal 1 -> 0

## Enforced by

`desks/mt5/tests/test_certificate_truth.py::test_a_second_writer_that_empties_the_authority_file_is_repaired_on_the_next_pass`

## Tags

#certificates #governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
