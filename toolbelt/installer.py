"""Installs and updates the downloader engines (yt-dlp, Deno, ffmpeg) into %LOCALAPPDATA%\\Toolbelt\\engines.

Only from the makers' official places (yt-dlp and Deno: their GitHub releases; ffmpeg: gyan.dev, the build that
ffmpeg.org links for Windows). Every download is checked against the SHA-256 fingerprint the maker publishes; a file
that doesn't match is thrown away and nothing is installed. He agreed to these three on 13 Oct (step 2), and to the BiRefNet cut-out model (step 3).

BiRefNet's official release has no published fingerprint, so its file is checked against the MD5 that rembg (the
well-known cut-out tool that uses the very same file) records in its source: two independent places must agree.
"""
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import engines

AGENT = {"User-Agent": "Toolbelt (Shamil's own app)"}
GYAN = "https://www.gyan.dev/ffmpeg/builds"
BIREFNET_URL = "https://github.com/ZhengPeng7/BiRefNet/releases/download/v1/BiRefNet-general-epoch_244.onnx"
BIREFNET_MD5 = "7a35a0141cbbc80de11d9c9a28f52697"      # from rembg/sessions/birefnet_general.py (13 Oct 2026)
BIREFNET_VERSION = "general-epoch_244"
# Real-ESRGAN's official Windows build has no published fingerprint either; this SHA-256 is the one the
# manga-translator-ui project records for the very same file (manga_translator/upscaling/esrgan.py, 13 Oct 2026).
REALESRGAN_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"
REALESRGAN_SHA = "abc02804e17982a3be33675e4d471e91ea374e65b70167abc09e31acb412802d"
REALESRGAN_VERSION = "0.2.5.0 (20220424)"
# Subtitles (agreed 15 Oct): whisper.cpp's own Windows build (the OpenBLAS one, fast on his Ryzen) from its GitHub
# releases, fingerprint from GitHub, and the large-v3-turbo model from the maker's Hugging Face page, whose
# fingerprint is the SHA-256 Hugging Face itself records for the file (checked 15 Oct 2026).
WHISPER_REPO = "ggml-org/whisper.cpp"
WHISPER_ZIP = "whisper-blas-bin-x64.zip"
WHISPER_MODEL = "ggml-large-v3-turbo-q5_0.bin"
WHISPER_MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/" + WHISPER_MODEL
WHISPER_MODEL_SHA = "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"


class InstallError(Exception):
    pass


def fetch_json(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_text(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def github_asset(repo, name):
    """The newest release of a GitHub project: its version and the download link + fingerprint of one file."""
    release = fetch_json("https://api.github.com/repos/%s/releases/latest" % repo)
    for asset in release.get("assets", []):
        if asset["name"] == name:
            digest = asset.get("digest") or ""
            if not digest.startswith("sha256:"):
                raise InstallError("GitHub gave no fingerprint for %s, so it isn't installed." % name)
            return release["tag_name"].lstrip("v"), asset["browser_download_url"], digest[7:], asset["size"]
    raise InstallError("The newest %s release has no %s." % (repo, name))


def github_asset_any(repo, name, pages=10):
    """Like github_asset, but the newest release that HAS the file (whisper.cpp puts its builds on b-releases)."""
    for release in fetch_json("https://api.github.com/repos/%s/releases?per_page=%d" % (repo, pages)):
        for asset in release.get("assets", []):
            if asset["name"] == name:
                digest = asset.get("digest") or ""
                if not digest.startswith("sha256:"):
                    raise InstallError("GitHub gave no fingerprint for %s, so it isn't installed." % name)
                return release["tag_name"].lstrip("v"), asset["browser_download_url"], digest[7:], asset["size"]
    raise InstallError("No recent %s release has %s." % (repo, name))


def latest(engine_id):
    """(version, url, sha256, size) of the newest official build."""
    if engine_id == "yt-dlp":
        return github_asset("yt-dlp/yt-dlp", "yt-dlp.exe")
    if engine_id == "deno":
        return github_asset("denoland/deno", "deno-x86_64-pc-windows-msvc.zip")
    if engine_id == "ffmpeg":
        version = fetch_text(GYAN + "/release-version").strip()
        if not version or len(version) > 20:
            raise InstallError("gyan.dev didn't say which ffmpeg is newest.")
        name = "ffmpeg-%s-essentials_build.zip" % version
        sha = fetch_text("%s/packages/%s.sha256" % (GYAN, name)).split()[0].strip().lower()
        if len(sha) != 64:
            raise InstallError("gyan.dev gave no proper fingerprint for ffmpeg, so it isn't installed.")
        return version, "%s/packages/%s" % (GYAN, name), sha, 0
    if engine_id == "birefnet":
        return BIREFNET_VERSION, BIREFNET_URL, "md5:" + BIREFNET_MD5, 973_000_000
    if engine_id == "realesrgan":
        return REALESRGAN_VERSION, REALESRGAN_URL, REALESRGAN_SHA, 45_500_000
    if engine_id == "whisper":
        return github_asset_any(WHISPER_REPO, WHISPER_ZIP)
    if engine_id == "whispermodel":
        return "large-v3-turbo q5_0", WHISPER_MODEL_URL, WHISPER_MODEL_SHA, 574_041_195
    raise InstallError("Toolbelt can't install %s yet." % engine_id)


def download(job, url, dest, sha256, size_hint, start, end, tries=6):
    """Streams url to dest, reporting progress between start and end percent, then checks the fingerprint.
    A stall or a dropped connection carries on from where it stopped (15 Oct: Hugging Face paused for 30 s mid-file)."""
    part = dest.with_name(dest.name + ".part")
    algo, _, expected = sha256.partition(":") if sha256.startswith("md5:") else ("sha256", "", sha256)
    digest = hashlib.new(algo)
    done, total = 0, size_hint
    try:
        with open(part, "wb") as out:
            for attempt in range(tries):
                headers = dict(AGENT, Range="bytes=%d-" % done) if done else AGENT
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                        if done and r.status != 206:                 # the server ignored "carry on from": start over
                            out.seek(0); out.truncate(); digest = hashlib.new(algo); done = 0
                        if not done:
                            total = int(r.headers.get("Content-Length") or 0) or size_hint
                        while True:
                            job.check()
                            chunk = r.read(256 * 1024)
                            if not chunk:
                                break
                            out.write(chunk)
                            digest.update(chunk)
                            done += len(chunk)
                            if total:
                                job.report(start + (end - start) * done / total, "Downloading %.0f of %.0f MB" % (done / 1048576, total / 1048576))
                    if not total or done >= total:
                        break
                except (TimeoutError, ConnectionError, OSError) as error:
                    if isinstance(error, urllib.error.HTTPError) or attempt == tries - 1:
                        raise
                    job.report(start + (end - start) * done / max(total or 1, 1), "The connection paused, carrying on (%d)" % (attempt + 1))
                    for _ in range(5 * 2 ** attempt):                # 5, 10, 20… seconds: the internet may be back by then
                        job.check()
                        time.sleep(1)
        if digest.hexdigest().lower() != expected.lower():
            raise InstallError("The download doesn't match the maker's fingerprint, so it was thrown away. Try again later.")
        part.replace(dest)
    finally:
        part.unlink(missing_ok=True)


def install(job, engine_id, base=None):
    """Downloads, checks and unpacks one engine. Replaces an older version only once the new one is complete."""
    base = Path(base) if base else engines.ENGINES_DIR
    job.report(1, "Asking for the newest version")
    version, url, sha, size = latest(engine_id)
    if engine_id == "deno" and tuple(int(x) for x in version.split(".")[:2]) < (2, 3):
        raise InstallError("yt-dlp needs Deno 2.3 or newer; the newest is %s." % version)
    staging = base / (engine_id + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        name = url.rsplit("/", 1)[1]
        file = staging / name
        download(job, url, file, sha, size, 3, 90)
        job.report(92, "Unpacking")
        if engine_id == "yt-dlp":
            pass                                             # yt-dlp.exe is the whole engine
        elif engine_id == "birefnet":
            file.rename(staging / "birefnet.onnx")
        elif engine_id == "realesrgan":                      # the program, its DLLs and its models folder
            with zipfile.ZipFile(file) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
                exe = next((n for n in names if n.rsplit("/", 1)[-1] == "realesrgan-ncnn-vulkan.exe"), None)
                if not exe:
                    raise InstallError("The Real-ESRGAN download has no realesrgan-ncnn-vulkan.exe in it.")
                top = exe[:-len("realesrgan-ncnn-vulkan.exe")]
                for n in names:
                    if n.startswith(top) and ".." not in n:
                        target = staging / n[len(top):]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(n) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            file.unlink()
        elif engine_id == "whispermodel":
            file.rename(staging / "model.bin")
        elif engine_id == "whisper":                         # only whisper-cli.exe and its DLLs (no server, no tests)
            with zipfile.ZipFile(file) as z:
                for n in z.namelist():
                    leaf = n.rsplit("/", 1)[-1]
                    if leaf == "whisper-cli.exe" or leaf.lower().endswith(".dll"):
                        with z.open(n) as src, open(staging / leaf, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            file.unlink()
            if not (staging / "whisper-cli.exe").exists():
                raise InstallError("The whisper.cpp download has no whisper-cli.exe in it.")
        elif engine_id == "deno":
            with zipfile.ZipFile(file) as z:
                if "deno.exe" not in z.namelist():
                    raise InstallError("The Deno download has no deno.exe in it.")
                z.extract("deno.exe", staging)
            file.unlink()
        else:                                                # ffmpeg: keep only bin\ffmpeg.exe and bin\ffprobe.exe
            (staging / "bin").mkdir()
            with zipfile.ZipFile(file) as z:
                for member in z.namelist():
                    leaf = member.rsplit("/", 1)[-1]
                    if member.count("/") >= 2 and member.split("/")[-2] == "bin" and leaf in ("ffmpeg.exe", "ffprobe.exe"):
                        with z.open(member) as src, open(staging / "bin" / leaf, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            file.unlink()
            if not (staging / "bin" / "ffmpeg.exe").exists():
                raise InstallError("The ffmpeg download has no ffmpeg.exe in it.")
        (staging / "version.txt").write_text(version, encoding="utf-8")
        job.check()
        target = base / engine_id
        old = base / (engine_id + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if target.exists():
            target.rename(old)
        staging.rename(target)
        shutil.rmtree(old, ignore_errors=True)
        job.report(100, "Installed %s %s" % (engine_id, version))
        return version
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def check_updates(base=None):
    """For each installed downloader engine: the installed and newest version (needs the internet)."""
    listing = engines.list_engines(base)
    result = {}
    for item in listing["engines"]:
        if item["id"] in ("yt-dlp", "deno", "ffmpeg", "birefnet", "realesrgan", "whisper", "whispermodel") and item["installed"]:
            try:
                newest = latest(item["id"])[0]
                result[item["id"]] = {"installed": item["version"], "newest": newest, "update": newest != item["version"]}
            except Exception as error:
                result[item["id"]] = {"installed": item["version"], "newest": "", "update": False, "error": str(error)}
    return result
