"""Regression coverage for save-value precision and table-backed enchant metadata."""
import json
from pathlib import Path
import unittest

from core.gamedata import GameData, SLOT_MATERIAL_TYPE


DATA = Path(__file__).resolve().parents[1] / "data"
GEAR_KEYS = {"WEAPON": 304111, "ARMOR": 504111, "ACCESSORY": 604111}


class GameDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gd = GameData(DATA)

    def option(self, slot, group, stat, tier):
        option = next(o for o in self.gd.stat_first_options(slot, group)
                      if o["statType"] == stat)
        return option, next(t for t in option["tiers"] if t["tier"] == tier)

    def enchant(self, slot, option, tier, value):
        raw = self.gd.to_raw(value, option["statType"], option["modType"])
        return self.gd.build_enchant(slot, tier["materialKey"], tier["statModKey"],
                                     tier["tier"], raw)

    def test_every_legal_table_value_roundtrips(self):
        self.assertTrue(self.gd.statmod)
        for key, row in self.gd.statmod.items():
            stat, mod = row["STATTYPE"], row["MODTYPE"]
            minimum, maximum = int(row["MinValue"]), int(row["MaxValue"])
            step = int(row["Interval"]) or 1
            with self.subTest(stat_mod=key):
                for raw in range(minimum, maximum + 1, step):
                    display = self.gd.to_display(raw, stat, mod)
                    self.assertIsInstance(display, (int, float))
                    wire_value = json.loads(json.dumps(display, allow_nan=False))
                    self.assertEqual(self.gd.to_raw(wire_value, stat, mod), raw)

    def test_all_option_bounds_validate_and_steps_keep_precision(self):
        for slot in range(len(SLOT_MATERIAL_TYPE)):
            for group, item_key in GEAR_KEYS.items():
                for option in self.gd.stat_first_options(slot, group):
                    for tier in option["tiers"]:
                        with self.subTest(slot=slot, group=group, tier=tier):
                            row = self.gd.statmod[(str(tier["statModKey"]), str(tier["tier"]))]
                            for field, column in (("min", "MinValue"), ("max", "MaxValue"),
                                                  ("interval", "Interval")):
                                raw = self.gd.to_raw(tier[field], option["statType"], option["modType"])
                                self.assertEqual(raw, int(row[column]))
                            for endpoint in ("min", "max"):
                                enchant = self.enchant(slot, option, tier, tier[endpoint])
                                self.assertEqual(self.gd.validate_enchant(slot, item_key, enchant), [])

    def test_damage_absorption_fractional_range(self):
        option, tier = self.option(2, "ARMOR", "DamageAbsorption", 5)
        self.assertEqual((tier["min"], tier["max"], tier["interval"]), (2.2, 2.6, 0.1))
        for value, raw in ((2.2, 22), (2.3, 23), (2.6, 26)):
            with self.subTest(value=value):
                enchant = self.enchant(2, option, tier, value)
                self.assertEqual(enchant["Value"], raw)
                self.assertEqual(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], enchant), [])

    def test_hp_regen_and_cooldown_fractional_values(self):
        for stat, raw, display in (("HpRegenPerSec", 150, 1.5),
                                   ("CooldownReduction", 115, 11.5)):
            with self.subTest(stat=stat):
                self.assertEqual(self.gd.to_display(raw, stat, "FLAT"), display)
                self.assertEqual(self.gd.to_raw(display, stat, "FLAT"), raw)

    def test_variant_stats_preserve_modtype_scaling(self):
        self.assertEqual(self.gd.to_display(15, "AttackDamage", "FLAT"), 15)
        self.assertEqual(self.gd.to_display(15, "AttackDamage", "ADDITIVE"), 1.5)
        self.assertEqual(self.gd.to_raw(1.5, "AttackDamage", "ADDITIVE"), 15)
        self.assertIsInstance(self.gd.to_display(20, "AttackDamage", "ADDITIVE"), int)

    def test_nonfinite_and_nonnumeric_values_are_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"),
                      "NaN", "sNaN", "Infinity", "-Infinity", "", "abc", None, True):
            for convert in (self.gd.to_raw, self.gd.to_display):
                with self.subTest(value=value, convert=convert.__name__):
                    with self.assertRaises(ValueError):
                        convert(value, "DamageAbsorption", "FLAT")

    def test_fractional_raw_values_are_rejected_without_rounding(self):
        cases = (("DamageAbsorption", "2.25"), ("HpRegenPerSec", "1.501"),
                 ("AttackDamage", "0.5"),
                 ("DamageAbsorption", "2.200000000000000000000000000001"))
        for stat, value in cases:
            with self.subTest(stat=stat, value=value):
                with self.assertRaises(ValueError):
                    self.gd.to_raw(value, stat, "FLAT")
        with self.assertRaises(ValueError):
            self.gd.to_display(22.5, "DamageAbsorption", "FLAT")
        self.assertEqual(self.gd.to_raw("2.2000", "DamageAbsorption", "FLAT"), 22)
        self.assertEqual(self.gd.to_raw("-2.2", "DamageAbsorption", "FLAT"), -22)
        self.assertEqual(self.gd.to_display(-22, "DamageAbsorption", "FLAT"), -2.2)

    def test_exact_decimal_input_does_not_depend_on_context_precision(self):
        display = "123456789012345678901234567890.1"
        self.assertEqual(self.gd.to_raw(display, "DamageAbsorption", "FLAT"),
                         1234567890123456789012345678901)
        with self.assertRaises(ValueError):
            self.gd.to_display(1234567890123456789012345678901, "DamageAbsorption", "FLAT")

    def test_representable_but_off_interval_value_is_rejected(self):
        option, tier = self.option(0, "ARMOR", "HpRegenPerSec", 2)
        enchant = self.enchant(0, option, tier, 1.55)
        self.assertEqual(enchant["Value"], 155)
        errors = self.gd.validate_enchant(0, GEAR_KEYS["ARMOR"], enchant)
        self.assertTrue(any("step 10" in error for error in errors), errors)

    def test_build_rejects_fractional_raw_value(self):
        option, tier = self.option(2, "ARMOR", "DamageAbsorption", 5)
        with self.assertRaises(ValueError):
            self.gd.build_enchant(2, tier["materialKey"], tier["statModKey"], tier["tier"], 22.5)

    def test_validate_checks_enum_metadata(self):
        option, tier = self.option(2, "ARMOR", "DamageAbsorption", 5)
        enchant = self.enchant(2, option, tier, tier["max"])
        self.assertEqual(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], enchant), [])
        for field in ("RecipeType", "StatType", "ModType"):
            with self.subTest(field=field):
                invalid = dict(enchant, **{field: 999})
                errors = self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], invalid)
                self.assertTrue(any(error.startswith(field + " ") for error in errors), errors)
                invalid.pop(field)
                errors = self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], invalid)
                self.assertTrue(any(error.startswith(field + " ") for error in errors), errors)
        self.assertEqual(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], self.gd.empty_enchant()), [])

    def test_validate_rejects_invalid_raw_value(self):
        option, tier = self.option(2, "ARMOR", "DamageAbsorption", 5)
        enchant = self.enchant(2, option, tier, tier["max"])
        for value in (22.5, float("nan"), float("inf"), "bad"):
            with self.subTest(value=value):
                invalid = dict(enchant, Value=value)
                self.assertTrue(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], invalid))

    def test_custom_value_keeps_its_valid_material_identity(self):
        enchant = self.gd.build_enchant(2, 121002, 101301, 2, 16)
        self.assertTrue(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], enchant))
        self.assertEqual(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], enchant,
                                                check_value=False), [])
        option, tier = self.option(0, "ARMOR", "HpRegenPerSec", 2)
        off_step = self.enchant(0, option, tier, 1.55)
        self.assertTrue(self.gd.validate_enchant(0, GEAR_KEYS["ARMOR"], off_step))
        self.assertEqual(self.gd.validate_enchant(0, GEAR_KEYS["ARMOR"], off_step,
                                                check_value=False), [])

    def test_custom_values_still_require_valid_identity(self):
        enchant = self.gd.build_enchant(2, 121002, 101301, 2, 16)
        for field, value in (("MaterialKey", 999999), ("MaterialKey", 0),
                             ("MaterialKey", 110001), ("StatModKey", 999999),
                             ("Tier", 999), ("RecipeType", 999),
                             ("StatType", 999), ("ModType", 999)):
            with self.subTest(field=field, value=value):
                invalid = dict(enchant, **{field: value})
                self.assertTrue(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], invalid,
                                                       check_value=False))
        self.assertTrue(self.gd.validate_enchant(0, GEAR_KEYS["ARMOR"], enchant,
                                               check_value=False))
        self.assertEqual(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"], self.gd.empty_enchant(),
                                                check_value=False), [])

    def test_custom_values_still_require_finite_integer_raw(self):
        enchant = self.gd.build_enchant(2, 121002, 101301, 2, 16)
        for value in (16.5, float("nan"), float("inf"), "bad"):
            with self.subTest(value=value):
                self.assertTrue(self.gd.validate_enchant(2, GEAR_KEYS["ARMOR"],
                                                       dict(enchant, Value=value), check_value=False))


if __name__ == "__main__":
    unittest.main()
