#!/usr/bin/env python3
"""
ptero_manager.py — Pterodactyl Primary Manager Wrapper for Palworld ARM64
Handles SteamCMD updates, Signal propagation for graceful shutdown, and a robust Interactive Console.
"""

import sys
import os
import subprocess
import signal
import time
import json
import threading
from urllib.request import Request, urlopen
import shutil
import re
from datetime import datetime

# Environment Variables
SERVER_ROOT = os.getenv("SERVER_ROOT", "/home/container")
GRACEFUL_SHUTDOWN_TIMEOUT = int(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT", "120"))

REST_PORT = os.getenv("REST_API_PORT", "8212")
REST_HOST = os.getenv("REST_API_HOST", "localhost")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-now")
CONSOLE_LANG = os.getenv("CONSOLE_LANG", "pt").lower()
BASE_URL = f"http://{REST_HOST}:{REST_PORT}/v1/api"

import base64

def is_truthy(val) -> bool:
    if val is None:
        return False
    return str(val).strip().lower() in ("true", "1", "yes", "on")

def check_update_enabled() -> bool:
    force_file = os.path.join(SERVER_ROOT, "tmp", ".force_update_next_boot")
    if os.path.exists(force_file):
        try:
            os.remove(force_file)
        except OSError:
            pass
        print("[UPDATE] Force update marker detected (.force_update_next_boot). Updating Palworld...", flush=True)
        return True

    if is_truthy(os.getenv("FORCE_UPDATE")):
        return True
    if is_truthy(os.getenv("AUTO_UPDATE")):
        return True
    if os.getenv("UPDATE_ON_START") is not None:
        return is_truthy(os.getenv("UPDATE_ON_START"))
    return True

UPDATE_ON_START = check_update_enabled()
UPDATE_ACTUALLY_DOWNLOADED = False
BACKUP_BEFORE_UPDATE = is_truthy(os.getenv("BACKUP_BEFORE_UPDATE", "true"))
_qm = os.getenv("QUIET_MONITORING")
QUIET_MONITORING = True if _qm is None or _qm.strip() == "" else is_truthy(_qm)

try:
    import log_filter
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import log_filter
    except ImportError:
        log_filter = None

# --- API Integration ---
def get_auth_header() -> dict:
    auth_str = f"admin:{ADMIN_PASSWORD}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/json",
        "User-Agent": "PteroManager/1.0"
    }

def api_request(endpoint: str, method: str = "GET", data: dict = None):
    url = f"{BASE_URL}{endpoint}"
    headers = get_auth_header()
    body_bytes = json.dumps(data).encode("utf-8") if data else None

    req = Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urlopen(req, timeout=5) as resp:
            resp_body = resp.read().decode("utf-8")
            if resp_body:
                return True, json.loads(resp_body)
            return True, {}
    except Exception as e:
        return False, str(e)


# --- SteamCMD Update ---
def backup_before_update():
    if not BACKUP_BEFORE_UPDATE:
        return
    saved_dir = os.path.join(SERVER_ROOT, "Pal", "Saved")
    if not os.path.exists(saved_dir):
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(SERVER_ROOT, "backups", f"pre-update-{timestamp}")
    print(f"[UPDATE] Creating pre-update backup at {backup_path}...", flush=True)
    try:
        shutil.copytree(saved_dir, backup_path, dirs_exist_ok=True)
        print("[UPDATE] Backup completed successfully.", flush=True)
    except Exception as e:
        print(f"[UPDATE] WARNING: Backup failed: {e}", flush=True)

def run_steamcmd_update() -> bool:
    print("[UPDATE] Checking Palworld server version...", flush=True)
    print(f"[UPDATE] Target installation: {SERVER_ROOT}", flush=True)
    print("[UPDATE] AppID: 2394010", flush=True)

    backup_before_update()

    depot_downloader = "/opt/depotdownloader/DepotDownloader"
    beta_id = os.getenv("SRCDS_BETAID", "").strip()
    beta_pass = os.getenv("SRCDS_BETAPASS", "").strip()
    downloaded_any_bytes = False

    # 1. Prefer native ARM64 DepotDownloader (direct, zero emulation, guaranteed to download Palworld binaries)
    if os.path.exists(depot_downloader) and os.access(depot_downloader, os.X_OK):
        cmd = [
            depot_downloader,
            "-app", "2394010",
            "-os", "linux",
            "-osarch", "64",
            "-dir", SERVER_ROOT
        ]
        if is_truthy(os.getenv("STEAMCMD_VALIDATE", "true")):
            cmd.append("-validate")
        if beta_id:
            cmd.extend(["-branch", beta_id])
        if beta_pass:
            cmd.extend(["-branchpassword", beta_pass])

        print("[UPDATE] Running native ARM64 DepotDownloader...", flush=True)
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            last_progress_time = 0.0
            if proc.stdout:
                for line in proc.stdout:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    if "Total downloaded:" in line_str:
                        m = re.search(r"Total downloaded:\s*(\d+)\s*bytes", line_str)
                        if m and int(m.group(1)) > 0:
                            downloaded_any_bytes = True
                    elif "Downloaded" in line_str and "bytes" in line_str:
                        m = re.search(r"Downloaded\s+(\d+)\s+bytes", line_str)
                        if m and int(m.group(1)) > 0:
                            downloaded_any_bytes = True

                    if "%" in line_str:
                        now = time.time()
                        if now - last_progress_time >= 2.0:
                            last_progress_time = now
                            print(f"[UPDATER] {line_str}", flush=True)
                    else:
                        print(f"[UPDATER] {line_str}", flush=True)
            proc.wait()
            if proc.returncode == 0:
                if downloaded_any_bytes:
                    print("[UPDATE] Palworld files updated successfully via native updater.", flush=True)
                else:
                    print("[UPDATE] Palworld server files are already up-to-date (0 bytes downloaded).", flush=True)
                return downloaded_any_bytes
            else:
                print(f"[UPDATE] DepotDownloader returned code {proc.returncode}. Trying SteamCMD fallback...", flush=True)
        except Exception as e:
            print(f"[UPDATE] DepotDownloader failed: {e}. Trying SteamCMD fallback...", flush=True)

    # 2. Fallback to SteamCMD under FEX
    steamcmd_sh = os.path.join(SERVER_ROOT, ".steamcmd", "steamcmd.sh")
    if not os.path.exists(steamcmd_sh):
        print(f"[UPDATE] SteamCMD not found at {steamcmd_sh}. Skipping update.", flush=True)
        return False

    validate_arg = " validate" if is_truthy(os.getenv("STEAMCMD_VALIDATE", "true")) else ""
    beta_arg = f" -beta {beta_id}" if beta_id else ""
    if beta_arg and beta_pass:
        beta_arg += f" -betapassword {beta_pass}"

    cmd_str = f'"{steamcmd_sh}" +@sSteamCmdForcePlatformType linux +@sSteamCmdForcePlatformBitness 64 +force_install_dir "{SERVER_ROOT}" +login anonymous +app_update 2394010{beta_arg}{validate_arg} +quit'
    cmd = ["FEXBash", "-c", cmd_str]

    print("[UPDATE] Running SteamCMD update in real-time...", flush=True)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        last_progress_time = 0.0
        steamcmd_updated = False
        if proc.stdout:
            for line in proc.stdout:
                line_str = line.strip()
                if not line_str:
                    continue
                if "success! app '2394010' fully installed" in line_str.lower():
                    steamcmd_updated = True
                if "progress:" in line_str.lower():
                    now = time.time()
                    if now - last_progress_time >= 2.0:
                        last_progress_time = now
                        print(f"[STEAMCMD] {line_str}", flush=True)
                else:
                    print(f"[STEAMCMD] {line_str}", flush=True)
        proc.wait()
        if proc.returncode == 0:
            print("[UPDATE] SteamCMD update completed successfully.", flush=True)
            return steamcmd_updated
        else:
            print(f"[UPDATE] SteamCMD update finished with exit code {proc.returncode}.", flush=True)
            return False
    except Exception as e:
        print(f"[UPDATE] SteamCMD update execution error: {e}", flush=True)
        return False


def fix_steamclient():
    """
    Palworld dedicated server on Linux requires steamclient.so in ~/.steam/sdk64/
    Otherwise it will crash with S_API FAIL.
    """
    print("[BOOT] Verifying steamclient.so paths...", flush=True)
    steamcmd_dir = os.path.join(SERVER_ROOT, ".steamcmd")
    source_client = os.path.join(steamcmd_dir, "linux64", "steamclient.so")
    
    sdk64_dir = os.path.join(SERVER_ROOT, ".steam", "sdk64")
    target_client = os.path.join(sdk64_dir, "steamclient.so")
    
    bin_target = os.path.join(SERVER_ROOT, "Pal", "Binaries", "Linux", "steamclient.so")

    if os.path.exists(source_client):
        os.makedirs(sdk64_dir, exist_ok=True)
        try:
            shutil.copy2(source_client, target_client)
            print(f"[BOOT] Copied steamclient.so to {target_client}", flush=True)
        except Exception as e:
            print(f"[BOOT] Failed to copy steamclient.so to sdk64: {e}", flush=True)
            
        try:
            if os.path.exists(os.path.dirname(bin_target)):
                shutil.copy2(source_client, bin_target)
                print(f"[BOOT] Copied steamclient.so to {bin_target}", flush=True)
        except Exception as e:
            print(f"[BOOT] Failed to copy steamclient.so to Binaries: {e}", flush=True)
    else:
        print(f"[BOOT] WARNING: Source steamclient.so not found at {source_client}", flush=True)


def configure_palworld_ini(file_path: str, log_action: bool = True) -> bool:
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if not content.strip() or "OptionSettings=(" not in content:
            return False

        modified = False

        # 1. bIsUseRestAPI=True
        if "bIsUseRestAPI=" in content:
            if "bIsUseRestAPI=True" not in content:
                content = re.sub(r"bIsUseRestAPI=\w+", "bIsUseRestAPI=True", content)
                modified = True
        else:
            content = content.replace("OptionSettings=(", "OptionSettings=(bIsUseRestAPI=True,")
            modified = True

        # 2. RESTAPIPort
        if "RESTAPIPort=" in content:
            if f"RESTAPIPort={REST_PORT}" not in content:
                content = re.sub(r"RESTAPIPort=\d+", f"RESTAPIPort={REST_PORT}", content)
                modified = True
        else:
            content = content.replace("OptionSettings=(", f"OptionSettings=(RESTAPIPort={REST_PORT},")
            modified = True

        # 3. bUseAuth (Must be False on ARM64/FEX to prevent Steam ticket failure / connection timeouts)
        auth_bool = is_truthy(os.getenv("USE_AUTH", "false"))
        auth_str = "True" if auth_bool else "False"
        if "bUseAuth=" in content:
            if f"bUseAuth={auth_str}" not in content:
                content = re.sub(r"bUseAuth=\w+", f"bUseAuth={auth_str}", content)
                modified = True
        else:
            content = content.replace("OptionSettings=(", f"OptionSettings=(bUseAuth={auth_str},")
            modified = True

        # 4. PublicPort (Ensure game port matches primary allocation)
        game_port = os.getenv("SERVER_PORT", "25565")
        if "PublicPort=" in content:
            if f"PublicPort={game_port}" not in content:
                content = re.sub(r"PublicPort=\d+", f"PublicPort={game_port}", content)
                modified = True
        else:
            content = content.replace("OptionSettings=(", f"OptionSettings=(PublicPort={game_port},")
            modified = True

        # 5. AdminPassword
        if ADMIN_PASSWORD and ADMIN_PASSWORD != "change-me-now":
            if f'AdminPassword="{ADMIN_PASSWORD}"' not in content:
                if 'AdminPassword=' in content:
                    content = re.sub(r'AdminPassword="[^"]*"', f'AdminPassword="{ADMIN_PASSWORD}"', content)
                    modified = True

        if modified:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            if log_action:
                print(f"[BOOT] Enforced settings in {os.path.basename(file_path)} (REST API=True, port={game_port}, bUseAuth={auth_str})", flush=True)
            return True
        return False
    except Exception as e:
        if log_action:
            print(f"[BOOT] Warning: Could not configure {file_path}: {e}", flush=True)
        return False


def enforce_all_ini_files():
    """
    Applies critical network and REST settings quietly to default and backup templates.
    """
    default_ini = os.path.join(SERVER_ROOT, "DefaultPalWorldSettings.ini")
    server_ini = os.path.join(SERVER_ROOT, "Pal", "Saved", "Config", "LinuxServer", "PalWorldSettings.ini")
    bak_ini = os.path.join(SERVER_ROOT, "tmp", "PalWorldSettings.ini.userbak")

    configure_palworld_ini(default_ini, log_action=False)
    configure_palworld_ini(server_ini, log_action=False)
    configure_palworld_ini(bak_ini, log_action=False)


def handle_post_config_generation():
    """
    Called the exact moment upstream manager finishes generating PalWorldSettings.ini.
    If no new game files were downloaded, restores user's custom settings instead of resetting to defaults.
    """
    global UPDATE_ACTUALLY_DOWNLOADED
    active_ini = os.path.join(SERVER_ROOT, "Pal", "Saved", "Config", "LinuxServer", "PalWorldSettings.ini")
    preboot_ini = os.path.join(SERVER_ROOT, "tmp", "PalWorldSettings.ini.preboot")

    if not UPDATE_ACTUALLY_DOWNLOADED and os.path.exists(preboot_ini) and os.path.getsize(preboot_ini) > 0:
        try:
            shutil.copy2(preboot_ini, active_ini)
            configure_palworld_ini(active_ini, log_action=False)
            print("[CONFIG] Servidor já atualizado. Configurações personalizadas preservadas com sucesso!", flush=True)
        except Exception as e:
            print(f"[CONFIG] Aviso ao restaurar configurações personalizadas: {e}", flush=True)
    else:
        # An actual update was downloaded or fresh install: ensure critical settings
        configure_palworld_ini(active_ini, log_action=False)
        if UPDATE_ACTUALLY_DOWNLOADED:
            print("[CONFIG] Atualização aplicada. Configurações atualizadas para a nova versão!", flush=True)


def detect_game_version() -> str:
    """
    Detects the installed Palworld version from files, manifests, or defaults to current release.
    """
    cache_file = os.path.join(SERVER_ROOT, "tmp", "palworld_version.txt")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass

    bin_path = os.path.join(SERVER_ROOT, "Pal", "Binaries", "Linux", "PalServer-Linux-Shipping")
    if os.path.exists(bin_path):
        try:
            with open(bin_path, "rb") as f:
                chunk = f.read(8 * 1024 * 1024)
                matches = re.findall(rb"(?:v)?(1\.0\.\d+\.\d+|0\.\d+\.\d+\.\d+)", chunk)
                if matches:
                    return matches[-1].decode("ascii", errors="ignore")
        except Exception:
            pass

    return "1.0.4.102642"


def start_version_and_readiness_reporter():
    """
    Polls the REST API once the server starts.
    When ready, prints the exact game version and announces connection readiness.
    """
    game_port = os.getenv("SERVER_PORT", "25565")
    def _worker():
        time.sleep(4)
        announced = False
        for _ in range(60):
            try:
                success, data = api_request("/info")
                if success and isinstance(data, dict):
                    ver = data.get("version", "").strip()
                    server_name = data.get("servername", "").strip()
                    if ver and not announced:
                        try:
                            v_file = os.path.join(SERVER_ROOT, "tmp", "palworld_version.txt")
                            with open(v_file, "w") as f:
                                f.write(ver)
                        except Exception:
                            pass
                        print(f"Game version is {ver}", flush=True)
                        print(f"[PALWORLD] Servidor pronto para conexões na porta {game_port}! Versão: {ver}", flush=True)
                        announced = True
                        break
            except Exception:
                pass
            time.sleep(2)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


# --- Traceback & Noise Suppression ---
def is_traceback_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False

    # Caret / underline lines from Python 3.11+: e.g. ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ or ~~~^^^~~~
    if set(s) <= {'^', '~', ' ', '|', '\t'}:
        return True

    # Traceback header & exception chaining
    if s.startswith("Traceback (most recent call last):") or \
       s.startswith("During handling of the above exception"):
        return True

    # Python stack frame lines: File "...", line 123, in ...
    if re.match(r'^File\s+"[^"]+",\s+line\s+\d+', s):
        return True

    # Asyncio / runpy / interpreter runtime frame expressions
    tb_tokens = (
        "asyncio.exceptions.CancelledError",
        "concurrent.futures._base.CancelledError",
        "asyncio.CancelledError",
        "KeyboardInterrupt",
        "exit_code = asyncio.run",
        "await asyncio.sleep",
        "return runner.run",
        "return await future",
        "run_until_complete",
        "_run_module_as_main",
        "_run_code",
        "wait_for_api_ready",
        "raise KeyboardInterrupt()",
        "return future.result()",
        "runner.run(main)",
        "asyncio/runners.py",
        "asyncio/tasks.py",
        "asyncio/base_events.py",
        "<frozen runpy>",
        "<frozen importlib",
        "self._sslobj.shutdown()",
        "Task was destroyed but it is pending",
        "source_traceback:",
        "Exception ignored in:",
        "loop.close()",
    )
    return any(token in s for token in tb_tokens)


# --- Manager Process ---
class ManagerWrapper:
    def __init__(self):
        self.process = None
        self.shutdown_requested = False
        self._shutdown_executing = False
        self.output_thread = None
        self.in_traceback = False

    def _stream_output(self):
        last_printed = None
        if not self.process or not self.process.stdout:
            return

        for raw_line in self.process.stdout:
            line = raw_line.strip()
            if not line:
                continue

            # Detect server shutdown from upstream logs
            if "Server stopped successfully" in line or "Backup cleanup" in line:
                self.shutdown_requested = True

            # Track whether we entered a traceback block
            if "Traceback (most recent call last):" in line or \
               "During handling of the above exception" in line:
                self.in_traceback = True

            # When shutdown was requested or when in a traceback, suppress tracebacks and asyncio noise
            if self.shutdown_requested or self.in_traceback or is_traceback_line(line):
                if is_traceback_line(line):
                    if any(exc in line for exc in ("KeyboardInterrupt", "CancelledError")):
                        self.in_traceback = False
                    continue
                if self.in_traceback:
                    if line.startswith(("[", "🟢", "🎮", "✨", "👋", "🚀", "✅", "🛡️", "🌐", "⚙️", "🛠️", "📥", "✓", "👁️", "👥", "📊", "🔔", "💤", "📦", "🛑", "🧹")):
                        self.in_traceback = False
                    else:
                        if any(exc in line for exc in ("KeyboardInterrupt", "CancelledError", "Error", "Exception")):
                            self.in_traceback = False
                        continue

            # Apply suppression patterns unless raw logs explicitly requested
            if (QUIET_MONITORING or CONSOLE_LANG != "raw") and log_filter:
                suppress = False
                for pat in log_filter.SUPPRESS_PATTERNS:
                    if pat.search(line):
                        suppress = True
                        break
                if suppress:
                    continue

            formatted = log_filter.format_line(line) if log_filter else line
            if not formatted:
                continue
            if formatted == last_printed:
                continue
            last_printed = formatted

            print(formatted, flush=True)

            # Intercept upstream config generation: preserve custom settings if no update occurred!
            if any(marker in line for marker in (
                "Configurações de jogo (PalWorldSettings.ini) aplicadas com sucesso",
                "PalWorldSettings.ini file generated successfully",
                "Server settings file generated successfully"
            )):
                handle_post_config_generation()

            # Ensure Pterodactyl startup.done matcher is satisfied as soon as the server reports ready
            if "Server started successfully and is stable" in line:
                print("Palworld server started successfully!", flush=True)

    def start(self, args):
        print("[BOOT] Starting upstream manager (src.server_manager)...", flush=True)
        cmd = ["python", "-u", "-m", "src.server_manager"] + args
        self.process = subprocess.Popen(
            cmd,
            cwd="/app",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        self.output_thread = threading.Thread(target=self._stream_output, daemon=True)
        self.output_thread.start()

    def shutdown(self):
        if self._shutdown_executing:
            return
        self._shutdown_executing = True
        self.shutdown_requested = True
        
        # Ignore further interrupt signals so graceful shutdown is never aborted midway
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        except Exception:
            pass

        print("\n[SHUTDOWN] Stop signal received", flush=True)
        print("[SHUTDOWN] Preparing graceful shutdown", flush=True)
        
        # 1. Request Save via API
        print("[SHUTDOWN] Requesting world save...", flush=True)
        success, err = api_request("/save", method="POST")
        if success:
            print("[SHUTDOWN] Save command sent successfully.", flush=True)
            time.sleep(3) # Wait for save to flush
        else:
            if "Connection refused" in str(err) or "111" in str(err):
                print("[SHUTDOWN] World save skipped (server was still initializing).", flush=True)
            else:
                print(f"[SHUTDOWN] Save command failed: {err}", flush=True)

        # 2. Send SIGINT to upstream manager
        if self.process and self.process.poll() is None:
            print("[SHUTDOWN] Sending termination signal to Manager...", flush=True)
            self.process.send_signal(signal.SIGINT)

            print(f"[SHUTDOWN] Waiting up to {GRACEFUL_SHUTDOWN_TIMEOUT} seconds for PalServer to exit...", flush=True)
            try:
                self.process.wait(timeout=GRACEFUL_SHUTDOWN_TIMEOUT)
                print("[SHUTDOWN] PalServer and Manager exited gracefully.", flush=True)
            except subprocess.TimeoutExpired:
                print(f"[SHUTDOWN] Timeout ({GRACEFUL_SHUTDOWN_TIMEOUT}s) reached! Forcing KILL.", flush=True)
                self.process.kill()
                self.process.wait()

        if self.output_thread and self.output_thread.is_alive():
            self.output_thread.join(timeout=2)
        
        print("[SHUTDOWN] Cleaning up and exiting. Shutdown complete.", flush=True)
        sys.exit(0)

# --- Diagnostic Commands ---
def get_memory_info():
    try:
        with open("/sys/fs/cgroup/memory.current", "r") as f:
            mem_current = int(f.read().strip())
    except Exception:
        mem_current = -1

    try:
        with open("/sys/fs/cgroup/memory.max", "r") as f:
            val = f.read().strip()
            mem_max = int(val) if val != "max" else "Unlimited"
    except Exception:
        mem_max = "Unknown"

    print("## Memory Diagnostics", flush=True)
    if mem_current >= 0:
        print(f"Container Memory (memory.current): {mem_current / (1024*1024):.2f} MB", flush=True)
    else:
        print("Container Memory: N/A", flush=True)
    
    print(f"Container Max (memory.max): {mem_max if isinstance(mem_max, str) else f'{mem_max / (1024*1024):.2f} MB'}", flush=True)

    # Use ps to gather RSS
    try:
        out = subprocess.check_output(["ps", "-e", "-o", "pid,ppid,rss,comm"])
        print("\nPID\tPPID\tRSS (MB)\tCOMMAND", flush=True)
        for line in out.decode().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 4:
                pid, ppid, rss = parts[0], parts[1], parts[2]
                cmd = " ".join(parts[3:])
                try:
                    rss_mb = int(rss) / 1024
                    print(f"{pid}\t{ppid}\t{rss_mb:.2f} MB\t{cmd}", flush=True)
                except ValueError:
                    print(line, flush=True)
    except Exception as e:
        print(f"Failed to get process list: {e}", flush=True)


# --- Command Router ---
def command_router(manager_wrapper):
    print("[CONSOLE] Interactive Command Router Started.", flush=True)
    print("[CONSOLE] Type /help for a list of commands.", flush=True)
    
    try:
        for line in sys.stdin:
            cmd_raw = line.strip()
            if not cmd_raw:
                continue
            
            print(f"[COMMAND] {cmd_raw}", flush=True)
            
            parts = cmd_raw.split(" ")
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd in ["/help", "/?", "help"]:
                print("## Internal Commands:", flush=True)
                print(" /status, /info      - Show server health and status", flush=True)
                print(" /save, /saveworld   - Force save the world", flush=True)
                print(" /say, /broadcast    - Send a message to all players", flush=True)
                print(" /players, /list     - List active players", flush=True)
                print(" /stop               - Gracefully stop the server", flush=True)
                print(" /update now         - Force update Palworld", flush=True)
                print(" /memory             - Show RAM diagnostics", flush=True)
                print(" /processes          - Show running processes", flush=True)
            
            elif cmd in ["/save", "/saveworld", "save", "saveworld"]:
                success, err = api_request("/save", method="POST")
                if success:
                    print("[RCON] World saved successfully.", flush=True)
                else:
                    print(f"[RCON] Save failed: {err}", flush=True)
                    
            elif cmd in ["/say", "/broadcast"]:
                msg = " ".join(args)
                if not msg:
                    print("Usage: /say <message>", flush=True)
                else:
                    success, err = api_request("/announce", method="POST", data={"message": msg})
                    if success:
                        print(f"[CHAT] Broadcast sent: {msg}", flush=True)
                    else:
                        print(f"[RCON] Broadcast failed: {err}", flush=True)
                        
            elif cmd in ["/players", "/list", "players", "list"]:
                success, data = api_request("/players")
                if success:
                    players = data.get("players", [])
                    print(f"## Active Players ({len(players)}):", flush=True)
                    for p in players:
                        name = p.get("name", "Unknown")
                        pid = p.get("account_name", "Unknown")
                        print(f"- {name} ({pid})", flush=True)
                else:
                    print(f"[RCON] Failed to get players: {data}", flush=True)
                    
            elif cmd in ["/status", "/info", "status", "info"]:
                success, data = api_request("/info")
                if success:
                    print(f"## Server Status", flush=True)
                    print(f"Version: {data.get('version', 'Unknown')}", flush=True)
                    print(f"Server Name: {data.get('servername', 'Unknown')}", flush=True)
                else:
                    print("[RCON] Server is unreachable or starting up.", flush=True)

            elif cmd in ["/stop", "stop"]:
                print("[CONSOLE] Manual stop requested.", flush=True)
                manager_wrapper.shutdown()
                break

            elif cmd in ["/memory", "memory"]:
                get_memory_info()

            elif cmd in ["/processes", "processes"]:
                os.system("ps -ef --forest")

            elif cmd == "/update":
                if len(args) > 0 and args[0] == "now":
                    print("[CONSOLE] Manual update requested.", flush=True)
                    force_file = os.path.join(SERVER_ROOT, "tmp", ".force_update_next_boot")
                    try:
                        os.makedirs(os.path.dirname(force_file), exist_ok=True)
                        with open(force_file, "w") as f:
                            f.write("1")
                    except Exception as e:
                        print(f"[UPDATE] Warning: Failed to set force update marker: {e}", flush=True)
                    print("[CONSOLE] Server marked to update Palworld on next boot. Shutting down gracefully...", flush=True)
                    manager_wrapper.shutdown()
                    break
                else:
                    print("Usage: /update now", flush=True)
                    
            elif cmd.startswith("/"):
                print(f"[CONSOLE] Unknown command: {cmd}", flush=True)
            else:
                print("[CONSOLE] Ignoring non-slash command. Use /help for internal commands.", flush=True)
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    wrapper = ManagerWrapper()

    # Handle Signals
    signal.signal(signal.SIGTERM, lambda s, f: wrapper.shutdown())
    signal.signal(signal.SIGINT, lambda s, f: wrapper.shutdown())

    # 0. Backup preboot settings to protect custom configs if server is already updated
    active_ini = os.path.join(SERVER_ROOT, "Pal", "Saved", "Config", "LinuxServer", "PalWorldSettings.ini")
    preboot_ini = os.path.join(SERVER_ROOT, "tmp", "PalWorldSettings.ini.preboot")
    if os.path.exists(active_ini) and os.path.getsize(active_ini) > 0:
        try:
            os.makedirs(os.path.dirname(preboot_ini), exist_ok=True)
            shutil.copy2(active_ini, preboot_ini)
        except Exception:
            pass

    # 1. Update Phase
    if UPDATE_ON_START:
        UPDATE_ACTUALLY_DOWNLOADED = run_steamcmd_update()

    # 1.5 Fix steamclient.so
    fix_steamclient()

    # 1.6 Configure and enforce INI settings (REST API, port, bUseAuth)
    enforce_all_ini_files()

    # 1.7 Announce installed game version immediately
    installed_ver = detect_game_version()
    print(f"Game version is {installed_ver}", flush=True)

    # 1.8 Start readiness and version confirmation reporter
    start_version_and_readiness_reporter()

    # 2. Start Manager
    wrapper.start(sys.argv[1:])

    # 3. Command Router
    # Run command router in a daemon thread so it keeps reading sys.stdin
    t_router = threading.Thread(target=command_router, args=(wrapper,), daemon=True)
    t_router.start()

    # 4. Wait for manager
    try:
        wrapper.process.wait()
    except KeyboardInterrupt:
        wrapper.shutdown()
    
    if wrapper.output_thread and wrapper.output_thread.is_alive():
        wrapper.output_thread.join(timeout=2)

    if wrapper.shutdown_requested or wrapper._shutdown_executing:
        print("[SHUTDOWN] Cleaning up and exiting. Shutdown complete.", flush=True)
        sys.exit(0)

    print("[WATCHDOG] Upstream manager process exited.", flush=True)
    sys.exit(wrapper.process.returncode if wrapper.process else 0)
