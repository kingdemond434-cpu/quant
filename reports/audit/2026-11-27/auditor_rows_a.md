# Auditor rows, batch a (2026-11-27 22:55Z): five governed paths at f502d81a234a560169a2a2eaef47d102b78aaac9

Each blob below is one I read myself, at a sha I reviewed in full.

| path | blob | where I read it |
|---|---|---|
| .github/scripts/audit_gate.py | 6e1e53cdfd1e5331ecadcf79141e5f5d741085d4 | boot r21 0ffd16b980 (the need=(RISK_JOB,) diff), unchanged through r24 4d61929c7 |
| desks/mt5/scripts/Adopt-Release.ps1 | 60d8eadef029b0d3384da184aa5c7bc077dab68a | boot r24 r5 0ac56067c (Get-PinnedCode), unchanged to r7 4d61929c7 (CLEAR) |
| ops/box_git/pinned_sitecustomize.py | 33ca6da188af5da651150175e3c8bf924c9115ab | boot r24 r5/r6, the fence plus pickle.find_class (r7 4d61929c7 CLEAR) |
| scripts/moneypath_precommit_guard.py | 9db2cbba86e1bda221790ffdbce758e17d92af28 | boot r24 r5, the CODE/ROOT split (r7 CLEAR) |
| desks/mt5/scripts/Adopt-And-Seal.ps1 | 88858e898d788495a6e74d82f00116913e7faa5e | the r24 line (r4–r7), 18d8b30a9e, and the full 8925da4048→9663b93706 merge delta I read on 11-27: EnsureManifestTasks and the retired-task step skip under -Pinned; canary, drift and arm-canary go through Invoke-AdoptGuard |

The remaining 45 of FOR_AUDIT_50 are open. Each one stays uncovered, so pre holds it, until a later batch rows it or HOLDs it.
