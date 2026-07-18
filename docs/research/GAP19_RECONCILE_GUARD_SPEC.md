# Gap #19 — Venue-Truth Divergence Circuit Breaker (reconcile guard) — SPEC, QUEUED POST-GATE-0

**Status:** spec pre-built 2026-07-19 (operator instruction). Implementation **queued for
post-Gate-0** (freeze holds; risk-path monitor, needs property/mutation tests before it goes live).
Independently proposed by 2/11 tier-1 panel models on 2026-07-17 (google/gemini-3.1-pro,
moonshotai/kimi-k2.6) — corroborated, not a one-off.

## Problem
Executor-book PnL (`web/live_combined.json` → net) and the dead-man's independent **venue-truth
equity** (`web/venue_equity.json`, derived from exchange account state) both exist as feeds, but
**nothing trips when they diverge.** The mark-vs-reality gap that hid the −41% NOM event on 2026-07-13
would, today, still surface only via a human audit. A books-vs-venue divergence is the earliest
possible signal that the book's own accounting has drifted from exchange truth.

## Design (a READER, never a writer of the risk rails)
- **Where:** a monitor pass (in `scripts/run_alerts.py`, alongside the existing 3-min ticks — NOT
  in the executor's risk path, so it stays a pure observer and respects the single-writer invariant).
- **Compute each refresh tick:** `divergence = |book_net − venue_truth_net|` (both re-based to the
  same start epoch and valuation convention — timestamp-aligned, like-for-like, per gap #30).
- **Band:** calibrate to **~2× the observed steady-state book-vs-venue noise** (measure the divergence
  distribution over ≥14 quiet live days first; do not hardcode a guess). Store the band + its
  calibration date in a small config so it is auditable and re-tunable.
- **On breach:** emit a `VENUE-DIVERGENCE` action that causes **RISK-PAUSE-OPENS** (hold + close only,
  add no new risk) **and pages** the operator. Auto-resumes when divergence returns within band for
  a hysteresis window (e.g. 3 consecutive clean ticks).

## Hard invariants (these are what make it safe, and testable)
1. **PAUSE, never FLATTEN.** It must stay clearly distinct from the Tier-3 dead-man's
   drawdown-from-high-water survival trigger. This is a *reconciliation* check, a different mechanism.
2. **NEVER writes the dead-man's state file.** Two-writers-on-one-rail was the 2026-07-11 false-fire
   root cause. This guard only READS venue-truth; it owns its own tiny state (last breach, paged-flag).
3. **Read-only wrt the executor book.** It signals PAUSE via the existing risk-action channel the
   executor already honours; it does not mutate positions or size.
4. **Independence-gated build.** Touches the risk path → do NOT co-window with any other risk-path
   change (same rule that governs #32).

## Test plan (property/mutation, to the v8 8.2 bar — required before live)
- band breach ⇒ pause + page fires exactly once (paged-flag dedupes);
- within-band ⇒ no pause, no page (no alarm fatigue);
- divergence returns within band for the hysteresis window ⇒ auto-resume;
- the guard NEVER opens a file handle to the dead-man state (assert via path mocking);
- re-based/timestamp-aligned comparison is correct under a simulated clock skew;
- a mutation that flips PAUSE→FLATTEN or adds a deadman-state write must FAIL a test.

## Calibration + rollout (post-Gate-0)
1. Log raw `book_net − venue_truth_net` each tick for ≥14 live days; fit the noise band (2× the
   quiet-state spread).
2. Ship behind the tests above; verify one synthetic breach pauses+pages+auto-resumes on testnet.
3. Only then arm on the live book. Until then, the daily micro-audit remains the divergence catch.
