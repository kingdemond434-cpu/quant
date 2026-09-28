import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK / "scripts", DESK / "research"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import external_gauntlet as eg  # noqa: E402


def test_streaming_array_preserves_every_row_and_order(tmp_path) -> None:
    rows = [{"i": i, "payload": "x" * (i % 13)} for i in range(1000)]
    path = tmp_path / "docket.json"
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    assert list(eg.iter_json_array(path, chunk_chars=37)) == rows


def test_streaming_array_rejects_a_non_array(tmp_path) -> None:
    path = tmp_path / "docket.json"
    path.write_text('{"rows": []}', encoding="utf-8")
    try:
        list(eg.iter_json_array(path, chunk_chars=5))
    except ValueError as exc:
        assert "top-level JSON array" in str(exc)
    else:
        raise AssertionError("non-array docket was accepted")
