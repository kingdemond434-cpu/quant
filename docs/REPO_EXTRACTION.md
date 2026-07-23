# REPO_EXTRACTION.md — Tooling Survey & Staged Adoption

Executed 2026-07-23 against the REPO EXTRACTION DIRECTIVE. Governed by the **complexity budget**:
anything ADOPTED must replace or prevent more code than it adds; extract METHODS, not dependencies,
wherever the method is small enough to own; NO repo contains alpha. Versions pinned in
`pyproject.toml`; licences vetted (all MIT/BSD/Apache-2.0 except where noted).

**Headline finding — the budget paid off before a line was written.** This repo already owns most of
Tier 1. The full López de Prado gauntlet (`libs/validation/{cpcv,pbo,dsr,bootstrap,fdr,reality_check,
walk_forward,lockbox,revalidation}`), the vectorbt-style cross-engine check (`libs/backtest/
cross_engine.py`, citing the same W3.2 finding), order idempotency (`libs/execution/retry.py`), and
the RD-Agent-style hypothesis→feedback loop (`libs/alpha_factory/{hypothesis_engine,research_memory}`)
were all present. "Adopt" therefore meant **verify + record** far more often than "write". Only
genuine gaps were filled, each small, owned, and tested.

## Complexity-budget ledger

| Adopted (owned) | Source method | LOC added (src+test) | LOC prevented / replaced |
|---|---|---:|---:|
| `libs/backtest/queue_fill.py` | hftbacktest — queue-position + latency maker fill | 70 + 63 | prevents a whole class of silent maker-fill P&L lies in every maker backtest |
| `labels.triple_barrier_labels` | mlfinlab — triple-barrier labels (from the book, not the port) | 55 + 58 | owns a canonical labeller instead of a 30k-line dep with known-wrong ports |
| `libs/research/microstructure.py` | algotrading-example — order-book imbalance / OFI | 40 + 35 | a ~40-line owned feature vs importing a research repo |
| `libs/research/stationarity.py` | statsmodels + arch — ADF / Engle-Granger / GARCH | 55 + 46 | thin seam over battle-tested libs; hand-rolling ADF/GARCH is banned |
| `libs/validation/baselines.py` | qlib — naive-baseline benchmark scorecard | 81 + 43 | catches DSR-significant-but-loses-to-buy-hold before deployment |
| `tests/backtest/test_live_backtest_parity.py` | nautilus_trader — sim/live parity guard | 0 + 59 | pins the invariants; **surfaced a real inv-vol divergence** (below) |
| **Verified already-owned** | mlfinlab gauntlet, vectorbt crosscheck, freqtrade idempotency, RD-Agent loop | 0 | **~642 LOC not reinvented** |

Net: ~301 lines of owned source + ~304 lines of test added; ~642 lines of reimplementation avoided
by verifying existing coverage first. Every adopted item earns its place.

---

## TIER 1 — ADOPT NOW

**1. nkaz001/hftbacktest** — *ADOPTED (new).* Extracted the fill *mechanism*: a passive order joins
the back of the queue and fills only as same-side trades consume `queue_ahead` then its own size,
delayed by latency. `libs/backtest/queue_fill.py` is a reduced-form owned port (queue priority +
latency + partial fill). Deliberately NOT modelled (documented): book replenishment, cancels-ahead,
price-level jumps. This hardens `libs/backtest/fills.py`, which modelled only slippage/commission —
i.e. it assumed a 100% passive fill rate, a silent lie for the maker-carry book.

**2. nkaz001/algotrading-example** — *ADOPTED (new).* Extracted depth-imbalance construction:
`(bid-ask)/(bid+ask) ∈ [-1,1]`. `libs/research/microstructure.py` provides `book_imbalance` and a
lagged, smoothed `depth_imbalance_signal` panel the existing `crypto_sleeves._book` can consume with
no look-ahead. It is a feature, not an edge — counts as a trial in the DSR ledger if ever screened.

**3. polakowo/vectorbt** — *ALREADY OWNED (verified) + pinned.* `libs/backtest/cross_engine.py`
already runs every strategy through an in-house vectorized reference, backtrader, and vectorbt, and
raises on divergence — the exact W3.2 remedy. Pinned as the optional `[crosscheck]` extra
(`vectorbt>=0.26`, `backtrader>=1.9`) so the dependency is versioned. No new code.

**4. hudson-and-thames/mlfinlab** — *MOSTLY ALREADY OWNED (verified) + one gap filled.* The gauntlet
already owns DSR, PBO, CPCV (purged/embargoed), bootstrap, SPA/FDR, walk-forward, lockbox,
revalidation. **Gap filled:** triple-barrier labels, implemented **from AFML ch. 3 directly** (the
directive's warning — open ports have known-wrong pieces — means an owned, verifiable port is the
correct disposition, not `pip install mlfinlab`). Deferred within #4: fractional differentiation and
dollar/volume bars (no consumer today — see queue).

**5. statsmodels + arch** — *ADOPTED (new, optional).* `libs/research/stationarity.py` wraps ADF,
Engle-Granger cointegration, and GARCH(1,1) behind import guards; installed via the optional
`[stats]` extra. The constitution bans hand-rolled ADF/GARCH (a subtly-wrong stationarity test
admits a spurious stat-arb card), so this defers to the battle-tested references and keeps only a
thin typed seam.

---

## TIER 2 — DEFERRED (trigger recorded, no code) — see `docs/research/adoption_queue.md`

**6. alphalens / alphalens-reloaded** — factor IC / decay / quantile spreads. TRIGGER: first
validated candidate exists to score. (Partial owned coverage already: `libs/research/ic.py`,
`information_value.py`.)

**7. PyPortfolioOpt + riskparity.py** — HRP / risk-parity / Ledoit-Wolf. TRIGGER: ≥2 uncorrelated
validated alphas to allocate between. (Owned but orphaned: `libs/portfolio/{hrp,optimize,
covariance,risk_parity}` — wire these first if the trigger fires.)

**8. blue-yonder/tsfresh** — automated TS features. TRIGGER: feature factory operational **with the
trials ledger counting live** — never a blind sweep; every feature is a trial under DSR.

---

## TIER 3 — READ FOR PATTERNS (no integration)

**9. freqtrade** — execution plumbing. Idempotency + reconcile-don't-blind-retry already owned
(`retry.py`); dry-run already owned (`paper_broker.py`, `staging.py`). Pattern noted: ccxt-style
per-venue quirk tables. **10. jesse** — architecture comparison; our thin native-connector + JSON
state is lighter and preferred at this scale. **11. stefan-jansen/machine-learning-for-trading** —
operator study material, not a dependency. **12. ccxt** — venue-quirk reference even where we use
native APIs. **13. awesome-quant / awesome-systematic-trading / topics** — standing prospector
grounds; re-walk monthly. **14. JerBouma/FinanceDatabase** — symbol-metadata reference only.

---

## TIER 4 — REJECTED (reason recorded; do not revisit)

**15. OctoBot / Crypto-Signal / grid-DCA frameworks** — automate the grid/martingale family the
constitution bans by name. **16. Vibe-Trading / QuantGPT / ai-hedge-fund swarms** — the AI-as-oracle
pattern we reject; AI is engineer and adversary, never the trade-deciding oracle. **17. FinRL /
deep-RL stacks** — severe overfitting surface, uninterpretable, violates simplicity-over-complexity
(operator and constitution concur). **18. A-share factor stacks / TA-indicator bots** — wrong
market, no edge.

---

## "Genuinely better repos" (operator's follow-up) — dispositions

| Repo | Best method | Disposition |
|---|---|---|
| **microsoft/RD-Agent** | hypothesis→implement→validate→feedback evolving knowledge | **Already owned** (orphaned): `alpha_factory/{hypothesis_engine,research_memory}`. Wiring is a *documented* future step (GAP_ANALYSIS: premature at 2 sleeves); the AI-as-oracle parts are rejected. No new code. |
| **microsoft/qlib** | benchmark harness vs standard baselines | **Adopted (new):** `libs/validation/baselines.py`. Also already-owned: `reality_check.py` (White RC + Hansen SPA). |
| **nautechsystems/nautilus_trader** | sim==live parity by construction | **Adopted (new test):** `test_live_backtest_parity.py`, which surfaced a real divergence (below). Full structural dedup deferred (touches live alpha code). |
| **freqtrade / jesse** | idempotent order lifecycle, dry-run | **Already owned:** `retry.py` (idempotency + reconcile), `paper_broker.py`. |
| **AI4Finance/FinRL** | deep-RL allocation/execution | **Rejected** (overfitting, uninterpretable — per operator instruction and constitution). |

## Findings surfaced by the survey (not part of the directive, but load-bearing)

- **Live↔backtest inverse-vol divergence.** `crypto_sleeves._book` (backtest) sizes with inverse-vol
  **lagged one bar** (`ret.rolling(vol_window).std().shift(1)`); `latest_weights` (live) uses vol
  through the final bar (no shift). Leg membership and dollar-neutrality match (both lag the signal);
  only the inverse-vol magnitudes differ. Not silently changed — live sizing on the freshest closed
  bar is defensible; the backtest is the one understating live behaviour. **Recommend** reconciling
  the convention (make `_book` match live, accepting a full backtest re-run) — operator's call.
- **The declared tooling was red.** Full `ruff` (10 issues) and `mypy --strict` (11 errors, incl.
  live `binance_live`/`binance_spot_live` credential-typing) failed on arrival — exactly what the
  missing CI would have caught. Both are now green; a CI gate (`.github/workflows/ci.yml`) enforces
  it going forward.
