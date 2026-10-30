"""Ścieżki aplikacji i ustawienia użytkownika (Linux i Windows)."""
from __future__ import annotations

import json
import os
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "vpx-launcher"
IS_WINDOWS = sys.platform.startswith("win")

# Zmienne z dotychczasowego skryptu (NVIDIA PRIME offload + X11).
LINUX_DEFAULT_ENV = {
    "__NV_PRIME_RENDER_OFFLOAD": "1",
    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
    "SDL_VIDEODRIVER": "x11",
}


def config_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_NAME


def data_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME


def artwork_dir() -> Path:
    return data_dir() / "artwork"


def default_log_path() -> Path:
    """Domyślny vpinball.log (VPX 10.8.1+ trzyma dane w podfolderze wersji, tu 10.8)."""
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "VPinballX"
    else:
        base = Path.home() / ".local" / "share" / "VPinballX"
    return base / "10.8" / "vpinball.log"


def env_to_text(env: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in env.items())


def text_to_env(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            env[key] = value.strip()
    return env


def split_args(text: str) -> list[str]:
    if not text.strip():
        return []
    try:
        return shlex.split(text, posix=not IS_WINDOWS)
    except ValueError:
        return text.split()


@dataclass
class Settings:
    vpx_executable: str = ""
    table_dirs: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    extra_args: str = ""
    auto_artwork: bool = True
    vps_db_url: str = ""
    tile_size: int = 1  # indeks: 0 małe, 1 średnie, 2 duże, 3 bardzo duże, 4 ogromne
    log_path: str = ""
    monitor: str = "keep"  # "keep" | "auto" | "name:<nazwa ekranu>"

    @staticmethod
    def path() -> Path:
        return config_dir() / "settings.json"

    @classmethod
    def defaults(cls) -> "Settings":
        s = cls()
        s.log_path = str(default_log_path())
        if not IS_WINDOWS:
            s.env = dict(LINUX_DEFAULT_ENV)
            # Spróbuj znaleźć VPinballX tam, gdzie trzymał go stary skrypt.
            found = sorted(Path.home().glob("Gry/VPinballX_BGFX*/VPinballX_BGFX"))
            if found:
                exe = found[-1]
                s.vpx_executable = str(exe)
                tables = exe.parent / "tables"
                if tables.is_dir():
                    s.table_dirs = [str(tables)]
        return s

    @classmethod
    def load(cls) -> "Settings":
        path = cls.path()
        if not path.is_file():
            s = cls.defaults()
            s.save()
            return s
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return cls.defaults()
        s = cls()
        s.vpx_executable = str(data.get("vpx_executable", ""))
        dirs = data.get("table_dirs", [])
        s.table_dirs = [str(d) for d in dirs] if isinstance(dirs, list) else []
        env = data.get("env", {})
        s.env = {str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else {}
        s.extra_args = str(data.get("extra_args", ""))
        s.auto_artwork = bool(data.get("auto_artwork", True))
        s.vps_db_url = str(data.get("vps_db_url", ""))
        try:
            s.tile_size = max(0, min(4, int(data.get("tile_size", 1))))
        except (TypeError, ValueError):
            s.tile_size = 1
        s.log_path = str(data.get("log_path") or default_log_path())
        monitor = str(data.get("monitor") or "keep")
        s.monitor = monitor if monitor in ("keep", "auto") or monitor.startswith("name:") else "keep"
        return s

    def save(self) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "vpx_executable": self.vpx_executable,
            "table_dirs": self.table_dirs,
            "env": self.env,
            "extra_args": self.extra_args,
            "auto_artwork": self.auto_artwork,
            "vps_db_url": self.vps_db_url,
            "tile_size": self.tile_size,
            "log_path": self.log_path,
            "monitor": self.monitor,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")
