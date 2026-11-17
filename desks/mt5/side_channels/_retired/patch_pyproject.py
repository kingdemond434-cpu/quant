import io

p = "pyproject.toml"
s = io.open(p, encoding="utf-8").read()
old = 'exclude = ["scratch"]'
assert old in s, "pattern not found"
note = (
    'exclude = ["scratch", "desks/mt5"]\n'
    "# `desks/mt5` is the mirror copy of the MT5 research desk (executes on the local Windows host;\n"
    "# this copy is for visibility/coordination only). External code with its own host conventions\n"
    "# (MetaTrader5 import, Windows paths, legacy style) -- same treatment as scratch: the gate should\n"
    "# measure the platform codebase, not a mirrored desk. It is never executed here; see\n"
    "# desks/mt5/docs/MT5_DESK.md."
)
s = s.replace(old, note)
io.open(p, "w", encoding="utf-8").write(s)
print("patched")