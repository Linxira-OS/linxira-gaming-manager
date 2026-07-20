from pathlib import Path
import tempfile
import unittest

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
