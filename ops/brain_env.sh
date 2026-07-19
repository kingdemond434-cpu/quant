# Shared brain auth environment -- sourced by EVERY claude-invoking script
# (run_cro_ai.sh + all digger scripts). Decision 2026-07-19 (Option A): the brain
# runs on METERED API billing (Console key, monthly spend cap, no weekly limit)
# so interactive subscription use can never starve it again (07-18 lost-day class).
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
