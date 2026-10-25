"""The finishing tools (15 Oct) on made-up files in a temporary folder: renaming many files (and undo), QR codes,
crop / many pictures / iPhone HEIC, cutting and evening out sound, subtitles with the real whisper.cpp, Wallpaper
Engine's folders, Fix all songs (LRCLIB answers faked), subtitles in downloads, and the resuming installer."""
import io
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import downloader                                              # noqa: E402
import engines                                                 # noqa: E402
import installer                                               # noqa: E402
import media                                                   # noqa: E402
import music                                                   # noqa: E402
import qrmaker                                                 # noqa: E402
import renamer                                                 # noqa: E402
import settings                                                # noqa: E402
import wallpaper                                               # noqa: E402

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


class Job:
    def __init__(self):
        self.messages = []
        self.extra = {}

    def report(self, percent, message=""):
        self.messages.append(message)

    def check(self):
        pass


tmp = Path(tempfile.mkdtemp(prefix="toolbelt-finish-"))
out = tmp / "out"
out.mkdir()

# ---------- renaming many files ----------
rn = tmp / "rename"
rn.mkdir()
renamer.UNDO = tmp / "undo.json"
for name in ("a.txt", "b.txt", "IMG_0001.JPG", "IMG_0002.JPG", "IMG_0003.JPG"):
    (rn / name).write_text(name, encoding="utf-8")
swap = [{"path": str(rn / "a.txt"), "old": "a.txt", "new": "b.txt", "problem": ""}, {"path": str(rn / "b.txt"), "old": "b.txt", "new": "a.txt", "problem": ""}]
r = renamer.apply(swap)
expect("rename: two files can swap names", r["ok"] and (rn / "a.txt").read_text() == "b.txt" and (rn / "b.txt").read_text() == "a.txt")
r = renamer.undo()
expect("rename: undo puts both names back", r["ok"] and (rn / "a.txt").read_text() == "a.txt" and renamer.can_undo() == 0)
imgs = sorted(rn.glob("IMG_*"))
plan = renamer.plan(imgs, {"find": "img_", "replace": "Holiday ", "ext_case": "lower"})
expect("rename: find / replace ignores upper or lower case, .JPG becomes .jpg", [p["new"] for p in plan] == ["Holiday 0001.jpg", "Holiday 0002.jpg", "Holiday 0003.jpg"])
plan = renamer.plan(imgs, {"base": "Texel", "number": "after", "start": 1, "digits": 2, "sep": " "})
expect("rename: a new name for all with numbers", [p["new"] for p in plan] == ["Texel 01.JPG", "Texel 02.JPG", "Texel 03.JPG"])
plan = renamer.plan(imgs, {"base": "same"})
expect("rename: the same name twice is a problem, not a crash", plan[0]["problem"] == "" and "same name" in plan[1]["problem"])
plan = renamer.plan([rn / "a.txt"], {"base": "b"})
expect("rename: an existing file's name is never taken", "already there" in plan[0]["problem"])
expect("rename: Windows' own names (CON) and bad characters are refused", "Windows" in renamer.plan([rn / "a.txt"], {"base": "CON"})[0]["problem"]
       and renamer.plan([rn / "a.txt"], {"base": "a:b"})[0]["problem"] != "")
expect("rename: a broken pattern says so", "pattern" in renamer.plan([rn / "a.txt"], {"find": "(", "regex": True})[0]["problem"])
plan = renamer.plan(imgs, {"number": "only", "start": 9, "digits": 3})
r = renamer.apply(plan)
expect("rename: numbers only, applied for real", r["ok"] and sorted(p.name for p in rn.glob("0*")) == ["009.JPG", "010.JPG", "011.JPG"])
expect("rename: the date of a file goes in front", renamer.new_name(rn / "a.txt", 0, {"date": "changed"}).startswith(time.strftime("%Y-")))
expect("rename: lower / UPPER / Title case", renamer.new_name(rn / "a.txt", 0, {"base": "mY fILE", "case": "title"}) == "My File.txt")

# ---------- QR codes ----------
p = qrmaker.preview("text", {"text": "https://example.com"})
expect("QR: a link becomes an SVG preview", p["ok"] and p["svg"].startswith("data:image/svg+xml;base64,") and p["modules"] >= 21)
svg, png = qrmaker.render(qrmaker.make("wifi", {"ssid": "Home", "password": "a;b", "security": "WPA"}), "#123456", "")
expect("QR: Wi-Fi in his colours with a see-through background", png[:8] == b"\x89PNG\r\n\x1a\n" and "#123456" in svg)
from segno import helpers                                     # noqa: E402
expect("QR: a ; in the Wi-Fi password is escaped", "P:a\\;b" in helpers.make_wifi_data(ssid="Home", password="a;b", security="WPA"))
for kind, values, word in (("text", {"text": " "}, "Type"), ("wifi", {}, "Wi-Fi"), ("contact", {}, "name"), ("text", {"text": "x" * 2100}, "too long")):
    try:
        qrmaker.make(kind, values)
        expect("QR: refuses " + word, False)
    except ValueError as error:
        expect("QR: refuses an empty / too long code (%s)" % word, word.lower() in str(error).lower())
expect("QR: pale or inverted colours are flagged", not qrmaker.contrast_ok("#FFFFFF", "#000000") and not qrmaker.contrast_ok("#DDDDDD", "#FFFFFF") and qrmaker.contrast_ok("#000000", "#FFFFFF"))

# ---------- pictures: crop, many at once, HEIC ----------
from PIL import Image                                          # noqa: E402
Image.new("RGB", (800, 600), (200, 50, 50)).save(tmp / "pic.jpg")
Image.new("RGBA", (300, 500), (0, 120, 255, 128)).save(tmp / "see.png")
Image.new("RGB", (640, 480), (20, 160, 90)).save(tmp / "phone.heic")
expect("HEIC: an iPhone photo counts as a picture and opens", media.HEIC and media.kind_of(tmp / "phone.heic") == "picture" and media.open_picture(tmp / "phone.heic").size == (640, 480))
expect("HEIC: it gets a thumbnail", media.thumbnail(tmp / "phone.heic").startswith("data:image/jpeg"))
r = media.crop_picture(tmp / "pic.jpg", {"x": 100, "y": 50, "w": 300, "h": 200}, out)
expect("crop: a drawn box", (r["width"], r["height"]) == (300, 200) and Image.open(r["path"]).size == (300, 200))
r = media.crop_picture(tmp / "pic.jpg", {"x": 700, "y": 500, "w": 400, "h": 400}, out)
expect("crop: a box past the edge is trimmed to the picture", (r["width"], r["height"]) == (100, 100))
r = media.crop_picture(tmp / "pic.jpg", "16:9", out)
expect("crop: 16:9 from the middle", (r["width"], r["height"]) == (800, 450))
r = media.crop_picture(tmp / "see.png", "1:1", out)
expect("crop: see-through stays see-through (PNG)", r["path"].endswith(".png") and Image.open(r["path"]).mode == "RGBA" and (r["width"], r["height"]) == (300, 300))
expect("crop: the centre box maths", media.centre_box(1000, 500, "1:1") == {"x": 250, "y": 0, "w": 500, "h": 500} and media.centre_box(500, 1000, "16:9")["h"] == 281)
job = Job()
r = media.batch_pictures(job, [tmp / "pic.jpg", tmp / "phone.heic", tmp / "see.png", tmp / "undo.json"], "format", {"fmt": "webp"}, out)
made = sorted(p.suffix for p in Path(r["folder"]).iterdir())
expect("many pictures: 3 converted into one new folder, the odd one skipped and named", r["done"] == 3 and made == [".webp"] * 3 and len(r["failed"]) == 1 and "undo.json" in r["failed"][0])
r2 = media.batch_pictures(Job(), [tmp / "pic.jpg"], "format", {"fmt": "webp"}, out)
expect("many pictures: a second run gets its own folder", r2["folder"] != r["folder"])
r = media.batch_pictures(Job(), [tmp / "pic.jpg", tmp / "see.png"], "resize", {"preset": "emoji"}, out)
expect("many pictures: resize to Discord emoji", all(Image.open(p).size == (128, 128) for p in Path(r["folder"]).iterdir()))
r = media.batch_pictures(Job(), [tmp / "pic.jpg", tmp / "phone.heic"], "crop", {"ratio": "1:1"}, out)
expect("many pictures: crop to a square", sorted(Image.open(p).size for p in Path(r["folder"]).iterdir()) == [(480, 480), (600, 600)])
r = media.batch_pictures(Job(), [tmp / "pic.jpg"], "icomp", {"fmt": "jpg", "quality": 60}, out)
expect("many pictures: compress reports before and after", r["before"] > 0 and r["after"] > 0)
try:
    media.batch_pictures(Job(), [tmp / "undo.json"], "format", {"fmt": "png"}, out)
    expect("many pictures: none working is an error", False)
except media.MediaError:
    expect("many pictures: none working is an error, and no empty folder stays behind", not any(p.is_dir() and not any(p.iterdir()) for p in out.iterdir()))

# ---------- sound ----------
ff = str(media.ffmpeg())
subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=8", "-af", "volume=-20dB", "-c:a", "libmp3lame", str(tmp / "tone.mp3")], check=True)
c = media.cut_sound(Job(), tmp / "tone.mp3", out, 1, 5, 0.5, 1)
expect("sound: a 4-second piece with fades, still an MP3", c.endswith("0m01s to 0m05s.mp3") and abs(media.probe(c)["duration"] - 4) < 0.2)
try:
    media.cut_sound(Job(), tmp / "tone.mp3", out, 3, 3.05)
    expect("sound: a piece that's too short is refused", False)
except media.MediaError:
    expect("sound: a piece that's too short is refused", True)
p, before, after = media.normalise(Job(), tmp / "tone.mp3", out, "spotify")
got = float(media.measure_loudness(Job(), p, 8)["input_i"])
expect("sound: evened out from %.1f to -14 LUFS (measured %.1f)" % (before, got), before < -30 and abs(got + 14) < 1)
subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=navy:s=320x180:d=3", "-c:v", "libx264", str(tmp / "silent.mp4")], check=True)
try:
    media.normalise(Job(), tmp / "silent.mp4", out)
    expect("sound: a video without sound says so", False)
except media.MediaError as error:
    expect("sound: a video without sound says so", "no sound" in str(error))

# ---------- subtitles (the real whisper.cpp, on Windows' own voice) ----------
if engines.path_of("whisper") and engines.path_of("whispermodel"):
    wav = tmp / "speech.wav"
    subprocess.run(["powershell", "-NoProfile", "-Command", "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$s.SetOutputToWaveFile('%s'); $s.Speak('Hello friends. The quick brown fox jumps over the lazy dog.'); $s.Dispose()" % wav], check=True, creationflags=0x08000000)
    subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=navy:s=320x180:d=6", "-i", str(wav), "-shortest", "-c:v", "libx264", "-c:a", "aac", str(tmp / "talk.mp4")], check=True)
    job = Job()
    v, srt = media.subtitles(job, tmp / "talk.mp4", out, "auto", False, "track")
    text = Path(srt).read_text(encoding="utf-8").lower()
    expect("subtitles: whisper wrote down what was said", "quick brown fox" in text and "-->" in text)
    expect("subtitles: the progress bar moved", any("Listening" in m for m in job.messages))
    expect("subtitles: the video got a subtitle track", any(s.get("codec_type") == "subtitle" for s in json.loads(subprocess.run(
        [str(media.ffprobe()), "-v", "quiet", "-print_format", "json", "-show_streams", v], capture_output=True, text=True).stdout)["streams"]))
    try:
        media.subtitles(Job(), tmp / "silent.mp4", out)
        expect("subtitles: no sound, no subtitles", False)
    except media.MediaError:
        expect("subtitles: no sound, no subtitles (a clear message)", True)
else:
    print("skip  subtitles (whisper.cpp was removed at his wish, 15 Oct; media.subtitles stays for later)")

# ---------- Wallpaper Engine ----------
steam = tmp / "Steam"
we = steam / "steamapps" / "workshop" / "content" / "431960"
(we / "111").mkdir(parents=True)
(we / "111" / "project.json").write_text(json.dumps({"title": "Sakura video", "type": "video", "file": "loop.mp4", "preview": "preview.gif"}), encoding="utf-8")
subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=640x360:d=2", "-c:v", "libx264", str(we / "111" / "loop.mp4")], check=True)
Image.new("RGB", (100, 60), (9, 9, 9)).save(we / "111" / "preview.gif")
(we / "222").mkdir()
(we / "222" / "project.json").write_text(json.dumps({"title": "Rain scene", "type": "scene", "file": "scene.json", "preview": "preview.jpg"}), encoding="utf-8")
Image.new("RGB", (400, 225), (40, 40, 90)).save(we / "222" / "preview.jpg")
(we / "333").mkdir()
(we / "333" / "project.json").write_text("not json", encoding="utf-8")
own = steam / "steamapps" / "common" / "wallpaper_engine" / "projects" / "myprojects" / "mine"
own.mkdir(parents=True)
(own / "project.json").write_text("﻿" + json.dumps({"title": "My own", "type": "web", "file": "index.html", "preview": "preview.gif"}), encoding="utf-8")
Image.new("RGB", (100, 60), (9, 9, 9)).save(own / "preview.gif")
items = wallpaper.wallpapers(steam)
expect("Wallpaper Engine: workshop + his own ones, a broken one skipped, videos first",
       [w["title"] for w in items] == ["Sakura video", "My own", "Rain scene"] and [w["kind"] for w in items] == ["video", "gif", "pic"])
expect("Wallpaper Engine: a video uses the video, a scene its preview", items[0]["path"].endswith("loop.mp4") and items[2]["path"].endswith("preview.jpg"))
expect("Wallpaper Engine: a small short video needs no copy", not wallpaper.needs_copy(items[0]))
expect("Wallpaper Engine: a thumbnail for the picker", wallpaper.thumb(items[0]).startswith("data:image/jpeg"))
copy = wallpaper.small_copy(Job(), items[0], out)
info = media.probe(copy)
expect("Wallpaper Engine: the background-sized copy is an MP4 without sound", copy.suffix == ".mp4" and info["width"] == 640 and not info["acodec"])
expect("Wallpaper Engine: find by id", wallpaper.find("222", steam)["title"] == "Rain scene")
real = wallpaper.wallpapers()
print("info  his own PC: %d wallpapers found" % len(real))

# ---------- SteamGridDB previews → the full-size file (16 Oct: his backgrounds were 850 px previews) ----------
import games                                                   # noqa: E402
links = games.full_size_links("https://cdn2.steamgriddb.com/hero_thumb/abc123.webm")
expect("SteamGridDB: a preview link tries the full file first, same ending first", links[0] == "https://cdn2.steamgriddb.com/hero/abc123.webm"
       and links[-1].endswith("hero_thumb/abc123.webm") and "https://cdn2.steamgriddb.com/hero/abc123.png" in links)
expect("SteamGridDB: covers (grids) too", games.full_size_links("https://cdn2.steamgriddb.com/grid_thumb/ff00.jpg")[0] == "https://cdn2.steamgriddb.com/grid/ff00.jpg")
expect("SteamGridDB: other links are left alone", games.full_size_links("https://example.com/hero_thumb/a.jpg") == ["https://example.com/hero_thumb/a.jpg"])
import urllib.error                                            # noqa: E402
asked = []


class FakeRequest:
    Request = staticmethod(lambda link, headers=None: link)

    @staticmethod
    def urlopen(link, timeout=30):
        asked.append(link)
        if link.endswith("hero/abc123.png"):
            return "full png"
        raise urllib.error.HTTPError(link, 404, "not found", {}, None)


expect("SteamGridDB: a 404 on one ending tries the next (the preview is .jpg, the real one .png)",
       games._open_full_size("https://cdn2.steamgriddb.com/hero_thumb/abc123.jpg", FakeRequest) == "full png" and asked[:2] == ["https://cdn2.steamgriddb.com/hero/abc123.jpg", "https://cdn2.steamgriddb.com/hero/abc123.png"])

# ---------- Fix all songs (LRCLIB faked) ----------
answers = {}
music_check = music.lrclib_check
music.lrclib_check = lambda t, a, al, s: answers.get((t, a), {"ok": True, "match": False, "synced": False, "candidates": []})
tags = {"path": "x.mp3", "name": "x.mp3", "title": "め組のひと / 宝鐘マリン cover", "artist": "Marine Ch. 宝鐘マリン", "album": "", "seconds": 207}
answers[("め組のひと", "宝鐘マリン")] = {"ok": True, "match": True, "synced": True, "candidates": []}
r = music.fix_one(tags, wait=lambda s: None)
expect("Fix all: the cleaned-up tags are found", r["status"] == "clean" and r["proposed"]["title"] == "め組のひと" and r["synced"])
answers.clear()
answers[(tags["title"], tags["artist"])] = {"ok": True, "match": True, "synced": False, "candidates": []}
expect("Fix all: a song LRCLIB already knows is left alone", music.fix_one(tags, wait=lambda s: None)["status"] == "already")
answers.clear()
answers[("め組のひと", "宝鐘マリン")] = {"ok": True, "match": False, "candidates": [{"title": "Megumi no Hito", "artist": "Houshou Marine", "album": "Covers", "fits": True, "synced": True, "diff": 1}]}
r = music.fix_one(tags, wait=lambda s: None)
expect("Fix all: else an LRCLIB entry of the same length", r["status"] == "found" and r["proposed"]["artist"] == "Houshou Marine")
answers.clear()
expect("Fix all: nothing fits → by hand", music.fix_one(tags, wait=lambda s: None)["status"] == "none")
waited = []
busy = iter([{"ok": False, "message": "LRCLIB says it's busy"}, {"ok": True, "match": True, "synced": False, "candidates": []}])
music.lrclib_check = lambda *a: next(busy)
expect("Fix all: 'busy' waits and asks again", music.fix_one(tags, wait=waited.append)["status"] == "already" and waited == [20])
music.lrclib_check = music_check

# ---------- subtitles in downloads ----------
a = downloader.build_args("both", 1080, "mp3", "t", "deno", "ff", "info.json", "auto")
expect("downloads: subtitles inside the video, also automatic ones", "--embed-subs" in a and "--write-auto-subs" in a and downloader.SUB_LANGS in a)
expect("downloads: no subtitles when off or for just the sound", "--embed-subs" not in downloader.build_args("both", 1080, "mp3", "t", "d", "f", "i") and
       "--embed-subs" not in downloader.build_args("audio", 0, "mp3", "t", "d", "f", "i", "made"))
expect("settings: dl_subs is checked", settings.check("dl_subs", "made") == (True, "made") and not settings.check("dl_subs", "yes")[0])

# ---------- the installer carries on after a dropped connection ----------
import hashlib                                                 # noqa: E402
blob = bytes(range(256)) * 4000
calls = []


class Resp(io.BytesIO):
    def __init__(self, data, status, total):
        super().__init__(data)
        self.status, self.headers = status, {"Content-Length": str(total)}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_open(req, timeout=30):
    rng = req.headers.get("Range")
    calls.append(rng)
    if rng is None:                                           # the first try stops halfway, like a stall
        class Half(Resp):
            def read(self, n=-1):
                got = super().read(n)
                if self.tell() > len(blob) // 2:
                    raise TimeoutError("stalled")
                return got
        return Half(blob, 200, len(blob))
    start = int(rng.split("=")[1].rstrip("-"))
    return Resp(blob[start:], 206, len(blob) - start)


real_open, real_sleep = installer.urllib.request.urlopen, installer.time.sleep
installer.urllib.request.urlopen, installer.time.sleep = fake_open, lambda s: None
try:
    dest = tmp / "engine.bin"
    installer.download(Job(), "https://example.test/x", dest, hashlib.sha256(blob).hexdigest(), 0, 0, 100)
    expect("installer: a stalled download carries on where it stopped and still matches", dest.read_bytes() == blob and calls[0] is None and calls[1].startswith("bytes="))
finally:
    installer.urllib.request.urlopen, installer.time.sleep = real_open, real_sleep
expect("whisper.cpp is off the engine list (his wish, 15 Oct), the installer still knows it", not {"whisper", "whispermodel"} & {c[0] for c in engines.CATALOG}
       and installer.WHISPER_MODEL_SHA and installer.WHISPER_ZIP)

import shutil                                                  # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)
print("ALL PASSED" if not failures else "%d FAILED" % len(failures))
sys.exit(1 if failures else 0)
