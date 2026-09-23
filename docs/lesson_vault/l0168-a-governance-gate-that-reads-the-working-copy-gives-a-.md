---
id: L0168
cost: wasted
tags: ["governance"]
---

# L0168

A governance gate that reads the WORKING COPY gives a verdict about a state nobody committed. In a shared tree that does not merely BURY failures (the 08-05 dirty-tree lesson) -- it MANUFACTURES them against correctly-committed work. Diff HEAD vs working copy for the gate's input file BEFORE believing any gate verdict; heal from a pinned sha and re-run the gate ATOMICALLY in one command, because the clobber recurs on a cadence and also hits docs/desk_lessons.jsonl (a learn.py add reported success and was reverted before it could be committed). Do NOT flee to a fresh worktree: it lacks gitignored data/ and fakes a LARGER red.

## Evidence

2026-08-19: mine_gate said '1 claim conversion with NO backing artifact (anchor-absent R0637)' while git show HEAD: contained R0637+R0638. Working 635 rows vs HEAD 637, strict subset. Reverted again ~60s after heal (mtime 08:27:25); desk_lessons.jsonl likewise ended at L0167 after a reported-successful add. heal+gate in ONE command => BACKLOG-CLEAR, 15/15 disposed. 9th R0423 instance.

## Tags

#governance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0046-split-gates-by-what-forward-data-can-repair-structural]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
