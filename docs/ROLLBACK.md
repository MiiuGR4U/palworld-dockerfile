# Rollback

Liste os diretórios em `/home/container/backups/mod-changes/` e execute:

```bash
/opt/palworld-mod-runtime/palmodctl rollback 20260810T120000.000000Z
```

O fluxo:

1. cria um backup `pre-rollback` do estado atual;
2. restaura fontes e state do snapshot selecionado;
3. não restaura saves/configs do jogo por padrão;
4. redeploya segundo as feature flags atuais;
5. grava `mods/state/last-rollback.json`.

Para restaurar saves e configs, a ação deve ser explícita e o servidor deve estar parado:

```bash
/opt/palworld-mod-runtime/palmodctl rollback BACKUP --restore-saves
```

Não use rollback de saves como reação automática a erro de mod: ele pode apagar progresso legítimo posterior ao snapshot.
