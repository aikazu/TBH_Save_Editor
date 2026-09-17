# 🏗 Architecture

Bundled assets target **1.2.4**, Steam build **25336766**. Source hashes and
coverage are recorded in `data/version.json`. Crypto details below retain
their original 1.00.17 provenance; local validation and encrypted-copy tests
do not establish that an edited save loads in the current game.

> Deep dive into how **TBH Save Editor** is built — the layers, data flow, save
> format, and enchantment resolution chain. Read this if you want to modify
> the editor or understand why a feature works the way it does.

---

## 📋 Table of Contents

1. [Big Picture](#big-picture)
2. [Layer 1 — ES3 Crypto](#layer-1--es3-crypto)
3. [Layer 2 — SystemInfo HMAC (Anti-Tamper)](#layer-2--systeminfo-hmac-anti-tamper)
4. [Save Schema](#save-schema)
5. [Enchantment Resolution Chain](#enchantment-resolution-chain)
6. [EnchantCount — The Activation Bug](#enchantcount--the-activation-bug)
7. [Stat Display Rules](#stat-display-rules)
8. [Code Map](#code-map)
9. [Data Files](#data-files)
10. [HTTP API](#http-api)

---

## 🌍 Big Picture

```
  Browser (vanilla JS)        Python (stdlib)              Game on disk
  ─────────────────────       ──────────────────           ──────────────
                              ┌──────────────────┐
  GET  /api/state     ───────►│  server.py       │
  GET  /api/heroes    ◄───────│  (HTTP handler)  │      SaveFile_Live.es3
  POST /api/load      ───────►│      │           │◄───── (AES-128-CBC)
  POST /api/set_enchant──────►│      ▼           │
  POST /api/save      ───────►│  core/es3.py     │      core/aes_pure.py
  GET  /api/stat_first───────►│   (decrypt /     │      (fallback)
                              │    encrypt +     │
                              │    HMAC)         │      data/*.csv
                              │      │           │◄───── (game tables)
                              │      ▼           │
                              │  core/gamedata.py│      data/names.json
                              │   (validation +  │      data/strings.json
                              │    resolution)   │      data/enums.json
                              └──────────────────┘
                                       ▲
                                       │ used by
                              ┌────────┴────────┐
                              │  extract/ (one- │
                              │  shot, UnityPy) │
                              └─────────────────┘
```

Three rules govern the whole design:

1. **No magic values.** Every enchant traceable through the game tables.
2. **The serialized save is HMAC-consistent.** Recompute HMAC over the exact serialized bytes; verify the resulting encrypted copy separately from game acceptance.
3. **The editor never asks the game.** All data is pre-extracted into `data/` and shipped with the app; no runtime game access needed.

---

## 🔐 Layer 1 — ES3 Crypto

The save uses **Easy Save 3** (ES3), a Unity asset. The file is AES-128-CBC encrypted, with the key derived from a constant password and a per-save random IV via PBKDF2-HMAC-SHA1.

```
IV         = raw[0..16]                                          (random per save)
key        = PBKDF2-HMAC-SHA1(password, salt=IV, iters=100, dkLen=16)  # 16 bytes
ciphertext = raw[16:]
plaintext  = AES-128-CBC-decrypt(key, IV, ciphertext) → unpad PKCS7
```

**Constants** (originally identified in game version **1.00.17**, retained in this editor):

| Field | Value |
|---|---|
| ES3 password | `emuMqG3bLYJ938ZDCfieWJ` |
| PBKDF2 iterations | 100 |
| Key length | 16 bytes (AES-128) |
| IV length | 16 bytes |
| Padding | PKCS7 |

**Encryption on save** is the reverse — a fresh random IV is generated, the
plaintext is PKCS7-padded, encrypted, and prepended with the IV. The game
re-encrypts on every save with a new IV, so the editor matches that behavior.

**AES backend selection** at boot (`core/es3.py`):

```
prefer  cryptography          →  AES_BACKEND = "cryptography"   (fast, requires pip)
fallback core/aes_pure.py     →  AES_BACKEND = "pure-python"     (zero deps, NIST-validated)
```

The pure-Python AES in `core/aes_pure.py`:
- generates S-box via GF(2⁸) (avoids hand-typed S-box typos)
- matches Unity/.NET column-major byte order
- validated against the NIST FIPS-197 test vector

> 💡 The `es3.py` module is the only file that touches the on-disk save. Everything else operates on the un-nested Python dicts (`save.account`, `save.player`).

---

## 🛡 Layer 2 — SystemInfo HMAC (Anti-Tamper)

The game protects saves against tampering with an **HMAC-SHA256** over the
two inner JSON blobs and the Steam ID, joined by `|`. It re-validates the
HMAC on every load — if it mismatches, the game treats the save as
adulterated.

```
SystemInfo = Base64(
    HMAC-SHA256(
        key     = HMAC_KEY,
        message = UTF8(accountJson + "|" + playerJson + "|" + steamId)
    )
)
```

**Constants** (originally identified in game version **1.00.17**, retained in this editor):

| Field | Value |
|---|---|
| HMAC key (hex) | `93d9429e9b72f22fdb3413193763eaba1e8cfae995f61466a81a36a609d8e456` |
| HMAC key length | 32 bytes |
| Algorithm | HMAC-SHA256 |
| Separator | `|` (single pipe) |
| Encoding | base64 of raw 32-byte digest |

**The historical 1.00.17 validation algorithm** lived in `bal.mcr`. Two checks:

1. **HMAC check** — recompute and byte-compare. Mismatch → flag as tampered (`StartOption.kri`).
2. **Steam ID check** — `account.ownerSteamId` must match the currently logged-in Steam account (`StartOption.krj`). Mismatch → also flag.

**Editor implication:** on every save, the editor **recomputes `SystemInfo`**
using the exact bytes it just wrote. Because we hash the same string we
serialize, the result is deterministic and consistent with the game's
expectation. As a side note, our compact `json.dumps` differs from the
game's Newtonsoft output only in float notation (e.g. `2.7e+11` vs
`270000000000.0`) — semantically identical, harmless.

> 🔒 The HMAC key is **constant per game version**, derived from the binary at build time. To extract it on a new version, see [`docs/PORTING.md`](PORTING.md).

---

## 💾 Save Schema

After decryption + JSON parse, the save is:

```jsonc
// ES3 outer JSON
{
  "__type": "ES3Type + Dictionary<string, ES3Data>",
  "value": [
    ["AccountSaveData", { "__type": "string", "value": "<nested JSON>" }],
    ["PlayerSaveData",  { "__type": "string", "value": "<nested JSON>" }],
    ["SystemInfo",      { "__type": "string", "value": "<base64 HMAC>"        }]
  ]
}
```

After `core/es3.py` un-nests it, you have two editable Python dicts:

```
SaveFile.account       = json.loads(AccountSaveData.value)
SaveFile.player        = json.loads(PlayerSaveData.value)
SaveFile._es3          = original outer dict  (kept for re-serialization)
```

**`AccountSaveData` shape** (minimal):

```jsonc
{
  "ownerSteamId": "76561198xxxxxxxxx",
  // … other account-level fields (untouched by the editor)
}
```

**`PlayerSaveData` shape** (the interesting part):

```jsonc
{
  "heroSaveDatas":  [ { "heroKey": 101, "HeroLevel": 50, "equippedItemIds": ["11111", ...] }, ... ],
  "itemSaveDatas":  [ { "UniqueId": 11111, "ItemKey": 304111, "EnchantData": [...], ... }, ... ],
  // … other player fields (untouched)
}
```

### ItemKey encoding

`ItemKey` is a 6-digit ID with a hidden grade digit:

```
6 XY MMM
  │  └─── model id (00..99)
  └────── grade digit (0..9) → EGradeType
```

| Prefix | Category | `gear_group()` returns |
|---|---|---|
| `1xxxxx` | material (decoration / engraving / inscription / soulstone / crafting) | — |
| `3xxxxx`, `4xxxxx` | weapon | `WEAPON` |
| `5xxxxx` | armor | `ARMOR` |
| `6xxxxx` | accessory | `ACCESSORY` |

The `3`-digit model ID is the "base model" — that's where the name and icon
live. Save instances (e.g. `604111` = amulet, model `11`, grade `4` =
`IMMORTAL`) are resolved to the base via `GameData.base_key()`:

```python
k = int(itemkey)
modelo = (k % 10000 // 10) % 100
return (k // 10000) * 10000 + modelo
```

---

## 🧙 Enchantment Resolution Chain

Normal enchant editing uses a 5-step lookup through the bundled game tables.
Passing these checks establishes table consistency, not game/server acceptance.
Explicit Custom values mode skips only value range/step checks while retaining
material/stat/tier/enum identity and finite integer raw-value validation.

```
EnchantData[0..5]
  │
  │  SLOT_MATERIAL_TYPE  =  ["DECORATION", "DECORATION",
  │                         "ENGRAVING",  "ENGRAVING",
  │                         "INSCRIPTION", "INSCRIPTION"]
  ▼
slot type    (DECORATION | ENGRAVING | INSCRIPTION)
  │
  │  lookup MaterialInfoData.csv  →  MATERIALTYPE, StatModGroupKey
  ▼
MaterialInfoData
  │
  │  lookup StatModGroupInfoData.csv  for (StatModGroupKey, GearGroup)
  │  GearGroup = WEAPON | ARMOR | ACCESSORY (from item)  +  COMMON fallback
  ▼
StatModGroupInfoData
  │
  │  filter by (item's GearGroup, slot's COMMON fallback)
  │  enumerate MinTier..MaxTier  →  (StatModKey, Tier)  pairs
  ▼
StatModInfoData
  │
  │  for (StatModKey, Tier)  →  STATTYPE, MODTYPE, MinValue, MaxValue, Interval
  ▼
Value     ∈  [MinValue, MaxValue],  step = Interval
```

**`EnchantData` shape** (one slot):

```jsonc
{
  "StatModKey":  100101,        // references StatModInfoData
  "Tier":        5,             // 1..10
  "Value":       15,            // raw, post-display-scaling
  "RecipeType":  3,             // 3=DECORATION, 4=ENGRAVING, 5=INSCRIPTION
  "ModType":     0,             // 0=FLAT, 1=ADDITIVE, 2=MULTIPLICATIVE
  "MaterialKey": 110001,        // references MaterialInfoData
  "StatType":    1              // 1=AttackDamage (from enums.StatType)
}
```

An empty slot has these seven fields set to 0. Saves may carry additional
fields such as `EnchantVersion`; the server preserves them when editing or
clearing a slot. Applying unchanged known fields leaves the counter unchanged.

---

## 🐞 EnchantCount — The Activation Bug

The game stores the number of *active* enchants per type in a 3-element
array, **`EnchantCount[3]`** — and uses it as the trigger to actually
**apply the stat bonuses**:

```
EnchantCount = [filled(0)+filled(1),  // decoration count
                filled(2)+filled(3),  // engraving count
                filled(4)+filled(5)]  // inscription count
```

**Why this matters:** if you set an `EnchantData` slot but don't bump the
corresponding `EnchantCount`, the enchantment shows up in the UI but has
**no effect** in-game. This is a real bug found in legacy saves.

**The fix is two-fold** in `core/gamedata.py`:

1. **`recount_enchants(item)`** — recomputes `EnchantCount` from the actual
   filled slots. Called on every `/api/set_enchant` and as an auto-repair
   pass on `/api/save` (loops over **all** items, returns a count of fixed
   items to surface in the status message).
2. **`bump_applied(item, slot_index)`** — increments the
   `DecorationAppliedTotalCount` / `EngravingAppliedTotalCount` /
   `InscriptionAppliedTotalCount` field on the item. This is a separate
   counter the game uses for stats / achievements.

---

## 📐 Stat Display Rules

Raw values in the save are often **scaled** for display. The mapping is
intricate because:

- Some stats are FLAT in the save but render as percent (`/10`)
- Some stats are already in percent units (`/1`)
- 5 *variant stats* have BOTH a flat-integer (FLAT) and a percent
  (ADDITIVE) version, distinguished by MODTYPE, not STATTYPE

The full mapping is curated against taskbarhero.wiki data and lives in
`core/gamedata.py:STAT_DISPLAY`.

| Stat family | Raw → display |
|---|---|
| `AreaOfEffect`, `AttackSpeed`, `CriticalDamage`, `DamageReduction`, typed `*DamagePercent`, and the skill/typed damage increases in `STAT_DISPLAY` | `raw / 10`, show as `%` |
| Elemental/chaos resistances, `MaxBlockChance`, `MaxDodgeChance`, `AllElementalResistance`, and physical/elemental/chaos damage reduction | `raw / 1`, show as `%` |
| `DamageAddition`, `FireDamageAddition`, … | `raw / 10`, show as `%` |
| `AttackDamage`, `Armor`, `MaxHp`, `MovementSpeed`, `CriticalChance` (FLAT) | `raw / 1`, integer (no unit) |
| `AttackDamage`, `Armor`, `MaxHp`, `MovementSpeed`, `CriticalChance` (ADDITIVE) | `raw / 10`, show as `%` |
| `DamageAbsorption` | `raw / 10`, no percent suffix; raw 5 → 0.5 |
| `HpRegenPerSec` | `raw / 100`, no percent suffix; raw 125 → 1.25 |
| `AddHpPerHit`, `AddHpPerKill`, `BaseAttackCountReduction`, `Multistrike`, `ProjectileCount`, `AdditionalExp`, `IncreaseExpAmount` | `raw / 1`, integer (no unit) |

Implementation: `_display_rule(stattype, modtype) → (divisor, is_percent)`,
called by `to_display()` and `to_raw()`. Conversion uses `Decimal` and exact
integer ratios: `to_raw(to_display(x, s, m), s, m) == x` for supported raw
values. Fractional display values and interval steps are preserved, including
CooldownReduction raw 115 → 11.5 and DamageAbsorption step 1 → 0.1.
Non-finite numbers, lossy display conversion, and input that cannot produce
a whole raw integer are rejected instead of rounded or truncated. Normal
validation then checks table range and interval membership.

> 🎯 **Why the stat-first editor?** A single stat like `PhysicalDamagePercent` on `WEAPON` is granted by **multiple materials at different tiers** (tiers 2, 3, 6, 8, 9 verified in data). The old material-first editor hid the other tiers. The new editor unions all tiers across all materials into one dropdown — see `GameData.stat_first_options()`.

---

## 🗺 Code Map

```
saveEditor/
├── server.py                    # stdlib HTTP server, /api/* routes
│
├── core/
│   ├── es3.py                   # SaveFile load/save, AES, HMAC recompute
│   ├── aes_pure.py              # pure-Python AES-128-CBC fallback
│   └── gamedata.py              # GameData + all table lookups + validation
│
├── web/
│   ├── index.html               # heroes / equipment / enchants + save review dialog
│   ├── style.css                # "Enchanter's Workbench" theme
│   └── app.js                   # state machine, stat-first editor
│
├── data/                        # game data (portable)
│   ├── tables/*.csv             # 15 CSVs from sharedassets0.assets
│   ├── names.json               # 534 ItemKey → display name
│   ├── strings.json             # 6 HeroName_* → display name
│   ├── enums.json               # StatType / MODTYPE / ERecipeType / EMaterialType / EGradeType
│   ├── icon_map.json
│   ├── version.json             # source version, hashes, counts, verification limits
│   └── icons/*.png              # 530 item / material icons
│
├── extract/                     # one-shot, needs UnityPy + the game
│   ├── extract_tables.py        # sharedassets0 TextAssets → CSV
│   ├── extract_enums.py         # Il2CppDumper dump.cs → enums.json
│   ├── extract_localization.py  # localization bundles → names.json + strings.json
│   ├── extract_sprites.py       # sharedassets0 Sprites → icons/*.png
│   ├── extract_all.py           # preflight + staged extraction + catalog checks + publication
│   ├── common.py                # shared paths and CLI arguments
│   └── test_extraction.py       # failure/rollback tests
│
├── tests/                       # decimal/validation and HTTP encrypted-fixture tests
│
└── docs/                        # you are here
```

### Key functions, at a glance

| Module | Function | Purpose |
|---|---|---|
| `core/es3.py` | `es3_decrypt` / `es3_encrypt` | AES-CBC + PKCS7 |
| `core/es3.py` | `SaveFile.save` | Serializes inner JSON, recomputes HMAC, re-encrypts, writes `.es3` + `.bak` |
| `core/gamedata.py` | `GameData.base_key` | Resolve save instance → base model (for name/icon lookup) |
| `core/gamedata.py` | `GameData.grade_id` / `grade_name` | ItemKey → EGradeType |
| `core/gamedata.py` | `GameData.slot_allowed` | Whether the item's grade allows this slot |
| `core/gamedata.py` | `GameData.recount_enchants` | Rebuild `EnchantCount[3]` from filled slots (activates effects) |
| `core/gamedata.py` | `GameData.stat_first_options` | Union (stat, tier) across all materials for a slot |
| `core/gamedata.py` | `GameData.build_enchant` | Build a complete `EnchantData` dict with numeric IDs |
| `core/gamedata.py` | `GameData.validate_enchant` | Type, group, tier, enum IDs, finite integer raw value, range, interval |
| `core/gamedata.py` | `GameData.to_display` / `to_raw` | Apply / reverse stat display scaling |

---

## 📊 Data Files

All data is **English-only** and **portable** (ships with the app, no runtime
game access required).

### `data/tables/*.csv`

CSV files extracted from the 1.2.4 `sharedassets0.assets` via `extract/extract_tables.py`.

| File | Rows | Used by |
|---|---|---|
| `MaterialInfoData.csv` | 143 | `GameData.materials` — material ItemKey → type + StatModGroup |
| `StatModInfoData.csv` | 620 | `GameData.statmod` — (StatModKey, Tier) → range + STATTYPE/MODTYPE |
| `StatModGroupInfoData.csv` | 474 | `GameData.groups` — StatModGroupKey → (GearGroup, StatModKey, MinTier..MaxTier) |
| `GradeInfoData.csv` | 10 | `GameData.grades_by_name` — grade → slot count per type |
| `GearInfoData.csv` | 5954 | `GameData.gear` — gear base stats (read but not currently surfaced in UI) |
| `HeroInfoData.csv` | 6 | `GameData.hero_info` — hero key → class type |
| `AttributeGroupInfoData.csv` | 8 | not loaded (reserved for future) |
| `CurrencyInfoData.csv` | 1 | not loaded |
| `GearTypeInfoData.csv` | 16 | not loaded |
| `GearTypeScaleInfoData.csv` | 20 | not loaded |
| `ItemTypeScaleInfoData.csv` | 2 | not loaded |
| `InventoryInfoData.csv` | 260 | not loaded (future: inventory editor) |
| `RuneInfoData.csv` / `RuneLevelInfoData.csv` | 248 / 833 | not loaded (future: rune editor) |
| `SynthesisRecipeInfoData.csv` | 587 | not loaded (future: recipe editor) |

### `data/names.json`

ItemKey → display name. 534 entries. Used for every item and material name in the UI.

### `data/strings.json`

`HeroName_<key>` → display name. 6 entries (one per hero). The only key
pattern used; other Unity localization keys are not loaded to keep the
shipped data lean.

### `data/enums.json`

5 enums parsed from `Il2CppDumper`'s `dump.cs`:

| Enum | Members | Used for |
|---|---|---|
| `StatType` | 65 | `EnchantData.StatType` ID ↔ name (e.g. `1` = `AttackDamage`) |
| `MODTYPE` | 3 | `EnchantData.ModType` ID ↔ name (FLAT / ADDITIVE / MULTIPLICATIVE) |
| `ERecipeType` | 10 | `EnchantData.RecipeType` (3=DECORATION, 4=ENGRAVING, 5=INSCRIPTION) |
| `EMaterialType` | 8 | MaterialInfoData type validation |
| `EGradeType` | 11 | ItemKey grade digit → COMMON / UNCOMMON / … / COSMIC / NONE |

### `data/icons/*.png`

530 PNG icons from the game's sprite atlas, named by ItemKey. Naming
convention in source: `Item_<ItemKey>` for materials, `<TYPE>_<GearKey>` for
equipment. Shared icons follow `ItemInfoData.IconPath`. Four localized keys
(`150102`, `150108`, `150109`, `150110`) have no item definition or icon in
this build; this coverage limit is recorded in `version.json`.

### `data/version.json`

Generated by the full extraction command. Includes `gameVersion`, `steamBuild`,
source SHA-256 hashes, extractor version, counts, and verification scope.
`verification.inGameVerified` remains `false`: extraction and catalog checks
cannot prove an edited save loads in the game.

---

## 🌐 HTTP API

All endpoints under `/api/*`. State (loaded save) lives in module-level
singleton `State.save` + `State.path`.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/` | — | `web/index.html` |
| GET | `/app.js` | — | JS bundle |
| GET | `/style.css` | — | CSS bundle |
| GET | `/icons/<key>` | — | PNG (key resolved via `base_key()`) |
| GET | `/api/state` | — | `{loaded, path, aesBackend, saveVersion, dataVersion}` |
| GET | `/api/heroes` | — | `{heroes:[…], path, saveVersion, dataVersion}` — must have a save loaded |
| GET | `/api/stat_first?item=<key>&slot=<i>` | — | `{slot, gearGroup, options:[…]}` — stat-first dropdown data |
| POST | `/api/load` | `{path?}` | `{heroes, path, saveVersion, dataVersion}` — load + decrypt .es3 |
| POST | `/api/set_enchant` | `{uniqueId, slot, materialKey, statModKey, tier, value, clear?, force?}` | full item payload with validation errors; `value` is in display units |
| POST | `/api/save` | `{}` | `{ok, path, backup, fixed}` — recount + encrypt + write |

### `/api/set_enchant` validation chain

1. Require a loaded save, an existing item, and slot index `0..5`.
2. If `clear: true`, clear an existing slot and recount; absent slots are a no-op.
3. Require `slot_allowed(itemKey, slot)` for additions/edits.
4. Convert display input to an exact raw integer; reject non-finite or unrepresentable values. Build the enchant using table enum IDs.
5. Always validate material/group/tier and enum IDs. Validate range and interval too, unless explicit `force`/Custom values is enabled.
6. Only after validation, extend the slot array if needed and apply the change. An identical enchant is a no-op; a changed enchant increments its applied counter and recounts.
7. Return the updated item payload. These edits remain in memory until `/api/save`.

The browser shows current values in the inline editor, tracks staged slot
changes, and requires a before/after review plus **Save with backup** before
calling `/api/save`. Reloading with staged edits and clearing an enchant have
their own confirmation dialogs.

### `/api/save` flow

1. Loop over **all** `itemSaveDatas` and call `recount_enchants()` — counts any items whose `EnchantCount` was fixed
2. `SaveFile.save(path, backup=True)` — serializes + HMAC + encrypt + write `.bak` + write `.es3`
3. Return `{ok, path, backup, fixed}` so the UI can surface "X counter(s) repaired"

Saving repairs counters but does not revalidate every existing enchant against
the current tables. Existing validation errors are surfaced in item payloads;
Custom values can intentionally leave values outside the table's range/step.

### Verification

Run `python -B -m unittest discover -s tests -v` (27 tests) and
`python -B -m unittest discover -s extract -p 'test_*.py' -v` (5 tests).
Coverage includes exact decimal conversion across legal table values, interval
and enum guards, Custom values identity checks, rejection without mutation, encrypted-fixture save/reload and
backup bytes, and extraction failure/rollback behavior. Browser verification
uses a disposable encrypted copy. A native game reload is separate evidence.

---

## 🔍 Further Reading

- **[`docs/PORTING.md`](PORTING.md)** — what to do when the game updates
- **[`README.md`](../README.md)** — quick start, features, project layout
