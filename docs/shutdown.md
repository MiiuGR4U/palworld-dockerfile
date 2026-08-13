# Graceful Shutdown

Pterodactyl sends a `SIGTERM` signal when the user clicks **Stop**. In the past, this was intercepted by bash and forwarded as `SIGINT`, which often led to timeout and Pterodactyl resorting to a hard `SIGKILL`.

## The New Shutdown Flow

`ptero_manager.py` captures `SIGTERM` (Stop) and `SIGINT` (Ctrl+C).

1. **Intercept Signal**: Manager blocks immediate termination.
2. **Request Save**: An API request is sent to Palworld's REST API (`/v1/api/save`) to ensure all player data is flushed to disk.
3. **Wait for Save**: The manager waits 3 seconds to allow the disk flush to complete.
4. **Propagate Signal**: The manager sends `SIGINT` to the upstream `src.server_manager` subprocess.
5. **Wait for Exit**: The manager waits up to `GRACEFUL_SHUTDOWN_TIMEOUT` (default: 120s).
6. **Fallback**: If the timeout is reached, the manager sends `SIGKILL` to forcefully terminate stuck processes.
7. **Clean Exit**: The container exits with code 0, signaling a clean stop to Pterodactyl.

## Configuration
- `GRACEFUL_SHUTDOWN_TIMEOUT`: Number of seconds to wait before resorting to KILL. Default is 120.
