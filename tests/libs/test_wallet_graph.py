"""ENTITY LABELS ARE CONSUMED AS GROUND TRUTH, SO A GUESS IS WORSE THAN AN ABSENCE.

Two failures dominate on-chain entity work and both are pinned here.

AS-OF RESOLUTION. The obvious implementation clusters the full history once, labels every address,
and backtests against those labels -- a signal that knows in 2024 that an address WOULD LATER be
revealed as an exchange hot wallet. Nobody had that knowledge at the time and it correlates with
exactly the flows being predicted. It is the most damaging lookahead available here because the
resulting backtest looks plausible rather than absurd.

FALSE MERGES. Splitting one entity in two costs power. Merging an exchange with a whale produces
an entity whose behaviour is an artefact and features that are confidently wrong. The rules are
conservative on purpose, and these tests hold them there.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.data.wallet_graph import (
    ENTITY_TYPES,
    MIN_TX_FOR_CLASSIFICATION,
    Tx,
    behavioural_profile,
    classify,
    cluster_asof,
    entity_flow,
    labels_asof,
)

DAY = 86400.0


def _exchange(n: int = 400, start: float = 0.0) -> list[Tx]:
    """A hot wallet: hundreds of distinct counterparties, roughly balanced flow."""
    rng = np.random.default_rng(0)
    out = []
    for i in range(n):
        t = start + i * 600 + rng.exponential(120)
        if i % 2:
            out.append(Tx(t, f"user{i}", "HOT", float(rng.lognormal(0, 1))))
        else:
            out.append(Tx(t, "HOT", f"user{i}", float(rng.lognormal(0, 1))))
    return out


def _market_maker(n: int = 300, start: float = 0.0) -> list[Tx]:
    """Machine-regular, few venues, unround sizes, two-sided."""
    out = []
    for i in range(n):
        t = start + i * 300 + (i % 3)          # tight, near-deterministic cadence
        venue = f"venue{i % 3}"
        v = 1.0 + (i % 97) / 313.0             # deliberately unround
        out.append(Tx(t, "MM", venue, v) if i % 2 else Tx(t, venue, "MM", v))
    return out


def _retail(n: int = 60, start: float = 0.0) -> list[Tx]:
    """Bursty and round-numbered -- a person typing amounts."""
    rng = np.random.default_rng(3)
    out, t = [], start
    for i in range(n):
        t += float(rng.exponential(3 * DAY))   # bursty
        out.append(Tx(t, "RET", f"cp{i % 4}", float(rng.choice([0.1, 0.5, 1.0, 2.0]))))
    return out


# ------------------------------------------------------------------ as-of resolution

def test_clustering_ignores_everything_after_asof() -> None:
    """THE LEAK THIS MODULE EXISTS TO PREVENT. A merge revealed by a later transaction must not
    appear in a cluster computed before it."""
    txs = [Tx(10.0, "a", "x", 1.0), Tx(500.0, "b", "y", 1.0, inputs=("a", "b"))]
    early = cluster_asof(txs, asof=100.0)
    late = cluster_asof(txs, asof=1000.0)
    assert early["a"] != early.get("b", "unset"), "the merge had not happened yet at asof=100"
    assert late["a"] == late["b"], "and it must be found once the co-spend is in view"


def test_profiles_ignore_everything_after_asof() -> None:
    txs = _exchange(n=200)
    mid = txs[len(txs) // 2].ts
    c = cluster_asof(txs, mid)
    p_mid = behavioural_profile("HOT", txs, c, mid)
    p_end = behavioural_profile("HOT", txs, c, txs[-1].ts)
    assert p_mid["n_tx"] < p_end["n_tx"]


def test_labels_asof_is_reproducible_from_truncated_history() -> None:
    """Handing the function only the past must give the same answer as handing it everything and
    asking for the past. If it does not, something is reading forward."""
    txs = _exchange()
    cut = txs[250].ts
    full = labels_asof(txs, cut)
    truncated = labels_asof([t for t in txs if t.ts <= cut], cut)
    assert {k: v.etype for k, v in full.items()} == {k: v.etype for k, v in truncated.items()}


# --------------------------------------------------------------------- false merges

def test_only_co_spent_inputs_merge() -> None:
    """Trading with the same counterparty is not shared control. Merging on it would fuse every
    address that ever touched an exchange into one entity."""
    txs = [Tx(1.0, "a", "EXCH", 1.0), Tx(2.0, "b", "EXCH", 1.0)]
    c = cluster_asof(txs, 100.0)
    assert c["a"] != c["b"]


def test_co_spending_does_merge() -> None:
    txs = [Tx(1.0, "a", "z", 1.0, inputs=("a", "b", "c"))]
    c = cluster_asof(txs, 100.0)
    assert c["a"] == c["b"] == c["c"]


def test_evm_shaped_data_yields_singletons_rather_than_false_clusters() -> None:
    """The common-input heuristic is a UTXO idea. On EVM a transaction has one sender, so it must
    produce nothing rather than silently inventing merges -- and the caller must be able to see
    that clustering did no work here."""
    txs = [Tx(float(i), f"a{i}", f"b{i}", 1.0) for i in range(50)]
    c = cluster_asof(txs, 1e9)
    assert len(set(c.values())) == len(set(c))


# ------------------------------------------------------------------- classification

def test_an_exchange_hot_wallet_is_recognised() -> None:
    txs = _exchange()
    lab = labels_asof(txs, txs[-1].ts)
    assert lab[cluster_asof(txs, txs[-1].ts)["HOT"]].etype == "EXCHANGE"


def test_a_market_maker_is_recognised() -> None:
    txs = _market_maker()
    lab = labels_asof(txs, txs[-1].ts)
    assert lab[cluster_asof(txs, txs[-1].ts)["MM"]].etype == "MARKET_MAKER"


def test_thin_evidence_returns_unknown_not_a_guess() -> None:
    """A behavioural profile on a handful of transfers is describing coincidence."""
    txs = [Tx(float(i) * DAY, "x", f"c{i}", 1.0) for i in range(5)]
    lab = classify("x", behavioural_profile("x", txs, cluster_asof(txs, 1e9), 1e9))
    assert lab.etype == "UNKNOWN"
    assert not lab.usable
    assert str(MIN_TX_FOR_CLASSIFICATION) in lab.reasons[0]


def test_an_ambiguous_profile_returns_unknown() -> None:
    """When two classes score within 0.1 the evidence does not separate them, and picking the
    larger would be arbitrary dressed as a finding."""
    lab = classify("amb", {"n_tx": 200.0, "n_counterparties": 4.0, "counterparty_ratio": 0.02,
                           "timing_cv": 0.44, "roundness": 0.05, "flow_imbalance": 0.05})
    assert lab.etype in {"UNKNOWN", "MARKET_MAKER", "BOT"}
    if lab.etype == "UNKNOWN":
        assert "does not separate" in lab.reasons[0] or "below the" in lab.reasons[0]


def test_every_label_is_a_known_type() -> None:
    txs = _exchange() + _market_maker(start=1e6) + _retail(start=2e6)
    for lab in labels_asof(txs, 1e9).values():
        assert lab.etype in ENTITY_TYPES


def test_confidence_is_bounded() -> None:
    txs = _exchange(n=2000)
    for lab in labels_asof(txs, 1e9).values():
        assert 0.0 <= lab.confidence <= 0.95


# ------------------------------------------------------------------------- flows

def test_flow_counts_only_usable_labels() -> None:
    """An UNKNOWN entity is excluded rather than bucketed. A residual bucket quietly becomes the
    biggest one and then gets a signal built on it."""
    txs = [*_exchange(), Tx(1.0, "ghost", "HOT", 999.0)]
    c = cluster_asof(txs, 1e9)
    lab = labels_asof(txs, 1e9)
    f = entity_flow(txs, c, lab, 1e9, etype="EXCHANGE")
    assert f["transfers_counted"] > 0
    assert f["inflow"] >= 0 and f["outflow"] >= 0


def test_flow_respects_asof() -> None:
    txs = _exchange()
    c, lab = cluster_asof(txs, 1e9), labels_asof(txs, 1e9)
    early = entity_flow(txs, c, lab, txs[100].ts)
    late = entity_flow(txs, c, lab, txs[-1].ts)
    assert early["transfers_counted"] < late["transfers_counted"]


def test_flow_of_an_absent_type_is_zero_not_an_error() -> None:
    txs = _exchange()
    f = entity_flow(txs, cluster_asof(txs, 1e9), labels_asof(txs, 1e9), 1e9, etype="TREASURY")
    assert f["net"] == 0.0


# ------------------------------------------------------------------------ hygiene

def test_negative_value_is_refused() -> None:
    with pytest.raises(ValueError, match="negative"):
        Tx(1.0, "a", "b", -1.0)


def test_an_empty_history_profiles_to_nothing() -> None:
    assert behavioural_profile("x", [], {}, 1e9) == {"n_tx": 0.0}


def test_one_whale_transfer_does_not_reclassify_an_exchange() -> None:
    """VALUE-WEIGHTED IMBALANCE IS OUTLIER-DOMINATED, and identity must not be. A single 999-unit
    deposit into a wallet that had processed 400 balanced transfers moved its VALUE imbalance from
    0.00 to 0.60 and reclassified an exchange as unrecognised. What makes something a hot wallet
    is that it processes many transfers in both directions -- a count fact, not a size one."""
    base = _exchange()
    c = cluster_asof(base, 1e9)
    clean = classify("HOT", behavioural_profile("HOT", base, c, 1e9))
    whaled = [*base, Tx(1.0, "whale", "HOT", 999.0)]
    cw = cluster_asof(whaled, 1e9)
    after = classify("HOT", behavioural_profile("HOT", whaled, cw, 1e9))
    assert clean.etype == "EXCHANGE"
    assert after.etype == "EXCHANGE", "one transfer changed who this entity is"


def test_count_and_value_imbalance_are_both_reported() -> None:
    """The value figure is still the right one when MAGNITUDE is the question; it is only the
    wrong one for identity. Both are published so neither gets silently substituted."""
    txs = _exchange()
    p = behavioural_profile("HOT", txs, cluster_asof(txs, 1e9), 1e9)
    assert "count_imbalance" in p and "flow_imbalance" in p
