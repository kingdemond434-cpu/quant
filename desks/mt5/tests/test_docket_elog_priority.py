"""docket_elog_priority (idea 617): bases, the score rule, the family rollup, the cap, the write."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parents[1]), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.frontier_identity import cell_id  # noqa: E402

from research import docket_elog_priority as D  # noqa: E402

NAMES = ["USDJPY_session_range_breakout_asia", "EURZAR_overnight_gap_decay_asia",
         "GBPZAR_overnight_gap_decay_asia"]


def _cells() -> dict[str, dict]:
    return {
        "a": {"sym": "USDJPY", "family": "session_range_breakout", "session": "asia"},
        "b": {"sym": "AUDCAD", "family": "overnight_gap_decay", "session": "asia"},
        "c": {"sym": "AUDCAD", "family": "carry", "session": ""},
    }


def _price(**kw):
    args: dict = {
        "names": NAMES, "grad": {NAMES[0]: 0.02},
        "rho": {NAMES[1]: 0.4, NAMES[2]: 0.2},
        "surv": {"overnight_gap_decay": 0.06, "carry": 0.01},
        "edge": {"overnight_gap_decay": 0.05},
        "meter": {"session_range_breakout": {"n": 10, "s": 20.0, "max_s": 4, "warmed": 10}},
    }
    args.update(kw)
    return {r["cell"]: r for r in D.price(_cells(), **args)}


def test_measured_prior_unmeasured_bases():
    rows = _price()
    a, b, c = rows["a"], rows["b"], rows["c"]
    assert a["basis_d_elog"] == "MEASURED" and a["d_elog_per_day"] == 0.02 * D.STEP_HEAT
    assert b["basis_d_elog"] == "PRIOR"
    assert abs(b["d_elog_per_day"] - 0.06 * 0.05 * (1 - 0.3)) < 1e-12
    assert D.PRIOR_FORMULA in b["formula"]
    # carry: no posterior edge and no column to read rho from -> null, never zero
    assert c["basis_d_elog"] == "UNMEASURED" and c["d_elog_per_day"] is None
    assert "posterior_edge (POSTERIOR_ALPHA.json)" in c["formula"]
    assert "rho_to_live_book (worlds.npz+sleeves.json)" in c["formula"]
    assert a["basis_cpu"] == "MEASURED" and a["cpu_s_est"] == 2.0
    assert b["basis_cpu"] == "PRIOR"
    assert set(a) == {"cell", "family", "sym", "d_elog_per_day", "cpu_s_est", "score",
                      "score_basis", "basis_d_elog", "basis_cpu", "formula"}


def test_cpu_unmeasured_without_meter():
    rows = _price(meter={})
    assert all(r["basis_cpu"] == "UNMEASURED" and r["cpu_s_est"] is None for r in rows.values())


def test_score_rules():
    rows = _price()
    a = rows["a"]
    assert a["score"] == round(0.02 * D.STEP_HEAT / 2.0, 12) and a["score_basis"] == "MEASURED"
    # PRIOR d_elog x PRIOR cpu -> null
    assert rows["b"]["score"] is None and rows["b"]["score_basis"] is None
    # MEASURED d_elog x UNMEASURED cpu -> null
    assert _price(meter={})["a"]["score"] is None
    # PRIOR d_elog x MEASURED cpu -> a PRIOR score
    b = _price(meter={"overnight_gap_decay": {"n": 2, "s": 2.0}})["b"]
    assert b["score_basis"] == "PRIOR"
    assert abs(b["score"] - 0.06 * 0.05 * 0.7 / 1.0) < 1e-12
    # UNMEASURED d_elog x MEASURED cpu -> null
    c = _price(meter={"carry": {"n": 1, "s": 3.0}})["c"]
    assert c["basis_cpu"] == "MEASURED" and c["score"] is None


def test_family_rollup_separate_bases():
    fams = D.rollup(list(_price().values()))
    srb = fams["session_range_breakout"]
    assert srb["basis_d_elog"] == "MEASURED" and srb["basis_cpu"] == "MEASURED"
    assert srb["n_scored"] == 1 and srb["n_measured"] == 1
    ogd = fams["overnight_gap_decay"]
    assert ogd["basis_d_elog"] == "PRIOR" and ogd["basis_cpu"] == "PRIOR"
    assert ogd["score_median"] is None and ogd["n_scored"] == 0 and ogd["n_cells"] == 1
    assert ogd["basis_d_elog_counts"] == {"MEASURED": 0, "PRIOR": 1, "UNMEASURED": 0}
    assert fams["carry"]["basis_d_elog"] == "UNMEASURED"


def test_rollup_median_over_non_null_scores_only():
    def row(score, bd):
        return {"family": "f", "score": score, "score_basis": None if score is None else bd,
                "basis_d_elog": bd, "basis_cpu": "MEASURED"}
    rows = [row(1.0, "MEASURED"), row(3.0, "PRIOR"), row(None, "UNMEASURED"),
            row(None, "UNMEASURED"), row(None, "UNMEASURED")]
    f = D.rollup(rows)["f"]
    assert f["score_median"] == 2.0 and f["n_scored"] == 2 and f["n_cells"] == 5
    assert f["basis_d_elog"] == "UNMEASURED" and f["basis_cpu"] == "MEASURED"
    assert f["basis_d_elog_counts"] == {"MEASURED": 1, "PRIOR": 1, "UNMEASURED": 3}


def _docket(tmp_path: Path, n: int) -> Path:
    rows = [{"symbol": f"S{i}", "family": f"fam{i % 7}", "params": {"k": i}} for i in range(n)]
    p = tmp_path / "external_survivors.json"
    p.write_text(json.dumps(rows), "utf-8")
    return p


def test_cell_key_is_the_gauntlet_cell_id(tmp_path):
    cells = D.docket_cells(_docket(tmp_path, 3))
    assert cell_id({"sym": "S1", "family": "fam1", "params": {"k": 1}}) in cells


def test_cap_keeps_rollup_complete(tmp_path):
    doc = D.build(docket=_docket(tmp_path, 50), worlds=tmp_path / "none.npz",
                  warm=tmp_path / "none.json", max_rows=5)
    assert doc["n_total"] == 50 and doc["n_rows"] == 5 and doc["capped"] is True
    assert len(doc["rows"]) == 5
    assert set(doc["families"]) == {f"fam{i}" for i in range(7)}
    assert sum(f["n_cells"] for f in doc["families"].values()) == 50
    assert doc["report_only"] is True and doc["consumer"] is None
    assert doc["intended_consumer"] == D.INTENDED_CONSUMER


def test_worlds_rho_reads_the_cache(tmp_path):
    r = np.random.default_rng(0).normal(size=(2, 50, 3)).astype("float32")
    np.savez(tmp_path / "w.npz", r=r, names=np.array(NAMES))
    names, arr = D.load_worlds(tmp_path / "w.npz")
    rho = D.book_rho(names, arr, set())
    assert set(rho) == set(NAMES) and all(0 <= v <= 1 for v in rho.values())


def test_atomic_write(tmp_path, monkeypatch):
    out = tmp_path / "DOCKET_ELOG_PRIORITY.json"
    out.write_text('{"old": true}', "utf-8")
    calls = []
    real = D.os.replace

    def spy(src, dst):
        calls.append((Path(src), Path(dst)))
        assert json.loads(Path(src).read_text("utf-8")) == {"new": 1}
        assert json.loads(Path(dst).read_text("utf-8")) == {"old": True}
        real(src, dst)

    monkeypatch.setattr(D.os, "replace", spy)
    D.write_atomic({"new": 1}, out)
    assert calls and calls[0][1] == out and calls[0][0] != out
    assert json.loads(out.read_text("utf-8")) == {"new": 1}
    assert not list(tmp_path.glob("*.tmp*"))
