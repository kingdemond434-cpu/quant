"""ONE ANSWER TO "IS THIS THE TRADING BOX?" (PR #130 audit, follow-up 1).

`libs/ops/host_identity` keys the answer on the machine's stable id (/etc/machine-id, or the
MachineGuid registry value on Windows) against the id recorded in config/trading_host.json. A
hostname is only a reported fallback: it can make an answer UNMEASURED, never TRADING.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops import host_identity as hi

ROOT = Path(__file__).resolve().parents[2]
BOX = "0123456789abcdef0123456789abcdef"
OTHER = "fedcba9876543210fedcba9876543210"
CFG = {"hostname": "vmi3571445", "machine_id": BOX}


def test_the_recorded_id_decides_and_the_hostname_never_does() -> None:
    assert hi.classify(BOX, "vmi3571445", CFG).verdict == hi.TRADING
    assert hi.classify(BOX.upper(), "renamed", CFG).verdict == hi.TRADING
    imp = hi.classify(OTHER, "vmi3571445", CFG)
    assert imp.verdict == hi.OFF_BOX and not imp.may_be_trading and not imp.confirmed_trading
    assert "a label is not an identity" in imp.why
    assert hi.classify(OTHER, "ubuntu-4gb-hel1-5", CFG).verdict == hi.OFF_BOX


def test_an_unreadable_or_unrecorded_id_is_unmeasured_not_a_guess() -> None:
    for ident in (hi.classify(None, "vmi3571445", CFG),
                  hi.classify(BOX, "vmi3571445", {"hostname": "vmi3571445", "machine_id": None})):
        assert ident.verdict == hi.UNMEASURED
        assert ident.confirmed_trading is False          # never grants credit
        assert ident.may_be_trading is True              # a loud fence stays loud on the box
        assert ident.hostname_match is True and "never taken as the identity" in ident.why
    off = hi.classify(None, "vmi3500897", CFG)
    assert off.verdict == hi.UNMEASURED and off.may_be_trading is False
    # a prefix is not a match: the build box's name shares the trading box's first letters
    assert hi.classify(None, "vmi35714450", CFG).hostname_match is False
    assert hi.classify(None, "VMI3571445.contaboserver.net", CFG).hostname_match is True


def test_a_committed_document_is_judged_by_the_id_it_carries() -> None:
    assert hi.is_recorded_trading_id(BOX, CFG) is True
    assert hi.is_recorded_trading_id(OTHER, CFG) is False
    assert hi.is_recorded_trading_id(None, CFG) is None
    assert hi.is_recorded_trading_id("UNMEASURED", CFG) is None
    assert hi.is_recorded_trading_id(BOX, {"hostname": "vmi3571445"}) is None


def test_this_machine_is_measured_without_raising() -> None:
    ident = hi.identify()
    assert ident.verdict in (hi.TRADING, hi.OFF_BOX, hi.UNMEASURED)
    assert set(ident.as_dict()) >= {"verdict", "machine_id", "hostname", "may_be_trading"}


def test_the_committed_config_names_the_trading_box() -> None:
    cfg = json.loads((ROOT / hi.CONFIG_REL).read_text("utf-8"))
    assert cfg["hostname"] == "vmi3571445"
    assert "machine_id" in cfg


def test_record_refuses_off_the_trading_box(tmp_path: Path) -> None:
    cfg = tmp_path / "trading_host.json"
    cfg.write_text(json.dumps({"hostname": "vmi3571445", "machine_id": None}), "utf-8")
    with pytest.raises(SystemExit, match="refused"):
        hi.record(cfg, identity=hi.classify(OTHER, "vmi3500897", {"hostname": "vmi3571445"}))
    with pytest.raises(SystemExit, match="unreadable"):
        hi.record(cfg, identity=hi.classify(None, "vmi3571445", {"hostname": "vmi3571445"}))
    written = hi.record(cfg, identity=hi.classify(BOX, "vmi3571445", {"hostname": "vmi3571445"}))
    assert written["machine_id"] == BOX
    assert hi.classify(BOX, "whatever", hi.load_config(cfg)).verdict == hi.TRADING


def test_every_host_question_goes_through_the_helper() -> None:
    """The three organs the audit named ask ONE helper, never a prefix or a file's mtime."""
    for rel in ("libs/tiers/box_evidence.py", "scripts/check_placement_interlock.py",
                "scripts/check_birth_obligations.py"):
        src = (ROOT / rel).read_text("utf-8")
        assert "host_identity" in src, rel
        assert ".startswith(TRADING_HOST)" not in src, rel
    birth = (ROOT / "scripts" / "check_birth_obligations.py").read_text("utf-8")
    body = birth[birth.index("def _is_trading_host"):birth.index("def _source_age_h")]
    assert "gateway_state" not in body and "st_mtime" not in body


def test_birth_obligations_judges_by_the_helper(monkeypatch: pytest.MonkeyPatch,
                                                tmp_path: Path) -> None:
    """A tracked gateway_state.json freshly written by git no longer makes a checkout 'the box';
    the recorded id (or an UNMEASURED id with the trading hostname) does."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "birth_hi", ROOT / "scripts" / "check_birth_obligations.py")
    assert spec and spec.loader
    birth = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(birth)
    gs = tmp_path / "desks" / "mt5" / "data" / "gateway_state.json"
    gs.parent.mkdir(parents=True)
    gs.write_text("{}", "utf-8")                       # fresh mtime: the old instrument said yes
    monkeypatch.setattr(hi, "identify", lambda config_path=None: hi.classify(OTHER, "vm", CFG))
    assert birth._is_trading_host(tmp_path) is False
    monkeypatch.setattr(hi, "identify", lambda config_path=None: hi.classify(BOX, "vm", CFG))
    assert birth._is_trading_host(tmp_path) is True
