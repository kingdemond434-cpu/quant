# CANARY SEARCHES — ecosystem-change early warning (Charter §21)

> **UNIVERSE RETARGETED 2026-08-18, header added 2026-09-05.** Searches seeded before 2026-08-18 canary the retired crypto-exchange ecosystem. A canary that watches a ground the desk no longer hunts reports nothing useful -- re-seed against MT5/Fusion grounds rather than re-running these.
>
> Nothing below is deleted: a row recording what was tried, graded or exhausted on the retired
> desk is exactly the knowledge that stops a future session paying for the same thing twice. But
> it is a RECORD, not a queue. Every new row runs against the MT5/Fusion Markets universe -- FX
> majors/crosses/exotics, metals, equity indices, energy, softs, US share CFDs and the crypto CFDs
> Fusion itself lists. **No crypto-exchange venue may be hunted, screened or scored again**
> (`docs/LAWS.md` S1); crypto reference data is admissible only where a specific reading informs a
> Fusion-executable instrument, never as a universe of its own.

_A small representative set of searches re-run each digging session (cheap, minutes). An
UNEXPECTED shift in results — repo counts, API behaviour, maintainer activity, publication
rate, doc structure — triggers broader targeted rediscovery BEFORE the normal cadence.
Baselines re-stamped whenever a shift is investigated (resolved = new baseline)._

**STATED CADENCE (tightened 2026-07-26, prose made to match the clock rather than the reverse):
re-run at the START of every digging session AND at least every 4 DAYS, whichever comes first.**
The original wording — "each digging session" — silently inherited the BIWEEKLY digging cadence
(ledger `2026-07-18-digging-cadence-biweekly`), i.e. a 14-day promise, while §36 was holding this
file to 4 days. Measured this cycle before choosing which side to move: the whole set runs from a
shell in **under 90 seconds** (6 of 9 canaries are single HTTP calls), so the cheap side is the
honest side and the 4-day clock stands. Enforced by `max_audit._PRODUCER_CADENCE` against the last
COMMIT of this file, so re-running without committing the result earns nothing.

## Canary set — seeded 2026-07-19 (one per major ecosystem; keep <=10 total)

| # | canary | ecosystem | baseline (2026-07-19) | watches for |
|---|--------|-----------|----------------------|-------------|
| C1 | GitHub search: `funding rate arbitrage` (repos, sort=updated) | EN GitHub | record count + top-5 on first run | new frameworks/searcher-bot waves |
| C2 | Gitee Explore: 量化交易 trending | CN OSS | record on first run | CN ecosystem shifts, migrations |
| C3 | data.binance.vision index reachability + tree shape | exchange archives | reachable, current tree | archive deprecation/expansion |
| C4 | Binance futures API changelog page | venue APIs | last-entry date on first run | endpoint deprecations (feeds API-watch) |
| C5 | arXiv q-fin new-submissions rate (7d count) | academia | record on first run | publication-velocity spikes |
| C6 | Hummingbot + Freqtrade commit velocity (30d) | EN OSS frameworks | record on first run | maintainer abandonment/acquisition |
| C7 | Naver search: 펀딩비 차익거래 (result mix) | KR web | record on first run | KR retail-quant emergence |
| C8 | CryptoQuant/Glassnode free-tier scope page | vendor free tiers | record on first run | free-tier expansion/contraction |
| C9 | keyless `eth_getLogs` over a 700-block range across the `data_registry.json` `eth_public_rpc` chain + the MEV-relay set | free RPC ecology | baseline 2026-07-26 (below) | free-tier enclosure; a registry fallback chain that no longer falls back |

C9 added 2026-07-26 on the explicit request in improvement_inbox #58 ("add an RPC capability probe
to canary_searches.md per charter §21 — this ecology shifts every few months and the desk should
notice BEFORE a collector breaks"). It is the only canary that guards a LIVE data path.

Each digger session: run its region's canaries, log PASS/SHIFT one-liner in its session notes;
SHIFT -> targeted rediscovery same session + note here with date.

## Run log

### 2026-07-26 — first real re-run since seeding (7 of 9 canaries executed; baselines now numeric)
Seeded 2026-07-19 with "record on first run" placeholders and never re-run — so until today the
baselines did not exist and no shift was detectable in principle. Results:

| # | result 2026-07-26 | vs baseline | verdict |
|---|-------------------|-------------|---------|
| C1 | GitHub repo search `funding rate arbitrage`: **total_count 229**; top-5 by pushed_at all within 3 days (Colin503/dashboard_funding_rates, Stevensu7/hyperliquid-spot-perp-monitor, MilaArtyNew/carrypilot, mrenoon/boros-crossex-terminal, ethduke/dex_funding_rate_arbitrage) | first numeric baseline | PASS (see note A) |
| C2 | Gitee search: HTTP 200 but a **849-byte JS SPA shell** — no server-rendered results | not machine-readable | UNMEASURABLE (see note C) |
| C3 | data.binance.vision: HTTP 200; S3 listing intact, top-level tree = `data/futures/`, `data/option/`, `data/spot/` | tree shape unchanged | PASS |
| C4 | Binance derivatives change-log page: **HTTP 202, 0 bytes** — JS/WAF-gated from this host | not machine-readable | UNMEASURABLE (see note C) |
| C5 | arXiv q-fin: **25 submissions in the trailing 7 days** (newest indexed 2026-07-23 — the API lags ~2-3 days) | first numeric baseline | PASS |
| C6 | 30-day commit counts: hummingbot **`development` 216**, hummingbot **`master` 0**, freqtrade **236** | first numeric baseline | PASS — but the canary was mis-specified (note B) |
| C7 | Naver `펀딩비 차익거래`: HTTP 200, 480,627 bytes returned | reachable; result-mix unscored | PARTIAL |
| C8 | CryptoQuant + Glassnode pricing pages: HTTP 200 both | reachable; scope text is JS-rendered | PARTIAL |
| C9 | keyless 700-block `eth_getLogs`: **flashbots OK** (accepted without error); **publicnode / llamarpc / cloudflare-eth / 1rpc / mevblocker → HTTP 403**; **ankr → "Unauthorized: you must authenticate"**; **eth-pokt.nodies → "block range too large, max 250"** | first baseline | **SHIFT — CONFIRMS improvement_inbox #58 independently** |

**Note A (C1) — an ecosystem tilt worth naming, not just a count.** 3 of the 5 most recently
pushed repos are DEX/perp-DEX-side (Hyperliquid spot-perp monitor, a cross-exchange Boros terminal,
a DEX funding-rate arb) rather than CEX carry. That is the same direction as the desk's own
small-capital item #52 (incentive-aware venue routing on perp DEXes). Not actionable alone — logged
so the next reading can tell a trend from a snapshot.

**Note B (C6) — the canary itself was wrong, and it would have cried wolf.** Measuring
hummingbot's DEFAULT branch reads **0 commits in 30 days** and looks exactly like maintainer
abandonment, which is precisely what C6 watches for. The truth is that hummingbot develops on
`development` (216 commits, last 2026-07-24); `master` last moved 2026-06-16. **C6 is hereby
re-specified to name the branch per repo** (hummingbot → `development`, freqtrade → default).
Recorded rather than quietly fixed: a canary that fires on its own measurement artifact is worse
than no canary, because the first false SHIFT trains the desk to ignore the next real one.

**Note C (C2/C4) — two canaries are not machine-readable from this host** (Gitee returns a JS
shell; Binance's change-log is WAF/JS-gated, HTTP 202 with an empty body). They are NOT quietly
dropped: they are marked UNMEASURABLE with the observed HTTP evidence, and each owes a scriptable
replacement — C4 → the versioned REST `/fapi` error/weight surface or the announcement RSS;
C2 → a Gitee API endpoint or a specific repo's commit feed. Owed by the next run.

## Shift log

- **2026-07-26 — C9 (NEW), free-RPC ecology: SHIFT confirmed, second independent observation.**
  The `data_registry.json` `eth_public_rpc` fallback chain does not fall back: publicnode,
  llamarpc and cloudflare-eth all return HTTP 403 to a keyless 700-block `eth_getLogs` from this
  host, and ankr now demands authentication outright (free tier gone). This independently
  reproduces improvement_inbox #58, which probed the same chain on 2026-07-25 from the VPS — two
  hosts, two days, same verdict, so it is an ecology change and not an IP-reputation blip.
  DIFFERENCE WORTH RECORDING: #58 reports `rpc.mevblocker.io` serving >=700-block ranges keyless;
  from THIS host it returned 403, so the working keyless set is narrower than #58 states —
  `rpc.flashbots.net` alone, and even there the call returned 0 logs, so treat "no error" as
  acceptance, not as verified coverage, until a filter with known-nonzero results is used.
  IMPACT: `balanceOf`-at-latest still works, so the live `onchain_flows.py` collector is
  unaffected; any EVENT-based or backfill collector built on the registry chain would fail
  silently. ACTION OWED (tracked, not left here): update `data_registry.json` `eth_public_rpc` to
  the probed reality — a registry that records a dead fallback chain is worse than one that
  records none, because it stops anyone from looking.

### 2026-08-02 — the canaries became an ORGAN (`scripts/run_canaries.py`)

Until today this file promised a 4-day cadence that **nothing executed**. Nine cheap HTTP checks,
run by whoever remembered — the same "cadence by LLM memory is a reliability hole" that
`run_cadence`'s own docstring names, and the same shape the gap-register re-rank had until this
cycle. The file's own 07-26 entry says it plainly: seeded 07-19 and never re-run, so "the baselines
did not exist and no shift was detectable in principle."

`scripts/run_canaries.py` now runs all nine every cycle, extracts the ONE tracked quantity per
canary (a diff over a whole page is noise; a diff over a measured number is a signal), and keeps
its machine baseline in `data/canary_history.jsonl` rather than parsing this prose — otherwise
reformatting the document would register as a detected shift.

**Result from the Claude Code container: 0/9 reachable.** Recorded as UNREACHABLE, never PASS —
"we could not look" and "we looked and nothing moved" are opposite facts, and a shift detector that
conflates them reports its own blindness as ecosystem stability.

| # | status | cause |
|---|--------|-------|
| C1, C5, C6 | BLIND | HTTP 403 from the agent proxy |
| C2, C3, C4, C7, C8, C9 | BLIND | tunnel connection refused |

One real fix came out of the attempt: the first version used `certifi` and got
CERTIFICATE_VERIFY_FAILED on hosts the proxy could actually reach, because this environment
terminates TLS at a proxy whose root is not in certifi. The organ now prefers `SSL_CERT_FILE` /
`REQUESTS_CA_BUNDLE`. Left uncorrected, that would have been a **self-inflicted blind spot reported
as an ecosystem fact** — the canary equivalent of the frozen-grid coverage bug.

**This entry does not claim a shift check happened.** It records that the duty is now executable
and that this environment cannot execute it. The nine canaries produce real baselines on the VPS,
where egress is open — the same box, and the same reason, as the recorders.

### 2026-08-19 — the run record moved to the organ's artifact; two welded verdicts un-welded

**Governance repoint.** §36 held THIS FILE to a 4-day commit cadence while the actual run duty
had been an organ since 08-02 — and the organ's record, `data/canary_history.jsonl`, was
**gitignored evidence**: runs on 08-09 and 08-18 sat invisible to a fence that measures commits,
so the file read "16d stale" 19 hours after a real run. The history file is now git-tracked and
`max_audit._PRODUCER_CADENCE` measures **it** at the same 4-day bar (nothing loosened — same
clock, truer subject). This file keeps the canary SET and the shift investigations, which are
event-driven, not cadenced.

**Two verdict repairs (welded-ON canaries carry zero information, L1.43):**
- **C9 was not asking its own question.** The doc says "keyless `eth_getLogs` over a 700-block
  range"; the implementation POSTed `eth_blockNumber` and tracked the **head** — a number that
  advances every ~12s, so C9 read SHIFT on literally every run. It now runs the real 700-block
  `getLogs` and tracks a **categorical** acceptance verdict (`ok` / `range-capped` /
  `auth-required` / `denied`) — the taxonomy of the 07-26 shift log — so SHIFT now means the
  acceptance **policy** moved.
- **Count canaries get a 10% spike band.** C1/C5-style totals grow a little every day, so
  exact-string compare made any re-run a SHIFT. The doc's own vocabulary is "publication-velocity
  **spikes**": `key=<int>` values now SHIFT only on a >10% move since the last look.

**Latest organ readings (08-18 VPS run, re-read under the new semantics):** C1 `total_count`
238→249 (+4.6%, within band — the DEX-ward tilt watch from 07-26 continues, no spike);
C5 2324→2330 (+0.3%, within band); C9's old "SHIFT" was the welded head, carrying nothing.
C3/C6/C8 stable; C2/C4/C7 unreachable from container hosts as documented. 2026-08-19 container
re-run: C1/C3/C6/C8 reachable and stable, no shifts; C9 blind from this host (403 — the VPS
answers the live-path question).
