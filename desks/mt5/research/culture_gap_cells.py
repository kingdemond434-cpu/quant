"""CULTURE-GAP CELLS -- every zero-coverage culture gap gets a producer, on the gap's own clock.

    python desks/mt5/research/culture_gap_cells.py --once --budget-s 240
    python desks/mt5/research/culture_gap_cells.py --once --dry-run

WHY THIS EXISTS (principal 2026-09-30). `cell_culture_index` measured the culture of every cell
and published the GAPS -- (MT5 asset class x jurisdiction x participant structure) with zero or
thin cells whose culture came from a SOURCE. Twenty-odd came back ZERO: Brazilian, Russian, South
African, Mexican and Turkish retail FX; the PBoC and RBI fixings; the Tokyo settlement fix; the
Japanese tax calendar; mainland T+1 on the Hong Kong indices; Korea; Dubai, Mumbai and Istanbul
physical gold; and a dozen home instruments (EUR, CHF, CZK, HUF, PLN, ILS, SGD, THB, IDR, HKD,
GER40, EUSTX50, AUS200, CA60, gilts, Treasuries) that no culture-sourced cell had ever touched.
`deep_forest_miner` already works gap regions first, but it mines PROSE, and a claim becomes a
cell only when the compiler can read an exact rule out of it -- which a fixing time on a central
bank's page never states as a rule. So the gaps stayed at zero while their grounds were crawled.

WHAT THIS ORGAN DOES. Each gap's PARTICIPANT STRUCTURE already names a clock: a policy-driven
market has a fixing, a settlement-constrained one a settlement or session window, a tax-driven one
a tax month, a physical-flow one a local session and a local premium, a retail-heavy one the
hours its households trade. `desks/mt5/data/culture_gap_recipes.json` writes each of those down
ONCE, as data -- the family, the instruments, the window in the MARKET'S OWN local clock, the
family's own parameter grid, and the roster row whose publisher states the fact
(`desks/mt5/data/source_rosters/culture_gap_sources.json`, also added to
`deep_forest_sources.json` so the forest crawls them). This organ:

  1. CONVERTS EVERY WINDOW TO BROKER STAMP-HOURS through `libs/regime/session_clock.py` (the
     venue clock is New York + 7 h; the bars carry it under a UTC label). A window is converted
     for every weekday of the year, and each DISTINCT broker hour the year needs becomes its own
     cell, with the share of the year it is exact on written into its rationale -- a 09:15
     Shanghai fix is stamp 04 while New York is on daylight time and stamp 03 otherwise, and a
     fixed-hour family can only be right for one of those at a time. A variant exact on less
     than `MIN_VARIANT_SHARE` of the year (the one or two weeks when two DST calendars disagree)
     is published, not minted: it would be a trial charged for a hypothesis nobody proposed.
     Every conversion is checked by round trip through `session_clock.server_to_utc`.

  2. MINTS CELLS THROUGH THE ONE DOOR, `libs.moat.registry` -- `record_discovery` once per recipe
     and `enqueue_candidate` per (instrument x broker variant x grid point x chart) -- so every
     trial is charged where every other producer's is, the moat exchange prices and leases it,
     and the sealed gauntlet judges it. Nothing is judged, sized or vetoed here.

  3. STAMPS CULTURE AT BIRTH through `cell_culture.stamp`: the jurisdiction/language of the
     publisher and the participant structure are DECLARED by the recipe (the recipe exists
     because that publisher states that fact); the failure-mode sentence and the crowding prior
     are left to the one inference rule, so `crowding_prior` follows the same rules as every other
     cell. MT5/Fusion instruments only (a symbol absent from the universe is refused and named),
     never the `discovered` family, never a crypto-exchange universe.

  4. ORDERS BY THE GAP LIST. Recipes whose gap is ZERO in the last published CELL_CULTURE.json go
     first, then THIN, then covered ones; an absent summary is UNMEASURED and reorders nothing.
     A cell already minted is never re-enqueued (the registry would count a second search of
     the same rule), so the per-recipe cursor walks each recipe's cell list once and a recipe
     whose list changes (new variants when DST rules move, a new grid point, a pack series that
     lands on the box) is walked again from where it differs.

  5. REFUSES WITHOUT EVIDENCE. A local-premium conditioner needs the pack's stamped series in the
     lake (`exogenous_conditioner` refuses without it); where the series is absent the recipe is
     UNMEASURED with the path it looked for, never a zero and never a guessed column.

Artifact: `desks/mt5/reports/CULTURE_GAP_CELLS.json` -- cells per gap and per recipe, the broker
variants with their year shares, the dropped variants, and every refusal with its reason.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

from libs.regime import session_clock as SC  # noqa: E402
from libs.research import cell_culture as CC  # noqa: E402

LEG = "culture_gap_cells"
RECIPES = DESK / "data" / "culture_gap_recipes.json"
ROSTER = DESK / "data" / "source_rosters" / "culture_gap_sources.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
SUMMARY = DESK / "reports" / "CELL_CULTURE.json"
CURSOR = DESK / "reports" / "culture_gap_cells_cursor.json"
OUT = DESK / "reports" / "CULTURE_GAP_CELLS.json"
SERIES_DIR = DESK / "data" / "lake" / "series"

#: A broker-hour variant exact on less of the year than this is published, not minted: the one
#: or two weeks when the local and New York DST calendars disagree are not a season.
MIN_VARIANT_SHARE = 0.10
#: Seconds kept back from the budget for the report.
WRITE_RESERVE_S = 10.0
#: Never minted, whatever a recipe says (data/banned_families.json holds the same ban).
BANNED_FAMILIES = frozenset({"discovered"})
ORIGIN = "culture_gap_cells"


# ----------------------------------------------------------------------------------- helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def recipes(path: Path = RECIPES) -> list[dict[str, Any]]:
    doc = _read(path, {})
    rows = doc.get("recipes") if isinstance(doc, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("id") and r.get("family")]


def roster(path: Path = ROSTER) -> dict[str, dict[str, Any]]:
    doc = _read(path, {})
    rows = doc.get("sources") if isinstance(doc, dict) else None
    return {str(r["id"]): r for r in (rows or []) if isinstance(r, dict) and r.get("id")}


def universe(path: Path = UNIVERSE) -> set[str]:
    doc = _read(path, {})
    return {str(k).upper() for k in doc} if isinstance(doc, dict) else set()


# ------------------------------------------------------------------------- the clock, converted
def _utc_to_broker(utc: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """True UTC instants -> the venue's stamp clock, the exact inverse of
    `session_clock.server_to_utc` (New York wall time + SERVER_SHIFT_H)."""
    shift = pd.Timedelta(hours=int(getattr(SC, "SERVER_SHIFT_H", 0)))
    return utc.tz_convert(SC.SERVER_TZ).tz_localize(None) + shift


def weekdays(year: int) -> list[date]:
    d, out = date(year, 1, 1), []
    while d.year == year:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def window_hours(window: dict[str, Any], days: list[date]) -> list[int | tuple[int, ...] | None]:
    """Per day, the broker stamp-hour value a window's parameter needs (None: failed round trip).

    `align: contains` is the H1 bar the instant falls in (a fix at 09:15 is in the 09:00 bar);
    `align: start` is the first H1 bar that starts at or after it (the first FULL hour after an
    open). `span: n` returns that bar and the n-1 after it, as a tuple (`hours=` parameters).
    """
    tz = str(window["tz"])
    hh, mm = (int(x) for x in str(window["at"]).split(":", 1))
    # wall-clock times of the market's own zone, localised on the next line (naive on purpose)
    local = pd.DatetimeIndex([pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=hh,
                                           minute=mm) for d in days])
    utc = local.tz_localize(tz, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    broker = _utc_to_broker(utc)
    ok = ~broker.isna()
    back = SC.server_to_utc(broker[ok])
    good = pd.Series(False, index=range(len(days)))
    good[ok.nonzero()[0]] = (back == utc[ok]).tolist() if len(back) else []
    align = str(window.get("align") or "contains")
    span = int(window.get("span") or 1)
    out: list[int | tuple[int, ...] | None] = []
    for i, b in enumerate(broker):
        if not bool(good.iloc[i]):
            out.append(None)
            continue
        h = int(b.hour)
        if align == "start" and (b.minute or b.second):
            h = (h + 1) % 24
        out.append(h if span <= 1 else tuple((h + k) % 24 for k in range(span)))
    return out


def variants(rec: dict[str, Any], year: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(kept, dropped) broker-parameter variants for a recipe's windows over `year`.

    Each variant is {"params": {...}, "share": fraction of the year's weekdays it is exact on}.
    A recipe with no windows has ONE variant with no clock parameters and share 1.0.
    """
    wins = [w for w in (rec.get("windows") or []) if isinstance(w, dict)]
    if not wins:
        return [{"params": {}, "share": 1.0}], []
    days = weekdays(year)
    cols = [window_hours(w, days) for w in wins]
    tally: Counter[tuple[Any, ...]] = Counter()
    for vals in zip(*cols, strict=True):
        if any(v is None for v in vals):
            continue
        tally[tuple(vals)] += 1
    n = sum(tally.values()) or 1
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for vals, k in tally.most_common():
        params = {w["param"]: (list(v) if isinstance(v, tuple) else v)
                  for w, v in zip(wins, vals, strict=True)}
        row = {"params": params, "share": round(k / n, 4)}
        why = _causal_order(rec, params)
        if why:
            dropped.append({**row, "why": why})
        elif k / n < MIN_VARIANT_SHARE:
            dropped.append({**row, "why": f"exact on {k} of {n} weekdays, under "
                                          f"{MIN_VARIANT_SHARE:.0%}: two DST calendars "
                                          "disagreeing, not a season"})
        else:
            kept.append(row)
    return kept, dropped


def _causal_order(rec: dict[str, Any], params: dict[str, Any]) -> str:
    """A variant whose later window falls BEFORE its earlier one inside the broker day would read
    a same-day future bar (session_handoff groups by broker day): refused, with the reason."""
    fam = str(rec.get("family"))
    if fam == "session_handoff":
        src = int(params.get("source_start_hour", 0)) + int(
            (rec.get("fixed") or {}).get("source_bars", 1)) - 1
        if int(params.get("trade_hour", 0)) <= src:
            return (f"trade_hour {params.get('trade_hour')} is not after the source bar {src} "
                    "inside one broker day; the family would read a later bar of the same day")
    if fam == "hedging_demand_close" and int(params.get("rod_start_hour", 0)) >= int(
            params.get("close_hour", 0)):
        return "rod_start_hour is not before close_hour inside one broker day"
    return ""


# --------------------------------------------------------------------------------- the cells
def _grid(rec: dict[str, Any]) -> list[dict[str, Any]]:
    grid = rec.get("grid") or {}
    keys = sorted(grid)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(list(grid[k]) for k in keys))] or [{}]


def pack_signals(pack: str) -> tuple[list[str], str]:
    """The numeric columns of a pack's stamped series, the same reading `pack_cells` makes.
    Empty with the reason when the series is not in this tree's lake: UNMEASURED, never a
    guessed column."""
    path = next((SERIES_DIR / f"{pack}{s}" for s in (".parquet", ".csv")
                 if (SERIES_DIR / f"{pack}{s}").exists()), None)
    if path is None:
        return [], (f"UNMEASURED: no stamped series for pack {pack!r} under "
                    f"{SERIES_DIR} on this host")
    try:
        from research.pack_cells import signals_of
        sigs, _n, why = signals_of(path)
    except Exception as exc:  # the reader is pack_cells'; its failure is named, not hidden
        return [], f"UNMEASURED: pack_cells.signals_of failed: {type(exc).__name__}: {exc}"
    return list(sigs), ("" if sigs else f"UNMEASURED: {why}")


def cells_for(rec: dict[str, Any], year: int, universe_syms: set[str]
              ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every cell a recipe asks for, in a stable order, and the recipe's measurement notes."""
    note: dict[str, Any] = {"refused": []}
    fam = str(rec["family"])
    if fam in BANNED_FAMILIES:
        note["refused"].append(f"family {fam!r} is banned")
        return [], note
    syms = []
    for s in rec.get("symbols") or []:
        su = str(s).upper()
        if su in universe_syms:
            syms.append(str(s))
        else:
            note["refused"].append(f"{s}: not in the MT5 universe registry")
    kept, dropped = variants(rec, year)
    note["variants"], note["dropped_variants"] = kept, dropped
    extra: list[dict[str, Any]] = [{}]
    if fam == "exogenous_conditioner":
        sigs, why = pack_signals(str(rec.get("pack") or ""))
        if not sigs:
            note["unmeasured"] = why
            return [], note
        extra = [{"source": rec["pack"], "signal": s} for s in sigs]
    out: list[dict[str, Any]] = []
    fixed = dict(rec.get("fixed") or {})
    for v in kept:
        for sym in syms:
            for ex in extra:
                for gp in _grid(rec):
                    for chart in rec.get("charts") or ["H1"]:
                        params = {**fixed, **v["params"], **ex, **gp}
                        out.append({"symbol": sym, "params": params, "chart": chart,
                                    "share": v["share"]})
    return out, note


def cell_key(rec_id: str, c: dict[str, Any]) -> str:
    blob = json.dumps([rec_id, c["symbol"], c["params"], c["chart"]], sort_keys=True,
                      default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------------------ the gap list
def gap_states(path: Path = SUMMARY) -> dict[tuple[str, str, str], str] | None:
    """(asset class, jurisdiction, structure|any) -> ZERO | THIN from the last published culture
    summary; None when no summary exists (UNMEASURED)."""
    doc = _read(path, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("gaps"), list):
        return None
    out: dict[tuple[str, str, str], str] = {}
    for g in doc["gaps"]:
        if not isinstance(g, dict):
            continue
        j = CC.jurisdiction_of(g.get("culture")) or str(g.get("culture") or "")
        out[(str(g.get("asset_class")), j, str(g.get("participant_structure") or "any"))] = str(
            g.get("state") or "")
    return out


def recipe_gap_state(rec: dict[str, Any], states: dict[tuple[str, str, str], str] | None) -> str:
    if states is None:
        return CC.UNMEASURED
    g = rec.get("gap") or {}
    key = (str(g.get("asset_class")), str(g.get("jurisdiction")),
           str(g.get("participant_structure") or "any"))
    return states.get(key, "COVERED")


_ORDER = {"ZERO": 0, "THIN": 1, CC.UNMEASURED: 2, "COVERED": 3}


# ---------------------------------------------------------------------------------- the door
def _culture(rec: dict[str, Any], cell: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    """The four fields through the ONE rule: culture and structure DECLARED (the recipe exists
    because its publisher states the fact), failure mode and crowding inferred."""
    row = {"family": rec["family"], "symbol": cell["symbol"], "params": cell["params"],
           "source_url": src.get("url"), "mechanism": rec.get("mechanism"),
           "source": f"{ORIGIN}:{rec['id']}"}
    return CC.stamp(row, source_culture=rec.get("source_culture"),
                    participant_structure=rec.get("participant_structure"))


def _rationale(rec: dict[str, Any], cell: dict[str, Any], src: dict[str, Any]) -> str:
    clock = ""
    wins = rec.get("windows") or []
    if wins:
        clock = (" Clock: " + "; ".join(f"{w['param']} = {w['at']} {w['tz']} ({w.get('align')})"
                                        for w in wins)
                 + f" -> broker stamp {cell['params'].get(wins[0]['param'])}, exact on "
                 f"{cell['share']:.0%} of the year's weekdays (libs/regime/session_clock).")
    fact = src.get("fact")
    return (f"{rec.get('mechanism')}.{clock}"
            + (f" Fact ({rec.get('source_id')}): {fact}." if fact else "")
            + (f" {rec['note']}." if rec.get("note") else ""))


def emit(rec: dict[str, Any], cells: list[dict[str, Any]], start: int, deadline: float,
         src: dict[str, Any], *, dry_run: bool, done: set[str]) -> dict[str, Any]:
    made = created = 0
    errors: list[str] = []
    did = ""
    mech = str(rec.get("mechanism") or "")
    region = str((rec.get("gap") or {}).get("jurisdiction") or "").lower()
    if not dry_run and cells[start:]:
        try:
            from libs.moat.registry import record_discovery
            did, _new = record_discovery(
                source_id=str(rec.get("source_id") or rec["id"]), source_type="culture_gap_recipe",
                mechanism=mech, origin=ORIGIN, generator=ORIGIN,
                assets=sorted({c["symbol"] for c in cells}),
                exact_rule_if_known=f"{rec['family']} on the recipe's broker-converted clock",
                horizons=list(rec.get("charts") or ["H1"]), source_url=src.get("url"),
                note=f"culture-gap recipe {rec['id']}",
                source_culture=rec.get("source_culture"),
                participant_structure=rec.get("participant_structure"))
        except Exception as exc:
            return {"emitted": 0, "created": 0, "next": start,
                    "errors": [f"record_discovery: {type(exc).__name__}: {str(exc)[:80]}"]}
    i = start
    while i < len(cells):
        if time.monotonic() > deadline:
            break
        c = cells[i]
        key = cell_key(rec["id"], c)
        i += 1
        if key in done:
            continue
        made += 1
        if dry_run:
            continue
        src_row = src
        fields = _culture(rec, c, src_row)
        try:
            from libs.moat.registry import enqueue_candidate
            _cid, was_new = enqueue_candidate(
                family=str(rec["family"]), symbol=c["symbol"], params=c["params"],
                origin=ORIGIN, mechanism=mech, chart=c["chart"], horizon=c["chart"],
                source_id=str(rec.get("source_id") or rec["id"]), discovery_id=did or None,
                generator=ORIGIN, department="information", region=region,
                transformation="culture_gap_recipe",
                pit_status=("STAMPED" if rec["family"] == "exogenous_conditioner"
                            else "PRICE_ONLY"),
                causal_rationale=_rationale(rec, c, src_row),
                falsifier=(f"{rec['family']} on {c['symbol']} {c['chart']} with "
                           f"{json.dumps(c['params'], sort_keys=True)} shows no out-of-sample "
                           f"edge after costs, or its losses coincide with the Western version's"),
                url=src_row.get("url"), **fields)
            created += int(bool(was_new))
            done.add(key)
        except Exception as exc:
            errors.append(f"{c['symbol']}/{c['chart']}: {type(exc).__name__}: {str(exc)[:60]}")
            if len(errors) >= 5:
                break
    return {"emitted": made, "created": created, "next": i, "discovery_id": did,
            "errors": errors}


# ------------------------------------------------------------------------------------ the run
def run(budget_s: float = 240.0, *, dry_run: bool = False, year: int | None = None,
        recipes_path: Path = RECIPES, summary: Path = SUMMARY,
        cursor_path: Path = CURSOR) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(2.0, budget_s - WRITE_RESERVE_S)
    yr = int(year or datetime.now(tz=UTC).year)
    recs = recipes(recipes_path)
    src_rows = roster()
    uni = universe()
    states = gap_states(summary)
    cursor = _read(cursor_path, {}) if not dry_run else {}
    if not isinstance(cursor, dict):
        cursor = {}
    per: list[dict[str, Any]] = []
    order = sorted(recs, key=lambda r: (_ORDER.get(recipe_gap_state(r, states), 9), r["id"]))
    for rec in order:
        cells, note = cells_for(rec, yr, uni)
        fp = hashlib.sha1(json.dumps([cell_key(rec["id"], c) for c in cells]).encode()
                          ).hexdigest()[:16]
        prev = cursor.get(rec["id"])
        st: dict[str, Any] = prev if isinstance(prev, dict) else {}
        done = set(st.get("done") or [])
        start = int(st.get("next") or 0) if st.get("fingerprint") == fp else 0
        src = src_rows.get(str(rec.get("source_id")), {})
        res = emit(rec, cells, start, deadline, src, dry_run=dry_run, done=done)
        if not dry_run:
            cursor[rec["id"]] = {"fingerprint": fp, "next": res["next"], "done": sorted(done),
                                 "updated_at": _now()}
        g = rec.get("gap") or {}
        per.append({
            "id": rec["id"], "family": rec["family"],
            "gap": f"{g.get('asset_class')}|{g.get('jurisdiction')}|"
                   f"{g.get('participant_structure') or 'any'}",
            "gap_state": recipe_gap_state(rec, states),
            "source_culture": rec.get("source_culture"),
            "participant_structure": rec.get("participant_structure"),
            "source_id": rec.get("source_id"), "source_verified": src.get("verified",
                                                                           CC.UNMEASURED),
            "cells_total": len(cells), "cells_minted_total": len(done),
            "emitted_this_pass": res["emitted"], "created_this_pass": res["created"],
            "complete": res["next"] >= len(cells) and len(cells) > 0,
            "variants": note.get("variants"), "dropped_variants": note.get("dropped_variants"),
            "refused": note.get("refused"), "unmeasured": note.get("unmeasured"),
            "errors": res.get("errors")})
    if not dry_run:
        _write(cursor_path, cursor)
    gaps: dict[str, dict[str, Any]] = {}
    for r in per:
        agg = gaps.setdefault(r["gap"], {"gap_state": r["gap_state"], "recipes": [],
                                         "cells_total": 0, "cells_minted_total": 0,
                                         "emitted_this_pass": 0, "unmeasured": []})
        agg["recipes"].append(r["id"])
        agg["cells_total"] += r["cells_total"]
        agg["cells_minted_total"] += r["cells_minted_total"]
        agg["emitted_this_pass"] += r["emitted_this_pass"]
        if r["unmeasured"]:
            agg["unmeasured"].append(f"{r['id']}: {r['unmeasured']}")
    return {
        "generated_at": _now(), "leg": LEG, "dry_run": dry_run, "year": yr,
        "clock": {"module": "libs/regime/session_clock.py", "server_tz": SC.SERVER_TZ,
                  "server_shift_h": getattr(SC, "SERVER_SHIFT_H", 0),
                  "min_variant_share": MIN_VARIANT_SHARE},
        "gap_list": ("read" if states is not None
                     else f"{CC.UNMEASURED}: {summary} absent, recipes run in id order"),
        "totals": {"recipes": len(per), "cells_total": sum(r["cells_total"] for r in per),
                   "emitted_this_pass": sum(r["emitted_this_pass"] for r in per),
                   "created_this_pass": sum(r["created_this_pass"] for r in per),
                   "unmeasured_recipes": [r["id"] for r in per if r["unmeasured"]]},
        "gaps": gaps, "recipes": per,
        "consumers": {"libs/moat/registry.py research_candidates":
                      "moat_candidate_compiler prices and leases them to the sealed gauntlet",
                      "desks/mt5/research/cell_culture_index.py":
                      "counts them per gap on its next pass (source-derived culture)"},
        "wall_s": round(time.monotonic() - t0, 2)}


def render(doc: dict[str, Any]) -> str:
    t = doc["totals"]
    return (f"culture_gap_cells: {t['recipes']} recipes, {t['cells_total']} cells defined, "
            f"{t['emitted_this_pass']} emitted this pass ({t['created_this_pass']} new), "
            f"{len(t['unmeasured_recipes'])} UNMEASURED recipe(s); {doc['wall_s']}s")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true", help="count cells, write nothing")
    ap.add_argument("--registry", type=Path, default=None, help="registry path (measurement)")
    ap.add_argument("--year", type=int, default=None)
    a = ap.parse_args(argv)
    if a.registry is not None:
        from libs.moat import registry as R
        R.set_path(a.registry)
    doc = run(a.budget_s, dry_run=a.dry_run, year=a.year)
    if not a.dry_run:
        _write(OUT, doc)
    print(render(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
