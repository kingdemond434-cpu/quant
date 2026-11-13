import subprocess, os
os.chdir(r"C:\Users\dell\mt5-research\scripts")

for cmd in [
    ["git", "add", "families_patch.py", "convert_to_hypotheses_v4.py", "full_pipeline_v2.py"],
    ["git", "commit", "-m", "zero-hardcode families registry + 197-symbol universe (Windows)"],
    ["git", "push", "origin", "desk-sync-clean"],
]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(r.stdout)
    if r.stderr:
        print("ERR:", r.stderr[:300])