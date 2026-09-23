"""F10 -- A TRAINED MODEL OF WHAT FAILS, so the gauntlet stops re-learning it one cell at a time.

THE PRINCIPAL, 2026-09-12:

    A trained meta-model over historical experiments predicting P(survive), likely failure gate,
    expected forward retention and expected dElog -- rejecting expensive low-value experiments
    BEFORE the gauntlet while preserving exploration.

THE GAP, AS THE LEDGER STATES IT: graveyard material already feeds back into search and
structural genealogy exists; the TRAINED MODEL does not. The difference is what the desk pays for
it. Every cell the gauntlet judges costs ten gates of compute AND a share of a fixed family-wise
error budget that every other hypothesis then has to clear. A desk that cannot predict which cells
will fail pays that twice: once in compute, once in the bar it raises for everything else.

THE TRAINING SET IS THE DESK'S OWN RECORD, and it is large: 21,582 docket cells, 20,911 of them
judged, 61 certificates. That is a real classification problem with a 0.28% base rate -- and the
base rate is why this must be CALIBRATED rather than merely ranked. A model that says "3%" about
cells that certify at 3% is worth compute; a model that says "3%" about cells that certify at 0.2%
will refuse the whole docket on a number that means nothing.

FOUR THINGS WERE ASKED FOR AND THE DESK CAN HONESTLY SUPPLY TWO (L1.28a):

    P(survive)              TRAINED. Logistic regression, L2, on a TEMPORAL split -- older cells
                            train, newer cells test -- because this model is used going forward
                            and a random split would let tomorrow's cells teach it about today's.
    expected forward        MEASURED where clocks exist: forward expectancy against in-sample
    retention               expectancy, per certificate that has a clock.
    likely failure gate     UNMEASURED, and the missing record is NAMED: no artifact on this box
                            records WHICH gate rejected which cell. `gauntlet_seen_cells.json`
                            records that a cell was judged and when; nothing records the verdict.
                            Until a per-cell gate ledger exists this cannot be trained, and
                            guessing it from family would be inventing the answer.
    expected dElog          UNMEASURED for the same reason one step further on: it needs the
                            allocator's marginal contribution per certificate, and the live book
                            holds 16 deals across 3 days.

IT RANKS AND IT DOES NOT REFUSE, and that is a deliberate limit rather than timidity. A model
trained on what HAS survived cannot know about a region the desk has never tried; letting it veto
would make the search a fixed point of its own history. So:

    THE EXPLORATION FLOOR IS ABSOLUTE. A stated share of every admission is drawn from the cells
    the model scores WORST, precisely because that is where its own evidence is thinnest. The
    floor is not a concession to fairness -- it is the only thing that lets the model be wrong in
    a recoverable way.

    A FAMILY WITH TOO FEW OBSERVATIONS IS NEVER DOWNRANKED. Absence of evidence sorts to the
    middle, never to the bottom.

    NOTHING IS DELETED. The output is an ORDER over the docket plus a published score; the
    gauntlet's own cursor rules still decide what it judges.

    python desks/mt5/research/negative_knowledge.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SEEN = DESK / "data" / "hypotheses" / "gauntlet_seen_cells.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
SHADOW = (DESK / "reports" / "shadow" / "shadow_state.json",
          DESK / "reports" / "shadow" / "qquant_shadow_state.json",
          DESK / "reports" / "shadow" / "scalp_shadow_state.json")
OUT = DESK / "reports" / "NEGATIVE_KNOWLEDGE.json"
MODEL = DESK / "data" / "negative_knowledge_model.json"

#: Share of admissions reserved for the cells this model scores WORST. Not a fairness gesture:
#: a model trained on what has survived cannot know about a region the desk has never tried, and
#: without a floor the search becomes a fixed point of its own history. The desk's own
#: EXPLORE_SHARE is the same argument at the capital layer.
EXPLORE_FLOOR = 0.20

#: Observations a family needs before its own history may move a cell's score. Below this the
#: family's rate is indistinguishable from the base rate and a confident downrank would be
#: arithmetic on three cells. Absence of evidence sorts to the MIDDLE, never to the bottom.
MIN_FAMILY_OBS = 40

#: Fraction of the record used for training, split by TIME. A random split would let a cell first
#: seen tomorrow teach the model about a cell first seen today, and this model's whole job is to
#: judge cells it has never seen.
TRAIN_FRAC = 0.70

#: L2 strength and gradient steps. Strong regularisation on purpose: at a 0.28% base rate an
#: unregularised fit will drive a rare-category coefficient to infinity on a single survivor.
L2 = 1.0
STEPS = 400
LR = 0.5

#: Survivors the held-out window needs before AUC or calibration mean anything. Ten is not a
#: statistical threshold so much as a floor of legibility: below it one certificate moves AUC by
#: tenths, and a reliability table is eight bins of zero and one bin of one.
MIN_TEST_POSITIVES = 10

SEED = 20260912


def _load_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _cell_key(symbol: Any, family: Any, params: Any) -> tuple[str, str, str]:
    """The identity of a CELL: symbol, family and the exact parameterisation."""
    return (str(symbol or ""), str(family or ""), json.dumps(params, sort_keys=True))


def _positives() -> set[tuple[str, str, str]]:
    """Cells that hold a certificate -- symbol, family AND PARAMS. The label.

    THE PARAMS ARE THE WHOLE LABEL AND LEAVING THEM OUT FAKED THE MODEL. The first version keyed
    on (symbol, family), which marked every sibling parameterisation positive because one of them
    certified: 3,487 of 21,582 docket rows labelled survivor against a true 61, a base rate of
    20.6% against a true 0.283%, and a test AUC of 0.986 that was the model rediscovering which
    symbol-family pairs hold a certificate -- i.e. reading the label off the label.

    On the exact key the match is 61 of 21,582, which is the registry's own count. A rate that
    equals the thing it is counting is the only evidence that the join is right.
    """
    doc = _load_json(SURVIVORS) or {}
    out: set[tuple[str, str, str]] = set()
    for row in (doc.get("survivors") or {}).values():
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") or {}
        sym = spec.get("symbol") or row.get("sym")
        fam = spec.get("family")
        if sym and fam:
            out.add(_cell_key(sym, fam, spec.get("params")))
    return out


def _retention() -> dict[str, Any]:
    """Forward expectancy against the in-sample expectancy that earned the certificate."""
    rows: list[dict[str, Any]] = []
    for p in SHADOW:
        d = _load_json(p)
        if not isinstance(d, dict):
            continue
        for key, r in d.items():
            if not isinstance(r, dict):
                continue
            fwd, n = r.get("exp_r"), r.get("n")
            if isinstance(fwd, (int, float)) and isinstance(n, (int, float)) and n >= 5:
                rows.append({"clock": key, "forward_exp_r": round(float(fwd), 6),
                             "n": int(n), "status": r.get("status")})
    if not rows:
        return {"status": "UNMEASURED",
                "why": "no forward clock carries at least five trades and an expectancy"}
    vals = [r["forward_exp_r"] for r in rows]
    vals.sort()
    mid = vals[len(vals) // 2]
    return {"status": "OK", "n_clocks": len(rows),
            "median_forward_exp_r": round(mid, 6),
            "n_positive": sum(1 for v in vals if v > 0),
            "clocks": rows[:40],
            "caveat": ("this is forward expectancy, not RETENTION: retention needs the in-sample "
                       "expectancy each clock's certificate was granted on, and the registry "
                       "row does not carry it. Reported as what it is.")}


# ------------------------------------------------------------------------------ the features

#: Verdicts the gate ledger needs before a failure-gate distribution is worth quoting. Below
#: this the modal gate is whichever one the last sweep happened to reach first.
MIN_GATE_ROWS = 200


def _failure_gates() -> dict[str, Any]:
    """Which gate actually kills cells, overall and per family, from the gate verdict ledger.

    THE DATA EXISTED AND WAS BEING THROWN AWAY. The gauntlet's verdicts have always carried
    `terminal_gate`; they were written to universal_gates_external.json and OVERWRITTEN every
    sweep, so the desk held one hour of rejections and no history -- which is why the first run of
    this organ had to report "likely failure gate: UNMEASURED". external_gauntlet now appends each
    cell's verdict to a ledger ON CHANGE ONLY, so the file grows at the rate the desk changes its
    mind rather than at 21,000 rows an hour.

    NO MODEL IS FITTED HERE AND NONE IS NEEDED. "Which gate is this family most likely to die at"
    is a frequency, and a frequency with a Wilson bound is a better answer than a classifier
    trained to reproduce it.
    """
    if not GATE_LEDGER.exists():
        return {"status": "UNMEASURED",
                "why": (f"no gate ledger at {GATE_LEDGER.relative_to(ROOT)} yet. "
                        f"external_gauntlet writes it from the sweep after this code lands; "
                        f"until then the desk genuinely has no per-cell verdict history."),
                "repair": "none needed -- the producer is wired; this fills on the next sweep"}
    overall: dict[str, int] = {}
    per_family: dict[str, dict[str, int]] = {}
    n = 0
    for ln in GATE_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("passed"):
            continue
        g = str(r.get("terminal_gate") or "UNKNOWN")
        fam = str(r.get("family") or "UNKNOWN")
        overall[g] = overall.get(g, 0) + 1
        per_family.setdefault(fam, {})[g] = per_family.setdefault(fam, {}).get(g, 0) + 1
        n += 1
    if n < MIN_GATE_ROWS:
        return {"status": "UNMEASURED", "n_rows": n,
                "why": (f"the gate ledger holds {n} rejection(s) against a floor of "
                        f"{MIN_GATE_ROWS}. Below that the modal gate is whichever one the last "
                        f"sweep reached first, not what kills cells.")}

    def _wilson(k: int, tot: int) -> list[float]:
        if tot <= 0:
            return [0.0, 1.0]
        z, ph = 1.96, k / tot
        d = 1 + z * z / tot
        c = (ph + z * z / (2 * tot)) / d
        h = z * math.sqrt(ph * (1 - ph) / tot + z * z / (4 * tot * tot)) / d
        return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]

    fams = []
    for fam, gates in sorted(per_family.items(), key=lambda t: -sum(t[1].values())):
        tot = sum(gates.values())
        if tot < 20:
            continue
        g, k = max(gates.items(), key=lambda t: t[1])
        fams.append({"family": fam, "n_rejections": tot, "most_likely_gate": g,
                     "share": round(k / tot, 4), "ci95": _wilson(k, tot),
                     "gates": dict(sorted(gates.items(), key=lambda t: -t[1])[:6])})
    return {"status": "OK", "n_rejections": n,
            "overall": dict(sorted(overall.items(), key=lambda t: -t[1])),
            "by_family": fams[:20],
            "reading": ("the gate a family dies at is where its compute is actually being spent. "
                        "A family that always dies at gate 1 costs one gate per cell; one that "
                        "dies at gate 9 has paid for eight.")}


def _rows() -> list[dict[str, Any]]:
    raw = _load_json(DOCKET)
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def _feature_names(fams: list[str], srcs: list[str]) -> list[str]:
    return (["bias", "log10_n", "exp_r", "max_dd_r", "t_stat", "profit_factor", "win_rate",
             "has_n", "has_exp_r", "has_t", "family_rate", "source_rate", "symbol_rate"]
            + [f"fam:{f}" for f in fams] + [f"src:{s}" for s in srcs])


def _rate_map(rows: list[dict[str, Any]], key: str, pos: set[tuple[str, str, str]],
              base: float) -> dict[str, float]:
    """Historical certification rate per category, computed on TRAIN ROWS ONLY.

    Smoothed toward the base rate by MIN_FAMILY_OBS pseudo-counts, so a category seen three times
    cannot claim a rate -- it sits at the base rate, which is the honest prior for something the
    desk has barely tried.
    """
    agg: dict[str, list[float]] = {}
    for r in rows:
        k = str(r.get(key) or "UNKNOWN")
        y = 1.0 if _cell_key(r.get("symbol"), r.get("family"),
                             r.get("params")) in pos else 0.0
        agg.setdefault(k, []).append(y)
    return {k: (sum(v) + base * MIN_FAMILY_OBS) / (len(v) + MIN_FAMILY_OBS)
            for k, v in agg.items()}


def _vec(r: dict[str, Any], fams: list[str], srcs: list[str],
         fam_rate: dict[str, float], src_rate: dict[str, float],
         sym_rate: dict[str, float], base: float) -> list[float]:
    def num(k: str, d: float = 0.0) -> float:
        v = r.get(k)
        return float(v) if isinstance(v, (int, float)) and math.isfinite(float(v)) else d

    n = num("n")
    fam = str(r.get("family") or "UNKNOWN")
    src = str(r.get("source") or "UNKNOWN")
    sym = str(r.get("symbol") or "UNKNOWN")
    v = [1.0,
         math.log10(max(n, 1.0)),
         max(-1.0, min(1.0, num("exp_r"))),
         max(-20.0, min(20.0, num("max_dd_r"))),
         max(-20.0, min(20.0, num("t_stat"))),
         max(0.0, min(10.0, num("profit_factor"))),
         max(0.0, min(1.0, num("win_rate"))),
         1.0 if isinstance(r.get("n"), (int, float)) else 0.0,
         1.0 if isinstance(r.get("exp_r"), (int, float)) else 0.0,
         1.0 if isinstance(r.get("t_stat"), (int, float)) else 0.0,
         fam_rate.get(fam, base), src_rate.get(src, base), sym_rate.get(sym, base)]
    v += [1.0 if fam == f else 0.0 for f in fams]
    v += [1.0 if src == s else 0.0 for s in srcs]
    return v


# ------------------------------------------------------------------------------- the model

def _fit(x: Any, y: Any) -> Any:
    """L2 logistic regression by full-batch gradient ascent on the log-likelihood.

    Written out rather than imported: sklearn is a declared dependency of this repo and is NOT
    installed on the box that runs this, and an organ that cannot run where it is scheduled is
    the defect III.16 names. Thirty lines of numpy have no such dependency.
    """
    import numpy as np
    w = np.zeros(x.shape[1], dtype=float)
    n = max(1, x.shape[0])
    for _ in range(STEPS):
        z = np.clip(x @ w, -30, 30)
        p = 1.0 / (1.0 + np.exp(-z))
        g = x.T @ (y - p) / n - L2 * w / n
        w = w + LR * g
    return w


def _predict(x: Any, w: Any) -> Any:
    import numpy as np
    return 1.0 / (1.0 + np.exp(-np.clip(x @ w, -30, 30)))


def _reliability(p: Any, y: Any, bins: int = 8) -> list[dict[str, Any]]:
    """Predicted rate against observed rate, by predicted decile. The only calibration that counts.

    A P(survive) used to spend compute must be CALIBRATED, not merely ordered: a model that says
    "3%" about cells certifying at 0.2% would refuse the whole docket on a number that means
    nothing, and the ranking would look fine the whole time.
    """
    import numpy as np
    order = np.argsort(p)
    chunks = np.array_split(order, bins)
    out: list[dict[str, Any]] = []
    for i, idx in enumerate(chunks):
        if idx.size == 0:
            continue
        out.append({"bin": i + 1, "n": int(idx.size),
                    "predicted": round(float(np.mean(p[idx])), 6),
                    "observed": round(float(np.mean(y[idx])), 6),
                    "n_survivors": int(np.sum(y[idx]))})
    return out


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy unavailable ({exc})"}

    rows = _rows()
    pos = _positives()
    if len(rows) < 500 or not pos:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": (f"{len(rows)} docket row(s) and {len(pos)} certified cell(s) -- too "
                        f"little to train anything honest")}

    # TEMPORAL SPLIT. `first_seen` orders the record; rows without it sort last and land in test,
    # which is the conservative direction -- an undated row never teaches the model.
    rows.sort(key=lambda r: str(r.get("first_seen") or "9999"))
    ntr = int(len(rows) * TRAIN_FRAC)
    train, test = rows[:ntr], rows[ntr:]
    n_pos_train = sum(
        1 for r in train
        if _cell_key(r.get("symbol"), r.get("family"), r.get("params")) in pos)
    base = n_pos_train / max(len(train), 1)
    if base <= 0:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("no certified cell falls in the training window, so the model has no "
                        "positive class to learn from. UNMEASURED, not a model of nothing.")}

    counts: dict[str, int] = {}
    scounts: dict[str, int] = {}
    for r in train:
        counts[str(r.get("family") or "UNKNOWN")] = \
            counts.get(str(r.get("family") or "UNKNOWN"), 0) + 1
        scounts[str(r.get("source") or "UNKNOWN")] = \
            scounts.get(str(r.get("source") or "UNKNOWN"), 0) + 1
    fams = [f for f, c in sorted(counts.items(), key=lambda t: -t[1])[:12]
            if c >= MIN_FAMILY_OBS]
    srcs = [s for s, c in sorted(scounts.items(), key=lambda t: -t[1])[:10]
            if c >= MIN_FAMILY_OBS]

    fam_rate = _rate_map(train, "family", pos, base)
    src_rate = _rate_map(train, "source", pos, base)
    sym_rate = _rate_map(train, "symbol", pos, base)

    def mat(rs: list[dict[str, Any]]) -> tuple[Any, Any]:
        x = np.asarray([_vec(r, fams, srcs, fam_rate, src_rate, sym_rate, base) for r in rs],
                       dtype=float)
        y = np.asarray([1.0 if _cell_key(r.get("symbol"), r.get("family"),
                                         r.get("params")) in pos else 0.0
                        for r in rs], dtype=float)
        return x, y

    xtr, ytr = mat(train)
    xte, yte = mat(test)
    # Standardise on TRAIN moments; the bias column is left alone.
    mu, sd = xtr.mean(axis=0), xtr.std(axis=0)
    sd[sd == 0] = 1.0
    mu[0], sd[0] = 0.0, 1.0
    w = _fit((xtr - mu) / sd, ytr)
    pte = _predict((xte - mu) / sd, w)
    ptr = _predict((xtr - mu) / sd, w)

    n_pos_te = int(yte.sum())
    # AUC by the rank identity, which needs no library and no binning.
    if n_pos_te and n_pos_te < yte.size:
        order = np.argsort(pte)
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(1, yte.size + 1)
        npos, nneg = float(n_pos_te), float(yte.size - n_pos_te)
        auc = float((ranks[yte == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg))
    else:
        auc = float("nan")

    rel = _reliability(pte, yte) if n_pos_te else []
    names = _feature_names(fams, srcs)
    weight_rows: list[tuple[float, str]] = [
        (round(float(v), 5), n) for n, v in zip(names, w, strict=False)]
    weight_rows.sort(key=lambda t: -abs(t[0]))
    weights: list[dict[str, Any]] = [{"feature": n, "weight": v} for v, n in weight_rows]

    # THE RANKING, and the exploration floor that keeps it honest.
    score_rows: list[tuple[float, dict[str, Any]]] = [
        (round(float(p), 6), {"symbol": r.get("symbol"), "family": r.get("family"),
                              "source": r.get("source")})
        for r, p in zip(test, pte, strict=False)]
    score_rows.sort(key=lambda t: -t[0])
    scored: list[dict[str, Any]] = [{**d, "p_survive": v} for v, d in score_rows]
    floor_n = int(len(scored) * EXPLORE_FLOOR)

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "training": {"n_docket": len(rows), "n_train": len(train), "n_test": len(test),
                     "n_certified_cells": len(pos),
                     "train_base_rate": round(base, 6),
                     "test_base_rate": round(float(yte.mean()), 6),
                     "n_survivors_in_test": n_pos_te,
                     "split": "TEMPORAL by first_seen; undated rows sort last, into test",
                     "families_encoded": fams, "sources_encoded": srcs},
        "performance": {
            # THE VERDICT IS ABOUT THE EVIDENCE, NOT THE NUMBER. At a 0.39% base rate a held-out
            # window of 6,475 cells contains two survivors, and an AUC computed on two positives
            # moves by tenths when one of them moves one rank. Publishing 0.825 without saying
            # that is the shape of every flattering metric this desk has a fence against.
            "status": ("OK" if n_pos_te >= MIN_TEST_POSITIVES else "UNMEASURED"),
            "auc_test": None if not math.isfinite(auc) else round(auc, 4),
            "n_test_positives": n_pos_te,
            "train_mean_p": round(float(ptr.mean()), 6),
            "test_mean_p": round(float(pte.mean()), 6),
            "reliability_by_predicted_bin": rel,
            "reading": (
                "AUC says the ORDER is informative; the reliability table says whether the NUMBER "
                "is. Both are needed: a model used to spend compute must be calibrated, and an "
                "uncalibrated model with good AUC will refuse the whole docket on a probability "
                "that means nothing while its ranking still looks fine."
                if n_pos_te >= MIN_TEST_POSITIVES else
                f"UNMEASURED. The held-out window holds {n_pos_te} survivor(s) against a floor "
                f"of {MIN_TEST_POSITIVES}; any AUC or calibration figure above is INDICATIVE "
                f"ONLY and must not be quoted as this model's accuracy. The model is fitted and "
                f"its out-of-sample value is unknown, which is not the same as zero. It becomes "
                f"measurable when the desk has minted enough certificates for a test window to "
                f"contain some -- i.e. this field is a thermometer for the certificate rate as "
                f"much as for the model."),
        },
        "weights": weights[:20],
        "top_ranked": scored[:15],
        "exploration_floor": {
            "share": EXPLORE_FLOOR, "n_cells": floor_n,
            "drawn_from": "the LOWEST-scoring cells, which is where the model's evidence is "
                          "thinnest",
            "why": ("a model trained on what HAS survived cannot know about a region the desk "
                    "has never tried. Letting it veto would make the search a fixed point of its "
                    "own history; the floor is what lets the model be wrong recoverably."),
        },
        "forward_retention": _retention(),
        "likely_failure_gate": _failure_gates(),
        "expected_delta_elog": {
            "status": "UNMEASURED",
            "why": ("needs the allocator's MARGINAL contribution per certificate, and the live "
                    "book holds 16 deals across 3 days. A dElog estimated off that would be a "
                    "number about three days of noise."),
        },
        "boundary": (
            "IT RANKS AND IT DOES NOT REFUSE. Nothing is deleted, no cell is removed from the "
            "docket, and the gauntlet's own cursor rules still decide what it judges. A family "
            f"with fewer than {MIN_FAMILY_OBS} observations is never downranked -- absence of "
            f"evidence sorts to the middle, never to the bottom."),
        "why": (
            "every cell the gauntlet judges costs ten gates of compute AND a share of a fixed "
            "family-wise error budget that every other hypothesis then has to clear. A desk that "
            "cannot predict which cells will fail pays that twice: once in compute, once in the "
            "bar it raises for everything else."),
        "_model": {"weights": [float(v) for v in w], "mu": [float(v) for v in mu],
                   "sd": [float(v) for v in sd], "features": names,
                   "families": fams, "sources": srcs, "base_rate": base,
                   "family_rate": fam_rate, "source_rate": src_rate, "symbol_rate": sym_rate,
                   "trained_at": now.isoformat(timespec="seconds")},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report and the model")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"negative knowledge: {doc.get('status')} -- {doc.get('why')}")
        return 0
    t, pf = doc["training"], doc["performance"]
    print(f"negative knowledge: OK   {t['n_train']} train / {t['n_test']} test, "
          f"base rate {t['train_base_rate']:.4%}, {t['n_survivors_in_test']} survivor(s) in test")
    if pf["status"] == "OK":
        print(f"  AUC(test) {pf['auc_test']}  on {pf['n_test_positives']} test survivor(s)")
    else:
        print(f"  performance UNMEASURED -- {pf['n_test_positives']} survivor(s) in the held-out "
              f"window; AUC {pf['auc_test']} is INDICATIVE ONLY, do not quote it")
    for r in pf["reliability_by_predicted_bin"]:
        print(f"    bin {r['bin']}  n={r['n']:<6} predicted {r['predicted']:.4%}  "
              f"observed {r['observed']:.4%}  ({r['n_survivors']} survivor(s))")
    print("  what it learned:")
    for w in doc["weights"][:8]:
        print(f"    {w['feature']:<28} {w['weight']:+.4f}")
    print(f"  exploration floor: {doc['exploration_floor']['n_cells']} cell(s) "
          f"({doc['exploration_floor']['share']:.0%}) reserved for the lowest scores")
    fg = doc["likely_failure_gate"]
    if fg.get("status") == "OK":
        print(f"  failure gates: {fg['n_rejections']} rejection(s) recorded")
        for row in fg["by_family"][:6]:
            print(f"    {row['family']:<26} {row['most_likely_gate']:<22} "
                  f"{row['share']:.0%} of {row['n_rejections']} "
                  f"CI95 [{row['ci95'][0]:.0%}, {row['ci95'][1]:.0%}]")
    else:
        print(f"  failure gates: {fg.get('status')} -- {str(fg.get('why'))[:120]}")
    fr = doc["forward_retention"]
    if fr.get("status") == "OK":
        print(f"  forward retention: OK   {fr['n_clocks']} clock(s), "
              f"median forward exp_r {fr['median_forward_exp_r']}, "
              f"{fr['n_positive']} positive")
    else:
        print(f"  forward retention: {fr.get('status')} -- "
              f"{str(fr.get('why'))[:100]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    model = doc.pop("_model")
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    MODEL.write_text(json.dumps(model, indent=1, default=str), encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {MODEL}\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
