"""desk_health turns RED (PROBLEM) when miner_candidates.json is over 2 h old."""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import check_desk_health as dh  # noqa: E402


def _run(tmp_path, age_s):
    f = tmp_path / "miner_candidates.json"
    if age_s is not None:
        stamp = (datetime.now(UTC) - timedelta(seconds=age_s)).isoformat(timespec="seconds")
        f.write_text('{"compiled_at": "%s", "hypotheses": []}' % stamp)
    dh._FINDINGS.clear()
    dh.check_compiler_fresh(f)
    return [x["level"] for x in dh._FINDINGS]


def test_fresh_is_ok(tmp_path):
    assert _run(tmp_path, 600) == ["OK"]


def test_stale_is_a_problem_not_ok(tmp_path):
    assert _run(tmp_path, 3 * 3600) == ["PROBLEM"]


def test_absent_is_a_problem(tmp_path):
    assert _run(tmp_path, None) == ["PROBLEM"]


def test_unstamped_is_unknown_never_ok(tmp_path):
    (tmp_path / "miner_candidates.json").write_text('{"hypotheses": []}')
    dh._FINDINGS.clear()
    dh.check_compiler_fresh(tmp_path / "miner_candidates.json")
    assert [x["level"] for x in dh._FINDINGS] == ["UNKNOWN"]
