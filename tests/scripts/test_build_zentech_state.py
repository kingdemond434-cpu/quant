from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_zentech_state.py"
SPEC = importlib.util.spec_from_file_location("build_zentech_state", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_missing_values_never_become_fake_zero() -> None:
    assert module._number(None, "missing") is None
    assert module._number(None, 0) == 0.0


def test_dashboard_identity_and_research_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "DESK", tmp_path / "desks" / "mt5")
    payload = module.build()
    assert payload["identity"]["name"] == "QUANT DESK"
    assert payload["account"]["equity"] is None
    assert payload["health"]["status"] == "UNMEASURED"


def test_terminal_shadow_rows_never_display_promotion_authority(
    monkeypatch, tmp_path: Path
) -> None:
    """Retained provenance must not look like a current promotion permission."""
    desk = tmp_path / "desks" / "mt5"
    shadow = desk / "reports" / "shadow"
    shadow.mkdir(parents=True)
    (shadow / "shadow_state.json").write_text(json.dumps({
        "retired": {"status": "RETIRED_ORPHAN", "n": 4, "exp_r": 0.2,
                    "promotion_authority": True},
        "active": {"status": "ACTIVE", "n": 4, "exp_r": 0.2,
                   "promotion_authority": True},
    }), encoding="utf-8")
    (shadow / "qquant_shadow_state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "DESK", desk)

    rows = {row["name"]: row for row in module._shadow_rows()}
    assert rows["retired"]["source_promotion_authority"] is True
    assert rows["retired"]["promotion_authority"] is False
    assert rows["active"]["promotion_authority"] is True

def test_stale_issue_board_cannot_render_a_clean_current_verdict(monkeypatch, tmp_path):
    from datetime import UTC, datetime

    reports = tmp_path / 'reports'
    reports.mkdir()
    path = reports / 'ISSUE_BOARD.json'
    original = {'measured_at': '2026-09-11T08:11:34+00:00', 'issues': [],
                'count': 0, 'by_severity': {}}
    path.write_text(json.dumps(original))
    monkeypatch.setattr(module, 'DESK', tmp_path)
    board = module._issue_board(datetime(2026, 9, 12, 3, tzinfo=UTC))
    assert board['freshness']['status'] == 'STALE'
    assert board['issues'][0]['key'] == 'stale:issue_board'
    assert board['count'] == 1
    assert board['measured_at'] == original['measured_at']
    assert json.loads(path.read_text()) == original


def test_issue_board_preserves_alarm_and_refuses_unknown_or_future_time(monkeypatch, tmp_path):
    from datetime import UTC, datetime

    reports = tmp_path / 'reports'
    reports.mkdir()
    monkeypatch.setattr(module, 'DESK', tmp_path)
    alarm = {'key': 'alarm:CANARY_ALARM.txt', 'severity': 'CAPITAL'}
    for stamp in (None, 'invalid', '2026-09-13T00:00:00Z'):
        (reports / 'ISSUE_BOARD.json').write_text(json.dumps({
            'measured_at': stamp, 'issues': [alarm], 'by_severity': {'CAPITAL': 1},
        }))
        board = module._issue_board(datetime(2026, 9, 12, 3, tzinfo=UTC))
        assert board['freshness']['status'] == 'UNMEASURED'
        assert board['issues'][0] == alarm
        assert board['by_severity'] == {'CAPITAL': 1, 'BLIND': 1}


def test_fresh_issue_board_has_no_synthetic_alarm(monkeypatch, tmp_path):
    from datetime import UTC, datetime

    reports = tmp_path / 'reports'
    reports.mkdir()
    monkeypatch.setattr(module, 'DESK', tmp_path)
    original = {'measured_at': '2026-09-12T02:30:00Z', 'issues': [], 'count': 0}
    (reports / 'ISSUE_BOARD.json').write_text(json.dumps(original))
    board = module._issue_board(datetime(2026, 9, 12, 3, tzinfo=UTC))
    assert board['freshness']['status'] == 'FRESH'
    assert board['issues'] == []
    assert board['count'] == 0


def test_staged_pull_account_is_used_without_publishing_raw_issues(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'DESK', tmp_path / 'desks/mt5')
    monkeypatch.setattr(module, '_mt5_snapshot', lambda: {})
    monkeypatch.setenv('QUANT_DESK_PULL_SNAPSHOT', 'incoming.json')
    (tmp_path / 'web').mkdir()
    published = {'account': {'equity': 10}, 'issues': {'count': 99}}
    (tmp_path / 'web/desk_state.json').write_text(json.dumps(published))
    (tmp_path / 'incoming.json').write_text(json.dumps({
        'account': {'equity': 607.68, 'balance': 607.68}, 'issues': {'count': 0},
    }))
    payload = module.build()
    assert payload['account']['equity'] == 607.68
    assert payload['issues']['freshness']['status'] == 'UNMEASURED'
    assert payload['issues']['count'] == 1
    assert json.loads((tmp_path / 'web/desk_state.json').read_text()) == published
