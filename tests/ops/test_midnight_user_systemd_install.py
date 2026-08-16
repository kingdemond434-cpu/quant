"""Rootless midnight scheduling must not clone the entire system timer plane."""

from __future__ import annotations

from pathlib import Path

RECONSTITUTE = Path("deploy/reconstitute_cron.sh")
SERVICE = Path("ops/quant-midnight-frontier.service")


def test_system_midnight_service_can_find_repo_and_user_installed_tools() -> None:
    service = SERVICE.read_text("utf-8")
    assert "Environment=\"PATH=" in service
    assert "/home/quant/quant-platform/.venv/bin" in service
    assert "/home/quant/.local/bin" in service
    assert "TimeoutStartSec=18h" in service
    assert "KillMode=control-group" in service


def test_non_root_fallback_installs_only_the_midnight_pair_as_user_units() -> None:
    source = RECONSTITUTE.read_text("utf-8")
    assert 'USER_CONFIG_HOME=${XDG_CONFIG_HOME:-"$USER_HOME/.config"}' in source
    assert 'USER_SYSTEMD_DIR="$USER_CONFIG_HOME/systemd/user"' in source
    assert '"$USER_SYSTEMD_DIR/quant-midnight-frontier.service"' in source
    assert '"$USER_SYSTEMD_DIR/quant-midnight-frontier.timer"' in source
    assert "systemctl --user daemon-reload" in source
    assert "systemctl --user enable --now quant-midnight-frontier.timer" in source
    assert "systemctl --user is-enabled --quiet quant-midnight-frontier.timer" in source
    assert "systemctl --user is-active --quiet quant-midnight-frontier.timer" in source
    assert "--no-ask-password enable-linger" in source

    user_install = source[source.index("SYSTEM_MIDNIGHT_LIVE=0") :]
    for other in (
        "quant-blindrediscovery",
        "quant-dataaxis",
        "quant-frontier",
        "quant-litminer",
        "quant-prospector",
    ):
        assert f'$USER_SYSTEMD_DIR/{other}' not in user_install


def test_user_service_is_derived_without_a_user_directive_and_with_runtime_paths() -> None:
    source = RECONSTITUTE.read_text("utf-8")
    assert "/^User=/ { next }" in source
    assert 'root "/.venv/bin:" home "/.local/bin' in source
    assert 'print "WorkingDirectory=" root' in source
    assert 'print "ExecStart=/bin/bash " root "/ops/run_midnight_frontier.sh"' in source


def test_rootless_fallback_refuses_a_duplicate_system_midnight_launcher() -> None:
    source = RECONSTITUTE.read_text("utf-8")
    assert "for u in quant-midnight-frontier quant-research" in source
    assert 'systemctl is-enabled "$u.timer"' in source
    assert 'systemctl is-active "$u.timer"' in source
    assert 'if [ "$SYSTEM_MIDNIGHT_LIVE" -eq 0 ]' in source


def test_root_install_path_still_installs_and_enables_all_committed_units() -> None:
    source = RECONSTITUTE.read_text("utf-8")
    assert "if [ -d /etc/systemd/system ] && [ -w /etc/systemd/system ]" in source
    assert 'cp -f "$ROOT/ops/$u.timer" "$ROOT/ops/$u.service" /etc/systemd/system/' in source
    assert 'systemctl enable --now "$u.timer"' in source
