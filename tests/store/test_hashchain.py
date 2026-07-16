"""Tests for hash-chain primitives."""

from __future__ import annotations

from typing import Any

from libs.store.hashchain import (
    GENESIS_PREV_HASH,
    canonical_json,
    compute_chain_hash,
    verify_chain,
)


def _build_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {"seq": row["seq"], "value": row["value"], "prev_hash": row["prev_hash"]}


def _make_chain(values: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prev = GENESIS_PREV_HASH
    for i, value in enumerate(values, start=1):
        fields = {"seq": i, "value": value, "prev_hash": prev}
        row_hash = compute_chain_hash(fields)
        rows.append({"seq": i, "value": value, "prev_hash": prev, "row_hash": row_hash})
        prev = row_hash
    return rows


def test_canonical_json_is_order_independent() -> None:
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_compute_chain_hash_is_deterministic() -> None:
    fields = {"seq": 1, "value": "x", "prev_hash": GENESIS_PREV_HASH}
    assert compute_chain_hash(fields) == compute_chain_hash(dict(fields))


def test_verify_chain_accepts_intact_chain() -> None:
    rows = _make_chain(["a", "b", "c"])
    ok, broken, _ = verify_chain(rows, _build_fields)
    assert ok
    assert broken is None


def test_verify_chain_detects_tampered_value() -> None:
    rows = _make_chain(["a", "b", "c"])
    rows[1]["value"] = "TAMPERED"
    ok, broken, message = verify_chain(rows, _build_fields)
    assert not ok
    assert broken == 2
    assert "tampered" in message


def test_verify_chain_detects_broken_linkage() -> None:
    rows = _make_chain(["a", "b"])
    rows[1]["prev_hash"] = "0" * 64
    ok, broken, _ = verify_chain(rows, _build_fields)
    assert not ok
    assert broken == 2


def test_verify_chain_detects_non_contiguous_seq() -> None:
    rows = _make_chain(["a", "b"])
    rows[1]["seq"] = 5
    ok, _broken, _ = verify_chain(rows, _build_fields)
    assert not ok
