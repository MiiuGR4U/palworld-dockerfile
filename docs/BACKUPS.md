# Backups de mudanças de mods

Quando o inventário SHA256 muda e `MODS_BACKUP_ON_CHANGE=true`, o backup é criado antes do deployment em:

```text
/home/container/backups/mod-changes/<timestamp>/
```

Inclui no mínimo:

- `Pal/Saved/SaveGames`;
- `Pal/Saved/Config`;
- `mods/state`;
- fontes `mods/patch`, `blueprint`, `lua`, `cpp`;
- `mods/configs` e `mods/manifests`.

Inventário sem mudança não cria backup nem redeploy. A retenção padrão é 10 backups e remove apenas snapshots antigos dentro de `backups/mod-changes`.

Backup manual:

```bash
/opt/palworld-mod-runtime/palmodctl backup
/opt/palworld-mod-runtime/palmodctl backup-if-needed
```

Backups do Pterodactyl continuam recomendados. O backup de mudança de mods não substitui uma política externa de disaster recovery.
