"""The expression factory: memory-derived caps, the sealed lockbox, the cost-ordered cheap layer,
a null factory that rejects a planted null and admits a planted signal, the campaign state
machine, the campaign adapter's registry rows with provenance, credits and negative knowledge,
islands and migration, transfer-before-tuning, and a no-LLM end-to-end pass on synthetic bars
that writes the artifact and its state under tmp_path."""
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


from libs.research import alpha_grammar as ag  # noqa: E402
from research import expression_factory as XF  # noqa: E402

N = 3600
META = {"AAA": {"asset_class": "Forex"}, "BBB": {"asset_class": "Forex"}}


def _bars(seed: int, n: int = N, drift: float = 0.0004) -> pd.DataFrame:
    """Synthetic H1 bars with a PLANTED mechanism: an 8-bar forward drift that follows a slow
    oscillation, which the bar's own shape (body / range) and its tick activity carry."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    ret = rng.normal(0, 0.0008, n) + drift * np.sign(np.sin(2 * np.pi * np.arange(n) / 96))
    close = 100 * np.exp(np.cumsum(ret))
    high = close * (1 + np.abs(rng.normal(0, 0.0005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.0005, n)))
    op = np.roll(close, 1)
    op[0] = close[0]
    tv = 100 + 50 * np.abs(np.sin(2 * np.pi * np.arange(n) / 96)) + rng.integers(0, 20, n)
    return pd.DataFrame({"open": op, "high": high, "low": low, "close": close,
                         "tick_volume": tv, "spread": 10.0}, index=idx)


def _world(bars: pd.DataFrame, extra: dict[str, pd.Series] | None = None,
           symbol: str = "AAA") -> XF.World:
    frames = ag.terminal_frames(bars, raw=bars, extra=extra)
    idx = pd.DatetimeIndex(bars.index)
    return XF.World(symbol, frames, np.log(frames["close"].to_numpy(dtype=float)),
                    idx.hour.to_numpy(dtype=np.int16), XF._regimes(frames["vol"]), 1e-4,
                    np.ones(24), {}, "Forex", "MEASURED")


@pytest.fixture
def factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> XF.Factory:
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup", raising=False)
    R.set_path(tmp_path / "alpha_registry.sqlite")
    paths = XF.Paths(tmp_path / "desk")
    lake = XF.Lake(paths, meta=META)
    for i, s in enumerate(META):
        lake.injected[s] = _bars(i)
    return XF.Factory(paths, lake=lake, seed=7, registry=R)


# ------------------------------------------------------------------ caps and the lockbox
def test_caps_are_derived_from_measured_free_memory_and_floor_when_unmeasured() -> None:
    floor = XF.derive_caps(None)
    assert (floor.max_symbols, floor.cache_cells, floor.max_cells, floor.twin_k) == \
        (3, 500_000, 200, 4) and not floor.stood_down
    down = XF.derive_caps(XF.MIN_FREE_MB - 1)
    assert down.stood_down and "stood down" in down.why
    big = XF.derive_caps(8000.0)
    assert 3 <= big.max_symbols <= 12 and big.max_cells > floor.max_cells
    assert XF.derive_caps(200_000.0).max_cells == 20_000


def test_the_lockbox_seals_the_tail_and_is_never_opened() -> None:
    bars = _bars(0)
    research, box = XF._seal(bars)
    assert box["status"] == "SEALED" and box["opened"] is False
    assert len(research) == int(N * (1 - XF.LOCKBOX_FRAC))
    assert box["sealed_from"] == str(bars.index[len(research)])
    assert research.index[-1] < bars.index[len(research)]
    short, box2 = XF._seal(bars.iloc[:800])
    assert box2["status"] == "UNSEALED" and len(short) == 800
    assert not any(name.startswith("open") for name in dir(XF.Factory))


# ------------------------------------------------------------------ the cheap layer
def test_cheap_layer_is_cost_ordered_and_names_the_first_failing_screen() -> None:
    world = _world(_bars(1))
    idx = world.frames["close"].index
    n = len(idx)
    const = pd.Series(1.0, index=idx)
    assert XF.cheap_screens(const, XF._zscore(const), world, 8, [])[0] == "non_constant"
    sparse = pd.Series(np.nan, index=idx)
    assert XF.cheap_screens(sparse, XF._zscore(sparse), world, 8, [])[0] == "finite"
    rng = np.random.default_rng(0)
    noise = pd.Series(rng.normal(0, 1, n), index=idx)
    z = XF._zscore(noise)
    failed, m = XF.cheap_screens(noise, z, world, 8, [])
    assert failed in ("ic", None) and "turnover" in m
    signal = world.frames["body"] / world.frames["range"]
    zs = XF._zscore(signal)
    failed, m = XF.cheap_screens(signal, zs, world, 8, [])
    assert failed is None and abs(m["ic"]) >= XF.CHEAP["ic_min"]
    twin = [("twin", zs.astype(np.float32))]
    failed, m = XF.cheap_screens(signal, zs, world, 8, twin)
    assert failed == "orthogonality" and m["rho_max"] >= XF.TWIN_RHO
    assert list(XF.CHEAP_ORDER) == ["finite", "non_constant", "turnover", "ic", "orthogonality"]


# ------------------------------------------------------------------ the null factory
def test_null_factory_rejects_a_planted_null_and_admits_a_planted_signal() -> None:
    rng = np.random.default_rng(11)
    n = N
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    ret = rng.normal(0, 0.001, n)
    close = 100 * np.exp(np.cumsum(ret))
    bars = pd.DataFrame({"open": np.roll(close, 1), "high": close * 1.0005, "low": close * 0.9995,
                         "close": close, "tick_volume": 100.0, "spread": 10.0}, index=idx)
    # THE PLANTED NULL: an external terminal of pure noise on a pure random walk
    null_world = _world(bars, {"positioning": pd.Series(rng.normal(0, 1, n), index=idx)})
    cell = XF.Cell(["zscore", "positioning", 24], "AAA", 8, asset_class="Forex")
    value = ag.evaluate(cell.expr, null_world.frames, {})
    t = XF.tier1(cell, null_world, value, np.random.default_rng(1))
    assert not t.passed
    z = XF._zscore(value)
    entries = XF._entries(z, 8, None)
    nulls = XF.null_factory(null_world, entries[int(entries.size * XF.IS_SHARE):], z, 1, 8,
                            0.0, np.random.default_rng(2))
    assert nulls["p_null"] > XF.T1["p_perm"] and nulls["worst"] in ("permutation", "shuffle",
                                                                    "synthetic")
    # THE PLANTED SIGNAL: the same terminal carrying the next eight bars' return
    fwd = np.log(close)
    lead = np.concatenate([fwd[8:] - fwd[:-8], np.zeros(8)]) + rng.normal(0, 0.002, n)
    sig_world = _world(bars, {"positioning": pd.Series(lead, index=idx)})
    value = ag.evaluate(cell.expr, sig_world.frames, {})
    t = XF.tier1(cell, sig_world, value, np.random.default_rng(1))
    assert t.passed, t.reason
    assert t.p_null <= XF.T1["p_perm"] and t.side == 1
    m = t.metrics()
    assert {"p_perm", "p_shuffle", "p_synth", "p_null", "worst_null"} <= set(m)


# ------------------------------------------------------------------ the campaign state machine
class _Row(dict[str, Any]):
    def __getitem__(self, k: str) -> Any:
        return dict.get(self, k)


class _Conn:
    def __init__(self, rows: dict[str, dict[str, Any]]) -> None:
        self.rows = rows

    def execute(self, _sql: str, args: tuple[str, str]) -> _Conn:
        self._hit = self.rows.get(args[0])
        return self

    def fetchone(self) -> _Row | None:
        return None if self._hit is None else _Row(self._hit)


def test_campaign_transitions_are_enforced_persisted_and_advanced_from_the_registry(
        tmp_path: Path) -> None:
    camp = XF.Campaign(tmp_path)
    cells = [XF.Cell(["delta", "close", w], "AAA", 8, asset_class="Forex", chain=["transfer"])
             for w in (5, 8, 12, 24)]
    for c in cells:
        camp.propose(c)
    k0, k1, k2, k3 = (c.key for c in cells)
    camp.advance(k0, "SCREENED")
    camp.advance(k0, "QUEUED", candidate_id="cand_a")
    camp.advance(k0, "TESTING")
    camp.advance(k0, "FORWARD")
    with pytest.raises(XF.CampaignError):
        camp.advance(k0, "FAILED")                     # FORWARD is terminal
    with pytest.raises(XF.CampaignError):
        camp.advance(k1, "QUEUED")                     # PROPOSED cannot skip SCREENED
    with pytest.raises(XF.CampaignError):
        camp.advance("never", "SCREENED")
    camp.fail(k1, "cheap:ic")
    camp.advance(k2, "SCREENED")
    camp.advance(k2, "QUEUED", candidate_id="cand_c")
    camp.advance(k3, "SCREENED")
    camp.advance(k3, "QUEUED", candidate_id="cand_d")
    assert camp.counts()["this_pass"]["QUEUED"] == 3
    camp.save()
    again = XF.Campaign(tmp_path)
    assert set(again.rows) == {k0, k2, k3}              # cheap-failed rows are counted, not kept
    assert again.lifetime["PROPOSED"] == 4 and again.lifetime["FAILED"] == 1
    journal = [json.loads(ln) for ln in (tmp_path / "campaign.jsonl").read_text().splitlines()]
    assert [t["to"] for t in journal if t["key"] == k0] == ["SCREENED", "QUEUED", "TESTING",
                                                             "FORWARD"]
    moved = again.refresh(_Conn({"cand_c": {"status": "claimed", "survived": 0},
                                 "cand_d": {"status": "judged", "survived": 0,
                                            "terminal_gate": "deflated_sharpe"}}))
    assert moved == {"TESTING": 1, "FORWARD": 0, "FAILED": 1, "unchanged": 0}
    assert again.state_of(k2) == "TESTING" and again.state_of(k3) == "FAILED"
    assert "deflated_sharpe" in again.rows[k3]["why"]
    assert again.refresh(_Conn({"cand_c": {"status": "survived", "survived": 1}}))["FORWARD"] == 1


# ------------------------------------------------------------------ credits and negative knowledge
def test_credits_reallocate_draws_toward_what_earns_and_record_negative_knowledge(
        tmp_path: Path) -> None:
    cr = XF.Credits(tmp_path / "credits.json")
    good, bad = ["delta", "close", 24], ["corr", "ret", "activity", 24]
    for _ in range(XF.NEG_KNOWLEDGE_N):
        cr.charge(bad, "subtree", "Forex")
        cr.charge(good, "point", "Forex")
    for _ in range(10):
        cr.screened(good, "point", "Forex")
    cr.survivor(good, "point", "Forex")
    w = dict(zip(XF.MOVES, cr.move_weights(XF.MOVES), strict=True))
    assert w["point"] > w["subtree"] and abs(sum(w.values()) - 1.0) < 1e-9
    neg = cr.never_survives()
    assert {r["operator"] for r in neg} == {"corr"} and neg[0]["asset_class"] == "Forex"
    assert cr.op_weight("delta", "Forex") > cr.op_weight("corr", "Forex")
    cr.save()
    back = XF.Credits(tmp_path / "credits.json")
    assert back.moves["point"]["survivors"] == 1 and back.ops["corr"]["trials"] == 40
    s = back.summary(XF.MOVES)
    assert s["negative_knowledge"][0]["operator"] == "corr" and "credit" in s["rule"]


# ------------------------------------------------------------------ islands, migration, the law
def test_islands_migrate_elites_as_parents_transferred_before_tuning(
        factory: XF.Factory) -> None:
    elite = XF.Cell(["zscore", "close", 24], "SPX", 8, asset_class="Indices", chain=["invent"])
    factory.islands = {"Indices": {"elites": {elite.descriptor(): {
        "score": 3.0, "cell": elite.as_dict()}}}}
    assert factory.migrate("Forex") == 1
    migrants = [p for p in factory.parents.values() if p.kind == "migrant"]
    assert len(migrants) == 1 and migrants[0].chain == ["invent", "migrate:Indices->Forex"]
    assert not migrants[0].transferred
    with pytest.raises(XF.TransferBeforeTuning):
        factory.mutate_parent(migrants[0])
    factory.archive = {"m/none|h8|Forex|single+bar+own": {"score": 1.5, "cell": XF.Cell(
        ["delta", "close", 5], "AAA", 8, asset_class="Forex").as_dict()}}
    factory.update_islands("Forex")
    assert set(factory.islands) == {"Indices", "Forex"}
    assert len(factory.islands["Forex"]["elites"]) == 1
    assert factory.migrate("Indices") == 1                   # and back the other way


def test_the_archive_key_is_mechanism_horizon_asset_class_representation() -> None:
    c = XF.Cell(["xrank", ["delta", "close", 24]], "AAA", 24, "session:london",
                asset_class="Forex")
    mech, hold, klass, rep = c.descriptor().split("|")
    assert mech.endswith("/session") and hold == "h24" and klass == "Forex"
    assert rep == "panel+bar+own"
    assert (XF.executable_by_formula_family(c.expr, c.state) or "").startswith("state filter")


# ------------------------------------------------------------------ end to end, no LLM
def test_end_to_end_pass_on_synthetic_bars_writes_the_artifact_and_queues_with_provenance(
        factory: XF.Factory, tmp_path: Path) -> None:
    from libs.moat import registry as R
    report = factory.run(14.0, symbols=list(META))
    assert report["status"] == "RAN" and report["dry_run"] is False
    paths = factory.paths
    assert paths.report.exists()
    doc = json.loads(paths.report.read_text("utf-8"))
    for key in ("population", "cheap_layer", "null_factory", "mutations", "credits", "campaign",
                "qd_archive", "families", "catalogue", "worlds", "migration", "registry"):
        assert key in doc, key
    assert doc["worlds"]["lockbox"]["AAA"]["status"] == "SEALED"
    assert doc["families"]["ledger"]["n_effective"] <= doc["families"]["ledger"]["n_raw"]
    assert doc["families"]["mirrored_to_trial_ledger"] is True
    assert doc["cheap_layer"]["passed"] + sum(doc["cheap_layer"]["rejected"].values()) > 0
    assert doc["population"]["parents_by_kind"]["alpha101"] >= 30
    assert doc["population"]["parents_transferred"] > 0
    assert sum(doc["mutations"]["by_move"].values()) == doc["cells"]["generated"]["mutation"]
    assert set(doc["mutations"]["by_move"]) <= {*XF.MOVES, "qd_state"}
    assert doc["mutations"]["trial_families_mutated"] > 0
    for name in ("trial_families", "archive", "seen", "parents", "state", "islands", "credits",
                 "campaign"):
        assert (paths.state_dir / f"{name}.json").exists(), name
    camp = doc["campaign"]["this_pass"]
    raised = sum(v for k, v in doc["cells"]["tier0"]["rejected"].items()
                 if k.startswith("evaluation raised"))
    assert camp["PROPOSED"] == doc["cheap_layer"]["passed"] + sum(
        doc["cheap_layer"]["rejected"].values()) + raised
    assert camp["PROPOSED"] <= doc["cells"]["tier0"]["evaluated"]
    assert camp["SCREENED"] == doc["cheap_layer"]["passed"]
    assert camp["QUEUED"] == doc["registry"]["queued"] + doc["registry"]["queued_existing"]
    assert camp["QUEUED"] >= 1, doc["cells"]
    assert camp["QUEUED"] == doc["cells"]["survivors"]
    rows = R.candidates(origin=None, limit=500)
    mine = [r for r in rows if r.get("generator") == XF.SOURCE]
    assert len(mine) == camp["QUEUED"]
    for r in mine:
        lineage = json.loads(r["lineage_json"])
        assert lineage["parent_genome"] and "mutation_chain" in lineage
        assert lineage["mutation_chain"][-1] in {*XF.MOVES, "transfer", "transfer_state",
                                                 "qd_state", "invent"}
        assert lineage["operator_credits"] and lineage["trial_family"]
        assert r["family"] == "formula" and r["status"] == "queued"
        assert r["department"] == "mathlab" and r["trial_family"]
        assert json.loads(r["params_json"])["expr"]
    assert doc["registry"]["cells"] == doc["cells"]["survivors"] + doc["cells"]["blocked_survivors"]
    klass = META["AAA"]["asset_class"].lower()          # the lake lower-cases the registry's class
    assert doc["qd_archive"]["cells_filled"] > 0 and doc["population"]["islands"][klass] > 0
    assert doc["migration"]["island"] == klass
    # a second factory on the same state finds the rows and the elites again
    again = XF.Factory(paths, lake=factory.lake, seed=8, registry=R)
    assert again.campaign.counts()["rows_by_state"].get("QUEUED", 0) == camp["QUEUED"]
    assert again.islands[klass]["elites"]
    assert again.credits.moves and again.families.families


def test_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.moat import registry as R
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup", raising=False)
    R.set_path(tmp_path / "alpha_registry.sqlite")
    paths = XF.Paths(tmp_path / "desk")
    lake = XF.Lake(paths, meta=META)
    lake.injected["AAA"] = _bars(3)
    fac = XF.Factory(paths, lake=lake, seed=1, dry_run=True, registry=R)
    report = fac.run(3.0, symbols=["AAA"])
    assert report["status"] == "RAN" and report["written"] == []
    assert not paths.report.exists() and not paths.state_dir.exists()


def test_main_accepts_once_and_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(XF, "free_phys_mb", lambda: XF.MIN_FREE_MB - 1)
    monkeypatch.setattr(XF, "DEFAULT_PATHS", XF.Paths(tmp_path / "desk"))
    assert XF.main(["--once", "--budget-s", "1", "--dry-run"]) == 0
    assert "STOOD_DOWN" in capsys.readouterr().out
