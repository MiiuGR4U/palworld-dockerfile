#!/bin/bash
# Palworld ARM64 — Pterodactyl / Hydrodactyl runtime bootstrap.
set -Eeuo pipefail
umask 022

readonly SERVER_ROOT="/home/container"
readonly DEFAULT_QUERY_PORT="27018"

CONSOLE_LANG="${CONSOLE_LANG:-pt}"
BANNER_TITLE="${BANNER_TITLE:-Palworld ARM64 / Pterodactyl}"
STARTUP_MESSAGE="${STARTUP_MESSAGE:-Starting Supersunho Palworld Server Manager...}"
PREFLIGHT_TEST_MSG="${PREFLIGHT_TEST_MSG:-FEX guest bootstrap OK}"
ENABLE_COLOR_LOGS="${ENABLE_COLOR_LOGS:-true}"
QUIET_MONITORING="${QUIET_MONITORING:-true}"

export CONSOLE_LANG ENABLE_COLOR_LOGS QUIET_MONITORING

if [[ "${ENABLE_COLOR_LOGS}" == "true" ]]; then
    C_RESET='\033[0m'
    C_GREEN='\033[32m'
    C_YELLOW='\033[33m'
    C_RED='\033[31m'
    C_CYAN='\033[36m'
else
    C_RESET=''
    C_GREEN=''
    C_YELLOW=''
    C_RED=''
    C_CYAN=''
fi

log_info()  { echo -e "${C_CYAN}[INFO]${C_RESET} $*"; }
log_ok()    { echo -e "${C_GREEN}[OK]${C_RESET} $*"; }
log_warn()  { echo -e "${C_YELLOW}[WARN]${C_RESET} $*"; }
log_error() { echo -e "${C_RED}[ERROR]${C_RESET} $*" >&2; }

fatal() {
    local message="$1"
    local exit_code="${2:-1}"
    log_error "${message}"
    exit "${exit_code}"
}

is_true() {
    case "${1:-}" in
        true|TRUE|True|1|yes|YES|Yes|on|ON|On) return 0 ;;
        *) return 1 ;;
    esac
}

validate_port() {
    local name="$1"
    local value="$2"
    if ! [[ "${value}" =~ ^[0-9]+$ ]] || (( value < 1 || value > 65535 )); then
        fatal "Invalid ${name}='${value}'. Expected an integer from 1 to 65535." 25
    fi
}

installer_passthrough() {
    case "${1:-}" in
        bash|/bin/bash|sh|/bin/sh)
            exec "$@"
            ;;
    esac
}

validate_architecture() {
    RUNTIME_ARCH="$(uname -m)"
    case "${RUNTIME_ARCH}" in
        aarch64|arm64) ;;
        *) fatal "Unsupported architecture '${RUNTIME_ARCH}'. This image requires ARM64/aarch64." 20 ;;
    esac
    export RUNTIME_ARCH
}

validate_runtime_user() {
    if (( $(id -u) == 0 )); then
        fatal "Runtime must be non-root. Configure Wings to run this image with the server UID/GID." 23
    fi
}

prepare_writable_paths() {
    log_info "Preparing writable paths under ${SERVER_ROOT}..."
    mkdir -p \
        "${SERVER_ROOT}/backups" \
        "${SERVER_ROOT}/logs/palworld" \
        "${SERVER_ROOT}/.steamcmd" \
        "${SERVER_ROOT}/Steam" \
        "${SERVER_ROOT}/.steam/sdk64" \
        "${SERVER_ROOT}/tmp" \
        "${SERVER_ROOT}/.cache/fex-emu" \
        "${SERVER_ROOT}/.config" \
        "${SERVER_ROOT}/.local/share" \
        "${SERVER_ROOT}/.fex-emu" \
        "${SERVER_ROOT}/Pal/Saved/Config/LinuxServer"
}

seed_steamcmd() {
    local target="${SERVER_ROOT}/.steamcmd/steamcmd.sh"
    if [[ -x "${target}" ]]; then
        return
    fi

    log_info "Seeding the writable SteamCMD runtime..."
    [[ -d /opt/steamcmd-seed ]] || fatal "SteamCMD seed directory /opt/steamcmd-seed is missing." 22
    cp -a /opt/steamcmd-seed/. "${SERVER_ROOT}/.steamcmd/"
    chmod 0755 "${target}"
    [[ -x "${target}" ]] || fatal "SteamCMD seed did not produce an executable launcher." 22
    log_ok "Writable SteamCMD runtime is ready."
}

configure_writable_environment() {
    export HOME="${SERVER_ROOT}"
    export XDG_CACHE_HOME="${SERVER_ROOT}/.cache"
    export XDG_CONFIG_HOME="${SERVER_ROOT}/.config"
    export XDG_DATA_HOME="${SERVER_ROOT}/.local/share"
    export TMPDIR="${SERVER_ROOT}/tmp"

    export SERVER_DIR="${SERVER_ROOT}"
    export BACKUP_DIR="${SERVER_ROOT}/backups"
    export LOG_DIR="${SERVER_ROOT}/logs"
    export STEAMCMD_DIR="${SERVER_ROOT}/.steamcmd"
}

detect_fex_rootfs() {
    local preferred="/opt/fex-rootfs/Ubuntu_24_04"
    local candidates=()

    [[ -d /opt/fex-rootfs ]] || fatal "FEX RootFS parent /opt/fex-rootfs is missing." 21

    if [[ -d "${preferred}" ]]; then
        FEX_ROOTFS="${preferred}"
    else
        mapfile -t candidates < <(
            find /opt/fex-rootfs -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sort
        )
        if (( ${#candidates[@]} == 0 )); then
            fatal "No FEX RootFS was found below /opt/fex-rootfs." 21
        fi
        if (( ${#candidates[@]} > 1 )); then
            fatal "Multiple FEX RootFS candidates found and Ubuntu_24_04 is absent: ${candidates[*]}" 21
        fi
        FEX_ROOTFS="${candidates[0]}"
    fi

    if [[ -z "$(find "${FEX_ROOTFS}" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
        fatal "Detected FEX RootFS is empty: ${FEX_ROOTFS}" 21
    fi
    export FEX_ROOTFS
}

configure_fex() {
    detect_fex_rootfs

    export FEX_APP_CONFIG_LOCATION="${SERVER_ROOT}/.fex-emu/"
    export FEX_APP_DATA_LOCATION="${SERVER_ROOT}/.fex-emu/"
    export FEX_APP_CACHE_LOCATION="${SERVER_ROOT}/.cache/fex-emu/"
    export FEX_ENABLE_JIT_CACHE="${FEX_ENABLE_JIT_CACHE:-1}"
    export FEX_JIT_CACHE_SIZE="${FEX_JIT_CACHE_SIZE:-1024}"
    export FEX_ENABLE_VIXL_SIMULATOR="${FEX_ENABLE_VIXL_SIMULATOR:-0}"
    export FEX_ENABLE_VIXL_DISASSEMBLER="${FEX_ENABLE_VIXL_DISASSEMBLER:-0}"
    export FEX_ENABLE_LAZY_MEMORY_DELETION="${FEX_ENABLE_LAZY_MEMORY_DELETION:-1}"
    export FEX_ENABLE_STATIC_REGISTER_ALLOCATION="${FEX_ENABLE_STATIC_REGISTER_ALLOCATION:-1}"

    local config_file="${SERVER_ROOT}/.fex-emu/Config.json"
    local config_temp="${config_file}.tmp.$$"
    printf '{"Config":{"RootFS":"%s"}}\n' "${FEX_ROOTFS}" > "${config_temp}"
    chmod 0644 "${config_temp}"
    mv -f "${config_temp}" "${config_file}"
}

fex_preflight() {
    command -v FEXBash >/dev/null 2>&1 || fatal "FEXBash is missing from the runtime image." 24

    log_info "Running the FEX guest bootstrap preflight..."
    if FEXBash -c "printf '%s\\n' '${PREFLIGHT_TEST_MSG}'" >/dev/null 2>&1; then
        log_ok "FEX guest bootstrap OK."
    else
        local exit_code=$?
        fatal "FEX guest bootstrap failed with exit code ${exit_code}." "${exit_code}"
    fi
}

configure_game_port() {
    [[ -n "${SERVER_PORT:-}" ]] || fatal "SERVER_PORT was not injected by Pterodactyl." 25
    validate_port "SERVER_PORT" "${SERVER_PORT}"

    if [[ " ${ADDITIONAL_SERVER_OPTIONS:-} " =~ [[:space:]]-port([=[:space:]]) ]]; then
        fatal "Do not set -port in ADDITIONAL_SERVER_OPTIONS; the primary allocation controls it." 25
    fi

    GAME_PORT="${SERVER_PORT}"
    PUBLIC_PORT="${SERVER_PORT}"
    ADDITIONAL_SERVER_OPTIONS="${ADDITIONAL_SERVER_OPTIONS:-} -port=${SERVER_PORT}"
    ADDITIONAL_SERVER_OPTIONS="${ADDITIONAL_SERVER_OPTIONS# }"
    export GAME_PORT PUBLIC_PORT ADDITIONAL_SERVER_OPTIONS
}

configure_query_port() {
    QUERY_PORT="${QUERY_PORT:-${DEFAULT_QUERY_PORT}}"
    validate_port "QUERY_PORT" "${QUERY_PORT}"
    export QUERY_PORT
}

print_runtime_summary() {
    local auth_state="disabled"
    local update_state="disabled"
    local mods_state="disabled"
    local safe_mode_state="no"
    is_true "${USE_AUTH:-false}" && auth_state="enabled"
    is_true "${UPDATE_ON_START:-true}" && update_state="enabled"
    is_true "${MODS_ENABLED:-false}" && mods_state="enabled"
    is_true "${MODS_SAFE_MODE:-false}" && safe_mode_state="yes"

    cat <<EOF
============================================================
 ${BANNER_TITLE}
============================================================
 Architecture                : ${RUNTIME_ARCH}
 Guest                       : x86_64 / FEX
 Runtime UID:GID             : $(id -u):$(id -g)
 Server Dir                  : ${SERVER_ROOT}
 Primary game allocation     : ${SERVER_IP:-0.0.0.0}:${GAME_PORT}/UDP
 Palworld listen argument    : -port=${GAME_PORT}
 PublicPort synchronized     : ${PUBLIC_PORT}
 Query allocation (EXTRA)    : ${QUERY_PORT}/UDP
 REST API (internal)         : localhost:${REST_API_PORT:-8212}/TCP
 RCON (internal)             : localhost:${RCON_PORT:-25575}/TCP
 FEX RootFS                  : ${FEX_ROOTFS}
 Steam Auth                  : ${auth_state}
 Auto Update                 : ${update_state}
 Mod System                  : ${mods_state}
 Mod Safe Mode               : ${safe_mode_state}
============================================================
EOF
}

palmodctl_path() {
    printf '%s\n' "/opt/palworld-mod-runtime/palmodctl"
}

configure_mod_guest_preload() {
    local tool="$1"
    local preload_path=""
    local real_fex=""
    local shim_dir="/opt/palworld-mod-runtime/bin"

    if ! preload_path="$("${tool}" preload-path)"; then
        log_info "UE4SS guest preload not required."
        return 0
    fi
    [[ -f "${preload_path}" ]] || fatal "palmodctl returned a missing preload: ${preload_path}" 33

    real_fex="$(command -v FEXBash || true)"
    [[ -n "${real_fex}" && -x "${real_fex}" ]] || fatal "Cannot resolve the real FEXBash." 24
    [[ "${real_fex}" != "${shim_dir}/FEXBash" ]] || fatal "FEXBash shim recursion detected." 33

    export PALMOD_REAL_FEXBASH="${real_fex}"
    export PALMOD_UE4SS_PRELOAD="${preload_path}"
    export PATH="${shim_dir}:${PATH}"
    log_warn "UE4SS Linux EXPERIMENTAL: guest-only preload enabled for PalServer x86_64."
}

mods_initialize() {
    local tool
    tool="$(palmodctl_path)"
    local inventory="${SERVER_ROOT}/mods/state/inventory.json"

    if ! is_true "${MODS_ENABLED:-false}" \
        && ! is_true "${MODS_SAFE_MODE:-false}" \
        && [[ ! -f "${inventory}" ]]; then
        log_info "Mod system disabled; vanilla baseline path selected."
        return 0
    fi

    [[ -x "${tool}" ]] || fatal "palmodctl is required but missing from the image: ${tool}" 30

    if is_true "${MODS_ENABLED:-false}" && ! is_true "${MODS_SAFE_MODE:-false}"; then
        log_info "Scanning mod source tree (static inspection only)."
        "${tool}" scan
        log_info "Validating all detected mods before deployment."
        if ! "${tool}" validate; then
            if is_true "${MODS_FAIL_ON_ERROR:-true}"; then
                log_warn "Validation failed; deployment will record quarantine state and refuse startup."
            else
                log_warn "Mod validation reported errors; invalid entries will be skipped/quarantined."
            fi
        fi
    fi

    log_info "Applying mod deployment state."
    "${tool}" deploy || fatal "palmodctl deployment failed." 32
    "${tool}" status
    configure_mod_guest_preload "${tool}"
}

preserve_custom_ini() {
    local ini_path="${SERVER_ROOT}/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini"
    local backup_path="${SERVER_ROOT}/tmp/PalWorldSettings.ini.userbak"

    if is_true "${PRESERVE_CUSTOM_SETTINGS:-true}" && [[ -f "${ini_path}" ]]; then
        log_info "Saving the current PalWorldSettings.ini for the existing compatibility guard."
        cp -a "${ini_path}" "${backup_path}"
    fi
}

# Forward shutdown, process_is_running, cleanup_runtime_children, and wait_for_manager 
# are obsolete as ptero_manager.py handles everything in Python now.

start_helper() {
    local helper_script="/scripts/palworld_helper.py"
    [[ -f "${helper_script}" ]] || return 0

    log_info "Starting the Palworld helper suite."
    python -u "${helper_script}" >/dev/null 2>&1 &
    HELPER_PID=$!
}

# Wait for manager removed

start_manager() {
    local manager_args=("$@")

    log_info "${STARTUP_MESSAGE}"
    cd /app
    preserve_custom_ini
    start_helper

    # Delegate the rest of execution (SteamCMD, signals, interactive console, and manager wrapper)
    # to the new Python Pterodactyl manager. Using exec replaces PID 1.
    log_info "Delegating to Pterodactyl Integration Manager (ptero_manager.py)..."
    exec python -u /scripts/ptero_manager.py "${manager_args[@]}"
}

main() {
    installer_passthrough "$@"
    validate_architecture
    validate_runtime_user
    prepare_writable_paths
    seed_steamcmd
    configure_writable_environment
    configure_fex
    configure_game_port
    configure_query_port
    print_runtime_summary
    fex_preflight
    mods_initialize

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
            log_info "Passing custom arguments to the Supersunho manager: $*"
            start_manager "$@"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
