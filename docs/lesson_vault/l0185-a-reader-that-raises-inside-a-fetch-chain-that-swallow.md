---
id: L0185
cost: blind
tags: ["data-integrity"]
enforced_by: tests/mt5/test_h1_cache_naive_index.py::test_every_bulk_downloader_stamps_utc
---

# L0185

A reader that RAISES inside a fetch chain that swallows exceptions reports a DATA fact when the truth is a FILE fact -- and nobody investigates a quiet market. Any guard that rejects an input must have its rejection surfaced by every caller, or the guard converts a repairable defect into an invisible one.

## Evidence

h1_source._normalise correctly refused 173 of 197 tz-naive H1 parquets; fetch_h1 caught it in `except Exception: continue` and returned None, so callers logged "no H1 source returned bars". The universal-ground mandate ran on 24 symbols for as long as those files existed. Cause was one keyword: five bulk downloaders called pd.to_datetime(rates["time"], unit="s") without utc=True on EPOCH SECONDS, keeping the instants and dropping the label. Fixed 48847e5e; reachability 24/197 -> 197/197.

## Enforced by

`tests/mt5/test_h1_cache_naive_index.py::test_every_bulk_downloader_stamps_utc`

## Tags

#data-integrity

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0024-judge-a-source-by-whether-it-carries-measured-data-not]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
