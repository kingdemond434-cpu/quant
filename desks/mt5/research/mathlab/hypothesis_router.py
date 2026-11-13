"""The math lab as a PhD team: concrete hypotheses in, the right mathematics per hypothesis.

WHY THIS EXISTS (principal, 2026-11-13: "funds have thousands of PhD mathematicians, physicists
etc who help discover edges"). The lab used to sweep the world model's residual blind: every
tradition ran on every residual panel, whatever the question. Measured over the 7 days to
2026-11-13 (PRODUCER_YIELD.json 07:55Z): 181 compute-hours for about 0.8 cells an hour reaching
the Judge. A residual has no mechanism, so a tradition cannot be matched to one.

WHAT IT DOES INSTEAD.
1. Reads CONCRETE HYPOTHESES from the moat registry: every discovery that names a mechanism and
   an asset the hypothesis lane may hunt, from any generator except the lab itself (mined
   claims, LLM-lab donations, the tier-1 idea proposer, ...). The newest come first, then
   machine-original ideas, then the desk's breadth gaps (gold, indices, the USD/JPY/EUR crosses).
2. ROUTES each hypothesis to EVERY tradition whose mathematics fits its mechanism, ranked by
   measured yield per compute-hour, adding traditions while the marginal one still earns
   (principal, 2026-11-13: "as much as possible -- that's the ROI"). State-space and change-point
   methods fit regime ideas, hazard and point processes event timing, graph and transfer-entropy
   methods lead-lag, and so on. The choice, rank and reason are logged per hypothesis.
3. Keeps the 90/10 split at the INPUT. At most 10% of the routed panels may be exotic FX
   (a pair with a non-G10 leg). The 2x live-cost bar for exotics belongs to the Judge and the
   promoter and is not re-implemented here.

WHAT IT NEVER DOES. Judge, gate, size or certify. Every object the routed traditions propose
goes through the same registry door, the same compiler, the same Judge and the same ten-gate
gauntlet as everything else, and is charged its search burden there (`burden.record_trials`).
"""
from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any

UNMEASURED = "UNMEASURED"

#: Mechanism classes. EVERY class whose keywords match contributes EVERY fitting tradition it
#: names (principal 2026-11-13: "not just one or two, as much as possible -- that's the ROI"), and
#: `route` then ranks them by measured yield per compute-hour and keeps adding while the marginal
#: tradition still earns. Each entry is (class, keywords, [(tradition, why), ...]); traditions
#: absent from the live registry are skipped at route time, so this table can name one early.
TOOLKIT: tuple[tuple[str, tuple[str, ...], tuple[tuple[str, str], ...]], ...] = (
    ("option_pricing", ("variance risk premium", "implied", "black-scholes", "heston", "kappa",
                        "jump-diffusion", "jump intensity", "bipower", "merton", "bates",
                        "variance swap", "option"),
     (("stochastic_processes", "stochastic calculus is the native language of option-derived "
                               "quantities: diffusions, stochastic variance and jump processes"),
      ("stochastic_physics", "Langevin/Fokker-Planck models fit variance with mean reversion"),
      ("rough_path_signatures", "signatures capture the path roughness behind implied-vs-realised"),
      ("extreme_value", "extreme-value theory models the jump component's size distribution"),
      ("anomalous_diffusion", "anomalous diffusion separates jumps from continuous diffusion"),
      ("turbulence", "multi-scale cascades model variance across horizons"))),
    ("regime", ("regime", "state", "switch", "transition", "risk-on", "risk off", "risk-off",
                "hmm", "structural break"),
     (("dynamical_systems", "state-space dynamics fit a mechanism that changes state"),
      ("change_point", "change-point detection locates the regime switch itself"),
      ("recurrence_quantification", "recurrence plots show when the system revisits a state"),
      ("takens_reconstruction", "delay embedding recovers the hidden state the regime lives in"),
      ("koopman_dmd", "Koopman modes separate the persistent states from the transients"),
      ("criticality", "critical slowing down warns before a regime flips"),
      ("statistical_mechanics", "phase-transition models describe collective state changes"))),
    ("event_timing", ("announcement", "release", "auction", "event", "fomc", "nfp", "cpi",
                      "earnings", "fixing", "fix ", "expiry", "rollover", "data surprise"),
     (("survival_hazard", "hazard models price WHEN a reaction starts and stops"),
      ("stochastic_processes", "point processes model event arrival and its decay"),
      ("linear_response", "response functions measure how a shock decays after the event"),
      ("change_point", "change-point detection finds where the event moved the series"),
      ("sequential_pattern_mining", "sequence mining finds the ordered steps around events"),
      ("matrix_profile", "matrix profiles find the recurring event-window motif"))),
    ("lead_lag", ("lead", "lag", "spillover", "cross-asset", "cross asset", "contagion",
                  "propagat", "network", "follows", "drives"),
     (("graph_theory", "graph methods map who moves first across instruments"),
      ("transfer_entropy", "transfer entropy measures directed information flow"),
      ("causal", "causal discovery separates the leader from a common driver"),
      ("network_physics", "network dynamics model how a move propagates"),
      ("information_physics", "directed information bounds what the leader can reveal"),
      ("tensor_decomposition", "tensor factors find the shared cross-asset components"))),
    ("calendar", ("session", "calendar", "hour", "weekday", "weekend", "holiday", "month-end",
                  "month end", "seasonal", "intraday", "overnight", "open", "close"),
     (("spectral", "spectral methods isolate fixed periodicities"),
      ("wavelet_scattering", "wavelets localise a pattern in both time and frequency"),
      ("matrix_profile", "matrix profiles find the same intraday shape repeating"),
      ("symmetry_invariance", "invariance tests check the pattern holds across days"),
      ("sequential_pattern_mining", "sequence mining finds the ordered session steps"))),
    ("tail", ("tail", "crash", "jump", "extreme", "gap", "squeeze", "liquidation", "stop"),
     (("extreme_value", "extreme-value theory models the tail the mechanism lives in"),
      ("tail_dependence", "tail dependence measures co-crashes across instruments"),
      ("anomalous_diffusion", "anomalous diffusion models jump-heavy price paths"),
      ("chaos_tests", "chaos tests tell a deterministic cascade from noise"),
      ("monte_carlo_abm", "agent simulations reproduce forced-liquidation cascades"))),
    ("flow_positioning", ("flow", "positioning", "crowd", "retail", "footprint", "hedger",
                          "dealer", "carry trade", "cot", "sentiment", "intervention"),
     (("game_theory_ecology", "participant ecology models who is forced to trade"),
      ("information_theory", "information measures read how much the flow reveals"),
      ("monte_carlo_abm", "agent simulations test whether the forced flow moves price"),
      ("control_theory", "control models describe a hedger steering a book back to target"),
      ("optimal_transport", "transport maps compare positioning distributions over time"))),
    ("mean_reversion", ("revert", "reversion", "spread", "basis", "cointegrat", "fair value",
                        "dislocation", "residual", "overreaction"),
     (("stochastic_processes", "mean-reverting processes fit a pull back to value"),
      ("koopman_dmd", "Koopman/DMD extracts the decaying modes of the spread"),
      ("conservation_laws", "conserved quantities pin the fair-value relation"),
      ("control_theory", "control models describe the restoring force"),
      ("sindy", "sparse identification finds the restoring equation itself"),
      ("geometry", "geometric methods measure distance from the fair-value manifold"))),
    ("momentum", ("momentum", "trend", "breakout", "continuation", "drift", "persistence"),
     (("dynamical_systems", "trend persistence is a dynamical-systems question"),
      ("symbolic_regression", "symbolic regression searches the trend rule's form"),
      ("anomalous_diffusion", "superdiffusion measures persistence directly"),
      ("renormalisation", "scaling across horizons tests whether the trend is real"),
      ("reservoir_computing", "reservoirs learn path-dependent continuation"),
      ("sindy", "sparse identification finds the drift equation"))),
    ("volatility", ("volatility", " vol ", "variance", "vix", "gvz", "ovx", "realised",
                    "realized", "implied"),
     (("rough_path_signatures", "signatures capture the path roughness volatility lives in"),
      ("stochastic_processes", "stochastic-volatility processes model the variance itself"),
      ("turbulence", "turbulence cascades model volatility across scales"),
      ("stochastic_physics", "Langevin models fit variance with feedback"),
      ("random_matrix", "random-matrix filters separate real co-volatility from noise"))),
    ("causal_macro", ("macro", "policy", "rate", "yield", "inflation", "liquidity", "central bank",
                      "term premium", "balance sheet"),
     (("causal", "causal discovery separates the driver from the coincidence"),
      ("transfer_entropy", "directed information confirms the driver leads"),
      ("inverse_problems", "inverse methods recover the unobserved policy driver"),
      ("dimensional_analysis", "dimensional analysis keeps the macro relation unit-consistent"),
      ("field_continuum", "continuum models describe liquidity spreading across markets"))),
)
DEFAULT_TOOLS: tuple[tuple[str, str], ...] = (
    ("symbolic_regression", "no mechanism class matched: search the rule's functional form"),
    ("information_theory", "no mechanism class matched: measure what the inputs reveal at all"),
)

G10 = frozenset({"USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "SEK", "NOK", "DKK"})
#: The breadth gaps the hourly pass names (gold, indices, the USD/JPY/EUR crosses).
GAP_PREFIXES = ("XAU", "US500", "US30", "NAS100", "USTEC", "GER40", "DE40", "UK100", "JP225",
                "JPN225", "EU50", "STOXX50")
GAP_CCY = frozenset({"USD", "JPY", "EUR"})
EXOTIC_SHARE = 0.10
MAX_HYPOTHESES = 400
#: Routing-log rows kept in MATH_LAB.json (the full count is in the status).
MAX_LOG = 200
#: The LLM lab's newest donation files read per pass.
NEWEST_DONATION_FILES = 6


def is_fx_pair(symbol: str) -> bool:
    core = re.sub(r"[^A-Z]", "", symbol.upper())[:6]
    return len(core) == 6 and core[:3].isalpha() and core[3:].isalpha() and (
        core[:3] in G10 or core[3:] in G10) and not core.startswith(("XAU", "XAG", "XPT", "XPD"))


def is_exotic(symbol: str) -> bool:
    """An FX pair with a non-G10 leg. Metals, indices, energy and softs are never exotic here."""
    if not is_fx_pair(symbol):
        return False
    core = re.sub(r"[^A-Z]", "", symbol.upper())[:6]
    return core[:3] not in G10 or core[3:] not in G10


def gap_weight(symbol: str) -> int:
    """2 for gold and the named indices, 1 for a USD/JPY/EUR cross, 0 otherwise."""
    upper = symbol.upper()
    if upper.startswith(GAP_PREFIXES):
        return 2
    if is_fx_pair(upper):
        core = re.sub(r"[^A-Z]", "", upper)[:6]
        if core[:3] in GAP_CCY and core[3:] in GAP_CCY:
            return 1
    return 0


def cap_exotics(symbols: list[str], slots: int) -> list[str]:
    """The first `slots` symbols in order, with exotic FX held to EXOTIC_SHARE of them.

    A held-back exotic is used only when nothing else fills a slot at all, so the cap never
    leaves the lab with no panel.
    """
    allowed_exotic = int(slots * EXOTIC_SHARE)
    out: list[str] = []
    held: list[str] = []
    for symbol in symbols:
        if len(out) >= slots:
            break
        if symbol in out:
            continue
        if is_exotic(symbol) and sum(is_exotic(t) for t in out) >= allowed_exotic:
            held.append(symbol)
            continue
        out.append(symbol)
    if not out and held:
        out = held[:1]
    return out


def _assets(row: dict[str, Any]) -> list[str]:
    raw = row.get("assets_json") or row.get("assets") or "[]"
    try:
        names = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, ValueError):
        return []
    return [str(n) for n in names if n]


def mechanism_text(row: dict[str, Any]) -> str:
    parts = (row.get("mechanism"), row.get("economic_rationale"), row.get("constraint_text"),
             row.get("information"))
    return " ".join(str(p) for p in parts if p).strip()


def load_hypotheses(allowed: list[str], *, conn: Any = None, limit: int = MAX_HYPOTHESES
                    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Concrete hypotheses on hunt-able symbols, newest first, with the reason each was kept.

    Reads the registry's `discoveries` table directly so the NEWEST rows come first
    (`registry.discoveries` orders oldest-first, which would starve today's ideas).
    """
    status: dict[str, Any] = {"source": "libs/moat/registry.py discoveries"}
    allowed_set = {s.upper(): s for s in allowed}
    try:
        from libs.moat import registry as reg
        c = conn or reg.connect()
    except Exception as exc:
        status.update(status=UNMEASURED, why=f"registry unopenable: {type(exc).__name__}")
        return [], status
    try:
        rows = [dict(r) for r in c.execute(
            "SELECT discovery_id, generator, origin, mechanism, economic_rationale,"
            " constraint_text, information, assets_json, created_at, state FROM discoveries"
            " WHERE COALESCE(generator,'') NOT LIKE 'math:%'"
            " AND COALESCE(generator,'') <> 'residual_hunt'"
            " AND COALESCE(mechanism,'') <> ''"
            " ORDER BY created_at DESC LIMIT ?", (int(limit) * 5,)).fetchall()]
    except Exception as exc:
        status.update(status=UNMEASURED, why=f"discoveries unreadable: {type(exc).__name__}")
        return [], status
    finally:
        if conn is None:
            with contextlib.suppress(Exception):
                c.close()
    out: list[dict[str, Any]] = []
    no_symbol = 0
    for row in rows:
        targets = [allowed_set[a.upper()] for a in _assets(row) if a.upper() in allowed_set]
        if not targets:
            no_symbol += 1
            continue
        origin = str(row.get("origin") or "")
        for target in targets[:2]:
            out.append({
                "hypothesis_id": str(row.get("discovery_id")),
                "generator": str(row.get("generator") or ""),
                "origin": origin,
                "target": target,
                "mechanism": mechanism_text(row)[:400],
                "created_at": str(row.get("created_at") or ""),
                "original": origin.upper() in {"DESK", "ORIGINAL", "LLM", "INVENTED"},
                "gap_weight": gap_weight(target),
                "exotic": is_exotic(target),
            })
        if len(out) >= limit:
            break
    status.update(status="MEASURED", read=len(rows), kept=len(out),
                  set_aside_no_huntable_symbol=no_symbol)
    return out, status


def _gap_tags(row: dict[str, Any]) -> list[str]:
    raw = row.get("breadth_gap") or row.get("breadth_gaps") or row.get("gap_tags") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(t) for t in raw if t] if isinstance(raw, (list, tuple)) else []


def _row_symbols(row: dict[str, Any]) -> list[str]:
    raw = (row.get("symbols") or row.get("candidate_symbols")
           or ([row["symbol"]] if row.get("symbol") else []))
    return [str(s) for s in raw if s] if isinstance(raw, (list, tuple)) else []


def _file_rows(path: Path) -> list[dict[str, Any]]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    rows = (doc.get("discoveries") or doc.get("ideas") or []) if isinstance(doc, dict) else doc
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def load_file_ideas(allowed: list[str], *, idea_files: list[Path | tuple[str, Path]],
                    donation_dirs: list[Path],
                    newest_files: int = NEWEST_DONATION_FILES
                    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Ideas that live in FILES rather than the registry, original ones first.

    Two sources. `idea_files`: the tier-1 IDEA_QUEUE's [ORIG] rows, mirrored into the repo with
    their MT5 symbols (`desks/mt5/data/hypotheses/orig_ideas.json`), because the box cannot read
    the project's shared folder. `donation_dirs`: the LLM lab's donations
    (`data/intelligence/llm_lab/discoveries_*.json`), whose rows carry `orig` and `breadth_gap`
    tags. A row tagged `orig` counts as an original idea; a `breadth_gap` tag adds one to its
    gap weight on top of the symbol's own.
    """
    allowed_set = {s.upper(): s for s in allowed}
    status: dict[str, Any] = {"idea_files": [], "donation_files": [], "rows": 0,
                              "set_aside_no_huntable_symbol": 0}
    sources: list[tuple[str, Path]] = []
    for item in idea_files:
        generator, path = item if isinstance(item, tuple) else ("idea_queue", item)
        if path.exists():
            sources.append((generator, path))
    for d in donation_dirs:
        if d.is_dir():
            newest = sorted(d.glob("discoveries_*.json"))[-newest_files:]
            sources += [("llm_lab", p) for p in newest]
    out: list[dict[str, Any]] = []
    for generator, path in sources:
        rows = _file_rows(path)
        status["donation_files" if generator == "llm_lab" else "idea_files"].append(
            {"path": path.name, "generator": generator, "rows": len(rows)})
        for i, row in enumerate(rows):
            status["rows"] += 1
            targets = [allowed_set[s.upper()] for s in _row_symbols(row)
                       if s.upper() in allowed_set]
            if not targets:
                status["set_aside_no_huntable_symbol"] += 1
                continue
            tags = _gap_tags(row)
            # An explicit `"orig": false` is honoured on every source; only an IDEA_QUEUE row
            # that says nothing defaults to original, because that file mirrors [ORIG] rows.
            original = bool(row.get("orig", generator == "idea_queue"))
            competing = row.get("competing_explanations") or []
            if isinstance(competing, (list, tuple)):
                competing = " ".join(str(c) for c in competing)
            mechanism = " ".join(str(row.get(k) or "") for k in (
                "mechanism_class", "mechanism", "title")).strip() + " " + " ".join(
                str(v) for v in (competing, row.get("separating_test"), row.get("falsifier"))
                if v)
            revision = str(row.get("lab") or "").upper() == "REVISION"
            hid = str(row.get("id") or row.get("cell_id") or f"{path.stem}:{i}")
            for target in targets[:2]:
                out.append({"hypothesis_id": hid, "generator": generator,
                            "origin": "ORIGINAL" if original else "", "target": target,
                            "mechanism": mechanism[:400], "created_at": str(
                                row.get("at") or row.get("created_at") or ""),
                            "original": original, "breadth_gap": tags,
                            "traditions": [str(t) for t in row.get("traditions") or []],
                            # The first test to formalise: the LLM lab's separating test, then
                            # the falsifier (LLM lab hand-off, 2026-11-13).
                            "first_test": str(row.get("separating_test")
                                              or row.get("falsifier") or "")[:400],
                            "refereed_revision": revision,
                            "gap_weight": gap_weight(target) + (1 if tags else 0),
                            "exotic": is_exotic(target)})
    # Original ideas and referee-hardened revisions first, then breadth gaps; nothing is
    # dropped, so the breadth of what the labs propose is kept and only the order changes.
    out.sort(key=lambda h: (not (h["original"] or h["refereed_revision"]), -h["gap_weight"]))
    status.update(status="MEASURED", kept=len(out),
                  original=sum(1 for h in out if h["original"]))
    return out, status


def route(hypothesis: dict[str, Any], registry: Any, yields: dict[str, float | None] | None = None,
          zero_yield: Any = ()) -> list[dict[str, Any]]:
    """EVERY tradition whose mathematics fits this hypothesis, ranked by measured yield per
    compute-hour, kept while the marginal one still earns.

    Order: traditions with positive measured yield (best first), then unpriced ones -- not enough
    compute yet to say, and running them is how their yield gets measured. A tradition with
    enough compute and zero on every rung is the marginal one that no longer earns and is left
    out, unless it is the only fitting tradition, so no hypothesis is left untested. Every extra
    tradition's search is charged to the trial count exactly as before (burden.record_trials).
    """
    text = f" {str(hypothesis.get('mechanism') or '').lower()} "
    fitting: list[dict[str, Any]] = []
    for klass, keywords, tools in TOOLKIT:
        hit = next((k for k in keywords if k in text), None)
        if hit is None:
            continue
        for tradition, why in tools:
            if tradition in registry and all(c["tradition"] != tradition for c in fitting):
                fitting.append({"tradition": tradition, "class": klass, "keyword": hit.strip(),
                                "why": why})
    if not fitting:
        fitting = [{"tradition": t, "class": "unclassified", "keyword": "", "why": why}
                   for t, why in DEFAULT_TOOLS if t in registry]
    # A hypothesis may NAME the mathematics it needs (`traditions`): those are pinned, ranked
    # first and never dropped by the zero-yield rule -- the zero was earned on other questions.
    pinned = [t for t in (hypothesis.get("traditions") or []) if t in registry]
    for t in reversed(pinned):
        fitting = [e for e in fitting if e["tradition"] != t]
        fitting.insert(0, {"tradition": t, "class": "named_by_hypothesis", "keyword": "",
                           "why": "the hypothesis names this mathematics itself"})
    zero = set(zero_yield or ()) - set(pinned)
    measured = yields or {}
    for i, entry in enumerate(fitting):
        value = measured.get(entry["tradition"])
        entry["expected_yield_per_h"] = value
        entry["order"] = i
        entry["tier"] = ("pinned" if entry["tradition"] in pinned else
                         "zero_yield" if entry["tradition"] in zero else
                         "earning" if isinstance(value, (int, float)) and value > 0 else
                         "unpriced")
    rank = {"pinned": -1, "earning": 0, "unpriced": 1, "zero_yield": 2}
    fitting.sort(key=lambda e: (rank[e["tier"]], -(e["expected_yield_per_h"] or 0.0), e["order"]))
    kept = [e for e in fitting if e["tier"] != "zero_yield"] or fitting[:1]
    for entry in kept:
        entry.pop("order", None)
    return kept


def plan(hypotheses: list[dict[str, Any]], registry: Any, max_targets: int, *,
         yields: dict[str, float | None] | None = None, zero_yield: Any = ()
         ) -> tuple[list[str], dict[str, list[str]], list[dict[str, Any]], dict[str, Any]]:
    """(targets, tradition -> targets, routing log, status).

    Targets are ranked by how many hypotheses name them, original ideas and breadth gaps first;
    exotic targets are held to EXOTIC_SHARE of the slots (at least one slot only when nothing
    else is available).
    """
    log: list[dict[str, Any]] = []
    score: dict[str, float] = {}
    exotic: dict[str, bool] = {}
    for h in hypotheses:
        tools = route(h, registry, yields, zero_yield)
        log.append({"hypothesis_id": h["hypothesis_id"], "target": h["target"],
                    "generator": h["generator"], "origin": h["origin"],
                    "original": bool(h["original"]),
                    "first_test": str(h.get("first_test") or "")[:200],
                    "breadth_gap": list(h.get("breadth_gap") or []),
                    "mechanism": h["mechanism"][:160], "tools": tools})
        score[h["target"]] = score.get(h["target"], 0.0) + 1.0 + 2.0 * float(h["original"]) \
            + float(h["gap_weight"])
        exotic[h["target"]] = bool(h["exotic"])
    ranked = sorted(score, key=lambda s: (-score[s], s))
    targets = cap_exotics(ranked, max_targets)
    held_back = [s for s in ranked if exotic.get(s) and s not in targets]
    by_tradition: dict[str, list[str]] = {}
    for entry in log:
        if entry["target"] not in targets:
            continue
        for tool in entry["tools"]:
            panels = by_tradition.setdefault(tool["tradition"], [])
            if entry["target"] not in panels:
                panels.append(entry["target"])
    status = {"hypotheses": len(hypotheses), "logged": len(log), "targets": targets,
              "exotic_held_back": held_back[:20], "exotic_share_cap": EXOTIC_SHARE,
              "traditions_routed": sorted(by_tradition),
              "rule": ("each hypothesis is routed to EVERY tradition whose mathematics fits its "
                       "mechanism, ranked by yield per compute-hour and kept while the marginal "
                       "one still earns; targets ranked by hypothesis count, original ideas and "
                       "breadth gaps first; exotics held to 10% of target slots")}
    return targets, by_tradition, log, status
