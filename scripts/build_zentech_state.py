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
import sys
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
            "days": int(_number(row.get("days_active"), row.get("days")) or 0),
            "source": row.get("bar_source"),
            "decay_ratio": decay, "promotion_authority": row.get("promotion_authority") is True,
        })
    return sorted(output, key=lambda row: row["expectancy_r"], reverse=True)


def _norm_status(status) -> str:
    """A lane's status, with the separator normalised, because the separator is not the meaning.

    THE BUG THIS ENDS, measured 2026-09-05 and it hid an entire lane. Three lanes write a
    promotion verdict and they do not agree on one character:

        shadow_forward.py    "PROMOTION CANDIDATE"    (space)
        scalp_shadow.py      "PROMOTION_CANDIDATE"    (underscore)
        qquant_shadow.py     "PROMOTION_CANDIDATE"    (underscore)

    The promotion counter below tested `status == "PROMOTION CANDIDATE"` -- the space form only --
    so every candidate the SCALP and QQUANT lanes ever produced was invisible to it. The dashboard
    reported `promotion_ready: 0` while the promoter, which matches the underscore form correctly,
    was looking at the same rows and seeing candidates. The principal was told repeatedly that
    nothing was promotable by a tile that could not see two of the three lanes.

    Same class as `_is_terminal` directly below, whose docstring records the same lesson about
    exact-string matching one rename later: a verdict that does not propagate is a rename, not a
    verdict. Normalising on READ is the fix that survives the next lane, because the next lane
    will also pick its own separator and no reader should have to know which.
    """
    return " ".join(str(status or "").upper().replace("_", " ").split())


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


def _funnel_docket() -> int | None:
    try:
        rows = json.loads((DESK / "data" / "hypotheses" / "external_survivors.json")
                          .read_text("utf-8"))
        return len(rows) if isinstance(rows, list) else None
    except (OSError, json.JSONDecodeError):
        return None


def _gate_stat(key: str) -> int | None:
    doc = _read(DESK / "reports" / "universal_gates_external.json")
    v = doc.get(key)
    return int(v) if isinstance(v, (int, float)) else None


def _certificate_census(certs: dict[str, Any]) -> dict[str, Any]:
    """Split the survivors file into ten-gate passes, gate failures and unrunnable certificates.

    IMPORTED, NEVER RE-IMPLEMENTED. `all_ten_pass` is the same predicate
    `shadow_admission.authorized_runs` uses to decide what may enrol, and the whole point of this
    function is to make the dashboard agree with that door. A local re-spelling of "all ten
    passed" is a second judge, and this desk has already paid for two builders of one identity
    (`run_key` reported 34 of 35 certificates clockless while every one was running). If the
    import fails the census refuses -- `basis` says so and the caller keeps the old number --
    because a census that silently degrades to "everything counts" is the defect it exists to fix.

    THREE POPULATIONS, and they are not nested the way the old count assumed:

        gate_failed   in the file, `all_ten_pass` False -- NOT a certificate, never was
        unrunnable    passed all ten, `shadow_spec.params` absent -- a certificate nothing can run
        certified     passed all ten -- the number the funnel means by "certified"

    `unrunnable` is a SUBSET of `certified`, not a sibling: those rows earned their certificate
    and cannot be executed, which is a publication defect worth its own line. `params == {}` is
    NOT unrunnable -- it is the complete parameterisation "family defaults", byte-exactly what the
    gauntlet ran, and excluding it has already held overnight_gap_decay certificates off their
    clocks twice (2026-08-27, and again here where 13 were reported unrunnable against 6 real).
    """
    try:
        sys.path.insert(0, str(DESK / "research"))
        from gate_policy import all_ten_pass          # type: ignore[import-not-found]
    except Exception as exc:                          # noqa: BLE001 - reported, never guessed
        return {"basis": f"UNAVAILABLE ({type(exc).__name__}: {exc})", "certified": None,
                "gate_failed": None, "gate_failed_names": [], "unrunnable_names": []}
    passed, failed = [], []
    for key, row in certs.items():
        if isinstance(row, dict) and all_ten_pass(row.get("gates")):
            passed.append(key)
        else:
            failed.append(key)
    unrunnable = [k for k in passed
                  if (certs[k].get("shadow_spec") or {}).get("params") is None]
    return {"basis": "ten_gate_verdict", "certified": len(passed),
            "gate_failed": len(failed), "gate_failed_names": sorted(failed),
            "unrunnable_names": sorted(unrunnable)}


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
    promo_names: list[str] = []
    for path in (DESK / "reports" / "shadow" / "shadow_state.json",
                 DESK / "reports" / "shadow" / "qquant_shadow_state.json",
                 DESK / "reports" / "shadow" / "scalp_shadow_state.json",
                 DESK / "reports" / "shadow" / "external_shadow_state.json"):
        data = _read(path)
        for key, row in list(data.items()) + list((data.get("sleeves") or {}).items() if isinstance(data.get("sleeves"), dict) else []):
            if not isinstance(row, dict) or "status" not in row:
                continue
            status = _norm_status(row.get("status"))
            if _is_terminal(status):
                continue
            # DAYS ARE DERIVED, NEVER TRUSTED. A lane whose engine went stale keeps writing
            # its last days_active forever (measured: XAGUSD stored 9 while forward_start said
            # 1 -- a promote lane reading the stored field would clear a window never served).
            # forward_start is the frozen clock; the wall clock is the other operand. Stored is
            # the fallback only when no forward_start exists.
            # BOTH SPELLINGS, because the lanes do not agree and the reader must not care.
            # shadow_forward and qquant_shadow write `days_active`; scalp_shadow writes `days`.
            # Reading only the first showed every scalp sleeve as "day 0/14" -- three gold scalp
            # sleeves that had been on their forward clock since 2026-08-22 displayed as if they
            # had started today, for a fortnight. Exactly the defect `_norm_status` fixes one
            # field over: this tile knew one lane's vocabulary and silently zeroed the others.
            days = int(_number(row.get("days_active"), row.get("days")) or 0)
            fs = _timestamp(row.get("forward_start"))
            if fs is not None:
                days = max(0, (datetime.now(UTC) - fs).days)
            forward.append({"name": key, "days": days, "of": 14,
                            "n": int(_number(row.get("n")) or 0),
                            # Shown beside the forward count, never added to it: an observation
                            # that predates the frozen clock is evidence about a different
                            # question and may not satisfy a forward threshold.
                            "n_historical": int(_number(row.get("n_historical")) or 0),
                            # lanes name their stats differently; the dash shows the fact,
                            # whatever the local field was called
                            "exp_r": _number(row.get("exp_r"), row.get("expectancy_r")),
                            "t": _number(row.get("forward_t"), row.get("t")),
                            "sleeve_id": row.get("sleeve_id"),
                            "status": status})
            # NORMALISED, so this counts every lane rather than only the one that writes a
            # space. See _norm_status: the scalp and qquant lanes were invisible here.
            if status == "PROMOTION CANDIDATE":
                promo_ready += 1
                promo_names.append(key)
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
    survivors_doc = _read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json") or {}
    certs = survivors_doc.get("survivors") or {}
    # AN ABSENT FILE IS NOT A DESK WITH ZERO CERTIFICATES. `_read` returns {} for both, and a
    # census over {} would publish `certified: 0` -- a clean, plausible number standing in for
    # "this host never saw the artifact". That is the WS-005 shape this repo refuses everywhere
    # else, and it would be worse here than the bug being fixed: 0 reads as a desk with no edge
    # rather than a dashboard with no data. The presence of the `survivors` KEY, not the size of
    # the mapping it holds, is what says the file was read.
    census = (_certificate_census(certs) if isinstance(survivors_doc.get("survivors"), dict)
              else {"basis": "UNAVAILABLE (reports/UNIVERSAL_SURVIVORS.json did not reach this "
                             "host, so no ten-gate census could be taken)",
                    "certified": None, "gate_failed": None,
                    "gate_failed_names": [], "unrunnable_names": []})
    unrunnable = census["unrunnable_names"]
    return {
        "certificates_unrunnable": len(unrunnable),
        "unrunnable_reason": ("`shadow_spec.params` is absent (None), so there is no "
                              "parameterisation to execute. Re-certify through the current "
                              "gauntlet, which records the parameterisation it tested. An EMPTY "
                              "mapping is not this case -- it is the complete parameterisation "
                              "'family defaults' and enrols normally."),
        "unrunnable_examples": sorted(unrunnable)[:6],
        # THE SURVIVORS FILE IS NOT A CERTIFICATE LIST, and reading it as one is how the
        # dashboard came to publish gate FAILURES as certificates. Measured 2026-09-06 on the
        # sealed canon: 66 rows, of which 12 carry status LOCKBOX_FAILED and `all_ten_pass ->
        # False`. `shadow_admission.authorized_runs` refuses those 12 correctly and silently, so
        # the operator saw "certified 55, clocks 19" and a 36-sleeve hole with no cause -- when a
        # third of the hole was simply rows that never passed. Counting the ten-gate verdict
        # instead of the dict length is the fix; the failures stay visible under their own name
        # rather than being deleted, because a row that failed a gate is evidence about the sweep.
        "certified_gate_failed": census["gate_failed"],
        "certified_gate_failed_examples": census["gate_failed_names"][:6],
        "census_basis": census["basis"],
        "forward_observations": forward_obs,
        "historical_observations": hist_obs,
        "discovered_backtested": hyp,
        # THE THROUGHPUT TILE MUST COUNT THE GAUNTLET. "141 backtested" was stage-A's little
        # miner grid while the ten gates judged 1,315 cells the same hour -- the dashboard
        # under-reported the machine by an order of magnitude and read as a stall (principal:
        # "thousands flowed through the gauntlet but backtesting is so low"). Docket size and
        # the last sweep's judged/unmeasured are the real funnel.
        "docket_candidates": _funnel_docket(),
        "gauntlet_last_judged": _gate_stat("n_judged"),
        "gauntlet_last_unmeasured": _gate_stat("n_unmeasured"),
        # THE TEN-GATE VERDICT, NOT THE FILE'S ROW COUNT. `n` is `len(survivors)`, which includes
        # rows that failed a gate and were kept for the record (see `certified_gate_failed`).
        # Publishing that as "certified" told the principal the desk held 55 certificates while
        # the door downstream refused a dozen of them for never having passed -- the funnel's
        # single most misleading number.
        #
        # AND IT DOES NOT FALL BACK TO `n`. The obvious fallback -- census unavailable, so use the
        # row count -- republishes the exact defect this line exists to fix, and does it precisely
        # when nobody can tell (the census is unavailable, so no other field contradicts it). An
        # overstated certificate count is not a degraded answer, it is a wrong one: it says the
        # desk holds edge it does not hold. None renders as an em-dash and `census_basis` names
        # the cause, which is the honest report of "this host cannot answer that question".
        # The census needs `gate_policy`, which loads the gate spec YAML -- the single source of
        # truth for what the ten gates ARE. A hardcoded gate list here would be a second judge,
        # and this desk has already paid twice for two builders of one identity.
        "certified": (census["certified"] if census["basis"] == "ten_gate_verdict" else None),
        "forward_clocks": len(forward),
        "promotion_ready": promo_ready,
        # NAMED, not just counted. A bare count told the principal "0 promotable" for days while
        # two lanes were unreadable to the counter; a NAME is checkable against the lane's own
        # state file the moment it looks wrong.
        "promotion_ready_names": sorted(promo_names),
        "live": len(live_rows),
        # NOT [:40] ANY MORE, AND THE CAP WAS NOT A DISPLAY CHOICE. check_research_health
        # reads THIS list to find BLOCKED and stalled clocks, so the cap silently limited the
        # fence to the 40 OLDEST sleeves. Measured 2026-09-01: shadow_state carried
        # configured_sleeves 56 against 57 runnable certificates, written six minutes earlier
        # -- enrolment was working same-day, exactly as shadow_forward claims. The 16 dropped
        # rows were the NEWEST clocks, which sort last by `days`, so every freshly certified
        # sleeve was invisible to the organ whose job is to notice a sleeve accruing nothing,
        # until older clocks aged out. A truncated funnel reads as a stalled one.
        # Bounded generously rather than unbounded: 500 rows is ~100KB, far above any plausible
        # clock count, so the artifact still cannot grow without limit.
        "forward_detail": sorted(forward, key=lambda r: -r["days"])[:500],
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


#: How old the box's freshest report may be before the dashboard calls it LATE. Deliberately the
#: SAME 2700s that `monitor_mt5_shadow_sync` already uses -- a dashboard that tolerated more than
#: the watchdog would be a second, looser opinion on one fact, and the looser one always wins the
#: argument because it is the one on screen.
BOX_LATE_SECONDS = 2700
#: Past this the box is not late, it is gone. Six hours spans a weekend gap in no market this desk
#: trades: XAUUSD and the FX majors never sit still that long while a gateway is alive.
BOX_SILENT_SECONDS = 6 * 3600
#: Every file the box's own sync carries, with the field each uses for its clock. If the box is
#: running, at least one of these moves every pass; if none has moved, nothing on the box is
#: writing and every other tile on this dashboard is reading a photograph.
BOX_REPORTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("reports/shadow/shadow_health.json", ("updated_at",)),
    ("data/gateway_state.json", ("last_reconcile", "updated_at", "as_of")),
    ("data/regime_state.json", ("swept_at", "updated_at")),
    ("data/account_state.json", ("updated_at", "timestamp", "fetched_at")),
    ("reports/shadow/scalp_shadow_state.json", ("updated_at", "last_update")),
)


def _box_liveness(now: datetime) -> dict[str, Any]:
    """IS THE MACHINE THAT HOLDS THE CAPITAL STILL REPORTING? Nothing on this board asked.

    MEASURED 2026-09-06: the box's last real state push was 2026-08-26 14:50 -- TEN DAYS.
    `monitor_mt5_shadow_sync` had been returning `status: FAILED, shadow health sync stale:
    896946s` every thirty minutes for the whole of it, correctly, into a systemd timer whose
    non-zero exit nobody reads. The dashboard never imported that verdict, so every tile on it
    went on rendering ten-day-old numbers in the present tense, and the desk was asked whether to
    put live capital behind them.

    That is the worst failure a dashboard has, because it is invisible in exactly the way that
    matters: a board showing stale truth and a board showing current truth are pixel-identical.
    Only the age distinguishes them, and the age was the one thing not on screen.

    The freshest clock across the box's own artifacts is what counts -- not the oldest. One organ
    dying is a defect in that organ; ALL of them stopping is the machine. `per_report` keeps the
    individual ages so the two cases stay distinguishable, because they need opposite responses.
    """
    ages: dict[str, Any] = {}
    newest: datetime | None = None
    for rel, fields in BOX_REPORTS:
        path = DESK / rel
        stamp = _timestamp(_find(_read(path), *fields))
        name = rel.rsplit("/", 1)[-1]
        if stamp is None:
            # ABSENCE IS NEVER A PASS (L1.28a) -- AND ABSENT IS NOT THE SAME AS UNSTAMPED.
            # The first draft printed "no clock in this file" for a file that does not exist on
            # this host, which reads as "the producer forgot a timestamp" when the truth is "the
            # producer runs on another machine and its output has never crossed the wire". Those
            # need opposite responses: one is a code fix, the other is a delivery fix, and
            # conflating them sends the reader to the wrong machine.
            ages[name] = {
                "age_seconds": None,
                "status": "ABSENT" if not path.exists() else "NO_CLOCK",
                "why": (f"{rel} does not exist here; it is written on the trading box and "
                        "reaches this host only through the shadow sync"
                        if not path.exists() else
                        f"{rel} exists but carries none of {list(fields)}"),
            }
            continue
        age = max(0.0, (now - stamp).total_seconds())
        ages[name] = {"age_seconds": round(age), "at": stamp.isoformat(timespec="seconds"),
                      "status": "FRESH" if age <= BOX_LATE_SECONDS else "STALE"}
        newest = stamp if newest is None or stamp > newest else newest

    if newest is None:
        return {"status": "UNMEASURED", "silent_seconds": None, "last_reported_at": None,
                "per_report": ages,
                "why": ("not one of the box's artifacts carries a readable clock, so this "
                        "dashboard cannot tell a live desk from a photograph of one")}
    silent = max(0.0, (now - newest).total_seconds())
    status = ("REPORTING" if silent <= BOX_LATE_SECONDS
              else "LATE" if silent < BOX_SILENT_SECONDS else "SILENT")
    hours = silent / 3600
    why = {
        "REPORTING": f"box reported {round(silent)}s ago",
        "LATE": (f"box has not reported for {hours:.1f}h -- every figure below is at least "
                 f"that old, whatever it looks like"),
        "SILENT": (f"box has not reported for {hours:.1f}h. Nothing on this dashboard is "
                   f"current. Do not size capital off it until the box reports again"),
    }[status]
    return {"status": status, "silent_seconds": round(silent),
            "last_reported_at": newest.isoformat(timespec="seconds"),
            "late_after_seconds": BOX_LATE_SECONDS, "silent_after_seconds": BOX_SILENT_SECONDS,
            "per_report": ages, "why": why}


def build() -> dict[str, Any]:
    gateway = _read(DESK / "data" / "gateway_state.json")
    # NEVER FALL BACK TO gateway_state FOR THE ACCOUNT (2026-09-04). On a box with no MT5
    # terminal _mt5_snapshot() returns None, account_state.json is often absent, and this fell
    # through to gateway_state -- whose `equity` was a stale 21127.01 while the live account held
    # 743.14. The VPS then OVERWROTE the correct figure it had just pulled from the trading box,
    # so the dashboard published a number 28x the real balance, and the equity curve recorded it
    # 32 times. Two writers, and the one WITHOUT a terminal won.
    #
    # A machine that cannot see the account must not publish a figure for it. Absence is not
    # permission to invent: when there is no snapshot, the previously PULLED desk_state is the
    # best available truth and is preserved rather than replaced.
    account = _mt5_snapshot() or _read(DESK / "data" / "account_state.json")
    if not account:
        _pulled = _read(ROOT / "web" / "desk_state.json").get("account") or {}
        account = _pulled if _number(_find(_pulled, "equity", "account_equity")) else {}
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
    box = _box_liveness(now)
    # STALE AT TWO MINUTES AND STALE AT TEN DAYS RENDERED THE SAME WORD. The account feed lags its
    # writer by design, so STALE is routine and reads as noise; a box that stopped reporting on
    # 08-26 is not routine and must not borrow that word's calm. When the box is gone, the account
    # tile says so in the box's own terms rather than in the feed's.
    if box["status"] == "SILENT" and live_state != "UNMEASURED":
        live_state = "SILENT"
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
        # EVERY ISSUE THE DESK CAN SEE, ON THE BOARD. Detection was never the gap -- 121
        # check_* scripts already worked. What was missing was one surface showing the
        # aggregate, so a real breach could be detected correctly and read by nobody.
        "issues": _read(DESK / "reports" / "ISSUE_BOARD.json"),
        "health": {
            "newest_h1_file": newest_bar_file, "midnight": midnight,
            "daily_cycle": daily, "status": live_state,
            # The first thing a reader needs and the last thing this board learned to say. Placed
            # inside `health` rather than a corner of its own because it QUALIFIES every other
            # number here: a REPORTING box makes them observations, a SILENT one makes them
            # history rendered in the present tense.
            "box": box,
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
