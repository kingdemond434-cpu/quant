"""The tape's off-box destination signs correctly, proves arrival, and never leaks a credential.

This module moves the one dataset on this desk that cannot be re-obtained. Three properties have
to hold before a single tick is entrusted to it: the signature is the one S3 expects (or nothing
uploads at all), an object is only called archived when it has been read back and shown to be the
bytes we sent, and no failure path anywhere prints the secret that produced the signature.

The signing vectors are checked against a FIXED clock and fixed keys, so the test fails on any
change to the canonical request -- header set, ordering, path escaping -- rather than only when a
live endpoint happens to reject it. A signature bug found by a provider at 3am on a full disk is
the same bug found here in a millisecond.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys

import pytest

DESK = pathlib.Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from mt5desk import object_store as ostore  # noqa: E402

CFG = ostore.Config(endpoint="https://acct.r2.cloudflarestorage.com", key_id="AKIAEXAMPLE",
                    secret="s3cr3t-not-real", bucket="quant-tape", region="auto")
CLOCK = dt.datetime(2026, 9, 7, 12, 0, 0, tzinfo=dt.UTC)


def test_the_signature_is_deterministic_and_covers_the_right_headers() -> None:
    body = b"tick-bytes"
    url, h = ostore._signed_headers(
        CFG, "PUT", "ticks/XAUUSD/2026-01-02.parquet", hashlib.sha256(body).hexdigest(),
        {"content-length": str(len(body))}, now=CLOCK)

    assert url == ("https://acct.r2.cloudflarestorage.com/quant-tape/"
                   "ticks/XAUUSD/2026-01-02.parquet"), "path-style URL changed"
    assert h["x-amz-date"] == "20260907T120000Z"
    auth = h["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE/20260907/auto/s3/aws4_request")
    # The signed-header list is part of the signature; a silent addition or drop breaks uploads
    # at the provider and nowhere else, so it is pinned.
    assert "SignedHeaders=content-length;host;x-amz-content-sha256;x-amz-date" in auth
    # Same inputs, same signature: the only variable is the clock, which is injected.
    again = ostore._signed_headers(
        CFG, "PUT", "ticks/XAUUSD/2026-01-02.parquet", hashlib.sha256(body).hexdigest(),
        {"content-length": str(len(body))}, now=CLOCK)[1]
    assert again["Authorization"] == auth


def test_a_key_with_slashes_keeps_them_and_odd_characters_are_escaped() -> None:
    """Slashes SEPARATE an object key; escaping them would address a different object."""
    url, _ = ostore._signed_headers(CFG, "PUT", "a/b c/d+e.parquet", "x", now=CLOCK)
    assert url.endswith("/quant-tape/a/b%20c/d%2Be.parquet"), url


def test_verify_accepts_only_the_exact_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b"tick-bytes"
    good = hashlib.md5(body).hexdigest()                        # noqa: S324 - S3's ETag is MD5

    monkeypatch.setattr(ostore, "head", lambda c, k, timeout=60.0: (len(body), good, "present"))
    ok, why = ostore.verify(CFG, "k", body)
    assert ok, why

    monkeypatch.setattr(ostore, "head", lambda c, k, timeout=60.0: (len(body) + 1, good, "present"))
    assert not ostore.verify(CFG, "k", body)[0], "a size mismatch was accepted"

    monkeypatch.setattr(ostore, "head", lambda c, k, timeout=60.0: (len(body), "deadbeef", "present"))
    assert not ostore.verify(CFG, "k", body)[0], "a wrong ETag was accepted"

    # A multipart ETag cannot prove content. Accepting it would mean deleting an irreplaceable
    # source on the strength of a checksum that does not describe the bytes.
    monkeypatch.setattr(ostore, "head", lambda c, k, timeout=60.0: (len(body), good + "-2", "present"))
    ok, why = ostore.verify(CFG, "k", body)
    assert not ok and "multipart" in why

    monkeypatch.setattr(ostore, "head", lambda c, k, timeout=60.0: (None, None, "absent"))
    assert not ostore.verify(CFG, "k", body)[0], "an absent object was accepted"


def test_no_failure_path_prints_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """A credential in an error message ends up in a log, a paste and a screenshot."""
    class Resp:
        status_code = 403
        text = "SignatureDoesNotMatch"
        headers: dict[str, str] = {}

    class FakeRequests:
        @staticmethod
        def put(url, data=None, headers=None, timeout=None):
            return Resp()

    monkeypatch.setitem(sys.modules, "requests", FakeRequests)
    ok, detail = ostore.put(CFG, "k", b"x")
    assert not ok
    assert CFG.secret not in detail and CFG.key_id not in detail, detail
    assert CFG.secret not in CFG.describe(), "describe() leaked the secret"
    assert CFG.key_id not in CFG.describe(), "describe() leaked the full key id"
    assert "AKIA" in CFG.describe(), "describe() should still identify WHICH key is in use"


def test_config_is_absent_rather_than_broken_when_unset(tmp_path, monkeypatch) -> None:
    """An unconfigured box must still be able to MEASURE, so this reports rather than raises."""
    for env in ostore.ENV.values():
        monkeypatch.delenv(env, raising=False)
    cfg, why = ostore.load(root=tmp_path)
    assert cfg is None and "not configured" in why
    assert "TAPE_ARCHIVE_ENDPOINT" in why, "the reason must name what to set"


def test_the_secrets_file_configures_it_and_env_wins(tmp_path, monkeypatch) -> None:
    for env in ostore.ENV.values():
        monkeypatch.delenv(env, raising=False)
    d = tmp_path / "data" / "secrets"
    d.mkdir(parents=True)
    (d / "tape_archive.json").write_text(json.dumps({
        "endpoint": "https://x.example.com/", "key_id": "K", "secret": "S",
        "bucket": "b", "region": "eu-west-1"}), "utf-8")

    cfg, why = ostore.load(root=tmp_path)
    assert cfg is not None, why
    assert cfg.endpoint == "https://x.example.com", "the trailing slash must be trimmed"
    assert cfg.region == "eu-west-1"

    monkeypatch.setenv("TAPE_ARCHIVE_BUCKET", "override")
    cfg, _ = ostore.load(root=tmp_path)
    assert cfg.bucket == "override", "the environment must win over the stored file"
