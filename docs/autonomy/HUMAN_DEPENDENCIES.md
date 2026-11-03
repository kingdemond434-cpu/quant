# Human dependencies in the quant release pipeline: the factual ledger

Started 2026-11-03 23:35Z by the Autonomy thread, answering zuck's 23:21Z and 23:25Z directive
("zero recurring human intervention for every legitimately delegable operation"). This file is
evidence only: a row is ELIMINATED+VERIFIED only when production evidence is cited. Code being
written, a PR being opened or a test passing on its own is never counted.

Statuses: **ELIMINATED+VERIFIED** (evidence cited) | **IN WORK** (the mechanism exists or is
being built; no production evidence yet) | **REMAINING** (the exact constraint is given) |
**OWNER-ONLY (exceptional)** (not recurring; it cannot be delegated without removing the
independence the system rests on).

## Headline facts, measured 2026-11-03 23:30Z

1. **No automatic merge has landed on LIVE since 2026-10-30.** Since 10-25, LIVE has 68 merge
   commits by `kingdemond434-cpu` (zuck's own GitHub merges), and 1 by `github-actions[bot]`:
   `298269eb1 Merge #483 (merge): audit CLEAR 252b83bc4`, 2026-10-30 12:58Z. There are 0 by the
   box registry sweep (title `Merge #N: ... registry CLEAR`) and 0 by the release authority path.
   Every merge since 10-30 has needed zuck. (`git log --merges --since=2026-10-25 --format=%an`)
2. **The newest release tag is `release/20261030T135148Z-298269eb1505`, more than four days
   old.** No LIVE CI run has passed since then, so seal/promote has minted no release for the
   box to adopt. LIVE `ci` runs on 11-03: every completed one failed or was cancelled. The runs
   on 442dfd6a8, 563d2e816 and e0b6b96e0 were still running at 23:28Z, an hour after they were
   queued.
3. **The cause of LIVE red:** `test_the_committed_journal_verifies` (D-20261103-004 had
   `evidence: []`). The fix is #661, with an AUDIT CLEAR at 5adeed81a, in the AUTO tier.
4. **The cause of risk-invariants red on most open PRs:** 21 PR heads still carried
   `mt5_ratchet.py`. #630 added it and #629 deleted it, and LIVE 8ff5596a9 does not contain it.
   20 of those PRs were brought up to date with LIVE via `update-branch` at 23:23Z, and the file
   is gone from every new head (#645 is superseded).

5. **No CONTROLLER PR can merge right now: `trusted-eval` has never run** (Governance, 23:29Z).
   `GET actions/workflows/trusted-eval.yml` returns 404. `pull_request_target` workflows are
   taken from the DEFAULT branch `master`, which is at f3bb5fc03 (11-03 17:45Z), from before
   #637 added trusted-eval.yml. `master` moves only when CI `promote` tree-takes it on a green
   LIVE run, and LIVE has been red (fact 3). So #661 → green LIVE → promote → master carries
   trusted-eval.yml → its next `ready_for_review` or `synchronize` event runs it on each PR.

6. **Box state, 23:29Z (Desk health, read-only):**
   - C:\opt\quant is at 6fe812a00 and gate-repo at 442dfd6a8.
   - The root pin is 8cbbb93f…f278 at commit d7fe4a7de (pinned 22:30:46Z).
   - The attestation env vars (ATTESTATIONS, PUBKEY, ROOT_PIN) are set.
   - **Quant-WorkflowGate: every sweep since 22:46Z was TERMINATED (0x41306) before it wrote its
     log, so nothing merges on the box.** Sweeps at 22:06Z and 22:27Z logged gh api 120 s
     timeouts and an i/o timeout to 140.82.121.5:443.
   - The authority's log, attestations and task are ACL-closed to agent box sessions, so
     whether the authority has signed anything is UNMEASURED by agents.
   - **The 22:50Z adoption is hung** (heartbeat stage "started", pid alive about 40 min). The
     22:35Z adoption held at 6fe812a00, "held-awaiting-audit", with production target
     298269eb1505 (the 10-30 release).
   - About 24 python processes from the 22:54Z fan-out may be starving both.

## The ledger

| # | Dependency | Status | Evidence / exact constraint |
|---|---|---|---|
| A1 | zuck's `APPROVE MERGES` on #453 for every PROTECTED/CONTROLLER PR | IN WORK | Level 1 release authority installed on the box 22:31Z (App installation 178340072, root pin 8cbbb93f…f278, task Quant-ReleaseAuthority). It signs CLEAR/HOLD per PR; the gate merges a CONTROLLER PR after a verified attestation, a green base-run `trusted-eval`, every gating+AUTO job and 24 h from its delivered notice. **Not yet proven:** no authority-cleared PR has merged. Acceptance case: #663 (CONTROLLER, one grow-only line), head 21289f32b. Earliest possible merge is 24 h after its notice. |
| A2 | zuck pasting Auditor rows into the box registry (AUTO tier) | IN WORK | The authority's signed attestations replace pasted rows. With the attestation env set, unsigned rows never clear. **Not yet proven** by a merge. |
| A3 | Marking drafts Ready | ELIMINATED in code, not yet verified | audit_gate marks an audited draft ready itself before merging (audit_gate.py docstring, rule "Then the gate marks a draft ready"). Verified only when A1/A2's first merge lands. |
| A4 | zuck merging PRs by hand | IN WORK | Fact 1: 68 of 69 merges since 10-25 were his. This is closed only by A1/A2 merges landing. |
| A5 | Root-authority changes (`ops/release/authority/*`, `ROOT_POLICY.json`) | OWNER-ONLY (exceptional) | By design, the authority never clears a change to itself (no self-modification). A merged core change switches attestations OFF until the owner rewrites `ROOT_PIN.json` as admin on the box. The box acts on GitHub with zuck's login, so that admin-only file is the one owner act automation cannot forge. Includes #650 (Level 2), head 2f8166ac7. |
| A6 | The controller files `audit_gate.py`, `trusted-eval.yml`, `workflow_gate.ps1` | REMAINING until Level 2 is enforced | These are ROOT today. Level 2 (#650) makes them CONTROLLER-class (base-evaluated, veto window), and they become owner-free only when a LIVE ruleset requires the authority App's status. Applying a repository ruleset needs repo-admin (GitHub permission), which only zuck holds. It is one time, not recurring. |
| A7 | Level 2 key placement | REMAINING (security HOLD) | The Auditor HOLDs it: the CRO lanes run as S4U at RunLevel Highest (`install_cro_cycle_tasks.ps1:63`), so an elevated lane could rewrite `authority.pub`/`ROOT_PIN` or read keys. Fix in work (Governance): a standard account with its own clone and no read of authority, registry or secrets. Same class: `MT5-CycleNoon` and `MT5-CycleMidnight` (SYSTEM, RunLevel Highest, never run) are to be de-elevated or removed under the same fix. |
| A8 | No PR author approving its own change | ELIMINATED by design, verified in code | The authority runs under its own Windows account and a read-only App. It cannot push, comment or merge. The gate merges and the authority signs, under separate identities (authority.py docstring). Claude never posts AUDIT CLEAR or writes registry rows. |
| C1 | CI queue starvation, reruns and cancels | REMAINING (agent-run, not durable) | Today a cloud session script reorders the queue (pre-approved 10-29). That is an agent dependency that dies with the session. GitHub-hosted concurrency is the bottleneck: about 240 open PRs, each with ci and release-gates. A durable fix must run on the box or in a scheduled workflow. Not built yet. |
| C2 | LIVE red blocking every release | IN WORK | Fact 3: #661, AUTO, CLEAR. It merges by the sweep after its window, then LIVE CI → seal → release tag. |
| C3 | Stale PR heads failing on deleted files | ELIMINATED for this case (23:23Z), recurring class REMAINING | Fact 4. The gate's box sweep brings a behind PR up only when it is otherwise mergeable. A stale-head refresh for every PR is not automated. |
| C6 | LIVE ruff red from #655 (it blocks every push that merges LIVE, through the pre-push gate) | IN WORK | #665, CLEAR at 69f9300c, AUTO tier. It merges only through the box sweep, so B1 binds. |
| C5 | `pull_request_target` workflows (audit-gate, trusted-eval) run from a stale `master` | IN WORK | Fact 5. It clears when promote runs after #661. Recurrence guard not built: master trailing LIVE silently disables base-run evaluation, and nothing alarms on it. |
| C4 | Independent-review (free models) unavailable | ELIMINATED in code | It ends UNAVAILABLE → the PR is QUEUED, never merged without review, re-run by the next sweep (audit_gate docstring, step D). |
| D1 | Box adoption of a new release | IN WORK | MT5-AdoptRelease runs hourly at :12 as SYSTEM. **No release since 10-30 (fact 2)**, so no adoption of 11-03 code can have happened through the release path. Box evidence (running HEAD, last adoption log) has been requested from Desk health and is not yet received. |
| D2 | Post-adoption health checks | IN WORK | Not run against a new release since 10-30. |
| D3 | Box provisioning for #658 memecoin gate (registry file, Machine env `MEMECOIN_AUDIT_REGISTRY`, `memecoin-gate` clone) | REMAINING | Desk health got ACL denials and did not elevate (correctly). The only standing elevated path is adoption running as SYSTEM, and the independence of that path rests on review plus the veto (A9). The clone is made by workflow_gate.ps1 itself once the env var exists. |
| D4 | Memecoin CLEAR rows | REMAINING | They must be authority attestations, not Claude rows. The authority evaluates only kingdemond434-cpu/quant. Extending it to memecoin changes the authority core (A5, owner re-pin), and memecoin_gate.py must then verify signatures. |
| B1 | Gate sweep reliability: killed by its task time limit | REMAINING (critical path) | Measured 23:31Z (Desk health): the task's ExecutionTimeLimit PT30M kills every sweep (0x41306), because box CPU is at 100% and sweeps now run past 30 min. The wrapper logs only after audit_gate returns, so a killed sweep leaves no line. **While this holds, no AUTO or CONTROLLER PR can merge automatically, #661 and #665 included: the attestation/registry path runs only in the box sweep.** CPU load: about 50 new pythons since 22:50Z under a SYSTEM task tree started 16:41Z, plus five pythons running for days (pids 9356, 2192, 21924, 4712, 24096). SYSTEM command lines are hidden from the agent's Administrator token. The fixes are: a heartbeat before audit_gate, a limit sized to load, and the gate at a priority above research but below live, so the judge/miner equal-priority rule is not touched. All of these are in workflow_gate.ps1 (ROOT) or the task registration (admin). The gate's code (audit_gate.py, workflow_gate.ps1) is ROOT, so a fix to the gate itself needs the owner re-pin (A5) until Level 2 (A6). The task time limit is set by task registration, which needs admin (S1). |
| B2 | Hung adoption | REMAINING, recovery in work (Desk health) | Fact 6. The 22:50Z adoption has been idle on a git child for more than 40 min while holding Global\MT5-GitWriter-v2, which blocks intel-ship-adopt. LIVE's Git runner already has a 300 s whole-tree timeout (libs/ops/release_promotion.py `Git.run`). The box runs its local commit 6fe812a00 (not on origin), so the stalled call's version and path are UNMEASURED. There is no watchdog that kills and retries a hung adoption. The self-heal watchdog #555 is unmerged (AUTO, CLEAR at 0fcae913). |
| B3 | Agents cannot observe the authority (ACL-closed log, attestations, task) | REMAINING by design | Keeping it isolated is the point. A read-only status export by the authority is needed for evidence: either Level 2's `release-authority` commit status (#650, owner-only), or a public-safe summary file the authority writes. |
| A9 | Independence of code run as SYSTEM after adoption | RESIDUAL (stated, not eliminable here) | Adoption and law_gate run merged code as SYSTEM. Independence therefore rests on review plus the veto window before a merge, not on process separation. |
| K1 | Credentials: API keys, App keys, key files | OWNER-ONLY (exceptional, per new credential) | Hard rule: agents never ask for, hold or store secrets. A new external key is placed by the owner. It is not recurring for existing keys. Rotation of the leaked YouTube key is explicitly waived by zuck. |
| S1 | Scheduled-task install and repair on the box | REMAINING | Registering or repairing a task needs admin. Agent box sessions (Remote Control) run without elevation and must not elevate. The self-heal watchdog (#555) is not merged. |
| S2 | Remote Control approval for agent box access | REMAINING | `start_remote_control` can show an approval prompt on zuck's device. Whether a standing approval for this box exists needs to be measured. |
| H1 | Agent handoffs and context loss | ELIMINATED in practice, partially verified | Project memory, `/mnt/project-files` and threads persist across sessions. The hourly pass (trigger) re-creates work. Measured gap: work that lives only in a running session script (C1) is lost on a container restart (this happened 11-03). |

## Acceptance protocol (not yet run)

1. #663 completes A1 end to end, with each step's artifact recorded here: the attestation
   file name and verdict, the trusted-eval run id, the notice time, the merge commit and its
   author, the release tag, the adoption log line, the running HEAD on the box, and the health
   check output.
2. An adversarial stage, with each case expected to be refused:
   - a CONTROLLER PR that loosens a base-pinned test;
   - a ROOT change;
   - a moved head after a CLEAR;
   - a HOLD inside the window.
3. Then count 100 consecutive eligible PRs merged and adopted with zero human actions, listing
   each PR number, merge author and adoption tag.

Until step 1 has evidence, the honest status of the pipeline is: **not autonomous; every merge
since 2026-10-30 needed zuck.**
