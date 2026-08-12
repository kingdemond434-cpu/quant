"""Arming the pager: the config is not the proof, the delivery is.

The desk's binding constraint is a pager that has been silent since 2026-07-30. These tests pin
the one property that makes an armer trustworthy -- it must be IMPOSSIBLE to finish believing you
are armed when nothing was delivered.
"""
from __future__ import annotations

import json

import pytest
import scripts.arm_alert_channel as ARM


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    cfg = tmp_path / "data/secrets/alert_channels.json"
    flag = tmp_path / "data/ALERT_CHANNELS_SILENT"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("silent since forever", "utf-8")
    monkeypatch.setattr(ARM, "CONFIG", cfg)
    monkeypatch.setattr(ARM, "SILENT_FLAG", flag)
    return cfg, flag


def _fake_ac(monkeypatch, *, delivers: bool, existing=None):
    sent = {}
    monkeypatch.setattr(ARM.AC, "load_channels", lambda *a, **k: list(existing or []))
    monkeypatch.setattr(ARM.AC, "status", lambda *a, **k: {"armed": 1, "armed_kinds": ["ntfy"]})

    def send_all(title, body, **kw):
        sent["title"] = title
        return {}
    monkeypatch.setattr(ARM.AC, "send_all", send_all)
    rows = [{"ts": "9999-01-01T00:00:00+00:00", "channel": "ntfy", "ok": delivers,
             "detail": "http 200" if delivers else "http 403"}]
    monkeypatch.setattr(ARM.AC, "ledger_tail", lambda n=20, **k: rows)
    return sent


# ------------------------------------------------------------------ the load-bearing property
def test_a_failed_delivery_reverts_the_config(sandbox, monkeypatch) -> None:
    """THE POINT. A config that cannot deliver is worse than none: it reads as armed on every
    dashboard while the desk is silent."""
    cfg, _ = sandbox
    _fake_ac(monkeypatch, delivers=False)
    rc = ARM.main(["--kind", "ntfy", "--topic", "t"])
    assert rc == 1
    assert not cfg.exists(), "a channel that never delivered must not be left armed"


def test_a_failed_delivery_leaves_a_prior_working_config_intact(sandbox, monkeypatch) -> None:
    """Arming a NEW bad channel must not disarm the one that already worked."""
    cfg, _ = sandbox
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"channels": [{"kind": "webhook", "url": "https://good"}]}), "utf-8")
    _fake_ac(monkeypatch, delivers=False, existing=[{"kind": "webhook", "url": "https://good"}])
    ARM.main(["--kind", "ntfy", "--topic", "t"])
    assert json.loads(cfg.read_text())["channels"][0]["kind"] == "webhook"


def test_a_successful_delivery_arms_and_clears_the_silence_flag(sandbox, monkeypatch) -> None:
    cfg, flag = sandbox
    _fake_ac(monkeypatch, delivers=True)
    assert ARM.main(["--kind", "ntfy", "--topic", "t"]) == 0
    assert cfg.exists() and not flag.exists()


def test_the_silence_flag_is_cleared_by_delivery_never_by_editing(sandbox, monkeypatch) -> None:
    """It clears itself on the next successful delivery -- nothing else clears it."""
    _, flag = sandbox
    _fake_ac(monkeypatch, delivers=False)
    ARM.main(["--kind", "ntfy", "--topic", "t"])
    assert flag.exists(), "a failed arming must NOT clear the silence flag"


# ------------------------------------------------------------------ secrets and permissions
def test_the_config_is_written_0600(sandbox, monkeypatch) -> None:
    """A pager token in a world-readable file is a credential leak that also pages you."""
    cfg, _ = sandbox
    _fake_ac(monkeypatch, delivers=True)
    ARM.main(["--kind", "telegram", "--token", "secret-token", "--chat-id", "123"])
    assert oct(cfg.stat().st_mode)[-3:] == "600"


def test_secrets_are_masked_in_stdout(sandbox, monkeypatch, capsys) -> None:
    _fake_ac(monkeypatch, delivers=True)
    ARM.main(["--kind", "telegram", "--token", "supersecrettoken", "--chat-id", "9911223344"])
    out = capsys.readouterr().out
    assert "supersecrettoken" not in out and "9911223344" not in out


def test_masking_never_reveals_a_short_secret_whole() -> None:
    assert ARM._mask("abc") == "***" and "abc" not in ARM._mask("abc")


# ------------------------------------------------------------------ additive, not replacing
def test_arming_a_second_kind_keeps_the_first(sandbox, monkeypatch) -> None:
    """Two channels on one provider is one channel wearing two hats -- the panel finding was
    INDEPENDENCE, so arming must be additive across kinds."""
    cfg, _ = sandbox
    _fake_ac(monkeypatch, delivers=True, existing=[{"kind": "webhook", "url": "https://a"}])
    ARM.main(["--kind", "ntfy", "--topic", "t"])
    kinds = {c["kind"] for c in json.loads(cfg.read_text())["channels"]}
    assert kinds == {"webhook", "ntfy"}


def test_rearming_the_same_kind_replaces_rather_than_duplicates(sandbox, monkeypatch) -> None:
    cfg, _ = sandbox
    _fake_ac(monkeypatch, delivers=True, existing=[{"kind": "ntfy", "topic": "old"}])
    ARM.main(["--kind", "ntfy", "--topic", "new"])
    chans = json.loads(cfg.read_text())["channels"]
    assert len(chans) == 1 and chans[0]["topic"] == "new"


# ------------------------------------------------------------------ refusals
def test_missing_required_args_refuse_rather_than_write_a_broken_config(sandbox) -> None:
    for argv in (["--kind", "ntfy"], ["--kind", "telegram", "--token", "t"], ["--kind", "webhook"]):
        with pytest.raises(SystemExit):
            ARM.main(argv)
    assert not sandbox[0].exists()


def test_verify_on_an_unarmed_box_reports_rather_than_pretending(monkeypatch, sandbox) -> None:
    monkeypatch.setattr(ARM.AC, "status", lambda *a, **k: {"armed": 0, "armed_kinds": []})
    assert ARM.main(["--verify"]) == 2


def test_keep_on_failure_is_opt_in_only(sandbox, monkeypatch) -> None:
    """The dangerous behaviour -- leaving an undelivering config in place -- must never be the
    default."""
    cfg, _ = sandbox
    _fake_ac(monkeypatch, delivers=False)
    ARM.main(["--kind", "ntfy", "--topic", "t", "--keep-on-failure"])
    assert cfg.exists(), "explicit opt-in keeps it"
    cfg.unlink()
    ARM.main(["--kind", "ntfy", "--topic", "t"])
    assert not cfg.exists(), "default reverts"
