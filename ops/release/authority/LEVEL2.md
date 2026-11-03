# Level 2: GitHub itself enforces the release authority (NOT ACTIVE)

Level 1 trusts the box gate to honour the authority's attestations. Level 2 makes GitHub refuse any
merge into LIVE that the authority did not pass. A rewritten gate, an agent on the box or a leaked
login then cannot land code that way. It is staged, and nothing here is on until the last step.

| Step | What | State |
|---|---|---|
| 1 | The authority posts the `release-authority` commit status on each PR head. CLEAR on AUTO/LOW gives success. CLEAR on CONTROLLER gives success only once `veto_hours` have passed since its FIRST signed CLEAR. ROOT, HOLD and FAIL give failure. It is on only while `C:\opt\audit_registry\POST_STATUS` exists. | built (#650) |
| 2 | A state publisher under its own Windows account holds a "quant-state" App key and pushes a box commit to LIVE only if every path is a state path (`libs/ops/release.py` `STATE_PREFIXES`). It replaces the direct `git push` in sync_shadow_to_git.ps1, Adopt-Release.ps1 and sign_train_leg.ps1. | built (#650) |
| 3 | `workflow_gate.ps1` and `sign_train_leg.ps1` use a "quant-merger" App token (`ops/release/merger/merger_env.ps1`; Contents, Pull requests and Workflows write) instead of zuck's gh login, whenever `C:\opt\merger\config.json` exists. | built (#650) |
| 4 | Once the merger is installed, the CRO cycle's agents push code to `cro/<lane>-<date>` and open a PR, never LIVE. CI's seal and promote jobs push LIVE, master and production as the state App, from an environment that admits LIVE alone. | built (#650) |
| 5 | The owner's one bootstrap run (below). | ready |

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

## The bootstrap: one owner run, once (`bootstrap_level2.ps1`)

Everything the owner did by hand in the earlier six-step list is now one elevated run on the box,
`powershell -ExecutionPolicy Bypass -File C:\opt\authority\repo\ops\release\authority\bootstrap_level2.ps1`
(after `git -C C:\opt\authority\repo fetch` and a checkout of the cleared #650 head, or of LIVE
once #650 is in). It is resumable and enforces nothing until its last step. Inside it, the owner
makes five decisions in his browser and the script does the rest:

| # | What the script does | The owner's act | Why it cannot be delegated |
|---|---|---|---|
| 1 | Checks #650's exact head against the gate's ROOT bar (`bootstrap_github.py ready`: every gating and AUTO check genuine and green, the latest trusted audit verdict a CLEAR of that head), then merges pinned to that head | starting the script | #650 changes the authority itself. No authority may approve its own change, and every other identity on the box is an agent's |
| 2 | Re-pins the root digest from a clean LIVE checkout | none (the run is elevated) | `ROOT_PIN.json` is admin-write on purpose: the pin is what an agent must never move |
| 3 | Creates `POST_STATUS`, runs the authority, and waits until it has posted a status | ticks Commit statuses: Read and write on the authority App, Saves, and Accepts on the installation | GitHub has no API that changes an App's permissions; only the App's owner can grant them |
| 4 | Serves the manifest for `quant-merger`, converts the code itself, writes the key into the App's own folder (no download), opens the install page, runs `install_merger.ps1` | clicks Create GitHub App, then Install on quant only | Creating an identity with write access to the repository is an account owner's act on github.com |
| 5 | The same for `quant-state-publisher`; configures `live-seal` (LIVE alone), `STATE_APP_KEY` and `STATE_APP_ID`; runs `install_publisher.ps1`; writes `STATE_APP.json` | the same two clicks | as 4, and environments and secrets are admin settings |
| 6 | Waits for a clean publisher pass and a merger token | none | |
| 7 | Fills the state App's id into both rulesets, runs `check_ruleset.py`, applies them, and reads LIVE's rules back the way the authority does every pass | none (his gh login, which he is running) | rulesets are admin settings |
| 8 | `gh auth logout`, and removes github.com entries from Credential Manager and every gh `hosts.yml` on the box | none | |

After that run:
- A routine PR (AUTO/LOW) and a protected one (CONTROLLER) need no owner act. The authority clears
  it, GitHub requires the authority's status, the merger merges it, and CI seals and promotes it as
  the state App.
- `ops/box/workflow_gate.ps1` and `ops/release/merger/*` move from ROOT to CONTROLLER by
  themselves. `ROOT_POLICY.json` `enforced_root_files` makes that switch, and it happens only while
  the authority reads GitHub's rule as active (`authority.level2_enforced`, which fails closed).
  Once GitHub enforces the status, a rewritten gate or merger cannot land anything the authority
  did not pass.
- **ROOT stays exceptional, and it is named.** These files remain ROOT:
  - `ops/release/authority/*` (the authority's code, policy, pin tools and rulesets);
  - `ops/release/publisher/*` (its path filter is the only bound on the state App's bypass);
  - `.github/scripts/audit_gate.py` (the authority loads it);
  - `.github/workflows/trusted-eval.yml` (the authority's base-run evidence).

  A change to one of them is merged by the owner through the admin bypass, which works in
  pull_request mode only, and is then re-pinned. There is no other way, by design.
- `master` and `production` take updates only from the state App (`ruleset_master.json`). master's
  `trusted-eval.yml` is the file pull_request_target runs, and production is what the box adopts.
  Before this, any write-capable login could move either: it could fake the base-run evaluation or
  roll the box back.

What the bootstrap does NOT make autonomous:
- the CLI logins of the CRO lanes' standard account (`claude /login`, `codex login`), which belong
  to the owner's Anthropic and OpenAI accounts;
- any box agent session that still pushes with the owner's gh login. Step 8 removes that login, and
  such sessions must use the merger identity (`merger_env.ps1`) from then on.
