"""Mint `cb_tone_event` cells from the central-bank tone corpus -- the corpus's judged consumer.

The tone corpus this reads is the banks' OWN speech pages, from sources whose terms allow
trading use (`mt5desk.family_cb_tone.PERMITTED_SOURCES`); the BIS extract is noncommercial and
is not read here or by the family. For each hypothesis-lane symbol (a rotating cursor, so the
whole universe is reached over hours) and each tone currency the symbol is priced in -- both legs
of an FX pair, the profit currency of a metal, index, energy, soft or crypto CFD, so gold reads
the Fed -- it runs `family_cb_tone_event` over a small declared grid (basis x tone side x
direction x hold), screens every variant net of the round trip with the shared proposer screen,
deflates by everything it tried, and donates one best variant per (symbol, currency) through
`proposer_common.donate`. The sealed gauntlet judges it via `ORTHOGONAL_FAMILIES`; the family
reloads the corpus from `currency` on the recipe, keyed on each speech's PUBLICATION day.

WITH NO PERMITTED CORPUS IT PARKS, BY NAME AND BY COUNT: status UNMEASURED, `parked_reason`
`bis_terms_noncommercial`, and `symbols_parked` -- the hypothesis-lane symbols that would have
been swept. Nothing is screened and nothing is donated.

The screen is not the gauntlet: it only keeps the gauntlet from being handed every variant.

    python desks/mt5/research/cb_tone_proposer.py --once --budget-s 600
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_cb_tone as F  # noqa: E402

from research import proposer_common as pc  # noqa: E402

SOURCE = "cb_tone_event"
FAMILY = "cb_tone_event"
REPORT = DESK / "reports" / "CB_TONE_PROPOSER.json"
UNMEASURED = "UNMEASURED"
DEFAULT_BUDGET_S = 600.0

#: The declared grid. One threshold per basis: a level day at least half one-sided, a surprise of
#: a quarter of the scale against the bank's own previous language.
BASES: tuple[tuple[str, float], ...] = (("level", 0.5), ("surprise", 0.25))
DIRECTIONS: tuple[str, ...] = ("long", "short")
HOLDS: tuple[int, ...] = (24, 72)


def currencies_for(symbol: str, row: dict[str, Any], held: set[str]) -> list[str]:
    """The tone currencies `symbol` is priced in: both FX legs, else the profit currency."""
    out: list[str] = []
    if str(row.get("asset_class") or "").lower() == "forex" and len(symbol) >= 6:
        out.append(symbol[:3].upper())
    out.append(str(row.get("currency_profit") or "").upper())
    return [c for i, c in enumerate(out) if c in held and c not in out[:i]]


def _symbols(meta: dict[str, Any]) -> list[str]:
    from research import universe_policy as up
    return [s for s in sorted(meta) if isinstance(meta[s], dict) and up.may_hypothesise(s)]


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def corpus_state() -> dict[str, Any]:
    """Which currencies the tone corpus holds on this host and how fresh each is."""
    held: dict[str, Any] = {}
    for ccy in ("USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "NZD"):
        s = F.tone_days(ccy)
        if s is not None and len(s):
            held[ccy] = {"published_days": len(s), "last_published": str(s.index.max().date())}
    return {"currencies": held, "dropped": dict(F.LAST_DROPPED),
            "permitted_sources": sorted(F.PERMITTED_SOURCES)}


def run(*, budget_s: float = DEFAULT_BUDGET_S, now: datetime | None = None,
        donate: bool = True) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    corpus = corpus_state()
    held = set(corpus["currencies"])
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "organ": "desks/mt5/research/cb_tone_proposer.py",
                           "family": FAMILY, "consumes": str(F.SPEECHES.name), "corpus": corpus}
    last = max((v["last_published"] for v in corpus["currencies"].values()), default=None)
    if last is not None:
        age = (now.date() - datetime.fromisoformat(last).date()).days
        rep["corpus_last_published"] = last
        rep["corpus_age_days"] = age
    meta = pc.universe_meta()
    syms = [s for s in _symbols(meta) if currencies_for(s, meta[s], held)]
    if not held or not syms:
        rep.update({"status": UNMEASURED, "tests_run": UNMEASURED, "cells_proposed": UNMEASURED,
                    "why": ("no permitted central-bank tone corpus on this host: "
                            f"{F.SPEECHES.name} is absent or holds no row from a source whose "
                            "terms allow trading use (the BIS extract is noncommercial and is "
                            "not read)" if not held else
                            "no hypothesis-lane symbol is priced in a tone currency")})
        if not held:
            rep["parked_reason"] = F.NO_PERMITTED_CORPUS
            rep["symbols_parked"] = len(_symbols(meta))
        _write(REPORT, rep)
        return rep
    start = int(_read(REPORT).get("cursor_next", 0)) % len(syms)
    order = syms[start:] + syms[:start]
    rows: list[dict[str, Any]] = []
    swept: list[str] = []
    skipped: dict[str, str] = {}
    for sym in order:
        if time.monotonic() - t0 > budget_s:
            break
        d = pc.bars(sym)
        if d is None or len(d) < 2000:
            skipped[sym] = "no or too few H1 bars"
            swept.append(sym)
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms"
            swept.append(sym)
            continue
        unf = pc.artifact_hours(d)
        for ccy in currencies_for(sym, meta[sym], held):
            for basis, min_abs in BASES:
                for tone in F.TONES:
                    for direction in DIRECTIONS:
                        for hold in HOLDS:
                            params = {"currency": ccy, "basis": basis, "tone": tone,
                                      "min_abs": min_abs, "direction": direction,
                                      "hold_bars": hold}
                            try:
                                sig = F.family_cb_tone_event(d, **params)
                            except F.CbToneUnavailable:
                                continue
                            sc = pc.screen(d, sig, cost, unf)
                            if sc is None:
                                continue
                            rows.append({"cell": f"{sym}.{FAMILY}.{ccy}", "symbol": sym,
                                         "params": params, **sc})
        swept.append(sym)
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"published {r['params']['currency']} central-bank speeches read "
                   f"{r['params']['tone']}ish on the {r['params']['basis']} basis "
                   f"(|reading| >= {r['params']['min_abs']}): holders of that currency's rate "
                   f"expectations reprice {r['symbol']} {r['params']['direction']} over the "
                   f"{r['params']['hold_bars']} bars after the speech is public"),
        title=f"{r['cell']} {r['params']['basis']} {r['params']['tone']} "
              f"{r['params']['direction']} h{r['params']['hold_bars']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep")}) for r in proposals]
    donated = None
    if donate and cands:
        donated = pc.donate(SOURCE, cands, len(rows))
    rep.update({"status": "OK", "symbols_available": len(syms), "symbols_swept": len(swept),
                "cursor_start": start, "cursor_next": (start + len(swept)) % len(syms),
                "tests_run": len(rows), "cells_proposed": len(proposals),
                "donated": len(cands) if donated else 0, "donation_path": str(donated or ""),
                "donation_refusals": dict(pc.LAST_DONATION) if donated is None and cands
                else None,
                "skipped": skipped, "elapsed_s": round(time.monotonic() - t0, 1),
                "proposals": proposals[:50]})
    _write(REPORT, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    a = ap.parse_args(argv)
    r = run(budget_s=a.budget_s)
    print(f"cb_tone_proposer: status={r['status']} swept={r.get('symbols_swept', 0)} "
          f"tests={r['tests_run']} proposed={r['cells_proposed']} "
          f"donated={r.get('donated', 0)} corpus_age_days={r.get('corpus_age_days')}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
