#!/usr/bin/env bash
# Databento API key placement (principal step). Key NEVER goes in chat or shell history.
# Run:  bash ops/setup_databento_key.sh
# Paste the key at the prompt, press Enter. Nothing else.
set -euo pipefail
cd /home/quant/quant-platform
umask 077

printf '\nPaste your Databento API key (starts with db-) and press Enter:\n> ' >&2
IFS= read -r RAW
KEY="$(printf '%s' "$RAW" | tr -d '[:space:]')"

[ -n "$KEY" ] || { echo "ERROR: empty input." >&2; exit 1; }
case "$KEY" in
    db-*) ;;
    *) echo "ERROR: Databento keys start with 'db-'. You pasted something else -- rerun and paste ONLY the key." >&2; exit 1;;
esac

mkdir -p data/secrets
printf '{"api_key": "%s"}' "$KEY" > data/secrets/databento.json
chmod 600 data/secrets/databento.json
echo "key written (600): data/secrets/databento.json (${#KEY} chars)" >&2

echo "verifying against the Databento API..." >&2
.venv/bin/python - "$KEY" <<'PY'
import base64, json, sys, urllib.request, ssl, certifi
key = sys.argv[1]
ctx = ssl.create_default_context(cafile=certifi.where())
auth = base64.b64encode(f"{key}:".encode()).decode()
try:
    r = urllib.request.Request(
        "https://hist.databento.com/v0/metadata.list_datasets",
        headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(r, timeout=25, context=ctx) as resp:
        ds = json.loads(resp.read())
    print("AUTH-OK. datasets visible:", len(ds), file=sys.stderr)
    print("GLBX.MDP3 (CME) available:", "GLBX.MDP3" in ds, file=sys.stderr)
except Exception as e:
    print(f"VERIFY FAILED: {e!r}", file=sys.stderr)
    sys.exit(1)
PY
echo "=== DATABENTO KEY VERIFIED -- surgical CME pulls can now be planned ===" >&2
echo "NOTE: \$125 credits are ONE-TIME. No bulk pulls; specific high-value windows only." >&2
