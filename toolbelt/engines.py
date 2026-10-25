"""The engines: the outside programs and AI models Toolbelt uses, all in %LOCALAPPDATA%\\Toolbelt\\engines.

Step 1 only finds out what is there and how big it is. Installing and updating come with the tool that needs
each engine (step 2 for yt-dlp, Deno and ffmpeg), and always ask first.
"""
import os
import subprocess
from pathlib import Path

from settings import DATA

ENGINES_DIR = DATA / "engines"
NO_WINDOW = 0x08000000                                  # CREATE_NO_WINDOW: never flash a console on screen

# id, name, what it does, licence, about how big, the file that shows it is installed, which step brings it
CATALOG = [
    ("yt-dlp", "yt-dlp", "downloads videos", "Unlicense", "~18 MB", "yt-dlp/yt-dlp.exe", 2),
    ("deno", "Deno", "needed for YouTube", "MIT", "~95 MB", "deno/deno.exe", 2),
    ("ffmpeg", "ffmpeg", "joins, converts, compresses", "GPL", "~200 MB", "ffmpeg/bin/ffmpeg.exe", 2),
    ("birefnet", "BiRefNet", "cut-outs, careful model", "MIT", "~930 MB", "birefnet/birefnet.onnx", 3),
    ("realesrgan", "Real-ESRGAN", "AI upscaling, GIF sharpening", "BSD", "~45 MB", "realesrgan/realesrgan-ncnn-vulkan.exe", 6),
    # whisper.cpp + its model (subtitles) were here 15 Oct; he found subtitles unnecessary, so they're off the list and
    # deleted from his PC. installer.py and media.subtitles still know them: put these two lines back to bring them back.
    # ("whisper", "whisper.cpp", "speech to text, for subtitles", "MIT", "~70 MB", "whisper/whisper-cli.exe", 10),
    # ("whispermodel", "Whisper model", "large-v3-turbo, many languages", "MIT", "~575 MB", "whispermodel/model.bin", 10),
]


def path_of(engine_id, base=None):
    """The program file of an installed engine, or None."""
    for eid, _name, _what, _lic, _approx, marker, _step in CATALOG:
        if eid == engine_id:
            p = Path(base or ENGINES_DIR) / marker
            return p if p.exists() else None
    return None


def folder_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def version_of(engine_id, base=None):
    """Each installer writes a version.txt next to the engine (step 2 onwards)."""
    try:
        return (Path(base or ENGINES_DIR) / engine_id / "version.txt").read_text(encoding="utf-8").strip()[:40]
    except OSError:
        return ""


def list_engines(base=None):
    base = Path(base) if base else ENGINES_DIR
    items, total = [], 0
    for engine_id, name, what, licence, approx, marker, step in CATALOG:
        installed = (base / marker).exists()
        size = folder_size(base / engine_id) if installed else 0
        total += size
        items.append({"id": engine_id, "name": name, "what": what, "licence": licence, "approx": approx,
                      "installed": installed, "size": size, "version": version_of(engine_id, base) if installed else "", "step": step})
    return {"engines": items, "total": total, "folder": str(base)}


_gpu_cache = None


def gpus():
    """The graphics cards Windows reports, read once (DirectML, Vulkan and AMF speed-ups depend on it)."""
    global _gpu_cache
    if _gpu_cache is None:
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                  "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }"],
                                 capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
            _gpu_cache = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        except (OSError, subprocess.SubprocessError):
            _gpu_cache = []
    return list(_gpu_cache)
