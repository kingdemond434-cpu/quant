"""THE RAW-FETCHER FENCE (LAWS 5e as amended by the principal, 2026-10-14: robots.txt is
respected desk-wide).

Every request the desk sends to someone else's site goes through `libs/data/polite_fetch`
(`get` / `get_text` / `post`, or the drop-in seams `polite_urlopen`, `polite_requests_get`,
`PoliteSession`, or `admit` before a caller's own send), so the site's holds and the origin's
robots.txt are read by THE ONE implementation (`HostAccess`) before any byte leaves the box.

This test parses every non-test Python file and fails on a RAW network call --
`urllib.request.urlopen`, a from-imported `urlopen`, the fence's own `fenced_urlopen` /
`guarded_urlopen` (a terms door, not a robots check), `requests.get/post/Session/...`,
`httpx.*`, `urllib3.PoolManager`, `http.client.HTTP(S)Connection`, or
`build_opener(...).open` -- outside the explicit list below. Each entry says WHY that file may
keep its raw call. A new scraper therefore fails CI until it is routed through polite_fetch or
argued onto this list.

Categories:
  WRAPPER        the audited seam itself (polite_fetch, the crawler's seam under HostAccess).
  NOT_SCRAPING   the request reads no one else's pages: an inference/LLM API the desk is a
                 paying customer of, an alert or heartbeat the desk SENDS, the desk's own
                 infrastructure or localhost, an execution venue, or a licensed keyed data API
                 under contract. robots.txt governs crawlers of a site's pages, not these.
  PENDING        the file is being changed on another branch right now (2026-10-14 landing
                 train); it is routed through polite_fetch THERE, and this entry is deleted when
                 that branch lands. Do not add to this category without naming the branch.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

WRAPPER = "WRAPPER"
NOT_SCRAPING = "NOT_SCRAPING"
PENDING = "PENDING"

#: path -> (category, reason). Keep it EXPLICIT: one line per file, never a directory glob.
ALLOWED: dict[str, tuple[str, str]] = {
    # ---- the audited wrappers
    "libs/data/polite_fetch.py": (WRAPPER, "THE polite seam: HostAccess holds + robots before "
                                            "every request and every redirect hop"),
    # ---- not scraping: inference / LLM APIs the desk pays for
    "libs/ops/llm_seat.py": (NOT_SCRAPING, "LLM inference API (OpenRouter/DeepSeek/xAI), keyed"),
    "libs/ops/openrouter_guard.py": (NOT_SCRAPING, "OpenRouter credit/balance API, keyed"),
    "libs/research/free_panel.py": (NOT_SCRAPING, "OpenRouter inference API, keyed"),
    "scripts/brain_model_upgrade.py": (NOT_SCRAPING, "Anthropic model API, keyed"),
    "scripts/breadth_expander.py": (NOT_SCRAPING, "OpenRouter inference API, keyed"),
    "scripts/collector_author.py": (NOT_SCRAPING, "LLM chat-completions API, keyed"),
    "scripts/gpt_hunter.py": (NOT_SCRAPING, "OpenRouter inference API, keyed"),
    "scripts/hypothesis_generator.py": (NOT_SCRAPING, "LLM chat-completions API, keyed"),
    "scripts/kimi_hunter.py": (NOT_SCRAPING, "LLM chat-completions API, keyed"),
    "scripts/meta_architect.py": (NOT_SCRAPING, "LLM chat-completions API, keyed"),
    "scripts/model_upgrade.py": (NOT_SCRAPING, "OpenRouter model catalogue + inference, keyed"),
    "scripts/refresh_panel_roster.py": (NOT_SCRAPING, "OpenRouter model catalogue, keyed"),
    "scripts/run_external_panel.py": (NOT_SCRAPING, "OpenRouter inference + ntfy alert"),
    "scripts/run_model_upgrade.py": (NOT_SCRAPING, "Anthropic model API + ntfy alert"),
    "scripts/run_strategic_director.py": (NOT_SCRAPING, "LLM chat-completions API, keyed"),
    "scripts/seats.py": (NOT_SCRAPING, "OpenRouter balance API + ntfy alert"),
    "scripts/_retired/llm_blind_researcher.py": (NOT_SCRAPING, "retired LLM API caller"),
    "scripts/_retired/llm_code_auditor.py": (NOT_SCRAPING, "retired LLM API caller"),
    "ops/release/independent_review.py": (NOT_SCRAPING, "LLM inference APIs (OpenRouter, "
                                                        "Gemini) for the release review, keyed"),
    # ---- not scraping: alerts and heartbeats the desk SENDS
    "libs/ops/alert_channels.py": (NOT_SCRAPING, "Telegram/ntfy/webhook alerts sent by the desk"),
    "scripts/run_alerts.py": (NOT_SCRAPING, "ntfy / healthchecks pings sent by the desk"),
    "scripts/page_digest.py": (NOT_SCRAPING, "ntfy digest sent by the desk"),
    "scripts/_retired/publish_dashboard_url.py": (NOT_SCRAPING, "ntfy notice sent by the desk"),
    "desks/mt5/scripts/box_heartbeat.py": (NOT_SCRAPING, "healthchecks.io ping sent by the box"),
    "scripts/run_deadman_switch.py": (NOT_SCRAPING, "Tier-3 deadman rail: never modified "
                                                   "autonomously (CLAUDE.md); alerts + venue"),
    # ---- not scraping: the desk's own infrastructure, localhost, venues, licensed APIs
    "desks/mt5/mt5desk/object_store.py": (NOT_SCRAPING, "the desk's own S3-compatible bucket, "
                                                        "signed PUT/HEAD"),
    "scripts/publish_netlify.py": (NOT_SCRAPING, "the desk's own Netlify deploy API, keyed"),
    "scripts/setup_netlify.py": (NOT_SCRAPING, "the desk's own Netlify deploy API, keyed"),
    "scripts/run_ngrok.py": (NOT_SCRAPING, "localhost ngrok agent API (127.0.0.1:4040)"),
    "scripts/check_unit_health.py": (NOT_SCRAPING, "localhost research_pulse.json"),
    "libs/execution/binance_testnet.py": (NOT_SCRAPING, "retired execution venue client "
                                                        "(testnet orders), keyed"),
    "libs/execution/binance_spot_testnet.py": (NOT_SCRAPING, "retired execution venue client "
                                                             "(testnet orders), keyed"),
    "scripts/_retired/pull_cme.py": (NOT_SCRAPING, "retired licensed keyed historical-data API "
                                                   "(Databento), under contract"),
    # ---- pending: changed on another branch of the 2026-10-14 landing train
    "desks/mt5/research/source_fixer.py": (PENDING, "claude/source-fixer-hard-stop (fixer probes "
                                                    "+ Wayback; holds in the shared store)"),
    "desks/mt5/research/free_data.py": (PENDING, "free_data owner branch + "
                                                 "claude/yahoo-live-substitutes"),
    "desks/mt5/recorders/vol_archive.py": (PENDING, "claude/yahoo-live-substitutes (Yahoo reader)"),
    "desks/mt5/research/fetch_futures_curves.py": (PENDING, "claude/yahoo-live-substitutes "
                                                            "(Yahoo reader)"),
    "desks/mt5/research/futures_lead_lag.py": (PENDING, "claude/yahoo-live-substitutes "
                                                        "(Yahoo reader)"),
    "desks/mt5/side_channels/earnings_miner.py": (PENDING, "yahoo follow-up: earnings_miner via "
                                                           "polite_fetch"),
    "scripts/check_source_routes.py": (PENDING, "yahoo follow-up: check_source_routes via "
                                                "polite_fetch"),
    "scripts/hurdle_rate.py": (PENDING, "claude/yahoo-live-substitutes (^IRX reader refused / "
                                        "FRED DTB3 substitute)"),
}

_RAW_NAMES = frozenset({"urlopen", "fenced_urlopen", "guarded_urlopen"})
_CLIENT_LIBS = frozenset({"requests", "httpx"})
_CLIENT_VERBS = frozenset({"get", "post", "put", "head", "patch", "delete", "request",
                           "Session", "Client", "AsyncClient", "stream"})


def raw_calls(src: str) -> list[tuple[int, str]]:
    """(line, call) for every raw network call in `src`."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id in _RAW_NAMES:
            out.append((node.lineno, f.id))
        elif isinstance(f, ast.Attribute):
            base = f.value
            bname = (base.id if isinstance(base, ast.Name)
                     else base.attr if isinstance(base, ast.Attribute) else "")
            if f.attr in _RAW_NAMES or (bname in _CLIENT_LIBS and f.attr in _CLIENT_VERBS):
                out.append((node.lineno, f"{bname}.{f.attr}"))
            elif bname == "urllib3" and f.attr == "PoolManager":
                out.append((node.lineno, "urllib3.PoolManager"))
            elif f.attr in ("HTTPSConnection", "HTTPConnection"):
                out.append((node.lineno, f"{bname}.{f.attr}"))
            elif (f.attr == "open" and isinstance(base, ast.Call)
                  and getattr(base.func, "attr", getattr(base.func, "id", "")) == "build_opener"):
                out.append((node.lineno, "build_opener().open"))
    return out


def _sources() -> list[Path]:
    out = []
    for p in sorted(ROOT.rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith((".git/", ".claude/", ".venv/", "venv/", "node_modules/")):
            continue
        if "/tests/" in f"/{rel}" or p.name.startswith("test_") or p.name == "conftest.py":
            continue
        out.append(p)
    return out


def test_no_raw_fetcher_outside_the_audited_list() -> None:
    offenders: list[str] = []
    for p in _sources():
        rel = p.relative_to(ROOT).as_posix()
        if rel in ALLOWED:
            continue
        try:
            src = p.read_text(encoding="utf-8")
            calls = raw_calls(src)
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        offenders += [f"{rel}:{ln} {name}" for ln, name in calls]
    assert offenders == [], (
        "raw network call outside polite_fetch -- route it through polite_fetch.get / "
        "polite_urlopen / polite_requests_get (robots.txt + holds first, LAWS 5e amended "
        "2026-10-14), or argue it onto ALLOWED with a reason:\n" + "\n".join(offenders))


def test_every_allowlisted_file_exists_and_still_needs_its_entry() -> None:
    """An entry whose file is gone or no longer makes a raw call is stale: delete it, so the
    list stays the exact set of raw callers and never becomes a blanket permission."""
    stale = []
    for rel in ALLOWED:
        p = ROOT / rel
        if not p.exists() or not raw_calls(p.read_text(encoding="utf-8")):
            stale.append(rel)
    assert stale == [], stale


def test_every_entry_names_a_category_and_a_reason() -> None:
    for rel, (cat, why) in ALLOWED.items():
        assert cat in (WRAPPER, NOT_SCRAPING, PENDING), rel
        assert len(why) > 10, rel


@pytest.mark.parametrize("snippet,expected", [
    ("import urllib.request\nurllib.request.urlopen('https://a.org')\n", 1),
    ("from urllib.request import urlopen\nurlopen('https://a.org')\n", 1),
    ("import requests\nrequests.get('https://a.org')\n", 1),
    ("import requests\ns = requests.Session()\n", 1),
    ("from libs.data import terms_fence as _tf\n_tf.guarded_urlopen('https://a.org')\n", 1),
    ("import urllib.request\nurllib.request.build_opener().open('https://a.org')\n", 1),
    ("from libs.data.polite_fetch import polite_urlopen\npolite_urlopen('https://a.org')\n", 0),
    ("from libs.data import polite_fetch as pf\npf.get('https://a.org')\n", 0),
])
def test_the_scanner_sees_a_raw_call(snippet: str, expected: int) -> None:
    assert len(raw_calls(snippet)) == expected
