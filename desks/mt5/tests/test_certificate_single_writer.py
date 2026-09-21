"""Regression fences for certificate authority and the full intraday collector."""

from pathlib import Path


DESK = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (DESK / relative).read_text("utf-8")


def test_explain_exists_before_expand_universe_entrypoint() -> None:
    source = _text("research/expand_universe.py")
    assert source.index("def _explain(") < source.index('if __name__ == "__main__":')


def test_external_gauntlet_is_the_only_pipeline_certificate_writer() -> None:
    authority = 'REPORTS / "UNIVERSAL_SURVIVORS.json"'
    assert authority in _text("scripts/external_gauntlet.py")
    for relative in (
        "research/universal_gate.py",
        "scripts/full_pipeline.py",
        "scripts/full_pipeline_v2.py",
    ):
        assert authority not in _text(relative), relative


def test_external_gauntlet_recovers_only_exact_gate_archive_rows() -> None:
    source = _text("scripts/external_gauntlet.py")
    assert 'DATA / "UNIVERSAL_SURVIVORS.canon.json"' in source
    assert "all_ten_pass(row.get(\"gates\"))" in source


def test_universe_job_fills_missing_ladder_instead_of_rewalking_it() -> None:
    wrapper = (DESK.parents[1] / "ops" / "run_universe.cmd").read_text("utf-8")
    assert "scripts\\download_all_symbols.py" in wrapper
    assert "research\\expand_universe.py" not in wrapper
    downloader = _text("scripts/download_all_symbols.py")
    assert '"M1": 200_000' in downloader
    assert '"M5": 120_000' in downloader
    assert '"M15": 80_000' in downloader
    assert '"M30": 60_000' in downloader
    assert '"H4": 30_000' in downloader
