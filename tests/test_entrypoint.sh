#!/bin/bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../pterodactyl-entrypoint.sh
source "${PROJECT_DIR}/pterodactyl-entrypoint.sh"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

is_true true || fail "true was not accepted"
is_true TRUE || fail "TRUE was not accepted"
is_true 1 || fail "1 was not accepted"
if is_true false; then fail "false was accepted"; fi
if is_true yesplease; then fail "arbitrary truthy text was accepted"; fi

SERVER_PORT=25565
ADDITIONAL_SERVER_OPTIONS="-useperfthreads"
configure_game_port
[[ "${GAME_PORT}" == "25565" ]] || fail "GAME_PORT was not derived from SERVER_PORT"
[[ "${PUBLIC_PORT}" == "25565" ]] || fail "PUBLIC_PORT was not synchronized"
[[ "${ADDITIONAL_SERVER_OPTIONS}" == "-useperfthreads -port=25565" ]] || fail "listen argument mismatch"

QUERY_PORT=27018
configure_query_port
[[ "${QUERY_PORT}" == "27018" ]] || fail "QUERY_PORT changed unexpectedly"

if (SERVER_PORT=25565; ADDITIONAL_SERVER_OPTIONS="-port=8211"; configure_game_port >/dev/null 2>&1); then
    fail "duplicate user -port was accepted"
fi

if (QUERY_PORT=70000; configure_query_port >/dev/null 2>&1); then
    fail "invalid query port was accepted"
fi

RUNTIME_ARCH=aarch64
FEX_ROOTFS=/opt/fex-rootfs/Ubuntu_24_04
SERVER_IP=192.0.2.10
GAME_PORT=25565
PUBLIC_PORT=25565
QUERY_PORT=27018
ADMIN_PASSWORD=must-not-appear
SERVER_PASSWORD=must-not-appear-either
summary="$(print_runtime_summary)"
[[ "${summary}" == *"192.0.2.10:25565/UDP"* ]] || fail "primary allocation missing from summary"
[[ "${summary}" == *"PublicPort synchronized     : 25565"* ]] || fail "PublicPort summary missing"
[[ "${summary}" != *"must-not-appear"* ]] || fail "ADMIN_PASSWORD leaked in summary"
[[ "${summary}" != *"must-not-appear-either"* ]] || fail "SERVER_PASSWORD leaked in summary"

case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        echo "Signal forwarding integration: SKIP (Windows POSIX compatibility layer)"
        ;;
    *)
        signal_ready="$(mktemp)"
        python -c 'import pathlib,signal,sys,time; pathlib.Path(sys.argv[1]).write_text("ready"); signal.signal(signal.SIGINT, lambda *_: sys.exit(42)); time.sleep(10)' "${signal_ready}" &
        MANAGER_PID=$!
        HELPER_PID=""
        for _ in 1 2 3 4 5; do
            [[ -s "${signal_ready}" ]] && break
            sleep 1
        done
        [[ -s "${signal_ready}" ]] || fail "signal test child did not become ready"
        SHUTDOWN_REQUESTED=false
        forward_shutdown SIGTERM
        set +e
        wait "${MANAGER_PID}"
        signal_exit=$?
        set -e
        rm -f -- "${signal_ready}"
        [[ "${signal_exit}" == "42" ]] || fail "SIGTERM was not translated to manager SIGINT"
        ;;
esac

echo "Entrypoint unit tests: PASS"
