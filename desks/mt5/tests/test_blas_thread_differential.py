"""The BLAS thread differential: sampling, inputs, comparison, the write guard and one real run.

The end-to-end test runs the SEALED `external_gauntlet.run_gauntlet` in fresh subprocesses on a
small synthetic fixture (frozen cells whose series are synthetic), so the harness is exercised
against the real judge without a recorded sweep or a series cache on this machine.
"""
from __future__ import annotations

import copy
import json
import os
import pickle
import stat
import subprocess
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import blas_threads as bt  # noqa: E402
from scripts import blas_thread_differential as bd  # noqa: E402


# ------------------------------------------------------------------------------ fixtures
def _cells(n: int, days: int = 420, seed: int = 7) -> list[dict]:
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2022-01-03", periods=days)
    base = rng.normal(0.0, 0.01, days)
    out = []
    for k in range(n):
        v = 0.6 * base + rng.normal(0.0004, 0.01, days)
        out.append({"sym": ("EURUSD", "XAUUSD", "GBPUSD", "USDJPY")[k % 4],
                    "family": "session_range_breakout", "params": {"k": k}, "timeframe": "H1",
                    "df": None, "sigs": None, "costs": None,
                    "_cached_ds": pd.Series(v, index=idx),
                    "_cached_ds3": pd.Series(v - 0.0002, index=idx),
                    "_ckey": f"synthetic{k}", "_last_day": idx[-1]})
    return out


def _fixture(path: Path, n: int, rebuild: list[dict] | None = None) -> Path:
    meta = json.loads(bd.DEFAULT_META.read_text("utf-8"))
    with open(path, "wb") as fh:
        pickle.dump({"kind": bd.CELLS_KIND, "meta": meta, "cells": _cells(n),
                     "rebuild_specs": rebuild or []}, fh)
    return path


def _arm_doc(threads: int, *, sr0: float = 0.0362, eig_hex: str = "0x1.0p+3",
             rho: float = 0.25, ckey: str = "k1") -> dict:
    verdict = {"cell": "EURUSD.f.p=1", "sym": "EURUSD", "passed": False,
               "stages": {"deflated_sharpe": {"sr0": sr0, "n_trials": 597, "passed": False}}}
    return {"threads": {"threadpoolctl": [{"user_api": "blas", "num_threads": threads}],
                        "os_threads": threads},
            "n_judged": 2, "census_calls": 1,
            "result": {"verdicts": [verdict, {**verdict, "cell": "XAUUSD.f.p=2"}],
                       "n_trials": 597, "trial_census": {"n_effective": 1.5, "n_raw": 2},
                       "constitution": {"dsr_threshold": 0.95}},
            "derived": {"rho": rho, "dsr_bar": 0.95},
            "census_returned": {"n_effective": 1.5},
            "probe": {"reported": {"taken_path_n_effective": 1.5},
                      "raw": {"eigvalsh_sha256": eig_hex}},
            "rebuilt": {"c1": {"ckey": ckey, "ds1_sha256": "aa"}}}


# ------------------------------------------------------------------------------ sampling
def test_sample_order_is_deterministic_deduplicated_and_order_free() -> None:
    specs = [{"sym": s, "family": "f", "params": {"k": k}} for s in "ABC" for k in range(5)]
    a = bd.sample_order(specs)
    b = bd.sample_order(list(reversed(specs)) + specs[:3])
    assert [bd.cell_key(x) for x in a] == [bd.cell_key(x) for x in b]
    assert len(a) == 15
    assert bd.sample_order([{"family": "f"}, {"sym": "A"}, "junk"]) == []  # type: ignore[list-item]


# ------------------------------------------------------------------------------ inputs
def test_load_input_reads_every_recorded_format(tmp_path) -> None:
    specs = [{"sym": "EURUSD", "family": "f", "params": {"a": 1}}]
    meta = {"symbols": {}}
    (tmp_path / "list.json").write_text(json.dumps(specs), "utf-8")
    (tmp_path / "meta.json").write_text(json.dumps(meta), "utf-8")
    got = bd.load_input(tmp_path / "list.json", tmp_path / "meta.json")
    assert got["kind"] == "specs" and got["specs"] == specs and got["meta"] == meta

    report = {"swept_at": "2026-10-22T00:00:00+00:00", "verdicts": [
        {"cell": "x", "sym": "EURUSD", "family": "f", "params": {"a": 1}, "passed": False}]}
    (tmp_path / "rep.json").write_text(json.dumps(report), "utf-8")
    got = bd.load_input(tmp_path / "rep.json", tmp_path / "meta.json")
    assert got["specs"] == specs and got["provenance"]["swept_at"] == report["swept_at"]

    with open(tmp_path / "plan.pkl", "wb") as fh:
        pickle.dump({"protocol": 2, "n": 4, "token": "t", "specs": specs, "meta": meta}, fh)
    got = bd.load_input(tmp_path / "plan.pkl")
    assert got["specs"] == specs and got["meta"] == meta
    assert got["provenance"]["plan_shards"] == 4 and got["provenance"]["sha256"]

    with open(tmp_path / "junk.pkl", "wb") as fh:
        pickle.dump([1, 2], fh)
    with pytest.raises(ValueError):
        bd.load_input(tmp_path / "junk.pkl")


# ------------------------------------------------------------------------------ comparison
def test_identical_arms_with_a_thread_contrast_are_identical() -> None:
    d = bd.decide_verdict({"default": _arm_doc(4), "single": _arm_doc(1)}, {})
    assert d["verdict"] == bd.IDENTICAL, d["why"]
    assert d["differences"] == []


def test_a_moved_sr0_is_listed_and_differs() -> None:
    d = bd.decide_verdict({"default": _arm_doc(4), "single": _arm_doc(1, sr0=0.0363)}, {})
    assert d["verdict"] == bd.DIFFERS
    paths = {(r["section"], r["path"]) for r in d["differences"]}
    assert ("verdict", "/EURUSD.f.p=1/stages/deflated_sharpe/sr0") in paths
    assert ("verdict", "/XAUUSD.f.p=2/stages/deflated_sharpe/sr0") in paths
    row = next(r for r in d["differences"] if r["section"] == "verdict")
    assert row["default"] == 0.0362 and row["single"] == 0.0363
    assert row["also_in_control"] is None


def test_a_moved_rho_differs_and_control_attributes_noise() -> None:
    arms = {"default": _arm_doc(4), "single": _arm_doc(1, rho=0.2500001),
            "control": _arm_doc(4, rho=0.2500002)}
    d = bd.decide_verdict(arms, {})
    assert d["verdict"] == bd.DIFFERS
    row = next(r for r in d["differences"] if r["path"] == "/rho")
    assert row["also_in_control"] is True
    assert d["control_differences"] == 1


def test_bit_level_intermediates_localise_but_do_not_decide() -> None:
    d = bd.decide_verdict({"default": _arm_doc(4), "single": _arm_doc(1, eig_hex="0x1.1p+3")},
                          {})
    assert d["verdict"] == bd.IDENTICAL
    assert d["localisation"]["single_vs_default"][0]["path"] == "/eigvalsh_sha256"


def test_a_reported_census_difference_differs() -> None:
    single = _arm_doc(1)
    single["probe"]["reported"]["eigvalsh_path_n_effective"] = 1.51
    d = bd.decide_verdict({"default": _arm_doc(4), "single": single}, {})
    assert d["verdict"] == bd.DIFFERS
    assert {r["section"] for r in d["differences"]} == {"probe_reported"}


def test_a_rebuilt_cell_whose_input_moved_is_set_aside() -> None:
    single = _arm_doc(1, ckey="k2")
    single["rebuilt"]["c1"]["ds1_sha256"] = "bb"
    d = bd.decide_verdict({"default": _arm_doc(4), "single": single}, {})
    assert d["verdict"] == bd.IDENTICAL
    assert d["rebuild_inputs_moved"] == ["c1"]
    same_key = _arm_doc(1)
    same_key["rebuilt"]["c1"]["ds1_sha256"] = "bb"
    assert bd.decide_verdict({"default": _arm_doc(4), "single": same_key},
                             {})["verdict"] == bd.DIFFERS


def test_no_thread_contrast_or_a_failed_arm_is_unmeasured() -> None:
    assert bd.decide_verdict({"default": _arm_doc(1), "single": _arm_doc(1)},
                             {})["verdict"] == bd.UNMEASURED
    blind = _arm_doc(4)
    blind["threads"] = {}
    assert bd.decide_verdict({"default": blind, "single": _arm_doc(1)},
                             {})["verdict"] == bd.UNMEASURED
    d = bd.decide_verdict({"default": _arm_doc(4), "single": None}, {"single": "exit 1"})
    assert d["verdict"] == bd.UNMEASURED and "single: exit 1" in d["why"]
    few = _arm_doc(1)
    few["n_judged"] = 1
    assert bd.decide_verdict({"default": _arm_doc(4), "single": few},
                             {})["verdict"] == bd.UNMEASURED


def test_diff_paths_reports_absent_keys_and_list_items() -> None:
    a = {"x": [1, 2, {"y": 1.0}], "z": 1}
    b = {"x": [1, 2, {"y": 1.0000000000000002}]}
    rows = bd.diff_paths(a, copy.deepcopy(b))
    assert {r["path"] for r in rows} == {"/x[2]/y", "/z"}


# ------------------------------------------------------------------------------ safety
def test_the_write_guard_refuses_writes_under_the_protected_root(tmp_path) -> None:
    prot, scratch = tmp_path / "repo", tmp_path / "repo" / "scratch"
    scratch.mkdir(parents=True)
    (prot / "ledger.jsonl").write_text("{}\n", "utf-8")
    code = f"""
import sys, json, os
sys.path[:0] = [{str(ROOT)!r}, {str(DESK)!r}]
from scripts import blas_thread_differential as bd
from pathlib import Path
bd.install_write_guard([Path({str(prot)!r})], [Path({str(scratch)!r})])
res = {{}}
for name, fn in [
    ("append", lambda: open({str(prot / 'ledger.jsonl')!r}, "a").write("x")),
    ("create", lambda: Path({str(prot / 'new.json')!r}).write_text("x")),
    ("replace", lambda: os.replace({str(scratch / 'a')!r}, {str(prot / 'ledger.jsonl')!r})),
    ("remove", lambda: os.remove({str(prot / 'ledger.jsonl')!r})),
    ("mkdir", lambda: os.mkdir({str(prot / 'd')!r})),
]:
    try:
        fn(); res[name] = "allowed"
    except PermissionError:
        res[name] = "refused"
    except OSError as e:
        res[name] = "oserror"
Path({str(scratch / 'a')!r}).write_text("ok")
res["read"] = open({str(prot / 'ledger.jsonl')!r}).read()
res["blocked"] = len(bd._GUARD["blocked"])
print(json.dumps(res))
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True)
    res = json.loads(out.stdout.strip().splitlines()[-1])
    for k in ("append", "create", "replace", "remove", "mkdir"):
        assert res[k] == "refused", (k, res)
    assert res["read"] == "{}\n" and res["blocked"] == 5
    assert (scratch / "a").read_text("utf-8") == "ok"
    assert not (prot / "new.json").exists()


def test_the_report_refuses_to_replace_a_read_only_file(tmp_path) -> None:
    out = tmp_path / "BLAS_DIFFERENTIAL.json"
    out.write_text("{}", "utf-8")
    os.chmod(out, stat.S_IREAD)
    try:
        with pytest.raises(PermissionError):
            bd.write_report({"schema": bd.SCHEMA, "verdict": bd.UNMEASURED}, out)
        assert out.read_text("utf-8") == "{}"
    finally:
        os.chmod(out, stat.S_IREAD | stat.S_IWRITE)


def test_scratch_inside_the_desk_state_is_refused(tmp_path) -> None:
    with pytest.raises(ValueError):
        bd.run(input_path=None, out=tmp_path / "r.json", scratch=DESK / "reports" / "x")


def test_no_recorded_input_is_unmeasured(tmp_path) -> None:
    rep = bd.run(input_path=tmp_path / "absent.pkl", out=tmp_path / "r.json")
    assert rep["verdict"] == bd.UNMEASURED and "no recorded sweep input" in rep["why"]
    assert rep["content_sha256"] == bt.content_sha256(rep)


def _state_listing() -> set[str]:
    out: set[str] = set()
    for d in (DESK / "data", DESK / "reports"):
        if d.exists():
            out |= {str(p) for p in d.iterdir()}
    return out


def test_a_plan_with_no_cached_series_builds_nothing_and_is_unmeasured(tmp_path) -> None:
    meta = json.loads(bd.DEFAULT_META.read_text("utf-8"))
    plan = tmp_path / "plan.pkl"
    with open(plan, "wb") as fh:
        pickle.dump({"protocol": 2, "n": 2, "token": "t", "meta": meta, "specs": [
            {"sym": "EURUSD", "family": "nonexistent_family_for_test", "params": {"k": 1}},
            {"sym": "NOSUCHSYMBOL", "family": "session_range_breakout", "params": {}}]}, fh)
    before = _state_listing()
    rep = bd.run(input_path=plan, out=tmp_path / "r.json", sample=5, rebuild=0)
    assert rep["verdict"] == bd.UNMEASURED
    assert rep["input"]["sampled_cells"] == 0 and rep["input"]["scanned_specs"] == 2
    assert _state_listing() == before


# ------------------------------------------------------------------------------ end to end
def test_end_to_end_on_the_real_judge(tmp_path) -> None:
    rebuild = []
    if (DESK / "data" / "universe" / "EURUSD_H1.parquet").exists():
        rebuild = [{"sym": "EURUSD", "family": "session_range_breakout", "params": {}}]
    fix = _fixture(tmp_path / "cells.pkl", 40, rebuild)
    out = tmp_path / "BLAS_DIFFERENTIAL.json"
    scratch = tmp_path / "scratch"
    before = _state_listing()
    rep = bd.run(input_path=fix, out=out, sample=36, rebuild=len(rebuild), control=True,
                 scratch=scratch)
    assert _state_listing() == before, "the harness wrote into the desk's state"
    assert rep["schema"] == bd.SCHEMA and rep["content_sha256"] == bt.content_sha256(rep)
    if (os.cpu_count() or 1) > 1:
        assert rep["verdict"] == bd.IDENTICAL, (rep["why"], rep.get("differences"))
        ok, why = bt.proof_status(out)
        assert ok is (bt.release_id() != "unreleased"), why
    else:
        assert rep["verdict"] == bd.UNMEASURED
    assert rep["input"]["sampled_cells"] == 36
    for arm in ("default", "single", "control"):
        t = rep["timing"][arm]
        assert t["per_cell_wall_ms"] > 0 and t["per_cell_cpu_ms"] >= 0
        assert rep["arms"][arm]["n_judged"] == 36 and rep["arms"][arm]["census_calls"] == 1
    assert rep["arms"]["single"]["threads"]["env"]["OPENBLAS_NUM_THREADS"] == "1"
    assert rep["arms"]["default"]["threads"]["env"]["OPENBLAS_NUM_THREADS"] is None
    kq = rep["key_quantities"]["single"]
    assert kq["trial_census"]["method"] == "null_calibrated_participation_ratio"
    assert 0 < kq["rho"] <= 1 and kq["dsr_bar"] is not None and kq["n_trials"] >= 2
    assert kq["family_effective_trials"]["effective"] >= 1
    probe = rep["probe"]["single"]
    assert probe["reported"]["census_path"] == "finite_gram"
    assert probe["reported"]["matrix_sha256"] == rep["probe"]["default"]["reported"][
        "matrix_sha256"]
    assert rep["write_guard_blocked"] == {}
    if rebuild:
        assert rep["timing"]["single"]["rebuild_cells"] == 1
