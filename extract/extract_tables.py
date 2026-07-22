"""
Extracts the data tables (CSV TextAssets) from sharedassets0.assets into data/tables/.
Runs once on a machine with the game installed + UnityPy (pip install UnityPy).
The result (data/tables/*.csv) is portable and ships with the app.
"""
import os
import UnityPy

GAME_DATA = r"C:\Program Files (x86)\Steam\steamapps\common\TaskbarHero\TaskBarHero_Data"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tables")

# Tables required for items + enchantments (plus a few useful extras).
WANTED = {
    "GearInfoData", "GearTypeInfoData", "GearTypeScaleInfoData", "ItemTypeScaleInfoData",
    "MaterialInfoData", "StatModInfoData", "StatModGroupInfoData", "GradeInfoData",
    "AttributeGroupInfoData", "InventoryInfoData", "SynthesisRecipeInfoData",
    "RuneInfoData", "RuneLevelInfoData", "CurrencyInfoData", "HeroInfoData",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    env = UnityPy.load(os.path.join(GAME_DATA, "sharedassets0.assets"))
    found = 0
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        d = obj.read()
        name = d.m_Name
        if name not in WANTED:
            continue
        raw = d.m_Script
        if isinstance(raw, str):
            raw = raw.encode("utf-8", "surrogateescape")
        path = os.path.join(OUT, name + ".csv")
        with open(path, "wb") as fh:
            fh.write(bytes(raw))
        print(f"  {name}.csv  ({len(raw)} bytes)")
        found += 1
    print(f"\nExtracted {found}/{len(WANTED)} tables into {OUT}")


if __name__ == "__main__":
    main()
