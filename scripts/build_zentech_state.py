"""Build the read-only DESK view state from canonical MT5 artifacts.

Output: web/desk_state.json, consumed by web/desk.html. (Filename kept as
build_zentech_state.py because daily_cycle, the desk-box scheduled task and the
moneypath fence all reference it by path; the ZENTECH branding it was named for
is retired.)
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "web" / "desk_state.json"


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _number(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value)
            if math.isfinite(value):
                return value
    return None


def _find(data: dict[str, Any], *names: str) -> Any:
    wanted = {name.casefold() for name in names}
    stack: list[Any] = [data]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if str(key).casefold() in wanted:
                    return value
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        return None


def _ledger() -> list[dict[str, Any]]:
    path = DESK / "data" / "live_ledger.jsonl"
    try:
        return [json.loads(line) for line in path.read_text("utf-8").splitlines()
                if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _series(rows: list[dict[str, Any]], starting: float | None) -> list[float]:
    if starting is None:
        return []
    values = [starting]
    for row in rows:
        pnl = _number(row.get("profit"), row.get("net_pnl"), row.get("pnl"))
        if pnl is not None:
            values.append(values[-1] + pnl)
    return values[-180:]


def _shadow_rows() -> list[dict[str, Any]]:
    combined: list[tuple[str, dict[str, Any]]] = []
    for path in (DESK / "reports" / "shadow" / "shadow_state.json",
                 DESK / "reports" / "shadow" / "qquant_shadow_state.json"):
        for key, row in _read(path).items():
            if isinstance(row, dict) and "status" in row:
                combined.append((key, row))
    output = []
    for key, row in combined:
        n = int(_number(row.get("n")) or 0)
        exp = _number(row.get("exp_r"))
        cum_r = _number(row.get("cum_r"))
        # User-facing profitable list is literal: unknown and non-positive rows are excluded.
        if exp is None or exp <= 0:
            continue
        roll = _number(row.get("roll20_exp"))
        decay = None if roll is None or exp == 0 else roll / exp
        output.append({
            "name": key, "status": row.get("status"), "trades": n,
            "expectancy_r": exp, "cum_r": cum_r, "max_dd_r": _number(row.get("max_dd_r")),
            "days": int(_number(row.get("days_active")) or 0), "source": row.get("bar_source"),
            "decay_ratio": decay, "promotion_authority": row.get("promotion_authority") is True,
        })
    return sorted(output, key=lambda row: row["expectancy_r"], reverse=True)


def _is_terminal(status) -> bool:
    """A clock is stopped if its status is terminal -- matched by PREFIX, not exact string.

    2026-08-26: the reconciler introduced RETIRED_ORPHAN / RETIRED_GATE_FAIL /
    RETIRED_UNRECONSTRUCTIBLE. Every consumer tested `status in {"RETIRED", ...}`, so 31 retired
    rows kept counting as live forward clocks on the dashboard -- a retirement that does not
    propagate is a rename, not a retirement.
    """
    s = str(status or "").upper()
    return s.startswith(("RETIRED", "KILL", "QUARANTIN", "DEAD", "REJECT")) or s == "PROMOTED"


def _equity_history(equity: float | None, now: datetime) -> list[dict[str, Any]]:
    """Persist a 24/7 sampled equity tape so the curve exists from day one.

    The ledger-derived curve needs closed trades; a young live book has none, so the panel said
    UNMEASURED forever. Every build with a measured equity appends one sample here (deduped to
    >=60s spacing); the curve then shows the real account line at the builder's cadence.
    """
    path = OUT.parent / "equity_history.jsonl"
    rows: list[dict[str, Any]] = []
    try:
        rows = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    except (OSError, json.JSONDecodeError):
        rows = []
    if equity is not None:
        last = _timestamp(rows[-1].get("at")) if rows else None
        if last is None or (now - last).total_seconds() >= 60:
            rows.append({"at": now.isoformat(), "equity": equity})
            rows = rows[-40000:]
            with suppress(OSError):
                path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    return rows


def _ledger_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Win rate / Sharpe / R drawdown from closed live trades. Empty ledger -> UNMEASURED."""
    rs, by_day = [], {}
    for row in rows:
        r = _number(row.get("r_multiple"))
        pnl = _number(row.get("profit"), row.get("net_pnl"), row.get("pnl"))
        if r is not None:
            rs.append(r)
        ts = _timestamp(row.get("time"))
        if ts is not None and pnl is not None:
            by_day[ts.date().isoformat()] = by_day.get(ts.date().isoformat(), 0.0) + pnl
    out: dict[str, Any] = {"closed_trades": len(rs), "win_rate": None, "sharpe_daily": None,
                           "max_dd_r": None, "current_dd_r": None,
                           "daily_pnl": sorted(by_day.items())[-14:]}
    if rs:
        out["win_rate"] = round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1)
        cum = peak = dd = cur = 0.0
        for r in rs:
            cum += r
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
            cur = cum - peak
        out["max_dd_r"], out["current_dd_r"] = round(dd, 2), round(cur, 2)
    daily_vals = [v for _, v in sorted(by_day.items())]
    if len(daily_vals) >= 5:
        mean = sum(daily_vals) / len(daily_vals)
        var = sum((x - mean) ** 2 for x in daily_vals) / (len(daily_vals) - 1)
        if var > 0:
            out["sharpe_daily"] = round(mean / var ** 0.5 * (252 ** 0.5), 2)
    return out


def _funnel(universal: dict[str, Any]) -> dict[str, Any]:
    """Stage counts for the ONE pipeline: discovered -> backtested -> certified -> forward -> live."""
    hyp = None
    for cand in (DESK / "data" / "hypotheses" / "external_backtest_results.json",
                 ROOT / "desks" / "mt5" / "data" / "hypotheses" / "external_backtest_results.json"):
        rows = None
        try:
            rows = json.loads(cand.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(rows, list):
            hyp = len(rows)
            break
    forward, promo_ready, live_rows = [], 0, {}
    for path in (DESK / "reports" / "shadow" / "shadow_state.json",
                 DESK / "reports" / "shadow" / "qquant_shadow_state.json",
                 DESK / "reports" / "shadow" / "scalp_shadow_state.json"):
        data = _read(path)
        for key, row in list(data.items()) + list((data.get("sleeves") or {}).items() if isinstance(data.get("sleeves"), dict) else []):
            if not isinstance(row, dict) or "status" not in row:
                continue
            status = str(row.get("status") or "").upper()
            if _is_terminal(status):
                continue
            days = int(_number(row.get("days_active")) or 0)
            forward.append({"name": key, "days": days, "of": 14,
                            "n": int(_number(row.get("n")) or 0),
                            # Shown beside the forward count, never added to it: an observation
                            # that predates the frozen clock is evidence about a different
                            # question and may not satisfy a forward threshold.
                            "n_historical": int(_number(row.get("n_historical")) or 0),
                            "sleeve_id": row.get("sleeve_id"),
                            "t": _number(row.get("forward_t")),
                            "exp_r": _number(row.get("exp_r")),
                            "status": status})
            if status == "PROMOTION CANDIDATE":
                promo_ready += 1
    sleeves_doc = _read(DESK / "data" / "sleeves.json")
    live_rows = sleeves_doc.get("sleeves") if isinstance(sleeves_doc.get("sleeves"), dict) else (
        sleeves_doc if isinstance(sleeves_doc, dict) else {})
    live_rows = {k: v for k, v in (live_rows or {}).items() if isinstance(v, dict)}
    forward_obs = sum(r["n"] for r in forward)
    hist_obs = sum(r.get("n_historical", 0) for r in forward)
    # WHY CERTIFIED != CLOCKS. A certificate with no `params` cannot be executed -- there is no
    # parameterisation to run -- so it never becomes a clock. Six of the desk's certificates are
    # in that state (the five original external.* rows plus AUDNZD, which runs in the qquant lane
    # under its own spec). Showing only the two totals makes that look like sleeves are going
    # missing; naming the gap turns a mystery into a work item.
    certs = (_read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json") or {}).get("survivors") or {}
    unrunnable = [k for k, v in certs.items()
                  if not ((v.get("shadow_spec") or {}).get("params"))]
    return {
        "certificates_unrunnable": len(unrunnable),
        "unrunnable_reason": ("no `params` in shadow_spec -- nothing to execute. Re-certify "
                              "through the current gauntlet, which records the parameterisation "
                              "it tested."),
        "unrunnable_examples": sorted(unrunnable)[:6],
        "forward_observations": forward_obs,
        "historical_observations": hist_obs,
        "discovered_backtested": hyp,
        "certified": universal.get("n"),
        "forward_clocks": len(forward),
        "promotion_ready": promo_ready,
        "live": len(live_rows),
        "forward_detail": sorted(forward, key=lambda r: -r["days"])[:40],
    }


def _mt5_snapshot() -> dict[str, Any]:
    """Live account read straight from the terminal, when this box has one.

    The file-based account_state lags its writer's cadence, so the dashboard sat on STALE for
    most of every hour. On the desk box the terminal is right here; on the research box the
    import fails and the file path below carries on unchanged (absence is a fallback, never an
    error). today_pnl is the sum of today's closed deal profits plus floating -- the number the
    principal means by "today's gain".
    """
    try:
        import MetaTrader5 as mt5  # type: ignore[import-not-found, import-untyped]
        if mt5.terminal_info() is None and not mt5.initialize():
            return {}
        info = mt5.account_info()
        if info is None:
            return {}
        now = datetime.now(UTC)
        day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
        closed = 0.0
        deals = mt5.history_deals_get(day0, now)
        for d in deals or ():
            closed += float(getattr(d, "profit", 0.0) or 0.0)
            closed += float(getattr(d, "commission", 0.0) or 0.0)
            closed += float(getattr(d, "swap", 0.0) or 0.0)
        return {
            "server": getattr(info, "server", None), "currency": getattr(info, "currency", None),
            "balance": float(info.balance), "equity": float(info.equity),
            "profit": float(info.profit), "margin": float(info.margin),
            "margin_free": float(info.margin_free),
            "today_pnl": round(closed + float(info.profit), 2),
            "updated_at": now.isoformat(),
        }
    except Exception:
        return {}


def build() -> dict[str, Any]:
    gateway = _read(DESK / "data" / "gateway_state.json")
    account = _mt5_snapshot() or _read(DESK / "data" / "account_state.json") or gateway
    qquant = _read(DESK / "reports" / "QQUANT_GATES.json")
    universal = _read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
    markout = _read(DESK / "reports" / "markout.json")
    midnight = _read(ROOT / "data" / "intelligence" / "mt5_midnight_state.json")
    daily = _read(DESK / "data" / "daily_cycle_state.json")
    rows = _ledger()
    balance = _number(_find(account, "balance", "account_balance"))
    equity = _number(_find(account, "equity", "account_equity"))
    start = _number(_find(account, "starting_capital", "initial_balance"), balance)
    profitable = _shadow_rows()
    passes = [row for row in qquant.get("verdicts", [])
              if isinstance(row, dict) and row.get("passed") is True]
    candidates = []
    for row in passes:
        stages = row.get("stages", {})
        candidates.append({
            "name": row.get("id"), "hunt": row.get("hunt"), "days": row.get("days"),
            "dsr": _number(stages.get("deflated_sharpe", {}).get("dsr")),
            "wf_sharpe": _number(stages.get("walk_forward", {}).get("oos_sharpe")),
            "pbo": _number(stages.get("pbo", {}).get("pbo")),
            "spa_p": _number(stages.get("reality_check_spa", {}).get("p_value")),
        })
    freshest = []
    for path in (DESK / "data" / "universe").glob("*_H1.parquet"):
        freshest.append(path.stat().st_mtime)
    newest_bar_file = (datetime.fromtimestamp(max(freshest), UTC).isoformat()
                       if freshest else None)
    now = datetime.now(UTC)
    account_at = _timestamp(_find(account, "updated_at", "timestamp", "at", "fetched_at"))
    account_age = None if account_at is None else (now - account_at).total_seconds()
    live_state = "LIVE" if equity is not None and account_age is not None and account_age <= 120 else (
        "STALE" if equity is not None else "UNMEASURED"
    )
    payload = {
        "generated_at": now.isoformat(),
        "identity": {"name": "QUANT DESK", "caption": "AUTONOMOUS MULTI-ASSET MT5 RESEARCH DESK"},
        "account": {
            "venue": _find(account, "server", "broker") or "UNMEASURED",
            "currency": _find(account, "currency") or "UNMEASURED",
            "balance": balance, "equity": equity, "starting_capital": start,
            "today_pnl": _number(_find(account, "today_pnl", "daily_pnl")),
            "open_pnl": _number(_find(account, "profit", "floating_pnl", "open_pnl")),
            "margin": _number(_find(account, "margin")),
            "free_margin": _number(_find(account, "margin_free", "free_margin")),
            "growth_pct": None if start in (None, 0) or equity is None else 100 * (equity / start - 1),
            "source_updated_at": None if account_at is None else account_at.isoformat(),
            "source_age_seconds": account_age,
        },
        "research": {
            "candidates_tested": qquant.get("survivors_total"),
            "historical_survivors": qquant.get("survivors_passing_all"),
            "canonical_survivors": universal.get("n"),
            "gate_failures": qquant.get("gate_fails", {}),
            "survivors": candidates,
        },
        "shadow": {"profitable": profitable, "profitable_count": len(profitable)},
        "execution": {
            "markout_usable": markout.get("usable") is True,
            "matched_fills": markout.get("n_matched"), "why": markout.get("why"),
            "open_trades": _find(gateway, "open_positions", "positions") or [],
        },
        "health": {
            "newest_h1_file": newest_bar_file, "midnight": midnight,
            "daily_cycle": daily, "status": live_state,
        },
        "equity_curve": _series(rows, start),
        "disclaimer": "Research and operator telemetry only. Missing values are UNMEASURED; shadow has zero order authority.",
    }
    # -- principal 2026-08-26 additions: stats, funnel, live decay, sampled equity ------------
    # READINESS IS THE HEADLINE. A dashboard that shows equity and sleeve counts without saying
    # what size is actually EARNED invites the reader to supply their own answer.
    # MOAT COVERAGE, PUBLISHED WHERE THE TAPE LIVES. The tick tape exists only on the desk box,
    # so when mined_ground runs on the research box the moat contributed ZERO -- the desk's one
    # proprietary pointer silently uncounted, which is the WS-005 shape again. This builder runs
    # ON the tape's box every 5 minutes, so it publishes a tiny summary the pull carries over.
    try:
        from datetime import timedelta as _td
        _tape = DESK / "data" / "tape" / "ticks"
        _cut = now - _td(days=7)
        _cov = {}
        _newest = None
        if _tape.exists():
            for _d in _tape.iterdir():
                if _d.is_dir():
                    _days = 0
                    for f in _d.glob("*.parquet"):
                        _mt = datetime.fromtimestamp(f.stat().st_mtime, UTC)
                        if _mt >= _cut:
                            _days += 1
                        if _newest is None or _mt > _newest:
                            _newest = _mt
                    if _days:
                        _cov[_d.name.upper()] = _days
        # newest_tape_write is THE liveness signal: coverage day-counts stay green for a week
        # after the recorder dies (measured 2026-08-27 -- recorder dead 9h, coverage fresh),
        # so the health fence needs the raw newest write, not a windowed summary of it.
        (DESK / "data" / "moat_coverage.json").write_text(
            json.dumps({"built_at": now.isoformat(timespec="seconds"),
                        "window_days": 7, "coverage": _cov,
                        "newest_tape_write": (_newest.isoformat(timespec="seconds")
                                              if _newest else None)}, indent=1), "utf-8")
    except Exception:
        pass
    # The stall watchdog's latest verdict travels to the dashboard: healing nobody can see
    # is healing nobody can trust (principal 2026-08-27: "nothing should ever be stalled,
    # I won't be here to tell you").
    payload["stall_watch"] = _read(DESK / "data" / "stall_watch.json") or {
        "status": "UNMEASURED", "note": "watchdog has not reported yet"}
    # The stall watchdog's latest verdict travels with the state so the dashboard can show
    # healing as it happens -- healing nobody can see is healing nobody can trust.
    payload["stall_watch"] = _read(DESK / "data" / "stall_watch.json")
    payload["readiness"] = _read(ROOT / "data" / "live_readiness.json") or {
        "status": "UNMEASURED", "blocking": ["readiness has not been assessed"]}
    payload["breadth"] = _read(ROOT / "data" / "miner_conversion.json") or {}
    payload["stats"] = _ledger_stats(rows)
    payload["stats"]["today_pnl"] = payload["account"]["today_pnl"]
    payload["pipeline"] = _funnel(universal)
    decay = _read(DESK / "data" / "decay_live.json")
    payload["decay"] = {
        "checked_at": decay.get("checked_at"), "live_sleeves": decay.get("live_sleeves"),
        "verdicts": decay.get("verdicts") or {}, "actions": decay.get("actions_taken") or [],
    }
    history = _equity_history(equity, now)
    if len(payload["equity_curve"]) < 2 and len(history) >= 2:
        payload["equity_curve"] = [r["equity"] for r in history][-500:]
        payload["equity_curve_source"] = "sampled_account_equity"
    return payload


def main() -> int:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".zentech_state.", dir=OUT.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        os.replace(name, OUT)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)
    print(f"ZENTECH state: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
