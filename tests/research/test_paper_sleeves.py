"""R0102 paper-sleeve auto-spawn -- every Stage-A survivor gets a clock, NEVER over the Holm cap.

The load-bearing behaviours pinned here: a corrected SCREEN-INTERESTING verdict spawns a paper
sleeve (state file + roster row, so the clock pays multiplicity from birth); at 12/12 the spawn
QUEUES instead (spawning over cap would raise every standing candidate's bar); the wait queue is
ordered by capacity runway SHORTEST FIRST (L1.18a -- a short-runway edge loses everything by
waiting); re-runs are idempotent; an absent/uncorrected verdict store REFUSES loudly; SCREEN-WEAK
and NOT-A-CANDIDATE can never qualify.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_paper_sleeve_spawner import run

from libs.research.paper_sleeves import (
    Candidate,
    decide,
    order_queue,
    parse_screen_verdicts,
    standing_names,
)

# ---------------------------------------------------------------------------------- fixtures


def _cohort(m: int, cap: int = 12, complete: bool = True, slots: list[str] | None = None) -> dict:
    return {"m_concurrent": m, "cap": cap, "complete": complete, "over_cap": m > cap,
            "idle_slots": max(0, cap - m),
            "slots": [{"name": n} for n in (slots or [])]}


def _trial(name: str, verdict: str, ic_t: float = 4.0, corrected: float = 0.9,
           is_candidate: bool = True, capacity: float | None = None) -> dict:
    t = {"name": name, "verdict": "SCREEN-INTERESTING", "verdict_adjusted": verdict,
         "ic_t_stat": ic_t, "sharpe_best_corrected": corrected, "is_candidate": is_candidate,
         "n": 1000}
    if capacity is not None:
        t["capacity_usd"] = capacity
    return t


def _store(root: Path, axis: str, trials: list[dict]) -> None:
    d = root / "reports/axis_screens"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{axis}.json").write_text(json.dumps({"axis": axis, "trials": trials}), "utf-8")


SURVIVOR = "SCREEN-INTERESTING (survives correction+multiplicity)"


# ------------------------------------------------------------------------- spawn from a verdict


def test_spawn_from_fake_verdict_creates_state_file_and_roster_row(tmp_path: Path) -> None:
    _store(tmp_path, "mining", [_trial("miner_outflow->btc_1d", SURVIVOR)])
    out, rc = run(tmp_path, cohort=_cohort(10), book_usd=50_000.0)
    assert rc == 0
    assert out["status"].startswith("SPAWNED 1")
    state = tmp_path / "data/mining_miner_outflow_btc_1d_shadow_state.json"
    assert state.exists(), "a spawn without a birth certificate is not a clock"
    doc = json.loads(state.read_text("utf-8"))
    assert doc["shadow_start"], "shadow_start is what slot_registry reads -- it must be stamped"
    assert doc["trial"] == "miner_outflow->btc_1d"
    roster = json.loads((tmp_path / "data/shadow_sleeves.json").read_text("utf-8"))
    assert "mining_miner_outflow_btc_1d" in roster, (
        "a sleeve outside the roster is a clock the cohort does not count -- m understated, "
        "every bar loosened: the forbidden direction")
    ledger = json.loads((tmp_path / "data/paper_sleeve_queue.json").read_text("utf-8"))
    assert ledger["spawned"][0]["name"] == "mining_miner_outflow_btc_1d"
    assert ledger["spawned"][0]["ts"] and ledger["spawned"][0]["reason"]


def test_weak_and_noncandidate_verdicts_never_qualify(tmp_path: Path) -> None:
    _store(tmp_path, "fx", [
        _trial("em_basket->btc_5d", "SCREEN-WEAK (Sharpe fails the 0.5 floor once corrected)"),
        _trial("SHIFT_em_basket_plus1d->btc_1d",
               "NOT-A-CANDIDATE (future-peeking shift diagnostic)", is_candidate=False),
    ])
    out, rc = run(tmp_path, cohort=_cohort(0), book_usd=50_000.0)
    assert rc == 0
    assert out["status"] == "NO-CANDIDATES"
    assert not out["queued"] and not out["spawned"]
    assert not list(tmp_path.glob("data/*_shadow_state.json"))


# ------------------------------------------------------------- over-cap queues, never spawns


def test_over_cap_queues_instead_of_spawning(tmp_path: Path) -> None:
    _store(tmp_path, "mining", [_trial("miner_outflow->btc_1d", SURVIVOR)])
    out, rc = run(tmp_path, cohort=_cohort(12), book_usd=50_000.0)
    assert rc == 0
    assert out["status"] == "QUEUED-AT-CAP"
    assert [q["name"] for q in out["queued"]] == ["mining_miner_outflow_btc_1d"]
    assert out["queued"][0]["ts"] and out["queued"][0]["reason"]
    assert not out["spawned"]
    assert not (tmp_path / "data/mining_miner_outflow_btc_1d_shadow_state.json").exists(), (
        "spawning at 12/12 pushes over_cap and raises every standing candidate's bar")


def test_incomplete_cohort_spawns_nothing(tmp_path: Path) -> None:
    # complete=False means a slot source was unreadable: m is a LOWER BOUND. Spawning against a
    # lower bound is how the cap gets breached while every number on screen says it was not.
    _store(tmp_path, "mining", [_trial("miner_outflow->btc_1d", SURVIVOR)])
    out, rc = run(tmp_path, cohort=_cohort(3, complete=False), book_usd=50_000.0)
    assert rc == 0
    assert out["status"] == "QUEUED-AT-CAP"
    assert "lower bound" in out["why_free"]
    assert not out["spawned"]


def test_partial_capacity_spawns_shortest_runway_first_and_queues_the_rest(tmp_path: Path) -> None:
    _store(tmp_path, "mining", [
        _trial("edge_short_runway->btc_1d", SURVIVOR, ic_t=3.0, capacity=100_000.0),
        _trial("edge_long_runway->btc_1d", SURVIVOR, ic_t=3.0, capacity=10_000_000.0),
        _trial("edge_unknown_capacity->btc_1d", SURVIVOR, ic_t=9.9),
    ])
    out, rc = run(tmp_path, cohort=_cohort(11), book_usd=50_000.0)
    assert rc == 0
    spawned = [s["name"] for s in out["spawned"]]
    assert spawned == ["mining_edge_short_runway_btc_1d"], (
        "one free slot must go to the SHORTEST runway -- the edge that loses everything by "
        "waiting -- not to arrival order or the strongest ic_t")
    assert [q["name"] for q in out["queued"]] == [
        "mining_edge_long_runway_btc_1d", "mining_edge_unknown_capacity_btc_1d"]


# ------------------------------------------------------------------------------- queue ordering


def test_queue_ordered_by_runway_shortest_first() -> None:
    cands = [
        Candidate(name="a_unknown", axis="x", trial="a", ic_t=9.0, capacity_usd=None),
        Candidate(name="b_long", axis="x", trial="b", ic_t=1.0, capacity_usd=5_000_000.0),
        Candidate(name="c_short", axis="x", trial="c", ic_t=1.0, capacity_usd=50_000.0),
    ]
    ordered = [c.name for c in order_queue(cands, book_usd=50_000.0)]
    assert ordered == ["c_short", "b_long", "a_unknown"], (
        "shortest runway first; UNKNOWN capacity is runway inf and must sort LAST -- an "
        "unmeasured edge never jumps ahead of one measurably about to expire")


def test_decide_orders_queue_by_runway_even_when_nothing_spawns() -> None:
    cands = [
        Candidate(name="b_long", axis="x", trial="b", capacity_usd=5_000_000.0),
        Candidate(name="c_short", axis="x", trial="c", capacity_usd=50_000.0),
    ]
    d = decide(cands, standing=set(), cohort=_cohort(12), book_usd=50_000.0)
    assert d["free_slots"] == 0
    assert [c.name for c in d["queue"]] == ["c_short", "b_long"]


# ---------------------------------------------------------------------------------- idempotency


def test_rerun_is_idempotent_no_duplicate_spawn_and_stable_queue_ts(tmp_path: Path) -> None:
    _store(tmp_path, "mining", [
        _trial("spawner->btc_1d", SURVIVOR),
        _trial("waiter->btc_1d", SURVIVOR, ic_t=2.0),
    ])
    out1, _ = run(tmp_path, cohort=_cohort(11), book_usd=50_000.0)
    first_ts = out1["queued"][0]["ts"]
    state = tmp_path / "data/mining_spawner_btc_1d_shadow_state.json"
    born = json.loads(state.read_text("utf-8"))["shadow_start"]

    # second pass: the spawned sleeve is now standing (state file + roster + ledger), still 12/12
    out2, rc = run(tmp_path, cohort=_cohort(12, slots=["mining_spawner_btc_1d"]),
                   book_usd=50_000.0)
    assert rc == 0
    assert len(out2["spawned"]) == 1, "re-running must not spawn the same hypothesis twice"
    assert json.loads(state.read_text("utf-8"))["shadow_start"] == born, (
        "rewriting shadow_start resets a clock's forward evidence -- never overwrite")
    roster = json.loads((tmp_path / "data/shadow_sleeves.json").read_text("utf-8"))
    assert roster.count("mining_spawner_btc_1d") == 1
    assert [q["name"] for q in out2["queued"]] == ["mining_waiter_btc_1d"]
    assert out2["queued"][0]["ts"] == first_ts, "first-seen stamp must survive re-runs"


def test_same_signal_root_at_two_horizons_is_one_sleeve(tmp_path: Path) -> None:
    _store(tmp_path, "mining", [
        _trial("hash_ribbon->btc_5d", SURVIVOR, ic_t=2.5),
        _trial("hash_ribbon->btc_20d", SURVIVOR, ic_t=4.5),
    ])
    parsed = parse_screen_verdicts(tmp_path / "reports/axis_screens")
    assert len(parsed["candidates"]) == 1, (
        "two horizons of one construction are one bet -- two clocks would spend two Holm slots "
        "on one hypothesis")
    assert parsed["candidates"][0].ic_t == 4.5, "keep the strongest, deterministically"


def test_dedupe_against_standing_clock_by_signal_root(tmp_path: Path) -> None:
    _store(tmp_path, "crypto", [_trial("stablecoin_supply_momentum->btc_1d", SURVIVOR)])
    out, rc = run(tmp_path, cohort=_cohort(5, slots=["stablecoin_supply_momentum"]),
                  book_usd=50_000.0)
    assert rc == 0
    assert out["status"] == "ALL-STANDING"
    assert out["duplicates"] and not out["spawned"] and not out["queued"]


# ------------------------------------------------------------------------------------- refusals


def test_absent_verdict_store_refuses_loudly(tmp_path: Path) -> None:
    out, rc = run(tmp_path, cohort=_cohort(0), book_usd=50_000.0)
    assert rc == 2
    assert out["status"] == "REFUSED-NO-INPUT"
    assert "absent" in out["why"]


def test_store_without_corrected_verdicts_refuses(tmp_path: Path) -> None:
    # raw harness output only -- no verdict_adjusted anywhere: the correction layer never ran,
    # and raw Sharpe is inflated up to 4.47x at 20d. Nothing may spawn from it.
    d = tmp_path / "reports/axis_screens"
    d.mkdir(parents=True)
    (d / "raw.json").write_text(json.dumps(
        {"axis": "raw", "trials": [{"name": "x->btc_5d", "verdict": "SCREEN-INTERESTING"}]}),
        "utf-8")
    out, rc = run(tmp_path, cohort=_cohort(0), book_usd=50_000.0)
    assert rc == 2
    assert out["status"] == "REFUSED-NO-INPUT"
    assert "verdict_adjusted" in out["why"]


def test_refusal_preserves_prior_queue(tmp_path: Path) -> None:
    _store(tmp_path, "mining", [_trial("miner_outflow->btc_1d", SURVIVOR)])
    run(tmp_path, cohort=_cohort(12), book_usd=50_000.0)
    (tmp_path / "reports/axis_screens/mining.json").unlink()
    out, rc = run(tmp_path, cohort=_cohort(12), book_usd=50_000.0)
    assert rc == 2
    assert [q["name"] for q in out["queued"]] == ["mining_miner_outflow_btc_1d"], (
        "a vanished verdict store must not silently dissolve a lawfully entered wait")


def test_corrupt_roster_refuses_spawn_and_requeues(tmp_path: Path) -> None:
    _store(tmp_path, "mining", [_trial("miner_outflow->btc_1d", SURVIVOR)])
    (tmp_path / "data").mkdir()
    (tmp_path / "data/shadow_sleeves.json").write_text("{corrupt", "utf-8")
    out, rc = run(tmp_path, cohort=_cohort(0), book_usd=50_000.0)
    assert rc == 0
    assert "roster_refusal" in out
    assert [q["name"] for q in out["queued"]] == ["mining_miner_outflow_btc_1d"]
    assert not (tmp_path / "data/mining_miner_outflow_btc_1d_shadow_state.json").exists(), (
        "a clock the cohort cannot count must not be born -- m would be understated and every "
        "bar loosened")


def test_standing_names_reads_slots_state_files_and_ledger(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/cashcarry_shadow_state.json").write_text('{"shadow_start": "2026-06-26"}')
    names = standing_names(_cohort(1, slots=["oi_divergence"]), tmp_path / "data",
                           {"spawned": [{"name": "old_spawn"}]})
    assert {"oi_divergence", "cashcarry", "old_spawn"} <= names
