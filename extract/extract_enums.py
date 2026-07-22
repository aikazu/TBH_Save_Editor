"""
Parses the relevant enums from dump.cs (Il2CppDumper) -> data/enums.json.
Needed to translate the numeric codes in the save (StatType:24, ModType:0, RecipeType:3...)
into names, and to cross-reference with the CSV tables (which use the names).
"""
import json
import os
import re

DUMP = r"C:\Users\gmarques\Downloads\TBH_dump_1.00.17\output\dump.cs"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "enums.json")

WANTED = ["StatType", "MODTYPE", "ERecipeType", "EMaterialType", "EGradeType", "GearGroup", "GEARGROUP"]


def parse_enum(text, name):
    # find "public enum <name> ... {" and read the members up to the closing '}'
    m = re.search(r"public enum %s\b[^\n]*\n\{" % re.escape(name), text)
    if not m:
        return None
    start = m.end()
    end = text.find("}", start)
    body = text[start:end]
    members = {}
    for mm in re.finditer(r"public const %s (\w+) = (-?\d+);" % re.escape(name), body):
        member, val = mm.group(1), int(mm.group(2))
        if member == "value__":
            continue
        members[str(val)] = member
    return members


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    text = open(DUMP, encoding="utf-8", errors="ignore").read()
    out = {}
    for name in WANTED:
        e = parse_enum(text, name)
        if e:
            out[name] = e
            print(f"  {name}: {len(e)} members  (ex: {list(e.items())[:4]})")
        else:
            print(f"  {name}: NOT found")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
