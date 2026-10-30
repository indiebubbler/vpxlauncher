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

from . import config, displays, vps
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
            self._set_status("Dodaj folder ze stołami w ustawieniach.")
            self.settingsRequested.emit()
            return
        self._start_scan(list(self._settings.table_dirs))

    def _start_scan(self, dirs: list[str]) -> None:
        if self._scanning:
            self._set_status("Skanowanie już trwa.")
            return
        self._set_scanning(True)
        self._set_status("Skanowanie folderów…")
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
            self._set_status(f"Błąd skanowania: {self._scan_error}")
        else:
            self._set_status(f"Skanowanie zakończone: {len(items)} stołów, nowych: {added}.")
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
            self._set_status(f"Dodano stołów: {added}.")
        else:
            self._set_status("Nie dodano nic nowego (obsługiwane są pliki .vpx i foldery).")

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
                f"Usunięto z biblioteki: {row['name']}. Plik na dysku został nietknięty, a skanowanie nie doda go ponownie."
            )

    @Slot()
    def restoreRemoved(self) -> None:
        count = self._lib.restore_removed()
        self._lib.refresh_missing()
        self._reload()
        self._set_status(f"Przywrócono usunięte stoły: {count}." if count else "Nie ma usuniętych stołów do przywrócenia.")

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
        self._set_status(f"Ustawiono grafikę dla: {row['name']}.")
        return True

    @Slot(int, QUrl)
    def setArtwork(self, table_id: int, url) -> None:
        if not self._apply_artwork(table_id, to_path(url)):
            self._set_status("Wybierz obraz PNG, JPG lub WebP.")

    @Slot(int, list)
    def setArtworkFromDrop(self, table_id: int, urls: list) -> None:
        paths = [to_path(u) for u in urls]
        for p in paths:
            if Path(p).suffix.lower() in IMAGE_EXTS:
                if not self._apply_artwork(table_id, p):
                    self._set_status("Nie udało się wczytać tego obrazu.")
                return
        self._import_paths(paths)  # upuszczono .vpx lub folder zamiast obrazu

    @Slot(int)
    def clearArtwork(self, table_id: int) -> None:
        row = self._lib.get(table_id)
        if row:
            self._drop_managed_artwork(row["artwork"])
            self._lib.set_artwork(table_id, "")
            self._model.update_row(self._lib.get(table_id))
            self._set_status(f"Usunięto grafikę: {row['name']}.")

    # ---- pobieranie grafik z internetu (baza VPS) ------------------------------
    def _start_art(self, rows: list[dict], force: bool = False) -> None:
        if self._fetching_art:
            self._set_status("Pobieranie grafik już trwa.")
            return
        if not rows:
            return
        self._art_force = {r["id"] for r in rows} if force else set()
        self._art_total = len(rows)
        self._art_seen = 0
        self._art_found = 0
        self._set_fetching_art(True)
        self._set_status(f"Pobieranie grafik: 0/{len(rows)}…")
        jobs = [{"id": r["id"], "name": r["name"]} for r in rows]
        threading.Thread(target=self._art_worker, args=(jobs,), daemon=True).start()

    def _art_worker(self, jobs: list[dict]) -> None:
        extra = [self._settings.vps_db_url] if self._settings.vps_db_url else []
        try:
            index = vps.VpsIndex.load(config.data_dir() / "vps-index.json", extra)
        except Exception as exc:
            self._artDone.emit(f"Nie udało się pobrać bazy VPS: {exc}")
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
        self._set_status(f"Pobieranie grafik: {self._art_seen}/{self._art_total}…")

    @Slot(str)
    def _on_art_done(self, error: str) -> None:
        self._set_fetching_art(False)
        if error:
            self._set_status(error)
        else:
            self._set_status(
                f"Grafiki: znaleziono {self._art_found} z {self._art_total}. "
                "Brakujące dodasz ręcznie, upuszczając obraz na kafelek."
            )

    @Slot()
    def fetchArtwork(self) -> None:
        rows = self._lib.missing_artwork(only_untried=False)
        if not rows:
            self._set_status("Wszystkie stoły mają już grafiki.")
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
            return (f"Nie znaleziono pliku logu:\n{path}\n\n"
                    "Uruchom dowolny stół albo wskaż właściwy plik w Ustawieniach.")
        except OSError as exc:
            return f"Nie można odczytać logu ({path}): {exc}"
        text = data.decode("utf-8", "replace")
        if truncated:
            text = "[… pominięto początek pliku …]\n" + text.split("\n", 1)[-1]
        return text

    # ---- ustawienia ----------------------------------------------------------
    @Slot(str, str, str, str, bool, str)
    def saveSettings(self, executable: str, dirs: str, env: str, args: str, auto_art: bool, log_path: str) -> None:
        old_dirs = list(self._settings.table_dirs)
        self._settings.vpx_executable = executable.strip()
        self._settings.table_dirs = [norm(d.strip()) for d in dirs.splitlines() if d.strip()]
        self._settings.env = config.text_to_env(env)
        self._settings.extra_args = args.strip()
        self._settings.auto_artwork = auto_art
        self._settings.log_path = log_path.strip() or str(config.default_log_path())
        self._settings.save()
        self.settingsChanged.emit()
        if self._settings.table_dirs and self._settings.table_dirs != old_dirs:
            self.scan()
        else:
            self._set_status("Zapisano ustawienia.")

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
        choices = ["Bez zmian (ustawienie z VPinballX.ini)", "Automatycznie: zewnętrzny, jeśli podłączony"]
        choices += [f"Ekran {i}: {s.label()}" for i, s in enumerate(screens)]
        mode = self._settings.monitor
        if mode.startswith("name:") and mode[5:] not in {s.name for s in screens}:
            choices.append(f"{mode[5:]} (odłączony, użyję trybu automatycznego)")
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
            return "bez zmian"
        if mode == "auto":
            return "automatycznie"
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
        self._set_status(f"Ekran gry: {self.monitorLabel}.")

    def _apply_monitor(self) -> str:
        """Ustawia ekran w VPinballX.ini przed startem. Zwraca dopisek do komunikatu."""
        screens = self._screen_infos()
        index, note = displays.resolve(self._settings.monitor, screens)
        if index is None:
            return ""
        ini = displays.ini_path_for(self._settings.log_path or str(config.default_log_path()))
        ok, error = displays.apply_display(ini, index)
        if not ok:
            return f" (ekran bez zmian: {error})"
        return f" na ekranie {index}: {screens[index].name}" + (f", {note}" if note else "")

    # ---- uruchamianie --------------------------------------------------------
    @Slot(int)
    def launch(self, table_id: int) -> None:
        if self._proc is not None:
            self._set_status("VPinball już działa.")
            return
        row = self._lib.get(table_id)
        if row is None:
            return
        exe = self._settings.vpx_executable
        if not exe or not Path(exe).is_file():
            self._set_status("Wskaż plik wykonywalny VPinballX w ustawieniach.")
            self.settingsRequested.emit()
            return
        if not Path(row["path"]).is_file():
            self._lib.refresh_missing()
            self._reload()
            self._set_status(f"Nie znaleziono pliku stołu: {row['path']}")
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
        self._set_status(f"Uruchamianie: {row['name']}{self._monitor_note}…")
        proc.start(exe, config.split_args(self._settings.extra_args) + ["-play", row["path"]])

    def _on_started(self, table_id: int, name: str) -> None:
        self._lib.record_play(table_id)
        self._model.update_row(self._lib.get(table_id))
        self._set_status(f"Gra trwa: {name}{self._monitor_note}")

    def _cleanup_proc(self) -> None:
        if self._proc is not None:
            self._proc.deleteLater()
            self._proc = None
        self._set_running(False)

    def _on_finished(self, code: int, status) -> None:
        if status == QProcess.ExitStatus.CrashExit:
            self._set_status("VPinball zamknął się nieoczekiwanie. Zobacz „Pokaż log gry” na dole okna.")
        elif code != 0:
            self._set_status(f"VPinball zakończył działanie z kodem {code}. Zobacz „Pokaż log gry” na dole okna.")
        else:
            self._set_status("Gra zakończona. Wybierz kolejny stół.")
        self._cleanup_proc()
        if self._sort in ("recent", "most"):
            self._reload()

    def _on_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._set_status("Nie udało się uruchomić VPinballX. Sprawdź ścieżkę i uprawnienia w ustawieniach.")
            self._cleanup_proc()
