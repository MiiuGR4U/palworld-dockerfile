# Blueprint / Logic Mods

Estado: `EXPERIMENTAL`.

Upload:

```text
/home/container/mods/blueprint/ModName/
├── mod.json
└── ModName.pak
```

O target é `Pal/Content/Paks/LogicMods/<mod-id>/`. O `palmodctl` ativa os componentes pinados `BPML_GenericFunctions` e `BPModLoaderMod`, além de gerar `load_order.txt` determinístico.

O startup recusa declarar o mod ativo quando a biblioteca, configuração, BP loader ou preflight estiver ausente. Binários stripped, offsets e hooks do dedicated server podem mudar depois de updates; um deployment correto não prova funcionamento do Blueprint.

Use primeiro UE4SS sem mods e conclua o teste de identidade descrito em [UE4SS-LINUX.md](UE4SS-LINUX.md).
