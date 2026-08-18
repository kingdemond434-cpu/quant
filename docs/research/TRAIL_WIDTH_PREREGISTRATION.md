# TRAIL WIDTH FORWARD TEST — pre-registration (R0479)

**Registered: 2026-08-18T21:00:00+00:00. Frozen. Constants live in
`scripts/resolve_paper_book.py` (`TRAIL_FWD_*`); editing them after this instant is the
p-hacking this document exists to prevent. Evaluated hourly by the resolver cron; the verdict is
`trail_forward` in `data/paper_book_pnl.json`.**

## Hypothesis

A 0.5R trail (challenger) compounds harder per trade than the live 1.0R trail (incumbent) on the
conviction sleeve, measured as paired per-trade log growth on identical bars.

## Motivating evidence — and why it has zero authority

- R0334 decomposition (2026-08-12, n=14 closed PAPER trades): median capture ratio 0.335 — the
  median trade keeps a third of the peak R it reached. Upper bound: MFE sampled from hourly
  re-marks, so peaks given back between marks are invisible.
- `trail_sweep` (state THIN, n=9): best_trail_r 0.5 vs live 1.0.

Both are IN-SAMPLE. A width fitted to 14 closes is curve-fitting in the sleeve's
steepest-gradient slot (growth_levers ranks the winner shape as the steepest term). The sweep
READ BY NOTHING until this registration was itself an unwired capability (III.16).

## Design

- **Sample:** conviction ladder trades ENTERED strictly after the registration instant. Trades
  entered before but closing after are partially in-sample (their bars fed the 0.335/0.5
  measurements) — excluded. Unparseable entry stamps cannot prove they are forward — excluded.
- **Statistic:** for each forward trade closed at both widths on the same bars,
  d = log1p(net_equity_return @ 0.5R) − log1p(net_equity_return @ 1.0R). Paired, so the
  trade/regime draw cancels; costs are recomputed per width (a wider trail holds longer and pays
  more funding).
- **Decision rule (frozen):** earliest read at n=25 paired closes; hard stop at n=50 (aligned
  with the sleeve's own KILL_AFTER_N so the trail question cannot outlive the sleeve question).
  - t ≥ +1.7 at n ≥ 25 → **ADOPT-BAR-MET**: changing TRAIL_R becomes authorised via a reviewed
    commit citing the block.
  - t ≤ −1.7 at n ≥ 25 → **REFUTED**: hypothesis retired, best_trail_r=0.5 was curve-fit.
  - |t| < 1.7 at n ≥ 50 → **INDISTINGUISHABLE**: incumbent stays, hypothesis retired.
  - No verdict of any kind before n=25. **NO EXTENSIONS** past n=50.

## Mechanism separation (required by R0479 before any change)

Capture ratio 0.335 has two candidate mechanisms: (a) the trail is genuinely too wide; (b) the
ladder is rarely climbed (median share of ladder reached 0.33), so most exits never arm a trail
at all. `share_reaching_trail` measures (b) directly on the forward sample. If fewer than 50% of
forward closes ever arm the trail, the verdict carries a MECHANISM NOTE that the LADDER, not the
trail, is the binding lever — an ADOPT verdict then authorises the width change but names the
ladder as the larger open question.

## What this registration forbids

- Editing `TRAIL_R` before an ADOPT-BAR-MET verdict (the config edit R0479 explicitly rejects).
- Editing any `TRAIL_FWD_*` constant after this instant.
- Reading `trail_sweep`'s in-sample curve as adoption evidence at any n.
- Extending a REFUTED/INDISTINGUISHABLE clock for a larger sample of the same mechanism
  (L1.16a: reopening needs a NAMED enabling change).
