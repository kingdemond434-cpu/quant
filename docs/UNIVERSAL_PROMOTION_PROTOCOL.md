> **SUPERSEDED 2026-08-25 (principal consolidation order).** Operative law now lives in
> [docs/LAWS.md](/docs/LAWS.md) and [docs/RESEARCH.md](/docs/RESEARCH.md); dispositions in
> [docs/MANDATE_COVERAGE.md](/docs/MANDATE_COVERAGE.md). This file is the unabridged ANNEX —
> consult it for detail, never for standing orders; on conflict the compact documents govern.
> The MT5 UNIVERSE MANDATE (LAWS §1) voids every crypto-universe clause herein.

# The Universal Validation & Promotion Protocol

**BINDING ON EVERY BRAIN.** Claude, Codex/opencode, and any LLM, agent or human that proposes an
edge to this operation. One protocol, one path, one set of gates. A strategy that reached live
capital by any other route is not validated, however good its numbers look — it is unmeasured, and
this desk treats unmeasured and worthless as the same thing until proven otherwise.

There is exactly one door: **hypothesis → falsify → sweep with multiplicity → shadow → promoter →
live.** No brain has a private door. No brain edits `data/sleeves.json` by hand. No brain arms
capital. If you find yourself about to write a sleeve straight into the trading config because you
are confident, stop: that confidence is the thing the protocol exists to test.

---

## Part I — Why this document exists: the bugs, and what they have in common

This is not a reprimand. Every defect below was found in work that was **substantially correct and
genuinely valuable** — the MT5 desk is real, the hunts are real, the surviving edges may well be
real. That is exactly why the defects mattered: sound infrastructure carried them silently. Read
them as a description of how *this particular kind of work* fails, because it will fail this way
again, in your code and in mine.

### 1. The lookahead that manufactured 180 survivors

`run_hunt12.day_states` labelled each trading day by the state of **that same day's** NY session,
then used the label to decide whether to trade that day's Asia and London windows. Asia opens at
07:00 UTC. The NY session that defined its label had not happened yet.

The sweep did not know this and reported **180 conditioned survivors**. After joining each day to
the **prior** completed session instead, the same sweep returned **9** — and the overlap between
the two sets was **zero**. Not "mostly the same, slightly fewer." A completely different set of
strategies. Every one of the original 180 was an artifact of knowing the afternoon before trading
the morning.

The tell was available before the fix: 180 survivors from a sweep of that size is not a rich
market, it is a broken join. **Implausible abundance is a bug report.**

### 2. Selection without paying for the search

The corrected sweep tested **2,464 cells** (symbols × windows × states × parameters) and reported
the best by t-statistic, with no multiplicity correction anywhere in the path. Nine cells cleared
the raw bar. Under the deflated Sharpe ratio — SR₀ = sd(SR across trials) × E[max of N normals] —
the honest count was **3**.

If you search 2,464 cells of pure noise, the best one has a t-statistic around 3.5. That is not a
discovery, it is arithmetic. **The number of things you looked at is part of your result.** A
t-stat quoted without its trial count is not a statistic; it is a screenshot.

### 3. The gate applied at one layer only

The conditioning state — the whole reason a candidate earned +0.276R instead of the unconditioned
+0.163R — existed in the sweep and **nowhere else**. `shadow_forward` keyed sleeves on
`(symbol, window)`. `promoter` wrote no state field. `gateway.sleeve_set` rebuilt every sleeve from
`window` alone.

Promoting `CADJPY asia FAILED_BREAK` would therefore have traded **CADJPY asia on every single
day** — carrying the name, the risk budget and the reported expectancy of a strategy that was never
running, while the unconditioned version traded in its place. Nothing anywhere would have logged
the substitution. The equity curve would simply have underperformed, and the desk would have
concluded the edge decayed.

**A gate applied at one layer is not a gate.** It has to survive every hop: sweep → shadow →
promoter → gateway → the order actually sent.

### 4. Two more state-drops in the same chain

Once the state field existed, it was dropped twice more:

- `promoter` parsed keys with `key.split(".", 1)`, putting `"asia.FAILED_BREAK"` into the window
  field. The gateway's window whitelist then rejected it and dropped the sleeve **silently** — a
  conditioned candidate would have met every promotion criterion forever and never promoted, with
  no error raised anywhere.
- The **retire** path rebuilt the shadow key as `f"{symbol}.{window}"`, dropping the state again.
  Retiring `CADJPY.asia.FAILED_BREAK` wrote KILL onto `CADJPY.asia` — a *different* sleeve, also in
  the shadow set, which had done nothing wrong — while the conditioned sleeve kept its
  `PROMOTION CANDIDATE` status and was re-promoted on the next run. Promote, retire, promote,
  forever, against the module's own docstring promise that retired sleeves are "never re-promoted."

Same defect, three times, in three functions written at three different times. When a field is
optional in one place it will be forgotten in every other place. **Make the invariant structural,
not remembered:** the sleeve's name *is* its shadow key; use it, never rebuild it.

### 5. Units that would have deleted the best edges

`spread_cost_per_lot` computed `median_spread_pts × tick_size × contract_size` — quote currency —
where the account model needed `median_spread_pts × tick_value`, account currency. For CADJPY this
read **1500 instead of 8.14**, a 184× overstatement.

Nothing would have crashed. The universe filter would simply have excluded every JPY cross as
uneconomic — and the JPY crosses are where the surviving edges actually live. A units error does
not announce itself; it quietly removes the answer from the search space.

### 6. Absence written as zero

`record_sleeve_returns` wrote `0.0` for days a sleeve did not trade. A day with no trade is not a
day with a zero return — it is a day with **no observation**. Zero-filling deflated every pairwise
correlation and manufactured diversification that did not exist, inflating k_eff by **1.36×** and
with it the entire heat budget.

The same class: `nan_to_num(..., nan=0.0)` in `_producer_margin_stress`; unfilled order intents
counted as zero-slippage fills in the markout. **Absence of a measurement is never a measurement of
zero, and it is never permission.**

### 7. The import error nobody saw

`record_sleeve_returns.py` imported `SUBTYPE_TO_CLASS`, which has never existed — the real name is
`CONSTRUCTION_CLASS` — inside a bare `except ImportError: pass`. The module ran, produced output,
and silently skipped its classification step for as long as it existed.

**A swallowed exception is a decision to be wrong quietly.** If a fallback is genuinely correct,
log it. If it is not, let it raise.

### 8. Numbers copied instead of sourced

`allocation.py` optimised and reported the book at `Q_TOTAL = 0.055` long after the gateway moved to
`0.0075` — a seven-fold disagreement about how much of the account is at risk, sitting in two files
that never compared notes. The desk was optimising one book and trading another.

### 9. Infrastructure that runs but decides nothing

`research_supervisor` restarts hunts. `hourly_cycle` checks health, mines Reddit, writes a frontier
report. Both work. Neither ever runs `shadow_forward`, `promoter`, or `markout` — the three
processes that actually move an edge toward capital. The supervisor's design makes this structural:
it is built around **one-shot DONE markers**, so a daily recurring job would run once and never
again.

Nine validated candidates were therefore sitting in a list that nothing executed. **A pipeline that
does not terminate in a decision is not a pipeline, it is a hobby.** Ask of every module you build:
*what changes because this ran?* If the answer is "a file is newer," it is not finished.

### The pattern

Seven of these nine are the same mistake wearing different clothes:

> **Something was absent, and absence was read as permission.**

An absent prior-day label became a same-day label. An absent multiplicity correction became a raw
t-stat. An absent state field became "trade every day." An absent trade became a zero return. An
absent import became a skipped step. An absent runner became "it must be running."

The discipline that prevents all seven is one sentence: **fail closed.** When the thing you need is
not there, the correct behaviour is to refuse, loudly, in the log — never to substitute a default
that happens to let the code continue. Every gate in this repo is now written that way, and
`state_allows()` is the reference implementation: a conditioned sleeve whose state cannot be
computed does not trade, because the alternative is trading something else under its name.

---

## Part II — The ladder every edge climbs

Validation intensity scales with how much capital the claim would attract. These are the rungs. You
may add rungs; you may never skip one.

**0. Mechanism, before any code.** State in one sentence *why this should work* — who is forced to
trade, what constraint they are under, why the money is not already taken. "The backtest is good"
is not a mechanism. An edge with no mechanism is a curve fit that has not been caught yet, and it
gets the harshest multiplicity treatment and the smallest size if it survives.

**1. Cheap falsification first.** Try hardest to kill it before you try to confirm it. The Tokyo-fix
hypothesis for gold died here: +0.216R on JP holidays against +0.212R on ordinary days. If the
mechanism were real, removing the mechanism would have changed the result. Ten minutes, one
hypothesis correctly buried.

**2. In-sample, then chronological OOS, then walk-forward.** Never random-split time series. Never
tune on the OOS window — the moment you look at it twice it is in-sample.

**3. Count your trials and pay for them.** Record the **exact** number of cells the sweep touched:
symbols × windows × states × parameters × families, including the ones you tried and abandoned.
Apply `mt5desk.multiplicity.deflated_t` with that count. Report `t_raw`, `n_trials`, `E_MAX`, and
`t_deflated` together, always. A result quoted without its trial count is rejected on sight.

**4. The gauntlet.** `research/qquant_gates.py` — ten gates: PBO/CSCV, Hansen SPA, CPCV,
walk-forward stability, parameter plateau, cost stress, latency stress, placebo, block bootstrap,
deflated Sharpe.

**Failing a gate is information, not a verdict.** The nine current candidates fail *only* deflated
Sharpe and pass the other nine. PBO 0.034 and walk-forward stability 1.0 say they are not
curve-fits; the DSR failure says the sample is too small to distinguish them from the best of 2,464
coin flips. That is a **power** problem, and the only cure for a power problem is more data. Which
is exactly what shadow produces, at zero capital. So: gauntlet failures on **validity** gates
(PBO, placebo, SPA) kill the candidate. Failures on **power** gates route it to shadow to earn more
evidence. Say which kind you have, and never quietly relax a gate to get a pass.

**5. Shadow.** Below.

**6. Live, small, sized by the risk budget.** Not by conviction.

---

## Part III — How to put an edge into shadow

This is the whole procedure. It is deliberately small, because a hard thing to do correctly gets
done incorrectly.

**Step 1.** Append one row to `SLEEVES` in `desks/mt5/research/shadow_forward.py`:

```python
("CADJPY", "asia", "FAILED_BREAK"),   # (symbol, window, state); state=None means unconditioned
```

**Step 2.** If the sleeve is conditioned, the function that computes its state must be **the same
function the sweep used** — imported, not reimplemented. `shadow_forward` imports `day_states` from
`run_hunt12` for exactly this reason. A shadow record built on a re-typed copy of the conditioning
rule is measuring a third strategy that neither the backtest nor the live book will ever run.

**Step 3.** Nothing else. Do not touch `sleeves.json`. Do not touch the gateway. The promoter owns
promotion; you own the hypothesis.

Shadow replays the sleeve on **real live H1 bars** from `SHADOW_START` forward, using the same
family code and engine as the backtest, with the account cost model, at **zero capital**. Fills are
simulated at real bar prices. It runs once per UTC day and is idempotent.

### What shadow decides, and when

Two clocks, doing two different jobs:

| | |
|---|---|
| `n >= 50` **or** `days_active >= 14` | **when to look** — the evaluation trigger |
| `n >= MIN_VERDICT_TRADES` (20) | **whether the sample can carry a verdict at all** |

Below 20 trades **no terminal verdict is issued in either direction**. The sleeve logs `DEFERRED`,
stays `ACTIVE`, and keeps accruing.

This exists because the 14-day clock was executing slow sleeves at random. A cell firing ~80×/year
produces about **three** trades in fourteen days, and the verdict is permanent. Measured against the
best candidate's +0.276R with per-trade sd 1.089, the probability of **killing a genuinely good
edge**:

```
   3 trades → 36.0%        20 trades → 17.7%
   5        → 32.1%        50        →  7.1%
  10        → 25.6%       100        →  1.9%
```

A 36% false-kill rate is worse than useless — it is a coin flip with extra steps, and it promotes
noise at the same rate in the other direction. So a slow edge is now never stuck (it promotes the
moment it has evidence) and never killed on three fills. Waiting is free: shadow uses no capital.

Verdict thresholds once evidence exists: `exp_r > 0.05R` **and** `max_dd_r > -25R` → `PROMOTION
CANDIDATE`; otherwise `KILL`.

---

## Part IV — How every brain monitors its shadow edges

**Every brain monitors its own edges, and every brain can read every other brain's.** There is one
state file, one format, one dashboard. A private tracker is a fork of the truth.

```
reports/shadow/shadow_state.json          per-sleeve n, cum_r, exp_r, max_dd_r, days_active, status
reports/shadow/ledger_<sym>_<win>[_<state>].json    every simulated trade, idempotent
logs/shadow.log                           the daily run, including every DEFERRED line
logs/promoter.log                          every promotion and retirement with its reason
data/order_intents.jsonl                   what the desk ASKED for  ─┐ joined by ticket
data/live_ledger.jsonl                     what the desk GOT        ─┘ by mt5desk.markout
```

Check on your edges with:

```bash
python -m mt5desk.markout                       # execution: intended vs filled, in R
python research/shadow_forward.py               # idempotent; skips if already run today
cat reports/shadow/shadow_state.json
```

### Demo is a rung on the ladder, not a shortcut down it

The desk switches brokers by editing one line of `data/terminal_path.txt`, so the account under the
gateway can change between two runs. Every ledger row is therefore stamped with `account`, `server`
and `account_kind`, and **the promoter counts only trades from the account currently in hand.**

This is not bookkeeping. Demo fills are **optimistic, not conservative**: a demo server has no
liquidity behind it and fills stop orders at the trigger price with no slippage — precisely the
assumption `markout` exists to test. A clean markout on demo is the null result a server that
*cannot* slip will always produce, so it confirms nothing. Blending demo and live rows would drag
the mean toward "no slippage" using trades that could not have slipped, and a losing demo week
could retire a live edge.

So: `markout` refuses to average across accounts and labels a demo measurement as **not evidence of
live execution**. Rows predating provenance match nothing and decide nothing — a deliberate loss of
history, because the alternative is crediting pre-switch trades to whatever account is connected
today.

What a demo run **does** prove, and it is worth real money to learn without spending any: contract
sizes, stop and freeze levels, symbol suffixes, session hours, margin maths, and whether the
gateway's orders are accepted at all. Run there first. Just never quote its slippage as your cost.

**Read `markout` before you believe any return figure you produce.** Every number this desk
generates assumes fills at exactly the bracket price, and session-range breakout enters on **stop
orders into fast moves** — the worst case for slippage, because the order becomes a market order
precisely when the book is thinnest and moving away.

The precedent is in this repository. The crypto desk's cost surface said 0.35bps for a BNB round
trip; its own fills said **~16bps**. Fifty times off. Every hold bucket came back negative while the
entry gate believed it was selecting winners. That desk found out by comparing intents to fills, and
only after a bad quarter. A 0.10R average slip against the gold book's +0.159R edge is **63% of
everything the book earns**. `markout` reports slippage as a share of the edge for that reason, and
reports `UNMEASURED` — never "0.0" — before the first fill.

---

## Part V — Promotion is automatic. Do not do it by hand.

`research/promoter.py` runs daily after `shadow_forward` and is the **only** writer of
`data/sleeves.json`. The gateway picks up its changes within a minute.

**PROMOTE** — shadow status is `PROMOTION CANDIDATE` and the sleeve is not already present:
- **JPY crosses and other non-gold**: promoted directly at `PROMOTED_LOT = 0.01`.
- **XAUUSD challengers**: promoted **only** if forward `exp_r` beats the armed gold sleeve's live
  forward `exp_r` in the same window by `CHAMPION_MARGIN = 0.02`; otherwise `KILL`. The three
  XAUUSD candidates are *filtered subsets of gold legs already live* — they exist to be measured
  **against** their parent, not promoted alongside it, which would double-count the same trades.
- The `state` field is written into the sleeve and the gateway **refuses to trade a conditioned
  sleeve whose state it cannot confirm** (`state_allows`, fails closed).

**RETIRE** — automatic, from the live ledger, no human in the loop:
- `n >= 10` and rolling-20 `exp <= 0` → edge gone
- forward `max_dd < -25R` → tail breach
- `n >= 50` and `exp < 0.05R` → too weak to hold a slot

Retired sleeves are marked `KILL` in shadow under **their own key** and are never re-promoted.

**The armed gold book is not managed here.** It is hunt5 authority, armed by a human, and
`sleeve_set()` places it **first** so `cap_by_heat` treats it as senior to anything the promoter
added on its own.

### The risk budget is not yours to set

Sizing is solved from one stated number, in one place, and imported everywhere:
`MAX_DRAWDOWN_TOLERANCE = 0.35` in `mt5desk/gateway_config_fallback.py`.

```
Q_OPT      = 1 - (1 - tolerance)^(1/33.7)  = 1.27% per trade     the risk that spends exactly
base heat  = Q_OPT × 3 legs                = 3.81% of equity      the tolerance, no more
budget     = base × sqrt(k_eff / 2.26), capped at MAX_HEAT_CEILING = 15%
```

Breadth is bought with **measured** orthogonality: more independent bets survive more total heat at
the same drawdown, because portfolio drawdown scales as H/√k_eff. **Unmeasured k_eff returns the
base budget, never the ceiling** — treating "not yet measured" as "independent" is precisely how a
correlated book discovers its real correlation during the drawdown instead of before it.

Do not hardcode a risk number anywhere. `test_no_consumer_hardcodes_its_own_risk_budget` will fail,
and it exists because a stale copy of this number once ran the desk at 7× its policy.

---

## Part VI — The rules, compressed

1. **Fail closed.** Absence is never permission. A gate that cannot evaluate must refuse, in the log.
2. **Count your trials and report them.** `t_raw`, `n_trials`, `E_MAX`, `t_deflated`, together.
3. **Never join a day to its own future.** Every conditioning label is prior-session or earlier.
4. **A gate must hold at every layer**, sweep to order. Verify the whole chain, not the function.
5. **Import the number, never restate it.** Two copies that must agree will disagree.
6. **Absence ≠ zero.** No zero-filling, no `nan_to_num(nan=0.0)`, no unfilled intents in a mean.
7. **Never swallow an exception** that changes what the code computes.
8. **Check units against the account**, not against the chart.
9. **Implausible abundance is a bug report.** 180 survivors means broken, not blessed.
10. **Every module ends in a decision.** A fresher file is not an outcome.
11. **Live reality outranks history**: idea < backtest < OOS < frozen forward < shadow < small live
    < long live. Historical results never overrule persistent live deterioration.
12. **No brain arms capital or hand-edits `sleeves.json`.** Propose → branch → test → shadow →
    promoter. The production firewall is not advisory.
13. **Write the test that would have caught it**, in the same commit as the fix, naming the defect
    in its docstring. Every test in `desks/mt5/tests/` is a bug that cannot come back.

---

## Part VII — What a brain does when it finds something

```
1.  State the mechanism in one sentence.
2.  Try to kill it. Cheapest falsification first.
3.  Sweep. Record the exact trial count.
4.  Apply multiplicity. Report deflated, not raw.
5.  Run research/qquant_gates.py. Say whether a failure is VALIDITY or POWER.
6.  Add one row to shadow_forward.SLEEVES. Import the conditioning function; never retype it.
7.  Commit with the test that would have caught the defect you found on the way.
8.  Stop. The promoter decides. Check reports/shadow/shadow_state.json tomorrow.
```

If a step is impossible — no data, no terminal, no venue — **say so and stop**. Do not substitute
the nearest thing that runs. This desk would rather have nine honest candidates in shadow than one
hundred and eighty that came from reading the afternoon before trading the morning.