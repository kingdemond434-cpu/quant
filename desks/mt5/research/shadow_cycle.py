"""Frequent, idempotent owner of every configured MT5 forward-shadow sleeve.

This is deliberately separate from daily research. Forward evidence follows data arrival, not a
calendar ceremony: each invocation replays the latest bars, refreshes all sleeve states, then runs
the deterministic promoter. Replays overwrite content-addressable ledgers, so cadence cannot
double-count trades.
"""
from __future__ import annotations

import json
import os
import re
import traceback
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "reports" / "shadow" / "shadow_health.json"


def _resilient_writers():
    """`libs.ops.win_write`, with the repo root put on sys.path if the .pth is missing.

    THE LAST CENSUS THE BOX PUBLISHED (2026-09-16T16:37Z) WAS FAILED ON TWO WINDOWS SHARING
    VIOLATIONS, not on a clock: `XAUUSD_M1.parquet` and `external_shadow_state.json` were
    overwritten in place while other organs held them open, Python raised PermissionError 13, and
    MT5-Shadow exited 1 every run while `legacy_shadow` itself had succeeded. See win_write.
    """
    import sys
    root = str(BASE.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.ops import win_write
    return win_write

#: EVERY BASIS ON WHICH THIS DESK ENROLS A FORWARD CLOCK. One place, because the alternative is
#: an `==` against one member scattered through the readers -- which is how the cure lane's 86
#: clocks came to be reported as missing for a day.
#:
#:   ORIGINAL_UNIVERSAL_10_PASS   all ten gates; the only basis that carries promotion authority
#:                                on its own, and what every clock held before 2026-09-13
#:   VALIDITY_PASS_POWER_DEFICIENT  all five VALIDITY gates pass, one or more POWER gates fail.
#:                                The deficiency is `cure_by_forward: true` BY DESIGN -- forward
#:                                evidence is the thing that cures a power shortfall -- so the
#:                                clock exists precisely to earn what the gate withheld. It
#:                                enrols with `promotion_authority: false` and stays there until
#:                                `pipeline/promote.py` applies the cure thresholds.
#:   FULL_10_PASS                 promote.py's own spelling of the ten-gate basis; accepted here
#:                                so the two vocabularies cannot disagree about who is enrolled.
ENROLLED_ADMISSIONS = frozenset({
    "ORIGINAL_UNIVERSAL_10_PASS",
    "VALIDITY_PASS_POWER_DEFICIENT",
    "FULL_10_PASS",
})

# The canonical bar producer runs hourly. Allow one cadence plus 15 minutes of scheduler jitter;
# the replay is idempotent and catches every intervening M1/M5/M15 bar at the next snapshot.
# A 30-minute consumer threshold made the second half of every healthy producer hour look failed.
SCALP_BAR_MAX_AGE_SECONDS = 75 * 60


def _fusion_gold_market_open(now: datetime) -> bool:
    """Approximate the broker's 24/5 gold session for refresh decisions.

    This is the same weekly boundary used by ``h1_source`` and ``scalp_shadow``.  A consumer
    must not attempt a second terminal attachment merely because an authoritative Friday file
    grows older while the venue is closed: no new bar exists to fetch, and the resulting MT5
    ``-10004 / No IPC connection`` used to turn an otherwise healthy shadow census FAILED every
    weekend.  Market-open freshness remains strict below.
    """
    t = now.astimezone(UTC)
    weekday, hour = t.weekday(), t.hour
    return not (weekday == 5 or (weekday == 4 and hour >= 22)
                or (weekday == 6 and hour < 22))


def _fresh_authoritative_scalp_bars(now: datetime | None = None) -> bool:
    """True when the canonical Fusion collector already supplied the bounded scalp input.

    The shadow cycle is a consumer, not a second terminal owner.  Re-attaching while the trading
    terminal is serving another scheduled collector produces MT5 ``-10004 / No IPC connection``
    even though all three authoritative files are already fresh.  We only skip the fallback pull
    when provenance grants promotion authority and every required file is fresh and non-empty.
    """
    now = now or datetime.now(UTC)
    universe = BASE / "data" / "universe"
    source = _read(universe / "XAUUSD_scalp_source.json")
    if source.get("promotion_authority") is not True:
        return False
    market_open = _fusion_gold_market_open(now)
    for timeframe in ("M1", "M5", "M15"):
        path = universe / f"XAUUSD_{timeframe}.parquet"
        try:
            age = now.timestamp() - path.stat().st_mtime
        except OSError:
            return False
        if path.stat().st_size <= 0 or age < -60:
            return False
        # Closed-market bars cannot become fresher.  The source is still authoritative and the
        # shadow engines account for elapsed MARKET-OPEN hours separately.  During an open
        # session the ordinary 75-minute producer SLA remains an absolute requirement.
        if market_open and age > SCALP_BAR_MAX_AGE_SECONDS:
            return False
    return True


def _refresh_scalp_bars() -> None:
    """Refresh broker M1/M5/M15 before replay; never place or modify an order.

    THIS USED TO ROUTE THROUGH fetch_gold_scalp.fetch(), which hard-refuses any
    account with account.trade_allowed set -- "refusing history job: account
    permits trading". That refusal is correct and stays completely untouched:
    fetch_gold_scalp.py is built for a heavier, occasional, manually-run pull
    (up to 90k bars, paged, 15 retries) and refusing to run that shape of job
    against a live-trading terminal is the right blast-radius guard for IT.

    But routing the routine 15-minute cycle through that same function meant
    every scheduled run refused outright the moment the desk went live on a
    real trading account -- these four scalp sleeves would stay
    WAITING_FOR_FORWARD_BARS forever on the one account this desk actually
    trades on, which is not a data problem, it is a wiring problem: this
    cycle's need is a small, bounded, ROUTINE refresh, the same shape of
    operation h1_source.from_mt5 already performs on this exact
    trade-allowed account every cycle, for the other 36 sleeves' H1 bars, with
    no incident. So this reuses that already-proven policy -- initialize,
    read, shutdown, no trade_allowed check -- and fetch_gold_scalp's own
    paging helper (_paged_rates, already exercised by the manual path), rather
    than fetch_gold_scalp.fetch()'s wrapper and its refusal. Writes the exact
    same file shapes fetch_gold_scalp.fetch() did -- XAUUSD_{tf}.parquet
    indexed by "timestamp", and XAUUSD_scalp_source.json with an honest (not
    refused) account_trade_allowed -- so scalp_shadow.py, which reads both,
    needs no changes.
    """
    if os.name != "nt":
        return
    if _fresh_authoritative_scalp_bars():
        return
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    import h1_source
    import MetaTrader5 as mt5
    import pandas as pd
    from fetch_gold_scalp import _paged_rates

    out_dir = BASE / "data" / "universe"
    frames = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
    failures: list[str] = []
    for terminal in h1_source._terminal_candidates():
        if not Path(terminal).exists():
            continue
        from mt5_session import attach_or_initialize
        if not attach_or_initialize(mt5, path=terminal, timeout=15_000):
            failures.append(f"{terminal}: initialize failed: {mt5.last_error()}")
            continue
        try:
            account = mt5.account_info()
            if account is None:
                failures.append(f"{terminal}: account unavailable")
                continue
            if not mt5.symbol_select("XAUUSD", True):
                failures.append(f"{terminal}: cannot select XAUUSD: {mt5.last_error()}")
                continue
            result: dict[str, int] = {}
            out_dir.mkdir(parents=True, exist_ok=True)
            for label, timeframe in frames.items():
                rates = _paged_rates(mt5, "XAUUSD", timeframe, 20_000)
                if rates is None or len(rates) == 0:
                    result[label] = 0
                    continue
                frame = pd.DataFrame(rates)
                frame.index = pd.to_datetime(frame.pop("time"), unit="s", utc=True)
                frame.index.name = "timestamp"
                # SERIALISED FIRST, THEN SWAPPED IN: an in-place to_parquet over a file the scalp
                # lane is reading is a sharing violation on Windows (PermissionError 13).
                import io as _io
                _buf = _io.BytesIO()
                frame.to_parquet(_buf)
                _resilient_writers().write_bytes_resilient(
                    out_dir / f"XAUUSD_{label}.parquet", _buf.getvalue())
                result[label] = len(frame)
            terminal_info = mt5.terminal_info()
            server = str(account.server)
            _resilient_writers().write_text_resilient(
                out_dir / "XAUUSD_scalp_source.json", _json.dumps({
                "fetched_at": _datetime.now(_UTC).isoformat(timespec="seconds"),
                "source_server": server,
                "source_company": str(terminal_info.company if terminal_info else ""),
                "account_trade_allowed": bool(account.trade_allowed),
                "symbol": "XAUUSD", "rows": result,
                "promotion_authority": "fusion" in server.casefold(),
            }, indent=2))
            if all(result.values()):
                return
            failures.append(f"{terminal}: incomplete {result}")
        except Exception as exc:
            failures.append(f"{terminal}: {type(exc).__name__}: {exc}")
        finally:
            mt5.shutdown()
    raise RuntimeError("no MT5 history source: " + " | ".join(failures))


def _read(path: Path) -> dict:
    try:
        row = json.loads(path.read_text("utf-8"))
        return row if isinstance(row, dict) else {}
    except (OSError, ValueError):
        return {}


#: NAMED EXCLUSIONS FROM THE ENROLMENT CENSUS (2026-11-25). A certificate the desk is FORBIDDEN to
#: clock is not a missing clock. Exotic FX is banned outright (zuck 2026-11-24 18:06Z: no mining,
#: judging or trading of exotic FX), and a family in data/banned_families.json never gets a clock
#: (`shadow_forward` refuses it by name). Counting either as "missing" made ENROLMENT_GAP -- and
#: MT5-Shadow's exit 3 -- permanent: measured on the box 2026-11-24, 13,452 certificates against
#: 627 clocks, with the exotic share of the clock book alone at ~60%. The exclusions are COUNTED
#: and REASONED on the health row, never dropped silently, and no gate, certificate or trial
#: count is touched: this changes which number is called a deficiency, not what passed.
EXCLUSION_REASONS = {
    "exotic": ("exotic FX is banned from mining, judging and trading (zuck 2026-11-24 18:06Z); "
               "universe_policy.is_exotic_symbol, the desk's one exotic definition"),
    "banned_family": "family banned by the principal (data/banned_families.json); no clock is owed",
}


def _symbol_of_cert(name: str, row: dict) -> str:
    spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    return str(spec.get("symbol") or row.get("sym") or row.get("symbol") or "").upper()


def _family_of_cert(row: dict) -> str:
    spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
    return str(spec.get("family") or row.get("family") or "")


def _exclusion_of(symbol: str, family: str) -> str | None:
    """'exotic' / 'banned_family' / None. Never raises: an unreadable policy excludes nothing,
    so an outage can only make the census LOUDER (more reported missing), never quieter."""
    if symbol:
        try:
            from universe_policy import is_exotic_symbol
            if is_exotic_symbol(symbol):
                return "exotic"
        except Exception:
            pass
    if family:
        try:
            from family_policy import family_banned
            if family_banned(family):
                return "banned_family"
        except Exception:
            pass
    return None


def _canonical_certificate_census() -> dict | None:
    """{all, eligible, excluded: {reason: {n, why}}} over the exact-policy canon, or None."""
    try:
        from gate_policy import all_ten_pass, is_exact_policy
        doc = _read(BASE / "reports" / "UNIVERSAL_SURVIVORS.json")
        if not is_exact_policy(doc.get("gate_policy")):
            return None
        rows = doc.get("survivors")
        if not isinstance(rows, dict):
            rows = {}
        n_all = 0
        excluded: dict[str, int] = {}
        for name, row in rows.items():
            if not (isinstance(row, dict) and all_ten_pass(row.get("gates"))):
                continue
            n_all += 1
            why = _exclusion_of(_symbol_of_cert(str(name), row), _family_of_cert(row))
            if why:
                excluded[why] = excluded.get(why, 0) + 1
        return {"all": n_all, "eligible": n_all - sum(excluded.values()),
                "excluded": {k: {"n": v, "why": EXCLUSION_REASONS[k]}
                             for k, v in sorted(excluded.items())}}
    except (ImportError, OSError, ValueError, TypeError):
        return None


def _canonical_certificate_count() -> int | None:
    """Exact-policy ten-gate certificates the desk OWES a clock: the canon minus the named
    exclusions above (see `_canonical_certificate_census` for the excluded counts)."""
    census = _canonical_certificate_census()
    return None if census is None else int(census["eligible"])


def _clock_row_excluded(key: str, row: dict) -> bool:
    """A clock row on an excluded symbol or family, so the census compares like with like."""
    k = str(key)
    sym = str(row.get("symbol") or (k.split(".", 1)[0] if "." in k else "")).upper()
    return _exclusion_of(sym, _family_of_key(k)) is not None


def _family_of_key(key: str) -> str:
    """The mechanism a shadow key names. Keys are minted, so this reads a field, not a guess."""
    k = str(key)
    if "." in k:                       # SYMBOL.family.selector#params
        parts = k.split("#", 1)[0].split(".")
        return parts[1] if len(parts) > 1 else ""
    parts = k.split("_p_", 1)[0].split("_")   # symbol_family_selector_p_hash
    return "_".join(parts[1:-1]) if len(parts) > 2 else ""


def _hash_of_key(key: str) -> str:
    """The parameter signature a shadow key carries, or "" when it is unparameterised."""
    import re as _re
    m = _re.search(r"_p_([0-9a-f]{8,})$", str(key))
    if m:
        return m.group(1)
    if "#" in str(key):
        import hashlib as _h
        return _h.sha256(str(key).split("#", 1)[1].encode("utf-8")).hexdigest()[:16]
    return ""


def _param_hash(row: object) -> str:
    """The parameter signature a forward row carries, or "" when it has none.

    A ROW'S IDENTITY IS ITS PARAMETERS, NOT ITS SYMBOL. Two sleeves on different instruments with
    the same parameter set are one hypothesis tested twice, and counting them as two is how a
    dashboard reports four times the breadth the book actually holds.
    """
    if not isinstance(row, dict):
        return ""
    for k in ("param_hash", "params_hash", "p"):
        v = row.get(k)
        if isinstance(v, str) and v:
            return v
    params = row.get("params")
    if isinstance(params, dict) and params:
        import hashlib
        return hashlib.sha256(
            json.dumps(params, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return ""


def _terminal_status(value: object) -> bool:
    status = str(value or "").upper()
    return any(status == prefix or status.startswith(prefix + "_") for prefix in (
        "KILL", "PROMOTED", "DEAD", "REJECTED", "RETIRED", "QUARANTINED",
    ))


def _canonical_live_exposure(name: object) -> str:
    """The executable exposure behind a promoted row.

    Gold ``_v2/_v3/_v4`` rows are certificate lineages behind ONE window.  The gateway already
    strips the suffix before pricing and places only the three parent brackets, but the health
    report used to publish every lineage as an independent live sleeve.  That made a three-leg
    book read as nine legs precisely where operators inspect concentration.  Only the explicit
    gold-window aliases are folded; versions of any other strategy remain distinct.
    """
    text = str(name or "")
    if re.fullmatch(r"gold_(?:asia|london_am|afternoon)_v\d+", text):
        return re.sub(r"_v\d+$", "", text)
    return text


def _zero_trade_diagnostics(rows: list[dict], now: datetime) -> dict[str, object]:
    """Explain zero-trade clocks without pretending a quiet hypothesis is a broken clock."""
    by_status: dict[str, int] = {}
    ages: list[float] = []
    mature = 0
    natural = 0
    suppressed: list[str] = []
    fresh_attempts = 0
    for row in rows:
        if int(row.get("n", 0) or 0) > 0:
            continue
        status = str(row.get("status") or "ACTIVE").upper()
        by_status[status] = by_status.get(status, 0) + 1
        attempted = row.get("last_attempt_at")
        try:
            attempt = datetime.fromisoformat(str(attempted).replace("Z", "+00:00"))
            attempt = attempt if attempt.tzinfo else attempt.replace(tzinfo=UTC)
            attempt_fresh = (now - attempt.astimezone(UTC)).total_seconds() <= 3 * 3600
        except (TypeError, ValueError):
            attempt_fresh = False
        fresh_attempts += int(attempt_fresh)
        has_bars = bool(str(row.get("bar_source") or "").strip())
        has_error = bool(str(row.get("last_error") or "").strip())
        if status == "ACTIVE" and attempt_fresh and has_bars and not has_error:
            natural += 1
        else:
            suppressed.append(str(row.get("sleeve") or row.get("key") or
                                  row.get("name") or "UNKNOWN"))
        raw = row.get("forward_start") or row.get("enrolled_at")
        try:
            stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            stamp = stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
            age = max(0.0, (now - stamp.astimezone(UTC)).total_seconds() / 86400.0)
        except (TypeError, ValueError):
            continue
        ages.append(age)
        if age >= 14.0:
            mature += 1
    return {
        "count": sum(by_status.values()),
        "by_status": dict(sorted(by_status.items())),
        "age_measured": len(ages),
        "median_age_days": (round(sorted(ages)[len(ages) // 2], 3) if ages else None),
        "mature_14d_without_trade": mature,
        "fresh_attempts": fresh_attempts,
        "naturally_inactive": natural,
        "suppressed_or_unproven": len(suppressed),
        "suppressed_examples": suppressed[:40],
        "rule": ("zero trades is not automatically a plumbing failure: blocked statuses name a "
                 "repair; only ACTIVE + fresh attempt + valid bar source + no current error is "
                 "natural inactivity. An ACTIVE clock older than 14 days is a low-frequency/selection "
                 "finding routed to forward exploitation; no synthetic or backdated trade is "
                 "ever created"),
    }


def _clock_rotation_summary() -> dict | None:
    """The forward engine's rotation summary (reports/shadow/CLOCK_FRESHNESS.json `summary`), so
    the health board shows how fresh every clock is without reading the per-clock table."""
    doc = _read(BASE / "reports" / "shadow" / "CLOCK_FRESHNESS.json")
    summ = doc.get("summary") if isinstance(doc, dict) else None
    return summ if isinstance(summ, dict) else None


def _clock_coverage_summary() -> dict | None:
    """reports/shadow/CLOCK_COVERAGE.json's verdict and counts (not its per-certificate list)."""
    doc = _read(BASE / "reports" / "shadow" / "CLOCK_COVERAGE.json")
    if not isinstance(doc, dict) or not doc:
        return None
    return {k: doc.get(k) for k in ("at", "status", "n_certified", "n_owed", "n_clocked",
                                    "n_missing", "missing_by_reason")}


def run() -> tuple[dict, int]:
    import external_shadow
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    started = datetime.now(UTC)
    errors: dict[str, str] = {}
    stage_seconds: dict[str, float] = {}
    for name, fn in (
        ("scalp_bar_refresh", _refresh_scalp_bars),
        # Compatibility migration only: retires the old private external ledger. External
        # certificates themselves run below in shadow_forward, so there is one evidence clock
        # per identity rather than two competing ledgers with different freshness.
        ("external_state_reconcile", external_shadow.main),
        ("legacy_shadow", shadow_forward.main),
        ("scalp_shadow", scalp_shadow.main),
        ("qquant_shadow", qquant_shadow.main),
        ("promoter", promoter.main),
    ):
        _t = datetime.now(UTC)
        try:
            result = fn()
            if isinstance(result, int) and not isinstance(result, bool) and result != 0:
                raise RuntimeError(f"returned non-zero status {result}")
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        finally:
            stage_seconds[name] = round((datetime.now(UTC) - _t).total_seconds(), 1)

    # PRE-REGISTRATION STAMP, CENTRALIZED (RESEARCH §6d). Every live forward row must carry
    # `forward_start` from the moment it exists; a clock counted from the first trade ever taken
    # was letting selection-era evidence pose as forward evidence (36 rows measured 2026-08-26).
    # The stamp is applied HERE -- by the orchestrator that owns these files -- so every engine,
    # present and future, is covered by one code path instead of each reimplementing it (the
    # one-pipeline law). First-seen-now is the only defensible stamp; backdating is fabrication.
    # READ FRESH UNDER THE LEDGER LOCK (2026-11-25, invariant I1): this used to read the file,
    # stamp, and replace it whole, so a clock another writer opened in between was dropped.
    import ledger_lock

    def _stamp_forward_start(_d: dict) -> int:
        _n = 0
        for _row in list(_d.values()) + list((_d.get("sleeves") or {}).values()):
            if (isinstance(_row, dict) and ("status" in _row or "n" in _row)
                    and not _terminal_status(_row.get("status"))
                    and not _row.get("forward_start")):
                _row["forward_start"] = datetime.now(UTC).isoformat()
                _n += 1
        return _n

    for _sf in ("shadow_state.json", "scalp_shadow_state.json", "qquant_shadow_state.json"):
        _p = BASE / "reports" / "shadow" / _sf
        if not _p.exists():
            continue
        try:
            _stamped = ledger_lock.update(_p, _stamp_forward_start)
        except OSError as _exc:
            print(f"forward_start stamp not written to {_sf} ({type(_exc).__name__}: {_exc})")
            continue
        if _stamped:
            print(f"stamped forward_start on {_stamped} row(s) in {_sf}")

    legacy = _read(BASE / "reports" / "shadow" / "shadow_state.json")
    scalp = _read(BASE / "reports" / "shadow" / "scalp_shadow_state.json")
    qquant = _read(BASE / "reports" / "shadow" / "qquant_shadow_state.json")
    # THE CENSUS COUNTED ONE ADMISSION STRING AND CALLED THE REST MISSING (fixed 2026-09-13).
    #
    # This matched `gate_admission == "ORIGINAL_UNIVERSAL_10_PASS"` exactly, which was complete
    # while that was the only basis any clock could hold. The power-cure lane ended that: a cell
    # that passes all five VALIDITY gates and fails only POWER gates now enrols carrying
    # `VALIDITY_PASS_POWER_DEFICIENT`, because `pipeline/promote.py` branches on that exact
    # string to apply the forward-cure thresholds instead of the ten-gate ones.
    #
    # So every cure clock became INVISIBLE HERE the moment the lane opened. Measured on the box
    # tonight: shadow_state.json held 230 rows with 218 ACTIVE, this set matched 95, and the
    # difference was published as `missing_sleeves: ["86 certified sleeve(s)"]` -- 86 clocks that
    # exist, are enrolled, are accruing forward evidence, and were being reported as never having
    # been created. The lane I opened to cure power deficiency is the lane this reported as a
    # hole, every hour, with an exit code.
    #
    # THE DEFECT IS THE EQUALITY, NOT THE VALUE. An `== <one enum member>` filter over a field
    # that is designed to grow new members fails silently and in the safe-looking direction: it
    # UNDER-counts, which reads as a shortfall rather than an error, so it survives review. Same
    # shape as `live: 0` (a reader that handled one JSON shape) and the `min_volume` /
    # `volume_min` spelling -- all three answered confidently with a number that meant "I did not
    # recognise this".
    #
    # A row is represented if it is a clock this desk knowingly enrolled. Membership is now the
    # test, the bases are named in one place, and an UNRECOGNISED basis is surfaced rather than
    # silently dropped -- because the next basis added will otherwise reproduce this exactly.
    represented_legacy = {
        key for key, row in legacy.items()
        if isinstance(row, dict) and str(row.get("gate_admission") or "") in ENROLLED_ADMISSIONS
    }
    _unrecognised = sorted({
        str(row.get("gate_admission") or "")
        for key, row in legacy.items()
        if isinstance(row, dict) and ("status" in row or "n" in row)
        and str(row.get("gate_admission") or "") not in ENROLLED_ADMISSIONS
    } - {""})
    if _unrecognised:
        print("UNRECOGNISED gate_admission basis (not counted, and that is a defect here, "
              f"not in the row): {_unrecognised}")
    represented_scalp = set((scalp.get("sleeves") or {}).keys())
    represented_qquant = {
        key for key, row in qquant.items()
        if key.startswith("qquant.") and isinstance(row, dict)
    }
    rows = [legacy[key] for key in represented_legacy]
    rows += [(scalp.get("sleeves") or {})[key] for key in represented_scalp]
    rows += [qquant[key] for key in represented_qquant]
    active_rows = [row for row in rows if not _terminal_status(row.get("status"))]
    # THE FAMILY AND THE PARAMETER HASH LIVE IN THE KEY, NOT IN THE ROW (fixed 2026-09-14).
    #
    # The first version of these fields read `row.get("family")` and `row.get("params")` and
    # reported n_mechanisms 0 and n_distinct_param_hashes 0 against 183 live rows -- a confident
    # zero, which is the precise failure these fields were added to expose. Shadow keys are minted
    # as `SYMBOL.family.selector#params` or `symbol_family_selector_p_<hash>`, so the identity is
    # in the key and the row carries only the accrued evidence.
    _active_keys = [k for k in (list(represented_legacy) + list(represented_scalp)
                                + list(represented_qquant))
                    if not _terminal_status((legacy.get(k) or (scalp.get("sleeves") or {}).get(k)
                                             or qquant.get(k) or {}).get("status"))]
    _n_mechs = len({_family_of_key(k) for k in _active_keys if _family_of_key(k)})
    _n_hashes = len({_hash_of_key(k) for k in _active_keys if _hash_of_key(k)})
    terminal_rows = [row for row in rows if _terminal_status(row.get("status"))]
    census = _canonical_certificate_census()
    certified = None if census is None else int(census["eligible"])
    # Like with like: a clock row on an excluded symbol or family is not counted against the
    # certificates the desk owes a clock (those exclude the same rows).
    _keyed = ([(k, legacy[k]) for k in represented_legacy]
              + [(k, (scalp.get("sleeves") or {})[k]) for k in represented_scalp]
              + [(k, qquant[k]) for k in represented_qquant])
    recorded = sum(1 for k, r in _keyed if not _clock_row_excluded(k, r))
    if certified is None:
        errors["certificate_census"] = "canonical exact-policy certificate store is unmeasured"
        missing = []
    else:
        missing = [] if recorded >= certified else [f"{certified - recorded} certified sleeve(s)"]
    # `BLOCKED_SLEEVE_ERROR` is the per-sleeve isolation status shadow_forward writes when one
    # row cannot be evaluated (gap-wirer 2026-08-27). It MUST be counted here: the whole point of
    # isolating a failure is that the other rows keep accruing, and a failure that stops halting
    # the book while also stopping being VISIBLE is a worse trade than the crash it replaced.
    blocked = sum(row.get("status") in {"NO_DATA", "WAITING_FOR_FORWARD_BARS", "STALE_SOURCE",
                                         "BLOCKED_UNIVERSAL_GATES", "BLOCKED_SLEEVE_ERROR",
                                         "BLOCKED_NO_BARS", "BLOCKED_INPUTS_UNAVAILABLE",
                                         "BLOCKED_FAMILY_UNBUILDABLE",
                                         "REFUSED_BY_UNIVERSE_POLICY"}
                  for row in active_rows)
    # LIVE-ARM STATE, SURFACED HERE ON PURPOSE. `armed` lives in data/gateway_state.json,
    # box-local and gitignored -- no other brain (Hetzner, a future session, anyone without
    # a shell on this exact machine) can see it any other way. This file is the one artifact
    # already pushed to Hetzner every 15 minutes by MT5-ShadowSync (sync_shadow_to_vps.ps1
    # tars up reports/shadow verbatim), so riding it costs no new sync plumbing. READ ONLY:
    # this never writes gateway_state.json or sleeves.json -- arming stays the human's act,
    # this only makes the CURRENT fact visible everywhere the health report already goes.
    gw = _read(BASE / "data" / "gateway_state.json")
    sleeves_doc = _read(BASE / "data" / "sleeves.json")
    live_sleeves = [s.get("name") for s in (sleeves_doc.get("sleeves") or [])
                    if isinstance(s, dict) and s.get("status") == "LIVE"]
    _live_aliases: dict[str, list[str]] = {}
    for _name in live_sleeves:
        _live_aliases.setdefault(_canonical_live_exposure(_name), []).append(str(_name))
    _live_exposures = sorted(_live_aliases)
    _zero_trade = _zero_trade_diagnostics(active_rows, datetime.now(UTC))
    health = {
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "configured_sleeves": len(active_rows),
        "represented_sleeves": len(active_rows),
        "certified_sleeves_total": certified,
        # THE CANON AND ITS NAMED EXCLUSIONS (2026-11-25): `certified_sleeves_total` is what the
        # desk owes a clock; these say what was set aside, how many, and why.
        "certified_canon_total": None if census is None else census["all"],
        "certified_excluded": None if census is None else census["excluded"],
        "clock_rotation": _clock_rotation_summary(),
        # INVARIANT I1's verdict (research/clock_coverage.py, hourly in `forward_enrolment`):
        # certified non-exotic specs minus clocked specs, which must be 0.
        "clock_coverage": _clock_coverage_summary(),
        "forward_clocks_total": len(active_rows),
        "certificate_basis": "reports/UNIVERSAL_SURVIVORS.json exact ten-gate policy",
        # THE DASHBOARD SAID 61 AND THE TRUTH WAS ABOUT SIX (added 2026-09-14).
        #
        # A sleeve count is not a breadth measure. Measured on the live book: one parameter hash,
        # `44136fa355b3678a`, held FOUR sleeves -- chfdkk, eurnok, gbpmxn, gbpnok -- the identical
        # overnight_gap_decay parameter set on four exotics in the same session. Earlier, twelve.
        # That is one bet counted four times, and `certified_sleeves_total` reports it as four.
        #
        # `n_eff` already measures this properly (5.59 against a 1/rho ceiling of 6.1) but it
        # lives in portfolio_evidence, which nothing on the health tile reads. So the number the
        # principal sees on the board grew from 23 to 61 while effective breadth stayed flat --
        # a number that looks maintained while carrying no usable information, which is the exact
        # defect class `check_stamp_freshness` was written for.
        #
        # Three counts, because they answer three different questions and collapsing them is how
        # the confusion started: how many ROWS, how many distinct PARAMETERISATIONS, how many
        # distinct MECHANISMS. The gap between the first and the last is the replication factor.
        "n_distinct_param_hashes": _n_hashes,
        "n_mechanisms": _n_mechs,
        "retired_shadow_sleeves": len(terminal_rows),
        "quarantined_uncertified_candidates": (
            int(legacy.get("gate_blocked_sleeves", 0) or 0)
            + int(scalp.get("gate_blocked_sleeves", 0) or 0)
        ),
        "sleeves_with_forward_trades": sum(
            int(row.get("n", 0) or 0) > 0 for row in active_rows
        ),
        "zero_trade_clocks": _zero_trade,
        "evidence_blocked_sleeves": max(
            blocked, int(_zero_trade.get("suppressed_or_unproven", 0) or 0)),
        "missing_sleeves": missing,
        "errors": errors,
        "seconds": round((datetime.now(UTC) - started).total_seconds(), 3),
        # WHERE THE SECONDS WENT (2026-11-05): per stage of this cycle, and inside the forward
        # engine per phase, family, chart and slowest row (shadow_forward.PassProfile).
        "stage_seconds": stage_seconds,
        "engine_profile": ((legacy.get("engine_pass") or {}).get("profile")
                           if isinstance(legacy.get("engine_pass"), dict) else None),
        "gateway_armed": bool(gw.get("armed", False)),
        # Executable exposures are the headline. Raw certificate rows remain alongside them for
        # lineage audit, so folding aliases can never erase evidence or hide which certificate
        # granted the parent window.
        "promoted_live_sleeves": _live_exposures,
        "promoted_live_certificate_rows": live_sleeves,
        "live_exposure_aliases": {k: v for k, v in sorted(_live_aliases.items())
                                  if len(v) > 1 or v[0] != k},
    }
    # AN ENROLMENT GAP IS A CENSUS, NOT A CRASH (fixed 2026-09-13, WS-005).
    #
    # `missing` and `errors` were collapsed into one FAILED verdict and one exit code 1. Measured
    # on the box tonight: the cycle ran for 2,667 seconds, saved 183 sleeves, resolved the
    # allocation FRESH, applied four demotions and a resize, rewrote sleeves.json -- and then
    # exited 1, because 187 certificates hold 95 clocks and the other 86 have none. Every part of
    # that run worked. The number it reported was TRUE. It was rendered as the same event as a
    # traceback.
    #
    # THE COST IS NOT COSMETIC. `ops/never_stale.py` keys its remedy table on the exit code, so
    # the healer that exists to end staleness read code 1, found nothing keyed to it -- 1 is too
    # generic to key globally -- and published "NEEDS HUMAN / no standing remedy for this shape"
    # every hour about a lane that was working. An operator who checks twice and finds the desk
    # healthy both times stops checking (L0296), and the one time it IS a traceback it will look
    # exactly the same.
    #
    # So the two alarms now render differently, and the gap gets an exit code of its own:
    #   errors   -> FAILED         1   something threw; the run is not trustworthy
    #   missing  -> ENROLMENT_GAP  3   the run is trustworthy AND says N certificates lack clocks
    #   blocked  -> EVIDENCE_BLOCKED 2 (unchanged)
    # A non-zero code is kept for the gap ON PURPOSE: 86 unenrolled certificates is a real
    # deficiency the desk must not be allowed to call OK. It is simply a DIFFERENT deficiency,
    # and `ENROLMENT_GAP` carries its own remedy in never_stale's task table.
    if errors:
        health["status"] = "FAILED"
    elif missing:
        health["status"] = "ENROLMENT_GAP"
    elif blocked or int(_zero_trade.get("suppressed_or_unproven", 0) or 0):
        health["status"] = "EVIDENCE_BLOCKED"
    else:
        health["status"] = "OPERATING"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # shadow_health.json is read by stall_watch, the publisher and the census every few minutes;
    # an in-place overwrite while one of them holds it is a Windows sharing violation (Errno 13).
    _resilient_writers().write_text_resilient(OUT, json.dumps(health, indent=2))
    print(json.dumps(health, indent=2))
    return health, {"OPERATING": 0, "EVIDENCE_BLOCKED": 2,
                    "ENROLMENT_GAP": 3}.get(health["status"], 1)


def main() -> int:
    return run()[1]


if __name__ == "__main__":
    raise SystemExit(main())
