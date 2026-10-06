"""The three money-path defects the 2026-10-06 acceptance map named, pinned.

1. The order comment truncated to 29 characters, so long sleeve names collided on one tag.
2. A fallback book key (`_vN` stripped, or SYMBOL_family_selector) handed every row that shared
   it the whole fraction the optimiser solved for the key.
3. The heat ceiling was taken from the allocator's artifact with no second reading.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import decision_core as dc  # noqa: E402

_GW = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")

# Five of the collision groups measured on LIVE 2d61e69a1 share their first 27 characters.
_LONG = ["eurgbp_discovered_asia_p_8e61aa", "eurgbp_discovered_asia_p_8e61bb",
         "chfnok_carry_asia_p_98d776f3e210d3e2", "chfnok_carry_asia_p_98d776f3e210d3ff"]


def test_a_name_that_fits_keeps_its_plain_tag() -> None:
    assert dc.sleeve_tag("gold_asia") == "DWgold_asia"
    assert dc.sleeve_tag("gold_asia") == dc.legacy_sleeve_tag("gold_asia")
    name27 = "x" * 27
    assert dc.sleeve_tag(name27) == "DW" + name27


def test_long_names_get_distinct_tags_inside_the_bound() -> None:
    tags = [dc.sleeve_tag(n) for n in _LONG]
    assert len(set(tags)) == len(_LONG)
    assert all(len(t) <= dc.SLEEVE_TAG_MAX for t in tags)
    assert all(t.startswith("DW") and "~" in t for t in tags)
    # The legacy truncation is exactly the collision this replaces.
    assert dc.legacy_sleeve_tag(_LONG[0]) == dc.legacy_sleeve_tag(_LONG[1])


def test_a_tag_resolves_to_the_full_roster_name() -> None:
    for n in _LONG:
        assert dc.sleeve_from_tag(dc.sleeve_tag(n), _LONG) == n
    # A legacy tag one name owns resolves; one two names share falls back to the stem.
    solo = "audnzd_session_breakout_p_1234567"
    assert dc.sleeve_from_tag(dc.legacy_sleeve_tag(solo), [solo, *_LONG]) == solo
    shared = dc.legacy_sleeve_tag(_LONG[0])
    assert dc.sleeve_from_tag(shared, _LONG) == shared[2:]
    assert dc.sleeve_from_tag("", _LONG, "UNATTRIBUTED") == "UNATTRIBUTED"
    assert dc.sleeve_from_tag("[sl 4300.69]", _LONG) == "[sl 4300.69]"


def test_a_position_opened_under_the_legacy_tag_is_still_its_sleeves() -> None:
    tags = dc.sleeve_tags(_LONG[2])
    assert dc.legacy_sleeve_tag(_LONG[2]) in tags and dc.sleeve_tag(_LONG[2]) in tags
    deals = [SimpleNamespace(entry=0, comment=dc.legacy_sleeve_tag(_LONG[2]), ticket=5, time=0)]
    assert dc.bar_already_traded(deals, tags) == (5, "1970-01-01T00:00:00+00:00")
    assert dc.bar_already_traded(deals, dc.sleeve_tag(_LONG[2])) is None
    # A sibling's NEW tag never matches this sleeve.
    deals = [SimpleNamespace(entry=0, comment=dc.sleeve_tag(_LONG[3]), ticket=6, time=0)]
    assert dc.bar_already_traded(deals, tags) is None


def test_every_match_path_reads_owned_tags_and_the_send_path_the_new_tag() -> None:
    assert "return sleeve_tag(name, COMMENT_MAX)" in _GW
    assert "bar_already_traded(_deals, owned_tags(name))" in _GW
    assert 'sleeve_from_tag(comment, [s.get("name") for s in sleeves], "UNATTRIBUTED")' in _GW
    assert '== tag]' not in _GW


def test_a_shared_book_key_splits_the_solved_fraction() -> None:
    joins = [("gold_afternoon_v2", "gold_afternoon"), ("gold_afternoon_v3", "gold_afternoon"),
             ("gold_afternoon_v4", "gold_afternoon"), ("gold_asia", "gold_asia"),
             ("eurchf_x_p_1", "EURCHF_x_s"), ("unpriced", None)]
    shares = dc.book_shares(joins)
    assert shares == {"gold_afternoon_v2": 3, "gold_afternoon_v3": 3, "gold_afternoon_v4": 3,
                      "gold_asia": 1, "eurchf_x_p_1": 1}
    # The exact owner is never divided, and fallback rows never count against it.
    assert dc.book_shares([("gold_asia", "gold_asia"), ("gold_asia_v2", "gold_asia")]) == {
        "gold_asia": 1, "gold_asia_v2": 1}
    assert "_book[_key]) / _n_share" in _GW


def _heat(op: float, growth: float = 0.5, surv: float = 0.5) -> dict:
    return {"envelope": {"operative_ceiling": op, "growth_ceiling": growth,
                         "survival_ceiling": surv, "survival": {"status": "MEASURED"}}}


def _surface(*rows: tuple[float, float]) -> dict:
    return {"rows": [{"heat": h, "p_ruin": p} for h, p in rows]}


def test_a_consistent_artifact_passes_unchanged() -> None:
    cap, why = dc.verify_heat_ceiling(0.4, "m", _heat(0.4),
                                      _surface((0.1, 0), (0.2, 0), (0.4, 0), (0.8, 0.02)))
    assert cap == 0.4 and "consistent" in why
    # No surface: reported, never a smaller book.
    cap, why = dc.verify_heat_ceiling(0.4, "m", _heat(0.4), None)
    assert cap == 0.4 and "UNVERIFIED" in why


def test_the_check_binds_only_on_a_contradiction() -> None:
    cap, why = dc.verify_heat_ceiling(0.4, "m", _heat(0.4, surv=0.3), _surface((0.1, 0)))
    assert cap == 0.3 and "BINDS" in why
    cap, why = dc.verify_heat_ceiling(0.4, "m", _heat(0.4),
                                      _surface((0.1, 0), (0.2, 0), (0.3, 0.01), (0.4, 0)))
    assert cap == 0.2 and "P(ruin)" in why
    cap, _ = dc.verify_heat_ceiling(0.4, "m", _heat(0.4), _surface((0.1, 0.01), (0.2, 0)))
    assert cap == min(0.4, float(dc.MAX_HEAT_CEILING))
    assert 'verify_heat_ceiling(cap, cap_why, heat, art.get("kelly_surface"))' in (
        _DESK / "mt5desk" / "decision_core.py").read_text(encoding="utf-8")
