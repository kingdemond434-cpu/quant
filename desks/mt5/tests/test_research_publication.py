"""Copied read-only outputs must advance atomically without hiding publication failures."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
import conversion_ledger as cl  # noqa: E402
import data_prospector as dp  # noqa: E402
import trial_allocator as ta  # noqa: E402
from macro import ledger  # noqa: E402


@pytest.fixture(params=["conversion", "prospector"])
def publication(request, tmp_path, monkeypatch):
    if request.param == "conversion":
        doc = {"generated_utc": "2026-09-14T00:00:00+00:00",
               "binding_stage": ta.GATE_STAGE, "binding_rate": 0.01,
               "stages": [{"measured": True}]}
        monkeypatch.setattr(cl, "assemble", lambda base: doc.copy())
        outputs = [tmp_path / "data" / "conversion_ledger.json"]
        def run():
            return cl.run(tmp_path)
    else:
        doc = {"generated_utc": "2026-09-14T00:00:00+00:00", "queue": [
            {"source": "official publication vintages", "engine_said": "missing PIT",
             "unlocks": ["event_reaction"], "score": 2.0}]}
        monkeypatch.setattr(dp, "rank", lambda: doc.copy())
        outputs = [tmp_path / "reports" / "DATA_PROSPECTOR.json",
                   tmp_path / "data" / "prospector_targets.json"]
        monkeypatch.setattr(dp, "OUT", outputs[0])
        monkeypatch.setattr(dp, "CRAWLER_TARGETS", outputs[1])
        run = dp.run
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"old_evidence": true}', encoding="utf-8")
        path.chmod(0o444)
    return run, outputs, doc


def test_copied_read_only_outputs_publish_and_remain_readable(publication):
    run, outputs, doc = publication
    if os.name == "posix" and os.geteuid() != 0:
        with pytest.raises(PermissionError):
            outputs[-1].open("w")
    run()
    for path in outputs:
        assert json.loads(path.read_text())["generated_utc"] == doc["generated_utc"]
    if outputs[0].name == "conversion_ledger.json":
        consumed = ta.target_stage(outputs[0])
        assert consumed["aimed_correctly"] is True
        assert consumed["measured_at"] == doc["generated_utc"]
    else:
        assert json.loads(outputs[1].read_text())["targets"][0]["query"] == \
            doc["queue"][0]["source"]


@pytest.mark.parametrize("failure", ["serialize", "replace"])
def test_failed_publication_retains_previous_artifact_and_propagates(
        publication, monkeypatch, failure):
    run, outputs, _ = publication
    before = {p: p.read_bytes() for p in outputs}

    def fail(*args, **kwargs):
        if failure == "serialize":
            args[1].write('{"partial":')
        raise OSError("injected publication failure")

    if failure == "serialize":
        monkeypatch.setattr(ledger.json, "dump", fail)
    else:
        monkeypatch.setattr(ledger.os, "replace", fail)
    with pytest.raises(OSError, match="injected publication failure"):
        run()
    assert {p: p.read_bytes() for p in outputs} == before
    assert not list(outputs[0].parents[1].rglob("*.tmp"))
