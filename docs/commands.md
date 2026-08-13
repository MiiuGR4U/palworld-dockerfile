# Command Router (Pterodactyl Console)

This image introduces a dedicated `ptero_manager.py` which intercepts Pterodactyl's `stdin` to provide a robust, interactive console.

## Internal Commands

Internal commands start with `/` and are processed directly by the manager.

- `/help` or `/?`: Show the list of internal commands.
- `/status` or `/info`: Show server health, uptime, version, and player count.
- `/save` or `/saveworld`: Force an immediate world save via REST API.
- `/say <msg>` or `/broadcast <msg>`: Send a global chat message to all players.
- `/players` or `/list`: List active players and their IDs.
- `/stop`: Trigger a graceful shutdown (save -> terminate manager -> terminate PalServer).
- `/update now`: Force a SteamCMD update check immediately (shuts down the server first).
- `/memory`: Show RAM diagnostics, comparing `cgroup memory.current` with individual process RSS. Useful to debug Pterodactyl RAM usage.
- `/processes`: Print the container's process tree to the console.

## RCON / External Commands

Any command that does not start with `/` (or is not recognized as internal) is currently ignored or can be routed to RCON in future extensions. For now, use the `/` commands to manage the server.
