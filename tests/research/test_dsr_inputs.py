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


def test_the_script_declares_the_report_the_library_writes() -> None:
    """The attestation registry reads the script's own OUT; it must be the library's REPORT."""
    import importlib.util

    from libs.research import dsr_inputs
    path = dsr_inputs.DESK / "scripts" / "measure_dsr_inputs.py"
    spec = importlib.util.spec_from_file_location("measure_dsr_inputs", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.OUT.resolve() == dsr_inputs.REPORT.resolve()


# ------------------------------------------------------------------------ bounded, publish-first
# The pass publishes before it harvests, an unchanged report costs a stat, the report is streamed,
# and a harvest that runs out of time says DEFERRED instead of being killed with nothing written.
def _golden_reports() -> list[dict[str, Any]]:
    """A fixed fixture: four sweeps with re-judged cells, unjudged rows, junk and a census."""
    rng = random.Random(20261021)
    out = []
    for k in range(4):
        vs: list[Any] = []
        for i in range(240):
            c = rng.random()
            if c < 0.05:
                vs.append({"cell": f"u{i}", "unmeasured": True, "days": 3})
            elif c < 0.08:
                vs.append(_verdict(f"s{i}", "fx", "X", 0.1, days=40))
            elif c < 0.10:
                vs.append("junk")
            else:
                vs.append({**_verdict(f"c{rng.randrange(400)}",
                                      rng.choice(["carry", "fx", "gold", "rare"]),
                                      f"S{rng.randrange(9)}", rng.gauss(0.0, 0.1),
                                      days=rng.randrange(55, 400)),
                           "series": [rng.random() for _ in range(rng.randrange(8))]})
        rep: dict[str, Any] = {"extra": {"nested": [1, {"x": "}]\\\"{"}]}, "verdicts": vs,
                               "hunt": f"h{k}", "swept_at": f"2026-10-1{k}T00:00:00+00:00"}
        if k % 2:
            rep["trial_census"] = {"method": "null_calibrated_participation_ratio",
                                   "n_raw": 100, "n_effective": 40 + k}
        out.append(rep)
    return out


def _golden_digest(mod: Any, work: Path, *, indent: int | None) -> str:
    """Every pass's document (code hash, content hash and the tmp paths removed) plus the ledger's
    bytes, hashed. Two passes per sweep: the second sees the report unchanged."""
    import hashlib
    from datetime import UTC, datetime
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    docs = []
    for rep in _golden_reports():
        rp = work / "report.json"
        rp.write_text(json.dumps(rep, indent=indent), encoding="utf-8")
        for _ in range(2):
            d = json.loads(json.dumps(mod.run(report_path=rp, ledger_path=work / "l.jsonl",
                                              out=work / "o.json", now=now)))
            d.pop("content_sha256")
            d["provenance"].pop("code")
            for s in d["provenance"]["sources"]:
                s.pop("path")
            docs.append(d)
    blob = json.dumps(docs, sort_keys=True).encode() + (work / "l.jsonl").read_bytes()
    return hashlib.sha256(blob).hexdigest()


#: Computed by the PRE-2026-10-21 module (harvest-then-measure, json.loads of the whole report) on
#: `_golden_reports`; the bounded pass must reproduce it exactly, documents and ledger bytes.
GOLDEN_DIGEST = {None: "f3a4d9942b11a26019b2f04686825376387560728e2667a9f79d7a22ff4f8a34",
                 2: "a2c197e61893640347f6db59c6d3dd468a7bcc2055001ad86e7c676a67286c53"}


@pytest.mark.parametrize("indent", [None, 2])
@pytest.mark.parametrize("chunk", [1 << 20, 7])
def test_a_completed_pass_is_byte_identical_to_the_old_pass(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch,
                                                            indent: int | None,
                                                            chunk: int) -> None:
    monkeypatch.setattr(di, "_CHUNK", chunk)             # 7: every value straddles a chunk edge
    assert _golden_digest(di, tmp_path, indent=indent) == GOLDEN_DIGEST[indent]


def test_an_unchanged_report_is_neither_hashed_nor_parsed(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    rp = _write(tmp_path / "r.json", _report(_sweep(150)))
    led, out = tmp_path / "l.jsonl", tmp_path / "o.json"
    first = di.run(report_path=rp, ledger_path=led, out=out)
    assert first["provenance"]["harvest"]["appended"] == 150

    def boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("the unchanged report was read")

    hashed: list[Path] = []
    real_sha = di._file_sha256

    def spy(path: Path) -> str | None:
        hashed.append(Path(path))
        return real_sha(path)

    for name in ("_file_sha256_bounded", "_stream_report", "_scan_ledger"):
        monkeypatch.setattr(di, name, boom)
    monkeypatch.setattr(di, "_file_sha256", spy)
    doc = di.run(report_path=rp, ledger_path=led, out=out)
    assert rp not in hashed                                # provenance reuses the indexed hash
    fh = first["provenance"]["harvest"]
    assert doc["provenance"]["harvest"] == {
        "status": di.MEASURED, "appended": 0, "sweep_id": fh["sweep_id"],
        "sha256": fh["sha256"], "why": di.ALREADY_HARVESTED_WHY}
    assert doc["provenance"]["sources"][1]["sha256"] == fh["sha256"]
    got, why = di.load_verified(out)
    assert got is not None, why


def test_a_touched_or_unindexed_report_is_recognised_from_the_ledger(tmp_path: Path) -> None:
    import os
    rp = _write(tmp_path / "r.json", _report(_sweep(150)))
    led = tmp_path / "l.jsonl"
    di.run(report_path=rp, ledger_path=led, out=tmp_path / "o.json")
    os.utime(rp, ns=(1, 1))                               # same bytes, new stat: re-hash
    h = di.harvest(rp, led)
    assert h["appended"] == 0 and h["why"] == di.ALREADY_HARVESTED_WHY
    di._index_path(led).unlink()                          # the index is a cache, never the truth
    h = di.harvest(rp, led)
    assert h["appended"] == 0 and h["why"] == di.ALREADY_HARVESTED_WHY
    assert len(di.read_ledger(led)) == 150


def test_an_overrun_publishes_from_the_ledger_and_defers_the_harvest(tmp_path: Path) -> None:
    led, out = tmp_path / "l.jsonl", tmp_path / "o.json"
    di.run(report_path=_write(tmp_path / "a.json", _report(_sweep(150, prefix="a"))),
           ledger_path=led, out=out)
    before = led.read_bytes()
    rb = _write(tmp_path / "b.json", _report(_sweep(60, prefix="b", seed=4)))
    doc = di.run(report_path=rb, ledger_path=led, out=out, budget_s=0)
    h = doc["provenance"]["harvest"]
    assert h["status"] == di.DEFERRED and h["appended"] == 0 and "deadline" in h["why"]
    assert led.read_bytes() == before                     # nothing half-appended
    assert doc["status"] == di.MEASURED and doc["variance"]["pooled"]["n"] == 150
    got, why = di.load_verified(out)
    assert got is not None, why                            # the judge still has fresh inputs
    done = di.run(report_path=rb, ledger_path=led, out=out)  # the next pass resumes
    assert done["provenance"]["harvest"]["appended"] == 60
    assert done["variance"]["pooled"]["n"] == 210


def test_a_deadline_mid_parse_appends_nothing_and_names_the_step(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import time
    rp = _write(tmp_path / "r.json", _report(_sweep(150)))
    led = tmp_path / "l.jsonl"
    real = di._stream_report
    monkeypatch.setattr(di, "_CHUNK", 64)
    monkeypatch.setattr(di, "_stream_report",
                        lambda p, _d: real(p, time.monotonic() - 1.0))   # expires while reading
    h = di.harvest(rp, led, deadline=time.monotonic() + 3600)
    assert h["status"] == di.DEFERRED and "reading" in h["why"] and h["sha256"]
    assert not led.exists()
    monkeypatch.setattr(di, "_stream_report", real)
    assert di.harvest(rp, led)["appended"] == 150          # the hash was kept; the rest resumes


def test_the_stream_reads_what_json_loads_reads(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(di, "_CHUNK", 5)
    vs: list[Any] = [*_sweep(40), 12, None, [1, 2], _verdict("big", "fx", "X", 1e300)]
    rep = {**_report(vs, census={"method": "participation_ratio", "n_raw": 9,
                                  "n_effective": 3}),
           "verdicts_tail": {"verdicts": "nested key is not the top-level key"}}
    for indent in (None, 1):
        rp = _write(tmp_path / "r.json", rep) if indent is None else tmp_path / "r.json"
        if indent:
            rp.write_text(json.dumps(rep, indent=indent), encoding="utf-8")
        meta, fields = di._stream_report(rp, None)
        want = json.loads(rp.read_text("utf-8"))
        assert meta == {k: want[k] for k in di._REPORT_KEYS if k in want}
        assert di._rows_from(fields, meta, sweep_id="x", judged_at="t") == di.trial_rows(
            want, sweep_id="x", judged_at="t")


@pytest.mark.parametrize("text", ['{"verdicts": [', '\ufeff{"verdicts": []}', "[]", "",
                                  '{"verdicts": []} x', '{"verdicts": [1,]}', '{"a": 1,}',
                                  '{"verdicts": [], "verdicts": [1]}', "{}", "  {  }  "])
def test_a_malformed_report_gets_the_old_verdict(tmp_path: Path, text: str) -> None:
    rp = tmp_path / "r.json"
    rp.write_text(text, encoding="utf-8")
    try:
        whole = json.loads(rp.read_text("utf-8"))
        want = None if isinstance(whole, dict) else f"{di._rel(rp)} is not a mapping"
    except ValueError as exc:
        want = f"{di._rel(rp)}: {type(exc).__name__}"
    h = di.harvest(rp, tmp_path / "l.jsonl")
    if want is None:
        assert h["status"] == di.MEASURED and h["appended"] == 0
    else:
        assert h["status"] == di.UNMEASURED and h["why"] == want


def test_a_measure_that_raises_writes_an_explicit_unmeasured_document(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "o.json"
    rp = _write(tmp_path / "r.json", _report(_sweep(150)))
    di.run(report_path=rp, ledger_path=tmp_path / "l.jsonl", out=out)
    assert di.load_verified(out)[0] is not None

    def broken(**_k: Any) -> Any:
        raise MemoryError("ledger too large")

    monkeypatch.setattr(di, "measure", broken)
    doc = di.run(report_path=rp, ledger_path=tmp_path / "l.jsonl", out=out)
    on_disk = json.loads(out.read_text("utf-8"))
    assert on_disk == json.loads(json.dumps(doc))         # the old document did not survive
    assert doc["status"] == di.UNMEASURED and "MemoryError" in doc["why"]
    assert doc["attempted_at"] and doc["measured_at"] is None
    assert doc["content_sha256"] == di.canonical_sha256(doc)
    got, why = di.load_verified(out)
    assert got is None and why.startswith("dsr_inputs_unmeasured") and "UNMEASURED" in why


def test_a_harvest_that_raises_still_publishes_from_the_ledger(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    led, out = tmp_path / "l.jsonl", tmp_path / "o.json"
    di.run(report_path=_write(tmp_path / "a.json", _report(_sweep(150))), ledger_path=led,
           out=out)
    monkeypatch.setattr(di, "harvest", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    doc = di.run(report_path=_write(tmp_path / "b.json", _report(_sweep(5, prefix="z"))),
                 ledger_path=led, out=out)
    assert doc["status"] == di.MEASURED
    assert doc["provenance"]["harvest"]["status"] == di.UNMEASURED
    assert "OSError" in doc["provenance"]["harvest"]["why"]
    assert di.load_verified(out)[0] is not None


def test_the_script_bounds_the_harvest_inside_the_leg(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_dsr_inputs_budget", ROOT / "desks" / "mt5" / "scripts" / "measure_dsr_inputs.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    assert mod.default_budget_s() == di.DEFAULT_HARVEST_BUDGET_S
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "300")
    assert mod.default_budget_s() == di.DEFAULT_HARVEST_BUDGET_S < 300
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "100")
    assert mod.default_budget_s() == pytest.approx(60.0)
    rp = _write(tmp_path / "r.json", _report(_sweep(120)))
    assert mod.main(["--once", "--report", str(rp), "--ledger", str(tmp_path / "l.jsonl"),
                     "--out", str(tmp_path / "o.json"), "--budget-s", "0"]) == 0
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["harvest_status"] == di.DEFERRED and line["status"] == di.UNMEASURED


@pytest.mark.parametrize("organ", ["harvest", "measure"])
def test_an_exception_holding_a_path_or_host_never_reaches_the_document(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, organ: str) -> None:
    """DSR_INPUTS.json is published box state and its `why` is echoed to the leg's stdout: a
    raised exception is named by its type only, never by its text (audit of 7cd7a86e, MF1)."""
    secret = r"C:\opt\quant\data\secrets\box-host-62.example\token"

    def boom(*_a: Any, **_k: Any) -> Any:
        raise OSError(secret)

    rp = _write(tmp_path / "r.json", _report(_sweep(150)))
    out = tmp_path / "o.json"
    monkeypatch.setattr(di, organ, boom)
    doc = di.run(report_path=rp, ledger_path=tmp_path / "l.jsonl", out=out)
    blob = json.dumps(doc) + out.read_text("utf-8")
    assert "box-host-62" not in blob and "secrets" not in blob
    assert f"{organ} raised OSError" in blob
