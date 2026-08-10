# Segurança

- Runtime deve ser non-root. A imagem declara `USER steam`, e Wings pode aplicar o UID/GID do servidor.
- Nenhum `chown -R`, `777`, privileged, FUSE, systemd ou mount externo é necessário.
- Arquivos mutáveis ficam em `/home/container`; `/home/steam` não é persistência.
- Scanner/validator não executam mod code.
- Symlinks em fontes de mod são rejeitados; targets são limitados a roots/arquivos gerenciados.
- Deployment usa staging, cópias temporárias e `os.replace`; falhas restauram arquivos anteriores quando possível.
- DLL/PE são rejeitados. ELF `.so` ainda é código arbitrário e tem acesso a tudo que o usuário do servidor pode acessar.
- Startup não baixa mods, CurseForge, Nexus ou loader `latest`.
- Logs de resumo não exibem `ADMIN_PASSWORD`, `SERVER_PASSWORD`, tokens ou webhooks.
- REST/RCON permanecem em localhost por padrão.

O arquivo de estado é administrativo. Não edite `mods/state/inventory.json` manualmente; paths são revalidados, mas adulteração pode impedir startup/cleanup.

Relate incidentes preservando console, `UE4SS.log`, inventory, quarantine e o backup anterior. Não envie senhas ou webhooks nos logs compartilhados.
