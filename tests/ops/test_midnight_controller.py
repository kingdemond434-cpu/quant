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
    # EXEC MOVED 2026-09-12 (ops/crontab.manifest "EXEC ROTTED" note): the committed unit runs
    # the controller directly, and the manifest's SYSTEMD line names that script so a
    # reconstitution installs what actually runs. The wrapper stays on disk with its ordering.
    service = SERVICE.read_text("utf-8")
    assert ("ExecStart=/bin/bash /home/quant/quant-platform/ops/"
            "run_midnight_codex_controller.sh") in service
    manifest = Path("ops/crontab.manifest").read_text("utf-8")
    assert ('SYSTEMD unit="quant-midnight-frontier.timer" on="*-*-* 00:00:00 Europe/Dublin" '
            'exec="ops/run_midnight_codex_controller.sh"') in manifest
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
        "scripts/run_midnight_completion.py",
        "scripts/build_mt5_midnight_state.py",
        "ops/run_midnight_codex_controller.sh",
    ]
    assert "data/constitution_core.lock" in contract["required_artifacts"]


def test_codex_controller_is_noninteractive_fenced_and_checkpointed() -> None:
    source = CONTROLLER.read_text("utf-8")
    for required in (
        "check_constitution_core.py",
        "codex login status",
        "--sandbox danger-full-access",
        "--dangerously-bypass-approvals-and-sandbox",
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
    assert "CODEX_NIGHTLY_TIMEOUT_SECONDS:-10800" in source
    # The unit file pins the model; the script must READ that pin rather than
    # overwrite it. _OVERRIDE stays as the operator escape hatch, but it can no
    # longer shadow the Environment= line into irrelevance.
    assert (
        'CODEX_NIGHTLY_MODEL="${CODEX_NIGHTLY_MODEL_OVERRIDE:-'
        '${CODEX_NIGHTLY_MODEL:-gpt-5.6-terra}}"'
    ) in source
    assert (
        'CODEX_NIGHTLY_REASONING_EFFORT="${CODEX_NIGHTLY_REASONING_EFFORT_OVERRIDE:-'
        '${CODEX_NIGHTLY_REASONING_EFFORT:-medium}}"'
    ) in source
    service = SERVICE.read_text("utf-8")
    assert "CODEX_NIGHTLY_MODEL=gpt-5.6-terra" in service
    assert "CODEX_NIGHTLY_REASONING_EFFORT=medium" in service
    # 4277867f (2026-09-14): the hard-coded 1200M/1500M killed the stage against 2251 MB free;
    # the limits are now DERIVED from the host's physical memory.
    for resource_control in ("MemoryHigh=50%", "MemoryMax=75%", "CPUWeight=25",
                             "IOSchedulingClass=idle", "OOMPolicy=stop"):
        assert resource_control in Path("ops/quant-external-pipeline.service").read_text("utf-8")
    assert "CODEX_GLOBAL_ARGS=(--dangerously-bypass-approvals-and-sandbox)" in source
    assert "CODEX_EXECUTION_ARGS=(--sandbox danger-full-access)" in source
    assert source.index("check_constitution_core.py") < source.index(
        "controller_checkpoint.py claim"
    ) < source.index("cat ops/midnight_codex_prompt.txt")
    assert "cat docs/MASTER_QUANT_CONSTITUTION.md" not in source
    assert "CHECKPOINT_RC=0" in source and "TRANSFER_RC=0" in source
    assert "HANDOFF_INCOMPLETE" in source
    assert "workspace write/sandbox failure; refusing false success" in source
    assert "sandbox denied the write" in source
    assert "CODEX_RC=126" in source
    assert '|| CHECKPOINT_RC=$?' in source
    assert '|| TRANSFER_RC=$?' in source


def test_shadow_forward_service_can_import_certified_enrolment_modules() -> None:
    # The unit now RUNS THE FILE rather than a `-c` import string (a unit naming no script is
    # invisible to the scheduler-manifest fence); the file puts desks/mt5 and research/ on
    # sys.path itself, which is what makes the certified-enrolment imports resolve.
    service = Path("ops/shadow-forward.service").read_text("utf-8")
    assert "desks/mt5/research/shadow_forward.py" in service
    assert "WorkingDirectory=/home/quant/quant-platform/desks/mt5" in service
    src = Path("desks/mt5/research/shadow_forward.py").read_text("utf-8")
    assert 'sys.path.insert(0, str(BASE / "research"))' in src
    assert "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))" in src


def test_midnight_builds_mt5_state_before_reasoning() -> None:
    wrapper = WRAPPER.read_text("utf-8")
    assert wrapper.index("--pipeline-start") < wrapper.index("build_mt5_midnight_state.py")
    assert wrapper.index("run_midnight_completion.py") < wrapper.index(
        "build_mt5_midnight_state.py"
    )
    assert "MT5/Fusion-only" in wrapper
    assert "legacy crypto-wide study registry" in wrapper


#: THE AGENDA WAS REPLACED, TWICE, ON PURPOSE: 5ac09b59 (2026-09-08, principal) made midnight a
#: repair-only controller, and 4277867f (2026-09-14) rewrote it as the STANDING AGENDA after the
#: adopt-chain repair ("Replace the previous ... agenda"). The three tests below pinned phrases of
#: the pre-09-08 brief; they now pin the invariants the current brief actually carries.


def test_controller_prompt_is_one_compact_mt5_only_operating_brief() -> None:
    raw = PROMPT.read_text("utf-8")
    prompt = " ".join(raw.split())          # the brief is hard-wrapped
    # Keep the nightly controller implementation-first and prevent mandate duplication
    # from silently consuming the reasoning budget again.
    assert len(raw) <= 10_000
    for required in (
        "STANDING AGENDA",
        "Preserve always-on miners",
        "Do not reset state",
        "do not replay completed tests or reset forward clocks",
        "Checkpoint after each completed unit",
        "DELIVER TO ORIGIN, NEVER TO A BOX",
        "Verify by content, not by SHA",
        "Do not reduce aggressiveness anywhere",
    ):
        assert required.casefold() in prompt.casefold(), required
    assert MANDATE.exists() and len(MANDATE.read_text("utf-8")) > 20_000
    assert "controller_continuity.py" in AGENTS.read_text("utf-8")
    controller = CONTROLLER.read_text("utf-8")
    assert controller.count("cat ops/midnight_codex_prompt.txt") == 1
    assert "cat ops/shared_conversion_controller.txt" not in controller
    # The MT5-only scope and the sealed constitution reach the controller through the wrapper
    # text it prints around the brief, not the brief itself.
    assert "SINGLE MT5-ONLY MIDNIGHT OPERATING BRIEF" in controller
    assert "MASTER_QUANT_CONSTITUTION.md passed scripts/check_constitution_core.py" in controller


def test_midnight_aggressively_converts_real_orphans_end_to_end() -> None:
    raw = PROMPT.read_text("utf-8")
    prompt = " ".join(raw.split())          # the brief is hard-wrapped
    for required in (
        "CANDIDATE CONSERVATION",
        "discovered = tested + queued + rejected + blocked",
        "lost must be zero",
        "STANDING FIXER and is scheduled NOWHERE. Wire it.",
        "done means it RUNS on a schedule and leaves an artifact",
    ):
        assert required in prompt, required


def test_midnight_routes_mt5_data_and_every_conversion_family() -> None:
    raw = PROMPT.read_text("utf-8")
    prompt = " ".join(raw.split())          # the brief is hard-wrapped
    for required in (
        "FORWARD LANE",
        "Make every rebase leave a record and refuse a silent one",
        "An absence is a verdict (UNMEASURED), never a zero and never a",
        "Do not fabricate one",
        "The 20% heat floor, the 0.02-lot gold floor",
    ):
        assert required in prompt, required
    controller = Path("ops/run_midnight_codex_controller.sh").read_text("utf-8")
    assert "SINGLE MT5-ONLY MIDNIGHT OPERATING BRIEF" in controller
    assert "shared_conversion_controller.txt" not in controller
