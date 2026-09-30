#!/usr/bin/env python3
"""THE CONSUMER OF THE ALT-PROXIES EQUITY HAND-OFF: share-CFD legs of true cross-sectional books.

    python desks/mt5/research/alt_equity_handoff.py --once --budget-s 240
    python desks/mt5/research/alt_equity_handoff.py --once --dry-run     # measure, charge nothing

WHY (law III.16, unwired is a defect). `research/alt_proxies.py` writes
`data/digests/alt_proxies_equity_handoff.json` every hour: for each free alt-data series (Korea's
20-day exports, TSA throughput, GDELT Taiwan tone ...) the share CFDs it bears on and the declared
prior sign. Share CFDs never mint alt-proxy cells there -- the two-lane order -- and until this
organ nothing read the file, so the equity half of that data fed nothing.

ONE LANE, THE CLASS BOOKS (principal 2026-09-30 11:29, and the coordinator's ruling the same day).
A macro alt-data release is not company news, so it is NOT the news lane's (`alt_release_drift`
was taken off `universe_policy.NEWS_LANE_FAMILIES` and retired). Its reaction is traded the way
the order admits for a share: RANKED ACROSS THE EQUITY PEER CLASS ON THE SAME DATE
(`mt5desk.families_alt_exposure`, in `universe_policy.CROSS_SECTIONAL_FAMILIES`). Each cell is one
share's LEG of a long-top / short-bottom book -- the class-book pattern of #136 -- so the union of
the legs is a market-neutral book on the DIFFERENCE between names' alt-data news, never a
single-name bet on a single series.

  alt_exposure_pace_book     each mapped share's prior-signed, self-standardised series pace
  alt_exposure_release_book  each mapped share's prior-signed latest release surprise_z

Cells: every share the hand-off's USABLE rows map, in the equity class, x each family x each point
of that family's grid (one point each today). A share the hand-off does not map is not a leg.

TRIALS ARE CHARGED ONCE PER CELL, EVER. A cell is MEASURED (its firing, counted exactly as
`cross_sectional_breadth` counts it) at most once a day, but it is CHARGED to the trial census only
the first time: `data/alt_equity_handoff_charged.json` is a persisted ledger of charged cell keys
that only ratchets up (never shrinks, never rewritten from a smaller set). Re-measuring a known
cell daily used to charge it daily -- ~66k trials a year from 182 hypotheses -- which is a false
multiple-testing bill paid by every other cell on the desk. A cell's charge key is its identity
PLUS the book's fingerprint (the sorted (share, series, sign) map), because a book whose
membership changed is a different hypothesis and is charged again. The charge lands as the
discovery file's `tests_run` when the pass donates, else in `null_pass_trials.jsonl`
(`experiment_ledger` reads both); keys enter the ledger only after their charge landed.

A cell whose firing clears the gauntlet's floor is donated once, through
`proposer_common.donate` into `data/intelligence/alt_equity_handoff/`. A cell that cannot be
measured names what is missing (the lake series, the share's bars) and is held.

THE DATASET IS REGISTERED. The hand-off is upserted into `data/data_registry.json` as
`alt_proxies_equity_handoff` (lifecycle INGESTED), so the D18 dataset-exploitation census (#155)
enrols it, and every donated row names it in `required_data` / `lineage`.

Artifact: `reports/ALT_EQUITY_HANDOFF.json`. UNMEASURED is an answer (L1.28a): an absent hand-off
is reported as absent, never as zero cells.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
#: The ratchet: every cell key ever charged to the trial census. Only grows.
CHARGED = BASE / "data" / "alt_equity_handoff_charged.json"
DATA_REGISTRY = BASE / "data" / "data_registry.json"
SERIES_DIR = BASE / "data" / "lake" / "series"
UNMEASURED = "UNMEASURED"
LANE = "class_book"
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


# ------------------------------------------------------------------ the books
def book_registry() -> dict[str, Any]:
    """{families, grid, basis}: the alt-exposure class books, restricted to the families the
    two-lane order admits for a share CFD (every one of them, by the pin test)."""
    from mt5desk import class_books as cb
    from mt5desk import families_alt_exposure as alt

    from research import universe_policy as up
    fams = {f: fn for f, fn in alt.ALT_EXPOSURE_FAMILIES.items()
            if f in up.CROSS_SECTIONAL_FAMILIES and cb.DEDICATED.get(f) == alt.SEEDED_BY}
    return {"families": fams, "grid": {f: cb.grid(f, alt.KLASS) for f in fams},
            "klass": alt.KLASS, "basis": "mt5desk.families_alt_exposure"}


def applies(symbol: str, klass: str) -> bool:
    """True when `symbol` is ranked in `klass` (the equity peer class)."""
    from research import universe_policy as up
    try:
        return up.peer_class(symbol) == klass
    except Exception:
        return False


def fingerprint(legs: dict[str, list[dict[str, Any]]]) -> str:
    """The book's membership: sorted (share, lake series, prior sign). A different map is a
    different book, hence a different hypothesis and a fresh charge."""
    flat = sorted((s, str(l["lake_file"]), int(l["prior_sign"]))
                  for s, ls in legs.items() for l in ls)
    return hashlib.sha256(json.dumps(flat).encode()).hexdigest()[:16]


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
    A row that is not `usable` (DEAD source, terms not confirmed) maps nothing and is counted."""
    reg = registry or book_registry()
    held: Counter = Counter()
    rows = handoff.get("rows") if isinstance(handoff.get("rows"), list) else []
    legs: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        if not r.get("usable"):
            why = "DEAD" if r.get("dead") else f"TERMS_{str(r.get('terms') or '?').upper()}"
            held[why] += len(r.get("shares") or {})
            continue
        sid, series = str(r.get("source") or ""), str(r.get("series") or "")
        for sym, sign in sorted((r.get("shares") or {}).items()):
            legs.setdefault(str(sym), []).append(
                {"source_id": sid, "series": series, "lake_file": str(r.get("lake_file") or ""),
                 "prior_sign": 1 if int(sign) > 0 else -1, "handoff_row": f"{sid}|{series}"})
    book = fingerprint(legs)
    cells: list[dict[str, Any]] = []
    for sym in sorted(legs):
        if not applies(sym, reg["klass"]):
            held["NOT_IN_EQUITY_CLASS"] += len(reg["families"])
            continue
        first = legs[sym][0]
        for fam in sorted(reg["families"]):
            for point in reg["grid"][fam]:
                params = {"symbol": sym, **point}
                ident = identity(sym, fam, params)
                cells.append({"symbol": sym, "family": fam, "params": params, "lane": LANE,
                              "legs": legs[sym], "source_id": first["source_id"],
                              "series": first["series"], "lake_file": first["lake_file"],
                              "prior_sign": first["prior_sign"], "meta": _meta(first["source_id"]),
                              "ident": ident, "charge_key": f"{ident}:{book}"})
    census = {"handoff_rows": len(rows),
              "usable_rows": sum(1 for r in rows if isinstance(r, dict) and r.get("usable")),
              "cells": len(cells), "book_fingerprint": book,
              "book_members": sorted(legs),
              "by_lane": dict(Counter(c["lane"] for c in cells)),
              "by_family": dict(sorted(Counter(c["family"] for c in cells).items())),
              "share_symbols": sorted({c["symbol"] for c in cells}),
              "not_minted": dict(held), "class_book_basis": reg["basis"],
              "class_book_families": sorted(reg["families"])}
    return cells, census


# ------------------------------------------------------------------ the charge ratchet
def load_charged(path: Path | None = None) -> tuple[dict[str, Any], str]:
    """(ledger, status). An unreadable ledger is set aside, never overwritten by a smaller one:
    every cell then charges again, which over-charges (the conservative side) rather than
    losing a charge."""
    p = path or CHARGED
    if not p.exists():
        return {"charged": {}}, "ABSENT (first pass)"
    doc = _read(p)
    if isinstance(doc, dict) and isinstance(doc.get("charged"), dict):
        return doc, "OK"
    aside = p.with_name(f"{p.name}.unreadable-{int(time.time())}")
    try:
        os.replace(p, aside)
    except OSError:
        pass
    return {"charged": {}}, f"UNREADABLE: set aside as {aside.name}; every cell charges again"


def save_charged(ledger: dict[str, Any], new: dict[str, dict[str, Any]],
                 path: Path | None = None) -> dict[str, Any]:
    """Union `new` into the ledger and write it. The written set is a SUPERSET of the one on
    disk, checked just before the write -- the ledger only ratchets up."""
    p = path or CHARGED
    on_disk = _read(p)
    have = dict(on_disk.get("charged") or {}) if isinstance(on_disk, dict) and \
        isinstance(on_disk.get("charged"), dict) else {}
    merged = {**have, **dict(ledger.get("charged") or {})}
    for k, v in new.items():
        merged.setdefault(k, v)
    if not set(have) <= set(merged):                          # pragma: no cover - by build
        raise RuntimeError("charged ledger would shrink; refusing to write")
    doc = {"rule": ("every alt_equity_handoff cell key ever charged to the trial census; a key "
                    "is charged once, and this set only grows"),
           "count": len(merged), "charged": dict(sorted(merged.items()))}
    _atomic(p, doc)
    return doc


def charge(new_trials: int, by_family: dict[str, int], cands: list[dict[str, Any]],
           now: datetime) -> dict[str, Any]:
    """Donate the candidates with `tests_run` = the cells charged for the FIRST time this pass
    (0 when every candidate was charged in an earlier pass), or, with nothing donated, append
    the new trials to the null-pass ledger. Exactly one carries them."""
    from research import alt_proxies as ap
    res: dict[str, Any] = {"donated": 0, "path": None, "status": "NOTHING_TO_CHARGE"}
    if cands:
        try:
            from research import proposer_common as pc
            path = pc.donate(SOURCE, cands, int(new_trials))
            res = {**pc.donation_counts(), "path": str(path) if path else None,
                   "status": "DONATED" if path else "REFUSED_AT_DOOR"}
            if path:
                res["trials_charged_via"] = "discovery file tests_run"
        except Exception as exc:
            res = {"donated": 0, "path": None, "status": "ERROR",
                   "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    if new_trials > 0 and not res.get("path"):
        row = {"at": now.isoformat(timespec="seconds"), "source": SOURCE,
               "tests_run": int(new_trials),
               "by_family": {k: int(v) for k, v in sorted(by_family.items()) if v},
               "why": "first-time cells charged once; no discovery file carried them this pass"}
        try:
            null = ap.DEFAULT_PATHS.null_trials
            null.parent.mkdir(parents=True, exist_ok=True)
            with null.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            res["null_trials_charged"] = int(new_trials)
            res["trials_charged_via"] = "null_pass_trials.jsonl"
        except OSError as exc:
            res["null_trials_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    res["landed"] = bool(res.get("path") or res.get("null_trials_charged") or new_trials == 0)
    return res


# ------------------------------------------------------------------ measurement
def _bars(symbol: str) -> Any:
    from research import cross_sectional_breadth as xsb
    return xsb._bars(symbol)


def _series_present(lake: str) -> bool:
    return any((SERIES_DIR / f"{lake}{s}").exists() for s in (".parquet", ".csv"))


def measure(cell: dict[str, Any], d: Any, reg: dict[str, Any]) -> dict[str, int]:
    """The leg's firing on the share's own bars, through the SAME call the gauntlet makes."""
    from research import cross_sectional_breadth as xsb
    sigs = list(reg["families"][cell["family"]](d, **cell["params"]) or [])
    return xsb.firing(sigs, d)


def floor_for(cell: dict[str, Any]) -> int:
    return SEED_FLOOR


def candidate(cell: dict[str, Any], firing: dict[str, int], handoff_sha: str,
              now: datetime) -> dict[str, Any]:
    m = cell["meta"]
    culture = {k: m.get(k) for k in ("source_culture", "participant_structure",
                                     "failure_mode_hypothesis", "crowding_prior")}
    series = ", ".join(f"{l['source_id']}/{l['series']} ({'+' if l['prior_sign'] > 0 else '-'})"
                       for l in cell["legs"])
    what = ("pace" if cell["family"] == "alt_exposure_pace_book" else "release surprise")
    mech = (f"{cell['symbol']}'s leg of the equity-class book ranked on prior-signed alt-data "
            f"{what} ({series}): long while it ranks in the class's top, short in its bottom, "
            f"on the same date. {m.get('mechanism')}")
    title = f"{cell['family']} {cell['symbol']} <- {series}"
    falsifier = ("the long-top / short-bottom book earns nothing over the same dates, or the "
                 "leg's realised sign contradicts the rank on shifted (placebo) release dates")
    lakes = [f"desks/mt5/data/lake/series/{l['lake_file']}.csv" for l in cell["legs"]]
    return {
        "source": SOURCE, "kind": "hypothesis", "symbol": cell["symbol"],
        "symbols": [cell["symbol"]], "family": cell["family"], "params": cell["params"],
        "cell": cell["ident"], "url": "", "title": title[:120], "mechanism": mech[:400],
        "payer": m.get("payer"), "constraint": m.get("constraint"), **culture,
        "prior_sign": cell["prior_sign"], "falsifier": falsifier,
        "available_time": now.isoformat(timespec="seconds"),
        "event_time": now.isoformat(timespec="seconds"),
        "required_data": [DATASET_KEY, *lakes],
        "lineage": {"dataset": DATASET_KEY, "source": cell["source_id"],
                    "series": cell["series"], "lake_file": cell["lake_file"],
                    "lane": cell["lane"], "legs": cell["legs"]},
        "provenance": {"organ": "research/alt_equity_handoff.py", "use": cell["lane"],
                       "handoff": "desks/mt5/data/digests/alt_proxies_equity_handoff.json",
                       "handoff_sha256": handoff_sha, "handoff_row": cell["legs"][0]["handoff_row"],
                       "charge_key": cell["charge_key"],
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
            "consumer": "research/alt_equity_handoff.py (cross-sectional alt-exposure class books)",
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
    cut = stripped[:-1].rstrip()                # drop the root's `}`; datasets' `}` is next
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
    reg = book_registry()
    cells, census = mint(handoff, reg)
    state = _read(STATE)
    state = state if isinstance(state, dict) and isinstance(state.get("cells"), dict) \
        else {"cells": {}}
    ledger, ledger_status = load_charged()
    charged_before = len(ledger["charged"])
    today = now.date().isoformat()
    held: Counter = Counter()
    measured = 0
    new_charges: dict[str, dict[str, Any]] = {}
    new_by_family: Counter = Counter()
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
            absent = [l["lake_file"] for l in cell["legs"] if not _series_present(l["lake_file"])]
            if len(absent) == len(cell["legs"]):
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
            key = cell["charge_key"]
            if key not in ledger["charged"] and key not in new_charges:
                new_charges[key] = {"at": now.isoformat(timespec="seconds"),
                                    "family": cell["family"], "symbol": cell["symbol"]}
                new_by_family[cell["family"]] += 1
        if int(prior.get("trade_days_lb") or 0) >= floor_for(cell):
            cands.append(candidate(cell, {k: int(prior.get(k) or 0)
                                          for k in ("signal_days", "trade_days_lb")}, sha, now))
        else:
            held["UNDER_FLOOR"] += 1
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_TO_CHARGE"}
    registration: dict[str, Any] = {"status": "DRY_RUN"}
    charged_now = 0
    if not dry_run:
        registration = register_dataset(handoff, now)
        if cands or new_charges:
            donation = charge(len(new_charges), dict(new_by_family), cands, now)
            if donation.get("path"):
                at = now.isoformat(timespec="seconds")
                for c in cands:
                    state["cells"].setdefault(str(c["cell"]), {})["donated_at"] = at
            if donation.get("landed") and new_charges:
                ledger = save_charged(ledger, new_charges)
                charged_now = len(new_charges)
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
        "measured_this_pass": measured,
        "trials_charged_this_pass": charged_now,
        "trials": {"ledger": "desks/mt5/data/alt_equity_handoff_charged.json",
                   "ledger_status": ledger_status, "charged_before": charged_before,
                   "charged_after": len(ledger["charged"]) if not dry_run else charged_before,
                   "first_time_this_pass": len(new_charges),
                   "remeasured_not_recharged": measured - len(new_charges),
                   "rule": "each cell key is charged once, ever; the ledger only grows"},
        "candidates_this_pass": len(cands),
        "donated_this_pass": int(donation.get("donated") or 0),
        "donated_total": donated_total,
        "held": dict(held),
        "donation": donation, "dataset_registration": registration,
        "rule": ("share CFDs mint only in CROSS_SECTIONAL_FAMILIES: each cell is one leg of an "
                 "equity-class book ranked on the hand-off's prior-signed alt-data reading on the "
                 "same date; a cell is charged to the census once, donated once when its firing "
                 "clears the floor, and a cell that cannot be measured names the missing input"),
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
          f"{m['handoff_rows']} usable rows {m['by_family']}; measured "
          f"{rep['measured_this_pass']}, charged {rep['trials_charged_this_pass']} new, donated "
          f"{rep['donated_this_pass']} (total {rep['donated_total']}); held {rep['held']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
