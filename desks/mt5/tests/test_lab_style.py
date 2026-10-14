"""LAB STYLE SCREEN: a lab cell that re-buys a style the book owns is held, never dropped.

  * saturation is read from STYLE_NOVELTY.json's dominant_style_counts at SATURATION_SHARE;
  * a KNOWN_STYLE cell in a saturated style is held; NOVEL, unsaturated and UNMEASURED cells are
    donated, each stamped with its reading;
  * a held cell is released once its style is no longer saturated, and an absent report holds
    nothing;
  * the verdict loop credits NOVEL certified k_eff, and the lab ranking draws on it.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lab_style as ls  # noqa: E402
import llm_lab_roles as roles  # noqa: E402

COUNTS = {"passive_window": 20, "range_breakout_12bar": 8, "trend_20d": 1}


def _report(path: Path, counts: dict[str, int], n: int = 43) -> Path:
    path.write_text(json.dumps({"dominant_style_counts": counts, "n_measured": n,
                                "novel_threshold": 0.5}))
    return path


#: A stand-in for style_novelty: the row's params say what its projection reads.
def _fake_sn() -> Any:
    return SimpleNamespace(
        style_matrix=lambda close, index, sigs, high=None, low=None: (sigs, None),
        project=lambda y, X: y)


@pytest.fixture()
def wired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import pandas as pd
    idx = pd.date_range("2024-01-01", periods=24 * 400, freq="h", tz="UTC")
    monkeypatch.setattr(ls, "_bars", lambda sym, d: pd.DataFrame({"close": 1.0}, index=idx))
    monkeypatch.setattr(ls, "_family", lambda name: (lambda df, **p: dict(p["reads"]))
                        if name == "exogenous_conditioner" else None)
    monkeypatch.setattr(ls, "BARS_DIR", tmp_path / "bars")
    monkeypatch.setattr(ls, "CALENDAR", tmp_path / "calendar.json")
    monkeypatch.setattr(ls, "HELD", tmp_path / "held_default.json")
    return tmp_path


def _row(cid: str, nov: float | None, dom: str | None) -> dict[str, Any]:
    reads = ({"status": "MEASURED", "novelty_return": nov, "dominant_style": dom, "n": 80}
             if nov is not None else {"status": "UNMEASURED", "why": "short"})
    return {"cell_id": cid, "family": "exogenous_conditioner", "symbol": "USDCNH",
            "params": {"reads": reads}, "lab": "cb_tone"}


def test_saturation_is_a_share_of_the_measured_certificates(tmp_path: Path) -> None:
    sat = ls.saturation(_report(tmp_path / "s.json", COUNTS))
    assert sat["saturated"] == ["passive_window", "range_breakout_12bar"]
    assert ls.saturation(tmp_path / "absent.json")["status"] == "UNMEASURED"


def test_known_styles_the_book_owns_are_held_and_everything_else_donates(wired: Path) -> None:
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    rows = [_row("passive", 0.1, "passive_window"), _row("novel", 0.8, "passive_window"),
            _row("trend", 0.2, "trend_20d"), _row("unmeasured", None, None),
            {"cell_id": "nofam", "family": "nope", "symbol": "X", "params": {}}]
    out, summary = ls.screen(rows, report=rep, held_path=held, sn=_fake_sn())
    by = {r["cell_id"]: r["style_screen"]["verdict"] for r in out}
    assert by == {"novel": "NOVEL", "trend": "KNOWN_STYLE", "unmeasured": "UNMEASURED",
                  "nofam": "UNMEASURED"}
    assert summary["held"] == 1 and list(json.loads(held.read_text())) == ["passive"]
    # Nothing is lost: four donated, one held, five in.
    assert len(out) + summary["held_total"] == len(rows)


def test_a_held_cell_is_released_when_its_style_stops_being_saturated(wired: Path) -> None:
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    ls.screen([_row("passive", 0.1, "passive_window")], report=rep, held_path=held,
              sn=_fake_sn())
    assert ls.release(report=rep, held_path=held) == ({}, 1)
    _report(rep, {"trend_20d": 30, "passive_window": 2})
    freed, still = ls.release(report=rep, held_path=held)
    assert [r["cell_id"] for r in freed.values()] == ["passive"] and still == 0
    sc = next(iter(freed.values()))["style_screen"]
    assert sc["release_reason"] == "STYLE_NO_LONGER_SATURATED"
    # Release never forgets on its own: the caller writes the donation, then forgets.
    assert list(json.loads(held.read_text())) == ["passive"]
    ls.forget(freed, held_path=held)
    assert json.loads(held.read_text()) == {}


def test_a_hold_is_a_deferral_that_expires(wired: Path) -> None:
    """Audit must-fix 2 on #385: saturation alone may never clear, so a hold has a maximum age."""
    from datetime import UTC, datetime, timedelta
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    ls.screen([_row("passive", 0.1, "passive_window")], report=rep, held_path=held,
              sn=_fake_sn())
    later = datetime.now(UTC) + timedelta(days=ls.MAX_HOLD_DAYS + 1)
    freed, still = ls.release(report=rep, held_path=held, now=later)
    sc = freed["passive"]["style_screen"]
    assert still == 0 and sc["release_reason"] == "HELD_EXPIRED" and sc["held_days"] > 14


def test_two_held_rows_never_share_a_key(wired: Path) -> None:
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    a, b = _row("", 0.1, "passive_window"), _row("", 0.2, "passive_window")
    ls.screen([a, b], report=rep, held_path=held, sn=_fake_sn())
    assert len(json.loads(held.read_text())) == 2


def test_the_hold_publishes_its_missed_growth_line(wired: Path) -> None:
    rep, held, out = _report(wired / "s.json", COUNTS), wired / "held.json", wired / "h.json"
    ls.screen([_row("passive", 0.1, "passive_window")], report=rep, held_path=held,
              sn=_fake_sn())
    doc = ls.publish_holds(held_path=held, out=out)
    assert doc["held"] == doc["trials_deferred"] == 1 and doc["verdict"] == "UNMEASURED"
    assert doc["oldest_hold_days"] is not None and json.loads(out.read_text())["held"] == 1
    doc = ls.publish_holds(credit={"style_hold_cost": {"judged": 2, "certified": 1,
                                                       "keff_days": 3.5}},
                           held_path=held, out=out)
    assert doc["verdict"] == "COSTS_GROWTH" and doc["keff_days_deferred"] == 3.5


def test_the_screen_never_reads_the_lockbox(wired: Path) -> None:
    import pandas as pd
    idx = pd.date_range("2024-01-01", periods=24 * 400, freq="h", tz="UTC")
    df = pd.DataFrame({"close": 1.0}, index=idx)
    cut = ls._before_lockbox(df, wired / "no_bars")
    from research.gate_policy import LOCKBOX_FRAC
    assert 0 < len(cut) < len(df) and cut.index[-1] < idx[int(len(idx) * (1 - LOCKBOX_FRAC))]


def test_no_style_report_holds_nothing(wired: Path) -> None:
    out, summary = ls.screen([_row("passive", 0.1, "passive_window")],
                             report=wired / "absent.json", held_path=wired / "h.json",
                             sn=_fake_sn())
    assert len(out) == 1 and summary["held"] == 0 and not (wired / "h.json").exists()


def test_without_style_novelty_every_cell_is_unmeasured_and_donated(
        wired: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "style_novelty", None)
    out, _ = ls.screen([_row("passive", 0.1, "passive_window")],
                       report=_report(wired / "s.json", COUNTS), held_path=wired / "h.json")
    assert out[0]["style_screen"]["verdict"] == "UNMEASURED"
    assert "#377" in out[0]["style_screen"]["why"]


def test_a_spent_budget_never_holds_a_row(wired: Path) -> None:
    out, summary = ls.screen([_row("passive", 0.1, "passive_window")], deadline=0.0,
                             report=_report(wired / "s.json", COUNTS),
                             held_path=wired / "h.json", sn=_fake_sn())
    assert len(out) == 1 and summary["not_reached"] == 1 and summary["held"] == 0


def test_the_verdict_loop_credits_novel_certified_keff(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    donate = tmp_path / "donate"
    donate.mkdir()
    rows = []
    for lab, v in (("N", "NOVEL"), ("S", "KNOWN_STYLE"), ("U", None)):
        for i in range(4):
            r: dict[str, Any] = {"cell_id": f"{lab}{i}", "lab": lab, "model": "m",
                                 "symbol": "USDCNH", "family": "exogenous_conditioner"}
            if v:
                r["style_screen"] = {"verdict": v}
            rows.append(r)
    (donate / "discoveries_x.json").write_text(json.dumps({"discoveries": rows}))
    ledger = tmp_path / "verdicts.jsonl"
    ledger.write_text("\n".join(json.dumps({"cell": r["cell_id"], "passed": True})
                                for r in rows) + "\n")
    monkeypatch.setattr(roles, "_keff", lambda cells: ({c["cid"]: 1.0 for c in cells}, "test"))
    doc = roles.verdict_loop(ledger, donate, [(x, "m") for x in "NSU" for _ in range(20)],
                             tmp_path / "credit.json")
    labs = doc["labs"]
    assert [labs[x]["keff"] for x in "NSU"] == [4.0, 4.0, 4.0]
    # Novelty is a bonus: a known-style certificate keeps its k_eff; an unmeasured one is
    # credited at its lab's measured novel share, which is 0 for a lab with nothing measured.
    assert [labs[x]["novel_keff"] for x in "NSU"] == [8.0, 4.0, 4.0]
    assert labs["S"]["styles"] == {"KNOWN_STYLE": 4}
    rng = random.Random(5)  # noqa: S311 - not crypto
    firsts = [roles.thompson(labs, ["S", "N"], rng)[0] for _ in range(300)]
    assert firsts.count("N") > 200, "a lab of new styles outranks one re-buying owned styles"


def test_a_held_then_certified_cell_is_charged_to_the_hold(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    donate = tmp_path / "donate"
    donate.mkdir()
    row = {"cell_id": "h1", "lab": "L", "model": "m", "symbol": "USDCNH",
           "family": "exogenous_conditioner",
           "style_screen": {"verdict": "KNOWN_STYLE", "held_days": 5.0}}
    (donate / "discoveries_r.json").write_text(json.dumps({"discoveries": [row]}))
    ledger = tmp_path / "v.jsonl"
    ledger.write_text(json.dumps({"cell": "h1", "passed": True}) + "\n")
    monkeypatch.setattr(roles, "_keff", lambda cells: ({c["cid"]: 0.4 for c in cells}, "t"))
    doc = roles.verdict_loop(ledger, donate, [], tmp_path / "c.json")
    assert doc["style_hold_cost"] == {"judged": 1, "certified": 1, "keff_days": 2.0,
                                      "certified_days_unmeasured": 0}


def test_the_inventors_are_told_which_styles_the_book_owns(tmp_path: Path) -> None:
    line = ls.prompt_line(_report(tmp_path / "s.json", COUNTS))
    assert "passive_window (20)" in line and "trend_20d" not in line
    assert "UNMEASURED" in ls.prompt_line(tmp_path / "absent.json")


def _monkey_ls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ls, "HELD", tmp_path / "held_default.json")
    monkeypatch.setattr(ls, "CALENDAR", tmp_path / "calendar.json")


def test_a_late_chart_never_reads_past_the_campaign_cut(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """Should-fix B on #385: the gauntlet cuts every cell at ONE campaign-wide date taken over
    the union of every chart's days; a chart that starts late has its own tail cut LATER than
    that, so a per-chart tail would read days the campaign lockbox judges."""
    import pandas as pd
    from research.gate_policy import lockbox_cut
    _monkey_ls(monkeypatch, tmp_path)
    bars = tmp_path / "bars"
    bars.mkdir()
    long_idx = pd.date_range("2018-01-01", "2025-12-31", freq="D", tz="UTC")
    short_idx = pd.date_range("2024-01-01", "2025-12-31", freq="h", tz="UTC")
    pd.DataFrame({"close": 1.0}, index=long_idx).to_parquet(bars / "OLD_H1.parquet")
    pd.DataFrame({"close": 1.0}, index=short_idx).to_parquet(bars / "NEW_H1.parquet")
    camp = lockbox_cut([pd.Series(0.0, index=long_idx.normalize())])
    own = lockbox_cut([pd.Series(0.0, index=short_idx.normalize().unique())])
    assert own > camp
    dev = ls._before_lockbox(pd.DataFrame({"close": 1.0}, index=short_idx), bars)
    assert len(dev) > 0 and dev.index[-1] < camp
    # The calendar is cached for the day, so the next cell reads no parquet.
    assert json.loads((tmp_path / "calendar.json").read_text())["charts"] == 2


def test_a_future_or_unreadable_stamp_expires_and_never_writes_infinity(wired: Path) -> None:
    """Should-fixes C and D on #385."""
    from datetime import UTC, datetime, timedelta
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    ls.screen([_row("future", 0.1, "passive_window"), _row("bad", 0.2, "passive_window")],
              report=rep, held_path=held, sn=_fake_sn())
    store = json.loads(held.read_text())
    store["future"]["style_screen"]["held_at"] = (datetime.now(UTC)
                                                  + timedelta(days=30)).isoformat()
    store["bad"]["style_screen"]["held_at"] = "not a time"
    store["bad"]["style_screen"]["at"] = "not a time"
    held.write_text(json.dumps(store))
    out = wired / "h.json"
    doc = ls.publish_holds(held_path=held, out=out)
    assert doc["unreadable_hold_stamps"] == 2 and doc["oldest_hold_days"] is None
    freed, still = ls.release(report=rep, held_path=held)
    assert still == 0 and set(freed) == {"future", "bad"}
    for r in freed.values():
        sc = r["style_screen"]
        assert sc["release_reason"] == "HELD_EXPIRED" and sc["held_days"] is None
        assert sc["held_days_status"] == "UNMEASURED"
    json.loads(json.dumps(freed), parse_constant=lambda c: pytest.fail(f"wrote {c}"))
    assert "Infinity" not in out.read_text()


def test_re_screening_a_held_cell_keeps_one_key_and_its_clock(wired: Path) -> None:
    """Should-fix E on #385: the stamp changes on every screen; the key and hold age do not."""
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    ls.screen([_row("p", 0.1, "passive_window")], report=rep, held_path=held, sn=_fake_sn())
    first = json.loads(held.read_text())["p"]["style_screen"]["held_at"]
    store = json.loads(held.read_text())
    store["p"]["style_screen"]["held_at"] = store["p"]["style_screen"]["at"] = \
        "2026-01-01T00:00:00+00:00"
    held.write_text(json.dumps(store))
    ls.screen([_row("p", 0.1, "passive_window")], report=rep, held_path=held, sn=_fake_sn())
    after = json.loads(held.read_text())
    assert list(after) == ["p"] and first != after["p"]["style_screen"]["held_at"]
    assert after["p"]["style_screen"]["held_at"] == "2026-01-01T00:00:00+00:00"
    # A DIFFERENT row under the same id still gets a key of its own.
    other = _row("p", 0.1, "passive_window")
    other["params"]["extra"] = 1
    ls.screen([other], report=rep, held_path=held, sn=_fake_sn())
    assert len(json.loads(held.read_text())) == 2


def test_held_rows_count_in_the_labs_novel_share(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """Should-fix F on #385: a lab with 1 NOVEL donated and 3 KNOWN held is 25% novel, not 100%."""
    _monkey_ls(monkeypatch, tmp_path)
    donate = tmp_path / "donate"
    donate.mkdir()
    rows = [{"cell_id": "n", "lab": "L", "style_screen": {"verdict": "NOVEL"}},
            {"cell_id": "u", "lab": "L"}]
    (donate / "discoveries_x.json").write_text(json.dumps({"discoveries": rows}))
    (tmp_path / "held_default.json").write_text(json.dumps({
        f"k{i}": {"cell_id": f"k{i}", "lab": "L", "style_screen": {"verdict": "KNOWN_STYLE"}}
        for i in range(3)}))
    owners = roles._donations(donate)
    assert owners["u"]["novel_weight"] == pytest.approx(0.25)


def test_a_certified_cell_with_an_unknown_wait_is_counted_never_priced(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _monkey_ls(monkeypatch, tmp_path)
    donate = tmp_path / "donate"
    donate.mkdir()
    row = {"cell_id": "h1", "lab": "L", "model": "m", "symbol": "USDCNH",
           "family": "exogenous_conditioner",
           "style_screen": {"verdict": "KNOWN_STYLE", "held_days": None, "released": "x",
                            "held_days_status": "UNMEASURED"}}
    (donate / "discoveries_r.json").write_text(json.dumps({"discoveries": [row]}))
    ledger = tmp_path / "v.jsonl"
    ledger.write_text(json.dumps({"cell": "h1", "passed": True}) + "\n")
    monkeypatch.setattr(roles, "_keff", lambda cells: ({c["cid"]: 0.4 for c in cells}, "t"))
    doc = roles.verdict_loop(ledger, donate, [], tmp_path / "c.json")
    assert doc["style_hold_cost"] == {"judged": 1, "certified": 1, "keff_days": 0.0,
                                      "certified_days_unmeasured": 1}


def test_the_hold_is_measured_on_the_missed_growth_ledger(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """Should-fix A on #385 (the measure half; the rail row goes through the sealed pass)."""
    import missed_growth as mg
    monkeypatch.setattr(mg, "BASE", tmp_path)
    assert mg.measure_lab_style_hold(None, {}, {})["verdict"] == "UNMEASURED"
    rep = tmp_path / "reports"
    rep.mkdir()
    (rep / "LAB_STYLE_HOLDS.json").write_text(json.dumps({"held": 0}))
    quiet = mg.measure_lab_style_hold(None, {}, {})
    assert quiet["verdict"] == "NOT_BINDING" and quiet["sample"] is True
    (rep / "LAB_STYLE_HOLDS.json").write_text(json.dumps(
        {"held": 3, "released_this_pass": 1, "held_then_judged": 2, "held_then_certified": 1,
         "keff_days_deferred": 3.5, "oldest_hold_days": 4.0}))
    busy = mg.measure_lab_style_hold(None, {}, {})
    assert busy["verdict"] == "UNMEASURED" and busy["keff_days_deferred"] == 3.5
    assert "sample" not in busy and "measure_lab_style_hold" in mg.MEASURES


def test_the_hold_key_ignores_the_moving_reading(wired: Path) -> None:
    """Audit must-fix 2 on #392: n and novelty_return move with every bar; the key and the hold
    clock must not."""
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    a = _row("p", 0.1, "passive_window")
    ls.screen([a], report=rep, held_path=held, sn=_fake_sn())
    store = json.loads(held.read_text())
    store["p"]["style_screen"]["held_at"] = "2026-01-01T00:00:00+00:00"
    held.write_text(json.dumps(store))
    b = _row("p", 0.1, "passive_window")
    b["style_screen"] = {"n": 1001, "novelty_return": 0.11}
    assert ls._content(a) == ls._content(b)
    ls.screen([b], report=rep, held_path=held, sn=_fake_sn())
    after = json.loads(held.read_text())
    assert list(after) == ["p"]
    assert after["p"]["style_screen"]["held_at"] == "2026-01-01T00:00:00+00:00"


def test_the_screen_stamps_the_last_day_it_read_and_the_compiler_carries_it(
        wired: Path) -> None:
    """Audit must-fix 1 on #392: the gauntlet knows the real cut, so the row says how far the
    screen read and the candidate carries it (the gauntlet's refusal is a sealed-pass patch)."""
    import pandas as pd
    df = pd.DataFrame({"close": 1.0}, index=pd.date_range("2024-01-01", periods=24 * 400,
                                                          freq="h", tz="UTC"))
    rd = ls._last_day(ls._before_lockbox(df, wired / "no_bars"))
    assert rd is not None and rd < "2025-02-03"
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    out, _ = ls.screen([_row("novel", 0.8, "trend_20d")], report=rep, held_path=held,
                       sn=_fake_sn())
    assert out[0]["style_screen"]["read_until"] == rd
    import miner_candidate_compiler as mcc
    cand = mcc._candidate("USDCNH", "exogenous_conditioner", {}, "llm_lab", out[0], "m")
    assert cand["screen_read_until"] == rd
    assert "screen_read_until" not in mcc._candidate("USDCNH", "exogenous_conditioner", {},
                                                     "llm_lab", {"cell_id": "x"}, "m")


def test_the_screen_reads_the_constitutions_held_out_share(monkeypatch: pytest.MonkeyPatch
                                                           ) -> None:
    from research.gate_policy import LOCKBOX_FRAC

    import libs.tiers.truth_kernel as tk
    monkeypatch.setattr(tk, "gauntlet_thresholds",
                        lambda *_a, **_k: {"lockbox_min_fraction": LOCKBOX_FRAC + 0.1})
    assert ls._lockbox_frac() == pytest.approx(LOCKBOX_FRAC + 0.1)
    monkeypatch.setattr(tk, "gauntlet_thresholds",
                        lambda *_a, **_k: {"lockbox_min_fraction": LOCKBOX_FRAC - 0.1})
    assert ls._lockbox_frac() == pytest.approx(LOCKBOX_FRAC), "never looser than the policy"
