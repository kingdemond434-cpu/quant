"""THE SOUTH-AMERICA INTERACTION MINER: families recorded, triples screened, absences named.

    python -m pytest desks/mt5/tests/test_south_america_interaction.py -q

THE REGISTRY IS REDIRECTED INTO `tmp_path` AND ITS BACKUP IS POINTED AT NOTHING. `registry.connect`
restores from `BACKUP` when the database file is absent, so a test that only calls `set_path`
would silently copy the desk's real moat into the temporary file and then write discoveries into a
copy of production. Both are monkeypatched, and every assertion here is against a database this
test created.

THREE PROPERTIES ARE PINNED, and each of them is a way this organ could look like it works while
doing nothing:

  1. EVERY FAMILY RECORDS A DISCOVERY WITH ITS REGION. The compiler reads `generator` and the
     command's conversion is measured by it, so a family that records under the wrong generator
     is invisible to the only number that says whether this file earns its compute.

  2. A PLANTED CONDITIONAL LEAD IS FOUND, AND AN UNCONDITIONAL ONE IS NOT. The screen's whole
     claim is that it detects a relationship that exists only inside a state. The second half is
     the one that matters: a screen that also fires on a relationship present everywhere is not
     measuring conditionality, it is measuring correlation with extra steps.

  3. A MISSING LEG IS UNMEASURED BY NAME, NOT A NULL. Every cross-region triple here needs an
     artifact from another command, and on this box none of them exists. The test asserts the
     triples say so with the paths they looked in -- because a triple that quietly disappears
     when a leg is absent is indistinguishable from a triple nobody ever wrote.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import south_america_interaction as SA  # noqa: E402


@pytest.fixture
def moat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A registry that is this test's own: redirected AND cut off from the production backup."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_such_backup")
    R.set_path(tmp_path / "registry.sqlite")
    conn = R.connect()
    try:
        yield conn
    finally:
        conn.close()
        R.set_path(None)


# --------------------------------------------------------------------------- the families
def test_every_family_records_a_discovery_stamped_with_its_region(moat) -> None:
    got = SA.record_families(conn=moat)
    assert got["outcome"] == "ok"
    assert got["n"] == len(SA.FAMILIES) >= 12
    assert got["n_new"] == got["n"], "a first pass should create every row"

    rows = R.discoveries(limit=500, conn=moat)
    by_gen = {r["generator"]: r for r in rows}
    for fam in SA.FAMILIES:
        gen = f"latam:{fam['id']}"
        assert gen in by_gen, f"{fam['id']} recorded nothing"
        payload = json.loads(by_gen[gen]["payload_json"])
        assert payload["region"] == fam["region"]
        assert payload["command"] == "SOUTH_AMERICA"
        assert payload["sensor_for"], f"{fam['id']}: no sensor target declared"
        assert by_gen[gen]["falsifier"], f"{fam['id']}: a hypothesis with no falsifier"


def test_recording_twice_creates_nothing_twice(moat) -> None:
    """The registry's content hash must collapse a re-run onto the same rows."""
    first = SA.record_families(conn=moat)
    second = SA.record_families(conn=moat)
    assert first["n_new"] == len(SA.FAMILIES)
    assert second["n_new"] == 0
    assert len(R.discoveries(limit=500, conn=moat)) == len(SA.FAMILIES)


def test_families_cover_every_country_and_name_only_real_symbols() -> None:
    from research import countries as C

    regions = {f["region"] for f in SA.FAMILIES}
    assert {"br", "cl", "ar", "mx", "co"} <= regions
    for fam in SA.FAMILIES:
        split = C.resolve(fam["symbols"])
        assert split["absent"] == [], f"{fam['id']}: {split['absent']} not in the universe"
        assert split["equities"] == [], f"{fam['id']}: single names"
        assert fam["sensor_for"], f"{fam['id']}: no sensor instruction"
        assert len(fam["falsifier"]) > 40, f"{fam['id']}: token falsifier"


# --------------------------------------------------------------------------- the screen
def _planted(n: int = 400, *, conditional: bool, seed: int = 7):
    """A driver that leads the target by three days -- inside the state only, or everywhere."""
    rng = np.random.default_rng(seed)
    driver = rng.normal(size=n)
    noise = rng.normal(size=n) * 0.35
    condition = np.zeros(n, dtype=bool)
    condition[n // 2:] = True
    target = noise.copy()
    lead = np.zeros(n)
    lead[3:] = driver[:-3]
    if conditional:
        target += lead * condition
    else:
        target += lead
    return driver, target, condition


def test_a_planted_conditional_lead_is_found_at_its_own_lag() -> None:
    driver, target, condition = _planted(conditional=True)
    got = SA.conditional_lead_lag(driver, target, condition, n_perm=200)
    assert got["outcome"] == "ok"
    assert got["lag"] == 3, f"found lag {got['lag']}"
    assert abs(got["stat"]) > 0.3
    assert got["p"] <= 0.05 and got["passes"] is True
    assert got["n_condition"] == 200


def test_the_null_permutes_the_condition_so_an_everywhere_effect_does_not_pass() -> None:
    """THE HALF THAT MATTERS. A relationship present in every state is not a conditional one, and
    permuting the condition labels is what makes the screen able to tell the difference."""
    driver, target, condition = _planted(conditional=False)
    got = SA.conditional_lead_lag(driver, target, condition, n_perm=300)
    assert got["outcome"] == "ok"
    assert got["passes"] is False, (
        f"an unconditional lead passed a conditional screen at p={got['p']}, which means the "
        f"null is not permuting the condition")


def test_no_relationship_at_all_does_not_pass() -> None:
    rng = np.random.default_rng(11)
    n = 300
    condition = np.zeros(n, dtype=bool)
    condition[100:200] = True
    got = SA.conditional_lead_lag(rng.normal(size=n), rng.normal(size=n), condition, n_perm=300)
    assert got["outcome"] == "ok" and got["passes"] is False


def test_a_short_series_and_a_thin_condition_are_unmeasured_not_negative() -> None:
    short = SA.conditional_lead_lag(np.arange(10.0), np.arange(10.0), np.ones(10, dtype=bool))
    assert short["outcome"] == "UNMEASURED" and "aligned observations" in short["why"]

    n = 100
    thin = np.zeros(n, dtype=bool)
    thin[:3] = True
    got = SA.conditional_lead_lag(np.arange(float(n)), np.arange(float(n)), thin)
    assert got["outcome"] == "UNMEASURED"
    assert "POORLY_MEASURED" in got["why"] and "not a negative result" in got["why"]


# --------------------------------------------------------------------------- the triples
def test_a_triple_with_every_leg_planted_screens_each_target() -> None:
    triple = SA.TRIPLES[1]
    driver, target, condition = _planted(conditional=True, seed=3)
    series = {triple["driver"]: driver, triple["condition"]: condition,
              triple["legs"][2]: np.zeros(driver.size)}
    series[triple["targets"][0]] = target
    got = SA.screen_triple(triple, series, n_perm=200)

    assert got["outcome"] == "ok"
    assert list(got["targets"]) == [triple["targets"][0]]
    assert got["n_passing"] == 1
    assert got["targets"][triple["targets"][0]]["lag"] == 3


def test_a_triple_with_a_missing_leg_is_unmeasured_and_says_which() -> None:
    triple = SA.TRIPLES[0]
    got = SA.screen_triple(triple, {triple["driver"]: np.zeros(50)}, n_perm=10)
    assert got["outcome"] == "UNMEASURED"
    assert set(got["missing_legs"]) == set(triple["legs"]) - {triple["driver"]}
    assert "not on this box" in got["why"]
    assert got["claim"], "a triple must carry its claim even when it cannot be measured"


def test_every_declared_triple_names_real_targets_and_three_legs() -> None:
    from research import countries as C

    assert len(SA.TRIPLES) == 3
    for triple in SA.TRIPLES:
        assert len(triple["legs"]) == 3, f"{triple['id']}: not a triple"
        assert triple["driver"] in triple["legs"] and triple["condition"] in triple["legs"]
        assert C.resolve(triple["targets"])["absent"] == [], f"{triple['id']}: absent targets"
        for leg in triple["legs"]:
            assert leg in SA.LEG_SOURCES, f"{triple['id']}: leg {leg} has no declared source"
        assert triple["why_conditional"] and triple["falsifier"]


def test_an_absent_leg_reports_the_paths_it_looked_in(tmp_path: Path) -> None:
    """UNMEASURED with no address is not a measurement: the next session cannot act on it."""
    got = SA.resolve_leg("me_saudi_liquidity", root=tmp_path)
    assert got["outcome"] == "UNMEASURED"
    assert got["found"] == []
    assert len(got["looked_in"]) >= 2
    assert "countries/sa/data_plane.py" in " ".join(got["looked_in"])


def test_a_leg_resolves_when_its_artifact_exists(tmp_path: Path) -> None:
    target = tmp_path / "desks/mt5/reports/KR_NOWCAST.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")
    got = SA.resolve_leg("kr_semiconductor_nowcast", root=tmp_path)
    assert got["outcome"] == "ok" and got["found"]


# --------------------------------------------------------------------------- the pass
def test_a_full_pass_writes_the_declared_report_shape(moat, tmp_path: Path) -> None:
    out = tmp_path / "SOUTH_AMERICA_INTERACTION.json"
    doc = SA.run(conn=moat, root=tmp_path, out=out, n_perm=20)

    for key in ("at", "families", "discoveries_recorded", "cross_region", "screens",
                "unmeasured", "rule"):
        assert key in doc, f"the report is missing {key}"
    assert out.exists()
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["n_families"] == len(SA.FAMILIES)
    assert written["command"] == "SOUTH_AMERICA"

    # On this box no cross-region artifact exists, so every triple must be UNMEASURED BY NAME.
    assert all(s["outcome"] == "UNMEASURED" for s in written["screens"])
    named = {row["what"] for row in written["unmeasured"]}
    assert {t["id"] for t in SA.TRIPLES} <= named
    assert all(row["why"] for row in written["unmeasured"])


def test_a_planted_leg_reaches_the_pass_and_is_screened(moat, tmp_path: Path) -> None:
    triple = SA.TRIPLES[1]
    driver, target, condition = _planted(conditional=True, seed=5)
    doc = SA.run(conn=moat, root=tmp_path, out=tmp_path / "r.json", n_perm=150,
                 series={triple["driver"]: driver, triple["condition"]: condition,
                         triple["legs"][2]: np.zeros(driver.size),
                         triple["targets"][0]: target})
    screened = {s["id"]: s for s in doc["screens"]}
    assert screened[triple["id"]]["outcome"] == "ok"
    assert screened[triple["id"]]["n_passing"] == 1
    assert doc["legs"][triple["driver"]]["outcome"] == "ok"


def test_dry_run_writes_nothing_at_all(moat, tmp_path: Path) -> None:
    """No report and no registry row: the shape a scheduler uses to check the organ is alive."""
    out = tmp_path / "must_not_exist.json"
    doc = SA.run(dry_run=True, conn=moat, root=tmp_path, out=out, n_perm=10)

    assert doc["dry_run"] is True
    assert not out.exists()
    assert "report_path" not in doc
    assert R.discoveries(limit=50, conn=moat) == []
    assert all(r["discovery_id"] == "dry-run" for r in doc["discoveries_recorded"]["recorded"])


def test_the_cli_dry_run_exits_clean_and_writes_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_such_backup")
    R.set_path(tmp_path / "registry.sqlite")
    monkeypatch.setattr(SA, "OUT", tmp_path / "never.json")
    try:
        assert SA.main(["--dry-run", "--perm", "10"]) == 0
    finally:
        R.set_path(None)
    assert not (tmp_path / "never.json").exists()
    assert "UNMEASURED" in capsys.readouterr().out
