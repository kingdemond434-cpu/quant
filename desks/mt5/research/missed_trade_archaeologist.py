"""THE MISSED-TRADE ARCHAEOLOGIST (LAWS 5m): for every large adverse move, missed forward move,
bad exit and regime failure in the live and shadow ledgers, reconstruct the decision state AS IT
WAS and ask which absent dataset, feature, market relationship or mechanism would have changed
the decision -- without using the future.

THE ONE RULE, AND THE TWO CLOCKS IT SEPARATES. An episode is SELECTED by its outcome: the fill
lost more than a unit of risk, the vetoed bracket would have run two ATRs, the time-exit left a
trend on the table, the regime-tagged clock lost across its trades. Outcomes are the future, and
they are used for exactly one thing -- choosing which decisions to dig up. The RECONSTRUCTION
uses only bars that had CLOSED before the decision was taken (`completed_before`: a bar whose
hour had not ended when the decision was made is still forming and is excluded), so the state the
question is asked of is the state the desk could have had. The test plants a spike after the
decision and asserts the reconstruction does not move.

THE ANSWERS ARE FROZEN BEFORE THEY ARE TESTED. Each answer is a prospective hypothesis or a
`dataset_request`: a statement, the pre-decision state it was derived from, a content hash, and
`frozen_at`. Credit for a frozen hypothesis comes ONLY from evidence stamped after `frozen_at` --
forward observations, later fills, the next regime -- and NEVER from a backtest that recovers the
episode it was dug from. A hypothesis that could be credited for explaining the loss it was minted
on would be a hypothesis generator scoring itself on its own training set, which is the exact
failure the frozen stamp exists to make impossible. `retrospective_credit` is recorded as NONE on
every record so no downstream reader can miss it.

NOT EVERY MISSED TRADE IS A RESEARCH QUESTION. A bracket vetoed because the release identity
refused the venue was not missed for want of a dataset; it was missed for want of a gateway.
Those episodes are classed OPERATIONAL and reported by their veto reason, and no hypothesis is
minted from them -- minting one would launder a wiring defect into a research programme.

    python desks/mt5/research/missed_trade_archaeologist.py --once [--budget-s 600] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
REPORTS = DESK / "reports"
DECISIONS = DATA / "decision_ledger.jsonl"
LIVE = DATA / "live_ledger.jsonl"
SHADOW_DIR = REPORTS / "shadow"
UNIVERSE = DATA / "universe"
STATE = DATA / "missed_trade_archaeology.json"
OUT = REPORTS / "MISSED_TRADES.json"

UNMEASURED = "UNMEASURED"
BUDGET_S = 600.0
MAX_EPISODES = 60
ADVERSE_R = -1.0            # a fill that lost at least one unit of risk
MOVE_ATR = 2.0              # a "large" move: two ATR(14) inside the horizon
HORIZON_BARS = 8            # completed H1 bars after the decision the move is measured over
REGIME_MIN_TRADES = 3
STATE_TAIL = 400            # completed bars the state is computed on (every window is <= 121)
#: The share of the pass budget episode SELECTION may take; the rest reconstructs and writes.
SELECT_SHARE = 0.6
KINDS: tuple[str, ...] = ("large_adverse_move", "missed_forward_move", "bad_exit",
                          "regime_failure")
#: Veto reasons that name a wiring or venue defect: no dataset changes those decisions.
OPERATIONAL_REASONS: tuple[str, ...] = ("release_identity", "venue", "VENUE_UNAVAILABLE",
                                        "terminal", "not armed", "connection", "margin")
CREDIT_RULE = ("credit only for later unseen evidence: forward observations and fills stamped "
               "after frozen_at; retrospective backtest recovery of the episode earns nothing")


# --------------------------------------------------------------------------------- utilities
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now()).isoformat(timespec="seconds")


def _at(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _jsonl(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if not path.exists():
        return [], f"absent: {path}"
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError as exc:
        return [], f"unreadable: {exc}"
    return out, None


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        path.write_bytes(tmp.read_bytes())
        tmp.unlink(missing_ok=True)
    return path


def _sym(s: Any) -> str:
    return str(s or "").split(".")[0].strip()


# --------------------------------------------------------------------------------- bars
def load_bars(symbol: str, universe: Path = UNIVERSE) -> Any:
    """The symbol's H1 bars, or None with no exception: an absent file is UNMEASURED upstream."""
    p = universe / f"{_sym(symbol)}_H1.parquet"
    if not p.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(p)
    except Exception:
        return None
    if df is None or len(df) == 0 or "close" not in df.columns:
        return None
    idx = pd.to_datetime(df.index, utc=True)
    df = df.copy()
    df.index = idx
    return df.sort_index()


def completed_before(bars: Any, t: datetime, bar_hours: float = 1.0) -> Any:
    """Only the bars whose period had ENDED at `t`: an H1 bar stamped 10:00 covers 10:00-11:00 and
    is still forming at 10:35, so a decision at 10:35 may read the 09:00 bar and nothing later."""
    cutoff = t - timedelta(hours=bar_hours)
    return bars.loc[bars.index <= cutoff]


def _atr(df: Any, n: int = 14) -> float | None:
    """ATR over the last `n` completed bars, vectorised on exactly the n+1 rows it needs. The
    first version ran a Python-level `Series.combine` over the whole 50,000-bar history for
    every episode and the organ's first real pass never reached its own report inside 900 s."""
    if len(df) < n + 1:
        return None
    import numpy as np
    tail = df.tail(n + 1)
    high = tail["high"].to_numpy(dtype=float)
    low = tail["low"].to_numpy(dtype=float)
    close = tail["close"].to_numpy(dtype=float)
    prev = close[:-1]
    tr = np.maximum.reduce([high[1:] - low[1:], np.abs(high[1:] - prev), np.abs(low[1:] - prev)])
    v = float(tr.mean())
    return v if v == v and v > 0 else None


def reconstruct(bars: Any, t: datetime) -> dict[str, Any]:
    """The decision state at `t`, from completed bars only. Every field names its own window so a
    reader can see that nothing in it postdates the last completed bar."""
    df = completed_before(bars, t)
    if df is None or len(df) < 30:
        return {"status": UNMEASURED, "why": f"{0 if df is None else len(df)} completed bar(s) "
                                              f"before the decision; the state needs 30",
                "as_of": None, "decision_time": _iso(t)}
    n_completed = len(df)
    df = df.tail(STATE_TAIL)     # every window below is <= 121 bars; the rest is history
    close = df["close"]
    last = float(close.iloc[-1])
    atr = _atr(df)
    ret = close.pct_change().dropna()
    n = len(df)
    lo48 = float(df["low"].tail(48).min())
    hi48 = float(df["high"].tail(48).max())
    vol24 = float(ret.tail(24).std()) if len(ret) >= 24 else None
    vol120 = float(ret.tail(120).std()) if len(ret) >= 120 else None
    tv = df["tick_volume"] if "tick_volume" in df.columns else None
    tv_z = None
    if tv is not None and len(tv) >= 120:
        base = tv.tail(120)
        sd = float(base.std())
        tv_z = round((float(tv.tail(24).mean()) - float(base.mean())) / sd, 3) if sd > 0 else None
    mean120 = float(close.tail(120).mean()) if n >= 120 else float(close.mean())
    state = {
        "status": "MEASURED",
        "decision_time": _iso(t),
        "as_of": df.index[-1].isoformat(),
        "bars_used": n_completed,
        "close": last,
        "atr14": round(atr, 6) if atr else None,
        "ret_24h": round(last / float(close.iloc[-25]) - 1.0, 6) if n >= 25 else None,
        "ret_120h": round(last / float(close.iloc[-121]) - 1.0, 6) if n >= 121 else None,
        "range_pos_48": round((last - lo48) / (hi48 - lo48), 4) if hi48 > lo48 else None,
        "vol_ratio_24_120": (round(vol24 / vol120, 4) if vol24 and vol120 and vol120 > 0
                             else None),
        "tick_volume_z": tv_z,
        "spread": float(df["spread"].iloc[-1]) if "spread" in df.columns else None,
        "trend_120": round(last / mean120 - 1.0, 6) if mean120 else None,
        "hour_utc": t.astimezone(UTC).hour,
        "weekday": t.astimezone(UTC).weekday(),
        "windows": {"atr14": 14, "range_pos": 48, "vol_ratio": [24, 120], "trend": 120,
                    "tick_volume_z": [24, 120]},
    }
    sig_src = {k: state[k] for k in ("close", "atr14", "ret_24h", "range_pos_48",
                                     "vol_ratio_24_120", "tick_volume_z", "trend_120",
                                     "hour_utc", "weekday")}
    state["signature"] = hashlib.sha256(json.dumps(sig_src, sort_keys=True, default=str)
                                        .encode("utf-8")).hexdigest()[:16]
    return state


def outcome_after(bars: Any, t: datetime, side: int | None,
                  horizon: int = HORIZON_BARS) -> dict[str, Any]:
    """THE FUTURE, used for SELECTION only: the largest move in ATR units over the next `horizon`
    completed bars. Never fed to `reconstruct` and never into an answer."""
    before = completed_before(bars, t)
    atr = _atr(before) if len(before) >= 15 else None
    after = bars.loc[bars.index > t - timedelta(hours=1)].head(horizon)
    if atr is None or len(after) == 0:
        return {"status": UNMEASURED, "why": "no ATR before or no bars after the decision"}
    ref = float(before["close"].iloc[-1]) if len(before) else float(after["open"].iloc[0])
    up = (float(after["high"].max()) - ref) / atr
    dn = (ref - float(after["low"].min())) / atr
    if side == 0:      # long
        fav, adv = up, dn
    elif side == 1:    # short
        fav, adv = dn, up
    else:              # a bracket: either direction counts
        fav, adv = max(up, dn), min(up, dn)
    return {"status": "MEASURED", "bars": len(after), "up_atr": round(up, 3),
            "down_atr": round(dn, 3), "favourable_atr": round(fav, 3),
            "adverse_atr": round(adv, 3), "atr14": round(atr, 6)}


# --------------------------------------------------------------------------------- episodes
def _operational(reason: Any) -> bool:
    r = str(reason or "").lower()
    return any(k.lower() in r for k in OPERATIONAL_REASONS)


def _episode_id(kind: str, symbol: str, sleeve: str, t: datetime) -> str:
    return "ep_" + hashlib.sha256(f"{kind}|{symbol}|{sleeve}|{_iso(t)}".encode()).hexdigest()[:14]


def find_episodes(decisions: list[dict[str, Any]], live: list[dict[str, Any]],
                  shadow: dict[str, list[dict[str, Any]]],
                  bars_for: Any, deadline: float | None = None,
                  unmeasured: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Every episode the ledgers name, each with the outcome that selected it. `deadline` is a
    monotonic instant: the shadow scan stops there and says so, so a slow box still gets a
    report from every pass instead of the same truncated prefix every hour."""
    out: list[dict[str, Any]] = []
    notes = unmeasured if unmeasured is not None else []
    # decisions by sleeve, taken, for joining live fills to their decision time
    taken_by_sleeve: dict[str, list[tuple[datetime, dict[str, Any]]]] = defaultdict(list)
    for d in decisions:
        t = _at(d.get("decided_at") or d.get("time"))
        if t is None:
            continue
        if d.get("taken"):
            taken_by_sleeve[str(d.get("sleeve") or d.get("strategy_id") or "")].append((t, d))
    for rows in taken_by_sleeve.values():
        rows.sort(key=lambda x: x[0])

    # (a) live fills that lost a unit of risk or more
    for f in live:
        t_exit = _at(f.get("time"))
        r = f.get("r_multiple")
        risk = f.get("risk_quote")
        pl = f.get("pl_quote")
        loss_r = None
        if isinstance(r, (int, float)) and r != 0:
            loss_r = float(r)
        elif isinstance(risk, (int, float)) and risk < 0 and isinstance(pl, (int, float)):
            loss_r = float(pl) / abs(float(risk))
        if t_exit is None or loss_r is None or loss_r > ADVERSE_R:
            continue
        sleeve = str(f.get("sleeve") or "")
        sym = _sym(f.get("symbol"))
        joined = [d for (t, d) in taken_by_sleeve.get(sleeve, []) if t <= t_exit]
        if not joined:
            out.append({"kind": "large_adverse_move", "lane": "live", "symbol": sym,
                        "sleeve": sleeve, "decision_time": None, "outcome": {"r": loss_r},
                        "status": UNMEASURED,
                        "why": "no taken decision row joins this fill, so its decision time is "
                               "unknown and no state can be reconstructed"})
            continue
        t_dec, _d = joined[-1]
        out.append({"kind": "large_adverse_move", "lane": "live", "symbol": sym,
                    "sleeve": sleeve, "decision_time": t_dec,
                    "side": f.get("side"),
                    "outcome": {"r": round(loss_r, 3), "deal": f.get("deal")},
                    "status": "SELECTED"})

    # (b) decisions not taken whose bracket would have run
    for d in decisions:
        if d.get("taken"):
            continue
        t = _at(d.get("decided_at") or d.get("time"))
        sym = _sym(d.get("symbol"))
        if t is None or not sym:
            continue
        reason = d.get("veto_reason") or d.get("reason") or d.get("outcome")
        if _operational(reason):
            out.append({"kind": "missed_forward_move", "lane": "decision", "symbol": sym,
                        "sleeve": str(d.get("sleeve") or ""), "decision_time": t,
                        "status": "OPERATIONAL", "veto_reason": str(reason),
                        "why": "vetoed by a venue/wiring condition; no dataset changes it"})
            continue
        bars = bars_for(sym)
        if bars is None:
            out.append({"kind": "missed_forward_move", "lane": "decision", "symbol": sym,
                        "sleeve": str(d.get("sleeve") or ""), "decision_time": t,
                        "status": UNMEASURED, "why": f"no H1 bars for {sym}"})
            continue
        side = d.get("side")
        side_i = {"buy": 0, "sell": 1, 0: 0, 1: 1}.get(side if side in (0, 1)
                                                      else str(side).lower())
        oc = outcome_after(bars, t, side_i)
        if oc.get("status") == "MEASURED" and float(oc["favourable_atr"]) >= MOVE_ATR:
            out.append({"kind": "missed_forward_move", "lane": "decision", "symbol": sym,
                        "sleeve": str(d.get("sleeve") or ""), "decision_time": t,
                        "side": side_i, "veto_reason": str(reason), "outcome": oc,
                        "status": "SELECTED"})

    # (c)+(d) shadow ledgers: adverse rows, bad exits, regime failures
    regime_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for i, (clock, rows) in enumerate(sorted(shadow.items())):
        if deadline is not None and time.monotonic() > deadline:
            notes.append({"what": "shadow scan", "why": f"selection deadline reached after "
                                                          f"{i} of {len(shadow)} ledgers; the "
                                                          f"rest are scanned next pass"})
            break
        parts = clock.split(".")
        sym = _sym(parts[0])
        regime = parts[2] if len(parts) >= 3 else None
        bars = bars_for(sym)
        for r in rows:
            t_in = _at(r.get("entry_time"))
            t_out = _at(r.get("exit_time"))
            rm = r.get("r_multiple")
            if t_in is None or not isinstance(rm, (int, float)):
                continue
            if regime:
                regime_rows[clock].append({"r": float(rm), "t": t_in, "symbol": sym})
            if float(rm) <= ADVERSE_R:
                out.append({"kind": "large_adverse_move", "lane": "shadow", "symbol": sym,
                            "sleeve": clock, "decision_time": t_in, "side": r.get("side"),
                            "outcome": {"r": round(float(rm), 3), "reason": r.get("reason")},
                            "status": "SELECTED"})
            if bars is None or t_out is None:
                continue
            reason = str(r.get("reason") or "")
            side = r.get("side") if r.get("side") in (0, 1) else None
            oc = outcome_after(bars, t_out, side)
            if oc.get("status") != "MEASURED":
                continue
            if reason == "ttl" and float(oc["favourable_atr"]) >= MOVE_ATR:
                out.append({"kind": "bad_exit", "lane": "shadow", "symbol": sym, "sleeve": clock,
                            "decision_time": t_in, "exit_time": t_out, "side": side,
                            "exit_reason": reason, "outcome": oc, "status": "SELECTED",
                            "sub_kind": "time_exit_left_trend"})
            elif reason == "sl" and float(oc["favourable_atr"]) >= MOVE_ATR:
                out.append({"kind": "bad_exit", "lane": "shadow", "symbol": sym, "sleeve": clock,
                            "decision_time": t_in, "exit_time": t_out, "side": side,
                            "exit_reason": reason, "outcome": oc, "status": "SELECTED",
                            "sub_kind": "stopped_then_reversed"})
    for clock, rs in regime_rows.items():
        if len(rs) < REGIME_MIN_TRADES:
            continue
        mean_r = sum(x["r"] for x in rs) / len(rs)
        if mean_r < 0:
            last = max(rs, key=lambda x: x["t"])
            out.append({"kind": "regime_failure", "lane": "shadow", "symbol": last["symbol"],
                        "sleeve": clock, "decision_time": last["t"],
                        "regime": clock.split(".")[2],
                        "outcome": {"n": len(rs), "mean_r": round(mean_r, 3)},
                        "status": "SELECTED"})
    return out


# --------------------------------------------------------------------------------- answers
def answers(kind: str, state: dict[str, Any], ep: dict[str, Any]) -> list[dict[str, Any]]:
    """Which ABSENT input would have changed the decision -- derived from the pre-decision state
    and the episode's class only. `absent` is one of dataset | feature | relationship |
    mechanism, the four the law names."""
    out: list[dict[str, Any]] = []
    if state.get("status") != "MEASURED":
        return out
    vr = state.get("vol_ratio_24_120")
    tvz = state.get("tick_volume_z")
    trend = state.get("trend_120")
    rp = state.get("range_pos_48")
    sym = str(ep.get("symbol") or "")
    if kind == "large_adverse_move":
        if isinstance(vr, (int, float)) and vr > 1.3:
            out.append({"absent": "feature", "what": "realised-vol regime at decision "
                                                     f"(24h/120h vol ratio {vr})",
                        "why": "the decision carried no volatility-regime conditioning and was "
                               "taken into an expanding-vol state"})
        if isinstance(tvz, (int, float)) and tvz < -0.5:
            out.append({"absent": "dataset", "what": "order-flow / tape at the decision bar",
                        "why": f"tick volume was thin (z {tvz}); a tape feature would have "
                               f"read the break as unsupported"})
        out.append({"absent": "relationship",
                    "what": ("cross-asset state for " + sym + " (DXY, US real yields)"
                             if sym.startswith("XAU") else
                             f"cross-asset state for {sym} (risk proxy, rate differential)"),
                    "why": "no cross-asset relationship entered the decision"})
        out.append({"absent": "mechanism", "what": "scheduled-event proximity inside the hold",
                    "why": "an event clock (forced_flow_calendar) was not consulted"})
    elif kind == "missed_forward_move":
        out.append({"absent": "feature", "what": f"range position {rp} and trend {trend} as "
                                                 f"conditioning for the vetoed bracket",
                    "why": "the veto reason named no state; the state was directional"})
        out.append({"absent": "dataset", "what": "session-open order flow",
                    "why": "a flow read at the open would have priced the veto"})
    elif kind == "bad_exit":
        if ep.get("sub_kind") == "time_exit_left_trend":
            out.append({"absent": "mechanism", "what": "trend-persistence exit: condition the "
                                                       f"time exit on trend_120 sign ({trend})",
                        "why": "the time exit ignored a persisting trend"})
        else:
            out.append({"absent": "feature", "what": "stop distance in ATR14 units "
                                                     f"(atr14 {state.get('atr14')})",
                        "why": "the stop sat inside the noise the ATR measures"})
    elif kind == "regime_failure":
        out.append({"absent": "relationship", "what": f"regime label {ep.get('regime')} versus "
                                                      f"cross-asset state",
                    "why": "the regime tag lost across its trades; the label and the world "
                           "disagreed"})
        out.append({"absent": "dataset", "what": "regime source freshness (state_vector age)",
                    "why": "a stale regime read is indistinguishable from a wrong one"})
    return out


def freeze(ep: dict[str, Any], state: dict[str, Any], ans: dict[str, Any],
           frozen_at: datetime | None = None) -> dict[str, Any]:
    """A prospective hypothesis or dataset_request, frozen: content-hashed over the episode's
    class, symbol, the answer and the pre-decision state signature. Re-freezing the same answer
    on the same state yields the same id."""
    kind = "dataset_request" if ans["absent"] == "dataset" else "prospective_hypothesis"
    src = {"episode_kind": ep["kind"], "symbol": ep.get("symbol"), "absent": ans["absent"],
           "what": ans["what"], "state_signature": state.get("signature")}
    hid = "mta_" + hashlib.sha256(json.dumps(src, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    t = frozen_at or _now()
    return {
        "hypothesis_id": hid, "kind": kind, "frozen_at": _iso(t),
        "statement": (f"{ans['absent']} absent at the decision: {ans['what']} -- "
                      f"{ans['why']}"),
        "episode_kind": ep["kind"], "symbol": ep.get("symbol"), "sleeve": ep.get("sleeve"),
        "decision_time": _iso(ep["decision_time"]) if isinstance(ep.get("decision_time"),
                                                                 datetime) else None,
        "state": state, "absent": ans["absent"], "what": ans["what"], "why": ans["why"],
        "credit_rule": CREDIT_RULE, "evaluation_start": _iso(t),
        "retrospective_credit": "NONE",
        "pit_requirements": ["features computed from bars closed before the decision bar",
                             "credit from observations stamped after frozen_at only"],
    }


def _register(h: dict[str, Any]) -> tuple[str | None, str]:
    try:
        from libs.moat import registry as reg
        did, created = reg.record_discovery(
            source_id="missed_trade_archaeologist", source_type=str(h["kind"]),
            mechanism=str(h["statement"])[:400], origin="DESK",
            generator="missed_trade_archaeologist", discovery_id=str(h["hypothesis_id"]),
            kind=str(h["kind"]), assets=[h.get("symbol")] if h.get("symbol") else [],
            economic_rationale=str(h["why"]), novelty=0.8, confidence=0.3,
            required_data=[h["what"]] if h["absent"] == "dataset" else [],
            PIT_requirements=h["pit_requirements"],
            falsifier=("forward observations after frozen_at show the conditioning does not "
                       "change the sleeve's realised R"),
            payload=h)
        return did, "created" if created else "existing"
    except Exception as exc:
        return None, f"registry unavailable: {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------------- the pass
def load_shadow(shadow_dir: Path = SHADOW_DIR) -> tuple[dict[str, list[dict[str, Any]]],
                                                        str | None]:
    if not shadow_dir.exists():
        return {}, f"absent: {shadow_dir}"
    out: dict[str, list[dict[str, Any]]] = {}
    for p in sorted(shadow_dir.glob("ledger_*.json")):
        rows = _read(p)
        if isinstance(rows, list):
            name = p.stem[len("ledger_"):]
            # ledger_XAUUSD_asia -> XAUUSD.asia ; regime-tagged clocks keep their third part
            bits = name.split("_", 1)
            clock = bits[0] + ("." + bits[1].replace("_", ".", 1) if len(bits) > 1 else "")
            out[clock] = [r for r in rows if isinstance(r, dict)]
    return out, None if out else "no ledger_*.json under the shadow directory"


def run(*, budget_s: float = BUDGET_S, dry_run: bool = False,
        max_episodes: int = MAX_EPISODES) -> dict[str, Any]:
    t0 = time.monotonic()
    now = _now()
    unmeasured: list[dict[str, str]] = []
    decisions, d_why = _jsonl(DECISIONS)
    if d_why:
        unmeasured.append({"what": "decision ledger", "why": d_why})
    live, l_why = _jsonl(LIVE)
    if l_why:
        unmeasured.append({"what": "live ledger", "why": l_why})
    shadow, s_why = load_shadow(SHADOW_DIR)
    if s_why:
        unmeasured.append({"what": "shadow ledgers", "why": s_why})
    state_doc = _read(STATE) or {}
    processed: dict[str, Any] = (state_doc.get("processed")
                                 if isinstance(state_doc.get("processed"), dict) else {})
    cache: dict[str, Any] = {}

    def bars_for(sym: str) -> Any:
        if sym not in cache:
            cache[sym] = load_bars(sym, UNIVERSE)
            if cache[sym] is None:
                unmeasured.append({"what": f"bars {sym}", "why": "no readable H1 parquet"})
        return cache[sym]

    episodes = find_episodes(decisions, live, shadow, bars_for,
                             deadline=t0 + budget_s * SELECT_SHARE, unmeasured=unmeasured)
    counts = {k: sum(1 for e in episodes if e["kind"] == k) for k in KINDS}
    by_status = {s: sum(1 for e in episodes if e["status"] == s)
                 for s in ("SELECTED", "OPERATIONAL", UNMEASURED)}
    hypotheses: list[dict[str, Any]] = []
    dug: list[dict[str, Any]] = []
    operational: list[dict[str, Any]] = []
    n_new = 0
    for ep in episodes:
        if time.monotonic() - t0 > budget_s:
            unmeasured.append({"what": "episodes", "why": f"budget {budget_s}s reached after "
                                                            f"{len(dug)} reconstruction(s)"})
            break
        t = ep.get("decision_time")
        eid = _episode_id(ep["kind"], ep["symbol"], str(ep.get("sleeve")),
                          t if isinstance(t, datetime) else now)
        ep["episode_id"] = eid
        if ep["status"] == "OPERATIONAL":
            operational.append({k: v for k, v in ep.items() if k != "decision_time"}
                               | {"decision_time": _iso(t) if isinstance(t, datetime) else None})
            continue
        if ep["status"] != "SELECTED" or not isinstance(t, datetime):
            continue
        if eid in processed:
            continue
        if n_new >= max_episodes:
            break
        n_new += 1
        bars = bars_for(ep["symbol"])
        state = (reconstruct(bars, t) if bars is not None else
                 {"status": UNMEASURED, "why": f"no bars for {ep['symbol']}"})
        ans = answers(ep["kind"], state, ep)
        frozen = [freeze(ep, state, a, now) for a in ans]
        if not dry_run:
            for h in frozen:
                h["discovery_id"], h["registry"] = _register(h)
        row = {**{k: v for k, v in ep.items() if k != "decision_time"},
               "decision_time": _iso(t), "state": state,
               "hypotheses": [h["hypothesis_id"] for h in frozen]}
        dug.append(row)
        hypotheses.extend(frozen)
        processed[eid] = {"at": _iso(now), "kind": ep["kind"],
                          "hypotheses": [h["hypothesis_id"] for h in frozen]}
    doc = {
        "at": _iso(now), "budget_s": budget_s, "elapsed_s": round(time.monotonic() - t0, 2),
        "dry_run": dry_run,
        "law": "LAWS 5m -- the Missed-Trade Archaeologist",
        "rule": ("outcomes select the episode; the reconstruction reads only bars that had "
                 "closed before the decision; every answer is frozen before it is tested and "
                 "credited only by later unseen evidence"),
        "episodes": {"found": len(episodes), "by_kind": counts, "by_status": by_status,
                     "dug_this_pass": len(dug), "processed_total": len(processed)},
        "dug": dug, "hypotheses": hypotheses, "operational": operational[:40],
        "n_operational": len(operational),
        "credit_rule": CREDIT_RULE,
        "consumers": ["libs/moat/registry.py discoveries (source_type dataset_request / "
                      "prospective_hypothesis) -> discovery_compiler",
                      "desks/mt5/research/meta_controller.py (acquire_dataset actions)"],
        "unmeasured": unmeasured,
    }
    if not dry_run:
        _atomic_write(STATE, {"at": _iso(now), "processed": processed})
        _atomic_write(OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-episodes", type=int, default=MAX_EPISODES)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, dry_run=a.dry_run, max_episodes=a.max_episodes)
    e = doc["episodes"]
    print(f"missed trades: {e['found']} episode(s) {e['by_kind']}; {e['by_status']}; dug "
          f"{e['dug_this_pass']}, {len(doc['hypotheses'])} frozen hypothesis/request(s), "
          f"{doc['n_operational']} operational"
          + ("; DRY RUN, nothing written" if a.dry_run else f" -> {OUT}"))
    for u in doc["unmeasured"][:8]:
        print(f"  UNMEASURED {u['what']}: {u['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
