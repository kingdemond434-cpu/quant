"""The Holm cohort is the desk's only multiplicity control on the only path to capital.

These tests pin the FAIL-SAFE DIRECTION, not just the arithmetic: understating m loosens every
Stage-B bar, which is the phantom-edge direction, so every degenerate case must push m UP (or
flag itself), never down.
"""
from __future__ import annotations

import json

import pytest

from libs.ops import desk_host
from libs.research import slot_registry as sr
from libs.validation.forward_stats import holm_bar


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """A throwaway repo root so tests never read (or write) the live clock artifacts."""
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(sr, "_ROOT", tmp_path)
    # STAMPED AS THE OWNING HOST, because that is what every test using this fixture is about.
    # Since GAP 111 the registry asks `desk_host.is_owning_host` before treating an absent
    # artifact as a measured zero -- a clone cannot tell "clock never born" from "gitignored
    # elsewhere", so it floors the cohort at the cap instead. These tests exercise the
    # MEASUREMENT arithmetic, which only runs on a box that owns its state; without the stamp
    # they would silently re-test the fail-closed floor. The non-owning path is covered by
    # tests/ops/test_desk_host.py.
    desk_host.stamp(tmp_path)
    return tmp_path


def _write(root, rel, payload):
    (root / rel).write_text(json.dumps(payload), "utf-8")


def test_counts_axis_standing_and_derivative_clocks(fake_root):
    _write(fake_root, "data/axis_shadow_state.json",
           {"axes": [{"axis": "kimchi", "verdict": "ACCRUING"},
                     {"axis": "cny", "verdict": "ACCRUING"}]})
    _write(fake_root, "data/cashcarry_shadow_state.json", {"shadow_start": "2026-06-26"})
    _write(fake_root, "data/shadow_sleeves.json", [])

    snap = sr.derive_slots()
    kinds = {s["kind"] for s in snap["slots"]}
    # 2 axis + 1 standing + 2 built-in derivative sleeves
    assert snap["m_concurrent"] == 5
    assert kinds == {"axis", "standing", "derivative"}


def test_retired_axis_leaves_the_cohort(fake_root):
    _write(fake_root, "data/axis_shadow_state.json",
           {"axes": [{"axis": "live", "verdict": "ACCRUING"},
                     {"axis": "dead", "verdict": "RETIRED"}]})
    _write(fake_root, "data/shadow_sleeves.json", [])

    names = {s["name"] for s in sr.derive_slots()["slots"]}
    assert "live" in names
    assert "dead" not in names


def test_unreadable_source_flags_incomplete_rather_than_counting_zero(fake_root):
    """A vanished clock file must never silently shrink m -- that would loosen every bar."""
    _write(fake_root, "data/axis_shadow_state.json",
           {"axes": [{"axis": "a", "verdict": "ACCRUING"}]})
    (fake_root / "data" / "cashcarry_shadow_state.json").write_text("{not json", "utf-8")

    snap = sr.derive_slots()
    assert snap["complete"] is False
    assert "data/cashcarry_shadow_state.json" in snap["unknown_sources"]


def test_registry_extras_are_added_to_the_builtin_sleeves(fake_root):
    _write(fake_root, "data/axis_shadow_state.json", {"axes": []})
    _write(fake_root, "data/shadow_sleeves.json", ["challenger_x"])

    deriv = {s["name"] for s in sr.derive_slots()["slots"] if s["kind"] == "derivative"}
    assert deriv == {"oi_divergence", "ls_contrarian", "challenger_x"}


def test_concurrent_m_never_returns_zero(fake_root):
    """m=0 would make holm_bar divide multiplicity away entirely -- an unbounded bar collapse."""
    _write(fake_root, "data/axis_shadow_state.json", {"axes": []})
    _write(fake_root, "data/shadow_sleeves.json", [])
    for rel in sr._STANDING_STATES.values():
        _write(fake_root, rel, {})
    # only the two built-in derivative sleeves survive; even at zero it must floor at 1
    assert sr.concurrent_m() >= 1


def test_bar_tightens_as_the_cohort_grows(fake_root):
    """The regression this module exists to stop: m=4 gave 2.24 while 12 clocks accrued (2.64)."""
    assert holm_bar(4, rank=1) == pytest.approx(2.24)
    assert holm_bar(12, rank=1) == pytest.approx(2.64)
    assert holm_bar(12, rank=1) > holm_bar(4, rank=1)


def test_over_cap_and_idle_are_both_reported(fake_root):
    _write(fake_root, "data/axis_shadow_state.json",
           {"axes": [{"axis": f"a{i}", "verdict": "ACCRUING"} for i in range(20)]})
    _write(fake_root, "data/shadow_sleeves.json", [])
    over = sr.derive_slots()
    assert over["over_cap"] is True
    assert over["idle_slots"] == 0

    _write(fake_root, "data/axis_shadow_state.json", {"axes": []})
    idle = sr.derive_slots()
    assert idle["over_cap"] is False
    assert idle["idle_slots"] == sr.MAX_FORWARD_SLOTS - idle["m_concurrent"]


def test_dead_clock_cannot_report_itself_as_accruing(fake_root):
    """derive_slots() ASSERTED "ACCRUING" as a string literal for derivative slots and proved
    standing slots only by the existence of a `shadow_start` stub. Measured 2026-08-01: 12 of 12
    slots claimed to accrue while crossasset had been frozen 41 days at day 1 with no scheduler
    line anywhere, and cny_premium sat at 0/40 for nine days (every z20 null). `idle_slots: 0`
    then suppressed the idleness alert. A capability is proven by its ARTIFACT, never a flag."""
    from datetime import UTC, datetime, timedelta
    now = datetime.now(tz=UTC)
    (fake_root / "web").mkdir(exist_ok=True)
    _write(fake_root, "data/axis_shadow_state.json", {"axes": []})
    _write(fake_root, "data/shadow_sleeves.json", [])
    for rel in sr._STANDING_STATES.values():
        _write(fake_root, rel, {"shadow_start": "2026-06-21"})
    # cashcarry advanced today; crossasset is a 41-day-old fossil; crypto_combined accrues but
    # has produced ZERO observations -- a clock can run on schedule and still carry no evidence.
    _write(fake_root, "web/cashcarry_shadow.json",
           {"forward_days": 36, "updated": now.isoformat()})
    _write(fake_root, "web/crossasset_shadow.json",
           {"forward_days": 1, "updated": (now - timedelta(days=41)).isoformat()})
    _write(fake_root, "web/crypto_shadow.json",
           {"forward_days": 0, "updated": now.isoformat()})
    out = sr.derive_slots()
    by = {s["name"]: s for s in out["slots"]}
    assert by["cashcarry"]["evidence"] == "ACCRUING"
    assert by["crossasset"]["evidence"] == "STALLED"
    assert by["crypto_combined"]["evidence"] == "NO-EVIDENCE"   # distinct from STALLED
    assert by["trend_30d"]["evidence"] == "UNMEASURED"          # artifact absent -> never asserted
    assert {r["name"] for r in out["not_accruing"]} == {"crossasset", "crypto_combined"}


def test_stalled_clocks_never_shrink_the_cohort(fake_root):
    """The fail-safe direction, applied to the new measurement: naming a clock dead must NOT drop
    it from m. Retiring a slot is an explicit ledgered decision; doing it implicitly here would
    loosen every Stage-B bar, which is the exact phantom-edge direction this module prevents."""
    from datetime import UTC, datetime, timedelta
    old = (datetime.now(tz=UTC) - timedelta(days=41)).isoformat()
    (fake_root / "web").mkdir(exist_ok=True)
    _write(fake_root, "data/axis_shadow_state.json", {"axes": []})
    _write(fake_root, "data/shadow_sleeves.json", [])
    for rel in sr._STANDING_STATES.values():
        _write(fake_root, rel, {"shadow_start": "2026-06-21"})
    for name, (rel, field) in sr._EVIDENCE.items():
        if name in sr._STANDING_STATES:
            _write(fake_root, rel, {field: 1, "updated": old})
    out = sr.derive_slots()
    assert len(out["not_accruing"]) == len(sr._STANDING_STATES)   # every standing clock is dead
    assert out["m_concurrent"] == len(out["slots"])               # ...and m still counts them all
    assert sr.concurrent_m() == out["m_concurrent"]


# --- ABSENT means "never born" only on the host that owns the artifacts (L1.28a / WS-005) ------

class TestAbsentIsNotTheSameAsGitignored:
    """`data/` is gitignored, so absence on a clone is a fact about the HOST, not the desk.

    The ABSENT/UNKNOWN split is right reasoning on the owning box and false everywhere else, and
    it fails in the LOOSER direction on the desk's most load-bearing integer: six missing birth
    certificates read as six clocks never born, so m shrinks and every Holm bar drops with it.
    """

    def _bare(self, tmp_path, monkeypatch):
        import libs.research.slot_registry as sr
        monkeypatch.setattr(sr, "_ROOT", tmp_path)
        return sr

    def test_A_HOST_WITH_NO_DESK_STATE_REFUSES_TO_CALL_THE_COHORT_MEASURED(
            self, tmp_path, monkeypatch):
        """THE ONE THAT MATTERS. Before this, a fresh clone published complete=True with a small
        m and the L1.6 fence went green against a bar the live desk does not use."""
        sr = self._bare(tmp_path, monkeypatch)
        snap = sr.derive_slots()

        assert snap["complete"] is False, (
            "zero readable sources is a host without desk state, never N measured zeros")
        assert snap["absent_sources"] == [], "absent must convert to unknown, not sit beside it"
        assert len(snap["unknown_sources"]) == 8
        assert sr.cohort_m_for_bar().provenance != "MEASURED"

    def test_the_floored_m_is_TIGHTER_than_the_false_measured_one(self, tmp_path, monkeypatch):
        """The whole point is the direction. If this made the bar looser it would be the defect
        it was written to remove."""
        sr = self._bare(tmp_path, monkeypatch)
        snap = sr.derive_slots()

        assert snap["m_upper"] > snap["m_concurrent"]
        assert sr.cohort_m_for_bar().m >= sr.MAX_FORWARD_SLOTS

    def test_the_two_hardcoded_derivative_rows_are_not_evidence_a_desk_ran(
            self, tmp_path, monkeypatch):
        """The first draft keyed this on `slots` being empty and was silently dead: the built-in
        derivative names are a tuple literal, so a bare clone always yields two rows."""
        sr = self._bare(tmp_path, monkeypatch)
        snap = sr.derive_slots()

        assert snap["m_concurrent"] == 2, "the hardcoded builtins still produce rows"
        assert snap["complete"] is False, "and those rows must not make the cohort look complete"

    def test_A_STAMPED_HOST_KEEPS_THE_ABSENT_SEMANTICS_INTACT(self, tmp_path, monkeypatch):
        """NEGATIVE CONTROL. On the owning host a genuinely un-born clock must still read ABSENT
        -- otherwise this fix would floor the live desk's bar forever on a real measured zero.

        THE PREMISE MOVED, AND THAT IS THE UPGRADE. This used to assert that ONE READABLE SOURCE
        proves the host owns the artifacts. It does not: a clone where a single organ has run
        satisfies exactly that and still holds five missing births it cannot interpret -- the
        residual GAP 111 named and could not close. Ownership is now stated by the running cycle
        and read here, so the control tests what it always meant to test.
        """
        import json
        sr = self._bare(tmp_path, monkeypatch)
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "axis_shadow_state.json").write_text(
            json.dumps({"axes": [{"axis": "a", "verdict": "ACCRUING", "forward_days": 5}]}),
            "utf-8")
        desk_host.stamp(tmp_path)

        snap = sr.derive_slots()
        assert snap["owning_host"] is True
        assert snap["absent_sources"], (
            "on the owning host a file never written IS a clock never born, and stays ABSENT")
        assert snap["complete"] is True
