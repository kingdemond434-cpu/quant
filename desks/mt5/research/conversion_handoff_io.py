"""conversion_handoff_io: streaming reads, the resolution ledger and the defect report.

Split out of conversion_handoff_converter.py so each file of the organ is a size the
independent reviewer can read whole. conversion_handoff_converter re-exports every name here;
the organ's behaviour and docstring live there."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from research.conversion_handoff_common import (
    CONVERTED,
    DEFECT_FAMILIES_LISTED,
    DEFECT_MESSAGES_PER_FAMILY,
    DEFECT_SAMPLES,
    RETRYABLE,
    ROOT,
    SEAT,
    TERMINAL,
    _now,
)

_DECODER = json.JSONDecoder()
_WS = " \t\r\n"


def _iter_array(fh: Any, buf: str, pos: int, chunk: int) -> Iterator[Any]:
    """Yield each element of a JSON array whose '[' is at `buf[pos-1]`, reading `fh` lazily."""
    eof = False
    while True:
        while True:
            while pos < len(buf) and buf[pos] in _WS + ",":
                pos += 1
            if pos < len(buf) or eof:
                break
            more = fh.read(chunk)
            if not more:
                eof = True
            buf, pos = buf[pos:] + more, 0
        if pos >= len(buf):
            return                      # truncated file: what was read stands, nothing invented
        if buf[pos] == "]":
            return
        try:
            obj, end = _DECODER.raw_decode(buf, pos)
        except ValueError:
            if eof:
                return
            more = fh.read(chunk)
            if not more:
                eof = True
            buf, pos = buf[pos:] + more, 0
            continue
        yield obj
        pos = end
        if pos > chunk:
            buf, pos = buf[pos:], 0


def handoff_header(path: Path) -> dict[str, Any]:
    """schema_version / generated_utc / n and the file's format, from its first 64 KiB."""
    out: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not out["exists"]:
        return out
    try:
        with path.open("r", encoding="utf-8") as fh:
            head = fh.read(65536)
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    first = head.split("\n", 1)[0].strip()
    try:
        row = json.loads(first) if first else None
    except ValueError:
        row = None
    if isinstance(row, dict) and "cell" in row:
        out["format"] = "jsonl"
        return out
    out["format"] = "json"
    for key, pat in (("schema_version", r'"schema_version"\s*:\s*(\d+)'),
                     ("generated_utc", r'"generated_utc"\s*:\s*"([^"]*)"'),
                     ("n", r'"n"\s*:\s*(\d+)')):
        m = re.search(pat, head.split('"rows"', 1)[0])
        if m:
            out[key] = int(m.group(1)) if key != "generated_utc" else m.group(1)
    return out


def iter_handoff(path: Path, chunk: int = 1 << 20) -> Iterator[dict[str, Any]]:
    """Every handoff row, streamed. JSONL (one row per line) and the writer's JSON object form
    (`{"schema_version", "generated_utc", "n", "rows": [...]}`, indent=1) are both read."""
    head = handoff_header(path)
    if not head.get("exists") or head.get("error"):
        return
    with path.open("r", encoding="utf-8") as fh:
        if head.get("format") == "jsonl":
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
            return
        buf = ""
        eof = False
        while True:
            m = re.search(r'"rows"\s*:\s*\[', buf)
            if m:
                break
            if eof:
                return
            more = fh.read(chunk)
            if not more:
                eof = True
            buf += more
        for row in _iter_array(fh, buf, m.end(), chunk):
            if isinstance(row, dict):
                yield row


def iter_json_list(path: Path, chunk: int = 1 << 20) -> Iterator[dict[str, Any]]:
    """Each element of a top-level JSON list (the docket), streamed."""
    try:
        fh = path.open("r", encoding="utf-8")
    except OSError:
        return
    with fh:
        buf = fh.read(chunk)
        i = buf.find("[")
        if i < 0:
            return
        for row in _iter_array(fh, buf, i + 1, chunk):
            if isinstance(row, dict):
                yield row


# =============================================================================================
# THE RESOLUTION LEDGER
# =============================================================================================

def row_key(row: Mapping[str, Any]) -> str:
    """A handoff row's identity: the judge's cell id, its parked reason and when it was parked.
    The cell id is the judge's own (`frontier_identity.docket_cell_id`, carried as `cell`); the
    parked stamp makes a cell the judge re-admits and re-parks a NEW row, never a resolved one."""
    raw = "|".join(str(row.get(k) or "") for k in ("cell", "reason", "first_parked_utc"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def parent_key(reason: Any, cell: Any) -> str:
    """A converted parent's identity across re-parks: the same cell under the same reason."""
    return f"{reason or ''}|{cell or ''}"


def load_ledger(path: Path, today: str | None = None) -> dict[str, Any]:
    """What the append-only ledger already settled. A torn line skips itself, never the rest.
    `today` (an ISO date) is the UTC day whose charges count against the day's budget."""
    resolved: dict[str, str] = {}
    retry_at: dict[str, tuple[str, str]] = {}
    charged_children: dict[str, str] = {}
    converted_parents: dict[str, list[str]] = {}
    family_day: Counter[str] = Counter()
    lifetime_trials: Counter[str] = Counter()
    lifetime_converted: Counter[str] = Counter()
    lifetime_by_reason_family: Counter[str] = Counter()
    today = today or _now().date().isoformat()
    try:
        fh = path.open("r", encoding="utf-8")
    except OSError:
        fh = None
    if fh is not None:
        with fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or not rec.get("key"):
                    continue
                st = str(rec.get("status") or "")
                key = str(rec["key"])
                if st in TERMINAL:
                    resolved[key] = st
                    retry_at.pop(key, None)
                elif st in RETRYABLE and key not in resolved:
                    retry_at[key] = (st, str(rec.get("at") or ""))
                if st == CONVERTED:
                    fam = str(rec.get("trial_family") or rec.get("family") or "?")
                    lifetime_converted[fam] += 1
                    n = int(rec.get("trials_charged") or 0)
                    if n:
                        lifetime_trials[fam] += n
                        lifetime_by_reason_family[f"{rec.get('reason')}|{fam}"] += n
                        if str(rec.get("at") or "")[:10] == today:
                            family_day[fam] += n
                    for cid in rec.get("child_ids") or []:
                        charged_children.setdefault(str(cid), key)
                    if rec.get("cell") and rec.get("child_ids"):
                        converted_parents.setdefault(parent_key(rec.get("reason"), rec["cell"]),
                                                     [str(c) for c in rec["child_ids"]])
    return {"resolved": resolved, "retry_at": retry_at,
            "charged_children": charged_children, "converted_parents": converted_parents,
            "family_day": family_day, "lifetime_by_reason_family": lifetime_by_reason_family,
            "lifetime_trials": lifetime_trials, "lifetime_converted": lifetime_converted}


def append_ledger(path: Path, recs: Sequence[Mapping[str, Any]]) -> int:
    if not recs:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
        fh.flush()
        with contextlib.suppress(OSError):
            os.fsync(fh.fileno())
    return len(recs)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


# =============================================================================================
# build_failed -> the family defect report
# =============================================================================================

_HEX = re.compile(r"\b[0-9a-f]{8,}\b")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_SPACE = re.compile(r"\s+")


def failure_signature(why: Any, symbol: Any = "") -> str:
    """The failure message with the parts that vary per cell (symbol, hashes, numbers) folded,
    so one defect in one family reads as one line however many cells hit it."""
    s = str(why or "").strip()
    if not s:
        return "(no message recorded)"
    sym = str(symbol or "").strip()
    if sym:
        s = s.replace(sym, "<SYM>")
    s = _HEX.sub("<HEX>", s)
    s = _NUM.sub("N", s)
    return _SPACE.sub(" ", s)[:200]


class DefectAggregate:
    """(family -> signature -> count, samples) over every build_failed row in the handoff."""

    def __init__(self) -> None:
        self.by_family: dict[str, Counter[str]] = defaultdict(Counter)
        self.samples: dict[tuple[str, str], dict[str, Any]] = {}
        self.total = 0

    def add(self, row: Mapping[str, Any]) -> None:
        fam = str(row.get("family") or "?")
        sig = failure_signature(row.get("why"), row.get("symbol"))
        self.total += 1
        self.by_family[fam][sig] += 1
        s = self.samples.setdefault((fam, sig), {"message": str(row.get("why") or "")[:300],
                                                 "cells": [], "symbols": set(),
                                                 "timeframes": Counter()})
        if len(s["cells"]) < DEFECT_SAMPLES:
            s["cells"].append(str(row.get("cell") or ""))
        if len(s["symbols"]) < 50:
            s["symbols"].add(str(row.get("symbol") or ""))
        s["timeframes"][str(row.get("timeframe") or "H1")] += 1

    def report(self, owners: Mapping[str, str], *, at: str, handoff: Mapping[str, Any],
               partial: bool) -> dict[str, Any]:
        fams = sorted(self.by_family.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
        ranked = []
        for fam, sigs in fams[:DEFECT_FAMILIES_LISTED]:
            msgs = []
            for sig, n in sigs.most_common(DEFECT_MESSAGES_PER_FAMILY):
                s = self.samples.get((fam, sig), {})
                msgs.append({"signature": sig, "count": n,
                             "sample_message": s.get("message"),
                             "sample_cells": list(s.get("cells") or []),
                             "sample_symbols": sorted(s.get("symbols") or [])[:DEFECT_SAMPLES],
                             "timeframes": dict(s.get("timeframes") or {})})
            total = sum(sigs.values())
            ranked.append({
                "family": fam, "count": total, "distinct_messages": len(sigs),
                "owner": owners.get(fam) or "UNMEASURED (family constructor not resolvable)",
                "messages": msgs,
                "issue": (f"{fam}: {total} parked cells failed to BUILD (signal construction "
                          f"raised). Top cause ({msgs[0]['count'] if msgs else 0}x): "
                          f"{msgs[0]['signature'] if msgs else '?'}. Fix the constructor; the "
                          "judge re-admits these cells after BUILD_FAILED_RETRY_DAYS once code "
                          "ships. No trial was minted for them.")})
        return {
            "generated_utc": at, "schema_version": 1, "producer": SEAT,
            "handoff": dict(handoff), "partial": partial,
            "build_failed_rows": self.total, "families": len(self.by_family),
            "ranked": ranked,
            "rule": ("build_failed is a family defect report, never a hypothesis: each row "
                     "resolves DEFECT_REPORTED and no trial is minted or charged for it. The "
                     "family's owner is the source file of its constructor "
                     "(mt5desk.families.get_family_func)."),
        }


def family_owners(families: Sequence[str]) -> dict[str, str]:
    """family -> the repo-relative file that builds it, or nothing when it cannot be resolved."""
    out: dict[str, str] = {}
    try:
        import inspect

        from mt5desk.families import get_family_func
    except Exception:
        return out
    for fam in families:
        try:
            fn = get_family_func(fam)
            src = inspect.getsourcefile(fn) if fn is not None else None
        except Exception:
            src = None
        if src:
            try:
                out[fam] = str(Path(src).resolve().relative_to(ROOT)).replace("\\", "/")
            except ValueError:
                out[fam] = str(src)
    return out


# =============================================================================================
# short_history_after_cut -> cross_asset_transplant
# =============================================================================================
