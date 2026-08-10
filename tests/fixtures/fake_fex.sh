#!/bin/bash
set -eu
printf '%s\n' "$@" > "${PALMOD_TEST_CAPTURE}"
