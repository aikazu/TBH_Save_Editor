# 📚 Documentation

Welcome to the **TBH Save Editor** docs. Start here, then dive into the doc
that matches your question.

---

## 🗺 Where to Go

| If you want to… | Read |
|---|---|
| Run the editor | [`../README.md`](../README.md) — Quick Start, 5-step workflow |
| Understand the system design | **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — layers, save schema, validation chain |
| Update the editor for a new game version | **[`PORTING.md`](PORTING.md)** — checklist, HMAC key extraction, re-extract |
| Modify the code or extend the editor | [`ARCHITECTURE.md`](ARCHITECTURE.md) — code map + key functions |

---

## 📖 The Docs

### [`ARCHITECTURE.md`](ARCHITECTURE.md)

The system design deep dive. Covers:

- 🌍 Big-picture architecture (browser ↔ server ↔ disk)
- 🔐 ES3 crypto layer (AES-128-CBC + PBKDF2)
- 🛡 SystemInfo HMAC anti-tamper layer
- 💾 Save schema (ES3 outer JSON, Account/Player inner JSON)
- 🧙 Enchantment resolution chain (the 5-step table lookup)
- 🐞 The `EnchantCount` activation bug
- 📐 Stat display rules (raw → display scaling)
- 🗺 Code map + key functions
- 📊 Data file inventory
- 🌐 HTTP API reference

**Read this first** if you want to understand *how* the editor works.

### [`PORTING.md`](PORTING.md)

The action-oriented guide for when **Taskbar Hero** updates. Covers:

- ⚡ TL;DR porting checklist
- 🔐 ES3 crypto (and how to find a new password)
- 🛡 SystemInfo HMAC (and the live key extraction)
- 🔑 Extracting the HMAC key via `dtcore.dll` (F8 hotkey)
- 🔍 Reverse-engineering workflow (Ghidra + Il2CppDumper)
- 🔄 Re-extracting data (tables, names, icons)
- 📁 File map of the broader RE / trainer / editor tooling

**Read this** when the game updates and something broke.

---

## 🧭 Conventions Used in These Docs

- **Monospaced** for file paths, commands, and identifiers: `core/es3.py`
- **Tables** for structured reference data
- **Code blocks** with language hints: ` ```powershell `, ` ```cpp `, ` ```jsonc `
- **Emoji anchors** for scannability — section headers start with a stable
  icon (🔐 crypto, 🛡 anti-tamper, 💾 storage, 🧙 game logic, 🐞 bugs,
  📐 rules, 🗺 maps, 📊 data, 🌐 API, 🔄 porting, 📚 reading)
- **Callouts** use `> ⚠️` for warnings, `> 💡` for tips, `> 🎯` for
  rules-of-thumb
- **Cross-references** use relative paths so the docs work both on
  GitHub and in a local viewer

---

## 🔗 Project Links

- [Main README](../README.md)
- [Source root](../)
