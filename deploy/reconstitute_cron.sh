#!/bin/sh
# deploy/reconstitute_cron.sh -- gap #58's actual DR fix (2026-07-29).
#
# Before this file existed, a restore-from-GitHub yielded a desk that ran NOTHING: the live
# VPS crontab was uncommitted and only 5 of the systemd units were in the repo
# (docs/GAP_REGISTER.md:272). Now: clone the repo, run this script, and the scheduler floor
# from ops/crontab.manifest is live again -- watchdog tick, recorders, collectors, daily
# cycle, digs. The manifest is RECONSTRUCTED evidence (see its header): a DR floor, not a
# verified twin of the box; the operator still owes the `crontab -l` paste (row #58,
# deadline 2026-08-05).
#
# POSIX sh, idempotent by construction:
#   * cron entries are installed inside a marker-fenced block -- re-running REPLACES the
#     block, never appends (the append failure mode is how boxes end up running a job twice);
#   * everything outside the fence in the user's crontab is preserved byte-for-byte;
#   * the committed quant-* timer units are enabled on the system plane when writable; without
#     root, the collision-free midnight controller alone is installed as a durable user timer
#     while the other units remain system-owned and their exact sudo recovery commands are shown.
#
# REFUSES to run when scripts/check_scheduler_manifest.py finds manifest-referenced scripts
# missing from the repo: installing a crontab of dead entries would fake a healthy DR drill
# while every tick fails silently (the DEAD CRON class, scripts/wiring_audit.py:8).
#
#     sh deploy/reconstitute_cron.sh
set -eu

SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SELF_DIR/.." && pwd)
# ROLE SELECTION (R0107, 2026-07-31): ops/role is per-box, gitignored state. Absent or
# "primary" -> the full manifest (unchanged behaviour). "research" -> the twin's subset, so a
# second VPS becomes a research twin with one line: echo research > ops/role
_ROLE=$(cat "$ROOT/ops/role" 2>/dev/null || echo primary)
if [ "$_ROLE" = "research" ]; then
    MANIFEST="$ROOT/ops/crontab.research.manifest"
else
    MANIFEST="$ROOT/ops/crontab.manifest"
fi
CHECKER="$ROOT/scripts/check_scheduler_manifest.py"
MARK_BEGIN="# >>> quant-desk ops/crontab.manifest >>> (managed block -- edit the manifest, not this)"
MARK_END="# <<< quant-desk ops/crontab.manifest <<<"

[ -f "$MANIFEST" ] || { echo "reconstitute: $MANIFEST missing -- nothing to install" >&2; exit 2; }

# venv python first (the desk convention), system python3 as the restore-day fallback.
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=$(command -v python3) || { echo "reconstitute: no python3" >&2; exit 2; }

# IMPORTABILITY GATE (added 2026-07-30). 124 of the 145 scripts that import `libs` have no
# sys.path guard -- they work in production only because the venv has quant-platform installed
# (pyproject: packages = ["libs", "app"]). On a RESTORE DAY that install is exactly what is
# missing, so reconstitution would happily write a full crontab of entries that all die on
# ModuleNotFoundError, and the desk would look scheduled while running nothing. That is a worse
# failure than refusing: a silent one.
#
# Measured here rather than assumed, and REPAIRED once before giving up -- a restore that stops
# to ask a human for `pip install -e .` has not restored anything.
if ! (cd "$ROOT" && "$PY" -c "import libs" >/dev/null 2>&1); then
    echo "reconstitute: 'import libs' fails -- installing the package into $PY"
    (cd "$ROOT" && "$PY" -m pip install -e . --quiet) || true
fi
if ! (cd "$ROOT" && "$PY" -c "import libs" >/dev/null 2>&1); then
    echo "reconstitute: REFUSING -- 'import libs' still fails after 'pip install -e .'." >&2
    echo "Most scheduled scripts would die on ModuleNotFoundError, leaving a crontab that" >&2
    echo "looks healthy and runs nothing. Fix the environment, then re-run." >&2
    exit 2
fi

# GATE: --report-only tolerates live-crontab drift (we are about to fix that) but still
# exits 2 on missing scripts / rotted committed timers -- exactly the refusal we want.
if ! "$PY" "$CHECKER" --report-only; then
    echo "reconstitute: REFUSING -- scripts/check_scheduler_manifest.py failed its repo" >&2
    echo "checks (manifest references missing scripts, or committed timers rotted)." >&2
    echo "Fix the manifest/repo first; installing dead cron entries fakes a healthy DR." >&2
    exit 2
fi

TMP=$(mktemp) || exit 2
trap 'rm -f "$TMP"' EXIT INT TERM

# current crontab minus any previous fenced block (first run: empty is fine).
crontab -l 2>/dev/null | awk -v b="$MARK_BEGIN" -v e="$MARK_END" '
    index($0, b) == 1 { skip = 1; next }
    index($0, e) == 1 { skip = 0; next }
    skip != 1 { print }
' > "$TMP" || true

# fresh fenced block: QUANT_ROOT pinned to THIS checkout (the manifest's default is the VPS
# path), then every active cron line from the manifest. SYSTEMD lines belong to the other
# plane and comment/env lines carry evidence, not schedule -- all filtered here.
{
    echo "$MARK_BEGIN"
    echo "# installed $(date -u +%Y-%m-%dT%H:%MZ) by deploy/reconstitute_cron.sh (gap #58)"
    echo "QUANT_ROOT=$ROOT"
    grep -v '^[[:space:]]*#' "$MANIFEST" | grep -v '^[[:space:]]*$' \
        | grep -v '^SYSTEMD' | grep -v '^QUANT_ROOT='
    echo "$MARK_END"
} >> "$TMP"

N_LINES=$(grep -v '^[[:space:]]*#' "$MANIFEST" | grep -v '^[[:space:]]*$' \
    | grep -v '^SYSTEMD' | grep -cv '^QUANT_ROOT=' || true)

if crontab "$TMP"; then
    echo "reconstitute: installed $N_LINES cron entries (fenced block, re-run replaces)"
else
    echo "reconstitute: crontab install FAILED -- cron plane not restored" >&2
    exit 2
fi

# systemd plane: committed dig units plus the collision-free midnight frontier. Copy+enable
# all units when we can. Without system write access, install ONLY the midnight frontier in the
# invoking user's systemd manager. The other timers stay on the system plane, so this fallback
# cannot create a second copy of every miner. Never die here: the cron plane above already
# restored the money-path watchdog backstop, which respawns the critical services.
UNITS="quant-blindrediscovery quant-dataaxis quant-frontier quant-litminer quant-prospector quant-midnight-frontier"
if command -v systemctl >/dev/null 2>&1; then
    COPIED=0
    if [ -d /etc/systemd/system ] && [ -w /etc/systemd/system ]; then
        for u in $UNITS; do
            cp -f "$ROOT/ops/$u.timer" "$ROOT/ops/$u.service" /etc/systemd/system/ \
                && COPIED=$((COPIED + 1)) \
                || echo "reconstitute: copy of $u unit files failed" >&2
        done
        # Migrate only the former midnight timer. quant-research.service belongs to the
        # autonomous supervisor and is intentionally never removed or disabled here.
        if [ -e /etc/systemd/system/quant-research.timer ] || \
                [ -L /etc/systemd/system/quant-research.timer ]; then
            systemctl disable --now quant-research.timer >/dev/null 2>&1 || true
            rm -f /etc/systemd/system/quant-research.timer
            echo "reconstitute: retired legacy quant-research.timer; preserved supervisor service"
        fi
        systemctl daemon-reload || echo "reconstitute: daemon-reload failed" >&2
        echo "reconstitute: copied $COPIED/6 unit pairs into /etc/systemd/system"
        echo "reconstitute: NOTE committed units hardcode /home/quant/quant-platform paths;"
        echo "reconstitute: if this checkout lives elsewhere, edit the copies before relying on them"
        for u in $UNITS; do
            if systemctl enable --now "$u.timer" >/dev/null 2>&1; then
                echo "reconstitute: enabled $u.timer"
            else
                echo "reconstitute: could not enable $u.timer -- owed:"
                echo "  sudo systemctl enable --now $u.timer"
            fi
        done
    else
        echo "reconstitute: /etc/systemd/system not writable -- run as root to install units, or:"
        for u in $UNITS; do
            echo "  sudo cp $ROOT/ops/$u.timer $ROOT/ops/$u.service /etc/systemd/system/"
        done
        echo "  sudo systemctl disable --now quant-research.timer  # legacy midnight timer only"
        echo "  sudo rm -f /etc/systemd/system/quant-research.timer"
        echo "  sudo systemctl daemon-reload"

        # Do not create two midnight launchers if a root-owned current or legacy timer is
        # already live. A disabled unit file is harmless; an enabled/active timer is not.
        SYSTEM_MIDNIGHT_LIVE=0
        for u in quant-midnight-frontier quant-research; do
            if systemctl is-enabled "$u.timer" >/dev/null 2>&1 || \
                    systemctl is-active "$u.timer" >/dev/null 2>&1; then
                SYSTEM_MIDNIGHT_LIVE=1
                echo "reconstitute: $u.timer is already live on the system plane; user timer skipped"
            fi
        done

        if [ "$SYSTEM_MIDNIGHT_LIVE" -eq 0 ]; then
            USER_HOME=${HOME:-}
            if [ -z "$USER_HOME" ] && command -v getent >/dev/null 2>&1; then
                USER_HOME=$(getent passwd "$(id -u)" | awk -F: '{print $6}')
            fi
            if [ -z "$USER_HOME" ]; then
                echo "reconstitute: cannot determine user home -- midnight user timer not installed" >&2
            else
                USER_CONFIG_HOME=${XDG_CONFIG_HOME:-"$USER_HOME/.config"}
                USER_SYSTEMD_DIR="$USER_CONFIG_HOME/systemd/user"
                mkdir -p "$USER_SYSTEMD_DIR"
                USER_SERVICE_TMP="$USER_SYSTEMD_DIR/.quant-midnight-frontier.service.tmp.$$"
                USER_TIMER_TMP="$USER_SYSTEMD_DIR/.quant-midnight-frontier.timer.tmp.$$"

                # Derive the user service from the authoritative committed service. Only the
                # identity/path fields differ; timer semantics remain byte-for-byte identical.
                if awk -v root="$ROOT" -v home="$USER_HOME" '
                    /^User=/ { next }
                    /^Environment="PATH=/ {
                        print "Environment=\"PATH=" root "/.venv/bin:" home "/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\""
                        next
                    }
                    /^WorkingDirectory=/ { print "WorkingDirectory=" root; next }
                    /^ExecStart=/ { print "ExecStart=/bin/bash " root "/ops/run_midnight_frontier.sh"; next }
                    { print }
                ' "$ROOT/ops/quant-midnight-frontier.service" > "$USER_SERVICE_TMP" && \
                        cp "$ROOT/ops/quant-midnight-frontier.timer" "$USER_TIMER_TMP" && \
                        chmod 0644 "$USER_SERVICE_TMP" "$USER_TIMER_TMP" && \
                        mv -f "$USER_SERVICE_TMP" \
                            "$USER_SYSTEMD_DIR/quant-midnight-frontier.service" && \
                        mv -f "$USER_TIMER_TMP" \
                            "$USER_SYSTEMD_DIR/quant-midnight-frontier.timer"; then
                    echo "reconstitute: installed midnight unit pair in $USER_SYSTEMD_DIR"

                    # Linger makes the user manager survive logout/reboot. It is normally
                    # permitted for the current account; if host policy denies it, expose the gap.
                    if command -v loginctl >/dev/null 2>&1; then
                        loginctl --no-ask-password enable-linger "$(id -un)" >/dev/null 2>&1 || true
                        if [ "$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null || true)" != "yes" ]; then
                            echo "reconstitute: WARNING user linger is not enabled; timer may wait for login" >&2
                            echo "  sudo loginctl enable-linger $(id -un)" >&2
                        fi
                    fi

                    # Cron/SSH environments sometimes omit this even while the user manager exists.
                    if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -d "/run/user/$(id -u)" ]; then
                        XDG_RUNTIME_DIR="/run/user/$(id -u)"
                        export XDG_RUNTIME_DIR
                    fi
                    if systemctl --user daemon-reload && \
                            systemctl --user enable --now quant-midnight-frontier.timer && \
                            systemctl --user is-enabled --quiet quant-midnight-frontier.timer && \
                            systemctl --user is-active --quiet quant-midnight-frontier.timer; then
                        echo "reconstitute: installed, enabled and active user quant-midnight-frontier.timer"
                    else
                        echo "reconstitute: user unit files installed but user manager activation failed" >&2
                        echo "  systemctl --user daemon-reload" >&2
                        echo "  systemctl --user enable --now quant-midnight-frontier.timer" >&2
                    fi
                else
                    rm -f "$USER_SERVICE_TMP" "$USER_TIMER_TMP"
                    echo "reconstitute: midnight user unit installation failed" >&2
                fi
            fi
        fi

        # These remain one-copy system services. Never mirror them into the user manager.
        for u in quant-blindrediscovery quant-dataaxis quant-frontier quant-litminer quant-prospector; do
            echo "reconstitute: $u.timer remains system-owned -- owed:"
            echo "  sudo systemctl enable --now $u.timer"
        done
    fi
else
    echo "reconstitute: no systemctl on this box -- systemd plane skipped (cron plane is live)"
fi
echo "reconstitute: done. Verify with: $PY $CHECKER  (drift should now be zero)"
