# Edição de Save do Taskbar Hero — Internals & Porting

Guia para **portar a edição de save para versões futuras** do jogo. Resume o que descobrimos e
os passos para refazer. Valores concretos abaixo são da versão **1.00.17**.

---

## TL;DR — checklist ao chegar versão nova

1. **Decriptar** o save com a senha ES3 atual e ver se ainda abre (seção 2). Se falhar, a senha mudou → seção 2.
2. **Testar a chave HMAC atual** no oráculo (seção 3). Se bater com o `SystemInfo` do save → nada mudou, só atualizar `data/` se quiser (seção 6).
3. **Se a chave não bater** → re-extrair em runtime via DLL (seção 4). Atualizar `SYSTEMINFO_HMAC_KEY` em `core/es3.py`.
4. **Re-extrair tabelas/nomes/ícones** se valores de jogo mudaram: `python extract/extract_all.py` (seção 6).
5. Validar editando 1 item + salvar num backup + abrir no jogo.

O algoritmo (HMAC-SHA256 sobre `account|player|steamId`) e a cripto (ES3 AES-128-CBC) têm sido **estáveis entre versões**; o que muda é o **valor da chave** e os **dados das tabelas**.

---

## 1. Save: onde fica e formato

- Caminho: `%USERPROFILE%\AppData\LocalLow\TesseractStudio\TaskbarHero\SaveFile_Live.es3`
- Formato: **Easy Save 3 (ES3)**, criptografado com **AES-128-CBC**.
- Decriptado = JSON ES3 com 3 chaves de topo, cada uma `{ "__type":"string", "value":"<...>" }`:
  - `AccountSaveData` → string com JSON (Newtonsoft) aninhado (tem `ownerSteamId`).
  - `PlayerSaveData` → string com JSON aninhado (heróis, itens, etc.). É o grosso do save.
  - `SystemInfo` → base64 de 32 bytes = **HMAC de integridade** (anti-tamper). Ver seção 3.

## 2. Camada 1 — Criptografia ES3 (decriptar / encriptar)

```
IV  = primeiros 16 bytes do arquivo  (aleatório por save)
key = PBKDF2-HMAC-SHA1(senha_ES3, salt=IV, iterações=100, dkLen=16)   # AES-128
corpo = AES-128-CBC + PKCS7 sobre o restante dos bytes
```

- **Senha ES3 (1.00.17):** `emuMqG3bLYJ938ZDCfieWJ`
- Encriptar = gerar IV novo aleatório (o jogo faz isso a cada save) e repetir.
- Implementação: `core/es3.py` (`es3_decrypt`/`es3_encrypt`). AES via `cryptography` ou `core/aes_pure.py` (puro, validado vs vetor NIST).
- **Se a senha mudar numa versão nova:** ela é passada ao construtor do `ES3Settings`/`AESEncryptionAlgorithm`. Achar no dump procurando o uso de `ES3Settings..ctor` no save manager (classe `bal`), ou no `stringliteral.json` por strings de ~22 chars perto da lógica de save. (Na prática não mudou.)

## 3. Camada 2 — SystemInfo (HMAC anti-tamper) + script

O jogo grava e **revalida no load**:

```
SystemInfo = Base64( HMAC-SHA256( key = CHAVE_HMAC,
                                  UTF8( accountJson + "|" + playerJson + "|" + steamId ) ) )
```

- `accountJson` = `AccountSaveData.value` exatamente como gravado; `playerJson` = `PlayerSaveData.value`; `steamId` = `account.ownerSteamId`; separador = `"|"`.
- **Validação no load** (método `bal.mcr`): recomputa o HMAC e compara byte-a-byte com o `SystemInfo` salvo. Se diferente → trata como **save adulterado** (`StartOption.kri`). Também compara o `ownerSteamId` do save com o Steam logado (`StartOption.krj` se diferente — não trocar o `ownerSteamId`).
- **Consequência:** ao editar Account/Player é **obrigatório recalcular o SystemInfo** (`core/es3.py` faz no `save()`). Como hasheamos exatamente as strings que gravamos, fica consistente e o jogo aceita. (Re-serialização compacta difere do Newtonsoft só na notação de float, ex `2.7e+11` vs `270...0.0` — semanticamente igual, inócuo.)
- **CHAVE_HMAC (1.00.17):** `93d9429e9b72f22fdb3413193763eaba1e8cfae995f61466a81a36a609d8e456` (32 bytes). É **constante** (derivada do binário, não depende de máquina/conta/save).

**Verificador (oráculo):** `editor/oracle_systeminfo.py` recebe a chave em hex e testa ordens/separadores contra o `SystemInfo` real do save. Se alguma combinação reproduz o valor armazenado → chave correta. Use para confirmar a chave a cada versão.

## 4. Obter a CHAVE_HMAC do jogo (DLL injetada) — o passo crítico

A chave (`bgco`, campo da classe `bal`) é derivada por PBKDF2 a partir de strings que vêm de um **blob montado em runtime** → recuperar **estaticamente é inviável**. Pegamos em **runtime**:

- No `Awake` da classe `bal`, `bgco = bam.mdj()`. **`bam.mdj()` é um método `static byte[]`** que retorna a chave (faz lazy-init sozinho). Basta invocá-lo.
- O `dtcore.dll` (injetado pelo trainer) tem `DumpSaveKey()` (hotkey **F8**) que faz:
  ```cpp
  klass  = FindClass(domain, "", "bam");                       // classe estática 'bam'
  method = il2cpp_class_get_method_from_name(klass, "mdj", 0);  // ou "gxn" (idêntico)
  ret    = il2cpp_runtime_invoke(method, nullptr, nullptr, &exc);  // Il2CppArray<byte>*
  // bytes em ret+0x20, length em ret+0x18 → loga hex
  ```
  Log em `%TEMP%\dtcore.log` (linha `SAVEKEY OK: bam.mdj() len=32 hex=...`). Também dumpa os literais (`DumpSaveLiterals`, classe `<PrivateImplementationDetails>{GUID}.a` getters eyg/eze/ezf/ezh) — úteis para conferência.
- **Passos:** abrir o jogo (entrar no save) → injetar o trainer (`TrainerBuild\DisplayTuner.exe`) → **F8** → copiar o hex do log → validar no oráculo → colar em `SYSTEMINFO_HMAC_KEY` (`core/es3.py`).
- **Se `bam.mdj` mudar de nome** numa versão nova (ofuscação): no dump, achar a classe estática cheia de métodos `byte[]` (keystore; era `bam`, TypeDefIndex ~3289) e o método público `byte[]()` que faz `Rfc2898DeriveBytes(...).GetBytes` + `BlockCopy`. Ou achar no `Awake` do save manager qual método estático preenche o campo usado como key do `HMACSHA256$$.ctor`.

## 5. Como descobrimos (engenharia reversa) — resumo do método

Ambiente em `C:\Users\gmarques\Downloads\ghidra_re\` (Ghidra 12 + pyghidra; ver memória `ghidra-re-workflow`). Fluxo:

1. **Dump** do jogo com Il2CppDumper → `dump.cs` (assinaturas + RVA), `stringliteral.json`, `script.json`.
2. Achar o **save manager**: no `dump.cs`, procurar `"SystemInfo"` (const), `AccountSaveData`/`PlayerSaveData` → caímos na classe `bal`.
3. **Decompilar** os métodos-alvo com `ghidra_re\decomp_pyghidra.py` (editar `TARGETS` com os RVAs; roda pyghidra). Métodos-chave 1.00.17: `mck` 0xA945F0 (monta `Base64(HMACSHA256(key, a|b|c))`), `mcr` 0xA95380 (valida no load), `mcc`/`ldo` (salvam), `bal.Awake` 0xA8C490 (`bgco=bam.mdj()`).
4. **Chave:** seguir `bam.mdj` 0xAA85D0 → PBKDF2(senha=UTF8(strA+strB), salt, iters) das strings de um blob acessado por offset (stub `<PrivImplDetails>.a` em 0xB0C590 fazendo `UTF8.GetString(blob, seed, len)`). Blob montado em runtime → **extrair a chave viva** (seção 4) em vez de reconstruir.
5. Scripts auxiliares em `ghidra_re\`: `resolve_literals.py`, `disasm_stub.py`, `find_blob.py`.

> Regra: o jogo usa ofuscação **determinística** — classes intocadas mantêm nomes entre versões; só o que o estúdio mexeu é reembaralhado. Sempre cruzar prólogos/assinaturas com o dump anterior.

## 6. Extrair dados do jogo (tabelas / nomes / ícones)

Para a app de edição de itens (`saveEditor`). Requer `pip install UnityPy` (só para extrair; a app não precisa).

- **Tabelas (CSV):** TextAssets em `TaskBarHero_Data\sharedassets0.assets` (`StatModInfoData`, `MaterialInfoData`, `StatModGroupInfoData`, `GradeInfoData`, `GearInfoData`, `HeroInfoData`...). `obj.read().m_Script`.
- **Nomes/strings (Unity Localization):** bundles em `StreamingAssets\aa\StandaloneWindows64\localization-*`. SharedTableData mapeia `m_Id`→key (`ItemName_<ItemKey>`, `HeroName_<HeroKey>`); `ItemTable_<locale>`/`StringTable_<locale>` mapeiam `m_Id`→texto (via `read_typetree()`).
- **Ícones:** Sprites em sharedassets0 com nome `Item_<ItemKey>` ou `<TIPO>_<GearKey>`; `sprite.image` (PIL) → PNG.
- **Enums:** parsear `dump.cs` (StatType, MODTYPE, ERecipeType, EMaterialType, EGradeType).
- Tudo orquestrado por `extract/extract_all.py` → gera `saveEditor/data/` (portável).

## 7. Arquivos & referências

- **Cripto + SystemInfo:** `saveEditor/core/es3.py` (+ `aes_pure.py`); verificador `editor/oracle_systeminfo.py`; decrypt simples `editor/decrypt_es3.py`.
- **DLL (extração da chave):** `TBH_Trainer_v1.3.0/TBHHook/dllmain.cpp` (`DumpSaveKey`/`DumpSaveLiterals`, hotkey F8); build `build.bat` → `dtcore.dll`.
- **RE:** `ghidra_re/decomp_pyghidra.py` e auxiliares.
- **App de edição:** `saveEditor/` (server.py + core/ + web/ + data/).
- **Memórias relacionadas:** `save-systeminfo-antitamper`, `save-editor-app`, `ghidra-re-workflow`, `tbh-trainer-port`.
