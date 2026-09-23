"""THE FORECAST CONTRACT (P4) AND THE CHALLENGE LEAGUE (P7/P41/P79).

Two properties are worth fencing here, and neither is about arithmetic.

FIRST: a belief that cannot be scored must be REFUSED at publication, not stored and skipped
later. A register that silently drops unscoreable rows reports a clean sample and a plausible n,
and the model publishing garbage looks identical to the model publishing well. That is the same
silent-success shape as every other defect this desk has found the hard way.

SECOND: the league must REFUSE to rank models that did not face the same test. An unequal
comparison is the easiest way to manufacture a champion and it never looks like cheating from
the inside -- a model scored through a calm month simply has a better number than one scored
through a crash, and nothing in the arithmetic objects. So the refusal has to be a tested
property, not a docstring.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_RESEARCH = _ROOT / "desks" / "mt5" / "research"


def _load(name: str):
    spec = importlib.util.spec_from_file_location("_" + name, _RESEARCH / f"{name}.py")
    assert spec and spec.loader, f"{name}.py is missing"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fc():
    return _load("forecast_contract")


@pytest.fixture(scope="module")
def zoo():
    return _load("model_zoo")


# --------------------------------------------------------------------------- contract
def _ok(fc, **over):
    base = {"model_id": "m1", "subject": "XAUUSD/up", "kind": "PROBABILITY", "value": 0.62,
            "horizon_s": 3600, "at": "2026-09-06T02:00:00+00:00"}
    return fc.Belief(**(base | over))


def test_a_well_formed_belief_is_accepted(fc) -> None:
    assert fc.defects(_ok(fc)) == []


@pytest.mark.parametrize(("over", "must_mention"), [
    ({"model_id": ""}, "model_id"),
    ({"subject": ""}, "subject"),
    ({"kind": "VIBES"}, "scoring rule"),
    ({"horizon_s": 0}, "horizon"),
    ({"horizon_s": -5}, "horizon"),
    ({"at": "not-a-time"}, "lookahead"),
    ({"value": 1.4}, "[0, 1]"),
    ({"value": "yes"}, "[0, 1]"),
    ({"confidence": 3.0}, "confidence"),
])
def test_every_unscoreable_belief_is_named_and_refused(fc, over, must_mention) -> None:
    """Each of these makes the belief ungradeable. None may pass silently."""
    bad = fc.defects(_ok(fc, **over))
    assert bad, f"{over} produced no defect -- an unscoreable belief would enter the register"
    assert any(must_mention in d for d in bad), (
        f"{over} -> {bad}, expected mention of {must_mention}")


def test_a_magnitude_belief_is_scored_by_a_different_rule(fc) -> None:
    """Using Brier on a magnitude silently rewards the wrong behaviour, which is worse than
    not scoring at all -- so the rule is part of the contract, not the scorer's choice."""
    assert fc.RULES["PROBABILITY"] != fc.RULES["MAGNITUDE"] != fc.RULES["DISTRIBUTION"]
    assert fc.defects(_ok(fc, kind="MAGNITUDE", value=-0.004)) == []
    assert fc.defects(_ok(fc, kind="MAGNITUDE", value="big"))


def test_refusals_are_recorded_not_dropped(fc, tmp_path) -> None:
    """THE DEFECT THIS PREVENTS. Dropping bad rows makes a broken model look like a quiet one."""
    reg = tmp_path / "register.jsonl"
    pub = fc.publish([_ok(fc), _ok(fc, model_id="", subject="")], register=reg)
    assert pub.counts() == {"accepted": 1, "refused": 1}
    rows = fc.read_register(reg)
    assert len(rows) == 2, "the refused belief vanished; its model now looks merely quiet"
    refused = [r for r in rows if r["status"] == "REFUSED"]
    assert refused and refused[0]["defects"], "a refusal with no reason cannot be acted on"


def test_a_belief_carries_no_position(fc) -> None:
    """P4's actual requirement: models publish beliefs and own no positions.

    If a size, a lot count or a direction-to-act ever appears on this dataclass, a research model
    has acquired a route to move money without passing the capital allocator.
    """
    fields = set(fc.Belief.__dataclass_fields__)
    for banned in ("size", "lots", "volume", "position", "order", "side", "sl", "tp", "risk"):
        assert banned not in fields, (
            f"Belief carries `{banned}` -- a model can now express a POSITION, and the "
            "separation that makes forecasting and sizing separately measurable is gone")


def test_lookahead_is_caught_at_publication(fc) -> None:
    """A feature stamped after the belief means the model saw the future."""
    row = {"at": "2026-09-06T02:00:00+00:00", "features": ["dxy_close"]}
    assert fc.leakage(row, {"dxy_close": "2026-09-06T01:00:00+00:00"}) is None
    late = fc.leakage(row, {"dxy_close": "2026-09-06T03:00:00+00:00"})
    assert late and "lookahead" in late


def test_horizons_bucket_so_unlike_forecasts_are_never_compared(fc) -> None:
    assert fc.bucket_of(600) == "intraday"
    assert fc.bucket_of(20 * 3600) == "session"
    assert fc.bucket_of(5 * 86400) == "swing"
    assert fc.bucket_of(60 * 86400) == "position"


# --------------------------------------------------------------------------- league
def _entry(zoo, **over):
    base = {"model_id": "a", "bucket": "session", "delta_elog": 0.10, "n": 100,
            "window_start": "2026-08-01", "window_end": "2026-09-01"}
    return zoo.Entry(**(base | over))


def test_two_models_on_the_same_test_are_comparable(zoo) -> None:
    assert zoo.comparable(_entry(zoo), _entry(zoo, model_id="b")) == []


@pytest.mark.parametrize(("over", "must_mention"), [
    ({"bucket": "intraday"}, "horizon"),
    ({"window_start": "2026-01-01"}, "evaluation window"),
    ({"cost_model": "optimistic"}, "cost model"),
    ({"n": 5}, "shared evidence"),
])
def test_an_unequal_test_is_refused_never_silently_ranked(zoo, over, must_mention) -> None:
    """THE POINT OF THE MODULE. Each of these produces a better number without more skill."""
    why = zoo.comparable(_entry(zoo), _entry(zoo, model_id="b", **over))
    assert why, f"{over} was treated as a fair comparison -- that is how a champion is faked"
    assert any(must_mention in w for w in why), f"{over} -> {why}"


def test_rent_can_make_a_more_accurate_model_lose(zoo) -> None:
    """dElog after rent, not accuracy. A model 2% better at 4x the compute has not earned it."""
    cheap = _entry(zoo, model_id="cheap", delta_elog=0.10, compute_hours=1)
    dear = _entry(zoo, model_id="dear", delta_elog=0.11, compute_hours=100)
    per_hour = 0.02
    assert zoo.rent(dear, per_hour)["net_delta_elog"] < zoo.rent(cheap, per_hour)["net_delta_elog"], (  # noqa: E501
        "the more accurate but far more expensive model still wins -- rent is not being charged, "
        "and the desk will keep buying capability it cannot afford")


def test_the_smaller_model_wins_at_equal_skill(zoo) -> None:
    """P41: smallest model at equal rent. Capacity is not free even when compute is."""
    small = _entry(zoo, model_id="small", params=10_000)
    big = _entry(zoo, model_id="big", params=10_000_000)
    assert zoo.rent(small, 0.02)["net_delta_elog"] > zoo.rent(big, 0.02)["net_delta_elog"]


def test_complexity_rent_never_outranks_a_real_skill_difference(zoo) -> None:
    """A rent that dominates skill is not a rent, it is a cap on capability."""
    big_better = _entry(zoo, model_id="big", delta_elog=0.20, params=10_000_000)
    small_worse = _entry(zoo, model_id="small", delta_elog=0.10, params=1_000)
    assert (zoo.rent(big_better, 0.02)["net_delta_elog"]
            > zoo.rent(small_worse, 0.02)["net_delta_elog"])


def test_a_title_changes_only_on_a_gain_beyond_the_noise_band(zoo) -> None:
    """A challenger ahead by 0.001 is ahead by nothing; the incumbent holds ties."""
    close = zoo.league([_entry(zoo, model_id="champ", delta_elog=0.100),
                        _entry(zoo, model_id="chal", delta_elog=0.1005)], 0.02)["session"]
    assert close["verdict"]["decisive"] is False, "a noise-width lead took the title"
    assert "incumbent holds" in close["verdict"]["why"]

    clear = zoo.league([_entry(zoo, model_id="champ", delta_elog=0.100),
                        _entry(zoo, model_id="chal", delta_elog=0.300)], 0.02)["session"]
    assert clear["verdict"]["decisive"] is True, "a decisive, fairly-won lead was refused"


def test_a_leader_from_an_unfair_pairing_is_not_called_champion(zoo) -> None:
    """Ranking still produces an order; it must not produce a TITLE on an unequal test."""
    t = zoo.league([_entry(zoo, model_id="lucky", delta_elog=0.9, window_start="2026-01-01"),
                    _entry(zoo, model_id="honest", delta_elog=0.1)], 0.02)["session"]
    assert t["verdict"]["decisive"] is False
    assert "not judged on the same test" in t["verdict"]["why"]
    assert t["incomparable"], "the unfair pairing was not reported"


def test_an_empty_zoo_reports_a_gap_not_a_pass(zoo, capsys) -> None:
    """ABSENCE IS NEVER A PASS (L1.28a). "No models yet" must not read like "all models fine"."""
    doc = zoo.run()
    if doc["entrants"] == 0:
        zoo.main([])
        assert "NO ENTRANTS" in capsys.readouterr().out
