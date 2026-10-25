"""Toolbelt: Shamil's home for his own apps plus everyday tools (downloader, cut-outs, converters, …).

Run it with the Python in its own folder:
    %LOCALAPPDATA%\\Toolbelt\\venv\\Scripts\\pythonw.exe main.py

The window is an Edge WebView (pywebview), handed the page as one piece of text (see page.py): no web server,
no port. The page talks to Python through `window.pywebview.api` (the Api class below).
Settings, engines and the window's own storage live in %LOCALAPPDATA%\\Toolbelt, never in OneDrive.

    --hidden --selftest FILE   start without showing the window, check the page works, write the result to
                               FILE and quit (used by the tests, so no window ever appears on screen)
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import webbrowser
import winreg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "toolbelt"))   # the modules live in toolbelt/ (25 Oct)

import psutil
import webview

import viewer
import winbar

import shellicon

import base64
import io

import threading

import apps
import appguard
import guardscan
import brand
import check
import clipboard
import drivers
import hotkey
import gameart
import games
import jumplist
import media
import qrmaker
import renamer
import tray
import wallpaper
import upscale
import colours
import cutout
import downloader
import engines
import installer
import leftscan
import music
import netswitch
import pccare
import ping
from clipboard import Watcher
from jobs import Jobs
from page import build_page, build_popup, build_calcpop, build_guard
from settings import DATA, Settings

VERSION = "1.0 (all nine steps: drivers and ping finish PC care)"
BACKGROUND = {"cartridge": "#26225A", "glass": "#EEF1F8", "glassdark": "#1C1E2A"}
PYTHONW = Path(sys.executable).with_name("pythonw.exe")
PYTHONW = PYTHONW if PYTHONW.exists() else Path(sys.executable)
LAUNCHER = Path(sys.executable).with_name("Toolbelt.exe")       # made by brand.make_launcher on start; shortcuts point at it
POPUP = ("Toolbelt Games", 320, 470)                          # the tray pop-up: title, width, height
CALCPOP = ("Toolbelt Calculator", 380, 560)
GUARD = ("Toolbelt App Guard", 380, 470)                          # App guard's warning, above the clock                   # the floating mini calculator


class Api:
    """What the page may ask Python to do. Every answer is plain data (turned into JSON by pywebview)."""

    def __init__(self, testing=False):
        self._settings = Settings()
        self._jobs = Jobs()
        self._window = None                               # set by main(), for the folder picker
        self._testing = testing
        self._clip = Watcher(lambda: self._settings.get()["watch_clipboard"])
        self._updates = None                              # the last update check (it needs the internet, so it's cached)
        self._cuts = {}                                   # token -> the picture, its cut-out and the chosen options
        self._sent = set()                                # folders downloads went to this session (Desktop, his own folder…)
        self._covers = {}                                 # token -> picture bytes waiting in the cover editor
        self._programs = None                             # the installed programs (step 9), read on first use
        self._store = None                                # the Windows (Store) apps, read on first use
        self._revo = leftscan.Session()                    # one uninstall / leftover hunt at a time (the Revo-style dialog)
        self._wint = None                                 # the Win+W keyboard hook, when switched on
        self._own_bar = False                             # True once Windows' title bar is replaced by the page's (winbar.py)
        self._drivers = None                              # the drivers and the board, read on first use
        self._ping = ping.Monitor()                       # pings only while the Ping & lag tab is open
        self._media = {}                                  # token -> file path, for Pictures & video
        self._media_before = {}                           # token -> "before" preview for Compress picture
        self._clips, self._clips_at = None, 0.0           # his game recordings
        self._games, self._games_at = None, 0.0           # the game list, read again after a minute
        self._hd = gameart.Worker(on_done=self._hd_done)   # small covers and banners are upscaled in the background (15 Oct)
        self._popup, self._popup_shown = None, False      # the tray pop-up window
        self._calcpop, self._calc_shown = None, False     # the floating mini calculator
        self._tray = None
        self._mail = []                                   # "open this screen" notes for the page (from --open and the tray)
        self._guardwin, self._guard_shown = None, False   # App guard's warning window (18 Oct)
        self._guard = appguard.Guard(self._settings.get, on_ask=self._guard_ask, skip_dirs=[DATA, Path(sys.prefix)])

    # ---------- settings ----------
    def settings(self):
        return self._settings.get()

    def set_setting(self, key, value):
        result = self._settings.set(key, value)
        if key == "look" and result["ok"]:
            brand.set_window_icon(result["settings"]["look"])     # the window icon follows the look
            if self._tray:
                self._tray.set_look(result["settings"]["look"])
            if not self._testing:
                threading.Thread(target=brand.follow_look, args=(result["settings"]["look"],), daemon=True).start()   # and the shortcuts / pinned button
        if key == "own_bar" and result["ok"]:
            result["message"] = "Takes effect when Toolbelt starts again (Quit from the tray, then open it)."
        if key == "win_t" and result["ok"] and not self._testing:
            on = result["settings"]["win_t"]
            changed = hotkey.set_windows_wint(off=on)            # Windows' own Win+W follows the switch (his wish, 15 Oct)
            self.win_t(False)
            self.win_t(on)
            result["message"] = ("Win+W opens Toolbelt." if on else "Win+W is Windows' own again.") + \
                (" Windows' setting changed: it counts after Explorer restarts (the button below) or the next sign-in." if changed else "")
        if key == "calc_key" and result["ok"]:
            applied = brand.calc_key(self._calc_command() if result["settings"]["calc_key"] else None)
            if not applied["ok"]:
                self._settings.set("calc_key", False)
                return {"ok": False, "message": applied["message"], "settings": self._settings.get()}
            result["message"] = applied["message"]
        return result

    def _calc_command(self):
        return '"%s" "%s" --open calc-mini' % (launcher(), Path(__file__).resolve())

    def add_to_start_menu(self):
        """Settings > About: a Start-menu shortcut with Toolbelt's icon and its own taskbar identity (so pinning works)."""
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        return brand.start_menu_shortcut(pythonw if pythonw.exists() else sys.executable, Path(__file__).resolve(), self._settings.get()["look"])

    def choose_folder(self):
        """Settings > Save to: Windows' own folder picker."""
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        start = self._settings.get()["save_to"]
        picked = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=start if Path(start).exists() else str(Path.home()))
        if not picked:
            return {"ok": False, "message": "", "settings": self._settings.get()}
        return self._settings.set("save_to", picked[0])

    # ---------- jobs ----------
    def jobs(self):
        return self._jobs.list()

    def cancel_job(self, job_id):
        return self._jobs.cancel(int(job_id))

    def clear_jobs(self):
        return self._jobs.clear_finished()

    def test_job(self, seconds=2):
        """Only for the self-test: a job that just counts, to prove the job list works end to end."""
        if not self._testing:
            return {"ok": False, "message": "Only available in the self-test."}

        def work(job):
            steps = 20
            for i in range(steps):
                job.check()
                time.sleep(float(seconds) / steps)
                job.report((i + 1) * 100 / steps, "Counting")
            return "nothing (test)"

        return {"ok": True, "id": self._jobs.submit("Test job", "Self-test", work).id}

    # ---------- step 2: installing the downloader engines ----------
    def install_engines(self, ids=None):
        """Starts one install job per missing engine (or the ones named). He agreed to yt-dlp, Deno and ffmpeg on 13 Oct."""
        wanted = [i for i in (ids or ["yt-dlp", "deno", "ffmpeg"]) if i in ("yt-dlp", "deno", "ffmpeg", "birefnet", "realesrgan", "whisper", "whispermodel")]
        started = []
        for engine_id in wanted:
            if ids is None and engines.path_of(engine_id):
                continue
            name = {"yt-dlp": "yt-dlp", "deno": "Deno", "ffmpeg": "ffmpeg", "birefnet": "the BiRefNet model", "realesrgan": "Real-ESRGAN", "whisper": "whisper.cpp", "whispermodel": "the Whisper model"}[engine_id]
            job = self._jobs.submit(("Update " if engines.path_of(engine_id) else "Install ") + name, "Engine",
                                    lambda job, e=engine_id: installer.install(job, e), {"engine": engine_id})
            started.append(job.id)
        self._updates = None
        return {"ok": True, "jobs": started, "message": "Installing %d engine%s" % (len(started), "" if len(started) == 1 else "s") if started else "All three are installed."}

    def check_updates(self, force=False):
        if self._updates is None or force:
            self._updates = installer.check_updates()
        return self._updates

    # ---------- step 2: the downloader ----------
    def look_up(self, url):
        try:
            return {"ok": True, "video": downloader.look_up(str(url).strip())}
        except downloader.DownloadError as error:
            return {"ok": False, "message": str(error)}
        except Exception as error:
            return {"ok": False, "message": "Looking it up failed: %s" % error}

    def send_places(self):
        """The "Send to" choices on Downloads, with the real folder behind each one."""
        s = self._settings.get()
        return {"folder": str(Path(s["save_to"]) / ("Downloads" if s["folder_per_tool"] else "")),
                "desktop": shellicon.known_folder("Desktop"),
                "videos": shellicon.known_folder("Videos"), "music": shellicon.known_folder("Music"),
                "spotify": str(music.SPOTIFY_DIR), "custom": s["custom_folder"], "chosen": s["send_to"]}

    def choose_send_folder(self):
        """Downloads > Send to > Pick a folder: Windows' folder picker, remembered for next time."""
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        start = self._settings.get()["custom_folder"]
        picked = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=start if start and Path(start).exists() else str(Path.home()))
        if not picked:
            return {"ok": False, "message": "", "settings": self._settings.get()}
        self._settings.set("custom_folder", picked[0])
        return self._settings.set("send_to", "custom")

    def _send_folder(self, place, mode, audio):
        """Where a download goes. Spotify only takes MP3s; anything else falls back to his Toolbelt folder."""
        p = self.send_places()
        if place == "spotify" and not (mode == "audio" and audio == "mp3"):
            place = "folder"
        if place == "library":
            return Path(p["music"] if mode == "audio" else p["videos"])
        if place == "custom" and not p["custom"]:
            place = "folder"
        return Path(p[place])

    def start_download(self, video_id, mode, height, audio, title, place=None):
        if mode not in ("both", "video", "audio") or audio not in ("mp3", "m4a", "opus"):
            return {"ok": False, "message": "Unknown choice."}
        s = self._settings.get()
        place = place or s["send_to"]
        if place not in ("folder", "desktop", "library", "spotify", "custom"):
            return {"ok": False, "message": "Unknown place."}
        folder = self._send_folder(place, mode, audio)
        self._sent.add(str(folder))

        def work(job):
            path = downloader.download(job, str(video_id), mode, height, audio, folder, s["name_pattern"], s["never_overwrite"], s.get("dl_subs", "off"))
            if folder == music.SPOTIFY_DIR:
                job.extra["spotify"] = path                      # it went straight into the Spotify folder
            elif mode == "audio" and audio == "mp3" and s["auto_spotify"]:
                sent = music.send_to_spotify(path)
                job.extra["spotify"] = sent.get("path") if sent["ok"] else ""
            if s["open_when_done"]:
                subprocess.Popen(["explorer.exe", "/select,", path])
            return path

        job = self._jobs.submit(str(title)[:200] or "Download", "Download", work,
                                {"video_id": str(video_id), "mode": mode, "stage": "Waiting", "folder": str(folder)})
        return {"ok": True, "id": job.id}

    def clipboard_offer(self):
        return self._clip.take_offer()

    def paste(self):
        return self._clip.paste()

    def _allowed(self, path):
        """The page may only touch files in his save folder, the Spotify folder or a folder a download went to, never anywhere else."""
        try:
            target = Path(path).resolve()
        except (OSError, ValueError):
            return None
        for root in [Path(self._settings.get()["save_to"]), music.SPOTIFY_DIR] + [Path(f) for f in self._sent]:
            try:
                if target.is_relative_to(root.resolve()) and target.is_file():
                    return target
            except (OSError, ValueError):
                pass
        return None

    def show_file(self, path):
        target = self._allowed(path)
        if not target:
            return {"ok": False, "message": "That file isn't there any more."}
        subprocess.Popen(["explorer.exe", "/select,", str(target)])
        return {"ok": True, "message": ""}

    def send_to_spotify(self, path):
        target = self._allowed(path)
        return music.send_to_spotify(target) if target else {"ok": False, "message": "That file isn't there any more."}

    def spotify_search(self, query):
        return music.spotify_search(query)

    def songs(self):
        return {"folder": str(music.SPOTIFY_DIR), "songs": music.songs()}

    def write_tags(self, path, values):
        target = self._allowed(path)
        if not target or not isinstance(values, dict):
            return {"ok": False, "message": "That file isn't there any more."}
        return music.write_tags(target, values)

    # ---------- Spotify extras (14 Oct): the cover (framed by hand) and lyrics ----------
    def song_cover(self, path):
        """The song's current cover and whether a YouTube picture can be fetched for it."""
        target = self._allowed(path)
        if not target:
            return {"ok": False, "message": "That file isn't there any more."}
        tags = music.read_tags(target)
        raw = music.cover_bytes(target)
        token = "k%d" % (int(time.time() * 1000) % 10000000)
        self._covers[token] = raw
        return {"ok": True, "token": token, "data": self._data_url(raw), "square": tags.get("square", False), "youtube": bool(tags.get("video_id")),
                "lyrics": tags.get("lyrics", False), "lrc": tags.get("lrc", False), "ttml": str(target.with_suffix(".ttml")) if tags.get("ttml") else "", "lyrics_text": self._lyrics_text(target)}

    def _lyrics_text(self, target):
        try:
            done = subprocess.run([str(music.ffprobe_path()), "-v", "quiet", "-show_entries", "format_tags=lyrics,lyrics-eng", "-of", "json", str(target)],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=music.NO_WINDOW)
            tags = json.loads(done.stdout or "{}").get("format", {}).get("tags", {})
            return next((v for v in tags.values() if v), "")
        except Exception:
            return ""

    def _data_url(self, raw):
        if not raw:
            return ""
        mime = "image/png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))

    def song_cover_from(self, path, source, url=""):
        """A new picture for the cover editor: 'youtube' (the video's picture), 'file' (his PC) or 'link' (a web address)."""
        target = self._allowed(path)
        if not target:
            return {"ok": False, "message": "That file isn't there any more."}
        try:
            if source == "youtube":
                vid = music.read_tags(target).get("video_id", "")
                if not vid:
                    return {"ok": False, "message": "This song doesn't remember which video it came from."}
                raw = music.youtube_picture(vid)
                if not raw:
                    return {"ok": False, "message": "YouTube didn't give a picture for it."}
            elif source == "file":
                if self._window is None:
                    return {"ok": False, "message": "The window isn't ready yet."}
                picked = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Pictures (*.png;*.jpg;*.jpeg;*.webp;*.avif;*.bmp;*.gif)",))
                if not picked:
                    return {"ok": False, "message": ""}
                raw = Path(picked[0]).read_bytes()
            elif source == "link":
                if not str(url).startswith(("http://", "https://")):
                    return {"ok": False, "message": "That isn't a web link (it should start with https://)."}
                raw = music.fetch_bytes(str(url))
            else:
                return {"ok": False, "message": "Unknown source."}
            from PIL import Image
            with Image.open(io.BytesIO(raw)) as img:
                w, h = img.size
        except Exception as error:
            return {"ok": False, "message": "That picture couldn't be used: %s" % str(error)[:120]}
        token = "k%d" % (int(time.time() * 1000) % 10000000)
        self._covers[token] = raw
        while len(self._covers) > 6:
            self._covers.pop(next(iter(self._covers)))
        return {"ok": True, "token": token, "data": self._data_url(raw), "width": w, "height": h}

    def song_cover_save(self, path, token, crop=None):
        target = self._allowed(path)
        raw = self._covers.get(str(token), b"")
        if not target or not raw:
            return {"ok": False, "message": "Pick a picture first."}
        try:
            jpeg = music.crop_square(raw, crop if isinstance(crop, dict) else None)
        except Exception as error:
            return {"ok": False, "message": "That picture couldn't be cropped: %s" % str(error)[:120]}
        result = music.set_cover(target, jpeg)
        if result["ok"]:
            result["data"] = self._data_url(jpeg)
        return result

    def song_suggest_tags(self, path):
        """Fix for lyrics: clean tags proposed from the YouTube-style ones (nothing saved yet)."""
        target = self._allowed(path)
        if not target:
            return {"ok": False, "message": "That file isn't there any more."}
        tags = music.read_tags(target)
        return {"ok": True, "current": {k: tags.get(k, "") for k in ("title", "artist", "album")}, "suggested": music.suggest_tags(tags, target.name), "seconds": tags.get("seconds", 0)}

    def song_lrclib_check(self, title, artist, album, seconds):
        """The same LRCLIB lookup lyrics-plus does, plus entries that would match (only on his button)."""
        return music.lrclib_check(str(title), str(artist), str(album), float(seconds or 0))

    def song_lyrics_find(self, path):
        target = self._allowed(path)
        if not target:
            return {"ok": False, "message": "That file isn't there any more."}
        tags = music.read_tags(target)
        title = re.sub(r"\s*[\(\[【].*?[\)\]】]\s*", " ", tags.get("title") or target.stem).strip()        # "(Official Video)" and friends confuse the search
        title = re.split(r"\s+[/／|｜]\s+|\s+-\s+", title)[0].strip() or title
        return music.lyrics_find(title, tags.get("artist", ""), tags.get("seconds", 0))

    def song_lyrics_save(self, path, plain, synced=""):
        target = self._allowed(path)
        if not target:
            return {"ok": False, "message": "That file isn't there any more."}
        return music.set_lyrics(target, str(plain or ""), str(synced or ""))

    def songs_fix_all(self):
        """Fix all songs (15 Oct): one job that asks LRCLIB about every song and proposes tags. Nothing is saved yet:
        the page shows the list and he saves the ones he ticks (songs_fix_apply)."""
        def work(job):
            listing = music.songs()
            out = []
            for i, tags in enumerate(listing):
                job.check()
                job.report(i * 100 / max(len(listing), 1), "Asking LRCLIB about %s (%d of %d)" % (tags.get("title") or tags.get("name"), i + 1, len(listing)))
                out.append(music.fix_one(tags, tags.get("name", ""), wait=lambda sec: (job.check(), time.sleep(sec))))
                job.extra["done"] = len(out)
                time.sleep(0.6)
            job.report(100, "%d of %d songs can be found by lyrics-plus" % (sum(1 for x in out if x["status"] != "none"), len(out)))
            return out
        job = self._jobs.submit("Fix all songs for lyrics", "Songs", work, {"done": 0})
        return {"ok": True, "job": job.id}

    def songs_fix_apply(self, items, lyrics=False):
        """Saves the ticked proposals: [{path, title, artist, album}]. With lyrics, also puts the words inside each song."""
        if not isinstance(items, list) or not items:
            return {"ok": False, "message": "Nothing ticked."}
        def work(job):
            saved, failed = 0, []
            for i, it in enumerate(items):
                job.check()
                target = self._allowed(str(it.get("path", "")))
                job.report(i * 100 / len(items), "Saving %d of %d" % (i + 1, len(items)))
                if not target:
                    failed.append(str(it.get("path", "")).split(chr(92))[-1])
                    continue
                r = music.write_tags(target, {k: str(it.get(k, "")) for k in ("title", "artist", "album")})
                if not r.get("ok"):
                    failed.append(target.name)
                    continue
                saved += 1
                if lyrics:
                    tags = music.read_tags(target)
                    found = music.lyrics_find(tags.get("title", ""), tags.get("artist", ""), tags.get("seconds", 0))
                    if found.get("ok") and (found.get("plain") or found.get("synced")):
                        music.set_lyrics(target, found.get("plain", ""), found.get("synced", ""))
                    time.sleep(0.6)
            job.report(100, "Saved %d song%s%s" % (saved, "" if saved == 1 else "s", (", %d failed" % len(failed)) if failed else ""))
            return {"saved": saved, "failed": failed}
        job = self._jobs.submit("Save fixed song tags", "Songs", work)
        return {"ok": True, "job": job.id}

    def open_spotify_folder(self):
        music.SPOTIFY_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(music.SPOTIFY_DIR)])
        return {"ok": True, "message": "Opened Music\\Toolbelt for Spotify"}

    # ---------- step 3: cut-outs ----------
    def cut_pick(self):
        """Windows' own file picker for a picture."""
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Pictures (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif;*.tif;*.tiff)",))
        if not picked:
            return {"ok": False, "message": ""}
        return self._cut_start(picked[0], Path(picked[0]).stem)

    def cut_paste(self):
        img = clipboard.grab_image()
        if img is None:
            return {"ok": False, "message": "There's no picture on the clipboard. Copy one (or take a screenshot) first."}
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return self._cut_start(buf.getvalue(), "pasted picture")

    def cut_data(self, name, data_b64):
        """A picture dropped on the page (the page reads the file and sends its bytes)."""
        try:
            raw = base64.b64decode(str(data_b64).split(",", 1)[-1], validate=False)
        except Exception:
            return {"ok": False, "message": "That file couldn't be read."}
        if len(raw) > 60 * 1024 * 1024:
            return {"ok": False, "message": "That picture is bigger than 60 MB."}
        return self._cut_start(raw, Path(str(name)).stem or "picture")

    def _cut_start(self, source, name):
        try:
            img = cutout.open_picture(source)
        except cutout.CutError as error:
            return {"ok": False, "message": str(error)}
        token = "c%d" % (len(self._cuts) + int(time.time() * 1000) % 100000)

        def work(job):
            if not engines.path_of("birefnet"):
                raise cutout.CutError("Install the BiRefNet model first (the button on this page).")
            job.report(10, "Loading the model (only the first time)" if not cutout.device() else "Cutting out")
            cutout.session()
            job.report(40, "Cutting out on the " + cutout.device())
            result, seconds, device = cutout.cut(img)
            self._cuts[token] = {"name": safe_stem(name), "original": img, "cutout": result, "bg": "none", "colour": "#FFFFFF",
                                 "picture": None, "outline": 0, "shadow": False, "seconds": seconds, "device": device}
            while len(self._cuts) > 8:                       # keep memory in check: only the newest 8 stay
                self._cuts.pop(next(iter(self._cuts)))
            job.extra.update({"token": token, "seconds": round(seconds, 1), "device": device})
            return token

        job = self._jobs.submit("Cut out " + safe_stem(name), "Cut out", work, {"token": token})
        return {"ok": True, "id": job.id, "token": token, "before": cutout.preview(img)}

    def _cut_final(self, c):
        if c["bg"] == "none":
            return cutout.sticker(c["cutout"], c["outline"], c["shadow"])
        return cutout.compose(c["cutout"], c["original"], c["bg"], c["colour"], c["picture"])

    def cut_result(self, token):
        c = self._cuts.get(token)
        if not c:
            return {"ok": False, "message": "That cut-out is gone; open the picture again."}
        return {"ok": True, "token": token, "name": c["name"], "before": cutout.preview(c["original"]), "after": cutout.preview(self._cut_final(c)),
                "width": c["original"].width, "height": c["original"].height, "seconds": round(c["seconds"], 1), "device": c["device"],
                "options": {k: c[k] for k in ("bg", "colour", "outline", "shadow")}}

    def cut_set(self, token, options):
        c = self._cuts.get(token)
        if not c or not isinstance(options, dict):
            return {"ok": False, "message": "That cut-out is gone; open the picture again."}
        if options.get("bg") in ("none", "white", "colour", "blur", "picture"):
            if options["bg"] == "picture" and c["picture"] is None:
                return {"ok": False, "message": "Choose a picture first."}
            c["bg"] = options["bg"]
        if isinstance(options.get("colour"), str) and len(options["colour"]) == 7 and options["colour"].startswith("#"):
            c["colour"] = options["colour"]
        if "outline" in options:
            c["outline"] = max(0, min(30, int(options["outline"] or 0)))
        if "shadow" in options:
            c["shadow"] = bool(options["shadow"])
        return {"ok": True, "after": cutout.preview(self._cut_final(c)), "options": {k: c[k] for k in ("bg", "colour", "outline", "shadow")}}

    def cut_background_picture(self, token):
        c = self._cuts.get(token)
        if not c or self._window is None:
            return {"ok": False, "message": "That cut-out is gone; open the picture again."}
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Pictures (*.png;*.jpg;*.jpeg;*.webp;*.bmp)",))
        if not picked:
            return {"ok": False, "message": ""}
        try:
            c["picture"] = cutout.open_picture(picked[0])
        except cutout.CutError as error:
            return {"ok": False, "message": str(error)}
        return self.cut_set(token, {"bg": "picture"})

    def _cut_folder(self):
        s = self._settings.get()
        return Path(s["save_to"]) / ("Cut-outs" if s["folder_per_tool"] else "")

    def cut_save(self, token):
        c = self._cuts.get(token)
        if not c:
            return {"ok": False, "message": "That cut-out is gone; open the picture again."}
        target = cutout.free_path(self._cut_folder(), c["name"] + " - cut out")
        target.write_bytes(cutout.png_bytes(self._cut_final(c)))
        if self._settings.get()["open_when_done"]:
            subprocess.Popen(["explorer.exe", "/select,", str(target)])
        return {"ok": True, "message": "Saved " + target.name, "path": str(target)}

    def cut_copy(self, token, kind=""):
        c = self._cuts.get(token)
        if not c:
            return {"ok": False, "message": "That cut-out is gone; open the picture again."}
        from PIL import Image
        if kind in cutout.DISCORD:
            png = cutout.discord_png(cutout.sticker(c["cutout"], c["outline"], c["shadow"]), kind)
            img = Image.open(io.BytesIO(png)).convert("RGBA")
        else:
            img = self._cut_final(c)
            png = cutout.png_bytes(img, optimize=False)
        flat = Image.new("RGBA", img.size, (255, 255, 255, 255))
        flat.alpha_composite(img)
        bmp = io.BytesIO()
        flat.convert("RGB").save(bmp, "BMP")
        if not clipboard.copy_image(png, bmp.getvalue()):
            return {"ok": False, "message": "Another program is holding the clipboard; try again."}
        return {"ok": True, "message": "Copied: paste it into Discord, Word or Paint (Ctrl+V)."}

    def cut_discord(self, token):
        """Saves the Discord emoji (128), sticker (320) and server icon (512) as see-through PNGs."""
        c = self._cuts.get(token)
        if not c:
            return {"ok": False, "message": "That cut-out is gone; open the picture again."}
        base = cutout.sticker(c["cutout"], c["outline"], c["shadow"])
        folder, paths = self._cut_folder(), []
        for kind, label in (("emoji", "emoji 128"), ("sticker", "sticker 320"), ("icon", "server icon 512")):
            target = cutout.free_path(folder, "%s - %s" % (c["name"], label))
            target.write_bytes(cutout.discord_png(base, kind))
            paths.append(str(target))
        if self._settings.get()["open_when_done"]:
            subprocess.Popen(["explorer.exe", "/select,", paths[0]])
        return {"ok": True, "message": "Saved the emoji, sticker and server icon.", "paths": paths}

    # ---------- step 4: Home ----------
    def _project(self, app_id):
        return next((p for p in apps.projects() if p["id"] == app_id), None)

    def home(self):
        """His projects (progress and Next up straight from their notes) and the Windows apps he added, with icons."""
        data = apps.load()
        projects = apps.projects()
        for p in projects:
            o = p.get("open") or {}
            if o.get("icon"):                                   # an icon file the project names itself
                target = str(Path(p["folder"]) / o["icon"])
            elif "exe" in o:
                target = os.path.expandvars(o["exe"])
            elif "file" in o:
                target = str(Path(p["folder"]) / os.path.expandvars(o["file"]))
            else:                                               # Python apps and scripts: the project folder's own icon
                target = p["folder"]
            p["icon"] = picture_icon(p["icon_file"]) if p.get("icon_file") and Path(p["icon_file"]).is_file() else                 shellicon.icon(target if Path(target).exists() else p["folder"], 64)
            if p["icon"] == shellicon.icon(str(DATA), 64):     # just Windows' plain yellow folder: the page shows a letter instead
                p["icon"] = ""
            p["can_open"] = bool(p.get("open")) or p["self"]
            p["has_settings"] = bool(p.get("settings")) or p["self"]
        added = []
        for a in data["added"]:
            entry = dict(a)
            entry["icon"] = shellicon.icon(a["target"], 64) if a["kind"] != "url" else ""
            entry["missing"] = a["kind"] != "url" and not Path(a["target"]).exists()
            added.append(entry)
        return {"projects": projects, "added": added, "vscode": bool(apps.vscode()), "root": str(apps.ROOT)}

    def home_open(self, app_id):
        p = self._project(app_id)
        if p:
            if p["self"]:
                return {"ok": True, "message": "You're already in it."}
            if not p.get("open"):
                return {"ok": False, "message": p.get("note") or "Toolbelt doesn't know how to open this one yet: right-click → Change how it opens."}
            result = apps.run(p["open"], p["folder"])
            if result["ok"]:
                result["message"] = "Opening %s. %s" % (p["name"], p.get("hint", "")) if p.get("hint") else "Opening %s…" % p["name"]
            return result
        a = next((x for x in apps.load()["added"] if x["id"] == app_id), None)
        return apps.open_added(a) if a else {"ok": False, "message": "That app isn't on Home any more."}

    def home_settings(self, app_id):
        p = self._project(app_id)
        if not p:
            return {"ok": False, "message": "That app isn't on Home any more."}
        if p["self"]:
            return {"ok": True, "message": "", "go": "settings"}
        if not p.get("settings"):
            return {"ok": False, "message": p.get("note") or (p["name"] + " has no settings of its own.")}
        result = apps.run(p["settings"], p["folder"])
        if result["ok"] and p.get("settings_hint"):
            result["message"] = p["settings_hint"]
        return result

    def home_folder(self, app_id):
        p = self._project(app_id)
        if p:
            subprocess.Popen(["explorer.exe", p["folder"]])
            return {"ok": True, "message": ""}
        a = next((x for x in apps.load()["added"] if x["id"] == app_id), None)
        if a and a["kind"] != "url" and Path(a["target"]).exists():
            subprocess.Popen(["explorer.exe", "/select,", a["target"]])
            return {"ok": True, "message": ""}
        return {"ok": False, "message": "There's no folder to show."}

    def home_code(self, app_id):
        p = self._project(app_id)
        return apps.open_in_vscode(p["folder"]) if p else {"ok": False, "message": "That app isn't on Home any more."}

    def home_notes(self, app_id):
        p = self._project(app_id)
        if not p or not p["status"]:
            return {"ok": False, "message": "It has no status notes."}
        code = apps.vscode()
        target = str(Path(p["folder"]) / p["status"])
        if code:
            subprocess.Popen([code, p["folder"], target], creationflags=0x00000008)
        else:
            os.startfile(target)
        return {"ok": True, "message": "Opening its notes"}

    def home_change(self, app_id, which):
        """Change how a project opens (or where its settings are): pick a program, shortcut, script or file."""
        p = self._project(app_id)
        if not p or which not in ("open", "settings") or self._window is None:
            return {"ok": False, "message": "That app isn't on Home any more."}
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, directory=p["folder"],
                                                 file_types=("Programs and files (*.exe;*.lnk;*.cmd;*.bat;*.ps1;*.html;*.json;*.ini;*.txt;*.md)", "All files (*.*)"))
        if not picked:
            return {"ok": False, "message": ""}
        f = picked[0]
        action = {"ps1": f} if f.lower().endswith(".ps1") else {"exe": f} if f.lower().endswith(".exe") else {"file": f}
        data = apps.load()
        data["overrides"].setdefault(app_id, {})[which] = action
        apps.save(data)
        return {"ok": True, "message": ("Opens with " if which == "open" else "Settings: ") + Path(f).name}

    def home_reset(self, app_id):
        data = apps.load()
        data["overrides"].pop(app_id, None)
        apps.save(data)
        return {"ok": True, "message": "Back to how Toolbelt opens it by default."}

    def home_hide(self, app_id, hidden):
        data = apps.load()
        data["hidden"] = [h for h in data["hidden"] if h != app_id] + ([app_id] if hidden else [])
        apps.save(data)
        return {"ok": True, "message": "Hidden from Home" if hidden else "Back on Home"}

    def start_menu(self):
        items = apps.start_menu()
        for item in items:
            item["icon"] = shellicon.icon(item["path"], 32)
        return items

    def home_add(self, kind, target, name="", group=""):
        return apps.add(kind, target, name, group)

    def home_add_many(self, paths):
        added = [apps.add("lnk", p)["ok"] for p in (paths or [])[:50]]
        return {"ok": any(added), "message": "Added %d app%s" % (sum(added), "" if sum(added) == 1 else "s")}

    def home_add_exe(self):
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Programs (*.exe;*.lnk)",))
        if not picked:
            return {"ok": False, "message": ""}
        return apps.add("lnk" if picked[0].lower().endswith(".lnk") else "exe", picked[0])

    def home_remove(self, app_id):
        return apps.remove(app_id)

    # ---------- step 5: Colours ----------
    def copy_text(self, text):
        ok = clipboard.copy_text(str(text)[:100000])
        return {"ok": ok, "message": "Copied" if ok else "Another program is holding the clipboard; try again."}

    def colours(self):
        return colours.load()

    def colours_save(self, name, stops):
        return colours.save_gradient(name, stops)

    def colours_delete(self, index):
        return colours.delete_gradient(index)

    def colours_remember(self, state):
        return colours.remember(state)

    def colours_from_picture(self):
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Pictures (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif)",))
        if not picked:
            return {"ok": False, "message": ""}
        try:
            return {"ok": True, "colours": colours.picture_palette(picked[0]), "name": Path(picked[0]).stem}
        except Exception:
            return {"ok": False, "message": "That picture couldn't be read."}

    # ---------- engines and the PC ----------
    def engines(self):
        return engines.list_engines()

    def gpus(self):
        return engines.gpus()

    def info(self):
        return {"version": VERSION, "data": str(DATA),
                "logos": {look: brand.svg(look, 22) for look in brand.LOOKS}}

    def open_folder(self, which):
        """Opens one of Toolbelt's own folders in Explorer (only these, never a path the page makes up)."""
        folders = {"engines": engines.ENGINES_DIR, "data": DATA, "save": Path(self._settings.get()["save_to"]), "quarantine": appguard.QUARANTINE}
        if which not in folders:
            return {"ok": False, "message": "Unknown folder."}
        folder = folders[which]
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(folder)])
        return {"ok": True, "message": "Opened " + str(folder)}

    # ---------- step 6: pictures & video ----------
    def _media_add(self, path):
        path = Path(str(path))
        if not path.is_file():
            return {"ok": False, "message": "That file isn't there."}
        token = media.unique_key(path)
        self._media[token] = str(path)
        info = media.probe(path)
        info.update({"token": token, "thumb": media.thumbnail(path) if info["kind"] in ("video", "picture", "gif") else ""})
        info.pop("path", None)                                   # the page works with tokens, never with paths
        return {"ok": True, "file": info}

    def _media_path(self, token):
        path = self._media.get(str(token))
        if not path or not Path(path).is_file():
            raise media.MediaError("That file is gone; pick it again.")
        return Path(path)

    def media_pick(self):
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, directory=str(media.media_root("Videos")), file_types=(
            "Videos sound and pictures (*.mp4;*.mkv;*.webm;*.mov;*.avi;*.m4v;*.ts;*.gif;*.mp3;*.m4a;*.wav;*.opus;*.ogg;*.flac;*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.avif;*.tif;*.tiff;*.ico;*.heic;*.heif)", "All files (*.*)"))
        if not picked:
            return {"ok": False, "message": ""}
        return self._media_add(picked[0])

    def media_drop(self, path):
        """A file dropped on the window: pywebview tells the page its full path."""
        return self._media_add(path)

    def media_folder(self):
        return str(media.save_folder(self._settings.get()))

    def media_info(self, token):
        try:
            return self._media_add(self._media_path(token))
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}

    def media_estimate(self, token, target_mb, start=0, end=0):
        try:
            return {"ok": True, "plan": media.plan_compress(media.probe(self._media_path(token)), float(target_mb), float(start or 0), float(end or 0))}
        except (media.MediaError, ValueError) as error:
            return {"ok": False, "message": str(error)}

    def media_picture_preview(self, token, fmt, quality, lossless=False):
        """Compress picture: how big it would get and what it would look like, without saving anything."""
        try:
            path = self._media_path(token)
            if fmt not in media.PICTURE_OUT:
                return {"ok": False, "message": "Unknown format."}
            out = media.compress_picture(path, fmt, int(quality), None, bool(lossless))
            if token not in self._media_before:
                self._media_before[token] = media.preview_data(media.open_picture(path))
                while len(self._media_before) > 6:
                    self._media_before.pop(next(iter(self._media_before)))
            out.update({"ok": True, "before": self._media_before[token], "original": path.stat().st_size})
            return out
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}
        except Exception as error:
            return {"ok": False, "message": "That didn't work: %s" % error}

    def media_video_plan(self, token, scale, start=0, end=0):
        try:
            return {"ok": True, "plan": upscale.plan_video(media.probe(self._media_path(token)), int(scale), float(start or 0), float(end or 0))}
        except (media.MediaError, ValueError) as error:
            return {"ok": False, "message": str(error)}

    # ---------- playing videos inside Toolbelt (viewer.py): the player, cutting while watching, before / after ----------
    def _play_url(self, path):
        if self._window is None:
            raise OSError("The window isn't ready yet.")
        return viewer.url(self._window, path)

    def media_url(self, token):
        """Where the page plays this file from (its folder mapped privately inside the window; no server)."""
        try:
            path = self._media_path(token)
            proxy = media.preview_copy(path, make=False)          # a playable copy made earlier, if the original wasn't
            return {"ok": True, "url": self._play_url(proxy or path), "proxy": bool(proxy), "name": path.name}
        except (media.MediaError, OSError) as error:
            return {"ok": False, "message": str(error)}

    def media_proxy(self, token):
        """The original won't play in Toolbelt (an unusual codec): make a light H.264 copy once, in AppData (a job)."""
        try:
            path = self._media_path(token)
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}

        def work(job):
            job.report(5, "Making a copy Toolbelt can play")
            out = media.preview_copy(path, make=True, job=job)
            job.extra["url"] = self._play_url(out)
            return str(out)

        job = self._jobs.submit("Playable copy · %s" % path.name[:60], "Preview", work, {"token": str(token)})
        return {"ok": True, "id": job.id}

    def media_compare(self, job_id):
        """Before / after of a finished media job: the original and the result, both playable, with their facts."""
        job = next((j for j in self._jobs.list() if j["id"] == int(job_id)), None)
        if not job or job["state"] != "done" or not job["extra"].get("path"):
            return {"ok": False, "message": "That job isn't finished."}
        try:
            before, after = self._media_path(job["extra"].get("token")), Path(job["extra"]["path"])
            facts = []
            for p in (before, after):
                info = media.probe(p) if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".avif", ".bmp") else {}
                w, h = (info.get("width"), info.get("height")) if info.get("width") else media.picture_size(p)
                facts.append({"url": self._play_url(media.preview_copy(p, make=False) or p), "size": p.stat().st_size, "width": w, "height": h,
                              "name": p.name})
        except (media.MediaError, OSError) as error:
            return {"ok": False, "message": str(error)}
        kind = "video" if after.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov", ".m4v") else "picture"
        return {"ok": True, "kind": kind, "before": facts[0], "after": facts[1], "start": float(job["extra"].get("start") or 0),
                "action": job["extra"].get("action", "")}

    def upscale_models(self):
        return {"installed": bool(engines.path_of("realesrgan")), "models": upscale.models()}

    def media_job(self, token, action, options=None):
        """Starts one piece of media work as a job. `action` says which; `options` the choices made on the page."""
        o = options if isinstance(options, dict) else {}
        try:
            src = self._media_path(token)
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}
        s = self._settings.get()
        folder = media.save_folder(s)
        f = lambda key, default=0.0: float(o.get(key, default) or 0)                     # noqa: E731
        start, end = f("start"), f("end")
        titles = {"convert": "Convert", "compress": "Compress video", "discord": "Fit for Discord", "clip": "GIF / WebM", "trim": "Trim",
                  "icomp": "Compress picture", "resize": "Resize", "format": "Picture format", "upscale": "Upscale", "sharpen_gif": "Sharpen GIF", "upscale_video": "Upscale video",
                  "crop": "Crop", "cutsound": "Cut sound", "normalise": "Even out loudness", "subs": "Subtitles"}
        if action not in titles:
            return {"ok": False, "message": "Unknown action."}
        if action in ("upscale", "sharpen_gif", "upscale_video") and not engines.path_of("realesrgan"):
            return {"ok": False, "message": "Install Real-ESRGAN first (the button on this page)."}
        if action == "subs" and not (engines.path_of("whisper") and engines.path_of("whispermodel")):
            return {"ok": False, "message": "Install whisper.cpp and the Whisper model first (the button on this page)."}

        def work(job):
            if action == "convert":
                dest = media.convert(job, src, str(o.get("fmt", "mp4")), folder)
            elif action == "compress":
                dest = media.compress(job, src, float(o.get("target", 10)), folder, start, end)
            elif action == "discord":
                dest = media.compress(job, src, 10, folder, start, end)
            elif action == "clip":
                dest = media.clip(job, src, str(o.get("kind", "gif")), folder, start, end, int(o.get("width", 480)), int(o.get("fps", 15)), str(o.get("dither", "bayer")))
            elif action == "trim":
                if end <= start:
                    raise media.MediaError("Pick a piece first (From and To).")
                dest = media.trim(job, src, folder, start, end)
            elif action == "icomp":
                job.report(30, "Compressing")
                dest = media.compress_picture(src, str(o.get("fmt", "webp")), int(o.get("quality", 80)), folder, bool(o.get("lossless")))["path"]
            elif action == "resize":
                job.report(30, "Resizing")
                dest = media.resize_picture(src, str(o.get("preset", "half")), folder, int(o.get("width", 0) or 0), int(o.get("height", 0) or 0),
                                            bool(o.get("keep", True)), bool(o.get("pixel")), str(o.get("fmt", "")))["path"]
            elif action == "format":
                job.report(30, "Converting")
                dest = media.picture_format(src, str(o.get("fmt", "png")), folder, int(o.get("quality", 90)))["path"]
            elif action == "crop":
                job.report(30, "Cropping")
                r = media.crop_picture(src, o.get("box") if isinstance(o.get("box"), dict) else str(o.get("ratio", "1:1")), folder, str(o.get("fmt", "")))
                dest = r["path"]
                job.extra.update(width=r["width"], height=r["height"])
            elif action == "cutsound":
                dest = media.cut_sound(job, src, folder, start, end, f("fade_in"), f("fade_out"))
            elif action == "normalise":
                dest, before, after = media.normalise(job, src, folder, str(o.get("target", "spotify")))
                job.extra.update(before=round(before, 1), after=after)
            elif action == "subs":
                dest, srt = media.subtitles(job, src, folder, str(o.get("lang", "auto")), bool(o.get("translate")), str(o.get("put", "srt")))
                job.extra["srt"] = srt
            elif action == "upscale":
                dest = upscale.upscale_picture(job, src, int(o.get("scale", 2)), str(o.get("model", "realesrgan-x4plus")), folder)
            elif action == "sharpen_gif":
                dest = upscale.sharpen_gif(job, src, int(o.get("scale", 2)), str(o.get("out", "webp")), folder, str(o.get("dither", "bayer")))
            else:
                dest = upscale.upscale_video(job, src, int(o.get("scale", 2)), str(o.get("model", "realesr-animevideov3")), folder, start, end)
            self._sent.add(str(Path(dest).parent))
            job.extra["path"] = dest
            job.extra.setdefault("size", Path(dest).stat().st_size)
            if s["open_when_done"]:
                subprocess.Popen(["explorer.exe", "/select,", dest])
            return dest

        job = self._jobs.submit("%s · %s" % (titles[action], src.name[:60]), "Media", work, {"token": str(token), "action": action, "start": start})
        return {"ok": True, "id": job.id}

    # ---------- Handy tools (15 Oct): QR codes and renaming many files ----------
    def qr_preview(self, kind, values, level="m", dark="#000000", light="#FFFFFF"):
        try:
            r = qrmaker.preview(str(kind), values, str(level), str(dark), str(light))
        except (ValueError, segno_error()) as error:
            return {"ok": False, "message": str(error)}
        r["readable"] = qrmaker.contrast_ok(str(dark), str(light))
        return r

    def qr_save(self, kind, values, level="m", dark="#000000", light="#FFFFFF", fmt="png"):
        """Saves the code as PNG (big, 20 px per square) or SVG (sharp at any size) in his save folder."""
        try:
            qr = qrmaker.make(str(kind), values, str(level))
        except (ValueError, segno_error()) as error:
            return {"ok": False, "message": str(error)}
        svg, png = qrmaker.render(qr, str(dark), str(light), 20)
        name = re.sub(r"[^\w\- ]+", " ", str((values or {}).get("ssid") or (values or {}).get("name") or (values or {}).get("text") or "code"))
        name = re.sub(r"\s+", " ", name).strip()[:40] or "code"
        folder = Path(self._settings.get()["save_to"])
        dest = media.out_path(folder, "QR - " + name, "." + ("svg" if fmt == "svg" else "png"))
        dest.write_bytes(svg.encode("utf-8") if fmt == "svg" else png)
        self._sent.add(str(dest.parent))
        return {"ok": True, "path": str(dest), "message": "Saved %s" % dest.name}

    def qr_copy(self, kind, values, level="m", dark="#000000", light="#FFFFFF"):
        try:
            qr = qrmaker.make(str(kind), values, str(level))
        except (ValueError, segno_error()) as error:
            return {"ok": False, "message": str(error)}
        _svg, png = qrmaker.render(qr, str(dark), str(light) or "#FFFFFF", 12)
        from PIL import Image
        bmp = io.BytesIO()
        Image.open(io.BytesIO(png)).convert("RGB").save(bmp, "BMP")
        if not clipboard.copy_image(png, bmp.getvalue()):
            return {"ok": False, "message": "Another program is holding the clipboard; try again."}
        return {"ok": True, "message": "Copied: paste it into Discord, Word or Paint (Ctrl+V)."}

    def rename_pick(self, what="files"):
        """The files to rename: several from a folder (Ctrl / Shift), or everything in one folder (not its subfolders)."""
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        if what == "folder":
            picked = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if not picked:
                return {"ok": False, "message": ""}
            paths = sorted((p for p in Path(picked[0]).iterdir() if p.is_file() and not p.name.startswith(".tb-rename-")), key=lambda p: p.name.lower())
        else:
            picked = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
            if not picked:
                return {"ok": False, "message": ""}
            paths = sorted((Path(p) for p in picked), key=lambda p: p.name.lower())
        self._rename = [str(p) for p in paths][:2000]
        return {"ok": True, "count": len(self._rename)}

    def rename_order(self, how):
        """Numbering follows this order: name, date changed or size."""
        files = [Path(p) for p in getattr(self, "_rename", []) if Path(p).exists()]
        key = {"name": lambda p: p.name.lower(), "date": lambda p: p.stat().st_mtime, "size": lambda p: p.stat().st_size}.get(str(how))
        if key:
            self._rename = [str(p) for p in sorted(files, key=key)]
        return {"ok": True}

    def rename_plan(self, rules):
        paths = [p for p in getattr(self, "_rename", []) if Path(p).exists()]
        try:
            items = renamer.plan(paths, rules if isinstance(rules, dict) else {})
        except Exception as error:
            return {"ok": False, "message": str(error)[:160], "items": []}
        self._rename_plan = items
        return {"ok": True, "items": [{k: it[k] for k in ("old", "new", "problem")} for it in items[:400]], "count": len(items),
                "changes": sum(1 for it in items if it["old"] != it["new"] and not it["problem"]), "problems": sum(1 for it in items if it["problem"]),
                "folder": str(Path(paths[0]).parent) if paths else "", "undo": renamer.can_undo()}

    def rename_apply(self, rules):
        plan = self.rename_plan(rules)
        if not plan["ok"]:
            return plan
        result = renamer.apply(self._rename_plan)
        if result["ok"]:
            back = {old: new for old, new in result["renamed"]}
            self._rename = [back.get(p, p) for p in self._rename]
        return result

    def rename_undo(self):
        result = renamer.undo()
        if result["ok"]:
            back = dict(result["renamed"])                              # undo's own pairs: [current name, restored name]
            self._rename = [back.get(p, p) for p in getattr(self, "_rename", [])]
        return result

    # ---------- many pictures at once (15 Oct) ----------
    def media_pick_many(self, what="files"):
        """Several pictures (Ctrl / Shift in the picker) or every picture in one folder."""
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        if what == "folder":
            picked = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=str(media.media_root("Pictures")))
            if not picked:
                return {"ok": False, "message": ""}
            paths = sorted(p for p in Path(picked[0]).iterdir() if p.is_file() and media.kind_of(p) == "picture")
        else:
            picked = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, directory=str(media.media_root("Pictures")),
                                                     file_types=("Pictures (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.avif;*.tif;*.tiff;*.heic;*.heif)",))
            if not picked:
                return {"ok": False, "message": ""}
            paths = [Path(p) for p in picked if media.kind_of(p) == "picture"]
        return self._batch_add(paths)

    def _batch_add(self, paths):
        paths = [Path(p) for p in paths][:500]
        if not paths:
            return {"ok": False, "message": "No pictures there."}
        items = []
        for p in paths:
            token = media.unique_key(p)
            self._media[token] = str(p)
            items.append({"token": token, "name": p.name, "size": p.stat().st_size})
        return {"ok": True, "items": items}

    def media_batch_thumb(self, token):
        try:
            return media.thumbnail(self._media_path(token), 0, 160)
        except media.MediaError:
            return ""

    def media_batch(self, tokens, action, options=None):
        o = options if isinstance(options, dict) else {}
        if action not in media.BATCH_ACTIONS:
            return {"ok": False, "message": "Unknown action."}
        try:
            paths = [str(self._media_path(t)) for t in (tokens or [])]
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}
        if not paths:
            return {"ok": False, "message": "Pick some pictures first."}
        s = self._settings.get()
        folder = media.save_folder(s)

        def work(job):
            r = media.batch_pictures(job, paths, action, o, folder)
            self._sent.add(r["folder"])
            job.extra.update(path=r["first"], folder=r["folder"], size=r["after"], before=r["before"], count=r["done"], failed=r["failed"])
            if s["open_when_done"]:
                os.startfile(r["folder"])
            return r["folder"]
        job = self._jobs.submit("%s · %d pictures" % (media.BATCH_ACTIONS[action], len(paths)), "Media", work, {"action": "batch"})
        return {"ok": True, "id": job.id}

    def media_clips(self, refresh=False):
        """His game recordings (ReLive, Game Bar, …), newest first; each gets a token so the tools can work on it."""
        if refresh or self._clips is None or time.time() - self._clips_at > 120:
            found = media.game_clips()
            for c in found:
                c["token"] = media.unique_key(c["path"])
                self._media[c["token"]] = c["path"]
                c.pop("path", None)
            self._clips, self._clips_at = found, time.time()
        return self._clips

    def media_clip_thumb(self, token):
        try:
            return {"ok": True, "thumb": media.thumbnail(self._media_path(token), 1.0, 320)}
        except media.MediaError:
            return {"ok": False, "thumb": ""}

    def cut_token(self, token):
        """Media > a picture > Cut out: hands the file to the cut-out tool."""
        try:
            path = self._media_path(token)
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}
        return self._cut_start(str(path), path.stem)

    # ---------- step 9: PC care (uninstaller, startup; drivers and ping come next) ----------
    def pc_programs(self, refresh=False):
        if refresh or self._programs is None:
            found = pccare.programs()
            for p in found:
                p["icon_data"] = shellicon.icon(p["icon"], 32) if p["icon"] else ""
            self._programs = found
        return self._programs

    def _prog(self, program_id):
        return next((p for p in (self._programs or []) if p["id"] == program_id), None)

    def pc_run(self, program_id):
        """Run: starts the program itself (its install folder's main program, or the icon's program)."""
        program = self._prog(program_id)
        exe = program and program.get("icon")
        if not exe or not exe.lower().endswith(".exe") or not Path(exe).exists():
            return {"ok": False, "message": "Toolbelt doesn't know which program file to start for this one."}
        subprocess.Popen([exe], cwd=str(Path(exe).parent))
        return {"ok": True, "message": "Starting " + program["name"]}

    def pc_open_location(self, program_id):
        program = self._prog(program_id)
        where = program and (program.get("location") or (Path(program["icon"]).parent if program.get("icon") else ""))
        if not where or not Path(str(where)).is_dir():
            return {"ok": False, "message": "Toolbelt doesn't know this program's folder."}
        subprocess.Popen(["explorer.exe", str(where)])
        return {"ok": True, "message": "Opened " + str(where)}

    def pc_program_action(self, program_id, action):
        """The right-click menu: search online, its About / Help / Update link, its registry key in Regedit."""
        program = self._prog(program_id) or next((a for a in (self._store or []) if a["id"] == program_id), None)
        if not program:
            return {"ok": False, "message": "That program isn't in the list any more."}
        if action == "google":
            webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(program["name"]))
            return {"ok": True, "message": "Searching the web for " + program["name"]}
        if action in ("about", "help", "update"):
            url = program.get(action) or ""
            if not url.lower().startswith(("http://", "https://")):
                return {"ok": False, "message": "This program has no such link."}
            webbrowser.open(url)
            return {"ok": True, "message": "Opened its link."}
        if action == "regedit" and program.get("key"):
            # Regedit opens at the key it last showed: set that first. Windows asks for admin for Regedit itself.
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Applets\Regedit") as k:
                winreg.SetValueEx(k, "LastKey", 0, winreg.REG_SZ, "Computer\\" + program["key"])
            try:
                os.startfile("regedit.exe")
            except OSError as error:
                return {"ok": False, "message": "Regedit didn't start: %s" % error}
            return {"ok": True, "message": "Regedit opens at its key (if Regedit was already open, close it first)."}
        if action == "data" and program.get("data"):
            subprocess.Popen(["explorer.exe", program["data"]])
            return {"ok": True, "message": "Opened its data folder."}
        return {"ok": False, "message": "That isn't something Toolbelt can do here."}

    def pc_export_programs(self, fmt="csv"):
        """Export list: every program with company, version, size and date, as CSV (Excel) or a web page."""
        import csv
        import html as html_mod
        progs = self.pc_programs()
        folder = Path(self._settings.get()["save_to"])
        folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d")
        cols = [("name", "Program"), ("publisher", "Company"), ("version", "Version"), ("size", "Size (MB)"), ("date", "Installed"), ("location", "Folder")]
        row = lambda p: [p["name"], p["publisher"], p["version"], "%.1f" % (p["size"] / 1048576) if p["size"] else "", p["date"], p["location"]]
        if fmt == "html":
            target = folder / ("Installed programs %s.html" % stamp)
            body = "".join("<tr>" + "".join("<td>%s</td>" % html_mod.escape(str(v)) for v in row(p)) + "</tr>" for p in progs)
            target.write_text("<!doctype html><meta charset='utf-8'><title>Installed programs</title><style>body{font:14px Segoe UI,sans-serif;margin:24px}"
                              "table{border-collapse:collapse}td,th{padding:4px 10px;border-bottom:1px solid #ddd;text-align:left}</style>"
                              "<h1>Installed programs (%d), %s</h1><table><tr>%s</tr>%s</table>" % (len(progs), stamp, "".join("<th>%s</th>" % c[1] for c in cols), body),
                              encoding="utf-8")
        else:
            target = folder / ("Installed programs %s.csv" % stamp)
            with open(target, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=";")                  # ; so Dutch Excel splits the columns
                w.writerow([c[1] for c in cols])
                w.writerows(row(p) for p in progs)
        subprocess.Popen(["explorer.exe", "/select,", str(target)])
        return {"ok": True, "message": "Saved " + target.name, "path": str(target)}

    # ---------- the Revo-style flow: restore point → its own uninstaller → scan → registry tree → files tree ----------
    def pc_revo_begin(self, kind, item_id, restore=True):
        restore_fn = pccare.restore_point if restore else None
        if kind == "app":
            app = next((a for a in (self._store or []) if a["id"] == item_id), None)
            if not app:
                return {"ok": False, "message": "That app isn't in the list any more."}

            def remove_app():
                result = pccare.remove_store_app(app["full"])
                self._store = None
                return result
            return self._revo.begin(app["name"], leftscan.profile_for_app(app), restore_fn, remove_app, None, "app")
        program = self._prog(item_id)
        if not program:
            return {"ok": False, "message": "That program isn't in the list any more."}
        profile = leftscan.profile_for_program(program)            # taken now: afterwards its folder may be gone
        listed = lambda: any(p["id"] == item_id for p in pccare.programs())
        return self._revo.begin(program["name"], profile, restore_fn, lambda: leftscan.launch_uninstaller(program), listed, "program")

    def pc_revo_go_on(self):
        """The restore point failed and he chose to uninstall anyway."""
        return self._revo.go_on_without_rp()

    def pc_revo_status(self):
        return self._revo.status()

    def pc_revo_scan(self, mode):
        return self._revo.scan(str(mode))

    def pc_revo_hunt(self, name, mode):
        return self._revo.hunt(str(name), str(mode))

    def pc_revo_cancel(self):
        return self._revo.cancel_scan()

    def pc_revo_result(self):
        return self._revo.result()

    def pc_revo_delete(self, ids, admin=False):
        return self._revo.delete([str(i) for i in (ids or [])], bool(admin))

    def pc_revo_close(self):
        """The dialog closed: forget the session, and read the program list again (something may be gone)."""
        if self._revo.phase in ("working", "scanning"):
            return {"ok": False, "message": "Still busy."}
        self._revo.reset()
        self._programs = None
        return {"ok": True}

    def pc_open_backups(self):
        folder = leftscan.DATA / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(folder)])
        return {"ok": True, "message": "Registry backups: double-click a .reg file to put it back."}

    # ---------- Windows (Store) apps ----------
    def pc_store_apps(self, refresh=False):
        if refresh or self._store is None:
            found = pccare.store_apps()
            for a in found:
                a["icon_data"] = shellicon.icon("shell:AppsFolder\\" + a["appid"], 32) if a["appid"] else ""
            self._store = found
        return self._store

    def pc_startup(self):
        found = pccare.startup()
        for s in found:
            s["icon_data"] = shellicon.icon(s["exe"], 32) if s["exe"] else ""
        return found

    def pc_set_startup(self, entry_id, enabled):
        return pccare.set_startup(str(entry_id), bool(enabled))

    def pc_restore_point(self):
        return pccare.restore_point()

    def pc_restore_points(self):
        return pccare.restore_points()

    # ---------- step 9 part 2: drivers and ping ----------
    def pc_drivers(self, refresh=False):
        if refresh or self._drivers is None:
            self._drivers = {"board": drivers.board(), "drivers": drivers.drivers()}
        return self._drivers

    def pc_wu_drivers(self):
        """Asks Windows Update which driver updates it has (a job: it can take a minute)."""
        def work(job):
            job.report(20, "Asking Windows Update…")
            result = drivers.windows_update_drivers()
            job.extra.update(result)
            if not result["ok"]:
                raise RuntimeError(result["message"])
            return "%d driver updates" % len(result["updates"])

        job = self._jobs.submit("Driver updates from Windows Update", "PC care", work, {"action": "wu"})
        return {"ok": True, "id": job.id}

    def pc_open_url(self, which, url=""):
        """Opens an official driver page (only the known makers' sites and the board's own page)."""
        allowed = [m[2] for m in drivers.MAKERS if m[2]]
        board_page = (self._drivers or {}).get("board", {}).get("page", "")
        if which == "board" and board_page:
            webbrowser.open(board_page)
            return {"ok": True, "message": "Opened your board's page. Pick Support > Driver & Utility there; the BIOS is under BIOS & Firmware."}
        if which == "maker" and url in allowed:
            webbrowser.open(url)
            return {"ok": True, "message": "Opened the maker's own driver page."}
        if which == "optional":
            os.startfile("ms-settings:windowsupdate-optionalupdates")
            return {"ok": True, "message": "Windows Update > Advanced options > Optional updates: driver updates are installed from there."}
        return {"ok": False, "message": "Toolbelt only opens official driver pages."}

    def ping_start(self, extra=None):
        hosts = [str(h).strip() for h in (extra or []) if str(h).strip()][:5]
        if self._ping.running():
            self._ping.stop()
            time.sleep(0.1)
        self._ping.start(hosts)
        return {"ok": True}

    def ping_stop(self):
        self._ping.stop()
        return {"ok": True}

    def ping_snapshot(self):
        return self._ping.snapshot()

    def pc_tool(self, which):
        """Windows' own tools, opened for him."""
        tools = {"apps": "ms-settings:appsfeatures", "update": "ms-settings:windowsupdate", "storage": "ms-settings:storagesense", "startup": "ms-settings:startupapps",
                 "devmgmt": "devmgmt.msc", "services": "services.msc", "msconfig": "msconfig.exe", "taskmgr": "taskmgr.exe", "cleanmgr": "cleanmgr.exe", "control": "control.exe", "protection": "SystemPropertiesProtection.exe"}
        target = tools.get(str(which))
        if not target:
            return {"ok": False, "message": "Unknown tool."}
        try:
            os.startfile(target)
            return {"ok": True, "message": ""}
        except OSError as error:
            return {"ok": False, "message": "Windows couldn't open it: %s" % error}

    # ---------- step 8: check a file ----------
    def check_pick(self, what="file"):
        """A file (or a folder) from Windows' own picker, for the Check a file screen."""
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        if what == "folder":
            picked = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if not picked:
                return {"ok": False, "message": ""}
            folder = Path(picked[0])
            count = sum(1 for p in folder.rglob("*") if p.is_file())
            return {"ok": True, "folder": str(folder), "name": folder.name, "files": count, "list": check.list_file_for(folder).exists()}
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, directory=str(media.media_root("Downloads") if (media.other_drives() and (media.other_drives()[0] / "Downloads").is_dir()) else Path.home()), file_types=("All files (*.*)",))
        if not picked:
            return {"ok": False, "message": ""}
        return self._media_add(picked[0])

    def check_hash(self, token):
        """All four fingerprints, as a job (big files take a while)."""
        try:
            src = self._media_path(token)
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}

        def work(job):
            found = check.hashes(job, src)
            job.extra.update(found)
            return "ok"

        job = self._jobs.submit("Fingerprints · " + src.name[:60], "Check", work, {"token": str(token), "action": "hash"})
        return {"ok": True, "id": job.id}

    def check_match(self, found, pasted):
        return check.match(found if isinstance(found, dict) else {}, str(pasted))

    def check_sign(self, token):
        try:
            return check.signature(self._media_path(token))
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}

    def check_sniff(self, token):
        try:
            return check.sniff(self._media_path(token))
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}

    def check_compare(self, token_a, token_b):
        try:
            a, b = self._media_path(token_a), self._media_path(token_b)
        except media.MediaError as error:
            return {"ok": False, "message": str(error)}

        def work(job):
            result = check.compare(job, a, b)
            job.extra.update(result)
            return "same" if result["same"] else "different"

        job = self._jobs.submit("Compare · %s and %s" % (a.name[:40], b.name[:40]), "Check", work, {"action": "compare"})
        return {"ok": True, "id": job.id}

    def check_folder(self, folder, what="make"):
        folder = Path(str(folder))
        if not folder.is_dir():
            return {"ok": False, "message": "That folder isn't there."}

        def work(job):
            result = check.folder_make(job, folder) if what == "make" else check.folder_verify(job, folder)
            job.extra.update(result)
            return "ok"

        job = self._jobs.submit(("Fingerprint list · " if what == "make" else "Check against the list · ") + folder.name, "Check", work, {"action": "folder-" + what, "folder": str(folder)})
        return {"ok": True, "id": job.id}

    # ---------- games: the quick list, the tray pop-up and the taskbar menu (14 Oct) ----------
    def _small_icon(self, path):
        if not path:
            return ""
        if Path(path).suffix.lower() in (".exe", ".lnk", ".dll"):
            return shellicon.icon(path, 32)                      # Explorer's own icon for a program
        return picture_icon(path, 32)

    def _cover_video(self, g):
        """A video cover (his ask, 15 Oct): the address the page plays it from (the HD copy once it's ready)."""
        if g.get("cover_kind") != "video" or not g.get("cover") or self._window is None or self._testing:
            return ""
        try:
            return viewer.url(self._window, gameart.best(g["cover"], "cover", "video"))
        except OSError:
            return ""

    def _cover_data(self, g):
        """The cover as a small data link: GIF covers are sent whole (so they move), pictures as a 450 px thumbnail,
        a video cover as its first moments (a still: the moving one is cover_video)."""
        path = g.get("cover")
        if not path:
            return ""
        if g.get("cover_kind") == "video":
            return media.thumbnail(gameart.best(path, "cover", "video"), 0.5, 450)
        if g.get("cover_kind") == "gif":
            path = gameart.best(path, "cover", "gif")             # the sharpened animated WebP once it's ready
            if self._window is not None and not self._testing:
                try:
                    return viewer.url(self._window, path)        # straight from the file, inside the window (any size)
                except OSError:
                    pass
            try:
                raw = Path(path).read_bytes()
                mime = "image/webp" if path.lower().endswith(".webp") else "image/gif"
                return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii")) if len(raw) < 4 * 1024 * 1024 else media.thumbnail(path, 0, 300)
            except OSError:
                return ""
        return media.thumbnail(gameart.best(path, "cover"), 0, 450)

    def games(self, refresh=False, everything=False):
        """His games with icons and covers. Hidden ones only when `everything` (the library's Hidden filter)."""
        if refresh or self._games is None or time.time() - self._games_at > 60:
            found = games.all_games()
            for g in found:
                g["icon_data"] = self._small_icon(g["icon"])
                g["cover_data"] = self._cover_data(g)
                g["cover_video"] = self._cover_video(g)
                # a frozen frame of a moving cover, for "Still" / "Move on hover" in Settings (his ask, 15 Oct)
                g["cover_still"] = media.thumbnail(gameart.best(g["cover"], "cover", g["cover_kind"]), 0.5, 450) \
                    if g.get("cover") and g.get("cover_kind") in ("gif", "video") else ""
                g["has_banner"] = bool(g.get("banner"))
                g["hd_cover"] = gameart.is_hd(g.get("cover"), "cover", g.get("cover_kind", "pic"))
                g["hd_banner"] = gameart.is_hd(g.get("banner"), "banner", g.get("banner_kind", "pic"))
                hd_ok = not self._testing                     # tests never start the upscaler
                wait_c = hd_ok and self._hd.want(g["key"], g.get("cover"), "cover", g.get("cover_kind", "pic"))
                banners = g.get("banners") or []
                wait_b = False
                for b in banners:                             # every background in the list gets its HD copy
                    wait_b = (hd_ok and self._hd.want(g["key"], b["path"], "banner", b["kind"])) or wait_b
                g["hd_wait"] = bool(wait_c or wait_b or self._hd.waiting(g.get("cover"), "cover") or any(self._hd.waiting(b["path"], "banner") for b in banners))
                # small previews for the editor's row of backgrounds, and what the slideshow needs
                g["banner_count"] = len(banners)
                g["banner_list"] = [{"kind": b["kind"], "own": b["own"], "thumb": media.thumbnail(gameart.best(b["path"], "banner", b["kind"]), 1.0, 240),
                                     "hd": gameart.is_hd(b["path"], "banner", b["kind"]), "width": self._art_width(b["path"])} for b in banners]
            self._games, self._games_at = found, time.time()
        return self._games if everything else games.visible(self._games)

    def _art_width(self, path):
        """How wide the original background is (remembered per file), so the editor can mark the ones that will look
        soft full screen: 16 Oct, his backgrounds were SteamGridDB previews of 850 px."""
        try:
            st = Path(path).stat()
        except (OSError, TypeError):
            return 0
        cache = self.__dict__.setdefault("_widths", {})
        key = (str(path), st.st_size, int(st.st_mtime))
        if key not in cache:
            info = media.probe(path)
            cache[key] = int(info.get("width") or 0)
        return cache[key]

    def games_hd_status(self):
        """For the progress bar (his ask, 15 Oct): which game's art is being sharpened, how far, and what waits."""
        s = self._hd.status()
        names = {g["key"]: g["name"] for g in (self._games or [])}
        if s["now"]:
            s["now"]["name"] = names.get(s["now"].get("key"), "")
        s["waitingNames"] = [names.get(k, "") for k in s["waiting"]]
        return s

    def _hd_done(self, key, which):
        """An HD cover or banner is ready: read the list again and tell the page to swap it in."""
        self._games = None
        self._mail.append({"games_hd": key, "which": which})

    def _games_changed(self):
        self._games = None
        threading.Thread(target=self.refresh_jumplist, daemon=True).start()

    def game_banner(self, key, index=0):
        """One of the game's backgrounds (number `index`, they fade from one to the next): a 2560 px JPEG, the GIF or
        WebP itself, or a video played from the file."""
        g = games.find(str(key), self.games(everything=True))
        banners = (g or {}).get("banners") or []
        if not banners:
            return {"ok": False, "kind": "pic", "data": ""}
        chosen = banners[int(index or 0) % len(banners)]
        path, kind = chosen["path"], chosen["kind"]
        try:
            if kind in ("gif", "video"):
                hd = gameart.is_hd(path, "banner", kind)
                path = gameart.best(path, "banner", kind)             # the sharpened WebP / MP4 once it's ready
                if self._window is not None and not self._testing:
                    try:                                              # played straight from the file inside the window: no size cap
                        return {"ok": True, "kind": kind, "data": viewer.url(self._window, path), "hd": hd}
                    except OSError:
                        pass
                raw = Path(path).read_bytes()
                if len(raw) > 15 * 1024 * 1024:
                    return {"ok": False, "kind": kind, "data": "", "message": "That banner is over 15 MB: too big to show here."}
                low = path.lower()
                mime = "image/webp" if low.endswith(".webp") else "image/gif" if kind == "gif" else "video/webm" if low.endswith(".webm") else "video/mp4"
                return {"ok": True, "kind": kind, "data": "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii")), "hd": hd}
            data = media.thumbnail(gameart.best(path, "banner"), 0, 2560)       # full screen now: up to 2560 px, the HD copy when ready
            return {"ok": bool(data), "kind": "pic", "data": data, "hd": gameart.is_hd(path, "banner")}
        except OSError:
            return {"ok": False, "kind": kind, "data": ""}

    def game_banner_edit(self, key, what, index=0):
        """The editor's row of backgrounds: remove one, move one earlier / later, or put the launcher's own back."""
        key = str(key)
        if what == "remove":
            result = games.remove_banner(key, int(index))
        elif what in ("left", "right"):
            result = games.move_banner(key, int(index), -1 if what == "left" else 1)
        elif what == "own":
            result = games.add_own_banner(key)
        else:
            return {"ok": False, "message": "Unknown change."}
        if result["ok"]:
            self._games_changed()
        return result

    def game_set(self, key, what, value):
        """favourite / hidden on or off, or the banner effect."""
        key = str(key)
        if what == "favourite":
            games.set_flag(key, "favourites", bool(value))
        elif what == "hidden":
            games.set_flag(key, "hidden", bool(value))
        elif what == "fx":
            games.set_fx(key, str(value))
        else:
            return {"ok": False, "message": "Unknown setting."}
        self._games_changed()
        return {"ok": True, "message": ""}

    def game_art_pick(self, key, which):
        """Artwork > + : a picture, GIF or (for banners) a short video from his PC."""
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        kinds = "Pictures GIFs and short videos (*.png;*.jpg;*.jpeg;*.webp;*.avif;*.gif;*.mp4;*.webm;*.mov;*.m4v)"   # covers too (15 Oct)
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=(kinds,))
        if not picked:
            return {"ok": False, "message": ""}
        result = games.set_art(str(key), str(which), picked[0])
        if result["ok"]:
            self._games_changed()
        return result

    def game_art_url(self, key, which, url):
        """Artwork > link: he pasted a web address of a picture; Toolbelt fetches that one file."""
        try:
            tmp = games.fetch_art(url)
        except ValueError as error:
            return {"ok": False, "message": str(error)}
        except Exception as error:
            return {"ok": False, "message": "Couldn't fetch that link: %s" % str(error)[:120]}
        try:
            result = games.set_art(str(key), str(which), tmp)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        if result["ok"]:
            self._games_changed()
        return result

    # ---------- Wallpaper Engine (15 Oct): its wallpapers as backgrounds ----------
    def wallpapers(self):
        """His Wallpaper Engine wallpapers (only read; nothing in Wallpaper Engine changes)."""
        try:
            items = wallpaper.wallpapers()
        except OSError as error:
            return {"ok": False, "message": "Couldn't read Wallpaper Engine's folders: %s" % str(error)[:120], "items": []}
        self._wp = {w["id"]: w for w in items}
        if not items:
            return {"ok": True, "items": [], "message": "No Wallpaper Engine wallpapers found in your Steam libraries."}
        return {"ok": True, "items": [{k: w[k] for k in ("id", "title", "type", "kind", "size", "tags")} for w in items]}

    def wallpaper_thumb(self, wp_id):
        w = getattr(self, "_wp", {}).get(str(wp_id))
        return wallpaper.thumb(w) if w else ""

    def game_wallpaper(self, key, which, wp_id):
        """Use a wallpaper: a video one becomes a moving background (a smaller copy first when it's big), a scene or
        web one gives its preview picture / GIF (sharpened by the HD worker afterwards)."""
        w = getattr(self, "_wp", {}).get(str(wp_id)) or wallpaper.find(wp_id)
        key, which = str(key), str(which)
        if not w or which not in ("cover", "banner"):
            return {"ok": False, "message": "That wallpaper isn't there any more."}
        if not wallpaper.needs_copy(w):
            result = games.set_art(key, which, w["path"])
            if result["ok"]:
                self._games_changed()
            return result

        def work(job):
            tmp = wallpaper.small_copy(job, w, media.CACHE.parent / "wallpaper")
            try:
                result = games.set_art(key, which, tmp)
            finally:
                tmp.unlink(missing_ok=True)
            if not result["ok"]:
                raise RuntimeError(result["message"])
            self._games_changed()
            job.extra["game"] = key
            return result["message"]
        job = self._jobs.submit("Background from " + w["title"][:50], "Wallpaper", work, {"game": key})
        return {"ok": True, "job": job.id, "message": "Making a background-sized copy of \"%s\" (it's %s). It appears when it's done." % (w["title"][:50], "%d MB" % (w["size"] // 1048576))}

    def game_art_clear(self, key, which):
        result = games.clear_art(str(key), str(which))
        self._games_changed()
        return result

    def game_art_search(self, key, which):
        """Artwork > find online: opens SteamGridDB for that game in his browser; he saves or copies a link from there."""
        g = games.find(str(key), self.games(everything=True))
        if not g:
            return {"ok": False, "message": "That game isn't in the list any more."}
        webbrowser.open(games.search_links(g["name"], str(which)))
        return {"ok": True, "message": "Opened SteamGridDB for %s. Right-click a picture there, copy its address, then use the link button." % g["name"]}

    def game_add(self):
        """+ Add game: any program on his PC."""
        if self._window is None:
            return {"ok": False, "message": "The window isn't ready yet."}
        picked = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Programs (*.exe;*.lnk)",))
        if not picked:
            return {"ok": False, "message": ""}
        result = games.add_custom(picked[0])                    # a .lnk is fine: Windows starts it like a double-click
        if result["ok"]:
            self._games_changed()
        return result

    def game_remove(self, key):
        result = games.remove_custom(str(key))
        if result["ok"]:
            self._games_changed()
        return result

    def game_folder(self, key):
        g = games.find(str(key), self.games(everything=True))
        folder = g.get("folder") if g else ""
        if not folder or not Path(folder).is_dir():
            return {"ok": False, "message": "Toolbelt doesn't know where that game is installed."}
        subprocess.Popen(["explorer.exe", folder])
        return {"ok": True, "message": "Opened " + folder}

    def play_game(self, key):
        game = games.find(str(key), self.games(everything=True))
        if not game:
            return {"ok": False, "message": "That game isn't in the list any more."}
        ok, message = games.play(game)
        if ok:
            game["last_played"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._games.sort(key=lambda g: (g["last_played"], g["name"].lower()), reverse=True)
            threading.Thread(target=self.refresh_jumplist, daemon=True).start()
        return {"ok": ok, "message": message}

    def refresh_jumplist(self):
        """Rewrites the taskbar right-click menu: recently played games + tasks."""
        if self._testing:
            return {"ok": True, "message": "Skipped in the self-test."}
        try:
            ok, message = jumplist.update(self.games(), launcher(), Path(__file__).resolve())
        except Exception as error:
            ok, message = False, "The taskbar menu couldn't be written: %s" % error
        return {"ok": ok, "message": message}

    def popup_toggle(self):
        return self.popup_hide() if self._popup_shown else self.popup_show()

    def popup_show(self):
        pop = self._popup
        if not pop:
            return {"ok": False}
        left, top, right, bottom = tray.work_area()
        pop.move(right - POPUP[1] - 12, bottom - POPUP[2] - 12)
        pop.show()
        self._popup_shown = True
        try:
            pop.evaluate_js("window.toolbeltPopup && window.toolbeltPopup.reload()")
        except Exception:
            pass
        threading.Thread(target=self._popup_watch, daemon=True).start()
        return {"ok": True}

    def popup_hide(self):
        self._popup_shown = False
        if self._popup:
            self._popup.hide()
        return {"ok": True}

    def _popup_watch(self):
        """Hides the pop-up when he clicks somewhere else (it stops being the window in front)."""
        time.sleep(0.7)
        misses = 0
        while self._popup_shown:
            time.sleep(0.15)
            if tray.foreground_is(POPUP[0]):
                misses = 0
            else:
                misses += 1
                if misses >= 3:
                    self.popup_hide()

    # ---------- the floating mini calculator ----------
    def calc_show(self):
        pop = self._calcpop
        if not pop:
            return {"ok": False, "message": "The mini calculator isn't ready."}
        if not self._calc_shown:
            left, top, right, bottom = tray.work_area()
            pop.move(right - CALCPOP[1] - 24, top + max(24, (bottom - top - CALCPOP[2]) // 2))
            pop.show()
            self._calc_shown = True
        try:
            pop.evaluate_js("window.calcPop && window.calcPop.reload()")
        except Exception:
            pass
        return {"ok": True}

    def calc_hide(self):
        self._calc_shown = False
        if self._calcpop:
            self._calcpop.hide()
        return {"ok": True}

    def calc_toggle(self):
        return self.calc_hide() if self._calc_shown else self.calc_show()

    def show_main(self, screen=""):
        """Brings the main window forward, on a screen if asked (from the tray and the taskbar menu)."""
        if self._popup_shown:
            self.popup_hide()
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "Toolbelt")
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
        if screen:
            self._mail.append({"open": str(screen)})
        return {"ok": True}

    def mail(self):
        """The page asks every second: anything to open? (--open and `run` from outside land in a small file.)"""
        out, self._mail = self._mail, []
        box = DATA / "open.txt"
        if box.exists():
            try:
                for line in box.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("run\t"):
                        _, tool, path = line.split("\t", 2)
                        out.append(self._door(tool, path))
                    elif line:
                        out.append({"open": line})
                box.unlink()
            except (OSError, ValueError):
                pass
        return out

    def _door(self, tool, path):
        """The command door (step 8): `Toolbelt.exe main.py run cutout "<file>"` from Waypoint's right-click menu."""
        added = self._media_add(path)
        if not added["ok"]:
            return {"open": "home", "toast": added["message"]}
        return {"run": tool if tool in ("cutout", "check", "media", "upscale") else "media", "token": added["file"]["token"], "file": added["file"]}

    # ---------- Toolbelt's own window bar (winbar.py): the page's buttons ----------
    # ---------- the internet switch (17 Oct): his Ethernet off / on without pulling the cable, see netswitch.py ----------
    def _net_adapter(self, fresh=False):
        if fresh or not hasattr(self, "_netname"):
            self._netname = netswitch.installed()
        return self._netname

    def net_state(self):
        """For the top-bar button (asked every few seconds; instant unless the adapter is down)."""
        name = self._net_adapter()
        if not name:
            return {"installed": False, "state": "on" if any(s.isup for n, s in psutil.net_if_stats().items() if not n.lower().startswith("loopback")) else "nocable"}
        return {"installed": True, "adapter": name, "state": netswitch.state(name)}

    def net_set(self, on):
        if not self._net_adapter():
            return {"ok": False, "message": "Set up the internet switch first (Settings > About).", "setup": True}
        return netswitch.switch(bool(on))

    def net_setup(self):
        result = netswitch.setup()
        self._net_adapter(fresh=True)
        return result

    def net_remove(self):
        result = netswitch.remove()
        self._net_adapter(fresh=True)
        return result

    # ---------- App guard (18 Oct): new programs are checked and he decides, see appguard.py ----------
    def guard_status(self):
        st = self._guard.status()
        st["on"] = self._settings.get()["guard_on"]
        return st

    def guard_switch(self, on):
        result = self._settings.set("guard_on", bool(on))
        if bool(on) and not self._testing:
            self._guard.start()
        elif not on:
            self._guard.stop()
        return {"ok": result["ok"], "message": "App guard is watching for new programs." if on else "App guard is off. Defender still protects you."}

    def guard_pending(self):
        return {"pending": list(self._guard.pending)}

    def guard_decide(self, ask_id, action):
        result = self._guard.decide(int(ask_id), str(action))
        if not self._guard.pending:
            self.guard_hide()
        if result.get("show"):
            self.show_main("guard-scan")                       # a note's "Show": Toolbelt opens on App guard's Scan tab
        return result

    # ---------- App guard's scans (18 Oct): Program check, Defender quick / full, a folder or drive ----------
    def guard_scan(self, kind, folder=""):
        if kind not in ("program", "quick", "full", "folder"):
            return {"ok": False, "message": "Unknown scan."}
        busy = [j for j in self._jobs.list() if j.get("kind") == "Scan" and j["state"] in ("waiting", "running")]
        if busy:
            return {"ok": False, "message": "A scan is already running; one at a time."}
        if kind == "folder":
            if not folder:
                if self._window is None:
                    return {"ok": False, "message": "The window isn't ready yet."}
                picked = self._window.create_file_dialog(webview.FOLDER_DIALOG)
                if not picked:
                    return {"ok": False, "message": ""}
                folder = picked[0]
            if not Path(folder).is_dir():
                return {"ok": False, "message": "That folder isn't there."}
        g = self._guard
        titles = {"program": "Program check", "quick": "Defender quick scan", "full": "Defender full scan", "folder": "Scan " + str(folder)}

        def work(job):
            if kind == "program":
                places = guardscan.program_places()
                files = [(label, f) for label, fs in places for f in fs]
                findings, fine = guardscan.check_files(job, files, g, label="Program check")
                result = {"label": "Program check", "findings": findings, "fine": fine, "checked": len(files),
                          "places": {label: len(fs) for label, fs in places}}
            elif kind == "folder":
                is_drive = len(str(folder).rstrip("\\/")) <= 2
                files = [("Folder", f) for f in guardscan._walk(folder, 6, 30000) if guardscan.interesting(f)]
                findings, fine = guardscan.check_files(job, files, g, scan=False, label="Checking programs", span=40)
                if is_drive:
                    findings = guardscan.usb_tricks(folder) + findings
                dv = guardscan.defender(job, "folder", folder, remediate=False)
                for t in dv["threats"]:
                    for f in t["files"] or [folder]:
                        findings.insert(0, {"path": f, "name": Path(f).name, "place": "Defender", "verdict": "danger", "size": 0, "checks": [["bad", "Defender: " + t["name"]]]})
                result = {"label": "Scan of " + str(folder), "findings": findings, "fine": fine, "checked": len(files), "threats": dv["threats"], "seconds": dv["seconds"]}
            else:
                dv = guardscan.defender(job, kind)
                result = {"label": titles[kind], "findings": [], "threats": dv["threats"], "seconds": dv["seconds"], "clean": dv["clean"] and not dv["threats"]}
            g.save_scan(kind, result)
            n = len(result.get("findings") or []) + len(result.get("threats") or [])
            job.report(100, "Done: %s" % ("%d to look at" % n if n else "nothing risky found"))
            return n

        job = self._jobs.submit(titles[kind], "Scan", work, {"scan": kind})
        return {"ok": True, "job": job.id, "message": "Started: " + titles[kind]}

    def guard_finding(self, path, action):
        """Trust / Quarantine / Show for something a scan or the Downloads check found (only paths it found)."""
        st = self._guard.status()
        found = {appguard._key(f["path"]) for s in st["scans"].values() for f in s.get("findings") or []} | {appguard._key(d["path"]) for d in st["downloads"]}
        if appguard._key(path) not in found:
            return {"ok": False, "message": "That isn't one of App guard's finds."}
        if action == "trust":
            return self._guard.trust_path(path)
        if action == "quarantine":
            return self._guard.quarantine_path(path)
        if action == "show":
            if not Path(path).exists():
                return {"ok": False, "message": "That file isn't there any more."}
            subprocess.Popen(["explorer.exe", "/select,", str(path)])
            return {"ok": True, "message": ""}
        return {"ok": False, "message": "Unknown action."}

    def guard_forget(self, path):
        return self._guard.forget(str(path))

    def guard_restore(self, qid):
        return self._guard.restore(str(qid))

    def guard_delete(self, qid):
        return self._guard.delete(str(qid))

    def _guard_ask(self):
        """A question is waiting: show the warning above the clock (it stays until he answers)."""
        win = self._guardwin
        if not win or self._testing:
            return
        left, top, right, bottom = tray.work_area()
        win.move(right - GUARD[1] - 12, bottom - GUARD[2] - 12)
        win.show()
        self._guard_shown = True
        try:
            win.evaluate_js("window.toolbeltGuard && window.toolbeltGuard.reload()")
        except Exception:
            pass

    def guard_hide(self):
        self._guard_shown = False
        if self._guardwin:
            self._guardwin.hide()
        return {"ok": True}

    def win_state(self):
        return {"own": bool(self._own_bar), "max": winbar.is_maximized(self._window) if self._window else False}

    def win_drag(self):
        """The mouse went down on the bar: Windows moves the window from here (snapping included)."""
        return {"ok": bool(self._window and self._own_bar and winbar.start_drag(self._window))}

    def win_min(self):
        if self._window:
            self._window.minimize()
        return {"ok": True}

    def win_max(self):
        """Maximise, or back to normal when it already is."""
        if not self._window:
            return {"ok": False}
        if winbar.is_maximized(self._window):
            self._window.restore()
        else:
            self._window.maximize()
        return self.win_state()

    def win_close(self):
        """The ✕: the same as Windows' close button was (Toolbelt quits; the tray icon goes too)."""
        if self._window:
            self._window.destroy()
        return {"ok": True}

    def wint_info(self):
        """For Settings: is Win+W Toolbelt's, is Windows' own switched off in Windows, and how Toolbelt catches it now
        ("hotkey" once Explorer let go of it, "hook" = the keyboard watcher until then)."""
        return {"on": bool(self._settings.get().get("win_t", True)), "windowsOff": hotkey.windows_wint_off(),
                "mode": self._wint.mode if self._wint and self._wint.running() else ""}

    def wint_restart_explorer(self):
        """Explorer reads its shortcut list when it starts: restart it, then catch Win+W the clean way (a hotkey)."""
        if self._testing:
            return {"ok": False, "message": "Not while testing."}
        hotkey.restart_explorer()
        time.sleep(2.5)                                       # let Explorer settle before asking for Win+W
        self.win_t(False)
        self.win_t(True)
        info = self.wint_info()
        return {"ok": True, "message": "Explorer restarted. Win+W is now a normal shortcut of Toolbelt's." if info["mode"] == "hotkey"
                else "Explorer restarted; Toolbelt still catches Win+W with its key watcher (sign out and in once if it stays that way).", "info": info}

    def win_t(self, on):
        """Starts or stops the Win+W keyboard hook, in its own small process (hotkey.Helper): inside Toolbelt a busy
        Python made it answer Windows late and Windows dropped it for good (15 Oct). While it runs, Windows' own
        Win+W (stepping through the taskbar) is swallowed."""
        if on:
            if not self._wint:
                self._wint = hotkey.Helper("Toolbelt")
            return self._wint.start()
        if self._wint:
            self._wint.stop()
        return False

    def quit(self):
        self._ping.stop()
        upscale.stop_all()                                    # an HD or upscale run in progress stops with Toolbelt (it resumes next start)
        if self._wint:
            self._wint.stop()
        if self._tray:
            self._tray.stop()
        self._guard.stop()
        for w in (self._popup, self._calcpop, self._guardwin, self._window):
            if w:
                try:
                    w.destroy()
                except Exception:
                    pass
        return {"ok": True}


def picture_icon(path, side=64):
    """A project's own icon picture (PNG) as a small data link (Windows' icon lookup would only show 'a PNG file')."""
    from PIL import Image
    try:
        img = Image.open(path)
        img.thumbnail((side, side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGBA").save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def safe_stem(name):
    """A short name that is safe in a file name."""
    clean = "".join("_" if ch in '\\/:*?"<>|' or ord(ch) < 32 else ch for ch in str(name)).strip(" .")
    return clean[:80] or "picture"


def launcher():
    """What shortcuts and the taskbar menu start: Toolbelt.exe when it exists, else pythonw.exe."""
    return LAUNCHER if LAUNCHER.exists() else PYTHONW


def already_running():
    """One Toolbelt at a time: a second start brings the first window forward instead."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW(None, False, "Local\\ToolbeltSingleInstance")
    if ctypes.get_last_error() != 183:                     # ERROR_ALREADY_EXISTS
        return False
    user32 = ctypes.WinDLL("user32")
    hwnd = user32.FindWindowW(None, "Toolbelt")
    if not hwnd:
        return False                                        # a leftover without a window: start normally instead of doing nothing
    user32.ShowWindow(hwnd, 9)                              # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


def selftest(window, api, out_file):
    """Runs inside the hidden window: waits for the page, walks every screen, runs a test job, checks no port is open."""
    result = {"ok": False}
    try:
        deadline = time.time() + 25
        ready = False
        while time.time() < deadline and not ready:
            time.sleep(0.4)
            try:
                ready = bool(window.evaluate_js("!!(window.toolbelt && window.toolbelt.ready)"))
            except Exception:
                ready = False
        screens = json.loads(window.evaluate_js("JSON.stringify(window.toolbelt.walkScreens())") or "{}")
        job_id = api.test_job(1.5)["id"]
        time.sleep(3.5)
        job_state = next((j["state"] for j in api.jobs() if j["id"] == job_id), "missing")
        shown = window.evaluate_js("JSON.stringify(window.toolbelt.state())")
        me = psutil.Process()
        listening = []
        for proc in [me] + me.children(recursive=True):
            try:
                listening += [c.laddr.port for c in proc.net_connections(kind="inet") if c.status == psutil.CONN_LISTEN]
            except psutil.Error:
                pass
        errors = window.evaluate_js("JSON.stringify(window.toolbelt.errors)")
        icon = brand.set_window_icon(api.settings()["look"])
        mark = window.evaluate_js("!!document.querySelector('#mark svg')")
        popup = None
        for _ in range(20):                                      # the hidden pop-up window loads its page too
            popup = api._popup.evaluate_js("JSON.stringify(window.toolbeltPopup && window.toolbeltPopup.state())") if api._popup else None
            if popup and popup != "null":
                break
            time.sleep(0.3)
        popup = json.loads(popup) if popup and popup != "null" else None
        calcpop = None
        for _ in range(20):
            calcpop = api._calcpop.evaluate_js("JSON.stringify(window.calcPop && window.calcPop.state())") if api._calcpop else None
            if calcpop and calcpop != "null":
                break
            time.sleep(0.3)
        calcpop = json.loads(calcpop) if calcpop and calcpop != "null" else None
        # the own window bar (15 Oct): Windows' caption gone, installed on page load (not by this test), the page knows
        own_ok, own_why, by_load = (True, "", True) if api._own_bar else winbar.install(window) + (False,)
        window.evaluate_js("window.toolbelt && window.toolbelt.winState && window.toolbelt.winState()")
        time.sleep(0.6)
        bar = {"installed": own_ok, "why": own_why, "onLoad": by_load, "captionGone": winbar.caption_gone(window),
               "pageKnows": window.evaluate_js("document.querySelector('#root').classList.contains('ownbar')"),
               "buttons": window.evaluate_js("document.querySelectorAll('.winbtns button').length")}
        bar_ok = own_ok and by_load and bar["captionGone"] and bar["pageKnows"] and bar["buttons"] == 3
        try:                                                # videos inside Toolbelt: the real WebView2 loads and seeks them
            sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
            import playcheck
            play = playcheck.run(window)
        except Exception as error:
            play = {"error": repr(error)[:200]}
        play_ok = str(play.get("fetch", "")) == "206 100" and str(play.get("codecs", {}).get("h264", "")).startswith(("yes", "probably", "maybe"))
        result = {"ok": ready and job_state == "done" and not listening and screens.get("failed") == [] and icon and bool(mark) and bool(popup) and bool(calcpop and calcpop.get("keys")) and bar_ok and play_ok,
                  "bar": bar, "play": play,
                  "ready": ready, "screens": screens, "job": job_state, "page": json.loads(shown) if shown else None,
                  "listening": listening, "errors": json.loads(errors) if errors else None, "icon": icon, "mark": bool(mark), "popup": popup, "calcpop": calcpop}
    except Exception as error:                              # a test should report, not hang
        result = {"ok": False, "error": repr(error)}
    finally:
        Path(out_file).write_text(json.dumps(result, indent=2), encoding="utf-8")
        api.quit()


def undo_windows_changes(now=None, nets=netswitch, keys=hotkey, mark=brand):
    """setup.ps1 -Uninstall runs `main.py --uninstall`: puts back what Toolbelt changed in Windows. Its own folders are
    the script's job. Returns the lines it prints."""
    now = now if now is not None else Settings().get()
    said = []
    if now.get("calc_key"):
        mark.calc_key(None)
        said.append("The Calculator key opens Windows' calculator again.")
    if now.get("win_t") and keys.set_windows_wint(off=False):
        said.append("Windows' own Win+%s is back (after signing out or restarting Explorer)." % keys.KEY_LETTER)
    if nets.installed():
        r = nets.remove()                                   # one admin prompt, like the setup
        said.append("Internet switch: " + r["message"])
    gone = mark.remove_shortcuts()
    if gone:
        said.append("Removed: " + ", ".join(gone))
    return said or ["Nothing in Windows needed putting back."]


def main():
    args = sys.argv[1:]
    hidden = "--hidden" in args
    test_file = args[args.index("--selftest") + 1] if "--selftest" in args else None
    if "--uninstall" in args:
        print("\n".join(undo_windows_changes()))
        return
    DATA.mkdir(parents=True, exist_ok=True)
    if "--play" in args:                                    # the taskbar menu: start a game and leave
        game = games.find(args[args.index("--play") + 1])
        if game:
            games.play(game)
        return
    opened = args[args.index("--open") + 1] if "--open" in args else ""
    door = ""
    if "run" in args and len(args) > args.index("run") + 2:  # Toolbelt.exe main.py run cutout "<file>"  (Waypoint's right-click menu)
        door = "run\t%s\t%s" % (args[args.index("run") + 1], args[args.index("run") + 2])
    if not test_file and already_running():
        if opened or door:
            with open(DATA / "open.txt", "a", encoding="utf-8") as box:                         # the running Toolbelt picks this up
                box.write((opened or door) + "\n")
        return
    brand.claim_taskbar()                                   # its own taskbar button, not Python's
    api = Api(testing=bool(test_file))
    if opened:
        api._mail.append({"open": opened})
    if door:
        api._mail.append(api._door(door.split("\t")[1], door.split("\t")[2]))
    look = api.settings()["look"]
    window = webview.create_window("Toolbelt", html=build_page(), js_api=api, width=1320, height=860, min_size=(900, 600),
                                   background_color=BACKGROUND.get(look, "#26225A"), hidden=hidden)
    api._window = window
    left, top, right, bottom = tray.work_area()
    api._popup = webview.create_window(POPUP[0], html=build_popup(), js_api=api, width=POPUP[1], height=POPUP[2],
                                       x=right - POPUP[1] - 12, y=bottom - POPUP[2] - 12, frameless=True, on_top=True,
                                       hidden=True, background_color=BACKGROUND.get(look, "#26225A"))
    api._guardwin = webview.create_window(GUARD[0], html=build_guard(), js_api=api, width=GUARD[1], height=GUARD[2],
                                          x=right - GUARD[1] - 12, y=bottom - GUARD[2] - 12, frameless=True, on_top=True, hidden=True,
                                          background_color=BACKGROUND.get(look, "#26225A"))
    api._calcpop = webview.create_window(CALCPOP[0], html=build_calcpop(), js_api=api, width=CALCPOP[1], height=CALCPOP[2],
                                         x=right - CALCPOP[1] - 24, y=top + 24, frameless=True, on_top=True, hidden=True,
                                         background_color=BACKGROUND.get(look, "#26225A"))

    def loaded():
        # Windows' title bar goes, the page's bar takes its place. Only once the page has loaded: at "shown" WebView2
        # isn't ready yet (its CoreWebView2 is still None, seen 15 Oct)
        # (25 Oct, "sometimes it glitches and doesn't appear": WebView2 can still be starting when "loaded" fires, and
        # the page only asked twice, at start and 1.5 s later; so try again for a while, then tell the page itself)
        if api._own_bar or not api.settings().get("own_bar", True):
            return
        why = ""
        for _ in range(40):
            ok, why = winbar.install(window)
            if ok:
                api._own_bar = True
                break
            time.sleep(0.25)
        else:
            print("own window bar not possible:", why)
        window.evaluate_js("window.toolbelt && window.toolbelt.winState && window.toolbelt.winState()")

    window.events.loaded += loaded

    def shown():
        brand.set_window_icon(look)
        if test_file:
            return                                          # no tray icon and no taskbar menu while testing
        api._tray = tray.Tray(look, on_click=api.popup_toggle, on_open=api.show_main, on_games=lambda: api.show_main("games"), on_quit=api.quit, on_calc=api.calc_show)
        api._tray.start()
        if api.settings()["win_t"]:
            try:
                hotkey.set_windows_wint(off=True)           # Windows' own Win+W stays off in Windows' settings (his wish)
            except OSError:
                pass
            api.win_t(True)                                 # Win+W opens / hides Toolbelt
        if api.settings()["guard_on"]:
            api._guard.start()                              # App guard watches for new programs (18 Oct)

        def taskbar_bits():
            # work folders left in Temp by upscales that were cut off (Toolbelt closed mid-run): ~470 MB on 15 Oct
            import shutil
            import tempfile
            for left in Path(tempfile.gettempdir()).glob("toolbelt-*"):
                try:
                    if left.is_dir() and left.name.split("-")[1] in ("video", "hd", "gif", "up", "2pass") and time.time() - left.stat().st_mtime > 600:
                        shutil.rmtree(left, ignore_errors=True)
                except (OSError, IndexError):
                    pass
            # Toolbelt.exe (the venv launcher with Toolbelt's icon) + the Start-menu shortcut carrying Toolbelt's identity:
            # without those Windows shows "Python" / a cmd icon (seen 14 Oct)
            try:
                brand.make_launcher(Path(sys.executable).parent, look)
                brand.start_menu_shortcut(launcher(), Path(__file__).resolve(), look)
                brand.start_menu_shortcut(launcher(), Path(__file__).resolve(), look, name="Calculator", args="--open calc-mini")   # "calc" in Start finds Toolbelt's
                if api.settings()["calc_key"]:
                    brand.calc_key(api._calc_command())                 # keep the registry entry pointing at the current folder
            except Exception:
                pass
            api.refresh_jumplist()

        threading.Thread(target=taskbar_bits, daemon=True).start()

    window.events.shown += shown
    # Closing the main window must end everything: the hidden pop-up window otherwise keeps the process alive without a
    # window, and every later start thinks Toolbelt is "already running" and quits (his pinned button did nothing, 14 Oct).
    def closed():
        api.quit()                                                 # its answer (a dict, for the page) would break pywebview's event code

    window.events.closed += closed
    webview.start(selftest if test_file else None, (window, api, test_file) if test_file else None,
                  http_server=False, private_mode=False, storage_path=str(DATA / "webview"))


def segno_error():
    """segno's own error type (a too-long text and so on), or ValueError if it has none."""
    try:
        from segno import DataOverflowError
        return DataOverflowError
    except ImportError:
        return ValueError


if __name__ == "__main__":
    main()

