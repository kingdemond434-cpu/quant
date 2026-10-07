"""The carry re-judge queue feeds the judge's own re-mint path and never edits a certificate."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("queue_carry_rejudge",
                                               DESK / "scripts" / "queue_carry_rejudge.py")
assert _spec and _spec.loader
q = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(q)


def _survivors(tmp_path: Path) -> Path:
    f = tmp_path / "UNIVERSAL_SURVIVORS.json"
    f.write_text(json.dumps({"survivors": {
        "external.CHFNOK.carry.p=aaa": {"cell": "CHFNOK.carry.p=aaa", "sym": "CHFNOK",
                                        "gated_at": "2026-09-02T23:37:32+00:00",
                                        "shadow_spec": {"symbol": "CHFNOK", "family": "carry",
                                                        "params": {"input_symbol": "CHFNOK"}}},
        "external.CHFNOK.carry.p=new": {"cell": "CHFNOK.carry.p=new", "sym": "CHFNOK",
                                        "gated_at": "2026-10-08T01:00:00+00:00",
                                        "shadow_spec": {"symbol": "CHFNOK", "family": "carry"}},
        "external.EURUSD.session_range_breakout.p=b": {
            "cell": "EURUSD.session_range_breakout.p=b", "gated_at": "2026-09-01T00:00:00+00:00",
            "shadow_spec": {"symbol": "EURUSD", "family": "session_range_breakout"}},
    }}))
    return f


def test_only_carry_certificates_gated_before_the_fix_are_queued(tmp_path) -> None:
    certs = q.carry_certificates((_survivors(tmp_path),))
    assert set(certs) == {"external.CHFNOK.carry.p=aaa"}
    assert certs["external.CHFNOK.carry.p=aaa"]["cell"] == "CHFNOK.carry.p=aaa"


def test_the_queue_merges_into_the_attestation_in_force(tmp_path) -> None:
    certs = q.carry_certificates((_survivors(tmp_path),))
    existing = {"attestation": {"version": "v4"}, "cells": ["X.y.p=1"],
                "stale_certificate_keys": ["external.X.y.p=1"]}
    doc, why = q.build_queue(certs, existing, {"version": "v4"})
    assert why == "ok" and doc is not None
    assert doc["cells"] == ["CHFNOK.carry.p=aaa", "X.y.p=1"]
    assert doc["stale_certificate_keys"] == ["external.CHFNOK.carry.p=aaa", "external.X.y.p=1"]


def test_a_queue_for_another_attestation_is_never_replaced(tmp_path) -> None:
    certs = q.carry_certificates((_survivors(tmp_path),))
    doc, why = q.build_queue(certs, {"attestation": {"version": "v5"}, "cells": ["a"]},
                             {"version": "v4"})
    assert doc is None and "ANOTHER attestation" in why
