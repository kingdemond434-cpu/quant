"""THE FENCE DECLARES THE LIVE LOGINS FROM THE BOX'S OWN ACCOUNT FILES (2026-10-29).

On the box neither QUANT_FENCE_ACCOUNT_IDS (a user env var never reaches MT5-ShadowSync, which
runs as SYSTEM) nor ACCOUNT_PROFILES.json (it would change live sizing through
gateway.venue_heat_cap) exists, so the fence read UNMEASURED and paged every 6h. It now also reads
the `login` of FUSION_LIVE_ACCOUNT.json and FTMO_LIVE_ACCOUNT.json, which already hold the live
logins. Strictness is kept: a present file that cannot be parsed, or whose login is not 4-12
ASCII digits, is a FenceConfigError; an absent one declares nothing. Every number is synthetic.
"""
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from libs.ops import login_fence as lf

FUSION_REL, FTMO_REL = (rel for rel, _ in lf.ACCOUNT_FILES)
_FUSION, _FTMO = "70010042", "51230077"


def _folded(zero: int) -> str:
    """_FUSION in another digit block (0x0660 Arabic-Indic, 0xFF10 fullwidth): not ASCII."""
    return "".join(chr(zero + int(c)) for c in _FUSION)


def _write(root: Path, rel: str, doc: Any) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc if isinstance(doc, str) else json.dumps(doc), "utf-8")
    return p


def test_the_sources_are_the_fusion_and_ftmo_files_by_their_login_field() -> None:
    assert dict(lf.ACCOUNT_FILES) == {"desks/mt5/data/FUSION_LIVE_ACCOUNT.json": "login",
                                      "desks/mt5/data/FTMO_LIVE_ACCOUNT.json": "login"}


def test_the_fusion_file_declares_its_login(tmp_path: Path) -> None:
    # decision_core.fusion_live_login's shape: an int login on FusionMarkets-Live.
    _write(tmp_path, FUSION_REL, {"login": int(_FUSION), "server": "FusionMarkets-Live"})
    assert lf.declared(tmp_path, {}) == (frozenset({_FUSION}), ("FUSION_LIVE_ACCOUNT.json",))


def test_the_ftmo_file_declares_its_login(tmp_path: Path) -> None:
    # ftmo_follower.bound_account's shape; the login may be written as a string.
    _write(tmp_path, FTMO_REL, {"login": f" {_FTMO} ", "server": "FTMO-Server",
                                "trade_mode": 0, "initial_balance": 10000,
                                "account_type": "2-step"})
    assert lf.declared(tmp_path, {}) == (frozenset({_FTMO}), ("FTMO_LIVE_ACCOUNT.json",))


def test_every_source_together_and_the_names_of_those_that_contributed(tmp_path: Path) -> None:
    _write(tmp_path, FUSION_REL, {"login": int(_FUSION), "server": "FusionMarkets-Live"})
    _write(tmp_path, FTMO_REL, {"login": int(_FTMO), "server": "FTMO-Server"})
    ids, sources = lf.declared(tmp_path, {lf.ID_ENV: "1234567"})
    assert ids == frozenset({_FUSION, _FTMO, "1234567"})
    assert sources == (lf.ID_ENV, "FUSION_LIVE_ACCOUNT.json", "FTMO_LIVE_ACCOUNT.json")
    assert lf.declared_ids(tmp_path, {}) == frozenset({_FUSION, _FTMO})


def test_an_absent_file_declares_nothing(tmp_path: Path) -> None:
    assert lf.declared(tmp_path, {}) == (frozenset(), ())
    _write(tmp_path, FTMO_REL, {"login": int(_FTMO)})       # Fusion's file stays absent
    assert lf.declared(tmp_path, {}) == (frozenset({_FTMO}), ("FTMO_LIVE_ACCOUNT.json",))


@pytest.mark.parametrize("login", [float(_FUSION), f"0{_FUSION}", f"  000{_FUSION} "],
                         ids=["integral-float", "leading-zero", "leading-zeros-padded"])
def test_a_login_declares_the_form_the_publisher_compares(tmp_path: Path, login: Any) -> None:
    # cross_account.norm_login / ftmo_follower._canon: 70010042.0 and "070010042" are the
    # terminal's int login 70010042. An integral float must not stop publication (rc 2).
    _write(tmp_path, FTMO_REL, {"login": login, "server": "FTMO-Server"})
    assert lf.declared(tmp_path, {}) == (frozenset({_FUSION}), ("FTMO_LIVE_ACCOUNT.json",))


def test_a_leading_zero_is_checked_after_normalising(tmp_path: Path) -> None:
    # "0700100" passed the 4-12 check before and declared "700100": that is what norm_login
    # makes of it, and 6 digits, so it stands. "0000" -> "0" and "0123" -> "123" do not.
    _write(tmp_path, FUSION_REL, {"login": "0700100"})
    assert lf.declared(tmp_path, {})[0] == frozenset({"700100"})
    for bad in ("0000", "0123", 0.0):
        _write(tmp_path, FUSION_REL, {"login": bad})
        with pytest.raises(lf.FenceConfigError, match=r"leading zeros|4-12"):
            lf.declared(tmp_path, {})


def test_the_e8_declaration_is_not_a_login_source(tmp_path: Path) -> None:
    # cross_account.expected_key reads E8_ACCOUNT.json as {"account_key": hash}: no login.
    _write(tmp_path, "desks/mt5/data/E8_ACCOUNT.json", "{torn")
    assert lf.declared(tmp_path, {}) == (frozenset(), ())


@pytest.mark.parametrize("doc", [
    "{", "", "[]", json.dumps([_FUSION]), {"server": "S"}, {"login": None}, {"login": ""},
    {"login": True}, {"login": float(_FUSION) + 0.5}, '{"login": NaN}', '{"login": Infinity}',
    '{"login": -Infinity}', {"login": 1e300}, {"login": "123"}, {"login": "1234567890123"},
    {"login": f"{_FUSION}x"}, {"login": _folded(0x0660)},
    {"login": _folded(0xFF10)}, {"login": -int(_FUSION)},
    {"login": {"n": _FUSION}}, {"login": "0000"}, {"login": "0123"}, {"login": "00000000"},
    {"login": 0.0},
], ids=["torn", "empty", "list", "list-of-login", "no-login", "null", "blank", "bool",
        "non-integral-float", "nan", "inf", "-inf", "huge-float", "short", "long", "word",
        "arabic-indic", "fullwidth", "negative", "object", "zeros", "zero-led-short",
        "eight-zeros", "zero-float"])
@pytest.mark.parametrize("rel", [FUSION_REL, FTMO_REL], ids=["fusion", "ftmo"])
def test_a_malformed_file_or_a_bad_login_is_a_config_error(
        tmp_path: Path, rel: str, doc: Any) -> None:
    _write(tmp_path, rel, doc)
    with pytest.raises(lf.FenceConfigError) as exc:
        lf.declared(tmp_path, {})
    assert Path(rel).name in str(exc.value)
    assert _FUSION not in str(exc.value) and "7001004" not in str(exc.value)


def _git(repo: Path, *args: str, data: bytes | None = None) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True,
                          check=True, timeout=60).stdout.decode().strip()


def _run_main(repo: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, bytes]
              ) -> tuple[int, dict[str, Any], str, str]:
    rows = [f"{_git(repo, 'hash-object', '-w', '--stdin', data=b)}\t{rel}"
            for rel, b in files.items()]
    monkeypatch.setattr(lf, "record_alert", lambda doc, root=None: "OPEN")
    monkeypatch.setattr(lf, "page", lambda doc, root=None: {"sent": False})
    monkeypatch.delenv(lf.ID_ENV, raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(rows) + "\n"))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    art = repo / "LOGIN_FENCE.json"
    rc = lf.main(["--repo", str(repo), "--artifact", str(art)])
    return rc, (json.loads(art.read_text("utf-8")) if art.exists() else {}), \
        out.getvalue(), err.getvalue()


def test_the_published_report_names_the_sources_and_never_the_values(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git(tmp_path, "init", "-q")
    _write(tmp_path, FUSION_REL, {"login": int(_FUSION), "server": "FusionMarkets-Live"})
    _write(tmp_path, FTMO_REL, {"login": _FTMO, "server": "FTMO-Server"})
    rc, doc, out, err = _run_main(tmp_path, monkeypatch, {
        "desks/mt5/reports/leak.txt": f"refused for x{_FUSION}.".encode(),
        "desks/mt5/reports/clean.json": b'{"n": 3}'})
    assert rc == 0
    assert doc["status"] == "REFUSED" and doc["declared_ids"] == "MEASURED"
    assert doc["n_declared_ids"] == 2
    assert doc["declared_sources"] == ["FTMO_LIVE_ACCOUNT.json", "FUSION_LIVE_ACCOUNT.json"]
    assert list(doc["refused"]) == ["desks/mt5/reports/leak.txt"]
    blob = json.dumps(doc) + out + err
    assert _FUSION not in blob and _FTMO not in blob, "a declared login reached the report"


def test_a_clean_pass_is_measured_once_an_account_file_declares(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git(tmp_path, "init", "-q")
    rc, doc, _, _ = _run_main(tmp_path, monkeypatch, {"a.json": b"{}"})
    assert rc == 0 and doc["status"] == "UNMEASURED" and doc["declared_sources"] == []
    _write(tmp_path, FUSION_REL, {"login": int(_FUSION), "server": "FusionMarkets-Live"})
    rc, doc, _, _ = _run_main(tmp_path, monkeypatch, {"a.json": b"{}"})
    assert rc == 0 and doc["status"] == "OK"
    assert doc["declared_sources"] == ["FUSION_LIVE_ACCOUNT.json"]


def test_a_bad_account_file_fails_the_publish_closed_without_the_value(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git(tmp_path, "init", "-q")
    _write(tmp_path, FTMO_REL, {"login": f"{_FTMO}-x"})
    rc, doc, out, err = _run_main(tmp_path, monkeypatch, {"a.json": b"{}"})
    assert rc == 2 and doc == {} and out == ""
    assert "FTMO_LIVE_ACCOUNT.json" in err and _FTMO not in err


def test_a_config_error_pages_deduped_and_without_the_value(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # rc 2 writes nothing and the publisher discards stderr: without a page a typo in an account
    # file stops all box state publication in silence. It pages through page()/send_all, deduped
    # by login_fence_alert.json like every other fence page, and the text carries no value.
    _git(tmp_path, "init", "-q")
    _write(tmp_path, FTMO_REL, {"login": f"{_FTMO}-x"})
    sent: list[tuple[str, str]] = []

    def sender(title: str, body: str) -> dict[str, Any]:
        sent.append((title, body))
        return {"armed": 1, "delivered": 1}

    monkeypatch.setattr(lf, "_default_sender", lambda root: sender)
    monkeypatch.delenv(lf.ID_ENV, raising=False)
    art = tmp_path / "LOGIN_FENCE.json"
    for _ in range(2):
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        assert lf.main(["--repo", str(tmp_path), "--artifact", str(art)]) == 2
    assert not art.exists()
    assert len(sent) == 1, "the rc-2 page was not deduplicated"
    title, body = sent[0]
    assert "config error" in title and "NO box state is published" in body
    state = (tmp_path / lf.PAGE_STATE_REL).read_text("utf-8")
    assert json.loads(state)["status"] == lf.CONFIG_ERROR
    assert all(_FTMO not in t for t in (title, body, state)), "a login reached the page"

    # Fixed: the next judged pass pages the recovery once (the existing idiom).
    _write(tmp_path, FTMO_REL, {"login": _FTMO})
    monkeypatch.setattr(lf, "record_alert", lambda doc, root=None: None)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert lf.main(["--repo", str(tmp_path), "--artifact", str(art)]) == 0
    assert [t for t, _ in sent[1:]] == ["LOGIN FENCE OK again"]


def test_a_config_error_page_that_raises_still_exits_2(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, FTMO_REL, {"login": f"{_FTMO}-x"})

    def boom(doc: dict[str, Any], root: object = None) -> dict[str, Any]:
        raise OSError("pager down")

    monkeypatch.setattr(lf, "page", boom)
    monkeypatch.delenv(lf.ID_ENV, raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    err = io.StringIO()
    monkeypatch.setattr("sys.stderr", err)
    assert lf.main(["--repo", str(tmp_path)]) == 2
    assert "page failed (OSError)" in err.getvalue() and _FTMO not in err.getvalue()
