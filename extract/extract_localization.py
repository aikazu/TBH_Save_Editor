"""
Extracts localized text (Unity Localization):
  - ItemTable  -> data/names_<locale>.json   (numeric ItemKey -> item/material name)
  - StringTable-> data/strings_<locale>.json  (string key -> text; includes HeroName_<key>, etc.)
Chain: SharedTableData (m_Id -> m_Key) + <Table>_<locale> (m_Id -> m_Localized).
"""
import json
import os
import re
import UnityPy

AA = (r"C:\Program Files (x86)\Steam\steamapps\common\TaskbarHero"
      r"\TaskBarHero_Data\StreamingAssets\aa\StandaloneWindows64")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

SHARED = "localization-assets-shared_assets_all.bundle"
LOCALES = {
    "en": "localization-string-tables-english(unitedstates)(en-us)_assets_all.bundle",
    "pt": "localization-string-tables-portuguese(brazil)(pt-br)_assets_all.bundle",
}
ITEMNAME_RE = re.compile(r"^ItemName_(\d+)$")


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


def locale_table(bundle, table_prefix, id_to_key, key_transform):
    env = UnityPy.load(os.path.join(AA, bundle))
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
            if key and loc:
                k = key_transform(key)
                if k is not None:
                    out[k] = loc
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    items_ids = shared_id_map("ItemTable")
    strings_ids = shared_id_map("StringTable")
    print(f"SharedTableData: ItemTable={len(items_ids)} StringTable={len(strings_ids)}")
    for loc, bundle in LOCALES.items():
        names = locale_table(bundle, "ItemTable_", items_ids,
                             lambda k: (lambda m: str(int(m.group(1))) if m else None)(ITEMNAME_RE.match(k)))
        with open(os.path.join(OUT, f"names_{loc}.json"), "w", encoding="utf-8") as fh:
            json.dump(names, fh, ensure_ascii=False, indent=2)
        strings = locale_table(bundle, "StringTable_", strings_ids, lambda k: k)
        with open(os.path.join(OUT, f"strings_{loc}.json"), "w", encoding="utf-8") as fh:
            json.dump(strings, fh, ensure_ascii=False, indent=2)
        print(f"  {loc}: {len(names)} names, {len(strings)} strings  (ex hero: {strings.get('HeroName_101')!r})")


if __name__ == "__main__":
    main()
