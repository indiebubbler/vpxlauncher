import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vpxlauncher import displays  # noqa: E402
from vpxlauncher.displays import ScreenInfo  # noqa: E402

LAPTOP = ScreenInfo("eDP-1", 1920, 1080, True)
EXT = ScreenInfo("DP-2", 3840, 2160, False)


class PickTests(unittest.TestCase):
    def test_auto_prefers_external(self):
        self.assertEqual(displays.pick_auto([LAPTOP, EXT]), 1)
        self.assertEqual(displays.pick_auto([LAPTOP]), 0)
        self.assertEqual(displays.pick_auto([]), 0)

    def test_auto_when_external_is_primary(self):
        self.assertEqual(displays.pick_auto([ScreenInfo("DP-2", 1, 1, True), ScreenInfo("eDP-1", 1, 1)]), 0)

    def test_auto_without_builtin_takes_non_primary(self):
        a, b = ScreenInfo("HDMI-A-1", 1, 1, True), ScreenInfo("DP-1", 1, 1)
        self.assertEqual(displays.pick_auto([a, b]), 1)
        self.assertEqual(displays.pick_auto([ScreenInfo(r"\\.\DISPLAY1", 1, 1, True), ScreenInfo(r"\\.\DISPLAY2", 1, 1)]), 1)

    def test_resolve_modes(self):
        s = [LAPTOP, EXT]
        self.assertEqual(displays.resolve("keep", s), (None, ""))
        self.assertEqual(displays.resolve("auto", s)[0], 1)
        self.assertEqual(displays.resolve("name:eDP-1", s), (0, ""))
        idx, note = displays.resolve("name:HDMI-A-9", s)  # zapamiętany ekran odłączony
        self.assertEqual(idx, 1)
        self.assertIn("HDMI-A-9", note)
        self.assertEqual(displays.resolve("auto", [LAPTOP])[0], 0)  # bez zewnętrznego wraca na ekran 0


class IniEditTests(unittest.TestCase):
    def test_replace_existing_key_keeps_the_rest(self):
        text = "; komentarz\n[Player]\nFullScreen=1\ndisplay = 1 ; stary\nWidth=100\n[Other]\nDisplay=7\n"
        out = displays.set_ini_value(text, "Player", "Display", "0")
        self.assertEqual(out, "; komentarz\n[Player]\nFullScreen=1\ndisplay = 0\nWidth=100\n[Other]\nDisplay=7\n")

    def test_insert_into_section_before_next_section(self):
        out = displays.set_ini_value("[Player]\nWidth=1\n\n[Other]\nA=1\n", "Player", "Display", "1")
        self.assertEqual(out, "[Player]\nWidth=1\nDisplay = 1\n\n[Other]\nA=1\n")

    def test_insert_into_last_section_and_missing_section(self):
        self.assertEqual(displays.set_ini_value("[Player]\nWidth=1", "Player", "Display", "1"), "[Player]\nWidth=1\nDisplay = 1\n")
        self.assertEqual(displays.set_ini_value("[Other]\nA=1\n", "Player", "Display", "1"), "[Other]\nA=1\n\n[Player]\nDisplay = 1\n")
        self.assertEqual(displays.set_ini_value("", "Player", "Display", "1"), "[Player]\nDisplay = 1\n")

    def test_crlf_preserved_and_no_prefix_match(self):
        text = "[Player]\r\nPlayfieldDisplay=3\r\nWidth=1\r\n"
        out = displays.set_ini_value(text, "Player", "Display", "0")
        self.assertIn("\r\n", out)
        self.assertNotIn("\r\r", out)
        self.assertEqual(displays.get_ini_value(out, "Player", "PlayfieldDisplay"), "3")  # nie ruszony przez 'Display'
        self.assertEqual(displays.get_ini_value(out, "Player", "Display"), "0")


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ini = Path(self.tmp.name) / "10.8" / "VPinballX.ini"
        self.ini.parent.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_writes_backup_once_and_is_idempotent(self):
        self.ini.write_bytes("[Player]\nDisplay=0\nName=Zażółć\n".encode("utf-8"))
        ok, err = displays.apply_display(self.ini, 1)
        self.assertEqual((ok, err), (True, ""))
        self.assertIn("Display=1", self.ini.read_text("utf-8"))
        self.assertIn("Zażółć", self.ini.read_text("utf-8"))
        backup = Path(str(self.ini) + displays.BACKUP_SUFFIX)
        self.assertIn("Display=0", backup.read_text("utf-8"))

        displays.apply_display(self.ini, 0)  # kolejna zmiana nie nadpisuje pierwszej kopii
        self.assertIn("Display=0", backup.read_text("utf-8"))
        before = self.ini.stat().st_mtime_ns
        self.assertEqual(displays.apply_display(self.ini, 0), (True, ""))
        self.assertEqual(self.ini.stat().st_mtime_ns, before)  # bez zmiany nie dotyka pliku

    def test_bom_and_ansi_files_roundtrip(self):
        self.ini.write_bytes(b"\xef\xbb\xbf[Player]\r\nDisplay=0\r\n")
        displays.apply_display(self.ini, 2)
        self.assertEqual(self.ini.read_bytes(), b"\xef\xbb\xbf[Player]\r\nDisplay=2\r\n")
        self.ini.write_bytes("[Player]\nDisplay=0\nNazwa=Za\xbf\n".encode("latin-1"))
        displays.apply_display(self.ini, 1)
        self.assertEqual(self.ini.read_bytes(), "[Player]\nDisplay=1\nNazwa=Za\xbf\n".encode("latin-1"))

    def test_playfielddisplay_synced_when_present(self):
        self.ini.write_text("[Player]\nPlayfieldDisplay=0\n")
        displays.apply_display(self.ini, 1)
        self.assertEqual(displays.get_ini_value(self.ini.read_text(), "Player", "PlayfieldDisplay"), "1")
        self.assertEqual(displays.get_ini_value(self.ini.read_text(), "Player", "Display"), "1")

    def test_apply_multiple_player_settings_with_one_backup(self):
        self.ini.write_text("[Player]\nDisplay=0\nPlayfieldDisplay=0\n")
        ok, error = displays.apply_player_settings(
            self.ini,
            {"Display": "1", "GfxBackend": "Vulkan"},
        )
        self.assertEqual((ok, error), (True, ""))
        text = self.ini.read_text()
        self.assertEqual(displays.get_ini_value(text, "Player", "Display"), "1")
        self.assertEqual(displays.get_ini_value(text, "Player", "PlayfieldDisplay"), "1")
        self.assertEqual(displays.get_ini_value(text, "Player", "GfxBackend"), "Vulkan")
        backup = Path(str(self.ini) + displays.BACKUP_SUFFIX)
        self.assertEqual(backup.read_text(), "[Player]\nDisplay=0\nPlayfieldDisplay=0\n")

    def test_missing_file_reports_error_without_creating_it(self):
        ok, err = displays.apply_display(self.ini, 1)
        self.assertFalse(ok)
        self.assertIn("Could not find settings file", err)
        self.assertFalse(self.ini.exists())

    def test_ini_path_next_to_log(self):
        self.assertEqual(displays.ini_path_for("/a/b/vpinball.log"), Path("/a/b/VPinballX.ini"))


class MonitorSettingTests(unittest.TestCase):
    def test_setting_default_and_sanitising(self):
        from vpxlauncher import config

        with tempfile.TemporaryDirectory() as d:
            os.environ["HOME"] = d
            os.environ["XDG_CONFIG_HOME"] = str(Path(d) / "cfg")
            s = config.Settings.load()
            self.assertEqual(s.monitor, "keep")
            s.monitor = "name:DP-2"
            s.save()
            self.assertEqual(config.Settings.load().monitor, "name:DP-2")
            config.Settings.path().write_text(json.dumps({"monitor": "cokolwiek"}))
            self.assertEqual(config.Settings.load().monitor, "keep")
            config.Settings.path().write_text(json.dumps({"monitor": "auto"}))
            self.assertEqual(config.Settings.load().monitor, "auto")


if __name__ == "__main__":
    unittest.main()
