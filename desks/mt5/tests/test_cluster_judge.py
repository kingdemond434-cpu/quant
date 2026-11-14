"""P8-J1 cluster judge: the Tier-S forward clocks judged as ONE hypothesis.

Pinned here: membership is the CANONICAL deflated Sharpe at n_trials=bar_n() with variance
1/(T-1), never a t constant (a t of 2.9 at n=5 fails it); the state-row form is the canonical
arithmetic; a shared legacy ledger is UNMEASURED_SHARED_LEDGER and a missing forward_start is
UNMEASURED_NO_FORWARD_START; a pair with too few shared days is UNMEASURED, never zero; N_eff is
UNMEASURED rather than computed on a subset; correlated clocks are about one bet, and independent
clocks come out INDEPENDENT with N_eff close to k (the auditor's probe); identical-trade clocks are
one duplicate group but rows missing a summary field are not; the composite is IN-SAMPLE by name;
the pairs output is bounded; and the leg writes nothing but its own report.
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cluster_judge as cj  # type: ignore[import-not-found]  # noqa: E402

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
START = "2026-09-01T00:00:00+00:00"


def _days(n: int) -> list[str]:
    d0 = date(2026, 9, 2)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def _rows(rs: list[float], days: list[str] | None = None) -> list[dict[str, Any]]:
    ds = days or _days(len(rs))
    return [{"entry_time": f"{d} 01:00:00+00:00", "exit_time": f"{d} 03:00:00+00:00",
             "r_multiple": r, "phase": "forward"} for d, r in zip(ds, rs, strict=True)]


def _state_row(rs: list[float], days: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    n = len(rs)
    ds = days or _days(n)
    mu = sum(rs) / n
    var = sum((x - mu) ** 2 for x in rs) / (n - 1)
    return {"status": "ACTIVE", "n": n, "cum_r": sum(rs), "exp_r": mu,
            "forward_t": round(mu / (var / n) ** 0.5, 3), "forward_start": START,
            "first_entry": f"{ds[0]} 01:00:00+00:00",
            "last_entry": f"{ds[-1]} 01:00:00+00:00", **extra}


def _world(tmp_path: Path, clocks: dict[str, list[float]], *,
           ledgers: dict[str, list[float]] | None = None,
           days: dict[str, list[str]] | None = None,
           state_extra: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    state = {k: _state_row(v, (days or {}).get(k), **(state_extra or {}).get(k, {}))
             for k, v in clocks.items()}
    (shadow / "shadow_state.json").write_text(json.dumps(state), "utf-8")
    from libs.research import forward_ledger as fl
    for k, rs in (ledgers if ledgers is not None else clocks).items():
        (shadow / fl.per_key_name(k)).write_text(json.dumps(_rows(rs, (days or {}).get(k))),
                                                 "utf-8")
    doc: dict[str, Any] = cj.build(now=NOW, shadow=shadow, sleeves_file=tmp_path / "none.json",
                                   clock_law=tmp_path / "none2.json", ledger_dirs=(shadow,))
    return doc


def _edge(seed: int, n: int = 40, mu: float = 0.8) -> list[float]:
    rnd = random.Random(seed)  # noqa: S311 - a seeded synthetic series, not a secret
    return [mu + rnd.gauss(0.0, 1.0) for _ in range(n)]


def _syms(k: int) -> list[str]:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [f"{letters[i % 26]}{letters[(i // 26) % 26]}XZAR" for i in range(k)]


# ------------------------------------------------------------------------------- the bar
def test_bar_is_the_canonical_dsr_at_bar_n_not_a_t_constant() -> None:
    assert cj.bar_n() == 5 and cj.bar_n(10_000) == 5
    # what the canonical bar needs under normal returns (the auditor's table)
    assert cj.required_t_normal(5) == pytest.approx(4.56, abs=0.01)
    assert cj.required_t_normal(10) == pytest.approx(3.45, abs=0.01)
    assert cj.required_t_normal(18) == pytest.approx(3.14, abs=0.01)
    assert cj.required_t_normal(100) == pytest.approx(2.89, abs=0.01)
    # a t just above the old constant fails at n = 5
    j = cj.judge_clock({"n": 5, "forward_t": 2.9, "exp_r": 0.5}, None)
    assert j["passed"] is False and j["basis"] == "state_row_normal_moments"
    assert j["dsr"] < 0.95


def test_moment_form_is_the_canonical_function() -> None:
    from scipy.stats import kurtosis, skew

    from libs.validation.dsr import deflated_sharpe_ratio
    rng = np.random.default_rng(3)
    for n in (5, 12, 40):
        r = rng.standard_t(5, size=n) * 0.7 + 0.6
        canon = deflated_sharpe_ratio(r, n_trials=5, variance_of_sharpes=1.0 / (n - 1)).dsr
        sr = float(r.mean() / r.std(ddof=1))
        mine = cj.dsr_from_moments(sr, n, float(skew(r, bias=False)),
                                   float(kurtosis(r, fisher=False, bias=False)))
        assert mine == pytest.approx(canon, abs=1e-12)
        assert cj.canonical_dsr(list(r))["dsr"] == pytest.approx(canon, abs=1e-6)


def test_no_state_t_and_no_returns_is_unmeasured_not_a_constant() -> None:
    j = cj.judge_clock({"n": 9}, None)
    assert j["passed"] is None and j["basis"] == cj.UNMEASURED


def test_membership_is_the_canonical_pass_and_the_comparison_list_is_reported(
        tmp_path: Path) -> None:
    strong = _edge(1, n=40, mu=1.0)
    five = [1.0, 1.4, 0.2, 1.9, 0.6]                 # t ~ 3.0 at n = 5: in the t list, fails
    doc = _world(tmp_path, {"GBPZAR.overnight_gap_decay.asia": strong,
                            "EURZAR.overnight_gap_decay.asia": five})
    assert [m["key"] for m in doc["members"]] == ["GBPZAR.overnight_gap_decay.asia"]
    cmp_ = doc["enumeration"]["comparison_t_list"]
    assert cmp_["count"] == 2 and cmp_["canonical_pass"] == 1
    assert cmp_["canonical_fail"][0]["key"] == "EURZAR.overnight_gap_decay.asia"
    assert cmp_["t_cut"] == pytest.approx(2.84, abs=0.005)
    assert doc["members"][0]["judgement"]["basis"] == "own_ledger_canonical"


# ------------------------------------------------------------------------------- ledgers
def test_shared_legacy_ledger_is_unmeasured_never_a_siblings_file(tmp_path: Path) -> None:
    a = "GBPZAR.overnight_gap_decay.asia"
    b = "GBPZAR.overnight_gap_decay.asia#session=overlap"
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    state = {a: _state_row(_edge(2, mu=1.0)), b: _state_row(_edge(3, mu=1.0))}
    (shadow / "shadow_state.json").write_text(json.dumps(state), "utf-8")
    (shadow / "ledger_GBPZAR_overnight_gap_decay_asia.json").write_text(
        json.dumps(_rows(_edge(2, mu=1.0))), "utf-8")
    doc = cj.build(now=NOW, shadow=shadow, sleeves_file=tmp_path / "x", clock_law=tmp_path / "y",
                   ledger_dirs=(shadow,))
    assert doc["n_clocks"] == 2
    for m in doc["members"]:
        assert m["ledger"]["status"] == cj.UNMEASURED_SHARED_LEDGER
        assert m["judgement"]["basis"] == "state_row_normal_moments"
        assert doc["promotion_input"][m["key"]]["ledger_status"] == cj.UNMEASURED_SHARED_LEDGER
    assert doc["n_unmeasured_shared_ledger"] == 2
    assert doc["measured"]["n_eff"]["n_eff"] is None
    assert doc["cluster_verdict"]["in_sample"]["verdict"] == cj.UNMEASURED


def test_no_forward_start_is_named(tmp_path: Path) -> None:
    doc = _world(tmp_path, {"GBPZAR.overnight_gap_decay.asia": _edge(4, mu=1.0)},
                 state_extra={"GBPZAR.overnight_gap_decay.asia": {"forward_start": None}})
    assert doc["members"][0]["ledger"]["status"] == cj.UNMEASURED_NO_FORWARD_START


def test_rows_before_the_own_boundary_are_not_forward_evidence(tmp_path: Path) -> None:
    rs = _edge(5, n=30, mu=1.0)
    late = f"{_days(10)[-1]}T00:00:00+00:00"          # boundary inside the ledger
    doc = _world(tmp_path, {"GBPZAR.overnight_gap_decay.asia": rs},
                 state_extra={"GBPZAR.overnight_gap_decay.asia": {"forward_start": late}})
    led = doc["members"][0]["ledger"]
    assert led["ledger_trades"] == 21 and "note" in led       # 30 rows, 9 before the boundary


# ------------------------------------------------------------------------------- dependence
def test_short_overlap_is_an_unmeasured_pair_never_zero() -> None:
    a = {d: 1.0 + i for i, d in enumerate(_days(5))}
    p = cj.pair_corr(a, dict(a), z=2.0)
    assert p["status"] == cj.UNMEASURED and p["rho"] is None and p["overlap_days"] == 5


def test_correlated_clocks_are_about_one_independent_bet(tmp_path: Path) -> None:
    base = _edge(6, n=60)
    clocks = {f"{s}.overnight_gap_decay.asia": [x * (1 + 0.1 * i) + 0.001 * j
                                                for j, x in enumerate(base)]
              for i, s in enumerate(("GBPZAR", "EURZAR", "USDZAR", "CHFZAR"))}
    doc = _world(tmp_path, clocks)
    assert doc["n_clocks"] == 4 and doc["n_measured_series"] == 4
    assert doc["measured"]["n_eff"]["n_eff"] == pytest.approx(1.0, abs=0.05)
    assert len(doc["measured"]["clusters"]) == 1
    for row in doc["promotion_input"].values():
        assert row["concentration_flag"] == cj.FLAG_CONCENTRATED


@pytest.mark.parametrize("k", [5, 20, 54])
def test_independent_clocks_are_independent_with_n_eff_near_k(tmp_path: Path, k: int) -> None:
    """The auditor's probe, at full overlap: k i.i.d. clocks, 60 common trading days."""
    clocks = {f"{s}.overnight_gap_decay.asia": _edge(1000 + i, n=60)
              for i, s in enumerate(_syms(k))}
    doc = _world(tmp_path, clocks)
    assert doc["n_clocks"] == k
    ne = doc["measured"]["n_eff"]
    assert ne["status"] == "MEASURED"
    assert ne["n_eff"] == pytest.approx(k, abs=max(1.0, 0.12 * k))
    # the un-corrected estimate is what the auditor saw: biased low as k grows
    assert ne["n_eff_raw"] <= ne["n_eff"]
    flags = Counter(r["concentration_flag"] for r in doc["promotion_input"].values())
    assert flags[cj.FLAG_INDEPENDENT] >= 0.85 * k
    assert flags[cj.FLAG_CONCENTRATED] == 0


def test_auditor_probe_sparse_overlap_publishes_no_biased_number(tmp_path: Path) -> None:
    """54 i.i.d. clocks, 18 trades each over 40 days: the overlaps are too short to measure, so
    N_eff and the flags are UNMEASURED -- never a small 'measured' N_eff on a subset."""
    rnd = random.Random(77)  # noqa: S311 - seeded synthetic calendar
    pool = _days(40)
    clocks: dict[str, list[float]] = {}
    days: dict[str, list[str]] = {}
    for i, s in enumerate(_syms(54)):
        key = f"{s}.overnight_gap_decay.asia"
        days[key] = sorted(rnd.sample(pool, 18))
        clocks[key] = _edge(2000 + i, n=18, mu=1.3)
    doc = _world(tmp_path, clocks, days=days)
    assert doc["n_clocks"] >= 50
    assert doc["measured"]["n_eff"]["n_eff"] is None
    flags = Counter(r["concentration_flag"] for r in doc["promotion_input"].values())
    assert flags[cj.FLAG_CONCENTRATED] == 0 and flags[cj.FLAG_MODERATE] == 0
    assert all(r["independent_bets"] is None for r in doc["promotion_input"].values())


def test_n_eff_debias_and_eigen_guard() -> None:
    assert cj.n_eff([[1.0, 0.0], [0.0, 1.0]])["n_eff"] == pytest.approx(2.0)
    assert cj.n_eff([[1.0, 1.0], [1.0, 1.0]])["n_eff"] == pytest.approx(1.0)
    # a rho at its null size is noise, not dependence
    ov = [[0, 26], [26, 0]]
    assert cj.n_eff([[1.0, 0.2], [0.2, 1.0]], ov)["n_eff"] == pytest.approx(2.0)
    bad = [[1.0, 0.9, -0.9], [0.9, 1.0, 0.9], [-0.9, 0.9, 1.0]]
    r = cj.n_eff(bad)
    assert r["min_eigenvalue"] < -0.1 and r["n_eff"] is None and r["status"] == cj.UNMEASURED


def test_identical_trade_clocks_are_one_duplicate_group_from_state_alone(tmp_path: Path) -> None:
    rs = _edge(7, mu=1.0)
    keys = [f"GBPSEK.formula.asia#expr={e}" for e in ("abs", "max", "neg")]
    doc = _world(tmp_path, {**dict.fromkeys(keys, rs),
                            "EURZAR.overnight_gap_decay.asia": _edge(8, mu=1.0)}, ledgers={})
    fc = doc["first_cut"]
    assert fc["clocks"] == 4 and fc["distinct_trade_streams_upper_bound"] == 2
    assert sorted(next(iter(fc["duplicate_groups"].values()))) == sorted(keys)
    for k in keys:
        assert doc["promotion_input"][k]["concentration_flag"] == cj.FLAG_DUPLICATE


def test_rows_missing_summary_fields_are_never_duplicates() -> None:
    ms = [{"key": f"K{i}", "symbol": "GBPZAR", "n": 12, "cum_r": None,
           "first_entry": None, "last_entry": None} for i in range(4)]
    g = cj.duplicate_groups(ms)
    assert set(g.values()) == {None}
    assert cj.state_first_cut(ms, g)["clocks_duplicate_unmeasured"] == 4


def test_currency_and_family_concentration() -> None:
    members = [{"key": k, "currencies": cj.currencies(k[:6]), "family": f}
               for k, f in (("GBPZAR", "overnight_gap_decay"), ("EURZAR", "overnight_gap_decay"),
                            ("USDZAR", "spread_state"), ("CHFDKK", "overnight_gap_decay"))]
    c = cj.concentration(members)
    assert c["by_currency"]["ZAR"]["leg_share"] == pytest.approx(3 / 8)
    assert c["by_currency"]["ZAR"]["clock_share"] == pytest.approx(0.75)
    assert "ZAR" in c["currencies_at_or_above_share"]["named"]
    assert c["by_family"]["overnight_gap_decay"]["share"] == pytest.approx(0.75)


# ------------------------------------------------------------------------------- the report
def test_composite_is_in_sample_and_never_clears(tmp_path: Path) -> None:
    clocks = {f"{s}.overnight_gap_decay.asia": _edge(300 + i, n=60)
              for i, s in enumerate(_syms(6))}
    doc = _world(tmp_path, clocks)
    v = doc["cluster_verdict"]
    assert v["in_sample"]["verdict"].startswith("IN_SAMPLE_")
    assert doc["measured"]["composite_equal_weight"]["in_sample"] is True
    assert v["out_of_sample"]["status"] == cj.UNMEASURED
    assert "CLEARS" not in json.dumps(v)


def test_pairs_output_is_bounded(tmp_path: Path) -> None:
    clocks = {f"{s}.overnight_gap_decay.asia": _edge(500 + i, n=30, mu=1.0)
              for i, s in enumerate(_syms(15))}
    doc = _world(tmp_path, clocks)
    assert doc["pairs_summary"]["pairs_possible"] == 105
    assert len(doc["pairs_top"]) == cj.TOP_K_PAIRS
    assert "pairs" not in doc


def test_writes_only_its_own_report_and_charges_one_trial(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    clocks = {"GBPZAR.overnight_gap_decay.asia": _edge(9, mu=1.0)}
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_state.json").write_text(
        json.dumps({k: _state_row(v) for k, v in clocks.items()}), "utf-8")
    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")}
    monkeypatch.setattr(cj, "SHADOW", shadow)
    monkeypatch.setattr(cj, "LEDGER_DIRS", (shadow,))
    monkeypatch.setattr(cj, "SLEEVES_FILE", tmp_path / "absent_sleeves.json")
    monkeypatch.setattr(cj, "CLOCK_LAW", tmp_path / "absent_law.json")
    out = tmp_path / "out" / "CLUSTER_JUDGE.json"
    real_write_text = Path.write_text
    written: list[Path] = []

    def _spy(self: Path, *a: Any, **k: Any) -> int:
        written.append(self)
        return real_write_text(self, *a, **k)
    monkeypatch.setattr(Path, "write_text", _spy)
    assert cj.main(["--out", str(out)]) == 0
    after = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    assert {p for p, m in after.items() if before.get(p) != m} == {out}
    assert [p.name for p in written] == ["CLUSTER_JUDGE.json.tmp"]
    doc = json.loads(out.read_text("utf-8"))
    assert doc["trials"]["trials_charged"] == 1 and doc["trials"]["trial_ledger_writes"] == 0
    assert doc["sizing_hook"]["status"] == "NOT_WIRED"
    src = Path(cj.__file__).read_text("utf-8")
    for writer in ("experiment_ledger", "trial_ledger.", "record_trial"):
        assert writer not in src, writer


def test_promotion_input_reader_never_raises(tmp_path: Path) -> None:
    assert cj.promotion_input("X", tmp_path / "absent.json")["concentration_flag"] == cj.UNMEASURED
    doc = _world(tmp_path, {"GBPZAR.overnight_gap_decay.asia": _edge(10, mu=1.0)})
    p = cj.write(doc, tmp_path / "cj.json")
    row = cj.promotion_input("GBPZAR.overnight_gap_decay.asia", p)
    assert {"independent_bets", "max_pair_corr", "cluster_id", "concentration_flag"} <= set(row)
    assert cj.promotion_input("NOPE", p)["concentration_flag"] == cj.UNMEASURED


def test_registered_as_an_hourly_core_leg() -> None:
    from libs.research.layers import LEG_LAYER
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"cluster_judge", "research/cluster_judge.py"' in src
    assert LEG_LAYER.get("cluster_judge") == "portfolio"
    contracts = json.loads((ROOT / "docs" / "research" / "experiment_contracts.json")
                           .read_text("utf-8"))
    assert "cluster_judge" in json.dumps(contracts)


# ----------------------------------------------- audit of 2ca3d7098, should-fixes
def test_n_trials_source_names_the_fallback_honestly(tmp_path: Path) -> None:
    """The bar's N source is the guard's bar_n only when the guard is in use; the hard-5
    fallback is published as FALLBACK_HARD_5, never as trial_count_guard."""
    assert cj.n_trials_source(cj._fixed_bar_n) == cj.FALLBACK_HARD_5

    def bar_n(_requested: Any = None) -> int:
        return 5
    bar_n.__module__ = "libs.research.trial_count_guard"
    assert cj.n_trials_source(bar_n) == "libs.research.trial_count_guard.bar_n"
    doc = _world(tmp_path, {"GBPZAR.overnight_gap_decay.asia": _edge(1, n=40, mu=1.0)})
    src = doc["bar"]["n_trials_source"]
    assert src == cj.n_trials_source()
    if cj.bar_n is cj._fixed_bar_n:
        assert src == cj.FALLBACK_HARD_5 and "trial_count_guard" not in src
    else:
        assert src.endswith(".bar_n") and src != cj.FALLBACK_HARD_5


def test_independent_needs_80pct_power_at_the_detectable_rho() -> None:
    """The bare significance threshold at rho = 0.7 is ~50% power; INDEPENDENT now needs every
    pair to detect 0.7 at >= 80% power, and the measured power is published."""
    from scipy.stats import norm
    z = cj.pair_z(5)
    assert z is not None
    # n where the old rule (z/sqrt(n) <= 0.7) just passes: ~50% power, now underpowered
    n_old = math.ceil((z / cj.DETECTABLE_RHO) ** 2)
    assert cj.power_at(cj.DETECTABLE_RHO, z, n_old) == pytest.approx(0.5, abs=0.12)
    assert cj.detectable_rho(z, n_old) > cj.DETECTABLE_RHO
    n_new = math.ceil(((z + float(norm.ppf(0.8))) / cj.DETECTABLE_RHO) ** 2)
    assert cj.detectable_rho(z, n_new) <= cj.DETECTABLE_RHO
    assert cj.power_at(cj.DETECTABLE_RHO, z, n_new) >= 0.80
    # a Monte Carlo of the actual test agrees the power is at least what is published
    rng = np.random.default_rng(11)
    cov = [[1.0, cj.DETECTABLE_RHO], [cj.DETECTABLE_RHO, 1.0]]
    hits = sum(float(np.corrcoef(*rng.multivariate_normal([0, 0], cov, size=n_new).T)[0, 1])
               > z / math.sqrt(n_new) for _ in range(2000))
    assert hits / 2000 >= 0.80
    flag, why = cj._flag("k", dup_g=None, dup_n=0, sig_pos=[], has_series=True, n_unmeasured=0,
                         detect=cj.detectable_rho(z, n_old), ledger_status="OWN")
    assert flag == cj.UNMEASURED and why is not None and "80% power" in why
    days = _days(n_new)
    rnd = random.Random(5)  # noqa: S311 - seeded synthetic series
    p = cj.pair_corr({d: rnd.gauss(0, 1) for d in days}, {d: rnd.gauss(0, 1) for d in days}, z=z)
    assert p["detectable_rho"] <= cj.DETECTABLE_RHO and p["power_at_detectable_rho"] >= 0.80
