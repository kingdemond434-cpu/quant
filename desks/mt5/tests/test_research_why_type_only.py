"""Three research reports publish an exception's TYPE, never its text (audit, 2026-11-18).

An exception message can carry a filesystem path, a host or a credential. Each test injects one
that carries all three, lets the module write its report, and reads the WRITTEN file:

- OCCUPANCY_MAP.json["culture_orthogonality"]      research/occupancy_map.culture_pass
- DOCKET_KEFF_ORDER.json["symbol_deltas"]           research/docket_keff.symbol_deltas
- merge_report.json["hypothesis_families"]          research/hypothesis_families.apply,
                                                    research/merge_hypotheses (the same field)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for _p in (str(DESK), str(DESK.parents[1]), str(TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pd = pytest.importorskip("pandas")

from research import docket_keff as dk  # noqa: E402
from research import hypothesis_families as hf  # noqa: E402
from research import occupancy_map as om  # noqa: E402

SECRET = "fake-token-for-test-only"  # noqa: S105 - a stand-in, not a credential
HOST = "db.internal.example"
LEAK_PATH = "/data/secrets/broker"


class _Leaky(Exception):
    pass


class _LeakyValue(ValueError):
    pass


def _message() -> str:
    return f"connect https://{HOST}{LEAK_PATH}/key={SECRET} failed"


def _raise(cls: type[Exception] = _Leaky) -> Any:
    def boom(*_a: object, **_k: object) -> Any:
        raise cls(_message())
    return boom


def _assert_clean(text: str) -> None:
    for needle in (SECRET, HOST, LEAK_PATH, "connect https://"):
        assert needle not in text, f"{needle!r} reached the written report"


def test_occupancy_map_publishes_the_culture_fault_type_only(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    from research import culture_orthogonality as co
    monkeypatch.setattr(co, "run", _raise())
    block = om.culture_pass([], dry_run=True)
    report = tmp_path / "OCCUPANCY_MAP.json"
    om.write({"culture_orthogonality": block}, [], report=report, intake=tmp_path / "intake")
    text = report.read_text("utf-8")
    assert json.loads(text)["culture_orthogonality"] == {"status": "ERROR", "why": "_Leaky"}
    _assert_clean(text)


def test_docket_keff_publishes_a_symbol_fault_type_only(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2024-01-01", periods=400, freq="D", tz="UTC")
    panel = {s: pd.Series(rng.normal(0, 0.01, 400), index=idx) for s in ("A", "INDEP")}
    monkeypatch.setattr(dk, "exposure_neff", _raise(_LeakyValue))
    rows = [{"family": "carry", "symbol": "INDEP", "params": {"i": 1}}]
    doc = dk.score(rows, breadth={"exposure_by_instrument": {"A": 1.0},
                                  "nominal": {"sleeves_in_the_measurement": 1}},
                   canon={}, loader=panel.get, read_artifacts=False)
    report = dk.publish(doc, tmp_path / "DOCKET_KEFF_ORDER.json")
    text = report.read_text("utf-8")
    got = json.loads(text)["symbol_deltas"]["INDEP"]
    assert got["status"] == "UNMEASURED" and got["why"] == "_LeakyValue", got
    _assert_clean(text)


@pytest.mark.parametrize("where", ["inside_apply", "apply_raises", "commit_raises"])
def test_merge_report_publishes_the_families_fault_type_only(where: str, tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    import test_hypothesis_families as thf

    from research import judge_coverage as jc
    from research import merge_hypotheses as mh
    hyp = tmp_path / "hypotheses"
    hyp.mkdir()
    target = hyp / "external_survivors.json"
    banked = [thf._row("EURUSD", fam="session_range_breakout", session="asia"),
              thf._row("XAUUSD", fam="session_range_breakout", session="london")]
    target.write_text(json.dumps(banked), "utf-8")
    fresh = {"hypotheses": [thf._row("EURUSD", fam="session_range_breakout", session="asia",
                                     range_hours=5)]}
    (hyp / "miner_candidates.json").write_text(json.dumps(fresh), "utf-8")
    monkeypatch.setattr(mh, "HYP", hyp)
    monkeypatch.setattr(mh, "TARGET", target)
    monkeypatch.setattr(mh, "tradeable_universe", lambda: {})
    monkeypatch.setattr(mh, "_pipeline_started_at", lambda: None)
    monkeypatch.setattr(mh, "_ack", lambda path: None)
    monkeypatch.setattr(mh, "_lease", lambda path: None)
    from libs.research import claim_selection as cs
    monkeypatch.setattr(cs, "LEDGER", hyp / "claim_families.json")
    monkeypatch.setattr(jc, "order_docket", lambda rows, **k: (rows, {}))
    monkeypatch.setattr(hf, "_daily", lambda s, u: None)
    monkeypatch.setattr(hf, "_lawful", lambda: (lambda s, f: True))
    monkeypatch.setattr(hf, "_unrunnable", lambda: thf.NOBLOCK)
    if where == "inside_apply":
        monkeypatch.setattr(hf, "load_clusters", _raise())
    elif where == "apply_raises":
        monkeypatch.setattr(hf, "apply", _raise())
    else:
        monkeypatch.setattr(hf.Pending, "commit", _raise())
    before = thf._tree_state()
    assert mh.main() == 0
    assert thf._tree_state() == before, "the merge test wrote a desk file"
    text = (hyp / "merge_report.json").read_text("utf-8")
    fam = json.loads(text)["hypothesis_families"]
    got = fam["commit"]["status"] if where == "commit_raises" else fam["status"]
    assert got == "FAILED: _Leaky", fam
    _assert_clean(text)
