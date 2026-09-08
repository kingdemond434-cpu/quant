---
id: L0260
cost: the publisher's conflict path died when it worked
tags: ["powershell", "sync", "publisher", "error-handling"]
---

# L0260

The most dangerous place for the Stop+2>&1 trap is a call whose stderr IS the result. sync_shadow_to_git's untracked-file probe deliberately makes `git merge` fail so it can read the file list out of the failure text -- so the pass terminated at exactly the moment the probe succeeded, and the parking logic below it never ran. A guard applied to one call site in a file is not applied to the file.

## Evidence

sync_shadow_to_git.ps1:130, unguarded, while Git-In-Repo at line 62 carried the fix and its explanation

## Tags

#powershell #sync #publisher #error-handling

## Related

- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0060-rank-a-mined-comment-tree-by-mechanism-keyword-density]]
- [[l0066-on-a-box-where-several-agent-sessions-share-one-workin]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
- [[l0080-libs-ops-input-provenance-inputs-read-json-records-a-s]]
