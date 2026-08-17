"""Market event tokenization, and the negative controls that make it worth anything.

The hypothesis is whether a self-supervised encoding finds microstructure grammar the hand-built
SMC state machine misses. That question is only answerable if the encoders can FAIL -- so the
load-bearing tests here are the ones asserting they find nothing in noise, and that no encoder
sees the future.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.tokenizer import (  # noqa: E402
    EVENT_TOKENS, encode_bpe, encode_continuous, encode_events, encode_quantile, encode_vq,
    find_motifs, rediscovers_smc)


def _bars(n=3000, seed=7, drift=0.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 2000 + np.cumsum(rng.normal(drift, 2, n))
    h = c + np.abs(rng.normal(0, 3, n))
    l = c - np.abs(rng.normal(0, 3, n))
    return pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": h, "low": l, "close": c}, index=idx)


# ------------------------------------------------------------------ the encoders

def test_every_encoder_returns_one_token_per_bar():
    df = _bars()
    for enc in (encode_events(df), encode_quantile(df), encode_vq(df)):
        assert len(enc) == len(df), f"{enc.name} dropped or invented bars"


def test_the_event_vocabulary_is_the_declared_one():
    enc = encode_events(_bars())
    assert set(enc.tokens) <= set(EVENT_TOKENS), "an undeclared token appeared"


def test_encoders_actually_discriminate():
    """A tokenizer emitting one symbol forever is not a tokenizer."""
    for enc in (encode_events(_bars()), encode_quantile(_bars()), encode_vq(_bars())):
        assert len(set(enc.tokens)) >= 5, f"{enc.name} collapsed to {len(set(enc.tokens))} symbols"


def test_the_continuous_baseline_is_not_discretized():
    """MANDATORY BASELINE. Without it, a tokenizer's win may only be a win over the other
    tokenizers -- which answers a question nobody asked."""
    f = encode_continuous(_bars())
    assert isinstance(f, pd.DataFrame)
    assert f["ret_sigma"].dropna().nunique() > 100, "the baseline got quantized"


# ------------------------------------------------------------------- no lookahead

def test_the_quantile_encoder_uses_trailing_bins_not_whole_sample_ones():
    """Fitting bin edges on the full series labels every bar using the distribution of bars that
    had not happened yet -- the day_states defect wearing a different hat. Truncating the input
    must not change the tokens that remain."""
    df = _bars()
    full = encode_quantile(df)
    half = encode_quantile(df.iloc[:1500])
    assert full.tokens[:1500] == half.tokens, "later bars changed earlier tokens: lookahead"


def test_the_vq_codebook_is_frozen_after_warmup():
    """Fitting the codebook on the whole series lets every token carry information from the end
    of the sample, and the resulting 'discovery' would be guaranteed."""
    df = _bars()
    full = encode_vq(df, warmup=500)
    half = encode_vq(df.iloc[:1500], warmup=500)
    assert full.tokens[:1500] == half.tokens, "the codebook moved with future data"


def test_the_event_encoder_is_causal():
    df = _bars()
    assert encode_events(df).tokens[:1200] == encode_events(df.iloc[:1200]).tokens


# --------------------------------------------------------------- negative controls

def test_no_smc_rediscovery_in_pure_noise():
    """THE CONTROL THAT MAKES A HIT MEAN SOMETHING. If sweep->displacement appears in random
    walks, finding it in real data proves nothing at all."""
    for seed in (1, 2, 3, 4, 5):
        r = rediscovers_smc(encode_events(_bars(seed=seed)))
        assert not r["rediscovered"], f"found SMC structure in noise (seed {seed}): {r['motifs']}"


def test_absence_of_rediscovery_is_not_evidence_against_the_smc_engine():
    r = rediscovers_smc(encode_events(_bars()))
    assert "Absence is not evidence against" in r["why"]


def test_motifs_are_returned_most_frequent_first():
    m = find_motifs(encode_events(_bars()), length=3, top=5)
    assert [c for _, c in m] == sorted([c for _, c in m], reverse=True)


# --------------------------------------------------------------------------- bpe

def test_bpe_merges_recurrent_pairs_into_atoms():
    b = encode_bpe(encode_events(_bars()), n_merges=10)
    assert any("+" in t for t in b.tokens), "no motif was merged"
    assert len(b) < 3000, "merging did not shorten the stream"


def test_bpe_charges_itself_for_every_merge():
    """Each merge is a choice made by looking at the data. A grammar discovered over twenty
    merges is twenty trials, and mt5desk.canonical needs to be told."""
    base = encode_events(_bars())
    b = encode_bpe(base, n_merges=10)
    assert b.n_trials == base.n_trials + b.meta["n_merges"]
    assert b.n_trials > base.n_trials


def test_bpe_refuses_to_merge_a_motif_seen_nine_times():
    """A pair appearing under ten times is not a motif, and merging it would manufacture
    vocabulary out of coincidence."""
    tiny = encode_events(_bars(n=200))
    b = encode_bpe(tiny, n_merges=50)
    assert b.meta["n_merges"] < 50, "merged past the frequency floor"


def test_encodings_carry_their_own_trial_count():
    for enc in (encode_events(_bars()), encode_quantile(_bars()), encode_vq(_bars())):
        assert enc.n_trials >= 1


# ------------------------------------------------------------------- degenerate in

def test_too_little_data_is_reported_not_guessed():
    enc = encode_vq(_bars(n=80))
    assert enc.meta.get("status") == "INSUFFICIENT_DATA"
    assert set(enc.tokens) == {"V_NA"}, "a codebook was fitted on 80 bars anyway"


def test_a_constant_series_does_not_produce_confident_tokens():
    idx = pd.date_range("2024-01-01", periods=300, freq="h", tz="UTC")
    flat = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}, index=idx)
    enc = encode_events(flat)
    assert set(enc.tokens) <= {"FLAT"}, f"invented structure in a flat series: {set(enc.tokens)}"
