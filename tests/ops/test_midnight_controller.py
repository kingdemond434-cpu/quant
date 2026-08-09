from __future__ import annotations

from pathlib import Path

SERVICE = Path("ops/quant-research.service")
TIMER = Path("ops/quant-research.timer")
WRAPPER = Path("ops/run_midnight_frontier.sh")
CONTROLLER = Path("ops/run_midnight_codex_controller.sh")
PROMPT = Path("ops/midnight_codex_prompt.txt")
MANDATE = Path("docs/research/TIER1_CONTROLLER_MANDATE.md")
AGENTS = Path("AGENTS.md")


def test_midnight_is_a_vps_controller_cycle_not_an_app_automation() -> None:
    assert "00:00:00 Europe/London" in TIMER.read_text("utf-8")
    assert "run_midnight_frontier.sh" in SERVICE.read_text("utf-8")
    wrapper = WRAPPER.read_text("utf-8")
    assert wrapper.index("run_sweep_then_cycle.sh") < wrapper.index(
        "run_midnight_codex_controller.sh"
    )
    assert ".midnight_controller_cycle.lock" in wrapper


def test_codex_controller_is_noninteractive_fenced_and_checkpointed() -> None:
    source = CONTROLLER.read_text("utf-8")
    for required in (
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


def test_controller_prompt_forces_continuation_conversion_and_open_world_coverage() -> None:
    prompt = PROMPT.read_text("utf-8")
    for required in (
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
