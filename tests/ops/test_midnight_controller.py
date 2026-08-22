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
    # A pre-run status publication is allowed, but the fresh MT5 snapshot must finish
    # before the actual reasoning-controller invocation.
    assert wrapper.index("build_mt5_midnight_state.py") < wrapper.rindex(
        "run_midnight_codex_controller.sh"
    )
    assert "run_sweep_then_cycle.sh" not in wrapper
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
    assert contract["venue_scope"] == "MT5_FUSION_ONLY"
    assert contract["pipeline"] == [
        "ops/run_midnight_frontier.sh",
        "scripts/build_mt5_midnight_state.py",
        "ops/run_midnight_codex_controller.sh",
    ]
    assert "data/constitution_core.lock" in contract["required_artifacts"]


def test_codex_controller_is_noninteractive_fenced_and_checkpointed() -> None:
    source = CONTROLLER.read_text("utf-8")
    for required in (
        "check_constitution_core.py",
        "codex login status",
        "--sandbox workspace-write",
        "controller_checkpoint.py claim",
        "controller_checkpoint.py heartbeat",
        "controller_checkpoint.py checkpoint",
        "controller_checkpoint.py transfer",
        "--successor claude-primary",
    ):
        assert required in source
    assert "persistent workers" in source or "deterministic machinery remains active" in source
    assert "--approve-for-me" in source and "--ask-for-approval never" in source
    assert 'codex "${CODEX_GLOBAL_ARGS[@]}" "${CODEX_ARGS[@]}"' in source
    assert "CLI_INCOMPATIBLE" in source
    assert "RUNNING_PIPELINE" in source and "RUNNING_CONTROLLER" in source
    assert "LEASE_ERROR" in source and "CLAIM_RC" in source
    assert "CODEX_NIGHTLY_TIMEOUT_SECONDS:-21600" in source
    # The unit file pins the model; the script must READ that pin rather than
    # overwrite it. _OVERRIDE stays as the operator escape hatch, but it can no
    # longer shadow the Environment= line into irrelevance.
    assert (
        'CODEX_NIGHTLY_MODEL="${CODEX_NIGHTLY_MODEL_OVERRIDE:-'
        '${CODEX_NIGHTLY_MODEL:-gpt-5.6-sol}}"'
    ) in source
    assert (
        'CODEX_NIGHTLY_REASONING_EFFORT="${CODEX_NIGHTLY_REASONING_EFFORT_OVERRIDE:-'
        '${CODEX_NIGHTLY_REASONING_EFFORT:-max}}"'
    ) in source
    service = SERVICE.read_text("utf-8")
    assert "CODEX_NIGHTLY_MODEL=gpt-5.6-sol" in service
    assert "CODEX_NIGHTLY_REASONING_EFFORT=max" in service
    assert "--dangerously-bypass-approvals-and-sandbox" not in source
    assert source.index("check_constitution_core.py") < source.index(
        "controller_checkpoint.py claim"
    ) < source.index("cat docs/MASTER_QUANT_CONSTITUTION.md")
    assert "CHECKPOINT_RC=0" in source and "TRANSFER_RC=0" in source
    assert "HANDOFF_INCOMPLETE" in source
    assert '|| CHECKPOINT_RC=$?' in source
    assert '|| TRANSFER_RC=$?' in source


def test_midnight_builds_mt5_state_before_reasoning() -> None:
    wrapper = WRAPPER.read_text("utf-8")
    assert wrapper.index("--pipeline-start") < wrapper.index("build_mt5_midnight_state.py")
    assert "MT5/Fusion-only" in wrapper
    assert "legacy crypto-wide study registry" in wrapper


def test_controller_prompt_is_one_compact_mt5_only_operating_brief() -> None:
    prompt = PROMPT.read_text("utf-8")
    # Keep the nightly controller implementation-first and prevent mandate duplication
    # from silently consuming the reasoning budget again.
    assert len(prompt) <= 10_000
    for required in (
        "MASTER_QUANT_CONSTITUTION.md",
        "continuation cycle",
        "Never reset",
        "MT5/Fusion only",
        "Convert, do not summarize",
        "IMPLEMENTED+TESTED",
        "checkpoint",
        "scripts/run_deadman_switch.py",
    ):
        assert required.casefold() in prompt.casefold()
    assert MANDATE.exists() and len(MANDATE.read_text("utf-8")) > 20_000
    assert "controller_continuity.py" in AGENTS.read_text("utf-8")
    for excluded_venue in ("Binance", "Bybit", "OKX", "Hyperliquid"):
        assert "Do not hunt" in prompt and excluded_venue in prompt
    controller = CONTROLLER.read_text("utf-8")
    assert controller.count("cat ops/midnight_codex_prompt.txt") == 1
    assert "cat ops/shared_conversion_controller.txt" not in controller


def test_midnight_aggressively_converts_real_orphans_end_to_end() -> None:
    prompt = PROMPT.read_text("utf-8")
    for required in (
        "ORPHAN",
        "INERT",
        "CONVERSION_FAILURE",
        "WIRE+TEST, ARCHIVE, DELETE, or BLOCK",
        "producer -> durable output -> consumer -> decision/research",
    ):
        assert required in prompt


def test_midnight_routes_mt5_data_and_every_conversion_family() -> None:
    prompt = PROMPT.read_text("utf-8")
    for required in (
        "broker bars/ticks/DOM",
        "preregistered hypothesis",
        "near-survivor/survivor",
        "zero-capital forward shadow",
        "multiplicity/PBO/SPA",
        "failure and near-survivor recycling",
        "real-fill attribution",
        "Claude, Codex, OpenCode",
        "No hardcoded output quota",
    ):
        assert required in prompt
    controller = Path("ops/run_midnight_codex_controller.sh").read_text("utf-8")
    assert "SINGLE MT5-ONLY MIDNIGHT OPERATING BRIEF" in controller
    assert "shared_conversion_controller.txt" not in controller
