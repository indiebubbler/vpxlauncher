import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class NVRAMScoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_known_bally_score_layout(self):
        from vpxlauncher.scores import scan_nvram_directory

        data = bytearray([0xFF] * 302)
        for offset, digit in zip(range(171, 165, -1), (8, 8, 5, 0, 5, 0)):
            data[offset] = (digit << 4) | 0x0F
        (self.root / "elektra.nv").write_bytes(data)

        record = scan_nvram_directory(self.root)[0]
        self.assertEqual((record["score"], record["scoreText"], record["status"]), (885050, "885 050", "score"))

    def test_reads_known_stern_score_layout(self):
        from vpxlauncher.scores import scan_nvram_directory

        data = bytearray(302)
        data[202:206] = bytes((0x00, 0x18, 0x03, 0x40))
        (self.root / "seawitch.nv").write_bytes(data)

        record = scan_nvram_directory(self.root)[0]
        self.assertEqual(record["score"], 180340)

    def test_reads_known_williams_score_layout_and_marks_unknown(self):
        from vpxlauncher.scores import scan_nvram_directory

        data = bytearray([0xFF] * 302)
        data[72:78] = bytes((0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5))
        (self.root / "scrpn_l1.nv").write_bytes(data)
        (self.root / "unknown.nv").write_bytes(bytes(302))

        records = scan_nvram_directory(self.root)
        self.assertEqual(records[0]["score"], 12345)
        self.assertEqual(records[1]["status"], "unsupported")

    def test_empty_known_file_and_nonexistent_directory(self):
        from vpxlauncher.scores import scan_nvram_directory

        (self.root / "elektra.nv").write_bytes(bytes([0xFF] * 302))
        self.assertEqual(scan_nvram_directory(self.root)[0]["status"], "empty")
        with self.assertRaises(FileNotFoundError):
            scan_nvram_directory(self.root / "missing")

    def test_invalid_known_layout_is_reported(self):
        from vpxlauncher.scores import scan_nvram_directory

        (self.root / "elektra.nv").write_bytes(b"short")
        record = scan_nvram_directory(self.root)[0]
        self.assertEqual(record["status"], "invalid")
        self.assertTrue(record["error"])


if __name__ == "__main__":
    unittest.main()
