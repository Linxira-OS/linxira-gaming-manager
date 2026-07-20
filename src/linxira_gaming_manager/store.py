import json
from pathlib import Path
import sqlite3
import uuid


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT,
    name TEXT NOT NULL,
    install_path TEXT NOT NULL,
    executable TEXT,
    prefix_path TEXT,
    launch_args TEXT NOT NULL DEFAULT '[]',
    UNIQUE(source, external_id)
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    kind TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
"""


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self):
        self.connection.close()

    def games(self):
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM games ORDER BY name COLLATE NOCASE"
        )]

    def upsert_discovered(self, game):
        game_id = game.get("id") or str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"linxira:{game['source']}:{game['external_id']}",
        ))
        self.connection.execute(
            """
            INSERT INTO games(id, source, external_id, name, install_path, executable, prefix_path, launch_args)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, external_id) DO UPDATE SET
                name=excluded.name,
                install_path=excluded.install_path,
                executable=COALESCE(excluded.executable, games.executable),
                prefix_path=COALESCE(excluded.prefix_path, games.prefix_path)
            """,
            (
                game_id,
                game["source"],
                game["external_id"],
                game["name"],
                game["install_path"],
                game.get("executable"),
                game.get("prefix_path"),
                json.dumps(game.get("launch_args", [])),
            ),
        )
        self.connection.commit()
        return game_id

    def add_imported(self, name, executable, prefix_path=None):
        executable = str(Path(executable).resolve())
        return self.upsert_discovered({
            "id": str(uuid.uuid4()),
            "source": "imported",
            "external_id": executable,
            "name": name,
            "install_path": str(Path(executable).parent),
            "executable": executable,
            "prefix_path": str(Path(prefix_path).resolve()) if prefix_path else None,
        })

    def record(self, kind, subject, status, detail=""):
        self.connection.execute(
            "INSERT INTO activity(kind, subject, status, detail) VALUES (?, ?, ?, ?)",
            (kind, subject, status, detail),
        )
        self.connection.commit()

    def activity(self, limit=100):
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,)
        )]
