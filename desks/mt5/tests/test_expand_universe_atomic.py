"""The actual collector preserves a complete chart if a replacement write fails."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import expand_universe as E


@pytest.mark.parametrize('fail_write', [False, True])
def test_collector_publishes_complete_chart_or_preserves_previous(tmp_path, monkeypatch, fail_write):
    universe = tmp_path / 'universe'
    universe.mkdir()
    dest = universe / 'EURUSD_H1.parquet'
    old = pd.DataFrame({'close': [1.0]}, index=pd.to_datetime(['2026-01-01'], utc=True))
    old.to_parquet(dest)
    original = dest.read_bytes()
    fake = SimpleNamespace(initialize=lambda: True, shutdown=lambda: None,
                           symbols_get=lambda: [SimpleNamespace(name='EURUSD', trade_mode=4)],
                           symbol_select=lambda *a: True, symbol_info=lambda *a: None,
                           TIMEFRAME_H1=1)
    monkeypatch.setitem(sys.modules, 'MetaTrader5', fake)
    monkeypatch.setattr(E, 'UNIVERSE', universe)
    monkeypatch.setattr(E, 'REGISTRY', tmp_path / 'registry.json')
    monkeypatch.setattr(E, 'REPORT', tmp_path / 'report.json')
    monkeypatch.setattr(E, 'TIMEFRAMES', ('H1',))
    monkeypatch.setattr(E, 'MIN_BARS', 1)
    monkeypatch.setattr(E, '_traded_symbols', lambda: set())
    monkeypatch.setattr(E, '_pull_bars', lambda *a: [{'time': 1767225600, 'close': 2.0}])
    write = pd.DataFrame.to_parquet

    def interrupted(frame, path, *args, **kwargs):
        # The reader must still see the old complete chart while the producer writes.
        assert dest.read_bytes() == original
        assert Path(path) != dest
        if fail_write:
            Path(path).write_bytes(b'PAR1-partial')
            raise OSError('injected interrupted write')
        return write(frame, path, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, 'to_parquet', interrupted)
    assert E.main() == 0
    report = json.loads(E.REPORT.read_text())
    if fail_write:
        assert dest.read_bytes() == original
        assert report['failed'][0]['why'] == 'OSError: injected interrupted write'
    else:
        assert pd.read_parquet(dest)['close'].tolist() == [2.0]
        assert report['failed'] == []
    assert list(universe.glob('*.tmp')) == []
