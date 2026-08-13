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
from datetime import datetime

# Environment Variables
SERVER_ROOT = os.getenv("SERVER_ROOT", "/home/container")
UPDATE_ON_START = os.getenv("UPDATE_ON_START", "true").lower() == "true"
BACKUP_BEFORE_UPDATE = os.getenv("BACKUP_BEFORE_UPDATE", "true").lower() == "true"
GRACEFUL_SHUTDOWN_TIMEOUT = int(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT", "120"))

REST_PORT = os.getenv("REST_API_PORT", "8212")
REST_HOST = os.getenv("REST_API_HOST", "localhost")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-now")
BASE_URL = f"http://{REST_HOST}:{REST_PORT}/v1/api"

import base64

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

def run_steamcmd_update():
    print("[UPDATE] Checking Palworld server version...", flush=True)
    print(f"[UPDATE] SteamCMD installation: {SERVER_ROOT}", flush=True)
    print("[UPDATE] AppID: 2394010", flush=True)

    backup_before_update()

    steamcmd_sh = os.path.join(SERVER_ROOT, ".steamcmd", "steamcmd.sh")
    if not os.path.exists(steamcmd_sh):
        print(f"[UPDATE] SteamCMD not found at {steamcmd_sh}. Skipping update.", flush=True)
        return

    cmd_str = f'"{steamcmd_sh}" +@sSteamCmdForcePlatformType linux +@sSteamCmdForcePlatformBitness 64 +force_install_dir "{SERVER_ROOT}" +login anonymous +app_update 2394010 validate +quit'
    cmd = ["FEXBash", "-c", cmd_str]

    print("[UPDATE] Running update... This may take a while.", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        if "Success! App '2394010' already up to date." in result.stdout:
            print("[UPDATE] Server is already up to date.", flush=True)
        else:
            print("[UPDATE] Update completed successfully.", flush=True)
    else:
        print(f"[UPDATE] SteamCMD update failed with exit code {result.returncode}.", flush=True)
        for line in result.stdout.splitlines()[-10:]:
            print(f"[STEAMCMD] {line}", flush=True)


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


# --- Manager Process ---
class ManagerWrapper:
    def __init__(self):
        self.process = None
        self.shutdown_requested = False

    def start(self, args):
        print("[BOOT] Starting upstream manager (src.server_manager)...", flush=True)
        cmd = ["python", "-u", "-m", "src.server_manager"] + args
        self.process = subprocess.Popen(cmd, cwd="/app")

    def shutdown(self):
        if self.shutdown_requested:
            return
        self.shutdown_requested = True
        
        print("\n[SHUTDOWN] Stop signal received", flush=True)
        print("[SHUTDOWN] Preparing graceful shutdown", flush=True)
        
        # 1. Request Save via API
        print("[SHUTDOWN] Requesting world save...", flush=True)
        success, err = api_request("/save", method="POST")
        if success:
            print("[SHUTDOWN] Save command sent successfully.", flush=True)
            time.sleep(3) # Wait for save to flush
        else:
            print(f"[SHUTDOWN] Save command failed or REST API not available: {err}", flush=True)

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
    
    for line in sys.stdin:
        cmd_raw = line.strip()
        if not cmd_raw:
            continue
        
        print(f"[COMMAND] {cmd_raw}", flush=True)
        
        parts = cmd_raw.split(" ")
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help" or cmd == "/?":
            print("## Internal Commands:", flush=True)
            print(" /status, /info      - Show server health and status", flush=True)
            print(" /save, /saveworld   - Force save the world", flush=True)
            print(" /say, /broadcast    - Send a message to all players", flush=True)
            print(" /players, /list     - List active players", flush=True)
            print(" /stop               - Gracefully stop the server", flush=True)
            print(" /update now         - Force update Palworld", flush=True)
            print(" /memory             - Show RAM diagnostics", flush=True)
            print(" /processes          - Show running processes", flush=True)
        
        elif cmd in ["/save", "/saveworld"]:
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
                    
        elif cmd in ["/players", "/list"]:
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
                
        elif cmd in ["/status", "/info"]:
            success, data = api_request("/info")
            if success:
                print(f"## Server Status", flush=True)
                print(f"Version: {data.get('version', 'Unknown')}", flush=True)
                print(f"Server Name: {data.get('servername', 'Unknown')}", flush=True)
            else:
                print("[RCON] Server is unreachable or starting up.", flush=True)

        elif cmd == "/stop":
            print("[CONSOLE] Manual stop requested.", flush=True)
            manager_wrapper.shutdown()

        elif cmd == "/memory":
            get_memory_info()

        elif cmd == "/processes":
            os.system("ps -ef --forest")

        elif cmd == "/update":
            if len(args) > 0 and args[0] == "now":
                print("[CONSOLE] Manual update requested. Shutting down server...", flush=True)
                manager_wrapper.shutdown()
                # Pterodactyl will detect exit and restart (or user has to manually start).
            else:
                print("Usage: /update now", flush=True)
                
        elif cmd.startswith("/"):
            print(f"[CONSOLE] Unknown command: {cmd}", flush=True)
        else:
            print("[CONSOLE] Ignoring non-slash command. Use /help for internal commands.", flush=True)


if __name__ == "__main__":
    wrapper = ManagerWrapper()

    # Handle Signals
    signal.signal(signal.SIGTERM, lambda s, f: wrapper.shutdown())
    signal.signal(signal.SIGINT, lambda s, f: wrapper.shutdown())

    # 1. Update Phase
    if UPDATE_ON_START:
        run_steamcmd_update()

    # 1.5 Fix steamclient.so
    fix_steamclient()

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
    
    print("[WATCHDOG] Upstream manager process exited.", flush=True)
    sys.exit(wrapper.process.returncode)
