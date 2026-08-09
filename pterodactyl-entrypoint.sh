#!/bin/bash
set -Eeuo pipefail

# Pterodactyl installer keeps the Docker image ENTRYPOINT and passes
# "bash /mnt/install/install.sh" as CMD. Pass installer/shell commands through.
case "${1:-}" in
    bash|/bin/bash|sh|/bin/sh)
        exec "$@"
        ;;
esac

echo "[PTERO-ARM64] Preparing writable Wings filesystem..."
echo "[PTERO-ARM64] UID:GID=$(id -u):$(id -g) ARCH=$(uname -m)"

mkdir -p \
    /home/container/backups \
    /home/container/logs/palworld \
    /home/container/.steamcmd \
    /home/container/Steam \
    /home/container/tmp \
    /home/container/.cache \
    /home/container/.config \
    /home/container/.local/share \
    /home/container/Pal/Saved/Config/LinuxServer

if [[ ! -x /home/container/.steamcmd/steamcmd.sh ]]; then
    echo "[PTERO-ARM64] Seeding writable SteamCMD..."
    cp -a /opt/steamcmd-seed/. /home/container/.steamcmd/
    chmod 0755 /home/container/.steamcmd/steamcmd.sh
fi

# HOME is reserved by Pterodactyl as an EggVariable, so set it internally.
export HOME=/home/container
export XDG_CACHE_HOME=/home/container/.cache
export XDG_CONFIG_HOME=/home/container/.config
export XDG_DATA_HOME=/home/container/.local/share
export TMPDIR=/home/container/tmp

export SERVER_DIR=/home/container
export BACKUP_DIR=/home/container/backups
export LOG_DIR=/home/container/logs
export STEAMCMD_DIR=/home/container/.steamcmd

exec /entrypoint-upstream.sh "$@"
