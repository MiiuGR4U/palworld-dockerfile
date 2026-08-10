# C++ Native Mods

Estado: `EXPERIMENTAL/limitado`.

Upload:

```text
/home/container/mods/cpp/ModName/
├── mod.json
└── main.so
```

O manifesto deve usar `"platform": "linux-x86_64"`. O validador exige:

- magic ELF;
- 64-bit;
- machine x86-64 (`EM_X86_64`);
- tipo shared object (`ET_DYN`);
- extensão `.so`.

O target do loader pinado é `Mods/<id>/libs/`. `.dll`, PE32/PE32+ e um PE renomeado para `.so` são rejeitados com:

```text
Windows DLL detected.
Current backend: Linux x86_64 under FEX.
Required: Linux x86_64 ELF .so.
```

Código nativo roda com as mesmas permissões do servidor Palworld. Trate qualquer `.so` como código arbitrário e instale somente de uma fonte confiável. Nunca “converta” DLL mudando a extensão.
