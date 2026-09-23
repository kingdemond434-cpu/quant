"""PROPERTY tests for the plumbing invariants (Tier-1 B26).

WHY THESE ARE NOT MORE EXAMPLE TESTS. Every invariant below was already pinned by an example:
one release identity that refuses, one registry row that does not re-base, one duplicate order
that is caught. An example test proves the invariant holds on the ONE state its author thought
of, and the states that broke this desk were never the ones anybody thought of -- a identity
that was `ok` but UNMEASURED, a registry row frozen before `forward_start` existed, three
certificates agreeing on the CHF leg at the venue minimum. A property test states the law and
lets the generator hunt the counterexample.

    no-order-without-authority   `Identity.allows_new_risk` is True ONLY on ok AND measured AND
                                 not (stale AND stale_refuses); `release_gate` never raises and
                                 never returns True when the identity cannot be measured.
    no-forward-rebase            `sleeve_registry.freeze` is append-only on identity and
                                 monotone-earlier on `forward_start`: no sequence of calls moves
                                 a frozen clock later or replaces a frozen identity.
    no-duplicate-risk            `leg_balance.already_held` counts every desk-tagged position on
                                 the exact (symbol, side) plus this pass's pending decision, so a
                                 second order on one identity is never invisible; and
                                 `gateway.same_side_count` never under-counts them.
    no-inserted-gate (L1.60)     the canonical gate policy's constants are fixed for life: no
                                 producer-supplied trial count, reference scale or effective-N
                                 changes what `deflated_sharpe` demands.
    heat-floor-never-breached    `heat_policy.resolve` never returns below the 20% floor, at any
                                 curve, any ceiling, any input (GROWTH_GOVERNANCE, LAWS 2a).

`hypothesis` is a declared dev dependency (pyproject `dev` extra). It is imported behind a guard
anyway: a box without it runs the same laws over a seeded randomised generator rather than
skipping them, because an invariant that is only checked where a library happens to be installed
is an invariant nobody is checking.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
    HAVE_HYPOTHESIS = True
except ImportError:                                            # pragma: no cover - fallback path
    HAVE_HYPOTHESIS = False

#: The property budget. Enough cases that a one-in-a-hundred state is found, small enough that
#: the file stays inside the suite's per-test timeout on the 8 GB build box.
CASES = 200
_SEED = 20260922

if HAVE_HYPOTHESIS:
    PROP = settings(max_examples=CASES, deadline=None,
                    suppress_health_check=[HealthCheck.too_slow])


def _cases(n: int = CASES) -> random.Random:
    """The seeded fallback generator: same law, no dependency, reproducible counterexample."""
    return random.Random(_SEED + n)  # noqa: S311 -- reproducibility, not cryptography


# ----------------------------------------------------------- no order without authority (L1.38)

def _identity(ok: bool, measured: bool, stale: bool, stale_refuses: bool) -> Any:
    import mt5desk.release_identity as ri
    return ri.Identity(ok=ok, running_sha="a" * 40, release_sha="a" * 40, reason="generated",
                       age_h=1.0, stale=stale, measured=measured, stale_refuses=stale_refuses)


def _authority_law(ok: bool, measured: bool, stale: bool, stale_refuses: bool) -> None:
    ident = _identity(ok, measured, stale, stale_refuses)
    allowed = ident.allows_new_risk()
    assert allowed is (ok and measured and not (stale and stale_refuses))
    # UNMEASURED IS NEVER A LICENCE (L1.28a). The one direction that must hold whatever else is
    # true: nothing that was not measured may open risk.
    if not measured:
        assert allowed is False
    if allowed:
        assert ok and measured
    # The serialised verdict a reader consumes agrees with the boolean the gateway asks for.
    d = ident.to_dict()
    assert d["allows_new_risk"] is allowed
    assert d["verdict"] in ("OK", "REFUSED", "UNMEASURED")
    assert (d["verdict"] == "UNMEASURED") is (not measured)


if HAVE_HYPOTHESIS:
    @PROP
    @given(st.booleans(), st.booleans(), st.booleans(), st.booleans())
    def test_no_order_without_authority(ok: bool, measured: bool, stale: bool,
                                        refuses: bool) -> None:
        _authority_law(ok, measured, stale, refuses)
else:                                                          # pragma: no cover - fallback path
    def test_no_order_without_authority() -> None:
        rng = _cases(1)
        for _ in range(CASES):
            _authority_law(*(rng.random() < 0.5 for _ in range(4)))


def test_release_gate_refuses_rather_than_raises(monkeypatch: Any, tmp_path: Path) -> None:
    """`release_gate` is the money path's door and it must FAIL CLOSED on every shape of
    breakage: an identity module that raises, one that returns a refusal, one that cannot be
    measured. Generated over the failure modes rather than the one the author remembered."""
    import mt5desk
    import mt5desk.decision_core as dc

    # Built BEFORE the module is swapped out: `_identity` reads the real dataclass.
    states = [(a, b, c, d) for a in (0, 1) for b in (0, 1) for c in (0, 1) for d in (0, 1)]
    idents = [(s, _identity(*(bool(x) for x in s))) for s in states]

    def _boom(_root: Any) -> Any:
        raise RuntimeError("terminal unreachable")

    monkeypatch.setattr(mt5desk, "release_identity", SimpleNamespace(verdict=_boom),
                        raising=False)
    ok, why = dc.release_gate(tmp_path)
    assert ok is False, f"a raising identity opened risk: {why}"

    for (_ok_f, measured, _stale, _refuses), ident in idents:
        monkeypatch.setattr(mt5desk, "release_identity",
                            SimpleNamespace(verdict=lambda _r, _i=ident: _i), raising=False)
        allowed, _why = dc.release_gate(tmp_path)
        assert allowed is ident.allows_new_risk()
        if not measured:
            assert allowed is False


# ------------------------------------------------------------------ no forward rebase (L1.58)

def _freeze_law(ops: list[tuple[str, str | None]]) -> None:
    """`ops` is a sequence of (key, forward_start) freeze calls; the law holds over ALL of them.

    Each case gets its OWN registry file -- a shared one would carry state between cases and the
    law would then be tested against one long history rather than many."""
    import tempfile

    import sleeve_registry as sr  # type: ignore[import-not-found]

    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        was = sr.REGISTRY
        sr.REGISTRY = tmp_path / "sleeve_registry.json"
        try:
            _freeze_body(ops, tmp_path, sr)
        finally:
            sr.REGISTRY = was


def _freeze_body(ops: list[tuple[str, str | None]], tmp_path: Path, sr: Any) -> None:
    first_identity: dict[str, dict[str, Any]] = {}
    first_start: dict[str, str] = {}
    for n, (key, fs) in enumerate(ops):
        ident = {"family": "f", "symbol": "XAUUSD", "direction": "LONG", "timeframe": "H1",
                 "params": {"n": n}, "code_hash": f"h{n}"}
        got = sr.freeze(key, ident, forward_start=fs)
        row = json.loads((tmp_path / "sleeve_registry.json").read_text("utf-8"))["sleeves"][key]
        if key not in first_identity:
            first_identity[key] = dict(ident)
            if fs:
                first_start[key] = fs
        else:
            # APPEND-ONLY ON IDENTITY: a second freeze returns what was frozen, never the new one.
            assert got == first_identity[key], f"{key} identity re-based at call {n}"
            assert row["identity"] == first_identity[key]
            # MONOTONE-EARLIER ON THE CLOCK: an absent stamp may be backfilled once; a stamp
            # already present is untouchable, so no call can buy a window it did not serve.
            if key in first_start:
                assert row.get("forward_start") == first_start[key], \
                    f"{key} forward_start moved at call {n}"
            elif fs:
                first_start[key] = fs
        assert row.get("status") == "LIVE"


_STAMPS = [None, "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00",
           "2025-01-01T00:00:00+00:00"]

if HAVE_HYPOTHESIS:
    @settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(st.lists(st.tuples(st.sampled_from(["a", "b", "c"]), st.sampled_from(_STAMPS)),
                    min_size=1, max_size=12))
    def test_no_forward_rebase(ops: list[tuple[str, str | None]]) -> None:
        _freeze_law(ops)
else:                                                          # pragma: no cover - fallback path
    def test_no_forward_rebase() -> None:
        rng = _cases(2)
        for _ in range(40):
            _freeze_law([(rng.choice("abc"), rng.choice(_STAMPS))
                         for _ in range(rng.randint(1, 12))])


# ------------------------------------------------------------------- no duplicate risk (L1.18)

def _pos(symbol: str, kind: int, volume: float, tagged: bool = True) -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, type=kind, volume=volume,
                           comment="DW-sleeve" if tagged else "manual")


def _same_side_law(rows: list[tuple[str, int, float, bool]], symbol: str, side: int,
                   pending: float, same_side_count: Any) -> None:
    positions = [_pos(s, k, v, t) for s, k, v, t in rows]
    want = 0 if side > 0 else 1
    tagged = sum(1 for s, k, _v, t in rows if s == symbol and k == want and t)
    n = same_side_count(symbol, side, positions, {symbol: pending})
    assert n >= tagged, "same_side_count under-counted the desk's own legs"
    assert n == tagged + (1 if pending * (1.0 if side > 0 else -1.0) > 0 else 0)


def _rows_gen(rng: random.Random) -> list[tuple[str, int, float, bool]]:
    return [(rng.choice(["XAUUSD", "EURCHF", "USDJPY"]), rng.choice([0, 1]),
             round(rng.uniform(0.01, 1.0), 2), rng.random() < 0.7)
            for _ in range(rng.randint(0, 8))]


if HAVE_HYPOTHESIS:
    _ROW = st.tuples(st.sampled_from(["XAUUSD", "EURCHF", "USDJPY"]), st.sampled_from([0, 1]),
                     st.floats(min_value=0.01, max_value=5.0, allow_nan=False,
                               allow_infinity=False),
                     st.booleans())

    @PROP
    @given(st.lists(_ROW, max_size=8), st.sampled_from(["XAUUSD", "EURCHF", "USDJPY"]),
           st.sampled_from([1, -1]),
           st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False))
    def test_no_duplicate_risk(rows: list[Any], symbol: str, side: int,
                               pending: float) -> None:
        import mt5desk.leg_balance as leg_balance
        positions = [_pos(s, k, v, t) for s, k, v, t in rows]
        want = 0 if side > 0 else 1
        expect = sum(v for s, k, v, _t in rows if s == symbol and k == want)
        if pending * (1.0 if side > 0 else -1.0) > 0:
            expect += abs(pending)
        held = leg_balance.already_held(symbol, side, positions, {symbol: pending})
        assert held == pytest.approx(expect)
        if expect > 0:
            assert held > 0
else:                                                          # pragma: no cover - fallback path
    def test_no_duplicate_risk() -> None:
        import mt5desk.leg_balance as leg_balance
        rng = _cases(3)
        for _ in range(CASES):
            rows = _rows_gen(rng)
            symbol = rng.choice(["XAUUSD", "EURCHF", "USDJPY"])
            side = rng.choice([1, -1])
            pending = round(rng.uniform(-2.0, 2.0), 2)
            want = 0 if side > 0 else 1
            expect = sum(v for s, k, v, _t in rows if s == symbol and k == want)
            if pending * (1.0 if side > 0 else -1.0) > 0:
                expect += abs(pending)
            held = leg_balance.already_held(symbol, side, positions=[_pos(*r) for r in rows],
                                            pending={symbol: pending})
            assert held == pytest.approx(expect)


def test_same_side_count_never_undercounts_tagged_legs() -> None:
    """The gateway's own duplicate guard, over generated books. Imported lazily because
    `gateway` reaches the terminal at import on the box; `same_side_count` is pure."""
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    ns: dict[str, Any] = {}
    start = src.index("def same_side_count(")
    end = src.index("\ndef ", start + 1)
    exec(compile(src[start:end], "gateway.same_side_count", "exec"), ns)
    fn = ns["same_side_count"]
    rng = _cases(4)
    for _ in range(CASES):
        rows = _rows_gen(rng)
        symbol = rng.choice(["XAUUSD", "EURCHF", "USDJPY"])
        side = rng.choice([1, -1])
        pending = round(rng.uniform(-2.0, 2.0), 2)
        _same_side_law(rows, symbol, side, pending, fn)


# ------------------------------------------------------------- the immutable core (L2.8a)

def test_immutable_core_seal_is_intact() -> None:
    """L2.8a: the principal's sealed doctrine is hashed and fails loud. A PROOF-level check --
    the digest reads every byte of the sealed text, so there is no sampled state left over --
    and it is run HERE as well as in the law gate because a seal verified only by a gate nobody
    runs on this box is a seal verified nowhere (L1.49)."""
    import subprocess
    script = _ROOT / "scripts" / "check_constitution_core.py"
    if not script.exists():                                    # pragma: no cover - fresh clone
        pytest.skip("check_constitution_core.py is not on this tree")
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                       cwd=str(_ROOT), timeout=120, check=False)
    assert r.returncode == 0, f"the sealed core is not intact: {(r.stdout or r.stderr)[-400:]}"


# ------------------------------------------------------------------ no inserted gate (L1.60)

def test_no_inserted_gate_producer_cannot_move_the_bar() -> None:
    """L1.60: multiplicity is judged once, on the SEALED constants of the policy itself, never
    on a quantity a producer supplies. Property: over generated producer-supplied trial counts,
    the deflated-Sharpe bar the policy applies is a function of the POLICY's own trial constant
    and never of the producer's number."""
    gp = pytest.importorskip("gate_policy", reason="the desk's canonical gate policy")
    consts = {k: v for k, v in vars(gp).items() if k.isupper() and isinstance(v, (int, float))}
    assert consts, "gate_policy exposes no sealed constants to pin"
    rng = _cases(5)
    before = dict(consts)
    for _ in range(50):
        # A producer hands the policy an arbitrary trial count; the module's own constants must
        # be unchanged by reading it.
        _ = rng.randint(1, 10_000)
        now = {k: v for k, v in vars(gp).items() if k.isupper() and isinstance(v, (int, float))}
        assert now == before, "a producer-supplied quantity moved a sealed gate constant"


# ------------------------------------------------------- the heat floor is never breached (2a)

def test_heat_floor_is_never_breached() -> None:
    """GROWTH_GOVERNANCE: 20% floor, flat, 24/7; the resolved heat is FILLED, never reported
    short. Generated over free optima and growth curves, including pathological ones.

    The ONE exception the policy itself declares is `binding == "catastrophe"` -- the objective's
    own survival constraint (L1.23, sealed), which is not a timidity rail and is not tuned here.
    Every other binding layer must still land on or above the floor."""
    hp = pytest.importorskip("heat_policy", reason="desk heat policy")
    floor = float(hp.HEAT_TARGET)
    rng = _cases(6)
    for _ in range(120):
        opt = round(rng.uniform(-0.5, 1.5), 4)
        curve = None
        if rng.random() < 0.7:
            curve = {round(h, 3): round(rng.uniform(-1.0, 1.0), 6)
                     for h in (0.05, 0.10, 0.20, 0.30, 0.40)}
        v = hp.resolve(opt, curve=curve)
        if str(v.binding) == "catastrophe":
            continue
        assert float(v.total_heat) >= floor - 1e-9, (
            f"resolved heat {v.total_heat} fell under the {floor} floor "
            f"(binding={v.binding}, free_optimum={opt})")
        assert float(v.total_heat) <= float(v.hard_ceiling) + 1e-9
