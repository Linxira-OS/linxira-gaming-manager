import json
from pathlib import Path
import sqlite3
import uuid

from .paths import game_data_path, game_prefix_path


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
    runner TEXT NOT NULL DEFAULT 'auto',
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
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(games)")}
        if "runner" not in columns:
            self.connection.execute("ALTER TABLE games ADD COLUMN runner TEXT NOT NULL DEFAULT 'auto'")
            self.connection.commit()

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
        game_data_path(game_id)
        self.connection.execute(
            """
            INSERT INTO games(id, source, external_id, name, install_path, executable, prefix_path, launch_args, runner)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, external_id) DO UPDATE SET
                name=excluded.name,
                install_path=excluded.install_path,
                executable=COALESCE(excluded.executable, games.executable),
                prefix_path=COALESCE(excluded.prefix_path, games.prefix_path),
                runner=CASE WHEN excluded.runner = 'auto' THEN games.runner ELSE excluded.runner END
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
                game.get("runner", "auto"),
            ),
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT id FROM games WHERE source = ? AND external_id = ?",
            (game["source"], game["external_id"]),
        ).fetchone()
        return row["id"]

    def add_imported(self, name, executable, runner="umu"):
        executable_path = Path(executable).resolve()
        if not executable_path.is_file() or executable_path.suffix.lower() != ".exe":
            raise ValueError("Imported Windows games must be regular .exe files")
        if runner not in {"umu", "wine"}:
            raise ValueError("Unsupported compatibility runner")
        game_id = self.upsert_discovered({
            "id": str(uuid.uuid4()),
            "source": "imported",
            "external_id": str(executable_path),
            "name": name,
            "install_path": str(executable_path.parent),
            "executable": str(executable_path),
            "runner": runner,
        })
        prefix = str(game_prefix_path(game_id))
        self.connection.execute(
            "UPDATE games SET prefix_path = ?, runner = ? WHERE id = ?",
            (prefix, runner, game_id),
        )
        self.connection.commit()
        return game_id

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
