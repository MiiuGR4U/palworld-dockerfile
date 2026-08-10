# Baseline Audit — 2026-08-10

## Scope and reproducibility

This audit describes the functional repository baseline before the mod subsystem is introduced.

- Local branch: `dev`
- Local commit: `8686f93c26ef94bf9b359067acb5f238a1a9cab4`
- Worktree at audit start: clean
- Upstream source inspected: `supersunho/docker-palworld-server` at commit `d473e05152bce698adbf1020e51c40700b0a0dd0`
- Important limitation: the local Dockerfile consumes the mutable image tag `supersunho/palworld-server:latest-arm64`; the inspected upstream source is therefore evidence of the current public implementation, not proof of the exact image digest deployed in production.

The existing Egg, shell syntax, Python compilation, and INI preservation smoke test all pass. A Docker build and an ARM64/FEX runtime test were not possible on the audit workstation because no Docker engine is installed.

## 1. Current tree

```text
.
├── .github/
│   └── workflows/
│       └── build.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── ARM64-FEX.md
│   ├── BASELINE-AUDIT.md
│   ├── DEVELOPMENT.md
│   ├── INSTALLATION.md
│   ├── PORTS.md
│   └── TROUBLESHOOTING.md
├── mind/
│   ├── CURRENT_STATE.md
│   ├── DECISIONS.md
│   ├── KNOWN_ISSUES.md
│   ├── TEST_MATRIX.md
│   └── TODO.md
├── scripts/
│   ├── log_filter.py
│   ├── palworld_helper.py
│   ├── test_ini_preservation.py
│   ├── validate-egg.py
│   ├── validate-shell.py
│   └── validate-shell.sh
├── Dockerfile
├── README.md
├── egg-palworld-arm64.json
└── pterodactyl-entrypoint.sh
```

At the audited commit there were 18 tracked files. `BASELINE-AUDIT.md` and `mind/TEST_MATRIX.md` are the first documentation-only additions made after the snapshot.

## 2. Current architecture

```text
Pterodactyl/Hydrodactyl Wings on ARM64
  -> custom ARM64 image
  -> custom non-root-compatible entrypoint
  -> Supersunho Python manager in /app
  -> FEXBash
  -> Ubuntu 24.04 x86_64 RootFS under /opt/fex-rootfs
  -> Linux x86_64 PalServer
```

Persistent and mutable state is redirected to `/home/container`. The custom entrypoint deliberately bypasses the upstream entrypoint because the latter creates and recursively changes ownership under `/home/steam`, which fails under a Wings-assigned non-root UID/GID.

The local repository does not vendor the Supersunho manager. Update, settings generation, REST/RCON management, process monitoring, and graceful shutdown logic therefore remain an upstream runtime dependency.

## 3. Installer flow

The installer is embedded in `egg-palworld-arm64.json` and runs with `/mnt/server` as its target:

1. Validate `aarch64`/`arm64` and check native DepotDownloader.
2. Create writable server, backup, log, SteamCMD, cache, config, and temp directories.
3. Run pinned-version DepotDownloader for App ID `2394010` with `-os linux -osarch 64 -validate`.
4. Verify `Pal/Binaries/Linux/PalServer-Linux-Shipping` and seed SteamCMD from the image.
5. Print paths and disk usage.

The installer does not call `apt`, `apt-get`, or `dpkg`. It does not explicitly delete `Pal/Saved`, mods, configs, or backups. DepotDownloader operates on the server root, so preservation must continue to be covered by regression tests and documentation.

## 4. Runtime flow

`pterodactyl-entrypoint.sh` performs architecture validation, creates writable directories, seeds SteamCMD, configures FEX and XDG paths, derives the game port, prints a banner, executes an FEX guest preflight, launches an optional helper, and starts the upstream manager with `cd /app && python -m src.server_manager`.

The upstream manager currently:

1. Loads configuration from environment-backed YAML.
2. Optionally performs SteamCMD update logic.
3. Regenerates `PalWorldSettings.ini` and `Engine.ini`.
4. Starts `PalServer.sh` through `FEXBash -c`.
5. Verifies process stability and REST readiness.
6. Starts monitoring, config watching, and version checks.
7. Uses REST first and then process-group termination during an orderly stop.

## 5. FEX flow

The entrypoint discovers the first direct child directory under `/opt/fex-rootfs`, exports it as `FEX_ROOTFS`, writes `/home/container/.fex-emu/Config.json`, redirects FEX config/data/cache paths to the persistent volume, and runs:

```bash
FEXBash -c 'printf "FEX guest bootstrap OK\n"'
```

The upstream process manager then builds the game command and launches it as `FEXBash -c <quoted PalServer command>`. `FEX_ROOTFS_PATH` is not used as the RootFS selector.

Audit concern: selecting the first directory is not deterministic if more than one RootFS exists. Detection must be deterministic and must reject empty or incomplete roots.

## 6. Port flow

The current intended flow is:

```text
Primary allocation -> injected SERVER_PORT -> GAME_PORT
  -> ADDITIONAL_SERVER_OPTIONS contains -port=<GAME_PORT>
  -> PUBLIC_PORT=<GAME_PORT>
```

`QUERY_PORT` is a separate user-editable Egg variable with an extra-allocation description and defaults to `27018`. REST `8212/TCP` and RCON `25575/TCP` are hidden/internal Egg settings and do not require allocations.

Audit concerns:

- `SERVER_PORT` currently falls back to `8211` instead of failing when the Pterodactyl injection is missing.
- A user can place a second `-port` option in `ADDITIONAL_SERVER_OPTIONS`.
- `QUERY_PORT` is validated by the upstream manager but not by the entrypoint before the summary.
- The banner does not print the requested allocation IP plus port or an explicit `PublicPort synchronized` line.

## 7. Steam flow

Initial installation uses native ARM64 DepotDownloader. Runtime updates use the seeded x86 SteamCMD through FEX. The upstream SteamCMD client performs a warm-up/self-update check, hashes the launcher before and after a failed warm-up, and refuses to proceed if a failed update modified the launcher.

`USE_AUTH=false` is present in the Egg and overrides the upstream default of `true`. This is required to avoid the observed `Invalid AppTicket` disconnects on the current ARM64/FEX backend.

Audit concerns:

- SteamCMD is downloaded from a mutable URL without a checksum during image build.
- The base image and final custom image references use mutable `latest` tags.
- The Egg exposes `UPDATE_ON_START=true`, but the audited upstream manager skips SteamCMD when `PalServer.sh` exists unless `FORCE_UPDATE=true`; the displayed UX and actual update semantics need a dedicated integration test.

## 8. Configuration flow

Egg variables are injected into the upstream environment-backed `config/default.yaml`. The manager writes `PalWorldSettings.ini` and `Engine.ini` on startup. A local helper attempts to preserve manual `PalWorldSettings.ini` edits by copying the file before manager startup and restoring it after a fixed two-second delay.

Audit concerns:

- The fixed-delay restore is a race with manager generation.
- The backup is stored in persistent `/home/container/tmp`; lifecycle and stale-backup behavior are not explicit.
- Restoring the entire INI can discard newly introduced upstream defaults.
- The helper catches broad exceptions silently for REST and Discord operations, reducing observability.
- The helper uses `change-me-now` as an internal fallback when `ADMIN_PASSWORD` is absent.

The preservation behavior is production-sensitive and must not be removed casually. Any replacement must be transactional and regression-tested against real manager generation.

## 9. Shutdown flow

The Egg stop command is `^C`. The upstream manager has orderly shutdown behavior through REST and process-group signals. However, with quiet monitoring enabled, the local entrypoint starts the manager on the left side of a shell pipeline and the Python filter on the right:

```bash
python -m src.server_manager 2>&1 | python /scripts/log_filter.py
```

This means the entrypoint shell remains the pipeline coordinator and PID/signal ownership is no longer equivalent to `exec python -m src.server_manager`. The background helper is also not supervised by the manager. This is the highest baseline runtime risk found by the audit and requires focused signal tests before refactoring.

## 10. Mod-system integration points

The safest integration boundary is after writable paths, ports, and FEX are configured but before the upstream manager is started:

```text
prepare writable paths
-> configure ports/FEX
-> palmodctl scan
-> static validation
-> backup-if-needed
-> transactional deployment
-> UE4SS preflight when required
-> start the unchanged manager path
```

Additional integration points:

- Docker build: copy the stdlib-only `palmodctl` runtime and pinned metadata.
- Egg: add disabled-by-default feature flags using Hydrodactyl string validation.
- Persistent volume: make `/home/container/mods` the source of truth and `/home/container/backups/mod-changes` the backup target.
- FEX launch: apply x86_64 `LD_PRELOAD` only inside the guest command. This requires a narrow, tested hook; a global ARM64 environment preload is forbidden.
- Health: expose `palmodctl status` without replacing the existing process/REST health model.

Because the PalServer command is built inside the upstream package, UE4SS guest-only injection cannot be made robust merely by exporting `LD_PRELOAD` in the ARM64 entrypoint. A controlled adapter or upstream-compatible command hook must be proven first.

## 11. Risks

| Priority | Risk | Consequence | Initial control |
| --- | --- | --- | --- |
| Critical | UE4SS can change player GUID/identity | Character/save mismatch | Feature flag off, mandatory backup, manual GUID gate |
| High | Log pipeline weakens signal propagation | Ungraceful stop/save loss | Signal regression test and supervised wrapper |
| High | Mutable upstream/base tags | Unreviewed behavior changes | Record digest/version and pin where feasible |
| High | Manager source not vendored | Local tests cannot prove runtime behavior | Contract tests against a pinned image |
| High | Whole-file INI restore race | Lost settings or stale config | Transactional preservation tests |
| High | Native C++ mods are arbitrary code | Full server-user compromise | ELF x86_64 validation, explicit opt-in/warning |
| Medium | First-directory RootFS selection | Wrong or nondeterministic guest | Deterministic validated selection |
| Medium | CI path filters omit helper/Egg changes | Stale image published | Expand paths and run tests before build |
| Medium | Downloads lack checksums/digests | Supply-chain drift | Pin artifacts and verify SHA256 |
| Medium | Log filter suppressions may hide evidence | Harder incident diagnosis | Debug/raw mode and tested allowlist |

## 12. Code and behavior to preserve

The following behavior is the protected baseline and should remain intact until a test demonstrates an equivalent or safer replacement:

- Bypass of the upstream `/entrypoint.sh`.
- Direct manager entry path: `cd /app && python -m src.server_manager`.
- `/home/container` as the only persistent/mutable root.
- Native ARM64 DepotDownloader installer for Linux x86_64 App ID `2394010`.
- SteamCMD seed in `/home/container/.steamcmd` and upstream self-update safeguards.
- `FEX_ROOTFS` discovery/configuration and FEX guest bootstrap preflight.
- Primary port derivation from Pterodactyl `SERVER_PORT` and `PUBLIC_PORT` synchronization.
- Separate `QUERY_PORT` allocation.
- Internal-only REST and RCON defaults.
- `USE_AUTH=false` default.
- Hydrodactyl string-based booleans and absence of reserved Egg variables.
- Existing saves, `Pal/Saved`, configs, backups, and user files during install/update.
- Existing INI-preservation intent until a safer tested implementation replaces it.
- Upstream manager ownership of update, generation, monitoring, RCON/REST, and PalServer lifecycle.

## 13. Technical debt

- No dedicated mod subsystem, inventory, quarantine, backup, rollback, or deployment tests.
- No `mind/TEST_MATRIX.md` at the audited commit.
- Egg validator does not enforce all required invariants and treats some safety failures as warnings.
- Shell validation only covers top-level `*.sh` files.
- No unit tests for ports, RootFS detection, signals, log filtering, helper behavior, or installer preservation.
- CI only rebuilds for Dockerfile, entrypoint, or workflow changes; copied Python helpers are omitted.
- CI builds and pushes without running repository validation/tests first.
- No pinned base-image digest, SteamCMD checksum, or build provenance metadata.
- Dockerfile switches to `USER root` and never declares a non-root final user; Wings may override it, but standalone behavior is root.
- RootFS detection is nondeterministic.
- `is_true()` is not centralized; boolean parsing is inconsistent and exact-string based.
- README is an old patch note rather than the project entry documentation.
- Requested security, backup, rollback, mods, and UE4SS documents are absent.
- The test named `test_ini_preservation.py` is a standalone simulation rather than a unit test of production code.
- No `.gitignore` rule prevents Python bytecode from dirtying the worktree.

## 14. Phased implementation plan

1. Preserve this audit, baseline hashes, decisions, issues, and test matrix.
2. Strengthen static validation and CI without changing runtime behavior.
3. Refactor entrypoint into small functions and add tests for ports, FEX selection, redaction, and signal handling.
4. Introduce a stdlib-only `palmodctl` with scan/list/validate/doctor/status and no deployment side effects.
5. Add deterministic inventory, state, quarantine, and safe mode.
6. Implement transactional Patch Pak deployment, backup-on-change, retention, and explicit rollback.
7. Add a pinned UE4SS Linux payload and metadata only after verifying a primary-source artifact and checksum.
8. Test UE4SS with no mods and complete the manual Player GUID/save gate.
9. Add Lua deployment and a minimal Hello World procedure.
10. Add Blueprint deployment with explicit loader/hook availability checks.
11. Add Linux x86_64 ELF `.so` validation/deployment and reject Windows DLLs.
12. Test coexistence, restart, shutdown, update, rollback, existing characters, and save integrity.
13. Finalize Egg UX, docs, image metadata, and release gates.

All UE4SS-dependent categories remain `EXPERIMENTAL` until the manual ARM64/FEX test matrix is completed. Local static tests alone cannot promote them to `SUPPORTED`.
