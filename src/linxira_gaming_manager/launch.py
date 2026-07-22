import json
from pathlib import Path
import shutil


def launch_command(game):
    if game["source"] == "steam":
        steam = shutil.which("steam")
        if not steam:
            raise FileNotFoundError("Steam is not installed")
        return steam, [f"steam://rungameid/{game['external_id']}"]

    executable = Path(game.get("executable") or "")
    if not executable.is_file():
        raise FileNotFoundError("Imported executable is unavailable")
    arguments = json.loads(game.get("launch_args") or "[]")
    if not isinstance(arguments, list) or not all(isinstance(value, str) for value in arguments):
        raise ValueError("Invalid launch arguments")
    return str(executable), arguments


def tool_status():
    return {
        "Steam": shutil.which("steam"),
        "UMU Launcher": shutil.which("umu-run"),
        "Wine": shutil.which("wine"),
        "Protontricks": shutil.which("protontricks"),
        "Winetricks": shutil.which("winetricks"),
        "restic": shutil.which("restic"),
        "GameMode": shutil.which("gamemoderun"),
        "Gamescope": shutil.which("gamescope"),
        "MangoHud": shutil.which("mangohud"),
    }
