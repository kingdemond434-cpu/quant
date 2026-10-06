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
- `mt5desk/kelly_sizing.py`: add `load_kelly_book(path, venue)`. Mirror `load_kelly_survival`:
  `book.<venue>.heat`, None when the file is absent, older than 2h or not OK. Skip `gold_*` keys,
  which keep their lot path.
- `mt5desk/gateway.py`, right after `_book, _book_why = allocator_book()`: if the kelly book is present,
  set `_book = {**(_book or {}), **kelly_book}` and log it. Keys are `SYMBOL_family_selector`, which
  `_book_key` already joins to sleeve rows. `from_book` then sizes at `min(h, MAX_RISK_FRAC)`
  with no 3% floor and no ramp.
- E8: `prop/e8_executor.py` / `e8_book.py` size non-gold at `RISK_FRAC` 0.15%. Read `book.e8.heat`
  the same way, falling back to `RISK_FRAC`.

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
E8: gold_asia and AUDCHF at 0.375% each (0.75% total daily risk). P(pass) 95%, median 108 days,
P(fail) 2.0%.
Not admitted: CHFNOK carry (live -3.67R/17), nine gap-decay crosses the worlds price at or below 0,
XAUUSD SRB (correlation 0.94 with gold_asia).
