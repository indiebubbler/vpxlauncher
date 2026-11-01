"""Read high scores from PinMAME NVRAM files using known ROM layouts."""
from __future__ import annotations

import json
import os
from pathlib import Path

LAYOUTS_PATH = Path(__file__).resolve().parent / "assets" / "score_layouts.json"


def _layouts() -> dict:
    with LAYOUTS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)["roms"]


def _read_initials(data: bytes, entry: dict) -> str:
    offset = entry.get("initials")
    if offset is None:
        return ""
    raw = data[offset : offset + entry["initials_length"]]
    if len(raw) != entry["initials_length"]:
        raise ValueError("file is shorter than the initials area")
    if entry.get("null_terminated"):
        raw = raw.split(b"\0", 1)[0]
    return "".join(chr(byte) if 32 <= byte < 127 else " " for byte in raw).strip()


def _read_score(data: bytes, layout: dict, entry: dict) -> int:
    offset = entry["score"]
    length = entry["length"]
    raw = data[offset : offset + length]
    if len(raw) != length:
        raise ValueError("file is shorter than the score area")

    if entry["encoding"] == "int":
        if all(byte == 0xFF for byte in raw):
            return 0
        return int.from_bytes(raw, byteorder=layout["byteorder"])

    if entry["encoding"] != "bcd":
        raise ValueError(f"unknown score encoding: {entry['encoding']}")
    if layout["byteorder"] == "little":
        raw = raw[::-1]

    nibble = layout.get("nibble", "both")
    if nibble == "high":
        digits = [byte >> 4 for byte in raw]
    elif nibble == "low":
        digits = [byte & 0x0F for byte in raw]
    else:
        digits = [digit for byte in raw for digit in (byte >> 4, byte & 0x0F)]

    score = 0
    for digit in digits:
        score = score * 10 + (digit if digit < 10 else 0)
    return score


def scan_nvram_directory(directory: str | os.PathLike) -> list[dict[str, str | int]]:
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"NVRAM folder does not exist: {root}")

    layouts = _layouts()
    records: list[dict[str, str | int]] = []

    def raise_walk_error(error: OSError) -> None:
        raise error

    for current, _subdirs, filenames in os.walk(root, onerror=raise_walk_error):
        for filename in filenames:
            path = Path(current) / filename
            if filename.startswith("._") or path.suffix.casefold() != ".nv":
                continue

            rom = path.stem.casefold()
            layout = layouts.get(rom)
            try:
                data = path.read_bytes()
            except OSError as exc:
                records.append({
                    "rom": rom,
                    "title": layout["title"] if layout else rom,
                    "label": "",
                    "initials": "",
                    "score": "",
                    "scoreText": "",
                    "status": "read_error",
                    "error": str(exc),
                    "_order": 0,
                })
                continue

            if layout is None:
                records.append({
                    "rom": rom,
                    "title": rom,
                    "label": "",
                    "initials": "",
                    "score": "",
                    "scoreText": "",
                    "status": "unsupported",
                    "error": "",
                    "_order": 0,
                })
                continue

            table_records = []
            try:
                for position, entry in enumerate(layout["records"][:5]):
                    score = _read_score(data, layout, entry)
                    if score == 0:
                        continue
                    table_records.append({
                        "rom": rom,
                        "title": layout["title"],
                        "label": entry["label"],
                        "initials": _read_initials(data, entry),
                        "score": score,
                        "scoreText": f"{score:,}".replace(",", " "),
                        "status": "score",
                        "error": "",
                        "_order": position,
                    })
            except (KeyError, TypeError, ValueError) as exc:
                records.append({
                    "rom": rom,
                    "title": layout["title"],
                    "label": "",
                    "initials": "",
                    "score": "",
                    "scoreText": "",
                    "status": "invalid",
                    "error": str(exc),
                    "_order": 0,
                })
                continue

            if table_records:
                records.extend(table_records)
            else:
                records.append({
                    "rom": rom,
                    "title": layout["title"],
                    "label": "",
                    "initials": "",
                    "score": "",
                    "scoreText": "",
                    "status": "empty",
                    "error": "",
                    "_order": 0,
                })

    records.sort(
        key=lambda record: (
            str(record["title"]).casefold(),
            str(record["rom"]).casefold(),
            int(record["_order"]),
        )
    )
    for record in records:
        record.pop("_order")
    return records
