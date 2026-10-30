import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vpxlauncher import vps  # noqa: E402

RAW = [
    {
        "name": "Twilight Zone", "manufacturer": "Bally", "year": 1993,
        "tableFiles": [
            {"tableFormat": "FP", "imgUrl": "https://img.example/fp.webp", "authors": ["Someone"]},
            {"tableFormat": "VPX", "imgUrl": "https://img.example/old.webp", "authors": ["Old Author"], "version": "1.0"},
            {"tableFormat": "VPX", "imgUrl": "https://img.example/vpw.webp", "authors": ["VPin Workshop (VPW)"], "version": "1.0.1"},
        ],
        "imgUrl": "https://img.example/tz_cover.webp",
    },
    {"name": "The Addams Family", "manufacturer": "Bally", "year": 1992,
     "tableFiles": [{"tableFormat": "VPX", "imgUrl": "https://img.example/taf.webp"}]},
    {"name": "Aliens", "manufacturer": "Original", "year": 2020,
     "tableFiles": [{"tableFormat": "VPX", "imgUrl": "https://img.example/aliens_orig.webp"}]},
    {"name": "Aliens", "manufacturer": "Data East", "year": 1993,
     "tableFiles": [{"tableFormat": "VPX", "imgUrl": "https://img.example/aliens_de.webp"}]},
    {"name": "Cover Only", "manufacturer": "X", "year": 1980, "tableFiles": [], "imgUrl": "https://img.example/cover.webp"},
    {"name": "Broken Img", "year": "n/a", "tableFiles": [{"tableFormat": "VPX", "imgUrl": "https://img.example/undefined_table_1.webp"}]},
    {"nie": "gra"},
]


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.index = vps.VpsIndex(vps.compact(RAW))

    def test_parse_stem(self):
        self.assertEqual(vps.parse_stem("Twilight Zone (Bally 1993) VPW 1.0"), ("Twilight Zone", 1993, "Bally"))
        self.assertEqual(vps.parse_stem("Addams_Family VPW v2.1 MOD")[0], "Addams Family")
        self.assertEqual(vps.parse_stem("Gra (Original 2020)"), ("Gra", 2020, "Original"))

    def test_title_key(self):
        self.assertEqual(vps.title_key("The Addams Family"), vps.title_key("Addams Family, The"))
        self.assertEqual(vps.title_key("Zażółć & Gęślą"), "zazolcandgesla")

    def test_find_exact_and_the(self):
        self.assertEqual(self.index.find("Twilight Zone (Bally 1993) VPW")["name"], "Twilight Zone")
        self.assertEqual(self.index.find("Addams Family (Bally 1992)")["name"], "The Addams Family")

    def test_year_and_manufacturer_disambiguate(self):
        self.assertEqual(self.index.find("Aliens (Data East 1993)")["mfr"], "Data East")
        self.assertEqual(self.index.find("Aliens (Original 2020)")["mfr"], "Original")

    def test_wrong_year_rejected_and_unknown(self):
        self.assertIsNone(self.index.find("Twilight Zone (Williams 1970)"))
        self.assertIsNone(self.index.find("Zupełnie Nieznany Stół"))

    def test_small_typo_fuzzy(self):
        self.assertEqual(self.index.find("Twilight Zon (Bally 1993)")["name"], "Twilight Zone")

    def test_image_choice(self):
        tz = self.index.find("Twilight Zone (Bally 1993) VPW")
        self.assertEqual(self.index.image_url(tz, "Twilight Zone (Bally 1993) VPW"), "https://img.example/vpw.webp")
        # bez wskazówek: pierwszy zrzut VPX (nigdy zrzut innego formatu)
        self.assertEqual(self.index.image_url(tz, "Twilight Zone"), "https://img.example/old.webp")
        cover = self.index.find("Cover Only (X 1980)")
        self.assertEqual(self.index.image_url(cover, "Cover Only"), "https://img.example/cover.webp")
        broken = [g for g in self.index.games if g["name"] == "Broken Img"][0]
        self.assertEqual(self.index.image_url(broken, "Broken Img"), "")


class NetworkAndCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "vps-index.json"
        self._orig = vps.http_get

    def tearDown(self):
        vps.http_get = self._orig
        self.tmp.cleanup()

    def test_download_builds_and_caches_compact_index(self):
        calls = []

        def fake(url, timeout=30, max_bytes=0):
            calls.append(url)
            if "dead" in url:
                raise OSError("404")
            return json.dumps(RAW).encode()

        vps.http_get = fake
        idx = vps.VpsIndex.load(self.cache, ["https://dead.example/db.json"])
        self.assertTrue(calls[0].startswith("https://dead"))  # własny adres próbowany pierwszy
        self.assertEqual(len(calls), 2)  # po porażce przechodzi do oficjalnego
        self.assertEqual(idx.find("Twilight Zone (Bally 1993)")["name"], "Twilight Zone")
        self.assertTrue(self.cache.is_file())

        vps.http_get = lambda *a, **k: (_ for _ in ()).throw(AssertionError("nie powinno być sieci"))
        self.assertEqual(vps.VpsIndex.load(self.cache).find("Aliens (Data East 1993)")["mfr"], "Data East")

    def test_stale_cache_used_when_offline(self):
        self.cache.write_text(json.dumps(vps.compact(RAW)))
        old = time.time() - 30 * 86400
        os.utime(self.cache, (old, old))
        vps.http_get = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))
        self.assertEqual(vps.VpsIndex.load(self.cache).find("Addams Family (Bally 1992)")["name"], "The Addams Family")

    def test_offline_without_cache_raises(self):
        vps.http_get = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))
        with self.assertRaises(RuntimeError):
            vps.VpsIndex.load(self.cache)

    def test_https_only_and_sniffing(self):
        with self.assertRaises(ValueError):
            self._orig("http://example.com/a.png")
        with self.assertRaises(ValueError):
            self._orig("file:///etc/passwd")
        self.assertEqual(vps.sniff_image_ext(b"\x89PNG\r\n\x1a\n...."), ".png")
        self.assertEqual(vps.sniff_image_ext(b"\xff\xd8\xff\xe0"), ".jpg")
        self.assertEqual(vps.sniff_image_ext(b"RIFF\x00\x00\x00\x00WEBPVP8 "), ".webp")
        self.assertIsNone(vps.sniff_image_ext(b"<html>not an image</html>"))


class LibraryMigrationTests(unittest.TestCase):
    def test_old_database_gets_art_tried_and_queries_work(self):
        from vpxlauncher.library import Library

        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "old.db"
            con = sqlite3.connect(db)
            con.execute(
                "CREATE TABLE tables (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL UNIQUE, name TEXT NOT NULL,"
                " author TEXT NOT NULL DEFAULT '', version TEXT NOT NULL DEFAULT '', artwork TEXT NOT NULL DEFAULT '',"
                " favorite INTEGER NOT NULL DEFAULT 0, play_count INTEGER NOT NULL DEFAULT 0, last_played REAL,"
                " added REAL NOT NULL, missing INTEGER NOT NULL DEFAULT 0)"
            )
            con.execute("INSERT INTO tables (path, name, added) VALUES ('/a.vpx', 'A', 1)")
            con.execute("INSERT INTO tables (path, name, artwork, added) VALUES ('/b.vpx', 'B', '/x.png', 1)")
            con.commit()
            con.close()

            lib = Library(db)
            self.assertEqual([r["name"] for r in lib.missing_artwork(only_untried=True)], ["A"])
            lib.mark_art_tried(1)
            self.assertEqual(lib.missing_artwork(only_untried=True), [])
            self.assertEqual([r["name"] for r in lib.missing_artwork(only_untried=False)], ["A"])


if __name__ == "__main__":
    unittest.main()
