"""The standing same-day veto window (zuck 2026-11-20, D-20261120-SAMEDAYVETO): a TRUST change with
the Auditor's CLEAR at its exact head is authorized by the pin writer once VETO_HOURS pass with no
owner veto; never for the signers, never without the CLEAR, never against an owner VETO."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import pin_writer as P  # noqa: E402
from ops.box_git import trust_check as T  # noqa: E402

POLICY = {"files": ["ops/signing/*", "ops/release/ceilings.json"], "grow_only": [],
          "symbols": {}}
T0 = datetime(2026, 11, 20, 12, tzinfo=UTC)


def _world(tmp: Path):
    repo = tmp / "r"
    repo.mkdir()

    def g(*a: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True,
                              text=True, encoding="utf-8").stdout.strip()
    g("init", "-q", "-b", P.LIVE)
    g("config", "user.email", "t@x")
    g("config", "user.name", "t")
    for rel, text in {"ops/signing/allowed_signers": "zuck key\n",
                      "ops/release/ceilings.json": '{"daily": 0.02}\n',
                      T.POLICY_PATH: json.dumps(POLICY)}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    g("add", "-A")
    g("commit", "-q", "-m", "base")
    base = g("rev-parse", "HEAD")
    heads = {}
    for name, rel, text in (("ceil", "ops/release/ceilings.json", '{"daily": 0.03}\n'),
                            ("keys", "ops/signing/allowed_signers", "evil\n")):
        g("checkout", "-q", "-b", name, base)
        (repo / rel).write_text(text)
        g("commit", "-q", "-am", name)
        heads[name] = g("rev-parse", "HEAD")
    g("checkout", "-q", P.LIVE)
    folder = tmp / "trust"
    folder.mkdir()
    shutil.copy(ROOT / "ops/box_git/trust_check.py", folder / "trust_check.py")
    (folder / "TRUST_SET.json").write_text(json.dumps(POLICY))
    pin = {"t_hash": T.t_hash(T.strict_git("git", "-C", str(repo)), base, POLICY),
           "live": base, "history": [], "files": {}}
    (folder / "pin.json").write_text(json.dumps(pin))
    return repo, folder, base, heads


def _forge(head: str, comments: list[dict]):
    def get(path: str):
        if "/pulls" in path:
            return [{"number": 3, "head": {"sha": head}, "base": {"ref": P.LIVE}}]
        page = int(path.rsplit("page=", 1)[1]) if "page=" in path else 1
        return comments[(page - 1) * P.PAGE: page * P.PAGE]
    return get


def _pass(repo: Path, folder: Path, forge, now: datetime) -> list[str]:
    return P.one_pass({"bare": str(repo)}, folder, forge=forge, now=now)


def _clear(head: str) -> dict:
    return {"user": {"login": "auditor"}, "body": f"AUDIT CLEAR {head} merge"}


def test_a_cleared_trust_change_is_authorized_after_the_window(tmp_path: Path) -> None:
    repo, folder, _base, heads = _world(tmp_path)
    h = heads["ceil"]
    forge = _forge(h, [_clear(h)])
    assert any("h left" in r for r in _pass(repo, folder, forge, T0))
    assert not (json.loads((folder / "pin.json").read_text()).get("authorized"))
    assert any("h left" in r for r in _pass(repo, folder, forge, T0 + timedelta(hours=3)))
    rows = _pass(repo, folder, forge, T0 + timedelta(hours=P.VETO_HOURS, minutes=1))
    assert any("standing veto window" in r for r in rows), rows
    pin = json.loads((folder / "pin.json").read_text())
    assert any(v["head"] == h for v in pin["authorized"].values())


def test_no_clear_an_owner_veto_or_the_signers_never_pass_by_window(tmp_path: Path) -> None:
    repo, folder, _base, heads = _world(tmp_path)
    later = T0 + timedelta(hours=P.VETO_HOURS * 10)
    h = heads["ceil"]
    filler = [{"user": {"login": "claude"}, "body": "note"}] * 50
    hold = {"user": {"login": "auditor"}, "body": f"AUDIT HOLD {h}"}
    edited = {**_clear(h), "created_at": "a", "updated_at": "b"}
    for comments in ([], [_clear(h), {"user": {"login": "claude"}, "body": f"VETO TRUST {h}"}],
                     [{"user": {"login": "claude"}, "body": f"AUDIT CLEAR {h} merge"}],
                     [_clear(h), hold], [edited], [_clear(h), *filler, hold],
                     [_clear(h), *filler, {"user": {"login": "x"}, "body": f"VETO TRUST {h}"}]):
        _pass(repo, folder, _forge(h, comments), T0)
        _pass(repo, folder, _forge(h, comments), later)
    k = heads["keys"]
    _pass(repo, folder, _forge(k, [_clear(k)]), T0)
    _pass(repo, folder, _forge(k, [_clear(k)]), later)
    assert not json.loads((folder / "pin.json").read_text()).get("authorized")


def test_the_inbox_carries_a_veto_line() -> None:
    from ops.box_git import inbox as I
    m, _why = I.parse_manifest({"branch": "claude/x", "head": "a" * 40,
                                "comments": ["VETO TRUST " + "b" * 40]})
    assert m is not None and m.comments == ("VETO TRUST " + "b" * 40,)
