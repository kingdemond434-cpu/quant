# MT5 DATA MOAT NODE — spec (principal blueprint, 2026-08-25)

Claimed under RESEARCH §2 (self-footprint moat, master 32) and LAWS L1.11. **Public data
discovers hypotheses; the continuously accumulated private MT5/Fusion tape makes them
irreproducible.** Years are the actual moat: 2029 cannot re-record 2026. The recorder therefore
outranks any deferrable build the day it is proposed.

## Topology (target)

Machine A = execution/money path (sterile; minimal cache). Machine B = **Moat Node** — the
Contabo Windows box records reality 24/7 and never decides trades. Machine C = Linux research
box reads Silver/Gold. Machine D = independent backup domain; three copies of Bronze is the
target. One-way flow only: execution emits sanitized telemetry INTO the store; the store never
holds credentials able to place trades (LAWS §4 secrets law). Interim reality: Machine B
currently also hosts the shadow/gateway — acceptable to start recording TODAY; separation is the
build-out direction, and the recorder must never contend with the money path (low priority I/O,
disk guard).

## Storage: three immutable levels

- **BRONZE — untouched truth, append-only, never edited**: `bronze/mt5_ticks/` (per symbol/day),
  `bronze/mt5_dom/`, `bronze/symbol_specs/`, `bronze/execution/`, `bronze/terminal_health/`,
  `bronze/macro/`, `bronze/reference_markets/`.
- **SILVER — normalized** (universal ticks, spreads, execution events, sessions, specs).
- **GOLD — proprietary research state** (features, regimes, cost surfaces, latency surfaces,
  survivor states, execution models, habitat models). Every Gold artifact answers "which raw
  bytes produced me": feature_id, version, code_hash, bronze_inputs, creation ts, PIT cutoff,
  schema_version. Old backtests stay reproducible; schema-migration tests keep old Bronze
  readable forever; DR drills prove a dead recorder rebuilds from checkpoints without loss or
  duplication.

## Release 1 (recording starts NOW — `desks/mt5/moat/moat_recorder.py`)

1. **Every Fusion symbol's ticks** — universe discovered dynamically each cycle
   (`symbols_get()`, registry not hardcode), collected INCREMENTALLY via `copy_ticks_range`
   with per-symbol cursor checkpoints (not `symbol_info_tick` polling); fields: time, time_msc,
   bid, ask, last, volume, volume_real, flags + local receive UTC + local monotonic.
2. **Spread/mid** derivable from Bronze ticks (Silver job, not recorder work).
3. **Symbol specification history** — daily snapshot + immediate on-change (hash of full
   symbol_info): contract size, tick size/value, digits, volume min/max/step, margins, stops and
   freeze levels, swaps + triple-swap day, sessions, filling mode, status. Point-in-time
   contract mechanics prevent backtesting today's spec against yesterday's market.
4. **DOM wherever Fusion exposes it** (`market_book_add`/`get`), labeled honestly as
   broker-local observation, never "the market".
5. **Server/feed health** — terminal_info state, connect/disconnect, missed intervals, sequence
   gaps, terminal restarts, recorder restarts.
6. **Clock audit** — broker-server timestamp vs local UTC vs local monotonic skew recorded every
   cycle; bad clocks silently ruin lead-lag and execution studies.
7. **Disk guard** — recorder pauses LOUDLY below free-space floor (the bybit 16GB/37GB lesson);
   pausing is logged as an anomaly, never silent.

## Release 2+ (in priority order)

**Execution-truth database** (every order: decision/send/response timestamps, bid/ask at each,
requested vs filled, slippage, commission, swap, retcode, latency, strategy/signal/hypothesis/
survivor ids, regime id, feature snapshot hash — Tier-3-adjacent: wired into the money path only
via the catchable-change law L1.38, never by the recorder). **Rejected/cancelled/requoted/
partial/modification events** — conditioning on successful execution is selection bias.
**Survivor decision states** — every evaluation including TRADE=false with reason; the decision
surface, not the trade history. **Champions shadowed forever** — retire capital, never
measurement; the graveyard becomes longitudinal science (resurrection, seasonality, crowding,
structural breaks). **Survivor Genome Archive** — permanent hypothesis identity (mechanism
family, parents, provenance, code hash, prereg, verdicts, forward/promotion/retirement states);
never delete failed candidates. **Survivor habitat model** — what predicts survival; validated
out-of-time so it learns alpha fertility, not our biases. **Cost surface**
f(symbol, session, vol, spread, order type, size, direction, event proximity, liquidity,
holding) replacing any flat cost constant. **Latency surface** across tick→decision→submit→
response→fill. **Fusion weirdness database** (`bronze/venue_events/`): spread flashes, stale
quotes, reject clusters, swap/spec anomalies, session distortions. **Reference markets + macro
vintages** (futures refs, rates, vol indices, calendar vintages, corporate/reference-event
vintages — revision-aware PIT), for lead-lag/basis vs the Fusion tape. **Point-in-time
account/broker state** (margin rules, leverage tier, equity, commissions, account mode,
server). **Self-footprint dataset** once size grows: market before us → our order → response →
post-fill drift → impact/adverse-selection/capacity estimates.

## Laws binding the node

Append-only Bronze; lineage on everything; one-way movement around the money path; recorder
never trades; clock provenance (L1.46) on every row; a recorder outage is a PAGED anomaly and a
permanent gap-record, never silence (WS-005); the node's coverage (symbols recorded / symbols
available, uptime, gap count) is a ratcheted floored metric from day one (L1.0/L2.0).
