"""The external code sandbox law: what a third-party process may touch, and every refusal named."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from libs.research import external_federation as fed
from libs.research import sandbox as sb


def test_the_environment_a_sandboxed_process_gets_carries_no_secret() -> None:
    env = sb.scrub_env({"PATH": "p", "MT5_LOGIN": "495044", "OPENAI_API_KEY": "sk-x",
                        "BROKER_PASSWORD": "hunter2", "QUANT_ALLOW_SSH_PY": "1",
                        "FRED_KEY": "k", "SYSTEMROOT": r"C:\Windows", "HOME": "/h"})
    assert env["PATH"] == "p" and env["SYSTEMROOT"] == r"C:\Windows"
    assert env["QUANT_SANDBOX"] == "1"
    for gone in ("MT5_LOGIN", "OPENAI_API_KEY", "BROKER_PASSWORD", "QUANT_ALLOW_SSH_PY",
                 "FRED_KEY"):
        assert gone not in env, f"{gone} reached a third-party process"


def test_an_unread_licence_is_a_label_and_no_longer_refuses_execution() -> None:
    """REWRITTEN 2026-09-23 (LAWS 5e). An unread LICENSE file refused DIRECT execution and was
    "the single reason every seed is UNDISPOSED today" -- a discovery brake that stopped the desk
    testing public research code. The run happens; the reading stays a recorded task."""
    system = fed.SEED_BY_ID["rd_agent"]
    assert sb.refuse_reason(system, "DIRECT") is None
    notes = " | ".join(sb.provenance_notes(system, "DIRECT"))
    assert "licence UNVERIFIED" in notes or "withholds redistribution" in notes


def test_a_rebuilt_system_is_refused_a_sandbox_by_name() -> None:
    why = sb.refuse_reason(fed.SEED_BY_ID["hubble"], "REBUILT")
    assert why and "REBUILT reproduces the mechanism" in why


def test_a_host_outside_the_roster_is_recorded_not_refused() -> None:
    """REWRITTEN 2026-09-23 (LAWS 5e). An eight-domain allowlist meant a research system
    published anywhere else was never tested. The host is now provenance on the row."""
    odd = fed.ExternalSystem("odd", "Odd", "https://files.example.ru/x.zip", "?", "DIRECT",
                             ("data_source",), ("data",), licence="MIT")
    assert sb.refuse_reason(odd, "DIRECT") is None
    assert any("off-roster host" in n for n in sb.provenance_notes(odd, "DIRECT"))


def test_an_upstream_with_no_host_is_still_refused_there_is_nothing_to_fetch() -> None:
    """The two refusals that remain are not policy: they are "there is nothing here to run"."""
    nowhere = fed.ExternalSystem("nowhere", "Nowhere", "public:some/paper", "?", "DIRECT",
                                 ("data_source",), ("data",), licence="MIT")
    why = sb.refuse_reason(nowhere, "DIRECT")
    assert why and "nothing to" in why


def test_a_licensed_allowlisted_system_is_eligible_and_dry_run_creates_nothing(tmp_path) -> None:
    system = fed.ExternalSystem("ok_sys", "OK", "github:someone/thing", "?", "DIRECT",
                                ("data_source",), ("data",), licence="MIT")
    assert sb.refuse_reason(system, "DIRECT") is None
    box = sb.provision(system, "DIRECT", root=tmp_path, dry_run=True)
    assert not box.provisioned and "dry run" in box.why
    assert not (tmp_path / "ok_sys").exists()
    real = sb.provision(system, "DIRECT", root=tmp_path, dry_run=False)
    assert real.provisioned and real.work.exists() and real.out.exists()
    assert tmp_path in real.root.parents or real.root.parent == tmp_path


def test_a_run_is_timed_out_and_its_environment_is_the_scrubbed_one(tmp_path) -> None:
    system = fed.ExternalSystem("runner", "R", "github:someone/thing", "?", "DIRECT",
                                ("data_source",), ("data",), licence="MIT")
    box = sb.provision(system, "DIRECT", root=tmp_path, dry_run=False)
    res = sb.run(box, [sys.executable, "-c",
                       "import os,sys;print('SECRET' if os.environ.get('MT5_LOGIN') else 'clean')"],
                 timeout_s=60)
    assert res.ok and res.stdout_tail and res.stdout_tail[-1] == "clean"
    slow = sb.run(box, [sys.executable, "-c", "import time;time.sleep(30)"], timeout_s=1)
    assert not slow.ok and "timed out" in slow.why


def test_an_unprovisioned_sandbox_refuses_to_run(tmp_path) -> None:
    system = fed.SEED_BY_ID["agonalpha"]
    box = sb.provision(system, "DIRECT", root=tmp_path, dry_run=True)
    res = sb.run(box, [sys.executable, "-c", "print(1)"])
    assert not res.ok and "not provisioned" in res.why


def test_the_packet_is_the_only_exit_and_a_verdict_cannot_pass(tmp_path) -> None:
    system = fed.ExternalSystem("p_sys", "P", "github:someone/thing", "?", "DIRECT",
                                ("data_source",), ("data",), licence="MIT")
    box = sb.provision(system, "DIRECT", root=tmp_path, dry_run=False)
    (box.out / "packet.json").write_text(json.dumps({
        "system_id": "p_sys", "run_id": "r1", "commit": "abc",
        "candidates": [{"family": "carry", "symbol": "XAUUSD"}], "trials_charged": 40}),
        encoding="utf-8")
    pkt = sb.packet(box)
    assert pkt.counts()["candidates"] == 1 and pkt.trials_charged == 40
    (box.out / "packet.json").write_text(json.dumps({
        "system_id": "p_sys", "run_id": "r2", "commit": "abc",
        "candidates": [{"family": "carry", "symbol": "XAUUSD", "survivor": True}]}),
        encoding="utf-8")
    with pytest.raises(ValueError, match="researcher, never a validator"):
        sb.packet(box)


def test_status_never_claims_to_enforce_the_network(tmp_path) -> None:
    st = sb.status(root=tmp_path)
    assert st["declared_not_enforced"] and "network egress" in st["declared_not_enforced"][0]
    assert "scrubbed environment" in st["enforced"]


def test_inputs_are_copied_never_mounted(tmp_path) -> None:
    system = fed.ExternalSystem("in_sys", "I", "github:someone/thing", "?", "DIRECT",
                                ("data_source",), ("data",), licence="MIT")
    box = sb.provision(system, "DIRECT", root=tmp_path, dry_run=False)
    src = tmp_path / "series.json"
    src.write_text('{"a": 1}', encoding="utf-8")
    res = sb.run(box, [sys.executable, "-c",
                       "import pathlib;print(pathlib.Path('series.json').read_text())"],
                 timeout_s=60, inputs={"series.json": src})
    assert res.ok and '"a": 1' in res.stdout_tail[-1]
    copied = box.work / "series.json"
    copied.write_text('{"a": 2}', encoding="utf-8")
    assert json.loads(src.read_text(encoding="utf-8"))["a"] == 1, (
        "a sandbox edit reached the desk's own file: inputs must be copies")


def test_the_sandbox_root_is_outside_the_repository() -> None:
    repo = Path(__file__).resolve().parents[2]
    assert repo not in sb.SANDBOX_ROOT.parents and repo != sb.SANDBOX_ROOT
