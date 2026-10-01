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
    # The judge restores only retired rows that still pass all ten gates.
    source = _text("scripts/external_gauntlet.py")
    assert "all_ten_pass(row.get(\"gates\"))" in source
    # Canon recovery is NOT the judge's: `external_gauntlet.py` never held a
    # `DATA / "UNIVERSAL_SURVIVORS.canon.json"` path in any reachable history (`git log --all -S`
    # finds only this test's own import in bcbec41f0). The one pen on the canonical seal is
    # research/canon_publication.py (0c1cceef8): it recovers stranded verdicts from the gate
    # output under the same all-ten predicate and merges them through publish()'s refusals.
    owner = _text("research/canon_publication.py")
    assert 'SEAL = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"' in owner
    assert "def recover_from_gate_output(" in owner
    recover = owner.split("def recover_from_gate_output(", 1)[1].split("\ndef ", 1)[0]
    assert "if not all_ten_pass(stages):" in recover
    assert "superseded = not is_admissible_trial_count_basis(gate_basis)" in recover
    publish = owner.split("\ndef publish(", 1)[1].split("\ndef ", 1)[0]
    assert 'if not all_ten_pass(row.get("gates")):' in publish
    assert "recovered=recovery.get(\"rows\")" in owner


def test_universe_job_fills_missing_ladder_instead_of_rewalking_it() -> None:
    wrapper = (DESK.parents[1] / "ops" / "run_universe.cmd").read_text("utf-8")
    assert "scripts\\refresh_tail.py" in wrapper
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
    # The terminal lease belongs only to the missing-parquet broker fallback. Holding it around
    # main() starves the chart refresher for most of every hour and blocks forward evidence.
    live_frame = gauntlet.split("def _live_frame", 1)[1].split("\ndef ", 1)[0]
    cli = gauntlet.split("def _cli_main", 1)[1]
    assert 'exclusive_job("fusion_terminal_research_lane"' in live_frame
    assert 'exclusive_job("fusion_terminal_research_lane"' not in cli
    installer = _text("scripts/Install-QuantWindows.ps1")
    assert "(Get-Date).Date.AddMinutes(30)" in installer
