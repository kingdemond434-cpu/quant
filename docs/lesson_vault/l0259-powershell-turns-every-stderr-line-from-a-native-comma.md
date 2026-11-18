---
id: L0259
cost: slow
tags: ["powershell", "windows", "native-commands", "silent-failure"]
---

# L0259

PowerShell turns every stderr LINE from a native command into an ErrorRecord, and under $ErrorActionPreference='Stop' the first one is TERMINATING. So `& git ... 2>&1` in a Stop script dies on output that is not an error: `git fetch` writing 'From https://github.com/<owner>/<repo>' is a SUCCESSFUL fetch describing itself. Exit code is the truth for a native command -- relax the preference around the call, restore it after, and check $LASTEXITCODE.

## Evidence

Adopt-Release.ps1:196 NativeCommandError on the fetch, on the box's first real run; sync_shadow_to_git.ps1 already carried the correct guard with a comment 60 lines above a second call that lacked it [cost as recorded: the adoption aborted before it touched one file]

## Tags

#powershell #windows #native-commands #silent-failure

## Related

- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0008-when-a-gate-looks-too-harsh-hunt-for-a-double-correcti]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0028-price-a-filter-in-both-errors-before-shipping-it-a-luc]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0047-before-penalising-a-quantity-check-it-is-not-already-i]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
