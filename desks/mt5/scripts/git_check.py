import subprocess, os
os.chdir(r"C:\Users\dell\mt5-research\scripts")
r = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=15)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:300])