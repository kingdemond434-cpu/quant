---
id: L0259
cost: the adoption aborted before it touched one file
tags: ["powershell", "windows", "native-commands", "silent-failure"]
---

# L0259

PowerShell turns every stderr LINE from a native command into an ErrorRecord, and under $ErrorActionPreference='Stop' the first one is TERMINATING. So `& git ... 2>&1` in a Stop script dies on output that is not an error: `git fetch` writing 'From https://github.com/<owner>/<repo>' is a SUCCESSFUL fetch describing itself. Exit code is the truth for a native command -- relax the preference around the call, restore it after, and check $LASTEXITCODE.

## Evidence

Adopt-Release.ps1:196 NativeCommandError on the fetch, on the box's first real run; sync_shadow_to_git.ps1 already carried the correct guard with a comment 60 lines above a second call that lacked it

## Tags

#powershell #windows #native-commands #silent-failure

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
- [[l0064-when-two-organs-read-the-same-source-share-the-filter-]]
- [[l0069-a-sibling-can-claim-your-l1-x-number-mid-build-check-t]]
- [[l0071-a-negative-exit-code-is-a-verdict-about-the-box-never-]]
