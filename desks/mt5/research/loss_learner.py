"""THE LOSS LEARNER: every live sleeve's losses and missed trades, turned into variant cells that
must beat their parent forward before they may replace it.

    live ledgers (Fusion live_ledger, prop ledger: E8 / FTMO)
      -> per trade: exit kind, excursion before the exit, what price did AFTER the exit
      -> loss MODES per sleeve (stop then target, give-back, ran past target, time-exit
         continuation), each with its support count
      -> one-step VARIANTS of the sleeve's certified identity, stepped on the parameter the
         mode names (target / stop / hold), never on a parameter that names the cell
      -> donated as EXACT_RECIPE through `proposer_common.donate` -> compiler -> docket
         -> the ordinary gauntlet (Judge, OOS, DSR at the charged trial count, Tier S)
      -> a certified variant gets a forward clock like every certificate
      -> REPLACEMENT: the variant's forward clock against its parent's forward clock, paired by
         day over the SAME window, at an always-valid bound whose alpha is split across EVERY
         variant ever minted from that parent
      -> `--act` (daily, after decay): a REPLACE verdict retires the parent sleeves.json row,
         but only once the variant row is LIVE with capital, so risk is moved, never dropped

PRINCIPAL 2026-11-03 (zuck): "24/7 self improving from losses ... track losses missed profit
opportunities etc from current sleeves n tweak them n test them as cells both fr prop firms n
fusion ... after promotion replace them w the more profitable same strats ones".

OVERFITTING TO RECENT LOSSES IS THE FAILURE THIS ORGAN EXISTS NEXT TO, and three things fence it:

  1. THE DIAGNOSIS ONLY CHOOSES WHICH NEIGHBOUR TO TEST. It never scores one. The losses that
     suggested "widen the target" are inside the history the gauntlet judges the variant on, but
     the gauntlet judges the variant on the WHOLE history, out of sample, at the desk's charged
     trial count -- a tweak that only fixes last month's losers fails there like any other.
  2. EVERY VARIANT IS A TRIAL, TWICE. Donated cells enter the docket, so the gauntlet's census
     charges each one in the deflated-Sharpe trial count. And the lineage ledger
     (`data/loss_learning/lineage.jsonl`, append-only) counts every variant ever minted from a
     parent: the replacement test's alpha is SEQ_ALPHA divided by that lifetime count, so the
     tenth tweak of one sleeve must beat it by more than the first did.
  3. REPLACEMENT IS DECIDED ON FORWARD EVIDENCE ONLY, stamped after the variant was frozen, so
     the episodes the variant was dug from can never be its evidence. Both clocks are the
     forward engine's own simulation on the same bars and cost model, paired by day.

PROMOTION IS UNTOUCHED. A certified variant matures and is promoted by `promoter.py` exactly as
any certificate (AUTOMATIC PROMOTION, 2026-09-04); the allocator funds it by dE[log W]. This organ
adds only the REPLACEMENT: retiring the parent once the variant has proved forward superiority.
A gateway window parent (the gold windows on Fusion, E8 and FTMO) is not a sleeves.json row and
its sizing lives in CERT_BOOK_LIVE.json, so a REPLACE there is written to
`data/loss_learning/BOOK_ROLLOUTS.json` as a request for that book's allocator; nothing
here edits a sizing file.

MISSED TRADES are TRACKED here (a live book that did not trade a day its sibling book traded, per
sleeve) and never turned into variants: a missed fill is a wiring or veto question, which is
`missed_trade_archaeologist`'s OPERATIONAL class, not a parameter question.

UNMEASURED IS A VERDICT (L1.28a). A book whose ledger is absent on this host, a trade with no
stop, a sleeve whose certified identity cannot be resolved: each is named in the report with its
reason, never read as "no losses".

    python desks/mt5/research/loss_learner.py --once [--dry-run]     # hourly leg
    python desks/mt5/research/loss_learner.py --act                  # daily step, after decay
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "loss_learner"
DATA = _DESK / "data"
OUT_DIR = DATA / "loss_learning"
LINEAGE = OUT_DIR / "lineage.jsonl"
ACTIONS = OUT_DIR / "replacements.jsonl"
#: Per-book rollout requests: one row per (REPLACE verdict, book this organ cannot write).
WINDOW_REQUESTS = OUT_DIR / "BOOK_ROLLOUTS.json"
#: Who sizes each book, and the firm rails the rollout is sized inside.
BOOK_CONSUMERS = {
    "fusion": "Fusion allocator (pf_allocator / CERT_BOOK_LIVE.json fusion block)",
    "e8": "E8 book owners (prop/e8_book, CERT_BOOK_LIVE.json e8 block)",
    "ftmo": "FTMO allocator (research/prop_challenge_allocator.py, CERT_BOOK_LIVE.json ftmo block)",
}
BOOK_RAILS = {
    "fusion": "max E[log W] within survival; heat floor 20%",
    "e8": ("E8 Pro: 2.5% daily loss incl. floating, 2%/day profit cap, floor $90k, no "
           "cross-account opposite trades, no Scandi pairs"),
    "ftmo": "FTMO 2-Step: 5% daily loss, 10% max loss; never on a symbol E8 trades",
}
REPORT = _DESK / "reports" / "LOSS_LEARNER.json"
SLEEVES = DATA / "sleeves.json"
REGISTRY = DATA / "sleeve_registry.json"
CERT_BOOK = DATA / "CERT_BOOK_LIVE.json"
FUSION_LEDGER = DATA / "live_ledger.jsonl"
PROP_LEDGER = DATA / "live_ledger_prop.jsonl"

#: Trailing window the loss modes are measured over.
TRAIL_DAYS = 60
#: Episodes a mode needs, and the share of the sleeve's diagnosed trades, before it is acted on.
#: Below either the mode is reported with its count and nothing is minted from it.
MIN_EPISODES = 3
MIN_MODE_SHARE = 0.15
#: New variants per parent per 24h. A bound on docket spam, not on research: the lineage keeps
#: every variant and the next day mints the next ones.
MAX_PER_PARENT_PER_DAY = 3
#: An excursion is measured in R (units of the trade's own stop distance).
GIVEBACK_MFE_R = 1.0
CONTINUATION_R = 1.0
#: Price within this many R of a level counts as exiting AT it.
LEVEL_TOL_R = 0.15
#: Bars read after entry when the family names no hold.
DEFAULT_HOLD_BARS = 12
#: The forward replacement bar mirrors promotion's (forward_verdict): 20 paired days over 14.
MIN_PAIRED_DAYS = 20
MIN_SPAN_DAYS = 14
#: Oldest report `act` will take verdicts from (the hourly leg's cadence, with a day of slack).
REPORT_MAX_AGE_H = 26
#: Fallback risk fraction for pricing log-growth when no book names the parent's size.
DEFAULT_FRAC = 0.01

#: Which parameters play which role. A name is matched on its head (before any `.i` suffix).
ROLE_NAMES: dict[str, tuple[str, ...]] = {
    "target": ("rr", "target_atr", "tp_atr", "target_r", "take_profit", "tp_mult", "target"),
    "stop": ("stop_atr", "sl_atr", "stop_mult", "sl_mult", "stop_r", "stop"),
    "hold": ("ttl_bars", "hold_bars", "max_hold", "horizon", "hold_days"),
}
#: What each loss mode asks of the parameters, as (role, step up?).
MODE_ACTIONS: dict[str, tuple[tuple[str, bool], ...]] = {
    "STOP_THEN_TARGET": (("stop", True),),
    "GIVEBACK_TO_STOP": (("target", False),),
    "GIVEBACK_ON_TIME": (("hold", False),),
    "RAN_PAST_TARGET": (("target", True),),
    "TIME_EXIT_CONTINUATION": (("hold", True),),
}
GOLD_LABELS_FALLBACK = ("asia", "london_am", "afternoon")


# ------------------------------------------------------------------------------------------
# Small readers
# ------------------------------------------------------------------------------------------

def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return default


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        t = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _gold_labels() -> tuple[str, ...]:
    try:
        from mt5desk.decision_core import GOLD_WINDOWS
        return tuple(str(w[0]) for w in GOLD_WINDOWS)
    except Exception:
        return GOLD_LABELS_FALLBACK


# ------------------------------------------------------------------------------------------
# Which sleeves are live, on which books, and what certified identity each one is
# ------------------------------------------------------------------------------------------

def _ledger_path(p: Path) -> Path:
    try:
        from libs.ops.live_ledger_view import ledger_path
        return Path(ledger_path(p))
    except Exception:
        return p


def ledger_rows(now: datetime, fusion: Path | None = None, prop: Path | None = None
                ) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """(rows, book_state). Every closed trade in the trailing window, tagged with its book.

    A book whose ledger file is absent is UNMEASURED with the path named; E8 has no per-trade
    writer on any branch as of 2026-10-28 (ftmo_follower's PROP_LEDGER note), so it is expected
    to read UNMEASURED until one exists, and says so."""
    cutoff = now - timedelta(days=TRAIL_DAYS)
    state: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    fpath = _ledger_path(fusion or FUSION_LEDGER)
    if Path(fpath).exists():
        rows = _jsonl(Path(fpath))
        state["fusion"] = f"MEASURED: {len(rows)} rows in {Path(fpath).name}"
        for r in rows:
            out.append({**r, "_book": "fusion"})
    else:
        state["fusion"] = f"UNMEASURED: no ledger at {fpath}"
    ppath = prop or PROP_LEDGER
    if ppath.exists():
        rows = _jsonl(ppath)
        books = Counter(str(r.get("book") or "prop") for r in rows)
        for b in ("e8", "ftmo"):
            state[b] = (f"MEASURED: {books[b]} rows in {ppath.name}" if books[b]
                        else f"UNMEASURED: {ppath.name} holds no book={b} rows")
        for r in rows:
            out.append({**r, "_book": str(r.get("book") or "prop")})
    else:
        state["e8"] = state["ftmo"] = f"UNMEASURED: no prop ledger at {ppath}"
    kept = []
    for r in out:
        t = _ts(r.get("exit_time")) or _ts(r.get("time"))
        if t is None or t < cutoff:
            continue
        if r.get("r_unreconstructible") is True:
            continue
        kept.append({**r, "_t": t})
    return kept, state


def live_sleeves(sleeves_doc: Any, cert_book: Any,
                 minlot: tuple[Any, float | None] | None = None) -> dict[str, dict[str, Any]]:
    """name -> {books, frac, row}. Live NOW = a LIVE sleeves.json row (Fusion), a positive
    cert-book key on any book, or a sleeve in the Fusion min-lot book's scope (`minlot` =
    (names, target risk), from `minlot_scope()`). A retired sleeve's
    old losses are not this organ's input: its parent is gone and a variant could replace
    nothing."""
    out: dict[str, dict[str, Any]] = {}

    def _add(name: str, book: str, frac: float | None = None, row: dict | None = None) -> None:
        e = out.setdefault(name, {"books": set(), "frac": 0.0, "row": None})
        e["books"].add(book)
        if frac is not None and frac > e["frac"]:
            e["frac"] = frac
        if row is not None:
            e["row"] = row

    for s in (sleeves_doc or {}).get("sleeves", []) if isinstance(sleeves_doc, dict) else []:
        if isinstance(s, dict) and str(s.get("status") or "").upper() == "LIVE" and s.get("name"):
            _add(str(s["name"]), "fusion", _num(s.get("risk_frac")), s)
    if isinstance(cert_book, dict) and cert_book.get("enabled") is not False:
        for book in ("fusion", "e8", "ftmo"):
            blk = cert_book.get(book)
            for k, v in (blk.items() if isinstance(blk, dict) else []):
                f = _num(v)
                if f and f > 0:
                    _add(str(k), book, f)
    if minlot:
        names, tr = minlot
        for k in names or ():
            _add(str(k), "fusion", tr)
    return out


def minlot_scope() -> tuple[frozenset[str], float | None]:
    """The Fusion min-lot book's scope, READ FROM THE CODE (decision_core's constant set and its
    fixed target risk), never from the switch file: the core is the switch's only reader
    (test_fusion_minlot_book.test_no_organ_writes_the_switch), and the file can only NARROW the
    code's set. A sleeve in scope but switched off sends no trades, so it yields no episodes and
    no variants; the superset costs nothing. Unimportable core -> empty scope, said in the report.
    """
    try:
        from mt5desk import decision_core as dcore
    except Exception:  # noqa: BLE001 -- an unreadable core narrows the input, never raises
        return frozenset(), None
    return (frozenset(getattr(dcore, "MINLOT_OVERRIDE_SLEEVES", frozenset())),
            _num(getattr(dcore, "MINLOT_OVERRIDE_TARGET_FRAC", None)))


def _registry(doc: Any) -> dict[str, dict[str, Any]]:
    s = doc.get("sleeves") if isinstance(doc, dict) else None
    return s if isinstance(s, dict) else {}


def resolve_identity(name: str, row: dict | None, registry: dict[str, dict[str, Any]],
                     pins: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str]:
    """(identity, how) -- the certified (symbol, family, selector, params) a live sleeve runs.

    In order: a gateway gold window maps to its clock `XAUUSD.<label>`; a cert-book pin that names
    `clock X`; the roster row's `certificate`; the registry under the name itself; the roster
    row's own family and params. None with the reason when nothing resolves."""
    candidates: list[tuple[str, str]] = []
    for lab in _gold_labels():
        if name == f"gold_{lab}":
            candidates.append((f"XAUUSD.{lab}", "gateway gold window"))
    pin = (pins or {}).get(name)
    if isinstance(pin, str):
        m = re.search(r"clock\s+([^\s,;()]+)", pin)
        if m:
            candidates.append((m.group(1), "cert-book pin"))
    if row and isinstance(row.get("certificate"), str):
        candidates.append((row["certificate"], "roster certificate"))
    candidates.append((name, "registry by name"))
    for key, how in candidates:
        ident = (registry.get(key) or {}).get("identity")
        if isinstance(ident, dict) and ident.get("family") and isinstance(ident.get("params"),
                                                                            dict):
            return ({"clock": key, "symbol": str(ident.get("symbol") or ""),
                     "family": str(ident["family"]),
                     "selector": str(ident.get("selector") or ""),
                     "params": dict(ident["params"]),
                     "direction": str(ident.get("direction") or "LONG")}, how)
    if row and row.get("family") and isinstance(row.get("params"), dict) and row.get("symbol"):
        return ({"clock": str(row.get("certificate") or name), "symbol": str(row["symbol"]),
                 "family": str(row["family"]), "selector": str(row.get("selector") or
                                                               row.get("window") or ""),
                 "params": dict(row["params"]), "direction": str(row.get("side") or "LONG")},
                "roster row")
    return None, ("UNRESOLVED: no registry identity under " +
                  ", ".join(k for k, _ in candidates) + " and the roster row carries no params")


def is_window(name: str) -> bool:
    return any(name == f"gold_{lab}" for lab in _gold_labels())


# ------------------------------------------------------------------------------------------
# Per-trade diagnosis
# ------------------------------------------------------------------------------------------

def _direction(r: dict[str, Any]) -> int | None:
    e, sl, tp = _num(r.get("entry_price")), _num(r.get("sl")), _num(r.get("tp"))
    if e and tp:
        return 1 if tp > e else -1
    if e and sl:
        return 1 if sl < e else -1
    es = r.get("entry_side")
    return 1 if es == 0 else -1 if es == 1 else None


def bar_offset_hours(trades: list[dict[str, Any]], bars: Any) -> int:
    """The clock offset (hours) that puts the most entry prices inside their entry bar's range.

    Ledger times and bar labels may sit on different clocks (broker vs UTC); a diagnosis read
    off the wrong bar is a diagnosis of a different trade. Measured, not assumed: 0 wins ties."""
    best, best_hits = 0, -1
    for off in (0, 1, -1, 2, -2, 3, -3, 7, -7):
        hits = 0
        for t in trades:
            et, ep = _ts(t.get("entry_time")), _num(t.get("entry_price"))
            if et is None or ep is None:
                continue
            key = (et + timedelta(hours=off)).replace(minute=0, second=0, microsecond=0)
            try:
                b = bars.loc[key]
            except (KeyError, TypeError):
                continue
            try:
                lo, hi = float(b["low"]), float(b["high"])
            except (TypeError, ValueError, KeyError):
                continue
            hits += int(lo - 1e-9 <= ep <= hi + 1e-9)
        if hits > best_hits:
            best, best_hits = off, hits
    return best


def diagnose(t: dict[str, Any], bars: Any, hold_bars: int, offset_h: int = 0
             ) -> dict[str, Any]:
    """One closed trade read against the bars around it. Units are R (the trade's stop distance).

    Returns {mode, exit_kind, r, mfe_r, after_fav_r, tp_r} or {mode: None, why} when the trade
    cannot be read (no stop, no bars, no entry)."""
    e, sl, tp = _num(t.get("entry_price")), _num(t.get("sl")), _num(t.get("tp"))
    xp = _num(t.get("fill_price"))
    d = _direction(t)
    et = _ts(t.get("entry_time"))
    xt = _ts(t.get("exit_time")) or _ts(t.get("time"))
    if not (e and sl and xp and d and et and xt):
        return {"mode": None, "why": "UNMEASURED: entry, stop, exit or times missing"}
    risk = abs(e - sl)
    if risk <= 0:
        return {"mode": None, "why": "UNMEASURED: zero stop distance"}
    r = d * (xp - e) / risk
    tp_r = abs(tp - e) / risk if tp else None
    shift = timedelta(hours=offset_h)
    t0 = (et + shift).replace(minute=0, second=0, microsecond=0)
    t1 = xt + shift
    t_end = t0 + timedelta(hours=max(hold_bars, 1) + 1)
    try:
        before = bars.loc[(bars.index >= t0) & (bars.index <= t1)]
        after = bars.loc[(bars.index > t1) & (bars.index <= max(t_end, t1 + timedelta(hours=6)))]
    except Exception as exc:
        return {"mode": None, "why": f"UNMEASURED: bars unreadable ({type(exc).__name__})"}
    if before.empty:
        return {"mode": None, "why": "UNMEASURED: no bars inside the trade"}

    def _fav(frame: Any) -> float | None:
        if frame.empty:
            return None
        ext = float(frame["high"].max()) if d > 0 else float(frame["low"].min())
        return d * (ext - e) / risk

    mfe = _fav(before)
    after_fav = _fav(after)
    reason = str(t.get("exit_reason") or "")
    if reason in ("stop", "stop_out"):
        kind = "stop"
    elif reason == "target":
        kind = "target"
    elif abs(xp - sl) / risk <= LEVEL_TOL_R:
        kind = "stop"
    elif tp and abs(xp - tp) / risk <= LEVEL_TOL_R:
        kind = "target"
    else:
        kind = "time"
    mode: str | None = None
    if kind == "stop" and tp_r is not None and after_fav is not None and after_fav >= tp_r:
        mode = "STOP_THEN_TARGET"
    elif kind == "stop" and mfe is not None and mfe >= GIVEBACK_MFE_R:
        mode = "GIVEBACK_TO_STOP"
    elif kind == "target" and tp_r is not None and after_fav is not None \
            and after_fav >= tp_r + CONTINUATION_R:
        mode = "RAN_PAST_TARGET"
    elif kind == "time" and after_fav is not None and after_fav >= r + CONTINUATION_R:
        mode = "TIME_EXIT_CONTINUATION"
    elif kind == "time" and r <= 0 and mfe is not None and mfe >= GIVEBACK_MFE_R * 0.5:
        mode = "GIVEBACK_ON_TIME"
    return {"mode": mode, "exit_kind": kind, "r": round(r, 4),
            "mfe_r": None if mfe is None else round(mfe, 4),
            "after_fav_r": None if after_fav is None else round(after_fav, 4),
            "tp_r": None if tp_r is None else round(tp_r, 4)}


#: Which book's row is read when several copied one signal: the Fusion ledger carries the
#: richest per-trade fields (stop, target, exit reason), so it is preferred where it exists.
BOOK_ORDER = ("fusion", "ftmo", "e8")


def episodes_of(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ONE EPISODE PER DECISION, NOT PER BOOK. Two books copying one signal are one episode; two
    separate trades the same day are two.

    The key is the SIGNAL HOUR and the direction -- the copies share the entry bar -- not the day.
    Keying on the day collapsed a sleeve's second same-direction trade of the day and under-counted
    its mode support."""
    uniq: dict[str, dict[str, Any]] = {}
    for t in sorted(trades, key=lambda r: (BOOK_ORDER.index(str(r.get("_book")))
                                           if str(r.get("_book")) in BOOK_ORDER
                                           else len(BOOK_ORDER), str(r.get("_book")))):
        et = _ts(t.get("entry_time")) or t["_t"]
        uniq.setdefault(f"{et.replace(minute=0, second=0, microsecond=0)}:{_direction(t)}", t)
    return sorted(uniq.values(), key=lambda r: r["_t"])


def active_modes(diags: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Every mode with its support; `active` when it clears both MIN_EPISODES and the share."""
    read = [x for x in diags if "exit_kind" in x]
    c = Counter(x["mode"] for x in read if x.get("mode"))
    n = len(read)
    out: dict[str, dict[str, Any]] = {}
    for mode, k in sorted(c.items()):
        share = k / n if n else 0.0
        out[mode] = {"episodes": k, "of": n, "share": round(share, 3),
                     "active": bool(k >= MIN_EPISODES and share >= MIN_MODE_SHARE)}
    return out


# ------------------------------------------------------------------------------------------
# Variants
# ------------------------------------------------------------------------------------------

def role_params(params: dict[str, Any], role: str) -> list[str]:
    names = ROLE_NAMES.get(role, ())
    return [k for k, v in params.items()
            if k in names and isinstance(v, (int, float)) and not isinstance(v, bool)]


def step_value(value: float, grid: list[float] | None, up: bool) -> float | None:
    """One step on the desk's enumerated grid when it has one, else +25% / -20%; integers stay
    integers and move by at least one; a positive parameter never steps to zero or below."""
    if grid:
        above = sorted(g for g in grid if g > value + 1e-12)
        below = sorted((g for g in grid if g < value - 1e-12), reverse=True)
        pick = above[0] if up and above else below[0] if (not up and below) else None
        if pick is not None:
            return pick
    if isinstance(value, int) and not isinstance(value, bool):
        nxt = max(value + 1, round(value * 1.25)) if up else min(value - 1, round(value * 0.8))
        return float(nxt) if nxt >= 1 else None
    nxt = value * 1.25 if up else value * 0.8
    nxt = round(nxt * 4) / 4 if abs(value) >= 1 else round(nxt, 3)
    if value > 0 and nxt <= 0:
        return None
    return nxt if abs(nxt - value) > 1e-12 else None


def make_variants(ident: dict[str, Any], modes: dict[str, dict[str, Any]],
                  existing: set[str], grid: dict[str, list[float]] | None = None
                  ) -> tuple[list[dict[str, Any]], list[str]]:
    """(variants, unmapped). One-step variants for every ACTIVE mode, on the parameters its role
    names. A variant whose node already exists (graph or lineage) is history and not re-minted.
    `unmapped` names an active mode the family has no parameter for."""
    from libs.research.hypothesis_graph import node_id

    params = dict(ident["params"])
    out: list[dict[str, Any]] = []
    unmapped: list[str] = []
    taken: set[str] = set()
    for mode, sup in sorted(modes.items(), key=lambda kv: -kv[1]["episodes"]):
        if not sup.get("active"):
            continue
        hit = False
        for role, up in MODE_ACTIONS.get(mode, ()):
            for p in role_params(params, role):
                v = params[p]
                nxt = step_value(v, (grid or {}).get(p), up)
                if nxt is None:
                    continue
                new = dict(params)
                new[p] = int(nxt) if isinstance(v, int) and float(nxt).is_integer() else nxt
                nid = node_id(ident["symbol"], ident["family"], new)
                hit = True
                if nid in existing or nid in taken:
                    continue
                taken.add(nid)
                out.append({"id": nid, "symbol": ident["symbol"], "family": ident["family"],
                            "selector": ident.get("selector") or "", "params": new,
                            "operator": f"loss_{p}_{'up' if up else 'down'}", "mode": mode,
                            "support": sup})
        if not hit:
            unmapped.append(f"{mode}: {ident['family']} has no "
                            f"{'/'.join(r for r, _ in MODE_ACTIONS.get(mode, ()))} parameter")
    return out, unmapped


def lineage_rows(path: Path | None = None) -> list[dict[str, Any]]:
    return _jsonl(path or LINEAGE)


def lifetime_trials(parent: str, rows: list[dict[str, Any]]) -> int:
    """Every variant ever minted from `parent`, whatever became of it."""
    return sum(1 for r in rows if r.get("parent") == parent)


def minted_today(parent: str, rows: list[dict[str, Any]], now: datetime) -> int:
    since = now - timedelta(hours=24)
    return sum(1 for r in rows if r.get("parent") == parent and (_ts(r.get("at")) or since) > since)


def _candidate(v: dict[str, Any], parent: dict[str, Any], sleeve: str, trials: int
               ) -> dict[str, Any]:
    from research import proposer_common as pc

    mech = (f"{v['family']} on {v['symbol']} ({v.get('selector') or 'all sessions'}): "
            f"{v['operator']} variant of live sleeve {sleeve} (clock {parent['clock']}), minted "
            f"because {v['support']['episodes']} of its last {v['support']['of']} diagnosed "
            f"trades showed {v['mode']}")
    c = pc.candidate(SOURCE, v["symbol"], v["family"], v["params"], mech,
                     f"Loss-learn {v['symbol']}.{v['family']}: {v['operator']} from "
                     f"{parent['clock']}",
                     {"parent": parent["clock"], "parent_sleeve": sleeve,
                      "operator": v["operator"], "mode": v["mode"], "support": v["support"],
                      "lineage_trials": trials,
                      "overfit_guard": ("diagnosis chooses the neighbour only; the gauntlet judges "
                                        "the whole history at the charged trial count; replacement "
                                        "needs forward evidence after freeze at alpha / lineage "
                                        "trials")})
    c["evidence"]["screen"] = ("not screened here: a diagnosed one-step neighbour of a live "
                               "certificate; the gauntlet screens and judges it")
    c["parent"] = parent["clock"]
    c["operator"] = v["operator"]
    if v.get("selector"):
        c["selector"] = v["selector"]
    return c


# ------------------------------------------------------------------------------------------
# Missed trades: a book that did not trade a day a sibling book traded the same sleeve
# ------------------------------------------------------------------------------------------

def missed_by_book(name: str, books: set[str], rows: list[dict[str, Any]],
                   book_state: dict[str, str]) -> dict[str, Any]:
    days: dict[str, set[str]] = {}
    for r in rows:
        if r.get("sleeve") == name:
            days.setdefault(str(r["_book"]), set()).add(r["_t"].date().isoformat())
    union = set().union(*days.values()) if days else set()
    out: dict[str, Any] = {}
    for b in sorted(books):
        if not str(book_state.get(b, "")).startswith("MEASURED"):
            out[b] = {"status": book_state.get(b, "UNMEASURED")}
            continue
        mine = days.get(b, set())
        miss = sorted(union - mine)
        out[b] = {"status": "MEASURED", "traded_days": len(mine), "missed_days": len(miss),
                  "missed": miss[-10:]}
    return out


# ------------------------------------------------------------------------------------------
# Replacement: the variant's forward clock against its parent's, same window, paired by day
# ------------------------------------------------------------------------------------------

def _clock_rows(key: str) -> list[tuple[datetime, float]]:
    try:
        from research.decay_monitor import _row_r, _row_time, _shadow_ledger_rows
    except Exception:
        return []
    out = []
    for r in _shadow_ledger_rows(key):
        if str(r.get("phase") or "") != "forward":
            continue
        t, rv = _row_time(r), _row_r(r)
        if t is not None and rv is not None:
            out.append((t, rv))
    return sorted(out)


def variant_clock_keys(ids: set[str]) -> tuple[dict[str, str], str]:
    """node id -> forward clock key, for every certified clock the forward engine enrols."""
    try:
        import shadow_forward as sf
        from libs.research.hypothesis_graph import node_id
        out: dict[str, str] = {}
        for row in sf.certified_sleeves():
            r = list(row) + ["LONG"]
            sym, win, params, fam, side = r[0], r[1], r[2], r[3], r[4]
            nid = node_id(str(sym), str(fam), dict(params or {}))
            if nid in ids:
                out[nid] = sf.sleeve_key(sym, win, params, fam, side)
        return out, "MEASURED"
    except Exception as exc:
        return {}, f"UNMEASURED: forward enrolment unreadable ({type(exc).__name__}: {exc})"


def replacement_verdict(parent_rows: list[tuple[datetime, float]],
                        variant_rows: list[tuple[datetime, float]], frac: float,
                        lineage_n: int) -> dict[str, Any]:
    """REPLACE when the variant's forward log-growth beats the parent's, day by day over the
    variant's own forward window, at an always-valid lower bound > 0 with alpha split across the
    parent's lifetime lineage -- and the variant's own forward verdict promotes it.

    Days where only one clock traded count the other as flat (0R): a variant that trades more
    often is credited only for what those trades earned."""
    from research.forward_verdict import SEQ_ALPHA, sequential_lower_bound, verdict

    if not variant_rows:
        return {"verdict": "WAITING", "why": "variant has no forward rows yet"}
    start = variant_rows[0][0]
    pv: dict[str, float] = {}
    vv: dict[str, float] = {}
    for t, r in parent_rows:
        if t >= start:
            pv[t.date().isoformat()] = pv.get(t.date().isoformat(), 0.0) + r
    for t, r in variant_rows:
        vv[t.date().isoformat()] = vv.get(t.date().isoformat(), 0.0) + r
    days = sorted(set(pv) | set(vv))
    f = frac if frac and frac > 0 else DEFAULT_FRAC
    p_g = [math.log1p(max(f * pv.get(d, 0.0), -0.99)) / f for d in days]
    v_g = [math.log1p(max(f * vv.get(d, 0.0), -0.99)) / f for d in days]
    diffs = [b - a for a, b in zip(p_g, v_g, strict=True)]
    span = (datetime.fromisoformat(days[-1]) - datetime.fromisoformat(days[0])).days if days else 0
    alpha = SEQ_ALPHA / max(1, lineage_n)
    lb = sequential_lower_bound(diffs, alpha=alpha) if diffs else float("-inf")
    own = verdict([r for _t, r in variant_rows], span)
    base = {"paired_days": len(days), "span_days": span, "alpha": round(alpha, 6),
            "lineage_trials": lineage_n, "frac": f,
            "mean_diff_r": round(sum(diffs) / len(diffs), 5) if diffs else None,
            "parent_growth_r": round(sum(p_g) / len(p_g), 5) if p_g else None,
            "variant_growth_r": round(sum(v_g) / len(v_g), 5) if v_g else None,
            "lower_bound_r": None if lb == float("-inf") else round(lb, 5),
            "variant_forward": {k: own.get(k) for k in ("promote", "n", "exp_r", "reason")},
            "parent_forward_n": len(pv)}
    if len(days) < MIN_PAIRED_DAYS or span < MIN_SPAN_DAYS:
        return {**base, "verdict": "IMMATURE",
                "why": f"{len(days)}/{MIN_PAIRED_DAYS} paired days, {span}/{MIN_SPAN_DAYS} span"}
    if not own.get("promote"):
        return {**base, "verdict": "HOLD_PARENT",
                "why": f"variant's own forward verdict does not promote: {own.get('reason')}"}
    if lb > 0:
        return {**base, "verdict": "REPLACE",
                "why": (f"variant beats parent by {base['mean_diff_r']:+.4f}R/day, always-valid "
                        f"lower bound {lb:+.4f}R > 0 at alpha {alpha:.4f} "
                        f"({lineage_n} lineage trials)")}
    return {**base, "verdict": "HOLD_PARENT",
            "why": (f"no forward superiority at alpha {alpha:.4f}: lower bound "
                    f"{base['lower_bound_r']}")}


# ------------------------------------------------------------------------------------------
# The pass
# ------------------------------------------------------------------------------------------

def _hold_of(params: dict[str, Any]) -> int:
    for k in ROLE_NAMES["hold"]:
        v = params.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            return int(v) * (24 if k == "hold_days" else 1)
    return DEFAULT_HOLD_BARS


def _graph_state() -> tuple[set[str], dict[str, dict[str, list[float]]], str]:
    try:
        from research import survivor_distiller as sd
        skipped: dict[str, str] = {}
        rows = sd._graph_rows(skipped)
        return set(sd._current(rows)), sd.grid_values(rows), (
            "; ".join(f"{k}: {v}" for k, v in skipped.items()) or f"{len(rows)} graph rows")
    except Exception as exc:
        return set(), {}, f"UNMEASURED: graph unreadable ({type(exc).__name__}: {exc})"


def run(now: datetime | None = None, dry_run: bool = False) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows, book_state = ledger_rows(now)
    sleeves_doc = _json(SLEEVES, {})
    cert_book = _json(CERT_BOOK, {})
    registry = _registry(_json(REGISTRY, {}))
    pins = cert_book.get("e8_pins") if isinstance(cert_book, dict) else {}
    live = live_sleeves(sleeves_doc, cert_book, minlot_scope())
    lineage = lineage_rows()
    existing, grid, graph_note = _graph_state()
    existing |= {str(r.get("id")) for r in lineage if r.get("id")}
    try:
        from research import proposer_common as pc
    except Exception:
        pc = None  # type: ignore[assignment]

    per: dict[str, Any] = {}
    to_donate: list[dict[str, Any]] = []
    new_lineage: list[dict[str, Any]] = []
    bars_cache: dict[str, Any] = {}
    for name, info in sorted(live.items()):
        ident, how = resolve_identity(name, info.get("row"), registry, pins)
        trades = [r for r in rows if r.get("sleeve") in (name, name[:27])]
        rep: dict[str, Any] = {"books": sorted(info["books"]), "frac": info["frac"],
                               "identity": ident, "identity_how": how,
                               "trades": len(trades),
                               "losses": sum(1 for t in trades
                                             if (_num(t.get("r_multiple")) or 0) < 0),
                               "sum_r": round(sum(_num(t.get("r_multiple")) or 0.0
                                                  for t in trades), 4),
                               "missed": missed_by_book(name, info["books"], rows, book_state)}
        per[name] = rep
        if ident is None:
            continue
        sym = ident["symbol"]
        if sym not in bars_cache:
            bars_cache[sym] = pc.bars(sym) if pc is not None else None
        bars = bars_cache[sym]
        if bars is None:
            rep["diagnosis"] = f"UNMEASURED: no H1 bars for {sym} on this host"
            continue
        episodes = episodes_of(trades)
        off = bar_offset_hours(episodes, bars)
        hold = _hold_of(ident["params"])
        diags = [diagnose(t, bars, hold, off) for t in episodes]
        modes = active_modes(diags)
        rep.update({"episodes": len(episodes), "bar_offset_h": off, "modes": modes,
                    "unread": dict(Counter(d["why"] for d in diags if "why" in d))})
        variants, unmapped = make_variants(ident, modes, existing,
                                           grid.get(ident["family"]))
        rep["unmapped_modes"] = unmapped
        room = MAX_PER_PARENT_PER_DAY - minted_today(ident["clock"], lineage + new_lineage, now)
        variants = variants[:max(0, room)]
        trials = lifetime_trials(ident["clock"], lineage + new_lineage)
        for v in variants:
            trials += 1
            existing.add(v["id"])
            to_donate.append(_candidate(v, ident, name, trials))
            new_lineage.append({"at": now.isoformat(timespec="seconds"), "id": v["id"],
                                "parent": ident["clock"], "parent_sleeve": name,
                                "parent_window": is_window(name),
                                "books": sorted(info["books"]),
                                "symbol": v["symbol"], "family": v["family"],
                                "selector": v.get("selector"), "params": v["params"],
                                "operator": v["operator"], "mode": v["mode"],
                                "support": v["support"], "frac": info["frac"],
                                "lineage_trial": trials})
        rep["minted"] = [v["operator"] for v in variants]

    donated: dict[str, Any] = {"donated": 0}
    if to_donate and not dry_run and pc is not None:
        pc.donate(SOURCE, to_donate, tests_run=len(to_donate))
        donated = pc.donation_counts()
    if new_lineage and not dry_run:
        # EVERY MINTED VARIANT IS A LINEAGE TRIAL, whether or not the intake door took it: a
        # refused row was still tried, and counting it can only make the replacement bar harder.
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with LINEAGE.open("a", encoding="utf-8") as fh:
            for r in new_lineage:
                fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
        lineage = lineage + new_lineage

    replacements = judge_replacements(lineage)
    report = {"generated_at": now.isoformat(timespec="seconds"), "source": SOURCE,
              "trail_days": TRAIL_DAYS, "books": book_state, "graph": graph_note,
              "sleeves": per, "minted": len(new_lineage),
              "donation": {k: donated.get(k) for k in ("donated", "refused_unstamped",
                                                       "refused_wrong_lane", "path")},
              "lineage_total": len(lineage), "replacements": replacements,
              "dry_run": dry_run,
              "rule": ("variants are hypotheses: the gauntlet judges each at the charged trial "
                       "count, and a parent is replaced only on forward superiority at "
                       "alpha / lineage trials")}
    if not dry_run:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    return report


def judge_replacements(lineage: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {str(r["id"]) for r in lineage if r.get("id")}
    if not ids:
        return {"status": "NO_LINEAGE", "verdicts": []}
    keys, how = variant_clock_keys(ids)
    verdicts = []
    for r in lineage:
        key = keys.get(str(r.get("id")))
        if not key:
            continue
        parent = str(r["parent"])
        v = replacement_verdict(_clock_rows(parent), _clock_rows(key),
                                float(r.get("frac") or 0.0),
                                lifetime_trials(parent, lineage))
        verdicts.append({"parent": parent, "parent_sleeve": r.get("parent_sleeve"),
                         "parent_window": bool(r.get("parent_window")), "variant_id": r["id"],
                         "books": list(r.get("books") or ["fusion"]),
                         "variant_symbol": r.get("symbol"), "variant_family": r.get("family"),
                         "variant_selector": r.get("selector"),
                         "variant_params": r.get("params"),
                         "variant_clock": key, **v})
    return {"status": how, "certified_variants": len(keys), "verdicts": verdicts}


# ------------------------------------------------------------------------------------------
# The act (daily): retire a parent sleeves.json row a LIVE, funded variant has beaten
# ------------------------------------------------------------------------------------------

def act(report: dict[str, Any] | None = None, sleeves_path: Path | None = None,
        now: datetime | None = None) -> dict[str, Any]:
    """Apply REPLACE verdicts. A sleeves.json parent is RETIRED only when its variant's row is
    LIVE with risk_frac > 0, so capital moves to the variant and is never simply removed; the
    position is queued for close through decay_monitor's queue. A gateway-window parent is
    written to BOOK_ROLLOUTS.json as a per-book request: its sizing is in CERT_BOOK_LIVE.json,
    which this organ never edits."""
    now = now or datetime.now(tz=UTC)
    report = report or _json(REPORT, {})
    sp = sleeves_path or SLEEVES
    doc = _json(sp, {})
    rows = doc.get("sleeves") if isinstance(doc, dict) else None
    verdicts = ((report.get("replacements") or {}).get("verdicts") or [])
    # A DEAD HOURLY LEG MUST NOT RETIRE ON YESTERDAY'S BOUND. The verdicts are only as current
    # as the report that carries them; past REPORT_MAX_AGE_H nothing is acted on, and says so.
    gen = _ts(report.get("generated_at"))
    if verdicts and (gen is None or now - gen > timedelta(hours=REPORT_MAX_AGE_H)):
        res = {"status": (f"STALE_REPORT: {REPORT.name} generated_at "
                          f"{report.get('generated_at')!r} is older than {REPORT_MAX_AGE_H}h "
                          "or unreadable; no verdict acted on"), "done": []}
        # ONE ROW PER STALE EPISODE, not one per pass: a dead leg would otherwise append a row
        # every hour. A new row is written only when the last one is not this same staleness.
        prev = _jsonl(ACTIONS)[-1:] if ACTIONS.exists() else []
        if not (prev and prev[0].get("action") == "STALE_REPORT"
                and prev[0].get("why") == res["status"]):
            ACTIONS.parent.mkdir(parents=True, exist_ok=True)
            with ACTIONS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": now.isoformat(timespec="seconds"),
                                     "action": "STALE_REPORT", "why": res["status"]}) + "\n")
        return res
    done: list[dict[str, Any]] = []
    window_requests: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return {"status": f"UNMEASURED: no roster at {sp}", "done": []}
    by_name = {str(s.get("name")): s for s in rows if isinstance(s, dict)}
    changed = False
    for v in verdicts:
        if v.get("verdict") != "REPLACE":
            continue
        # EVERY BOOK THE PARENT TRADES GETS THE REPLACEMENT (principal 2026-11-03: "all things
        # get applied to all accounts"). A book this organ cannot write -- a gateway window on any
        # account, and every prop book, whose sizing lives in CERT_BOOK_LIVE.json under its
        # firm's rails -- gets a rollout request for its own allocator; the Fusion roster row is
        # retired here, below.
        for book in v.get("books") or ["fusion"]:
            if book == "fusion" and not v.get("parent_window"):
                continue
            window_requests.append({**v, "book": book,
                                    "requested_at": now.isoformat(timespec="seconds"),
                                    "consumer": BOOK_CONSUMERS.get(book, "allocator owners"),
                                    "firm_rails": BOOK_RAILS.get(book, "")})
        if v.get("parent_window"):
            continue
        vrow = by_name.get(str(v.get("variant_clock")))
        prow = by_name.get(str(v.get("parent_sleeve"))) or by_name.get(str(v.get("parent")))
        if prow is None or str(prow.get("status") or "").upper() != "LIVE":
            continue
        if vrow is None or str(vrow.get("status") or "").upper() != "LIVE" \
                or not (_num(vrow.get("risk_frac")) or 0) > 0:
            done.append({"parent": prow.get("name"), "variant": v.get("variant_clock"),
                         "action": "PENDING_VARIANT_LIVE",
                         "why": "variant has not been promoted LIVE with capital yet; the "
                                "parent keeps every unit of its risk until it is"})
            continue
        reason = (f"replaced by forward-superior loss-learning variant "
                  f"{v.get('variant_clock')}: {v.get('why')}")
        # THE SAME FIELDS EVERY OTHER RETIREMENT PATH WRITES (promoter.retire_banned /
        # retire_unrunnable / retire_tier_s_live). A RETIRED row left carrying a positive
        # risk_frac is still a fraction to anyone who sums the roster, and a door the
        # alpha-state ledger never sees is a transition the desk cannot reconstruct.
        was = str(prow.get("status") or "")
        prow.update({"status": "RETIRED", "risk_frac": 0.0, "risk_frac_source": "none",
                     "retired_at": now.isoformat(timespec="seconds"), "retired_by": SOURCE,
                     "retire_reason": reason})
        changed = True
        done.append({"parent": prow.get("name"), "variant": v.get("variant_clock"),
                     "action": "RETIRED_PARENT", "why": v.get("why"),
                     "_door": (was, reason, v),
                     # RULE 1, RECORDED. A retirement is a zero on the parent, so the growth it
                     # gives up is written beside the growth it buys -- both sides measured, from
                     # the verdict that decided it, in log-wealth per day at the parent's own
                     # fraction. Not appended to data/missed_growth.jsonl: that ledger is keyed
                     # by the sealed rails registry (libs.portfolio.rails) and this is not a rail.
                     "opportunity_cost": {
                         "unit": "forward log-wealth per day, at frac "
                                 f"{v.get('frac')}",
                         "parent_forgone_per_day": v.get("parent_growth_r"),
                         "variant_gain_per_day": v.get("variant_growth_r"),
                         "net_per_day": v.get("mean_diff_r"),
                         "lower_bound_r": v.get("lower_bound_r"),
                         "paired_days": v.get("paired_days"), "alpha": v.get("alpha"),
                         "two_sided": True,
                         "why": ("the parent keeps every unit of its risk until this bound "
                                 "clears; the measured difference IS the growth the "
                                 "retirement buys")}})
    if changed:
        # ATOMIC, AND RE-READ FIRST. The hourly promoter writes this same file from another
        # process, so a plain read-modify-write can lose its pass or be lost by it. The rows are
        # re-read here and only the parents this pass retires are re-applied, onto whatever the
        # promoter left; the replace is atomic so no reader ever sees a half-written roster.
        fresh = _json(sp, None)
        if isinstance(fresh, dict) and isinstance(fresh.get("sleeves"), list):
            fresh_by = {str(r.get("name")): r for r in fresh["sleeves"] if isinstance(r, dict)}
            for d in done:
                if d.get("action") != "RETIRED_PARENT":
                    continue
                row, mine = fresh_by.get(str(d["parent"])), by_name.get(str(d["parent"]))
                if row is None or mine is None:
                    continue
                if str(row.get("status") or "").upper() != "LIVE":
                    d["action"] = "SUPERSEDED"
                    d["why"] = (f"another writer left this row {row.get('status')!r} before this "
                                f"pass could retire it; nothing written")
                    continue
                vfresh = fresh_by.get(str(d.get("variant")))
                if vfresh is None or str(vfresh.get("status") or "").upper() != "LIVE" \
                        or not (_num(vfresh.get("risk_frac")) or 0) > 0:
                    d["action"] = "SUPERSEDED"
                    d["why"] = ("the variant row is no longer LIVE with capital in the roster "
                                "re-read just before the write; the parent keeps its risk")
                    continue
                row.update({k: mine[k] for k in ("status", "risk_frac", "risk_frac_source",
                                                 "retired_at", "retired_by", "retire_reason")})
            doc = fresh
        wrote, how = _write_roster(sp, doc)
        if not wrote:
            for d in done:
                if d.get("action") == "RETIRED_PARENT":
                    d["action"] = "WRITE_FAILED"
                    d["why"] = f"roster not written ({how}); nothing retired"
        # DOORS ONLY AFTER THE WRITE, AND ONLY FOR ROWS ACTUALLY RETIRED. RETIRED is one-way on
        # the alpha-state ledger; a door for a row the re-read superseded or a write that failed
        # would record a retirement that never happened.
        for d in done:
            door = d.pop("_door", None)
            if door is not None and d.get("action") == "RETIRED_PARENT":
                _note_retirement_door(str(d["parent"]), *door)
        try:
            from research.decay_monitor import queue_close
            queue_close([str(d["parent"]) for d in done
                         if d["action"] == "RETIRED_PARENT"],
                        path=sp.parent / "RETIRED_CLOSE_QUEUE.json")
        except Exception as exc:
            done.append({"action": "CLOSE_QUEUE_FAILED", "why": f"{type(exc).__name__}: {exc}"})
    for d in done:
        d.pop("_door", None)
    if done:
        ACTIONS.parent.mkdir(parents=True, exist_ok=True)
        with ACTIONS.open("a", encoding="utf-8") as fh:
            for d in done:
                fh.write(json.dumps({"at": now.isoformat(timespec="seconds"), **d},
                                    default=str) + "\n")
    WINDOW_REQUESTS.parent.mkdir(parents=True, exist_ok=True)
    WINDOW_REQUESTS.write_text(json.dumps({"at": now.isoformat(timespec="seconds"),
                                           "requests": window_requests,
                                           "rule": "a gateway window or a prop book is replaced "
                                                   "by that book's allocator inside its firm's "
                                                   "rails, never by this organ"},
                                          indent=1, default=str), "utf-8")
    return {"status": "OK", "done": done, "window_requests": len(window_requests)}


#: os.replace onto a file another process holds open raises WinError 5 on Windows (Python
#: opens without FILE_SHARE_DELETE, and the gateway reads sleeves.json every pass).
REPLACE_TRIES = 5
REPLACE_SLEEP_S = 0.2


def _write_roster(sp: Path, doc: Any) -> tuple[bool, str]:
    """Atomic replace, retried while a reader holds the file; then an in-place write; the temp
    file never survives. Returns (written, how). Never raises."""
    import time

    body = json.dumps(doc, indent=2, default=str)
    tmp = sp.with_suffix(sp.suffix + f".loss_learner.{os.getpid()}.tmp")
    try:
        tmp.write_text(body, "utf-8")
    except OSError as exc:
        return False, f"temp write failed: {type(exc).__name__}: {exc}"
    last: Exception | None = None
    try:
        for _ in range(REPLACE_TRIES):
            try:
                os.replace(tmp, sp)
                return True, "atomic replace"
            except PermissionError as exc:
                last = exc
                time.sleep(REPLACE_SLEEP_S)
        try:
            sp.write_text(body, "utf-8")
            return True, f"in-place write after {REPLACE_TRIES} refused replaces ({last})"
        except OSError as exc:
            return False, f"replace refused ({last}) and in-place write failed: {exc}"
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _note_retirement_door(name: str, from_status: str, reason: str,
                          v: dict[str, Any]) -> None:
    """Write the RETIRED door onto the alpha-state ledger, through the promoter's own writer.

    Retirement is the one door the ledger always accepts. A failure to take a note must never
    abort the retirement itself (the `plog` lesson, 2026-09-03), so it is named and swallowed."""
    try:
        from research import promoter
        promoter.note_door(name, door="RETIRED", from_status=from_status or "LIVE",
                           to_status="RETIRED", reason=reason,
                           evidence={"replaced_by": v.get("variant_clock"),
                                     "lower_bound_r": v.get("lower_bound_r"),
                                     "paired_days": v.get("paired_days"),
                                     "alpha": v.get("alpha"),
                                     "lineage_trials": v.get("lineage_trials"),
                                     "retired_by": SOURCE})
        promoter.flush_door_events()
    except Exception as exc:                            # pragma: no cover - note-taking only
        print(f"{SOURCE}: RETIRED door not recorded for {name} "
              f"({type(exc).__name__}: {exc})", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="track, diagnose, mint, judge")
    ap.add_argument("--act", action="store_true", help="apply REPLACE verdicts (daily)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.act:
        res = act()
        print(json.dumps({k: res[k] for k in res if k != "done"} | {"n_done": len(res.get("done")
                                                                                    or [])}))
        return 0
    rep = run(dry_run=a.dry_run)
    if not a.dry_run:
        # LLM SIZING SHADOW (2026-11-03): deliberate on fresh gold signals before they close,
        # score closed ones by E[log W]. Shadow only; a failure never costs this leg.
        try:
            from research import llm_sizing_shadow
            llm_sizing_shadow.run()
        except Exception as exc:
            print(f"llm_sizing_shadow: {type(exc).__name__}: {exc}"[:200])
    print(json.dumps({"sleeves": len(rep["sleeves"]), "minted": rep["minted"],
                      "donated": rep["donation"].get("donated"),
                      "books": rep["books"],
                      "replacements": len(rep["replacements"].get("verdicts") or [])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
