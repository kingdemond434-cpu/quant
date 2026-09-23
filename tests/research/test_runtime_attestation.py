"""THE RUNTIME ATTESTATION pins the four honest states and the one-host rule.

Every test here builds its own tree under tmp_path. None of them touches the committed
`docs/research/runtime_state.json`: a test that regenerated the attestation would make the fence
unable to catch a stopped clock, which is the only thing the fence is for.
"""
from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "desks" / "mt5" / "research"), str(ROOT / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import runtime_attestation as ra  # noqa: E402

from scripts import check_runtime_attestation as fence  # noqa: E402


def test_state_never_returns_a_blank_and_names_every_case() -> None:
    assert ra._state(False, None, 3600, ran=False)[0] == "NEVER"
    assert ra._state(False, None, 3600, ran=True)[0] == "MISSING"
    assert ra._state(True, 9999.0, 3600, ran=True)[0] == "STALE"
    assert ra._state(True, 60.0, 3600, ran=True)[0] == "LIVE"
    # no declared cadence: nothing here may call it late
    assert ra._state(True, 9e9, None, ran=True)[0] == ra.UNMEASURED
    for exists in (True, False):
        for cad in (3600, None):
            state, why = ra._state(exists, 10.0 if exists else None, cad, ran=True)
            assert state in ra.STATES and why.strip()


def test_summary_takes_only_declared_scalars_and_never_a_body(tmp_path: Path) -> None:
    art = tmp_path / "A.json"
    art.write_text(json.dumps({
        "rows": 12, "status": "ok", "nested": {"a": [1, 2, 3]}, "secret_key": "x" * 500,
        "count": 3, "total": 4, "passed": 5, "failed": 6, "refused": 7, "defects": 8,
        "verdict": "y" * 200,
    }), encoding="utf-8")
    out = ra._summary(art, art.stat().st_size)
    assert "nested" not in out and "secret_key" not in out
    assert len(out) <= ra.MAX_SUMMARY_KEYS
    assert all(isinstance(v, (int, float, bool, str)) for v in out.values())
    assert all(len(v) <= ra.MAX_SUMMARY_CHARS for v in out.values() if isinstance(v, str))


def test_oversized_artifact_is_named_unmeasured_not_skipped(tmp_path: Path) -> None:
    art = tmp_path / "big.json"
    art.write_text("{}", encoding="utf-8")
    out = ra._summary(art, ra.MAX_PARSE_BYTES + 1)
    assert ra.UNMEASURED in str(out["_"])


def test_attest_names_one_host_and_holds_its_size(tmp_path: Path) -> None:
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    doc = ra.attest(ra.Paths.at(tmp_path), budget_s=30.0)
    assert doc["attests_to_host"] == doc["host"]["hostname"] == socket.gethostname()
    assert doc["host"]["role_evidence"].strip()
    assert len(json.dumps(doc, default=str)) <= ra.MAX_JSON_BYTES
    assert set(doc["census"]) == set(ra.STATES)
    assert all(r["state"] in ra.STATES for r in doc["organs"])
    text = ra.render(doc)
    assert doc["host"]["hostname"] in text and "describes no other machine" in text


def _write(tmp_path: Path, doc: dict) -> None:
    p = ra.Paths.at(tmp_path)
    p.out_json.parent.mkdir(parents=True, exist_ok=True)
    p.out_json.write_text(json.dumps(doc, default=str), encoding="utf-8")


def _doc(**over: object) -> dict:
    here = socket.gethostname()
    base = {
        "schema": "runtime_attestation/1",
        "generated_at": ra._iso(time.time()),
        "attests_to_host": here,
        "host": {"hostname": here, "role": "non_trading_host", "role_evidence": "measured"},
        "census": dict.fromkeys(ra.STATES, 0),
        "organs": [],
    }
    base.update(over)
    return base


def test_fence_fails_on_host_drift_everywhere(tmp_path: Path) -> None:
    _write(tmp_path, _doc(attests_to_host="some-other-box"))
    v = fence.measure(tmp_path)
    assert any("host drift" in f for f in v["failures"])
    assert fence.main(["--root", str(tmp_path)]) == 2


def test_fence_fails_when_the_role_is_asserted_not_measured(tmp_path: Path) -> None:
    here = socket.gethostname()
    _write(tmp_path, _doc(host={"hostname": here, "role": "box", "role_evidence": ""}))
    assert any("role is asserted" in f for f in fence.measure(tmp_path)["failures"])


def test_fence_fails_on_staleness_on_the_attesting_host(tmp_path: Path) -> None:
    _write(tmp_path, _doc(generated_at=ra._iso(time.time() - ra.MAX_SILENCE_S - 600)))
    v = fence.measure(tmp_path)
    assert v["on_attesting_host"] and any("stale on its own host" in f for f in v["failures"])
    assert fence.main(["--root", str(tmp_path)]) == 2


def test_fence_passes_elsewhere_and_absence_is_unmeasured(tmp_path: Path) -> None:
    # a stale document ABOUT another host is that host's business, not this reader's
    _write(tmp_path, _doc(attests_to_host="other-box",
                          host={"hostname": "other-box", "role": "box",
                                "role_evidence": "measured"},
                          generated_at=ra._iso(time.time() - 10 * ra.MAX_SILENCE_S)))
    v = fence.measure(tmp_path)
    assert not v["on_attesting_host"]
    assert not any("stale" in f for f in v["failures"])
    assert fence.main(["--root", str(tmp_path)]) == 0
    assert fence.main(["--root", str(tmp_path), "--require-state"]) == 2
    (tmp_path / "docs" / "research" / "runtime_state.json").unlink()
    assert fence.main(["--root", str(tmp_path)]) == 0
    assert fence.main(["--root", str(tmp_path), "--require-state"]) == 2


def test_the_leg_the_layer_and_the_committed_artifact_are_wired() -> None:
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["runtime_attestation"] == "meta"
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("runtime_attestation"' in src
    assert '"runtime_attestation": rta' in src
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert gate.count("check_runtime_attestation.py") == 2
    # THE WHOLE POINT: both files must be committable, or a reader on GitHub sees nothing.
    from libs.ops.release import is_state_path
    for rel in ("docs/research/runtime_state.json", "docs/research/RUNTIME_STATE.md"):
        assert is_state_path(rel), f"{rel} must be a state path the box owns and pushes"
