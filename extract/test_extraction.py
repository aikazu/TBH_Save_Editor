"""Failure checks for replacing an existing generated data directory."""
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import extract_all
import extract_enums


class ExtractionFailureTests(unittest.TestCase):
    def test_missing_inputs_leave_existing_output_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "data"
            output.mkdir()
            marker = output / "names.json"
            marker.write_text('{"old": "catalog"}', encoding="utf-8")
            with self.assertRaisesRegex(FileNotFoundError, "Missing extraction input"):
                extract_all.preflight(root / "game", root / "missing.cs", output)
            self.assertEqual(marker.read_text(encoding="utf-8"), '{"old": "catalog"}')
            self.assertEqual(list(root.iterdir()), [output])

    def test_incomplete_dump_fails_with_required_enum_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            dump = Path(temporary) / "dump.cs"
            dump.write_text("// Wrong or incomplete dump\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Required enums not found.*StatType"):
                extract_enums.read_enums(dump)

    def test_extractor_failure_does_not_publish_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "data"
            output.mkdir()
            marker = output / "names.json"
            marker.write_bytes(b"old catalog")
            args = SimpleNamespace(output=output, game_dir=root / "game", dump_path=root / "dump.cs",
                                   game_version="test", steam_build="test")

            def fail_after_write(game_dir, staged):
                (staged / "partial.csv").write_bytes(b"incomplete")
                raise ValueError("simulated extraction failure")

            with patch.object(extract_all, "preflight", return_value={}):
                with patch.object(extract_all.extract_tables, "main", side_effect=fail_after_write):
                    with self.assertRaisesRegex(ValueError, "simulated extraction failure"):
                        extract_all.run(args)
            self.assertEqual(marker.read_bytes(), b"old catalog")
            self.assertEqual(list(root.iterdir()), [output])
            self.assertEqual(list(output.iterdir()), [marker])

    def check_publish_failure(self, fail_restore):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "data"
            output.mkdir()
            (output / "names.json").write_bytes(b"old catalog")
            args = SimpleNamespace(output=output, game_dir=root / "game", dump_path=root / "dump.cs",
                                   game_version="test", steam_build="test")
            rename = Path.rename

            def fail_publication(path, target):
                if path.parent.name.startswith(".tbh-extract-") and path.name == "data":
                    raise OSError("simulated publication failure")
                if fail_restore and path.name.startswith(".tbh-data-backup-"):
                    raise OSError("simulated restoration failure")
                return rename(path, target)

            with ExitStack() as patches:
                patches.enter_context(patch.object(extract_all, "preflight", return_value={}))
                patches.enter_context(patch.object(extract_all, "check_catalog", return_value={}))
                patches.enter_context(patch.object(extract_all.importlib.metadata, "version", return_value="test"))
                for module in (extract_all.extract_tables, extract_all.extract_enums,
                               extract_all.extract_localization, extract_all.extract_sprites):
                    patches.enter_context(patch.object(module, "main", return_value={}))
                patches.enter_context(patch.object(Path, "rename", fail_publication))
                error = RuntimeError if fail_restore else OSError
                message = "retained for recovery" if fail_restore else "publication failure"
                with self.assertRaisesRegex(error, message):
                    extract_all.run(args)
            if fail_restore:
                backups = list(root.glob(".tbh-data-backup-*"))
                self.assertEqual(len(backups), 1)
                self.assertEqual((backups[0] / "names.json").read_bytes(), b"old catalog")
            else:
                self.assertEqual((output / "names.json").read_bytes(), b"old catalog")
                self.assertEqual(list(root.iterdir()), [output])

    def test_publication_failure_restores_previous_data(self):
        self.check_publish_failure(fail_restore=False)

    def test_failed_restoration_retains_recovery_copy(self):
        self.check_publish_failure(fail_restore=True)


if __name__ == "__main__":
    unittest.main()
