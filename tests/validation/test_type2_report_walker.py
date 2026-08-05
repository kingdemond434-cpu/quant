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
    assert all("screen agrees" in c.note for c in costs), [
        c.note for c in costs if "screen agrees" not in c.note
    ]


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
    assert any(u["status"] == "NOT-READABLE-HERE" for u in unread), (
        "the blocked moat artifact must be reported as unreadable, not omitted"
    )
    doc = _MOD.build_artifact(costs, unread, _ROOT)
    json.dumps(doc, allow_nan=False)
    assert doc["citations"] == dict.fromkeys(doc["citations"], True), (
        f"cited measured context is missing from this checkout: {doc['citations']}"
    )


@pytest.mark.parametrize("label", [POWERED, UNDERPOWERED, INDETERMINATE])
def test_the_three_labels_are_the_only_vocabulary(label: str) -> None:
    assert label in {"POWERED-NEGATIVE", "UNDERPOWERED", "INDETERMINATE"}
