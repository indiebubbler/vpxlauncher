import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class RemovedTablesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["HOME"] = str(self.home)
        os.environ["XDG_CONFIG_HOME"] = str(self.home / "cfg")
        os.environ["XDG_DATA_HOME"] = str(self.home / "data")
        self.tables = self.home / "tables"
        self.tables.mkdir()
        for n in ("A", "B"):
            (self.tables / f"{n}.vpx").write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def _lib(self):
        from vpxlauncher.library import Library
        return Library(self.home / "data" / "lib.db")

    def test_removed_table_is_not_readded_by_scan(self):
        from vpxlauncher.scanner import scan_directories

        lib = self._lib()
        items = scan_directories([str(self.tables)])
        for i in items:
            lib.upsert(i)
        lib.commit()
        a = next(r for r in lib.list_tables() if r["name"] == "A")
        lib.set_artwork(a["id"], "/x/art.png")
        lib.remove(a["id"])

        self.assertEqual(lib.count(), 1)
        self.assertEqual(lib.removed_count(), 1)
        self.assertEqual([r["name"] for r in lib.list_tables()], ["B"])
        self.assertEqual(lib.get(a["id"])["artwork"], "")

        # ponowny skan: A nie wraca, nic nowego
        self.assertEqual(sum(lib.upsert(i) for i in scan_directories([str(self.tables)])), 0)
        lib.commit()
        self.assertEqual([r["name"] for r in lib.list_tables()], ["B"])
        self.assertEqual(lib.missing_artwork(only_untried=False)[0]["name"], "B")
        self.assertEqual(len(lib.missing_artwork(only_untried=False)), 1)

    def test_manual_add_and_restore_bring_it_back(self):
        from vpxlauncher.scanner import build_item

        lib = self._lib()
        item = build_item(self.tables / "A.vpx")
        lib.upsert(item)
        tid = lib.list_tables()[0]["id"]
        lib.remove(tid)
        self.assertEqual(lib.count(), 0)

        self.assertTrue(lib.upsert(item, restore=True))  # ręczne dodanie przywraca
        self.assertEqual(lib.count(), 1)
        self.assertEqual(lib.removed_count(), 0)

        lib.remove(tid)
        self.assertEqual(lib.restore_removed(), 1)  # "Przywróć usunięte"
        self.assertEqual(lib.count(), 1)
        self.assertEqual(lib.restore_removed(), 0)

    def test_old_database_gets_removed_column(self):
        from vpxlauncher.library import Library

        db = self.home / "old.db"
        con = sqlite3.connect(db)
        con.execute(
            "CREATE TABLE tables (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL UNIQUE, name TEXT NOT NULL,"
            " author TEXT NOT NULL DEFAULT '', version TEXT NOT NULL DEFAULT '', artwork TEXT NOT NULL DEFAULT '',"
            " favorite INTEGER NOT NULL DEFAULT 0, play_count INTEGER NOT NULL DEFAULT 0, last_played REAL,"
            " added REAL NOT NULL, missing INTEGER NOT NULL DEFAULT 0, art_tried INTEGER NOT NULL DEFAULT 0)"
        )
        con.execute("INSERT INTO tables (path, name, added) VALUES ('/a.vpx', 'A', 1)")
        con.commit()
        con.close()
        lib = Library(db)
        self.assertEqual(lib.count(), 1)  # migracja nie gubi istniejących wierszy
        lib.remove(1)
        self.assertEqual(lib.removed_count(), 1)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["HOME"] = str(self.home)
        os.environ["XDG_CONFIG_HOME"] = str(self.home / "cfg")

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_log_path_and_tile_size_roundtrip(self):
        from vpxlauncher import config

        s = config.Settings.load()
        if not config.IS_WINDOWS:
            self.assertEqual(s.log_path, str(self.home / ".local/share/VPinballX/10.8/vpinball.log"))
        self.assertEqual(s.tile_size, 1)
        s.tile_size = 4
        s.log_path = "/tmp/custom.log"
        s.save()
        again = config.Settings.load()
        self.assertEqual((again.tile_size, again.log_path), (4, "/tmp/custom.log"))

    def test_bad_values_are_sanitised(self):
        from vpxlauncher import config

        path = config.Settings.path()
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"tile_size": 99, "log_path": ""}))
        s = config.Settings.load()
        self.assertEqual(s.tile_size, 4)
        self.assertTrue(s.log_path.endswith("vpinball.log"))
        path.write_text(json.dumps({"tile_size": "x"}))
        self.assertEqual(config.Settings.load().tile_size, 1)


if __name__ == "__main__":
    unittest.main()
