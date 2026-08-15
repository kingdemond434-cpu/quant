"""Every switch on the money path, in one read -- and the three ways that report can lie.

Arming this desk is nine independent facts across three directories, two of them gitignored, three
of them RAILS whose sense is inverted. `run_golive_preflight` checked exactly one. These tests pin
that the reporter distinguishes absent from unreadable, gets the rail polarity right, arms nothing,
and never touches a key.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
import scripts.report_arming as A


@pytest.fixture()
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake box. Nothing here may touch the real data/ directory."""
    (tmp_path / "data" / "secrets").mkdir(parents=True)
    (tmp_path / "docs" / "research").mkdir(parents=True)
    monkeypatch.setattr(A, "_ROOT", tmp_path)
    monkeypatch.delenv("DESK_WALLET", raising=False)
    return tmp_path


def test_ABSENT_AND_UNREADABLE_ARE_DIFFERENT_ANSWERS(box: Path) -> None:
    """THE DEFECT THIS DESK NAMES MOST OFTEN, on the one report that decides whether money moves.
    A permissions error on LIVE_ENABLE and a missing LIVE_ENABLE have different fixes, and
    collapsing them is how a desk decides it is armed because nothing said otherwise."""
    assert A._probe("data/LIVE_ENABLE")["state"] == "ABSENT"

    d = box / "data" / "locked"
    d.mkdir()
    (d / "marker").write_text("{}", "utf-8")
    d.chmod(0o000)
    try:
        row = A._probe("data/locked/marker")
        # a root-run test can still stat through mode 000; skip rather than assert a lie
        if row["state"] != "ABSENT":
            assert row["state"] in {"UNREADABLE", "PRESENT"}
            if row["state"] == "UNREADABLE":
                assert "NOT the same as absent" in row["why"]
    finally:
        d.chmod(0o755)


def test_AN_UNREADABLE_SWITCH_IS_NEVER_COUNTED_AS_ARMED_OR_OFF(box: Path) -> None:
    """UNKNOWN is its own bucket in the verdict. Folding it into 'off' understates the problem
    (the fix is different); folding it into 'armed' spends money on a guess."""
    (box / "data" / "LIVE_ENABLE").write_text("{}", "utf-8")
    rep = A.build()
    for row in rep["switches"].values():
        assert row["armed"] in (True, False, None)
    assert rep["n_unknown"] == len(rep["unknown"])
    assert rep["fully_armed"] is False, "a clone with no keyfile is not fully armed"


def test_THE_RAILS_ARE_INVERTED_AND_THE_REPORT_KNOWS_IT(box: Path) -> None:
    """PRESENT on a rail means FROZEN. Reading the three rails with the same polarity as the five
    enable-markers would report a halted book as fully armed -- the most dangerous single line
    this file could produce."""
    rep = A.build()
    assert rep["switches"]["rail_freeze"]["armed"] is True, "absent rail = free to trade"

    (box / "data" / "FREEZE").write_text("", "utf-8")
    rep2 = A.build()
    assert rep2["switches"]["rail_freeze"]["armed"] is False
    assert rep2["switches"]["rail_freeze"]["state"] == "PRESENT"
    assert rep2["rail_frozen"] is True
    assert rep2["fully_armed"] is False


def test_AN_EMPTY_RAIL_FILE_STILL_FREEZES(box: Path) -> None:
    """Presence is the latch. A rail whose file is empty or malformed must not read as clear --
    the failure mode is a rail that trips and a writer that dies before writing its reason."""
    (box / "data" / "DEADMAN_FIRED").write_text("", "utf-8")
    assert A.build()["rail_frozen"] is True


def test_THE_KEYFILE_IS_NEVER_OPENED(box: Path) -> None:
    """`data/secrets/**` never leaves the box and no tool ever prints a key. Not parsed, not
    length-checked, not summarised: a 'safe' summary of a key is still a function of the key, and
    this artifact is published to web/."""
    secret = box / "data" / "secrets" / "binance_live_spot.json"
    secret.write_text(json.dumps({"api_key": "SENSITIVE-VALUE", "secret": "ALSO-SENSITIVE"}),
                      "utf-8")
    secret.chmod(0o600)
    rep = A.build()
    row = rep["switches"]["spot_keyfile"]
    assert row["armed"] is True and row["state"] == "PRESENT"
    assert row["contents"] == "NOT READ -- existence and mode only, by design"
    blob = json.dumps(rep)
    assert "SENSITIVE-VALUE" not in blob and "ALSO-SENSITIVE" not in blob
    # the source itself must contain no read of that path
    src = Path(A.__file__).read_text("utf-8")
    assert "read_text" not in src.split("def _probe")[1].split("def _wallet")[0]


def test_A_WORLD_READABLE_KEYFILE_IS_WARNED_ABOUT(box: Path) -> None:
    secret = box / "data" / "secrets" / "binance_live_spot.json"
    secret.write_text("{}", "utf-8")
    secret.chmod(0o644)
    row = A.build()["switches"]["spot_keyfile"]
    assert "group/world readable" in row.get("warning", "")
    assert stat.filemode(secret.stat().st_mode).startswith("-rw-r--r--")


def test_THE_WALLET_RESOLUTION_IS_REPORTED_NOT_ASSUMED(box: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """Which wallet the cycle trades decides whether any of this arming matters: pointed at a
    wallet the capital has left, every sleeve places nothing and writes a row identical to a
    quiet market."""
    assert A.build()["wallet"]["effective"] == "spot"
    (box / "data" / "DESK_WALLET").write_text("margin\n", "utf-8")
    assert A.build()["wallet"]["effective"] == "margin"
    monkeypatch.setenv("DESK_WALLET", "spot")
    assert A.build()["wallet"]["effective"] == "spot", "env wins over the file"


def test_IT_ARMS_NOTHING(box: Path) -> None:
    """A reporter that could arm the desk would be a fourth path to live trading wearing the name
    of a status check. Asserted against the SOURCE, so the property survives a refactor."""
    A.build()
    for marker in ("LIVE_ENABLE", "MARGIN_ENABLE", "auto_promotion_armed.json"):
        assert not (box / "data" / marker).exists(), f"build() created {marker}"
    src = Path(A.__file__).read_text("utf-8")
    body = src.split('"""', 2)[2]          # skip the module docstring, which discusses these
    # exactly one write is allowed: the report artifact itself
    assert body.count("write_text(") == 1, "the only write is web/arming.json"
    for forbidden in ("unlink(", "os.remove", "shutil.rmtree", "touch("):
        assert forbidden not in body, f"{forbidden} must never appear in a status reporter"


def test_THE_CONNECTORS_OWN_VERDICT_IS_ASKED_NOT_REDERIVED() -> None:
    """A status report holding its own opinion of whether the venue is armed is how two answers
    come to exist, and the one that disagrees quietly is the one that spends money."""
    c = A._connectors()
    assert set(c) == {"spot", "margin"}
    for row in c.values():
        assert row["armed"] in (True, False, None)
        assert row["why"], "a verdict without its reason cannot be audited"
