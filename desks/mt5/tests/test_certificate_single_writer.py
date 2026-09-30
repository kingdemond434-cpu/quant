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
        # retired to scripts/_retired/ in 7401f769 (2026-09-27); still must never write it
        "scripts/_retired/full_pipeline_v2.py",
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
    assert "C:\\Program Files\\Python314\\python.exe" in wrapper
    assert '"%PYTHON%" %PYARGS% -u -W ignore' in wrapper
    downloader = _text("scripts/download_all_symbols.py")
    assert 'exclusive_job("fusion_terminal_research_lane"' in downloader
    assert "from research.expand_universe import _pull_bars" in downloader
    assert "_hydration_retried" in downloader
    assert "attach_or_initialize(mt5, path=terminal_path(), timeout=30_000)" in downloader
    assert "mt5.shutdown()\ntime.sleep(1)\nmt5.initialize()" not in downloader
    assert "pq.ParquetFile(pq_path).metadata" in downloader
    assert "pd.read_parquet(pq_path)" not in downloader
    assert "def _recent_no_data(" in downloader
    assert "24 * 3600" in downloader
    assert "def _all_cells_accounted_for(" in downloader
    assert "no Fusion request is due" in downloader
    assert downloader.index("if _accounted:") < downloader.index("import MetaTrader5 as mt5")
    assert '"M1": 200_000' in downloader
    assert '"M5": 120_000' in downloader
    assert '"M15": 80_000' in downloader
    assert '"M30": 60_000' in downloader
    assert '"H4": 30_000' in downloader


def test_gauntlet_and_universe_share_the_fusion_research_lane() -> None:
    gauntlet = _text("scripts/external_gauntlet.py")
    assert 'exclusive_job("fusion_terminal_research_lane"' in gauntlet
    installer = _text("scripts/Install-QuantWindows.ps1")
    assert "(Get-Date).Date.AddMinutes(30)" in installer
