"""The adversary must break a lie and leave a truth standing -- proved on planted effects.

Every test here plants a KNOWN mechanism into synthetic bars and asserts which attack finds it.
A test that only checked `main() == 0` would pass against an organ that returned SURVIVED for
everything, which is the exact failure a counterexample agent exists to prevent.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import counterexample_agent as CA  # noqa: E402

DAYS = 400
HOUR = 7
TTL = 4


# ------------------------------------------------------------------------------- fixtures
def _index(days: int = DAYS) -> pd.DatetimeIndex:
    return pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="UTC")


def _bars(steps: np.ndarray, idx: pd.DatetimeIndex) -> pd.DataFrame:
    close = 100.0 * np.exp(np.cumsum(steps))
    open_ = np.concatenate(([100.0], close[:-1]))
    return pd.DataFrame({"open": open_, "close": close,
                         "high": np.maximum(open_, close), "low": np.minimum(open_, close)},
                        index=idx)


def _sides(rng: np.random.Generator, days: int, long_share: float) -> np.ndarray:
    return np.where(rng.random(days) < long_share, 1, -1)


def planted(*, days: int = DAYS, drift: float = 0.0, seed: int = 7,
            sides: np.ndarray | None = None, edge: float = 0.0,
            months: set[str] | None = None, spike_bar: int | None = None,
            noise: float = 0.0015) -> tuple[pd.DataFrame, np.ndarray]:
    """Bars with a known effect, and the per-day side the rule would take.

    `edge` is added to each of the TTL bars after the signal, TIMES the day's side -- so a rule
    that takes that side earns it and a rule that does not, does not. `spike_bar` puts the whole
    effect in one bar and takes it back in the next, which is what a parameter CLIFF looks like.
    `months` restricts the effect to named YYYY-MM months, which is what a one-month edge is.
    """
    idx = _index(days)
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, noise, size=len(idx))
    side_of = sides if sides is not None else np.ones(days, dtype=int)
    for day in range(days):
        entry = day * 24 + HOUR + 1                # the bar the trade is filled on
        if entry + TTL + 3 >= len(idx):
            continue
        if months is not None and idx[entry].strftime("%Y-%m") not in months:
            continue
        s = int(side_of[day])
        if spike_bar is not None:
            steps[entry + spike_bar] += edge * s * TTL
            steps[entry + spike_bar + 1] -= edge * s * TTL
        else:
            for k in range(TTL):
                steps[entry + k] += edge * s
    return _bars(steps, idx), side_of


def stub_family(side_of: np.ndarray, *, days: int = DAYS
                ) -> Callable[[pd.DataFrame, str, dict[str, Any]], tuple[list[CA.Sig], str]]:
    """A `family_signals` stand-in: one signal a day at HOUR, ttl from the params."""

    def _signals(d: pd.DataFrame, family: str, params: dict[str, Any]
                 ) -> tuple[list[CA.Sig], str]:
        ttl = max(1, int(params.get("ttl_bars", TTL)))
        out: list[CA.Sig] = []
        for day in range(min(days, len(d) // 24)):
            i = day * 24 + HOUR
            if i + ttl + 2 >= len(d):
                break
            out.append(CA.Sig(time=d.index[i], side=int(side_of[day]), ttl_bars=ttl))
        return out, f"{len(out)} stub signal(s) for {family}"

    return _signals


def _base(d: pd.DataFrame, sigs: list[CA.Sig]) -> tuple[list[Any], np.ndarray, dict[str, Any]]:
    times, r = CA.trades(d, sigs)
    s = CA.stat(r)
    assert s is not None, "the planted series must clear the independent-trade floor"
    return times, r, s


# --------------------------------------------------------------------- a real edge survives
def test_real_edge_survives_every_attack(monkeypatch: pytest.MonkeyPatch) -> None:
    rng = np.random.default_rng(3)
    sides = _sides(rng, DAYS, 0.5)
    d, _ = planted(sides=sides, edge=0.0016, seed=11)
    placebo, _ = planted(sides=sides, edge=0.0, seed=99)       # same rule, no mechanism there
    fam = stub_family(sides)
    monkeypatch.setattr(CA, "family_signals", fam)
    monkeypatch.setattr(CA, "load_bars", lambda s: placebo if s == "PLACEBO" else d)

    sigs, _ = fam(d, "planted", {"ttl_bars": TTL})
    times, r, base = _base(d, sigs)
    assert base["t"] > 6, base

    v = CA.placebo_symbol(d, sigs, base, family="planted", params={"ttl_bars": TTL},
                          symbol="REAL", placebo="PLACEBO")
    assert v["status"] == "SURVIVED", v

    v = CA.placebo_date(d, sigs, base, rng=np.random.default_rng(5))
    assert v["status"] == "SURVIVED", v
    assert v["value"] < CA.ROTATION_P

    v = CA.sign_flip(d, sigs, base)
    assert v["status"] == "SURVIVED", v          # the SIDES carry the edge, not a drift

    v = CA.neighbour_param(d, base, family="planted", params={"ttl_bars": TTL})
    assert v["status"] == "SURVIVED", v          # a plateau in ttl, not a spike

    v = CA.excluded_window(times, r, base)
    assert v["status"] == "SURVIVED", v
    assert v["best_month_share"] < 0.5


# ------------------------------------------------------------- each lie meets its own attack
def test_one_month_edge_is_broken_by_the_excluded_window(monkeypatch: pytest.MonkeyPatch
                                                         ) -> None:
    """The whole effect lives in one month: the effect IS that month."""
    sides = np.ones(DAYS, dtype=int)
    d, _ = planted(sides=sides, edge=0.06, months={"2024-03"}, seed=21, noise=0.0008)
    fam = stub_family(sides)
    monkeypatch.setattr(CA, "family_signals", fam)

    sigs, _ = fam(d, "onemonth", {"ttl_bars": TTL})
    times, r, base = _base(d, sigs)
    assert base["t"] > 3, base                   # it looks like an edge before the attack

    v = CA.excluded_window(times, r, base)
    assert v["status"] == "BROKEN", v
    assert v["best_month"] == "2024-03"
    assert v["best_month_share"] > 0.8, v


def test_directionless_rule_is_broken_by_the_sign_flip(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rule mostly long on a drifting instrument: a static position earns the same."""
    rng = np.random.default_rng(4)
    sides = np.where(rng.random(DAYS) < 0.82, 1, -1)
    # The effect does NOT follow the rule's side -- every day drifts up at the signal hour, so
    # whatever the rule says, holding long over the same windows collects it.
    d, _ = planted(sides=np.ones(DAYS, dtype=int), edge=0.0018, seed=31)
    fam = stub_family(sides)
    monkeypatch.setattr(CA, "family_signals", fam)

    sigs, _ = fam(d, "drifty", {"ttl_bars": TTL})
    _times, _r, base = _base(d, sigs)

    v = CA.sign_flip(d, sigs, base)
    assert v["status"] == "BROKEN", v
    assert v["value"] >= CA.FLIP_SHARE, v
    assert v["statistic"].startswith("|static one-sided mean|")


def test_one_sided_family_reports_the_flip_as_unmeasured(monkeypatch: pytest.MonkeyPatch
                                                          ) -> None:
    """A mirror is not a counterexample, and the organ says so rather than claiming survival."""
    sides = np.ones(DAYS, dtype=int)
    d, _ = planted(sides=sides, edge=0.0016, seed=41)
    fam = stub_family(sides)
    monkeypatch.setattr(CA, "family_signals", fam)
    sigs, _ = fam(d, "oneside", {"ttl_bars": TTL})
    _times, _r, base = _base(d, sigs)

    v = CA.sign_flip(d, sigs, base)
    assert v["status"] == "UNMEASURED", v
    assert "mirror" in v["why"]
    assert v["t_flip"] == pytest.approx(-base["t"], abs=1e-6)


def test_untimed_edge_is_broken_by_the_placebo_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """A constant drift is not a timing rule: a rotated date earns exactly as much."""
    idx = _index()
    rng = np.random.default_rng(9)
    steps = rng.normal(0.0012, 0.0006, size=len(idx))       # drift EVERYWHERE, not at HOUR
    d = _bars(steps, idx)
    sides = np.ones(DAYS, dtype=int)
    fam = stub_family(sides)
    monkeypatch.setattr(CA, "family_signals", fam)

    sigs, _ = fam(d, "alwaysup", {"ttl_bars": TTL})
    _times, _r, base = _base(d, sigs)
    assert base["t"] > 5, base

    v = CA.placebo_date(d, sigs, base, rng=np.random.default_rng(13))
    assert v["status"] == "BROKEN", v
    assert v["value"] >= CA.ROTATION_P, v


def test_parameter_cliff_is_broken_by_the_neighbour(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rule that works at ttl=4 and dies at 3 and 5 had its parameter chosen by the data."""
    sides = np.ones(DAYS, dtype=int)
    d, _ = planted(sides=sides, edge=0.004, spike_bar=TTL, seed=51, noise=0.0006)
    fam = stub_family(sides)
    monkeypatch.setattr(CA, "family_signals", fam)

    sigs, _ = fam(d, "cliff", {"ttl_bars": TTL})
    _times, _r, base = _base(d, sigs)
    assert base["t"] > 4, base

    v = CA.neighbour_param(d, base, family="cliff", params={"ttl_bars": TTL})
    assert v["status"] == "BROKEN", v
    assert any(p["status"] == "CLIFF" for p in v["params_tested"]), v


def test_the_placebo_symbol_breaks_a_generic_statistic(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unrelated market paying the same means the mechanism is not what earns it."""
    sides = np.ones(DAYS, dtype=int)
    d, _ = planted(sides=sides, edge=0.0016, seed=61)
    twin, _ = planted(sides=sides, edge=0.0016, seed=62)     # a different market, same payoff
    fam = stub_family(sides)
    monkeypatch.setattr(CA, "family_signals", fam)
    monkeypatch.setattr(CA, "load_bars", lambda s: twin if s == "TWIN" else d)

    sigs, _ = fam(d, "generic", {"ttl_bars": TTL})
    _times, _r, base = _base(d, sigs)
    v = CA.placebo_symbol(d, sigs, base, family="generic", params={"ttl_bars": TTL},
                          symbol="REAL", placebo="TWIN")
    assert v["status"] == "BROKEN", v
    assert v["value"] >= CA.PLACEBO_SHARE, v


# --------------------------------------------------------------------- absence is a verdict
def test_missing_bars_and_missing_family_are_unmeasured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CA, "load_bars", lambda s: None)
    res = CA.attack({"id": "c1", "symbol": "NOPE", "family": "x", "params_json": "{}",
                     "status": "queued"})
    assert res["verdict"] == "UNMEASURED"
    assert "500 H1 bars" in res["why"]

    sides = np.ones(DAYS, dtype=int)
    d, _ = planted(sides=sides, edge=0.0, seed=71)
    monkeypatch.setattr(CA, "load_bars", lambda s: d)
    monkeypatch.setattr(CA, "family_signals", lambda *a, **k: ([], "no constructor for family"))
    res = CA.attack({"id": "c2", "symbol": "REAL", "family": "ghost", "params_json": "{}",
                     "status": "queued"})
    assert res["verdict"] == "UNMEASURED"
    assert res["attacks"] == []
    assert "no constructor" in res["why"]


def test_short_series_never_reads_as_survival(monkeypatch: pytest.MonkeyPatch) -> None:
    """Under the trade floor there is no baseline, so there is nothing to have survived."""
    sides = np.ones(40, dtype=int)
    d, _ = planted(days=40, sides=sides, edge=0.002, seed=81)
    monkeypatch.setattr(CA, "load_bars", lambda s: d)
    monkeypatch.setattr(CA, "family_signals", stub_family(sides, days=10))
    res = CA.attack({"id": "c3", "symbol": "REAL", "family": "tiny", "params_json": "{}",
                     "status": "queued"})
    assert res["verdict"] == "UNMEASURED"
    assert "below the floor" in res["why"]


# ------------------------------------------------------------------- the report and the row
def _registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A HERMETIC registry. `connect` restores from the desk's moat backup when the file is
    absent, so a test that only set the path would silently read the real desk."""
    from libs.moat import registry as reg
    monkeypatch.setattr(reg, "BACKUP", tmp_path / "no_such_backup.sqlite")
    reg.set_path(tmp_path / "alpha_registry.sqlite")
    return reg


def test_report_is_written_even_with_no_candidate(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    _registry(tmp_path, monkeypatch)
    out = tmp_path / "COUNTEREXAMPLE_AGENT.json"
    assert CA.main(["--once", "--budget-s", "20", "--max-attacks", "3", "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["counts"]["candidates_attacked"] == 0
    assert any(r["name"] == "registry" for r in doc["inputs"])
    assert doc["per_attack"]["sign_flip"] == {"SURVIVED": 0, "BROKEN": 0, "UNMEASURED": 0}


def test_verdict_lands_on_the_registry_row_and_changes_no_status(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _registry(tmp_path, monkeypatch)
    cid, created = reg.enqueue_candidate(family="planted", symbol="REAL",
                                         params={"ttl_bars": TTL}, origin="DESK",
                                         mechanism="test", status="queued")
    assert created
    rng = np.random.default_rng(3)
    sides = _sides(rng, DAYS, 0.5)
    d, _ = planted(sides=sides, edge=0.0016, seed=11)
    monkeypatch.setattr(CA, "family_signals", stub_family(sides))
    monkeypatch.setattr(CA, "load_bars", lambda s: d)
    monkeypatch.setattr(CA, "placebo_for", lambda s, u: None)

    report = CA.build(max_attacks=5, budget_s=120.0, dry_run=False)
    assert report["counts"]["candidates_attacked"] == 1
    assert report["counts"]["registry_rows_written"] == 1

    conn = reg.connect()
    try:
        row = dict(conn.execute("SELECT status, counterexample_verdict, "
                                "counterexample_broken_by, counterexample_judged_at "
                                "FROM research_candidates WHERE id=?", (cid,)).fetchone())
    finally:
        conn.close()
    assert row["status"] == "queued", "the agent must never change a candidate's status"
    assert row["counterexample_verdict"] in ("ALL_SURVIVED", "BROKEN")
    assert row["counterexample_judged_at"]


def test_dry_run_writes_nothing_and_records_nothing(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _registry(tmp_path, monkeypatch)
    cid, _ = reg.enqueue_candidate(family="planted", symbol="REAL", params={"ttl_bars": TTL},
                                   origin="DESK", mechanism="test", status="queued")
    sides = np.ones(DAYS, dtype=int)
    d, _ = planted(sides=sides, edge=0.0016, seed=11)
    monkeypatch.setattr(CA, "family_signals", stub_family(sides))
    monkeypatch.setattr(CA, "load_bars", lambda s: d)
    monkeypatch.setattr(CA, "placebo_for", lambda s, u: None)

    out = tmp_path / "nowhere.json"
    assert CA.main(["--dry-run", "--max-attacks", "3", "--budget-s", "60",
                    "--out", str(out)]) == 0
    assert not out.exists(), "--dry-run must write no artifact"

    conn = reg.connect()
    try:
        row = dict(conn.execute("SELECT counterexample_verdict, counterexample_judged_at "
                                "FROM research_candidates WHERE id=?", (cid,)).fetchone())
        events = conn.execute("SELECT COUNT(*) AS n FROM alpha_events WHERE alpha_id=?",
                              (cid,)).fetchone()["n"]
    finally:
        conn.close()
    assert row["counterexample_verdict"] is None
    assert row["counterexample_judged_at"] is None
    assert events == 0
