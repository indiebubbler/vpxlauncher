"""Logika aplikacji udostępniona do QML."""
from __future__ import annotations

import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import (
    Property,
    QObject,
    QProcess,
    QProcessEnvironment,
    QUrl,
    Signal,
    Slot,
)

from . import config, displays, i18n, vps
from .library import Library
from .models import TableModel
from .scanner import IMAGE_EXTS, VPX_EXT, build_item, norm, scan_directories

LOG_MAX_BYTES = 512 * 1024


def to_path(value) -> str:
    """QUrl / 'file:///…' / zwykła ścieżka -> ścieżka lokalna."""
    if isinstance(value, QUrl):
        return value.toLocalFile()
    text = str(value)
    if text.startswith("file:"):
        return QUrl(text).toLocalFile()
    return text


class Backend(QObject):
    statusChanged = Signal()
    runningChanged = Signal()
    scanningChanged = Signal()
    fetchingArtChanged = Signal()
    tileSizeChanged = Signal()
    monitorsChanged = Signal()
    settingsChanged = Signal()
    libraryChanged = Signal()
    settingsRequested = Signal()
    _scanDone = Signal(list)
    _artResult = Signal(int, str)
    _artDone = Signal(str)

    def __init__(self, library: Library, settings: config.Settings, model: TableModel, parent=None):
        super().__init__(parent)
        self._lib = library
        self._settings = settings
        self._model = model
        self._status = ""
        self._running = False
        self._scanning = False
        self._total = 0
        self._removed = 0
        self._query = ""
        self._favorites_only = False
        self._sort = "name"
        self._proc: QProcess | None = None
        self._scan_error = ""
        self._fetching_art = False
        self._monitor_note = ""
        self._art_total = 0
        self._art_seen = 0
        self._art_found = 0
        self._art_force: set[int] = set()
        self._scanDone.connect(self._on_scan_done)
        self._artResult.connect(self._on_art_result)
        self._artDone.connect(self._on_art_done)
        app = QGuiApplication.instance()
        if app is not None:  # podłączenie/odłączenie monitora odświeża listę wyboru
            app.screenAdded.connect(lambda *_: self.monitorsChanged.emit())
            app.screenRemoved.connect(lambda *_: self.monitorsChanged.emit())
        self._lib.refresh_missing()
        self._reload()
        if self._total == 0 and settings.table_dirs:
            self.scan()  # pierwsze uruchomienie: od razu zbuduj bibliotekę

    # ---- właściwości dla QML -------------------------------------------------
    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(bool, notify=runningChanged)
    def running(self):
        return self._running

    @Property(bool, notify=scanningChanged)
    def scanning(self):
        return self._scanning

    @Property(bool, notify=fetchingArtChanged)
    def fetchingArt(self):
        return self._fetching_art

    @Property(int, notify=libraryChanged)
    def removedCount(self):
        return self._removed

    @Property(int, notify=tileSizeChanged)
    def tileSize(self):
        return self._settings.tile_size

    @Property(str, notify=settingsChanged)
    def settingsLogPath(self):
        return self._settings.log_path

    @Property(bool, notify=settingsChanged)
    def settingsAutoArt(self):
        return self._settings.auto_artwork

    @Property(str, notify=settingsChanged)
    def language(self):
        return self._settings.language

    @Property(list, constant=True)
    def languageCodes(self):
        return list(i18n.LANGUAGES)

    @Property(list, constant=True)
    def languageNames(self):
        return list(i18n.LANGUAGES.values())

    @Property(int, notify=libraryChanged)
    def totalTables(self):
        return self._total

    @Property(str, notify=settingsChanged)
    def settingsExecutable(self):
        return self._settings.vpx_executable

    @Property(str, notify=settingsChanged)
    def settingsDirs(self):
        return "\n".join(self._settings.table_dirs)

    @Property(str, notify=settingsChanged)
    def settingsEnv(self):
        return config.env_to_text(self._settings.env)

    @Property(str, notify=settingsChanged)
    def settingsArgs(self):
        return self._settings.extra_args

    # ---- pomocnicze ----------------------------------------------------------
    def _set_status(self, text: str) -> None:
        if text != self._status:
            self._status = text
            self.statusChanged.emit()

    def _text(self, message: str, **values: object) -> str:
        return i18n.translate(self._settings.language, message, **values)

    @Slot(str, result=str)
    def translate(self, message: str) -> str:
        return self._text(message)

    def _set_running(self, value: bool) -> None:
        if value != self._running:
            self._running = value
            self.runningChanged.emit()

    def _set_scanning(self, value: bool) -> None:
        if value != self._scanning:
            self._scanning = value
            self.scanningChanged.emit()

    def _set_fetching_art(self, value: bool) -> None:
        if value != self._fetching_art:
            self._fetching_art = value
            self.fetchingArtChanged.emit()

    def _reload(self) -> None:
        self._model.set_rows(self._lib.list_tables(self._query, self._favorites_only, self._sort))
        self._total = self._lib.count()
        self._removed = self._lib.removed_count()
        self.libraryChanged.emit()

    @Slot(QUrl, result=str)
    def urlToPath(self, url) -> str:
        return to_path(url)

    # ---- filtrowanie ---------------------------------------------------------
    @Slot(str)
    def setQuery(self, text: str) -> None:
        self._query = text
        self._reload()

    @Slot(bool)
    def setFavoritesOnly(self, value: bool) -> None:
        self._favorites_only = value
        self._reload()

    @Slot(str)
    def setSort(self, key: str) -> None:
        self._sort = key
        self._reload()

    # ---- skanowanie i dodawanie ----------------------------------------------
    @Slot()
    def scan(self) -> None:
        if not self._settings.table_dirs:
            self._set_status(self._text("Add a folder with tables in Settings."))
            self.settingsRequested.emit()
            return
        self._start_scan(list(self._settings.table_dirs))

    def _start_scan(self, dirs: list[str]) -> None:
        if self._scanning:
            self._set_status(self._text("A scan is already in progress."))
            return
        self._set_scanning(True)
        self._set_status(self._text("Scanning folders..."))
        threading.Thread(target=self._scan_worker, args=(dirs,), daemon=True).start()

    def _scan_worker(self, dirs: list[str]) -> None:
        try:
            items = scan_directories(dirs)
            self._scan_error = ""
        except Exception as exc:  # nie zabijaj wątku po cichu
            items = []
            self._scan_error = str(exc)
        self._scanDone.emit(items)

    @Slot(list)
    def _on_scan_done(self, items: list) -> None:
        added = sum(1 for item in items if self._lib.upsert(item))
        self._lib.commit()
        self._lib.refresh_missing()
        self._set_scanning(False)
        self._reload()
        if self._scan_error:
            self._set_status(self._text("Scan failed: {error}", error=self._scan_error))
        else:
            self._set_status(self._text("Scan complete: {count} tables, {added} new.", count=len(items), added=added))
            if added and self._settings.auto_artwork:
                self._start_art(self._lib.missing_artwork(only_untried=True))

    def _import_paths(self, paths: list[str]) -> None:
        added, folders = 0, []
        for raw in paths:
            if not raw:
                continue
            p = Path(raw)
            if p.is_dir():
                folders.append(str(p))
            elif p.is_file() and p.suffix.lower() == VPX_EXT:
                added += int(self._lib.upsert(build_item(p), restore=True))
        self._lib.commit()
        self._reload()
        if folders:
            self._start_scan(folders)
        elif added:
            self._set_status(self._text("Added tables: {count}.", count=added))
        else:
            self._set_status(self._text("Nothing new was added (supported items are .vpx files and folders)."))

    @Slot(list)
    def addTables(self, urls: list) -> None:
        self._import_paths([to_path(u) for u in urls])

    @Slot(list)
    def handleDrop(self, urls: list) -> None:
        self._import_paths([to_path(u) for u in urls])

    # ---- akcje na stole ------------------------------------------------------
    @Slot(int)
    def toggleFavorite(self, table_id: int) -> None:
        self._lib.toggle_favorite(table_id)
        if self._favorites_only:
            self._reload()
        else:
            self._model.update_row(self._lib.get(table_id))

    @Slot(int)
    def removeTable(self, table_id: int) -> None:
        row = self._lib.get(table_id)
        if row:
            self._drop_managed_artwork(row["artwork"])
            self._lib.remove(table_id)
            self._reload()
            self._set_status(
                self._text(
                    "Removed from library: {name}. The file on disk was not changed and scanning will not add it again.",
                    name=row["name"],
                )
            )

    @Slot()
    def restoreRemoved(self) -> None:
        count = self._lib.restore_removed()
        self._lib.refresh_missing()
        self._reload()
        self._set_status(
            self._text("Restored removed tables: {count}.", count=count)
            if count else self._text("There are no removed tables to restore.")
        )

    @Slot(int)
    def setTileSize(self, index: int) -> None:
        index = max(0, min(4, int(index)))
        if index != self._settings.tile_size:
            self._settings.tile_size = index
            self._settings.save()
            self.tileSizeChanged.emit()

    # ---- grafiki -------------------------------------------------------------
    @staticmethod
    def _is_managed(path: str) -> bool:
        if not path:
            return False
        try:
            return Path(path).resolve().parent == config.artwork_dir().resolve()
        except OSError:
            return False

    def _drop_managed_artwork(self, path: str) -> None:
        if self._is_managed(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def _apply_artwork(self, table_id: int, src: str) -> bool:
        row = self._lib.get(table_id)
        if row is None:
            return False
        ext = Path(src).suffix.lower()
        if ext not in IMAGE_EXTS or not os.path.isfile(src):
            return False
        dest_dir = config.artwork_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{table_id}-{int(time.time() * 1000)}{ext}"
        shutil.copy2(src, dest)
        self._drop_managed_artwork(row["artwork"])
        self._lib.set_artwork(table_id, str(dest))
        self._model.update_row(self._lib.get(table_id))
        self._set_status(self._text("Set artwork for: {name}.", name=row["name"]))
        return True

    @Slot(int, QUrl)
    def setArtwork(self, table_id: int, url) -> None:
        if not self._apply_artwork(table_id, to_path(url)):
            self._set_status(self._text("Choose a PNG, JPG, or WebP image."))

    @Slot(int, list)
    def setArtworkFromDrop(self, table_id: int, urls: list) -> None:
        paths = [to_path(u) for u in urls]
        for p in paths:
            if Path(p).suffix.lower() in IMAGE_EXTS:
                if not self._apply_artwork(table_id, p):
                    self._set_status(self._text("Could not load this image."))
                return
        self._import_paths(paths)  # upuszczono .vpx lub folder zamiast obrazu

    @Slot(int)
    def clearArtwork(self, table_id: int) -> None:
        row = self._lib.get(table_id)
        if row:
            self._drop_managed_artwork(row["artwork"])
            self._lib.set_artwork(table_id, "")
            self._model.update_row(self._lib.get(table_id))
            self._set_status(self._text("Removed artwork: {name}.", name=row["name"]))

    # ---- pobieranie grafik z internetu (baza VPS) ------------------------------
    def _start_art(self, rows: list[dict], force: bool = False) -> None:
        if self._fetching_art:
            self._set_status(self._text("Artwork download is already in progress."))
            return
        if not rows:
            return
        self._art_force = {r["id"] for r in rows} if force else set()
        self._art_total = len(rows)
        self._art_seen = 0
        self._art_found = 0
        self._set_fetching_art(True)
        self._set_status(self._text("Downloading artwork: {done}/{total}...", done=0, total=len(rows)))
        jobs = [{"id": r["id"], "name": r["name"]} for r in rows]
        threading.Thread(target=self._art_worker, args=(jobs,), daemon=True).start()

    def _art_worker(self, jobs: list[dict]) -> None:
        extra = [self._settings.vps_db_url] if self._settings.vps_db_url else []
        try:
            index = vps.VpsIndex.load(config.data_dir() / "vps-index.json", extra)
        except Exception as exc:
            self._artDone.emit(str(exc) or type(exc).__name__)
            return
        art_dir = config.artwork_dir()
        art_dir.mkdir(parents=True, exist_ok=True)
        for job in jobs:
            path = ""
            try:
                game = index.find(job["name"])
                url = index.image_url(game, job["name"]) if game else ""
                if url:
                    data = vps.http_get(url, timeout=30)
                    ext = vps.sniff_image_ext(data)
                    if ext:
                        dest = art_dir / f"{job['id']}-{int(time.time() * 1000)}{ext}"
                        dest.write_bytes(data)
                        path = str(dest)
            except Exception:
                path = ""  # jedna nieudana grafika nie zatrzymuje reszty
            self._artResult.emit(job["id"], path)
        self._artDone.emit("")

    @Slot(int, str)
    def _on_art_result(self, table_id: int, path: str) -> None:
        self._art_seen += 1
        self._lib.mark_art_tried(table_id)
        if path:
            row = self._lib.get(table_id)
            # Nie nadpisuj grafiki dodanej ręcznie w trakcie pobierania (chyba że to jawne "znajdź ponownie").
            if row is not None and (row["artwork"] == "" or table_id in self._art_force):
                self._drop_managed_artwork(row["artwork"])
                self._lib.set_artwork(table_id, path)
                self._art_found += 1
                self._model.update_row(self._lib.get(table_id))
            else:
                try:
                    os.remove(path)
                except OSError:
                    pass
        self._set_status(self._text(
            "Downloading artwork: {done}/{total}...",
            done=self._art_seen,
            total=self._art_total,
        ))

    @Slot(str)
    def _on_art_done(self, error: str) -> None:
        self._set_fetching_art(False)
        if error:
            self._set_status(self._text("Could not download the VPS database: {error}", error=error))
        else:
            self._set_status(
                self._text(
                    "Artwork: found {found} of {total}. Add missing artwork by dropping an image onto a tile.",
                    found=self._art_found,
                    total=self._art_total,
                )
            )

    @Slot()
    def fetchArtwork(self) -> None:
        rows = self._lib.missing_artwork(only_untried=False)
        if not rows:
            self._set_status(self._text("All tables already have artwork."))
            return
        self._start_art(rows)

    @Slot(int)
    def fetchArtworkFor(self, table_id: int) -> None:
        row = self._lib.get(table_id)
        if row:
            self._start_art([row], force=True)

    # ---- log gry -------------------------------------------------------------
    def _log_file(self) -> Path:
        return Path(self._settings.log_path or str(config.default_log_path()))

    @Slot(result=str)
    def logInfo(self) -> str:
        path = self._log_file()
        try:
            st = path.stat()
        except OSError:
            return str(path)
        return f"{path}  ({datetime.fromtimestamp(st.st_mtime):%d.%m.%Y %H:%M:%S}, {st.st_size // 1024} KB)"

    @Slot(result=str)
    def readLog(self) -> str:
        """Zwraca końcówkę vpinball.log (ostatnie 512 KB)."""
        path = self._log_file()
        try:
            size = path.stat().st_size
            with open(path, "rb") as handle:
                truncated = size > LOG_MAX_BYTES
                if truncated:
                    handle.seek(size - LOG_MAX_BYTES)
                data = handle.read()
        except FileNotFoundError:
            return self._text(
                "Could not find the log file:\n{path}\n\nLaunch any table or choose the correct file in Settings.",
                path=path,
            )
        except OSError as exc:
            return self._text("Could not read log file ({path}): {error}", path=path, error=exc)
        text = data.decode("utf-8", "replace")
        if truncated:
            text = self._text("[... beginning of file omitted ...]\n") + text.split("\n", 1)[-1]
        return text

    # ---- ustawienia ----------------------------------------------------------
    @Slot(str, str, str, str, bool, str, str)
    def saveSettings(
        self,
        executable: str,
        dirs: str,
        env: str,
        args: str,
        auto_art: bool,
        log_path: str,
        language: str,
    ) -> None:
        old_dirs = list(self._settings.table_dirs)
        old_language = self._settings.language
        self._settings.vpx_executable = executable.strip()
        self._settings.table_dirs = [norm(d.strip()) for d in dirs.splitlines() if d.strip()]
        self._settings.env = config.text_to_env(env)
        self._settings.extra_args = args.strip()
        self._settings.auto_artwork = auto_art
        self._settings.log_path = log_path.strip() or str(config.default_log_path())
        self._settings.language = language if language in i18n.LANGUAGES else "en"
        self._settings.save()
        self.settingsChanged.emit()
        if self._settings.language != old_language:
            self.monitorsChanged.emit()
        if self._settings.table_dirs and self._settings.table_dirs != old_dirs:
            self.scan()
        else:
            self._set_status(self._text("Settings saved."))

    # ---- wybór monitora ------------------------------------------------------
    @staticmethod
    def _screen_infos() -> list[displays.ScreenInfo]:
        primary = QGuiApplication.primaryScreen()
        infos = []
        for screen in QGuiApplication.screens():
            dpr = screen.devicePixelRatio() or 1.0
            size = screen.size()
            infos.append(displays.ScreenInfo(screen.name(), round(size.width() * dpr), round(size.height() * dpr), screen == primary))
        infos.sort(key=lambda info: not info.primary)  # główny ekran jako 0 (stabilnie)
        return infos

    @Property(list, notify=monitorsChanged)
    def monitorChoices(self):
        screens = self._screen_infos()
        choices = [
            self._text("Unchanged (use VPinballX.ini setting)"),
            self._text("Automatic: external display if connected"),
        ]
        choices += [
            self._text("Display {index}: {label}", index=i, label=s.label(self._settings.language))
            for i, s in enumerate(screens)
        ]
        mode = self._settings.monitor
        if mode.startswith("name:") and mode[5:] not in {s.name for s in screens}:
            choices.append(self._text("{name} (disconnected; using automatic mode)", name=mode[5:]))
        return choices

    @Property(int, notify=monitorsChanged)
    def monitorIndex(self):
        mode = self._settings.monitor
        if mode == "keep":
            return 0
        if mode == "auto":
            return 1
        names = [s.name for s in self._screen_infos()]
        wanted = mode[5:]
        return 2 + (names.index(wanted) if wanted in names else len(names))

    @Property(str, notify=monitorsChanged)
    def monitorLabel(self):
        mode = self._settings.monitor
        if mode == "keep":
            return self._text("unchanged")
        if mode == "auto":
            return self._text("automatic")
        return mode[5:]

    @Slot(int)
    def setMonitorChoice(self, index: int) -> None:
        screens = self._screen_infos()
        if index <= 0:
            mode = "keep"
        elif index == 1:
            mode = "auto"
        elif index - 2 < len(screens):
            mode = f"name:{screens[index - 2].name}"
        else:
            return  # wpis o odłączonym ekranie: zostaw dotychczasowy wybór
        self._settings.monitor = mode
        self._settings.save()
        self.monitorsChanged.emit()
        self._set_status(self._text("Game display: {label}.", label=self.monitorLabel))

    def _apply_monitor(self) -> str:
        """Ustawia ekran w VPinballX.ini przed startem. Zwraca dopisek do komunikatu."""
        screens = self._screen_infos()
        index, note = displays.resolve(self._settings.monitor, screens, self._settings.language)
        if index is None:
            return ""
        ini = displays.ini_path_for(self._settings.log_path or str(config.default_log_path()))
        ok, error = displays.apply_display(ini, index, self._settings.language)
        if not ok:
            return f" ({self._text('Display unchanged: {error}', error=error)})"
        return " " + self._text("on display {index}: {name}", index=index, name=screens[index].name) + (
            f", {note}" if note else ""
        )

    # ---- uruchamianie --------------------------------------------------------
    @Slot(int)
    def launch(self, table_id: int) -> None:
        if self._proc is not None:
            self._set_status(self._text("VPinball is already running."))
            return
        row = self._lib.get(table_id)
        if row is None:
            return
        exe = self._settings.vpx_executable
        if not exe or not Path(exe).is_file():
            self._set_status(self._text("Choose the VPinballX executable in Settings."))
            self.settingsRequested.emit()
            return
        if not Path(row["path"]).is_file():
            self._lib.refresh_missing()
            self._reload()
            self._set_status(self._text("Table file not found: {path}", path=row["path"]))
            return

        proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        for key, value in self._settings.env.items():
            env.insert(key, value)
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(Path(exe).parent))
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        proc.started.connect(lambda: self._on_started(table_id, row["name"]))
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        self._monitor_note = self._apply_monitor()
        self._proc = proc
        self._set_running(True)
        self._set_status(self._text("Launching: {name}{note}...", name=row["name"], note=self._monitor_note))
        proc.start(exe, config.split_args(self._settings.extra_args) + ["-play", row["path"]])

    def _on_started(self, table_id: int, name: str) -> None:
        self._lib.record_play(table_id)
        self._model.update_row(self._lib.get(table_id))
        self._set_status(self._text("Playing: {name}{note}", name=name, note=self._monitor_note))

    def _cleanup_proc(self) -> None:
        if self._proc is not None:
            self._proc.deleteLater()
            self._proc = None
        self._set_running(False)

    def _on_finished(self, code: int, status) -> None:
        if status == QProcess.ExitStatus.CrashExit:
            self._set_status(self._text(
                "VPinball closed unexpectedly. Check Show game log at the bottom of the window."
            ))
        elif code != 0:
            self._set_status(self._text(
                "VPinball exited with code {code}. Check Show game log at the bottom of the window.",
                code=code,
            ))
        else:
            self._set_status(self._text("Game finished. Choose another table."))
        self._cleanup_proc()
        if self._sort in ("recent", "most"):
            self._reload()

    def _on_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._set_status(self._text(
                "Could not start VPinballX. Check the path and permissions in Settings."
            ))
            self._cleanup_proc()
