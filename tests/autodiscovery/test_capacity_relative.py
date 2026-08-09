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
    """§42: being ALLOWED into the small-capacity niche is not the same as hunting it."""

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

    def _run(self, tmp_path, monkeypatch, caps: list[float]) -> list[tuple[str, str]]:
        m, store = self._store(tmp_path, caps)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        db = tmp_path / "sor_research.sqlite"
        db.touch()
        monkeypatch.setattr(m, "_CANDIDATE_DB", db)
        monkeypatch.setattr("libs.autodiscovery.memory.CandidateStore", store)
        defects: list[tuple[str, str]] = []
        m.check_capacity_hunt(defects)
        return defects

    def test_fund_shaped_hunt_fires(self, tmp_path, monkeypatch) -> None:
        # every candidate needs eight figures -> the desk is competing where it has no advantage
        defects = self._run(tmp_path, monkeypatch, [5e7, 8e7, 1e8, 2e8, 9e7, 1.5e8])
        assert defects and defects[0][0] == "capacity-hunt-fund-shaped"
        assert "NO advantage" in defects[0][1]

    def test_niche_hunt_is_silent(self, tmp_path, monkeypatch) -> None:
        # both bands represented: 4 niche, 4 that can absorb size
        defects = self._run(tmp_path, monkeypatch,
                            [50e3, 120e3, 400e3, 80e3, 9e7, 2e7, 5e7, 3e8])
        assert defects == []

    def test_a_funnel_starved_of_niche_fires(self, tmp_path, monkeypatch) -> None:
        caps = [50e3] + [5e7] * 7                # 1/8 niche, below the 25% both bands must hold
        ids = [d[0] for d in self._run(tmp_path, monkeypatch, caps)]
        assert "capacity-hunt-fund-shaped" in ids

    def test_a_funnel_starved_of_LARGE_fires_too(self, tmp_path, monkeypatch) -> None:
        # SYMMETRY: hunting only small is the same bias pointed the other way, and it leaves no
        # successor inventory for the day the book outgrows the small edges
        caps = [50e3, 80e3, 120e3, 200e3, 400e3, 900e3, 2e6, 5e7]   # 1/8 large
        ids = [d[0] for d in self._run(tmp_path, monkeypatch, caps)]
        assert "capacity-hunt-niche-only" in ids

    def test_both_bands_present_is_silent(self, tmp_path, monkeypatch) -> None:
        caps = [50e3, 80e3, 200e3, 400e3, 5e7, 6e7, 7e7, 8e7]   # 50/50
        ids = [d[0] for d in self._run(tmp_path, monkeypatch, caps)]
        assert "capacity-hunt-fund-shaped" not in ids
        assert "capacity-hunt-niche-only" not in ids

    def test_unfillable_candidates_are_their_own_defect(self, tmp_path, monkeypatch) -> None:
        # small is the advantage; too small to fill is not -- and it must not be scored as niche
        caps = [500.0, 1_000.0, 50e3, 120e3, 400e3, 900e3]
        ids = [d[0] for d in self._run(tmp_path, monkeypatch, caps)]
        assert "capacity-hunt-unfillable" in ids

    def test_too_few_candidates_is_not_judged(self, tmp_path, monkeypatch) -> None:
        m, store = self._store(tmp_path, [1e7, 2e7])
        monkeypatch.setattr(m, "ROOT", tmp_path)
        db = tmp_path / "sor_research.sqlite"
        db.touch()
        monkeypatch.setattr(m, "_CANDIDATE_DB", db)
        monkeypatch.setattr("libs.autodiscovery.memory.CandidateStore", store)
        defects: list[tuple[str, str]] = []
        m.check_capacity_hunt(defects)
        assert defects == []
