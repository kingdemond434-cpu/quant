"""ACCEPTANCE TESTS OWED: the principal's external reviewer, 2026-10-06 (desk half).

Each finding carries a PLAIN test pinning the reproduction at LIVE 2d61e69a1 (the defect exists
today, measured on the real module) and a STRICT XFAIL acceptance test asserting the correct
behaviour. While the defect stands CI is green; the day a builder fixes it the acceptance test
XPASSes, strict fails the run, and the fixer removes the marker AND the now-false reproduction pin
in the same change.

Owners:
  allocator_trigger, fast-path world cache, heat_policy   -> "Growth allocator overhaul" (desktop)
  forecast_contract                                       -> "World sensor and macro surprise"
  acquire_datasets, source_evig                           -> "Global data discovery and use"

The portfolio-library half (robust_elog concavity, multiperiod, decay) lives in
tests/portfolio/test_reviewer_findings_2026_10_06.py.
"""
from __future__ import annotations

import io
import json
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import acquire_datasets as acq  # noqa: E402
from research import allocator_trigger as at  # noqa: E402
from research import forecast_contract as fc  # noqa: E402
from research import heat_policy as hp  # noqa: E402
from research import source_evig as evig  # noqa: E402

ALLOC = "owner: Growth allocator overhaul (desktop)"
SENSOR = "owner: World sensor and macro surprise"
DATA = "owner: Global data discovery and use"


# ================================================ finding 2: allocator_trigger consumes on SIGHT
#
# allocator_trigger.poll stores every source's new signature as "seen" (allocator_trigger.py:225)
# BEFORE deciding whether it will solve (debounce at :229, solve at :230-264). A change that is
# debounced, or whose solve FAILS, has already been consumed, and the next pass sees no change.


class _Harness:
    """One watched file under tmp, a fake solver, and the real `poll`."""

    def __init__(self, tmp: Path, monkeypatch: pytest.MonkeyPatch, rc: int = 0) -> None:
        self.file = tmp / "MACRO_VIEW.json"
        self.file.write_text(json.dumps({"labels": {"usd": "up"}}), encoding="utf-8")
        self.calls = 0
        self.rc = rc
        monkeypatch.setattr(at, "ROOT", tmp)
        monkeypatch.setattr(at, "sources", lambda: [
            at.Source("macro_surprise", self.file, ("labels",), "test source")])
        monkeypatch.setattr(at, "_heat_now", lambda: 0.20)
        monkeypatch.setattr(at, "_allocation_stamp", lambda: (None, None))

        def _solve(_budget: float) -> dict[str, Any]:
            self.calls += 1
            return {"rc": self.rc, "wall_s": 0.0, "tail": "fake solver"}

        monkeypatch.setattr(at, "_solve", _solve)

    def change(self) -> None:
        self.file.write_text(json.dumps({"labels": {"usd": "down"}}), encoding="utf-8")

    @staticmethod
    def poll(state: dict[str, Any], last_solve_at: float) -> dict[str, Any]:
        st = json.loads(json.dumps(state))
        st["last_solve_at"] = last_solve_at
        out: dict[str, Any] = at.poll(state=st, write=False, solve=True)
        return out


def _debounced_then_quiet(h: _Harness) -> tuple[dict[str, Any], dict[str, Any]]:
    base = h.poll({}, 0.0)                                   # first sight: baseline only
    h.change()
    deb = h.poll(base["state"], time.time())                 # inside MIN_SOLVE_GAP_S
    after = h.poll(deb["state"], 0.0)                        # window long expired, file unchanged
    return deb, after


def test_reproduction_trigger_debounced_change_is_never_served(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REPRODUCED (2a): the debounced pass records stood_down=DEBOUNCED and promises "served by
    the next pass, not dropped"; the next pass sees changed=False and the solver is never called."""
    h = _Harness(tmp_path, monkeypatch)
    deb, after = _debounced_then_quiet(h)
    assert deb["debounced"] is True
    assert deb["fired"][0]["stood_down"] == "DEBOUNCED"
    assert "not dropped" in deb["fired"][0]["why"]
    assert after["watch"][0]["changed"] is False
    assert h.calls == 0


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06 (2a): a change inside the debounce window is stored as seen "
    "and never solved (desks/mt5/research/allocator_trigger.py:225 vs :229). " + ALLOC))
def test_acceptance_trigger_debounced_change_stays_pending(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = _Harness(tmp_path, monkeypatch)
    _debounced_then_quiet(h)
    assert h.calls == 1, "the pending change must be solved on the first pass after the window"


def _failed_then_quiet(h: _Harness) -> dict[str, Any]:
    base = h.poll({}, 0.0)
    h.change()
    failed = h.poll(base["state"], 0.0)                      # solve fires and fails (rc=1)
    return h.poll(failed["state"], 0.0)                      # next pass, file unchanged


def test_reproduction_trigger_failed_solve_is_never_retried(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REPRODUCED (2b): rc=1, allocation_landed=False, and the next pass does not retry."""
    h = _Harness(tmp_path, monkeypatch, rc=1)
    after = _failed_then_quiet(h)
    assert h.calls == 1
    assert after["watch"][0]["changed"] is False
    assert after["fired"] == []


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06 (2b): a change whose solve failed is already marked seen "
    "(desks/mt5/research/allocator_trigger.py:225, last_solve set at :264 regardless of rc). "
    + ALLOC))
def test_acceptance_trigger_failed_solve_is_retried(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = _Harness(tmp_path, monkeypatch, rc=1)
    _failed_then_quiet(h)
    assert h.calls == 2, "an unacknowledged change must be retried until a solve succeeds"


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06 (2): trigger state keeps one 'sig' per source; observed, "
    "pending and consumed versions are not separate (allocator_trigger.py:207-225, :283). "
    + ALLOC))
def test_acceptance_trigger_state_separates_observed_pending_consumed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract: each per-source state row names its observed, pending and consumed versions,
    and after a debounced change pending != consumed."""
    h = _Harness(tmp_path, monkeypatch)
    deb, _ = _debounced_then_quiet(h)
    row = next(iter(deb["state"]["seen"].values()))
    assert {"observed", "pending", "consumed"} <= set(row), sorted(row)
    assert row["pending"] != row["consumed"]


# ========================================== finding 3: fast-path world cache has no fingerprint
#
# pf_allocator.run reuses CACHE/worlds.npz when `mode == "fast"` and the file is < 3600 s old
# (pf_allocator.py:3514) and its names match (:3517). The cache stores r/names/crisis/mu only
# (:3529), so a change in forecasts, regime, costs or config with the same names reuses worlds
# drawn on the OLD evidence; the fast clock also skips regime_state (:3401).

PF = DESK / "research" / "pf_allocator.py"


def test_reproduction_fast_cache_keyed_on_names_and_age_only() -> None:
    src = PF.read_text(encoding="utf-8")
    assert ('if mode == "fast" and cachef.exists() and time.time() - cachef.stat().st_mtime '
            '< 3600:') in src
    assert 'if tuple(z["names"]) == tuple(e.name for e in ev):' in src
    assert ("np.savez_compressed(cachef, r=worlds.r, names=np.array(worlds.names),\n"
            "                                crisis=worlds.crisis, mu=worlds.mu_draws)") in src
    assert ('labels, probs, regime_diag = (regime_state(daily) if mode in ("heavy", "normal")\n'
            '                                  else ((), (), {"skipped": f"{mode} clock"}))') in src
    assert "fingerprint" not in src[src.index('cachef = CACHE / "worlds.npz"'):
                                    src.index("# 1. WHAT GROWTH ACTUALLY WANTS")]


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: fast-path world cache reused on age<3600s + same names only "
    "(desks/mt5/research/pf_allocator.py:3514-3533); needs a decision-state fingerprint. "
    + ALLOC))
def test_acceptance_fast_cache_invalidated_by_decision_relevant_evidence() -> None:
    """Contract (rename freely, keep the substance): `pf_allocator.decision_state_fingerprint(ev,
    cfg)` is stable on identical inputs and changes when ANY decision-relevant input changes with
    the sleeve names held fixed -- returns, cost, decay hazard, regime probabilities, config --
    and the cache read in `run` compares it."""
    from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig
    from research import pf_allocator as pf

    fp = pf.decision_state_fingerprint
    r = np.tile([0.01, -0.005], 150)
    ev = [SleeveEvidence("a", r.copy()), SleeveEvidence("b", r.copy() * 0.5)]
    cfg = WorldConfig(n_worlds=128, n_rows=256)
    base = fp(ev, cfg)
    assert fp([SleeveEvidence("a", r.copy()), SleeveEvidence("b", r.copy() * 0.5)], cfg) == base
    variants = {
        "returns": ([SleeveEvidence("a", r.copy() * 2.0), ev[1]], cfg),
        "cost": ([SleeveEvidence("a", r.copy(), cost_bias_r=0.05), ev[1]], cfg),
        "decay": ([SleeveEvidence("a", r.copy(), decay_prob_i=0.9), ev[1]], cfg),
        "regime": (ev, WorldConfig(n_worlds=128, n_rows=256, regime_probs=(("trend", 1.0),))),
        "config": (ev, WorldConfig(n_worlds=128, n_rows=256, crisis_prob=0.2)),
    }
    for what, (e, c) in variants.items():
        assert fp(e, c) != base, f"{what} changed but the fingerprint did not"
    src = PF.read_text(encoding="utf-8")
    block = src[src.index('cachef = CACHE / "worlds.npz"'):
                src.index("# 1. WHAT GROWTH ACTUALLY WANTS")]
    assert "decision_state_fingerprint" in block


# ======================================= finding 6: heat_policy state adjustment is UP-ONLY
#
# heat_policy.resolve: "THE STATE MAY ONLY RAISE" (heat_policy.py:629-634) -- a measured state
# curve whose argmax inside [floor, ceiling] is BELOW the unconditional optimum is ignored.
#
# THE FLOOR (ALLOC-11, principal 2026-10-06 15:42Z "yes" in the Growth allocator thread): the
# fixed 20% utilisation floor (heat_policy.py:583) is replaced by a two-sided growth policy. The
# 20% target still holds the book up when the measured growth curve says it costs nothing; when
# the curve says 20% gives up growth (or growth is negative everywhere) exposure falls to the
# growth optimum, cash included. The survival bars, the effective-heat ceiling and the
# catastrophe guard stay.

GLOBAL_CURVE = {0.20: 0.0010, 0.22: 0.0012, 0.24: 0.0014, 0.26: 0.0016, 0.28: 0.0018,
                0.30: 0.0017}
CALM_CURVE = {0.20: 0.0010, 0.22: 0.0015, 0.24: 0.0012, 0.26: 0.0008, 0.28: 0.0005,
              0.30: 0.0001}


def _calm_verdict() -> hp.HeatVerdict:
    return hp.resolve(0.28, curve=GLOBAL_CURVE, state="calm",
                      curves={"calm": hp.StateCurve("calm", CALM_CURVE, 64)})


def test_reproduction_heat_state_adjustment_only_raises() -> None:
    """REPRODUCED: the calm state's own curve (64 worlds) peaks at 22%, inside the band, and the
    resolved heat stays 28% (binding="growth"); a state wanting 30% DOES raise 24% -> 30%."""
    v = _calm_verdict()
    assert v.state_optimum == pytest.approx(0.22)
    assert v.total_heat == pytest.approx(0.28)
    assert v.binding == "growth"
    up = hp.resolve(0.24, curve=GLOBAL_CURVE, state="up", curves={"up": hp.StateCurve(
        "up", {0.20: 0.0, 0.22: 0.0, 0.24: 0.0, 0.26: 0.0, 0.28: 0.0, 0.30: 0.002}, 64)})
    assert up.total_heat == pytest.approx(0.30) and up.binding == "state_growth"


NEGATIVE_CURVE = {0.0: 0.0, 0.10: -0.0005, 0.20: -0.0010, 0.25: -0.0015, 0.30: -0.0020}
COSTLY_FLOOR_CURVE = {0.0: 0.0, 0.10: 0.0020, 0.20: 0.0010, 0.25: 0.0006, 0.30: 0.0002}
FREE_FLOOR_CURVE = {0.10: 0.0010, 0.20: 0.0010, 0.25: 0.0010, 0.30: 0.0009}


def test_reproduction_flat_floor_holds_the_book_at_20_when_growth_is_negative() -> None:
    """REPRODUCED: with growth negative at every heat (optimum: cash) and a state curve agreeing,
    the flat floor still resolves the book to 20% (binding="mandate")."""
    v = hp.resolve(0.0, curve=NEGATIVE_CURVE, state="bad",
                   curves={"bad": hp.StateCurve("bad", NEGATIVE_CURVE, 64)})
    assert v.total_heat == pytest.approx(0.20)
    assert v.binding == "mandate"
    c = hp.resolve(0.10, curve=COSTLY_FLOOR_CURVE)
    assert c.total_heat == pytest.approx(0.20) and c.binding == "mandate"


def test_the_target_still_holds_the_book_up_when_it_costs_nothing() -> None:
    """KEPT UNDER ALLOC-11: when the measured curve says 20% gives up no growth, the 20% target
    still holds the book up. This holds today and must keep holding after the change."""
    v = hp.resolve(0.10, curve=FREE_FLOOR_CURVE)
    assert v.total_heat >= 0.20 - 1e-12


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06 (ALLOC-11, principal 'yes' 15:42Z): the flat 20% floor "
    "(desks/mt5/research/heat_policy.py:583, :617-626) holds the book at 20% when growth is "
    "negative everywhere. " + ALLOC))
def test_acceptance_negative_growth_everywhere_resolves_to_cash() -> None:
    """Growth negative at every heat: the growth optimum is cash, so the book resolves to 0."""
    v = hp.resolve(0.0, curve=NEGATIVE_CURVE, state="bad",
                   curves={"bad": hp.StateCurve("bad", NEGATIVE_CURVE, 64)})
    assert v.total_heat == pytest.approx(0.0, abs=1e-9)
    assert v.binding != "mandate"


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06 (ALLOC-11, principal 'yes' 15:42Z): the flat 20% floor "
    "(desks/mt5/research/heat_policy.py:583, :617-626) overrides a growth optimum of 10% that "
    "the measured curve pays 0.0020/day for against 0.0010/day at 20%. " + ALLOC))
def test_acceptance_a_costly_floor_yields_to_the_growth_optimum() -> None:
    """20% gives up real growth: exposure falls to the growth optimum (10% here)."""
    v = hp.resolve(0.10, curve=COSTLY_FLOOR_CURVE)
    assert v.total_heat == pytest.approx(0.10)
    assert v.binding != "mandate"


def test_the_catastrophe_guard_and_survival_bar_stay() -> None:
    """KEPT UNDER ALLOC-11: the survival bar still clips growth, whatever the floor becomes."""
    v = hp.resolve(0.30, curve=GLOBAL_CURVE, survival_ceiling=0.24)
    assert v.total_heat <= 0.24 + 1e-12
    assert v.binding == "survival_ceiling"


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: state adjustment is up-only ('THE STATE MAY ONLY RAISE', "
    "desks/mt5/research/heat_policy.py:629-634). " + ALLOC))
def test_acceptance_heat_state_adjustment_is_two_sided_above_the_floor() -> None:
    """The STATE adjustment inside the band is two-sided (the floor itself is covered by the
    ALLOC-11 acceptance tests above). Under Rule 1 a reduction must
    prove it raises robust forward E[log W]; the state's own growth curve, measured on that
    state's worlds (64 here, above MIN_STATE_WORLDS), IS that measurement -- E[log W | calm]
    is 0.0015/day at 22% against 0.0005/day at 28%. So the book should resolve to 22%, which is
    still above the 20% floor."""
    v = _calm_verdict()
    assert v.total_heat == pytest.approx(0.22)
    assert v.total_heat >= v.floor


# ===================================== finding 7: forecast_contract accepts malformed quantiles
#
# forecast_contract.defects (forecast_contract.py:131-135) only checks that keys and values are
# finite numbers: levels outside (0,1) and non-monotone quantiles are publishable.

def _dist(value: dict[float, float]) -> fc.Belief:
    return fc.Belief(model_id="m", subject="XAUUSD:ret:1h", kind="DISTRIBUTION", value=value,
                     horizon_s=3600, at="2026-10-06T00:00:00+00:00")


BAD_LEVELS = {1.5: 1.0, -0.2: 0.5}
EDGE_LEVELS = {0.0: 1.0, 1.0: 2.0}
CROSSED = {0.1: 2.0, 0.9: -1.0}


def test_reproduction_forecast_accepts_bad_quantiles() -> None:
    """REPRODUCED: levels 1.5 / -0.2, levels 0.0 / 1.0 and q10=2.0 > q90=-1.0 all return []."""
    assert fc.defects(_dist(BAD_LEVELS)) == []
    assert fc.defects(_dist(EDGE_LEVELS)) == []
    assert fc.defects(_dist(CROSSED)) == []


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: DISTRIBUTION validator accepts levels outside (0,1) "
    "(desks/mt5/research/forecast_contract.py:131-135). " + SENSOR))
def test_acceptance_forecast_rejects_levels_outside_open_unit_interval() -> None:
    assert fc.defects(_dist(BAD_LEVELS))
    assert fc.defects(_dist(EDGE_LEVELS))


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: DISTRIBUTION validator accepts non-monotone quantiles, "
    "q10 > q90 (desks/mt5/research/forecast_contract.py:131-135). " + SENSOR))
def test_acceptance_forecast_rejects_crossed_quantiles() -> None:
    """Reject, or repair under a TESTED policy (e.g. rearrangement) that is recorded on the row;
    silently publishing a crossed distribution is the one outcome not allowed."""
    assert fc.defects(_dist(CROSSED))


# ====================================== finding 8: acquire_datasets drops information silently
#
# MIN_ROWS = 200 (acquire_datasets.py:66) is enforced inside _dated (:238), so a SHORT but
# properly dated series is refused as "no usable date column"; _numeric_series stops at six
# columns (:250); a zip keeps only its largest .csv/.txt/.tsv member (:200); and keyed URLs are
# skipped with `continue` (:319, :338) and named nowhere, though the module doc (:20) says
# "skipped and named".


def _csv(cols: dict[str, list[Any]]) -> bytes:
    text: str = pd.DataFrame(cols).to_csv(index=False)
    return text.encode("utf-8")


def _dates(n: int) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.date_range("2020-01-01", periods=n, freq="D")]


def _wide_csv(n_cols: int = 10, n: int = 300) -> bytes:
    # Column tokens carry a non-hex letter so a certificate hash can never match them by luck.
    rng = np.random.default_rng(0)
    cols: dict[str, list[Any]] = {"date": _dates(n)}
    for i in range(n_cols):
        cols[f"qcol{i}"] = list(rng.normal(0.0, 1.0, n))
    return _csv(cols)


def _two_member_zip() -> bytes:
    rng = np.random.default_rng(1)
    big = _csv({"date": _dates(400), "alpha": list(rng.normal(0, 1, 400))})
    small = _csv({"date": _dates(250), "beta": list(rng.normal(0, 1, 250))})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("big.csv", big)
        z.writestr("small.csv", small)
    return buf.getvalue()


def _short_csv() -> bytes:
    rng = np.random.default_rng(2)
    return _csv({"date": _dates(150), "gamma": list(rng.normal(0, 1, 150))})


KEYED = "https://example.org/data.csv?api_key=REDACTED"
PLAIN = "https://example.org/plain.csv"


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Every path acquire() touches, under tmp; certificates are not written."""
    store = tmp_path / "acquired"
    paths = {"store": store, "registry": store / "registry.json",
             "report": tmp_path / "dataset_acquisition.json", "world": tmp_path / "world"}
    paths["world"].mkdir()
    monkeypatch.setattr(acq, "STORE", store)
    monkeypatch.setattr(acq, "REGISTRY", paths["registry"])
    monkeypatch.setattr(acq, "REPORT", paths["report"])
    monkeypatch.setattr(acq, "WORLD", paths["world"])
    monkeypatch.setattr(acq, "DESK", tmp_path)                 # no country packs
    monkeypatch.setattr(acq, "_SEED_ENDPOINTS", ())
    monkeypatch.setattr(acq, "write_certificate", lambda cert: tmp_path / "cert.json")
    return paths


def _acquire_one(monkeypatch: pytest.MonkeyPatch, raw: bytes, url: str = PLAIN
                 ) -> dict[str, Any]:
    monkeypatch.setattr(acq, "_endpoints", lambda limit: [(url, "example.org")])
    monkeypatch.setattr(acq, "_fetch", lambda u: (raw, "text/csv"))
    rep: dict[str, Any] = acq.acquire(limit=5)
    return rep


def _all_text(paths: dict[str, Path], report: dict[str, Any]) -> str:
    reg = paths["registry"].read_text("utf-8") if paths["registry"].exists() else ""
    return json.dumps(report, default=str) + reg


def test_reproduction_acquire_six_column_cap(sandbox: dict[str, Path],
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """REPRODUCED: a dated file with 10 numeric columns persists 6 (qcol0..qcol5);
    qcol6..qcol9 vanish without a word in the report or registry."""
    rep = _acquire_one(monkeypatch, _wide_csv())
    names = sorted(rep["new_series"])
    assert len(names) == 6 and all(n.endswith(f"_qcol{i}") for i, n in enumerate(names))
    text = _all_text(sandbox, rep)
    assert all(f"qcol{i}" not in text for i in range(6, 10))


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: _numeric_series stops at 6 columns "
    "(desks/mt5/research/acquire_datasets.py:246-257, cap at :250). " + DATA))
def test_acceptance_acquire_every_column_ingested_or_surfaced(
        sandbox: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    rep = _acquire_one(monkeypatch, _wide_csv())
    text = _all_text(sandbox, rep)
    for i in range(10):
        assert any(n.endswith(f"_qcol{i}") for n in rep["new_series"]) or f"qcol{i}" in text, i


def test_reproduction_acquire_zip_keeps_largest_member_only(
        sandbox: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """REPRODUCED: a zip of big.csv (alpha, 400 rows) + small.csv (beta, 250 rows) yields alpha
    only; beta and small.csv are named nowhere."""
    rep = _acquire_one(monkeypatch, _two_member_zip(), "https://example.org/bulk.zip")
    assert [n.rsplit("_", 1)[-1] for n in rep["new_series"]] == ["alpha"]
    text = _all_text(sandbox, rep)
    assert "beta" not in text and "small.csv" not in text


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: zip archives keep only the largest member "
    "(desks/mt5/research/acquire_datasets.py:194-200). " + DATA))
def test_acceptance_acquire_every_archive_member_ingested_or_surfaced(
        sandbox: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    rep = _acquire_one(monkeypatch, _two_member_zip(), "https://example.org/bulk.zip")
    assert (any(n.endswith("_beta") for n in rep["new_series"])
            or "small.csv" in _all_text(sandbox, rep))


def test_reproduction_acquire_short_history_misreported_as_undated(
        sandbox: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """REPRODUCED: 150 cleanly dated daily rows are refused as "no usable date column" -- the
    MIN_ROWS=200 bar sits inside the DATE check, so a short history is mislabelled undated."""
    rep = _acquire_one(monkeypatch, _short_csv())
    assert acq.MIN_ROWS == 200
    assert rep["new_series"] == []
    assert rep["refusals"] == {"no usable date column -- refused rather than stamped with now": 1}


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: MIN_ROWS=200 is applied inside _dated, so short dated "
    "series are refused as undated (desks/mt5/research/acquire_datasets.py:66, :227, :238). "
    + DATA))
def test_acceptance_acquire_short_history_has_its_own_policy(
        sandbox: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """A short but dated series is either ingested (flagged short) or refused under a reason that
    SAYS short history -- never as undated."""
    rep = _acquire_one(monkeypatch, _short_csv())
    reasons = " ".join(rep["refusals"])
    assert "no usable date column" not in reasons
    assert rep["new_series"] or "short" in reasons.lower() or "history" in reasons.lower()


def test_reproduction_acquire_keyed_sources_skipped_unnamed(
        sandbox: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """REPRODUCED: a crawler discovery listing a keyed and a plain endpoint yields only the plain
    one from _endpoints, and the keyed URL appears nowhere in the report or registry."""
    (sandbox["world"] / "discoveries_20261006.json").write_text(
        json.dumps([{"host": "example.org", "endpoints": [KEYED, PLAIN]}]), encoding="utf-8")
    assert acq._endpoints(10) == [(PLAIN, "example.org")]
    monkeypatch.setattr(acq, "_fetch", lambda u: (None, "html"))
    rep = acq.acquire(limit=10)
    text = _all_text(sandbox, rep)
    assert PLAIN in text and KEYED not in text and "api_key" not in text


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: keyed sources are dropped with `continue` and named nowhere "
    "(desks/mt5/research/acquire_datasets.py:319, :338; doc at :20 says 'skipped and named'). "
    + DATA))
def test_acceptance_acquire_keyed_sources_are_surfaced(
        sandbox: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    (sandbox["world"] / "discoveries_20261006.json").write_text(
        json.dumps([{"host": "example.org", "endpoints": [KEYED, PLAIN]}]), encoding="utf-8")
    monkeypatch.setattr(acq, "_fetch", lambda u: (None, "html"))
    rep = acq.acquire(limit=10)
    assert KEYED in _all_text(sandbox, rep)


# ======================================= finding 9: source_evig novelty is keyed on symbols only
#
# source_evig.price (source_evig.py:178-197): `covered` counts collected sources per TARGET
# SYMBOL and novelty is the share of a source's symbols nobody covers, so a new observable or
# mechanism about an already-covered instrument scores the same 0.0 as a duplicate feed.

_SOURCES = [
    {"id": "cot_gold", "targets": ["XAUUSD"], "observable": "cftc_net_positioning",
     "mechanism": "positioning", "cadence": "weekly"},
    {"id": "cot_gold_mirror", "targets": ["XAUUSD"], "observable": "cftc_net_positioning",
     "mechanism": "positioning", "cadence": "weekly"},
    {"id": "gold_options_skew", "targets": ["XAUUSD"], "observable": "options_25d_risk_reversal",
     "mechanism": "options_skew", "cadence": "weekly"},
    {"id": "cot_silver", "targets": ["XAGUSD"], "observable": "cftc_net_positioning",
     "mechanism": "positioning", "cadence": "weekly"},
]
_STATE = {"cot_gold": {"last_status": "COLLECTED"}}


def _priced(tmp: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, Any]]:
    monkeypatch.setattr(evig, "VAULT", tmp / "vault")
    return {r["id"]: r for r in evig.price(_SOURCES, _STATE, {})}


def test_reproduction_evig_new_observable_scores_like_a_duplicate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REPRODUCED: with cot_gold collected, the options-skew source (new observable, new
    mechanism, same instrument) scores novelty 0.0 -- identical to a mirror of cot_gold -- while
    a COT feed on silver scores 1.0."""
    rows = _priced(tmp_path, monkeypatch)
    assert rows["gold_options_skew"]["novelty"] == 0.0
    assert rows["cot_gold_mirror"]["novelty"] == 0.0
    assert rows["cot_silver"]["novelty"] == 1.0


@pytest.mark.xfail(strict=True, reason=(
    "ACCEPTANCE OWED 2026-10-06: novelty keyed on target symbols only "
    "(desks/mt5/research/source_evig.py:178-197). " + DATA))
def test_acceptance_evig_novelty_separates_information_from_coverage(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A new observable/mechanism on a covered instrument is NEW INFORMATION and must out-score
    a duplicate feed of an observable already collected."""
    rows = _priced(tmp_path, monkeypatch)
    assert rows["gold_options_skew"]["novelty"] > rows["cot_gold_mirror"]["novelty"]
    assert rows["gold_options_skew"]["evig"] > rows["cot_gold_mirror"]["evig"]
