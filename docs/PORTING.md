# 🔄 Porting Guide

> What to do when **Taskbar Hero** updates and your editor breaks. Covers the
> full checklist, how to extract the new HMAC key, the reverse-engineering
> workflow, and the data extraction pipeline.
>
> All concrete values in this guide are from game version **1.00.17**.

---

## ⚡ TL;DR — Porting Checklist

When a new game version drops, walk this list top to bottom:

| # | Step | If it works | If it doesn't |
|---|---|---|---|
| 1 | **Decrypt** the new save with the current ES3 password | ✅ Save opens | → Password changed, see [§2](#2-es3-crypto) |
| 2 | **Test the current HMAC key** against the new `SystemInfo` | ✅ Hash matches | → Key changed, see [§4](#4-extracting-the-hmac-key) |
| 3 | **Re-extract data** (tables / names / icons) | ✅ Editor works on new saves | Investigate schema changes (rare) |
| 4 | **Smoke-test**: load → edit one item → save → open in-game | ✅ All good | Walk the chain again |
| 5 | **Ship it** | 🎉 | Open an issue with details |

The good news: the **algorithm** (HMAC-SHA256 over `account|player|steamId`)
and the **crypto** (ES3 AES-128-CBC) have been **stable across versions**.
What usually changes is the **HMAC key value** and **table data**.

> 💡 Historical stability: ES3 password, IV handling, JSON schema, and HMAC composition haven't changed between 1.00.x versions. Expect this to keep holding.

---

## 1. Save Location & Format

| Field | Value |
|---|---|
| **Path** | `%USERPROFILE%\AppData\LocalLow\TesseractStudio\TaskbarHero\SaveFile_Live.es3` |
| **Container** | Easy Save 3 (ES3) |
| **Encryption** | AES-128-CBC, PBKDF2-HMAC-SHA1 key derivation |

The decrypted file is JSON with three top-level keys, each shaped `{ "__type": "string", "value": "<...>" }`:

| Key | Content |
|---|---|
| `AccountSaveData` | nested JSON string; contains `ownerSteamId` |
| `PlayerSaveData` | nested JSON string; heroes, items, enchants, … (the bulk of the save) |
| `SystemInfo` | base64 of 32 bytes = HMAC integrity tag (see [§3](#3-systeminfo-hmac)) |

See [`ARCHITECTURE.md`](ARCHITECTURE.md#-save-schema) for the full schema.

---

## 2. ES3 Crypto

```
IV         = raw[0..16]                                                  (random per save)
key        = PBKDF2-HMAC-SHA1(password, salt=IV, iters=100, dkLen=16)   # 16 bytes
ciphertext = raw[16:]
plaintext  = AES-128-CBC-decrypt(key, IV, ciphertext)  →  unpad PKCS7
```

| Constant | Value (1.00.17) |
|---|---|
| ES3 password | `emuMqG3bLYJ938ZDCfieWJ` |
| PBKDF2 iterations | `100` |
| Key length | 16 bytes (AES-128) |
| IV length | 16 bytes |
| Padding | PKCS7 |

### Implementation

`core/es3.py`:
- `es3_decrypt(raw, password)` — decrypt a raw save blob
- `es3_encrypt(plaintext, password, iv=None)` — encrypt; if `iv` is None, generate fresh
- `SaveFile.load(path)` / `SaveFile.save(path, backup=True)` — high-level

The AES backend is auto-selected:

```
prefer  cryptography  →  AES_BACKEND = "cryptography"   (fast)
fallback core/aes_pure.py  →  AES_BACKEND = "pure-python"  (zero deps, NIST-validated)
```

### If the password changes

The password is passed to the `ES3Settings` / `AESEncryptionAlgorithm`
constructor in the game's save manager. To find it in a new version:

1. **In the Il2CppDumper `dump.cs`**: search for `ES3Settings` or the
   `AESEncryptionAlgorithm` ctor calls in the save manager class.
2. **In `stringliteral.json`**: look for ~22-char strings near the save
   logic. Historically there's only one candidate.
3. Update `ES3_PASSWORD` at the top of `core/es3.py`.

In practice the password has not changed across observed versions.

---

## 3. SystemInfo HMAC

The game re-validates this on every load — mismatch → save flagged as
adulterated.

```
SystemInfo = Base64(
    HMAC-SHA256(
        key     = HMAC_KEY,
        message = UTF8(accountJson + "|" + playerJson + "|" + steamId)
    )
)
```

| Constant | Value (1.00.17) |
|---|---|
| **HMAC key (hex)** | `93d9429e9b72f22fdb3413193763eaba1e8cfae995f61466a81a36a609d8e456` |
| HMAC key length | 32 bytes |
| Algorithm | HMAC-SHA256 |
| Separator | `\|` (single pipe) |
| Encoding | base64 of raw digest |

### Validation in the game (`bal.mcr`)

Two checks on load:

1. **HMAC check** — recompute and byte-compare. Mismatch → `StartOption.kri`.
2. **Steam ID check** — `account.ownerSteamId` must match the logged-in
   Steam account. Mismatch → `StartOption.krj`.

⚠️ **Do not** modify `ownerSteamId` in the save — it must match the
currently logged-in Steam account.

### Editor consequence

On every save, the editor **recomputes `SystemInfo`** over the exact bytes
it just serialized. The result is byte-stable, and the game accepts it.

> **Side note:** our compact `json.dumps` differs from the game's Newtonsoft
> output only in float notation (e.g. `2.7e+11` vs `270000000000.0`) —
> semantically identical, harmless.

### Verifying a key (the "oracle")

Use the included oracle script (in the upstream `editor/` tooling) to test
candidate keys against a real `SystemInfo` value. The oracle tries multiple
orderings and separators; if any combination reproduces the stored hash,
the key is correct.

```powershell
python editor\oracle_systeminfo.py --key <hex> --save <path-to-.es3>
```

---

## 4. Extracting the HMAC Key

This is the **critical step** when the key changes. The key is derived by
PBKDF2 from strings that come from a **blob assembled at runtime** — so
static analysis alone won't recover it. We extract it live from the running
game.

### How the key is constructed (1.00.17)

- Field `bgco` of class `bal` (the save manager) holds the key bytes.
- Initialized in `bal.Awake` as `bgco = bam.mdj()`.
- `bam.mdj()` is a `static byte[]` method that returns the key. It does
  lazy-init internally; you can call it any time.
- The method internally runs `Rfc2898DeriveBytes` (PBKDF2-HMAC-SHA1) on
  strings read from a blob, with a hard-coded salt and iteration count.

### Live extraction via the trainer DLL

`dtcore.dll` is injected into the game process by the trainer launcher.
It exposes a `DumpSaveKey()` function that, when triggered by the **F8**
hotkey, invokes `bam.mdj()` via IL2CPP reflection and logs the result:

```cpp
klass  = FindClass(domain, "", "bam");
method = il2cpp_class_get_method_from_name(klass, "mdj", 0);
ret    = il2cpp_runtime_invoke(method, nullptr, nullptr, &exc);
// ret is Il2CppArray<byte>*; bytes at ret+0x20, length at ret+0x18
// log: SAVEKEY OK: bam.mdj() len=32 hex=...
```

The log file is at `%TEMP%\dtcore.log`. Look for a line like:

```
SAVEKEY OK: bam.mdj() len=32 hex=93d9429e9b72f22fdb3413193763eaba1e8cfae995f61466a81a36a609d8e456
```

`DumpSaveLiterals` also dumps the underlying PBKDF2 source strings (getters
`eyg` / `eze` / `ezf` / `ezh` on `<PrivateImplementationDetails>{GUID}.a`).
Useful for cross-checking.

### Step-by-step

1. Launch the game, load the save.
2. Run the trainer: `TrainerBuild\DisplayTuner.exe` (injects `dtcore.dll`).
3. Press **F8** in-game.
4. Open `%TEMP%\dtcore.log` → copy the hex after `hex=`.
5. Validate with the oracle (§3).
6. Paste the hex into `SYSTEMINFO_HMAC_KEY` in `core/es3.py`.

### If `bam.mdj` is renamed

The class name and method name are obfuscation; they may change between
versions. To find the new equivalents:

1. In the Il2CppDumper `dump.cs`, look for a **static class** with mostly
   `byte[]` methods (the "keystore"). Historically it was `bam` with
   TypeDefIndex ~3289.
2. The key-returning method is a public `byte[]()` that does
   `Rfc2898DeriveBytes(...).GetBytes` followed by `BlockCopy`.
3. Alternatively, find the `Awake` of the save manager and follow which
   static method populates the field used as the `HMACSHA256` ctor's
   argument.

The reverse-engineering workflow below covers this in more detail.

---

## 5. Reverse-Engineering Workflow

The key discovery was done with **Ghidra 12 + pyghidra** in
`C:\Users\gmarques\Downloads\ghidra_re\`. The general flow:

1. **Dump** the game with **Il2CppDumper** → `dump.cs` (signatures + RVAs),
   `stringliteral.json`, `script.json`.
2. **Locate the save manager** in `dump.cs`: search for the literal
   `"SystemInfo"`, then `AccountSaveData` / `PlayerSaveData` — the class
   that references all three is the save manager (historically `bal`).
3. **Decompile** the methods of interest using
   `ghidra_re\decomp_pyghidra.py` (edit the `TARGETS` list with the RVAs
   from the dump). Key methods in 1.00.17:

   | Method | RVA (1.00.17) | Role |
   |---|---|---|
   | `bal.mck` | `0xA945F0` | Assembles `Base64(HMACSHA256(key, a\|b\|c))` |
   | `bal.mcr` | `0xA95380` | Validates on load (the oracle target) |
   | `bal.mcc` / `bal.ldo` | — | Persist to disk |
   | `bal.Awake` | `0xA8C490` | `bgco = bam.mdj()` — pulls the HMAC key |
   | `bam.mdj` | `0xAA85D0` | The PBKDF2 key derivation |
   | `<PrivImplDetails>.a` | `0xB0C590` | Stub returning `UTF8.GetString(blob, seed, len)` |

4. **Trace the key** by stepping from `bam.mdj` through PBKDF2 (it consumes
   two UTF-8 strings fetched from a runtime blob via the `<PrivImplDetails>.a`
   stub). The blob itself is built at runtime — so recovering the key
   statically is impractical. **Extract it live** (§4) instead.
5. **Helper scripts** in `ghidra_re\`:
   - `resolve_literals.py` — map `stringliteral.json` indices to C# strings
   - `disasm_stub.py` — show disassembly around a target RVA
   - `find_blob.py` — scan for blob-construction patterns

> 🎯 **Rule of thumb**: Taskbar Hero uses **deterministic** obfuscation.
> Untouched classes keep their names between versions; only what the
> studio edits gets re-scrambled. Always cross-check new function
> prologues / signatures against the previous dump.

---

## 6. Re-Extracting Data (tables / names / icons)

For the editor's data files in `data/`. Requires `pip install UnityPy` (only
needed here, not for running the editor itself).

```powershell
pip install UnityPy
python extract\extract_all.py
```

The orchestrator runs four sub-scripts in sequence:

| Step | Script | Source | Output |
|---|---|---|---|
| 1 | `extract_tables.py` | `sharedassets0.assets` TextAssets | `data/tables/*.csv` (15 tables) |
| 2 | `extract_enums.py` | Il2CppDumper `dump.cs` | `data/enums.json` (5 enums) |
| 3 | `extract_localization.py` | localization bundles (`localization-string-tables-english(unitedstates)(en-us)_assets_all.bundle`) | `data/names.json`, `data/strings.json` |
| 4 | `extract_sprites.py` | `sharedassets0.assets` Sprites | `data/icons/*.png` + `data/icon_map.json` |

### Where the data lives in the game

```
<Steam>\steamapps\common\TaskbarHero\
└── TaskBarHero_Data\
    ├── sharedassets0.assets               ← tables (TextAsset), sprites
    └── StreamingAssets\
        └── aa\StandaloneWindows64\
            ├── localization-assets-shared_assets_all.bundle
            └── localization-string-tables-english(unitedstates)(en-us)_assets_all.bundle
```

### Resolution chain for names

```
SharedTableData (m_Id → m_Key)   +   <Table>_en (m_Id → m_Localized)
         │                                       │
         │        ItemTable_en  →  ItemName_<ItemKey>   →  names.json
         │        StringTable_en →  HeroName_<key>      →  strings.json
```

For names, `extract_localization.py` only extracts the key patterns the
editor actually uses (`ItemName_*` and `HeroName_*`) to keep the output
data lean (~16KB instead of ~130KB of unconsumed strings).

### Icon naming convention

- Materials: `Item_<ItemKey>`
- Equipment: `<TYPE>_<GearKey>`

Coverage: 1 sprite per `ItemKey`, no ambiguity.

---

## 7. File Map

| File / Path | Role |
|---|---|
| `core/es3.py` | AES-CBC + PKCS7 + HMAC; `SaveFile.load` / `SaveFile.save` |
| `core/aes_pure.py` | Pure-Python AES-128-CBC fallback (NIST-validated) |
| `core/gamedata.py` | Table loaders + enchant validation engine |
| `editor/oracle_systeminfo.py` | Verify candidate HMAC keys against a real `SystemInfo` |
| `editor/decrypt_es3.py` | Decrypt a `.es3` to plain JSON (one-shot CLI) |
| `TBH_Trainer_v1.3.0/TBHHook/dllmain.cpp` | `DumpSaveKey` / `DumpSaveLiterals` (F8 hotkey) |
| `ghidra_re/decomp_pyghidra.py` + helpers | Ghidra decompilation script |
| `extract/extract_*.py` | One-shot data extraction (UnityPy) |
| `docs/ARCHITECTURE.md` | System design deep dive (read this first) |
| `README.md` | Quick start, features, layout |

---

## 📚 Related Reading

- **[`README.md`](../README.md)** — quick start and overview
- **[`docs/ARCHITECTURE.md`](ARCHITECTURE.md)** — system design, layers, save schema
- **[`docs/README.md`](README.md)** — docs index
