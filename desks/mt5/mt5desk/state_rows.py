"""ONE LOADER AT EVERY ORGAN BOUNDARY: rows are validated one by one, a bad row is quarantined
and counted, and an input past its shelf life is UNMEASURED (roots R3 + R9, 2026-11-27).

WHY. Organs read each other's files raw and solved all-or-nothing. From 11-21 the allocator died
440 times running on ONE sleeves.json row whose certificate was a bare string, and the fix that
landed (92b8edbbc) handled that one row type only. The gateway's roster loader had the same
shape: one non-object row in sleeves.json returned an EMPTY roster, so every LIVE sleeve stopped
trading on one malformed line. And nothing read the date: spreads stamped 09-23 and an E8 slip
stamped 10-20 (n = 0) were used as if measured today.

THE RULE, for every reader that goes through here:
  * A file that is absent is ABSENT; one that is unreadable or torn is UNMEASURED. Neither is ever
    a partial good set read as complete.
  * Each row is checked on its own. A row that fails is QUARANTINED with its index and reason;
    every other row is returned. One bad row never empties the set.
  * `max_age_s`: the input's age is its own stamp (`generated_at` / `at` / `measured_at` /
    `updated_at`), else the file's mtime. Past the limit the status is STALE and the caller
    decides, but it can never read a stale input as fresh: the status travels with the rows.
  * Quarantine counts are published to `reports/STATE_QUARANTINE.json`, one block per input, so a
    writer emitting a bad shape is visible the hour it starts, not after 440 failures.
Never raises.
"""
from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
QUARANTINE_REPORT = DESK / "reports" / "STATE_QUARANTINE.json"
OK, ABSENT, UNMEASURED, STALE = "OK", "ABSENT", "UNMEASURED", "STALE"
_STAMPS = ("generated_at", "at", "measured_at", "updated_at", "written_at")
#: Quarantine samples kept per input in the report (the count is always exact).
SAMPLE = 5


@dataclass
class Loaded:
    rows: list[dict[str, Any]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)
    status: str = ABSENT
    why: str = ""
    age_s: float | None = None
    doc: dict[str, Any] | None = None

    @property
    def usable(self) -> bool:
        """True when the rows may be read as current (OK). STALE rows are returned for callers
        that bill a stale input explicitly, never for ones that would read it as fresh."""
        return self.status == OK


def _parse_ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    with contextlib.suppress(ValueError):
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    return None


def age_of(path: Path, doc: Any, now: datetime) -> float | None:
    """Seconds since the input was produced: its own stamp first, else the file's mtime."""
    if isinstance(doc, Mapping):
        for k in _STAMPS:
            t = _parse_ts(doc.get(k))
            if t is not None:
                return max(0.0, (now - t).total_seconds())
    with contextlib.suppress(OSError):
        return max(0.0, now.timestamp() - os.stat(path).st_mtime)
    return None


def load_doc(path: Path, *, max_age_s: float | None = None, now: datetime | None = None,
             allow_list: bool = False) -> Loaded:
    """A whole JSON document with its status and age (no row checks). A top-level list is
    legal only for `load_rows` (`allow_list`); it then rides in `rows` unchecked."""
    now = now or datetime.now(UTC)
    if not path.exists():
        return Loaded(status=ABSENT, why=f"{path.name} absent")
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return Loaded(status=UNMEASURED, why=f"{path.name} unreadable: {type(exc).__name__}")
    if isinstance(doc, list) and allow_list:
        age = age_of(path, None, now)
        st = STALE if max_age_s is not None and (age is None or age > max_age_s) else OK
        return Loaded(status=st, rows=doc, age_s=age,
                      why="" if st == OK else f"{path.name} past its {int(max_age_s or 0)}s limit")
    if not isinstance(doc, dict):
        return Loaded(status=UNMEASURED, why=f"{path.name} is not an object")
    age = age_of(path, doc, now)
    if max_age_s is not None and (age is None or age > max_age_s):
        return Loaded(status=STALE, doc=doc, age_s=age,
                      why=f"{path.name} is {age if age is None else round(age)}s old "
                          f"(limit {int(max_age_s)}s)")
    return Loaded(status=OK, doc=doc, age_s=age)


def load_rows(path: Path, *, key: str | None = None,
              check: Callable[[Any], str | None] | None = None,
              max_age_s: float | None = None, now: datetime | None = None,
              name: str | None = None, publish: bool = True,
              report: Path | None = None) -> Loaded:
    """Rows of a JSON list (the document itself, or `doc[key]`), each checked by `check`
    (returns None for a good row, else the reason). Never raises."""
    now = now or datetime.now(UTC)
    out = load_doc(path, max_age_s=max_age_s, now=now, allow_list=key is None)
    if out.status in (ABSENT, UNMEASURED):
        _publish(name or path.name, out, now, report, publish)
        return out
    doc: Any = out.doc
    if doc is None:                                       # a top-level list
        raw, out.rows = out.rows, []
    else:
        raw = doc.get(key) if key is not None else None
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        out.status, out.why, out.rows = UNMEASURED, f"{path.name}[{key}] is not a list", []
        _publish(name or path.name, out, now, report, publish)
        return out
    for i, r in enumerate(raw):
        why = "not an object" if not isinstance(r, dict) else None
        if why is None and check is not None:
            try:
                why = check(r)
            except Exception as exc:  # noqa: BLE001 -- a checker bug quarantines, never kills
                why = f"check raised {type(exc).__name__}"
        if why:
            out.quarantined.append({"index": i, "why": why,
                                    "name": r.get("name") if isinstance(r, dict) else None})
        else:
            out.rows.append(r)
    _publish(name or path.name, out, now, report, publish)
    return out


def _publish(name: str, out: Loaded, now: datetime, report: Path | None, on: bool) -> None:
    if not on:
        return
    with contextlib.suppress(Exception):
        p = report or QUARANTINE_REPORT
        try:
            doc = json.loads(p.read_text("utf-8"))
            doc = doc if isinstance(doc, dict) else {}
        except (OSError, ValueError):
            doc = {}
        inputs = doc.get("inputs") if isinstance(doc.get("inputs"), dict) else {}
        prev = inputs.get(name) if isinstance(inputs.get(name), dict) else {}
        block = {"at": now.isoformat(timespec="seconds"), "status": out.status, "why": out.why,
                 "rows": len(out.rows), "quarantined": len(out.quarantined),
                 "sample": out.quarantined[:SAMPLE],
                 "age_s": None if out.age_s is None else round(out.age_s)}
        if {k: prev.get(k) for k in ("status", "rows", "quarantined")} == \
                {k: block[k] for k in ("status", "rows", "quarantined")} and prev.get("at", "")[:13] \
                == block["at"][:13]:
            return                      # same reading this hour: no rewrite on every pass
        inputs[name] = block
        doc = {"schema": "state-quarantine-v1", "generated_at": block["at"], "inputs": inputs}
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(p)


# ------------------------------------------------------------------------------ sleeves.json

def sleeve_problem(r: Mapping[str, Any]) -> str | None:
    """Why a sleeves.json row cannot be read safely, or None. The two certificate shapes the
    promoter writes (a {"cell": ...} dict, or the bare clock key string) are both legal."""
    if not isinstance(r.get("name"), str) or not r.get("name"):
        return "no name"
    if not isinstance(r.get("status"), str):
        return "status is not a string"
    cert = r.get("certificate")
    if cert is not None and not isinstance(cert, (dict, str)):
        return f"certificate is a {type(cert).__name__}"
    sym = r.get("symbol")
    if sym is not None and not isinstance(sym, str):
        return f"symbol is a {type(sym).__name__}"
    for k in ("risk_frac", "fraction"):
        v = r.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
            return f"{k} is not a number"
    return None


def sleeve_rows(path: Path, *, now: datetime | None = None, publish: bool = True,
                report: Path | None = None) -> Loaded:
    """Every readable sleeves.json row; a malformed row is quarantined, never fatal."""
    return load_rows(path, key="sleeves", check=sleeve_problem, now=now, name="sleeves.json",
                     publish=publish, report=report)
