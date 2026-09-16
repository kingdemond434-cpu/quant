"""The intervention lab must move the right thing, in the right direction, at the right lag.

WHY EACH OF THESE EXISTS. `world_lab` is a HYPOTHESIS GENERATOR with zero authority, which makes
it tempting to test loosely -- nothing it says can size a position, so what is the harm. The harm
is that a simulator that is quietly wrong donates confident nonsense into the same docket every
honest proposer feeds, and every one of those cells spends the desk's shared family-wise error
budget. A lab nobody can check is worse than no lab.

So these pin the four things that were actually wrong during the build, each of which produced a
plausible-looking artifact:

  * PROPAGATION. do(X, +1) must arrive at Y at lag 1 with beta's sign and at Z at lag 2 with the
    product's sign -- not at lag 0, not with a lost sign through an `opposite` identity.
  * PARTICIPANTS ARE EDGE-TRIGGERED. Level-triggered, `vol_control` re-fired on every bar its
    condition held and reported -21.4 sigma off a +2 sigma shock. The cooldown is the fix and is
    pinned here, because the artifact looked entirely reasonable while it was broken.
  * RESIDUAL IS TOTAL MINUS DIRECT, exactly. It is the only quantity compared against cost, so a
    definition that drifted would change what gets donated without changing any headline.
  * THE DOOR. Only registered families, never a single-name equity, never an unclassified symbol.

Plus determinism under seed, UNMEASURED with no graph, and a --dry-run that writes and donates
nothing -- the three properties an hourly organ is trusted on.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

wl = pytest.importorskip("research.world_lab", reason="the lab ships with the desk")


# --------------------------------------------------------------------------------- fixtures
def _node(nid: str, kind: str = "mt5_instrument") -> dict[str, Any]:
    return {"id": nid, "kind": kind}


def _edge(src: str, dst: str, lag: int, strength: float, status: str = "ADMITTED",
          clock: str = "H1") -> dict[str, Any]:
    return {"src": src, "dst": dst, "lag": lag, "strength": strength, "status": status,
            "clock": clock, "direction": "opposite" if strength < 0 else "same", "n": 10_000,
            "evidence": {"xcorr": {"best": {"sd_boot": 0.0}}}}


def _write(path: Path, doc: dict[str, Any]) -> Path:
    path.write_text(json.dumps(doc), "utf-8")
    return path


def chain_graph(tmp: Path) -> Path:
    """X -> Y at lag 1 beta +0.5, Y -> Z at lag 1 beta -0.3. The whole arithmetic is checkable."""
    return _write(tmp / "graph.json", {
        "nodes": [_node("X"), _node("Y"), _node("Z")],
        "edges": [_edge("X", "Y", 1, 0.5), _edge("Y", "Z", 1, -0.3)]})


def desk_graph(tmp: Path) -> Path:
    """A graph in the desk's own vocabulary: an identity, two hypothesis-lane legs and an equity.

    `currency:USD -> USDX` is a lag-0 STRUCTURAL identity, so a shock declared on `currency:USD`
    must land on USDX; `currency:CAD -> USDCAD` is the OPPOSITE identity, which is where a lost
    sign would hide.
    """
    return _write(tmp / "desk.json", {
        "nodes": [_node("USDX"), _node("XAUUSD"), _node("XAGUSD"), _node("USDCAD"),
                  _node("Apple"), _node("NOTREAL"), _node("currency:USD", "currency"),
                  _node("currency:CAD", "currency")],
        "edges": [
            {"src": "currency:USD", "dst": "USDX", "lag": 0, "status": "STRUCTURAL",
             "direction": "same"},
            {"src": "currency:CAD", "dst": "USDCAD", "lag": 0, "status": "STRUCTURAL",
             "direction": "opposite"},
            _edge("USDX", "XAUUSD", 2, -0.40),
            _edge("USDX", "currency:CAD", 1, 0.35),
            _edge("XAUUSD", "XAGUSD", 1, 0.45),
            _edge("XAUUSD", "Apple", 1, 0.50),
            _edge("XAUUSD", "NOTREAL", 1, 0.50),
        ]})


def fake_bars(**over: float) -> Any:
    row = {"price": 100.0, "sigma_h1": 1e-3, "median_abs_daily": 1e-5}
    row.update(over)
    return lambda _sym: dict(row)


@pytest.fixture
def exact(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every source of randomness and spread so the arithmetic is exactly predictable."""
    monkeypatch.setattr(wl, "SHOCK_BARS", 1)
    monkeypatch.setattr(wl, "PARTICIPANT_SE", 0.0)
    monkeypatch.setattr(wl, "bar_stats", fake_bars())


def net_of(path: Path) -> Any:
    net = wl.load_network(path, Path("does-not-exist.json"))
    assert net is not None
    for e in net.edges:
        e.se = 0.0                       # the band is tested elsewhere; here beta must be exact
    return net


def lab_of(net: Any, table: dict[str, Any] | None = None, **kw: Any) -> Any:
    zero = dict.fromkeys(wl.DEFAULT_PARTICIPANTS, 0.0)
    default = {s: {k: {"value": v, "basis": "test"} for k, v in zero.items()}
               for s in net.instruments()}
    return wl.Lab(net, table if table is not None else default,
                  **{"draws": 4, "horizon": 8, "seed": 11, **kw})


# ------------------------------------------------------------------------------ propagation
def test_do_x_propagates_with_the_right_sign_and_lag(tmp_path: Path, exact: None) -> None:
    """+1 on X is +0.5 on Y one bar later and -0.15 on Z two bars later. Nothing arrives early."""
    net = net_of(chain_graph(tmp_path))
    lab = lab_of(net)
    z, _ = lab.simulate("X", 1.0, participants=False)
    iy, iz = net.index["Y"], net.index["Z"]
    assert z[:, iy, 0] == pytest.approx(0.0)
    assert z[:, iy, 1] == pytest.approx(0.5)
    assert z[:, iz, 1] == pytest.approx(0.0)
    assert z[:, iz, 2] == pytest.approx(-0.15)
    assert float(np.mean(z[:, iy, :].sum(axis=1))) > 0
    assert float(np.mean(z[:, iz, :].sum(axis=1))) < 0


def test_a_negative_shock_flips_every_leg(tmp_path: Path, exact: None) -> None:
    net = net_of(chain_graph(tmp_path))
    z, _ = lab_of(net).simulate("X", -2.0, participants=False)
    assert z[:, net.index["Y"], 1] == pytest.approx(-1.0)
    assert z[:, net.index["Z"], 2] == pytest.approx(0.3)


def test_an_opposite_identity_is_merged_and_keeps_its_sign(tmp_path: Path) -> None:
    """`currency:CAD -> USDCAD` opposite: an arc INTO the currency must reach USDCAD flipped.

    Identities are collapsed rather than propagated, and collapsing is exactly where a sign gets
    dropped -- silently, because the path still looks like a path.
    """
    net = net_of(desk_graph(tmp_path))
    assert net.alias["currency:USD"] == ("USDX", 1.0)
    assert net.alias["currency:CAD"] == ("USDCAD", -1.0)
    assert "currency:CAD" not in net.index and "USDCAD" in net.index
    arc = next(e for e in net.edges if e.src == "USDX" and e.dst == "USDCAD")
    assert arc.beta == pytest.approx(-0.35)          # +0.35 into CAD == -0.35 into USDCAD
    assert net.proxy_of("currency:USD") == ("USDX", 1.0)


def test_the_shock_is_a_day_not_a_bar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A macro shock is declared in DAILY sigma and cumulates to shock * sqrt(SHOCK_BARS)."""
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    net = net_of(chain_graph(tmp_path))
    z, _ = lab_of(net, horizon=40).simulate("X", 1.0, participants=False)
    assert float(np.mean(z[:, net.index["X"], :].sum(axis=1))) == pytest.approx(
        np.sqrt(wl.SHOCK_BARS), rel=1e-9)


def test_a_cycle_is_capped_rather_than_allowed_to_resonate(tmp_path: Path) -> None:
    """Two arcs whose loop gain exceeds one are scaled, and the scaling is COUNTED, not hidden."""
    path = _write(tmp_path / "cycle.json", {
        "nodes": [_node("X"), _node("Y")],
        "edges": [_edge("X", "Y", 1, 0.95), _edge("Y", "X", 1, 0.95)]})
    net = net_of(path)
    assert net.scaled_rows == 2
    for e in net.edges:
        assert abs(e.beta) <= wl.STABILITY_MAX + 1e-12
    z, _ = wl.Lab(net, {}, draws=2, horizon=60, seed=1).simulate("X", 1.0, participants=False)
    assert np.all(np.abs(z) <= wl.Z_CLIP)
    assert np.isfinite(z).all()


# ----------------------------------------------------------------------------- participants
def test_a_participant_response_modifies_the_path_as_specified(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               exact: None) -> None:
    """A CTA trigger adds its coefficient, signed by the move, at the bar the move clears it."""
    monkeypatch.setattr(wl, "CTA_TRIGGER_Z", 0.1)
    net = net_of(chain_graph(tmp_path))
    table = {s: {k: {"value": 0.0} for k in wl.DEFAULT_PARTICIPANTS}
             for s in net.instruments()}
    table["Y"]["cta_trigger"] = {"value": 0.4}
    lab = lab_of(net, table)
    base, _ = lab.simulate("X", 1.0, participants=False)
    z, contrib = lab.simulate("X", 1.0, participants=True)
    iy = net.index["Y"]
    assert base[:, iy, 2] == pytest.approx(0.0)
    assert z[:, iy, 2] == pytest.approx(0.4)          # cum = +0.5 at t=2, so it fires long
    assert contrib["cta_trigger"][:, lab.inst.index("Y")] == pytest.approx(0.4)


def test_an_operator_fires_once_per_episode_not_once_per_bar(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch,
                                                             exact: None) -> None:
    """THE BUG THIS PINS: level-triggered, the same decision was re-taken on every bar.

    The condition below holds from bar 2 to the end of the horizon. Edge-triggered it contributes
    0.4 once; level-triggered it contributed 0.4 x 7 and the artifact looked fine.
    """
    monkeypatch.setattr(wl, "CTA_TRIGGER_Z", 0.1)
    monkeypatch.setattr(wl, "FIRE_COOLDOWN", 48)
    net = net_of(chain_graph(tmp_path))
    table = {s: {k: {"value": 0.0} for k in wl.DEFAULT_PARTICIPANTS} for s in net.instruments()}
    table["Y"]["cta_trigger"] = {"value": 0.4}
    lab = lab_of(net, table, horizon=9)
    _z, contrib = lab.simulate("X", 1.0, participants=True)
    assert contrib["cta_trigger"][:, lab.inst.index("Y")] == pytest.approx(0.4)


def test_dealer_gamma_damps_a_large_bar(tmp_path: Path, exact: None) -> None:
    """A long-gamma dealer shrinks the bar; the shrink is recorded as that operator's own work."""
    net = net_of(chain_graph(tmp_path))
    table = {s: {k: {"value": 0.0} for k in wl.DEFAULT_PARTICIPANTS} for s in net.instruments()}
    table["Y"]["dealer_gamma"] = {"value": 0.5}
    lab = lab_of(net, table)
    z, contrib = lab.simulate("X", 2.0, participants=True)
    iy = net.index["Y"]
    assert 0.0 < float(np.mean(z[:, iy, 1])) < 1.0      # would be exactly 1.0 undamped
    assert float(np.mean(contrib["dealer_gamma"][:, lab.inst.index("Y")])) < 0.0


def test_participant_coefficients_declare_measured_or_prior(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch
                                                            ) -> None:
    """A stated prior must never be indistinguishable from a measured footprint."""
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    net = net_of(chain_graph(tmp_path))
    table, basis = wl.participant_table(net, {})
    assert "STATED PRIORS" in basis
    assert all(v["basis"] == "prior" for v in table["Y"].values())
    ecology = {"symbols": {"Y": {"vol_control": {"effect": -0.02},
                                 "dealer_gamma": {"effect": -0.5}}}}
    table, basis = wl.participant_table(net, ecology)
    assert basis.startswith("measured")
    assert table["Y"]["vol_control"]["basis"] == "measured"
    assert table["Y"]["vol_control"]["value"] < 0
    # pinned (negative distance) means dealers are LONG gamma, which DAMPS: a positive coefficient
    assert table["Y"]["dealer_gamma"]["value"] > 0
    assert table["Y"]["cta_trigger"]["basis"] == "prior"


# --------------------------------------------------------------------------------- residual
def _spec(nodes: list[str], shock: float = 1.0) -> dict[str, Any]:
    return {"shock": shock, "month_end": False, "nodes": nodes, "chain": "a test chain"}


def test_residual_is_exactly_total_minus_direct(tmp_path: Path, exact: None) -> None:
    """The only quantity measured against cost, and therefore the only one worth pinning hard."""
    net = net_of(chain_graph(tmp_path))
    lab = lab_of(net)
    got = wl.run_scenario(lab, _spec(["X"]), {})
    assert got["status"] == "OK" and got["trigger_node"] == "X"
    total, _ = lab.simulate("X", 1.0)
    direct, _ = lab.simulate("X", 1.0, edges=[e for e in net.edges if e.src == "X"],
                             participants=False)
    for row in got["effects"]:
        i = net.index[row["instrument"]]
        want = float(np.mean(total[:, i, :].sum(axis=1) - direct[:, i, :].sum(axis=1)))
        assert row["residual_sigma"] == pytest.approx(want, abs=5e-7)


def test_an_instrument_the_graph_is_silent_about_keeps_its_whole_effect(tmp_path: Path,
                                                                       exact: None) -> None:
    """Z has no DIRECT arc from X, so its direct prediction is zero and residual == total.

    Y does have one, so its residual is only what the chain and the participants added.
    """
    net = net_of(chain_graph(tmp_path))
    got = wl.run_scenario(lab_of(net), _spec(["X"]), {})
    rows = {r["instrument"]: r for r in got["effects"]}
    assert rows["Z"]["graph_speaks"] is False
    assert rows["Z"]["residual_sigma"] == pytest.approx(rows["Z"]["expected_move_sigma"])
    assert rows["Y"]["graph_speaks"] is True
    assert rows["Y"]["residual_sigma"] == pytest.approx(0.0, abs=1e-9)
    d = got["disagreement_with_observational"]
    assert d["n_instruments"] == 2 and d["n_where_graph_speaks"] == 1 and d["n_silent"] == 1
    assert d["max_abs_sigma"] >= d["mean_abs_sigma"] > 0


def test_actionable_needs_the_residual_to_clear_the_round_trip(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               exact: None) -> None:
    net = net_of(chain_graph(tmp_path))
    cheap = wl.run_scenario(lab_of(net), _spec(["X"]), {})
    assert any(r["actionable"] for r in cheap["effects"])
    monkeypatch.setattr(wl, "bar_stats", fake_bars(median_abs_daily=10.0))
    dear = wl.run_scenario(lab_of(net), _spec(["X"]), {})
    assert not any(r["actionable"] for r in dear["effects"])
    assert all(r["cost"] > abs(r["residual"]) for r in dear["effects"])


def test_no_bars_means_null_and_never_actionable(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """UNMEASURED is a verdict (L1.28a). A missing price scale is not a zero effect."""
    monkeypatch.setattr(wl, "bar_stats", lambda _s: None)
    net = net_of(chain_graph(tmp_path))
    got = wl.run_scenario(lab_of(net), _spec(["X"]), {})
    for row in got["effects"]:
        assert row["expected_move"] is None and row["residual"] is None
        assert row["band"] is None and row["cost"] is None and row["actionable"] is None
        assert row["expected_move_sigma"] is not None


# -------------------------------------------------------------------------------- scenarios
def test_the_scenario_library_runs_and_names_what_it_could_not(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch
                                                               ) -> None:
    monkeypatch.setattr(wl, "GRAPH", desk_graph(tmp_path))
    monkeypatch.setattr(wl, "CAUSAL_LAB", tmp_path / "absent.json")
    monkeypatch.setattr(wl, "ECOLOGY", tmp_path / "absent.json")
    monkeypatch.setattr(wl, "COST_SURFACE", tmp_path / "absent.json")
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    doc = wl.build(seed=3, draws=8, horizon=12, limit=0)
    assert doc["status"] == "OK"
    assert set(doc["scenarios"]) == set(wl.SCENARIOS)
    assert doc["authority"].startswith("ZERO")
    ok = [n for n, s in doc["scenarios"].items() if s["status"] == "OK"]
    assert "usd_shock" in ok
    for name, sc in doc["scenarios"].items():
        assert sc["chain"], name
        if sc["status"] == "OK":
            assert sc["trigger_node"]
            assert sc["trigger_requested"] == wl.SCENARIOS[name]["nodes"][0]
            assert set(sc["disagreement_with_observational"]) >= {
                "mean_abs_sigma", "n_instruments", "n_where_graph_speaks", "n_silent", "top"}
        else:
            assert sc["why"] and any(u["what"] == f"scenario {name}" for u in doc["unmeasured"])


def test_a_trigger_that_reaches_no_price_is_stepped_over_and_recorded(tmp_path: Path,
                                                                      monkeypatch:
                                                                      pytest.MonkeyPatch) -> None:
    """`event:US_CPI` has no outgoing arc here, so the ladder moves on -- and SAYS it moved on."""
    doc = json.loads(desk_graph(tmp_path).read_text("utf-8"))
    doc["nodes"].append({"id": "event:US_CPI", "kind": "event"})
    path = _write(tmp_path / "ladder.json", doc)
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    net = net_of(path)
    assert wl.reaches_instrument(net, "event:US_CPI", 240) is False
    assert wl.reaches_instrument(net, "USDX", 240) is True
    node, wanted = wl.resolve_trigger(net, wl.SCENARIOS["cpi_surprise"]["nodes"], 240)
    assert wanted == "event:US_CPI" and node == "USDX"
    got = wl.run_scenario(lab_of(net, horizon=12), wl.SCENARIOS["cpi_surprise"], {})
    assert got["trigger_requested"] == "event:US_CPI" and got["trigger_node"] == "USDX"


def test_the_recorded_fallback_is_shrunk_and_declared(tmp_path: Path) -> None:
    """Nothing admitted: the lab may still explore, at half weight, and must say so loudly."""
    path = _write(tmp_path / "rec.json", {
        "nodes": [_node("X"), _node("Y")],
        "edges": [_edge("X", "Y", 1, 0.4, status="RECORDED_NOT_ADMITTED")]})
    net = net_of(path)
    assert net.basis.startswith("recorded_not_admitted")
    assert net.edges[0].beta == pytest.approx(0.4 * wl.RECORDED_SHRINK)
    assert net.notes and "ADMITS 0 arcs" in net.notes[0]


def test_causal_lab_is_read_tolerantly(tmp_path: Path) -> None:
    """Another seat owns that schema. A row it cannot parse is skipped, never fatal."""
    lab_doc = _write(tmp_path / "CAUSAL_LAB.json", {"edges": [
        {"src": "X", "dst": "Z", "lag": 3, "klass": "CONFIRMED_CAUSAL", "beta": 0.2},
        {"src": "X", "dst": "Z", "lag": 1, "klass": "SPURIOUS", "beta": 0.9},
        {"src": "nope", "dst": "Z", "klass": "CAUSAL", "beta": 0.9}, "junk", {}]})
    net = wl.load_network(chain_graph(tmp_path), lab_doc)
    assert net is not None and "causal_lab" in net.basis
    arcs = [e for e in net.edges if e.basis == "causal_lab"]
    assert [(e.src, e.dst, e.lag, round(e.beta, 3)) for e in arcs] == [("X", "Z", 3, 0.2)]


# ------------------------------------------------------------------------------- the door
def _donating_doc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(wl, "GRAPH", desk_graph(tmp_path))
    for name in ("CAUSAL_LAB", "ECOLOGY", "COST_SURFACE"):
        monkeypatch.setattr(wl, name, tmp_path / "absent.json")
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    return wl.build(seed=5, draws=8, horizon=16, limit=20, only="usd_shock")


def test_only_registered_families_and_never_a_single_name_equity(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch
                                                                 ) -> None:
    """The docket's door, tested at the door: Apple is reachable, actionable, and refused."""
    doc = _donating_doc(tmp_path, monkeypatch)
    known = wl.registered_families()
    assert {"macro_conditional", "event_reaction", "lead_lag"} <= known
    assert doc["hypotheses"], "the fixture is meant to produce donatable rows"
    for row in doc["hypotheses"]:
        assert row["family"] in known
        assert row["symbol"] not in ("Apple", "NOTREAL")
        assert row["timeframe"] == "H1"
        assert row["source"].startswith("world_lab:")
        assert row["trigger"]["node"] and row["trigger"]["lag"] >= 1
        assert "SYNTHETIC" in row["why"]
        assert row["evidence"]["authority"] == "ZERO -- synthetic"
    refused = {r["symbol"]: r["why"] for r in doc["refused"]}
    assert "two-lane mandate" in refused.get("Apple", "")
    assert "NOTREAL" in refused, "an UNCLASSIFIED symbol is not permitted by its absence"


def test_every_donated_param_is_one_the_family_actually_takes(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch
                                                             ) -> None:
    """`family_call` splats `params` into the family as kwargs, so a stray key is a TypeError.

    THIS IS WHY THE TRIGGER LIVES ON `trigger` AND NOT IN `params`. The first build put
    `trigger_node` and `shock_sigma` in there because the brief asked the params to name the
    trigger; the rows compiled to EXACT_RECIPE and would have died at the backtest. What the
    family knows the trigger by -- `driver_symbol` for `lead_lag` -- still rides in `params`.
    """
    import inspect

    from mt5desk import families as fam_mod
    from mt5desk import families_orthogonal as fo

    doc = _donating_doc(tmp_path, monkeypatch)
    assert doc["hypotheses"]
    for row in doc["hypotheses"]:
        entry: Any = fo.ORTHOGONAL_FAMILIES.get(row["family"])
        if entry is None:
            entry = fam_mod.FAMILY_REGISTRY.get(row["family"])
            entry = entry.get("func") if isinstance(entry, dict) else entry
        assert callable(entry), row["family"]
        allowed = set(inspect.signature(entry).parameters)
        assert set(row["params"]) <= allowed, (row["family"], set(row["params"]) - allowed)
        assert row["params"], "a cell with no parameters is not a recipe"
    lead = [r for r in doc["hypotheses"] if r["family"] == "lead_lag"]
    assert lead and all(r["params"]["driver_symbol"] == r["trigger"]["node"] for r in lead)


def test_an_unclassified_trigger_falls_back_to_the_macro_family(tmp_path: Path) -> None:
    """A trigger that prices nothing is a macro axis, not a driver series."""
    net = net_of(desk_graph(tmp_path))
    assert wl.family_for(net, "USDX", "XAUUSD") == ("lead_lag", "USDX")
    assert wl.family_for(net, "USDX", "USDX") == (wl.FALLBACK_FAMILY, "")
    assert wl.family_params("macro_conditional", {"driver_symbol": "X", "regime_high": 0.6}) == {
        "regime_high": 0.6}


def test_an_unregistered_family_is_refused_rather_than_donated(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch
                                                               ) -> None:
    doc = _donating_doc(tmp_path, monkeypatch)
    net = net_of(desk_graph(tmp_path))
    rows, refused = wl.hypotheses(net, doc["scenarios"], {"nothing_real"}, 20)
    assert rows == []
    assert any("no such family is registered" in r["why"] for r in refused)


def test_donate_is_handed_the_rows_and_the_seat(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """A full CLI pass, with `donate` captured: the seat is `world_lab`, the scenario is the row's.

    The seat is deliberately NOT `world_lab:<scenario>` -- that becomes a directory name, and a
    colon is not a legal path character on the box that trades.
    """
    seen: dict[str, Any] = {}

    def capture(source: str, rows: list[dict[str, Any]], tests_run: int) -> None:
        seen.update({"source": source, "rows": rows, "tests_run": tests_run})

    import research.proposer_common as pc
    monkeypatch.setattr(pc, "donate", capture)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(seen.get("rows") or [])})
    monkeypatch.setattr(wl, "GRAPH", desk_graph(tmp_path))
    for name in ("CAUSAL_LAB", "ECOLOGY", "COST_SURFACE"):
        monkeypatch.setattr(wl, name, tmp_path / "absent.json")
    monkeypatch.setattr(wl, "OUT", tmp_path / "WORLD_LAB.json")
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    assert wl.main(["--seed", "5", "--draws", "8", "--horizon", "16",
                    "--scenario", "usd_shock"]) == 0
    assert seen["source"] == "world_lab"
    assert seen["rows"] and all(r["source"].startswith("world_lab:") for r in seen["rows"])
    out = json.loads((tmp_path / "WORLD_LAB.json").read_text("utf-8"))
    assert out["donated"] == len(seen["rows"])
    assert set(out) >= {"at", "n_nodes", "n_edges", "scenarios", "donated", "unmeasured",
                        "authority", "rule"}


def test_one_question_is_charged_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two scenarios whose ladder lands on the same node must not buy the cell twice."""
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    net = net_of(desk_graph(tmp_path))
    lab = lab_of(net, wl.participant_table(net, {})[0], horizon=16)
    one = wl.run_scenario(lab, _spec(["USDX"], 1.5), {})
    assert any(r["actionable"] for r in one["effects"]), "the fixture must produce a donation"
    rows, refused = wl.hypotheses(net, {"a": one, "b": dict(one)}, wl.registered_families(), 20)
    cells = [(r["symbol"], r["family"], r["trigger"]["lag"]) for r in rows]
    assert len(cells) == len(set(cells))
    assert any("shared trial budget" in r["why"] for r in refused)


def test_max_donations_is_a_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = _donating_doc(tmp_path, monkeypatch)
    net = net_of(desk_graph(tmp_path))
    rows, _ = wl.hypotheses(net, doc["scenarios"], wl.registered_families(), 1)
    assert len(rows) <= 1


# -------------------------------------------------------------------- determinism and safety
def test_the_same_seed_gives_the_same_lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                          ) -> None:
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    net = net_of(chain_graph(tmp_path))
    table, _ = wl.participant_table(net, {})
    a, _ = wl.Lab(net, table, draws=16, horizon=10, seed=99).simulate("X", 1.0)
    b, _ = wl.Lab(net, table, draws=16, horizon=10, seed=99).simulate("X", 1.0)
    c, _ = wl.Lab(net, table, draws=16, horizon=10, seed=100).simulate("X", 1.0)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_the_whole_build_is_reproducible_under_a_seed(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wl, "GRAPH", desk_graph(tmp_path))
    for name in ("CAUSAL_LAB", "ECOLOGY", "COST_SURFACE"):
        monkeypatch.setattr(wl, name, tmp_path / "absent.json")
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    one = wl.build(seed=7, draws=8, horizon=12, limit=5, only="usd_shock")
    two = wl.build(seed=7, draws=8, horizon=12, limit=5, only="usd_shock")
    assert json.dumps(one["scenarios"], sort_keys=True) == json.dumps(two["scenarios"],
                                                                     sort_keys=True)
    assert [r["title"] for r in one["hypotheses"]] == [r["title"] for r in two["hypotheses"]]


def test_a_band_widens_with_the_edge_uncertainty(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """The Monte Carlo must actually be doing something: a wider sd_boot is a wider band."""
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    doc = json.loads(chain_graph(tmp_path).read_text("utf-8"))
    for e in doc["edges"]:
        e["evidence"]["xcorr"]["best"]["sd_boot"] = 0.20
    net = wl.load_network(_write(tmp_path / "wide.json", doc), tmp_path / "absent.json")
    assert net is not None
    got = wl.run_scenario(wl.Lab(net, {}, draws=200, horizon=8, seed=4), _spec(["X"]), {})
    for row in got["effects"]:
        low, high = row["band"]
        assert low < row["expected_move"] < high


def test_unmeasured_without_a_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No graph is a VERDICT, not a crash and not an empty success."""
    monkeypatch.setattr(wl, "GRAPH", tmp_path / "nothing-here.json")
    doc = wl.build(draws=4, horizon=6)
    assert doc["status"] == "UNMEASURED"
    assert doc["n_nodes"] == 0 and doc["n_edges"] == 0 and doc["donated"] == 0
    assert doc["scenarios"] == {}
    assert doc["unmeasured"] and "no readable causal graph" in doc["unmeasured"][0]["why"]
    assert doc["authority"].startswith("ZERO")


def test_a_malformed_graph_is_unmeasured_not_an_exception(tmp_path: Path) -> None:
    for payload in ('{"nodes": [], "edges": []}', "{}", "not json at all"):
        path = tmp_path / "bad.json"
        path.write_text(payload, "utf-8")
        assert wl.load_network(path, tmp_path / "absent.json") is None


def test_dry_run_writes_nothing_and_donates_nothing(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_a: Any, **_k: Any) -> None:
        raise AssertionError("--dry-run must never donate")

    import research.proposer_common as pc
    monkeypatch.setattr(pc, "donate", refuse)
    monkeypatch.setattr(wl, "GRAPH", desk_graph(tmp_path))
    for name in ("CAUSAL_LAB", "ECOLOGY", "COST_SURFACE"):
        monkeypatch.setattr(wl, name, tmp_path / "absent.json")
    out = tmp_path / "WORLD_LAB.json"
    monkeypatch.setattr(wl, "OUT", out)
    monkeypatch.setattr(wl, "bar_stats", fake_bars())
    assert wl.main(["--dry-run", "--draws", "8", "--horizon", "12",
                    "--scenario", "usd_shock"]) == 0
    assert not out.exists()
