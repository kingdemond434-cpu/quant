t = open(r"desks\mt5\research\shadow_forward.py", encoding="utf-8", errors="replace").read()
for pat in ("stale IDENTITY_BROKEN cleared", "IDENTITY_BROKEN cleared from state"):
    print(f"  '{pat}': {t.count(pat)}")
