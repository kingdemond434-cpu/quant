"""AgentValue: the miner numerator meets the compute-ledger denominator, and refuses to guess.

Measured 2026-09-08 (inventory I10): survivors were measured per miner, hours were measured per
hourly leg, and nothing joined them -- `compute_ledger.rank` asked for a `value_by_run` nobody
supplied. These tests pin the join's three honest states: MEASURED where a ledger row is named
after a source with a survivor count; UNCOSTED / UNPRICED where one side is missing and NAMED;
UNJUDGED where a source's rows never reached a backtest, so its zero is not a measurement.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_miner_conversion as cmc  # noqa: E402


def _ledger(tmp_path: Path, *names: str) -> Path:
    p = tmp_path / "compute_ledger.jsonl"
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    p.write_text("".join(json.dumps({"at": now, "run": n, "kind": "hourly_cycle",
                                     "outcome": "ok", "wall_s": 1800.0, "cpu_s": 10.0}) + "\n"
                         for n in names), "utf-8")
    return p


PER_MINER = {
    "cot": {"discoveries": 22, "reached_backtest": 7, "survivors": 2, "conversion": 0.09},
    "reddit": {"discoveries": 239, "reached_backtest": 0, "survivors": 0, "conversion": 0.0},
    "deepseek": {"discoveries": 3, "reached_backtest": 3, "survivors": 0, "conversion": 0.0},
}
COMPILED = {
    "compiled_at": "2026-09-09T00:00:00+00:00",
    "per_source": {"cot": {"rows": 22, "candidates": 7, "deepening": 0},
                   "reddit": {"rows": 239, "candidates": 0, "deepening": 239},
                   "deepseek": {"rows": 3, "candidates": 3, "deepening": 0}},
    "seats": {"deepseek": {"rows": 3, "candidates": 3, "deepening": 0},
              "kimi_k3_deep_forest": {"rows": 0, "candidates": 0, "deepening": 0}},
}


def test_a_ledger_that_names_only_hourly_legs_prices_no_agent_and_says_why(tmp_path) -> None:
    av = cmc.agent_value(PER_MINER, COMPILED, ledger=_ledger(tmp_path, "mine", "search"))
    assert av["status"] == "UNMEASURED"
    assert av["table"]["ranked"] == []
    assert av["table"]["unpriced"] == ["mine", "search"]         # costed, no survivor count
    assert av["table"]["uncosted"] == ["cot", "deepseek"]        # survivor count, no hours
    assert "named after hourly-cycle legs" in av["missing_input"]
    assert "compute_ledger.costed(<miner>)" in av["missing_input"]
    assert av["value_by_run"] == {"cot": 2.0, "deepseek": 0.0}


def test_a_source_never_judged_is_unjudged_not_zero(tmp_path) -> None:
    av = cmc.agent_value(PER_MINER, COMPILED, ledger=_ledger(tmp_path, "mine"))
    assert "reddit" in av["unjudged"] and "reddit" not in av["value_by_run"]
    assert "not a measured zero" in av["unjudged"]["reddit"]
    assert av["numerator"]["sources_unjudged"] == 1
    assert av["numerator"]["sources_priced"] == 2


def test_a_ledger_row_named_after_a_source_gives_a_measured_value_per_hour(tmp_path) -> None:
    av = cmc.agent_value(PER_MINER, COMPILED, ledger=_ledger(tmp_path, "cot", "mine"))
    assert av["status"] == "MEASURED" and av["missing_input"] == ""
    (row,) = av["table"]["ranked"]
    assert row["run"] == "cot" and row["hours"] == 0.5
    assert row["value_per_hour"] == 4.0                          # 2 survivors / 0.5h
    assert av["table"]["uncosted"] == ["deepseek"]
    assert av["numerator"]["unit"] == "survivors"
    assert "Not dE[log W]" in av["numerator"]["basis"]


def test_an_absent_ledger_is_the_honest_state_not_a_zero(tmp_path) -> None:
    av = cmc.agent_value(PER_MINER, COMPILED, ledger=tmp_path / "nowhere.jsonl")
    assert av["status"] == "UNMEASURED"
    assert av["denominator"]["costed_runs"] == 0
    assert "nothing has been costed" in av["missing_input"]


def test_the_seats_block_is_reported_per_seat_with_survivors_and_cost_basis(tmp_path) -> None:
    av = cmc.agent_value(PER_MINER, COMPILED, ledger=_ledger(tmp_path, "mine"))
    seats = av["seats"]
    assert seats["status"] == "MEASURED"
    ds = seats["seats"]["deepseek"]
    assert ds["rows"] == 3 and ds["survivors"] == 0.0
    assert ds["survivors_basis"] == "survivors among rows that reached a backtest"
    assert ds["cost"].startswith("UNCOSTED")
    kimi = seats["seats"]["kimi_k3_deep_forest"]
    assert kimi["rows"] == 0 and kimi["survivors"] is None
    assert "no discovery rows" in kimi["survivors_basis"]


def test_a_compiled_artifact_without_a_seats_block_is_unmeasured_and_names_it(tmp_path) -> None:
    old = {k: v for k, v in COMPILED.items() if k != "seats"}
    av = cmc.agent_value(PER_MINER, old, ledger=_ledger(tmp_path, "mine"))
    assert av["seats"]["status"] == "UNMEASURED"
    assert "`seats` block" in av["seats"]["missing_input"]
    assert "2026-09-09" in av["seats"]["missing_input"]           # the stale compiled_at is named
    assert av["seats"]["per_source_fallback"] == {"deepseek": COMPILED["per_source"]["deepseek"]}


def test_no_compiled_artifact_at_all_is_unmeasured_and_names_the_file(tmp_path) -> None:
    av = cmc.agent_value(PER_MINER, None, ledger=_ledger(tmp_path, "mine"))
    assert av["seats"]["status"] == "UNMEASURED"
    assert "miner_candidates.json" in av["seats"]["missing_input"]


def test_main_writes_the_agent_value_artifact_beside_the_alarm(tmp_path, monkeypatch) -> None:
    for name in ("OUT", "ALARM", "AGENT_VALUE"):
        monkeypatch.setattr(cmc, name, tmp_path / f"{name}.json")
    monkeypatch.setattr(cmc, "INTEL", [tmp_path / "no_intel"])
    monkeypatch.setattr(cmc, "CERTS", tmp_path / "no_certs.json")
    monkeypatch.setattr(cmc, "HYP", tmp_path / "no_hyp.json")
    monkeypatch.setattr(cmc, "COMPILED", tmp_path / "no_compiled.json")
    monkeypatch.setattr(cmc, "request_repair", lambda *_a, **_k: None)
    cmc.main()
    av = json.loads((tmp_path / "AGENT_VALUE.json").read_text("utf-8"))
    assert av["status"] in ("MEASURED", "UNMEASURED")
    assert av["seats"]["status"] == "UNMEASURED"
    assert "rule" in av and "UNJUDGED" in av["rule"]
