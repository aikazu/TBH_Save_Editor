# 🔥 TBH Save Editor

> **The Enchanter's Workbench** — edit Decoration, Engraving, and Inscription
> slots on your heroes' equipped gear with **full game-table validation** and
> **automatic anti-tamper HMAC** on save. Runs locally in your browser, no
> upload, no telemetry.

---

## ✨ Features

- ✅ **Validated against the real game tables** — every enchant you create is game-legal
- 🔐 **Local AES-128-CBC + HMAC-SHA256** — the save never leaves your machine
- 📦 **Zero dependencies** — pure Python stdlib; a single optional `cryptography` for speed
- 🧮 **Auto-recomputes `SystemInfo`** on save (anti-tamper check still passes in-game)
- 🎯 **Stat-first editor** — see every tier of every stat, not just what one material happens to grant
- 🩹 **Auto-repair** for legacy broken `EnchantCount` (activates effects that look right but do nothing)

---

## 🚀 Quick Start

**Prerequisites:** Python 3. Nothing else. No `pip install`.

```powershell
cd TBH_Save_Editor
python server.py
```

Opens `http://127.0.0.1:8765` in your browser. The save path is auto-filled.

### 5-step workflow

| # | Action | Result |
|---|--------|--------|
| 1 | Click **Load** | Save decrypted, heroes populated |
| 2 | Pick a **hero** | See equipped items (icon + name) |
| 3 | Click an **item** | 6 enchant slots: 2 Decoration, 2 Engraving, 2 Inscription |
| 4 | **Edit** a slot | Pick stat → tier → value (defaults to MAX) |
| 5 | **Save to Game** | Writes `.es3` (with `.bak` backup) and recomputes `SystemInfo` |

> ⚠️ **Close the game before saving** — otherwise it overwrites the file on exit.

---

## 🏗 Architecture

```
                ┌───────────────────────────────────────────────┐
                │            SaveFile_Live.es3                  │
                │     AES-128-CBC · PBKDF2-SHA1 · PKCS7         │
                └────────────────────────┬──────────────────────┘
                                         │ decrypt
                                         ▼
        ┌──────────────────────────────────────────────────────────┐
        │  ES3 outer JSON                                           │
        │  { AccountSaveData, PlayerSaveData, SystemInfo }         │
        │      ↑                       ↑                  ↑         │
        │  "Account"               "Player"         HMAC base64    │
        │  (steamId, ...)          (heroes, items,   of (acc|ply|   │
        │                          enchants, ...)    steam)         │
        └────────────────────────┬─────────────────────────────────┘
                                 │  un-nest → editable dicts
                                 ▼
   ┌───────────────────────────────────────────────────────────────┐
   │  Enchantment editor  (core/gamedata.py)                       │
   │                                                               │
   │    MaterialInfo ──→ StatModGroup ──→ StatMod (per Tier)        │
   │        │                │                 │                   │
   │        └─ recipe type must match slot type ─┘                 │
   │                                                               │
   │    + EnchantCount[3] = active slot count per type (ACTIVATES) │
   │    + validate: type match, stat mod for gear group, range,    │
   │      tier, interval                                          │
   └───────────────────────────────────────────────────────────────┘
                                 │
                                 │  serialize (compact JSON)
                                 ▼
        ┌──────────────────────────────────────────────────────────┐
        │  Recompute SystemInfo HMAC                                │
        │  Re-encrypt with fresh IV → write .es3 (+ .es3.bak)       │
        └──────────────────────────────────────────────────────────┘
```

Read the deep dive in **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**.

---

## 📂 Project Layout

```
saveEditor/
├── server.py            # local web server (stdlib, zero deps)
├── core/                # Python — crypto + game logic
│   ├── es3.py           # AES-CBC encrypt/decrypt + SystemInfo HMAC
│   ├── aes_pure.py      # AES-128 in pure Python (NIST-validated fallback)
│   └── gamedata.py      # game tables loader + enchant validation engine
├── web/                 # frontend (vanilla HTML/CSS/JS)
│   ├── index.html
│   ├── style.css        # "Enchanter's Workbench" theme
│   └── app.js
├── data/                # game data, portable — ships with the app
│   ├── tables/*.csv     # StatModInfoData, MaterialInfoData, …
│   ├── names.json       # ItemKey → display name (item / material)
│   ├── strings.json     # HeroName_<key> → hero display name
│   ├── enums.json       # StatType / MODTYPE / ERecipeType / EMaterialType / EGradeType
│   ├── icon_map.json
│   └── icons/*.png      # 511 item / material icons
├── docs/                # this guide + architecture + porting
└── extract/             # one-shot scripts that GENERATE data/ (need UnityPy + the game)
```

---

## 🔍 How Validation Works

Every enchant you create must trace a complete chain through the game tables:

```
EnchantData[0..5]   →  slot type (DECORATION | ENGRAVING | INSCRIPTION)
MaterialKey          →  MaterialInfoData: MATERIALTYPE + StatModGroupKey
StatModGroupKey
  + GearGroup        →  StatModGroupInfoData: list of (StatModKey, MinTier..MaxTier)
StatModKey + Tier    →  StatModInfoData: STATTYPE, MODTYPE, MinValue, MaxValue, Interval
Value                ∈  [MinValue, MaxValue], step = Interval
```

`GearGroup` (`WEAPON` / `ARMOR` / `ACCESSORY` / `COMMON`) is derived from the
`ItemKey` prefix (`3xxxxx` = weapon, `5xxxxx` = armor, `6xxxxx` = accessory).
The editor rejects any combination the game itself would reject, so the result
is always game-legit.

> 💡 **Stat display scaling**: most stats are stored as `raw_value * 10` and
> displayed as percentages. The 5 *variant stats* (`AttackDamage`, `Armor`,
> `MaxHp`, `MovementSpeed`, `CriticalChance`) have a flat-integer variant
> (FLAT) and a percent variant (ADDITIVE), resolved per-MODTYPE. The mapping
> is in `core/gamedata.py:STAT_DISPLAY` and is curated against the
> taskbarhero.wiki data.

---

## 🔄 Re-Extracting Data

Data in `data/` was extracted from game version **1.00.17**. When the game
updates and the values change, re-extract on a machine with the game +
`pip install UnityPy`:

```powershell
python extract/extract_all.py
```

| If the game changes… | Do this |
|---|---|
| Table values / names / icons | `python extract/extract_all.py` |
| `SystemInfo` HMAC key | See **[`docs/PORTING.md`](docs/PORTING.md)** — runtime key extraction via `dtcore.dll` (F8 hotkey) |
| ES3 password | Search `stringliteral.json` in the dump for ~22-char strings near the save manager; usually doesn't change |

---

## 🛠 Tech Stack

| Layer | Tech |
|---|---|
| Server | Python 3 stdlib (`http.server`, `socketserver`) |
| Crypto | AES-128-CBC + PBKDF2-HMAC-SHA1 + HMAC-SHA256 |
| Crypto fallback | Pure-Python AES (validated against NIST FIPS-197 vector) |
| Frontend | Vanilla HTML / CSS / JS, no framework, no build step |
| Data extraction | `UnityPy` (one-shot, offline only) |

---

## 📚 Documentation

- **[`docs/README.md`](docs/README.md)** — index of all docs
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — system design, data formats, validation
- **[`docs/PORTING.md`](docs/PORTING.md)** — porting to a new game version (HMAC key, RE workflow, re-extract)

---

## ⚠️ Disclaimer

This is a personal single-player save editor. The game is single-player and
offline; no online service is touched. Use at your own risk — always keep the
`.es3.bak` backup the app creates on every save.
