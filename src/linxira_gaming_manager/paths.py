import os
from pathlib import Path


def data_home():
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))


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
