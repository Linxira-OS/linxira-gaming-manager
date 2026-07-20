from pathlib import Path
import tempfile
import unittest
from unittest import mock

from linxira_gaming_manager.discovery import discover_steam


class DiscoveryTests(unittest.TestCase):
    def test_discovers_manifest_from_primary_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            steamapps = root / "steamapps"
            steamapps.mkdir()
            (steamapps / "appmanifest_42.acf").write_text("fixture", encoding="utf-8")
            with mock.patch("linxira_gaming_manager.discovery._load_vdf") as load:
                load.side_effect = [
                    {"AppState": {"appid": "42", "name": "Test Game", "installdir": "Test"}}
                ]
                games = discover_steam([root])
        self.assertEqual(games[0]["external_id"], "42")
        self.assertEqual(games[0]["source"], "steam")

    def test_malformed_manifest_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            steamapps = root / "steamapps"
            steamapps.mkdir()
            (steamapps / "appmanifest_bad.acf").write_text("fixture", encoding="utf-8")
            with mock.patch("linxira_gaming_manager.discovery._load_vdf", return_value={}):
                self.assertEqual(discover_steam([root]), [])
