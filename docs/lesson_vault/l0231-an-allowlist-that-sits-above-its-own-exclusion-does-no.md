---
id: L0231
cost: blind
tags: ["delivery", "gitignore"]
---

# L0231

An allowlist that sits ABOVE its own exclusion does nothing: git applies the LAST matching rule. And a publisher faithfully publishing a file git refuses to accept is indistinguishable from a dead producer -- the symptom points at the machine that is working.

## Evidence

.gitignore allowlisted shadow_health.json at line 142 and re-excluded it at line 244 with **/shadow_health.json. After PR #47 untracked the runtime state the file was untracked AND ignored, so sync_shadow_to_git.ps1 staged it every 15 minutes, git dropped it silently, and the script honestly logged 'no change since last sync' ~1000 times over 11 days. The dashboard read 'box has not reported for 266.4h' -- matching the committed copy's updated_at to the minute -- while the file on disk was 26 minutes old with 19 sleeves against the committed 16. Its siblings survived only because their negations sit below line 244.

## Tags

#delivery #gitignore

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0002-paginate-every-venue-history-endpoint-truncation-is-th]]
- [[l0004-a-committed-fix-is-inert-until-the-process-actually-re]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0053-state-the-units-in-the-name-of-every-threshold-constan]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
