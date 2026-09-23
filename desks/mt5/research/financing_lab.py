"""THE FINANCING LAB: the live book's balance sheet, its stress, and the Allocator-V2 evidence.

WHAT THIS IS (LAWS 5m, the Collateral/Settlement/Balance-Sheet organ). Every pass it measures
what the live CFD book actually costs to carry -- swaps paid out of the desk's own deal ledger,
margin in use, funding by currency for a EUR account holding USD/JPY/GBP/NOK exposures, the
next settlement's charge and whether it is the triple night -- runs the book through three
stress scenarios (2020-03, the 2022 rate shock, and the worst 2026 day MEASURED off the desk's
own H1 tape), and builds the named evidence vector of `libs.portfolio.allocator_evidence` for
every LIVE / STANDBY sleeve and for the book, including the book's geometric return AFTER the
financing its replays never charged.

TWO ARTIFACTS, TWO READERS. `data/allocator_evidence.json` is the input `pf_allocator` reads
(lineage factor, financing R/day, whether the replay charged it) and is `kind: "evidence"` --
it sets no fraction, no cap and no veto. `reports/FINANCING_LAB.json` is the human-readable
measurement: the balance sheet, the funding legs, the scenarios, what was UNMEASURED and why.

UNMEASURED IS A VALUE HERE. A host without a terminal cannot read the margin in use or the
account's leverage; it says so, and every downstream number that needs them is UNMEASURED with
the reason, never a zero and never yesterday's figure (L1.28a). `borrow` is UNMEASURED BY
CONSTRUCTION for a CFD book and the report carries that sentence rather than a rate.

    python desks/mt5/research/financing_lab.py --once --budget-s 600 [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import allocator_evidence as AE  # noqa: E402
from libs.portfolio import financing as F  # noqa: E402

DATA = DESK / "data"
REPORTS = DESK / "reports"
ACCOUNT_STATE = DATA / "account_state.json"
GATEWAY_STATE = DATA / "gateway_state.json"
SLEEVES = DATA / "sleeves.json"
ALLOCATION = REPORTS / "pf_allocation.json"
ROI_EVIDENCE = DATA / "roi_capital_evidence.json"
SWAP_REJUDGE = REPORTS / "SWAP_REJUDGE.json"
LIVE_LEDGER = DATA / "live_ledger.jsonl"
BROKER_CLOCK = DATA / "broker_clock.json"
TERMS_DIR = DATA / "tape" / "contract_terms"
UNIVERSE = DATA / "universe" / "universe.json"
BARS_DIR = DATA / "universe"
CAPACITY = REPORTS / "CAPACITY.json"
OUT_EVIDENCE = DATA / "allocator_evidence.json"
OUT_REPORT = REPORTS / "FINANCING_LAB.json"

BUDGET_S = 600.0
ACCOUNT_CCY_DEFAULT = "EUR"
#: the swap window the ledger is summed over
SWAP_WINDOW_DAYS = 30
#: the tape scenario's horizon: the worst 24 H1 bars against each held side, in 2026
TAPE_WINDOW_BARS = 24
#: the rollover hour used when broker_clock.json is silent (server UTC+2 -> 00:00 server)
ROLLOVER_HOUR_UTC_FALLBACK = 22
UNMEASURED = F.UNMEASURED
MEASURED = F.MEASURED
DECLARED = F.DECLARED


# --------------------------------------------------------------------------------- helpers


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> Path:
    """tmp + os.replace; a read-only destination is WinError 5 on this box, so fall back to a
    direct rewrite rather than a crash that would stop the pass."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
        return path
    except PermissionError:
        try:
            os.chmod(path, 0o666)
            os.replace(tmp, path)
            return path
        except OSError:
            pass
    path.write_bytes(tmp.read_bytes())
    return path


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


class _Budget:
    def __init__(self, budget_s: float) -> None:
        self.t0 = time.monotonic()
        self.budget_s = float(budget_s)
        self.exhausted_at: str | None = None

    def over(self, step: str) -> bool:
        if self.exhausted_at is not None:
            return True
        if time.monotonic() - self.t0 > self.budget_s:
            self.exhausted_at = step
            return True
        return False

    @property
    def elapsed(self) -> float:
        return round(time.monotonic() - self.t0, 3)


# --------------------------------------------------------------------------------- account


def read_account() -> dict[str, Any]:
    """The account as the terminal reports it, else as the desk's own state files carry it."""
    out: dict[str, Any] = {"currency": ACCOUNT_CCY_DEFAULT, "balance": None, "equity": None,
                           "margin": None, "leverage": None, "stop_out_pct": None,
                           "positions": [], "source": "", "unmeasured": []}
    try:
        import MetaTrader5 as mt5  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        mt5 = None
    if mt5 is not None:
        opened = False
        try:
            if mt5.terminal_info() is None:
                try:
                    from mt5desk.config import terminal_path
                    path = terminal_path()
                except Exception:
                    path = ""
                opened = bool(mt5.initialize(path=path) if path else mt5.initialize())
            acc = mt5.account_info() if (opened or mt5.terminal_info() is not None) else None
            if acc is not None:
                out.update({"currency": str(acc.currency or ACCOUNT_CCY_DEFAULT),
                            "balance": float(acc.balance), "equity": float(acc.equity),
                            "margin": float(acc.margin), "leverage": float(acc.leverage),
                            "stop_out_pct": float(getattr(acc, "margin_so_so", 0.0) or 0.0)
                            or None, "source": "live terminal"})
                rows = []
                for p in mt5.positions_get() or ():
                    rows.append({"symbol": p.symbol, "type": int(p.type), "volume": p.volume,
                                 "price_open": p.price_open, "price_current": p.price_current,
                                 "profit": p.profit, "swap": p.swap,
                                 "sleeve": str(getattr(p, "comment", "") or "")})
                out["positions"] = rows
                return out
        except Exception as exc:  # the terminal is not a reason to lose the pass
            out["unmeasured"].append(f"terminal: {type(exc).__name__}: {exc}")
        finally:
            if opened:
                with suppress(Exception):
                    mt5.shutdown()
    st = _read_json(ACCOUNT_STATE) or {}
    gw = _read_json(GATEWAY_STATE) or {}
    if isinstance(st, dict):
        out["currency"] = str(st.get("currency") or ACCOUNT_CCY_DEFAULT)
        out["balance"] = _f(st.get("balance"))
        out["equity"] = _f(st.get("equity"))
        if st.get("margin") is not None:
            out["margin"] = _f(st.get("margin"))
    if isinstance(gw, dict):
        if _f(gw.get("equity")) is not None:
            out["equity"] = _f(gw.get("equity"))
        pos = gw.get("position")
        if isinstance(pos, list):
            out["positions"] = [r for r in pos if isinstance(r, dict)]
    out["source"] = "account_state.json + gateway_state.json (no terminal on this host)"
    if out["margin"] is None:
        out["unmeasured"].append("margin in use: no terminal and account_state.json carries "
                                 "no margin field")
    out["unmeasured"].append("account leverage: readable from the terminal only")
    out["unmeasured"].append("stop-out level: readable from the terminal only")
    return out


# ----------------------------------------------------------------------------------- terms


def load_terms(leverage: float | None) -> tuple[dict[str, F.InstrumentTerms], str]:
    """Contract terms per symbol: the latest tape observation, else the universe registry."""
    latest: Path | None = None
    try:
        files = sorted(TERMS_DIR.glob("*.parquet"))
        latest = files[-1] if files else None
    except OSError:
        latest = None
    out: dict[str, F.InstrumentTerms] = {}
    src = ""
    if latest is not None:
        try:
            import pandas as pd
            df = pd.read_parquet(latest)
            if "observed_at" in df.columns:
                df = df.sort_values("observed_at")
            for _, row in df.drop_duplicates("symbol", keep="last").iterrows():
                rec = {k: (None if (isinstance(v, float) and math.isnan(v)) else v)
                       for k, v in row.to_dict().items()}
                out[str(rec["symbol"])] = F.InstrumentTerms.from_row(rec, leverage=None)
            src = f"contract_terms tape {latest.name} ({len(out)} symbols)"
        except Exception as exc:
            out = {}
            src = f"contract_terms tape unreadable ({type(exc).__name__})"
    reg = _read_json(UNIVERSE)
    if isinstance(reg, dict):
        reg = reg.get("symbols", reg)
        n_reg = 0
        for sym, row in reg.items():
            if not isinstance(row, dict):
                continue
            cls = str(row.get("asset_class") or "")
            if sym in out:
                t = out[sym]
                if not t.asset_class and cls:
                    out[sym] = F.InstrumentTerms(**{**t.__dict__, "asset_class": cls})
                continue
            out[sym] = F.InstrumentTerms.from_row(row, symbol=sym)
            n_reg += 1
        src = (src + "; " if src else "") + f"universe.json ({n_reg} symbols without tape terms)"
    # THE LEVERAGE TIER: the account's leverage applies to forex; a CFD's margin rate is the
    # venue's own per-instrument number the terms tape does not carry, so it stays UNMEASURED.
    if leverage is not None and leverage > 0:
        for sym, t in list(out.items()):
            if t.asset_class in ("Forex", "Forex Exotics"):
                out[sym] = F.InstrumentTerms(**{**t.__dict__, "leverage": float(leverage)})
    return out, src or "no contract terms on this host"


def read_bars(symbol: str, since: str = "2026-01-01") -> tuple[float | None, list[float]]:
    """(last close, closes since `since`) from the symbol's H1 parquet, or (None, [])."""
    path = BARS_DIR / f"{symbol}_H1.parquet"
    if not path.exists():
        return None, []
    try:
        import pandas as pd
        df = pd.read_parquet(path, columns=["close"])
        closes = df["close"].astype(float)
        last = float(closes.iloc[-1]) if len(closes) else None
        recent = closes[closes.index >= since] if hasattr(closes.index, "tz") else closes
        return last, [float(x) for x in recent.to_numpy()]
    except Exception:
        return None, []


# ---------------------------------------------------------------------------------- ledger


def swaps_paid(now: datetime, window_days: int = SWAP_WINDOW_DAYS) -> dict[str, Any]:
    """Swap actually charged on closed deals in the window, from the desk's own live ledger."""
    try:
        lines = LIVE_LEDGER.read_text("utf-8").splitlines()
    except OSError:
        return {"status": UNMEASURED, "why": "no live ledger on this host", "window_days":
                window_days}
    since = now - timedelta(days=window_days)
    by_symbol: dict[str, float] = {}
    by_sleeve: dict[str, float] = {}
    n = 0
    n_nonzero = 0
    total = 0.0
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        try:
            t = datetime.fromisoformat(str(r.get("time")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        if t < since:
            continue
        sw = _f(r.get("swap"))
        if sw is None:
            continue
        n += 1
        if sw != 0.0:
            n_nonzero += 1
        total += sw
        by_symbol[str(r.get("symbol"))] = by_symbol.get(str(r.get("symbol")), 0.0) + sw
        by_sleeve[str(r.get("sleeve"))] = by_sleeve.get(str(r.get("sleeve")), 0.0) + sw
    return {"status": MEASURED if n else UNMEASURED,
            "why": (f"{n} closed deal(s) in the last {window_days} days" if n
                    else f"no closed deals in the last {window_days} days"),
            "window_days": window_days, "n_deals": n, "n_deals_with_swap": n_nonzero,
            "total_account_ccy": round(total, 4),
            "by_symbol": {k: round(v, 4) for k, v in sorted(by_symbol.items())},
            "by_sleeve": {k: round(v, 4) for k, v in sorted(by_sleeve.items())},
            "sign": "MT5: positive is a credit to the desk"}


def rollover_hour_utc() -> tuple[int, str]:
    bc = _read_json(BROKER_CLOCK)
    off = _f(bc.get("utc_offset_hours")) if isinstance(bc, dict) else None
    if off is None:
        return ROLLOVER_HOUR_UTC_FALLBACK, "fallback (broker_clock.json unreadable)"
    return int((24 - int(off)) % 24), f"broker_clock.json utc_offset_hours={off:g}"


# -------------------------------------------------------------------------------- evidence


def _family_of(name: str, row: dict[str, Any] | None) -> str:
    if row and row.get("family"):
        return str(row["family"])
    parts = name.split("_")
    if name.startswith("gold_") or parts[-1].endswith("_DAY") \
            or (len(parts) > 2 and parts[-1] in ("TREND", "NORMAL", "RANGE")):
        return "session_bracket"
    return "_".join(parts[1:-1]) or "unspecified"


def _rejudge_index(doc: Any) -> list[dict[str, Any]]:
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
        return []
    out = []
    for r in doc["records"]:
        if not isinstance(r, dict):
            continue
        cert = str(r.get("certificate") or "")
        m = re.search(r"p=([0-9a-f]+)", cert)
        out.append({"key": _norm(f"{r.get('symbol')}_{r.get('family')}_{r.get('window')}"),
                    "hash": m.group(1) if m else "", "rec": r})
    return out


def _match_rejudge(name: str, index: list[dict[str, Any]]) -> dict[str, Any] | None:
    n = _norm(name)
    best: dict[str, Any] | None = None
    for row in index:
        hit = bool(row["key"]) and row["key"] in n and (not row["hash"] or row["hash"] in n)
        if hit and (best is None or len(row["key"]) + len(row["hash"])
                    > len(best["key"]) + len(best["hash"])):
            best = row
    return None if best is None else best["rec"]


def evidence_vectors(sleeve_rows: list[dict[str, Any]], book: dict[str, float],
                     alloc: dict[str, Any], roi_doc: Any, rejudge: Any,
                     terms: dict[str, F.InstrumentTerms], capacity: Any
                     ) -> tuple[list[AE.EvidenceVector], dict[str, Any]]:
    """One named bundle per LIVE/STANDBY sleeve and per funded book sleeve."""
    rows_by_name = {str(r.get("name")): r for r in sleeve_rows if r.get("name")}
    roster = list(rows_by_name)
    for n in book:
        if n not in rows_by_name:
            roster.append(n)
    roi_terms, roi_why = AE.roi_factors_by_mechanism(roi_doc if isinstance(roi_doc, dict)
                                                     else None)
    mechanisms = list(roi_terms)
    index = _rejudge_index(rejudge)
    decay = ((alloc.get("decay_posterior") or {}).get("by_sleeve") or {}) \
        if isinstance(alloc, dict) else {}
    marginal = alloc.get("marginal_delta_elog") or {} if isinstance(alloc, dict) else {}
    loading = ((alloc.get("effective_heat") or {}).get("top_loading") or {}) \
        if isinstance(alloc, dict) else {}
    tilts = ((alloc.get("macro_regime") or {}).get("tilts") or {}) \
        if isinstance(alloc, dict) else {}
    cap_rows: dict[str, dict[str, Any]] = {}
    if isinstance(capacity, dict) and isinstance(capacity.get("rows"), list):
        for r in capacity["rows"]:
            if isinstance(r, dict) and r.get("sleeve"):
                cap_rows[str(r["sleeve"])] = r
    lineage_of: dict[str, str] = {}
    meta: dict[str, dict[str, Any]] = {}
    for name in roster:
        row = rows_by_name.get(name)
        fam = _family_of(name, row)
        sym = str((row or {}).get("symbol") or name.split("_")[0])
        # the legs come from the terms when the tape has them and from the symbol's own
        # six letters when it does not, so a pair and its inverse share one lineage either way
        t = terms.get(sym) or F.InstrumentTerms(symbol=sym)
        legs = list(t.legs())
        tf = str((row or {}).get("timeframe") or "H1")
        lineage_of[name] = AE.lineage_key(fam, sym, legs, tf)
        meta[name] = {"family": fam, "symbol": sym, "timeframe": tf, "row": row}
    lin_terms = AE.lineage_factors(book, lineage_of)
    vectors: list[AE.EvidenceVector] = []
    n_fin = 0
    n_roi = 0
    for name in roster:
        m = meta[name]
        row = m["row"] or {}
        mech = AE.match_mechanism(name, m["family"], mechanisms)
        roi_t = roi_terms.get(mech) if mech else None
        if roi_t is not None and roi_t.status == MEASURED:
            n_roi += 1
        rec = _match_rejudge(name, index)
        fin_t: AE.Term | None = None
        charged: bool | None = None
        if rec is not None:
            sd, sn = _f(row.get("shadow_days")), _f(row.get("shadow_n"))
            tpd = (sn / sd) if sd and sn and sd > 0 else 1.0
            fin_t = AE.financing_term(_f(rec.get("swap_charge_r")), tpd, _f(rec.get("edge_r")))
            if fin_t.status == MEASURED:
                n_fin += 1
                if not (sd and sn and sd > 0):
                    fin_t = AE.Term(fin_t.name, fin_t.value, fin_t.status, fin_t.factor,
                                    fin_t.source, fin_t.note + "; trades/day DECLARED 1.0 "
                                    "(one signal per session-day; no shadow count on the row)")
            # SWAP_REJUDGE's own finding: every certificate was minted at zero swap.
            charged = False
        desc: dict[str, AE.Term] = {}
        if name in marginal and _f(marginal[name]) is not None:
            desc["posterior_edge"] = AE.descriptive("posterior_edge", float(marginal[name]),
                                                    "pf_allocation.marginal_delta_elog")
        sd = _f(row.get("shadow_days"))
        if sd is not None and sd > 0:
            desc["confidence"] = AE.descriptive("confidence", 4.0 * sd / (4.0 * sd + 60.0),
                                                "sleeves.json shadow_days -> 4n/(4n+60)")
        hz = _f((decay.get(name) or {}).get("hazard")) if isinstance(decay, dict) else None
        if hz is not None and hz > 0:
            desc["alpha_half_life"] = AE.descriptive("alpha_half_life", math.log(2.0) / hz,
                                                     "pf_allocation.decay_posterior hazard "
                                                     "-> ln2/hazard days")
        ld = _f(loading.get(name)) if isinstance(loading, dict) else None
        if ld is not None:
            desc["common_hidden_exposures"] = AE.descriptive(
                "common_hidden_exposures", abs(ld), "pf_allocation.effective_heat.top_loading")
        tl = _f(tilts.get(name)) if isinstance(tilts, dict) else None
        if tl is not None:
            desc["regime_relevance"] = AE.descriptive("regime_relevance", tl,
                                                      "pf_allocation.macro_regime.tilts")
        cr = cap_rows.get(name)
        if cr is not None and _f(cr.get("headroom_multiple")) is not None:
            desc["capacity"] = AE.descriptive("capacity", float(cr["headroom_multiple"]),
                                              "reports/CAPACITY.json headroom_multiple")
        vectors.append(AE.build_vector(
            name, family=m["family"], symbol=m["symbol"], lineage=lineage_of[name],
            lineage_term=lin_terms.get(name), roi_term=roi_t, financing=fin_t,
            financing_charged_in_replay=charged, descriptive_terms=desc))
    return vectors, {"roi": roi_why, "n_roster": len(roster), "n_in_book": len(book),
                     "n_financing_measured": n_fin, "n_roi_measured": n_roi,
                     "n_rejudge_records": len(index)}


# ------------------------------------------------------------------------------------ pass


def run(*, budget_s: float = BUDGET_S, dry_run: bool = False) -> dict[str, Any]:
    now = _now()
    b = _Budget(budget_s)
    unmeasured: list[str] = []

    acct = read_account()
    unmeasured.extend(acct["unmeasured"])
    ccy = str(acct["currency"] or ACCOUNT_CCY_DEFAULT)
    equity = _f(acct["equity"])
    balance = _f(acct["balance"]) if _f(acct["balance"]) is not None else equity
    positions = F.positions_from_rows(acct["positions"])
    terms, terms_src = load_terms(_f(acct["leverage"]))

    # PRICES AND RATES, read once: the held symbols, the funding pairs and the roster symbols.
    sleeves_doc = _read_json(SLEEVES)
    raw_rows = (sleeves_doc.get("sleeves") if isinstance(sleeves_doc, dict) else sleeves_doc)
    sleeve_rows = [r for r in (raw_rows if isinstance(raw_rows, list) else [])
                   if isinstance(r, dict) and str(r.get("status")) in ("LIVE", "STANDBY")]
    alloc = _read_json(ALLOCATION) or {}
    book: dict[str, float] = {}
    if isinstance(alloc, dict) and isinstance(alloc.get("book"), dict):
        book = {str(k): float(v) for k, v in alloc["book"].items()
                if _f(v) is not None and float(v) > 0}
    want: set[str] = {p.symbol for p in positions}
    for p in positions:
        t = terms.get(p.symbol)
        if t is not None:
            for leg in t.legs():
                if leg in F.CURRENCIES and leg != ccy:
                    want.update({f"{ccy}{leg}", f"{leg}{ccy}"})
            if t.currency_profit and t.currency_profit != ccy:
                want.update({f"{ccy}{t.currency_profit}", f"{t.currency_profit}{ccy}"})
    prices: dict[str, float] = {}
    closes_2026: dict[str, list[float]] = {}
    for sym in sorted(want):
        if b.over("prices"):
            unmeasured.append("prices: budget exhausted before every symbol was read")
            break
        if sym not in terms and not (BARS_DIR / f"{sym}_H1.parquet").exists():
            continue
        last, recent = read_bars(sym)
        if last is not None:
            prices[sym] = last
            closes_2026[sym] = recent
    rates = dict(prices)

    # THE BALANCE SHEET AND THE CASH LADDER.
    margin_m = (F.measured(float(acct["margin"]), acct["source"]) if _f(acct["margin"])
                is not None else F.unmeasured("margin in use not readable on this host"))
    so = (F.measured(float(acct["stop_out_pct"]), "terminal margin_so_so")
          if _f(acct["stop_out_pct"]) else F.unmeasured("stop-out level readable from the "
                                                        "terminal only"))
    sheet: F.BalanceSheet | None = None
    if equity is not None and balance is not None:
        sheet = F.BalanceSheet(ccy, balance, equity, margin_m, so, acct["source"])
    else:
        unmeasured.append("equity/balance: neither the terminal nor the state files carry them")
    roll_h, roll_src = rollover_hour_utc()
    positions = [F.OpenPosition(p.symbol, p.side, p.lots, p.price_open,
                                price=p.price if p.price else prices.get(p.symbol),
                                floating_pnl=p.floating_pnl, swap_accrued=p.swap_accrued,
                                sleeve=p.sleeve) for p in positions]
    ladder = (F.cash_ladder(sheet, positions, terms, rates) if sheet is not None
              else {"status": UNMEASURED, "why": "no balance sheet"})
    funding_pairs = {s: t for s, t in terms.items()
                     if len(s) == 6 and (s.startswith(ccy) or s.endswith(ccy))
                     and s[:3] in F.CURRENCIES and s[3:] in F.CURRENCIES}
    funding = F.funding_by_currency(positions, terms, rates, ccy, funding_pairs, prices)
    settlement: dict[str, Any] = {"rollover_hour_utc": roll_h, "source": roll_src,
                                  "by_symbol": {}}
    for sym in sorted({p.symbol for p in positions}):
        t = terms.get(sym)
        if t is not None:
            settlement["by_symbol"][sym] = F.settlement_calendar(now, t, rollover_hour_utc=roll_h)
    swap_curve = {sym: F.swap_curve(terms[sym], prices.get(sym))
                  for sym in sorted({p.symbol for p in positions}) if sym in terms}
    paid = swaps_paid(now)

    # STRESS: two declared histories and the desk's own measured 2026 tape event.
    tape_moves: dict[str, float] = {}
    tape_dates: dict[str, Any] = {}
    net_side: dict[str, float] = {}
    for p in positions:
        net_side[p.symbol] = net_side.get(p.symbol, 0.0) + p.sign * p.lots
    for sym, signed in net_side.items():
        closes = closes_2026.get(sym) or []
        w = F.worst_adverse_move(closes, "LONG" if signed >= 0 else "SHORT", TAPE_WINDOW_BARS)
        if w.known and w.value is not None:
            tape_moves[sym] = w.value
            tape_dates[sym] = {"move": round(w.value, 6), "n_closes_2026": len(closes)}
        else:
            unmeasured.append(f"2026 tape event for {sym}: {w.why}")
    scenarios = [F.SCENARIO_2020_03, F.SCENARIO_2022_RATES,
                 F.tape_scenario(f"2026 tape event (worst {TAPE_WINDOW_BARS} H1 bars against "
                                 "each held side)", tape_moves, horizon_days=1.0,
                                 provenance="desks/mt5/data/universe/<symbol>_H1.parquet, 2026")]
    stress_out: dict[str, Any] = {}
    if sheet is not None and not b.over("stress"):
        for sc in scenarios:
            stress_out[sc.name] = F.stress(sheet, positions, terms, rates, sc)
    else:
        stress_out = {"status": UNMEASURED,
                      "why": "no balance sheet" if sheet is None else "budget exhausted"}

    # THE EVIDENCE VECTORS, PER SLEEVE AND FOR THE BOOK.
    roi_doc = _read_json(ROI_EVIDENCE)
    rejudge = _read_json(SWAP_REJUDGE)
    capacity = _read_json(CAPACITY)
    vectors, ev_meta = evidence_vectors(sleeve_rows, book, alloc if isinstance(alloc, dict)
                                        else {}, roi_doc, rejudge, terms, capacity)
    book_ev = AE.book_vector(vectors, book)
    gross = (_f((alloc.get("growth") or {}).get("mean_log_per_day"))
             if isinstance(alloc, dict) else None)
    fin_by_sleeve = {v.sleeve: v.financing_cost_r_per_day for v in vectors}
    after = F.after_financing_growth(gross, book, fin_by_sleeve)

    evidence_doc = {
        "at": now.isoformat(), "kind": "evidence", "producer": "research/financing_lab.py",
        "max_age_s": AE.MAX_AGE_S,
        "sleeves": {v.sleeve: v.as_dict() for v in vectors},
        "book": {**book_ev, "after_financing_growth": after},
        "terms": [{"name": s.name, "role": s.role, "priced_inside_allocator":
                   s.priced_inside_allocator, "where": s.where, "consumed_as": s.consumed_as}
                  for s in AE.TERM_SPECS],
        "consumer": {"reader": "research/pf_allocator.py apply_allocator_evidence",
                     "reads": ["lineage_factor", "financing_cost_r_per_day",
                               "financing_charged_in_replay"],
                     "how": ("a bounded, two-sided tilt of the posterior mean and a signed "
                             "financing level shift, both inside the E[log W] solve; neutral "
                             "when this file is absent or older than max_age_s")},
        "boundary": ("EVIDENCE ONLY. This file sets no fraction, no cap and no veto; it never "
                     "touches the 20% heat floor, the 0.02-lot gold floor or the daily-loss "
                     "parameters. A term the desk cannot measure reads 1.0."),
        "sources": ev_meta,
    }
    report = {
        "generated_utc": now.isoformat(), "elapsed_s": b.elapsed, "dry_run": dry_run,
        "account": {"currency": ccy, "source": acct["source"],
                    "leverage": _f(acct["leverage"]), "n_positions": len(positions)},
        "balance_sheet": sheet.as_dict() if sheet is not None else {"status": UNMEASURED},
        "cash_ladder": ladder, "funding_by_currency": funding,
        "settlement": settlement, "swap_curve_held": swap_curve, "swaps_paid": paid,
        "terms_source": terms_src, "prices_read": len(prices),
        "stress": stress_out, "tape_event_2026": tape_dates,
        "borrow": F.borrow(),
        # THE COUNTERPARTY LEG (the mandate's fourth friction beside funding, margin and
        # settlement): reported with its name on it, never charged into the posterior.
        "counterparty": F.counterparty(sheet, positions, venue=acct.get("server") or "",
                                       account_kind=acct.get("account_kind") or ""),
        "evidence": {"n_sleeves": len(vectors), "book": book_ev,
                     "after_financing_growth": after, **ev_meta},
        "unmeasured": unmeasured,
        "budget": {"budget_s": budget_s, "exhausted_at": b.exhausted_at},
        "law": ("LAWS 5m: the portfolio-capital allocator reads posterior edge x confidence x "
                "regime relevance x diversification x capacity x liquidity x execution "
                "quality x alpha half-life, less impact, financing stress, common hidden "
                "exposures, lineage concentration and tail risk -- as evidence, through its "
                "own E[log W] arithmetic, never as a cap (GROWTH_GOVERNANCE Rules 1 and 2)"),
    }
    if not dry_run:
        _atomic_write(OUT_EVIDENCE, evidence_doc)
        _atomic_write(OUT_REPORT, report)
    return {"evidence": evidence_doc, "report": report}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    out = run(budget_s=float(a.budget_s), dry_run=bool(a.dry_run))
    rep, ev = out["report"], out["evidence"]
    bs = rep["balance_sheet"]
    print(f"financing lab {rep['generated_utc']}: {rep['account']['n_positions']} position(s), "
          f"equity {bs.get('equity')} {rep['account']['currency']}, margin "
          f"{(bs.get('margin_used') or {}).get('status')}, swaps paid "
          f"{rep['swaps_paid'].get('total_account_ccy')} over {rep['swaps_paid'].get('n_deals')} "
          f"deal(s); {ev['book']['n_sleeves']} sleeve vector(s), lineage HHI "
          f"{ev['book']['lineage_hhi']}, after-financing "
          f"{ev['book']['after_financing_growth']['after_financing_log_per_day']}/day")
    st = rep["stress"]
    if isinstance(st, dict):
        for name, sc in st.items():
            if isinstance(sc, dict) and "pnl" in sc:
                print(f"  {name}: pnl {sc['pnl']} margin_call={sc['margin_call']} "
                      f"forced={sc['forced_deleveraging']['triggered']} [{sc['status']}]")
    for u in rep["unmeasured"][:8]:
        print(f"  UNMEASURED {u}")
    print("  dry run: nothing written" if a.dry_run
          else f"  wrote {OUT_EVIDENCE.name}, {OUT_REPORT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
