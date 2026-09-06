"""THE EXPERIMENT CACHE AND SCALING LAB (P39 / P40).

A cache has one failure mode that matters and it is not a miss. A miss costs an hour. A COLLISION
returns a result computed under different conditions, instantly and confidently -- strictly worse
than having no cache at all, because nobody rechecks a fast answer.

So the tests here are almost entirely about what the key must SEPARATE and what it must NOT. Every
component of the key gets a test that changing it changes the key; the things outside the key get
a test that changing them does not. And a key with a component missing must REFUSE rather than
default, because a defaulted component is exactly how a collision gets manufactured.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_expcache", _ROOT / "desks" / "mt5" / "research" / "experiment_cache.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ec():
    return _load()


def _exp(ec, **over):
    base = {"data": "XAUUSD/H1/2020-2026@rev7", "features": ("dxy", "vix", "atr"),
            "model": "ridge(alpha=0.1)", "code_sha": "abc1234", "seed": 7}
    return ec.Experiment(**(base | over))


# --------------------------------------------------------------- what MUST separate
@pytest.mark.parametrize(("field", "value"), [
    ("data", "XAUUSD/H1/2020-2026@rev8"),
    ("features", ("dxy", "vix")),
    ("model", "ridge(alpha=0.2)"),
    ("code_sha", "def5678"),
    ("seed", 8),
])
def test_every_key_component_changes_the_key(ec, field, value) -> None:
    """Anything that could change the answer must change the key, or the cache collides."""
    assert _exp(ec).key() != _exp(ec, **{field: value}).key(), (
        f"changing {field} did not change the key -- two genuinely different experiments now "
        "share a cache entry, and one will be served the other's result")


def test_the_code_sha_is_part_of_the_key(ec) -> None:
    """Named separately because it is the one people leave out.

    Without it the cache serves yesterday's number for today's estimator forever, and does so
    behind a spectacular hit rate.
    """
    assert _exp(ec, code_sha="aaa").key() != _exp(ec, code_sha="bbb").key()
    assert "code_sha" in ec.KEY_PARTS


# --------------------------------------------------------------- what must NOT separate
def test_feature_order_does_not_change_the_key(ec) -> None:
    """The same inputs in a different order are the same experiment. A key sensitive to list
    order misses on every re-run for no reason at all."""
    assert _exp(ec, features=("vix", "atr", "dxy")).key() == _exp(ec).key()


def test_context_does_not_change_the_key(ec) -> None:
    """Host, hour and who asked cannot change the answer, so they cannot change the key."""
    a = _exp(ec, context={"host": "vps", "at": "2026-09-06T02:00:00"})
    b = _exp(ec, context={"host": "box", "at": "2026-01-01T00:00:00"})
    assert a.key() == b.key(), "recorded context leaked into the key; the cache will never hit"


# --------------------------------------------------------------- refusals
@pytest.mark.parametrize(("over", "mentions"), [
    ({"data": ""}, "data"),
    ({"features": ()}, "features"),
    ({"model": ""}, "model"),
    ({"code_sha": ""}, "code_sha"),
])
def test_a_missing_key_component_is_refused_not_defaulted(ec, over, mentions) -> None:
    """THE COLLISION FACTORY. A defaulted component makes different experiments share a key."""
    bad = ec.missing_parts(_exp(ec, **over))
    assert bad, f"{over} was accepted; a defaulted component manufactures collisions"
    assert any(mentions in b for b in bad)


def test_a_dirty_tree_is_never_cached(ec, tmp_path) -> None:
    """Two different working trees share a HEAD, so a result cached against it can be served to
    the wrong one. `-dirty` must refuse on BOTH lookup and store."""
    e = _exp(ec, code_sha="abc1234-dirty")
    got, why = ec.lookup(e, tmp_path / "c.jsonl")
    assert got is None and why.startswith("REFUSED") and "dirty" in why
    ok, why2 = ec.store(e, {"oos_skill": 0.1}, 10.0, tmp_path / "c.jsonl")
    assert ok is False and why2.startswith("REFUSED")


def test_a_miss_is_not_a_refusal(ec, tmp_path) -> None:
    """They mean different things and demand different responses: a miss runs the experiment,
    a refusal means the experiment cannot be safely cached at all."""
    got, why = ec.lookup(_exp(ec), tmp_path / "c.jsonl")
    assert got is None and why.startswith("MISS")


def test_a_stored_result_comes_back(ec, tmp_path) -> None:
    path = tmp_path / "c.jsonl"
    ok, _ = ec.store(_exp(ec), {"oos_skill": 0.42}, 120.0, path)
    assert ok
    got, why = ec.lookup(_exp(ec), path)
    assert got == {"oos_skill": 0.42} and why.startswith("HIT")


def test_a_different_experiment_does_not_come_back(ec, tmp_path) -> None:
    """The whole point, stated as a test: a near-identical experiment must MISS."""
    path = tmp_path / "c.jsonl"
    ec.store(_exp(ec), {"oos_skill": 0.42}, 120.0, path)
    got, why = ec.lookup(_exp(ec, model="ridge(alpha=0.2)"), path)
    assert got is None and why.startswith("MISS"), (
        "a different model was served another model's cached result")


# --------------------------------------------------------------- P40
def test_a_slope_from_too_few_runs_calls_itself_insufficient(ec, tmp_path) -> None:
    """An exponent from a handful of runs is numerology, and numerology that recommends
    spending money is worse than no answer at all."""
    path = tmp_path / "c.jsonl"
    for i, rows in enumerate((1000, 1100, 1200)):
        e = ec.Experiment(data=f"d{i}", features=("f",), model="m", code_sha="abc1234",
                          seed=i, context={"rows": rows})
        ec.store(e, {"oos_skill": 0.1 + i * 0.01}, 10.0, path)
    s = ec.scaling("rows", path)
    assert s["runs"] == 3, "the axis was not actually varied; this test proved nothing"
    assert s["sufficient"] is False, (
        f"three runs spanning {s['doublings_spanned']} doublings was called sufficient")
    assert "numerology" in s["verdict"]


def test_a_flat_scaling_curve_says_stop_spending(ec, tmp_path) -> None:
    """The decision this supports is coarse: keep spending, or stop."""
    path = tmp_path / "c.jsonl"
    for i in range(8):
        e = ec.Experiment(data=f"d{i}", features=("f",), model="m", code_sha="abc1234", seed=i,
                          context={"rows": 1000 * (2 ** i)})
        ec.store(e, {"oos_skill": 0.30}, 10.0, path)
    s = ec.scaling("rows", path)
    assert s["sufficient"] is True, s["verdict"]
    assert abs(s["log_slope"]) < 0.01
    assert "spend, not investment" in s["verdict"]


def test_a_rising_scaling_curve_says_keep_spending(ec, tmp_path) -> None:
    path = tmp_path / "c.jsonl"
    for i in range(8):
        e = ec.Experiment(data=f"d{i}", features=("f",), model="m", code_sha="abc1234", seed=i,
                          context={"rows": 1000 * (2 ** i)})
        ec.store(e, {"oos_skill": 0.10 + 0.05 * i}, 10.0, path)
    s = ec.scaling("rows", path)
    assert s["sufficient"] is True and s["log_slope"] > 0.01
    assert "keep spending" in s["verdict"]


def test_an_axis_that_does_not_vary_yields_no_slope(ec, tmp_path) -> None:
    """A slope through a vertical stack of points is not a scaling law."""
    path = tmp_path / "c.jsonl"
    for i in range(8):
        e = ec.Experiment(data=f"d{i}", features=("f",), model="m", code_sha="abc1234", seed=i,
                          context={"rows": 5000})
        ec.store(e, {"oos_skill": 0.1 + 0.01 * i}, 10.0, path)
    s = ec.scaling("rows", path)
    assert s["log_slope"] is None and s["sufficient"] is False


def test_an_empty_cache_reports_a_gap_not_a_pass(ec, tmp_path, monkeypatch, capsys) -> None:
    """ABSENCE IS NEVER A PASS. An empty cache is not a healthy cache."""
    monkeypatch.setattr(ec, "CACHE", tmp_path / "empty.jsonl")
    monkeypatch.setattr(ec, "REPORT", tmp_path / "r.json")
    ec.main([])
    assert "EMPTY" in capsys.readouterr().out
