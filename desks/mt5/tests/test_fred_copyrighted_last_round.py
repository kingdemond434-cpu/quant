"""The last third-party FRED readers (coordinator ruling, 2026-10-20).

screen_fred_macro_axis (VIXCLS), run_cot_screen (SP500), fetch_sge_premium (the LBMA PM fix),
fetch_alfred and the data/vintages revision store: a series terms_fence `fred_copyrighted` names
is refused before any request, published as UNMEASURED_NO_LICENSED_SOURCE with a missed_growth
line, and an old file of it is kept on disk but never read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import free_data as fd  # noqa: E402


def _series(n: int = 60) -> dict[str, float]:
    days = pd.date_range("2024-01-01", periods=n, freq="D")
    return {d.date().isoformat(): 1.0 + i / 100 for i, d in enumerate(days)}


@pytest.fixture
def fred_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Every fred_series call, answered from memory: a refused id must never reach it."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake(series_id: str, start: str = "2010-01-01", vintage: str | None = None,
             **kw: Any) -> dict[str, float]:
        calls.append((series_id, {"start": start, **kw}))
        return _series()

    monkeypatch.setattr(fd, "fred_series", fake)
    return calls


# ------------------------------------------------------------- screen_fred_macro_axis
def test_the_macro_screen_refuses_vixcls_before_any_request(
        fred_calls: list[tuple[str, dict[str, Any]]]) -> None:
    import screen_fred_macro_axis as sfm
    sfm.UNMEASURED.clear()
    assert sfm.fred_deep("VIXCLS") is None
    row = sfm.UNMEASURED["VIXCLS"]
    assert row["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    assert row["missed_growth"]["policy_row"] == "fred_copyrighted"
    assert row["missed_growth"]["delta_elogw"] == "UNMEASURED"
    s = sfm.fred_deep("DGS10")
    assert s is not None and len(s) == 60
    assert [c[0] for c in fred_calls] == ["DGS10"]
    # deep history, uncached (the 6h cache key carries no start), no unread mirror
    assert fred_calls[0][1] == {"start": "1900-01-01", "alternate": False, "use_cache": False}


def test_the_macro_screen_has_no_bare_urlopen_and_reads_no_key() -> None:
    text = (ROOT / "scripts" / "screen_fred_macro_axis.py").read_text("utf-8")
    assert "urlopen(" not in text and "import urllib" not in text
    assert "data/secrets" not in text


# ------------------------------------------------------------------- run_cot_screen
def test_the_cot_screen_refuses_sp500_and_names_us500_as_metadata(
        fred_calls: list[tuple[str, dict[str, Any]]]) -> None:
    import run_cot_screen as cot
    with pytest.raises(cot.FredRefused) as exc:
        cot._fred("SP500")
    row = exc.value.row
    assert row["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    assert row["substitute"] == "mt5_own_bars:US500"
    assert row["missed_growth"]["policy_row"] == "fred_copyrighted"
    assert cot._fred("DGS10") == _series()
    assert [c[0] for c in fred_calls] == ["DGS10"]
    text = (ROOT / "scripts" / "run_cot_screen.py").read_text("utf-8")
    assert "fredgraph.csv" not in text      # FRED is reached only through free_data


# ---------------------------------------------------------------- fetch_sge_premium
def test_the_sge_premium_refuses_the_pm_fix_and_labels_its_gold_leg(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
        fred_calls: list[tuple[str, dict[str, Any]]]) -> None:
    import fetch_sge_premium as sge
    monkeypatch.setattr(sge, "REPORTS", tmp_path)
    monkeypatch.setattr(sge, "fetch_sge", lambda: ({}, "fixture"))
    assert sge.main() == 2                                    # no SGE print: fails closed
    rep = json.loads((tmp_path / "sge_premium.json").read_text("utf-8"))
    assert rep["intl_leg"]["series"] == "XAUUSD"
    assert "NOT the LBMA PM fix" in rep["intl_leg"]["label"]
    assert rep["unmeasured_no_licensed_source"]["GOLDPMGBD228NLBM"]["substitute"] == \
        "mt5_own_bars:XAUUSD"
    assert rep["missed_growth"][0]["policy_row"] == "fred_copyrighted"
    # the USDCNY fallback goes through the fence, never a bare GET
    s = sge._fred_series("DEXCHUS", "usdcny")
    assert s is not None and s.name == "usdcny"
    assert [c[0] for c in fred_calls] == ["DEXCHUS"]
    assert "fredgraph.csv" not in (DESK / "research" / "fetch_sge_premium.py").read_text("utf-8")


# --------------------------------------------------------------------- fetch_alfred
def test_alfred_refuses_a_third_party_series_even_on_request(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import fetch_alfred as fa
    asked: list[str] = []
    monkeypatch.setattr(fa, "api_key", lambda: "k")
    monkeypatch.setattr(fa, "fetch_vintages", lambda sid, key, **k: asked.append(sid))
    monkeypatch.setattr(fa, "REPORTS", tmp_path)
    monkeypatch.setattr(fa, "OUT", tmp_path / "alfred")
    (tmp_path / "alfred").mkdir()
    (tmp_path / "alfred" / "VIXCLS.parquet").write_bytes(b"old")   # an old file stays put
    fa.main(["VIXCLS", "PAYEMS"])
    assert asked == ["PAYEMS"]
    rep = json.loads((tmp_path / "alfred_vintages.json").read_text("utf-8"))
    assert rep["unmeasured_no_licensed_source"]["VIXCLS"]["status"] == \
        fd.UNMEASURED_NO_LICENSED_SOURCE
    assert "VIXCLS" not in rep["skipped_already_present"]
    assert (tmp_path / "alfred" / "VIXCLS.parquet").read_bytes() == b"old"


# ------------------------------------------------------------- the data/vintages store
def _plant_log(root: Path, series: str) -> Path:
    from libs.research import vintage
    path = root / vintage.STORE_DIR / f"{series}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"series": series, "period": p, "value": v,
                                        "vintage": "2026-01-01"}) + "\n"
                            for p, v in _series(10).items()), "utf-8")
    return path


def test_an_old_vixcls_log_is_kept_but_never_read_or_extended(tmp_path: Path) -> None:
    from libs.research import vintage
    path = _plant_log(tmp_path, "VIXCLS")
    before = path.read_bytes()
    assert vintage.read_log(tmp_path, "VIXCLS") == []
    assert vintage.latest_known(tmp_path, "VIXCLS") == {}
    assert vintage.as_of(tmp_path, "VIXCLS", "2026-06-01") == {}
    assert vintage.revisions(tmp_path, "VIXCLS") == []
    assert vintage.summarise(tmp_path, "vixcls")["status"] == \
        vintage.UNMEASURED_NO_LICENSED_SOURCE
    assert vintage.record(tmp_path, "VIXCLS", {"2026-02-01": 20.0}, vintage="2026-02-02") == 0
    assert path.read_bytes() == before                         # not deleted, not appended


def test_a_public_domain_log_still_reads(tmp_path: Path) -> None:
    from libs.research import vintage
    _plant_log(tmp_path, "DGS10")
    assert len(vintage.latest_known(tmp_path, "DGS10")) == 10
    assert vintage.record(tmp_path, "DGS10", {"2030-01-01": 4.0}, vintage="2030-01-02") == 1


def test_the_data_os_census_names_the_licence(tmp_path: Path) -> None:
    from libs.tiers import data_os
    _plant_log(tmp_path, "VIXCLS")
    assert data_os.vintage_series((tmp_path,)) == {"VIXCLS": tmp_path}   # listed, by name
    assert data_os._vintage_summary(tmp_path, "VIXCLS")["status"] == \
        "UNMEASURED_NO_LICENSED_SOURCE"


def test_the_bill_reads_the_last_round_carriers() -> None:
    import missed_growth as mg
    organs = {o for o, _ in mg.FRED_COPYRIGHTED_CUT_ARTIFACTS}
    assert {"screen_fred_macro_axis", "run_cot_screen", "fetch_sge_premium"} <= organs
