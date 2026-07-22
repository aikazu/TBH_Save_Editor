"""
TBH Save Editor - local web server (stdlib, zero dependencies).
Edits the enchantments (decoration/engraving/inscription) of heroes' equipped items,
with validation against the game tables, and recomputes the SystemInfo on save.

Usage:  python server.py        (opens http://127.0.0.1:8765 in the browser)
"""
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser

from core import es3, gamedata

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
ICONS = os.path.join(DATA, "icons")
PORT = 8765

GD = gamedata.GameData(DATA)
# UI-facing slot labels. DEPENDS on core/gamedata.SLOT_MATERIAL_TYPE order.
SLOT_LABELS = ["Decoration", "Decoration", "Engraving", "Engraving", "Inscription", "Inscription"]


class State:
    save = None
    path = None


def default_save_path():
    up = os.environ.get("USERPROFILE", "")
    p = os.path.join(up, "AppData", "LocalLow", "TesseractStudio", "TaskbarHero", "SaveFile_Live.es3")
    return p if os.path.exists(p) else ""


# ---------------- serialization for the UI ----------------
def item_payload(it):
    ikey = it["ItemKey"]
    enchants = []
    for i, ed in enumerate(it.get("EnchantData", [])[:6]):
        filled = ed.get("MaterialKey", 0) != 0
        e = {"slot": i, "type": GD.slot_material_type(i), "label": SLOT_LABELS[i],
             "filled": filled, "allowed": GD.slot_allowed(ikey, i)}
        if filled:
            si = GD.statmod.get((str(ed.get("StatModKey")), str(ed.get("Tier"))))
            mtp = si["MODTYPE"] if si else "FLAT"
            stt = si["STATTYPE"] if si else ""
            is_pct = GD.is_percent(stt, mtp)
            e.update({
                "materialKey": ed["MaterialKey"],
                "materialName": GD.name(ed["MaterialKey"]),
                "materialIcon": "/icons/%s" % ed["MaterialKey"] if GD.has_icon(ed["MaterialKey"]) else None,
                "statModKey": ed.get("StatModKey"),
                "tier": ed.get("Tier"),
                "value": GD.to_display(ed.get("Value", 0), stt, mtp),
                "isPercent": is_pct,
                "stat": GD.pretty_stat(si["STATTYPE"]) + (" %" if is_pct else "") if si else "?",
                "errors": GD.validate_enchant(i, ikey, ed),
            })
        enchants.append(e)
    return {
        "uniqueId": str(it["UniqueId"]),
        "itemKey": ikey,
        "name": GD.name(ikey),
        "icon": "/icons/%s" % ikey if GD.has_icon(ikey) else None,
        "group": GD.gear_group(ikey),
        "grade": GD.grade_name(ikey),
        "maxSlots": GD.max_slots(ikey),
        "enchantCount": it.get("EnchantCount"),
        "enchants": enchants,
    }


def heroes_payload():
    sf = State.save
    items_by_uid = {str(it["UniqueId"]): it for it in sf.player.get("itemSaveDatas", [])}
    out = []
    for h in sf.player.get("heroSaveDatas", []):
        slots = []
        for uid in h.get("equippedItemIds", []):
            if str(uid) == "0" or str(uid) not in items_by_uid:
                continue
            slots.append(item_payload(items_by_uid[str(uid)]))
        out.append({"heroKey": h.get("heroKey"), "level": h.get("HeroLevel"),
                    "name": GD.hero_name(h.get("heroKey")),
                    "klass": GD.hero_class(h.get("heroKey")), "items": slots})
    return {"heroes": out, "path": State.path}


def find_item(uid):
    for it in State.save.player.get("itemSaveDatas", []):
        if str(it["UniqueId"]) == str(uid):
            return it
    return None


# ---------------- HTTP handler ----------------
class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        if not os.path.exists(path):
            return self._send(404, {"error": "not found"})
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def log_message(self, *a):
        pass  # silent logging

    # ---- GET ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        if p == "/" or p == "/index.html":
            return self._file(os.path.join(WEB, "index.html"), "text/html; charset=utf-8")
        if p == "/app.js":
            return self._file(os.path.join(WEB, "app.js"), "application/javascript; charset=utf-8")
        if p == "/style.css":
            return self._file(os.path.join(WEB, "style.css"), "text/css; charset=utf-8")
        if p.startswith("/icons/"):
            key = GD.base_key(p[len("/icons/"):].replace(".png", ""))
            return self._file(os.path.join(ICONS, "%s.png" % key), "image/png")
        if p == "/api/state":
            return self._send(200, {"loaded": State.save is not None, "path": State.path or default_save_path(),
                                    "aesBackend": es3.AES_BACKEND})
        if p == "/api/heroes":
            if not State.save:
                return self._send(400, {"error": "No save loaded"})
            return self._send(200, heroes_payload())
        if p == "/api/stat_first":
            # Stat-first editor: merges tiers across all materials of the slot's type.
            item_key = int(q["item"][0])
            slot = int(q.get("slot", ["0"])[0])
            gg = GD.gear_group(item_key)
            return self._send(200, {"slot": slot, "gearGroup": gg,
                                   "options": GD.stat_first_options(slot, gg)})
        return self._send(404, {"error": "Unknown route"})

    # ---- POST ----
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        p = u.path
        if p == "/api/load":
            path = body.get("path") or default_save_path()
            try:
                State.save = es3.SaveFile.load(path)
                State.path = path
            except Exception as e:
                return self._send(400, {"error": "Failed to load: %s" % e})
            return self._send(200, heroes_payload())
        if p == "/api/set_enchant":
            it = find_item(body["uniqueId"])
            if not it:
                return self._send(404, {"error": "Item not found"})
            slot = int(body["slot"])
            while len(it.get("EnchantData", [])) <= slot:
                it.setdefault("EnchantData", []).append(GD.empty_enchant())
            if body.get("clear"):
                it["EnchantData"][slot] = GD.empty_enchant()
                GD.recount_enchants(it)  # keep EnchantCount consistent
                return self._send(200, item_payload(it))
            if not GD.slot_allowed(it["ItemKey"], slot):
                return self._send(400, {"error": "Item grade %s does not allow this slot" % GD.grade_name(it["ItemKey"])})
            try:
                statmodkey = int(body["statModKey"])
                tier = int(body["tier"])
                # frontend sends display-scale value; convert back to raw save value
                si = GD.statmod.get((str(statmodkey), str(tier)))
                mtp = si["MODTYPE"] if si else "FLAT"
                stt = si["STATTYPE"] if si else ""
                raw_value = GD.to_raw(int(body["value"]), stt, mtp)
                ed = GD.build_enchant(slot, int(body["materialKey"]), statmodkey, tier, raw_value)
            except Exception as e:
                return self._send(400, {"error": str(e)})
            errs = GD.validate_enchant(slot, it["ItemKey"], ed)
            if errs:
                return self._send(400, {"error": "; ".join(errs)})
            it["EnchantData"][slot] = ed
            GD.bump_applied(it, slot)     # +1 to the type's AppliedTotalCount
            GD.recount_enchants(it)       # EnchantCount = active slots per type (ACTIVATES the effect in-game)
            return self._send(200, item_payload(it))
        if p == "/api/save":
            if not State.save:
                return self._send(400, {"error": "Nothing loaded"})
            # repair inconsistent EnchantCount on ALL items (fixes legacy bugs where an
            # enchantment showed up but had no effect).
            fixed = 0
            for it in State.save.player.get("itemSaveDatas", []):
                before = it.get("EnchantCount")
                GD.recount_enchants(it)
                if it["EnchantCount"] != before:
                    fixed += 1
            try:
                State.save.save(State.path, backup=True)
            except Exception as e:
                return self._send(500, {"error": str(e)})
            return self._send(200, {"ok": True, "path": State.path, "backup": State.path + ".bak", "fixed": fixed})
        return self._send(404, {"error": "Unknown route"})


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


# ---------------- console prettifier ----------------
class C:
    """Minimal ANSI colour helper. Disabled when stdout isn't a TTY."""
    _on = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None and os.environ.get("TERM", "") != "dumb"

    @classmethod
    def _wrap(cls, code, text):
        if not cls._on:
            return text
        return "\x1b[%sm%s\x1b[0m" % (code, text)

    @staticmethod
    def bold(t):    return C._wrap("1", t)
    @staticmethod
    def dim(t):     return C._wrap("2", t)
    @staticmethod
    def cyan(t):    return C._wrap("36", t)
    @staticmethod
    def green(t):   return C._wrap("32", t)
    @staticmethod
    def yellow(t):  return C._wrap("33", t)
    @staticmethod
    def magenta(t): return C._wrap("35", t)
    @staticmethod
    def red(t):     return C._wrap("31", t)


BANNER = r"""
 ____  ____  _____   _   _   _____    ____  _____  ____  _____  ____
|  _ \|  _ \|  ___| | |_| | / ____|  / __ \|  __ )/ __ \|  __ )/ __ \
| |_) | |_) | |_    |  _  || (___   | |  | |  __ \ |  | |  __ \ |  | |
|  _ <|  _ <|  _|   | | | | \___ \  | |  | | |_/ / |  | | |_/ / |  | |
|_| \_\_| \_\_|     |_| |_| _____/  |_|  |_|_____/|____/|____/ |_|  |_|

                       Enchantment Editor for TaskbarHero
"""


def print_banner():
    """Print the ASCII banner in cyan/bold."""
    lines = BANNER.splitlines()
    for line in lines:
        if "Enchantment Editor" in line:
            print(C.dim(line))
        elif line.strip():
            print(C.cyan(C.bold(line)))
    print()


def print_status_panel(url, save_path, aes_backend):
    """Print a tidy box with server status info."""
    aes_label = "pure-python (fallback, no deps)" if "pure" in aes_backend.lower() else aes_backend
    save_label = save_path if save_path else "(auto-detect: AppData\\LocalLow\\TesseractStudio\\TaskbarHero)"
    rows = [
        ("URL",        C.green(url)),
        ("AES",        C.yellow(aes_label)),
        ("Save file",  C.cyan(save_label)),
        ("Status",     C.green("● Ready")),
    ]
    width = max(len(k) for k, _ in rows) + 2
    border = C.dim("─" * 54)
    print(border)
    print("  " + C.bold("TBH Save Editor") + C.dim("  -  server status"))
    print(border)
    for k, v in rows:
        pad = " " * (width - len(k))
        print("  " + C.dim(k + ":") + pad + " " + v)
    print(border)
    print(C.dim("  › Tekan Ctrl+C untuk keluar"))


def main():
    httpd = Server(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d" % PORT
    save_path = default_save_path()
    print_banner()
    print_status_panel(url, save_path, es3.AES_BACKEND)
    if not os.environ.get("TBH_NO_BROWSER"):
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
        print(C.dim("  ✦ ") + C.magenta("Shutting down. Bye!"))


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
