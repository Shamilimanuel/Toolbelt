r"""Check a file (step 8): fingerprints, who signed it, compare two files, a whole folder's list, and what a file really is.

- A fingerprint (hash) is a short code worked out from every byte of a file: change one byte and the code changes.
  Download sites publish them so you can see the file arrived unchanged. All four kinds are made in one pass.
- A signature is different: a company vouches for the file with a certificate; Windows can check it (Authenticode).
- Every file starts with a few bytes that say what it is (PNG, ZIP, EXE…), whatever the name claims.
"""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from jobs import Cancelled

NO_WINDOW = 0x08000000
ALGOS = ("md5", "sha1", "sha256", "sha512")
CHUNK = 4 * 1024 * 1024


class CheckError(Exception):
    pass


def hashes(job, path, algos=ALGOS):
    """All fingerprints of one file in a single read, with progress and Cancel."""
    path = Path(path)
    if not path.is_file():
        raise CheckError("That file isn't there.")
    total = path.stat().st_size or 1
    hs = {a: hashlib.new(a) for a in algos}
    done = 0
    with open(path, "rb") as f:
        while True:
            if job:
                job.check()
            block = f.read(CHUNK)
            if not block:
                break
            for h in hs.values():
                h.update(block)
            done += len(block)
            if job:
                job.report(100 * done / total, "Reading %d%%" % int(100 * done / total))
    return {a: h.hexdigest() for a, h in hs.items()}


def match(found, pasted):
    """Which kind the pasted code is (by its length) and whether it matches. Spaces, dashes and upper case don't matter."""
    code = "".join(ch for ch in str(pasted).strip().lower() if ch in "0123456789abcdef")
    kinds = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}
    algo = kinds.get(len(code))
    if not code:
        return {"ok": False, "algo": "", "message": "Paste a fingerprint first."}
    if not algo:
        return {"ok": False, "algo": "", "message": "That's %d characters: not an MD5 (32), SHA-1 (40), SHA-256 (64) or SHA-512 (128)." % len(code)}
    same = found.get(algo, "") == code
    return {"ok": same, "algo": algo, "message": ("The %s fingerprint matches: the file is exactly what the site published." if same else
                                                 "The %s fingerprint is DIFFERENT. The download is damaged or not the same file: don't run it, download it again.") % algo.upper().replace("SHA", "SHA-")}


def signature(path):
    """Who signed the file, through Windows' own check (Get-AuthenticodeSignature)."""
    path = Path(path)
    if not path.is_file():
        return {"ok": False, "message": "That file isn't there."}
    script = ("$s = Get-AuthenticodeSignature -LiteralPath '%s'; "
              "[pscustomobject]@{Status=$s.Status.ToString(); Message=$s.StatusMessage; Subject=$s.SignerCertificate.Subject; Issuer=$s.SignerCertificate.Issuer; "
              "NotBefore=if($s.SignerCertificate){$s.SignerCertificate.NotBefore.ToString('yyyy-MM-dd')}else{''}; NotAfter=if($s.SignerCertificate){$s.SignerCertificate.NotAfter.ToString('yyyy-MM-dd')}else{''}; "
              "TimeStamp=$s.TimeStamperCertificate.Subject} | ConvertTo-Json -Compress") % str(path).replace("'", "''")
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=NO_WINDOW)
        data = json.loads(done.stdout.strip() or "{}")
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "message": "Windows couldn't check the signature: %s" % str(error)[:120]}

    def cn(subject):
        for part in str(subject or "").split(","):
            part = part.strip()
            if part.startswith("CN="):
                return part[3:].strip('"')
        return str(subject or "")

    status = data.get("Status", "")
    if status == "UnknownError" and "not one supported" in str(data.get("Message", "")):
        status = "NotSignable"                                   # a picture, a text, a zip: this kind of file can't carry a signature
    verdicts = {"NotSignable": ("info", "This kind of file can't carry a signature", "Only programs, installers, scripts and drivers can be signed (EXE, DLL, MSI, PS1, SYS, CAB). For a %s, use the fingerprints instead." % (path.suffix.lstrip(".").upper() or "file")),"Valid": ("ok", "Signed by " + cn(data.get("Subject")), "The signature is valid and the file hasn't been changed since."),
                "NotSigned": ("warn", "Not signed", "Nobody vouches for this file. Not always bad (many small tools aren't signed), but be careful with anything that asks for admin rights."),
                "HashMismatch": ("bad", "Changed after signing", "The file was signed, but its contents changed afterwards. Don't run it."),
                "NotTrusted": ("bad", "Signed, but the signer isn't trusted", "Windows doesn't trust the certificate behind this signature."),
                "UnknownError": ("warn", "Couldn't be checked", data.get("Message") or "Windows couldn't verify this signature.")}
    level, title, why = verdicts.get(status, ("warn", status or "Unknown", data.get("Message") or ""))
    return {"ok": True, "status": status, "level": level, "title": title, "why": why, "signer": cn(data.get("Subject")), "issuer": cn(data.get("Issuer")),
            "from": data.get("NotBefore") or "", "until": data.get("NotAfter") or "", "timestamp": cn(data.get("TimeStamp"))}


def compare(job, a, b):
    """Are two files the same? Sizes first (cheap), then the SHA-256 of both."""
    a, b = Path(a), Path(b)
    if not a.is_file() or not b.is_file():
        raise CheckError("Pick two files first.")
    if a.stat().st_size != b.stat().st_size:
        return {"same": False, "why": "Different sizes: %s and %s bytes." % (format(a.stat().st_size, ","), format(b.stat().st_size, ","))}
    ha = hashes(job, a, ("sha256",))["sha256"]
    hb = hashes(job, b, ("sha256",))["sha256"]
    return {"same": ha == hb, "why": "Same size and the same SHA-256 fingerprint: you can safely delete one." if ha == hb else "Same size, but the contents differ.", "sha256": [ha, hb]}


# ---------- a whole folder: a list of every file's fingerprint, to check later ----------
def list_file_for(folder):
    folder = Path(folder)
    return folder.parent / (folder.name + ".sha256")


def folder_make(job, folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise CheckError("That folder isn't there.")
    files = [p for p in folder.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files) or 1
    done, lines = 0, []
    for i, p in enumerate(files):
        job.check()
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while True:
                block = f.read(CHUNK)
                if not block:
                    break
                h.update(block)
                done += len(block)
        lines.append("%s *%s" % (h.hexdigest(), p.relative_to(folder).as_posix()))
        job.report(100 * done / total, "%d of %d files" % (i + 1, len(files)))
    target = list_file_for(folder)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"path": str(target), "files": len(files), "bytes": total}


def folder_verify(job, folder, list_path=None):
    """Checks the folder against its list: changed, missing and new files."""
    folder = Path(folder)
    list_path = Path(list_path) if list_path else list_file_for(folder)
    if not list_path.is_file():
        raise CheckError("There is no fingerprint list for this folder yet. Make one first.")
    expected = {}
    for line in list_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or " " not in line:
            continue
        code, name = line.split(" ", 1)
        expected[name.lstrip("*").strip()] = code.lower()
    present = {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}
    changed, missing, new = [], [], sorted(set(present) - set(expected))
    total = sum(present[n].stat().st_size for n in expected if n in present) or 1
    done = 0
    for i, (name, code) in enumerate(expected.items()):
        job.check()
        if name not in present:
            missing.append(name)
            continue
        h = hashlib.sha256()
        with open(present[name], "rb") as f:
            while True:
                block = f.read(CHUNK)
                if not block:
                    break
                h.update(block)
                done += len(block)
        if h.hexdigest() != code:
            changed.append(name)
        job.report(100 * done / total, "%d of %d files" % (i + 1, len(expected)))
    return {"checked": len(expected), "changed": changed, "missing": missing, "new": new, "ok": not changed and not missing}


# ---------- what is it really? the first bytes of a file ----------
SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "PNG picture", ".png"), (b"\xff\xd8\xff", "JPEG picture", ".jpg"), (b"GIF87a", "GIF picture", ".gif"), (b"GIF89a", "GIF picture", ".gif"),
    (b"BM", "BMP picture", ".bmp"), (b"%PDF", "PDF document", ".pdf"), (b"MZ", "Windows program (EXE / DLL)", ".exe"), (b"\x7fELF", "Linux program", ""),
    (b"Rar!\x1a\x07", "RAR archive", ".rar"), (b"7z\xbc\xaf\x27\x1c", "7-Zip archive", ".7z"), (b"\x1f\x8b", "GZIP archive", ".gz"), (b"ID3", "MP3 song", ".mp3"),
    (b"\xff\xfb", "MP3 song", ".mp3"), (b"\xff\xf3", "MP3 song", ".mp3"), (b"fLaC", "FLAC song", ".flac"), (b"OggS", "Ogg sound / video", ".ogg"),
    (b"\x1a\x45\xdf\xa3", "MKV / WebM video", ".mkv"), (b"FWS", "Flash", ".swf"), (b"CWS", "Flash", ".swf"), (b"SQLite format 3\x00", "SQLite database", ".db"),
    (b"\x00\x00\x01\x00", "Windows icon", ".ico"), (b"wOFF", "Web font", ".woff"), (b"wOF2", "Web font", ".woff2"), (b"\xd0\xcf\x11\xe0", "Old Office document", ".doc"),
]
DANGEROUS = {".exe", ".scr", ".com", ".pif", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jar", ".msi", ".hta", ".lnk"}
DOC_LIKE = {".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4", ".zip", ".xlsx", ".pptx"}


def sniff(path):
    path = Path(path)
    if not path.is_file():
        return {"ok": False, "message": "That file isn't there."}
    with open(path, "rb") as f:
        head = f.read(64)
    ext = path.suffix.lower()
    real, want = "", ""
    for magic, name, suffix in SIGNATURES:
        if head.startswith(magic):
            real, want = name, suffix
            break
    if not real and head[:4] == b"RIFF" and len(head) >= 12:
        kind = head[8:12]
        real, want = {b"WEBP": ("WebP picture", ".webp"), b"WAVE": ("WAV sound", ".wav"), b"AVI ": ("AVI video", ".avi")}.get(kind, ("RIFF file", ""))
    if not real and len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        real, want = ("HEIC picture", ".heic") if brand in (b"heic", b"heix", b"mif1") else ("MP4 / MOV video", ".mp4")
    if not real and head[:4] == b"PK\x03\x04":
        real, want = "ZIP archive", ".zip"
        if ext in (".docx", ".xlsx", ".pptx", ".jar", ".apk", ".zip", ".odt", ".ods", ".epub"):
            real, want = {".docx": "Word document", ".xlsx": "Excel sheet", ".pptx": "PowerPoint", ".jar": "Java program", ".apk": "Android app", ".odt": "OpenDocument text", ".ods": "OpenDocument sheet", ".epub": "E-book"}.get(ext, "ZIP archive"), ext
    if not real:
        try:
            text = head.decode("utf-8")
            if "\x00" not in text:
                real, want = "Plain text", ".txt"
        except UnicodeDecodeError:
            pass
    if not real:
        real, want = "Unknown (no known first bytes)", ""
    parts = path.name.lower().split(".")
    double = len(parts) >= 3 and "." + parts[-2] in DOC_LIKE and ext in DANGEROUS
    verdict, advice = "ok", ""
    if real.startswith("Windows program") and ext not in DANGEROUS | {".dll", ".sys", ".ocx", ".cpl", ".efi"}:
        verdict, advice = "danger", "A program pretending to be a %s. Don't open it." % (ext.lstrip(".") or "file")
    elif double:
        verdict, advice = "danger", "A %s with a second, fake ending (%s). Don't open it." % (real, "." + parts[-2])
    elif want and ext != want and not (want == ".jpg" and ext == ".jpeg") and not (want == ".mp4" and ext in (".mov", ".m4a", ".m4v")) and not (want == ".mkv" and ext == ".webm") and not (want == ".exe" and ext in (".dll", ".sys", ".scr", ".ocx", ".cpl", ".efi")):
        verdict, advice = "warn", "Really a %s: rename it to %s" % (real, want)
    return {"ok": True, "name": path.name, "ext": ext, "real": real, "want": want, "verdict": verdict, "advice": advice, "size": path.stat().st_size}
