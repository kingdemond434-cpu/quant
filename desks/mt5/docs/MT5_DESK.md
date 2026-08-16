# MT5 Research Desk (XAUUSD) — Visibility Copy

**Do not run anything from this directory.** The desk executes on the local
Windows host (`C:\Users\dell\mt5-research`). This copy exists so every brain
in the repo reads one canonical picture of the MT5 desk.

## What this desk is

A swap-free (Islamic, halal) XAUUSD session-range-breakout book on
VantageMarkets-Live 14 (login 34049153, 633.89 EUR, 1:500), currently
**armed** with 0.01 lot per sleeve.

Four decorrelated daily windows place brackets (buy-stop/sell-stop, SL 1.2xATR
or range span, TP 2R) at 07:00 / 13:00 / 14:00 / 17:00 UTC. Unfilled brackets
are cancelled 20:30 UTC; positions are force-closed 19:30 UTC — never across
the broker's daily 21:00-22:00 UTC trading pause.

## Numbers (2018-2026 dense sample, costs inside R)

- Combined: n=2,812, exp +0.127R, t=6.82, PF 1.37, SR 2.34, maxDD -18.5R
- Model: ~116%/yr arithmetic at 0.01 lot/sleeve (2.7% risk per trade),
  worst historical DD -51%
- Scaling is linear in lot; at 10k EUR use ~0.16 lots/sleeve for the same
  risk profile
- Forward validation starts **Monday 2026-08-17 07:00 UTC** — 50 live trades
  + 14 days before scaling

## Gates the edge passed

t > 2 | WF OOS positive per fold | 24/27 param combos | cost stress at 2x |
replay on live bars 13/13 | n=2,812. Full details in `reports/verdict_breakout.json`.

## Graveyard (do not resurrect without new data)

monday_gap, london_close_momentum, asia_momentum, usd_session_shock,
comex_settlement, dow_effect, all 4 COT families, momentum_volgate,
spread_state_avoidance (marginal, maxDD -49R to -96R).

## Coordination rules for other brains

- The **crypto desk is frozen**: no new alphas, no execution work. Its data
  feeds remain as information inputs. `CASHCARRY_KILL` stays latched.
- The MT5 gateway runs only on the Windows host; do not attempt to run it here.
- If you see a red flag in `MT5_DESK_STATE.json` (e.g. gateway unarmed,
  reconcile failures), report it in the repo — the human + Windows host
  operator act on it.