# ARM64 & FEX-Emu Technical Reference

## FEX-Emu Architecture on ARM64

FEX-Emu is a high-performance x86/x86_64 emulator designed specifically for Linux ARM64 hosts. Unlike traditional binary translation layers, FEX utilizes JIT compilation and static register mapping to achieve low-overhead execution for x86_64 binaries.

```text
ARM64 Host Kernel
   └─ Container (Non-root user: 999)
       └─ FEX-Emu
           └─ RootFS: /opt/fex-rootfs/Ubuntu_24_04
               └─ PalServer-Linux-Shipping (x86_64)
```

## Critical Configuration Options

### 1. `FEX_ROOTFS`
- **Path**: Pointed to `/opt/fex-rootfs/Ubuntu_24_04`.
- **Note**: `FEX_ROOTFS` is the authoritative environment variable consumed by `FEXBash` and `FEX`. Do not use `FEX_ROOTFS_PATH`.

### 2. User Storage Redirection
All FEX configuration and JIT cache files are redirected to the writable Pterodactyl volume:
- `FEX_APP_CONFIG_LOCATION=/home/container/.fex-emu/`
- `FEX_APP_DATA_LOCATION=/home/container/.fex-emu/`
- `FEX_APP_CACHE_LOCATION=/home/container/.cache/fex-emu/`

### 3. Performance Tuning Options

```bash
export FEX_ENABLE_JIT_CACHE=1
export FEX_JIT_CACHE_SIZE=1024
export FEX_ENABLE_VIXL_SIMULATOR=0
export FEX_ENABLE_VIXL_DISASSEMBLER=0
export FEX_ENABLE_LAZY_MEMORY_DELETION=1
export FEX_ENABLE_STATIC_REGISTER_ALLOCATION=1
```

## Steam Authentication Limitation (`USE_AUTH=false`)

When running `PalServer-Linux-Shipping` under FEX emulation:
- Steam API ticket verification (`bUseAuth=True`) communicates with native `steamclient.so` via IPC.
- Inter-process ticket validation under emulation frequently causes client handshakes to fail with `kicked by AUTH. Error: Invalid AppTicket`.
- Setting `USE_AUTH=false` disables ticket authorization while maintaining password protection via `SERVER_PASSWORD`.
