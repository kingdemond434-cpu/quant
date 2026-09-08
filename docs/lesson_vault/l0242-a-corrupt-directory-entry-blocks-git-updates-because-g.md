---
id: L0242
cost: the whole adoption, every hour
tags: ["git", "ntfs", "adoption", "sync", "release"]
---

# L0242

A corrupt directory entry blocks git updates because git updates a file by UNLINKING it, not by rewriting it. Opening the existing file with truncate rewrites the contents and never consults the damaged entry, so a tree can be landed in full while one path is unlinkable. What must never be done first is `merge -s ours`: it keeps the current tree and records the target as a parent, so a repository that never adopted the work reports itself up to date while running the old code.

## Evidence

unable to unlink old 'desks/mt5/side_channels/run_external_backtest.py': Invalid argument -- from git merge, git checkout <ref> -- ., and git pull alike; no process held the file and Move-Item failed the same way

## Tags

#git #ntfs #adoption #sync #release

## Related

- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
- [[l0062-never-git-stash-pop-in-this-shared-working-tree-git-st]]
