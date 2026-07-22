from pathlib import Path
import tempfile
import unittest
from unittest import mock

from linxira_gaming_manager.store import Store


class StoreTests(unittest.TestCase):
    def test_discovery_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "state.db")
            game = {
                "source": "steam",
                "external_id": "42",
                "name": "Test Game",
                "install_path": "/games/test",
            }
            first = store.upsert_discovered(game)
            second = store.upsert_discovered(game)
            self.assertEqual(first, second)
            self.assertEqual(len(store.games()), 1)
            store.close()

    def test_activity_is_newest_first(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "state.db")
            store.record("scan", "Steam", "succeeded")
            store.record("backup", "Prefix", "failed")
            self.assertEqual(store.activity()[0]["kind"], "backup")
            store.close()

    def test_imported_game_keeps_stable_id_runner_and_managed_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "game.exe"
            executable.write_bytes(b"MZ")
            with mock.patch.dict("os.environ", {"XDG_DATA_HOME": str(root / "data")}, clear=True):
                store = Store(root / "state.db")
                try:
                    first = store.add_imported("Game", executable, "umu")
                    second = store.add_imported("Game", executable, "wine")
                    game = store.games()[0]
                finally:
                    store.close()
        self.assertEqual(first, second)
        self.assertEqual(game["runner"], "wine")
        self.assertEqual(
            game["prefix_path"],
            str(root / f"data/linxira/gaming-manager/games/{first}/prefix"),
        )
