"""THE LATENCY LAB -- the act clock's constants and the JSON/JSONL helpers its readers share.

WHAT IS LEFT OF IT. The hourly leg `latency_lab` is DEDUPLICATED (hourly_cycle names
`feed_clock_lab` canonical): the feed/clock observatory measures the tape's receipt clock and the
impact lab the desk's own order clock. What stays here is what those organs import rather than
re-derive, so there is one definition of each:

  TAUS_MS            the act-clock grid -- the delays at which "the desk acted this late" is
                     asked, reused as the lags the propagation graph is judged at. It starts at
                     one second on purpose: colocation is `cannot_reproduce` on this desk
                     (shadow_institutional), so the desk operates where latency does not bind,
                     one second to hours, and a grid below that would price a race it never runs.
  ROUTES_NOT_SIZES   the rule every latency finding carries on its payload.
  DELTA_SANE_MS      the bound outside which a receipt-vs-venue delta is a clock that is WRONG,
                     not skewed (scripts/check_clock_provenance uses the same bound).
  _f, _epoch_ms      the tolerant float and timestamp readers: None for anything unreadable,
                     never 0, never now (UNMEASURED IS A VALUE, L1.28a).
  get                a nested read that answers None instead of raising on a missing branch.
  read_jsonl         every dict row of an append-only ledger, torn and junk lines skipped.
  _write_atomic      tmp + os.replace, the house idiom (shadow_institutional._write_atomic).

NEGATIVES ARE KEPT. A receipt stamp earlier than the venue stamp is a broker-clock offset, and
dropping it would turn that offset into a flattering one-sided delay. Readers that summarise
deltas keep the sign and bound only the absolute value by DELTA_SANE_MS.

It measures nothing on its own, writes nothing unless a caller asks, and sizes nothing.
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

#: The act clock, in milliseconds: 1 s, 5 s, 15 s, 30 s, 1 m, 5 m, 15 m, 1 h.
TAUS_MS: tuple[int, ...] = (1_000, 5_000, 15_000, 30_000, 60_000, 300_000, 900_000, 3_600_000)
#: Receipt-vs-venue deltas beyond this are a wrong clock and are left out of any percentile.
DELTA_SANE_MS = 3_600_000
ROUTES_NOT_SIZES = ("a latency or timing finding routes research (a candidate_prior, a"
                    " hypothesis, an entry-timing input); it never sizes, caps or vetoes a"
                    " sleeve (GROWTH_GOVERNANCE Rule 1)")
#: Numbers above this are epoch MILLISECONDS; below it, epoch seconds (1e11 s is year 5138).
_MS_FLOOR = 1e11


def _f(value: Any) -> float | None:
    """A finite float, or None. A bool is not a number here: True is not a price."""
    if value is None or isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _epoch_ms(value: Any) -> float | None:
    """Epoch milliseconds from an ISO stamp, a datetime/Timestamp or an epoch number.

    A naive stamp is read as UTC (the desk's ledgers are UTC-stamped). An empty or unparseable
    value is None, never the current time: a row with no clock has no place on the act clock.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return dt.timestamp() * 1000.0
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp() * 1000.0
    if isinstance(value, int | float):
        v = _f(value)
        if v is None:
            return None
        return v if abs(v) >= _MS_FLOOR else v * 1000.0
    text = str(value).strip()
    if not text:
        return None
    num = _f(text)
    if num is not None:
        return _epoch_ms(num)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp() * 1000.0


def get(doc: Any, *path: Any, default: Any = None) -> Any:
    """`doc[path[0]][path[1]]...`, or `default` the moment a branch is missing or not a map."""
    cur = doc
    for key in path:
        if not isinstance(cur, Mapping) or key not in cur:
            return default
        cur = cur[key]
    return default if cur is None else cur


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Every dict row of a JSONL file; blank, torn and non-object lines skipped, absent is []."""
    rows: list[dict[str, Any]] = []
    try:
        with Path(path).open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it; `os.replace` onto a read-only file is WinError 5."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str, ensure_ascii=False)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    for attempt in range(2):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt or not path.exists():
                break
            try:
                os.chmod(path, 0o666)
            except OSError:
                break
        except OSError:
            break
    # The replace was refused: write in place rather than lose the artifact.
    path.write_text(body, encoding="utf-8")
    tmp.unlink(missing_ok=True)
