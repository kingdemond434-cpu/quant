#!/usr/bin/env python3
"""Per-seat PAYLOAD CAPACITY TEST (principal 2026-07-20).

A seat that silently blanks on the audit payload is a dead seat -- it inflates "13/13
responded" while contributing nothing. Advertised context windows are NOT reliable (minimax-m3
claims 1M and blanked at 260k chars), so capacity is measured, not trusted.

Method: send each seat the REAL audit payload and demand a one-line answer that can only be
produced by actually ingesting it (the name of the last file in the payload). Output is tiny,
so this costs input tokens only. Result per seat: PASS (ingested + answered), BLANK (silent
failure -- the dangerous case), or ERROR.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, "/home/quant/quant-platform")
import os

os.chdir("/home/quant/quant-platform")

from scripts.build_audit_coverage import audit_payload  # noqa: E402 -- after chdir/sys.path
from scripts.run_external_panel import _ask  # noqa: E402 -- after chdir/sys.path

from libs.llm.push import build_turns  # noqa: E402

payload, files = audit_payload()
last_file = files[-1] if files else "?"
probe = (payload + "\n\n### CAPACITY PROBE\nReply with ONE line only: the path of the LAST "
         "file shown above. No explanation, no preamble.")

providers = json.loads(Path("data/secrets/llm_panel.json").read_text())["providers"]
print(f"payload: {len(probe):,} chars (~{len(probe)//4:,} tokens) | {len(files)} files")
print(f"expected answer contains: {last_file}\n")


def test(pv: dict[str, Any]) -> tuple[str, str, int, str]:
    m = pv["model"]
    try:
        # Same orphaning as deep_review.py: 0debac3 moved `_ask`'s 4th parameter from `system` to
        # a `messages` list and this caller kept passing (system, user). Every seat raised
        # TypeError and the `except Exception` below rendered it as a per-model "ERROR" row --
        # a capacity probe that reports every model dead looks exactly like an outage.
        r = _ask(pv["base_url"], pv["key"], m,
                 build_turns("You are a precise assistant.", probe))
        body = r.strip()
        if len(body) < 3:
            return (m, "BLANK", len(body), repr(r[:40]))
        ok = last_file.split("/")[-1] in body or last_file in body
        return (m, "PASS" if ok else "RESPONDED-WRONG", len(body), body[:70].replace("\n", " "))
    except Exception as e:
        return (m, "ERROR", 0, repr(e)[:90])


with ThreadPoolExecutor(max_workers=6) as ex:
    rows = list(ex.map(test, providers))

print(f"{'MODEL':<42} {'RESULT':<16} {'LEN':>6}  DETAIL")
print("-" * 110)
bad = []
for m, res, ln, det in sorted(rows, key=lambda x: (x[1] != "PASS", x[0])):
    print(f"{m:<42} {res:<16} {ln:>6}  {det}")
    if res in ("BLANK", "ERROR"):
        bad.append((m, res))
print("-" * 110)
print(f"PASS: {sum(1 for r in rows if r[1] == 'PASS')}/{len(rows)}   "
      f"BLANK/ERROR (swap candidates): {[b[0] for b in bad] or 'none'}")
