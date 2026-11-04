# Autonomy tracker: every human dependency, its remediation and its observed outcome

Owner: the Autonomy thread. This tracker follows zuck's 2026-11-03 23:41Z mandate. zuck's
23:41:31Z amendment dropped the feature freeze, so research continues. A copy is at
`/mnt/project-files/autonomy/HUMAN_DEPENDENCIES.md`.

**Status: NOT COMPLETE.** Every merge to LIVE since 2026-10-30 needed zuck, and no release has
been produced since 2026-10-30.

**Rules.** An outcome is written only from an observed artifact (a commit, run id, log line or
file), with its time. Code written, a PR existing, or a test passing locally is never an
outcome. Expected results are not recorded.

**Categories** (zuck, Phase 7):
- **PROVEN**: eliminated, and the autonomous behaviour has been observed in production.
- **AUTOMATABLE**: a legitimate solution exists, but it is not yet implemented or proven.
- **EXTERNAL**: needs a provider, account, service or permission outside the system.
- **NON-DELEGABLE**: an exceptional owner decision that keeps the security authority
  independent.

**Owners** are threads: Autonomy (AU), Desk health (DH, the box), Governance (GV, the release
authority), Auditor (AD), YouTube miner (YT).

## Observations (newest first, UTC, 2026-11-03/04)

| Time | Observation | Source |
|---|---|---|
| 11-04 00:15 | #666 independent-review (7B) FAIL at aca6be9e6: unbounded --budget-s. Fixed at 7b038bfcf: the flag accepts only (0,300] and run() clamps. Merged #665 head; ab7b70d30 gates green. AD re-audit requested. #678 HOLD on 306ec2cce is superseded by 49baf7be2, where research is never lowered. #659's cancelled ci and release-gates runs were re-run. | runs API, AD |
| 11-04 00:05 | DH: adoption is deadlocked at release 298269eb15. The box guard (10-29) has no box_published exemption and reads clears from the frozen target. See R2b. | DH box read |
| 11-04 00:10 | ADOPT_CLEARS.jsonl on LIVE dd5091910 has a CLEAR row (row 21, 625fdd3a1) for the exact blobs of all three offsite-backup paths. sleeves.json (984bea98) and BARS_STATE.json (e6d64e26) have no CLEAR row for their current blobs, so they pass only through the box-published exemption, which needs the box's sync log. The box's current ADOPT_GUARD.json is UNMEASURED (requested from DH). | git show LIVE:ADOPT_CLEARS.jsonl |
| 11-04 00:05 | #678 (resource governor, AUTO) is open as a draft at d89cba424, stacked on #665's bb08306e2. ops/gates.sh is all green there. | gates.sh |
| 11-04 00:00 | GV chose option (a): #650 merged #665's bb08306e2 and was pushed at d93e5dea3. The bootstrap's step 2 re-pins from LIVE after #650 merges, which also repairs the #658 pin break (R15). | GV note |
| 23:58 | Root digest on LIVE differs from ROOT_PIN (d7fe4a7de) because #658 changed ops/box/workflow_gate.ps1, a ROOT file. While they differ, the authority does not act, so no PR can auto-merge. | git diff d7fe4a7de..LIVE over root files |
| 23:45 | LIVE 8ff5596a9 cannot be pushed by any session that merges it. Causes: ruff (from #655) and two law fences (component-registry clock ratchet 5>2; birth obligations) on three video-miner scripts. | GV |
| 23:37 | AD CLEAR on #666 at aca6be9e6. | AD row |
| 23:31 | Quant-WorkflowGate has ExecutionTimeLimit PT30M. Box CPU is at 100%. Every sweep since 22:46:10Z ended 0x41306 with no log line, because the installed wrapper logs only after audit_gate returns. About 50 new pythons since 22:50Z belong to a SYSTEM tree started 16:41Z. Five pythons have been running for days (pids 9356, 2192, 21924, 4712, 24096). SYSTEM command lines are hidden from the Administrator token. | DH |
| 23:31 | Adoption 22:50:26Z (pid 23960) is idle on a git child (py 26404 > python 28768 > git 34884 > git 34196) and holds Global\MT5-GitWriter-v2. intel-ship-adopt was blocked for its full 9 min (23:11:30Z). Last adopt log line, 22:52:46Z: "tip 6727fc33e5ff carries 191 unreleased code paths; adopting newest green release 298269eb1505". | DH |
| 23:29 | C:\opt\quant HEAD is 6fe812a00, a box-local commit not on origin; gate-repo is at 442dfd6a8. ROOT_PIN is 8cbbb93f…f278 at d7fe4a7de (pinned 22:30:46Z). Machine env QUANT_AUTHORITY_{ATTESTATIONS,PUBKEY,ROOT_PIN} is set. The authority's log, attestations and task are access-denied to agent sessions. pin_root.py was refused by the session classifier, so pin vs LIVE is UNMEASURED. | DH |
| 23:29 | `trusted-eval` has never run. `GET actions/workflows/trusted-eval.yml` returns 404. pull_request_target loads workflows from default branch `master`, which is at f3bb5fc03 (17:45Z) and predates #637. | GV |
| 23:28 | LIVE `ci` push runs on 442dfd6a8, 563d2e816 and e0b6b96e0 were still in progress about 1 h after creation. Every completed LIVE run on 11-03 failed or was cancelled. | ci.yml runs API |
| 23:26 | 21 open PR heads still contained mt5_ratchet.py, which is absent on LIVE 8ff5596a9. 20 were updated by update-branch (all except #645), and the re-read heads no longer contain it. AD re-keyed them at 23:29Z. | contents API |
| 23:25 | Merge provenance since 10-25: 68 merges by kingdemond434-cpu, 1 by github-actions (#483, 10-30 12:58Z), 0 by the box registry/authority sweep. Newest tag: `release/20261030T135148Z-298269eb1505`. | git log --merges; ls-remote --tags |

## Tracker

Each row gives: owner, root cause, remediation (PR or action), acceptance test, observed outcome.

### Release chain (critical path, in order)

| # | Dependency | Cat. | Owner | Root cause | Remediation | Acceptance test | Observed outcome |
|---|---|---|---|---|---|---|---|
| R1 | Box gate sweep never completes | AUTOMATABLE | DH, AU | PT30M limit at 100% CPU. live-first ran unbounded before the gate. Research at equal priority starves release ops. The wrapper logs only at the end. | #666 bounds live-first to 300 s (AD CLEAR). Measure which child process consumes the 30 min. Research must run below release and risk (zuck 23:41Z); see B1. Gate heartbeat and priority inside workflow_gate.ps1 are ROOT (R9). | The gate log shows a `gate@<sha>` summary on 3 consecutive 10-min runs, with LastTaskResult 0. | Every run since 22:46Z killed. **#666 can merge only through this same sweep (deadlock).** |
| R2 | Hung adoption holds GitWriter | AUTOMATABLE | DH, AU | Stalled git child with no effective timeout on the path the box runs. Box code is 6fe812a00; LIVE's `Git.run` has a 300 s whole-tree timeout. | DH stops only the stalled fetch child, after checks. Assess reusing #555's watchdog for future hangs. | An induced, isolated git stall is killed and retried, and the next adoption completes (adopt log). | Hung since 22:50Z. |
| R2b | Adoption can never pass at the frozen release | AUTOMATABLE (after R10's owner run) | AU, AD, DH | The box runs the 10-29 adopt_guard, which has no box_published exemption. It reads ADOPT_CLEARS.jsonl as the TARGET carries it, and the target always falls back to release 298269eb15, which is frozen and lacks row 21. So 5 paths are uncovered forever (ADOPT_GUARD.json, 23:51:20Z). This is a deadlock, not slowness. Each futile pass also pauses state publishing. | A newer green release R (needs LIVE CI green, so #665 on LIVE, so the R10 run). R carries row 21. AD reviews R's own frozen state blobs and writes a CLEAR row, as with rows 22-24. Adopting R installs the guard with box_published. REFUSED: a box-local commit of the state files, which would manufacture the box_changed exemption. | The adopt log shows R adopted and ADOPT_GUARD.json shows ADOPT. The next release adopts with no new state row. | Deadlocked. Root cause from DH, 00:05Z, with box evidence. |
| R3 | LIVE CI red: journal D-20261103-004 | AUTOMATABLE | AU | `decide` accepted `evidence: []`. | #661: append-only amend verb; decide refuses empty evidence. AD CLEAR 5adeed81a. | #661 merged by the sweep, and `test_the_committed_journal_verifies` passes on a LIVE push run. | Not merged (R1). |
| R4 | LIVE CI red: ruff from #655 | AUTOMATABLE | YT | Lint errors merged by an owner merge. | #665 (AD CLEAR 69f9300c), plus the two law fences on the same files (YT). | LIVE `quality` green. | Not merged (R1). |
| R5 | No release since 10-30 | AUTOMATABLE | AU | No green LIVE run, so seal and promote don't run. | R3 + R4. | A new `release/*` tag after a green LIVE run. | None. |
| R6 | `master` stale, so trusted-eval and Actions audit-gate run old or no code | AUTOMATABLE | AU, GV | pull_request_target loads from the default branch. Promote moves master only on green LIVE. No alarm on divergence. | R5; then a divergence alarm (master age vs LIVE in the merge-pipeline watch) as an AUTO PR. | `actions/workflows/trusted-eval.yml` returns 200, and a trusted-eval run exists for #663. | 404. |
| R7 | CI queue starvation | AUTOMATABLE | AU | About 240 open PRs × 3 workflows against 20 concurrent jobs. | The box's `live_first_ci.py` (zuck 10-29 standing approval) runs inside R1. Until R1 works, a cloud-session script reorders the queue, which is not durable. | LIVE and CLEARed PR runs start within 10 min of queueing with no agent session running. | Cloud-session script, not durable. |
| R8 | PROTECTED/CONTROLLER PRs need zuck's APPROVE MERGES | AUTOMATABLE | GV | Design before the authority existed. | Level 1 authority, installed 22:31Z by zuck. A CONTROLLER PR needs an attestation, a base-run trusted-eval and a 24 h window. | Test B: #663 (head 21289f32b, AD CLEAR) merged by the gate, then adopted and healthy. | Not started (R1, R6). Authority activity is unobservable to agents (R12). |
| R9 | Controller files (audit_gate.py, trusted-eval.yml, workflow_gate.ps1) | NON-DELEGABLE until Level 2 | GV | ROOT: the authority never clears them, and a change switches attestations off until an owner re-pin. | #650 (Level 2) makes them CONTROLLER once a LIVE ruleset requires the authority App's status. | A controller PR merged by the gate with no owner act. | #650 at 2f8166ac7, AD carry CLEAR, CI re-queued. |
| R10 | Root authority itself (ops/release/authority/*, ROOT_POLICY.json) | NON-DELEGABLE | owner | No self-modification. Re-pin is an admin write of ROOT_PIN.json. The box acts on GitHub as zuck's login, so this file is the one act automation cannot forge. | Phase 4 (GV, 00:30Z): ONE owner run, `ops/release/authority/bootstrap_level2.ps1` (elevated, resumable, enforces nothing until GitHub confirms). The owner acts are: (1) start the run, which merges #650 pinned to its head under the ROOT bar, because #650 changes the authority itself; (2) tick Commit statuses R&W on the authority App and accept, because there is no API for App permissions; (3) Create, then Install, for each of the two Apps, because creating a write identity is an account-owner act. Everything else is automated: re-pin, live-seal environment, installers, writer conversion, both rulesets applied and read back, gh logout. Afterwards the gate and merger move ROOT→CONTROLLER, master and production become writable only by promote, and desk-sync-clean is removed from live-seal. Still exceptional after it: ops/release/authority/*, publisher/*, audit_gate.py, trusted-eval.yml, and the CRO lanes' CLI logins (external accounts). | The bootstrap's own read-back shows both rulesets active and the re-pin equal to LIVE's digest. A controller PR then merges with no owner act. | #650 pushed at d93e5dea3, carrying #665 (gates green). Not run. AD re-audit requested. |
| R11 | Repository ruleset activation | NON-DELEGABLE (one time) | owner | Rulesets need repo admin, which only zuck holds. | Bundle into the single bootstrap (R10), if it is needed. | The ruleset is active and blocks an unattested push in a test. | Prepared in #650, not applied. |
| R12 | Agents cannot see authority decisions | AUTOMATABLE | GV | ACL isolation (correct). | The authority publishes a non-secret status: the Level 2 `release-authority` commit status, or a summary file. | An agent reads per-PR authority verdicts without touching the key folder. | Unobservable. |
| R13 | Level 2 key placement: CRO lanes run elevated | AUTOMATABLE | GV | S4U/Highest (install_cro_cycle_tasks.ps1:63). MT5-CycleNoon and MT5-CycleMidnight run as SYSTEM/Highest and have never run. | De-elevate to a standard Limited account with its own clone. Committed locally by GV; blocked by C1. | Task principals read Limited, and the lanes still produce. | Not pushed. |
| R14 | Memecoin AUTO path (#658): registry file, machine env, clone | AUTOMATABLE (env/file), NON-DELEGABLE (attestations) | DH, GV | ACL denials (DH correctly did not elevate). Rows must be authority attestations, and the authority evaluates only the quant repo, so extending it is a root change (R10). | A provisioning step through the sanctioned elevated path, if one exists (adoption runs as SYSTEM). | A memecoin PR merged by the gate. | Not started. |
| R15 | Root pin broken by #658 | AUTOMATABLE inside R10's run | AU | #658 changed ops/box/workflow_gate.ps1 (ROOT) without a re-pin, so LIVE's root digest is not ROOT_PIN and the authority is off. This was an Autonomy error. | Bootstrap step 2 re-pins from LIVE after #650 merges (same owner run as R10; no extra act). Future: a PR that touches a ROOT file must say so in its title and stay out of the AUTO path. | The authority's log shows the pin equal to LIVE's root digest, then an attestation-driven merge. | Open. |

### CI and repository hygiene

| # | Dependency | Cat. | Owner | Root cause | Remediation | Acceptance test | Observed outcome |
|---|---|---|---|---|---|---|---|
| C1 | LIVE unpushable for sessions that merge LIVE (pre-push gate) | AUTOMATABLE | YT | ruff and law fences on the video-miner files. | #665 plus the YT fence fix. | A session push of a LIVE merge succeeds. | Refused. |
| C2 | Stale PR heads fail on files LIVE deleted | AUTOMATABLE | AU | Heads branched while #630's file existed. The sweep brings up only mergeable PRs. | Done once at 23:23Z. The recurring class needs a sweep-side bring-up of PRs that are red only because they are behind. | A PR red only because it is behind is brought up with no agent action. | Manual, by an agent, once. |
| C3 | Free-model independent-review unavailable | AUTOMATABLE | — | Free models are sometimes unavailable. | The review ends UNAVAILABLE and the PR is QUEUED and re-run later; it is never merged. | An observed QUEUED-then-reviewed PR. | — |

### Box operations

| # | Dependency | Cat. | Owner | Root cause | Remediation | Acceptance test | Observed outcome |
|---|---|---|---|---|---|---|---|
| B1 | Research load starves release ops and risk | AUTOMATABLE | DH, AU | Release ops have no priority rule. judge_priority.py only keeps the judge equal to the miners. | Order per zuck 23:41Z: live E8 > risk/release (gate, adoption) > research. Adoption is Adopt*, AUTO tier. The gate wrapper is ROOT or needs an admin task registration. | Gate and adoption finish inside their limits under 100% research load. Observed in the governor's own report: THROTTLE entered and left, with research given back its own class. | #666 bounds live-first to 300 s (AD CLEAR). #678 resource governor is a draft, awaiting audit and a box dry run. Neither is merged or installed. |
| B2 | Stale long-running pythons | AUTOMATABLE | DH | Unknown; needs an elevated read of SYSTEM command lines. | Identify them, then reap only orphaned or hung ones through the existing `proctree.reap_orphaned_workers`. | A census names every process older than 24 h. | UNMEASURED. |
| B3 | Scheduled-task install and repair | NON-DELEGABLE today | owner | Registering a task needs admin, and agent box sessions must not elevate. | A task-manifest reconcile step inside adoption, which runs as SYSTEM, would be the sanctioned path. Its safety rests on review plus the veto (B5). | A manifest change is reconciled by adoption with no owner act. | — |
| B3a | `scripts\run_video_cells_box.ps1 -Install` (after #665 is adopted) | NON-DELEGABLE today (B3 class) | DH | Needs Administrator and a non-interactive principal. | Same as B3: an adoption-run manifest reconcile. | The task exists with the expected principal and produces video cells. | Pending adoption. |
| B4 | Remote Control approval for agent box access | EXTERNAL | owner | The platform may prompt on zuck's device. | Measure whether a standing approval exists. | — | UNMEASURED. |
| B5 | Merged code runs as SYSTEM after adoption | Residual (stated) | — | Adoption and law_gate run as SYSTEM. | Independence rests on review plus the veto before a merge. | — | — |

### Credentials, sessions, handoffs

| # | Dependency | Cat. | Owner | Root cause | Remediation | Acceptance test | Observed outcome |
|---|---|---|---|---|---|---|---|
| K1 | New external API keys and App keys | EXTERNAL / NON-DELEGABLE | owner | Hard rule: agents never hold or ask for secrets. | The owner places each credential once. Not recurring for existing keys. | — | — |
| H1 | Work held only in a live session (for example R7's queue script) | AUTOMATABLE | AU | Cloud containers are reclaimed. | Move it to box tasks (R7) and project memory. | The queue keeps its order with no session alive for 2 h. | Session-held. |
| H2 | Agent handoffs and context loss | AUTOMATABLE | coordinator | — | Project memory, project files, threads, hourly pass. | — | Threads resumed after container restarts on 11-03. |

## Acceptance tests (zuck Phase 8)

| Test | Definition | Status |
|---|---|---|
| A | Ordinary PR: merged automatically, released, adopted and healthy, with 0 owner actions. Candidates: #666 or #661 (AUTO, CLEAR). | Not started (R1). |
| B | Protected PR #663: authenticated clearance, trusted-base checks, the full 24 h veto, controller merge, adoption, 0 owner actions. | Not started (R1, R6). |
| C | Induced recoverable faults (CI, scheduler, API, deploy) recover automatically. | Not started. |
| D | Each of these is rejected: spoofed approval, altered reviewer, veto bypass, unauthorised ceiling raise, stale attestation. | Not started. |
| E | 100 consecutive eligible PRs, each recorded with PR number, SHA, audit evidence, checks, veto, merge identity and time, release tag, adoption evidence, health, and human actions. | 0 of 100. |
