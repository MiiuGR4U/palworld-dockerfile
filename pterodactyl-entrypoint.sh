#!/bin/bash
set -Eeuo pipefail

# ------------------------------------------------------------
# Installer passthrough
# ------------------------------------------------------------
# Wings creates installer containers with:
#   Cmd = [egg_entrypoint, "/mnt/install/install.sh"]
# while keeping the image ENTRYPOINT. Therefore our wrapper receives:
#   bash /mnt/install/install.sh
# and must pass that through unchanged.
case "${1:-}" in
    bash|/bin/bash|sh|/bin/sh)
        exec "$@"
        ;;
esac

echo "[PTERO-ARM64/v2] Wings-native Palworld bootstrap"
echo "[PTERO-ARM64/v2] UID:GID=$(id -u):$(id -g) ARCH=$(uname -m)"

case "$(uname -m)" in
    aarch64|arm64) ;;
    *)
        echo "[FATAL] This image requires ARM64/aarch64."
        exit 20
        ;;
esac

# ------------------------------------------------------------
# Writable state: ONLY /home/container
# ------------------------------------------------------------
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
    echo "[PTERO-ARM64/v2] Seeding writable SteamCMD..."
    cp -a /opt/steamcmd-seed/. /home/container/.steamcmd/
    chmod 0755 /home/container/.steamcmd/steamcmd.sh
fi

# ------------------------------------------------------------
# FEX configuration
# ------------------------------------------------------------
# Supersunho's FEX image stores its x86_64 RootFS under /opt/fex-rootfs.
# Since Wings runs us with a different UID and Pterodactyl reserves HOME as
# an EggVariable, create a user-local FEX config in the writable volume.
ROOTFS_DIR="$(find /opt/fex-rootfs -mindepth 1 -maxdepth 1 -type d -print -quit 2>/dev/null || true)"

if [[ -z "${ROOTFS_DIR}" || ! -d "${ROOTFS_DIR}" ]]; then
    echo "[FATAL] No preinstalled FEX RootFS found under /opt/fex-rootfs."
    exit 21
fi

printf '{"Config":{"RootFS":"%s"},"ThunksDB":{}}\n' "${ROOTFS_DIR}" \
    > /home/container/.fex-emu/Config.json

export HOME=/home/container
export XDG_CACHE_HOME=/home/container/.cache
export XDG_CONFIG_HOME=/home/container/.config
export XDG_DATA_HOME=/home/container/.local/share
export TMPDIR=/home/container/tmp

export SERVER_DIR=/home/container
export BACKUP_DIR=/home/container/backups
export LOG_DIR=/home/container/logs
export STEAMCMD_DIR=/home/container/.steamcmd

export FEX_ROOTFS_PATH=/opt/fex-rootfs
export FEX_ENABLE_JIT_CACHE=1
export FEX_JIT_CACHE_SIZE=1024
export FEX_ENABLE_VIXL_SIMULATOR=0
export FEX_ENABLE_VIXL_DISASSEMBLER=0
export FEX_ENABLE_LAZY_MEMORY_DELETION=1
export FEX_ENABLE_STATIC_REGISTER_ALLOCATION=1

echo "[PTERO-ARM64/v2] SERVER_DIR=${SERVER_DIR}"
echo "[PTERO-ARM64/v2] STEAMCMD_DIR=${STEAMCMD_DIR}"
echo "[PTERO-ARM64/v2] FEX RootFS=${ROOTFS_DIR}"

# Make failures obvious before starting the manager.
if [[ ! -x /home/container/.steamcmd/steamcmd.sh ]]; then
    echo "[FATAL] Writable SteamCMD bootstrap is missing."
    exit 22
fi

if [[ ! -d /app/src ]]; then
    echo "[FATAL] Supersunho manager source /app/src is missing."
    exit 23
fi

# ------------------------------------------------------------
# Runtime
# ------------------------------------------------------------
case "${1:---start-server}" in
    --start-server|"")
        echo "[PTERO-ARM64/v2] Starting Supersunho manager WITHOUT upstream entrypoint..."
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
        echo "[PTERO-ARM64/v2] Unknown mode '$1'; starting server manager."
        cd /app
        exec python -m src.server_manager
        ;;
esac
