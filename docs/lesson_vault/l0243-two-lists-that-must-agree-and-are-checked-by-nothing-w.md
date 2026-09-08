---
id: L0243
cost: 13h of unhealed research tasks, a silent publisher
tags: ["scheduling", "windows", "installer", "silent-failure"]
---

# L0243

Two lists that must agree and are checked by nothing will disagree. reboot_drill.ps1 required eleven scheduled tasks; Install-QuantWindows.ps1 built five, and the six it could not build were the ones whose absence is silent -- the dashboard publisher, the git publisher, the stall watchdog, the gauntlet, and the two moat organs. A table entry whose path is wrong is the same failure one level down: the loop prints [SKIP] and the installer still exits reporting success.

## Evidence

data/stall_watch.json last written 2026-09-06T23:57; scripts/build_zentech_state.py lives at the repository root, so a desk-root-only Join-Path could never have found it

## Tags

#scheduling #windows #installer #silent-failure

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0024-judge-a-source-by-whether-it-carries-measured-data-not]]
- [[l0025-run-the-positive-control-a-gauntlet-that-has-never-bee]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0045-an-empty-forward-slot-buys-no-safety-holm-is-priced-at]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
