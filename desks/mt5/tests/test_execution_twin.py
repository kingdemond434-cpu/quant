"""The hourly Execution Digital Twin organ: ledgers in, report and private dataset out.

Pinned here:

  * with no intent ledger on the box the organ returns UNMEASURED with the reason, writes
    nothing and `main()` exits 0 -- it never fabricates a twin;
  * with the gateway's three ledgers it writes `reports/EXECUTION_TWIN.json` (calibration
    tables, recalibration, verdicts, every table with its n), appends every case to the private
    dataset, and moves the watermark;
  * re-running on unchanged ledgers is UNCHANGED, appends nothing and rewrites nothing; a ledger
    that grows appends exactly the new case; a case that RESOLVES later (its deal arrives) is
    appended again with its resolution, so the dataset's last row per key is the truth;
  * a symbol-filtered run is a probe: it reports and moves no watermark;
  * `main()` prints the YIELD line the hourly pass parses, and the organ is callable through
    `hourly_discovery.run_organ` under the "run_budget" convention the handoff declares.
"""
from __future__ import annotations

import inspect
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import execution_twin as et  # noqa: E402
import hourly_discovery as hd  # noqa: E402

T0 = datetime(2026, 9, 5, 9, 0, tzinfo=UTC)
PX = 3000.0


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every path the organ touches, under tmp_path. No real ledger is ever read or appended."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    monkeypatch.setattr(et, "INTENTS", data / "order_intents.jsonl")
    monkeypatch.setattr(et, "OUTCOMES", data / "execution_algo_outcomes.jsonl")
    monkeypatch.setattr(et, "LEDGER", data / "live_ledger.jsonl")
    monkeypatch.setattr(et, "UNIVERSE", data / "universe.json")
    monkeypatch.setattr(et, "STATE", data / "execution_twin_state.json")
    monkeypatch.setattr(et, "CASES", data / "execution_twin_cases.jsonl")
    monkeypatch.setattr(et, "REPORT", reports / "EXECUTION_TWIN.json")
    (data / "universe.json").write_text(json.dumps({
        "XAUUSD": {"contract_size": 100.0, "median_spread_pts": 15.0, "digits": 2,
                   "tick_size": 0.01}}), "utf-8")
    # the deal ledger exists (empty) as it does on the trading box once record_trades has run;
    # without it no resting order can ever be called UNFILLED, only unresolved
    (data / "live_ledger.jsonl").write_text("", "utf-8")

    class Desk:
        def __init__(self) -> None:
            self.n = 0

        @staticmethod
        def _append(path: Path, rows: list[dict]) -> None:
            with path.open("a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")

        def market(self, n: int, *, realised: float = 3e-4, retcode: int = 10009) -> None:
            ints, outs = [], []
            for _ in range(n):
                i = self.n
                self.n += 1
                t = T0 + timedelta(minutes=i)
                ints.append({"time": t.isoformat(timespec="seconds"), "sleeve": "fam",
                             "symbol": "XAUUSD", "side": "buy", "lot": 0.1, "intended": PX,
                             "sl": PX * 0.996, "tp": PX * 1.01, "ticket": 1000 + i,
                             "retcode": retcode, "policy_advice": {"policy": "MARKET"}})
                if retcode == 10009:
                    outs.append({"at": (t + timedelta(seconds=2)).isoformat(), "algo": "market",
                                 "symbol": "XAUUSD", "side": "buy", "lots": 0.1,
                                 "filled_lots": 0.1, "expected_cost": 1e-4,
                                 "realised_cost": realised, "filled_frac": 1.0,
                                 "expected_p_fill": 1.0, "utility": 0.1, "n_fills": 1})
            self._append(et.INTENTS, ints)
            if outs:
                self._append(et.OUTCOMES, outs)

        def bracket(self, n: int) -> list[int]:
            """n pending stops, old enough to be resolved; returns their tickets."""
            ints, tickets = [], []
            for _ in range(n):
                i = self.n
                self.n += 1
                t = T0 - timedelta(days=3) + timedelta(minutes=i)
                tickets.append(2000 + i)
                ints.append({"time": t.isoformat(timespec="seconds"), "sleeve": "gold",
                             "symbol": "XAUUSD", "side": "buy_stop", "lot": 0.1,
                             "intended": PX, "sl": PX * 0.996, "tp": PX * 1.01,
                             "ticket": 2000 + i, "retcode": 10008, "decision_bid": PX - 5,
                             "decision_ask": PX - 4.7, "spread_at_decision": 0.3,
                             "order_type": "pending_stop"})
            self._append(et.INTENTS, ints)
            return tickets

        def deal(self, ticket: int, entry: float) -> None:
            self._append(et.LEDGER, [{"time": T0.isoformat(), "sleeve": "gold",
                                      "symbol": "XAUUSD", "side": 0, "order": ticket,
                                      "entry_price": entry, "fill_price": entry + 1.0,
                                      "volume": 0.1, "account_kind": "live", "deal": ticket + 9}])

        def cases(self) -> list[dict]:
            """The dataset's rows, each tagged with the ticket its synthetic intent_id ends in."""
            p = et.CASES
            rows = [json.loads(ln) for ln in p.read_text("utf-8").splitlines()] \
                if p.exists() else []
            for r in rows:
                tail = r["intent_id"].rsplit("|", 1)[-1]
                r["ticket_key"] = int(tail) if tail.isdigit() else None
            return rows

        def report(self) -> dict:
            return json.loads(et.REPORT.read_text("utf-8"))

        def state(self) -> dict:
            return json.loads(et.STATE.read_text("utf-8"))

    return Desk()


def test_absent_ledgers_are_unmeasured_and_nothing_is_written(desk, capsys) -> None:
    d = et.run(budget_s=60.0)
    assert d["status"] == "UNMEASURED" and "no intent ledger" in d["why"]
    assert d["cases_joined"] == 0 and d["donated_rows"] == 0
    assert not et.REPORT.exists() and not et.STATE.exists() and not et.CASES.exists()
    sys.argv = ["execution_twin"]
    assert et.main() == 0
    out = capsys.readouterr().out
    assert "UNMEASURED" in out
    assert hd.parse_yield(out) == {"cases_joined": 0, "symbols_calibrated": 0,
                                   "symbols_unmeasured": 0}


def test_the_hour_writes_the_report_the_dataset_and_the_watermark(desk) -> None:
    desk.market(30, realised=3e-4)
    desk.market(2, retcode=10019)
    tickets = desk.bracket(4)
    desk.deal(tickets[0], PX + 0.5)
    d = et.run(budget_s=60.0)
    assert d["status"] == "MEASURED" and d["cases_joined"] == 36 and d["donated_rows"] == 36
    rep = desk.report()
    assert rep["cases"]["n"] == 36 and rep["cases"]["rejected"] == 2
    assert rep["cases"]["joined_outcome"] == 30 and rep["cases"]["joined_deal"] == 1
    assert rep["cases"]["by_join_key"] == {"fuzzy": 30, "none": 5, "ticket": 1}
    assert rep["cases"]["by_account_kind"] == {"unknown": 35, "live": 1}
    # the tables carry n and verdicts, and the simulator's spread came from the registry
    sym = rep["recalibration"]["symbols"]["XAUUSD"]
    assert sym["slip"]["n"] == 31 and sym["verdict"] == "SIM_TOO_OPTIMISTIC"
    # 30 market fills at 3e-4 and one bracket filled 0.5 above its trigger, on a modelled 0.0
    assert sym["slip"]["applied_frac"] == pytest.approx((30 * 3e-4 + 0.5 / PX) / 31, abs=1e-8)
    assert rep["sim_costs"]["XAUUSD"]["spread_frac"] == pytest.approx(15 * 0.01 / PX)
    assert sym["slippage_multiplier"] > 1.0
    assert rep["slippage_calibration"]["by_symbol"]["XAUUSD"]["n"] == 31
    assert rep["reject_model"]["by_symbol"]["XAUUSD"]["k"] == 2
    assert rep["fill_calibration"]["by_order_type"]["pending_stop"]["n"] == 4
    assert rep["latency"]["status"] == "UNMEASURED"
    assert rep["algo_scoreboard"]["algos"]["market"]["n"] == 30
    assert rep["execution_choice_value"]["symbols"]["XAUUSD"]["algos"]["market"]["n"] == 30
    assert rep["consumers"]["status"].startswith("NOT WIRED")
    assert any("intent_id" in g for g in rep["gaps"])
    assert d["symbols_calibrated"] == 1 and d["symbols_unmeasured"] == 0
    # the private dataset and the watermark
    rows = desk.cases()
    assert len(rows) == 36 and {r["join_key"] for r in rows} == {"fuzzy", "none", "ticket"}
    st = desk.state()
    assert st["ledger_rows"] == {"intents": 36, "outcomes": 30, "deals": 1}
    assert st["runs"] == 1 and st["donated_total"] == 36


def test_rerunning_does_not_double_count_and_growth_appends_only_the_new(desk) -> None:
    desk.market(12)
    tickets = desk.bracket(2)
    first = et.run()
    assert first["donated_rows"] == 14 and len(desk.cases()) == 14
    mtime = et.REPORT.stat().st_mtime_ns
    again = et.run()
    assert again["status"] == "UNCHANGED" and again["donated_rows"] == 0
    assert again["cases_joined"] == 14 and len(desk.cases()) == 14
    assert et.REPORT.stat().st_mtime_ns == mtime and desk.state()["runs"] == 1
    # one more market order: exactly one new row
    desk.market(1)
    third = et.run()
    assert third["donated_rows"] == 1 and len(desk.cases()) == 15
    assert desk.state()["runs"] == 2 and desk.state()["donated_total"] == 15
    # a bracket that resolves later is appended AGAIN with its resolution, the old row kept:
    # it was UNFILLED (three days old, no deal) and its deal now says it filled 2.0 above
    before = [r for r in desk.cases() if r["ticket_key"] == tickets[1]]
    assert [r["filled"] for r in before] == [False]
    desk.deal(tickets[1], PX + 2.0)
    fourth = et.run()
    assert fourth["donated_rows"] == 1 and len(desk.cases()) == 16
    after = [r for r in desk.cases() if r["ticket_key"] == tickets[1]]
    assert [r["filled"] for r in after] == [False, True]
    assert after[-1]["join_key"] == "ticket"
    assert after[-1]["actual_slip_frac"] == pytest.approx(2.0 / PX)


def test_a_symbol_filtered_run_is_a_probe_that_moves_no_watermark(desk) -> None:
    desk.market(12)
    probe = et.run(symbols=["EURUSD"])
    assert probe["status"] == "UNMEASURED" and "none usable" in probe["why"]
    assert not et.STATE.exists()
    probe = et.run(symbols=["XAUUSD"])
    assert probe["status"] == "MEASURED" and probe["symbols_filter"] == ["XAUUSD"]
    assert not et.STATE.exists() and et.REPORT.exists()


def test_main_prints_the_yield_line_the_hourly_pass_parses(desk, capsys) -> None:
    desk.market(12)
    sys.argv = ["execution_twin", "--budget-s", "30"]
    assert et.main() == 0
    out = capsys.readouterr().out
    assert "EXECUTION TWIN  cases=12" in out
    assert hd.parse_yield(out) == {"cases_joined": 12, "symbols_calibrated": 1,
                                   "symbols_unmeasured": 0}


def test_the_organ_answers_hourly_discoverys_run_budget_convention(desk, monkeypatch) -> None:
    """The handoff line is `"execution_twin": "run_budget"`; prove that convention calls it."""
    assert "budget_s" in inspect.signature(et.run).parameters
    desk.market(12)
    monkeypatch.setattr(hd, "ORGANS", {"execution_twin": "run_budget"})
    rep = hd.run_organ("execution_twin", 45.0)
    res = rep["result"]
    assert res["status"] == "MEASURED" and res["budget_s"] == 45.0
    assert res["cases_joined"] == 12
    # the standard yield counter the pass already knows counts the dataset rows donated
    assert hd.yield_of(res)["donated_rows"] == 12
