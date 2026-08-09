# Known Issues & Troubleshooting History — Palworld ARM64

## Historical Issues & Solutions

### 1. `mkdir: cannot create directory '/home/steam': Permission denied`
- **Root Cause**: Base image entrypoint (`/entrypoint.sh`) executed `setup_permissions()` trying to modify `/home/steam`.
- **Solution**: Bypassed upstream entrypoint in `Dockerfile` and invoked Python server manager directly from `/pterodactyl-entrypoint.sh`.

### 2. `Current RootFS path set to '' / RootFS path doesn't exist`
- **Root Cause**: `FEX_ROOTFS_PATH` was set instead of `FEX_ROOTFS`, which FEX-Emu guest bootstrap requires.
- **Solution**: Set `export FEX_ROOTFS="${ROOTFS_DIR}"` pointing to `/opt/fex-rootfs/Ubuntu_24_04` and auto-generated `/home/container/.fex-emu/Config.json`.

### 3. `kicked by AUTH. Error: Invalid AppTicket`
- **Root Cause**: `bUseAuth=True` combined with x86_64 `steamclient.so` under FEX emulation causes Steam ticket validation failure upon client handshake.
- **Solution**: Keep `USE_AUTH=false` as default Egg setting for ARM64 deployment.

### 4. `ca-certificates / dpkg error code (1) during installation`
- **Root Cause**: Running `apt-get` or `dpkg` inside Pterodactyl installation script under restricted non-root container permissions.
- **Solution**: Package all required tools (`DepotDownloader`, `steamcmd` seed) inside the Docker image during `docker build`.

### 5. `Palworld listening on 8211 instead of SERVER_PORT`
- **Root Cause**: Upstream server manager passed query options but omitted `-port=`.
- **Solution**: Append `-port=${GAME_PORT}` via `ADDITIONAL_SERVER_OPTIONS` in entrypoint.

### 6. Egg import failed on `HOME` variable declaration
- **Root Cause**: Declaring Pterodactyl-reserved environment variable `HOME` in Egg JSON `variables`.
- **Solution**: Remove `HOME` from Egg variables list; set `export HOME=/home/container` inside container entrypoint.
