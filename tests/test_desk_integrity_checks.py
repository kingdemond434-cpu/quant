"""Checks for the seven defects found in the 2026-07-26 adversarial audit.

Each one existed because the desk measured a PROXY instead of the thing its own rule named: the
register's re-rank stamp instead of its rows, `libs/` reachability instead of `scripts/`,
tidiness instead of the book's positions. These lock the corrected measurements, and each guard
is also tested for FIRING -- a check that can only pass is not a check."""

from __future__ import annotations

import json
from datetime import date

import pytest
import scripts.max_audit as m

from libs.research.finding_registry import register_health


def _nav(tmp_path, rows: list[dict]) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/nav_attestation.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")


def _run(monkeypatch, tmp_path, fn) -> list[tuple[str, str]]:
    monkeypatch.setattr(m, "ROOT", tmp_path)
    out: list[tuple[str, str]] = []
    fn(out)
    return out


class TestBookCollapse:
    """A book losing most of itself overnight must be loud. Nothing watched this."""

    def test_carry_collapse_fires(self, tmp_path, monkeypatch) -> None:
        _nav(tmp_path, [
            {"date": "d1", "equity_marked": 14874, "n_carries": 10, "deployed_notional": 4499},
            {"date": "d2", "equity_marked": 14628, "n_carries": 2, "deployed_notional": 3150},
        ])
        assert "book-carries-collapse" in [d[0] for d in _run(
            monkeypatch, tmp_path, m.check_book_collapse)]

    def test_equity_collapse_fires(self, tmp_path, monkeypatch) -> None:
        _nav(tmp_path, [{"date": "d1", "equity_marked": 10_000, "n_carries": 4},
                        {"date": "d2", "equity_marked": 8_000, "n_carries": 4}])
        assert "book-equity-collapse" in [d[0] for d in _run(
            monkeypatch, tmp_path, m.check_book_collapse)]

    def test_realized_pnl_may_only_ratchet_up(self, tmp_path, monkeypatch) -> None:
        # banked P&L falling is an accounting restatement, not a trading loss
        _nav(tmp_path, [{"date": "d1", "equity_marked": 100, "realized_spot_pnl": 636},
                        {"date": "d2", "equity_marked": 100, "realized_spot_pnl": 502}])
        assert "book-realized-pnl-fell" in [d[0] for d in _run(
            monkeypatch, tmp_path, m.check_book_collapse)]

    def test_ordinary_rebalancing_is_silent(self, tmp_path, monkeypatch) -> None:
        # a bar tight enough to fire on rotation gets acknowledged into silence
        _nav(tmp_path, [{"date": "d1", "equity_marked": 10_000, "n_carries": 10,
                         "realized_spot_pnl": 500},
                        {"date": "d2", "equity_marked": 9_700, "n_carries": 8,
                         "realized_spot_pnl": 505}])
        assert _run(monkeypatch, tmp_path, m.check_book_collapse) == []

    def test_one_row_is_not_judged(self, tmp_path, monkeypatch) -> None:
        _nav(tmp_path, [{"date": "d1", "equity_marked": 10_000, "n_carries": 10}])
        assert _run(monkeypatch, tmp_path, m.check_book_collapse) == []

    def test_missing_ledger_is_silent(self, tmp_path, monkeypatch) -> None:
        assert _run(monkeypatch, tmp_path, m.check_book_collapse) == []


class TestRegisterRowStaleness:
    """The rule says 'items stale >7 days'. The check measured the RE-RANK STAMP instead."""

    _HDR = "_Re-ranked 2026-07-26T01:00Z._\n\n"
    _ROW = ("| {id} | **{t}** | mechanism text | plan text | brain | {added} | open |\n")

    def _reg(self, rows: list[tuple[int, str, str]]) -> str:
        return self._HDR + "".join(
            self._ROW.format(id=i, t=t, added=a) for i, t, a in rows)

    def test_a_daily_restamp_no_longer_makes_rows_immortal(self) -> None:
        # THE bug: header re-ranked today, rows 10 days old, check reported clean
        h = register_health(self._reg([(1, "ancient obligation", "07-16")]),
                            today=date(2026, 7, 26))
        assert h.rerank_age_days == 0.0          # header is fresh
        assert h.stale_rows                       # ...and the row is still caught
        assert h.oldest_open_days == 10.0

    def test_a_fresh_row_is_not_stale(self) -> None:
        h = register_health(self._reg([(2, "new item", "07-25")]), today=date(2026, 7, 26))
        assert h.stale_rows == ()

    def test_year_rollover_does_not_exempt_the_oldest_rows(self) -> None:
        # a December row read as THIS year would be -300 days old and silently exempt
        h = register_health(self._reg([(3, "december item", "12-20")]), today=date(2026, 1, 10))
        assert h.oldest_open_days > 0 and h.stale_rows

    def test_the_audit_check_actually_fires(self) -> None:
        out: list[tuple[str, str]] = []
        m.check_gap_register_health(out)
        assert "gap-register-rows-stale" in [d[0] for d in out], \
            "the live register has rows past its own 7-day bar and the check stayed silent"


class TestOrphanScripts:
    """check_orphan_code BFS's FROM scripts/, so it cannot see an unrun script."""

    def _tree(self, tmp_path, scripts: dict[str, str], cycle: list[str]):
        (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
        for n, b in scripts.items():
            (tmp_path / "scripts" / n).write_text(b, "utf-8")
        (tmp_path / "scripts/daily_research_cycle.py").write_text(
            "_STEPS = [" + ", ".join(f'("x", "scripts/{c}", 60)' for c in cycle) + "]\n", "utf-8")
        return tmp_path

    def test_an_unreferenced_script_is_caught(self, tmp_path, monkeypatch) -> None:
        root = self._tree(tmp_path, {"wired.py": "", "lonely.py": ""}, ["wired.py"])
        assert "orphan-scripts" in [d[0] for d in _run(
            monkeypatch, root, m.check_orphan_scripts)]

    def test_a_cycle_script_is_not_an_orphan(self, tmp_path, monkeypatch) -> None:
        root = self._tree(tmp_path, {"wired.py": ""}, ["wired.py"])
        assert _run(monkeypatch, root, m.check_orphan_scripts) == []

    def test_a_script_called_by_another_script_is_reachable(self, tmp_path, monkeypatch) -> None:
        root = self._tree(tmp_path, {"wired.py": "import helper\n", "helper.py": ""},
                          ["wired.py"])
        assert _run(monkeypatch, root, m.check_orphan_scripts) == []

    def test_page_digest_is_reported_not_silently_wired(self) -> None:
        """It calls itself a daily job and is in no cadence -- REPORT that, do not wire it.

        Wiring another account's unverified pager into a daily cadence is how you turn one
        unnoticed script into daily spam, and register #3 is literally "pager delivery
        unverified". The detector's job is to surface it; the decision is the principal's."""
        out: list[tuple[str, str]] = []
        m.check_orphan_scripts(out)
        assert any("page_digest.py" in msg for _, msg in out)

    def test_a_declared_oneshot_is_exempt(self, tmp_path, monkeypatch) -> None:
        root = self._tree(tmp_path, {"wired.py": "", "pull_cme.py": ""}, ["wired.py"])
        assert _run(monkeypatch, root, m.check_orphan_scripts) == []


class TestLawNumbers:
    """Two accounts wrote a §38 and a §39 for different laws hours apart."""

    def test_a_collision_is_caught(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "ops").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs/DIGGING_CHARTER.md").write_text(
            "## 39. AN EXCLUSION SPAWNS A HUNT\ntext\n", "utf-8")
        (tmp_path / "ops/principal_doctrine.txt").write_text(
            "## 39. CAPACITY-BOUND EDGE PRIMACY\ntext\n", "utf-8")
        out = _run(monkeypatch, tmp_path, m.check_law_numbers_unique)
        assert "law-number-collision" in [d[0] for d in out]

    def test_the_live_tree_has_no_collision(self) -> None:
        out: list[tuple[str, str]] = []
        m.check_law_numbers_unique(out)
        assert [d for d in out if d[0] == "law-number-collision"] == []

    def test_the_next_free_number_is_published(self) -> None:
        from pathlib import Path
        out: list[tuple[str, str]] = []
        m.check_law_numbers_unique(out)
        p = Path("docs/research/next_law_number.txt")
        assert p.exists() and int(p.read_text().split()[0]) > 42



class TestMineEvidenceBase:
    """A ratchet calibrated on two observations is superstition with a JSON file."""

    def _rec(self, tmp_path, n: int):
        (tmp_path / "docs/research").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs/research/conversion_record.json").write_text(
            json.dumps({"n_records": n}), "utf-8")
        return tmp_path

    def test_thin_evidence_is_reported(self, tmp_path, monkeypatch) -> None:
        assert "mine-ratchet-thin-evidence" in [d[0] for d in _run(
            monkeypatch, self._rec(tmp_path, 2), m.check_mine_evidence_base)]

    def test_a_real_base_is_silent(self, tmp_path, monkeypatch) -> None:
        assert _run(monkeypatch, self._rec(tmp_path, 25), m.check_mine_evidence_base) == []

    def test_no_record_yet_is_not_a_defect(self, tmp_path, monkeypatch) -> None:
        assert _run(monkeypatch, tmp_path, m.check_mine_evidence_base) == []


class TestVenueTruthBeatsMoldedCurve:
    """`equity_marked` is the last point of a MOLDED CURVE, not an account balance."""

    def test_venue_truth_is_exposed_but_NOT_the_default(self) -> None:
        """`high_water` is a high-water mark, not spot equity.

        Defaulting to it would raise `capacity_required` through any drawdown and start
        rejecting the small edges §42 spent the day admitting -- tightening a live gate on a
        number that cannot be tested from here. Exposed for comparison; not wired."""
        import inspect

        import libs.research.capacity_policy as cp
        assert callable(cp.venue_book_usd)
        assert "venue_book_usd()" not in inspect.getsource(cp.live_book_usd)

    def test_it_falls_back_to_the_nav_chain(self, tmp_path, monkeypatch) -> None:
        from datetime import UTC, datetime

        import libs.research.capacity_policy as cp
        p = tmp_path / "nav.jsonl"
        p.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                 "molded_curve_usd": 1_234.0, "n_carries": 3}) + "\n", "utf-8")
        assert cp.live_book_usd(ledger=p) == 1_234.0

    def test_the_old_field_name_still_reads(self) -> None:
        # the chain is append-only; historical rows carry the old key
        import tempfile
        from datetime import UTC, datetime
        from pathlib import Path

        import libs.research.capacity_policy as cp
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "nav.jsonl"
            p.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                     "equity_marked": 777.0}) + "\n", "utf-8")
            assert cp.live_book_usd(ledger=p) == 777.0

    def test_a_missing_deadman_state_is_none_not_zero(self) -> None:
        # zero would collapse the capacity requirement to the absolute floor
        import libs.research.capacity_policy as cp
        assert cp.venue_book_usd() is None or cp.venue_book_usd() > 0

    def test_nav_writes_the_honest_field_name(self) -> None:
        from pathlib import Path
        src = Path("scripts/run_nav_attest.py").read_text("utf-8")
        assert "molded_curve_usd" in src and "not venue truth" in src


@pytest.mark.parametrize("check", [
    m.check_book_collapse, m.check_mine_evidence_base,
    m.check_orphan_scripts, m.check_law_numbers_unique,
])
def test_every_new_check_is_registered_in_the_sweep(check) -> None:
    """A check the sweep never calls is the orphan problem, one level up.

    Asserts against the CHECKS registry the sweep actually iterates -- not against main()'s
    source, which only mentions the loop variable."""
    assert check in [fn for _, fn in m.CHECKS], \
        f"{check.__name__} is defined but is not in CHECKS, so the sweep never runs it"
