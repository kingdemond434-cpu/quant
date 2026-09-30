#!/usr/bin/env python3
"""THE CONSUMER OF THE ALT-PROXIES EQUITY HAND-OFF: share-CFD cells in both lanes the order allows.

    python desks/mt5/research/alt_equity_handoff.py --once --budget-s 240
    python desks/mt5/research/alt_equity_handoff.py --once --dry-run     # measure, donate nothing

WHY (law III.16, unwired is a defect). `research/alt_proxies.py` writes
`data/digests/alt_proxies_equity_handoff.json` every hour: for each free alt-data series (Korea's
20-day exports, TSA throughput, GDELT Taiwan tone ...) the share CFDs it bears on and the declared
prior sign. Share CFDs never mint alt-proxy cells there -- the two-lane order -- and until this
organ nothing read the file, so the equity half of that data fed nothing.

THE TWO LANES, AND NOTHING ELSE (principal 2026-09-06, amended 2026-09-30). A share CFD may mint
only in the cross-sectional class books (`universe_policy.CROSS_SECTIONAL_FAMILIES`) or the news
lane's own families (`universe_policy.NEWS_LANE_FAMILIES`). Every cell here is one of those two,
and `proposer_common.donate` re-checks it at the door.

  (a) EVENT LANE -- `alt_release_drift` (mt5desk/family_alt_release.py). One cell per (series,
      share): follow each release whose |surprise_z| >= 1 in the direction sign(z) x declared
      prior, entered at the first bar opening after the release's first `available_time` on the
      broker clock, held five trading days.
  (b) CLASS BOOKS -- every class-book family the registry holds (`mt5desk.class_books` when #136
      is in the tree, else `families_cross_sectional`), at its first grid point, on each share,
      CONDITIONED on the hand-off series as a ranking input: the leg the prior favours is kept
      while the series' `pace` is on the prior's side, via the `alt:` conditioner and `side_mode`
      that `mt5desk.cell_modifiers` applies identically in the gauntlet, the clock and the
      executor. Two cells per (series, share, family): pace > 0 keeps the prior's side, pace < 0
      keeps the other.

WHAT IS DONATED, AND WHAT IS CHARGED. A cell is MEASURED (the family run on the share's own bars,
its firing counted exactly as `cross_sectional_breadth` counts it) at most once a day, and every
measured cell is a trial charged to the census: a pass that donates carries the count as the
discovery file's `tests_run`; a pass that donates nothing appends it to `null_pass_trials.jsonl`
(`alt_proxies._donate`, which `experiment_ledger` reads either way). A cell whose firing clears
the gauntlet's floor is donated once, through `proposer_common.donate` into
`data/intelligence/alt_equity_handoff/`. A cell that cannot be measured names what is missing
(the lake series, the share's bars) and is held, never donated to come back UNKNOWN.

THE DATASET IS REGISTERED. The hand-off is upserted into `data/data_registry.json` as
`alt_proxies_equity_handoff` (lifecycle INGESTED), so the D18 dataset-exploitation census (#155)
enrols it, and every donated row names it in `required_data` / `lineage`, which that census reads
to credit the cells to the dataset.

Artifact: `reports/ALT_EQUITY_HANDOFF.json`. UNMEASURED is an answer (L1.28a): an absent hand-off
is reported as absent, never as zero cells.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "alt_equity_handoff"
DATASET_KEY = "alt_proxies_equity_handoff"
HANDOFF = BASE / "data" / "digests" / "alt_proxies_equity_handoff.json"
REPORT = BASE / "reports" / "ALT_EQUITY_HANDOFF.json"
STATE = BASE / "data" / "alt_equity_handoff_state.json"
DATA_REGISTRY = BASE / "data" / "data_registry.json"
SERIES_DIR = BASE / "data" / "lake" / "series"
UNMEASURED = "UNMEASURED"

EVENT_FAMILY = "alt_release_drift"
#: The event cell's recipe. |surprise_z| >= 1 is the same extreme `alt_proxies` direct cells use.
EVENT_PARAMS: dict[str, Any] = {"column": "surprise_z", "threshold": 1.0, "side": 1,
                                "hold_days": 5, "atr_n": 20, "stop_atr": 3.0, "rr": 1.5}
#: The conditioner column: `pace` is the series' own signed momentum (alt_proxies' lake envelope),
#: the same axis its indirect cells condition certified parents on.
PACE = "pace"
#: The sealed gauntlet drops a daily series under 60 days; `cross_sectional_breadth.SEED_FLOOR`
#: (66) is that floor plus a margin, and it is the class-book floor here too.
SEED_FLOOR = 66


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
    os.replace(tmp, path)


def identity(symbol: str, family: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"s": symbol, "f": family, "p": params}, sort_keys=True,
                                     default=str).encode()).hexdigest()[:20]


# ------------------------------------------------------------------ the class-book registry
def class_book_registry() -> dict[str, Any]:
    """{families, grid, scoped, operator} from `mt5desk.class_books` (#136) when it is in the
    tree, else from `families_cross_sectional`, restricted to the families the two-lane order
    admits for a share CFD. The operator family (a conditioner over a base cell) is not a base."""
    from research import universe_policy as up
    try:
        from mt5desk import class_books as cb  # type: ignore[attr-defined,unused-ignore]
        fams, grid = dict(cb.FAMILIES), dict(cb.PARAM_GRID)
        scoped = dict(getattr(cb, "SCOPED", {}) or {})
        operator = str(getattr(cb, "OPERATOR", "") or "")
        basis = "mt5desk.class_books"
    except ImportError:
        from mt5desk import families_cross_sectional as xs
        fams, grid, scoped, operator = dict(xs.CROSS_SECTIONAL_FAMILIES), dict(xs.PARAM_GRID), \
            {}, ""
        basis = "mt5desk.families_cross_sectional"
    keep = {f: fn for f, fn in fams.items()
            if f in up.CROSS_SECTIONAL_FAMILIES and f != operator and grid.get(f)}
    return {"families": keep, "grid": grid, "scoped": scoped, "basis": basis}


def base_params(grid: dict[str, list[Any]]) -> dict[str, Any]:
    """The family's FIRST grid point (sorted keys): one base per family, not a search over it."""
    keys = sorted(grid)
    first = next(itertools.product(*(grid[k] for k in keys)), ())
    return dict(zip(keys, first, strict=True))


def applies(family: str, symbol: str, scoped: dict[str, Any]) -> bool:
    """True when `symbol` is a member of a class the family ranks within."""
    from research import universe_policy as up
    classes = scoped.get(family)
    try:
        if not classes:
            return up.peer_class(symbol) is not None
        return any(symbol in up.class_members(str(k)) for k in classes)
    except Exception:
        return False


# ------------------------------------------------------------------ minting
def _meta(source_id: str) -> dict[str, Any]:
    """The source's mechanism and culture fields from alt_proxies' own roster, UNMEASURED when
    the roster does not know the id (never invented here)."""
    try:
        from research import alt_proxies as ap
        src = ap.BY_ID.get(source_id)
    except Exception:
        src = None
    if src is None:
        blank: dict[str, Any] = dict.fromkeys(
            ("mechanism", "payer", "constraint", "source_culture", "failure_mode_hypothesis",
             "crowding_prior", "substitutes_for", "source_name"), UNMEASURED)
        return {**blank, "participant_structure": []}
    return {"mechanism": src.mechanism, "payer": src.payer, "constraint": src.constraint,
            "source_culture": src.source_culture,
            "participant_structure": list(src.participant_structure),
            "failure_mode_hypothesis": src.failure_mode_hypothesis,
            "crowding_prior": src.crowding_prior,
            "substitutes_for": src.substitutes_for or "", "source_name": src.name}


def mint(handoff: dict[str, Any], registry: dict[str, Any] | None = None
         ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every cell the hand-off's CURRENT contents imply, before any measurement: (cells, census).
    A row that is not `usable` (DEAD source, terms not confirmed) mints nothing and is counted."""
    reg = registry or class_book_registry()
    cells: list[dict[str, Any]] = []
    held: Counter = Counter()
    rows = handoff.get("rows") if isinstance(handoff.get("rows"), list) else []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if not r.get("usable"):
            why = "DEAD" if r.get("dead") else f"TERMS_{str(r.get('terms') or '?').upper()}"
            held[why] += len(r.get("shares") or {})
            continue
        lake = str(r.get("lake_file") or "")
        sid, series = str(r.get("source") or ""), str(r.get("series") or "")
        meta = _meta(sid)
        for sym, sign in sorted((r.get("shares") or {}).items()):
            sign = 1 if int(sign) > 0 else -1
            common = {"handoff_row": f"{sid}|{series}", "source_id": sid, "series": series,
                      "lake_file": lake, "prior_sign": sign, "meta": meta}
            ev = {"source": lake, "prior_sign": sign, **EVENT_PARAMS}
            cells.append({**common, "symbol": sym, "family": EVENT_FAMILY, "params": ev,
                          "lane": "event", "base": None, "mods": {}})
            for fam in sorted(reg["families"]):
                if not applies(fam, sym, reg["scoped"]):
                    held["CLASS_BOOK_SCOPE"] += 2
                    continue
                base = {"symbol": sym, **base_params(reg["grid"][fam])}
                for op, keep in (("gt", sign), ("lt", -sign)):
                    mods = {"conditioner": f"alt:{lake}:{PACE}:{op}:0",
                            "side_mode": "long" if keep > 0 else "short"}
                    cells.append({**common, "symbol": sym, "family": fam,
                                  "params": {**base, **mods}, "lane": "class_book",
                                  "base": base, "mods": mods})
    for c in cells:
        c["ident"] = identity(c["symbol"], c["family"], c["params"])
    census = {"handoff_rows": len(rows),
              "usable_rows": sum(1 for r in rows if isinstance(r, dict) and r.get("usable")),
              "cells": len(cells),
              "by_lane": dict(Counter(c["lane"] for c in cells)),
              "by_family": dict(sorted(Counter(c["family"] for c in cells).items())),
              "by_source": dict(sorted(Counter(c["source_id"] for c in cells).items())),
              "share_symbols": sorted({c["symbol"] for c in cells}),
              "not_minted": dict(held), "class_book_basis": reg["basis"],
              "class_book_families": sorted(reg["families"])}
    return cells, census


# ------------------------------------------------------------------ measurement
def _bars(symbol: str) -> Any:
    from research import cross_sectional_breadth as xsb
    return xsb._bars(symbol)


def _series_present(lake: str) -> bool:
    return any((SERIES_DIR / f"{lake}{s}").exists() for s in (".parquet", ".csv"))


def measure(cell: dict[str, Any], d: Any, reg: dict[str, Any]) -> dict[str, int]:
    """The cell's firing on the share's own bars, through the SAME calls the gauntlet makes: the
    family, then `cell_modifiers.apply` for the conditioner and side."""
    from research import cross_sectional_breadth as xsb
    if cell["lane"] == "event":
        from mt5desk.family_alt_release import family_alt_release_drift
        sigs = family_alt_release_drift(d, **cell["params"])
    else:
        from mt5desk import cell_modifiers as cm
        sigs = list(reg["families"][cell["family"]](d, **cell["base"]) or [])
        sigs = cm.apply(sigs, d, cell["mods"])
    return xsb.firing(list(sigs or []), d)


def floor_for(cell: dict[str, Any]) -> int:
    """Class books: SEED_FLOOR trade days. Events: enough holds to fill SEED_FLOOR daily rows."""
    if cell["lane"] == "event":
        return math.ceil(SEED_FLOOR / max(1, int(cell["params"]["hold_days"])))
    return SEED_FLOOR


def candidate(cell: dict[str, Any], firing: dict[str, int], handoff_sha: str,
              now: datetime) -> dict[str, Any]:
    m = cell["meta"]
    culture = {k: m.get(k) for k in ("source_culture", "participant_structure",
                                     "failure_mode_hypothesis", "crowding_prior")}
    arrow = "+" if cell["prior_sign"] > 0 else "-"
    if cell["lane"] == "event":
        mech = (f"{m.get('mechanism')}. Each release of {cell['series']} ({cell['source_id']}) "
                f"with |surprise_z|>=1 moves {cell['symbol']} in the direction of the surprise x "
                f"the declared prior ({arrow}); the payer is the holder who does not read the "
                "release, entered after its first available_time on the broker clock")
        title = f"{EVENT_FAMILY} {cell['symbol']} <- {cell['source_id']}/{cell['series']}"
        falsifier = ("the post-release drift on shifted (placebo) release dates is as large as "
                     "on the real ones, or the realised sign contradicts the declared prior")
    else:
        mech = (f"{cell['family']} leg on {cell['symbol']}, kept only on the side the "
                f"{cell['series']} ({cell['source_id']}) prior favours while its pace is "
                f"{'rising' if ':gt:' in cell['mods']['conditioner'] else 'falling'}: "
                f"{m.get('mechanism')}")
        title = (f"{cell['family']} {cell['symbol']} | {cell['source_id']}/{cell['series']} "
                 f"{cell['mods']['conditioner'].rsplit(':', 3)[1]} {cell['mods']['side_mode']}")
        falsifier = ("the conditioned leg earns no more than the unconditioned class-book leg "
                     "on the same share over the same dates")
    lake_rel = f"desks/mt5/data/lake/series/{cell['lake_file']}.csv"
    return {
        "source": SOURCE, "kind": "hypothesis", "symbol": cell["symbol"],
        "symbols": [cell["symbol"]], "family": cell["family"], "params": cell["params"],
        "cell": cell["ident"], "url": "", "title": title[:120], "mechanism": mech[:400],
        "payer": m.get("payer"), "constraint": m.get("constraint"), **culture,
        "prior_sign": cell["prior_sign"], "falsifier": falsifier,
        "available_time": now.isoformat(timespec="seconds"),
        "event_time": now.isoformat(timespec="seconds"),
        "required_data": [DATASET_KEY, lake_rel],
        "lineage": {"dataset": DATASET_KEY, "source": cell["source_id"],
                    "series": cell["series"], "lake_file": cell["lake_file"],
                    "lane": cell["lane"]},
        "provenance": {"organ": "research/alt_equity_handoff.py", "use": cell["lane"],
                       "handoff": "desks/mt5/data/digests/alt_proxies_equity_handoff.json",
                       "handoff_sha256": handoff_sha, "handoff_row": cell["handoff_row"],
                       "source_id": cell["source_id"], "series": cell["series"],
                       "prior_sign_basis": "declared prior, untested",
                       "substitutes_for": m.get("substitutes_for"),
                       "source_name": m.get("source_name"), **culture},
        "evidence": {"firing": firing, "floor_trade_days": floor_for(cell),
                     "screen": ("firing only (distinct signal days, lower bound on trade days, "
                                "counted as cross_sectional_breadth counts them); the ten gates "
                                "judge the rest")}}


# ------------------------------------------------------------------ registry row
def registry_row(handoff: dict[str, Any], ingested: str) -> dict[str, Any]:
    series = sorted({str(r.get("lake_file")) for r in handoff.get("rows") or []
                     if isinstance(r, dict) and r.get("lake_file")})
    return {"lifecycle": "INGESTED",
            "source": ("research/alt_proxies.py equity hand-off: free alt-data substitutes "
                       "(PIT lake series) mapped to the share CFDs they bear on"),
            "format": "json", "path": "data/digests/alt_proxies_equity_handoff.json",
            "ingested": ingested, "series": series,
            "consumer": "research/alt_equity_handoff.py (event lane + class books)",
            "provenance": "desks/mt5/research/alt_proxies.py equity_handoff()"}


def register_dataset(handoff: dict[str, Any], now: datetime, path: Path | None = None
                     ) -> dict[str, Any]:
    """Make sure data_registry.json carries the hand-off so the D18 census enrols it.

    The registry is a HAND-KEPT file, so this organ never reformats it: when the row is present
    it is only READ (a series list that no longer matches the hand-off is reported as drift,
    never rewritten); when it is absent the row is INSERTED as text before the `datasets`
    object closes, leaving every other byte as it was."""
    p = path or DATA_REGISTRY
    try:
        text = p.read_text("utf-8")
        doc = json.loads(text)
    except (OSError, ValueError):
        doc, text = None, ""
    if not isinstance(doc, dict) or not isinstance(doc.get("datasets"), dict):
        return {"status": UNMEASURED, "why": f"{p.name} absent or unreadable: not registered"}
    prior = doc["datasets"].get(DATASET_KEY)
    if isinstance(prior, dict):
        want = registry_row(handoff, str(prior.get("ingested") or ""))["series"]
        missing = sorted(set(want) - set(prior.get("series") or []))
        return {"status": "REGISTERED", "changed": False, "key": DATASET_KEY,
                "series_not_in_registry_row": missing}
    body = json.dumps({DATASET_KEY: registry_row(handoff, now.date().isoformat())}, indent=2)
    inner = "\n".join("  " + ln for ln in body.splitlines()[1:-1])
    stripped = text.rstrip()
    cut = stripped.rstrip("}").rstrip()        # the file ends `...}\n  }\n}`: datasets, then root
    if not stripped.endswith("}") or not cut.endswith("}"):
        return {"status": UNMEASURED, "why": f"{p.name} does not end with the datasets object"}
    head = cut[:-1].rstrip()
    sep = "," if not head.endswith("{") else ""
    out = f"{head}{sep}\n{inner}\n  }}\n}}\n"
    try:
        json.loads(out)
    except ValueError:
        return {"status": UNMEASURED, "why": "inserting the row would not parse; not written"}
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(out, "utf-8")
    os.replace(tmp, p)
    return {"status": "REGISTERED", "changed": True, "key": DATASET_KEY}


# ------------------------------------------------------------------ the pass
def run(*, budget_s: float = 240.0, dry_run: bool = False, now: datetime | None = None,
        handoff_path: Path | None = None) -> dict[str, Any]:
    started = time.monotonic()
    now = now or _now()
    hp = handoff_path or HANDOFF
    try:
        raw = hp.read_bytes()
        handoff = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        rep = {"at": now.isoformat(timespec="seconds"), "organ": SOURCE, "status": UNMEASURED,
               "why": f"hand-off {hp.name} unreadable ({type(exc).__name__}): no cells minted, "
                      "none claimed"}
        if not dry_run:
            _atomic(REPORT, rep)
        return rep
    sha = hashlib.sha256(raw).hexdigest()
    reg = class_book_registry()
    cells, census = mint(handoff, reg)
    state = _read(STATE)
    state = state if isinstance(state, dict) and isinstance(state.get("cells"), dict) \
        else {"cells": {}}
    today = now.date().isoformat()
    held: Counter = Counter()
    by_family: Counter = Counter()
    measured = 0
    cands: list[dict[str, Any]] = []
    bars_cache: dict[str, Any] = {}
    stopped = "all cells visited"
    for cell in cells:
        prior = state["cells"].get(cell["ident"]) or {}
        if prior.get("donated_at"):
            held["ALREADY_DONATED"] += 1
            continue
        if prior.get("day") != today:
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached; resumes next pass"
                held["BUDGET"] += 1
                continue
            if not _series_present(cell["lake_file"]):
                held["SERIES_ABSENT"] += 1
                continue
            if cell["symbol"] not in bars_cache:
                bars_cache[cell["symbol"]] = _bars(cell["symbol"])
            d = bars_cache[cell["symbol"]]
            if d is None:
                held["BARS_ABSENT"] += 1
                continue
            try:
                got = measure(cell, d, reg)
            except Exception as exc:
                held[f"ERROR:{type(exc).__name__}"] += 1
                continue
            prior = {**got, "day": today, "family": cell["family"], "symbol": cell["symbol"]}
            state["cells"][cell["ident"]] = prior
            measured += 1
            by_family[cell["family"]] += 1
        if int(prior.get("trade_days_lb") or 0) >= floor_for(cell):
            cands.append(candidate(cell, {k: int(prior.get(k) or 0)
                                          for k in ("signal_days", "trade_days_lb")}, sha, now))
        else:
            held["UNDER_FLOOR"] += 1
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_TO_CHARGE"}
    registration: dict[str, Any] = {"status": "DRY_RUN"}
    if not dry_run:
        registration = register_dataset(handoff, now)
        if cands or measured:
            from research import alt_proxies as ap
            donation = ap._donate(ap.DEFAULT_PATHS, SOURCE, cands, measured, dict(by_family),
                                  now)
            if donation.get("path"):
                at = now.isoformat(timespec="seconds")
                for c in cands:
                    state["cells"].setdefault(str(c["cell"]), {})["donated_at"] = at
        _atomic(STATE, state)
    donated_total = sum(1 for v in state["cells"].values() if v.get("donated_at"))
    rep = {
        "at": now.isoformat(timespec="seconds"), "organ": SOURCE, "status": "OK",
        "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2),
        "handoff": {"path": "desks/mt5/data/digests/alt_proxies_equity_handoff.json",
                    "sha256": sha, "rows": census["handoff_rows"],
                    "usable_rows": census["usable_rows"]},
        "minted": census,
        "measured_this_pass": measured, "trials_charged_this_pass": 0 if dry_run else measured,
        "candidates_this_pass": len(cands),
        "donated_this_pass": int(donation.get("donated") or 0),
        "donated_total": donated_total,
        "held": dict(held),
        "donation": donation, "dataset_registration": registration,
        "rule": ("share CFDs mint only in CROSS_SECTIONAL_FAMILIES (conditioned class-book legs) "
                 "or the news lane (alt_release_drift); every measured cell is charged to the "
                 "census, a cell is donated once when its firing clears the floor, and a cell "
                 "that cannot be measured names the missing input"),
    }
    if not dry_run:
        _atomic(REPORT, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(budget_s=a.budget_s, dry_run=a.dry_run)
    if rep.get("status") != "OK":
        print(f"alt_equity_handoff: {rep.get('status')} -- {rep.get('why')}")
        return 0
    m = rep["minted"]
    print(f"alt_equity_handoff: {m['cells']} cells minted from {m['usable_rows']}/"
          f"{m['handoff_rows']} usable rows {m['by_lane']}; measured {rep['measured_this_pass']},"
          f" donated {rep['donated_this_pass']} (total {rep['donated_total']}); held "
          f"{rep['held']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
