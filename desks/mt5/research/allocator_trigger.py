"""ALLOCATOR TRIGGERS -- the book re-solves when the world changes, not when the clock says so.

PRINCIPAL, 2026-09-23: "make sure the allocator is 24/7 and not slow, and trades on instant macro
news -- the allocation dynamically switches sleeves, instant, for maximum growth, cross-asset."

WHAT WAS WRONG. `pf_allocator` re-solved on a clock and on nothing else. A macro surprise at
:03, a regime transition at :07, a certificate minted at :11 and a fill at :19 all waited for the
top of the hour, and the book that traded through them was solved against a world that no longer
existed. An hour is not "instant", and the cost is not theoretical: the sleeve the new state
favours is the one the book is NOT holding for up to sixty minutes.

WHAT THIS DOES. It watches the artifacts that carry a state change, each with the signature that
makes it a CHANGE rather than a rewrite, and when one moves it fires `pf_allocator --mode fast`
immediately. The slow full solve keeps its own cadence as the backstop -- this adds reactions, it
never replaces the hourly pass.

  macro_surprise          reports/MACRO_VIEW.json        the macro labels / surprise block
  regime_transition       data/regime_state.json,
                          reports/REGIME_ROUTER.json     the regime the router is routing to
  certificate_change      data/sleeve_registry.json      a certificate arriving or dying
  fill                    data/gateway_state.json        realised risk moved at the venue
  cost_capacity_revision  reports/NET_EDGE.json          net-of-cost or capacity was re-priced
  news_resolve_request    data/allocator_resolve_request.json
                                                         `news_event_stream` asked for a re-solve
  equity_move             data/gateway_state.json        Fusion equity moved > k x its measured
                          (else data/account_state.json) daily volatility since the last version
                          reports/E8_GOLD.json           the same, for the E8 account
  cost_regime             data/cost_truth_quotes.json    a sleeve symbol's live spread or swap
                                                         left its dispersion band
  drift_health            reports/DRIFT.json             a sleeve's hazard verdict or hazard band
                                                         moved, or the book verdict did

ANCHORED FINGERPRINTS (2026-10-06). The first six inputs are hashed: any change to the watched
keys is a change. Equity and quotes cannot work that way -- equity moves on every tick of an
open position and a spread breathes by a point every minute, so a hash would make every rewrite a
re-solve. Those three sources carry an ANCHOR in their OBSERVED record: the values the latest
version recorded. A reading becomes a new version only when it leaves the anchor's band, and the
anchor moves only then, so a slow drift accumulates against it until it is material and noise
inside the band never moves the signature at all. Once that version is consumed, the anchor IS
the value the landed decision used. An unreadable reading is not an observation: the previous
signature and anchor stand. The bands, and what each is derived from, are at `_equity_band` and
`_cost_fingerprint`; DRIFT.json needs no band beyond the drift monitor's own declared lines, so it
is a plain hash of the fields the allocator reads from it and nothing else.

THE THREE LEDGERS (2026-10-06). The first version kept ONE record per input, `seen`, and wrote it
on every pass BEFORE deciding whether to solve. So a change that arrived inside the 60s debounce
was recorded as seen, logged as "served by the next pass, not dropped" -- and the next pass
compared against the record that already held it, saw no change, and never served it. The same
held for a solve that failed: the change was seen, the solve did not land, and nothing would ever
fire for it again. The log row promised a retry that the state made impossible. And "landed" was
read off `generated_utc` moving forward, which the HOURLY leg also moves: a fast solve that stood
down on the allocator lock while the hourly pass wrote a book read as a landed reaction.

Each watched input now carries three separate records in `data/allocator_trigger_state.json`:

  OBSERVED   the latest version on disk (a monotone per-input sequence number plus the signature;
             the sequence is what orders versions, because a signature can return to an old value
             and A -> B -> A is two changes, not zero)
  PENDING    every version observed and not yet consumed by a landed decision. It survives the
             debounce, a failed solve, a timeout, a stand-down and a process restart, because it
             is only ever removed by the step below
  CONSUMED   the version a LANDED decision actually used

A decision has LANDED only when `pf_allocation.json` carries a `decision_id` together with the
input versions it consumed, and those versions echo the request this organ issued. A newer
timestamp is not proof of anything. A solve issued with versions V can consume only V: a version
observed after the request was issued has a higher sequence number and stays pending, and an
echo that claims a version this organ never sent is refused. The contract the solver must honour
is in `_request_env` / `_decision_of` and in the report's `decision_contract` block.

WHY IT IS SAFE UNDER GROWTH GOVERNANCE. It fires the SAME solver the hourly leg fires, with the
same heat law, the same floor and the same certificate contest. It sets no fraction and passes no
override: a re-solve can only reallocate between sleeves inside the heat the law already
resolved. The only thing it passes the solver is the list of input versions it is asking about,
and the solver echoes them back -- an identifier, never a parameter. Every re-solve records
`heat_before` and `heat_after` so the two-sidedness is a MEASUREMENT -- a reaction that lowered
total heat would show up here as its own defect rather than hiding inside an average.

CROSS-ASSET BY CONSTRUCTION, and that is the solver's property, not this organ's: `pf_allocator`
solves E[log W] over the WHOLE book at once, so gold, FX, indices and the rest compete for the
same heat on their conditional expected log growth. This organ only decides WHEN that joint solve
happens.

REACTION LATENCY IS PUBLISHED, so "not slow" is a number. Every consumed version records the
change's OWN start (its timestamp field, else its file mtime, clamped into the window in which
this organ could have seen it) and the landed decision that consumed it;
`reports/ALLOCATOR_REACTION.json` carries p50 / p95 / p99 over every sample and per kind, set
against the 20s poll and the 60s solve gap, so a regression is visible the hour it happens.

    python desks/mt5/research/allocator_trigger.py --once --budget-s 600
    python desks/mt5/research/allocator_trigger.py --resident --interval-s 20   # the 24/7 shape
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import inspect
import json
import math
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT = REPORTS / "ALLOCATOR_REACTION.json"
#: Append-only: one row per solve attempt and one per consumed input version. The report is a
#: summary and is overwritten; this is the record a latency regression is measured against.
LOG = DATA / "allocator_reactions.jsonl"
#: The three ledgers (observed / pending / consumed) per watched input. Written atomically.
STATE = DATA / "allocator_trigger_state.json"
#: One trigger pass at a time. The resident and the hourly `--once` leg both run this module; two
#: read-modify-write passes over STATE would let the later writer erase a version the earlier
#: one had just made pending -- the very loss this file exists to prevent.
LOCK = DATA / "allocator_trigger.lock"
ALLOCATION = REPORTS / "pf_allocation.json"
#: Written by `news_event_stream` (its RESOLVE_REQUEST) only when a pass produced requests.
RESOLVE_REQUEST = DATA / "allocator_resolve_request.json"

#: The poll interval of the 24/7 resident. Not a tuning knob: it is the smallest interval at
#: which the watched artifacts can change (their producers are minute-scale at best), and a
#: faster poll would spend CPU re-hashing files that cannot have moved.
DEFAULT_INTERVAL_S = 20.0
#: A fast solve costs ~15-30s on this box. Two firings inside one of those would queue behind the
#: allocator's own lock and the second would stand down with nothing to add, so a firing waits
#: this long for the previous one to land. It is a DEBOUNCE, not a rate limit: a trigger that
#: arrives during the wait stays PENDING and is served by the first pass after the gap.
#: (pf_allocator's own docstring prices `--mode fast` at "~5 min"; the 15-30s figure above is
#: this file's claim and the published `solve_wall_s` samples are what settle it. Neither
#: constant is changed here: the gap is measured from the END of the previous solve, so it bounds
#: solver occupancy either way.)
MIN_SOLVE_GAP_S = 60.0
#: After a solve that did not LAND (non-zero rc, timeout, stand-down, or an output without the
#: decision contract) the next attempt waits MIN_SOLVE_GAP_S * 2**(failures-1), capped here.
#: Without the cap a solver that never honours the contract would be retried every 60s forever;
#: with it the retry rate falls to four an hour, and the hourly full solve stays the backstop.
RETRY_BACKOFF_CAP_S = 900.0
#: The single env var the trigger hands the solver: {"request_id", "input_versions"}.
REQUEST_ENV = "QUANT_ALLOC_TRIGGER_REQUEST"
STATE_SCHEMA = 2
#: Bounds on what the state file carries. Pending is never truncated by age -- only by count, and
#: then the OLDEST entry is kept (it is the one the latency is measured from) with the newest.
MAX_PENDING_PER_INPUT = 64
MAX_ISSUED = 24
MAX_APPLIED = 64
MAX_SAMPLES = 512

#: EQUITY MATERIALITY. A move is material when |ln(equity / anchor)| > EQUITY_K_SIGMA x the
#: book's measured DAILY log-equity volatility. k = 1: a move the size of an ordinary day's move
#: is a move the hourly backstop would otherwise sit on for up to an hour, while anything inside
#: one daily sigma is the noise the last solve already sized through (its worlds are drawn at
#: that volatility). The sigma is measured, in this order: (1) this organ's own daily equity
#: closes (equity incl. floating, one per UTC day, kept on the input's record); (2) the realised
#: daily P&L reconstructed from the deal ledger in data/cost_truth_quotes.json (balance rebuilt
#: by running sum, deposits excluded from P&L, weekdays only) -- realised only, so it UNDER-reads
#: a book with open risk, which errs toward firing; (3) EQUITY_DEFAULT_DAILY_VOL, ONLY when
#: neither has EQUITY_MIN_DAYS of history. Which one was used is published per pass.
EQUITY_K_SIGMA = 1.0
EQUITY_MIN_DAYS = 10
#: The stated fallback, used only when no history exists. Not measured: a prior of the order of
#: a diversified FX/metals book at the 20-30% heat law. Published as "DEFAULT" when it binds.
EQUITY_DEFAULT_DAILY_VOL = 0.01
EQUITY_MAX_CLOSES = 120
#: COST MATERIALITY floor, in log2 units: a doubling. It is the bucket width `book_trigger` uses
#: for the same quotes (one regime definition on the box, not two), and the floor under the
#: symbol's own measured dispersion log2(p90/p50) from data/cost_surface.json, because spreads
#: are quoted in whole points and a 1 -> 2 point tick is a doubling that means nothing. Swap has
#: no measured dispersion anywhere on the box, so its band IS this floor, plus any sign change.
COST_LOG2_FLOOR = 1.0
#: drift_monitor's own lines (perishability.HAZARD_AT_RISK / HAZARD_BREAKING), read from the
#: library at call time; these are only the fallback if the import fails.
HAZARD_BANDS_FALLBACK = (0.15, 0.35)


class Source:
    """One watched artifact: what makes it a CHANGE, and when the change happened."""

    def __init__(self, kind: str, path: Path, keys: tuple[str, ...], why: str, *,
                 fires_on_absent: bool = True, requires_nonempty: str | None = None,
                 first_sight_pending: bool = False,
                 fingerprint: Callable[..., tuple[str, Any, dict[str, Any]]] | None = None,
                 ) -> None:
        self.kind, self.path, self.keys, self.why = kind, path, keys, why
        #: An ANCHORED fingerprint, `fn(doc, inp, now) -> (signature, anchor, detail)`, for an
        #: input a hash would fire on noise (equity, quotes). None = hash `keys`.
        self.fingerprint = fingerprint
        #: A state artifact disappearing IS a change of state. A request file disappearing is
        #: not a request.
        self.fires_on_absent = fires_on_absent
        #: A request-shaped input is a change only when this list field is non-empty.
        self.requires_nonempty = requires_nonempty
        #: A state artifact seen for the first time is the BASELINE the book was already solved
        #: against. A request seen for the first time is an unanswered request.
        self.first_sight_pending = first_sight_pending

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.path.name}"

    def actionable(self, doc: dict[str, Any] | None, sig: str) -> bool:
        if sig in ("absent", "no-watched-key") and not self.fires_on_absent:
            return False
        if self.requires_nonempty:
            val = (doc or {}).get(self.requires_nonempty)
            return isinstance(val, list) and len(val) > 0
        return True


def sources() -> list[Source]:
    return [
        Source("macro_surprise", REPORTS / "MACRO_VIEW.json",
               ("labels", "regime", "surprise", "state", "now"),
               "a macro release moved the state the book is conditioned on"),
        Source("regime_transition", DATA / "regime_state.json",
               ("current", "regime", "label", "state", "probs"),
               "the regime the worlds are drawn from changed"),
        Source("regime_transition", REPORTS / "REGIME_ROUTER.json",
               ("current", "route", "regime", "routed_to"),
               "the router changed which regime a sleeve is routed to"),
        Source("certificate_change", DATA / "sleeve_registry.json",
               ("sleeves",),
               "a certificate arrived or died: the roster the book solves over moved"),
        Source("fill", DATA / "gateway_state.json",
               ("position", "netting_booked", "brackets", "lot"),
               "a fill moved realised risk at the venue"),
        Source("cost_capacity_revision", REPORTS / "NET_EDGE.json",
               ("capacity_by_sleeve", "n_sign_flips", "ranked_if_net_were_the_only_ranking"),
               "net-of-cost or per-sleeve capacity was re-priced"),
        # NEWS RE-SOLVE REQUESTS REACHED NOBODY. `news_event_stream` writes this file (atomically,
        # only when a pass produced requests) and nothing read it: the fast lane's whole output
        # was a request with no listener. `at` IS part of the signature here, unlike the state
        # artifacts above -- every write is a new request, and two identical requests an hour
        # apart are two requests.
        Source("news_resolve_request", RESOLVE_REQUEST, ("at", "requests"),
               "news_event_stream requested a re-solve: a news event moved the world state",
               fires_on_absent=False, requires_nonempty="requests", first_sight_pending=True),
        # THE THREE EVENT-DRIVEN RE-SOLVES (principal, 2026-10-06). Kinds are named so they stay
        # distinguishable from `book_trigger`'s (#264), which reads the same two files and keeps
        # its own state under "book".
        Source("equity_move", DATA / "gateway_state.json", ("equity",),
               "account equity moved more than k x its measured daily volatility since the "
               "equity the last version recorded",
               fires_on_absent=False, fingerprint=_fusion_equity_fingerprint),
        Source("equity_move", REPORTS / "E8_GOLD.json", ("equity",),
               "E8 account equity moved more than k x its measured daily volatility",
               fires_on_absent=False, fingerprint=_e8_equity_fingerprint),
        Source("cost_regime", DATA / "cost_truth_quotes.json", ("symbols",),
               "a sleeve symbol's live spread or swap left its measured dispersion band",
               fires_on_absent=False, fingerprint=_cost_fingerprint),
        Source("drift_health", REPORTS / "DRIFT.json",
               ("verdict", "structure_verdict", "hazard_by_sleeve"),
               "drift_monitor moved a sleeve's hazard verdict or band, or the book verdict",
               fires_on_absent=False, fingerprint=_drift_fingerprint),
    ]


# --------------------------------------------------------------------------- anchored inputs
def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _prev(inp: dict[str, Any]) -> tuple[str | None, Any]:
    obs = inp.get("observed") or {}
    return obs.get("sig"), obs.get("anchor")


def _std(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _closes_sigma(closes: dict[str, Any]) -> tuple[float | None, int]:
    """Daily log-equity volatility from this organ's own per-day closes (consecutive days)."""
    days = sorted(d for d, v in closes.items() if (_num(v) or 0.0) > 0)
    rets = [math.log(float(closes[b]) / float(closes[a])) for a, b in pairwise(days)]
    return _std(rets), len(rets)


def _deals_sigma(quotes: dict[str, Any] | None) -> tuple[float | None, int]:
    """Daily realised log-return volatility from the deal ledger. The balance is rebuilt as the
    running sum of every deal (the ledger opens with the deposit); P&L is trade deals only
    (types 0/1: profit + swap + commission + fee), so a deposit is never a return."""
    deals = (quotes or {}).get("deals")
    if not isinstance(deals, list):
        return None, 0
    rows = sorted((d for d in deals if isinstance(d, dict) and _num(d.get("epoch")) is not None),
                  key=lambda d: float(d["epoch"]))
    bal = 0.0
    open_bal: dict[date, float] = {}
    pnl: dict[date, float] = {}
    for d in rows:
        amt = sum(_num(d.get(k)) or 0.0 for k in ("profit", "swap", "comm", "fee"))
        day = datetime.fromtimestamp(float(d["epoch"]), tz=UTC).date()
        if d.get("type") in (0, 1):
            open_bal.setdefault(day, bal)
            pnl[day] = pnl.get(day, 0.0) + amt
        bal += amt
    if not pnl:
        return None, 0
    first, last = min(pnl), max(pnl)
    rets: list[float] = []
    day, running = first, open_bal[first]
    while day <= last:
        if day.weekday() < 5:
            start = open_bal.get(day, running)
            p = pnl.get(day, 0.0)
            if start > 0 and start + p > 0:
                rets.append(math.log((start + p) / start))
            running = start + p
        day += timedelta(days=1)
    return _std(rets), len(rets)


def _equity_band(inp: dict[str, Any], quotes: dict[str, Any] | None) -> dict[str, Any]:
    """The materiality threshold in log-equity, and the history it was derived from."""
    sigma, n = _closes_sigma(inp.get("equity_closes") or {})
    if sigma and n >= EQUITY_MIN_DAYS:
        basis = f"MEASURED: {n} daily returns of this organ's own equity closes"
    else:
        sigma, n = _deals_sigma(quotes)
        if sigma and n >= EQUITY_MIN_DAYS:
            basis = f"MEASURED: {n} weekday realised returns from cost_truth_quotes.json deals"
        else:
            sigma, basis = EQUITY_DEFAULT_DAILY_VOL, (
                f"DEFAULT: under {EQUITY_MIN_DAYS} days of equity history; stated prior "
                f"{EQUITY_DEFAULT_DAILY_VOL} daily vol")
    return {"daily_vol": round(float(sigma), 6), "k_sigma": EQUITY_K_SIGMA,
            "threshold_log": round(EQUITY_K_SIGMA * float(sigma), 6), "basis": basis}


def _equity_fingerprint(eq: float | None, inp: dict[str, Any], now: float,
                        quotes: dict[str, Any] | None,
                        src_name: str) -> tuple[str, Any, dict[str, Any]]:
    prev_sig, anchor = _prev(inp)
    if eq is None or eq <= 0:
        # unreadable is not an observation: the previous version stands
        return (prev_sig or "no-watched-key"), anchor, {"equity": None, "source": src_name}
    closes = dict(inp.get("equity_closes") or {})
    closes[datetime.fromtimestamp(now, tz=UTC).date().isoformat()] = round(eq, 2)
    inp["equity_closes"] = dict(sorted(closes.items())[-EQUITY_MAX_CLOSES:])
    band = _equity_band(inp, quotes)
    a = _num((anchor or {}).get("equity")) if isinstance(anchor, dict) else None
    move = math.log(eq / a) if a and a > 0 else None
    if move is not None and abs(move) <= band["threshold_log"]:
        new_anchor = anchor
    else:
        new_anchor = {"equity": round(eq, 2)}
    return (_hash(new_anchor), new_anchor,
            {"equity": eq, "anchor_equity": a, "log_move": None if move is None else
             round(move, 6), "source": src_name, **band})


def _fusion_equity_fingerprint(doc: dict[str, Any] | None, inp: dict[str, Any],
                               now: float) -> tuple[str, Any, dict[str, Any]]:
    """Fusion equity: gateway_state.json, else account_state.json (kelly_survival's order)."""
    eq, src = _num((doc or {}).get("equity")), "gateway_state.json:equity"
    if eq is None or eq <= 0:
        eq, src = _num((_read(DATA / "account_state.json") or {}).get("equity")), \
            "account_state.json:equity"
    return _equity_fingerprint(eq, inp, now, _read(DATA / "cost_truth_quotes.json"), src)


def _e8_equity_fingerprint(doc: dict[str, Any] | None, inp: dict[str, Any],
                           now: float) -> tuple[str, Any, dict[str, Any]]:
    """E8 equity: its own closes or the default -- the Fusion deal ledger is another account."""
    return _equity_fingerprint(_num((doc or {}).get("equity")), inp, now, None,
                               "E8_GOLD.json:equity")


def _sleeve_symbols() -> set[str]:
    """Every LIVE sleeve's symbol, from both rosters the gateway trades."""
    out: set[str] = set()
    reg = (_read(DATA / "sleeve_registry.json") or {}).get("sleeves")
    if isinstance(reg, dict):
        for row in reg.values():
            if isinstance(row, dict) and row.get("status") == "LIVE":
                sym = (row.get("identity") or {}).get("symbol")
                if sym:
                    out.add(str(sym))
    rows = (_read(DATA / "sleeves.json") or {}).get("sleeves")
    if isinstance(rows, list):
        out.update(str(r["symbol"]) for r in rows
                   if isinstance(r, dict) and r.get("symbol") and r.get("status") == "LIVE")
    return out


def _spread_band(surface_row: Any) -> tuple[float, str]:
    ratio = _num((surface_row or {}).get("stress_p90_over_p50")) \
        if isinstance(surface_row, dict) else None
    if ratio and ratio > 1.0:
        w = math.log2(ratio)
        if w > COST_LOG2_FLOOR:
            return w, f"measured log2(p90/p50)={w:.3f} from cost_surface.json"
        return COST_LOG2_FLOOR, (f"measured log2(p90/p50)={w:.3f} below the one-doubling floor")
    return COST_LOG2_FLOOR, "no measured dispersion in cost_surface.json: one-doubling floor"


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def _cost_fingerprint(doc: dict[str, Any] | None, inp: dict[str, Any],
                      now: float) -> tuple[str, Any, dict[str, Any]]:
    """Per sleeve symbol, an anchor of (spread, swap_long, swap_short) that moves only when one
    leaves its band. SPREAD: |log2((pts+1)/(anchor+1))| > max(floor, log2(p90/p50)) -- the +1 is
    the one-point quote grid, so 0 -> 1 point is not a regime. SWAP: a sign change, or a
    magnitude move beyond the floor (a doubling or a halving)."""
    prev_sig, anchor = _prev(inp)
    quotes = (doc or {}).get("symbols")
    if not isinstance(quotes, dict) or not quotes:
        return (prev_sig or "no-watched-key"), anchor, {"n_symbols": 0}
    roster = _sleeve_symbols()
    syms = sorted(roster & set(quotes)) if roster else sorted(quotes)
    surface = (_read(DATA / "cost_surface.json") or {}).get("symbols") or {}
    old = anchor if isinstance(anchor, dict) else {}
    new: dict[str, Any] = {}
    moved: dict[str, list[str]] = {}
    for sym in syms:
        q = quotes.get(sym)
        prev = old.get(sym)
        if not isinstance(q, dict):
            if prev is not None:
                new[sym] = prev
            continue
        spread = _num(q.get("live_spread_pts"))
        if spread is None:
            spread = _num(q.get("spread"))
        cur = {"spread": spread, "swap_long": _num(q.get("swap_long")),
               "swap_short": _num(q.get("swap_short"))}
        if not isinstance(prev, dict):
            new[sym] = cur
            continue
        row = dict(prev)
        w, _ = _spread_band(surface.get(sym))
        s0 = _num(prev.get("spread"))
        if spread is not None and spread >= 0 and (
                s0 is None or abs(math.log2((spread + 1.0) / (max(s0, 0.0) + 1.0))) > w):
            row["spread"] = spread
            moved.setdefault(sym, []).append("spread")
        for leg in ("swap_long", "swap_short"):
            v, v0 = cur[leg], _num(prev.get(leg))
            if v is None:
                continue
            if v0 is None or _sign(v) != _sign(v0) or (
                    v != 0 and v0 != 0 and abs(math.log2(abs(v) / abs(v0))) > COST_LOG2_FLOOR):
                row[leg] = v
                moved.setdefault(sym, []).append(leg)
        new[sym] = row
    if not new:
        return (prev_sig or "no-watched-key"), anchor, {"n_symbols": 0}
    detail = {"n_symbols": len(new), "roster_symbols": len(roster), "moved": moved,
              "swap_band_log2": COST_LOG2_FLOOR,
              "spread_band": "max(1 doubling, log2(stress_p90_over_p50))"}
    # A symbol joining or leaving the roster is `certificate_change`'s event, not a cost regime:
    # the anchor takes it in silently and the signature stands unless a held symbol moved.
    if prev_sig and prev_sig != "no-watched-key" and not moved:
        return prev_sig, new, detail
    return _hash(new), new, detail


def _hazard_bands() -> tuple[float, float]:
    try:
        from libs.research import perishability as ph
        return float(ph.HAZARD_AT_RISK), float(ph.HAZARD_BREAKING)
    except Exception:                                          # pragma: no cover - lib optional
        return HAZARD_BANDS_FALLBACK


def _drift_fingerprint(doc: dict[str, Any] | None, inp: dict[str, Any],
                       now: float) -> tuple[str, Any, dict[str, Any]]:
    """Only what `pf_allocator` reads from DRIFT.json, discretised on drift_monitor's own lines:
    the book `verdict` and `structure_verdict` (the crisis-world share) and, per sleeve, its
    `verdict` and which hazard band its `hazard` sits in. A rewrite that moves a hazard inside
    its band, a z-score, a timestamp or a `what_changed` line moves nothing."""
    prev_sig, anchor = _prev(inp)
    if not isinstance(doc, dict):
        return (prev_sig or "no-watched-key"), anchor, {"readable": False}
    at_risk, breaking = _hazard_bands()
    sleeves: dict[str, Any] = {}
    for name, row in (doc.get("hazard_by_sleeve") or {}).items():
        if not isinstance(row, dict):
            continue
        h = _num(row.get("hazard"))
        band = None if h is None else (2 if h >= breaking else 1 if h >= at_risk else 0)
        sleeves[str(name)] = [row.get("verdict"), band]
    fp = {"verdict": doc.get("verdict"), "structure_verdict": doc.get("structure_verdict"),
          "sleeves": sleeves}
    return _hash(fp), fp, {"n_sleeves": len(sleeves), "bands": [at_risk, breaking]}


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")


def _read(p: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _atomic_write_text(path: Path, text: str) -> None:
    """Temp file in the same directory, then `os.replace` -- never a half-written state file.

    WINDOWS: `os.replace` onto a READ-ONLY destination raises PermissionError (WinError 5) where
    POSIX would succeed, and a reader holding the file open raises it too (WinError 32). The first
    is cured by clearing the read-only bit, the second by a short wait; both are retried a bounded
    number of times and then raised, because a state write that silently failed would be the
    lost-change defect again. The temp name carries pid + nonce so two writers never share one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                with contextlib.suppress(OSError):
                    path.chmod(0o644)
                time.sleep(0.05 * (attempt + 1))
    finally:
        with contextlib.suppress(OSError):
            if tmp.exists():
                tmp.unlink()


@contextlib.contextmanager
def _pass_lock(stale_after_s: float) -> Iterator[bool]:
    """Yield True to one trigger pass at a time; False to a pass that must stand down.

    An O_EXCL lock file, stale after `stale_after_s` (a pass is bounded by its solve budget).
    No pid probe: on Windows `os.kill(pid, 0)` TERMINATES the process rather than testing it.
    A pass that stands down loses nothing -- whatever it would have observed is still on disk
    for the holder or the next pass.
    """
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    for _ in range(2):
        try:
            fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                age = time.time() - LOCK.stat().st_mtime
            except OSError:
                continue
            if age <= stale_after_s:
                break
            with contextlib.suppress(OSError):
                LOCK.unlink()
        except OSError:
            break
    if fd is None:
        yield False
        return
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "at": _iso(time.time())}).encode())
        os.close(fd)
        yield True
    finally:
        with contextlib.suppress(OSError):
            LOCK.unlink()


def _signature(doc: dict[str, Any] | None, keys: tuple[str, ...]) -> str:
    """A hash of the DECISION-RELEVANT part only.

    Hashing the whole file would fire on every rewrite -- these artifacts all carry an `at` stamp
    that changes when nothing else does, so a whole-file hash would make every producer a trigger
    and the allocator would re-solve continuously on no new information.
    """
    if doc is None:
        return "absent"
    part = {k: doc.get(k) for k in keys if k in doc}
    if not part:
        return "no-watched-key"
    blob = json.dumps(part, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _event_at(doc: dict[str, Any] | None, p: Path) -> tuple[str, str]:
    """The artifact's OWN timestamp -- the instant the world changed, not the instant we looked.

    Latency measured from our own detection would flatter every number by exactly the poll
    interval, which is the part this organ controls and the part that matters least.
    """
    for field in ("at", "generated_utc", "measured_at", "as_of", "timestamp"):
        val = (doc or {}).get(field)
        if isinstance(val, str) and val.strip():
            return val, f"artifact field {field!r}"
    try:
        return (datetime.fromtimestamp(p.stat().st_mtime, tz=UTC).isoformat(timespec="seconds"),
                "file mtime (the artifact carries no timestamp field)")
    except OSError:
        return datetime.now(tz=UTC).isoformat(timespec="seconds"), "absent artifact"


def _parse(stamp: Any) -> float | None:
    if not stamp:
        return None
    try:
        dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).timestamp()


def _version(seq: int, sig: str) -> str:
    return f"{int(seq)}:{sig}"


def _seq_of(version: Any) -> int | None:
    try:
        return int(str(version).split(":", 1)[0])
    except (TypeError, ValueError):
        return None


def _change_start(event_at: str, basis: str, prev_checked: float | None,
                  now: float) -> tuple[float, str]:
    """When the change began, for latency: its own stamp, clamped into the provable window.

    Upper clamp (now): a stamp in this host's future is clock skew, not a negative latency.
    Lower clamp (the previous look at this input): that look saw the OLD version, so the new one
    cannot have been on disk before it. Producers stamp `at` when they START, and an artifact
    that took ten minutes to build would otherwise charge ten minutes to the allocator.
    """
    ev = _parse(event_at)
    if ev is None:
        return now, "first observation (no parseable timestamp)"
    if ev > now:
        return now, f"{basis}, ahead of this host's clock: clamped to first observation"
    if prev_checked is not None and ev < prev_checked:
        return prev_checked, (f"{basis} predates the previous look that saw the old version: "
                              f"clamped to that look")
    return ev, basis


def _heat_now() -> float | None:
    art = _read(ALLOCATION)
    if art is None:
        return None
    h = art.get("heat") or {}
    for k in ("resolved", "total", "heat_deployed"):
        try:
            return float(h[k])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _allocation_stamp() -> tuple[str | None, float | None]:
    """The allocation artifact's `generated_utc`, for REPORTING ONLY. It moves whenever ANY
    allocator pass writes -- the hourly leg included -- so it is never read as a landing."""
    art = _read(ALLOCATION)
    stamp = (art or {}).get("generated_utc")
    return (str(stamp) if stamp else None), _parse(stamp)


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _request_env(request: dict[str, Any]) -> dict[str, str]:
    """THE TRIGGER'S HALF OF THE DECISION CONTRACT: what the solver is told it is answering.

    `QUANT_ALLOC_TRIGGER_REQUEST` = {"request_id": str, "input_versions": {input key: version}}.
    An env var rather than an argument: `pf_allocator`'s argparse rejects an unknown flag, so an
    argument would turn every reaction into rc=2 until the solver learned it, while an env var it
    does not read yet is simply ignored -- and the trigger then reads "not landed" and retries.
    """
    env = dict(os.environ)
    env[REQUEST_ENV] = json.dumps({"request_id": request["request_id"],
                                   "input_versions": request["input_versions"]},
                                  sort_keys=True)
    return env


def _solve(budget_s: float, request: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fire the SAME solver the hourly leg fires, in its fast mode. Never in-process: the solver
    allocates heavily and a crash inside it must not take the watcher down with it."""
    started = time.time()
    try:
        r = subprocess.run(
            [sys.executable, "-u", str(DESK / "research" / "pf_allocator.py"),
             "--mode", "fast"],
            cwd=str(DESK), capture_output=True, text=True,
            env=_request_env(request) if request else None,
            timeout=max(60.0, float(budget_s)), check=False)
        return {"rc": int(r.returncode), "wall_s": round(time.time() - started, 2),
                "tail": ((r.stdout or "") + (r.stderr or ""))[-400:]}
    except subprocess.TimeoutExpired:
        return {"rc": None, "wall_s": round(time.time() - started, 2),
                "tail": f"TIMEOUT after {budget_s}s"}
    except OSError as exc:
        return {"rc": None, "wall_s": round(time.time() - started, 2),
                "tail": f"{type(exc).__name__}: {exc}"}


def _decision_of(art: dict[str, Any] | None) -> dict[str, Any] | None:
    """THE SOLVER'S HALF OF THE CONTRACT, read from `pf_allocation.json`. None = no decision.

    Required: `decision_id` (non-empty string, unique per pass) and `consumed_input_versions`
    (non-empty object: input key -> version, echoed from the request). `trigger_request_id`
    (echo of request_id) ties it to the request; `decided_utc` (else `generated_utc`) is when it
    was decided. An allocation lacking any required field is NOT a landed decision, however
    fresh its timestamp.
    """
    if not isinstance(art, dict):
        return None
    did = art.get("decision_id")
    consumed = art.get("consumed_input_versions")
    if not (isinstance(did, str) and did.strip()):
        return None
    if not isinstance(consumed, dict) or not consumed:
        return None
    req = art.get("trigger_request_id")
    return {"decision_id": did.strip(),
            "request_id": req if isinstance(req, str) and req else None,
            "consumed": {str(k): str(v) for k, v in consumed.items()},
            "decided_at": art.get("decided_utc") or art.get("generated_utc")}


def _fresh_state() -> dict[str, Any]:
    return {"schema": STATE_SCHEMA, "seen": {}, "last_solve_at": 0.0, "fail_count": 0,
            "issued": [], "applied_decisions": [], "latency_samples": []}


def _load_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    """The ledgers live under `seen`, keyed `<kind>:<file name>` -- the key schema 1 used, so a
    reader of the old state file finds the same rows. Each row is read by its SHAPE, not by the
    file's schema number: a schema-2 row (it has `observed`) is kept as-is; a schema-1 row
    (`sig` only) is migrated as the baseline, because whether a solve consumed it is unknowable
    now -- schema 1 marked debounced and failed changes seen too."""
    st = _fresh_state()
    if not isinstance(raw, dict):
        return st
    # KEYS THIS ORGAN DOES NOT OWN ARE CARRIED THROUGH UNTOUCHED. `book_trigger` (#264) keeps its
    # state under "book" in this same file; rebuilding the state from known keys only would erase
    # it on every pass.
    for k, v in raw.items():
        if k not in st and k not in ("seen", "inputs", "at"):
            st[k] = v
    for k in ("last_solve_at", "fail_count", "issued", "applied_decisions", "latency_samples"):
        if raw.get(k) is not None:
            st[k] = raw[k]
    st["last_solve_at"] = float(st.get("last_solve_at") or 0.0)
    rows = raw.get("seen") or raw.get("inputs") or {}
    for key, rec in rows.items():
        if not isinstance(rec, dict):
            continue
        if "observed" in rec:
            st["seen"][key] = rec
            continue
        sig = rec.get("sig")
        if not sig:
            continue
        at = rec.get("at")
        ver = _version(1, sig)
        st["seen"][key] = {
            "observed": {"seq": 1, "sig": sig, "version": ver, "observed_at": at,
                         "checked_at": at},
            "pending": [],
            "consumed": {"seq": 1, "version": ver, "decision_id": None,
                         "basis": "migrated from schema-1 `seen`; consumption unverifiable"}}
    return st


def _cap_pending(pend: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(pend) <= MAX_PENDING_PER_INPUT:
        return pend
    return [pend[0], *pend[-(MAX_PENDING_PER_INPUT - 1):]]


def _observe(src: Source, inp: dict[str, Any], now: float) -> dict[str, Any]:
    """Update OBSERVED; append to PENDING when the version moved. Never touches CONSUMED except
    to record the baseline on a state artifact's first sighting."""
    doc = _read(src.path)
    anchor: Any = None
    detail: dict[str, Any] | None = None
    if src.fingerprint is not None:
        sig, anchor, detail = src.fingerprint(doc, inp, now)
    else:
        sig = _signature(doc, src.keys)
    obs = dict(inp.get("observed") or {})
    prev_sig = obs.get("sig")
    prev_seq = int(obs.get("seq") or 0)
    prev_checked = _parse(obs.get("checked_at"))
    first_sight = prev_sig is None
    moved = (not first_sight) and sig != prev_sig
    event_at, basis = _event_at(doc, src.path)
    added = False
    if first_sight or moved:
        seq = prev_seq + 1
        ver = _version(seq, sig)
        inp["observed"] = {"seq": seq, "sig": sig, "version": ver, "observed_at": _iso(now),
                           "observed_ts": now, "event_at": event_at, "event_at_basis": basis,
                           "checked_at": _iso(now)}
        if src.fingerprint is not None:
            inp["observed"]["anchor"] = anchor
        actionable = src.actionable(doc, sig)
        if actionable and (moved or src.first_sight_pending):
            start_ts, start_basis = _change_start(event_at, basis,
                                                  None if first_sight else prev_checked, now)
            pend = list(inp.get("pending") or [])
            pend.append({"seq": seq, "version": ver, "kind": src.kind,
                         "observed_at": _iso(now), "observed_ts": now,
                         "event_at": event_at, "event_at_basis": basis,
                         "start_ts": start_ts, "start_basis": start_basis})
            inp["pending"] = _cap_pending(pend)
            added = True
        elif first_sight and not inp.get("consumed"):
            inp["consumed"] = {"seq": seq, "version": ver, "decision_id": None,
                               "basis": "baseline: first sighting of a state artifact"}
    else:
        obs["checked_at"] = _iso(now)
        if src.fingerprint is not None and anchor is not None:
            obs["anchor"] = anchor            # same signature: the band held, or a roster join
        inp["observed"] = obs
    inp.setdefault("pending", [])
    inp["kind"], inp["path"] = src.kind, _rel(src.path)
    return {"key": src.key, "kind": src.kind, "path": inp["path"], "signature": sig,
            "version": inp["observed"]["version"], "previous": prev_sig,
            "changed": bool(moved), "first_seen": first_sight, "became_pending": added,
            "n_pending": len(inp["pending"]), "event_at": event_at, "event_at_basis": basis,
            "consumed_version": (inp.get("consumed") or {}).get("version"), "why": src.why,
            **({"materiality": detail} if detail is not None else {})}


def _land(st: dict[str, Any], dec: dict[str, Any] | None,
          now: float) -> tuple[str, list[dict[str, Any]]]:
    """Apply a decision to the ledgers. Returns (verdict, latency samples).

    Consumption is per input and by SEQUENCE: the decision consumes, for each input, exactly the
    version this organ sent in that request and the allocator echoed back, and with it every
    older pending version of that input (a later state supersedes an earlier one). Anything
    pending with a higher sequence -- observed after the request was issued -- stays pending.
    CONSUMED only ever moves forward, so a late or stale decision can never roll it back.
    """
    if dec is None:
        return "NO_DECISION_CONTRACT", []
    if dec["decision_id"] in (st.get("applied_decisions") or []):
        return "ALREADY_APPLIED", []
    issued = {r.get("request_id"): r for r in (st.get("issued") or [])}
    req = issued.get(dec["request_id"])
    if req is None:
        return "NOT_A_REQUEST_THIS_TRIGGER_ISSUED", []
    landed_ts = _parse(dec.get("decided_at"))
    issued_ts = float(req.get("issued_ts") or 0.0)
    if landed_ts is None or landed_ts > now or landed_ts < issued_ts:
        landed_ts = now
    samples: list[dict[str, Any]] = []
    attested = 0
    for key, sent in (req.get("input_versions") or {}).items():
        if dec["consumed"].get(key) != sent:
            continue                      # the solver did not attest THIS version: not consumed
        seq = _seq_of(sent)
        inp = (st.get("seen") or {}).get(key)
        if seq is None or inp is None:
            continue
        attested += 1
        pend = list(inp.get("pending") or [])
        served = [p for p in pend if int(p.get("seq") or 0) <= seq]
        inp["pending"] = [p for p in pend if int(p.get("seq") or 0) > seq]
        if int((inp.get("consumed") or {}).get("seq") or 0) < seq:
            inp["consumed"] = {"seq": seq, "version": sent, "decision_id": dec["decision_id"],
                               "request_id": req["request_id"], "landed_at": _iso(landed_ts)}
        for p in served:
            samples.append({
                "schema": STATE_SCHEMA, "event": "consumed", "at": _iso(now),
                "decision_id": dec["decision_id"], "request_id": req["request_id"],
                "key": key, "kind": p.get("kind") or inp.get("kind"),
                "version": p.get("version"), "consumed_as": sent,
                "event_at": p.get("event_at"), "start_basis": p.get("start_basis"),
                "observed_at": p.get("observed_at"), "landed_at": _iso(landed_ts),
                # THE NUMBER THE PRINCIPAL ASKED FOR: the change's own start to the landed
                # decision that consumed it.
                "latency_s": round(landed_ts - float(p.get("start_ts") or landed_ts), 2),
                "from_observation_s": round(landed_ts - float(p.get("observed_ts") or landed_ts),
                                            2)})
    if attested == 0:
        return "CONSUMED_VERSIONS_DO_NOT_ECHO_THE_REQUEST", []
    req["outcome"] = "LANDED"
    req["decision_id"] = dec["decision_id"]
    st["applied_decisions"] = [*(st.get("applied_decisions") or []),
                               dec["decision_id"]][-MAX_APPLIED:]
    st["latency_samples"] = [*(st.get("latency_samples") or []), *samples][-MAX_SAMPLES:]
    return "LANDED", samples


def _backoff_s(failures: int) -> float:
    return float(min(RETRY_BACKOFF_CAP_S, MIN_SOLVE_GAP_S * 2 ** max(0, failures - 1)))


def _wait_s(failures: int) -> float:
    """How long after the last attempt the next may start: the gap, or the backoff if longer."""
    return max(MIN_SOLVE_GAP_S, _backoff_s(failures)) if failures else MIN_SOLVE_GAP_S


def _call_solver(fn: Callable[..., dict[str, Any]], budget_s: float,
                 req: dict[str, Any]) -> dict[str, Any]:
    """Call `fn(budget_s, request)`; a one-argument solver (`_solve(budget)`, the shape test
    harnesses patch in) is called with the budget only and so carries no request -- its output
    can then only land if it echoes a request by other means, which is the conservative side."""
    try:
        params = [p for p in inspect.signature(fn).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL)]
    except (TypeError, ValueError):
        params = []
    if len(params) >= 2 or any(p.kind is p.VAR_POSITIONAL for p in params):
        return fn(budget_s, req)
    return fn(budget_s)


def poll(*, budget_s: float = 600.0, state: dict[str, Any] | None = None,
         write: bool = True, solve: bool = True, now: float | None = None,
         clock: Callable[[], float] = time.time,
         solver: Callable[[float, dict[str, Any]], dict[str, Any]] | None = None,
         ) -> dict[str, Any]:
    """One pass: settle any decision already on disk, observe every input, solve once if anything
    is pending and the gap/backoff allows, and settle the decision that solve produced."""
    st = _load_state(state if state is not None else _read(STATE))
    t0 = clock() if now is None else float(now)
    solver = solver or _solve
    rows: list[dict[str, Any]] = []

    # 1. A decision already on disk -- a previous pass that read the artifact before it landed,
    # or a process that died between the solve and the state write -- is applied first.
    verdict0, samples0 = _land(st, _decision_of(_read(ALLOCATION)), t0)
    rows.extend(samples0)

    # 2. OBSERVED and PENDING.
    inputs: dict[str, Any] = st["seen"]
    watch = [_observe(src, inputs.setdefault(src.key, {}), t0) for src in sources()]
    pending_keys = sorted(k for k, inp in inputs.items() if inp.get("pending"))

    last_solve = float(st.get("last_solve_at") or 0.0)
    # The backoff is measured FROM the last attempt (`last_solve_at`), never stored as an
    # absolute deadline: one clock, one field, and a caller that resets `last_solve_at` (an
    # operator forcing a retry) is genuinely past the wait rather than fighting a hidden second
    # deadline.
    wait_until = last_solve + _wait_s(int(st.get("fail_count") or 0))
    debounced = bool(pending_keys) and t0 < wait_until
    attempt: dict[str, Any] | None = None

    if pending_keys and solve and not debounced:
        # 3. Issue a request for EXACTLY the versions observed now. The solve can consume these
        # and nothing newer.
        req = {"request_id": uuid.uuid4().hex, "issued_at": _iso(t0), "issued_ts": t0,
               "input_versions": {k: inp["observed"]["version"] for k, inp in inputs.items()
                                  if (inp.get("observed") or {}).get("version")},
               "pending_keys": pending_keys, "outcome": "ISSUED"}
        st["issued"] = [*(st.get("issued") or []), req][-MAX_ISSUED:]
        heat_before = _heat_now()
        res = _call_solver(solver, budget_s, req)
        t1 = max(t0, clock())
        heat_after = _heat_now()
        st["last_solve_at"] = t1
        dec = _decision_of(_read(ALLOCATION))
        # Settled on its own merits even when it answers ANOTHER request: an earlier request of
        # ours landing late consumes only what IT was sent, which `_land` enforces by sequence.
        verdict, samples = _land(st, dec, t1)
        rows.extend(samples)
        if dec is not None and dec.get("request_id") != req["request_id"]:
            verdict = "DECISION_ANSWERS_ANOTHER_REQUEST"
        if res.get("rc") not in (0, None) and verdict != "LANDED":
            verdict = f"SOLVER_FAILED rc={res.get('rc')}"
        elif res.get("rc") is None and verdict != "LANDED":
            verdict = "SOLVER_DID_NOT_FINISH"
        landed = verdict == "LANDED"
        if landed:
            st["fail_count"] = 0
        else:
            req["outcome"] = verdict
            st["fail_count"] = int(st.get("fail_count") or 0) + 1

        attempt = {
            "schema": STATE_SCHEMA, "event": "attempt", "at": _iso(t1),
            "request_id": req["request_id"], "pending_keys": pending_keys,
            "input_versions": req["input_versions"], "verdict": verdict, "landed": landed,
            "decision_id": (dec or {}).get("decision_id") if landed else None,
            "solve_wall_s": res.get("wall_s"), "solver_rc": res.get("rc"),
            "heat_before": heat_before, "heat_after": heat_after,
            # TWO-SIDED, MEASURED. A reaction reallocates; it must not shrink the book. This is
            # reported, never enforced -- the heat law owns the total and this organ has no path
            # to it.
            "heat_preserved": (None if (heat_before is None or heat_after is None)
                               else bool(heat_after >= heat_before - 5e-4)),
            "retry_after": None if landed else _iso(t1 + _wait_s(st["fail_count"])),
            # The allocation artifact's own stamp, for the reader. NOT evidence of landing.
            "allocation_at": _allocation_stamp()[0],
            "note": "" if landed else str(res.get("tail") or "")[-200:]}
        rows.insert(0, attempt)
    elif pending_keys:
        rows.append({"schema": STATE_SCHEMA, "event": "deferred", "at": _iso(t0),
                     "pending_keys": pending_keys,
                     "stood_down": "SOLVE_DISABLED" if not solve else "DEBOUNCED",
                     "why": ("--no-solve: watch only; pending is kept" if not solve else
                             f"next solve allowed at {_iso(wait_until)} (gap "
                             f"{MIN_SOLVE_GAP_S:.0f}s, failures {st.get('fail_count', 0)}); "
                             f"pending is kept and served then")})

    st["at"] = _iso(t0)
    st["schema"] = STATE_SCHEMA
    if write:
        _atomic_write_text(STATE, json.dumps(st, indent=1, default=str) + "\n")
        if rows:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, default=str) + "\n")
    return {"watch": watch, "fired": rows, "state": st, "debounced": debounced,
            "attempt": attempt, "settled_on_entry": verdict0, "pending_keys": sorted(
                k for k, inp in inputs.items() if inp.get("pending"))}


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    """Nearest-rank percentile: always an observed sample, never an interpolation."""
    if not sorted_vals:
        return None
    rank = max(1, math.ceil(p / 100.0 * len(sorted_vals)))
    return sorted_vals[min(rank, len(sorted_vals)) - 1]


def _summary(vals: list[float]) -> dict[str, Any]:
    v = sorted(vals)
    return {"n": len(v), "p50_s": _percentile(v, 50), "p95_s": _percentile(v, 95),
            "p99_s": _percentile(v, 99), "best_s": v[0] if v else None,
            "worst_s": v[-1] if v else None,
            "share_within_poll_interval": (round(sum(x <= DEFAULT_INTERVAL_S for x in v)
                                                 / len(v), 4) if v else None),
            "share_within_poll_plus_gap": (round(sum(x <= DEFAULT_INTERVAL_S + MIN_SOLVE_GAP_S
                                                     for x in v) / len(v), 4) if v else None),
            "status": "MEASURED" if v else "UNMEASURED"}


def latency_report(samples: list[dict[str, Any]],
                   kinds: list[str] | None = None) -> dict[str, Any]:
    """End-to-end latency, change start -> landed decision that consumed it, as p50/p95/p99.

    Three views: every consumed version, per kind, and per DECISION (its slowest input -- the
    oldest change that decision answered). Set beside the poll interval and the solve gap,
    because those are the delay this organ adds by construction: a change can wait up to one
    poll to be seen and up to one gap to be solved, before the solve's own wall time.
    """
    vals = [float(s["latency_s"]) for s in samples
            if isinstance(s.get("latency_s"), (int, float))]
    by_kind: dict[str, list[float]] = {}
    by_dec: dict[str, float] = {}
    for s in samples:
        lat = s.get("latency_s")
        if not isinstance(lat, (int, float)):
            continue
        by_kind.setdefault(str(s.get("kind") or "unknown"), []).append(float(lat))
        d = str(s.get("decision_id") or "")
        by_dec[d] = max(by_dec.get(d, float("-inf")), float(lat))
    obs = [float(s["from_observation_s"]) for s in samples
           if isinstance(s.get("from_observation_s"), (int, float))]
    # Every WATCHED kind gets a row, so a kind that has never been consumed reads UNMEASURED
    # rather than being absent -- absence is not a latency.
    for k in kinds or []:
        by_kind.setdefault(k, [])
    return {
        "all_inputs": _summary(vals),
        "per_decision_slowest_input": _summary(list(by_dec.values())),
        "from_first_observation": _summary(obs),
        "by_kind": {k: _summary(v) for k, v in sorted(by_kind.items())},
        "poll_interval_s": DEFAULT_INTERVAL_S,
        "min_solve_gap_s": MIN_SOLVE_GAP_S,
        "structural_delay_s": {"detect_worst": DEFAULT_INTERVAL_S,
                               "debounce_worst": MIN_SOLVE_GAP_S,
                               "sum_before_solve_wall": DEFAULT_INTERVAL_S + MIN_SOLVE_GAP_S},
        "n_decisions": len(by_dec),
    }


DECISION_CONTRACT = {
    "request_env": REQUEST_ENV,
    "request_shape": {"request_id": "str", "input_versions": {"<input key>": "<seq>:<sig>"}},
    "allocation_fields": {
        "decision_id": "non-empty str, unique per pass",
        "trigger_request_id": "the request_id from the env var, verbatim",
        "consumed_input_versions": "the input_versions object from the env var, verbatim",
        "decided_utc": "ISO-8601 UTC instant of the decision (optional; else generated_utc)",
    },
    "landed_iff": ("decision_id present AND trigger_request_id names a request this trigger "
                   "issued AND consumed_input_versions echoes that request's versions; a newer "
                   "timestamp alone is never a landing"),
}


def run(*, budget_s: float = 600.0, write: bool = True, solve: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    with _pass_lock(stale_after_s=float(budget_s) + 300.0) if write else \
            contextlib.nullcontext(True) as got:
        if not got:
            return {"at": _iso(time.time()), "schema": STATE_SCHEMA, "stood_down": "LOCKED",
                    "why": "another trigger pass holds the state; it observes the same disk",
                    "watch": [], "n_watched": 0, "n_changed_this_pass": 0,
                    "fired_this_pass": [], "n_pending_inputs": None, "latency": {}}
        res = poll(budget_s=budget_s, write=write, solve=solve)
    st = res["state"]
    attempts = [r for r in _tail() if r.get("event") == "attempt"]
    heats = [r for r in attempts if r.get("heat_preserved") is False]
    rep = {
        "at": _iso(time.time()),
        "schema": STATE_SCHEMA,
        "watch": res["watch"],
        "n_watched": len(res["watch"]),
        "n_changed_this_pass": sum(1 for w in res["watch"] if w["changed"]),
        "fired_this_pass": res["fired"],
        "debounced": res["debounced"],
        "pending": {k: [p.get("version") for p in (inp.get("pending") or [])]
                    for k, inp in st["seen"].items() if inp.get("pending")},
        "n_pending_inputs": len(res["pending_keys"]),
        "consumed": {k: (inp.get("consumed") or {}).get("version")
                     for k, inp in st["seen"].items()},
        "fail_count": st.get("fail_count"),
        "retry_after": (_iso(float(st.get("last_solve_at") or 0.0)
                             + _wait_s(int(st.get("fail_count") or 0)))
                        if st.get("fail_count") else None),
        "latency": latency_report(st.get("latency_samples") or [],
                                  sorted({s.kind for s in sources()})),
        "recent_attempts": attempts[-8:],
        "heat_reductions": len(heats),
        "heat_reduction_rows": heats[-4:],
        "poll_interval_s": DEFAULT_INTERVAL_S,
        "min_solve_gap_s": MIN_SOLVE_GAP_S,
        "retry_backoff_cap_s": RETRY_BACKOFF_CAP_S,
        "decision_contract": DECISION_CONTRACT,
        "backstop": ("the hourly `pf_allocator` leg still runs its full solve on its own "
                     "cadence; these reactions are added to it, never instead of it"),
        "boundary": ("fires the same solver with the same heat law. It sets no fraction, no cap "
                     "and no veto, and it cannot move the 20% heat floor or the 0.02-lot gold "
                     "floor; heat_before/heat_after are recorded so a reaction that shrank the "
                     "book would be visible as its own defect"),
        "elapsed_s": round(time.monotonic() - started, 3),
    }
    if write:
        _atomic_write_text(OUT, json.dumps(rep, indent=1, sort_keys=True, default=str) + "\n")
        try:
            from libs.ops.events import leg_events
            leg_events("allocator_trigger", "OK", n_fired=len(res["fired"]),
                       n_changed=rep["n_changed_this_pass"], artifact=str(OUT))
        except Exception:                                      # pragma: no cover - events opt.
            pass
    return rep


def _tail(n: int = 400) -> list[dict[str, Any]]:
    try:
        lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _print(rep: dict[str, Any]) -> None:
    if rep.get("stood_down"):
        print(f"ALLOCATOR TRIGGERS  stood down: {rep['stood_down']} ({rep.get('why')})")
        return
    print(f"ALLOCATOR TRIGGERS  watched={rep['n_watched']} changed={rep['n_changed_this_pass']} "
          f"pending_inputs={rep['n_pending_inputs']} fail_count={rep['fail_count']}")
    lat = (rep.get("latency") or {}).get("all_inputs") or {}
    print(f"  latency n={lat.get('n')} p50={lat.get('p50_s')}s p95={lat.get('p95_s')}s "
          f"p99={lat.get('p99_s')}s (poll {DEFAULT_INTERVAL_S:.0f}s, gap "
          f"{MIN_SOLVE_GAP_S:.0f}s)")
    for f in rep["fired_this_pass"]:
        if f.get("event") == "attempt":
            print(f"  SOLVE {f['verdict']}: wall={f.get('solve_wall_s')}s "
                  f"heat {f.get('heat_before')} -> {f.get('heat_after')}")
        elif f.get("event") == "consumed":
            print(f"  CONSUMED {f['key']} {f['version']}: latency={f.get('latency_s')}s")
        else:
            print(f"  DEFERRED {f.get('pending_keys')}: {f.get('stood_down')}")
    if rep["heat_reductions"]:
        print(f"  WARNING: {rep['heat_reductions']} recorded reaction(s) lowered total heat")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one poll (the scheduled leg shape)")
    ap.add_argument("--resident", action="store_true", help="poll forever (the 24/7 shape)")
    ap.add_argument("--interval-s", type=float, default=DEFAULT_INTERVAL_S)
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--no-solve", action="store_true",
                    help="watch and record, never fire the solver")
    ap.add_argument("--dry-run", action="store_true", help="write nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.resident:
        # 24/7. The keep-alive task restarts this if the box reboots or the process dies; the
        # loop itself never exits on a bad pass, because a watcher that dies on one unreadable
        # artifact is a watcher that is not watching.
        deadline_interval = max(5.0, float(args.interval_s))
        while True:
            try:
                rep = run(budget_s=args.budget_s, write=not args.dry_run,
                          solve=not args.no_solve)
                if rep["fired_this_pass"]:
                    _print(rep)
            except Exception as exc:                           # pragma: no cover - resident
                print(f"allocator_trigger pass failed ({type(exc).__name__}: {exc}); "
                      f"the next poll retries in {deadline_interval:.0f}s", flush=True)
            time.sleep(deadline_interval)
    rep = run(budget_s=args.budget_s, write=not args.dry_run, solve=not args.no_solve)
    if args.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        _print(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
