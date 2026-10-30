# VPX Launcher (MVP)

Nowoczesny launcher stołów Visual Pinball X: siatka kafelków z grafikami, wyszukiwarka,
ulubione, skanowanie folderów. Python + PySide6 (Qt Quick), działa na Linuksie i Windowsie.

## Uruchomienie

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m vpxlauncher
```

Przy pierwszym uruchomieniu na Linuksie launcher sam szuka `~/Gry/VPinballX_BGFX*/VPinballX_BGFX`,
dodaje jego podfolder `tables` i wstawia zmienne ze starego skryptu
(`__NV_PRIME_RENDER_OFFLOAD`, `__GLX_VENDOR_LIBRARY_NAME`, `SDL_VIDEODRIVER`).
Wszystko zmienisz w oknie **Ustawienia**.

## Obsługa

- **Graj**: dwuklik na kafelku, Enter albo bursztynowy przycisk po najechaniu.
- **Biblioteka → Skanuj foldery**: przeszukuje foldery z ustawień (rekurencyjnie). **Dodaj stół…** albo upuszczenie
  plików `.vpx` / folderów na okno dodaje je ręcznie.
- **Grafika**: pobierana automatycznie z bazy Virtual Pinball Spreadsheet (patrz niżej). Własną dodasz,
  upuszczając obraz na kafelek albo przez prawy przycisk → *Wybierz grafikę…*; ręczna grafika ma pierwszeństwo.
  Obraz leżący obok stołu pod tą samą nazwą (`Stol.vpx` + `Stol.png`) jest wykrywany sam.
- Prawy przycisk na kafelku: ulubione, wybierz grafikę, *Znajdź grafikę online* (podmienia obecną),
  usuń grafikę, usuń z biblioteki (plik na dysku zostaje).
- **Usunięty stół nie wraca przy skanowaniu.** Wraca tylko po ręcznym dodaniu pliku albo przez
  *Biblioteka → Przywróć usunięte stoły*.
- **Rozmiar kafelków**: przycisk *Kafelki* (małe, średnie, duże, bardzo duże, ogromne), `Ctrl +` / `Ctrl -`
  albo `Ctrl` + kółko myszy. Wybór jest zapamiętywany.
- **Ekran gry**: link *Ekran gry* w stopce wybiera monitor, na którym startuje VPinball: *Bez zmian*,
  *Automatycznie* (zewnętrzny, jeśli podłączony; bez niego ekran 0) albo konkretny ekran z listy
  (zapamiętywany po nazwie, np. `DP-2`). Lista odświeża się po podłączeniu i odłączeniu monitora.
- **Log gry**: link *Pokaż log gry* na dole okna otwiera `vpinball.log` (końcówka pliku, z odświeżaniem
  i kopiowaniem). Po błędnym zamknięciu gry pasek stanu podpowiada, żeby tam zajrzeć.
- Skróty: `Ctrl+F` szukaj, strzałki nawigacja, `Enter` graj, `Ctrl +` / `Ctrl -` rozmiar kafelków.

## Automatyczne grafiki (baza VPS)

- Po skanowaniu nowe stoły bez grafiki są dopasowywane do bazy Virtual Pinball Spreadsheet i dostają zrzut
  stołu (a jeśli go brak, okładkę lub backglass). Wyłączysz to w **Ustawieniach**.
- **Biblioteka → Pobierz brakujące grafiki** ponawia próbę dla wszystkich stołów bez obrazu.
- Dopasowanie jest lokalne: po nazwie pliku (`Tytuł (Producent Rok) …`), z uwzględnieniem producenta i roku
  oraz drobnych literówek. Zbyt niepewne dopasowania są odrzucane, więc część stołów zostanie bez grafiki
  (dodasz ją ręcznie). Przy kilku zrzutach wybierany jest ten, którego opis pasuje do nazwy pliku (np. `VPW`).
- Do internetu trafia tylko pobranie publicznej bazy (cache 7 dni w `vps-index.json`) i adresów obrazów.
  Nazwy Twoich plików nie są wysyłane. Dozwolone są wyłącznie adresy https, obrazy są sprawdzane (PNG/JPG/WebP)
  i limitowane do 8 MB.
- Bez internetu launcher używa ostatniej pobranej bazy. Własny adres bazy możesz wpisać w `settings.json`
  w kluczu `vps_db_url`.

## Dane

- Ustawienia: `~/.config/vpx-launcher/settings.json` (Windows: `%APPDATA%\vpx-launcher`)
- Biblioteka i grafiki: `~/.local/share/vpx-launcher/` (Windows: `%LOCALAPPDATA%\vpx-launcher`)

## Znane ograniczenia MVP

- Brak ręcznego wyboru spośród kilku kandydatów: dopasowanie jest w pełni automatyczne.
- Nie sprawdziłem na żywo adresu oficjalnej bazy VPS ani działania pobierania; logika jest przetestowana
  na danych testowych. Gdyby adres się zmienił, podaj nowy w `vps_db_url`.
- Nazwa kafelka = nazwa pliku `.vpx`; autor i wersja są czytane z pliku (wymaga `olefile`).
- Stoły usunięte w starszej wersji (zanim usuwanie stało się trwałe) wrócą przy najbliższym skanowaniu; usuń je ponownie.
- Log pokazuje plik tak, jak zapisał go VPinball. Domyślna ścieżka na Linuksie to
  `~/.local/share/VPinballX/10.8/vpinball.log`; na Windowsie przyjąłem `%APPDATA%\VPinballX\10.8\vpinball.log`
  (niezweryfikowane), w razie czego zmienisz ją w Ustawieniach.
- **Wybór ekranu nie był sprawdzony z prawdziwym VPinball 10.8.1.** Launcher ustawia przed startem klucz
  `Display` w sekcji `[Player]` pliku `VPinballX.ini` (leży obok `vpinball.log`) i zmienia tylko tę jedną linię.
  Pierwsza zmiana tworzy kopię `VPinballX.ini.launcher-backup`. Numer ekranu to kolejność z listy launchera
  (główny jako 0); jeśli VPinball numeruje ekrany inaczej i gra otworzy się na złym, wybierz w menu drugi ekran.
  Gdy w pliku jest też klucz `PlayfieldDisplay`, jest ustawiany tak samo. Przy trybie *Bez zmian* plik nie jest ruszany.
- Wykrywanie wbudowanego ekranu laptopa działa po nazwie (`eDP`, `LVDS`, `DSI`). Na Windowsie jako zewnętrzny
  wybierany jest pierwszy ekran niegłówny.
- Testy logiki: `python -m unittest discover -s tests`.
