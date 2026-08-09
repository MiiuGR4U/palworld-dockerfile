#!/usr/bin/env python3
"""
palworld_helper.py — Palworld Native Helper Suite
Provides Auto-Save with emergency shutdown protection, Auto-Broadcast in-game announcements,
and Discord Webhook notifications for server status and player connections.
Zero external dependencies (uses urllib.request).
"""

import sys
import os
import json
import time
import signal
import base64
import threading
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Environment Configuration
REST_PORT = os.getenv("REST_API_PORT", "8212")
REST_HOST = os.getenv("REST_API_HOST", "localhost")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-now")
CONSOLE_LANG = os.getenv("CONSOLE_LANG", "pt").lower()

AUTOSAVE_INTERVAL = int(os.getenv("AUTOSAVE_INTERVAL_MINUTES", "15"))
AUTOSAVE_NOTIFY = os.getenv("AUTOSAVE_NOTIFY_INGAME", "true").lower() == "true"

ANNOUNCE_INTERVAL = int(os.getenv("ANNOUNCE_INTERVAL_MINUTES", "10"))
ANNOUNCE_MESSAGES_RAW = os.getenv(
    "ANNOUNCE_MESSAGES",
    "🎮 Bem-vindos ao servidor! Divirtam-se e boa jogatina!;💾 O progresso do servidor é salvo automaticamente a cada 15 minutos.;⚔️ Lembrem-se de organizar os Pals e cuidar da base!;💬 Qualquer dúvida ou erro no servidor, mandem mensagem no grupo!"
)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
DISCORD_NOTIFY_PLAYERS = os.getenv("DISCORD_NOTIFY_PLAYERS", "true").lower() == "true"
PRESERVE_CUSTOM_SETTINGS = os.getenv("PRESERVE_CUSTOM_SETTINGS", "true").lower() == "true"

BASE_URL = f"http://{REST_HOST}:{REST_PORT}/v1/api"

def preserve_user_ini():
    if not PRESERVE_CUSTOM_SETTINGS:
        return

    ini_path = "/home/container/Pal/Saved/Config/LinuxServer/PalWorldSettings.ini"
    bak_path = "/home/container/tmp/PalWorldSettings.ini.userbak"

    if os.path.exists(bak_path):
        try:
            # Small sleep to let manager write initial defaults
            time.sleep(2)
            with open(bak_path, "r", encoding="utf-8", errors="ignore") as f_bak:
                custom_content = f_bak.read()

            if custom_content.strip():
                with open(ini_path, "w", encoding="utf-8") as f_ini:
                    f_ini.write(custom_content)
                print("[HELPER] 🛡️ [CONFIG] Edições manuais do arquivo PalWorldSettings.ini preservadas com sucesso!", flush=True)
        except Exception as e:
            print(f"[HELPER] ⚠️ Não foi possível restaurar PalWorldSettings.ini: {e}", flush=True)

def get_auth_header() -> dict:
    auth_str = f"admin:{ADMIN_PASSWORD}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/json",
        "User-Agent": "PalworldHelper/1.0"
    }

def api_request(endpoint: str, method: str = "GET", data: dict = None) -> tuple[bool, dict]:
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
    except (URLError, HTTPError, json.JSONDecodeError, Exception):
        return False, {}

def send_discord_embed(title: str, description: str, color: int = 3447003):
    if not DISCORD_WEBHOOK_URL:
        return

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "footer": {"text": "Palworld ARM64 Helper"}
            }
        ]
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "PalworldHelper/1.0"}
    req = Request(DISCORD_WEBHOOK_URL, data=body_bytes, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=5):
            pass
    except Exception:
        pass

def trigger_save() -> bool:
    success, _ = api_request("/save", method="POST")
    if success and AUTOSAVE_NOTIFY:
        msg = "💾 [AUTOSAVE] Progresso do mundo salvo com sucesso!" if CONSOLE_LANG == "pt" else "💾 [AUTOSAVE] World progress saved!"
        api_request("/announce", method="POST", data={"message": msg})
    return success

def send_announce(message: str) -> bool:
    if not message.strip():
        return False
    success, _ = api_request("/announce", method="POST", data={"message": message.strip()})
    return success

# Background Auto-Save Loop
def autosave_loop():
    if AUTOSAVE_INTERVAL <= 0:
        return
    while True:
        time.sleep(AUTOSAVE_INTERVAL * 60)
        trigger_save()

# Background Auto-Broadcast Loop
def autoannounce_loop():
    if ANNOUNCE_INTERVAL <= 0:
        return
    messages = [m.strip() for m in ANNOUNCE_MESSAGES_RAW.split(";") if m.strip()]
    if not messages:
        return

    index = 0
    while True:
        time.sleep(ANNOUNCE_INTERVAL * 60)
        msg = messages[index % len(messages)]
        send_announce(msg)
        index += 1

# Player Join/Leave Tracking Loop
def player_tracker_loop():
    known_players = set()
    first_run = True

    while True:
        time.sleep(10)
        success, data = api_request("/players")
        if not success:
            continue

        players = data.get("players", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        current_players = {}

        for p in players:
            if isinstance(p, dict):
                p_id = p.get("account_name") or p.get("steam_id") or p.get("name")
                p_name = p.get("name", "Desconhecido")
                if p_id:
                    current_players[p_id] = p_name

        current_ids = set(current_players.keys())

        if not first_run:
            joined = current_ids - known_players
            left = known_players - current_ids

            for p_id in joined:
                name = current_players[p_id]
                if DISCORD_WEBHOOK_URL and DISCORD_NOTIFY_PLAYERS:
                    send_discord_embed("✨ Jogador Conectou", f"**{name}** entrou no servidor!", color=3066993)

            for p_id in left:
                if DISCORD_WEBHOOK_URL and DISCORD_NOTIFY_PLAYERS:
                    send_discord_embed("👋 Jogador Desconectou", f"Um jogador desconectou do servidor.", color=15158332)

        known_players = current_ids
        first_run = False

# Emergency Shutdown Signal Handler
def shutdown_handler(signum, frame):
    print("[HELPER] Emergency shutdown signal received! Executing forced world save...", flush=True)
    trigger_save()
    if DISCORD_WEBHOOK_URL:
        send_discord_embed("🔴 Servidor Encerrado", "O servidor Palworld foi desligado.", color=15158332)
    sys.exit(0)

def main():
    # Preserve custom PalWorldSettings.ini edits
    preserve_user_ini()

    # Register signal handlers for graceful stop
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Wait for REST API to respond
    print("[HELPER] Waiting for Palworld REST API at localhost:8212...", flush=True)
    for _ in range(30):
        success, _ = api_request("/info")
        if success:
            print("[HELPER] Palworld REST API connected successfully!", flush=True)
            break
        time.sleep(5)

    if DISCORD_WEBHOOK_URL:
        send_discord_embed("🟢 Servidor Online", "O servidor Palworld ARM64 está online e pronto para conexões!", color=3066993)

    # Launch background threads
    t_save = threading.Thread(target=autosave_loop, daemon=True)
    t_announce = threading.Thread(target=autoannounce_loop, daemon=True)
    t_players = threading.Thread(target=player_tracker_loop, daemon=True)

    t_save.start()
    t_announce.start()
    t_players.start()

    # Keep helper process alive
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
