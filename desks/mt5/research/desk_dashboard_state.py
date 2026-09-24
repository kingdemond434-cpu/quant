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
#: THE WORD UNMEASURED HAS TO MEAN ONE THING OR IT MEANS NOTHING (principal, 2026-09-24).
#:
#: Two different facts wore it here. "Nobody looked" is a hole and a defect. "The desk looked and
#: the thing is genuinely not there" is a MEASUREMENT -- the gateway holding no open position is
#: a real and correct answer about a flat book, and rendering it UNMEASURED taught every reader
#: to skim past the word until the word stopped working. A reader who cannot tell the two apart
#: cannot tell which rows are work.
#:
#: So a measured emptiness renders MEASURED_EMPTY and carries the FACT rather than a reason for
#: absence. It is published in its own list, never folded into `unmeasured`, and never hidden:
#: absence still never resolves to a clean verdict (L1.28a, WS-005) -- but a measured emptiness
#: was never an absence.
MEASURED_EMPTY = "MEASURED_EMPTY"


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

    def empty(self, value: Any, fact: str, why_absent: str = "") -> dict[str, Any]:
        """A field whose EMPTINESS IS THE ANSWER. Present-and-empty is MEASURED_EMPTY with the
        fact; a source that is missing or silent about the field is still UNMEASURED.

        The caller uses this only where it has checked that the artifact ANSWERED -- that the
        producer ran, looked, and found nothing. Anywhere the producer might simply not have
        written the field, `field()` is the honest call and UNMEASURED is the honest verdict.
        """
        cite = self.cite()
        if self.status in (MISSING, UNREADABLE):
            cite["value"] = None
            return cite
        if value in (None, "", [], {}):
            cite["status"] = MEASURED_EMPTY
            cite["why"] = fact
            cite["value"] = value if value is not None else None
            return cite
        return self.field(value, why_absent)


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


# ------------------------------------------------------- WHEN WAS THIS CERTIFICATE BORN
#: The census's own birth ledger. THE SEALED STORE IS READ AND NEVER WRITTEN: this file is
#: written by this organ, holds one row per certificate key, and only ever moves a birth EARLIER.
#: Derived from `DESK` at CALL TIME, not bound at import: a module constant would ignore a test's
#: temporary desk and read -- or write -- the real box's ledger from inside a test.
def births_path() -> Path:
    return DESK / "reports" / "CERTIFICATE_BIRTHS.json"


def _births(survivors: list[tuple[str, dict[str, Any]]], now: datetime) -> dict[str, Any]:
    """Every certificate's own birth time, and the evidence it rests on.

    THE BIRTH WAS ALWAYS THERE AND NOTHING READ IT. This row rendered UNMEASURED on the grounds
    that `UNIVERSAL_SURVIVORS.json` records one `swept_at` for the whole store -- true, and
    beside the point, because every survivor row carries its own `gated_at`: the instant that
    certificate passed the tenth gate. That is its birth, stamped by the sealed writer at the
    moment of birth, and the dashboard was reading `days` (the BACKTEST span) instead.

    WHY A LEDGER RATHER THAN JUST READING THE FIELD. A certificate that is retired and later
    restored is re-stamped, and `restored_at` on this box's own store is three weeks after
    `gated_at`. Reading the live field alone would let a certificate get YOUNGER, and an age that
    can fall is not an age. So the ledger is a RATCHET ON TRUTH: a birth may move earlier when
    older evidence turns up -- the append-only `SURVIVORS_LEDGER.json` keeps the original
    `gated_at` of claims the canonical store has since re-stamped -- and never later.

    A certificate with no `gated_at` anywhere is NOT given a birth. It gets a FLOOR: this host
    first saw it at T, so it is no younger than that, and the row says which it is.
    """
    prior = _read_json(births_path())
    raw_rows = prior.get("certificates")
    rows: dict[str, Any] = raw_rows if isinstance(raw_rows, dict) else {}
    ledger = _read_json(DESK / "reports" / "SURVIVORS_LEDGER.json")
    raw_claims = ledger.get("claims")
    claims: dict[str, Any] = raw_claims if isinstance(raw_claims, dict) else {}
    # The ledger keys claims as "<lane>.<hunt>.<cell>" and the store keys them "<hunt>.<cell>";
    # the CELL is the identity both spellings agree on, so the fallback joins on it.
    by_cell: dict[str, str] = {}
    for row in claims.values():
        if isinstance(row, dict) and row.get("cell") and row.get("gated_at"):
            cell = str(row["cell"])
            stamp = str(row["gated_at"])
            if stamp < by_cell.get(cell, "￿"):
                by_cell[cell] = stamp

    out: dict[str, dict[str, Any]] = {k: dict(v) for k, v in rows.items() if isinstance(v, dict)}
    for key, cert in survivors:
        seen = out.setdefault(key, {})
        candidates: list[tuple[str, str]] = []
        if isinstance(cert.get("gated_at"), str) and cert["gated_at"].strip():
            candidates.append((cert["gated_at"], "UNIVERSAL_SURVIVORS.<cert>.gated_at"))
        cell = str(cert.get("cell") or "")
        if cell in by_cell:
            candidates.append((by_cell[cell], "SURVIVORS_LEDGER.claims[].gated_at (append-only)"))
        if isinstance(seen.get("born_at"), str):
            candidates.append((seen["born_at"], str(seen.get("basis") or "prior ledger row")))
        if candidates:
            born, basis = min(candidates, key=lambda c: c[0])
            seen["born_at"] = born
            seen["basis"] = basis
        seen.setdefault("first_seen_here", now.isoformat(timespec="seconds"))
        seen["n_passes"] = int(seen.get("n_passes") or 0) + 1
        seen["last_seen_here"] = now.isoformat(timespec="seconds")
    return {"certificates": out, "ledger_claims_joined": len(by_cell)}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        got = json.loads(path.read_text("utf-8", errors="replace"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _age_block(rows: list[dict[str, Any]], births: dict[str, Any]) -> dict[str, Any]:
    """The store's age, per certificate and in summary. An unbirthed certificate is named."""
    ages = [r["age_s"] for r in rows if isinstance(r.get("age_s"), (int, float))]
    floored = [r["certificate"] for r in rows if r.get("age_basis") == "FLOOR"]
    if not rows:
        return {"status": UNMEASURED, "value": None, "source": str(births_path()),
                "why": "the canonical store holds no certificate to date"}
    if not ages:
        return {"status": UNMEASURED, "value": None, "source": str(births_path()),
                "why": (f"none of the {len(rows)} certificate(s) carries a `gated_at` in the "
                        f"canonical store or in the append-only survivors ledger, so no birth "
                        f"time exists on this host to date them from")}
    ages.sort()
    mid = ages[len(ages) // 2]
    return {
        "status": MEASURED, "source": str(births_path()),
        "value": {"n_dated": len(ages), "n_undated": len(rows) - len(ages),
                  "oldest_age": _human_age(ages[-1]), "oldest_age_s": round(ages[-1], 1),
                  "newest_age": _human_age(ages[0]), "newest_age_s": round(ages[0], 1),
                  "median_age": _human_age(mid), "median_age_s": round(mid, 1)},
        "floored": floored[:10],
        "why": ("" if not floored else
                f"{len(floored)} certificate(s) carry a FLOOR rather than a birth: this host "
                f"first saw them at the stamped time and no earlier evidence exists, so they are "
                f"no YOUNGER than the age shown and may be older"),
        "basis": ("birth = the earliest `gated_at` for this certificate across the sealed store "
                  "and the append-only survivors ledger, ratcheted earlier-only in "
                  "reports/CERTIFICATE_BIRTHS.json, which this organ owns and writes. The sealed "
                  "UNIVERSAL_SURVIVORS.json is read and never written."),
        "ledger_claims_joined": births.get("ledger_claims_joined"),
    }


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
    births = _births(pairs, _now())
    birth_rows = births["certificates"]
    rows: list[dict[str, Any]] = []
    if pairs:
        for key, cert in pairs:
            if time.time() > deadline:
                break
            born = birth_rows.get(str(key)) or {}
            born_at = born.get("born_at")
            age_s = _age_of_iso(born_at) if born_at else _age_of_iso(born.get("first_seen_here"))
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
                "born_at": born_at or born.get("first_seen_here"),
                "age_s": round(age_s, 1) if age_s is not None else None,
                "age": _human_age(age_s),
                "age_basis": ("GATED_AT" if born_at else
                              "FLOOR" if born.get("first_seen_here") else UNMEASURED),
                "age_source": born.get("basis") or "first seen by this census",
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
        "certificate_age": _age_block(rows, births),
        "births_written": str(births_path()),
        "divergences": ct.field(_dig(ct.doc, "n_divergences")),
        "divergences_fatal": ct.field(_dig(ct.doc, "n_fatal")),
        "join_coverage": ct.field(_dig(ct.doc, "one_lane", "join", "total_joinable")),
        "join_denominator": ct.field(_dig(ct.doc, "one_lane", "join", "total_denominator")),
        "rows": rows,
        # Carried out to `_publish`, which owns every write in this module. `build()` stays
        # side-effect free so `--no-write` really writes nothing, including this ledger.
        "_births_payload": births,
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
        # A FLAT BOOK IS AN ANSWER. The gateway writes `position` every reconcile; a null there
        # means it looked and holds nothing, which is a MEASUREMENT of a flat book and was being
        # rendered as a hole. The hole case is real and separate: `gateway_state.json` absent or
        # carrying no `position` KEY at all means the gateway never reported, and that still
        # reads UNMEASURED below.
        "open_position": (gw.empty(_dig(gw.doc, "position"),
                                   "FLAT: the gateway reconciled and holds no open position")
                          if "position" in gw.d else
                          gw.field(None, "gateway_state.json carries no `position` key at all: "
                                         "the gateway has not reported a book, which is a hole "
                                         "and not a flat book")),
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
        # CERTIFICATES, THEN CELLS, THEN COMPUTE SPENT. Ordering on certificates alone left every
        # producer that holds none -- which is almost all of them, and always will be -- in
        # whatever order the census emitted, so the top of the table was alphabetical and said
        # nothing. The tie-breaks put the producers that made something first, and after them the
        # ones that spent the most compute making nothing, which is the row a reader must see.
        def _n(r: dict[str, Any], field: str) -> float:
            v = r.get(field)
            return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else -1.0

        rows.sort(key=lambda r: (-_n(r, "certificates"), -_n(r, "unique_cells"),
                                 -_n(r, "cells"), -_n(r, "compute_hours"),
                                 str(r.get("producer") or "")))

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
        # THE ORPHAN THAT WAS NOT AN ORPHAN. `productivity_census` writes this field and wrote
        # null both when there was no caveat to make and when the ledger was absent, so the
        # dashboard rendered a clean reading as UNMEASURED. The census now names all three
        # states; this reads the sibling keys so an OLD census artifact still resolves rather
        # than renders a hole (the box adopts on its own clock, and a reader must not have to
        # wait for it).
        "compute_note": (pc.field(_dig(pc.doc, "compute_ledger_note"))
                         if _dig(pc.doc, "compute_ledger_note") is not None else
                         pc.empty(None,
                                  (f"NO CAVEAT: the compute ledger is available and "
                                   f"{_dig(pc.doc, 'compute_ledger_matched_producers')} roster "
                                   f"producer(s) match a priced run, so there is nothing to "
                                   f"caveat (census predates the always-written note)")
                                  if _dig(pc.doc, "compute_available") else
                                  (f"the compute ledger is unavailable on this host "
                                   f"({_dig(pc.doc, 'compute_why') or 'no reason recorded'}), so "
                                   f"no caveat about it could be computed"))),
        "liveness_census": pr.field(_dig(pr.doc, "census"),
                                    "PRODUCER_CENSUS.json carries no census block"),
        "liveness_basis": ("PRODUCER_CENSUS measures whether a producer RUNS (LIVE/DARK/SLOW), "
                           "which is a different question from what it PRODUCED"),
        # EVERY PRODUCER, NOT THE FIRST SIXTY. This published `rows[:60]` of 1,981 and named the
        # other 1,921 as "more the producer did not publish" -- so the one panel that answers
        # "which producers contribute and how much" withheld 97% of its own answer, and a reader
        # asking about the 1,921 had nowhere to look. A cap here is not a display concern: the
        # HTML renders whatever this hands it, so this IS the data. The rows are eight scalar
        # fields each (~160 bytes), which is a few hundred kilobytes for the whole desk -- the
        # cost of publishing a producer is far below the cost of hiding one.
        "rows": rows,
        "rows_truncated": 0,
        "n_rows": len(rows),
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


def _global_factor_scalars(doc: Any) -> dict[str, Any] | None:
    """The world's scalar factors, from the engine's own block or flattened out of its rows."""
    block = _dig(doc, "global_factors", default={}) or {}
    if not isinstance(block, dict):
        return None
    scalars = block.get("scalars")
    if isinstance(scalars, dict) and scalars:
        return scalars
    flat: dict[str, Any] = {}
    for key, row in block.items():
        if isinstance(row, (int, float, str)) and not isinstance(row, bool):
            flat[key] = row
        elif isinstance(row, dict):
            for field, value in row.items():
                if (isinstance(value, (int, float)) and not isinstance(value, bool)) or (
                        field in ("status", "as_of") and isinstance(value, str)):
                    flat[f"{key}.{field}"] = value
    return flat or None


def _surprise_reading(doc: Any) -> str:
    """One sentence about the surprise lane, DERIVED from its own counts each pass."""
    pairs = _dig(doc, "n_pairs")
    zs = _dig(doc, "surprise", "n_standardized")
    thin = _dig(doc, "surprise", "thin_history")
    floor = _dig(doc, "surprise", "min_surprise_n")
    cells = _dig(doc, "n_cells")
    if not isinstance(pairs, int):
        return ("EVENT_SURPRISE.json publishes no pair count on this host, so whether the desk "
                "can tell a shock from a non-event is itself unmeasured")
    if pairs == 0:
        return ("the desk holds releases WITHOUT a consensus, so every z-score is UNMEASURED: a "
                "release is not a surprise until an expectation is paired to it. No registered "
                "ground produced a pair this pass")
    return (f"{pairs} (actual, consensus) pair(s) held; {zs} carry a z against the release's own "
            f"surprise history and {thin} are still thin (under {floor} prior surprises of the "
            f"same release, which is counted and never pooled). {cells} measured reaction cell(s) "
            f"follow from them. A thin release is UNMEASURED by name, not by silence")


def _news_stream_organ() -> dict[str, Any]:
    """Is the news -> world-state lane alive, and if not, WHICH kind of not-alive is it?

    WHAT THIS ROW USED TO SAY, and why it was useless: "news_event_stream.py does not exist on
    this host". True, and it told a reader nothing they could act on. MEASURED 2026-09-24: the
    organ exists on the build box, is tracked in git (added 2026-09-17), and is wired as an
    hourly leg -- but the commit that adds it was never pushed, so the trading box's tree has
    never carried it and the leg that calls it has been failing every hour since it was wired.
    It was not renamed and it was not folded into anything.

    So this row now measures the ORGAN'S OUTPUT, which is the thing a reader cares about, and
    separates three states that were one: the code is absent (a shipping defect, with the leg
    named), the code is present and has never written (a runtime defect), or the artifacts are
    there with their ages.
    """
    code = DESK / "research" / "news_event_stream.py"
    report = Src("desks/mt5/reports/NEWS_EVENT_STREAM.json", 7200,
                 "desks/mt5/research/news_event_stream.py")
    world = Src("desks/mt5/data/world_state.json", 7200,
                "desks/mt5/research/news_event_stream.py (fast lane)")
    if not code.exists():
        return {
            "status": MISSING, "value": None,
            "code_present": False,
            "source": "desks/mt5/research/news_event_stream.py",
            "artifacts": [report.cite(), world.cite()],
            "why": ("SHIPPING DEFECT, not a lost organ: desks/mt5/research/news_event_stream.py "
                    "is absent from THIS host's tree while hourly_cycle.py still registers the "
                    "leg `news_event_stream` that runs it, so that leg fails every hour. The "
                    "file is tracked in git on the build box (added 2026-09-17) and the commit "
                    "carrying it has not reached this tree. The repair is a push and an "
                    "adoption, not a rewrite."),
            "repair": ("push the commit that adds research/news_event_stream.py, then let "
                       "MT5-AdoptRelease land it"),
        }
    if report.status == MISSING and world.status == MISSING:
        return {"status": UNMEASURED, "value": None, "code_present": True,
                "source": "desks/mt5/research/news_event_stream.py",
                "artifacts": [report.cite(), world.cite()],
                "why": ("the organ's code is present on this host and neither "
                        "reports/NEWS_EVENT_STREAM.json nor data/world_state.json exists, so it "
                        "has never completed a pass here: a runtime defect, not a missing file")}
    live = report if report.status != MISSING else world
    return {"status": live.status, "code_present": True,
            "value": {"report": report.cite(), "world_state": world.cite(),
                      "n_events": _dig(report.doc, "n_events"),
                      "n_deep": _dig(report.doc, "n_deep")},
            "source": live.rel, "age": live.cite()["age"],
            "why": live.why}


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
    gr = Src("desks/mt5/data/event_consensus_sources.json", 10 ** 9,
             "the registry of public consensus grounds (hand-registered, not produced)")
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
                  # A CAPTURED HEADLINE IS NOT A SCHEDULED RELEASE. These rows are the news
                  # lane's tail -- wires, statements, stories -- and a consensus pairs to a
                  # CALENDAR RELEASE with a reference period. There is no expectation to pair to
                  # a headline, and saying so is a measurement about what this row IS; it is not
                  # a missing z-score. The desk's z-scores live in EVENT_SURPRISE and are
                  # counted in `surprise.reading` above.
                  "surprise": MEASURED_EMPTY,
                  "surprise_why": ("a captured headline, not a scheduled release: a consensus "
                                   "pairs to a calendar release with a reference period, and a "
                                   "headline has none. Release z-scores are in EVENT_SURPRISE")}
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
    transition = _dig(rr.doc, "last_transition")
    census = _dig(rr.doc, "router_census")
    return {
        "status": mv.status,
        "sources": [mv.cite(), mse.cite(), es.cite(), era.cite(), cal.cite(), rr.cite(),
                    gr.cite()],
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
            # THE SCALARS WERE NEVER MISSING -- THIS READER WAS LOOKING AT THE WRONG DEPTH.
            # `global_factors` is six dispersion DICTS plus the FRED snapshot, each carrying its
            # own status, so a filter for top-level scalars found nothing and reported the organ
            # as unmeasured while it was measuring the whole cross-section. The engine now
            # publishes `global_factors.scalars`, derived from those same rows; this reads it,
            # and FLATTENS the rows itself when the artifact predates that change, so the
            # dashboard is never blind waiting for an adoption.
            "global_factors": mse.field(_global_factor_scalars(mse.doc),
                                        "MACRO_STATE_ENGINE.json publishes neither a "
                                        "`global_factors.scalars` block nor any dispersion row "
                                        "this reader could flatten"),
            "registry_census": mse.field(_dig(mse.doc, "registry_census")),
        },
        "surprise": {
            "status": es.field(_dig(es.doc, "status")),
            "why": es.field(_dig(es.doc, "why")),
            "n_pairs": es.field(_dig(es.doc, "n_pairs")),
            "n_standardized": es.field(_dig(es.doc, "surprise", "n_standardized")),
            "n_thin_history": es.field(_dig(es.doc, "surprise", "thin_history")),
            "n_releases": es.field(_dig(es.doc, "surprise", "n_releases")),
            "min_surprise_n": es.field(_dig(es.doc, "surprise", "min_surprise_n")),
            "n_calendar_events": es.field(_dig(es.doc, "calendar", "n_events")),
            "with_consensus_pair": es.field(_dig(es.doc, "calendar", "with_pair")),
            "store_rows": es.field(_dig(es.doc, "store", "rows")),
            # THE REGISTRY IS ITS OWN MEASUREMENT. Reading the count out of the last pass's
            # collector block reports UNMEASURED on any pass that ran with --no-collect, which
            # says nothing about how many grounds are registered -- so the registry is read
            # where it lives. An absent registry is the real hole here, and it is the one that
            # kept this whole lane at n_pairs=0.
            "collector_sources": gr.field(
                len(_dig(gr.doc, "sources", default=[]) or []) or None,
                "desks/mt5/data/event_consensus_sources.json registers no source, so the "
                "consensus collector has nothing to fetch and every z-score stays unmeasured"),
            "collector_last_pass": es.field(_dig(es.doc, "collector", "status")),
            # DERIVED, NEVER ASSERTED. This line used to be a hard-coded sentence saying every
            # z-score was unmeasured, which stayed true-sounding after it stopped being true.
            "reading": _surprise_reading(es.doc),
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
            "stream_organ": _news_stream_organ(),
        },
        "regime": {
            "current_state": rr.field(router_state or None),
            "state_sources": rr.field(_dig(rr.doc, "state_sources")),
            "n_sleeves": rr.field(_dig(rr.doc, "n_sleeves")),
            # ZERO ROUTERS ACTIVE IS TWO DIFFERENT FACTS and the count alone tells them apart
            # in neither direction: every sleeve judged and none worth its tax is the router
            # WORKING; nothing judged at all is the router DARK. The census the organ now
            # publishes carries which -- n_scored against n_not_scored, with the reasons -- so
            # a measured zero renders as the measurement it is.
            "router_active": ({**rr.cite(), "value": _dig(rr.doc, "counts", "router_active"),
                               "status": (MEASURED_EMPTY
                                          if (census or {}).get("status") == MEASURED
                                          and not _dig(rr.doc, "counts", "router_active")
                                          else rr.status),
                               "why": str((census or {}).get("why") or ""),
                               "census": census}
                              if isinstance(census, dict) else
                              rr.field(_dig(rr.doc, "counts", "router_active"),
                                       "REGIME_ROUTER.json publishes no router_census, so a "
                                       "zero here cannot be told from a dark router")),
            "unmeasured": rr.empty(_dig(rr.doc, "unmeasured"),
                                   "the router pass recorded no unmeasured axis or subject: a "
                                   "clean pass, not an unread one"),
            "last_transition": ({**rr.cite(), **transition}
                                if isinstance(transition, dict) else
                                {"status": UNMEASURED, "value": None,
                                 "source": "desks/mt5/reports/REGIME_ROUTER.json",
                                 "why": ("REGIME_ROUTER.json on this host predates the state "
                                         "history sidecar (data/regime_state_history.jsonl) and "
                                         "publishes no `last_transition`, so the time of the "
                                         "last regime change is not measured here yet")}),
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


def _collect_unmeasured(node: Any, path: str, out: list[dict[str, Any]],
                        empty: list[dict[str, Any]] | None = None) -> None:
    """Two lists, because they are two different things.

    `out` is the WORKLIST: rows nobody measured. `empty` is the register of measured emptinesses
    -- a flat book, a clean pass, a judged zero -- which are answers and must still be visible,
    because a measured emptiness that is silently dropped is how an absence gets to resolve to a
    clean verdict (L1.28a, WS-005). Nothing is hidden; the two are simply not the same list.
    """
    if isinstance(node, dict):
        status = node.get("status")
        if status in (UNMEASURED, MISSING, UNREADABLE, STALE) and "why" in node:
            out.append({"where": path, "status": status, "why": str(node.get("why") or ""),
                        "source": node.get("source")})
        elif status == MEASURED_EMPTY and empty is not None and "why" in node:
            empty.append({"where": path, "status": status, "fact": str(node.get("why") or ""),
                          "source": node.get("source")})
        for key, val in node.items():
            if key in ("rows", "sources", "fences", "next") or key.startswith("_"):
                continue
            _collect_unmeasured(val, f"{path}.{key}" if path else str(key), out, empty)


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
    measured_empty: list[dict[str, Any]] = []
    _collect_unmeasured(sections, "", unmeasured, measured_empty)
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
                 "MEASURED EMPTINESS -- a flat book, a judged zero, a clean pass -- renders "
                 "MEASURED_EMPTY with the fact, so the word UNMEASURED always means a genuine "
                 "hole and is always a worklist row; a document older than cadence_s is stale "
                 "and says so before any number"),
        "headline": _headline(sections),
        "sections": sections,
        "unmeasured": unmeasured[:120],
        "n_unmeasured": len(unmeasured),
        "measured_empty": measured_empty[:120],
        "n_measured_empty": len(measured_empty),
    }
    doc["_births_payload"] = sections["canon"].pop("_births_payload", None)
    return doc


def _publish(doc: dict[str, Any]) -> dict[str, Any]:
    """Write the report, then EXTEND the payload the page already fetches. Never a second file."""
    written: dict[str, Any] = {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload_births = doc.pop("_births_payload", None)
    if isinstance(payload_births, dict):
        births = births_path()
        births.parent.mkdir(parents=True, exist_ok=True)
        btmp = births.with_suffix(".tmp")
        btmp.write_text(json.dumps({
            "source": "desk_dashboard_state",
            "written_at": _now().isoformat(timespec="seconds"),
            "rule": ("one row per certificate; `born_at` is the earliest `gated_at` seen for it "
                     "in the sealed store or the append-only survivors ledger and moves EARLIER "
                     "only. A certificate with no gated_at anywhere carries `first_seen_here` "
                     "as a FLOOR -- it is no younger than that -- and never a birth."),
            **payload_births}, indent=1, default=str), encoding="utf-8")
        os.replace(btmp, births)
        written["births"] = str(births)
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
