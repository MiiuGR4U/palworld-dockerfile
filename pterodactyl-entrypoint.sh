#!/bin/bash
# ==============================================================================
# Palworld ARM64 — Pterodactyl / Hydrodactyl Entrypoint Script
# High-resilience, modular, non-root runtime bootstrap with anti-spam UI
# ==============================================================================
set -Eeuo pipefail

# ------------------------------------------------------------------------------
# Configurable UI & Logging Customizations
# ------------------------------------------------------------------------------
BANNER_TITLE="${BANNER_TITLE:-Palworld ARM64 - Pterodactyl}"
STARTUP_MESSAGE="${STARTUP_MESSAGE:-Starting Supersunho Palworld Server Manager...}"
PREFLIGHT_TEST_MSG="${PREFLIGHT_TEST_MSG:-FEX guest bootstrap OK}"
ENABLE_COLOR_LOGS="${ENABLE_COLOR_LOGS:-true}"
QUIET_MONITORING="${QUIET_MONITORING:-true}"

# ANSI Colors (only applied if ENABLE_COLOR_LOGS=true)
if [[ "${ENABLE_COLOR_LOGS}" == "true" ]]; then
    C_RESET='\033[0m'
    C_BOLD='\033[1m'
    C_BLUE='\033[34m'
    C_GREEN='\033[32m'
    C_YELLOW='\033[33m'
    C_RED='\033[31m'
    C_CYAN='\033[36m'
    C_MAGENTA='\033[35m'
else
    C_RESET=''
    C_BOLD=''
    C_BLUE=''
    C_GREEN=''
    C_YELLOW=''
    C_RED=''
    C_CYAN=''
    C_MAGENTA=''
fi

log_info()    { echo -e "${C_CYAN}[INFO]${C_RESET} $*"; }
log_success() { echo -e "${C_GREEN}[✔ OK]${C_RESET}  $*"; }
log_warn()    { echo -e "${C_YELLOW}[WARN]${C_RESET}  $*"; }
log_fatal()   { echo -e "${C_RED}[FATAL]${C_RESET} $*"; }

log_section() {
    echo -e "${C_CYAN}╭────────────────────────────────────────────────────────────╮${C_RESET}"
    echo -e "${C_CYAN}│${C_RESET}  ${C_BOLD}${C_MAGENTA}$1${C_RESET}"
    echo -e "${C_CYAN}╰────────────────────────────────────────────────────────────╯${C_RESET}"
}

# Pterodactyl installer passthrough.
case "${1:-}" in
    bash|/bin/bash|sh|/bin/sh)
        exec "$@"
        ;;
esac

# ------------------------------------------------------------------------------
# 1. Architecture Validation
# ------------------------------------------------------------------------------
validate_architecture() {
    ARCH="$(uname -m)"
    if [[ "${ARCH}" != "aarch64" && "${ARCH}" != "arm64" ]]; then
        log_fatal "Unsupported architecture: '${ARCH}'. This image requires ARM64/aarch64 node."
        exit 20
    fi
}

# ------------------------------------------------------------------------------
# 2. Writable Storage Directory Setup
# ------------------------------------------------------------------------------
prepare_directories() {
    log_info "Verifying Pterodactyl volume structure under /home/container..."
    mkdir -p \
        /home/container/backups \
        /home/container/logs/palworld \
        /home/container/.steamcmd \
        /home/container/Steam \
        /home/container/.steam/sdk64 \
        /home/container/tmp \
        /home/container/.cache/fex-emu \
        /home/container/.config \
        /home/container/.local/share \
        /home/container/.fex-emu \
        /home/container/Pal/Saved/Config/LinuxServer
}

# ------------------------------------------------------------------------------
# 3. Writable SteamCMD Seeding
# ------------------------------------------------------------------------------
seed_steamcmd() {
    if [[ ! -x /home/container/.steamcmd/steamcmd.sh ]]; then
        log_info "Seeding writable SteamCMD environment..."
        if [[ -d /opt/steamcmd-seed ]]; then
            cp -a /opt/steamcmd-seed/. /home/container/.steamcmd/
            chmod 0755 /home/container/.steamcmd/steamcmd.sh
            log_success "SteamCMD seeded successfully."
        else
            log_fatal "SteamCMD seed directory /opt/steamcmd-seed missing from image!"
            exit 22
        fi
    fi
}

# ------------------------------------------------------------------------------
# 4. Environment & FEX Setup
# ------------------------------------------------------------------------------
configure_environment() {
    export HOME=/home/container
    export XDG_CACHE_HOME=/home/container/.cache
    export XDG_CONFIG_HOME=/home/container/.config
    export XDG_DATA_HOME=/home/container/.local/share
    export TMPDIR=/home/container/tmp

    # Server Manager Paths
    export SERVER_DIR=/home/container
    export BACKUP_DIR=/home/container/backups
    export LOG_DIR=/home/container/logs
    export STEAMCMD_DIR=/home/container/.steamcmd

    # Locate RootFS embedded in image
    ROOTFS_DIR="$(find /opt/fex-rootfs -mindepth 1 -maxdepth 1 -type d -print -quit 2>/dev/null || true)"

    if [[ -z "${ROOTFS_DIR}" || ! -d "${ROOTFS_DIR}" ]]; then
        log_fatal "No preinstalled FEX RootFS found under /opt/fex-rootfs."
        exit 21
    fi

    export FEX_ROOTFS="${ROOTFS_DIR}"
    export FEX_APP_CONFIG_LOCATION=/home/container/.fex-emu/
    export FEX_APP_DATA_LOCATION=/home/container/.fex-emu/
    export FEX_APP_CACHE_LOCATION=/home/container/.cache/fex-emu/

    # Write fallback config file
    printf '{"Config":{"RootFS":"%s"}}\n' "${ROOTFS_DIR}" > /home/container/.fex-emu/Config.json

    # ARM64 JIT Optimization Defaults
    export FEX_ENABLE_JIT_CACHE="${FEX_ENABLE_JIT_CACHE:-1}"
    export FEX_JIT_CACHE_SIZE="${FEX_JIT_CACHE_SIZE:-1024}"
    export FEX_ENABLE_VIXL_SIMULATOR="${FEX_ENABLE_VIXL_SIMULATOR:-0}"
    export FEX_ENABLE_VIXL_DISASSEMBLER="${FEX_ENABLE_VIXL_DISASSEMBLER:-0}"
    export FEX_ENABLE_LAZY_MEMORY_DELETION="${FEX_ENABLE_LAZY_MEMORY_DELETION:-1}"
    export FEX_ENABLE_STATIC_REGISTER_ALLOCATION="${FEX_ENABLE_STATIC_REGISTER_ALLOCATION:-1}"
}

# ------------------------------------------------------------------------------
# 5. Port Derivation & Networking
# ------------------------------------------------------------------------------
configure_ports() {
    GAME_PORT="${SERVER_PORT:-8211}"

    if ! [[ "${GAME_PORT}" =~ ^[0-9]+$ ]] || (( GAME_PORT < 1 || GAME_PORT > 65535 )); then
        log_fatal "Invalid Pterodactyl primary allocation SERVER_PORT='${GAME_PORT}'."
        exit 25
    fi

    export PUBLIC_PORT="${GAME_PORT}"

    # Force Palworld listen port through ADDITIONAL_SERVER_OPTIONS
    USER_ADDITIONAL_OPTIONS="${ADDITIONAL_SERVER_OPTIONS:-}"
    export ADDITIONAL_SERVER_OPTIONS="${USER_ADDITIONAL_OPTIONS} -port=${GAME_PORT}"
}

# ------------------------------------------------------------------------------
# 6. High-Aesthetics Unicode Console Banner
# ------------------------------------------------------------------------------
print_banner() {
    echo -e "${C_CYAN}╭────────────────────────────────────────────────────────────╮${C_RESET}"
    echo -e "${C_CYAN}│${C_RESET} ${C_BOLD}${C_MAGENTA}${BANNER_TITLE}${C_RESET}"
    echo -e "${C_CYAN}├────────────────────────────────────────────────────────────┤${C_RESET}"
    echo -e "${C_CYAN}│${C_RESET}  🎮 ${C_BOLD}Server Name${C_RESET}  : ${SERVER_NAME:-Palworld ARM64 Server}"
    echo -e "${C_CYAN}│${C_RESET}  ⚡ ${C_BOLD}Architecture${C_RESET} : $(uname -m) (UID $(id -u):$(id -g))"
    echo -e "${C_CYAN}│${C_RESET}  🌐 ${C_BOLD}Game Port${C_RESET}   : ${GAME_PORT}/UDP (Primary Allocation)"
    echo -e "${C_CYAN}│${C_RESET}  🔍 ${C_BOLD}Query Port${C_RESET}  : ${QUERY_PORT:-27018}/UDP (Extra Allocation)"
    echo -e "${C_CYAN}│${C_RESET}  🛡️ ${C_BOLD}FEX RootFS${C_RESET}   : ${FEX_ROOTFS}"
    echo -e "${C_CYAN}│${C_RESET}  🔒 ${C_BOLD}Steam Auth${C_RESET}   : ${USE_AUTH:-false} (Disabled for ARM64/FEX)"
    echo -e "${C_CYAN}│${C_RESET}  🧹 ${C_BOLD}Quiet Logs${C_RESET}   : ${QUIET_MONITORING:-true} (Anti-Spam Active)"
    echo -e "${C_CYAN}╰────────────────────────────────────────────────────────────╯${C_RESET}\n"
}

# ------------------------------------------------------------------------------
# 7. FEX Preflight Verification
# ------------------------------------------------------------------------------
preflight_fex() {
    command -v FEXBash >/dev/null 2>&1 || {
        log_fatal "FEXBash binary missing from image."
        exit 24
    }

    log_info "Executing FEX guest preflight test..."
    if FEXBash -c "printf '%s\\n' '${PREFLIGHT_TEST_MSG}'" >/dev/null 2>&1; then
        log_success "FEX guest preflight test passed."
    else
        rc=$?
        log_fatal "FEX guest preflight test failed with exit code ${rc}."
        exit "${rc}"
    fi
}

# ------------------------------------------------------------------------------
# 8. Start Manager with Optional Anti-Spam Stream Filtering
# ------------------------------------------------------------------------------
start_manager() {
    log_info "${STARTUP_MESSAGE}"
    cd /app

    FILTER_SCRIPT="/scripts/log_filter.py"
    if [[ ! -f "${FILTER_SCRIPT}" ]]; then
        FILTER_SCRIPT="$(pwd)/scripts/log_filter.py"
    fi

    if [[ "${QUIET_MONITORING}" == "true" && -f "${FILTER_SCRIPT}" ]]; then
        log_info "Anti-spam log filter enabled."
        exec python -u -m src.server_manager 2>&1 | python -u "${FILTER_SCRIPT}"
    else
        exec python -m src.server_manager
    fi
}

# ------------------------------------------------------------------------------
# Main Dispatcher
# ------------------------------------------------------------------------------
main() {
    validate_architecture
    prepare_directories
    seed_steamcmd
    configure_environment
    configure_ports
    print_banner
    preflight_fex

    case "${1:---start-server}" in
        --start-server|"")
            start_manager
            ;;
        --health-check)
            exec python /usr/local/bin/healthcheck
            ;;
        --shell)
            exec /bin/bash
            ;;
        *)
            log_info "Custom startup command: '$*'"
            cd /app
            exec python -m src.server_manager "$@"
            ;;
    esac
}

main "$@"
