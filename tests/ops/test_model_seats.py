"""The two-seat model routing (principal 2026-08-12) and the upgrade that must not undo it."""
from __future__ import annotations

from libs.ops.model_chain import (
    DEFAULT_CHAIN,
    MINER_CHAIN,
    SEAT_DEFAULT,
    SEAT_MINER,
    chain_for,
    promote_into,
    read_chain,
    render_chain,
    seat_for,
)


# ------------------------------------------------------------------ the policy itself
def test_default_seat_is_opus_and_miner_seat_is_fable() -> None:
    assert DEFAULT_CHAIN[0] == "claude-opus-5"
    assert MINER_CHAIN[0] == "claude-fable-5"


def test_every_non_miner_organ_lands_on_opus() -> None:
    for organ in ("cro", "capability_hunt", "recommendation_worker", "deep_sweep",
                  "commit_audit", "interactive", ""):
        assert seat_for(organ) == SEAT_DEFAULT, organ
        assert chain_for(organ)[0] == "claude-opus-5", organ


def test_only_chinese_miners_hold_the_fable_seat_by_default() -> None:
    """SUPERSEDED POLICY, UPDATED NOT DELETED. Until 2026-08-12 this asserted that EVERY miner
    landed on Fable -- the pool-splitting argument. The principal's directive inverted it: Opus 5
    is the default for all local Claude work, and Fable is reserved for Chinese miners plus
    miners that have EARNED it on measured downstream value. The surviving invariant is that the
    Fable seat is a small, named, defensible set rather than 'every miner'."""
    for organ in ("cn_sources", "chinese_miner", "bilibili", "juejin", "wechat"):
        assert seat_for(organ) == SEAT_MINER, organ
        assert chain_for(organ)[0] == "claude-fable-5", organ
    for organ in ("frontier", "litminer", "prospector", "dataaxis", "blindrediscovery",
                  "crypto_factory"):
        assert seat_for(organ) == SEAT_DEFAULT, organ
        assert chain_for(organ)[0] == "claude-opus-5", organ


def test_a_non_chinese_miner_reaches_fable_only_when_measured_elite() -> None:
    """Eligibility is DYNAMIC (miner_roi.rank_elite) and never hardcoded -- a static list is how
    'currently best' silently becomes 'chosen once'."""
    assert chain_for("litminer")[0] == "claude-opus-5"
    assert chain_for("litminer", elite={"litminer"})[0] == "claude-fable-5"


def test_regional_suffixes_resolve_to_their_family() -> None:
    """The frontier miner runs as frontier-cn / frontier-kr / ... -- seven labels, one seat, and
    after the inversion that seat is Opus."""
    for region in ("cn", "en", "ru", "kr", "jp", "ar", "br"):
        assert seat_for(f"frontier-{region}") == SEAT_DEFAULT, region


def test_an_unknown_organ_defaults_to_opus_not_fable() -> None:
    """ASYMMETRIC ON PURPOSE. A new organ mis-seated onto Opus costs subscription headroom; one
    mis-seated onto Fable can silently drain the metered pool the miners depend on."""
    assert seat_for("some_organ_invented_next_month") == SEAT_DEFAULT


def test_both_chains_keep_a_walk_down_so_exhaustion_is_never_an_outage() -> None:
    """Either pool draining must be a paged, self-healing transition -- the 07-24 failure was an
    outage precisely because no chain existed beneath the head."""
    for chain in (DEFAULT_CHAIN, MINER_CHAIN):
        assert len(chain) >= 2, chain
        assert len(set(chain)) == len(chain), f"duplicate rung wastes a fallback: {chain}"


def test_the_two_seats_do_not_share_a_head() -> None:
    """If both seats headed the same model the split would be decorative and one pool would still
    be the desk's single point of starvation."""
    assert DEFAULT_CHAIN[0] != MINER_CHAIN[0]


# --------------------------------------------------------- the upgrade that must not reverse it
def test_pinned_promotion_keeps_fable_at_the_miner_head() -> None:
    """THE POINT. run_model_upgrade adopts a newer flagship unattended at 03:00. Prepending it to
    the miner chain would move every miner onto the Max seat with nobody awake to review it."""
    out = promote_into(list(MINER_CHAIN), "claude-opus-6", pin_head=True)
    assert out[0] == "claude-fable-5", out
    assert out[1] == "claude-opus-6", out


def test_unpinned_promotion_still_prepends_for_the_default_seat() -> None:
    out = promote_into(list(DEFAULT_CHAIN), "claude-opus-6", pin_head=False)
    assert out[0] == "claude-opus-6"
    assert out[1] == "claude-opus-5", "the outgoing head must be retained as the fallback"


def test_pinned_promotion_does_not_duplicate_an_existing_rung() -> None:
    out = promote_into(list(MINER_CHAIN), "claude-opus-5", pin_head=True)
    assert out.count("claude-opus-5") == 1, out
    assert out[0] == "claude-fable-5"


# ------------------------------------------------------------------ the generated file
def test_rendered_env_exports_both_seats() -> None:
    txt = render_chain(list(DEFAULT_CHAIN), reason="test", sealed="2026-08-12T00:00:00+00:00")
    assert 'export _BRAIN_MODEL_CHAIN="claude-opus-5' in txt
    assert 'export _MINER_MODEL_CHAIN="claude-fable-5' in txt
    assert 'ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-5}"' in txt


def test_the_live_env_file_matches_the_declared_policy() -> None:
    """The committed ops/model_chain.env is what the VPS actually sources. A module that says
    opus-first while the file still says fable-first is the three-copy drift of 07-30 returning."""
    assert read_chain("_BRAIN_MODEL_CHAIN")[0] == "claude-opus-5"
    assert read_chain("_MINER_MODEL_CHAIN")[0] == "claude-fable-5"


def test_a_missing_chain_file_degrades_to_current_policy_not_the_previous_one() -> None:
    """read_chain's compiled-in floor must track the CURRENT policy. A floor left at the old
    fable-first order would quietly restore last month's routing the moment the file went
    missing -- a downgrade that looks like a default."""
    from libs.ops.model_chain import _FALLBACK_CHAIN
    assert _FALLBACK_CHAIN[0] == "claude-opus-5"
