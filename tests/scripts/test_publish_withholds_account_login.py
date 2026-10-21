"""THE PUBLISHER WITHHOLDS THE LOGIN, AND REFUSES WHAT IT CANNOT WITHHOLD (v5g, 2026-10-21).

Measured 2026-10-21: origin's `desks/mt5/data/cost_truth_quotes.json` (af09b4e1, a box-state
commit) still carried `account.login` -- the live account number -- although its writer
(desks/mt5/research/cost_truth.py) had withheld it for weeks. The file is rewritten only when the
terminal read succeeds, so the old copy sat on the box's disk and every sync re-offered it; the
v5f fence would then refuse it forever, which keeps origin's leaky copy in place. So the
publisher now applies the writer's own rule (libs/ops/account_withhold.py) to the blob BEFORE the
fence judges it, and the fence still blocks any other file that names a declared login.

pwsh is absent off the box, so the wiring is pinned by source and the behaviour by running the
same two Python steps the publisher runs, in the same order, on real git blobs. Every number here
is synthetic; the one test that reads the real tree prints and asserts COUNTS only.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from libs.ops import account_withhold as aw
from libs.ops import login_fence as lf

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "desks" / "mt5" / "scripts" / "sync_shadow_to_git.ps1"
QUOTES = "desks/mt5/data/cost_truth_quotes.json"
FAKE = "5551234"              # synthetic, never a real login
FAKE_IDS = frozenset({FAKE})


def _allowlist() -> list[str]:
    """Every path the sync offers to Publish-StateOnto: `$relPaths` and `$reportPaths`."""
    src = SYNC.read_text("utf-8", errors="ignore")
    out: list[str] = []
    for name in ("$relPaths = @(", "$reportPaths = @("):
        start = src.index(name)
        block = src[start:src.index("\n)", start)]
        code = "\n".join(ln.split("#", 1)[0] for ln in block.splitlines())
        out += [p for p in re.findall(r'"([^"]+)"', code) if "/" in p]
    return out


def _git(repo: Path, *args: str, data: bytes | None = None) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True,
                          check=True).stdout.decode().strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _publish(repo: Path, files: dict[str, bytes], monkeypatch: pytest.MonkeyPatch,
             capsys: pytest.CaptureFixture[str]) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Publish-StateOnto's two Python steps, in its order: hash, scrub, fence, drop refused.
    Returns (rel -> the bytes that WOULD be staged, the LOGIN_FENCE artifact)."""
    rows = [f"{_git(repo, 'hash-object', '-w', '--stdin', data=b)}\t{rel}"
            for rel, b in files.items()]
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(rows) + "\n"))
    assert aw.main(["--repo", str(repo)]) == 0
    scrubbed = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert [r.split("\t")[1] for r in scrubbed] == list(files), "the scrub reorders nothing"
    monkeypatch.setattr(lf, "record_alert", lambda doc, root=None: "OPEN")
    monkeypatch.setattr(lf, "page", lambda doc, root=None: {})
    monkeypatch.setattr(lf, "declared_ids", lambda root, env=None: FAKE_IDS)
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(scrubbed) + "\n"))
    art = repo / "LOGIN_FENCE.json"
    assert lf.main(["--repo", str(repo), "--artifact", str(art)]) == 0
    refused = set(capsys.readouterr().out.split())
    staged = {}
    for row in scrubbed:
        blob, rel = row.split("\t")
        if rel not in refused:
            staged[rel] = subprocess.run(["git", "-C", str(repo), "cat-file", "blob", blob],
                                         capture_output=True, check=True).stdout
    return staged, json.loads(art.read_text("utf-8"))


def _quotes(account: dict[str, Any]) -> bytes:
    doc = {"at": "2026-09-23T00:00:00+00:00", "account": account,
           "terminal": {"name": "t", "connected": True, "build": 1},
           "server_utc_offset_hours": 3, "rollover_hour_utc": 21,
           "symbols": {"XAUUSD": {"spread_pts": 12.0}}, "deals": []}
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


_LEAKY = {"company": "Fusion Markets Pty Ltd", "currency": "USD", "leverage": 500,
          "login": int(FAKE), "margin_mode": 2, "server": "FusionMarkets-Live"}


# ------------------------------------------------------------------- (1) published scrubbed


def test_a_login_bearing_quotes_file_is_published_scrubbed(
        repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    staged, art = _publish(repo, {QUOTES: _quotes(_LEAKY)}, monkeypatch, capsys)
    assert QUOTES in staged, "the scrubbed quotes file must publish, not be refused"
    assert FAKE.encode() not in staged[QUOTES]
    acct = json.loads(staged[QUOTES])["account"]
    assert "login" not in acct and acct["login_withheld"] is True
    assert {k: acct[k] for k in ("company", "currency", "leverage", "margin_mode", "server")} \
        == {k: _LEAKY[k] for k in ("company", "currency", "leverage", "margin_mode", "server")}
    assert art["status"] == "OK" and art["refused"] == {}
    assert FAKE not in json.dumps(art)


def test_the_scrub_is_the_writers_own_bytes() -> None:
    """A scrubbed old copy is byte-identical to what cost_truth.py writes today for the same
    account, and a file already in that form is left alone (its blob does not change)."""
    new, dropped = aw.scrub_for_publish(QUOTES, _quotes(_LEAKY))
    assert dropped == ["account.login"]
    writer = aw.account_block(type("Acct", (), _LEAKY)())
    assert new == _quotes(writer)
    assert aw.scrub_for_publish(QUOTES, _quotes(writer)) == (None, [])
    assert aw.scrub_for_publish("desks/mt5/data/other.json", _quotes(_LEAKY)) == (None, [])


def test_the_writer_and_the_publisher_share_one_rule() -> None:
    src = (ROOT / "desks" / "mt5" / "research" / "cost_truth.py").read_text("utf-8")
    assert "from libs.ops.account_withhold import account_block" in src
    assert 'out["account"] = account_block(acct)' in src
    block = aw.account_block(type("Acct", (), {"login": None, "server": "S"})())
    assert block["login_withheld"] is False and "login" not in block


@pytest.mark.parametrize("account", [
    {"login": int(FAKE)}, {"login": FAKE}, {"Login": int(FAKE)}, {"login_id": int(FAKE)},
    {"mt5_login": FAKE, "login_withheld": False},
])
def test_every_login_shaped_key_in_the_account_block_is_withheld(account: dict[str, Any]) -> None:
    new, dropped = aw.scrub_for_publish(QUOTES, _quotes({**account, "server": "S"}))
    assert new is not None and dropped and FAKE.encode() not in new
    acct = json.loads(new)["account"]
    assert acct["login_withheld"] is True and acct["server"] == "S"


@pytest.mark.parametrize("data", [b"not json", b'{"account": "Fusion Zero"}', b"[1, 2]",
                                  b'{"account": {"login_withheld": true}}'])
def test_what_the_scrub_cannot_or_need_not_change_passes_through(data: bytes) -> None:
    assert aw.scrub_for_publish(QUOTES, data) == (None, [])


def test_an_unscrubbable_quotes_file_is_still_refused_by_the_fence(
        repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # The login sits where the scrub does not look (the deals list): the fence must catch it.
    doc = json.loads(_quotes({"login_withheld": True, "server": "S"}))
    doc["deals"] = [{"ticket": 1, "comment": f"acct {FAKE}"}]
    bad = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    staged, art = _publish(repo, {QUOTES: bad, "desks/mt5/data/b.json": b'{"ok": 1}'},
                           monkeypatch, capsys)
    assert QUOTES not in staged and "desks/mt5/data/b.json" in staged
    assert QUOTES in art["refused"] and FAKE not in json.dumps(art)


# --------------------------------------------- (2) a declared login blocks ANY allowlisted file


def _allowlisted_text_paths() -> list[str]:
    return [p for p in _allowlist() if Path(p).suffix.lower() not in lf.BINARY_EXEMPT]


def test_the_allowlist_is_read() -> None:
    paths = _allowlist()
    assert QUOTES in paths and "desks/mt5/data/sleeves.json" in paths and len(paths) >= 10


@pytest.mark.parametrize("rel", _allowlisted_text_paths())
def test_a_declared_login_in_any_allowlisted_file_blocks_that_file(
        rel: str, repo: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Under a key nobody would call a login, so only the declared-number rules can catch it.
    leaky = json.dumps({"symbol_id": "00" + FAKE, "note": "fine"}).encode() + b"\n"
    other = "desks/mt5/reports/ZZ_clean.json"
    staged, art = _publish(repo, {rel: leaky, other: b'{"fine": true}\n'}, monkeypatch, capsys)
    assert rel not in staged, f"{rel} carried a declared login and was staged anyway"
    assert other in staged, "one refusal must not stop the clean files"
    assert art["status"] == "REFUSED" and rel in art["refused"]
    keys = {str(h["key"]) for h in art["refused"][rel]}
    assert keys, "the refusal row must name the key"
    assert FAKE not in json.dumps(art), "the refusal row must never carry the value"


def test_the_ps1_scrubs_then_fences_then_drops_refused_and_fails_closed() -> None:
    src = SYNC.read_text("utf-8")
    fn = src[src.index("function Publish-StateOnto"):src.index("$entries = for")]
    scrub, fence = fn.index("libs\\ops\\account_withhold.py"), fn.index("libs\\ops\\login_fence.py")
    assert scrub < fence, "the fence must judge the SCRUBBED blob"
    assert "$scrubRc -ne 0 -or $scrubbed.Count -ne $Paths.Count" in fn
    assert "$blobs[$i] = $blob" in fn
    assert "if ($fenceRc -ne 0)" in fn and "if ($refused -contains $Paths[$i]) { continue }" in fn
    # nothing staged comes from anywhere but the post-fence $Paths / $blobs
    entries = src[src.index("$entries = for"):src.index("$idx = Join-Path")]
    assert "$blobs[$i]" in entries and "$Paths[$i]" in entries


# --------------------------------------------- (3) the real tree's copy is detected, count-only


def _ledger_logins() -> frozenset[str]:
    """The logins the repo's own ledgers already carry (their sealed legacy prefixes)."""
    out: set[str] = set()
    for rel in lf.LEGACY_PIN:
        held = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{rel}"],
                              capture_output=True, check=False).stdout
        for ln in held.splitlines():
            try:
                row = json.loads(ln)
            except ValueError:
                continue
            acct = row.get("account") if isinstance(row, dict) else None
            if isinstance(acct, (int, str)) and str(acct).isdigit() and 4 <= len(str(acct)) <= 12:
                out.add(str(int(acct)))
    return frozenset(out)


def test_the_tracked_quotes_copy_is_detected_and_the_scrub_clears_it() -> None:
    """COUNT-ONLY: no value is printed, compared in an assertion message, or returned."""
    held = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{QUOTES}"],
                          capture_output=True, check=False).stdout
    if not held:
        pytest.skip("no tracked cost_truth_quotes.json in this checkout")
    ids = _ledger_logins()
    if not ids:
        pytest.skip("no ledger login to compare against in this checkout")
    n_before = len(lf.findings(QUOTES, held, ids))
    acct = json.loads(held).get("account") or {}
    n_login_keys = sum(1 for k in acct if lf.is_login_key(str(k)))
    if n_login_keys == 0:
        assert n_before == 0, "a clean tracked copy must not be refused"
        return
    assert n_before > 0, "the fence must detect the login-bearing tracked copy"
    new, dropped = aw.scrub_for_publish(QUOTES, held)
    assert new is not None and len(dropped) == n_login_keys
    n_after = len(lf.findings(QUOTES, new, ids))
    assert n_after == 0, f"the scrubbed copy still has {n_after} finding(s)"
