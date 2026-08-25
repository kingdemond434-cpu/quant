from pathlib import Path

import scripts.run_live_combined as live_combined


def test_retirement_marker_removes_active_views_but_preserves_history(
    tmp_path: Path, monkeypatch,
) -> None:
    marker = tmp_path / "data" / "RECORDERS_OFF"
    active = tmp_path / "web" / "live_combined.json"
    portfolio = tmp_path / "web" / "portfolio.json"
    history = tmp_path / "data" / "live_combined_state.json"
    marker.parent.mkdir(parents=True)
    active.parent.mkdir(parents=True)
    marker.touch()
    for path in (active, portfolio, history):
        path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(live_combined, "_CRYPTO_RETIRED", marker)
    monkeypatch.setattr(live_combined, "_OUT", active)
    monkeypatch.setattr(live_combined, "_PORT", portfolio)

    live_combined.main()

    assert not active.exists()
    assert not portfolio.exists()
    assert history.exists()


def test_shadow_timer_runs_unified_cycle() -> None:
    root = Path(__file__).resolve().parents[2]
    service = (root / "ops" / "qquant-shadow.service").read_text(encoding="utf-8")
    timer = (root / "ops" / "qquant-shadow.timer").read_text(encoding="utf-8")
    assert "research/shadow_cycle.py" in service
    assert "SuccessExitStatus=2" in service
    assert "*:00/30:00" in timer
