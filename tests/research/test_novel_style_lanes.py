"""Novel-style lanes N1 (FX option-expiry pinning) and N2 (Swiss gold exports): fixtures only."""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.alt_proxies as A  # noqa: E402
import research.novel_style_lanes as N  # noqa: E402
from mt5desk import family_fx_expiry_pin as F  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "novel_styles"
ALT_FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
SEEN = datetime(2026, 7, 20, tzinfo=UTC)


# ------------------------------------------------------------------------------ N1 parser
def test_ppd_parser_keeps_new_fx_option_prints_on_the_four_pairs_only() -> None:
    rows = N.parse_ppd_csv((FIX / "dtcc_ppd_fx_options.csv").read_bytes(), SEEN)
    by = {(r["pair"], r["strike_raw"]): r for r in rows}
    assert sorted(by) == [("AUDUSD", 0.66), ("EURUSD", 1.0849), ("EURUSD", 1.0851),
                          ("USDJPY", 157.5)]          # CANC, no option type and USDCAD dropped
    eur = by[("EURUSD", 1.0851)]
    assert eur["strike"] == 1.085 and eur["notional_capped"] is True
    assert eur["notional_usd"] == pytest.approx(1.0851e9)
    assert by[("USDJPY", 157.5)]["notional_usd"] == 5e8
    assert by[("AUDUSD", 0.66)]["notional_usd"] == 3.3e8
    assert eur["available_time"] == "2026-07-13T09:01:00+00:00"       # its dissemination stamp
    assert eur["pit_basis"] == "dissemination_timestamp"
    assert eur["retrieval_time"] == SEEN.isoformat(timespec="seconds")


def test_a_block_delayed_print_is_public_at_its_dissemination_not_execution_plus_slack() -> None:
    rows = N.parse_ppd_csv((FIX / "dtcc_ppd_fx_options.csv").read_bytes(), SEEN)
    late = next(r for r in rows if r["strike_raw"] == 1.0849)
    executed = datetime.fromisoformat(late["event_time"])
    assert datetime.fromisoformat(late["available_time"]) - executed > timedelta(hours=4)
    assert late["available_time"] == "2026-07-13T14:30:00+00:00"


def test_a_print_without_a_dissemination_timestamp_is_dropped_and_counted() -> None:
    dropped: dict[str, int] = {}
    rows = N.parse_ppd_csv((FIX / "dtcc_ppd_fx_options.csv").read_bytes(), SEEN, dropped)
    assert 1.0875 not in {r["strike_raw"] for r in rows} and dropped == {
        "no_dissemination_time": 1}
    # A file without the column at all: every print is dropped, none execution-stamped.
    text = (FIX / "dtcc_ppd_fx_options.csv").read_text("utf-8").splitlines()
    head = text[0].split(",")
    i = head.index("Dissemination Timestamp")
    stripped = "\n".join(",".join(c for j, c in enumerate(line.split(",")) if j != i)
                         for line in text[:2])
    none: dict[str, int] = {}
    assert N.parse_ppd_csv(stripped.encode(), SEEN, none) == [] and none[
        "no_dissemination_time"] == 1


def test_cut_is_ten_new_york_through_daylight_saving() -> None:
    assert F.cut_utc(date(2026, 7, 15)).hour == 14
    assert F.cut_utc(date(2026, 1, 14)).hour == 15


# ------------------------------------------------------------------------------ N1 family
def _bars(day: date, path: list[float]) -> pd.DataFrame:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(days=2)
    idx = pd.date_range(start, periods=len(path), freq="h", tz="UTC")
    c = np.asarray(path, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.0004, "low": c - 0.0004, "close": c},
                        index=idx)


def _frame(tmp: Path, rows: list[dict]) -> Path:
    d = tmp / "series"
    d.mkdir()
    pd.DataFrame(rows).to_csv(d / f"{F.SERIES_ID}.csv", index=False)
    F._CACHE.clear()
    return d


def _print(avail: datetime, strike: float = 1.0850, usd: float = 2e9) -> dict:
    return {"pair": "EURUSD", "expiry_date": "2026-07-15", "strike": strike,
            "notional_usd": usd, "available_time": avail.isoformat()}


def test_pin_trades_toward_a_large_known_strike_into_the_cut(tmp_path: Path) -> None:
    expiry = date(2026, 7, 15)
    path = [1.0846 + 0.00001 * (i % 3) for i in range(48 + 24)]
    root = _frame(tmp_path, [_print(datetime(2026, 7, 14, tzinfo=UTC))])
    sigs = F.family_fx_expiry_pin(_bars(expiry, path), symbol="EURUSD", mode="pin",
                                  proximity_atr=2.0, series_root=root)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.side == 1 and s.target == pytest.approx(1.085) and s.tag == "fx_expiry_pin.pin"
    assert s.time < pd.Timestamp(F.cut_utc(expiry))
    mirror = F.family_fx_expiry_pin(_bars(expiry, path), -1, symbol="EURUSD", mode="pin",
                                    proximity_atr=2.0, series_root=root)
    assert len(mirror) == 1 and mirror[0].side == -1


def test_a_print_not_yet_public_at_the_decision_is_not_used(tmp_path: Path) -> None:
    expiry = date(2026, 7, 15)
    path = [1.0846] * 72
    late = F.cut_utc(expiry) - timedelta(minutes=30)          # after the pin decision
    root = _frame(tmp_path, [_print(late)])
    assert F.family_fx_expiry_pin(_bars(expiry, path), symbol="EURUSD", mode="pin",
                                  proximity_atr=2.0, series_root=root) == []


def test_release_trades_the_departure_after_the_cut(tmp_path: Path) -> None:
    expiry = date(2026, 7, 15)
    path = [1.0850] * 72
    cut_pos = 48 + F.cut_utc(expiry).hour
    path[cut_pos + 1] = 1.0858                                  # leaves the strike upward
    root = _frame(tmp_path, [_print(datetime(2026, 7, 14, tzinfo=UTC))])
    sigs = F.family_fx_expiry_pin(_bars(expiry, path), symbol="EURUSD", mode="release",
                                  proximity_atr=2.0, series_root=root)
    assert len(sigs) == 1 and sigs[0].side == 1 and sigs[0].tag == "fx_expiry_pin.release"


def test_family_refuses_without_its_frame_or_its_pair(tmp_path: Path) -> None:
    bars = _bars(date(2026, 7, 15), [1.0846] * 72)
    F._CACHE.clear()
    assert F.family_fx_expiry_pin(bars, symbol="EURUSD", series_root=tmp_path) == []
    root = _frame(tmp_path, [_print(datetime(2026, 7, 14, tzinfo=UTC))])
    assert F.family_fx_expiry_pin(bars, symbol="GBPUSD", series_root=root) == []
    assert F.family_fx_expiry_pin(bars, symbol="", series_root=root) == []


def test_family_is_registered_through_the_one_registry() -> None:
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES
    from research.axis_registry import FAMILY_TABLE
    assert ORTHOGONAL_FAMILIES["fx_expiry_pin"] is F.family_fx_expiry_pin
    assert "fx_expiry_pin" in FAMILY_INPUTS
    assert FAMILY_TABLE["fx_expiry_pin"][0] == "gamma_hedging_state"


# ------------------------------------------------------------------------------ the leg
def test_leg_publishes_held_terms_ideas_only_cells_and_unmeasured_novelty(tmp_path: Path) -> None:
    report = tmp_path / "NOVEL_STYLE_LANES.json"
    doc = N.run(fixtures=FIX, report=report, series_dir=tmp_path / "series",
                style_novelty_path=tmp_path / "absent.json", now=SEEN)
    on_disk = json.loads(report.read_text("utf-8"))
    assert on_disk["N1"]["status"] == "IDEAS_ONLY" and doc["N1"]["fetched"] is False
    assert on_disk["terms"]["dtcc_ppd_fx_options"]["verdict"] == "HELD"
    assert "unauthorized use" in on_disk["terms"]["dtcc_ppd_fx_options"]["terms_quote"]
    assert on_disk["N1"]["prints_parsed"] == 4 and on_disk["N1"]["n_cells"] == 32
    assert on_disk["N1"]["prints_dropped_no_dissemination_time"] == 1
    assert on_disk["N2"]["held_substitute"]["substitute"] == "none: UNMEASURED"
    assert all(c["status"] == "IDEAS_ONLY" and not c["donated"] for c in on_disk["N1"]["cells"])
    assert on_disk["N1"]["trials_charged"] == 0 and on_disk["N2"]["trials_charged"] == 0
    assert on_disk["N2"]["terms"] == "to_confirm"
    assert on_disk["N2"]["status"].startswith("BLOCKED_ON_TERMS")
    assert all(c["status"] == "HELD" for c in on_disk["N2"]["cells"])
    nov = on_disk["novelty"]
    assert nov["dominant_style_counts"] == "UNMEASURED"
    assert {v["verdict"] for v in nov["lanes"].values()} == {"UNMEASURED"}
    assert (tmp_path / "series" / "fx_option_expiry_strikes.csv").exists()


def test_novelty_reads_the_book_when_the_artifact_exists(tmp_path: Path) -> None:
    p = tmp_path / "STYLE_NOVELTY.json"
    p.write_text(json.dumps({"dominant_style_counts": {"passive_window": 23,
                                                       "momentum_6bar": 5}}), "utf-8")
    nov = N.novelty(p)
    assert nov["lanes"]["N1"]["verdict"] == "DECLARED_OUTSIDE_DOMINANT"
    assert nov["lanes"]["N1"]["return_novelty"] == "UNMEASURED"
    assert nov["lanes"]["N1"]["dominant_overlap"] == {"momentum_6bar": 5}


def test_fixtures_never_write_into_the_production_strike_frame(tmp_path: Path) -> None:
    with pytest.raises(N.FixturesIntoProduction):
        N.run(fixtures=FIX, style_novelty_path=tmp_path / "x.json", now=SEEN)
    assert N.main(["--once", "--fixtures", str(FIX)]) == 2
    assert N.main(["--once", "--fixtures", str(FIX), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "series" / "fx_option_expiry_strikes.csv").exists()
    assert (tmp_path / N.REPORT.name).exists()


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    report = tmp_path / "r.json"
    N.run(dry_run=True, fixtures=FIX, report=report, series_dir=tmp_path / "s",
          style_novelty_path=tmp_path / "x.json", now=SEEN)
    assert not report.exists() and not (tmp_path / "s").exists()


# ------------------------------------------------------------------------------ N2 (alt_proxies)
def _bazg_series(body: bytes) -> dict[tuple[str, date], float]:
    return {(o.series, o.period): o.value for o in A.parse_bazg_exports(body, A.Ctx())}


def test_bazg_parser_builds_destination_tonnes_and_asia_share() -> None:
    got = _bazg_series((ALT_FIX / "ch_bazg_gold_exports.csv").read_bytes())
    jun, may = date(2026, 6, 30), date(2026, 5, 31)
    assert got[("gold_exp_total_t", jun)] == 110.0
    assert got[("gold_exp_cn_t", jun)] == 30.0 and got[("gold_exp_uk_t", jun)] == 50.0
    assert got[("gold_exp_asia_share", jun)] == pytest.approx(60 / 110, abs=1e-6)
    assert got[("silver_exp_total_t", jun)] == 500.0 and got[("silver_exp_in_t", jun)] == 400.0
    assert got[("gold_exp_asia_share", may)] == pytest.approx(0.1)
    assert not any(k[0].startswith("oil") for k in got)        # 2709 is not a metal


def test_bazg_parser_reads_the_zipped_bulk_file() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("OGD_EXP_TN_M.csv", (ALT_FIX / "ch_bazg_gold_exports.csv").read_bytes())
    assert _bazg_series(buf.getvalue()) == _bazg_series(
        (ALT_FIX / "ch_bazg_gold_exports.csv").read_bytes())


def test_bazg_row_is_held_on_terms_and_never_fetched(tmp_path: Path) -> None:
    src = A.BY_ID["ch_bazg_gold_exports"]
    assert src.terms == "to_confirm" and A.status_of(src).startswith("BLOCKED_ON_TERMS")
    assert "Kommerzielle Nutzung" in A.TERMS_EVIDENCE["ch_bazg_gold_exports"]["terms_quote"]

    def boom(url: str) -> tuple[bytes, str]:
        raise AssertionError("a HELD source was fetched")

    paths = A.Paths(tmp_path)
    paths.obs_dir.mkdir(parents=True, exist_ok=True)
    rec = A.collect(paths, src, {}, SEEN, fetch=True, fixtures=None, deadline=1e18, getter=boom)
    assert rec["requests"] == 0


def test_bazg_series_reach_the_lake_in_the_conditioner_envelope(tmp_path: Path) -> None:
    from dataclasses import replace
    src = replace(A.BY_ID["ch_bazg_gold_exports"], terms="confirmed")
    store: dict = {}
    A.merge_vintages(store, src, A.parse_bazg_exports(
        (ALT_FIX / "ch_bazg_gold_exports.csv").read_bytes(), A.Ctx()), SEEN)
    pts = A.build_points(src, store)
    row = pts["gold_exp_asia_share"][-1]
    assert row["available_time"] >= "2026-07-25"                 # release rule, never early
    paths = A.Paths(tmp_path)
    written = A.write_lake_series(paths, src, pts)
    assert "alt_ch_bazg_gold_exports__gold_exp_asia_share.csv" in written
