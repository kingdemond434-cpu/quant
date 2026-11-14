"""LIVE AGAINST ITS OWN BACKTEST: the decay kill switch's comparison half.

The decay ladder (`decay_monitor.verdict`) judges a live sleeve against FIXED bars: n, t and a
drawdown rail. It never asked the question the kill switch exists for: "is this sleeve doing
what its certificate said it would?" This module answers it per sleeve, from evidence the desk
already keeps, and moves the ladder ONE step, two-sided, exactly as `decay_regime` does:

    VETO        the blind reviewer's latest reading of the sleeve's own certificate is VETO:
                the backtest no longer reproduces from the data, so the live row rests on a
                claim the desk cannot stand behind. HEALTHY -> FADE.
    CONTRADICTS the reproduction says the edge is positive (t >= REPRO_T) and the sleeve's live
                record says the opposite with as much evidence as promotion demanded of good
                (n >= MIN_N, mean <= 0, t <= -LIVE_T). HEALTHY -> FADE.
    AGREES / UNMEASURED
                nothing moves.

UNIT-SAFE BY CONSTRUCTION. Live trades are R multiples; a reproduction's expectancy is in the
certificate's own unit (daily R for some gates, per-trade for others -- measured 2026-11-11 on
the TG3 cells). So the comparison is on SIGN and on t, which are unit-free, never on the gap
between two numbers in different units.

TWO-SIDED, AND IT RETIRES NOTHING. The step is a FADE only; when the condition clears (a later
PASS, or the live record recovers) the ladder reads HEALTHY again and the monitor's own UNFADE
lifts it. The drawdown rail and the pooled verdicts are untouched, and a RETIRE the ladder
reached stays a RETIRE. gold_asia is exempt, as it is from every decay step (principal
2026-10-29). Each step is logged to the same episode ledger `decay_regime` uses, so its realised
value is priced (GROWTH_GOVERNANCE Rule 1).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: The blind reviewer's own ledger, read here as a FILE rather than through `blind_reviewer`:
#: importing that module would pull the re-execution engine (hostile roster, replay) into the
#: money path's import closure for the sake of reading one JSONL.
REVIEW_LEDGER = Path(__file__).resolve().parents[1] / "data" / "blind_review_ledger.jsonl"

EXEMPT = {"gold_asia", "xauusd.asia"}
MIN_N = 10
LIVE_T = 2.0
REPRO_T = 2.0


def certificate_cell(row: dict) -> str | None:
    """The certificate key a roster row was promoted on, whichever shape the promoter wrote."""
    c = row.get("certificate")
    if isinstance(c, dict):
        cell = c.get("cell") or c.get("key") or c.get("certificate")
        return str(cell) if cell else None
    if isinstance(c, str) and c:
        return c
    for k in ("principal_certificate", "source_cell", "cell"):
        if row.get(k):
            return str(row[k])
    return None


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def reference(row: dict, reviews: dict[str, dict]) -> dict:
    """What the backtest says about this sleeve now: the blind reviewer's latest row for its
    certificate. `reviews` is cell -> latest ledger row. UNMEASURED when there is none."""
    cell = certificate_cell(row)
    if not cell:
        return {"status": "UNMEASURED", "why": "the roster row names no certificate"}
    rev = reviews.get(cell)
    if rev is None:
        # The ledger keys `<hunt>.<cell>`; a roster row may carry the bare cell, or the hunt-
        # qualified one against a bare ledger key. EXACT on the cell part only: a suffix match
        # could pin another hunt's VETO on the wrong cell (#1005 audit should-fix).
        hits = sorted(k for k in reviews
                      if k.split(".", 1)[1:] == [cell] or cell.split(".", 1)[1:] == [k])
        if len(hits) > 1:
            return {"status": "UNMEASURED", "cell": cell,
                    "why": (f"{len(hits)} hunts reviewed a cell named {cell} "
                            f"({', '.join(hits[:4])}); the roster row does not say which")}
        rev = reviews[hits[0]] if hits else None
    if rev is None:
        return {"status": "UNMEASURED", "cell": cell,
                "why": "the blind reviewer has never reproduced this certificate"}
    rep = rev.get("reproduced") or {}
    return {"status": "MEASURED", "cell": cell, "verdict": str(rev.get("verdict") or ""),
            "reviewed_at": rev.get("at"), "repro_n": rep.get("n"),
            "repro_t": _num(rep.get("t")), "repro_expectancy": _num(rep.get("expectancy"))}


def gap(s: dict, ref: dict) -> tuple[str, str]:
    """(VETO | CONTRADICTS | AGREES | UNMEASURED, why) for live stats `s` against `ref`."""
    if ref.get("status") != "MEASURED":
        return "UNMEASURED", str(ref.get("why") or "no reproduction")
    if ref.get("verdict") == "VETO":
        return "VETO", (f"the blind reviewer VETOED certificate {ref['cell']} at "
                        f"{ref.get('reviewed_at')}: the backtest this sleeve rests on no longer "
                        f"reproduces")
    rt = ref.get("repro_t")
    n, t, mean = int(s.get("n") or 0), float(s.get("t") or 0.0), float(s.get("exp_r") or 0.0)
    if rt is not None and rt >= REPRO_T and n >= MIN_N and mean <= 0.0 and t <= -LIVE_T:
        return "CONTRADICTS", (f"backtest reproduces at t={rt:.2f} but live reads t={t} "
                               f"exp={mean}R over n={n}: the sleeve is not doing what its "
                               f"certificate says")
    return "AGREES", (f"live t={t} over n={n} against reproduction t={rt}: no contradiction "
                      f"at the bar (n>={MIN_N}, live t<=-{LIVE_T}, repro t>={REPRO_T})")


def adjust(name: str, verdict: str, why: str, s: dict, ref: dict
           ) -> tuple[str, str, str | None, str]:
    """(verdict, why, step, gap_class). Moves HEALTHY -> FADE on VETO / CONTRADICTS, nothing
    else; gold_asia is exempt."""
    cls, gwhy = gap(s, ref)
    if name.lower() in EXEMPT:
        return verdict, why, None, cls
    if verdict == "HEALTHY" and cls in ("VETO", "CONTRADICTS"):
        return "FADE", f"{gwhy} (one step from the ladder's HEALTHY: {why})", \
            f"HEALTHY->FADE:{cls.lower()}", cls
    return verdict, why, None, cls


def latest_reviews(ledger_rows: list[dict]) -> dict[str, dict]:
    """cell -> its latest blind-review ledger row, latest by append order (as the promoter)."""
    out: dict[str, dict] = {}
    for r in ledger_rows:
        if isinstance(r, dict) and r.get("cell"):
            out[str(r["cell"])] = r
    return out


def read_reviews(path: Path | None = None) -> dict[str, dict]:
    """cell -> latest review row from the ledger file. An absent or unreadable file RAISES
    OSError; the caller (`decay_monitor._reviews`) turns that into {} so every comparison reads
    UNMEASURED and nothing moves. An unparseable line is skipped."""
    p = path or REVIEW_LEDGER
    rows: list[dict] = []
    with p.open(encoding="utf-8") as fh:            # OSError propagates to the caller
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                rows.append(r)
    return latest_reviews(rows)
