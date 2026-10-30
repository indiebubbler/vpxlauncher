"""Dopasowanie stołów do bazy Virtual Pinball Spreadsheet (VPS) i pobieranie grafik.

Dopasowanie działa lokalnie: do internetu trafia tylko pobranie publicznej bazy
oraz adresów obrazów, nazwy Twoich plików nie są nigdzie wysyłane.
"""
from __future__ import annotations

import difflib
import gzip
import json
import os
import re
import time
import unicodedata
import urllib.request
import zlib
from pathlib import Path

# Pierwszy adres to oficjalna baza, drugi to kopia na GitHubie. Własny adres można
# podać w settings.json (klucz "vps_db_url"), wtedy jest próbowany jako pierwszy.
DB_URLS = [
    "https://virtualpinballspreadsheet.github.io/vps-db/db/vpsdb.json",
    "https://raw.githubusercontent.com/Fraesh/vps-db/master/vpsdb.json",
]
CACHE_MAX_AGE = 7 * 24 * 3600
USER_AGENT = "vpx-launcher/0.2 (desktop app; contact: local user)"
MAX_DB_BYTES = 250 * 1024 * 1024
MAX_IMG_BYTES = 8 * 1024 * 1024
ACCEPT_SCORE = 0.88

NOISE_WORDS = {
    "vpw", "mod", "vr", "fss", "rom", "b2s", "hybrid", "vpx", "edition", "remake",
    "reskin", "physmod", "fixed", "fix", "final", "beta", "release", "table",
}
YEAR_RE = re.compile(r"\b(19[3-9]\d|20[0-4]\d)\b")
VERSION_RE = re.compile(r"\bv?\d+(?:[._]\d+)+[a-z]?\b|\bv\d+[a-z]?\b", re.IGNORECASE)


# ---- sieć --------------------------------------------------------------------
def _gunzip(raw: bytes, limit: int) -> bytes:
    out = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, limit + 1)
    if len(out) > limit:
        raise ValueError("Odpowiedź po rozpakowaniu jest zbyt duża")
    return out


def http_get(url: str, timeout: float = 30, max_bytes: int = MAX_IMG_BYTES) -> bytes:
    """Pobiera zasób po HTTPS z limitem rozmiaru (łatwo podmienić w testach)."""
    if not url.lower().startswith("https://"):
        raise ValueError("Dozwolone są tylko adresy https")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("Odpowiedź jest zbyt duża")
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = _gunzip(raw, max_bytes)
    return raw


def sniff_image_ext(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


# ---- normalizacja nazw -------------------------------------------------------
_SPECIAL = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ß": "ss", "æ": "ae", "Æ": "AE"})


def _strip_accents(text: str) -> str:
    # NFKD nie rozkłada m.in. "ł" i "ø", więc zamieniamy je ręcznie.
    text = text.translate(_SPECIAL)
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def title_key(text: str) -> str:
    """Klucz porównawczy: bez wielkości liter, akcentów, interpunkcji i przedimka 'The'."""
    s = _strip_accents(text).casefold().replace("&", " and ")
    s = re.sub(r",\s*the\s*$", "", s)
    s = re.sub(r"^\s*the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def parse_stem(stem: str) -> tuple[str, int, str]:
    """'Twilight Zone (Bally 1993) VPW 1.0' -> ('Twilight Zone', 1993, 'Bally')."""
    stem = stem.replace("_", " ")
    year, mfr = 0, ""
    m = re.match(r"^(.*?)\s*\(([^)]*)\)", stem)
    if m:
        title, meta = m.group(1), m.group(2)
        y = YEAR_RE.search(meta)
        if y:
            year = int(y.group(1))
            meta = YEAR_RE.sub("", meta)
        mfr = meta.strip(" ,-/")
    else:
        title = stem
        title = VERSION_RE.sub(" ", title)
        title = " ".join(w for w in title.split() if w.casefold() not in NOISE_WORDS)
        y = YEAR_RE.search(title)
        if y:
            year = int(y.group(1))
            title = YEAR_RE.sub(" ", title)
    return title.strip(" -_."), year, mfr


# ---- indeks bazy -------------------------------------------------------------
def compact(raw_games) -> list[dict]:
    """Zmniejsza ogromny vpsdb.json do pól potrzebnych do dopasowania grafik."""
    out: list[dict] = []
    for g in raw_games if isinstance(raw_games, list) else []:
        if not isinstance(g, dict) or not g.get("name"):
            continue
        tables = []
        for tf in g.get("tableFiles") or []:
            if not isinstance(tf, dict) or tf.get("tableFormat") != "VPX":
                continue
            hint = " ".join([*(str(a) for a in tf.get("authors") or []), str(tf.get("comment") or ""), str(tf.get("version") or "")])
            tables.append({"img": str(tf.get("imgUrl") or ""), "hint": hint})
        b2s = next((str(b["imgUrl"]) for b in g.get("b2sFiles") or [] if isinstance(b, dict) and b.get("imgUrl")), "")
        try:
            year = int(g.get("year") or 0)
        except (TypeError, ValueError):
            year = 0
        out.append({
            "name": str(g["name"]),
            "mfr": str(g.get("manufacturer") or ""),
            "year": year,
            "tables": tables,
            "cover": str(g.get("imgUrl") or ""),
            "b2s": b2s,
        })
    return out


def _usable(url: str) -> bool:
    return url.startswith("https://") and "/undefined_" not in url


class VpsIndex:
    def __init__(self, games: list[dict]):
        self.games = games
        self._by_key: dict[str, list[dict]] = {}
        for g in games:
            key = title_key(g["name"])
            if key:
                self._by_key.setdefault(key, []).append(g)
        self._keys = list(self._by_key)

    @classmethod
    def load(cls, cache_path: Path, extra_urls: list[str] | None = None) -> "VpsIndex":
        cache_path = Path(cache_path)
        fresh = cache_path.is_file() and time.time() - cache_path.stat().st_mtime < CACHE_MAX_AGE
        if fresh:
            try:
                return cls(json.loads(cache_path.read_text("utf-8")))
            except (OSError, ValueError):
                pass
        errors: list[str] = []
        for url in [u for u in (extra_urls or []) if u] + DB_URLS:
            try:
                raw = http_get(url, timeout=120, max_bytes=MAX_DB_BYTES)
                games = compact(json.loads(raw.decode("utf-8")))
                if not games:
                    raise ValueError("pusta baza")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = cache_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(games, ensure_ascii=False), "utf-8")
                os.replace(tmp, cache_path)
                return cls(games)
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        if cache_path.is_file():  # nieaktualna kopia lepsza niż brak
            try:
                return cls(json.loads(cache_path.read_text("utf-8")))
            except (OSError, ValueError):
                pass
        raise RuntimeError("; ".join(errors) or "brak dostępnych źródeł")

    def find(self, stem: str) -> dict | None:
        title, year, mfr = parse_stem(stem)
        key = title_key(title)
        if not key:
            return None
        cands: dict[int, tuple[dict, float]] = {id(g): (g, 1.0) for g in self._by_key.get(key, [])}
        if not cands:
            for k in difflib.get_close_matches(key, self._keys, n=5, cutoff=0.86):
                ratio = difflib.SequenceMatcher(None, key, k).ratio()
                for g in self._by_key[k]:
                    cands[id(g)] = (g, ratio)
        best, best_score = None, 0.0
        for g, base in cands.values():
            score = base
            if year and g["year"]:
                score += 0.1 if year == g["year"] else (-0.15 if abs(year - g["year"]) > 1 else 0.0)
            if mfr and g["mfr"]:
                a, b = title_key(mfr), title_key(g["mfr"])
                if a and b:
                    score += 0.05 if (a in b or b in a) else -0.05
            score += min(len(g["tables"]), 10) * 0.001  # remis: lepiej opisany wpis
            if score > best_score:
                best, best_score = g, score
        return best if best_score >= ACCEPT_SCORE else None

    @staticmethod
    def image_url(game: dict, stem: str) -> str:
        """Najlepsza grafika: zrzut stołu pasujący do nazwy pliku, potem jakikolwiek, potem okładka."""
        words = {w for w in re.split(r"[^a-z0-9]+", _strip_accents(stem).casefold()) if len(w) > 1}
        best_url, best_overlap = "", -1
        for t in game["tables"]:
            if not _usable(t["img"]):
                continue
            hint_words = {w for w in re.split(r"[^a-z0-9]+", _strip_accents(t["hint"]).casefold()) if len(w) > 1}
            overlap = len(words & hint_words)
            if overlap > best_overlap:
                best_url, best_overlap = t["img"], overlap
        if best_url:
            return best_url
        for fallback in (game["cover"], game["b2s"]):
            if _usable(fallback):
                return fallback
        return ""
