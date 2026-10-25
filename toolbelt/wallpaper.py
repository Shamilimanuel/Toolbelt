"""Wallpaper Engine's wallpapers as game backgrounds (his idea, 15 Oct: "From Wallpaper Engine" in Edit artwork).

Wallpaper Engine keeps each wallpaper in its own folder with a project.json (title, type, file, preview):
  <Steam library>\\steamapps\\workshop\\content\\431960\\<id>\\   the ones he subscribed to in the Workshop
  <Steam library>\\steamapps\\common\\wallpaper_engine\\projects\\myprojects\\<name>\\   the ones he made himself
A video wallpaper is a real MP4/WebM, so it becomes a moving background. Scene and web wallpapers only exist inside
Wallpaper Engine, so their preview (often a small GIF) is used; Toolbelt's HD worker sharpens it afterwards.
Only reads these folders; nothing is changed in Wallpaper Engine.
"""
import json
from pathlib import Path

import games
import media

WE_APPID = "431960"
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi"}
MAX_DIRECT = 40 * 1024 * 1024                    # set_art's own limit; bigger videos get a smaller copy first


def roots(steam=None):
    """Every folder that holds wallpapers, in every Steam library."""
    base = Path(steam) if steam else games.steam_dir()
    if not base:
        return []
    libraries = [base]
    folders = games.parse_vdf(games._read(base / "steamapps" / "libraryfolders.vdf")).get("libraryfolders", {})
    for entry in folders.values():
        if isinstance(entry, dict) and entry.get("path"):
            p = Path(entry["path"])
            if p.is_dir() and p not in libraries:
                libraries.append(p)
    out = []
    for lib in libraries:
        for folder in (lib / "steamapps" / "workshop" / "content" / WE_APPID, lib / "steamapps" / "common" / "wallpaper_engine" / "projects" / "myprojects"):
            if folder.is_dir():
                out.append(folder)
    return out


def _project(folder):
    try:
        data = json.loads((folder / "project.json").read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    kind = str(data.get("type") or "").lower()
    file = folder / str(data.get("file") or "") if data.get("file") else None
    preview = folder / str(data.get("preview") or "") if data.get("preview") else None
    if preview and not preview.is_file():
        preview = None
    if kind == "video" and file and file.is_file() and file.suffix.lower() in VIDEO_EXT:
        use, what = file, "video"
    elif preview:
        use, what = preview, "gif" if preview.suffix.lower() == ".gif" else "pic"
    else:
        return None
    return {"id": folder.name, "title": str(data.get("title") or folder.name)[:120], "type": kind or "scene", "kind": what,
            "path": str(use), "preview": str(preview) if preview else "", "size": use.stat().st_size,
            "tags": [str(t) for t in (data.get("tags") or []) if isinstance(t, str)][:4]}


def wallpapers(steam=None):
    """All usable wallpapers: videos first, then the rest, each group by title."""
    out, seen = [], set()
    for root in roots(steam):
        for folder in root.iterdir():
            if folder.is_dir() and folder.name not in seen:
                item = _project(folder)
                if item:
                    seen.add(folder.name)
                    out.append(item)
    out.sort(key=lambda w: (w["kind"] != "video", w["title"].lower()))
    return out


def find(wp_id, steam=None):
    return next((w for w in wallpapers(steam) if w["id"] == str(wp_id)), None)


def needs_copy(item):
    """A video wallpaper that's too big (often 4K and hundreds of MB) or too long gets a smaller copy first."""
    if item["kind"] != "video":
        return False
    if item["size"] > MAX_DIRECT:
        return True
    info = media.probe(item["path"]) or {}
    return float(info.get("duration") or 0) > 60


def small_copy(job, item, folder):
    """1920 px wide at most, no sound, the first 60 seconds, as an MP4 that set_art accepts. Returns the new file."""
    ff = media.ffmpeg()
    if not ff:
        raise RuntimeError("Install ffmpeg first (Engines).")
    info = media.probe(item["path"]) or {}
    seconds = min(float(info.get("duration") or 60), 60.0)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / ("wallpaper-%s.mp4" % "".join(c for c in item["id"] if c.isalnum())[:40])
    args = ["-i", item["path"], "-t", "%.2f" % seconds, "-an",
            "-vf", "scale='min(1920,iw)':-2:flags=lanczos,fps='min(60,source_fps)'", "-c:v", "libx264", "-preset", "medium",
            "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-fs", str(MAX_DIRECT - 1024 * 1024), str(out)]
    media.run(job, args, seconds, "Making a background-sized copy")
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError("ffmpeg didn't make the copy.")
    return out


def thumb(item, width=320):
    """A small still for the picker (the preview's first frame, or a frame of the video)."""
    src = item.get("preview") or item["path"]
    return media.thumbnail(src, 0, width) if src else ""
