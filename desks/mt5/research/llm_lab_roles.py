"""FIVE MORE LAB ROLES (principal 2026-10-13, "fr max edge discoveries"). Each one adds a different
way of finding or killing an edge, and none of them has promotion authority.

  VERDICT LOOP     every gauntlet verdict goes back to the lab and the model that proposed the
                   cell, with its terminal gate. Labs and models are ranked by CERTIFIED
                   INCREMENTAL k_eff PER CALL (`docket_keff.score` on the certified cells), not by
                   how many novel cells they produced. `llm_lab.assign_model` and
                   `llm_lab.prioritised` spend against it.
  Q  MISSED MOVES  once a day: the largest recent MT5 daily moves on symbols no LIVE sleeve
                   trades, handed to a lab that writes causal hypotheses as exact cells which the
                   gauntlet tests on every past occurrence.
  R  CODE LAB      for conversion debt whose rule no registered family can express, a model
                   writes `feature(df)` in pure numpy/pandas. It runs in a SANDBOX: an AST
                   whitelist (no import, no attribute starting with "_", no I/O builtins), a
                   subprocess under `python -I` with an emptied environment and a timeout, and
                   three tests (shape, finite share, causality: perturbing later bars must not move
                   earlier values). A passing feature computed on the symbol's bars becomes a lake
                   series that the registered `exogenous_conditioner` family reads, and the cell
                   goes through the ordinary compiler. Nothing here imports or writes the money
                   path.
  S  SOURCE SCOUT  a model names non-English official public sources the desk lacks. Each row
                   is probed politely once (robots.txt, one GET; a login, paywall, CAPTCHA or rate
                   limit is recorded and never crossed), and reachable rows join
                   `asia_collector`'s registry as plane `llm_scout`.
  T  SLEEVE RED    once a day, for every LIVE sleeve: the strongest argument that it will fail
     TEAM          (regime break, crowding, data change, cost, venue), each with an observable and
                   a test. ADVISORY ONLY: written to `data/llm_lab/sleeve_red_team.json`; no
                   capital path reads it, and only measured evidence may ever move capital.

Every model call is free-tier (`libs.ops.free_chain`, or the seat that already routes to it), the
seat's prompt hygiene (`scrub`) runs on every prompt, and the local rung runs only on spare CPU.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = BASE / "data" / "llm_lab"
CREDIT = STATE_DIR / "verdict_credit.json"
EVIDENCE_START = STATE_DIR / "evidence_start.json"
MISSED = STATE_DIR / "missed_moves.jsonl"
DAILY = STATE_DIR / "daily_roles.json"
CODE_LEDGER = STATE_DIR / "code_lab.jsonl"
SCOUTED = STATE_DIR / "scouted_sources.json"
RED_TEAM = STATE_DIR / "sleeve_red_team.json"
CODE_DIR = BASE / "data" / "lake" / "code_lab"
SERIES_DIR = BASE / "data" / "lake" / "series"
BARS_DIR = BASE / "data" / "universe"
SLEEVES = BASE / "data" / "sleeves.json"
DONATE_DIR = BASE / "data" / "intelligence" / "llm_lab"
UNMEASURED = "UNMEASURED"
#: lab_style.NOVELTY_BONUS, repeated so the credit survives a tree without lab_style.
NOVELTY_BONUS = 1.0
PROXY_KEFF = 0.5          #: a certified cell's credit when k_eff cannot be measured, labelled so


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _h(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _jsonl(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return out
    return out[-limit:] if limit else out


def _append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return len(rows)


def _due_today(role: str) -> bool:
    return str((_read_json(DAILY, {}) or {}).get(role) or "") != _now()[:10]


def _mark_today(role: str) -> None:
    doc = _read_json(DAILY, {}) or {}
    doc[role] = _now()[:10]
    _write_json(DAILY, doc)


def _chat(system: str, user: str, *, max_tokens: int = 1200, temperature: float = 0.7,
          timeout: float = 90.0, chat: Callable[..., Any] | None = None) -> tuple[str, str]:
    """(reply text, "provider:model") from the free chain, or ("", why). Hygiene first."""
    try:
        from libs.research.proposer_seat import PromptRefused, scrub
        scrub(system + "\n" + user)
    except ImportError:                                # pragma: no cover
        return "", "prompt hygiene unavailable: nothing is sent"
    except PromptRefused as exc:
        return "", f"prompt refused: {str(exc)[:80]}"
    if chat is None:
        try:
            from libs.ops import free_chain
            chat = free_chain.chat
        except Exception:                              # pragma: no cover
            return "", "free chain unavailable"
    try:
        r = chat(system, user, max_tokens=max_tokens, temperature=temperature, timeout=timeout)
    except Exception as exc:
        return "", f"chain: {type(exc).__name__}"
    return str(getattr(r, "text", "") or ""), f"{getattr(r, 'provider', '')}:{getattr(r, 'model', '')}"


def _json_lines(text: str) -> list[dict[str, Any]]:
    """Every JSON object in a reply, nested braces and code strings included."""
    out: list[dict[str, Any]] = []
    dec = json.JSONDecoder()
    t = text or ""
    i = t.find("{")
    while i != -1:
        try:
            obj, end = dec.raw_decode(t, i)
        except ValueError:
            i = t.find("{", i + 1)
            continue
        if isinstance(obj, dict):
            out.append(obj)
        i = t.find("{", end)
    return out


# ============================================================================ evidence start
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}")


def record_evidence_start(rows: Iterable[dict[str, Any]], path: Path | None = None) -> int:
    """cell id -> {"from": first date whose data is evidence, "sym", "family", "params"}, for every
    donated cell whose guard names a date. The sealed gauntlet patch
    (patches/llm_lookahead_gauntlet) reads this map and drops earlier days from the cell's series
    before any gate; sym/family/params let it match a cell whose params the compiler filled out.
    A later entry never loosens an earlier one: the stored date only ever moves LATER."""
    p = path or EVIDENCE_START
    doc: dict[str, Any] = _read_json(p, {}) or {}
    n = 0
    for r in rows:
        cid = str(r.get("cell_id") or "")
        ev = str((r.get("lookahead_guard") or {}).get("evidence_from") or "")
        if not cid or not _DAY.match(ev) or ev[:10] <= "1900-01-01":
            continue
        old = doc.get(cid)
        was = str(old.get("from") if isinstance(old, dict) else old or "")
        if ev[:10] > was:
            doc[cid] = {"from": ev[:10], "sym": str(r.get("symbol") or ""),
                        "family": str(r.get("family") or ""), "params": r.get("params") or {}}
            n += 1
    if n:
        _write_json(p, doc)
    return n


# ============================================================================ verdict loop
def _donations(donate_dir: Path) -> dict[str, dict[str, Any]]:
    """cell id -> {lab, model, style} from every donation the lab and its roles have written."""
    try:
        import lab_style
        weigh: Callable[[dict[str, Any], float], tuple[float, str]] = lab_style.credit_weight
        share: Callable[[Iterable[dict[str, Any]]], float] = lab_style.novel_share
    except Exception:                                  # pragma: no cover - defensive
        def weigh(_r: dict[str, Any], _u: float = 0.0) -> tuple[float, str]:
            return 0.0, UNMEASURED

        def share(_rows: Iterable[dict[str, Any]]) -> float:
            return 0.0
    rows_by_lab: dict[str, list[dict[str, Any]]] = {}
    for f in sorted(donate_dir.glob("discoveries_*.json")):
        for r in (_read_json(f, {}) or {}).get("discoveries") or []:
            if isinstance(r, dict) and r.get("cell_id"):
                rows_by_lab.setdefault(str(r.get("lab") or "?"), []).append(r)
    # An UNMEASURED cell is credited at its lab's MEASURED novel share (audit must-fix 3).
    lab_share = {lab: share(rows) for lab, rows in rows_by_lab.items()}
    out: dict[str, dict[str, Any]] = {}
    for f in sorted(donate_dir.glob("discoveries_*.json")):
        doc = _read_json(f, {}) or {}
        for r in doc.get("discoveries") or []:
            if isinstance(r, dict) and r.get("cell_id"):
                w, style = weigh(r, lab_share.get(str(r.get("lab") or "?"), 0.0))
                sc = r.get("style_screen") or {}
                out[str(r["cell_id"])] = {"held_days": float(sc.get("held_days") or 0.0),
                                          "lab": str(r.get("lab") or "?"),
                                          "model": str(r.get("model") or "lexicon"),
                                          "symbol": str(r.get("symbol") or ""),
                                          "family": str(r.get("family") or ""),
                                          "style": style, "novel_weight": w}
    return out


def _keff(cells: list[dict[str, str]]) -> tuple[dict[str, float], str]:
    """Incremental effective bets each certified cell adds to the book, or a labelled proxy."""
    if not cells:
        return {}, "no certified cells"
    try:
        import docket_keff
        rows = [{"symbol": c["symbol"], "family": c["family"], "_cid": c["cid"]} for c in cells]
        doc = docket_keff.score(rows)
        inst = str(((doc or {}).get("instrument") or {}).get("status") or "")
        vals = {r["_cid"]: max(0.0, float(r.get("_keff") or 0.0)) for r in rows}
        if inst == "UNMEASURED" or not any(vals.values()):
            raise ValueError("book exposure UNMEASURED")
        return vals, "docket_keff (delta N_eff on the desk's daily panel)"
    except Exception as exc:
        return ({c["cid"]: PROXY_KEFF for c in cells},
                f"k_eff UNMEASURED ({str(exc)[:60]}): {PROXY_KEFF} per certified cell as proxy")


def verdict_loop(verdicts_path: Path, donate_dir: Path | None = None,
                 asks: Iterable[tuple[str, str]] = (), credit_path: Path | None = None
                 ) -> dict[str, Any]:
    """Join verdicts to their proposer, add this pass's calls, and re-rank. Returns the credit doc.

    `asks` is this pass's (lab, model) per call. Calls accumulate forever, so a lab that spends
    many calls for one certificate ranks below one that spent few."""
    path = credit_path or CREDIT
    doc = _read_json(path, {}) or {}
    labs: dict[str, dict[str, Any]] = doc.setdefault("labs", {})
    models: dict[str, dict[str, Any]] = doc.setdefault("models", {})
    for lab, model in asks:
        for table, key in ((labs, lab), (models, model or "default_route")):
            row = table.setdefault(key, {"calls": 0})
            row["calls"] = int(row.get("calls", 0)) + 1
    owners = _donations(donate_dir or DONATE_DIR)
    latest: dict[str, dict[str, Any]] = {}
    for r in _jsonl(verdicts_path):
        cid = str(r.get("cell") or "")
        if cid in owners:
            latest[cid] = r
    certified = [{"cid": c, **owners[c]} for c, r in latest.items() if r.get("passed")]
    keff, basis = _keff(certified)
    for table in (labs, models):
        for row in table.values():
            row.update({"judged": 0, "certified": 0, "keff": 0.0, "novel_keff": 0.0,
                        "styles": {}, "gates": {}})
    feedback: dict[str, list[str]] = {}
    hold_cost = {"judged": 0, "certified": 0, "keff_days": 0.0}
    for cid, r in latest.items():
        own = owners[cid]
        if own.get("held_days"):
            hold_cost["judged"] += 1
            if r.get("passed"):
                hold_cost["certified"] += 1
                hold_cost["keff_days"] = round(hold_cost["keff_days"] + keff.get(cid, 0.0)
                                               * float(own["held_days"]), 4)
        gate = str(r.get("terminal_gate") or r.get("gate") or ("CERTIFIED" if r.get("passed")
                                                                 else "UNKNOWN"))
        why = str(r.get("reason") or r.get("why") or "")[:90]
        for table, key in ((labs, own["lab"]), (models, own["model"])):
            row = table.setdefault(key, {"calls": 0, "judged": 0, "certified": 0, "keff": 0.0,
                                         "novel_keff": 0.0, "styles": {}, "gates": {}})
            row["judged"] += 1
            row["gates"][gate] = row["gates"].get(gate, 0) + 1
            if r.get("passed"):
                row["certified"] += 1
                row["keff"] = round(row["keff"] + keff.get(cid, 0.0), 4)
                # NOVELTY IS A BONUS ON k_eff (audit must-fix 3 on #385): a known-style
                # certificate keeps the k_eff it measured; a novel one earns (1 + bonus) x it.
                row["novel_keff"] = round(row.get("novel_keff", 0.0) + keff.get(cid, 0.0)
                                          * (1.0 + NOVELTY_BONUS * float(own["novel_weight"])), 4)
                row["styles"][own["style"]] = row["styles"].get(own["style"], 0) + 1
        if not r.get("passed") and held_out(gate, why):
            continue                      # audit must-fix 7: a held-out death is never told
        line = (f"verdict on your cell {cid[:60]} ({own['family']} on {own['symbol']}): "
                + (f"CERTIFIED, +{keff.get(cid, 0.0):.2f} effective bets" if r.get("passed")
                   else f"died at {gate}{(' -- ' + why) if why else ''}"))
        feedback.setdefault(own["lab"], []).append(line)
    for table in (labs, models):
        for row in table.values():
            calls = max(1, int(row.get("calls", 0)))
            row["keff_per_call"] = round(float(row.get("keff", 0.0)) / calls, 6)
            row["novel_keff_per_call"] = round(float(row.get("novel_keff", 0.0)) / calls, 6)
    doc.update({"generated_at": _now(), "keff_basis": basis, "judged_cells": len(latest),
                "certified_cells": len(certified),
                "ranking_rule": "NOVEL certified incremental k_eff per call: each certificate's "
                                "k_eff x (1 + bonus x w), w = 1 NOVEL, 0 KNOWN_STYLE, the lab's "
                                "measured novel share if UNMEASURED; novelty counts are NOT a "
                                "ranking input",
                "style_hold_cost": hold_cost,
                "feedback": {k: v[-8:] for k, v in feedback.items()}})
    _write_json(path, doc)
    return doc


def thompson(rows: dict[str, dict[str, Any]], keys: Sequence[str], rng: random.Random) -> list[str]:
    """Order `keys` by a Beta draw on NOVEL certified k_eff per call: successes are effective
    bets certified in styles the book does not already own, trials are calls. An unseen key
    draws from the flat prior, so it is explored. A row written before the style screen existed
    has no `novel_keff` and is read on its plain k_eff."""
    def draw(k: str) -> float:
        r = rows.get(k) or {}
        s = max(0.0, float(r.get("novel_keff", r.get("keff", 0.0))))
        n = max(float(r.get("calls", 0)), s)
        return rng.betavariate(1.0 + s, 1.0 + n - s)
    return sorted(keys, key=draw, reverse=True)


# ============================================================================ Q missed moves
def _daily(sym: str, bars_dir: Path) -> Any:
    f = bars_dir / f"{sym}_H1.parquet"
    if not f.exists():
        return None
    try:
        import numpy as np
        import pandas as pd
        d = pd.read_parquet(f, columns=["close"])
        r = np.log(d["close"]).diff().dropna().resample("1D").sum()
        return r[r != 0]
    except Exception:
        return None


def live_symbols(path: Path | None = None) -> set[str]:
    doc = _read_json(path or SLEEVES, {}) or {}
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    return {str(r.get("symbol")) for r in rows or [] if isinstance(r, dict)
            and str(r.get("status") or "").upper() == "LIVE"}


def missed_moves(uni: dict[str, str], *, bars_dir: Path | None = None, lookback_days: int = 3,
                 top: int = 6, may: Callable[[str], bool] | None = None) -> list[dict[str, Any]]:
    """The largest recent daily moves, in units of each symbol's own 60-day volatility, on
    symbols no LIVE sleeve trades. "Not captured" is read from sleeve presence; fills are not
    joined here, so a LIVE sleeve that sat out the move still counts as having captured it."""
    bd = bars_dir or BARS_DIR
    held = live_symbols()
    panel: dict[str, Any] = {}
    for sym in uni:
        if may is not None and not may(sym):
            continue
        r = _daily(sym, bd)
        if r is not None and len(r) >= 70:
            panel[sym] = r
    if not panel:
        return []
    moves: list[dict[str, Any]] = []
    for sym, r in panel.items():
        sd = r.rolling(60, min_periods=40).std().shift(1)
        z = (r / sd).dropna()
        for day, zv in z.tail(lookback_days).items():
            if math.isfinite(float(zv)):
                moves.append({"symbol": sym, "day": str(day)[:10], "ret": round(float(r[day]), 5),
                              "z": round(float(zv), 2), "captured": sym in held})
    moves = [m for m in moves if not m["captured"]]
    moves.sort(key=lambda m: -abs(m["z"]))
    out = moves[:top]
    for m in out:
        same = sorted((x for x in moves if x["day"] == m["day"] and x["symbol"] != m["symbol"]),
                      key=lambda x: -abs(x["z"]))[:5]
        m["same_day"] = [f"{x['symbol']} z={x['z']:+.1f}" for x in same]
    return out


MISSED_MANDATE = ("A large move happened that the desk's live book did not trade. Write CAUSAL "
                  "hypotheses for it: who was forced or informed, what clock or event drove it, "
                  "and a rule that would have been positioned before it. Every hypothesis must be "
                  "an exact cell that can be tested on EVERY past occurrence of the same "
                  "condition, not a story about this one day.")


#: Gates whose outcome is held-out evidence (the lockbox and its kin). Their deaths never reach
#: anything model-facing (audit must-fix 7): a model told "died at lockbox" learns the held-out
#: segment, and the scrub then refuses the prompt that carried it, silencing the lab.
HELD_OUT = re.compile(r"lock|hold.?out|held.?out|reserved", re.I)


def held_out(gate: str, why: str = "") -> bool:
    return bool(HELD_OUT.search(gate or "") or HELD_OUT.search(why or ""))


# ============================================================================ R code lab
SAFE_CALLS = frozenset({"abs", "min", "max", "len", "range", "float", "int", "round", "sum",
                        "enumerate", "zip", "bool"})
#: AN ALLOWLIST, NOT A DENY-LIST (audit must-fix 1, 2026-10-13). A deny-list of names was beaten
#: by an attribute CHAIN: `pd.io.common.os.system(...)` never names `os` as a bare Name. So every
#: attribute anywhere in the source must be on one of the lists below, whatever its base: a
#: chain through `io`, `lib`, `ctypeslib`, `common` or any reader/writer cannot be spelled at all.
NP_ATTRS = frozenset({
    "abs", "arctan", "arange", "asarray", "clip", "cos", "cumsum", "cumprod", "diff", "exp",
    "float64", "full", "full_like", "inf", "int64", "isfinite", "isnan", "log", "log1p",
    "maximum", "mean", "median", "minimum", "nan", "nanmean", "nanmedian", "nanstd", "nansum",
    "nan_to_num", "ones", "ones_like", "percentile", "quantile", "sign", "sin", "sqrt", "square",
    "std", "sum", "tanh", "var", "where", "zeros", "zeros_like", "pi", "e", "max", "min", "round",
    "floor", "ceil", "hypot", "power", "abs"})
PD_ATTRS = frozenset({"Series", "DataFrame", "concat", "isna", "notna", "NA", "Timedelta"})
#: Methods and properties on the frame, its columns and their results.
VALUE_ATTRS = frozenset({
    "abs", "all", "any", "astype", "bfill", "clip", "close", "copy", "count", "cummax",
    "cummin", "cumprod", "cumsum", "day", "dayofweek", "diff", "dropna", "dt", "ewm", "ffill",
    "fillna", "high", "hour", "iloc", "index", "isna", "kurt", "loc", "low", "max", "mean",
    "median", "min", "minute", "month", "notna", "open", "pct_change", "quantile", "rank",
    "replace", "rolling", "round", "shape", "shift", "skew", "std", "sum", "values", "var",
    "volume", "weekday", "where", "mask", "expanding", "corr", "cov", "between", "eq", "ne",
    "gt", "ge", "lt", "le", "add", "sub", "mul", "div", "clip_lower", "clip_upper", "sign",
    "year", "date", "size", "empty", "reindex_like", "align", "to_numpy", "tolist"})


def code_refusal(code: str) -> str:
    """'' when the source is inside the allowlist, else the reason it is refused."""
    if len(code) > 6000:
        return "longer than 6000 characters"
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    local: set[str] = {"feature"}
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            local.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            local.add(node.id)
        elif isinstance(node, ast.FunctionDef):
            local.add(node.name)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "import is not allowed (np and pd are provided)"
        if isinstance(node, (ast.Global, ast.Nonlocal, ast.With, ast.AsyncFunctionDef,
                             ast.Await, ast.Yield, ast.YieldFrom, ast.Try, ast.Raise,
                             ast.ClassDef, ast.Lambda, ast.Starred, ast.NamedExpr)):
            return f"{type(node).__name__} is not allowed"
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and not (
                node.id in local or node.id in SAFE_CALLS or node.id in ("np", "pd", "True",
                                                                          "False", "None")):
            return f"name {node.id!r} is not allowed"
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                return f"attribute {node.attr!r} is not allowed"
            base = node.value
            if isinstance(base, ast.Name) and base.id == "np":
                ok = node.attr in NP_ATTRS
            elif isinstance(base, ast.Name) and base.id == "pd":
                ok = node.attr in PD_ATTRS
            else:
                ok = node.attr in VALUE_ATTRS
            if not ok:
                return f"attribute {node.attr!r} is not on the allowlist"
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and (
                "/" in node.value or "\\" in node.value or ":" in node.value):
            return "string constants may not carry paths"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and \
                node.func.id not in SAFE_CALLS and node.func.id not in local:
            return f"call to {node.func.id!r} is not allowed (use np./pd. functions)"
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(tree.body) != 1 or not funcs or funcs[0].name != "feature":
        return "the source must be exactly one function named feature(df)"
    return ""


#: The OS as read at import; a test overrides this, never `os.name` (pathlib reads that).
_OS_NAME = os.name


def code_lab_isolated() -> str:
    """'' when the sandbox can cap the child, else why role R stands down.

    Audit must-fix 1: rlimits are POSIX-only, so on Windows the child has no memory or CPU cap
    beyond the wall-clock timeout. Role R therefore runs only where the caps exist, unless the
    principal sets QUANT_LLM_CODE_LAB=1 (the allowlist above still binds).
    """
    if os.environ.get("QUANT_LLM_CODE_LAB", "") == "1":
        return ""
    if _OS_NAME != "posix":
        return ("DISABLED_NO_ISOLATION: no rlimit on this OS; set QUANT_LLM_CODE_LAB=1 to run "
                "under the allowlist and timeout alone")
    return ""


_RUNNER = r'''
import json, sys
try:                                    # POSIX: a feature may not take more than 2 GB or 60 s CPU
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
except Exception:
    pass
import numpy as np, pandas as pd
BUILTINS = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
            for k in ("abs","min","max","len","range","float","int","round","sum","enumerate",
                      "zip","bool","True","False","None","isinstance","list","dict","tuple")
            if (k in __builtins__ if isinstance(__builtins__, dict) else hasattr(__builtins__, k))}
src = open(sys.argv[1], encoding="utf-8").read()
mode = sys.argv[2]
ns = {"__builtins__": BUILTINS, "np": np, "pd": pd}
exec(compile(src, "feature", "exec"), ns)
f = ns["feature"]
def run(df):
    out = f(df.copy())
    s = pd.Series(np.asarray(out, dtype=float).ravel()) if not isinstance(out, pd.Series) else out
    return pd.Series(np.asarray(s, dtype=float), index=df.index[:len(s)]) if len(s) == len(df) else s
if mode == "test":
    rng = np.random.default_rng(7)
    n = 600
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    df = pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c,
                       "volume": rng.integers(1, 100, n).astype(float)}, index=idx)
    a = run(df)
    res = {"length_ok": len(a) == n}
    fin = np.isfinite(np.asarray(a, dtype=float))
    res["finite_share"] = float(fin.mean()) if len(a) else 0.0
    vals = np.asarray(a, dtype=float)[fin]
    res["varies"] = bool(len(vals) > 10 and float(np.nanstd(vals)) > 0)
    cut = int(n * 0.8)
    df2 = df.copy()
    df2.iloc[cut:] = df2.iloc[cut:] * 1.5
    b = run(df2)
    pa, pb = np.asarray(a, dtype=float)[:cut], np.asarray(b, dtype=float)[:cut]
    same = np.allclose(np.nan_to_num(pa, nan=1e300), np.nan_to_num(pb, nan=1e300), rtol=1e-9,
                       atol=1e-12)
    res["causal"] = bool(same)
    print(json.dumps(res))
else:
    df = pd.read_parquet(sys.argv[3])
    s = run(df)
    out = pd.DataFrame({"value": np.asarray(s, dtype=float)}, index=df.index[:len(s)])
    out.to_csv(sys.argv[4], index_label="bar_time")
    print(json.dumps({"rows": int(len(out))}))
'''


def sandbox(code: str, mode: str = "test", bars: Path | None = None, out: Path | None = None,
            timeout: float = 30.0) -> dict[str, Any]:
    """Run the feature in a child interpreter: isolated mode, empty environment (no key can be
    read), a temporary working directory, a hard timeout. The whitelist runs first."""
    why = code_refusal(code)
    if why:
        return {"ok": False, "why": f"refused: {why}"}
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "feature.py"
        src.write_text(code, encoding="utf-8")
        runner = Path(tmp) / "runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        args = [sys.executable, "-I", str(runner), str(src), mode]
        if mode == "series":
            args += [str(bars), str(out)]
        env = {k: os.environ[k] for k in ("SYSTEMROOT", "PATH", "TEMP", "TMP") if k in os.environ}
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=tmp,
                               env=env, check=False)
        except subprocess.TimeoutExpired:
            return {"ok": False, "why": f"timeout after {timeout:.0f}s"}
    if p.returncode != 0:
        return {"ok": False, "why": f"raised: {(p.stderr or '').strip().splitlines()[-1:]}"}
    try:
        res = json.loads((p.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "why": "no result line"}
    if mode == "test":
        ok = bool(res.get("length_ok") and res.get("causal") and res.get("varies")
                  and float(res.get("finite_share") or 0) >= 0.5)
        res["ok"] = ok
        if not ok:
            res["why"] = ("failed: " + ", ".join(k for k in ("length_ok", "causal", "varies")
                                                 if not res.get(k))
                          + ("" if float(res.get("finite_share") or 0) >= 0.5
                             else " finite_share<0.5"))
        return res
    res["ok"] = True
    return res


CODE_SYSTEM = (
    "You write ONE Python function `def feature(df):` for a research desk. `df` is a pandas "
    "DataFrame of H1 bars indexed by time with columns open, high, low, close, volume. `np` and "
    "`pd` are already available; do NOT import anything, do not read or write files, do not use "
    "names starting with an underscore. Return a pandas Series (same index as df) whose value at "
    "each bar uses ONLY that bar and earlier bars (no shift(-k), no centred windows, no future "
    "data). Reply with ONE JSON object: {\"code\": \"<the function source>\", \"side_when_high\": "
    "1 or -1, \"why\": \"<one line: which rule it computes>\"}.")


def _series_from_feature(code: str, sym: str, name: str, bars_dir: Path) -> tuple[Path | None, str]:
    bars = bars_dir / f"{sym}_H1.parquet"
    if not bars.exists():
        return None, f"NEEDS_DATA: no H1 bars for {sym} on this host"
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    raw = SERIES_DIR / f"{name}.raw.csv"
    res = sandbox(code, "series", bars, raw, timeout=90.0)
    if not res.get("ok"):
        return None, str(res.get("why"))
    import pandas as pd
    df = pd.read_csv(raw)
    raw.unlink(missing_ok=True)
    t = pd.to_datetime(df["bar_time"], utc=True, errors="coerce")
    # A bar's value is known at its CLOSE; the bar clock is broker time under a UTC label, and the
    # conditioner's own 24h lag absorbs that offset (family_exogenous_conditioner docstring).
    df["available_time"] = (t + pd.Timedelta(hours=1)).dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    df["source_id"] = name
    out = SERIES_DIR / f"{name}.csv"
    df[["available_time", "source_id", "value"]].dropna().to_csv(out, index=False)
    return out, ""


def code_lab(debt_path: Path, uni: dict[str, str], *, max_items: int, deadline: float,
             chat: Callable[..., Any] | None = None, bars_dir: Path | None = None
             ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Write, sandbox-test and run feature code for rule-shaped debt. Returns (donations, tally)."""
    why = code_lab_isolated()
    if why:
        return [], {"state": why}
    bd = bars_dir or BARS_DIR
    doc = _read_json(debt_path, {}) or {}
    rows: dict[str, dict[str, Any]] = doc.get("rows") or {}
    want = ("NEEDS_EXACT_RULE_EXTRACTION", "NEEDS_EXECUTABLE_FAMILY")
    todo = [r for r in rows.values() if r.get("state") == "OPEN"
            and any(b in want for b in r.get("blockers") or [])
            and int(r.get("code_attempts") or 0) < 2]
    todo.sort(key=lambda r: str(r.get("first_seen") or ""))
    tally: Counter = Counter()
    donations: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for r in todo[:max_items]:
        if time.time() > deadline:
            tally["not_this_pass"] += 1
            continue
        payload = dict(r.get("payload") or {})
        syms = [s for s in payload.get("symbols") or [] if s in uni][:1]
        r["code_attempts"] = int(r.get("code_attempts") or 0) + 1
        if not syms:
            tally["no_symbol"] += 1
            continue
        user = (f"Mechanism: {str(payload.get('mechanism'))[:400]}\n"
                f"Falsifier: {str(payload.get('falsifier'))[:200]}\n"
                f"Missing rule: {', '.join(map(str, payload.get('needs') or []))[:300]}\n"
                "Compute the feature whose extreme values this mechanism says precede a move.")
        text, model = _chat(CODE_SYSTEM, user, max_tokens=900, temperature=0.2, chat=chat)
        tally["asked"] += 1
        got = (_json_lines(text) or [{}])[0]
        code = str(got.get("code") or "")
        side = 1 if int(got.get("side_when_high") or 1) >= 0 else -1
        test = sandbox(code) if code else {"ok": False, "why": "no code in the reply"}
        row = {"debt_id": r.get("id"), "at": _now(), "model": model, "symbol": syms[0],
               "code_sha": _h(code), "test": test}
        if not test.get("ok"):
            tally["failed_tests"] += 1
            ledger.append(row)
            continue
        name = f"codelab_{_h(code, syms[0])}"
        CODE_DIR.mkdir(parents=True, exist_ok=True)
        (CODE_DIR / f"{name}.py").write_text(code, encoding="utf-8")
        path, why = _series_from_feature(code, syms[0], name, bd)
        if path is None:
            tally["no_series"] += 1
            row["series"] = why
            ledger.append(row)
            continue
        params = {"source": name, "signal": "value", "transform": "level_z", "threshold": 1.5,
                  "side_when_high": side}
        cell = {"family": "exogenous_conditioner", "params": params, "symbol": syms[0]}
        try:
            import llm_lab
            cid = llm_lab.cell_identity(cell)
            guard = llm_lab.lookahead_guard(model)
        except Exception:                              # pragma: no cover
            cid, guard = f"{syms[0]}.exogenous_conditioner.{name}", {"evidence_from": _now()[:10]}
        donations.append({
            "kind": "hypothesis", "family": "exogenous_conditioner", "params": params,
            "symbols": [syms[0]], "symbol": syms[0],
            "mechanism": str(payload.get("mechanism") or "")[:300],
            "falsifier": str(payload.get("falsifier") or "")[:200],
            "title": f"llm_lab R code lab: {str(got.get('why') or name)[:100]}",
            "lab": "R", "lab_name": "code_lab", "model": model, "cell_id": cid,
            "novelty_class": "COMPOSITIONAL_DESCENDANT", "mechanism_class": "converted_rule",
            "lineage": {"root": str(r.get("id")), "operator": "llm_lab.code_lab"},
            "url": f"llm_lab://R/{name}", "lookahead_guard": guard,
            "copy_trade": False, "credibility_inherited": False, "gauntlet_bypass": False})
        r["state"] = "RESOLVED"
        r["resolved_by"] = f"code_lab:{name}"
        r["resolved_at"] = _now()
        row["series"] = name
        tally["converted"] += 1
        ledger.append(row)
    if todo:
        doc["rows"] = rows
        _write_json(debt_path, doc)
    _append_jsonl(CODE_LEDGER, ledger)
    return donations, dict(tally)


# ============================================================================ S source scout
SCOUT_PLANES = (("zh", "China"), ("ja", "Japan"), ("ko", "Korea"), ("ru", "Russia and CIS"),
                ("tr", "Turkiye"), ("ar", "Gulf and North Africa"), ("pt", "Brazil"),
                ("es", "Mexico, Chile, Colombia, Peru"), ("id", "Indonesia"), ("hi", "India"),
                ("de", "Germany, Austria, Switzerland"), ("pl", "Poland and CEE"),
                ("af", "South Africa"), ("th", "Thailand"), ("vi", "Vietnam"))
SCOUT_SYSTEM = (
    "You know official public data sources in many languages. Name sources a quantitative FX, "
    "metals, energy and index desk probably LACKS: statistics offices, central banks, ministries, "
    "customs, exchanges, port and grid operators, regulators publishing in the local language. "
    "Only sources that are public without login or payment. One JSON object per line: "
    '{"name": "...", "publisher": "...", "url": "https://...", "language": "<code>", '
    '"country": "<iso2>", "expect": "csv|json|xml|any", "cadence": "daily|weekly|monthly|'
    'quarterly", "targets": ["<MT5 symbol>"], "mechanism": "<why the number moves those '
    'instruments, <=200 chars>"}')
_GATED = re.compile(r"(?i)login|signin|sign-in|subscribe|paywall|account|register|captcha")


def scout_rows(text: str, plane: tuple[str, str], known_hosts: set[str], uni: dict[str, str]
               ) -> tuple[list[dict[str, Any]], Counter]:
    out: list[dict[str, Any]] = []
    why: Counter = Counter()
    for r in _json_lines(text):
        url = str(r.get("url") or "")
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            why["bad url"] += 1
            continue
        if _GATED.search(url):
            why["login or paywall path"] += 1
            continue
        if parts.netloc.lower() in known_hosts:
            why["host already in the registry"] += 1
            continue
        targets = [s for s in r.get("targets") or [] if s in uni][:8]
        if not targets:
            why["no MT5 target"] += 1
            continue
        out.append({"id": f"scout_{_h(url)}", "plane": "llm_scout",
                    "country": str(r.get("country") or "")[:4].lower(),
                    "name": str(r.get("name") or "")[:160], "url": url,
                    "expect": str(r.get("expect") or "any") if str(r.get("expect")) in
                    ("csv", "json", "xml", "any") else "any",
                    "access": "public", "cadence": str(r.get("cadence") or "monthly")[:12],
                    "language": str(r.get("language") or plane[0])[:5], "targets": targets,
                    "mechanism": str(r.get("mechanism") or "")[:200],
                    "why": f"source scout ({plane[1]}): {str(r.get('publisher') or '')[:80]}",
                    "origin": "llm_source_scout", "terms": "to_confirm",
                    "fetch_policy": "polite public fetch; never crosses a login, paywall, "
                                    "CAPTCHA or rate limit", "probe": UNMEASURED})
    return out, why


def probe(row: dict[str, Any], get: Callable[[str], tuple[int, bytes]] | None = None,
          *, resolve: Callable[[str], list[str]] | None = None) -> str:
    """One polite look: robots.txt, then one GET. Returns REACHABLE or the named reason not."""
    def _get(url: str) -> tuple[int, bytes]:
        import requests
        # No redirects: a public URL that 302s to a private one would skip the host check.
        r = requests.get(url, timeout=20, allow_redirects=False,
                         headers={"User-Agent": "quant-desk-source-scout/1.0"})
        return r.status_code, r.content[:20000]
    g = get or _get
    from libs.ops.public_host import public_url
    why = public_url(row.get("url", ""), resolve=resolve)
    if why:
        return f"REFUSED:{why}"
    parts = urllib.parse.urlsplit(row["url"])
    try:
        code, body = g(f"{parts.scheme}://{parts.netloc}/robots.txt")
        if code == 200:
            from urllib.robotparser import RobotFileParser
            rp = RobotFileParser()
            rp.parse(body.decode("utf-8", errors="replace").splitlines())
            if not rp.can_fetch("quant-desk-source-scout/1.0", row["url"]):
                return "ROBOTS_DISALLOW"
        code, body = g(row["url"])
    except Exception as exc:
        return f"UNREACHABLE:{type(exc).__name__}"
    if code in (401, 402, 403, 407, 429):
        return f"GATED:HTTP_{code}"
    if code != 200:
        return f"HTTP_{code}"
    if re.search(rb"(?i)captcha|verify you are human|cf-chl", body):
        return "GATED:CHALLENGE"
    return "REACHABLE"


# ============================================================================ T sleeve red team
FAILURE_MODES = ("regime_break", "crowding", "data_change", "cost_change", "venue_change",
                 "structural_break", "overfit", "liquidity", "policy_change", "correlation_spike")
RED_SYSTEM = (
    "You are the red team for a live trading sleeve. For each sleeve listed, give the strongest "
    "reasons it will FAIL from here. One JSON object per line: {\"sleeve\": \"<name>\", "
    "\"failure_mode\": \"" + "|".join(FAILURE_MODES) + "\", \"argument\": \"<=300 chars\", "
    "\"observable\": \"<what number would show it starting, <=120 chars>\", \"test\": \"<a check "
    "the desk can run on its own data, <=160 chars>\", \"horizon_days\": <int>}. No scores, no "
    "probabilities.")


def live_sleeves(path: Path | None = None) -> list[dict[str, Any]]:
    doc = _read_json(path or SLEEVES, {}) or {}
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    return [r for r in rows or [] if isinstance(r, dict)
            and str(r.get("status") or "").upper() == "LIVE"]


def red_team(sleeves: list[dict[str, Any]], *, chat: Callable[..., Any] | None = None,
             deadline: float, max_calls: int) -> tuple[dict[str, Any], int]:
    names = {str(s.get("name")) for s in sleeves}
    attacks: list[dict[str, Any]] = []
    calls = 0
    for i in range(0, len(sleeves), 4):
        if calls >= max_calls or time.time() > deadline:
            break
        chunk = sleeves[i:i + 4]
        user = "\n".join(f"sleeve {s.get('name')}: {s.get('family')} on {s.get('symbol')} "
                         f"{s.get('timeframe') or ''} session={s.get('session') or '-'}"
                         for s in chunk)
        text, model = _chat(RED_SYSTEM, user, max_tokens=1200, temperature=0.6, chat=chat)
        calls += 1
        for r in _json_lines(text):
            if str(r.get("sleeve")) not in names or r.get("failure_mode") not in FAILURE_MODES:
                continue
            if len(str(r.get("argument") or "")) < 20:
                continue
            try:
                horizon = int(r.get("horizon_days") or 30)
            except (TypeError, ValueError):
                horizon = 30
            attacks.append({"sleeve": str(r["sleeve"]), "failure_mode": r["failure_mode"],
                            "argument": str(r["argument"])[:300],
                            "observable": str(r.get("observable") or "")[:120],
                            "test": str(r.get("test") or "")[:160],
                            "horizon_days": max(1, min(365, horizon)), "model": model,
                            "at": _now()})
    by: dict[str, list[dict[str, Any]]] = {}
    for a in attacks:
        by.setdefault(a["sleeve"], []).append(a)
    doc = {"generated_at": _now(), "advisory": True,
           "authority": "NONE: arguments only. No capital path reads this file; a sleeve's size "
                        "moves only on measured evidence (drift monitor, forward clock, allocator).",
           "live_sleeves": sorted(names), "attacked": sorted(by),
           "unattacked": sorted(names - set(by)), "attacks": by,
           "modes": dict(Counter(a["failure_mode"] for a in attacks))}
    return doc, calls


# ============================================================================ the pass
def run(*, lab: Any, reg: Any, uni: dict[str, str], mem: Any, tallies: dict[str, Any],
        models: dict[str, Any], outputs: dict[str, list[dict[str, Any]]], rng: random.Random,
        calls_left: int, deadline: float, seat_on: bool, chat: Callable[..., Any] | None = None
        ) -> tuple[dict[str, Any], int]:
    """Run roles Q, R, S, T inside the lab pass. Returns (report, calls made)."""
    rep: dict[str, Any] = {}
    calls = 0
    if not seat_on:
        return {"state": "seat dark: roles planned, nothing asked"}, 0

    # Q -- missed-move archaeology, once a day.
    if _due_today("Q") and calls < calls_left and time.time() < deadline:
        moves = missed_moves(uni, may=lambda s: bool(lab._lane_ok(s, "")))
        rep["Q"] = {"moves": len(moves)}
        if moves:
            _append_jsonl(MISSED, [{**m, "seen_at": _now()} for m in moves])
            ctx = [f"move: {m['symbol']} {m['day']} return {m['ret']:+.4f} "
                   f"({m['z']:+.1f} sd of its own 60-day vol); same day: "
                   f"{', '.join(m['same_day']) or 'nothing else extreme'}" for m in moves]
            ctx += ["all registered families: " + lab.all_family_names(reg)[:900],
                    lab.FORMULA_GRAMMAR]
            coord = {"lab": "Q", "mechanism_class": "missed_move", "asset_class": "",
                     "horizon": "swing"}
            ask = lab.Ask(lab.LAB_BY_KEY["Q"], coord, "missed_move", "", ctx[:40],
                          f"{MISSED_MANDATE} {lab.TASK_RULES}")
            props = lab._call(ask, n=6, timeout=max(20.0, min(120.0, deadline - time.time())))
            calls += 1
            t = tallies.setdefault("Q", lab.Tally())
            t.asked += 1
            for p in props:
                if not isinstance(p, tuple):
                    lab.process(p, "Q", coord, reg, uni, mem, t, models, outputs)
        _mark_today("Q")

    # R -- code lab for rule-shaped debt.
    if calls < calls_left and time.time() < deadline:
        k = max(0, min(3, calls_left - calls))
        dons, tally = code_lab(lab.DEBT, uni, max_items=k, deadline=deadline, chat=chat)
        calls += int(tally.get("asked", 0))
        outputs["donate"].extend(dons)
        rep["R"] = tally

    # S -- source scout, one plane per pass in rotation.
    if calls < calls_left and time.time() < deadline:
        doc = _read_json(SCOUTED, {}) or {}
        cursor = int(doc.get("cursor", 0)) % len(SCOUT_PLANES)
        plane = SCOUT_PLANES[cursor]
        try:
            import asia_collector
            known = {urllib.parse.urlsplit(str(s.get("url"))).netloc.lower()
                     for s in (_read_json(asia_collector.REGISTRY, {}) or {}).get("sources") or []}
        except Exception:                              # pragma: no cover
            known = set()
        known |= {urllib.parse.urlsplit(str(s.get("url"))).netloc.lower()
                  for s in doc.get("sources") or []}
        text, model = _chat(SCOUT_SYSTEM, f"Language/region: {plane[1]} ({plane[0]}). "
                            f"Symbols the desk trades: {', '.join(sorted(uni)[:120])}", chat=chat)
        calls += 1
        rows, why = scout_rows(text, plane, known, uni)
        for r in rows:
            if time.time() > deadline:
                break
            r["probe"] = probe(r)
            r["model"] = model
            r["probed_at"] = _now()
        doc["sources"] = [*(doc.get("sources") or []), *rows]
        doc["cursor"] = cursor + 1
        doc["generated_at"] = _now()
        _write_json(SCOUTED, doc)
        rep["S"] = {"plane": plane[1], "proposed": len(rows), "discards": dict(why),
                    "reachable": sum(1 for r in rows if r["probe"] == "REACHABLE")}

    # T -- live-sleeve red team, once a day, advisory only.
    if _due_today("T") and calls < calls_left and time.time() < deadline:
        sleeves = live_sleeves()
        if sleeves:
            doc, n = red_team(sleeves, chat=chat, deadline=deadline,
                              max_calls=max(1, min(4, calls_left - calls)))
            calls += n
            _write_json(RED_TEAM, doc)
            rep["T"] = {"live": len(sleeves), "attacked": len(doc["attacked"]),
                        "modes": doc["modes"]}
        else:
            rep["T"] = {"live": 0, "why": "no LIVE sleeve in data/sleeves.json on this host"}
        _mark_today("T")
    return rep, calls


# ============================================================================ coverage fence
#: Roles that run once a UTC day; the fence reads them on their own cadence.
DAILY_ROLES = ("Q", "T")


def coverage_report(models: dict[str, Any], pass_cov: dict[str, dict[str, Any]],
                    tallies: dict[str, dict[str, Any]], role_report: dict[str, Any],
                    cb_tone: dict[str, Any], credit: dict[str, Any], chain: dict[str, Any], *,
                    seat_on: bool, dry_run: bool, rotation: dict[str, str] | None = None,
                    window_h: int | None = None, budget_bound: bool = False,
                    collector: dict[str, Any] | None = None) -> dict[str, Any]:
    """EVERY MODEL, EVERY LAB, EVERY ROLE PRODUCES EVERY CYCLE (principal 2026-10-13). RED names
    each one that did not, and why: never asked (cap), asked and silent, or the chain fell
    through to another model (rate limit or outage on that one).

    THE ACCOUNT'S DAILY LIMIT IS SPREAD, NOT IGNORED. When OpenRouter's measured allowance cannot
    give every free model a call every hour, the lab rotates least-recently-asked first and the
    cycle is the rotation window (`window_h`). A model not asked this pass is ROTATING, not red,
    while its last ask is inside that window, or while it has never been asked and the pass spent
    its whole share (`budget_bound`); past the window it is red."""
    red: list[str] = []
    rotation = rotation or {}
    now_dt = datetime.now(UTC)
    yields = (credit or {}).get("models") or {}
    rows: dict[str, Any] = {}
    available = sorted(k for k, r in models.items() if r.get("status") == "REGISTERED")
    for k in available:
        r = models[k]
        pc = pass_cov.get(k) or {}
        y = yields.get(k) or {}
        state = ("ANSWERED" if pc.get("answered") else
                 "FELL_THROUGH" if pc.get("fell_through_to") else
                 "SILENT" if pc.get("asked") else "NOT_ASKED")
        if state == "NOT_ASKED" and window_h:
            last = _parse_ts(rotation.get(k))
            if (last is not None and now_dt - last <= timedelta(hours=window_h)) or (
                    last is None and budget_bound):
                state = "ROTATING"
        rows[k] = {"state_this_cycle": state, "asked_total": int(r.get("asked", 0)),
                   "replies_total": int(r.get("replies", 0)),
                   "accepted_total": int(r.get("accepted", 0)),
                   "exact_cells_total": int(r.get("exact", 0)),
                   "novel_cells_total": int(r.get("novel", 0)),
                   "certified": int(y.get("certified", 0)), "certified_keff": y.get("keff", 0.0),
                   "keff_per_call": y.get("keff_per_call", 0.0),
                   "fell_through_to": pc.get("fell_through_to") or []}
        if state not in ("ANSWERED", "ROTATING"):
            red.append(f"model {k}: {state}")
    for k, r in models.items():
        if r.get("status") in ("DELISTED", "REVIEW_PENDING") and k not in rows:
            rows[k] = {"state_this_cycle": r["status"]}
    labs = {}
    for key, t in tallies.items():
        state = ("PRODUCED" if int(t.get("proposals", 0)) else
                 "SILENT" if int(t.get("asked", 0)) else "NOT_ASKED")
        labs[key] = state
        if state != "PRODUCED" and key not in ("SYNTHESIS", "CONVERTER", *DAILY_ROLES):
            red.append(f"lab {key}: {state}")
    roles: dict[str, str] = {}
    daily = _read_json(DAILY, {}) or {}
    yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
    for key in DAILY_ROLES:
        ran = str(daily.get(key) or "")
        roles[key] = "RAN_TODAY" if ran == _now()[:10] else (
            "RAN_YESTERDAY" if ran == yesterday else "NOT_RUN")
        if roles[key] == "NOT_RUN":
            red.append(f"role {key}: has not run in its daily window")
    for key in ("R", "S"):
        rr = (role_report or {}).get(key)
        roles[key] = "RAN" if isinstance(rr, dict) else "NOT_RUN"
        if isinstance(rr, dict) and str(rr.get("state", "")).startswith("DISABLED"):
            roles[key] = str(rr["state"]).split(":")[0]       # deliberate, named, not silent
        if roles[key] == "NOT_RUN":
            red.append(f"role {key}: not run this cycle")
    cb_state = str((cb_tone or {}).get("state") or ("RAN" if (cb_tone or {}).get("docs") is not
                                                     None else "NOT_RUN"))
    roles["CB_TONE"] = "RAN" if (cb_tone or {}).get("docs") is not None else cb_state
    if roles["CB_TONE"] != "RAN":
        red.append(f"role CB_TONE: {roles['CB_TONE']}")
    if collector is not None:
        roles["COLLECTOR"] = str(collector.get("state") or "NOT_RUN")
        if roles["COLLECTOR"] not in ("RAN", "NOTHING_OWED"):
            red.append(f"role COLLECTOR: {roles['COLLECTOR']}")
    if not available:
        red.append("no free model registered: OpenRouter catalogue unreadable or key absent")
    verdict = ("UNMEASURED" if dry_run or not seat_on else "GREEN" if not red else "RED")
    return {"generated_at": _now(), "verdict": verdict,
            "rule": "every available free model, every lab and every LLM role produces on every "
                    "cycle; RED names each one that did not",
            "red": red[:200], "models_available": len(available),
            "models_answered": sum(1 for k in available if rows[k]["state_this_cycle"] ==
                                   "ANSWERED"),
            "models_rotating": sum(1 for k in available if rows[k]["state_this_cycle"] ==
                                   "ROTATING"),
            "rotation_window_h": window_h or UNMEASURED,
            "models": rows, "labs": labs, "roles": roles,
            "chain": {k: (chain or {}).get(k) for k in ("verdict", "cloud_usable",
                                                         "skipped_no_key")}}


def _parse_ts(raw: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
