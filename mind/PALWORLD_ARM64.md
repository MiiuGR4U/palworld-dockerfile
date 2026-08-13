# Palworld ARM64 Pterodactyl Integration Architecture

## Overview
This document captures the decisions made during the major refactoring to deeply integrate the Palworld ARM64 FEX-Emu container into Pterodactyl/Wings.

## Previous Flaws
- **Dead Console:** `pterodactyl-entrypoint.sh` launched `src.server_manager` in the background and used `wait`. Pterodactyl's `stdin` was never consumed, making the console read-only.
- **Broken Shutdown:** Pterodactyl sent `SIGTERM`, which bash converted to `SIGINT`. Upstream manager failed to gracefully flush saves and shut down in time, leading to `SIGKILL`.
- **Broken Updates:** SteamCMD wasn't updating `/home/container` correctly before starting the game.

## The Solution: `ptero_manager.py`
We introduced a Python wrapper (`scripts/ptero_manager.py`) to act as the primary foreground process (PID 1).

### Flow
1. **Pterodactyl starts the container.**
2. `pterodactyl-entrypoint.sh` executes preflight and environment setup.
3. Entrypoint uses `exec python -u /scripts/ptero_manager.py` to replace itself.
4. **Update Phase:** `ptero_manager.py` checks `UPDATE_ON_START`. If true, it runs `steamcmd` forcing `/home/container`.
5. **Manager Launch:** It launches the upstream `src.server_manager` as a subprocess.
6. **Command Router:** It runs a daemon thread reading `sys.stdin`. Internal commands (`/save`, `/say`, `/memory`, `/stop`) are routed via REST API or OS commands.
7. **Graceful Shutdown:** It traps `SIGTERM`/`SIGINT`, sends an explicit `/save` API call, waits for it, and then sends `SIGINT` to the upstream manager, waiting up to `GRACEFUL_SHUTDOWN_TIMEOUT` (120s) before clean exit.

## Decisions Made
- **Preserve Existing Manager:** We did NOT remove `src.server_manager` or build a parallel V2. Instead, we wrapped it to provide the exact integrations Pterodactyl expects while preserving its REST/RCON functionalities.
- **Memory Diagnostics:** We added `/memory` to dump cgroup and RSS metrics rather than artificially multiplying Pterodactyl's metrics. This ensures Wings gets the real, unmasked data from Docker cgroups.
- **Save Before Stop:** The `/stop` command and the `SIGTERM` trap both explicitly call the REST API `/save` before killing any processes.

## Extensibility
The command router in `ptero_manager.py` is modular and easy to expand. More commands can be added to the loop reading from `sys.stdin`.
