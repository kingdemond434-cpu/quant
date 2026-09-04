import os
import subprocess, textwrap

code = textwrap.dedent("""\
import pandas as pd, glob, os
for f in sorted(glob.glob('/home/quant/quant-platform/desks/mt5/data/universe/*_H1.parquet'))[:5]:
    df = pd.read_parquet(f)
    print(os.path.basename(f), list(df.columns))
""")

proc = subprocess.run(
    ["ssh", os.environ.get("QUANT_VPS", "quant@VPS_HOST_REDACTED"),
     "cat > /tmp/check_cols.py << 'PYEOF'\n" + code + "\nPYEOF"],
    capture_output=True, text=True, timeout=10
)
proc2 = subprocess.run(
    ["ssh", os.environ.get("QUANT_VPS", "quant@VPS_HOST_REDACTED"),
     "/home/quant/quant-platform/.venv/bin/python /tmp/check_cols.py 2>&1"],
    capture_output=True, text=True, timeout=30
)
print(proc2.stdout)
if proc2.stderr:
    print("ERR:", proc2.stderr[:500])
