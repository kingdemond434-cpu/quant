"""THE PER-(METHOD, DOMAIN) YIELD TABLE, BUILT OVER A SYNTHETIC DESK WHOSE EVERY CELL IS PLANTED.

The thing this organ can get wrong is not a crash, it is a plausible number. A raw ratio at n=1
says 100%, an untested cell reported as 0 says "this method does not work here" when the desk has
never asked, and a cost column divided by the wrong denominator reorders the whole table. So the
lineage log, the docket, the registry and the compute ledger are all written under tmp_path with
KNOWN counts, and every test asserts the table recovered THAT cell.

The four properties that matter, each pinned by its own test:
  n=0 posts the prior EXACTLY and is labelled PRIOR -- never 0, never a division;
  n large posts the empirical rate, because shrinkage that never lets go is a different lie;
  a measured 20-in-100 outranks a one-hit-at-n=1, which is precisely what a ratio cannot do;
  every cell keeps a strictly positive weight, because this organ ranks and may never veto.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import engine_registry as er  # noqa: E402

#: The synthetic broker registry: two hypothesis-lane classes so a domain split is observable.
REGISTRY = {"EURUSD": {"asset_class": "forex"}, "GBPUSD": {"asset_class": "forex"},
            "AUDUSD": {"asset_class": "forex"}, "XAUUSD": {"asset_class": "metals"},
            "XAGUSD": {"asset_class": "metals"}}


def _graph_row(source: str, symbol: str, fate: str, family: str = "carry") -> dict[str, Any]:
    return {"id": f"{source}{symbol}{fate}{family}", "symbol": symbol, "family": family,
            "params": {}, "source": source, "parent": "", "fate": fate, "why": "planted",
            "gates": {}, "at": "2026-09-22T00:00:00+00:00", "region": ""}


def _plant(tmp: Path, rows: list[dict[str, Any]], *, docket: list[dict[str, Any]] | None = None,
           ledger: list[dict[str, Any]] | None = None) -> None:
    graph = tmp / "hypothesis_graph.jsonl"
    graph.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    er.GRAPH = graph
    dock = tmp / "external_survivors.json"
    dock.write_text(json.dumps(docket or []), "utf-8")
    er.DOCKET = dock
    comp = tmp / "compute_ledger.jsonl"
    comp.write_text("".join(json.dumps(r) + "\n" for r in (ledger or [])), "utf-8")
    er.COMPUTE = comp
    er.REGISTRY_DB = tmp / "absent_registry.sqlite"
    er.SOURCE_REG = tmp / "absent_source_registry.json"
    er.SEAT_ROOTS = (tmp / "no_seats_a", tmp / "no_seats_b")
    er.REPORT = tmp / "reports" / "ENGINE_REGISTRY.json"


@pytest.fixture(autouse=True)
def _desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A synthetic desk. Every module path is redirected; nothing tracked is ever written."""
    universe = tmp_path / "universe.json"
    universe.write_text(json.dumps(REGISTRY), "utf-8")
    from research import universe_policy as up
    monkeypatch.setattr(up, "UNIVERSE", universe)
    up._registry.cache_clear()
    er._AC_CACHE.clear()
    for name in ("GRAPH", "DOCKET", "COMPUTE", "REGISTRY_DB", "SOURCE_REG", "SEAT_ROOTS",
                 "REPORT"):
        monkeypatch.setattr(er, name, getattr(er, name), raising=True)
    _plant(tmp_path, [])
    yield
    up._registry.cache_clear()
    er._AC_CACHE.clear()


# ------------------------------------------------------------------ the posterior behaves
def test_no_trials_posts_the_prior_exactly_and_says_so() -> None:
    """n=0 is UNMEASURED, and UNMEASURED reports the prior -- never 0 (L1.28a)."""
    post = er.posterior(0, 0, 0.2, 9.8)
    assert post["basis"] == "PRIOR"
    assert post["p_mean"] == pytest.approx(0.2 / 10.0, abs=1e-9)
    assert post["raw_ratio"] is None
    assert post["p_mean"] > 0.0


def test_large_n_converges_on_the_empirical_rate() -> None:
    """Shrinkage that never lets go is its own lie: at n=10,000 the prior must be invisible."""
    post = er.posterior(2000, 10_000, 0.2, 9.8)
    assert post["basis"] == "MEASURED"
    assert post["p_mean"] == pytest.approx(0.2, abs=2e-3)
    assert post["ci"][0] < 0.2 < post["ci"][1]
    # and the interval must have TIGHTENED relative to a thin cell at the same rate
    thin = er.posterior(2, 10, 0.2, 9.8)
    assert (post["ci"][1] - post["ci"][0]) < (thin["ci"][1] - thin["ci"][0])


def test_credible_interval_is_a_real_beta_interval() -> None:
    """The pure-python incomplete beta must actually be the Beta CDF, or every interval is decor."""
    assert er.betainc(2.0, 5.0, 0.0) == 0.0
    assert er.betainc(2.0, 5.0, 1.0) == 1.0
    assert er.betainc(1.0, 1.0, 0.37) == pytest.approx(0.37, abs=1e-9)   # uniform
    q = er.beta_quantile(3.0, 7.0, 0.5)
    assert er.betainc(3.0, 7.0, q) == pytest.approx(0.5, abs=1e-6)
    post = er.posterior(5, 10, 0.5, 0.5)
    assert post["ci"][0] < post["p_mean"] < post["ci"][1]


def test_a_measured_cell_outranks_a_noisy_one_hit() -> None:
    """THE WHOLE REASON THIS IS NOT A RATIO. 1-of-1 reads as 100% and must not win."""
    pooled = 0.02
    a0, b0 = er.PRIOR_STRENGTH * pooled, er.PRIOR_STRENGTH * (1 - pooled)
    measured = er.posterior(20, 100, a0, b0)
    one_hit = er.posterior(1, 1, a0, b0)
    assert one_hit["raw_ratio"] == 1.0                      # the ratio really does say 100%
    assert measured["p_mean"] > one_hit["p_mean"]
    assert one_hit["basis"] == "THIN"


# ------------------------------------------------------------------ the table is measured
def test_the_planted_cells_are_recovered_with_their_counts(tmp_path: Path) -> None:
    """A method that certifies in forex and one that never has must not share a row."""
    rows = ([_graph_row("miner:good", "EURUSD", "CERTIFIED") for _ in range(8)]
            + [_graph_row("miner:good", "GBPUSD", "FAILED") for _ in range(92)]
            + [_graph_row("miner:quiet", "XAUUSD", "BORN") for _ in range(30)])
    for i, r in enumerate(rows):
        r["id"] = f"r{i}"
    _plant(tmp_path, rows)
    rep = er.build(budget_s=30.0)
    cells = {c["cell"]: c for c in rep["cells"]}

    good_fx = cells["miner:good|forex"]
    assert good_fx["n_proposed"] == 100
    assert good_fx["n_tested"] == 100
    assert good_fx["n_certified"] == 8
    assert good_fx["p_certified"]["basis"] == "MEASURED"

    quiet = cells["miner:quiet|metals"]
    assert quiet["n_proposed"] == 30
    assert quiet["n_tested"] == 0 and quiet["n_certified"] == 0
    assert quiet["p_certified"]["basis"] == "PRIOR"
    assert quiet["verdict"].startswith("UNMEASURED")
    # UNMEASURED IS NOT ZERO. The untested cell reports the pooled prior, not a verdict of no.
    assert quiet["p_certified"]["p_mean"] == pytest.approx(rep["prior"]["pooled_p"], abs=1e-8)
    assert rep["totals"] == {"n_proposed": 130, "n_compiled": 0, "n_tested": 100,
                             "n_certified": 8}


def test_the_domain_really_is_the_asset_class(tmp_path: Path) -> None:
    """One method, two asset classes, two cells -- an engine that works in FX is not thereby
    an engine that works in metals, and a single pooled row would hide exactly that."""
    rows = ([_graph_row("miner:split", "EURUSD", "CERTIFIED") for _ in range(10)]
            + [_graph_row("miner:split", "XAUUSD", "FAILED") for _ in range(10)])
    for i, r in enumerate(rows):
        r["id"] = f"s{i}"
    _plant(tmp_path, rows)
    rep = er.build(budget_s=30.0)
    cells = {c["cell"]: c for c in rep["cells"]}
    assert cells["miner:split|forex"]["n_certified"] == 10
    assert cells["miner:split|metals"]["n_certified"] == 0
    assert (cells["miner:split|forex"]["p_certified"]["p_mean"]
            > cells["miner:split|metals"]["p_certified"]["p_mean"])


def test_the_docket_splits_the_external_label_into_real_methods(tmp_path: Path) -> None:
    """30,000 lineage rows under one label `external` is not a measurement of any method. The
    docket knows which sweep produced each (symbol, family) and the finer name must win."""
    rows = [_graph_row("external", "EURUSD", "CERTIFIED", family="gap"),
            _graph_row("external", "GBPUSD", "FAILED", family="carry")]
    rows[0]["id"], rows[1]["id"] = "d0", "d1"
    docket = [{"symbol": "EURUSD", "family": "gap", "source": "orthogonal_sweep:gap"},
              {"symbol": "GBPUSD", "family": "carry", "source": "edge_search:hour"}]
    _plant(tmp_path, rows, docket=docket)
    rep = er.build(budget_s=30.0)
    names = {c["method"] for c in rep["cells"]}
    assert "orthogonal_sweep:gap" in names and "edge_search:hour" in names
    assert "external" not in names


def test_cost_comes_from_the_compute_ledger_and_absence_is_unmeasured(tmp_path: Path) -> None:
    """A cost invented for a method the ledger cannot price is worse than no cost at all."""
    rows = [_graph_row("edge_search:hour", "EURUSD", "FAILED") for _ in range(10)]
    rows += [_graph_row("nobody_knows_this", "EURUSD", "FAILED") for _ in range(10)]
    for i, r in enumerate(rows):
        r["id"] = f"c{i}"
    _plant(tmp_path, rows, ledger=[{"run": "search", "wall_s": 20.0}])
    rep = er.build(budget_s=30.0)
    cells = {c["cell"]: c for c in rep["cells"]}
    priced = cells["edge_search:hour|forex"]
    assert priced["cost_s_per_proposal"] == pytest.approx(2.0)        # 20s over 10 proposals
    assert "compute ledger" in priced["cost_basis"]
    assert priced["expected_yield_per_compute_hour"] is not None

    unpriced = cells["nobody_knows_this|forex"]
    assert unpriced["cost_s_per_proposal"] is None
    assert unpriced["cost_basis"].startswith("UNMEASURED")
    assert unpriced["expected_yield_per_compute_hour"] is None
    assert unpriced["yield_basis"] == "UNMEASURED"


def test_expected_yield_per_compute_hour_is_rate_over_cost(tmp_path: Path) -> None:
    """The arithmetic the whole ranking rests on, pinned once."""
    rows = [_graph_row("edge_search:hour", "EURUSD", "CERTIFIED") for _ in range(50)]
    rows += [_graph_row("edge_search:hour", "GBPUSD", "FAILED") for _ in range(50)]
    for i, r in enumerate(rows):
        r["id"] = f"y{i}"
    _plant(tmp_path, rows, ledger=[{"run": "search", "wall_s": 100.0}])
    rep = er.build(budget_s=30.0)
    for cell in rep["cells"]:
        if cell["expected_yield_per_compute_hour"] is None:
            continue
        expect = cell["p_certified"]["p_mean"] * 3600.0 / cell["cost_s_per_proposal"]
        assert cell["expected_yield_per_compute_hour"] == pytest.approx(expect, rel=1e-6)


# ------------------------------------------------------------------ the weights never veto
def test_every_cell_keeps_a_positive_weight_and_the_vector_is_normalised(tmp_path: Path) -> None:
    """THIS ORGAN RANKS AND MAY NEVER VETO. A zero weight is a defunding decision, and the desk
    does not reduce its own aggressiveness on a table of counts."""
    rows = ([_graph_row("miner:good", "EURUSD", "CERTIFIED") for _ in range(5)]
            + [_graph_row("miner:good", "EURUSD", "FAILED") for _ in range(95)]
            + [_graph_row("miner:dud", "GBPUSD", "FAILED") for _ in range(200)]
            + [_graph_row("miner:new", "XAUUSD", "BORN") for _ in range(3)])
    for i, r in enumerate(rows):
        r["id"] = f"w{i}"
    _plant(tmp_path, rows, ledger=[{"run": "mine", "wall_s": 50.0}])
    rep = er.build(budget_s=30.0)
    weights = rep["weights"]
    assert weights, "a table with cells must publish weights"
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert all(v > 0.0 for v in weights.values()), "no cell may be weighted to zero"
    # the never-tested cell is funded BECAUSE it is unmeasured, not in spite of it
    assert rep["exploration"]["regime"] == "YIELD_AND_EXPLORATION"
    assert weights["miner:new|metals"] > 0.0
    # and the certifying method outranks the one that never has, at equal cost
    assert weights["miner:good|forex"] > weights["miner:dud|forex"]


def test_with_nothing_judged_the_whole_vector_is_exploration(tmp_path: Path) -> None:
    """A desk that has certified nothing yet has no yield to follow, and saying so beats
    inventing a ranking out of a prior it shares with every other cell."""
    rows = [_graph_row("miner:a", "EURUSD", "BORN"), _graph_row("miner:b", "XAUUSD", "BORN")]
    rows[0]["id"], rows[1]["id"] = "p0", "p1"
    _plant(tmp_path, rows)
    rep = er.build(budget_s=30.0)
    assert rep["exploration"]["regime"] == "PRIOR_ONLY"
    assert sum(rep["weights"].values()) == pytest.approx(1.0, abs=1e-6)
    assert all(v > 0.0 for v in rep["weights"].values())


def test_shares_are_keyed_by_leg_and_normalised(tmp_path: Path) -> None:
    """`research_budget` reads a `shares` block keyed by leg. Publishing one in any other shape
    is publishing a number nobody can spend."""
    rows = ([_graph_row("edge_search:hour", "EURUSD", "CERTIFIED") for _ in range(4)]
            + [_graph_row("edge_search:hour", "EURUSD", "FAILED") for _ in range(6)]
            + [_graph_row("miner:x", "XAUUSD", "FAILED") for _ in range(10)])
    for i, r in enumerate(rows):
        r["id"] = f"l{i}"
    _plant(tmp_path, rows, ledger=[{"run": "search", "wall_s": 10.0},
                                   {"run": "mine", "wall_s": 10.0}])
    rep = er.build(budget_s=30.0)
    assert set(rep["shares"]) <= {"search", "mine", "maintain_miners", "sweep", "merge_docket",
                                  "deepen", "compile_candidates", "moat_miner", "deep_forest",
                                  "world_crawler", "causal_graph"}
    assert sum(rep["shares"].values()) == pytest.approx(1.0, abs=1e-6)
    assert rep["shares"]["search"] > 0.0


# ------------------------------------------------------------------ absence is a verdict
def test_every_missing_input_is_named_not_crashed(tmp_path: Path) -> None:
    """An organ that dies on a missing artifact publishes nothing; one that invents a number
    publishes a lie. It must publish the absence."""
    er.GRAPH = tmp_path / "nope.jsonl"
    er.DOCKET = tmp_path / "nope.json"
    er.COMPUTE = tmp_path / "nope2.jsonl"
    rep = er.build(budget_s=10.0)
    assert rep["sources"]["hypothesis_graph"]["status"] == "absent"
    assert "not on disk" in rep["sources"]["hypothesis_graph"]["why"]
    assert rep["sources"]["docket"]["status"] == "absent"
    assert rep["n_cells"] == 0
    assert rep["exploration"]["regime"] == "EMPTY"


def test_corrupt_lineage_lines_are_counted_not_fatal(tmp_path: Path) -> None:
    graph = tmp_path / "hypothesis_graph.jsonl"
    graph.write_text('{"broken\n' + json.dumps(_graph_row("miner:ok", "EURUSD", "FAILED")) + "\n",
                     "utf-8")
    er.GRAPH = graph
    rep = er.build(budget_s=10.0)
    assert rep["sources"]["hypothesis_graph"]["status"] == "present"
    assert "1 unparseable" in rep["sources"]["hypothesis_graph"]["why"]
    assert rep["totals"]["n_proposed"] == 1


def test_the_row_budget_is_derived_never_hard_coded() -> None:
    n, why = er.row_budget()
    assert n >= er.MIN_ROWS
    assert "available" in why or "floor" in why


# ------------------------------------------------------------------ the cli contract
def test_dry_run_writes_nothing_and_a_real_run_writes_the_artifact(tmp_path: Path) -> None:
    rows = [_graph_row("miner:ok", "EURUSD", "FAILED")]
    _plant(tmp_path, rows)
    out = tmp_path / "reports" / "ENGINE_REGISTRY.json"
    assert er.main(["--once", "--budget-s", "20", "--dry-run"]) == 0
    assert not out.exists(), "--dry-run must write nothing at all"
    assert er.main(["--once", "--budget-s", "20"]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["organ"] == "engine_registry"
    assert doc["rule"] == er.RULE
    assert doc["prior"]["strength_pseudo_trials"] == er.PRIOR_STRENGTH
    assert "growth_governance" in doc


# ------------------------------------------------------------------ the consumer reads it
def test_research_budget_reads_the_shares_and_only_ever_adds(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    """THE CONSUMER, PINNED. `research_budget._engine_factor` is the one thing that spends this
    table, and it must be ONE-SIDED.

    Measured 2026-09-23 and the reason the floor is 1.0: clipped to [0.5, 2.0] like the file's
    other factors, `deepen` came back at x0.50 and 600s became 470s. Nothing claims the freed
    seconds, so that is a research shrink by fiat -- which no session may do. A leg the table
    prices above the equal share may be funded above par; one priced below runs at par.
    """
    from research import research_budget as rb
    art = tmp_path / "ENGINE_REGISTRY.json"
    art.write_text(json.dumps({"shares": {"rich": 0.8, "poor": 0.1, "mid": 0.1}}), "utf-8")
    monkeypatch.setattr(rb, "ENGINE", art)

    rich, why_rich = rb._engine_factor("rich")
    poor, why_poor = rb._engine_factor("poor")
    absent, why_absent = rb._engine_factor("not_on_the_table")
    assert rich > 1.0 and "x2.40" in why_rich          # 0.8 against an equal share of 1/3
    assert poor == 1.0, why_poor                       # priced low -> par, never below
    assert absent == 1.0 and "par" in why_absent
    assert rich <= rb.ENGINE_CEIL and rb.ENGINE_FLOOR == 1.0


def test_research_budget_is_unchanged_when_the_table_is_absent(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch
                                                               ) -> None:
    from research import research_budget as rb
    monkeypatch.setattr(rb, "ENGINE", tmp_path / "nothing_here.json")
    factor, why = rb._engine_factor("deepen")
    assert factor == 1.0 and "par" in why
