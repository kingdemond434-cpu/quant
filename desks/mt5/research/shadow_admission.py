"""Fail-closed bridge from canonical ten-gate certificates to shadow work."""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

try:  # package import (tests/library callers) versus direct script execution
    from .gate_policy import all_ten_pass, is_exact_policy
except ImportError:  # pragma: no cover - exercised by production script entrypoints
    from gate_policy import all_ten_pass, is_exact_policy

BASE = Path(__file__).resolve().parent.parent


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def authorized_specs(base: Path = BASE) -> set[tuple[str, str, str | None, str, bool]]:
    """Return exact executable specs certified under the original policy only.

    Legacy qquant session rows are reconstructible from REAL_SURVIVORS. Newer
    universal survivors must publish an explicit ``shadow_spec``; guessing lost
    parameters from a display cell name is forbidden.
    """
    reports = base / "reports"
    out: set[tuple[str, str, str | None, str, bool]] = set()

    qquant = _read(reports / "QQUANT_GATES.json")
    if is_exact_policy(qquant.get("gate_policy")):
        for row in qquant.get("verdicts", []):
            if not isinstance(row, dict) or row.get("passed") is not True:
                continue
            if not all_ten_pass(row.get("stages")):
                continue
            parts = str(row.get("id") or "").split()
            if len(parts) != 5:
                continue
            symbol, family, side, selector, condition = parts
            if family.casefold() not in {"breakout", "session_range_breakout"}:
                continue
            if side.upper() != "LONG":
                continue
            state = None if condition.upper() in {"NONE", "ALL", "UNCONDITIONED"} else condition
            out.add((symbol, selector, state, "session_range_breakout", False))

    # Compatibility rows are accepted only when they carry the same complete
    # policy attestation; they cannot bypass or strengthen the QQUANT authority.
    real = _read(reports / "REAL_SURVIVORS.json")
    for row in real.get("real_survivors", []):
        if not isinstance(row, dict) or row.get("REAL3") is not True:
            continue
        cert = row.get("qquant_gates") or {}
        if not is_exact_policy(cert.get("policy")) or not all_ten_pass(cert.get("stages")):
            continue
        family = str(row.get("fam") or "SESSION_RANGE_BREAKOUT").casefold()
        if family not in {"breakout", "session_range_breakout"}:
            continue
        if str(row.get("side") or "LONG").upper() != "LONG":
            continue
        state = row.get("state") or None
        out.add((str(row["sym"]), str(row["win"]), state,
                 "session_range_breakout", False))

    universal = _read(reports / "UNIVERSAL_SURVIVORS.json")
    if is_exact_policy(universal.get("gate_policy")):
        for row in universal.get("survivors", {}).values():
            if not isinstance(row, dict) or not all_ten_pass(row.get("gates")):
                continue
            spec = row.get("shadow_spec")
            if not isinstance(spec, dict):
                continue
            required = {"symbol", "selector", "family", "is_universe"}
            if not required <= set(spec):
                continue
            out.add((str(spec["symbol"]), str(spec["selector"]),
                     spec.get("condition") or None, str(spec["family"]),
                     spec["is_universe"] is True))
    return out


def partition_work(
    declared: Iterable[tuple[str, str, str | None, str, bool]],
    base: Path = BASE,
) -> tuple[list[tuple[str, str, str | None, str, bool]],
           list[tuple[str, str, str | None, str, bool]]]:
    authority = authorized_specs(base)
    admitted, blocked = [], []
    for spec in declared:
        (admitted if spec in authority else blocked).append(spec)
    return admitted, blocked
