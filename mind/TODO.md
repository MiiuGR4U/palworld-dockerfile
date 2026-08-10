# Task Tracking — Palworld ARM64 Evolution

Last updated: 2026-08-10

## Completed

- [x] Phase 0: capture clean baseline commit, file inventory, hashes, and existing test results.
- [x] Phase 1: audit tree, installer, runtime, FEX, networking, Steam, config, shutdown, integration points, risks, protected behavior, and debt.
- [x] Phase 2: update project memory and create the explicit test matrix.
- [x] Phase 3: strengthen Egg/shell/Python validation and make CI run it.
- [x] Phase 4: refactor entrypoint without changing the manager path or vanilla launch options.

## In progress

- [ ] Phase 9: complete manual Player GUID/save baseline and UE4SS comparison on ARM64.

## Planned implementation

- [x] Phase 5: persistent mod directories and static `palmodctl` operations.
- [x] Phase 6: transactional Patch Pak deployment.
- [x] Phase 7: Safe Mode, inventory, backup retention, quarantine, and explicit rollback.
- [x] Phase 8: pin/checksum UE4SS Linux and implement guest-only preload routing.
- [ ] Phase 10: run Lua Hello World on ARM64 (structural implementation PASS).
- [ ] Phase 11: run Blueprint minimal on ARM64 (structural implementation PASS).
- [ ] Phase 12: run C++ Linux `.so` Hello World on ARM64 (ELF/deployment tests PASS).
- [ ] Phase 13: run all four simultaneously on ARM64 (single-transaction test PASS).
- [x] Phase 14: add safe Egg flags, ordering, descriptions, and validation.
- [x] Phase 15: complete repository documentation; runtime results remain explicitly pending.

## Release blockers

- [ ] Prove signal propagation and graceful shutdown with quiet logs enabled.
- [ ] Replace or prove safe the fixed-delay INI preservation behavior.
- [x] Pin the Supersunho base digest and checksum UE4SS/DepotDownloader artifacts.
- [ ] Complete ARM64/FEX runtime matrix on a non-production copy of real saves.
- [ ] Pass existing-character GUID, guild, inventory, base, restart, and save-integrity gates.
