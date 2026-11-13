"""ONLY REAL EDGES ON THE PROP BOOKS (research/real_edge.py): one judge, read by E8 and FTMO."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import real_edge as re_  # noqa: E402


def _write(tmp: Path, rows: dict) -> Path:
    p = tmp / "REOPEN_VERIFICATION.json"
    p.write_text(json.dumps({"rows": rows, "n_verified": 0}), "utf-8")
    return p


def test_verified_refused_and_unlisted(tmp_path) -> None:
    p = _write(tmp_path, {
        "XAUUSD.a": {"certificate": "external.A", "verified": True, "why_not": []},
        "EURUSD.b": {"certificate": "external.B", "verified": False,
                     "why_not": ["forward t 1.2 < 2", "n 14 < 30"]}})
    v, status = re_.load(p)
    assert status.startswith("OK: 1 of 2")
    assert re_.verified("external.A", v) and re_.refusal("external.A", v) is None
    assert not re_.verified("external.B", v)
    assert "forward t 1.2 < 2" in str(re_.refusal("external.B", v))
    assert re_.refusal("external.Z", v) is None and not re_.verified("external.Z", v)


def test_one_failing_clock_fails_a_shared_certificate(tmp_path) -> None:
    p = _write(tmp_path, {
        "k1": {"certificate": "external.C", "verified": True, "why_not": []},
        "k2": {"certificate": "external.C", "verified": False, "why_not": ["max DD -31R"]}})
    v, _ = re_.load(p)
    assert not re_.verified("external.C", v) and "max DD" in str(re_.refusal("external.C", v))


def test_absent_or_torn_is_unmeasured_and_admits_nothing_new(tmp_path) -> None:
    v, status = re_.load(tmp_path / "absent.json")
    assert v == {} and status.startswith("UNMEASURED")
    (tmp_path / "torn.json").write_text("{", "utf-8")
    v, status = re_.load(tmp_path / "torn.json")
    assert v == {} and status.startswith("UNMEASURED") and not re_.verified("external.A", v)


def test_both_prop_books_and_the_e8_door_read_the_same_judge() -> None:
    for rel in ("research/prop_challenge_allocator.py", "prop/e8_book.py",
                "prop/e8_executor.py"):
        src = (_DESK / rel).read_text("utf-8")
        assert "real_edge.load()" in src and "refusal(" in src, rel


def test_it_never_sizes_or_sends() -> None:
    src = (_DESK / "research" / "real_edge.py").read_text("utf-8")
    for banned in ("order_send", "load_cert_book", "__main__", "write_text"):
        assert banned not in src
