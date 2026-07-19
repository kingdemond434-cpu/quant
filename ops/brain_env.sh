# Shared brain auth environment -- sourced by EVERY claude-invoking script
# (run_cro_ai.sh + all digger scripts). Option A (metered API key) was SUPERSEDED by
# Option B (Max subscription) same day -- see ledger #102. This hook stays as the
# DORMANT fallback: inert without the keyfile (OAuth login is then used), and the
#
# Key lives in data/secrets/anthropic_api_key (chmod 600, gitignored) -- read here
# at spawn time, NEVER in a systemd Environment= line (visible via /proc/<pid>/environ,
# same rule as the live-connector keyfile). If the keyfile is absent, we fall back to
# whatever OAuth login exists in ~/.claude so nothing breaks before key placement.
export PATH="$HOME/.local/bin:$PATH"
_BRAIN_KEYFILE="/home/quant/quant-platform/data/secrets/anthropic_api_key"
if [ -f "$_BRAIN_KEYFILE" ]; then
    ANTHROPIC_API_KEY="$(cat "$_BRAIN_KEYFILE")"
    export ANTHROPIC_API_KEY
fi
