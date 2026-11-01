"""Best-effort readers for known PinMAME NVRAM score layouts."""
from __future__ import annotations

import os
from pathlib import Path


_WILLIAMS_SCORES = {
    "barra_l1": (104, 109),
    "bk_l4": (104, 109),
    "frpwr_b7": (72, 78),
    "scrpn_l1": (72, 77),
}
_BALLY_SCORES = {"elektra", "fathom"}
_STERN_SCORES = {"seawitch", "viper"}
_KNOWN_ROMS = _BALLY_SCORES | _STERN_SCORES | set(_WILLIAMS_SCORES)


def _raise_walk_error(error: OSError) -> None:
    raise error


def _read_bally(data: bytes) -> int | None:
    if len(data) <= 172:
        raise ValueError("file is shorter than the Bally score area")
    digits: list[str] = []
    for byte in reversed(data[166:173]):
        if byte == 0xFF:
            digits.append("")
            continue
        digit, suffix = byte >> 4, byte & 0x0F
        if suffix != 0x0F or digit > 9:
            raise ValueError("invalid Bally score digit")
        digits.append(str(digit))
    text = "".join(digits).lstrip("0")
    return int(text) if text else None


def _read_stern(data: bytes) -> int | None:
    if len(data) <= 205:
        raise ValueError("file is shorter than the Stern score area")
    parts = data[202:206]
    if any((byte >> 4) > 9 or (byte & 0x0F) > 9 for byte in parts):
        raise ValueError("invalid Stern BCD score")
    values = [(byte >> 4) * 10 + (byte & 0x0F) for byte in parts]
    score = values[0] * 1_000_000 + values[1] * 10_000 + values[2] * 100 + values[3]
    return score or None


def _read_williams(data: bytes, start: int, end: int) -> int | None:
    if len(data) <= end:
        raise ValueError("file is shorter than the Williams score area")
    digits: list[str] = []
    for byte in data[start : end + 1]:
        if byte == 0xFF:
            digits.append("")
            continue
        digit, prefix = byte & 0x0F, byte >> 4
        if prefix != 0x0F or digit > 9:
            raise ValueError("invalid Williams score digit")
        digits.append(str(digit))
    text = "".join(digits).lstrip("0")
    return int(text) if text else None


def _parse_score(path: Path, data: bytes) -> int | None:
    rom = path.stem.casefold()
    if rom in _BALLY_SCORES:
        return _read_bally(data)
    if rom in _STERN_SCORES:
        return _read_stern(data)
    if rom in _WILLIAMS_SCORES:
        start, end = _WILLIAMS_SCORES[rom]
        return _read_williams(data, start, end)
    return None


def scan_nvram_directory(directory: str | os.PathLike) -> list[dict[str, str | int]]:
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"NVRAM folder does not exist: {root}")

    records: list[dict[str, str | int]] = []
    for current, _subdirs, filenames in os.walk(root, onerror=_raise_walk_error):
        for filename in filenames:
            if filename.startswith("._") or Path(filename).suffix.casefold() != ".nv":
                continue
            path = Path(current) / filename
            record: dict[str, str | int] = {
                "rom": path.stem,
                "score": "",
                "scoreText": "",
                "status": "unsupported",
                "error": "",
            }
            try:
                data = path.read_bytes()
            except OSError as exc:
                record["status"] = "read_error"
                record["error"] = str(exc)
            else:
                if path.stem.casefold() in _KNOWN_ROMS:
                    try:
                        score = _parse_score(path, data)
                    except ValueError as exc:
                        record["status"] = "invalid"
                        record["error"] = str(exc)
                        records.append(record)
                        continue
                    if score is None:
                        record["status"] = "empty"
                    else:
                        record["score"] = score
                        record["scoreText"] = f"{score:,}".replace(",", " ")
                        record["status"] = "score"
            records.append(record)

    records.sort(
        key=lambda record: (
            record["status"] != "score",
            -int(record["score"]) if record["status"] == "score" else 0,
            str(record["rom"]).casefold(),
        )
    )
    return records
