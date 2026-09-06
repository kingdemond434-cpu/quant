---
id: L0099
cost: blind
tags: ["worktree"]
---

# L0099

An absolute path in an edit targets the tree it NAMES, not the tree your shell is in. When working in a git worktree, verify where a file landed before trusting any gate that reads it -- a gate run in the worktree reports green about a registration that went to the main tree, and it is right to: it never saw the file.

## Evidence

2026-08-12 R0317: _GOVERNED/_MAP edits landed in /home/quant/quant-platform/scripts/ while cwd was .claude/worktrees/owed-b3-xls. check_build_standard printed '68/68 organs OK' having never seen read_xls.py; after relocating the patch it read 69 organs and audited it for real. It also left the SHARED tree dirty for every sibling session.

## Tags

#worktree

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0005-when-a-claim-is-checkable-in-one-command-checking-is-c]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
