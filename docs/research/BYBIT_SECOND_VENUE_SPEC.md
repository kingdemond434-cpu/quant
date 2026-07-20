# BYBIT SECOND VENUE — PREBUILT SPEC (founders-review directive #2, principal 2026-07-19)

_Status: SPEC ONLY — deploy strictly POST-GATE-0 (freeze governs). Prebuilt per the standing
spec-prebuild rule so execution never waits on design. Purpose: kill the single-counterparty
tail (FTX class — the desk's largest unpriced risk), double funding-rate breadth, and open
cross-venue basis as a free orthogonal signal axis. The recorder ALREADY captures Bybit L2
24/7, so the data moat accrues before a single order is placed._

## 1. Connector (`libs/execution/bybit_live.py` + `bybit_spot_live.py`)
- Mirror the binance_live.py pattern EXACTLY: same function surface (drop-in), triple-guard
  arming (own keyfile `data/secrets/bybit_live.json` + shared `data/LIVE_ENABLE` + shared
  `data/LIVE_VPS_VERIFIED`), keyfile-only credentials (no env path), capability whitelist by
  construction (place/cancel/read ONLY — no withdraw/transfer/sub-account wrapped, ever),
  reserved rate-limit budget for the kill path.
- Bybit-specifics to encode: unified-account margin model (vs Binance cross), different
  funding-interval metadata (some symbols 4h/1h — normalize to 8h-equivalent APR in the
  carry ranker), position-mode setting pinned one-way, API rate-limit map, testnet base
  URL for the S0 dry-run phase.
- Verification bar: identical to LIVE_CONNECTOR_SPEC §7 (property tests, mutation ≥90%,
  breaker report, failure injection, e2e dry runs) — risk-path code, built fresh.

## 2. Book split & sizing
- Post-Gate-0 target: carry book splits across venues by funding-adjusted EV, hard cap ≤60%
  of live capital on any single venue (counterparty rail — additive, never loosened live).
- Per-venue free-capital sizing (07-13 incident class stays fixed per-venue); per-venue
  depth guard; per-venue venue-side reduce-only protective stops per connector spec §3.

## 3. Risk-rail integration (all additive)
- Dead-man: venue-equity measure becomes SUM of per-venue equities, each computed by the
  same audited formula; a single-venue read failure marks that venue STALE (pager) rather
  than zeroing it into the sum — the 07-19 measurement-artifact class must be impossible
  by construction here.
- Reconcile guard, fill-based accounting, kill switch: instantiate per-venue; global kill
  flattens both.
- New tripwire: cross-venue NAV divergence >X% (X calibrated in Gate-0 data) pages.

## 4. New signal axis (research, free)
- Cross-venue basis/funding spread (Binance vs Bybit perp funding + mark divergence) logged
  from the recorder + funding collectors NOW; enters the gauntlet as a cross-sectional
  family per founders-directive #4 — never a single-name bullet.
- Genealogy: exchange-native, license-clean, reconstructed in-house.

## 5. Gates & sequencing
1. Gate 0 completes on Binance (unchanged, blocking).
2. Bybit connector built to §1 bar + testnet dry-run ≥1 week clean.
3. Gate-0-equivalent micro-allocation on Bybit ($100-200, venue-minimum notional) before
   any book split.
4. Full-panel pre-mortem (PANEL_MISSION=premortem) before Bybit live keys — same as
   Binance go-live rule. Keys: principal-placed, trade-only, withdrawal-disabled,
   IP-whitelisted.

## 6. Explicitly out of scope
- No new venues beyond Bybit until this one carries live evidence (one counterparty-tail
  kill at a time). No cross-venue ARBITRAGE execution (latency game we lose) — the spread
  is a SIGNAL input and diversification lever, not a race.
