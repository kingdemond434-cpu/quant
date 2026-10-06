"""IS OUR OWN BOOK MARTINGALE-SHAPED? -- Aurum's forensics, pointed inward.

`provider_reverse` was ported from the Aurum desk to read a COPY PROVIDER's mechanism out of its
fills. The desk mines 205 mql5_signals captures and 205 darwinex ones, so that was the obvious
target -- and it is not usable yet, which is worth stating rather than hiding: those captures are
raw PAGE HTML, not per-fill rows. Feeding an HTML blob to a module that wants `Trade(ticket,
symbol, direction, lots, open_utc, ...)` would be fabrication dressed as analysis, so it is not
done. When the provider miner starts extracting fills, the same functions read them unchanged.

WHAT THE DESK CAN ANSWER TODAY, and it is the more urgent question anyway: does the desk's OWN
book have the structure it would condemn in somebody else's? `data/live_ledger.jsonl` holds real
fills from the live account on FusionMarkets-Live -- entry, exit, lots, SL, TP, realised PnL -- and
that is exactly the shape `build_baskets` -> `infer_structure` -> `ruin_forensics` consumes.

WHY IT MATTERS MORE THAN IT SOUNDS. The principal asked on 2026-09-12 about an EA advertising a
91.67% win rate, 73 consecutive wins, max 2 consecutive losses and a Sharpe of 43.65. The answer
was that those numbers diagnose a martingale: you win small constantly and the loss is deferred,
not avoided, so the curve looks impossibly smooth right up until it is not. A desk that can say
that about somebody else's book and has never checked its own is asserting, not measuring. This
measures.

UNMEASURED IS THE EXPECTED ANSWER AT FIRST, AND IT IS A REAL ONE. `infer_structure` needs enough
baskets to separate a ladder from a coincidence, and the live ledger currently holds a handful of
fills. Reporting UNMEASURED against a stated minimum is the honest output; reporting "no
martingale detected" off four trades would be the lie L1.28a exists to prevent.

    python desks/mt5/research/book_forensics.py [--apply] [--genome]

THE PUBLIC TRADER GENOME, WITH ITS GRAVEYARD (2026-10-06; Asia directive PART XIV, global PART
XXIII, audit row 35). The same forensics, pointed outward at the population rather than at one
provider. `build_genome` writes one structural row per public trader or system -- source,
culture, market, instruments, holding period, style tags (provider_reverse.summary_signature),
drawdown, lifespan and OUTCOME -- from the seats the desk already harvests (FX Blue statements via
`fxblue_mechanism_summary.genome_records`, competition ranking tables via
`deep_forest_miner.competition_rows`), and it KEEPS THE DEAD: delisted statements, emptied and
blown accounts, traders who stopped. Mechanism base rates are then measured over alive + dead,
so a style's success rate is P(alive and profitable | style) over everyone who tried it, printed
beside the survivor-only rate it replaces and the inflation between the two.

Three things leave it, all through doors that already exist:
  * candidate cells -- each style with a registered family analogue is screened on the desk's
    bars (proposer_common.screen -> deflate -> donate); every screen is a trial, null passes
    included, and the genome's own contrasts are counted into the same charge;
  * failure memory -- styles whose death rate is significantly above the population's are
    published in data/trader_genome_priors.json, which failure_prior reads into FAILURE_PRIOR;
  * a crowding prior -- the share of the public population (alive + dead) trading each symbol
    and style, stamped on every candidate this file donates.

THE TERMS GATE FAILS CLOSED. Every source carries a TERMS entry; a `refused` source is counted
and never enters the genome, a `to_confirm` source is held in the dataset flagged but feeds no
base rate, prior or candidate (BLOCKED_ON_TERMS) until a human records the terms here with the
URL and the verbatim quote (TERMS_EVIDENCE). PIT: a row is knowable only from its own
publication date (`knowable_from`); `as_of` drops every row the desk could not have read yet.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
LEDGER = DESK / "data" / "live_ledger.jsonl"
OUT = DESK / "reports" / "BOOK_FORENSICS.json"
GENOME = DESK / "data" / "trader_genome.parquet"
GENOME_REPORT = DESK / "reports" / "TRADER_GENOME.json"
PRIORS = DESK / "data" / "trader_genome_priors.json"
COMPETITION = DESK / "data" / "trader_genome_competition.jsonl"
INTEL = DESK / "data" / "intelligence"
#: Side ledger of looks from passes that donated nothing; experiment_ledger adds it to the
#: lifetime trial count (written through alt_proxies._donate, the desk's one null-pass helper).
NULL_TRIALS = DESK / "data" / "null_pass_trials.jsonl"
SOURCE = "trader_genome"


def _reverse():
    """Load the ported module by path, registered so dataclasses can resolve it."""
    spec = importlib.util.spec_from_file_location(
        "provider_reverse", DESK / "research" / "provider_reverse.py")
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["provider_reverse"] = mod
    spec.loader.exec_module(mod)
    return mod


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _trades(mod) -> tuple[list, list[str]]:
    """Ledger rows -> Trade objects, and the rows that could not be read.

    MT5 encodes side as 0/1 rather than BUY/SELL, and the ledger's `time` is the CLOSE. The entry
    instant is not recorded per row, so open_utc falls back to the close: that flattens the
    HOLDING PERIOD, which `build_baskets` uses only to decide which fills belong together inside
    BASKET_WINDOW. The distortion is recorded here rather than left for a reader to discover,
    because a basket window applied to collapsed timestamps groups more aggressively than it
    should -- it can merge, never split, so it biases toward FINDING structure. A finding under a
    bias toward finding is worth less, and saying so is the difference between analysis and a
    number.
    """
    rows: list = []
    skipped: list[str] = []
    try:
        lines = LEDGER.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"ledger unreadable: {type(exc).__name__}: {exc}"]
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            skipped.append("unparseable json line")
            continue
        close = _ts(r.get("time"))
        sym = str(r.get("symbol") or "")
        lots = r.get("volume")
        entry = r.get("entry_price")
        if not (sym and close and lots and entry):
            skipped.append(f"{r.get('deal')}: missing symbol/time/volume/entry_price")
            continue
        side = r.get("side")
        direction = "BUY" if side in (0, "0", "BUY", "buy") else "SELL"
        try:
            rows.append(mod.Trade(
                ticket=str(r.get("deal") or r.get("order") or "?"),
                symbol=sym, direction=direction, lots=float(lots),
                open_utc=close, close_utc=close,
                open_price=float(entry),
                close_price=(float(r["fill_price"]) if r.get("fill_price") is not None else None),
                sl=(float(r["sl"]) if r.get("sl") else None),
                tp=(float(r["tp"]) if r.get("tp") else None),
                profit=(float(r["pl_quote"]) if r.get("pl_quote") is not None else None),
            ))
        except (TypeError, ValueError) as exc:
            skipped.append(f"{r.get('deal')}: {type(exc).__name__}: {exc}")
    return rows, skipped


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    mod = _reverse()
    if mod is None:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": "provider_reverse not loadable -- UNMEASURED, never 'no structure'"}

    trades, skipped = _trades(mod)
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"),
        "source": str(LEDGER.relative_to(ROOT)),
        "n_trades": len(trades),
        "n_skipped": len(skipped),
        "skipped": skipped[:10],
        "min_baskets_required": getattr(mod, "MIN_BASKETS", None),
        "open_utc_caveat": ("the ledger records the CLOSE instant only, so open_utc falls back to "
                            "it. That collapses holding periods and makes the basket window group "
                            "more aggressively than it should -- it can merge, never split, so it "
                            "biases toward FINDING structure, and a finding under that bias is "
                            "worth correspondingly less."),
    }
    if not trades:
        doc |= {"status": "UNMEASURED",
                "why": "no readable fills in the live ledger -- absence of trades is not absence "
                       "of structure (L1.28a)"}
        return doc

    try:
        baskets = mod.build_baskets(trades)
        doc["n_baskets"] = len(baskets)
        need = int(getattr(mod, "MIN_BASKETS", 0) or 0)
        if len(baskets) < need:
            doc |= {"status": "UNMEASURED",
                    "why": (f"{len(baskets)} basket(s) against a stated minimum of {need}. "
                            f"Reporting 'no martingale' from fewer would be exactly the claim "
                            f"L1.28a forbids -- the desk has not traded enough for this question "
                            f"to have an answer yet.")}
            return doc
        structure = mod.infer_structure(baskets)
        doc["structure"] = (
            {k: v for k, v in vars(structure).items() if not k.startswith("_")}
            if hasattr(structure, "__dict__") else str(structure))
        forensics = mod.ruin_forensics(baskets, structure, equity=None)
        doc["ruin_forensics"] = ({k: v for k, v in vars(forensics).items()
                                  if not k.startswith("_")}
                                 if hasattr(forensics, "__dict__") else str(forensics))
        doc["status"] = "OK"
    except Exception as exc:
        doc |= {"status": "UNMEASURED",
                "why": f"forensics raised {type(exc).__name__}: {exc}"}
    return doc


# ================================================================== the public trader genome

#: THE TERMS GATE, FAIL CLOSED (same vocabulary as alt_proxies.TERMS). `confirmed` only where a
#: human has read the source's terms and recorded the URL and verbatim quote in TERMS_EVIDENCE.
#: Competition grounds are keyed `competition:<ground name>`; an unlisted key is `to_confirm`.
TERMS: dict[str, tuple[str, str]] = {
    "fxblue": ("to_confirm", "fxblue.com robots.txt disallows fetching /terms and /legal/terms "
               "from this host (2026-10-06); the terms have not been read"),
    "mql5_signals": ("refused", "MQL5 Terms of Use 3.7 forbid automated access and 3.9 forbid "
                     "reproducing site content"),
    "mql5_survivors": ("refused", "MQL5 Terms of Use 3.7 / 3.9 / 3.13 (same site as "
                       "mql5_signals)"),
    "darwinex": ("to_confirm", "website terms refused to this host by robots.txt "
                 "(2026-10-06); the DARWIN API T&C limit Darwinex Data to 'internal purposes' "
                 "within a registered Application, which the desk does not hold (no key) -- "
                 "not a clause permitting automated use of the public site's statistics"),
    "collective2": ("refused", "Collective2 Terms of Service s.9 forbid derivative works from "
                    "platform content and s.7 forbid scraping protected material"),
    "myfxbook": ("to_confirm", "seat walled (Cloudflare managed challenge, never bypassed); no "
                 "public-systems API; terms not read"),
}
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "mql5_signals": {
        "url": "https://www.mql5.com/en/about/terms", "checked": "2026-10-06",
        "quote": ("3.7: \"You agree not to access the website www.mql5.com through any automated "
                  "means, including use of scripts, crawlers, or similar technologies.\" 3.9: "
                  "\"You agree that You will not reproduce, duplicate, copy, sell, trade or "
                  "resell the content of the website www.mql5.com\"")},
    "mql5_survivors": {
        "url": "https://www.mql5.com/en/about/terms", "checked": "2026-10-06",
        "quote": ("3.13: \"You will not copy, sell, license, distribute, transfer, modify, "
                  "adapt, translate, prepare derivative works from ...\"")},
    "fxblue": {
        "url": "https://www.fxblue.com/terms", "checked": "2026-10-06",
        "quote": ("NOT READ: the fetch was refused by the site's robots.txt from this host "
                  "(re-tried 2026-10-06 at /terms and /legal/terms; same refusal, not "
                  "bypassed)")},
    "darwinex": {
        "url": "https://darwinex.com/cs/legal/darwin-api-conditions", "checked": "2026-10-06",
        "quote": ("DARWIN API T&C: \"You may only use such Darwinex Data for your internal "
                  "purposes or within your Application\"; \"you will not disclose, sell or "
                  "transfer any Darwinex Data without our prior written consent\". Website "
                  "terms (darwinex.com/legal, /legal/terms-of-use) NOT READ: robots.txt refused "
                  "the fetch, not bypassed. Fenced: no clause permits automated use of the "
                  "public site, and the API route needs an account the desk does not hold")},
    "collective2": {
        "url": "https://collective2.com/terms-of-service", "checked": "2026-10-06",
        "quote": ("s.7: \"scrape, copy, resell, or redistribute paid strategy content or other "
                  "protected material except as expressly allowed\"; s.9: \"you may not copy, "
                  "modify, distribute, license, sell, reverse engineer, or create derivative "
                  "works from the Service or platform content\"")},
}
#: The seats the genome census reads, so a walled seat is a counted absence, not a silence.
SEATS = ("fxblue", "mql5_signals", "mql5_survivors", "darwinex", "collective2",
         "myfxbook_outlook")
#: A style needs this many population rows (alive + dead) before its base rate is a number.
MIN_TAG_N = 10
#: Deflated z for a style to enter failure memory / be ranked as a persistence signature.
SIGNIF_Z = 2.0
#: Desk symbols screened per style (the population's most-traded with bars on this box).
SYMBOLS_PER_STYLE = 3
MIN_BARS = 3000
#: Style -> registered family analogue. "Improve, do not clone" (provider_reverse): the
#: martingale / no-stop styles are screened as their ENTRY with a hard stop and fixed size, never
#: as the recovery ladder. Session styles are absent on purpose: the statements' hour histograms
#: are on each broker's own clock, and mapping them to the desk's UTC bars would be a guess.
STYLE_FAMILY: dict[str, tuple[str, dict[str, Any], str]] = {
    "positive_skew": ("trend_ma_cross", {}, "positively skewed per-trade P&L: let winners run"),
    "pyramiding_size": ("trend_ma_cross", {"ttl_bars": 24},
                        "size added as the account grows: trend persistence"),
    "high_win_rate": ("mean_reversion_bollinger", {"rr": 1.0},
                      "many small wins: fade the stretch, take profit early, hard stop"),
    "martingale_signature": ("mean_reversion_bollinger", {"rr": 1.8},
                             "the martingale's entry with the recovery layer stripped"),
    "no_hard_stop": ("range_reversion", {},
                     "the no-stop book's range entry, with a stop it never had"),
    "negative_skew": ("range_reversion", {"rr": 1.0},
                      "short-vol shape: range fade with a hard stop"),
    "single_instrument": ("pullback_entry", {}, "specialist on one instrument: trend pullback"),
}


def terms_of(source: str) -> str:
    return TERMS.get(source, ("to_confirm", "not listed"))[0]


def _fxblue() -> Any:
    spec = importlib.util.spec_from_file_location(
        "fxblue_mechanism_summary", DESK / "scripts" / "fxblue_mechanism_summary.py")
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _competition_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """Competition ledger -> genome rows, newest sighting per competitor."""
    p = path or COMPETITION
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    best: dict[str, dict[str, Any]] = {}
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        key = f"comp:{r.get('ground')}:{r.get('group') or ''}:{r.get('name')}"
        prev = best.get(key)
        if prev is None or str(r.get("available_time", "")) >= str(prev.get("available_time", "")):
            best[key] = r
    out = []
    for key, r in best.items():
        dd = r.get("max_dd_pct")
        tags = ["deep_drawdown"] if isinstance(dd, (int, float)) and dd <= -50.0 else []
        ret = r.get("return_pct")
        lang, region = str(r.get("language") or ""), str(r.get("region") or "")
        out.append({
            "trader_id": key, "source": f"competition:{r.get('ground')}",
            "culture": f"{region}/{lang}".strip("/") or None, "account_type": "Real",
            "currency": None, "market": "futures_competition", "instruments": [],
            "outcome": r.get("outcome") or "ALIVE", "outcome_why": r.get("outcome_why"),
            "dead": r.get("outcome") == "BLOWN",
            "profitable": (ret > 0) if isinstance(ret, (int, float)) else None,
            "first_active": None, "last_active": None, "survival_days": None,
            "published_time": r.get("published_time"), "available_time": r.get("available_time"),
            # THE FETCH, NEVER THE PAGE'S META DATE: rankings are republished in place, so the
            # meta date predates the standings the fetch read (deep_forest_miner.competition_rows).
            "knowable_from": r.get("available_time"),
            "n_trades_sampled": 0, "win_rate": None, "payoff_ratio": None, "skew": None,
            "tail_ratio": None, "median_hold_raw": None, "max_dd_pct": dd,
            "top_symbol_share": None, "session": None, "session_share": None,
            "lot_escalation": None, "hold_unit": None, "session_clock": None,
            "style_tags": tags})
    return out


def _seat_census() -> dict[str, Any]:
    """What each harvested seat holds: usable records, or the wall it reports."""
    import gzip
    out: dict[str, Any] = {}
    for seat in SEATS:
        d = INTEL / seat
        kinds: dict[str, int] = {}
        files = sorted(d.glob("rollup_*.jsonl.gz")) if d.exists() else []
        for f in files:
            try:
                with gzip.open(f, "rt", encoding="utf-8") as fh:
                    for ln in fh:
                        if ln.strip():
                            k = str(json.loads(ln).get("kind"))
                            kinds[k] = kinds.get(k, 0) + 1
            except (OSError, ValueError, EOFError):
                continue
        key = "myfxbook" if seat == "myfxbook_outlook" else seat
        out[seat] = {"present": d.exists(), "rollups": len(files), "kinds": kinds,
                     "terms": terms_of(key), "terms_why": TERMS.get(key, ("", ""))[1]}
    return out


def _hold_tags(rows: list[dict[str, Any]]) -> None:
    """Holding-period terciles WITHIN each source (units are each publisher's own)."""
    by: dict[str, list[float]] = {}
    for r in rows:
        if isinstance(r.get("median_hold_raw"), (int, float)):
            by.setdefault(r["source"], []).append(float(r["median_hold_raw"]))
    cut: dict[str, tuple[float, float]] = {}
    for src, xs in by.items():
        xs = sorted(xs)
        if len(xs) >= 9:
            cut[src] = (xs[len(xs) // 3], xs[2 * len(xs) // 3])
    for r in rows:
        c = cut.get(r["source"])
        h = r.get("median_hold_raw")
        if c is None or not isinstance(h, (int, float)):
            continue
        tag = "hold_short" if h <= c[0] else ("hold_long" if h > c[1] else "hold_mid")
        r["style_tags"] = sorted(set(r["style_tags"]) | {tag})


def build_genome(fxblue_paths: list[Path] | None = None,
                 competition_path: Path | None = None) -> tuple[list[dict[str, Any]],
                                                                dict[str, Any]]:
    """(rows, census). Refused sources are counted and never stored."""
    rows: list[dict[str, Any]] = []
    census: dict[str, Any] = {"refused_rows": {}, "errors": []}
    fx = _fxblue()
    if fx is None:
        census["errors"].append("fxblue_mechanism_summary not loadable")
    else:
        try:
            rows.extend(fx.genome_records(fxblue_paths))
        except Exception as exc:
            census["errors"].append(f"fxblue genome: {type(exc).__name__}: {exc}")
    rows.extend(_competition_rows(competition_path))
    kept: list[dict[str, Any]] = []
    for r in rows:
        t = terms_of(str(r["source"]))
        if t == "refused":
            census["refused_rows"][r["source"]] = census["refused_rows"].get(r["source"], 0) + 1
            continue
        r["terms_status"] = t
        kept.append(r)
    _hold_tags(kept)
    return kept, census


def as_of(rows: list[dict[str, Any]], at: datetime) -> list[dict[str, Any]]:
    """Only the rows the desk could have read at `at` (knowable_from <= at)."""
    out = []
    for r in rows:
        k = _ts(r.get("knowable_from"))
        if k is not None and k <= at:
            out.append(r)
    return out


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def _z(k1: int, n1: int, k2: int, n2: int) -> float | None:
    """Two-proportion z of group 1 against group 2 (pooled)."""
    if n1 <= 0 or n2 <= 0:
        return None
    p = (k1 + k2) / (n1 + n2)
    se = (p * (1 - p) * (1 / n1 + 1 / n2)) ** 0.5
    return None if se <= 0 else (k1 / n1 - k2 / n2) / se


def base_rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mechanism base rates over alive + dead, with the survivor-only rate beside each.

    `success` is alive AND profitable, over everyone who carried the style. DELISTED rows have
    no features (the page is gone), so they cannot be attributed to a style: the bound
    `p_alive_floor` assumes every one of them carried it -- the worst case the graveyard allows.
    Every style compared is a LOOK; `n_contrasts` is the count and the z is deflated by it.
    """
    from research.multiplicity import deflate_t

    pop = [r for r in rows if r["outcome"] != "SHELL"]
    unattributed = sum(1 for r in pop if r["outcome"] == "DELISTED")
    feat = [r for r in pop if r["outcome"] != "DELISTED"]
    tags = sorted({t for r in feat for t in r["style_tags"]})
    tested = [t for t in tags if sum(1 for r in feat if t in r["style_tags"]) >= MIN_TAG_N]
    n_contrasts = 2 * len(tested)             # survival AND success, per style
    out: dict[str, Any] = {}
    for t in tags:
        have = [r for r in feat if t in r["style_tags"]]
        rest = [r for r in feat if t not in r["style_tags"]]
        alive = [r for r in have if not r["dead"]]
        succ = sum(1 for r in alive if r.get("profitable"))
        r_alive = sum(1 for r in rest if not r["dead"])
        r_succ = sum(1 for r in rest if not r["dead"] and r.get("profitable"))
        n = len(have)
        row: dict[str, Any] = {
            "n": n, "alive": len(alive), "dead": n - len(alive),
            "status": "MEASURED" if t in tested else "UNMEASURED_SMALL_N",
            "p_alive": round(len(alive) / n, 4) if n else None,
            "p_alive_ci95": _wilson(len(alive), n),
            "p_alive_floor": round(len(alive) / (n + unattributed), 4) if n else None,
            "p_success_population": round(succ / n, 4) if n else None,
            "p_success_survivor_only": round(succ / len(alive), 4) if alive else None,
        }
        if row["p_success_population"] is not None and row["p_success_survivor_only"] is not None:
            row["survivorship_inflation"] = round(row["p_success_survivor_only"]
                                                  - row["p_success_population"], 4)
        if t in tested:
            zs = _z(len(alive), n, r_alive, len(rest))
            zw = _z(succ, n, r_succ, len(rest))
            row["z_alive_vs_rest"] = round(zs, 3) if zs is not None else None
            row["z_success_vs_rest"] = round(zw, 3) if zw is not None else None
            row["z_alive_deflated"] = (round(deflate_t(zs, n_contrasts), 3)
                                       if zs is not None else None)
            row["z_success_deflated"] = (round(deflate_t(zw, n_contrasts), 3)
                                         if zw is not None else None)
            row["z_death_deflated"] = (round(deflate_t(-zs, n_contrasts), 3)
                                       if zs is not None else None)
        out[t] = row
    alive_all = sum(1 for r in feat if not r["dead"])
    return {"population": len(pop), "with_features": len(feat),
            "unattributable_dead": unattributed,
            "p_alive_population": round(alive_all / len(feat), 4) if feat else None,
            "p_success_population": round(sum(1 for r in feat if not r["dead"]
                                              and r.get("profitable")) / len(feat), 4)
            if feat else None,
            "n_contrasts": n_contrasts, "by_style": out}


def priors(rows: list[dict[str, Any]], rates: dict[str, Any]) -> dict[str, Any]:
    """Failure memory (styles that die) and the crowding prior (where the crowd trades)."""
    pop = [r for r in rows if r["outcome"] not in ("SHELL", "DELISTED")]
    n = len(pop)
    fail = []
    for t, v in (rates.get("by_style") or {}).items():
        zd = v.get("z_death_deflated")
        if v.get("status") == "MEASURED" and zd is not None and float(zd) >= SIGNIF_Z:
            fail.append({"style": t, "p_death": round(1 - float(v["p_alive"]), 4), "n": v["n"],
                         "z_death_deflated": zd,
                         "family_analogue": (STYLE_FAMILY.get(t) or (None,))[0]})
    sym: dict[str, int] = {}
    for r in pop:
        for s in r.get("instruments") or []:
            sym[s] = sym.get(s, 0) + 1
    style: dict[str, float] = {}
    for t, v in (rates.get("by_style") or {}).items():
        style[t] = round(int(v["n"]) / n, 4) if n else 0.0
    return {
        "failure_memory": sorted(fail, key=lambda x: -x["z_death_deflated"]),
        "crowding_prior": {
            "population": n,
            "symbol_share": {s: round(c / n, 4) for s, c in
                             sorted(sym.items(), key=lambda kv: -kv[1])[:60]} if n else {},
            "style_share": style,
            "rule": ("share of the public population (alive + dead) trading a symbol or "
                     "carrying a style; a PRIOR on capacity and decay, never a veto")},
        "base_rates": {t: {k: v.get(k) for k in ("n", "p_alive", "p_success_population",
                                                 "p_success_survivor_only", "status")}
                       for t, v in (rates.get("by_style") or {}).items()},
    }


def _frame(rows: list[dict[str, Any]]) -> Any:
    import pandas as pd
    df = pd.DataFrame(rows)
    for c in ("instruments", "style_tags"):
        if c in df.columns:
            df[c] = df[c].apply(lambda v: list(v) if isinstance(v, (list, tuple)) else [])
    return df


def _family_fn(name: str) -> Any:
    try:
        from mt5desk import families
    except ImportError:
        return None
    fn = getattr(families, f"family_{name}", None)
    return fn if callable(fn) else None


def propose(rows: list[dict[str, Any]], rates: dict[str, Any], pri: dict[str, Any],
            budget_s: float = 900.0, write: bool = True) -> dict[str, Any]:
    """Styles -> family analogues -> screened cells -> the donor door. Every screen is a trial."""
    import time

    from research import proposer_common as pc
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        def may_hypothesise(_s: str) -> bool:                   # type: ignore[misc]
            return True
    started = time.monotonic()
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    styles = rates.get("by_style") or {}
    screened: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}
    for style, (fam, params, why) in STYLE_FAMILY.items():
        v = styles.get(style)
        if not v or v.get("status") != "MEASURED":
            skipped[style] = "no measured population base rate"
            continue
        fn = _family_fn(fam)
        if fn is None:
            skipped[style] = f"family {fam} not registered on this tree"
            continue
        counts: dict[str, int] = {}
        for r in rows:
            if style in r["style_tags"]:
                for s in r.get("instruments") or []:
                    counts[s] = counts.get(s, 0) + 1
        syms = [s for s, _ in sorted(counts.items(), key=lambda kv: -kv[1])
                if s in have and may_hypothesise(s)][:SYMBOLS_PER_STYLE]
        if not syms:
            skipped[style] = "none of the population's instruments has bars on this box"
            continue
        for sym in syms:
            if time.monotonic() - started > budget_s:
                skipped[f"{style}:{sym}"] = "budget exhausted"
                continue
            d = pc.bars(sym)
            if d is None or len(d) < MIN_BARS:
                skipped[f"{style}:{sym}"] = "too few H1 bars"
                continue
            cost = pc.cost_frac(sym, meta, d["close"])
            if cost is None:
                skipped[f"{style}:{sym}"] = "no contract terms to price the round trip"
                continue
            try:
                sig = fn(d, **params)
            except Exception as exc:
                skipped[f"{style}:{sym}"] = f"family raised {type(exc).__name__}"
                continue
            sc = pc.screen(d, sig or [], cost, pc.artifact_hours(d)) if sig else None
            body = dict(sc) if sc else {"n_independent": 0, "gross_per_trade": 0.0,
                                         "t_gross": 0.0, "clears_cost": False,
                                         "net_per_trade": round(-cost, 8),
                                         "cost_frac": round(cost, 8)}
            screened.append({"cell": f"{sym}.{fam}.genome_{style}", "symbol": sym,
                             "family": fam, "params": params, "style": style, "why": why,
                             "screened": bool(sc), **body})
    # THE GENOME'S OWN LOOKS ARE TRIALS TOO: each contrast it ran is charged into the sweep, as
    # a null row, so a cell proposed off a style is deflated by every style the genome compared.
    n_looks = len(screened) + int(rates.get("n_contrasts") or 0)
    for r in screened:
        r["t_gross"] = float(r.get("t_gross") or 0.0)
    nulls = [{"cell": f"genome_contrast_{i}", "t_gross": 0.0, "clears_cost": False,
              "n_independent": 0} for i in range(int(rates.get("n_contrasts") or 0))]
    swept = pc.deflate(screened + nulls)
    swept = [r for r in swept if not str(r["cell"]).startswith("genome_contrast_")]
    proposals = pc.best_per_cell(swept)
    crowd = pri.get("crowding_prior") or {}
    cands = []
    for r in proposals:
        v = styles.get(r["style"]) or {}
        cands.append(pc.candidate(
            SOURCE, r["symbol"], r["family"], dict(r["params"]),
            mechanism=(f"public trader genome: {r['why']} (style {r['style']}: population "
                       f"P(alive & profitable)={v.get('p_success_population')} over "
                       f"{v.get('n')} alive+dead, survivor-only "
                       f"{v.get('p_success_survivor_only')})"),
            title=f"{r['cell']} from the public trader genome",
            evidence={**{k: r.get(k) for k in ("n_independent", "gross_per_trade",
                                              "net_per_trade", "cost_frac", "t_gross",
                                              "t_deflated_sweep", "n_tests_sweep",
                                              "t_deflated_lifetime", "n_tests_lifetime")},
                      "genome_style": r["style"], "genome_base_rate": v,
                      "crowding_prior": {"symbol_share": (crowd.get("symbol_share") or {}).get(
                          r["symbol"]), "style_share": (crowd.get("style_share") or {}).get(
                          r["style"])}}))
    rep: dict[str, Any] = {"tests_run": len(screened), "n_looks_charged": n_looks,
                           "cells_proposed": len(proposals), "skipped": skipped,
                           "screened": [{k: r.get(k) for k in (
                               "cell", "style", "screened", "n_independent", "t_gross",
                               "t_deflated_sweep", "proposed")} for r in swept]}
    if write:
        # EVERY LOOK IS CHARGED, NULL PASSES INCLUDED. A pass whose screens and contrasts
        # passed nothing writes no discovery file, so its looks would vanish from the lifetime
        # count; the desk's one helper for that (alt_proxies._donate) donates when there is
        # something to donate and otherwise appends the looks to null_pass_trials.jsonl, which
        # experiment_ledger adds to the lifetime total. Exactly one of the two carries them.
        by_family: dict[str, int] = {}
        for r in screened:
            by_family[str(r["family"])] = by_family.get(str(r["family"]), 0) + 1
        if rates.get("n_contrasts"):
            by_family["genome_contrast"] = int(rates["n_contrasts"])
        rep["charge"] = _charge(cands, n_looks, by_family)
        if rep["charge"].get("path"):
            rep["donated"] = rep["charge"]["path"]
            rep["donation"] = pc.donation_counts()
    return rep


def _charge(cands: list[dict[str, Any]], n_looks: int,
            by_family: dict[str, int]) -> dict[str, Any]:
    """Donate the candidates, or charge the null pass to NULL_TRIALS (never neither)."""
    from research import alt_proxies as ap
    paths = ap.Paths(NULL_TRIALS.parent.parent)
    if paths.null_trials != NULL_TRIALS:            # the helper's ledger IS the desk's ledger
        raise RuntimeError(f"null-pass ledger mismatch: {paths.null_trials} != {NULL_TRIALS}")
    out: dict[str, Any] = ap._donate(paths, SOURCE, cands, n_looks, by_family,
                                     datetime.now(tz=UTC))
    return out


def genome(write: bool = True, budget_s: float = 900.0, *,
           fxblue_paths: list[Path] | None = None,
           competition_path: Path | None = None) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    rows, census = build_genome(fxblue_paths, competition_path)
    n_all = len(rows)
    rows = as_of(rows, now)
    census["not_yet_knowable"] = n_all - len(rows)
    usable = [r for r in rows if r["terms_status"] == "confirmed"]
    blocked: dict[str, int] = {}
    for r in rows:
        if r["terms_status"] != "confirmed":
            blocked[r["source"]] = blocked.get(r["source"], 0) + 1
    outcomes: dict[str, dict[str, int]] = {}
    for r in rows:
        o = outcomes.setdefault(r["source"], {})
        o[r["outcome"]] = o.get(r["outcome"], 0) + 1
    doc: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"), "rows": len(rows),
        "outcomes_by_source": outcomes, "seats": _seat_census(),
        "refused_rows": census["refused_rows"], "errors": census["errors"],
        "not_yet_knowable": census["not_yet_knowable"],
        "terms_blocked_rows": blocked,
        "rules": {"dormant_after_days": 180, "emptied_share": 0.05,
                  "graveyard": ["DELISTED", "BLOWN", "EMPTIED", "DORMANT"],
                  "success": "alive AND profitable, over alive + dead",
                  "pit": ("knowable_from = publication date when stated, else the harvest; "
                          "harvest-decided outcome labels (DORMANT/ALIVE/DELISTED) and "
                          "competition rankings (republished in place) = the harvest/fetch")},
        "artifacts": {"dataset": str(GENOME.relative_to(ROOT)),
                      "priors": str(PRIORS.relative_to(ROOT))},
    }
    if not usable:
        doc |= {"status": "BLOCKED_ON_TERMS",
                "why": (f"{len(rows)} genome row(s) held, none from a source whose terms are "
                        f"confirmed; no base rate, prior or candidate is derived until a human "
                        f"records the terms in book_forensics.TERMS / TERMS_EVIDENCE"),
                "base_rates": "UNMEASURED", "proposer": {"tests_run": 0, "cells_proposed": 0}}
        pri: dict[str, Any] = {"status": "BLOCKED_ON_TERMS", "failure_memory": [],
                               "crowding_prior": {}, "base_rates": {}}
    else:
        rates = base_rates(usable)
        pri = {"status": "MEASURED", **priors(usable, rates)}
        doc |= {"status": "OK", "base_rates": rates,
                "failure_memory": pri["failure_memory"],
                "proposer": propose(usable, rates, pri, budget_s=budget_s, write=write)}
    pri |= {"at": doc["at"], "source": str(GENOME_REPORT.relative_to(ROOT)),
            "consumers": ["desks/mt5/research/failure_prior.py (public_graveyard block)",
                          "desks/mt5/research/book_forensics.py (crowding_prior on candidates)"]}
    if write:
        GENOME.parent.mkdir(parents=True, exist_ok=True)
        try:
            _frame(rows).to_parquet(GENOME, index=False)
        except Exception as exc:
            doc["errors"].append(f"parquet write: {type(exc).__name__}: {exc}")
        GENOME_REPORT.parent.mkdir(parents=True, exist_ok=True)
        GENOME_REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        PRIORS.write_text(json.dumps(pri, indent=1, default=str), encoding="utf-8")
    return doc


def run(budget_s: float = 900.0, write: bool = True) -> dict[str, Any]:
    """The daily clock: our own book's forensics, then the public genome and its proposer."""
    for p in (str(DESK), str(DESK / "research"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    own = build()
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(own, indent=1, default=str), encoding="utf-8")
    g = genome(write=write, budget_s=budget_s)
    prop = g.get("proposer") or {}
    return {"book_status": own.get("status"), "genome_status": g.get("status"),
            "genome_rows": g.get("rows"), "tests_run": prop.get("tests_run", 0),
            "cells_proposed": prop.get("cells_proposed", 0)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report")
    ap.add_argument("--genome", action="store_true", help="also build the public trader genome")
    a = ap.parse_args(argv)
    if a.genome:
        for p in (str(DESK), str(DESK / "research"), str(ROOT)):
            if p not in sys.path:
                sys.path.insert(0, p)
        g = genome(write=a.apply)
        print(f"trader genome: {g['status']}  {g['rows']} row(s)  "
              f"outcomes={json.dumps(g['outcomes_by_source'])}")
        if g.get("why"):
            print(f"  {g['why']}")
    doc = build()
    print(f"book forensics: {doc.get('status')}  {doc.get('n_trades', 0)} fill(s), "
          f"{doc.get('n_baskets', '-')} basket(s)")
    if doc.get("why"):
        print(f"  {doc['why'][:160]}")
    if doc.get("structure"):
        print(f"  structure: {json.dumps(doc['structure'], default=str)[:200]}")
    if doc.get("ruin_forensics"):
        print(f"  ruin:      {json.dumps(doc['ruin_forensics'], default=str)[:200]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
