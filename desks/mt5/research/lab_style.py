"""LAB STYLE SCREEN: is a lab cell a style the desk already owns, measured before it is donated.

THE ASK (principal 2026-10-13 21:31Z, routed by the coordinator): hunt UNKNOWN styles. Tier-1's
`style_novelty` (#377) found 0 of 43 certificates novel -- every live edge projects onto a
textbook style (passive window, range breakout, trend, carry). The LLM lab's conditioned cells
(central-bank tone, collector series, forum and local-language streams) exist to be the opposite,
and nothing checked that they were: a conditioner whose direction choice reduces to "long the
window" is the passive-window style wearing a data source.

WHAT IS MEASURED. Each cell's own signals, on the instrument's own H1 bars, are projected onto
the same known-style library with the same code `style_novelty` applies to certificates
(`style_matrix` and `project`, imported, never copied), so a lab cell and a certificate are read
on one ruler. The reading is `novelty_return` (1 - adjusted R^2 on the styles) and the
`dominant_style` when the fit explains enough to name one.

WHAT IT CHANGES, AND WHAT IT DOES NOT.
  * A cell whose dominant style is SATURATED -- it dominates at least SATURATION_SHARE of the
    desk's measured certificates in STYLE_NOVELTY.json `dominant_style_counts` -- and whose
    novelty_return is below the certificate threshold is HELD, not donated: it would re-buy a
    style the desk owns and spend a family-wise trial doing so. HELD IS NOT DROPPED: the row is
    kept in `style_held.json` with its measurement and released on the first pass at which its
    style is no longer saturated. Nothing is deleted, and the trial count only falls by trials
    that were never run.
  * NOVEL and UNMEASURED cells are donated exactly as before. UNMEASURED is not a pass (L1.28a):
    the row carries `style_screen.status = UNMEASURED` and earns half credit, labelled.
  * The verdict loop credits a lab by NOVEL certified k_eff (`credit_weight`), so the lab ranking
    spends calls on the labs whose certificates are new styles.
No bar, gate, trial charge or promotion path is touched: models still have zero authority and the
one gauntlet judges every donated row.
"""
from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = BASE / "data" / "llm_lab"
HELD = STATE_DIR / "style_held.json"
REPORT = BASE / "reports" / "STYLE_NOVELTY.json"
BARS_DIR = BASE / "data" / "universe"
UNMEASURED = "UNMEASURED"

#: A style is SATURATED when it is the dominant style of at least this share of the desk's
#: measured certificates: the book already owns it, so another cell of it buys no new bet.
SATURATION_SHARE = 0.10
#: Fallback when STYLE_NOVELTY.json carries no threshold: style_novelty.NOVEL_T.
NOVEL_T = 0.5
#: Credit per certified cell by screen verdict. UNMEASURED is half, labelled, as PROXY_KEFF is.
CREDIT_WEIGHT = {"NOVEL": 1.0, "KNOWN_STYLE": 0.0, UNMEASURED: 0.5}
#: Most cells screened per call: each runs one family over the full H1 history.
MAX_SCREEN = 60


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def saturation(report: Path | None = None) -> dict[str, Any]:
    """The styles the desk's certificates already own, read from STYLE_NOVELTY.json."""
    doc = _read_json(report or REPORT, {}) or {}
    counts = doc.get("dominant_style_counts") if isinstance(doc, dict) else None
    n = doc.get("n_measured") if isinstance(doc, dict) else None
    thr = doc.get("novel_threshold") if isinstance(doc, dict) else None
    if not isinstance(counts, dict) or not isinstance(n, int) or n <= 0:
        return {"status": UNMEASURED, "saturated": [], "counts": {},
                "novel_threshold": NOVEL_T,
                "why": "no measured STYLE_NOVELTY.json on this host: nothing is held"}
    sat = sorted((str(s) for s, c in counts.items()
                  if isinstance(c, int) and c / n >= SATURATION_SHARE),
                 key=lambda s: -int(counts[s]))
    return {"status": "MEASURED", "saturated": sat, "counts": dict(counts), "n_measured": n,
            "novel_threshold": float(thr) if isinstance(thr, (int, float)) else NOVEL_T,
            "generated_utc": doc.get("generated_utc")}


def _family(name: str) -> Callable[..., Any] | None:
    try:
        from mt5desk import families, families_orthogonal
    except Exception:
        return None
    fn = (getattr(families_orthogonal, "ORTHOGONAL_FAMILIES", {}) or {}).get(name)
    return fn or getattr(families, f"family_{name}", None)


def _bars(sym: str, bars_dir: Path) -> Any:
    f = bars_dir / f"{sym}_H1.parquet"
    if not f.exists():
        return None
    try:
        import pandas as pd
        return pd.read_parquet(f)
    except Exception:
        return None


def measure(row: Mapping[str, Any], *, bars_dir: Path | None = None,
            sn: Any = None) -> dict[str, Any]:
    """One cell's style reading on its own bars. Never raises; every gap is UNMEASURED."""
    sym = str(row.get("symbol") or (row.get("symbols") or [""])[0] or "")
    fam = str(row.get("family") or "")
    if sn is None:
        try:
            import style_novelty as sn
        except Exception:
            return {"status": UNMEASURED, "why": "style_novelty is not on this tree (#377)"}
    fn = _family(fam)
    if fn is None:
        return {"status": UNMEASURED, "why": f"family {fam!r} is not executable here"}
    df = _bars(sym, bars_dir or BARS_DIR)
    if df is None or len(df) == 0 or "close" not in getattr(df, "columns", ()):
        return {"status": UNMEASURED, "why": f"no H1 bars for {sym!r} on this host"}
    try:
        sigs = fn(df, **dict(row.get("params") or {}))
        hl = ((df["high"].to_numpy(dtype=float), df["low"].to_numpy(dtype=float))
              if {"high", "low"} <= set(df.columns) else (None, None))
        y, X = sn.style_matrix(df["close"].to_numpy(dtype=float), df.index, sigs or [],
                               high=hl[0], low=hl[1])
        proj = sn.project(y, X)
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
    if proj.get("status") != "MEASURED":
        return {"status": UNMEASURED, "why": str(proj.get("why") or "projection unmeasured")}
    return {"status": "MEASURED", "n": proj.get("n"),
            "novelty_return": proj.get("novelty_return"),
            "dominant_style": proj.get("dominant_style"),
            "residual_t": proj.get("residual_t")}


def verdict(reading: Mapping[str, Any], sat: Mapping[str, Any]) -> str:
    """NOVEL, KNOWN_STYLE (a measured cell explained by the style library) or UNMEASURED."""
    if reading.get("status") != "MEASURED":
        return UNMEASURED
    nov = reading.get("novelty_return")
    if not isinstance(nov, (int, float)) or not math.isfinite(float(nov)):
        return UNMEASURED
    return "NOVEL" if float(nov) >= float(sat.get("novel_threshold") or NOVEL_T) else "KNOWN_STYLE"


def held(reading: Mapping[str, Any], sat: Mapping[str, Any]) -> bool:
    """Only a KNOWN_STYLE cell whose dominant style the book already owns is held."""
    return (verdict(reading, sat) == "KNOWN_STYLE"
            and str(reading.get("dominant_style") or "") in set(sat.get("saturated") or []))


def screen(rows: Iterable[dict[str, Any]], *, deadline: float | None = None,
           bars_dir: Path | None = None, report: Path | None = None,
           held_path: Path | None = None, sn: Any = None,
           clock: Callable[[], float] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(rows to donate, summary). Every row is stamped `style_screen`; held rows are stored."""
    import time
    tick = clock or time.time
    sat = saturation(report)
    out: list[dict[str, Any]] = []
    store = _read_json(held_path or HELD, {}) or {}
    tally = {"screened": 0, "NOVEL": 0, "KNOWN_STYLE": 0, UNMEASURED: 0, "held": 0,
             "not_reached": 0}
    for i, r in enumerate(rows):
        if i >= MAX_SCREEN or (deadline is not None and tick() > deadline):
            reading: dict[str, Any] = {"status": UNMEASURED,
                                       "why": "screen budget spent before this row"}
            tally["not_reached"] += 1
        else:
            reading = measure(r, bars_dir=bars_dir, sn=sn)
            tally["screened"] += 1
        v = verdict(reading, sat)
        tally[v] += 1
        r = {**r, "style_screen": {**reading, "verdict": v, "at": _now(),
                                   "saturated_styles": list(sat.get("saturated") or [])}}
        if held(reading, sat):
            tally["held"] += 1
            store[str(r.get("cell_id") or len(store))] = r
            continue
        out.append(r)
    if tally["held"]:
        _write_json(held_path or HELD, store)
    return out, {**tally, "saturation": {k: sat.get(k) for k in ("status", "saturated",
                                                                   "n_measured", "why")},
                 "held_total": len(store)}


def release(*, report: Path | None = None, held_path: Path | None = None
            ) -> tuple[list[dict[str, Any]], int]:
    """(rows whose style is no longer saturated, rows still held). No re-measurement: the stored
    reading is judged against the CURRENT saturation, so a style the book stops owning frees its
    cells on the next pass. An unreadable report frees every row: holding is the exception."""
    path = held_path or HELD
    store = _read_json(path, {}) or {}
    if not store:
        return [], 0
    sat = saturation(report)
    freed = {k: v for k, v in store.items()
             if not held(v.get("style_screen") or {}, sat)}
    if freed:
        _write_json(path, {k: v for k, v in store.items() if k not in freed})
    return [{**v, "style_screen": {**(v.get("style_screen") or {}),
                                   "released": _now()}} for v in freed.values()], \
        len(store) - len(freed)


def credit_weight(row: Mapping[str, Any]) -> tuple[float, str]:
    """A certified cell's share of credit for being a NEW style, and the verdict it came from."""
    v = str((row.get("style_screen") or {}).get("verdict") or UNMEASURED)
    return CREDIT_WEIGHT.get(v, CREDIT_WEIGHT[UNMEASURED]), v


def prompt_line(report: Path | None = None) -> str:
    """One line for the inventors: the styles the book owns, so they propose around them."""
    sat = saturation(report)
    if sat.get("status") != "MEASURED":
        return "styles the book owns: UNMEASURED on this host"
    counts = sat.get("counts") or {}
    owned = ", ".join(f"{s} ({counts.get(s)})" for s in sat.get("saturated") or [])
    return ("styles the book already owns (certificates dominated by each): "
            + (owned or "none above the saturation share")
            + ". A cell whose direction choice reduces to one of these is held, not judged; "
              "propose information the price path cannot reproduce.")
