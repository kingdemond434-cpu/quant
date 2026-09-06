---
id: L0062
cost: hygiene
tags: ["git"]
---

# L0062

NEVER 'git stash pop' in this shared working tree. 'git stash push <path>' on a file with NO changes creates NO stash and still exits 0, so the next 'git stash pop' silently pops a SIBLING SESSION'S stash instead of yours. To test a file at HEAD, use 'git show HEAD:<path>' or 'git stash push' with an explicit --message you then pop BY NAME.

## Evidence

2026-08-01: stashing an unmodified docs/desk_lessons.jsonl created nothing; the follow-up pop applied stash@{0} 'brain-inflight' from a concurrent session and left UU conflicts in holdings_record.json and recommendation_ledger.json -- two LEDGERS. Recovered only because the conflicted pop KEEPS the stash entry.

## Tags

#git

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0031-the-backtest-gauntlet-is-a-screen-with-zero-promotion-]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
