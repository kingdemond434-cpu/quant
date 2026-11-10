"""R3: the attested evaluator re-sign path fails closed on every irregularity (2026-11-10).

Throwaway keys only; nothing here touches the box, GitHub or the real manifest.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ed25519  # noqa: E402


def _mod() -> Any:
    path = ROOT / "ops" / "release" / "authority" / "evaluator_attest.py"
    spec = importlib.util.spec_from_file_location("evaluator_attest_t", path)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    sys.modules["evaluator_attest_t"] = m
    spec.loader.exec_module(m)
    return m


EA = _mod()
F = "desks/mt5/research/gate_policy.py"
OLD, NEW = "a" * 16, "b" * 16
HEAD, BASE = "1" * 40, "2" * 40
T0 = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)


def _key() -> tuple[Any, tuple[Any, str]]:
    priv = ed25519.Ed25519PrivateKey.generate()
    raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    pub = EA.pinned_key(base64.b64encode(raw).decode())
    assert pub is not None
    return priv, pub


def _envs(
    priv: Any, kid: str, changed: dict[str, tuple[str, str]] | None = None
) -> list[dict[str, str]]:
    sts = EA.statements(
        changed or {F: (OLD, NEW)},
        repo="o/r",
        head=HEAD,
        base=BASE,
        digest="d" * 64,
        auditor_at="2026-11-10T19:00:00+00:00",
        kid=kid,
        now=T0,
    )
    return [EA.sign_statement(st, priv, kid) for st in sts]


def _manifest(tmp: Path, files: dict[str, str]) -> Path:
    p = tmp / "IMMUTABLE_MANIFEST.json"
    p.write_text(
        json.dumps({"signed_by": "principal", "files": files, "append_only": {"x": {"n": 1}}}),
        "utf-8",
    )
    return p


def test_no_pinned_key_means_the_path_is_off(tmp_path: Path) -> None:
    priv, (_pub, kid) = _key()
    m = _manifest(tmp_path, {F: OLD})
    ok, _why = EA.apply(_envs(priv, kid), manifest=m, current={F: NEW}, immutable=(F,), key=None)
    assert not ok and json.loads(m.read_text())["files"][F] == OLD
    assert EA.PINNED_PUBKEY_B64 == "" or EA.pinned_key() is not None


def test_apply_writes_only_the_attested_hash_and_keeps_the_record_seals(tmp_path: Path) -> None:
    priv, key = _key()
    m = _manifest(tmp_path, {F: OLD, "other.py": "c" * 16})
    ok, lines = EA.apply(
        _envs(priv, key[1]), manifest=m, current={F: NEW}, immutable=(F,), key=key, now=T0
    )
    doc = json.loads(m.read_text())
    assert ok, lines
    assert doc["files"] == {F: NEW, "other.py": "c" * 16}
    assert doc["append_only"] == {"x": {"n": 1}} and doc["signed_by"] == "principal"
    assert doc["rotation_signers"][F] == f"release-authority:{key[1]}"
    assert EA.verify_manifest(m, key) == []


def test_another_key_is_refused(tmp_path: Path) -> None:
    priv, _ = _key()
    _, other = _key()
    m = _manifest(tmp_path, {F: OLD})
    ok, _ = EA.apply(_envs(priv, other[1]), manifest=m, current={F: NEW}, immutable=(F,), key=other)
    assert not ok


def test_an_edited_statement_fails_the_signature(tmp_path: Path) -> None:
    priv, key = _key()
    env = _envs(priv, key[1])[0]
    env["statement"] = env["statement"].replace(NEW, "e" * 16)
    m = _manifest(tmp_path, {F: OLD})
    ok, lines = EA.apply([env], manifest=m, current={F: "e" * 16}, immutable=(F,), key=key)
    assert not ok and any("signature" in x for x in lines)


def test_stale_or_replayed_and_wrong_checkout_are_refused(tmp_path: Path) -> None:
    priv, key = _key()
    m = _manifest(tmp_path, {F: "f" * 16})
    assert not EA.apply(_envs(priv, key[1]), manifest=m, current={F: NEW}, immutable=(F,), key=key)[
        0
    ]
    m = _manifest(tmp_path, {F: OLD})
    assert not EA.apply(
        _envs(priv, key[1]), manifest=m, current={F: "9" * 16}, immutable=(F,), key=key
    )[0]


def test_all_or_nothing(tmp_path: Path) -> None:
    priv, key = _key()
    g = "libs/portfolio/rails.py"
    envs = _envs(priv, key[1], {F: (OLD, NEW), g: (OLD, NEW)})
    m = _manifest(tmp_path, {F: OLD, g: "0" * 16})
    ok, _ = EA.apply(envs, manifest=m, current={F: NEW, g: NEW}, immutable=(F, g), key=key)
    assert not ok and json.loads(m.read_text())["files"] == {F: OLD, g: "0" * 16}


def test_the_fence_itself_is_never_attested(tmp_path: Path) -> None:
    priv, key = _key()
    me = "scripts/check_immutable_evaluator.py"
    m = _manifest(tmp_path, {me: OLD})
    ok, _ = EA.apply(
        _envs(priv, key[1], {me: (OLD, NEW)}),
        manifest=m,
        current={me: NEW},
        immutable=(me,),
        key=key,
    )
    assert not ok
    good, why = EA.decide({me: (OLD, NEW)}, {me: OLD}, {"files": {me: NEW}})
    assert not good and any("fence itself" in w for w in why)


def test_decide_is_exact_match_with_the_auditor_row() -> None:
    assert EA.decide({F: (OLD, NEW)}, {F: OLD}, {"files": {F: NEW}})[0]
    assert not EA.decide({F: (OLD, NEW)}, {F: OLD}, {"files": {F: "9" * 16}})[0]
    assert not EA.decide({F: (OLD, NEW)}, {F: OLD}, {"files": {F: NEW, "x.py": NEW}})[0]
    assert not EA.decide({F: (OLD, NEW)}, {F: "3" * 16}, {"files": {F: NEW}})[0]
    assert not EA.decide({F: (OLD, "<absent>")}, {F: OLD}, {"files": {F: "<absent>"}})[0]
    assert not EA.decide({}, {}, {"files": {F: NEW}})[0]


def test_latest_auditor_row_wins_and_hold_vetoes() -> None:
    rows = [
        {"kind": "EVALUATOR_CLEAR", "head": HEAD, "files": {F: NEW}, "at": "t1"},
        {"kind": "EVALUATOR_HOLD", "head": HEAD, "at": "t2"},
    ]
    assert EA.auditor_clear(rows, HEAD)[0] is None
    assert EA.auditor_clear(rows[:1], HEAD)[0] is not None
    assert EA.auditor_clear(rows[:1], BASE)[0] is None


def test_verify_flags_a_forged_attestation(tmp_path: Path) -> None:
    priv, key = _key()
    m = _manifest(tmp_path, {F: OLD})
    assert EA.apply(_envs(priv, key[1]), manifest=m, current={F: NEW}, immutable=(F,), key=key)[0]
    doc = json.loads(m.read_text())
    doc["attestations"][F]["sig"] = base64.b64encode(b"\0" * 64).decode()
    m.write_text(json.dumps(doc))
    assert EA.verify_manifest(m, key)
    assert EA.verify_manifest(m, None)  # claims an attestation, nothing to verify it with


def test_hash_rule_matches_the_fence() -> None:
    assert EA.content_hash(b"a\r\nb\n") == EA.content_hash(b"a\nb\n")


def test_the_repository_manifest_carries_no_unverifiable_attestation() -> None:
    fen = EA.fence()
    assert EA.verify_manifest(fen.MANIFEST, EA.pinned_key()) == []
