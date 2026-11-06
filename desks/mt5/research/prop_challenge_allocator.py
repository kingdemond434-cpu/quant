#!/usr/bin/env python3
"""PROP CHALLENGE ALLOCATOR: the FTMO book (and next the E8 book), picked and sized by a solve.

The principal, 2026-10-28 14:34Z: "make a FTMO allocator just as advanced as our Fusion allocator
... the bridge between fastest passing rate while passing probability is highest, like speed times
highest passing probability, and uses all the certified sleeves ... and FTMO's cost model ... and
deploys based on that, so we don't have to worry about the books anymore." And 14:39Z: it must
know which phase the account is in and re-optimise for it automatically.

THE OBJECTIVE, AS ONE NUMBER. A challenge pays nothing until the account is funded, and a funded
account earns roughly the same amount on every day it is funded. So the value of a book is the
number of days it buys funded inside the planning horizon:

    J(book) = E[ 1{funded} * max(H - T_funded, 0) ] / H

`T_funded` is trading days from NOW until the last phase passes, through every phase still ahead
(each later phase at its own optimal book, solved first: a backward induction), plus the days the
firm takes to issue the next account. J is literally "speed times probability": a book that passes
for sure in H/2 days scores 0.5, one that passes half the time in no time scores 0.5. It is
evaluated on two worlds -- the allocator's posterior as estimated, and the same with every positive
edge HALVED -- and the solve maximises the 50/50 mixture, because the desk does not know which one
it lives in.

SURVIVAL IS NOT LOOSENED. The desk's own prop precedent (`kelly_survival.e8_barrier`: "P(the account
fails) held to EPS_DEATH; inside it, the fastest median pass wins") holds on BOTH worlds, at the
solve margin `kelly_survival.BOOK_MARGIN`, and the published book is re-measured on an independent
path sample. What that constraint costs is published as the frontier's unconstrained optimum, so it
is a measured price and not an assumption (growth governance Rule 1).

FUNDED is a different game and gets the other objective: maximise ruin-counted E[log W] of the
account with the firm's loss limits as ruin, P(breach within kelly_survival.HORIZON) <= EPS_DEATH
on both worlds -- the Fusion rule, with the firm's limits standing in for the death line.

THE ARENA IS THE FIRM'S OWN RULE TEXT (`RULES`), CHECKED DAY BY DAY:
  * the daily loss limit is measured from the day's starting balance (FTMO: 00:00 CE(S)T) on EQUITY,
    floating included, so the day's LOW is what is tested. The worlds carry daily R per sleeve, not
    the order of fills, so the low is taken ADVERSARIALLY: every losing leg lands before any winning
    one. That over-states breaches, never under-states them.
  * the maximum loss is static from the initial balance and is tested on the same low.
  * the target counts on balance with positions closed, and needs the firm's minimum trading days;
    an account at target before then completes them with minimum-lot days at no modelled risk.
  * E8's 2% daily profit cap strips the excess at rollover (`prop_barrier`).

THE UNIVERSE, every gate fail-closed and every refusal NAMED in `screen`:
  1. certificates in the canonical store (`kelly_survival.certified_roster`: banned families, M15,
     the Reddit/StockTwits terms fence already out), priced by the allocator's worlds or replayed;
  2. TIER S: the certificate's deflated-Sharpe gate passed at dsr >= 0.95 AND its Tier S door
     verdict is CLEAR (data/tier_s/door_verdicts.json). The bar is read, never set here;
  3. LISTED on the venue's terminal (`data/ftmo_registry.json` from prop/ftmo_venue_reader.py, else
     the FTMO-terminal registry snapshot `data/cost_truth_quotes.json`);
  4. PRICED AT THE VENUE'S COST at the sleeve's own fill hour: FTMO's spread at that hour (its own
     cost surface, `data/cost_surface_ftmo.json`) over the spread the replay charged, turned into an
     R-per-trade bias exactly as `libs.portfolio.execution_cost` does for Fusion (BASE_COST_R x
     (ratio - 1), clipped at MAX_RATIO, never a credit). A sleeve the venue cannot price is OUT;
  5. not quarantined (`live_sleeve_policy.json` empty symbol list) and not a principal zero;
  6. E8'S SYMBOLS ARE ELIGIBLE (principal override, zuck 2026-10-29 14:46Z: "remove the e8
     exception"). Until then a sleeve on a symbol E8's live book trades was out. The no-opposite
     rule now lives where it can actually be enforced, at the order: a sleeve that shares a symbol
     with E8 is marked `e8_overlap` and its `direction_fence`, and no FTMO executor may send it
     without the cross-account opposite-side fence (`mt5desk.cross_account.opposite_block`, the
     gold direction lock for XAUUSD). `prop/ftmo_executor.py` is that executor: it checks the
     Fusion and E8 books under the placement lock before every send.
The one exception is the gold_asia COPY, and it is the principal's switch, not this solve's
(`COPY_COLUMNS`, `copy_switch`): FTMO bans cross-firm copying and the principal overrode that with
informed consent (2026-10-28 14:31Z). It is a column only while the principal holds it on, and the
solve may only resize it inside (0, the principal's value]; a zero (a pause) is never re-opened.

WHAT IS EMPTY IS A REQUEST, NOT A SHRUG. Every venue-listed symbol with no Tier S sleeve is written
as a targeted hypothesis (`data/intelligence/ftmo_allocator/ftmo_gap_hypotheses.jsonl`) on the
families that already certify elsewhere, so the miner compiler and the gauntlet aim at FTMO-tradable
cells. Trials are counted by the gauntlet at its fixed canonical count, so this inflates nothing.

DEPLOYMENT. reports/FTMO_ALLOCATOR.json always. The `ftmo` block of data/CERT_BOOK_LIVE.json is
rewritten ONLY when data/FTMO_ALLOCATOR_ARMED exists, the account state is MEASURED and fresh, the
book validated, and only for keys an FTMO executor trades: the gold copy (`FTMO_EXECUTABLE`, the
follower) and every non-gold sleeve whose certificate spec is published in `specs` (the sleeve
executor, `prop/ftmo_executor.py`, 2026-10-29). The deployed book is SOLVED over those keys alone
(audit #489 MF1), so a column with no executor (a non-copy gold window: gold has one FTMO owner)
can never pull risk away from one that trades; the joint solve over every admitted column is
published as `joint_book`, its extra columns as SIZED_NO_EXECUTOR, and the J they would add as
J_missed. A key that was in the block and is no longer executable is written 0 -- a sleeve the
solve dropped is never left funded.

    python desks/mt5/research/prop_challenge_allocator.py [--venue ftmo] [--paths 1500]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "FTMO_ALLOCATOR.json"
ACCOUNT_STATE = BASE / "reports" / "FTMO_ACCOUNT_STATE.json"
FTMO_REGISTRY = BASE / "data" / "ftmo_registry.json"
FTMO_QUOTES = BASE / "data" / "cost_truth_quotes.json"
FTMO_SURFACE = BASE / "data" / "cost_surface_ftmo.json"
FUSION_SURFACE = BASE / "data" / "cost_surface.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
DOORS = BASE / "data" / "tier_s" / "door_verdicts.json"
SLEEVE_POLICY = BASE / "data" / "live_sleeve_policy.json"
CERT_BOOK = BASE / "data" / "CERT_BOOK_LIVE.json"
ARMED = BASE / "data" / "FTMO_ALLOCATOR_ARMED"
GAP_REQUESTS = BASE / "data" / "intelligence" / "ftmo_allocator" / "ftmo_gap_hypotheses.jsonl"

#: The Tier S bar is the gate spec's, read off the certificate; restated here only to compare.
DSR_BAR = 0.95
#: The planning horizon in trading days: one year. A pass after H buys nothing inside it.
HORIZON_DAYS = 252
#: Trading days per path. FTMO's 2-Step has no time limit, so a path still running at the end is
#: neither a pass nor a failure; it scores zero in J (it is not funded inside H).
SIM_DAYS = 252
N_PATHS = 1500
#: Days after a phase passes before the next account trades: FTMO reviews the evaluation and
#: issues the Verification, then the FTMO Account after identity checks. Not published as a
#: number; two trading days per hand-off is the firm's stated "usually within 1-2 business days"
#: for the review. Small against any plausible T, and it only shifts J, never the argmax.
HANDOFF_DAYS = 2
#: The size grid (risk per trade, fraction of the INITIAL balance) and the search steps.
STEPS = (0.004, 0.002, 0.001, 0.0005)
STARTS = 4
#: Scores closer than this are a tie, broken by progress to the target (see `search`).
TIE_EPS = 1e-9
#: Total sizes probed along the unconstrained mix when the constrained book comes back empty:
#: a positive size there that keeps P(fail) within the margin and makes progress means the
#: search missed it (EMPTY_BOOK_SEARCH_DEFECT), never that zero is the answer.
EMPTY_PROBE = (1e-4, 5e-4, 1e-3, 2e-3)
#: The account state must be younger than this to deploy from (the reader runs every 5 minutes).
STATE_MAX_AGE_S = 3 * 3600
#: Keys the gold follower trades (prop/ftmo_follower.py). Non-gold keys are the sleeve
#: executor's (`executor_runs`); a non-copy gold window has no FTMO executor.
FTMO_EXECUTABLE = frozenset({"gold_asia"})
#: Symbols the sleeve executor never trades: gold has one FTMO owner, the follower.
EXECUTOR_SKIP_SYMBOLS = frozenset({"XAUUSD"})
#: THE COPY IS THE PRINCIPAL'S SWITCH, NEVER THIS SOLVE'S. FTMO's rules ban copied/coordinated
#: trades across firms; the principal overrode that with informed consent on 2026-10-28 14:31Z
#: ("Copy anyway", cmsg G7EkJ9KTaSMy5a42YV4Hxg). So the gold_asia copy is a column ONLY while the
#: principal holds it on -- "ftmo" in gold_oco's lanes AND a non-zero ceiling in the PRINCIPAL'S OWN
#: file (`COPY_PRINCIPAL`, which this module never writes) -- and this solve may then only size it
#: inside [0, that ceiling]. The traded key in CERT_BOOK_LIVE is the solve's; the ceiling is never
#: read back from it, so an allocator write (a zero included) can neither ratchet the ceiling down
#: nor pause the copy. A zero or an absent file IS the principal's pause.
#: Every other column must be the FTMO account's own Tier S sleeve, off every E8 symbol.
COPY_COLUMNS = {"gold_asia": "principal override 2026-10-28 14:31Z: FTMO copies E8 gold_asia"}
COPY_PRINCIPAL = BASE / "data" / "FTMO_COPY_PRINCIPAL.json"
#: Fusion's measured commission per lot per side (cost_truth.py: 2.00 EUR on every symbol),
#: taken as 2.00 in the account currency so the FTMO excess over it is never under-stated.
FUSION_COMMISSION_PER_SIDE = 2.0
#: The broker hour each gold window places at (decision_core: gold_asia 07:00 broker).
GOLD_FILL_HOUR = {"gold_asia": 7, "gold_london_am": 13, "gold_afternoon": 17}
CHALLENGE_PHASES = ("phase1", "phase2")


@dataclass(frozen=True)
class VenueRules:
    """One firm's rule text, as fractions of the initial balance."""
    name: str
    daily_loss: float
    max_loss: float
    min_days: int
    targets: dict[str, float]          # phase -> profit target; the funded phase has none
    next_phase: dict[str, str]
    profit_cap: float | None = None    # E8: excess over +cap stripped at rollover
    source: str = ""


#: FTMO 2-Step, read 2026-10-28 from ftmo.com/en/trading-objectives and /en/2-step-challenge:
#: 10% then 5% target "with all positions closed"; Maximum Daily Loss 5% of the initial balance
#: under the balance at 00:00 CE(S)T, tested on equity incl. floating; Maximum Loss 10% static;
#: 4 Minimum Trading Days (a day a position is opened) in both phases; trading period unlimited.
FTMO_2STEP = VenueRules(
    name="ftmo_2step", daily_loss=0.05, max_loss=0.10, min_days=4,
    targets={"phase1": 0.10, "phase2": 0.05},
    next_phase={"phase1": "phase2", "phase2": "funded"},
    source="ftmo.com/en/trading-objectives + /en/2-step-challenge, read 2026-10-28")
#: E8 Pro (prop_barrier.py; principal off the dashboard 2026-09-12): 10% target, 10% static floor,
#: 2.5% daily from the day's starting balance incl. floating, 2% daily profit cap stripped.
E8_PRO = VenueRules(
    name="e8_pro", daily_loss=0.025, max_loss=0.10, min_days=0,
    targets={"phase1": 0.10}, next_phase={"phase1": "funded"}, profit_cap=0.02,
    source="prop_barrier.py (E8 invoice + dashboard, 2026-09-12)")
RULES = {"ftmo": FTMO_2STEP, "e8": E8_PRO}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


# ===================================================================== the account's own state

@dataclass
class AccountState:
    """Where the account stands NOW, as fractions of its initial balance."""
    phase: str = "phase1"
    balance: float = 1.0
    equity: float = 1.0
    day_start: float = 1.0
    days_traded: int = 0
    status: str = "ASSUMED_FRESH"
    why: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def measured(self) -> bool:
        return self.status == "MEASURED"


def read_account_state(path: Path = ACCOUNT_STATE, *, now: datetime | None = None,
                       rules: VenueRules = FTMO_2STEP) -> AccountState:
    """The venue reader's snapshot, or a fresh phase-1 account flagged as ASSUMED (never deployed
    from). Phase changes are the reader's to detect (new account key or balance reset)."""
    now = now or datetime.now(tz=UTC)
    doc = _read_json(path)
    if not isinstance(doc, dict) or doc.get("status") not in ("OK", "UNMEASURED") \
            or "balance" not in doc:
        why = "no FTMO account state" if doc is None else f"state status {doc.get('status')!r}"
        return AccountState(why=f"{why}: solved from a fresh phase-1 account; not deployable")
    try:
        initial = float(doc["initial_balance"])
        st = AccountState(phase=str(doc["phase"]), balance=float(doc["balance"]) / initial,
                          equity=float(doc["equity"]) / initial,
                          day_start=float(doc["day_start_balance"]) / initial,
                          days_traded=int(doc.get("days_traded") or 0),
                          status="MEASURED" if doc.get("status") == "OK" else "UNESTABLISHED",
                          detail={k: doc.get(k) for k in ("phase", "phase_why", "account_key",
                                                          "generated_at", "open_positions")})
        at = datetime.fromisoformat(str(doc["generated_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        return AccountState(why=f"state unreadable ({type(exc).__name__}: {exc}); not deployable")
    if st.phase not in (*rules.targets, "funded"):
        return AccountState(why=f"unknown phase {st.phase!r}; not deployable")
    if not st.measured:
        st.why = f"phase not established ({doc.get('phase_why')}); solved from it, not deployable"
        return st
    age = (now - at).total_seconds()
    if age > STATE_MAX_AGE_S:
        st.status = "STALE"
        st.why = f"state is {age / 3600:.1f}h old; solved from it, not deployable"
    else:
        st.why = f"state {age:.0f}s old"
    return st


# ===================================================================== the barrier simulation

def simulate_phase(r: np.ndarray, h: np.ndarray, rules: VenueRules, phase: str,
                   st: AccountState) -> dict[str, np.ndarray]:
    """Walk every path through one phase's rules from `st`, day by day.

    r: (paths, days, sleeves) daily R; h: (sleeves,) risk fraction of the initial balance.
    Returns per path: state (0 running, 1 pass, 2 daily breach, 3 max loss) and days used.
    """
    target = rules.targets.get(phase)
    n, t_n, _ = r.shape
    on = h > 0
    day = r @ h                                                      # (n, t)
    low = np.minimum(r, 0.0) @ h                                     # losers first: the day's low
    traded = (r[:, :, on] != 0).any(axis=2) if on.any() else np.zeros((n, t_n), dtype=bool)
    bal = np.full(n, st.balance)
    start = np.full(n, st.day_start)
    eq_now = st.equity
    done_days = np.full(n, st.days_traded)
    state = np.zeros(n, dtype=np.int8)
    days = np.full(n, t_n, dtype=np.int32)
    floor_max = 1.0 - rules.max_loss
    for t in range(t_n):
        live = state == 0
        if not live.any():
            break
        # Day 0 starts from the account's live equity against today's own starting balance.
        cur = bal if t else np.full(n, eq_now)
        trough = cur + low[:, t]
        f_d = live & (trough <= start - rules.daily_loss)
        f_m = live & ~f_d & (trough <= floor_max)
        bal = np.where(live, cur + day[:, t], bal)
        if rules.profit_cap is not None:
            bal = np.where(live, np.minimum(bal, start + rules.profit_cap), bal)
        done_days = done_days + (live & traded[:, t])
        state[f_d], state[f_m] = 2, 3
        days[f_d | f_m] = t + 1
        if target is not None:
            hit = live & ~f_d & ~f_m & (bal >= 1.0 + target)
            # At target before the minimum days: the rest are minimum-lot days, no modelled risk.
            state[hit] = 1
            days[hit] = t + 1 + np.maximum(rules.min_days - done_days[hit], 0)
        start = bal.copy()
    # PROGRESS TO THE TARGET (the tie-break, 2026-10-29): +1 at a pass, -1 at a failure, and a
    # running path's signed share of the way from the account now to the target, in [-1, 1].
    # Signed, so a size whose paths drift down (a negative edge) scores below standing aside.
    if target is not None:
        gap = max(1.0 + target - st.balance, 1e-9)
        prog = np.where(state == 1, 1.0,
                        np.where(state == 0, np.clip((bal - st.balance) / gap, -1.0, 1.0), -1.0))
    else:
        prog = np.zeros(n)
    return {"state": state, "days": days, "progress": prog}


def phase_outcome(sim: dict[str, np.ndarray], cont: np.ndarray | None,
                  horizon: int = HORIZON_DAYS) -> dict[str, float]:
    """J = E[1{funded} max(H - T, 0)]/H, with `cont` the next phases' own T (inf = never funded),
    paired path-for-path in a fixed shuffled order (independent phases)."""
    passed = sim["state"] == 1
    t = np.where(passed, sim["days"].astype(float), np.inf)
    if cont is not None:
        t = t + HANDOFF_DAYS + np.resize(cont, t.size)
    j = float(np.mean(np.clip(horizon - t, 0.0, None)) / horizon)
    tp = sim["days"][passed]
    return {"J": j, "p_pass": float(passed.mean()),
            "progress": float(np.mean(sim["progress"])) if "progress" in sim else 0.0,
            "p_fail": float(np.isin(sim["state"], (2, 3)).mean()),
            "p_daily": float((sim["state"] == 2).mean()),
            "p_max_loss": float((sim["state"] == 3).mean()),
            "p_unresolved": float((sim["state"] == 0).mean()),
            "days_median": float(np.median(tp)) if tp.size else None,
            "days_p90": float(np.percentile(tp, 90)) if tp.size else None,
            "p_funded_in_h": float(np.mean(np.isfinite(t) & (t <= horizon)))}


def funded_outcome(r: np.ndarray, h: np.ndarray, rules: VenueRules,
                   st: AccountState) -> dict[str, float]:
    """Funded: ruin-counted E[log W]/day of the account, breach of either limit = ruin."""
    sim = simulate_phase(r, h, rules, "funded", st)
    alive = sim["state"] == 0
    bal = st.balance + np.cumsum(r @ h, axis=1)[:, -1]
    lw = np.where(alive, np.log(np.clip(bal, 1e-9, None)), math.log(1.0 - rules.max_loss))
    return {"elog_per_day": float(lw.mean() / r.shape[1]), "p_breach": float((~alive).mean()),
            "p_daily": float((sim["state"] == 2).mean()),
            "p_max_loss": float((sim["state"] == 3).mean())}


# ===================================================================== paths

def draw_paths(worlds: np.ndarray, n: int, days: int, seed: int, block: int = 20) -> np.ndarray:
    """(n, days, sleeves): each path lives in ONE world and chains random `block`-day runs of its
    rows, which keeps the cross-section's co-movement and short-range serial dependence."""
    g = np.random.default_rng(seed)
    w_n, t_n, _ = worlds.shape
    block = min(block, t_n)
    wi = g.integers(0, w_n, n)
    k = -(-days // block)
    st = g.integers(0, t_n - block + 1, (n, k))
    rows = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(n, -1)[:, :days]
    return worlds[wi[:, None], rows, :]


# ===================================================================== the universe

def _symbol_of(col: str) -> str:
    return "XAUUSD" if col.startswith("gold_") else col.split("_", 1)[0]


def venue_listing() -> tuple[dict[str, dict[str, Any]], str]:
    """{symbol: registry row} on the FTMO terminal, and where it came from."""
    doc = _read_json(FTMO_REGISTRY)
    if isinstance(doc, dict) and isinstance(doc.get("symbols"), dict) and doc["symbols"]:
        return doc["symbols"], f"{FTMO_REGISTRY.name} ({doc.get('generated_at')})"
    q = _read_json(FTMO_QUOTES)
    if isinstance(q, dict) and "FTMO" in str((q.get("terminal") or {}).get("name", "")):
        rows = {s: v for s, v in (q.get("symbols") or {}).items()
                if isinstance(v, dict) and v.get("status") != "UNMEASURED"}
        return rows, f"{FTMO_QUOTES.name} FTMO-terminal snapshot ({q.get('at')})"
    return {}, "UNMEASURED: no FTMO registry on this host"


def tier_s_columns(screen: list[dict[str, Any]], doors: dict[str, Any]) -> dict[str, str]:
    """{world column: the certificate that makes it Tier S}. Bar read off the certificate."""
    store = _read_json(BASE / "reports" / "UNIVERSAL_SURVIVORS.json") or {}
    if not store.get("survivors"):
        store = _read_json(BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json") or {}
    certs = store.get("survivors") or {}
    rows = (doors or {}).get("rows") or {}
    out: dict[str, str] = {}
    for row in screen:
        key, col = row["certificate"], row.get("column")
        gate = ((certs.get(key) or {}).get("gates") or {}).get("deflated_sharpe") or {}
        dsr = gate.get("dsr")
        door = (rows.get(key) or {}).get("verdict")
        row["tier_s"] = {"dsr": dsr, "dsr_passed": gate.get("passed"), "door": door}
        if not (gate.get("passed") is True and isinstance(dsr, (int, float)) and dsr >= DSR_BAR):
            row.setdefault("ftmo_excluded", f"not Tier S: dsr {dsr!r} (bar {DSR_BAR})")
        elif door != "CLEAR":
            row.setdefault("ftmo_excluded", f"not Tier S: door verdict {door!r}")
        elif col and not row.get("excluded"):
            out.setdefault(col, key)
    return out


def venue_cost_bias(col: str, selector: str, listing: dict[str, Any],
                    ftmo_surface: dict[str, Any] | None, fusion_surface: dict[str, Any] | None,
                    registry: dict[str, Any] | None, *, risk_per_lot: float | None = None,
                    ftmo_commission: float | None = None) -> dict[str, Any]:
    """FTMO's spread at the sleeve's fill hour over the spread the replay charged, as an R bias.

    Both sides in PRICE units (each venue's own point), so a digits difference is not a cost.
    The charged side is the SMALLER of the replay's pooled spread and its own hour cell (whichever
    the replay used, the bias is then never under-stated). FTMO's hour cell comes from its own
    cost surface; until the venue reader has built one, FTMO's live registry spread scaled by
    Fusion's hour shape stands in, labelled PROXY_SHAPE.

    WHERE THE STOP IS MEASURED (the gold windows: the live ledger's risk per lot), the extra
    spread and commission are charged EXACTLY: 2 x (FTMO spread - charged spread) x contract over
    the risk per lot, plus 2 x (FTMO commission - Fusion's) per lot. Otherwise the allocator's
    ratio convention (`execution_cost`) applies, which assumes the whole BASE_COST_R is spread.
    """
    from libs.portfolio.execution_cost import BASE_COST_R, MAX_RATIO, fill_hour
    sym = _symbol_of(col)
    hour = GOLD_FILL_HOUR.get(col)
    if hour is None:
        hour, _ = fill_hour(selector, col)
    if hour is None:
        return {"status": "UNPRICED", "why": "no fill hour"}
    lrow = listing.get(sym) or {}
    f_point = lrow.get("point")
    fu = ((fusion_surface or {}).get("symbols") or {}).get(sym) or {}
    reg = (registry or {}).get(sym) or {}
    u_point = reg.get("point") or fu.get("point")
    if u_point is None:
        u_point = reg.get("tick_size") or fu.get("tick_size")
    try:
        f_point, u_point = float(f_point), float(u_point)
    except (TypeError, ValueError):
        return {"status": "UNPRICED", "why": f"{sym}: a venue point size is unknown"}
    fcell = ((((ftmo_surface or {}).get("symbols") or {}).get(sym) or {}).get("hours") or {}) \
        .get(str(hour)) or {}
    ucell = (fu.get("hours") or {}).get(str(hour)) or {}
    u_hour = ucell.get("p50") if ucell.get("status") == "MEASURED" else None
    u_pool = reg.get("median_spread_pts") or fu.get("pooled_median_spread_pts")
    charged = [float(v) for v in (u_hour, u_pool) if isinstance(v, (int, float)) and v > 0]
    if not charged:
        return {"status": "UNPRICED", "why": f"{sym}: the replay's charged spread is unknown"}
    charged_px = min(charged) * u_point
    if fcell.get("status") == "MEASURED" and isinstance(fcell.get("p50"), (int, float)):
        f_px, basis = float(fcell["p50"]) * f_point, "FTMO cost surface"
    else:
        live = lrow.get("live_spread_pts", lrow.get("spread"))
        hours = [float(c["p50"]) for c in (fu.get("hours") or {}).values()
                 if isinstance(c, dict) and c.get("status") == "MEASURED"
                 and isinstance(c.get("p50"), (int, float))]
        if not isinstance(live, (int, float)) or u_hour is None or not hours:
            return {"status": "UNPRICED", "why": f"{sym} h{hour:02d}: no FTMO spread at that hour"}
        shape = float(u_hour) / float(np.median(hours))
        f_px, basis = max(float(live), 1.0) * f_point * max(shape, 1.0), "PROXY_SHAPE"
    ratio_raw = f_px / charged_px
    ratio = min(ratio_raw, MAX_RATIO)
    contract = lrow.get("trade_contract_size") or reg.get("contract_size")
    if risk_per_lot is not None and not risk_per_lot > 0:
        return {"status": "UNPRICED", "why": f"{sym}: measured risk per lot {risk_per_lot!r}"}
    if risk_per_lot and isinstance(contract, (int, float)) and contract > 0:
        comm = 2.0 * max(float(ftmo_commission or 0.0) - FUSION_COMMISSION_PER_SIDE, 0.0)
        bias = (2.0 * max(f_px - charged_px, 0.0) * float(contract) + comm) / float(risk_per_lot)
        method = f"STOP_MEASURED (risk/lot {risk_per_lot:.0f})"
    else:
        bias = BASE_COST_R * max(ratio - 1.0, 0.0)
        method = f"RATIO x BASE_COST_R {BASE_COST_R}"
    return {"status": "PRICED", "basis": basis, "method": method, "hour": int(hour),
            "ftmo_spread_px": round(f_px, 8), "charged_spread_px": round(charged_px, 8),
            "ratio": round(ratio, 3), "ratio_raw": round(ratio_raw, 3),
            "bias_r_per_trade": round(bias, 4)}


def ftmo_commissions() -> dict[str, float]:
    """{symbol: commission per lot per side} MEASURED off the FTMO account's own deals (the venue
    reader's registry, else the FTMO-terminal snapshot). A symbol never traded there is absent."""
    out: dict[str, list[float]] = {}
    for path in (FTMO_REGISTRY, FTMO_QUOTES):
        doc = _read_json(path)
        if not isinstance(doc, dict):
            continue
        if "FTMO" not in str((doc.get("terminal") or {}).get("name", "")):
            continue
        for d in doc.get("deals") or []:
            try:
                vol, comm = float(d.get("vol") or 0), float(d.get("comm") or 0)
            except (TypeError, ValueError):
                continue
            if vol > 0 and d.get("sym"):
                out.setdefault(str(d["sym"]), []).append(abs(comm) / vol)
        if out:
            break
    return {k: float(np.median(v)) for k, v in out.items()}


def principal_ceiling(path: Path | None = None) -> dict[str, float]:
    """{copy column: the principal's ceiling} from COPY_PRINCIPAL; absent or unreadable = {}."""
    doc = _read_json(path or COPY_PRINCIPAL)
    out: dict[str, float] = {}
    for col in COPY_COLUMNS:
        raw = doc.get(col) if isinstance(doc, dict) else None
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
            out[col] = float(raw)
    return out


def copy_switch(path: Path | None = None) -> dict[str, tuple[bool, float, str]]:
    """{copy column: (on, the principal's ceiling, why)}. Fail-closed: unreadable = off."""
    ceiling = principal_ceiling(path)
    try:
        from mt5desk.gold_oco import declared_lanes
        lanes = declared_lanes()
    except Exception as exc:                              # pragma: no cover - box path
        lanes, lane_why = (), f"gold_oco lanes unreadable ({type(exc).__name__})"
    else:
        lane_why = f"gold_oco lanes {list(lanes)}"
    out: dict[str, tuple[bool, float, str]] = {}
    for col in COPY_COLUMNS:
        cur = ceiling.get(col, 0.0)
        on = "ftmo" in lanes and cur > 0
        out[col] = (on, cur, f"{lane_why}; {COPY_PRINCIPAL.name} {col} = {cur}")
    return out


def e8_symbols() -> set[str]:
    """Symbols E8's live book trades (a non-zero `e8` key in CERT_BOOK_LIVE)."""
    doc = _read_json(CERT_BOOK) or {}
    return {_symbol_of(k) for k, v in (doc.get("e8") or {}).items()
            if isinstance(v, (int, float)) and v > 0}


def quarantined_symbols() -> set[str]:
    doc = _read_json(SLEEVE_POLICY) or {}
    allow = doc.get("live_symbols") if isinstance(doc.get("live_symbols"), dict) else doc
    return {s for s, v in (allow or {}).items() if isinstance(v, list) and not v}


def executor_runs(col: str, specs: dict[str, Any]) -> bool:
    """Does an FTMO executor trade `col`? The follower's gold copy, or a non-gold sleeve whose
    certificate spec the sleeve executor can rebuild."""
    if col in FTMO_EXECUTABLE:
        return True
    spec = specs.get(col)
    return isinstance(spec, dict) and str(spec.get("symbol") or "").upper() not in \
        EXECUTOR_SKIP_SYMBOLS


def sleeve_spec(cert_key: str) -> tuple[dict[str, Any] | None, str]:
    """(the spec the sleeve executor runs, why): the certificate's own `shadow_spec`, in the
    E8 book's shape (prop/e8_book._load_survivors) so one reconstruction serves both lanes."""
    store = _read_json(BASE / "reports" / "UNIVERSAL_SURVIVORS.json") or {}
    if not store.get("survivors"):
        store = _read_json(BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json") or {}
    cert = (store.get("survivors") or {}).get(cert_key)
    if not isinstance(cert, dict):
        return None, f"certificate {cert_key} is not in the store"
    spec = cert.get("shadow_spec") or {}
    sym = str(spec.get("symbol") or cert.get("sym") or "").upper()
    fam = str(spec.get("family") or "")
    if not sym or not fam:
        return None, f"certificate {cert_key} carries no symbol/family spec"
    try:
        from admission_integrity import spec_fingerprint
        fp = spec_fingerprint(spec.get("symbol"), spec.get("family"), spec.get("selector"),
                              spec.get("side"), spec.get("params"))
    except Exception as exc:
        return None, f"spec fingerprint unavailable ({type(exc).__name__})"
    return {"key": cert_key, "symbol": sym, "family": fam,
            "selector": spec.get("selector") or "asia", "fingerprint": fp,
            "params": {k: v for k, v in spec.items()
                       if k not in ("symbol", "family", "selector", "is_universe", "hunt")}}, "ok"


def executable_columns(cols: list[str], uni: dict[str, Any]) -> set[str]:
    """The admitted columns an FTMO executor can send: the deployed book is solved over these
    alone."""
    specs = uni.get("specs") or {}
    return {c for c in cols if executor_runs(c, specs)}


def build_universe(seed: int = 0) -> dict[str, Any]:
    """Columns, world tensor and the screen, every gate fail-closed and named."""
    import kelly_survival as ks
    try:
        z = np.load(ks.WORLDS, allow_pickle=True)
    except (OSError, ValueError) as exc:
        return {"status": f"UNMEASURED: worlds unreadable ({type(exc).__name__})"}
    names = [str(x) for x in z["names"]]
    r_all = np.asarray(z["r"], dtype=float)
    cert_cols, screen = ks.certified_roster(names)
    r_c = r_all[:, :, [names.index(c) for c in cert_cols]] if cert_cols else r_all[:, :, :0]
    r_c, cert_cols, unpriced = ks._extend_worlds(r_c, cert_cols, screen, seed)
    doors = _read_json(DOORS) or {}
    tier_s = tier_s_columns(screen, doors)
    listing, listing_src = venue_listing()
    ftmo_surface = _read_json(FTMO_SURFACE)
    fusion_surface = _read_json(FUSION_SURFACE)
    registry = _read_json(UNIVERSE)
    e8_syms, quarantine = e8_symbols(), quarantined_symbols()
    from mt5desk.decision_core import principal_zero
    sel_of = {row.get("column"): row.get("selector") for row in screen if row.get("column")}

    cols: list[str] = []
    slices: list[np.ndarray] = []
    costs: dict[str, Any] = {}
    columns: dict[str, dict[str, Any]] = {}
    specs: dict[str, dict[str, Any]] = {}

    deals: list[dict[str, Any]] = []
    try:
        with ks.LEDGER.open(encoding="utf-8") as fh:
            deals = [json.loads(t) for t in (ln.strip() for ln in fh) if t.startswith("{")]
    except (OSError, ValueError):
        deals = []
    ev = ks.live_evidence(deals) if deals else {}
    commission = ftmo_commissions()

    def admit(col: str, series: np.ndarray, why: str) -> None:
        rpl = (ev.get(col[len("gold_"):]) or {}).get("risk_per_lot") if col.startswith("gold_") \
            else None
        cost = venue_cost_bias(col, str(sel_of.get(col) or ""), listing, ftmo_surface,
                               fusion_surface, registry,
                               risk_per_lot=float(np.median(rpl)) if rpl else None,
                               ftmo_commission=commission.get(_symbol_of(col)))
        costs[col] = cost
        if cost["status"] != "PRICED":
            columns[col] = {"admitted": False, "why": f"UNPRICED_AT_FTMO_COST: {cost['why']}",
                            "rail": "ftmo_unpriced"}
            return
        x = series - cost["bias_r_per_trade"] * (series != 0)
        cols.append(col)
        slices.append(x)
        columns[col] = {"admitted": True, "why": why}

    n_w, n_t = r_c.shape[0], r_c.shape[1]
    caps: dict[str, float] = {}
    for col, (on, cur, swhy) in copy_switch().items():
        if not on:
            columns[col] = {"admitted": False, "why": f"COPY_OFF: the principal's switch is off "
                                                      f"({swhy})", "rail": "ftmo_copy_switch"}
        elif col in names:
            admit(col, r_all[:n_w, :n_t, names.index(col)], f"{COPY_COLUMNS[col]} ({swhy})")
            caps[col] = cur
    for k, col in enumerate(cert_cols):
        sym = _symbol_of(col)
        reason = None
        if col in columns:
            continue
        if col not in tier_s:
            reason = "not Tier S (dsr bar or door verdict; see screen)"
        elif sym not in listing:
            reason = f"NOT_LISTED on the FTMO terminal ({listing_src})"
        elif sym in quarantine:
            reason = "quarantined in live_sleeve_policy.json"
        elif principal_zero(col, "ftmo"):
            reason = "principal zero"
        if reason:
            columns[col] = {"admitted": False, "why": reason, "rail": "ftmo_universe"}
            continue
        admit(col, r_c[:, :, k], f"Tier S via {tier_s[col]}")
        if columns[col].get("admitted"):
            spec, swhy = sleeve_spec(tier_s[col])
            if spec is not None:
                specs[col] = spec
            else:
                columns[col]["no_spec"] = swhy
        if sym in e8_syms and columns[col].get("admitted"):
            columns[col]["e8_overlap"] = True
            columns[col]["direction_fence"] = (
                f"E8 also trades {sym}: an order needs the cross-account opposite-side fence "
                "(cross_account.opposite_block / the gold direction lock) before it is sent")
    if not cols:
        return {"status": "NO_ADMISSIBLE_SLEEVE", "columns": columns, "screen": screen,
                "caps": caps,
                "costs": costs, "listing_source": listing_src, "unpriced": unpriced,
                "listing": listing, "tier_s": tier_s}
    r = np.stack(slices, axis=2)
    # Live evidence moves each column's mean exactly as the Fusion book solve does.
    post: dict[str, Any] = {}
    for k, c in enumerate(cols):
        live_r = ev.get(c[len("gold_"):], {}).get("r", []) if c.startswith("gold_") else []
        prior = float(r[:, :, k].mean())
        mean, weight = ks.posterior_shift(prior, live_r)
        r[:, :, k] += mean - prior
        post[c] = {"prior_r": round(prior, 4), "live_n": len(live_r),
                   "posterior_r": round(mean, 4), "live_weight": round(weight, 3)}
    return {"status": "OK", "cols": cols, "r": r, "columns": columns, "screen": screen,
            "caps": caps, "specs": specs,
            "costs": costs, "posterior": post, "listing_source": listing_src,
            "unpriced": unpriced, "listing": listing, "tier_s": tier_s}


# ===================================================================== the solve

@dataclass
class World:
    est: np.ndarray
    halved: np.ndarray


def make_worlds(r: np.ndarray, n: int, days: int, seed: int) -> tuple[World, World]:
    """(solve sample, independent validation sample), each as-estimated and edges-halved."""
    import kelly_survival as ks
    mu = r.mean(axis=(0, 1))
    r_h = r - ks.BOOK_HAIRCUT * np.maximum(mu, 0.0)
    return (World(draw_paths(r, n, days, seed + 1), draw_paths(r_h, n, days, seed + 1)),
            World(draw_paths(r, 2 * n, days, seed + 2), draw_paths(r_h, 2 * n, days, seed + 2)))


def evaluate(world: World, h: np.ndarray, rules: VenueRules, phase: str, st: AccountState,
             cont: dict[str, np.ndarray] | None) -> dict[str, Any]:
    if phase == "funded":
        e, hv = funded_outcome(world.est, h, rules, st), funded_outcome(world.halved, h, rules, st)
        return {"score": 0.5 * (e["elog_per_day"] + hv["elog_per_day"]),
                "risk": max(e["p_breach"], hv["p_breach"]), "as_estimated": e, "edges_halved": hv}
    c_e = cont["est"] if cont else None
    c_h = cont["halved"] if cont else None
    e = phase_outcome(simulate_phase(world.est, h, rules, phase, st), c_e)
    hv = phase_outcome(simulate_phase(world.halved, h, rules, phase, st), c_h)
    return {"score": 0.5 * (e["J"] + hv["J"]), "risk": max(e["p_fail"], hv["p_fail"]),
            "tie": 0.5 * (e["progress"] + hv["progress"]),
            "as_estimated": e, "edges_halved": hv}


def search(world: World, rules: VenueRules, phase: str, st: AccountState,
           cont: dict[str, np.ndarray] | None, cap: float | np.ndarray,
           rng: np.random.Generator,
           margin: float | None) -> tuple[np.ndarray, float]:
    """Multi-start pattern search (coordinate steps + pairwise transfers), the kelly_survival
    book search on this objective. `margin` None = unconstrained (the frontier's reference).

    LEXICOGRAPHIC: a move is taken when it raises the score, or leaves it within TIE_EPS and
    raises the progress to the target. Without the tie-break the search stalled on a flat zero
    (2026-10-29 15:33Z): every size small enough to keep P(fail) within the margin passed phase 1
    too slowly for the whole chain to fund inside the horizon, so J was exactly 0 everywhere
    feasible, no strict improvement existed, and the zero book deployed over a sleeve the
    unconstrained solve sized at 0.009. Progress still separates those sizes, so the search now
    climbs to the largest survivable one. The constraint is unchanged."""
    k = world.est.shape[2]
    worst = (-math.inf, -math.inf)

    def val(h: np.ndarray) -> tuple[float, float]:
        if np.any(h < 0) or np.any(h > cap + 1e-12):
            return worst
        ev = evaluate(world, h, rules, phase, st, cont)
        if margin is not None and ev["risk"] > margin:
            return worst
        return float(ev["score"]), float(ev.get("tie", 0.0))

    def better(v: tuple[float, float], cur: tuple[float, float]) -> bool:
        if v[0] > cur[0] + TIE_EPS:
            return True
        return v[0] >= cur[0] - TIE_EPS and v[1] > cur[1] + TIE_EPS

    best_h, best_v = np.zeros(k), val(np.zeros(k))
    for s in range(STARTS):
        h = np.full(k, 0.002) if s == 0 else rng.dirichlet(np.ones(k)) * rng.uniform(0.005, 0.03)
        h = np.minimum(h, cap)
        while val(h) == worst and h.sum() > 1e-4:
            h *= 0.8
        cur = val(h)
        if cur == worst:
            continue
        for step in STEPS:
            moved = True
            while moved:
                moved = False
                for i in range(k):
                    for d in (step, -step):
                        t = h.copy()
                        t[i] = max(0.0, t[i] + d)
                        v = val(t)
                        if better(v, cur):
                            h, cur, moved = t, v, True
                for i in range(k):
                    for j in range(k):
                        if i != j and h[i] >= step:
                            t = h.copy()
                            t[i] -= step
                            t[j] += step
                            v = val(t)
                            if better(v, cur):
                                h, cur, moved = t, v, True
        if better(cur, best_v):
            best_h, best_v = h, cur
    return best_h, best_v[0]


def empty_book_probe(world: World, h_u: np.ndarray, rules: VenueRules, phase: str,
                     st: AccountState, cont: dict[str, np.ndarray] | None,
                     cap: float | np.ndarray, margin: float) -> dict[str, Any] | None:
    """When the constrained book is empty: the first probe size along the unconstrained mix
    (`EMPTY_PROBE`, within the caps) that keeps P(fail) within `margin` AND scores or progresses,
    or None. A hit means positive sizes are feasible and useful, so the empty book is a search
    defect and must not deploy; None means zero is the survival answer (every size breaches)."""
    k = h_u.size
    d = h_u / h_u.sum() if h_u.sum() > 0 else np.full(k, 1.0 / k)
    for total in EMPTY_PROBE:
        h = np.minimum(d * total, cap)
        ev = evaluate(world, h, rules, phase, st, cont)
        if ev["risk"] <= margin and (ev["score"] > 0 or ev.get("tie", 0.0) > 0):
            return {"total_risk": round(float(h.sum()), 5), "risk": round(ev["risk"], 5),
                    "score": round(ev["score"], 6), "progress": round(ev.get("tie", 0.0), 5)}
    return None


def continuation(world: World, h: np.ndarray, rules: VenueRules, phase: str,
                 cont: dict[str, np.ndarray] | None, seed: int) -> dict[str, np.ndarray]:
    """Days from the START of `phase` to funded (inf = never), per path, for earlier phases."""
    g = np.random.default_rng(seed)
    out = {}
    for key, paths in (("est", world.est), ("halved", world.halved)):
        sim = simulate_phase(paths, h, rules, phase, AccountState())
        t = np.where(sim["state"] == 1, sim["days"].astype(float), np.inf)
        if cont is not None:
            t = t + HANDOFF_DAYS + cont[key][: t.size]
        out[key] = g.permutation(t)
    return out


def frontier(world: World, h: np.ndarray, rules: VenueRules, phase: str, st: AccountState,
             cont: dict[str, np.ndarray] | None) -> list[dict[str, Any]]:
    """The trade-off curve along the chosen mix: P(pass) against days, at scaled sizes."""
    pts = []
    for s in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
        ev = evaluate(world, h * s, rules, phase, st, cont)
        e = ev["as_estimated"]
        pts.append({"scale": s, "total_risk": round(float((h * s).sum()), 4),
                    "J_mix": round(ev["score"], 4), "worst_p_fail": round(ev["risk"], 4),
                    **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in e.items()}})
    return pts


def solve(venue: str = "ftmo", *, n_paths: int = N_PATHS, seed: int = 0,
          state: AccountState | None = None) -> dict[str, Any]:
    import kelly_survival as ks
    from mt5desk.sizing import MAX_RISK_FRAC

    from libs.portfolio.posterior_growth import EPS_STOP as EPS_DEATH
    rules = RULES[venue]
    now = datetime.now(tz=UTC)
    st = state or read_account_state(rules=rules, now=now)
    doc: dict[str, Any] = {
        "generated_at": now.isoformat(timespec="seconds"), "venue": venue, "rules": rules.name,
        "rules_source": rules.source,
        "objective": ("challenge: max J = E[1{funded} max(H-T,0)]/H over the remaining phases, "
                      "50/50 as-estimated and edges-halved, s.t. P(fail) <= margin on both; "
                      "funded: max ruin-counted E[log W], P(breach) <= margin on both"),
        "horizon_days": HORIZON_DAYS, "eps_death": EPS_DEATH, "margin": ks.BOOK_MARGIN,
        "account": {"phase": st.phase, "status": st.status, "why": st.why,
                    "balance_x_initial": round(st.balance, 5),
                    "equity_x_initial": round(st.equity, 5),
                    "day_start_x_initial": round(st.day_start, 5),
                    "days_traded": st.days_traded,
                    "to_target": (round(1 + rules.targets[st.phase] - st.balance, 5)
                                  if st.phase in rules.targets else None),
                    "to_daily_limit": round(st.equity - (st.day_start - rules.daily_loss), 5),
                    "to_max_loss": round(st.equity - (1 - rules.max_loss), 5)}}
    uni = build_universe(seed)
    doc["universe"] = {k: uni.get(k) for k in ("status", "columns", "costs", "posterior",
                                               "listing_source", "unpriced")}
    doc["gap_requests"] = write_gap_requests(uni, now)
    if uni["status"] != "OK":
        doc["status"] = uni["status"]
        doc["validation_score"] = 0.0
        doc["deployable"] = False
        doc["rail_blocks"] = rail_blocks(uni)
        return doc
    all_cols, r = uni["cols"], uni["r"]
    full_w, full_valid = make_worlds(r, n_paths, SIM_DAYS, seed)
    # THE DEPLOYED BOOK IS SOLVED OVER WHAT CAN BE SENT, AND NOTHING ELSE (audit #489 MF1). A joint
    # solve over every admitted column lets the optimiser move risk from a column that trades to a
    # correlated one with no executor, so the traded size would fall by side effect, never by
    # evidence. The paths are drawn per row, independent of the columns, so the executable slice
    # of the joint worlds IS the executable solve's input: adding a column with no executor can
    # never move the deployed book. The joint solve is published beside it (`joint_book`) as the
    # missed-growth view of the executors that do not exist yet.
    exec_idx = [k for k, c in enumerate(all_cols) if c in executable_columns(all_cols, uni)]
    if not exec_idx:
        doc["status"] = "NO_EXECUTABLE_SLEEVE"
        doc["validation_score"] = 0.0
        doc["deployable"] = False
        doc["sized_no_executor_columns"] = list(all_cols)
        doc["rail_blocks"] = rail_blocks(uni)
        return doc
    cols = [all_cols[k] for k in exec_idx]
    solve_w = World(full_w.est[:, :, exec_idx], full_w.halved[:, :, exec_idx])
    valid_w = World(full_valid.est[:, :, exec_idx], full_valid.halved[:, :, exec_idx])
    rng = np.random.default_rng(seed)
    # Per-column ceiling: the venue's per-trade cap, and for the principal's copy the value the
    # principal set (an equity fraction, so in initial-balance units at today's equity).
    cap_all = np.array([min(MAX_RISK_FRAC, uni["caps"][c] * st.equity) if c in uni["caps"]
                        else MAX_RISK_FRAC for c in all_cols])
    cap = cap_all[exec_idx]
    # BACKWARD INDUCTION: the last challenge phase first (from a fresh account), so every earlier
    # phase is valued by what passing it is actually worth.
    chain = [st.phase]
    while chain[-1] in rules.next_phase and rules.next_phase[chain[-1]] != "funded":
        chain.append(rules.next_phase[chain[-1]])
    phases: dict[str, Any] = {}
    cont: dict[str, np.ndarray] | None = None
    for i, phase in enumerate(reversed(chain)):
        here = st if phase == st.phase else AccountState(phase=phase)
        if phase == "funded":
            h, v = search(solve_w, rules, phase, here, None, cap, rng, ks.BOOK_MARGIN)
            h_u, v_u = h, v
        else:
            h, v = search(solve_w, rules, phase, here, cont, cap, rng, ks.BOOK_MARGIN)
            h_u, v_u = search(solve_w, rules, phase, here, cont, cap, rng, None)
        val = evaluate(valid_w, h, rules, phase, here, cont)
        block = {"from": "the account now" if phase == st.phase else "a fresh account",
                 "status": "OK" if v > -math.inf else "NO_SURVIVING_BOOK",
                 "risk_frac": {c: round(float(h[k]), 4) for k, c in enumerate(cols) if h[k] > 0},
                 "total_risk": round(float(h.sum()), 4),
                 "validation": _round(val),
                 "unconstrained": {"risk_frac": {c: round(float(h_u[k]), 4)
                                                 for k, c in enumerate(cols) if h_u[k] > 0},
                                   "score": round(v_u, 5) if v_u > -math.inf else None,
                                   "missed_score": (round(v_u - v, 5)
                                                    if v > -math.inf and v_u > -math.inf
                                                    else None)}}
        if phase != "funded":
            block["frontier"] = frontier(valid_w, h, rules, phase, here, cont)
        if val["risk"] > EPS_DEATH:
            block["status"] = "VALIDATION_FAILED: independent sample breaches EPS_DEATH"
        if phase != "funded" and not (h > 0).any() and (h_u > 0).any():
            # RED, NOT A ZERO (2026-10-29): an empty book while the unconstrained solve sizes an
            # admitted column is read against the probe. Feasible useful sizes exist -> the
            # search failed, the block is left as it is. None -> zero is the survival answer.
            hit = empty_book_probe(solve_w, h_u, rules, phase, here, cont, cap, ks.BOOK_MARGIN)
            block["empty_book_probe"] = hit or "every probe size breaches the margin or is idle"
            if hit is not None:
                prior = block["status"]
                block["status"] = ("EMPTY_BOOK_SEARCH_DEFECT: a positive size within the margin "
                                   "makes progress; not deployed"
                                   + ("" if prior == "OK" else f" (also {prior})"))
        phases[phase] = block
        if phase != "funded" and phase != st.phase:
            cont = continuation(solve_w, h, rules, phase, cont, seed + 10 + i)
    doc["phases"] = phases
    now_block = phases[st.phase]
    doc["book"] = dict(now_block["risk_frac"])
    # THE EXECUTOR SIZES ON EQUITY (prop/ftmo_follower: fraction x equity); the solve sizes on the
    # initial balance. The written fraction carries the same dollars at today's equity.
    specs = uni.get("specs") or {}
    doc["executable"] = {c: math.floor(v / st.equity * 1e5) / 1e5 for c, v in doc["book"].items()}
    doc["specs"] = {c: specs[c] for c in doc["executable"] if c in specs}
    doc["sized_no_executor"] = {}
    # Missed growth (Rule 1): the joint solve over every admitted column, from the same account
    # and the same continuation, against the deployed book -- what the missing executors cost.
    if len(cols) < len(all_cols) and now_block["status"] == "OK":
        h_j, v_j = search(full_w, rules, st.phase, st, cont, cap_all, rng, ks.BOOK_MARGIN)
        if v_j > -math.inf:
            j_joint = evaluate(full_valid, h_j, rules, st.phase, st, cont)["score"]
            j_exec = now_block["validation"]["score"]
            doc["joint_book"] = {c: round(float(h_j[k]), 4) for k, c in enumerate(all_cols)
                                 if h_j[k] > 0}
            doc["sized_no_executor"] = {c: v for c, v in doc["joint_book"].items()
                                        if c not in cols}
            doc["missed_growth_no_executor"] = {"J_joint": round(j_joint, 5),
                                                "J_executable": round(j_exec, 5),
                                                "J_missed": round(j_joint - j_exec, 5)}
    doc["rail_blocks"] = rail_blocks(uni)
    doc["e8_overlap"] = sorted(c for c, row in (uni.get("columns") or {}).items()
                               if row.get("e8_overlap"))
    doc["status"] = now_block["status"]
    doc["validation_score"] = (now_block["validation"]["score"]
                               if now_block["status"] == "OK" else 0.0)
    doc["deployable"] = bool(now_block["status"] == "OK" and st.measured)
    # `book` and `executable` are the solve, never the deployed block: a reader that does not
    # check `deployable` is told so in the file itself (audit 2026-10-29).
    doc["book_deployed"] = doc["deployable"]
    if str(doc["status"]).startswith("EMPTY_BOOK_SEARCH_DEFECT"):
        doc["red"] = ("RED EMPTY_BOOK_SEARCH_DEFECT: the solve came back empty while a size within "
                      "the margin makes progress; the standing ftmo block is left deployed")
    return doc


def mark_defect(doc: dict[str, Any], prev: Any) -> None:
    """Carry a standing EMPTY_BOOK_SEARCH_DEFECT's start across passes (from the last report), so
    its RED line says how long the old block has stood; a sound pass drops both."""
    if not str(doc.get("status")).startswith("EMPTY_BOOK_SEARCH_DEFECT"):
        doc.pop("red", None)
        doc.pop("defect_since", None)
        return
    was = isinstance(prev, dict) and str(prev.get("status")).startswith("EMPTY_BOOK_SEARCH_DEFECT")
    since = (prev.get("defect_since") if was and isinstance(prev, dict) else None) \
        or doc.get("generated_at")
    doc["defect_since"] = since
    doc["red"] = (f"RED EMPTY_BOOK_SEARCH_DEFECT since {since}: the solve came back empty while "
                  f"a size within the margin makes progress; the standing ftmo block is left "
                  f"deployed")


def rail_blocks(uni: dict[str, Any]) -> list[dict[str, Any]]:
    """Every column a rail kept out, with its prior mean R: the missed-growth ledger's input.
    Its J is UNMEASURED -- a column the venue cannot list or price cannot be simulated there."""
    out = []
    for col, row in (uni.get("columns") or {}).items():
        if row.get("admitted") or not row.get("rail"):
            continue
        out.append({"column": col, "rail": row["rail"], "why": row["why"],
                    "missed_J": "UNMEASURED"})
    return out


def _round(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    return round(x, 5) if isinstance(x, float) else x


# ===================================================================== gap requests

def write_gap_requests(uni: dict[str, Any], now: datetime,
                       path: Path | None = None) -> dict[str, Any]:
    """FTMO-listed FX and metal symbols with no Tier S sleeve, as targeted hypotheses on the
    families that certify elsewhere. One file, rewritten each pass, read by the miner compiler.
    `path` defaults to GAP_REQUESTS read at call time, so a test's redirect reaches it."""
    path = path or GAP_REQUESTS
    listing = uni.get("listing") or {}
    tier_s = uni.get("tier_s") or {}
    covered = {_symbol_of(c) for c in tier_s}
    # THE FAMILIES ARE EVERY TEN-GATE CERTIFICATE'S, not only Tier S: a family that certified
    # anywhere is the best-evidenced mechanism to aim at an FTMO symbol, and the gauntlet (not
    # this file) decides whether the new cell earns anything.
    fams = sorted({c.split("_", 1)[1].rsplit("_", 1)[0] for c in tier_s if "_" in c}
                  | {row.get("family") for row in (uni.get("screen") or [])
                     if row.get("family") and not row.get("excluded")})
    fams = [f for f in fams if f]

    def tradable_fx(sym: str) -> bool:
        return (len(sym) == 6 and sym.isalpha() and sym.isupper()) or sym.startswith("XA")

    gaps = sorted(s for s in listing if tradable_fx(s) and s not in covered)
    # ONE ROW PER SYMBOL: the compiler reads at most a handful of declared symbols per row
    # (miner_candidate_compiler._MAX_TEXT_SYMBOLS), so a row naming all the gaps tests four.
    rows = [{"kind": "hypothesis", "family": f, "symbols": [g],
             "source": "ftmo_allocator",
             "title": f"FTMO gap: {f} on {g}, FTMO-listed with no Tier S sleeve",
             "text": (f"The FTMO allocator has no Tier S certified sleeve on {g}, which the FTMO "
                      f"terminal lists. {f} certifies elsewhere; test it on {g}."),
             "at": now.isoformat(timespec="seconds")} for f in fams for g in gaps]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        os.replace(tmp, path)
        wrote = path.relative_to(BASE).as_posix() if path.is_relative_to(BASE) else str(path)
    except OSError as exc:
        wrote = f"unwritten ({type(exc).__name__})"
    return {"listed": len(listing), "covered_tier_s": sorted(covered), "gap_symbols": len(gaps),
            "families": fams, "rows": len(rows), "file": wrote}


# ===================================================================== deployment

def apply_book(doc: dict[str, Any], path: Path = CERT_BOOK, armed: Path = ARMED,
               principal: Path | None = None) -> dict[str, Any]:
    """Lay the executable keys into CERT_BOOK_LIVE's `ftmo` block, only when armed and sound."""
    if not armed.exists():
        return {"applied": False, "why": f"standby: {armed.name} absent"}
    if not doc.get("deployable"):
        return {"applied": False, "why": f"not deployable ({doc.get('status')}; account "
                                         f"{(doc.get('account') or {}).get('status')})"}
    from mt5desk.sizing import MAX_RISK_FRAC
    book = _read_json(path)
    if not isinstance(book, dict) or book.get("enabled") is not True:
        return {"applied": False, "why": "CERT_BOOK_LIVE.json unreadable or not enabled"}
    block = dict(book.get("ftmo") or {})
    # Every key the solve can execute, and every numeric key already in the block: one the solve
    # no longer funds is written 0 (fail closed), never left at its old size.
    keys = set(FTMO_EXECUTABLE) | set(doc.get("executable") or {}) | {
        k for k, v in block.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    new = {k: float((doc.get("executable") or {}).get(k, 0.0)) for k in sorted(keys)}
    if any(not 0.0 <= v <= MAX_RISK_FRAC for v in new.values()):
        return {"applied": False, "why": "a value lies outside [0, MAX_RISK_FRAC]"}
    ceiling = principal_ceiling(principal)
    for k, v in new.items():
        if k in COPY_COLUMNS and v > ceiling.get(k, 0.0) + 1e-12:
            # The principal's file is the ceiling and its zero (or absence) the pause: the solve
            # never re-opens the copy and never sizes it above what the principal set.
            return {"applied": False,
                    "why": f"{k} {v} would exceed the principal's {ceiling.get(k, 0.0)}"}
    if all(abs(block.get(k, -1) - v) < 1e-9 for k, v in new.items()):
        return {"applied": False, "why": "unchanged"}
    block.update(new)
    book["ftmo"] = block
    book["ftmo_by"] = (f"research/prop_challenge_allocator.py {doc['generated_at']} "
                       f"({doc['account']['phase']}, J-mix solve; armed by "
                       f"{armed.name})")
    # The follower reads this file every minute: tmp + fsync + os.replace, retried on Windows'
    # PermissionError -- the follower's own writer.
    from prop.ftmo_follower import _atomic_write
    _atomic_write(path, json.dumps(book, indent=1))
    return {"applied": True, "ftmo": new}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--venue", choices=sorted(RULES), default="ftmo")
    ap.add_argument("--paths", type=int, default=N_PATHS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = solve(a.venue, n_paths=a.paths, seed=a.seed)
    mark_defect(doc, _read_json(a.out))
    if doc.get("red"):
        print(doc["red"], file=sys.stderr)
    if a.venue == "ftmo":
        try:
            doc["deploy"] = apply_book(doc)
        except Exception as exc:                          # the report is written regardless
            doc["deploy"] = {"applied": False, "why": f"write failed ({type(exc).__name__}: {exc})"}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    os.replace(tmp, a.out)
    ph = (doc.get("phases") or {}).get(doc["account"]["phase"]) or {}
    print(f"prop_challenge_allocator[{a.venue}]: {doc.get('status')} phase="
          f"{doc['account']['phase']} ({doc['account']['status']}) book={doc.get('book')} "
          f"J={((ph.get('validation') or {}).get('score'))} deploy={doc.get('deploy')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
