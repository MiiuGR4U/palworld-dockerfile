#!/usr/bin/env python3
"""
log_filter.py — Streamlined Anti-Spam Log Filter for Palworld Pterodactyl Runtime
Filters out repetitive internal REST API polling and Unreal Engine Sentry HTTP/2 cURL traces
while preserving all critical server events, player notifications, warnings, and errors.
"""

import sys
import re

# Ensure unbuffered UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Regex patterns to suppress when QUIET_MONITORING=true
SUPPRESS_PATTERNS = [
    # REST API polling spam
    re.compile(r"REST accessed endpoint /v1/api/(players|info)\s+OK"),
    re.compile(r"API call completed /(players|info)"),

    # Sentry / cURL verbose HTTP2 traces from Unreal Engine
    re.compile(r"^\*\s+"),  # Lines starting with '* '
    re.compile(r"^>\s+"),  # Lines starting with '> '
    re.compile(r"^<\s+"),  # Lines starting with '< '
    re.compile(r"^(Host|user-agent|accept|x-sentry-auth|content-type|content-length):\s*"),
    re.compile(r"^o1291919\.ingest\.us\.sentry\.io"),
    re.compile(r"^\{\}\* Connection #"),

    # Steam API interface warnings during initial handshake
    re.compile(r"^\[S_API FAIL\] Tried to access Steam interface"),

    # Redundant duplicate manager verification logs
    re.compile(r"Server process started, verifying startup\.\.\."),
    re.compile(r"Verifying server process startup\.\.\."),
    re.compile(r"Checking process stability for 10 seconds\.\.\."),
    re.compile(r"Cleared only user-added callbacks"),
    re.compile(r"Auto settings generation successful:"),
    re.compile(r"Using Engine\.ini base from:"),
]

def main():
    seen_duplicate_lines = set()

    for line in sys.stdin:
        stripped = line.strip()

        # Check if line matches any suppression pattern
        should_suppress = False
        for pattern in SUPPRESS_PATTERNS:
            if pattern.search(stripped):
                should_suppress = True
                break

        if should_suppress:
            continue

        # Suppress duplicate consecutive lines for specific redundant manager events
        if "Auto settings generation successful" in stripped or "Using Engine.ini base" in stripped:
            if stripped in seen_duplicate_lines:
                continue
            seen_duplicate_lines.add(stripped)

        # Output clean line immediately
        sys.stdout.write(line)
        sys.stdout.flush()

if __name__ == "__main__":
    main()
