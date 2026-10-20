"""The realised-risk-in-EUR invariant: the order risks what the allocator INTENDED, no more.

WHAT IT ENFORCES, AND WHAT IT DOES NOT (2026-10-20). 441071a47 capped the final family lot at
the GLOBAL per-order envelope (`MAX_RISK_FRAC` x equity at the stop). That bounds every order by
one house number; it says nothing about THIS sleeve. A sleeve the allocator sized at 3% could
reach the venue at 4.4% -- the currency-leg and macro modifiers' nearest-step rounding and the
`max(volume_min, ...)` lift both push upward -- and stay under the 10% envelope throughout.

INTENDED risk is the sleeve's resolved fraction INCLUDING its two-sided modifiers (`leg_mult`,
`macro_mult`), times equity. A boost the modifiers decided is intent, so their upside is never
clipped here. REALISED risk is the final lot x stop distance x EUR per price unit per lot. The
invariant only removes the part of the order that NOBODY decided: the rounding overshoot. It is
not a smaller book (GROWTH_GOVERNANCE Rule 1 / allocator sovereignty): the allocator's fraction
goes out as resolved, to within one venue step at or under PRE_TOL x intent.

    pre-order   realised > PRE_TOL x intended  -> floor to the largest venue step <= that bound;
                below volume_min                -> refuse ("risk_intent"), never lift
    post-fill   risk at the FILL price and the actual SL > POST_TOL x intended
                -> breach row + halt THAT sleeve's new entries (no close, no other sleeve)

The halt lifts when the breach is acknowledged (`ACK` file, breach id or sleeve name) or a pass
re-measures the sleeve's held positions within POST_TOL. A sleeve with nothing open has nothing
to re-measure: that is UNMEASURED, never clean (L1.28a), so it waits for the acknowledgement.

Missed-growth lines: `research.missed_growth.measure_risk_intent_floor` and
`measure_realised_risk_halt`. The rail register (`libs/portfolio/rails.py`) is sealed; the hunk
that registers both is shipped separately for the sealed pass.

NOTHING HERE TOUCHES THE VENUE. Pure arithmetic, a JSONL appender that never raises, and
functions over the gateway's own pass-state dict.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Pre-order tolerance: realised may exceed intent by at most this factor (one step of slack on
#: small accounts is the reason it is not 1.0).
PRE_TOL = 1.10
#: Post-fill tolerance: a fill whose risk at its own price and stop exceeds this x intent is a
#: breach -- slippage or a stop the venue moved, not rounding.
POST_TOL = 1.50
#: How many recent fills the health row summarises.
FILL_WINDOW = 50


class Unmeasured(ValueError):
    """An input the invariant needs is absent, non-finite or non-positive."""


def _pos(value: object, name: str) -> float:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise Unmeasured(f"{name} unreadable ({value!r})") from exc
    if not (math.isfinite(v) and v > 0.0):
        raise Unmeasured(f"{name} is {v!r}, not a positive finite number")
    return v


def _floor_steps(x: float, step: float) -> float:
    return round(math.floor(x / step + 1e-9) * step, 8)


def enforce(lot: float, intended_frac: float, equity: float, dist: float, unit: float,
            vstep: float, vmin: float, *, sovereign: bool = True) -> dict[str, Any]:
    """Hold the final lot to PRE_TOL x the intended EUR at the stop.

    Returns `ok`, `stage`, `why`, `lot`, `realised_eur` (of the RETURNED lot), `intended_eur`,
    `ratio`, `floored` and `pre_lot`. Raises `Unmeasured` on any unusable input -- the caller
    refuses by name, exactly as the 441071a47 envelope does.

    Under the revert (`sovereign=False`, the principal's `ALLOCATOR_SOVEREIGN.json` switch) the
    venue-minimum lift is the documented behaviour, so a floor that would fall below the minimum
    sends the minimum and says so instead of refusing.
    """
    lot = float(lot)
    if not (math.isfinite(lot) and lot > 0.0):
        raise Unmeasured(f"final lot is {lot!r}")
    equity = _pos(equity, "equity")
    dist = _pos(dist, "stop distance")
    unit = _pos(unit, "EUR per price unit")
    vstep = _pos(vstep, "volume_step")
    vmin = _pos(vmin, "volume_min")
    try:
        frac = float(intended_frac)
    except (TypeError, ValueError) as exc:
        raise Unmeasured(f"intended fraction unreadable ({intended_frac!r})") from exc
    if not (math.isfinite(frac) and frac >= 0.0):
        raise Unmeasured(f"intended fraction is {frac!r}")
    intended = frac * equity
    per_lot = dist * unit
    realised = lot * per_lot
    base = {"pre_lot": lot, "intended_eur": round(intended, 6)}
    if not intended > 0.0:
        if sovereign:
            return {**base, "ok": False, "stage": "risk_intent", "lot": 0.0,
                    "realised_eur": round(realised, 6), "ratio": None, "floored": False,
                    "why": "intent is zero EUR but a lot was resolved; zero sends no order"}
        return {**base, "ok": True, "stage": "ok", "lot": lot, "floored": False,
                "realised_eur": round(realised, 6), "ratio": None,
                "why": "revert path: zero intent lifted to the venue minimum by policy"}
    bound = PRE_TOL * intended
    if realised <= bound * (1.0 + 1e-9):
        return {**base, "ok": True, "stage": "ok", "lot": lot, "floored": False,
                "realised_eur": round(realised, 6), "ratio": round(realised / intended, 6),
                "why": f"realised {realised:.2f} EUR within {PRE_TOL:g}x intent {intended:.2f}"}
    capped = _floor_steps(bound / per_lot, vstep)
    if capped + 1e-12 < vmin:
        if sovereign:
            return {**base, "ok": False, "stage": "risk_intent", "lot": 0.0, "floored": False,
                    "realised_eur": round(realised, 6), "ratio": round(realised / intended, 6),
                    "why": (f"venue minimum {vmin:g} lot risks {vmin * per_lot:.2f} EUR against "
                            f"an intent of {intended:.2f} EUR ({PRE_TOL:g}x = {bound:.2f}); "
                            f"snapped down, never lifted")}
        capped = vmin
    new_real = capped * per_lot
    return {**base, "ok": True, "stage": "ok", "lot": float(capped), "floored": True,
            "realised_eur": round(new_real, 6), "ratio": round(new_real / intended, 6),
            "why": (f"floored {lot:g} -> {capped:g} lot: {realised:.2f} EUR at the stop was "
                    f"{realised / intended:.2f}x the {intended:.2f} EUR intended")}


def enforce_on_venue(lot: float, intended_frac: float, equity: float, dist: float,
                     sym: object, unit_fn: Callable[[], float], *,
                     sovereign: bool = True) -> dict[str, Any]:
    """`enforce` with the venue's own step, minimum and EUR conversion read off `sym`.

    No defaults: a symbol that does not state its step or minimum, or a conversion that raises,
    is `Unmeasured` -- a guessed 0.01 is how a share CFD's 0.1 minimum was once mis-sized.
    """
    try:
        unit = unit_fn()
    except Exception as exc:
        raise Unmeasured(f"EUR per price unit unavailable ({type(exc).__name__}: {exc})") from exc
    return enforce(lot, intended_frac, equity, dist, unit,
                   getattr(sym, "volume_step", None),  # type: ignore[arg-type]
                   getattr(sym, "volume_min", None),  # type: ignore[arg-type]
                   sovereign=sovereign)


def fill_risk_eur(volume: object, fill_price: object, sl: object, side: int,
                  unit: object) -> float:
    """EUR at risk from the FILL price to the actual stop. A stop on the profit side is 0."""
    vol = _pos(volume, "fill volume")
    px = _pos(fill_price, "fill price")
    stop = _pos(sl, "stop loss")
    u = _pos(unit, "EUR per price unit")
    if int(side) not in (1, -1):
        raise Unmeasured(f"side is {side!r}")
    return max(0.0, int(side) * (px - stop)) * vol * u


def measure_fill(*, sleeve: str, symbol: str, side: int, volume: object, fill_price: object,
                 sl: object, unit: object, intended_eur: object, lane: str,
                 deal: object = None, pre_lot: object = None,
                 floored: object = None) -> dict[str, Any]:
    """One post-fill measurement row. Unmeasurable inputs give a row saying so, never a ratio."""
    row: dict[str, Any] = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                           "sleeve": sleeve, "symbol": symbol, "lane": lane,
                           "side": "buy" if int(side) > 0 else "sell", "deal": deal,
                           "volume": volume, "fill_price": fill_price, "sl": sl,
                           "pre_lot": pre_lot, "floored": floored}
    try:
        intended = _pos(intended_eur, "intended EUR")
        realised = fill_risk_eur(volume, fill_price, sl, side, unit)
    except Unmeasured as exc:
        row.update({"status": "UNMEASURED", "why": str(exc), "breach": False})
        return row
    ratio = realised / intended
    row.update({"status": "MEASURED", "intended_eur": round(intended, 6),
                "realised_eur": round(realised, 6), "ratio": round(ratio, 6),
                "breach": bool(ratio > POST_TOL)})
    row["breach_id"] = (f"{sleeve}:{deal}:{row['at']}" if row["breach"] else None)
    return row


def append_jsonl(path: Path, row: dict[str, Any]) -> bool:
    """Append one row. NEVER raises: telemetry must not break the money path."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        return True
    except Exception:
        return False


# ------------------------------------------------------------------------------- the halt
def halt(st: dict, row: dict[str, Any]) -> None:
    """Halt the breaching sleeve's NEW entries. Its open position is left exactly as it is."""
    st.setdefault("risk_halt", {})[str(row["sleeve"])] = {
        "breach_id": row.get("breach_id"), "at": row.get("at"), "symbol": row.get("symbol"),
        "intended_eur": row.get("intended_eur"), "realised_eur": row.get("realised_eur"),
        "ratio": row.get("ratio")}


def halted(st: dict, name: str) -> dict[str, Any] | None:
    h = (st.get("risk_halt") or {}).get(name)
    return h if isinstance(h, dict) else None


def halt_why(h: dict[str, Any]) -> str:
    return (f"refused: realised-risk halt since {h.get('at')} -- a fill risked "
            f"{h.get('realised_eur')} EUR against {h.get('intended_eur')} intended "
            f"({h.get('ratio')}x > {POST_TOL:g}x); new entries wait for the breach "
            f"{h.get('breach_id')} to be acknowledged or re-measured clean")


def read_acks(path: Path) -> set[str]:
    """Acknowledged breach ids or sleeve names: {"acknowledged": [...]}. Unreadable -> none."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    vals = doc.get("acknowledged") if isinstance(doc, dict) else doc
    return {str(x) for x in vals} if isinstance(vals, list) else set()


def review_halts(st: dict, acks: set[str],
                 positions_for: Callable[[str, str], Iterable[Any]],
                 unit_for: Callable[[str], float]) -> list[str]:
    """Lift halts that are acknowledged or re-measured clean. Returns one note per halt read.

    Re-measure: the sleeve's OPEN positions, each priced from its own open price to its current
    stop. Within POST_TOL x the recorded intent lifts the halt. No open position, an unreadable
    one, or a position with no stop is UNMEASURED and the halt stands.
    """
    notes: list[str] = []
    book = st.get("risk_halt") or {}
    for name in list(book):
        h = book[name] if isinstance(book[name], dict) else {}
        if name in acks or (h.get("breach_id") and str(h["breach_id"]) in acks):
            book.pop(name, None)
            notes.append(f"[{name}] realised-risk halt LIFTED: acknowledged")
            continue
        try:
            symbol = str(h.get("symbol") or "")
            positions = list(positions_for(symbol, name))
            if not positions:
                raise Unmeasured("no open position to re-measure")
            intended = _pos(h.get("intended_eur"), "recorded intent")
            unit = unit_for(symbol)
            risk = sum(fill_risk_eur(getattr(p, "volume", None), getattr(p, "price_open", None),
                                     getattr(p, "sl", None),
                                     1 if int(getattr(p, "type", 0)) == 0 else -1, unit)
                       for p in positions)
        except Exception as exc:
            notes.append(f"[{name}] realised-risk halt stands: UNMEASURED ({exc})")
            continue
        if risk <= POST_TOL * intended:
            book.pop(name, None)
            notes.append(f"[{name}] realised-risk halt LIFTED: held risk re-measured "
                         f"{risk:.2f} EUR <= {POST_TOL:g}x {intended:.2f}")
        else:
            notes.append(f"[{name}] realised-risk halt stands: held risk {risk:.2f} EUR > "
                         f"{POST_TOL:g}x {intended:.2f}")
    if not book:
        st.pop("risk_halt", None)
    return notes


# ------------------------------------------------------------------------------ the summary
def _quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def ratio_summary(path: Path, n: int = FILL_WINDOW) -> dict[str, Any]:
    """realised/intended over the last `n` MEASURED fills. None of them is UNMEASURED."""
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if isinstance(r, dict):
                    rows.append(r)
    except (OSError, ValueError):
        rows = []
    ratios = [float(r["ratio"]) for r in rows
              if r.get("status") == "MEASURED" and isinstance(r.get("ratio"), (int, float))
              and math.isfinite(float(r["ratio"]))][-n:]
    if not ratios:
        return {"status": "UNMEASURED", "n": 0, "n_rows": len(rows),
                "why": f"no measured fill in {path.name}"}
    return {"status": "MEASURED", "n": len(ratios), "n_rows": len(rows),
            "p50": round(_quantile(ratios, 0.50), 4), "p95": round(_quantile(ratios, 0.95), 4),
            "max": round(max(ratios), 4),
            "n_breaches": sum(1 for x in ratios if x > POST_TOL)}
