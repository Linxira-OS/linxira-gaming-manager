from pathlib import Path
import shutil


def backup_command(repository, password_file, source):
    restic = shutil.which("restic")
    if not restic:
        raise FileNotFoundError("restic is not installed")
    repository = Path(repository).expanduser()
    password_file = Path(password_file).expanduser()
    source = Path(source).expanduser()
    if not password_file.is_file():
        raise FileNotFoundError("restic password file is unavailable")
    if not source.is_dir():
        raise FileNotFoundError("backup source is unavailable")
    return (
        restic,
        ["--repo", str(repository), "backup", str(source), "--json"],
        {"RESTIC_PASSWORD_FILE": str(password_file)},
    )
