"""BREADTH EXPANDER -- external LLM as a COLLEAGUE to the miners (generative, not judicial).

Every other panel mission (audit/premortem/verify) is JUDICIAL: it critiques finished work. This
one is GENERATIVE: "here is territory you have not looked at." Orthogonality in the OBSERVER, not
just the observed (L6 applied to the cognition layer).

MAXIMUM DAILY SWEEP (principal 2026-07-27): ALL 6 lenses every day, 3 seats each, 15-20 sources
per call. Cost was never the binding constraint -- the first 2-seat run cost $0.015, so a full
sweep is ~18 calls ~ $0.14/day ~ $4.20/month against a $100-150 cap.

DESIGN DECISIONS:
  COLD, NOT MEMORY -- memory anchors; a model recalling its own suggestions drifts into
    incremental variants. Cold cognition + post-hoc dedup = fresh thinking AND no repeats. Same
    principle as blind rediscovery, which is deliberately blind to current coverage maps.
  ALL LENSES DAILY -- one prompt reshuffled would converge; six orthogonal framings cannot.
  SEAT ROTATION -- lead seat always present, 2 rotating labs per lens, so all 13 labs contribute
    within days without firing 13 calls per lens.
  PARALLEL PROBING -- with a full sweep the HTTP probes, not the LLM calls, are the wall clock.
  SATURATION ALARM -- if novelty/day trends to zero that is real exhaustion of THIS lens set OR
    lens staleness; both must be VISIBLE and trigger lens regeneration. Silence is the failure
    mode the ceiling clause forbids.

HARD CONSTRAINTS: Stage-A only, zero promotion authority (L4). Every suggestion feasibility-probed
(first run: 6/11 were dead links). Respects the panel budget envelope (abort, never silently
degrade). §13 legitimacy gate: public + legitimately accessible only. Yield measured as method
`external_llm_expander` -- 300 sources and zero survivors decays its share like anything else.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import seats  # noqa: E402 -- after the sys.path bootstrap above

KEYS = ROOT / "data/secrets/llm_panel.json"
CLASSMAP = ROOT / "data/information_class_map.json"
OUT = ROOT / "data/breadth_expansion.jsonl"
CTX = ssl.create_default_context()

LEAD_SEAT = "openai/gpt-5.6-terra-pro"
DIVERSITY_POOL = ["x-ai/grok-4.3", "google/gemini-3.1-pro-preview", "deepseek/deepseek-v4-pro",
                  "qwen/qwen3.7-max", "z-ai/glm-5.2", "moonshotai/kimi-k3", "minimax/minimax-m3",
                  "google/gemini-3.6-flash", "meituan/longcat-2.0", "nvidia/nemotron-3-ultra-550b-a55b"]

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
     "migration, liquidity droughts). For each name the IDEAL observable, then the closest FREE "
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
    "4. State the MECHANISM: why would this move crypto prices, and does it LEAD or coincide?\n"
    "5. Do NOT suggest: Binance/OKX/Bybit/Deribit standard market data, Glassnode/CryptoQuant/"
    "Nansen/Kaiko paid tiers, generic Twitter/Reddit sentiment, or news aggregators -- all are "
    "already covered or already refuted.\n"
    "Output ONE source per line, format:\n"
    "NAME | URL_OR_ENDPOINT | MODALITY | MECHANISM (<=20 words) | LEADS_OR_COINCIDES"
)



def _doctrine(role: str = "") -> str:
    """Runtime doctrine preamble. One source (scripts/doctrine.py); never a pasted copy."""
    try:
        from scripts.doctrine import preamble
        return preamble(role)
    except Exception:  # blind-except intentional (BLE001)
        try:
            import sys as _s
            _s.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
            from doctrine import preamble  # type: ignore
            return preamble(role)
        except Exception:  # blind-except intentional (BLE001)
            return ""          # never break a caller over a preamble


def _ask(base_url: str, key: str, model: str, system: str, user: str, timeout: float = 110.0) -> str:
    body = json.dumps({"model": model, "max_tokens": 16000, "temperature": 1.0,
                       "reasoning": {"effort": "high"},
                       "messages": [{"role": "system", "content": _doctrine("breadth_expander") + system},
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
    """An unprobed LLM suggestion is a dead link until proven otherwise."""
    u = url if url.startswith("http") else "https://" + url.strip().strip("<>()[]")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
            return f"OK-{r.status}"
    except urllib.error.HTTPError as e:
        return f"HTTP-{e.code}"
    except Exception as e:
        return type(e).__name__


def novelty_trend(path: Path, new: int, total: int) -> str:
    """Saturation alarm -- falling novelty is real exhaustion OR stale lenses. Both must be seen."""
    hist = []
    if path.exists():
        for ln in path.read_text("utf-8").splitlines()[-600:]:
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("_summary"):
                hist.append(r)
    rates = [h["new"] / max(1, h["total"]) for h in hist[-7:]]
    today = new / max(1, total)
    if len(rates) >= 3 and sum(rates) / len(rates) < 0.05 and today < 0.05:
        return ("*** SATURATION ALARM: novelty <5% over 3+ runs -- lens set exhausted or stale. "
                "REGENERATE lenses via blind re-derivation; do not report 'nothing new'. ***")
    avg = f" (7-run avg {sum(rates)/len(rates)*100:.0f}%)" if rates else " (first runs)"
    return f"novelty {today*100:.0f}% today{avg}"


def main() -> None:
    if not KEYS.exists():
        print("no llm_panel.json -- cannot run")
        return
    # Live-roster resolution: an upgraded-away lead or pool seat is substituted (same lab first),
    # never silently dropped. The lead is resolved on its own so it can never be crowded out of
    # the pool's distinct-lab budget, and the pool keeps its lens-rotation diversity.
    lead = seats.resolve([LEAD_SEAT], n=1, role="breadth_lead")
    pool = seats.resolve(DIVERSITY_POOL, n=len(DIVERSITY_POOL), distinct_labs=False,
                         role="breadth_pool")
    by_model = {p["model"]: p for p in (lead + pool)}
    LEAD = lead[0]["model"] if lead else LEAD_SEAT
    POOL = [p["model"] for p in pool] or DIVERSITY_POOL

    # budget envelope -- same wallet as the panel; abort rather than silently degrade
    try:
        bcfg = json.loads((ROOT / "data/panel_budget.json").read_text("utf-8"))
        bstate = json.loads((ROOT / "data/panel_budget_state.json").read_text("utf-8"))
    except Exception:
        bcfg, bstate = {}, {}
    # KEY NAMES MUST MATCH THE PANEL'S OWN CONFIG. My first version read monthly_usd_cap/cap_usd,
    # which do not exist, so it printed "no cap configured" and the guard was INERT while a real
    # $120 envelope was sitting in the file. A guard reading the wrong key is worse than none.
    cap = float(bcfg.get("monthly_envelope_usd") or 0) or None
    alert = float(bcfg.get("alert_at_usd") or 0) or None
    spent = float(bstate.get("usage_at_month_start") or 0)
    obs = [float(c) for c in (bstate.get("observed_run_costs") or [])]
    n_calls = len(LENSES) * 3
    # MEASURED cost, not assumed: panel history is ~$2.93/run at 13 seats => ~$0.22/call.
    # The old 0.008/call constant was 27x optimistic and is exactly how a 402 happens mid-run.
    per_call = (max(obs) / 13.0) if obs else 0.22
    need = per_call * n_calls
    if cap and spent + need > cap:
        print(f"ABORT -- envelope guard: spent ${spent:.2f} + est ${need:.2f} > envelope "
              f"${cap:.2f}. PAGE the principal; never silently degrade quality.")
        return
    if alert and spent + need > alert:
        print(f"WARN -- past alert threshold ${alert:.2f} (spent ${spent:.2f} + est ${need:.2f})")
    print(f"budget: est ${need:.2f} for {n_calls} calls @ ${per_call:.3f}/call (measured)"
          + (f" | month ${spent:.2f}/${cap:.2f}" if cap else " | NO ENVELOPE CONFIGURED"))

    known: set[str] = set()
    # DEDUP MUST INCLUDE THE GRAVEYARD, not just the class map. The 2026-07-27 sweep re-suggested
    # Bithumb/Coinone/Bitso/Mercado -- all TESTED AND KILLED the same day -- because dedup only
    # read the class map. Re-proposing refuted sources wastes probe budget and research time.
    gy = ROOT / "docs/graveyard.md"
    if gy.exists():
        for ln in gy.read_text("utf-8").splitlines():
            if ln.startswith("|"):
                first = ln.strip("|").split("|")[0].strip().lower()
                known.add(first)
                known.update(w for w in re.split(r"[^a-z0-9]+", first) if len(w) > 4)
    if CLASSMAP.exists():
        cm = json.loads(CLASSMAP.read_text("utf-8"))
        for k, v in cm.get("classes", {}).items():
            known.add(k.lower())
            known.update(w for w in re.split(r"[^a-z0-9]+", v.get("note", "").lower())
                         if len(w) > 4)

    day = datetime.now(tz=UTC).toordinal()
    today = datetime.now(tz=UTC).date().isoformat()
    print(f"=== BREADTH EXPANDER | FULL SWEEP: {len(LENSES)} lenses x 3 seats ===\n")

    # PARALLEL LLM CALLS. 18 sequential high-effort calls ran 70+ minutes and were reaped by the
    # watchdog three times; the sweep must fit inside its cadence budget, so fan them out.
    jobs = []
    for li, (lens_name, lens_txt) in enumerate(LENSES):
        seats_for_lens = [LEAD] + [POOL[(day + li + k) % len(POOL)] for k in (0, 1)]
        user = (f"LENS -- {lens_name}\n{lens_txt}\n\n"
                "Name 15-20 sources through THIS lens only. Be specific and checkable. "
                "Prefer OBSCURE and NON-ENGLISH over well-known -- the desk has the obvious ones.")
        for seat in seats_for_lens:
            prov = by_model.get(seat)
            if prov:
                jobs.append((lens_name, seat, prov, user))

    def _run(j):
        ln_name, seat, prov, user = j
        try:
            return ln_name, seat, _ask(prov["base_url"], prov["key"], seat, SYSTEM, user), None
        except Exception as e:
            return ln_name, seat, "", f"{type(e).__name__} {getattr(e, 'code', '')}"

    print(f"dispatching {len(jobs)} calls in parallel (9 workers)...")
    with ThreadPoolExecutor(max_workers=9) as ex:
        answers = list(ex.map(_run, jobs))

    rows: list[dict[str, Any]] = []
    for lens_name, seat, txt, err in answers:
        if err:
            print(f"    {seat.split('/')[-1]:<24} {lens_name[:18]:<18} FAILED ({err})")
            continue
        got = 0
        for ln in txt.splitlines():
            if ln.count("|") < 3:
                continue
            parts = [x.strip() for x in ln.split("|")]
            name, url = parts[0].lstrip("-*0123456789. "), parts[1]
            if not name or len(name) > 90 or not url:
                continue
            dup = name.lower() in known or any(
                w in known for w in re.split(r"[^a-z0-9]+", name.lower()) if len(w) > 5)
            rows.append({"date": today, "lens": lens_name, "seat": seat, "name": name,
                         "url": url, "modality": parts[2] if len(parts) > 2 else "",
                         "mechanism": parts[3] if len(parts) > 3 else "",
                         "leads": parts[4] if len(parts) > 4 else "",
                         "duplicate": dup, "probe": "", "reachable": False})
            known.add(name.lower())          # dedup within the sweep too
            got += 1
        print(f"    {seat.split('/')[-1]:<24} {lens_name[:18]:<18} +{got}")

    todo = [r for r in rows if not r["duplicate"]]
    print(f"\nprobing {len(todo)} candidates in parallel...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(probe, [r["url"] for r in todo]))
    for r, st in zip(todo, results, strict=False):
        r["probe"] = st
        r["reachable"] = st.startswith("OK")
    for r in rows:
        if r["duplicate"]:
            r["probe"] = "skipped-dup"

    n_new = sum(1 for r in rows if not r["duplicate"] and r["reachable"])
    print("\n=== NEW + REACHABLE ===")
    for r in rows:
        if not r["duplicate"] and r["reachable"]:
            print(f"  {r['name'][:44]:<44} {r['modality'][:12]:<12} {r['lens'][:20]}")

    with OUT.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
        fh.write(json.dumps({"_summary": True, "date": today, "total": len(rows),
                             "new": n_new, "lenses": len(LENSES)}) + "\n")

    tot = len(rows)
    print(f"\n  {tot} suggestions | {sum(1 for r in rows if r['duplicate'])} known | "
          f"{sum(1 for r in rows if not r['duplicate'] and not r['reachable'])} unreachable | "
          f"{n_new} NEW+REACHABLE")
    print(f"  {novelty_trend(OUT, n_new, tot)}")
    print("  -> Stage-A only, zero promotion authority; enters class map as never-visited")


if __name__ == "__main__":
    main()
