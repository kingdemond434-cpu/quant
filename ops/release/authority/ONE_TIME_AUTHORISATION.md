# Release authority: one-time authorisation pack (for zuck's review)

Nothing in this PR turns anything on by merging it. The gate keeps working exactly as it does
today (zuck's CLEAR + APPROVE path, then the unsigned registry path) until you finish step 6.
Every step below needs you, once, because each one creates an identity, a key or a root rule,
and none of them can be done legitimately by a code-writing agent.

## What you get

- **No more registry pastes.** The authority signs a CLEAR for each eligible PR itself, so you
  stop editing `C:\opt\audit_registry\registry.jsonl`. Once the authority is on, the gate reads no
  unsigned CLEAR row at all. A HOLD row you paste still works as a veto.
- **Kept as they are:** the 24 h veto window (it starts only when the gate's ntfy notice is
  delivered), replay-shadow, risk-invariants, independent-review, the gating CI, auto-revert,
  DEACTIVATE and AUDIT HOLD.
- **New:** a base-run `trusted-eval` job for any PR that changes a check. It runs the BASE's tests
  and the BASE's ceilings check against the PR's code, so a PR can't approve itself by rewriting
  its own checks.
- **Emergency stop:** create the file `C:\opt\audit_registry\attestations\DEACTIVATE`, or post
  `DEACTIVATE RELEASE CONTROLLER` on #453. Either one stops all signing and all authority merges
  at once.

**Two honest limits, from the Auditor's review:**
- `trusted-eval` starts running PR code (read-only token, no secrets) on every same-repo PR the
  moment this merges. That's why this PR also removes `cache: pip` from the gating workflows:
  PR code runs in the base's cache scope, so no gating job may read a cache.
- A `trusted-eval` green proves the base's tests pass against an *honest* head. A hostile head
  could fake one. Against a hostile author, the defences are independent review, the 24 h veto
  and auto-revert, plus Level 2 below.

## The steps (about 20 minutes, once)

1. **Review and merge this PR through your own path.** Post `AUDIT CLEAR <head>` on the PR,
   then `APPROVE MERGES` on #453. It is ROOT, so it can't clear itself and the authority will
   never clear it.
2. **Create the read-only GitHub App** "quant-release-authority" (github.com, then Settings,
   Developer settings, GitHub Apps, New).
   - Permissions are all **Read-only**: Contents, Metadata, Pull requests, Checks, Actions,
     Issues, Commit statuses.
   - No webhook. Install it on `kingdemond434-cpu/quant` only.
   - Note the App ID and the Installation ID, and generate one private key (a .pem download).
3. **On the box, over RDP, elevated:**
   `powershell -File C:\opt\quant\ops\release\authority\install_authority.ps1 -AppId <id> -InstallationId <id>`
   - It creates the `quant-authority` account, its folders and their ACLs, generates the signing
     key inside that account's own folder (no key is ever shown or typed), writes the public key
     and the root pin, and registers the 10-minute task.
   - Then move the App .pem you downloaded to `C:\opt\authority\key\app.pem` yourself.
4. **Dry run.** Run `schtasks /Run /TN Quant-ReleaseAuthority` once, then read
   `C:\opt\authority\authority.log`. You'll see one verdict line per open PR. Nothing merges yet,
   because the gate isn't reading the authority until step 6.
5. **Sandbox proof on the box.** Run `python C:\opt\quant\ops\release\authority\sandbox.py`.
   It ends `DEMO PASS` (the full sign, notify, 24 h and pinned-merge flow against a fake GitHub).
6. **Turn it on.** Set three machine environment variables (elevated):
   - `setx /M QUANT_AUTHORITY_PUBKEY C:\opt\audit_registry\authority.pub`
   - `setx /M QUANT_AUTHORITY_ATTESTATIONS C:\opt\audit_registry\attestations`
   - `setx /M QUANT_AUTHORITY_ROOT_PIN C:\opt\audit_registry\ROOT_PIN.json`

   `QUANT_AUDIT_REGISTRY` stays set as it is today: it holds the window record and your HOLD
   rows. From the next sweep on, PROTECTED PRs merge from verified attestations, 24 h after the
   gate's delivered notice.

After this the only recurring touch is a **root change**, which is rare by design: a change to
the authority, the gate core, `trusted-eval.yml`, `workflow_gate.ps1`, `ROOT_POLICY.json` or
the sizing envelope. You merge it through your own path, then re-pin with
`python ops\release\authority\pin_root.py --write C:\opt\audit_registry\ROOT_PIN.json` from a
clean checkout of LIVE. Until you re-pin, the authority signs nothing and the gate ignores
attestations, so a root change can only switch the path off, never on.

## What becomes zero-touch, and what honestly can't

Classified against the 216 open PRs on 2026-11-03:

| Class | Open PRs | After this |
|---|---|---|
| AUTO / LOW (code, sizing, allocator, judge, sealed files on the AUTO floor) | 200 | Already no-touch on the AUTO path. Their blockers are CI, replay-shadow and review, not you |
| CONTROLLER (workflows, `ops/release/*`, reviewer, ceilings, conftest, gates.sh) | 11 | **Zero touches.** Authority CLEAR + trusted-eval + 24 h veto |
| Ceiling raise inside the envelope | 1 (#598) | **Zero touches** (see below) |
| ROOT (gate core `audit_gate.py`: #626, #623, #597, #498) | 4 | **Still you** in Level 1. Level 2 removes this |

**Why the gate core stays root in Level 1.** Today the box merges with *your* gh login, and any
script that runs on the box can use it. A gate change that the authority cleared could rewrite
how the gate merges. That would let an agent's change take merge power, and no test of the base
can fully rule it out. So in Level 1 a change to the merger needs the root path.

**Level 2 (recommended next, one more sitting of about 15 minutes).** This takes the gate core
off the root list:
- A second App, "quant-merger", with Contents write, Pull requests write and Workflows write,
  replaces your gh login in `workflow_gate.ps1`. You then log your gh out on the box.
- A LIVE ruleset requires the status check `release-authority` from the authority App.
- The box-state publish gets its own App in the ruleset's bypass list.

Then GitHub itself refuses any merge the authority didn't pass, even one made by a rewritten gate.
`audit_gate.py` moves from ROOT to CONTROLLER, and the only root left is the authority, its policy
and the ruleset. I'll build it on your word.

**Things no design should make autonomous, and this one doesn't:**
- **Replay-unmeasured money-path changes** (#439, #479, #483). These stay blocked until
  replay-shadow measures them. The fix is widening replay-shadow's scenario grid, never a CLEAR.
- **A reviewer FAIL** (#489 and others). It is never converted into a CLEAR. The route is the
  author fixing the issue and the reviewer re-reviewing the new head. Automatic adjudication of
  false findings is designed but not built in this PR:
  - The trigger is a reviewer finding that a base-versus-head deterministic test refutes.
  - A second independent model family must agree it's false.
  - Only then does the finding clear, and only under a ROOT_POLICY rule.
- **A conftest change a PR genuinely needs.** trusted-eval uses the base's conftest. A PR whose
  tests only pass with its own conftest fails trusted-eval and stays blocked. Split the conftest
  change into its own PR, which trusted-eval can then judge.

## The sizing envelope (your 19:19Z ask)

`ROOT_POLICY.json` `envelope` delegates ceiling raises:
- A listed knob may go up, by at most **25% per PR**, up to its `hard_max`.
- Every other gate still binds: replay-shadow measures the effect, independent-review, the 24 h
  veto, and auto-revert if LIVE CI breaks.
- Firm rules are `fixed`: FTMO `DAILY_LOSS_FRAC` 5% and `MAX_LOSS_FRAC` 10%. E8's 2.5% daily and
  the $90k floor live in the rails, which are `superset` and `equal` pins. None of these can ever
  be raised this way.
- Lowering a ceiling is not delegated either. NEVER REDUCE AGGRESSIVENESS means no cap by fiat,
  so a lowering goes to your path.
- Per-trade risk is clipped at run time to the remaining firm headroom by the rails, which no
  envelope raise can move. For example, MAX_RISK_FRAC 0.10 never means risking 10% against
  E8's 2.5% daily limit.

**The honest gap.** The `hard_max` values are set to today's ceilings (MAX_RISK_FRAC 0.10,
BASE_RISK_FRAC 0.03, MAX_NOTIONAL_X 5.0), so nothing can be raised yet. The right `hard_max` is
`min(shrunk fractional-Kelly optimum, survival bound)`:
- the optimum uses crisis correlations;
- the survival bound keeps P(breach of any firm's daily or max loss) under 1%.

That number has to come from a base-run calculator over heat_policy's measured curves, not from
me typing it. **Next build:** an `envelope-eval` job that computes it on every ceilings PR and
writes the bound into the attestation's evidence. After that, raises toward the measured optimum
are fully autonomous, and only the formula itself stays root.

## Threat model in one breath

- A Claude or Codex session can't mint a CLEAR, because it never holds the key: the key folder
  is readable only by `quant-authority` and SYSTEM.
- An edited, forged, stale, expired or other-key attestation fails verification.
- A changed root policy changes the digest, which voids every old attestation, and LIVE stops
  matching the pin.
- A PR that changes the checks is judged by the base's tests (`trusted-eval`), never by its own.
- A missed notice starts no window.
- A HOLD, a DEACTIVATE, a kill file, a new push, a failed or re-run-red check, or conflicting
  verdicts each stop the merge.
- The merge is pinned to the head sha, so of two concurrent merges GitHub accepts one.
- A merge that breaks LIVE CI is auto-reverted (#591).
- **Residual risk until Level 2:** anything running as Administrator on the box can use your gh
  login.
