# 🔄 Porting Guide

> What to do when **Taskbar Hero** updates and your editor breaks. Covers the
> full checklist, how to extract the new HMAC key, the reverse-engineering
> workflow, and the data extraction pipeline.
>
> Bundled data now targets **1.2.8**, Steam build **25454993**. Historical
> crypto keys, obfuscated method names, and RVAs below describe **1.00.17**;
> do not assume those method locations still apply to a newer binary.

Current verification covers extracted data and local encrypted-copy checks.
Browser checks also use disposable copies. Loading an edited save in game
1.2.8 has not been verified; `data/version.json` records that boundary.

---

## ⚡ TL;DR — Porting Checklist

When a new game version drops, walk this list top to bottom:

| # | Step | If it works | If it doesn't |
|---|---|---|---|
| 1 | **Decrypt** the new save with the current ES3 password | ✅ Save opens | → Password changed, see [§2](#2-es3-crypto) |
| 2 | **Test the current HMAC key** against the new `SystemInfo` | ✅ Hash matches | → Key changed, see [§4](#4-extracting-the-hmac-key) |
| 3 | **Re-extract data** (tables / enums / names / icons) with a matching dump | Catalog reflects the installed build | Inspect extractor errors and schema changes |
| 4 | **Test a copy**: load → hero → equipment → edit → review → save with backup → decrypt/reload; separately load in-game | Record local and game results separately | Investigate the failing boundary |
| 5 | **Ship it** | 🎉 | Open an issue with details |

The implemented algorithm is HMAC-SHA256 over `account|player|steamId`, with
ES3 AES-128-CBC encryption. Check both crypto compatibility and table data
for each update; successful decryption alone does not validate the tables.

> Historical 1.00.x observations are background, not a compatibility guarantee
> for the next update. Preserve original saves and work on copies during checks.

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

### Historical 1.00.17 validation in the game (`bal.mcr`)

Two checks on load:

1. **HMAC check** — recompute and byte-compare. Mismatch → `StartOption.kri`.
2. **Steam ID check** — `account.ownerSteamId` must match the logged-in
   Steam account. Mismatch → `StartOption.krj`.

⚠️ **Do not** modify `ownerSteamId` in the save — it must match the
currently logged-in Steam account.

### Editor consequence

On every save, the editor **recomputes `SystemInfo`** over the exact bytes
it just serialized. Verify the resulting encrypted copy and HMAC first;
acceptance by the game is a separate test.

> **Side note:** our compact `json.dumps` differs from the game's Newtonsoft
> output only in float notation (e.g. `2.7e+11` vs `270000000000.0`) —
> semantically equivalent JSON. That equivalence does not replace a game-load test.

### Verifying a key (the "oracle")

Use the oracle script from the upstream `editor/` tooling (not shipped in this repository) to test
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

### Historical live extraction via the trainer DLL

The trainer and identifiers in this section belong to the original 1.00.17
workflow. They were not used or validated during this 1.2.4 data refresh.

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

The original key discovery used **Ghidra 12 + pyghidra** and the upstream
`ghidra_re` tooling. The general flow:

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

For the editor's generated files in `data/`. UnityPy is required only for
extraction; the editor runtime still uses the Python standard library. Supply
an Il2CppDumper `dump.cs` produced from the same installed game build.

```powershell
python -m pip install UnityPy
python -B extract\extract_all.py --dump-path 'C:\path\to\dump.cs' --game-version 1.2.8 --steam-build 25454993
```

`--game-dir` accepts the install root or `TaskBarHero_Data`; its default is
`C:\Program Files (x86)\Steam\steamapps\common\TaskbarHero`.
Use `--output 'C:\path\to\extracted-data'` to inspect a refresh separately.
Version/build arguments must describe the inputs; the extractor records them
as supplied values, not a detected or in-game-verified version.

Preflight checks the asset files, texture resource, localization bundles,
matching dump's required enums, and UnityPy before publication. Extraction
runs in a temporary staging directory. Only after all four steps and catalog
checks pass does it replace the generated directory. A failed extraction
leaves prior data intact; a publication error attempts rollback and preserves
a recovery copy if restoration itself fails.

The orchestrator runs four sub-scripts in sequence:

| Step | Script | Source | Output |
|---|---|---|---|
| 1 | `extract_tables.py` | `sharedassets0.assets` TextAssets | `data/tables/*.csv` (15 tables) |
| 2 | `extract_enums.py` | Il2CppDumper `dump.cs` | `data/enums.json` (5 enums) |
| 3 | `extract_localization.py` | localization bundles (`localization-string-tables-english(unitedstates)(en-us)_assets_all.bundle`) | `data/names.json`, `data/strings.json` |
| 4 | `extract_sprites.py` | `sharedassets0.assets` Sprites | `data/icons/*.png` + `data/icon_map.json` |

The full command also generates `data/version.json`: game version/build,
UTC extraction time, source hashes, UnityPy version, counts, coverage limits,
and `verification.inGameVerified: false`.

The 1.2.8 snapshot (tables byte-identical to 1.2.4) contains 15 tables, 534 item names, 6 hero names, and 530
icons. Enum counts are StatType 65, MODTYPE 3, ERecipeType 10, EMaterialType 8,
and EGradeType 11. All old numeric IDs remain unchanged; new members include
MaxAllElementalResistance, CORROSION, and ETC.

### Where the data lives in the game

```
<Steam>\steamapps\common\TaskbarHero\
└── TaskBarHero_Data\
    ├── sharedassets0.assets               ← tables (TextAsset), sprites
    ├── sharedassets0.assets.resS          ← sprite texture data
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

Shared sprites are resolved through `ItemInfoData.IconPath`, including coins
and plague-fruit variants. Four localized keys (`150102`, `150108`, `150109`,
`150110`) have neither an item definition nor a sprite in the current build;
they remain listed in the generated coverage metadata. Every named item with
an item definition and every enchant material has an extracted icon.

### Local verification before a game test

```powershell
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s extract -p 'test_*.py' -v
```

The current 26 core/HTTP tests cover legal raw-value round-trips, fractional
display ranges/steps, enum and Custom values identity validation, rejection without mutation, and an
encrypted fixture's save/reload plus exact backup. The 5 extractor tests cover
missing inputs, incomplete dumps, partial extraction, and rollback failures.
These tests do not launch the game.

The 1.2.4 table refresh changes all four elemental/chaos resistance families
at tiers 4–10; tier 10 now spans 80–90 instead of 50–55. Several material
stat/tier mappings also changed. Refreshing only the version label would leave
normal editing inconsistent with these tables.

Use a disposable encrypted save copy for browser verification. Check an existing
enchant opens with its current stat/tier/value, apply a decimal value such as
DamageAbsorption 0.5, review before/after, save with backup, and reload the copy.
`to_raw()` must reject input that cannot resolve to an integer raw value rather
than truncate it. Keep the game-load result separate from these local checks.

---

## 7. File Map

| File / Path | Role |
|---|---|
| `core/es3.py` | AES-CBC + PKCS7 + HMAC; `SaveFile.load` / `SaveFile.save` |
| `core/aes_pure.py` | Pure-Python AES-128-CBC fallback (NIST-validated) |
| `core/gamedata.py` | Table loaders + enchant validation engine |
| `editor/oracle_systeminfo.py` | Upstream-only historical tool to verify candidate HMAC keys |
| `editor/decrypt_es3.py` | Upstream-only historical decryption CLI |
| `TBH_Trainer_v1.3.0/TBHHook/dllmain.cpp` | Upstream-only historical `DumpSaveKey` / `DumpSaveLiterals` |
| `ghidra_re/decomp_pyghidra.py` + helpers | Upstream-only Ghidra tooling |
| `extract/extract_*.py` | One-shot data extraction (UnityPy) |
| `data/version.json` | Generated source hashes, version/build, counts, and verification scope |
| `tests/` / `extract/test_extraction.py` | Core/HTTP fixture checks and extraction failure checks |
| `docs/ARCHITECTURE.md` | System design deep dive (read this first) |
| `README.md` | Quick start, features, layout |

---

## 📚 Related Reading

- **[`README.md`](../README.md)** — quick start and overview
- **[`docs/ARCHITECTURE.md`](ARCHITECTURE.md)** — system design, layers, save schema
- **[`docs/README.md`](README.md)** — docs index
