"""The capacity gate is a RATIO to deployed equity, not a fixed dollar figure.

It was a flat $100,000 floor, which hard-rejected every edge too small to absorb six figures --
i.e. exactly the capacity-bound niche PROSPECTOR_SPEC names as the desk's one structural
advantage. A perfect $20k-capacity listing dislocation failed on `capacity` alone, whatever its
DSR. These lock the corrected behaviour so the flat floor cannot come back by accident."""

from __future__ import annotations

from libs.autodiscovery.validation import capacity_required


class TestCapacityRequired:
    def test_scales_with_the_book(self) -> None:
        small = capacity_required(5_000.0)
        large = capacity_required(500_000.0)
        assert large > small
        assert large / small == 100.0  # linear in deployed equity, as a ratio should be

    def test_small_book_admits_a_small_edge(self) -> None:
        # the regression that mattered: a $20k-capacity edge is FINE on a $5k book (4x headroom)
        assert capacity_required(5_000.0) <= 20_000.0

    def test_the_old_flat_floor_no_longer_binds_a_small_book(self) -> None:
        assert capacity_required(5_000.0) < 1.0e5

    def test_large_book_still_demands_real_capacity(self) -> None:
        # the protection is intact where it matters: never be a big share of your own edge
        assert capacity_required(500_000.0) >= 1.0e6

    def test_absolute_floor_holds_when_book_size_is_unknown(self) -> None:
        # 0.0 means "unknown", and must NOT silently mean "anything goes"
        assert capacity_required(0.0) >= 500.0

    def test_negative_equity_is_treated_as_zero(self) -> None:
        assert capacity_required(-100.0) == capacity_required(0.0)

    def test_headroom_multiple_is_at_least_double(self) -> None:
        # you must never be more than half of your own edge's capacity, at any size
        for eq in (1_000.0, 10_000.0, 1.0e6):
            assert capacity_required(eq) >= 2.0 * eq


class TestCapacityHuntCheck:
    """§39: being ALLOWED into the small-capacity niche is not the same as hunting it."""

    def _store(self, tmp, caps: list[float]):
        import scripts.max_audit as m
        m_caps = list(caps)

        class _C:
            def __init__(self, c: float) -> None:
                self.metrics = type("M", (), {"capacity_usd": c})()

        class _S:
            def __init__(self, *a, **k) -> None: ...
            def all(self):
                return [_C(c) for c in m_caps]

        return m, _S

    def test_fund_shaped_hunt_fires(self, tmp_path, monkeypatch) -> None:
        # every candidate needs seven figures -> the desk is competing where it has no advantage
        m, store = self._store(tmp_path, [5e6, 8e6, 1e7, 2e7, 9e6, 1.5e7])
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr("libs.autodiscovery.memory.CandidateStore", store)
        defects: list[tuple[str, str]] = []
        m.check_capacity_hunt(defects)
        assert defects and defects[0][0] == "capacity-hunt-fund-shaped"
        assert "NO advantage" in defects[0][1]

    def test_niche_hunt_is_silent(self, tmp_path, monkeypatch) -> None:
        m, store = self._store(tmp_path, [20_000, 50_000, 120_000, 80_000, 15_000, 9e6])
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr("libs.autodiscovery.memory.CandidateStore", store)
        defects: list[tuple[str, str]] = []
        m.check_capacity_hunt(defects)
        assert defects == []

    def test_too_few_candidates_is_not_judged(self, tmp_path, monkeypatch) -> None:
        m, store = self._store(tmp_path, [1e7, 2e7])
        monkeypatch.setattr(m, "ROOT", tmp_path)
        monkeypatch.setattr("libs.autodiscovery.memory.CandidateStore", store)
        defects: list[tuple[str, str]] = []
        m.check_capacity_hunt(defects)
        assert defects == []
