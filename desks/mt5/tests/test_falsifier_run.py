"""The falsifier battery finally has a caller, and the caller withdraws nothing.

    python -m pytest desks/mt5/tests/test_falsifier_run.py -q

`libs/validation/falsifiers.py` had zero importers; this producer runs its catalogue over every
certificate and writes a defect report beside them. What must hold:

  1. the tests run in the catalogue's kill-rate-per-second order, and the FIRST killer in that
     order is the one named -- not the last, which is what `falsifiers.run` itself reports
     when asked not to stop;
  2. an input the desk cannot supply is UNMEASURED with the reason, never skipped silently and
     never a pass;
  3. the wall-clock budget is honoured before every certificate and every test, and whatever it
     does not reach is recorded as NOT_REACHED carrying its previous verdict;
  4. the certificate file is byte-identical after the run -- a defect report withdraws nothing;
  5. the truncation test is fed the gauntlet's builder, so a lookahead in the builder is caught.
"""
from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import falsifier_run as fr  # noqa: E402
from mt5desk.engine import Signal  # noqa: E402

from libs.validation import falsifiers  # noqa: E402

N_BARS = 900
TTL = 6


def _bars_and_signals(drift_per_bar: float, seed: int = 0) -> tuple[pd.DataFrame, list[Signal]]:
    """A random walk with an edge PLANTED after every signal bar at a known strength."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=N_BARS, freq="h", tz="UTC")
    r = rng.normal(0.0, 0.001, N_BARS)
    at = list(range(30, N_BARS - 40, 12))
    for i in at:
        r[i + 1:i + 1 + TTL] += drift_per_bar
    c = 100.0 * np.exp(np.cumsum(r))
    o = np.r_[100.0, c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0005,
                       "low": np.minimum(o, c) * 0.9995, "close": c}, index=idx)
    sigs = [Signal(time=idx[i], side=1, stop=float(c[i]) * 0.99, target=float(c[i]) * 1.02,
                   ttl_bars=TTL, tag="planted") for i in at]
    return df, sigs


def _cert(sym: str, family: str = "planted", **params) -> dict:
    return {"sym": sym, "status": "UNIVERSAL",
            "shadow_spec": {"symbol": sym, "family": family, "params": params}}


def _write_certs(path: Path, ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"n": len(ids), "note": "fixture",
                                "survivors": {cid: _cert(cid.split(".")[0]) for cid in ids}}),
                    "utf-8")


def _builder_for(cells: dict[str, tuple[pd.DataFrame, list[Signal]]], *,
                 lookahead: bool = False):
    """A stand-in for `external_gauntlet.build_cell` over synthetic cells.

    With `lookahead=True` the builder's signals depend on the LAST bar of whatever frame it is
    given, which is exactly the defect the truncation test exists to catch.
    """
    def build(sym, family, params, meta, h1_override=None):
        if sym not in cells:
            return None
        df, sigs = cells[sym]
        frame = df if h1_override is None else h1_override
        out = [s for s in sigs if s.time in frame.index]
        if lookahead and len(frame) < len(df):
            out = out[:-1]                         # the truncated frame "loses" a signal
        return {"sym": sym, "family": family, "params": params, "timeframe": "H1",
                "df": frame, "sigs": out, "costs": 0.0005}
    return build


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    certs = tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json"
    report = tmp_path / "reports" / "FALSIFIER_VERDICTS.json"
    monkeypatch.setattr(fr, "_meta", lambda path=None: {})
    monkeypatch.setattr(fr, "_premortems", lambda certs: ({}, "catalogue order only: test"))

    @contextlib.contextmanager
    def _lock(name, need_mb=0):
        yield True
    monkeypatch.setitem(sys.modules, "job_lock", type(sys)("job_lock"))
    sys.modules["job_lock"].exclusive_job = _lock
    return {"certs": certs, "report": report, "tmp": tmp_path}


def _run(desk: dict, monkeypatch, builder, ids: list[str], **kw) -> dict:
    _write_certs(desk["certs"], ids)
    monkeypatch.setattr(fr, "_builder", lambda: builder)
    return fr.run(certs_path=desk["certs"], fallback=desk["tmp"] / "absent.json",
                  report_path=desk["report"], premortem=False, **kw)


# ------------------------------------------------- 1. order, and the FIRST killer

def test_tests_run_in_the_catalogue_s_kill_rate_per_second_order(desk, monkeypatch) -> None:
    good = _bars_and_signals(0.003)
    doc = _run(desk, monkeypatch, _builder_for({"GOOD": good}), ["GOOD.planted"])
    e = doc["per_certificate"]["GOOD.planted"]
    assert e["order"] == falsifiers.schedule()
    assert e["tests_run"] == e["order"], "every test was reached and run in schedule order"
    assert e["status"] == "SURVIVED" and e["first_killer"] is None
    assert all("seconds" in r for r in e["results"].values())


def test_the_first_killer_in_schedule_order_is_named_and_every_kill_is_counted(
        desk, monkeypatch) -> None:
    """`falsifiers.run(stop_on_fail=False)` names the LAST failing test; a re-test should start
    with the cheapest objection that settled the question, so the first is named here."""
    noise = _bars_and_signals(0.0)
    doc = _run(desk, monkeypatch, _builder_for({"NOISE": noise}), ["NOISE.planted"])
    e = doc["per_certificate"]["NOISE.planted"]
    assert e["status"] == "KILLED"
    assert e["first_killer"] == e["order"][0] == "cost_surface"
    assert len(e["kills"]) >= 2 and e["kills"] == [n for n in e["order"] if n in e["kills"]]
    assert doc["summary"]["first_killers"] == {"cost_surface": 1}


# ------------------------------------------------- 2. UNMEASURED with the reason

def test_an_input_the_desk_cannot_supply_is_unmeasured_with_why_never_a_pass(
        desk, monkeypatch) -> None:
    good = _bars_and_signals(0.003)
    doc = _run(desk, monkeypatch, _builder_for({"GOOD": good}), ["GOOD.planted"])
    e = doc["per_certificate"]["GOOD.planted"]
    assert e["results"]["usd_residual"]["verdict"] == "UNMEASURED"
    assert "USD driver" in e["results"]["usd_residual"]["why"]
    assert "usd_residual" in e["unmeasured"]
    assert doc["input_gaps"]["usd_residual"] == fr.USD_GAP


def test_a_certificate_the_builder_cannot_build_is_unmeasured_with_why(desk, monkeypatch) -> None:
    doc = _run(desk, monkeypatch, _builder_for({}), ["GONE.planted"])
    e = doc["per_certificate"]["GONE.planted"]
    assert e["status"] == "UNMEASURED"
    assert "no executable cell" in e["why"]
    assert doc["summary"]["by_status"] == {"UNMEASURED": 1}


def test_an_unpriced_cost_makes_every_cost_dependent_test_unmeasured(desk, monkeypatch) -> None:
    """Running the cost tests at zero would grade the GROSS edge and call it a pass."""
    good = _bars_and_signals(0.003)
    build = _builder_for({"GOOD": good})

    def unpriced(*a, **k):
        out = build(*a, **k)
        if out:
            out["costs"] = None
        return out
    doc = _run(desk, monkeypatch, unpriced, ["GOOD.planted"])
    e = doc["per_certificate"]["GOOD.planted"]
    assert e["cost_fraction"] is None and "unpriced" in e["cost_basis"]
    for name in fr.COST_DEPENDENT:
        assert e["results"][name]["verdict"] == "UNMEASURED", name
    assert e["results"]["truncation"]["verdict"] == "PASS", "truncation needs no cost"


def test_cost_fraction_prices_a_costs_object_in_log_return_units() -> None:
    from mt5desk.engine import Costs
    df, _ = _bars_and_signals(0.0)
    frac, basis = fr.cost_fraction(df, Costs(spread_per_lot=16.0, commission_per_lot=2.25,
                                             contract_oz=100.0))
    px = float(np.nanmedian(df["close"]))
    assert frac == pytest.approx((16.0 + 4.5) / 100.0 / px)
    assert "median close" in basis
    assert fr.cost_fraction(df, None) == (None, "unpriced: the cell carries no cost model")


# ------------------------------------------------- 3. the budget, and what it did not reach

def test_a_spent_budget_records_not_reached_with_the_previous_verdict(desk, monkeypatch) -> None:
    good = _bars_and_signals(0.003)
    build = _builder_for({"A": good, "B": good})
    first = _run(desk, monkeypatch, build, ["A.planted", "B.planted"])
    assert {e["status"] for e in first["per_certificate"].values()} == {"SURVIVED"}
    second = _run(desk, monkeypatch, build, ["A.planted", "B.planted"], budget_sec=0.0)
    assert second["status"] == "NOT_REACHED" and second["n_not_reached"] == 2
    for e in second["per_certificate"].values():
        assert e["status"] == "NOT_REACHED" and "budget" in e["why"]
        assert e["previous"]["status"] == "SURVIVED"
        assert e["measured_at"] == e["previous"]["measured_at"], "rotation keeps the old stamp"


def test_the_budget_is_checked_before_every_test_inside_a_certificate(monkeypatch) -> None:
    """A deadline that lands mid-battery leaves the rest NOT_REACHED, never silently absent."""
    df, sigs = _bars_and_signals(0.003)
    import time as _time
    clock = iter([0.0] * 3 + [10.0] * 20)
    monkeypatch.setattr(_time, "monotonic", lambda: next(clock))
    out = fr.falsify({"df": df, "signals": sigs, "cost": 0.0005, "cost_basis": "given",
                      "family": None, "params": {}, "usd": None}, deadline=5.0)
    assert out["tests_run"] and out["not_reached"]
    assert out["tests_run"] + out["not_reached"] == out["order"]
    assert out["complete"] is False


def test_the_rotation_puts_never_measured_certificates_first_then_the_oldest() -> None:
    prior = {"old": {"measured_at": "2026-09-01T00:00:00+00:00"},
             "new": {"measured_at": "2026-09-08T00:00:00+00:00"}}
    assert fr.rotation(["new", "old", "never"], prior) == ["never", "old", "new"]


# ------------------------------------------------- 4. nothing withdrawn

def test_the_certificate_file_is_byte_identical_after_a_kill(desk, monkeypatch) -> None:
    noise = _bars_and_signals(0.0)
    _write_certs(desk["certs"], ["NOISE.planted"])
    before = desk["certs"].read_bytes()
    doc = _run(desk, monkeypatch, _builder_for({"NOISE": noise}), ["NOISE.planted"])
    assert doc["per_certificate"]["NOISE.planted"]["status"] == "KILLED"
    assert desk["certs"].read_bytes() == before
    assert "withdraws nothing" in doc["law"]
    written = json.loads(desk["report"].read_text("utf-8"))
    assert written["per_certificate"]["NOISE.planted"]["first_killer"] == "cost_surface"


# ------------------------------------------------- 5. the builder feeds the truncation test

def test_a_lookahead_in_the_builder_is_caught_by_the_truncation_test(desk, monkeypatch) -> None:
    good = _bars_and_signals(0.003)
    causal = _run(desk, monkeypatch, _builder_for({"GOOD": good}), ["GOOD.planted"])
    assert causal["per_certificate"]["GOOD.planted"]["results"]["truncation"]["verdict"] == "PASS"
    leaky = _run(desk, monkeypatch, _builder_for({"GOOD": good}, lookahead=True),
                 ["GOOD.planted"])
    e = leaky["per_certificate"]["GOOD.planted"]
    assert e["results"]["truncation"]["verdict"] == "FAIL"
    assert "truncation" in e["kills"]


def test_the_library_battery_registers_a_truncation_kill_and_names_the_first(
        monkeypatch) -> None:
    """Two defects in `libs.validation.falsifiers`, found by its first caller: the lookahead
    sentinel's own CAUSAL/LOOKAHEAD word overwrote the battery's PASS/FAIL (so a truncation kill
    never registered), and a full run named the LAST failing test as `killed_by`."""
    df, sigs = _bars_and_signals(0.003)
    leaky = _builder_for({"X": (df, sigs)}, lookahead=True)

    def family_fn(frame, **_kw):
        return leaky("X", "planted", {}, {}, h1_override=frame)["sigs"]
    out = falsifiers.run(df, sigs, 0.0005, stop_on_fail=False, family=family_fn)
    assert out["results"]["truncation"]["verdict"] == "FAIL"
    assert out["results"]["truncation"]["lookahead_verdict"] == "LOOKAHEAD"
    assert out["killed_by"] == "truncation" and out["verdict"] == "KILLED"
    monkeypatch.setitem(falsifiers.FALSIFIERS, "cost_surface",
                        lambda *a, **k: {"verdict": "FAIL", "n": 99})
    out = falsifiers.run(df, sigs, 0.0005, stop_on_fail=False, family=family_fn)
    assert out["killed_by"] == "cost_surface", "the FIRST kill in schedule order, not the last"


# ------------------------------------------------- the docket, and the entry point

def test_an_empty_docket_is_named_not_run_over(desk, monkeypatch) -> None:
    monkeypatch.setattr(fr, "_builder", lambda: (lambda *a, **k: None))
    doc = fr.run(certs_path=desk["tmp"] / "nope.json", fallback=desk["tmp"] / "nope2.json",
                 report_path=desk["report"], premortem=False)
    assert doc["status"] == "NO_CERTIFICATES" and "non-empty" in doc["why"]
    assert desk["report"].exists()


def test_the_data_canon_is_read_when_the_reports_file_is_absent(tmp_path: Path) -> None:
    canon = tmp_path / "canon.json"
    _write_certs(canon, ["X.planted"])
    certs, source = fr.load_certificates(tmp_path / "absent.json", canon)
    assert set(certs) == {"X.planted"} and source == str(canon)


def test_main_returns_zero_and_writes_the_report(desk, monkeypatch, capsys) -> None:
    good = _bars_and_signals(0.003)
    _write_certs(desk["certs"], ["GOOD.planted"])
    monkeypatch.setattr(fr, "_builder", lambda: _builder_for({"GOOD": good}))
    rc = fr.main(["--certs", str(desk["certs"]), "--report", str(desk["report"]),
                  "--budget-sec", "30", "--no-premortem"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "falsifier_run: MEASURED 1/1" in out
    assert json.loads(desk["report"].read_text("utf-8"))["n_reached"] == 1
