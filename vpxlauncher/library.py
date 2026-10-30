"""Biblioteka stołów w SQLite."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tables (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    author      TEXT NOT NULL DEFAULT '',
    version     TEXT NOT NULL DEFAULT '',
    artwork     TEXT NOT NULL DEFAULT '',
    favorite    INTEGER NOT NULL DEFAULT 0,
    play_count  INTEGER NOT NULL DEFAULT 0,
    last_played REAL,
    added       REAL NOT NULL,
    missing     INTEGER NOT NULL DEFAULT 0
)
"""


class Library:
    def __init__(self, db_path: str | os.PathLike):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path))
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)
        columns = {r["name"] for r in self.db.execute("PRAGMA table_info(tables)")}
        if "art_tried" not in columns:  # migracja ze starszej wersji bazy
            self.db.execute("ALTER TABLE tables ADD COLUMN art_tried INTEGER NOT NULL DEFAULT 0")
        if "removed" not in columns:  # stoły usunięte przez użytkownika (skan ich nie przywraca)
            self.db.execute("ALTER TABLE tables ADD COLUMN removed INTEGER NOT NULL DEFAULT 0")
        self.db.commit()

    def upsert(self, item: dict, restore: bool = False) -> bool:
        """Dodaje lub odświeża stół. Zwraca True, jeśli stół jest nowy lub przywrócony.

        Stoły usunięte przez użytkownika są pomijane przy skanowaniu; wracają tylko po
        ręcznym dodaniu (restore=True) albo przez restore_removed().
        """
        row = self.db.execute("SELECT id, removed FROM tables WHERE path = ?", (item["path"],)).fetchone()
        was_removed = bool(row and row["removed"])
        if was_removed:
            if not restore:
                return False
            self.db.execute("UPDATE tables SET removed = 0, art_tried = 0 WHERE id = ?", (row["id"],))
        if row:
            self.db.execute(
                "UPDATE tables SET author = ?, version = ?, missing = 0,"
                " artwork = CASE WHEN artwork = '' THEN ? ELSE artwork END WHERE id = ?",
                (item.get("author", ""), item.get("version", ""), item.get("artwork", ""), row["id"]),
            )
            return was_removed
        self.db.execute(
            "INSERT INTO tables (path, name, author, version, artwork, added) VALUES (?, ?, ?, ?, ?, ?)",
            (
                item["path"],
                item["name"],
                item.get("author", ""),
                item.get("version", ""),
                item.get("artwork", ""),
                time.time(),
            ),
        )
        return True

    def commit(self) -> None:
        self.db.commit()

    def get(self, table_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM tables WHERE missing = 0 AND removed = 0").fetchone()[0]

    def list_tables(self, query: str = "", favorites_only: bool = False, sort: str = "name") -> list[dict]:
        rows = [dict(r) for r in self.db.execute("SELECT * FROM tables WHERE missing = 0 AND removed = 0")]
        q = query.strip().casefold()
        if q:
            rows = [r for r in rows if q in r["name"].casefold() or q in (r["author"] or "").casefold()]
        if favorites_only:
            rows = [r for r in rows if r["favorite"]]
        rows.sort(key=lambda r: r["name"].casefold())  # remisy w pozostałych sortowaniach
        if sort == "recent":
            rows.sort(key=lambda r: r["last_played"] or 0, reverse=True)
        elif sort == "most":
            rows.sort(key=lambda r: r["play_count"], reverse=True)
        elif sort == "added":
            rows.sort(key=lambda r: r["added"], reverse=True)
        return rows

    def toggle_favorite(self, table_id: int) -> None:
        self.db.execute("UPDATE tables SET favorite = 1 - favorite WHERE id = ?", (table_id,))
        self.db.commit()

    def record_play(self, table_id: int) -> None:
        self.db.execute(
            "UPDATE tables SET play_count = play_count + 1, last_played = ? WHERE id = ?",
            (time.time(), table_id),
        )
        self.db.commit()

    def set_artwork(self, table_id: int, path: str) -> None:
        self.db.execute("UPDATE tables SET artwork = ? WHERE id = ?", (path, table_id))
        self.db.commit()

    def missing_artwork(self, only_untried: bool) -> list[dict]:
        """Stoły bez grafiki; only_untried pomija te, dla których już próbowano pobrać obraz."""
        sql = "SELECT * FROM tables WHERE missing = 0 AND removed = 0 AND artwork = ''"
        if only_untried:
            sql += " AND art_tried = 0"
        return [dict(r) for r in self.db.execute(sql + " ORDER BY name COLLATE NOCASE")]

    def mark_art_tried(self, table_id: int) -> None:
        self.db.execute("UPDATE tables SET art_tried = 1 WHERE id = ?", (table_id,))
        self.db.commit()

    def remove(self, table_id: int) -> None:
        """Usuwa stół z biblioteki na stałe: wiersz zostaje jako znacznik, więc skan go nie doda."""
        self.db.execute("UPDATE tables SET removed = 1, artwork = '' WHERE id = ?", (table_id,))
        self.db.commit()

    def restore_removed(self) -> int:
        cur = self.db.execute("UPDATE tables SET removed = 0, art_tried = 0 WHERE removed = 1")
        self.db.commit()
        return cur.rowcount

    def removed_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM tables WHERE removed = 1").fetchone()[0]

    def delete(self, table_id: int) -> None:
        self.db.execute("DELETE FROM tables WHERE id = ?", (table_id,))
        self.db.commit()

    def refresh_missing(self) -> None:
        for row in self.db.execute("SELECT id, path, missing FROM tables").fetchall():
            gone = 0 if os.path.isfile(row["path"]) else 1
            if gone != row["missing"]:
                self.db.execute("UPDATE tables SET missing = ? WHERE id = ?", (gone, row["id"]))
        self.db.commit()
