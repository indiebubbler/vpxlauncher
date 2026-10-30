"""Punkt wejścia: python -m vpxlauncher"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from . import config
from .backend import Backend
from .library import Library
from .models import TableModel

QML_DIR = Path(__file__).resolve().parent / "qml"

# Paleta "szyba bekglasu nocą": granat + bursztynowa żarówka (jedyny mocny akcent).
THEME = {
    "bg": "#0f1623",
    "surface": "#172033",
    "raised": "#1f2b43",
    "line": "#2c3b5a",
    "text": "#e9edf5",
    "muted": "#8e9bb4",
    "lamp": "#ffb347",
    "lampDeep": "#c9791a",
}


def main() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("VPX Launcher")
    app.setDesktopFileName("vpx-launcher")

    settings = config.Settings.load()
    library = Library(config.data_dir() / "library.db")
    model = TableModel()
    backend = Backend(library, settings, model)

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("theme", THEME)
    ctx.setContextProperty("backend", backend)
    ctx.setContextProperty("tableModel", model)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()
