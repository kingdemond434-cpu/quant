"""THE COMMITTED DIGEST of the Asian / alt-data organs: what each one's last run measured.

WHY. Every report these organs write lives under `desks/mt5/reports/`, which `.gitignore`
excludes (`**/reports/*`): the box owns ~50 MB there and rewrites it hourly. So a reader on
GitHub could see that the code exists but not what it found. `runtime_attestation` publishes a
hash and a few scalars per organ; this adds, for the five new organs only, the few facts a
reviewer asks first -- status, rows, which sources/cells were measured and which were not, and
the gain verdicts -- in one small file under `desks/mt5/data/digests/`, which is tracked and
which the box's sync (`git add -A -- desks/mt5/data`) already carries.

SMALL AND DETERMINISTIC BY CONSTRUCTION. One section per organ, replaced whole on each of its
runs; every list is sorted and capped at MAX_LIST, keys are sorted, and nothing is written that
the run did not measure (no wall-clock beyond the run's own `at`). The same run inputs write the
same bytes.

    organs: alpha_capture, alt_proxies, nlp_event_factors, blog_social_mining, nlp_social_cells
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DIGEST = ROOT / "desks" / "mt5" / "data" / "digests" / "asia_alt_data_digest.json"
MAX_LIST = 60
UNMEASURED = "UNMEASURED"


def _sorted(items: Iterable[Any]) -> list[str]:
    return sorted({str(x) for x in items})[:MAX_LIST]


def section(*, at: str, status: str, rows: int | None, measured: Iterable[Any],
            unmeasured: Iterable[Any], gain: Mapping[str, Any],
            **extra: Any) -> dict[str, Any]:
    """The one shape every organ publishes. `gain` maps a tested unit to its verdict string."""
    g = {str(k): str(v) for k, v in sorted(gain.items(), key=lambda kv: str(kv[0]))}
    counts: dict[str, int] = {}
    for v in g.values():
        counts[v] = counts.get(v, 0) + 1
    return {"at": at, "status": status, "rows": rows if rows is not None else UNMEASURED,
            "measured": _sorted(measured), "unmeasured": _sorted(unmeasured),
            "gain_counts": dict(sorted(counts.items())),
            "gain": dict(list(g.items())[:MAX_LIST]), **extra}


def _lock(path: Path, wait_s: float = 5.0) -> int | None:
    lock = path.with_name(path.name + ".lock")
    end = time.monotonic() + wait_s
    while True:
        try:
            return os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 120:        # a crashed writer's lock
                    lock.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() > end:
                return None                  # proceed unlocked: a lost section heals next run
            time.sleep(0.05)
        except OSError:
            return None


def publish(organ: str, body: Mapping[str, Any], path: Path = DIGEST) -> Path:
    """Replace `organ`'s section of the digest; other organs' sections are kept as they are."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = _lock(path)
    try:
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        prior = doc.get("organs")
        organs: dict[str, Any] = dict(prior) if isinstance(prior, dict) else {}
        organs[organ] = dict(body)
        out = {"what": ("last-run digest of the Asian / alt-data organs; the full reports stay "
                        "box-local under desks/mt5/reports (gitignored)"),
               "organs": dict(sorted(organs.items()))}
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False,
                                  default=str) + "\n", "utf-8")
        os.replace(tmp, path)
    finally:
        if fd is not None:
            os.close(fd)
            with contextlib.suppress(OSError):
                path.with_name(path.name + ".lock").unlink()
    return path
