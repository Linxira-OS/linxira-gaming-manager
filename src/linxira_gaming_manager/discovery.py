from pathlib import Path


def _load_vdf(path):
    import vdf

    with Path(path).open(encoding="utf-8", errors="replace") as stream:
        return vdf.load(stream)


def discover_steam(roots):
    libraries = []
    seen = set()
    for root in roots:
        root = Path(root).expanduser()
        if not root.is_dir():
            continue
        library_file = root / "steamapps/libraryfolders.vdf"
        candidates = [root]
        if library_file.is_file():
            try:
                folders = _load_vdf(library_file).get("libraryfolders", {})
                candidates.extend(
                    Path(value["path"])
                    for value in folders.values()
                    if isinstance(value, dict) and value.get("path")
                )
            except (OSError, ValueError, TypeError):
                pass
        for candidate in candidates:
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                continue
            if resolved in seen or not resolved.is_dir():
                continue
            seen.add(resolved)
            libraries.append(resolved)

    games = []
    for library in libraries:
        steamapps = library / "steamapps"
        for manifest in sorted(steamapps.glob("appmanifest_*.acf")):
            try:
                state = _load_vdf(manifest).get("AppState", {})
                app_id = str(state["appid"])
                name = str(state["name"])
                install_dir = steamapps / "common" / str(state["installdir"])
            except (OSError, ValueError, TypeError, KeyError):
                continue
            games.append({
                "source": "steam",
                "external_id": app_id,
                "name": name,
                "install_path": str(install_dir),
                "prefix_path": str(steamapps / "compatdata" / app_id / "pfx"),
            })
    return games
