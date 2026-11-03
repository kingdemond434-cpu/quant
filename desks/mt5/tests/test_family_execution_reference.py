import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5desk.decision_core import family_bracket
from mt5desk.family_call import signal_reference_price, spread_blocks_entry


def test_overnight_distances_match_replay_fill_and_absolute_levels():
    time = pd.Timestamp('2026-10-08T00:00:00Z')
    bars = pd.DataFrame({'open': [100.0, 109.0], 'close': [108.0, 111.0]},
                        index=[time, time + pd.Timedelta(hours=1)])
    signal = SimpleNamespace(time=time, stop=90.0, target=120.0)
    reference = signal_reference_price('overnight_gap_decay', bars, signal)
    assert reference == 109.0
    result = family_bracket(signal, 1, 109.0, 109.0, reference)
    assert result[-1] == 'certified'
    assert result[1:4] == (90.0, 120.0, 19.0)
    assert signal_reference_price('range_reversion', bars, signal) == 108.0
    # A later executable quote retains the replay's 19-point risk and 11-point reward.
    moved = family_bracket(signal, 1, 114.0, 114.0, reference)
    assert moved[-1] == 're_anchored'
    assert moved[1:4] == (95.0, 125.0, 19.0)


def test_gap_beyond_certified_levels_does_not_bypass_stale_check():
    time = pd.Timestamp('2026-10-08T00:00:00Z')
    bars = pd.DataFrame({'open': [100.0, 125.0], 'close': [108.0, 126.0]},
                        index=[time, time + pd.Timedelta(hours=1)])
    signal = SimpleNamespace(time=time, stop=90.0, target=120.0)
    reference = signal_reference_price('overnight_gap_decay', bars, signal)
    assert reference == 108.0
    assert family_bracket(signal, 1, 125.0, 126.0, reference)[-1] == 'stale'


@pytest.mark.parametrize('side,stop,target,bid,ask', [
    (1, 90, 120, 119, 121),
    (-1, 120, 90, 89, 91),
])
def test_transient_spread_can_be_rechecked_without_granting_entry(side, stop, target, bid, ask):
    signal = SimpleNamespace(stop=stop, target=target)
    assert spread_blocks_entry(signal, side, bid, ask)
    # Once both sides pass the target, the signal is genuinely stale.
    later = (121, 122) if side > 0 else (88, 89)
    assert not spread_blocks_entry(signal, side, *later)
    # Once both sides pass the stop, it cannot be revived either.
    stopped = (88, 89) if side > 0 else (121, 122)
    assert not spread_blocks_entry(signal, side, *stopped)
    # A recovered quote must pass the existing bracket check independently.
    eligible = (100, 101) if side > 0 else (99, 100)
    assert family_bracket(signal, side, *eligible, 100)[-1] == 'certified'


def test_missing_reference_is_explicitly_unmeasured():
    signal = SimpleNamespace(time=pd.Timestamp('2026-10-08T00:00:00Z'))
    assert signal_reference_price('overnight_gap_decay', pd.DataFrame(), signal) is None
    assert not spread_blocks_entry(SimpleNamespace(stop=90, target=120), 1, float('nan'), 121)
