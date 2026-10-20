"""A BROKERAGE LOGIN DOES NOT CROSS THE BOX'S STATE WIRE. Never places an order.

`desks/mt5/scripts/sync_shadow_to_git.ps1` publishes the box's state blobs onto origin. The
live-identifier fence (tests/ops/test_live_infrastructure_is_not_published.py) is a pytest: it can
only notice a login AFTER origin holds it. This is the publish-time half. The publisher hashes the
allowlisted files, hands this module the BLOB ids it is about to commit, and drops whatever this
refuses -- so the bytes judged here are exactly the bytes published (audit v3: the first fence read
the file, then let `hash-object` read the disk again, and a write between the two went unchecked).

WHAT IT REFUSES (audit v3, measured false negatives and positives, 2026-10-14):
  * a login-shaped KEY -- `login`, `login_id`, `"Login ID"`, `account`, `account_number`,
    `accountLogin`, `account-login`, `mt5_login`, `fusion_live_login`, any case -- whose VALUE is
    account-shaped (4 to 12 digits, bare, quoted or first in a list);
  * the same inside escaped JSON (`{\\"login\\": ...}` in a string) and `\\u`-encoded keys;
  * a CSV/TSV header naming such a column, when any row of that column is account-shaped.
WHAT IT PASSES: `login_withheld` (the bool research/cost_truth.py writes), `account_key` (the
hash), null/true/false, `requires_login: 0`, `last_login: "<ts>"`, `login: "ok"`, `login: ""`,
and `account: {...}` / `account: "Fusion Zero"`. Python's `re.IGNORECASE` and `str.lower()` are
locale-independent, so a tr-TR box reads `LOGIN` the same as an en-US one (the .NET
culture-sensitive IgnoreCase of the first fence did not).

LEGACY PREFIXES. `live_ledger.jsonl` and `order_intents.jsonl` carried the raw login in `account`
on every row until their writers moved to a hashed `account_key`. Those old rows cannot be
rewritten: the ledger's prefix is sealed in IMMUTABLE_MANIFEST.json and every audited reader
raises on a changed prefix (libs/ops/live_ledger_view.py), and the gateway appends to both files
while the box runs. So for those two paths only, the rows BEFORE the first `account_key` row are
the frozen legacy prefix and are not judged; every row from the first `account_key` row onward is.
A writer that regresses after the cutover is refused. The entry goes when the principal scrubs
history (`git filter-repo` is theirs alone) and the prefix no longer carries a login.

A refusal is written to desks/mt5/reports/LOGIN_FENCE.json (published on the next pass) and opens
`state_login_fence_refusal` in data/alert_ledger.json; a clean pass closes it. Neither, and no
line printed here, ever carries the value: only the path, the key name and the line number.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "desks" / "mt5" / "reports" / "LOGIN_FENCE.json"
ALERTS = ROOT / "data" / "alert_ledger.json"
ALERT_ID = "state_login_fence_refusal"

#: Binary state the fence does not read as text (market frames; a regex over pickled bytes only
#: ever false-alarms). Every OTHER extension is judged, known or not -- an unknown one is read as
#: text rather than waved through (audit v3: `.yaml`, `.log`, `.xml` used to bypass the fence).
BINARY_EXEMPT = frozenset({".pkl", ".pickle", ".parquet", ".feather", ".npz", ".npy"})

#: Paths whose rows before the first `account_key` row are the sealed legacy prefix (see above).
LEGACY_PREFIX: dict[str, str] = {
    "desks/mt5/data/live_ledger.jsonl":
        "rows before the first account_key row carry the raw login; the prefix is sealed "
        "(IMMUTABLE_MANIFEST.json) and cannot be rewritten",
    "desks/mt5/data/order_intents.jsonl":
        "rows before the first account_key row carry the raw login; the gateway appends to it "
        "live and its reconcile reads it, so it is not rewritten in place",
}
CUTOVER_MARK = '"account_key"'

#: Normalised (lower-case, alphanumerics only) key names that name an account.
ACCOUNT_KEYS = frozenset({"account", "accountnumber", "accountno", "accountnum", "accountid",
                          "accountlogin", "login", "loginid", "loginno", "loginnumber"})
#: Normalised prefixes that make a `*login` key something other than the account's identity.
NOT_IDENTITY = ("requires", "require", "needs", "last", "failed", "allow", "auto", "sso",
                "first", "prev", "next")
_ACCOUNT_SHAPED = re.compile(r"\d{4,12}")
#: key, then `:` or `=`, then a bare / quoted / first-in-list value. The key may be quoted with
#: " or ' (Python repr) or bare; the value capture is only ever compared, never stored.
_PAIR = re.compile(
    r"""["']?(?P<key>[A-Za-z][A-Za-z0-9 _\-]{0,40}?)["']?\s*[:=]\s*\[?\s*"""
    r"""(?P<val>"[^"\n]{0,40}"|'[^'\n]{0,40}'|-?\d[\d.]*)""")
_UESC = re.compile(r"\\u([0-9a-fA-F]{4})")


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def is_login_key(key: str) -> bool:
    n = _norm(key)
    if n.startswith(NOT_IDENTITY):
        return False
    return n in ACCOUNT_KEYS or n.endswith(("login", "loginid"))


def _account_shaped(val: str) -> bool:
    return _ACCOUNT_SHAPED.fullmatch(val.strip().strip("\"'").strip()) is not None


def _decoded(text: str) -> str:
    """The text with `\\uXXXX` escapes and up to two levels of `\\"` escaping undone."""
    out = _UESC.sub(lambda m: chr(int(m.group(1), 16)), text)
    for _ in range(2):
        out = out.replace('\\\\"', '\\"').replace('\\"', '"')
    return out


def _pairs(text: str) -> list[tuple[str, int]]:
    """(key name, line) for each login-shaped key with an account-shaped value -- names only.

    The decoded text is scanned whole, so a value on the line after its key is still seen, and
    an escaped key is still a key; lines are counted on the decoded text."""
    hits: list[tuple[str, int]] = []
    flat = _decoded(text)
    for m in _PAIR.finditer(flat):
        if is_login_key(m.group("key")) and _account_shaped(m.group("val")):
            hits.append((m.group("key").strip(), flat.count("\n", 0, m.start()) + 1))
    return hits


def _csv_hits(text: str, sep: str) -> list[str]:
    rows = list(csv.reader(io.StringIO(text), delimiter=sep))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    cols = [i for i, c in enumerate(rows[0]) if is_login_key(c)]
    return sorted({rows[0][i].strip() for r in rows[1:] for i in cols
                   if i < len(r) and _account_shaped(r[i])})


def findings(rel: str, data: bytes) -> list[dict[str, Any]]:
    """Why `rel` must not publish, as {key, line} rows -- never the value. [] = publishable."""
    suffix = Path(rel).suffix.lower()
    if suffix in BINARY_EXEMPT:
        return []
    text = data.decode("utf-8", errors="replace").lstrip("﻿")
    if suffix in (".csv", ".tsv"):
        return [{"key": k, "line": 1} for k in _csv_hits(text, "\t" if suffix == ".tsv" else ",")]
    offset = 0
    if rel in LEGACY_PREFIX:
        lines = text.splitlines(keepends=True)
        start = next((i for i, ln in enumerate(lines) if CUTOVER_MARK in ln), len(lines))
        text, offset = "".join(lines[start:]), start
    return [{"key": k, "line": line + offset} for k, line in _pairs(text)]


def _blobs(repo: Path, ids: list[str]) -> list[bytes | None]:
    """The blobs' bytes, in one `git cat-file --batch` process; None for a missing object."""
    proc = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"],
                          input=("\n".join(ids) + "\n").encode(), capture_output=True,
                          timeout=120, check=True)
    buf, pos = proc.stdout, 0
    out: list[bytes | None] = []
    for _ in ids:
        eol = buf.index(b"\n", pos)
        head = buf[pos:eol].split()
        pos = eol + 1
        if len(head) < 3 or head[1] == b"missing":
            out.append(None)
            continue
        size = int(head[2])
        out.append(buf[pos:pos + size])
        pos += size + 1
    return out


def judge(repo: Path, entries: list[tuple[str, str]]) -> dict[str, Any]:
    """Judge (blob, rel) pairs. An unreadable blob is refused: this fence fails closed."""
    data = _blobs(repo, [b for b, _ in entries])
    refused: dict[str, list[dict[str, Any]]] = {}
    legacy: list[str] = []
    for (_blob, rel), raw in zip(entries, data, strict=True):
        if raw is None:
            refused[rel] = [{"key": "<blob unreadable>", "line": 0}]
            continue
        if rel in LEGACY_PREFIX and CUTOVER_MARK not in raw.decode("utf-8", "replace"):
            legacy.append(rel)
        got = findings(rel, raw)
        if got:
            refused[rel] = got[:20]
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "status": "REFUSED" if refused else "OK",
            "n_checked": len(entries), "n_refused": len(refused),
            "refused": refused,
            # paths whose whole content is still the sealed legacy prefix (no cutover row yet)
            "legacy_prefix_only": sorted(legacy),
            "rule": "login-shaped key with an account-shaped value; values are never recorded"}


def record_alert(doc: dict[str, Any], root: Path | None = None) -> str | None:
    """Give a refusal a lifecycle in the desk's AlertLedger (scripts/check_placement_interlock.py
    idiom): a false positive that silently stops one file publishing forever is the risk."""
    base = Path(root or ROOT)
    try:
        sys.path.insert(0, str(base))
        from libs.ops.alert_ledger import AlertLedger
        ledger = AlertLedger(base / "data" / "alert_ledger.json")
        if doc.get("status") == "OK":
            alert = ledger.alerts.get(ALERT_ID)
            if alert is not None and alert.open:
                ledger.verify(ALERT_ID, still_firing=False)
                ledger.save()
                return "FIXED"
            return None
        why = "; ".join(f"{rel}: {', '.join(sorted({h['key'] for h in hits}))}"
                        for rel, hits in sorted(doc.get("refused", {}).items()))
        ledger.observe(ALERT_ID, ("state publish refused (login-shaped key, value withheld): "
                                  + why)[:600], scope="RUNTIME")
        ledger.save()
        return "OPEN"
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    """stdin: one `<blob>\\t<rel>` per line. stdout: one refused rel per line. rc 0 = judged."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=ROOT)
    ap.add_argument("--artifact", type=Path, default=None)
    args = ap.parse_args(argv)
    entries: list[tuple[str, str]] = []
    for ln in sys.stdin.read().splitlines():
        blob, sep, rel = ln.partition("\t")
        if sep:
            entries.append((blob.strip(), rel.strip().replace("\\", "/")))
    doc = judge(args.repo, entries)
    doc["alert"] = record_alert(doc, args.repo)
    out = args.artifact or (args.repo / "desks" / "mt5" / "reports" / "LOGIN_FENCE.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp.replace(out)
    for rel in sorted(doc["refused"]):
        print(rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
