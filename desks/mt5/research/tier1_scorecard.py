"""ONE artifact saying where the desk stands on its fourteen Tier-1 dimensions, measured hourly.

WHY, measured 2026-09-16 and recorded as C25 in `docs/research/tier1_program.json`: *"no single
artifact carries the fourteen rows; the numbers are scattered across eight artifacts; six rows
have no source anywhere."* A programme whose scorecard must be reassembled by hand from eight
files is a programme whose progress is whatever the last reader remembered.

NOTHING HERE IS ASSERTED. Every row names the artifact and field it was read from, and a row whose
artifact is absent reads UNMEASURED **with the path it looked for** -- never zero, never a default.
That is law L1.28a (WS-005): absence never resolves to a clean verdict, and a zero would be the
worst lie available, because a zero is a MEASUREMENT -- it says the organ ran and found nothing.

A SCORECARD, NOT A SCORE: fourteen numbers on fourteen scales do not add up, and collapsing them
costs the reader the one thing worth knowing -- which dimension is starving. `overall` counts
AT/ABOVE vs BELOW vs UNMEASURED and NAMES the three weakest measured rows; it never averages them.

`first_target` is the next rung, not the ceiling, and `max_solo_direction` is where the principal's
blueprint says a solo desk can reach, so a row AT its first target still has somewhere to travel.
No target is ever lowered to make the board look better (ratchet law L1.50), and this file sizes
nothing and gates nothing -- a scorecard with authority is one people fight over instead of read.

    python desks/mt5/research/tier1_scorecard.py              # write reports/TIER1_SCORECARD.json
    python desks/mt5/research/tier1_scorecard.py --dry-run    # print the table, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORTS, DATA = DESK / "reports", DESK / "data"

# Module-level so a test can point every one at a tmp_path and exercise the code the box runs.
# A row reaching into a hard-coded path is a row no test can falsify.
EFFECTIVE_BREADTH = REPORTS / "EFFECTIVE_BREADTH.json"
BREADTH_MANDATE, ALPHA_GENOME = REPORTS / "BREADTH_MANDATE.json", REPORTS / "ALPHA_GENOME.json"
TIMEFRAME_COVERAGE = REPORTS / "TIMEFRAME_COVERAGE.json"
SESSION_CHART_EXPANSION = REPORTS / "SESSION_CHART_EXPANSION.json"
UNIVERSAL_SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
PIT_CENSUS, LAKE_PROMOTION = REPORTS / "PIT_CENSUS.json", REPORTS / "LAKE_PROMOTION.json"
LIVE_LEDGER, SLEEVES = DATA / "live_ledger.jsonl", DATA / "sleeves.json"
PROCESS_HEALTH, SYNC_MARKER = REPORTS / "process_health.json", DATA / "sync_marker.json"
SHADOW_STATE, COST_SURFACE = REPORTS / "shadow" / "shadow_state.json", DATA / "cost_surface.json"
WORLD_CAUSAL_GRAPH = REPORTS / "WORLD_CAUSAL_GRAPH.json"
CROSS_ASSET_GRAPH = REPORTS / "CROSS_ASSET_GRAPH.json"
STATE_VECTOR, MACRO_STATE = DATA / "state_vector.json", DATA / "macro_state.json"
ALLOCATOR_PROOF, PF_ALLOCATION = REPORTS / "ALLOCATOR_PROOF.json", REPORTS / "pf_allocation.json"
TAPE_RECORDER, MOAT_COVERAGE = REPORTS / "TAPE_RECORDER.json", DATA / "moat_coverage.json"
TAPE_TICKS, ROW_CONVERSION = DATA / "tape" / "ticks", REPORTS / "ROW_CONVERSION.json"
CANDIDATE_CONSERVATION = REPORTS / "CANDIDATE_CONSERVATION.json"
OUT = REPORTS / "TIER1_SCORECARD.json"

BELOW, AT, ABOVE, UNMEASURED = "BELOW", "AT", "ABOVE", "UNMEASURED"
_STAMPS = ("generated_utc", "generated_at", "at", "built_at", "swept_at", "updated_at", "updated",
           "measured_utc", "last_cycle")

#: dimension -> (unit, first_target, max_solo_direction, lower_is_better). The scale lives here
#: and not in fourteen call sites, so no row can drift from the board it is printed on. The moat
#: row's blueprint names a direction ("years") and no number; one year is this file's stated
#: reading of the first rung, declared here rather than hidden inside a verdict.
SPEC: dict[str, tuple[str, float, str, bool]] = {
    "effective_breadth_n_eff": ("bets", 15.0, "25-40", False),
    "certified_chart_session_axes": ("cells", 20.0, "majority measured", False),
    "mechanism_clusters_occupied": ("clusters", 10.0, "persistent expansion", False),
    "asset_classes_producing_survivors": ("classes", 5.0, "whole executable universe", False),
    "pit_compliance_pct": ("pct", 100.0, "100% and held", False),
    "live_trade_attribution_pct": ("pct", 99.0, "100", False),
    "silent_scheduled_failures": ("organs", 0.0, "0", True),
    "backtest_forward_lineage_pct": ("pct", 100.0, "100", False),
    "cost_model_maturity": ("ordinal 0-3", 2.0, "3", False),
    "cross_asset_intelligence": ("ordinal 0-3", 2.0, "3", False),
    "macro_intelligence": ("ordinal 0-3", 2.0, "3", False),
    "allocator_maturity": ("ordinal 0-3", 2.0, "3", False),
    "proprietary_moat_days": ("days", 365.0, "years", False),
    "research_conversion_backlog": ("candidates", 0.0, "near-zero useful backlog", True),
}


# ------------------------------------------------------------------------------------ plumbing
def _read(path: Path | str) -> Any:
    """Whatever the file holds, or None. Tolerant by design: this organ never crashes a cycle."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ValueError, TypeError):
        return None


def _read_jsonl(path: Path | str) -> list[dict[str, Any]] | None:
    try:
        text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except (OSError, TypeError):
        return None
    rows = []
    for line in (ln for ln in text.splitlines() if ln.strip()):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        rows.append(row) if isinstance(row, dict) else None
    return rows


def _rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except (OSError, ValueError):
        return Path(path).name


def _num(value: Any) -> float | None:
    return None if isinstance(value, bool) or not isinstance(value, (int, float)) else float(value)


def _stamp(doc: Any) -> str | None:
    for key in _STAMPS if isinstance(doc, dict) else ():
        if isinstance(doc.get(key), str) and doc[key]:
            return str(doc[key])
    return None


def _dict(doc: Any, key: str) -> dict[str, Any]:
    value = doc.get(key) if isinstance(doc, dict) else None
    return value if isinstance(value, dict) else {}


def _keys_anywhere(doc: Any, names: set[str], depth: int = 0) -> set[str]:
    """Which of `names` appear as a key anywhere in `doc`. Bounded -- a surface file is large."""
    found: set[str] = set()
    if depth > 5:
        return found
    for key, value in doc.items() if isinstance(doc, dict) else ():
        found |= ({str(key).lower()} & names) | _keys_anywhere(value, names, depth + 1)
    for value in doc[:200] if isinstance(doc, list) else ():
        found |= _keys_anywhere(value, names, depth + 1)
    return found


def _verdict(current: float | None, target: float | None, lower_is_better: bool) -> str:
    if current is None or target is None:
        return UNMEASURED
    if abs(current - target) <= 1e-9:
        return AT
    return (ABOVE if current < target else BELOW) if lower_is_better else (
        ABOVE if current > target else BELOW)


def _mk(dimension: str, current: float | None, basis: str,
        measured_at: str | None = None) -> dict[str, Any]:
    unit, target, direction, lower = SPEC[dimension]
    return {"dimension": dimension, "current": current, "unit": unit, "first_target": target,
            "max_solo_direction": direction, "basis": basis,
            "verdict": _verdict(current, target, lower), "measured_at": measured_at,
            "lower_is_better": lower}


def _gone(dimension: str, paths: list[Path | str]) -> dict[str, Any]:
    """The path it LOOKED FOR goes in the row. 'Missing' with no path is an accusation."""
    return _mk(dimension, None, f"ABSENT/UNREADABLE: {', '.join(_rel(p) for p in paths)}")


def _survivors(doc: Any) -> list[tuple[str, str]]:
    """(symbol, selector) for every survivor row that names a symbol."""
    out = []
    for row in _dict(doc, "survivors").values():
        spec = _dict(row, "shadow_spec")
        symbol = str(spec.get("symbol") or (row or {}).get("sym") or "").strip()
        if symbol:
            out.append((symbol, str(spec.get("selector") or "")))
    return out


def _sleeve_rows() -> list[dict[str, Any]]:
    doc = _read(SLEEVES)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


# ---------------------------------------------------------------------------- the fourteen rows
def _r01_effective_breadth() -> dict[str, Any]:
    doc = _read(EFFECTIVE_BREADTH)
    eff = _dict(doc, "effective")
    value, field = _num(eff.get("effective_breadth")), "effective.effective_breadth"
    if value is None:
        value, field = _num(eff.get("n_eff")), "effective.n_eff"
    if value is None:
        doc = _read(BREADTH_MANDATE)
        value = _num(_dict(doc, "ratchet").get("n_eff"))
        field = f"{_rel(BREADTH_MANDATE)} ratchet.n_eff"
    if value is None:
        return _gone("effective_breadth_n_eff", [EFFECTIVE_BREADTH, BREADTH_MANDATE])
    return _mk("effective_breadth_n_eff", value,
               f"{_rel(EFFECTIVE_BREADTH)} {field} (n_nominal={eff.get('n_nominal')}, "
               f"binding={eff.get('binding_reading')})", _stamp(doc))


def _r02_certified_chart_session_axes() -> dict[str, Any]:
    # The named reports carry the AXES, not a certified cell -- SESSION_CHART_EXPANSION says of
    # itself "PROPOSES ONLY -- mints no certificate" -- so certified cells are counted where the
    # desk records them, and a cell missing either axis is undeclared, never filled in with an H1.
    dim, read, docs, charts = "certified_chart_session_axes", [], [], "?"
    pairs: list[tuple[str, str]] = []
    for path in (TIMEFRAME_COVERAGE, SESSION_CHART_EXPANSION):
        doc = _read(path)
        if isinstance(doc, dict):
            read.append(_rel(path))
            docs.append(doc)
            by_tf = _dict(doc, "coverage").get("by_timeframe")
            if isinstance(by_tf, dict):
                charts = str(sum(1 for v in by_tf.values() if (_num(v) or 0.0) > 0))
    sleeves = _sleeve_rows()
    if sleeves:
        read.append(_rel(SLEEVES))
        docs.append(_read(SLEEVES))
        pairs += [(str(s.get("timeframe") or "").upper(), str(s.get("session") or ""))
                  for s in sleeves if s.get("certificate")]
    surv = _read(UNIVERSAL_SURVIVORS)
    if isinstance(surv, dict):
        read.append(_rel(UNIVERSAL_SURVIVORS))
        docs.append(surv)
        for row in _dict(surv, "survivors").values():
            spec = _dict(row, "shadow_spec")
            pairs.append((str(_dict(spec, "params").get("timeframe") or spec.get("timeframe")
                              or "").upper(), str(spec.get("selector") or "")))
    if not read:
        return _gone(dim, [TIMEFRAME_COVERAGE, SESSION_CHART_EXPANSION, SLEEVES,
                           UNIVERSAL_SURVIVORS])
    cells = {p for p in pairs if all(p)}
    return _mk(dim, float(len(cells)),
               f"{' + '.join(read)}: distinct (timeframe, session) over certified rows; "
               f"charts_hunted={charts}, cells_without_both_axes="
               f"{sum(1 for p in pairs if not all(p))}", _stamp(docs[0]))


def _r03_mechanism_clusters() -> dict[str, Any]:
    dim = "mechanism_clusters_occupied"
    mandate = _read(BREADTH_MANDATE)
    if isinstance(mandate, dict) and isinstance(mandate.get("occupied"), list):
        return _mk(dim, float(len(mandate["occupied"])), f"{_rel(BREADTH_MANDATE)} occupied "
                   f"(declared_clusters={mandate.get('declared_clusters')})", _stamp(mandate))
    breadth = _read(EFFECTIVE_BREADTH)
    clusters = _dict(breadth, "clusters")
    if clusters:
        union = {str(x) for key in ("occupied_either", "occupied_traded", "occupied_certified")
                 for x in clusters.get(key) or []
                 if isinstance(clusters.get(key), list)}
        return _mk(dim, float(len(union)), f"{_rel(EFFECTIVE_BREADTH)} clusters.occupied_* union "
                   f"(declared={clusters.get('declared')})", _stamp(breadth))
    genome = _read(ALPHA_GENOME)
    n_clusters = _num(genome.get("n_clusters")) if isinstance(genome, dict) else None
    if n_clusters is None:
        return _gone(dim, [BREADTH_MANDATE, EFFECTIVE_BREADTH, ALPHA_GENOME])
    return _mk(dim, n_clusters, f"{_rel(ALPHA_GENOME)} n_clusters", _stamp(genome))


def _r04_asset_classes() -> dict[str, Any]:
    dim = "asset_classes_producing_survivors"
    surv = _read(UNIVERSAL_SURVIVORS)
    if not isinstance(surv, dict):
        return _gone(dim, [UNIVERSAL_SURVIVORS])
    try:
        from universe_policy import asset_class_of
    except ImportError as exc:                                              # pragma: no cover
        return _mk(dim, None, f"UNMEASURED: research/universe_policy.py not importable ({exc})")
    classes = {asset_class_of(symbol) for symbol, _selector in _survivors(surv)}
    unclassified = sum(1 for k in classes if not k)
    return _mk(dim, float(len(classes - {""})),
               f"{_rel(UNIVERSAL_SURVIVORS)} survivors[*].shadow_spec.symbol -> "
               f"universe_policy.asset_class_of (unclassified={unclassified})", _stamp(surv))


def _r05_pit_compliance() -> dict[str, Any]:
    dim = "pit_compliance_pct"
    census, lake = _read(PIT_CENSUS), _read(LAKE_PROMOTION)
    readings: list[tuple[str, float]] = []
    stamped, needed = (_num(_dict(census, "census").get(k)) for k in ("stamped", "sidecars"))
    if stamped is not None and needed:
        readings.append(("PIT stamped/sidecars", round(100.0 * stamped / needed, 2)))
    silver = _num(lake.get("silver_share")) if isinstance(lake, dict) else None
    if silver is not None:
        readings.append(("lake silver_share", round(100.0 * silver, 2)))
    if not readings:
        return _gone(dim, [PIT_CENSUS, LAKE_PROMOTION])
    # THE MINIMUM OVER THE MEASURED READINGS, never their average -- the desk's own rule in
    # EFFECTIVE_BREADTH.json. A lake that stamps nothing is not half point-in-time clean.
    name, value = min(readings, key=lambda t: t[1])
    return _mk(dim, value,
               f"{_rel(PIT_CENSUS)} canaries.green={_dict(census, 'canaries').get('green')}, "
               f"census.stamped/sidecars + {_rel(LAKE_PROMOTION)} silver_share; binding={name}",
               _stamp(census) or _stamp(lake))


def _r06_live_attribution() -> dict[str, Any]:
    dim = "live_trade_attribution_pct"
    deals = _read_jsonl(LIVE_LEDGER)
    if deals is None:
        return _gone(dim, [LIVE_LEDGER])
    known = {str(s.get("name")) for s in _sleeve_rows()}
    known |= set(_dict(_read(UNIVERSAL_SURVIVORS), "survivors"))
    hit = sum(1 for d in deals if str(d.get("sleeve") or "") in known)
    if not deals:
        # An EMPTY ledger is not 100% attributed. It is no evidence at all (L1.28a).
        return _mk(dim, None, f"UNMEASURED: {_rel(LIVE_LEDGER)} holds no deals to attribute")
    return _mk(dim, round(100.0 * hit / len(deals), 2),
               f"{_rel(LIVE_LEDGER)} sleeve in {_rel(SLEEVES)} sleeves[*].name or "
               f"{_rel(UNIVERSAL_SURVIVORS)} survivors keys: {hit}/{len(deals)}",
               str(deals[-1].get("time") or "") or None)


def _r07_silent_failures() -> dict[str, Any]:
    dim = "silent_scheduled_failures"
    health, marker = _read(PROCESS_HEALTH), _read(SYNC_MARKER)
    read, total, bad_legs = [], 0.0, 0
    counts = _dict(health, "counts")
    if counts:
        read.append(f"{_rel(PROCESS_HEALTH)} counts.FAILING+NOT_SCHEDULED")
        total += (_num(counts.get("FAILING")) or 0.0) + (_num(counts.get("NOT_SCHEDULED")) or 0.0)
    if isinstance(marker, dict):
        read.append(f"{_rel(SYNC_MARKER)} legs LEG_FAILED/TIMEOUT")
        bad_legs = sum(1 for leg in marker.values() if isinstance(leg, dict)
                       and str(leg.get("status") or "") in ("LEG_FAILED", "TIMEOUT"))
        total += bad_legs
    if not read:
        return _gone(dim, [PROCESS_HEALTH, SYNC_MARKER])
    return _mk(dim, total, f"{' + '.join(read)} (legs={bad_legs})",
               _stamp(health) or _stamp(marker))


def _r08_forward_lineage() -> dict[str, Any]:
    # A clock key carries symbol and selector (`XAUUSD.asia.MACRO_FAV`) and so does the
    # certificate, so the join is on what the desk records, not on a naming convention. The
    # single-candidate fallback is `credit_assignment`'s: two organs disagreeing about what a
    # lineage IS would make both reports unreadable.
    dim = "backtest_forward_lineage_pct"
    surv, shadow = _read(UNIVERSAL_SURVIVORS), _read(SHADOW_STATE)
    if not isinstance(surv, dict) or not isinstance(shadow, dict):
        return _gone(dim, [UNIVERSAL_SURVIVORS, SHADOW_STATE])
    by_symbol: dict[str, list[str]] = {}
    for key, row in shadow.items():
        if isinstance(row, dict):
            by_symbol.setdefault(str(key).split(".")[0], []).append(str(key))
    certs = _survivors(surv)
    joined = sum(1 for symbol, selector in certs
                 if any(selector and selector in c for c in by_symbol.get(symbol) or [])
                 or (len(by_symbol.get(symbol) or []) == 1 and not selector))
    if not certs:
        return _mk(dim, None,
                   f"UNMEASURED: {_rel(UNIVERSAL_SURVIVORS)} holds no survivors to join")
    return _mk(dim, round(100.0 * joined / len(certs), 2),
               f"{_rel(UNIVERSAL_SURVIVORS)} survivors x {_rel(SHADOW_STATE)} clock keys "
               f"(symbol+selector, credit_assignment join): {joined}/{len(certs)}", _stamp(surv))


def _r09_cost_model() -> dict[str, Any]:
    dim = "cost_model_maturity"
    doc = _read(COST_SURFACE)
    if not isinstance(doc, dict):
        return _gone(dim, [COST_SURFACE])
    by_hour = any(isinstance(v, dict) and v.get("hours") for v in _dict(doc, "symbols").values())
    dims = _keys_anywhere(doc, {"size", "by_size", "volume_bucket", "regime", "by_regime",
                                "order_type", "by_order_type"})
    per_alpha = _keys_anywhere(doc, {"by_alpha", "by_sleeve", "by_strategy", "per_alpha"})
    level = 0.0 if not by_hour else (1.0 if not dims else (2.0 if not per_alpha else 3.0))
    return _mk(dim, level, f"{_rel(COST_SURFACE)} symbols[*].hours={by_hour}, "
               f"size/regime/order_type dims={sorted(dims) or 'ABSENT'}, per-alpha distribution="
               f"{sorted(per_alpha) or 'ABSENT'}", _stamp(doc))


def _r10_cross_asset() -> dict[str, Any]:
    dim = "cross_asset_intelligence"
    world = _read(WORLD_CAUSAL_GRAPH)
    if not isinstance(world, dict):
        graph = _read(CROSS_ASSET_GRAPH)
        n_edges = _num(graph.get("edges")) if isinstance(graph, dict) else None
        if n_edges is None:
            return _gone(dim, [WORLD_CAUSAL_GRAPH, CROSS_ASSET_GRAPH])
        return _mk(dim, 1.0 if n_edges > 0 else 0.0,
                   f"{_rel(CROSS_ASSET_GRAPH)} edges={int(n_edges)} -- counts only, no edge list, "
                   "so no edge field can be read", _stamp(graph))
    edges = [e for key in ("admitted_edges", "recorded_not_admitted")
             for e in world.get(key) or [] if isinstance(e, dict)]
    keys = {str(k).lower() for e in edges[:400] for k in e}
    present = {
        "lag": bool(keys & {"lag", "lag_total", "lags"}),
        "stability": "stability" in keys,
        "event_propagation": bool(world.get("chains") or _num(world.get("chains_seeded"))),
        "conditional_partial": bool(keys & {"conditional", "partial_corr", "conditioning"}
                                    or world.get("conditioning")),
        "regime_dependence": bool(keys & {"state_dependence", "regime", "regime_dependence"}),
    }
    n_present = sum(present.values())
    level = 0.0 if not edges else (1.0 if n_present <= 2 else (2.0 if n_present <= 4 else 3.0))
    return _mk(dim, level, f"{_rel(WORLD_CAUSAL_GRAPH)} edges={len(edges)} carrying "
               f"{sorted(k for k, v in present.items() if v) or 'NO EDGE FIELDS'}; "
               f"edges_admitted={world.get('edges_admitted')}", _stamp(world))


def _r11_macro() -> dict[str, Any]:
    dim = "macro_intelligence"
    macro, vector = _read(MACRO_STATE), _read(STATE_VECTOR)
    if not isinstance(macro, dict) and not isinstance(vector, dict):
        return _gone(dim, [MACRO_STATE, STATE_VECTOR])
    n_series = len(_dict(macro, "series")) or len(_dict(vector, "assets")) + len(
        _dict(vector, "factors"))
    diffs = _dict(macro, "differentials")
    per_country = bool(_keys_anywhere(macro, {"by_country", "countries", "blocks_by_country"})
                       ) or len(diffs) >= 2
    sens = bool(_dict(vector, "factors") or _dict(vector, "conditioning")
                or _keys_anywhere(macro, {"sensitivities", "betas", "sensitivity"}))
    level = 0.0 if n_series < 1 else (1.0 if not per_country else (2.0 if not sens else 3.0))
    return _mk(dim, level, f"{_rel(MACRO_STATE)} series={n_series}, per-country blocks="
               f"{per_country} (differentials={len(diffs)}), {_rel(STATE_VECTOR)} "
               f"sensitivities={sens}", _stamp(macro) or _stamp(vector))


def _r12_allocator() -> dict[str, Any]:
    dim = "allocator_maturity"
    standalone, pf = _read(ALLOCATOR_PROOF), _read(PF_ALLOCATION)
    own = isinstance(standalone, dict) and "passed" in standalone
    proof = standalone if own else _dict(pf, "proof")
    if not proof:
        return _gone(dim, [ALLOCATOR_PROOF, PF_ALLOCATION])
    why, passed = str(proof.get("why") or ""), bool(proof.get("passed"))
    hysteresis = bool(proof.get("hysteresis")) or "holds authority" in why or "margin" in why
    posterior = "posterior" in {str(k).lower() for k in _dict(proof, "scores")} or bool(
        _dict(pf, "posterior_growth"))
    level = 1.0 if not (passed and hysteresis) else (2.0 if not posterior else 3.0)
    return _mk(dim, level, f"{_rel(ALLOCATOR_PROOF) if own else _rel(PF_ALLOCATION) + ' proof'}: "
               f"passed={passed}, hysteresis={hysteresis}, {_rel(PF_ALLOCATION)} posterior "
               f"fields={posterior}", _stamp(standalone) or _stamp(pf))


def _r13_moat_days() -> dict[str, Any]:
    # `moat_coverage.json` counts PARQUET FILES in a 7-day window (two naming conventions share
    # the directory, so its counts exceed its own window) and TAPE_RECORDER publishes liveness.
    # Neither carries a day count, so reading one as "days" would be a fabrication; both are named
    # in the basis as the cross-check they actually are.
    dim, days, scanned = "proprietary_moat_days", set(), 0
    try:
        for symbol_dir in sorted(Path(TAPE_TICKS).iterdir()):
            if not symbol_dir.is_dir() or scanned >= 500:
                continue
            scanned += 1
            days |= {s for s in (f.stem.replace("-", "") for f in symbol_dir.glob("*.parquet"))
                     if len(s) == 8 and s.isdigit()}
    except OSError:
        scanned = 0
    moat, recorder = _read(MOAT_COVERAGE), _read(TAPE_RECORDER)
    if not scanned and not days:
        return _gone(dim, [TAPE_TICKS, MOAT_COVERAGE, TAPE_RECORDER])
    return _mk(dim, float(len(days)),
               f"{_rel(TAPE_TICKS)}/*/YYYY-MM-DD.parquet distinct dates over {scanned} symbol "
               f"dir(s); {_rel(MOAT_COVERAGE)} newest_tape_write="
               f"{(moat or {}).get('newest_tape_write')}, {_rel(TAPE_RECORDER)} "
               f"state={(recorder or {}).get('state')}", _stamp(moat) or _stamp(recorder))


def _r14_conversion_backlog() -> dict[str, Any]:
    dim = "research_conversion_backlog"
    conservation, conversion = _read(CANDIDATE_CONSERVATION), _read(ROW_CONVERSION)
    waiting = _num(conservation.get("n_waiting")) if isinstance(conservation, dict) else None
    if waiting is not None:
        lost = _num(conservation.get("n_lost")) or 0.0
        return _mk(dim, waiting + lost, f"{_rel(CANDIDATE_CONSERVATION)} n_waiting={int(waiting)}"
                   f" + n_lost={int(lost)}", _stamp(conservation))
    summary = _dict(conversion, "summary")
    backlog = _num(summary.get("backlog"))
    if backlog is None:
        return _gone(dim, [CANDIDATE_CONSERVATION, ROW_CONVERSION])
    return _mk(dim, backlog, f"{_rel(ROW_CONVERSION)} summary.backlog "
               f"(backlog_share={summary.get('backlog_share')})", _stamp(conversion))


BUILDERS = (_r01_effective_breadth, _r02_certified_chart_session_axes, _r03_mechanism_clusters,
            _r04_asset_classes, _r05_pit_compliance, _r06_live_attribution, _r07_silent_failures,
            _r08_forward_lineage, _r09_cost_model, _r10_cross_asset, _r11_macro, _r12_allocator,
            _r13_moat_days, _r14_conversion_backlog)


# ----------------------------------------------------------------------- the board, and the why
def _gap(row: dict[str, Any]) -> float:
    """0 = at or past the first target, 1 = nothing of it achieved. For RANKING only."""
    current, target = row.get("current"), row.get("first_target")
    if current is None or target is None:
        return -1.0
    if row.get("lower_is_better"):
        return 1.0 - 1.0 / (1.0 + max(0.0, float(current) - float(target)))
    return 0.0 if float(target) <= 0 else max(0.0, 1.0 - min(1.0, float(current) / float(target)))


def _overall(rows: list[dict[str, Any]]) -> dict[str, Any]:
    at_or_above = [r for r in rows if r["verdict"] in (AT, ABOVE)]
    below = [r for r in rows if r["verdict"] == BELOW]
    unmeasured = [r for r in rows if r["verdict"] == UNMEASURED]
    weakest = sorted((r for r in rows if r["verdict"] != UNMEASURED),
                     key=lambda r: (-_gap(r), str(r["dimension"])))[:3]
    named = "; ".join(f"{r['dimension']} at {r['current']} {r['unit']} against a first target of "
                      f"{r['first_target']}" for r in weakest) or "none -- no row is measured"
    absent = ("each of those names the artifact path it looked for, so the work there is to "
              "schedule the organ that writes it, never to assume the number"
              if unmeasured else "which would be a verdict and never a zero, and today there "
              "are none -- every row below was read from an artifact that exists")
    why = (f"{len(at_or_above)} of {len(rows)} dimensions are AT or ABOVE their first target, "
           f"{len(below)} are BELOW and {len(unmeasured)} are UNMEASURED -- {absent}. "
           f"The three weakest MEASURED "
           f"rows are {named}. Those buy the most next hour, because the rest of the board is read "
           "through them: breadth that is not point-in-time clean cannot be trusted, a live trade "
           "that cannot be attributed cannot feed credit assignment, and a backlog that does not "
           "shrink is a claim the desk cannot cash. Nothing here is asserted -- a number moves "
           "when an organ writes a better artifact, never when this file is edited.")
    return {"at_or_above": len(at_or_above), "below": len(below), "unmeasured": len(unmeasured),
            "weakest_measured": [r["dimension"] for r in weakest], "why": why}


def build() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for builder in BUILDERS:
        try:
            rows.append(builder())
        except Exception as exc:
            rows.append({"dimension": builder.__name__[5:], "current": None, "unit": "?",
                         "first_target": None, "max_solo_direction": "?", "verdict": UNMEASURED,
                         "basis": f"UNMEASURED: builder raised {type(exc).__name__}: {exc}",
                         "measured_at": None, "lower_is_better": False})
    return {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "authority": ("MEASUREMENT ONLY -- sizes nothing, gates nothing, certifies nothing. "
                          "It reports where the fourteen Tier-1 dimensions stand, read from the "
                          "artifacts that own them."),
            "n_rows": len(rows), "rows": rows, "overall": _overall(rows)}


def render(doc: dict[str, Any]) -> list[str]:
    """Sixteen lines: a header, the fourteen rows, and the overall count."""
    lines = [f"{'dimension':<34}{'current':>12}{'target':>10}  {'verdict':<11}basis"]
    for row in doc.get("rows") or []:
        current = "UNMEASURED" if row["current"] is None else f"{row['current']:g}"
        target = "-" if row["first_target"] is None else f"{row['first_target']:g}"
        lines.append(f"{str(row['dimension'])[:33]:<34}{current:>12}{target:>10}  "
                     f"{row['verdict']!s:<11}{str(row['basis'])[:29]}")
    overall = doc.get("overall") or {}
    weakest = ", ".join(d[:18] for d in overall.get("weakest_measured") or []) or "none measured"
    lines.append(f"AT/ABOVE {overall.get('at_or_above')}  BELOW {overall.get('below')}  "
                 f"UNMEASURED {overall.get('unmeasured')}  weakest: {weakest}"[:100])
    return lines


def write(doc: dict[str, Any], path: Path | str | None = None) -> bool:
    """Atomic: a reader never sees a half-written board. Never raises -- it reports False."""
    target = Path(path or OUT)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{target.name}.tmp{os.getpid()}")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, target)
        return True
    except OSError as exc:
        print(f"TIER1_SCORECARD not written ({type(exc).__name__}: {exc})")
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the table, write nothing")
    parser.add_argument("--out", default=None, help="override the output path")
    args = parser.parse_args(argv)
    doc = build()
    for line in render(doc):
        print(line)
    if not args.dry_run:
        write(doc, args.out)
        print(f"written: {args.out or OUT}")
    return 0


if __name__ == "__main__":                                                  # pragma: no cover
    raise SystemExit(main())
