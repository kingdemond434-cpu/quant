---
id: L0101
cost: blind
tags: ["testing"]
---

# L0101

Assert the DISCRIMINATING property in a fixture control, never a proxy for it. 'The table split into >1 chunk' is not 'the split landed where the bug lives' -- make the fixture report the discriminating count and assert on that.

## Evidence

tests/data/test_xls_reader.py: test_fixture_can_express_sst_split asserted len(encode_sst(...)) > 1 and passed at cap 97, where the SST spans 2 records with ZERO mid-string cuts -- so the repeated flag byte the reader must consume never appeared and the entire bug-(b) path went untested while its own control read green. Measured: cap 24 -> 8 mid-string splits, 32 -> 3, 40 -> 4, 64 -> 0, 97 -> 0 (pre-fix strings). Same file: _STRINGS were all latin-1 so the per-segment width flip was never exercised, and test_wide_string_round_trips passed a 24-byte cap to a 17-byte table -> one chunk, no CONTINUE at all.

## Tags

#testing

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0021-hysteresis-must-key-on-the-economic-condition-never-on]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
