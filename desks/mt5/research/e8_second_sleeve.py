#!/usr/bin/env python3
"""THE E8 SECOND SLEEVE: which candidate, beside gold_asia, adds the most independent edge to E8.

BACKLOG row 26 (Max-growth, 2026-10-13): "Find at least one more promising, max-uncorrelated,
max-edge sleeve for E8 beside gold." Since the principal's 2026-10-20 21:52Z order the E8 book
trades gold_asia alone (CERT_BOOK_LIVE.json `e8`), and E8 readiness is counted in INDEPENDENT
MECHANISMS, never certificates (docs/PROP_FIRM_E8.md). One sleeve is one mechanism. This organ
ranks every candidate the desk knows about against that book and names the best ones, or names
the exact gate that stops each one.

IT IS A RANKER AND NOTHING ELSE. It writes one report. It sizes nothing, arms nothing, writes no
CERT_BOOK block and adds no cap or veto anywhere: the gates below decide where a candidate sits in
the ranking, never whether anything trades. Trading a winner is the E8 book owner's act (see
`WIRING`).

THE CANDIDATES, four tiers, every one read from an artifact LIVE already publishes:

  JOINT       a column of the allocator's world tensor (data/pf_allocator_cache/worlds.npz). These
              carry daily R on the SAME rows as gold_asia, so correlation, crisis correlation,
              tail co-loss, marginal E[log W] and the E8 barrier are all MEASURED.
  CERTIFIED   a certificate (reports/FORWARD_ENROLMENT.json `certificates`, the canon the
              enrolment leg reads, plus reports/UNIVERSAL_SURVIVORS.json) that is not a column.
  NEAR        a power-deficient near-certified cell on the forward cure
              (reports/FORWARD_CURE_ROSTER.json, else reports/POWER_CURE_CANDIDATES.json).
  FORWARD     a forward clock with evidence (reports/shadow/*_shadow_state.json) that holds no
              certificate.

Only a JOINT candidate can be ELIGIBLE: the others have no daily series on gold_asia's rows, so
their correlation and their marginal E[log W] are UNMEASURED, and an absent input is never read
as a pass. Their missing gate is named (`joint_series`) and so is the organ that would close it.

THE GATES, each PASS / FAIL / UNMEASURED, every one published per candidate:

  mechanism      its family differs from gold_asia's. gold_asia is the asia session-range bracket
                 on XAUUSD (decision_core: "Session-range brackets"; docs/BOOK_E8_MEASURED.md
                 Finding 1), i.e. `session_range_breakout`. Another srb sleeve, on any symbol, is
                 the same mechanism and adds no independent bet.
  e8_symbol      the venue lists it. The measured catalogue (data/e8_catalogue.json, written by
                 prop/e8_book.py whenever the venue answers) decides when present. Without it, the
                 documented 2026-09-13 measurement (PROP_FIRM_E8.md: "E8 lists no Scandi or EM
                 crosses", ten blocked symbols named) fails a Scandi/EM cross, and the symbols the
                 desk has positive evidence the venue quotes pass; anything else is UNMEASURED.
  session        the E8 executor runs H1 bars (prop/e8_executor LOOKBACK_BARS, family_call's H1
                 sessions), so an M5/M15/M30 spec does not fit the lane that would trade it.
  no_opposite    E8 forbids opposite trades across accounts. A symbol another account's book also
                 trades (CERT_BOOK_LIVE `fusion` / `ftmo`, non-zero) needs the cross-account fence
                 (mt5desk.cross_account.opposite_block) at the order: FENCE_REQUIRED, published.
  correlation    |rho| with gold_asia over every row AND over the crisis worlds both at or under
                 kelly_survival.BOOK_MAX_CORR (the book solve's own bar).
  headroom       with the candidate added at the chosen size, P(a day's adversarial low breaches
                 the 2.5% daily loss) stays within max(EPS_DEATH, what gold_asia alone carries).
                 The low is taken the prop allocator's way: every losing leg lands before any
                 winning one, so floating loss is never under-stated.
  growth         marginal ruin-counted E[log W] (kelly_survival.ruin_counted_elog) is positive and
                 E8 P(pass) (kelly_survival.e8_barrier: 2% daily cap stripped, $90k floor, 2.5%
                 daily) is not lowered, on the 50/50 mixture of the as-estimated and edges-halved
                 worlds (kelly_survival.BOOK_HAIRCUT) the allocators already use.
  evidence       net of cost: a forward clock with n >= FORWARD_MIN_N decides by its own sign
                 (forward R is cost-rebased by the clock); else a certificate's x3-cost
                 expectancy; else UNMEASURED.

THE SIZE is the E8 risk grid (kelly_survival.E8_RISKS), and the chosen one is the size with the
largest mixture marginal E[log W] whose headroom holds. Choosing the growth-optimal admissible size
is a measurement for the ranking, not a sizing decision: the allocator sizes what trades.

EVIDENCE MOVES THE PRIOR. A column's per-trade mean (its non-zero rows) is shifted toward its
forward clock's realised R exactly as kelly_survival moves the gold windows on live R
(`posterior_shift`: the prior is K_SLEEVE observations, each forward trade LIVE_WEIGHT). gold_asia
uses its live ledger when one is on the host and its forward clock (XAUUSD.asia) otherwise.

    -> reports/E8_SECOND_SLEEVE.json   (hourly leg `e8_second_sleeve`)

    python desks/mt5/research/e8_second_sleeve.py [--paths 2000] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "E8_SECOND_SLEEVE.json"
CERT_BOOK = BASE / "data" / "CERT_BOOK_LIVE.json"
E8_CATALOGUE = BASE / "data" / "e8_catalogue.json"
ENROLMENT = BASE / "reports" / "FORWARD_ENROLMENT.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
CURE_ROSTER = BASE / "reports" / "FORWARD_CURE_ROSTER.json"
CURE_SNAPSHOT = BASE / "reports" / "POWER_CURE_CANDIDATES.json"
SHADOW_DIR = BASE / "reports" / "shadow"
SHADOW_LANES = ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json",
                "external_shadow_state.json")

PASS, FAIL, UNMEASURED, FENCE = "PASS", "FAIL", "UNMEASURED", "FENCE_REQUIRED"

#: The live E8 book's one sleeve and the key its forward clock is filed under (CERT_BOOK_LIVE
#: `e8_pins`: "gateway window gold_asia, clock XAUUSD.asia").
GOLD = "gold_asia"
GOLD_CLOCK = "XAUUSD.asia"
GOLD_SYMBOL = "XAUUSD"
#: gold_asia's mechanism: the asia session-range bracket (decision_core "Session-range brackets
#: hit this ..."; BOOK_E8_MEASURED.md Finding 1: the live book is one mechanism,
#: session_range_breakout). Every gold window shares it.
GOLD_FAMILY = "session_range_breakout"
#: Used only when CERT_BOOK_LIVE carries no positive gold_asia value (the box's 2026-10-20 value).
GOLD_RISK_FALLBACK = 0.006

#: A forward clock with at least this many observations decides the evidence gate by its sign.
#: Below it the clock is published as depth but the certificate's costed backtest decides.
FORWARD_MIN_N = 10
#: Paths per world for the E8 barrier and E[log W] (the kelly_survival E8 count).
N_PATHS = 2000
#: Unpriced candidates published in full; the rest are counted.
MAX_UNPRICED_ROWS = 25
TOP_N = 3

#: E8's own rule text (kelly_survival E8 constants, docs/PROP_FIRM_E8.md).
E8_RULES = {"daily_loss_incl_floating": 0.025, "daily_profit_cap": 0.02,
            "floor_usd": 90_000.0, "initial_usd": 100_000.0, "target_usd": 110_000.0,
            "no_opposite_trades_across_accounts": True, "no_scandinavian_pairs": True}
#: The venue lists "no Scandi or EM crosses" (PROP_FIRM_E8.md, 2026-09-13 connection) and the
#: principal's rule bans Scandinavian pairs outright.
SCANDI = ("NOK", "SEK", "DKK")
EM = ("ZAR", "MXN", "TRY", "HUF", "PLN", "CZK", "CNH")
#: The ten symbols the venue refused on 2026-09-13 (PROP_FIRM_E8.md "Blocked symbols").
DOCUMENTED_BLOCKED = frozenset({"CHFNOK", "EURNOK", "GBPNOK", "GBPSEK", "EURZAR", "GBPZAR",
                                "USDZAR", "GBPMXN", "USDMXN", "CHFDKK"})
#: Symbols with POSITIVE evidence that the venue lists them, used only when the measured
#: catalogue is not on this host. Each with its source; nothing here is inferred from absence.
DOCUMENTED_LISTED: dict[str, str] = {
    **dict.fromkeys(("USDJPY", "CADJPY", "EURJPY", "GBPJPY", "XAUUSD"),
                    "PROP_FIRM_E8.md 2026-09-13: session_range_breakout 15 tradeable / 0 blocked "
                    "(BOOK_E8_MEASURED.md: those five symbols)"),
    **dict.fromkeys(("AUDCHF", "CADCHF", "GBPCHF"),
                    "PROP_FIRM_E8.md 2026-09-13: overnight_gap_decay 3 tradeable -- the twelve "
                    "certified symbols minus the nine blocked"),
    "EURUSD": "PROP_FIRM_E8.md: quoted live at 0.431 bps",
    "AUDNZD": "prop/e8_executor.py cost-fence note: quoted on the venue",
    "AUDCAD": "prop/e8_executor.py cost-fence note: quoted on the venue",
}
#: Timeframes the E8 executor's H1 fetch can run.
E8_TIMEFRAMES = ("H1",)

WIRING = (
    "Nothing here trades. To trade a winner on E8: (1) the E8 book owner adds its key to the "
    "`e8` block of desks/mt5/data/CERT_BOOK_LIVE.json (keyed SYMBOL_family_selector, the "
    "allocator's naming) with a fraction from the allocator -- prop/e8_executor sizes e8 keys from "
    "that block and prop/e8_gold.window_risk sizes gold; (2) the certificate's shadow_spec must "
    "reconstruct in prop/e8_executor (the `e8_pins` row names its clock); (3) a symbol another "
    "account also trades needs mt5desk.cross_account.opposite_block at the order. An UNPRICED "
    "candidate first needs a column in data/pf_allocator_cache/worlds.npz (research/pf_allocator.py "
    "prices certificates into the world tensor), after which this ranker measures it on the next "
    "pass.")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _round(x: Any, k: int = 6) -> Any:
    return round(float(x), k) if isinstance(x, (int, float, np.floating)) and \
        math.isfinite(float(x)) else x


# ===================================================================== naming

def column_identity(col: str) -> dict[str, str]:
    """(symbol, family, selector, timeframe) of a world column, from the allocator's naming
    (`SYMBOL_family_selector`, `gold_<window>`, `SYM_asia_FAILED_BREAK`, the scalp lane's
    `xau_m15_anti_breakout`)."""
    if col.startswith("gold_"):
        return {"symbol": GOLD_SYMBOL, "family": GOLD_FAMILY, "selector": col[len("gold_"):],
                "timeframe": "H1"}
    m = re.match(r"^xau_(m\d+)_(anti_\w+?)(?:_(overlap|ny|asia|london))?$", col)
    if m:
        return {"symbol": GOLD_SYMBOL, "family": m.group(2), "selector": m.group(3) or "all",
                "timeframe": m.group(1).upper()}
    m = re.match(r"^([A-Z0-9]+)_(\w+?)_FAILED_BREAK$", col)
    if m:
        return {"symbol": m.group(1), "family": "failed_breakout", "selector": m.group(2),
                "timeframe": "H1"}
    sym, _, rest = col.partition("_")
    fam, _, sel = rest.rpartition("_")
    return {"symbol": sym, "family": fam or rest, "selector": sel or "all", "timeframe": "H1"}


def clock_key(symbol: str, family: str, selector: str) -> str:
    """The forward lane's base key: `SYM.family.selector`; session_range_breakout files as
    `SYM.selector` (shadow_state: `USDJPY.asia`)."""
    if family == GOLD_FAMILY:
        return f"{symbol}.{selector}"
    return f"{symbol}.{family}.{selector}"


def _key_timeframe(key: str) -> str:
    m = re.search(r"@(M\d+|H\d+|D1)", key)
    return m.group(1).upper() if m else "H1"


def _key_identity(key: str) -> tuple[str, str, str]:
    """(symbol, family, selector) of a forward-lane key `SYM.family.selector[@TF][#params]`."""
    base = key.split("#", 1)[0].split("@", 1)[0]
    parts = base.split(".")
    if len(parts) == 2:
        return parts[0].upper(), GOLD_FAMILY, parts[1]
    if len(parts) >= 3:
        return parts[0].upper(), parts[1], parts[2]
    return base.upper(), "", ""


# ===================================================================== evidence

def forward_clocks() -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Every forward clock with a row count, keyed as its lane files it, and the lanes read."""
    out: dict[str, dict[str, Any]] = {}
    read: list[str] = []
    for lane in SHADOW_LANES:
        doc = _read_json(SHADOW_DIR / lane)
        if not isinstance(doc, dict):
            continue
        read.append(lane)
        rows = doc.get("sleeves") if isinstance(doc.get("sleeves"), dict) else doc
        for k, v in rows.items():
            if isinstance(v, dict) and _num(v.get("n")) is not None:
                out[str(k)] = {"lane": lane, "n": int(v.get("n") or 0),
                               "exp_r": _num(v.get("exp_r")), "forward_t": _num(v.get("forward_t")),
                               "max_dd_r": _num(v.get("max_dd_r")), "status": v.get("status")}
    return out, read


def certificate_gates() -> dict[str, dict[str, Any]]:
    """`SYM.family.selector` -> the strongest certificate's costed gates (UNIVERSAL_SURVIVORS)."""
    doc = _read_json(SURVIVORS) or {}
    out: dict[str, dict[str, Any]] = {}
    for key, c in (doc.get("survivors") or {}).items():
        if not isinstance(c, dict):
            continue
        spec = c.get("shadow_spec") or {}
        parts = str(key).split(".")
        sym = str(c.get("sym") or spec.get("symbol") or (parts[1] if len(parts) > 1 else ""))
        fam = str(spec.get("family") or (parts[2] if len(parts) > 2 else ""))
        sel = str(spec.get("selector") or "asia")
        g = c.get("gates") or {}
        row = {"certificate": key, "timeframe": str(spec.get("timeframe") or "H1").upper(),
               "exp_x3_costs": _num((g.get("stress_costs") or {}).get("exp_x3")),
               "wf_oos_sharpe": _num((g.get("walk_forward") or {}).get("oos_sharpe")),
               "dsr": _num((g.get("deflated_sharpe") or {}).get("dsr")),
               "ev": _num((g.get("expected_value") or {}).get("ev"))}
        ck = f"{sym.upper()}.{fam}.{sel}"
        prev = out.get(ck)
        if prev is None or (row["exp_x3_costs"] or -1e9) > (prev["exp_x3_costs"] or -1e9):
            out[ck] = row
    return out


def enrolled_certificates() -> tuple[list[dict[str, Any]], str]:
    doc = _read_json(ENROLMENT)
    if not isinstance(doc, dict) or not isinstance(doc.get("certificates"), list):
        return [], f"UNMEASURED: {ENROLMENT.name} absent or unreadable"
    return [r for r in doc["certificates"] if isinstance(r, dict)], \
        f"{ENROLMENT.name} at {doc.get('at')}"


def near_certified() -> tuple[list[dict[str, Any]], str]:
    """Near-certified cells on the forward cure: the cumulative roster, else the snapshot."""
    for path, field in ((CURE_ROSTER, "rows"), (CURE_SNAPSHOT, "candidates")):
        doc = _read_json(path)
        rows = doc.get(field) if isinstance(doc, dict) else None
        if isinstance(rows, dict):
            out = []
            for k, v in rows.items():
                v = v if isinstance(v, dict) else {}
                parts = str(k).split(".")
                out.append({"key": str(k),
                            "symbol": str(v.get("symbol") or v.get("sym")
                                          or (parts[1] if len(parts) > 1 else "")).upper(),
                            "family": str(v.get("family")
                                          or (parts[2] if len(parts) > 2 else "")),
                            "selector": str(v.get("selector") or "asia")})
            return out, f"{path.name} ({len(out)} rows)"
    return [], (f"UNMEASURED: neither {CURE_ROSTER.name} nor {CURE_SNAPSHOT.name} is on this "
                "host")


def evidence_gate(fwd: dict[str, Any] | None, cert: dict[str, Any] | None) -> dict[str, Any]:
    """Net-of-cost evidence depth and its verdict."""
    out: dict[str, Any] = {"forward": fwd, "certificate": cert}
    n = int((fwd or {}).get("n") or 0)
    er = (fwd or {}).get("exp_r")
    x3 = (cert or {}).get("exp_x3_costs")
    if n >= FORWARD_MIN_N and er is not None:
        out.update(depth=f"FORWARD_NET n={n}", verdict=PASS if er > 0 else FAIL,
                   why=f"forward clock {n} obs, net exp_r {er:+.3f}R, t {fwd.get('forward_t')}")
    elif x3 is not None:
        out.update(depth=f"BACKTEST_X3_COSTS (forward n={n})", verdict=PASS if x3 > 0 else FAIL,
                   why=f"certificate expectancy at 3x costs {x3:+.4f}R; forward n={n} under "
                       f"{FORWARD_MIN_N}")
    elif n > 0 and er is not None:
        out.update(depth=f"FORWARD_THIN n={n}", verdict=UNMEASURED,
                   why=f"forward clock only {n} obs (< {FORWARD_MIN_N}) and no costed certificate")
    else:
        out.update(depth="NONE", verdict=UNMEASURED,
                   why="no forward clock and no costed certificate on this host")
    return out


def best_clock(clocks: dict[str, dict[str, Any]], symbol: str, family: str, selector: str,
               timeframe: str = "H1") -> tuple[str | None, dict[str, Any] | None]:
    """The base clock for the cell when it exists, else its strongest variant at that timeframe."""
    base = clock_key(symbol, family, selector)
    if base in clocks:
        return base, clocks[base]
    best: tuple[str | None, dict[str, Any] | None] = (None, None)
    for k, v in clocks.items():
        if _key_identity(k) == (symbol, family, selector) and _key_timeframe(k) == timeframe:
            if best[1] is None or (v.get("forward_t") or -1e9) > (best[1].get("forward_t") or -1e9):
                best = (k, v)
    return best


# ===================================================================== static gates

def mechanism_gate(family: str) -> dict[str, Any]:
    if not family:
        return {"verdict": UNMEASURED, "why": "no family on the candidate"}
    if family == GOLD_FAMILY:
        return {"verdict": FAIL, "why": f"{family} is gold_asia's own mechanism: one bet, two names"}
    return {"verdict": PASS, "why": f"{family} differs from gold_asia's {GOLD_FAMILY}"}


def e8_catalogue() -> tuple[set[str] | None, str]:
    doc = _read_json(E8_CATALOGUE)
    rows = doc.get("instruments") if isinstance(doc, dict) else None
    if isinstance(rows, list) and rows:
        return {str(r).upper() for r in rows}, \
            f"{E8_CATALOGUE.name} measured {doc.get('measured_utc')} ({len(rows)} instruments)"
    return None, f"{E8_CATALOGUE.name} not on this host; the documented 2026-09-13 reading decides"


def symbol_gate(symbol: str, catalogue: set[str] | None) -> dict[str, Any]:
    s = symbol.upper()
    if any(c in s for c in SCANDI):
        return {"verdict": FAIL, "why": f"{s} is a Scandinavian pair (E8 rule)"}
    if catalogue is not None:
        listed = s in catalogue or any(k.upper().startswith(s) for k in catalogue)
        return {"verdict": PASS if listed else FAIL,
                "why": "in the measured E8 catalogue" if listed else "NOT_LISTED in the measured "
                                                                     "E8 catalogue"}
    if s in DOCUMENTED_BLOCKED:
        return {"verdict": FAIL, "why": f"{s} refused by the venue 2026-09-13 (PROP_FIRM_E8.md)"}
    if len(s) == 6 and any(c in s for c in EM):
        return {"verdict": FAIL, "why": f"{s} is an EM cross; E8 lists no EM crosses "
                                        "(PROP_FIRM_E8.md 2026-09-13)"}
    if s in DOCUMENTED_LISTED:
        return {"verdict": PASS, "why": DOCUMENTED_LISTED[s]}
    return {"verdict": UNMEASURED,
            "why": f"{s}: no measured catalogue on this host and no documented listing"}


def session_gate(timeframe: str, selector: str) -> dict[str, Any]:
    tf = (timeframe or "H1").upper()
    if tf not in E8_TIMEFRAMES:
        return {"verdict": FAIL, "why": f"{tf} spec; the E8 executor runs H1 bars only"}
    return {"verdict": PASS, "why": f"H1 {selector or 'all'} fits the E8 executor's H1 sessions"}


def other_account_symbols(book: dict[str, Any]) -> dict[str, list[str]]:
    """Symbols each OTHER account's book trades (non-zero keys), for the no-opposite rule."""
    out: dict[str, list[str]] = {}
    for acct in ("fusion", "ftmo"):
        for k, v in (book.get(acct) or {}).items():
            if isinstance(v, (int, float)) and v > 0:
                sym = GOLD_SYMBOL if str(k).startswith("gold_") else str(k).split("_")[0].upper()
                out.setdefault(sym, []).append(acct)
    return out


def opposite_gate(symbol: str, others: dict[str, list[str]]) -> dict[str, Any]:
    accts = others.get(symbol.upper())
    if accts:
        return {"verdict": FENCE, "why": f"{symbol} also traded on {sorted(set(accts))}: an order "
                                         "needs mt5desk.cross_account.opposite_block"}
    return {"verdict": PASS, "why": f"no other account's book trades {symbol}"}


# ===================================================================== the joint measurement

def _posterior(col: np.ndarray, fwd_r: list[float]) -> tuple[np.ndarray, dict[str, Any]]:
    """Shift a column's per-trade mean (its non-zero rows) toward the realised R."""
    import kelly_survival as ks
    nz = col != 0
    if not nz.any() or not fwd_r:
        return col, {"live_n": 0, "shift": 0.0}
    prior = float(col[nz].mean())
    mean, w = ks.posterior_shift(prior, fwd_r)
    out = col.copy()
    out[nz] += mean - prior
    return out, {"prior_r_per_trade": _round(prior, 4), "posterior_r_per_trade": _round(mean, 4),
                 "live_n": len(fwd_r), "live_weight": _round(w, 3)}


def _adversarial_breach(paths: np.ndarray, h: np.ndarray, limit: float) -> float:
    """P(a path has a day whose adversarial low -- every losing leg first -- hits -limit)."""
    low = np.minimum(paths * h[None, None, :], 0.0).sum(axis=2)
    return float((low <= -limit).any(axis=1).mean())


def _measure(paths: np.ndarray, h: np.ndarray, equity: float) -> dict[str, Any]:
    import kelly_survival as ks
    el, p_dead, _ = ks.ruin_counted_elog(paths, h)
    e8 = ks.e8_barrier(paths, h, equity)
    return {"elog_per_day": el, "p_death": p_dead, "p_pass": e8["p_pass"],
            "p_floor": e8["p_floor"], "p_daily_close": e8["p_daily"],
            "median_days": e8["median_days"],
            "p_daily_adversarial": _adversarial_breach(paths, h, ks.E8_DAILY_BREACH)}


def joint_metrics(gold: np.ndarray, cand: np.ndarray, crisis: np.ndarray, gold_risk: float,
                  equity: float, n_paths: int, seed: int) -> dict[str, Any]:
    """Correlation, crisis and tail co-movement, and the marginal growth table of `cand` beside
    gold_asia at `gold_risk`, on the as-estimated and edges-halved worlds."""
    import kelly_survival as ks
    from prop_challenge_allocator import draw_paths
    g, c = gold.ravel(), cand.ravel()
    rho = float(np.corrcoef(g, c)[0, 1]) if g.std() > 0 and c.std() > 0 else None
    rho_crisis: float | None = None
    if crisis.any():
        gc, cc = gold[crisis].ravel(), cand[crisis].ravel()
        if gc.std() > 0 and cc.std() > 0:
            rho_crisis = float(np.corrcoef(gc, cc)[0, 1])
    # THE TAIL is gold_asia's worst losing days (its bottom decile, and only days it lost), so a
    # quantile that lands on a no-trade zero row never counts a flat day as a tail day.
    q = float(np.quantile(g, 0.1))
    tail = (g <= min(q, 0.0)) & (g < 0)
    tail_coloss = float((c[tail] < 0).mean()) if tail.any() else None
    base_loss = float((c < 0).mean())

    r = np.stack([gold, cand], axis=2)
    mu = r.mean(axis=(0, 1))
    worlds = {"as_estimated": r, "edges_halved": r - ks.BOOK_HAIRCUT * np.maximum(mu, 0.0)}
    h0 = np.array([gold_risk, 0.0])
    base: dict[str, dict[str, Any]] = {}
    paths_of: dict[str, np.ndarray] = {}
    for name, w in worlds.items():
        paths_of[name] = draw_paths(w, n_paths, ks.E8_DAYS, seed)
        base[name] = _measure(paths_of[name], h0, equity)
    tolerance = max(ks.EPS_DEATH, max(b["p_daily_adversarial"] for b in base.values()))
    table = []
    for s in ks.E8_RISKS:
        if s <= 0:
            continue
        h = np.array([gold_risk, s])
        row: dict[str, Any] = {"risk": s}
        for name in worlds:
            m = _measure(paths_of[name], h, equity)
            row[name] = {k: _round(v) for k, v in m.items()}
            row[name]["d_elog_per_day"] = _round(m["elog_per_day"] - base[name]["elog_per_day"])
            row[name]["d_p_pass"] = _round(m["p_pass"] - base[name]["p_pass"], 4)
        row["d_elog_mix"] = _round(0.5 * (row["as_estimated"]["d_elog_per_day"]
                                          + row["edges_halved"]["d_elog_per_day"]))
        row["d_p_pass_mix"] = _round(0.5 * (row["as_estimated"]["d_p_pass"]
                                            + row["edges_halved"]["d_p_pass"]), 4)
        row["p_daily_adversarial_max"] = max(row["as_estimated"]["p_daily_adversarial"],
                                             row["edges_halved"]["p_daily_adversarial"])
        row["headroom_holds"] = row["p_daily_adversarial_max"] <= tolerance + 1e-12
        table.append(row)
    ok = [t for t in table if t["headroom_holds"]]
    chosen = max(ok, key=lambda t: t["d_elog_mix"]) if ok else None
    return {"rho": _round(rho, 4), "rho_crisis": _round(rho_crisis, 4),
            "tail_coloss": _round(tail_coloss, 4), "loss_rate": _round(base_loss, 4),
            "base": {k: {a: _round(b) for a, b in v.items()} for k, v in base.items()},
            "headroom_tolerance": _round(tolerance, 4), "table": table, "chosen": chosen}


def prior_only_reading(gold: np.ndarray, cand: np.ndarray, j: dict[str, Any], gold_risk: float,
                       equity: float, n_paths: int, seed: int) -> dict[str, Any] | None:
    """The chosen size re-read on the allocator's PRIOR columns, before any forward or live
    evidence moved them: how much of the reading the forward clocks carry. Published, never a
    gate -- the posterior is the desk's convention, and this is its sensitivity."""
    import kelly_survival as ks
    from prop_challenge_allocator import draw_paths
    ch = j.get("chosen")
    if not ch:
        return None
    r = np.stack([gold, cand], axis=2)
    paths = draw_paths(r, n_paths, ks.E8_DAYS, seed)
    b = _measure(paths, np.array([gold_risk, 0.0]), equity)
    m = _measure(paths, np.array([gold_risk, ch["risk"]]), equity)
    return {"risk": ch["risk"], "d_elog_per_day": _round(m["elog_per_day"] - b["elog_per_day"]),
            "d_p_pass": _round(m["p_pass"] - b["p_pass"], 4),
            "cand_mean_r_per_day": _round(float(cand.mean()), 4)}


def mark_mechanisms(ranked: list[dict[str, Any]], series: dict[str, np.ndarray]) -> None:
    """Readiness counts independent MECHANISMS: the first eligible row of a family is a new
    mechanism, a later one is the same mechanism again, and each row carries its correlation with
    every higher-ranked eligible row."""
    seen: dict[str, str] = {}
    for i, c in enumerate(ranked):
        fam = c["family"]
        c["mechanism_novelty"] = ("NEW_MECHANISM" if fam not in seen
                                  else f"SAME_MECHANISM_AS {seen[fam]}")
        seen.setdefault(fam, c["candidate"])
        x = series.get(c["candidate"])
        rho: dict[str, Any] = {}
        for prev in ranked[:i]:
            y = series.get(prev["candidate"])
            if x is not None and y is not None and x.std() > 0 and y.std() > 0:
                rho[prev["candidate"]] = _round(float(np.corrcoef(x.ravel(), y.ravel())[0, 1]), 4)
        c["rho_with_higher_ranked"] = rho


def correlation_gate(j: dict[str, Any]) -> dict[str, Any]:
    import kelly_survival as ks
    rho, rc = j.get("rho"), j.get("rho_crisis")
    if rho is None:
        return {"verdict": UNMEASURED, "why": "a constant series has no correlation"}
    worst = max(abs(rho), abs(rc) if rc is not None else 0.0)
    why = (f"rho {rho:+.3f}, crisis rho {rc if rc is None else f'{rc:+.3f}'}, tail co-loss "
           f"{j.get('tail_coloss')} vs base loss rate {j.get('loss_rate')}; bar "
           f"{ks.BOOK_MAX_CORR}")
    if rc is None:
        return {"verdict": UNMEASURED if abs(rho) <= ks.BOOK_MAX_CORR else FAIL,
                "why": why + " (no crisis worlds)"}
    return {"verdict": PASS if worst <= ks.BOOK_MAX_CORR else FAIL, "why": why}


def growth_gates(j: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    ch = j.get("chosen")
    if ch is None:
        return ({"verdict": FAIL, "why": "no size on the E8 grid keeps the daily-loss breach within "
                                         f"{j.get('headroom_tolerance')}"},
                {"verdict": FAIL, "why": "no admissible size"})
    head = {"verdict": PASS, "why": f"at risk {ch['risk']}: P(adversarial daily breach) "
                                    f"{ch['p_daily_adversarial_max']:.4f} <= "
                                    f"{j.get('headroom_tolerance')}"}
    d_el, d_pp = ch["d_elog_mix"], ch["d_p_pass_mix"]
    ok = d_el > 0 and d_pp >= 0
    return head, {"verdict": PASS if ok else FAIL,
                  "why": f"mixture dE[log W]/day {d_el:+.6f}, dP(pass) {d_pp:+.4f} at risk "
                         f"{ch['risk']}"}


# ===================================================================== the build

HARD_GATES = ("mechanism", "e8_symbol", "session", "correlation", "headroom", "growth", "evidence")


def _verdict_of(gates: dict[str, dict[str, Any]]) -> tuple[bool, list[str]]:
    missing = [g for g in HARD_GATES if (gates.get(g) or {}).get("verdict") != PASS]
    if (gates.get("no_opposite") or {}).get("verdict") not in (PASS, FENCE):
        missing.append("no_opposite")
    return not missing, missing


def build(*, n_paths: int = N_PATHS, seed: int = 0, now: datetime | None = None
          ) -> dict[str, Any]:
    import kelly_survival as ks
    now = now or datetime.now(UTC)
    doc: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "row": "BACKLOG 26 (Max-growth 2026-10-13): a second E8 sleeve beside "
                                  "gold_asia", "e8_rules": E8_RULES, "wiring": WIRING,
                           "gates": list(HARD_GATES) + ["no_opposite"],
                           "authority": "REPORT ONLY: sizes nothing, arms nothing, writes no "
                                        "CERT_BOOK block"}
    book = _read_json(CERT_BOOK) or {}
    gold_risk = _num((book.get("e8") or {}).get(GOLD))
    doc["book"] = {"e8": book.get("e8"), "source": CERT_BOOK.name if book else "UNMEASURED"}
    if not gold_risk or gold_risk <= 0:
        doc["book"]["gold_risk_note"] = (f"no positive e8 gold_asia in {CERT_BOOK.name}; measured "
                                         f"at the 2026-10-20 value {GOLD_RISK_FALLBACK}")
        gold_risk = GOLD_RISK_FALLBACK
    doc["book"]["gold_risk"] = gold_risk
    equity, eq_src = ks.e8_equity()
    doc["e8_equity"] = {"usd": equity or ks.E8_INITIAL,
                        "source": eq_src if equity else f"{eq_src}; the initial balance is used"}
    equity = equity or ks.E8_INITIAL

    clocks, lanes = forward_clocks()
    certs = certificate_gates()
    enrolled, enrol_src = enrolled_certificates()
    near, near_src = near_certified()
    catalogue, cat_src = e8_catalogue()
    others = other_account_symbols(book)
    try:
        worlds_name = str(Path(ks.WORLDS).relative_to(BASE))
    except ValueError:
        worlds_name = str(ks.WORLDS)
    doc["inputs"] = {"worlds": worlds_name, "forward_lanes": lanes,
                     "certificates": enrol_src, "survivors": f"{len(certs)} costed cells",
                     "near_certified": near_src, "e8_catalogue": cat_src,
                     "other_accounts": others}

    try:
        z = np.load(ks.WORLDS, allow_pickle=True)
        names = [str(x) for x in z["names"]]
        r_all = np.asarray(z["r"], dtype=float)
        crisis = np.asarray(z["crisis"], dtype=bool) if "crisis" in z.files else \
            np.zeros(r_all.shape[0], dtype=bool)
    except (OSError, ValueError, KeyError) as exc:
        names, r_all, crisis = [], np.zeros((0, 0, 0)), np.zeros(0, dtype=bool)
        doc["inputs"]["worlds_status"] = f"UNMEASURED: worlds unreadable ({type(exc).__name__})"

    candidates: list[dict[str, Any]] = []
    series: dict[str, np.ndarray] = {}
    priced_cells: set[tuple[str, str, str]] = set()
    if GOLD in names:
        gi = names.index(GOLD)
        gold_live: list[float] = []
        try:
            with ks.LEDGER.open(encoding="utf-8") as fh:
                deals = [json.loads(t) for t in (ln.strip() for ln in fh) if t.startswith("{")]
            gold_live = list(ks.live_evidence(deals).get("asia", {}).get("r", []))
            gsrc = f"live ledger ({len(gold_live)} gold_asia deals)"
        except (OSError, ValueError, ImportError):
            gsrc = "live ledger not on this host"
        if not gold_live:
            gc = clocks.get(GOLD_CLOCK) or {}
            if gc.get("n") and gc.get("exp_r") is not None:
                gold_live = [float(gc["exp_r"])] * int(gc["n"])
                gsrc += f"; forward clock {GOLD_CLOCK} n={gc['n']} exp_r {gc['exp_r']:+.3f}"
        gold_col, gpost = _posterior(r_all[:, :, gi], gold_live)
        doc["gold_asia"] = {"posterior": gpost, "evidence_source": gsrc,
                            "mechanism": GOLD_FAMILY, "symbol": GOLD_SYMBOL}
        for j, col in enumerate(names):
            if col == GOLD:
                continue
            ident = column_identity(col)
            sym, fam, sel, tf = (ident["symbol"], ident["family"], ident["selector"],
                                 ident["timeframe"])
            priced_cells.add((sym, fam, sel))
            fkey, fwd = (col, clocks.get(col)) if col in clocks else \
                best_clock(clocks, sym, fam, sel, tf)
            cert = certs.get(f"{sym}.{fam}.{sel}")
            if cert and cert.get("timeframe"):
                tf = cert["timeframe"] if not col.startswith("xau_") else tf
            fwd_r = [float(fwd["exp_r"])] * int(fwd["n"]) if fwd and fwd.get("exp_r") is not None \
                and fwd.get("n") else []
            cand_col, cpost = _posterior(r_all[:, :, j], fwd_r)
            jm = joint_metrics(gold_col, cand_col, crisis, gold_risk, equity, n_paths, seed)
            jm["prior_only"] = prior_only_reading(r_all[:, :, gi], r_all[:, :, j], jm,
                                                  gold_risk, equity, n_paths, seed)
            series[col] = cand_col
            head, grow = growth_gates(jm)
            gates = {"mechanism": mechanism_gate(fam), "e8_symbol": symbol_gate(sym, catalogue),
                     "session": session_gate(tf, sel), "no_opposite": opposite_gate(sym, others),
                     "correlation": correlation_gate(jm), "headroom": head, "growth": grow,
                     "evidence": evidence_gate(fwd and {**fwd, "key": fkey}, cert)}
            eligible, missing = _verdict_of(gates)
            ch = jm.get("chosen") or {}
            candidates.append({
                "candidate": col, "tier": "JOINT", "symbol": sym, "family": fam,
                "selector": sel, "timeframe": tf, "eligible": eligible, "missing_gates": missing,
                "n_gates_pass": sum(1 for g in HARD_GATES if gates[g].get("verdict") == PASS),
                "score": {"d_elog_per_day_mix": ch.get("d_elog_mix"),
                          "d_p_pass_mix": ch.get("d_p_pass_mix"), "risk": ch.get("risk"),
                          "rho": jm["rho"], "rho_crisis": jm["rho_crisis"],
                          "tail_coloss": jm["tail_coloss"],
                          "evidence_depth": gates["evidence"].get("depth")},
                "posterior": cpost, "prior_only": jm["prior_only"], "gates": gates,
                "joint": {k: v for k, v in jm.items() if k not in ("table", "prior_only")},
                "size_table": jm["table"]})
            if "base_gold_alone" not in doc:
                doc["base_gold_alone"] = jm["base"]
    else:
        doc["inputs"]["worlds_status"] = doc["inputs"].get(
            "worlds_status", f"UNMEASURED: worlds carry no {GOLD} column")

    candidates.sort(key=lambda c: (not c["eligible"], -c["n_gates_pass"],
                                   -(c["score"]["d_elog_per_day_mix"] or -1e9)))

    # ---- the unpriced tiers: every measurable gate, and the joint gates UNMEASURED by name.
    unpriced: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add(tier: str, sym: str, fam: str, sel: str, key: str, tf: str) -> None:
        cell = (sym, fam, sel)
        if not sym or not fam or cell in priced_cells:
            return
        fkey, fwd = (key, clocks.get(key)) if key in clocks else best_clock(clocks, sym, fam, sel,
                                                                           tf)
        row = unpriced.get(cell)
        if row is not None:
            row["n_variants"] += 1
            if tier == "CERTIFIED" and row["tier"] != "CERTIFIED":
                row["tier"] = "CERTIFIED"
            return
        cert = certs.get(f"{sym}.{fam}.{sel}")
        gates = {"mechanism": mechanism_gate(fam), "e8_symbol": symbol_gate(sym, catalogue),
                 "session": session_gate(tf, sel), "no_opposite": opposite_gate(sym, others),
                 "evidence": evidence_gate(fwd and {**fwd, "key": fkey}, cert)}
        for g in ("correlation", "headroom", "growth"):
            gates[g] = {"verdict": UNMEASURED,
                        "why": "joint_series: not a column of worlds.npz, so nothing measures it "
                               "on gold_asia's rows"}
        _, missing = _verdict_of(gates)
        unpriced[cell] = {"candidate": f"{sym}.{fam}.{sel}", "tier": tier, "symbol": sym,
                          "family": fam, "selector": sel, "timeframe": tf, "eligible": False,
                          "missing_gates": ["joint_series"] + missing, "n_variants": 1,
                          "n_static_gates_pass": sum(1 for g in ("mechanism", "e8_symbol",
                                                                 "session", "evidence")
                                                     if gates[g]["verdict"] == PASS),
                          "forward_t": (fwd or {}).get("forward_t"), "gates": gates}

    for c in enrolled:
        key = str(c.get("key") or "")
        add("CERTIFIED", str(c.get("symbol") or "").upper(), str(c.get("family") or ""),
            str(c.get("selector") or ""), key, _key_timeframe(key))
    for c in near:
        add("NEAR", c["symbol"], c["family"], c["selector"], c["key"], _key_timeframe(c["key"]))
    for k, v in clocks.items():
        if (v.get("n") or 0) > 0 and str(v.get("status") or "") not in ("KILL", "DEAD", "RETIRED",
                                                                         "REJECTED"):
            sym, fam, sel = _key_identity(k)
            add("FORWARD", sym, fam, sel, k, _key_timeframe(k))
    up = sorted(unpriced.values(), key=lambda c: (-c["n_static_gates_pass"],
                                                  -(c["forward_t"] or -1e9)))

    eligible = [c for c in candidates if c["eligible"]]
    mark_mechanisms(eligible, series)
    doc["n_candidates"] = len(candidates) + len(up)
    doc["n_joint"] = len(candidates)
    doc["n_unpriced"] = len(up)
    doc["n_eligible"] = len(eligible)
    doc["n_independent_mechanisms_eligible"] = len({c["family"] for c in eligible})
    doc["candidates"] = candidates
    doc["unpriced_candidates"] = up[:MAX_UNPRICED_ROWS]
    doc["unpriced_ready_but_for_joint"] = sum(1 for c in up if c["n_static_gates_pass"] == 4)
    fail_counts: dict[str, int] = {}
    for c in candidates:
        for g in c["missing_gates"]:
            fail_counts[g] = fail_counts.get(g, 0) + 1
    doc["joint_gate_failures"] = fail_counts

    def brief(c: dict[str, Any]) -> dict[str, Any]:
        return {"candidate": c["candidate"], "family": c["family"], "symbol": c["symbol"],
                "eligible": c["eligible"], "missing_gates": c["missing_gates"],
                **c["score"], "prior_only": c.get("prior_only"),
                "mechanism_novelty": c.get("mechanism_novelty"),
                "rho_with_higher_ranked": c.get("rho_with_higher_ranked"),
                "why": {g: c["gates"][g]["why"] for g in (*HARD_GATES, "no_opposite")}}

    if not names or GOLD not in names:
        doc["status"] = "UNMEASURED"
        doc["verdict"] = doc["inputs"].get("worlds_status")
        doc["top"] = []
    elif eligible:
        doc["status"] = "OK"
        doc["verdict"] = (f"{len(eligible)} eligible; best {eligible[0]['candidate']} "
                          f"(dE[log W]/day {eligible[0]['score']['d_elog_per_day_mix']:+.6f}, "
                          f"dP(pass) {eligible[0]['score']['d_p_pass_mix']:+.4f})")
        rest = [c for c in candidates if not c["eligible"]]
        doc["top"] = [brief(c) for c in (eligible + rest)[:TOP_N]]
    else:
        doc["status"] = "NONE_ELIGIBLE"
        closest = candidates[:TOP_N]
        doc["verdict"] = "NONE_ELIGIBLE: " + "; ".join(
            f"{c['candidate']} misses {','.join(c['missing_gates'])}" for c in closest)
        doc["top"] = [brief(c) for c in closest]
    doc["measured"] = doc["status"] != "UNMEASURED"
    return doc


def write(doc: dict[str, Any], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--paths", type=int, default=N_PATHS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(n_paths=a.paths, seed=a.seed)
    try:
        write(doc, a.out)
    except OSError as exc:
        print(f"e8_second_sleeve: could not write {a.out}: {exc}")
        return 1
    print(f"e8_second_sleeve: {doc['status']} -- {doc.get('verdict')}")
    for c in doc.get("top") or []:
        print(f"  {c['candidate']}: dElog/day {c.get('d_elog_per_day_mix')} dP(pass) "
              f"{c.get('d_p_pass_mix')} rho {c.get('rho')} crisis {c.get('rho_crisis')} "
              f"missing {c['missing_gates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
