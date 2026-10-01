"""The warmer spends its builds on the BACKLOG first, and builds each exact rule ONCE.

Warmth decides what a sweep contains (a cached cell costs the sealed judge no build), so the order
the warmer builds in is the order the backlog drains in. These pin the three capacity properties:
the backlog-first order is a PERMUTATION (nothing dropped, re-judges delayed not lost), the
never-judged test is the sealed sweep's own (seen-cells plus stamped-but-unjudged), and exact
equivalents are served from one build under their OWN cache keys.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "scripts"), str(_DESK / "research"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import warm_gauntlet_cache as W  # noqa: E402


def _fake_G(tmp_path: Path, seen: dict, unjudged: set, refuse: set | None = None):
    cache = tmp_path / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        _seen_cells=lambda: dict(seen), _stamped_but_unjudged=lambda: set(unjudged),
        cell_id=lambda c: f"{c['sym']}.{c['family']}.{sorted((c.get('params') or {}).items())}",
        modifier_preflight=lambda sp: ("refused" if sp.get("sym") in (refuse or set()) else None),
        CACHE_DIR=cache)


def _spec(sym: str, fam: str = "engulfing_reversal", **params) -> dict:
    return {"sym": sym, "family": fam, "params": dict(params), "tf": "H1"}


def test_backlog_first_is_a_permutation_with_the_backlog_at_the_front(tmp_path: Path) -> None:
    specs = [_spec(f"S{i}") for i in range(10)]
    probe = _fake_G(tmp_path / "probe", seen={}, unjudged=set())
    judged = {probe.cell_id(sp) for sp in specs[:6]}
    G = _fake_G(tmp_path, seen=dict.fromkeys(judged, "t"), unjudged=set())
    n = W.never_judged_flags(G, specs)
    assert n == 4
    out = W.backlog_first(specs)
    assert sorted(id(s) for s in out) == sorted(id(s) for s in specs)
    assert [s["sym"] for s in out[:4]] == ["S6", "S7", "S8", "S9"], \
        "never-judged cells first, in their incoming (priority) order"
    assert [s["sym"] for s in out[4:]] == ["S0", "S1", "S2", "S3", "S4", "S5"]


def test_a_stamp_without_stages_is_still_the_backlog(tmp_path: Path) -> None:
    """The sealed sweep's own rule: seen but never actually judged is NEW."""
    sp = _spec("S0")
    cid = _fake_G(tmp_path / "probe", seen={}, unjudged=set()).cell_id(sp)
    G = _fake_G(tmp_path, seen={cid: "t"}, unjudged={cid})
    W.never_judged_flags(G, [sp])
    assert sp["_never_judged"] is True


def test_modifier_refusals_are_counted_and_not_sent(tmp_path: Path) -> None:
    G = _fake_G(tmp_path, seen={}, unjudged=set(), refuse={"BAD"})
    keep, n = W.modifier_refusals(G, [_spec("OK"), _spec("BAD"), _spec("OK2")])
    assert n == 1 and [s["sym"] for s in keep] == ["OK", "OK2"]


def test_equivalents_build_once_and_each_keeps_its_own_key(tmp_path: Path) -> None:
    G = _fake_G(tmp_path, seen={}, unjudged=set())
    a = {**_spec("EURUSD"), "ckey": "ka"}
    b = {**_spec("EURUSD", representation="macro"), "ckey": "kb"}
    c = {**_spec("EURUSD", timeframe="H1"), "ckey": "kc"}
    other = {**_spec("EURUSD", rr=9.9), "ckey": "kd"}
    keyed = [a, b, c, other]
    send, followers, served = W.plan_equivalents(G, keyed, set(), [a, b, c, other])
    assert [s["ckey"] for s in send] == ["ka", "kd"], "one build per exact rule"
    assert followers == {"ka": ["kb", "kc"]} and served == 0
    (G.CACHE_DIR / "ka.npz").write_bytes(b"series")
    assert W.fan_out(G, "ka", followers["ka"]) == 2
    for k in ("kb", "kc"):
        assert (G.CACHE_DIR / f"{k}.npz").read_bytes() == b"series"


def test_a_twin_already_warm_serves_a_cold_member_without_a_build(tmp_path: Path) -> None:
    G = _fake_G(tmp_path, seen={}, unjudged=set())
    a = {**_spec("EURUSD"), "ckey": "ka"}
    b = {**_spec("EURUSD", representation="macro"), "ckey": "kb"}
    (G.CACHE_DIR / "ka.npz").write_bytes(b"warm")
    send, followers, served = W.plan_equivalents(G, [a, b], {"ka"}, [b])
    assert send == [] and followers == {} and served == 1
    assert (G.CACHE_DIR / "kb.npz").read_bytes() == b"warm"


def test_a_group_with_a_held_member_sends_nothing(tmp_path: Path) -> None:
    """Its twins would fail the identical build; the held member retries for the group."""
    G = _fake_G(tmp_path, seen={}, unjudged=set())
    a = {**_spec("EURUSD"), "ckey": "ka"}
    b = {**_spec("EURUSD", representation="macro"), "ckey": "kb"}
    send, followers, served = W.plan_equivalents(G, [a, b], set(), [b], held=[a])
    assert send == [] and followers == {} and served == 0


@pytest.mark.parametrize("missing", [True, False])
def test_fan_out_never_invents_a_series(tmp_path: Path, missing: bool) -> None:
    G = _fake_G(tmp_path, seen={}, unjudged=set())
    if not missing:
        (G.CACHE_DIR / "src.npz").write_bytes(b"s")
    n = W.fan_out(G, "src", ["dst"])
    assert n == (0 if missing else 1)
    assert (G.CACHE_DIR / "dst.npz").exists() is (not missing)
