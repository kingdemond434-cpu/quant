"""Everything the hourly cycle did not finish, finished once a day at 00:00 UTC.

WHY A CATCH-UP EXISTS AT ALL. The hourly cycle is a BUDGET: it runs what fits in an hour and
moves on, which is correct -- an hourly job that tries to drain a 23,465-row docket blocks the
next hour's fresh candidates behind stale ones. The cost of that design is a residue: cells never
reached, survivors never certified, certificates never enrolled, producers whose last run failed.
Nothing was measuring the residue, so it accumulated silently and each organ reported success.
Measured 2026-09-06: 147 of 23,465 docket cells had ever reached a backtest, five whole mechanism
families had been tested zero times, and 18 certificates could never be enrolled.

WHAT THIS IS NOT. It is not a second pipeline and it re-implements no stage. Every step below
calls the SAME module the hourly cycle calls, with the same gates at the same thresholds. A
catch-up that judged by its own rules would be a second judge with a looser bar, arriving at
midnight when nobody is watching -- the exact shape of the defect this desk keeps finding.

IDEMPOTENT BY MEASUREMENT, NOT BY A FLAG. Each step recomputes what is still outstanding and
does only that, so running it twice in a row does the work once and reports zero the second time.
There is no "already ran tonight" marker to go stale, and a step that was interrupted resumes
from the artifacts rather than from a checkpoint that may not describe them.

    python research/nightly_catchup.py            # report only
    python research/nightly_catchup.py --apply    # do the work
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "NIGHTLY_CATCHUP.json"

#: A step gets this long before it is abandoned and reported as TIMEOUT. Generous: the docket
#: sweep is the long pole and measured 265s for 8,057 cells on three workers, so an hour covers
#: a docket several times larger than today's. A step that times out does NOT stop the run --
#: the remaining steps still execute, because a nightly repair that gives up halfway leaves the
#: desk in a state nobody planned for.
STEP_TIMEOUT_S = 3600


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _run(script: str, args: tuple[str, ...] = ()) -> dict[str, Any]:
    """Run a desk script the way its own scheduler does, and report rather than raise."""
    for root in (BASE, ROOT):
        target = root / script
        if target.exists():
            break
    else:
        return {"ok": False, "why": f"{script} not found under {BASE} or {ROOT}"}
    try:
        proc = subprocess.run([sys.executable, str(target), *args], cwd=str(target.parent.parent),
                              capture_output=True, text=True, timeout=STEP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"ok": False, "why": f"TIMEOUT after {STEP_TIMEOUT_S}s"}
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-3:]
    # EXIT 2 IS NOT FAILURE ON THIS DESK. It is the UNANSWERED code (shadow_gap, qquant_gates):
    # the host could not answer the question, which is a different fact from the work failing,
    # and conflating them turns "no hunt report here" into a red alarm nobody can act on.
    return {"ok": proc.returncode in (0, 2), "rc": proc.returncode, "tail": tail}


# --------------------------------------------------------------- what is outstanding

def untested_cells() -> dict[str, Any]:
    """Docket cells with no backtest result, by family.

    Keyed on (symbol, family, params) exactly as `normalize_grid` builds its identity, so a cell
    swept on M5 and one swept on H1 count separately -- they are different candidates and the
    chart is part of the identity.
    """
    docket = _read(BASE / "data" / "hypotheses" / "external_survivors.json") or []
    done = _read(BASE / "data" / "hypotheses" / "external_backtest_results.json") or []

    def key(r: dict) -> str:
        return json.dumps({"s": r.get("symbol"), "f": r.get("family"),
                           "p": r.get("params") or {}}, sort_keys=True, default=str)

    have = {key(r) for r in done if isinstance(r, dict)}
    missing = [r for r in docket if isinstance(r, dict) and key(r) not in have]
    from collections import Counter
    return {"docket": len(docket), "tested": len(have), "untested": len(missing),
            "by_family": dict(Counter(r.get("family") for r in missing).most_common(12))}


def uncertified_survivors() -> dict[str, Any]:
    """Backtest survivors the gauntlet has not judged.

    A survivor is not a certificate and must never be treated as one -- this counts what the ten
    gates have not yet SEEN, which is a throughput fact, and never implies those cells would pass.
    """
    res = _read(BASE / "data" / "hypotheses" / "external_backtest_results.json") or []
    surv = [r for r in res if isinstance(r, dict)
            and (r.get("exp_r") or 0) > 0.05 and (r.get("max_dd_r") or -99) > -30]
    certs = ((_read(BASE / "reports" / "UNIVERSAL_SURVIVORS.json") or {}).get("survivors") or {})
    judged = {str(v.get("sym") or "") + "|" + str((v.get("shadow_spec") or {}).get("family") or "")
              for v in certs.values() if isinstance(v, dict)}
    pending = [r for r in surv if f"{r.get('symbol')}|{r.get('family')}" not in judged]
    return {"survivors": len(surv), "already_certified_pairs": len(judged),
            "awaiting_gauntlet": len(pending)}


def clockless_certificates() -> dict[str, Any]:
    """Certificates that passed all ten gates, can be run, and are on no forward clock.

    Uses the SAME two predicates the doors use -- `gate_policy.all_ten_pass` and
    `survivor_publication.unrunnable_reason` -- so this cannot disagree with admission about what
    a certificate is. A gate-failed row was never a certificate and an unrunnable one cannot be
    enrolled; neither is a work item, and counting them here is how "55 certified, 19 clocks" came
    to look like 36 lost sleeves.
    """
    certs = ((_read(BASE / "reports" / "UNIVERSAL_SURVIVORS.json") or {}).get("survivors") or {})
    try:
        from gate_policy import all_ten_pass
        from survivor_publication import unrunnable_reason
    except ImportError as exc:
        return {"status": f"UNAVAILABLE ({exc})"}
    certified = {k: v for k, v in certs.items()
                 if isinstance(v, dict) and all_ten_pass(v.get("gates"))}
    runnable = {k for k, v in certified.items() if unrunnable_reason(v) is None}
    enrolled: set[str] = set()
    for name in ("shadow_state.json", "qquant_shadow_state.json",
                 "scalp_shadow_state.json", "external_shadow_state.json"):
        state = _read(BASE / "reports" / "shadow" / name) or {}
        rows = state.get("sleeves") if isinstance(state.get("sleeves"), dict) else state
        for k, v in (rows or {}).items():
            if isinstance(v, dict) and "status" in v:
                enrolled.add(str(k))
    # A clock key is the sleeve identity, not the certificate key, so membership is tested on the
    # SYMBOL the certificate names -- coarse on purpose. Over-counting an enrolled certificate as
    # enrolled is safe here; under-counting would manufacture work that the forward engine would
    # then refuse, which is the noisier of the two errors.
    syms = {str((certs[k].get("shadow_spec") or {}).get("symbol") or "") for k in runnable}
    covered = {s for s in syms if any(s and s in e for e in enrolled)}
    return {"certified": len(certified), "runnable": len(runnable),
            "clocks": len(enrolled), "symbols_runnable": len(syms),
            "symbols_without_a_clock": sorted(syms - covered)[:20],
            "clockless_symbols": len(syms - covered)}


def breadth_gaps() -> dict[str, Any]:
    """Families the book still has no certificate in, and whether they are reachable."""
    doc = _read(ROOT / "data" / "miner_conversion.json") or {}
    missing = ((doc.get("book_breadth") or {}).get("missing_families") or [])
    return {"missing_families": [m.get("family") for m in missing],
            "reachable": [m.get("family") for m in missing if m.get("state") == "REACHABLE"],
            "needs": {m.get("family"): m.get("needs") for m in missing}}


def bar_coverage() -> dict[str, Any]:
    """Docket symbols this host cannot judge, and which of the two reasons applies.

    THE SINGLE LARGEST BLOCKER IN THE FUNNEL, and it is not a code defect. Measured 2026-09-06,
    the gauntlet wrote 23,465 verdict rows and judged 42 of them; 15,275 were refused at
    `symbol_eligibility` before any statistical gate ran:

        3,839 cells   the symbol is absent from the universe registry -- no cost model, so no
                      honest backtest is possible (a guessed spread certifies losing cells)
       11,436 cells   no <SYM>_H1.parquet on this host -- US500, NAS100, CADCHF, Meta, Tesla,
                      GeneralMotors and 190 more

    Those are the same two populations `run_external_backtest.hold_uncoverable` reports, to the
    cell: both stages agree, which is what says this is a DATA fact rather than a bug in either.
    The gauntlet is behaving correctly -- it will not judge a cell it cannot replay or cost.

    ONLY MT5 CAN CLOSE IT. `free_data` serves DAILY bars; the gap is hourly, and hourly bars for
    these instruments exist only in the broker terminal. So this step is a no-op on the research
    VPS and does the real work on the trading box, and it says which host it is on rather than
    reporting a false zero.
    """
    cov = _read(BASE / "reports" / "BACKTEST_COVERAGE.json") or {}
    charts = {p.stem.rpartition("_")[0].upper()
              for p in (BASE / "data" / "universe").glob("*_*.parquet")}
    try:
        import MetaTrader5  # noqa: F401
        terminal = True
    except Exception:                             # noqa: BLE001 - absence is the answer here
        terminal = False
    return {"symbols_with_bars": len(charts),
            "held_no_bars": cov.get("held_no_bars"),
            "held_no_costs": cov.get("held_no_costs"),
            "symbols_no_bars": (cov.get("symbols_no_bars") or [])[:25],
            "symbols_no_costs": (cov.get("symbols_no_costs") or [])[:25],
            "mt5_terminal": terminal,
            "note": ("bars are fetchable only where the MT5 terminal runs; on a host without it "
                     "this step is a no-op and the gap stays reported rather than silently zero")}


def miner_conversion() -> dict[str, Any]:
    """How much of the mined corpus has become an executable candidate.

    THE GAUGE THE DASHBOARD GOT WRONG. `check_miner_conversion` keys RAW miner rows by
    (family|symbol|session) -- and `family` is present on ZERO rows of every miner, because
    miners emit observations (swap_diff, month, hit_rate), not strategies. So every row hashed to
    `unknown|*|*`: broker_swaps' 35,156 rows collapsed to "1 distinct mechanism", eleven miners
    read 100.0% duplicate, and the panel said 48 of 50 miners convert nothing. The compiler had
    in fact accounted 178,753 rows into 364 executable candidates and 25,207 deepening tasks.
    This measures the COMPILER's output, which is where conversion actually happens.
    """
    doc = _read(BASE / "data" / "hypotheses" / "miner_candidates.json") or {}
    deep = _read(BASE / "data" / "hypotheses" / "miner_deepening_queue.json") or {}
    rows = doc.get("hypotheses") if isinstance(doc.get("hypotheses"), list) else []
    queue = deep.get("tasks") if isinstance(deep.get("tasks"), list) else deep
    return {"rows_accounted": doc.get("rows_accounted"),
            "executable_candidates": len(rows),
            "deepening_tasks": len(queue) if isinstance(queue, (list, dict)) else None,
            "compiled_at": doc.get("compiled_at"),
            "per_source": len(doc.get("per_source") or {})}


def organ_liveness() -> dict[str, Any]:
    """Are the always-on organs actually producing -- crawler, frontier, LLM absorption?

    NAMED INDIVIDUALLY, NOT ROLLED INTO ONE "ok". Each of these fails in its own way and needs
    its own repair: a crawler with no network writes nothing, a frontier cycle with no API key
    writes an empty plan, and both look identical in a single boolean. Staleness is measured
    against the artifact's mtime because these organs write on their own cadence and a run that
    produced no NEW rows is still a run that happened.
    """
    now = datetime.now(UTC)
    out: dict[str, Any] = {}
    for name, rel in (("world_crawler", "data/intelligence"),
                      ("frontier_intel", "reports/FRONTIER_INTELLIGENCE.json"),
                      ("frontier_gaps", "reports/FRONTIER_GAPS.json"),
                      ("deep_forest", "reports/DEEP_FOREST.json"),
                      ("edge_search", "data/hypotheses/edge_search_results.json"),
                      ("miner_candidates", "data/hypotheses/miner_candidates.json")):
        path = BASE / rel
        if not path.exists():
            out[name] = {"status": "ABSENT", "path": rel}
            continue
        newest = path
        if path.is_dir():
            files = [p for p in path.rglob("*.json")]
            if not files:
                out[name] = {"status": "EMPTY", "path": rel}
                continue
            newest = max(files, key=lambda p: p.stat().st_mtime)
        # THE ARTIFACT'S OWN STAMP BEATS ITS mtime, and on a git checkout the mtime is simply
        # wrong: it records when GIT WROTE THE FILE, not when the organ ran. Measured
        # 2026-09-06 -- FRONTIER_INTELLIGENCE.json showed 7.6h by mtime while its own
        # `generated_utc` said 2026-09-05T23:15:25, and DEEP_FOREST.json showed 32.1h against an
        # internal stamp a full day older still. Reporting the mtime told the principal four
        # organs were stale using a clock that measures `git checkout`, which is a fact about
        # this container and not about whether anything is running. The internal stamp travels
        # with the artifact and means the same thing on every host.
        stamp = None
        doc = _read(newest)
        if isinstance(doc, dict):
            for field in ("generated_utc", "generated_at", "compiled_at", "swept_at",
                          "measured_at", "at"):
                raw = doc.get(field)
                if isinstance(raw, str) and len(raw) > 15:
                    try:
                        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        stamp = stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
                        break
                    except ValueError:
                        continue
        basis = "artifact stamp" if stamp else "file mtime (no internal stamp; on a git "\
                                              "checkout this measures the checkout, not the run)"
        age_h = ((now - stamp).total_seconds() / 3600 if stamp
                 else (now.timestamp() - newest.stat().st_mtime) / 3600)
        out[name] = {"status": "FRESH" if age_h < 6 else "STALE",
                     "age_h": round(age_h, 1), "newest": newest.name, "basis": basis}
    # BOTH CARRIERS, because the key has two and checking one reports a false ABSENT. The
    # desk's own loader (`gpt_hunter._credentials`) reads data/secrets/llm_panel.json FIRST and
    # falls back to the environment; an earlier version of this function checked only the
    # environment and told the principal the LLM organs could not run while the key sat in the
    # secrets file. A liveness probe that asks a different question from the consumer is not a
    # probe, it is a second opinion -- so this asks exactly what the consumer asks.
    #
    # PRESENT/ABSENT ONLY. Never the value, never a prefix, never the length: a secret that
    # reaches a report reaches every reader of that report, and this one is published.
    import os
    carriers = []
    secret_file = ROOT / "data" / "secrets" / "llm_panel.json"
    doc = _read(secret_file)
    if isinstance(doc, dict) and (doc.get("api_key") or doc.get("key")):
        carriers.append("data/secrets/llm_panel.json")
    if os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        carriers.append("environment")
    out["llm_key"] = {"status": "PRESENT" if carriers else "ABSENT",
                      "carriers": carriers,
                      "note": ("" if carriers else
                               "neither data/secrets/llm_panel.json nor OPENROUTER_API_KEY on "
                               "this host -- LLM-backed organs cannot run HERE, which is a "
                               "host fact and says nothing about the box or the VPS")}
    return out


def blueprint_coverage() -> dict[str, Any]:
    """The mandate's three declarations, as the closure report last computed them.

    READ FROM THE ARTIFACT, NOT RECOMPUTED HERE. `closure_report` walks every capability three
    times over and takes ~10 minutes on this tree; recomputing it inside a measurement that runs
    before AND after every step would spend an hour of the night's budget answering the same
    question twenty times. The step below regenerates it; this reports what is on disk and how
    old that is, which is the honest shape of "the last time anyone computed coverage".
    """
    doc = _read(BASE / "reports" / "TIER6_CLOSURE.json")
    if not isinstance(doc, dict):
        return {"status": "ABSENT -- coverage has never been computed on this host"}
    return {"architectural_pct": doc.get("architectural_coverage_pct"),
            "operational_pct": doc.get("operational_coverage_pct"),
            "measurement_pct": doc.get("measurement_coverage_pct"),
            "measurement_denominator": doc.get("measurement_denominator"),
            "declarations": doc.get("declarations"),
            "owing_rent": doc.get("owing_rent"),
            "chains_complete": doc.get("chains_complete"),
            "computed_at": doc.get("generated_at")}


def stale_and_broken() -> dict[str, Any]:
    """Whatever the issue board can see, and which of it is safe to repair automatically."""
    try:
        from issue_board import collect
    except ImportError as exc:
        return {"status": f"UNAVAILABLE ({exc})"}
    issues = collect()
    return {"open": len(issues),
            "auto_repairable": sum(1 for i in issues if getattr(i, "auto", False)),
            "keys": [i.key for i in issues][:25]}


def lesson_orphans() -> dict[str, Any]:
    """Lessons the desk can no longer reach -- absorbed memory that has silently fallen out."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from lessons import orphans
    except Exception as exc:                      # noqa: BLE001 - reported, never guessed
        return {"status": f"UNAVAILABLE ({type(exc).__name__}: {exc})"}
    try:
        unreached, lost = orphans()
    except Exception as exc:                      # noqa: BLE001
        return {"status": f"FAILED ({type(exc).__name__}: {exc})"}
    return {"unreached": len(unreached), "lost": len(lost),
            "names": [str(x) for x in list(unreached)[:10]]}


# --------------------------------------------------------------- the run

#: Each step: (name, what it measures, what closes it). The repair is the SAME entry point the
#: hourly cycle uses -- never a private re-implementation with its own thresholds.
STEPS: tuple[tuple[str, Any, str, tuple[str, ...]], ...] = (
    # ORDER IS THE FUNNEL'S OWN ORDER, and it is not cosmetic: compiling miner rows into
    # candidates before the docket sweep means tonight's new candidates are backtested tonight
    # rather than waiting for tomorrow, and certifying before enrolling means a certificate
    # minted at 00:15 gets its forward clock at 00:20 instead of losing a day. Each step's
    # measurement is taken again after it runs, so the report shows what the night actually
    # moved rather than what it attempted.
    # BARS FIRST. Every stage below refuses a symbol it cannot replay, so fetching missing charts
    # before compiling and sweeping is what turns 15,275 refused cells into judged ones. On a
    # host with no terminal this is a no-op that still reports the gap.
    ("acquire_bars", bar_coverage,
     "scripts/download_remaining.py", ()),
    ("compile_miners", miner_conversion,
     "research/miner_candidate_compiler.py", ()),
    ("compile_anomalies", lambda: {"note": "anomaly rows -> executable candidates"},
     "research/compile_anomalies.py", ()),
    ("compile_weak_signals", lambda: {"note": "sub-threshold leads -> cheap hypotheses"},
     "research/weak_signal_compiler.py", ()),
    ("merge_docket", lambda: {"note": "every compiled source merged into one docket"},
     "research/merge_hypotheses.py", ()),
    ("backtest_docket", untested_cells,
     "side_channels/run_external_backtest.py", ()),
    ("certify_survivors", uncertified_survivors,
     "scripts/external_gauntlet.py", ()),
    ("enrol_clocks", clockless_certificates,
     "research/shadow_forward.py", ()),
    ("repair_stale", stale_and_broken,
     "research/issue_board.py", ("--apply",)),
    ("refresh_breadth", breadth_gaps,
     "scripts/check_miner_conversion.py", ()),
    ("rebuild_dashboard", lambda: {"note": "always rebuilt so the night's work is visible"},
     "scripts/build_zentech_state.py", ()),
    # THE CLOSURE REPORT IS REGENERATED LAST, after the night's work has moved the tree. A
    # coverage report that is only ever run by hand describes whatever the tree looked like the
    # last time someone remembered -- and the whole point of §159 is that the three declarations
    # are computed from the CURRENT state, not from an earlier reading of it. Running it after
    # everything else means the numbers describe the desk the night leaves behind.
    ("closure_report", blueprint_coverage,
     "blueprint/closure_report.py", ("--write",)),
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually run the repairs; without it, measure and report only")
    ap.add_argument("--only", default="", help="run one step by name")
    args = ap.parse_args(argv)

    started = datetime.now(UTC)
    report: dict[str, Any] = {"started_at": started.isoformat(timespec="seconds"),
                              "applied": bool(args.apply), "steps": {}}
    for name, measure, script, extra in STEPS:
        if args.only and args.only != name:
            continue
        try:
            before = measure()
        except Exception as exc:                  # noqa: BLE001 - a broken measure is a finding
            report["steps"][name] = {"measure_failed": f"{type(exc).__name__}: {exc}"}
            print(f"{name:20s} MEASURE FAILED {type(exc).__name__}: {exc}", flush=True)
            continue
        entry: dict[str, Any] = {"before": before, "script": script}
        print(f"{name:20s} {json.dumps(before, default=str)[:150]}", flush=True)
        if args.apply:
            entry["run"] = _run(script, extra)
            try:
                entry["after"] = measure()
            except Exception as exc:              # noqa: BLE001
                entry["after"] = {"measure_failed": f"{type(exc).__name__}: {exc}"}
            print(f"{'':20s} -> {json.dumps(entry['run'], default=str)[:150]}", flush=True)
        report["steps"][name] = entry

    # REPORTED EVERY RUN, whether or not a step touched them. Both are questions about whether
    # the desk is still itself: organs that stopped producing, and lessons that have fallen out
    # of reach. Neither has a repair that is safe to automate -- a dead crawler needs a human to
    # ask why, and an unreachable lesson is a memory defect, not a job to rerun.
    report["organs"] = organ_liveness()
    report["lessons"] = lesson_orphans()
    report["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    report["wall_s"] = round((datetime.now(UTC) - started).total_seconds(), 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nnightly catch-up {'APPLIED' if args.apply else 'MEASURED'} in "
          f"{report['wall_s']:.0f}s -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
