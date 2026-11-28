#!/usr/bin/env python3
"""ZERO-CELL FAMILIES: every live family the judge has never been handed a cell for, and why.

    python desks/mt5/research/zero_cell_families.py --once --budget-s 600
    python desks/mt5/research/zero_cell_families.py --once --dry-run      # diagnose, mint nothing

THE MEASUREMENT (JUDGE_COVERAGE.json, 2026-11-17 13:10Z). `unmined_live_families` named twenty
registered families with `mined: 0`: no docket row, so no judge can ever reach them. Each has a
code path that resolves it (`families.live_family_names`), and none of them had a reason. A
family that is registered, buildable and never judged is a claim the desk cannot cash (L1.49),
and "no cells" with no cause is the silent clean verdict L1.28a forbids.

WHAT THIS DOES, EVERY HOUR. It reads the list from the judge's own artifact (never a list kept
here, so a family registered tomorrow is diagnosed the hour the judge names it) and, for each
family, MEASURES on this host why its producer has minted nothing, from that producer's own
artifact and from the inputs the family reads:

  PRESCREEN_FORWARDS_NONE  the producer runs the family on desk bars and its own pre-screen
                           forwards nothing (learned_miners' deflated t > 2; mass_screen's
                           run-level BH over ~10^6 cells, where the lead grammar is ~1%).
                           ACTION: SEEDED -- this organ mints the family's FIRST cells (below).
  NO_PRODUCER_REACHES      no scheduled producer enumerates the family (the hunt16 dav_*
                           population is outside breadth_sweep's family set).
  OPERATOR_NEEDS_BASE      the family is an operator over a named base cell (hunt16_cell
                           re-expresses an EVICTED hunt16 certificate); with no base there is
                           nothing to mint, and the unfiltered form IS the base family.
  BLOCKED_INPUT            an input the family reads is absent on this host, named exactly.
  INPUT_PRESENT_PRODUCER_OWES  the inputs exist and the owning producer still minted nothing;
                           its own artifact's counts are copied in so the gap is attributable.

FIRST CELLS, NOT A SEARCH. For a PRESCREEN_FORWARDS_NONE family this organ runs the owning
producer's OWN screen (`learned_miners.mine`, `mass_screen._worker`) on the desk's bars and
donates at most SEED_K cells: the best-ranked measured cells that clear the producer's own cost
test (learned: `clears_cost` with >= MIN_TRADES independent trades; mass_screen: positive net R
and positive at 3x spread), one per symbol, through the producer's own door (`proposer_common.
donate` / `mass_screen.forward`). Every row carries `seed` with the width it was drawn from, so
the judge's trial census charges the whole screen and `certificate_provenance` can see the lane.
Nothing is relaxed downstream: the cells face the sealed gauntlet's ten gates unchanged. A seeded
family is not seeded again for RESEED_AFTER_H hours; once the judge counts it as mined it leaves
the list and this organ stops touching it. Why first cells at all: a family with no verdict has
no posterior, and its first judged cells are the cheapest information the judge can buy (the same
reason breadth_sweep orders never-mined families first) -- but a pre-screen that forwards nothing
leaves the family unmeasured forever, which is not a measurement of the family.

Artifact: `reports/ZERO_CELL_FAMILIES.json` (and `judge_coverage` copies each family's cause into
`unmined_reasons`). State: `data/zero_cell_seed_state.json`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = BASE / "reports" / "ZERO_CELL_FAMILIES.json"
STATE = BASE / "data" / "zero_cell_seed_state.json"
JUDGE_COVERAGE = BASE / "reports" / "JUDGE_COVERAGE.json"
LAKE = BASE / "data" / "lake" / "series"
UNMEASURED = "UNMEASURED"

#: At most this many first cells per family per seeding.
SEED_K = 3
#: A seeded family still unmined after this long (the door refused, or the judge has not counted
#: it yet) may be seeded again.
RESEED_AFTER_H = 168.0

PRESCREEN_FORWARDS_NONE = "PRESCREEN_FORWARDS_NONE"
NO_PRODUCER_REACHES = "NO_PRODUCER_REACHES"
OPERATOR_NEEDS_BASE = "OPERATOR_NEEDS_BASE"
BLOCKED_INPUT = "BLOCKED_INPUT"
INPUT_PRESENT_PRODUCER_OWES = "INPUT_PRESENT_PRODUCER_OWES"
NO_PROBE = "NO_PROBE"
CAUSES = (PRESCREEN_FORWARDS_NONE, NO_PRODUCER_REACHES, OPERATOR_NEEDS_BASE, BLOCKED_INPUT,
          INPUT_PRESENT_PRODUCER_OWES, NO_PROBE)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def _age_h(path: Path) -> float | None:
    try:
        return round((time.time() - path.stat().st_mtime) / 3600.0, 2)
    except OSError:
        return None


# ------------------------------------------------------------------------------ the list ---
def unmined(path: Path | None = None) -> tuple[list[str], dict[str, Any]]:
    """(families with zero docket cells, where the list came from), from the judge's artifact.

    `unmined_live_families` when published, else every `families` row with `mined == 0`. An
    absent or unreadable report is UNMEASURED and an empty list, never "no family is unmined".
    """
    p = path or JUDGE_COVERAGE
    doc = _read(p)
    if not isinstance(doc, dict):
        return [], {"status": UNMEASURED, "why": f"{p.name} absent or unreadable"}
    names = doc.get("unmined_live_families")
    basis = "unmined_live_families"
    if not isinstance(names, list):
        raw = doc.get("families")
        fams: dict[str, Any] = raw if isinstance(raw, dict) else {}
        names = [f for f, r in fams.items() if isinstance(r, dict) and r.get("mined") == 0]
        basis = "families[].mined == 0"
    return (sorted({str(n) for n in names if n}),
            {"status": "MEASURED", "path": p.name, "at": doc.get("at") or doc.get("generated_at"),
             "basis": basis})


# ------------------------------------------------------------------------------ the probes --
def _verdict(cause: str, why: str, *, action: str = "NONE_HERE", producer: str = "",
             **detail: Any) -> dict[str, Any]:
    return {"cause": cause, "why": why, "action": action, "producer": producer, **detail}


def learned_family_models() -> dict[str, str]:
    """{family: learned_miners model} for the five learned families, read from the miner."""
    try:
        from research import learned_miners as lm
        return {str(spec["family"]): model for model, spec in lm.MINERS.items()}
    except Exception:
        return {}


def probe_learned(fam: str, model: str) -> dict[str, Any]:
    rep_path = BASE / "reports" / "learned_miners.json"
    rep = _read(rep_path)
    seen: dict[str, Any] = {"report": rep_path.name, "report_age_h": _age_h(rep_path)}
    if isinstance(rep, dict):
        for key, res in (rep.get("miners") or {}).items():
            if str(key).split("@")[0] == model and isinstance(res, dict):
                seen[key] = {"tests_attempted": res.get("tests_attempted"),
                             "candidates": res.get("candidates")}
        why = ("learned_miners screens the family on desk bars and proposes a cell only at "
               "deflated t > 2 net of cost; every configuration x symbol x threshold it measured "
               "fell short, so nothing reached the compiler")
    else:
        why = ("learned_miners has written no report on this host (it runs only as a daily_cycle "
               "proposer, last in a long list), and its pre-screen proposes only at deflated "
               "t > 2: measured on the desk's bars 2026-11-18 the best was 0.57")
    return _verdict(PRESCREEN_FORWARDS_NONE, why, action="SEED",
                    producer="research/learned_miners.py", producer_artifact=seen)


def probe_mass_screen_lead() -> dict[str, Any]:
    path = BASE / "reports" / "MASS_SCREEN.json"
    doc = _read(path)
    lead = ((doc or {}).get("by_grammar") or {}).get("lead") if isinstance(doc, dict) else None
    fdr = (doc or {}).get("fdr") if isinstance(doc, dict) else None
    return _verdict(
        PRESCREEN_FORWARDS_NONE,
        "mass_screen applies ONE Benjamini-Hochberg cut over every cell of every grammar; the "
        "lead grammar is ~1% of the width and its best p never reaches the pooled cut (measured "
        "2026-11-18 on 24 hypothesis-lane symbols: lead min p 5.5e-5 against a pooled cut of "
        "2e-7; 0 of 48 lead candidates rejected even under a lead-only cut)",
        action="SEED", producer="research/mass_screen.py",
        producer_artifact={"report": path.name, "report_age_h": _age_h(path),
                           "lead": lead if isinstance(lead, dict) else UNMEASURED,
                           "fdr": fdr if isinstance(fdr, dict) else UNMEASURED})


def probe_hunt16_population(fam: str) -> dict[str, Any]:
    try:
        from research import breadth_sweep as bs
        ok, _blocked = bs.default_families()
        reached = fam in ok
    except Exception as exc:
        return _verdict(NO_PRODUCER_REACHES, f"breadth_sweep unimportable ({type(exc).__name__})",
                        producer="research/breadth_sweep.py", reached=UNMEASURED)
    if reached:
        return _verdict(NO_PRODUCER_REACHES,
                        "breadth_sweep now enumerates the hunt16 population; its next pass mints "
                        "this family's cells at defaults", action="UPSTREAM_FIXED",
                        producer="research/breadth_sweep.py", reached=True)
    return _verdict(NO_PRODUCER_REACHES,
                    "a run_hunt16.FAMILIES member: families.live_family_names counts it, but "
                    "breadth_sweep.default_families reads only FAMILY_REGISTRY and "
                    "ORTHOGONAL_FAMILIES, so no scheduled producer ever enumerates it; the fix is "
                    "breadth_sweep importing executables.hunt16_families (one change, owned by "
                    "the breadth sweep, not duplicated here)",
                    producer="research/breadth_sweep.py", reached=False)


def probe_hunt16_cell() -> dict[str, Any]:
    ev = _read(BASE / "reports" / "UNIVERSAL_SURVIVORS_UNRUNNABLE.json")
    rows = (ev.get("evicted") or ev.get("rows") or []) if isinstance(ev, dict) else (
        ev if isinstance(ev, list) else [])
    hunt = [r for r in rows if isinstance(r, dict) and str(r.get("family", "")).startswith("dav_")]
    rj = _read(BASE / "reports" / "REJUDGE_EVICTED.json")
    cells = [c for c in ((rj or {}).get("cells") or []) if isinstance(c, dict)
             and c.get("family") == "hunt16_cell"] if isinstance(rj, dict) else []
    return _verdict(
        OPERATOR_NEEDS_BASE,
        "an operator over an EVICTED hunt16 certificate: rejudge_evicted is its only minter and "
        "writes one cell per evicted dav_* certificate (base_family, direction, signal hour, day "
        "label from the certificate). Unfiltered, hunt16_cell(base_family=X) IS dav X -- the "
        "same signals -- so minting it blind would charge the judge twice for one rule",
        producer="research/rejudge_evicted.py",
        evicted_hunt16_certificates=len(hunt) if ev is not None else UNMEASURED,
        rejudge_cells=len(cells) if rj is not None else UNMEASURED)


def probe_class_carry() -> dict[str, Any]:
    try:
        from mt5desk import families_cross_sectional as xs
        src, lake = xs.CARRY_SOURCE, xs.CARRY_DIR
    except Exception:
        src, lake = "fred_rdiff3m", LAKE
    have = sorted(p.name for p in lake.glob(f"{src}_*.parquet")) if lake.is_dir() else []
    if not have:
        return _verdict(
            BLOCKED_INPUT,
            f"reads {src}_<symbol>.parquet (a point-in-time 3-month rate differential) from "
            f"data/lake/series: 0 files on this host, no organ in this repository writes "
            f"them, and their source is FRED, which the desk refuses for every automated fetch. "
            f"Unblocks when a free, terms-clean rate-differential series lands under that name",
            producer="research/cross_sectional_breadth.py", input=f"data/lake/series/{src}_*",
            input_files=0)
    return _verdict(INPUT_PRESENT_PRODUCER_OWES,
                    f"{len(have)} {src} series present; cross_sectional_breadth owns the grid",
                    producer="research/cross_sectional_breadth.py", input_files=len(have),
                    producer_artifact=_xsb_row("cross_sectional_class_carry"))


def _xsb_row(fam: str) -> Any:
    doc = _read(BASE / "reports" / "CROSS_SECTIONAL_BREADTH.json")
    if not isinstance(doc, dict):
        return UNMEASURED
    raw = doc.get("seeding")
    seeding: dict[str, Any] = raw if isinstance(raw, dict) else {}
    by = seeding.get("cells_by_family")
    return by.get(fam, UNMEASURED) if isinstance(by, dict) else UNMEASURED


def _bars_present(sym: str) -> bool:
    try:
        from research import proposer_common as pc
        b = pc.bars(sym)
        return b is not None and len(b) > 0
    except Exception:
        return False


def probe_month_end() -> dict[str, Any]:
    try:
        from research import specialist_cell as sc
        proxies = sorted({"UST10Y", *sc.BOND_OF.values()})
    except Exception:
        proxies = ["UKGILT", "UST10Y"]
    missing = [s for s in proxies if not _bars_present(s)]
    if missing:
        return _verdict(
            BLOCKED_INPUT,
            f"reads its bond proxy's H1 bars as of each decision bar; absent on this host: "
            f"{', '.join(missing)}. specialist_cell builds every month_end_rebalance cell through "
            f"the sealed build_cell and the family returns no signal without the proxy",
            producer="research/specialist_cell.py", input=missing)
    doc = _read(BASE / "reports" / "SPECIALIST_CELLS.json")
    rows = ((doc or {}).get("seeding") or {}).get("by_mechanism") if isinstance(doc, dict) else None
    mine = [r for r in (rows or []) if isinstance(r, dict)
            and r.get("mechanism") == "month_end_rebalance"]
    return _verdict(
        INPUT_PRESENT_PRODUCER_OWES,
        "the bond proxies' bars are present; specialist_cell owns the index catalogue and has "
        "donated no month_end_rebalance cell -- its by_mechanism row says whether they were "
        "held under the 66-trade-day floor, not reached in budget or set aside",
        producer="research/specialist_cell.py",
        producer_artifact=mine or UNMEASURED,
        producer_input_gaps={k: v for k, v in (((doc or {}).get("seeding") or {})
                                               .get("input_gaps") or {}).items()
                             if k.startswith("month_end_rebalance")} if isinstance(doc, dict)
        else UNMEASURED)


def probe_alt_release() -> dict[str, Any]:
    doc = _read(BASE / "data" / "digests" / "alt_proxies_equity_handoff.json")
    rows = [r for r in ((doc or {}).get("rows") or []) if isinstance(r, dict)
            and r.get("usable") and not r.get("dead")] if isinstance(doc, dict) else []
    if not rows:
        return _verdict(BLOCKED_INPUT, "the alt_proxies equity hand-off lists no usable series",
                        producer="research/alt_equity_handoff.py",
                        input="data/digests/alt_proxies_equity_handoff.json")
    present = [r["lake_file"] for r in rows if r.get("lake_file") and any(
        (LAKE / f"{r['lake_file']}{s}").exists() for s in (".parquet", ".csv"))]
    if not present:
        return _verdict(
            BLOCKED_INPUT,
            f"each cell replays a lake series named by the hand-off; 0 of {len(rows)} usable "
            f"series files exist under data/lake/series on this host (alt_proxies has not "
            f"written them here), so every cell is held SERIES_ABSENT",
            producer="research/alt_equity_handoff.py",
            input=sorted({str(r.get("lake_file")) for r in rows})[:20])
    rep = _read(BASE / "reports" / "ALT_EQUITY_HANDOFF.json")
    return _verdict(
        INPUT_PRESENT_PRODUCER_OWES,
        f"{len(present)} of {len(rows)} hand-off series are present; the event cell fires only "
        f"on releases with |surprise_z| >= 1 and is donated only once its firing clears the "
        f"gauntlet floor",
        producer="research/alt_equity_handoff.py", input_files=len(present),
        producer_artifact=(rep or {}).get("held", UNMEASURED) if isinstance(rep, dict)
        else UNMEASURED)


def probe_analyst(fam: str) -> dict[str, Any]:
    store = BASE / "data" / "alpha_capture" / "analyst_views.jsonl"
    try:
        with store.open("rb") as fh:
            n = sum(1 for line in fh if line.strip())
    except OSError:
        n = 0
    if not n:
        return _verdict(
            BLOCKED_INPUT,
            "replays point-in-time analyst/broker/guidance views from alpha_capture's store; the "
            "store holds 0 views on this host (no source has been fetched here), so there is no "
            "event to place",
            producer="research/alpha_capture.py", input="data/alpha_capture/analyst_views.jsonl",
            input_rows=0)
    rep = _read(BASE / "reports" / "ANALYST_VIEWS.json")
    return _verdict(
        INPUT_PRESENT_PRODUCER_OWES,
        f"{n} views stored; alpha_capture donates a cell only for a source whose drift clears "
        f"its placebo contract, so its contract verdicts say which gate held",
        producer="research/alpha_capture.py", input_rows=n,
        producer_artifact={"cells": (rep or {}).get("cells", UNMEASURED),
                           "contract": {k: (v or {}).get("status") for k, v in
                                        ((rep or {}).get("contract") or {}).items()
                                        if isinstance(v, dict)}} if isinstance(rep, dict)
        else UNMEASURED)


def probe(fam: str, learned: dict[str, str] | None = None) -> dict[str, Any]:
    """Why `fam` has no docket cell, measured on this host. Never raises."""
    learned = learned if learned is not None else learned_family_models()
    try:
        if fam in learned:
            return probe_learned(fam, learned[fam])
        if fam == "mass_screen_lead":
            return probe_mass_screen_lead()
        if fam == "hunt16_cell":
            return probe_hunt16_cell()
        if fam == "cross_sectional_class_carry":
            return probe_class_carry()
        if fam == "month_end_rebalance":
            return probe_month_end()
        if fam == "alt_release_drift":
            return probe_alt_release()
        if fam in ("analyst_revision_drift", "analyst_cross_market_lead"):
            return probe_analyst(fam)
        if fam.startswith("dav_"):
            return probe_hunt16_population(fam)
    except Exception as exc:
        return _verdict(NO_PROBE, f"probe raised {type(exc).__name__}")
    return _verdict(NO_PROBE, "no probe names this family's producer yet: UNMEASURED, and listed "
                              "so the next session writes one")


# ----------------------------------------------------------------------------- the seeders --
def _seed_note(width: int, producer: str, basis: str) -> dict[str, Any]:
    return {"lane": "zero_cell_first_cells", "producer": "research/zero_cell_families.py",
            "screen": producer, "screen_width": int(width), "basis": basis, "k": SEED_K}


def pick_learned(rows: list[dict[str, Any]], k: int = SEED_K) -> list[dict[str, Any]]:
    """The best `k` measured rows that clear the miner's own cost test, one per symbol."""
    from research import proposer_common as pc
    ok = [r for r in rows if r.get("clears_cost") and float(r.get("t_gross") or 0.0) > 0
          and int(r.get("n_independent") or 0) >= pc.MIN_TRADES]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in sorted(ok, key=lambda x: -float(x.get("t_deflated_sweep") or -1e9)):
        if str(r["symbol"]) in seen:
            continue
        seen.add(str(r["symbol"]))
        out.append(r)
        if len(out) >= k:
            break
    return out


def seed_learned(fam: str, model: str, *, budget_s: float, dry_run: bool) -> dict[str, Any]:
    from research import learned_miners as lm
    from research import proposer_common as pc
    syms = lm.PANELS.get("core", lm.PANEL)
    bars = lm.load_bars(syms)
    if len(bars) < lm.MIN_PANEL:
        return {"status": BLOCKED_INPUT, "why": f"{len(bars)} of {len(syms)} core panel symbols "
                f"have bars, below the miner's {lm.MIN_PANEL} floor"}
    res = lm.mine(model, bars, pc.universe_meta(), deadline=time.monotonic() + budget_s,
                  panel_name="core")
    trials = res.pop("_trials", [])
    picks = pick_learned(res.get("rows") or [])
    out: dict[str, Any] = {"tests_attempted": res.get("tests_attempted"),
                           "tests_screened": res.get("tests_screened"),
                           "clear_cost": sum(1 for r in res.get("rows") or []
                                             if r.get("clears_cost")),
                           "picked": [{k: r.get(k) for k in ("symbol", "config", "entry_z",
                                                              "t_gross", "t_deflated_sweep",
                                                              "n_independent")} for r in picks]}
    if not picks:
        out["status"] = "NOTHING_CLEARS_COST"
        return out
    cands = [lm.make_candidate(model, r, panel=res["panel"], tests_run=res["tests_attempted"],
                               n_effective=res["effective_trials"]) for r in picks]
    note = _seed_note(int(res["tests_attempted"]), "research/learned_miners.py",
                      "best deflated t among cells clearing the miner's own cost test")
    for c in cands:
        c["seed"] = note
    if dry_run:
        out["status"] = "DRY_RUN"
        return out
    door = pc.donate(str(res["source"]), cands, int(res["tests_attempted"]), suffix="seed")
    out["donated"] = str(door) if door else None
    out["donation"] = pc.donation_counts()
    out["trial_ledger_error"] = lm._append_trials(
        [{"generated_utc": _now().isoformat(), "source": res["source"], "trial_id": t.trial_id,
          "family": t.family, "descriptors": dict(t.descriptors), "donated": door is not None,
          "lane": "zero_cell_first_cells"} for t in trials], lm.TRIALS)
    out["status"] = "DONATED" if door else "REFUSED_AT_DOOR"
    return out


def pick_mass_screen(cands: list[dict[str, Any]], k: int = SEED_K) -> list[dict[str, Any]]:
    """Lead candidates positive net and at 3x spread, deduplicated, best p first, one per
    symbol."""
    from research import mass_screen as ms
    ok = [c for c in cands if c.get("grammar") == "lead" and float(c.get("mean_r") or 0) > 0
          and float(c.get("mean_r_x3") or 0) > 0]
    kept, _ = ms.dedup(ok)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in sorted(kept, key=lambda r: float(r["p"])):
        if str(c["symbol"]) in seen:
            continue
        seen.add(str(c["symbol"]))
        out.append(c)
        if len(out) >= k:
            break
    return out


def seed_mass_screen_lead(*, budget_s: float, dry_run: bool) -> dict[str, Any]:
    import numpy as np
    from mt5desk.mass_screen_rules import GRAMMARS

    from research import mass_screen as ms
    skip = tuple(g for g in GRAMMARS if g != "lead")
    deadline = time.monotonic() + budget_s
    width = 0
    cands: list[dict[str, Any]] = []
    done: list[str] = []
    for sym in ms.hypothesis_symbols():
        if time.monotonic() > deadline:
            break
        r = ms._worker(sym, ms.FDR_Q, skip)
        if r.get("error"):
            continue
        done.append(sym)
        width += int(((r.get("by_grammar") or {}).get("lead") or {}).get("cells") or 0)
        cands.extend(r.get("candidates") or [])
    if not done:
        return {"status": BLOCKED_INPUT, "why": "no hypothesis-lane symbol screened"}
    picks = pick_mass_screen(cands)
    cut = ms.bh_threshold(np.array([c["p"] for c in cands]), width, ms.FDR_Q)
    ranked = sorted(float(c["p"]) for c in cands)
    for c in picks:
        rank = int(np.searchsorted(ranked, c["p"], side="right"))
        c["_qvalue"] = min(1.0, float(c["p"]) * width / max(rank, 1))
        c["_m"], c["_q"] = width, ms.FDR_Q
    out: dict[str, Any] = {"symbols_screened": len(done), "lead_cells": width,
                           "candidates_p_le_q": len(cands), "lead_only_bh_cut": cut,
                           "picked": [{k: c.get(k) for k in ("symbol", "p", "t", "mean_r",
                                                              "mean_r_x3", "n_days", "hold",
                                                              "direction")} | {
                               "leader": (c.get("cond") or {}).get("leader")} for c in picks]}
    if not picks:
        out["status"] = "NOTHING_CLEARS_COST"
        return out
    if dry_run:
        out["status"] = "DRY_RUN"
        return out
    fwd = ms.forward(picks)
    out["forward"] = fwd
    out["seed"] = _seed_note(width, "research/mass_screen.py",
                             "lowest p among lead cells positive net and at 3x spread")
    out["status"] = "FORWARDED" if int(fwd.get("created", 0)) + int(
        fwd.get("already_present", 0)) else "REFUSED_AT_DOOR"
    return out


def seeders(learned: dict[str, str]) -> dict[str, Callable[..., dict[str, Any]]]:
    out: dict[str, Callable[..., dict[str, Any]]] = {
        fam: (lambda budget_s, dry_run, _f=fam, _m=model:
              seed_learned(_f, _m, budget_s=budget_s, dry_run=dry_run))
        for fam, model in learned.items()}
    out["mass_screen_lead"] = seed_mass_screen_lead
    return out


# ---------------------------------------------------------------------------------- the run --
def run(*, budget_s: float = 600.0, dry_run: bool = False, coverage: Path | None = None,
        out: Path | None = None, state_path: Path | None = None) -> dict[str, Any]:
    started = time.monotonic()
    now = _now()
    fams, src = unmined(coverage)
    learned = learned_family_models()
    state_p = state_path or STATE
    state = _read(state_p)
    state = state if isinstance(state, dict) else {}
    seeded_at: dict[str, Any] = dict(state.get("seeded_at") or {})
    table: dict[str, dict[str, Any]] = {f: probe(f, learned) for f in fams}
    seed_fns = seeders(learned)
    due = []
    for f in fams:
        if table[f]["action"] != "SEED" or f not in seed_fns:
            continue
        last = seeded_at.get(f)
        try:
            age = (now - datetime.fromisoformat(str(last))).total_seconds() / 3600.0 \
                if last else None
        except ValueError:
            age = None
        if age is not None and age < RESEED_AFTER_H:
            table[f]["seed"] = {"status": "SEEDED_RECENTLY", "seeded_at": last,
                                "age_h": round(age, 2)}
            continue
        due.append(f)
    # Least-recently seeded first, so a tight budget rotates through every due family.
    due.sort(key=lambda f: str(seeded_at.get(f) or ""))
    for i, f in enumerate(due):
        left = budget_s - (time.monotonic() - started)
        share = left / max(1, len(due) - i)
        if share < 20.0:
            table[f]["seed"] = {"status": "BUDGET", "why": f"{left:.0f}s left of {budget_s:g}s"}
            continue
        try:
            got = seed_fns[f](budget_s=share, dry_run=dry_run)
        except Exception as exc:
            got = {"status": f"ERROR:{type(exc).__name__}"}
        table[f]["seed"] = got
        if not dry_run and got.get("status") in ("DONATED", "FORWARDED"):
            seeded_at[f] = now.isoformat()
    if not dry_run:
        _write(state_p, {"seeded_at": seeded_at, "updated": now.isoformat()})
    by_cause = Counter(v["cause"] for v in table.values())
    doc = {
        "generated_at": now.isoformat(timespec="seconds"),
        "status": "MEASURED" if src.get("status") == "MEASURED" else UNMEASURED,
        "source": src, "dry_run": bool(dry_run),
        "n_unmined": len(fams), "by_cause": dict(by_cause),
        "seeded_this_pass": sorted(f for f, v in table.items()
                                   if (v.get("seed") or {}).get("status") in ("DONATED",
                                                                                "FORWARDED")),
        "blocked_input": {f: v["why"] for f, v in table.items() if v["cause"] == BLOCKED_INPUT},
        "families": table,
        "elapsed_s": round(time.monotonic() - started, 2),
        "rule": ("a live family with no docket cell is diagnosed every hour from its producer's "
                 "own artifact and its inputs; a family whose producer's pre-screen forwards "
                 "nothing gets at most SEED_K first cells through that producer's door, charged "
                 "at the screen's full width; an absent input is BLOCKED_INPUT by name; nothing "
                 "is relaxed at the judge"),
    }
    _write(out or REPORT, doc)
    return doc


def reasons(path: Path | None = None) -> dict[str, dict[str, str]]:
    """{family: {cause, action, why}} from the last report, for `judge_coverage` to publish
    beside `unmined_live_families`. {} when absent: the judge reports no cause, never a guess."""
    doc = _read(path or REPORT)
    fams = (doc or {}).get("families") if isinstance(doc, dict) else None
    if not isinstance(fams, dict):
        return {}
    return {str(f): {"cause": str(v.get("cause")), "action": str(v.get("action")),
                     "why": str(v.get("why"))[:400], "at": str(doc.get("generated_at"))}
            for f, v in fams.items() if isinstance(v, dict)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="diagnose and screen, mint nothing")
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, dry_run=args.dry_run)
    print(f"zero_cell_families: {doc['status']} unmined={doc['n_unmined']} "
          f"by_cause={doc['by_cause']} seeded={doc['seeded_this_pass']} -> {REPORT.name}")
    for f, v in sorted(doc["families"].items()):
        print(f"  {f:28} {v['cause']:28} {v['action']:14} "
              f"{(v.get('seed') or {}).get('status', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
