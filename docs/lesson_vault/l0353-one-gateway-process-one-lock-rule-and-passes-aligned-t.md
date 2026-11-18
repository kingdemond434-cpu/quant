---
id: L0353
cost: capital
tags: ["ops", "money-path"]
enforced_by: desks/mt5/tests/test_gateway_resident.py::test_the_loop_wrapper_is_the_research_one_never_the_desk_root_copy
---

# L0353

One gateway process, one lock rule, and passes aligned to the bar clock. Two loop wrappers with different lock rules (a pid lock that respects a living holder, a pid-less 'locked' file stolen after five minutes) ran passes concurrently whenever a pass took more than five minutes, and the same signal bar was sent twice by both; a resident that imported the wrong wrapper by sys.path order looked identical in every log. Before trusting a mark or a lock, check which file each running process actually imported and whether passes end within seconds of each other.

## Evidence

gateway.log 2026-09-16: pass ends 09:25:30 and 09:25:33, 09:28:49 and 09:28:52; entries per sleeve in pairs 8-18 min apart (01:22/01:30, 02:15/02:33, 03:22/03:28, 06:04/06:14, 09:04/09:14); gateway.lock content 'locked' while research/run_gateway_loop.py writes a pid; sys.path[0] was desks/mt5 so import run_gateway_loop resolved to the desk-root legacy copy; entry delays 938-2044 s after the bar open on 50 of 52 forex closes

## Enforced by

`desks/mt5/tests/test_gateway_resident.py::test_the_loop_wrapper_is_the_research_one_never_the_desk_root_copy`

## Tags

#ops #money-path

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0022-mark-based-books-are-blind-to-fill-damage-mark-positio]]
