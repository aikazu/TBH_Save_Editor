"""
Game knowledge base (CSV tables + names + enums + icons) and the enchantment
validation logic.

EnchantData resolution chain:
  slot (index 0..5) -> type: DECORATION(0,1) / ENGRAVING(2,3) / INSCRIPTION(4,5)
  material (MaterialKey) -> MaterialInfoData -> MATERIALTYPE (must match the slot) + StatModGroupKey
  StatModGroupKey + item GearGroup (WEAPON/ARMOR/ACCESSORY, +COMMON) -> StatModGroupInfoData
      -> options (StatModKey, MinTier..MaxTier)
  StatModKey + Tier -> StatModInfoData -> STATTYPE, MODTYPE, MinValue, MaxValue, Interval
  Value chosen in [MinValue, MaxValue] with Interval step.
"""
import csv
import json
import os
import re

# slot index -> required material type
SLOT_MATERIAL_TYPE = ["DECORATION", "DECORATION", "ENGRAVING", "ENGRAVING", "INSCRIPTION", "INSCRIPTION"]
# material type -> RecipeType (ERecipeType)
RECIPE_TYPE = {"DECORATION": 3, "ENGRAVING": 4, "INSCRIPTION": 5}


def _read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# material type -> accumulated counter field in itemSaveData
COUNT_FIELD = {
    "DECORATION": "DecorationAppliedTotalCount",
    "ENGRAVING": "EngravingAppliedTotalCount",
    "INSCRIPTION": "InscriptionAppliedTotalCount",
}
# material type -> index in EnchantCount[3]
COUNT_INDEX = {"DECORATION": 0, "ENGRAVING": 1, "INSCRIPTION": 2}


class GameData:
    def __init__(self, data_dir):
        self.dir = data_dir
        t = os.path.join(data_dir, "tables")
        self.materials = {r["ItemKey"]: r for r in _read_csv(os.path.join(t, "MaterialInfoData.csv"))}
        self.gear = {r["GearKey"]: r for r in _read_csv(os.path.join(t, "GearInfoData.csv"))}
        # group -> rows
        self.groups = {}
        for r in _read_csv(os.path.join(t, "StatModGroupInfoData.csv")):
            self.groups.setdefault(r["StatModGroupKey"], []).append(r)
        # (StatModKey, Tier) -> row
        self.statmod = {}
        for r in _read_csv(os.path.join(t, "StatModInfoData.csv")):
            self.statmod[(r["StatModKey"], r["Tier"])] = r
        # materials grouped by type
        self.materials_by_type = {"DECORATION": [], "ENGRAVING": [], "INSCRIPTION": []}
        for k, r in self.materials.items():
            mt = r["MATERIALTYPE"]
            if mt in self.materials_by_type:
                self.materials_by_type[mt].append(k)
        # names and icons
        self.names = json.load(open(os.path.join(data_dir, "names.json"), encoding="utf-8"))
        self.icon_map = json.load(open(os.path.join(data_dir, "icon_map.json"), encoding="utf-8"))
        self._named = set(self.names)  # keys with their own name/icon (base models)
        # hero display names (trimmed: HeroName_<key> only)
        self.hero_names = json.load(open(os.path.join(data_dir, "strings.json"), encoding="utf-8"))
        enums = json.load(open(os.path.join(data_dir, "enums.json"), encoding="utf-8"))
        self.stat_name_to_id = {v: int(k) for k, v in enums["StatType"].items()}
        self.modtype_name_to_id = {v: int(k) for k, v in enums["MODTYPE"].items()}
        self.egrade = enums["EGradeType"]  # id(str) -> name
        self.grades_by_name = {r["GRADE"]: r for r in _read_csv(os.path.join(t, "GradeInfoData.csv"))}
        self.hero_info = {r["HeroKey"]: r for r in _read_csv(os.path.join(t, "HeroInfoData.csv"))}

    # ---- heroes ----
    def hero_name(self, herokey):
        return (self.hero_names.get("HeroName_%s" % herokey)
                or self.hero_info.get(str(herokey), {}).get("ClassType")
                or ("Hero %s" % herokey))

    def hero_class(self, herokey):
        return self.hero_info.get(str(herokey), {}).get("ClassType", "")

    # ---- grade and slots ----
    def grade_id(self, itemkey):
        s = str(itemkey)
        return int(s[2]) if len(s) == 6 and s.isdigit() and int(s) >= 300000 else None

    def grade_name(self, itemkey):
        g = self.grade_id(itemkey)
        return self.egrade.get(str(g)) if g is not None else None

    def max_slots(self, itemkey):
        """How many slots of each type the item's grade allows."""
        r = self.grades_by_name.get(self.grade_name(itemkey))
        if not r:
            return {"DECORATION": 2, "ENGRAVING": 2, "INSCRIPTION": 2}  # permissive fallback
        return {"DECORATION": int(r["ExtraSlotAmount_Decoration"]),
                "ENGRAVING": int(r["ExtraSlotAmount_Engraving"]),
                "INSCRIPTION": int(r["ExtraSlotAmount_Inscription"])}

    def slot_allowed(self, itemkey, slot_index):
        mt = SLOT_MATERIAL_TYPE[slot_index]
        return (slot_index % 2) < self.max_slots(itemkey)[mt]

    # ---- counters (fixes the bug: the game uses EnchantCount to ACTIVATE the effect) ----
    def recount_enchants(self, item):
        """Recomputes EnchantCount[3] = number of filled slots [deco, eng, insc]."""
        ed = item.get("EnchantData", [])
        f = lambda i: 1 if i < len(ed) and ed[i].get("MaterialKey", 0) != 0 else 0
        item["EnchantCount"] = [f(0) + f(1), f(2) + f(3), f(4) + f(5)]

    def bump_applied(self, item, slot_index):
        """Increments the accumulated counter (AppliedTotalCount) of the slot's type."""
        fld = COUNT_FIELD[SLOT_MATERIAL_TYPE[slot_index]]
        item[fld] = int(item.get(fld, 0)) + 1

    # ---- item-instance -> base model resolution (the one with name/icon) ----
    def base_key(self, itemkey):
        """Items in the save are instances (with grade); name/icon live on the 'base model'.
        Ex: 604111 (amulet grade 4, model 11) -> 600011. Materials with suffix 900 -> base."""
        s = str(itemkey)
        if s in self._named:
            return s
        if len(s) == 9 and s.endswith("900") and s[:6] in self._named:  # stacked material
            return s[:6]
        k = int(itemkey)
        modelo = (k % 10000 // 10) % 100
        b = str((k // 10000) * 10000 + modelo)
        return b if b in self._named else s

    # ---- basic lookups ----
    def name(self, itemkey):
        bk = self.base_key(itemkey)
        return self.names.get(bk) or f"#{itemkey}"

    def icon_file(self, itemkey):
        return self.icon_map.get(self.base_key(itemkey))

    def has_icon(self, itemkey):
        return self.base_key(itemkey) in self.icon_map

    def gear_group(self, itemkey):
        d = int(itemkey) // 100000
        return {3: "WEAPON", 4: "WEAPON", 5: "ARMOR", 6: "ACCESSORY"}.get(d)

    def slot_material_type(self, slot_index):
        return SLOT_MATERIAL_TYPE[slot_index]

    # human-readable name for a StatType (ex PhysicalDamagePercent -> "Physical Damage %")
    @staticmethod
    def pretty_stat(stattype_name):
        words = re.findall(r"[A-Z][a-z0-9]*", stattype_name or "")
        s = " ".join(words) if words else (stattype_name or "")
        return s.replace(" Percent", " %")

    # ---- stat options for a material on an item ----
    def stat_options(self, material_key, gear_group):
        """Returns the stat options a material can grant on an item of the given gear_group.
        Each option: {statModKey, statType, statTypeId, statName, modType, modTypeId, tiers:[...]}."""
        mat = self.materials.get(str(material_key))
        if not mat:
            return []
        rows = self.groups.get(mat["StatModGroupKey"], [])
        allowed = {gear_group, "COMMON"}
        opts = []
        for row in rows:
            if row["GearGroup"] not in allowed:
                continue
            tiers = []
            for tier in range(int(row["MinTier"]), int(row["MaxTier"]) + 1):
                si = self.statmod.get((row["StatModKey"], str(tier)))
                if si:
                    tiers.append({
                        "tier": tier,
                        "min": int(si["MinValue"]),
                        "max": int(si["MaxValue"]),
                        "interval": int(si["Interval"]),
                        "statType": si["STATTYPE"],
                        "modType": si["MODTYPE"],
                    })
            if not tiers:
                continue
            st = tiers[0]["statType"]
            mtp = tiers[0]["modType"]
            opts.append({
                "statModKey": int(row["StatModKey"]),
                "gearGroup": row["GearGroup"],
                "statType": st,
                "statTypeId": self.stat_name_to_id.get(st, 0),
                "statName": self.pretty_stat(st),
                "modType": mtp,
                "modTypeId": self.modtype_name_to_id.get(mtp, 0),
                "tiers": tiers,
            })
        return opts

    def stat_range(self, statmodkey, tier):
        si = self.statmod.get((str(statmodkey), str(tier)))
        if not si:
            return None
        return {"min": int(si["MinValue"]), "max": int(si["MaxValue"]), "interval": int(si["Interval"]),
                "statType": si["STATTYPE"], "modType": si["MODTYPE"]}

    # Display rules per STATTYPE, derived by cross-referencing the raw save
    # ranges against taskbarhero.wiki/effects. The scaling is intrinsic to each
    # stat (not to MODTYPE): e.g. DamageReduction is FLAT in the save but still
    # renders as /10 percent; FireResistance renders at /1 percent. Each entry is
    # (divisor, is_percent). Stats absent here default to (1, False).
    STAT_DISPLAY = {
        # /10 percent (raw value*10, display as %)
        "AreaOfEffect": (10, True), "AttackSpeed": (10, True), "BlockChance": (10, True),
        "CastSpeed": (10, True), "CooldownReduction": (10, True), "CriticalDamage": (10, True),
        "DamageReduction": (10, True), "DodgeChance": (10, True), "HpLeech": (10, True),
        "ColdDamagePercent": (10, True), "FireDamagePercent": (10, True),
        "LightningDamagePercent": (10, True), "PhysicalDamagePercent": (10, True),
        "ChaosDamagePercent": (10, True),
        "IncreaseAreaOfEffectDamage": (10, True), "IncreaseMeleeDamage": (10, True),
        "IncreaseProjectileDamage": (10, True), "IncreaseSummonDamage": (10, True),
        "SkillDurationIncrease": (10, True), "SkillHealIncrease": (10, True),
        "SkillRangeExpansion": (10, True),
        # /1 percent (raw already in percent units)
        "AllElementalResistance": (1, True), "ChaosResistance": (1, True),
        "ColdResistance": (1, True), "FireResistance": (1, True),
        "LightningResistance": (1, True), "PhysicalDamageReduction": (1, True),
        "FireDamageReduction": (1, True), "ColdDamageReduction": (1, True),
        "LightningDamageReduction": (1, True), "ChaosDamageReduction": (1, True),
        "MaxBlockChance": (1, True), "MaxDodgeChance": (1, True),
        "MaxFireResistance": (1, True), "MaxColdResistance": (1, True),
        "MaxLightningResistance": (1, True), "MaxChaosResistance": (1, True),
        # /1 percent, damage-addition family (raw 100-150 -> ~10-15%)
        "DamageAddition": (10, True), "FireDamageAddition": (10, True),
        "ColdDamageAddition": (10, True), "LightningDamageAddition": (10, True),
        "ChaosDamageAddition": (10, True), "PhysicalDamageAddition": (10, True),
        # /10 flat: stored as raw*10 but rendered as a plain integer (no %).
        # E.g. DamageAbsorption T8 raw 40-50 -> display 4-5.
        "DamageAbsorption": (10, False),
        # flat (raw as-is, no unit): AddHpPerHit, AddHpPerKill,
        # HpRegenPerSec, BaseAttackCountReduction, Multistrike, ProjectileCount,
        # AdditionalExp, IncreaseExpAmount -> default (1, False) below.
        # AttackDamage/Armor/MaxHp/MovementSpeed/CriticalChance have FLAT and
        # ADDITIVE variants -> resolved per-MODTYPE via VARIANT_STATS.
    }

    # Variant stats: the ADDITIVE (percent) variant of these is /10 percent; the
    # FLAT variant is a plain integer. Keyed by STATTYPE.
    VARIANT_STATS = {"AttackDamage", "Armor", "MaxHp", "MovementSpeed", "CriticalChance"}

    @classmethod
    def _display_rule(cls, stattype_name, modtype):
        """Returns (divisor, is_percent) for a stat. Variant stats depend on
        MODTYPE; everything else is intrinsic to the STATTYPE."""
        if stattype_name in cls.VARIANT_STATS:
            return (10, True) if modtype == "ADDITIVE" else (1, False)
        return cls.STAT_DISPLAY.get(stattype_name, (1, False))

    @classmethod
    def is_percent(cls, stattype_name, modtype):
        return cls._display_rule(stattype_name, modtype)[1]

    @classmethod
    def to_display(cls, value, stattype_name, modtype):
        """Raw save value -> human-readable scale."""
        div = cls._display_rule(stattype_name, modtype)[0]
        return int(value) // div

    @classmethod
    def to_raw(cls, value, stattype_name, modtype):
        """Human-readable value -> raw save value."""
        div = cls._display_rule(stattype_name, modtype)[0]
        return int(value) * div

    def stat_first_options(self, slot_index, gear_group):
        """Stat-first view: for a slot's material type, merges every material's
        stat options into one list keyed by (STATTYPE, MODTYPE), unioning tiers
        across ALL materials. Each tier carries the StatModKey + MaterialKey that
        provide it (needed to build the EnchantData later).

        Keying by MODTYPE in addition to STATTYPE keeps variants apart: e.g.
        AttackDamage FLAT (+1~300) vs AttackDamage ADDITIVE (+5~150%) are two
        separate options instead of one muddled entry. min/max/interval are given
        in *display* scale (ADDITIVE /10), so the UI never shows raw 1500.

        When several materials grant the same (StatModKey, tier), the one with
        the smallest ItemKey wins (deterministic; all are game-legit).

        Returns: [{statType, statName, statTypeId, modType, modTypeId, isPercent,
                   tiers: [{tier, statModKey, materialKey, min, max, interval}]}]."""
        mtype = SLOT_MATERIAL_TYPE[slot_index]
        allowed = {gear_group, "COMMON"}
        # (STATTYPE, MODTYPE) -> {meta + {tier -> {statModKey, materialKey, range}}}
        merged = {}
        for mk in sorted(self.materials_by_type.get(mtype, []), key=int):
            mat = self.materials[mk]
            for row in self.groups.get(mat["StatModGroupKey"], []):
                if row["GearGroup"] not in allowed:
                    continue
                smk = row["StatModKey"]
                for tier in range(int(row["MinTier"]), int(row["MaxTier"]) + 1):
                    si = self.statmod.get((smk, str(tier)))
                    if not si:
                        continue
                    st = si["STATTYPE"]
                    mtp = si["MODTYPE"]
                    slot = merged.setdefault((st, mtp), {
                        "statType": st,
                        "statName": self._labeled_stat(st, mtp),
                        "statTypeId": self.stat_name_to_id.get(st, 0),
                        "modType": mtp,
                        "modTypeId": self.modtype_name_to_id.get(mtp, 0),
                        "isPercent": self.is_percent(st, mtp),
                        "_tiers": {},
                    })
                    # smallest-material-wins for a given (StatModKey, tier)
                    prev = slot["_tiers"].get(tier)
                    if prev is None or int(mk) < int(prev["materialKey"]):
                        slot["_tiers"][tier] = {
                            "tier": tier,
                            "statModKey": int(smk),
                            "materialKey": int(mk),
                            "min": self.to_display(si["MinValue"], st, mtp),
                            "max": self.to_display(si["MaxValue"], st, mtp),
                            "interval": self.to_display(si["Interval"], st, mtp) or 1,
                        }
        # flatten to sorted lists
        out = []
        for (st, mtp), slot in merged.items():
            tiers = [slot["_tiers"][t] for t in sorted(slot["_tiers"])]
            out.append({
                "statType": slot["statType"],
                "statName": slot["statName"],
                "statTypeId": slot["statTypeId"],
                "modType": slot["modType"],
                "modTypeId": slot["modTypeId"],
                "isPercent": slot["isPercent"],
                "tiers": tiers,
            })
        # stable order by stat name for a predictable dropdown
        out.sort(key=lambda o: o["statName"])
        return out

    def _labeled_stat(self, stattype_name, modtype):
        """Human-readable stat name with a variant suffix so FLAT and ADDITIVE
        (percent) versions of the same stat are visually distinct in a dropdown.
        Only the 5 variant stats (which have two MODTYPEs with different units)
        get a suffix; single-unit stats show their unit via the value instead."""
        if stattype_name in self.VARIANT_STATS:
            base = self.pretty_stat(stattype_name)
            return base + " (%)" if self.is_percent(stattype_name, modtype) else base
        return self.pretty_stat(stattype_name)

    # ---- build / validate an EnchantData ----
    def build_enchant(self, slot_index, material_key, statmodkey, tier, value):
        si = self.statmod.get((str(statmodkey), str(tier)))
        if not si:
            raise ValueError("StatModKey/Tier does not exist")
        mtype = SLOT_MATERIAL_TYPE[slot_index]
        return {
            "StatModKey": int(statmodkey),
            "Tier": int(tier),
            "Value": int(value),
            "RecipeType": RECIPE_TYPE[mtype],
            "ModType": self.modtype_name_to_id.get(si["MODTYPE"], 0),
            "MaterialKey": int(material_key),
            "StatType": self.stat_name_to_id.get(si["STATTYPE"], 0),
        }

    def empty_enchant(self):
        return {"StatModKey": 0, "Tier": 0, "Value": 0, "RecipeType": 0,
                "ModType": 0, "MaterialKey": 0, "StatType": 0}

    def validate_enchant(self, slot_index, item_key, ed):
        """Validates consistency of a (non-empty) EnchantData. Returns list of errors (empty = ok)."""
        errs = []
        if not ed or ed.get("MaterialKey", 0) == 0:
            return errs  # empty slot is valid
        mk = str(ed["MaterialKey"])
        mat = self.materials.get(mk)
        if not mat:
            return [f"Unknown MaterialKey {mk}"]
        want = SLOT_MATERIAL_TYPE[slot_index]
        if mat["MATERIALTYPE"] != want:
            errs.append(f"material is {mat['MATERIALTYPE']} but slot is {want}")
        gg = self.gear_group(item_key)
        opt = next((o for o in self.stat_options(mk, gg) if o["statModKey"] == ed.get("StatModKey")), None)
        if not opt:
            errs.append("StatModKey does not belong to this material/item group")
            return errs
        tier = next((t for t in opt["tiers"] if t["tier"] == ed.get("Tier")), None)
        if not tier:
            errs.append(f"Tier {ed.get('Tier')} is invalid for this stat")
            return errs
        v = ed.get("Value", 0)
        if not (tier["min"] <= v <= tier["max"]):
            errs.append(f"Value {v} is outside range [{tier['min']},{tier['max']}]")
        elif tier["interval"] and (v - tier["min"]) % tier["interval"] != 0:
            errs.append(f"Value {v} does not respect step {tier['interval']}")
        return errs
