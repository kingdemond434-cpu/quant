# VPS DEPLOY + REVIEW PROMPT — branch `claude/quant-repo-review-9po4g5`

**To the desk brain (daily CRO cycle):** an external review + hardening branch is ready. Your job:
(1) read every change **fresh this cycle** (VERIFY-THEN-CLAIM — never assert from this doc alone),
(2) review it adversarially — argue where it's wrong before you agree, (3) deploy what you accept to
the VPS from the repo, (4) **verify each item is actually live** with a fresh read, and log the
result to the ledger. Nothing here is authority to skip a gate or touch live capital — it is
infrastructure, tests, discovery cadence, and one screening-breadth change. The live-arming gate and
the risk floors are untouched and stay untouched.

## 0. First, verify the premise (do not trust this file)

```
git fetch && git log --oneline master..origin/claude/quant-repo-review-9po4g5
git diff --stat master..origin/claude/quant-repo-review-9po4g5
```
Read the actual diffs. Everything below is a claim to verify against the tree, not a fact to accept.

## 1. What the branch changed (the inventory)

**Safety / engineering (already green on the branch: ruff clean, mypy --strict clean 350 files, pytest exit 0):**
- `.github/workflows/ci.yml` — CI gate (ruff + mypy + pytest) so nothing reaches the VPS ungated.
- Greened the tree: fixed pre-existing red `ruff` (10) + `mypy --strict` (11, incl. `binance_live`/`binance_spot_live` credential typing). Declared `scikit-learn`; set pytest `importlib` mode.
- Deepened executor-path tests: `run_crypto_target.merge_sleeve_books` (behavior-preserving extraction) + `_sleeve_weights`; `run_deadman_reconciliation._chunked_trades` pagination/de-dupe.
- Fixed the stale deadman test to the hardened `_HW_CONFIRM` contract.

**Discovery tooling (owned methods, complexity-budget gated — see `docs/REPO_EXTRACTION.md`):**
- `libs/backtest/queue_fill.py` (hftbacktest queue+latency fill), `libs/features/labels.triple_barrier_labels` (AFML), `libs/research/microstructure.py` (OFI), `libs/research/stationarity.py` (ADF/EG/GARCH, optional `[stats]`), `libs/validation/baselines.py` (qlib-style naive-baseline scorecard).
- `libs/alpha_factory/hypothesis_novelty.py` — pre-compute novelty gate (RD-Agent trace-conditioning): screen a candidate against the graveyard BEFORE compute. **Wire this into the frontier-miner / prospector path** so scarce compute skips redundant hypotheses.
- `libs/autodiscovery/generation_roi.py` + `scripts/run_generation_roi_test.py` — falsification harness proving mass generation over fixed data is self-defeating (DSR deflation). Run it; keep it as the ROI gate on any future generator.

**Discovery cadence — MAXED to the ROI ceiling (systemd timers in `ops/`):**
- `quant-dataaxis.timer`: weekly → **daily** (`*-*-* 14:00`).
- `quant-prospector.timer`: biweekly → **3×/week** (Mon/Wed/Fri 18:00).
- `quant-litminer.timer`: biweekly → **3×/week** (Tue/Thu/Sat 18:00).
- `quant-frontier.timer` + `quant-frontier.service` + `run_frontier_rotation.sh`: **NEW** — brings the 7 regional frontier miners to **3×/week each** (3 regions/day deterministic rotation, verified even coverage) per DIGGER PARITY (§14). Caps load at 3 heavy digs/day so the recorder + connector keep brain-time first.
- `quant-blindrediscovery.timer`: quarterly → **monthly** (deliberately NOT more — re-walking the graveyard faster finds nothing and feeds DSR deflation).

**Screening breadth (validation accelerant):**
- `ingest_crypto_enriched.py --top` default 80 → **150**. Wider screening panel = more cross-sectional observations/day = faster statistical power (the only real validation accelerant per `anytime_valid.py`). Screening only — the live trade universe + depth guard are separate. **Verify the scheduler isn't overriding `--top`; if it is, raise it there too.**

## 2. Adversarial review — argue before you agree

For each item: does it help, is it correct, does it fit the complexity budget, does it touch a gate
or the money path it shouldn't? Flag anything wrong to the ledger. Known caveats already logged:
- **Live↔backtest parity:** `latest_weights` reads the signal at `iloc[-2]` but inverse-vol at `iloc[-1]` (a one-bar offset `_book` lacks). NOT auto-changed — the fix direction depends on whether the lake's last D1 bar is complete or forming at runtime. **Confirm the bar semantics, then decide + backtest the aligned variant.** A characterization test pins current behavior so it can't drift.

## 3. The REAL validation accelerants — evaluate + implement WITH testing (not blind)

`anytime_valid.py`'s own Monte-Carlo conclusion: *the only accelerants are MORE OBSERVATIONS; there
is no free lunch on a cleverer test.* So, in priority order:
1. **Higher-frequency archives.** The metric collectors snapshot **daily**. Binance futures publishes OI / long-short / taker at 5m–1h. Archive at venue-max granularity into immutable Bronze (autocorrelation limits the gain, but the archive is forever and you cannot back-fill data you never gathered). Test: diff a finer pull vs the daily snapshot before any pipeline trusts it.
2. **Cross-sectional breadth on the live path.** Consider raising `run_crypto_target` `top_n=120` — but backtest first to confirm no capacity/noise harm; the depth guard already stands aside on thin books.
3. **Reconstructed history back-fill.** Per the FREE-DATA doctrine, reconstruct historical OI/LS/etc from archives to front-load out-of-sample instead of waiting forward — the single biggest lever on the 40-day clock.
4. **anytime-valid = SECONDARY check ONLY.** Its verified data shows it is SLOWER than the fixed clock for real edges (median 132d for Sharpe-2). Add it as a stricter belt-and-suspenders gate if you want more rigor — do NOT wire it to replace or shorten the 40/90-day clock. It is not a speed lever.

## 4. Deploy (VERIFY-THEN-CLAIM each step)

```
# Decide first: merge the branch to master, or pull it directly on the VPS. (I cannot merge to
# master; that is your call after review.)
git pull                      # or merge the reviewed branch

# Timers: remove the OLD frontier cron / run_cro_ai frontier line FIRST -- the new
# quant-frontier.timer REPLACES it. Leaving both = duplicate scheduler (the 1b5300f bug).
systemctl daemon-reload
systemctl enable --now quant-frontier.timer
systemctl restart quant-dataaxis.timer quant-prospector.timer quant-litminer.timer quant-blindrediscovery.timer
```

## 5. Verify it is ACTUALLY live (report each verified/unverified)

```
systemctl list-timers | grep quant           # dataaxis daily, prospector Mon/Wed/Fri, litminer
                                              # Tue/Thu/Sat, frontier daily, blindrediscovery monthly
systemctl cat quant-frontier.timer           # confirm the file on disk matches the repo
python -m pytest -q                           # exit 0 on the deployed tree
ruff check . && mypy                           # both clean
python -c "import libs.alpha_factory.hypothesis_novelty, libs.autodiscovery.generation_roi"  # import OK
python scripts/run_generation_roi_test.py     # the ROI harness runs
```
No timer counts as deployed until `list-timers` shows its next elapse; no code change counts as live
until a fresh read confirms it. Log the verified inventory to the decision ledger. If any step fails
or you disagree with any change, say so — do not mark it done.
