---
id: L0129
cost: blind
tags: ["ops"]
---

# L0129

Never read a clean 'git status' as evidence YOUR output landed. In a shared checkout a sibling agent's commit sweeps up your uncommitted files under ITS subject line, so your work looks committed while you committed nothing -- and anything gitignored (data/*) is silently left behind. Verify authorship and reachability the only way that cannot lie: 'git log -S <your string> -- <path>' for who actually committed it, and 'git cat-file -s origin/<branch>:<path>' for whether a citation resolves from the REMOTE.

## Evidence

2026-08-12 KR miner: card kr_rail_state_transition_global_leg was written with [s33: wired -> data/ppomppu_kr_era_threads.jsonl]; git log -S showed it committed inside d917b3c4, subject 'JP frontier s3'. Both cited data/ paths were untracked under .gitignore:11 and existed on that box only. Fixed in 5b6ff73d.

## Tags

#ops

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
