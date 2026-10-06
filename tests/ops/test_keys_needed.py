"""KEYS_NEEDED: missing, dark, unconfigured and rejected keys are listed; unavailable, paid and
banned ones never are; no value ever reaches the artifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops import keys_needed as kn


def _doc(tmp_path: Path, present: set[str], **reports: object) -> dict:
    for name, body in reports.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(body), "utf-8")
    return kn.build(reports=tmp_path, present=lambda n: n in present)


def test_a_missing_free_key_is_needed_and_a_set_one_is_not(tmp_path: Path) -> None:
    doc = _doc(tmp_path, {"EIA_API_KEY"})
    names = {i["name"] for i in doc["items"]}
    assert "FRED_API_KEY" in names and "EIA_API_KEY" not in names
    fred = next(i for i in doc["items"] if i["name"] == "FRED_API_KEY")
    assert fred["signup"].startswith("https://") and fred["why"]


def test_unavailable_paid_and_banned_are_never_asked(tmp_path: Path) -> None:
    doc = _doc(tmp_path, set(), ASIA_COLLECTOR={"rows": [
        {"id": "tushare", "status": "UNCONFIGURED", "key_env": "TUSHARE_TOKEN"},
        {"id": "tyc", "status": "UNCONFIGURED", "key_env": "TIANYANCHA_TOKEN"}]})
    names = {i["name"] for i in doc["items"]}
    assert not names & {"TUSHARE_TOKEN", "JQ_USER", "DART_API_KEY", "CDSE_USERNAME",
                        "TIANYANCHA_TOKEN", "X_BEARER_TOKEN", "OPENAI_API_KEY"}


def test_a_rejected_key_is_needed_even_though_it_is_set(tmp_path: Path) -> None:
    doc = _doc(tmp_path, set(kn.env_keys.key_names()), ASIA_COLLECTOR={"rows": [
        {"id": "eia_energy", "access": "key", "status": "HTTP_ERROR", "http": 401,
         "key_env": "EIA_API_KEY"}]})
    assert [i["name"] for i in doc["items"]] == ["EIA_API_KEY"]
    assert doc["items"][0]["reasons"][0].startswith("REJECTED")


def test_blocked_auth_from_the_coverage_report(tmp_path: Path) -> None:
    every = set(kn.env_keys.key_names()) - {"BANXICO_TOKEN"}
    doc = _doc(tmp_path, every, CREDENTIAL_COVERAGE={"vars": [
        {"env": "BANXICO_TOKEN", "status": "BLOCKED_AUTH", "actionable": True,
         "dark_consumers": ["x"]}]})
    item = next(i for i in doc["items"] if i["name"] == "BANXICO_TOKEN")
    assert any(r.startswith("BLOCKED_AUTH") for r in item["reasons"])


def test_acquired_names_count_as_set_and_the_digest_tracks_the_list(tmp_path: Path) -> None:
    a = kn.build(reports=tmp_path, present=lambda n: False)
    b = kn.build(reports=tmp_path, present=lambda n: False, acquired=["FRED_API_KEY"])
    assert "FRED_API_KEY" not in {i["name"] for i in b["items"]}
    assert a["digest"] != b["digest"]
    assert kn.build(reports=tmp_path, present=lambda n: False)["digest"] == a["digest"]


def test_no_value_reaches_the_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIA_API_KEY", "VALUE-NEVER-WRITTEN")
    doc = kn.build(reports=tmp_path)
    out = tmp_path / "KEYS_NEEDED.json"
    kn.write(doc, out)
    assert "VALUE-NEVER-WRITTEN" not in out.read_text("utf-8")
    assert all(line.startswith("- `") for line in kn.lines(doc))
