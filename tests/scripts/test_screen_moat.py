"""THE MOAT SURVIVOR HUNT, AND THE FOUR ALIGNMENT BUGS IT TOOK TO GET RIGHT.

`moat_mine` reconstructs seven proprietary features from the desk's self-recorded L2 tape and
`mine_moat` records which cells have been measured. Nothing ever asked whether any of them
PREDICTS anything -- the one asset a competitor cannot buy produced descriptive statistics and no
verdict, at asymmetry depth 2 of 5.

Getting the harness honest took four corrections, every one of which would have manufactured edge:

  1. ENTRY PRICE WAS A TIME MACHINE. The last print at or before the signal landed 14 SECONDS
     BEFORE it, so the return window spanned the very move the feature was measured during.
  2. THE TARGET WAS DOUBLE-SHIFTED. `stage_a_screen` takes CONTEMPORANEOUS returns and predicts
     t+1 itself; being handed pre-forwarded returns made its own misalignment rail fire on 14 of
     19 hypotheses.
  3. THE SHARPE RAIL IS DAILY-CALIBRATED. The screen annualises, so at 60s the factor is ~725 and
     noise reported sharpe_reversal=53.4 against a ceiling of 6.
  4. HORIZONS HAD TO BECOME STRIDES over the snapshot grid, so one screen period equals one
     horizon rather than one 15-second snapshot.

The controls matter more than any of it: a contemporaneous-only planted structure must yield NO
survivors, and a genuinely predictive one MUST yield some. A harness that never finds anything is
indistinguishable from a broken one.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.screen_moat as S  # noqa: E402


def _tape(root: Path, *, predictive: bool, n: int = 4000, seed: int = 11,
          strength: float = 0.0010, noise: float = 0.0004, funding: bool = False,
          lead: float = 0.4, day: str = "20260101_00") -> None:
    """Book imbalance drives the NEXT period (predictive) or the CURRENT one (contemporaneous).

    `funding` adds k="meta" rows so the FUSE-class mechanism has both legs. Without them it
    correctly returns nothing -- which is right, and also means a test written against this tape
    silently skips it. That is how a full-sample normalisation leak lived in it.

    `lead` IS WHAT MAKES THE PREDICTIVE TAPE A SIGNAL RATHER THAN A LEAK, and getting it wrong
    invalidated the positive control. The original put 100% of imbalance's price move AFTER the
    snapshot, so the feature at `t` explained all of the return `t -> t+1` and NONE of `t-1 -> t`:
    forward IC ~0.49 against a contemporaneous correlation of ~0. No real microstructure signal
    looks like that -- imbalance that predicts the next minute is also moving price right now --
    and it is precisely the shape `axis_screen`'s `ic_exceeds_contemporaneous` rail exists to
    catch. So the harness was right and the control was wrong: it planted a leak and demanded the
    leak detector stay quiet. It only ever "passed" because a separate defect inflated `n_eff` at
    sub-daily horizons (fixed 2026-08-05), which pushed `ic_min` to ~0.0005 and left the rail's
    threshold hostage to a near-zero contemporaneous term.

    With `lead=0.4`, 60% of the move lands before the snapshot and 40% after -- a genuine lead,
    where the forward IC is real and WEAKER than the contemporaneous relationship, which is the
    pattern the rail's own docstring names as honest. The planted edge remains detectable; it
    simply stops impersonating a bug.
    """
    d = root / "binance" / "BTCUSDT"
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    mid, t0 = 30000.0, 1767225600000
    imb = rng.normal(0, 1, n)
    rows = []
    for i in range(n):
        if not predictive:
            mid *= np.exp(strength * imb[i] + rng.normal(0, noise))   # move happens FIRST
        else:
            mid *= np.exp((1.0 - lead) * strength * imb[i])           # the contemporaneous part
        ts = t0 + i * 15000
        b = [max(0.01, 1.0 + 0.5 * imb[i] + rng.normal(0, 0.15)) for _ in range(20)]
        a = [max(0.01, 1.0 - 0.5 * imb[i] + rng.normal(0, 0.15)) for _ in range(20)]
        rows.append({"t": ts, "k": "d", "u": i,
                     "b": [[f"{mid - 0.5 - j * 0.5:.2f}", f"{b[j]:.4f}"] for j in range(20)],
                     "a": [[f"{mid + 0.5 + j * 0.5:.2f}", f"{a[j]:.4f}"] for j in range(20)]})
        rows.append({"t": ts + 1000, "k": "t", "a": i, "p": f"{mid:.2f}", "q": "0.5"})
        if funding and i % 20 == 0:
            rows.append({"t": ts + 500, "k": "meta",
                         "fr": float(0.0001 + 0.00005 * np.sin(i / 37.0))})
        if predictive:
            mid *= np.exp(lead * strength * imb[i] + rng.normal(0, noise))   # the FORWARD part
    with gzip.open(d / f"{day}.jsonl.gz", "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _run(tmp: Path, root: Path, *, files: int | None = None) -> dict:
    """Run the screen against a temp tape with EVERY output path redirected.

    THE REDIRECTION IS LOAD-BEARING, NOT TIDINESS. The screen now persists coverage and a survivor
    registry, and an unredirected test writes SYNTHETIC-TAPE SURVIVORS into the desk's real
    registry -- where they are indistinguishable from findings on the actual archive and carry the
    same provenance fields. `test_every_written_path_is_redirected` fails if a future output is
    added without being redirected here, because the next person to add one will not read this.
    """
    S.MOAT, S.REPORT, S.HISTORY = root, tmp / "r.json", tmp / "h.jsonl"
    S.COVERAGE, S.REGISTRY = tmp / "cov.json", tmp / "reg.json"
    sys.argv = ["screen_moat.py"] + ([] if files is None else ["--files", str(files)])
    assert S.main() == 0
    return json.loads((tmp / "r.json").read_text("utf-8"))


# --------------------------------------------------------------------- alignment

def test_entry_is_the_first_print_after_the_signal_not_before_it(tmp_path) -> None:
    """BUG 1, AND IT IS A TIME MACHINE. Pricing entry at the last print BEFORE the signal put the
    fill 14 seconds in the past, so the return window contained the move the feature described."""
    rows = [{"t": 1000, "k": "t", "a": 0, "p": "100", "q": "1"},
            {"t": 3000, "k": "t", "a": 1, "p": "110", "q": "1"},
            {"t": 5000, "k": "t", "a": 2, "p": "121", "q": "1"}]
    snaps = np.array([2000, 4000], dtype="int64")
    r = S.period_returns(rows, snaps)
    # snapshot @2000 -> first print after = 110 ; snapshot @4000 -> 121. Return = 121/110 - 1.
    assert np.isnan(r[0]), "the first period has no prior entry and must be unmeasured"
    assert r[1] == np.float64(121) / 110 - 1


def test_a_period_with_no_print_is_nan_not_zero(tmp_path) -> None:
    """No trade means no return. A zero tells the screen nothing happened when nothing was seen."""
    rows = [{"t": 1000, "k": "t", "a": 0, "p": "100", "q": "1"}]
    assert np.isnan(S.period_returns(rows, np.array([5000, 9000], dtype="int64"))).all()


def test_horizons_are_strides_so_one_period_equals_one_horizon() -> None:
    """BUG 4. The screen predicts ONE PERIOD ahead; if a period is a 15s snapshot then a '900s
    horizon' was never actually tested."""
    assert S.SNAPSHOT_S == 15
    assert all(h % S.SNAPSHOT_S == 0 for h in S.HORIZONS_S)


def test_the_sharpe_ceiling_is_rescaled_for_the_horizon() -> None:
    """BUG 3. The screen annualises, so a ceiling of 6.0 calibrated at horizon_days=1 becomes a
    725-fold tighter bar at 60s -- and pure noise reported sharpe_reversal=53.4 against it."""
    import inspect
    src = inspect.getsource(S.screen_symbol)
    assert "sharpe_ceiling" in src
    assert "np.sqrt(1.0 / hd)" in src


def test_the_target_is_contemporaneous_because_the_screen_shifts_it_itself() -> None:
    """BUG 2. stage_a_screen's contract: target_ret[t] is the return over period t, and it
    predicts t+1 from signal[t]. Handing it pre-forwarded returns shifts twice."""
    assert "CONTEMPORANEOUS" in S.period_returns.__doc__
    assert not hasattr(S, "forward_returns"), "the double-shifting version must be gone"


# ---------------------------------------------------------------------- controls

def test_a_contemporaneous_only_edge_yields_no_survivors(tmp_path) -> None:
    """THE NEGATIVE CONTROL. Imbalance that reflects the move which just happened is not a
    prediction, however strong the relationship looks."""
    root = tmp_path / "moat_c"
    _tape(root, predictive=False)
    rep = _run(tmp_path, root)
    assert rep["survivors"] == [], f"survivors on a non-predictive tape: {rep['survivors']}"


#: The positive control's tape parameters, named because THREE separate rails constrain them and
#: changing one in isolation silently converts this test into a different question:
#:
#:   n=20_000    POWER. `powered = min_detectable_ic <= ic_min` and min_detectable_ic = 1.96/sqrt
#:               (n_eff). At 60s periods a 4,000-snapshot tape gives n_eff=978 -> 0.0627 against
#:               an ic_min of 0.03, so `powered` is FALSE and no strength whatever can produce a
#:               survivor. This control passed for weeks only because a defect inflated n_eff at
#:               sub-daily horizons (14.4M from 10k rows); when that was fixed on 2026-08-05 the
#:               control went red and revealed it had never demonstrated detection under correct
#:               power accounting. 20,000 snapshots -> n_eff=4,978 -> 0.0278, powered.
#:               THE OPERATIONAL FACT THIS ENCODES: at a 60s horizon the moat screen cannot
#:               certify anything until roughly 4,300 non-overlapping periods -- about three days
#:               of continuous tape per cell. Shorter is not a weak result, it is no result.
#:   lead=0.5    THE LEAKAGE RAIL. Forward IC must not exceed 1.5x the contemporaneous
#:               correlation, or `ic_exceeds_contemporaneous` fires and the planted edge is
#:               correctly called a leak.
#:   noise       THE DE-CONTAMINATION RAIL, from the other side. |same-period corr| must stay
#:               under contam_max=0.20 or the verdict is TIMING-ARTIFACT. Measured here: 0.178.
#:
#: The window between those last two is genuinely narrow, and that is the harness working: a
#: forward relationship that is real, weaker than the same-period one, and not merely the
#: same-period one bleeding through.
_CONTROL = {"n": 20_000, "lead": 0.5, "strength": 0.0012, "noise": 0.0012}


def test_a_genuinely_predictive_edge_IS_found(tmp_path) -> None:
    """THE POSITIVE CONTROL, AND THE MORE IMPORTANT ONE. A harness that never finds anything is
    indistinguishable from a broken harness, and 'no survivors' from it means nothing."""
    root = tmp_path / "moat_p"
    _tape(root, predictive=True, **_CONTROL)
    rep = _run(tmp_path, root)
    assert rep["survivors"], "a planted forward edge must be found"
    assert all(s["rw_p_adjusted"] <= 0.05 for s in rep["survivors"])


def test_the_same_edge_on_a_short_tape_is_UNDERPOWERED_not_a_survivor(tmp_path) -> None:
    """THE OTHER HALF OF THE POSITIVE CONTROL, and the half whose absence hid the n_eff defect.

    Identical planted edge, one fifth of the tape. The screen must report that it could not have
    seen it -- never a survivor, and never a refutation either. Without this, shortening the tape
    (or re-inflating n_eff) turns the test above green again by making everything "powered", which
    is exactly how the defect survived: the control only ever asserted that SOMETHING was found.
    """
    root = tmp_path / "moat_short"
    _tape(root, predictive=True, **{**_CONTROL, "n": 4_000})
    rep = _run(tmp_path, root)
    assert rep["survivors"] == [], "a tape too short to be powered must yield no survivor"
    rows = [r for r in rep["results"] if r.get("mechanism") == "imbalance"
            and r.get("horizon_s") == 60]
    assert rows and not rows[0]["powered"], "n_eff must not certify a 978-period cell as powered"


def test_romano_wolf_runs_per_horizon_not_across_all_of_them() -> None:
    """BUG 5, AND IT WAS DATA DESTRUCTION DRESSED AS STRICTNESS. Candidates at different horizons
    live on different period grids -- 60s has 978 observations, 900s has 45. Stacking them into
    one matrix truncated every column to the SHORTEST, cutting a t = +4.49 candidate to its last
    45 points and returning p_adjusted = 1.0. A horizon is the natural family: within it every
    mechanism shares one grid and one length."""
    import inspect
    src = inspect.getsource(S.main)
    assert "for h in HORIZONS_S:" in src
    assert "rw_family" in src


def test_survivors_must_clear_family_wise_error_not_just_stage_a(tmp_path) -> None:
    """Seven mechanisms x three horizons is a family, and the best of a family looks good by
    construction. A SCREEN-INTERESTING that fails Romano-Wolf is NOT a survivor."""
    root = tmp_path / "moat_c2"
    _tape(root, predictive=False)
    rep = _run(tmp_path, root)
    interesting = rep["tally"].get("SCREEN-INTERESTING", 0)
    assert len(rep["survivors"]) <= interesting


# ----------------------------------------------------------------------- hygiene

def test_a_scalar_mechanism_is_skipped_not_broadcast(tmp_path) -> None:
    """replenishment_halflife is one number per file. Broadcasting it to a constant would hand a
    degenerate feature a verdict."""
    root = tmp_path / "moat_s"
    _tape(root, predictive=True, n=800)
    rep = _run(tmp_path, root)
    assert rep["tally"].get("SCALAR-NOT-SCREENABLE", 0) >= 1


def test_absent_tape_is_reported_not_synthesised(tmp_path) -> None:
    rep = _run(tmp_path, tmp_path / "nope")
    assert rep["state"] == "NO TAPE"
    assert "NOT synthesised" in rep["note"]


def test_every_hypothesis_is_logged_win_or_lose(tmp_path) -> None:
    """Reporting only the printer is p-hacking. Zero survivors is a publishable outcome."""
    root = tmp_path / "moat_l"
    _tape(root, predictive=False)
    rep = _run(tmp_path, root)
    assert sum(rep["tally"].values()) == rep["hypotheses"]
    assert rep["authority"].startswith("NONE")


# ------------------------------------------------------- manufactured mechanisms

def test_the_manufactured_features_are_actually_screened() -> None:
    """The asymmetry ledger ranked these first and they sat as PROPOSALS. A feature that exists,
    is RECONSTRUCT/FUSE class and is never screened is worth exactly as much as one that does not
    exist -- and the moat screen was the only organ that could tell the difference."""
    from libs.hypmax.moat_features import MANUFACTURED
    assert set(MANUFACTURED) <= set(S.MECHANISMS)
    assert len(S.MECHANISMS) == len(S._EXTRACTORS) + len(MANUFACTURED), "no silent name swap"


def test_a_name_collision_between_the_two_sources_is_fatal() -> None:
    """`{**a, **b}` resolves a duplicate key by SILENTLY dropping one definition, and which one
    survives depends on dict order. Two mechanisms sharing a name would be screened once and
    reported under a name that no longer means what the other module thinks it means."""
    import inspect
    src = inspect.getsource(S)
    assert "_COLLISION" in src and "RuntimeError" in src


def test_manufactured_features_are_causal_and_finite(tmp_path) -> None:
    """Each value at snapshot i may use only snapshots <= i. Verified by TRUNCATION: recomputing
    on a prefix must reproduce the prefix of the full-series answer, which is impossible for any
    feature that peeks forward."""
    from libs.hypmax import moat_features as MF
    root = tmp_path / "moat_mf"
    _tape(root, predictive=True, n=600, funding=True)
    rows = S._rows(next((root / "binance" / "BTCUSDT").glob("*.jsonl.gz")))
    depth = [r for r in rows if r.get("k") in S.DEPTH_KINDS]
    cut = depth[len(depth) // 2]["t"]
    prefix = [r for r in rows if int(r["t"]) <= cut]
    for name, fn in MF.MANUFACTURED.items():
        full, part = np.asarray(fn(rows)), np.asarray(fn(prefix))
        if part.size == 0:
            continue                      # nothing computable on the prefix says nothing about it
        # Features align to the LAST k snapshots, so compare the leading part of the prefix
        # answer against the same absolute positions in the full one.
        k = min(part.size, full.size) - 1
        a, b = full[:k], part[:k]
        both = np.isfinite(a) & np.isfinite(b)
        assert both.sum() > 0, f"{name}: nothing finite to compare"
        assert np.allclose(a[both], b[both], rtol=1e-9, atol=1e-12), (
            f"{name} changed its own past when future data arrived -- lookahead")


def test_a_fusion_with_one_leg_missing_returns_nothing(tmp_path) -> None:
    """book_pressure_vs_funding is FUSE class. Defaulting the absent funding leg to zero would
    turn it into plain book imbalance wearing a name that claims a barrier it does not have."""
    from libs.hypmax.moat_features import book_pressure_vs_funding
    root = tmp_path / "moat_nf"
    _tape(root, predictive=True, n=400)          # the synthetic tape publishes no k="meta"
    rows = S._rows(next((root / "binance" / "BTCUSDT").glob("*.jsonl.gz")))
    assert book_pressure_vs_funding(rows).size == 0


# ------------------------------------------------------------ coverage frontier

def test_repeated_runs_move_onto_unscreened_cells(tmp_path) -> None:
    """THE WHOLE POINT OF THE FRONTIER. `files[-200:]` re-screened the newest slice forever, so
    the oldest tape -- the part that cannot be backfilled at any price -- was never looked at."""
    root = tmp_path / "moat_cov"
    _tape(root, predictive=True, n=400)
    d = root / "binance" / "BTCUSDT"
    src = (d / "20260101_00.jsonl.gz").read_bytes()
    for day in ("20260102_00", "20260103_00"):
        (d / f"{day}.jsonl.gz").write_bytes(src)

    first = _run(tmp_path, root, files=1)
    second = _run(tmp_path, root, files=1)
    assert first["cells_on_disk"] == 3
    assert first["symbols"] != second["symbols"], (
        f"the second run re-screened the same cell: {first['symbols']}")
    assert second["coverage_pct"] > first["coverage_pct"], "coverage must accumulate across runs"


def test_coverage_counts_mechanisms_that_RESOLVED_not_cells_that_were_touched(tmp_path) -> None:
    """The miner's rule, and it is the difference between 'we asked everywhere' and 'we ran
    everywhere'. Mined-and-barren and never-looked-at demand opposite responses."""
    root = tmp_path / "moat_cov2"
    _tape(root, predictive=True, n=400)
    rep = _run(tmp_path, root)
    cov = json.loads((tmp_path / "cov.json").read_text("utf-8"))
    cell = next(iter(cov["screened"].values()))
    assert set(cell["mechanisms"]) < set(S.MECHANISMS), (
        "a scalar mechanism resolves no IC and must never be recorded as covered")
    # It is recorded as UNANSWERABLE instead, which is a different claim: the cell was asked and
    # the question has no answer here, as against never having been asked. An earlier version of
    # this test asserted coverage < 100% -- true only while unanswerable pairs sat in the
    # denominator, which is the arithmetic that made the frontier unable to close.
    assert set(cell["unscreenable"]) & set(S.MECHANISMS)
    assert not set(cell["mechanisms"]) & set(cell["unscreenable"])
    assert rep["screenable_grid"] < len(S.MECHANISMS) * rep["cells_on_disk"]


def test_a_gap_is_not_a_horizon() -> None:
    """Hole-first scheduling hands the screen non-adjacent days BY DESIGN. Subsampling assumes
    every step is stride x 15s; across a gap one '60-second period' can be twelve hours and it
    carries twelve hours of return into a sample whose every other point carries a minute."""
    ts = np.array([0, 60_000, 120_000, 86_400_000, 86_460_000], dtype="int64")
    m = S._contiguous(ts, 60)
    assert not m[0], "the first point has no preceding period"
    assert m[1] and m[2] and m[4]
    assert not m[3], "a period spanning a day must not be priced as a minute"


# ------------------------------------------------------------ survivor registry

def test_survivors_persist_with_their_misses(tmp_path) -> None:
    """A survivor printed once and overwritten is a rumour. The denominator is the point: nothing
    controls family-wise error ACROSS runs, so screening the archive repeatedly returns false
    survivors at the nominal rate by construction."""
    root = tmp_path / "moat_reg"
    _tape(root, predictive=True, **_CONTROL)
    rep = _run(tmp_path, root)
    assert rep["survivors"]
    reg = json.loads((tmp_path / "reg.json").read_text("utf-8"))
    e = next(iter(reg.values()))
    assert e["times_screened"] >= 1 and "hit_rate" in e and "first_seen" in e
    assert any(v["times_survived"] >= 1 for v in reg.values())
    # Every scored candidate is recorded, not only the winners.
    assert len(reg) >= len(rep["survivors"])


def test_persistence_requires_more_than_one_independent_cell(tmp_path) -> None:
    """One survivor from one screening is the best of a family of thirty-three. Promotion to
    PERSISTENT needs the same triple to survive on cells that are genuinely different days."""
    root = tmp_path / "moat_reg2"
    _tape(root, predictive=True, strength=0.0035, noise=0.0004)
    rep = _run(tmp_path, root)
    assert rep["persistent_candidates"] == [], "a single cell cannot establish persistence"


def test_the_registry_records_sign_stability(tmp_path) -> None:
    """The cheapest fraud test there is: a real microstructure effect points the same way every
    day, a fitted one flips, and a mean IC hides that by cancelling."""
    root = tmp_path / "moat_reg3"
    _tape(root, predictive=True, n=1200)
    _run(tmp_path, root)
    reg = json.loads((tmp_path / "reg.json").read_text("utf-8"))
    assert all("ic_sign_stability" in v for v in reg.values())


def test_every_written_path_is_redirected(tmp_path) -> None:
    """THE TEST THAT CATCHES THE NEXT OUTPUT NOBODY REDIRECTS. An unredirected artifact writes
    synthetic-tape findings into the desk's real registry, where they are indistinguishable from
    findings on the actual archive."""
    root = tmp_path / "moat_red"
    _tape(root, predictive=True, n=400)
    _run(tmp_path, root)
    real = Path(S.ROOT) / "data"
    for name in ("MOAT", "REPORT", "HISTORY", "COVERAGE", "REGISTRY"):
        p = Path(getattr(S, name))
        assert real not in p.parents and p != real, f"{name} still points at the real data dir"


def test_an_unanswerable_mechanism_leaves_the_denominator_not_the_numerator(tmp_path) -> None:
    """A GAP THAT CAN NEVER CLOSE IS A LIE ABOUT ARITHMETIC, NOT A FINDING ABOUT THE DESK.

    `replenishment_halflife` returns one number per cell -- there is nothing to correlate against
    a return, here or anywhere -- so counting it as an unscreened hole pins coverage below 91%
    forever. P26 makes a gap that stops closing a breach, so that would raise a standing alarm
    about a denominator. It is recorded per cell and reported, never silently dropped: 'asked and
    unanswerable' and 'never asked' demand opposite responses.
    """
    root = tmp_path / "moat_den"
    _tape(root, predictive=True, n=900)
    rep = _run(tmp_path, root)
    assert rep["unscreenable_pairs"] >= 1, "the scalar mechanism must be recorded as unanswerable"
    assert rep["screenable_grid"] < len(S.MECHANISMS) * rep["cells_on_disk"]
    cov = json.loads((tmp_path / "cov.json").read_text("utf-8"))
    cell = next(iter(cov["screened"].values()))
    assert "replenishment_halflife" in cell["unscreenable"]
    assert "replenishment_halflife" not in cell["mechanisms"], (
        "unanswerable is not the same as answered -- it must never count as covered")


def test_a_fuse_mechanism_with_no_input_is_retired_not_chased_forever(tmp_path) -> None:
    """EMPTY IS NOT SHORT. `book_pressure_vs_funding` returns NOTHING on a venue that publishes no
    funding, and that cell's files are already written -- no amount of further recording adds the
    field. Counting it as an open hole leaves a frontier that can never reach 100%, which under
    P26 reads as a breach that never closes. A SHORT series is the opposite: a quantity problem
    the recorders fix by running, and it must stay a hole.
    """
    root = tmp_path / "moat_noinput"
    _tape(root, predictive=True, n=700)          # no funding rows on this tape
    rep = _run(tmp_path, root)
    verdicts = {(r.get("mechanism"), r.get("verdict")) for r in rep["results"]}
    assert ("book_pressure_vs_funding", "NO-INPUT") in verdicts
    cov = json.loads((tmp_path / "cov.json").read_text("utf-8"))
    cell = next(iter(cov["screened"].values()))
    assert "book_pressure_vs_funding" in cell["unscreenable"]
    # ...and a short-but-present series must NOT be retired, or a real hole disappears.
    assert not any(v == "NO-INPUT" for m, v in verdicts if m == "resting_stability")


def test_the_frontier_actually_reaches_full_coverage_on_a_finite_archive(tmp_path) -> None:
    """THE PROPERTY THE WHOLE DESIGN EXISTS FOR. Repeated budgeted runs must converge, not
    plateau: every cell touched, and every remaining hole attributable to tape quantity rather
    than to arithmetic that can never resolve."""
    root = tmp_path / "moat_conv"
    _tape(root, predictive=True, n=700)
    src = (root / "binance" / "BTCUSDT" / "20260101_00.jsonl.gz").read_bytes()
    for day in ("20260102_00", "20260103_00"):
        (root / "binance" / "BTCUSDT" / f"{day}.jsonl.gz").write_bytes(src)

    seen, last = set(), None
    for _ in range(4):
        last = _run(tmp_path, root, files=1)
        seen.update(last["symbols"])
    assert len(seen) == 3, f"the frontier never reached every cell: {seen}"
    assert last["cells_covered_pct"] == 100.0
    assert last["coverage_pct"] > 80.0, (
        f"coverage stalled at {last['coverage_pct']}% -- a denominator that cannot be filled is "
        "an alarm about arithmetic, not about the desk")


def test_the_screen_and_the_miner_key_cells_the_same_way() -> None:
    """SHARING A GRID IS THE WHOLE REASON TO MATCH THE MINER. A cell that is mined but never
    screened is only a VISIBLE hole if both organs mean the same thing by "cell".

    This organ briefly took the first ten characters of the filename, which on the recorders'
    `YYYYMMDD_HH.jsonl.gz` yields `20260105_0` -- the date plus the tens digit of the hour. That
    split every day into up to three cells, put the two organs on different grids, and made every
    screened cell smaller, which is also a weaker screen.
    """
    import scripts.mine_moat as MM
    for name in ("20260105_00.jsonl.gz", "20260105_17.jsonl.gz", "20260105_9.jsonl.gz"):
        p = Path("data/moat/binance/BTCUSDT") / name
        assert S._day_of(p) == "20260105"
        assert S._day_of(p) == p.stem.split("_")[0], (
            "mine_moat keys on stem.split('_')[0]; the two must not drift")
    assert "split(\"_\")" in Path(MM.__file__).read_text("utf-8"), (
        "the miner's rule changed -- re-check that this organ still matches it")
