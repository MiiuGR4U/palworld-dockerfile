# Port Allocation Guide — Palworld ARM64

## Overview of Port Roles

| Port Name | Environment Var | Pterodactyl Allocation | Protocol | Visibility / Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Game Port** | Injected `SERVER_PORT` | **Primary Allocation** | UDP | Public direct-connect game traffic |
| **Steam Query Port** | `QUERY_PORT` | **Extra Allocation** | UDP | Steam Server Browser / Master Server query |
| **Internal REST API** | `REST_API_PORT` (8212) | Internal (`localhost`) | TCP | Used by Supersunho manager |
| **Internal RCON** | `RCON_PORT` (25575) | Internal (`localhost`) | TCP | Used for graceful shutdown & manager commands |

---

## 1. Game Port (Primary Allocation)
- **Automatic Derivation**: The primary game port is derived automatically from the Pterodactyl `SERVER_PORT` allocation.
- **Listen Parameter**: Passed automatically to Palworld as `-port=${SERVER_PORT}` via `ADDITIONAL_SERVER_OPTIONS`.
- **Public Port Sync**: `PUBLIC_PORT` is synchronized automatically to match `SERVER_PORT`.
- **User Action**: The administrator does **not** need to manually configure the primary game port.

Expected startup lines:

```text
Primary game allocation     : IP:PORT/UDP
Palworld listen argument    : -port=PORT
PublicPort synchronized     : PORT
```

Do not add `-port` to `ADDITIONAL_SERVER_OPTIONS`; startup rejects a duplicate override.

---

## 2. Steam Query Port (Extra Allocation)
- **Purpose**: Required if you want your Palworld server to appear in the Steam Server Browser query list.
- **Requirement**: Add **ONE extra UDP allocation** in Pterodactyl (e.g. `27018/UDP`).
- **Configuration**: Set the `QUERY_PORT` variable in the Pterodactyl panel to match that allocation's port number.

---

## 3. Internal REST API & RCON
- **Purpose**: Process monitoring, status reporting, and graceful server shutdowns (`^C` or stop button).
- **Security**: Bound internally to `localhost`. They do **not** require extra Pterodactyl allocations and are hidden from end users.
