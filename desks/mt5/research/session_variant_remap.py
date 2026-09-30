"""DEAD SESSION VARIANTS ALREADY IN THE DOCKET: found, marked, and replaced by cells that can fire.

WHY THIS EXISTS (2026-09-30, Tier S). The producers now consult the firing-hours oracle
(`libs/research/family_firing.py`) before minting an `asia` / `london` / `ny` variant, but the
docket the sealed judge reads already holds every variant minted before that: 21% of the judge's
UNKNOWN verdicts were session variants of families that only fire at one hour, a filter window
that holds no signal by construction. The docket is BOX STATE (`external_survivors.json` is
written by the merge and acknowledged by the judge) and is never rewritten here or on origin.

WHAT ONE PASS DOES, bounded by rows and by seconds:
  1. streams the docket and collects every session variant;
  2. measures the oracle keys it has never measured (cache `data/family_firing_hours.json`,
     versioned), within `--measure-s`;
  3. classifies each variant LIVE / LIVE_FILTER_ONLY / SESSION_TZ_MISMATCH / DEAD / UNMEASURED.
     DEAD needs BOTH clocks empty (never on today's server-hour filter, never in the market's own
     session); UNMEASURED is never DEAD; and the evidence guard (`family_firing.protected`: the
     certificate canon, the judge's verdict ledger, the docket's own net verdicts) turns any DEAD
     answer on a certified, passed or net-positive cell into PROTECTED_BY_EVIDENCE. Only DEAD is
     remapped; LIVE_FILTER_ONLY trades as the desk runs today and is never marked or sorted last;
  4. writes every DEAD variant to the sidecar `data/hypotheses/DEAD_SESSION_VARIANTS.jsonl`, with
     the hours its family fires and its stand-in -- the file a feeder (the cache warmer, the
     two-stage judge) reads to skip a slot it would otherwise spend on an empty signal list;
  5. donates each stand-in through the ONE registry door (`libs.moat.registry.enqueue_candidate`,
     de-duplicating on content hash, so a re-run adds nothing twice). Each stand-in is a NEW cell,
     charged to the trial census when the judge reads it like every other cell;
  6. publishes `reports/SESSION_VARIANT_REMAP.json`: dead found, remapped, UNMEASURED, by family.

NOTHING IS REMOVED. The dead variant stays in the docket; the sidecar is a mark, not a deletion,
and the sealed judge's own order is untouched (its skip is a patch under
/mnt/project-files/patches/session_variants/, for the principal).

    python desks/mt5/research/session_variant_remap.py --once --budget-s 240
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import family_firing as ff  # noqa: E402

DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
SIDECAR = BASE / "data" / "hypotheses" / "DEAD_SESSION_VARIANTS.jsonl"
REPORT = BASE / "reports" / "SESSION_VARIANT_REMAP.json"
ORIGIN = "session_variant_remap"
#: Docket rows read per pass. The box's docket passed 1.5m rows; a pass that reads them all is
#: fine at this cost (one decode, no build), and a cap keeps a runaway docket from binding the leg.
MAX_ROWS = 3_000_000
#: Stand-ins donated per pass; the registry door de-duplicates, so the rest arrive next hour.
MAX_DONATE = 20_000
CULTURE_KEYS = ("source_culture", "participant_structure", "failure_mode_hypothesis",
                "crowding_prior")
SEALED_NEED = ("/mnt/project-files/patches/session_variants/: the sealed sort in "
               "external_gauntlet.main cannot read DEAD_SESSION_VARIANTS.jsonl; the patch there "
               "sorts a dead variant last (never drops it). The two-stage judge "
               "(claude/two-stage-judge) should read the sidecar in stage 0 and spend no build "
               "on a listed genome_id.")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _ident(symbol: str, family: str, params: dict) -> bytes:
    raw = json.dumps([symbol, family, params], sort_keys=True, default=str,
                     separators=(",", ":"))
    return hashlib.blake2b(raw.encode(), digest_size=10).digest()


def _culture(row: dict, family: str, dead: str, home: str,
             remap: str = "") -> dict[str, str]:
    """The parent's culture provenance, carried; UNMEASURED where the parent had none. The
    failure-mode sentence is written for the stand-in when the parent carried none."""
    out = {k: str(row.get(k) or "") for k in CULTURE_KEYS}
    out["source_culture"] = out["source_culture"] or ff.UNMEASURED
    out["participant_structure"] = out["participant_structure"] or ff.UNMEASURED
    out["crowding_prior"] = out["crowding_prior"] or ff.UNMEASURED
    if remap == "reanchored":
        why = (f"{family}'s hour is re-anchored to the {home} market's own open, so it fails when "
               f"the order flow at that open stops resembling the flow at the hour the rule was "
               f"written for, not on the original session's calendar.")
    elif remap == "rehomed":
        why = (f"{family} never fires in {dead}; its stand-in trades the rule only where it does "
               f"fire ({home}), so it fails when {home}'s participants stop supplying the flow the "
               f"rule reads, not when {dead}'s do.")
    else:
        why = (f"{family} in {dead} is dead only on the server-hour clock; it fails with {dead}'s "
               f"own participants once the filter reads the market clock.")
    out["failure_mode_hypothesis"] = out["failure_mode_hypothesis"] or why
    return out


def scan(docket: Path = DOCKET, *, max_rows: int = MAX_ROWS,
         guard: dict | None = None) -> tuple[list[dict], set[bytes], dict[str, int]]:
    """(session variant rows, identity of every docket cell, census) in one streaming pass. Every
    row's own net verdict is noted in `guard` on the way past."""
    variants: list[dict] = []
    idents: set[bytes] = set()
    census = {"rows": 0, "session_variants": 0, "truncated": 0}
    if not docket.exists():
        return variants, idents, census
    for row in ff.iter_json_array(docket):
        if census["rows"] >= max_rows:
            census["truncated"] = 1
            break
        census["rows"] += 1
        if not isinstance(row, dict):
            continue
        sym, fam = str(row.get("symbol") or ""), str(row.get("family") or "")
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        idents.add(_ident(sym, fam, params))
        if guard is not None:
            ff.note_net_verdict(guard, row)
        sess = str(params.get("session") or "").lower()
        if sess in ff.SESSION_NAMES and sym and fam:
            census["session_variants"] += 1
            variants.append({"genome_id": row.get("genome_id"), "symbol": sym, "family": fam,
                             "params": params, "session": sess,
                             **{k: row[k] for k in CULTURE_KEYS if row.get(k)}})
    return variants, idents, census


def classify_all(variants: list[dict], cache: dict, *, measure_s: float,
                 guard: dict | None = None) -> dict[str, Any]:
    """Measure missing keys (bounded) and classify every variant in place."""
    started = time.monotonic()
    measured = 0
    first: dict[str, dict] = {}
    for v in variants:
        first.setdefault(ff.key(v["family"], v["params"], v["symbol"]), v)
    for k, v in first.items():
        if not ff.stale(cache["keys"].get(k)):
            continue
        if time.monotonic() - started > measure_s:
            break
        base = {kk: vv for kk, vv in v["params"].items() if kk != "session"}
        cache["keys"][k] = ff.measure(v["family"], base, v["symbol"])
        measured += 1
    first_sym = first
    for v in variants:
        rec = ff.lookup(v["family"], v["params"], cache, v["symbol"])
        v["verdict"] = ff.guarded_verdict(rec, v["session"], symbol=v["symbol"],
                                          family=v["family"], params=v["params"], guard=guard)
        if v["verdict"] == ff.PROTECTED:
            v["protected_by"] = ff.protected(guard, v["symbol"], v["family"], v["params"],
                                             v["session"])
    return {"keys": len(first_sym), "measured_now": measured,
            "unmeasured_keys": sum(1 for k in first_sym if (cache["keys"].get(k) or {})
                                   .get("status") != "MEASURED"),
            "elapsed_s": round(time.monotonic() - started, 2)}


def plan(variants: list[dict], idents: set[bytes], cache: dict, *,
         measure_s: float) -> list[dict]:
    """A sidecar row for every DEAD variant, carrying the first stand-in not already a cell."""
    started = time.monotonic()
    rows: list[dict] = []
    chosen: set[bytes] = set()
    stamp = _now()
    for v in variants:
        # LIVE_FILTER_ONLY and PROTECTED_BY_EVIDENCE never reach the sidecar: the sealed patch
        # sorts every sidecar row last, and both of those trade as the desk runs today.
        if v.get("verdict") not in (ff.DEAD, ff.TZ_MISMATCH):
            continue
        fam, sym, sess = v["family"], v["symbol"], v["session"]
        rec = ff.lookup(fam, v["params"], cache, sym) or {}
        if v["verdict"] == ff.TZ_MISMATCH:
            # Dead ONLY on today's server-hour window: never remapped -- the shared filter's move
            # to the market clock (pass 2) makes this very cell live. Planned for the report
            # but NOT written to the sidecar (`SIDECAR_VERDICTS`): the sealed patch sorts every
            # sidecar row last, and these are held out until pass 2 re-measures them.
            rows.append({
                "genome_id": v.get("genome_id"), "symbol": sym, "family": fam,
                "params": v["params"], "session": sess, "chart": ff.chart_of(fam, v["params"]),
                "verdict": ff.TZ_MISMATCH, "cause": ff.TZ_MISMATCH,
                "fires_at_hours": sorted(int(h) for h in rec.get("hours") or {}),
                "market_session_signals": ff.market_count(rec, sess),
                "n_signals_measured": rec.get("n"), "marked_at": stamp, "replacement": None,
                **_culture(v, fam, sess, sess)})
            continue
        can_measure = time.monotonic() - started < measure_s
        pick = None
        for cand in ff.replacements(fam, v["params"], sess, cache=cache,
                                    measure_missing=can_measure, symbol=sym):
            i = _ident(sym, fam, cand)
            if i in idents or i in chosen:
                continue
            pick = cand
            chosen.add(i)
            break
        home = str((pick or {}).get("session") or "all")
        row: dict[str, Any] = {
            "genome_id": v.get("genome_id"), "symbol": sym, "family": fam,
            "params": v["params"], "session": sess, "chart": ff.chart_of(fam, v["params"]),
            "verdict": ff.DEAD, "cause": ff.NEVER_FIRES,
            # DEAD needs both clocks empty, so this is False on every row; kept as the check.
            "server_window_fires": bool(ff.window_count(rec, sess)),
            "fires_at_hours": sorted(int(h) for h in rec.get("hours") or {}),
            "n_signals_measured": rec.get("n"), "marked_at": stamp,
            "replacement": None,
        }
        kind = ""
        if pick is not None:
            moved = any(pick.get(n) != v["params"].get(n) for n in ff.hour_params(fam))
            kind = "reanchored" if moved else "rehomed"
            row["replacement"] = {"params": pick, "session": home, "remap": kind}
        row.update(_culture(v, fam, sess, home, kind or "rehomed"))
        rows.append(row)
    return rows


#: The only verdicts written to the sidecar the sealed patch sorts last (2026-09-30 audit of #145):
#: DEAD alone. SESSION_TZ_MISMATCH stays out until it is re-measured on the market-clock filter;
#: LIVE_FILTER_ONLY and PROTECTED_BY_EVIDENCE never reach `plan` at all.
SIDECAR_VERDICTS = frozenset({ff.DEAD})


def write_sidecar(rows: list[dict], path: Path = SIDECAR) -> None:
    """Rewritten whole each pass: a DERIVED mark over the docket, never a ledger of its own.
    Only rows whose verdict is in `SIDECAR_VERDICTS` are written."""
    rows = [r for r in rows if r.get("verdict") in SIDECAR_VERDICTS]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def donate(rows: list[dict], *, budget_s: float, max_donate: int = MAX_DONATE) -> dict[str, Any]:
    """Every stand-in through the one registry door; content-hash de-duplicated."""
    started = time.monotonic()
    todo = [r for r in rows if r.get("replacement")][:max_donate]
    if not todo:
        return {"available": True, "planned": 0, "created": 0, "already_present": 0,
                "failed": 0}
    try:
        from libs.moat.registry import connect, enqueue_candidate
        con = connect()
    except Exception as exc:
        return {"available": False,
                "why": f"{ff.UNMEASURED}: registry door unreachable ({type(exc).__name__})"}
    created = existing = failed = 0
    stopped = "plan exhausted"
    try:
        for r in todo:
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached"
                break
            rep = r["replacement"]
            p = rep["params"]
            try:
                _id, made = enqueue_candidate(
                    family=r["family"], symbol=r["symbol"], params=p, origin=ORIGIN, conn=con,
                    mechanism=(f"{r['family']} {rep['remap']} from its dead {r['session']} "
                               f"variant to {rep['session']} (fires at hours "
                               f"{r['fires_at_hours']})"),
                    producer=ORIGIN, chart=r["chart"], session=str(p.get("session") or "all"),
                    regime=str(p.get("regime") or ""), transformation=f"session_{rep['remap']}",
                    **{k: r[k] for k in CULTURE_KEYS})
            except Exception:
                failed += 1
                continue
            created += int(bool(made))
            existing += int(not made)
    finally:
        con.close()
    return {"available": True, "planned": len(todo), "created": created,
            "already_present": existing, "failed": failed, "stopped_because": stopped,
            "elapsed_s": round(time.monotonic() - started, 2)}


def guard_check(variants: list[dict], guard: dict) -> dict[str, Any]:
    """Independent re-check: how many DEAD variants the evidence says fire. Must be 0."""
    bad = [v for v in variants if v.get("verdict") == ff.DEAD
           and ff.protected(guard, v["symbol"], v["family"], v["params"], v["session"])]
    lfo_or_prot = [v for v in variants if v.get("verdict") in (ff.LIVE_FILTER_ONLY, ff.PROTECTED)]
    evid = [v for v in variants
            if ff.protected(guard, v["symbol"], v["family"], v["params"], v["session"])]
    return {"sources": guard.get("sources"),
            "certified_cells": len(guard.get("certified") or ()),
            "passed_cells": len(guard.get("passed") or ()),
            "net_positive_cells": len(guard.get("net_positive") or ()),
            "session_variants_with_evidence": len(evid),
            "evidence_variants_by_verdict": dict(Counter(str(v.get("verdict")) for v in evid)),
            "certified_or_positive_dead": len(bad),
            "certified_or_positive_dead_sample": [
                {k: v[k] for k in ("symbol", "family", "params", "session")} for v in bad[:10]],
            "live_filter_only_or_protected": len(lfo_or_prot)}


def report(variants: list[dict], rows: list[dict], census: dict, cls: dict,
           don: dict, guard: dict | None = None) -> dict[str, Any]:
    by: dict[str, Counter] = defaultdict(Counter)
    for v in variants:
        by[v["family"]]["variants"] += 1
        by[v["family"]][str(v.get("verdict") or ff.UNMEASURED).lower()] += 1
    for r in rows:
        if r.get("verdict") == ff.TZ_MISMATCH:
            continue
        if r.get("replacement"):
            by[r["family"]]["remapped"] += 1
            by[r["family"]][r["replacement"]["remap"]] += 1
    fams = {}
    for f, c in sorted(by.items(), key=lambda kv: -kv[1]["dead"]):
        judged = (c["dead"] + c["live"] + c["session_tz_mismatch"] + c["live_filter_only"]
                  + c["protected_by_evidence"])
        fams[f] = {**dict(c), "dead_share_of_variants": round(c["dead"] / c["variants"], 4),
                   "dead_share_of_measured": (round(c["dead"] / judged, 4) if judged
                                              else ff.UNMEASURED)}
    n = len(variants)
    dead = sum(1 for v in variants if v.get("verdict") == ff.DEAD)
    live = sum(1 for v in variants if v.get("verdict") == ff.LIVE)
    tzm = sum(1 for v in variants if v.get("verdict") == ff.TZ_MISMATCH)
    lfo = sum(1 for v in variants if v.get("verdict") == ff.LIVE_FILTER_ONLY)
    prot = sum(1 for v in variants if v.get("verdict") == ff.PROTECTED)
    unm = n - dead - live - tzm - lfo - prot
    judged = dead + live + tzm + lfo + prot
    dead_rows = [r for r in rows if r.get("verdict") == ff.DEAD]
    return {
        "generated_at": _now(), "oracle_version": ff.VERSION,
        "docket": {**census, "path": str(DOCKET.relative_to(BASE))},
        "session_variants": n, "dead_found": dead, "live": live, "unmeasured": unm,
        "session_tz_mismatch": tzm, "session_tz_mismatch_in_sidecar": 0,
        "sidecar_verdicts": sorted(SIDECAR_VERDICTS), "live_filter_only": lfo,
        "protected_by_evidence": prot,
        "dead_share": round(dead / n, 4) if n else ff.UNMEASURED,
        "dead_share_of_measured": round(dead / judged, 4) if judged else ff.UNMEASURED,
        "dead_rule": ("DEAD only when NEITHER clock holds a signal (never on today's server-hour "
                      "filter, never in the market's own session); filter-only is "
                      f"{ff.LIVE_FILTER_ONLY}, market-only is {ff.TZ_MISMATCH}"),
        "dead_by_cause": {ff.NEVER_FIRES: dead},
        "guard": guard_check(variants, guard) if guard is not None else ff.UNMEASURED,
        "dead_but_server_window_fires": sum(1 for r in dead_rows
                                            if r.get("server_window_fires")),
        "dead_today_on_server_window": (sum(1 for r in dead_rows
                                            if not r.get("server_window_fires")) + tzm),
        "oracle_clock_hash": ff.clock_hash(),
        "clock": ff.CLOCK_BASIS,
        "remapped": sum(1 for r in dead_rows if r.get("replacement")),
        "remapped_by_kind": dict(Counter(r["replacement"]["remap"] for r in dead_rows
                                         if r.get("replacement"))),
        "dead_without_standin": sum(1 for r in dead_rows if not r.get("replacement")),
        "oracle": cls, "donation": don, "by_family": fams,
        "sidecar": str(SIDECAR.relative_to(BASE)),
        "consumers": ["libs/research/family_firing.session_cells <- miner_candidate_compiler."
                      "expand_axes, breadth_sweep.cells, axis_registry, qd_frontier, "
                      "trajectory_evolution, moat_card_explosion",
                      "registry door -> research_candidates (origin session_variant_remap)"],
        "sealed_need": SEALED_NEED,
        "law": ("NOTHING REMOVED: a dead variant stays in the docket and is only marked; "
                "UNMEASURED is never DEAD; every stand-in is a new cell charged to the census"),
    }


def run(*, budget_s: float = 240.0, donate_rows: bool = True, docket: Path = DOCKET,
        cache_path: Path | None = None, sidecar: Path = SIDECAR,
        out: Path = REPORT, canon: Path | None = None,
        ledger: Path | None = None) -> dict[str, Any]:
    started = time.monotonic()
    # An unreadable universe.json makes every class key miss the cache, so every variant reads
    # UNMEASURED. That result stands (UNMEASURED is never DEAD, never 0); the cause is warned and
    # published so it is never mistaken for a cache that was simply never measured.
    unreadable = ff.universe_unreadable()
    if unreadable:
        ff.warn_universe_unreadable(unreadable)
    cache = ff.load_cache(cache_path)
    guard = ff.load_guard(canon, ledger)
    variants, idents, census = scan(docket, guard=guard)
    cls = classify_all(variants, cache, measure_s=budget_s * 0.45, guard=guard)
    left = max(5.0, budget_s * 0.7 - (time.monotonic() - started))
    rows = plan(variants, idents, cache, measure_s=left * 0.5)
    ff.save_cache(cache, cache_path)
    write_sidecar(rows, sidecar)
    left = max(5.0, budget_s * 0.95 - (time.monotonic() - started))
    don = (donate(rows, budget_s=left) if donate_rows
           else {"available": True, "dry_run": True,
                 "planned": sum(1 for r in rows if r.get("replacement"))})
    doc = report(variants, rows, census, cls, don, guard)
    doc["universe_unreadable"] = unreadable or None
    doc["elapsed_s"] = round(time.monotonic() - started, 2)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(out.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, default=str)
    os.chmod(tmp, 0o644)
    os.replace(tmp, out)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--no-donate", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, donate_rows=not a.no_donate)
    print(f"session_variant_remap: {doc['session_variants']} variants, {doc['dead_found']} dead, "
          f"{doc['live_filter_only']} live-filter-only, {doc['session_tz_mismatch']} tz-mismatch, "
          f"{doc['live']} live, {doc['unmeasured']} unmeasured, {doc['remapped']} remapped "
          f"in {doc['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
