"""Lead-level blind replication: selection, the frozen copy's blindness, independence, verdicts.

THE FIXTURE IS THE ARGUMENT. The bars carry a planted INTRADAY edge -- every day drifts up over
the six bars after hour 3 and does nothing else -- and the stubbed family trades exactly that.
The registry, the universe and the family table are all throwaway, so what the tests measure is
this organ's own wiring: which leads it picks, what the frozen copy is allowed to carry, WHICH
LOADER the second implementation used, and what a verdict does to the registry.

The independence check is the one worth reading twice: `proposer_common.bars` -- the first pass's
door into the parquet -- is replaced by a recorder that hands back a POISONED frame. A run that
still comes back REPRODUCED with that recorder never called is a run that loaded its own bars.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lead_replication as lr  # noqa: E402

from libs.moat import registry as R  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SYMBOL = "TESTFX"
FAMILY = "planted_ramp"
N_DAYS = 300
SIGNAL_HOUR = 3
TTL = 6
DRIFT = 0.0012


class Sig:
    """The three attributes `proposer_common.screen` reads off a signal, and nothing else."""

    __slots__ = ("side", "time", "ttl_bars")

    def __init__(self, time: Any, side: int, ttl_bars: int) -> None:
        self.time, self.side, self.ttl_bars = time, int(side), int(ttl_bars)


def family_planted(df: pd.DataFrame, side: int = 1, ttl_bars: int = TTL,
                   rr: float = 2.0) -> list[Sig]:
    """One signal a day at the planted hour. `rr` exists so a rule can declare it."""
    return [Sig(ts, side, ttl_bars) for ts in df.index if ts.hour == SIGNAL_HOUR]


def _bars(seed: int = 7, drift: float = DRIFT) -> pd.DataFrame:
    """Hourly bars whose only structure is a drift over the six hours after the signal hour.

    `open[i] == close[i-1]` exactly and the index is continuous, so `artifact_hours` finds no
    marked open and no daily reopen: the screen refuses nothing and the planted edge is the whole
    of the measurement.
    """
    rng = np.random.default_rng(seed)
    n = N_DAYS * 24
    idx = pd.date_range("2023-01-02", periods=n, freq="h", tz="UTC", name="time")
    step = rng.normal(0.0, 0.0002, n)
    hours = np.asarray(idx.hour)
    step[(hours > SIGNAL_HOUR) & (hours <= SIGNAL_HOUR + TTL)] += drift
    close = 100.0 * np.exp(np.cumsum(step))
    open_ = np.concatenate([[100.0], close[:-1]])
    return pd.DataFrame(
        {"open": open_, "high": np.maximum(open_, close) * 1.0001,
         "low": np.minimum(open_, close) * 0.9999, "close": close,
         "tick_volume": np.ones(n, dtype="int64")}, index=idx)


#: A rule the way this registry records one: JSON, and carrying the first pass's own numbers,
#: which `scrub_rule` must strip before anything downstream sees it.
RULE_JSON = json.dumps({"family_hint": f"{FAMILY} long on H1", "rr": 2.5, "ttl_bars": TTL,
                        "t": 9.1, "net_per_trade": 0.0031, "baseline": 0.5})
SHORT_RULE_JSON = json.dumps({"family_hint": f"{FAMILY} short on H1", "ttl_bars": TTL, "t": 9.1})
#: The same recipe from a miner that wrote down no statistic at all -- the common case.
RULE_NO_STATISTIC = json.dumps({"family_hint": f"{FAMILY} long on H1", "rr": 2.5,
                                "ttl_bars": TTL})
#: What the FIRST pass recorded. Never handed to the second implementation.
PAYLOAD_UP = {"t": 9.1, "net_per_trade": 0.0031, "n": 300}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A throwaway registry, a throwaway universe, a stubbed family table, and a recorder in
    place of the first pass's loader."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    universe = tmp_path / "universe"
    universe.mkdir()
    _bars().to_parquet(universe / f"{SYMBOL}_H1.parquet")
    monkeypatch.setattr(lr, "UNIVERSE", universe)
    monkeypatch.setattr(lr, "FROZEN_DIR", tmp_path / "replication")
    monkeypatch.setattr(lr, "SURVIVORS", tmp_path / "UNIVERSAL_SURVIVORS.json")
    monkeypatch.setattr(lr, "DAILY_OS", tmp_path / "DAILY_RESEARCH_OS.json")
    monkeypatch.setattr(lr, "OUT", tmp_path / "LEAD_REPLICATION.json")
    monkeypatch.setattr(lr, "family_names", lambda: {FAMILY: {"rr": 2.0, "ttl_bars": TTL}})
    monkeypatch.setattr(lr, "resolve_family", lambda name: family_planted if name == FAMILY
                        else None)
    monkeypatch.setattr(pc, "universe_meta", dict)
    first_pass_calls: list[str] = []

    def poisoned(sym: str) -> pd.DataFrame:
        """The first pass's loader, replaced by a frame with the edge REVERSED. Any reproduction
        that went through this door comes back with the wrong sign."""
        first_pass_calls.append(sym)
        return _bars(drift=-DRIFT)

    monkeypatch.setattr(pc, "bars", poisoned)
    lr.BARS_READ.clear()
    yield {"tmp": tmp_path, "universe": universe, "first_pass_calls": first_pass_calls}
    R.set_path(None)


def _lead(rule: str, *, payload: dict[str, Any] | None = None, mechanism: str = "session drift",
          assets: tuple[str, ...] = (SYMBOL,), score: float = 0.9, status: str = "queued",
          conn: Any = None) -> tuple[str, str]:
    """A discovery with one candidate, as the registry actually holds them."""
    did, _ = R.record_discovery(
        source_id="test_miner", source_type="miner", mechanism=mechanism, origin="EXTERNAL",
        generator="planted", assets=list(assets), exact_rule_if_known=rule,
        economic_rationale="a planted intraday drift the desk can re-derive",
        payload=payload or {}, conn=conn)
    cid, _ = R.enqueue_candidate(family=FAMILY, symbol=assets[0] if assets else SYMBOL,
                                 params={"rule": rule[:20]}, origin="EXTERNAL", mechanism=mechanism,
                                 discovery_id=did, status=status, conn=conn)
    R.mark_candidate(cid, status, score=score, conn=conn)
    return did, cid


def _filler(n: int = 12, conn: Any = None) -> None:
    """Enough scored candidates for a decile to BE a decile, all far below the planted lead.

    They carry no `discovery_id` on purpose: they are the population the quantile is taken over,
    not leads of their own, so the selection test measures the threshold rather than the fixture.
    """
    for i in range(n):
        cid, _ = R.enqueue_candidate(family="filler", symbol=f"F{i}", params={"i": i},
                                     origin="DESK", conn=conn)
        R.mark_candidate(cid, "queued", score=0.001 * (i + 1), conn=conn)


# ------------------------------------------------------------------------------- 1. selection

def test_a_top_decile_candidate_makes_its_lead_important(desk):
    _filler()
    did, _ = _lead(RULE_JSON, payload=PAYLOAD_UP)
    leads, diag = lr.important_leads()
    assert diag["top_decile"] is not None
    assert [entry["discovery"]["discovery_id"] for entry in leads] == [did]
    assert "top decile" in leads[0]["why"][0]


def test_a_certified_cell_and_the_daily_os_are_the_other_two_axes(desk):
    _filler()
    cert_did, cert_cid = _lead("certified rule", score=0.0005, status="survived")
    named_did, _ = _lead("named rule", assets=("OTHER",), score=0.0004)
    (desk["tmp"] / "UNIVERSAL_SURVIVORS.json").write_text(
        json.dumps({"survivors": {f"hunt.{cert_cid}": {"cell": cert_cid}}}), encoding="utf-8")
    (desk["tmp"] / "DAILY_RESEARCH_OS.json").write_text(
        json.dumps({"binding": f"the day turns on {named_did}"}), encoding="utf-8")
    leads, _ = lr.important_leads()
    why = {e["discovery"]["discovery_id"]: " ".join(e["why"]) for e in leads}
    assert "certified" in why[cert_did]
    assert "daily research OS" in why[named_did]


def test_the_decile_is_taken_over_the_whole_scored_population(desk):
    _filler()
    _lead(RULE_JSON, payload=PAYLOAD_UP)
    scores = lr.all_scores()
    assert len(scores) == 13, "the quantile must see every scored row, not one page of them"
    assert max(scores) == pytest.approx(0.9)
    _leads, diag = lr.important_leads()
    assert diag["scored_candidates"] == 13


def test_a_decile_over_a_handful_of_rows_is_unmeasured_not_a_promotion(desk):
    _lead(RULE_JSON, payload=PAYLOAD_UP)
    leads, diag = lr.important_leads()
    assert diag["top_decile"] is None
    assert "UNMEASURED" in diag["top_decile_basis"]
    assert leads == []


# ---------------------------------------------------------------------------------- 2. freeze

def test_the_frozen_copy_carries_nothing_of_the_first_implementation(desk):
    _filler()
    _lead(RULE_JSON, payload=PAYLOAD_UP)
    leads, _ = lr.important_leads()
    frozen = lr.freeze(leads[0]["discovery"])

    assert set(frozen) == set(lr.FROZEN_FIELDS)
    assert lr.forbidden_in(frozen) == []
    blob = json.dumps(frozen)
    for forbidden in ("9.1", "0.0031", "net_per_trade", '"t"', "baseline", "payload"):
        assert forbidden not in blob, f"{forbidden!r} crossed into the frozen copy"
    # The RULE survives the scrub: a replication with no recipe is not a replication.
    assert "rr" in frozen["exact_rule"] and "ttl_bars" in frozen["exact_rule"]
    assert frozen["instruments"] == [SYMBOL]


def test_a_prose_rule_keeps_its_recipe_and_loses_its_evidence():
    frozen = lr.freeze({"discovery_id": "d1", "mechanism": "m",
                        "exact_rule": "london break, rr=2.0, ttl_bars=12 (t = 6.4, p=0.001)"})
    assert "rr=2.0" in frozen["exact_rule"] and "ttl_bars=12" in frozen["exact_rule"]
    assert "6.4" not in frozen["exact_rule"] and "0.001" not in frozen["exact_rule"]
    assert lr.forbidden_in(frozen) == []


def test_the_frozen_copy_on_disk_is_the_only_thing_written(desk):
    frozen = lr.freeze({"discovery_id": "d9", "mechanism": "m", "exact_rule": "r",
                        "assets_json": json.dumps([SYMBOL])})
    path = lr.write_frozen(frozen, desk["tmp"] / "replication")
    assert path.name == "d9.json"
    assert set(json.loads(path.read_text(encoding="utf-8"))) == set(lr.FROZEN_FIELDS)


# -------------------------------------------------------------- 3. the second implementation

def test_the_rule_text_alone_gives_back_a_family_and_only_its_declared_numbers(desk):
    frozen = lr.freeze({"discovery_id": "d2", "mechanism": "session drift",
                        "exact_rule": RULE_JSON, "assets_json": json.dumps([SYMBOL])})
    spec, why = lr.reimplement(frozen, universe=desk["universe"])
    assert why == "ok"
    assert spec["family"] == FAMILY and spec["symbol"] == SYMBOL and spec["timeframe"] == "H1"
    assert spec["side"] == 1
    # `rr` came from the rule (2.5, not the family's declared 2.0); the first pass's `t` did not.
    assert spec["params"] == {"rr": 2.5, "ttl_bars": TTL}


def test_a_family_the_tree_does_not_implement_is_refused_rather_than_guessed(desk):
    frozen = lr.freeze({"discovery_id": "d3", "mechanism": "unknown thing",
                        "exact_rule": "do something clever at the open",
                        "assets_json": json.dumps([SYMBOL])})
    spec, why = lr.reimplement(frozen, universe=desk["universe"])
    assert spec is None
    assert "names no family" in why


def test_the_second_implementation_never_touches_the_first_passs_loader(desk):
    _filler()
    _lead(RULE_JSON, payload=PAYLOAD_UP)
    doc = lr.build(dry_run=True, universe=desk["universe"])
    assert doc["verdicts"][0]["verdict"] == lr.REPRODUCED
    assert desk["first_pass_calls"] == [], "the first pass's bar loader was used"
    assert any(f"{SYMBOL}_H1.parquet" in p for p in lr.BARS_READ)
    assert doc["independence"]["loaders_refused"]


def test_independent_bars_reads_the_parquet_and_records_the_read(desk):
    lr.BARS_READ.clear()
    frame = lr.independent_bars(SYMBOL, "H1", desk["universe"])
    assert frame is not None and len(frame) == N_DAYS * 24
    assert str(frame.index.tz) == "UTC"
    assert len(lr.BARS_READ) == 1
    assert lr.independent_bars("NOSUCH", "H1", desk["universe"]) is None


# --------------------------------------------------------------------------- 4. the verdicts

def test_a_lead_that_comes_back_is_reproduced_and_earns_expensive_resources(desk):
    _filler()
    did, cid = _lead(RULE_JSON, payload=PAYLOAD_UP)
    doc = lr.build(universe=desk["universe"])

    row = doc["verdicts"][0]
    assert row["verdict"] == lr.REPRODUCED
    assert row["first"]["t"] == pytest.approx(9.1)
    assert row["second"]["direction"] == 1 and row["second"]["n"] >= pc.MIN_TRADES
    assert doc["promoted"] == [did] and doc["blocked"] == []

    cand = next(c for c in R.candidates(limit=100) if c["id"] == cid)
    assert float(cand["expected_info_gain"]) == lr.INFO_GAIN_REPRODUCED
    assert cand["status"] == "queued"
    # The priority term is re-derived so it actually reorders the queue, and never downward.
    assert float(cand["score"]) >= 0.9
    mem = R.memories(kind="replication")
    assert len(mem) == 1 and did in mem[0]["statement"]
    assert (desk["tmp"] / "replication" / f"{did}.json").exists()


def test_a_lead_that_does_not_come_back_is_blocked_and_its_cells_marked_unstable(desk):
    _filler()
    did, cid = _lead(SHORT_RULE_JSON, payload=PAYLOAD_UP)
    doc = lr.build(universe=desk["universe"])

    row = doc["verdicts"][0]
    assert row["verdict"] == lr.NOT_REPRODUCED
    assert row["second"]["direction"] == -1
    assert "DIRECTION disagrees" in " ".join(row["why"])
    assert doc["blocked"] == [did] and doc["promoted"] == []

    disc = next(d for d in R.discoveries(limit=100) if d["discovery_id"] == did)
    assert disc["state"] == "BLOCKED" and disc["blocked_reason"] == "replication_failed"
    cand = next(c for c in R.candidates(limit=100) if c["id"] == cid)
    assert cand["status"] == "judged" and cand["failure_class"] == "unstable"
    assert cand["failure_class"] in R.FAILURE_CLASSES


def test_a_lead_with_no_rule_text_is_unmeasured_and_nothing_is_blocked(desk):
    _filler()
    did, cid = _lead("", payload=PAYLOAD_UP)
    doc = lr.build(universe=desk["universe"])

    row = doc["verdicts"][0]
    assert row["verdict"] == lr.UNMEASURED
    assert "no exact rule" in " ".join(row["why"])
    assert doc["blocked"] == [] and doc["promoted"] == []
    assert any(u["what"] == did for u in doc["unmeasured"])
    disc = next(d for d in R.discoveries(limit=100) if d["discovery_id"] == did)
    assert disc["state"] == "UNPROCESSED"
    assert next(c for c in R.candidates(limit=100) if c["id"] == cid)["status"] == "queued"


def test_a_lead_whose_first_pass_recorded_no_t_is_unmeasured_not_a_failure(desk):
    _filler()
    did, _ = _lead(RULE_NO_STATISTIC, payload={"note": "the miner recorded no statistic"})
    doc = lr.build(universe=desk["universe"])
    row = doc["verdicts"][0]
    assert row["verdict"] == lr.UNMEASURED
    assert "nothing to reproduce WITHIN" in " ".join(row["why"])
    assert row["second"]["n"] >= pc.MIN_TRADES, "the second reading is still published"
    assert doc["blocked"] == []
    assert next(d for d in R.discoveries(limit=100)
                if d["discovery_id"] == did)["state"] == "UNPROCESSED"


@pytest.mark.parametrize(("first", "second", "expect"), [
    ({"t": 8.0, "direction": 1}, {"t": 6.0, "direction": 1, "n": 40}, lr.REPRODUCED),
    ({"t": 8.0, "direction": 1}, {"t": 24.0, "direction": 1, "n": 40}, lr.REPRODUCED),
    ({"t": 8.0, "direction": 1}, {"t": 2.0, "direction": 1, "n": 40}, lr.NOT_REPRODUCED),
    ({"t": 8.0, "direction": 1}, {"t": -8.0, "direction": -1, "n": 40}, lr.NOT_REPRODUCED),
    ({"t": None, "direction": None}, {"t": 8.0, "direction": 1, "n": 40}, lr.UNMEASURED),
    ({"t": 8.0, "direction": 1}, {"t": None, "direction": None, "n": None, "why": "no bars"},
     lr.UNMEASURED),
])
def test_the_verdict_rule_is_a_floor_with_no_ceiling(first, second, expect):
    verdict, why = lr.judge(first, second)
    assert verdict == expect
    assert why and all(isinstance(line, str) for line in why)


# --------------------------------------------------------------------------------- the pass

def test_dry_run_writes_no_frozen_copy_no_artifact_and_no_registry_effect(desk):
    _filler()
    did, cid = _lead(SHORT_RULE_JSON, payload=PAYLOAD_UP)
    doc = lr.build(dry_run=True, universe=desk["universe"])

    assert doc["verdicts"][0]["verdict"] == lr.NOT_REPRODUCED
    assert doc["frozen"] == 0 and doc["blocked"] == [] and doc["promoted"] == []
    assert not (desk["tmp"] / "replication").exists()
    assert not (desk["tmp"] / "LEAD_REPLICATION.json").exists()
    disc = next(d for d in R.discoveries(limit=100) if d["discovery_id"] == did)
    assert disc["state"] == "UNPROCESSED"
    assert next(c for c in R.candidates(limit=100) if c["id"] == cid)["status"] == "queued"


def test_an_empty_selection_is_a_measurement_not_an_idle_organ(desk):
    doc = lr.build(universe=desk["universe"])
    assert doc["n_important"] == 0 and doc["verdicts"] == []
    assert any(u["what"] == "important_leads" for u in doc["unmeasured"])
    assert doc["rule"] == lr.RULE
    assert set(doc) >= {"at", "n_important", "frozen", "verdicts", "blocked", "promoted",
                        "unmeasured", "rule"}


def test_the_cli_dry_run_returns_zero_and_writes_nothing(desk, capsys):
    _filler()
    _lead(RULE_JSON, payload=PAYLOAD_UP)
    assert lr.main(["--dry-run", "--max-leads", "3", "--budget-s", "60"]) == 0
    out = capsys.readouterr().out
    assert "LEAD REPLICATION" in out and "dry-run" in out
    assert not (desk["tmp"] / "LEAD_REPLICATION.json").exists()


def test_the_cli_writes_the_artifact_with_the_contract_keys(desk, capsys):
    _filler()
    did, _ = _lead(RULE_JSON, payload=PAYLOAD_UP)
    assert lr.main(["--max-leads", "3"]) == 0
    capsys.readouterr()
    doc = json.loads((desk["tmp"] / "LEAD_REPLICATION.json").read_text(encoding="utf-8"))
    assert set(doc) >= {"at", "n_important", "frozen", "verdicts", "blocked", "promoted",
                        "unmeasured", "rule"}
    assert doc["rule"] == lr.RULE and doc["promoted"] == [did]
    row = doc["verdicts"][0]
    assert set(row) >= {"discovery_id", "verdict", "first", "second", "why"}
    assert set(row["first"]) >= {"t", "direction"} and set(row["second"]) >= {"t", "direction"}
