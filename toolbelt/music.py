"""Music: sending songs to Spotify's Local Files, looking a song up in Spotify, and reading / fixing song tags.

Spotify has no "import" for outside songs: its desktop app shows MP3s from folders you add under
Settings > Local Files. Toolbelt copies songs into one such folder (Music\\Toolbelt for Spotify). Adding that folder
in Spotify is a one-time click the person does; on a phone, local files need Spotify Premium.
Tags are read with ffprobe and written with ffmpeg (both from the engines), copying the audio untouched.
"""
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

import engines

NO_WINDOW = 0x08000000
SPOTIFY_DIR = Path.home() / "Music" / "Toolbelt for Spotify"
TAG_KEYS = ("title", "artist", "album")


def free_name(folder, name):
    """name, or name (2), name (3)… if that file already exists in folder."""
    target = Path(folder) / name
    stem, suffix, n = target.stem, target.suffix, 2
    while target.exists():
        target = Path(folder) / ("%s (%d)%s" % (stem, n, suffix))
        n += 1
    return target


def send_to_spotify(path):
    """Copies a song into the Spotify folder (the original stays where it was)."""
    src = Path(path)
    if not src.is_file():
        return {"ok": False, "message": "That file isn't there any more."}
    if src.suffix.lower() != ".mp3":
        return {"ok": False, "message": "Spotify only plays MP3s reliably: download it as MP3 first."}
    SPOTIFY_DIR.mkdir(parents=True, exist_ok=True)
    if src.parent.resolve() == SPOTIFY_DIR.resolve():
        return {"ok": True, "message": "It's already in the Spotify folder.", "path": str(src)}
    for existing in SPOTIFY_DIR.glob("*.mp3"):
        if existing.stat().st_size == src.stat().st_size and existing.stem.startswith(src.stem):
            return {"ok": True, "message": "It's already in the Spotify folder.", "path": str(existing)}
    target = free_name(SPOTIFY_DIR, src.name)
    shutil.copy2(src, target)
    square_cover(target)                                        # YouTube's 16:9 picture becomes a square cover, like Spotify's own
    return {"ok": True, "message": "Copied to Music\\Toolbelt for Spotify. In Spotify: Local Files.", "path": str(target)}


# ---------- covers ----------
def cover_bytes(path):
    """The picture inside the song (JPEG/PNG bytes), or b''."""
    ff = engines.path_of("ffmpeg")
    if not ff:
        return b""
    done = subprocess.run([str(ff), "-v", "error", "-i", str(path), "-an", "-c:v", "copy", "-f", "image2pipe", "-"],
                          capture_output=True, timeout=60, creationflags=NO_WINDOW)
    return done.stdout if done.returncode == 0 and len(done.stdout) > 100 else b""


def crop_square(image_bytes, crop=None, side=640):
    """A square JPEG from a picture. `crop` = {x, y, w} in the picture's own pixels (the square he framed), else the middle."""
    import io
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    W, H = img.size
    if crop and all(k in crop for k in ("x", "y", "w")):
        w = max(1, min(int(crop["w"]), W, H))
        x = max(0, min(int(crop["x"]), W - w))
        y = max(0, min(int(crop["y"]), H - w))
    else:
        w = min(W, H)
        x, y = (W - w) // 2, (H - w) // 2
    out = img.crop((x, y, x + w, y + w)).resize((side, side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=90, optimize=True)
    return buf.getvalue()


def set_cover(path, jpeg_bytes):
    """Puts a new front cover into the song, keeping sound, tags and lyrics."""
    ff = engines.path_of("ffmpeg")
    if not ff:
        return {"ok": False, "message": "Install ffmpeg first (Engines)."}
    src = Path(path)
    if src.suffix.lower() != ".mp3":
        return {"ok": False, "message": "Covers can only be set on MP3s here."}
    cover = src.with_name(src.stem + ".cover.jpg")
    tmp = src.with_name(src.stem + ".tagging" + src.suffix)
    cover.write_bytes(jpeg_bytes)
    try:
        args = [str(ff), "-y", "-v", "error", "-i", str(src), "-i", str(cover), "-map", "0:a", "-map", "1", "-map_metadata", "0", "-c", "copy",
                "-id3v2_version", "3", "-disposition:v", "attached_pic", "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)", str(tmp)]
        done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)
        if done.returncode != 0 or not tmp.exists():
            tmp.unlink(missing_ok=True)
            return {"ok": False, "message": "ffmpeg couldn't write the cover: " + (done.stderr.strip()[:200] or "unknown error")}
        os.replace(tmp, src)
    finally:
        cover.unlink(missing_ok=True)
    return {"ok": True, "message": "Cover saved. Spotify shows it the next time it reads the folder."}


def square_cover(path):
    """If the embedded cover isn't square (YouTube thumbnails are 16:9), crop the middle to a square."""
    try:
        from PIL import Image
        import io
        raw = cover_bytes(path)
        if not raw:
            return False
        with Image.open(io.BytesIO(raw)) as img:
            if abs(img.width - img.height) <= 2:
                return False
        return set_cover(path, crop_square(raw))["ok"]
    except Exception:
        return False


def video_id_of(tags):
    """yt-dlp stores the video's address in the purl tag; its id gives us the YouTube picture again."""
    import re
    for key in ("purl", "comment"):
        m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", str(tags.get(key, "")))
        if m:
            return m.group(1)
    return ""


def fetch_bytes(url, limit=20 * 1024 * 1024):
    """One web file, only when he asked for it (a cover from YouTube or a link he pasted)."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Toolbelt/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise ValueError("That file is bigger than 20 MB.")
    return data


def youtube_picture(video_id):
    """The biggest YouTube picture that exists for this video."""
    for name in ("maxresdefault", "sddefault", "hqdefault"):
        try:
            data = fetch_bytes("https://i.ytimg.com/vi/%s/%s.jpg" % (video_id, name))
            if len(data) > 2000:                                 # YouTube answers a tiny grey picture for sizes it lacks
                return data
        except Exception:
            continue
    return b""


# ---------- tags that Spicetify's lyrics-plus can match (15 Oct) ----------
# lyrics-plus never reads lyrics from the file: for a local song it searches LRCLIB and Musixmatch by the tags
# (title, artist, album, length). So clean tags are what make lyrics (and their romaji / translations) show up.
import re as _re

_NOISE = [r"【[^】]*】", r"\[[^\]]*\]", r"歌ってみた", r"\((?:cover|covered by[^)]*|official[^)]*|mv|music video|lyrics?)\)", r"（(?:cover|カバー)）",
          r"\b(?:official\s+(?:music\s+)?video|music\s+video|official\s+mv|mv|lyric video)\b", r"\s-\sMP3$", r"#\S+"]


def _tidy(text):
    text = _re.sub(r"\s+", " ", str(text)).strip(" -_/|・~～")
    return text.strip()


def suggest_tags(tags, file_name=""):
    """A clean title / artist / album from YouTube-style tags: 'め組のひと / 宝鐘マリン cover' → め組のひと, 宝鐘マリン."""
    raw = str(tags.get("title") or Path(file_name).stem or "")
    raw = _re.sub(r"\s-\sMP3$|\s-\s\d{3,4}p$", "", raw)
    singer = ""
    parts = _re.split(r"\s*/\s*|\s+---\s+|\s_\s|\s+\|\s+|\s+／\s*", raw, maxsplit=1)
    title = parts[0]
    if len(parts) > 1:
        singer = parts[1]
    for pattern in _NOISE:
        title = _re.sub(pattern, " ", title, flags=_re.I)
        singer = _re.sub(pattern, " ", singer, flags=_re.I)
    title = _re.sub(r"\(\s*\)|（\s*）", " ", title)
    title = _re.sub(r"\s-\s?([^-]{2,30}?)\s?-(?=\s|$)", r" (\1)", title)          # "BIRDBRAIN -Japanese Ver.-" → "BIRDBRAIN (Japanese Ver.)"
    singer = _re.sub(r"\b(?:cover|covered by|by)\b", " ", singer, flags=_re.I)
    singer = _re.sub(r"（[^）]*）|\([^)]*\)", " ", singer)                    # （9さい） and other notes
    artist = _tidy(singer)
    if not artist:
        artist = str(tags.get("artist") or "")
        artist = _re.sub(r"\b(?:Ch\.|Channel|Official|公式)\b", " ", artist, flags=_re.I)
        artist = _re.sub(r"hololive\S*|にじさんじ|【[^】]*】|\([^)]*\)", " ", artist, flags=_re.I)
        artist = _tidy(artist)
    title = _tidy(title)
    return {"title": title or raw, "artist": artist, "album": str(tags.get("album") or "") or title or raw}


def lrclib_check(title, artist, album, seconds):
    """Does what lyrics-plus does (LRCLIB api/get with the four tags) and, if that misses, lists entries that would match.
    Only when he presses the button."""
    import urllib.request
    import urllib.parse

    def fetch(url):
        req = urllib.request.Request(url, headers={"User-Agent": "Toolbelt/1.0 (https://github.com/Shamilimanuel/Toolbelt)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    import urllib.error
    busy = {"ok": False, "message": "LRCLIB says it's busy (too many questions in a short time). Try again in a minute."}
    exact = None
    try:
        exact = fetch("https://lrclib.net/api/get?" + urllib.parse.urlencode({"track_name": title, "artist_name": artist, "album_name": album, "duration": round(float(seconds or 0))}))
    except urllib.error.HTTPError as error:
        if error.code == 429:                                    # rate limit: not a "no", just "not now" (seen 15 Oct)
            return busy
        exact = None                                             # 404 = no entry with exactly these tags
    except Exception as error:
        return {"ok": False, "message": "Couldn't reach LRCLIB: %s" % str(error)[:120]}
    try:
        found = fetch("https://lrclib.net/api/search?" + urllib.parse.urlencode({"track_name": title}))
    except urllib.error.HTTPError as error:
        if error.code == 429 and not exact:
            return busy
        found = []
    except Exception as error:
        if exact:
            found = []
        else:
            return {"ok": False, "message": "Couldn't reach LRCLIB: %s" % str(error)[:120]}
    seen, cands = set(), []
    for r in found if isinstance(found, list) else []:
        key = (r.get("trackName"), r.get("artistName"), r.get("albumName"))
        if key in seen or not (r.get("plainLyrics") or r.get("syncedLyrics")):
            continue
        seen.add(key)
        diff = abs(float(r.get("duration") or 0) - float(seconds or 0))
        cands.append({"title": r.get("trackName") or "", "artist": r.get("artistName") or "", "album": r.get("albumName") or "",
                      "duration": r.get("duration") or 0, "diff": round(diff, 1), "synced": bool(r.get("syncedLyrics")), "fits": diff <= 2})
    cands.sort(key=lambda c: (not c["fits"], not c["synced"], c["diff"]))
    hit = bool(exact and (exact.get("plainLyrics") or exact.get("syncedLyrics")))
    return {"ok": True, "match": hit, "synced": bool(exact and exact.get("syncedLyrics")), "candidates": cands[:8]}


def fix_one(tags, file_name="", wait=None):
    """Fix all songs (15 Oct): the tags that make lyrics-plus find this song, decided the way he'd do it by hand.
    already = LRCLIB knows it as it is; clean = the cleaned-up tags hit; found = an LRCLIB entry of the same length;
    none = nothing fits (he fixes that one by hand). wait(seconds) is called between questions to stay polite."""
    import time as _time
    wait = wait or _time.sleep
    current = {k: str(tags.get(k) or "") for k in ("title", "artist", "album")}
    seconds = float(tags.get("seconds") or 0)

    def ask(t):
        for attempt in range(3):
            r = lrclib_check(t["title"], t["artist"], t["album"], seconds)
            if r.get("ok") or "busy" not in str(r.get("message", "")):
                return r
            wait(20 * (attempt + 1))                              # rate limit: give LRCLIB a breather, then again
        return r

    out = {"path": tags.get("path", ""), "name": tags.get("name") or file_name, "current": current, "proposed": dict(current), "status": "none", "synced": False, "message": ""}
    if current["title"]:
        r = ask(current)
        if not r.get("ok"):
            out["status"], out["message"] = "error", r.get("message", "")
            return out
        if r.get("match"):
            out.update(status="already", synced=r.get("synced", False))
            return out
        wait(0.6)
    clean = suggest_tags(tags, file_name)
    r = ask(clean) if clean != current else r
    if not r.get("ok"):
        out["status"], out["message"] = "error", r.get("message", "")
        return out
    if r.get("match"):
        out.update(status="clean", proposed=clean, synced=r.get("synced", False))
        return out
    fit = [c for c in r.get("candidates", []) if c.get("fits")]
    if fit:
        c = fit[0]
        out.update(status="found", proposed={"title": c["title"], "artist": c["artist"], "album": c["album"]}, synced=c["synced"])
    else:
        out["proposed"] = clean
    return out


# ---------- lyrics (LRCLIB: free, no account; fetched only when he presses Find) ----------
def lyrics_find(title, artist="", seconds=0):
    import urllib.request
    import urllib.parse
    q = {"track_name": title, "artist_name": artist} if artist else {"q": title}
    url = "https://lrclib.net/api/search?" + urllib.parse.urlencode(q)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Toolbelt/1.0 (https://github.com/Shamilimanuel/Toolbelt)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            found = json.loads(resp.read().decode("utf-8"))
    except Exception as error:
        return {"ok": False, "message": "Couldn't reach LRCLIB: %s" % str(error)[:120]}
    if not isinstance(found, list) or not found:
        return {"ok": False, "message": "LRCLIB has no lyrics for that title. Try a shorter title (just the song name) and the artist."}
    found.sort(key=lambda r: (abs(float(r.get("duration") or 0) - float(seconds or 0)) if seconds else 0, 0 if r.get("syncedLyrics") else 1))
    best = found[0]
    return {"ok": True, "plain": best.get("plainLyrics") or "", "synced": best.get("syncedLyrics") or "", "instrumental": bool(best.get("instrumental")),
            "found": "%s · %s" % (best.get("trackName", ""), best.get("artistName", "")), "matches": len(found)}


def set_lyrics(path, plain, synced=""):
    """Writes the lyrics into the MP3 (the USLT tag Spicetify's lyrics-plus reads) and, when synced, a .lrc next to it."""
    ff = engines.path_of("ffmpeg")
    if not ff:
        return {"ok": False, "message": "Install ffmpeg first (Engines)."}
    src = Path(path)
    if src.suffix.lower() != ".mp3":
        return {"ok": False, "message": "Lyrics can only be written into MP3s here."}
    plain = str(plain or "").replace("\r\n", "\n").strip()[:20000]
    tmp = src.with_name(src.stem + ".tagging" + src.suffix)
    args = [str(ff), "-y", "-v", "error", "-i", str(src), "-map", "0", "-c", "copy", "-id3v2_version", "3", "-metadata", "lyrics=" + plain, str(tmp)]
    done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)
    if done.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        return {"ok": False, "message": "ffmpeg couldn't write the lyrics: " + (done.stderr.strip()[:200] or "unknown error")}
    os.replace(tmp, src)
    lrc = src.with_suffix(".lrc")
    if synced and str(synced).strip():
        lrc.write_text(str(synced).replace("\r\n", "\n").strip() + "\n", encoding="utf-8")
        write_ttml(src, synced)
    elif not plain:
        lrc.unlink(missing_ok=True)
        src.with_suffix(".ttml").unlink(missing_ok=True)
    return {"ok": True, "message": "Lyrics saved in the song" + (" (plus a .lrc and a .ttml for Spicy Lyrics, with the timing)" if synced else "") + ". For Spotify's lyrics-plus, the tags are what count (Tags → Fix for lyrics)." if plain else "Lyrics removed."}


LRC_TIME = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")


def lrc_to_ttml(synced, seconds=0):
    """A .lrc (one [mm:ss.xx] per line) as a line-timed TTML, the file Spicy Lyrics imports for a local song (25 Oct: it
    doesn't look local files up online). Each line ends where the next begins; an empty LRC line is a pause; the last
    line ends with the song. No empty lines in the file (Spicy Lyrics' rule). Returns "" when there's no timing."""
    from xml.sax.saxutils import escape
    timed = []
    for raw in str(synced or "").replace("\r\n", "\n").split("\n"):
        stamps = LRC_TIME.findall(raw)
        text = LRC_TIME.sub("", raw).strip()
        for m, s in stamps:                                      # [00:12.30][01:40.10]chorus: the same line twice
            timed.append((int(m) * 60 + float(s.replace(":", ".")), text))
    timed.sort(key=lambda t: t[0])
    if not any(text for _, text in timed):
        return ""
    end_all = max(float(seconds or 0), timed[-1][0] + 4)

    def clock(t):
        return "%d:%06.3f" % (int(t // 60), t % 60)
    lines = []
    for i, (start, text) in enumerate(timed):
        if not text:
            continue
        end = timed[i + 1][0] if i + 1 < len(timed) else end_all
        lines.append('<p begin="%s" end="%s" ttm:agent="v1">%s</p>' % (clock(start), clock(max(end, start + 0.1)), escape(text)))
    words = " ".join(text for _, text in timed)
    lang = "ja" if re.search(r"[぀-ヿ一-鿿]", words) else "en"
    first = next(start for start, text in timed if text)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<tt xmlns="http://www.w3.org/ns/ttml" xmlns:itunes="http://music.apple.com/lyric-ttml-internal" '
            'xmlns:ttm="http://www.w3.org/ns/ttml#metadata" itunes:timing="Line" xml:lang="%s">'
            '<head><metadata><ttm:agent type="person" xml:id="v1"/></metadata></head>'
            '<body dur="%s"><div begin="%s" end="%s">%s</div></body></tt>\n') % (lang, clock(end_all), clock(first), clock(end_all), "".join(lines))


def write_ttml(src, synced=None):
    """The .ttml next to the song (from the .lrc when no lyrics are given). Returns its path, or None."""
    src = Path(src)
    if synced is None:
        lrc = src.with_suffix(".lrc")
        if not lrc.exists():
            return None
        synced = lrc.read_text(encoding="utf-8", errors="replace")
    tags = read_tags(src)
    ttml = lrc_to_ttml(synced, tags.get("seconds", 0) if tags.get("ok") else 0)
    if not ttml:
        return None
    out = src.with_suffix(".ttml")
    out.write_text(ttml, encoding="utf-8")
    return out


def spotify_search(query):
    """Opens Spotify's own search for this song (the app if installed, else the website)."""
    q = " ".join(str(query).split())[:200]
    if not q:
        return {"ok": False, "message": "Nothing to search for."}
    try:
        os.startfile("spotify:search:" + urllib.parse.quote(q))
        return {"ok": True, "message": "Searching Spotify for: " + q}
    except OSError:
        webbrowser.open("https://open.spotify.com/search/" + urllib.parse.quote(q))
        return {"ok": True, "message": "Spotify isn't installed, so the search opened in your browser."}


def ffprobe_path():
    probe = engines.path_of("ffmpeg")
    return probe.parent / "ffprobe.exe" if probe else None


def read_tags(path):
    ffprobe = ffprobe_path()
    if not ffprobe:
        return {"ok": False, "message": "Install ffmpeg first (Engines)."}
    done = subprocess.run([str(ffprobe), "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=NO_WINDOW)
    if done.returncode != 0:
        return {"ok": False, "message": "ffprobe couldn't read that file."}
    data = json.loads(done.stdout or "{}")
    tags = {k.lower(): v for k, v in (data.get("format", {}).get("tags") or {}).items()}
    pic = [s for s in data.get("streams", []) if s.get("disposition", {}).get("attached_pic")]
    lyrics = next((v for k, v in tags.items() if k == "lyrics" or k.startswith("lyrics-")), "")
    return {"ok": True, "path": str(path), "name": Path(path).name, "title": tags.get("title", ""), "artist": tags.get("artist", ""),
            "album": tags.get("album", ""), "cover": bool(pic), "square": bool(pic) and abs(int(pic[0].get("width", 0) or 0) - int(pic[0].get("height", 0) or 0)) <= 2,
            "lyrics": bool(lyrics.strip()), "lrc": Path(path).with_suffix(".lrc").exists(), "ttml": Path(path).with_suffix(".ttml").exists(), "video_id": video_id_of(tags),
            "seconds": float(data.get("format", {}).get("duration") or 0)}


def write_tags(path, values):
    """Rewrites title / artist / album, copying the sound and the cover untouched."""
    ff = engines.path_of("ffmpeg")
    if not ff:
        return {"ok": False, "message": "Install ffmpeg first (Engines)."}
    src = Path(path)
    if not src.is_file() or src.suffix.lower() not in (".mp3", ".m4a"):
        return {"ok": False, "message": "Only MP3 and M4A songs can be tagged here."}
    tmp = src.with_name(src.stem + ".tagging" + src.suffix)
    args = [str(ff), "-y", "-v", "error", "-i", str(src), "-map", "0", "-c", "copy"]
    if src.suffix.lower() == ".mp3":
        args += ["-id3v2_version", "3"]
    for key in TAG_KEYS:
        if key in values:
            args += ["-metadata", "%s=%s" % (key, str(values[key])[:300])]
    done = subprocess.run(args + [str(tmp)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, creationflags=NO_WINDOW)
    if done.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        return {"ok": False, "message": "ffmpeg couldn't write the tags: " + (done.stderr.strip()[:200] or "unknown error")}
    os.replace(tmp, src)
    return {"ok": True, "message": "Saved. Spotify picks up the new title next time it looks at the folder.", "tags": read_tags(src)}


def songs():
    """The songs in the Spotify folder, with their tags."""
    if not SPOTIFY_DIR.exists():
        return []
    out = []
    for p in sorted(SPOTIFY_DIR.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)[:200]:
        if p.with_suffix(".lrc").exists() and not p.with_suffix(".ttml").exists():
            write_ttml(p)                                      # songs from before 25 Oct get their Spicy Lyrics file too
        out.append(read_tags(p))
    return out
