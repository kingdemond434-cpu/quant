"""Cross-section breadth: the properties that decide whether the number can be believed.

Three things are load-bearing here and each has bitten this desk before, so each is pinned:

  1. THE BLOCKED PATH IS A RESULT. With no panel on disk the script must write a BLOCKED artifact
     naming the missing input and exit NONZERO. It must never emit a breadth number, and it must
     never reach for a simulator. This measurement gates the EV hard-kill on `narrow_breadth`, so
     a fabricated answer here would be worse than no answer.

  2. RESIDUALISATION ACTUALLY REMOVES THE FACTOR, proven on panels whose true answer is known by
     construction rather than on the market, where nobody knows the right answer.

  3. PREFIX INVARIANCE. Truncating the input must not move any earlier output, all the way from
     raw returns to the expanding breadth path. The first version of the script failed this
     silently by feeding full-sample betas into a "trailing" path.

`_module()` loads the script by path AND registers it in `sys.modules` before executing it --
without the registration `@dataclass` cannot resolve `Panel.__module__` and the import dies with
a bare AttributeError, which reads as a broken test rather than a broken loader.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "scripts" / "measure_cross_section_breadth.py"


def _module() -> Any:
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location("measure_cross_section_breadth", _SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # dataclasses need the module resolvable during exec
    spec.loader.exec_module(mod)
    return mod


mcsb = _module()


def _one_factor_panel(t: int, n: int, *, rho_idio: float = 0.0, seed: int = 0,
                      beta_lo: float = 0.7, beta_hi: float = 1.3) -> np.ndarray:
    """Returns with ONE known common factor and idiosyncratic parts of known correlation.

    `rho_idio` is the TRUE residual correlation: 0.0 means a correct residualiser must report
    approximately the demeaning floor, and nothing above it.
    """
    rng = np.random.default_rng(seed)
    f = rng.normal(0.0, 0.03, (t, 1))
    betas = rng.uniform(beta_lo, beta_hi, (1, n))
    common = rng.normal(0.0, 1.0, (t, 1))
    idio = (np.sqrt(rho_idio) * common
            + np.sqrt(max(1.0 - rho_idio, 0.0)) * rng.normal(0.0, 1.0, (t, n))) * 0.03
    return np.asarray(f * betas + idio)


def _panel_doc(returns: np.ndarray, symbols: list[str], start_ms: int = 1_700_000_000_000,
               ) -> dict[str, Any]:
    """Wrap a return matrix as a cache document (prices reconstructed from the returns)."""
    closes = 100.0 * np.exp(np.vstack([np.zeros((1, returns.shape[1])), np.cumsum(returns, 0)]))
    ts = [float(start_ms + i * 86_400_000) for i in range(closes.shape[0])]
    return {"source": "test", "fetched_utc": "test",
            "bars": {s: {"t": ts, "close": [float(v) for v in closes[:, j]]}
                     for j, s in enumerate(symbols)}}


# --------------------------------------------------------------------------------------------
# 1. The blocked path.
# --------------------------------------------------------------------------------------------

def test_no_panel_on_disk_writes_blocked_report_and_exits_nonzero(tmp_path, monkeypatch):
    """The rule this desk will not bend: no data -> a named blocker, not a number."""
    monkeypatch.setattr(mcsb, "CACHE", tmp_path / "absent.json")
    monkeypatch.setattr(mcsb, "LAKE", tmp_path / "absent_lake")
    out = tmp_path / "report.json"

    code = mcsb.main(["--out", str(out)])

    assert code != 0, "a blocked run must exit nonzero"
    rep = json.loads(out.read_text("utf-8"))
    assert rep["status"] == "BLOCKED"
    assert rep["headline_n_eff"] is None, "a blocked report must not carry a breadth number"
    assert "no daily close panel" in rep["missing_input"]
    # It must name the paths it ACTUALLY looked at -- a blocker that names the wrong file sends
    # the next reader to investigate the wrong box.
    assert any("absent.json" in c for c in rep["checked"]), "must name the exact cache path"
    assert any("absent_lake" in c for c in rep["checked"]), "must name the exact lake path"
    assert rep["remedy"]


def test_blocked_run_never_fetches_without_the_flag(tmp_path, monkeypatch):
    """Absent data must not silently become a network call -- or, worse, a simulated one."""
    monkeypatch.setattr(mcsb, "CACHE", tmp_path / "absent.json")
    monkeypatch.setattr(mcsb, "LAKE", tmp_path / "absent_lake")

    def _boom(*_a: object, **_k: object) -> dict[str, Any]:
        raise AssertionError("fetch attempted without --fetch")

    monkeypatch.setattr(mcsb, "fetch_okx", _boom)
    assert mcsb.main(["--out", str(tmp_path / "r.json")]) != 0


def test_the_script_contains_no_synthetic_market_fallback():
    """A change-detector on the one rule that cannot be relaxed.

    `one_factor_null` legitimately simulates -- to calibrate an ESTIMATOR's floor on data whose
    answer is known. What must never exist is a path where an absent panel is replaced by
    generated prices. This pins the reachable set: only the null calibrator may draw randomness,
    and it is never called on the blocked path.
    """
    src = _SRC.read_text("utf-8")
    body = src.split('"""', 2)[2]                       # skip the module docstring
    rng_lines = [ln.strip() for ln in body.splitlines() if "default_rng" in ln]
    assert rng_lines, "expected the null calibrator to be the one randomness site"
    assert len(rng_lines) == 1, f"unexpected randomness outside the null calibrator: {rng_lines}"
    assert "def blocked_report" in body


def test_panel_too_small_after_cleaning_blocks_rather_than_reporting(monkeypatch):
    """Unknown must BLOCK. A breadth number from 3 names is a different, unasked question."""
    rets = _one_factor_panel(300, 3, seed=1)
    doc = _panel_doc(rets, ["A", "B", "C"])
    closes = np.column_stack([np.array(doc["bars"][s]["close"]) for s in ("A", "B", "C")])
    panel = mcsb.Panel(("A", "B", "C"), np.arange(closes.shape[0], dtype="int64"),
                       closes, "test", "test")
    rep = mcsb.build_report(panel)
    assert rep["status"] == "BLOCKED"
    assert rep["headline_n_eff"] is None


def test_dead_feed_is_dropped_not_counted_as_the_best_diversifier():
    """A frozen feed correlates with nothing. Counting it would MANUFACTURE breadth."""
    rets = _one_factor_panel(300, 10, seed=2)
    rets = np.column_stack([rets, np.zeros(300)])            # a pegged / halted symbol
    live = mcsb.live_columns(rets)
    assert live[:10].all()
    assert not live[10], "a zero-variance column must be dropped, not treated as independent"


# --------------------------------------------------------------------------------------------
# 2. Residualisation actually removes a common factor.
# --------------------------------------------------------------------------------------------

def test_residualisation_collapses_a_known_common_factor():
    """The core claim: raw correlation is the factor, residual correlation is what is left."""
    rets = _one_factor_panel(600, 20, seed=3)
    raw = mcsb.measure(rets)
    resid, _ = mcsb.residualise(rets)
    res = mcsb.measure(resid)

    assert raw.mean_corr > 0.4, f"synthetic factor too weak to be a test: {raw.mean_corr}"
    assert res.mean_corr < 0.05
    assert res.mean_corr < raw.mean_corr - 0.35, "residualisation must remove most of the factor"
    assert res.n_eff > 5 * raw.n_eff


def test_residual_correlation_lands_on_the_arithmetic_floor_when_nothing_is_there():
    """Calibration: with idiosyncratics INDEPENDENT by construction the answer is the floor.

    This is what makes the real panel's +0.0045 excess readable. Without it, a residual
    correlation of -0.033 could be read as "negatively correlated, better than independent",
    which would be breadth invented out of the demeaning constraint.
    """
    n = 25
    rets = _one_factor_panel(800, n, seed=4, rho_idio=0.0)
    resid, _ = mcsb.residualise(rets)
    floor = mcsb.demeaning_floor(n)
    excess = mcsb.measure(resid).mean_corr - floor
    assert abs(excess) < 0.01, f"expected the floor {floor:.4f}, excess was {excess:+.4f}"


def test_a_second_factor_loaded_on_every_name_is_correctly_absorbed():
    """Not a defect, and worth pinning so nobody 'fixes' it.

    A second common factor with equal loadings across the whole panel is, by definition, the
    market factor wearing another name. There is no observable that separates them and residual
    breadth SHOULD be unaffected. This is why `_one_factor_panel(rho_idio=...)` is not used to
    build residual structure: it produces an absorbed factor, not a surviving one.
    """
    plain = mcsb.measure(mcsb.residualise(_one_factor_panel(800, 25, seed=5))[0])
    doubled = mcsb.measure(
        mcsb.residualise(_one_factor_panel(800, 25, seed=5, rho_idio=0.30))[0])
    assert abs(plain.n_eff - doubled.n_eff) < 1.0


def test_genuine_residual_clusters_survive_and_only_the_pr_can_see_them():
    """The single strongest argument for the headline estimator, on a known-answer panel.

    Add a factor loading on HALF the names -- structure that is genuinely not the market and
    genuinely survives market removal. The mean pairwise correlation does not move AT ALL (the
    cluster's positive within-block correlation is exactly offset by negative cross-block
    correlation), so the equicorrelation N_eff reports the identical number for a clustered panel
    and a clean one. The participation ratio drops sharply. Reporting mean correlation alone here
    would have called a two-block panel fully diversified.
    """
    base = _one_factor_panel(800, 24, seed=5)
    cluster = np.random.default_rng(55).normal(0.0, 0.025, (800, 1))
    clustered = base.copy()
    clustered[:, :12] += cluster                      # a sector/narrative factor on half the panel

    plain_resid, _ = mcsb.residualise(base)
    clust_resid, _ = mcsb.residualise(clustered)
    plain, clust = mcsb.measure(plain_resid), mcsb.measure(clust_resid)

    assert clust.n_eff == pytest.approx(plain.n_eff, abs=0.01), \
        "equicorrelation N_eff is blind to offsetting clusters -- that is the point"
    assert clust.mean_corr == pytest.approx(plain.mean_corr, abs=0.005)
    assert mcsb.participation_ratio(clust_resid) < mcsb.participation_ratio(plain_resid) - 3.0, \
        "the participation ratio must detect the surviving cluster"


def test_betas_are_recovered():
    rets = _one_factor_panel(1200, 20, seed=6, beta_lo=0.5, beta_hi=1.5)
    _, betas = mcsb.residualise(rets)
    assert 0.3 < float(betas.min()) < 1.0
    assert 1.0 < float(betas.max()) < 1.8


def test_single_asset_proxy_manufactures_the_hard_kill_on_structureless_data():
    """THE finding, pinned as a regression: the obvious factor choice invents narrow breadth.

    Idiosyncratics are independent by construction, so the true residual correlation is zero and
    the true breadth is N. Regressing on one member of the panel injects that member's own
    idiosyncratic return into every residual, and the estimator reports a cross-section narrow
    enough to trip alpha_economics' hard kill. If this test ever goes quiet, someone has changed
    the factor and the desk is one commit from killing its own research programme on an artifact.
    """
    rets = _one_factor_panel(500, 28, seed=7, rho_idio=0.0)
    proxy = mcsb.measure(mcsb.residualise_single_proxy(rets, 0))
    honest = mcsb.measure(mcsb.residualise(rets)[0])

    assert proxy.mean_corr > 0.25, "single-asset proxy should show large spurious correlation"
    assert proxy.n_eff < mcsb.NARROW_BREADTH_LINE, "the artifact should trip narrow_breadth"
    assert honest.n_eff > 5 * proxy.n_eff
    assert not mcsb.gate_verdict(honest.n_eff)["verdict"].startswith("REJECT (hard")


def test_leave_one_out_market_excludes_the_symbol_itself():
    rets = np.arange(40.0).reshape(10, 4)
    f = mcsb.leave_one_out_market(rets)
    for i in range(4):
        expected = np.delete(rets, i, axis=1).mean(axis=1)
        assert np.allclose(f[:, i], expected)


# --------------------------------------------------------------------------------------------
# 3. Prefix invariance -- trailing data only, end to end.
# --------------------------------------------------------------------------------------------

def test_trailing_residuals_are_prefix_invariant():
    """Truncating the panel must not change a single earlier residual."""
    rets = _one_factor_panel(400, 12, seed=8)
    full = mcsb.residualise_trailing(rets, warmup=60)
    for k in (200, 310, 399):
        cut = mcsb.residualise_trailing(rets[:k], warmup=60)
        a, b = full[:k], cut
        both = np.isfinite(a) & np.isfinite(b)
        assert both.any()
        assert np.allclose(a[both], b[both], atol=1e-12), f"lookahead leaked at truncation {k}"
        assert (np.isfinite(a) == np.isfinite(b)).all()


def test_expanding_breadth_path_is_prefix_invariant():
    """The whole chain -- returns -> trailing residuals -> expanding breadth -- stays trailing."""
    rets = _one_factor_panel(400, 12, seed=9)
    full = mcsb.expanding_breadth(mcsb.residualise_trailing(rets, warmup=60), min_obs=120)
    cut = mcsb.expanding_breadth(mcsb.residualise_trailing(rets[:330], warmup=60), min_obs=120)
    both = np.isfinite(full[:330]) & np.isfinite(cut)
    assert both.sum() > 50, "expected a usable overlapping window"
    assert np.allclose(full[:330][both], cut[both], atol=1e-10)


def test_full_sample_residuals_are_NOT_prefix_invariant():
    """The counter-example that gives the test above its meaning.

    `residualise` fits beta on the whole sample, so truncation MOVES earlier rows. That is fine
    for a descriptive upper bound and fatal for anything called trailing. Pinning the difference
    stops the two from being quietly swapped.
    """
    rets = _one_factor_panel(400, 12, seed=10)
    full, _ = mcsb.residualise(rets)
    cut, _ = mcsb.residualise(rets[:200])
    assert not np.allclose(full[:200], cut, atol=1e-10)


def test_trailing_rows_before_warmup_are_nan_not_zero():
    """An unmeasurable residual must not enter downstream arithmetic as a small number."""
    rets = _one_factor_panel(300, 8, seed=11)
    out = mcsb.residualise_trailing(rets, warmup=100)
    assert np.isnan(out[:100]).all()
    assert np.isfinite(out[100:]).all()


# --------------------------------------------------------------------------------------------
# Estimator behaviour and the reported arithmetic.
# --------------------------------------------------------------------------------------------

def test_participation_ratio_separates_clusters_from_uniform_redundancy():
    """Why the headline does not use mean correlation alone.

    Two perfectly-correlated blocks with OPPOSITE signs have a mean pairwise correlation near
    zero -- the equicorrelation route calls that fully diversified. It is 2 bets, and the
    participation ratio says so.
    """
    rng = np.random.default_rng(12)
    a = rng.normal(0.0, 1.0, (600, 1))
    b = rng.normal(0.0, 1.0, (600, 1))
    panel = np.hstack([np.repeat(a, 6, axis=1), np.repeat(-a, 6, axis=1),
                       np.repeat(b, 6, axis=1), np.repeat(-b, 6, axis=1)])
    panel = panel + rng.normal(0.0, 0.01, panel.shape)

    assert abs(mcsb.measure(panel).mean_corr) < 0.10, "mean correlation is blind to sign-flips"
    assert mcsb.participation_ratio(panel) < 4.0, "the PR must see the two blocks"


def test_required_ic_inverts_grinold():
    assert mcsb.required_ic(25.0) == pytest.approx(0.2, abs=1e-9)
    assert mcsb.required_ic(25.0, bets_per_year=4.0) == pytest.approx(0.1, abs=1e-9)
    assert mcsb.required_ic(0.0) == float("inf")           # unknown must not read as "easy"
    # The desk's best-ever measured IC cannot reach IR 1.0 on any plausible cross-section.
    assert mcsb.required_ic(100.0) > mcsb.DESK_BEST_IC


def test_gate_verdict_hard_kills_only_below_the_narrow_breadth_line():
    """The imported gate, not a paraphrase of it, decides -- on both sides of the line."""
    narrow = mcsb.gate_verdict(3.0)
    wide = mcsb.gate_verdict(20.0)
    assert narrow["verdict"] == "REJECT (hard economic kill)"
    assert "narrow_breadth" in narrow["tags"]
    assert not wide["verdict"].startswith("REJECT (hard")
    assert "narrow_breadth" not in wide["tags"]


def test_end_to_end_report_on_a_known_panel_is_measured_and_self_consistent():
    """A full build_report pass whose true breadth is known by construction."""
    n = 20
    rets = _one_factor_panel(500, n, seed=13, rho_idio=0.0)
    closes = 100.0 * np.exp(np.vstack([np.zeros((1, n)), np.cumsum(rets, 0)]))
    syms = tuple(f"S{i:02d}" for i in range(n))
    ts = np.arange(closes.shape[0], dtype="int64") * 86_400_000 + 1_700_000_000_000
    rep = mcsb.build_report(mcsb.Panel(syms, ts, closes, "test", "test"),
                            warmup=120, null_draws=4)

    assert rep["status"] == "MEASURED"
    assert rep["panel"]["n_symbols"] == n
    assert rep["raw"]["mean_corr"] > 0.4
    # True breadth is N (independent idiosyncratics); the estimator must land near it, not at 2.
    assert rep["headline_n_eff"] > 0.6 * n
    assert rep["headline_n_eff"] <= n, "breadth cannot exceed the number of instruments"
    assert not rep["narrow_breadth"]["fires"]
    assert rep["ic_required"]["cross_sectional_only"] == pytest.approx(
        1.0 / np.sqrt(rep["headline_n_eff"]), rel=1e-3)
    assert rep["breadth_illusion"]["ir_overstatement_x"] >= 1.0
    # The sampling caveat must be surfaced as a field, not buried in prose.
    assert rep["sampling_caveat"]["noise_dominated"] is False
    assert rep["sampling_caveat"]["marchenko_pastur"]["mp_edge"] > 1.0
    assert mcsb.render(rep).count("SAMPLING CAVEAT") == 1


def test_report_renders_without_a_trailing_block_when_the_sample_is_short():
    """Short samples must degrade to 'not reported', never to a fabricated trailing number."""
    n = 12
    rets = _one_factor_panel(150, n, seed=14)
    closes = 100.0 * np.exp(np.vstack([np.zeros((1, n)), np.cumsum(rets, 0)]))
    ts = np.arange(closes.shape[0], dtype="int64") * 86_400_000
    rep = mcsb.build_report(mcsb.Panel(tuple(f"S{i}" for i in range(n)), ts, closes, "t", "t"),
                            warmup=140, null_draws=3)
    assert rep["status"] == "MEASURED"
    assert rep["residual_trailing"] is None
    assert "residual (trailing beta)" not in mcsb.render(rep)


def test_alignment_inner_joins_and_never_forward_fills(tmp_path):
    """A forward-filled close is a fake zero return, which INFLATES breadth. Drop, never pad."""
    n = 10
    rets = _one_factor_panel(400, n, seed=15)
    doc = _panel_doc(rets, [f"S{i}" for i in range(n)])
    doc["bars"]["S0"]["t"] = doc["bars"]["S0"]["t"][200:]      # a late listing
    doc["bars"]["S0"]["close"] = doc["bars"]["S0"]["close"][200:]
    path = tmp_path / "panel.json"
    path.write_text(json.dumps(doc), "utf-8")

    panel = mcsb.load_cache(path)
    assert panel is not None
    assert "S0" not in panel.symbols, "a short history must be dropped by the coverage screen"
    assert "S0" in panel.dropped_short
    assert panel.closes.shape[0] == 401, "the survivors must keep their full history"
