# DEEP SWEEP SYNTHESIS — 2026-08-01

*Synthesis lead. Inputs: 9 subsystem audits dated 20260801 (11,206 lines). Every number below is
either quoted from an auditor with its proving command, or re-verified by me — re-verified claims
are marked **[SL-verified]** with the command I ran.*

**STATUS: COMPLETE.** All nine reports read in full (11,206 lines). Sections A–G complete; six
load-bearing claims independently re-verified by me against the live system (two came back *worse*
than reported); TIER1_BENCHMARK re-graded in-session (10 rows, 8 downgrades, all four T1s cut);
portfolio rowed R0232–R0246; principal page updated with 3 human acts and **1 purchase cancelled**.

---

## SL-VERIFIED FACTS (re-run by the synthesis lead, not taken on report)

The synthesis's job is to adjudicate, so I re-derived the load-bearing claims from the live system
rather than trusting nine reports. Six checks, all confirming — two of them **worse** than the
auditor stated.

**SL-1 — the campaign discards 82.86% of its own observations. [CONFIRMED, exact]**
```
$ .venv/bin/python -c "import pickle,pathlib,numpy as np; d=pickle.loads(pathlib.Path('_audit_prepared.pkl').read_bytes()); \
  lens=np.array([len(t[-1]) for t in d]); print(len(d), lens.sum(), 310*len(lens), np.percentile(lens,[0,25,50,75,100]))"
420  759444  130200  [ 310.  845. 2134. 2382. 4594.]
```
420 candidates hold **759,444 observations**; the campaign truncates every series to the shortest
(`min_len = 310`) and tests on **130,200**. The median candidate has **2,134** observations and is
judged on 310 — **13% of its own history**. Alpha-discovery's "82.9%" is exact.

**SL-2 — stratifying by history depth drops the hurdle 2.6× on 57% of the pool. [CONFIRMED, computed]**
Splitting alpha five ways across depth bands (a *more* conservative multiplicity treatment) still
collapses the bar, because T enters as √(T−1):

| band (obs) | n | median T | hurdle annual SR |
|---|---|---|---|
| flat design (status quo) | 420 | 310 | **3.99** |
| 310–400 | 42 | 381 | 3.42 |
| 400–700 | 42 | 513 | 2.95 |
| 700–1,500 | 70 | 1,098 | 2.09 |
| **1,500–3,000** | **238** | **2,358** | **1.55** |
| 3,000–5,000 | 28 | 3,896 | 1.04 |

The modal band — **238 of 420 candidates, 57% of the pool** — faces **1.55** instead of ~4–5.
A 1.55 annual-Sharpe bar is one real crypto alphas clear. The desk's own certification records
`underpowered_below_annual_sharpe: 5.0` and `power(true SR 2.0) = 0.0025`. **The 420/0 record is
manufactured by testing 57% of the pool on 13% of its history.**

**SL-3 — the module that fixes SL-2 has ZERO callers. [CONFIRMED — worse than reported]**
```
$ grep -rn "campaign_window" --include=*.py . | grep -v "/.git/\|/data/rollback/\|__pycache__"
tests/validation/test_campaign_window.py:6:from libs.validation.campaign_window import (
tests/validation/test_campaign_window.py:104:    from libs.validation.campaign_window import Stratum
```
Alpha-discovery reported this as "blocked only by an `alpha=` kwarg no call site passes." It is
worse: **there are no call sites.** The only two references in the repository are inside its own
unit test. This is the §42 orphan pattern verbatim — *"Unit tests are what make this invisible:
they prove the mechanism works and say NOTHING about whether anything runs it."*

**SL-4 — the certifier reports BLOCKED on an input that is on disk and loads. [CONFIRMED]**
`reports/gauntlet_certification.json` says the real-cohort half *"stays blocked on a builder for
_audit_prepared.pkl (3 readers, 0 writers)."* The file exists at repo root, 6,100,907 bytes, loads
in one line, and contains exactly the 420 real candidates (SL-1). `certify_gauntlet.py:59` already
points at it. The certification is **self-blocking on a file it can already read.**

**SL-5 — two conversion instruments disagree on the same ledger, and max_push reads the lenient one. [CONFIRMED]**
```
$ .venv/bin/python scripts/check_conversion.py
conversion fence (L1.28b): REPAIR-MODE -- 155 rows in backlog (0 past due, oldest 5.66d); last 7d: 231 raised vs 76 dispositioned
$ .venv/bin/python scripts/recommendations.py report
recommendations: 231 total | 71 implemented | 5 rejected | 62 scheduled | 78 open
  DEFECT [UNDISPOSED past grace] R0067 ... R0068 ... R0069
  DEFECT [SCHEDULED past due]    R0002 (5.7d) R0020 (3.5d) R0025 (3.3d) R0043 (2.0d) R0058 (1.4d) R0062 (1.4d)
```
**`past_due: 0` vs nine named DEFECTS.** Arrival/service ratio **231/76 = 3.04**. `done`(14) +
`screened`(1) = **the 15 immortal rows** meta named, exactly.

**SL-6 — the live credential is a placeholder string. [CONFIRMED]**
```
$ cat data/secrets/binance_live.json
{"key": "claude setup-token", "secret": "claude setup-token"}
```
Launch-readiness's "the launch is a NO-OP" is literally true at the credential layer. **Only the
principal can fix this** — it is a hard wall, not work (see §D).

Supporting, same method: `check_replacement_rate` → `UNMEASURED-BIRTHS ... 12 live forward clock(s)
occupied of 12`; `check_exploration` → `DARK -- 2 never produced`; `check_ratchets` →
`miner_seats_productive 9.1%` (largest gap on the board); no `delisted`/`survivorship` handling
exists anywhere in `libs/` or `scripts/`; crontab is 144 lines and seats use `flock -n`, so a held
lock is a **silent** skip.

---

## (A) OVERALL VERDICT + CEILING TABLE

### The verdict

**Every one of the nine seats scored itself DOWN this week, and every one of the nine says the
drop is measurement, not decay. That claim is true, it is the single best thing that happened
this week, and it is only available once.**

What actually changed is that the desk's *instruments* got honest faster than its *machinery* got
better. Seven seats now publish a carry table (adoption 1/8 → 6/7), and the carry tables are what
made falsification visible: four load-bearing assumptions behind last week's meta score were
falsified in one day; validation retracted its own K4 after finding the leak protection inert;
data-moat retracted its own flagship "irreplaceable" claim; infrastructure corrected its own prior
number by 10×. A desk that can refute its own headline results in one cycle is working.

But the underlying machine did not move, and the reason is now measured rather than felt:

> **Detection is running at ~166 findings/cycle (+57% in one cycle). Repair is running at 15.2%
> closure. Arrivals 33/day against dispositions 10.9/day, ρ ≈ 3. Of the 6 rows that came due on
> their first-ever due date today, 0 converted.** [SL-5, meta M1/M4/M17]

That is not a motivation problem and exhortation will not touch it. At ρ ≈ 3 a queue does not
drain; it diverges. **This week's finding is that the desk's binding constraint has moved off
discovery entirely and onto conversion**, and three of the nine seats reached that conclusion
independently from different evidence (meta M17, execution E19, launch §9).

The second cross-cutting fact, which no single seat could see and which reorders the whole
portfolio, is in §B.

### The honest ceiling map

| subsystem | now | 07-31 | ceiling | gap | opportunity cost / 1y | why it moved |
|---|---|---|---|---|---|---|
| **research-engine** | **22%** | — | 80% | 58 | **largest on the desk** — 7 languages × 365d of archaeology forgone | 1/11 seats productive (9.1%, SL-verified); 0 new mechanisms 14d; memory 100% write-only |
| **validation-stats** | **26%** | 58% | 85% | 51 | **the whole funnel** — 0 admits in the gate's life | N22: purge/embargo inert; N23: Sharpe 4.135× overstated; 3/11 gates zero-information |
| **alpha-discovery** | **30%** | 35% | 88% | 58 | highest after launch | 0.25% power/candidate; 82.86% of obs discarded (SL-1); 3 refill paths blocked |
| **launch-readiness** | **31%** | 38% | 95% | 64 | **largest, asymmetric both ways** | launch is a no-op (L4/L9); key is a placeholder (SL-6); S1 sizes to 4× |
| **execution-growth** | **31%** | — | 85% | 54 | one year of un-attributable evidence | 2 repro'd order-path defects; governor inert in the running process; 1.15% tape coverage |
| **data-intelligence** | **31%** | 36% | 85% | 54 | **very high** — a contaminated panel taxes every future study | DI-28 survivorship (SL-verified); DI-31 zero backups; both instruments confidently wrong |
| **data-moat** | **52%** | 55% | 85% | 33 | high; **one item has an expiry** | flagship "irreplaceable" claim REFUTED; backup inert and self-greening |
| **meta-blindspots** | **52%** | 58% | 85% | 33 | ~85% of 8 seats' output converts to nothing; 11,728 bps aging | "scheduled" converts 0/6; retraction reached 1 of ~45 sites |
| **infrastructure** | **54%** | 62% | 92% | 38 | very high, 3 tails: security / capital / permanent loss | 11 fences green on absent input; live RCE path; capital fence divides a number by itself |
| **composite (9)** | **36.6%** | **48.9%**¹ | **86%** | **49** | — | ¹comparable 7-seat set: 48.9 → 39.4, **−9.4 pts** |

**Read the composite as a measurement correction, not a decline — once.** I am logging that as a
falsifiable forecast rather than an assurance: **if next week's composite falls again on
"measurement correction" reasoning, the correct reading flips to decline.** (L1.29 forecast:
composite ≥ 39% on 2026-08-08, confidence 0.6.)

### TIER-1 BENCHMARK RE-GRADE — applied to `docs/research/TIER1_BENCHMARK.md` this session

The register and this table must never disagree silently. Nine of its rows moved on this week's
evidence, and **eight of the nine are downgrades**. Before the detail, the mechanism that makes
this the highest-leverage edit in the report:

> `run_max_push.py:279-285` queues **only rows scoring < 1.0**. A row graded **T1 is silently
> removed from the desk's daily work queue.** [meta M15]

So the four T1 rows were not merely flattering — **they were de-queuing four entire layers**, and
three of them are the layers this sweep found most broken. Over-grading here is not a reporting
error; it is a work-suppression mechanism.

| layer | was | now | evidence for the move |
|---|---|---|---|
| `validation_methodology` | **T1** | **T3** | N22 purge/embargo inert (`.train` referenced 0 times; cpcv fraction identical to 6dp across a 250× parameter range); N23 `_PERIODS_PER_YEAR = 24*260` on daily bars = 4.135× overstatement; 3 of 11 gates carry zero information; certification is 2 targets × **1 seed** |
| `self_audit_layer` | **T1** | **T2** | M15: the grade cites "planted controls" — `grep -rn "plant" scripts/max_audit.py scripts/run_deep_sweep.py` → no output. They do not exist |
| `research_governance` | **T1** | **T2** | L2.3's third disposition converts 0/6 (M1); the two push/CI-blocking fences are substring whitelists with unreachable failure states (M16b); 15 rows park in a status the tooling cannot write |
| `llm_native_automation` | **T1** | **T3** | `miner_seats_productive` **9.1%** — 10 of 11 seats fully configured, credentialed, unit-tested, and producing nothing; the frontier seat's `exit $?` swallow reports `Result=success` on 7 failed digs |
| `monitoring_observability` | T2 | **T3** | pager at ~29% precision (2 of 7 standing CRITICALs provably false, 1 structurally incapable of being true); 11 fences exit 0 on absent input; no time-series store exists at all |
| `security_opsec` | T3 | **T4** | anonymous off-box fetch of the full research web root returns desk content, not a login page; push-capable PAT live in `remote.origin.url` and provably leaked to LLM vendors; deploy gate executes fetched code **before** deciding to trust it |
| `data_moat` | T2 | **T3** | its stated closer was "backups/moat replicas live (run_moat_backup)" — that organ replicates a 0-table database and its drill hashes the replica against **itself** |
| `data_engineering` | T2 | **T3** | survivorship at the source (SL-verified: LUNA/UST/FTT/SRM all absent), 40% of the panel frozen 6 weeks, 5 non-crypto asset classes dark for 43 days unnoticed |
| `vol_surface_expertise` | T3 | **T4** | the only options dataset is a side-effect of the executor, forward-archive-only, 15 gaps > 24h in 35 days, ~1 obs/day |
| `forward_history_depth` | `time_bound: **yes**` | `time_bound: **no**` | **the most consequential single edit.** It was listed as a wall (calendar time). Two seats independently refuted it: 82.86% of on-disk observations are discarded by a one-line idiom (SL-1), and 345 days of free first-party L2 sit downloadable now. A wall that is actually a wiring job has been keeping the desk's highest-leverage fix out of the max-push queue |

Rows held: `risk_rails` **T2** (design is genuinely good; wiring is not — closer must now name
E15/E20/L6/G9), `execution` **T3**, `simulation_prod_parity` **T2** (but E17's connector-surface
gap belongs in its closer), `conversion_repair` **T2** — *on notice*: its closer is "dispositions
≥ arrivals for 30 consecutive days" and the measured ratio is 1:3.

## (B) CAPABILITY MAP

### The missing capability that unlocks the most: **a measured conversion path**

Not a new instrument — the desk has ~15. The missing capability is that **anything found gets
worked**. Every seat's top item is blocked behind the same queue, and the arithmetic (ρ ≈ 3,
closure 15.2%, 0/6 on first due date, 0/26 synthesis rows with a due date) says the queue cannot
drain by effort. Three sub-capabilities, all cheap, all measured-missing:

1. **One honest conversion meter.** Two exist and disagree; the work queue reads the lenient one
   (SL-5). Three one-line fixes: date compare on a `datetime` not a string; count `open` rows past
   grace; add `done`/`screened` to `_TERMINAL`.
2. **Admission control.** `repair_mode_line = 25` is arithmetically unreachable at ρ ≈ 3, so
   REPAIR-MODE is welded ON and carries no information. Replace the level trigger with a rate
   trigger. **Do not raise the line — that is the denominator trick.**
3. **Adjacency as a recorded fact.** "Implemented" currently means the named instance was fixed.
   R0051 is the proof: closed after 4 lines in 1 file; the refuted claim survives at ~45 sites,
   *including a module that routes research compute on it*.

**Highest-ROI multiplier, and it is a different thing from the above: measure the audit layer's
own recall `d` by planting defects (meta X1).** The desk plants controls to certify its alpha gate
(`positive_control.py`) and mutants to certify its tests (`mutation_score.json`), and has never
once planted a defect to certify its **audits** — the layer that finds everything else. Every
"we found N findings" on this page is a count with no denominator. One session, retroactively
re-prices every sweep the desk has ever run.

### The biggest bottleneck / greatest systemic risk if it fails

**The measurement layer itself, and it has already failed — silently, in eleven places.** This is
the sweep's dominant structural finding, reached independently by four seats:

- 11 fences map exactly one status string to a non-zero exit; `UNMEASURED` falls through to
  `else 0`. To cron, systemd and CI they are green while measuring nothing. [infra G28]
- `check_utilisation`'s `deployed_capital` divides `live_book_usd()` by a function whose first
  rung *is* `live_book_usd()` — ≡100% SATURATED forever, while `deployed_notional: 0`. [G0]
- `check_exploration` grades file **mtime**, not yield: an auth-failed hunt that proposed and
  built nothing turns its organ GREEN. [meta M6]
- `data_vitals._rows` reads the **oldest** 3000 rows of an append-only log and calls `max(ts)` the
  feed's freshness — error of 57,184 hours on one feed, and it goes permanently blind to any feed
  the moment that feed becomes valuable. [DI-1]
- `run_moat_backup`'s restore drill hashes the replica against **itself** and certifies a 0-table
  database as good. [DM8-1 / G29]

The class has a name now and it should be adopted desk-wide: **mtime-and-existence as a proxy for
work.** Three seats hit it independently in one day. Naming it is what makes it greppable — every
`stat()`-based and `.exists()`-based fence in the estate becomes a candidate.

**Why this outranks every alpha item:** the desk's entire operating model is "measure, floor,
ratchet." If the measuring devices report confident numbers while blind, the ratchet ratifies
fiction and every downstream decision inherits it. Both instruments the desk uses to see its own
data (`data_vitals`, `data_assets`) are wrong in ways that produce *confident* output.

## (C) PRIORITIZED PORTFOLIO

Ranked by **(direct + enabling + optionality + compounding) / (effort × maintenance × opportunity
cost)** — not by raw severity. ⚙ = compounding multiplier. These compete for one brain seat, so
the ordering is the product, not the list.

### THE ORDERING CONSTRAINT — read before the table

Three seats each found a defect that reads as "fix the instrument." Together they impose a
**sequence**, and the obvious order is the dangerous one:

- alpha-discovery: the gate cannot see (0.25% power) → *raise power*
- validation: the gate has **zero leak protection** anywhere in the live path (N22/N21), and
  reported Sharpes are **4.135× overstated** (N23) → *the measurements feeding it are wrong*
- data-intelligence: the **panel is survivorship-biased at the source** (DI-28) → *the input is
  contaminated*

**Raising the gate's power before fixing the panel and the leak converts a 100%-reject screen into
a powered detector of survivorship artifacts and leaked labels.** Right now the gate's
reject-everything behaviour is the only thing keeping contaminated candidates off forward clocks.
That is an accidental safety property, not a designed one — but it means the correct order is
**input → leak → measurement → power → re-certify**, and doing #4 first is the phantom-edge
factory this constitution exists to prevent. No single seat could see this; each owns one link.

### P0 — the money path, this session, in this order

| # | item | why first | effort | conf |
|---|---|---|---|---|
| **1** | **Restart `quant-cashcarry` BEFORE clearing the KILL file** [E15] | **[SL-verified]** PID 1626623 started 16:44:27; the guard fix landed 69 min later. The running process reads `generated`, the guard writes `ts` → parsed epoch 1970 → age 1.79e9 s → stale → **return early**. Guard orders `size_frac 0.0, limit_only`; the process holding the book runs full size, takers allowed. Masked only by the KILL file. **The masking ends at REARM**, and E1/E2 (fill-by-absence, partial-fill over-execution) release on the same tick | ~0 | 1.00 |
| **2** | **Add a profitability criterion to Gate 0** [E22] | The strategy about to be funded loses money in **every** hold bucket on its own realised tape — **[SL-verified]** `<2h −33.77bps · 2-8h −78.97bps · 8-24h −102.62bps · >24h −712.71bps` — while its backtest reports gates 10/10. Not one of the eleven launch criteria reads profitability, slippage or fee intensity. L1.4: reality outranks simulation | low | 0.95 |
| **3** | **Surface Binance error codes** (`{code,msg}` into the return dict; **append**, don't `write_text`) [L12/E3/G26] | Converts six other findings from silent to self-diagnosing, and is the cheapest. A naked leg opened 17 min before the infra sweep and the pager is structurally incapable of seeing it: `_ERR` is declared at `run_alerts.py:46` and **never read** | ~15 lines | 1.00 |
| **4** | **Copy the 3-line multi-asset equity fix to `binance_live.py:188`** [L10/E20] | The exact fix already exists at `binance_testnet.py:181-183`. Both files were edited the same day and the live one kept the old read. This is the read that valued a solvent book near zero, flattened it, and disarmed the dead-man on 07-30. Ranked #2 desk-wide on 07-31 and still undone | 3 lines | 1.00 |
| **5** | **Gate `_compounded_capital` on a live-inception boundary** [L19] | Seeds `stage: S1` → `_compounded_capital(200)` returns **800**, from *testnet* realised P&L, against a $200 deposit of which ~$100 is spot. Gate-0's capital cap is evaluated on the pre-multiplied number | small | 0.95 |

### P1 — the conversion capacity that everything else is queued behind

| # | item | why | effort | conf |
|---|---|---|---|---|
| **6** ⚙ | **Fix the two conversion meters + the 15 immortal rows** [M2/M3] | **[SL-verified]** `past_due: 0` vs 9 named DEFECTS, and `run_max_push.py:239` reads the forgiving one. Three one-line fixes. This meter gates repair-mode for the whole desk | hours | 0.95 |
| **7** | **Drain the six P1 rows and measure what it costs** [X4] | The desk has never measured its own repair capacity μ. R0058 first (6,500 bps, *active data destruction*, scheduled, came due, untouched). Capacity before structure — building better finding infrastructure while 25 of 26 synthesis rows sit parked raises arrival into an already-unstable queue | 1 session | 0.9 |
| **8** ⚙ | **`!= "OK"` — eleven decorative fences become real** [G28] | One token. The model implementation is already in-repo at `check_law_families.py:143`; it fixes five of eleven immediately. Add exit-code assertions to the fence test template — asserting the *status field* and never the *exit code* is why this survived | low | 0.95 |
| **9** ⚙ | **Measure audit recall `d` by planting defects** [X1] | Retroactively converts every sweep from a count into an estimate; gives `unknown_unknown_score` its first estimator; resolves L1.43's quiet-detector ambiguity. Hold out 4 of 12 planted defects as an unseen set or `d` inflates | 1 session | 0.85 |
| **10** | **Re-grade `TIER1_BENCHMARK.md`** (done this session, §A) | A T1 grade de-queues the layer from max-push. Four layers were being suppressed. Minutes, and it makes 8/9/6 self-sustaining | minutes | 0.9 |

### P2 — the discovery instrument, IN THE ORDER ABOVE

| # | item | why | effort | conf |
|---|---|---|---|---|
| **11** ⚙ | **Point-in-time universe: persist `exchangeInfo` daily, all statuses** [DI-28] | **[SL-verified]** LUNA/UST/FTT/SRM absent; 279 symbols all selected on *today's* liquidity then backfilled 7 years. **The exchangeInfo call is already made on every ingest and thrown away.** The validation stack is blind to it because it corrupts the input panel, not the test. **Precondition for #14** | low | 0.9 |
| **12** | **Make the CPCV gate read the purged training fold — or delete the parameters and the docstring** [N22] | **[SL-verified]** `.train` referenced **0 times** in `_cpcv_positive_fraction`; the fraction is identical to 6dp across purge 0→500 and embargo 0→0.40. Combined with walk-forward at `embargo=0` and PBO having no purge/embargo/block: **no gate in the live path has any leak protection whatsoever** | small | 0.95 |
| **13** | **Fix `_PERIODS_PER_YEAR` (4.135×) and stop stripping zeros (1.0325×)** [N23/N23b] | Every reported daily Sharpe is overstated ~4.3× combined, persisted, surfaced, and used to rank rejects. Zero-stripping also breaks CPCV contiguity and the calendar index | ~1 line each | 0.95 |
| **14** ⚙ | **Wire the stratified campaign window** [alpha O1 / SL-2 / SL-3] | **[SL-verified]** the module is written, unit-tested, and has **zero callers** — its only two references repo-wide are in its own test. Stratifying lifts the modal band (238 of 420 candidates) from a ~4.0 hurdle to **1.55**. **Score it as a power fix, never as a yield forecast** (§E-1). **Must not precede #11–#13** | ~1 week | 0.9 |
| **15** | **Run the real certification + write the gate-power artifact** [N1/N2/E1] | The 8×12 harness exists with zero production callers; the live artifact is 2 targets × **1 seed**, and nothing below SR 3.0 has ever been tested. N2's numbers exist **only in a git commit message** — the one place no fence, ratchet or future audit will look | ~1h compute | 0.95 |
| **16** | **Unblock the three refill paths** [alpha F6/F7/F8] | H8 unreachable (dedup hash omits timeframe); universe capped at 10.8% by `limit=30` → 3,486 candidates excluded at zero acquisition cost; resurrection feeder selects zero until 2026-08-10 by arithmetic. Three trivial fixes; each is why `tested=0` looks like a fact about crypto | trivial ×3 | 0.9 |

### P3 — moat, durability, security

| # | item | why | effort | conf |
|---|---|---|---|---|
| **17** | **Back up the 7.4 MB that is actually irreplaceable — in one git commit** [G29] | Infrastructure corrected the prior figure by 10×: irreplaceable non-depth = **7,411,081 bytes**; depth ladders ~0.82 GB; the 6.12 GB Bybit tree is *not* irreplaceable (§E-4). **This supersedes the €4/mo Storage Box ask for everything except the depth ladders.** Fix the drill to hash the **source**, and make ABSENT fail rather than `continue` | low | 0.9 |
| **18** | **T7: probe whether the free 345-day L2 archive is on rolling retention — 2026-08-08** | **The only item on the desk with a possible expiry.** One command, three HEAD probes. If rolling, every day of delay destroys a day of free history permanently and #19 becomes time-critical | 1 command | — |
| **19** ⚙ | **Claim the free 345-day Bybit L2 backfill as FEATURES, not bytes** | 200 levels vs our 25, 100 ms vs 4,080 ms, 345d vs 10.6d — free, first-party, §13-clean, and **already in our own universe map at `status: queued`**. Raw does not fit (268 GB vs 23 GB free): stream → reduce to 1-min features → delete the zip (~1 GB parquet). Directly lifts the h≥5 horizon gate and the 4,268-obs power wall | large | 0.85 |
| **20** | **Security: Cloudflare Access + rotate the PAT + scratch-checkout the deploy gate** [G1/G2/G3] | Not risks — a **live disclosure** (anonymous off-box fetch returns desk content) and a working RCE into the box that will hold live keys. Access is dashboard-side and needs no deploy. Treat the PAT as already disclosed to every LLM vendor in the chain | operator + medium | 0.9 |
| **21** | **Propagate the kimchi/420 retraction to all ~45 sites** [M11] | The only meta item with a *direct* alpha path: `reject_rescore.py:4` is routing compute away from the 420 re-score on a refuted premise, and the graveyard has **three rows asserting kimchi survived and zero recording that it died** | 1 session | 0.95 |
| **22** | **One line ×2: point the liquidation readers at the file that exists** [DM8-10] | 50,301 rows, 22 days of a live service, read by nobody because both consumers read `.jsonl` and the file is `.parquet` — inside a swallowing `try:` | one line | 0.95 |

## (D) HARD WALLS

Genuine walls only. **Three things previously carried as walls are demoted below — that demotion
is worth more than the wall list itself.**

### Real walls — physical or external

1. **Crypto sample depth.** BTC perp history starts 2019-09-08; the 2017 top and the entire
   2018-19 bear are **missing**. 8 independent >25% drawdown episodes = **315 days per independent
   macro observation**. The common cross-sectional span across the panel is **7.3 months**. No
   multiplicity correction compensates for 8 macro observations. *(This is the honest replacement
   justification for the BitMEX decade programme — the one in its spec rests on a retracted
   number.)*
2. **Forward evidence takes calendar time.** 8h panels accrue √3×; otherwise one day per day.
3. **Real API keys and the deposit are human acts.** **[SL-6]** the live credential on disk is the
   literal string `claude setup-token`. Only the principal can fix this, and the launcher's `-s`
   non-empty skip test grandfathers the placeholder **forever** — so the file must be deleted
   first. → PRINCIPAL_ACTION.
4. **Binance USD-M futures must be separately enabled on the account** (quiz + agreement) — and
   nothing probes for it; the risk block is wrapped in `_safe()`, so if `/fapi/v2/*` raises, the
   ruin rail simply does not evaluate and **the book opens anyway**.
5. **One box, one disk, one region.** No RAID, no swap, 3.8 GB RAM shared between the money path
   and every research organ. `quant` has no sudo, so any launch-day restart needs a human who
   appears in no runbook.
6. **Deribit per-strike IV has no free history** — archived forward only. The 8.1 days in the two
   largest gaps are gone permanently.
7. **Raw L2 backfill does not fit**: 268 GB against 23 GB free. This bounds the *method*
   (stream-and-reduce), not the capability.
8. **`data/moat` depth ladders (~0.82 GB) are genuinely unreconstructable** at our own timestamps —
   ~10 months of forward recording to rebuild.
9. **The execution tape's denominator is unknowable retroactively.** Failures never reach the tape
   (`continue` before `_log_trade`), so every fill rate is over successes only, forever.

### Demoted — carried as walls, refuted this week

| was a "wall" | actually |
|---|---|
| `forward_history_depth` (`time_bound: yes`) | **a one-line idiom.** 82.86% of on-disk observations are discarded before any test runs [SL-1]. Re-graded in §A |
| "our L2 tape is irreplaceable" | **refuted.** Free first-party at 8× depth, 41× resolution, 345d vs 10.6d — and it was already in our own universe map at `status: queued` |
| "the second model family is a funding wall" | **not tested.** HTTP **400** is a request-shape / model-id error, not **402**. One call ever made, nobody read the request. A possibly-one-line fix sits behind an assumed budget wall |
| "compute / the frontier is the constraint" | **explicitly not.** With 2028 compute the desk would still hash hypotheses without a timeframe, cap the universe at 30 symbols, and have `ZWIN = {1:20, 5:12, 20:6}`. The frontier lens came back empty across three seats and that emptiness is the finding |
| "we need to buy data" | **no.** 9.16 GB on disk with 83.8% carrying one test; 1.1 GB of paid CME 85% unread; 3,486 candidates excluded by a default argument. No paid path is proposed anywhere in this sweep |

## (E) AUDITOR DISAGREEMENTS — adjudicated

**E-1 · Does fixing the campaign window unweld the gate? — alpha-discovery O1 vs validation N3/N7.
BOTH ARE RIGHT; validation wins the specific claim; the framing must change.**

Alpha-discovery: stratifying by history depth takes per-candidate power 0.25% → 37.9% and
E[discoveries] 1.06 → 159. Validation measured the actual data: at the max-observation window
(T=2109, N=266) **0 candidates are rejected** (min adjusted p 0.089); BH → 0; BY → 0; family-scoped
BH across 7 families → 0. Admitting the best of 266 needs q ≥ 0.372 (37.2% FDR) or m ≤ 35.7.

**Ruling.** My own computation on the production pickle [SL-2] confirms the hurdle drop is real
and large — the modal band (238 of 420 candidates, median T=2,358) faces **1.55** instead of ~4.0.
But **"E[d] = 159" is a power counterfactual that assumes every candidate is a true SR-2 alpha**,
which is exactly the assumption the 1.06 figure also carries. It is not a yield forecast, and
publishing it as one would be precisely the "maximise DECLARATION, not DISCOVERY" defect. Validation's
caveat is binding and I adopt it verbatim: *shipping the window fix without the multiplicity fix
reproduces today's 0-survivor result with more compute.* → **Ranked #14, framed as a power fix,
sequenced behind #11–#13.**

**E-2 · Is the gauntlet certification self-greening? — validation N1's numbers are STALE; N1's
finding survives. [SL-verified]**

N1 reported `targets: [10.0], seeds: 1, min_passing_true_sharpe: 10.0`. The live artifact reads
`targets: [3.0, 5.0], seeds: 1, floor 5.0`. Commit `baf342e` re-certified at **01:36:12**, after
the validation seat's read. **Ruling: the numbers are superseded, the substance stands and is
arguably worse** — 2 targets × **1 seed** against a written 8×12 harness with zero production
callers, `pass_rate` at SR 3.0 is **0.0**, and nothing below 3.0 has ever been tested. The desk's
entire realistic operating range (SR 1–2.5) remains unmeasured. Any document citing
`min_passing_true_sharpe = 5.0` as settled — including `GAP_REGISTER.md:94` and the BitMEX spec —
is citing a 1-seed result.

**E-3 · Is the certification blocked on a missing input? — the certifier is wrong; both auditors
right; two different mechanisms, both real. [SL-verified]**

`reports/gauntlet_certification.json` says the real-cohort half "stays blocked on a builder for
`_audit_prepared.pkl` (3 readers, 0 writers)". The file exists at repo root, 6,100,907 bytes, loads
in one line, holds exactly the 420 real candidates. Validation ran its entire N3 analysis against
it. **Ruling: the "no writer" claim is false.** Alpha-discovery's diagnosis (CWD-relative path +
gitignored → silently degrades to synthetic outside repo root) and validation's diagnosis (a
6-day-frozen, zero-writer, uncontracted input on 5 organs' decision path) are *different* defects
producing one symptom. Fix both: anchor the path to `_ROOT`, and put the input under a freshness
contract.

**E-4 · How much data is irreplaceable — 8.7 GB, 7.2 GB, or 7.4 MB? INFRASTRUCTURE IS RIGHT.**

Data-intelligence DI-31 treats the whole 7.2 GB moat as irreplaceable and asks for offsite backup.
Infrastructure G29 decomposes it: irreplaceable non-depth **7,411,081 bytes**; depth ladders
**~0.82 GB**; re-downloadable **~8.2 GB**, of which Bybit's 6.12 GB is refuted as a moat by the
data-moat seat's own cost-inversion test. **Ruling: adopt infrastructure's decomposition.** The
practical consequence is large and favourable — **the entire irreplaceable non-depth set fits in
one free git commit to a remote the desk already pushes to**, which supersedes the standing €4/mo
Storage Box ask for everything except the 0.82 GB ladders. Both seats agree on the thing that
matters: **there are currently zero verified copies, and the organ protecting them certifies an
empty replica as good.**

**E-5 · "The retrieval index is broken" — REFUTED, and acting on it would have rewritten working
code.** Research-engine F-12 and alpha-discovery F25 both indict the novelty gate. Data-moat
measured the similarity function directly: **recall@1 = 324/324 = 100%**. The defect is *corpus
scope and representation depth* — documents are titles only (median 10 tokens); 21,251 tokens of
statement/lessons sit unindexed; the richest store is outside the corpus entirely. **Ruling: fix
the corpus builder, not the matcher.** This also adjudicates alpha-discovery F25's correction to
research-engine's "J = 0.000 → 0.977" figure — F25 is right that the figure is same-document
self-similarity, not paraphrase retrieval, and the ledger correction is owed.

**E-6 · Did the alpha-discovery seat vanish? — NO. Meta's M17 fact 3 is stale.** Meta (02:38)
recorded 7 files with no `alpha-discovery` and inferred a silent seat death. The file exists,
written **03:18**. **Ruling: the seat ran late, not never.** The *underlying* finding stands
untouched and is the more important half: there is no `.FAILED` sidecar convention, so an absent
seat and a healthy seat are the same observation — and `run_deep_sweep.py:150-170` already writes
sidecars while `run_capability_hunt.py:341` emits `exit 90` that nothing consumes.

**E-7 · How many equity numbers? — 4 (research-engine F-18), 6 (prior), or 7 (launch L21)? All
stand; they count different sets.** F-18 counts capacity-policy sources spanning **8.0×**; L21
counts every desk equity artifact spanning **3.3×**. **Ruling: the union is what matters, and the
direction is the finding — the count went UP this week, 6 → 7.** Venue truth is $6,257.59 against
the $18,675.73 every capacity band divides by (**2.98× hot**), so under L1.18a's ≥10% slice the
gauntlet is retiring as OUTGROWN every edge with capacity between ~$626 and ~$1,868 — exactly the
§42 band the desk calls its structural advantage.

**E-8 · Convergences, not disagreements — these gain confidence from independence.** The log
reaper (infra G7 / research-engine F-28, from opposite directions); the `deployed_capital`
tautology (infra G0 / research-engine F-25); `mtime-as-proxy-for-work` (infra / research-engine /
meta, three seats, one day); the phantom `data/research_memory.db` (five seats). **The reaper
convergence has a retroactive consequence every future audit must honour: a missing log is not
evidence an organ never ran, and every prior conclusion of that shape must be re-derived.**

## (F) RECURSIVE META

### Which audits produced the most value this week

1. **validation-stats — the most valuable, decisively.** N22 alone (leak protection inert across
   the entire live path) invalidates more prior work than any other single finding, and it was
   found only by refusing to accept its own prior sweep's K4. It also retracted itself mid-report.
2. **infrastructure** — G28 (one token, eleven fences) is the highest leverage-per-character item
   on the board; G29 corrected a prior number by 10× *in the direction that saves money*.
3. **data-intelligence** — DI-28 is the only finding that silently taxes every future
   cross-sectional result, and it is invisible to the entire validation stack by construction.
4. **meta-blindspots** — resolved its own P1 prediction against itself (0/6) and found the T1
   de-queuing mechanism, which is what makes §A's re-grade load-bearing rather than cosmetic.

### Which produced least — and why that is not a criticism

**execution-growth** carries the worst repeat fraction (**59.1%**) and **launch-readiness**
converted **0 of 10**. Neither is a weak seat; both are re-reporting because *nothing was fixed*.
The distinguishing statistic is the reciprocal: data-intelligence 8.6% repeat, data-moat 16.7%,
against execution 59.1%. **That is a process difference, not a subject-matter one** — the low-repeat
seats re-scope onto new ground each cycle; the high-repeat seats re-verify the same unfixed list.
The fix is upstream (conversion), not in the prompt.

### What is no longer discriminative — retire these questions

- **"we found N findings."** A count with no denominator, until `d` exists (portfolio #9).
- **`unknown_unknown_score`.** 40 published instances, **zero lines of code**, and two seats used
  **opposite conventions in the same week** (data-intelligence raises on discovery, data-moat
  lowers). **I am complying with meta's instruction to the synthesis lead: I have not averaged or
  trended it anywhere in this report**, and last week's synthesis should not have. Give it an
  estimator or demote it to prose.
- **Any verdict resting on mtime, min-bytes, file existence, or a status substring.**
  `check_exploration` FRESH, `check_law_families` 6/6, `check_build_standard` 38/38,
  `check_utilisation` SATURATED, `check_freshness` 1.0, `conversion_status.past_due` — all
  currently non-discriminative.
- **"REPAIR-MODE"** as a state. Permanently on since it became unreachable; it cannot tell a good
  day from a bad one.

### New audit sections that should exist next week

1. **A planted-defect control run against the audit layer itself** (portfolio #9). The desk plants
   controls for its alpha gate and mutants for its tests and has never certified its auditors.
2. **An OUTPUT-VALIDITY section**, and the matching **7th L1.41 condition**: *an organ that reports
   success must compare its output against its input, never against itself.*
   `grep -cin "output.*valid|compare.*source|row_count|non_empty" scripts/check_build_standard.py`
   → **0**. All six existing conditions govern an organ's *form*; none asks whether the artifact
   contains what it claims. Plus the fixture rule the backup defect proves:
   **a test fixture may not create a path that production lacks.**
3. **A cross-seat ORDERING section.** §C's sequencing constraint was invisible to all nine seats
   because each owned one link. This is the synthesis's unique product and should be a standing
   heading.
4. **A `.FAILED` sidecar convention** so an absent seat is distinguishable from a healthy one.
5. **Stable per-seat finding IDs.** Every seat renumbers daily, so repeat-fraction can never be
   automated. Ranked deliberately *below* capacity work (structure after capacity).

### Improving the audit's own genome

- **The completion contract is the clearest improving signal on the desk** (1/8 → 0/8 → 7/8 → 6/7),
  and it is the *only* reason the repeat-fraction was measurable at all. A process change made a
  measurement possible two days later. Protect it.
- **Extract the re-scoping discipline into the sweep prompt.** The 8.6%-vs-59.1% spread is
  reproducible and mechanical, not talent.
- **This sweep's flagship runs 7× its declared cadence by accident** (weekly cron; `organ_catchup`
  re-fires it every 45 min because a fully-successful run writes 783 bytes against a 1200-byte
  success threshold). Under L1.28c a cadence nobody chose is not a cadence. Decide it — and add the
  reusable fence: **"a success threshold a successful run cannot reach."**

## (G) RESEARCH CAPABILITY CAGR

Composite of the seven components, measured not asserted:

| component | measure | reading | direction |
|---|---|---|---|
| experiment throughput | new mechanisms in 14d | **0** (434 = 31 symbols × 14 fixed templates) | **flat** |
| | miner seats productive | **9.1%** (1 of 11) — largest gap on the ratchet board | flat |
| hypothesis quality | novelty gate recall@prod threshold | **0%**; nearest neighbour wrong 8/8 | flat |
| validation quality | gate lifetime admits | **0** of 1,244 trials; `furthest_gate 5` of 11 | flat |
| | leak protection in the live path | **none anywhere** (N22/N21/PBO) | **down** (newly known) |
| automation | exploration organs producing | **2 of 6 never produced**; fence grades mtime | flat |
| knowledge reuse | research-memory content readers | **0** on 117k chars; `predecessor_id` 0/192 | flat |
| implementation velocity | arrivals ÷ dispositions | **33/day ÷ 10.9/day = ρ 3.04**; closure 15.2% | **down** |
| data coverage | corpus 247→324 (+30%); memory 160→192 (+20%); collection gapless (bybit 100%) | acquisition genuinely up | **up** |
| **measurement honesty** | carry-table adoption 1/8 → 6/7; four prior assumptions falsified; three flagship claims retracted | — | **sharply up** |

**Is the engine getting stronger week over week? On output, no — it is flat, and on two components
it went down. On self-knowledge, yes, and sharply.**

The desk's *build* capability is demonstrably high: 157 commits in a day; 17 engines in one commit;
the backup organ built the day it was recommended; two ratchet floors converted within ~7 hours.
Its *convert* capability is 15.2% and its *fidelity* capability is the new binding constraint —
**every fence built on 07-31 shipped with at least one defect of the class it was built to detect,
and the backup organ built to close the #1-ranked finding now reports PASS over an empty replica,
which is strictly worse than the open defect it replaced.**

That is the CAGR reading in one line: **the desk is compounding its ability to see itself faster
than its ability to act on what it sees, and the gap widened this week.** Conversion is the
exponent; everything in §C P1 exists to raise it.

One honest caution against over-reading this section: **the log reaper has been deleting the
evidence base 3×/day**, so several liveness-derived components here are floors, not totals. That
is portfolio item #8's neighbour and is why infra ranks it prerequisite to trusting any future
infrastructure audit.

## LEDGER ROWS RAISED BY THIS SYNTHESIS

Ledger-first (R0056 pattern — `improvement_inbox.md` is write-only and a finding that lives only in
a report body is not tracked). **Fifteen rows for ~250 findings across nine seats.** That ratio is
deliberate: L1.28b's lesson is that raising the arrival rate into a ρ ≈ 3 queue makes things worse,
so this synthesis rows the portfolio, not the sweep.

| row | portfolio | item | roi_bps |
|---|---|---|---|
| **R0232** | P0-1 | Restart `quant-cashcarry` before clearing KILL — deployed binary lacks the guard fix | 9000 |
| **R0233** | P0-2 | Gate-0 profitability criterion — every hold bucket bleeds on the realised tape | 6000 |
| **R0234** | P0-3 | 3-line multi-asset equity fix to `binance_live.py:188` | 5000 |
| **R0235** | P0-4 | Gate `_compounded_capital` on a live-inception boundary (returns 800 on a 200 deposit) | 5500 |
| **R0236** | P1-5 | One honest conversion meter (3 one-line fixes) | 4000 |
| **R0237** | P1-6 | `!= "OK"` — eleven fences green on absent input + exit-code assertions in the test template | 4500 |
| **R0238** | P1-7 | Measure audit recall `d` by planting defects | 5000 |
| **R0239** | P2-8 | Point-in-time universe (survivorship at the source) | 7000 |
| **R0240** | P2-9 | CPCV purge/embargo inert — no leak protection anywhere in the live path | 6500 |
| **R0241** | P2-10 | Unblock the three candidate refill paths | 3000 |
| **R0242** | P3-11 | Moat backup inert and self-certifying; irreplaceable set is 7.4 MB, not 8.7 GB | 4000 |
| **R0243** | P3-12 | Free 345-day first-party L2 archive + **T7 retention probe 2026-08-08** | 5000 |
| **R0244** | P3-13 | Propagate the kimchi/420 retraction to ~45 remaining sites | 3500 |
| **R0245** | P3-14 | Liquidation readers point at a file that has never existed (one line ×2) | 2000 |
| **R0246** | P3-15 | Deploy gate executes fetched code before gating it (RCE, 10-min SLA) | 3000 |

**Deduped — cited, not re-added** (the denominator matters; duplicate rows corrupt it exactly as
the doctrine forbids): **R0041** already owns the `min_len` truncation → portfolio #14, and this
sweep adds decisive new evidence to it — `campaign_window.py` has **zero callers**, not "a missing
kwarg" [SL-3]. **R0086** already owns `_PERIODS_PER_YEAR` ×4.1 → #13. **R0077 / R0223 / R0188**
already own the certification / gate-harshness cluster → #15, and all three now rest on a
**1-seed** artifact (§E-2). **R0073 / R0203** already own moat survivability → #17, re-scoped by
R0242's 10× correction. **R0084** already owns the `cashcarry_error.log` + TCA bundle → #3.

**Also owed and not rowed here** (named so the omission is not silent, per the coverage ratchet):
the ~250 individual seat findings need `track_findings.py` rows, and three ledger *corrections* are
owed rather than new work — R0051's `implemented` is false at ~45 sites (R0244 covers the repair,
not the status), R0211's "LEVEL-REACTION tested once" is a substring-matcher artifact (true count
is **zero**), and the research-engine report's "J = 0.000 → 0.977" figure is same-document
self-similarity, not paraphrase retrieval (§E-5).

**L1.29 forecasts logged by this synthesis, resolve-by 2026-08-08:**
composite capability ≥ 39% (conf **0.6** — if it falls again on "measurement correction" reasoning,
the correct reading flips from honesty to decline); ≥ 6 of R0232–R0246 terminal (conf **0.35**,
and that number is the whole point of §B).
