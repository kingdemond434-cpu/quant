"""PROMOTING A MOAT SURVIVOR -- and the four ways a persistent finding is still nothing.

The screen hunts continuously and records every triple it promotes. Nothing read that file, which
made the survivor registry a diary. This organ reads it and turns persistence into a FORWARD
CLOCK -- never capital.

Everything here is about the bar. Romano-Wolf controls family-wise error inside one screening
pass; across thousands of passes nothing does, so "it survived" is not evidence on its own. The
tests that matter most are the two controls: a sweep of pure noise must promote NOTHING, and a
candidate that genuinely beats the sweep's own rate MUST be promoted -- an organ that never
promotes is indistinguishable from a broken one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.promote_moat_survivors as P  # noqa: E402


def _entry(*, survived: int, screened: int, cells: int = 3, stab: float = 1.0,
           sym: str = "binance:BTCUSDT", mech: str = "hidden_liquidity",
           horizon: int = 60) -> dict:
    return {"symbol": sym, "mechanism": mech, "horizon_s": horizon,
            "times_survived": survived, "times_screened": screened,
            "cells": [f"{sym}@2026010{i}" for i in range(1, cells + 1)],
            "ic_mean": 0.08, "ic_sign_stability": stab, "best_p_adjusted": 0.004,
            "hit_rate": survived / max(screened, 1)}


def _registry(entries: dict[str, dict], filler: int = 40) -> dict:
    """The named entries plus a background of screened-and-never-survived triples, which is what
    sets the measured base rate. A registry of winners alone would report a base rate of 1.0."""
    reg = dict(entries)
    for i in range(filler):
        reg[f"filler{i}|imbalance|60"] = _entry(survived=0, screened=10, sym=f"v:S{i}")
    return reg


def _run(tmp_path: Path, registry: dict, screen: dict | None = None, **kw) -> dict:
    P.REGISTRY, P.SCREEN = tmp_path / "reg.json", tmp_path / "screen.json"
    P.PREREG, P.REPORT = tmp_path / "prereg.json", tmp_path / "promo.json"
    P.CLOCK_DIR, P.ROOT = tmp_path / "clocks", tmp_path
    P.REGISTRY.write_text(json.dumps(registry), "utf-8")
    P.SCREEN.write_text(json.dumps(screen or {"results": []}), "utf-8")
    sys.argv = ["promote_moat_survivors.py", *(["--dry-run"] if kw.get("dry") else [])]
    assert P.main() == 0
    return json.loads(P.REPORT.read_text("utf-8"))


# ------------------------------------------------------------------- the derived bar

def test_the_base_rate_is_measured_from_the_registry_not_assumed() -> None:
    """THE WHOLE STATISTICAL CONTENT. The sweep's own empirical promotion rate is what a
    persistent candidate has to beat -- so when the screen gets looser the bar rises by itself and
    nobody has to remember to retune it."""
    reg = _registry({"a|m|60": _entry(survived=3, screened=6)})
    p, surv, seen = P.base_rate(reg)
    assert surv == 3 and seen == 6 + 40 * 10
    assert abs(p - 3 / 406) < 1e-9


def test_the_binomial_tail_is_exact_and_monotone() -> None:
    assert P.binom_tail(0, 10, 0.1) == 1.0
    assert P.binom_tail(10, 10, 0.5) == 0.5**10
    assert P.binom_tail(3, 10, 0.1) > P.binom_tail(5, 10, 0.1)
    assert P.binom_tail(1, 0, 0.5) == 1.0          # no screenings -> no claim


# ---------------------------------------------------------------------- the controls

def test_a_sweep_of_pure_noise_promotes_nothing(tmp_path) -> None:
    """THE NEGATIVE CONTROL. Every triple survives at exactly the sweep's own rate, so no
    candidate is more surprising than the sweep's background -- which is what a false positive
    looks like from the inside."""
    reg = {}
    for i in range(60):
        reg[f"v:S{i}|imbalance|60"] = _entry(survived=1 if i < 6 else 0, screened=10,
                                             sym=f"v:S{i}")
    rep = _run(tmp_path, reg)
    assert rep["promoted"] == [], f"noise promoted: {rep['promoted']}"
    assert any(r["refused"] == "NOT-BEYOND-CHANCE" for r in rep["refused"])


def test_a_candidate_that_genuinely_beats_the_sweep_IS_promoted(tmp_path) -> None:
    """THE POSITIVE CONTROL, AND THE MORE IMPORTANT ONE. An organ that never promotes anything is
    indistinguishable from a broken organ, and 'nothing promoted' from it would mean nothing."""
    reg = _registry({"binance:BTCUSDT|hidden_liquidity|60": _entry(survived=6, screened=7)})
    rep = _run(tmp_path, reg)
    assert rep["promoted"], "a candidate surviving 6 of 7 against a ~1% base rate must promote"
    assert rep["promoted"][0]["p_persistence"] < P.ALPHA


# ------------------------------------------------------------------- the four refusals

def test_two_survivals_on_one_cell_is_one_tape_read_twice(tmp_path) -> None:
    reg = _registry({"x|hidden_liquidity|60": _entry(survived=6, screened=7, cells=1)})
    rep = _run(tmp_path, reg)
    assert rep["promoted"] == []
    assert rep["refused"][0]["refused"] == "ONE-CELL"


def test_a_sign_that_flips_is_a_fit_not_an_effect(tmp_path) -> None:
    """Checked BEFORE magnitude, because a large mean IC assembled from opposing days is the more
    convincing lie -- the cancellation hides the instability."""
    reg = _registry({"x|hidden_liquidity|60": _entry(survived=6, screened=7, stab=0.2)})
    rep = _run(tmp_path, reg)
    assert rep["promoted"] == []
    assert rep["refused"][0]["refused"] == "SIGN-UNSTABLE"


def test_one_for_one_is_a_hundred_percent_hit_rate_and_means_nothing(tmp_path) -> None:
    reg = _registry({"x|hidden_liquidity|60": _entry(survived=1, screened=1)})
    rep = _run(tmp_path, reg)
    assert rep["promoted"] == []
    assert rep["refused"][0]["refused"] == "TOO-FEW-SCREENINGS"


def test_persistence_cannot_rehabilitate_an_alignment_artifact(tmp_path) -> None:
    """The desk's own bithumb IC-0.72 fake was persistent too. It was persistently misaligned."""
    reg = _registry({"binance:BTCUSDT|hidden_liquidity|60": _entry(survived=6, screened=7)})
    screen = {"results": [{"symbol": "binance:BTCUSDT@20260101", "mechanism": "hidden_liquidity",
                           "verdict": "SUSPECT-LOOKAHEAD"}]}
    rep = _run(tmp_path, reg, screen)
    assert rep["promoted"] == []
    assert rep["refused"][0]["refused"] == "SUSPECT-LOOKAHEAD"


def test_a_sweep_promoting_a_third_of_everything_promotes_nothing_at_all(tmp_path) -> None:
    """A base rate this high is a fact about the SCREEN, not about the tape. Promoting off a
    mis-calibrated sweep would industrialise the error rather than find an edge."""
    reg = {f"v:S{i}|imbalance|60": _entry(survived=4, screened=10, sym=f"v:S{i}")
           for i in range(20)}
    rep = _run(tmp_path, reg)
    assert rep["stats"]["state"] == "SWEEP-MISCALIBRATED"
    assert rep["promoted"] == [] and rep["refused"] == []


# ------------------------------------------------------------------ what promotion buys

def test_promotion_buys_a_forward_clock_and_nothing_else(tmp_path) -> None:
    """The two-stage law is unchanged: stage A moves a candidate into the waiting room, and the
    waiting room's rent is paid in days, not in capital."""
    reg = _registry({"binance:BTCUSDT|hidden_liquidity|60": _entry(survived=6, screened=7)})
    rep = _run(tmp_path, reg)
    assert rep["authority"].startswith("PRE-REGISTRATION ONLY")
    prereg = json.loads((tmp_path / "prereg.json").read_text("utf-8"))
    rec = next(iter(prereg.values()))
    clock = tmp_path / rec["clock"]
    assert clock.exists()
    line = json.loads(clock.read_text("utf-8").splitlines()[-1])
    assert "no capital" in line["authority"]
    src = Path("scripts/promote_moat_survivors.py").read_text("utf-8")
    for banned in ("gated_leverage", "allocate_with_capacity", "place_order", "weights"):
        assert banned not in src, f"the promoter must not reach sizing: {banned}"


def test_the_clock_advances_once_per_day_not_once_per_run(tmp_path) -> None:
    """The screen runs continuously by design. If each pass advanced the clock, 'ninety forward
    days' would be reachable in an afternoon -- which would make the waiting room free."""
    reg = _registry({"binance:BTCUSDT|hidden_liquidity|60": _entry(survived=6, screened=7)})
    _run(tmp_path, reg)
    _run(tmp_path, reg)
    _run(tmp_path, reg)
    prereg = json.loads((tmp_path / "prereg.json").read_text("utf-8"))
    rec = next(iter(prereg.values()))
    assert rec["clock_days"] == 1, "three runs in one day must be one forward day"


def test_a_dry_run_adjudicates_without_starting_anything(tmp_path) -> None:
    reg = _registry({"binance:BTCUSDT|hidden_liquidity|60": _entry(survived=6, screened=7)})
    rep = _run(tmp_path, reg, dry=True)
    assert rep["promoted"] and rep["clocks_advanced"] == 0
    assert not (tmp_path / "prereg.json").exists()
    assert not (tmp_path / "clocks").exists()


def test_refusals_are_reported_with_their_reasons_not_dropped(tmp_path) -> None:
    """A promotion list without its refusals is a highlight reel. 'We looked and said no, because
    X' is the finding that stops the same candidate being re-litigated every cycle."""
    reg = _registry({"a|hidden_liquidity|60": _entry(survived=1, screened=1),
                     "b|book_slope|60": _entry(survived=6, screened=7, cells=1, sym="b"),
                     "c|imbalance|60": _entry(survived=6, screened=7, stab=0.1, sym="c")})
    rep = _run(tmp_path, reg)
    reasons = {r["refused"] for r in rep["refused"]}
    assert {"TOO-FEW-SCREENINGS", "ONE-CELL", "SIGN-UNSTABLE"} <= reasons
    assert all(r.get("why") for r in rep["refused"])


def test_an_absent_registry_is_reported_not_invented(tmp_path) -> None:
    P.REGISTRY, P.SCREEN = tmp_path / "nope.json", tmp_path / "screen.json"
    P.PREREG, P.REPORT = tmp_path / "prereg.json", tmp_path / "promo.json"
    P.CLOCK_DIR, P.ROOT = tmp_path / "clocks", tmp_path
    sys.argv = ["promote_moat_survivors.py"]
    assert P.main() == 0
    rep = json.loads((tmp_path / "promo.json").read_text("utf-8"))
    assert rep["state"] == "NO REGISTRY"
