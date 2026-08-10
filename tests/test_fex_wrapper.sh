#!/bin/bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf -- "${TEST_DIR}"' EXIT

FAKE_FEX="${TEST_DIR}/real-fex"
CAPTURE="${TEST_DIR}/capture.txt"
PRELOAD="${TEST_DIR}/libUE4SS.so"
touch "${PRELOAD}"
cp "${PROJECT_DIR}/tests/fixtures/fake_fex.sh" "${FAKE_FEX}"
chmod 0755 "${FAKE_FEX}"

PALMOD_REAL_FEXBASH="${FAKE_FEX}" \
PALMOD_UE4SS_PRELOAD="${PRELOAD}" \
PALMOD_TEST_CAPTURE="${CAPTURE}" \
    "${PROJECT_DIR}/scripts/FEXBash" -c "/home/container/PalServer.sh -port=25565"

guest_command="$(sed -n '2p' "${CAPTURE}")"
[[ "${guest_command}" == *"LD_PRELOAD="* ]] || {
    echo "FAIL: PalServer guest command did not receive LD_PRELOAD" >&2
    exit 1
}
[[ "${guest_command}" == *"/home/container/PalServer.sh -port=25565"* ]] || {
    echo "FAIL: PalServer guest command was not preserved" >&2
    exit 1
}

PALMOD_REAL_FEXBASH="${FAKE_FEX}" \
PALMOD_UE4SS_PRELOAD="${PRELOAD}" \
PALMOD_TEST_CAPTURE="${CAPTURE}" \
    "${PROJECT_DIR}/scripts/FEXBash" -c "/home/container/.steamcmd/steamcmd.sh +quit"

steam_command="$(sed -n '2p' "${CAPTURE}")"
[[ "${steam_command}" != *"LD_PRELOAD="* ]] || {
    echo "FAIL: SteamCMD guest command received the UE4SS preload" >&2
    exit 1
}

echo "FEX guest-only preload tests: PASS"
