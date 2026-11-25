"""E8 all-fire headroom: the arithmetic, the overlap, the stand-down verdict, UNMEASURED inputs
never reading as 0, and that the report imports nothing from the money path."""
from __future__ import annotations

import ast
import json
import re
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import e8_headroom as eh  # noqa: E402

KW = {"daily": 0.025, "stand_down": 0.0075, "max_concurrent": 3, "cadence_s": 300.0}
THREE = {"asia": 0.0075, "london_am": 0.0075, "afternoon": 0.0075}


def test_three_stops_at_three_quarters_with_measured_slip_is_red() -> None:
    s = eh.scenario("x", THREE, "t", 0.202, **KW)
    assert s["stop_risk_all_fire"] == pytest.approx(0.0225)
    assert s["concurrent_slip_adjusted"] == pytest.approx(0.0225 * 1.202)
    assert s["worst_case"] > 0.025 and s["flag"] == "RED"
    assert s["stand_down_prevents_breach"] == "NOT_GUARANTEED"


def test_without_slip_the_same_book_stays_inside_and_needs_no_stand_down() -> None:
    s = eh.scenario("x", THREE, "t", 0.0, **KW)
    assert s["worst_case"] == pytest.approx(0.0225) and s["flag"] == "GREEN"
    assert s["stand_down_prevents_breach"] == "NOT_NEEDED"


def test_sequential_trips_after_one_loss_and_counts_one_resting_leak() -> None:
    s = eh.scenario("x", THREE, "t", 0.0, **KW)
    assert s["stand_down_trips_after_losses"] == 1
    assert s["sequential_with_stand_down"] == pytest.approx(0.015)


def test_exactly_at_the_limit_is_not_red() -> None:
    s = eh.scenario("x", {"a": 0.0125, "b": 0.0125}, "t", 0.0, **{**KW, "max_concurrent": 2})
    assert s["worst_case"] == pytest.approx(0.025) and s["flag"] == "GREEN"


def test_unmeasured_slip_is_named_not_zero_in_the_row() -> None:
    s = eh.scenario("x", THREE, "t", None, **KW)
    assert s["slip_r_used"] == "UNMEASURED"
    # Audit must-fix: a missing slip is never computed as 0 -- no worst case, flag UNMEASURED.
    assert s["worst_case"] is None and s["flag"] == "UNMEASURED"
    assert s["headroom_to_daily_pct_of_day_start"] is None


def test_overall_flag_is_never_green_while_a_counted_scenario_is_unmeasured() -> None:
    green = eh.scenario("g", THREE, "t", 0.0, **KW)
    unm = eh.scenario("u", THREE, "t", None, **KW)
    red = eh.scenario("r", THREE, "t", 0.202, **KW)
    assert eh.overall_flag([green]) == "GREEN"
    assert eh.overall_flag([green, unm]) == "UNMEASURED"
    assert eh.overall_flag([green, unm, red]) == "RED"
    assert eh.overall_flag([]) == "UNMEASURED"
    # A reference-only row (ARTIFACT_PROXY) never moves the flag, even when it breaches.
    art = {**red, "flag": eh.ARTIFACT_PROXY, "counted": False}
    assert eh.overall_flag([green, art]) == "GREEN"


def test_build_without_markout_is_unmeasured_not_green(tmp_path: Path) -> None:
    # The audit probe: guard, gold and decision_core present, no markout.json.
    doc = eh.build(_fake_desk(tmp_path), now=datetime(2026, 10, 20, 17, tzinfo=UTC))
    assert doc["flag"] == "UNMEASURED"
    assert "stated_live_e8_slip" in doc["unmeasured_scenarios"]


def test_overlap_of_the_live_schedule_is_three_from_the_afternoon_signal() -> None:
    ov = eh.overlap([("asia", 7.0), ("london_am", 13.0), ("afternoon", 17.0)], 19.5)
    assert ov["max_concurrent"] == 3 and ov["max_concurrent_from_hour"] == 17.0
    assert [r["fill_until"] for r in ov["windows"]] == [13.0, 17.0, 19.5]


def test_concurrency_is_bounded_by_the_schedule() -> None:
    s = eh.scenario("x", THREE, "t", 0.0, **{**KW, "max_concurrent": 2})
    assert s["stop_risk_all_fire"] == pytest.approx(0.015)


def test_slip_reads_fusion_as_a_labelled_proxy_and_e8_as_unmeasured() -> None:
    out = eh.slip_r({"usable": True, "mean_slip_r": -0.2, "n_matched": 9})
    assert out["proxy"]["value"] == pytest.approx(0.2)
    assert out["proxy"]["status"] == "ARTIFACT_PROXY"
    assert "markout.py:344-349" in out["proxy"]["why"]
    assert out["e8"]["status"] == "UNMEASURED" and out["e8"]["value"] is None
    assert eh.slip_r(None)["proxy"]["status"] == "UNMEASURED"


def test_money_headroom_is_unmeasured_without_box_state() -> None:
    out = eh.money_headroom({"equity": None, "day_start": None}, 0.027, 0.025, 90_000.0)
    assert out["status"] == "UNMEASURED" and out["room_to_daily_floor_frac"] == "UNMEASURED"


def test_money_headroom_with_box_state() -> None:
    out = eh.money_headroom({"equity": 100_000.0, "day_start": 100_000.0}, 0.027, 0.025,
                            90_000.0)
    # 2,500 / -200 / 10,000 of a 100,000 day start, published as fractions of it
    assert out["room_to_daily_floor_frac"] == pytest.approx(0.025)
    assert out["after_worst_case_daily_frac"] == pytest.approx(-0.002)
    assert out["room_to_static_floor_frac"] == pytest.approx(0.10)
    assert "100000" not in json.dumps(out) and "equity" not in out


def test_kelly_follows_the_live_lane_shape_and_age() -> None:
    now = datetime(2026, 10, 20, 17, tzinfo=UTC)
    doc = {"generated_at": now.isoformat(),
           "e8": {"status": "OK", "windows": {"london_am": {"risk_frac": 0.0075}}}}
    assert eh.kelly_e8_windows(doc, now, 7200)[0] == {"london_am": 0.0075}
    old = {**doc, "generated_at": (now - timedelta(hours=3)).isoformat()}
    assert eh.kelly_e8_windows(old, now, 7200)[0] is None
    assert eh.kelly_e8_windows(None, now, 7200)[1].startswith("UNMEASURED")
    assert eh.kelly_e8_windows(doc, now, None)[1].startswith("UNMEASURED")


def test_cert_book_voids_whole_on_a_bad_value() -> None:
    assert eh.cert_e8_windows({"enabled": True, "e8": {"gold_asia": 0.01}}) == {"asia": 0.01}
    assert eh.cert_e8_windows({"enabled": True, "e8": {"gold_asia": "x"}}) is None
    assert eh.cert_e8_windows({"enabled": False, "e8": {"gold_asia": 0.01}}) is None


def _fake_desk(tmp: Path) -> Path:
    for rel in ("prop/e8_guard.py", "prop/e8_gold.py", "mt5desk/decision_core.py",
                "ops/box_tasks.manifest", "data/CERT_BOOK_LIVE.json",
                "mt5desk/kelly_sizing.py", "mt5desk/sizing.py"):
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DESK / rel, tmp / rel)
    return tmp


def test_build_on_a_copy_of_the_desk_keeps_the_markout_artifact_out_of_the_flag(
        tmp_path: Path) -> None:
    desk = _fake_desk(tmp_path)
    (desk / "reports").mkdir()
    (desk / "reports" / "markout.json").write_text(json.dumps(
        {"usable": True, "mean_slip_r": -0.202, "n_matched": 229}), encoding="utf-8")
    doc = eh.build(desk, now=datetime(2026, 10, 20, 17, tzinfo=UTC))
    # The -0.202R row would breach (2.705%), but it is a unit artifact: reference only.
    art = next(s for s in doc["scenarios"]
               if s["scenario"] == "stated_live_fusion_artifact_proxy")
    assert art["flag"] == "ARTIFACT_PROXY" and art["counted"] is False
    assert art["worst_case"] == pytest.approx(0.0225 * 1.202, abs=1e-6)
    # E8's own slip is UNMEASURED, so the flag is UNMEASURED and the worst case counts only the
    # measured (zero-slip) scenarios.
    assert doc["flag"] == "UNMEASURED" and doc["report_only"] is True
    assert doc["worst_case"]["pct"] == pytest.approx(2.25)
    assert doc["worst_case"]["over_measured_scenarios_only"] is True
    assert doc["risk_inputs"]["kelly_max_age_s"] == 7200
    assert doc["money_headroom"]["status"] == "UNMEASURED"
    assert doc["schedule"]["max_concurrent"] == 3
    assert doc["guard"]["cadence_s"] == 300.0


def test_build_with_box_state_measures_money(tmp_path: Path) -> None:
    desk = _fake_desk(tmp_path)
    (desk / "reports").mkdir()
    (desk / "data" / "e8_guard_state.json").write_text(json.dumps(
        {"day": "2026-10-20", "day_start": 101_000.0, "peak_equity": 101_000.0}),
        encoding="utf-8")
    (desk / "reports" / "E8_GUARD.json").write_text(json.dumps(
        {"decision": {"equity": 100_500.0, "day_start": 101_000.0}}), encoding="utf-8")
    doc = eh.build(desk, now=datetime(2026, 10, 20, 17, tzinfo=UTC), stated_risk=None)
    m = doc["money_headroom"]
    assert m["status"] == "MEASURED"
    # published to 6 decimal places
    assert m["room_to_daily_floor_frac"] == pytest.approx(
        (100_500.0 - 101_000.0 * 0.975) / 101_000.0, abs=1e-6)
    assert m["room_to_static_floor_frac"] == pytest.approx(10_500.0 / 101_000.0, abs=1e-6)
    blob = json.dumps(doc)
    assert "100500" not in blob and "101000" not in blob and "90000" not in blob


def test_unreadable_risk_frac_never_sizes_a_window_and_is_not_the_half_percent(
        tmp_path: Path) -> None:
    # e8_gold.run (since the r6/r7 cert-book whitelist) never reaches RISK_FRAC: an enabled book
    # sizes unnamed windows at 0 and a void book sizes every window at 0. So an unreadable
    # RISK_FRAC is REPORTED UNMEASURED but cannot make the resolved book unknown -- and the
    # half percent never appears as a window's risk.
    desk = _fake_desk(tmp_path)
    (desk / "prop" / "e8_gold.py").write_text("RISK_FRAC = compute()\n", encoding="utf-8")
    doc = eh.build(desk, now=datetime(2026, 10, 20, 17, tzinfo=UTC), stated_risk=None)
    assert doc["risk_inputs"]["risk_frac_fallback"] == "UNMEASURED"
    rows = [s for s in doc["scenarios"] if s["scenario"] == "repo_resolved_no_slip"]
    assert rows and rows[0]["worst_case"] is not None
    assert 0.005 not in rows[0]["window_risk"].values()
    src = json.loads(rows[0]["risk_source"])
    assert set(src.values()) <= {"pinned_zero", "cert_book", "cert_book_absent",
                                 "cert_book_void", "cert_book capped at E8_CERT_CEILING"}


def test_void_cert_book_sizes_every_window_zero_never_risk_frac(tmp_path: Path) -> None:
    desk = _fake_desk(tmp_path)
    (desk / "data" / "CERT_BOOK_LIVE.json").write_text("{torn", encoding="utf-8")
    doc = eh.build(desk, now=datetime(2026, 10, 20, 17, tzinfo=UTC), stated_risk=None)
    row = next(s for s in doc["scenarios"] if s["scenario"] == "repo_resolved_no_slip")
    assert set(row["window_risk"].values()) == {0.0}
    assert row["worst_case"] == 0.0


def test_unreadable_kelly_age_with_a_solve_present_cannot_size_e8(tmp_path: Path) -> None:
    # The solve's age is reported UNMEASURED, but the live lane overrides the solve on every
    # path, so the resolved window risk does not depend on it.
    desk = _fake_desk(tmp_path)
    (desk / "mt5desk" / "kelly_sizing.py").write_text("X = 1\n", encoding="utf-8")
    (desk / "reports").mkdir()
    (desk / "reports" / "KELLY_SURVIVAL.json").write_text(json.dumps(
        {"generated_at": "2026-10-20T16:00:00+00:00",
         "e8": {"status": "OK", "windows": {"london_am": {"risk_frac": 0.0123}}}}),
        encoding="utf-8")
    doc = eh.build(desk, now=datetime(2026, 10, 20, 17, tzinfo=UTC), stated_risk=None)
    assert doc["risk_inputs"]["kelly_max_age_s"] == "UNMEASURED"
    row = next(s for s in doc["scenarios"] if s["scenario"] == "repo_resolved_no_slip")
    assert row["worst_case"] is not None and 0.0123 not in row["window_risk"].values()


@pytest.mark.parametrize("breaks", ["ceiling", "pins", "range"])
def test_an_unresolvable_live_input_makes_the_resolved_book_unmeasured(
        tmp_path: Path, breaks: str) -> None:
    # What the live lane DOES read -- the code ceiling, the principal's pinned zeros and the cert
    # book's range -- is the honest UNMEASURED: without it the live window risk is unknown.
    desk = _fake_desk(tmp_path)
    core = desk / "mt5desk" / "decision_core.py"
    if breaks == "ceiling":
        core.write_text(core.read_text(encoding="utf-8").replace(
            "E8_CERT_CEILING = 0.006", "E8_CERT_CEILING = ceiling()"), encoding="utf-8")
    elif breaks == "pins":
        core.write_text(core.read_text(encoding="utf-8").replace(
            "PRINCIPAL_ZERO: dict[str, frozenset[str]] = {",
            "PRINCIPAL_ZERO: dict[str, frozenset[str]] = load_pins() or {"), encoding="utf-8")
    else:
        (desk / "mt5desk" / "sizing.py").write_text("MAX_RISK_FRAC = cap()\n",
                                                    encoding="utf-8")
    doc = eh.build(desk, now=datetime(2026, 10, 20, 17, tzinfo=UTC), stated_risk=None)
    rows = [s for s in doc["scenarios"] if s["scenario"].startswith("repo_resolved")]
    assert rows and all(s["worst_case"] is None for s in rows)
    assert doc["flag"] == "UNMEASURED"


def test_principal_zero_resolves_from_source_by_ast() -> None:
    zeros = eh.literal_sets(DESK / "mt5desk" / "decision_core.py", "PRINCIPAL_ZERO")
    assert zeros is not None
    from mt5desk.decision_core import PRINCIPAL_ZERO
    assert zeros == {k: frozenset(v) for k, v in PRINCIPAL_ZERO.items()}


def test_resolution_matches_the_live_lane_precedence() -> None:
    names = ["asia", "london_am", "afternoon"]
    book = {"enabled": True, "e8": {"gold_asia": 0.009, "gold_london_am": 0.004}}
    risk, src, why = eh.resolve_live_windows(names, book, pinned=frozenset({"gold_london_am"}),
                                             ceiling=0.006, max_frac=0.10)
    assert why == "" and risk == {"asia": 0.006, "london_am": 0.0, "afternoon": 0.0}
    assert src == {"asia": "cert_book capped at E8_CERT_CEILING", "london_am": "pinned_zero",
                   "afternoon": "cert_book_absent"}


@pytest.mark.parametrize("equity,day_start", [(0.0, 100_000.0), (100_000.0, 0), (-1.0, 5.0)])
def test_zero_or_negative_equity_is_unmeasured(equity: float, day_start: float) -> None:
    out = eh.money_headroom({"equity": equity, "day_start": day_start}, 0.02, 0.025, 90_000.0)
    assert out["status"] == "UNMEASURED"


def test_missing_constants_are_unmeasured_not_green(tmp_path: Path) -> None:
    doc = eh.build(tmp_path, now=datetime(2026, 10, 20, tzinfo=UTC))
    assert doc["flag"] == "UNMEASURED"


def test_main_writes_the_artifact(tmp_path: Path) -> None:
    out = tmp_path / "E8_HEADROOM.json"
    assert eh.main(["--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["report_only"] is True


def test_the_report_imports_nothing_from_the_money_path() -> None:
    tree = ast.parse((DESK / "research" / "e8_headroom.py").read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"__future__", "argparse", "ast", "json", "re", "sys", "datetime",
                    "pathlib", "typing"}


#: A broker deal, ticket, order or login is a 7+ digit run. Nothing published may carry one.
_ID_RUN = re.compile(r"\d{7,}")


def _id_shaped(obj: object, at: str = "$") -> list[str]:
    """Every string (key or value) holding a 7+ digit run, and every integer of 7+ digits.
    Floats are skipped: their decimals are not identifiers."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _ID_RUN.search(str(k)):
                out.append(f"{at} key {k}")
            out += _id_shaped(v, f"{at}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _id_shaped(v, f"{at}[{i}]")
    elif isinstance(obj, str):
        if _ID_RUN.search(obj):
            out.append(f"{at}: {obj[:80]}")
    elif isinstance(obj, int) and not isinstance(obj, bool) and abs(obj) >= 1_000_000:
        out.append(f"{at}: int {obj}")
    return out


def test_the_e8_headroom_report_text_has_no_seven_digit_run(tmp_path):
    doc = eh.build(_fake_desk(tmp_path), now=datetime(2026, 10, 20, 17, tzinfo=UTC))
    assert _id_shaped(doc) == []
    assert not _ID_RUN.search(eh.ARTIFACT_WHY)


def test_the_live_tree_e8_headroom_report_has_no_seven_digit_run():
    assert _id_shaped(eh.build(now=datetime(2026, 10, 20, 17, tzinfo=UTC))) == []
