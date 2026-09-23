"""ONE JOINED DOCUMENT, so the dashboard can never disagree with the desk.

WHY THIS EXISTS. Every number the principal wants on a phone is already measured somewhere on this
box -- the canon in `CERTIFICATE_TRUTH.json`, the defects in `PLUMBING_WATCHDOG.json` and
`BATTERY_FENCES.json`, the money in `gateway_state.json` and `live_ledger.jsonl`, the producers in
`PRODUCTIVITY_CENSUS.json`, the funnel in `RESEARCH_PRODUCTIVITY.json`, the binding constraint in
`BOTTLENECK_ATTACK.json`, the macro lane in `MACRO_VIEW.json` / `MACRO_STATE_ENGINE.json` /
`EVENT_SURPRISE.json` / `EVENT_RESPONSE_ATLAS.json` / `forced_flow_calendar.json` /
`REGIME_ROUTER.json`. What was missing was ONE document that joins them on the identity the desk
already trades on, so a page cannot quietly show a certificate the promoter does not hold, or a
clock the registry retired.

THE JOIN IS THE POINT. `certificate_truth.parts(symbol, family, selector)` is the canonical
identity stamped at birth (2026-09-23); certificates, forward clocks and live sleeves are joined
through it and through `certificate_truth.row_identity`, never by string-matching a name. A
certificate with no clock says so, a clock with no certificate says so, and neither is hidden.

AGE IS A VALUE, NOT A DECORATION. Every field carries the artifact it came from and how old that
artifact is. A section whose source is older than its declared staleness horizon renders STALE; an
artifact that is absent renders MISSING with the organ that should have written it; a measurement
the desk genuinely does not hold renders UNMEASURED with its reason (L1.28a). Nothing here ever
renders an absence as a zero -- a zero is a claim, and this organ measures rather than claims.

IT MOVES NOTHING. Read-only over the desk's artifacts; it writes its own report and merges itself
into the display payload. It sizes nothing, gates nothing, and no organ reads it back to decide.

    desks/mt5/reports/DESK_DASHBOARD_STATE.json   the joined document
    web/desk_state.json ["dashboard"]             the same document inside the payload the page
                                                  already fetches -- EXTENDED, never a second file
                                                  (`scripts/build_zentech_state.py` re-injects it
                                                  on its own 15-minute publish so the block
                                                  survives a republish)
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.certificate_truth import parts, row_identity  # noqa: E402

OUT = DESK / "reports" / "DESK_DASHBOARD_STATE.json"
WEB = ROOT / "web" / "desk_state.json"
#: The leg's cadence. The page compares the document's own age to this and says so at the top
#: BEFORE any number when the document is older -- an old number presented as current is the one
#: failure mode a dashboard must not have.
CADENCE_S = 3600.0

MEASURED, STALE, MISSING, UNMEASURED, UNREADABLE = (
    "MEASURED", "STALE", "MISSING", "UNMEASURED", "UNREADABLE")


def _now() -> datetime:
    return datetime.now(UTC)


def _human_age(seconds: float | None) -> str:
    if seconds is None:
        return UNMEASURED
    s = int(max(0.0, seconds))
    if s < 90:
        return f"{s}s"
    if s < 5400:
        return f"{s // 60}m"
    if s < 172800:
        return f"{s // 3600}h {(s % 3600) // 60}m"
    return f"{s // 86400}d {(s % 86400) // 3600}h"


class Src:
    """One artifact, read once, carrying its own age and verdict."""

    def __init__(self, rel: str, stale_s: float, owner: str = "") -> None:
        self.rel = rel
        self.stale_s = float(stale_s)
        self.owner = owner
        self.path = ROOT / rel
        self.doc: Any = None
        self.age_s: float | None = None
        self.why = ""
        if not self.path.exists():
            self.status = MISSING
            self.why = (f"{rel} is absent on this host"
                        + (f"; {owner} is its writer" if owner else ""))
            return
        try:
            self.age_s = max(0.0, time.time() - self.path.stat().st_mtime)
            self.doc = json.loads(self.path.read_text("utf-8", errors="replace"))
        except (OSError, ValueError) as exc:
            self.status = UNREADABLE
            self.why = f"{rel} could not be read: {type(exc).__name__}: {exc}"
            return
        self.status = MEASURED
        if self.age_s is not None and self.age_s > self.stale_s:
            self.status = STALE
            self.why = (f"{rel} is {_human_age(self.age_s)} old, past its "
                        f"{_human_age(self.stale_s)} horizon"
                        + (f"; {owner} should have rewritten it" if owner else ""))

    @property
    def d(self) -> dict[str, Any]:
        return self.doc if isinstance(self.doc, dict) else {}

    def cite(self) -> dict[str, Any]:
        return {"source": self.rel, "age_s": (round(self.age_s, 1) if self.age_s is not None
                                              else None),
                "age": _human_age(self.age_s), "status": self.status, "why": self.why}

    def field(self, value: Any, why_absent: str = "") -> dict[str, Any]:
        """A value with its provenance. An absent value is UNMEASURED with a reason, never 0."""
        cite = self.cite()
        if self.status in (MISSING, UNREADABLE):
            cite["value"] = None
            return cite
        if value is None:
            cite["status"] = UNMEASURED
            cite["why"] = why_absent or f"{self.rel} does not publish this field"
            cite["value"] = None
            return cite
        cite["value"] = value
        return cite


def _dig(doc: Any, *path: str, default: Any = None) -> Any:
    cur = doc
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _find_key(doc: Any, *needles: str, depth: int = 2) -> tuple[Any, str] | None:
    """The first numeric field whose name carries every needle, with the path that found it.

    A dashboard that hard-codes one key name goes blind the day the producer renames it; this
    reports the path it used so the reader can check the join rather than trust it."""
    if not isinstance(doc, dict) or depth < 0:
        return None
    for key, val in doc.items():
        low = str(key).lower()
        if all(n in low for n in needles) and isinstance(val, (int, float)) and not isinstance(
                val, bool):
            return val, str(key)
    for key, val in doc.items():
        if isinstance(val, dict):
            found = _find_key(val, *needles, depth=depth - 1)
            if found is not None:
                return found[0], f"{key}.{found[1]}"
    return None


def _age_of_iso(stamp: Any) -> float | None:
    if not isinstance(stamp, str) or not stamp.strip():
        return None
    text = stamp.strip().replace("Z", "+00:00")
    with contextlib.suppress(ValueError):
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0.0, (_now() - parsed).total_seconds())
    return None


def _seconds_until(stamp: Any) -> float | None:
    """Seconds from now to a stamp, POSITIVE into the future. `_age_of_iso` clamps at zero, which
    is right for an artifact's age and wrong for a release that has not happened yet."""
    if not isinstance(stamp, str) or not stamp.strip():
        return None
    with contextlib.suppress(ValueError):
        parsed = datetime.fromisoformat(stamp.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return (parsed - _now()).total_seconds()
    return None


def _tail_rows(path: Path, nbytes: int, limit: int) -> list[dict[str, Any]]:
    """The last rows of a JSONL file without reading the whole file -- news_captures is 50 MB."""
    rows: list[dict[str, Any]] = []
    try:
        with path.open("rb") as handle:
            size = path.stat().st_size
            handle.seek(max(0, size - nbytes))
            chunk = handle.read().decode("utf-8", "replace")
    except OSError:
        return rows
    lines = chunk.splitlines()
    if size > nbytes and lines:
        lines = lines[1:]
    for line in lines[-limit:]:
        with contextlib.suppress(ValueError):
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _all_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text("utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        if not line.strip():
            continue
        with contextlib.suppress(ValueError):
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _stats(values: list[float]) -> dict[str, Any]:
    """Mean, sd and per-trade Sharpe -- UNMEASURED below two observations, never 0.0."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sd": None, "sharpe": None,
                "why": "no trades in the ledger for this key"}
    mean = sum(values) / n
    if n < 2:
        return {"n": n, "mean": round(mean, 4), "sd": None, "sharpe": None,
                "why": "n=1: a dispersion needs two observations"}
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return {"n": n, "mean": round(mean, 4), "sd": 0.0, "sharpe": None,
                "why": "sd=0: every observation identical, a ratio is undefined"}
    return {"n": n, "mean": round(mean, 4), "sd": round(sd, 4),
            "sharpe": round(mean / sd, 4), "why": ""}


# ------------------------------------------------------------------------------------- CANON
def _canon(deadline: float) -> dict[str, Any]:
    ct = Src("desks/mt5/reports/CERTIFICATE_TRUTH.json", 7200,
             "desks/mt5/research/certificate_truth.py")
    us = Src("desks/mt5/reports/UNIVERSAL_SURVIVORS.json", 86400,
             "desks/mt5/scripts/external_gauntlet.py")
    reg = Src("desks/mt5/data/sleeve_registry.json", 86400,
              "desks/mt5/research/sleeve_registry.py")
    sl = Src("desks/mt5/data/sleeves.json", 86400, "desks/mt5/research/promoter.py")

    clocks: dict[str, list[dict[str, Any]]] = {}
    reg_rows = _dig(reg.doc, "sleeves", default={})
    if isinstance(reg_rows, dict):
        for key, row in reg_rows.items():
            if not isinstance(row, dict):
                continue
            ident = row_identity("sleeve_registry", str(key), row)
            pk = parts(ident.get("symbol"), ident.get("family"), ident.get("selector"))
            clocks.setdefault(pk, []).append({
                "clock": str(key), "status": row.get("status"),
                "forward_start": row.get("forward_start"),
                "age_s": _age_of_iso(row.get("forward_start")),
                "age": _human_age(_age_of_iso(row.get("forward_start")))})

    live_keys: dict[str, dict[str, Any]] = {}
    sl_rows = _dig(sl.doc, "sleeves", default=[])
    if isinstance(sl_rows, list):
        for row in sl_rows:
            if not isinstance(row, dict):
                continue
            ident = row_identity("sleeves", str(row.get("name") or ""), row)
            live_keys[parts(ident.get("symbol"), ident.get("family"),
                            ident.get("selector"))] = {
                "sleeve": row.get("name"), "status": row.get("status"),
                "symbol": row.get("symbol"), "timeframe": row.get("timeframe")}

    # THE STORE IS WRITTEN IN TWO SHAPES and both are live on this desk: a list of certificate
    # keys, and a dict of key -> the judged row. Reading only one of them is how a dashboard
    # shows an empty canon while the desk holds 28 certificates.
    survivors = _dig(us.doc, "survivors", default=[])
    pairs: list[tuple[str, dict[str, Any]]] = []
    if isinstance(survivors, dict):
        pairs = [(str(k), v if isinstance(v, dict) else {}) for k, v in survivors.items()]
    elif isinstance(survivors, list):
        pairs = [(str(k), {}) for k in survivors]
    rows: list[dict[str, Any]] = []
    if pairs:
        for key, cert in pairs:
            if time.time() > deadline:
                break
            ident = row_identity("UNIVERSAL_SURVIVORS", str(key), {})
            pk = parts(ident.get("symbol"), ident.get("family"), ident.get("selector"))
            backing = clocks.get(pk, [])
            accruing = [c for c in backing if str(c.get("status") or "").upper() in
                        ("LIVE", "STANDBY", "FORWARD", "ACCRUING")]
            live = live_keys.get(pk)
            rows.append({
                "certificate": str(key), "identity": pk,
                "symbol": ident.get("symbol"), "family": ident.get("family"),
                "selector": ident.get("selector"), "timeframe": ident.get("timeframe"),
                "clocks": [c["clock"] for c in backing][:6],
                "clock_status": ([str(c.get("status")) for c in accruing][:3] or
                                 [str(c.get("status")) for c in backing][:3] or None),
                "clock_age": (_human_age(max((c["age_s"] for c in backing
                                              if c["age_s"] is not None), default=None))
                              if backing else UNMEASURED),
                "clock_why": ("" if backing else
                              "no row in data/sleeve_registry.json joins this identity"),
                "days": cert.get("days"),
                "live": bool(live), "live_sleeve": (live or {}).get("sleeve")})

    n_backed = sum(1 for r in rows if r["clocks"])
    canon_block = _dig(ct.doc, "canon", default={}) or {}
    return {
        "status": ct.status if ct.status != MEASURED else us.status,
        "sources": [ct.cite(), us.cite(), reg.cite(), sl.cite()],
        "n_certificates": ct.field(canon_block.get("n"),
                                   "CERTIFICATE_TRUTH.json carries no canon.n"),
        "canon_status": ct.field(canon_block.get("status")),
        "canon_store": ct.field(canon_block.get("source")),
        "scalp_n": ct.field(canon_block.get("scalp_n")),
        "retired": us.field(len(_dig(us.doc, "retired_certificates") or [])
                            if isinstance(_dig(us.doc, "retired_certificates"), (list, dict))
                            else None),
        "swept_at": us.field(_dig(us.doc, "swept_at")),
        "n_backed_by_clock": us.field(n_backed if rows else None,
                                      "no survivor rows to join"),
        "n_live": us.field(sum(1 for r in rows if r["live"]) if rows else None,
                           "no survivor rows to join"),
        "certificate_age": {"status": UNMEASURED,
                            "why": ("UNIVERSAL_SURVIVORS.json records one sweep time for the whole "
                                    "store (swept_at) and no per-certificate birth, so a "
                                    "certificate's own age is not measured on this host; the "
                                    "backing clock's forward_start is shown instead"),
                            "source": "desks/mt5/reports/UNIVERSAL_SURVIVORS.json"},
        "divergences": ct.field(_dig(ct.doc, "n_divergences")),
        "divergences_fatal": ct.field(_dig(ct.doc, "n_fatal")),
        "join_coverage": ct.field(_dig(ct.doc, "one_lane", "join", "total_joinable")),
        "join_denominator": ct.field(_dig(ct.doc, "one_lane", "join", "total_denominator")),
        "rows": rows,
    }


# ----------------------------------------------------------------------------------- DEFECTS
def _defects(deadline: float) -> dict[str, Any]:
    pw = Src("desks/mt5/reports/PLUMBING_WATCHDOG.json", 3600,
             "desks/mt5/research/plumbing_watchdog.py")
    fen = Src("desks/mt5/reports/BATTERY_FENCES.json", 7200,
              "desks/mt5/research/battery_fences.py")

    rows: list[dict[str, Any]] = []
    raw = _dig(pw.doc, "defects", default=[])
    windows = _dig(pw.doc, "escalation_windows_s", default={}) or {}
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict) or time.time() > deadline:
                break
            age = _age_of_iso(row.get("first_seen"))
            window = windows.get(str(row.get("check"))) if isinstance(windows, dict) else None
            rows.append({
                "check": row.get("check"), "owner": row.get("organ") or row.get("check"),
                "severity": row.get("severity"), "evidence": str(row.get("evidence") or "")[:220],
                "repair": str(row.get("repair") or "")[:220],
                "first_seen": row.get("first_seen"), "age_s": age, "age": _human_age(age),
                "past_window": (bool(age is not None and window and age > float(window))
                                if window else None),
                "key": row.get("key")})
    rows.sort(key=lambda r: (-(r.get("age_s") or 0.0),))

    failing = _dig(fen.doc, "failing", default=[]) or []
    ran = _dig(fen.doc, "ran", default=[]) or []
    never = _dig(fen.doc, "never_run", default=[]) or []
    fences: list[dict[str, Any]] = []
    if isinstance(failing, list):
        fences += [{"fence": str(f), "verdict": "FAILING", "age": _human_age(fen.age_s),
                    "owner": str(f), "why": ""} for f in failing]
    if isinstance(ran, list):
        fences += [{"fence": str(f), "verdict": "PASSING", "age": _human_age(fen.age_s),
                    "owner": str(f), "why": ""} for f in ran if f not in (failing or [])]
    if isinstance(never, list):
        fences += [{"fence": str(f), "verdict": UNMEASURED, "age": _human_age(fen.age_s),
                    "owner": str(f),
                    "why": "this fence has never run on this host, so it has no verdict to give"}
                   for f in never]

    return {
        "status": pw.status,
        "sources": [pw.cite(), fen.cite()],
        "plumbing_moving": pw.field(_dig(pw.doc, "PLUMBING_MOVING")),
        "n_open": pw.field(_dig(pw.doc, "n_defects")),
        "n_escalated": pw.field(_dig(pw.doc, "n_escalated")),
        "n_past_window": pw.field(_dig(pw.doc, "n_past_escalation_window")),
        "n_fences_rostered": fen.field(_dig(fen.doc, "rostered")),
        "n_fences_failing": fen.field(len(failing) if isinstance(failing, list) else None),
        "n_fences_never_run": fen.field(_dig(fen.doc, "n_never_run")),
        "rows": rows[:90],
        "rows_truncated": max(0, len(rows) - 90),
        "fences": fences[:60],
    }


# -------------------------------------------------------------------------------------- LIVE
def _live(deadline: float) -> dict[str, Any]:
    gw = Src("desks/mt5/data/gateway_state.json", 3600, "desks/mt5/gateway.py")
    guard = Src("desks/mt5/data/e8_guard_state.json", 86400, "the E8 guard")
    e8g = Src("desks/mt5/reports/E8_GOLD.json", 7200, "desks/mt5/research/e8_gold.py")
    e8x = Src("desks/mt5/reports/E8_EXEC.json", 7200, "the E8 executor")
    led_path = DESK / "data" / "live_ledger.jsonl"
    led_age = (max(0.0, time.time() - led_path.stat().st_mtime) if led_path.exists() else None)
    rows = _all_rows(led_path) if led_path.exists() and time.time() < deadline else []
    led_cite = {"source": "desks/mt5/data/live_ledger.jsonl", "age_s": led_age,
                "age": _human_age(led_age),
                "status": (MEASURED if rows else (MISSING if led_age is None else UNMEASURED)),
                "why": ("" if rows else
                        "the live ledger holds no reconstructible deals on this host")}

    today = _now().date().isoformat()
    per: dict[str, dict[str, Any]] = {}
    day_pnl = 0.0
    day_n = 0
    for row in rows:
        name = str(row.get("sleeve") or "UNATTRIBUTED")
        bucket = per.setdefault(name, {"sleeve": name, "symbol": row.get("symbol"),
                                       "n": 0, "pnl": 0.0, "r": [], "last": None})
        bucket["n"] = int(bucket["n"]) + 1
        with contextlib.suppress(TypeError, ValueError):
            bucket["pnl"] = float(bucket["pnl"]) + float(row.get("pl_quote") or 0.0)
        rm = row.get("r_multiple")
        if isinstance(rm, (int, float)) and not isinstance(rm, bool):
            bucket["r"].append(float(rm))
        stamp = str(row.get("time") or "")
        if stamp > str(bucket["last"] or ""):
            bucket["last"] = stamp
        if stamp[:10] == today:
            day_n += 1
            with contextlib.suppress(TypeError, ValueError):
                day_pnl += float(row.get("pl_quote") or 0.0)

    sleeves: list[dict[str, Any]] = []
    for bucket in per.values():
        stats = _stats(list(bucket["r"]))
        age = _age_of_iso(bucket["last"])
        sleeves.append({"sleeve": bucket["sleeve"], "symbol": bucket["symbol"],
                        "n": bucket["n"], "pnl": round(float(bucket["pnl"]), 2),
                        "r_mean": stats["mean"], "r_sd": stats["sd"], "sharpe": stats["sharpe"],
                        "sharpe_why": stats["why"], "last": bucket["last"],
                        "age": _human_age(age), "age_s": age})
    sleeves.sort(key=lambda s: -(s["pnl"] or 0.0))
    book = _stats([float(v) for b in per.values() for v in b["r"]])

    return {
        "status": gw.status,
        "sources": [gw.cite(), led_cite, guard.cite(), e8g.cite(), e8x.cite()],
        "equity": gw.field(_dig(gw.doc, "equity")),
        "armed": gw.field(_dig(gw.doc, "armed")),
        "last_reconcile": gw.field(_dig(gw.doc, "last_reconcile")),
        "open_position": gw.field(_dig(gw.doc, "position"),
                                  "the gateway reports no open position"),
        "placement_last_ok": gw.field(_dig(gw.doc, "placement_health", "last_ok")),
        "day_pnl": {**led_cite, "value": (round(day_pnl, 2) if rows else None),
                    "status": (MEASURED if rows else led_cite["status"]),
                    "why": ("" if rows else str(led_cite["why"]))},
        "day_trades": {**led_cite, "value": (day_n if rows else None)},
        "trades_total": {**led_cite, "value": (len(rows) if rows else None)},
        "pnl_total": {**led_cite,
                      "value": (round(sum(float(b["pnl"]) for b in per.values()), 2)
                                if rows else None)},
        "book_r_mean": {**led_cite, "value": book["mean"], "why": book["why"]},
        "book_sharpe": {**led_cite, "value": book["sharpe"], "why": book["why"],
                        "basis": "per-trade Sharpe = mean(R) / sd(R) over reconstructible deals"},
        "sleeves": sleeves,
        "e8": {
            "equity": e8g.field(_dig(e8g.doc, "equity")),
            "armed": e8g.field(_dig(e8g.doc, "armed")),
            "risk_usd": e8g.field(_dig(e8g.doc, "risk_usd")),
            "day_start": guard.field(_dig(guard.doc, "day_start")),
            "peak_equity": guard.field(_dig(guard.doc, "peak_equity")),
            "stood_down": guard.field(_dig(guard.doc, "stood_down")),
            "guard_verdict": e8x.field(_dig(e8x.doc, "guard", "verdict")),
            "guard_why": e8x.field(_dig(e8x.doc, "guard", "why")),
            "guard_day_pnl": e8x.field(_dig(e8x.doc, "guard", "day_pnl")),
            "room_to_daily_floor": e8x.field(_dig(e8x.doc, "guard", "room_to_daily_floor")),
            "may_open": e8x.field(_dig(e8x.doc, "guard", "may_open")),
            "n_sent": e8x.field(_dig(e8x.doc, "n_sent")),
        },
    }


# --------------------------------------------------------------------------------- PRODUCERS
_PROD_FIELDS = (
    ("cells", ("raw_cells", "cells", "cells_emitted")),
    ("unique_cells", ("unique_cells", "unique_by_content_hash")),
    ("cells_judged", ("cells_judged", "judged", "judged_cells")),
    ("certificates", ("certificates", "n_certificates")),
    ("orthogonality_added", ("orthogonality_added", "orthogonality", "orthogonal_cells",
                             "effective_cells")),
    ("compute_hours", ("compute_hours", "compute_h", "compute")),
)


def _producers(deadline: float) -> dict[str, Any]:
    pc = Src("desks/mt5/reports/PRODUCTIVITY_CENSUS.json", 7200,
             "desks/mt5/research/productivity_census.py")
    pr = Src("desks/mt5/reports/PRODUCER_CENSUS.json", 21600,
             "desks/mt5/research/producer_census.py")

    raw = None
    from_key = ""
    for key in ("producers", "rows", "by_producer", "top_by_certificates"):
        cand = _dig(pc.doc, key)
        if isinstance(cand, list) and cand:
            raw, from_key = cand, key
            break
    rows: list[dict[str, Any]] = []
    if raw is not None:
        for row in raw:
            if not isinstance(row, dict) or time.time() > deadline:
                break
            out: dict[str, Any] = {"producer": row.get("producer") or row.get("key"),
                                   "region": row.get("region"), "kind": row.get("kind")}
            for label, names in _PROD_FIELDS:
                value: Any = None
                for name in names:
                    if isinstance(row.get(name), (int, float)) and not isinstance(
                            row.get(name), bool):
                        value = row[name]
                        break
                out[label] = value if value is not None else UNMEASURED
            rows.append(out)
        rows.sort(key=lambda r: -(r["certificates"] if isinstance(r["certificates"], (int, float))
                                  else -1))

    return {
        "status": pc.status,
        "table_source": (f"PRODUCTIVITY_CENSUS.{from_key}" if raw is not None else UNMEASURED),
        "sources": [pc.cite(), pr.cite()],
        "n_producers": pc.field(_dig(pc.doc, "n_producers")),
        "n_productive": pc.field(_dig(pc.doc, "n_productive")),
        "n_zero_cell_with_compute": pc.field(_dig(pc.doc, "n_zero_cell_with_compute")),
        "window_days": pc.field(_dig(pc.doc, "window_days")),
        "totals": pc.field(_dig(pc.doc, "totals")),
        "dedup": pc.field(_dig(pc.doc, "dedup")),
        "compute_note": pc.field(_dig(pc.doc, "compute_ledger_note")),
        "liveness_census": pr.field(_dig(pr.doc, "census"),
                                    "PRODUCER_CENSUS.json carries no census block"),
        "liveness_basis": ("PRODUCER_CENSUS measures whether a producer RUNS (LIVE/DARK/SLOW), "
                           "which is a different question from what it PRODUCED"),
        "rows": rows[:60],
        "rows_truncated": max(0, len(rows) - 60) if rows else 0,
        "why": (pc.why if pc.status != MEASURED else
                ("" if rows else
                 "PRODUCTIVITY_CENSUS.json holds no per-producer row this organ could read")),
    }


# ------------------------------------------------------------------------------------ FUNNEL
def _funnel(deadline: float) -> dict[str, Any]:
    pc = Src("desks/mt5/reports/PRODUCTIVITY_CENSUS.json", 7200,
             "desks/mt5/research/productivity_census.py")
    rp = Src("desks/mt5/reports/RESEARCH_PRODUCTIVITY.json", 7200,
             "desks/mt5/research/research_productivity.py")
    ct = Src("desks/mt5/reports/CERTIFICATE_TRUTH.json", 7200,
             "desks/mt5/research/certificate_truth.py")
    rf = Src("desks/mt5/reports/RESEARCH_FUNNEL.json", 14400,
             "desks/mt5/research/research_funnel.py")
    qc = Src("desks/mt5/reports/QUEUE_CENSUS.json", 21600, "the queue census")
    reg = Src("desks/mt5/data/sleeve_registry.json", 86400,
              "desks/mt5/research/sleeve_registry.py")
    sl = Src("desks/mt5/data/sleeves.json", 86400, "desks/mt5/research/promoter.py")

    reg_rows = _dig(reg.doc, "sleeves", default={})
    accruing = 0
    if isinstance(reg_rows, dict):
        accruing = sum(1 for r in reg_rows.values() if isinstance(r, dict)
                       and str(r.get("status") or "").upper() in ("LIVE", "STANDBY", "FORWARD"))
    sl_rows = _dig(sl.doc, "sleeves", default=[])
    live_n = (sum(1 for r in sl_rows if isinstance(r, dict)
                  and str(r.get("status") or "").upper() == "LIVE")
              if isinstance(sl_rows, list) else None)

    oldest = None
    for src in (qc, rp):
        if time.time() > deadline:
            break
        found = _find_key(src.doc, "oldest")
        if found is not None:
            oldest = {**src.cite(), "value": found[0], "field": found[1]}
            break
    if oldest is None:
        oldest = {"status": UNMEASURED, "value": None,
                  "source": "desks/mt5/reports/QUEUE_CENSUS.json",
                  "why": ("no artifact on this host publishes the enqueue time of the OLDEST "
                          "unjudged candidate; CERTIFICATE_TRUTH publishes the queued COUNT only, "
                          "so the backlog's age is unmeasured rather than zero")}

    return {
        "status": rp.status,
        "sources": [pc.cite(), rp.cite(), ct.cite(), rf.cite(), qc.cite(), reg.cite(), sl.cite()],
        "sources_visited": pc.field(_dig(pc.doc, "totals", "sources_visited")),
        "discoveries": pc.field(_dig(pc.doc, "registry_totals", "discoveries")),
        "candidates": pc.field(_dig(pc.doc, "registry_totals", "research_candidates")),
        "unique_cells": pc.field(_dig(pc.doc, "totals", "unique_cells")),
        "judged": rp.field(_dig(rp.doc, "stages", "judged", "cells")),
        "judged_unmeasured": rp.field(_dig(rp.doc, "stages", "judged", "unmeasured")),
        "certificates": ct.field(_dig(ct.doc, "canon", "n")),
        "clocks_accruing": reg.field(accruing if isinstance(reg_rows, dict) else None,
                                     "data/sleeve_registry.json holds no sleeves block"),
        "live": sl.field(live_n, "data/sleeves.json holds no sleeves list"),
        "unjudged_backlog": ct.field(_dig(ct.doc, "one_lane", "queued")),
        "unjudged_backlog_deepening": rp.field(_dig(rp.doc, "stages", "deepening", "queued")),
        "unjudged_oldest": oldest,
        "stale_unjudged": ct.field(_dig(ct.doc, "one_lane", "stale_unjudged")),
        "conversion": rp.field(_dig(rp.doc, "conversion")),
        "bottleneck_stage": rp.field(_dig(rp.doc, "bottleneck")),
        "forward_valid_discoveries": rf.field(_dig(rf.doc, "numerator",
                                                   "forward_valid_discoveries")),
        "forward_valid_why": rf.field(_dig(rf.doc, "numerator", "why")),
    }


# ------------------------------------------------------------------------------- BOTTLENECKS
def _bottlenecks() -> dict[str, Any]:
    ba = Src("desks/mt5/reports/BOTTLENECK_ATTACK.json", 7200,
             "desks/mt5/research/bottleneck_attack.py")
    trend = _dig(ba.doc, "trend_24h", default={}) or {}
    rows: list[dict[str, Any]] = []
    raw = _dig(ba.doc, "bottlenecks", default=[])
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            name = str(row.get("bottleneck"))
            tr = trend.get(name, {}) if isinstance(trend, dict) else {}
            rows.append({"bottleneck": name, "owner": row.get("owner"),
                         "severity": row.get("severity"), "status": row.get("status"),
                         "value": row.get("value"), "unit": row.get("unit"),
                         "basis": str(row.get("basis") or "")[:200],
                         "trend": tr.get("direction") or UNMEASURED,
                         "trend_delta": tr.get("delta"),
                         "trend_why": tr.get("why") or ""})
    return {
        "status": ba.status,
        "sources": [ba.cite()],
        "binding": ba.field(_dig(ba.doc, "binding", "bottleneck")),
        "binding_owner": ba.field(_dig(ba.doc, "binding", "owner")),
        "binding_value": ba.field(_dig(ba.doc, "binding", "value")),
        "binding_unit": ba.field(_dig(ba.doc, "binding", "unit")),
        "binding_why": ba.field(_dig(ba.doc, "binding", "why")),
        "trend_window_h": ba.field(_dig(ba.doc, "trend_24h", "window_h")),
        "rows": rows,
    }


# -------------------------------------------------------------------------------- MACRO NEWS
def _macro(deadline: float) -> dict[str, Any]:
    mv = Src("desks/mt5/reports/MACRO_VIEW.json", 21600, "desks/mt5/research/macro_desk.py")
    mse = Src("desks/mt5/reports/MACRO_STATE_ENGINE.json", 21600,
              "desks/mt5/research/macro_state_engine.py")
    es = Src("desks/mt5/reports/EVENT_SURPRISE.json", 21600,
             "desks/mt5/research/event_surprise.py")
    era = Src("desks/mt5/reports/EVENT_RESPONSE_ATLAS.json", 21600,
              "desks/mt5/research/event_response_atlas.py")
    cal = Src("desks/mt5/data/forced_flow_calendar.json", 172800,
              "desks/mt5/research/forced_flow_calendar.py")
    rr = Src("desks/mt5/reports/REGIME_ROUTER.json", 21600,
             "desks/mt5/research/regime_router.py")
    sl = Src("desks/mt5/data/sleeves.json", 86400, "desks/mt5/research/promoter.py")

    live_symbols = {str(r.get("symbol") or "").upper()
                    for r in (_dig(sl.doc, "sleeves", default=[]) or [])
                    if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"}

    # --- the calendar's next releases, each joined to the book it bears on
    now_iso = _now().isoformat()
    upcoming: list[dict[str, Any]] = []
    events = _dig(cal.doc, "events", default=[])
    if isinstance(events, list):
        future = [e for e in events if isinstance(e, dict)
                  and str(e.get("window_start_utc") or "") >= now_iso]
        future.sort(key=lambda e: str(e.get("window_start_utc")))
        for ev in future[:14]:
            if time.time() > deadline:
                break
            instruments = [str(i).upper() for i in (ev.get("instruments") or [])
                           if isinstance(i, str)]
            hit = sorted(set(instruments) & live_symbols)
            upcoming.append({
                "kind": ev.get("kind"), "name": ev.get("name"),
                "window_start_utc": ev.get("window_start_utc"),
                "window_end_utc": ev.get("window_end_utc"),
                "instruments": instruments[:8],
                "n_instruments": len(instruments),
                "in_s": _seconds_until(ev.get("window_start_utc")),
                "in": _human_age(_seconds_until(ev.get("window_start_utc"))),
                "desk": (f"WAITING: {len(hit)} live sleeve symbol(s) in this window ("
                         + ", ".join(hit[:4]) + ")") if hit else
                        "NO LIVE SLEEVE trades an instrument in this window",
                "acted": bool(hit)})

    # --- what already happened: the captured news tail (public headlines only)
    news_path = DESK / "data" / "news_captures.jsonl"
    news_age = (max(0.0, time.time() - news_path.stat().st_mtime) if news_path.exists() else None)
    captured = _tail_rows(news_path, 120000, 14) if news_path.exists() else []
    news_rows = [{"source": r.get("source"), "title": str(r.get("title") or "")[:160],
                  "happened_at": r.get("happened_at"), "received_at": r.get("received_at"),
                  "age": _human_age(_age_of_iso(r.get("received_at"))),
                  "lane": r.get("lane"),
                  "surprise": UNMEASURED,
                  "surprise_why": ("the desk holds this release without a consensus pair, so no "
                                   "surprise was measured -- see EVENT_SURPRISE.why")}
                 for r in reversed(captured)]

    lean = _dig(mv.doc, "lean", default={}) or {}
    top_lean = sorted(((k, v) for k, v in lean.items() if isinstance(v, (int, float))),
                      key=lambda kv: -abs(float(kv[1])))[:8] if isinstance(lean, dict) else []

    era_cells = _dig(era.doc, "cells", default=[])
    top_cells: list[dict[str, Any]] = []
    if isinstance(era_cells, list):
        scored = [c for c in era_cells if isinstance(c, dict)
                  and isinstance(c.get("mean_bp"), (int, float))]
        scored.sort(key=lambda c: -abs(float(c["mean_bp"])))
        top_cells = [{"cell": c.get("cell"), "kind": c.get("kind"), "symbol": c.get("symbol"),
                      "horizon": c.get("horizon"), "n": c.get("n"),
                      "mean_bp": c.get("mean_bp"), "hit_rate": c.get("hit_rate"),
                      "live_symbol": str(c.get("symbol") or "").upper() in live_symbols}
                     for c in scored[:14]]

    router_state = _dig(rr.doc, "current_state", default={}) or {}
    transition = _find_key(rr.doc, "transition")
    return {
        "status": mv.status,
        "sources": [mv.cite(), mse.cite(), es.cite(), era.cite(), cal.cite(), rr.cite()],
        "view": {
            "lean": mv.field([{"ccy": k, "lean": round(float(v), 4)} for k, v in top_lean]
                             or None, "MACRO_VIEW.json carries no lean block"),
            "confidence": mv.field(_dig(mv.doc, "confidence")),
            "strength": mv.field(_dig(mv.doc, "strength")),
            "newest_print": mv.field(_dig(mv.doc, "newest_print")),
            "print_age_days": mv.field(_dig(mv.doc, "age_days")),
            "why": mv.field(_dig(mv.doc, "why")),
        },
        "state_engine": {
            "status": mse.field(_dig(mse.doc, "status")),
            "blocks": mse.field(sorted(_dig(mse.doc, "blocks", default={}) or {})
                                if isinstance(_dig(mse.doc, "blocks"), dict) else None),
            "blocks_summary": mse.field(_dig(mse.doc, "blocks_summary")),
            "global_factors": mse.field({k: v for k, v in
                                         (_dig(mse.doc, "global_factors", default={}) or {}).items()
                                         if isinstance(v, (int, float, str))} or None,
                                        "MACRO_STATE_ENGINE.json carries no scalar global factor"),
            "registry_census": mse.field(_dig(mse.doc, "registry_census")),
        },
        "surprise": {
            "status": es.field(_dig(es.doc, "status")),
            "why": es.field(_dig(es.doc, "why")),
            "n_pairs": es.field(_dig(es.doc, "surprise", "n_pairs")),
            "n_calendar_events": es.field(_dig(es.doc, "calendar", "n_events")),
            "with_consensus_pair": es.field(_dig(es.doc, "calendar", "with_pair")),
            "reading": ("the desk holds releases WITHOUT a consensus, so every z-score below is "
                        "UNMEASURED: a release is not a surprise until an expectation is paired "
                        "to it"),
        },
        "reactions": {
            "n_cells": era.field(_dig(era.doc, "n_cells")),
            "threshold_t": era.field(_dig(era.doc, "threshold_t")),
            "rows": top_cells,
            "why": ("measured post-event reactions, in basis points, from the desk's own bars -- "
                    "not a consensus surprise"),
        },
        "calendar": {
            "next": upcoming,
            "n_events": cal.field(_dig(cal.doc, "n_events")),
            "generated_at": cal.field(_dig(cal.doc, "generated_at")),
            "status": cal.status, "why": cal.why,
        },
        "news": {
            "rows": news_rows,
            "source": "desks/mt5/data/news_captures.jsonl",
            "age": _human_age(news_age), "age_s": news_age,
            "status": (MEASURED if news_rows else MISSING),
            "why": ("" if news_rows else
                    "no captured news rows on this host"),
            "stream_organ": {
                "status": MISSING,
                "why": ("desks/mt5/research/news_event_stream.py does not exist on this host; the "
                        "news lane's capture file is what is published, so the stream organ's "
                        "own artifact is missing rather than empty")},
        },
        "regime": {
            "current_state": rr.field(router_state or None),
            "state_sources": rr.field(_dig(rr.doc, "state_sources")),
            "n_sleeves": rr.field(_dig(rr.doc, "n_sleeves")),
            "router_active": rr.field(_dig(rr.doc, "counts", "router_active")),
            "unmeasured": rr.field(_dig(rr.doc, "unmeasured")),
            "last_transition": ({**rr.cite(), "value": transition[0], "field": transition[1]}
                                if transition else
                                {"status": UNMEASURED, "value": None,
                                 "source": "desks/mt5/reports/REGIME_ROUTER.json",
                                 "why": ("REGIME_ROUTER publishes the CURRENT state and no "
                                         "transition history, so the time of the last state "
                                         "change is not measured on this host")}),
        },
    }


# ---------------------------------------------------------------------------------- HEADLINE
def _headline(sections: dict[str, Any]) -> dict[str, Any]:
    """The six numbers checked at a glance, each keeping the provenance of its own section."""
    ii = Src("desks/mt5/reports/INDEPENDENCE_INTAKE.json", 7200,
             "desks/mt5/research/independence_intake.py")
    per_hour = _find_key(ii.doc, "per", "hour")
    ortho = _find_key(ii.doc, "orthogon")
    live = sections["live"]
    return {
        "equity": live["equity"],
        "day_pnl": live["day_pnl"],
        "certificates": sections["canon"]["n_certificates"],
        "defects_open": sections["defects"]["n_open"],
        "cells_per_hour": ({**ii.cite(), "value": per_hour[0], "field": per_hour[1]}
                           if per_hour else
                           {**ii.cite(), "value": None, "status": UNMEASURED,
                            "why": (ii.why or "INDEPENDENCE_INTAKE.json publishes no per-hour "
                                    "cell rate this organ could read")}),
        "cells_per_hour_orthogonal": ({**ii.cite(), "value": ortho[0], "field": ortho[1]}
                                      if ortho else
                                      {**ii.cite(), "value": None, "status": UNMEASURED,
                                       "why": (ii.why or "INDEPENDENCE_INTAKE.json publishes no "
                                               "orthogonality-weighted rate")}),
        "clocks_accruing": sections["funnel"]["clocks_accruing"],
        "binding_bottleneck": sections["bottlenecks"]["binding"],
    }


def _collect_unmeasured(node: Any, path: str, out: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        status = node.get("status")
        if status in (UNMEASURED, MISSING, UNREADABLE, STALE) and "why" in node:
            out.append({"where": path, "status": status, "why": str(node.get("why") or ""),
                        "source": node.get("source")})
        for key, val in node.items():
            if key in ("rows", "sources", "fences", "next"):
                continue
            _collect_unmeasured(val, f"{path}.{key}" if path else str(key), out)


def build(budget_s: float = 120.0) -> dict[str, Any]:
    started = time.time()
    deadline = started + max(5.0, float(budget_s))
    sections: dict[str, Any] = {}
    sections["canon"] = _canon(deadline)
    sections["defects"] = _defects(deadline)
    sections["live"] = _live(deadline)
    sections["producers"] = _producers(deadline)
    sections["funnel"] = _funnel(deadline)
    sections["bottlenecks"] = _bottlenecks()
    sections["macro"] = _macro(deadline)

    unmeasured: list[dict[str, Any]] = []
    _collect_unmeasured(sections, "", unmeasured)
    worst = [name for name, sec in sections.items()
             if isinstance(sec, dict) and sec.get("status") in (MISSING, UNREADABLE, STALE)]
    doc: dict[str, Any] = {
        "source": "desk_dashboard_state",
        "host": socket.gethostname(),
        "generated_at": _now().isoformat(timespec="seconds"),
        "generated_epoch": time.time(),
        "cadence_s": CADENCE_S,
        "budget_s": float(budget_s),
        "elapsed_s": round(time.time() - started, 2),
        "status": ("PARTIAL" if worst else MEASURED),
        "degraded_sections": worst,
        "rule": ("every value carries the artifact it came from and that artifact's age; an "
                 "absent measurement renders UNMEASURED with its reason and never as a zero; a "
                 "document older than cadence_s is stale and says so before any number"),
        "headline": _headline(sections),
        "sections": sections,
        "unmeasured": unmeasured[:120],
        "n_unmeasured": len(unmeasured),
    }
    return doc


def _publish(doc: dict[str, Any]) -> dict[str, Any]:
    """Write the report, then EXTEND the payload the page already fetches. Never a second file."""
    written: dict[str, Any] = {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, OUT)
    written["report"] = str(OUT)
    if WEB.exists():
        try:
            payload = json.loads(WEB.read_text("utf-8", errors="replace"))
        except (OSError, ValueError) as exc:
            written["web"] = f"UNWRITTEN: {type(exc).__name__}: {exc}"
            return written
        if isinstance(payload, dict):
            payload["dashboard"] = doc
            wtmp = WEB.with_suffix(".dash.tmp")
            wtmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
            os.replace(wtmp, WEB)
            written["web"] = str(WEB)
        else:
            written["web"] = "UNWRITTEN: web/desk_state.json is not an object"
    else:
        written["web"] = f"UNWRITTEN: {WEB} is absent"
    return written


def run(budget_s: float = 120.0, write: bool = True) -> dict[str, Any]:
    doc = build(budget_s=budget_s)
    if write:
        doc["written"] = _publish(doc)
        with contextlib.suppress(Exception):
            from libs.ops import events
            events.emit("DESK_DASHBOARD_STATE",
                        status=str(doc["status"]),
                        unmeasured=int(doc["n_unmeasured"]),
                        degraded=",".join(doc["degraded_sections"])[:120])
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode there is)")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, write=not a.no_write)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        head = doc["headline"]
        print(f"desk dashboard state {doc['generated_at']} on {doc['host']}: "
              f"{doc['status']} in {doc['elapsed_s']}s")
        for key in ("equity", "day_pnl", "certificates", "defects_open", "cells_per_hour",
                    "clocks_accruing", "binding_bottleneck"):
            cell = head.get(key, {})
            print(f"  {key:<24} {cell.get('value')!s:<18} {cell.get('status')!s:<10} "
                  f"{cell.get('age') or ''!s:<8} {str(cell.get('why') or '')[:70]}")
        print(f"  unmeasured rows: {doc['n_unmeasured']}; degraded: {doc['degraded_sections']}")
        print(f"  written: {doc.get('written')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
