"""THE EXOTIC CERTIFICATES' SPECS, RE-EXPRESSED ON THE INSTRUMENTS THE DESK MAY TRADE.

MEASURED ON THE BOX 2026-11-25 02:30Z: 13,452 ten-gate certificates, 722 of them on non-exotic
instruments. The principal banned exotics outright (zuck 2026-11-24 18:06Z: no mining, judging or
trading of an FX pair with a fiat leg outside USD EUR JPY GBP CHF AUD NZD CAD), so 12,730
certificates name a mechanism the book can never hold. The mechanism may still be real: a spec
that certified on USDZAR may be pricing the DOLLAR leg, and the dollar trades on EURUSD.

WHAT THIS ORGAN DOES. For every certified spec whose symbol is exotic, it takes the EXACT family
and params and mints the same spec on the eligible tradable instruments that share its economic
driver, chosen by the declared mapping below. Each minted cell is a NEW hypothesis entering the
desk's one door (`libs.moat.registry.enqueue_candidate`, the same door `pack_cells` and
`timeframe_fanout` use; `merge_hypotheses` feeds the registry into the docket through
`libs.moat.docket_feed`), so it is judged by the sealed gauntlet and charged as a trial exactly
like any other cell.

WHAT IT NEVER DOES. The exotic certificate is PROVENANCE, never evidence: nothing from its gates
travels with the minted cell, no gate, threshold, DSR/FDR input or trial count is read or
written, and no certificate is touched. An exotic is never a target. A cell already in the docket
(by `frontier_identity.docket_cell_id`) or in the registry (by its content hash) is skipped and
counted, never minted twice.

THE MAPPING (declared, so a reader can say why each target was chosen):

  * leg      -- default for every family: the tradable FX pairs that carry one of the source's
                major legs (USDZAR -> USD majors; EURNOK -> EUR pairs; CHFHUF -> CHF pairs). A
                source with no major leg maps to the USD majors, the pricing leg of every exotic.
  * carry    -- the tradable FX pairs with the largest positive swap (money per lot per night,
                from the broker's own swap table), top CARRY_TOP_K; the leg rule when the
                registry carries no swaps.
  * macro    -- macro_conditional: the instruments its macro series is declared to drive
                (SERIES_DRIVER -> DRIVER_TARGETS); an unknown series falls back to the leg rule.
  * driver   -- formula: the instruments the expression's driver terminals (usd, rates, risk,
                gold, oil, growth) name; a bar-only expression falls back to the leg rule.

A scalar param equal to the source symbol (carry's `input_symbol`) is re-pointed at the target;
a target that is one of the spec's own factor symbols is skipped (a residual on itself).

BUDGET AND CURSOR. The full plan is ordered deterministically by (source key, target); each pass
mints at most `--budget-cells` NEW cells from a saved cursor and wraps, so every planned cell is
reached over passes. Duplicates do not consume the budget.

    python desks/mt5/research/exotic_transplant.py --once
    python desks/mt5/research/exotic_transplant.py --once --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The certified set the box holds at run time, then the canon fallback the prop allocator uses
#: when the first is empty (prop_challenge_allocator.py reads the same pair).
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SURVIVORS_CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
CURSOR = DESK / "data" / "exotic_transplant_cursor.json"
OUT = DESK / "reports" / "EXOTIC_TRANSPLANT.json"

ORIGIN = "exotic_transplant"
#: New cells minted per pass. Deterministic; the cursor carries the rest to the next pass.
BUDGET_CELLS = int(os.environ.get("EXOTIC_TRANSPLANT_BUDGET_CELLS", "2000"))
CARRY_TOP_K = 8

MAJORS8: frozenset[str] = frozenset({"USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD"})
#: The registry classes a target may come from: FX majors/crosses, metals, indices, energy and
#: crypto CFDs -- the principal's tradable set. Equities, softs and bonds are never targets here.
TARGET_CLASSES: frozenset[str] = frozenset({
    "forex", "forex majors", "forex crosses", "fx", "fx_major", "fx_cross", "fx major",
    "fx cross", "commodities", "commodity", "metals", "energy", "indices", "index", "crypto",
    "cryptocurrency"})
FX_CLASSES: frozenset[str] = frozenset({
    "forex", "forex majors", "forex crosses", "fx", "fx_major", "fx_cross", "fx major",
    "fx cross"})

#: What each driver force moves, declared. Filtered at run time to eligible symbols.
DRIVER_TARGETS: dict[str, tuple[str, ...]] = {
    "usd": ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "USDX",
            "XAUUSD"),
    "rates": ("USDJPY", "EURUSD", "USDX", "XAUUSD", "US500", "NAS100", "US30"),
    "risk": ("AUDJPY", "NZDJPY", "CADJPY", "USDJPY", "US500", "NAS100", "GER40", "JPN225",
             "XAUUSD", "BTCUSD"),
    "gold": ("XAUUSD", "XAGUSD", "AUDUSD", "USDCHF"),
    "oil": ("XTIUSD", "XBRUSD", "USDCAD", "CADJPY"),
    "growth": ("AUDUSD", "NZDUSD", "XCUUSD", "AUS200", "HK50", "CHINAH"),
}
DRIVER_TERMINALS: tuple[str, ...] = tuple(DRIVER_TARGETS)
#: macro_conditional's series (orthogonal_sweep.DAILY_MACRO_SERIES) -> the force it measures.
SERIES_DRIVER: dict[str, str] = {
    "DTWEXBGS": "usd", "DGS10": "rates", "DGS2": "rates", "T10Y2Y": "rates", "SOFR": "rates",
    "DFF": "rates", "VIXCLS": "risk", "BAMLH0A0HYM2": "risk", "DCOILWTICO": "oil"}
#: The family's own default when a cell names no series: the first of its list (the dollar).
MACRO_DEFAULT_SERIES = "DTWEXBGS"

RULES: dict[str, str] = {
    "leg": ("the tradable FX pairs carrying one of the source's major legs; a source with no "
            "major leg maps to the USD majors"),
    "carry": (f"the top {CARRY_TOP_K} tradable FX pairs by positive swap (money per lot per "
              "night from the broker swap table); the leg rule when no swaps are held"),
    "macro": ("macro_conditional: the instruments its macro series is declared to drive "
              "(SERIES_DRIVER -> DRIVER_TARGETS); the leg rule for an unknown series"),
    "driver": ("formula: the instruments its driver terminals name (DRIVER_TARGETS); the leg "
               "rule for a bar-only expression"),
}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


# ------------------------------------------------------------------ classification
def _bare(sym: str) -> str:
    return str(sym or "").split("@", 1)[0].strip()


def is_exotic(sym: str, klass: str | None = None) -> bool:
    """The desk's ONE exotic definition (`universe_policy.is_exotic_symbol`)."""
    from research import universe_policy as up
    return bool(up.is_exotic_symbol(_bare(sym), klass))


def _legs(sym: str) -> tuple[str, str] | None:
    core = "".join(ch for ch in _bare(sym).upper() if "A" <= ch <= "Z")
    return (core[:3], core[3:6]) if len(core) == 6 else None


def eligible_targets(meta: Mapping[str, Any], universe_dir: Path | None = None
                     ) -> dict[str, dict[str, Any]]:
    """symbol -> its registry row, for every symbol this organ may mint on: a target class,
    never exotic, not flagged untradeable, and (when the host holds any H1 parquet) one the
    merge's tradeable filter would keep."""
    udir = universe_dir if universe_dir is not None else UNIVERSE.parent
    have_parquets = False
    try:
        have_parquets = any(udir.glob("*_H1.parquet"))
    except OSError:
        have_parquets = False
    out: dict[str, dict[str, Any]] = {}
    for sym, row in meta.items():
        if not isinstance(row, dict):
            continue
        klass = str(row.get("asset_class") or "").strip().lower()
        if klass not in TARGET_CLASSES or "exotic" in klass:
            continue
        if row.get("tradeable") is False:
            continue
        if is_exotic(str(sym), klass):
            continue
        if have_parquets and not (udir / f"{sym}_H1.parquet").exists():
            continue
        out[str(sym)] = row
    return out


def _is_fx(row: Mapping[str, Any]) -> bool:
    return str(row.get("asset_class") or "").strip().lower() in FX_CLASSES


# ------------------------------------------------------------------ the certified set
def certified_rows() -> tuple[dict[str, Any], str]:
    """The certified set the box holds NOW: reports/ first, the canon when that is empty."""
    for p in (SURVIVORS, SURVIVORS_CANON):
        doc = _read(p, {}) or {}
        surv = doc.get("survivors") if isinstance(doc, dict) else None
        if isinstance(surv, dict) and surv:
            return surv, str(p.relative_to(DESK)).replace("\\", "/")
    return {}, ""


def parse_spec(key: str, row: Mapping[str, Any]) -> dict[str, Any] | None:
    """(symbol, family, params, chart) of one `external.<SYM>.<family>.<params>` certificate."""
    if not str(key).startswith("external."):
        return None
    parts = str(key).split(".")
    if len(parts) < 3:
        return None
    _spec = row.get("shadow_spec")
    spec: Mapping[str, Any] = _spec if isinstance(_spec, dict) else {}
    named = parts[1]
    sym = _bare(str(spec.get("symbol") or row.get("sym") or named))
    fam = str(spec.get("family") or parts[2])
    raw = spec.get("params") if isinstance(spec.get("params"), dict) else row.get("params")
    params = dict(raw) if isinstance(raw, dict) else {}
    chart = ""
    if params.get("timeframe"):
        chart = str(params["timeframe"]).upper()
    elif "@" in named:
        chart = named.split("@", 1)[1].upper()
    elif spec.get("timeframe") or spec.get("chart"):
        chart = str(spec.get("timeframe") or spec.get("chart")).upper()
    if not sym or not fam:
        return None
    return {"key": str(key), "symbol": sym, "family": fam, "params": params,
            "chart": chart or "H1"}


# ------------------------------------------------------------------ the mapping
def _leg_targets(src: str, elig: Mapping[str, Mapping[str, Any]]) -> list[str]:
    legs = _legs(src)
    majors = [c for c in (legs or ()) if c in MAJORS8]
    if not majors:
        majors = ["USD"]
    out: list[tuple[int, str]] = []
    for sym, row in elig.items():
        if not _is_fx(row):
            continue
        tl = _legs(sym)
        if not tl or not (set(tl) <= MAJORS8):
            continue
        shared = [c for c in majors if c in tl]
        if not shared:
            continue
        # the same leg in the same position (USDZAR -> USDJPY before EURUSD) ranks first
        same_pos = any(legs and tl[i] == legs[i] for i in (0, 1) if legs and legs[i] in majors)
        out.append((0 if same_pos else 1, sym))
    return [s for _r, s in sorted(out)]


def carry_money(row: Mapping[str, Any]) -> float | None:
    """The better side's swap in account money per lot per night, or None when unknown."""
    try:
        sl, ss = float(row["swap_long"]), float(row["swap_short"])
        tv = float(row.get("tick_value") or 0.0)
        ts = float(row.get("tick_size") or 0.0)
        digits = int(row.get("digits") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    if tv <= 0 or ts <= 0:
        return None
    point = 10.0 ** -digits
    return max(sl, ss) * tv * (point / ts)


def _carry_targets(src: str, elig: Mapping[str, Mapping[str, Any]]) -> list[str] | None:
    scored = []
    for sym, row in elig.items():
        if not _is_fx(row):
            continue
        m = carry_money(row)
        if m is not None:
            scored.append((-m, sym))
    if not scored:
        return None
    return [s for _m, s in sorted(scored)[:CARRY_TOP_K]]


def _driver_list(drivers: Iterable[str], elig: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for d in drivers:
        for s in DRIVER_TARGETS.get(d, ()):
            if s in elig and s not in out:
                out.append(s)
    return out


def formula_drivers(expr: Any) -> list[str]:
    """The driver terminals a formula expression names, in DRIVER_TERMINALS order."""
    if isinstance(expr, (list, tuple)):
        found: set[str] = set()
        stack: list[Any] = [expr]
        while stack:
            x = stack.pop()
            if isinstance(x, str):
                found.add(x)
            elif isinstance(x, (list, tuple)):
                stack.extend(x[1:] if x and isinstance(x[0], str) else x)
    else:
        found = set(re.findall(r"[A-Za-z_]+", str(expr or "")))
    return [d for d in DRIVER_TERMINALS if d in found]


def targets_for(spec: Mapping[str, Any], elig: Mapping[str, Mapping[str, Any]]
                ) -> tuple[list[str], str, str]:
    """(targets, rule, driver) for one exotic spec. Never an exotic, never the source."""
    fam, src, params = spec["family"], spec["symbol"], spec.get("params") or {}
    rule, driver, out = "leg", "", None
    if fam == "carry":
        got = _carry_targets(src, elig)
        if got:
            rule, out = "carry", got
    elif fam == "macro_conditional":
        series = str(params.get("macro_series") or MACRO_DEFAULT_SERIES).upper()
        force = SERIES_DRIVER.get(series)
        if force:
            got = _driver_list([force], elig)
            if got:
                rule, driver, out = "macro", f"{series}->{force}", got
    elif fam == "formula":
        drivers = formula_drivers(params.get("expr"))
        if drivers:
            got = _driver_list(drivers, elig)
            if got:
                rule, driver, out = "driver", ",".join(drivers), got
    if out is None:
        out = _leg_targets(src, elig)
    final = [t for t in out if t != src and t in elig and not is_exotic(t)]
    return final, rule, driver


def transplant_params(params: Mapping[str, Any], src: str, target: str) -> dict[str, Any] | None:
    """The source's exact params on `target`: a scalar naming the source is re-pointed at the
    target; None when the target is one of the spec's own factor symbols."""
    out: dict[str, Any] = {}
    s_up = src.upper()
    for k, v in params.items():
        if isinstance(v, str) and _bare(v).upper() == s_up:
            out[k] = target
        elif isinstance(v, (list, tuple)) and any(
                isinstance(x, str) and _bare(x).upper() == target.upper() for x in v):
            return None
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------ the plan
def build_plan(survivors: Mapping[str, Any], elig: Mapping[str, Mapping[str, Any]]
               ) -> tuple[list[dict[str, Any]], dict[str, Counter[str]]]:
    """Every (exotic source spec x target) cell, deterministically ordered and de-duplicated
    within the plan (first source in key order keeps the provenance)."""
    from research.frontier_identity import docket_cell_id
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    plan: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in sorted(survivors):
        row = survivors[key]
        if not isinstance(row, dict):
            continue
        spec = parse_spec(key, row)
        if spec is None:
            stats["_not_external"]["sources_read"] += 1
            continue
        fam = spec["family"]
        st = stats[fam]
        st["certificates_read"] += 1
        if not is_exotic(spec["symbol"]):
            continue
        st["exotic_sources"] += 1
        targets, rule, driver = targets_for(spec, elig)
        if not targets:
            st["sources_with_no_target"] += 1
            continue
        for t in targets:
            p = transplant_params(spec["params"], spec["symbol"], t)
            if p is None:
                st["skipped_target_is_factor"] += 1
                continue
            cell = {"symbol": t, "family": fam, "params": p, "timeframe": spec["chart"]}
            cid = docket_cell_id(cell)
            if cid in seen:
                st["skipped_duplicate_in_plan"] += 1
                continue
            seen.add(cid)
            st["targets_planned"] += 1
            plan.append({**cell, "cell_id": cid, "source_certificate": key,
                         "source_symbol": spec["symbol"], "rule": rule, "driver": driver})
    return plan, stats


def docket_ids(path: Path, plan_ids: set[str], families: set[str], symbols: set[str],
               deadline: float) -> tuple[set[str], str]:
    """The planned cell ids already in the docket, streamed once. ('', ...) when complete."""
    from research.frontier_identity import docket_cell_id
    hit: set[str] = set()
    if not path.exists():
        return hit, "UNMEASURED: no docket on this host"
    try:
        from libs.research.family_firing import iter_json_array
        n = 0
        for r in iter_json_array(path):
            n += 1
            if not isinstance(r, dict) or r.get("family") not in families:
                continue
            if str(r.get("symbol") or r.get("sym") or "") not in symbols:
                continue
            cid = docket_cell_id(r)
            if cid in plan_ids:
                hit.add(cid)
            if n % 50000 == 0 and time.monotonic() > deadline:
                return hit, f"PARTIAL: budget spent after {n} docket rows"
    except Exception as exc:
        return hit, f"UNMEASURED: docket unreadable ({type(exc).__name__})"
    return hit, ""


def _sort_key(item: Mapping[str, Any]) -> tuple[str, str]:
    return (str(item["source_certificate"]), str(item["cell_id"]))


def mint_one(item: Mapping[str, Any], conn: Any) -> bool:
    """One planned cell through the registry door. True when a NEW candidate was written."""
    from libs.moat.registry import enqueue_candidate
    fam, t, src, key = item["family"], item["symbol"], item["source_symbol"], \
        item["source_certificate"]
    chart = str(item["timeframe"] or "H1")
    why = (f"{fam} certified on the exotic {src}; re-expressed on {t} by the {item['rule']} "
           f"rule{(' (' + item['driver'] + ')') if item.get('driver') else ''}: the same "
           "economic driver may carry over to an instrument the desk may trade")
    _cid, created = enqueue_candidate(
        family=fam, symbol=t, params=dict(item["params"]), origin=ORIGIN, mechanism=why,
        chart=chart, conn=conn, generator=ORIGIN, department="prediction",
        transformation="exotic_transplant", source_id=key, parent_ids=[key],
        lineage={"producer": ORIGIN, "source_certificate": key, "source_symbol": src,
                 "mapping_rule": item["rule"], "driver": item.get("driver") or "",
                 "evidence": "none: the source certificate is provenance, never evidence"},
        causal_rationale=why,
        falsifier=f"{fam} with {src}'s certified params has no edge on {t} at {chart}")
    return bool(created)


def build(budget_s: float = 300.0, *, budget_cells: int = BUDGET_CELLS, dry_run: bool = False,
          survivors: Mapping[str, Any] | None = None, survivors_path: str = "",
          meta: Mapping[str, Any] | None = None, universe_dir: Path | None = None,
          docket: Path | None = None, cursor_path: Path | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(1.0, budget_s)
    now = _now()
    cpath = cursor_path or CURSOR
    if survivors is None:
        survivors, survivors_path = certified_rows()
    if meta is None:
        meta = _read(UNIVERSE, {}) or {}
    elig = eligible_targets(meta, universe_dir)
    plan, stats = build_plan(survivors, elig)
    plan.sort(key=_sort_key)
    ids = {p["cell_id"] for p in plan}
    in_docket, docket_why = docket_ids(docket or DOCKET, ids, {p["family"] for p in plan},
                                       {p["symbol"] for p in plan}, deadline)

    cur = _read(cpath, {}) or {}
    after = cur.get("after")
    start = 0
    if isinstance(after, list) and len(after) == 2:
        k = (str(after[0]), str(after[1]))
        start = next((i for i, p in enumerate(plan) if _sort_key(p) > k), len(plan))
    if start >= len(plan):
        start = 0
    order = plan[start:] + plan[:start]

    conn = None
    reg_why = ""
    if not dry_run and order:
        try:
            from libs.moat import registry as R
            conn = R.connect()
        except Exception as exc:
            reg_why = f"UNMEASURED: registry unavailable ({type(exc).__name__})"
    minted = 0
    walked = 0
    last: tuple[str, str] | None = None
    errors: list[str] = []
    from libs.moat.registry import content_hash
    try:
        for item in order:
            if minted >= budget_cells or time.monotonic() > deadline or reg_why:
                break
            st = stats[item["family"]]
            walked += 1
            last = _sort_key(item)
            if item["cell_id"] in in_docket:
                st["skipped_duplicate_docket"] += 1
                continue
            if dry_run:
                st["would_mint"] += 1
                minted += 1
                continue
            h = content_hash(item["family"], item["symbol"], item["params"],
                             str(item["timeframe"] or "H1"))
            if conn is not None and conn.execute(
                    "SELECT 1 FROM research_candidates WHERE content_hash=?", (h,)
                    ).fetchone() is not None:
                st["skipped_duplicate_registry"] += 1
                continue
            try:
                if mint_one(item, conn):
                    st["minted"] += 1
                    minted += 1
                else:
                    st["skipped_duplicate_registry"] += 1
            except Exception as exc:
                errors.append(f"{item['cell_id'][:40]}: {type(exc).__name__}: {str(exc)[:60]}")
                if len(errors) > 20:
                    break
    finally:
        if conn is not None:
            conn.close()

    wrapped = walked >= len(order) and bool(order)
    if not dry_run and last is not None:
        _write(cpath, {"at": now, "after": [] if wrapped else list(last),
                       "rule": ("plan ordered by (source certificate, cell id); each pass starts "
                                "after the last cell it walked and wraps at the end")})
    fams = {k: dict(v) for k, v in sorted(stats.items())}
    total = Counter[str]()
    for k, v in stats.items():
        if not k.startswith("_"):
            total.update(v)
    unmeasured = [w for w in (docket_why, reg_why) if w]
    if not survivors:
        unmeasured.append("UNMEASURED: no certified set on this host")
    return {
        "at": now,
        "status": ("UNMEASURED" if not survivors or reg_why else "OK"),
        "dry_run": bool(dry_run),
        "certified_source": survivors_path,
        "n_certificates": len(survivors),
        "n_eligible_targets": len(elig),
        "rules": RULES,
        "driver_targets": {k: list(v) for k, v in DRIVER_TARGETS.items()},
        "series_driver": SERIES_DRIVER,
        "totals": dict(total),
        "by_family": fams,
        "plan_cells": len(plan),
        "plan_start": start,
        "walked_this_pass": walked,
        "minted_this_pass" if not dry_run else "would_mint_this_pass": minted,
        "budget_cells": budget_cells,
        "cursor_wrapped": wrapped,
        "docket_dedupe": docket_why or "COMPLETE",
        "unmeasured": unmeasured,
        "errors": errors[:10],
        "boundary": ("MINTS ONLY, through libs.moat.registry.enqueue_candidate. Every cell is a "
                     "new hypothesis judged and charged by the sealed gauntlet like any other; "
                     "the exotic certificate is provenance (source_id, parent_ids, lineage), "
                     "never evidence. No gate, DSR/FDR input, trial count or certificate is "
                     "read for scoring or written. No exotic target, ever."),
        "seconds": round(time.monotonic() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--budget-cells", type=int, default=BUDGET_CELLS)
    ap.add_argument("--dry-run", action="store_true",
                    help="count the cells this pass would mint and write nothing but the report")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, budget_cells=a.budget_cells, dry_run=a.dry_run)
    try:
        _write(a.out, doc)
    except OSError as exc:
        print(f"exotic transplant: could not write {a.out}: {exc}")
        return 1
    t = doc["totals"]
    print(f"exotic transplant: {doc['n_certificates']} certificate(s) from "
          f"{doc['certified_source'] or 'NOWHERE'}, {t.get('exotic_sources', 0)} exotic; "
          f"{doc['n_eligible_targets']} eligible target(s); plan {doc['plan_cells']} cell(s)")
    print(f"  {'would mint' if a.dry_run else 'minted'} "
          f"{doc.get('would_mint_this_pass', doc.get('minted_this_pass', 0))}; duplicates "
          f"docket {t.get('skipped_duplicate_docket', 0)} registry "
          f"{t.get('skipped_duplicate_registry', 0)} plan {t.get('skipped_duplicate_in_plan', 0)}")
    for fam, row in doc["by_family"].items():
        if fam.startswith("_"):
            continue
        print(f"   {fam:<24} exotic {row.get('exotic_sources', 0):<6} planned "
              f"{row.get('targets_planned', 0):<6} "
              f"{'would' if a.dry_run else 'minted'} "
              f"{row.get('would_mint', row.get('minted', 0))}")
    for w in doc["unmeasured"]:
        print(f"  {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
