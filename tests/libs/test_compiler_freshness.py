"""A stale compiled-candidates file must never pass as current (2026-11-25)."""
from datetime import UTC, datetime, timedelta

from libs.research import compiler_freshness as cf

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def _write(path, age_s, tail=""):
    stamp = (NOW - timedelta(seconds=age_s)).isoformat(timespec="seconds")
    path.write_text('{\n "compiled_at": "%s",\n "freshness": {},\n "hypotheses": [%s]\n}'
                    % (stamp, tail))
    return path


def test_fresh_stale_and_boundary(tmp_path):
    p = _write(tmp_path / "c.json", 600)
    assert cf.is_fresh(p, NOW) and cf.age_s(p, NOW) == 600
    assert not cf.is_fresh(_write(tmp_path / "s.json", cf.MAX_AGE_S + 1), NOW)
    assert cf.is_fresh(_write(tmp_path / "b.json", cf.MAX_AGE_S), NOW)


def test_absent_unreadable_and_unstamped_are_never_fresh(tmp_path):
    assert cf.age_s(tmp_path / "nope.json", NOW) is None
    assert not cf.is_fresh(tmp_path / "nope.json", NOW)
    bad = tmp_path / "bad.json"
    bad.write_text('{"hypotheses": []}')
    assert cf.age_s(bad, NOW) is None and not cf.is_fresh(bad, NOW)
    bad.write_text('{"compiled_at": "not a date"}')
    assert cf.age_s(bad, NOW) is None


def test_head_read_does_not_need_the_whole_file(tmp_path):
    p = _write(tmp_path / "big.json", 60, tail='"' + "x" * 3_000_000 + '"')
    assert cf.age_s(p, NOW) == 60


def test_compiler_publishes_the_freshness_block_and_phase_marks():
    import inspect

    from research import miner_candidate_compiler as mcc
    src = inspect.getsource(mcc.main)
    for phase in ("setup_s", "intake_s", "compile_s", "graph_s", "steer_s", "stamp_s"):
        assert f'_mark("{phase}")' in src
    assert '"freshness": {' in src and mcc.FRESH_MAX_AGE_S == cf.MAX_AGE_S
