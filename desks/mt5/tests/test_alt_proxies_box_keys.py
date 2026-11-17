"""alt_proxies loads its declared keys on the box by NAME at runtime (coordinator 2026-11-11): the
leg runs as SYSTEM and never inherited the User-scope keys, so every key read False."""
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import alt_proxies as A  # noqa: E402

DECLARED = sorted({s.key_env for s in A.SOURCES if s.key_env})


def test_read_key_first_then_secrets_file(tmp_path):
    a, b, c = DECLARED[0], DECLARED[1], DECLARED[2]
    env: dict[str, str] = {}
    f = tmp_path / "alt_keys.json"
    f.write_text(json.dumps({a: "file-a", b: "file-b", "NOT_DECLARED": "x"}), "utf-8")
    asked: list[str] = []

    def reader(name: str) -> str:
        asked.append(name)
        return "via-read-key" if name == a else ""

    src = A.load_box_keys(env, keys_file=f, reader=reader)
    assert src[a] == "read_key" and a not in env, "a key read_key finds is never shadowed by file"
    assert env[b] == "file-b" and src[b] == "secrets_file"
    assert c not in src and c not in env, "absent from both sources stays absent"
    assert "NOT_DECLARED" not in env, "only declared key_env names are ever loaded"
    assert sorted(asked) == DECLARED, "read_key is asked first, for every declared name"


def test_default_first_source_is_lives_read_key(tmp_path, monkeypatch):
    for n in DECLARED:                       # recorded so undo removes what the loader sets
        monkeypatch.setenv(n, "")
        monkeypatch.delenv(n)
    calls: list[str] = []

    def fake_read_key(n: str) -> str:
        calls.append(n)
        return "rk" if n == DECLARED[0] else ""

    monkeypatch.setattr(A, "read_key", fake_read_key)
    f = tmp_path / "alt_keys.json"
    f.write_text(json.dumps({DECLARED[0]: "file-0", DECLARED[1]: "file-1"}), "utf-8")
    src = A.load_box_keys(keys_file=f)
    assert calls == DECLARED
    assert src[DECLARED[0]] == "read_key"
    assert os.environ.get(DECLARED[0]) is None, "a read_key hit is not exported"
    assert os.environ[DECLARED[1]] == "file-1" and src[DECLARED[1]] == "secrets_file"


def test_a_refused_key_is_never_loaded(tmp_path, monkeypatch):
    a, b = DECLARED[0], DECLARED[1]
    monkeypatch.setattr(A, "key_refused", lambda n: n == a)
    env: dict[str, str] = {}
    f = tmp_path / "alt_keys.json"
    f.write_text(json.dumps({a: "paid-value", b: "free-value"}), "utf-8")
    src = A.load_box_keys(env, keys_file=f, reader=lambda n: "set" if n == a else "")
    assert src[a] == "refused" and a not in env
    assert env[b] == "free-value" and src[b] == "secrets_file"
    assert "paid-value" not in json.dumps(src)


def test_the_loader_uses_the_catalogs_refusal():
    env_keys = sys.modules["libs.ops.env_keys"]
    assert A.key_refused is env_keys.refused and A.read_key is env_keys.read_key


def test_absent_everywhere_stays_absent_and_blocked(tmp_path):
    env: dict[str, str] = {}
    src = A.load_box_keys(env, keys_file=tmp_path / "none.json", reader=lambda n: "")
    assert src == {} and env == {}
    keyed = next(s for s in A.SOURCES if s.key_env and s.terms == "confirmed")
    assert A.status_of(keyed, env).startswith("BLOCKED_ON_KEY:")


def test_the_source_map_never_carries_a_value(tmp_path):
    env: dict[str, str] = {}
    f = tmp_path / "k.json"
    f.write_text(json.dumps({DECLARED[0]: "s3cr3t-value"}), "utf-8")
    src = A.load_box_keys(env, keys_file=f, reader=lambda n: "")
    assert "s3cr3t-value" not in json.dumps(src)


def test_secrets_presence_is_boolean_only(tmp_path):
    (tmp_path / "latam_apis.json").write_text(json.dumps({"banxico_token": "tok-123"}), "utf-8")
    keys = {DECLARED[0]: "v", DECLARED[1]: " "}
    (tmp_path / "alt_keys.json").write_text(json.dumps(keys), "utf-8")
    p = A.secrets_presence(tmp_path)
    assert p["latam_apis.json:banxico_token"] is True
    assert p[f"alt_keys.json:{DECLARED[0]}"] is True and p[f"alt_keys.json:{DECLARED[1]}"] is False
    assert all(isinstance(v, bool) for v in p.values()) and "tok-123" not in json.dumps(p)
    assert A.secrets_presence(tmp_path / "missing")["latam_apis.json:banxico_token"] is False


class _FakeWinreg:
    """Only ANOTHER account's hive (HKEY_USERS\\<sid>\\Environment) holds the keys; this account's
    HKCU and the machine scope hold nothing."""
    HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER, HKEY_USERS = object(), object(), object()
    REG_SZ, REG_EXPAND_SZ, KEY_READ, KEY_WOW64_64KEY = 1, 2, 0x20019, 0x100

    def __init__(self, hives):
        self.hives = hives            # {sid: {name: (value, type)}}
        self.opened: list[str] = []

    def EnumKey(self, root, i):
        sids = list(self.hives)
        if root is not self.HKEY_USERS or i >= len(sids):
            raise OSError
        return sids[i]

    def OpenKey(self, root, path, *a, **k):
        if root is self.HKEY_USERS:
            self.opened.append(path)
            sid = path.split("\\")[0]
            if sid in self.hives:
                import contextlib as _c
                return _c.nullcontext(self.hives[sid])
        raise OSError

    def QueryValueEx(self, k, name):
        if name not in k:
            raise OSError
        return k[name]

    def EnumValue(self, k, i):
        items = list(k.items())
        if i >= len(items):
            raise OSError
        n, (v, t) = items[i]
        return n, v, t


def test_no_other_accounts_value_ever_reaches_the_environment_or_the_result(tmp_path,
                                                                             monkeypatch):
    other = "other-sid-s3cr3t"
    fake = _FakeWinreg({"S-1-5-21-9-1001": dict.fromkeys(DECLARED, (other, 1))})
    monkeypatch.setitem(sys.modules, "winreg", fake)
    monkeypatch.setattr(sys, "platform", "win32")
    for n in DECLARED:
        monkeypatch.setenv(n, "")
        monkeypatch.delenv(n)
    src = A.load_box_keys(keys_file=tmp_path / "none.json")
    assert src == {}, "nothing was found in this account's scopes or the secrets file"
    assert all(os.environ.get(n) != other for n in DECLARED)
    assert other not in json.dumps(src)
    assert not any(read for read in fake.opened if read.endswith("\\Environment")), \
        "the loader never opens another account's Environment key"


def test_the_hive_walk_is_gone():
    assert not hasattr(A, "_registry_user_env") and not hasattr(A, "REGISTRY_CONFLICTS")
    assert "HKEY_USERS" not in inspect.getsource(A)
