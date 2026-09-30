"""DSR inputs are MEASURED from judged trials, carry provenance, and fail closed; no constant."""
from __future__ import annotations

import json
import random
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from libs.research import dsr_inputs as di

ROOT = Path(__file__).resolve().parents[2]


def _verdict(cell: str, fam: str, sym: str, sr: float, days: int = 300) -> dict[str, Any]:
    return {"cell": cell, "family": fam, "sym": sym, "days": days, "passed": False,
            "stages": {"in_sample_screen": {"passed": sr > 0, "sharpe": sr}}}


def _report(verdicts: list[dict[str, Any]], *, at: str | None = None, hunt: str = "h",
            census: dict[str, Any] | None = None) -> dict[str, Any]:
    doc: dict[str, Any] = {"hunt": hunt, "swept_at": at or di._iso(di._now()),
                           "verdicts": verdicts}
    if census is not None:
        doc["trial_census"] = census
    return doc


def _write(path: Path, doc: dict[str, Any]) -> Path:
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _sweep(n: int, fam: str = "carry", sd: float = 0.05, seed: int = 1,
           prefix: str = "c") -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [_verdict(f"{prefix}{i}", fam, f"S{i % 5}", rng.gauss(0.0, sd)) for i in range(n)]


# ------------------------------------------------------------------------------ harvest
def test_harvest_keeps_only_judged_cells_and_is_idempotent(tmp_path: Path) -> None:
    vs = _sweep(3)
    vs.append(_verdict("short", "carry", "X", 0.2, days=40))            # never judged
    vs.append({"cell": "unm", "family": "carry", "unmeasured": True, "days": 10,
               "stages": {"observations": {"passed": False}}})
    vs.append({"cell": "nosr", "family": "carry", "days": 200, "stages": {}})
    rp = _write(tmp_path / "r.json", _report(vs))
    led = tmp_path / "l.jsonl"
    h = di.harvest(rp, led)
    assert h["appended"] == 3
    assert di.harvest(rp, led)["appended"] == 0                           # same sweep
    assert len(di.read_ledger(led)) == 3


def test_a_rejudged_cell_with_the_same_sharpe_is_not_written_twice(tmp_path: Path) -> None:
    led = tmp_path / "l.jsonl"
    di.harvest(_write(tmp_path / "a.json", _report(_sweep(4), hunt="a")), led)
    vs = [*_sweep(4), _verdict("new", "carry", "S9", 0.3)]
    assert di.harvest(_write(tmp_path / "b.json", _report(vs, hunt="b")), led)["appended"] == 1


def test_absent_sweep_report_harvests_nothing_and_says_so(tmp_path: Path) -> None:
    h = di.harvest(tmp_path / "none.json", tmp_path / "l.jsonl")
    assert h["status"] == di.UNMEASURED and h["appended"] == 0


# ------------------------------------------------------------------------------ measurement
def test_variance_is_the_plain_ddof1_variance_of_the_judged_sharpes(tmp_path: Path) -> None:
    vs = _sweep(150, sd=0.07)
    rp = _write(tmp_path / "r.json", _report(vs))
    doc = di.run(report_path=rp, ledger_path=tmp_path / "l.jsonl", out=tmp_path / "o.json")
    want = float(np.var([v["stages"]["in_sample_screen"]["sharpe"] for v in vs], ddof=1))
    assert doc["status"] == di.MEASURED
    assert doc["variance"]["pooled"]["n"] == 150
    assert doc["variance"]["pooled"]["variance"] == pytest.approx(want, rel=1e-6)
    assert doc["variance"]["by_family"]["carry"]["status"] == di.MEASURED
    assert "not annualised" in doc["variance"]["units"]


def test_the_window_is_current_and_the_latest_sharpe_per_cell_counts(tmp_path: Path) -> None:
    led = tmp_path / "l.jsonl"
    old = di._iso(di._now() - timedelta(days=90))
    di.harvest(_write(tmp_path / "old.json", _report(_sweep(120, sd=1.0, prefix="o"), at=old)),
               led)
    di.harvest(_write(tmp_path / "new.json", _report(_sweep(110, sd=0.01, seed=3))), led)
    doc = di.measure(ledger_path=led, report_path=tmp_path / "new.json")
    assert doc["variance"]["pooled"]["n"] == 110                      # the old sweep is outside
    assert doc["variance"]["pooled"]["variance"] < 0.001
    assert doc["variance"]["lifetime_pooled"]["n"] == 230
    assert doc["effective_trials"]["nominal"] == 230                 # lifetime counts everything


def test_too_few_cells_is_unmeasured_never_a_default(tmp_path: Path) -> None:
    rp = _write(tmp_path / "r.json", _report(_sweep(20)))
    doc = di.run(report_path=rp, ledger_path=tmp_path / "l.jsonl", out=tmp_path / "o.json")
    assert doc["status"] == di.UNMEASURED
    assert doc["unmeasured_reason"] == "dsr_inputs_unmeasured"
    got, why = di.load_verified(tmp_path / "o.json")
    assert got is None and "dsr_inputs_unmeasured" in why


def test_a_thin_family_gets_the_pooled_variance_and_says_so(tmp_path: Path) -> None:
    vs = _sweep(120, fam="carry") + _sweep(5, fam="rare", prefix="r", seed=9)
    rp = _write(tmp_path / "r.json", _report(vs))
    di.run(report_path=rp, ledger_path=tmp_path / "l.jsonl", out=tmp_path / "o.json")
    doc, why = di.load_verified(tmp_path / "o.json")
    assert doc is not None, why
    fam = di.cell_inputs(doc, "carry")
    rare = di.cell_inputs(doc, "rare")
    assert fam is not None and rare is not None
    assert "family carry" in fam["variance_basis"]
    assert "pooled" in rare["variance_basis"]
    assert rare["variance"] == doc["variance"]["pooled"]["variance"]
    assert di.cell_inputs(doc, "never_seen")["effective_trials"] is None  # type: ignore[index]


# ------------------------------------------------------------------------------ effective trials
def test_effective_trials_follow_the_judges_correlation_census(tmp_path: Path) -> None:
    led = tmp_path / "l.jsonl"
    census = {"method": "null_calibrated_participation_ratio", "n_raw": 100, "n_effective": 25}
    vs = [_verdict(f"c{i}", "carry", "EURUSD" if i % 2 else "GBPUSD", 0.01 * i)
          for i in range(100)]
    di.harvest(_write(tmp_path / "r.json", _report(vs, census=census)), led)
    eff = di.effective_trials(di.read_ledger(led))
    row = eff["by_family"]["carry"]
    assert row["nominal"] == 100 and row["effective"] == 25


def test_an_unmeasurable_census_charges_every_cell_in_full(tmp_path: Path) -> None:
    led = tmp_path / "l.jsonl"
    census = {"method": "unmeasurable", "n_raw": 40, "n_effective": 40}
    di.harvest(_write(tmp_path / "r.json", _report(_sweep(40), census=census)), led)
    assert di.effective_trials(di.read_ledger(led))["by_family"]["carry"]["effective"] == 40


def test_effective_trials_are_floored_at_distinct_symbols(tmp_path: Path) -> None:
    led = tmp_path / "l.jsonl"
    census = {"method": "participation_ratio", "n_raw": 50, "n_effective": 1}
    vs = [_verdict(f"c{i}", "carry", f"S{i % 10}", 0.01) for i in range(50)]
    di.harvest(_write(tmp_path / "r.json", _report(vs, census=census)), led)
    row = di.effective_trials(di.read_ledger(led))["by_family"]["carry"]
    assert row["effective"] == 10 <= row["nominal"]


# ------------------------------------------------------------------------------ the judge's door
@pytest.fixture
def measured(tmp_path: Path) -> Path:
    rp = _write(tmp_path / "r.json", _report(_sweep(150)))
    out = tmp_path / "DSR_INPUTS.json"
    di.run(report_path=rp, ledger_path=tmp_path / "l.jsonl", out=out)
    return out


def test_a_fresh_verified_document_is_used(measured: Path) -> None:
    doc, why = di.load_verified(measured)
    assert doc is not None and why == ""
    prov = doc["provenance"]
    assert {s["role"] for s in prov["sources"]} >= {
        "append-only ledger of judged trial Sharpes"}
    assert all(s["sha256"] for s in prov["sources"])
    assert prov["n"] == 150 and prov["window"]["days"] == di.WINDOW_DAYS
    assert prov["method"]["variance"] and prov["method"]["effective_trials"]
    assert prov["timestamp"] == doc["measured_at"]
    assert doc["content_sha256"] == di.canonical_sha256(doc)


def test_absent_is_unmeasured(tmp_path: Path) -> None:
    doc, why = di.load_verified(tmp_path / "absent.json")
    assert doc is None and why.startswith("dsr_inputs_unmeasured")


def test_a_hand_edited_variance_fails_the_provenance_hash(measured: Path) -> None:
    doc = json.loads(measured.read_text("utf-8"))
    doc["variance"]["pooled"]["variance"] = 0.0002
    measured.write_text(json.dumps(doc), encoding="utf-8")
    got, why = di.load_verified(measured)
    assert got is None and "provenance hash" in why and "dsr_inputs_unmeasured" in why


def test_stale_and_future_documents_are_refused(measured: Path) -> None:
    now = di._now()
    got, why = di.load_verified(measured, now=now + timedelta(seconds=di.MAX_AGE_S + 60))
    assert got is None and "stale" in why
    got, why = di.load_verified(measured, now=now - timedelta(hours=1))
    assert got is None and "future" in why


def test_no_constant_survives_in_the_organ() -> None:
    import ast
    tree = ast.parse((ROOT / "libs" / "research" / "dsr_inputs.py").read_text("utf-8"))
    floats = {n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert not floats & {0.014863, 0.0002, 0.00082}
    et = (ROOT / "desks" / "mt5" / "research" / "effective_trials.py").read_text("utf-8")
    assert "0.014863 if" not in et


# ------------------------------------------------------------------------------ the clock
def test_the_script_publishes_and_the_hourly_leg_runs_it(tmp_path: Path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_dsr_inputs", ROOT / "desks" / "mt5" / "scripts" / "measure_dsr_inputs.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rp = _write(tmp_path / "r.json", _report(_sweep(120)))
    out = tmp_path / "o.json"
    assert mod.main(["--once", "--report", str(rp), "--ledger", str(tmp_path / "l.jsonl"),
                     "--out", str(out)]) == 0
    assert json.loads(out.read_text("utf-8"))["status"] == di.MEASURED
    cycle = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("dsr_inputs", "scripts/measure_dsr_inputs.py"' in cycle
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["dsr_inputs"] == "information"
