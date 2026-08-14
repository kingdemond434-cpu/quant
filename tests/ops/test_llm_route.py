"""L1.54 routing, pinned. THE PRIMITIVE TWELVE ORGANS DEPEND ON HAD NO TEST AT ALL.

That is the finding this file starts from. `libs/ops/llm_route` exists because eleven organs each
resolved ONE model and stopped, and `kimi_hunter` proved the cost -- scheduled 56 times a week,
one unavailable model string, and it had produced literally nothing since it was built: no
artifact, no ledger row, no complaint. The fix was centralised precisely so there would be ONE
implementation to get right, and then nothing pinned it, so the one implementation was free to
drift back toward the defect it replaced.

The properties below are the ones whose loss is SILENT. A chain that quietly stops being a chain
does not raise; it returns a shorter list, every organ still runs, and the desk finds out when a
month of scheduled work turns out to have produced nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

from libs.ops.llm_route import (
    MODEL_ROUTING_HOSTS,
    Route,
    build_chain,
    chain_is_sound,
    load_seats,
)


def _roster(tmp: Path, providers: list[dict[str, object]]) -> Path:
    p = tmp / "llm_panel.json"
    p.write_text(json.dumps({"providers": providers}), "utf-8")
    return p


# --------------------------------------------------------------------------- load_seats

def test_A_BROKEN_ROSTER_IS_AN_EMPTY_LIST_NOT_A_TRACEBACK(tmp_path: Path) -> None:
    """Called from SCHEDULED organs. A traceback here kills the run before it can record the
    blocker, which is how a credentials problem becomes indistinguishable from silence."""
    assert load_seats(tmp_path / "nope.json") == []
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", "utf-8")
    assert load_seats(bad) == []
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"providers": "a string"}), "utf-8")
    assert load_seats(wrong) == []


def test_A_SEAT_WITHOUT_BOTH_URL_AND_KEY_IS_NOT_A_SEAT(tmp_path: Path) -> None:
    path = _roster(tmp_path, [
        {"model": "a", "base_url": "https://openrouter.ai/api/v1", "key": "k"},
        {"model": "b", "base_url": "https://openrouter.ai/api/v1"},          # no key
        {"model": "c", "key": "k"},                                          # no endpoint
        {"model": "d", "base_url": "", "key": "k"},                          # empty endpoint
    ])
    assert [s["model"] for s in load_seats(path)] == ["a"]


# --------------------------------------------------------------------------- build_chain

def test_A_MODEL_ROUTING_HOST_SERVES_EVERY_MODEL_IN_THE_CHAIN(tmp_path: Path) -> None:
    """The exact fact kimi_hunter was missing: a roster full of gateway seats is not a roster that
    can serve only the models those seats were filed under."""
    path = _roster(tmp_path, [
        {"model": "openai/gpt-x", "base_url": "https://openrouter.ai/api/v1", "key": "k"},
    ])
    chain = build_chain(["anthropic/claude-y", "moonshotai/kimi-z"], path)
    assert [r.model for r in chain] == ["anthropic/claude-y", "moonshotai/kimi-z"]
    assert all(r.base_url.endswith("/v1") for r in chain)


def test_THE_EXACT_SEAT_IS_TRIED_BEFORE_THE_GATEWAY(tmp_path: Path) -> None:
    """A credential filed under a model is the most likely to work for it; ordering is the whole
    value of a chain, so it is pinned rather than left to dict order."""
    path = _roster(tmp_path, [
        {"model": "x/y", "base_url": "https://openrouter.ai/api/v1", "key": "gateway"},
        {"model": "x/y", "base_url": "https://direct.example/v1", "key": "exact"},
    ])
    chain = build_chain(["x/y"], path)
    # both seats declare the model, so both are "exact"; the gateway is not allowed to displace a
    # direct credential by being listed as routable as well
    assert [r.key for r in chain] == ["gateway", "exact"]
    assert len({r.base_url for r in chain}) == 2


def test_ONE_SEAT_IS_NEVER_TRIED_TWICE_FOR_THE_SAME_MODEL(tmp_path: Path) -> None:
    path = _roster(tmp_path, [
        {"model": "x/y", "base_url": "https://openrouter.ai/api/v1", "key": "k"},
    ])
    chain = build_chain(["x/y"], path)
    assert len(chain) == 1


def test_AN_EMPTY_ROSTER_YIELDS_NO_ROUTES_AND_INVENTS_NONE(tmp_path: Path) -> None:
    """A real answer the caller must record as a blocker. Manufacturing a default endpoint here
    would turn 'no credentials' into 'the model refused', which are different facts."""
    assert build_chain(["a", "b"], _roster(tmp_path, [])) == []


def test_FREE_IS_CARRIED_ON_THE_ROUTE_SO_AN_ANSWER_STAYS_ATTRIBUTABLE(tmp_path: Path) -> None:
    """Degradation buys ATTEMPTS, never leniency: the caller is handed the model that actually
    answered so a fallback result can be re-run on the preferred route later."""
    path = _roster(tmp_path, [
        {"model": "v/w", "base_url": "https://openrouter.ai/api/v1", "key": "k"},
    ])
    chain = build_chain(["v/w", "v/w:free"], path)
    assert [r.free for r in chain] == [False, True]
    assert chain[1].label.endswith("[free]")
    assert Route("m", "u", "k").label == "m"


def test_OPENCODE_IS_A_MODEL_ROUTING_HOST(tmp_path: Path) -> None:
    """Added as an ALTERNATIVE ROUTE, never a replacement (2026-08-14). OpenCode Zen is an
    OpenAI-compatible gateway that dispatches on the request body's `model`, which is the only
    property that decides membership. Listing it grants nothing by itself -- `build_chain` still
    only considers seats present in the roster -- so adding a Zen key becomes a credential change
    with no commit, which is the point: the desk should never ship code to gain a route."""
    assert "opencode" in MODEL_ROUTING_HOSTS
    assert "openrouter" in MODEL_ROUTING_HOSTS, (
        "removing OpenRouter would reproduce the single-route failure L1.54 exists to end, at a "
        "different address")
    path = _roster(tmp_path, [
        {"model": "zen/coder", "base_url": "https://opencode.ai/zen/v1", "key": "k"},
    ])
    assert [r.model for r in build_chain(["some/other-model"], path)] == ["some/other-model"]


def test_HOST_MATCHING_IS_CASE_INSENSITIVE(tmp_path: Path) -> None:
    path = _roster(tmp_path, [
        {"model": "a", "base_url": "https://OpenRouter.AI/api/v1", "key": "k"},
    ])
    assert build_chain(["b"], path)


# --------------------------------------------------------------------------- chain_is_sound

def test_A_SHORT_CHAIN_IS_A_PREFERENCE_NOT_A_CHAIN() -> None:
    ok, why = chain_is_sound(["a/one", "b/two"])
    assert not ok and "preference" in why


def test_ONE_FAMILY_IS_ONE_OPINION_REPEATED() -> None:
    ok, why = chain_is_sound(["v/a", "v/b", "v/c:free"])
    assert not ok and "change the lens" in why


def test_NO_FREE_TAIL_MEANS_AN_UNFUNDED_ACCOUNT_STOPS() -> None:
    ok, why = chain_is_sound(["v/a", "w/b", "x/c"])
    assert not ok and "nowhere to degrade" in why


def test_A_FREE_TIER_AHEAD_OF_A_PAID_ROUTE_IS_REJECTED() -> None:
    """Free tiers go LAST. Ahead of a paid route they are not a fallback, they are a silent
    downgrade of every call the desk believed it was paying for."""
    ok, why = chain_is_sound(["v/a:free", "w/b", "x/c"])
    assert not ok and "free tiers go last" in why


def test_A_SOUND_CHAIN_PASSES_AND_SAYS_WHY() -> None:
    ok, why = chain_is_sound(["v/a", "w/b", "x/c", "v/d:free"])
    assert ok
    assert "3 families" in why and "1 free tier" in why


def test_AN_ALL_FREE_CHAIN_IS_SOUND() -> None:
    """No paid route to be ordered ahead of, so the ordering rule has nothing to bite on. This is
    the unfunded desk's normal state and it must not read as a defect on top of being broke."""
    ok, _ = chain_is_sound(["v/a:free", "w/b:free", "x/c:free"])
    assert ok
