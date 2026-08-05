"""Regression tests for the Stage-A order-book-state screen and its alignment primitives.

WHAT THESE PIN, AND WHY EACH ONE EXISTS. The mechanism class under test is the desk's #1 ranked
untested one, and the reason it has never been screened is not missing data -- it is that book
state is CONCURRENT with price, so a naive screen of it manufactures an IC that is a restatement of
the bar that just finished. Every prior kill on the neighbouring informed-order-flow class died
exactly there. So the tests are about the two things that decide whether this screen is worth
anything:

  * the residualisation really removes the same-period component, and cannot see forward;
  * the alignment really excludes the bar containing the snapshot;

plus the two verdicts the screen must be able to tell apart on a fixture where the answer is known
by construction (a genuine lead, and pure coincidence), and the refusal to fabricate when the tape
is absent.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest
import scripts.screen_orderbook_state as S

from libs.research.moat_microstructure import read_partition
from libs.research.orderbook_state import (
    CONSTRUCTIONS,
    FORMS,
    Alignment,
    bar_close_states,
    boundary_prices,
    contiguous_mask,
    period_returns,
    residualise,
    snapshot_states,
)

BAR_MS = 60_000
T0 = 1_767_225_600_000          # 2026-01-01T00:00:00Z, a real UTC instant


# ---------------------------------------------------------------------------- synthetic fixtures

def _series(n: int, *, lead: bool, phi: float = 0.0, rho: float = 0.7,
            g: float = 0.35, c: float = 0.9, seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    """(book state, same-bar return) where the answer is known BY CONSTRUCTION.

    `lead=True`  -- an AR(1) latent book state drives the NEXT bar's return (g), and the observed
                    state is additionally contaminated by the CURRENT bar's return (c). This is a
                    genuine lead wearing the concurrency that makes the class hard.
    `lead=False` -- the state is PURE concurrency (no g term at all), but returns are
                    autocorrelated (phi). That combination is what fakes a forward IC: contaminated
                    state at k correlates with r[k], and r[k] correlates with r[k+1]. It is the
                    coinbase/turkey/kimchi shape, generated deliberately.

    The lead DECAYS (the state is AR(1)) rather than being a one-period shift, because a pure
    one-period shift is the signature `axis_screen`'s own lookahead rail fires on -- correctly.
    """
    rng = np.random.default_rng(seed)
    s = np.zeros(n)
    u = rng.normal(size=n)
    for k in range(1, n):
        s[k] = rho * s[k - 1] + u[k]
    s /= s.std()
    eps = rng.normal(size=n)
    r = np.zeros(n)
    for k in range(1, n):
        r[k] = phi * r[k - 1] + (g * s[k - 1] if lead else 0.0) + eps[k]
    r = r / r.std() * 0.0008
    rz = r / r.std()
    x = (s if lead else np.zeros(n)) + c * rz + 0.6 * rng.normal(size=n)
    return x, r


def _write_tape(path: Path, state: np.ndarray, ret: np.ndarray, *,
                bar_ms: int = BAR_MS, t0: int = T0, p0: float = 50_000.0) -> Path:
    """A gzip-jsonl partition in the Binance recorder schema, built to the DECLARED alignment.

    Per bar k (right edge b_k = t0 + (k+1)*bar_ms):
      * a DECOY print early inside bar k at a deliberately wrong price -- it must never reach the
        target, because the target is priced at or after b_k;
      * two depth snapshots inside bar k, the LAST of which carries state[k];
      * the boundary print at exactly b_k, which IS the price the target must use.
    """
    px = p0 * np.cumprod(1.0 + np.asarray(ret, dtype="float64"))
    rows: list[dict[str, object]] = []
    for k in range(len(state)):
        edge = t0 + (k + 1) * bar_ms
        rows.append({"t": edge - bar_ms + 5, "k": "t",
                     "p": round(float(px[k]) * 1.05, 4), "q": 0.5, "m": False})
        for offset, val in ((2_000, 0.0), (1_000, float(state[k]))):
            xi = max(-0.95, min(0.95, val / 4.0))
            bids = [[round(float(px[k]) * (1 - 0.0002 - i * 0.0001), 4),
                     round(10.0 * (1 + xi) * (0.9 ** i), 6)] for i in range(5)]
            asks = [[round(float(px[k]) * (1 + 0.0002 + i * 0.0001), 4),
                     round(10.0 * (1 - xi) * (0.9 ** i), 6)] for i in range(5)]
            rows.append({"t": edge - offset, "k": "d", "b": bids, "a": asks})
        rows.append({"t": edge, "k": "t", "p": round(float(px[k]), 4), "q": 1.0, "m": True})
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def _cell_rows(path: Path, label: str, *, decision_lag_ms: int = 0) -> list[dict[str, object]]:
    rows = S.screen_cell(label, list(read_partition(path)), decision_lag_ms=decision_lag_ms)
    scored = [r for r in rows if isinstance(r.get("ic"), (int, float))]
    S._significance(scored, n_family=S.PREREGISTERED_FAMILY)
    S._type2(scored, n_family=S.PREREGISTERED_FAMILY)
    return rows


def _pick(rows: list[dict[str, object]], construction: str, form: str,
          bar_ms: int = BAR_MS) -> dict[str, object]:
    hits = [r for r in rows if r.get("construction") == construction
            and r.get("form") == form and r.get("bar_ms") == bar_ms]
    assert len(hits) == 1, f"expected exactly one {construction}/{form}@{bar_ms}, got {len(hits)}"
    return hits[0]


# --------------------------------------------------------------------- the residualisation itself

def test_residualisation_removes_same_period_correlation():
    """THE LOAD-BEARING CLAIM, on a fixture where the answer is known: a state that is 91%
    same-period return must come out of `residualise` essentially orthogonal to it."""
    rng = np.random.default_rng(3)
    ret = rng.normal(0, 0.01, 2000)
    state = 0.9 * (ret / ret.std()) + rng.normal(0, 0.4, 2000)

    before = float(np.corrcoef(state, ret)[0, 1])
    resid = residualise(state, ret, min_obs=60)
    ok = np.isfinite(resid)
    after = float(np.corrcoef(resid[ok], ret[ok])[0, 1])

    assert before > 0.85, "fixture is not contaminated, so it tests nothing"
    assert abs(after) < 0.05, f"same-period correlation survived residualisation: {after}"
    assert int(ok.sum()) == 2000 - 60, "warmup must be exactly min_obs bars, no more, no fewer"


def test_residualisation_preserves_a_genuine_lead():
    """De-contamination must not be de-signalling. A state that leads keeps its forward IC."""
    rng = np.random.default_rng(5)
    ret = rng.normal(0, 0.01, 3000)
    fwd = np.roll(ret, -1)
    state = 0.9 * (ret / ret.std()) + 0.20 * (fwd / ret.std()) + rng.normal(0, 0.5, 3000)

    resid = residualise(state, ret, min_obs=60)
    ok = np.isfinite(resid)
    ok[-1] = False                                   # last bar has no forward return
    assert abs(float(np.corrcoef(resid[ok], fwd[ok])[0, 1])) > 0.15


def test_residualise_cannot_see_forward():
    """THE PROPERTY THAT MAKES THE RESIDUAL TRADEABLE. Perturbing a FUTURE return must leave every
    earlier residual bit-identical -- a full-sample beta would change all of them, silently, and
    would look exactly like preprocessing."""
    rng = np.random.default_rng(9)
    ret = rng.normal(0, 0.01, 800)
    state = 0.7 * (ret / ret.std()) + rng.normal(0, 0.5, 800)

    base = residualise(state, ret, min_obs=60)
    poked = ret.copy()
    poked[500] += 5.0                                # a return that has not happened yet at k<500
    after = residualise(state, poked, min_obs=60)

    assert np.array_equal(base[:500], after[:500], equal_nan=True)
    assert not np.array_equal(base[500:], after[500:], equal_nan=True), \
        "the perturbation must matter from its own bar onward, or the test proves nothing"


def test_residualise_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="length mismatch"):
        residualise(np.zeros(10), np.zeros(11))


# ------------------------------------------------------------------------------- alignment is law

def test_bar_close_takes_the_last_snapshot_strictly_inside_the_bar():
    al = Alignment(bar_ms=BAR_MS)
    rows = [
        {"t": T0 + 10_000, "k": "d", "b": [[100.0, 1.0]], "a": [[101.0, 9.0]]},
        {"t": T0 + 59_999, "k": "d", "b": [[100.0, 9.0]], "a": [[101.0, 1.0]]},
        {"t": T0 + 60_000, "k": "d", "b": [[100.0, 1.0]], "a": [[101.0, 1.0]]},
    ]
    ms, states = snapshot_states(rows)
    edges, closes = bar_close_states(ms, states, alignment=al)

    assert edges.tolist() == [T0 + 60_000, T0 + 120_000]
    # bar 0 closes on the 59_999ms snapshot (9 bid vs 1 ask -> +0.8), NOT the one AT the edge,
    # which belongs to bar 1 because the interval is half-open.
    assert closes["obi_touch"][0] == pytest.approx(0.8)
    assert closes["obi_touch"][1] == pytest.approx(0.0)


def test_target_is_priced_at_or_after_the_bar_edge_never_inside_it():
    """A snapshot at t never sees the bar containing t: prints strictly inside bar k cannot reach
    the price that opens the forward window at b_k."""
    al = Alignment(bar_ms=BAR_MS)
    edges = np.array([T0 + BAR_MS, T0 + 2 * BAR_MS], dtype="int64")
    t_ms = np.array([T0 + 5, T0 + BAR_MS - 1, T0 + BAR_MS, T0 + 2 * BAR_MS], dtype="int64")
    t_px = np.array([1.0, 2.0, 3.0, 4.0])

    p = boundary_prices(t_ms, t_px, edges, alignment=al)
    assert p.tolist() == [3.0, 4.0]                  # the AT-edge prints, not the inside ones

    # Rewriting every print INSIDE the bars leaves the boundary prices untouched.
    t_px2 = np.array([999.0, 888.0, 3.0, 4.0])
    assert boundary_prices(t_ms, t_px2, edges, alignment=al).tolist() == [3.0, 4.0]


def test_decision_lag_can_only_move_the_target_later():
    al0 = Alignment(bar_ms=BAR_MS)
    al1 = Alignment(bar_ms=BAR_MS, decision_lag_ms=500)
    edges = np.array([T0 + BAR_MS], dtype="int64")
    t_ms = np.array([T0 + BAR_MS, T0 + BAR_MS + 400, T0 + BAR_MS + 900], dtype="int64")
    t_px = np.array([10.0, 11.0, 12.0])

    assert boundary_prices(t_ms, t_px, edges, alignment=al0)[0] == pytest.approx(10.0)
    assert boundary_prices(t_ms, t_px, edges, alignment=al1)[0] == pytest.approx(12.0)


def test_period_return_is_contemporaneous_not_forward():
    """`axis_screen` does the forward shift itself; handing it an already-forward target makes it
    shift twice, which its own lookahead rail then reads as misalignment."""
    r = period_returns(np.array([100.0, 110.0, 121.0]))
    assert np.isnan(r[0])
    assert r[1] == pytest.approx(0.10)
    assert r[2] == pytest.approx(0.10)


def test_gapped_bars_are_dropped_not_priced():
    al = Alignment(bar_ms=BAR_MS)
    edges = np.array([T0 + BAR_MS, T0 + 2 * BAR_MS, T0 + 50 * BAR_MS], dtype="int64")
    m = contiguous_mask(edges, alignment=al)
    assert m.tolist() == [False, True, False]


def test_a_recorder_outage_never_becomes_a_period(tmp_path):
    """Two non-adjacent stretches of tape must not be joined by a period that spans the outage.

    One twelve-hour "60-second" return would both dominate an IC computed over hundreds AND drag
    the expanding beta that every later residual is built from -- which is why the gap is blanked
    BEFORE the orthogonalisation, not merely masked out of the correlation afterwards.
    """
    state, ret = _series(300, lead=False)
    first = _write_tape(tmp_path / "a.jsonl.gz", state[:150], ret[:150])
    second = _write_tape(tmp_path / "b.jsonl.gz", state[150:], ret[150:],
                         t0=T0 + 400 * BAR_MS)               # a 250-bar hole in the recording
    recs = list(read_partition(first)) + list(read_partition(second))

    rows = S.screen_cell("fut:BTCUSDT@20260101", recs, decision_lag_ms=0)
    row = _pick(rows, "obi_touch", "raw")
    assert row["gap_breaks"] == 1
    # 300 bars, minus the first (no preceding period) and minus the one that would have spanned
    # the outage. Nothing else is lost, so the drop is surgical rather than a truncation.
    assert row["n_paired"] == 298


def test_alignment_is_echoed_and_declares_its_lookahead_risk():
    d = Alignment(bar_ms=BAR_MS).as_dict()
    assert d["excludes_current_bar"] is True
    assert d.get("lookahead_risk")
    assert d["horizon_days"] == pytest.approx(BAR_MS / 86_400_000.0)


@pytest.mark.parametrize("bad", [{"bar_ms": 0}, {"bar_ms": BAR_MS, "decision_lag_ms": -1}])
def test_alignment_rejects_impossible_rules(bad):
    with pytest.raises(ValueError):
        Alignment(**bad)


# ------------------------------------------------------------------- the two verdicts that matter

@pytest.mark.parametrize("form", list(FORMS))
def test_every_preregistered_cell_produces_a_row(tmp_path, form):
    """Clause 3: a construction that silently vanishes is indistinguishable from one never tried."""
    state, ret = _series(400, lead=True)
    rows = _cell_rows(_write_tape(tmp_path / "fut/BTCUSDT/20260101_00.jsonl.gz", state, ret),
                      "fut:BTCUSDT@20260101")
    got = {(r["construction"], r["bar_ms"]) for r in rows if r.get("form") == form}
    assert got == {(c, h) for c in CONSTRUCTIONS for h in S.HORIZONS_MS}


def test_a_leading_book_state_is_detected(tmp_path):
    """END TO END through the real tape, the real alignment and the audited harness: a state that
    genuinely leads must SURVIVE residualisation and clear the family-wise bar."""
    state, ret = _series(5000, lead=True)
    rows = _cell_rows(_write_tape(tmp_path / "fut/BTCUSDT/20260101_00.jsonl.gz", state, ret),
                      "fut:BTCUSDT@20260101")
    resid = _pick(rows, "obi_deep", "residualised")

    assert resid["verdict"] == "SCREEN-INTERESTING"
    assert resid["powered"] is True
    assert abs(float(resid["ic"])) > S.IC_MIN
    assert resid["clears_family_wise"] is True
    assert abs(float(resid["same_period_corr"])) < 0.2, "residual must not still be concurrent"

    survivors, _ = S.classify([r for r in rows if isinstance(r.get("ic"), (int, float))])
    assert any(s["construction"] == "obi_deep" and s["bar_ms"] == BAR_MS for s in survivors)

    # A survivor is not one of this run's recorded NEGATIVES, so the power headline -- which is a
    # statement about what the nulls know -- must not count it as an underpowered one.
    rep = S.build_report(rows, alignment=Alignment(bar_ms=BAR_MS), files_read=1,
                         files_on_disk=1, cells_screened=1, cells_on_disk=1)
    assert (rep["power_counts_at_family_charge"]["negatives"]
            == rep["scored"] - len(rep["survivors"]))
    assert rep["survivors"], "the leader must reach the artifact, not only classify()"


def test_charging_latency_weakens_the_reading(tmp_path):
    """THE DECLARED LOOK-AHEAD RISK, exercised rather than merely stated. decision_lag_ms=0 assumes
    a zero-latency fill and is an UPPER BOUND; charging a realistic round trip must move the number
    DOWN, which is what makes "re-run any survivor at the measured latency" a real control rather
    than a sentence in a docstring."""
    state, ret = _series(1500, lead=True)
    tape = _write_tape(tmp_path / "fut/BTCUSDT/20260101_00.jsonl.gz", state, ret)
    optimistic = _pick(_cell_rows(tape, "c"), "obi_deep", "residualised")
    charged = _pick(_cell_rows(tape, "c", decision_lag_ms=30_000), "obi_deep", "residualised")

    assert abs(float(charged["ic"])) < abs(float(optimistic["ic"]))
    assert charged["alignment"]["decision_lag_ms"] == 30_000


def test_a_merely_coincident_book_state_is_killed_as_an_artifact(tmp_path):
    """THE FAILURE MODE THIS WHOLE SCREEN EXISTS TO SURVIVE. The state carries NO forward
    information -- it is pure concurrency -- but returns are autocorrelated, so the raw form shows
    a healthy forward IC. It must die on the angle-20 gate, and nothing may survive."""
    state, ret = _series(5000, lead=False, phi=0.30)
    rows = _cell_rows(_write_tape(tmp_path / "fut/ETHUSDT/20260102_00.jsonl.gz", state, ret),
                      "fut:ETHUSDT@20260102")
    raw = _pick(rows, "obi_deep", "raw")
    resid = _pick(rows, "obi_deep", "residualised")
    scored = [r for r in rows if isinstance(r.get("ic"), (int, float))]

    assert abs(float(raw["ic"])) > S.IC_MIN, "fixture must fake a forward IC, or it tests nothing"
    assert raw["verdict"] == "TIMING-ARTIFACT"
    assert abs(float(raw["same_period_corr"])) > 0.2
    assert raw["decontam_passed"] is False

    # Orthogonalised, the fake IC is gone: whatever is left cannot clear the family-wise bar.
    assert abs(float(resid["ic"])) < abs(float(raw["ic"])) / 2.0
    assert resid["clears_family_wise"] is False

    survivors, graveyard = S.classify(scored)
    assert survivors == []
    killed = [g for g in graveyard
              if g["construction"] == "obi_deep" and g["bar_ms"] == BAR_MS
              and g["verdict"] == "TIMING-ARTIFACT"]
    assert killed, "a powered artifact is graveyard-grade knowledge and must be recorded"
    assert killed[0]["detection_floor_ic_unadjusted"] is not None
    assert killed[0]["detection_floor_ic_family_wise"] is not None
    assert "de-contamination" in killed[0]["reason"]


def test_underpowered_cells_are_never_graveyarded():
    """"Could not tell" must never be filed as "it is dead" -- the graveyard is permanent."""
    rows = [{"cell": "c", "construction": "obi_deep", "form": "residualised", "bar_ms": BAR_MS,
             "verdict": "SCREEN-UNDERPOWERED", "ic": 0.001, "powered": False,
             "clears_family_wise": False, "min_detectable_ic": 0.9}]
    survivors, graveyard = S.classify(rows)
    assert survivors == []
    assert graveyard == []


def test_a_raw_only_winner_is_recorded_as_concurrent_only():
    """The pre-registered null, confirmed: the raw state scored and the orthogonalised one did
    not, so the apparent forecast was a restatement of a bar that had already happened."""
    common = {"cell": "c", "construction": "obi_deep", "bar_ms": BAR_MS, "min_detectable_ic": 0.02}
    rows = [
        {**common, "form": "raw", "verdict": "SCREEN-INTERESTING", "ic": 0.21,
         "same_period_corr": 0.19, "powered": True, "clears_family_wise": True},
        {**common, "form": "residualised", "verdict": "SCREEN-WEAK", "ic": 0.004,
         "same_period_corr": 0.0, "powered": True, "clears_family_wise": False},
    ]
    survivors, graveyard = S.classify(rows)
    assert survivors == [], "the raw form can never be a survivor of this screen"
    # The diagnosis outranks the generic SCREEN-WEAK label: a kill has to record WHY, and "the
    # raw twin scored and this one did not" IS the finding for this mechanism class.
    assert [g["verdict"] for g in graveyard] == ["CONCURRENT-ONLY"]
    assert graveyard[0]["raw_ic"] == 0.21
    assert graveyard[0]["raw_same_period_corr"] == 0.19
    assert graveyard[0]["detection_floor_ic_unadjusted"] == 0.02


def test_multiplicity_charge_never_shrinks_below_the_preregistration():
    """A run that reads less tape than planned cannot buy significance by shrinking its family."""
    rows = [{"ic": 0.05, "n_eff": 1000.0} for _ in range(3)]
    S._significance(rows, n_family=max(S.PREREGISTERED_FAMILY, len(rows)))
    assert rows[0]["family_size"] == S.PREREGISTERED_FAMILY == 30
    assert rows[0]["family_z_critical"] > 1.96


# ---------------------------------------------------------------------- the refusal to fabricate

def test_absent_tape_yields_a_status_artifact_naming_the_missing_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "MOAT", tmp_path / "data/moat")
    out = tmp_path / "artifact.json"

    assert S.main(["--out", str(out)]) == 0

    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "NOT-READABLE-HERE"
    assert doc["rows"] == [] and doc["survivors"] == [] and doc["graveyard"] == []
    assert any(p.endswith("data/moat") for p in doc["missing_paths"])
    for venue in S.VENUE_DIRS:
        assert any(venue in p for p in doc["missing_paths"]), f"{venue} not named"
    # The pre-registration travels with the honest empty result, so the record shows WHAT would
    # have been tested rather than only that nothing was.
    assert doc["pre_registration"]["family_preregistered"] == S.PREREGISTERED_FAMILY
    assert doc["pre_registration"]["alpha"] == 0.05
    assert "no synthetic tape is generated" in doc["refusal"]


def test_an_existing_but_empty_venue_directory_is_still_not_readable(tmp_path, monkeypatch):
    """A directory that exists and holds no partitions is a recorder that is not running -- it must
    not read as 'screened, nothing found'."""
    moat = tmp_path / "data/moat"
    for v in S.VENUE_DIRS:
        (moat / v).mkdir(parents=True)
    monkeypatch.setattr(S, "MOAT", moat)
    out = tmp_path / "artifact.json"

    assert S.main(["--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "NOT-READABLE-HERE"
    assert all("no partitions" in p for p in doc["missing_paths"])


def test_end_to_end_run_over_a_present_tape_writes_a_screened_artifact(tmp_path, monkeypatch):
    state, ret = _series(400, lead=False, phi=0.1)
    moat = tmp_path / "data/moat"
    _write_tape(moat / "fut/BTCUSDT/20260101_00.jsonl.gz", state, ret)
    monkeypatch.setattr(S, "MOAT", moat)
    out = tmp_path / "artifact.json"

    assert S.main(["--out", str(out), "--files", "5"]) == 0

    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "SCREENED"
    assert doc["cells_screened"] == 1 and doc["files_read"] == 1
    assert doc["family_size_charged"] >= S.PREREGISTERED_FAMILY
    assert doc["pre_registration"]["primary_form"] == "residualised"
    assert doc["stage"].startswith("A ")
    assert doc["authority"].startswith("NONE")
    # Power is reported ALONGSIDE the verdict, so a null is distinguishable from blindness -- on
    # BOTH bases, each named, because a cell routinely clears the unadjusted floor and not the
    # family-wise one and an unlabelled pair of counts would read as a contradiction.
    assert doc["power_headline_at_family_charge"]
    assert doc["power_counts_at_family_charge"]["negatives"] > 0
    assert "powered_cells_unadjusted" in doc
    assert "interesting_but_failed_multiplicity" in doc
    assert all("alignment" in r for r in doc["rows"])
