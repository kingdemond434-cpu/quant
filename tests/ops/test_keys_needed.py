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


def test_a_requested_key_is_parked_out_of_the_alert(tmp_path: Path) -> None:
    every = set(kn.env_keys.key_names()) - {"ENTSOE_API_TOKEN"}
    a = kn.build(reports=tmp_path, present=lambda n: n in every)
    from datetime import UTC, datetime
    b = kn.build(reports=tmp_path, present=lambda n: n in every,
                 requested=["ENTSOE_API_TOKEN@2026-10-06"],
                 now=datetime(2026, 10, 7, tzinfo=UTC))
    assert [i["name"] for i in a["items"]] == ["ENTSOE_API_TOKEN"]
    assert b["items"] == [] and b["requested_waiting"] == ["ENTSOE_API_TOKEN"]


def test_a_failed_build_writes_an_unmeasured_stub(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "desks" / "mt5")]
    from research import credential_coverage as cc

    out = tmp_path / "KEYS_NEEDED.json"
    out.write_text('{"digest": "stale", "items": [{"name": "OLD"}]}', "utf-8")
    monkeypatch.setattr(cc, "REPORT", tmp_path / "CREDENTIAL_COVERAGE.json")
    monkeypatch.setattr(kn, "OUT", out)
    monkeypatch.setattr(kn, "write", lambda doc, path=out: path.write_text(json.dumps(doc)))
    monkeypatch.setattr(kn, "build", lambda **_: (_ for _ in ()).throw(RuntimeError("x")))
    assert cc.main([]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["status"] == "UNMEASURED" and doc["items"] == []


def test_requested_keys_are_dated_and_resurface_when_stale(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    every = set(kn.env_keys.key_names()) - {"ENTSOE_API_TOKEN"}
    now = datetime(2026, 10, 7, tzinfo=UTC)

    def run(entry: str) -> dict:
        return kn.build(reports=tmp_path, present=lambda n: n in every, requested=[entry],
                        now=now)
    assert run("ENTSOE_API_TOKEN@2026-10-06")["items"] == []
    stale = run("ENTSOE_API_TOKEN@2026-09-01")["items"]
    assert stale and any(r.startswith("REQUESTED_STALE") for r in stale[0]["reasons"])
    assert [i["name"] for i in run("ENTSOE_API_TOKEN")["items"]] == ["ENTSOE_API_TOKEN"]
    # A future date would park the key until then: it is not parked at all (re-audit of #252).
    future = run("ENTSOE_API_TOKEN@2099-01-01")["items"]
    assert [i["name"] for i in future] == ["ENTSOE_API_TOKEN"]
    assert any(r.startswith("REQUESTED_FUTURE_DATE") for r in future[0]["reasons"])
