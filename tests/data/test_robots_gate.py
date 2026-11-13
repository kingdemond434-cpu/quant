"""The shared robots gate takes the stricter rule: an unread policy is never permission."""
from __future__ import annotations

from libs.data.robots_gate import RobotsGate, honest_ua


def _gate(status: int, text: str = "") -> tuple[RobotsGate, list[str]]:
    calls: list[str] = []

    def get(url: str) -> tuple[int, str]:
        calls.append(url)
        return status, text
    return RobotsGate("unit", get_text=get), calls


def test_ua_names_the_organ_and_the_source_and_impersonates_nobody() -> None:
    ua = honest_ua("alfred_vintages")
    assert ua.startswith("quant-research/1.0") and "alfred_vintages" in ua
    assert "Mozilla" not in ua and "Chrome" not in ua


def test_missing_robots_allows_and_is_read_once_per_host() -> None:
    g, calls = _gate(404)
    assert g.refusal("https://a.example/x") is None
    assert g.refusal("https://a.example/y") is None
    assert calls == ["https://a.example/robots.txt"]


def test_forbidden_robots_disallows_everything() -> None:
    g, _ = _gate(403)
    assert g.refusal("https://a.example/x")


def test_unreadable_robots_is_a_refusal_not_a_permission() -> None:
    for st in (0, 500, 429):
        g, _ = _gate(st)
        assert "unreadable" in str(g.refusal("https://a.example/x"))


def test_disallow_for_our_token_or_star_binds() -> None:
    g, _ = _gate(200, "User-agent: quant-research\nDisallow: /private\n")
    assert g.refusal("https://a.example/private/x")
    assert g.refusal("https://a.example/public") is None
    g2, _ = _gate(200, "User-agent: *\nDisallow: /\n")
    assert g2.refusal("https://b.example/anything")
    assert g2.refusal("https://b.example/robots.txt") is None
