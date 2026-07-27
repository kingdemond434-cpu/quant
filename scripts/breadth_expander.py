"""BREADTH EXPANDER -- an external LLM as a COLLEAGUE to the miners, not a judge of them.

Every existing panel mission (audit / premortem / verify) is JUDICIAL: it reads finished work and
critiques it. This one is GENERATIVE: "here is territory you have not looked at." That role did not
exist on this desk.

WHY AN EXTERNAL MODEL AT ALL: orthogonality in the OBSERVER, not just the observed (L6 applied to
the cognition layer). A different lab's model has different training data, regional coverage and
recency, so it surfaces sources this desk structurally cannot think of.

DESIGN DECISIONS (principal left these to me):
  COLD, NOT MEMORY -- memory anchors: a model recalling its own prior suggestions drifts into
    incremental variations of the same neighbourhood. Cold cognition + POST-HOC dedup against the
    class map gives fresh thinking AND no repeats. Same principle as the desk's blind rediscovery,
    which is deliberately blind to current coverage maps.
  ROTATING LENS -- each run attacks breadth from a structurally different L6 angle, so "never
    exhausted" is mechanical rather than aspirational. A daily reshuffle of one prompt would
    converge; six orthogonal framings do not.
  2 SEATS/DAY, NOT 13 -- lead seat is the flagship OpenAI reasoning model (principal's pick),
    plus ONE rotating non-OpenAI seat for lab diversity. Over a week every lab contributes, at
    ~2 calls/day instead of 13. OpenRouter is budget-capped and currently thin.

HARD CONSTRAINTS:
  * Stage-A ONLY, zero promotion authority (L4). It generates candidates; the fixed confirmation
    budget never moves.
  * EVERY suggestion is FEASIBILITY-PROBED before it counts. LLMs confidently invent APIs -- on
    2026-07-27 alone, suggested sources died at: Feixiaohao (SSL), AICoin (404), Binance
    leaderboard (404), DefiLlama bridges (402 paid). Unprobed suggestions are a list of dead links.
  * §13 legitimacy gate unchanged: public + legitimately accessible only.
  * Its yield is MEASURED as method `external_llm_expander` -- if it produces 300 sources and zero
    survivors, its budget share decays like anything else. No permanent seat on reputation.

Run from repo root.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KEYS = ROOT / "data/secrets/llm_panel.json"
CLASSMAP = ROOT / "data/information_class_map.json"
OUT = ROOT / "data/breadth_expansion.jsonl"
CTX = ssl.create_default_context()

LEAD_SEAT = "openai/gpt-5.6-terra-pro"          # flagship reasoning seat (principal's pick)
DIVERSITY_POOL = ["x-ai/grok-4.3", "google/gemini-3.1-pro-preview", "deepseek/deepseek-v4-pro",
                  "qwen/qwen3.7-max", "z-ai/glm-5.2", "moonshotai/kimi-k3", "minimax/minimax-m3"]

# rotating L6 lenses -- one per day, so consecutive runs cannot converge
LENSES = [
    ("MODALITY GAP", "The desk mines TABULAR data well and is structurally blind to other carriers "
     "(filing 0/2, transcript 0/2, video 0/1, graph 0/4, archive 0/2 covered). Name FREE, PUBLIC "
     "sources in the UNDER-COVERED carriers specifically."),
    ("NEGATIVE SPACE", "Name information that MATTERS for crypto price formation but leaves NO "
     "direct public footprint -- then name the free PROXY that does leave one."),
    ("CROSS-DOMAIN IMPORT", "Name information classes that OTHER disciplines mine routinely "
     "(epidemiology, insurance, supply chain, sports analytics, intelligence, ecology) that crypto "
     "quant does not, and the free crypto-domain equivalent."),
    ("ADVERSARIAL", "If a top quant firm had an edge this desk lacks, what INFORMATION would it be "
     "built on? Name the public shadow that information casts."),
    ("NON-ENGLISH FRONTIER", "Name free public sources in Chinese, Korean, Japanese, Russian, "
     "Arabic, Portuguese, Turkish or Spanish that English-language crypto research systematically "
     "misses. Native-language platforms, not English mirrors."),
    ("INVERSION", "Start from targets (funding regime shifts, liquidation cascades, venue "
     "migration, liquidity droughts). For each, name the IDEAL observable, then the closest FREE "
     "public proxy."),
]

SYSTEM = (
    "You are a research scout for a systematic crypto trading desk. You are a COLLEAGUE helping "
    "the desk's own miners see further -- not an auditor. Your job is BREADTH: name information "
    "sources, classes and modalities the desk has probably NOT considered.\n"
    "HARD RULES:\n"
    "1. FREE and PUBLIC only. No paywalled, pirated, private-group or paid-vendor data.\n"
    "2. Be SPECIFIC AND CHECKABLE: give the actual endpoint/domain/dataset name. Vague categories "
    "('social sentiment') are useless; 'api.example.com/v1/x, free, no key, daily history' is useful.\n"
    "3. Prefer sources with STRUCTURED or reconstructable history -- a signal needs a time series.\n"
    "4. State the MECHANISM: why would this information move crypto prices, and does it LEAD or "
    "merely coincide?\n"
    "5. Do NOT suggest: Binance/OKX/Bybit/Deribit standard market data, Glassnode/CryptoQuant/"
    "Nansen/Kaiko paid tiers, generic Twitter/Reddit sentiment, or news aggregators. All are "
    "already covered or already refuted.\n"
    "Output ONE source per line, format:\n"
    "NAME | URL_OR_ENDPOINT | MODALITY | MECHANISM (<=20 words) | LEADS_OR_COINCIDES"
)


def _ask(base_url: str, key: str, model: str, system: str, user: str, timeout: float = 300.0) -> str:
    body = json.dumps({"model": model, "max_tokens": 4000, "temperature": 0.9,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body,
                                 method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")


def probe(url: str) -> str:
    """Feasibility check -- an unprobed LLM suggestion is a dead link until proven otherwise."""
    if not url.startswith("http"):
        url = "https://" + url.strip().strip("<>()[]")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return f"OK-{r.status}"
    except urllib.error.HTTPError as e:
        return f"HTTP-{e.code}"
    except Exception as e:
        return type(e).__name__


def main() -> None:
    if not KEYS.exists():
        print("no llm_panel.json -- cannot run"); return
    provs = json.loads(KEYS.read_text("utf-8"))["providers"]
    # provider records are {name, base_url, key, model}
    by_model = {p.get("model"): p for p in provs if isinstance(p, dict)}

    # --- BUDGET ENVELOPE (do NOT bypass the panel's guard -- this spends the same wallet) -----
    # The panel aborts rather than silently degrading; this respects the same envelope and the
    # same observed-cost history, scaled to the 2 seats this script actually uses.
    try:
        bcfg = json.loads(Path("data/panel_budget.json").read_text("utf-8"))
        bstate = json.loads(Path("data/panel_budget_state.json").read_text("utf-8"))
    except Exception:
        bcfg, bstate = {}, {}
    cap = float(bcfg.get("monthly_usd_cap") or bcfg.get("cap_usd") or 0) or None
    spent = float(bstate.get("month_spend_usd") or bstate.get("spent_usd") or 0)
    obs = [float(c) for c in (bstate.get("observed_costs") or bstate.get("run_costs") or [])]
    need = max([*obs[-6:], 0.05 * 2]) * (2 / max(1, len(provs)))
    if cap and spent + need > cap:
        print(f"breadth-expander: ABORT -- envelope guard. spent ${spent:.2f} + est ${need:.3f} "
              f"> cap ${cap:.2f}. Never degrade silently; page the principal.")
        return
    print(f"budget: est ${need:.3f} for 2 seats"
          + (f" | month ${spent:.2f}/${cap:.2f}" if cap else " | no cap configured"))

    day = datetime.now(tz=UTC).toordinal()
    lens_name, lens_txt = LENSES[day % len(LENSES)]
    diversity = DIVERSITY_POOL[day % len(DIVERSITY_POOL)]
    seats = [LEAD_SEAT, diversity]

    known = set()
    if CLASSMAP.exists():
        cm = json.loads(CLASSMAP.read_text("utf-8"))
        for k, v in cm.get("classes", {}).items():
            known.add(k.lower())
            known.update(w for w in re.split(r"[^a-z0-9]+", v.get("note", "").lower()) if len(w) > 4)

    user = (f"LENS OF THE DAY -- {lens_name}\n{lens_txt}\n\n"
            f"Name 8-12 sources through THIS lens only. Be specific and checkable.")
    print(f"=== BREADTH EXPANDER | lens: {lens_name} | seats: {', '.join(seats)} ===\n")

    rows, n_new = [], 0
    for seat in seats:
        prov = by_model.get(seat)
        if not prov:
            print(f"  {seat}: not in roster, skipped"); continue
        try:
            txt = _ask(prov["base_url"], prov["key"], seat, SYSTEM, user)
        except Exception as e:
            print(f"  {seat}: FAILED ({type(e).__name__} {getattr(e,'code','')})")
            continue
        for ln in txt.splitlines():
            if ln.count("|") < 3:
                continue
            parts = [x.strip() for x in ln.split("|")]
            name, url = parts[0].lstrip("-*0123456789. "), parts[1]
            if not name or len(name) > 90:
                continue
            dup = name.lower() in known or any(
                w in known for w in re.split(r"[^a-z0-9]+", name.lower()) if len(w) > 5)
            st = probe(url) if not dup else "skipped-dup"
            reachable = st.startswith("OK")
            if not dup and reachable:
                n_new += 1
            rows.append({"date": datetime.now(tz=UTC).date().isoformat(), "lens": lens_name,
                         "seat": seat, "name": name, "url": url,
                         "modality": parts[2] if len(parts) > 2 else "",
                         "mechanism": parts[3] if len(parts) > 3 else "",
                         "leads": parts[4] if len(parts) > 4 else "",
                         "duplicate": dup, "probe": st, "reachable": reachable})
            flag = "DUP" if dup else ("NEW" if reachable else "dead")
            print(f"  [{flag:>4}] {name[:46]:<46} {st:<12} {parts[2][:12] if len(parts)>2 else ''}")

    if rows:
        with OUT.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    tot = len(rows)
    print(f"\n  {tot} suggestions | {sum(1 for r in rows if r['duplicate'])} already known | "
          f"{sum(1 for r in rows if not r['duplicate'] and not r['reachable'])} unreachable | "
          f"{n_new} NEW + REACHABLE")
    print("  -> new+reachable enter the class map as never-visited; Stage-A only, zero promotion")
    print(f"  -> appended {OUT}")


if __name__ == "__main__":
    main()
