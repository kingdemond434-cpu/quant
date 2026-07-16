"""Cold-audit dossier generator for the Multi-Model Advisory Panel (weekly, 7th cycle).

Compiles a ~2-page, SANITIZED snapshot of the desk from live feeds: identity, current
numbers, active edges + candidates, risk posture, top bottlenecks, and the most recent
decision-ledger entries. Written for an external LLM that has never seen the system.
SANITIZATION IS A HARD GATE: the dossier must never contain keys, tokens, pager topics,
tunnel URLs, or file paths under data/secrets -- `sanitize()` blocks known patterns and
the panel runner refuses a dossier that fails it. Writes docs/EXTERNAL_PANEL_DOSSIER.md.

    python scripts/generate_external_review_doc.py
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("docs/EXTERNAL_PANEL_DOSSIER.md")
# hard-block patterns: secrets-shaped strings must never leave the machine in a dossier.
# Token heuristic = 28+ chars WITHOUT a hyphen (keys/tokens are long unhyphenated runs;
# ledger ids like 2026-07-12-first-inversion-... are hyphen-segmented and stay readable).
_BLOCK = [re.compile(p, re.I) for p in (
    r"\b[A-Za-z0-9_]{28,}\b",
    r"quant-desk-[0-9a-f]+",         # pager topic
    r"ntfy\.sh/\S+",
    r"data[/\\]secrets",
    r"ngrok|netlify\.app|trycloudflare",
    r"\b\d{1,3}(?:\.\d{1,3}){3}\b",  # IP addresses (2026-07-16: gap register carries the VPS
)]                                   # IP -- must never reach external labs)


def sanitize(text: str) -> str:
    """Redact secrets-shaped substrings; the dossier is advisory content, never ops detail."""
    for pat in _BLOCK:
        text = pat.sub("[redacted]", text)
    return text


def _load(p: str) -> dict[str, Any]:
    try:
        d: dict[str, Any] = json.loads(Path(p).read_text("utf-8"))
        return d
    except (OSError, json.JSONDecodeError):
        return {}


def build() -> str:
    sh = _load("web/cashcarry_shadow.json")
    lc = _load("web/live_combined.json")
    ga = _load("web/growth_audit.json")
    rc = _load("web/root_cause.json")
    led = _load("data/decision_ledger.json").get("decisions", [])[-10:]
    mo = lc.get("molded", {})
    lines = [
        "# Cold-Audit Dossier -- Autonomous Solo Crypto Quant Desk",
        f"Generated {datetime.now(tz=UTC).date().isoformat()} from live feeds. "
        "You are reading the POST-FIX system (two adversarial review rounds absorbed).",
        "",
        "## Identity",
        "AI-operated systematic desk: delta-neutral funding carry (long spot + short perp, "
        "top-10 positive-funding names, 35% concentration cap, funding-weighted water-fill) "
        "deployed on Binance testnets; validation gauntlet = CPCV + deflated Sharpe + PBO + "
        "White reality check + frozen forward shadows; sizing = shrunk-Kelly "
        "S^2/(S^2+SE^2) with NW-adjusted effective N, ruin<=2% cap, 35%/15% ruin/DD rails, "
        "isolated dead-man switch. Objective: max E[log wealth] s.t. survival.",
        "",
        "## Current numbers",
        f"- Carry forward shadow: day {sh.get('forward_days')}/90, NW t-stat "
        f"{sh.get('forward_tstat')} (naive {sh.get('forward_tstat_naive')}), forward Sharpe "
        f"{sh.get('forward_ann_sharpe')} vs backtest {sh.get('backtest_ann_sharpe')}; "
        f"regime evidence: {sh.get('funding_vol')}, events {sh.get('regime_events')}",
        f"- Book: net ${mo.get('net_pnl')}, funding ${mo.get('funding')} "
        f"({mo.get('run_rate_apr_pct')}% APR run-rate), {mo.get('n_closed_trades')} closed "
        f"trades, winrate {mo.get('winrate_pct')}%, max DD {mo.get('max_dd_pct')}%",
        "- Candidates (paper): perp L/S, trend_30d, regime-gated challenger -- all in "
        "90d forward shadows with Holm cohort correction (carry is Holm-exempt primary)",
        f"- Growth audit: {len(ga.get('conservatism_defects', []) or [])} conservatism "
        f"defects; root-cause verdict: {rc.get('top_cause')} ({rc.get('action')})",
        "",
        "## Promotion + sizing rules (attack these)",
        "- Fast-track >=40 fwd days: NW-t >= bar AND fwd >= 0.5x backtest AND regime "
        "evidence (famine/basis event OR funding-vol >= 25th pct of backtest rolling-40d); "
        "standard 90d; 40d floor. Directional sleeves need >=2 vol bands in-window.",
        "- Shrunk-Kelly fraction = S^2/(S^2+SE^2), SE on NW effective-N, evidence pooling "
        "live + 0.25x shadow (live-only after 60 live days); demotion elevator 0.25x on "
        "DD > 2x model / shortfall > 50% edge / live 30d Sharpe < 0.5x shadow.",
        "- Carry first-inversion probation: NAV-scaled 0.75x/<25k, 0.6x/<100k, 0.5x above, "
        "until one inversion survived or 60 live days.",
        "- Executor rails: ADL-detect -> flatten spot (never re-short a squeeze), basis-stop "
        ">3% premium -> exit 6h; hedge-reconcile every 600s cycle; maker-first execution.",
        "",
        "## Known limitations (repeating these scores zero)",
        "Zero live track record; single edge family (funding); single venue; free data "
        "ceiling; solo principal + single AI vendor; laptop until VPS; testnet fills "
        "optimistic vs live.",
        "",
        "## Last 10 ledger decisions",
    ]
    for e in led:
        lines.append(f"- {e.get('id')}: {str(e.get('decision'))[:220]}")
    lines += [
        "",
        "## Top open bottlenecks (self-assessed)",
        "1. Economic concentration in funding carry (crowding = slow structural decay).",
        "2. Testnet->live execution transfer (TCA pipeline queued, not yet live).",
        "3. Capacity ceiling of top-10 Binance perps (cross-venue study queued).",
    ]
    # GAP REGISTER (2026-07-16): auditors were benchmarking blind to the desk's own queue --
    # feeding them the ranked register lets them attack the ranking itself (missing gaps,
    # wrong priorities) instead of rediscovering known items. Sanitizer still gates everything.
    try:
        reg = Path("docs/GAP_REGISTER.md").read_text("utf-8")
        rows = [ln for ln in reg.splitlines() if ln.startswith("| ") and "---" not in ln]
        lines += ["", "## Current gap register (self-assessed, ranked -- attack the ranking)",
                  *rows[1:11]]
    except OSError:
        pass
    return sanitize("\n".join(lines))


def main() -> None:
    doc = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(doc, "utf-8")
    print(f"dossier -> {_OUT} ({len(doc)} chars, sanitized)")


if __name__ == "__main__":
    main()
