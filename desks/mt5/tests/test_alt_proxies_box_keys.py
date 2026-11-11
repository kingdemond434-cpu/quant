"""alt_proxies loads its declared keys on the box by NAME at runtime (coordinator 2026-11-11): the
leg runs as SYSTEM and never inherited the User-scope keys, so every key read False."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import alt_proxies as A  # noqa: E402

DECLARED = sorted({s.key_env for s in A.SOURCES if s.key_env})


def test_env_wins_then_file_then_registry(tmp_path):
    a, b, c = DECLARED[0], DECLARED[1], DECLARED[2]
    env = {a: "from-env"}
    f = tmp_path / "alt_keys.json"
    f.write_text(json.dumps({a: "file-a", b: "file-b", "NOT_DECLARED": "x"}), "utf-8")
    asked: list[set[str]] = []

    def reg(names: set[str]) -> dict[str, str]:
        asked.append(set(names))
        return {c: "reg-c", b: "reg-b"}

    src = A.load_box_keys(env, keys_file=f, registry=reg)
    assert env[a] == "from-env" and src[a] == "env"
    assert env[b] == "file-b" and src[b] == "secrets_file"
    assert env[c] == "reg-c" and src[c] == "registry_user"
    assert "NOT_DECLARED" not in env, "only declared key_env names are ever loaded"
    assert b not in asked[0] and a not in asked[0], "the registry is asked only for what is missing"


def test_absent_everywhere_stays_absent_and_blocked(tmp_path):
    env: dict[str, str] = {}
    src = A.load_box_keys(env, keys_file=tmp_path / "none.json", registry=lambda n: {})
    assert src == {} and env == {}
    keyed = next(s for s in A.SOURCES if s.key_env and s.terms == "confirmed")
    assert A.status_of(keyed, env).startswith("BLOCKED_ON_KEY:")


def test_the_source_map_never_carries_a_value(tmp_path):
    env: dict[str, str] = {}
    f = tmp_path / "k.json"
    f.write_text(json.dumps({DECLARED[0]: "s3cr3t-value"}), "utf-8")
    src = A.load_box_keys(env, keys_file=f, registry=lambda n: {})
    assert "s3cr3t-value" not in json.dumps(src)


def test_registry_reader_is_inert_off_windows(monkeypatch):
    monkeypatch.setattr(A.sys, "platform", "linux")
    assert A._registry_user_env({DECLARED[0]}) == {}


def test_secrets_presence_is_boolean_only(tmp_path):
    (tmp_path / "latam_apis.json").write_text(json.dumps({"banxico_token": "tok-123"}), "utf-8")
    (tmp_path / "alt_keys.json").write_text(json.dumps({DECLARED[0]: "v", DECLARED[1]: " "}), "utf-8")
    p = A.secrets_presence(tmp_path)
    assert p["latam_apis.json:banxico_token"] is True
    assert p[f"alt_keys.json:{DECLARED[0]}"] is True and p[f"alt_keys.json:{DECLARED[1]}"] is False
    assert all(isinstance(v, bool) for v in p.values()) and "tok-123" not in json.dumps(p)
    assert A.secrets_presence(tmp_path / "missing")["latam_apis.json:banxico_token"] is False
