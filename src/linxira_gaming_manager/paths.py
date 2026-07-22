import os
from pathlib import Path
import stat
from uuid import UUID


def data_home():
    configured = os.environ.get("XDG_DATA_HOME")
    return Path(configured) if configured else Path.home() / ".local/share"


def state_home():
    configured = os.environ.get("XDG_STATE_HOME")
    return Path(configured) if configured else Path.home() / ".local/state"


def _canonical_game_id(game_id):
    try:
        normalized = str(UUID(game_id))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Game ID is not a canonical UUID") from error
    if normalized != game_id:
        raise ValueError("Game ID is not a canonical UUID")
    return normalized


def game_data_path(game_id):
    return data_home() / "linxira/gaming-manager/games" / _canonical_game_id(game_id)


def game_prefix_path(game_id):
    return game_data_path(game_id) / "prefix"


def game_log_path(game_id, timestamp):
    game_id = _canonical_game_id(game_id)
    return state_home() / "linxira/gaming-manager/games" / game_id / "logs" / f"{timestamp}.log"


def ensure_private_directory(path, boundary, anchor):
    path = Path(path)
    boundary = Path(boundary)
    anchor = Path(anchor)
    try:
        relative = path.relative_to(boundary)
        boundary_relative = boundary.relative_to(anchor)
    except ValueError as error:
        raise ValueError("Managed path is outside Linxira storage") from error
    anchor.mkdir(parents=True, exist_ok=True, mode=0o700)
    current = anchor
    for part in (*boundary_relative.parts, *relative.parts):
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o700)
            metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("Managed path contains a symlink or non-directory")
        current.chmod(0o700)
    return path


def state_path():
    return Path(
        os.environ.get(
            "LINXIRA_GAMING_STATE_PATH",
            data_home() / "linxira/gaming-manager/state.db",
        )
    )


def steam_roots():
    configured = os.environ.get("LINXIRA_STEAM_ROOTS")
    if configured:
        return [Path(value) for value in configured.split(os.pathsep) if value]
    return [
        data_home() / "Steam",
        Path.home() / ".steam/steam",
        Path.home() / ".local/share/Steam",
    ]
