# AGENTS.md — TBH Save Editor

Local-only web tool that edits enchantments (Decoration / Engraving / Inscription)
on heroes' equipped gear in a **Taskbar Hero** (`SaveFile_Live.es3`) save file.
Python 3 stdlib HTTP server + vanilla HTML/CSS/JS frontend. **Zero runtime
dependencies.** Edits are validated against pre-extracted game tables and the
`SystemInfo` HMAC is recomputed on save. Bundled tables target **1.2.8**, Steam
build **25454993**; in-game edited-save reload is not verified for this update.
Read [`README.md`](README.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
before touching anything beyond trivial edits.

> ⚠️ **DWYOR.** This modifies an encrypted save. Crafted/dropped items are also
> validated **server-side** by the game, so edits can still get a save rejected
> or an account flagged. Never run the editor against a save with no backup.

---

## Run

```powershell
python server.py              # http://127.0.0.1:8765  (opens browser automatically)
$env:TBH_NO_BROWSER=1         # set this to skip auto-opening the browser
```

- No `pip install`, no build step, no bundler. Pure Python 3 stdlib.
- Optional speed-up only: `pip install cryptography` → AES backend switches to
  it automatically. Without it, the pure-Python AES fallback
  (`core/aes_pure.py`, validated against NIST FIPS-197) is used.
- Run `python -B -m unittest discover -s tests -v` (27 core/HTTP tests) and
  `python -B -m unittest discover -s extract -p 'test_*.py' -v` (5 extraction tests).
  No linter or formatter is configured. Check the browser workflow on a disposable
  encrypted copy: load → hero → equipment → edit → review → save with backup.
  Verify exact round-trips and report browser, encrypted-copy, and in-game
  reload evidence separately. Do not claim game acceptance from local tests.

---

## Project layout

```
server.py            # stdlib HTTP server + /api/* routes. State singleton (State.save / State.path).
core/
  es3.py             # ONLY file that touches the on-disk save. AES-CBC + SystemInfo HMAC.
  aes_pure.py        # Pure-Python AES-128 fallback. Do not edit unless NIST vectors still pass.
  gamedata.py        # GameData: table loader + enchant validation engine + stat display rules.
web/                 # Vanilla frontend (no framework, no build). index.html / style.css / app.js.
data/                # Portable game data (ships with app). DO NOT edit by hand — see extract/.
  tables/*.csv       # Game tables extracted from sharedassets0.assets.
  names.json         # ItemKey -> display name (534).
  strings.json       # HeroName_<key> -> hero display name (6).
  enums.json         # StatType / MODTYPE / ERecipeType / EMaterialType / EGradeType.
  icon_map.json + icons/*.png  # 530 icons, including shared-sprite aliases.
  version.json       # 1.2.8/build 25454993, source hashes/counts; data extraction only.
tests/               # Core numeric/validation and HTTP encrypted-fixture tests.
extract/             # ONE-SHOT scripts that GENERATE data/. Need UnityPy + the game installed.
docs/                # README, ARCHITECTURE, PORTING.
```

---

## Architecture boundaries (respect these)

1. **`core/es3.py` is the only module that reads/writes the `.es3` file.**
   Everything else operates on the un-nested Python dicts
   (`SaveFile.account`, `SaveFile.player`). Do not parse/serialize the save
   elsewhere.
2. **No magic values in enchant data.** Every enchant must trace the full
   resolution chain through the game tables — see "Enchantment Resolution Chain"
   in `docs/ARCHITECTURE.md`. Normal edits go through `GameData.build_enchant()` +
   `GameData.validate_enchant()`. Explicit Custom values mode skips only value
   range/step checks; material/stat/tier/enum identity, numeric conversion,
   and slot/grade guards still apply.
3. **The save must be byte-stable + HMAC-consistent.** On save, `SaveFile.save`
   recomputes `SystemInfo` over the exact bytes it just wrote, then re-encrypts
   with a **fresh random IV** (matching the game's behavior). Do not change the
   HMAC composition (`account|player|steamId`, joined by `|`) or the JSON
   serialization without understanding the impact.
4. **`data/` is generated, not hand-edited.** Use
   `python -B extract/extract_all.py --dump-path 'C:\path\to\dump.cs' --game-version 1.2.8 --steam-build 25454993`
   with UnityPy, the game, and its matching dump. `--game-dir` overrides the
   standard Windows Steam path. Extraction stages and verifies the catalog
   before replacing `data/`; `data/version.json` records provenance and limits.

---

## Critical correctness rules (easy to break)

- **`EnchantCount[3]` activates the effect.** Setting an `EnchantData` slot
  without bumping the matching `EnchantCount` makes the enchant appear in the
  UI but do **nothing** in-game. Always call `recount_enchants()` after editing
  slots, and `bump_applied()` for the `*AppliedTotalCount` counter.
  `/api/save` also runs a repair pass over **all** items.
- Preserve unrecognized enchant fields such as `EnchantVersion` when updating
  or clearing known fields. Applying an unchanged enchant must not increase counters.
- **Stat display scaling is curated, not uniform.** Display uses raw integers
  divided by 1, 10, or 100; 5 *variant stats* (`AttackDamage`, `Armor`, `MaxHp`,
  `MovementSpeed`, `CriticalChance`) have FLAT vs ADDITIVE variants resolved by
  **MODTYPE**, not STATTYPE. The full mapping is `STAT_DISPLAY` /
  `_display_rule()` in `core/gamedata.py`. Round-trip must hold:
  `to_raw(to_display(x, stattype, modtype), stattype, modtype) == x`.
  Preserve fractional display values and steps (raw 115 → 11.5, raw 5 → 0.5).
  Reject non-finite values and fractions that cannot produce an integer raw
  value; never truncate with `int()` or `//`. Normal edits also validate enum
  consistency and interval membership before mutating an item.
- **`slot` index ordering is load-bearing.** `SLOT_MATERIAL_TYPE` =
  `[DECO, DECO, ENG, ENG, INSC, INSC]` and `server.py:SLOT_LABELS` mirrors it.
  Changing one without the other breaks the UI.
- **Crypto and table provenance are separate.** The ES3 password, PBKDF2 params
  (iters=100, dkLen=16), and HMAC key in `core/es3.py` retain their historical
  1.00.17 provenance. Tables/enums/assets in `data/` target 1.2.8. When the game
  updates, follow [`docs/PORTING.md`](docs/PORTING.md)
  (decrypt → verify HMAC → re-extract → smoke-test), not a blind edit.

---

## Coding conventions in this repo

- **Python:** stdlib only. Module docstrings explain the "why". `GameData`
  methods are short and single-purpose. CSVs read with `encoding="utf-8-sig"`.
  Enum name↔id maps are built from `data/enums.json`.
- **Frontend:** `"use strict"`, no framework, no build step. `app.js` uses a
  small `$`/`el` helper set and a `STATE` object; talks to the server only via
  the `api()` helper (`fetch` + JSON). Match the existing terse style; do not
  introduce npm/bundlers.
- **Comments:** explain WHY, not WHAT (the code already shows what). Keep
  commented-out code out of commits.
- **Logging:** `server.py` prints a banner + status panel to the console with a
  minimal ANSI helper (`class C`) that auto-disables color when not a TTY or
  when `NO_COLOR` is set. Keep server logging human-readable and TTY-safe.

---

## Before changing sensitive areas, read

- **`docs/ARCHITECTURE.md`** — layers, save schema, enchant resolution chain,
  `EnchantCount` bug, stat display rules, code map, HTTP API reference.
- **`docs/PORTING.md`** — required when the game updates (HMAC key extraction
  via `dtcore.dll`, RE workflow with Ghidra/Il2CppDumper, re-extract pipeline).
