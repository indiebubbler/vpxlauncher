"""Wybór ekranu, na którym startuje VPinball.

VPinball (standalone 10.8) czyta numer ekranu z klucza ``Display`` w sekcji ``[Player]``
pliku VPinballX.ini. Launcher ustawia go tuż przed startem gry, edytując tylko tę jedną linię
(reszta pliku, komentarze i kolejność zostają). Przy pierwszej zmianie powstaje kopia
``VPinballX.ini.launcher-backup``.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

BUILTIN_PREFIXES = ("EDP", "LVDS", "DSI")  # nazwy wbudowanych paneli laptopów (Linux)
BACKUP_SUFFIX = ".launcher-backup"


@dataclass(frozen=True)
class ScreenInfo:
    name: str
    width: int
    height: int
    primary: bool = False

    def label(self) -> str:
        return f"{self.name} ({self.width}×{self.height}{', główny' if self.primary else ''})"


# ---- wybór ekranu ------------------------------------------------------------
def is_builtin(name: str) -> bool:
    return name.upper().startswith(BUILTIN_PREFIXES)


def pick_auto(screens: list[ScreenInfo]) -> int:
    """Zewnętrzny ekran, jeśli podłączony; w przeciwnym razie ekran 0."""
    if len(screens) < 2:
        return 0
    builtin = [i for i, s in enumerate(screens) if is_builtin(s.name)]
    if builtin:
        external = [i for i in range(len(screens)) if i not in builtin]
        return external[0] if external else 0
    # Brak rozpoznawalnego panelu wbudowanego (np. Windows, dwa monitory na pulpicie):
    # weź pierwszy ekran niegłówny.
    non_primary = [i for i, s in enumerate(screens) if not s.primary]
    return non_primary[0] if non_primary else 0


def resolve(mode: str, screens: list[ScreenInfo]) -> tuple[int | None, str]:
    """mode: 'keep' | 'auto' | 'name:<nazwa ekranu>'. Zwraca (indeks lub None, notatka)."""
    if mode == "keep" or not screens:
        return None, ""
    if mode == "auto":
        return pick_auto(screens), "tryb automatyczny"
    if mode.startswith("name:"):
        wanted = mode[5:]
        for i, s in enumerate(screens):
            if s.name == wanted:
                return i, ""
        return pick_auto(screens), f"ekranu {wanted} nie ma, użyto trybu automatycznego"
    return None, ""


# ---- edycja VPinballX.ini ----------------------------------------------------
_SECTION_RE = re.compile(r"^\s*\[([^\]]*)\]\s*$")


def _locate(lines: list[str], section: str, key: str):
    """(początek sekcji, koniec sekcji, linia klucza); None, gdy nie znaleziono."""
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=", re.IGNORECASE)
    in_section, start, end, key_line = False, None, None, None
    for i, line in enumerate(lines):
        m = _SECTION_RE.match(line)
        if m:
            if in_section and end is None:
                end = i
            in_section = m.group(1).strip().lower() == section.lower()
            if in_section and start is None:
                start = i
            continue
        if in_section and key_line is None and key_re.match(line):
            key_line = i
    if in_section and end is None:
        end = len(lines)
    return start, end, key_line


def get_ini_value(text: str, section: str, key: str) -> str | None:
    lines = text.splitlines()
    _s, _e, key_line = _locate(lines, section, key)
    if key_line is None:
        return None
    return lines[key_line].split("=", 1)[1].strip()


def set_ini_value(text: str, section: str, key: str, value: str) -> str:
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    start, end, key_line = _locate(lines, section, key)
    if key_line is not None:
        # zachowaj styl zapisu (spacje wokół "=", wielkość liter klucza); komentarz po wartości jest pomijany
        lines[key_line] = re.sub(r"^(\s*[^=]*=\s*).*$", lambda m: m.group(1) + value, lines[key_line])
    elif start is not None:
        pos = end
        while pos - 1 > start and not lines[pos - 1].strip():
            pos -= 1  # wstaw przed pustymi liniami kończącymi sekcję
        lines.insert(pos, f"{key} = {value}")
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"[{section}]", f"{key} = {value}"]
    return nl.join(lines) + nl


def ini_path_for(log_path: str) -> Path:
    """VPinballX.ini leży obok vpinball.log (VPX 10.8.1 trzyma je w ~/.local/share/VPinballX/10.8/)."""
    return Path(log_path).parent / "VPinballX.ini"


def apply_display(ini_path: str | os.PathLike, index: int) -> tuple[bool, str]:
    """Ustawia [Player] Display w VPinballX.ini. Zwraca (powodzenie, komunikat błędu)."""
    path = Path(ini_path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return False, f"nie znaleziono {path} (uruchom VPinball raz, aby powstał plik ustawień)"
    except OSError as exc:
        return False, f"nie można odczytać {path}: {exc}"

    bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw[3:] if bom else raw
    try:
        text, encoding = body.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        text, encoding = body.decode("latin-1"), "latin-1"  # starsze pliki w ANSI: odczyt i zapis bez zmian bajtów

    new_text = set_ini_value(text, "Player", "Display", str(index))
    # Na wypadek innej nazwy klucza w nowszych wersjach: jeśli plik zawiera PlayfieldDisplay, zsynchronizuj.
    if get_ini_value(new_text, "Player", "PlayfieldDisplay") is not None:
        new_text = set_ini_value(new_text, "Player", "PlayfieldDisplay", str(index))
    if new_text == text or new_text.rstrip("\r\n") == text.rstrip("\r\n"):
        return True, ""  # już ustawione, nie ruszaj pliku

    try:
        backup = path.with_name(path.name + BACKUP_SUFFIX)
        if not backup.exists():
            shutil.copy2(path, backup)
        tmp = path.with_name(path.name + ".launcher-tmp")
        tmp.write_bytes((b"\xef\xbb\xbf" if bom else b"") + new_text.encode(encoding))
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except OSError as exc:
        return False, f"nie można zapisać {path}: {exc}"
    return True, ""
