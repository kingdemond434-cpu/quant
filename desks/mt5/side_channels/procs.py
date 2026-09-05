import psutil, time
now = time.time()
for p in psutil.process_iter(["name", "cmdline", "create_time"]):
    try:
        cmd = " ".join(p.info["cmdline"] or [])
        if p.info["name"] and p.info["name"].lower().startswith("python"):
            age = (now - p.info["create_time"]) / 60
            tag = "SIGNAL" if "signal_gate" in cmd else ""
            print(f"pid={p.pid} age={age:.1f}min {tag} {cmd[:70]}")
    except Exception:
        pass