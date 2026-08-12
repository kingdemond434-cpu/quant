"""The auto-upgrader's judgement, tested without a network -- and the single-source fence.

Two things are proven here. First, that `is_upgrade` refuses everything it should refuse: an
unrecognised family, a lower tier, a re-dated snapshot of the same version. An upgrader that is
merely eager would route the desk's whole research programme -- and eventually its position sizing
-- through a model nobody verified.

Second, that the chain is not re-inlined anywhere. It was hardcoded in three files until
2026-07-30; the auto-upgrade only works if there is exactly ONE place a new head can be written.
That is the same defect check_capacity_single_source exists for, so it gets the same treatment.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from libs.ops.model_chain import (
    MAX_CHAIN,
    is_flagship,
    is_upgrade,
    parse_model,
    promote,
    read_chain,
    render_chain,
)

_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.parametrize(("model", "tier", "ver"), [
    ("claude-opus-5", 3, 5.0),
    ("claude-fable-5", 3, 5.0),
    ("claude-opus-4-8", 3, 4.8),
    ("claude-sonnet-5", 2, 5.0),
    ("claude-haiku-4-5-20251001", 1, 4.5),
    ("claude-3-5-sonnet-20241022", 2, 3.5),      # legacy ordering: digits before the family
    ("gpt-5", -1, -1.0),                          # not ours at all
    ("claude-newname-9", -1, 9.0),                # known SHAPE, undeclared family
])
def test_parse_model(model, tier, ver):
    assert parse_model(model) == (tier, ver)


def test_version_ordering_within_a_family():
    """4-8 must sort BELOW 5, not above it. Naive string compare gets this backwards."""
    assert parse_model("claude-opus-4-8")[1] < parse_model("claude-opus-5")[1]
    assert is_upgrade("claude-opus-5", "claude-opus-4-8")
    assert not is_upgrade("claude-opus-4-8", "claude-opus-5")


def test_newer_flagship_is_an_upgrade():
    assert is_upgrade("claude-opus-6", "claude-fable-5")
    assert is_upgrade("claude-fable-6", "claude-fable-5")


def test_unknown_family_is_never_an_upgrade():
    """THE safety property. A model id this code has never seen may not even be a chat model, and
    auto-adopting it would put an unverified model on the path that sizes real positions."""
    assert not is_upgrade("claude-newname-9", "claude-fable-5")
    assert not is_upgrade("gpt-5", "claude-fable-5")
    assert not is_flagship("claude-newname-9")


def test_lower_tier_never_displaces_a_flagship():
    """A brand-new sonnet is newer and still worse for this workload."""
    assert not is_upgrade("claude-sonnet-9", "claude-opus-5")


def test_same_version_is_not_an_upgrade():
    """A re-dated snapshot of the running model must not churn the chain nightly for no gain."""
    assert not is_upgrade("claude-opus-5", "claude-opus-5")


def test_promote_retains_the_outgoing_head():
    """The reversibility property: a promoted model that throttles at 03:00 must fall back to
    exactly what ran yesterday, with nobody awake."""
    chain = ["claude-fable-5", "claude-opus-5", "claude-opus-4-8"]
    out = promote("claude-opus-6", chain)
    assert out[0] == "claude-opus-6"
    assert out[1] == "claude-fable-5", "yesterday's head must sit directly beneath the new one"
    assert "claude-opus-5" in out


def test_promote_is_idempotent_and_bounded():
    chain = ["claude-fable-5", "claude-opus-5", "claude-opus-4-8"]
    once = promote("claude-opus-6", chain)
    assert promote("claude-opus-6", once) == once, "re-promoting must not duplicate"
    deep = promote("claude-opus-8", promote("claude-opus-7", once))
    assert len(deep) <= MAX_CHAIN
    assert len(set(deep)) == len(deep), "no duplicates after repeated promotion"


def test_read_chain_falls_back_rather_than_returning_empty(tmp_path, monkeypatch):
    """A missing or corrupt chain file must be a DOWNGRADE, never an outage: an organ with no
    model at all is strictly worse than an organ on last week's model."""
    import libs.ops.model_chain as mc
    monkeypatch.setattr(mc, "CHAIN_FILE", tmp_path / "absent.env")
    assert mc.read_chain(), "empty chain would leave every organ with no model"
    (tmp_path / "junk.env").write_text("# nothing useful here\n", "utf-8")
    monkeypatch.setattr(mc, "CHAIN_FILE", tmp_path / "junk.env")
    assert mc.read_chain()


def test_render_round_trips(tmp_path, monkeypatch):
    import libs.ops.model_chain as mc
    chain = ["claude-opus-6", "claude-fable-5"]
    f = tmp_path / "model_chain.env"
    f.write_text(render_chain(chain, reason="test", sealed="2026-07-30T00:00:00Z"), "utf-8")
    monkeypatch.setattr(mc, "CHAIN_FILE", f)
    assert mc.read_chain() == chain


# --------------------------------------------------------------------------------------------
# SINGLE-SOURCE FENCE. Not a unit test -- a repo invariant, checked in the test tree because that
# is what runs on every commit.

_CHAIN_LITERAL = re.compile(r'_BRAIN_MODEL_CHAIN\s*=\s*"claude-')

# Each exemption is a place a literal is CORRECT, with the reason. Everything else re-inlining the
# chain would silently pin that organ to yesterday's models after an auto-upgrade.
_ALLOWED = {
    "ops/model_chain.env",        # the generated single source itself
    "libs/ops/model_chain.py",    # owns the compiled-in fallback constant
    "ops/brain_env.sh",           # ${_BRAIN_MODEL_CHAIN:-...} default, only if the file is absent
    "tests/ops/test_model_chain.py",
    # The UPGRADER's own test. Its fixture is definitionally a chain literal: the thing
    # under test is rewrite_text turning an inline ${_BRAIN_MODEL_CHAIN:-...} default into
    # the upgraded one, so a transformer's test must contain what it transforms -- exactly
    # as this file must contain the pattern it greps for. NOT a config pinning an organ to
    # yesterday's models, which is the only thing this fence exists to stop.
    "tests/scripts/test_model_upgrade.py",
    # The SEAT POLICY's own test (principal 2026-08-12, two chains). Same argument as the two
    # entries above and worth stating rather than inheriting: this file asserts WHICH model heads
    # each seat is declared to run -- opus for everything, fable pinned to the miner family -- so
    # it must name them to pin them. That is the opposite of the drift this fence stops. A literal
    # is dangerous in an ORGAN, where it silently keeps running yesterday's model after an
    # upgrade; in a test it is the thing that makes an unattended upgrade detectable at all, and
    # test_pinned_promotion_keeps_fable_at_the_miner_head exists precisely to catch the 03:00
    # auto-upgrader reversing the seat split.
    "tests/ops/test_model_seats.py",
}


def test_model_chain_is_declared_in_exactly_one_place():
    offenders = []
    for pat in ("*.sh", "*.py"):
        for p in list(_ROOT.glob(f"ops/**/{pat}")) + list(_ROOT.glob(f"scripts/**/{pat}")) \
                + list(_ROOT.glob(f"libs/**/{pat}")) + list(_ROOT.glob(f"tests/**/{pat}")):
            rel = p.relative_to(_ROOT).as_posix()
            if rel in _ALLOWED:
                continue
            if _CHAIN_LITERAL.search(p.read_text("utf-8", errors="ignore")):
                offenders.append(rel)
    assert not offenders, (
        f"model chain re-inlined in {offenders}. Source ops/model_chain.env instead -- a literal "
        "here pins this organ to yesterday's models after run_model_upgrade.py adopts a newer one."
    )


def test_the_live_chain_file_exists_and_is_flagship_headed():
    chain = read_chain()
    assert chain, "no live chain"
    assert is_flagship(chain[0]), f"chain head {chain[0]} is not a flagship model"
    assert len(set(chain)) == len(chain), f"duplicate entries in live chain: {chain}"
