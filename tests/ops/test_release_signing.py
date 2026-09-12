"""A box must run code this desk SEALED, not code that merely appeared on disk.

    python -m pytest tests/ops/test_release_signing.py -q

THE THREE WRITERS THIS EXISTS FOR, all measured on 2026-09-11:
  * `sftp-server.exe` overwriting desks/mt5/mt5desk/families.py over an authorised key,
  * `Adopt-Release` reverting a correct allocator fix because origin lagged,
  * a RELEASE.json copied between boxes, naming a commit absent from the receiving clone.
Each is a different writer; none of them holds the signing key, and that is the whole point.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops import release_signing as rs


@pytest.fixture()
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A box with its own signing key and nothing inherited from the environment."""
    monkeypatch.delenv("QUANT_RELEASE_SIGNING_KEY", raising=False)
    (tmp_path / "data" / "secrets").mkdir(parents=True)
    created, _ = rs.ensure_key(tmp_path)
    assert created
    return tmp_path


def _record() -> dict:
    return {"code_sha": "81e21af9545d", "money_path_hash": "d59af6929a965043",
            "immutable_hash": "5337e3676406ff02", "generated_utc": "2026-09-11T18:00:00Z",
            "sealed_by": "operator", "dirty": 1032}


def test_a_stamped_record_verifies(box: Path) -> None:
    rec, why = rs.stamp(_record(), box)
    assert rec[rs.SIG_FIELD] and rec[rs.SIG_ALGO_FIELD] == rs.ALGO, why
    ok, reason = rs.verify(rec, box)
    assert ok, reason


def test_an_unsigned_record_is_refused(box: Path) -> None:
    ok, reason = rs.verify(_record(), box)
    assert not ok
    assert "no signature" in reason


def test_editing_the_money_path_hash_breaks_the_signature(box: Path) -> None:
    """THE CASE THAT MATTERS. A commit whose money path was rewritten on disk after sealing
    must stop verifying -- that is exactly the sftp trample, and a signature over code_sha
    alone would have happily passed it."""
    rec, _ = rs.stamp(_record(), box)
    assert rs.verify(rec, box)[0]
    rec["money_path_hash"] = "0000000000000000"
    ok, reason = rs.verify(rec, box)
    assert not ok
    assert "does not match" in reason


def test_editing_the_code_sha_breaks_the_signature(box: Path) -> None:
    rec, _ = rs.stamp(_record(), box)
    rec["code_sha"] = "deadbeefcafe"
    assert not rs.verify(rec, box)[0]


def test_editing_the_immutable_core_breaks_the_signature(box: Path) -> None:
    rec, _ = rs.stamp(_record(), box)
    rec["immutable_hash"] = "ffffffffffffffff"
    assert not rs.verify(rec, box)[0]


def test_provenance_fields_are_outside_the_signature(box: Path) -> None:
    """Timestamps, the sealer's name and the dirty count change for honest reasons. If they
    were signed, every honest re-read would look like tampering and the check would be
    switched off within a week."""
    rec, _ = rs.stamp(_record(), box)
    rec["generated_utc"] = "2099-01-01T00:00:00Z"
    rec["sealed_by"] = "someone else"
    rec["dirty"] = 999999
    ok, reason = rs.verify(rec, box)
    assert ok, reason


def test_another_boxs_key_does_not_verify_here(box: Path, tmp_path: Path) -> None:
    """A release sealed on a DIFFERENT box, copied here, must not pass. This is the
    RELEASE.json-copied-between-boxes failure, caught by the signature rather than by a
    confusing 'sealed commit is not in this clone' message after the fact."""
    other = tmp_path / "other_box"
    (other / "data" / "secrets").mkdir(parents=True)
    rs.ensure_key(other)
    rec, _ = rs.stamp(_record(), other)
    assert rs.verify(rec, other)[0], "sanity: it verifies on the box that signed it"
    ok, reason = rs.verify(rec, box)
    assert not ok
    assert "does not match" in reason


def test_a_missing_key_is_not_a_pass(box: Path) -> None:
    """UNMEASURED IS NOT A VERDICT (L1.28a). Deleting the key must make verification FAIL,
    never succeed-by-default -- otherwise removing one file disarms the whole check."""
    rec, _ = rs.stamp(_record(), box)
    rs.key_path(box).unlink()
    ok, reason = rs.verify(rec, box)
    assert not ok
    assert "cannot verify" in reason and "not a pass" in reason


def test_an_unknown_algorithm_is_refused(box: Path) -> None:
    rec, _ = rs.stamp(_record(), box)
    rec[rs.SIG_ALGO_FIELD] = "rot13"
    ok, reason = rs.verify(rec, box)
    assert not ok
    assert "unknown signature algorithm" in reason


def test_ensure_key_never_overwrites(box: Path) -> None:
    """Re-running setup must not silently invalidate every release sealed before it."""
    before = rs.key_path(box).read_bytes()
    created, msg = rs.ensure_key(box)
    assert not created and "already present" in msg
    assert rs.key_path(box).read_bytes() == before


def test_the_key_is_never_in_the_signed_payload(box: Path) -> None:
    """A payload that embedded the key would leak it into any log that printed the payload."""
    body = rs.payload(_record())
    assert rs.load_key(box) not in body
    assert b"secret" not in body.lower()


def test_signature_is_stable_across_field_insertion_order(box: Path) -> None:
    """Two records with the same signed values must produce the same MAC however the dict was
    built, or an honest rewrite of the file would read as tampering."""
    a = rs.stamp(_record(), box)[0][rs.SIG_FIELD]
    src = _record()
    reordered = {k: src[k] for k in reversed(list(src))}
    b = rs.stamp(reordered, box)[0][rs.SIG_FIELD]
    assert a == b


def test_the_record_round_trips_through_json(box: Path) -> None:
    """RELEASE.json is written and read as JSON; the signature must survive that unchanged."""
    rec, _ = rs.stamp(_record(), box)
    again = json.loads(json.dumps(rec))
    ok, reason = rs.verify(again, box)
    assert ok, reason
