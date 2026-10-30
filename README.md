# VPX Launcher (MVP)

A modern launcher for Visual Pinball X tables, with an image tile grid, search, favorites, and folder scanning. Built with Python and PySide6 (Qt Quick); runs on Linux and Windows.

The app is in English by default. To switch to Polish, open **Settings** and change **Language**. The language setting is saved between launches.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m vpxlauncher
```

On its first launch on Linux, the launcher looks for `~/Gry/VPinballX_BGFX*/VPinballX_BGFX`, adds its `tables` subfolder, and sets the environment variables used by the previous script (`__NV_PRIME_RENDER_OFFLOAD`, `__GLX_VENDOR_LIBRARY_NAME`, `SDL_VIDEODRIVER`). You can change these settings in **Settings**.

## Using the app

- **Play**: double-click a tile, press Enter, or click the amber button that appears when you hover over a tile.
- **Library → Scan folders** scans the folders configured in Settings, including subfolders. Use **Add table...** or drop `.vpx` files or folders onto the window to add tables manually.
- **Artwork** is downloaded automatically from the Virtual Pinball Spreadsheet database (see below). Add your own by dropping an image onto a tile or right-clicking and choosing *Choose artwork...*; manual artwork takes precedence. An image next to a table with the same base name (for example, `Table.vpx` and `Table.png`) is detected automatically.
- Right-click a tile to manage favorites and artwork, *Find artwork online* (replaces the current image), or remove the artwork or table from the library. Removing a table does not delete its file from disk.
- **Removed tables do not reappear when scanning.** Add the file manually or use *Library → Restore removed tables* to bring them back.
- **Tile size**: use the *Tiles* button (Small, Medium, Large, Very large, Huge), `Ctrl +` / `Ctrl -`, or `Ctrl` + mouse wheel. Your choice is saved.
- **Game display**: use the *Game display* link in the footer to choose the monitor where VPinball starts: *Unchanged*, *Automatic* (an external display if connected, otherwise display 0), or a specific display from the list. A specific display is remembered by name, such as `DP-2`. The list refreshes when displays are connected or disconnected.
- **Game log**: click *Show game log* at the bottom of the window to open `vpinball.log` (the end of the file, with refresh and copy controls). If the game exits unexpectedly, the status bar suggests checking the log.
- Shortcuts: `Ctrl+F` to search, arrow keys to navigate, Enter to play, and `Ctrl +` / `Ctrl -` to change tile size.

## Automatic artwork (VPS database)

- After scanning, new tables without artwork are matched against the Virtual Pinball Spreadsheet database and assigned a playfield image (or, if unavailable, a flyer or backglass). Disable this in **Settings**.
- **Library → Download missing artwork** retries for all tables without an image.
- Matching is performed locally using the file name (`Title (Manufacturer Year) ...`), manufacturer, year, and minor spelling differences. Uncertain matches are rejected, so some tables may remain without artwork; add an image manually. If multiple playfield images are available, the one whose description best matches the file name (for example, `VPW`) is selected.
- The app only sends requests to download the public database (cached for 7 days in `vps-index.json`) and image URLs. Your file names are not sent. Only HTTPS URLs are allowed; images are validated (PNG/JPG/WebP) and limited to 8 MB.
- When offline, the launcher uses the last downloaded database. You can specify a custom database URL in the `vps_db_url` key in `settings.json`.

## Data locations

- Settings: `~/.config/vpx-launcher/settings.json` (Windows: `%APPDATA%\vpx-launcher`)
- Library and artwork: `~/.local/share/vpx-launcher/` (Windows: `%LOCALAPPDATA%\vpx-launcher`)

## Known MVP limitations

- There is no manual selection among multiple match candidates; matching is fully automatic.
- The official VPS database URL and live downloads have not been verified; the matching logic is tested with sample data. If the URL changes, set the new one in `vps_db_url`.
- A tile's name is the `.vpx` file name. The author and version are read from the file (requires `olefile`).
- Tables removed in an older version, before removal became permanent, will reappear the next time you scan. Remove them again if needed.
- The log viewer displays the file as written by VPinball. The default Linux path is `~/.local/share/VPinballX/10.8/vpinball.log`; the assumed Windows path is `%APPDATA%\VPinballX\10.8\vpinball.log` (unverified). You can change it in Settings.
- **Display selection has not been tested with VPinball 10.8.1.** Before launch, the launcher sets the `Display` key in the `[Player]` section of `VPinballX.ini` (next to `vpinball.log`) and changes only that line. The first change creates a `VPinballX.ini.launcher-backup` copy. Display numbers follow the launcher's list (the primary display is 0); if VPinball numbers displays differently and the game opens on the wrong one, choose another display in the menu. If the file also has a `PlayfieldDisplay` key, it is set to the same value. In *Unchanged* mode, the file is not modified.
- A built-in laptop display is detected by its name (`eDP`, `LVDS`, `DSI`). On Windows, the first non-primary display is chosen as the external display.
- Logic tests: `python -m unittest discover -s tests`.
