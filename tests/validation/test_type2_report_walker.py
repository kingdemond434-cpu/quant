"""The walker must read what is on disk and INVENT NOTHING.

Two failure modes are fenced here, both of which would turn an honesty instrument into a
fabrication one:

  1. UNDERCOUNTING THE DENOMINATOR. Every recorded negative that cannot be labelled must still be
     counted. The first draft of the graveyard parser closed a markdown table on the first prose
     line and lost 26 of 44 kills to a paragraph sitting mid-table -- which would have flattered
     the powered fraction by dropping exactly the rows that are unlabellable.
  2. RECONSTRUCTING AN ABSENT ARTIFACT. Files cited in the docs but not present in a checkout
     (VPS runtime state) must be reported as NOT-READABLE-HERE, never rebuilt from the prose that
     cites them.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from libs.validation.type2_cost import INDETERMINATE, POWERED, UNDERPOWERED

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "run_type2_report", _ROOT / "scripts/run_type2_report.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_MOD: ModuleType = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

_GRAVEYARD = """# Graveyard

| Hypothesis | Verdict | Tag | Lesson |
|---|---|---|---|
| alpha_one | Sharpe -1.4 | `wrong_sign` | note |
| alpha_two | IC -0.04, n=5 majors, 180 bars | `no_edge` | note |

**Standing conclusion:** a paragraph in the middle of the table.

| alpha_three | -0.8 | `overfit` | note |

## another table that is not a list of kills

| era | venue pair | the barrier | outcome |
|---|---|---|---|
| 2013 | MtGox / BTC-e | insolvency | premium -> 0 |
"""


def _write(root: Path, rel: str, payload: Any) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload), "utf-8")


def test_graveyard_table_survives_prose_and_excludes_non_kill_tables(tmp_path: Path) -> None:
    rows = _MOD._graveyard_rows(_GRAVEYARD)
    assert [r[0] for r in rows] == ["alpha_one", "alpha_two", "alpha_three"]
    assert not any("MtGox" in r[1] for r in rows)


def test_every_graveyard_row_is_indeterminate_and_no_number_is_parsed_from_prose(
    tmp_path: Path,
) -> None:
    """'n=5 majors' is a symbol count and '180 bars' a per-symbol length. Neither is a sample size.

    Guessing one would manufacture the evidence whose absence is the finding, so the row is
    labelled INDETERMINATE and the prose is flagged for a human instead.
    """
    _write(tmp_path, "docs/graveyard.md", _GRAVEYARD)
    costs, unread = _MOD.read_graveyard(tmp_path)
    assert unread == []
    assert len(costs) == 3
    assert {c.label for c in costs} == {INDETERMINATE}
    assert all(not c.powered for c in costs)
    two = next(c for c in costs if c.name == "alpha_two")
    assert "NOT parsed here" in two.note


def test_real_graveyard_on_this_checkout_is_read_and_wholly_indeterminate() -> None:
    costs, _ = _MOD.read_graveyard(_ROOT)
    assert len(costs) >= 40, "the kill tables lost rows -- the denominator is being undercounted"
    assert {c.label for c in costs} == {INDETERMINATE}


def test_blocked_moat_artifact_is_reported_not_reconstructed(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "reports/moat_campaign.json",
        {"status": "BLOCKED", "blocker": "no recorded symbols", "rows": []},
    )
    costs, unread = _MOD.read_moat(tmp_path)
    assert costs == []
    assert len(unread) == 1
    assert unread[0]["status"] == "NOT-READABLE-HERE"
    assert "not reconstructed" in unread[0]["why"] or "NOT reconstructed" in unread[0]["why"]


def test_absent_artifacts_are_reported_never_silently_skipped(tmp_path: Path) -> None:
    """'I could not read it' must never render as 'there was nothing there'."""
    for reader in (
        _MOD.read_gauntlet_certification,
        _MOD.read_exchange_netflow,
        _MOD.read_unlock_screen,
        _MOD.read_cot_screen,
        _MOD.read_moat,
        _MOD.read_axis_screens,
    ):
        costs, unread = reader(tmp_path)
        assert costs == []
        assert len(unread) == 1
        assert unread[0]["status"] == "NOT-READABLE-HERE"


def test_byte_identical_campaign_artifacts_are_counted_once(tmp_path: Path) -> None:
    payload = {
        "n_candidates": 4,
        "bars_per_symbol": {"BTC": 2000},
        "pooled_by_mechanism": {"n_mechanisms": 0, "rows": []},
        "top_by_oos": [],
    }
    _write(tmp_path, "reports/real_campaign.json", payload)
    _write(tmp_path, "reports/real_campaign_max.json", payload)
    costs, unread = _MOD.read_real_campaigns(tmp_path)
    assert len(costs) == 1
    assert any(u["status"] == "DUPLICATE" for u in unread)


def test_intraday_intervals_are_converted_on_their_own_clock(tmp_path: Path) -> None:
    """Three artifacts covering the same 61 days must not read as different amounts of evidence."""
    for name, interval, bars in (
        ("intraday_rotation.json", None, 17568),
        ("intraday_rotation_15m.json", "15m", 5856),
        ("intraday_rotation_1h.json", "1h", 1464),
    ):
        payload: dict[str, Any] = {
            "protocol": {"test_bars": bars, "n_configs_deflation": 540},
            "deployment_gate": {
                "rotation": {"verdict": "NO-GO", "oos_annualised_sharpe": -20.8}
            },
        }
        if interval is not None:
            payload["interval"] = interval
        _write(tmp_path, f"reports/{name}", payload)
    costs, unread = _MOD.read_intraday(tmp_path)
    assert unread == []
    assert len(costs) == 3
    floors = {round(c.min_detectable_effect, 6) for c in costs}
    assert len(floors) == 1, "bar size changed the answer; only elapsed time may"
    assert {c.label for c in costs} == {UNDERPOWERED}


def test_unknown_bar_interval_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "reports/intraday_rotation_3s.json",
        {
            "interval": "3s",
            "protocol": {"test_bars": 100, "n_configs_deflation": 1},
            "deployment_gate": {"rotation": {"verdict": "NO-GO"}},
        },
    )
    costs, unread = _MOD.read_intraday(tmp_path)
    assert costs == []
    assert unread and "unknown bar interval" in unread[0]["why"]


def test_screen_cells_reproduce_the_screens_own_powered_flag_on_this_checkout() -> None:
    """The module GENERALISES axis_screen; it must not re-judge the cells it reads."""
    costs: list[Any] = []
    for reader in (_MOD.read_axis_screens, _MOD.read_exchange_netflow):
        got, _ = reader(_ROOT)
        costs.extend(got)
    assert costs, "no Stage-A screen cells found on this checkout"
    # THREE STATES. A cell whose screen recorded NO powered flag has not disagreed with anything,
    # and calling that a disagreement manufactures a finding out of a silence -- which is what
    # started happening the moment converted screens (whose sources report a verdict and a
    # detection floor but never a boolean) reached this directory. What must still FAIL is a real
    # contradiction: the screen said powered and this module says otherwise, or vice versa.
    contradictions = [c.note for c in costs if "DISAGREES" in c.note]
    assert not contradictions, contradictions
    assert any("screen agrees" in c.note for c in costs), (
        "not one cell reproduced its screen's own flag -- the walker is no longer checking "
        "anything, which is the quiet direction of failure")


def test_declared_trials_are_reported_but_never_applied(tmp_path: Path) -> None:
    """A cell powered only at N=1 while its artifact declares six trials must say so, and keep its
    verdict. The label uses the multiplicity the SCREEN applied; the fragility is only a note.
    """
    cell = {
        "name": "cell",
        "n": 4294,
        "horizon_days": 0.003472222222222222,
        "panel_width": 1,
        "powered": True,
        "min_detectable_ic": 0.0299,
        "verdict": "SCREEN-WEAK",
    }
    labelled = _MOD._screen_cell(cell, name="cell", source="s", n_tests=1, declared_trials=6)
    assert labelled.label == POWERED, "the screen's N=1 verdict must be reproduced, not replaced"
    assert "screen agrees" in labelled.note
    assert "FRAGILE" in labelled.note and "NOT applied" in labelled.note

    unchanged = _MOD._screen_cell(cell, name="cell", source="s", n_tests=1, declared_trials=1)
    assert "FRAGILE" not in unchanged.note
    assert unchanged.label == labelled.label


def test_end_to_end_writes_a_strict_json_artifact(tmp_path: Path) -> None:
    _write(tmp_path, "docs/graveyard.md", _GRAVEYARD)
    _write(
        tmp_path,
        "reports/real_campaign.json",
        {
            "n_candidates": 10,
            "bars_per_symbol": {"BTC": 2018, "ETH": 2018},
            "pooled_by_mechanism": {
                "n_mechanisms": 1,
                "rows": [
                    {
                        "name": "POOLED:x",
                        "n_symbols": 2,
                        "symbols": ["BTC", "ETH"],
                        "failed_gates": ["reality_check"],
                    }
                ],
            },
            "top_by_oos": [{"name": "BTC:x", "n_bars": 2018, "failed_gates": ["dsr"]}],
        },
    )
    out = tmp_path / "data/type2_cost.json"
    assert _MOD.main(["--json", str(out), "--root", str(tmp_path), "--quiet"]) == 0
    doc = json.loads(out.read_text("utf-8"))
    json.dumps(doc, allow_nan=False)  # must be strict JSON: no bare NaN/Infinity anywhere
    assert doc["alpha"] == 0.05
    # 3 graveyard kills + the campaign-level zero + 1 pooled mechanism + 1 published per-symbol row.
    assert doc["headline"]["n_negatives"] == len(doc["negatives"]) == 6
    assert doc["headline"]["n_indeterminate"] == 3
    assert {r["label"] for r in doc["negatives"]} <= {POWERED, UNDERPOWERED, INDETERMINATE}
    assert "LABELS ONLY" in doc["authority"]
    assert doc["generated_utc"].endswith("+00:00"), "timestamps must be timezone-aware UTC"


def test_end_to_end_on_this_checkout_labels_every_row(tmp_path: Path) -> None:
    costs, unread = _MOD.collect(_ROOT)
    assert costs, "no recorded negatives found on this checkout"
    assert all(c.label in {POWERED, UNDERPOWERED, INDETERMINATE} for c in costs)
    assert all(c.source for c in costs), "every negative must name the artifact it came from"
    # THE INVARIANT, NOT THE SNAPSHOT. This used to assert that SOME artifact reports
    # NOT-READABLE-HERE, which was really an assertion that the moat campaign was still blocked on
    # this checkout. It ran, the reader gained a real-shape branch, `unread` went empty, and the
    # test went red on a repo that had just got BETTER -- a test coupled to live state rather than
    # to behaviour. What must actually hold is that nothing is silently DROPPED: an artifact the
    # readers could not turn into labelled costs appears in `unread` with a status and a reason.
    for u in unread:
        assert u.get("status"), f"an unread artifact with no status: {u}"
        assert u.get("why"), f"{u.get('artifact')} is reported unread with no reason"
        assert u.get("artifact"), f"an unread entry naming no artifact: {u}"
    doc = _MOD.build_artifact(costs, unread, _ROOT)
    json.dumps(doc, allow_nan=False)
    # A DANGLING citation is a repo defect and still fails. A runtime-only citation absent from a
    # clean checkout is not: reports/ is gitignored, so demanding all four citations be present
    # asserted that this BOX had run a particular producer -- and turned the walker red on any
    # checkout that had not. The two are now declared apart at the source.
    assert doc["citations_dangling"] == [], (
        f"this report cites tracked files that no longer exist: {doc['citations_dangling']}"
    )


@pytest.mark.parametrize("label", [POWERED, UNDERPOWERED, INDETERMINATE])
def test_the_three_labels_are_the_only_vocabulary(label: str) -> None:
    assert label in {"POWERED-NEGATIVE", "UNDERPOWERED", "INDETERMINATE"}


class TestTheMoatReaderHandlesBothShapes:
    """The reader was written when reports/moat_campaign.json was BLOCKED with zero rows. The
    campaign then ran and it reported UNHANDLED-SHAPE -- honest, and 48 recorded negatives went
    unlabelled anyway. These fix the shape it now reads to a FIXTURE, so the next environment
    change breaks a fixture rather than the live-checkout test."""

    @staticmethod
    def _write(tmp_path: Path, doc: dict) -> Path:
        (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
        (tmp_path / "reports/moat_campaign.json").write_text(json.dumps(doc), "utf-8")
        return tmp_path

    def test_a_blocked_artifact_is_still_reported_not_reconstructed(self, tmp_path: Path) -> None:
        """The original behaviour, preserved: the prose in VPS_STATE cites rows this checkout does
        not have, and inventing them would fabricate the exact record this instrument demands."""
        root = self._write(tmp_path, {"status": "BLOCKED", "blocker": "no lake", "rows": []})
        costs, unread = _MOD.read_moat(root)
        assert costs == []
        assert unread[0]["status"] == "NOT-READABLE-HERE"

    def test_rows_are_labelled_on_the_bar_the_artifact_declares(self, tmp_path: Path) -> None:
        """THE CLOCK BUG THIS GUARDS. sharpe_negative demands n_bars and ppy share a clock. The
        moat campaign runs on 60,000ms bars, so passing the module-wide daily PPY would credit
        4,980 minutes of tape with 13.6 YEARS and turn the desk's blindest campaign into its
        best-powered one."""
        root = self._write(tmp_path, {
            "status": "COMPLETE", "bar_ms": 60000, "n_obs": 4980, "n_candidates": 2,
            "bars_per_symbol": {"BTCUSDT": 25791},
            "rows": [{"name": "flow:BTCUSDT", "survived": False, "oos_sharpe": 0.1,
                      "failed": ["fragility"]}],
        })
        costs, unread = _MOD.read_moat(root)
        assert unread == []
        assert len(costs) == 2, "one campaign-level row plus one per non-survivor"
        assert all(c.label == UNDERPOWERED for c in costs), (
            "25,791 ONE-MINUTE bars is 18 days; anything but UNDERPOWERED means the clock was "
            "read as daily")
        assert all(c.power_at_reference < 0.05 for c in costs)

    def test_a_screen_survivor_is_not_counted_as_a_negative(self, tmp_path: Path) -> None:
        root = self._write(tmp_path, {
            "status": "COMPLETE", "bar_ms": 60000, "n_obs": 4980, "n_candidates": 2,
            "bars_per_symbol": {"BTCUSDT": 25791},
            "rows": [{"name": "a:BTCUSDT", "survived": True},
                     {"name": "b:BTCUSDT", "survived": False}],
        })
        costs, _ = _MOD.read_moat(root)
        assert [c.name for c in costs if c.source.endswith("#rows")] == ["b:BTCUSDT"]

    def test_a_missing_bar_interval_is_refused_rather_than_assumed(self, tmp_path: Path) -> None:
        """No interval means no way to turn a bar count into elapsed time. Guessing daily is the
        one assumption that makes every label wrong in the OPTIMISTIC direction."""
        root = self._write(tmp_path, {
            "status": "COMPLETE", "n_obs": 4980, "n_candidates": 1,
            "rows": [{"name": "a:BTCUSDT", "survived": False}],
        })
        costs, unread = _MOD.read_moat(root)
        assert costs == []
        assert unread[0]["status"] == "NOT-READABLE-HERE"
        assert "bar_ms" in unread[0]["why"]

    def test_a_symbol_absent_from_the_bar_map_says_so(self, tmp_path: Path) -> None:
        root = self._write(tmp_path, {
            "status": "COMPLETE", "bar_ms": 60000, "n_obs": 4980, "n_candidates": 1,
            "bars_per_symbol": {"BTCUSDT": 25791},
            "rows": [{"name": "a:NOTINMAP", "survived": False}],
        })
        costs, _ = _MOD.read_moat(root)
        row = next(c for c in costs if c.source.endswith("#rows"))
        assert "absent from bars_per_symbol" in row.note


def test_a_converted_cell_is_judged_on_its_own_recorded_n_eff(tmp_path: Path) -> None:
    """THE conv_idle REGRESSION. A converted screen deflated 136,931 raw rows to an honest
    n_eff of 1,711 -- but recorded no panel_width, because the conversion had none to carry.
    Recomputing from raw n branded the cell POWERED and its honest powered=False flag a
    contradiction. The cell's own recorded n_eff is the screen's convention; reproducing the
    screen means using it."""
    _write(tmp_path, "reports/axis_screens/converted__trials.json", {
        "trials": [{
            "name": "conv::cell::h1d", "n": 136931, "n_eff": 1711.6, "horizon_days": 1.0,
            "ic": 0.0106, "min_detectable_ic": 0.0474, "powered": False,
            "verdict": "SCREEN-UNDERPOWERED",
        }],
    })
    costs, unread = _MOD.read_axis_screens(tmp_path)
    assert unread == []
    assert len(costs) == 1
    assert "DISAGREES" not in costs[0].note, costs[0].note
    assert "screen agrees" in costs[0].note


def test_a_real_contradiction_still_fires_on_the_recorded_n_eff(tmp_path: Path) -> None:
    """The detection must survive the fix: a cell whose recorded powered flag contradicts its
    OWN recorded n_eff (1.96/sqrt(50) = 0.277 >> 0.03) is a genuinely broken artifact, and the
    walker must say so."""
    _write(tmp_path, "reports/axis_screens/broken__trials.json", {
        "trials": [{
            "name": "broken::cell::h1d", "n": 9000, "n_eff": 50.0, "horizon_days": 1.0,
            "ic": 0.001, "min_detectable_ic": 0.277, "powered": True,
            "verdict": "SCREEN-WEAK",
        }],
    })
    costs, _ = _MOD.read_axis_screens(tmp_path)
    assert len(costs) == 1
    assert "DISAGREES" in costs[0].note, costs[0].note


def test_the_powered_flag_is_reproduced_at_the_screens_own_power_convention(
        tmp_path: Path) -> None:
    """The screen's `powered` is a 50%-power detectability floor (1.96/sqrt(n_eff) <= 0.03,
    so n_eff >= ~4270). Judging it at this module's 80% default (n_eff >= ~8710) manufactured a
    contradiction on every honest cell in between -- a false fire produced by the instrument's
    own convention, not by the screen."""
    _write(tmp_path, "reports/axis_screens/between__trials.json", {
        "trials": [{
            "name": "between::cell::h1d", "n": 6000, "n_eff": 6000.0, "horizon_days": 1.0,
            "ic": 0.002, "min_detectable_ic": 0.0253, "powered": True,
            "verdict": "SCREEN-WEAK",
        }],
    })
    costs, _ = _MOD.read_axis_screens(tmp_path)
    assert len(costs) == 1
    assert "DISAGREES" not in costs[0].note, costs[0].note
    assert "screen agrees" in costs[0].note


def test_a_cell_without_recorded_n_eff_recomputes_honouring_overlap_periods(
        tmp_path: Path) -> None:
    """Fallback path: no recorded n_eff. The recompute must use the recorded overlap deflation
    (non-overlapping grid -> 1), not the annualisation horizon -- 8000/(1*100)=80, not
    8000/(20*100)=4."""
    _write(tmp_path, "reports/axis_screens/legacy__trials.json", {
        "trials": [{
            "name": "legacy::cell::h20d", "n": 8000, "horizon_days": 20.0,
            "overlap_periods": 1.0, "panel_width": 100,
            "ic": 0.001, "verdict": "SCREEN-UNDERPOWERED",
        }],
    })
    costs, _ = _MOD.read_axis_screens(tmp_path)
    assert len(costs) == 1
    assert abs(costs[0].n_eff - 80.0) < 1.0, costs[0].n_eff
