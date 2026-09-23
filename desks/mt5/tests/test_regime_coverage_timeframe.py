"""The coverage cell carries the chart (Tier-1 A6): state x family x cluster x timeframe.

Before 2026-09-08 every bucket in REGIME_COVERAGE.json was implicitly H1. Pinned: the label comes
from the certificate (stated), from the desk's own declared default when the certificate carries
params without a chart, and reads UNSTATED -- a bucket of its own, never a silent H1 -- when no
certificate matches the sleeve; the cell key carries it; the instruction names it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.state_admission import Trade  # noqa: E402
from research import regime_coverage as rc  # noqa: E402


def _canon(tmp_path: Path, monkeypatch) -> Path:
    canon = tmp_path / "canon.json"
    canon.write_text(json.dumps({"survivors": {
        "a": {"sym": "XAUUSD", "shadow_spec": {"symbol": "XAUUSD", "family": "fam0",
                                              "params": {"rr": 1.5, "timeframe": "m5"}}},
        "b": {"sym": "XAUUSD", "shadow_spec": {"symbol": "XAUUSD", "family": "fam1",
                                              "params": {"rr": 2.0}}},
        "c": {"sym": "EURUSD", "shadow_spec": {"symbol": "EURUSD", "family": "srb"}},
        "d": {"sym": "GBPUSD", "shadow_spec": {"symbol": "GBPUSD", "family": "fam0",
                                              "params": {"timeframe": "M15"}}},
        "e": {"sym": "GBPUSD", "shadow_spec": {"symbol": "GBPUSD", "family": "fam0",
                                              "params": {"rr": 1.0}}},
    }}), "utf-8")
    monkeypatch.setattr(rc, "CANON", canon)
    return canon


def test_the_map_labels_by_how_it_knows(tmp_path, monkeypatch) -> None:
    _canon(tmp_path, monkeypatch)
    pair, sym_only, basis = rc._timeframe_map()
    assert pair[("XAUUSD", "fam0")] == "M5"            # stated, upper-cased
    assert pair[("XAUUSD", "fam1")] == "H1"            # params without a chart: declared default
    assert pair[("EURUSD", "srb")] == "H1"             # no params at all: the same declared rule
    assert pair[("GBPUSD", "fam0")] == "AMBIGUOUS"     # two certificates, two charts
    assert sym_only == {"EURUSD": "H1"}                # XAUUSD and GBPUSD disagree with themselves
    assert basis == {"stated": 2, "declared_default_H1": 3}


def test_the_labeller_never_defaults_an_unknown_sleeve_to_h1(tmp_path, monkeypatch) -> None:
    _canon(tmp_path, monkeypatch)
    pair, sym_only, _ = rc._timeframe_map()
    fn = rc._timeframe_labeller(pair, sym_only)
    t = lambda sleeve: Trade(sleeve, "2026-01-01T00:00:00+00:00", 0.1, {})  # noqa: E731
    assert fn(t("XAUUSD_fam0_asia")) == "M5"
    assert fn(t("XAUUSD_fam1_asia")) == "H1"
    assert fn(t("EURUSD_asia")) == "H1"                # breakout sleeve: symbol-only fallback
    assert fn(t("USDJPY_fam0_asia")) == rc.UNSTATED_TF  # no certificate anywhere
    assert fn(t("XAUUSD_fam0_asia@M15#rr=2")) == "M15"  # the sleeve key's own chart outranks


def test_absent_canon_reads_every_sleeve_unstated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rc, "CANON", tmp_path / "nope.json")
    assert rc._timeframe_map() == ({}, {}, {})
    fn = rc._timeframe_labeller({}, {})
    assert fn(Trade("XAUUSD_fam0_asia", "2026-01-01T00:00:00+00:00", 0.1, {})) == "UNSTATED"


def _trades() -> list[Trade]:
    rng = np.random.default_rng(0)
    out = []
    for i in range(600):
        tf = "M5" if i % 2 == 0 else "H1"
        sleeve = f"XAUUSD_fam{i % 3}_asia"
        r = (0.3 if (tf == "M5" and i % 3 == 0) else -0.1) + rng.normal(scale=0.3)
        out.append(Trade(sleeve=sleeve, when=f"2026-0{1 + i % 8}-{1 + i % 27:02d}T10:00:00+00:00",
                         r=r, buckets={"global": "A", rc.TIMEFRAME_DIM: tf}))
    return out


def test_the_cell_key_and_the_instruction_carry_the_chart() -> None:
    cov = rc.coverage(_trades(), ("global", rc.TIMEFRAME_DIM))
    assert set(cov) == {"global=A|timeframe=M5", "global=A|timeframe=H1"}
    assert cov["global=A|timeframe=M5"]["n_covering"] >= 1
    assert cov["global=A|timeframe=H1"]["n_covering"] == 0
    tasks = rc.instructions(cov)
    assert [t["state"] for t in tasks] == ["global=A|timeframe=H1"]
    assert tasks[0]["timeframe"] == "H1" and "Chart: H1" in tasks[0]["description"]
    assert rc._timeframe_of_key("global=A|session=ASIA") is None


def test_run_appends_the_chart_axis_and_states_the_denominator(tmp_path, monkeypatch) -> None:
    _canon(tmp_path, monkeypatch)
    monkeypatch.setattr(rc, "OUT", tmp_path / "REGIME_COVERAGE.json")
    monkeypatch.setattr(rc, "QUEUE", tmp_path / "queue.json")
    monkeypatch.setattr(rc, "_admitted", lambda: set())
    monkeypatch.setattr(rc, "_global_regime_labeller", lambda: (lambda t: "A"))
    monkeypatch.setattr(rc, "_cluster_map", lambda: {})
    rows = [Trade("XAUUSD_fam0_asia", f"2026-01-{1 + i % 27:02d}T00:00:00+00:00", 0.2, {})
            for i in range(40)]
    rows += [Trade("USDJPY_fam9_asia", f"2026-01-{1 + i % 27:02d}T00:00:00+00:00", -0.2, {})
             for i in range(40)]
    import research.state_admission_run as sar
    monkeypatch.setattr(sar, "load_trades", lambda basis: rows)
    doc = rc.run(write_queue=False)
    assert doc["dimensions"] == ["global", "timeframe"]
    assert set(doc["coverage"]) == {"global=A|timeframe=M5", "global=A|timeframe=UNSTATED"}
    assert doc["timeframes"] == {"M5": 1, "UNSTATED": 1}
    assert doc["timeframe_basis"] == {"stated": 2, "declared_default_H1": 3,
                                      "sleeves_unstated": 1}
    assert "timeframe_certificates" not in doc["gaps"]
