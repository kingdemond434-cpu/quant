"""Yield-curve lake packs: US H.15, ECB AAA and MoF JGB curves, slopes, cross-market spreads.

Fixtures are written from each publisher's documented public format (the hosts are proxy-blocked
from the build container, so liveness from here is UNMEASURED). Pinned:

  1. the MoF CSV parser (English `Date`/`10Y` and Japanese era `基準日`/`10年`), `-` is missing;
  2. PIT stamping per publisher, never the period date, and a spread at the LATER leg's stamp;
  3. 2s10s slopes, cross-market spreads and their weekly changes;
  4. the packs land where pack_cells and family_exogenous_conditioner read them, with targets;
  5. liveness: a pack or JGB series empty for more than two passes is RED;
  6. the CNY fix is UNMEASURED_NO_LICENSED_SOURCE with its missed-growth line;
  7. a 403 from MoF is a hard stop with no further request.
"""
from __future__ import annotations

import json
import sys
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import axis_ingest as ai  # noqa: E402
from research import axis_ingest_all as A  # noqa: E402

JGB_EN = ("Interest Rate,,,,,,,,,,,,,,,\n"
          "Date,1Y,2Y,3Y,4Y,5Y,6Y,7Y,8Y,9Y,10Y,15Y,20Y,25Y,30Y,40Y\n"
          "2026/10/29,0.6,0.9,1,1,1.1,1.2,1.3,1.4,1.5,1.7,2.2,2.6,2.9,3.1,3.4\n"
          "2026/10/30,0.6,0.92,1,1,1.1,1.2,1.3,1.4,1.5,1.72,2.2,2.6,2.9,-,3.4\n")
JGB_JA = ("国債金利情報,,,,,,,,,,,,,,,(単位：%)\n"  # noqa: RUF001 -- the file's own full-width colon
          "基準日,1年,2年,3年,4年,5年,6年,7年,8年,9年,10年,15年,20年,25年,30年,40年\n"
          "R8.10.22,0.6,0.88,1,1,1.1,1.2,1.3,1.4,1.5,1.69,2.2,2.6,2.9,3.05,3.4\n")


def _doc(pts: dict[str, list[tuple[str, float]]]) -> dict:
    return {"n_series": len(pts),
            "series": {k: {"points": [{"d": d, "v": v} for d, v in p]} for k, p in pts.items()}}


DAYS = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23",
        "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]


def _docs() -> dict[str, dict]:
    def ramp(base: float, step: float) -> list[tuple[str, float]]:
        return [(d, round(base + step * i, 4)) for i, d in enumerate(DAYS)]
    return {"fred": _doc({"DGS2": ramp(3.5, 0.01), "DGS5": ramp(3.7, 0.01),
                          "DGS10": ramp(4.1, 0.02), "DGS30": ramp(4.6, 0.02)}),
            "ecb": _doc({"eur_aaa_2y": ramp(2.0, 0.0), "eur_aaa_10y": ramp(2.6, 0.01),
                         "eur_aaa_30y": ramp(3.0, 0.01)}),
            "jgb": _doc({"jgb_2y": ramp(0.9, 0.0), "jgb_10y": ramp(1.7, 0.01),
                         "jgb_30y": ramp(3.1, 0.01)})}


def test_the_mof_csv_parses_in_both_languages() -> None:
    en = ai.parse_jgb_csv(JGB_EN)
    assert en["jgb_10y"] == [("2026-10-29", 1.7), ("2026-10-30", 1.72)]
    assert en["jgb_2y"][-1] == ("2026-10-30", 0.92)
    assert en["jgb_30y"] == [("2026-10-29", 3.1)]          # "-" is missing, never zero
    ja = ai.parse_jgb_csv(JGB_JA)
    assert ja["jgb_10y"] == [("2026-10-22", 1.69)]          # Reiwa 8 = 2026
    with pytest.raises(ValueError):
        ai.parse_jgb_csv("<html>blocked</html>")


def test_ingest_jgb_merges_current_over_history_and_stops_on_403() -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return (JGB_JA if "historical" in url else JGB_EN).encode("utf-8")
    doc = ai.ingest_jgb(fetch=fetch)
    assert doc["series_state"] == {"jgb_2y": "OK", "jgb_10y": "OK", "jgb_30y": "OK"}
    assert doc["series"]["jgb_10y"]["first"] == "2026-10-22"

    calls.clear()

    def refused(url: str) -> bytes:
        calls.append(url)
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]
    doc = ai.ingest_jgb(fetch=refused)
    assert len(calls) == 1 and doc["n_series"] == 0
    assert all("HTTP_403" in v for v in doc["failed"].values())


def test_every_row_is_stamped_at_availability_never_the_period_date() -> None:
    # FRED H.15: next business day; Friday's print is known Monday.
    assert ai.available_time("fred", "2026-10-30") == "2026-11-02T22:00:00+00:00"
    # ECB YC: noon CET the next TARGET day, stamped 12:00 UTC (later in either season).
    assert ai.available_time("ecb", "2026-10-29") == "2026-10-30T12:00:00+00:00"
    # MoF: 09:30 JST next business day = 00:30 UTC, stamped 01:00 UTC.
    assert ai.available_time("jgb", "2026-10-29") == "2026-10-30T01:00:00+00:00"
    packs = ai.build_yield_packs(_docs())
    for rows in packs.values():
        for r in rows:
            assert r["available_time"][:10] > r["event_time"]
    # A spread is known only when both legs are: the FRED leg's later stamp.
    sp = {r["event_time"]: r for r in packs[ai.SPREAD_PACK]}
    assert sp["2026-10-29"]["available_time"] == "2026-10-30T22:00:00+00:00"


def test_slopes_spreads_and_weekly_changes() -> None:
    packs = ai.build_yield_packs(_docs())
    us = {r["event_time"]: r for r in packs["yc_us_treasury"]}
    assert us["2026-10-30"]["us_2s10s"] == pytest.approx((4.1 + 0.18) - (3.5 + 0.09))
    # the weekly change compares with the last value at or before d-7 (2026-10-23, index 4)
    assert us["2026-10-30"]["us_2s10s_wchg"] == pytest.approx(0.05)
    assert us["2026-10-19"]["us_2s10s_wchg"] is None
    for pid, col in (("yc_ea_aaa", "ea_2s10s"), ("yc_jp_jgb", "jp_2s10s")):
        last = packs[pid][-1]
        assert last[col] is not None and last[f"{col}_wchg"] == pytest.approx(0.05)
    sp = packs[ai.SPREAD_PACK][-1]
    assert sp["us_ea_aaa_10y"] == pytest.approx((4.1 + 0.18) - (2.6 + 0.09))
    assert sp["us_jp_10y"] == pytest.approx((4.1 + 0.18) - (1.7 + 0.09))
    assert sp["us_jp_10y_wchg"] == pytest.approx(0.05)


def test_packs_land_where_pack_cells_and_the_family_read_them(tmp_path: Path) -> None:
    from mt5desk import family_exogenous_conditioner as fec

    from research import pack_cells
    sdir, vdir = tmp_path / "series", tmp_path / "vault"
    out = ai.publish_yield_packs(_docs(), series_dir=sdir, vault_dir=vdir)
    assert out["n_series"] == 4 and set(out["series_state"].values()) == {"OK"}
    for pid in ai.PACK_TARGETS:
        assert (sdir / f"{pid}.csv").exists() and (vdir / pid).is_dir()
        pit = json.loads((sdir / f"{pid}.pit.json").read_text(encoding="utf-8"))
        assert pit["n_rows"] > 0 and pit["frames"][0]["status"] == "STAMPED"
    sigs, n, why = pack_cells.signals_of(sdir / "yc_xmkt_spreads.csv")
    assert {"us_ea_aaa_10y", "us_jp_10y"} <= set(sigs) and n == len(DAYS) and not why
    assert not {"available_time", "event_time", "source_id"} & set(sigs)
    s = fec.conditioner("yc_us_treasury", "us_2s10s", "delta", root=sdir)
    assert s is not None and not s.empty
    # lagged a further 24h past the availability stamp before it may condition a bar
    assert str(s.index.min()) > "2026-10-21T22:00"


def test_the_registry_declares_every_pack_with_its_targets() -> None:
    reg = json.loads((_DESK / "data" / "asia_sources.json").read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in reg["sources"]}
    for pid, targets in ai.PACK_TARGETS.items():
        assert rows[pid]["targets"] == targets
    wanted = {"EURUSD", "USDJPY", "GER40", "JPN225", "US500", "UST10Y", "UST05Y"}
    assert wanted <= {t for ts in ai.PACK_TARGETS.values() for t in ts}
    from research import pack_cells
    for pid in ai.PACK_TARGETS:
        assert pack_cells._fenced_pack(rows[pid]) is None


def test_an_empty_pass_never_blanks_a_pack(tmp_path: Path) -> None:
    sdir = tmp_path / "series"
    ai.publish_yield_packs(_docs(), series_dir=sdir, vault_dir=tmp_path / "v")
    before = (sdir / "yc_jp_jgb.csv").read_text(encoding="utf-8")
    docs = _docs()
    docs["jgb"] = {"n_series": 0, "series": {}}
    out = ai.publish_yield_packs(docs, series_dir=sdir, vault_dir=tmp_path / "v")
    assert out["series_state"]["yc_jp_jgb"] == "EMPTY"
    assert (sdir / "yc_jp_jgb.csv").read_text(encoding="utf-8") == before


def test_liveness_turns_red_after_more_than_two_empty_passes() -> None:
    assert "jgb" in A.EXTERNAL_AXES and "yield_packs" in A.EXTERNAL_AXES
    axes = {"yield_packs": {"n": 3, "series_state": {"yc_jp_jgb": "EMPTY", "yc_us_treasury": "OK"},
                            "failed": {"yc_jp_jgb": "EMPTY"}},
            "jgb": {"n": 0, "series_state": {"jgb_10y": "EMPTY"}, "failed": {}}}
    live: dict | None = None
    verdicts = []
    for _ in range(3):
        live = A.update_liveness(live, axes, datetime.now(tz=UTC))
        verdicts.append(live["dependencies"]["yield_packs/yc_jp_jgb"]["verdict"])
    assert verdicts == ["AMBER", "AMBER", "RED"]
    assert "jgb/jgb_10y" in live["red"] and live["verdict"] == "RED"
    assert live["dependencies"]["yield_packs/yc_us_treasury"]["verdict"] == "GREEN"


def test_the_ingest_leg_builds_the_packs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import types
    seen: dict = {}
    stub = types.ModuleType("axis_ingest")
    docs = _docs()
    stub.INGESTERS = {k: (lambda d=d: d) for k, d in docs.items()}  # type: ignore[attr-defined]

    def publish(d: dict, apply: bool = True) -> dict:
        seen.update(d)
        return ai.publish_yield_packs(d, series_dir=tmp_path / "s", vault_dir=tmp_path / "v",
                                      apply=apply)
    stub.publish_yield_packs = publish  # type: ignore[attr-defined]
    monkeypatch.setattr(A, "OUT_DIR", tmp_path / "axes")
    monkeypatch.setitem(sys.modules, "axis_ingest", stub)
    doc = A.run_all(apply=False)
    assert set(seen) == {"ecb", "fred", "jgb"}
    assert doc["axes"]["yield_packs"]["state"] == "OK"
    assert doc["axes"]["yield_packs"]["n"] == 4


def test_the_cny_fix_is_unmeasured_with_its_missed_growth_line() -> None:
    hold = ai.CNY_FIX_HOLD
    assert hold["status"] == "UNMEASURED_NO_LICENSED_SOURCE"
    assert hold["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert "DEXCHUS" in json.dumps(hold["tried"])
    out = ai.publish_yield_packs(_docs(), apply=False)
    assert out["held"]["cny_central_parity"] is hold and out["missed_growth"]


def test_new_fred_and_ecb_series_are_requested() -> None:
    assert {"DGS2", "DGS5", "DGS10", "DGS30"} <= set(ai.FRED_SERIES)
    assert {"eur_aaa_2y", "eur_aaa_10y", "eur_aaa_30y"} <= set(ai.ECB_SERIES)
    assert ai.ECB_SERIES["eur_aaa_30y"][1].endswith("SR_30Y")
    assert "jgb" in ai.INGESTERS
