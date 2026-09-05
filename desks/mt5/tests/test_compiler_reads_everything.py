"""Nothing a miner writes is unread, and the desk's own anomalies compile rather than queue.

TWO MEASURED LOSSES, ONE AFTER THE OTHER, both in `recent_rows`.

  FIRST   it opened the NEWEST FILE PER SOURCE DIRECTORY. 5,524 discovery artifacts in the
          window, 60 opened -- 98.5% of what the miners produced never reached the compiler.
  SECOND  fixing that left the FILENAME as a filter. `discoveries_*.json` is an inclusion list, so
          a miner naming its output anything else was not rejected, it was never read. Measured
          the same day: 119,902 further rows in 583 artifacts, of which 97,405 were the desk's OWN
          anomaly scanner -- fully structured, with symbol, condition, horizon, n and t.

The principal's rule is the general form: anything a crawler or miner produces that is not already
a direct candidate gets reverse-engineered and sent to the gauntlet. So the read is every JSON
artifact under either intelligence root, at any depth, minus a short list of NAMED operational
state files -- an exclusion list, which fails OPEN against a miner nobody has written yet.

AND THE ANOMALY ROWS ARE NOT PROSE. A `lead_lag` row names both instruments, the lag and the sign;
a `cross_asset_residual` row names the factor and the horizon. Those are complete executable
recipes measured by the desk's own scanner, and they compile. Every other anomaly shape -- a
conditional return with no family hint, which is 96,318 of the 97,405 -- still goes to DEEPENING,
because a mechanism that has not been named is not a candidate and never becomes one by being
counted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

mc = pytest.importorskip("miner_candidate_compiler")

_UNIVERSE = {"EURUSD", "GBPUSD", "XAUUSD", "AUDJPY", "US500"}


def _write(root: Path, rel: str, rows: list[dict]) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"discoveries": rows}), "utf-8")
    return path


@pytest.fixture
def roots(tmp_path, monkeypatch):
    """Two intelligence roots the compiler will read, isolated from the real ones."""
    a, b = tmp_path / "desk_intel", tmp_path / "repo_intel"
    a.mkdir(); b.mkdir()
    monkeypatch.setattr(mc, "INTEL_ROOTS", (a, b))
    return a, b


class TestEveryArtifactIsRead:
    def test_a_miner_that_does_not_say_discoveries_in_its_filename_is_read(self, roots) -> None:
        """THE SECOND LOSS, directly. `signals_*`, `articles_*`, `forum_*`, `codebase_*` and
        `anomalies_*` were 1,403 artifacts the compiler never opened -- not rejected, unread."""
        a, _ = roots
        for name in ("mql5/signals_20260902.json", "mql5/forum_20260902.json",
                     "world/articles_20260902.json", "prospector/codebase_cat.json",
                     "anomalies/anomalies_20260904.json"):
            _write(a, name, [{"title": f"row from {name}", "symbol": "EURUSD"}])
        rows = mc.recent_rows(mc.datetime.now(tz=mc.UTC))
        titles = {str(r.get("title")) for _, r in rows}
        assert len(titles) == 5, f"only {len(titles)} of 5 artifact shapes were read: {titles}"

    def test_every_file_in_a_directory_is_read_not_only_the_newest(self, roots) -> None:
        """THE FIRST LOSS. A miner writing one artifact per run kept only its last run."""
        a, _ = roots
        for i in range(6):
            _write(a, f"src/discoveries_{i}.json", [{"title": f"run {i}", "symbol": "EURUSD"}])
        titles = {str(r.get("title")) for _, r in mc.recent_rows(mc.datetime.now(tz=mc.UTC))}
        assert titles == {f"run {i}" for i in range(6)}

    def test_artifacts_nested_deeper_than_one_directory_are_read(self, roots) -> None:
        a, _ = roots
        _write(a, "region/asia/jp/discoveries_1.json", [{"title": "deep", "symbol": "EURUSD"}])
        assert any(r.get("title") == "deep" for _, r in mc.recent_rows(mc.datetime.now(tz=mc.UTC)))

    def test_both_intelligence_roots_are_read(self, roots) -> None:
        a, b = roots
        _write(a, "x/discoveries_1.json", [{"title": "desk side", "symbol": "EURUSD"}])
        _write(b, "y/videos_1.json", [{"title": "repo side", "symbol": "EURUSD"}])
        titles = {str(r.get("title")) for _, r in mc.recent_rows(mc.datetime.now(tz=mc.UTC))}
        assert titles == {"desk side", "repo side"}

    def test_a_row_repeated_across_files_is_carried_once(self, roots) -> None:
        """The dedup is what makes reading everything safe, and it already existed -- the old
        behaviour was not protecting against duplicates, it was discarding distinct rows."""
        a, _ = roots
        row = {"title": "same row", "symbol": "EURUSD"}
        for i in range(20):
            _write(a, f"src/discoveries_{i}.json", [dict(row)])
        assert len(mc.recent_rows(mc.datetime.now(tz=mc.UTC))) == 1

    def test_a_file_older_than_the_window_is_not_read(self, roots) -> None:
        import os
        a, _ = roots
        p = _write(a, "src/discoveries_old.json", [{"title": "stale", "symbol": "EURUSD"}])
        old = (mc.datetime.now(tz=mc.UTC) - mc.timedelta(days=mc.WINDOW_DAYS + 2)).timestamp()
        os.utime(p, (old, old))
        assert mc.recent_rows(mc.datetime.now(tz=mc.UTC)) == []


class TestOperationalStateIsNotEvidence:
    def test_a_named_cursor_at_the_root_is_skipped(self, roots) -> None:
        """A miner's own bookkeeping is not a lead. Reading it would spend a seat call on a
        coverage registry."""
        a, _ = roots
        _write(a, "anomaly_cursor.json", [{"title": "cursor row", "symbol": "EURUSD"}])
        assert mc.recent_rows(mc.datetime.now(tz=mc.UTC)) == []

    def test_the_same_name_inside_a_source_directory_is_read(self, roots) -> None:
        """MATCHED AT THE ROOT ONLY. These names are generic enough that a per-source file called
        `coverage_registry.json` would plausibly hold rows, and an exclusion that swallowed a
        source would be the very failure this widening exists to end."""
        a, _ = roots
        _write(a, "somesource/coverage_registry.json", [{"title": "real", "symbol": "EURUSD"}])
        assert any(r.get("title") == "real" for _, r in mc.recent_rows(mc.datetime.now(tz=mc.UTC)))

    def test_the_exclusion_list_is_exact_names_not_substrings(self) -> None:
        """A substring rule on "state" or "coverage" would silently eat future miners."""
        assert mc._is_operational_state(Path("frontier_state.json")) is True
        assert mc._is_operational_state(Path("frontier_state_discoveries.json")) is False
        assert mc._is_operational_state(Path("src/frontier_state.json")) is False


class TestTheDesksOwnAnomaliesCompile:
    def _row(self, **over) -> dict:
        base = {"kind": "anomaly", "family_hint": "lead_lag", "symbol": "EURUSD",
                "against": "XAUUSD", "condition": "lead_lag_XAUUSD_lag1", "horizon": 1,
                "n": 44237, "corr": 0.18, "t_stat": 38.6, "mechanism_status": "UNNAMED"}
        base.update(over)
        return base

    def test_a_lead_lag_anomaly_becomes_an_exact_recipe(self) -> None:
        got, disp = mc.compile_row("anomalies", self._row(), _UNIVERSE)
        assert disp == "STRUCTURED_LEAD_LAG"
        (c,) = got
        assert c["family"] == "lead_lag"
        assert c["params"] == {"driver_symbol": "XAUUSD", "lag": 1, "direction": "same"}

    def test_a_negative_correlation_is_carried_as_the_opposite_direction(self) -> None:
        (c,), _ = mc.compile_row("anomalies", self._row(corr=-0.28), _UNIVERSE)
        assert c["params"]["direction"] == "opposite"

    def test_the_lag_is_read_from_the_condition_when_the_horizon_is_absent(self) -> None:
        (c,), _ = mc.compile_row("anomalies", self._row(horizon=None,
                                                        condition="lead_lag_XAUUSD_lag6"),
                                 _UNIVERSE)
        assert c["params"]["lag"] == 6

    def test_a_lead_lag_row_with_no_lag_anywhere_goes_to_deepening(self) -> None:
        """A lead-lag recipe without a lag is the SHAPE of a rule, not a rule."""
        got, disp = mc.compile_row("anomalies", self._row(horizon=None, condition="lead_lag_X"),
                                   _UNIVERSE)
        assert got == [] and disp == "NEEDS_EXACT_RULE_EXTRACTION"

    def test_a_driver_outside_the_live_universe_is_not_compiled(self) -> None:
        """The recipe would name bars the box cannot serve, which is a candidate that can never
        be tested rather than one that fails."""
        got, disp = mc.compile_row("anomalies", self._row(against="NOTATRADEABLETHING"), _UNIVERSE)
        assert got == [] and disp == "NEEDS_EXACT_RULE_EXTRACTION"

    def test_a_cross_asset_residual_anomaly_carries_its_factor_and_horizon(self) -> None:
        row = self._row(family_hint="cross_asset_residual", condition="resid_rich_vs_XAUUSD",
                        horizon=6, corr=None)
        (c,), disp = mc.compile_row("anomalies", row, _UNIVERSE)
        assert disp == "STRUCTURED_CROSS_ASSET_RESIDUAL"
        assert c["family"] == "cross_asset_residual"
        assert c["params"] == {"factor_symbols": ["XAUUSD"], "ttl_bars": 6}

    def test_the_residual_recipe_does_not_restate_the_familys_own_defaults(self) -> None:
        """The scanner measures on the family's defaults (240-bar lookback, 2sd). Freezing those
        onto every candidate would fork the two the day the family's defaults change."""
        row = self._row(family_hint="cross_asset_residual", horizon=6)
        (c,), _ = mc.compile_row("anomalies", row, _UNIVERSE)
        assert "lookback" not in c["params"] and "entry_z" not in c["params"]

    def test_an_anomaly_with_no_family_hint_still_goes_to_deepening(self) -> None:
        """96,318 of the 97,405 rows. An UNNAMED mechanism is not a candidate, and this widening
        does not change that -- deepening is where a mechanism gets named."""
        row = {"kind": "anomaly", "symbol": "EURUSD", "condition": "hour_q0-0.05", "horizon": 1,
               "mean_bp": 6.6, "t_stat": 27.5, "mechanism_status": "UNNAMED"}
        got, disp = mc.compile_row("anomalies", row, _UNIVERSE)
        assert got == [] and disp == "NEEDS_EXACT_RULE_EXTRACTION"

    def test_the_compiled_family_is_one_the_executor_can_actually_run(self) -> None:
        """A candidate for a family with no constructor is an orphan by construction. Both new
        paths are checked here rather than assumed, because compiling to an unrunnable name is a
        conversion number that buys nothing."""
        ex = pytest.importorskip("mt5desk.executables")
        for fam in ("lead_lag", "cross_asset_residual"):
            assert ex.resolve_family(fam) is not None, fam
            assert ex.executor_gap(fam) is None, fam


class TestNothingIsDroppedSilently:
    def test_every_row_is_either_a_candidate_or_a_deepening_task(self, roots) -> None:
        """The compiler's own contract: no row silently dies. A row that produces no candidate
        must appear in the deepening queue, which is what the reverse-engineering worker drains."""
        a, _ = roots
        _write(a, "mix/discoveries_1.json", [
            {"title": "prose lead", "url": "http://x"},                       # no symbol
            {"title": "symbol only", "symbol": "EURUSD"},                     # no rule
            {"kind": "anomaly", "family_hint": "lead_lag", "symbol": "EURUSD",
             "against": "XAUUSD", "horizon": 1, "corr": 0.2},                 # a recipe
        ])
        seen = mc.recent_rows(mc.datetime.now(tz=mc.UTC))
        assert len(seen) == 3
        made = deepened = 0
        for src, row in seen:
            produced, _ = mc.compile_row(src, row, _UNIVERSE)
            made += bool(produced)
            deepened += not produced
        assert made + deepened == 3, "a row reached neither the gauntlet nor the deepening queue"
        assert made == 1 and deepened == 2
