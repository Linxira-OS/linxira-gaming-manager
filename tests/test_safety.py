from pathlib import Path
import tempfile
import unittest
from unittest import mock

from linxira_gaming_manager.backup import backup_command
from linxira_gaming_manager.launch import launch_command


class SafetyTests(unittest.TestCase):
    def test_steam_launch_uses_fixed_argument_array(self):
        with mock.patch("shutil.which", return_value="/usr/bin/steam"):
            executable, arguments = launch_command({
                "source": "steam", "external_id": "42"
            })
        self.assertEqual(executable, "/usr/bin/steam")
        self.assertEqual(arguments, ["steam://rungameid/42"])

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
