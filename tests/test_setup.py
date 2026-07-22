import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from linxira_gaming_manager.setup import (
    GAMING_BUNDLE,
    SetupTransaction,
    apply_setup,
    discard_setup,
    plan_setup,
)


class GamingSetupTests(unittest.TestCase):
    def test_plan_requests_only_the_fixed_catalog_bundle(self):
        commands = []

        def run(command, timeout=None):
            commands.append(command)
            output = Path(command[command.index("--output-dir") + 1])
            (output / "request-plan.json").write_text(json.dumps({
                "directPackageTargets": ["gamemode", "steam"],
            }), encoding="utf-8")
            return ""

        with mock.patch("linxira_gaming_manager.setup._trusted_executable", return_value="/usr/bin/linxira-components"), \
             mock.patch("linxira_gaming_manager.setup._run", side_effect=run):
            transaction = plan_setup(Path("/catalog.json"))
        try:
            self.assertEqual(commands[0][0:2], ["/usr/bin/linxira-components", "plan"])
            self.assertEqual(commands[0][commands[0].index("--bundle") + 1], GAMING_BUNDLE)
            self.assertEqual(commands[0][commands[0].index("--accept-license") + 1], "steam")
            self.assertNotIn("--application", commands[0])
            self.assertNotIn("--profile", commands[0])
            self.assertEqual(transaction.plan["directPackageTargets"], ["gamemode", "steam"])
        finally:
            discard_setup(transaction)

    def test_apply_uses_only_fixed_confirmation_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "request-plan.json").write_text("{}", encoding="utf-8")
            transaction = SetupTransaction(root, {"directPackageTargets": ["steam"]}, "/usr/bin/linxira-components")
            commands = []

            def run(command, timeout=None):
                commands.append(command)
                if command[1] == "confirm":
                    (root / "confirmation.json").write_text("{}", encoding="utf-8")
                return "applied"

            with mock.patch("linxira_gaming_manager.setup._run", side_effect=run), \
                 mock.patch("linxira_gaming_manager.setup._trusted_executable", return_value="/usr/bin/pkexec"):
                self.assertEqual(apply_setup(transaction), "applied")

        self.assertEqual(commands[-1][0:3], [
            "/usr/bin/pkexec", "/usr/bin/linxira-components", "apply",
        ])
        self.assertEqual(commands[-1][3], "--confirmation")
        self.assertNotIn("--catalog", commands[-1])


if __name__ == "__main__":
    unittest.main()
