import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class MetadataTests(unittest.TestCase):
    def test_version_is_consistent(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        module = ast.parse(
            (ROOT / "src/linxira_gaming_manager/__init__.py").read_text(encoding="utf-8")
        )
        assignment = module.body[0]
        self.assertEqual(ast.literal_eval(assignment.value), version)
        self.assertIn(f'version = "{version}"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_desktop_uses_the_fixed_command(self):
        desktop = (ROOT / "data/org.linxira.GamingManager.desktop").read_text(encoding="utf-8")
        self.assertIn("Exec=linxira-gaming-manager", desktop)
        self.assertNotIn("Terminal=true", desktop)
