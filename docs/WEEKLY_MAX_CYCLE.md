# WEEKLY GAP-MAX SWEEP — standing autonomous cycle (principal order 2026-07-29)

Constitution L4 (weekly) + L2.9 capability audit loop, made operational. Two halves, both
autonomous — the sweep never waits for the principal to ask.

## What one sweep does (in order)

1. **RE-ORIENT** — fresh-read GAP_REGISTER (re-rank stamp), DESK_BRIEF, latest desk snapshot,
   max_audit output, decision-ledger tail. Known state first, so step 2 hunts what is NOT there.
2. **UNKNOWN-GAP AUDIT** — parallel sweep of EVERY subsystem (data, validation, execution, risk,
   portfolio, ops/infra, research process, governance/docs), each auditor hunting gaps NOT on
   the register, with the proactive battery (self_interrogation_patterns.md) as the method.
   Every candidate finding is adversarially verified (refute-first), then rowed on the register
   or closed with a written reason. Dedup against register + graveyard before rowing.
3. **MAX BUILDOUT** — everything unblocked gets built/upgraded to its validated ceiling,
   highest-EV first (L1.26): upgrade existing before new, merge duplicates, activate the unused,
   retire what fails justification (L2.9 exits only). Risk-path code keeps the v8 8.2 bar
   (property + mutation + second-family fuzz) and Tier-3 stays never-touch.
4. **BLOCKER LEDGER** — everything blocked gets its exact dependency + next action + owner
   recorded (register row or PRINCIPAL_ACTION page). Silence is the only forbidden outcome.
5. **VERIFY + SHIP** — full CI (ruff + whole-tree pytest + mypy), mutation spot-check on
   anything risk-path touched, commit with evidence-bearing messages, push.
6. **REPORT** — what moved, what was measured, what is blocked on whom, and the answer to the
   standing L1.26 question: *the single highest expected-value improvement right now*.

## The two halves

- **Desk half (VPS, already cadenced):** the weekly deep cold audit + churn loop (L4) carries
  the sweep's audit duties; max_audit's fences enforce dispositions daily. No new organ — this
  rides existing cadence per the anti-bloat rule.
- **Builder half (scheduled Claude session, this repo):** a weekly scheduled session runs the
  full 6-step sweep above with multi-agent fan-out, exactly like the 2026-07-29 session that
  installed this file. Schedule: weekly (created 2026-07-29 via the remote-session scheduler).
  The session works on branch `claude/wonderful-darwin-7uiobi` (or its successor), commits and
  pushes; the VPS pulls on its normal deploy path.

## Non-negotiables the sweep inherits

- L1.24: activity is not output — every build names the compounding path it serves.
- L1.25: zero survivors triggers diagnostics, never surrender.
- L1.27: cheap reversible improvements get built, not deliberated.
- L2.4: every claim carries its proving command and the value read.
- §41: every recommendation reaches implemented / rejected-with-reason / scheduled-with-date.
- The sweep believes it is never done: "maxed" is a floor with a ratchet, not a state.
