---
id: L0339
cost: blind
tags: ["research", "data"]
enforced_by: tests/test_check_row_conversion_contract.py::test_backlog_is_not_yield_but_non_evidence_is_an_honest_refusal
---

# L0339

EVERY MINED ROW MUST REACH A TERMINAL DISPOSITION: a cell, or a refusal named in the desk's own vocabulary. 'Needs extraction' is a BACKLOG, never an answer. Do NOT force a cell out of every row -- manufacturing one from a leaderboard position or an empty page is worse than leaving it -- but never let one label cover a bug, a missing converter and a broken crawler at once. Before fixing, split the backlog by (seat, kind) and look at an actual row: the remedy is usually in the row, not in an LLM call.

## Evidence

2026-09-15: 63,126 rows labelled NEEDS_SYMBOL_EXTRACTION hid three unrelated faults. resolve_symbols upper-cased the token so every mixed-case Fusion symbol (Accenture, Adobe, AlibabaGroup) resolved to nothing -- 10,926 broker_swaps rows queued for an LLM call to recover an instrument the row already named. event_like matched the seat 'central_bank' while the seat on disk is 'central_banks' -- one character, 16,462 rows carrying an explicit currency field. And 33,530 rows had no BODY text at all -- only a title or a bare URL -- which is a COLLECTOR defect the label hid inside a research backlog. The first version of that check looked at row['text'] alone and ran BEFORE the prose path, which labelled the working deepseek seat an empty capture; a title is a label, not a body, and the test must exclude it and run last. Fixing all three took candidates from 418,676 to 860,818 (+105.6%) and terminal share from 58.9% to 69.8%.

## Enforced by

`tests/test_check_row_conversion_contract.py::test_backlog_is_not_yield_but_non_evidence_is_an_honest_refusal`

## Tags

#research #data

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
