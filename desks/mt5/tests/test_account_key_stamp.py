"""The ledgers stamp a KEYED account hash, and every account decision is unchanged by it.

2026-10-20 (audits v3-v5 of publish_sync_schtasks): `live_ledger.jsonl` and `order_intents.jsonl`
are tracked and published from the box, and on LIVE they carried the live login 257 and 44 times
under `account`. Their writers now stamp `account_key` = "sha256:" + HMAC-SHA256(box key,
"<login>@<server>")[:16] from `libs.ops.provenance.account_key` -- the r5 FORMAT, but keyed (v5:
a bare sha256 of login@server with the server in clear is invertible in a minute). No box key:
the function returns None and never a bare hash. Legacy rows keep the original raw comparison.

THE MONEY PATH IS PINNED HERE, not asserted in prose. `same_account` decides which ledger rows
are evidence for the account in hand: the promoter's retirements and admissions, the gold
retirement re-derivation, and `independence.measure_from_ledger` (k_eff -> the heat budget ->
size). So the old comparison is restated below as the reference and the new one must agree with
it on every (row, account) pair, for legacy rows and for rows the new writer stamps.
"""
from __future__ import annotations

import hashlib
import hmac
import inspect
import itertools
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import provenance  # noqa: E402
from mt5desk.provenance import DEMO, LIVE, UNKNOWN  # noqa: E402

from libs.ops import provenance as libs_provenance  # noqa: E402

_GW = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")


def _old_same_account(row: dict, acc: dict) -> bool:
    """`provenance.same_account` as it was before the hashed stamp (2026-10-20), verbatim."""
    login, server, kind = (row.get("account"), row.get("server"),
                           row.get("account_kind", UNKNOWN))
    if kind == UNKNOWN or login is None:
        return False
    return (login == acc.get("login") and server == acc.get("server")
            and kind == acc.get("kind"))


_LOGINS = (5551234, 9990001, 1)
_SERVERS = ("FusionMarkets-Live", "FusionMarkets-Demo")
_KINDS = (LIVE, DEMO, UNKNOWN)
_ACCS = [{"login": lg, "server": sv, "kind": k}
         for lg, sv, k in itertools.product(_LOGINS, _SERVERS, _KINDS)]
_ACCS += [{"login": None, "server": None, "kind": UNKNOWN}]
_LEGACY = [{"account": lg, "server": sv, "account_kind": k, "sleeve": "gold_asia"}
           for lg, sv, k in itertools.product((*_LOGINS, None), _SERVERS, _KINDS)]
_LEGACY += [{"sleeve": "x"}]


def test_the_key_is_a_keyed_hmac_in_r5_s_format(_account_key_file: Path) -> None:
    """"sha256:" + HMAC-SHA256(box key, "<login>@<server>")[:16] -- never the bare sha256."""
    key = _account_key_file.read_bytes().strip()
    msg = b"5551234@FusionMarkets-Live"
    want = "sha256:" + hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]
    got = provenance.account_key(5551234, "FusionMarkets-Live")
    assert got == want and provenance.is_key(got)
    assert got != "sha256:" + hashlib.sha256(msg).hexdigest()[:16], "the invertible v4 key"
    assert provenance.account_key is libs_provenance.account_key, "one helper, not two"
    assert provenance.account_key(5551234.0, "S") == provenance.account_key(5551234, "S")
    # v5c: a digit string is the same account as the int (norm_login); "" stays distinct from None
    assert provenance.account_key("5551234", "S") == provenance.account_key(5551234, "S")
    assert provenance.account_key(1, "") != provenance.account_key(1, None)
    for bad in ((None, "S"), ("", "S"), (True, "S")):
        assert provenance.account_key(*bad) is None


def test_the_helper_s_signature_is_stable() -> None:
    sig = inspect.signature(libs_provenance.account_key)
    assert str(sig) == ("(login: 'object', server: 'object', *, create: 'bool' = False)"
                        " -> 'str | None'")


def test_no_box_key_is_the_none_sentinel_never_a_bare_hash(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "secrets" / "account_key.hmac"
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(missing))
    assert provenance.account_key(5551234, "S") is None
    assert not missing.exists(), "a READER created the box key"
    row = {"account_key": None, "server": "S", "account_kind": LIVE}
    assert provenance.same_account(row, {"login": 5551234, "server": "S", "kind": LIVE}) is False
    # a short key file is unusable and is never overwritten
    missing.parent.mkdir(parents=True)
    missing.write_bytes(b"short")
    assert provenance.account_key(1, "S", create=True) is None
    assert missing.read_bytes() == b"short"


def test_the_writer_creates_the_key_once_and_never_prints_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "secrets" / "account_key.hmac"
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))
    a = provenance.account_key(7, "S", create=True)
    assert path.exists() and len(path.read_bytes().strip()) >= 32
    body = path.read_bytes()
    assert provenance.account_key(7, "S", create=True) == a == provenance.account_key(7, "S")
    assert path.read_bytes() == body
    out = capsys.readouterr()
    assert body.decode() not in out.out + out.err


def test_the_box_key_is_gitignored() -> None:
    import subprocess
    root = _DESK.parents[1]
    rc = subprocess.run(["git", "check-ignore", "-q", libs_provenance.KEY_REL], cwd=root,
                        check=False).returncode
    assert rc == 0, "data/secrets/account_key.hmac would be committed"


@pytest.mark.parametrize("acc", _ACCS, ids=lambda a: f"{a['login']}@{a['server']}/{a['kind']}")
def test_same_account_is_unchanged_on_legacy_rows(acc: dict) -> None:
    for row in _LEGACY:
        assert provenance.same_account(row, acc) is _old_same_account(row, acc), (row, acc)


@pytest.mark.parametrize("acc", _ACCS, ids=lambda a: f"{a['login']}@{a['server']}/{a['kind']}")
def test_a_row_the_new_writer_stamps_matches_exactly_where_the_old_stamp_did(acc: dict) -> None:
    for writer_acc in _ACCS:
        old_row = {"account": writer_acc["login"], "server": writer_acc["server"],
                   "account_kind": writer_acc["kind"]}
        new_row = provenance.stamp(writer_acc)
        assert "account" not in new_row, "the writer still stamps the raw login"
        assert provenance.same_account(new_row, acc) is _old_same_account(old_row, acc), (
            writer_acc, acc)


def test_a_ledger_of_both_shapes_is_one_account_to_every_grouping_reader() -> None:
    acc = {"login": 5551234, "server": "FusionMarkets-Live", "kind": LIVE}
    legacy = {"account": 5551234, "server": "FusionMarkets-Live", "account_kind": LIVE}
    groups = provenance.split_by_account([legacy, provenance.stamp(acc)])
    assert len(groups) == 1, "markout would read a one-account ledger as MIXED"
    assert provenance.row_key(legacy) == provenance.row_key(provenance.stamp(acc))


def test_k_eff_and_the_promoter_admission_are_identical_across_the_cutover() -> None:
    """independence.measure_from_ledger sizes the heat budget from the rows same_account keeps;
    the same rows stamped either way must give the same k_eff, word for word."""
    from mt5desk import independence
    acc = {"login": 5551234, "server": "FusionMarkets-Live", "kind": LIVE}
    other = {"login": 9990001, "server": "FusionMarkets-Demo", "kind": DEMO}
    base = []
    for day in range(1, 29):
        for i, sleeve in enumerate(("a", "b", "c")):
            base.append({"time": f"2026-09-{day:02d}T1{i}:00:00+00:00", "sleeve": sleeve,
                         "r_multiple": ((day * (i + 2)) % 7 - 3) / 3.0})
    def as_old(row: dict, a: dict) -> dict:
        return {**row, "account": a["login"], "server": a["server"], "account_kind": a["kind"]}
    def as_new(row: dict, a: dict) -> dict:
        return {**row, **provenance.stamp(a)}
    old = [as_old(r, acc if n % 4 else other) for n, r in enumerate(base)]
    new = [as_new(r, acc if n % 4 else other) for n, r in enumerate(base)]
    mixed = [o if n % 2 else w for n, (o, w) in enumerate(zip(old, new, strict=True))]
    want = independence.measure_from_ledger(old, acc)
    assert independence.measure_from_ledger(new, acc) == want
    assert independence.measure_from_ledger(mixed, acc) == want
    keep = [provenance.same_account(r, acc) for r in old]
    assert [provenance.same_account(r, acc) for r in new] == keep
    assert [provenance.same_account(r, acc) for r in mixed] == keep


def test_the_gateway_writes_the_key_and_never_the_raw_login() -> None:
    """Both tracked writers. The ledger row is `provenance.stamp` (pinned above). The intent
    key is set inside `_record_intent`, the append-only recorder whose only output is the row
    it writes and its intent_id -- so the change cannot reach what is sent, sized or refused."""
    assert "_prov.stamp(_prov.current_account(mt5.account_info()))" in _GW
    assert 'row.setdefault("account", ' not in _GW, "an intent row stamps the raw login again"
    body = _GW[_GW.index("def _record_intent"):]
    body = body[:body.index("\ndef ")]
    assert 'row.setdefault("account_key", _akey(' in body
    assert "create=True" in body, "the intent writer must be able to create the box key"
    code = "\n".join(ln.split("#", 1)[0] for ln in body.splitlines())
    assert "order_send(" not in code and "order_check(" not in code
    # its return value is the intent id, a hash of symbol|sleeve|side|minute: no account in it
    iid = _GW[_GW.index("def _intent_id"):]
    iid = iid[:iid.index("\ndef ")]
    assert "account" not in "\n".join(ln.split("#", 1)[0] for ln in iid.splitlines())


@pytest.mark.parametrize("writer,reader", [
    ({"login": 5551234.0, "server": "S", "kind": LIVE},
     {"login": 5551234, "server": "S", "kind": LIVE}),
    ({"login": 5551234, "server": "S", "kind": LIVE},
     {"login": 5551234.0, "server": "S", "kind": LIVE}),
    ({"login": 5551234, "server": "", "kind": LIVE},
     {"login": 5551234, "server": "", "kind": LIVE}),
    ({"login": 5551234, "server": "", "kind": LIVE},
     {"login": 5551234, "server": None, "kind": LIVE}),
], ids=["N.0-writer", "N.0-reader", "empty-server", "empty-vs-none"])
def test_the_n_point_0_and_empty_server_edges_decide_as_the_raw_comparison_did(
        writer: dict, reader: dict) -> None:
    old_row = {"account": writer["login"], "server": writer["server"],
               "account_kind": writer["kind"]}
    assert provenance.same_account(provenance.stamp(writer), reader) is \
        _old_same_account(old_row, reader)


# v5b (2026-10-21): the key is written temp-file -> fsync -> hard link, a 0-byte or short key is
# NO key, and with no key the writer fails closed -- never the raw login, never a bare sha256.
@pytest.mark.parametrize("body", [b"", b"   \n", b"x" * 31], ids=["empty", "blank", "short"])
def test_a_zero_byte_or_short_key_is_no_key_and_the_stamp_fails_closed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    path = tmp_path / "secrets" / "account_key.hmac"
    path.parent.mkdir(parents=True)
    path.write_bytes(body)
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))
    assert libs_provenance._box_key() is None
    assert libs_provenance._box_key(create=True) is None
    assert path.read_bytes() == body, "a short key was overwritten (orphans its rows)"
    acc = {"login": 5551234, "server": "FusionMarkets-Live", "kind": LIVE}
    row = provenance.stamp(acc)
    assert row["account_key"] is None and row["account_withheld"] is True
    assert "account" not in row, "the writer stamped the raw login with no key"
    assert "5551234" not in repr(row)
    msg = b"5551234@FusionMarkets-Live"
    assert ("sha256:" + hashlib.sha256(msg).hexdigest()[:16]) not in repr(row)
    assert provenance.same_account(row, acc) is False


def test_the_key_is_written_to_a_temp_file_fsynced_and_linked_into_place(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    path = tmp_path / "secrets" / "account_key.hmac"
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))
    synced: list[int] = []
    linked: list[tuple[str, str]] = []
    real_fsync, real_link = os.fsync, os.link

    def fsync(fd: int) -> None:
        synced.append(fd)
        real_fsync(fd)

    def link(src: str, dst: str) -> None:
        assert Path(src).parent == path.parent, "the temp file must sit beside the key"
        assert len(Path(src).read_bytes().strip()) >= 32, "linked before the bytes were written"
        linked.append((str(src), str(dst)))
        real_link(src, dst)

    monkeypatch.setattr(libs_provenance.os, "fsync", fsync)
    monkeypatch.setattr(libs_provenance.os, "link", link)
    assert provenance.account_key(7, "S", create=True) is not None
    assert synced and linked and linked[0][1] == str(path)
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name], "a temp file was left"


def test_without_hard_links_the_key_is_still_created_once(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "secrets" / "account_key.hmac"
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))

    def no_link(src: str, dst: str) -> None:
        raise OSError("hard links not supported")

    monkeypatch.setattr(libs_provenance.os, "link", no_link)
    a = provenance.account_key(7, "S", create=True)
    assert a is not None and len(path.read_bytes().strip()) >= 32
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name]


def test_an_existing_read_only_key_is_never_replaced(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """os.replace onto a read-only file raises WinError 5 on the box; an existing key -- read-only
    or not, usable or not -- is never a replace target."""
    import os
    import stat
    path = tmp_path / "secrets" / "account_key.hmac"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"k" * 40)
    os.chmod(path, stat.S_IREAD)
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))
    replaced: list[str] = []
    monkeypatch.setattr(libs_provenance.os, "replace",
                        lambda a, b: replaced.append(str(b)))
    try:
        a = provenance.account_key(7, "S", create=True)
        libs_provenance._create_key(path)        # a racing writer finds a key: no-op
        assert a == provenance.account_key(7, "S")
        assert path.read_bytes() == b"k" * 40 and replaced == []
        assert sorted(p.name for p in path.parent.iterdir()) == [path.name]
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


def test_a_crash_before_the_link_leaves_no_key_and_no_temp_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "secrets" / "account_key.hmac"
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))

    def crash(fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(libs_provenance.os, "fsync", crash)
    assert provenance.account_key(7, "S", create=True) is None
    assert list(path.parent.iterdir()) == [], "a torn key or temp file was left behind"
    row = provenance.stamp({"login": 7, "server": "S", "kind": LIVE})
    assert "account" not in row and row["account_key"] is None


# v5c (2026-10-21): the key cache is keyed on (inode, size, mtime); the no-hard-link fallback is
# an exclusive create of the key path, never a replace.
def test_a_key_replaced_in_place_is_re_read_even_at_the_same_mtime(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    path = tmp_path / "account_key.hmac"
    path.write_bytes(b"a" * 40)
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))
    first = provenance.account_key(7, "S")
    st = path.stat()
    new = tmp_path / "new.hmac"
    new.write_bytes(b"b" * 40)                       # same size
    os.utime(new, ns=(st.st_atime_ns, st.st_mtime_ns))  # same mtime
    os.replace(new, path)                            # new inode
    assert path.stat().st_mtime_ns == st.st_mtime_ns
    second = provenance.account_key(7, "S")
    assert first is not None and second is not None and first != second, "served a stale key"


def test_without_hard_links_an_existing_key_is_never_replaced(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The race the v5b fallback left open: another writer lands a key between the absent check
    and the replace. v5c has no replace: an exclusive create finds theirs and keeps it."""
    path = tmp_path / "secrets" / "account_key.hmac"
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))
    theirs = b"t" * 64

    def racing_link(src: str, dst: str) -> None:
        Path(dst).write_bytes(theirs)                # the other writer wins, right now
        raise OSError("hard links not supported")

    def no_replace(a: str, b: str) -> None:
        raise AssertionError("os.replace was called on the key path")

    monkeypatch.setattr(libs_provenance.os, "link", racing_link)
    monkeypatch.setattr(libs_provenance.os, "replace", no_replace)
    got = provenance.account_key(7, "S", create=True)
    assert path.read_bytes() == theirs, "an existing key was overwritten"
    want = "sha256:" + hmac.new(theirs, b"7@S", hashlib.sha256).hexdigest()[:16]
    assert got == want
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name]


def test_the_no_hard_link_fallback_creates_exclusively_and_fsyncs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    path = tmp_path / "secrets" / "account_key.hmac"
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(path))
    flags: list[int] = []
    synced: list[int] = []
    real_open, real_fsync = os.open, os.fsync

    def spy_open(p: Any, f: int, *a: Any, **kw: Any) -> int:
        if not kw and Path(p) == path:
            flags.append(f)
        return real_open(p, f, *a, **kw)

    def spy_fsync(fd: int) -> None:
        synced.append(fd)
        real_fsync(fd)

    def no_link(src: str, dst: str) -> None:
        raise OSError("hard links not supported")

    monkeypatch.setattr(libs_provenance.os, "open", spy_open)
    monkeypatch.setattr(libs_provenance.os, "fsync", spy_fsync)
    monkeypatch.setattr(libs_provenance.os, "link", no_link)
    monkeypatch.setattr(libs_provenance.os, "replace",
                        lambda a, b: (_ for _ in ()).throw(AssertionError("replace")))
    assert provenance.account_key(7, "S", create=True) is not None
    assert flags and all(f & os.O_EXCL and f & os.O_CREAT for f in flags)
    assert len(synced) >= 2, "the temp file and the key itself must both be fsynced"
    assert len(path.read_bytes().strip()) >= 32


# v5c (2026-10-21, coordinator): account_key is THE one account-key function and normalises
# internally -- norm_login for the login, .strip() for the server. Fake logins only.
_FORMS = (7000001, "7000001", " 7000001 ", 7000001.0, "\t7000001\n")


@pytest.mark.parametrize("server", ["X", " X ", "X\n"], ids=["clean", "padded", "newline"])
def test_every_form_of_one_login_and_server_is_one_key(server: str) -> None:
    want = libs_provenance.account_key(7000001, "X")
    assert want is not None and provenance.is_key(want)
    for form in _FORMS:
        assert libs_provenance.account_key(form, server) == want, (form, server)
        assert libs_provenance.norm_login(form) == 7000001


def test_a_different_login_or_server_is_a_different_key() -> None:
    base = libs_provenance.account_key(7000001, "X")
    assert libs_provenance.account_key(7000002, "X") != base
    assert libs_provenance.account_key("7000002", " X ") != base
    assert libs_provenance.account_key(7000001, "Y") != base
    assert libs_provenance.account_key(7000001, None) != libs_provenance.account_key(7000001, "")


@pytest.mark.parametrize("garbage", [
    None, True, False, "", "   ", "7000001a", "7,000,001", "7000001.0", "-7000001", "+7000001",
    "\u0667000001", 7000001.5, float("nan"), float("inf"), 0, -7000001, 0.0, b"7000001",
    [7000001], {"login": 7000001}, object(),
], ids=lambda g: type(g).__name__ + ":" + repr(g)[:12])
def test_garbage_logins_fail_closed(garbage: object) -> None:
    assert libs_provenance.norm_login(garbage) is None
    assert libs_provenance.account_key(garbage, "X") is None
    assert libs_provenance.account_key(garbage, "X", create=True) is None


def test_an_int_login_with_a_clean_server_hashes_exactly_as_before(
        _account_key_file: Path) -> None:
    """Rows already stamped from the terminal's int login keep their key across v5c."""
    key = _account_key_file.read_bytes().strip()
    want = "sha256:" + hmac.new(key, b"7000001@X", hashlib.sha256).hexdigest()[:16]
    assert libs_provenance.account_key(7000001, "X") == want


def test_a_string_login_row_now_matches_its_int_account() -> None:
    """THE ONE DECISION v5c CHANGES, on purpose: a writer handed "N" and a reader holding N are
    the same account (the raw comparison said not). The terminal reports logins as ints."""
    writer = {"login": "7000001", "server": "S", "kind": LIVE}
    reader = {"login": 7000001, "server": "S", "kind": LIVE}
    assert provenance.same_account(provenance.stamp(writer), reader) is True



# v5d (2026-10-21, audit hold on v5c): fail-closed is never silent. A short or unreadable key,
# and a username handed in as a login, each open ONE alert per incident in the AlertLedger beside
# the key's secrets directory (a temp ledger here, never the repo's data/alert_ledger.json).
_REPO_LEDGER = Path(__file__).resolve().parents[3] / "data" / "alert_ledger.json"


def _ledger_alerts(path: Path) -> dict[str, Any]:
    import json
    return json.loads(path.read_text("utf-8"))["alerts"] if path.exists() else {}


@pytest.fixture
def _box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    key = tmp_path / "data" / "secrets" / "account_key.hmac"
    key.parent.mkdir(parents=True)
    monkeypatch.setenv(libs_provenance.KEY_ENV, str(key))
    monkeypatch.setattr(libs_provenance, "_ALERTED", set())
    return key, tmp_path / "data" / "alert_ledger.json"


def _repo_ledger_digest() -> str | None:
    return (hashlib.sha256(_REPO_LEDGER.read_bytes()).hexdigest()
            if _REPO_LEDGER.exists() else None)


def test_a_short_key_pages_once_with_the_restore_step_and_never_its_bytes(
        _box: tuple[Path, Path]) -> None:
    key, ledger = _box
    before = _repo_ledger_digest()
    key.write_bytes(b"ab12")                            # what a crash mid-write leaves
    for _ in range(5):
        assert provenance.account_key(7000001, "S", create=True) is None
    alerts = _ledger_alerts(ledger)
    assert set(alerts) == {libs_provenance.ALERT_KEY}
    a = alerts[libs_provenance.ALERT_KEY]
    assert a["state"] == "NEEDS_HUMAN" and len([h for h in a["history"] if "OPEN" in h]) == 1
    assert "restore data/secrets/account_key.hmac from the laptop backup" in a["message"]
    assert "never regenerate" in a["message"].lower() and "4 bytes" in a["message"]
    assert "ab12" not in ledger.read_text("utf-8"), "the key's bytes reached the ledger"
    assert key.read_bytes() == b"ab12", "a short key was regenerated"
    assert _repo_ledger_digest() == before, "the repo's alert ledger was touched"
    # a second process (fresh memo) is the SAME incident: still one OPEN
    libs_provenance._ALERTED.clear()
    assert provenance.account_key(7000001, "S") is None
    a = _ledger_alerts(ledger)[libs_provenance.ALERT_KEY]
    assert len([h for h in a["history"] if " OPEN" in h]) == 1


def test_an_unreadable_key_pages_and_a_restored_key_closes_the_incident(
        _box: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    key, ledger = _box
    key.write_bytes(b"k" * 64)
    real = Path.read_bytes

    def denied(self: Path) -> bytes:
        if self == key:
            raise PermissionError("denied")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", denied)
    libs_provenance._KEY_CACHE.clear()
    assert provenance.account_key(7000001, "S") is None
    a = _ledger_alerts(ledger)[libs_provenance.ALERT_KEY]
    assert a["state"] == "NEEDS_HUMAN" and "unreadable (PermissionError)" in a["message"]
    assert libs_provenance.key_state()["state"] == "unreadable"
    monkeypatch.setattr(Path, "read_bytes", real)
    assert provenance.account_key(7000001, "S") is not None      # restored
    assert _ledger_alerts(ledger)[libs_provenance.ALERT_KEY]["state"] == "FIXED"


def test_key_state_reports_state_and_size_never_contents(_box: tuple[Path, Path]) -> None:
    key, _ledger = _box
    assert libs_provenance.key_state()["state"] == "absent"
    key.write_bytes(b"ab12")
    st = libs_provenance.key_state()
    assert st["state"] == "short" and st["size_bytes"] == 4 and "ab12" not in repr(st)
    key.write_bytes(b"k" * 64)
    st = libs_provenance.key_state()
    assert st["state"] == "present" and st["size_bytes"] == 64 and "kkkk" not in repr(st)


@pytest.mark.parametrize("name", ["trader.alice", "alice@example.invalid", "x7000001"],
                         ids=["dotted", "email", "letter-prefix"])
def test_a_username_login_keys_none_and_pages_once_without_the_name(
        _box: tuple[Path, Path], name: str) -> None:
    key, ledger = _box
    key.write_bytes(b"k" * 64)
    for _ in range(3):
        assert provenance.account_key(name, "S", create=True) is None
    row = provenance.stamp({"login": name, "server": "S", "kind": LIVE})
    assert row["account_key"] is None and "account" not in row
    alerts = _ledger_alerts(ledger)
    assert set(alerts) == {libs_provenance.ALERT_USERNAME}
    a = alerts[libs_provenance.ALERT_USERNAME]
    assert len([h for h in a["history"] if " OPEN" in h]) == 1
    assert name not in ledger.read_text("utf-8"), "the username reached the ledger"


def test_garbage_that_is_not_a_username_does_not_page(_box: tuple[Path, Path]) -> None:
    key, ledger = _box
    key.write_bytes(b"k" * 64)
    for g in (None, 0, -1, 7000001.5, b"7000001", "", "  "):
        assert provenance.account_key(g, "S") is None
    assert _ledger_alerts(ledger) == {}


def test_numpy_integer_logins_key_like_an_int() -> None:
    np = pytest.importorskip("numpy")
    want = libs_provenance.account_key(7000001, "X")
    for v in (np.int64(7000001), np.int32(7000001), np.uint32(7000001), np.uint64(7000001),
              np.float64(7000001.0)):
        assert libs_provenance.norm_login(v) == 7000001, type(v)
        assert libs_provenance.account_key(v, "X") == want
    for bad in (np.True_, np.int64(0), np.int64(-7), np.float64(7000001.5)):
        assert libs_provenance.norm_login(bad) is None, repr(bad)


def test_numpy_is_not_imported_by_the_module() -> None:
    import subprocess
    code = ("import sys; import libs.ops.provenance as p; p.norm_login(7); "
            "print('numpy' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=str(_DESK.parents[1]),
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "False"
