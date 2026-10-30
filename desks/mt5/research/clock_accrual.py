#!/usr/bin/env python3
"""CLOCK ACCRUAL -- for every certificate, is its forward clock gathering observations, and if not,
WHY, as one named reason.

    python desks/mt5/research/clock_accrual.py --once        # write reports/CLOCK_ACCRUAL.json
    python desks/mt5/research/clock_accrual.py --print       # the headline, no write

THE QUESTION NO EXISTING ORGAN ANSWERS PER CLOCK. `forward_enrolment` asks "does the certificate
hold a clock" and calls a clock accruing from its STATUS string; `check_certificate_clock_law`
asks whether the observation COUNT moved across two samples; `clock_liveness` asks whether the
last advance lags the venue. Each is right about its own question, and none of them says, for a
clock that sits enrolled at n=0 for a week, WHICH of a dozen independent causes is holding it:
the family cannot be rebuilt, the chart is missing from the bar store, the warmup was too short
for the family's own lookback, the key the certificate implies is not the key the lane writes,
the pass was killed before it reached the row, or the strategy's gate simply has not opened.
Those have a dozen different owners, and a count with no reason sends every one of them to the
wrong organ.

SO THE UNIT HERE IS THE CERTIFICATE AND THE OUTPUT IS AN ENUM. Every certificate the admission
door returns (`shadow_admission.authorized_runs`, both lanes) plus every one it dropped gets
exactly one `reason` from `REASONS`, with the row's own `enrolled`, `last_attempt_at`,
`last_entry` and `n` beside it. The headline is the non-accruing count BY REASON. Nothing here
enrols, retires, sizes or promotes; the fixes live in the organs that own each cause, and this is
what tells them apart.

WHERE THE CLOCK LIVES DEPENDS ON THE LANE, and that is itself one of the causes. A scalp
certificate's clock is the candidate row under `scalp_shadow_state.json["sleeves"]`; a qquant
certificate's clock is keyed by the certificate's own name in `qquant_shadow_state.json`; every
other certificate is keyed by `shadow_forward.sleeve_key`. Deriving the H1 key for all three made
every scalp and qquant certificate read "no clock" while it was running. `clock_address` is the
one resolver, and `forward_enrolment` and the L1.102 fence read it too.

UNMEASURED IS AN ANSWER (L1.28a). An unreadable canon or lane makes the affected rows, and if
necessary the whole headline, UNMEASURED -- never zero and never a pass.

HOST APPLICABILITY. On a host that advances clocks (MetaTrader5 installed) a lane that has not
been rewritten inside `SILENT_H` convicts its working rows of ENGINE_NOT_REACHED. On a build box,
whose lane files are copies, each row is judged AS OF its lane's own last pass and the lane's age
is published beside it, so a stale copy reads as a stale copy rather than as 800 silent clocks.

Artifact: desks/mt5/reports/CLOCK_ACCRUAL.json (hourly leg `clock_accrual`).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SHADOW_DIR = DESK / "reports" / "shadow"
OUT = DESK / "reports" / "CLOCK_ACCRUAL.json"
UNIVERSE = DESK / "data" / "universe"

UNMEASURED = "UNMEASURED"

H1_LANE = "shadow_state.json"
QQUANT_LANE = "qquant_shadow_state.json"
SCALP_LANE = "scalp_shadow_state.json"
LANES = (H1_LANE, QQUANT_LANE, SCALP_LANE)

#: A working clock the engine has not touched for this long is not being advanced. Three hourly
#: cycles, the same line `forward_enrolment.SILENT_TICK_HOURS` draws.
SILENT_H = 3.0

#: The floor under the derived warming window: a clock younger than this with no observation is
#: waiting, not stuck -- the floor the L1.102 fence uses so a weekend cannot manufacture a stall.
WARMING_FLOOR_H = 72.0
#: How many of the family's own measured inter-observation gaps a clock may wait.
WARMING_MULTIPLE = 3.0

# ---------------------------------------------------------------- the enum
ACCRUING = "ACCRUING"
WARMING = "WARMING"
DECIDED = "DECIDED"
#: Reasons under which the clock is doing its job; everything else is non-accruing.
COMPLIANT = (ACCRUING, WARMING, DECIDED)

NOT_ENROLLED = "NOT_ENROLLED"                  # no row under the key, and no near row either
KEY_MISMATCH = "KEY_MISMATCH"                  # a row for the same strategy under another key
PARAMS_UNRESOLVED = "PARAMS_UNRESOLVED"        # admission dropped it: no spec / no params
SELECTOR_UNMAPPED = "SELECTOR_UNMAPPED"        # breakout selector with no window
FAMILY_UNBUILDABLE = "FAMILY_UNBUILDABLE"      # no constructor the lane can call
SIDE_UNRUNNABLE = "SIDE_UNRUNNABLE"            # short on a family that takes no side, or garbage
BANNED_FAMILY = "BANNED_FAMILY"                # the principal banned the family outright
UNIVERSE_POLICY_REFUSED = "UNIVERSE_POLICY_REFUSED"
SYMBOL_UNMAPPED = "SYMBOL_UNMAPPED"            # the symbol is not in the universe registry
BAR_FILE_MISSING = "BAR_FILE_MISSING"          # no bars, and the chart's parquet is absent
NO_BARS = "NO_BARS"                            # no usable bars although a file exists
INPUTS_UNAVAILABLE = "INPUTS_UNAVAILABLE"      # a non-price input could not be rebuilt
ENGINE_ERROR = "ENGINE_ERROR"                  # the row raised
IDENTITY_BROKEN = "IDENTITY_BROKEN"
QUARANTINED = "QUARANTINED"
RETIRED_WHILE_CERTIFIED = "RETIRED_WHILE_CERTIFIED"
ENGINE_NOT_REACHED = "ENGINE_NOT_REACHED"      # a working row the pass has not visited
NO_SIGNAL_SINCE_FORWARD_START = "NO_SIGNAL_SINCE_FORWARD_START"
GATE_NEVER_OPENS = "GATE_NEVER_OPENS"          # no signal in the whole replay, not even historical
BLOCKED_UNNAMED = "BLOCKED_UNNAMED"            # a status this vocabulary does not know
#: An enrolled clock no certificate on this host's canon maps to, so the engine's roster -- rebuilt
#: every pass from the canon -- never visits it. Only in the enrolled-clock census.
OFF_ROSTER = "OFF_ROSTER"

REASONS = (ACCRUING, WARMING, DECIDED, NOT_ENROLLED, KEY_MISMATCH, PARAMS_UNRESOLVED,
           SELECTOR_UNMAPPED, FAMILY_UNBUILDABLE, SIDE_UNRUNNABLE, BANNED_FAMILY,
           UNIVERSE_POLICY_REFUSED, SYMBOL_UNMAPPED, BAR_FILE_MISSING, NO_BARS,
           INPUTS_UNAVAILABLE, ENGINE_ERROR, IDENTITY_BROKEN, QUARANTINED,
           RETIRED_WHILE_CERTIFIED, ENGINE_NOT_REACHED, NO_SIGNAL_SINCE_FORWARD_START,
           GATE_NEVER_OPENS, BLOCKED_UNNAMED, OFF_ROSTER, UNMEASURED)

#: Who fixes each non-accruing reason. Published with the headline so a count routes itself.
OWNER = {
    NOT_ENROLLED: "research/forward_enrolment.py (repair sweep) -> shadow_forward.main",
    KEY_MISMATCH: "research/clock_accrual.clock_address (the one key resolver)",
    PARAMS_UNRESOLVED: "the canon publisher: re-mint the certificate with its shadow_spec.params",
    SELECTOR_UNMAPPED: "research/shadow_forward.WINDOWS",
    FAMILY_UNBUILDABLE: "mt5desk/families*.py or the lane's own family registry",
    SIDE_UNRUNNABLE: "the family's `side` parameter (mt5desk.family_call.accepts_side)",
    BANNED_FAMILY: "none -- the principal's ban; the certificate should not exist",
    UNIVERSE_POLICY_REFUSED: "research/universe_policy.py (clears on the engine's next pass once "
                             "the policy admits the symbol)",
    SYMBOL_UNMAPPED: "data/universe/universe.json (scripts/repair_universe_registry.py)",
    BAR_FILE_MISSING: "MT5-Universe (scripts/download_all_symbols.py fetches `bars_wanted` first)",
    NO_BARS: "research/h1_source.py / scripts/refresh_tail.py (stale or short series)",
    INPUTS_UNAVAILABLE: "mt5desk/family_inputs.py (the family's non-price inputs)",
    ENGINE_ERROR: "research/shadow_forward.py -- read `last_error`",
    IDENTITY_BROKEN: "research/sleeve_registry.py / scripts/heal_identity_broken_clocks.py",
    QUARANTINED: "scripts/check_forward_clock_ratchet.py (a breached window stays breached)",
    RETIRED_WHILE_CERTIFIED: "research/forward_reconcile.py (REVIVED_CERTIFIED) / "
                             "research/retired_clocks.py (evacuation, then re-enrolment)",
    ENGINE_NOT_REACHED: "the lane's scheduled pass (MT5-Shadow / enrol_clocks): killed or not run",
    NO_SIGNAL_SINCE_FORWARD_START: "none -- the strategy has not fired since its clock froze",
    GATE_NEVER_OPENS: "the family's own warmup/lookback against shadow_forward.FETCH_DAYS",
    BLOCKED_UNNAMED: "whoever wrote the status -- name it in this vocabulary",
    OFF_ROSTER: "research/clock_liveness.py + clock_reenrol.py (re-enrol an exact identity) or "
                "research/forward_reconcile.py (retire an orphan)",
}

#: Row statuses that mean the lane is advancing the clock.
WORKING = frozenset({"", "ACTIVE", "NONE", "UNMEASURED", "ACCUMULATING", "PROXY_SHADOW"})
#: Verdicts the clock reached.
DECIDED_STATUSES = frozenset({"KILL", "KILLED", "PROMOTED", "DEAD", "REJECTED",
                              "PROMOTION CANDIDATE", "PROMOTION_CANDIDATE"})
#: Exact row statuses -> reason. Prefixes are handled in `_status_reason`.
STATUS_REASON = {
    "BLOCKED_INPUTS_UNAVAILABLE": INPUTS_UNAVAILABLE,
    "BLOCKED_FAMILY_UNBUILDABLE": FAMILY_UNBUILDABLE,
    "BLOCKED_SLEEVE_ERROR": ENGINE_ERROR,
    "IDENTITY_BROKEN": IDENTITY_BROKEN,
    "REFUSED_BY_UNIVERSE_POLICY": UNIVERSE_POLICY_REFUSED,
    "REFUSED_BANNED_FAMILY": BANNED_FAMILY,
    "WIRING_ERROR": FAMILY_UNBUILDABLE,           # qquant: family or window unknown to hunt16
    "STALE_SOURCE": NO_BARS,                      # scalp: the chart stopped updating
    "WAITING_FOR_FORWARD_BARS": NO_BARS,          # scalp: no bar yet after SHADOW_START
}


# ---------------------------------------------------------------- small readers
def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        t = datetime.fromisoformat(raw.strip().replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _hours(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return (a - b).total_seconds() / 3600.0


def host_runs_clocks() -> bool:
    """True where a terminal advances clocks; reuses `clock_liveness.mt5_installed`."""
    try:
        from research import clock_liveness
        return bool(clock_liveness.mt5_installed())
    except Exception:
        return False


# ---------------------------------------------------------------- the key resolver
def clock_address(run: Mapping[str, Any]) -> tuple[str, str | None]:
    """(lane file, clock key) for one authorized run -- where its forward clock LIVES.

    One resolver for three lanes, because deriving the H1 key for all of them is itself a cause
    of "no clock" (KEY_MISMATCH): the scalp lane keys its rows by candidate under `sleeves`, and
    the qquant lane keys them by the certificate's own name. The H1 key is the engine's own
    `sleeve_key`, never a reconstruction. None when the engine cannot be imported.
    """
    name = str(run.get("certificate") or "")
    if str(run.get("lane") or "") == "scalp" or name.startswith("scalp."):
        return SCALP_LANE, str(run.get("selector") or name.removeprefix("scalp."))
    if name.startswith("qquant."):
        return QQUANT_LANE, name
    try:
        from shadow_forward import sleeve_key  # type: ignore[import-not-found]
    except Exception:
        return H1_LANE, None
    try:
        return H1_LANE, str(sleeve_key(str(run.get("symbol") or ""),
                                       str(run.get("selector") or ""),
                                       dict(run.get("params") or {}),
                                       str(run.get("family") or "session_range_breakout"),
                                       str(run.get("side") or "LONG")))
    except Exception:
        return H1_LANE, None


def lane_rows(shadow_dir: Path | None = None) -> tuple[dict[str, dict[str, dict[str, Any]]],
                                                        dict[str, Any]]:
    """{lane: {key: row}} with the scalp lane's nested `sleeves` flattened, plus lane meta.

    A lane file that is absent or unreadable is recorded in meta as UNMEASURED and contributes no
    rows -- the certificates that live there are then UNMEASURED, never NOT_ENROLLED.
    """
    root = Path(shadow_dir or SHADOW_DIR)
    rows: dict[str, dict[str, dict[str, Any]]] = {}
    meta: dict[str, Any] = {}
    for lane in LANES:
        doc = _read_json(root / lane)
        if not isinstance(doc, dict):
            meta[lane] = {"readable": False}
            continue
        here: dict[str, dict[str, Any]] = {}
        for key, row in doc.items():
            if isinstance(row, dict) and ("n" in row or "status" in row) and key != "sleeves":
                here[str(key)] = row
        nested = doc.get("sleeves")
        if isinstance(nested, dict):
            for key, row in nested.items():
                if isinstance(row, dict):
                    here[str(key)] = row
        rows[lane] = here
        pass_ = doc.get("engine_pass") if isinstance(doc.get("engine_pass"), dict) else {}
        meta[lane] = {"readable": True, "rows": len(here),
                      "updated_at": doc.get("updated_at") or UNMEASURED,
                      "engine_pass": pass_ or UNMEASURED}
    return rows, meta


# ---------------------------------------------------------------- the engine's own gates
def _banned(family: str) -> bool:
    try:
        from family_policy import family_banned  # type: ignore[import-not-found]
        return bool(family_banned(family))
    except Exception:
        return False


def _engine_gate(run: Mapping[str, Any]) -> str | None:
    """The reason `shadow_forward.certified_sleeves` would not enrol this H1 run, or None.

    Mirrors the engine's own filters by CALLING them (family ban, window map, constructor, side),
    so the diagnostic and the engine cannot disagree about which certificates are runnable.
    """
    fam = str(run.get("family") or "session_range_breakout")
    if _banned(fam):
        return BANNED_FAMILY
    try:
        import shadow_forward as sf
    except Exception:
        return None
    if fam == "session_range_breakout":
        if str(run.get("selector") or "") not in sf.WINDOWS:
            return SELECTOR_UNMAPPED
    elif sf._family_fn(fam) is None:
        return FAMILY_UNBUILDABLE
    side = str(run.get("side") or "").upper()
    if side and side not in ("LONG", "SHORT"):
        return SIDE_UNRUNNABLE
    if side == "SHORT":
        fn = sf._family_fn(fam) if fam != "session_range_breakout" else None
        if fam != "session_range_breakout" and fn is None:
            return FAMILY_UNBUILDABLE
        try:
            if fn is not None and not sf._accepts_side(fn):
                return SIDE_UNRUNNABLE
        except Exception:
            return None
    return None


def _universe_symbols() -> set[str] | None:
    doc = _read_json(UNIVERSE / "universe.json")
    return set(doc) if isinstance(doc, dict) else None


def _timeframe(run: Mapping[str, Any]) -> str:
    return str(run.get("timeframe") or (run.get("params") or {}).get("timeframe")
               or "H1").upper()


def _bar_file(symbol: str, timeframe: str) -> bool:
    return (UNIVERSE / f"{symbol}_{timeframe}.parquet").exists()


def _policy_now(symbol: str, family: str) -> bool | None:
    try:
        from universe_policy import may_hypothesise  # type: ignore[import-not-found]
        return bool(may_hypothesise(symbol, family))
    except Exception:
        return None


def _stem(key: str) -> str:
    """The key without its param signature -- symbol, family, window and chart."""
    base = key.split("#", 1)[0]
    return base + (".SHORT" if key.endswith(".SHORT") and not base.endswith(".SHORT") else "")


def _near_keys(key: str, rows: Mapping[str, Any]) -> list[str]:
    stem = _stem(key)
    return sorted(k for k in rows if k != key and _stem(k) == stem)[:5]


def family_gap_hours(rows: Mapping[str, Mapping[str, Any]],
                     families: Mapping[str, str]) -> dict[str, float]:
    """family -> median hours between forward observations, from the desk's own rows."""
    per: dict[str, list[float]] = {}
    for key, row in rows.items():
        fam = families.get(key)
        n = row.get("n")
        if not fam or not isinstance(n, int) or n < 2:
            continue
        first, last = _parse_ts(row.get("first_entry")), _parse_ts(row.get("last_entry"))
        if first is None or last is None or last <= first:
            continue
        per.setdefault(fam, []).append((last - first).total_seconds() / 3600.0 / (n - 1))
    return {f: statistics.median(g) for f, g in per.items() if g}


def warming_hours(family: str, gaps: Mapping[str, float]) -> float:
    gap = gaps.get(family)
    return WARMING_FLOOR_H if gap is None else max(WARMING_FLOOR_H, gap * WARMING_MULTIPLE)


# ---------------------------------------------------------------- one certificate
def _status_reason(status: str) -> str | None:
    """A reason read off a non-working row status, or None when the status is working."""
    s = status.strip().upper()
    if s in WORKING:
        return None
    if s in DECIDED_STATUSES:
        return DECIDED
    if s in STATUS_REASON:
        return STATUS_REASON[s]
    if s.startswith("QUARANT"):
        return QUARANTINED
    if s.startswith(("RETIRED", "VOID")):
        return RETIRED_WHILE_CERTIFIED
    if s.startswith("REFUSED"):
        return UNIVERSE_POLICY_REFUSED if "UNIVERSE" in s else BLOCKED_UNNAMED
    if s == "BLOCKED_NO_BARS" or s == "NO_DATA":
        return NO_BARS                          # refined to BAR_FILE_MISSING by the caller
    if any(s.startswith(d + "_") for d in DECIDED_STATUSES):
        return DECIDED
    return BLOCKED_UNNAMED


def judge(run: Mapping[str, Any], lane: str, key: str | None, row: Mapping[str, Any] | None,
          lane_row_map: Mapping[str, Any] | None, *, ref: datetime, lane_age_h: float | None,
          host_live: bool, gaps: Mapping[str, float], universe: set[str] | None
          ) -> dict[str, Any]:
    """One certificate -> one entry carrying exactly one reason from `REASONS`."""
    symbol = str(run.get("symbol") or "")
    family = str(run.get("family") or "session_range_breakout")
    tf = _timeframe(run)
    entry: dict[str, Any] = {
        "certificate": str(run.get("certificate") or ""), "symbol": symbol, "family": family,
        "selector": str(run.get("selector") or ""), "side": str(run.get("side") or "LONG"),
        "timeframe": tf, "lane": lane, "key": key or UNMEASURED,
        "enrolled": row is not None if lane_row_map is not None else UNMEASURED,
        "status": UNMEASURED, "last_attempt_at": None, "last_entry": None, "n": UNMEASURED,
        "n_historical": UNMEASURED, "forward_start": None,
    }
    if row is not None:
        entry.update(status=str(row.get("status") or ""),
                     last_attempt_at=row.get("last_attempt_at") or row.get("last_source_bar"),
                     last_entry=row.get("last_entry") or row.get("first_trade_at"),
                     n=row.get("n", UNMEASURED), n_historical=row.get("n_historical", UNMEASURED),
                     forward_start=row.get("forward_start") or row.get("enrolled_at"))

    def done(reason: str, detail: str) -> dict[str, Any]:
        entry["reason"] = reason
        entry["accruing"] = reason in COMPLIANT
        entry["detail"] = detail
        return entry

    if key is None:
        return done(UNMEASURED, "the engine's sleeve_key could not be imported: key UNMEASURED")
    if lane_row_map is None:
        return done(UNMEASURED, f"lane file {lane} is absent or unreadable on this host")

    if row is None:
        gate = _engine_gate(run) if lane == H1_LANE else None
        if gate:
            return done(gate, f"shadow_forward.certified_sleeves refuses it ({gate}); no row is "
                              f"ever written. Owner: {OWNER.get(gate)}")
        if universe is not None and symbol and symbol not in universe:
            return done(SYMBOL_UNMAPPED, f"{symbol} is not in data/universe/universe.json")
        near = _near_keys(key, lane_row_map)
        if near:
            entry["near_keys"] = near
            return done(KEY_MISMATCH, f"no row under {key!r}, but {len(near)} row(s) for the same "
                                      f"symbol/family/window/chart exist under another key")
        return done(NOT_ENROLLED, "certified and holds no forward clock row in its lane")

    if lane == H1_LANE and _banned(family):
        return done(BANNED_FAMILY, f"family {family!r} is banned; the engine keeps the row as "
                                   f"residue and never advances it again")
    status = str(row.get("status") or "")
    sreason = _status_reason(status)
    if sreason == NO_BARS:
        present = _bar_file(symbol, tf)
        entry["bar_file_present"] = present
        entry["bars_wanted"] = {"symbol": symbol, "timeframe": tf}
        return done(NO_BARS if present else BAR_FILE_MISSING,
                    (f"no usable {tf} bars; the parquet exists, so it is stale or short"
                     if present else f"no usable {tf} bars and {symbol}_{tf}.parquet is absent "
                                     f"from the bar store"))
    if sreason == UNIVERSE_POLICY_REFUSED:
        entry["policy_admits_now"] = _policy_now(symbol, family)
        return done(sreason, "refused by universe_policy on the row's last pass"
                    + ("; the policy admits the symbol now, so the engine's next pass clears it"
                       if entry["policy_admits_now"] else ""))
    if sreason is not None:
        return done(sreason, str(row.get("last_error") or row.get("quarantine_reason")
                                 or row.get("status_why") or status)[:300])

    # A WORKING ROW. Has the lane's pass reached it?
    attempt = _parse_ts(entry["last_attempt_at"])
    if host_live and lane_age_h is not None and lane_age_h > SILENT_H:
        return done(ENGINE_NOT_REACHED, f"lane {lane} last written {lane_age_h:.1f}h ago on a "
                                        f"host that advances clocks (limit {SILENT_H:g}h)")
    since = _hours(ref, attempt)
    if attempt is None or (since is not None and since > SILENT_H):
        return done(ENGINE_NOT_REACHED,
                    "never attempted by the engine" if attempt is None else
                    f"last attempted {since:.1f}h before the lane's own last pass "
                    f"(limit {SILENT_H:g}h): the pass stopped before this row")

    n = row.get("n")
    n = n if isinstance(n, int) else 0
    if n > 0:
        return done(ACCRUING, f"{n} forward observation(s), last {entry['last_entry']}")
    started = _parse_ts(entry["forward_start"])
    age = _hours(ref, started)
    limit = warming_hours(family, gaps)
    entry["warming_limit_h"] = round(limit, 1)
    if age is None or age < limit:
        return done(WARMING, f"no observation yet, clock {age if age is None else round(age, 1)}h "
                             f"old, inside this family's {limit:.0f}h window")
    hist = row.get("n_historical")
    if isinstance(hist, int) and hist > 0:
        return done(NO_SIGNAL_SINCE_FORWARD_START,
                    f"{hist} historical signal(s) and none in {age:.0f}h since the clock froze")
    return done(GATE_NEVER_OPENS,
                f"not one signal in the whole replay window ({age:.0f}h forward, 0 historical): "
                f"the family's gate has never opened on the bars the engine gives it")


# ---------------------------------------------------------------- every enrolled clock
def _identity_of(lane: str, key: str, row: Mapping[str, Any],
                 registry: Mapping[str, Any]) -> dict[str, Any]:
    """A run-shaped description of a clock row: from its frozen identity, else from its key."""
    ident = (registry.get(key) or {}).get("identity") if isinstance(registry.get(key),
                                                                     dict) else None
    if isinstance(ident, dict):
        return {"certificate": key, "symbol": ident.get("symbol"),
                "family": ident.get("family"), "selector": ident.get("selector"),
                "side": ident.get("direction") or "LONG",
                "timeframe": ident.get("timeframe") or "H1"}
    if lane == SCALP_LANE:
        raw = row.get("choice")
        choice: Mapping[str, Any] = raw if isinstance(raw, dict) else {}
        return {"certificate": key, "symbol": row.get("symbol") or "XAUUSD",
                "family": choice.get("family"),
                "selector": key, "timeframe": row.get("timeframe") or "H1", "lane": "scalp"}
    if lane == QQUANT_LANE:
        return {"certificate": key, "family": "hunt16",
                "symbol": key.split(".")[3].split(" ")[0] if key.count(".") >= 3 else ""}
    base = key.split("#", 1)[0]
    chart = base.split("@", 1)[1].split(".")[0] if "@" in base else "H1"
    parts = base.split("@", 1)[0].split(".")
    fam = parts[1] if len(parts) > 2 else "session_range_breakout"
    sel = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
    return {"certificate": key, "symbol": parts[0], "family": fam, "selector": sel,
            "side": "SHORT" if key.endswith(".SHORT") else "LONG", "timeframe": chart}


def clock_census(rows: Mapping[str, Mapping[str, Mapping[str, Any]]],
                 meta: Mapping[str, Any], *, ref: Mapping[str, datetime],
                 ages: Mapping[str, float | None], host_live: bool,
                 gaps: Mapping[str, float], now: datetime,
                 roster: set[str] | None = None) -> dict[str, Any]:
    """Every ENROLLED clock (a row that is neither retired nor decided), whatever canon says.

    The certificate census above is the law's unit; this is the operator's: a lane can carry
    clocks for certificates the canon on this host no longer lists (the box's canon runs ahead of
    any copy), and those clocks still either accrue or do not.
    """
    registry_doc = _read_json(DESK / "data" / "sleeve_registry.json")
    registry = (registry_doc.get("sleeves") or {}) if isinstance(registry_doc, dict) else {}
    out: list[dict[str, Any]] = []
    for lane, lmap in rows.items():
        for key, row in lmap.items():
            status = str(row.get("status") or "").strip().upper()
            if status.startswith(("RETIRED", "VOID")):
                continue
            run = _identity_of(lane, key, row, registry)
            e = judge(run, lane, key, row, lmap, ref=ref.get(lane, now),
                      lane_age_h=ages.get(lane), host_live=host_live, gaps=gaps, universe=None)
            if e["reason"] == DECIDED:
                continue
            if (e["reason"] == ENGINE_NOT_REACHED and lane == H1_LANE and roster is not None
                    and key not in roster):
                e["reason"] = OFF_ROSTER
                e["detail"] = ("no certificate on this host's canon maps to this key, so the "
                               "engine's roster never visits it; " + str(e.get("detail") or ""))
            out.append({k: e.get(k) for k in ("key", "lane", "symbol", "family", "timeframe",
                                              "status", "last_attempt_at", "last_entry", "n",
                                              "reason", "detail")})
    by: dict[str, int] = {}
    for e in out:
        by[e["reason"]] = by.get(e["reason"], 0) + 1
    non = {r: c for r, c in by.items() if r not in COMPLIANT}
    return {
        "n_enrolled": len(out),
        "n_accruing": by.get(ACCRUING, 0), "n_warming": by.get(WARMING, 0),
        "n_non_accruing": sum(non.values()),
        "non_accruing_by_reason": dict(sorted(non.items(), key=lambda kv: (-kv[1], kv[0]))),
        "clocks": [e for e in out if e["reason"] not in COMPLIANT],
        "rule": "every lane row that is neither retired nor decided, judged by the same enum",
    }


# ---------------------------------------------------------------- the census
def certificates() -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """Every authorized run in both lanes, every admission drop, and an error string."""
    try:
        from shadow_admission import (  # type: ignore[import-not-found]
            DROPPED_CERTIFICATES,
            authorized_runs,
        )
        runs = list(authorized_runs(DESK, lanes=("h1", "scalp")))
        return runs, list(DROPPED_CERTIFICATES), ""
    except Exception as exc:
        return [], [], f"{type(exc).__name__}: {exc}"


def build(now: datetime | None = None, shadow_dir: Path | None = None,
          runs: list[dict[str, Any]] | None = None,
          dropped: list[dict[str, Any]] | None = None,
          host_live: bool | None = None) -> dict[str, Any]:
    t = _now(now)
    why = ""
    if runs is None:
        runs, dropped, why = certificates()
    dropped = list(dropped or [])
    live = host_runs_clocks() if host_live is None else bool(host_live)
    rows, meta = lane_rows(shadow_dir)
    lane_ref: dict[str, datetime] = {}
    lane_age: dict[str, float | None] = {}
    for lane, m in meta.items():
        up = _parse_ts(m.get("updated_at")) if isinstance(m, dict) else None
        lane_age[lane] = _hours(t, up)
        lane_ref[lane] = t if (live or up is None) else up

    addresses = [(run, *clock_address(run)) for run in runs]
    fam_by_key = {key: str(run.get("family") or "") for run, _lane, key in addresses if key}
    all_rows: dict[str, dict[str, Any]] = {}
    for lane_rows_ in rows.values():
        for k, r in lane_rows_.items():
            all_rows.setdefault(k, r)
    gaps = family_gap_hours(all_rows, fam_by_key)
    universe = _universe_symbols()

    entries: list[dict[str, Any]] = []
    for run, lane, key in addresses:
        lmap = rows.get(lane)
        row = lmap.get(key) if (lmap is not None and key) else None
        age = lane_age.get(lane)
        entries.append(judge(run, lane, key, row, lmap, ref=lane_ref.get(lane, t),
                             lane_age_h=age, host_live=live, gaps=gaps, universe=universe))
    for d in dropped:
        name = str(d.get("certificate") or "")
        if name.startswith("qquant."):
            # hunt16 certificates carry no H1 params by design: `qquant_shadow` owns them and
            # keys the clock by the certificate's own name, so the admission drop is not a
            # verdict on whether they have a clock.
            qrun = {"certificate": name, "family": "hunt16", "symbol": name.split(".")[3]
                    .split(" ")[0] if name.count(".") >= 3 else ""}
            lane, key = clock_address(qrun)
            lmap = rows.get(lane)
            entries.append(judge(qrun, lane, key,
                                 lmap.get(key) if (lmap is not None and key) else None,
                                 lmap, ref=lane_ref.get(lane, t), lane_age_h=lane_age.get(lane),
                                 host_live=live, gaps=gaps, universe=None))
            continue
        entries.append({"certificate": str(d.get("certificate") or ""), "lane": UNMEASURED,
                        "key": UNMEASURED, "enrolled": False, "status": UNMEASURED,
                        "last_attempt_at": None, "last_entry": None, "n": UNMEASURED,
                        "reason": PARAMS_UNRESOLVED, "accruing": False,
                        "detail": str(d.get("why") or "")[:300]})

    by_reason: dict[str, int] = {}
    for e in entries:
        by_reason[e["reason"]] = by_reason.get(e["reason"], 0) + 1
    non = {r: c for r, c in by_reason.items() if r not in COMPLIANT}
    measured = not why and bool(meta.get(H1_LANE, {}).get("readable"))
    wanted: dict[tuple[str, str], int] = {}
    for e in entries:
        w = e.get("bars_wanted")
        if isinstance(w, dict):
            cell = (str(w.get("symbol")), str(w.get("timeframe")))
            wanted[cell] = wanted.get(cell, 0) + 1

    roster = ({key for _run, lane, key in addresses if key and lane == H1_LANE}
              if not why else None)
    clocks = clock_census(rows, meta, ref=lane_ref, ages=lane_age, host_live=live, gaps=gaps,
                          now=t, roster=roster)
    cert_keys = {e["key"] for e in entries if e.get("key") not in (None, UNMEASURED)}
    uncertified_working = sorted(
        k for k, r in rows.get(H1_LANE, {}).items()
        if k not in cert_keys and str(r.get("status") or "").strip().upper() in WORKING)

    doc: dict[str, Any] = {
        "at": t.isoformat(timespec="seconds"),
        "status": "MEASURED" if measured else UNMEASURED,
        "why": why or ("" if measured else "the H1 lane state file is absent or unreadable"),
        "host_runs_clocks": live,
        "judged_as_of": ("now" if live else
                         "each lane's own last pass (this host advances no clock; lane files are "
                         "copies, so their age is published instead of convicting every row)"),
        "headline": {
            "n_certificates": len(entries) if measured else UNMEASURED,
            "n_enrolled": (sum(1 for e in entries if e.get("enrolled") is True)
                           if measured else UNMEASURED),
            "n_accruing": by_reason.get(ACCRUING, 0) if measured else UNMEASURED,
            "n_warming": by_reason.get(WARMING, 0) if measured else UNMEASURED,
            "n_decided": by_reason.get(DECIDED, 0) if measured else UNMEASURED,
            "n_non_accruing": sum(non.values()) if measured else UNMEASURED,
            "non_accruing_by_reason": (dict(sorted(non.items(), key=lambda kv: (-kv[1], kv[0])))
                                       if measured else UNMEASURED),
        },
        "enrolled_clocks": ({k: v for k, v in clocks.items() if k != "clocks"}
                            if measured else UNMEASURED),
        "owners": {r: OWNER[r] for r in set(non) | set(clocks["non_accruing_by_reason"])
                   if r in OWNER},
        "lanes": {lane: {**m, "age_h": _round_or_unmeasured(lane_age.get(lane))}
                  for lane, m in meta.items()},
        "family_gap_hours": {k: round(v, 2) for k, v in sorted(gaps.items())},
        "bars_wanted": [{"symbol": s, "timeframe": tf, "clocks": n}
                        for (s, tf), n in sorted(wanted.items(), key=lambda kv: -kv[1])],
        "uncertified_working_clocks": {"n": len(uncertified_working),
                                       "keys": uncertified_working[:50],
                                       "why": "working rows in the H1 lane that no certificate "
                                              "in this canon maps to; forward_reconcile owns "
                                              "them, and they are not in the headline"},
        "reasons": list(REASONS),
        "certificates": entries,
        "non_accruing_clocks": clocks["clocks"] if measured else [],
        "rule": ("one reason per certificate, from the enum in `reasons`. ACCRUING, WARMING and "
                 "DECIDED are the clock doing its job; every other reason is a certificate that "
                 "cannot mature and therefore cannot be promoted, and `owners` names the organ "
                 "that fixes it. Unreadable is UNMEASURED, never zero."),
    }
    return doc


def _round_or_unmeasured(v: float | None) -> float | str:
    return UNMEASURED if v is None else round(v, 2)


def write(doc: Mapping[str, Any], target: Path | None = None) -> Path:
    path = Path(target or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def bars_wanted(report: Path | None = None) -> list[tuple[str, str]]:
    """(symbol, timeframe) cells forward clocks are waiting for, most clocks first.

    The consumer contract for the bar collectors: an absent or unreadable report is an empty
    list, never an error, so collection order degrades to what it was.
    """
    doc = _read_json(Path(report or OUT))
    rows = doc.get("bars_wanted") if isinstance(doc, dict) else None
    out: list[tuple[str, str]] = []
    for w in rows if isinstance(rows, list) else []:
        if isinstance(w, dict) and w.get("symbol") and w.get("timeframe"):
            out.append((str(w["symbol"]), str(w["timeframe"]).upper()))
    return out


def render(doc: Mapping[str, Any]) -> str:
    h = doc.get("headline") or {}
    lines = [f"CLOCK ACCRUAL [{doc.get('status')}]  certificates={h.get('n_certificates')} "
             f"enrolled={h.get('n_enrolled')} accruing={h.get('n_accruing')} "
             f"warming={h.get('n_warming')} decided={h.get('n_decided')} "
             f"NON-ACCRUING={h.get('n_non_accruing')}"]
    by = h.get("non_accruing_by_reason")
    if isinstance(by, dict):
        for r, c in by.items():
            lines.append(f"    {r:32s} {c:5d}   -> {OWNER.get(r, '')}")
    ec = doc.get("enrolled_clocks")
    if isinstance(ec, dict):
        lines.append(f"  ENROLLED CLOCKS {ec.get('n_enrolled')}: accruing={ec.get('n_accruing')} "
                     f"warming={ec.get('n_warming')} NON-ACCRUING={ec.get('n_non_accruing')}")
        for r, c in (ec.get("non_accruing_by_reason") or {}).items():
            lines.append(f"    {r:32s} {c:5d}")
    for lane, m in (doc.get("lanes") or {}).items():
        lines.append(f"  lane {lane}: age {m.get('age_h')}h rows {m.get('rows', UNMEASURED)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="measure and write the artifact")
    ap.add_argument("--print", dest="show", action="store_true", help="print, do not write")
    args = ap.parse_args(argv)
    doc = build()
    if not args.show:
        write(doc)
    print(render(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
