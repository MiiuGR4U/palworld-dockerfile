# Troubleshooting Guide — Palworld ARM64

This document records known runtime issues, error signatures, root causes, and verified solutions.

---

### Issue 1: `mkdir: cannot create directory '/home/steam': Permission denied`
- **Symptom**: Container fails to start immediately upon launch.
- **Cause**: Upstream image `/entrypoint.sh` runs `setup_permissions()` attempting to modify `/home/steam`. Under Wings non-root runtime, user `container` has no write access outside `/home/container`.
- **Solution**: Bypass upstream `/entrypoint.sh` in `Dockerfile`. Use `pterodactyl-entrypoint.sh` which executes `cd /app && exec python -m src.server_manager` directly.

---

### Issue 2: `Current RootFS path set to '' / RootFS path doesn't exist`
- **Symptom**: FEX guest bootstrap fails with exit code 21.
- **Cause**: Environment variable `FEX_ROOTFS_PATH` was set instead of `FEX_ROOTFS`.
- **Solution**: Export `FEX_ROOTFS=/opt/fex-rootfs/Ubuntu_24_04` and generate `/home/container/.fex-emu/Config.json`.

---

### Issue 3: `kicked by AUTH. Error: Invalid AppTicket`
- **Symptom**: Players join server but are instantly kicked during handshake.
- **Cause**: Steam AppTicket validation failure under x86_64 FEX emulation.
- **Solution**: Set `USE_AUTH=false` in Egg variables.

---

### Issue 4: `ca-certificates / dpkg error code (1)`
- **Symptom**: Installation script fails during `apt-get` or `dpkg` execution.
- **Cause**: Attempting to run package managers inside restricted non-root installer container.
- **Solution**: Pre-install all required binaries (`DepotDownloader`, `steamcmd` seed) inside custom Docker image.

---

### Issue 5: `Palworld listening on 8211 instead of SERVER_PORT`
- **Symptom**: Server starts but players cannot connect on configured Pterodactyl primary port.
- **Cause**: Server manager passes query options without appending `-port=`.
- **Solution**: Automatically append `-port=${SERVER_PORT}` via `ADDITIONAL_SERVER_OPTIONS`.

---

### Issue 6: `Egg Import Error: Reserved Variable 'HOME'`
- **Symptom**: Pterodactyl/Hydrodactyl panel throws validation error when importing `egg-palworld-arm64.json`.
- **Cause**: Variable `HOME` declared in Egg JSON `variables`.
- **Solution**: Remove `HOME` from Egg variables list; export `HOME=/home/container` inside container entrypoint.

---

### Issue 7: `Windows DLL detected`
- **Cause**: A Windows UE4SS `.dll` or PE binary was uploaded to the Linux backend.
- **Solution**: Remove/disable the entry or obtain a Linux x86_64 ELF `.so`. Renaming is not conversion.

---

### Issue 8: `UE4SS preflight failed`
- **Cause**: Missing/invalid pinned loader files, unknown strict-version match, or missing Blueprint components.
- **Solution**: Enable `MODS_SAFE_MODE=true`, boot vanilla, inspect `palmodctl doctor` and image metadata. Do not bypass the preflight on production saves.

---

### Issue 9: Character appears new after UE4SS
- **Severity**: Critical.
- **Action**: Stop, enable Safe Mode, preserve all logs/states, compare PlayerUID/GUID/save filename, and use explicit rollback only after review. Do not continue testing mods.

---

### Issue 10: Invalid mod quarantined
- **Cause**: Invalid manifest, incomplete Pak group, missing `scripts/main.lua`, DLL/PE, wrong ELF architecture, or dependency error.
- **Solution**: Correct the source, then clear logical quarantine with `palmodctl quarantine MOD_ID --clear` and restart.
