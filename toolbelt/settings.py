"""Toolbelt's settings: one small JSON file in %LOCALAPPDATA%\\Toolbelt, never in OneDrive.

Every value is checked before it is saved, so a broken or hand-edited file can't break the app:
anything unknown or wrong is quietly replaced by the default.
"""
import json
import os
import re
from pathlib import Path

DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Toolbelt"

LOOKS = ("cartridge", "glass", "glassdark")
SEND_TO = ("folder", "desktop", "library", "spotify", "custom")
BAD_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def defaults():
    return {
        "look": "cartridge",
        "accent": "",                       # "" = the look's own accent, else "#RRGGBB"
        "animations": True,
        "save_to": str(Path.home() / "Downloads" / "Toolbelt"),
        "name_pattern": "{title} - {quality}.{ext}",
        "never_overwrite": True,
        "folder_per_tool": False,
        "open_when_done": True,
        "watch_clipboard": True,            # offer to download YouTube links he copies (only while Toolbelt runs)
        "keep": "both",                     # the downloader's default: both (video + sound), video, or audio
        "audio_format": "mp3",
        "auto_spotify": True,               # MP3s also go to Music\Toolbelt for Spotify
        "send_to": "folder",                # where downloads go: folder (save_to), desktop, library (Videos/Music), spotify or custom
        "custom_folder": "",                # the folder he picked last for "custom"
        "calc_key": False,                  # the keyboard's Calculator key opens Toolbelt's mini calculator (a registry entry)
        "win_t": True,                      # Win+T opens / hides Toolbelt (a keyboard hook; his choice 15 Oct)
        "own_bar": True,                    # Toolbelt's own window bar instead of Windows' (his choice 15 Oct)
        "cover_motion": "hover",            # GIF / video covers in the game library: still, hover (and the picked one) or always
        "banner_dwell": 20,                 # seconds a game's background stays before fading to its next one (his ask, 15 Oct)
        "guard_on": True,                   # App guard watches for new programs (his OK on the prototype, 18 Oct)
        "guard_signed": True,               # validly signed programs go through by themselves (still logged)
        "guard_scan": True,                 # Defender scans each new program's file
        "guard_downloads": True,            # each new download is checked; a warning only when it's risky (18 Oct)
        "guard_usb": True,                  # a USB stick is checked when it's plugged in (18 Oct)
        "dl_subs": "off",                   # subtitles with downloaded videos: off, made (the uploader's own) or auto (also YouTube's automatic ones)
    }


def check(key, value):
    """Returns (ok, clean value or reason)."""
    if key == "look":
        return (value in LOOKS, value if value in LOOKS else "Unknown look.")
    if key == "accent":
        ok = value == "" or (isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is not None)
        return (ok, value.upper() if ok else "An accent is a colour like #FFCF3F.")
    if key == "keep":
        return (value in ("both", "video", "audio"), value if value in ("both", "video", "audio") else "Pick video + sound, video only or just the sound.")
    if key == "send_to":
        ok = value in SEND_TO
        return (ok, value if ok else "Pick the Toolbelt folder, Desktop, Videos/Music, Spotify or a folder of your own.")
    if key == "custom_folder":
        if value == "":
            return (True, "")
        if not isinstance(value, str):
            return (False, "Pick a folder.")
        path = Path(value.strip())
        return (path.is_absolute(), str(path) if path.is_absolute() else "Pick a full folder path.")
    if key == "banner_dwell":
        return (value in (10, 20, 45, 90), value if value in (10, 20, 45, 90) else "Pick 10, 20, 45 or 90 seconds.")
    if key == "cover_motion":
        return (value in ("still", "hover", "always"), value if value in ("still", "hover", "always") else "Pick Still, Move on hover or Always move.")
    if key == "dl_subs":
        return (value in ("off", "made", "auto"), value if value in ("off", "made", "auto") else "Pick Off, Only real subtitles or Also automatic ones.")
    if key == "audio_format":
        return (value in ("mp3", "m4a", "opus"), value if value in ("mp3", "m4a", "opus") else "Pick MP3, M4A or Opus.")
    if key in ("animations", "never_overwrite", "folder_per_tool", "open_when_done", "watch_clipboard", "auto_spotify", "calc_key", "win_t", "own_bar", "guard_on", "guard_signed", "guard_scan", "guard_downloads", "guard_usb"):
        return (isinstance(value, bool), value if isinstance(value, bool) else "This one is on or off.")
    if key == "save_to":
        if not isinstance(value, str) or not value.strip():
            return (False, "Pick a folder.")
        path = Path(value.strip())
        return (path.is_absolute(), str(path) if path.is_absolute() else "Pick a full folder path, like C:\\Users\\you\\Downloads.")
    if key == "name_pattern":
        if not isinstance(value, str) or not value.strip() or len(value) > 120:
            return (False, "Give a name pattern, for example {title} - {quality}.{ext}")
        if BAD_NAME_CHARS.search(value):
            return (False, 'File names can\'t contain \\ / : * ? " < > |')
        if "{ext}" not in value:
            return (False, "Keep {ext} in it, so files get the right ending.")
        return (True, value.strip())
    return (False, "Unknown setting.")


class Settings:
    def __init__(self, folder=DATA):
        self.file = Path(folder) / "settings.json"
        self.values = defaults()
        try:
            stored = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored = {}
        if isinstance(stored, dict):
            for key, value in stored.items():
                if key in self.values:
                    ok, clean = check(key, value)
                    if ok:
                        self.values[key] = clean

    def get(self):
        return dict(self.values)

    def set(self, key, value):
        ok, clean = check(key, value)
        if not ok:
            return {"ok": False, "message": clean, "settings": self.get()}
        self.values[key] = clean
        self._save()
        return {"ok": True, "message": "", "settings": self.get()}

    def _save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
        os.replace(tmp, self.file)                     # all or nothing: never a half-written file
