from __future__ import annotations

import json
from pathlib import Path

SERVICE = Path("ops/quant-midnight-frontier.service")
TIMER = Path("ops/quant-midnight-frontier.timer")
WRAPPER = Path("ops/run_midnight_frontier.sh")
CONTROLLER = Path("ops/run_midnight_codex_controller.sh")
PROMPT = Path("ops/midnight_codex_prompt.txt")
MANDATE = Path("docs/research/TIER1_CONTROLLER_MANDATE.md")
AGENTS = Path("AGENTS.md")
DEPLOY = Path("ops/deploy_vps.sh")
RECONSTITUTE = Path("deploy/reconstitute_cron.sh")
SUPERVISOR = Path("deploy/quant-research.service")
CONTRACT = Path("docs/research/OVERNIGHT_FRONTIER_CONTRACT.json")


def test_midnight_is_a_vps_controller_cycle_not_an_app_automation() -> None:
    assert "00:00:00 Europe/Dublin" in TIMER.read_text("utf-8")
    assert "run_midnight_frontier.sh" in SERVICE.read_text("utf-8")
    wrapper = WRAPPER.read_text("utf-8")
    assert wrapper.index("run_sweep_then_cycle.sh") < wrapper.index(
        "run_midnight_codex_controller.sh"
    )
    assert ".midnight_controller_cycle.lock" in wrapper
    assert "quant-midnight-frontier.timer" in DEPLOY.read_text("utf-8")
    assert "quant-midnight-frontier" in RECONSTITUTE.read_text("utf-8")
    assert not Path("ops/quant-research.service").exists()
    assert "run_supervisor.py" in SUPERVISOR.read_text("utf-8")
    for deployer in (DEPLOY, RECONSTITUTE):
        source = deployer.read_text("utf-8")
        assert "disable --now quant-research.timer" in source
        assert "quant-research.service" in source and "preserv" in source
        assert "rm -f /etc/systemd/system/quant-research.service" not in source


def test_overnight_contract_names_the_authority_and_collision_free_units() -> None:
    contract = json.loads(CONTRACT.read_text("utf-8"))
    assert contract["schedule"] == {
        "timezone": "Europe/Dublin",
        "local_start": "00:00",
        "systemd_timer": "ops/quant-midnight-frontier.timer",
        "systemd_service": "ops/quant-midnight-frontier.service",
        "renewal": "daily_and_never_terminal",
    }
    assert contract["controller_mandate"] == "docs/MASTER_QUANT_CONSTITUTION.md"
    assert contract["implementation_mandate"] == "docs/research/TIER1_CONTROLLER_MANDATE.md"
    assert "data/constitution_core.lock" in contract["required_artifacts"]


def test_codex_controller_is_noninteractive_fenced_and_checkpointed() -> None:
    source = CONTROLLER.read_text("utf-8")
    for required in (
        "check_constitution_core.py",
        "codex login status",
        "--ask-for-approval never",
        "--sandbox workspace-write",
        "controller_checkpoint.py claim",
        "controller_checkpoint.py heartbeat",
        "controller_checkpoint.py checkpoint",
        "controller_checkpoint.py transfer",
        "--successor claude-primary",
    ):
        assert required in source
    assert "persistent workers" in source or "deterministic machinery remains active" in source
    assert "--dangerously-bypass-approvals-and-sandbox" not in source
    assert source.index("check_constitution_core.py") < source.index(
        "controller_checkpoint.py claim"
    ) < source.index("cat docs/MASTER_QUANT_CONSTITUTION.md")
    assert "CHECKPOINT_RC=0" in source and "TRANSFER_RC=0" in source
    assert "HANDOFF_INCOMPLETE" in source
    assert '|| CHECKPOINT_RC=$?' in source
    assert '|| TRANSFER_RC=$?' in source


def test_controller_prompt_forces_continuation_conversion_and_open_world_coverage() -> None:
    prompt = PROMPT.read_text("utf-8")
    for required in (
        "MASTER_QUANT_CONSTITUTION.md",
        "continuation cycle",
        "Never reset",
        "open-world coverage",
        "Convert, do not summarize",
        "IMPLEMENT, TEST, BLOCKED",
        "checkpoint",
        "scripts/run_deadman_switch.py",
    ):
        assert required.casefold() in prompt.casefold()
    assert MANDATE.exists() and len(MANDATE.read_text("utf-8")) > 20_000
    assert "controller_continuity.py" in AGENTS.read_text("utf-8")
