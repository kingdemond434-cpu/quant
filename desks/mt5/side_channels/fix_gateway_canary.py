# Read the current file
with open('/home/quant/quant-platform/desks/mt5/mt5desk/gateway.py', 'r') as f:
    content = f.read()

# Fix 1: Update load_sleeves to add canary_state based on live trade count
old_load = '''def load_sleeves() -> list[dict]:
    """Promoted sleeves from data/sleeves.json (writer: research/promoter.py)."""
    if not SLEEVES_FILE.exists():
        return []
    try:
        data = json.loads(SLEEVES_FILE.read_text(encoding="utf-8"))
        return [s for s in data.get("sleeves", []) if s.get("status") == "LIVE"]
    except Exception:
        return []'''

new_load = '''def load_sleeves() -> list[dict]:
    """Promoted sleeves from data/sleeves.json (writer: research/promoter.py).

    Adds explicit CANARY state based on live trade count:
      SHADOW           -> not yet promoted (not in this list)
      FORWARD_READY    -> promoted, 0 live trades (awaiting first fill)
      CANARY_25        -> 1-49 live trades (0.25x authority)
      CANARY_50        -> 50-199 live trades (0.50x authority)
      LIVE_FULL        -> 200+ live trades (1.00x authority)
      HIBERNATED       -> promoted but dormant (below equity floor)
      RETIRED          -> retired by promoter (removed from this list)
    """
    if not SLEEVES_FILE.exists():
        return []
    try:
        data = json.loads(SLEEVES_FILE.read_text(encoding="utf-8"))
        live_sleeves = [s for s in data.get("sleeves", []) if s.get("status") == "LIVE"]
        # Add canary state to each sleeve
        for s in live_sleeves:
            n = sleeve_live_n(s["name"])
            if n == 0:
                s["canary_state"] = "FORWARD_READY"
            elif n < 50:
                s["canary_state"] = "CANARY_25"
            elif n < 200:
                s["canary_state"] = "CANARY_50"
            else:
                s["canary_state"] = "LIVE_FULL"
        return live_sleeves
    except Exception:
        return []'''

content = content.replace(old_load, new_load)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/mt5desk/gateway.py', 'w') as f:
    f.write(content)

print("gateway.py canary states added successfully")