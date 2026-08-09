# Current State — Palworld ARM64 Pterodactyl/Hydrodactyl

## Core Overview
The project runs Palworld Dedicated Server (Linux x86_64) on ARM64 Pterodactyl Wings nodes using FEX-Emu with an embedded Ubuntu 24.04 RootFS.

## Architecture
- Host: Pterodactyl Wings (ARM64 / `aarch64`)
- Container Base: `supersunho/palworld-server:latest-arm64`
- Emulation: FEX-Emu with embedded RootFS at `/opt/fex-rootfs/Ubuntu_24_04`
- Game Server: Palworld Dedicated Server (`AppID 2394010`)
- Writable Root: Strictly `/home/container`
- Installer: Native ARM64 `DepotDownloader` (`/opt/depotdownloader/DepotDownloader`)

## Key Working Decisions
1. **Entrypoint Bypass**: We do not invoke `/entrypoint.sh` from the base image because `setup_permissions()` attempts to write to `/home/steam`, causing `Permission denied` under Wings non-root runtime.
2. **Direct Manager Invocation**: Starts `cd /app && exec python -m src.server_manager` directly under non-root Pterodactyl user.
3. **Primary Game Port (`SERVER_PORT`)**: Automatically derived from Pterodactyl primary allocation and appended via `ADDITIONAL_SERVER_OPTIONS="-port=${SERVER_PORT}"`. `PUBLIC_PORT` is synchronized automatically.
4. **Steam Authentication (`USE_AUTH=false`)**: Defaults to `false` on ARM64/FEX to prevent `Invalid AppTicket` authentication drops.
5. **Hydrodactyl Rules**: Boolean variables use `required|string|in:true,false` instead of `required|boolean`. Reserved Pterodactyl environment variables (`HOME`, `SERVER_PORT`, etc.) are NOT declared in Egg variables.
