# Level 2: GitHub itself enforces the release authority (NOT ACTIVE)

Level 1 trusts the box gate to honour the authority's attestations. Level 2 makes GitHub refuse any
merge into LIVE that the authority did not pass. A rewritten gate, an agent on the box or a leaked
login then cannot land code that way. It is staged, and nothing here is on until the last step.

| Step | What | State |
|---|---|---|
| 1 | The authority posts the `release-authority` commit status on each PR head. CLEAR on AUTO/LOW gives success. CLEAR on CONTROLLER gives success only once `veto_hours` have passed since its FIRST signed CLEAR. ROOT, HOLD and FAIL give failure. It is on only while `C:\opt\audit_registry\POST_STATUS` exists. | built (#650) |
| 2 | A state publisher under its own Windows account holds a "quant-state" App key and pushes a box commit to LIVE only if every path is a state path (`libs/ops/release.py` `STATE_PREFIXES`). It replaces the direct `git push` in sync_shadow_to_git.ps1, Adopt-Release.ps1 and sign_train_leg.ps1. | built (#650) |
| 3 | `workflow_gate.ps1` and `sign_train_leg.ps1` use a "quant-merger" App token (`ops/release/merger/merger_env.ps1`; Contents, Pull requests and Workflows write) instead of zuck's gh login, whenever `C:\opt\merger\config.json` exists. | built (#650) |
| 4 | Once the merger is installed, the CRO cycle's agents (Run-DeskCycle.ps1) push code to `cro/<lane>-<date>` and open a PR, never LIVE (built in #650). Still to build: CI's seal job stops pushing LIVE with GITHUB_TOKEN. It uses the state App's token from an Actions **environment restricted to the LIVE branch**, so a PR's own workflow never sees that token. | to build |
| 5 | The owner's setup: authority App commit statuses set to Read & write; create the two Apps; `New-Item C:\opt\audit_registry\POST_STATUS`; put the state App's id in place of `actor_id: 0`, run `python ops/release/authority/check_ruleset.py` until it prints `SAFE to import`, then import `ruleset_live.json`; `gh auth logout` and clear the box's git credential. | after 2-4 run on the box |

Why each piece is needed:
- A ruleset requiring a status refuses direct pushes too, and today five box writers push LIVE with
  zuck's login.
- A personal repo's ruleset can't limit a bypass to paths, so the state App's key must sit under its
  own account behind a paths-only check, the same way the authority key does.

`ruleset_live.json` has two bypass actors, and `check_ruleset.py` refuses any other set:
- repository admin, in **pull_request** mode only (zuck's ROOT merges, never a direct push);
- the state App.

GitHub Actions is never a bypass actor (#650 audit MF). A same-repo `pull_request` run executes
the PR's own workflow file with a write-scoped GITHUB_TOKEN, so an Actions bypass would let any
branch push LIVE past the authority.

The veto clock runs from the first CLEAR signed after the latest signed HOLD on that head, so a
HOLD that is raised and then lifted restarts the window. FAIL and WAIT are never signed and do not
restart it; they stop the status at failure or pending while they stand.

The required check is pinned to the authority App (`integration_id` 5601819), so no other identity
can post a status that satisfies it.

## The owner's Level 2 setup, in order (once #650 is merged and adopted)

Each step is safe to stop after, and nothing is enforced until step 6.

1. **Re-pin** (#650 is ROOT): run `python ops\release\authority\pin_root.py --write C:\opt\audit_registry\ROOT_PIN.json` from a clean checkout of LIVE.
2. **Authority App:** on its settings page, set Commit statuses to Read & write. Then run `New-Item C:\opt\audit_registry\POST_STATUS` and the authority starts posting the check.
3. **Create the "quant-merger" App** with Contents, Pull requests and Workflows Read & write, and Metadata Read. No webhook; install it on quant only. Then run `install_merger.ps1 -AppId N`.
4. **Create the "quant-state-publisher" App** with Contents Read & write and Metadata Read. Then:
   - run `install_publisher.ps1 -AppId N`;
   - write `C:\opt\audit_registry\STATE_APP.json` as `{"login": "quant-state-publisher[bot]"}`, which starts the push-log detector with a baseline.
5. **Wait a day.** Check that the state publisher's log shows pushes, and that the CI seal step (step 4 above) is built.
6. **Enforce:**
   - put the state App's id in `ruleset_live.json`;
   - run `python ops\release\authority\check_ruleset.py` until it prints `SAFE to import`;
   - import the ruleset (Settings, Rules, Rulesets, Import);
   - on the box, run `gh auth logout`, and remove zuck's github.com entry from Windows Credential Manager.
