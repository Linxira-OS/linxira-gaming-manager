from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


CATALOG_PATH = Path("/usr/share/linxira/catalog/catalog-v3.json")
COMPONENTS_CLI = Path("/usr/bin/linxira-components")
PKEXEC = Path("/usr/bin/pkexec")
GAMING_BUNDLE = "bundle-gaming-setup"


class SetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class SetupTransaction:
    directory: Path
    plan: dict[str, object]
    executable: str


def _trusted_executable(path: Path) -> str:
    if not path.is_absolute() or not path.is_file():
        raise SetupError(f"trusted executable is unavailable: {path}")
    return str(path)


def _run(command: list[str], timeout: int | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError(f"cannot run {command[0]}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise SetupError(detail)
    return (result.stdout or result.stderr).strip()


def _document(path: Path, description: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SetupError(f"invalid {description}: {exc}") from exc
    if not isinstance(value, dict):
        raise SetupError(f"invalid {description}")
    return value


def plan_setup(
    catalog_path: Path = CATALOG_PATH,
) -> SetupTransaction:
    resolved = _trusted_executable(COMPONENTS_CLI)
    directory = Path(tempfile.mkdtemp(prefix="linxira-gaming-setup-"))
    try:
        _run([
            resolved,
            "plan",
            "--catalog",
            str(catalog_path),
            "--bundle",
            GAMING_BUNDLE,
            "--accept-license",
            "steam",
            "--output-dir",
            str(directory),
        ], timeout=30)
        plan = _document(directory / "request-plan.json", "gaming setup plan")
        targets = plan.get("directPackageTargets")
        if not isinstance(targets, list) or not targets or not all(
            isinstance(item, str) and item for item in targets
        ):
            raise SetupError("gaming setup plan contains no valid package targets")
        return SetupTransaction(directory, plan, resolved)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def discard_setup(transaction: SetupTransaction) -> None:
    shutil.rmtree(transaction.directory, ignore_errors=True)


def apply_setup(transaction: SetupTransaction) -> str:
    try:
        _run([
            transaction.executable,
            "confirm",
            "--catalog",
            str(CATALOG_PATH),
            "--plan",
            str(transaction.directory / "request-plan.json"),
            "--output-dir",
            str(transaction.directory),
        ], timeout=30)
        confirmation = transaction.directory / "confirmation.json"
        _document(confirmation, "gaming setup confirmation")
        resolved_pkexec = _trusted_executable(PKEXEC)
        return _run([
            resolved_pkexec,
            transaction.executable,
            "apply",
            "--confirmation",
            str(confirmation),
        ])
    finally:
        discard_setup(transaction)
