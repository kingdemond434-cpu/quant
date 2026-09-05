# COT SCREEN RESULT — 41 years of positioning data, read for the first time (register #77)

Pre-registered in `docs/research/AXIS_PREREGISTRATIONS.md` **before** any computation. Stage-A
screen: **zero promotion authority**. Runner `scripts/run_cot_screen.py`, artifact
`data/cot_screen_summary.json`. Reproduce:

    python scripts/run_cot_screen.py --years 1986-2026

Panel: CFTC Commitments-of-Traders futures-only archives 1986→2026 (public domain), 6 contracts
with a licence-clean price leg from FRED's keyless CSV endpoint (public domain). **24 trials
charged** (2 constructions × 6 assets × 2 questions), all logged.

---

## B. THE GORTON-HAYASHI-ROUWENHORST GATE — REPLICATED, and it cancels a purchase

GHR reject hedging pressure: positioning is significant **contemporaneously** and **zero lagged**
— and only the lagged form is tradeable. On the desk's own 41-year panel:

**Pooled lagged Newey-West t = −0.64.** Indistinguishable from zero.

| asset | construction | t contemporaneous | t **lagged** |
|---|---|---:|---:|
| crude_oil | commercial | −0.22 | −0.57 |
| crude_oil | noncommercial | +0.27 | +0.63 |
| eur_fx | commercial | −2.20 | **−2.48** |
| eur_fx | noncommercial | +2.21 | **+2.81** |
| jpy_fx | commercial | +0.95 | +0.24 |
| jpy_fx | noncommercial | −0.93 | −0.31 |
| gbp_fx | commercial | −0.40 | −0.38 |
| gbp_fx | noncommercial | +0.59 | +0.12 |
| sp500 | commercial | +0.65 | +1.13 |
| sp500 | noncommercial | +1.24 | +0.89 |
| ust_10y | commercial | +0.61 | −0.20 |
| ust_10y | noncommercial | +0.46 | +0.94 |

**EUR FX is the only asset clearing |t|=1.96 on the lagged form, and it does NOT survive
multiplicity.** With 24 charged trials the two-sided Bonferroni bar is **|z| = 3.08**; EUR's best
is 2.81. One asset in six at that level is what 24 trials produce from noise, and the desk's own
law counts every charged cell. Reported here rather than presented as a find — a single surviving
cell after a 24-cell sweep is the textbook shape of a phantom edge.

### PRE-COMMITTED CONSEQUENCE, now executed
The pre-registration stated: *pooled lagged predictability indistinguishable from zero is a REJECT
for the positioning-axis CLASS and CANCELS any multi-week crypto positioning-data acquisition.*
That condition is met. **The queued crypto positioning acquisition is CANCELLED on evidence**, and
the ~1-day test that produced this verdict replaced a multi-week data programme — which was
register #77's stated reason for ranking this work at all.

Note what this does NOT say: it does not claim positioning data is worthless. It says that in the
only tradeable form (lagged), across 41 years and six liquid contracts, the effect is absent — so
crypto `ls`/`oi` positioning must clear a bar that the deepest available positioning panel does
not clear, before the desk spends weeks acquiring more of it.

---

## A. POST-PUBLICATION DECAY — UNANSWERABLE ON THIS PANEL, and that is the finding

The desk adopted a **borrowed** −58% McLean-Pontiff post-publication haircut as a standing prior
(register #71) and has been citing it as if it were measured. It cannot be validated here:

| asset | n pre-2000 | Sharpe pre | Sharpe post |
|---|---:|---:|---:|
| crude_oil | 488 | **−0.37** | −0.07 |
| jpy_fx | 489 | **−0.80** | +0.18 |
| gbp_fx | 369 | **−0.34** | +0.32 |
| ust_10y | 311 | **−0.78** | +0.02 |
| eur_fx | 0 | — | +0.20 |
| sp500 | 311 | 0.00 (no price) | −0.34 |

**In every asset with a real pre-publication sample, the pre-publication Sharpe is NEGATIVE and the
post-publication Sharpe is HIGHER.** There is no positive effect to decay. Decay is therefore
reported as `n/a` by construction rather than as a fabricated negative number — the honest output.

Three consequences, stated plainly:
1. **The −58% haircut remains BORROWED.** The desk must cite it as an imported assumption, not as
   a measured property of its own data. Register #71's action item ("compute shrinkage on the
   desk's OWN realized right tail") is unaffected and still owed — that is a different measurement.
2. It is **consistent with question B**: an effect with no lagged predictability in 41 years cannot
   show publication decay, because it was never there in tradeable form.
3. The naive reading — "post > pre, so publication IMPROVED it" — is rejected here as noise, not
   adopted: all post-period Sharpes are between −0.34 and +0.36, i.e. inside the noise band for
   1,100–2,200 weekly observations, and 24 trials were charged.

### Coverage gaps, named rather than papered over
- **eur_fx has no pre-2000 sample** because the euro did not exist before 1999. Structural.
- **sp500 has no usable pre-sample** because FRED's `SP500` series begins **2016-08-01** (verified:
  first row `2016-08-01,2170.84`). A price-side limit, not a COT limit. A longer licence-clean
  equity index leg would close it.
- **Metals, grains and softs are absent entirely.** Stooq (the obvious free continuous-futures
  source) sits behind a JavaScript proof-of-work bot gate, and **register #80 is an OPEN principal
  ruling on whether defeating an anti-bot gate is inside §13** — so it was not defeated. Yahoo's
  chart endpoint returned HTTP 429. This is the single largest improvement available to this
  screen and it is **blocked on that ruling**, not on engineering.

---

## Two parsing defects this screen found in itself (both would have produced false negatives)

Recorded because each is the same failure shape the desk keeps finding: an instrument reporting a
fact about the world when it was actually reporting a fact about itself.

1. **Substring column matching.** `"Commercial Positions-Long (All)"` is a substring of
   `"NONCommercial Positions-Long (All)"`, and the noncommercial column appears FIRST in the CFTC
   file. A substring lookup returned the noncommercial value for both legs, so **all 12 commercial
   series computed to exactly 0.00** — which printed as "no edge in hedging pressure" and was a
   parsing bug. Fixed by anchoring on the column prefix.
2. **Contract-name drift across eras.** Pre-2000 crude is filed `CRUDE OIL, LIGHT 'SWEET'` (quotes
   around SWEET) and pre-2000 sterling is `POUND STERLING` (no "BRITISH"), while `"S&P 500"` also
   substring-matched `S&P 500 BARRA GROWTH INDEX` and `E-MINI S&P 500` — stacking three different
   contracts into one series (5,395 weekly rows where 41 years hold ~2,130). Fixed with normalised
   prefix matching, per-era name aliases, and per-date dedup by largest open interest.

**The generalisable rule:** a silent parse failure and an absent effect are indistinguishable in
the output. Any screen reporting "no effect" must first show that its inputs are non-degenerate —
here, that the commercial series is not identically zero and that one date holds one contract.

---

## Disposition

- **B: REJECT the positioning-axis class** (pooled lagged t = −0.64, 41 years, 6 contracts).
  Crypto positioning-data acquisition **cancelled on evidence**. Re-entry per L1.16a needs a NAMED
  enabling change — e.g. intraday-frequency positioning data, where per-observation signal is
  materially higher than weekly.
- **A: NOT MEASURED — the borrowed prior stays labelled as borrowed.** Re-opening requires a
  licence-clean commodity/metals price leg (blocked on the register #80 ruling) or a longer equity
  index series.
- Nothing here promotes anything. No forward clock was started.


## KRT position-CHANGE screen (2026-08-25, card #40 conversion)

Prereg: AXIS_PREREGISTRATIONS.md C. Primary pooled dx1: beta=-6.6e-05, NW t=-0.41, n=12356; recent24m dx1 t=0.24; XS dx1 mean IC=-0.0108 (t=-0.92). 26 trials charged; dropped: none.

**SCREEN-KILL: pooled dx1 fails the preregistered bar (beta >= 0 or t > -1.96)**
