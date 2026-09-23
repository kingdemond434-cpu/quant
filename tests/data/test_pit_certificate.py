"""The seven adversarial questions, put to synthetic datasets whose answers are known.

    python -m pytest tests/data/test_pit_certificate.py -q

Each test PLANTS the defect the check exists to catch, so a check that stops asking stops passing
here. What must not regress:

  1. a clean dataset carries authority; every one of the seven is asked and answers PASS
  2. a planted LEAK fails certification -- both shapes: a row dated after now, and a row knowable
     before the event it describes
  3. a source that restates history with no vintage fails; with a vintage it passes
  4. a truncated history is NAMED -- the missing span appears in the why, at the head and in the
     middle
  5. survivorship is DECLARED, never inferred: an undeclared selection is UNMEASURED, a
     survivor-conditioned one FAILS
  6. a schema change fails; no prior hash is UNMEASURED, never a pass
  7. UNMEASURED is not authority, the certificate id is stable across re-certification of an
     unchanged dataset, and to_json/from_json round-trips
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from libs.data import pit_certificate as pc

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
LAG = timedelta(days=2)


def _series(n: int = 200, start: str = "2026-01-01", freq: str = "D",
            lag: timedelta = LAG) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    rng = np.random.default_rng(0)
    return pd.DataFrame({"value": rng.normal(size=n),
                         "available_time": idx + pd.Timedelta(lag)}, index=idx)


def _meta(df: pd.DataFrame, **over: object) -> dict[str, object]:
    m: dict[str, object] = {
        "dataset": "synthetic/clean", "url": "https://example.invalid/clean.csv",
        "revised": False, "selection": "full_history_no_filter",
        "publication_lag_s": int(LAG.total_seconds()), "history_starts": "2026-01-01",
        "schema_hash": pc.schema_hash(df),
    }
    m.update(over)
    return m


def _verdicts(cert: pc.PITCertificate) -> dict[str, str]:
    return {c.name: c.verdict for c in cert.checks}


# ------------------------------------------------- 1. the clean case

def test_a_clean_dataset_carries_authority_and_answers_all_seven() -> None:
    df = _series()
    cert = pc.certify(_meta(df), df, now=NOW)
    assert cert.authority is True
    assert set(_verdicts(cert)) == set(pc.CHECK_NAMES), "a question that stopped being asked"
    assert set(_verdicts(cert).values()) == {pc.VERDICT_PASS}
    assert not cert.failures() and not cert.unmeasured()


def test_every_check_carries_a_why_long_enough_to_act_on() -> None:
    df = _series()
    for c in pc.certify(_meta(df), df, now=NOW).checks:
        assert len(c.why) > 30, f"{c.name} gives a verdict without a reason"


# ------------------------------------------------- 2. planted leaks

def test_a_planted_leak_fails_certification_when_rows_are_knowable_before_they_happen() -> None:
    """THE CANONICAL PIT LEAK: available_time earlier than the event it describes."""
    df = _series()
    df["available_time"] = df.index - pd.Timedelta(days=1)
    cert = pc.certify(_meta(df, schema_hash=pc.schema_hash(df)), df, now=NOW)
    assert cert.authority is False
    assert "leak" in cert.failures()
    assert "knowable before it happened" in cert.why("leak")


def test_a_planted_leak_fails_when_rows_are_dated_after_now() -> None:
    df = _series(n=400)                                  # runs past NOW at a daily cadence
    cert = pc.certify(_meta(df), df, now=NOW)
    assert cert.authority is False
    assert "leak" in cert.failures()
    assert "dated AFTER now" in cert.why("leak")


def test_an_availability_stamp_in_the_future_fails() -> None:
    df = _series(n=60)
    df["available_time"] = df.index + pd.Timedelta(days=3650)
    cert = pc.certify(_meta(df, schema_hash=pc.schema_hash(df)), df, now=NOW)
    assert "availability" in cert.failures()
    assert "future" in cert.why("availability")


def test_stamps_sooner_than_the_declared_publication_lag_fail() -> None:
    df = _series(n=60, lag=timedelta(hours=1))
    cert = pc.certify(_meta(df, schema_hash=pc.schema_hash(df)), df, now=NOW)
    assert "availability" in cert.failures()
    assert "sooner than the source publishes" in cert.why("availability")


# ------------------------------------------------- 3. revisions

def test_a_restating_source_with_no_vintage_column_fails() -> None:
    idx = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    df = pd.DataFrame({"value": np.arange(60.0)}, index=idx)
    cert = pc.certify(_meta(df, revised=True, schema_hash=pc.schema_hash(df)), df, now=NOW)
    assert "revision" in cert.failures()
    assert "no vintage column" in cert.why("revision")


def test_repeated_event_times_are_a_restatement_by_another_name() -> None:
    idx = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    doubled = idx.append(idx[:10])
    df = pd.DataFrame({"value": np.arange(len(doubled), dtype=float)}, index=doubled.sort_values())
    cert = pc.certify(_meta(df, revised=None, schema_hash=pc.schema_hash(df)), df, now=NOW)
    assert "revision" in cert.failures()
    assert "repeat an event time" in cert.why("revision")


def test_a_restating_source_with_a_vintage_passes() -> None:
    df = _series(n=60)
    cert = pc.certify(_meta(df, revised=True), df, now=NOW)
    assert cert.authority is True
    assert "available_time" in cert.why("revision")


def test_an_undeclared_revision_policy_is_unmeasured_not_a_pass() -> None:
    idx = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    df = pd.DataFrame({"value": np.arange(60.0)}, index=idx)
    cert = pc.certify(_meta(df, revised=None, schema_hash=pc.schema_hash(df)), df, now=NOW)
    assert "revision" in cert.unmeasured()
    assert cert.authority is False, "UNMEASURED is not authority"


# ------------------------------------------------- 4. truncation is NAMED

def test_a_truncated_history_names_the_missing_span() -> None:
    df = _series(n=200)
    cut = pd.concat([df.iloc[:50], df.iloc[150:]])          # 100 days removed from the middle
    cert = pc.certify(_meta(df, schema_hash=pc.schema_hash(cut)), cut, now=NOW)
    assert cert.authority is False
    assert "truncation" in cert.failures()
    why = cert.why("truncation")
    assert "2026-02-19" in why and "2026-05-31" in why, f"the hole is not named: {why}"
    detail = next(c.detail for c in cert.checks if c.name == "truncation")
    assert detail["gap_from"].startswith("2026-02-19") and detail["gap_to"].startswith("2026-05-31")


def test_a_head_truncation_is_named_against_the_declared_start() -> None:
    df = _series(n=100, start="2026-03-01")
    cert = pc.certify(_meta(df, history_starts="2026-01-01"), df, now=NOW)
    assert "truncation" in cert.failures()
    assert "truncated at the head" in cert.why("truncation")
    assert "2026-01-01" in cert.why("truncation")


def test_a_normal_weekend_cadence_is_not_a_truncation() -> None:
    idx = pd.bdate_range("2026-01-01", periods=120, tz="UTC")
    df = pd.DataFrame({"value": np.arange(120.0), "available_time": idx + pd.Timedelta(LAG)},
                      index=idx)
    cert = pc.certify(_meta(df, schema_hash=pc.schema_hash(df)), df, now=NOW)
    assert cert.authority is True, cert.why("truncation")


def test_too_few_rows_to_have_a_cadence_is_unmeasured() -> None:
    df = _series(n=5)
    cert = pc.certify(_meta(df, history_starts=None, schema_hash=pc.schema_hash(df)), df, now=NOW)
    assert "truncation" in cert.unmeasured()


# ------------------------------------------------- 5. survivorship is declared

def test_an_undeclared_selection_is_unmeasured_and_carries_no_authority() -> None:
    df = _series()
    cert = pc.certify(_meta(df, selection=None), df, now=NOW)
    assert "survivorship" in cert.unmeasured()
    assert cert.authority is False


@pytest.mark.parametrize("selection", ["currently_listed", "top_by_current_size",
                                       "the instruments still trading today"])
def test_a_selection_that_conditions_on_the_present_fails(selection: str) -> None:
    df = _series()
    cert = pc.certify(_meta(df, selection=selection), df, now=NOW)
    assert "survivorship" in cert.failures()
    assert "future information about every past row" in cert.why("survivorship")


def test_a_selection_the_checker_does_not_know_is_unmeasured_not_a_pass() -> None:
    df = _series()
    cert = pc.certify(_meta(df, selection="some_bespoke_rule"), df, now=NOW)
    assert "survivorship" in cert.unmeasured()


# ------------------------------------------------- 6. schema drift

def test_a_changed_schema_fails_and_names_both_hashes() -> None:
    df = _series()
    cert = pc.certify(_meta(df, schema_hash="0000stalehash00"), df, now=NOW)
    assert "schema" in cert.failures()
    assert "0000stalehash00" in cert.why("schema") and pc.schema_hash(df) in cert.why("schema")


def test_a_renamed_column_moves_the_schema_hash() -> None:
    df = _series()
    renamed = df.rename(columns={"value": "obs_value"})
    assert pc.schema_hash(df) != pc.schema_hash(renamed)


def test_no_prior_schema_hash_is_unmeasured_and_reports_this_run_s() -> None:
    df = _series()
    cert = pc.certify(_meta(df, schema_hash=None), df, now=NOW)
    assert "schema" in cert.unmeasured()
    assert pc.schema_hash(df) in cert.why("schema")


# ------------------------------------------------- 7. the certificate itself

def test_the_id_is_stable_across_recertification_of_an_unchanged_dataset() -> None:
    df = _series()
    a = pc.certify(_meta(df), df, now=NOW)
    b = pc.certify(_meta(df), df, now=NOW + timedelta(days=30))
    assert a.certificate_id == b.certificate_id
    assert a.certified_at != b.certified_at


def test_the_id_moves_when_the_dataset_does() -> None:
    df = _series()
    more = _series(n=201)
    assert pc.certify(_meta(df), df, now=NOW).certificate_id != \
        pc.certify(_meta(more), more, now=NOW).certificate_id


def test_to_json_and_from_json_round_trip(tmp_path: Path) -> None:
    df = _series()
    cert = pc.certify(_meta(df), df, now=NOW)
    assert pc.PITCertificate.from_json(cert.to_json()) == cert
    p = pc.write(cert, tmp_path)
    assert p.exists() and p.name == "synthetic_clean.json"
    assert pc.load("synthetic/clean", tmp_path) == cert
    assert pc.has_authority("synthetic/clean", tmp_path) is True


def test_a_missing_or_corrupt_certificate_is_not_a_certificate(tmp_path: Path) -> None:
    assert pc.load("never/certified", tmp_path) is None
    assert pc.has_authority("never/certified", tmp_path) is False
    pc.path_for("junk/one", tmp_path).parent.mkdir(parents=True, exist_ok=True)
    pc.path_for("junk/one", tmp_path).write_text("{not json", "utf-8")
    assert pc.load("junk/one", tmp_path) is None
    assert pc.has_authority("junk/one", tmp_path) is False


def test_the_census_counts_authority_and_names_what_blocks_it(tmp_path: Path) -> None:
    clean = _series()
    pc.write(pc.certify(_meta(clean), clean, now=NOW), tmp_path)
    dirty = _series(n=60)
    pc.write(pc.certify(_meta(dirty, selection=None, schema_hash=pc.schema_hash(dirty),
                              dataset="synthetic/dirty"), dirty, now=NOW), tmp_path)
    pc.path_for("broken", tmp_path).write_text("not a certificate", "utf-8")

    c = pc.census(tmp_path)
    assert c["certificates"] == 2
    assert c["with_authority"] == 1 and c["without_authority"] == 1
    assert c["datasets_with_authority"] == ["synthetic/clean"]
    assert c["blocking_check"]["synthetic/dirty"] == ["survivorship"]
    assert c["unreadable"] == ["broken.json"]
    assert c["by_check"]["leak"][pc.VERDICT_PASS] == 2


def test_an_empty_certificate_directory_reports_none_rather_than_authority(tmp_path: Path) -> None:
    c = pc.census(tmp_path / "absent")
    assert c["certificates"] == 0 and c["with_authority"] == 0
    assert c["authority_frac"] is None, "no certificates is not 100% authority and not 0%"


def test_a_certificate_ages_out(tmp_path: Path) -> None:
    df = _series()
    cert = pc.certify(_meta(df), df, now=NOW)
    assert not pc.stale(cert, now=NOW + timedelta(days=1))
    assert pc.stale(cert, now=NOW + timedelta(days=200))
