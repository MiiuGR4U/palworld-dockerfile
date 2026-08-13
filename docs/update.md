# Auto Updates & SteamCMD

Updates are now fully integrated into the startup process through `ptero_manager.py`.

## Flow

1. The container starts.
2. If `UPDATE_ON_START=true`, the manager triggers the update sequence.
3. If `BACKUP_BEFORE_UPDATE=true`, it creates a backup of `Pal/Saved` to `/home/container/backups/pre-update-<timestamp>`.
4. SteamCMD is launched with `+force_install_dir /home/container` to guarantee files are downloaded to the correct Pterodactyl allocation path.
5. `app_update 2394010 validate` is executed.
6. The manager evaluates the exit code. If successful, Palworld startup continues.

## Manual Update
You can force an update using the interactive console:
- `/update now`

This will trigger a graceful shutdown of the server. You can then restart the server from Pterodactyl, which will trigger the update on boot.
