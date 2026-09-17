"""THE DATA-DISCOVERY SWARM -- for every hypothesis, its missing information and the cheapest
PIT-clean source that could expose it (ledger M12, principal 2026-09-17).

IT IS NOT A STRATEGY MINER AND MUST NOT BECOME ONE. Every other hunter on this desk asks "what
edge can I find in what I already have". This one asks the opposite and only question:

    what LAWFUL, PUBLIC or LICENSED dataset would let the desk measure something it
    cannot measure at all today?

`value_of_data` already prices a missing observation (`ValueOfData = uncertainty reduction /
cost`) and stops, by its own declaration, one move short: it ranks NEEDS and names no SOURCE.
`data_prospector` ranks SOURCES from a catalogue and never asks which hypothesis is blocked on
each. Neither joins the two, so a need sits ranked forever with nothing to buy and a source sits
ranked with nobody asking for it. This organ is that join.

WHERE THE NEEDS COME FROM -- four registers, and each absent one is NAMED, never counted as zero:

    registry      discoveries whose `required_data` names an observable the desk lacks
    value_of_data the priced needs in `reports/VALUE_OF_DATA.json` (its `value` is the
                  information term of the ranking, in R of posterior sd removed)
    research_os   `store.blocking_observables()` -- what the desk recorded as DATA_UNAVAILABLE
    ontology      `mechanism_ontology` observables that no axis in `data/axes` and no
                  `research_api` verb can serve

WHAT "THE DESK LACKS" MEANS, measured rather than assumed: an observable is HELD when a
`research_api` verb already answers it -- `data.query` for bars and prices, `macro.query` for an
axis file actually on disk, `event.query` for the forced-flow calendar -- and MISSING otherwise.
The axes are read off the directory, so adding `fred.json` to `data/axes` retires every need it
serves without anyone editing this file.

THE CATALOGUE IS DECLARED HERE, PUBLIC OR LICENSED ONLY, and every row carries the same six
fields: source, access, pit_status, cadence, cost, how_to_fetch. `pit_status` is the field that
decides whether a source may be used at all -- publication lag and revision policy, in the
vocabulary `libs/data/pit_stamp` already speaks, because a series joined on the period it
DESCRIBES rather than the instant it became READABLE manufactures an edge that cannot exist live.
A source whose vintages are unavailable is recorded with that said out loud rather than left off
the list, so the next session argues with a row instead of rediscovering the gap.

NO CRYPTO-EXCHANGE GROUND (MT5 universe mandate, 2026-08-18). No funding, no perpetual basis, no
exchange-native order book: those are not in this catalogue and `MANDATE_EXCLUDED` says why.
EDGAR is present for the EVENT LANE ONLY -- single-name equities are traded on filings and
earnings, never hunted for statistical hypotheses (two-lane order, 2026-09-06).

THE RANKING, one line, every term measured or declared:

    score = (needs_unblocked x hypotheses_blocked x expected_information_value)
            / (cost + integration_effort)

An unpriced information value takes a DECLARED prior and carries `value_unmeasured`; it never
takes 0.0 (which reads as "measured and worthless") and never takes infinity (which would sort an
unpriced row to the top for not having been priced) -- L1.28a in a denominator.

WHAT IT WRITES. Each ranked source becomes a DISCOVERY (source_type `dataset`, origin `EXTERNAL`,
state UNPROCESSED, payload {observable, source, pit_status, needs, how_to_fetch}) plus a row in
the registry's `sources` table with status `candidate`, kind `dataset`. Both are idempotent: the
registry's content hash dedupes the discovery and the source row is an upsert.

IT MAKES NO NETWORK CALL. The scout catalogues and ranks; `acquire_datasets` is the only organ on
this desk that fetches, on its own clock. A scout that also bought would be two organs and the
second one would be unaccountable.

    python desks/mt5/research/data_scout.py [--dry-run] [--budget-s 120]

numpy only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402

AXES = DESK / "data" / "axes"
VALUE_OF_DATA = DESK / "reports" / "VALUE_OF_DATA.json"
OUT = DESK / "reports" / "DATA_SCOUT.json"

BUDGET_S = 120.0
#: Ranked sources published, recorded and registered per run.
TOP_SOURCES = 40
#: Alternatives named beside the best source on each need.
MAX_ALTERNATIVES = 3
#: Information value for a need nothing has priced. DECLARED, on `value_of_data`'s own unit (R of
#: posterior sd removed): the median unblock value its model publishes is ~0.05, so a tenth of it
#: is a real but modest prior -- never 0.0, never infinity (L1.28a in a denominator).
VALUE_PRIOR = 0.005

RULE = ("for every hypothesis its missing information and the cheapest PIT-clean source that "
        "could expose it")

#: The six fields every catalogue row carries, validated on every run by `validate_catalogue`.
CATALOGUE_FIELDS: tuple[str, ...] = ("source", "access", "pit_status", "cadence", "cost",
                                     "how_to_fetch")
ACCESS = ("free", "licensed")

#: Observables the desk already holds through a `research_api` verb that needs no new dataset.
#: `data.query` answers every one of these off the universe parquet. `open`, `high`, `low` and
#: `close` are DELIBERATELY ABSENT: matched as tokens they retire `open_interest`, which is an
#: exchange observable the desk does not have and cannot get from a bar column.
BARS_MARKS: tuple[str, ...] = ("bar", "bars", "price", "ohlc", "tick_volume", "volume", "return",
                               "candle", "quote")
#: `event.query` answers the forced-flow calendar's own rules (dates, not actuals).
EVENT_MARKS: tuple[str, ...] = ("calendar", "event schedule", "roll date", "expiry", "rebalance")

#: Observables the standing mandate FORBIDS hunting a source for (2026-08-18), named rather than
#: silently omitted so the next session argues with the list instead of rediscovering it. Only
#: crypto-EXCHANGE-NATIVE quantities are here: book observables (depth, spread, microprice,
#: queue imbalance) are legitimate MT5 microstructure the desk already records on its own tape,
#: and excluding those would be timidity rather than the mandate (GROWTH GOVERNANCE).
MANDATE_EXCLUDED: dict[str, str] = {
    "funding_rate": "perpetual-swap funding exists only on crypto exchanges; forbidden universe",
    "perp_spot_spread": "a perpetual-versus-spot basis is crypto-exchange-native",
    "liquidation_notional": "exchange liquidation feeds are crypto-exchange-native",
    "taker_flow_imbalance": "the taker/maker tape is a crypto-exchange-native construct",
    "cross_venue_spread": "multi-venue spread is a crypto-exchange observable; Fusion is one venue",
    "venue_volume_share": "venue share across exchanges is crypto-exchange ground",
}
#: Need kinds no dataset can serve at any price. `value_of_data` says it itself: forward trades
#: "accrue by trading, and the only currency that buys them is calendar time". Shopping for them
#: would fill the queue with rows nothing could ever close -- they are SET ASIDE and counted, not
#: dropped silently.
NOT_PURCHASABLE_KINDS: tuple[str, ...] = ("forward_trades",)

#: THE CATALOGUE. Public or licensed, one row per (observable class, source). `cost` and
#: `integration_effort` are on `data_prospector`'s 1..10 implementation-cost scale so a row here
#: can be ranked against one there. `how_to_fetch` names an EXISTING route where one exists -- a
#: `research_api` verb or a fetcher module on this tree -- and says "no fetcher on this tree" when
#: it does not, because a route nobody wrote is a defect to see rather than a promise to make.
CATALOGUE: tuple[dict[str, Any], ...] = (
    # ---------------------------------------------------------------- macro: rates and prices
    {"source": "FRED (St. Louis Fed) series: DGS2/DGS10/DFII10/T10YIE/DTWEXBGS",
     "observable_class": "macro_rates",
     "observables": ("yield", "rate", "real_rate", "breakeven", "curve", "dollar_index",
                     "interest_differential", "policy_rate"),
     "access": "free", "cadence": "daily",
     "pit_status": ("publication lag ~1 business day; FRED REVISES IN PLACE and carries no "
                    "vintage, so a FRED join is point-in-time only to the observation date -- "
                    "ALFRED below is the vintage-safe twin"),
     "cost": 1.0, "integration_effort": 1.0,
     "how_to_fetch": "research_api macro.query(axis='fred', series=...); research/fetch_fred.py"},
    {"source": "ALFRED vintage archive (same series, as-first-released)",
     "observable_class": "macro_rates",
     "observables": ("yield_vintage", "revision", "real_time_macro", "first_release"),
     "access": "free", "cadence": "daily",
     "pit_status": ("VINTAGE-CLEAN: every observation carries the date it was first published, "
                    "so `available_time` is measured rather than modelled"),
     "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "research/fetch_alfred.py"},
    {"source": "US Treasury daily yield curve (home.treasury.gov CSV)",
     "observable_class": "macro_rates",
     "observables": ("yield", "curve", "tenor", "term_premium"),
     "access": "free", "cadence": "daily",
     "pit_status": "published the same evening; never revised; lag 1 day",
     "cost": 1.0, "integration_effort": 1.0,
     "how_to_fetch": "acquire_datasets seed endpoint (already declared)"},
    # ----------------------------------------------------------------------- positioning
    {"source": "CFTC Commitments of Traders (legacy + financial futures, weekly)",
     "observable_class": "positioning",
     "observables": ("positioning", "cot", "net_position", "open_interest", "commercial",
                     "speculator", "crowding"),
     "access": "free", "cadence": "weekly",
     "pit_status": ("Tuesday snapshot published Friday 15:30 ET -- a 3-day lag that MUST be "
                    "applied; the desk's `cot` axis stamps `knowable_at` at ingest"),
     "cost": 1.0, "integration_effort": 1.0,
     "how_to_fetch": "research_api macro.query(axis='cot', series='<SYM>.net_pct_oi')"},
    {"source": "ICE Commitments of Traders (Brent, gasoil, ICE FX)",
     "observable_class": "positioning",
     "observables": ("positioning", "net_position", "open_interest", "energy_positioning"),
     "access": "free", "cadence": "weekly",
     "pit_status": "Tuesday snapshot published Friday; same 3-day lag as the CFTC report",
     "cost": 1.5, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},
    # --------------------------------------------------- central banks: policy and balance sheet
    {"source": "ECB Data Portal (SDW) -- EXR, BSI, ILM, MIR, policy rates",
     "observable_class": "central_bank",
     "observables": ("balance_sheet", "policy_rate", "reserves", "liquidity", "euro_rates",
                     "fx_reference_rate"),
     "access": "free", "cadence": "daily",
     "pit_status": ("reference rates published 16:00 CET same day; balance-sheet series weekly "
                    "with a ~3-day lag; revisions are republished with a vintage id"),
     "cost": 1.0, "integration_effort": 1.0,
     "how_to_fetch": "research_api macro.query(axis='ecb', series=...)"},
    {"source": "Federal Reserve H.4.1 / H.8 / H.15 statistical releases",
     "observable_class": "central_bank",
     "observables": ("balance_sheet", "reserves", "bank_credit", "repo", "liquidity"),
     "access": "free", "cadence": "weekly",
     "pit_status": "H.4.1 Thursday 16:30 ET for the Wednesday position: 1-day lag, rarely revised",
     "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "Bank of Japan time-series search (balance sheet, JGB holdings, FX intervention)",
     "observable_class": "central_bank",
     "observables": ("balance_sheet", "intervention", "jgb_holdings", "policy_rate", "yen_policy"),
     "access": "free", "cadence": "monthly",
     "pit_status": ("intervention totals published at month end for the prior month: a lag of up "
                    "to 31 days that MUST be modelled, and the single most common look-ahead in "
                    "yen research"),
     "cost": 1.5, "integration_effort": 3.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "Bank of England statistical database (Bankstats, reserves, gilt operations)",
     "observable_class": "central_bank",
     "observables": ("balance_sheet", "policy_rate", "gilt", "reserves", "sterling_policy"),
     "access": "free", "cadence": "monthly",
     "pit_status": "monthly release ~20 days after the reference month; revisions republished",
     "cost": 1.5, "integration_effort": 3.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "SNB data portal (sight deposits, FX reserves, policy rate)",
     "observable_class": "central_bank",
     "observables": ("sight_deposits", "fx_reserves", "intervention", "policy_rate",
                     "franc_policy"),
     "access": "free", "cadence": "weekly",
     "pit_status": ("sight deposits published Monday for the prior week -- the cleanest weekly "
                    "proxy for CHF intervention there is; lag 3 days"),
     "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "BIS data portal -- central bank policy rates (WS_CBPOL), credit, property",
     "observable_class": "central_bank",
     "observables": ("policy_rate", "credit_gap", "global_liquidity", "rate_differential"),
     "access": "free", "cadence": "monthly",
     "pit_status": "monthly bulk CSV, ~10-day lag; the desk's `bis` axis stamps `knowable_at`",
     "cost": 1.0, "integration_effort": 1.0,
     "how_to_fetch": "research_api macro.query(axis='bis', series=...)"},
    # ------------------------------------------------------------------------- FX structure
    {"source": "BIS Triennial Central Bank Survey (FX turnover by pair and venue)",
     "observable_class": "fx_structure",
     "observables": ("turnover", "fx_volume", "liquidity_share", "venue_share", "capacity"),
     "access": "free", "cadence": "quarterly",
     "pit_status": ("TRIENNIAL: the survey is published months after its April reference window, "
                    "so it is a slow-moving CAPACITY prior and never a conditioning signal"),
     "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "BIS effective exchange rate indices (narrow and broad, nominal and real)",
     "observable_class": "fx_structure",
     "observables": ("effective_exchange_rate", "reer", "neer", "valuation"),
     "access": "free", "cadence": "monthly",
     "pit_status": "monthly, ~15-day lag, revised when trade weights are updated",
     "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},
    # ------------------------------------------------------------ exchange public daily data
    {"source": "CME Group daily bulletin -- settlements, volume, open interest, delivery notices",
     "observable_class": "exchange_public",
     "observables": ("settlement", "volume", "open_interest", "delivery", "roll", "basis",
                     "futures_curve", "term_structure"),
     "access": "free", "cadence": "daily",
     "pit_status": ("settlements published the evening of the trade date; delivery notices the "
                    "same evening; the bulletin is final, not revised -- usable next session"),
     "cost": 1.5, "integration_effort": 3.0,
     "how_to_fetch": "research/fetch_futures_curves.py (curve build; bulletin parse not wired)"},
    {"source": "ICE Futures daily settlement and volume reports (Brent, gasoil, ICE FX)",
     "observable_class": "exchange_public",
     "observables": ("settlement", "volume", "open_interest", "futures_curve", "energy_basis"),
     "access": "free", "cadence": "daily",
     "pit_status": "end-of-day report, published the same evening, not revised",
     "cost": 1.5, "integration_effort": 3.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "Eurex daily statistics (settlement prices, volume, OI on DAX/EuroStoxx/Bund)",
     "observable_class": "exchange_public",
     "observables": ("settlement", "volume", "open_interest", "index_futures", "bund",
                     "equity_index_basis"),
     "access": "free", "cadence": "daily",
     "pit_status": "published the same evening for the trade date; final",
     "cost": 1.5, "integration_effort": 3.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "CME CVOL and options settlement surface (public daily files)",
     "observable_class": "exchange_public",
     "observables": ("implied_vol", "vol_surface", "skew", "option_open_interest"),
     "access": "free", "cadence": "daily",
     "pit_status": "same-evening publication for the trade date; final",
     "cost": 2.0, "integration_effort": 4.0, "how_to_fetch": "no fetcher on this tree"},
    # -------------------------------------------------------------------------- energy
    {"source": "EIA -- Weekly Petroleum Status Report, natural gas storage, WTI spot",
     "observable_class": "energy",
     "observables": ("inventory", "crude_stocks", "gas_storage", "production", "refinery_run",
                     "energy_fundamental"),
     "access": "free", "cadence": "weekly",
     "pit_status": ("WPSR Wednesday 10:30 ET for the Friday-ending week: a 5-day lag, and the "
                    "print itself is the event -- revisions are rare and republished"),
     "cost": 1.0, "integration_effort": 2.0,
     "how_to_fetch": "acquire_datasets seed endpoint (RWTCd spot only)"},
    {"source": "IEA Oil Market Report statistics (public tables)",
     "observable_class": "energy",
     "observables": ("demand_forecast", "supply_balance", "oecd_stocks", "energy_fundamental"),
     "access": "licensed",
     "cadence": "monthly",
     "pit_status": ("mid-month release for the prior month; the full dataset is subscription, the "
                    "headline tables are public -- licence read BEFORE any reuse"),
     "cost": 4.0, "integration_effort": 4.0, "how_to_fetch": "no fetcher on this tree"},
    # -------------------------------------------------------------------------- softs
    {"source": "USDA WASDE and NASS crop reports",
     "observable_class": "softs",
     "observables": ("crop_production", "ending_stocks", "yield_forecast", "soft_fundamental",
                     "export_sales"),
     "access": "free", "cadence": "monthly",
     "pit_status": ("WASDE released 12:00 ET on a published calendar date; embargoed until then, "
                    "so the release instant is exact and the lag is zero at that instant"),
     "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "USDA FAS weekly export sales",
     "observable_class": "softs",
     "observables": ("export_sales", "demand", "soft_fundamental"),
     "access": "free", "cadence": "weekly",
     "pit_status": "Thursday 08:30 ET for the week ending the prior Thursday: a 7-day lag",
     "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},
    # -------------------------------------------------------------------------- metals
    {"source": "LBMA precious metals -- daily price auction, vault holdings, clearing statistics",
     "observable_class": "metals",
     "observables": ("gold_benchmark", "vault_holdings", "clearing_volume", "metal_flow",
                     "gold_fundamental"),
     "access": "free", "cadence": "daily",
     "pit_status": ("auction prices same day; vault holdings monthly with a ~1-month lag -- two "
                    "completely different `available_time`s that must not be joined as one"),
     "cost": 1.5, "integration_effort": 3.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "Shanghai Gold Exchange -- premium, withdrawals, deliverable volume",
     "observable_class": "metals",
     "observables": ("sge_premium", "withdrawals", "physical_demand", "metal_flow"),
     "access": "free", "cadence": "daily",
     "pit_status": "published the following Shanghai session; weekly withdrawal tables lag ~7 days",
     "cost": 2.0, "integration_effort": 2.0, "how_to_fetch": "research/fetch_sge_premium.py"},
    {"source": "World Gold Council / ETF holdings (GLD and peers, daily bar list)",
     "observable_class": "metals",
     "observables": ("etf_holdings", "gold_flow", "physical_demand"),
     "access": "free", "cadence": "daily",
     "pit_status": "holdings published the next business day; not revised",
     "cost": 1.0, "integration_effort": 1.0, "how_to_fetch": "research/fetch_gld.py"},
    # ------------------------------------------------------------- national statistics offices
    {"source": "National statistics offices (BLS, ONS, Destatis, INSEE, ABS, StatCan, e-Stat)",
     "observable_class": "national_statistics",
     "observables": ("cpi", "inflation", "employment", "gdp", "trade_balance", "retail_sales",
                     "pmi_official", "actual", "surprise"),
     "access": "free", "cadence": "monthly",
     "pit_status": ("release calendars are published in advance and the print instant is exact; "
                    "BUT most series are REVISED, so only the FIRST RELEASE is point-in-time and "
                    "a vintage table is required to backtest one"),
     "cost": 2.0, "integration_effort": 4.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "Economic release calendar with ACTUAL and CONSENSUS prints",
     "observable_class": "national_statistics",
     "observables": ("actual", "consensus", "surprise", "forecast", "event_reaction"),
     "access": "licensed", "cadence": "daily",
     "pit_status": ("the actual is knowable at the release instant and the consensus only at its "
                    "own survey close; a vendor snapshot without both timestamps cannot be used"),
     "cost": 5.0, "integration_effort": 3.0,
     "how_to_fetch": "no fetcher on this tree (ff_calendar_vintage seat donates prose only)"},
    # ------------------------------------------------------------------ multilateral archives
    {"source": "IMF data (IFS, BOP, COFER reserve currency composition)",
     "observable_class": "multilateral",
     "observables": ("reserves", "reserve_composition", "balance_of_payments", "capital_flow"),
     "access": "free", "cadence": "quarterly",
     "pit_status": "COFER ~3 months after quarter end; IFS monthly with a ~6-week lag; revised",
     "cost": 1.5, "integration_effort": 3.0, "how_to_fetch": "no fetcher on this tree"},
    {"source": "World Bank open data (commodity Pink Sheet, development indicators)",
     "observable_class": "multilateral",
     "observables": ("commodity_index", "terms_of_trade", "country_fundamental"),
     "access": "free", "cadence": "monthly",
     "pit_status": "Pink Sheet published the first business days of the month for the prior month",
     "cost": 1.0, "integration_effort": 2.0, "how_to_fetch": "no fetcher on this tree"},
    # ------------------------------------------------------------------- the event lane only
    {"source": "SEC EDGAR full-text and filing index (8-K, 10-Q, 10-K, 13F)",
     "observable_class": "filings_event_lane",
     "observables": ("filing", "earnings", "guidance", "disclosure", "institutional_holdings"),
     "access": "free", "cadence": "daily",
     "pit_status": ("the acceptance timestamp on each filing IS the availability instant, to the "
                    "second -- the cleanest PIT stamp in this catalogue; 13F is 45 days after "
                    "quarter end and is stale by construction"),
     "cost": 1.0, "integration_effort": 2.0,
     "how_to_fetch": ("no fetcher on this tree; EVENT LANE ONLY -- single names are traded on "
                      "filings and never hunted for statistical hypotheses (2026-09-06)")},
    # ------------------------------------------------------------------- the desk's own tape
    {"source": "Fusion/MT5 tick tape already recorded under data/tape/ticks/<SYM>",
     "observable_class": "own_tape",
     "observables": ("spread", "tick", "depth", "slippage", "execution_cost", "liquidity",
                     "cost_surface", "adverse_move"),
     "access": "free", "cadence": "hourly",
     "pit_status": ("the desk's own recording: `ingested_time` is the fetch instant and there is "
                    "no publication lag at all -- the only source here with none"),
     "cost": 1.0, "integration_effort": 1.0,
     "how_to_fetch": "already collected by the tape recorder; no acquisition needed"},
    {"source": "Fusion/MT5 finer charts (M1/M5/M15) for every book symbol",
     "observable_class": "own_tape",
     "observables": ("m15", "m5", "m1", "intraday_bar", "microstructure_regime"),
     "access": "free", "cadence": "hourly",
     "pit_status": "broker feed, no publication lag; bars are final on close",
     "cost": 1.0, "integration_effort": 1.0,
     "how_to_fetch": "research/fetch_universe.py (already wired for H1; ladder charts partial)"},
)


# ------------------------------------------------------------------------------- small tools

def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it; `os.replace` onto a read-only file is WinError 5."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    for attempt in range(2):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt or not path.exists():
                break
            try:
                os.chmod(path, 0o666)
            except OSError:
                break
        except OSError:
            break
    path.write_text(body, encoding="utf-8")


def _slug(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")[:64] or "unnamed"


def _words(text: Any) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", str(text or "").lower()) if len(w) > 2}


# --------------------------------------------------------------------- what the desk already has

def held_observables(axes_dir: Path | None = None) -> tuple[set[str], dict[str, str]]:
    """(marks the desk already answers, why each one is held).

    MEASURED, NOT ASSUMED. The axes are read off `data/axes`, so dropping a new axis file in
    retires every need it serves without anyone editing this module -- and deleting one puts the
    need back, which is the behaviour a coverage floor that ratchets needs (L1.50).
    """
    marks: set[str] = set()
    why: dict[str, str] = {}
    for mark in BARS_MARKS:
        marks.add(mark)
        why[mark] = "research_api data.query answers this off the universe parquet"
    for mark in EVENT_MARKS:
        marks.add(mark)
        why[mark] = "research_api event.query answers this from forced_flow_calendar's own rules"
    for axis in sorted(Path(axes_dir or AXES).glob("*.json")):
        name = axis.stem.lower()
        marks.add(name)
        why[name] = f"research_api macro.query(axis={name!r}) -- the axis file is on disk"
        doc = _read_json(axis)
        series = doc.get("series") if isinstance(doc, dict) else None
        for key in list(series or {})[:200]:
            token = _slug(key)
            marks.add(token)
            why[token] = f"a series of the {name} axis"
    return marks, why


def mandate_reason(observable: Any) -> str:
    """Why the standing MT5 universe mandate forbids hunting a source for this observable, or ""
    when it does not. NO SOURCE IS EVER SOUGHT for a crypto-exchange-native quantity, and the
    refusal is published per need rather than being an absence somebody later wonders about."""
    low = _slug(observable)
    tokens = _words(observable)
    for key, why in MANDATE_EXCLUDED.items():
        slug = _slug(key)
        if slug in low or slug in tokens:
            return why
    return ""


def is_missing(observable: str, marks: set[str]) -> bool:
    """True when no held mark answers this observable.

    A single-word mark must match a WHOLE token; only a multi-word mark is matched as a phrase.
    That distinction is load-bearing: matching `open` as a substring made `open_interest` read as
    "the desk already has it" -- an exchange observable retired by a bar column.

    A MANDATE-EXCLUDED observable always reports MISSING here, so `gather` refuses it with the
    mandate's own reason instead of a bar column quietly retiring it and the refusal never being
    published.
    """
    low = _slug(observable)
    if not low:
        return False
    if mandate_reason(observable):
        return True
    if low in marks:
        return False
    tokens = _words(observable) | {low}
    for mark in marks:
        slug = _slug(mark)
        if ("_" in slug and slug in low) or slug in tokens:
            return False
    return True


# -------------------------------------------------------------------------- 1. gather the needs

def _need(observable: str, source_register: str, *, hypotheses: int, mechanisms: Sequence[str],
          value: float | None, why: str) -> dict[str, Any]:
    return {"observable": str(observable), "register": source_register,
            "blocked_hypotheses": int(max(hypotheses, 0)),
            "mechanisms": sorted({str(m) for m in mechanisms if m})[:12],
            "value": None if value is None else round(float(value), 8), "why": why}


def needs_from_registry(marks: set[str], *, conn: Any = None, limit: int = 2000
                        ) -> list[dict[str, Any]]:
    """One need per observable a discovery's `required_data` names that the desk lacks."""
    c = conn or R.connect()
    try:
        rows = c.execute("SELECT discovery_id, mechanism, required_data_json FROM discoveries "
                         "WHERE required_data_json IS NOT NULL AND required_data_json NOT IN "
                         "('', 'null', '[]') LIMIT ?", (int(limit),)).fetchall()
    finally:
        if conn is None:
            c.close()
    by_obs: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            wanted = json.loads(str(row["required_data_json"]))
        except ValueError:
            continue
        for item in (wanted if isinstance(wanted, list) else [wanted]):
            obs = str(item or "").strip()
            if not obs or not is_missing(obs, marks):
                continue
            slot = by_obs.setdefault(obs, {"n": 0, "mechs": set()})
            slot["n"] += 1
            slot["mechs"].add(str(row["mechanism"] or "")[:80])
    return [_need(obs, "registry.required_data", hypotheses=slot["n"], mechanisms=slot["mechs"],
                  value=None,
                  why=(f"{slot['n']} registry discovery/ies declare this in required_data and no "
                       f"research_api verb answers it"))
            for obs, slot in sorted(by_obs.items())]


def needs_from_value_of_data(marks: set[str], path: Path | None = None
                             ) -> tuple[list[dict[str, Any]], str]:
    """The priced needs, carrying `value_of_data`'s own number as the information term.

    A `forward_trades` row is SET ASIDE and counted: no dataset on earth sells another twenty
    fills on a live sleeve, and shopping for one would fill the queue with rows nothing could
    ever close.
    """
    doc = _read_json(path or VALUE_OF_DATA)
    if not isinstance(doc, dict) or not isinstance(doc.get("top"), list):
        return [], (f"UNMEASURED: {path or VALUE_OF_DATA} is absent or not in the expected shape, "
                    f"so no need on this run carries a priced information value")
    out: list[dict[str, Any]] = []
    aside = 0
    for row in doc["top"]:
        if not isinstance(row, dict):
            continue
        if str(row.get("kind") or "") in NOT_PURCHASABLE_KINDS:
            aside += 1
            continue
        obs = str(row.get("what") or row.get("need_id") or "").strip()
        if not obs or not is_missing(obs, marks):
            continue
        out.append(_need(obs, "value_of_data", hypotheses=int(row.get("serves") or 0),
                         mechanisms=[str(h) for h in (row.get("for_hypotheses") or [])],
                         value=row.get("value"),
                         why=str(row.get("why") or "")[:240] or "priced by value_of_data"))
    return out, (f"{len(out)} priced need(s) of {len(doc['top'])} published rows; {aside} set "
                 f"aside as not purchasable ({', '.join(NOT_PURCHASABLE_KINDS)})")


def needs_from_research_os(marks: set[str]) -> tuple[list[dict[str, Any]], str]:
    """Observables research_os recorded as DATA_UNAVAILABLE -- the desk's own blocked work."""
    try:
        from libs.research_os import store
        rows = list(store.blocking_observables())
    except Exception as exc:
        return [], f"UNMEASURED: research_os unreachable ({type(exc).__name__}: {exc})"
    out = [_need(str(r.get("observable") or ""), "research_os.blocking_observables",
                 hypotheses=int(r.get("hypotheses_blocked") or 0),
                 mechanisms=[f"mechanism_{i}"
                             for i in range(int(r.get("mechanisms_blocked") or 0))],
                 value=None,
                 why=(f"{r.get('hypotheses_blocked')} failure(s) across "
                      f"{r.get('mechanisms_blocked')} mechanism(s) are in state DATA_UNAVAILABLE "
                      f"on this observable: not refuted, unmeasured"))
           for r in rows if str(r.get("observable") or "").strip()
           and is_missing(str(r.get("observable")), marks)]
    return out, f"{len(rows)} blocking observable(s), {len(out)} of them still missing"


def needs_from_ontology(marks: set[str]) -> tuple[list[dict[str, Any]], str]:
    """Mechanism-contract observables no axis and no verb can serve.

    The ontology is the only register that names what the desk WOULD need to test a mechanism it
    has never been able to touch, which is exactly the blind spot a data scout exists for.
    """
    try:
        from libs.research.mechanism_ontology import CORE_MECHANISMS
    except Exception as exc:
        return [], f"UNMEASURED: the mechanism ontology is unreachable ({type(exc).__name__})"
    by_obs: dict[str, set[str]] = {}
    for mech in CORE_MECHANISMS.values():
        for obs in getattr(mech, "observables", ()):
            if is_missing(str(obs), marks):
                by_obs.setdefault(str(obs), set()).add(str(mech.mechanism_id))
    out = [_need(obs, "mechanism_ontology", hypotheses=len(mechs), mechanisms=sorted(mechs),
                 value=None,
                 why=(f"{len(mechs)} mechanism contract(s) declare this observable as what "
                      f"MEASURES them, and nothing on this desk serves it"))
           for obs, mechs in sorted(by_obs.items())]
    return out, f"{len(CORE_MECHANISMS)} mechanism(s), {len(out)} unserved observable(s)"


def gather(*, conn: Any = None, axes_dir: Path | None = None,
           value_path: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every missing information requirement the desk can name today, deduped by observable.

    A need seen by two registers keeps the LARGER hypothesis count and the MEASURED value, and
    records both registers -- a need nobody priced must not displace one somebody did.
    """
    marks, why_held = held_observables(axes_dir)
    registers: dict[str, Any] = {"held_marks": len(marks)}
    rows = needs_from_registry(marks, conn=conn)
    registers["registry"] = f"{len(rows)} need(s) from discovery required_data"
    priced, note = needs_from_value_of_data(marks, value_path)
    registers["value_of_data"] = note
    blocked, note = needs_from_research_os(marks)
    registers["research_os"] = note
    onto, note = needs_from_ontology(marks)
    registers["mechanism_ontology"] = note

    merged: dict[str, dict[str, Any]] = {}
    refused: dict[str, str] = {}
    for need in [*rows, *priced, *blocked, *onto]:
        key = _slug(need["observable"])
        forbidden = mandate_reason(need["observable"])
        if forbidden:
            refused[str(need["observable"])] = forbidden
            continue
        if key not in merged:
            merged[key] = {**need, "registers": [need["register"]]}
            continue
        have = merged[key]
        have["registers"].append(need["register"])
        have["blocked_hypotheses"] = max(have["blocked_hypotheses"], need["blocked_hypotheses"])
        have["mechanisms"] = sorted(set(have["mechanisms"]) | set(need["mechanisms"]))[:12]
        if have.get("value") is None and need.get("value") is not None:
            have["value"], have["why"] = need["value"], need["why"]
    registers["held_examples"] = sorted(why_held)[:12]
    registers["mandate_refused"] = refused
    return sorted(merged.values(), key=lambda r: str(r["observable"])), registers


# ------------------------------------------------------------------------- 2. the catalogue

def validate_catalogue(catalogue: Sequence[Mapping[str, Any]] | None = None
                       ) -> tuple[list[dict[str, Any]], list[str]]:
    """(usable rows, complaints). A row missing one of the six fields is REFUSED and named -- a
    source with no declared PIT status or no declared access is not a source this desk may buy."""
    complaints: list[str] = []
    usable: list[dict[str, Any]] = []
    for row in (catalogue if catalogue is not None else CATALOGUE):
        name = str(row.get("source") or "<unnamed>")
        missing = [f for f in CATALOGUE_FIELDS if not str(row.get(f, "")).strip()]
        if missing:
            complaints.append(f"{name}: missing {', '.join(missing)}")
            continue
        if str(row.get("access")) not in ACCESS:
            complaints.append(f"{name}: access {row.get('access')!r} is not one of {ACCESS}")
            continue
        usable.append(dict(row))
    return usable, complaints


def serves(need: Mapping[str, Any], entry: Mapping[str, Any]) -> bool:
    """Does this catalogue row expose this need's observable? Token overlap on the row's declared
    observable vocabulary and its class -- declared, so it can be argued with."""
    tokens = _words(need.get("observable")) | {_slug(need.get("observable"))}
    for obs in (*entry.get("observables", ()), entry.get("observable_class", "")):
        low = _slug(obs)
        if not low:
            continue
        if low in tokens or any(low in t or t in low for t in tokens if len(t) > 3):
            return True
    return False


# ---------------------------------------------------------------------------- 3. the ranking

def rank_sources(need: Mapping[str, Any], catalogue: Sequence[Mapping[str, Any]]
                 ) -> list[dict[str, Any]]:
    """Every catalogue row that could expose this need, best first.

    score = (needs_unblocked x hypotheses_blocked x information_value) / (cost + effort), with the
    information value taking `VALUE_PRIOR` and a `value_unmeasured` flag when nothing priced it.
    """
    value = need.get("value")
    unmeasured = value is None
    info = VALUE_PRIOR if unmeasured else float(value)
    hyps = max(int(need.get("blocked_hypotheses") or 0), 1)
    out: list[dict[str, Any]] = []
    for entry in catalogue:
        if not serves(need, entry):
            continue
        denom = float(entry.get("cost") or 1.0) + float(entry.get("integration_effort") or 1.0)
        out.append({
            "source": entry["source"], "observable_class": entry.get("observable_class", ""),
            "access": entry["access"], "pit_status": entry["pit_status"],
            "cadence": entry["cadence"], "cost": float(entry["cost"]),
            "integration_effort": float(entry.get("integration_effort") or 1.0),
            "how_to_fetch": entry["how_to_fetch"],
            "score": round(1.0 * hyps * info / max(denom, 1e-6), 8),
            "value_used": round(info, 8), "value_unmeasured": bool(unmeasured),
        })
    return sorted(out, key=lambda r: (-r["score"], r["cost"], r["source"]))


def rank(needs: Sequence[Mapping[str, Any]], catalogue: Sequence[Mapping[str, Any]]
         ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(needs with their best source and alternatives, ranked sources across all needs).

    A source's own rank sums the scores of every need it unblocks, so a row that serves six needs
    outranks one that serves a single richer need at the same price -- which is the whole reason
    `needs_unblocked` is a term at all.
    """
    rows: list[dict[str, Any]] = []
    by_source: dict[str, dict[str, Any]] = {}
    for need in needs:
        options = rank_sources(need, catalogue)
        rows.append({
            "observable": need["observable"],
            "blocked_hypotheses": int(need.get("blocked_hypotheses") or 0),
            "mechanisms": list(need.get("mechanisms") or []),
            "registers": list(need.get("registers") or ([need["register"]]
                                                        if need.get("register") else [])),
            "value": need.get("value"), "why": need.get("why"),
            "best_source": options[0] if options else None,
            "alternatives": options[1:1 + MAX_ALTERNATIVES],
            "unserved": not options,
        })
        for opt in options:
            slot = by_source.setdefault(opt["source"], {**opt, "needs": [], "score": 0.0,
                                                       "needs_unblocked": 0,
                                                       "hypotheses_blocked": 0})
            slot["needs"].append(need["observable"])
            slot["needs_unblocked"] += 1
            slot["hypotheses_blocked"] += int(need.get("blocked_hypotheses") or 0)
            slot["score"] = round(slot["score"] + float(opt["score"]), 8)
    ranked = sorted(by_source.values(), key=lambda r: (-r["score"], r["cost"], r["source"]))
    return rows, ranked


# ------------------------------------------------------------------ 4. what the scout records

def _register_source(entry: Mapping[str, Any], *, conn: Any = None) -> bool:
    """One `candidate` row of kind `dataset` in the registry's `sources` table, upserted.

    WRITTEN HERE RATHER THAN IN `libs/moat/registry.py` because that module ships no writer for
    the `sources` table -- NAMED as a defect rather than hidden: the right home for this is a
    `record_source` beside `record_discovery`, and until it exists this is the one organ that
    touches the table directly.
    """
    c = conn or R.connect()
    try:
        sid = f"dataset:{_slug(entry['source'])}"
        meta = {k: entry.get(k) for k in ("observable_class", "cadence", "pit_status",
                                          "how_to_fetch", "cost", "integration_effort",
                                          "needs_unblocked", "hypotheses_blocked", "score")}
        row = c.execute("SELECT source_id FROM sources WHERE source_id=?", (sid,)).fetchone()
        licence = (f"{entry.get('access')} -- PIT: {entry.get('pit_status')}")[:900]
        if row is None:
            c.execute("INSERT INTO sources(source_id, url, kind, language, country, "
                      "asset_classes_json, discovered_from, discovered_via, first_seen, "
                      "last_crawled, status, licence_note, meta_json) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (sid, "", "dataset", "", "", json.dumps([]), "data_scout",
                       str(entry.get("observable_class") or ""), _now(), None, "candidate",
                       licence, json.dumps(meta, sort_keys=True, default=str)))
        else:
            c.execute("UPDATE sources SET status=?, licence_note=?, meta_json=?, "
                      "discovered_via=? WHERE source_id=?",
                      ("candidate", licence, json.dumps(meta, sort_keys=True, default=str),
                       str(entry.get("observable_class") or ""), sid))
        c.commit()
        return row is None
    finally:
        if conn is None:
            c.close()


def record(ranked: Sequence[Mapping[str, Any]], *, conn: Any = None, limit: int = TOP_SOURCES
           ) -> dict[str, int]:
    """Each ranked source becomes a DISCOVERY and a candidate `sources` row. Idempotent: the
    registry's content hash dedupes the discovery and the source row is an upsert."""
    out = {"discoveries_recorded": 0, "discoveries_seen": 0, "sources_registered": 0,
           "sources_seen": 0}
    for entry in list(ranked)[:max(int(limit), 0)]:
        sid = f"dataset:{_slug(entry['source'])}"
        payload = {"observable": list(entry.get("needs") or [])[:20], "source": entry["source"],
                   "pit_status": entry["pit_status"], "needs": list(entry.get("needs") or [])[:20],
                   "how_to_fetch": entry["how_to_fetch"], "access": entry["access"],
                   "cadence": entry["cadence"], "cost": entry["cost"],
                   "integration_effort": entry.get("integration_effort"),
                   "score": entry.get("score")}
        # THE DEDUPE KEY IS THE SOURCE, NOT THE NEEDS. `record_discovery` hashes (source,
        # mechanism, assets, rule); naming the current need list in the mechanism would mint a
        # fresh discovery every time the need set shifted, and the same dataset would accumulate
        # a row per pass. The needs ride in the payload, where they belong.
        _did, created = R.record_discovery(
            source_id=sid, source_type="dataset",
            mechanism=f"data acquisition: {entry['source']}"[:400],
            origin="EXTERNAL", generator="data_scout",
            assets=[], exact_rule_if_known="", required_data=list(entry.get("needs") or [])[:20],
            pit_requirements=[entry["pit_status"]], information="external_dataset",
            economic_rationale=(f"{entry.get('needs_unblocked')} need(s) and "
                                f"{entry.get('hypotheses_blocked')} blocked hypothesis/es are "
                                f"waiting on this observable"),
            falsifier=("the series arrives with no usable publication lag or vintage, so it "
                       "cannot be joined point-in-time"),
            payload=payload, conn=conn)
        out["discoveries_recorded"] += int(created)
        out["discoveries_seen"] += 1
        out["sources_registered"] += int(_register_source(entry, conn=conn))
        out["sources_seen"] += 1
    return out


def build(*, budget_s: float = BUDGET_S, dry_run: bool = False, conn: Any = None,
          axes_dir: Path | None = None, value_path: Path | None = None,
          catalogue: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Gather, catalogue, rank and -- unless dry -- record. Returns the artifact."""
    t0 = time.monotonic()
    c = conn or R.connect()
    try:
        needs, registers = gather(conn=c, axes_dir=axes_dir, value_path=value_path)
        usable, complaints = validate_catalogue(catalogue)
        rows, ranked = rank(needs, usable)
        unmeasured: list[dict[str, str]] = []
        for key in ("value_of_data", "research_os", "mechanism_ontology"):
            note = str(registers.get(key) or "")
            if note.startswith("UNMEASURED"):
                unmeasured.append({"what": key, "why": note})
        for row in rows:
            if row["unserved"]:
                unmeasured.append({
                    "what": str(row["observable"]),
                    "why": ("no catalogue row exposes this observable; the gap is published so "
                            "the catalogue can be argued with rather than quietly widened")})
        for bad in complaints:
            unmeasured.append({"what": "catalogue_row", "why": bad})
        if not needs:
            unmeasured.append({"what": "needs", "why": (
                "no register named a missing observable this pass; an empty need list is a "
                "measurement of the desk's coverage, not an idle organ (L1.28a)")})
        spent = time.monotonic() - t0
        wrote = {"discoveries_recorded": 0, "sources_registered": 0}
        if not dry_run and spent < budget_s:
            wrote = record(ranked, conn=c)
        elif not dry_run:
            unmeasured.append({"what": "record", "why": f"budget: {budget_s:g}s spent gathering"})
        values = [float(r["value"]) for r in rows if r.get("value") is not None]
        return {
            "at": _now(), "n_needs": len(rows), "needs": rows,
            "catalogue_size": len(usable),
            "catalogue_classes": sorted({str(e.get("observable_class") or "") for e in usable}),
            "ranked_sources": [{k: v for k, v in r.items() if k != "needs"} | {
                "needs": list(r.get("needs") or [])[:8]} for r in ranked[:TOP_SOURCES]],
            "discoveries_recorded": int(wrote.get("discoveries_recorded", 0)),
            "sources_registered": int(wrote.get("sources_registered", 0)),
            "unmeasured": unmeasured,
            "registers": registers,
            "mandate_excluded": dict(MANDATE_EXCLUDED),
            "model": {
                "score": ("(needs_unblocked x hypotheses_blocked x expected_information_value) "
                          "/ (cost + integration_effort)"),
                "value_unit": "R of posterior sd removed (value_of_data's own unit)",
                "value_prior": VALUE_PRIOR,
                "n_values_measured": len(values),
                "median_measured_value": (round(float(np.median(values)), 8) if values
                                          else "UNMEASURED"),
                "why_not_zero": ("an unpriced need takes a DECLARED prior, never 0.0 (which reads "
                                 "as measured and worthless) and never infinity (which would "
                                 "sort it to the top for not having been priced)")},
            "boundary": ("this organ makes no network call: it catalogues and ranks, and "
                         "acquire_datasets is the only thing on this desk that fetches"),
            "seconds": round(time.monotonic() - t0, 2), "dry_run": bool(dry_run), "rule": RULE,
        }
    finally:
        if conn is None:
            c.close()


def render(doc: Mapping[str, Any]) -> list[str]:
    lines = [f"DATA SCOUT  {doc['n_needs']} missing information requirement(s) against a "
             f"{doc['catalogue_size']}-row catalogue "
             f"({len(doc['catalogue_classes'])} class(es))  [{doc['rule']}]",
             "  registers: " + "; ".join(f"{k}={v}" for k, v in (doc.get("registers") or {}).items()
                                         if k not in ("held_examples", "held_marks"))]
    for row in (doc.get("needs") or [])[:8]:
        best = row.get("best_source") or {}
        lines.append(f"  {str(row['observable'])[:38]:<38} blocks {row['blocked_hypotheses']:>4} "
                     f"-> {str(best.get('source') or 'NO SOURCE IN THE CATALOGUE')[:56]}")
    lines.append(f"  recorded {doc['discoveries_recorded']} new discovery/ies and "
                 f"{doc['sources_registered']} new candidate source(s); "
                 f"{len(doc.get('unmeasured') or [])} named absence(s)")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="for every hypothesis its missing information and the cheapest PIT-clean "
                    "source that could expose it")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S,
                    help=f"seconds for the whole run (default {BUDGET_S:g})")
    ap.add_argument("--dry-run", action="store_true",
                    help="gather, rank and print; record no discovery, register no source, "
                         "write no artifact")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run)
    for line in render(doc):
        print(line)
    if a.dry_run:
        print("  --dry-run: nothing recorded, nothing registered, nothing written")
        return 0
    _write_atomic(OUT, doc)
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
