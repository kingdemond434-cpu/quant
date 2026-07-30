"""Reality-gap engine (L2.10) -- must fail LOUD on missing links, call a sign flip a BREAK
whatever the magnitude, and reproduce the two gaps the desk found by hand."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

_SPEC = importlib.util.spec_from_file_location(
    "run_reality_gap", Path(__file__).resolve().parents[2] / "scripts/run_reality_gap.py")
assert _SPEC is not None and _SPEC.loader is not None
_MOD: ModuleType = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def _run(tmp_path: Path, monkeypatch: Any) -> dict[str, Any]:
    monkeypatch.chdir(tmp_path)
    _MOD._OUT = tmp_path / "web/reality_gap.json"
    _MOD.main()
    out: dict[str, Any] = json.loads((tmp_path / "web/reality_gap.json").read_text("utf-8"))
    return out


def _write(tmp_path: Path, rel: str, payload: Any) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), "utf-8")


def test_no_feeds_is_no_data_never_ok(tmp_path: Path, monkeypatch: Any) -> None:
    rep = _run(tmp_path, monkeypatch)
    assert rep["overall"] == "NO-DATA"
    assert len(rep["missing_links"]) == len(rep["links"])


def test_sign_flip_is_always_a_break(tmp_path: Path, monkeypatch: Any) -> None:
    # Shadow says +1.2, live says -0.06 (the desk's actual deployed Sharpe sign problem).
    _write(tmp_path, "web/cashcarry_shadow.json", {"ann_sharpe": 1.2})
    _write(tmp_path, "web/cashcarry_live.json", {"ann_sharpe": -0.06})
    rep = _run(tmp_path, monkeypatch)
    link = next(x for x in rep["links"] if x["link"] == "shadow_sharpe -> live_sharpe")
    assert link["verdict"] == "BREAK"
    assert "SIGN FLIP" in link["detail"]
    assert rep["overall"] == "BREAK"


def test_fee_fire_ratio_reads_break(tmp_path: Path, monkeypatch: Any) -> None:
    # The 7.75x class: modelled ~5 bps, realised ~39 bps round-trip.
    _write(tmp_path, "data/cost_model.json",
           {"symbols": {"A": {"fut_sell": {"500": {"median_bps": 5.0}}},
                        "B": {"fut_sell": {"500": {"median_bps": 5.0}}}}})
    _write(tmp_path, "data/cashcarry_trades.json", [{"rt_bps": 39.0} for _ in range(20)])
    rep = _run(tmp_path, monkeypatch)
    link = next(x for x in rep["links"] if x["link"].startswith("modelled_cost"))
    assert link["verdict"] == "BREAK"
    assert link["ratio"] > 3.0


def test_venue_truth_offset_reads_break(tmp_path: Path, monkeypatch: Any) -> None:
    # The measured 36.4% definitional offset (register #19) must be VISIBLE, not silent.
    _write(tmp_path, "web/cashcarry_live.json", {"equity": 15000.0})
    _write(tmp_path, "web/venue_equity.json", {"equity": 9540.0})
    rep = _run(tmp_path, monkeypatch)
    link = next(x for x in rep["links"] if x["link"].startswith("book_equity"))
    assert link["verdict"] == "BREAK"
    assert 0.30 < link["relative_diff"] < 0.40


def test_aligned_chain_reads_ok(tmp_path: Path, monkeypatch: Any) -> None:
    _write(tmp_path, "web/discovery.json", {"sharpe": 1.0})
    _write(tmp_path, "web/cashcarry_shadow.json", {"ann_sharpe": 0.9})
    _write(tmp_path, "web/cashcarry_shadow_8h.json", {"ann_sharpe": 0.8})
    _write(tmp_path, "web/cashcarry_live.json", {"ann_sharpe": 0.85, "equity": 10000.0})
    _write(tmp_path, "web/venue_equity.json", {"equity": 10100.0})
    _write(tmp_path, "data/cost_model.json",
           {"symbols": {"A": {"fut_sell": {"500": {"median_bps": 10.0}}}}})
    _write(tmp_path, "data/cashcarry_trades.json", [{"rt_bps": 11.0} for _ in range(20)])
    rep = _run(tmp_path, monkeypatch)
    assert rep["overall"] == "OK", rep["links"]
    assert rep["open_gaps"] == []


def test_engine_never_writes_outside_its_report(tmp_path: Path, monkeypatch: Any) -> None:
    _write(tmp_path, "web/cashcarry_shadow.json", {"ann_sharpe": 1.0})
    _run(tmp_path, monkeypatch)
    written = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert "web/reality_gap.json" in written
    # It measures; it must never touch state, book or config files.
    assert not [w for w in written if w.startswith(("data/cashcarry_positions",
                                                    "data/deadman", "data/cashcarry_config"))]
