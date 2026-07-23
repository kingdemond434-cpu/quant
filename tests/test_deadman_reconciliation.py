"""Test the paginated venue-history fetch in the dead-man reconciliation.

`_chunked_trades` guards a documented silent-truncation failure class (querying past a venue's
span cap returns an empty/partial list, not an error — institutional_knowledge.md: paginate every
history endpoint). A regression here silently drops fills and mis-scopes an incident reconciliation.
"""

from __future__ import annotations

from scripts.run_deadman_reconciliation import _chunked_trades


def test_paginates_the_full_span_and_dedupes_boundary_rows() -> None:
    calls: list[tuple[int, int]] = []

    def fake_fetch(sym: str, a: int, b: int) -> list[dict]:
        calls.append((a, b))
        return [{"id": a}, {"id": b}]  # boundary id repeats as the next chunk's start -> dedupe

    out = _chunked_trades(fake_fetch, "BTCUSDT", 0, 100, 40)
    assert calls == [(0, 40), (40, 80), (80, 100)]  # full span paged, last chunk capped at end
    assert sorted(t["id"] for t in out) == [0, 40, 80, 100]  # 40 and 80 fetched twice, de-duped


def test_empty_fetch_returns_empty_not_error() -> None:
    assert _chunked_trades(lambda s, a, b: [], "X", 0, 100, 40) == []
