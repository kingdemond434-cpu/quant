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
    assert provenance.account_key("5551234", "S") != provenance.account_key(5551234, "S")
    assert provenance.account_key(1, "") != provenance.account_key(1, None)
    for bad in ((None, "S"), ("", "S"), (True, "S")):
        assert provenance.account_key(*bad) is None


def test_the_helper_s_signature_is_stable() -> None:
    sig = inspect.signature(libs_provenance.account_key)
    assert str(sig) == "(login: 'object', server: 'object', *, create: 'bool' = False) -> 'str | None'"


def test_no_box_key_is_the_none_sentinel_never_a_bare_hash(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_the_writer_creates_the_key_once_and_never_prints_it(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch,
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
