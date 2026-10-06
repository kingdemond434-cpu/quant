"""VERIFIED DATASET USE -- which consumer actually READ which dataset, at which version, for what.

THE GAP (principal, 2026-10-06): *"publishing intelligence is not proof that a decision consumes
it"* and *"fully used must mean more than produced cells"*. The desk could say a dataset was
listed, fetched, parsed or turned into cells; it could not say which organ read it last, which
vintage that read saw, or which of the legitimate uses the read served. "Use verified" was a
claim with no record behind it.

THE RECORD. A consumer calls `record_reads(consumer, {dataset: version}, use=...)` at the moment
it actually loads data. Each consumer owns ONE file (`data/dataset_use/<consumer>.json`), so
concurrent organs never contend for a lock and a crashed writer can only lose its own row.
`census()` folds every consumer file into per-dataset rows: the consumers, the uses they serve,
the version each read and how long ago.

THE USES are the eight the principal's acquisition order names, and a dataset earns credit for a
demonstrated read in ANY of them -- it is never forced to manufacture a trading signal to turn a
dashboard green:

    new_hypotheses   a candidate/cell generator read it as a predictor
    conditioning     an existing strategy is gated or scaled by it
    nowcast          it enters an economic-state estimate or a published forecast
    regime_state     it enters a regime / latent-state model
    risk             volatility, covariance, tail or concentration estimation
    execution        spreads, slippage, financing, capacity
    verification     an independent cross-check of another source
    research_priority it steers what the desk investigates next

RECORDING NEVER BREAKS A CONSUMER. Every write is best-effort and atomic; a disk error is
swallowed, because a reader that fails to log must still trade, research and decide. A missing
record therefore reads UNMEASURED in the census -- never "unused", never zero.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
USE_DIR = ROOT / "desks" / "mt5" / "data" / "dataset_use"

USES: tuple[str, ...] = ("new_hypotheses", "conditioning", "nowcast", "regime_state", "risk",
                         "execution", "verification", "research_priority")

#: A read older than this no longer demonstrates CURRENT use; the census marks it STALE.
STALE_AFTER_S = 3 * 86400

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")

#: Per-process memo of reads already written, so a consumer that looks one series up thousands
#: of times in a pass writes it once per `_REWRITE_S` instead of rewriting its file each time.
_RECENT: dict[tuple[str, str, str, str], float] = {}
_REWRITE_S = 600.0


def _now() -> datetime:
    return datetime.now(UTC)


def _file(consumer: str, root: Path | None = None) -> Path:
    return (root or USE_DIR) / f"{_SAFE.sub('_', consumer)[:80]}.json"


def record_reads(consumer: str, datasets: Mapping[str, str | None], *, use: str,
                 root: Path | None = None, now: datetime | None = None) -> bool:
    """Record that `consumer` just read every dataset in `datasets` (id -> version) for `use`.

    Returns True when the record was written. Never raises."""
    if use not in USES or not consumer or not datasets:
        return False
    when = now or _now()
    stamp = when.timestamp()
    key_root = str(root or USE_DIR)
    todo = {ds: v for ds, v in datasets.items()
            if stamp - _RECENT.get((key_root, consumer, str(ds), use), -1e18) >= _REWRITE_S}
    if not todo:
        return True
    datasets = todo
    at = when.isoformat(timespec="seconds")
    path = _file(consumer, root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            doc = json.loads(path.read_text("utf-8"))
            if not isinstance(doc, dict):
                doc = {}
        except (OSError, ValueError):
            doc = {}
        rows = doc.setdefault("datasets", {})
        for ds, version in datasets.items():
            row = rows.setdefault(str(ds), {"uses": {}, "reads": 0, "first_read_at": at})
            row["reads"] = int(row.get("reads") or 0) + 1
            row["last_read_at"] = at
            row["version"] = None if version is None else str(version)
            row.setdefault("uses", {})[use] = at
        doc.update({"consumer": consumer, "updated_at": at})
        tmp = path.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), "utf-8")
        os.replace(tmp, path)
        for ds in datasets:
            _RECENT[(key_root, consumer, str(ds), use)] = stamp
        return True
    except OSError:
        return False


def census(root: Path | None = None, *, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """dataset -> {consumers: {name: {version, last_read_at, uses, stale}}, uses: [...],
    live_consumers: n}. Built only from recorded reads."""
    base = root or USE_DIR
    at = now or _now()
    out: dict[str, dict[str, Any]] = {}
    try:
        files = sorted(base.glob("*.json"))
    except OSError:
        files = []
    for f in files:
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        consumer = str(doc.get("consumer") or f.stem)
        for ds, row in (doc.get("datasets") or {}).items():
            if not isinstance(row, dict):
                continue
            try:
                last = datetime.fromisoformat(str(row.get("last_read_at")))
                age = (at - last.astimezone(UTC)).total_seconds()
            except (TypeError, ValueError):
                age = None
            stale = age is None or age > STALE_AFTER_S
            e = out.setdefault(str(ds), {"consumers": {}, "uses": set(), "live_consumers": 0})
            e["consumers"][consumer] = {"version": row.get("version"),
                                        "last_read_at": row.get("last_read_at"),
                                        "uses": sorted((row.get("uses") or {}).keys()),
                                        "stale": stale}
            if not stale:
                e["live_consumers"] += 1
                e["uses"].update((row.get("uses") or {}).keys())
    for e in out.values():
        e["uses"] = sorted(e["uses"])
    return out
