"""The real thing, run by hand (it uses the internet): looks a link up and downloads it with the installed engines,
exactly like the app does, then (for MP3s) puts it in the Spotify folder and reads its tags back.

    %LOCALAPPDATA%\\Toolbelt\\venv\\Scripts\\python.exe tests\\try_download.py URL [audio|both|video] [height]

First real test (13 Oct): his Marine cover, https://youtu.be/JGgnJ0XKGN4, as MP3.
"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import downloader
import music
from settings import Settings


class Job:
    def __init__(self):
        self.progress, self.extra, self.cancelled, self.message, self._last = 0, {}, False, "", -1

    def check(self):
        pass

    def report(self, p, m=""):
        self.progress = p
        if int(p) // 10 != self._last:
            self._last = int(p) // 10
            print("  %5.1f%%  %s  [%s]" % (p, m, self.extra.get("stage", "")), flush=True)


args = sys.argv[1:]
out = None
if "--out" in args:
    out = args[args.index("--out") + 1]
    del args[args.index("--out"):args.index("--out") + 2]
no_spotify = "--no-spotify" in args
args = [a for a in args if a != "--no-spotify"]
url = args[0] if args else "https://youtu.be/JGgnJ0XKGN4"
mode = args[1] if len(args) > 1 else "audio"
height = int(args[2]) if len(args) > 2 else None
s = Settings().get()
if out:
    s["save_to"] = out

t = time.time()
video = downloader.look_up(url)
print("Looked up in %.1fs: %s · %s · %ds" % (time.time() - t, video["title"], video["channel"], video["duration"]))
print("  qualities:", ", ".join("%s (%.0f MB)" % (h["label"], h["size"] / 1048576) for h in video["heights"]))
print("  sound: MP3 ~%.1f MB" % (video["sound"]["mp3"] / 1048576), "· thumbnail:", "yes" if video["thumb"] else "no")

t = time.time()
path = downloader.download(Job(), video["id"], mode, height or (video["heights"][0]["height"] if video["heights"] else None), s["audio_format"] if mode == "audio" else "mp3",
                           Path(s["save_to"]), s["name_pattern"], s["never_overwrite"])
size = Path(path).stat().st_size
print("Downloaded in %.0fs: %s (%.1f MB)" % (time.time() - t, path, size / 1048576))

if path.lower().endswith(".mp3") and not no_spotify:
    sent = music.send_to_spotify(path)
    print("Spotify:", sent["message"], sent.get("path", ""))
    tags = music.read_tags(sent.get("path") or path)
    print("Tags: title=%r artist=%r album=%r cover=%s length=%.0fs" % (tags.get("title"), tags.get("artist"), tags.get("album"), tags.get("cover"), tags.get("seconds", 0)))
print("ALL DONE (try_download)")
