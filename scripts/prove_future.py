"""PROVE future enforcement, do not assert it. Plant violations, confirm the guards fail, remove.

The principal has asked repeatedly whether this is really enforced. Every previous answer was a
CLAIM about current state. This is an adversarial test of FUTURE state: it creates exactly the
things that would appear tomorrow -- a new LLM caller that forgets doctrine, a new prompt file
without the mandate, and a principle silently dropped from the preamble -- and verifies each guard
catches it.

A guard that has never been shown to fail has never been shown to work.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".")
PY = ".venv/bin/python"
results = []


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    return r.returncode


# ---------------------------------------------------------------- baseline
d0 = run(f"{PY} scripts/doctrine.py")
p0 = run(f"{PY} scripts/principle_audit.py")
results.append(("BASELINE doctrine guard", d0 == 0, f"exit {d0} (expect 0)"))
results.append(("BASELINE principle guard", p0 == 0, f"exit {p0} (expect 0)"))

# ---------------------------------------------------------------- test 1: future LLM caller
fake = ROOT / "scripts/_tmp_future_caller.py"
fake.write_text(
    'import json, urllib.request\n'
    'def ask(k, system, user):\n'
    '    body = json.dumps({"model": "x", "messages": ['
    '{"role": "system", "content": system}]}).encode()\n'
    '    return urllib.request.urlopen("https://openrouter.ai/api/v1/chat/completions")\n',
    "utf-8")
d1 = run(f"{PY} scripts/doctrine.py")
results.append(("FUTURE LLM caller without doctrine is CAUGHT", d1 != 0,
                f"exit {d1} (expect non-zero)"))
fake.unlink()

# ---------------------------------------------------------------- test 2: future prompt file
fp = ROOT / "prompts/panel_missions/_tmp_future_mission.txt"
fp.write_text("ROLE: analyse the desk and report findings.\n", "utf-8")
d2 = run(f"{PY} scripts/doctrine.py")
results.append(("FUTURE prompt file without mandate is CAUGHT", d2 != 0,
                f"exit {d2} (expect non-zero)"))
fp.unlink()

# ---------------------------------------------------------------- test 3: dropped principle
doc = ROOT / "scripts/doctrine.py"
orig = doc.read_text("utf-8")
# Remove the SECTION BODY, not just its header -- v1 removed only the title and the audit
# still matched on body text, so the "dropped principle" proof passed vacuously.
i = orig.index("BOTTLENECK FIRST")
j = orig.index("OPPORTUNITY COST")
tampered = orig[:i] + orig[j:]
doc.write_text(tampered, "utf-8")
p3 = run(f"{PY} scripts/principle_audit.py")
results.append(("PRINCIPLE silently dropped is CAUGHT", p3 != 0, f"exit {p3} (expect non-zero)"))
doc.write_text(orig, "utf-8")

# ---------------------------------------------------------------- restore check
d4 = run(f"{PY} scripts/doctrine.py")
p4 = run(f"{PY} scripts/principle_audit.py")
results.append(("RESTORED doctrine guard", d4 == 0, f"exit {d4} (expect 0)"))
results.append(("RESTORED principle guard", p4 == 0, f"exit {p4} (expect 0)"))

print("=== ADVERSARIAL PROOF OF FUTURE ENFORCEMENT ===")
print("    guards are not asserted -- violations are planted and the guards must FAIL on them\n")
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<50} {detail}")
bad = [r for r in results if not r[1]]
print(f"\n  {len(results)-len(bad)}/{len(results)} proofs passed")
if bad:
    print("  A guard that does not fail on a planted violation does not work.")
else:
    print("  Every guard fails on a planted violation and passes when restored. Enforcement is")
    print("  demonstrated for callers, prompts and principles that DO NOT EXIST YET.")
sys.exit(1 if bad else 0)
