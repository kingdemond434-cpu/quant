# Certified-book promotion: the desktop-pass spec (2026-10-06)

Principal, 2026-10-06: "all promising max uncorrelated pf sleeves out of current certis fr promotions
i want to put them on mt5 n e8 early, the max growth n promising sleeve book".

The cloud cannot make this change. The edit to the live sizing path was refused (auto mode, Production
Deploy), so it runs here, behind the principal's Allow. This file is the spec. Nothing in it is applied yet.

## 0. First, on the box
1. Check, and restore if it is missing, `C:\opt\quant\.venv`. The MT5 tasks call
   `.venv\Scripts\python.exe`, so without it the promoter, the heavy scans and pf_allocator do
   not run. UNVERIFIED: one report says the venv is missing and LIVE is 0, but it cites no artifact,
   and the last committed sleeves.json (09-28) reads LIVE 40 / STANDBY 26. Read the box's own
   sleeves.json and do not assume any sleeve's current status.
2. Run `python desks/mt5/research/kelly_survival.py --book` and read `reports/KELLY_SURVIVAL.json` -> `book`.
   On the box it reads the canonical store (847 certificates on 10-06). Any certificate the allocator
   never priced is replayed through `pf_allocator.certified_evidence` (cached a day), and up to 24
   decorrelated positive-mean ones join the search. `book.unpriced` says how many. Use the box's
   numbers, not the git-snapshot ones below.

## 1. The gateway sizes from the book
THE SIZES TO DEPLOY (principal 2026-10-06 21:10Z: go live this way on both accounts, one-time
exception). Each value is risk per trade as a fraction of equity, keyed the allocator's way:

| account | book key | fraction |
|---|---|---|
| Fusion | `EURZAR_overnight_gap_decay_asia` | 0.098 |
| Fusion | `USDZAR_overnight_gap_decay_asia` | 0.100 |
| Fusion | `AUDCHF_overnight_gap_decay_asia` | 0.100 |
| Fusion | `gold_asia` | 0.082 |
| E8 | `gold_asia` | 0.010 |
| E8 | `AUDCHF_overnight_gap_decay_asia` | 0.010 |

No `USDJPY_session_range_breakout_*` key in either account (Reddit-only lineage, #162 quarantine).
Every key NOT in this table keeps whatever the allocator set, including 0 (no order).

- `mt5desk/kelly_sizing.py`: add `load_kelly_book(path, venue)`, mirroring `load_kelly_survival`.
  It reads `book.<venue>.heat` and returns None when the file is absent, older than 2h, or not OK.
  It keeps `gold_*` keys: `bracket_lane_lot` passes a `sized_by == "allocator_book"` row's
  `risk_frac` straight into `gold_book_lot`, so `gold_asia` sizes from the book like any other
  sleeve.
- Put the overlay at ONE place, the end of `allocator_book()` in `mt5desk/gateway.py`:
  `book = {**(book or {}), **kelly}`, append `"; kelly book sets N"` to `why`, and return. Both
  call sites then see it: the sizing loop (`_book, _book_why = allocator_book()`) and the
  decision-context memo. Overlaying at the call site instead would leave decision rows showing
  the allocator's h while orders go out at the kelly fraction.
  - WITHOUT #261 (live as of 2f35a6352): that is the whole change. The loop's `_book_key` joins
    keys to sleeve rows. `from_book` sets `risk_frac = h`, and `promoted_lot` / `gold_book_lot`
    deploy it with no floor or ramp. `MAX_RISK_FRAC` 0.10 caps it, which every size above
    respects.
  - WITH #261 (`claude/allocator-dynamic-20261006`, open): the overlay still goes at the end of
    `allocator_book()`, AFTER #261's `_note_consumed_allocation(...)` call, so
    `allocator_book.consumed` still names the pf_allocation decision. Then:
    1. `book_shares` splits a key's h across rows that share it. The kelly keys are cell-level,
       so if two LIVE rows join one key (e.g. two EURZAR gap-decay variants) each gets h/2. That
       is intended: one bet, one fraction.
    2. #261's `new_risk_gate` still governs. When release, reconcile or terminal checks say no,
       no new risk is sent, whatever the book says. The overlay never bypasses it.
    3. Record `st["kelly_book"] = {"venue", "n", "generated_at"}` beside `consumed_decision_id`,
       so the pass shows which overlay it ran.
    Apply in either order. If #261 lands second, re-apply the three-line overlay at the end of
    its `allocator_book()`. Its rewrite of that function would otherwise drop it.
- READ AT ORDER TIME. `research/book_trigger.py` (on the allocator trigger's ~20s pass, #261) re-solves
  the book within one tick of a fill, a 1% equity move, a certificate change, a spread or swap
  regime change, or a new allocation. So the reader must re-read KELLY_SURVIVAL.json every pass and never
  cache it across passes; a solve that lands between passes is sized from on the next one.
- The overlay applies only while the kelly book is fresh (<= 2h). A stale or absent book leaves
  the allocator's book untouched, and the heat-floor fallback is unchanged.
- E8: `prop/e8_executor.py` / `e8_book.py` size non-gold at `RISK_FRAC` 0.15%. Read
  `book.e8.heat` the same way and fall back to `RISK_FRAC`. To deploy the table's E8 sizes, the
  E8 run of `--book` must emit them. Until the box has a cached E8 catalogue it reports
  UNMEASURED, so write the two E8 keys above into the reader's override for this one-time
  exception and log that they came from this spec.

## 2. Admit and promote the sleeves
- `data/live_sleeve_policy.json`: admit the book's symbols (on the git snapshot: EURZAR, USDZAR,
  AUDCHF), or apply the queued `live_symbols ["*"]`. Keep the discovered and M15 bans.
- The rows must reach LIVE through the promoter (a fresh pf_allocation.json, two admitting heavy scans,
  a measured cost basis), or through the principal-confirmed promotion record the promoter
  supports (`promoter_principal_override.patch`). Never by hand-editing `status`.
- Check: the gateway logs "kelly book sets N sleeve(s)", and the first fills land at the solved fractions.

## Git-snapshot answer (certs 09-16, worlds 09-28), provisional
Re-solved 10-06 21:30Z after the terms fence dropped USDJPY SRB (Reddit-only lineage, PR #162;
`--book` now excludes such cells itself). Do NOT admit or promote USDJPY session_range_breakout
from this book.
Fusion: EURZAR, AUDCHF and USDZAR overnight gap decay at about 10% each, gold_asia 8.2% (0.01 lot).
Total heat 38.4%. P(<=20% equity in 60d) is 3.3% as estimated and 4.25% with edges halved.
Today's three gold windows at 0.02 lot read 13%.
E8 (zuck 21:10Z, one-time exception, pass within about a month): gold_asia 1.0% and AUDCHF 1.0%
risk per trade (2% total per day). P(pass within 30d) 28%, median 38 days, 92% eventual pass, breach
4.5% as estimated and 16% with edges halved. 95% within 30 days is not reachable at any risk.
Fallback if the halved-edge breach is unacceptable: 0.75% each (52-day median, breach <=5% both ways).
Frontier table: /mnt/project-files/sizing/CERT_BOOK_2026-10-06.md.
Final sizes for the desktop pass. Fusion: EURZAR 9.8%, USDZAR 10%, AUDCHF 10%, gold_asia 8.2%.
E8: gold_asia 1.0%, AUDCHF 1.0%. Do not include USDJPY SRB.
Not admitted: CHFNOK carry (live -3.67R/17), nine gap-decay crosses the worlds price at or below 0,
XAUUSD SRB (correlation 0.94 with gold_asia).
