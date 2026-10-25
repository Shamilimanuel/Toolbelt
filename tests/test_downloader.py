"""Tests for step 2 that need no internet: the downloader's helpers, the installer's checks, Spotify copying, settings.

The real end-to-end download (his Marine cover) is tests\\try_download.py, run by hand because it uses the internet.
"""
import hashlib
import io
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import downloader
import installer
import music
from unittest import mock
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from settings import Settings

failures = []


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


# ---------- spotting links ----------
expect("youtu.be link found", downloader.find_link("look https://youtu.be/JGgnJ0XKGN4 !") == "https://youtu.be/JGgnJ0XKGN4")
expect("watch link with extras found", downloader.find_link("https://www.youtube.com/watch?v=JGgnJ0XKGN4&t=42s").startswith("https://www.youtube.com/watch?v=JGgnJ0XKGN4"))
expect("shorts and music links found", downloader.find_link("https://youtube.com/shorts/abcdefghijk") and downloader.find_link("https://music.youtube.com/watch?v=abcdefghijk"))
expect("other sites ignored", downloader.find_link("https://example.com/watch?v=abcdefghijk") is None and downloader.find_link("hello") is None)
expect("trailing bracket trimmed", downloader.find_link("(https://youtu.be/JGgnJ0XKGN4)") == "https://youtu.be/JGgnJ0XKGN4")
expect("huge clipboard text ignored", downloader.find_link("x" * 5000 + "https://youtu.be/JGgnJ0XKGN4") is None)

# ---------- qualities ----------
INFO = {"id": "abc", "title": "め組のひと / 宝鐘マリン cover", "channel": "Marine Ch.", "duration": 240, "formats": [
    {"format_id": "140", "vcodec": "none", "acodec": "mp4a", "filesize": 3_900_000},
    {"format_id": "251", "vcodec": "none", "acodec": "opus", "filesize": 3_700_000},
    {"format_id": "137", "vcodec": "avc1", "acodec": "none", "height": 1080, "filesize": 80_000_000},
    {"format_id": "248", "vcodec": "vp9", "acodec": "none", "height": 1080, "filesize": 60_000_000},
    {"format_id": "313", "vcodec": "vp9", "acodec": "none", "height": 2160, "filesize_approx": 400_000_000},
    {"format_id": "136", "vcodec": "avc1", "acodec": "none", "height": 720, "tbr": 2500},
    {"format_id": "160", "vcodec": "avc1", "acodec": "none", "height": 144, "filesize": 2_000_000},
    {"format_id": "sb0", "vcodec": "none", "acodec": "none"},
]}
q = downloader.quality_options(INFO)
labels = [h["label"] for h in q["heights"]]
expect("heights best first, 4K named, tiny ones dropped", labels == ["4K", "1080p", "720p"])
expect("size = biggest video at that height + best sound", q["heights"][1]["size"] == 80_000_000 + 3_900_000)
expect("size from bitrate when unknown", q["heights"][2]["video_only"] == int(2500 * 1000 / 8 * 240))
expect("MP3 size estimated from the length", q["sound"]["mp3"] == int(240 * 245000 / 8))
s = downloader.summary(INFO)
expect("summary has title, channel, length", s["title"].startswith("め組") and s["channel"] == "Marine Ch." and s["duration"] == 240)
expect("quality tags", downloader.quality_tag("audio", None, "mp3") == "MP3" and downloader.quality_tag("both", 2160) == "2160p" and downloader.quality_tag("video", 1080) == "1080p no sound")

# ---------- file names ----------
expect("forbidden characters swapped", downloader.safe_text('a/b:c*d?"e<f>g|h') == "a_b_c_d__e_f_g_h")
tpl = downloader.output_template("C:\\Out", "{title} - {quality}.{ext}", "め組のひと / 宝鐘マリン cover", "MP3")
expect("template keeps Japanese, swaps the slash, leaves the ending to yt-dlp", tpl == "C:\\Out\\め組のひと _ 宝鐘マリン cover - MP3.%(ext)s")
expect("a % in a title can't become a yt-dlp field", "100%%" in downloader.output_template("C:\\Out", "{title}.{ext}", "100% real", "x"))
expect("(2) goes before the ending", downloader.output_template("C:\\Out", "{title}.{ext}", "Song", "x", 2) == "C:\\Out\\Song (2).%(ext)s")
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / "Song - MP3.mp3").write_bytes(b"x")
    expect("an existing file gets (2) when overwriting is off", downloader.free_template(tmp, "{title} - {quality}.{ext}", "Song", "MP3", True).endswith("Song - MP3 (2).%(ext)s"))
    expect("…and keeps the name when overwriting is on", downloader.free_template(tmp, "{title} - {quality}.{ext}", "Song", "MP3", False).endswith("Song - MP3.%(ext)s"))
    # cancel only removes what the download itself made
    keep = Path(tmp) / "Song - MP3.webm"
    keep.write_bytes(b"old")
    template = str(Path(tmp) / "Song - MP3.%(ext)s")
    before = downloader.existing_with_stem(template)
    (Path(tmp) / "Song - MP3.webm.part").write_bytes(b"half")
    downloader.tidy(template, before)
    expect("cancel removes the half file but not the older one", keep.exists() and not (Path(tmp) / "Song - MP3.webm.part").exists() and (Path(tmp) / "Song - MP3.mp3").exists())

# ---------- yt-dlp's command line ----------
a = downloader.build_args("audio", None, "mp3", "C:\\Out\\x.%(ext)s", "C:\\e\\deno\\deno.exe", "C:\\e\\ffmpeg\\bin", "C:\\c\\abc.info.json")
expect("sound only: extract to MP3 at best quality with cover and tags", all(x in a for x in ["-x", "--embed-thumbnail", "--embed-metadata"]) and a[a.index("--audio-format") + 1] == "mp3" and a[a.index("--audio-quality") + 1] == "0")
expect("Deno and ffmpeg are passed by path", a[a.index("--js-runtimes") + 1] == "deno:C:\\e\\deno\\deno.exe" and a[a.index("--ffmpeg-location") + 1] == "C:\\e\\ffmpeg\\bin")
expect("uses the saved lookup, never a playlist", "--load-info-json" in a and "--no-playlist" in a)
b = downloader.build_args("both", 2160, "mp3", "t", "d", "f", "i")
expect("video + sound: best up to 4K, joined into MP4 (MKV if MP4 can't hold it)", b[b.index("-f") + 1].startswith("bv*[height<=2160]+ba") and b[b.index("--merge-output-format") + 1] == "mp4/mkv")
v = downloader.build_args("video", 1080, "mp3", "t", "d", "f", "i")
expect("video only: no sound stream asked for", v[v.index("-f") + 1] == "bv*[height<=1080]/bv*" and "-x" not in v)
p = downloader.parse_progress("TBPROG downloading|1048576|4194304|NA|524288.5|6")
expect("progress line read", p == {"status": "downloading", "got": 1048576, "total": 4194304, "speed": 524288.5, "eta": 6})
p = downloader.parse_progress("TBPROG downloading|100|NA|5000|NA|NA")
expect("estimate used when the total is unknown", p["total"] == 5000 and p["speed"] is None)
expect("other lines ignored", downloader.parse_progress("[youtube] abc: Downloading webpage") is None)
expect("errors put plainly", "private" in downloader.clean_error("ERROR: [youtube] abc: Private video. Sign in").lower())
expect("speed and time shown plainly", downloader.fmt_speed(5 * 1048576) == "5.0 MB/s" and downloader.fmt_eta(125) == "2:05")

# ---------- the installer's checks (a fake download from a local file) ----------
class FakeJob:
    progress = 0
    cancelled = False
    def check(self): pass
    def report(self, p, m=""): self.progress = p


with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / "thing.bin"
    src.write_bytes(b"official build" * 1000)
    good = hashlib.sha256(src.read_bytes()).hexdigest()
    dest = Path(tmp) / "got.bin"
    installer.download(FakeJob(), src.as_uri(), dest, good, 0, 0, 90)
    expect("a download that matches the fingerprint is kept", dest.read_bytes() == src.read_bytes())
    dest.unlink()
    try:
        installer.download(FakeJob(), src.as_uri(), dest, "0" * 64, 0, 0, 90)
        expect("a mismatching download is refused", False)
    except installer.InstallError:
        expect("a mismatching download is refused and nothing is left", not dest.exists() and not dest.with_name("got.bin.part").exists())

    # the whole install with a pretend source: deno from a zip, replacing an older version
    zbytes = io.BytesIO()
    with zipfile.ZipFile(zbytes, "w") as z:
        z.writestr("deno.exe", b"MZ fake deno")
    zpath = Path(tmp) / "deno-x86_64-pc-windows-msvc.zip"
    zpath.write_bytes(zbytes.getvalue())
    base = Path(tmp) / "engines"
    (base / "deno").mkdir(parents=True)
    (base / "deno" / "deno.exe").write_bytes(b"old")
    real_latest = installer.latest
    installer.latest = lambda eid: ("2.9.7", zpath.as_uri(), hashlib.sha256(zpath.read_bytes()).hexdigest(), 0)
    try:
        installer.install(FakeJob(), "deno", base)
        expect("install unpacks deno.exe and writes its version", (base / "deno" / "deno.exe").read_bytes() == b"MZ fake deno" and (base / "deno" / "version.txt").read_text() == "2.9.7")
        expect("no leftovers after installing", sorted(x.name for x in base.iterdir()) == ["deno"])
        installer.latest = lambda eid: ("2.1.0", zpath.as_uri(), hashlib.sha256(zpath.read_bytes()).hexdigest(), 0)
        try:
            installer.install(FakeJob(), "deno", base)
            expect("a Deno older than 2.3 is refused", False)
        except installer.InstallError:
            expect("a Deno older than 2.3 is refused, the old one kept", (base / "deno" / "version.txt").read_text() == "2.9.7")
    finally:
        installer.latest = real_latest

# ---------- Spotify folder ----------
with tempfile.TemporaryDirectory() as tmp:
    real_dir = music.SPOTIFY_DIR
    music.SPOTIFY_DIR = Path(tmp) / "Spotify"
    try:
        song = Path(tmp) / "Song.mp3"
        song.write_bytes(b"ID3 fake")
        r = music.send_to_spotify(song)
        expect("an MP3 is copied into the Spotify folder", r["ok"] and (music.SPOTIFY_DIR / "Song.mp3").exists() and song.exists())
        expect("sending it twice doesn't make a copy", music.send_to_spotify(song)["ok"] and len(list(music.SPOTIFY_DIR.iterdir())) == 1)
        other = Path(tmp) / "x" / "Song.mp3"
        other.parent.mkdir()
        other.write_bytes(b"ID3 different song, same name")
        r = music.send_to_spotify(other)
        expect("a different song with the same name gets (2)", r["ok"] and r["path"].endswith("Song (2).mp3"))
        expect("non-MP3s are refused with a reason", not music.send_to_spotify(Path(tmp) / "x").get("ok"))
        clip = Path(tmp) / "clip.webm"
        clip.write_bytes(b"x")
        expect("a video can't go to Spotify", "MP3" in music.send_to_spotify(clip)["message"])
    finally:
        music.SPOTIFY_DIR = real_dir

# ---------- covers and lyrics (real ffmpeg on a 2-second tone; no internet) ----------
import engines                                                # noqa: E402
if engines.path_of("ffmpeg"):
    import subprocess
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        song = Path(tmp) / "song.mp3"
        wide = Path(tmp) / "wide.jpg"
        subprocess.run([str(engines.path_of("ffmpeg")), "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-c:a", "libmp3lame", "-q:a", "7", str(song)], check=True, creationflags=0x08000000)
        Image.new("RGB", (640, 360), (200, 60, 60)).save(wide)
        expect("a song without a cover says so", music.read_tags(song)["cover"] is False and music.cover_bytes(song) == b"")
        jpeg = music.crop_square(wide.read_bytes(), {"x": 100, "y": 0, "w": 360})
        with Image.open(io.BytesIO(jpeg)) as im:
            expect("crop_square gives a 640×640 JPEG from the framed square", im.size == (640, 640) and im.format == "JPEG")
        expect("set_cover embeds it", music.set_cover(song, jpeg)["ok"] and music.read_tags(song)["cover"] and music.read_tags(song)["square"])
        expect("the cover can be read back", len(music.cover_bytes(song)) > 1000)
        r = music.set_cover(song, wide.read_bytes())
        expect("a wide cover is noticed; square_cover fixes it", r["ok"] and not music.read_tags(song)["square"] and music.square_cover(song) and music.read_tags(song)["square"])
        r = music.set_lyrics(song, "line one\nline two", "[00:01.00] line one\n[00:02.00] line two")
        t = music.read_tags(song)
        expect("lyrics go into the MP3 (USLT) and an .lrc next to it", r["ok"] and t["lyrics"] and t["lrc"] and (Path(tmp) / "song.lrc").read_text(encoding="utf-8").startswith("[00:01"))
        expect("tags, cover and lyrics survive write_tags", music.write_tags(song, {"title": "Tone"})["ok"] and music.read_tags(song)["cover"] and music.read_tags(song)["lyrics"])
        expect("with timing, a .ttml for Spicy Lyrics is written too", t["ttml"] and 'itunes:timing="Line"' in (Path(tmp) / "song.ttml").read_text(encoding="utf-8"))
        expect("removing lyrics clears the .lrc and the .ttml too", music.set_lyrics(song, "")["ok"] and not music.read_tags(song)["lyrics"] and not (Path(tmp) / "song.lrc").exists() and not (Path(tmp) / "song.ttml").exists())
        import xml.etree.ElementTree as ET
        tt = ET.fromstring(music.lrc_to_ttml("[ar:Someone]\n[00:12.15]いなせだね & <夏>\n[00:16.23]\n[00:20.55][01:40.00]chorus\n", 207.5))
        ps = [(p.get("begin"), p.get("end"), p.text) for p in tt.iter("{http://www.w3.org/ns/ttml}p")]
        expect("LRC → TTML: lines in time order, a chorus twice, an empty line is a pause, the last line ends with the song, Japanese marked",
               ps == [("0:12.150", "0:16.230", "いなせだね & <夏>"), ("0:20.550", "1:40.000", "chorus"), ("1:40.000", "3:27.500", "chorus")]
               and tt.get("{http://www.w3.org/XML/1998/namespace}lang") == "ja")
        expect("no timing, no TTML", music.lrc_to_ttml("just words\nno times", 100) == "")
        expect("video id from yt-dlp's purl tag", music.video_id_of({"purl": "https://www.youtube.com/watch?v=JGgnJ0XKGN4"}) == "JGgnJ0XKGN4" and music.video_id_of({}) == "")
    real_find = music.lyrics_find
    try:
        import urllib.request
        def refuse(*a, **k):
            raise OSError("no internet in tests")
        saved_open = urllib.request.urlopen
        urllib.request.urlopen = refuse
        r = music.lyrics_find("Megumi no hito", "Houshou Marine", 242)
        expect("lyrics_find without internet explains instead of crashing", not r["ok"] and "LRCLIB" in r["message"])
    finally:
        urllib.request.urlopen = saved_open

# ---------- Fix for lyrics: clean tags from YouTube-style ones (his four real songs, 15 Oct) ----------
cases = [({"title": "め組のひと / 宝鐘マリン cover", "artist": "Marine Ch. 宝鐘マリン hololive3期生"}, ("め組のひと", "宝鐘マリン")),
         ({"title": "みむかｩわナイストライ/ P丸様。【歌ってみた】", "artist": "P丸様。"}, ("みむかｩわナイストライ", "P丸様。")),
         ({"title": "【オリジナル楽曲】粛聖!! ロリ神レクイエム☆ / しぐれうい（9さい）【IOSYS（まろん&D.watt）】", "artist": "しぐれうい"}, ("粛聖!! ロリ神レクイエム☆", "しぐれうい")),
         ({"title": "BIRDBRAIN -Japanese Ver.- 歌ってみた(Cover) --- Aokiro!", "artist": "Aokiro!"}, ("BIRDBRAIN (Japanese Ver.)", "Aokiro!"))]
for tags, (want_title, want_artist) in cases:
    got = music.suggest_tags(tags, "x.mp3")
    expect("clean tags: %s / %s" % (want_title, want_artist), (got["title"], got["artist"]) == (want_title, want_artist) and got["album"] == want_title)
expect("an album already there is kept", music.suggest_tags({"title": "Song", "artist": "A", "album": "Real Album"})["album"] == "Real Album")
expect("a plain title stays as it is", music.suggest_tags({"title": "Bohemian Rhapsody", "artist": "Queen"}) == {"title": "Bohemian Rhapsody", "artist": "Queen", "album": "Bohemian Rhapsody"})
import urllib.error                                            # noqa: E402
with mock.patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("u", 429, "busy", {}, None)):
    expect("LRCLIB's 'too many questions' is reported as busy, not as 'no lyrics'", "busy" in music.lrclib_check("a", "b", "c", 100)["message"])

# ---------- new settings ----------
with tempfile.TemporaryDirectory() as tmp:
    st = Settings(tmp)
    expect("downloader defaults", st.get()["keep"] == "both" and st.get()["audio_format"] == "mp3" and st.get()["watch_clipboard"] is True and st.get()["auto_spotify"] is True)
    expect("keep only takes the three choices", not st.set("keep", "everything")["ok"] and st.set("keep", "audio")["ok"])
    expect("sound format only MP3, M4A, Opus", not st.set("audio_format", "wav")["ok"] and st.set("audio_format", "opus")["ok"])
    expect("send to: the five places only, Toolbelt folder by default", st.get()["send_to"] == "folder" and not st.set("send_to", "cloud")["ok"] and st.set("send_to", "desktop")["ok"])
    expect("his own folder must be a full path", not st.set("custom_folder", "Clips")["ok"] and not st.set("custom_folder", 5)["ok"] and st.set("custom_folder", tmp)["ok"])

# ---------- where a download goes ----------
import main                                                          # noqa: E402
import shellicon                                                     # noqa: E402
with tempfile.TemporaryDirectory() as tmp:
    api = main.Api()
    api._settings = Settings(tmp)
    api._settings.set("save_to", tmp)
    where = api._send_folder
    expect("Windows knows his Desktop (OneDrive moved it)", Path(shellicon.known_folder("Desktop")).is_dir())
    expect("Toolbelt folder and Desktop", where("folder", "both", "mp3") == Path(tmp) and where("desktop", "both", "mp3") == Path(shellicon.known_folder("Desktop")))
    expect("Videos / Music picks by kind", where("library", "video", "mp3") == Path(shellicon.known_folder("Videos")) and where("library", "audio", "m4a") == Path(shellicon.known_folder("Music")))
    expect("Spotify only for MP3s, else the Toolbelt folder", where("spotify", "audio", "mp3") == music.SPOTIFY_DIR and where("spotify", "both", "mp3") == Path(tmp) and where("spotify", "audio", "opus") == Path(tmp))
    expect("no folder of his own picked yet: Toolbelt folder", where("custom", "both", "mp3") == Path(tmp))
    api._settings.set("custom_folder", str(Path(tmp) / "Clips"))
    expect("his own folder once picked", where("custom", "both", "mp3") == Path(tmp) / "Clips")
    expect("an unknown place is refused", not api.start_download("x", "both", 1080, "mp3", "t", "cloud")["ok"])

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_downloader)")
