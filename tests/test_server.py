"""HTTP regressions use disposable synthetic saves, never the game's save path."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from core import es3
from core.es3 import SaveFile
import server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.Server(("127.0.0.1", 0), server.Handler)
        cls.worker = threading.Thread(
            target=cls.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        cls.worker.start()
        cls.addClassCleanup(cls.stop_server)

    @classmethod
    def stop_server(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.worker.join(timeout=3)
        if cls.worker.is_alive():
            raise AssertionError("Test HTTP server did not stop")

    def setUp(self):
        previous_save, previous_path = server.State.save, server.State.path
        self.addCleanup(self.restore_state, previous_save, previous_path)
        server.State.save = None
        server.State.path = None
        self.directory = tempfile.TemporaryDirectory(prefix="tbh-http-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "synthetic.es3")
        default_path = patch.object(server, "default_save_path", return_value=self.path)
        default_path.start()
        self.addCleanup(default_path.stop)
        self.account = {
            "ownerSteamId": "synthetic-test-owner",
            "version": "1.2.4",
            "settings": {"language": "en", "music": 0.75},
        }
        self.player = {
            "heroSaveDatas": [
                {"heroKey": 101, "HeroLevel": 42, "equippedItemIds": [1001]}
            ],
            "itemSaveDatas": [
                {
                    "UniqueId": 1001,
                    "ItemKey": 504111,
                    "EnchantCount": [0, 0, 0],
                    "EngravingAppliedTotalCount": 7,
                    "Durability": 83,
                }
            ],
            "currencies": {"gold": 123456, "gems": 17},
            "questProgress": [1, 3, 5],
        }
        self.fixture = SaveFile({
            "AccountSaveData": {"__type": "string", "value": json.dumps(self.account)},
            "PlayerSaveData": {"__type": "string", "value": json.dumps(self.player)},
            "SystemInfo": {"__type": "string", "value": ""},
            "UnrelatedData": {"__type": "string", "value": "preserve this"},
        })
        self.fixture.save(self.path, backup=False)
        self.edit = {
            "uniqueId": "1001", "slot": 2, "materialKey": 124003,
            "statModKey": 104001, "tier": 5, "value": 2.3,
        }

    @staticmethod
    def restore_state(save, path):
        server.State.save, server.State.path = save, path

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(*self.httpd.server_address, timeout=3)
        try:
            encoded = json.dumps(body) if body is not None else None
            connection.request(method, path, body=encoded,
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def load(self):
        status, payload = self.request("POST", "/api/load", {"path": self.path})
        self.assertEqual(status, 200, payload)
        return payload

    def test_state_and_load_report_versions(self):
        status, state = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertFalse(state["loaded"])
        self.assertEqual(state["dataVersion"], server.DATA_VERSION["gameVersion"])
        self.assertIsNone(state["saveVersion"])
        loaded = self.load()
        self.assertEqual(loaded["saveVersion"], "1.2.4")
        self.assertEqual(loaded["dataVersion"], server.DATA_VERSION["gameVersion"])
        status, state = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertTrue(state["loaded"])
        self.assertEqual(state["saveVersion"], "1.2.4")
        self.assertEqual(state["path"], self.path)

    def test_decimal_edit_save_reload_and_exact_backup(self):
        original_bytes = Path(self.path).read_bytes()
        self.load()
        status, item = self.request("POST", "/api/set_enchant", self.edit)
        self.assertEqual(status, 200, item)
        self.assertEqual(item["enchants"][2]["value"], 2.3)
        self.assertEqual(item["enchants"][2]["errors"], [])
        edited = copy.deepcopy(server.State.save.player)
        edited_item = edited["itemSaveDatas"][0]
        self.assertEqual(edited_item["EnchantData"][2]["Value"], 23)
        self.assertEqual(edited_item["EnchantCount"], [0, 1, 0])
        self.assertEqual(edited_item["EngravingAppliedTotalCount"], 8)
        status, saved = self.request("POST", "/api/save", {})
        self.assertEqual(status, 200, saved)
        self.assertTrue(saved["ok"])
        self.assertEqual(Path(saved["backup"]).read_bytes(), original_bytes)
        reloaded = SaveFile.load(self.path)
        self.assertEqual(reloaded.account, self.account)
        self.assertEqual(reloaded.player, edited)
        self.assertEqual(reloaded.player["currencies"], self.player["currencies"])
        self.assertEqual(reloaded.player["questProgress"], self.player["questProgress"])
        self.assertEqual(reloaded.player["heroSaveDatas"], self.player["heroSaveDatas"])
        self.assertEqual(reloaded.player["itemSaveDatas"][0]["Durability"], 83)
        self.assertEqual(reloaded._es3["UnrelatedData"], self.fixture._es3["UnrelatedData"])

    def test_second_save_keeps_the_original_backup(self):
        original_bytes = Path(self.path).read_bytes()
        self.load()
        self.assertEqual(self.request("POST", "/api/set_enchant", self.edit)[0], 200)
        status, first = self.request("POST", "/api/save", {})
        self.assertEqual(status, 200, first)
        first_saved_bytes = Path(self.path).read_bytes()
        status, second = self.request("POST", "/api/save", {})
        self.assertEqual(status, 200, second)
        self.assertNotEqual(first["backup"], second["backup"])
        self.assertTrue(first["backup"].endswith(".bak"))
        self.assertEqual(Path(first["backup"]).read_bytes(), original_bytes)
        self.assertEqual(Path(second["backup"]).read_bytes(), first_saved_bytes)

    def test_backups_are_capped_but_keep_the_original(self):
        original_bytes = Path(self.path).read_bytes()
        legacy = Path(self.path + ".bak")
        legacy.write_bytes(b"legacy backup")
        self.load()
        self.assertEqual(self.request("POST", "/api/set_enchant", self.edit)[0], 200)
        for _ in range(4):
            before_save = Path(self.path).read_bytes()
            status, saved = self.request("POST", "/api/save", {})
            self.assertEqual(status, 200, saved)
        backups = es3._backups(self.path)
        self.assertEqual(len(backups), es3.BACKUP_LIMIT)
        self.assertEqual(Path(backups[0]).read_bytes(), original_bytes)
        self.assertEqual(backups[-1], saved["backup"])
        self.assertEqual(Path(backups[-1]).read_bytes(), before_save)
        self.assertEqual(legacy.read_bytes(), b"legacy backup")
        self.assertEqual(self.load()["heroes"][0]["items"][0]["enchants"][2]["value"], 2.3)

    def test_rejected_values_do_not_create_or_extend_enchant_data(self):
        self.load()
        for existing_slots in (None, [server.GD.empty_enchant()]):
            item = server.State.save.player["itemSaveDatas"][0]
            if existing_slots is not None:
                item["EnchantData"] = existing_slots
            before = copy.deepcopy(server.State.save.player)
            for value in (2.31, 2):
                with self.subTest(existing_slots=existing_slots, value=value):
                    status, error = self.request("POST", "/api/set_enchant",
                                                 {**self.edit, "value": value})
                    self.assertEqual(status, 400, error)
                    self.assertIn("error", error)
                    self.assertEqual(server.State.save.player, before)

    def test_invalid_slots_are_rejected_without_mutation(self):
        self.load()
        before = copy.deepcopy(server.State.save.player)
        for slot in (-1, 6, "invalid", None):
            for clear in (False, True):
                with self.subTest(slot=slot, clear=clear):
                    status, error = self.request("POST", "/api/set_enchant",
                                                 {**self.edit, "slot": slot, "clear": clear})
                    self.assertEqual(status, 400, error)
                    self.assertEqual(server.State.save.player, before)

    def test_custom_values_bypass_range_but_still_require_integer_raw_values(self):
        self.load()
        status, item = self.request("POST", "/api/set_enchant",
                                     {**self.edit, "value": 9.9, "force": True})
        self.assertEqual(status, 200, item)
        enchant = item["enchants"][2]
        self.assertEqual(enchant["value"], 9.9)
        self.assertTrue(enchant["identityValid"])
        self.assertEqual(len(enchant["errors"]), 1)
        self.assertIn("outside range", enchant["errors"][0])
        before = copy.deepcopy(server.State.save.player)
        self.assertEqual(before["itemSaveDatas"][0]["EnchantData"][2]["Value"], 99)
        status, error = self.request("POST", "/api/set_enchant",
                                     {**self.edit, "value": 2.31, "force": True})
        self.assertEqual(status, 400, error)
        self.assertEqual(server.State.save.player, before)

    def test_custom_mode_rejects_invalid_material_stat_and_tier(self):
        self.load()
        before = copy.deepcopy(server.State.save.player)
        for invalid in ({"materialKey": 999999}, {"materialKey": 110001},
                        {"statModKey": 100101}, {"statModKey": 999999}, {"tier": 2}):
            with self.subTest(invalid=invalid):
                status, error = self.request("POST", "/api/set_enchant",
                                             {**self.edit, "force": True, **invalid})
                self.assertEqual(status, 400, error)
                self.assertIn("error", error)
                self.assertEqual(server.State.save.player, before)

    def test_custom_noop_preserves_original_material_and_applied_counter(self):
        item = self.fixture.player["itemSaveDatas"][0]
        item["EnchantData"] = [
            server.GD.empty_enchant(), server.GD.empty_enchant(),
            {"StatModKey": 101301, "Tier": 2, "Value": 16, "RecipeType": 4,
             "ModType": 0, "MaterialKey": 121002, "StatType": 13},
        ]
        item["EnchantCount"] = [0, 1, 0]
        self.fixture.save(self.path, backup=False)
        enchant = self.load()["heroes"][0]["items"][0]["enchants"][2]
        self.assertTrue(enchant["identityValid"])
        self.assertEqual(enchant["errors"], ["Value 16 is outside range [10,15]"])
        before = copy.deepcopy(server.State.save.player)
        status, item = self.request("POST", "/api/set_enchant", {
            **self.edit, "materialKey": enchant["materialKey"],
            "statModKey": enchant["statModKey"], "tier": enchant["tier"],
            "value": enchant["value"], "force": True,
        })
        self.assertEqual(status, 200, item)
        self.assertEqual(item["enchants"][2]["materialKey"], 121002)
        self.assertEqual(server.State.save.player, before)
        self.assertEqual(server.State.save.player["itemSaveDatas"][0]
                         ["EngravingAppliedTotalCount"], 7)

    def test_payload_marks_an_invalid_enchant_identity(self):
        item = self.fixture.player["itemSaveDatas"][0]
        item["EnchantData"] = [
            server.GD.empty_enchant(), server.GD.empty_enchant(),
            {"StatModKey": 104001, "Tier": 5, "Value": 23, "RecipeType": 4,
             "ModType": 0, "MaterialKey": 110001, "StatType": 40},
        ]
        item["EnchantCount"] = [0, 1, 0]
        self.fixture.save(self.path, backup=False)
        enchant = self.load()["heroes"][0]["items"][0]["enchants"][2]
        self.assertFalse(enchant["identityValid"])
        self.assertIn("material is DECORATION but slot is ENGRAVING", enchant["errors"])
        self.assertEqual(server.State.save.player, self.fixture.player)

    def test_unchanged_changed_and_cleared_enchants_preserve_extra_save_fields(self):
        item = self.fixture.player["itemSaveDatas"][0]
        item["EnchantData"] = [
            server.GD.empty_enchant(), server.GD.empty_enchant(),
            {"StatModKey": 104001, "Tier": 5, "Value": 23, "RecipeType": 4,
             "ModType": 0, "MaterialKey": 124003, "StatType": 40,
             "EnchantVersion": None, "FutureMetadata": {"revision": 2, "tags": ["retain"]}},
        ]
        item["EnchantCount"] = [0, 1, 0]
        self.fixture.save(self.path, backup=False)
        self.load()
        expected = copy.deepcopy(server.State.save.player)

        status, payload = self.request("POST", "/api/set_enchant", self.edit)
        self.assertEqual(status, 200, payload)
        self.assertEqual(server.State.save.player, expected)

        status, payload = self.request("POST", "/api/set_enchant", {**self.edit, "value": 2.4})
        self.assertEqual(status, 200, payload)
        expected_item = expected["itemSaveDatas"][0]
        expected_item["EnchantData"][2]["Value"] = 24
        expected_item["EngravingAppliedTotalCount"] = 8
        self.assertEqual(server.State.save.player, expected)

        status, payload = self.request("POST", "/api/set_enchant", {**self.edit, "clear": True})
        self.assertEqual(status, 200, payload)
        for field in ("StatModKey", "Tier", "Value", "RecipeType", "ModType", "MaterialKey", "StatType"):
            expected_item["EnchantData"][2][field] = 0
        expected_item["EnchantCount"] = [0, 0, 0]
        self.assertFalse(payload["enchants"][2]["filled"])
        self.assertEqual(server.State.save.player, expected)

    def test_edit_before_load_is_rejected(self):
        for clear in (False, True):
            with self.subTest(clear=clear):
                status, error = self.request("POST", "/api/set_enchant",
                                             {**self.edit, "clear": clear})
                self.assertEqual(status, 400, error)
                self.assertIsNone(server.State.save)
                self.assertIsNone(server.State.path)

    def test_existing_enchant_payload_preserves_stat_tier_and_decimal(self):
        item = self.fixture.player["itemSaveDatas"][0]
        item["EnchantData"] = [
            server.GD.empty_enchant(), server.GD.empty_enchant(),
            {"StatModKey": 104001, "Tier": 5, "Value": 23, "RecipeType": 4,
             "ModType": 0, "MaterialKey": 124003, "StatType": 40},
        ]
        item["EnchantCount"] = [0, 1, 0]
        self.fixture.save(self.path, backup=False)
        loaded = self.load()
        enchant = loaded["heroes"][0]["items"][0]["enchants"][2]
        self.assertEqual(enchant["statType"], "DamageAbsorption")
        self.assertEqual(enchant["modType"], "FLAT")
        self.assertEqual(enchant["statModKey"], 104001)
        self.assertEqual(enchant["materialKey"], 124003)
        self.assertEqual(enchant["tier"], 5)
        self.assertEqual(enchant["value"], 2.3)
        self.assertFalse(enchant["isPercent"])
        self.assertEqual(enchant["errors"], [])
        self.assertEqual(server.State.save.player, self.fixture.player)

    def test_missing_enchants_return_six_slots_without_mutation(self):
        loaded = self.load()
        slots = loaded["heroes"][0]["items"][0]["enchants"]
        self.assertEqual([slot["slot"] for slot in slots], list(range(6)))
        self.assertFalse(any(slot["filled"] for slot in slots))
        self.assertEqual(server.State.save.player, self.player)
        self.assertNotIn("EnchantData", server.State.save.player["itemSaveDatas"][0])


if __name__ == "__main__":
    unittest.main()
