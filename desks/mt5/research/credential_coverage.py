"""CREDENTIAL COVERAGE -- the hourly answer to "which keys should the principal register, and did
the ones already set turn into cells?"

For every environment credential in `libs/data/credentials.registry()` this writes, to
`reports/CREDENTIAL_COVERAGE.json`:

  * whether it is present ON THIS HOST (SET / MISMATCHED_NAME / BLOCKED_AUTH) and under which
    accepted name -- presence only, never a value;
  * every consumer (fetcher file, branch, the names it reads), whether that file is on this
    checkout, and whether it is WIRED to a clock (an hourly_cycle leg, a VPS ops script or unit,
    or a box scheduled-task installer) -- found by searching those clock files for the consumer's
    file stem or leg, so the answer cannot drift from the code;
  * cells minted from it in the last 24h, read from the consumers' OWN donation files
    (`data/intelligence/<seat>/discoveries_*.json`): a row that names its `credential_var` is
    attributed to that var, otherwise the consumer's total is reported as shared. A seat
    directory that does not exist here is UNMEASURED, never 0;
  * an ESTIMATE of cells/day the key unlocks (`credentials.estimate_for`), labelled as one, and
    the rank it gives;
  * every consumer that reads a different NAME from the principal's (`name_mismatches`), and the
    keyless sources with where they are wired.

`--markdown PATH` also writes the ranked KEYS_TO_REGISTER table (one `setx` line per key,
placeholder values only).

    python desks/mt5/research/credential_coverage.py --once [--markdown PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data import credentials as cred  # noqa: E402

REPORT = DESK / "reports" / "CREDENTIAL_COVERAGE.json"
UNMEASURED = cred.UNMEASURED
_STAMP = re.compile(r"discoveries_(\d{8})_(\d{4})")


def clock_files(root: Path = ROOT) -> dict[str, str]:
    """Every file that schedules work, by relative path -> its text."""
    pats = ("desks/mt5/research/hourly_cycle.py", "ops/*.sh", "ops/*.service",
            "desks/mt5/scripts/*.ps1")
    out: dict[str, str] = {}
    for pat in pats:
        for p in sorted(root.glob(pat)):
            try:
                out[str(p.relative_to(root))] = p.read_text("utf-8", errors="replace")
            except OSError:
                continue
    return out


def wired(c: cred.Consumer, clocks: Mapping[str, str], root: Path = ROOT) -> dict[str, Any]:
    if "/" not in c.path or not (root / c.path).exists():
        return {"on_this_checkout": False, "wired": "NOT_ON_THIS_BRANCH",
                "lands_with": c.branch}
    stems = {Path(c.path).stem}
    if c.leg:
        stems.add(c.leg)
    hits = sorted(f for f, text in clocks.items()
                  if any(re.search(rf"(?<![\w]){re.escape(s)}(?![\w])", text) for s in stems)
                  and not f.endswith(Path(c.path).name))
    return {"on_this_checkout": True, "wired": "WIRED" if hits else "NOT_WIRED",
            "clocks": hits}


def cells_24h(var: str, c: cred.Consumer, now: datetime, desk: Path = DESK) -> dict[str, Any]:
    """From the consumer's own donation files. UNMEASURED when no seat directory exists here."""
    if not c.seats:
        return {"cells_24h": UNMEASURED, "why": "consumer declares no donation seat"}
    cut = now - timedelta(hours=24)
    seen_dir = False
    total = attributed = files = 0
    per_var = False
    for seat in c.seats:
        d = desk / "data" / "intelligence" / seat
        if not d.is_dir():
            continue
        seen_dir = True
        for p in d.glob("discoveries_*.json"):
            m = _STAMP.search(p.name)
            if not m:
                continue
            try:
                at = datetime.strptime(m[1] + m[2], "%Y%m%d%H%M").replace(tzinfo=UTC)
            except ValueError:
                continue
            if at < cut:
                continue
            try:
                rows = json.loads(p.read_text("utf-8")).get("discoveries") or []
            except (OSError, ValueError, AttributeError):
                continue
            files += 1
            total += len(rows)
            for r in rows:
                if isinstance(r, dict) and "credential_var" in r:
                    per_var = True
                    attributed += int(r.get("credential_var") == var)
    if not seen_dir:
        return {"cells_24h": UNMEASURED,
                "why": f"no data/intelligence/{'|'.join(c.seats)} on this host"}
    if per_var:
        return {"cells_24h": attributed, "attribution": "per_var", "files": files}
    return {"cells_24h": total, "attribution": "shared_by_consumer", "files": files}


def build(now: datetime | None = None, environ: Mapping[str, str] | None = None,
          root: Path = ROOT, desk: Path = DESK) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    clocks = clock_files(root)
    rows: list[dict[str, Any]] = []
    for v in cred.registry():
        st = cred.status(v, environ, root)
        est = cred.estimate_for(v)
        cons = []
        # Name states against the CANONICAL name when nothing is set, so the report says ahead
        # of time which readers a principal's `setx` would leave dark.
        states = {s["path"]: s for s in cred.consumer_states(v, st["present_as"] or [v.env],
                                                             root)}
        for c in v.consumers:
            w = wired(c, clocks, root)
            _, reads = cred.effective_reads(c, v, root)
            cons.append({"path": c.path, "branch": c.branch, "leg": c.leg,
                         "reads": [n for n in reads if not n.startswith("file:")],
                         "secrets_keys": [n for n in reads if n.startswith("file:")],
                         "name_state": states[c.path]["state"],
                         "note": c.note, **w, **cells_24h(v.env, c, now, desk)})
        rows.append({
            "env": v.env, "accepted_names": list(v.accepted), "secrets_keys": list(v.secrets),
            "provider": v.provider, "signup_url": v.signup_url, "free_tier": v.free_tier,
            "unlocks": v.unlocks, "instruments": list(v.instruments),
            "families": list(v.families), "kind": v.kind, "group": v.group or None,
            "principal_list": v.principal_list, "built": v.built,
            # Actionable = someone consumes it AND the provider's terms allow this desk's machine
            # use. A var failing either is listed under "considered and not built", never ranked
            # among the keys to register.
            "machine_use_allowed": v.machine_use_allowed, "terms": v.terms or None,
            "actionable": bool(v.consumers) and v.machine_use_allowed,
            "status": st["status"], "present_as": st["present_as"],
            "dark_consumers": st["dark_consumers"],
            "resolved_on_merge": st.get("resolved_on_merge", []), "consumers": cons,
            "estimate": {"label": "ESTIMATE", "cells_per_day": est.cells_per_day,
                         "grid": est.grid or None, "per_pass_cap": est.per_pass_cap,
                         "series_or_pairs": est.series, "symbols": est.symbols,
                         "cells_per_pair": est.cells_per_pair, "basis": est.basis or
                         ("no consumer built" if not v.consumers else UNMEASURED)},
            "setx": cred.setx_line(v)})
    # A paired var (an id and its secret) ranks with its group's best estimate, right after it.
    group_best: dict[str, int] = {}
    for r in rows:
        if r["group"]:
            group_best[r["group"]] = max(group_best.get(r["group"], 0),
                                         r["estimate"]["cells_per_day"] or 0)
    ranked = sorted(rows, key=lambda r: (
        not r["actionable"],
        -(group_best.get(r["group"], 0) if r["group"] else r["estimate"]["cells_per_day"] or 0),
        str(r["group"] or r["env"]), r["estimate"]["cells_per_day"] is None,
        not r["principal_list"], r["env"]))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    keyless = []
    for k in cred.keyless():
        present = [p for p in k.get("wired_in") or () if (root / p).exists()]
        row = {**k, "wired_in": list(k.get("wired_in") or ()),
               "status": "WIRED" if present else "NOT_WIRED"}
        if k.get("credential") and present:
            # A keyless door the keyed_sources leg reads: its clock and its own cells, the same
            # measurement a keyed var gets (cells attributed by `credential_var`).
            c = cred.Consumer(present[0], (), cred.LIVE, cred.KS_LEG,
                              tuple(k.get("seats") or ()))
            w = wired(c, clocks, root)
            row.update({"status": "WIRED" if w["wired"] == "WIRED" else w["wired"],
                        "clocks": w.get("clocks", []),
                        **cells_24h(str(k["credential"]), c, now, desk)})
        keyless.append(row)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"generated_at": now.isoformat(timespec="seconds"), "host": platform.node(),
            "writer": "research/credential_coverage.py",
            # The CRO duty this artifact answers (#121's duty table): credential coverage.
            "cro_duty": "D24",
            "rule": ("presence only -- no value is read, printed or written. BLOCKED_AUTH until "
                     "set; MISMATCHED_NAME when set under a name a consumer does not read (a "
                     "consumer on another branch whose reader accepts it is RESOLVED_ON_MERGE, "
                     "not a mismatch). "
                     "cells_24h is read from the consumers' own donation files; UNMEASURED when "
                     "that file tree is absent here. estimate.cells_per_day is an ESTIMATE "
                     "(declared series x symbols x cells per pair, bounded by the per-pass cap "
                     "x 24)"),
            "status_counts": counts, "vars": ranked,
            # A registry file that fails to load is NAMED here; the leg still writes its report.
            "registry_error": cred.load_error(),
            "name_mismatches": cred.name_mismatches(root),
            "status_words_mapped_to_BLOCKED_AUTH": sorted(cred.BLOCKED_SYNONYMS),
            "keyless": keyless}


def markdown(doc: Mapping[str, Any]) -> str:
    lines = ["# Keys to register", "",
             *([f"**{doc['registry_error']}** -- the registry did not load; this list is "
                "empty until it does.", ""] if doc.get("registry_error") else []),
             f"Generated {doc['generated_at']} by `desks/mt5/research/credential_coverage.py` "
             "(the hourly `credential_coverage` leg rewrites `desks/mt5/reports/"
             "CREDENTIAL_COVERAGE.json`). Cells/day is an **ESTIMATE**: declared series x "
             "mapped symbols x cells per pair, bounded by the consumer's per-pass cap x 24. "
             "Status is for the host that generated this file.", "",
             "| Rank | Key | Env var | Signup | Unlocks | Est. cells/day | Consumer | Status |",
             "|---:|---|---|---|---|---:|---|---|"]
    for r in doc["vars"]:
        if not r["actionable"]:
            continue
        cons = "; ".join(f"`{c['path']}` ({c['branch']})" for c in r["consumers"])
        est = r["estimate"]["cells_per_day"]
        if est is None and r["group"]:
            est = f"(pair: {r['group']})"
        lines.append(f"| {r['rank']} | {r['provider']} | `{r['env']}` | {r['signup_url']} | "
                     f"{r['unlocks']} | {est if est is not None else 'UNMEASURED'} | {cons} | "
                     f"{r['status']} |")
    lines += ["", "## Set commands (placeholders only; run on the trading box, then restart the "
              "service so the new environment is inherited)", "", "```"]
    lines += [r["setx"] for r in doc["vars"] if r["actionable"]]
    lines += ["```", "", "## Considered and not built", "",
              "| Env var | Provider | Signup | Why not |", "|---|---|---|---|"]
    for r in doc["vars"]:
        if not r["actionable"]:
            lines.append(f"| `{r['env']}` | {r['provider']} | {r['signup_url']} | "
                         f"{r['built'].removeprefix('NOT_BUILT: ')} |")
    lines += ["", "## Readers that use a different name", "",
              "| Var | Consumer | Branch | Names it reads |", "|---|---|---|---|"]
    for m in doc["name_mismatches"]:
        lines.append(f"| `{m['var']}` | `{m['consumer']}` | {m['branch']} | "
                     f"{', '.join(m['reads'])} |")
    lines += ["", "## No key needed", "", "| Provider | Wired in | Status |", "|---|---|---|"]
    for k in doc["keyless"]:
        lines.append(f"| {k['provider']} | {', '.join(k['wired_in']) or '-'} | {k['status']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--markdown", default="")
    a = ap.parse_args(argv)
    doc = build()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), "utf-8")
    os.replace(tmp, REPORT)
    if a.markdown:
        Path(a.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(a.markdown).write_text(markdown(doc), "utf-8")
    print(f"credential_coverage: {doc['status_counts']}; {len(doc['name_mismatches'])} name "
          "mismatches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
