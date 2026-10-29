# VPinball Launcher

Desktopowy launcher Visual Pinball X napisany w Pythonie i PySide6. Działa na
Windows oraz Linuksie (w tym Fedora KDE).

## Funkcje

- Katalog stołów z wyszukiwaniem i okładkami.
- Ręczne dodawanie plików `.vpx` oraz skanowanie wybranego katalogu i jego
	podkatalogów.
- Okładki z pliku lokalnego lub pobrane z bezpośredniego adresu URL obrazu.
- Konfiguracja pliku emulatora, katalogu roboczego, dodatkowych argumentów
	i opcjonalnych zmiennych środowiskowych Linuksa.
- Biblioteka i pobrane okładki są przechowywane w katalogu danych użytkownika;
	nie wymagają instalacji bazy danych.

## Uruchamianie

Wymagany jest Python 3.10 lub nowszy.

Linux / Fedora:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Po pierwszym uruchomieniu otwórz **Ustawienia** i wybierz program Visual
Pinball X (`VPinballX.exe` w Windows lub `VPinballX_BGFX` w Linuksie). Katalog
roboczy domyślnie wskazuje folder emulatora. Opcjonalne zmienne środowiskowe
Linuksa wpisz rozdzielone spacjami, np. `SDL_VIDEODRIVER=x11`.

## Uruchamianie z powłoki

Dotychczasowy skrypt `vpxlauncher.sh` pozostaje bez zmian. Nowa aplikacja ma
własną bibliotekę i ustawienia; uruchom ją poleceniem `python main.py`.