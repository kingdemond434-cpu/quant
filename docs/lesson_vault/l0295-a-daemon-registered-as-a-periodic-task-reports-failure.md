---
id: L0295
cost: blind
tags: ["ops", "scheduler"]
---

# L0295

A DAEMON registered as a periodic task reports failure forever. The scheduler kills it at ExecutionTimeLimit and records 0x800710E0 or 0xC000013A every cycle, whatever the process was actually doing. Daemons get an at-startup trigger and ExecutionTimeLimit zero; periodic jobs get a bounded single pass.

## Evidence

2026-09-12: MT5-NewsDesk (news_desk.main() is `while True:`) and MT5-ResearchReports both ran on 4h limits and reported FAILING on every cycle. news_desk ran perfectly by hand. The registration was the defect, not the script.

## Tags

#ops #scheduler

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
