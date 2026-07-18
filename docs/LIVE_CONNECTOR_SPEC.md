# LIVE CONNECTOR — FROZEN BUILD SPEC (gap #2; consolidates every absorbed requirement)

_Frozen 2026-07-17. Build target: complete + reviewed + breaker-tested BEFORE the ~2026-08-05
validation gate so zero gate-time is wasted. Builder: the brain across dedicated cycles or the
CRO in a dedicated session — NOT as the tail of an unrelated session; risk-path code gets
built fresh or not at all. Sources: gap register row 2; ledgers `2026-07-16-v8-master-
blueprint-triage`, `2026-07-17-no-change-cap-principal-order`; principal throughput amendment._

## 1. Connector module (`libs/execution/binance_live.py`)
- Mirrors the testnet modules' interface EXACTLY (drop-in: `import binance_live as fut/spot`).
- Base URLs pinned to live; capability whitelist HARD-CODED: {place order, cancel, read
  account/positions/fills}. No withdrawal, no transfer, no sub-account, no key-management
  endpoints — enforced by the module exposing only whitelisted functions.
- Keys from `data/secrets/binance_live.json` — placed by the PRINCIPAL via SSH, trade-only,
  withdrawal-disabled, IP-whitelisted to the VPS. Module is fully inert without the file.
- `kill` path keeps its own reserved rate-limit budget (crisis = everyone else is hitting 429).

## 2. Stage machine (`data/stage_state.json` + `libs/execution/staging.py`)
- S0 testnet/paper (current) → S1 live-minimum → S2 full automation.
- S1 entry (Gate 0): principal places keys + explicit sign-off; λ-equivalent lock: capital
  fraction ≤ 0.10 of authorized live capital; 4–5 liquid symbols at venue-minimum notional
  (evidence breadth: calibration rows accrue ~4x faster).
- S2 entry (automatic, ALL must hold): ≥8 weeks live, ≥10 resolved calibration rows, 0
  critical drill failures, realized cost ≤ 1.25× modeled.
- Any tripwire demotes ONE stage instantly; demotions unlimited; every transition unit-tested
  including demotion. Stage flip also flips cadence (S1 adds weekly generation + canary floor).

## 3. Host-death survivorship (non-negotiable at S1)
- VENUE-SIDE PROTECTIVE STOPS: every live position carries a resting reduce-only stop at the
  EXCHANGE at ruin-line distance, placed/updated on every position change. These survive total
  host death.
- NO-NAKED-POSITION INVARIANT: reconcile check — any live position without its venue-side stop
  for >60s → freeze new entries + page.
- External heartbeat (already live) + monthly drill: kill the process with a testnet position
  open; verify the stop persists and the external page arrives.

## 4. Pager de-risk ladder (S1+)
- Page unacked 15 min → cancel resting orders + halve size; 60 min → flatten to neutral;
  4 h → full flatten, entries disabled until manual re-arm. Ladder drilled monthly.

## 5. Canary (S1+)
- Every 6 h: minimum-notional round-trip on the most liquid pair; failure or excess latency →
  limit-only mode + −50% max size for 6 h. Feeds the `data/canary_state.json` cadence floor.

## 6. Numeric ramp gate (no discretionary language)
- Upgrade size step ONLY when, trailing 8 weeks: (a) realized cost ≤ 1.25× modeled,
  (b) live Sharpe ≥ 0.6× same-period backtest, (c) slippage KS-test p > 0.05 vs model,
  (d) drill pass-streak ≥ 8 weeks, (e) calibration MAE falling 2 consecutive months.
- Down-steps unlimited and immediate. Leverage-optimizer clamp stays until its confidence
  pipeline is root-caused (gap #14) AND ≥30 uncontaminated live days AND principal sign-off.

## 7. Verification bar (risk-path code — from the principal's own v8 §8.2)
- Property-based tests: size never exceeds cap/negative; stop always present; stage
  transitions exact. Mutation testing on the connector + staging: ≥90% mutants killed or the
  build fails. A second model family fuzzes the five risk-path files against synthetic paths
  and writes a breaker report; CI asserts zero criticals. Dry-run harness on testnet first.

## 7b. GATE-0 PRE-MORTEM (mandatory, blocking -- principal 2026-07-18)
Before the PRINCIPAL_ACTION key request: the FULL 13-model panel pre-mortems the verified connector, breaker report, and arming plan. Mandate: argue this go-live fails; find the bug the tests missed. Unresolved critical findings block the request.

## 8. Explicitly out of scope for the connector build
- Key creation/rotation, deposits, withdrawals, capital sweeps: principal-only, forever.
- Any relaxation of Tier-3 rails, deadman, cadence floors.
