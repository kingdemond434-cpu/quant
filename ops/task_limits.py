"""A scheduled task's own limits, read from its definition file: how long one run may last
(Settings/ExecutionTimeLimit), how often it is meant to start (the first trigger's Repetition
Interval) and where its Exec action appends its log (`>> "...log"`).

WHY (2026-10-29). The box swept 36 tasks whose last result was 0x800710E0 while their state was
Running. Under MultipleInstances=IgnoreNew that code is the task's own resident (or long) instance
refusing a relaunch, so the result code says nothing about health. What does is whether the
instance is still producing output inside the bound it was registered with. This module reads
that bound. ops/process_health.py does the judging.

The definition files live under C:\\Windows\\System32\\Tasks, which SYSTEM (MT5-ProcessHealth's
account) can read. Reading them is a file read, with no schtasks call and no Schedule service.
NEVER RAISES: a missing or unreadable file gives every field None and a `why`.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

TASKS_DIR = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "Tasks"
NS = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"

_DURATION = re.compile(
    r"^P(?:(?P<d>\d+(?:\.\d+)?)D)?(?:T(?:(?P<h>\d+(?:\.\d+)?)H)?(?:(?P<m>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<s>\d+(?:\.\d+)?)S)?)?$")
#: `>> "C:\...\X.log"` or `> C:\...\X.log` in an Exec action's arguments.
_LOG_REDIRECT = re.compile(r'>>?\s*"?([^"<>|\r\n]+?\.log)"?(?=\s|$|")', re.IGNORECASE)


def duration_min(text: str | None) -> float | None:
    """ISO-8601 task duration (PT20M, P3D, PT1H30M) in minutes. Blank, malformed, or PT0S
    (which the scheduler reads as "no limit") is None."""
    m = _DURATION.match((text or "").strip().upper())
    if not m or not any(m.groupdict().values()):
        return None
    g = {k: float(v) if v else 0.0 for k, v in m.groupdict().items()}
    total = g["d"] * 1440 + g["h"] * 60 + g["m"] + g["s"] / 60.0
    return total or None


def _find(root: ET.Element, path: str) -> ET.Element | None:
    hit = root.find("/".join(f"{NS}{p}" for p in path.split("/")))
    return hit if hit is not None else root.find(path)


def parse_limits(data: bytes) -> dict[str, Any]:
    """The limits in one task definition (UTF-16 with a BOM, as Windows writes it).
    A DOCTYPE (and so any entity declaration: XXE, billion laughs) is refused with ValueError
    BEFORE parsing; a real task definition never carries one."""
    up = data.upper()
    for enc in ("utf-8", "utf-16-le", "utf-16-be"):
        if "<!DOCTYPE".encode(enc) in up or "<!ENTITY".encode(enc) in up:
            raise ValueError("task definition carries a DOCTYPE/ENTITY declaration: refused")
    root = ET.fromstring(data)
    limit = _find(root, "Settings/ExecutionTimeLimit")
    policy = _find(root, "Settings/MultipleInstancesPolicy")
    interval = None
    triggers = _find(root, "Triggers")
    for trig in list(triggers) if triggers is not None else []:
        rep = trig.find(f"{NS}Repetition/{NS}Interval")
        if rep is None:
            rep = trig.find("Repetition/Interval")
        if rep is not None and duration_min(rep.text) is not None:
            interval = duration_min(rep.text)
            break
    logs: list[str] = []
    actions = _find(root, "Actions")
    for ex in list(actions) if actions is not None else []:
        for part in ("Arguments", "Command"):
            el = ex.find(f"{NS}{part}")
            if el is None:
                el = ex.find(part)
            for hit in _LOG_REDIRECT.findall((el.text or "") if el is not None else ""):
                logs.append(hit.strip())
    raw_limit = (limit.text or "").strip() if limit is not None else ""
    return {
        # Absent is the scheduler's own default of 72 h; PT0S is "no limit" (a daemon).
        "execution_time_limit": raw_limit or "PT72H (default)",
        "execution_time_limit_min": duration_min(raw_limit or "PT72H"),
        "interval_min": interval,
        "multiple_instances": (policy.text or "").strip() if policy is not None else "",
        "logs": logs,
    }


def task_limits(name: str, base: Path | None = None) -> dict[str, Any]:
    """`parse_limits` for task `name` (with or without its leading backslash). NEVER RAISES."""
    base = TASKS_DIR if base is None else base
    parts = [p for p in name.replace("/", "\\").split("\\") if p]
    empty: dict[str, Any] = {"execution_time_limit": None, "execution_time_limit_min": None,
                             "interval_min": None, "multiple_instances": "", "logs": []}
    if not parts:
        return {**empty, "why": "no task name"}
    path = base.joinpath(*parts)
    try:
        return {**parse_limits(path.read_bytes()), "why": ""}
    except (OSError, ValueError, SyntaxError) as exc:   # ET.ParseError is a SyntaxError
        return {**empty, "why": f"task definition unreadable: {type(exc).__name__}"}
