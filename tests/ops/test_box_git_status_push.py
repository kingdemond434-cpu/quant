"""ops/box_git/status_push.py: the box publishes desk status off-box with no Claude session."""
from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ops.box_git import status_push as S

NOW = datetime(2026, 11, 24, 17, tzinfo=UTC)


def _st(tmp: Path, files: tuple[str, ...], url: str = "") -> S.Status:
    (tmp / "keys").mkdir(exist_ok=True)
    return S.Status(url=url or "git@gitlab.com:o/d.git", key=tmp / "keys" / "status_ed25519",
                    checkout=tmp / "co", root=tmp / "desk", files=files)


def test_scrub_drops_credentials_and_identities_at_any_depth():
    doc = {"equity": 101.5, "login": 123, "Server": "x", "nested": [{"api_key": "k", "r": 1.2}],
           "account_number": 9, "trades_today": 3, "password": "p"}
    assert S.scrub(doc) == {"equity": 101.5, "nested": [{"r": 1.2}], "trades_today": 3}


def test_collect_reads_only_safe_allow_listed_json(tmp_path):
    desk = tmp_path / "desk"
    (desk / "desks/mt5/data").mkdir(parents=True)
    (desk / "desks/mt5/data/account_state.json").write_text(
        json.dumps({"e8": {"equity": 99000, "login": 5}}), encoding="utf-8")
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")
    st = _st(tmp_path, ("desks/mt5/data/account_state.json", "../secret.json",
                        "C:/x.json", "data/secrets/llm_panel.txt", "missing.json"))
    got = S.collect(st, NOW, {"loop": {"pr": "ok"}})
    assert got["desks__mt5__data__account_state.json"] == {"e8": {"equity": 99000}}
    assert set(got) == {"desks__mt5__data__account_state.json", "missing.json", "SUMMARY.json"}
    assert got["SUMMARY.json"]["loop"] == {"pr": "ok"}


def test_oversize_file_is_named_not_published(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "MAX_FILE", 4)
    (tmp_path / "desk").mkdir()
    (tmp_path / "desk/big.json").write_text('{"a": 12345}', encoding="utf-8")
    got = S.collect(_st(tmp_path, ("big.json",)), NOW)
    assert "omitted" in got["big.json"]


def test_push_writes_one_orphan_commit_to_the_status_branch_hourly(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    (tmp_path / "desk").mkdir()
    (tmp_path / "desk/a.json").write_text('{"equity": 1, "token": "t"}', encoding="utf-8")
    st = _st(tmp_path, ("a.json",), url=remote.resolve().as_uri())
    state = tmp_path / "state"
    state.mkdir()
    assert S.push(st, state, NOW).startswith("status pushed")
    assert S.push(st, state, NOW + timedelta(minutes=10)) == "status: not due"
    assert S.push(st, state, NOW + timedelta(hours=1)).startswith("status pushed")
    log = subprocess.run(["git", "-C", str(remote), "log", "--oneline", S.STATUS_BRANCH],
                         capture_output=True, text=True, check=True).stdout.strip().splitlines()
    assert len(log) == 1                                 # orphan, force-pushed: one commit
    body = subprocess.run(["git", "-C", str(remote), "show", f"{S.STATUS_BRANCH}:a.json"],
                          capture_output=True, text=True, check=True).stdout
    assert json.loads(body) == {"equity": 1}
    heads = subprocess.run(["git", "-C", str(remote), "for-each-ref", "--format=%(refname)"],
                           capture_output=True, text=True, check=True).stdout.split()
    assert heads == ["refs/heads/status"]                # never main


def test_failed_push_says_why_and_stays_due(tmp_path):
    (tmp_path / "desk").mkdir()
    st = _st(tmp_path, (), url=(tmp_path / "nowhere.git").as_uri())
    out = S.push(st, tmp_path, NOW)
    assert out.startswith("status not pushed") and S.due(tmp_path, NOW)


def test_installer_uses_its_own_key_and_never_the_drop_key():
    src = (Path(__file__).resolve().parents[2] / "ops/box_git/install_status.ps1").read_text(
        encoding="utf-8")
    assert "status_ed25519" in src and "drop_ed25519" not in src
    assert "QuantForge-Status" in src and "branch=status" in src


def test_scrub_redacts_ips_hosts_and_raw_account_ids():
    """Audit MF-1: key names alone missed {'account': 51234567, 'host': ..., 'ip': ...}."""
    doc = {"account": 51234567, "host": "10.1.2.3", "ip": "1.2.3.4",
           "note": "connected to 62.0.0.1 ok", "rows": [{"account": "E8", "r": 0.4},
                                                       {"account": "FTMO-2", "r": -1.0},
                                                       {"account": "51234567", "r": 1}],
           "terminal_path": "C:/x", "endpoint": "https://a", "v6": "fe80:0:0:0:1:2:3:4"}
    assert S.scrub(doc) == {"account": "[id]", "note": "connected to [ip] ok",
                            "rows": [{"account": "E8", "r": 0.4},
                                     {"account": "FTMO-2", "r": -1.0},
                                     {"account": "[id]", "r": 1}],
                            "v6": "[ip]"}


def test_status_never_goes_to_the_drop_project(tmp_path):
    """Audit MF-2: a write-capable box key never sits on the drop project."""
    cfg = tmp_path / "loop.json"
    cfg.write_text(json.dumps({"state": str(tmp_path / "s.json"),
                               "drop": {"url": "git@gitlab.com:o/drop.git"},
                               "status": {"url": "git@gitlab.com:O/drop", "key": "k",
                                          "checkout": "c", "root": "r"}}), encoding="utf-8")
    try:
        S.from_config(cfg)
        raise AssertionError("status url equal to the drop url was accepted")
    except ValueError as exc:
        assert "drop" in str(exc)
    src = (Path(__file__).resolve().parents[2] / "ops/box_git/install_status.ps1").read_text(
        encoding="utf-8")
    assert "StatusUrl equals the drop url" in src


def test_account_label_never_passes_a_login_with_a_letter_prefix():
    assert S.scrub({"account": "a51234567"}) == {"account": "[id]"}
    assert S.scrub({"account": "Fusion"}) == {"account": "Fusion"}


def test_clock_times_survive_and_short_ipv6_is_redacted():
    assert S.scrub({"t": "2026-11-24 17:10:08"}) == {"t": "2026-11-24 17:10:08"}
    assert S.scrub({"n": "via fe80::1 and ::1 and 2001:db8:0:0:1:0:0:1"}) == {
        "n": "via [ip] and [ip] and [ip]"}
