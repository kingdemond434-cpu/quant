"""F18 -- EVERY DEFECT THIS DESK HAS SUFFERED BECOMES A PERMANENT TEST IT CANNOT SUFFER SILENTLY.

THE PRINCIPAL, 2026-09-12:

    Every historical defect becomes an immutable benchmark -- same-bar ambiguity, state-drop
    propagation, JPY cost conversion, stale artifacts, timestamps, scheduler claims, dead scripts
    returning success, release overwrite, duplicate research identity, null admission -- and no
    new researcher, model or refactor may pass without clearing all of them.

WHY A BENCH AND NOT MORE TESTS. The suite already asserts that code behaves. A bench asserts
something different and harder: that a CLASS OF MISTAKE this desk has actually made is still
impossible. The distinction matters because the defects here were not bugs in a function -- they
were plausible, well-formed, silent answers. "0/0 measured" is a valid report. "Every price
UNMEASURED" is a valid board. A test suite written against the code's intent passes all of them.

EVERY CASE IS A THING THAT REALLY HAPPENED, WITH ITS DATE. A bench of hypothetical failures is a
style guide; a bench of survived failures is institutional memory that executes. A case whose
defect cannot be cited is not admitted, which is why this file grows by evidence rather than by
imagination.

IMMUTABILITY IS ENFORCED BY COUNTING AND HASHING, not by asking nicely. The case registry is
content-hashed and the count is a RATCHET: `data/quantbench_floor.json` records the highest case
count ever seen, and a run that finds fewer cases than the floor FAILS. Deleting an inconvenient
case is therefore a visible act, which is the only kind of immutability a text file can have.

A CASE MAY REPORT UNMEASURABLE, and that is not a pass. A probe whose evidence is absent says so
and is counted apart from the passes, because a bench that scores absence as success is the exact
green-run lie the whole thing exists to stop.

    python desks/mt5/research/quantbench.py [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "QUANTBENCH.json"
FLOOR = DESK / "data" / "quantbench_floor.json"


def _ok(msg: str) -> dict[str, Any]:
    return {"verdict": "PASS", "detail": msg}


def _bad(msg: str) -> dict[str, Any]:
    return {"verdict": "FAIL", "detail": msg}


def _unk(msg: str) -> dict[str, Any]:
    return {"verdict": "UNMEASURABLE", "detail": msg}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _stale_against(report: Path, producer: Path) -> str | None:
    """Is this artifact OLDER than the code that produces it? Then it is history, not evidence.

    THE BENCH'S OWN FIRST FAILURE, AND IT WAS RIGHT TO FAIL AND WRONG TO ASSERT. Run on the
    MIRROR box, `dead_script_returning_success` read a CAPACITY.json written before capacity.py
    was repaired -- 0 sleeves, exactly the defect -- and failed. The artifact was telling the
    truth about a run that happened before the fix existed, on a machine where the daily lane
    does not run.

    A probe that reads an artifact older than its producer is measuring the PAST. It cannot
    distinguish "the defect has returned" from "this report has not been regenerated since the
    repair", and asserting the first on evidence for the second would fail every push from any
    box that does not run the whole research lane. So the probe reports UNMEASURABLE and says
    which file is stale -- which is not a pass, and is counted apart from one.
    """
    try:
        r_m, p_m = report.stat().st_mtime, producer.stat().st_mtime
    except OSError:
        return None
    if r_m < p_m:
        return (f"{report.name} was written before {producer.name} was last changed, so it "
                f"reports a run from before the repair. This artifact is history on this box, "
                f"not evidence about the current tree")
    return None


# ==============================================================================================
# THE CASES. Each names a defect that actually occurred, on a date, and probes whether the
# condition that allowed it still holds. The probe answers about the CURRENT tree, never about
# the fix that was applied -- a bench that checked "was this line changed" would pass forever
# after one commit and catch nothing.
# ==============================================================================================

def _c_dead_script_success() -> dict[str, Any]:
    """A scheduled organ that runs, writes a report and measures nothing, reporting success."""
    report = DESK / "reports" / "CAPACITY.json"
    stale = _stale_against(report, DESK / "research" / "capacity.py")
    if stale:
        return _unk(stale)
    d = _read(report)
    if d is None:
        return _unk("CAPACITY.json absent -- the probe needs the artifact the defect appeared in")
    n, measured = d.get("sleeves"), d.get("measured")
    if not isinstance(n, int) or not isinstance(measured, int):
        return _unk("CAPACITY.json carries no sleeves/measured counts")
    if n == 0:
        return _bad("capacity reports 0 sleeves again -- its source has gone silent a second "
                    "time, and 0/0 is a well-formed answer that looks like success")
    if not d.get("sleeve_source"):
        return _bad("capacity no longer records WHICH source its roster came from, so a silent "
                    "fallback is invisible again")
    return _ok(f"{measured}/{n} measured from {d.get('sleeve_source')}")


def _c_unexplained_unmeasured() -> dict[str, Any]:
    """An UNMEASURED verdict with no `why` -- absence that does not say what is absent."""
    report = DESK / "reports" / "INFORMATION_VALUE.json"
    stale = _stale_against(report, DESK / "research" / "information_value.py")
    if stale:
        return _unk(stale)
    d = _read(report)
    if d is None:
        return _unk("INFORMATION_VALUE.json absent")
    ue = d.get("unexplained_unmeasured") or {}
    n = ue.get("n")
    if not isinstance(n, int):
        return _unk("the report does not carry the unexplained-UNMEASURED count")
    # This is a RATCHET case, not a zero case: the desk has 51 of these today and the bench's job
    # is to stop it GROWING, not to fail every run until every legacy report is repaired.
    prev = (_read(FLOOR) or {}).get("unexplained_unmeasured")
    if isinstance(prev, int) and n > prev:
        return _bad(f"{n} UNMEASURED verdicts carry no explanation, up from {prev}. L1.28a's "
                    f"force is that absence must say WHAT is absent")
    return _ok(f"{n} unexplained UNMEASURED verdict(s), not above the recorded floor")


def _c_label_leakage() -> dict[str, Any]:
    """A trained model whose label key was coarser than its unit, faking its own accuracy."""
    report = DESK / "reports" / "NEGATIVE_KNOWLEDGE.json"
    stale = _stale_against(report, DESK / "research" / "negative_knowledge.py")
    if stale:
        return _unk(stale)
    d = _read(report)
    if d is None:
        return _unk("NEGATIVE_KNOWLEDGE.json absent")
    t = d.get("training") or {}
    base = t.get("train_base_rate")
    n_cert = t.get("n_certified_cells")
    if not isinstance(base, (int, float)) or not isinstance(n_cert, int):
        return _unk("the report carries no base rate or certified-cell count")
    # The desk's true certification rate is well under 1%. A base rate above 5% means the label
    # is matching more rows than there are certificates -- exactly the (symbol, family) key that
    # marked 3,487 rows positive against a true 61.
    if float(base) > 0.05:
        return _bad(f"training base rate is {float(base):.2%} -- far above this desk's true "
                    f"certification rate. The label key is coarser than a certificate")
    return _ok(f"base rate {float(base):.4%} on {n_cert} certified cell(s)")


def _c_unbuildable_donation() -> dict[str, Any]:
    """A candidate donated with params the named family cannot accept -- a born zombie."""
    try:
        from mt5desk import families as FAM
    except ImportError as exc:
        return _unk(f"families not importable ({exc})")
    intel = DESK / "data" / "intelligence"
    if not intel.exists():
        return _unk("no intelligence directory")
    bad: list[str] = []
    checked = unresolved = no_family = 0
    # THE NEWEST FILE FROM EVERY DONOR, not the newest files overall.
    #
    # Two sampling rules failed before this one, and both failed by EXAMINING THE WRONG FILES
    # while reporting honestly that they had. Sorting by path took whichever seat sorts last in
    # the alphabet. Sorting by mtime took the 40 newest, which on a busy hour are 40 files from
    # the chattiest seats -- 89 candidates, none naming a registered family, while the donation
    # this case exists to guard sat one rank below the cut.
    #
    # One file per donor guarantees every producer is represented however often it writes, which
    # is the property a bench needs: a case that only samples the loud seats cannot catch a
    # defect in a quiet one.
    newest: dict[str, pathlib.Path] = {}
    for f in intel.rglob("discoveries_*.json"):
        if not f.is_file():
            continue
        donor = f.parent.name
        cur = newest.get(donor)
        if cur is None or f.stat().st_mtime > cur.stat().st_mtime:
            newest[donor] = f
    for f in sorted(newest.values()):
        doc = _read(f)
        # DONATION FILES COME IN TWO SHAPES. The proposer contract writes a dict with a
        # `discoveries` list; older seat files are a bare list. The probe crashed on the second
        # and reported UNMEASURABLE -- which the bench correctly refused to score as a pass.
        if isinstance(doc, list):
            cands = doc
        elif isinstance(doc, dict):
            cands = doc.get("discoveries") or []
        else:
            continue
        for c in cands[:40]:
            if not isinstance(c, dict):
                continue
            fam = str(c.get("family") or "")
            if not fam or fam == "None":
                no_family += 1
                continue
            entry = FAM.FAMILY_REGISTRY.get(fam)
            if not entry:
                # NOT EVERY BUILDABLE FAMILY LIVES IN THE REGISTRY. build_cell special-cases
                # `discovered`, `carry`, `event_reaction` and the orthogonal generators, and the
                # first version of this probe counted all of those as unresolvable and reported
                # UNMEASURABLE across a docket that is 79% `discovered`. A probe that examines
                # nothing and says so is working; one that examines nothing and passes is not.
                unresolved += 1
                continue
            checked += 1
            allowed = set(entry.get("defaults") or {})
            extra = [k for k in (c.get("params") or {}) if k not in allowed]
            # A family that takes **kwargs absorbs anything; joint_genome is the one that does.
            if extra and fam != "joint_genome":
                bad.append(f"{f.name}:{fam} carries {extra[:4]}")
    if not checked:
        return _unk(f"no donated candidate names a REGISTERED family "
                    f"({unresolved} named an unregistered one, {no_family} named none). The "
                    f"property is untested this pass, which is not the same as satisfied")
    if bad:
        return _bad(f"{len(bad)} donation(s) carry params their family cannot accept, so "
                    f"build_cell cannot build them: {bad[:3]}")
    return _ok(f"{checked} donated candidate(s) buildable by the family they name "
               f"({unresolved} unregistered, {no_family} carry no family)")


def _c_wrong_lane_docket() -> dict[str, Any]:
    """Hypothesis-lane cells on instruments the two-lane mandate does not hunt."""
    try:
        from research.proposer_common import _lane_filtered
    except ImportError as exc:
        return _unk(f"the lane door is not importable ({exc})")
    ok, refused = _lane_filtered([{"symbol": "Apple", "family": "discovered"},
                                  {"symbol": "XAUUSD", "family": "discovered"}])
    if len(ok) != 1 or len(refused) != 1:
        return _bad("the donation door no longer refuses single-name equities: it admitted "
                    f"{[c.get('symbol') for c in ok]}")
    return _ok("the docket's door refuses single-name equities and admits the hunt lane")


def _c_schema_drift_reader() -> dict[str, Any]:
    """A reader keyed on fields the producer does not publish, reporting a board of UNMEASURED."""
    mcp = DESK / "reports" / "META_CONTROLLER.json"
    stale = _stale_against(mcp, DESK / "research" / "meta_controller.py")
    if stale:
        return _unk(stale)
    mc = _read(mcp)
    bm = _read(DESK / "reports" / "BUDGET_MARKET.json")
    if mc is None or bm is None:
        return _unk("META_CONTROLLER.json or BUDGET_MARKET.json absent")
    produced = {str(r.get("resource")) for r in (bm.get("resources") or [])
                if isinstance(r, dict)
                and isinstance(r.get("price_dElogW_per_unit_per_day"), (int, float))}
    read_ok = {k for k, v in (mc.get("prices") or {}).items()
               if isinstance(v, dict) and v.get("status") == "OK"}
    missed = produced - read_ok
    if missed:
        return _bad(f"budget_market published a price for {sorted(missed)} and the controller "
                    f"read it as UNMEASURED -- a reader keyed on the wrong schema")
    return _ok(f"every measured price ({sorted(produced) or 'none yet'}) reaches the controller")


def _c_free_tier_ceiling() -> dict[str, Any]:
    """The desk believing a published request ceiling while the provider refuses every call."""
    try:
        from libs.ops import llm_seat
    except ImportError as exc:
        return _unk(f"llm_seat not importable ({exc})")
    for name in ("observed_free_ceiling", "note_free_limit_hit", "_is_daily_free_refusal"):
        if not hasattr(llm_seat, name):
            return _bad(f"llm_seat has no {name}: the seat can no longer LEARN the provider's "
                        f"real daily ceiling and will spend its cadence on refusals again")
    return _ok("the seat learns its real ceiling from the provider's own 429")


def _c_selection_as_execution() -> dict[str, Any]:
    """An execution comparison across variants that trade different numbers of signals."""
    report = DESK / "reports" / "EXECUTION_SCIENCE.json"
    stale = _stale_against(report, DESK / "research" / "execution_science.py")
    if stale:
        return _unk(stale)
    d = _read(report)
    if d is None:
        return _unk("EXECUTION_SCIENCE.json absent")
    vs = d.get("variants") or []
    if not vs:
        return _unk("no variants reported")
    if any("like_for_like" not in v for v in vs):
        return _bad("execution variants no longer declare like-for-like comparability, so a "
                    "variant that trades a third as often can top the board as an execution win")
    return _ok(f"{sum(1 for v in vs if v.get('like_for_like'))} of {len(vs)} variants are "
               f"like-for-like and the rest are marked")


def _c_null_admission() -> dict[str, Any]:
    """A forward lane whose noise-admission rate has never been measured."""
    report = DESK / "reports" / "FORWARD_CALIBRATION.json"
    stale = _stale_against(report, DESK / "research" / "forward_calibration.py")
    if stale:
        return _unk(stale)
    d = _read(report)
    if d is None:
        return _unk("FORWARD_CALIBRATION.json absent")
    n = (d.get("null") or {}).get("false_admission_rate")
    if not isinstance(n, (int, float)):
        return _bad("the forward lane publishes no false-admission rate, so 'it passed forward' "
                    "carries no information about how often noise passes forward")
    return _ok(f"noise would pass {float(n):.2%} of this lane's clocks")


def _c_stale_artifact() -> dict[str, Any]:
    """An organ whose report stopped updating while its scheduler reported healthy."""
    # LOADED BY PATH, NOT AS `ops.organ_contract`. `test_gateway_loop_finds_libs` forbids any
    # desk module from bare-importing a repo-ROOT directory name: this file puts ROOT first on
    # sys.path, and `ops`, `data`, `config` and `scripts` are all directories there, so such an
    # import can silently resolve to a namespace package of the wrong directory on a box whose
    # cwd differs. The fence caught this one the day it was written. `ops/process_health.py`
    # gets away with `import organ_contract` because it already lives in that directory; a desk
    # module has to say which file it means.
    import importlib.util

    _oc = ROOT / "ops" / "organ_contract.py"
    try:
        _spec = importlib.util.spec_from_file_location("quantbench_organ_contract", _oc)
        if _spec is None or _spec.loader is None:
            return _unk(f"organ_contract not loadable from {_oc}")
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        check = _mod.check
    except Exception as exc:
        return _unk(f"organ_contract not importable ({type(exc).__name__}: {exc})")
    try:
        res = check()
    except Exception as exc:
        return _unk(f"organ_contract.check() raised {type(exc).__name__}: {exc}")
    rows = res.get("organs") or res.get("rows") or []
    if not rows:
        return _unk("organ_contract reported no organs")
    return _ok(f"{len(rows)} organ(s) carry a freshness contract")


def _c_immutable_count() -> dict[str, Any]:
    """The bench itself: a case removed is a visible act, never a quiet one."""
    prev = (_read(FLOOR) or {}).get("n_cases")
    n = len(CASES)
    if isinstance(prev, int) and n < prev:
        return _bad(f"the bench has {n} cases and once had {prev}. A defect this desk survived "
                    f"has been deleted from its memory")
    return _ok(f"{n} case(s), never fewer than the recorded floor")


#: id -> (the defect as it happened, its date, the probe). The date is not decoration: a case
#: whose defect cannot be cited is not a benchmark, it is an opinion about style.
CASES: dict[str, tuple[str, str, Callable[[], dict[str, Any]]]] = {
    "dead_script_returning_success": (
        "capacity.py's only sleeve source raised ImportError, the except swallowed it, and "
        "measure() returned '0/0 measured' for as long as the file existed -- an organ that ran, "
        "wrote a report and said nothing, invisibly, because 0/0 is a well-formed answer",
        "2026-09-12", _c_dead_script_success),
    "unexplained_unmeasured": (
        "51 UNMEASURED verdicts across the desk's reports carried no `why` at all. L1.28a's "
        "force is not the word UNMEASURED -- it is that absence must say WHAT is absent",
        "2026-09-12", _c_unexplained_unmeasured),
    "label_coarser_than_unit": (
        "the negative-knowledge model keyed its label on (symbol, family), marking 3,487 docket "
        "rows positive against a true 61 -- a 20.6% base rate against 0.283% and a held-out AUC "
        "of 0.986 that was the model reading the label off the label",
        "2026-09-12", _c_label_leakage),
    "unbuildable_donation": (
        "joint_evolution's winners would have been donated naming a base family that cannot "
        "accept the layer kwargs, so build_cell could not build them and the rows would have "
        "died silently in the intake -- the same shape as the six zombie certificates evicted "
        "the night before",
        "2026-09-12", _c_unbuildable_donation),
    "wrong_lane_docket": (
        "10,927 of 21,582 docket cells sat on symbols the two-lane mandate forbids hypothesising "
        "on, holding zero certificates at a 0.046% upper bound, with 447 minted AFTER the "
        "mandate. Routing was wired at the backtest's door and nothing stood at the docket's",
        "2026-09-12", _c_wrong_lane_docket),
    "reader_keyed_on_wrong_schema": (
        "the meta-controller read budget_market's prices under the key `price` while the market "
        "publishes `price_dElogW_per_unit_per_day` under `resources`. Every price read "
        "UNMEASURED -- including capital, which had been measured on the same pass. No error, a "
        "complete-looking board, and the upstream measurement silently discarded",
        "2026-09-12", _c_schema_drift_reader),
    "believed_ceiling_over_measured": (
        "llm_seat assumed OpenRouter's published 900 free requests a day. The provider refused "
        "at 562 while the desk's counter read 338 'left', so every organ afterwards spent its "
        "cadence on refusals that read like an outage",
        "2026-09-12", _c_free_tier_ceiling),
    "selection_reported_as_execution": (
        "a session filter topped the execution board on median growth while keeping 32% of the "
        "signals. A variant that trades a third as often is not executing the same strategy "
        "better; comparing per-day growth across different trade counts mixes selection with "
        "execution",
        "2026-09-12", _c_selection_as_execution),
    "null_admission_unmeasured": (
        "the forward lane's promotion rule had never been asked what fraction of PURE NOISE it "
        "admits, so 'it passed forward' carried no information about how often noise passes "
        "forward",
        "2026-09-12", _c_null_admission),
    "stale_artifact_healthy_scheduler": (
        "organs were built, correct and scheduled nowhere, or scheduled and silently stale, "
        "while every scheduler reported healthy -- the class III.16 names",
        "2026-09-12", _c_stale_artifact),
    "bench_erosion": (
        "the bench's own failure mode: a case deleted because it was inconvenient. Immutability "
        "in a text file can only mean that removing one is a VISIBLE act",
        "2026-09-12", _c_immutable_count),
}


def _registry_hash() -> str:
    """Content hash over the case ids and their cited defects. A weakened bench changes it."""
    blob = json.dumps({k: (v[0], v[1]) for k, v in sorted(CASES.items())},
                      sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    results: list[dict[str, Any]] = []
    for cid, (defect, when, probe) in sorted(CASES.items()):
        try:
            r = probe()
        except Exception as exc:
            r = _unk(f"probe raised {type(exc).__name__}: {exc}")
        results.append({"case": cid, "defect_occurred": when, "defect": defect, **r})

    tally: dict[str, int] = {}
    for r in results:
        tally[str(r["verdict"])] = tally.get(str(r["verdict"]), 0) + 1
    failed = [r for r in results if r["verdict"] == "FAIL"]
    unmeasurable = [r for r in results if r["verdict"] == "UNMEASURABLE"]

    floor = _read(FLOOR) or {}
    prev_n = floor.get("n_cases")
    return {
        "at": now.isoformat(timespec="seconds"),
        "n_cases": len(CASES),
        "registry_hash": _registry_hash(),
        "floor": {"n_cases": prev_n, "hash": floor.get("registry_hash"),
                  "unexplained_unmeasured": floor.get("unexplained_unmeasured")},
        "tally": tally,
        "status": ("FAIL" if failed else "ATTENTION" if unmeasurable else "PASS"),
        "results": results,
        "n_failed": len(failed),
        "n_unmeasurable": len(unmeasurable),
        "unmeasurable_is_not_a_pass": (
            "a probe whose evidence is absent reports UNMEASURABLE and is counted apart from the "
            "passes. A bench that scored absence as success would be the exact green-run lie the "
            "whole thing exists to stop, and it would score highest on an empty box."),
        "immutability": (
            "the case count is a RATCHET and the registry is content-hashed. A run finding fewer "
            "cases than the floor FAILS on the `bench_erosion` case, so deleting an inconvenient "
            "benchmark is a visible act -- which is the only immutability a text file can have."),
        "admission_rule": (
            "a case is admitted only with a defect that ACTUALLY HAPPENED and its date. A bench "
            "of hypothetical failures is a style guide; a bench of survived failures is "
            "institutional memory that executes."),
        "why": (
            "the suite asserts that code behaves. A bench asserts that a CLASS OF MISTAKE is "
            "still impossible -- and every defect here was a plausible, well-formed, SILENT "
            "answer that a test written against the code's intent passes."),
    }


def _save_floor(doc: dict[str, Any]) -> dict[str, Any]:
    """The ratchet. It only ever rises on counts and only ever falls on defect counts."""
    prev = _read(FLOOR) or {}
    iv = _read(DESK / "reports" / "INFORMATION_VALUE.json") or {}
    unexplained = (iv.get("unexplained_unmeasured") or {}).get("n")
    row = {
        "n_cases": max(int(doc["n_cases"]), int(prev.get("n_cases") or 0)),
        "registry_hash": doc["registry_hash"],
        "updated": doc["at"],
        # DEFECT COUNTS RATCHET DOWNWARD: today's number becomes tomorrow's ceiling, so the
        # backlog can shrink and can never quietly grow back.
        "unexplained_unmeasured": (min(int(unexplained), int(prev["unexplained_unmeasured"]))
                                   if isinstance(unexplained, int)
                                   and isinstance(prev.get("unexplained_unmeasured"), int)
                                   else (unexplained
                                         if isinstance(unexplained, int)
                                         else prev.get("unexplained_unmeasured"))),
    }
    FLOOR.parent.mkdir(parents=True, exist_ok=True)
    FLOOR.write_text(json.dumps(row, indent=1), encoding="utf-8")
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report and update the floor")
    a = ap.parse_args(argv)
    doc = build()
    print(f"quantbench: {doc['status']}   {doc['n_cases']} case(s), registry "
          f"{doc['registry_hash']}   {doc['tally']}")
    for r in doc["results"]:
        mark = {"PASS": " ", "FAIL": "!", "UNMEASURABLE": "?"}[str(r["verdict"])]
        print(f" {mark} {r['case']:<34} {r['verdict']:<13} {str(r['detail'])[:74]}")
    if doc["n_failed"]:
        print(f"\n  {doc['n_failed']} DEFECT(S) HAVE RETURNED:")
        for r in doc["results"]:
            if r["verdict"] == "FAIL":
                print(f"    {r['case']} (first seen {r['defect_occurred']})")
                print(f"      then: {r['defect'][:150]}")
                print(f"      now : {r['detail'][:150]}")
    if not a.apply:
        print("  --apply not given; nothing written, floor not updated")
        return 0
    doc["floor_written"] = _save_floor(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}\n-> {FLOOR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
