"""
Extracts English text from Unity Localization bundles -> data/.
Only the keys the app actually consumes are written (saves ~110KB of dead weight).

  - ItemTable  -> data/names.json     (ItemKey -> item/material display name)
  - StringTable-> data/strings.json   (only HeroName_<key> -> hero display name)
Chain: SharedTableData (m_Id -> m_Key) + <Table>_en (m_Id -> m_Localized).
"""
import json
import os
import re
import UnityPy

AA = (r"C:\Program Files (x86)\Steam\steamapps\common\TaskbarHero"
      r"\TaskBarHero_Data\StreamingAssets\aa\StandaloneWindows64")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

SHARED = "localization-assets-shared_assets_all.bundle"
BUNDLE = "localization-string-tables-english(unitedstates)(en-us)_assets_all.bundle"
ITEMNAME_RE = re.compile(r"^ItemName_(\d+)$")
HERONAME_RE = re.compile(r"^HeroName_(\d+)$")


def shared_id_map(collection):
    """m_Id -> m_Key of the collection (ItemTable / StringTable)."""
    env = UnityPy.load(os.path.join(AA, SHARED))
    out = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if tree.get("m_TableCollectionName") != collection:
            continue
        for e in tree.get("m_Entries", []):
            out[e["m_Id"]] = e.get("m_Key", "")
    return out


def locale_table(table_prefix, id_to_key, key_filter):
    env = UnityPy.load(os.path.join(AA, BUNDLE))
    out = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if not str(tree.get("m_Name", "")).startswith(table_prefix):
            continue
        for e in tree.get("m_TableData", []):
            key = id_to_key.get(e.get("m_Id"))
            loc = e.get("m_Localized")
            if not (key and loc):
                continue
            value = key_filter(key)
            if value is not None:
                out[value] = loc
    return out


def _to_itemkey(key):
    m = ITEMNAME_RE.match(key)
    return str(int(m.group(1))) if m else None


def _to_herokey(key):
    m = HERONAME_RE.match(key)
    return key if m else None  # keep full "HeroName_<n>" key


def main():
    os.makedirs(OUT, exist_ok=True)
    items_ids = shared_id_map("ItemTable")
    strings_ids = shared_id_map("StringTable")
    print(f"SharedTableData: ItemTable={len(items_ids)} StringTable={len(strings_ids)}")

    names = locale_table("ItemTable_", items_ids, _to_itemkey)
    with open(os.path.join(OUT, "names.json"), "w", encoding="utf-8") as fh:
        json.dump(names, fh, ensure_ascii=False, indent=2)
    print(f"  names.json: {len(names)} item names")

    hero_names = locale_table("StringTable_", strings_ids, _to_herokey)
    with open(os.path.join(OUT, "strings.json"), "w", encoding="utf-8") as fh:
        json.dump(hero_names, fh, ensure_ascii=False, indent=2)
    print(f"  strings.json: {len(hero_names)} hero names  (ex: {hero_names.get('HeroName_101')!r})")


if __name__ == "__main__":
    main()
