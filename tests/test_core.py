import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        os.environ["HOME"] = str(self.home)
        os.environ["XDG_CONFIG_HOME"] = str(self.home / "cfg")
        os.environ["XDG_DATA_HOME"] = str(self.home / "data")

    def tearDown(self):
        self.tmp.cleanup()

    def _tables(self):
        d = self.home / "tables"
        (d / "sub").mkdir(parents=True)
        for name in ("Twilight Zone (Bally 1993) VPW.vpx", "sub/Addams Family.vpx", "sub/._junk.vpx", "sub/notes.txt"):
            (d / name).write_bytes(b"x")
        (d / "Twilight Zone (Bally 1993) VPW.png").write_bytes(b"png")
        return d

    def test_scan_finds_tables_and_sidecar(self):
        from vpxlauncher.scanner import scan_directories

        d = self._tables()
        items = scan_directories([str(d), str(d / "nie-ma")])
        self.assertEqual([i["name"] for i in items], ["Addams Family", "Twilight Zone (Bally 1993) VPW"])
        self.assertTrue(items[1]["artwork"].endswith(".png"))
        self.assertEqual(items[0]["artwork"], "")

    def test_library_flow(self):
        from vpxlauncher.library import Library
        from vpxlauncher.scanner import scan_directories

        lib = Library(self.home / "data" / "lib.db")
        items = scan_directories([str(self._tables())])
        self.assertEqual(sum(lib.upsert(i) for i in items), 2)
        self.assertEqual(sum(lib.upsert(i) for i in items), 0)  # ponowny skan nie dubluje
        lib.commit()
        rows = lib.list_tables()
        self.assertEqual(len(rows), 2)

        tz = next(r for r in rows if r["name"].startswith("Twilight"))
        lib.toggle_favorite(tz["id"])
        self.assertEqual([r["name"] for r in lib.list_tables(favorites_only=True)], [tz["name"]])
        lib.record_play(tz["id"])
        time.sleep(0.01)
        self.assertEqual(lib.list_tables(sort="recent")[0]["id"], tz["id"])
        self.assertEqual(len(lib.list_tables(query="addams")), 1)
        self.assertEqual(len(lib.list_tables(query="ŻŻŻ")), 0)

        os.remove(tz["path"])
        lib.refresh_missing()
        self.assertEqual(lib.count(), 1)

    def test_settings_roundtrip_and_detection(self):
        from vpxlauncher import config

        exe_dir = self.home / "Gry" / "VPinballX_BGFX-10.8.1-x" / "tables"
        exe_dir.mkdir(parents=True)
        exe = exe_dir.parent / "VPinballX_BGFX"
        exe.write_bytes(b"#!/bin/sh")
        s = config.Settings.load()
        if not config.IS_WINDOWS:
            self.assertEqual(s.vpx_executable, str(exe))
            self.assertEqual(s.table_dirs, [str(exe_dir)])
            self.assertTrue(s.prime_run)
            self.assertEqual(s.env, {"SDL_VIDEODRIVER": "x11"})
        s.extra_args = "-minimized"
        s.language = "pl"
        s.graphics_backend = "Vulkan"
        s.cheat = True
        s.prime_run = False
        s.save()
        self.assertEqual(config.Settings.load().extra_args, "-minimized")
        self.assertEqual(config.Settings.load().language, "pl")
        self.assertEqual(config.Settings.load().graphics_backend, "Vulkan")
        self.assertTrue(config.Settings.load().cheat)
        self.assertFalse(config.Settings.load().prime_run)

    def test_env_and_args_parsing(self):
        from vpxlauncher import config

        self.assertEqual(config.text_to_env("A=1\n# x\n\nB = two words \nbad"), {"A": "1", "B": "two words"})
        self.assertEqual(config.split_args('-a "b c" -d'), ["-a", "b c", "-d"])
        self.assertEqual(config.split_args("  "), [])

    def test_language_defaults_to_english_and_translates(self):
        from vpxlauncher import config, i18n

        self.assertEqual(config.Settings.load().language, "en")
        self.assertEqual(i18n.translate("en", "Settings"), "Settings")
        self.assertEqual(i18n.translate("pl", "Settings"), "Ustawienia")
        self.assertEqual(i18n.translate("unknown", "Settings"), "Settings")


if __name__ == "__main__":
    unittest.main()
