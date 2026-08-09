#!/bin/bash
set -Eeuo pipefail

# Pterodactyl installer passthrough.
case "${1:-}" in
    bash|/bin/bash|sh|/bin/sh)
        exec "$@"
        ;;
esac

echo "[PTERO-ARM64] Wings-native Palworld bootstrap"
echo "[PTERO-ARM64] UID:GID=$(id -u):$(id -g) ARCH=$(uname -m)"

case "$(uname -m)" in
    aarch64|arm64) ;;
    *)
        echo "[FATAL] This image requires ARM64/aarch64."
        exit 20
        ;;
esac

# All mutable state must stay in the Wings writable server volume.
mkdir -p \
    /home/container/backups \
    /home/container/logs/palworld \
    /home/container/.steamcmd \
    /home/container/Steam \
    /home/container/.steam/sdk64 \
    /home/container/tmp \
    /home/container/.cache \
    /home/container/.config \
    /home/container/.local/share \
    /home/container/.fex-emu \
    /home/container/Pal/Saved/Config/LinuxServer

# Seed writable SteamCMD once.
if [[ ! -x /home/container/.steamcmd/steamcmd.sh ]]; then
    echo "[PTERO-ARM64] Seeding writable SteamCMD..."
    cp -a /opt/steamcmd-seed/. /home/container/.steamcmd/
    chmod 0755 /home/container/.steamcmd/steamcmd.sh
fi

# Locate the x86_64 RootFS embedded in Supersunho's ARM64 image.
ROOTFS_DIR="$(find /opt/fex-rootfs -mindepth 1 -maxdepth 1 -type d -print -quit 2>/dev/null || true)"

if [[ -z "${ROOTFS_DIR}" || ! -d "${ROOTFS_DIR}" ]]; then
    echo "[FATAL] No preinstalled FEX RootFS found under /opt/fex-rootfs."
    find /opt/fex-rootfs -maxdepth 2 -print 2>/dev/null || true
    exit 21
fi

# Pterodactyl reserves HOME as an EggVariable, so set it inside the image.
export HOME=/home/container
export XDG_CACHE_HOME=/home/container/.cache
export XDG_CONFIG_HOME=/home/container/.config
export XDG_DATA_HOME=/home/container/.local/share
export TMPDIR=/home/container/tmp

# Supersunho manager writable paths.
export SERVER_DIR=/home/container
export BACKUP_DIR=/home/container/backups
export LOG_DIR=/home/container/logs
export STEAMCMD_DIR=/home/container/.steamcmd

# ------------------------------------------------------------------
# IMPORTANT FEX FIX
# ------------------------------------------------------------------
# FEX runtime consumes FEX_ROOTFS. FEX_ROOTFS_PATH is not the runtime
# RootFS selector used by FEXBash/FEX.
export FEX_ROOTFS="${ROOTFS_DIR}"

# Point FEX's user config/data locations to writable Pterodactyl storage too.
export FEX_APP_CONFIG_LOCATION=/home/container/.fex-emu/
export FEX_APP_DATA_LOCATION=/home/container/.fex-emu/
export FEX_APP_CACHE_LOCATION=/home/container/.cache/fex-emu/

mkdir -p "${FEX_APP_CACHE_LOCATION}"

# Keep a valid main config as a fallback. FEX_ROOTFS above is authoritative.
printf '{"Config":{"RootFS":"%s"}}\n' "${ROOTFS_DIR}" \
    > /home/container/.fex-emu/Config.json

# ARM64 runtime tuning retained from the upstream image.
export FEX_ENABLE_JIT_CACHE=1
export FEX_JIT_CACHE_SIZE=1024
export FEX_ENABLE_VIXL_SIMULATOR=0
export FEX_ENABLE_VIXL_DISASSEMBLER=0
export FEX_ENABLE_LAZY_MEMORY_DELETION=1
export FEX_ENABLE_STATIC_REGISTER_ALLOCATION=1

echo "[PTERO-ARM64] SERVER_DIR=${SERVER_DIR}"
echo "[PTERO-ARM64] STEAMCMD_DIR=${STEAMCMD_DIR}"
echo "[PTERO-ARM64] FEX_ROOTFS=${FEX_ROOTFS}"
echo "[PTERO-ARM64] FEX_APP_CONFIG_LOCATION=${FEX_APP_CONFIG_LOCATION}"

# ------------------------------------------------------------
# Pterodactyl primary allocation -> Palworld game port
# ------------------------------------------------------------
# SERVER_PORT is injected automatically by Pterodactyl/Wings and is reserved,
# so it must NOT be declared as an EggVariable.
GAME_PORT="${SERVER_PORT:-8211}"

if ! [[ "${GAME_PORT}" =~ ^[0-9]+$ ]] || (( GAME_PORT < 1 || GAME_PORT > 65535 )); then
    echo "[FATAL] Invalid Pterodactyl primary allocation SERVER_PORT='${GAME_PORT}'."
    exit 25
fi

# PublicPort is metadata for community/public lobby. Keep it in sync with the
# actual primary allocation so there is never a second manually-maintained port.
export PUBLIC_PORT="${GAME_PORT}"

# Supersunho's ProcessManager currently adds query/startup options but does not
# add -port=. Additional options are appended LAST, so force the actual Palworld
# listen port through that mechanism while preserving user custom options.
USER_ADDITIONAL_OPTIONS="${ADDITIONAL_SERVER_OPTIONS:-}"
export ADDITIONAL_SERVER_OPTIONS="${USER_ADDITIONAL_OPTIONS} -port=${GAME_PORT}"

echo "[PTERO-ARM64] Primary game allocation: ${SERVER_IP:-0.0.0.0}:${GAME_PORT}/UDP"
echo "[PTERO-ARM64] Palworld listen argument: -port=${GAME_PORT}"
echo "[PTERO-ARM64] PublicPort synchronized: ${PUBLIC_PORT}"
echo "[PTERO-ARM64] Query port: ${QUERY_PORT:-27018}/UDP (extra allocation recommended for browser/query)"

[[ -x /home/container/.steamcmd/steamcmd.sh ]] || {
    echo "[FATAL] Writable SteamCMD bootstrap is missing."
    exit 22
}

[[ -d /app/src ]] || {
    echo "[FATAL] Supersunho manager source /app/src is missing."
    exit 23
}

command -v FEXBash >/dev/null 2>&1 || {
    echo "[FATAL] FEXBash is missing from the runtime image."
    exit 24
}

# Fail here with a focused FEX error instead of waiting for Palworld manager.
echo "[PTERO-ARM64] Testing FEX RootFS..."
if FEXBash -c 'printf "FEX guest bootstrap OK\n"' ; then
    echo "[PTERO-ARM64] FEX preflight: OK"
else
    rc=$?
    echo "[FATAL] FEX preflight failed with exit code ${rc}."
    echo "[FATAL] FEX_ROOTFS=${FEX_ROOTFS}"
    exit "${rc}"
fi

case "${1:---start-server}" in
    --start-server|"")
        echo "[PTERO-ARM64] Starting Supersunho manager..."
        cd /app
        exec python -m src.server_manager
        ;;
    --health-check)
        exec python /usr/local/bin/healthcheck
        ;;
    --shell)
        exec /bin/bash
        ;;
    *)
        echo "[PTERO-ARM64] Unknown mode '$1'; starting server manager."
        cd /app
        exec python -m src.server_manager
        ;;
esac
