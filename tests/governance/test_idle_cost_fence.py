"""Tests for the idle-cost fence (L1.51).

THE WIRING TESTS HERE ARE THE POINT. This fence exists because the desk's ONLY idleness law was
fenced by a gate structurally incapable of reporting idleness: `check_utilisation._capital()`
divided a number by itself and printed `SATURATED 100%` on a book holding zero positions. A test
suite that only checked the new fence's arithmetic would leave the original class of defect --
a measurement whose numerator and denominator share a source -- free to come back.

So three things are asserted: the refusal paths (unmeasured must never read OK, L1.28a), the
non-additivity of overlapping clamps, and that the fence stays attached to the constitution, the
build standard and the scheduler.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research import idle_yield as iy  # noqa: E402
from scripts import check_idle_cost as fence  # noqa: E402


def _nav(root: Path, *, equity: float = 10_000.0, deployed: float = 0.0, n: int = 0,
         mode: str = "PAPER (testnet) -- pre-Gate-0") -> None:
    p = root / "data/nav_attestation.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "date": "2026-08-05", "ts": (datetime.now(tz=UTC) - timedelta(days=1)).isoformat(),
        "molded_curve_usd": equity, "equity_marked": equity, "deployed_notional": deployed,
        "n_carries": n, "mode": mode}) + "\n", "utf-8")


def _live(root: Path, *, deployed: float = 0.0, n: int = 0,
          action: str = "none", reasons: list[str] | None = None) -> None:
    p = root / "web/cashcarry_live.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "deployed_notional": deployed, "n_carries": n,
        "risk": {"action": action, "reasons": reasons or [], "dd_from_peak_pct": -17.6}}), "utf-8")


def _yield_inputs(root: Path) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data/hurdle_rate.json").write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(), "risk_free": 0.0034663,
        "days": 33.92}), "utf-8")
    (root / "data/defi_lending.jsonl").write_text(json.dumps({
        "ts": datetime.now(tz=UTC).isoformat(), "symbol": "USDC", "supply_apy": 3.7847,
        "tvl_usd": 162_057_606.0, "project": "aave-v3", "chain": "Ethereum"}) + "\n", "utf-8")


def _live_book(root: Path, *, equity: float = 10_000.0, deployed: float = 0.0,
               action: str = "none", reasons: list[str] | None = None) -> None:
    """A funded, non-paper book with both yield rungs available."""
    _nav(root, equity=equity, deployed=deployed, mode="LIVE")
    _live(root, deployed=deployed, n=1 if deployed else 0, action=action, reasons=reasons)
    _yield_inputs(root)
    (root / "data/LIVE_ENABLE").write_text("1", "utf-8")


class TestRefusalPath:
    """Unmeasured must never read as OK -- the whole reason this fence can be trusted."""

    def test_absent_chain_is_NO_DATA_not_OK(self, tmp_path: Path) -> None:
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "NO-DATA"
        assert rep["usd_per_day"] is None

    def test_paper_book_is_UNMEASURABLE_not_OK(self, tmp_path: Path) -> None:
        _nav(tmp_path, equity=13_151.52)
        _live(tmp_path)
        _yield_inputs(tmp_path)
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "UNMEASURABLE-PAPER-BOOK"
        assert rep["usd_per_day"] is None, "a molded curve produced a real-looking dollar cost"
        assert rep["hypothetical_usd_per_year"] == pytest.approx(490.5, abs=2.0)
        assert any("MOLDED" in b for b in rep["breaches"])

    def test_no_yield_rung_is_NO_FLOOR_not_OK(self, tmp_path: Path) -> None:
        _nav(tmp_path, equity=10_000.0, mode="LIVE")
        _live(tmp_path)
        (tmp_path / "data/LIVE_ENABLE").write_text("1", "utf-8")
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "NO-FLOOR"
        assert rep["usd_per_day"] is None

    def test_paper_outranks_unpriced_clamps(self, tmp_path: Path) -> None:
        # A paper book cannot produce a trustworthy clamp price, so the deeper refusal must win
        # rather than being masked by the shallower one.
        _nav(tmp_path, equity=13_151.52)
        _live(tmp_path, action="pause_opens", reasons=[])
        _yield_inputs(tmp_path)
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "UNMEASURABLE-PAPER-BOOK"


class TestStatuses:
    def test_live_idle_book_is_PRICED(self, tmp_path: Path) -> None:
        _live_book(tmp_path, equity=10_000.0, deployed=0.0)
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "PRICED"
        assert rep["usd_per_year"] == pytest.approx(373.0, abs=2.0)
        assert rep["clamps"] == []

    def test_fully_deployed_book_is_OK(self, tmp_path: Path) -> None:
        _live_book(tmp_path, equity=10_000.0, deployed=9_500.0)
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "OK"

    def test_clamp_without_a_lifting_condition_is_UNPRICED(self, tmp_path: Path) -> None:
        """The anti-timidity breach: a clamp nobody can price is a clamp nobody can argue with."""
        _live_book(tmp_path, equity=10_000.0, deployed=0.0, action="pause_opens", reasons=[])
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "UNPRICED"
        assert any("no lifting condition" in b for b in rep["breaches"])

    def test_clamp_with_a_named_lifting_condition_is_priced(self, tmp_path: Path) -> None:
        _live_book(tmp_path, equity=10_000.0, deployed=0.0, action="pause_opens",
                   reasons=["drawdown -17.6% <= -15%: resumes above -15%"])
        rep = fence.build_report(root=tmp_path)
        assert rep["status"] == "PRICED"
        clamp = next(c for c in rep["clamps"] if c["clamp"] == "risk_pause_opens")
        assert clamp["priced"] is True and clamp["usd_per_day"] is not None
        assert clamp["cumulative_usd"] is not None


class TestClampRegister:
    def test_gate0_fires_when_LIVE_ENABLE_is_absent(self, tmp_path: Path) -> None:
        _nav(tmp_path, equity=10_000.0, mode="LIVE")
        _live(tmp_path)
        _yield_inputs(tmp_path)
        names = [c["clamp"] for c in fence.build_report(root=tmp_path)["clamps"]]
        assert "gate0_not_live" in names

    def test_kill_switch_is_registered_as_a_rail_not_a_gate(self, tmp_path: Path) -> None:
        # L1.23 headroom is LEGITIMATE. It is priced so the desk knows what the protection costs,
        # never so the price can be used to argue it away.
        _live_book(tmp_path)
        (tmp_path / "data/CASHCARRY_KILL").write_text("", "utf-8")
        clamp = next(c for c in fence.build_report(root=tmp_path)["clamps"]
                     if c["clamp"] == "cashcarry_kill")
        assert clamp["kind"] == "rail"

    def test_ramp_holds_only_the_fraction_it_withholds(self, tmp_path: Path) -> None:
        _live_book(tmp_path, equity=10_000.0, deployed=0.0)
        (tmp_path / "data/live_guard.json").write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(),
            "ramp": {"size_fraction": 0.10, "why": "blocked by: a_cost_le_1_25x"}}), "utf-8")
        clamp = next(c for c in fence.build_report(root=tmp_path)["clamps"]
                     if c["clamp"] == "ramp_size_fraction")
        # 90% withheld, not 100%: the ramp permits a tenth of the book.
        assert clamp["holds_usd"] == pytest.approx(9_000.0)

    def test_per_clamp_costs_are_declared_non_additive(self, tmp_path: Path) -> None:
        """Six clamps each blocking the whole book do not cost six times the book."""
        _live_book(tmp_path, equity=10_000.0, deployed=0.0, action="pause_opens",
                   reasons=["resumes above -15%"])
        (tmp_path / "data/CASHCARRY_KILL").write_text("", "utf-8")
        rep = fence.build_report(root=tmp_path)
        assert "multiply-counts" in rep["not_additive"]
        summed = sum(c["usd_per_day"] for c in rep["clamps"] if c["usd_per_day"])
        assert summed > rep["usd_per_day"], "fixture does not exercise overlap"
        # The DESK-level number is computed once from total idle, never by summing clamps.
        assert rep["usd_per_day"] == pytest.approx(10_000.0 * 0.0373 / 365.0, abs=0.01)

    def test_paper_book_leaves_every_clamp_unpriced(self, tmp_path: Path) -> None:
        _nav(tmp_path, equity=13_151.52)
        _live(tmp_path, action="pause_opens", reasons=["x"])
        _yield_inputs(tmp_path)
        rep = fence.build_report(root=tmp_path)
        assert rep["clamps"], "no clamps enumerated"
        assert all(c["usd_per_day"] is None and not c["priced"] for c in rep["clamps"])
        assert all("UNPRICEABLE" in c["note"] for c in rep["clamps"])


class TestCapitalCeilingWeld:
    """THE ORIGINAL DEFECT. `_capital()` passed `live_book_usd()` as numerator and
    `_desk_equity_usd()` as denominator -- and the former is the FIRST RUNG INSIDE the latter, so
    the ratio was identically 1.0 and a zero-position book printed SATURATED at 100%."""

    def test_deployed_and_equity_do_not_share_a_source(self, monkeypatch: pytest.MonkeyPatch
                                                       ) -> None:
        from scripts import check_utilisation as cu
        monkeypatch.setattr(iy, "book_state", lambda *a, **k: iy.BookState(
            equity_usd=10_000.0, deployed_usd=2_000.0, idle_usd=8_000.0, n_positions=2,
            mode="LIVE", is_paper=False, measurable=True, why="fixture", source="fixture"))
        c = cu._capital()
        assert c.limit == 10_000.0 and c.used == 2_000.0
        assert c.utilisation == pytest.approx(0.2), "numerator and denominator share a source"
        assert c.status != "SATURATED"

    def test_zero_positions_never_reads_saturated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts import check_utilisation as cu
        monkeypatch.setattr(iy, "book_state", lambda *a, **k: iy.BookState(
            equity_usd=13_151.52, deployed_usd=0.0, idle_usd=13_151.52, n_positions=0,
            mode="LIVE", is_paper=False, measurable=True, why="fixture", source="fixture"))
        c = cu._capital()
        assert c.utilisation == 0.0 and c.status.startswith("IDLE")

    def test_paper_book_reads_UNMEASURED_not_SATURATED(self, monkeypatch: pytest.MonkeyPatch
                                                       ) -> None:
        from scripts import check_utilisation as cu
        monkeypatch.setattr(iy, "book_state", lambda *a, **k: iy.BookState(
            equity_usd=13_151.52, deployed_usd=0.0, idle_usd=13_151.52, n_positions=0,
            mode="PAPER (testnet) -- pre-Gate-0", is_paper=True, measurable=False,
            why="molded curve", source="fixture"))
        c = cu._capital()
        assert c.status == "UNMEASURED" and c.utilisation == 0.0


class TestWiring:
    """These fail if the fence is quietly detached from the desk's enforcement surfaces."""

    def test_registered_in_the_build_standard(self) -> None:
        from scripts.check_build_standard import _GOVERNED
        assert "check_idle_cost.py" in _GOVERNED

    def test_law_is_mapped_in_the_enforcement_matrix(self) -> None:
        from scripts.build_enforcement_matrix import _FENCE_OWNERS, _MAP
        assert "L1.51" in _MAP
        assert "scripts/check_idle_cost.py" in _MAP["L1.51"]
        assert "libs/research/idle_yield.py" in _MAP["L1.51"]
        assert _FENCE_OWNERS.get("check_idle_cost") == "L1.51"

    def test_law_exists_in_the_constitution(self) -> None:
        text = (_ROOT / "docs/CONSTITUTION.md").read_text("utf-8")
        assert "## L1.51" in text

    def test_law_reaches_the_organs_via_the_doctrine(self) -> None:
        # A law that never reaches an organ cannot change behaviour however well fenced (L1.36).
        assert "L1.51" in (_ROOT / "ops/principal_doctrine.txt").read_text("utf-8")

    def test_scheduled_in_the_crontab_manifest(self) -> None:
        text = (_ROOT / "ops/crontab.manifest").read_text("utf-8")
        assert "check_idle_cost.py" in text

    def test_lawful_entry_guard_is_called(self) -> None:
        # L1.42: every entry point passes the laws. Skipping guard() fails the build standard.
        src = (_ROOT / "scripts/check_idle_cost.py").read_text("utf-8")
        assert "_law_guard()" in src
