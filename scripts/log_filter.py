#!/usr/bin/env python3
"""
log_filter.py — Interactive Anti-Spam Log Transformer & Portuguese Console Translator
Strips blank lines, filters internal REST/Sentry noise, and transforms raw technical logs
into beautiful, colorized, icon-enhanced Portuguese status messages for Pterodactyl console.
"""

import sys
import os
import re

# Ensure unbuffered UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CONSOLE_LANG = os.getenv("CONSOLE_LANG", "pt").lower()
ENABLE_COLOR = os.getenv("ENABLE_COLOR_LOGS", "true").lower() == "true"

# ANSI Colors
if ENABLE_COLOR:
    C_RESET = "\033[0m"
    C_BOLD = "\033[1m"
    C_BLUE = "\033[34m"
    C_GREEN = "\033[32m"
    C_YELLOW = "\033[33m"
    C_RED = "\033[31m"
    C_CYAN = "\033[36m"
    C_MAGENTA = "\033[35m"
else:
    C_RESET = C_BOLD = C_BLUE = C_GREEN = C_YELLOW = C_RED = C_CYAN = C_MAGENTA = ""

# Patterns to suppress entirely when QUIET_MONITORING=true
SUPPRESS_PATTERNS = [
    re.compile(r"REST accessed endpoint /v1/api/(players|info)\s+OK"),
    re.compile(r"API call completed /(players|info)"),
    re.compile(r"^\*\s+"),
    re.compile(r"^>\s+"),
    re.compile(r"^<\s+"),
    re.compile(r"^(Host|user-agent|accept|x-sentry-auth|content-type|content-length):\s*"),
    re.compile(r"^o1291919\.ingest\.us\.sentry\.io"),
    re.compile(r"^\{\}\* Connection #"),
    re.compile(r"^\[S_API FAIL\] Tried to access Steam interface"),
    re.compile(r"Server process started, verifying startup\.\.\."),
    re.compile(r"Verifying server process startup\.\.\."),
    re.compile(r"Checking process stability for 10 seconds\.\.\."),
    re.compile(r"Cleared only user-added callbacks"),
]

# Portuguese Translation & Transformation Rules
TRANSFORM_RULES_PT = [
    (
        re.compile(r"Server status: Running \(Players: (\d+), PID: (\d+)\)"),
        f"{C_GREEN}🟢 [STATUS]{C_RESET} {C_BOLD}Servidor Ativo & Estável{C_RESET} │ 👥 Jogadores Online: {C_CYAN}\\1{C_RESET} │ PID: \\2"
    ),
    (
        re.compile(r"Server operational - Players: (\d+)"),
        f"{C_GREEN}🎮 [PALWORLD]{C_RESET} {C_BOLD}Servidor Operacional{C_RESET} │ 👥 {C_CYAN}\\1{C_RESET} Jogador(es) Conectado(s)"
    ),
    (
        re.compile(r"Player (.*) joined"),
        f"{C_MAGENTA}✨ [CONEXÃO]{C_RESET} {C_BOLD}Jogador '{C_CYAN}\\1{C_MAGENTA}' entrou no servidor!{C_RESET}"
    ),
    (
        re.compile(r"Player (.*) left"),
        f"{C_YELLOW}👋 [DESCONEXÃO]{C_RESET} Jogador '\\1' saiu do servidor."
    ),
    (
        re.compile(r"Starting Palworld server with dynamic options"),
        f"{C_CYAN}🚀 [INICIANDO]{C_RESET} {C_BOLD}Executando Palworld com otimizações ARM64/FEX...{C_RESET}"
    ),
    (
        re.compile(r"Server started successfully with configured options"),
        f"{C_GREEN}✅ [SUCESSO]{C_RESET} {C_BOLD}Palworld iniciado e pronto para conexões!{C_RESET}"
    ),
    (
        re.compile(r"Server process is running and stable"),
        f"{C_GREEN}🛡️ [SISTEMA]{C_RESET} Processo do servidor verificado e estável."
    ),
    (
        re.compile(r"REST API started on port (\d+)"),
        f"{C_CYAN}🌐 [API REST]{C_RESET} Interface REST iniciada na porta {C_BOLD}\\1{C_RESET}"
    ),
    (
        re.compile(r"Running Palworld dedicated server on :(\d+)"),
        f"{C_GREEN}🎮 [REDES]{C_RESET} Palworld rodando e escutando na porta UDP {C_BOLD}:\\1{C_RESET}"
    ),
    (
        re.compile(r"Server settings file generated successfully"),
        f"{C_CYAN}⚙️ [CONFIG]{C_RESET} Configurações de jogo (PalWorldSettings.ini) aplicadas com sucesso."
    ),
    (
        re.compile(r"Engine settings file generated successfully"),
        f"{C_CYAN}⚙️ [CONFIG]{C_RESET} Configurações de Engine (Engine.ini) aplicadas com sucesso."
    ),
    (
        re.compile(r"Auto settings generation successful: (\d+) defaults, (\d+) overrides, (\d+) new settings"),
        f"{C_CYAN}🛠️ [CONFIG]{C_RESET} Configurações geradas: \\1 padrões, \\2 personalizações, \\3 novas opções."
    ),
    (
        re.compile(r"Downloading/updating server files\.\.\."),
        f"{C_YELLOW}📥 [STEAMCMD]{C_RESET} Verificando e atualizando arquivos do servidor Palworld..."
    ),
    (
        re.compile(r"Server files already exist, skipping download.*"),
        f"{C_GREEN}✓ [STEAMCMD]{C_RESET} Arquivos do servidor atualizados e verificados."
    ),
    (
        re.compile(r"Generating server settings\.\.\."),
        f"{C_CYAN}🛠️ [CONFIG]{C_RESET} Processando arquivos de configuração do servidor..."
    ),
    (
        re.compile(r"Config file watcher started.*"),
        f"{C_BLUE}👁️ [MONITOR]{C_RESET} Monitoramento de arquivos e configurações ativado."
    ),
    (
        re.compile(r"Starting player monitoring"),
        f"{C_BLUE}👥 [MONITOR]{C_RESET} Monitoramento de entrada/saída de jogadores iniciado."
    ),
    (
        re.compile(r"Starting server status monitoring"),
        f"{C_BLUE}📊 [MONITOR]{C_RESET} Monitoramento de status do servidor ativado."
    ),
    (
        re.compile(r"Discord notifications disabled"),
        f"{C_CYAN}🔔 [NOTIFICAÇÕES]{C_RESET} Notificações do Discord desativadas por configuração."
    ),
    (
        re.compile(r"Idle restart manager disabled by configuration"),
        f"{C_CYAN}💤 [REINÍCIO]{C_RESET} Reinício por inatividade desativado."
    ),
    (
        re.compile(r"Game version is (.*)"),
        f"{C_GREEN}📦 [VERSÃO]{C_RESET} Versão do Palworld: {C_BOLD}\\1{C_RESET}"
    ),
]

def format_line(line: str) -> str:
    if CONSOLE_LANG == "raw":
        return line

    # Strip ISO timestamp prefix if present: [INFO] 2026-08-09T16:39:58 text
    clean_line = re.sub(r"^\[INFO\]\s+\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\s*", "", line)
    clean_line = re.sub(r"^\[WARNING\]\s+\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\s*", "", clean_line)

    for pattern, replacement in TRANSFORM_RULES_PT:
        if pattern.search(clean_line):
            return pattern.sub(replacement, clean_line)

    # If no pattern matched, preserve clean formatting
    if line.startswith("[INFO]"):
        return re.sub(r"^\[INFO\]\s+\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\s*", f"{C_CYAN}[INFO]{C_RESET} ", line)
    if line.startswith("[WARNING]"):
        return re.sub(r"^\[WARNING\]\s+\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\s*", f"{C_YELLOW}[AVISO]{C_RESET} ", line)

    return line

def main():
    last_printed = None

    for line in sys.stdin:
        stripped = line.strip()

        # CRITICAL: Eliminate ALL empty lines / blank line spam
        if not stripped:
            continue

        # Suppress internal REST/Sentry noise
        should_suppress = False
        for pattern in SUPPRESS_PATTERNS:
            if pattern.search(stripped):
                should_suppress = True
                break

        if should_suppress:
            continue

        # Format / translate line
        formatted = format_line(stripped)

        # De-duplicate consecutive identical status lines
        if formatted == last_printed:
            continue
        last_printed = formatted

        # Output clean line immediately
        sys.stdout.write(formatted + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
