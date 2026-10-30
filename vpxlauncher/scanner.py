"""Skanowanie folderów w poszukiwaniu stołów .vpx i odczyt metadanych."""
from __future__ import annotations

import os
from pathlib import Path

VPX_EXT = ".vpx"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def norm(path: str | os.PathLike) -> str:
    return os.path.normpath(os.path.abspath(str(path)))


def _decode(data: bytes) -> str:
    if not data:
        return ""
    # Strumienie TableInfo w .vpx to zwykle UTF-16LE; na wszelki wypadek obsłuż też UTF-8.
    text = data.decode("utf-16-le", "ignore") if b"\x00" in data else data.decode("utf-8", "ignore")
    return text.replace("\x00", "").strip()[:120]


def read_info(path: Path) -> dict[str, str]:
    """Autor i wersja stołu z kontenera OLE (wymaga olefile; bez niego zwraca {})."""
    try:
        import olefile
    except ImportError:
        return {}
    info: dict[str, str] = {}
    try:
        if not olefile.isOleFile(str(path)):
            return {}
        with olefile.OleFileIO(str(path)) as ole:
            for key, stream in (("author", "TableInfo/AuthorName"), ("version", "TableInfo/TableVersion")):
                try:
                    info[key] = _decode(ole.openstream(stream).read())
                except Exception:
                    info[key] = ""
    except Exception:
        return {}
    return info


def find_sidecar_image(path: Path) -> str:
    """Obraz leżący obok stołu pod tą samą nazwą (np. Stol.vpx + Stol.png)."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        for candidate in (path.with_suffix(ext), path.with_suffix(ext.upper())):
            if candidate.is_file():
                return norm(candidate)
    return ""


def build_item(path: str | os.PathLike) -> dict[str, str]:
    p = Path(path)
    info = read_info(p)
    return {
        "path": norm(p),
        "name": p.stem,
        "author": info.get("author", ""),
        "version": info.get("version", ""),
        "artwork": find_sidecar_image(p),
    }


def scan_directories(dirs: list[str]) -> list[dict[str, str]]:
    seen: set[str] = set()
    items: list[dict[str, str]] = []
    for root_dir in dirs:
        if not os.path.isdir(root_dir):
            continue
        for current, _subdirs, files in os.walk(root_dir, followlinks=True):
            for filename in files:
                if filename.startswith("._") or not filename.lower().endswith(VPX_EXT):
                    continue
                full = norm(os.path.join(current, filename))
                if full in seen:
                    continue
                seen.add(full)
                items.append(build_item(full))
    items.sort(key=lambda i: i["name"].casefold())
    return items
