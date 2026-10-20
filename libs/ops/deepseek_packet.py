"""POINT-IN-TIME RESEARCH PACKET -- DeepSeek third-brain addendum, section 3.

The hourly cycle used to call ``run_role(..., state={})``. A model asked to invent alpha from an
empty context can only recite its priors; this module gives it the desk's measured facts instead
-- universe, data axes, frontier coverage, conversion backlog, empirical memory, portfolio
opportunity and resource state.

Facts only. Every section names the artifact it was read from and that artifact's mtime, so a
finding is attributable to a point in time. Interpretations, rankings and other agents'
conclusions are never read here; ``deepseek_cycle.cold_context`` still strips them if a caller
attaches one.

Nothing here is authoritative: the packet is context, never an instruction, and it can promote,
size or certify nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter, deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PACKET_VERSION = 1
MAX_ITEMS = 8
LEDGER_TAIL = 5_000


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _iso(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat(timespec="seconds")


def _entry(base: Path, rel: str) -> dict[str, Any]:
    path = base / rel
    try:
        st = path.stat()
    except OSError:
        return {"path": rel, "present": False}
    return {
        "path": rel,
        "present": True,
        "bytes": st.st_size,
        "mtime_utc": _iso(st.st_mtime),
        "age_hours": round(max(0.0, (datetime.now(tz=UTC).timestamp() - st.st_mtime) / 3600.0), 2),
    }


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rows(doc: Any, key: str | None = None) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict) and key:
        rows = doc.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _size_mb(path: Path) -> float | None:
    try:
        return round(path.stat().st_size / (1024.0 * 1024.0), 1)
    except OSError:
        return None


def _line_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return None


def _tail(path: Path, n: int = LEDGER_TAIL) -> list[dict[str, Any]]:
    buf: deque[str] = deque(maxlen=n)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.strip():
                    buf.append(line)
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in buf:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _safe(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except Exception as exc:  # a missing organ is UNMEASURED, never silently zero
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _universe(base: Path) -> dict[str, Any]:
    doc = _json(base / "desks/mt5/data/universe/universe.json") or {}
    rows = {k: v for k, v in doc.items() if not str(k).startswith("_") and isinstance(v, dict)}
    tradeable = [k for k, v in rows.items() if v.get("tradeable")]
    cats = Counter(str(v.get("category") or "unknown") for v in rows.values())
    tfs = Counter(tf for v in rows.values() for tf in (v.get("bars_by_timeframe") or {}))
    lasts = [str(v.get("last") or "") for v in rows.values() if v.get("last")]
    if not rows:
        return {"status": "UNMEASURED", "why": "universe.json absent or empty"}
    return {
        "symbols": len(rows),
        "tradeable": len(tradeable),
        "by_category": dict(cats.most_common(MAX_ITEMS)),
        "timeframes": dict(tfs.most_common(MAX_ITEMS)),
        "last_bar_utc": max(lasts) if lasts else None,
        "tradeable_sample": tradeable[:MAX_ITEMS],
    }


def _data_and_features(base: Path) -> dict[str, Any]:
    data = base / "desks/mt5/data"
    dirs: list[dict[str, Any]] = []
    try:
        for d in sorted((p for p in data.iterdir() if p.is_dir()), key=lambda p: p.name):
            files = [p for p in d.iterdir() if p.is_file()]
            newest = max((p.stat().st_mtime for p in files), default=0.0)
            dirs.append({"name": d.name, "files": len(files),
                         "newest_utc": _iso(newest) if newest else None})
    except OSError:
        pass
    dirs.sort(key=lambda r: (r["files"], r["name"]), reverse=True)
    if not dirs:
        return {"status": "UNMEASURED", "why": "no data directories under desks/mt5/data"}
    return {
        "data_dirs": dirs[:MAX_ITEMS],
        "data_dir_count": len(dirs),
        "axes": [{"name": p.stem, "mb": _size_mb(p)}
                 for p in sorted((data / "axes").glob("*.json"))[:MAX_ITEMS]]
        if (data / "axes").is_dir() else [],
    }


def _pit(base: Path) -> dict[str, Any]:
    rels = (
        "desks/mt5/data/universe/universe.json",
        "desks/mt5/data/sleeves.json",
        "desks/mt5/data/account_state.json",
        "desks/mt5/reports/pf_allocation.json",
        "desks/mt5/data/hypotheses/admissible_docket.json",
        "desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
        "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl",
        "docs/graveyard.md",
    )
    return {"artifacts": [_entry(base, rel) for rel in rels]}


def _frontier(base: Path) -> dict[str, Any]:
    docket = _json(base / "desks/mt5/data/hypotheses/admissible_docket.json") or {}
    cells = _rows(docket, "cells")
    fams = Counter(str(c.get("family") or "?") for c in cells)
    survivors = _json(base / "desks/mt5/reports/UNIVERSAL_SURVIVORS.json") or {}
    surv = survivors.get("survivors") if isinstance(survivors, dict) else None
    surv_n = int(survivors.get("n") or 0) if isinstance(survivors, dict) else 0
    sfams: Counter[str] = Counter()
    if isinstance(surv, dict):
        for cell in list(surv)[:200_000]:
            parts = str(cell).split(".")
            if len(parts) > 1:
                sfams[parts[1]] += 1
    known = set(fams) | set(sfams)
    if not cells and not surv_n:
        return {"status": "UNMEASURED", "why": "no admissible docket and no survivors report"}
    return {
        "docket_rows": len(cells) or int(docket.get("n") or 0),
        "docket_families": dict(fams.most_common(MAX_ITEMS)),
        "certified_survivors": surv_n,
        "survivor_families": dict(sfams.most_common(MAX_ITEMS)),
        "known_families": len(known),
        "graveyard_lines": _line_count(base / "docs/graveyard.md"),
    }


def _conversion(base: Path) -> dict[str, Any]:
    hyp = base / "desks/mt5/data/hypotheses"
    deepening = _json(hyp / "miner_deepening_queue.json")
    deepened = _json(hyp / "deepened_candidates.json")
    ortho = _json(hyp / "orthogonal_candidates.json")
    search = _json(hyp / "edge_search_results.json")
    if not any((hyp / n).exists() for n in ("miner_deepening_queue.json",
                                            "deepened_candidates.json",
                                            "orthogonal_candidates.json",
                                            "external_survivors.json")):
        return {"status": "UNMEASURED", "why": "no hypothesis artifacts under data/hypotheses"}
    return {
        "deepening_queue": len(_rows(deepening, "tasks")) if isinstance(deepening, dict)
        else len(_rows(deepening)),
        "deepened_candidates": len(_rows(deepened, "candidates")) if isinstance(deepened, dict)
        else len(_rows(deepened)),
        "orthogonal_candidates": len(_rows(ortho, "hypotheses")) if isinstance(ortho, dict)
        else len(_rows(ortho)),
        "search_results": len(_rows(search, "hypotheses")) if isinstance(search, dict)
        else len(_rows(search)),
        "raw_bank_mb": _size_mb(hyp / "external_survivors.json"),
        "conversion_handoff_mb": _size_mb(hyp / "conversion_handoff.json"),
    }


def _memory(base: Path) -> dict[str, Any]:
    ledger_path = base / "desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl"
    if not ledger_path.exists():
        return {"status": "UNMEASURED", "why": "gate_verdict_ledger.jsonl absent"}
    tail = _tail(ledger_path)
    gates: Counter[str] = Counter()
    failed: Counter[str] = Counter()
    fams: Counter[str] = Counter()
    passed = 0
    post_hoc = 0
    for row in tail:
        if row.get("passed"):
            passed += 1
        gates[str(row.get("terminal_gate") or "?")] += 1
        fams[str(row.get("family") or "?")] += 1
        for g in row.get("failed_gates") or []:
            failed[str(g)] += 1
        if str(row.get("prereg_status") or "").upper() == "POST_HOC":
            post_hoc += 1
    return {
        "judgements_in_tail": len(tail),
        "passed_in_tail": passed,
        "terminal_gates": dict(gates.most_common(MAX_ITEMS)),
        "failed_gates": dict(failed.most_common(MAX_ITEMS)),
        "families_in_tail": dict(fams.most_common(MAX_ITEMS)),
        "post_hoc_in_tail": post_hoc,
        "capability_records": _line_count(base / "docs/research/capability_challengers.jsonl"),
    }


def _portfolio(base: Path) -> dict[str, Any]:
    sleeves = _json(base / "desks/mt5/data/sleeves.json") or {}
    rows = _rows(sleeves, "sleeves")
    status = Counter(str(r.get("status") or "?") for r in rows)
    acct = _json(base / "desks/mt5/data/account_state.json") or {}
    pf = _json(base / "desks/mt5/reports/pf_allocation.json") or {}
    book = pf.get("book")
    if not isinstance(book, dict):
        book = {}
    if not rows and not acct:
        return {"status": "UNMEASURED", "why": "sleeves.json and account_state.json absent"}
    return {
        "sleeves": len(rows),
        "sleeve_status": dict(status.most_common(MAX_ITEMS)),
        "account": {k: acct.get(k) for k in ("venue", "currency", "balance", "equity",
                                             "open_positions")},
        "allocator": {"mode": pf.get("mode"), "armed": pf.get("armed"),
                      "effective_heat": pf.get("effective_heat"),
                      "book_rows": len(book), "no_trade": pf.get("no_trade")},
        "mechanism_mix": list((pf.get("mechanism_mix") or {}).keys())[:MAX_ITEMS]
        if isinstance(pf.get("mechanism_mix"), dict) else [],
    }


def _resources(base: Path) -> dict[str, Any]:
    disk = shutil.disk_usage(base)
    out: dict[str, Any] = {
        "cpu_count": os.cpu_count(),
        "disk_total_gb": round(disk.total / (1024.0 ** 3), 1),
        "disk_free_gb": round(disk.free / (1024.0 ** 3), 1),
    }
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]

        vm = psutil.virtual_memory()
        out["ram_total_gb"] = round(vm.total / (1024.0 ** 3), 1)
        out["ram_available_gb"] = round(vm.available / (1024.0 ** 3), 1)
    except Exception as exc:
        out["ram"] = f"UNMEASURED: {type(exc).__name__}"
    return out


def _stable(obj: Any) -> Any:
    """Drop wall-clock-only fields so the packet hash identifies content, not the second it ran."""
    if isinstance(obj, dict):
        return {k: _stable(v) for k, v in obj.items() if k not in ("age_hours",)}
    if isinstance(obj, list):
        return [_stable(v) for v in obj]
    return obj


def build(root: Path | str | None = None) -> dict[str, Any]:
    """Return the compact, PIT-stamped research packet the cold phase is given."""
    base = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    sections = {
        "universe": _safe(lambda: _universe(base)),
        "data_and_features": _safe(lambda: _data_and_features(base)),
        "point_in_time_metadata": _safe(lambda: _pit(base)),
        "research_frontier": _safe(lambda: _frontier(base)),
        "conversion_inventory": _safe(lambda: _conversion(base)),
        "empirical_memory": _safe(lambda: _memory(base)),
        "portfolio_opportunity_state": _safe(lambda: _portfolio(base)),
        "resource_state": _safe(lambda: _resources(base)),
    }
    measured = sum(1 for s in sections.values() if s.get("status") != "UNMEASURED")
    doc = {
        "packet_version": PACKET_VERSION,
        "generated_utc": _now(),
        "status": "MEASURED" if measured >= 6 else "PARTIAL",
        "sections_measured": measured,
        "sections": sections,
        "law": ("facts in, interpretations out. The packet can promote, size or certify nothing; "
                "every finding still enters the canonical compiler and gauntlet"),
    }
    doc["packet_hash"] = hashlib.sha256(
        json.dumps(_stable(sections), sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return doc
