# Memory & CPU Diagnostics

Pterodactyl/Wings measures RAM and CPU through Docker `cgroups`. Because FEX-Emu maps a huge virtual memory space (up to 8GB+) for emulation, tools like `htop` or `ps` might report high VSZ, but the actual physical RAM used is Resident Set Size (RSS).

However, the metric that Pterodactyl shows on the panel is exactly what Docker reports in `/sys/fs/cgroup/memory.current` (or `memory.usage_in_bytes` on older cgroups). 

## Discrepancies
If Pterodactyl reports 1-2GB, but Palworld is known to use 8GB, there are a few explanations:
1. **FEX Memory Sharing**: FEX handles page faults and mmaps in a way that the kernel might classify as shared memory or page cache, rather than anonymous RSS belonging directly to the process.
2. **Cgroup V1 vs V2**: Different cgroup versions account for page cache differently.

## Diagnostic Tool
We added a built-in command to the interactive console:
- `/memory`

This command outputs:
1. The raw `memory.current` value from the container's cgroup (This is exactly what Pterodactyl sees).
2. The raw `memory.max` value.
3. A process tree with the actual RSS (Resident Set Size) of every running process inside the container.

You can use this to prove that PalServer is running within the same cgroup and identify where the memory is being allocated. No artificial multiplier is used; Pterodactyl is receiving the exact, unmasked cgroup metric.
