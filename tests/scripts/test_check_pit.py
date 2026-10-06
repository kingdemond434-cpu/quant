"""THE PIT RATCHET HAD NO MEMORY (audit 2026-09-05, finding (b)).

    python -m pytest tests/scripts/test_check_pit.py -q

`desks/mt5/data/pit_high_water.json` was never committed and a missing one was read as 0.0, so
every fresh CI runner measured against zero and passed. Same defect as the money-path floor, same
repair: an absent baseline FAILS naming the file and the command that creates it; `--init` seals
it once from a real census; the mark only ever rises.

WHAT MUST NOT REGRESS:

  1. a missing or corrupt baseline fails, naming the file and `--init`
  2. `--init` seals the measured fraction with the population it was measured over -- once
  3. a fall fails and the mark does not drop; a rise raises it and keeps `sealed_at`
  4. a census over zero rows is UNMEASURED: not a pass, not a zero, not sealable
  5. `--floor` can tighten the bar but never loosen the ratchet
  6. the committed baseline is real
  7. the DATASET census rides alongside: certificates with and without authority are counted and
     named, an empty certificate directory reports NONE rather than authority, and none of it
     can move the row ratchet's exit code in either direction (2026-09-05)
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import scripts.check_pit as P

from libs.data import pit_certificate as pcert
from libs.data.pit import stamp

ROOT = Path(__file__).resolve().parents[2]


def _intel(tmp_path: Path, sources: dict[str, tuple[int, int]]) -> Path:
    """An intelligence tree: per source, (stamped rows, unstamped rows) in one discoveries file."""
    intel = tmp_path / "intelligence"
    for name, (n_stamped, n_plain) in sources.items():
        rows: list[dict[str, Any]] = [
            stamp({"title": f"{name} {i}", "found_at": "2026-09-01T00:00:00+00:00"}, name,
                  source_version="test")
            for i in range(n_stamped)
        ] + [{"title": f"{name} plain {i}"} for i in range(n_plain)]
        d = intel / name
        d.mkdir(parents=True)
        (d / "discoveries_20260901_0000.json").write_text(json.dumps(rows), "utf-8")
    intel.mkdir(exist_ok=True)
    return intel


def _certificates(tmp_path: Path, *, clean: int = 0, blocked: int = 0) -> Path:
    """A certificate directory: `clean` datasets that pass all seven, `blocked` that do not.

    The blocked ones fail on SURVIVORSHIP by declaring nothing -- the honest default for a
    dataset the acquirer never described, and the one this census exists to make visible.
    """
    root = tmp_path / "pit_certificates"
    now = datetime(2026, 9, 5, tzinfo=UTC)
    idx = pd.date_range("2026-01-01", periods=200, freq="D", tz="UTC")
    df = pd.DataFrame({"value": np.arange(200.0),
                       "available_time": idx + pd.Timedelta(days=2)}, index=idx)
    base = {"revised": False, "publication_lag_s": 172800, "history_starts": "2026-01-01",
            "schema_hash": pcert.schema_hash(df)}
    for i in range(clean):
        pcert.write(pcert.certify({**base, "dataset": f"good/{i}",
                                   "selection": "full_history_no_filter"}, df, now=now), root)
    for i in range(blocked):
        pcert.write(pcert.certify({**base, "dataset": f"undeclared/{i}"}, df, now=now), root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
         sources: dict[str, tuple[int, int]], baseline: dict[str, Any] | str | None,
         *args: str, certificates: Path | None = None) -> tuple[int, str, dict[str, Any] | None]:
    """Drive main() against an isolated tree. `baseline` is a dict (JSON), a raw string (for
    corruption) or None (absent). Returns (exit code, stdout, baseline on disk afterwards)."""
    monkeypatch.setattr(P, "INTEL", _intel(tmp_path, sources))
    monkeypatch.setattr(P, "OUT", tmp_path / "reports" / "PIT_CENSUS.json")
    # ISOLATED FROM THE REPO'S OWN CERTIFICATES so a test asserts on what it seeded, never on
    # whatever the desk happens to have certified today.
    monkeypatch.setattr(P, "CERTIFICATES", certificates or (tmp_path / "no_certificates"))
    bpath = tmp_path / "data" / "pit_high_water.json"
    if isinstance(baseline, dict):
        bpath.parent.mkdir(parents=True, exist_ok=True)
        bpath.write_text(json.dumps(baseline), "utf-8")
    elif isinstance(baseline, str):
        bpath.parent.mkdir(parents=True, exist_ok=True)
        bpath.write_text(baseline, "utf-8")
    code = P.main(["--baseline", str(bpath), *args])
    out = capsys.readouterr().out
    return code, out, _on_disk(bpath)


def _on_disk(bpath: Path) -> dict[str, Any] | None:
    """The baseline after the run: None when absent, or still the junk it was seeded with."""
    if not bpath.exists():
        return None
    try:
        doc = json.loads(bpath.read_text("utf-8"))
    except ValueError:
        return {"_unparseable": bpath.read_text("utf-8")}
    return doc if isinstance(doc, dict) else {"_not_a_record": doc}


def _sealed(frac: float, **extra: Any) -> dict[str, Any]:
    doc = {"sealed_at": "2026-09-05T00:00:00+00:00", "measured_at": "2026-09-05T00:00:00+00:00",
           "stamped_frac": frac, "rows": 100, "stamped": int(frac * 100), "sources": 2}
    doc.update(extra)
    return doc


HALF = {"alpha": (5, 5), "beta": (5, 5)}       # 50% stamped over 20 rows


# ------------------------------------------------- 1. no memory is a failure

def test_a_missing_baseline_fails_and_names_the_file_and_the_command(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    """THE MEASURED DEFECT: `hw = 0.0` on a fresh runner, so any fraction at all passed."""
    code, out, after = _run(tmp_path, monkeypatch, capsys, HALF, None)
    assert code != 0
    assert "pit_high_water.json" in out and "--init" in out
    assert after is None, "a failing run must not manufacture the baseline it says is missing"


@pytest.mark.parametrize("junk", ["", "nope", "[]", '{"at": "x"}', '{"stamped_frac": "0.5"}'])
def test_a_corrupt_baseline_fails_rather_than_reading_as_zero(
        tmp_path: Path, monkeypatch: Any, capsys: Any, junk: str) -> None:
    code, out, _ = _run(tmp_path, monkeypatch, capsys, HALF, junk)
    assert code != 0
    assert "UNREADABLE" in out


# ------------------------------------------------- 2. sealing is deliberate and one-time

def test_init_seals_the_measured_fraction_with_its_population(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    code, out, after = _run(tmp_path, monkeypatch, capsys, HALF, None, "--init")
    assert code == 0, out
    assert after is not None
    assert after["stamped_frac"] == 0.5
    assert after["rows"] == 20 and after["stamped"] == 10 and after["sources"] == 2
    for key in ("sealed_at", "measured_at", "report", "census_generated_utc", "command"):
        assert after.get(key), f"sealed without `{key}`"
    assert after["sealed_at"] == after["measured_at"]
    assert after["report"].endswith("PIT_CENSUS.json")
    assert (tmp_path / "reports" / "PIT_CENSUS.json").exists(), "the census doc it names"


def test_init_refuses_to_overwrite(tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    """Re-sealing would be the one code path able to lower the mark."""
    code, out, after = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.9), "--init")
    assert code != 0 and "REFUSING" in out
    assert after is not None and after["stamped_frac"] == 0.9


# ------------------------------------------------- 3. falls fail, rises stick

def test_a_fall_fails_and_the_mark_holds(tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    code, out, after = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.9))
    assert code != 0
    assert "PIT REGRESSION" in out and "50.0%" in out and "90.0%" in out
    assert after is not None and after["stamped_frac"] == 0.9


def test_a_rise_raises_the_mark_and_keeps_the_seal_date(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    code, out, after = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.25))
    assert code == 0, out
    assert after is not None
    assert after["stamped_frac"] == 0.5
    assert after["rows"] == 20, "the population that earned the new mark is recorded with it"
    assert after["measured_at"] != "2026-09-05T00:00:00+00:00"
    assert after["sealed_at"] == "2026-09-05T00:00:00+00:00"
    assert "raised" in out


def test_a_flat_run_writes_nothing(tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    code, _out, after = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.5))
    assert code == 0
    assert after is not None and after["measured_at"] == "2026-09-05T00:00:00+00:00"


def test_unstamped_sources_are_named_not_averaged_away(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    code, out, _ = _run(tmp_path, monkeypatch, capsys,
                        {"good": (10, 0), "lazy": (0, 10)}, _sealed(0.5))
    assert code == 0, out
    assert "unstamped: lazy" in out and "unstamped: good" not in out


# ------------------------------------------------- 4. zero rows is not a reading

def test_a_census_over_nothing_is_unmeasured_not_zero(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    """The silent-zero defect in a second form: `stamped_frac or 0.0` over an empty tree."""
    code, out, _ = _run(tmp_path, monkeypatch, capsys, {}, _sealed(0.0))
    assert code != 0
    assert "UNMEASURED" in out


def test_init_will_not_seal_from_nothing(tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    code, out, after = _run(tmp_path, monkeypatch, capsys, {}, None, "--init")
    assert code != 0 and "UNMEASURED" in out
    assert after is None


# ------------------------------------------------- 5. --floor tightens, never loosens

def test_an_explicit_floor_cannot_loosen_the_ratchet(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    code, out, _ = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.9), "--floor", "0.1")
    assert code != 0, "a --floor below the mark must not excuse a regression against the mark"
    assert "floor 90.0%" in out


def test_an_explicit_floor_above_the_mark_binds(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    code, out, _ = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.25), "--floor", "0.75")
    assert code != 0 and "PIT REGRESSION" in out


# ------------------------------------------------- 7. the dataset census rides alongside

def test_certificates_are_counted_and_the_blocked_ones_named(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    certs = _certificates(tmp_path, clean=2, blocked=1)
    code, out, _ = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.5),
                        certificates=certs)
    assert code == 0, out
    assert "PIT certificates: 2 of 3 carry authority" in out
    assert "no authority: undeclared/0" in out
    assert "blocked on survivorship" in out


def test_the_census_doc_carries_the_certificate_half(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    certs = _certificates(tmp_path, clean=1, blocked=2)
    _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.5), certificates=certs)
    doc = json.loads((tmp_path / "reports" / "PIT_CENSUS.json").read_text("utf-8"))
    c = doc["certificates"]
    assert c["certificates"] == 3 and c["with_authority"] == 1 and c["without_authority"] == 2
    assert c["datasets_with_authority"] == ["good/0"]
    assert c["by_check"]["survivorship"]["UNMEASURED"] == 2


def test_no_certificates_reads_as_none_not_as_authority(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    """The absent-file defect this whole check exists to end, in its dataset form."""
    code, out, _ = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.5))
    assert code == 0, out
    assert "PIT certificates: NONE" in out
    assert "no promotion authority" in out
    doc = json.loads((tmp_path / "reports" / "PIT_CENSUS.json").read_text("utf-8"))
    assert doc["certificates"]["authority_frac"] is None


def test_the_certificate_census_cannot_move_the_row_ratchet(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    """A perfect dataset census must not excuse a stamped-fraction regression, and a bad one
    must not fail a run that cleared the mark. The ratchet is the stamped fraction, alone."""
    good = _certificates(tmp_path / "a", clean=3, blocked=0)
    code, out, after = _run(tmp_path / "a", monkeypatch, capsys, HALF, _sealed(0.9),
                            certificates=good)
    assert code != 0 and "PIT REGRESSION" in out
    assert after is not None and after["stamped_frac"] == 0.9

    bad = _certificates(tmp_path / "b", clean=0, blocked=3)
    code, out, _ = _run(tmp_path / "b", monkeypatch, capsys, HALF, _sealed(0.5),
                        certificates=bad)
    assert code == 0, "a census with no authority anywhere is reported, not enforced, here"
    assert "0 of 3 carry authority" in out


def test_an_unreadable_certificate_is_named_and_is_not_a_certificate(
        tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    certs = _certificates(tmp_path, clean=1, blocked=0)
    (certs / "junk.json").write_text("{not json", "utf-8")
    code, out, _ = _run(tmp_path, monkeypatch, capsys, HALF, _sealed(0.5), certificates=certs)
    assert code == 0, out
    assert "UNREADABLE certificate: junk.json" in out
    doc = json.loads((tmp_path / "reports" / "PIT_CENSUS.json").read_text("utf-8"))
    assert doc["certificates"]["certificates"] == 1, "junk must not count as a certificate"


# ------------------------------------------------- 6. the committed baseline is real

def test_the_committed_baseline_exists_and_is_sealed() -> None:
    assert P.HIGH_WATER.exists(), (
        f"{P.HIGH_WATER.relative_to(ROOT)} is not committed -- the PIT ratchet has no memory. "
        f"Seal it with:\n  {P.INIT_COMMAND}")
    doc = P.read_baseline(P.HIGH_WATER)
    assert 0.0 <= float(doc["stamped_frac"]) <= 1.0
    assert int(doc["rows"]) > 0, "a mark sealed over zero rows is an absent one"
    assert doc.get("sealed_at") and doc.get("measured_at") and doc.get("report")
