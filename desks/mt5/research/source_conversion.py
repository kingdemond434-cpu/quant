#!/usr/bin/env python3
"""SOURCE_CONVERSION.json -- per data source: mined -> judged -> certified -> live, and reach.

THE PRINCIPAL'S GOAL (2026-11): maximum indirect conversion. Every data source the desk holds must
feed hypotheses for EVERY instrument it trades (cross-asset and lead-lag links included), not just
the source's own instrument, and a source with zero judged hypotheses is a FAULT. This organ is the
measurement; it mints, judges and vetoes nothing.

PROVENANCE IS NOT A NEW PIPE. A cell already says which source it uses:

  * a NAMED series: recipe `params` `source` (exogenous_conditioner, alt_series_momentum,
    alt_conditioned, alt_release_drift), `pack_id`, or `series_key` (world_macro_state);
  * otherwise the FAMILY says it: `mt5desk.families_orthogonal.FAMILY_INPUTS` (cot_positioning ->
    COT, macro_conditional -> macro state, orderflow/liquidity -> the tick tape, carry -> swap
    terms, event_reaction -> the calendar, analyst_* -> analyst views, everything price-derived ->
    the price-bar baseline). A family missing from FAMILY_INPUTS is a legacy price-only family and
    is counted as such: `family_inferred_price_only` says how many cells that touched.

THE FOUR COUNTS, each from the artifact that owns it:

  mined      the docket (`admissible_docket.json`) and the compiler's `miner_candidates.json`,
             one cell id each (`frontier_identity.docket_cell_id`, the judge's own identity)
  judged     `gate_verdict_ledger.jsonl` rows carrying a real verdict (terminal gate or a pass;
             UNKNOWN and NOT_RUN are not verdicts). When the ledger is absent on this host the
             fallback is `gauntlet_seen_cells.json` ("judged, and when"); `judged_basis` names it
  certified  `reports/UNIVERSAL_SURVIVORS.json` + `data/UNIVERSAL_SURVIVORS.canon.json`
  live       `data/sleeves.json` rows with status LIVE, and the non-zero fractions of
             `data/CERT_BOOK_LIVE.json` (the fusion / e8 / ftmo blocks)

UNMEASURED IS NEVER ZERO (L1.28a). An absent input leaves its column `null` with the reason in
`unmeasured`, and a FAULT is never raised from a column that was not measured. Exotics
(`universe_policy.is_exotic_symbol`) and instruments outside the statistical lane are set aside and
counted, never reached and never eligible.

FAULTS: `ZERO_JUDGED` (mined > 0, judged == 0) and `NEVER_MINED` (the source exists on this host and
no cell names it).

    python desks/mt5/research/source_conversion.py --once
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "SOURCE_CONVERSION.json"
SCHEMA = "source-conversion/1"
UNMEASURED = "UNMEASURED"
#: An admissible docket larger than this is not parsed whole on a small box; the compiler's file
#: and the ledger still are, and the report says the docket was skipped.
MAX_DOCKET_BYTES = 400 * 1024 * 1024

#: The price-bar baseline every price-derived family reads.
PRICE = "price_bars"
#: Non-lake sources, by family. Anything else is price-derived.
FAMILY_SOURCE: dict[str, str] = {
    "cot_positioning": "cot", "macro_conditional": "macro_state",
    "event_reaction": "events_calendar",
    "carry": "swap_terms", "carry_risk_off": "swap_terms", "style_premia": "swap_terms",
    "liquidity_regime": "tick_tape", "orderflow_imbalance": "tick_tape",
    "spread_state": "tick_tape", "execution_state": "microstructure_surfaces",
    "analyst_revision_drift": "analyst_views", "analyst_cross_market_lead": "analyst_views",
}
#: Where each fixed source lives, relative to the desk, for the existence test.
FIXED_PATHS: dict[str, tuple[str, ...]] = {
    PRICE: ("data/universe",), "cot": ("data/cot", "data/cot_disagg", "data/cot_tff"),
    "macro_state": ("data/macro_state.json",), "events_calendar": ("data/events.jsonl",),
    "swap_terms": ("data/tape/contract_terms", "data/intelligence/broker_swaps"),
    "tick_tape": ("data/tape/ticks",),
    "microstructure_surfaces": ("reports/MICROSTRUCTURE_SURFACES.json",),
    "analyst_views": ("data/alpha_capture/analyst_views.jsonl",),
}
NAMED_KEYS = ("source", "pack_id", "series_key")
#: Families whose recipe `source`/`pack_id`/`series_key` names a data series (not a miner).
NAMED_FAMILIES = frozenset({"exogenous_conditioner", "alt_series_momentum", "alt_conditioned",
                            "alt_release_drift", "world_macro_state"})
#: A driver / peer instrument named on the recipe: the cell reads ANOTHER instrument's bars.
LINK_KEYS = ("driver_symbol", "cond_symbol", "bond_symbol", "risk_symbol", "leader")

_DECLARED: frozenset[str] | None = None


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _norm(sid: str) -> str:
    s = str(sid).strip()
    return s[3:] if s.startswith("fs_") else s


def _declared_families() -> frozenset[str]:
    global _DECLARED
    if _DECLARED is None:
        try:
            from mt5desk.families_orthogonal import FAMILY_INPUTS
            _DECLARED = frozenset(FAMILY_INPUTS)
        except Exception:
            _DECLARED = frozenset()
    return _DECLARED


def source_of(family: str, params: dict[str, Any] | None) -> tuple[str, bool]:
    """(source id, inferred). A named series wins; else the family's declared input."""
    p = params or {}
    fam = str(family or "")
    if fam in NAMED_FAMILIES:
        for k in NAMED_KEYS:
            v = p.get(k)
            if isinstance(v, str) and v.strip():
                return (f"world:{v}" if k == "series_key" else _norm(v)), False
    if fam in FAMILY_SOURCE:
        return FAMILY_SOURCE[fam], False
    return PRICE, fam not in _declared_families()


def eligible_universe(desk: Path = DESK) -> tuple[list[str], int, int]:
    """(eligible non-exotic statistical-lane instruments, exotics set aside, other set aside)."""
    from research import universe_policy as up
    reg = _json(desk / "data" / "universe" / "universe.json")
    names = sorted(reg) if isinstance(reg, dict) else []
    ok: list[str] = []
    exotic = other = 0
    for s in names:
        if up.is_exotic_symbol(s):
            exotic += 1
        elif up.lane(s) == up.HYPOTHESIS:
            ok.append(s)
        else:
            other += 1
    return ok, exotic, other


def _rows(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict):
        for k in ("hypotheses", "cells", "rows", "candidates", "docket"):
            if isinstance(doc.get(k), list):
                return [r for r in doc[k] if isinstance(r, dict)]
    return []


def load_cells(desk: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """(docket rows, paths read, notes). Both files; the judge's identity does the dedupe."""
    rows: list[dict[str, Any]] = []
    read: list[str] = []
    notes: list[str] = []
    for rel in ("data/hypotheses/admissible_docket.json", "data/hypotheses/miner_candidates.json"):
        p = desk / rel
        if not p.exists():
            notes.append(f"{rel} absent on this host")
            continue
        try:
            if p.stat().st_size > MAX_DOCKET_BYTES:
                notes.append(f"{rel} skipped: {p.stat().st_size >> 20} MB over the "
                             f"{MAX_DOCKET_BYTES >> 20} MB parse bound")
                continue
        except OSError:
            continue
        got = _rows(_json(p))
        if got:
            rows.extend(got)
            read.append(rel)
        else:
            notes.append(f"{rel} unreadable or holds no rows")
    return rows, read, notes


def judged_ids(desk: Path) -> tuple[set[str] | None, str, str]:
    """(cell ids with a real verdict | None, basis, why-unmeasured)."""
    led = desk / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
    if led.exists():
        seen: set[str] = set()
        try:
            with led.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(r, dict) or not r.get("cell"):
                        continue
                    if str(r.get("downstream_status") or "").startswith("NOT_RUN"):
                        continue
                    if r.get("passed") is not True and str(
                            r.get("terminal_gate") or "") in ("", "UNKNOWN"):
                        continue
                    seen.add(str(r["cell"]))
            return seen, "gate_verdict_ledger", ""
        except OSError:
            pass
    seen_doc = _json(desk / "data" / "hypotheses" / "gauntlet_seen_cells.json")
    if isinstance(seen_doc, dict):
        return set(seen_doc), "gauntlet_seen_cells", ""
    return None, "none", "gate_verdict_ledger.jsonl and gauntlet_seen_cells.json both absent"


def certified_cells(desk: Path) -> tuple[list[dict[str, Any]] | None, str]:
    out: dict[str, dict[str, Any]] = {}
    present = False
    for rel in ("reports/UNIVERSAL_SURVIVORS.json", "data/UNIVERSAL_SURVIVORS.canon.json"):
        d = _json(desk / rel)
        if not isinstance(d, dict) or not isinstance(d.get("survivors"), dict):
            continue
        present = True
        for key, v in d["survivors"].items():
            if isinstance(v, dict):
                out.setdefault(str(v.get("cell") or key), v)
    if not present:
        return None, "UNIVERSAL_SURVIVORS.json and canon both absent"
    return list(out.values()), ""


def _cell_family(cell: str, sym: str) -> str:
    """Family from a survivor's cell string: `SYM.family.params` or `SYM family ...`."""
    c = cell[9:] if cell.startswith("external.") else cell
    parts = c.split(".") if "." in c.split(" ")[0] else c.split(" ")
    return parts[1] if len(parts) > 1 and parts[0].split("@")[0] == sym else ""


def live_rows(desk: Path) -> tuple[list[dict[str, Any]] | None, str]:
    rows: list[dict[str, Any]] = []
    present = False
    sl = _json(desk / "data" / "sleeves.json")
    if isinstance(sl, dict) and isinstance(sl.get("sleeves"), list):
        present = True
        for s in sl["sleeves"]:
            if isinstance(s, dict) and str(s.get("status")) == "LIVE":
                rows.append({"symbol": str(s.get("symbol") or ""),
                             "family": str(s.get("family") or ""),
                             "params": s.get("params") or {}})
    cb = _json(desk / "data" / "CERT_BOOK_LIVE.json")
    if isinstance(cb, dict) and cb.get("enabled") is True:
        present = True
        fams = sorted(_declared_families(), key=len, reverse=True)
        for block in ("fusion", "e8", "ftmo"):
            b = cb.get(block)
            if not isinstance(b, dict):
                continue
            for key, frac in b.items():
                if isinstance(frac, (int, float)) and frac > 0:
                    fam = next((f for f in fams if f in str(key)), "")
                    rows.append({"symbol": str(key).split("_")[0], "family": fam, "params": {}})
    why = "" if present else "sleeves.json and CERT_BOOK_LIVE absent"
    return (rows if present else None), why


def existing_sources(desk: Path) -> dict[str, str]:
    """source id -> kind, for every source that EXISTS on this host."""
    out: dict[str, str] = {}
    reg = _json(desk / "data" / "asia_sources.json")
    for r in (reg.get("sources") if isinstance(reg, dict) else None) or []:
        if isinstance(r, dict) and r.get("id") and str(r.get("role") or "") != "transport":
            out[_norm(r["id"])] = "lake_pack"
    lake = desk / "data" / "lake" / "series"
    if lake.is_dir():
        for f in lake.iterdir():
            if f.suffix in (".parquet", ".csv"):
                out.setdefault(_norm(f.stem), "lake_series")
    wd = desk / "data" / "world_datasets"
    if wd.is_dir():
        for f in wd.iterdir():
            out.setdefault(f"world:{f.stem}", "world_dataset")
    for sid, paths in FIXED_PATHS.items():
        if any((desk / p).exists() for p in paths):
            out[sid] = "fixed"
    return out


def build(desk: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    desk = desk or DESK
    from research import universe_policy as up
    from research.frontier_identity import docket_cell_id
    eligible, n_exotic, n_other = eligible_universe(desk)
    elig = frozenset(eligible)
    rows, read, notes = load_cells(desk)
    judged, judged_basis, judged_why = judged_ids(desk)
    cert, cert_why = certified_cells(desk)
    live, live_why = live_rows(desk)
    exist = existing_sources(desk)

    mined: dict[str, set[str]] = defaultdict(set)
    jset: dict[str, set[str]] = defaultdict(set)
    reach_m: dict[str, set[str]] = defaultdict(set)
    reach_j: dict[str, set[str]] = defaultdict(set)
    cross: Counter[str] = Counter()
    by_id: dict[str, str] = {}
    inferred = skipped_exotic = skipped_lane = 0
    for r in rows:
        sym = str(r.get("symbol") or r.get("sym") or "")
        fam = str(r.get("family") or "")
        if not sym or not fam:
            continue
        if up.is_exotic_symbol(sym):
            skipped_exotic += 1
            continue
        if sym not in elig:
            skipped_lane += 1
            continue
        try:
            cid = docket_cell_id(r)
        except Exception:
            continue
        if cid in by_id:
            continue
        params = r.get("params") if isinstance(r.get("params"), dict) else {}
        src, inf = source_of(fam, params)
        by_id[cid] = src
        inferred += int(inf)
        mined[src].add(cid)
        reach_m[src].add(sym)
        if any(str(params.get(k) or "") not in ("", sym) for k in LINK_KEYS):
            cross[src] += 1
        if judged is not None and cid in judged:
            jset[src].add(cid)
            reach_j[src].add(sym)

    certd: dict[str, set[str]] | None = None
    cert_total = cert_exotic = 0
    cert_fam: Counter[str] = Counter()
    cert_src: Counter[str] = Counter()
    if cert is not None:
        certd = defaultdict(set)
        for v in cert:
            sym, cell = str(v.get("sym") or ""), str(v.get("cell") or "")
            cert_total += 1
            if up.is_exotic_symbol(sym):
                cert_exotic += 1
                continue
            cert_fam[_cell_family(cell, sym) or "unknown"] += 1
            c2 = cell[9:] if cell.startswith("external.") else cell
            src = by_id.get(c2) or by_id.get(cell)
            if src is None:
                src, _ = source_of(_cell_family(cell, sym), {})
            certd[src].add(cell)
            cert_src[src] += 1
    livd: dict[str, set[str]] | None = None
    if live is not None:
        livd = defaultdict(set)
        for i, r in enumerate(live):
            if up.is_exotic_symbol(r["symbol"]):
                continue
            src, _ = source_of(r["family"], r["params"])
            livd[src].add(f"{r['symbol']}|{r['family']}|{i}")

    mined_ok = bool(read)
    ids = sorted(set(exist) | set(mined) | set(certd or {}) | set(livd or {}))
    out_rows: list[dict[str, Any]] = []
    for sid in ids:
        unm: list[str] = []
        exists = sid in exist or sid in mined
        m = len(mined[sid]) if mined_ok else None
        if not mined_ok:
            unm.append("mined: no docket or compiler file on this host")
        j: int | None = len(jset[sid]) if (mined_ok and judged is not None) else None
        if judged is None:
            unm.append(f"judged: {judged_why}")
        c = len(certd[sid]) if certd is not None else None
        if certd is None:
            unm.append(f"certified: {cert_why}")
        lv = len(livd[sid]) if livd is not None else None
        if livd is None:
            unm.append(f"live: {live_why}")
        fault = None
        if m is not None and j is not None and m > 0 and j == 0:
            fault = "ZERO_JUDGED"
        elif m == 0 and sid in exist:
            fault = "NEVER_MINED"
        reached = len(reach_m[sid]) if mined_ok else None
        out_rows.append({
            "source": sid, "kind": exist.get(sid, "named_by_cells"), "exists": exists,
            "mined": m, "judged": j, "certified": c, "live": lv,
            "instruments_reached_mined": reached,
            "instruments_reached_judged": len(reach_j[sid]) if j is not None else None,
            "eligible_instruments": len(elig),
            "reach_ratio": (round(reached / len(elig), 4) if reached is not None and elig
                            else None),
            "unreached_sample": (sorted(elig - reach_m[sid])[:12] if mined_ok else None),
            "cross_asset_cells": cross[sid] if mined_ok else None,
            "judged_over_mined": round(j / m, 4) if j is not None and m else None,
            "certified_over_judged": round(c / j, 4) if c is not None and j else None,
            "live_over_certified": round(lv / c, 4) if lv is not None and c else None,
            "fault": fault is not None, "fault_reason": fault, "unmeasured": unm})
    faults = [r for r in out_rows if r["fault"]]
    status = "FAULT" if faults else (UNMEASURED if (not mined_ok or judged is None) else "OK")
    top = sorted((r for r in out_rows if r["mined"]), key=lambda r: -r["mined"])[:5]
    if cert is None:
        headline: dict[str, Any] = {"status": UNMEASURED, "non_exotic_certified": None,
                                    "total_certified": None, "exotic_share": None,
                                    "why": cert_why}
    else:
        headline = {
            "status": "MEASURED", "total_certified": cert_total,
            "exotic_certified": cert_exotic,
            "non_exotic_certified": cert_total - cert_exotic,
            "exotic_share": round(cert_exotic / cert_total, 4) if cert_total else None,
            "non_exotic_by_family": dict(cert_fam.most_common()),
            "non_exotic_by_source": dict(cert_src.most_common()),
            "rule": ("exotics are banned (universe_policy.is_exotic_symbol): counted here as "
                     "excluded, never targeted, never reached")}
    return {
        "schema": SCHEMA, "headline": headline,
        "at": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
        "status": status, "n_sources": len(out_rows), "n_faults": len(faults),
        "faults": [{"source": r["source"], "reason": r["fault_reason"]} for r in faults],
        "judged_basis": judged_basis, "inputs_read": read, "notes": notes,
        "eligible_universe": {"n": len(elig), "exotics_set_aside": n_exotic,
                              "other_lane_set_aside": n_other},
        "cells": {"distinct_eligible": len(by_id), "family_inferred_price_only": inferred,
                  "rows_exotic_set_aside": skipped_exotic,
                  "rows_off_lane_or_unlisted_set_aside": skipped_lane},
        "top_by_mined": [{k: r[k] for k in ("source", "mined", "judged", "certified", "live",
                                            "instruments_reached_mined")} for r in top],
        "sources": out_rows,
        "rule": ("UNMEASURED is never zero: an absent input leaves its column null and raises no "
                 "fault. ZERO_JUDGED = mined > 0 and judged == 0; NEVER_MINED = the source exists "
                 "here and no cell names it. Report only: it mints, judges and vetoes nothing."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    doc = build()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"source_conversion: {doc['status']} sources={doc['n_sources']} "
          f"faults={doc['n_faults']} judged_basis={doc['judged_basis']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
