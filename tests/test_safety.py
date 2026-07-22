from pathlib import Path
import tempfile
import unittest
from unittest import mock
import uuid

from linxira_gaming_manager.backup import backup_command
from linxira_gaming_manager.launch import launch_command, launch_spec
from linxira_gaming_manager.paths import ensure_private_directory


class SafetyTests(unittest.TestCase):
    def test_steam_launch_uses_fixed_argument_array(self):
        with mock.patch("pathlib.Path.is_file", return_value=True):
            executable, arguments = launch_command({
                "source": "steam", "external_id": "42"
            })
        self.assertEqual(Path(executable).parts[-3:], ("usr", "bin", "steam"))
        self.assertEqual(arguments, ["steam://rungameid/42"])

    def test_imported_windows_game_uses_managed_umu_prefix_and_filtered_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "game.exe"
            executable.write_bytes(b"MZ")
            runner = root / "umu-run"
            runner.write_text("runner", encoding="utf-8")
            with mock.patch.dict("os.environ", {
                "XDG_DATA_HOME": str(root / "data"),
                "HOME": str(root),
                "DISPLAY": ":0",
                "LD_PRELOAD": "/untrusted.so",
                "VK_DRIVER_FILES": "/tmp/untrusted.json",
                "LC_ATTACK": "/tmp/untrusted",
            }, clear=True), mock.patch.dict(
                "linxira_gaming_manager.launch.RUNNER_PATHS", {"umu": runner}
            ):
                game_id = str(uuid.uuid4())
                game = {
                    "id": game_id, "source": "imported", "runner": "umu",
                    "executable": str(executable),
                    "prefix_path": str(root / f"data/linxira/gaming-manager/games/{game_id}/prefix"),
                    "launch_args": '["--safe"]',
                }
                spec = launch_spec(game)
        self.assertEqual(spec.program, str(runner))
        self.assertEqual(spec.arguments, (str(executable), "--safe"))
        self.assertEqual(spec.environment["GAMEID"], "umu-default")
        self.assertEqual(spec.environment["PATH"], "/usr/bin")
        self.assertNotIn("LD_PRELOAD", spec.environment)
        self.assertNotIn("VK_DRIVER_FILES", spec.environment)
        self.assertNotIn("LC_ATTACK", spec.environment)

    def test_imported_game_rejects_non_uuid_id_and_symlinked_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "game.exe"
            executable.write_bytes(b"MZ")
            runner = root / "wine"
            runner.write_text("runner", encoding="utf-8")
            game_id = str(uuid.uuid4())
            prefix = root / f"data/linxira/gaming-manager/games/{game_id}/prefix"
            prefix.parent.mkdir(parents=True)
            try:
                prefix.symlink_to(root, target_is_directory=True)
            except OSError:
                self.skipTest("directory symlinks are unavailable")
            base = {
                "source": "imported", "runner": "wine", "executable": str(executable),
                "prefix_path": str(prefix), "launch_args": "[]",
            }
            with mock.patch.dict("os.environ", {"XDG_DATA_HOME": str(root / "data")}, clear=True), mock.patch.dict(
                "linxira_gaming_manager.launch.RUNNER_PATHS", {"wine": runner}
            ):
                with self.assertRaisesRegex(ValueError, "canonical UUID"):
                    launch_spec({**base, "id": "../escape"})
                with self.assertRaisesRegex(ValueError, "symlink"):
                    launch_spec({**base, "id": game_id})

    def test_backup_password_is_passed_by_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "prefix"
            source.mkdir()
            password = root / "password"
            password.write_text("secret", encoding="utf-8")
            with mock.patch("shutil.which", return_value="/usr/bin/restic"):
                executable, arguments, environment = backup_command(
                    root / "repository", password, source
                )
        self.assertEqual(executable, "/usr/bin/restic")
        self.assertNotIn("secret", arguments)
        self.assertEqual(environment["RESTIC_PASSWORD_FILE"], str(password))

    def test_private_directory_rejects_symlink_below_xdg_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            anchor = root / "state"
            anchor.mkdir()
            outside = root / "outside"
            outside.mkdir()
            try:
                (anchor / "linxira").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("directory symlinks are unavailable")
            boundary = anchor / "linxira/gaming-manager"
            with self.assertRaisesRegex(ValueError, "symlink"):
                ensure_private_directory(boundary / "games", boundary, anchor)

    def test_source_has_no_privileged_or_shell_transaction(self):
        source = (Path(__file__).parents[1] / "src/linxira_gaming_manager/app.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("pkexec", "sudo", "pacman", "flatpak", "shell=True"):
            self.assertNotIn(forbidden, source)

    def test_setup_backend_has_no_package_manager_or_shell(self):
        source = (Path(__file__).parents[1] / "src/linxira_gaming_manager/setup.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("sudo", "pacman", "flatpak", "shell=True"):
            self.assertNotIn(forbidden, source)
        self.assertIn('"--confirmation"', source)
