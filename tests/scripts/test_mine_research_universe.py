"""MT5 UNIVERSE MANDATE (2026-08-18): the miner hunts the full MT5/Fusion universe and NO
crypto-exchange universe. These pin both halves on the miner's own query surface -- removal of
the crypto-exchange-native vocabulary AND presence of the MT5 market and its mechanisms -- so a
future edit that quietly re-adds a Binance/funding/on-chain query fails loudly.

The scorer is deliberately NOT asserted crypto-free: it ranks by METHODOLOGY (permutation,
walk-forward, overfit), which is universe-neutral and transfers to any market. What must change
is what we SEARCH FOR, not how we rank what comes back.
"""
from __future__ import annotations

import scripts.mine_research_queue as m

from libs.research.video_triage import SURFACE_THRESHOLD, score_title

_ALL_QUERY_LISTS = ("BILIBILI_QUERIES", "CN_ARTICLE_QUERIES", "SEARCH_QUERIES")

#: Crypto-exchange-native vocabulary. A query hunting any of these is hunting the forbidden
#: universe. Kept as substrings because that is how they appear inside a multi-word query.
_BANNED = (
    "加密货币", "加密", "币安", "数字货币", "永续合约", "资金费率", "跨交易所", "链上", "矿工",
    "crypto", "binance", "bybit", "okx", "hyperliquid", "perpetual", "funding rate", "on-chain",
)


def _joined() -> str:
    out = []
    for name in _ALL_QUERY_LISTS:
        out.extend(getattr(m, name))
    return " ".join(out).lower()


def test_no_query_hunts_the_crypto_exchange_universe() -> None:
    joined = _joined()
    hit = [b for b in _BANNED if b.lower() in joined]
    assert not hit, f"miner still hunts crypto-exchange terms: {hit}"


def test_the_miner_targets_the_mt5_universe() -> None:
    """Removal is not enough; the sweep must actually reach gold/FX and an MT5-native mechanism."""
    joined = _joined()
    assert any(a in joined for a in ("黄金", "xauusd", "gold", "外汇", "forex")), "no gold/FX asset"
    assert any(a in joined for a in ("mt5", "ea", "expert advisor", "智能交易")), "no MT5/EA target"
    assert any(a in joined for a in ("cot", "持仓", "套息", "carry", "掉期", "swap")), \
        "no MT5-native mechanism (COT / carry / swap)"


def test_universe_neutral_validation_queries_are_preserved() -> None:
    """The retarget must not throw away the highest-converting register -- validation vocabulary
    transfers to any market and stays."""
    joined = _joined()
    assert "过拟合" in joined or "overfitting" in joined
    assert "样本外" in joined or "out of sample" in joined or "walk forward" in joined


def test_scorer_surfaces_a_gold_cot_study() -> None:
    """A gold/COT study with validation vocabulary must clear the surface threshold, or the
    retargeted queries would return content the ranker then buries."""
    s, _ = score_title("XAUUSD gold strategy: COT positioning walk-forward out-of-sample test")
    assert s >= SURFACE_THRESHOLD, f"gold/COT study scored {s}"


def test_scorer_still_buries_a_gold_hype_reel() -> None:
    """Methodology-first: naming the asset must not rescue a personal-profit reel."""
    s, _ = score_title("This GOLD strategy made me $80,000 a month (secret)")
    assert s < SURFACE_THRESHOLD, f"gold hype reel scored {s}"
