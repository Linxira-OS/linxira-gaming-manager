import json
from dataclasses import dataclass
import os
from pathlib import Path
import shutil

from .paths import game_prefix_path


@dataclass(frozen=True)
class LaunchSpec:
    program: str
    arguments: tuple[str, ...]
    environment: dict[str, str]
    working_directory: str


ENVIRONMENT_KEYS = {
    "HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "DISPLAY", "WAYLAND_DISPLAY",
    "XAUTHORITY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS",
    "PULSE_SERVER", "PIPEWIRE_REMOTE", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME", "XDG_STATE_HOME", "DRI_PRIME",
    "__GLX_VENDOR_LIBRARY_NAME", "__NV_PRIME_RENDER_OFFLOAD",
    "__VK_LAYER_NV_optimus",
}
RUNNER_PATHS = {
    "steam": Path("/usr/bin/steam"),
    "umu": Path("/usr/bin/umu-run"),
    "wine": Path("/usr/bin/wine"),
}


def _environment(prefix, runner, source=None):
    current = os.environ if source is None else source
    environment = {
        key: value for key, value in current.items()
        if key in ENVIRONMENT_KEYS or key in {"LC_ALL", "LC_CTYPE", "LC_MESSAGES"}
    }
    environment["PATH"] = "/usr/bin"
    if prefix is not None:
        environment["WINEPREFIX"] = str(prefix)
    if runner == "umu":
        environment["GAMEID"] = "umu-default"
        environment["STORE"] = "none"
    return environment


def _arguments(game):
    arguments = json.loads(game.get("launch_args") or "[]")
    if not isinstance(arguments, list) or not all(
        isinstance(value, str) and "\x00" not in value for value in arguments
    ):
        raise ValueError("Invalid launch arguments")
    return arguments


def launch_spec(game, environment=None):
    if game["source"] == "steam":
        steam = RUNNER_PATHS["steam"]
        if not steam.is_file():
            raise FileNotFoundError("Steam is not installed")
        return LaunchSpec(
            str(steam),
            (f"steam://rungameid/{game['external_id']}",),
            _environment(None, "steam", environment),
            str(Path.home()),
        )

    executable = Path(game.get("executable") or "").resolve()
    if not executable.is_file() or executable.suffix.lower() != ".exe":
        raise FileNotFoundError("Imported Windows executable is unavailable")
    game_id = game.get("id")
    if not isinstance(game_id, str) or not game_id:
        raise ValueError("Imported game has no stable ID")
    expected_prefix = game_prefix_path(game_id)
    prefix = Path(game.get("prefix_path") or "")
    if prefix != expected_prefix:
        raise ValueError("Imported game prefix is outside managed Linxira storage")
    if prefix.is_symlink() or prefix.parent.is_symlink():
        raise ValueError("Imported game prefix contains a symlink")
    runner = game.get("runner")
    if runner not in {"umu", "wine"}:
        raise ValueError("Imported game has an unsupported compatibility runner")
    program = RUNNER_PATHS[runner]
    if not program.is_file():
        raise FileNotFoundError(f"Compatibility runner is not installed: {program.name}")
    arguments = (str(executable), *_arguments(game))
    return LaunchSpec(
        str(program),
        arguments,
        _environment(prefix, runner, environment),
        str(executable.parent),
    )


def launch_command(game):
    spec = launch_spec(game)
    return spec.program, list(spec.arguments)


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
