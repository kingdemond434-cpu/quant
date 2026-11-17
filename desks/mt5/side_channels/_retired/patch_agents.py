import io

p = "AGENTS.md"
s = io.open(p, encoding="utf-8").read()
needle = "docs/MASTER_QUANT_CONSTITUTION.md"
assert needle in s, "needle not found"
if "docs/MANDATE_NET_COMPOUNDING.md" not in s:
    add = (
        "- `docs/MANDATE_NET_COMPOUNDING.md` — BINDING human mandate: maximize robust net geometric "
        "growth; high drawdown is acceptable if survivable, ruin is not; never under-size out of "
        "drawdown discomfort; applies to ALL desks\n"
    )
    s = s.replace("- `" + needle + "`", add + "- `" + needle + "`", 1)
    io.open(p, "w", encoding="utf-8").write(s)
    print("patched")
else:
    print("already present")