import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse
import uuid
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "VPinball Launcher"
TABLE_FILTER = "Stoły Visual Pinball (*.vpx)"
IMAGE_FILTER = "Grafiki (*.png *.jpg *.jpeg *.webp *.bmp)"


def data_directory():
    root = os.environ.get("APPDATA") if sys.platform == "win32" else os.environ.get("XDG_DATA_HOME")
    if root:
        base = Path(root)
    else:
        base = Path.home() / ("AppData/Roaming" if sys.platform == "win32" else ".local/share")
    directory = base / "VPinballLauncher"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "covers").mkdir(exist_ok=True)
    return directory


def load_library():
    try:
        return json.loads((data_directory() / "library.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_library(tables):
    path = data_directory() / "library.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class CoverDownload(QThread):
    download_complete = Signal(str)
    download_error = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            request = urllib.request.Request(self.url, headers={"User-Agent": "VPinballLauncher/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                content_type = response.headers.get_content_type()
                if not content_type.startswith("image/"):
                    raise ValueError("Podany adres nie zwraca pliku graficznego.")
                data = response.read(15 * 1024 * 1024 + 1)
            if len(data) > 15 * 1024 * 1024:
                raise ValueError("Grafika jest większa niż 15 MB.")
            suffix = Path(urlparse(self.url).path).suffix.lower()
            if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                suffix = ".jpg" if content_type == "image/jpeg" else ".png"
            destination = data_directory() / "covers" / f"{uuid.uuid4().hex}{suffix}"
            destination.write_bytes(data)
            self.download_complete.emit(str(destination))
        except (OSError, ValueError, urllib.error.URLError) as error:
            self.download_error.emit(str(error))


class CoverDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dodaj okładkę")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Wybierz grafikę z dysku albo podaj bezpośredni adres URL obrazu."))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/okladka.jpg")
        layout.addWidget(self.url_input)
        buttons = QHBoxLayout()
        self.local_button = QPushButton("Wybierz plik...")
        self.url_button = QPushButton("Pobierz z URL")
        cancel_button = QPushButton("Anuluj")
        buttons.addWidget(self.local_button)
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.url_button)
        layout.addLayout(buttons)
        self.cover_path = ""
        self.downloader = None
        self.url_button.clicked.connect(self.download_cover)
        self.local_button.clicked.connect(self.choose_cover)
        cancel_button.clicked.connect(self.reject)

    def choose_cover(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Wybierz okładkę", "", IMAGE_FILTER)
        if filename:
            self.cover_path = filename
            self.accept()

    def download_cover(self):
        url = self.url_input.text().strip()
        if not url.startswith(("https://", "http://")):
            QMessageBox.warning(self, "Nieprawidłowy adres", "Podaj pełny adres URL rozpoczynający się od http:// lub https://.")
            return
        self.url_button.setEnabled(False)
        self.url_button.setText("Pobieranie...")
        self.downloader = CoverDownload(url, self)
        self.downloader.download_complete.connect(self.downloaded)
        self.downloader.download_error.connect(self.download_failed)
        self.downloader.start()

    def downloaded(self, path):
        self.downloader.wait()
        self.cover_path = path
        self.accept()

    def download_failed(self, error):
        self.url_button.setEnabled(True)
        self.url_button.setText("Pobierz z URL")
        QMessageBox.warning(self, "Nie udało się pobrać grafiki", error)


class TableTile(QFrame):
    clicked = Signal(str)

    def __init__(self, table, parent=None):
        super().__init__(parent)
        self.table = table
        self.setObjectName("tableTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(264)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.art = QLabel()
        self.art.setObjectName("tileArt")
        self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art.setFixedHeight(210)
        self.art.setText("VPX")
        self.art.setProperty("class", "artPlaceholder")
        self.set_cover(table.get("cover", ""))
        layout.addWidget(self.art)
        name = QLabel(table.get("name") or Path(table["path"]).stem)
        name.setObjectName("tileName")
        name.setWordWrap(True)
        layout.addWidget(name)

    def set_cover(self, cover):
        pixmap = QPixmap(cover) if cover and Path(cover).is_file() else QPixmap()
        if pixmap.isNull():
            self.art.setPixmap(QPixmap())
            self.art.setText("VPX")
            return
        self.art.setText("")
        self.art.setPixmap(pixmap.scaled(QSize(260, 210), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.table["path"])
        super().mousePressEvent(event)


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia emulatora")
        self.setMinimumWidth(560)
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(QLabel("Plik wykonywalny Visual Pinball X"))
        exe_row = QHBoxLayout()
        self.exe_input = QLineEdit(settings.value("emulator_path", ""))
        self.exe_input.setPlaceholderText("VPinballX.exe lub VPinballX_BGFX")
        browse_exe = QPushButton("Przeglądaj...")
        exe_row.addWidget(self.exe_input)
        exe_row.addWidget(browse_exe)
        layout.addLayout(exe_row)
        layout.addWidget(QLabel("Katalog roboczy emulatora (opcjonalnie, domyślnie katalog programu)"))
        work_row = QHBoxLayout()
        self.work_input = QLineEdit(settings.value("working_directory", ""))
        browse_work = QPushButton("Wybierz...")
        work_row.addWidget(self.work_input)
        work_row.addWidget(browse_work)
        layout.addLayout(work_row)
        layout.addWidget(QLabel("Katalog skanowania stołów"))
        tables_row = QHBoxLayout()
        self.tables_input = QLineEdit(settings.value("tables_directory", ""))
        browse_tables = QPushButton("Wybierz...")
        tables_row.addWidget(self.tables_input)
        tables_row.addWidget(browse_tables)
        layout.addLayout(tables_row)
        layout.addWidget(QLabel("Dodatkowe argumenty emulatora (oprócz -play i ścieżki stołu)"))
        self.arguments_input = QLineEdit(settings.value("arguments", ""))
        self.arguments_input.setPlaceholderText("np. --fullscreen")
        layout.addWidget(self.arguments_input)
        self.linux_options = QLineEdit(settings.value("linux_environment", ""))
        self.linux_options.setPlaceholderText("Zmienne środowiskowe Linux, np. SDL_VIDEODRIVER=x11")
        if sys.platform == "win32":
            self.linux_options.hide()
        else:
            layout.addWidget(self.linux_options)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Anuluj")
        save = QPushButton("Zapisz")
        save.setObjectName("primaryButton")
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        browse_exe.clicked.connect(lambda: self.pick_file(self.exe_input))
        browse_work.clicked.connect(lambda: self.pick_directory(self.work_input))
        browse_tables.clicked.connect(lambda: self.pick_directory(self.tables_input))
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save_settings)

    def pick_file(self, field):
        filename, _ = QFileDialog.getOpenFileName(self, "Wybierz emulator", field.text())
        if filename:
            field.setText(filename)

    def pick_directory(self, field):
        directory = QFileDialog.getExistingDirectory(self, "Wybierz katalog", field.text())
        if directory:
            field.setText(directory)

    def save_settings(self):
        self.settings.setValue("emulator_path", self.exe_input.text().strip())
        self.settings.setValue("working_directory", self.work_input.text().strip())
        self.settings.setValue("tables_directory", self.tables_input.text().strip())
        self.settings.setValue("arguments", self.arguments_input.text().strip())
        self.settings.setValue("linux_environment", self.linux_options.text().strip())
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("VPinballLauncher", "VPinballLauncher")
        self.tables = load_library()
        self.selected_path = ""
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 790)
        self.setMinimumSize(760, 560)
        self.setStatusBar(QStatusBar())
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(30, 22, 30, 20)
        main_layout.setSpacing(20)
        header = QHBoxLayout()
        brand = QVBoxLayout()
        eyebrow = QLabel("VISUAL PINBALL X")
        eyebrow.setObjectName("eyebrow")
        brand.addWidget(eyebrow)
        title = QLabel("Twoja kolekcja")
        title.setObjectName("pageTitle")
        brand.addWidget(title)
        header.addLayout(brand)
        header.addStretch()
        self.settings_button = QPushButton("Ustawienia")
        self.settings_button.clicked.connect(self.open_settings)
        header.addWidget(self.settings_button)
        main_layout.addLayout(header)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("searchInput")
        self.search.setPlaceholderText("Szukaj stołu...")
        self.search.textChanged.connect(self.render_tables)
        toolbar.addWidget(self.search, 1)
        add_file = QPushButton("Dodaj stół")
        scan = QPushButton("Skanuj katalog")
        self.play_button = QPushButton("Uruchom stół")
        self.play_button.setObjectName("primaryButton")
        add_file.clicked.connect(self.add_table)
        scan.clicked.connect(self.scan_directory)
        self.play_button.clicked.connect(self.launch_table)
        toolbar.addWidget(add_file)
        toolbar.addWidget(scan)
        toolbar.addWidget(self.play_button)
        main_layout.addLayout(toolbar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 12, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.scroll.setWidget(self.grid_host)
        splitter.addWidget(self.scroll)
        self.details = QWidget()
        self.details.setObjectName("detailsPanel")
        self.details.setMinimumWidth(245)
        detail_layout = QVBoxLayout(self.details)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_layout.setSpacing(12)
        self.detail_art = QLabel("WYBIERZ STÓŁ")
        self.detail_art.setObjectName("detailArt")
        self.detail_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_art.setMinimumHeight(190)
        self.detail_art.setMaximumHeight(240)
        detail_layout.addWidget(self.detail_art)
        self.detail_name = QLabel("Twoja kolekcja")
        self.detail_name.setObjectName("detailTitle")
        self.detail_name.setWordWrap(True)
        detail_layout.addWidget(self.detail_name)
        self.detail_path = QLabel("Dodaj pliki .vpx albo zeskanuj katalog, aby rozpocząć.")
        self.detail_path.setObjectName("mutedText")
        self.detail_path.setWordWrap(True)
        detail_layout.addWidget(self.detail_path)
        self.cover_button = QPushButton("Zmień okładkę")
        self.remove_button = QPushButton("Usuń z kolekcji")
        self.cover_button.clicked.connect(self.change_cover)
        self.remove_button.clicked.connect(self.remove_table)
        detail_layout.addWidget(self.cover_button)
        detail_layout.addWidget(self.remove_button)
        detail_layout.addStretch()
        splitter.addWidget(self.details)
        splitter.setSizes([780, 300])
        main_layout.addWidget(splitter, 1)
        self.render_tables()

    def render_tables(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        query = self.search.text().strip().casefold()
        filtered = [table for table in self.tables if query in table.get("name", "").casefold()]
        width = max(1, self.scroll.viewport().width())
        columns = max(1, width // 205)
        for index, table in enumerate(filtered):
            tile = TableTile(table)
            tile.clicked.connect(self.select_table)
            self.grid.addWidget(tile, index // columns, index % columns)
        self.grid.setRowStretch((len(filtered) + columns - 1) // columns, 1)
        self.play_button.setEnabled(bool(self.selected_path and any(t["path"] == self.selected_path for t in self.tables)))
        if not filtered:
            empty = QLabel("Nie znaleziono stołów." if self.tables else "Twoja biblioteka jest pusta. Dodaj stół albo zeskanuj katalog z plikami .vpx.")
            empty.setObjectName("mutedText")
            empty.setWordWrap(True)
            self.grid.addWidget(empty, 0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render_tables()

    def select_table(self, path):
        self.selected_path = path
        table = next((entry for entry in self.tables if entry["path"] == path), None)
        if not table:
            return
        self.detail_name.setText(table.get("name", Path(path).stem))
        self.detail_path.setText(path)
        pixmap = QPixmap(table.get("cover", "")) if table.get("cover") else QPixmap()
        self.detail_art.setPixmap(pixmap.scaled(QSize(360, 240), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation) if not pixmap.isNull() else QPixmap())
        self.detail_art.setText("" if not pixmap.isNull() else "BRAK OKŁADKI")
        self.play_button.setEnabled(True)
        for index in range(self.grid.count()):
            widget = self.grid.itemAt(index).widget()
            if isinstance(widget, TableTile):
                widget.setProperty("selected", widget.table["path"] == path)
                widget.style().unpolish(widget)
                widget.style().polish(widget)

    def persist(self):
        save_library(self.tables)

    def add_table(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Dodaj stół Visual Pinball", self.settings.value("tables_directory", ""), TABLE_FILTER)
        if filename:
            self.add_paths([filename])

    def add_paths(self, paths):
        known = {str(Path(table["path"]).resolve()) for table in self.tables}
        added = 0
        for path in paths:
            resolved = str(Path(path).resolve())
            if Path(resolved).is_file() and Path(resolved).suffix.lower() == ".vpx" and resolved not in known:
                self.tables.append({"path": resolved, "name": Path(resolved).stem, "cover": ""})
                known.add(resolved)
                added += 1
        self.tables.sort(key=lambda table: table.get("name", "").casefold())
        self.persist()
        self.render_tables()
        self.statusBar().showMessage(f"Dodano stołów: {added}", 5000)

    def scan_directory(self):
        start = self.settings.value("tables_directory", "") or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Wybierz katalog do skanowania", start)
        if not directory:
            return
        self.settings.setValue("tables_directory", directory)
        paths = [str(path) for path in Path(directory).rglob("*") if path.is_file() and path.suffix.lower() == ".vpx"]
        self.add_paths(paths)

    def change_cover(self):
        table = next((entry for entry in self.tables if entry["path"] == self.selected_path), None)
        if not table:
            return
        dialog = CoverDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.cover_path:
            source = Path(dialog.cover_path)
            if source.parent != data_directory() / "covers":
                suffix = source.suffix.lower() if source.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"} else ".png"
                destination = data_directory() / "covers" / f"{uuid.uuid4().hex}{suffix}"
                shutil.copy2(source, destination)
                table["cover"] = str(destination)
            else:
                table["cover"] = dialog.cover_path
            self.persist()
            self.select_table(table["path"])
            self.render_tables()

    def remove_table(self):
        self.tables = [table for table in self.tables if table["path"] != self.selected_path]
        self.selected_path = ""
        self.detail_name.setText("Wybierz stół")
        self.detail_path.setText("Stół usunięto z kolekcji.")
        self.detail_art.setPixmap(QPixmap())
        self.detail_art.setText("WYBIERZ STÓŁ")
        self.persist()
        self.render_tables()

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("Zapisano ustawienia emulatora.", 4000)

    def launch_table(self):
        table = next((entry for entry in self.tables if entry["path"] == self.selected_path), None)
        if not table:
            return
        emulator = self.settings.value("emulator_path", "").strip()
        if not emulator or not Path(emulator).is_file():
            QMessageBox.information(self, "Skonfiguruj emulator", "Wybierz plik wykonywalny Visual Pinball X w ustawieniach.")
            self.open_settings()
            return
        arguments = self.settings.value("arguments", "").strip()
        import shlex
        command = [emulator, *shlex.split(arguments), "-play", table["path"]]
        working_directory = self.settings.value("working_directory", "").strip() or str(Path(emulator).parent)
        environment = os.environ.copy()
        if sys.platform.startswith("linux"):
            environment.update(dict(item.split("=", 1) for item in self.settings.value("linux_environment", "").split() if "=" in item))
        try:
            subprocess.Popen(command, cwd=working_directory, env=environment)
        except OSError as error:
            QMessageBox.critical(self, "Nie udało się uruchomić stołu", str(error))


STYLESHEET = """
QWidget { color: #e8eee9; font-family: 'Segoe UI', 'Noto Sans', sans-serif; font-size: 13px; }
QMainWindow, #root { background: #101512; }
#eyebrow { color: #b6d84a; font-size: 10px; font-weight: 700; }
#pageTitle { color: #f3f5ef; font-size: 28px; font-weight: 700; }
QPushButton { background: #222b25; color: #e8eee9; border: 1px solid #354239; border-radius: 6px; padding: 9px 13px; font-weight: 600; }
QPushButton:hover { background: #303d33; border-color: #70844c; }
QPushButton:disabled { color: #6a756d; background: #1a201c; border-color: #27302a; }
#primaryButton { color: #11170d; background: #b6d84a; border-color: #b6d84a; font-weight: 700; }
#primaryButton:hover { background: #c6e765; }
QLineEdit { background: #171e19; border: 1px solid #354239; border-radius: 6px; padding: 10px 12px; selection-background-color: #729334; }
QLineEdit:focus { border-color: #b6d84a; }
#searchInput { min-height: 21px; }
QScrollArea { background: transparent; }
#tableTile { background: #1a211c; border: 1px solid #2d3931; border-radius: 7px; }
#tableTile:hover, #tableTile[selected="true"] { border: 1px solid #b6d84a; background: #202a21; }
#tileArt { background: #26332a; color: #b6d84a; font-size: 24px; font-weight: 800; border-top-left-radius: 6px; border-top-right-radius: 6px; }
#tileName { padding: 9px 10px; font-size: 13px; font-weight: 600; }
#detailsPanel { background: #171e19; border: 1px solid #2d3931; border-radius: 7px; }
#detailArt { background: #26332a; color: #95a298; border-radius: 5px; font-size: 11px; font-weight: 700; }
#detailTitle { color: #f1f3eb; font-size: 19px; font-weight: 700; }
#mutedText { color: #98a49a; }
QSplitter::handle { width: 10px; background: transparent; }
QStatusBar { color: #98a49a; background: #101512; }
QMessageBox { background: #171e19; }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Segoe UI" if sys.platform == "win32" else "Noto Sans", 10))
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
