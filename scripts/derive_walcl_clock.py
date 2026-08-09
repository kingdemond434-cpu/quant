"""WALCL reserve-impulse forward clock -- R0031, pre-registered 2026-07-31.

STAGE A EVIDENCE (data/fred_macro_screen.json, trial fred_macro::reserve_quantity_impulse::h1b):
IC +0.1106 on n=815 weekly obs, mechanism-consistent momentum sign (Sharpe 0.82), de-contamination
PASSED (residual IC +0.0964), verdict SCREEN-UNDERPOWERED -- the 4-week window sampled weekly
carries ~204 independent obs (t~1.6) against a min-detectable IC of 0.1816. The power wall cannot
be closed retroactively; the honest path is FORWARD ACCRUAL under the Two-Stage law. This clock
fills the Holm slot freed by the kimchi_premium retirement (cohort 11 -> 12, cap 12).

PRE-REGISTERED CONSTRUCTION (mirrors the screen exactly; changing any of it is a NEW trial):
  signal   = 4-week log change in WALCL (Fed H.4.1 balance sheet, weekly Wednesday as-of)
  lag      = +2 calendar days on every observation (Thursday 16:30 ET release -> usable from the
             Friday 00:00Z crypto close; same explicit-lag alignment the screen declared)
  z        = trailing 20-observation z-score of the impulse (inclusive rolling window, past-only)
  direction= +1 (momentum: long BTC when z > 0), target = BTCUSDT next-day close-to-close,
             position held constant between weekly releases (the daily axis-clock evaluation of a
             weekly-held signal IS the weekly-hold strategy; nw_tstat prices the autocorrelation)

The clock's first forward day is its registration day. This deriver NEVER back-writes dates --
forward evidence begins now, or it is not forward evidence.

Laws: L1.25a(b) (survivors hunted daily -- an empty slot with a non-empty candidate space is an
idleness defect), TWO-STAGE DISCOVERY (Stage A earns a clock, never a cent), L1.41 (build
standard). Reads data/fred_macro.json (written daily by collect_fred_macro.py); no network.

    python scripts/derive_walcl_clock.py
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_ARCHIVE = _ROOT / "data" / "fred_macro.json"
_CLOCK = _ROOT / "data" / "walcl_impulse.jsonl"

#: Pre-registered constants -- constants for the life of the clock (a second window is a second
#: trial and raises VARIANTS_TRIED at the screen, never a silent edit here).
_IMPULSE_WEEKS = 4
_ZWIN = 20
_RELEASE_LAG_DAYS = 2
#: Refuse to emit a z until the window is genuinely full: a z against a part-window is a
#: different (unregistered) construction.
_MIN_OBS = _IMPULSE_WEEKS + _ZWIN


def _series() -> list[tuple[str, float]]:
    """WALCL (date, value) rows from the FRED archive, oldest first.

    Refusal path (L1.41): a missing/unreadable/short archive returns [] and the caller exits
    non-zero saying so -- this clock must never fabricate a row from absent input.
    """
    try:
        doc = json.loads(_ARCHIVE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = doc.get("series", {}).get("WALCL", [])
    out = [(str(d), float(v)) for d, v in rows if v]
    out.sort()
    return out


def signal_for(today: str, rows: list[tuple[str, float]]) -> dict | None:
    """The pre-registered z for date `today`, from observations AVAILABLE by then.

    Availability = as-of date + _RELEASE_LAG_DAYS. Returns None when the usable history is
    shorter than _MIN_OBS (refusal, not zero -- a fabricated 0.0 would be a position).
    """
    avail = [(d, v) for d, v in rows
             if (datetime.fromisoformat(d) + timedelta(days=_RELEASE_LAG_DAYS)).date().isoformat()
             <= today]
    if len(avail) < _MIN_OBS:
        return None
    imp = [math.log(avail[i][1]) - math.log(avail[i - _IMPULSE_WEEKS][1])
           for i in range(_IMPULSE_WEEKS, len(avail))]
    win = imp[-_ZWIN:]
    mean = sum(win) / len(win)
    var = sum((x - mean) ** 2 for x in win) / len(win)
    sd = math.sqrt(var)
    if sd < 1e-12:
        return None                # degenerate window (incl. float-noise flat): refuse, loudly
    return {"date": today, "z20": round((imp[-1] - mean) / sd, 4),
            "asof": avail[-1][0], "impulse": round(imp[-1], 6)}


def main() -> int:
    _law_guard()
    today = datetime.now(tz=UTC).date().isoformat()
    rows = _series()
    if not rows:
        print(f"walcl-clock: CANNOT MEASURE -- {_ARCHIVE} missing/unreadable/empty; no row written")
        return 1
    sig = signal_for(today, rows)
    if sig is None:
        print(f"walcl-clock: CANNOT MEASURE -- {len(rows)} obs available, need {_MIN_OBS} "
              "with release lag; no row written")
        return 1
    if _CLOCK.exists():
        for line in _CLOCK.read_text("utf-8").splitlines():
            try:
                if json.loads(line).get("date") == today:
                    print(f"walcl-clock: {today} already recorded (idempotent) -- z {sig['z20']}")
                    return 0
            except json.JSONDecodeError:
                continue
    with _CLOCK.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sig) + "\n")
    print(f"walcl-clock: {today} z {sig['z20']} (asof {sig['asof']}, "
          f"impulse {sig['impulse']}) -> {_CLOCK.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
