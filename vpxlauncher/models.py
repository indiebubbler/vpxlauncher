"""Model listy stołów dla QML."""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QUrl

ROLES = ["tableId", "title", "author", "version", "artwork", "favorite", "playCount", "lastPlayed"]
FIRST_ROLE = 0x0100 + 1  # Qt::UserRole + 1


def present(row: dict) -> dict:
    art = row.get("artwork") or ""
    url = QUrl.fromLocalFile(art).toString() if art and os.path.isfile(art) else ""
    last = row.get("last_played")
    return {
        "tableId": row["id"],
        "title": row["name"],
        "author": row.get("author") or "",
        "version": row.get("version") or "",
        "artwork": url,
        "favorite": bool(row.get("favorite")),
        "playCount": int(row.get("play_count") or 0),
        "lastPlayed": datetime.fromtimestamp(last).strftime("%d.%m.%Y") if last else "",
    }


class TableModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def roleNames(self):
        return {FIRST_ROLE + i: name.encode() for i, name in enumerate(ROLES)}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        offset = int(role) - FIRST_ROLE
        if 0 <= offset < len(ROLES):
            return self._rows[index.row()][ROLES[offset]]
        return None

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = [present(r) for r in rows]
        self.endResetModel()

    def update_row(self, row: dict | None) -> None:
        """Odświeża jeden kafelek bez resetowania widoku (zachowuje przewinięcie)."""
        if row is None:
            return
        for i, existing in enumerate(self._rows):
            if existing["tableId"] == row["id"]:
                self._rows[i] = present(row)
                idx = self.index(i, 0)
                self.dataChanged.emit(idx, idx)
                return
