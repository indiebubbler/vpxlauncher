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

    def test_reads_wpc_bcd_score_and_initials(self):
        from vpxlauncher.scores import scan_nvram_directory

        data = bytearray(8192)
        data[7299:7302] = b"ABC"
        data[7302:7307] = bytes.fromhex("00 12 34 56 78")
        (self.root / "taf_l7.nv").write_bytes(data)

        record = scan_nvram_directory(self.root)[0]
        self.assertEqual(record["title"], "The Addams Family")
        self.assertEqual(record["label"], "Grand Champion")
        self.assertEqual(record["initials"], "ABC")
        self.assertEqual((record["score"], record["scoreText"]), (12345678, "12 345 678"))

    def test_reads_little_endian_stern_sam_score(self):
        from vpxlauncher.scores import scan_nvram_directory

        data = bytearray(0x20000)
        data[14332:14336] = b"SSR\0"
        data[14356:14364] = (75_000_000).to_bytes(8, "little")
        (self.root / "acd_170h.nv").write_bytes(data)

        record = scan_nvram_directory(self.root)[0]
        self.assertEqual(record["initials"], "SSR")
        self.assertEqual(record["score"], 75_000_000)

    def test_reads_packed_nibbles(self):
        from vpxlauncher.scores import scan_nvram_directory

        data = bytearray([0xFF] * 256)
        data[166:173] = bytes((0x1F, 0x2E, 0x3D, 0x4C, 0x5B, 0x6A, 0x79))
        (self.root / "centaur.nv").write_bytes(data)

        record = scan_nvram_directory(self.root)[0]
        self.assertEqual((record["score"], record["scoreText"]), (7654321, "7 654 321"))

    def test_lists_unknown_roms_and_skips_empty_scores(self):
        from vpxlauncher.scores import scan_nvram_directory

        (self.root / "centaur.nv").write_bytes(bytes([0xFF] * 302))
        (self.root / "unknown.nv").write_bytes(bytes(302))

        records = {record["rom"]: record for record in scan_nvram_directory(self.root)}
        self.assertEqual(records["centaur"]["status"], "empty")
        self.assertEqual(records["unknown"]["status"], "unsupported")

    def test_short_known_file_and_nonexistent_directory(self):
        from vpxlauncher.scores import scan_nvram_directory

        (self.root / "taf_l7.nv").write_bytes(b"short")
        record = scan_nvram_directory(self.root)[0]
        self.assertEqual(record["status"], "invalid")
        self.assertTrue(record["error"])
        with self.assertRaises(FileNotFoundError):
            scan_nvram_directory(self.root / "missing")


if __name__ == "__main__":
    unittest.main()
